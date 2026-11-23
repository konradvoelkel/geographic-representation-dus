"""Eigenschaften der Validierungsmaße für alle Eingaben, und deal.cases auf ihre Verträge.

Die Beispiele in ``tests/unit/test_validation_measures.py`` sagen, dass die Zahlen an bekannten
Stellen stimmen; hier steht, was für jede Kodierung gilt: α = 1 bei identischen Kodierungen, α
hängt nicht an der Folge der Einheiten oder Kodierer, κ ist symmetrisch und gleich scikit-learn,
jede Güte liegt in [0, 1], das ideale Ranking hat nDCG 1.
"""

from __future__ import annotations

import math
import random
import warnings

import deal
from hypothesis import assume, given
from hypothesis import strategies as st
from sklearn.metrics import cohen_kappa_score, ndcg_score, precision_recall_fscore_support

from georep.validation.measures import (
    LEVELS,
    Level,
    agreement,
    classify_scores,
    cohen_kappa,
    krippendorff_alpha,
    ndcg_at_k,
    wilson_interval,
)

CATEGORIES = ["1", "2", "3", "4", "5"]
labels = st.sampled_from(CATEGORIES)
levels = st.sampled_from(LEVELS)


@st.composite
def two_codings(draw: st.DrawFn, min_size: int = 1) -> tuple[list[str], list[str]]:
    first = draw(st.lists(labels, min_size=min_size, max_size=40))
    second = draw(st.lists(labels, min_size=len(first), max_size=len(first)))
    return first, second


coded_units = st.lists(
    st.lists(st.one_of(st.none(), labels), min_size=1, max_size=4).map(tuple),
    min_size=1,
    max_size=30,
)


@given(st.lists(labels, min_size=2, max_size=40), levels)
def test_identical_codings_have_alpha_one(values: list[str], level: Level) -> None:
    assume(len(set(values)) >= 2)
    units = [(v, v) for v in values]
    assert krippendorff_alpha(units, level, CATEGORIES) == 1.0


@given(coded_units, levels, st.randoms(use_true_random=False))
def test_alpha_ignores_the_order_of_units_and_coders(
    units: list[tuple[str | None, ...]], level: Level, rng: random.Random
) -> None:
    shuffled = [tuple(rng.sample(unit, len(unit))) for unit in units]
    rng.shuffle(shuffled)
    first = krippendorff_alpha(units, level, CATEGORIES)
    second = krippendorff_alpha(shuffled, level, CATEGORIES)
    assert (first is None) == (second is None)
    if first is not None and second is not None:
        assert math.isclose(first, second, abs_tol=1e-9)


@given(two_codings())
def test_kappa_is_symmetric_and_scikit_learns(coding: tuple[list[str], list[str]]) -> None:
    first, second = coding
    kappa = cohen_kappa(first, second)
    assert kappa == cohen_kappa(second, first)
    if kappa is not None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            assert math.isclose(kappa, cohen_kappa_score(first, second), abs_tol=1e-9)


@given(st.lists(labels, min_size=1, max_size=40))
def test_a_coder_agrees_with_himself(values: list[str]) -> None:
    assert agreement(values, values) == 1.0
    kappa = cohen_kappa(values, values)
    assert kappa is None or kappa == 1.0


@given(two_codings())
def test_two_coder_alpha_and_kappa_agree_on_perfect_agreement(
    coding: tuple[list[str], list[str]],
) -> None:
    first, second = coding
    alpha = krippendorff_alpha(list(zip(first, second, strict=True)), "nominal", CATEGORIES)
    if alpha is not None and alpha == 1.0:
        assert first == second


