"""Beobachtet gegen erwartet (``analysis.practice``), an einem Beispiel zum Nachrechnen.

Zwei Gremien: im Ausschuss wird viel gefragt (3 von 4 Dokumenten sind Kontrolle), im Rat wenig
(1 von 4). Fraktion A stellt drei Dokumente im Ausschuss und eines im Rat, B eines im Ausschuss
und drei im Rat; ein gemeinsames Dokument zählt für beide. Roh fragt A mehr als B — gegen die Praxis
ihrer Gremien gerechnet nicht.
"""

from __future__ import annotations

import polars as pl
import pytest

from georep.analysis.practice import EXPECTED, OBSERVED, RATIO, N, observed_expected


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "periode": ["p"] * 8,
            "gremium": ["AUS"] * 4 + ["RAT"] * 4,
            "fraktionen": [["A"], ["A"], ["A"], ["B"], ["A", "B"], ["B"], ["B"], []],
            "kontrolle": [True, True, False, True, True, False, False, False],
        }
    )


def test_the_expected_count_is_the_practice_of_the_bodies_summed_over_the_documents() -> None:
    found = observed_expected(
        _frame(),
        unit="fraktionen",
        outcome="kontrolle",
        strata=("periode", "gremium"),
        by=("periode",),
    )
    assert found.columns == ["periode", "fraktionen", N, OBSERVED, EXPECTED, RATIO]
    rows = {r["fraktionen"]: r for r in found.iter_rows(named=True)}
    # Ausschuss 3/4, Rat 1/4 (das Dokument ohne Fraktion zählt für den Anteil des Rates mit)
    assert rows["A"][N] == 4 and rows["A"][OBSERVED] == 3
    assert rows["A"][EXPECTED] == pytest.approx(3 * 0.75 + 0.25)
    assert rows["B"][N] == 4 and rows["B"][OBSERVED] == 2
    assert rows["B"][EXPECTED] == pytest.approx(0.75 + 3 * 0.25)
    assert rows["A"][RATIO] == pytest.approx(3 / 2.5)
    assert rows["B"][RATIO] == pytest.approx(2 / 1.5)


def test_a_scalar_unit_and_no_expectation_give_no_ratio() -> None:
    frame = pl.DataFrame(
        {"gremium": ["X", "X", "Y"], "fraktion": ["A", "B", "A"], "antwort": [False, False, True]}
    )
    found = observed_expected(frame, unit="fraktion", outcome="antwort", strata=("gremium",))
    rows = {r["fraktion"]: r for r in found.iter_rows(named=True)}
    assert rows["B"][EXPECTED] == 0 and rows["B"][RATIO] is None
    assert rows["A"][RATIO] == pytest.approx(1.0)


def test_by_must_be_a_stratum() -> None:
    with pytest.raises(Exception, match="by in strata"):
        observed_expected(
            _frame(), unit="fraktionen", outcome="kontrolle", strata=("gremium",), by=("periode",)
        )
