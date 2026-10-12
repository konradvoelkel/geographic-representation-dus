"""Treffer je Wahlbezirk und Verknüpfung mit den Wählerdaten.

Entspricht ``src/analyse.py``: Wörterbuch auf Begriffe auflösen, mit dem Index verbinden, je
Wahlbezirk die Vereinigung der Dokument-IDs zählen; ``hide_in_display`` nimmt Begriffe nur aus
der Anzeigeliste, nicht aus der Zählung (Verhalten der Arbeit, Kapitel 4.3.5).

Dazu Regel 2 „stadtweite Begriffe" (``docs/decisions.md``, Punkt 44): welche Begriffe über der
Schwelle der Dokumenthäufigkeit liegen, sagt ``citywide_terms``; die Seite nennt sie, und nur mit
``search.citywide_exclude`` nimmt ``without_terms`` sie vor der Zählung aus dem Wörterbuch.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

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


@dataclass(frozen=True)
class Citywide:
    """Die Begriffe über der Schwelle, die stärksten zuerst, mit der Schwelle und ihrer Herkunft.

    ``threshold`` ist die Dokumenthäufigkeit, über der ein Begriff als stadtweit gilt (die
    Schwelle selbst gehört noch nicht dazu), ``basis`` der Satzteil für die Seite („über dem
    99-%-Quantil der Dokumenthäufigkeit"). Ohne Schwelle ist alles leer.
    """

    threshold: int
    basis: str
    terms: tuple[str, ...]


@deal.pre(lambda index, *, quantile, median_factor: has_columns(index, TERM, HITS))
@deal.pre(
    lambda index, *, quantile, median_factor: (
        0.0 <= quantile < 1.0 and median_factor >= 0.0 and not (quantile and median_factor)
    ),
    message="Quantil in [0, 1) oder Vielfaches des Medians, nie beides",
)
@deal.post(lambda result: result.threshold >= 0 and len(set(result.terms)) == len(result.terms))
def citywide_terms(index: pl.DataFrame, *, quantile: float, median_factor: float) -> Citywide:
    """Begriffe mit auffällig hoher Dokumenthäufigkeit; welche, sagt eine der beiden Schwellen.

    Die Quantilschwelle passt sich dem Datensatz an (auf der Referenz liegt das 99-%-Quantil bei
    64 Dokumenten), das Vielfache des Medians ist die robustere Alternative, wenn der Median
    aussagekräftig ist. Beide zugleich wäre eine doppelte Wahrheit, darum verbietet es der
    Vertrag und die Settings prüfen es beim Laden.
    """
    counts = index.get_column(HITS)
    if counts.is_empty() or (not quantile and not median_factor):
        return Citywide(0, "", ())
    if quantile:
        raw = float(counts.quantile(quantile) or 0.0)
        percent = f"{quantile * 100:g}".replace(".", ",")
        basis = f"über dem {percent}-%-Quantil der Dokumenthäufigkeit"
    else:
        # ``Series.median`` ist für polars über alle Spaltentypen deklariert; die Spalte ist
        # per Vertrag die Dokumenthäufigkeit, also eine Zahl.
        median = counts.median()
        raw = (float(median) if isinstance(median, int | float) else 0.0) * median_factor
        factor = f"{median_factor:g}".replace(".", ",")
        basis = f"über dem {factor}-fachen des Medians der Dokumenthäufigkeit"
    threshold = int(math.floor(raw))
    above = (
        index.filter(pl.col(HITS) > threshold)
        .unique(subset=[TERM], keep="first")
        .sort([HITS, TERM], descending=[True, False])
    )
    return Citywide(threshold, f"{basis} ({threshold} Dokumente)", tuple(above.get_column(TERM)))


@deal.pre(lambda dictionary, terms: has_columns(dictionary, TERMS))
@deal.ensure(
    lambda dictionary, terms, result: result.height == dictionary.height,
    message="die Wahlbezirke bleiben, nur ihre Begriffslisten werden kürzer",
)
def without_terms(dictionary: pl.DataFrame, terms: Sequence[str]) -> pl.DataFrame:
    """Dasselbe Wörterbuch ohne die genannten Begriffe; ohne Begriffe unverändert."""
    if not terms:
        return dictionary
    drop = list(terms)
    return dictionary.with_columns(
        pl.col(TERMS).list.eval(pl.element().filter(~pl.element().is_in(drop))).alias(TERMS)
    )
