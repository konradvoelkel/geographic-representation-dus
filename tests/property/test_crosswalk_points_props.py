"""Invarianten von ``point_shares`` für beliebige Punkte über einem Gitter von Stimmbezirken.

Vorhaben 22 (``docs/plans/22-bedarf.md``, § 6): je Punkt summieren die Anteile zu 1, die Summe über
alle Wahlbezirke ist die Zahl der Punkte im Band, Band 0 ist Punkt in Fläche, und ein breiteres
Band verliert keinen Wahlbezirk eines schmaleren. Das Orakel ist ``shapely.distance`` über die
**Eingabepunkte**, nicht über die Punkte, die die Funktion selbst ausgibt (Review 2026-11-24, N11):
ein Punkt, den sie still verlöre, fiele sonst nicht auf. Neben dem Gitter ein Stimmbezirk mit Loch
und einer Insel darin.
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

# Ein Stimmbezirk mit Loch (100 bis 200 m) und darin ein kleinerer (120 bis 180 m), 20 m Luft
# dazwischen: ein Punkt im Loch liegt in keiner der beiden Flächen, ein Band erreicht den Ring auch von
# innen (Review 2026-11-24, N11).
RING = shapely.Polygon(
    [(0, 0), (300, 0), (300, 300), (0, 300)], [[(100, 100), (200, 100), (200, 200), (100, 200)]]
)
HOLED = [Precinct("R", 1, "W1", RING), Precinct("I", 2, "W2", box(120, 120, 180, 180))]
layouts = st.sampled_from([GRID, HOLED])

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


def _within(
    coords: list[tuple[float, float]], layout: list[Precinct], band: float
) -> dict[int, list[int]]:
    """Das Orakel: je Eingabepunkt die Wahlbezirke, deren Fläche höchstens ``band`` entfernt ist."""
    return {
        index: sorted(
            {p.district_id for p in layout if p.geometry.distance(shapely.Point(x, y)) <= band}
        )
        for index, (x, y) in enumerate(coords)
    }


def _frame(coords: list[tuple[float, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        {POINT: list(range(len(coords))), "x": [c[0] for c in coords], "y": [c[1] for c in coords]},
        schema={POINT: pl.Int64, "x": pl.Float64, "y": pl.Float64},
    )


@given(coords=points, band=bands, layout=layouts)
def test_the_shares_of_each_point_sum_to_one(
    coords: list[tuple[float, float]], band: float, layout: list[Precinct]
) -> None:
    shares = point_shares(_frame(coords), layout, band_m=band)
    sums = shares.group_by(POINT).agg(pl.col(POINT_SHARE).sum()).get_column(POINT_SHARE)
    assert sums.to_list() == pytest.approx([1.0] * sums.len())
    assert bool(
        ((shares.get_column(POINT_SHARE) > 0) & (shares.get_column(POINT_SHARE) <= 1)).all()
    )
    # Über alle Wahlbezirke ist die Summe die Zahl der Eingabepunkte, die im Band einen haben.
    reached = {index for index, districts in _within(coords, layout, band).items() if districts}
    assert set(shares.get_column(POINT)) == reached
    assert float(shares.get_column(POINT_SHARE).sum()) == pytest.approx(len(reached))


@given(coords=points, layout=layouts)
def test_band_zero_is_point_in_polygon(
    coords: list[tuple[float, float]], layout: list[Precinct]
) -> None:
    shares = point_shares(_frame(coords), layout, band_m=0.0)
    for index, (x, y) in enumerate(coords):
        point = shapely.Point(x, y)
        expected = sorted({p.district_id for p in layout if p.geometry.intersects(point)})
        found = shares.filter(pl.col(POINT) == index).get_column("wahlkreis_id").to_list()
        assert found == expected, (x, y)


@given(coords=points, band=bands, layout=layouts)
def test_the_band_is_the_set_of_districts_within_that_distance(
    coords: list[tuple[float, float]], band: float, layout: list[Precinct]
) -> None:
    shares = point_shares(_frame(coords), layout, band_m=band)
    for index, expected in _within(coords, layout, band).items():
        found = shares.filter(pl.col(POINT) == index).get_column("wahlkreis_id").to_list()
        assert found == expected, (coords[index], band)


@pytest.mark.parametrize(
    ("x", "y", "band", "expected"),
    [
        (150.0, 150.0, 0.0, [2]),  # auf der Insel
        (110.0, 150.0, 0.0, []),  # im Loch, je 10 m vom Ring und von der Insel
        (110.0, 150.0, 5.0, []),
        (110.0, 150.0, 10.0, [1, 2]),  # das Band erreicht den Ring von innen und die Insel
        (105.0, 150.0, 5.0, [1]),  # 5 m vom Ring, 15 m von der Insel
        (100.0, 150.0, 0.0, [1]),  # auf dem inneren Rand: in der geschlossenen Fläche
    ],
)
def test_a_point_in_the_hole_belongs_to_the_ring_only_within_the_band(
    x: float, y: float, band: float, expected: list[int]
) -> None:
    shares = point_shares(_frame([(x, y)]), HOLED, band_m=band)
    assert shares.get_column("wahlkreis_id").to_list() == expected


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
