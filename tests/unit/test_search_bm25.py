"""Vorhaben 18: BM25, Rangfolge und Mischung an Beispielen, gegen Rechnungen von Hand."""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pytest

from georep.search.bm25 import (
    Bm25Index,
    Tokenizer,
    bm25_scores,
    build_index,
    count_terms,
    ranking,
    rrf,
)

K1, B = 1.2, 0.75


def _index(texts: list[str]) -> tuple[Bm25Index, Tokenizer]:
    tokenize = Tokenizer()
    ids = [f"id{i}" for i in range(len(texts))]
    return build_index(ids, count_terms(texts, tokenize)), tokenize


def test_the_tokenizer_lowercases_splits_on_non_words_and_stems() -> None:
    tokenize = Tokenizer()
    assert tokenize("Radwege, Schulen und Straße!") == ["radweg", "schul", "und", "strass"]
    assert Tokenizer(stemming=False)("Radwege, Schulen") == ["radwege", "schulen"]
    assert tokenize("a_b 12\fx") == ["a_b", "12", "x"]


def test_bm25_against_a_hand_calculation_on_three_documents() -> None:
    """d0 „Rad Weg", d1 „Rad Rad", d2 „Schule"; Frage „Rad": N = 3, n = 2, mittlere Länge 5/3."""
    index, tokenize = _index(["Rad Weg", "Rad Rad", "Schule"])
    scores = bm25_scores(index, tokenize("Rad"), K1, B)
    idf = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))
    norm = K1 * (1 - B + B * 2 / (5 / 3))  # beide Rad-Dokumente haben zwei Token
    assert scores.tolist() == pytest.approx(
        [idf * 1 * (K1 + 1) / (1 + norm), idf * 2 * (K1 + 1) / (2 + norm), 0.0]
    )
    assert ranking(scores, 10, positive_only=True) == [1, 0]
    assert ranking(scores, 10) == [1, 0, 2]


def test_each_distinct_query_token_counts_once_and_unknown_tokens_count_nothing() -> None:
    index, tokenize = _index(["Rad Weg", "Rad Rad", "Schule"])
    once = bm25_scores(index, tokenize("Rad"), K1, B)
    twice = bm25_scores(index, tokenize("Rad rad Räder Unbekannt"), K1, B)
    # „Räder" stemmt zu „rad"; „unbekannt" steht in keinem Dokument
    assert twice.tolist() == once.tolist()


def test_the_matrix_counts_terms_per_unit() -> None:
    index = build_index(["a", "b"], [Counter({"x": 2, "y": 1}), Counter({"y": 3})])
    assert index.vocabulary == {"x": 0, "y": 1}
    assert index.matrix.toarray().tolist() == [[2.0, 1.0], [0.0, 3.0]]
    assert index.lengths.tolist() == [3.0, 3.0]


def test_ties_keep_the_order_of_the_units() -> None:
    values = np.asarray([0.5, 1.0, 0.5, 1.0, 0.0])
    assert ranking(values, 10) == [1, 3, 0, 2, 4]
    assert ranking(values, 3) == [1, 3, 0]
    assert ranking(values, 10, positive_only=True) == [1, 3, 0, 2]
    assert ranking(np.asarray([0.0, -1.0]), 10, positive_only=True) == []


def test_rrf_on_two_lists_by_hand() -> None:
    """k = 60: a ist Erster und Zweiter, b Zweiter und Erster, c nur in einer Liste."""
    fused = rrf([["a", "b", "c"], ["b", "a"]], 60, 100)
    # Gleichstand zwischen a und b: nach ID
    assert [unit for unit, _ in fused] == ["a", "b", "c"]
    assert [score for _, score in fused] == pytest.approx([1 / 61 + 1 / 62] * 2 + [1 / 63])


def test_rrf_reads_only_the_first_depth_of_each_list() -> None:
    fused = dict(rrf([["a", "b", "c"], ["c"]], 60, 2))
    assert fused == {"a": 1 / 61, "b": 1 / 62, "c": 1 / 61}
