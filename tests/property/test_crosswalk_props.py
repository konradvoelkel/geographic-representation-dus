"""Invarianten beider Crosswalks für beliebige Stimmbezirkstabellen und Flächen."""

from __future__ import annotations

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import box

from georep.crosswalk import area_shares, district_weights, unit_weights
from georep.geo import Area

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


# --- Flächenanteile: Zielflächen sind Gitterzellen, Quellflächen Kästen darin ------------------

CELLS = [Area(f"{i}{j}", box(i, j, i + 1, j + 1)) for i in range(4) for j in range(3)]


@st.composite
def boxes(draw: st.DrawFn) -> list[Area]:
    """Kästen, die ganz im Gitter [0, 4] × [0, 3] liegen: Bedeckung ist damit immer 1."""
    made: list[Area] = []
    for n in range(draw(st.integers(min_value=1, max_value=6))):
        x = draw(st.floats(min_value=0.0, max_value=3.5))
        y = draw(st.floats(min_value=0.0, max_value=2.5))
        w = draw(st.floats(min_value=0.1, max_value=4.0 - x))
        h = draw(st.floats(min_value=0.1, max_value=3.0 - y))
        made.append(Area(f"p{n}", box(x, y, x + w, y + h)))
    return made


@given(sources=boxes())
def test_area_shares_partition_each_source_and_match_the_intersection(sources: list[Area]) -> None:
    shares = area_shares(sources, CELLS)
    sums = shares.group_by("source_id").agg(pl.col("share").sum())
    assert sums.get_column("share").to_list() == pytest.approx([1.0] * sums.height)
    assert shares.get_column("coverage").to_list() == pytest.approx([1.0] * shares.height)
    by_key = {a.key: a for a in sources}
    for row in shares.iter_rows(named=True):
        source = by_key[row["source_id"]]
        cell = next(c for c in CELLS if c.key == row["target_id"])
        expected = source.geometry.intersection(cell.geometry).area / source.geometry.area
        assert row["share"] == pytest.approx(expected)


@given(sources=boxes(), factor=st.floats(min_value=0.2, max_value=5.0))
def test_scaling_the_grid_does_not_change_the_shares(sources: list[Area], factor: float) -> None:
    """Anteile sind dimensionslos: dieselbe Lage in einem gestreckten Gitter ergibt dieselben Zahlen."""

    def stretch(area: Area) -> Area:
        minx, miny, maxx, maxy = area.geometry.bounds
        return Area(area.key, box(minx * factor, miny * factor, maxx * factor, maxy * factor))

    a = area_shares(sources, CELLS)
    b = area_shares([stretch(s) for s in sources], [stretch(c) for c in CELLS])
    assert a.get_column("share").to_list() == pytest.approx(b.get_column("share").to_list())
    assert a.select("source_id", "target_id").equals(b.select("source_id", "target_id"))


# --- Gewichte je Wahlbezirk aus Anteilen ---------------------------------------------------------

precincts = st.lists(
    st.tuples(
        st.integers(min_value=1, max_value=4),  # Wahlbezirk
        st.integers(min_value=1, max_value=3000),  # Wahlberechtigte
        st.floats(min_value=0.0, max_value=1.0),  # Anteil der Einheit "A", Rest geht an "B"
    ),
    min_size=1,
    max_size=25,
)


def _pair(table: list[tuple[int, int, float]]) -> tuple[pl.DataFrame, pl.DataFrame]:
    counts = pl.DataFrame(
        [(f"p{i}", d, n) for i, (d, n, _) in enumerate(table)],
        schema={"stimmbezirk_id": pl.String, "wahlkreis_id": pl.Int64, "wahlberechtigte": pl.Int64},
        orient="row",
    )
    rows = [
        (f"p{i}", unit, share if unit == "A" else 1.0 - share)
        for i, (_, _, share) in enumerate(table)
        for unit in ("A", "B")
        if (share if unit == "A" else 1.0 - share) > 0.0
    ]
    shares = pl.DataFrame(
        rows,
        schema={"source_id": pl.String, "target_id": pl.String, "share": pl.Float64},
        orient="row",
    )
    return counts, shares


@given(table=precincts)
def test_district_weights_partition_each_district(table: list[tuple[int, int, float]]) -> None:
    counts, shares = _pair(table)
    weights = district_weights(counts, shares)
    sums = weights.group_by("wahlkreis_id").agg(pl.col("gewicht").sum())
    assert sums.get_column("gewicht").to_list() == pytest.approx([1.0] * sums.height)
    assert set(weights.get_column("wahlkreis_id")) == set(counts.get_column("wahlkreis_id"))


@given(table=precincts, factor=st.integers(min_value=2, max_value=7))
def test_scaling_the_eligible_voters_keeps_the_weights(
    table: list[tuple[int, int, float]], factor: int
) -> None:
    counts, shares = _pair(table)
    a = district_weights(counts, shares)
    b = district_weights(counts.with_columns(pl.col("wahlberechtigte") * factor), shares)
    assert a.get_column("gewicht").to_list() == pytest.approx(b.get_column("gewicht").to_list())
    assert a.select("wahlkreis_id", "einheit").equals(b.select("wahlkreis_id", "einheit"))
