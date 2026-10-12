"""Der Städtevergleich: eine Seite aus den veröffentlichten Ordnern mehrerer Städte (Option 01).

Gelesen wird je Stadt nur, was auf ihrer Seite zum Download steht: ``data/summary.json``
(Kernzahlen und Regression), ``data/wahlbezirke.geojson`` (Flächen in EPSG:4326 mit Kennzahlen)
und ``data/wahlbezirke_auswertung.parquet`` (Zeilen je Wahlbezirk). Die Stadtseite ist damit die
Schnittstelle, nicht ihr Zwischenstand (docs/plans/01-staedte.md, § 2).

Die Diagramme: zwei kleine Choroplethen mit **gemeinsamen** Quantilklassen (sonst verglichen sie
Farben, die nichts miteinander zu tun haben) und ein Streudiagramm mit einer Farbe je Stadt und
je einer Regressionsgeraden. Die beiden Farben sind die der Seite (``--accent``, ``--selected``);
sie bestehen die sechs Prüfungen der Skill ``dataviz`` in hell und dunkel (Delta E 33,6 normal,
24,7 protan hell; 31,8 und 26,8 dunkel), und jede Reihe trägt zusätzlich eine eigene Markenform.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from georep.analysis.regression import RegressionResult
from georep.errors import SchemaError
from georep.geo import LONLAT, project, transformer
from georep.report.charts import Axes, Classification, classify, legend, rate_label
from georep.report.geometry import Projection, bounds_of, fit, svg_path
from georep.report.model import format_de, percent_de

SMALL_MAP_WIDTH = 320.0  # zwei Karten nebeneinander, auch auf einem schmalen Bildschirm
SCATTER_WIDTH = 640.0
SCATTER_HEIGHT = 400.0
SUMMARY_NAME = "summary.json"
GEOJSON_NAME = "wahlbezirke.geojson"
RESULTS_NAME = "wahlbezirke_auswertung.parquet"
SHAPES = ("circle", "square")  # zweite Kodierung neben der Farbe (dataviz: nie Farbe allein)


@dataclass(frozen=True)
class DistrictPoint:
    """Ein Wahlbezirk im Vergleich: Nummer, Name, Trefferquote, Wahlbeteiligung, Wahlberechtigte."""

    id: int
    name: str
    rate: float
    turnout: float
    eligible: int


@dataclass(frozen=True)
class CitySite:
    """Was der veröffentlichte Ordner einer Stadt hergibt."""

    slug: str
    name: str
    href: str  # relativ zur Wurzel des veröffentlichten Ordners
    summary: dict[str, object]
    districts: tuple[DistrictPoint, ...]
    shapes: dict[int, BaseGeometry]  # im Arbeits-CRS, aus dem veröffentlichten GeoJSON

    @property
    def figures(self) -> dict[str, float]:
        figures = self.summary.get("figures")
        if not isinstance(figures, dict):
            raise SchemaError(f"{self.slug}: summary.json ohne figures")
        return figures

    @property
    def fit(self) -> RegressionResult | None:
        regression = self.summary.get("regression")
        payload = regression.get("all") if isinstance(regression, dict) else None
        if not isinstance(payload, dict):
            return None
        return RegressionResult(
            n=int(payload["n"]),
            slope=float(payload["slope"]),
            intercept=float(payload["intercept"]),
            r=float(payload["r"]),
            p=float(payload["p"]),
            stderr=float(payload.get("stderr", 0.0)),
        )

    @property
    def eligible_per_district(self) -> float:
        total = sum(d.eligible for d in self.districts)
        return total / len(self.districts) if self.districts else 0.0


def read_city_site(folder: Path, href: str, working_crs: str) -> CitySite:
    """Liest den veröffentlichten Ordner einer Stadt; fehlt eine Datei, ist das ein Schemafehler."""
    data = folder / "data"
    missing = [n for n in (SUMMARY_NAME, GEOJSON_NAME, RESULTS_NAME) if not (data / n).is_file()]
    if missing:
        raise SchemaError(f"{folder}: {missing} fehlen; lief `georep run` für diese Stadt?")
    summary = json.loads((data / SUMMARY_NAME).read_text(encoding="utf-8"))
    city = summary.get("city", {})
    results = pl.read_parquet(data / RESULTS_NAME).select(
        "wahlkreis_id", "trefferquote", "wahlbeteiligung", "Wahlberechtigte_insgesamt"
    )
    eligible = {
        int(row["wahlkreis_id"]): int(row["Wahlberechtigte_insgesamt"])
        for row in results.iter_rows(named=True)
    }
    collection = json.loads((data / GEOJSON_NAME).read_text(encoding="utf-8"))
    to_working = transformer(LONLAT, working_crs)
    districts: list[DistrictPoint] = []
    shapes: dict[int, BaseGeometry] = {}
    for feature in collection["features"]:
        properties = feature["properties"]
        district = int(properties["wahlkreis_id"])
        districts.append(
            DistrictPoint(
                id=district,
                name=str(properties["name"]),
                rate=float(properties["trefferquote"]),
                turnout=float(properties["wahlbeteiligung"]),
                eligible=eligible.get(district, 0),
            )
        )
        shapes[district] = project(shape(feature["geometry"]), to_working)
    return CitySite(
        slug=str(city.get("slug", "")),
        name=str(city.get("name", "")),
        href=href,
        summary=summary,
        districts=tuple(sorted(districts, key=lambda d: d.id)),
        shapes=shapes,
    )


@dataclass(frozen=True)
class ComparisonModel:
    """Alles, was ``vergleich.html`` braucht; Zeit und Commit sind Eingaben."""

    generated_at: dt.datetime
    version: str
    commit: str | None
    cities: tuple[CitySite, ...]
    maps: tuple[tuple[str, str], ...]  # (Stadtname, SVG)
    scatter_svg: str
    rate_legend: tuple[tuple[int, str], ...]


def _num(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def shared_classes(cities: tuple[CitySite, ...]) -> Classification:
    """Quantilklassen über die Trefferquoten **aller** Städte; nur so sind die Farben vergleichbar."""
    values = {
        index: district.rate
        for index, district in enumerate(d for city in cities for d in city.districts)
    }
    return classify(values)


def small_map(city: CitySite, classes: Classification, offset: int) -> str:
    """Eine kleine Choroplethe ohne Bedienung: Flächen, Klassen, Namen im ``<title>``."""
    projection: Projection = fit(bounds_of(city.shapes), SMALL_MAP_WIDTH)
    # Der Slug kommt aus summary.json, also aus einer Datei: escapen wie jeden anderen Wert
    ident = html.escape(city.slug, quote=True)
    parts = [
        f'<svg class="small-map" viewBox="{projection.view_box}" role="img" '
        f'aria-labelledby="map-{ident}" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="map-{ident}">Trefferquote je Wahlbezirk in {html.escape(city.name)}</title>',
        '<g class="districts" fill-rule="evenodd">',
    ]
    for index, district in enumerate(city.districts):
        geometry = city.shapes.get(district.id)
        if geometry is None:
            continue
        klass = classes.classes[offset + index]
        parts.append(
            f'<path class="district q{klass}" d="{svg_path(geometry, projection)}">'
            f"<title>{html.escape(district.name)} (Wahlbezirk {district.id}): "
            f"Trefferquote {rate_label(district.rate)}, "
            f"Wahlbeteiligung {percent_de(district.turnout)}</title></path>"
        )
    parts.append("</g></svg>")
    return "".join(parts)


def comparison_scatter(cities: tuple[CitySite, ...]) -> str:
    """Trefferquote gegen Wahlbeteiligung, eine Farbe und eine Markenform je Stadt."""
    xs = [d.rate for city in cities for d in city.districts]
    ys = [d.turnout * 100.0 for city in cities for d in city.districts]
    axes = Axes.fit(xs, ys, width=SCATTER_WIDTH, height=SCATTER_HEIGHT)
    parts = [
        f'<svg class="scatter" viewBox="0 0 {_num(SCATTER_WIDTH)} {_num(SCATTER_HEIGHT)}" '
        'role="img" aria-labelledby="scatter-title" xmlns="http://www.w3.org/2000/svg">',
        '<title id="scatter-title">Trefferquote gegen Wahlbeteiligung je Wahlbezirk, '
        "beide Städte</title>",
        axes.clip_path(),
        axes.grid(),
        axes.axis_lines(),
        axes.tick_labels(),
        axes.axis_titles("Trefferquote (Dokumente je Wahlberechtigtem)", "Wahlbeteiligung in %"),
    ]
    for index, city in enumerate(cities):
        series = f"s{index}"
        fit_line = city.fit
        if fit_line is not None and city.districts:
            # Die Gerade nur über den Wertebereich dieser Stadt: sie in den Bereich der anderen
            # zu verlängern wäre eine Extrapolation, die niemand gerechnet hat.
            own = [d.rate for d in city.districts]
            x0, x1 = max(axes.x0, min(own)), min(axes.x1, max(own))
            parts.append(
                f'<g class="fits {series}" clip-path="url(#plot)"><line class="fit" '
                f'x1="{_num(axes.sx(x0))}" y1="{_num(axes.sy(fit_line.slope * x0 + fit_line.intercept))}" '
                f'x2="{_num(axes.sx(x1))}" y2="{_num(axes.sy(fit_line.slope * x1 + fit_line.intercept))}"/></g>'
            )
        parts.append(f'<g class="dots {series}">')
        for district in city.districts:
            cx, cy = axes.sx(district.rate), axes.sy(district.turnout * 100.0)
            title = (
                f"{city.name}, Wahlbezirk {district.id} {district.name}: "
                f"Trefferquote {rate_label(district.rate)}, "
                f"Wahlbeteiligung {percent_de(district.turnout)}"
            )
            marker = (
                f'<circle class="dot" cx="{_num(cx)}" cy="{_num(cy)}" r="4"/>'
                if SHAPES[index % len(SHAPES)] == "circle"
                else f'<rect class="dot" x="{_num(cx - 3.5)}" y="{_num(cy - 3.5)}" '
                'width="7" height="7"/>'
            )
            parts.append(f"<g><title>{html.escape(title)}</title>{marker}</g>")
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


def build_comparison(
    cities: tuple[CitySite, ...], *, now: dt.datetime, version: str, commit: str | None
) -> ComparisonModel:
    classes = shared_classes(cities)
    maps: list[tuple[str, str]] = []
    offset = 0
    for city in cities:
        maps.append((city.name, small_map(city, classes, offset)))
        offset += len(city.districts)
    return ComparisonModel(
        generated_at=now,
        version=version,
        commit=commit,
        cities=cities,
        maps=tuple(maps),
        scatter_svg=comparison_scatter(cities),
        rate_legend=tuple((entry.klass, entry.label) for entry in legend(classes, rate_label)),
    )


def table_rows(model: ComparisonModel) -> list[dict[str, str]]:
    """Eine Zeile je Stadt; die Zahlen stammen aus ``summary.json``, nichts ist hier gerechnet."""
    rows: list[dict[str, str]] = []
    for city in model.cities:
        figures = city.figures
        fit_line = city.fit
        rates = [d.rate for d in city.districts]
        rows.append(
            {
                "name": city.name,
                "href": city.href or "./",
                "districts": format_de(float(figures["districts"])),
                "precincts": format_de(float(figures["precincts"])),
                "documents": format_de(float(figures["documents"])),
                "terms": format_de(float(figures["terms"])),
                "documents_hit": format_de(float(figures["documents_hit"])),
                "rate_median": rate_label(statistics.median(rates) if rates else 0.0),
                "turnout_median": percent_de(float(figures["turnout_median"])),
                "eligible_per_district": format_de(city.eligible_per_district),
                "r": format_de(fit_line.r, 3) if fit_line else "—",
                "p": format_de(fit_line.p, 3) if fit_line else "—",
            }
        )
    return rows
