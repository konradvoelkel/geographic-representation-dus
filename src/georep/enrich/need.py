"""Beitrag von Vorhaben 22: Bedarf und Aufmerksamkeit je Wahlbezirk.

Zwei Schritte hinter dem Kern (``docs/plans/22-bedarf.md``, § 6 und § 10):

* ``need_data`` (Netz, nur mit dem Schalter ``context.need.fetch``) holt die Archive der Bedarfsquellen aus ``[context.need]`` nach
  ``cache_root/bedarf/`` und schneidet die Gemeinde heraus: Unfälle, Zellen des Zensus-Gitters mit
  Mittelpunkt in einem Stimmbezirk, Schulen mit Sozialindex, dazu ``quellen.json`` mit URL, Größe,
  SHA-256 und Abrufdatum je Archiv. Alles unter ``external/bedarf/``; ohne Netz legt ``bootstrap``
  dieselben Dateien aus dem Paket dorthin (``georep pack --need``).
* ``need`` (offline) rechnet je Wahlbezirk Bedarf und Aufmerksamkeit
  (``processed/wahlbezirke_bedarf.parquet``) und, wo das Profil Hypothesen oder Paare nennt, ihre
  Tests (``processed/bedarf_hypothesen.parquet``).

Ein Archiv, das jünger ist als ``cache.opendata_s``, wird nicht noch einmal geladen: die Archive
fallen unter keine Cache-Regel der Session (``docs/architecture.md``, „Netz"), und dieselbe Datei
für Düsseldorf und Mönchengladbach zweimal zu holen, wären 105 MB umsonst. Die Pfade gehören diesem
Modul (Synergien 2026-11, § 2.1): wer die Tabellen liest, nimmt sie aus ``need_files``.
"""

from __future__ import annotations

import datetime as dt
import math
import time
from pathlib import Path
from typing import NamedTuple

import numpy as np
import polars as pl
import shapely

from georep.analysis.need import MAIN, STRATUM, hypothesis_table, neighbours
from georep.crosswalk import DISTRICT, POINT, POINT_SHARE, point_shares
from georep.enrich import Contribution
from georep.geo import Precinct, read_canonical_precincts, transformer
from georep.http import Transport
from georep.io import digest, write_bytes, write_json, write_parquet
from georep.layout import Layout
from georep.pipeline import Step
from georep.prep.context import (
    ACCIDENTS_FILE,
    GRID_FILE,
    NEED_DATA_SCHEMA_VERSION,
    NEED_DIR,
    NEED_SCHEMA_VERSION,
    SCHOOLS_FILE,
    SOURCES_FILE,
    accidents_by_district,
    attention_by_district,
    grid_by_district,
    in_period,
    need_table,
    read_accidents,
    read_grid,
    read_schools,
    schools_by_district,
)
from georep.report.need import PAGE_NAME, need_data, need_enabled, need_inputs, need_links
from georep.report.pages import Page
from georep.report.tables import PublishedTable
from georep.settings import NeedSettings, Settings, archive_name
from georep.sources.opendata import fetch_csv, fetch_zip


class NeedFiles(NamedTuple):
    archives: Path  # die Archive der Quellen, von allen Profilen geteilt
    accidents: Path
    grid: Path
    schools: Path
    sources: Path
    table: Path
    tests: Path


def need_files(layout: Layout) -> NeedFiles:
    """Archive unter ``cache_root/bedarf/``, Stadtauszüge unter ``external/bedarf/``, Tabellen unter ``processed/``."""
    extracts = layout.external / NEED_DIR
    return NeedFiles(
        archives=layout.cache_root / NEED_DIR,
        accidents=extracts / ACCIDENTS_FILE,
        grid=extracts / GRID_FILE,
        schools=extracts / SCHOOLS_FILE,
        sources=extracts / SOURCES_FILE,
        table=layout.processed / "wahlbezirke_bedarf.parquet",
        tests=layout.processed / "bedarf_hypothesen.parquet",
    )


