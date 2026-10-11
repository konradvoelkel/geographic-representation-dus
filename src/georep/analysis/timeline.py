"""Monatsreihe: Dokumente je Monat, stadtweit und je Wahlbezirk.

Zwei reine Polars-Funktionen (Frame zu Frame, keine Pfade) für den Schritt ``timeline``:
``monthly_series`` zählt je Monat die Dokumente des Korpus, die mit Text und die mit mindestens
einem Treffer; ``district_months`` zerlegt die Treffer je Wahlbezirk nach Monat. Der Monat ist
immer der Monatserste (``dt.truncate("1mo")``); Dokumente ohne Datum stehen in einer Zeile mit
leerem Monat am Ende, weil sie zur Summe gehören, aber zu keinem Monat.

Die Zählung ist dieselbe wie in ``analysis.hits``: ein Dokument zählt je Wahlbezirk einmal, auch
wenn mehrere Begriffe des Bezirks vorkommen. Die Nachbedingung von ``district_months`` prüft das
gegen ``hits_by_district`` (Option 07, docs/plans/07-monitoring.md § 5, Stufe C).
"""

from __future__ import annotations

import deal
import polars as pl

from georep.analysis.hits import DISTRICT, TERMS, hits_by_district
from georep.contracts import all_nonnegative, has_columns, keys_sorted_unique, months_in_order
from georep.search.index import HITS, PAPER_IDS, TERM

MONTH = "monat"
DOCUMENTS = "dokumente"
WITH_TEXT = "mit_text"
WITH_HITS = "mit_treffer"
ID = "id"
DATE = "date"

# Die Spalten, die beide Funktionen vom Korpus brauchen; ``mit_text`` ist ``text != ""``.
CORPUS_META = (ID, DATE, WITH_TEXT)
MONTHLY_SCHEMA = {MONTH: pl.Date, DOCUMENTS: pl.Int64, WITH_TEXT: pl.Int64, WITH_HITS: pl.Int64}
DISTRICT_MONTHS_SCHEMA = {DISTRICT: pl.Int64, MONTH: pl.Date, HITS: pl.Int64}


def _counts_are_nested(frame: pl.DataFrame) -> bool:
    """Je Monat: mit Treffer höchstens mit Text, mit Text höchstens Dokumente."""
    return bool(
        (
            (frame.get_column(WITH_HITS) <= frame.get_column(WITH_TEXT))
            & (frame.get_column(WITH_TEXT) <= frame.get_column(DOCUMENTS))
        ).all()
    )


def _covers_the_whole_corpus(
    corpus_meta: pl.DataFrame, index: pl.DataFrame, result: pl.DataFrame | None = None
) -> bool:
    assert result is not None
    return int(result.get_column(DOCUMENTS).sum()) == corpus_meta.height


def _hits_come_from_documents_with_text(corpus_meta: pl.DataFrame, index: pl.DataFrame) -> bool:
    """Der Index entsteht aus dem Korpustext: ein getroffenes Dokument steht im Korpus und hat Text."""
    hit = set(index.get_column(PAPER_IDS).explode().drop_nulls().to_list())
    return hit <= set(corpus_meta.filter(pl.col(WITH_TEXT)).get_column(ID).to_list())


# deal prüft die innerste Vorbedingung zuerst: der Spaltentest steht unten, damit die Prädikate
# darüber sich auf die Spalten verlassen können.
@deal.pre(_hits_come_from_documents_with_text, message="jedes getroffene Dokument hat Text")
@deal.pre(
    lambda corpus_meta, index: (
        has_columns(corpus_meta, *CORPUS_META) and has_columns(index, TERM, PAPER_IDS)
    ),
    message="Korpus mit id, date und mit_text; Index mit Begriff und Dokument-IDs",
)
@deal.post(lambda result: result.columns == list(MONTHLY_SCHEMA))
@deal.post(lambda result: months_in_order(result, MONTH))
@deal.post(lambda result: all_nonnegative(result, DOCUMENTS, WITH_TEXT, WITH_HITS))
@deal.post(_counts_are_nested, message="mit_treffer <= mit_text <= dokumente")
@deal.ensure(
    _covers_the_whole_corpus, message="jedes Dokument des Korpus zählt in genau einem Monat"
)
def monthly_series(corpus_meta: pl.DataFrame, index: pl.DataFrame) -> pl.DataFrame:
    """Monat (Monatserster), Dokumente, mit Text, mit Treffer; lückenlos vom ersten bis zum letzten."""
    hit_ids = index.get_column(PAPER_IDS).explode().drop_nulls().unique().implode()
    counted = (
        corpus_meta.with_columns(
            pl.col(DATE).dt.truncate("1mo").alias(MONTH),
            pl.col(ID).is_in(hit_ids).alias(WITH_HITS),
        )
        .group_by(MONTH)
        .agg(
            pl.len().cast(pl.Int64).alias(DOCUMENTS),
            pl.col(WITH_TEXT).sum().cast(pl.Int64),
            pl.col(WITH_HITS).sum().cast(pl.Int64),
        )
        .select(list(MONTHLY_SCHEMA))
    )
    dated = counted.filter(pl.col(MONTH).is_not_null()).sort(MONTH)
    undated = counted.filter(pl.col(MONTH).is_null())
    if dated.is_empty():
        return undated
    months = pl.date_range(
        dated.get_column(MONTH).min(),  # type: ignore[arg-type]
        dated.get_column(MONTH).max(),  # type: ignore[arg-type]
        interval="1mo",
        eager=True,
    ).alias(MONTH)
    gapless = (
        pl.DataFrame([months])
        .join(dated, on=MONTH, how="left")
        .with_columns(pl.col(DOCUMENTS, WITH_TEXT, WITH_HITS).fill_null(0))
        .sort(MONTH)
    )
    return pl.concat([gapless, undated]) if not undated.is_empty() else gapless


