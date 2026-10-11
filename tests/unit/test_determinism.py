"""Zwei Läufe auf denselben Eingaben schreiben byteweise dieselben Dateien."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from tests.legacy_runner import run_offline_chain

COMPARED = ["inverted_index.csv", "wahlbezirke_auswertung.csv", "combined_searchdict.csv"]


def test_two_runs_are_byte_identical(mini_root: Path, tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    run_offline_chain(mini_root, first)
    run_offline_chain(mini_root, second)
    for name in COMPARED:
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_index_is_sorted_by_term(mini_root: Path, tmp_path: Path) -> None:
    run_offline_chain(mini_root, tmp_path)
    terms = pl.read_csv(
        tmp_path / "inverted_index.csv", schema_overrides={"suchbegriffe": pl.String}
    )["suchbegriffe"].to_list()
    assert terms == sorted(terms)