def _fresh(target: Path, *, max_age_s: int, now: float) -> bool:
    """Liegt das Archiv da und ist jünger als ``max_age_s``? Dann wird es nicht geladen."""
    return target.is_file() and now - target.stat().st_mtime < max_age_s


def _fetch_archive(http: Transport, url: str, target: Path) -> Path:
    """Ein Archiv laden, prüfen (Zip oder CSV) und atomar unter ``target`` ablegen."""
    content = fetch_zip(http, url) if target.suffix.lower() == ".zip" else fetch_csv(http, url)
    write_bytes(target, content)
    return target


def _described(path: Path, url: str) -> dict[str, object]:
    fetched = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.UTC).date()
    return {
        "url": url,
        "datei": path.name,
        "bytes": path.stat().st_size,
        "sha256": digest(path),
        "abgerufen": fetched.isoformat(),
    }


def _with_points(frame: pl.DataFrame, source_crs: str, working_crs: str) -> pl.DataFrame:
    """``punkt`` (Zeilennummer) und ``x``, ``y`` im Arbeits-CRS, für ``point_shares``."""
    xs = frame.get_column("x").cast(pl.Float64).to_numpy()
    ys = frame.get_column("y").cast(pl.Float64).to_numpy()
    if source_crs != working_crs:
        xs, ys = transformer(source_crs, working_crs).transform(xs, ys)
    return frame.with_row_index(POINT).with_columns(
        pl.col(POINT).cast(pl.Int64),
        pl.Series("x", np.asarray(xs, dtype=np.float64)),
        pl.Series("y", np.asarray(ys, dtype=np.float64)),
    )


def _grid_box(
    precincts: list[Precinct], working_crs: str, grid_crs: str, margin: float
) -> tuple[int, int, int, int]:
    """Das Rechteck um die Stadt im CRS des Gitters, mit Rand, auf ganze Meter."""
    minx, miny, maxx, maxy = shapely.union_all([p.geometry for p in precincts]).bounds
    xs, ys = transformer(working_crs, grid_crs).transform(
        [minx, maxx, minx, maxx], [miny, miny, maxy, maxy]
    )
    return (
        math.floor(min(xs) - margin),
        math.floor(min(ys) - margin),
        math.ceil(max(xs) + margin),
        math.ceil(max(ys) + margin),
    )


# Spalten von wahlbezirke_bedarf, die nur mit Klassen des passenden Ausschusses Werte tragen.
CLASS_COLUMNS = frozenset(
    {"dok_mit_text", "dok_verkehr", "dok_jugend", "anteil_verkehr", "anteil_jugend",
     "dok_verkehr_je_1000_ew"}
)  # fmt: skip


def _without_values(need: NeedSettings, unavailable: set[str]) -> list[str]:
    """Die Hypothesen und Paare, deren Spalten in diesem Lauf keine Werte tragen.

    Ein Profil mit Hypothesen über Variablen der Fremddaten (``hb_score``) oder über Anteile der
    Klassen kann ohne ``context.root`` oder ohne Klassifikator laufen (die Tests der Kette tun das).
    Dann bleiben ihre Zeilen in der Tabelle, mit ``p`` null, ohne Ergebnis und Deutung, und Holm
    rechnet weiter über alle vorab festgelegten (Review 2026-11-24, N2); die Zeile des Laufs nennt
    sie. Im Lauf eines Profils mit allem fehlt nichts.
    """
    names = [h.name for h in need.hypotheses if unavailable & {h.need, h.attention}]
    return names + [f"{a}~{b}" for a, b in need.explore if unavailable & {a, b}]


