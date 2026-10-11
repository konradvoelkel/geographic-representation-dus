"""Treffer je Wahlbezirk und Verknüpfung mit den Wählerdaten.

Entspricht ``src/analyse.py``: Wörterbuch auf Begriffe auflösen, mit dem Index verbinden, je
Wahlbezirk die Vereinigung der Dokument-IDs zählen; ``hide_in_display`` nimmt Begriffe nur aus
der Anzeigeliste, nicht aus der Zählung (Verhalten der Arbeit, Kapitel 4.3.5).
"""

from __future__ import annotations

from collections.abc import Iterable

import deal
import polars as pl

from georep.contracts import all_nonnegative, has_columns, lists_sorted_unique, sorted_unique
from georep.errors import EmptyResultError
from georep.search.index import HITS, PAPER_IDS, TERM

DISTRICT = "wahlkreis_id"
TERMS = "suchbegriffe"
RATE = "trefferquote"


def _only_dictionary_districts(
    dictionary: pl.DataFrame,
    index: pl.DataFrame,
    hide_in_display: Iterable[str] = (),
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return set(result.get_column(DISTRICT)) <= set(dictionary.get_column(DISTRICT))


@deal.pre(
    lambda dictionary, index, hide_in_display=(): (
        has_columns(dictionary, DISTRICT, TERMS) and has_columns(index, TERM, PAPER_IDS, HITS)
    )
)
@deal.post(lambda result: result.columns == [DISTRICT, TERMS, PAPER_IDS, HITS])
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.post(
    lambda result: lists_sorted_unique(result, TERMS) and lists_sorted_unique(result, PAPER_IDS)
)
@deal.post(
    lambda result: bool(
        (result.get_column(HITS) == result.get_column(PAPER_IDS).list.len().cast(pl.Int64)).all()
    ),
    message="anzahl_treffer zählt die vereinigten Dokument-IDs",
)
@deal.ensure(_only_dictionary_districts, message="nur Wahlbezirke aus dem Wörterbuch")
@deal.raises(EmptyResultError)
def hits_by_district(
    dictionary: pl.DataFrame, index: pl.DataFrame, hide_in_display: Iterable[str] = ()
) -> pl.DataFrame:
    """wahlkreis_id, suchbegriffe (Anzeigeliste), paper_ids (Vereinigung), anzahl_treffer."""
    hidden = list(hide_in_display)
    joined = dictionary.explode(TERMS).join(index, left_on=TERMS, right_on=TERM, how="inner")
    if joined.is_empty():
        raise EmptyResultError("Kein Suchbegriff des Wörterbuchs kommt im invertierten Index vor.")
    return (
        joined.group_by(DISTRICT)
        .agg(
            pl.col(TERMS).filter(~pl.col(TERMS).is_in(hidden)).unique().sort(),
            pl.col(PAPER_IDS).explode().drop_nulls().unique().sort(),
        )
        .with_columns(pl.col(PAPER_IDS).list.len().cast(pl.Int64).alias(HITS))
        .sort(DISTRICT)
    )


@deal.pre(
    lambda hits, voters, eligible_column: (
        has_columns(hits, DISTRICT, HITS) and has_columns(voters, DISTRICT, eligible_column)
    )
)
@deal.pre(
    lambda hits, voters, eligible_column: bool((voters.get_column(eligible_column) > 0).all()),
    message="Wahlberechtigte je Wahlbezirk müssen positiv sein, sonst ist die Quote undefiniert",
)
@deal.post(lambda result: sorted_unique(result, DISTRICT) and all_nonnegative(result, RATE))
@deal.ensure(
    lambda hits, voters, eligible_column, result: (
        set(result.get_column(DISTRICT))
        <= set(hits.get_column(DISTRICT)) & set(voters.get_column(DISTRICT))
    )
)
@deal.raises(EmptyResultError)
def join_voters(hits: pl.DataFrame, voters: pl.DataFrame, eligible_column: str) -> pl.DataFrame:
    """Treffer mit den Wählerdaten verbinden; Trefferquote = Treffer je Wahlberechtigtem."""
    joined = hits.join(voters, on=DISTRICT, how="inner")
    if joined.is_empty():
        raise EmptyResultError("Keine Wahlbezirks-ID der Treffer findet sich in den Wählerdaten.")
    return joined.with_columns((pl.col(HITS) / pl.col(eligible_column)).alias(RATE)).sort(DISTRICT)
