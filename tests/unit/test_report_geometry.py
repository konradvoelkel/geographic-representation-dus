"""Wahlbezirksflächen, SVG-Pfade und GeoJSON der Berichtsseite."""

from __future__ import annotations

import math
import re
from pathlib import Path

import deal
import pytest
import shapely
from shapely.geometry import MultiPolygon, Polygon, box

from georep.geo import Precinct, read_canonical_precincts
from georep.report.geometry import (
    Projection,
    bounds_of,
    district_shapes,
    fit,
    label_point,
    svg_path,
    wahlbezirke_geojson,
)
from georep.report.model import DistrictRow
from georep.settings import Settings


@pytest.fixture(scope="module")
def precincts(mini_precincts: Path, default_settings: Settings) -> list[Precinct]:
    return read_canonical_precincts(mini_precincts, default_settings.geo.working_crs)


def _row(district: int, name: str = "Bezirk") -> DistrictRow:
    return DistrictRow(district, name, 10, 1000, 500, 0.5, 0.01, 3, 1, (), ())


def test_district_shapes_unite_the_precincts(precincts: list[Precinct]) -> None:
    shapes = district_shapes(precincts)
    assert sorted(shapes) == [1, 10, 38]
    assert all(g.is_valid and not g.is_empty for g in shapes.values())
    before = sum(p.geometry.area for p in precincts)
    assert sum(g.area for g in shapes.values()) == pytest.approx(before, rel=0.01)
    raw = district_shapes(precincts, tolerance_m=0)
    assert all(
        shapely.get_num_coordinates(shapes[d]) < shapely.get_num_coordinates(raw[d]) for d in shapes
    )


def test_district_shapes_on_the_full_reference(
    reference_precincts: Path, default_settings: Settings
) -> None:
    precincts = read_canonical_precincts(reference_precincts, default_settings.geo.working_crs)
    shapes = district_shapes(precincts)
    assert len(shapes) == 41
    assert sum(shapely.get_num_coordinates(g) for g in shapes.values()) < 3000


def test_district_shapes_refuse_negative_tolerance(precincts: list[Precinct]) -> None:
    with pytest.raises(deal.PreContractError):
        district_shapes(precincts, tolerance_m=-1)


def test_fit_keeps_the_aspect_ratio_and_flips_y() -> None:
    projection = fit((100.0, 200.0, 300.0, 300.0), width=400.0)
    assert projection.view_box == "0 0 400.00 200.00"
    assert projection.point(100.0, 300.0) == (0.0, 0.0)  # Nordwestecke oben links
    assert projection.point(300.0, 200.0) == (400.0, 200.0)
    with pytest.raises(deal.PreContractError):
        fit((0.0, 0.0, 0.0, 1.0), width=10.0)


def test_an_infinite_bound_is_no_bounding_box() -> None:
    """crosshair, 2026-10-13: ``fit((-1.0, 0.0, inf, 1.0), 1.0)`` lieferte Skala und Höhe 0.

    ``width / (max_x - min_x)`` ist bei einer unendlichen Grenze 0, und die Nachbedingung „Höhe und
    Skala positiv" brach daran. Dieselbe Lehre wie bei ``nice_ticks`` am 2026-10-12: eine
    Vorbedingung über Grenzen muss sagen, dass sie endlich sind.
    """
    for bounds in (
        (-1.0, 0.0, math.inf, 1.0),
        (-math.inf, 0.0, 1.0, 1.0),
        (0.0, -math.inf, 1.0, 1.0),
        (0.0, 0.0, 1.0, math.inf),
        (0.0, 0.0, math.nan, 1.0),
    ):
        with pytest.raises(deal.PreContractError):
            fit(bounds, width=10.0)
    with pytest.raises(deal.PreContractError):
        fit((0.0, 0.0, 1.0, 1.0), width=math.inf)


def test_svg_path_writes_rings_with_two_decimals() -> None:
    projection = Projection(0.0, 10.0, 1.0, 10.0, 10.0)
    outer = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], holes=[[(4, 4), (6, 4), (6, 6), (4, 6)]])
    path = svg_path(outer, projection)
    assert path.count("M") == 2 and path.count("Z") == 2
    assert path.startswith("M0.00,10.00 10.00,10.00 10.00,0.00 0.00,0.00Z")
    assert svg_path(MultiPolygon([outer, box(20, 20, 21, 21)]), projection).count("M") == 3
    assert all(math.isfinite(float(n)) for n in re.findall(r"-?\d+\.\d+", path))


def test_label_point_lies_in_the_largest_polygon() -> None:
    projection = Projection(0.0, 100.0, 1.0, 100.0, 100.0)
    shape = MultiPolygon([box(0, 0, 10, 10), box(50, 50, 90, 90)])
    x, y = label_point(shape, projection)
    assert 50 <= x <= 90 and 10 <= y <= 50


def test_geojson_is_lonlat_with_the_district_properties(
    precincts: list[Precinct], default_settings: Settings
) -> None:
    shapes = district_shapes(precincts)
    rows = [_row(1, "Eins"), _row(10, "Zehn"), _row(38, "Achtunddreißig")]
    collection = wahlbezirke_geojson(shapes, rows, default_settings.geo.working_crs)
    features = collection["features"]
    assert isinstance(features, list) and len(features) == 3
    assert "crs" not in collection
    first = features[0]
    assert first["properties"] == {
        "wahlkreis_id": 1,
        "name": "Eins",
        "anzahl_treffer": 10,
        "trefferquote": 0.01,
        "wahlbeteiligung": 0.5,
    }
    coords = str(first["geometry"]["coordinates"])
    numbers = [float(n) for n in re.findall(r"-?\d+\.\d+", coords)]
    lons, lats = numbers[0::2], numbers[1::2]
    assert all(6.6 < lon < 6.95 for lon in lons) and all(51.1 < lat < 51.4 for lat in lats)
    assert all(len(str(n).split(".")[1]) <= 6 for n in numbers)
    with pytest.raises(deal.PreContractError):
        wahlbezirke_geojson(shapes, rows[:2], default_settings.geo.working_crs)


def test_bounds_of_spans_all_shapes() -> None:
    shapes = {1: box(0, 0, 1, 1), 2: box(5, 5, 6, 7)}
    assert bounds_of(shapes) == (0.0, 0.0, 6.0, 7.0)
