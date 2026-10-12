"""Geometrie ohne geopandas: shapely, pyproj, STRtree.

Ein metrisches Arbeits-CRS, genau eine Stelle, die nach lon/lat zurückprojiziert (``to_lonlat``),
``always_xy=True`` überall, ``make_valid`` statt ``buffer(0)`` (Lehren aus bubatzblick,
docs/decisions.md, Punkt 7). Die Stimmbezirke kommen als GeoJSON in EPSG:4647 vom Open-Data-Portal.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import deal
import numpy as np
import numpy.typing as npt
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

from georep.errors import SchemaError
from georep.settings import Columns

LONLAT = "EPSG:4326"


@dataclass(frozen=True)
class Precinct:
    """Ein Stimmbezirk mit Geometrie im Arbeits-CRS."""

    precinct_id: str
    district_id: int
    district_name: str
    geometry: BaseGeometry


@dataclass(frozen=True)
class Area:
    """Eine Fläche mit Schlüssel im Arbeits-CRS: eine Raumeinheit der Stadt, ein Stimmbezirk.

    Der allgemeine Fall von ``Precinct`` für die Umrechnung von Gebietseinheiten
    (``georep.crosswalk``): ein Schlüssel als Text, weil die Schlüssel der Quellen führende
    Nullen tragen (``011001``), und eine reparierte Geometrie.
    """

    key: str
    geometry: BaseGeometry

    @classmethod
    def of(cls, precinct: Precinct) -> Area:
        return cls(precinct.precinct_id, precinct.geometry)


def transformer(source: str | CRS, target: str | CRS) -> Transformer:
    return Transformer.from_crs(
        CRS.from_user_input(source), CRS.from_user_input(target), always_xy=True
    )


def project(geometry: BaseGeometry, trans: Transformer) -> BaseGeometry:
    def convert(coords: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        x, y = trans.transform(coords[:, 0], coords[:, 1])
        return np.column_stack((x, y))

    return shapely.transform(geometry, convert)


def geojson_crs(collection: dict[str, object], default: str) -> str:
    """CRS-Angabe einer FeatureCollection (``urn:ogc:def:crs:EPSG::4647``), sonst ``default``."""
    crs = collection.get("crs")
    if isinstance(crs, dict):
        props = crs.get("properties")
        if isinstance(props, dict) and isinstance(props.get("name"), str):
            return str(props["name"])
    return default


def _features(
    path: Path, working_crs: str, source_crs: str
) -> tuple[list[dict[str, Any]], Transformer]:
    """Die Features einer FeatureCollection und der Transformer von ihrem CRS ins Arbeits-CRS."""
    collection = json.loads(path.read_text(encoding="utf-8"))
    features = collection.get("features")
    if not isinstance(features, list) or not features:
        raise SchemaError(f"{path.name}: keine Features")
    return features, transformer(geojson_crs(collection, source_crs), working_crs)


# Option 02: Der alte Wahlbezirkszuschnitt trägt neben der Nummer einen Namen; ``Area`` hält
# bewusst nur den Schlüssel (Option 03), darum liest diese Funktion die Namen als eigene
# Abbildung. Ein Name ist Anzeige, keine Geometrie -- er gehört nicht in den Crosswalk.
@deal.raises(SchemaError)
def read_area_names(path: Path, key_property: str, name_property: str) -> dict[str, str]:
    """Kennung -> Name aus den Eigenschaften eines GeoJSON, ohne Geometrie und ohne Projektion."""
    collection = json.loads(path.read_text(encoding="utf-8"))
    features = collection.get("features")
    if not isinstance(features, list) or not features:
        raise SchemaError(f"{path.name}: keine Features")
    names: dict[str, str] = {}
    for feature in features:
        props = feature.get("properties") or {}
        missing = [c for c in (key_property, name_property) if c not in props]
        if missing:
            raise SchemaError(f"{path.name}: Felder fehlen: {missing}")
        names[str(props[key_property])] = str(props[name_property])
    return names


@deal.post(
    lambda result: (
        len(result) > 0 and all(p.geometry.is_valid and not p.geometry.is_empty for p in result)
    ),
    message="jeder Stimmbezirk hat eine gültige, nicht leere Fläche",
)
def read_precincts(
    path: Path, columns: Columns, working_crs: str, *, source_crs: str = LONLAT
) -> list[Precinct]:
    """Liest das Stimmbezirks-GeoJSON, repariert ungültige Geometrien, projiziert ins Arbeits-CRS."""
    features, trans = _features(path, working_crs, source_crs)
    precincts: list[Precinct] = []
    for feature in features:
        props = feature.get("properties", {})
        missing = [
            c
            for c in (columns.precinct_id, columns.district_id, columns.district_name)
            if c not in props
        ]
        if missing:
            raise SchemaError(f"{path.name}: Felder fehlen: {missing}")
        precincts.append(
            Precinct(
                precinct_id=str(props[columns.precinct_id]),
                district_id=int(props[columns.district_id]),
                district_name=str(props[columns.district_name]),
                geometry=repaired(project(shape(feature["geometry"]), trans)),
            )
        )
    return precincts


@deal.post(
    lambda result: (
        len(result) > 0
        and all(a.geometry.is_valid and not a.geometry.is_empty for a in result)
        and len({a.key for a in result}) == len(result)
    ),
    message="jede Fläche hat einen eigenen Schlüssel und eine gültige, nicht leere Geometrie",
)
@deal.raises(SchemaError)
def read_areas(
    path: Path, key_property: str, working_crs: str, *, source_crs: str = LONLAT
) -> list[Area]:
    """Flächen mit Schlüssel aus einem GeoJSON, projiziert ins Arbeits-CRS.

    Wie ``read_precincts``, aber ohne Annahmen über weitere Eigenschaften: eine beliebige
    Gebietsgliederung (Raumeinheiten der Stadt, ein älterer Zuschnitt) wird so zur Eingabe von
    ``georep.crosswalk``. ``source_crs`` gilt nur, wenn die Datei kein ``crs`` nennt.
    """
    collection = json.loads(path.read_text(encoding="utf-8"))
    features = collection.get("features")
    if not isinstance(features, list) or not features:
        raise SchemaError(f"{path.name}: keine Features")
    trans = transformer(geojson_crs(collection, source_crs), working_crs)
    areas: list[Area] = []
    for feature in features:
        props = feature.get("properties", {})
        if key_property not in props:
            raise SchemaError(f"{path.name}: Eigenschaft {key_property!r} fehlt")
        areas.append(
            Area(str(props[key_property]), repaired(project(shape(feature["geometry"]), trans)))
        )
    keys = [a.key for a in areas]
    if len(set(keys)) != len(keys):
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        raise SchemaError(f"{path.name}: {key_property} doppelt: {duplicates}")
    return areas


def repaired(geometry: BaseGeometry) -> BaseGeometry:
    """``make_valid`` nach der Projektion (Fließkomma-Rauschen der Transformation), nur Flächen.

    Die Stimmbezirke aus dem Portal haben Selbstberührungen; ``make_valid`` liefert dann eine
    GeometryCollection aus Polygonen und Linien. Die Linien tragen keine Fläche und fallen weg,
    wie im ``repair_geometry`` der Arbeit. Nie ``buffer(0)``: das füllt Höfe (bubatzblick).
    """
    if geometry.is_valid:
        return geometry
    fixed = make_valid(geometry)
    if isinstance(fixed, Polygon | MultiPolygon):
        return fixed
    parts = [g for g in getattr(fixed, "geoms", []) if isinstance(g, Polygon | MultiPolygon)]
    polygons = [
        p for part in parts for p in (part.geoms if isinstance(part, MultiPolygon) else [part])
    ]
    if not polygons:
        raise SchemaError(f"Geometrie ohne Fläche nach make_valid: {fixed.geom_type}")
    return polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)


class PrecinctIndex:
    """Punkt (lon, lat) -> Stimmbezirk, über einen STRtree statt einer Schleife über 306 Polygone."""

    def __init__(self, precincts: Sequence[Precinct], working_crs: str) -> None:
        self.precincts = list(precincts)
        self._tree = shapely.STRtree([p.geometry for p in self.precincts])
        self._to_working = transformer(LONLAT, working_crs)

    @deal.pre(
        lambda self, lon, lat: -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0,
        message="lon/lat außerhalb des Wertebereichs: vertauscht? (always_xy)",
    )
    def locate(self, lon: float, lat: float) -> Precinct | None:
        x, y = self._to_working.transform(lon, lat)
        hits = self._tree.query(shapely.Point(x, y), predicate="within")
        return self.precincts[int(hits[0])] if len(hits) else None

    def locate_many(self, points: Iterable[tuple[float, float]]) -> list[Precinct | None]:
        return [self.locate(lon, lat) for lon, lat in points]


def to_lonlat(geometry: BaseGeometry, working_crs: str) -> BaseGeometry:
    """Die eine Rückprojektion nach lon/lat: für Bounding Boxes und Overpass-Polygone."""
    return project(geometry, transformer(working_crs, LONLAT))


@deal.post(
    lambda result: (
        -180.0 <= result[0] <= result[2] <= 180.0 and -90.0 <= result[1] <= result[3] <= 90.0
    ),
    message="(min_lon, min_lat, max_lon, max_lat) in Grad",
)
def lonlat_bounds(geometry: BaseGeometry, working_crs: str) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) wie ``shapely.bounds`` im Altcode."""
    minx, miny, maxx, maxy = to_lonlat(geometry, working_crs).bounds
    return (float(minx), float(miny), float(maxx), float(maxy))


