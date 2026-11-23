"""Die Maße der Validierung gegen Rechnungen von Hand, Krippendorffs Beispiele und scikit-learn.

scikit-learn steht hier als Gegenprobe, nicht als Abhängigkeit des Pakets: im Paket darf es nur in
zwei Modulen von ``analysis/`` stehen (``test_dependency_boundary.py``).
"""

from __future__ import annotations

import math

import deal
import pytest
from sklearn.metrics import (
    cohen_kappa_score,
    confusion_matrix,
    ndcg_score,
    precision_recall_fscore_support,
)

from georep.validation.measures import (
    agreement,
    classify_scores,
    cohen_kappa,
    krippendorff_alpha,
    ndcg_at_k,
    stratified_share,
    wilson_interval,
)

# --- Wilson: von Hand gerechnet, z = 1,96 (gerundet auf vier Stellen) -----------------------------


def test_wilson_eight_of_ten_by_hand() -> None:
    # p = 0,8; z² = 3,8415; Nenner 1 + z²/n = 1,38415; Mitte (0,8 + 0,19207) / 1,38415 = 0,71674;
    # halbe Breite 1,96 · √(0,016 + 0,0096037) / 1,38415 = 0,22658 -> [0,4902; 0,9433]
    low, high = wilson_interval(8, 10)
    assert (round(low, 4), round(high, 4)) == (0.4902, 0.9433)


def test_wilson_at_the_edges_reaches_zero_and_one_exactly() -> None:
    # 0 von 10: die obere Grenze ist z² / (n + z²) = 3,8415 / 13,8415 = 0,2775
    assert wilson_interval(0, 10)[0] == 0.0
    assert round(wilson_interval(0, 10)[1], 4) == 0.2775
    assert wilson_interval(10, 10)[1] == 1.0
    assert round(wilson_interval(10, 10)[0], 4) == 0.7225


def test_wilson_needs_a_proportion() -> None:
    with pytest.raises(deal.PreContractError):
        wilson_interval(3, 2)
    with pytest.raises(deal.PreContractError):
        wilson_interval(0, 0)


# --- Krippendorffs α: die Rechenbeispiele aus Krippendorff (2011), „Computing Krippendorff's
# Alpha-Reliability", Annenberg School for Communication, Departmental Papers 43 --------------------


def test_alpha_binary_two_coders_is_krippendorffs_example_a() -> None:
    a = "0100000010"
    b = "1110010000"
    alpha = krippendorff_alpha(list(zip(a, b, strict=True)), "nominal", ["0", "1"])
    # o_01 = 4, n_0 = 14, n_1 = 6, n = 20: 1 − 19 · 8 / (2 · 14 · 6) = 0,0952
    assert alpha is not None and round(alpha, 3) == 0.095


def test_alpha_nominal_two_coders_is_krippendorffs_example_b() -> None:
    # Beispiel B: Kodierer A a a b b d c c c e d d a, Kodierer B b a b b b c c c e d d d
    a = "aabbdcccedda"
    b = "babbbccceddd"
    alpha = krippendorff_alpha(list(zip(a, b, strict=True)), "nominal", list("abcde"))
    # 6 Paare uneinig, Σ n_c² = 128 bei n = 24: 1 − 23 · 6 / (576 − 128) = 0,692
    assert alpha is not None and round(alpha, 3) == 0.692


KRIPPENDORFF_C: list[tuple[str | None, ...]] = [
    # vier Beobachter, zwölf Einheiten, Werte 1 bis 5, fehlende als None (Beispiel C)
    ("1", "1", None, "1"),
    ("2", "2", "3", "2"),
    ("3", "3", "3", "3"),
    ("3", "3", "3", "3"),
    ("2", "2", "2", "2"),
    ("1", "2", "3", "4"),
    ("4", "4", "4", "4"),
    ("1", "1", "2", "1"),
    ("2", "2", "2", "2"),
    (None, "5", "5", "5"),
    (None, None, "1", "1"),
    (None, "3", None, None),
]


@pytest.mark.parametrize(
    ("level", "expected"), [("nominal", 0.743), ("ordinal", 0.815), ("interval", 0.849)]
)
def test_alpha_with_missing_values_is_krippendorffs_example_c(level: str, expected: float) -> None:
    alpha = krippendorff_alpha(KRIPPENDORFF_C, level, ["1", "2", "3", "4", "5"])  # type: ignore[arg-type]
    assert alpha is not None and round(alpha, 3) == expected


def test_alpha_ignores_units_with_a_single_value() -> None:
    without = [unit for unit in KRIPPENDORFF_C if sum(v is not None for v in unit) >= 2]
    categories = ["1", "2", "3", "4", "5"]
    assert krippendorff_alpha(without, "ordinal", categories) == krippendorff_alpha(
        KRIPPENDORFF_C, "ordinal", categories
    )


