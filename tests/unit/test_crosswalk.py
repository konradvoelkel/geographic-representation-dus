"""Attribut-Crosswalk: Gewichte je Wahlbezirk und Einheit aus den Wahlberechtigten je Stimmbezirk."""

from __future__ import annotations

import deal
import polars as pl
import pytest

from georep.crosswalk import unit_weights


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
