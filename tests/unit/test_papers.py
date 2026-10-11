from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from georep.io import write_parquet
from georep.prep.papers import (
    CORPUS_COLUMNS,
    CORPUS_SCHEMA_VERSION,
    corpus_from_legacy_json,
    documents_with_text,
)


def test_legacy_corpus_conversion(mini_root: Path, tmp_path: Path) -> None:
    corpus = corpus_from_legacy_json(mini_root / "interim" / "paper_with_text.json")
    assert corpus.columns == CORPUS_COLUMNS
    assert corpus.height == 200 and documents_with_text(corpus) == 200
    assert corpus.schema["date"] == pl.Date
    assert corpus["id"].is_sorted()
    assert corpus["text"].null_count() == 0
    lo, hi = corpus["date"].min(), corpus["date"].max()
    assert isinstance(lo, dt.date) and isinstance(hi, dt.date)
    assert dt.date(2020, 9, 13) <= lo <= hi <= dt.date(2025, 9, 14)
    write_parquet(corpus, tmp_path / "c.parquet", schema_version=CORPUS_SCHEMA_VERSION)
    assert pl.read_parquet_metadata(tmp_path / "c.parquet")["georep.schema_version"] == "1"
