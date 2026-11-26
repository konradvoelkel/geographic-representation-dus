"""Punkte auf Wahlbezirke: die scharfe Zuordnung (Band 0) und das Randband an Handbeispielen.

Vorhaben 22 (``docs/plans/22-bedarf.md``, § 3.1 und § 10, Punkt 4): der Unfallatlas legt einen
Unfall auf die Straßenachse, und Wahlbezirksgrenzen laufen oft auf Straßenmitten. Ein Punkt im
Band um eine Grenze geht darum zu gleichen Teilen an jeden Wahlbezirk, der im Band liegt.
"""

from __future__ import annotations

import deal
import polars as pl
import pytest
from shapely.geometry import box

from georep.crosswalk import POINT, POINT_SHARE, point_shares
from georep.geo import Precinct

# Zwei Wahlbezirke nebeneinander, Quadrate von 100 m: 1 links, 2 rechts; 2 aus zwei Stimmbezirken.
LEFT = Precinct("0101", 1, "Links", box(0, 0, 100, 100))
RIGHT_LOW = Precinct("0201", 2, "Rechts", box(100, 0, 200, 50))
RIGHT_HIGH = Precinct("0202", 2, "Rechts", box(100, 50, 200, 100))
PRECINCTS = [LEFT, RIGHT_LOW, RIGHT_HIGH]


def _points(*coords: tuple[float, float]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            POINT: list(range(len(coords))),
            "x": [float(x) for x, _ in coords],
            "y": [float(y) for _, y in coords],
        },
        schema={POINT: pl.Int64, "x": pl.Float64, "y": pl.Float64},
    )


def test_a_point_inside_goes_whole_to_its_district() -> None:
    shares = point_shares(_points((30, 30)), PRECINCTS)
    assert shares.columns == [POINT, "wahlkreis_id", POINT_SHARE]
    assert shares.rows() == [(0, 1, 1.0)]
    assert shares.schema == {POINT: pl.Int64, "wahlkreis_id": pl.Int64, POINT_SHARE: pl.Float64}


def test_a_point_on_the_shared_edge_is_split_in_half_even_at_band_zero() -> None:
    shares = point_shares(_points((100, 30)), PRECINCTS)
    assert shares.rows() == [(0, 1, 0.5), (0, 2, 0.5)]


def test_a_point_outside_every_district_is_missing() -> None:
    shares = point_shares(_points((30, 30), (500, 500)), PRECINCTS, band_m=20.0)
    assert shares.get_column(POINT).to_list() == [0]


def test_the_band_splits_a_point_near_the_edge_and_only_there() -> None:
    points = _points((90, 30), (70, 30), (110, 75))
    sharp = point_shares(points, PRECINCTS, band_m=0.0)
    assert sharp.rows() == [(0, 1, 1.0), (1, 1, 1.0), (2, 2, 1.0)]
    banded = point_shares(points, PRECINCTS, band_m=20.0)
    assert banded.rows() == [(0, 1, 0.5), (0, 2, 0.5), (1, 1, 1.0), (2, 1, 0.5), (2, 2, 0.5)]


def test_two_precincts_of_one_district_do_not_split_the_district_share() -> None:
    """Gleiche Teile je Wahlbezirk, nicht je Stimmbezirk: der Punkt auf der inneren Grenze von 2."""
    shares = point_shares(_points((150, 50)), PRECINCTS, band_m=5.0)
    assert shares.rows() == [(0, 2, 1.0)]


def test_by_precinct_the_same_point_is_split_between_the_precincts() -> None:
    shares = point_shares(_points((150, 50)), PRECINCTS, band_m=0.0, unit="stimmbezirk_id")
    assert shares.columns == [POINT, "stimmbezirk_id", POINT_SHARE]
    assert shares.rows() == [(0, "0201", 0.5), (0, "0202", 0.5)]


def test_a_corner_of_three_precincts_splits_in_thirds_by_precinct() -> None:
    shares = point_shares(_points((100, 50)), PRECINCTS, unit="stimmbezirk_id")
    assert shares.get_column("stimmbezirk_id").to_list() == ["0101", "0201", "0202"]
    assert shares.get_column(POINT_SHARE).to_list() == pytest.approx([1 / 3] * 3)
    by_district = point_shares(_points((100, 50)), PRECINCTS)
    assert by_district.rows() == [(0, 1, 0.5), (0, 2, 0.5)]


def test_rows_are_sorted_by_point_and_district_whatever_the_input_order() -> None:
    points = _points((150, 20), (30, 30), (100, 30)).reverse()
    shares = point_shares(points, PRECINCTS)
    keys = shares.select(POINT, "wahlkreis_id").rows()
    assert keys == sorted(keys)


def test_no_points_give_an_empty_frame_with_the_schema() -> None:
    shares = point_shares(_points(), PRECINCTS, band_m=20.0)
    assert shares.height == 0
    assert shares.schema == {POINT: pl.Int64, "wahlkreis_id": pl.Int64, POINT_SHARE: pl.Float64}


def test_a_negative_band_breaks_the_contract() -> None:
    with pytest.raises(deal.PreContractError):
        point_shares(_points((30, 30)), PRECINCTS, band_m=-1.0)


def test_a_point_twice_breaks_the_contract() -> None:
    twice = pl.concat([_points((30, 30)), _points((60, 60))])
    with pytest.raises(deal.PreContractError):
        point_shares(twice, PRECINCTS)


def test_a_missing_coordinate_breaks_the_contract() -> None:
    broken = _points((30, 30)).with_columns(pl.lit(None, dtype=pl.Float64).alias("x"))
    with pytest.raises(deal.PreContractError):
        point_shares(broken, PRECINCTS)
