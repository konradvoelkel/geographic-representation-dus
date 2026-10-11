from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from georep.bootstrap import bootstrap, legacy_corpus_to_parquet
from georep.layout import Layout


def _layout(tmp_path: Path, mini_root: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", mini_root)


def test_bootstrap_copies_inputs_and_converts_the_corpus(tmp_path: Path, mini_root: Path) -> None:
    layout = _layout(tmp_path, mini_root)
    report = bootstrap(layout)
    assert sorted(report.copied) == [
        "Stimmbezirk_Wahlergebnis.csv",
        "paper_with_text.json",
        "streets_per_district.json",
        "wikipedia_dict.json",
    ]
    assert sorted(report.missing) == [
        "Stimmbezirke_2025.geojson",
        "paper_objects.json",
        "paper_urls.json",
    ]
    assert report.corpus_rows == 200
    assert (
        layout.results_csv.read_bytes()
        == (mini_root / "external" / "Stimmbezirk_Wahlergebnis.csv").read_bytes()
    )
    corpus = pl.read_parquet(layout.corpus)
    assert corpus.columns == [
        "id",
        "name",
        "reference",
        "date",
        "paper_type",
        "main_file",
        "download_url",
        "text",
    ]
    assert corpus.schema["date"] == pl.Date
    assert corpus.height == 200
    assert corpus["id"].is_sorted()
    assert "Korpus mit 200 Dokumenten" in report.summary()


def test_bootstrap_is_idempotent_and_force_recopies(tmp_path: Path, mini_root: Path) -> None:
    layout = _layout(tmp_path, mini_root)
    bootstrap(layout)
    second = bootstrap(layout)
    assert second.copied == [] and len(second.skipped) == 4 and second.corpus_rows is None
    forced = bootstrap(layout, force=True)
    assert len(forced.copied) == 4 and forced.corpus_rows == 200


def test_bootstrap_never_writes_into_the_reference(tmp_path: Path, mini_root: Path) -> None:
    before = sorted(p.relative_to(mini_root) for p in mini_root.rglob("*"))
    bootstrap(_layout(tmp_path, mini_root))
    after = sorted(p.relative_to(mini_root) for p in mini_root.rglob("*"))
    assert before == after


def test_corpus_conversion_keeps_text_and_parses_dates(tmp_path: Path, mini_root: Path) -> None:
    rows = legacy_corpus_to_parquet(
        mini_root / "interim" / "paper_with_text.json", tmp_path / "c.parquet"
    )
    corpus = pl.read_parquet(tmp_path / "c.parquet")
    assert rows == 200
    assert corpus["text"].null_count() == 0
    lo, hi = corpus["date"].min(), corpus["date"].max()
    assert isinstance(lo, dt.date) and isinstance(hi, dt.date)
    assert dt.date(2020, 9, 13) <= lo <= hi <= dt.date(2025, 9, 14)
    meta = pl.read_parquet_metadata(tmp_path / "c.parquet")
    assert meta["georep.schema_version"] == "1"
