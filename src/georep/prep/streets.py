"""Straßennamen je Stimmbezirk (OSM) zu Suchbegriffen je Wahlbezirk.

Entspricht ``src/prep_streets.py``: je Wahlbezirk die sortierte Menge der Straßennamen aller
seiner Stimmbezirke. Listen statt ``"; "``-Strings.
"""

from __future__ import annotations

from pathlib import Path

import deal
import polars as pl

from georep.contracts import has_columns, lists_sorted_unique, sorted_unique

DISTRICT = "wahlkreis_id"
TERMS = "suchbegriffe"


def read_streets_json(path: Path) -> pl.DataFrame:
    """``streets_per_district.json``: eine Zeile je Stimmbezirk mit der Liste ``straßen``."""
    return pl.read_json(path)


@deal.pre(lambda streets: has_columns(streets, "wahlbezirk_id", "straßen"))
@deal.post(lambda result: result.columns == [DISTRICT, TERMS])
@deal.post(lambda result: sorted_unique(result, DISTRICT) and lists_sorted_unique(result, TERMS))
def streets_by_district(streets: pl.DataFrame) -> pl.DataFrame:
    return (
        streets.select(pl.col("wahlbezirk_id").cast(pl.Int64).alias(DISTRICT), pl.col("straßen"))
        .explode("straßen")
        .drop_nulls("straßen")
        .group_by(DISTRICT)
        .agg(pl.col("straßen").unique().sort().alias(TERMS))
        .sort(DISTRICT)
    )
