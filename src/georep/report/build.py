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

from georep.export import write_csv
from georep.geo import LONLAT, read_precincts, transformer
from georep.io import atomic_path, digest, write_json, write_text
from georep.layout import Layout
from georep.report.charts import (
    MAP_WIDTH,
    choropleth,
    classify,
    legend,
    own_share_label,
    project_pois,
    rate_label,
    scatter,
    turnout_label,
)
from georep.report.documents import DOCUMENT_COLUMNS, documents_payload
from georep.report.geometry import (
    SIMPLIFY_M,
    bounds_of,
    district_shapes,
    fit,
    wahlbezirke_geojson,
)
from georep.report.model import Download, ReportModel, build_report_model, format_de
from georep.report.render import Visuals, render_map, render_report
from georep.report.tables import GEOJSON_TABLE, published
from georep.settings import Settings

GEOJSON_NAME = "wahlbezirke.geojson"
SCHEMA_NAME = "schema.json"
DOCUMENTS_NAME = "dokumente.json"
MAP_NAME = "karte.html"
# Als Tupel-Konstante, nicht als ``except (A, B)``: ruff 0.17.0 entfernt dort die Klammern und
# hinterlässt Python-2-Syntax, die nicht mehr parst (2026-10-12, dieses Modul lag so auf main).
GIT_ERRORS = (OSError, subprocess.TimeoutExpired)


@dataclass(frozen=True)
class SiteSummary:
    districts: int
    files: int  # Downloads plus index.html und karte.html
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
    except GIT_ERRORS:
        return None
    return run.stdout.strip() or None


def _download(path: Path, fmt: str, rows: int | None, description: str) -> Download:
    return Download(path.name, fmt, rows, path.stat().st_size, digest(path), description)


def _rows(parquet: Path) -> int:
    return int(pl.scan_parquet(parquet).select(pl.len()).collect().item())


def write_tables(layout: Layout) -> list[Download]:
    """Die Tabellen des Registers als Parquet (kopiert) und CSV nach ``site/data/``."""
    data_dir = layout.guard_writable(layout.site_data)
    downloads: list[Download] = []
    for table in published(layout):
        parquet = table.path(layout)
        rows = _rows(parquet)
        target = data_dir / parquet.name
        with atomic_path(target) as tmp:
            shutil.copyfile(parquet, tmp)
        downloads.append(_download(target, "Parquet", rows, table.description))
        csv_target = data_dir / f"{table.name}.csv"
        write_csv(parquet, csv_target, table.joins, table.separator)
        downloads.append(_download(csv_target, "CSV", rows, f"{table.description}, als CSV"))
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


def write_documents(layout: Layout, model: ReportModel) -> Download:
    """``dokumente.json``: die Dokumente mit Treffer ohne Texte, je Begriff als Indizes."""
    payload = documents_payload(
        pl.read_parquet(layout.corpus, columns=DOCUMENT_COLUMNS),
        pl.read_parquet(layout.index),
        model.hidden_terms,
        version=model.version,
        generated_at=model.generated_at,
    )
    target = layout.site_data / DOCUMENTS_NAME
    write_json(target, payload, indent=None)
    documents = payload["documents"]
    assert isinstance(documents, list)
    return _download(
        target,
        "JSON",
        len(documents),
        "Dokumente mit Treffer: Link, Datum, Drucksache, Titel, Art; je Begriff die Dokumente als Indizes",
    )


def _places_geojson(pois: pl.DataFrame) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"label": row["label"], "wahlkreis_id": int(row["wahlkreis_id"])},
                "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            }
            for row in pois.iter_rows(named=True)
        ],
    }


def _map_districts(
    geojson: dict[str, object], model: ReportModel, classes: dict[int, int]
) -> dict[str, object]:
    """Die Flächen für karte.html: zusätzlich Klasse und formatierte Kennzahlen je Bezirk."""
    rows = {d.id: d for d in model.districts}
    features = geojson["features"]
    assert isinstance(features, list)
    enriched = []
    for feature in features:
        props = dict(feature["properties"])
        row = rows[int(props["wahlkreis_id"])]
        props.update(
            klasse=classes[row.id],
            treffer_text=format_de(row.hits),
            quote_text=rate_label(row.rate),
            beteiligung_text=turnout_label(row.turnout),
        )
        enriched.append({**feature, "properties": props})
    return {**geojson, "features": enriched}


def build_site(
    layout: Layout, settings: Settings, *, now: dt.datetime, commit: str | None
) -> SiteSummary:
    layout.guard_writable(layout.site_data).mkdir(parents=True, exist_ok=True)
    working_crs = settings.geo.working_crs
    downloads = write_tables(layout)
    precincts = read_precincts(layout.districts_geojson, settings.columns, working_crs)
    shapes = district_shapes(precincts, SIMPLIFY_M)
    model = build_report_model(layout, settings, now=now, commit=commit)
    downloads.append(write_documents(layout, model))

    geojson = wahlbezirke_geojson(shapes, model.districts, working_crs)
    geojson_target = layout.site_data / GEOJSON_NAME
    write_json(geojson_target, geojson, indent=None)
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
    pois = pl.read_parquet(layout.pois_table, columns=["label", "wahlkreis_id", "lon", "lat"])
    xs, ys = transformer(LONLAT, working_crs).transform(
        pois.get_column("lon").to_numpy(), pois.get_column("lat").to_numpy()
    )
    points = project_pois(
        list(
            zip(
                xs.tolist(),
                ys.tolist(),
                pois.get_column("label").to_list(),
                pois.get_column("wahlkreis_id").to_list(),
                strict=True,
            )
        ),
        projection,
    )
    rate_legend = legend(rate, rate_label)
    # Option 05: dritte Kennzahl der Karte, der Anteil der eigenen Bezirksvertretung
    own = classify({d.id: d.bodies.own_share for d in model.districts if d.bodies})
    visuals = Visuals(
        map_svg=choropleth(
            model.districts,
            shapes,
            projection,
            rate,
            turnout,
            points,
            extra_classes={"bodies": own},
        ),
        scatter_svg=scatter(model.districts, model.regression),
        rate_legend=rate_legend,
        turnout_legend=legend(turnout, turnout_label),
        simplify_m=SIMPLIFY_M,
        pois=len(points),
        bodies_legend=legend(own, own_share_label),
    )
    map_html = render_map(
        model, _map_districts(geojson, model, rate.classes), _places_geojson(pois), rate_legend
    )
    write_text(layout.guard_writable(layout.site / MAP_NAME), map_html)
    html = render_report(model, visuals)
    write_text(layout.guard_writable(layout.site_index), html)
    total = (
        sum(d.bytes for d in downloads) + len(html.encode("utf-8")) + len(map_html.encode("utf-8"))
    )
    return SiteSummary(len(model.districts), len(downloads) + 2, total)