@given(two_codings())
def test_every_score_is_a_proportion_and_scikit_learns(
    coding: tuple[list[str], list[str]],
) -> None:
    gold, predicted = coding
    scores = classify_scores(gold, predicted, CATEGORIES)
    for average, mine in (
        ("micro", (scores.micro_precision, scores.micro_recall, scores.micro_f1)),
        ("macro", (scores.macro_precision, scores.macro_recall, scores.macro_f1)),
    ):
        theirs = precision_recall_fscore_support(
            gold, predicted, labels=CATEGORIES, average=average, zero_division=0.0
        )[:3]
        assert all(
            math.isclose(m, float(t), abs_tol=1e-9) for m, t in zip(mine, theirs, strict=True)
        )
        assert all(0.0 <= m <= 1.0 for m in mine)
    for score in scores.classes:
        for value, interval in (
            (score.precision, score.precision_interval),
            (score.recall, score.recall_interval),
        ):
            assert (value is None) == (interval is None)
            if value is not None and interval is not None:
                assert interval[0] <= value <= interval[1]


@given(st.integers(0, 500), st.integers(1, 500), st.integers(2, 5))
def test_wilson_narrows_with_more_trials(successes: int, trials: int, factor: int) -> None:
    assume(successes <= trials)
    low, high = wilson_interval(successes, trials)
    wider_low, wider_high = wilson_interval(successes * factor, trials * factor)
    assert high - low >= wider_high - wider_low - 1e-12


judged = st.dictionaries(
    st.sampled_from([f"d{i}" for i in range(12)]),
    st.sampled_from([0.0, 1.0, 2.0, 3.0]),
    min_size=1,
    max_size=12,
)


@given(judged, st.integers(1, 15))
def test_the_ideal_ranking_has_ndcg_one(gains: dict[str, float], k: int) -> None:
    ideal = sorted(gains, key=lambda doc: -gains[doc])
    value = ndcg_at_k(ideal, gains, k)
    if any(gain > 0 for gain in gains.values()):
        assert value is not None and math.isclose(value, 1.0)
    else:
        assert value is None


@given(judged, st.integers(1, 15), st.randoms(use_true_random=False))
def test_ndcg_is_scikit_learns_for_any_ranking_of_the_judged(
    gains: dict[str, float], k: int, rng: random.Random
) -> None:
    assume(any(gain > 0 for gain in gains.values()))
    docs = sorted(gains)
    ranking = rng.sample(docs, len(docs))
    score = {doc: float(len(ranking) - i) for i, doc in enumerate(ranking)}  # keine Gleichstände
    expected = (
        ndcg_score([[gains[d] for d in docs]], [[score[d] for d in docs]], k=k)
        if len(docs) > 1
        else 1.0
    )
    value = ndcg_at_k(ranking, gains, k)
    assert value is not None and math.isclose(value, float(expected), abs_tol=1e-9)


# --- deal.cases: hypothesis greift die Verträge direkt an (wie test_contract_cases.py) -------------

COUNT = 200


@deal.cases(wilson_interval, count=COUNT, check_types=False)
def test_wilson_interval_contract(case: deal.TestCase) -> None:
    case()


@deal.cases(
    cohen_kappa,
    count=COUNT,
    check_types=False,
    kwargs={"first": st.lists(labels, max_size=12), "second": st.lists(labels, max_size=12)},
)
def test_cohen_kappa_contract(case: deal.TestCase) -> None:
    case()


@deal.cases(
    agreement,
    count=COUNT,
    check_types=False,
    kwargs={"first": st.lists(labels, max_size=12), "second": st.lists(labels, max_size=12)},
)
def test_agreement_contract(case: deal.TestCase) -> None:
    case()


@deal.cases(
    ndcg_at_k,
    count=COUNT,
    check_types=False,
    kwargs={
        "ranking": st.lists(st.sampled_from([f"d{i}" for i in range(8)]), max_size=8),
        "gains": st.dictionaries(st.text(max_size=3), st.floats(allow_nan=True)),
    },
)
def test_ndcg_contract(case: deal.TestCase) -> None:
    case()


@deal.cases(
    krippendorff_alpha,
    count=COUNT,
    check_types=False,
    kwargs={"units": coded_units, "level": levels, "categories": st.just(CATEGORIES)},
)
def test_krippendorff_alpha_contract(case: deal.TestCase) -> None:
    case()
