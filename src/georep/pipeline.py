"""Schrittregister: jeder Schritt kennt Eingaben, Ausgaben und seine Schema-Version.

Ein Stamp neben der ersten Ausgabe hält fest, womit sie entstand: Hashes der Eingaben,
Fingerprint der Settings, Code-Version, Schema-Version. Stimmt alles, ist der Schritt aktuell
und wird übersprungen; ``force`` erzwingt, ``dry_run`` plant nur. Jeder Lauf nennt, was er getan
hat und warum (docs/architecture.md, „Pipeline" und „Sicherheit").
"""

from __future__ import annotations

import datetime as dt
import json
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import polars as pl

from georep import __version__
from georep.analysis.hits import hits_by_district, join_voters
from georep.errors import GeorepError, MissingInputError
from georep.geo import PrecinctIndex, read_precincts
from georep.http import Transport
from georep.io import digest, write_bytes, write_json, write_parquet
from georep.layout import Layout
from georep.prep.extract import extract_missing
from georep.prep.papers import CORPUS_SCHEMA_VERSION, build_corpus, documents_with_text
from georep.prep.pois import clean_pois, pois_by_district, read_pois_json
from georep.prep.streets import read_streets_json, streets_by_district
from georep.prep.voters import aggregate_voters, read_results_csv
from georep.report.build import MAP_NAME, SCHEMA_NAME, build_site, current_commit
from georep.search.dictionary import all_terms, build_dictionary
from georep.search.index import build_index
from georep.settings import Settings
from georep.sources import cached_session
from georep.sources.oparl import fetch_papers
from georep.sources.opendata import fetch_districts_geojson, fetch_results_csv
from georep.sources.overpass import fetch_streets_per_precinct
from georep.sources.pdfs import PdfStore
from georep.sources.wiki import fetch_geosearch_pois, fetch_sparql_pois, sparql_query
from georep.stores import PaperStore, TextStore

Status = Literal["ausgeführt", "übersprungen", "geplant"]


@dataclass(frozen=True)
class Step:
    name: str
    inputs: tuple[Path, ...]
    outputs: tuple[Path, ...]
    run: Callable[[], str]
    schema_version: int = 1
    network: bool = False

    @property
    def stamp_path(self) -> Path:
        first = self.outputs[0]
        return first.with_name(first.name + ".stamp.json")


@dataclass(frozen=True)
class Outcome:
    step: str
    status: Status
    reason: str
    seconds: float = 0.0

    def line(self) -> str:
        took = f" ({self.seconds:.1f} s)" if self.status == "ausgeführt" else ""
        return f"{self.step:<12} {self.status:<13} {self.reason}{took}"


class UnknownStepError(GeorepError):
    """Ein angeforderter Schrittname existiert nicht."""


def input_digests(step: Step) -> dict[str, str]:
    return {p.name: digest(p) for p in step.inputs}


def expected_stamp(step: Step, settings: Settings) -> dict[str, object]:
    return {
        "step": step.name,
        "schema_version": step.schema_version,
        "settings": settings.fingerprint(),
        "code": __version__,
        "inputs": input_digests(step),
        "outputs": [p.name for p in step.outputs],
    }


def freshness(step: Step, settings: Settings) -> tuple[bool, str]:
    """(aktuell?, Grund). Prüft Ausgaben, Stamp, Eingaben, dann den Inhalt des Stamps."""
    missing_out = [p.name for p in step.outputs if not p.exists()]
    if missing_out:
        return False, f"Ausgabe fehlt: {', '.join(missing_out)}"
    if not step.stamp_path.exists():
        return False, "kein Stamp"
    missing_in = [p.name for p in step.inputs if not p.exists()]
    if missing_in:
        return False, f"Eingabe fehlt: {', '.join(missing_in)}"
    try:
        stamped = json.loads(step.stamp_path.read_text(encoding="utf-8"))
    except ValueError:
        return False, "Stamp unlesbar"
    reason = stamp_mismatch(stamped, step, settings)
    return (True, "aktuell") if reason is None else (False, reason)


def stamp_mismatch(stamped: dict[str, object], step: Step, settings: Settings) -> str | None:
    """Der erste Grund, aus dem ein gelesener Stamp nicht mehr zu Schritt und Settings passt."""
    if stamped.get("schema_version") != step.schema_version:
        return "Schema geändert"
    if stamped.get("settings") != settings.fingerprint():
        return "Settings geändert"
    if stamped.get("code") != __version__:
        return f"Code-Version {stamped.get('code')} -> {__version__}"
    stamped_inputs = stamped.get("inputs")
    known = stamped_inputs if isinstance(stamped_inputs, dict) else {}
    changed = [name for name, value in input_digests(step).items() if known.get(name) != value]
    if changed:
        return f"Eingabe geändert: {', '.join(changed)}"
    return None


