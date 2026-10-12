"""Crosswalk: Attributgewichte je Wahlbezirk und der Flächen-Crosswalk auf einen Zuschnitt."""

from __future__ import annotations

import deal
import polars as pl
import pytest
from shapely.geometry import MultiPolygon, Polygon

from georep.crosswalk import (
    assign_by_point,
    largest_remainder,
    target_weights,
    transfer_counts,
    unit_weights,
)
from georep.errors import SchemaError
from georep.geo import Area


def test_district_in_two_city_districts_is_weighted_by_eligible_voters() -> None:
    # Wie Wahlbezirk 40 (Urdenbach, Garath Kämpenviertel): 8 136 Wahlberechtigte in Stadtbezirk 9,
    # 4 430 in Stadtbezirk 10; Briefwahlbezirke tragen 0 und fallen weg.
    precincts = pl.DataFrame(
        {
            "wahlkreis_id": [40, 40, 40, 40, 41, 41],
            "stadtbezirk": [9, 9, 10, 10, 10, 10],
            "wahlberechtigte": [5000, 3136, 4430, 0, 3000, 0],
        }
    )
    weights = unit_weights(precincts, "stadtbezirk", "wahlberechtigte")
    assert weights.columns == ["wahlkreis_id", "stadtbezirk", "wahlberechtigte", "gewicht"]
    assert weights.get_column("wahlkreis_id").to_list() == [40, 40, 41]
    assert weights.get_column("stadtbezirk").to_list() == [9, 10, 10]
    assert weights.get_column("wahlberechtigte").to_list() == [8136, 4430, 3000]
    assert weights.get_column("gewicht").to_list() == pytest.approx([0.6475, 0.3525, 1.0], abs=1e-4)


def test_negative_counts_violate_the_precondition() -> None:
    frame = pl.DataFrame({"wahlkreis_id": [1], "einheit": [1], "n": [-1]})
    with pytest.raises(deal.PreContractError):
        unit_weights(frame, "einheit", "n")
    with pytest.raises(deal.PreContractError):
        unit_weights(frame.drop("n"), "einheit", "n")


# --- Option 02: Zuordnung, Gewichte je Ziel und der summentreue Übertrag -----------------------
#
# Die Flächenanteile selbst prüft ``test_crosswalk_areas.py`` (Option 03); hier steht, was eine
# Periode darauf aufbaut. Schlüssel sind Text, wie ``area_shares`` sie gibt.


