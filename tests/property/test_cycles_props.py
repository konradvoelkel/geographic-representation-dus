"""Eigenschaften des Rhythmus und der exakten Tests von Vorhaben 17 (``analysis.cycles``).

Für jeden Zufallskorpus summiert ``zeit_monate`` zur Zahl der Dokumente und hängt nicht an der
Zeilenfolge; jedes Wahljahr aus ``complete_years`` liegt ganz in der Periode. Der
Randomisierungstest von H17.2 und Jonckheere-Terpstra geben für jede Tabelle p in
[1 / Zuordnungen, 1] und stimmen mit der wörtlichen Rechnung des Messskripts überein (Messdokument
17, § 6): dort je Zuordnung beide Matrizen doppelt zentriert, hier über Zellsummen; dort JT über
Kombinationen der Gruppen, hier über Anordnungen der Gruppenlabels.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from datetime import date, timedelta
from itertools import combinations, permutations

import numpy as np
import polars as pl
from hypothesis import given, settings
from hypothesis import strategies as st

from georep.analysis.cycles import (
    budget_test,
    complete_years,
    jonckheere,
    month_table,
    multiset_permutations,
)
from tests.unit.test_cycles import RULES

days = st.dates(min_value=date(2019, 1, 1), max_value=date(2022, 12, 31))
documents = st.lists(
    st.tuples(
        st.one_of(st.none(), days),
        st.sampled_from(("Anfrage CDU", "Antrag", "Haushaltsantrag SPD", "Vorlage", None)),
        st.sampled_from(("Anfrage zum Weg", "Antrag", "Mitteilung", "", None)),
        st.sampled_from(("text", "")),
        st.sampled_from(("Fraktion", "Verwaltung", "Person", None)),
        st.sampled_from(("rat", "ausschuss", None)),
    ),
    min_size=1,
    max_size=30,
)


def _frames(rows: list[tuple[object, ...]]) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    ids = [f"d{i:03d}" for i in range(len(rows))]
    corpus = pl.DataFrame(
        {
            "id": ids,
            "date": [r[0] for r in rows],
            "paper_type": [r[1] for r in rows],
            "name": [r[2] for r in rows],
            "text": [r[3] for r in rows],
        },
        schema={
            "id": pl.String,
            "date": pl.Date,
            "paper_type": pl.String,
            "name": pl.String,
            "text": pl.String,
        },
    )
    originators = pl.DataFrame(
        {"id": ids, "urheber_art": [r[4] for r in rows]},
        schema={"id": pl.String, "urheber_art": pl.String},
    )
    bodies = pl.DataFrame(
        {"id": ids, "gremium_art": [r[5] for r in rows]},
        schema={"id": pl.String, "gremium_art": pl.String},
    )
    return corpus, originators, bodies


@given(documents, st.randoms(use_true_random=False))
def test_the_month_table_sums_to_the_corpus_in_any_row_order(
    rows: list[tuple[object, ...]], rnd: random.Random
) -> None:
    corpus, originators, bodies = _frames(rows)
    table = month_table(corpus, originators, bodies, RULES, years=[2019, 2020, 2021])
    assert int(table.get_column("dokumente").sum()) == len(rows)
    assert int(table.get_column("mit_text").sum()) == sum(r[3] == "text" for r in rows)
    order = list(range(len(rows)))
    rnd.shuffle(order)
    shuffled = month_table(
        corpus[order], originators[order[::-1]], bodies[order], RULES, years=[2019, 2020, 2021]
    )
    assert shuffled.equals(table)


@given(days, st.integers(min_value=0, max_value=2000), st.integers(min_value=1, max_value=12))
def test_every_complete_year_lies_inside_its_period(first: date, length: int, month: int) -> None:
    last = first + timedelta(days=length)
    years = complete_years(first, last, month)
    for year in years:
        assert date(year, month, 1) >= date(first.year, first.month, 1)
        assert date(year + 1, month, 1) - timedelta(days=1) <= last
    # ein Tag mehr nimmt nie ein Wahljahr weg
    assert set(years) <= set(complete_years(first, last + timedelta(days=1), month))


@given(st.lists(st.integers(min_value=0, max_value=3), min_size=1, max_size=7))
def test_multiset_permutations_are_all_distinct_arrangements(labels: list[int]) -> None:
    found = multiset_permutations(labels)
    expected = math.factorial(len(labels))
    for count in Counter(labels).values():
        expected //= math.factorial(count)
    assert found.shape == (expected, len(labels))
    assert len({tuple(r) for r in found.tolist()}) == expected
    assert all(sorted(r) == sorted(labels) for r in found.tolist())


def _naive_delta(table: np.ndarray, assignment: tuple[int, ...]) -> float:
    def center(a: np.ndarray) -> np.ndarray:
        return a - a.mean(axis=1, keepdims=True) - a.mean(axis=0, keepdims=True) + a.mean()

    y = center(np.log1p(table))
    t = np.zeros_like(table)
    for row, column in enumerate(assignment):
        t[row, column] = 1.0
    tt = center(t)
    return float((tt * y).sum() / (tt * tt).sum())


@st.composite
def budget_cases(draw: st.DrawFn) -> tuple[np.ndarray, list[int]]:
    rows = draw(st.integers(min_value=2, max_value=5))
    columns = draw(st.integers(min_value=2, max_value=4))
    cells = draw(
        st.lists(
            st.integers(min_value=0, max_value=60), min_size=rows * columns, max_size=rows * columns
        )
    )
    assignment = draw(
        st.lists(
            st.integers(min_value=0, max_value=columns - 1), min_size=rows, max_size=rows
        ).filter(lambda a: len(set(a)) >= 2)
    )
    return np.array(cells, dtype=np.float64).reshape(rows, columns), assignment


@settings(max_examples=60)
@given(budget_cases())
def test_the_budget_test_is_the_measured_formula_over_every_arrangement(
    case: tuple[np.ndarray, list[int]],
) -> None:
    table, assignment = case
    result = budget_test(table, assignment)
    every = sorted(set(permutations(assignment)))
    deltas = [_naive_delta(table, z) for z in every]
    observed = _naive_delta(table, tuple(assignment))
    assert result.count == len(every)
    assert math.isclose(result.statistic, observed, rel_tol=1e-9, abs_tol=1e-9)
    assert 1 / result.count - 1e-12 <= result.p <= 1.0
    assert result.p_two_sided is not None and 1 / result.count - 1e-12 <= result.p_two_sided <= 1.0
    # Gleichstände bis auf Rundung darf der schnelle Weg anders zählen; sonst dieselbe Zahl
    near = sum(abs(d - observed) < 1e-9 for d in deltas)
    larger = sum(d >= observed - 1e-12 for d in deltas)
    assert abs(result.p * len(every) - larger) <= near


def _naive_jt(values: list[float], sizes: list[int]) -> tuple[float, float]:
    """Wie das Messskript: über die Kombinationen, welche Werte in welche Gruppe fallen."""

    def jt(groups: list[list[float]]) -> float:
        return sum(
            1.0 if a < b else (0.5 if a == b else 0.0)
            for i in range(len(groups))
            for j in range(i + 1, len(groups))
            for a in groups[i]
            for b in groups[j]
        )

    def split(free: list[int], rest: list[int]) -> list[list[list[int]]]:
        if not rest:
            return [[]]
        out = []
        for chosen in combinations(free, rest[0]):
            left = [f for f in free if f not in chosen]
            out += [[list(chosen), *more] for more in split(left, rest[1:])]
        return out

    start, groups = 0, []
    for size in sizes:
        groups.append(values[start : start + size])
        start += size
    observed = jt(groups)
    every = split(list(range(len(values))), sizes)
    larger = sum(jt([[values[i] for i in g] for g in z]) >= observed - 1e-12 for z in every)
    return observed, larger / len(every)


@st.composite
def jt_cases(draw: st.DrawFn) -> tuple[list[float], list[int]]:
    sizes = draw(st.lists(st.integers(min_value=1, max_value=3), min_size=2, max_size=3))
    values = draw(
        st.lists(
            st.sampled_from((0.01, 0.02, 0.03, 0.05, 0.08)),
            min_size=sum(sizes),
            max_size=sum(sizes),
        )
    )
    return values, sizes


@given(jt_cases())
def test_jonckheere_agrees_with_the_measurement_and_stays_in_range(
    case: tuple[list[float], list[int]],
) -> None:
    values, sizes = case
    result = jonckheere(values, sizes)
    observed, p = _naive_jt(values, sizes)
    assert result.statistic == observed
    assert math.isclose(result.p, p)
    assert 1 / result.count - 1e-12 <= result.p <= 1.0
