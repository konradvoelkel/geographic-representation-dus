"""Sucheinträge: jeder Begriff genau einmal, Dokumente zwischen Maximum und Summe, Falten stabil."""

from __future__ import annotations

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.report.search import canonical_term, fold, fold_ascii, search_entries
from georep.search.dictionary import STREET_ABBREVIATIONS, build_dictionary
from tests.property.test_dictionary_props import raw_terms

LIST_OF_STR = pl.List(pl.String)
words = st.text(alphabet="abcstrßäöü .", min_size=0, max_size=14)


@given(term=words)
def test_canonical_term_is_idempotent_and_free_of_abbreviations(term: str) -> None:
    once = canonical_term(term)
    assert canonical_term(once) == once
    assert all(short not in once for _, short in STREET_ABBREVIATIONS)
    assert once == once.lower()
    if all(short not in term for _, short in STREET_ABBREVIATIONS):
        assert once == term


@given(term=st.text(max_size=20))
def test_fold_is_idempotent_trimmed_and_without_marks(term: str) -> None:
    for folding in (fold, fold_ascii):
        once = folding(term)
        assert folding(once) == once
        assert once == once.strip() and "  " not in once
        assert "ß" not in once and all(short not in once for _, short in STREET_ABBREVIATIONS)


def _frame(rows: dict[int, list[str]]) -> pl.DataFrame:
    return pl.DataFrame(
        {"wahlkreis_id": list(rows), "suchbegriffe": list(rows.values())},
        schema={"wahlkreis_id": pl.Int64, "suchbegriffe": LIST_OF_STR},
    )


@given(
    pois=st.dictionaries(st.integers(1, 4), raw_terms, min_size=1, max_size=4),
    streets=st.dictionaries(st.integers(1, 4), raw_terms, min_size=1, max_size=4),
    papers=st.data(),
)
def test_every_term_lies_under_one_entry_and_documents_are_a_union(
    pois: dict[int, list[str]], streets: dict[int, list[str]], papers: st.DataObject
) -> None:
    dictionary = build_dictionary(_frame(pois), _frame(streets))
    terms = sorted(set(dictionary.get_column("suchbegriffe").explode().drop_nulls().to_list()))
    ids = {
        t: papers.draw(st.lists(st.sampled_from(["p1", "p2", "p3"]), max_size=3, unique=True))
        for t in terms
    }
    index = pl.DataFrame(
        {
            "suchbegriffe": terms,
            "paper_ids": [ids[t] for t in terms],
            "anzahl_treffer": [len(ids[t]) for t in terms],
        },
        schema={"suchbegriffe": pl.String, "paper_ids": LIST_OF_STR, "anzahl_treffer": pl.Int64},
    )
    districts = dictionary.get_column("wahlkreis_id").to_list()
    results = pl.DataFrame(
        {"wahlkreis_id": districts, "anzahl_treffer": [1] * len(districts)},
        schema={"wahlkreis_id": pl.Int64, "anzahl_treffer": pl.Int64},
    )
    labels = pl.DataFrame(
        {"label": [t for terms in pois.values() for t in terms]}, schema={"label": pl.String}
    )
    hidden = terms[:1]
    entries = search_entries(
        dictionary,
        index,
        _frame(streets),
        labels,
        results,
        {d: f"Bezirk {d}" for d in districts},
        hidden,
    )
    shown = [t for t in terms if t not in hidden]
    targets = {t: canonical_term(t) if canonical_term(t) in shown else t for t in shown}
    by_term = {e.term: e for e in entries if e.kind != "w"}
    assert set(by_term) == set(targets.values())
    for entry in by_term.values():
        members = [t for t, target in targets.items() if target == entry.term]
        assert members
        assert (
            max(len(ids[m]) for m in members)
            <= entry.documents
            <= sum(len(ids[m]) for m in members)
        )
        assert entry.documents == len({p for m in members for p in ids[m]})
        assert set(entry.districts) == {
            d
            for d, ts in zip(
                districts, dictionary.get_column("suchbegriffe").to_list(), strict=True
            )
            if any(m in ts for m in members)
        }
    assert [e.districts for e in entries if e.kind == "w"] == [(d,) for d in districts]
