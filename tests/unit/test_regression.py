from __future__ import annotations

import polars as pl
import pytest

from georep.analysis.regression import regress, regression_pair, spearman
from georep.errors import EmptyResultError


def test_regression_without_spread_in_x_is_a_domain_error() -> None:
    frame = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3],
            "trefferquote": [0.2, 0.2, 0.2],
            "wahlbeteiligung": [0.5, 0.6, 0.7],
        }
    )
    with pytest.raises(EmptyResultError, match="Streuung"):
        regress(frame)


def test_two_distinct_x_values_are_enough_spread() -> None:
    """Mutant < -> <= an n_unique() < 2 überlebte am 2026-10-11: kein Test hatte genau zwei x-Werte."""
    frame = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3],
            "trefferquote": [0.1, 0.1, 0.2],
            "wahlbeteiligung": [0.5, 0.6, 0.7],
        }
    )
    assert regress(frame).n == 3


def test_regression_pair_without_outliers_has_no_second_fit() -> None:
    frame = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3, 4],
            "trefferquote": [0.1, 0.2, 0.3, 0.9],
            "wahlbeteiligung": [0.5, 0.6, 0.7, 0.4],
        }
    )
    pair = regression_pair(frame)
    assert pair.excluded == () and pair.without is None and pair.all.n == 4
    with_outlier = regression_pair(frame, [4])
    assert with_outlier.excluded == (4,) and with_outlier.without is not None
    assert with_outlier.without.n == 3 and with_outlier.all == pair.all
    # Zu wenige Bezirke ohne die Ausreißer: die zweite Spalte bleibt leer, die erste steht
    assert regression_pair(frame, [1, 4]).without is None


def test_a_constant_y_is_no_result_either() -> None:
    """Ohne Streuung in y liefert scipy r und p als NaN; das ist kein Ergebnis (Option 02).

    Mit echten Daten kommt der Fall nicht vor, mit den Differenzen zweier Perioden auf einer
    kleinen Fixture schon: dort können alle Wahlbeteiligungen gleich sein.
    """
    frame = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3],
            "trefferquote": [0.01, 0.02, 0.03],
            "wahlbeteiligung": [0.5, 0.5, 0.5],
        }
    )
    with pytest.raises(EmptyResultError, match="Streuung in wahlbeteiligung"):
        regress(frame)


# --- Option 06: Rangkorrelation ----------------------------------------------------------------


def test_spearman_is_one_for_the_same_order_and_minus_one_for_the_reverse() -> None:
    frame = pl.DataFrame(
        {"a": [1.0, 2.0, 3.0, 4.0], "b": [10.0, 20.0, 30.0, 40.0], "c": [4.0, 3.0, 2.0, 1.0]}
    )
    assert spearman(frame, "a", "b") == 1.0
    assert spearman(frame, "a", "c") == -1.0
    assert spearman(frame, "b", "a") == 1.0  # symmetrisch


def test_spearman_has_no_value_without_variance_or_without_rows() -> None:
    flat = pl.DataFrame({"a": [1.0, 1.0, 1.0], "b": [1.0, 2.0, 3.0]})
    assert spearman(flat, "a", "b") is None
    assert spearman(flat, "b", "a") is None
    assert spearman(pl.DataFrame({"a": [1.0, 2.0], "b": [1.0, 2.0]}), "a", "b") is None


def test_spearman_ignores_the_distances_and_sees_only_the_order() -> None:
    frame = pl.DataFrame({"a": [1.0, 2.0, 100.0], "b": [1.0, 2.0, 3.0]})
    assert spearman(frame, "a", "b") == 1.0


def _ranked(rates: dict[int, float]) -> pl.DataFrame:
    """Je Bezirk eine Quote und eine Beteiligung, die nicht an ihr hängt."""
    return pl.DataFrame(
        {
            "wahlkreis_id": list(rates),
            "trefferquote": list(rates.values()),
            "wahlbeteiligung": [0.5, 0.6, 0.55, 0.62, 0.48, 0.58][: len(rates)],
        }
    )


def test_the_pair_knows_where_the_excluded_districts_rank() -> None:
    """Die Seite nannte 1 und 10 „die beiden höchsten Trefferquoten", ob es stimmte oder nicht.

    In der Periode 2014 bis 2020 stehen sie auf Platz 2 und 9, und seit Punkt 68 steht 10 auch in
    der Hauptperiode auf Platz 3 (2026-11-18). Die Ränge zählen von der höchsten Quote an.
    """
    frame = _ranked({1: 0.15, 2: 0.09, 10: 0.08, 3: 0.05, 4: 0.04, 5: 0.06})
    third = regression_pair(frame, (1, 10))
    assert third.excluded_ranks == (1, 3) and not third.excluded_are_top
    top = regression_pair(frame, (2, 1))
    assert top.excluded_ranks == (2, 1) and top.excluded_are_top
    assert regression_pair(frame).excluded_ranks == ()
    assert not regression_pair(frame).excluded_are_top  # ohne Ausschluss nichts zu behaupten
