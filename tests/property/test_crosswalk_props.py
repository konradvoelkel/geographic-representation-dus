"""Invarianten des Attribut-Crosswalks für beliebige Stimmbezirkstabellen."""

from __future__ import annotations

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.crosswalk import unit_weights

rows = st.lists(
    st.tuples(
        st.integers(min_value=1, max_value=5),  # Wahlbezirk
        st.integers(min_value=1, max_value=4),  # Einheit
        st.integers(min_value=0, max_value=3000),  # Wahlberechtigte
    ),
    min_size=1,
    max_size=40,
)


def _frame(table: list[tuple[int, int, int]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "wahlkreis_id": [r[0] for r in table],
            "einheit": [r[1] for r in table],
            "n": [r[2] for r in table],
        },
        schema={"wahlkreis_id": pl.Int64, "einheit": pl.Int64, "n": pl.Int64},
    )


@given(table=rows)
def test_weights_partition_each_district(table: list[tuple[int, int, int]]) -> None:
    frame = _frame(table)
    weights = unit_weights(frame, "einheit", "n")
    sums = weights.group_by("wahlkreis_id").agg(pl.col("gewicht").sum())
    assert sums.get_column("gewicht").to_list() == pytest.approx([1.0] * sums.height)
    assert weights.get_column("gewicht").min() > 0 if weights.height else True  # type: ignore[operator]
    # Eine Zeile je (Wahlbezirk, Einheit) mit Zählgröße, und die Summen stimmen
    with_count = frame.filter(pl.col("n") > 0)
    expected = with_count.group_by("wahlkreis_id", "einheit").agg(pl.col("n").sum())
    assert weights.height == expected.height
    joined = weights.join(expected, on=["wahlkreis_id", "einheit"], suffix="_erwartet")
    assert joined.get_column("n").to_list() == joined.get_column("n_erwartet").to_list()


@given(table=rows, factor=st.integers(min_value=2, max_value=7))
def test_scaling_the_counts_keeps_the_weights(
    table: list[tuple[int, int, int]], factor: int
) -> None:
    frame = _frame(table)
    scaled = frame.with_columns(pl.col("n") * factor)
    a, b = unit_weights(frame, "einheit", "n"), unit_weights(scaled, "einheit", "n")
    assert a.get_column("gewicht").to_list() == pytest.approx(b.get_column("gewicht").to_list())
    assert a.select("wahlkreis_id", "einheit").equals(b.select("wahlkreis_id", "einheit"))


@given(
    district=st.integers(1, 5),
    unit=st.integers(1, 4),
    counts=st.lists(st.integers(1, 100), min_size=1, max_size=5),
)
def test_a_district_in_one_unit_has_weight_one(district: int, unit: int, counts: list[int]) -> None:
    frame = _frame([(district, unit, c) for c in counts])
    weights = unit_weights(frame, "einheit", "n")
    assert weights.height == 1 and weights.get_column("gewicht").item() == 1.0
    assert weights.get_column("n").item() == sum(counts)
