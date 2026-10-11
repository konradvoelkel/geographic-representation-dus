"""Korpus: ein Text je Ratsdokument.

Phase 2: Umwandlung des Altformats ``paper_with_text.json`` nach ``papers.parquet``. Phase 3
bringt die Extraktion aus den PDFs mit Textcache hierher.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

CORPUS_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen von papers.parquet ändern
CORPUS_COLUMNS = [
    "id",
    "name",
    "reference",
    "date",
    "paper_type",
    "main_file",
    "download_url",
    "text",
]


def corpus_from_legacy_json(json_path: Path) -> pl.DataFrame:
    """``paper_with_text.json`` (Liste von Objekten mit paperType, mainFile, paper_text) als Korpus."""
    return (
        pl.read_json(json_path)
        .select(
            pl.col("id").cast(pl.String),
            pl.col("name").cast(pl.String),
            pl.col("reference").cast(pl.String),
            pl.col("date").cast(pl.String).str.to_date("%Y-%m-%d", strict=False),
            pl.col("paperType").cast(pl.String).alias("paper_type"),
            pl.col("mainFile").cast(pl.String).alias("main_file"),
            pl.col("download_url").cast(pl.String),
            pl.col("paper_text").cast(pl.String).fill_null("").alias("text"),
        )
        .sort("id")
    )


def documents_with_text(corpus: pl.DataFrame) -> int:
    return int(corpus.filter(pl.col("text") != "").height)
