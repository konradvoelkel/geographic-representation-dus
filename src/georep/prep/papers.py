"""Korpus: ein Text je Ratsdokument, aus ``PaperStore`` und ``TextStore``.

Metadaten kommen aus ``raw/papers.jsonl``, Texte aus dem Textstore (``georep.prep.extract``);
Paper ohne Text bekommen einen leeren String, wie in der Arbeit.

Seit Schema-Version 3 (Option 04) kommen die vier URL-Listen des Records als ``List(String)`` mit:
``georep.analysis.parties`` liest ``originator_organization``, Option 5 später
``consultation_organizations``. Aus ``from_legacy`` sind sie leer.
"""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl
from polars._typing import PolarsDataType

from georep.records import PaperRecord
from georep.stores import TextStore

# Version 3 (Option 04): die vier URL-Listen des Records kommen als List(String) mit.
CORPUS_SCHEMA_VERSION = 3  # erhöhen, wenn sich Spalten oder Typen von papers.parquet ändern
ORIGINATOR_COLUMNS = (
    "originator_person",
    "originator_organization",
    "under_direction_of",
    "consultation_organizations",
)
CORPUS_SCHEMA: dict[str, PolarsDataType] = {
    "id": pl.String,
    "name": pl.String,
    "reference": pl.String,
    "date": pl.Date,
    "paper_type": pl.String,
    "main_file": pl.String,
    "file_name": pl.String,
    "download_url": pl.String,
    "text": pl.String,
    **{column: pl.List(pl.String) for column in ORIGINATOR_COLUMNS},
}
CORPUS_COLUMNS = list(CORPUS_SCHEMA)


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
                **{column: list(getattr(record, column)) for column in ORIGINATOR_COLUMNS},
            }
        )
    return pl.DataFrame(rows, schema=CORPUS_SCHEMA)


def documents_with_text(corpus: pl.DataFrame) -> int:
    return int(corpus.filter(pl.col("text") != "").height)
