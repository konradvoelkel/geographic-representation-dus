"""Treffer je Wahlbezirk und Verknüpfung mit den Wählerdaten.

Entspricht ``src/analyse.py``: Wörterbuch auf Begriffe auflösen, mit dem Index verbinden, je
Wahlbezirk die Vereinigung der Dokument-IDs zählen; ``hide_in_display`` nimmt Begriffe nur aus
der Anzeigeliste, nicht aus der Zählung (Verhalten der Arbeit, Kapitel 4.3.5).
"""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl

from georep.errors import EmptyResultError
from georep.search.index import HITS, PAPER_IDS, TERM

DISTRICT = "wahlkreis_id"
TERMS = "suchbegriffe"
RATE = "trefferquote"


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


def join_voters(hits: pl.DataFrame, voters: pl.DataFrame, eligible_column: str) -> pl.DataFrame:
    """Treffer mit den Wählerdaten verbinden; Trefferquote = Treffer je Wahlberechtigtem."""
    joined = hits.join(voters, on=DISTRICT, how="inner")
    if joined.is_empty():
        raise EmptyResultError("Keine Wahlbezirks-ID der Treffer findet sich in den Wählerdaten.")
    return joined.with_columns((pl.col(HITS) / pl.col(eligible_column)).alias(RATE)).sort(DISTRICT)
