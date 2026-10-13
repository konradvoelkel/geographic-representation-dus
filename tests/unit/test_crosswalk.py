"""Crosswalk: Attributgewichte je Wahlbezirk und der Flächen-Crosswalk auf einen Zuschnitt."""

from __future__ import annotations

import deal
import polars as pl
import pytest
from shapely.geometry import MultiPolygon, Polygon

from georep.crosswalk import (
    area_shares,
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


def test_equal_weights_are_ordered_by_the_unit_and_not_by_chance() -> None:
    """Die zugesagte Folge ist „Wahlbezirk, dann Gewicht absteigend, dann Einheit".

    Zwei Einheiten mit **demselben** Gewicht zeigen, dass die Einheit der Stichentscheid ist und
    aufsteigend sortiert. Ohne diesen Fall entscheidet das Gewicht allein, und die Richtung des
    letzten Schlüssels ist unbelegt: der Mutant ``descending=[False, True, False]`` zu
    ``[…, True]`` überlebte am 2026-10-13 (docs/mutation-2026-10-13.md). Dieselbe Sorte Befund
    wie der ``maintain_order``-Mutant vom 2026-10-12.
    """
    precincts = pl.DataFrame(
        {
            "wahlkreis_id": [1, 1, 2, 2],
            "stadtbezirk": [7, 3, 4, 9],
            "wahlberechtigte": [1000, 1000, 1500, 500],
        }
    )
    weights = unit_weights(precincts, "stadtbezirk", "wahlberechtigte")
    assert weights.get_column("stadtbezirk").to_list() == [3, 7, 4, 9]
    assert weights.get_column("gewicht").to_list() == pytest.approx([0.5, 0.5, 0.75, 0.25])


def test_target_weights_order_equal_weights_by_the_source() -> None:
    """Wie oben für den Weg je Zielfläche: Ziel, Gewicht absteigend, dann Quelle."""
    shares = pl.DataFrame(
        {
            "source_id": ["b", "a", "c"],
            "target_id": ["1", "1", "1"],
            "share": [1.0, 1.0, 1.0],
        }
    )
    counts = pl.DataFrame({"source_id": ["b", "a", "c"], "n": [100, 100, 300]})
    weights = target_weights(shares, counts, "n")
    assert weights.get_column("source_id").to_list() == ["c", "a", "b"]
    assert weights.get_column("gewicht").to_list() == pytest.approx([0.6, 0.2, 0.2])


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


# --- Punkt 51: Splitter aus der Fließkomma-Arithmetik ------------------------------------------


def test_a_shared_border_does_not_become_a_share() -> None:
    """Zwei Zielflächen, die nur eine Grenze mit der Quelle teilen: das ist kein Schnittstück.

    Der Schnitt zweier Flächen entlang einer gemeinsamen Grenze ist in Fließkomma nicht 0,
    sondern etwas wie 4,44e-16 -- und ob er über 0 liegt, hängt an den Koordinaten und nicht an
    der Geografie (hypothesis, 2026-10-13). Hier liegt die Quelle genau in der linken Zelle; die
    rechte berührt sie nur, und ihre Zeile darf nicht entstehen.
    """
    source = [Area("p", Polygon([(0.1, 0.1), (3.0, 0.1), (3.0, 0.9), (0.1, 0.9)]))]
    targets = [
        Area("links", Polygon([(0.0, 0.0), (3.0, 0.0), (3.0, 1.0), (0.0, 1.0)])),
        Area("rechts", Polygon([(3.0, 0.0), (6.0, 0.0), (6.0, 1.0), (3.0, 1.0)])),
    ]
    shares = area_shares(source, targets)
    assert shares.get_column("target_id").to_list() == ["links"]
    assert shares.get_column("share").to_list() == [1.0]
    # Ohne Schwelle hinge es am Zufall der Koordinaten, ob die Berührung eine Zeile wird
    assert area_shares(source, targets, min_share=0.0).height >= 1


def test_a_sliver_falls_out_before_the_shares_are_normalised() -> None:
    """Die Schwelle wirkt vor der Normierung: der Rest summiert trotzdem zu 1.

    Die Quelle liegt zu 99,99999 % in der linken Zelle und ragt um 1e-7 ihrer Fläche in die
    rechte. Mit der Vorgabe (1e-9) bleibt dieser Zipfel; mit einer groben Schwelle fällt er weg,
    und der verbleibende Anteil ist genau 1, nicht 0,9999999.
    """
    source = [Area("p", Polygon([(0.0, 0.0), (1.0 + 1e-7, 0.0), (1.0 + 1e-7, 1.0), (0.0, 1.0)]))]
    targets = [
        Area("links", Polygon([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])),
        Area("rechts", Polygon([(1.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0)])),
    ]
    fine = area_shares(source, targets)
    assert fine.get_column("target_id").to_list() == ["links", "rechts"]
    assert fine.get_column("share").to_list()[1] == pytest.approx(1e-7, rel=1e-3)
    coarse = area_shares(source, targets, min_share=1e-6)
    assert coarse.get_column("target_id").to_list() == ["links"]
    assert coarse.get_column("share").to_list() == [1.0]
    # Die Bedeckung zählt den Splitter dann auch nicht mit: sie bleibt knapp unter 1
    assert coarse.get_column("coverage").to_list()[0] == pytest.approx(1 - 1e-7, rel=1e-3)


def test_the_threshold_has_to_be_a_share() -> None:
    source = [Area("p", Polygon([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]))]
    with pytest.raises(deal.PreContractError):
        area_shares(source, source, min_share=1.5)


def test_the_default_of_the_setting_is_the_default_of_the_function() -> None:
    """Zwei Stellen, eine Zahl: ``settings.py`` kann ``MIN_SHARE`` nicht importieren (Zyklus über
    ``geo``), darum hält dieser Test sie zusammen."""
    from georep.crosswalk import MIN_SHARE
    from georep.settings import Crosswalk

    assert Crosswalk().min_share == MIN_SHARE
