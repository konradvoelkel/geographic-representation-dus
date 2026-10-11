"""Der Schritt ``report``: Download-Dateien, Schema, Karte, Diagramm, Seite.

Reihenfolge: erst die Dateien unter ``site/data/`` (Parquet kopiert, CSV mit den Regeln von
``georep export``, GeoJSON, ``schema.json``), dann das Modell mit ihren Prüfsummen, dann die
SVGs, zuletzt ``index.html``; die trägt den Stamp. Zeit und Commit sind Eingaben.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

import polars as pl

from georep.export import csv_plan, write_csv
from georep.geo import LONLAT, read_precincts, transformer
from georep.io import atomic_path, digest, write_json, write_text
from georep.layout import Layout
from georep.report.charts import (
    MAP_WIDTH,
    choropleth,
    classify,
    legend,
    project_points,
    rate_label,
    scatter,
    turnout_label,
)
from georep.report.geometry import (
    SIMPLIFY_M,
    bounds_of,
    district_shapes,
    fit,
    wahlbezirke_geojson,
)
from georep.report.model import (
    GEOJSON_TABLE,
    Download,
    ReportModel,
    build_report_model,
    format_de,
    published_tables,
)
from georep.report.render import Visuals, render_report
from georep.settings import Settings

GEOJSON_NAME = "wahlbezirke.geojson"
SCHEMA_NAME = "schema.json"
DESCRIPTIONS = {
    "wahlbezirke_auswertung": "Auswertung je Wahlbezirk: Treffer, Begriffe, Dokument-IDs, Wähler, Trefferquote",
    "inverted_index": "Invertierter Index: je Begriff die Dokumente mit Treffer",
    "combined_searchdict": "Wörterbuch je Wahlbezirk mit allen Begriffen",
    "wahlbezirke_waehler": "Wahlergebnis der Ratswahl 2025 je Wahlbezirk",
    "wikidata_vis": "Orte mit Koordinate und Wahlbezirk",
    "wahlbezirke_strassen": "Straßennamen je Wahlbezirk",
}


@dataclass(frozen=True)
class SiteSummary:
    districts: int
    files: int  # Downloads plus index.html
    bytes: int

    def line(self) -> str:
        return f"{self.districts} Wahlbezirke, {self.files} Dateien, {format_de(self.bytes / 1e6, 1)} MB"


def current_commit(cwd: Path | None = None) -> str | None:
    """Kurzer Commit-Hash aus ``GITHUB_SHA`` oder ``git rev-parse``; None, wenn beides fehlt."""
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha[:7]
    try:
        run = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return None
    return run.stdout.strip() or None


def _download(path: Path, fmt: str, rows: int | None, description: str) -> Download:
    return Download(path.name, fmt, rows, path.stat().st_size, digest(path), description)


def _rows(parquet: Path) -> int:
    return int(pl.scan_parquet(parquet).select(pl.len()).collect().item())


def write_tables(layout: Layout) -> list[Download]:
    """Die sechs Tabellen als Parquet (kopiert) und CSV nach ``site/data/``."""
    data_dir = layout.guard_writable(layout.site_data)
    plan = {parquet: (joins, sep) for parquet, joins, sep in csv_plan(layout)}
    downloads: list[Download] = []
    for name, parquet in published_tables(layout).items():
        rows = _rows(parquet)
        target = data_dir / parquet.name
        with atomic_path(target) as tmp:
            shutil.copyfile(parquet, tmp)
        downloads.append(_download(target, "Parquet", rows, DESCRIPTIONS[name]))
        joins, separator = plan[parquet]
        csv_target = data_dir / f"{name}.csv"
        write_csv(parquet, csv_target, joins, separator)
        downloads.append(_download(csv_target, "CSV", rows, f"{DESCRIPTIONS[name]}, als CSV"))
    return downloads


def write_schema(layout: Layout, model: ReportModel) -> Download:
    tables: dict[str, list[dict[str, str]]] = {}
    for column in model.columns:
        tables.setdefault(column.table, []).append(
            {
                "column": column.column,
                "dtype": column.dtype,
                "description": column.description,
                "unit": column.unit,
            }
        )
    target = layout.site_data / SCHEMA_NAME
    write_json(
        target,
        {
            "version": model.version,
            "generated_at": model.generated_at.isoformat(),
            "tables": tables,
        },
    )
    return _download(target, "JSON", None, "Spaltenschema aller Tabellen, maschinenlesbar")


def build_site(
    layout: Layout, settings: Settings, *, now: dt.datetime, commit: str | None
) -> SiteSummary:
    layout.guard_writable(layout.site_data).mkdir(parents=True, exist_ok=True)
    working_crs = settings.geo.working_crs
    downloads = write_tables(layout)
    precincts = read_precincts(layout.districts_geojson, settings.columns, working_crs)
    shapes = district_shapes(precincts, SIMPLIFY_M)
    model = build_report_model(layout, settings, now=now, commit=commit)

    geojson_target = layout.site_data / GEOJSON_NAME
    write_json(
        geojson_target, wahlbezirke_geojson(shapes, model.districts, working_crs), indent=None
    )
    downloads.append(
        _download(
            geojson_target,
            "GeoJSON",
            len(shapes),
            f"Flächen der Wahlbezirke in EPSG:4326 mit den Kennzahlen (Tabelle {GEOJSON_TABLE})",
        )
    )
    model = replace(model, downloads=tuple(downloads))
    downloads.append(write_schema(layout, model))
    model = replace(model, downloads=tuple(downloads))

    projection = fit(bounds_of(shapes), MAP_WIDTH)
    rate = classify({d.id: d.rate for d in model.districts})
    turnout = classify({d.id: d.turnout for d in model.districts})
    pois = pl.read_parquet(layout.pois_table, columns=["lon", "lat"])
    xs, ys = transformer(LONLAT, working_crs).transform(
        pois.get_column("lon").to_numpy(), pois.get_column("lat").to_numpy()
    )
    points = project_points(list(zip(xs.tolist(), ys.tolist(), strict=True)), projection)
    visuals = Visuals(
        map_svg=choropleth(model.districts, shapes, projection, rate, turnout, points),
        scatter_svg=scatter(model.districts, model.regression),
        rate_legend=legend(rate, rate_label),
        turnout_legend=legend(turnout, turnout_label),
        simplify_m=SIMPLIFY_M,
        pois=len(points),
    )
    html = render_report(model, visuals)
    write_text(layout.guard_writable(layout.site_index), html)
    total = sum(d.bytes for d in downloads) + len(html.encode("utf-8"))
    return SiteSummary(len(model.districts), len(downloads) + 1, total)
