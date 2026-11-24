"""Eigenschaften von Holm (``analysis.hypotheses.holm``) für jede Familie von p-Werten.

Holm verwirft nie, was der unkorrigierte Test nicht verwirft (Messdokument 17, § 6), der
angepasste Wert liegt zwischen p und 1, ein kleinerer p-Wert bekommt nie einen größeren
angepassten Wert, die Folge der Eingabe spielt keine Rolle, und mindestens eine Hypothese fällt
genau dann, wenn der kleinste p-Wert unter α/m liegt (der erste Holm-Schritt ist Bonferroni).

Das Orakel (Review N7, 2026-11-24) ist Holms Schrittregel, wie sie in Holm (1979) und im Messskript
von Vorhaben 17 steht: aufsteigend sortiert fällt H_(k) genau dann, wenn p_(j) <= α/(m − j + 1)
für alle j <= k (mit ``strict`` <). Die Rechnung über das laufende Maximum von (m − j + 1) · p_(j)
ist mathematisch dasselbe, aber nicht in Gleitkommazahlen: m = 11, p = 0,05/11 gibt 11 · p =
0,05000000000000001.
"""

from __future__ import annotations

import random

from hypothesis import example, given
from hypothesis import strategies as st

from georep.analysis.hypotheses import family, holm

p_values = st.dictionaries(
    st.text(alphabet="abcdefgh", min_size=1, max_size=3),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    min_size=1,
    max_size=8,
)
alphas = st.sampled_from((0.01, 0.05, 0.1))


@given(p_values, alphas)
def test_holm_never_rejects_what_the_uncorrected_test_keeps(
    p: dict[str, float], alpha: float
) -> None:
    for key, adjusted in holm(p, alpha).items():
        assert p[key] <= adjusted.p_holm <= 1.0
        if adjusted.rejected:
            assert p[key] <= alpha


@given(p_values)
def test_a_smaller_p_never_gets_a_larger_adjusted_value(p: dict[str, float]) -> None:
    adjusted = holm(p)
    for a in p:
        for b in p:
            if p[a] < p[b]:
                assert adjusted[a].p_holm <= adjusted[b].p_holm


@given(p_values, st.randoms(use_true_random=False))
def test_the_order_of_the_family_does_not_matter(p: dict[str, float], rnd: random.Random) -> None:
    keys = list(p)
    rnd.shuffle(keys)
    shuffled = {key: p[key] for key in keys}
    assert holm(shuffled) == holm(p)


@given(p_values, alphas)
def test_something_falls_exactly_when_bonferroni_lets_the_smallest_fall(
    p: dict[str, float], alpha: float
) -> None:
    rejected = [a.rejected for a in holm(p, alpha).values()]
    assert any(rejected) == (min(p.values()) <= alpha / len(p))


def _step_rule(p: dict[str, float], alpha: float, strict: bool) -> dict[str, bool]:
    """Holms Schrittregel wörtlich: je Rang die Schwelle α/(m − j + 1), ab dem ersten Halt nichts."""
    order = sorted(p, key=lambda key: (p[key], key))
    m = len(order)
    still = True
    out: dict[str, bool] = {}
    for j, key in enumerate(order, 1):
        bound = alpha / (m - j + 1)
        still = still and (p[key] < bound if strict else p[key] <= bound)
        out[key] = still
    return out


ELEVEN = {"a": 0.05 / 11, **{f"b{i}": 1.0 for i in range(10)}}


@given(p_values, alphas, st.booleans())
@example(ELEVEN, 0.05, False)
def test_holm_rejects_exactly_what_the_step_rule_rejects(
    p: dict[str, float], alpha: float, strict: bool
) -> None:
    expected = _step_rule(p, alpha, strict)
    assert {k: a.rejected for k, a in holm(p, alpha, strict=strict).items()} == expected


@given(p_values)
def test_family_confirms_exactly_what_holm_rejects(p: dict[str, float]) -> None:
    adjusted = holm(p)
    for key, (p_holm, word) in family(p).items():
        assert p_holm == adjusted[key].p_holm
        assert (word == "bestätigt") == adjusted[key].rejected