def _box(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def test_point_assignment_finds_the_one_containing_target() -> None:
    sources = [Area("a", _box(0, 0, 1, 1)), Area("b", _box(2, 0, 3, 1))]
    targets = [Area("7", _box(-1, -1, 1.5, 2)), Area("8", _box(1.5, -1, 4, 2))]
    assert assign_by_point(sources, targets) == {"a": "7", "b": "8"}


def test_point_assignment_names_the_source_without_a_target() -> None:
    sources = [Area("a", _box(0, 0, 1, 1)), Area("weit-weg", _box(50, 50, 51, 51))]
    with pytest.raises(SchemaError, match="weit-weg"):
        assign_by_point(sources, [Area("1", _box(-1, -1, 2, 2))])
    # Überlappende Ziele sind genauso ein Datenfehler wie keines
    with pytest.raises(SchemaError, match="0 Zielflächen|2 Zielflächen"):
        assign_by_point(
            [Area("a", _box(0, 0, 1, 1))],
            [Area("1", _box(-1, -1, 2, 2)), Area("2", _box(-1, -1, 2, 2))],
        )


def test_point_assignment_also_works_for_a_multipart_source() -> None:
    """Ein mehrteiliger Stimmbezirk liegt mit seinem Punkt in genau einem Wahlbezirk."""
    two_parts = MultiPolygon([_box(0, 0, 1, 1), _box(0.2, 2, 0.8, 3)])
    assert assign_by_point([Area("m", two_parts)], [Area("5", _box(-1, -1, 4, 4))]) == {"m": "5"}


def test_target_weights_normalise_per_target() -> None:
    shares = pl.DataFrame(
        {"source_id": ["a", "b", "c"], "target_id": ["1", "1", "2"], "share": [1.0, 1.0, 1.0]}
    )
    counts = pl.DataFrame({"source_id": ["a", "b", "c"], "n": [300, 100, 50]})
    weights = target_weights(shares, counts, "n")
    assert weights.columns == ["source_id", "target_id", "gewicht"]
    assert weights.get_column("source_id").to_list() == ["a", "b", "c"]
    assert weights.get_column("gewicht").to_list() == pytest.approx([0.75, 0.25, 1.0])


def test_target_weights_drop_sources_without_count() -> None:
    shares = pl.DataFrame({"source_id": ["a", "b"], "target_id": ["1", "1"], "share": [1.0, 1.0]})
    counts = pl.DataFrame({"source_id": ["a", "b"], "n": [10, 0]})
    weights = target_weights(shares, counts, "n")
    assert weights.get_column("source_id").to_list() == ["a"]
    assert weights.get_column("gewicht").item() == 1.0


def test_target_weights_need_one_row_per_source() -> None:
    """Eine doppelte Quelle würde den Join vervielfachen und die Gewichte still verschieben."""
    shares = pl.DataFrame({"source_id": ["a", "b"], "target_id": ["1", "1"], "share": [1.0, 1.0]})
    doubled = pl.DataFrame({"source_id": ["a", "a", "b"], "n": [300, 300, 100]})
    with pytest.raises(deal.PreContractError):
        target_weights(shares, doubled, "n")
    with pytest.raises(deal.PreContractError):
        target_weights(shares, pl.DataFrame({"source_id": ["a", "b"], "n": [-1, 1]}), "n")


def test_largest_remainder_keeps_the_sum_and_stays_close() -> None:
    assert largest_remainder([1.5, 1.5, 1.0]) == [2, 1, 1]
    assert largest_remainder([0.4, 0.4, 0.2]) == [1, 0, 0]
    assert largest_remainder([]) == []
    assert largest_remainder([3.0]) == [3]
    assert sum(largest_remainder([33.3, 33.3, 33.4])) == 100


def test_largest_remainder_refuses_negative_or_infinite_values() -> None:
    with pytest.raises(deal.PreContractError):
        largest_remainder([-1.0])
    with pytest.raises(deal.PreContractError):
        largest_remainder([float("inf")])


def test_transfer_counts_moves_voters_and_keeps_the_city_sum() -> None:
    # Zielschlüssel als Int64: der Aufrufer castet, damit die Reste numerisch sortiert zugeteilt
    # werden (als Text stünde „10" vor „2").
    shares = pl.DataFrame(
        {"source_id": ["a", "a", "b"], "target_id": [1, 2, 2], "share": [0.5, 0.5, 1.0]}
    )
    counts = pl.DataFrame({"source_id": ["a", "b"], "eligible": [1001, 500], "voters": [501, 250]})
    moved = transfer_counts(counts, shares, ["eligible", "voters"])
    assert moved.columns == ["target_id", "eligible", "voters"]
    assert moved.get_column("target_id").to_list() == [1, 2]
    # 500,5 und 1000,5: der groesste Rest entscheidet, bei Gleichstand der kleinere Index
    assert moved.get_column("eligible").to_list() == [501, 1000]
    assert moved.get_column("voters").to_list() == [251, 500]
    assert int(moved.get_column("eligible").sum()) == 1501
    assert int(moved.get_column("voters").sum()) == 751
    assert moved.schema["eligible"] == pl.Int64


def test_transfer_counts_needs_the_same_sources_on_both_sides() -> None:
    shares = pl.DataFrame({"source_id": ["a"], "target_id": [1], "share": [1.0]})
    counts = pl.DataFrame({"source_id": ["a", "b"], "n": [1, 2]})
    with pytest.raises(deal.PreContractError):
        transfer_counts(counts, shares, ["n"])
    with pytest.raises(deal.PreContractError):
        transfer_counts(counts.head(1).with_columns(pl.col("n") * -1), shares, ["n"])