def run_step(
    step: Step,
    settings: Settings,
    *,
    force: bool = False,
    dry_run: bool = False,
    online: bool = False,
) -> Outcome:
    if step.network and not online:
        return Outcome(step.name, "übersprungen", "Netz aus; `--online` oder `georep fetch`")
    fresh, reason = freshness(step, settings)
    if fresh and not force:
        return Outcome(step.name, "übersprungen", reason)
    if force:
        reason = "erzwungen"
    if dry_run:
        # Frühere geplante Schritte erzeugen ihre Ausgaben erst im echten Lauf.
        return Outcome(step.name, "geplant", reason)
    missing = [str(p) for p in step.inputs if not p.exists()]
    if missing:
        raise MissingInputError(
            f"Schritt {step.name}: Eingaben fehlen: {', '.join(missing)}. "
            "Fehlt der Korpus oder die Rohdaten, hilft `georep bootstrap`."
        )
    started = time.perf_counter()
    summary = step.run()
    stamp = expected_stamp(step, settings) | {"written": dt.datetime.now(dt.UTC).isoformat()}
    write_json(step.stamp_path, stamp)
    outcome = Outcome(
        step.name, "ausgeführt", f"{reason}; {summary}", time.perf_counter() - started
    )
    return outcome


def select_steps(steps: Sequence[Step], names: Iterable[str] | None) -> list[Step]:
    wanted = list(names or [])
    if not wanted:
        return list(steps)
    known = {s.name: s for s in steps}
    unknown = [n for n in wanted if n not in known]
    if unknown:
        raise UnknownStepError(f"Unbekannte Schritte: {unknown}; bekannt: {list(known)}")
    return [s for s in steps if s.name in wanted]


def run_pipeline(
    steps: Sequence[Step],
    settings: Settings,
    names: Iterable[str] | None = None,
    *,
    force: bool = False,
    dry_run: bool = False,
    online: bool = False,
) -> list[Outcome]:
    return [
        run_step(s, settings, force=force, dry_run=dry_run, online=online)
        for s in select_steps(steps, names)
    ]


# --- die Schritte ---------------------------------------------------------------------------


