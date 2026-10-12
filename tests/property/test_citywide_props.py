"""Eigenschaften der Schwelle für stadtweite Begriffe (Regel 2, decisions.md Punkt 44)."""

from __future__ import annotations

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.hits import Citywide, citywide_terms
from georep.search.index import HITS, PAPER_IDS, TERM

terms = st.text(alphabet="abcde", min_size=1, max_size=3)
frequencies = st.lists(st.tuples(terms, st.integers(0, 500)), min_size=1, max_size=40).map(
    lambda pairs: list({t: n for t, n in pairs}.items())
)


def _index(pairs: list[tuple[str, int]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            TERM: [p[0] for p in pairs],
            PAPER_IDS: [[f"d{i}" for i in range(min(p[1], 3))] for p in pairs],
            HITS: [p[1] for p in pairs],
        },
        schema={TERM: pl.String, PAPER_IDS: pl.List(pl.String), HITS: pl.Int64},
    )


@given(pairs=frequencies, quantile=st.floats(0.5, 0.999), factor=st.floats(1.0, 50.0))
def test_every_citywide_term_lies_above_the_threshold(
    pairs: list[tuple[str, int]], quantile: float, factor: float
) -> None:
    index = _index(pairs)
    counts = dict(pairs)
    for found in (
        citywide_terms(index, quantile=quantile, median_factor=0.0),
        citywide_terms(index, quantile=0.0, median_factor=factor),
    ):
        assert len(set(found.terms)) == len(found.terms)
        assert all(counts[term] > found.threshold for term in found.terms)
        assert all(
            counts[term] <= found.threshold for term in counts if term not in set(found.terms)
        )
        # Mit Schwelle gibt es immer einen Satz für die Seite, auch wenn niemand darüber liegt
        assert found.basis
    assert citywide_terms(index, quantile=0.0, median_factor=0.0) == Citywide(0, "", ())


@given(pairs=frequencies, quantile=st.floats(0.5, 0.999), factor=st.floats(1.0, 50.0))
def test_the_threshold_is_at_least_one_and_the_list_stays_a_minority(
    pairs: list[tuple[str, int]], quantile: float, factor: float
) -> None:
    """Befund 3: ohne Untergrenze wird in einem dünnen Index jeder Begriff mit einem Dokument
    stadtweit. Mit ihr braucht ein stadtweiter Begriff mindestens zwei Dokumente, und die Liste
    bleibt eine Minderheit der Begriffe."""
    index = _index(pairs)
    counts = dict(pairs)
    for found in (
        citywide_terms(index, quantile=quantile, median_factor=0.0),
        citywide_terms(index, quantile=0.0, median_factor=factor),
    ):
        assert found.threshold >= 1
        assert all(counts[term] >= 2 for term in found.terms)
        assert 2 * len(found.terms) <= len(pairs)


@given(pairs=frequencies, low=st.floats(0.5, 0.9), high=st.floats(0.9, 0.999))
def test_a_higher_quantile_names_at_most_as_many_terms(
    pairs: list[tuple[str, int]], low: float, high: float
) -> None:
    index = _index(pairs)
    few = citywide_terms(index, quantile=high, median_factor=0.0)
    many = citywide_terms(index, quantile=low, median_factor=0.0)
    assert few.threshold >= many.threshold
    assert set(few.terms) <= set(many.terms)
