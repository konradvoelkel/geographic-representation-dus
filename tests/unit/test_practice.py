"""Beobachtet gegen erwartet (``analysis.practice``), an einem Beispiel zum Nachrechnen.

Zwei Gremien: im Ausschuss wird viel gefragt (3 von 4 Dokumenten sind Kontrolle), im Rat wenig
(1 von 4). Fraktion A stellt drei Dokumente im Ausschuss und eines im Rat, B eines im Ausschuss
und drei im Rat; ein gemeinsames Dokument zählt für beide. Roh fragt A mehr als B — gegen die Praxis
ihrer Gremien gerechnet nicht.
"""

from __future__ import annotations

import random

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


def _large(rows: int = 100_000) -> pl.DataFrame:
    """Viele Zeilen, viele Schichten, gemeinsame Dokumente: genug, dass Polars parallel rechnet."""
    rnd = random.Random(15)
    units = [
        sorted({f"F{rnd.randrange(8)}", *([f"F{rnd.randrange(8)}"] if rnd.random() < 0.2 else [])})
        for _ in range(rows)
    ]
    return pl.DataFrame(
        {
            "gremium": [f"G{rnd.randrange(300)}" for _ in range(rows)],
            "fraktionen": units,
            "kontrolle": [rnd.random() < 0.37 for _ in range(rows)],
        }
    )


def test_the_expectation_is_the_same_to_the_last_bit_on_every_run() -> None:
    """Review 2026-11-24, M1: ein Join ohne Folge und eine Fließkommasumme im ``group_by`` gaben an
    5 000 Zeilen 17 verschiedene Vektoren in 30 Läufen. Eine Zahl der Seite darf das nicht."""
    frame = _large()
    seen = {
        tuple(
            float(x).hex()
            for x in observed_expected(
                frame, unit="fraktionen", outcome="kontrolle", strata=("gremium",)
            )[EXPECTED]
        )
        for _ in range(20)
    }
    assert len(seen) == 1


def test_the_expectation_does_not_depend_on_the_row_order_to_the_last_bit() -> None:
    """Dieselbe Eigenschaft, ohne auf den Zufall der Threads zu warten: andere Zeilenfolge,
    dieselben Bits. Eine Summe in der Folge der Zeilen hängt an ihr; eine exakt gerundete nicht."""
    frame = _large(20_000)
    rnd = random.Random(24)

    def bits(rows: pl.DataFrame) -> tuple[str, ...]:
        found = observed_expected(rows, unit="fraktionen", outcome="kontrolle", strata=("gremium",))
        return tuple(float(x).hex() for x in found[EXPECTED])

    first = bits(frame)
    for _ in range(3):
        order = list(range(frame.height))
        rnd.shuffle(order)
        assert bits(frame[order]) == first


def test_a_unit_named_twice_in_one_document_counts_once() -> None:
    """Review 2026-11-24, K2: ein Dokument zählt für jede Einheit darin einmal, auch wenn die Liste
    sie doppelt nennt (Vorhaben 14 übergibt eigene Listen)."""
    frame = pl.DataFrame(
        {"gremium": ["X", "X"], "fraktionen": [["A", "A"], ["B"]], "kontrolle": [True, False]}
    )
    found = observed_expected(frame, unit="fraktionen", outcome="kontrolle", strata=("gremium",))
    rows = {r["fraktionen"]: r for r in found.iter_rows(named=True)}
    assert (rows["A"][N], rows["A"][OBSERVED]) == (1, 1)
    assert rows["A"][EXPECTED] == pytest.approx(0.5)
