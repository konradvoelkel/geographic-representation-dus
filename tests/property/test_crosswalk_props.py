"""Invarianten beider Crosswalks für beliebige Stimmbezirkstabellen und Flächen."""

from __future__ import annotations

import math

import polars as pl
import pytest
import shapely
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from georep.crosswalk import (
    MIN_SHARE,
    area_shares,
    assign_by_point,
    district_weights,
    largest_remainder,
    target_weights,
    transfer_counts,
    unit_weights,
)
from georep.errors import SchemaError
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


@given(sources=boxes())
def test_no_share_below_the_threshold_survives(sources: list[Area]) -> None:
    """Punkt 51: unter ``min_share`` ist ein Schnittstück ein Splitter und keine Zeile.

    Die Eigenschaft ist der Grund der Schwelle: ob ein Stück aus der Fließkomma-Arithmetik über
    0 liegt, hängt am Gitter und nicht an der Geografie (siehe den Test darüber). Geprüft wird
    mit einer groben Schwelle, damit die Aussage auch bei kleinen Kästen etwas bedeutet.
    """
    for threshold in (MIN_SHARE, 0.05):
        # Die grobe Schwelle nimmt einem Kasten über mehreren Zellen so viel Bedeckung, dass der
        # Wächter ``min_coverage`` sonst zuschlägt; hier geht es nur um die Anteile.
        shares = area_shares(sources, CELLS, min_coverage=0.01, min_share=threshold)
        assert bool((shares.get_column("share") >= threshold).all()), threshold


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
    # Anteile unter einem Billionstel sind keine Flächenanteile, sondern Fließkomma-Rauschen;
    # area_shares liefert sie nicht, und ein Gewicht daraus liefe in die denormalen Zahlen.
    rows = [
        (f"p{i}", unit, part)
        for i, (_, _, share) in enumerate(table)
        for unit, part in (("A", share), ("B", 1.0 - share))
        if part > 1e-12
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


# --- Option 02: Flächen-Crosswalk zwischen zwei Gitterzuschnitten ------------------------------

BOUND = 1000.0
cut_lines = st.lists(
    st.integers(min_value=100, max_value=900), min_size=1, max_size=3, unique=True
).map(sorted)
COUNT_COLUMNS = ("wahlberechtigte", "waehler")


def _cells(xs: list[int], ys: list[int]) -> list[Area]:
    """Das Gitter, das die Schnitte aus [0, 1000]² machen; Schlüssel ``Spalte-Zeile``."""
    edges_x = [0.0, *(float(x) for x in xs), BOUND]
    edges_y = [0.0, *(float(y) for y in ys), BOUND]
    return [
        Area(f"{i}-{j}", box(edges_x[i], edges_y[j], edges_x[i + 1], edges_y[j + 1]))
        for i in range(len(edges_x) - 1)
        for j in range(len(edges_y) - 1)
    ]


def _merged(cells: list[Area], groups: dict[str, str]) -> list[Area]:
    parts: dict[str, list[BaseGeometry]] = {}
    for cell in cells:
        parts.setdefault(groups[cell.key], []).append(cell.geometry)
    return [Area(key, shapely.unary_union(p)) for key, p in sorted(parts.items())]


@st.composite
def two_cuts(draw: st.DrawFn) -> tuple[list[Area], list[Area]]:
    """Ein Quellgitter und ein unabhängiges Zielgitter, dessen Zellen zu 1 bis 3 Bezirken verschmelzen."""
    sources = _cells(draw(cut_lines), draw(cut_lines))
    target_cells = _cells(draw(cut_lines), draw(cut_lines))
    n = draw(st.integers(min_value=1, max_value=3))
    groups = {cell.key: str(draw(st.integers(min_value=1, max_value=n))) for cell in target_cells}
    return sources, _merged(target_cells, groups)


def _counts(keys: list[str], values: list[list[int]]) -> pl.DataFrame:
    return pl.DataFrame(
        {"source_id": keys, **{c: v for c, v in zip(COUNT_COLUMNS, values, strict=True)}},
        schema={"source_id": pl.String, **dict.fromkeys(COUNT_COLUMNS, pl.Int64)},
    )


@given(cuts=two_cuts())
def test_area_shares_partition_every_source(
    cuts: tuple[list[Area], list[Area]],
) -> None:
    sources, targets = cuts
    shares = area_shares(sources, targets)
    assert set(shares.get_column("source_id")) == {s.key for s in sources}
    sums = shares.group_by("source_id").agg(pl.col("share").sum())
    assert sums.get_column("share").to_list() == pytest.approx([1.0] * sums.height, abs=1e-9)
    # Die Zielbezirke bedecken das ganze Gebiet, also ist die Abdeckung überall 1
    assert shares.get_column("coverage").to_list() == pytest.approx([1.0] * shares.height, abs=1e-9)


@given(cuts=two_cuts(), data=st.data())
def test_transfer_keeps_the_column_sums_and_weights_sum_to_one(
    cuts: tuple[list[Area], list[Area]], data: st.DataObject
) -> None:
    sources, targets = cuts
    keys = sorted(s.key for s in sources)
    values = [
        data.draw(
            st.lists(
                st.integers(min_value=0, max_value=5000), min_size=len(keys), max_size=len(keys)
            )
        )
        for _ in COUNT_COLUMNS
    ]
    counts = _counts(keys, values)
    shares = area_shares(sources, targets)
    moved = transfer_counts(counts, shares, list(COUNT_COLUMNS))
    for column in COUNT_COLUMNS:
        assert int(moved.get_column(column).sum()) == int(counts.get_column(column).sum())
    assert set(moved.get_column("target_id")) <= {t.key for t in targets}
    weights = target_weights(shares, counts, COUNT_COLUMNS[0])
    sums = weights.group_by("target_id").agg(pl.col("gewicht").sum())
    assert sums.get_column("gewicht").to_list() == pytest.approx([1.0] * sums.height, abs=1e-9)


@given(xs=cut_lines, ys=cut_lines, groups=st.integers(min_value=1, max_value=3))
def test_the_same_cut_gives_the_identity(xs: list[int], ys: list[int], groups: int) -> None:
    """Dasselbe Gitter als Quelle und als Grundlage der Ziele: ein Paar je Quelle mit Anteil 1."""
    cells = _cells(xs, ys)
    keys = sorted(c.key for c in cells)
    assignment = {key: str(1 + i % groups) for i, key in enumerate(keys)}
    targets = _merged(cells, assignment)
    shares = area_shares(cells, targets)
    assert shares.height == len(cells)
    assert shares.get_column("share").to_list() == pytest.approx([1.0] * shares.height)
    assert shares.get_column("source_id").to_list() == keys
    assert shares.get_column("target_id").to_list() == [assignment[k] for k in keys]
    assert assign_by_point(cells, targets) == assignment


@given(cuts=two_cuts(), margin=st.floats(min_value=1.0, max_value=50.0))
def test_a_smaller_target_area_lowers_the_coverage_only_at_the_edge(
    cuts: tuple[list[Area], list[Area]], margin: float
) -> None:
    """Fehlt den Zielen ein Randstreifen, sinkt die Abdeckung genau der Quellen am Rand.

    Der Streifen ist höchstens 50 breit, jede Gitterzeile mindestens 100 hoch: jede Quelle
    behält also Schnittfläche, und nur die oberste Zeile verliert etwas. Unter der Schwelle
    ist das ein Fehler, darüber bleiben die Anteile je Quelle eine Zerlegung.
    """
    sources, targets = cuts
    top = BOUND - margin
    clip = box(0.0, 0.0, BOUND, top)
    clipped = [
        Area(t.key, shapely.intersection(t.geometry, clip))
        for t in targets
        if shapely.intersection(t.geometry, clip).area > 0.0
    ]
    with pytest.raises(SchemaError, match="von Zielflächen bedeckt"):
        area_shares(sources, clipped, min_coverage=0.999)
    shares = area_shares(sources, clipped, min_coverage=0.4)
    full = set(shares.filter(pl.col("coverage") > 1.0 - 1e-9).get_column("source_id"))
    assert full == {s.key for s in sources if s.geometry.bounds[3] <= top + 1e-9}
    assert full != {s.key for s in sources}  # die oberste Zeile verliert immer etwas
    sums = shares.group_by("source_id").agg(pl.col("share").sum())
    assert sums.get_column("share").to_list() == pytest.approx([1.0] * sums.height, abs=1e-9)


@given(
    values=st.lists(
        st.floats(min_value=0.0, max_value=1e5, allow_nan=False, allow_infinity=False), max_size=60
    )
)
def test_largest_remainder_is_integral_close_and_sum_preserving(values: list[float]) -> None:
    rounded = largest_remainder(values)
    assert all(isinstance(n, int) for n in rounded)
    assert sum(rounded) == round(math.fsum(values))
    assert all(abs(n - v) < 1.0 for n, v in zip(rounded, values, strict=True))
