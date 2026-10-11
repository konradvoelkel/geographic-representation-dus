from __future__ import annotations

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.hits import hits_by_district, join_voters
from georep.search.index import build_index
from tests.property.oracle_matcher import oracle_extract

TERMS = ["kö", "kö-bogen", "straße", "hofgarten", "am wehrhahn", "wehrhahn", "ölberg"]
ids = st.lists(
    st.text(alphabet="abc", min_size=1, max_size=3).map(lambda s: f"p{s}"),
    min_size=0,
    max_size=6,
    unique=True,
)
index_rows = st.dictionaries(st.sampled_from(TERMS), ids, min_size=1, max_size=len(TERMS))
dictionary_rows = st.dictionaries(
    st.integers(1, 4),
    st.lists(st.sampled_from(TERMS), min_size=1, max_size=5, unique=True),
    min_size=1,
    max_size=4,
)


def _index(rows: dict[str, list[str]]) -> pl.DataFrame:
    terms = sorted(rows)
    return pl.DataFrame(
        {
            "suchbegriffe": terms,
            "paper_ids": [sorted(rows[t]) for t in terms],
            "anzahl_treffer": [len(rows[t]) for t in terms],
        },
        schema={
            "suchbegriffe": pl.String,
            "paper_ids": pl.List(pl.String),
            "anzahl_treffer": pl.Int64,
        },
    )


@given(
    dictionary=dictionary_rows, index=index_rows, hidden=st.sets(st.sampled_from(TERMS), max_size=2)
)
def test_hits_count_unique_documents_and_hide_only_in_display(
    dictionary: dict[int, list[str]], index: dict[str, list[str]], hidden: set[str]
) -> None:
    dict_df = pl.DataFrame(
        {
            "wahlkreis_id": list(dictionary),
            "suchbegriffe": [sorted(v) for v in dictionary.values()],
        },
        schema={"wahlkreis_id": pl.Int64, "suchbegriffe": pl.List(pl.String)},
    )
    overlap = {d: [t for t in terms if t in index] for d, terms in dictionary.items()}
    if not any(overlap.values()):
        return  # leere Schnittmenge ist ein Domänenfehler, separat getestet
    hits = hits_by_district(dict_df, _index(index), hidden)
    assert hits["wahlkreis_id"].to_list() == sorted(d for d, t in overlap.items() if t)
    for row in hits.iter_rows(named=True):
        terms = overlap[row["wahlkreis_id"]]
        union = {pid for t in terms for pid in index[t]}
        assert set(row["paper_ids"]) == union and row["anzahl_treffer"] == len(union)
        assert row["suchbegriffe"] == sorted(set(terms) - hidden)
    voters = pl.DataFrame(
        {"wahlkreis_id": list(dictionary), "Wahlberechtigte_insgesamt": [100] * len(dictionary)},
        schema={"wahlkreis_id": pl.Int64, "Wahlberechtigte_insgesamt": pl.Int64},
    )
    results = join_voters(hits, voters, "Wahlberechtigte_insgesamt")
    assert (results["trefferquote"] >= 0).all() and (
        results["trefferquote"] == results["anzahl_treffer"] / 100
    ).all()


texts = st.lists(
    st.sampled_from(
        ["kö", "kö-bogen", "straße", "hofgarten", "am wehrhahn", "ölberg", "x", "straßenbahn"]
    ),
    max_size=6,
).map(" ".join)


@given(
    corpus=st.dictionaries(
        st.text(alphabet="abc", min_size=1, max_size=3), texts, min_size=1, max_size=8
    ),
    terms=st.sets(st.sampled_from(TERMS), min_size=1),
)
def test_index_matches_the_oracle_per_document(corpus: dict[str, str], terms: set[str]) -> None:
    frame = pl.DataFrame(
        {"id": list(corpus), "text": list(corpus.values())},
        schema={"id": pl.String, "text": pl.String},
    )
    expected = {
        t: sorted(i for i, text in corpus.items() if t in oracle_extract(text, terms))
        for t in sorted(terms)
    }
    if not any(expected.values()):
        return
    index = build_index(frame, sorted(terms))
    assert index["suchbegriffe"].to_list() == sorted(terms)
    assert {r["suchbegriffe"]: r["paper_ids"] for r in index.iter_rows(named=True)} == expected
    assert index["anzahl_treffer"].to_list() == [len(expected[t]) for t in sorted(terms)]
