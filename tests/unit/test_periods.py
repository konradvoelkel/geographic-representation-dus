"""Vergleich zweier Perioden: Spalten, Differenzen, Schnittmenge, Regression der Änderungen."""

from __future__ import annotations

import deal
import polars as pl
import pytest

from georep.analysis.periods import (
    D_RATE,
    D_TURNOUT,
    compare_periods,
    comparison_columns,
    delta_regression,
)
from georep.errors import EmptyResultError

LABELS = ("Wahlperiode 2014 bis 2020", "Wahlperiode 2020 bis 2025")


def _results(districts: list[int], hits: list[int], turnout: list[float]) -> pl.DataFrame:
    eligible = [10_000] * len(districts)
    return pl.DataFrame(
        {
            "wahlkreis_id": districts,
            "anzahl_treffer": hits,
            "Wahlberechtigte_insgesamt": eligible,
            "trefferquote": [h / e for h, e in zip(hits, eligible, strict=True)],
            "wahlbeteiligung": turnout,
        }
    ).sort("wahlkreis_id")


OLD = _results([1, 2, 3], [100, 200, 300], [0.40, 0.50, 0.60])
NEW = _results([1, 2, 3], [150, 180, 400], [0.45, 0.48, 0.70])


def test_comparison_has_both_periods_and_the_differences() -> None:
    frame = compare_periods(NEW, OLD, labels=LABELS)
    assert frame.columns == comparison_columns()
    assert frame.get_column("wahlkreis_id").to_list() == [1, 2, 3]
    assert set(frame.get_column("periode_alt")) == {LABELS[0]}
    assert set(frame.get_column("periode_neu")) == {LABELS[1]}
    assert frame.get_column("anzahl_treffer_alt").to_list() == [100, 200, 300]
    assert frame.get_column("anzahl_treffer_neu").to_list() == [150, 180, 400]
    assert frame.get_column(D_RATE).to_list() == pytest.approx([0.005, -0.002, 0.01])
    assert frame.get_column(D_TURNOUT).to_list() == pytest.approx([0.05, -0.02, 0.10])


def test_only_districts_in_both_periods_are_compared() -> None:
    fewer = _results([2, 3], [200, 300], [0.5, 0.6])
    frame = compare_periods(NEW, fewer, labels=LABELS)
    assert frame.get_column("wahlkreis_id").to_list() == [2, 3]
    with pytest.raises(EmptyResultError, match="Zuschnitt"):
        compare_periods(NEW, _results([7, 8, 9], [1, 2, 3], [0.1, 0.2, 0.3]), labels=LABELS)


def test_comparison_needs_one_row_per_district_and_two_names() -> None:
    doubled = pl.concat([OLD, OLD]).sort("wahlkreis_id")
    with pytest.raises(deal.PreContractError):
        compare_periods(NEW, doubled, labels=LABELS)
    with pytest.raises(deal.PreContractError):
        compare_periods(NEW, OLD, labels=("gleich", "gleich"))
    with pytest.raises(deal.PreContractError):
        compare_periods(NEW, OLD, labels=("", "neu"))
    with pytest.raises(deal.PreContractError):
        compare_periods(NEW.drop("trefferquote"), OLD, labels=LABELS)


def test_swapping_the_periods_flips_the_signs() -> None:
    forward = compare_periods(NEW, OLD, labels=LABELS)
    backward = compare_periods(OLD, NEW, labels=(LABELS[1], LABELS[0]))
    assert forward.get_column(D_RATE).to_list() == pytest.approx(
        [-d for d in backward.get_column(D_RATE).to_list()]
    )
    assert (
        forward.get_column("anzahl_treffer_alt").to_list()
        == backward.get_column("anzahl_treffer_neu").to_list()
    )


def test_delta_regression_relates_the_two_changes() -> None:
    frame = compare_periods(NEW, OLD, labels=LABELS)
    fit = delta_regression(frame)
    assert fit.n == 3 and -1.0 <= fit.r <= 1.0 and 0.0 <= fit.p <= 1.0
    # Die Beteiligung ist in Prozentpunkten: 0,05 Anteil werden 5 Punkte
    assert fit.slope == pytest.approx(1000.0, rel=0.2)


def test_delta_regression_refuses_a_comparison_without_spread() -> None:
    flat = _results([1, 2, 3], [100, 100, 100], [0.4, 0.5, 0.6])
    with pytest.raises(EmptyResultError, match="Streuung"):
        delta_regression(compare_periods(flat, flat.clone(), labels=LABELS))
