"""Eigenschaften der multiplen Regression für beliebige Zahlen.

Der Maßstab ist ``scipy.stats.linregress`` im bivariaten Fall und die Algebra der kleinsten
Quadrate im übrigen: R² wächst nie, wenn ein Term dazukommt; die Steigung eines
Added-Variable-Plots ist der Koeffizient (Frisch-Waugh-Lovell); p liegt in [0, 1].
"""

from __future__ import annotations

import polars as pl
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from scipy.stats import linregress

from georep.analysis.ols import fit_ols, partial_residuals
from georep.errors import EmptyResultError

values = st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False)
triples = st.lists(st.tuples(values, values, values), min_size=6, max_size=30)


def _frame(rows: list[tuple[float, float, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        rows, schema={"y": pl.Float64, "a": pl.Float64, "b": pl.Float64}, orient="row"
    )


def _usable(frame: pl.DataFrame, columns: tuple[str, ...] = ("y", "a", "b")) -> bool:
    """Streuung in jeder Spalte über dem Fließkomma-Rauschen, sonst ist die Designmatrix entartet.

    Drei verschiedene Werte reichen nicht: hypothesis fand Spalten, die sich erst in der 16.
    Stelle unterscheiden, und ``fit_ols`` lehnt sie zu Recht als praktisch singulär ab
    (Konditionszahl 1e113, 2026-10-12). Eine Steigung auf solchen Daten wäre Rauschen.
    """
    for column in columns:
        series = frame.get_column(column)
        low, high = float(series.min() or 0.0), float(series.max() or 0.0)  # type: ignore[arg-type]
        if series.n_unique() <= 2 or high - low < 1e-6 * max(1.0, abs(low), abs(high)):
            return False
    return True


@given(rows=triples)
def test_the_bivariate_fit_is_linregress(rows: list[tuple[float, float, float]]) -> None:
    frame = _frame(rows)
    assume(_usable(frame, ("y", "a")))
    fit = fit_ols(frame, "y", ["a"])
    reference = linregress(frame.get_column("a").to_numpy(), frame.get_column("y").to_numpy())
    assert fit.term("a").coefficient == pytest.approx(reference.slope, rel=1e-7, abs=1e-9)
    assert fit.intercept.coefficient == pytest.approx(reference.intercept, rel=1e-7, abs=1e-9)
    assert fit.term("a").stderr == pytest.approx(reference.stderr, rel=1e-7, abs=1e-9)
    assert fit.term("a").p == pytest.approx(reference.pvalue, rel=1e-7, abs=1e-9)
    assert fit.r2 == pytest.approx(reference.rvalue**2, rel=1e-7, abs=1e-9)
    assert 0.0 <= fit.term("a").p <= 1.0 and fit.term("a").vif == 1.0


@given(rows=triples)
def test_r_squared_never_falls_when_a_term_is_added(
    rows: list[tuple[float, float, float]],
) -> None:
    frame = _frame(rows)
    assume(_usable(frame))
    small = fit_ols(frame, "y", ["a"])
    try:
        large = fit_ols(frame, "y", ["a", "b"])
    except EmptyResultError:
        return  # linear abhängige Terme sind kein Modell
    assert large.r2 >= small.r2 - 1e-9
    assert large.k == small.k + 1 and large.n == small.n


@given(rows=triples)
def test_the_added_variable_slope_is_the_coefficient(
    rows: list[tuple[float, float, float]],
) -> None:
    frame = _frame(rows)
    assume(_usable(frame))
    try:
        fit = fit_ols(frame, "y", ["a", "b"])
    except EmptyResultError:
        return
    for term in ("a", "b"):
        xs, ys = partial_residuals(frame, "y", ["a", "b"], term)
        variance = sum(x * x for x in xs)
        assume(variance > 1e-6)
        slope = sum(x * y for x, y in zip(xs, ys, strict=True)) / variance
        assert slope == pytest.approx(fit.term(term).coefficient, rel=1e-6, abs=1e-9)


@given(rows=triples, scale=st.floats(min_value=0.1, max_value=1000.0))
def test_scaling_y_scales_the_coefficients_and_leaves_p_alone(
    rows: list[tuple[float, float, float]], scale: float
) -> None:
    frame = _frame(rows)
    assume(_usable(frame, ("y", "a")))
    one = fit_ols(frame, "y", ["a"])
    scaled = fit_ols(frame, "y", ["a"], y_scale=scale)
    assert scaled.term("a").coefficient == pytest.approx(
        one.term("a").coefficient * scale, rel=1e-7
    )
    assert scaled.term("a").p == pytest.approx(one.term("a").p, rel=1e-7, abs=1e-12)
    assert scaled.r2 == pytest.approx(one.r2, rel=1e-7, abs=1e-12)
