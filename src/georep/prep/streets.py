"""Straßennamen je Stimmbezirk (OSM) zu Suchbegriffen je Wahlbezirk.

Entspricht ``src/prep_streets.py``: je Wahlbezirk die sortierte Menge der Straßennamen aller
seiner Stimmbezirke. Listen statt ``"; "``-Strings.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

DISTRICT = "wahlkreis_id"
TERMS = "suchbegriffe"


def read_streets_json(path: Path) -> pl.DataFrame:
    """``streets_per_district.json``: eine Zeile je Stimmbezirk mit der Liste ``straßen``."""
    return pl.read_json(path)


def streets_by_district(streets: pl.DataFrame) -> pl.DataFrame:
    return (
        streets.select(pl.col("wahlbezirk_id").cast(pl.Int64).alias(DISTRICT), pl.col("straßen"))
        .explode("straßen")
        .drop_nulls("straßen")
        .group_by(DISTRICT)
        .agg(pl.col("straßen").unique().sort().alias(TERMS))
        .sort(DISTRICT)
    )
