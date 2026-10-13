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

from georep.analysis.hits import DISTRICT
from georep.analysis.ols import CONSTANT, model_frame, partial_residuals
from georep.export import write_csv
from georep.geo import LONLAT, read_canonical_precincts, transformer
from georep.io import atomic_path, digest, write_json, write_text
from georep.layout import Layout
from georep.prep.voters import TURNOUT
from georep.report.charts import (
    MAP_WIDTH,
    Classification,
    added_variable_plot,
    bars,
    choropleth,
    classify,
    classify_fixed,
    delta_scatter,
    hits_label,
    legend,
    legend_for,
    own_share_label,
    party_maps,
    per_term_label,
    percent_signed_label,
    points_label,
    project_pois,
    rate_label,
    ratio_label,
    scatter,
    turnout_label,
)
from georep.report.documents import DOCUMENT_COLUMNS, documents_payload, originator_labels
from georep.report.geometry import (
    SIMPLIFY_M,
    bounds_of,
    district_shapes,
    fit,
    wahlbezirke_geojson,
)
from georep.report.model import (
    SUMMARY_FIELDS,
    Download,
    ReportModel,
    build_report_model,
    format_de,
    summary_payload,
)
from georep.report.render import Visuals, render_map, render_report
from georep.report.tables import GEOJSON_TABLE, TABLES, PublishedTable, published
from georep.report.terms import pairs, terms_payload
from georep.settings import Settings

GEOJSON_NAME = "wahlbezirke.geojson"
SCHEMA_NAME = "schema.json"
SUMMARY_NAME = "summary.json"
DOCUMENTS_NAME = "dokumente.json"
TERMS_NAME = "begriffe.json"  # Punkt 49
MAP_NAME = "karte.html"


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
    except OSError, subprocess.TimeoutExpired:
        return None
    return run.stdout.strip() or None


def _download(path: Path, fmt: str, rows: int | None, description: str) -> Download:
    return Download(path.name, fmt, rows, path.stat().st_size, digest(path), description)


def _rows(parquet: Path) -> int:
    return int(pl.scan_parquet(parquet).select(pl.len()).collect().item())


def _remove_unpublished(layout: Layout, wanted: list[PublishedTable]) -> None:
    """Dateien abgeschalteter Tabellen aus ``site/data/`` nehmen, damit nichts Altes mitfährt.

    Nur Namen aus dem Register: eine Tabelle, die jetzt nicht veröffentlicht wird (``topics.k = 0``
    nach einem Lauf mit Themen), ließe sonst ihr Parquet und ihr CSV im Ordner stehen, ohne Link
    auf der Seite, aber mit im Pages-Paket. Fremde Dateien bleiben unberührt.
    """
    keep = {t.path(layout).name for t in wanted} | {f"{t.name}.csv" for t in wanted}
    for table in TABLES:
        for name in (table.path(layout).name, f"{table.name}.csv"):
            stale = layout.site_data / name
            if name not in keep and stale.is_file():
                stale.unlink()


def write_tables(layout: Layout, settings: Settings | None = None) -> list[Download]:
    """Die Tabellen des Registers als Parquet (kopiert) und CSV nach ``site/data/``."""
    data_dir = layout.guard_writable(layout.site_data)
    downloads: list[Download] = []
    wanted = published(layout, settings)
    _remove_unpublished(layout, wanted)
    for table in wanted:
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
            # Option 01: summary.json ist keine Tabelle, steht aber im Schema
            "summary": dict(SUMMARY_FIELDS),
        },
    )
    return _download(target, "JSON", None, "Spaltenschema aller Tabellen, maschinenlesbar")


def write_summary(layout: Layout, model: ReportModel) -> Download:
    """``summary.json``: Kernzahlen, beide Regressionen, Datenstand, Stadt (Option 01).

    Das ist die Schnittstelle des Städtevergleichs: ``georep publish`` liest je Stadt nur den
    veröffentlichten Ordner, nie Zwischenergebnisse.
    """
    target = layout.guard_writable(layout.site_summary)
    write_json(target, summary_payload(model))
    return _download(
        target, "JSON", None, "Kernzahlen, Regression und Datenstand dieser Stadt, maschinenlesbar"
    )