def build_steps(
    settings: Settings,
    layout: Layout,
    http: Transport | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Step]:
    """Alle Schritte in Reihenfolge; Netzschritte laufen nur mit ``online``.

    ``http`` ist die Testnaht: ohne Angabe entsteht die gecachte Session erst, wenn ein Netzschritt
    sie braucht.
    """
    columns = settings.columns.results
    oparl = settings.sources.oparl
    session: Transport | None = http

    def transport() -> Transport:
        nonlocal session
        if session is None:
            session = cached_session(settings, layout.http_cache)
        return session

    def opendata() -> str:
        csv = fetch_results_csv(transport(), settings.sources.opendata.results_url, sep=columns.sep)
        write_bytes(layout.results_csv, csv)
        geo = fetch_districts_geojson(transport(), settings.sources.opendata.districts_url)
        write_json(layout.districts_geojson, geo, indent=None)
        return f"{len(csv)} Bytes Wahlergebnis, {len(geo['features'])} Stimmbezirke"

    def papers() -> str:
        store = PaperStore(layout.papers)
        known = store.load()
        since: dt.datetime | None = None
        if known and oparl.incremental:
            newest = max((r.modified for r in known.values() if r.modified), default=None)
            if newest is not None:
                since = newest - dt.timedelta(days=1)
        records, fetched = fetch_papers(
            transport(),
            oparl.endpoint,
            settings.period,
            delay_s=oparl.delay_s,
            modified_since=since,
            stop_when_older=oparl.stop_when_older,
            sleep=sleep,
        )
        report = store.upsert(records)
        mode = f"seit {since.date()}" if since else "vollständig"
        return f"{mode}: {fetched.summary()}; Store {report.summary()}"

    def pdfs() -> str:
        records = PaperStore(layout.papers).load().values()
        report = PdfStore(layout.pdf_dir).download(
            transport(), records, delay_s=oparl.delay_s, limit=oparl.pdf_limit or None, sleep=sleep
        )
        return report.summary()

    def streets_osm() -> str:
        found = read_precincts(layout.districts_geojson, settings.columns, settings.geo.working_crs)
        entries = fetch_streets_per_precinct(
            transport(),
            settings.sources.osm.overpass_endpoint,
            found,
            settings.geo.working_crs,
            tolerance_m=settings.sources.osm.simplify_m,
            delay_s=settings.sources.osm.delay_s,
            sleep=sleep,
        )
        write_json(layout.streets, entries, indent=None)
        names = sum(len(e["straßen"]) for e in entries)
        return f"{len(entries)} Stimmbezirke, {names} Straßennamen"

    def pois_wiki() -> str:
        wiki = settings.sources.wikidata
        found = read_precincts(layout.districts_geojson, settings.columns, settings.geo.working_crs)
        index = PrecinctIndex(found, settings.geo.working_crs)
        sparql = fetch_sparql_pois(
            transport(), wiki.sparql_endpoint, sparql_query(wiki.entity, wiki.language), index
        )
        geosearch = fetch_geosearch_pois(
            transport(),
            wiki.wikipedia_api,
            found,
            index,
            settings.geo.working_crs,
            limit=wiki.geosearch_limit,
            delay_s=wiki.delay_s,
            sleep=sleep,
        )
        entries = sparql + geosearch
        write_json(layout.pois, entries, indent=None)
        assigned = sum(1 for e in entries if e["wahlkreis_id"] is not None)
        return f"{len(sparql)} per SPARQL, {len(geosearch)} per GeoSearch, {assigned} zugeordnet"

    def texts() -> str:
        store = TextStore(layout.texts)
        names = [r.file_name for r in PaperStore(layout.papers).load().values() if r.file_name]
        report = extract_missing(
            PdfStore(layout.pdf_dir), store, names, settings.search.text_split_marker
        )
        if not layout.texts.exists():
            store.save()
        return report.summary()

    def voters() -> str:
        frame = aggregate_voters(read_results_csv(layout.results_csv, columns), columns)
        write_parquet(frame, layout.voters, schema_version=1)
        return f"{frame.height} Wahlbezirke"

    def streets() -> str:
        frame = streets_by_district(read_streets_json(layout.streets))
        write_parquet(frame, layout.streets_by_district, schema_version=1)
        return f"{frame.height} Wahlbezirke, {frame.get_column('suchbegriffe').list.len().sum()} Straßennamen"

    def pois() -> str:
        clean = clean_pois(read_pois_json(layout.pois), settings.search.exclude)
        grouped = pois_by_district(clean)
        write_parquet(clean, layout.pois_table, schema_version=1)
        write_parquet(grouped, layout.pois_by_district, schema_version=1)
        return f"{clean.height} Orte in {grouped.height} Wahlbezirken"

    def dictionary() -> str:
        frame = build_dictionary(
            pl.read_parquet(layout.pois_by_district), pl.read_parquet(layout.streets_by_district)
        )
        write_parquet(frame, layout.dictionary, schema_version=1)
        return f"{len(all_terms(frame))} Begriffe in {frame.height} Wahlbezirken"

    def corpus() -> str:
        records = PaperStore(layout.papers).load().values()
        frame = build_corpus(records, TextStore(layout.texts))
        write_parquet(frame, layout.corpus, schema_version=CORPUS_SCHEMA_VERSION)
        return f"{frame.height} Dokumente, {documents_with_text(frame)} mit Text"

    def index() -> str:
        terms = all_terms(pl.read_parquet(layout.dictionary))
        corpus = pl.read_parquet(layout.corpus, columns=["id", "text"])
        frame = build_index(corpus, terms)
        write_parquet(frame, layout.index, schema_version=1)
        return f"{frame.height} Begriffe, {int(frame.get_column('anzahl_treffer').sum())} Treffer in {corpus.height} Dokumenten"

    def results() -> str:
        hits = hits_by_district(
            pl.read_parquet(layout.dictionary),
            pl.read_parquet(layout.index),
            settings.search.hide_in_display,
        )
        frame = join_voters(hits, pl.read_parquet(layout.voters), columns.eligible)
        write_parquet(frame, layout.results, schema_version=1)
        return (
            f"{frame.height} Wahlbezirke, {int(frame.get_column('anzahl_treffer').sum())} Treffer"
        )

    def report() -> str:
        return build_site(
            layout, settings, now=dt.datetime.now(dt.UTC), commit=current_commit()
        ).line()

    return [
        Step(
            "opendata", (), (layout.results_csv, layout.districts_geojson), opendata, network=True
        ),
        Step("papers", (), (layout.papers,), papers, network=True),
        Step("pdfs", (layout.papers,), (layout.pdf_manifest,), pdfs, network=True),
        Step(
            "streets_osm", (layout.districts_geojson,), (layout.streets,), streets_osm, network=True
        ),
        Step("pois_wiki", (layout.districts_geojson,), (layout.pois,), pois_wiki, network=True),
        Step("texts", (layout.papers, layout.pdf_manifest), (layout.texts,), texts),
        Step("voters", (layout.results_csv,), (layout.voters,), voters),
        Step("streets", (layout.streets,), (layout.streets_by_district,), streets),
        Step("pois", (layout.pois,), (layout.pois_table, layout.pois_by_district), pois),
        Step(
            "dictionary",
            (layout.pois_by_district, layout.streets_by_district),
            (layout.dictionary,),
            dictionary,
        ),
        Step(
            "corpus",
            (layout.papers, layout.texts),
            (layout.corpus,),
            corpus,
            CORPUS_SCHEMA_VERSION,
        ),
        Step("index", (layout.dictionary, layout.corpus), (layout.index,), index),
        Step(
            "results", (layout.dictionary, layout.index, layout.voters), (layout.results,), results
        ),
        Step(
            "report",
            (
                layout.results,
                layout.dictionary,
                layout.index,
                layout.voters,
                layout.pois_table,
                layout.streets_by_district,
                layout.corpus,
                layout.districts_geojson,
            ),
            (layout.site_index, layout.site_data / SCHEMA_NAME, layout.site / MAP_NAME),
            report,
        ),
    ]
