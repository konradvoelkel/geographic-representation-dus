"""Invertierter Index: je Suchbegriff die Dokumente, in denen er vorkommt.

Entspricht ``src/reverse_index.py``: alle Begriffe aller Wahlbezirke in einem Matcher, ein
Durchlauf über den Korpus, je Begriff die sortierte Menge der Dokument-IDs. Begriffe ohne
Treffer bleiben mit leerer Liste stehen; ein Index ohne jeden Treffer ist ein Fehler.
"""

from __future__ import annotations

from collections.abc import Sequence

import deal
import polars as pl

from georep.contracts import clean_terms, has_columns, lists_sorted_unique, sorted_unique
from georep.errors import EmptyResultError
from georep.search.matcher import KeywordMatcher, make_matcher

TERM = "suchbegriffe"
PAPER_IDS = "paper_ids"
HITS = "anzahl_treffer"
INDEX_SCHEMA = {TERM: pl.String, PAPER_IDS: pl.List(pl.String), HITS: pl.Int64}


def _covers_terms_with_corpus_ids(
    corpus: pl.DataFrame,
    terms: Sequence[str],
    matcher: KeywordMatcher | None = None,
    result: pl.DataFrame | None = None,
) -> bool:
    """Nachbedingung: jeder Begriff genau einmal, jede Dokument-ID stammt aus dem Korpus."""
    assert result is not None
    return result.get_column(TERM).to_list() == sorted(terms) and set(
        result.get_column(PAPER_IDS).explode().drop_nulls().to_list()
    ) <= set(corpus.get_column("id").to_list())


@deal.pre(lambda corpus, terms, matcher=None: has_columns(corpus, "id", "text"))
@deal.pre(
    lambda corpus, terms, matcher=None: (
        len(terms) > 0 and len(set(terms)) == len(terms) and clean_terms(list(terms))
    ),
    message="Begriffe nicht leer, eindeutig, kleingeschrieben und ohne Komma",
)
@deal.post(lambda result: result.columns == [TERM, PAPER_IDS, HITS])
@deal.post(lambda result: sorted_unique(result, TERM))
@deal.post(lambda result: lists_sorted_unique(result, PAPER_IDS))
@deal.post(
    lambda result: bool(
        (result.get_column(HITS) == result.get_column(PAPER_IDS).list.len().cast(pl.Int64)).all()
    ),
    message="anzahl_treffer ist die Mächtigkeit der ID-Menge",
)
@deal.ensure(_covers_terms_with_corpus_ids, message="jeder Begriff einmal, jede ID aus dem Korpus")
@deal.raises(EmptyResultError)
def build_index(
    corpus: pl.DataFrame, terms: Sequence[str], matcher: KeywordMatcher | None = None
) -> pl.DataFrame:
    """Korpus mit Spalten ``id`` und ``text``; ``terms`` eindeutig und kleingeschrieben."""
    matcher = make_matcher(terms) if matcher is None else matcher
    hits: dict[str, list[str]] = {term: [] for term in terms}
    for doc_id, text in corpus.select("id", "text").iter_rows():
        if not text:
            continue
        for term in matcher.extract(text):
            hits[term].append(doc_id)
    ordered = sorted(hits)
    frame = pl.DataFrame(
        {TERM: ordered, PAPER_IDS: [sorted(set(hits[term])) for term in ordered]},
        schema={TERM: pl.String, PAPER_IDS: pl.List(pl.String)},
    ).with_columns(pl.col(PAPER_IDS).list.len().cast(pl.Int64).alias(HITS))
    if total_hits(frame) == 0:
        raise EmptyResultError(
            f"Kein einziger der {len(terms)} Suchbegriffe kommt in {corpus.height} Dokumenten vor."
        )
    return frame


def total_hits(index: pl.DataFrame) -> int:
    total = index.get_column(HITS).sum()
    return int(total) if total is not None else 0