def write_documents(layout: Layout, model: ReportModel, settings: Settings) -> Download:
    """``dokumente.json``: die Dokumente mit Treffer ohne Texte, je Begriff als Indizes."""
    # Option 04: der Urheber je Dokument, falls der Schritt ``parties`` lief. Die Label kommen aus
    # den Settings und nicht aus ``model.parties``, damit auch die Gruppen ohne Stimmenspalte
    # (Tierschutz/Freie Wähler, Die PARTEI, Volt) ihren Namen tragen und nicht ihren Schlüssel.
    attribution = (
        pl.read_parquet(layout.document_originators)
        if layout.document_originators.exists()
        else None
    )
    labels = {p.key: p.label for p in (*settings.originators.parties, *settings.originators.groups)}
    payload = documents_payload(
        pl.read_parquet(layout.corpus, columns=DOCUMENT_COLUMNS),
        pl.read_parquet(layout.index),
        model.hidden_terms,
        version=model.version,
        generated_at=model.generated_at,
        originators=originator_labels(attribution, labels),
    )
    target = layout.site_data / DOCUMENTS_NAME
    write_json(target, payload, indent=None)
    documents = payload["documents"]
    assert isinstance(documents, list)
    return _download(
        target,
        "JSON",
        len(documents),
        "Dokumente mit Treffer: Link, Datum, Drucksache, Titel, Art, Urheber; "
        "je Begriff die Dokumente als Indizes",
    )


