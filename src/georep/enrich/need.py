"""Beitrag von Vorhaben 22: Bedarf und Aufmerksamkeit je Wahlbezirk.

Zwei Schritte hinter dem Kern (``docs/plans/22-bedarf.md``, § 6 und § 10):

* ``need_data`` (Netz) holt die Archive der Bedarfsquellen aus ``[context.need]`` nach
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

from georep.analysis.need import CONFIRMED, MAIN, STRATUM, hypothesis_table, neighbours
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
from georep.settings import Settings, archive_name
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


def _archive(
    http: Transport, url: str, folder: Path, *, max_age_s: int, now: float
) -> tuple[Path, bool]:
    """Das Archiv unter ``folder``; geladen nur, wenn es fehlt oder älter ist als ``max_age_s``."""
    target = folder / archive_name(url)
    if target.is_file() and now - target.stat().st_mtime < max_age_s:
        return target, False
    content = fetch_zip(http, url) if target.suffix.lower() == ".zip" else fetch_csv(http, url)
    write_bytes(target, content)
    return target, True


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


def need_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Die Schritte ``need_data`` und ``need``, wenn ``context.need.enabled``."""
    need = settings.context.need
    if not need.enabled:
        return []
    files = need_files(layout)
    working = settings.geo.working_crs
    ags = settings.city.ags
    with_classes = need.with_classes() and settings.classify.enabled
    with_context = layout.context_root is not None
    with_tests = bool(need.hypotheses or need.explore)

    def precincts() -> list[Precinct]:
        return read_canonical_precincts(layout.precincts_geojson, working)

    def need_data() -> str:
        now = time.time()
        fetched = 0
        paths: dict[str, Path] = {}
        for url in need.archive_urls():
            paths[url], new = _archive(
                http, url, files.archives, max_age_s=settings.cache.opendata_s, now=now
            )
            fetched += new
        accidents = pl.concat(
            [read_accidents(paths[url], ags) for url in need.accidents.archives]
        ).sort("jahr", "monat", "x", "y")
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
        schools = read_schools(
            paths[need.schools.schools_url],
            paths[need.schools.index_url],
            ags,
            crs=need.schools.crs,
            index_encoding=need.schools.index_encoding,
        )
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
            f"{cells.height} Gitterzellen, {schools.height} Schulen der Gemeinde {ags}"
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
        base = pl.DataFrame(
            {DISTRICT: districts, "flaeche_km2": [u.area / 1e6 for u in unions]},
            schema={DISTRICT: pl.Int64, "flaeche_km2": pl.Float64},
        ).join(strata, on=DISTRICT, how="left")
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
            return done
        frame = table.join(
            results.select(DISTRICT, "trefferquote", "wahlbeteiligung"), on=DISTRICT, how="left"
        ).with_columns(pl.col("begriffe").cast(pl.Float64).log().alias("log_begriffe"))
        if with_context:
            frame = frame.join(pl.read_parquet(layout.context_table), on=DISTRICT, how="left")
        tests = hypothesis_table(
            frame.sort(DISTRICT),
            need,
            weights=neighbours(unions, need.neighbour_m),
            exclude=settings.analysis.exclude_districts,
        )
        write_parquet(tests, files.tests, schema_version=NEED_SCHEMA_VERSION)
        main = tests.filter(pl.col("rechnung") == MAIN)
        verdicts = ", ".join(
            f"{name} {'bestätigt' if result == CONFIRMED else 'nicht bestätigt'}"
            for name, result in main.select("hypothese", "ergebnis").rows()
        )
        return f"{done}; {verdicts or 'keine Hypothese'}, {tests.height} Zeilen"

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
    return [
        Step(
            "need_data",
            (layout.precincts_geojson,),
            (*extracts, files.sources),
            need_data,
            NEED_DATA_SCHEMA_VERSION,
            network=True,
        ),
        Step(
            "need",
            inputs,
            (files.table, *((files.tests,) if with_tests else ())),
            need_step,
            NEED_SCHEMA_VERSION,
        ),
    ]


CONTRIBUTION = Contribution("22-bedarf", steps=need_steps)
