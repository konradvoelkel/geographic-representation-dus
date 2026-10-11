"""Points of Interest (Wikidata, Wikipedia) bereinigen und je Wahlbezirk sammeln.

Entspricht ``src/prep_wiki.py`` einschließlich seiner Reihenfolge, die den Golden Master prägt:
erst Duplikate nach Label entfernen (erstes Vorkommen bleibt), dann Einträge ohne Wahlbezirk
verwerfen, dann Kommas aus den Labels tilgen, dann die Ausschlussliste anwenden.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import deal
import polars as pl

from georep.contracts import has_columns, lists_sorted_unique, sorted_unique

DISTRICT = "wahlkreis_id"
TERMS = "suchbegriffe"
POI_COLUMNS = ["label", DISTRICT, "lon", "lat"]


def read_pois_json(path: Path) -> pl.DataFrame:
    """Zwei Schlüsselsätze in einer Datei (SPARQL mit url, GeoSearch mit pageid und dist):
    das Schema muss über alle Zeilen abgeleitet werden."""
    return pl.read_json(path, infer_schema_length=None)


@deal.pre(lambda pois, exclude: has_columns(pois, *POI_COLUMNS))
@deal.post(lambda result: result.columns == POI_COLUMNS)
@deal.post(
    lambda result: (
        result.get_column(DISTRICT).null_count() == 0
        and not result.get_column("label").str.contains(",", literal=True).any()
    ),
    message="jeder Ort hat einen Wahlbezirk, kein Label trägt ein Komma",
)
@deal.ensure(lambda pois, exclude, result: result.height <= pois.height)
def clean_pois(pois: pl.DataFrame, exclude: Iterable[str]) -> pl.DataFrame:
    """Tabelle label, wahlkreis_id, lon, lat; Reihenfolge der Quelle bleibt."""
    excluded = list(exclude)
    return (
        pois.unique(subset=["label"], keep="first", maintain_order=True)
        .drop_nulls(DISTRICT)
        .with_columns(
            pl.col("label").str.replace_all(",", "", literal=True),
            pl.col(DISTRICT).cast(pl.Int64),
        )
        .filter(~pl.col("label").is_in(excluded))
        .select(POI_COLUMNS)
    )


@deal.pre(lambda clean: has_columns(clean, DISTRICT, "label"))
@deal.post(lambda result: result.columns == [DISTRICT, TERMS])
@deal.post(lambda result: sorted_unique(result, DISTRICT) and lists_sorted_unique(result, TERMS))
def pois_by_district(clean: pl.DataFrame) -> pl.DataFrame:
    return clean.group_by(DISTRICT).agg(pl.col("label").unique().sort().alias(TERMS)).sort(DISTRICT)
