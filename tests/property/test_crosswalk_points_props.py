"""Invarianten von ``point_shares`` für beliebige Punkte über einem Gitter von Stimmbezirken.

Vorhaben 22 (``docs/plans/22-bedarf.md``, § 6): je Punkt summieren die Anteile zu 1, die Summe über
alle Wahlbezirke ist die Zahl der Punkte im Band, Band 0 ist Punkt in Fläche, und ein breiteres
Band verliert keinen Wahlbezirk eines schmaleren.
"""

from __future__ import annotations

import polars as pl
import pytest
import shapely
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import box

from georep.crosswalk import POINT, POINT_SHARE, point_shares
from georep.geo import Precinct

# Ein Gitter von 3 × 3 Stimmbezirken zu 100 m; der Wahlbezirk ist die Spalte (drei Wahlbezirke aus
# je drei Stimmbezirken), damit innere Grenzen eines Wahlbezirks vorkommen.
GRID = [
    Precinct(f"{col}{row}", col + 1, f"W{col + 1}", box(100 * col, 100 * row, 100 * (col + 1), 100 * (row + 1)))
    for col in range(3)
    for row in range(3)
]  # fmt: skip

# Koordinaten auf einem 10-m-Raster treffen Grenzen und Ecken oft; dazu beliebige auf Millimeter.
# Auf Millimeter, weil das Orakel ``distance`` bei 1e-188 unterläuft (das Quadrat wird 0, der
# Abstand 0), während ``intersects`` exakt rechnet: hypothesis fand am 2026-11-24 den Punkt
# (0, -1,2e-188), den das Orakel in Wahlbezirk 1 sah und die Funktion zu Recht nicht. Karten haben
# keine Koordinaten unter einem Millimeter.
coordinate = st.one_of(
    st.integers(min_value=-5, max_value=35).map(lambda k: 10.0 * k),
    st.floats(min_value=-50.0, max_value=350.0, allow_nan=False).map(lambda v: round(v, 3)),
)
points = st.lists(st.tuples(coordinate, coordinate), max_size=30)
bands = st.sampled_from([0.0, 0.5, 5.0, 20.0, 60.0])


def _frame(coords: list[tuple[float, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        {POINT: list(range(len(coords))), "x": [c[0] for c in coords], "y": [c[1] for c in coords]},
        schema={POINT: pl.Int64, "x": pl.Float64, "y": pl.Float64},
    )


@given(coords=points, band=bands)
def test_the_shares_of_each_point_sum_to_one(
    coords: list[tuple[float, float]], band: float
) -> None:
    shares = point_shares(_frame(coords), GRID, band_m=band)
    sums = shares.group_by(POINT).agg(pl.col(POINT_SHARE).sum()).get_column(POINT_SHARE)
    assert sums.to_list() == pytest.approx([1.0] * sums.len())
    assert bool(
        ((shares.get_column(POINT_SHARE) > 0) & (shares.get_column(POINT_SHARE) <= 1)).all()
    )
    # Über alle Wahlbezirke ist die Summe die Zahl der Punkte, die im Band einen haben.
    assert float(shares.get_column(POINT_SHARE).sum()) == pytest.approx(
        shares.get_column(POINT).n_unique()
    )


@given(coords=points)
def test_band_zero_is_point_in_polygon(coords: list[tuple[float, float]]) -> None:
    shares = point_shares(_frame(coords), GRID, band_m=0.0)
    for index, (x, y) in enumerate(coords):
        point = shapely.Point(x, y)
        expected = sorted({p.district_id for p in GRID if p.geometry.intersects(point)})
        found = shares.filter(pl.col(POINT) == index).get_column("wahlkreis_id").to_list()
        assert found == expected, (x, y)


@given(coords=points, band=bands)
def test_the_band_is_the_set_of_districts_within_that_distance(
    coords: list[tuple[float, float]], band: float
) -> None:
    shares = point_shares(_frame(coords), GRID, band_m=band)
    for index, (x, y) in enumerate(coords):
        point = shapely.Point(x, y)
        expected = sorted({p.district_id for p in GRID if p.geometry.distance(point) <= band})
        found = shares.filter(pl.col(POINT) == index).get_column("wahlkreis_id").to_list()
        assert found == expected, (x, y, band)


@given(coords=points, narrow=bands, wide=bands)
def test_a_wider_band_keeps_every_district_of_a_narrower(
    coords: list[tuple[float, float]], narrow: float, wide: float
) -> None:
    narrow, wide = min(narrow, wide), max(narrow, wide)
    small = set(
        point_shares(_frame(coords), GRID, band_m=narrow).select(POINT, "wahlkreis_id").rows()
    )
    large = set(
        point_shares(_frame(coords), GRID, band_m=wide).select(POINT, "wahlkreis_id").rows()
    )
    assert small <= large


@given(coords=points)
def test_by_precinct_and_by_district_cover_the_same_points(
    coords: list[tuple[float, float]],
) -> None:
    frame = _frame(coords)
    districts = point_shares(frame, GRID, band_m=5.0)
    precincts = point_shares(frame, GRID, band_m=5.0, unit="stimmbezirk_id")
    assert set(districts.get_column(POINT)) == set(precincts.get_column(POINT))
