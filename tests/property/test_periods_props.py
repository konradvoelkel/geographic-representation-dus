"""Invarianten des Periodenvergleichs für beliebige Auswertungen."""

from __future__ import annotations

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.periods import D_RATE, D_TURNOUT, compare_periods, delta_regression
from georep.errors import EmptyResultError

LABELS = ("alt", "neu")
district_ids = st.lists(
    st.integers(min_value=1, max_value=41), min_size=1, max_size=12, unique=True
)


@st.composite
def results(draw: st.DrawFn, districts: list[int]) -> pl.DataFrame:
    size = len(districts)
    hits = draw(st.lists(st.integers(0, 5000), min_size=size, max_size=size))
    eligible = draw(st.lists(st.integers(1, 20000), min_size=size, max_size=size))
    voters = [draw(st.integers(0, e)) for e in eligible]
    return pl.DataFrame(
        {
            "wahlkreis_id": districts,
            "anzahl_treffer": hits,
            "Wahlberechtigte_insgesamt": eligible,
            "trefferquote": [h / e for h, e in zip(hits, eligible, strict=True)],
            "wahlbeteiligung": [v / e for v, e in zip(voters, eligible, strict=True)],
        },
        schema={
            "wahlkreis_id": pl.Int64,
            "anzahl_treffer": pl.Int64,
            "Wahlberechtigte_insgesamt": pl.Int64,
            "trefferquote": pl.Float64,
            "wahlbeteiligung": pl.Float64,
        },
    ).sort("wahlkreis_id")


@st.composite
def two_periods(draw: st.DrawFn) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Zwei Auswertungen über teils dieselben Wahlbezirke."""
    shared = draw(district_ids)
    extra = draw(st.lists(st.integers(42, 60), max_size=3, unique=True))
    return draw(results(sorted(shared))), draw(results(sorted(shared + extra)))


@given(both=two_periods())
def test_the_comparison_is_antisymmetric_and_covers_the_intersection(
    both: tuple[pl.DataFrame, pl.DataFrame],
) -> None:
    current, previous = both
    forward = compare_periods(current, previous, labels=LABELS)
    backward = compare_periods(previous, current, labels=(LABELS[1], LABELS[0]))
    shared = set(current.get_column("wahlkreis_id")) & set(previous.get_column("wahlkreis_id"))
    assert set(forward.get_column("wahlkreis_id")) == shared
    assert forward.height == backward.height
    for delta in (D_RATE, D_TURNOUT):
        assert forward.get_column(delta).to_list() == pytest.approx(
            [-d for d in backward.get_column(delta).to_list()], abs=1e-12
        )


@given(both=two_periods())
def test_the_delta_regression_stays_in_range_or_says_why_not(
    both: tuple[pl.DataFrame, pl.DataFrame],
) -> None:
    frame = compare_periods(both[0], both[1], labels=LABELS)
    try:
        fit = delta_regression(frame)
    except EmptyResultError:
        # Weniger als drei gemeinsame Bezirke oder keine Streuung in einer Änderung
        assert (
            frame.height < 3
            or frame.get_column(D_RATE).n_unique() < 2
            or frame.get_column(D_TURNOUT).n_unique() < 2
        )
        return
    assert -1.0 <= fit.r <= 1.0 and 0.0 <= fit.p <= 1.0 and fit.n == frame.height
