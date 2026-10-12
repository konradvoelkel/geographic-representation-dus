"""Der geometrische Crosswalk an Handbeispielen: Flächenanteile und Gewichte je Wahlbezirk."""

from __future__ import annotations

import polars as pl
import pytest
from shapely.geometry import box

from georep.crosswalk import area_shares, district_weights, unit_weights
from georep.errors import SchemaError
from georep.geo import Area

# Zwei Zielflächen nebeneinander, Einheitsquadrate: A links, B rechts.
A = Area("A", box(0, 0, 1, 1))
B = Area("B", box(1, 0, 2, 1))


def _table(rows: list[tuple[str, int, int]]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={"stimmbezirk_id": pl.String, "wahlkreis_id": pl.Int64, "wahlberechtigte": pl.Int64},
        orient="row",
    )


def test_a_source_across_two_targets_splits_in_half() -> None:
    half = Area("p1", box(0.5, 0, 1.5, 1))
    shares = area_shares([half], [A, B])
    assert shares.columns == ["source_id", "target_id", "share", "coverage"]
    assert shares.get_column("share").to_list() == pytest.approx([0.5, 0.5])
    assert sorted(shares.get_column("target_id")) == ["A", "B"]
    assert shares.get_column("coverage").to_list() == pytest.approx([1.0, 1.0])


def test_a_source_inside_one_target_gets_weight_one_and_rows_are_sorted_by_key() -> None:
    inside = Area("p1", box(0.1, 0.1, 0.2, 0.2))
    wide = Area("p2", box(0.6, 0, 1.4, 1))
    shares = area_shares([wide, inside], [A, B])
    assert shares.select("source_id", "target_id").rows() == [
        ("p1", "A"),
        ("p2", "A"),
        ("p2", "B"),
    ]
    assert shares.row(0) == pytest.approx(("p1", "A", 1.0, 1.0))


def test_uncovered_source_is_a_schema_error_but_passes_under_a_lower_threshold() -> None:
    sticking_out = Area("p9", box(1.5, 0, 2.5, 1))
    with pytest.raises(SchemaError, match="p9"):
        area_shares([sticking_out], [A, B])
    lenient = area_shares([sticking_out], [A, B], min_coverage=0.5)
    assert lenient.row(0) == pytest.approx(("p9", "B", 1.0, 0.5))


def test_touching_targets_without_area_do_not_appear() -> None:
    # Die Quelle berührt B nur an der Kante x = 1; eine Berührung trägt keine Fläche.
    touching = Area("p1", box(0, 0, 1, 1))
    shares = area_shares([touching], [A, B])
    assert shares.get_column("target_id").to_list() == ["A"]


def test_district_weights_combine_eligible_voters_and_area_shares() -> None:
    table = _table([("p1", 1, 1000), ("p2", 1, 3000), ("p3", 2, 500)])
    shares = pl.DataFrame(
        [("p1", "A", 1.0), ("p2", "A", 0.5), ("p2", "B", 0.5), ("p3", "B", 1.0)],
        schema={"source_id": pl.String, "target_id": pl.String, "share": pl.Float64},
        orient="row",
    )
    weights = district_weights(table, shares)
    assert weights.columns == ["wahlkreis_id", "einheit", "gewicht"]
    # Wahlbezirk 1: A = 1000 + 1500, B = 1500, zusammen 4000
    assert weights.rows() == [
        (1, "A", pytest.approx(0.625)),
        (1, "B", pytest.approx(0.375)),
        (2, "B", 1.0),
    ]


def test_both_crosswalks_agree_when_each_precinct_lies_in_one_unit() -> None:
    """Deckt sich jede Quellfläche mit genau einer Einheit, muss der geometrische Weg dasselbe
    liefern wie der Attribut-Crosswalk: dieselbe Zuordnung, dieselben Gewichte."""
    table = _table([("p1", 1, 1000), ("p2", 1, 3000), ("p3", 2, 500)])
    sources = [
        Area("p1", box(0, 0, 1, 1)),
        Area("p2", box(1, 0, 2, 1)),
        Area("p3", box(1, 0, 2, 1)),
    ]
    geometric = district_weights(table, area_shares(sources, [A, B]))
    attributes = unit_weights(
        table.with_columns(pl.Series("einheit", ["A", "B", "B"])), "einheit", "wahlberechtigte"
    )
    assert geometric.rows() == pytest.approx(
        attributes.select("wahlkreis_id", "einheit", "gewicht").rows()
    )


def test_a_district_without_eligible_voters_falls_away_instead_of_dividing_by_zero() -> None:
    """Wie ``unit_weights``: Zeilen ohne Zählgröße zählen nicht, ein Wahlbezirk ganz ohne fehlt.

    Das Modul dient auch den Optionen 02 und 05, die andere Zählgrößen mitbringen (Review
    2026-10-12); 0/0 wäre dort ein Vertragsbruch statt einer Aussage.
    """
    table = _table([("p1", 1, 0), ("p2", 1, 0), ("p3", 2, 500)])
    shares = pl.DataFrame(
        [("p1", "A", 1.0), ("p2", "B", 1.0), ("p3", "B", 1.0)],
        schema={"source_id": pl.String, "target_id": pl.String, "share": pl.Float64},
        orient="row",
    )
    weights = district_weights(table, shares)
    assert weights.rows() == [(2, "B", 1.0)]
    # Teils ohne Wahlberechtigte: nur die Stimmbezirke mit zählen
    mixed = _table([("p1", 1, 0), ("p2", 1, 300), ("p3", 2, 500)])
    assert district_weights(mixed, shares).rows() == [(1, "B", 1.0), (2, "B", 1.0)]
