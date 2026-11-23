"""Eigenschaften der indirekten Standardisierung (``analysis.practice.observed_expected``).

Mit genau einer Einheit je Dokument ist die Summe der Erwartungen die Summe der Beobachtungen
(je Gruppe ``by``): die Standardisierung verteilt nur um. Bei überall gleichem Anteil p ist die
Erwartung p mal die Zahl der Dokumente. Die Zeilenfolge spielt keine Rolle.
"""

from __future__ import annotations

import random

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.practice import EXPECTED, OBSERVED, N, observed_expected

rows = st.lists(
    st.tuples(
        st.sampled_from(("p1", "p2")),
        st.sampled_from(("RAT", "AUS", "BV1", None)),
        st.sampled_from(("A", "B", "C")),
        st.booleans(),
    ),
    min_size=1,
    max_size=40,
)


def _frame(found: list[tuple[str, str | None, str, bool]]) -> pl.DataFrame:
    return pl.DataFrame(
        found,
        schema={"periode": pl.String, "gremium": pl.String, "einheit": pl.String, "y": pl.Boolean},
        orient="row",
    )


def _oe(frame: pl.DataFrame) -> pl.DataFrame:
    return observed_expected(
        frame, unit="einheit", outcome="y", strata=("periode", "gremium"), by=("periode",)
    )


@given(rows)
def test_with_one_unit_per_document_expected_sums_to_observed(
    found: list[tuple[str, str | None, str, bool]],
) -> None:
    result = _oe(_frame(found))
    for (_period,), group in result.group_by(["periode"]):
        assert group[EXPECTED].sum() == pytest.approx(group[OBSERVED].sum())
    assert int(result[N].sum()) == len(found)


@given(rows, st.randoms(use_true_random=False))
def test_the_row_order_does_not_matter(
    found: list[tuple[str, str | None, str, bool]], rnd: random.Random
) -> None:
    other = list(found)
    rnd.shuffle(other)
    first, second = _oe(_frame(found)), _oe(_frame(other))
    assert first.drop(EXPECTED, "verhaeltnis").equals(second.drop(EXPECTED, "verhaeltnis"))
    assert first[EXPECTED].to_list() == pytest.approx(second[EXPECTED].to_list())


@given(rows, st.booleans())
def test_a_constant_practice_expects_its_share_of_every_document(
    found: list[tuple[str, str | None, str, bool]], value: bool
) -> None:
    same = [(p, g, u, value) for p, g, u, _ in found]
    result = _oe(_frame(same))
    assert result[EXPECTED].to_list() == pytest.approx([n * float(value) for n in result[N]])
