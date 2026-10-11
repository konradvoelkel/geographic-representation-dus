"""Korpus: ein Text je Ratsdokument, aus ``PaperStore`` und ``TextStore``.

Metadaten kommen aus ``raw/papers.jsonl``, Texte aus dem Textstore; Paper ohne Text bekommen
einen leeren String, wie in der Arbeit. Phase 3 bringt die Extraktion aus den PDFs hierher.
"""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl

from georep.records import PaperRecord
from georep.stores import TextStore

CORPUS_SCHEMA_VERSION = 2  # erhöhen, wenn sich Spalten oder Typen von papers.parquet ändern
CORPUS_COLUMNS = [
    "id",
    "name",
    "reference",
    "date",
    "paper_type",
    "main_file",
    "file_name",
    "download_url",
    "text",
]
CORPUS_SCHEMA = {
    "id": pl.String,
    "name": pl.String,
    "reference": pl.String,
    "date": pl.Date,
    "paper_type": pl.String,
    "main_file": pl.String,
    "file_name": pl.String,
    "download_url": pl.String,
    "text": pl.String,
}


def build_corpus(records: Iterable[PaperRecord], texts: TextStore) -> pl.DataFrame:
    rows = []
    for record in sorted(records, key=lambda r: r.id):
        text = texts.get(record.file_name) if record.file_name else None
        rows.append(
            {
                "id": record.id,
                "name": record.name,
                "reference": record.reference,
                "date": record.date,
                "paper_type": record.paper_type,
                "main_file": record.main_file,
                "file_name": record.file_name,
                "download_url": record.download_url,
                "text": text or "",
            }
        )
    return pl.DataFrame(rows, schema=CORPUS_SCHEMA)


def documents_with_text(corpus: pl.DataFrame) -> int:
    return int(corpus.filter(pl.col("text") != "").height)
