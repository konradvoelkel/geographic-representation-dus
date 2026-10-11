"""Suchwörterbuch je Wahlbezirk: Orte und Straßen vereint, normalisiert, mit ``str.``-Varianten.

Entspricht ``src/combine_searchdicts.py``: nur Wahlbezirke, die in beiden Quellen vorkommen;
Begriffe kleingeschrieben und getrimmt; zu jedem Begriff mit ``straße`` kommt die Variante mit
``str.`` dazu; sortiert und eindeutig.
"""

from __future__ import annotations

import polars as pl

DISTRICT = "wahlkreis_id"
TERMS = "suchbegriffe"


def normalise_terms(terms: pl.Expr) -> pl.Expr:
    """Listen-Ausdruck: trimmen, kleinschreiben, Leeres weg, ``straße``-Varianten, eindeutig, sortiert."""
    cleaned = terms.list.eval(pl.element().str.strip_chars().str.to_lowercase()).list.eval(
        pl.element().filter(pl.element() != "")
    )
    variants = cleaned.list.eval(
        pl.element()
        .filter(pl.element().str.contains("straße", literal=True))
        .str.replace_all("straße", "str.", literal=True)
    )
    return cleaned.list.concat(variants).list.unique().list.sort()


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


def all_terms(dictionary: pl.DataFrame) -> list[str]:
    """Alle Begriffe über alle Wahlbezirke, eindeutig und sortiert."""
    return sorted(set(dictionary.get_column(TERMS).explode().drop_nulls().to_list()))