@deal.pre(
    lambda geometry, working_crs, tolerance_m=0.0: tolerance_m >= 0 and not geometry.is_empty,
    message="Toleranz nicht negativ, Geometrie nicht leer",
)
@deal.post(
    lambda result: (
        len(result.split()) >= 8
        and len(result.split()) % 2 == 0
        and all(-90.0 <= float(v) <= 90.0 for v in result.split()[0::2])
        and all(-180.0 <= float(v) <= 180.0 for v in result.split()[1::2])
    ),
    message="geschlossener Ring aus mindestens vier lat-lon-Paaren in Grad",
)
@deal.raises(SchemaError)
def overpass_polygon(geometry: BaseGeometry, working_crs: str, tolerance_m: float = 0.0) -> str:
    """Außenring des größten Polygons als ``lat lon lat lon …`` für ``(poly:"…")`` in Overpass.

    ``tolerance_m`` vereinfacht vorher im Arbeits-CRS (Douglas-Peucker), damit die Abfrage kurz bleibt.
    """
    simplified = geometry.simplify(tolerance_m) if tolerance_m > 0 else geometry
    polygons = list(simplified.geoms) if hasattr(simplified, "geoms") else [simplified]
    largest = to_lonlat(max(polygons, key=lambda p: p.area), working_crs)
    if not isinstance(largest, Polygon):
        raise SchemaError(f"Overpass-Polygon braucht ein Polygon, nicht {largest.geom_type}")
    return " ".join(f"{lat:.6f} {lon:.6f}" for lon, lat in largest.exterior.coords)