def test_alpha_is_undefined_without_variation() -> None:
    assert krippendorff_alpha([("x", "x"), ("x", "x")], "nominal", ["x", "y"]) is None
    assert krippendorff_alpha([("x", None)], "nominal", ["x"]) is None


def test_alpha_ordinal_counts_the_order_of_the_categories() -> None:
    # Dieselbe Uneinigkeit wiegt ordinal schwerer, wenn die Kategorien weit auseinander liegen.
    near = [("1", "2"), ("2", "2"), ("3", "3"), ("1", "1"), ("3", "3")]
    far = [("1", "3"), ("2", "2"), ("3", "3"), ("1", "1"), ("2", "2")]
    categories = ["1", "2", "3"]
    alpha_near = krippendorff_alpha(near, "ordinal", categories)
    alpha_far = krippendorff_alpha(far, "ordinal", categories)
    assert alpha_near is not None and alpha_far is not None and alpha_near > alpha_far


def test_alpha_rejects_a_value_outside_the_categories() -> None:
    with pytest.raises(deal.PreContractError):
        krippendorff_alpha([("a", "z")], "nominal", ["a", "b"])
    with pytest.raises(deal.PreContractError):
        krippendorff_alpha([("a", "b")], "interval", ["a", "b"])


# --- Cohens κ und Übereinstimmung -----------------------------------------------------------------

FIRST = ["ja", "ja", "nein", "ja", "nein", "nein", "ja", "ja", "nein", "ja"]
SECOND = ["ja", "nein", "nein", "ja", "nein", "ja", "ja", "ja", "nein", "ja"]


def test_kappa_by_hand_and_as_scikit_learn() -> None:
    # p_o = 8/10; A: 6 ja, 4 nein; B: 6 ja, 4 nein; p_e = 0,36 + 0,16 = 0,52;
    # κ = (0,8 − 0,52) / (1 − 0,52) = 0,5833
    kappa = cohen_kappa(FIRST, SECOND)
    assert kappa is not None and round(kappa, 4) == 0.5833
    assert kappa == pytest.approx(cohen_kappa_score(FIRST, SECOND), abs=1e-12)


def test_kappa_is_undefined_when_both_always_say_the_same() -> None:
    assert cohen_kappa(["ja"] * 5, ["ja"] * 5) is None
    assert cohen_kappa(["ja"] * 5, ["nein"] * 5) == 0.0


def test_agreement_is_a_share_of_units() -> None:
    assert agreement(FIRST, SECOND) == 0.8
    assert agreement([], []) is None


# --- Präzision, Recall, F1 gegen scikit-learn -----------------------------------------------------

GOLD = ["a", "a", "b", "c", "c", "c", "b", "a", "c", "b", "a"]
PRED = ["a", "b", "b", "c", "a", "c", "b", "a", "a", "b", "a"]
LABELS = ["a", "b", "c", "d"]  # d kommt nie vor: undefiniert, im Makromittel 0


def test_per_class_scores_are_scikit_learns() -> None:
    scores = classify_scores(GOLD, PRED, LABELS)
    precision, recall, f1, support = precision_recall_fscore_support(
        GOLD, PRED, labels=LABELS, zero_division=0.0
    )
    for i, label in enumerate(LABELS):
        mine = scores.of(label)
        assert (mine.precision or 0.0) == pytest.approx(precision[i])
        assert (mine.recall or 0.0) == pytest.approx(recall[i])
        assert (mine.f1 or 0.0) == pytest.approx(f1[i])
        assert mine.support == support[i]
    assert scores.of("d").precision is None and scores.of("d").recall is None


@pytest.mark.parametrize("average", ["micro", "macro"])
def test_averages_are_scikit_learns(average: str) -> None:
    scores = classify_scores(GOLD, PRED, LABELS)
    # Befund 5: das Makromittel zählt nur Klassen mit Gold oder Vorhersage, „d" also nicht
    present = ["a", "b", "c"]
    precision, recall, f1, _ = precision_recall_fscore_support(
        GOLD, PRED, labels=present, average=average, zero_division=0.0
    )
    mine = (
        (scores.micro_precision, scores.micro_recall, scores.micro_f1)
        if average == "micro"
        else (scores.macro_precision, scores.macro_recall, scores.macro_f1)
    )
    assert mine == pytest.approx((precision, recall, f1))


def test_confusion_matrix_is_scikit_learns() -> None:
    scores = classify_scores(GOLD, PRED, LABELS)
    assert [list(row) for row in scores.confusion] == confusion_matrix(
        GOLD, PRED, labels=LABELS
    ).tolist()


