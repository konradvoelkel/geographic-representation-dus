"""Geo-Schicht gegen die Referenz: Stimmbezirke lesen, Orte zuordnen wie die Arbeit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from georep.geo import (
    Precinct,
    PrecinctIndex,
    lonlat_bounds,
    overpass_polygon,
    read_precincts,
    to_lonlat,
)
from georep.settings import Settings, load_settings


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


@pytest.fixture(scope="module")
def precincts(reference_root: Path, settings: Settings) -> list[Precinct]:
    return read_precincts(
        reference_root / "external" / "Stimmbezirke_2025.geojson",
        settings.columns,
        settings.geo.working_crs,
    )


def test_reference_geojson_reads_306_valid_precincts_in_41_districts(
    precincts: list[Precinct],
) -> None:
    assert len(precincts) == 306
    assert len({p.district_id for p in precincts}) == 41
    assert all(p.geometry.is_valid for p in precincts)
    # EPSG:25832 statt 4647: Rechtswerte ohne Zonenpräfix, Düsseldorf um 340 km Ost, 5,67 Mm Nord
    x, y = precincts[0].geometry.centroid.coords[0]
    assert 330_000 < x < 360_000 and 5_660_000 < y < 5_700_000


def test_lonlat_bounds_and_overpass_polygon(precincts: list[Precinct], settings: Settings) -> None:
    first = precincts[0]
    min_lon, min_lat, max_lon, max_lat = lonlat_bounds(first.geometry, settings.geo.working_crs)
    assert 6.6 < min_lon < max_lon < 6.95 and 51.1 < min_lat < max_lat < 51.4
    poly = overpass_polygon(first.geometry, settings.geo.working_crs, tolerance_m=5)
    coords = poly.split()
    assert len(coords) % 2 == 0 and len(coords) >= 8
    assert 51.1 < float(coords[0]) < 51.4 and 6.6 < float(coords[1]) < 6.95  # lat zuerst
    assert len(overpass_polygon(first.geometry, settings.geo.working_crs)) >= len(poly)


def test_index_assigns_reference_pois_like_the_thesis(
    precincts: list[Precinct], reference_root: Path, settings: Settings
) -> None:
    """Die Arbeit hat 2010 Orte mit geopandas.contains in EPSG:4326 zugeordnet; der STRtree im
    metrischen CRS muss dieselbe Zuordnung liefern. Randfälle (Punkt exakt auf einer Grenze)
    dürfen abweichen, gemessen am 2026-10-11: null."""
    index = PrecinctIndex(precincts, settings.geo.working_crs)
    pois = json.loads((reference_root / "raw" / "wikipedia_dict.json").read_text(encoding="utf-8"))
    assigned = [p for p in pois if p.get("wahlkreis_id") is not None]
    unassigned = [p for p in pois if p.get("wahlkreis_id") is None]
    assert len(assigned) == 1996 and len(unassigned) == 14
    mismatches = [
        (p["label"], p["stimmbezirk_id"], hit.precinct_id if hit else None)
        for p in assigned
        if (hit := index.locate(p["lon"], p["lat"])) is None
        or int(hit.precinct_id)
        != int(p["stimmbezirk_id"])  # die Arbeit speicherte 202, das GeoJSON sagt "0202"
        or hit.district_id != int(p["wahlkreis_id"])
    ]
    assert mismatches == []
    assert all(index.locate(p["lon"], p["lat"]) is None for p in unassigned)


def test_locate_outside_returns_none(precincts: list[Precinct], settings: Settings) -> None:
    index = PrecinctIndex(precincts, settings.geo.working_crs)
    assert index.locate(13.4, 52.5) is None  # Berlin
    kunstakademie = index.locate(6.77365, 51.23054)
    assert kunstakademie is not None and kunstakademie.district_id == 1


def test_to_lonlat_roundtrip(settings: Settings) -> None:
    square = Polygon([(340000, 5670000), (341000, 5670000), (341000, 5671000), (340000, 5671000)])
    lonlat = to_lonlat(square, settings.geo.working_crs)
    assert 6.7 < lonlat.centroid.x < 6.9 and 51.1 < lonlat.centroid.y < 51.3
