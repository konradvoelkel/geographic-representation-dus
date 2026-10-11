"""Wahlbezirke aus Stimmbezirken: vereinigen, vereinfachen, als SVG-Pfade und GeoJSON ausgeben.

Alles im metrischen Arbeits-CRS (EPSG:25832), darum ist die Karte formtreu, ohne Kacheln und ohne
Reprojektion; nur das GeoJSON für GIS geht über ``georep.geo.to_lonlat`` nach EPSG:4326.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import deal
import shapely
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.geometry.base import BaseGeometry

from georep.geo import Precinct, repaired, to_lonlat
from georep.report.model import DistrictRow

AREA_TOLERANCE = 0.01  # die Flächensumme nach dem Vereinfachen weicht höchstens 1 % ab
SIMPLIFY_M = 15.0  # Douglas-Peucker im Arbeits-CRS; 26 773 -> 2066 Stützpunkte bei 0,01 % Fläche
GEOJSON_DECIMALS = 6  # rund 10 cm in Grad; mehr ist Rauschen der Transformation


def _same_districts(
    precincts: Sequence[Precinct],
    tolerance_m: float = SIMPLIFY_M,
    result: Mapping[int, BaseGeometry] | None = None,
) -> bool:
    assert result is not None
    return set(result) == {p.district_id for p in precincts}


def _area_kept(
    precincts: Sequence[Precinct],
    tolerance_m: float = SIMPLIFY_M,
    result: Mapping[int, BaseGeometry] | None = None,
) -> bool:
    assert result is not None
    before = sum(p.geometry.area for p in precincts)
    after = sum(g.area for g in result.values())
    return abs(after - before) <= AREA_TOLERANCE * before


@deal.pre(lambda precincts, tolerance_m=SIMPLIFY_M: tolerance_m >= 0 and len(precincts) > 0)
@deal.post(lambda result: all(g.is_valid and not g.is_empty for g in result.values()))
@deal.ensure(_same_districts, message="ein Wahlbezirk je district_id der Stimmbezirke")
@deal.ensure(_area_kept, message="Flächensumme bis auf 1 % erhalten")
def district_shapes(
    precincts: Sequence[Precinct], tolerance_m: float = SIMPLIFY_M
) -> dict[int, BaseGeometry]:
    """``unary_union`` je Wahlbezirk, vereinfacht mit erhaltener Topologie, repariert; nach ID sortiert."""
    by_district: dict[int, list[BaseGeometry]] = {}
    for precinct in precincts:
        by_district.setdefault(precinct.district_id, []).append(precinct.geometry)
    shapes: dict[int, BaseGeometry] = {}
    for district, parts in sorted(by_district.items()):
        merged = shapely.unary_union(parts)
        if tolerance_m > 0:
            merged = merged.simplify(tolerance_m, preserve_topology=True)
        shapes[district] = repaired(merged)
    return shapes


@dataclass(frozen=True)
class Projection:
    """Arbeits-CRS -> SVG: die Bounding Box auf eine viewBox der Breite ``width``, y gespiegelt."""

    min_x: float
    max_y: float
    scale: float  # SVG-Einheiten je Meter
    width: float
    height: float

    @property
    def view_box(self) -> str:
        return f"0 0 {self.width:.2f} {self.height:.2f}"

    def point(self, x: float, y: float) -> tuple[float, float]:
        return ((x - self.min_x) * self.scale, (self.max_y - y) * self.scale)


@deal.pre(
    lambda bounds, width: width > 0 and bounds[2] > bounds[0] and bounds[3] > bounds[1],
    message="Breite positiv, Bounding Box mit Ausdehnung in beiden Richtungen",
)
@deal.post(lambda result: result.height > 0 and result.scale > 0)
def fit(bounds: tuple[float, float, float, float], width: float) -> Projection:
    """Seitenverhältnis bleibt: die Höhe folgt aus der Bounding Box."""
    min_x, min_y, max_x, max_y = bounds
    scale = width / (max_x - min_x)
    return Projection(min_x, max_y, scale, width, (max_y - min_y) * scale)


def bounds_of(shapes: Mapping[int, BaseGeometry]) -> tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = shapely.unary_union(list(shapes.values())).bounds
    return (float(min_x), float(min_y), float(max_x), float(max_y))


def _polygons(geometry: BaseGeometry) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    return [g for g in getattr(geometry, "geoms", []) if isinstance(g, Polygon)]


@deal.post(lambda result: result == "" or (result.startswith("M") and result.endswith("Z")))
def svg_path(geometry: BaseGeometry, projection: Projection) -> str:
    """``d``-Attribut mit zwei Nachkommastellen; Löcher als eigene Ringe, Füllung per ``evenodd``."""
    parts: list[str] = []
    for polygon in _polygons(geometry):
        for ring in (polygon.exterior, *polygon.interiors):
            points = [projection.point(x, y) for x, y in ring.coords[:-1]]
            parts.append("M" + " ".join(f"{x:.2f},{y:.2f}" for x, y in points) + "Z")
    return "".join(parts)


def label_point(geometry: BaseGeometry, projection: Projection) -> tuple[float, float]:
    """Ein Punkt im größten Polygon, für die Nummer auf der Karte."""
    largest = max(_polygons(geometry), key=lambda p: p.area)
    x, y = largest.representative_point().coords[0]
    return projection.point(float(x), float(y))


def _rounded(value: object, decimals: int) -> object:
    if isinstance(value, float):
        return round(value, decimals)
    if isinstance(value, tuple | list):
        return [_rounded(v, decimals) for v in value]
    return value


@deal.pre(
    lambda shapes, rows, working_crs: set(shapes) <= {r.id for r in rows},
    message="jede Fläche hat eine Zeile der Auswertung",
)
@deal.ensure(
    lambda shapes, rows, working_crs, result: (
        isinstance(result["features"], list) and len(result["features"]) == len(shapes)
    )
)
def wahlbezirke_geojson(
    shapes: Mapping[int, BaseGeometry], rows: Sequence[DistrictRow], working_crs: str
) -> dict[str, object]:
    """FeatureCollection in EPSG:4326 (RFC 7946, darum ohne ``crs``-Mitglied), sechs Nachkommastellen."""
    by_id = {row.id: row for row in rows}
    features: list[dict[str, object]] = []
    for district, geometry in sorted(shapes.items()):
        row = by_id[district]
        lonlat = dict(mapping(to_lonlat(geometry, working_crs)))
        lonlat["coordinates"] = _rounded(lonlat["coordinates"], GEOJSON_DECIMALS)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "wahlkreis_id": row.id,
                    "name": row.name,
                    "anzahl_treffer": row.hits,
                    "trefferquote": row.rate,
                    "wahlbeteiligung": row.turnout,
                },
                "geometry": lonlat,
            }
        )
    return {
        "type": "FeatureCollection",
        "name": "Kommunalwahlbezirke Düsseldorf 2025",
        "features": features,
    }