def need_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Die Schritte ``need_data`` (nur mit ``context.need.fetch``) und ``need``, wenn ``enabled``."""
    need = settings.context.need
    if not need.enabled:
        return []
    files = need_files(layout)
    working = settings.geo.working_crs
    ags = settings.city.ags
    with_classes = need.with_classes() and settings.classify.enabled
    with_context = layout.context_root is not None
    unavailable = set() if with_context else {v.name for v in settings.context.variables}
    unavailable |= set() if with_classes else set(CLASS_COLUMNS)
    skipped = _without_values(need, unavailable)
    with_tests = bool(need.hypotheses or need.explore)

    def precincts() -> list[Precinct]:
        return read_canonical_precincts(layout.precincts_geojson, working)

    def need_data() -> str:
        now = time.time()
        fetched = 0
        paths: dict[str, Path] = {}
        for url in need.archive_urls():
            target = files.archives / archive_name(url)
            if _fresh(target, max_age_s=settings.cache.opendata_s, now=now):
                paths[url] = target
                continue
            if fetched and need.delay_s:
                time.sleep(need.delay_s)  # eine Anfrage nach der anderen, mit Pause
            paths[url] = _fetch_archive(http, url, target)
            fetched += 1
        years = [read_accidents(paths[url], ags) for url in need.accidents.archives]
        accidents = pl.concat([year.frame for year in years]).sort("jahr", "monat", "x", "y")
        areas = precincts()
        grid = need.grid
        cells = read_grid(
            paths[grid.population_url],
            grid.population_member,
            paths[grid.rent_url],
            grid.rent_member,
            _grid_box(areas, working, grid.crs, grid.margin_m),
        )
        # Nur Zellen mit Mittelpunkt in einem Stimmbezirk: der Rest des Rechtecks gehört zu den
        # Nachbargemeinden und fällt im Schritt need ohnehin heraus.
        inside = (
            point_shares(_with_points(cells, grid.crs, working), areas).get_column(POINT).unique()
        )
        cells = (
            cells.with_row_index(POINT)
            .filter(pl.col(POINT).cast(pl.Int64).is_in(inside.to_list()))
            .drop(POINT)
        )
        located = read_schools(
            paths[need.schools.schools_url],
            paths[need.schools.index_url],
            ags,
            crs=need.schools.crs,
            index_encoding=need.schools.index_encoding,
        )
        schools = located.frame
        for frame, target in (
            (accidents, files.accidents),
            (cells, files.grid),
            (schools, files.schools),
        ):
            write_parquet(
                frame, layout.guard_writable(target), schema_version=NEED_DATA_SCHEMA_VERSION
            )
        write_json(
            layout.guard_writable(files.sources),
            {"ags": ags, "archive": [_described(paths[url], url) for url in need.archive_urls()]},
        )
        return (
            f"{len(paths)} Archive, {fetched} davon geladen; {accidents.height} Unfälle, "
            f"{cells.height} Gitterzellen, {schools.height} Schulen der Gemeinde {ags}; ohne "
            f"Koordinate verworfen: {sum(year.dropped for year in years)} Unfälle, "
            f"{located.dropped} Schulen"
        )

    def need_step() -> str:
        areas = precincts()
        districts = sorted({p.district_id for p in areas})
        unions = [
            shapely.union_all([p.geometry for p in areas if p.district_id == d]) for d in districts
        ]
        strata = (
            pl.read_parquet(layout.district_units)
            .sort(DISTRICT, "gewicht", STRATUM, descending=[False, True, False])
            .group_by(DISTRICT, maintain_order=True)
            .first()
            .select(DISTRICT, STRATUM)
        )
        # Nach dem Join sortieren: auch ein linker legt die Zeilenfolge nicht fest (CLAUDE.md).
        base = (
            pl.DataFrame(
                {DISTRICT: districts, "flaeche_km2": [u.area / 1e6 for u in unions]},
                schema={DISTRICT: pl.Int64, "flaeche_km2": pl.Float64},
            )
            .join(strata, on=DISTRICT, how="left")
            .sort(DISTRICT)
        )
        accidents = in_period(
            pl.read_parquet(files.accidents), settings.period.start, settings.period.end
        )
        points = _with_points(accidents, need.accidents.crs, working)
        fuzzy = point_shares(points, areas, band_m=need.band_m)
        sharp = point_shares(points, areas)
        cells = _with_points(pl.read_parquet(files.grid), need.grid.crs, working)
        schools = _with_points(pl.read_parquet(files.schools), need.schools.crs, working)
        results = pl.read_parquet(layout.results)
        committees = (
            pl.read_parquet(layout.papers_committee, columns=["id", "ausschuss"])
            if with_classes
            else None
        )
        table = need_table(
            base,
            accidents_by_district(points, fuzzy, sharp),
            grid_by_district(cells, point_shares(cells, areas)),
            schools_by_district(schools, point_shares(schools, areas), need.schools.forms),
            attention_by_district(
                results,
                committees,
                need.classes.traffic if with_classes else [],
                need.classes.youth if with_classes else [],
            ),
        )
        write_parquet(table, files.table, schema_version=NEED_SCHEMA_VERSION)
        outside = accidents.height - fuzzy.get_column(POINT).n_unique()
        shared = fuzzy.filter(pl.col(POINT_SHARE) < 1).get_column(POINT).n_unique()
        done = (
            f"{table.height} Wahlbezirke; {accidents.height} Unfälle im Zeitraum, {shared} im Band "
            f"von {need.band_m:g} m geteilt, {outside} ohne Wahlbezirk; "
            f"{float(table.get_column('einwohner_zensus').sum()):.0f} Einwohner"
        )
        if not with_tests:
            # Review 2026-11-24, N9: ohne Hypothesen und Paare ist die Tabelle keine Ausgabe; eine
            # alte aus einem früheren Lauf bliebe sonst ohne Stamp und veraltet liegen.
            if files.tests.exists():
                files.tests.unlink()
                return f"{done}; alte {files.tests.name} entfernt"
            return done
        frame = table.join(
            results.select(DISTRICT, "trefferquote", "wahlbeteiligung"), on=DISTRICT, how="left"
        ).with_columns(pl.col("begriffe").cast(pl.Float64).log().alias("log_begriffe"))
        if with_context:
            frame = frame.join(pl.read_parquet(layout.context_table), on=DISTRICT, how="left")
        # Was dieser Lauf nicht hat, steht als Spalte ohne Werte da: die Zeile bleibt, p ist null (N2).
        frame = frame.with_columns(
            pl.lit(None, dtype=pl.Float64).alias(name)
            for name in sorted(unavailable - set(frame.columns))
        )
        tests = hypothesis_table(
            frame.sort(DISTRICT),
            need,
            weights=neighbours(unions, need.neighbour_m),
        )
        write_parquet(tests, files.tests, schema_version=NEED_SCHEMA_VERSION)
        main = tests.filter(pl.col("rechnung") == MAIN)
        verdicts = ", ".join(
            f"{name} {result} ({reading})"
            for name, result, reading in main.select("hypothese", "ergebnis", "deutung").rows()
        )
        without = (
            f"; ohne Fremddaten oder Klassen nicht gerechnet: {', '.join(skipped)}"
            if skipped
            else ""
        )
        return f"{done}; {verdicts or 'keine Hypothese'}, {tests.height} Zeilen{without}"

    extracts = (files.accidents, files.grid, files.schools)
    inputs = (
        *extracts,
        files.sources,
        layout.precincts_geojson,
        layout.results,
        layout.district_units,
        *((layout.papers_committee,) if with_classes else ()),
        *((layout.context_table,) if with_context and with_tests else ()),
    )
    fetching = [
        Step(
            "need_data",
            (layout.precincts_geojson,),
            (*extracts, files.sources),
            need_data,
            NEED_DATA_SCHEMA_VERSION,
            network=True,
        )
    ]
    # Review 2026-11-24, N1: der Netzschritt nur mit seinem Schalter, wie die Ratsschritte.
    return [
        *(fetching if need.fetch else []),
        Step(
            "need",
            inputs,
            (files.table, *((files.tests,) if with_tests else ())),
            need_step,
            NEED_SCHEMA_VERSION,
        ),
    ]


# --- Stufe 3 (docs/plans/22-bedarf.md, § 7 mit § 10): Tabellen und Seite ------------------------
_DISTRICT = ("Nummer des Kommunalwahlbezirks", "")
_ACCIDENTS = "Unfälle mit Personenschaden der Monate der Periode"
TABLES = (
    PublishedTable(
        "wahlbezirke_bedarf",
        lambda layout: need_files(layout).table,
        "Bedarf und Aufmerksamkeit je Wahlbezirk: Unfälle, Einwohner, Miete, Schulsozialindex, "
        "Dokumente mit Treffer und Anteile der Klassen",
        {
            "wahlkreis_id": _DISTRICT,
            "stadtbezirk": (
                "Stadtbezirk mit den meisten Wahlberechtigten des Wahlbezirks (die Schicht der "
                "Rechnung innerhalb der Stadtbezirke)",
                "",
            ),
            "flaeche_km2": ("Fläche des Wahlbezirks aus den Stimmbezirken", "km²"),
            "einwohner_zensus": (
                "Einwohner des Zensus 2022 in den Gitterzellen mit Mittelpunkt im Wahlbezirk",
                "Personen",
            ),
            "unfaelle": (
                f"{_ACCIDENTS}; nahe einer Grenze zu gleichen Teilen an jeden Wahlbezirk im "
                "Randband (context.need.band_m)",
                "Unfälle",
            ),
            "unfaelle_schwer": ("davon mit Getöteten oder Schwerverletzten", "Unfälle"),
            "unfaelle_rad_fuss": (
                "davon mit Beteiligung eines Fahrrads oder zu Fuß Gehender",
                "Unfälle",
            ),
            "unfaelle_scharf": ("dieselben Unfälle scharf zugeordnet (Punkt in Fläche)", "Unfälle"),
            "unfaelle_geteilt": (
                "Anteile aus Unfällen, die auf mehrere Wahlbezirke gehen",
                "Unfälle",
            ),
            "unfaelle_je_1000": ("unfaelle je 1 000 Einwohner des Zensus", "je 1 000 Einwohner"),
            "unfaelle_scharf_je_1000": ("unfaelle_scharf je 1 000 Einwohner", "je 1 000 Einwohner"),
            "unfaelle_je_km2": ("unfaelle je km² Fläche", "je km²"),
            "miete_qm": (
                "durchschnittliche Nettokaltmiete des Zensus 2022, gewogen mit den Einwohnern der "
                "Zellen mit Wert",
                "Euro je m²",
            ),
            "miete_abdeckung": ("Anteil der Einwohner in Zellen mit Mietwert", "Anteil 0 bis 1"),
            "schulen": (
                "Schulen der Formen aus context.need.schools.forms im Wahlbezirk",
                "Schulen",
            ),
            "schulen_mit_index": ("davon mit Stufe im Schulsozialindex", "Schulen"),
            "sozialindex_schulen": (
                "Mittel der Stufen des Schulsozialindex dieser Schulen; leer ohne Schule mit Stufe",
                "Stufe 1 bis 9",
            ),
            "begriffe": ("Begriffe im Wörterbuch des Wahlbezirks", "Begriffe"),
            "dok": ("Dokumente mit mindestens einem Treffer im Wörterbuch", "Dokumente"),
            "dok_mit_text": (
                "davon die Dokumente, die eine Klasse tragen (also Text haben); leer ohne Klassifikator",
                "Dokumente",
            ),
            "dok_verkehr": (
                "davon in den Klassen context.need.classes.traffic (auf der Seite „Ordnung und "
                "Verkehr“); leer ohne Klassifikator",
                "Dokumente",
            ),
            "dok_jugend": (
                "davon in den Klassen context.need.classes.youth (Jugend und Schule); leer ohne "
                "Klassifikator",
                "Dokumente",
            ),
            "anteil_verkehr": ("dok_verkehr durch dok_mit_text", "Anteil 0 bis 1"),
            "anteil_jugend": ("dok_jugend durch dok_mit_text", "Anteil 0 bis 1"),
            "dok_je_1000_ew": ("dok je 1 000 Einwohner des Zensus", "je 1 000 Einwohner"),
            "dok_verkehr_je_1000_ew": (
                "dok_verkehr je 1 000 Einwohner; leer ohne Klassifikator",
                "je 1 000 Einwohner",
            ),
        },
        enabled=need_enabled,
    ),
    PublishedTable(
        "bedarf_hypothesen",
        lambda layout: need_files(layout).tests,
        "Die vorab festgelegten Tests von Bedarf gegen Aufmerksamkeit, Robustheit und die "
        "explorativen Rechnungen, je Zeile eine Rechnung",
        {
            "hypothese": (
                "Kennung der vorab festgelegten Hypothese, etwa H1; leer bei einem Paar",
                "",
            ),
            "p": ("p-Wert der Rechnung, unkorrigiert; leer bei der Robustheit", "Anteil 0 bis 1"),
            "p_holm": (
                "nach Holm über alle vorab festgelegten Tests, nur beim Haupttest",
                "Anteil 0 bis 1",
            ),
            "ergebnis": ("bestätigt oder nicht bestätigt, nur beim Haupttest", ""),
            "n": ("Wahlbezirke der Rechnung", ""),
            "festgelegt": (
                "Commit, in dem die Hypothese vor der ersten Rechnung festgelegt wurde",
                "",
            ),
            "deutung": (
                "Aufmerksamkeit folgt dem Bedarf, ungleiche Aufmerksamkeit oder kein "
                "Zusammenhang nachweisbar; nur beim Haupttest",
                "",
            ),
            "rechnung": (
                "haupttest, robustheit, innerhalb (Stadtbezirke), moran_residuen, moran_bedarf, "
                "moran_aufmerksamkeit oder paar",
                "",
            ),
            "explorativ": ("nach dem ersten Lauf gerechnet, ohne Korrektur", ""),
            "bedarf": ("Spalte des Bedarfs (x)", ""),
            "aufmerksamkeit": ("Spalte der Aufmerksamkeit (y)", ""),
            "kontrolle": ("Spalte, bei deren festem Wert partiell gerechnet ist; sonst leer", ""),
            "ohne": ("Wahlbezirke, ohne die gerechnet ist", "Liste"),
            "mass": ("spearman (ρ) oder moran_i", ""),
            "wert": ("das Maß", ""),
            "ci_lo": ("untere Grenze des 95-%-Bootstrap-Intervalls, nur beim Haupttest", ""),
            "ci_hi": ("obere Grenze des 95-%-Bootstrap-Intervalls, nur beim Haupttest", ""),
            "test": ("permutation oder asymptotisch", ""),
            "alternative": ("greater (einseitig, ρ > 0) oder two-sided", ""),
            "permutationen": ("Zahl der Permutationen", ""),
            "seed": ("Seed des Zufallsgenerators", ""),
        },
        joins={"ohne": "; "},
        optional=True,
        enabled=need_enabled,
    ),
)

PAGE = Page(
    PAGE_NAME,
    "Bedarf und Aufmerksamkeit je Wahlbezirk",
    "Wo amtliche Zahlen viel Bedarf zeigen, bei Unfällen, sozialer Lage und Kindern, und wie oft "
    "die Ratsdokumente diese Wahlbezirke nennen.",
    inputs=need_inputs,
    data=need_data,
    enabled=need_enabled,
    links=need_links,
)

CONTRIBUTION = Contribution("22-bedarf", steps=need_steps, tables=TABLES, pages=(PAGE,))