def write_terms(layout: Layout, model: ReportModel) -> Download:
    """``begriffe.json``: je Wahlbezirk seine Begriffe mit Treffer (Punkt 49).

    Die Listen standen bis zum 2026-10-13 in der Seite und waren mit 334 KB ihr größter Posten,
    obwohl sie zugeklappt dastanden; der Abschnitt „Begriffe" lädt sie jetzt beim Aufklappen nach
    (docs/seitengroesse-2026-10.md, § 4).
    """
    target = layout.site_data / TERMS_NAME
    write_json(
        target,
        terms_payload(model.districts, version=model.version, generated_at=model.generated_at),
        indent=None,
    )
    return _download(
        target,
        "JSON",
        pairs(model.districts),
        "Begriffe mit Treffer je Wahlbezirk mit der Zahl ihrer Dokumente, absteigend; "
        "der Abschnitt Begriffe lädt sie beim Aufklappen eines Wahlbezirks nach",
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


def partial_plots(layout: Layout, settings: Settings, model: ReportModel) -> list[tuple[str, str]]:
    """Option 03: ein Added-Variable-Plot je Term des Hauptmodells, leer ohne Kontextdaten.

    Die Residuen entstehen aus derselben Tabelle wie die Modelle; die Punkte tragen die
    ``DistrictRow`` ihres Wahlbezirks, damit Tooltip und Markierung wie im Streudiagramm wirken.
    """
    controls = model.controls
    if controls is None or not layout.context_table.exists():
        return []
    main = next((m for m in controls.models if m.name == controls.main), None)
    if main is None or main.k < 1:
        return []
    frame = model_frame(pl.read_parquet(layout.results), pl.read_parquet(layout.context_table))
    names = {row.id: row.name for row in model.districts}
    districts = [(int(i), names[int(i)]) for i in frame.get_column(DISTRICT).to_list()]
    terms = [t.term for t in main.terms if t.term != CONSTANT]
    plots: list[tuple[str, str]] = []
    for stats in main.terms:
        if stats.term == CONSTANT:
            continue
        xs, ys = partial_residuals(
            frame, TURNOUT, terms, stats.term, y_scale=settings.context.models.y_scale
        )
        plots.append(
            (
                f"{stats.label} (Steigung {format_de(stats.coefficient, 2)})",
                added_variable_plot(
                    districts,
                    xs,
                    ys,
                    stats.coefficient,
                    key=stats.term,
                    title=(
                        f"{stats.label} gegen Wahlbeteiligung, beide um die übrigen Terme bereinigt"
                    ),
                    x_title=f"{stats.label}, bereinigt",
                    y_title="Wahlbeteiligung, bereinigt",
                ),
            )
        )
    return plots


def build_site(
    layout: Layout, settings: Settings, *, now: dt.datetime, commit: str | None
) -> SiteSummary:
    layout.guard_writable(layout.site_data).mkdir(parents=True, exist_ok=True)
    working_crs = settings.geo.working_crs
    downloads = write_tables(layout, settings)
    precincts = read_canonical_precincts(
        layout.target_view(settings).precincts_geojson, working_crs
    )
    shapes = district_shapes(precincts, SIMPLIFY_M)
    model = build_report_model(layout, settings, now=now, commit=commit)
    downloads.append(write_documents(layout, model, settings))
    downloads.append(write_terms(layout, model))  # Punkt 49

    geojson = wahlbezirke_geojson(
        shapes,
        model.districts,
        working_crs,
        # Option 01 und 02: Stadt und Periode stehen im Namen der FeatureCollection
        f"Kommunalwahlbezirke {settings.city.name}, {model.period.title}",
    )
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
    # Option 01: die Schnittstelle des Städtevergleichs, als eigener Download
    downloads.append(write_summary(layout, model))
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
    # Punkt 46: drei Normierungen derselben Treffer. Die beiden Zählungen bekommen Quantile wie
    # die Quote, die Abweichung feste Grenzen aus den Settings -- Quantile wären dort genau die
    # Klassen der Quote, nur divergierend gefärbt (docs/skalierung-2026-10.md, § 2.4).
    with_scaling = [d for d in model.districts if d.metrics is not None]
    extra: dict[str, Classification] = {"bodies": own}
    hits_classes = per_term_classes = deviation_classes = None
    if with_scaling:
        hits_classes = classify({d.id: float(d.hits) for d in with_scaling})
        per_term_classes = classify({d.id: d.metrics.per_term for d in with_scaling if d.metrics})
        # Hier ist der Schlüssel der Wahlbezirk und jeder kommt einmal vor: die Klassen der
        # Flächen entstehen wirklich aus diesen Werten.
        deviation_classes = classify_fixed(
            {d.id: d.metrics.deviation for d in with_scaling if d.metrics},
            settings.report.diverging.district_percent,
        )
        extra |= {
            "treffer": hits_classes,
            "jebegriff": per_term_classes,
            "abweichung": deviation_classes,
        }
    dated_months = [row for row in model.timeline if row.month is not None]  # Option 07
    # Punkt 46: die beiden divergierenden Legenden der Parteikarten. Ihre Klassen stecken schon in
    # den Zellen (``party_section``); hier entstehen nur die Beschriftungen der festen Grenzen,
    # und die kennen die Werte nicht (``legend_for``).
    diverging = settings.report.diverging
    party_points_legend = (
        legend_for(diverging.party_points, points_label) if model.party_cells else ()
    )
    party_ratio_legend = legend_for(diverging.party_ratio, ratio_label) if model.party_cells else ()
    visuals = Visuals(
        map_svg=choropleth(
            model.districts,
            shapes,
            projection,
            rate,
            turnout,
            points,
            extra_classes=extra,
        ),
        # Option 07: ohne Wahlbeteiligung zur Periode gibt es kein Streudiagramm, dafür Balken
        scatter_svg=scatter(model.districts, model.regression) if model.regression else None,
        delta_svg=(
            delta_scatter(model.comparison.rows, model.comparison.regression)
            if model.comparison is not None
            else ""
        ),
        rate_legend=rate_legend,
        turnout_legend=legend(turnout, turnout_label),
        simplify_m=SIMPLIFY_M,
        pois=len(points),
        bodies_legend=legend(own, own_share_label),
        partial_svgs=partial_plots(layout, settings, model),
        # Option 04: eine kleine Karte je Partei, die 41 Pfade einmal in <defs>
        party_maps_svg=party_maps(model.party_cells, shapes, projection, model.parties),
        bars_svg=bars(model.timeline) if dated_months else "",
        # Punkt 46: je Normierung eine Legende; leere Listen blenden Radio und Legende aus
        party_points_legend=party_points_legend,
        party_ratio_legend=party_ratio_legend,
        hits_legend=legend(hits_classes, hits_label) if hits_classes else (),
        per_term_legend=legend(per_term_classes, per_term_label) if per_term_classes else (),
        deviation_legend=(
            legend(deviation_classes, percent_signed_label) if deviation_classes else ()
        ),
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
