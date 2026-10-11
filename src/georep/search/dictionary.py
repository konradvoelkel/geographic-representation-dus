"""Suchwörterbuch je Wahlbezirk: Orte und Straßen vereint, normalisiert, mit ``str.``-Varianten.

Entspricht ``src/combine_searchdicts.py``: nur Wahlbezirke, die in beiden Quellen vorkommen;
Begriffe kleingeschrieben und getrimmt; zu jedem Begriff mit ``straße`` kommt die Variante mit
``str.`` dazu (``STREET_ABBREVIATIONS``); sortiert und eindeutig.
"""

from __future__ import annotations

import deal
import polars as pl

from georep.contracts import clean_terms, has_columns, lists_sorted_unique, sorted_unique

DISTRICT = "wahlkreis_id"
TERMS = "suchbegriffe"
# Langform und Abkürzung: zu jedem Begriff mit der Langform kommt die Variante mit der Abkürzung
# ins Wörterbuch (Verhalten der Arbeit). Die Suche der Berichtsseite liest dieselben Paare
# (``georep.report.search``), damit die Regel nur hier steht; Option 10 macht sie konfigurierbar.
STREET_ABBREVIATIONS: tuple[tuple[str, str], ...] = (("straße", "str."),)


def normalise_terms(terms: pl.Expr) -> pl.Expr:
    """Listen-Ausdruck: trimmen, kleinschreiben, Leeres weg, Abkürzungs-Varianten, eindeutig, sortiert."""
    cleaned = terms.list.eval(pl.element().str.strip_chars().str.to_lowercase()).list.eval(
        pl.element().filter(pl.element() != "")
    )
    with_variants = cleaned
    for long, short in STREET_ABBREVIATIONS:
        with_variants = with_variants.list.concat(
            cleaned.list.eval(
                pl.element()
                .filter(pl.element().str.contains(long, literal=True))
                .str.replace_all(long, short, literal=True)
            )
        )
    return with_variants.list.unique().list.sort()


@deal.pre(
    lambda pois_by_district, streets_by_district: (
        has_columns(pois_by_district, DISTRICT, TERMS)
        and has_columns(streets_by_district, DISTRICT, TERMS)
    ),
    message="beide Eingaben brauchen wahlkreis_id und suchbegriffe",
)
@deal.post(lambda result: result.columns == [DISTRICT, TERMS])
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.post(lambda result: lists_sorted_unique(result, TERMS))
@deal.post(lambda result: all(clean_terms(t) for t in result.get_column(TERMS).to_list()))
@deal.ensure(
    lambda pois_by_district, streets_by_district, result: (
        set(result.get_column(DISTRICT))
        == set(pois_by_district.get_column(DISTRICT))
        & set(streets_by_district.get_column(DISTRICT))
    ),
    message="genau die Wahlbezirke, die in beiden Quellen vorkommen",
)
def build_dictionary(
    pois_by_district: pl.DataFrame, streets_by_district: pl.DataFrame
) -> pl.DataFrame:
    """Eine Zeile je Wahlbezirk mit der Liste ``suchbegriffe``."""
    joined = pois_by_district.join(
        streets_by_district, on=DISTRICT, how="inner", suffix="_strassen"
    )
    return joined.select(
        pl.col(DISTRICT),
        normalise_terms(pl.col(TERMS).list.concat(pl.col(f"{TERMS}_strassen"))).alias(TERMS),
    ).sort(DISTRICT)


@deal.pre(lambda dictionary: has_columns(dictionary, TERMS))
@deal.post(lambda result: result == sorted(set(result)))
def all_terms(dictionary: pl.DataFrame) -> list[str]:
    """Alle Begriffe über alle Wahlbezirke, eindeutig und sortiert."""
    return sorted(set(dictionary.get_column(TERMS).explode().drop_nulls().to_list()))
