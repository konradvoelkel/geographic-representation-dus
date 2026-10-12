"""Eigenschaften der Monatsreihe (Option 07) über zufälligen Korpora und Indizes.

Die Daten werden so gezogen, wie die Kette sie liefert: Treffer gibt es nur zu Dokumenten des
Korpus, die Text haben (der Index entsteht aus dem Korpustext).
"""

from __future__ import annotations

import datetime as dt

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.timeline import district_months, monthly_series
from georep.contracts import months_in_order, next_month

DOCUMENT_IDS = [f"p{i}" for i in range(8)]
TERM_NAMES = ["allee", "weg", "platz"]


@st.composite
def corpora(draw: st.DrawFn) -> pl.DataFrame:
    ids = draw(st.lists(st.sampled_from(DOCUMENT_IDS), min_size=1, max_size=8, unique=True))
    dates = draw(
        st.lists(
            st.one_of(st.none(), st.dates(dt.date(2025, 1, 1), dt.date(2026, 12, 31))),
            min_size=len(ids),
            max_size=len(ids),
        )
    )
    texts = draw(st.lists(st.booleans(), min_size=len(ids), max_size=len(ids)))
    return pl.DataFrame(
        {"id": ids, "date": dates, "mit_text": texts},
        schema={"id": pl.String, "date": pl.Date, "mit_text": pl.Boolean},
    )


@st.composite
def dictionaries(draw: st.DrawFn) -> pl.DataFrame:
    districts = draw(st.lists(st.integers(1, 4), min_size=1, max_size=4, unique=True))
    terms = [
        draw(st.lists(st.sampled_from(TERM_NAMES), min_size=0, max_size=3, unique=True))
        for _ in districts
    ]
    return pl.DataFrame(
        {"wahlkreis_id": sorted(districts), "suchbegriffe": terms},
        schema={"wahlkreis_id": pl.Int64, "suchbegriffe": pl.List(pl.String)},
    )


def _index_for(corpus: pl.DataFrame, picks: list[list[int]]) -> pl.DataFrame:
    """Ein Index über die Dokumente mit Text; ``picks`` wählt je Begriff Positionen daraus."""
    with_text = corpus.filter(pl.col("mit_text")).get_column("id").to_list()
    lists = [
        sorted({with_text[i % len(with_text)] for i in pick}) if with_text else [] for pick in picks
    ]
    return pl.DataFrame(
        {
            "suchbegriffe": TERM_NAMES,
            "paper_ids": lists,
            "anzahl_treffer": [len(items) for items in lists],
        },
        schema={
            "suchbegriffe": pl.String,
            "paper_ids": pl.List(pl.String),
            "anzahl_treffer": pl.Int64,
        },
    )


picks_st = st.lists(
    st.lists(st.integers(0, 7), max_size=4), min_size=len(TERM_NAMES), max_size=len(TERM_NAMES)
)


@given(corpus=corpora(), picks=picks_st)
def test_monthly_series_counts_every_document_exactly_once(
    corpus: pl.DataFrame, picks: list[list[int]]
) -> None:
    index = _index_for(corpus, picks)
    frame = monthly_series(corpus, index)
    assert int(frame.get_column("dokumente").sum()) == corpus.height
    assert int(frame.get_column("mit_text").sum()) == int(corpus.get_column("mit_text").sum())
    hit = set(index.get_column("paper_ids").explode().drop_nulls().to_list())
    assert int(frame.get_column("mit_treffer").sum()) == len(hit)
    assert months_in_order(frame, "monat")
    months = [m for m in frame.get_column("monat").to_list() if m is not None]
    dated = corpus.get_column("date").drop_nulls().to_list()
    if dated:
        assert months[0] == min(dated).replace(day=1)
        assert next_month(months[-1]) == next_month(max(dated).replace(day=1))
    else:
        assert months == []


@given(corpus=corpora(), dictionary=dictionaries(), picks=picks_st)
def test_district_months_decompose_the_hits_of_each_district(
    corpus: pl.DataFrame, dictionary: pl.DataFrame, picks: list[list[int]]
) -> None:
    index = _index_for(corpus, picks)
    frame = district_months(dictionary, index, corpus)
    by_term = dict(
        zip(index.get_column("suchbegriffe"), index.get_column("paper_ids"), strict=True)
    )
    for district, terms in dictionary.rows():
        documents: set[str] = set()
        for term in terms:
            documents |= set(by_term.get(term, []))
        mine = frame.filter(pl.col("wahlkreis_id") == district)
        assert int(mine.get_column("anzahl_treffer").sum()) == len(documents)
        # Je Monat höchstens so viele Dokumente, wie der Korpus in diesem Monat hat
        assert mine.height <= len(documents)
