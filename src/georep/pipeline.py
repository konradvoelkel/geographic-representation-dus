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
from georep.analysis.bodies import documents_by_body, hits_by_body
from georep.analysis.bodies import summary as bodies_summary
from georep.analysis.hits import DISTRICT, hits_by_district, join_voters
from georep.analysis.ols import model_frame, model_terms, models_table
from georep.analysis.parties import (
    classify_originators,
    originator_figures,
    originators_by_district,
    party_hits,
    read_organizations,
)
from georep.analysis.periods import compare_periods, delta_regression
from georep.crosswalk import (
    COVERAGE,
    SHARE,
    SOURCE,
    TARGET,
    area_shares,
    assign_by_point,
    district_weights,
    transfer_counts,
)
from georep.errors import GeorepError, MissingInputError, SchemaError
from georep.geo import (
    Area,
    PrecinctIndex,
    read_area_names,
    read_areas,
    read_canonical_precincts,
    read_precincts,
)
from georep.http import Transport
from georep.io import digest, write_bytes, write_json, write_parquet
from georep.layout import Layout
from georep.prep.bodies import BODIES_SCHEMA_VERSION, BodyRules, classify_papers
from georep.prep.bodies import summary as papers_bodies_summary
from georep.prep.context import (
    MISSING_SUFFIX,
    aggregate_context,
    district_variables,
    precinct_table,
    read_context_table,
)
from georep.prep.extract import extract_missing
from georep.prep.papers import CORPUS_SCHEMA_VERSION, build_corpus, documents_with_text
from georep.prep.pois import clean_pois, pois_by_district, read_pois_json
from georep.prep.precincts import canonical_precincts, district_names_from_csv, read_source
from georep.prep.streets import directory_agreement, read_streets_json, streets_by_district
from georep.prep.voters import (
    ELIGIBLE_TOTAL,
    PRECINCT,
    SOURCE_DISTRICT,
    VOTERS,
    aggregate_voters,
    check_postal_total,
    count_columns,
    district_results,
    district_units,
    precinct_counts,
    read_results_csv,
    spread_postal,
    with_shares,
)
from georep.records import PaperRecord
from georep.report.build import MAP_NAME, SCHEMA_NAME, build_site, current_commit
from georep.report.geometry import district_shapes
from georep.search.dictionary import all_terms, build_dictionary
from georep.search.index import build_index
from georep.settings import Settings
from georep.sources import cached_session
from georep.sources.oparl import (
    fetch_organizations,
    fetch_papers,
    read_progress,
    write_progress,
)
from georep.sources.opendata import fetch_csv, fetch_districts_file, fetch_geojson
from georep.sources.overpass import fetch_streets_per_precinct
from georep.sources.pdfs import PdfStore
from georep.sources.wiki import fetch_geosearch_pois, fetch_sparql_pois, sparql_query
from georep.stores import PaperStore, TextStore

Status = Literal["ausgeführt", "übersprungen", "geplant"]
PARTIES_SCHEMA = 1  # Option 04: Schema-Version der drei Ausgaben des Schritts ``parties``


def _class_shares(figures: dict[str, int], total: int) -> list[tuple[str, float]]:
    """Die Urheberklassen mit Anteil, stärkste zuerst; leere Klassen bleiben draußen."""
    found = [(art, count / total) for art, count in figures.items() if count and total]
    return sorted(found, key=lambda pair: pair[1], reverse=True)


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