def test_proportions_carry_their_wilson_interval() -> None:
    scores = classify_scores(GOLD, PRED, LABELS)
    a = scores.of("a")
    # a: 3 von 5 Vorhersagen richtig, 3 von 4 Goldlabels gefunden; 8 von 11 Einheiten richtig
    assert (a.true_positive, a.predicted, a.support) == (3, 5, 4)
    assert a.precision_interval == wilson_interval(3, 5)
    assert a.recall_interval == wilson_interval(3, 4)
    assert scores.accuracy_interval == wilson_interval(8, 11)


def test_scores_reject_an_unknown_label() -> None:
    with pytest.raises(deal.PreContractError):
        classify_scores(["a"], ["x"], ["a", "b"])


# --- nDCG@k gegen scikit-learn ---------------------------------------------------------------------


def test_ndcg_is_scikit_learns_when_every_judged_document_is_ranked() -> None:
    gains = {"d1": 2.0, "d2": 0.0, "d3": 1.0, "d4": 2.0, "d5": 0.0, "d6": 1.0}
    scores = {"d1": 0.3, "d2": 0.9, "d3": 0.8, "d4": 0.1, "d5": 0.5, "d6": 0.7}
    docs = sorted(gains)
    for k in (1, 3, 5, 10):
        expected = ndcg_score([[gains[d] for d in docs]], [[scores[d] for d in docs]], k=k)
        assert ndcg_at_k(scores, gains, k) == pytest.approx(expected)


def test_ndcg_averages_ties_like_scikit_learn() -> None:
    """Befund 4: gleiche Punktzahlen bekommen das Mittel ihrer Ränge, wie ``ndcg_score``."""
    gains = {"d1": 2.0, "d2": 0.0, "d3": 1.0, "d4": 2.0}
    scores = {"d1": 0.5, "d2": 0.5, "d3": 0.5, "d4": 0.1}
    docs = sorted(gains)
    for k in (1, 2, 3, 4):
        expected = ndcg_score([[gains[d] for d in docs]], [[scores[d] for d in docs]], k=k)
        assert ndcg_at_k(scores, gains, k) == pytest.approx(expected)


def test_ndcg_counts_only_judged_documents() -> None:
    """Befund 4: ein ungeurteiltes Dokument vorn drückt die Zahl nicht; ein geurteiltes ohne
    Punktzahl steht hinten."""
    gains = {"d1": 1.0, "d2": 0.0}
    assert ndcg_at_k({"x": 9.0, "d1": 1.0, "d2": 0.5}, gains, 1) == 1.0
    assert ndcg_at_k({"d2": 1.0}, gains, 2) == pytest.approx(1 / math.log2(3))


def test_ndcg_is_undefined_without_a_relevant_document() -> None:
    assert ndcg_at_k({"d1": 1.0}, {"d1": 0.0}, 5) is None
    assert ndcg_at_k({"d1": 1.0}, {}, 5) is None


def test_ndcg_rejects_scores_that_are_not_finite() -> None:
    with pytest.raises(deal.PreContractError):
        ndcg_at_k({"d1": float("nan")}, {"d1": 1.0}, 5)


# --- Gewichte: geschichteter Schätzer (Befund 1) ----------------------------------------------------


def test_stratified_share_by_hand_is_project_14s_weighted_precision() -> None:
    """Die Kantenpräzision von Vorhaben 14, gewichtet mit den Schichtgrößen (Messdokument § 4.1)."""
    hits = {
        "mg": (12, 15),
        "periode": (10, 10),
        "antwort": (25, 25),
        "nachfrage": (14, 15),
        "umsetzung": (21, 25),
        "aenderung": (18, 20),
        "nachtrag": (10, 10),
        "bau": (5, 5),
        "bezug_titel": (12, 12),
        "bezug_text": (12, 13),
    }
    sizes = {
        "mg": 387,
        "periode": 2599,
        "antwort": 272,
        "nachfrage": 303,
        "umsetzung": 2915,
        "aenderung": 657,
        "nachtrag": 301,
        "bau": 22,
        "bezug_titel": 438,
        "bezug_text": 6976,
    }
    result = stratified_share(hits, sizes)
    assert round(result.estimate, 3) == 0.922 and result.population == 14870
    # Kish: n_eff = N² / Σ N_h²/m_h, deutlich unter 150, weil bezug_text 47 % mit 13 Kanten trägt
    expected = 14870**2 / sum(sizes[h] ** 2 / m for h, (_, m) in hits.items())
    assert result.effective_n == pytest.approx(expected) and result.effective_n < 60
    low, high = result.interval
    assert (
        low < 0.922 < high
        and high - low > wilson_interval(139, 150)[1] - wilson_interval(139, 150)[0]
    )


def test_a_self_weighting_sample_gives_the_plain_share_and_wilson() -> None:
    hits = {"a": (9, 10), "b": (2, 5)}
    result = stratified_share(hits, {"a": 100, "b": 50})
    assert result.estimate == pytest.approx(11 / 15) and result.effective_n == pytest.approx(15)
    assert result.interval == pytest.approx(wilson_interval(11, 15))
