"""Vorhaben 18: Eigenschaften der Wortsuche und der Mischung über beliebige Texte und Listen."""

from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from georep.search.bm25 import Tokenizer, bm25_scores, build_index, count_terms, ranking, rrf
from georep.search.stem import stem

WORDS = st.sampled_from(["rad", "radweg", "radwege", "schule", "schulen", "und", "der", "baum"])
TEXTS = st.lists(st.lists(WORDS, max_size=8).map(" ".join), min_size=1, max_size=8)
IDS = st.sampled_from([f"d{i}" for i in range(12)])
LISTS = st.lists(IDS, unique=True, max_size=12)


@given(first=LISTS, second=LISTS, k=st.integers(0, 80), depth=st.integers(0, 12))
def test_rrf_is_symmetric_in_its_lists(
    first: list[str], second: list[str], k: int, depth: int
) -> None:
    assert rrf([first, second], k, depth) == rrf([second, first], k, depth)


@given(lists=st.lists(LISTS, max_size=4), k=st.integers(1, 80), depth=st.integers(0, 12))
def test_rrf_holds_exactly_the_units_within_depth(
    lists: list[list[str]], k: int, depth: int
) -> None:
    fused = rrf(lists, k, depth)
    assert {unit for unit, _ in fused} == {unit for listing in lists for unit in listing[:depth]}
    assert all(score > 0 for _, score in fused)


@given(texts=TEXTS, query=st.lists(WORDS, max_size=4).map(" ".join))
def test_bm25_scores_exactly_the_units_with_a_query_token(texts: list[str], query: str) -> None:
    tokenize = Tokenizer()
    index = build_index([f"d{i}" for i in range(len(texts))], count_terms(texts, tokenize))
    scores = bm25_scores(index, tokenize(query), 1.2, 0.75)
    wanted = set(tokenize(query))
    hits = [i for i, text in enumerate(texts) if wanted & set(tokenize(text))]
    assert sorted(ranking(scores, len(texts), positive_only=True)) == hits
    assert bool(np.all(scores >= 0))


@given(word=st.text(st.sampled_from("abeinrstuyäöüß"), max_size=20))
def test_the_stem_never_grows_and_has_no_umlaut(word: str) -> None:
    assert len(stem(word)) <= len(word.replace("ß", "ss"))
    assert not set(stem(word)) & set("äöüß")
