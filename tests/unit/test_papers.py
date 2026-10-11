from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from georep.bootstrap import REFERENCE_EXTRACTOR, seed_stores_from_legacy
from georep.io import write_parquet
from georep.layout import Layout
from georep.prep.papers import (
    CORPUS_COLUMNS,
    CORPUS_SCHEMA_VERSION,
    build_corpus,
    documents_with_text,
)
from georep.stores import PaperStore, TextStore


def test_corpus_from_stores_matches_the_legacy_file(mini_root: Path, tmp_path: Path) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", mini_root)
    items = json.loads((mini_root / "interim" / "paper_with_text.json").read_text(encoding="utf-8"))
    papers, texts = seed_stores_from_legacy(layout, items)
    assert (papers, texts) == (200, 200)
    corpus = build_corpus(PaperStore(layout.papers).load().values(), TextStore(layout.texts))
    assert corpus.columns == CORPUS_COLUMNS
    assert corpus.height == 200 and documents_with_text(corpus) == 200
    assert corpus.schema["date"] == pl.Date
    assert corpus["id"].is_sorted()
    by_id = {item["id"]: item for item in items}
    for row in corpus.iter_rows(named=True):
        item = by_id[row["id"]]
        assert row["text"] == item["paper_text"]
        assert row["file_name"] == item["download_url"].rsplit("/", 1)[-1]
        assert row["date"] == dt.date.fromisoformat(item["date"])
    meta = TextStore(layout.texts).meta(corpus["file_name"][0])
    assert meta is not None and meta.extractor == REFERENCE_EXTRACTOR
    write_parquet(corpus, tmp_path / "c.parquet", schema_version=CORPUS_SCHEMA_VERSION)
    assert pl.read_parquet_metadata(tmp_path / "c.parquet")["georep.schema_version"] == "2"