def _index_belongs_to_the_corpus(
    dictionary: pl.DataFrame, index: pl.DataFrame, corpus_meta: pl.DataFrame
) -> bool:
    documents = set(index.get_column(PAPER_IDS).explode().drop_nulls().to_list())
    return documents <= set(corpus_meta.get_column(ID).to_list())


def _sums_match_hits_by_district(
    dictionary: pl.DataFrame,
    index: pl.DataFrame,
    corpus_meta: pl.DataFrame,
    result: pl.DataFrame | None = None,
) -> bool:
    """Je Wahlbezirk summieren die Monate zu den Treffern aus ``hits_by_district``.

    Ein Wahlbezirk ohne Treffer steht dort mit 0 und hier mit keiner Zeile: eine Zeile je Monat
    gibt es nur, wenn im Monat ein Dokument getroffen wurde.
    """
    assert result is not None
    if result.is_empty():
        return True  # ohne Schnittmenge wirft hits_by_district; dann gibt es auch keine Zeile
    got = result.group_by(DISTRICT).agg(pl.col(HITS).sum().alias("summe"))
    both = (
        hits_by_district(dictionary, index)
        .select(DISTRICT, HITS)
        .join(got, on=DISTRICT, how="left")
        .with_columns(pl.col("summe").fill_null(0))
    )
    extra = set(got.get_column(DISTRICT)) - set(both.get_column(DISTRICT))
    return not extra and bool((both.get_column(HITS) == both.get_column("summe")).all())


@deal.pre(_index_belongs_to_the_corpus, message="jede Dokument-ID des Index steht im Korpus")
@deal.pre(
    lambda dictionary, index, corpus_meta: (
        has_columns(dictionary, DISTRICT, TERMS)
        and has_columns(index, TERM, PAPER_IDS)
        and has_columns(corpus_meta, ID, DATE)
    )
)
@deal.post(lambda result: result.columns == list(DISTRICT_MONTHS_SCHEMA))
@deal.post(lambda result: keys_sorted_unique(result, DISTRICT, MONTH))
@deal.post(
    lambda result: bool((result.get_column(HITS) > 0).all()),
    message="jede Zeile zählt mindestens ein Dokument",
)
@deal.ensure(_sums_match_hits_by_district, message="die Monate summieren zu hits_by_district")
def district_months(
    dictionary: pl.DataFrame, index: pl.DataFrame, corpus_meta: pl.DataFrame
) -> pl.DataFrame:
    """Wahlbezirk, Monat, Dokumente mit Treffer in einem Begriff des Bezirks (je Dokument einmal)."""
    months = corpus_meta.select(ID, pl.col(DATE).dt.truncate("1mo").alias(MONTH))
    return (
        dictionary.select(DISTRICT, TERMS)
        .explode(TERMS)
        .join(index.select(TERM, PAPER_IDS), left_on=TERMS, right_on=TERM, how="inner")
        .select(DISTRICT, PAPER_IDS)
        .explode(PAPER_IDS)
        .drop_nulls(PAPER_IDS)
        .unique()
        .join(months, left_on=PAPER_IDS, right_on=ID, how="inner")
        .group_by(DISTRICT, MONTH)
        .agg(pl.len().cast(pl.Int64).alias(HITS))
        .sort([DISTRICT, MONTH], nulls_last=True)
        .select(list(DISTRICT_MONTHS_SCHEMA))
    )
