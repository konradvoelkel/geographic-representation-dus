"""Eigenschaften der Tests von Vorhaben 22 für beliebige Eingaben (``georep.analysis.need``)."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.need import holm, morans_i, permutation_test, spearman, within_strata

p_values = st.lists(st.floats(min_value=0.0, max_value=1.0), max_size=12)
values = st.lists(
    st.floats(min_value=-1e3, max_value=1e3, allow_nan=False), min_size=3, max_size=25
)
# Moran's I bekommt Ränge und Rangresiduen. Beliebige Floats verlieren beim Verschieben ihre Streuung:
# hypothesis fand am 2026-11-24 [0, 0, 1,2e-9] mit shift 1, wo nach dem Zentrieren nur sechs
# Stellen übrig waren (I = -0,2500015 statt -0,25); das ist Rundung, keine Eigenschaft.
whole = st.lists(st.integers(min_value=-1000, max_value=1000).map(float), min_size=3, max_size=25)


@given(p=p_values)
def test_holm_never_lowers_a_p_and_keeps_their_order(p: list[float]) -> None:
    adjusted = holm(p)
    assert all(a >= q and a <= 1.0 for a, q in zip(adjusted, p, strict=True))
    order = sorted(range(len(p)), key=lambda i: (p[i], i))
    assert [adjusted[i] for i in order] == sorted(adjusted)


@given(p=p_values, data=st.data())
def test_holm_follows_a_reordering_of_its_input(p: list[float], data: st.DataObject) -> None:
    order = data.draw(st.permutations(range(len(p))))
    adjusted = holm(p)
    shuffled = holm([p[i] for i in order])
    assert shuffled == pytest.approx([adjusted[i] for i in order])


@given(x=values, seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_the_permutation_p_lies_in_its_grid(x: list[float], seed: int) -> None:
    xs = np.asarray(x)
    ys = np.random.default_rng(seed).normal(size=len(xs))
    rho, p = permutation_test(
        xs, ys, alternative="two-sided", permutations=49, rng=np.random.default_rng(seed)
    )
    if rho is None:
        assert p is None
    else:
        assert p is not None and 1 / 50 <= p <= 1.0
        assert round(p * 50) == pytest.approx(p * 50)


@given(
    x=st.lists(st.integers(min_value=-1000, max_value=1000), min_size=3, max_size=25),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_spearman_ignores_a_monotone_transformation(x: list[int], seed: int) -> None:
    """Ganze Zahlen, damit die Abbildung exakt bleibt: in Fließkomma macht sie Nachbarn gleich."""
    xs = np.asarray(x, dtype=np.float64)
    ys = np.random.default_rng(seed).normal(size=len(xs))
    rho = spearman(xs, ys)
    transformed = spearman(xs**3 + xs, ys)
    assert (rho is None) == (transformed is None)
    if rho is not None:
        assert transformed == pytest.approx(rho)


@given(x=values, seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_one_stratum_is_no_stratum(x: list[float], seed: int) -> None:
    xs = np.asarray(x)
    ys = np.random.default_rng(seed).normal(size=len(xs))
    inside, _ = within_strata(
        xs, ys, np.zeros(len(xs), dtype=np.int64), permutations=9, rng=np.random.default_rng(0)
    )
    rho = spearman(xs, ys)
    assert (inside is None) == (rho is None)
    if inside is not None:
        assert inside == pytest.approx(rho, abs=1e-9)


@given(
    x=whole,
    scale=st.floats(min_value=0.01, max_value=100.0),
    shift=st.floats(min_value=-100, max_value=100),
)
def test_morans_i_ignores_scale_and_shift(x: list[float], scale: float, shift: float) -> None:
    xs = np.asarray(x)
    n = len(xs)
    weights = np.zeros((n, n))
    for i in range(n - 1):
        weights[i, i + 1] = weights[i + 1, i] = 1.0
    first, _ = morans_i(xs, weights, permutations=9, rng=np.random.default_rng(0))
    second, _ = morans_i(xs * scale + shift, weights, permutations=9, rng=np.random.default_rng(0))
    if first is not None and second is not None:
        assert second == pytest.approx(first, abs=1e-6)
