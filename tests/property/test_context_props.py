"""Eigenschaften des gewichteten Mittels: Lage, Konstanz, Renormierung."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.prep.context import aggregate_context, named_weights
from georep.settings import ContextSettings, load_settings

# Zwei Variablen auf denselben Einheiten: eine mit Werten, eine teils ohne.
SETTINGS = """
context.max_missing_weight = 1.0
context.variables = [
  { name = "x", label = "x", unit = "", kind = "value", columns = ["X"] },
]
context.models = { main = ["trefferquote", "x"], parties = ["trefferquote"], single = ["x"] }
"""


@pytest.fixture(scope="module")
def context(tmp_path_factory: pytest.TempPathFactory) -> ContextSettings:
    root = tmp_path_factory.mktemp("context_props")
    (root / "settings.toml").write_text(SETTINGS, encoding="utf-8")
    return load_settings(cwd=root).context


def _frames(values: list[float | None], weights: list[float]) -> tuple[pl.DataFrame, pl.DataFrame]:
    keys = [f"u{i}" for i in range(len(values))]
    total = sum(weights)
    weight_frame = pl.DataFrame(
        {
            "wahlkreis_id": [1] * len(keys),
            "einheit": keys,
            "gewicht": [w / total for w in weights],
        },
        schema={"wahlkreis_id": pl.Int64, "einheit": pl.String, "gewicht": pl.Float64},
    )
    value_frame = pl.DataFrame(
        {"einheit": keys, "x": values}, schema={"einheit": pl.String, "x": pl.Float64}
    )
    return weight_frame, value_frame


pairs = st.lists(
    st.tuples(
        st.floats(min_value=-500.0, max_value=500.0),  # Wert der Einheit
        st.floats(min_value=0.01, max_value=100.0),  # Gewicht des Stimmbezirksanteils
    ),
    min_size=1,
    max_size=12,
)


@given(table=pairs)
def test_the_mean_lies_between_the_smallest_and_the_largest_value(
    table: list[tuple[float, float]], context: ContextSettings
) -> None:
    values = [v for v, _ in table]
    frame = aggregate_context(*_frames(list(values), [w for _, w in table]), context)
    mean = frame.get_column("x").item()
    assert min(values) - 1e-9 <= mean <= max(values) + 1e-9
    assert frame.get_column("x_fehlgewicht").item() == pytest.approx(0.0)


@given(value=st.floats(min_value=-500.0, max_value=500.0), weights=pairs)
def test_constant_units_give_the_constant(
    value: float, weights: list[tuple[float, float]], context: ContextSettings
) -> None:
    frame = aggregate_context(*_frames([value] * len(weights), [w for _, w in weights]), context)
    assert frame.get_column("x").item() == pytest.approx(value, abs=1e-9)


@given(table=pairs, extra=st.floats(min_value=0.01, max_value=50.0))
def test_a_unit_without_a_value_only_renormalises(
    table: list[tuple[float, float]], extra: float, context: ContextSettings
) -> None:
    """Eine Einheit ohne Wert ändert das Mittel nicht, sie taucht nur im Fehlgewicht auf."""
    values = [v for v, _ in table]
    weights = [w for _, w in table]
    without = aggregate_context(*_frames(list(values), list(weights)), context)
    with_gap = aggregate_context(*_frames([*values, None], [*weights, extra]), context)
    assert with_gap.get_column("x").item() == pytest.approx(without.get_column("x").item())
    assert with_gap.get_column("x_fehlgewicht").item() == pytest.approx(
        extra / (sum(weights) + extra)
    )


def test_the_fixture_settings_describe_one_variable(context: ContextSettings) -> None:
    assert [v.name for v in context.unit_variables()] == ["x"]
    assert context.root == Path("context")


# Gewichte je (Wahlbezirk, Einheit) und ein Name je Einheit; die Folge der Eingabe ist beliebig.
unit_weights_rows = st.lists(
    st.tuples(
        st.integers(1, 9),  # Wahlbezirk
        st.sampled_from("ABCDE"),  # Einheit
        st.floats(0.01, 1.0, allow_nan=False, allow_infinity=False),  # Gewicht
    ),
    min_size=1,
    max_size=14,
    unique_by=lambda row: (row[0], row[1]),
)


@given(rows=unit_weights_rows)
def test_the_published_crosswalk_is_sorted_whatever_the_join_gives(
    rows: list[tuple[int, str, float]],
) -> None:
    """``wahlbezirke_crosswalk.parquet`` wird veröffentlicht und muss byteidentisch entstehen.

    Der Join auf ``einheit`` legt die Zeilenfolge nicht fest; bis zum 2026-10-13 stand in
    ``context_step`` keine Sortierung, und die Zusage "zwei Läufe schreiben dieselbe Datei"
    (docs/architecture.md, "Datenhaltung") galt nur zufällig. Als Eigenschaft statt als Beispiel,
    weil sie für jede Eingabe gilt (Review-Befund 9, 2026-10-13).
    """
    weights = pl.DataFrame(
        rows,
        schema={"wahlkreis_id": pl.Int64, "einheit": pl.String, "gewicht": pl.Float64},
        orient="row",
    )
    units = sorted({row[1] for row in rows})
    values = pl.DataFrame(
        [(unit, f"Bezirk {unit}") for unit in reversed(units)],
        schema={"einheit": pl.String, "einheit_name": pl.String},
        orient="row",
    )
    found = named_weights(weights, values)
    assert found.columns == ["wahlkreis_id", "einheit", "einheit_name", "gewicht"]
    keys = list(found.select("wahlkreis_id", "einheit").iter_rows())
    assert keys == sorted(keys)
    assert found.get_column("einheit_name").null_count() == 0
    # Dieselben Zeilen in anderer Folge geben dieselbe Datei, Zeile für Zeile
    assert named_weights(weights.reverse(), values.reverse()).equals(found)