# Option 01: die Eingaben plus das Straßenverzeichnis, wo das Profil eines kennt.
def with_directory(layout: Layout, *inputs: Path) -> tuple[Path, ...]:
    directory = layout.streets_directory
    return (*inputs, *(() if directory is None else (directory,)))


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
    context = settings.context
    # Option 03: ohne context_root im Layout (settings ``context.root = ""``) gibt es die drei
    # Schritte nicht; die Dateinamen und alles Inhaltliche stehen in den Settings.
    with_context = layout.context_root is not None
    session: Transport | None = http
    # Option 02: ein Periodenprofil darf das Wörterbuch der Hauptperiode benutzen; dann liest es
    # deren Rohdaten (Straßen, Orte) und holt selbst nichts aus dem Netz.
    own_dictionary = settings.period.dictionary == "own"
    dictionary_source = layout if own_dictionary else layout.for_profile("")

    def transport() -> Transport:
        nonlocal session
        if session is None:
            session = cached_session(settings, layout.http_cache)
        return session

    def opendata() -> str:
        portal = settings.sources.opendata
        csv = fetch_csv(transport(), portal.results_url, sep=columns.sep)
        write_bytes(layout.results_csv, csv)
        # Option 01: byteweise, wie die Quelle liefert — ein Shapefile-Zip überlebt kein
        # Umschreiben; was daraus wird, entscheidet der Schritt ``shapes``.
        flaechen = fetch_districts_file(
            transport(), portal.districts_url, fmt=settings.precincts.format
        )
        write_bytes(layout.districts_geojson, flaechen)
        done = f"{len(csv)} Bytes Wahlergebnis, {len(flaechen)} Bytes Flächen"
        # --- Option 01: zwei Dateien, die nur manche Städte veröffentlichen
        for url, target, what in (
            (portal.streets_url, layout.streets_directory, "Straßenverzeichnis"),
            (portal.district_names_url, layout.district_names_csv, "Wahlbezirksnamen"),
        ):
            if url and target is not None:
                write_bytes(target, fetch_csv(transport(), url, sep=columns.sep))
                done += f", {what}"
        # --- Option 02: ein Periodenprofil braucht zusätzlich den Zuschnitt seiner Wahlbezirke
        # und ihr Ergebnis (dort stehen die Briefwähler, die kein Stimmbezirk ausweist)
        if portal.district_shapes_url:
            shapes = fetch_geojson(transport(), portal.district_shapes_url)
            write_json(layout.district_shapes_geojson, shapes, indent=None)
            done += f", {len(shapes['features'])} Wahlbezirke"
        if portal.district_results_url:
            per_district = fetch_csv(transport(), portal.district_results_url, sep=columns.sep)
            write_bytes(layout.district_results_csv, per_district)
            done += f", {len(per_district)} Bytes Wahlbezirksergebnis"
        return done

    # --- Option 03: die Fremddaten je Raumeinheit frisch vom Portal (``bootstrap`` nimmt die
    # Kopie im Repo, die beim Bauen ohne Netz reicht)
    def context_data() -> str:
        files = context.files
        table = fetch_csv(transport(), files.table.url, sep=context.table.sep)
        write_bytes(layout.external / files.table.file, table)
        units = fetch_geojson(transport(), files.units.url)
        write_json(layout.external / files.units.file, units, indent=None)
        indicators = fetch_csv(transport(), files.indicators.url, sep=context.table.sep)
        write_bytes(layout.external / files.indicators.file, indicators)
        return (
            f"{len(table)} Bytes Tabelle, {len(units['features'])} {context.units.label}, "
            f"{len(indicators)} Bytes Erläuterungen"
        )

    # --- Option 01: aus der Quellgeometrie die kanonischen Stimmbezirke; alles, was danach
    # Flächen liest, kennt nur noch diese Datei
    def shapes() -> str:
        rules = settings.precincts
        source = read_source(layout.districts_geojson, rules)
        names = (
            district_names_from_csv(layout.district_names_csv, rules, columns)
            if rules.names_from_results and layout.district_names_csv is not None
            else None
        )
        canonical = canonical_precincts(source, rules, names)
        write_json(layout.precincts_geojson, canonical, indent=None)
        districts = {f["properties"]["wahlbezirk"] for f in canonical["features"]}
        return (
            f"{len(canonical['features'])} Stimmbezirke in {len(districts)} Wahlbezirken, "
            f"CRS {source.crs}"
        )

    def papers() -> str:
        store = PaperStore(layout.papers)
        known = store.load()
        since: dt.datetime | None = None
        if known and oparl.incremental:
            newest = max((r.modified for r in known.values() if r.modified), default=None)
            if newest is not None:
                since = newest - dt.timedelta(days=1)
        # --- Option 02: seitenweise speichern und wiederaufnehmen. Der Abruf einer alten Periode
        # dauert Stunden; bricht er ab, darf der nächste Lauf nicht bei first_page beginnen.
        resume = read_progress(layout.papers_progress)
        pages_done = 0

        def page_done(kept: list[PaperRecord], next_url: str | None) -> None:
            nonlocal pages_done
            pages_done += 1
            store.upsert(kept)
            write_progress(layout.papers_progress, next_url, pages_done)

        records, fetched = fetch_papers(
            transport(),
            oparl.endpoint,
            settings.period,
            delay_s=oparl.delay_s,
            modified_since=since,
            stop_when_older=oparl.stop_when_older,
            max_pages=oparl.max_pages or None,  # Option 04: 0 = alle Seiten
            first_page=oparl.first_page,
            resume_from=resume,
            on_page=page_done,
            sleep=sleep,
        )
        # Option 07: Gelöschte liefert der Server nur zu modified_since; sie fliegen aus dem Store.
        report = store.upsert(records, deleted=fetched.deleted_ids)
        # Der Fortschritt existiert nur, solange ein Abruf unvollständig ist.
        layout.papers_progress.unlink(missing_ok=True)
        mode = f"seit {since.date()}" if since else "vollständig"
        resumed = " (fortgesetzt)" if resume else ""
        return f"{mode}{resumed}: {fetched.summary()}; Store {report.summary()}"

    def pdfs() -> str:
        records = PaperStore(layout.papers).load().values()
        report = PdfStore(layout.pdf_dir).download(
            transport(), records, delay_s=oparl.delay_s, limit=oparl.pdf_limit or None, sleep=sleep
        )
        return report.summary()

    def streets_osm() -> str:
        found = read_canonical_precincts(layout.precincts_geojson, settings.geo.working_crs)
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
        found = read_canonical_precincts(layout.precincts_geojson, settings.geo.working_crs)
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
        raw = read_results_csv(layout.results_csv, columns)
        frame = aggregate_voters(raw, columns)
        write_parquet(frame, layout.voters, schema_version=1)
        # --- Option 05: die Zuordnung zu den Stadtbezirken steht in derselben CSV
        units = district_units(raw, columns)
        write_parquet(units, layout.district_units, schema_version=1)
        return f"{frame.height} Wahlbezirke, {units.height} Paare mit Stadtbezirk"

    # --- Option 03: Raumeinheiten auf Wahlbezirke umrechnen und die Variablen mitteln
    def context_step() -> str:
        working = settings.geo.working_crs
        precincts = read_precincts(layout.districts_geojson, settings.columns, working)
        table = precinct_table(precincts, read_results_csv(layout.results_csv, columns), columns)
        units = read_areas(layout.external / context.files.units.file, context.units.key, working)
        shares = area_shares(
            [Area.of(p) for p in precincts], units, min_coverage=context.min_coverage
        )
        weights = district_weights(table, shares)
        values = read_context_table(layout.external / context.files.table.file, context)
        joined = aggregate_context(weights, values, context).join(
            district_variables(pl.read_parquet(layout.voters), context), on="wahlkreis_id"
        )
        # Erst alle Variablen in der Reihenfolge der Settings, dann die Fehlgewichte: so liest sich
        # die Tabelle, und die Spaltendoku entsteht aus derselben Liste (report.tables).
        frame = joined.select(
            "wahlkreis_id",
            *(v.name for v in context.variables),
            *(f"{v.name}{MISSING_SUFFIX}" for v in context.unit_variables()),
        )
        write_parquet(frame, layout.context_table, schema_version=1)
        named = weights.join(values.select("einheit", "einheit_name"), on="einheit", how="left")
        write_parquet(
            named.select("wahlkreis_id", "einheit", "einheit_name", "gewicht"),
            layout.crosswalk,
            schema_version=1,
        )
        return (
            f"{frame.height} Wahlbezirke, {len(units)} {context.units.label}, "
            f"{len(context.variables)} Variablen"
        )

    # --- Option 02: Zuordnung der Stimmbezirke eines alten Zuschnitts auf die Wahlbezirke heute
    def precincts() -> str:
        cross = settings.crosswalk
        working = settings.geo.working_crs
        sources = read_areas(layout.districts_geojson, cross.precinct_id, working)
        old = read_areas(layout.district_shapes_geojson, cross.district_id, working)
        names = read_area_names(
            layout.district_shapes_geojson, cross.district_id, cross.district_name
        )
        targets = [
            Area(str(district), shape)
            for district, shape in district_shapes(
                read_precincts(
                    layout.target_view(settings).districts_geojson, settings.columns, working
                ),
                tolerance_m=0.0,
            ).items()
        ]
        home = assign_by_point(sources, old)
        shares = area_shares(sources, targets, min_coverage=cross.min_coverage)
        frame = (
            shares.rename({SOURCE: PRECINCT, SHARE: "anteil", COVERAGE: "abdeckung"})
            # Die Schlüssel des Crosswalks sind Text; die Wahlbezirke sind im ganzen Projekt
            # Int64, und die Reste beim Runden sollen an die numerisch sortierten Bezirke gehen.
            .with_columns(pl.col(TARGET).cast(pl.Int64).alias(DISTRICT))
            .with_columns(
                pl.col(PRECINCT).replace_strict(home, return_dtype=pl.String).alias("_quelle")
            )
            .with_columns(
                pl.col("_quelle").cast(pl.Int64).alias(SOURCE_DISTRICT),
                pl.col("_quelle")
                .replace_strict(names, return_dtype=pl.String)
                .alias("wahlbezirk_quelle_name"),
            )
            .select(
                PRECINCT,
                SOURCE_DISTRICT,
                "wahlbezirk_quelle_name",
                DISTRICT,
                "anteil",
                "abdeckung",
            )
            .sort([PRECINCT, DISTRICT])
        )
        write_parquet(frame, layout.precinct_assignment, schema_version=1)
        split = frame.group_by(PRECINCT).len().filter(pl.col("len") > 1).height
        least = frame.get_column("abdeckung").to_list()
        return (
            f"{len(sources)} Stimmbezirke auf {frame.get_column(DISTRICT).n_unique()} Wahlbezirke, "
            f"{frame.height} Paare, {split} geteilt, Abdeckung ab {min(least):.4f}"
        )

    # --- Option 02: Wähler des alten Zuschnitts über die Zuordnung auf die Wahlbezirke heute
    def voters_transferred() -> str:
        assignment = pl.read_parquet(layout.precinct_assignment)
        found = precinct_counts(read_results_csv(layout.results_csv, columns), columns)
        per_district = district_results(
            read_results_csv(layout.district_results_csv, columns), columns
        )
        counts = count_columns(columns)
        complete = spread_postal(
            found.urn,
            dict(
                zip(
                    assignment.get_column(PRECINCT).to_list(),
                    assignment.get_column(SOURCE_DISTRICT).to_list(),
                    strict=True,
                )
            ),
            per_district,
            counts,
        )
        postal = check_postal_total(
            found.postal,
            VOTERS,
            int(per_district.get_column(VOTERS).sum()) - int(found.urn.get_column(VOTERS).sum()),
        )
        moved = transfer_counts(
            complete.rename({PRECINCT: SOURCE}),
            assignment.select(
                pl.col(PRECINCT).alias(SOURCE),
                pl.col(DISTRICT).alias(TARGET),
                pl.col("anteil").alias(SHARE),
            ),
            counts,
        )
        frame = with_shares(moved.rename({TARGET: DISTRICT}), columns.parties)
        write_parquet(frame, layout.voters, schema_version=1)
        # Option 05 rechnet auf dem Zielzuschnitt: die Zuordnung Wahlbezirk zu Stadtbezirk gilt
        # für beide Perioden und kommt darum aus der Hauptperiode, nicht aus der alten CSV (die
        # Ratswahl 2020 nennt keinen Stadtbezirk).
        write_parquet(
            pl.read_parquet(layout.target_view(settings).district_units),
            layout.district_units,
            schema_version=1,
        )
        return (
            f"{frame.height} Wahlbezirke aus {complete.height} Stimmbezirken, "
            f"{postal} Briefwähler verteilt, "
            f"{int(frame.get_column(ELIGIBLE_TOTAL).sum())} Wahlberechtigte"
        )

    def streets() -> str:
        frame = streets_by_district(read_streets_json(dictionary_source.streets))
        write_parquet(frame, layout.streets_by_district, schema_version=1)
        line = (
            f"{frame.height} Wahlbezirke, "
            f"{frame.get_column('suchbegriffe').list.len().sum()} Straßennamen"
        )
        # Option 01: wo die Stadt ein Straßenverzeichnis veröffentlicht, misst der Schritt, wie
        # gut die Flächen zum Zuschnitt der Wahl passen; die Seite nennt die Zahl.
        directory = layout.streets_directory
        if directory is not None and directory.is_file():
            agreement = directory_agreement(layout.streets, directory, columns, settings.precincts)
            line += f"; Verzeichnis: {agreement.line()}"
        return line

    def pois() -> str:
        clean = clean_pois(read_pois_json(dictionary_source.pois), settings.search.exclude)
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
        frame = join_voters(hits, pl.read_parquet(layout.voters), ELIGIBLE_TOTAL)
        write_parquet(frame, layout.results, schema_version=1)
        return (
            f"{frame.height} Wahlbezirke, {int(frame.get_column('anzahl_treffer').sum())} Treffer"
        )

    # --- Option 05: Gremium je Dokument aus der Drucksachennummer, dann die Kennzahlen
    def bodies() -> str:
        corpus = pl.read_parquet(layout.corpus, columns=["id", "reference"])
        frame = classify_papers(corpus, BodyRules.from_settings(settings.bodies))
        write_parquet(frame, layout.papers_bodies, schema_version=BODIES_SCHEMA_VERSION)
        return papers_bodies_summary(frame)

    # --- Option 05
    def body_hits() -> str:
        results_frame = pl.read_parquet(layout.results)
        papers_frame = pl.read_parquet(layout.papers_bodies)
        units = pl.read_parquet(layout.district_units)
        districts = hits_by_body(results_frame, papers_frame, units, ELIGIBLE_TOTAL)
        bodies_frame = documents_by_body(papers_frame, results_frame, units)
        write_parquet(districts, layout.district_bodies, schema_version=1)
        write_parquet(bodies_frame, layout.bodies_table, schema_version=1)
        return bodies_summary(districts, bodies_frame)

    # --- Option 06: Themen je Dokument (docs/plans/06-gewichtung.md)
    def topics() -> str:
        # Erst hier importieren, nicht oben: sklearn kostet rund 0,4 s Importzeit, und nur wer
        # rechnet, soll sie zahlen (``georep status`` lädt build_steps).
        from georep.analysis.topics import dominant_topics, fit_topics

        model = fit_topics(pl.read_parquet(layout.corpus, columns=["id", "text"]), settings.topics)
        write_parquet(model.topics, layout.topics, schema_version=1)
        write_parquet(dominant_topics(model.shares), layout.topic_documents, schema_version=1)
        write_parquet(model.shares, layout.topic_shares, schema_version=1)
        words = int(model.topics.get_column("woerter").list.len().sum())
        return (
            f"{model.topics.height} Themen, {model.shares.height} Dokumente, "
            f"{words} Wörter in den Beschriftungen"
        )

    # --- Option 06: Gewichtete Trefferquoten
    def weights() -> str:
        from georep.analysis.weights import TypeRules, term_weights, variants

        with_text = int(
            pl.scan_parquet(layout.corpus).select((pl.col("text") != "").sum()).collect().item()
        )
        dictionary_frame = pl.read_parquet(layout.dictionary)
        index_frame = pl.read_parquet(layout.index)
        frame = variants(
            dictionary_frame,
            index_frame,
            pl.read_parquet(layout.corpus, columns=["id", "paper_type"]),
            pl.read_parquet(layout.voters),
            ELIGIBLE_TOTAL,
            with_text,
            [
                TypeRules(
                    rule_set.name,
                    rule_set.default,
                    tuple((rule.pattern, rule.weight) for rule in rule_set.rules),
                )
                for rule_set in settings.weights.paper_type
            ],
            settings.weights.combined,
            pl.read_parquet(layout.topic_shares) if settings.topics.k > 0 else None,
        )
        write_parquet(frame, layout.weighted, schema_version=1)
        write_parquet(
            term_weights(dictionary_frame, index_frame, with_text),
            layout.term_weights,
            schema_version=1,
        )
        unit = frame.filter(pl.col("variante") == "einheit").get_column("anzahl_treffer_gewichtet")
        return (
            f"{frame.get_column('variante').n_unique()} Varianten, "
            f"{frame.get_column('wahlkreis_id').n_unique()} Wahlbezirke, "
            f"Einheit = {int(unit.sum())} Treffer"
        )

    # --- Option 03: die Modelle von Tabelle 6 über die Kontrollvariablen
    def controls() -> str:
        frame = model_frame(pl.read_parquet(layout.results), pl.read_parquet(layout.context_table))
        table = models_table(frame, settings)
        write_parquet(table, layout.controls, schema_version=1)
        samples = 2 if settings.analysis.exclude_districts else 1
        fitted = table.select("modell", "stichprobe").unique().height
        return (
            f"{fitted} von {len(model_terms(context)) * samples} Modellen geschätzt "
            f"(n = {frame.height})"
        )

    # --- Option 04: Urheber und Parteien
    def organizations() -> str:
        found, pages = fetch_organizations(
            transport(),
            oparl.organizations_endpoint,
            delay_s=oparl.delay_s,
            sleep=sleep,
        )
        write_json(
            layout.organizations,
            [o.model_dump(mode="json", by_alias=True, exclude_none=True) for o in found],
            indent=None,
        )
        fractions = sum(1 for o in found if o.classification == "Fraktion")
        return f"{len(found)} Organisationen auf {pages} Seite(n), {fractions} Fraktionen"

    # --- Option 04
    def parties() -> str:
        corpus_frame = pl.read_parquet(
            layout.corpus,
            columns=["id", "paper_type", "name", "text", "originator_organization"],
        )
        found = read_organizations(layout.organizations)
        attribution = classify_originators(corpus_frame, settings.originators, found)
        write_parquet(attribution, layout.document_originators, schema_version=PARTIES_SCHEMA)
        results_frame = pl.read_parquet(layout.results)
        write_parquet(
            originators_by_district(results_frame, attribution),
            layout.district_originators,
            schema_version=PARTIES_SCHEMA,
        )
        party_frame = party_hits(
            results_frame,
            attribution,
            pl.read_parquet(layout.voters),
            settings.originators.parties,
            ELIGIBLE_TOTAL,
        )
        write_parquet(party_frame, layout.party_results, schema_version=PARTIES_SCHEMA)
        figures = originator_figures(attribution)
        shares = ", ".join(
            f"{share:.0%} {art}" for art, share in _class_shares(figures, attribution.height)
        )
        return (
            f"{attribution.height} Dokumente: {shares}; "
            f"{party_frame.height} Kennzahlen je Partei und Bezirk"
            + (f"; {len(found)} Organisationen" if found else "")
        )

    # --- Option 02: beide Perioden nebeneinander; nur mit compare.period
    def compare() -> str:
        other = layout.for_profile(settings.compare.period)
        if digest(layout.dictionary) != digest(other.dictionary):
            raise SchemaError(
                "Vergleich setzt dasselbe Wörterbuch voraus: "
                f"{layout.dictionary} und {other.dictionary} unterscheiden sich. "
                'Das Profil der älteren Periode braucht period.dictionary = "base".'
            )
        frame = compare_periods(
            pl.read_parquet(layout.results),
            pl.read_parquet(other.results),
            labels=(settings.compare.label or settings.compare.period, settings.period.title),
        )
        write_parquet(frame, layout.comparison, schema_version=1)
        fit = delta_regression(frame)
        return f"{frame.height} Wahlbezirke in beiden Perioden; Differenzen {fit.summary()}"

    def report() -> str:
        return build_site(
            layout, settings, now=dt.datetime.now(dt.UTC), commit=current_commit()
        ).line()

    # --- Option 02: ein Periodenprofil holt zusätzlich den Zuschnitt seiner Wahlbezirke
    opendata_outputs = [layout.results_csv, layout.districts_geojson]
    if settings.sources.opendata.district_shapes_url:
        opendata_outputs.append(layout.district_shapes_geojson)
    if settings.sources.opendata.district_results_url:
        opendata_outputs.append(layout.district_results_csv)
    # --- Option 01: zwei Dateien, die nur manche Städte veröffentlichen
    if settings.sources.opendata.streets_url and layout.streets_directory is not None:
        opendata_outputs.append(layout.streets_directory)
    if settings.sources.opendata.district_names_url and layout.district_names_csv is not None:
        opendata_outputs.append(layout.district_names_csv)
    # Option 01: ohne eigene Wahlbezirke in der Quellgeometrie (ein Periodenprofil mit Crosswalk)
    # gibt es die kanonischen Stimmbezirke nicht; dann fehlt der Schritt und die Kette liest die
    # Datei der Hauptperiode (``target_view``).
    with_shapes = settings.precincts.enabled
    names_input = (
        (layout.district_names_csv,)
        if settings.precincts.names_from_results and layout.district_names_csv is not None
        else ()
    )
    # Option 06: ohne Themenmodell (``topics.k = 0``) fehlt der Schritt und niemand nennt seine
    # Ausgaben als Eingabe; die zwei Tabellen der Themen sind im Register ``optional``.
    with_topics = settings.topics.k > 0
    # Option 01: die Urheber (Option 04) brauchen die Fraktionsnamen der Stadt
    with_parties = bool(settings.originators.parties)
    topic_outputs = (layout.topics, layout.topic_documents, layout.topic_shares)
    context_files = tuple(layout.external / name for name in context.files.names())
    return [
        Step("opendata", (), tuple(opendata_outputs), opendata, network=True),
        # --- Option 01: aus der Quellgeometrie der kanonische Stand der Stimmbezirke
        *(
            [
                Step(
                    "shapes",
                    (layout.districts_geojson, *names_input),
                    (layout.precincts_geojson,),
                    shapes,
                )
            ]
            if with_shapes
            else []
        ),
        # --- Option 03
        *(
            [Step("context_data", (), context_files, context_data, network=True)]
            if with_context
            else []
        ),
        Step("papers", (), (layout.papers,), papers, network=True),
        # --- Option 04: eine Seite, rund eine halbe Sekunde; liefert die Abbildung URL zu Partei
        Step("organizations", (), (layout.organizations,), organizations, network=True),
        Step("pdfs", (layout.papers,), (layout.pdf_manifest,), pdfs, network=True),
        # --- Option 02: mit dem Wörterbuch der Hauptperiode gibt es die beiden Netzschritte nicht
        *(
            [
                # Option 01: beide lesen den kanonischen Stand, nicht die Quelldatei
                Step(
                    "streets_osm",
                    (layout.precincts_geojson,),
                    (layout.streets,),
                    streets_osm,
                    network=True,
                ),
                Step(
                    "pois_wiki",
                    (layout.precincts_geojson,),
                    (layout.pois,),
                    pois_wiki,
                    network=True,
                ),
            ]
            if own_dictionary
            else []
        ),
        Step("texts", (layout.papers, layout.pdf_manifest), (layout.texts,), texts),
        # --- Option 02: der Crosswalk braucht beide Zuschnitte, dann rechnet voters über ihn
        *(
            [
                Step(
                    "precincts",
                    (
                        layout.districts_geojson,
                        layout.district_shapes_geojson,
                        layout.target_view(settings).districts_geojson,
                    ),
                    (layout.precinct_assignment,),
                    precincts,
                ),
                Step(
                    "voters",
                    (
                        layout.results_csv,
                        layout.district_results_csv,
                        layout.precinct_assignment,
                        layout.target_view(settings).district_units,
                    ),
                    (layout.voters, layout.district_units),
                    voters_transferred,
                ),
            ]
            if settings.crosswalk.enabled
            else [
                Step(
                    "voters",
                    (layout.results_csv,),
                    (layout.voters, layout.district_units),  # Option 05: zweite Ausgabe
                    voters,
                )
            ]
        ),
        # --- Option 03
        *(
            [
                Step(
                    "context",
                    (
                        layout.districts_geojson,
                        layout.results_csv,
                        layout.external / context.files.units.file,
                        layout.external / context.files.table.file,
                        layout.voters,
                    ),
                    (layout.context_table, layout.crosswalk),
                    context_step,
                )
            ]
            if with_context
            else []
        ),
        # Option 01: ``streets`` misst zusätzlich gegen das Straßenverzeichnis, wo es eines gibt
        Step(
            "streets",
            with_directory(layout, dictionary_source.streets),
            (layout.streets_by_district,),
            streets,
        ),
        Step(
            "pois",
            (dictionary_source.pois,),
            (layout.pois_table, layout.pois_by_district),
            pois,
        ),
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
        # --- Option 06
        *([Step("topics", (layout.corpus,), topic_outputs, topics)] if with_topics else []),
        Step("index", (layout.dictionary, layout.corpus), (layout.index,), index),
        Step(
            "results", (layout.dictionary, layout.index, layout.voters), (layout.results,), results
        ),
        # --- Option 05
        Step(
            "bodies",
            (layout.corpus,),
            (layout.papers_bodies,),
            bodies,
            BODIES_SCHEMA_VERSION,
        ),
        # --- Option 05
        Step(
            "body_hits",
            (layout.results, layout.papers_bodies, layout.district_units),
            (layout.district_bodies, layout.bodies_table),
            body_hits,
        ),
        # --- Option 06
        Step(
            "weights",
            (layout.dictionary, layout.index, layout.corpus, layout.voters)
            + ((layout.topic_shares,) if with_topics else ()),
            (layout.weighted, layout.term_weights),
            weights,
        ),
        # --- Option 03
        *(
            [
                Step(
                    "controls",
                    (layout.results, layout.context_table),
                    (layout.controls,),
                    controls,
                )
            ]
            if with_context
            else []
        ),
        # --- Option 04: nach results, weil es dessen paper_ids schneidet; organizations.json ist
        # eine Eingabe nur, wenn der Netzschritt lief (dann wandert ihr Hash in den Stamp).
        # Option 01: ohne Fraktionsnamen im Profil gibt es keine Urheber zu erkennen.
        *(
            [
                Step(
                    "parties",
                    (
                        layout.corpus,
                        layout.results,
                        layout.voters,
                        *((layout.organizations,) if layout.organizations.exists() else ()),
                    ),
                    (
                        layout.document_originators,
                        layout.district_originators,
                        layout.party_results,
                    ),
                    parties,
                    PARTIES_SCHEMA,
                )
            ]
            if with_parties
            else []
        ),
        # --- Option 02: der Vergleich steht vor dem Bericht und wird seine letzte Eingabe
        *(
            [
                Step(
                    "compare",
                    (
                        layout.results,
                        layout.for_profile(settings.compare.period).results,
                        layout.dictionary,
                        layout.for_profile(settings.compare.period).dictionary,
                    ),
                    (layout.comparison,),
                    compare,
                )
            ]
            if settings.compare.period
            else []
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
                # Option 02: der gerechnete Zuschnitt, bei einem Crosswalk-Profil der der
                # Hauptperiode (dort liegen Flächen und Namen der Wahlbezirke); Option 01: als
                # kanonischer Stand aus dem Schritt ``shapes``
                layout.target_view(settings).precincts_geojson,
                # Option 01: die Seite nennt die Übereinstimmung mit dem Straßenverzeichnis
                *((layout.streets_directory,) if layout.streets_directory is not None else ()),
                # Option 05
                layout.district_bodies,
                layout.bodies_table,
                layout.district_units,
                # Option 06
                layout.weighted,
                layout.term_weights,
                # Option 03: die drei Tabellen und die Definitionen der Indikatoren
                *(
                    (
                        layout.context_table,
                        layout.crosswalk,
                        layout.controls,
                        layout.external / context.files.indicators.file,
                    )
                    if with_context
                    else ()
                ),
                # Option 04; Option 01: nur, wo das Profil Fraktionsnamen mitbringt
                *(
                    (
                        layout.document_originators,
                        layout.district_originators,
                        layout.party_results,
                    )
                    if with_parties
                    else ()
                ),
            )
            + ((layout.topics, layout.topic_documents) if with_topics else ())
            # --- Option 02: der Vergleich und die Zuordnung der älteren Periode
            + (
                (
                    layout.comparison,
                    layout.for_profile(settings.compare.period).precinct_assignment,
                )
                if settings.compare.period
                else ()
            ),
            (layout.site_index, layout.site_data / SCHEMA_NAME, layout.site / MAP_NAME),
            report,
        ),
    ]
