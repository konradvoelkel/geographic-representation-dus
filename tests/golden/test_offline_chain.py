"""Charakterisierungstests: die Offline-Kette des Altcodes liefert heute genau dieses Ergebnis.

Kein Test behauptet, das Ergebnis sei richtig; er behauptet, es sei unverändert. Das volle
Referenzkorpus (19108 Dokumente) läuft als ``slow``; die Mini-Fixture mit 200 Dokumenten und
drei Wahlbezirken ist das schnelle Netz für die Umstellung auf Polars.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from tests.legacy_runner import run_offline_chain

EXACT_COLS = [
    "wahlkreis_id",
    "anzahl_treffer",
    "Wahlberechtigte_insgesamt",
    "Waehler",
    "suchbegriffe",
]
FLOAT_COLS = ["wahlkreis_id", "trefferquote", "wahlbeteiligung"]
INDEX_SCHEMA = {"suchbegriffe": pl.String, "paper_ids": pl.String}


def _auswertung(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema_length=None).sort("wahlkreis_id")


def _index_as_sets(path: Path) -> dict[str, frozenset[str]]:
    """Begriff -> Menge der Dokument-IDs; die Zeilenreihenfolge des Altcodes ist nicht deterministisch."""
    df = pl.read_csv(path, infer_schema_length=None, schema_overrides=INDEX_SCHEMA)
    out: dict[str, frozenset[str]] = {}
    for row in df.iter_rows(named=True):
        ids = row["paper_ids"]
        out[str(row["suchbegriffe"])] = frozenset(str(ids).split(";")) if ids else frozenset()
    return out


def _assert_chain_matches(inputs: Path, expected_dir: Path, tmp_path: Path) -> None:
    run_offline_chain(inputs, tmp_path)
    got = _auswertung(tmp_path / "wahlbezirke_auswertung.csv")
    exp = _auswertung(expected_dir / "wahlbezirke_auswertung.csv")
    assert_frame_equal(got.select(EXACT_COLS), exp.select(EXACT_COLS))
    assert_frame_equal(got.select(FLOAT_COLS), exp.select(FLOAT_COLS), rel_tol=1e-12)
    assert _index_as_sets(tmp_path / "inverted_index.csv") == _index_as_sets(
        expected_dir / "inverted_index.csv"
    )


def test_mini_chain_matches_frozen_outputs(mini_root: Path, tmp_path: Path) -> None:
    _assert_chain_matches(mini_root, mini_root / "expected", tmp_path)


@pytest.mark.slow
def test_reference_chain_matches_committed_outputs(reference_root: Path, tmp_path: Path) -> None:
    _assert_chain_matches(reference_root, reference_root / "processed", tmp_path)


def test_mini_fixture_shape(mini_root: Path) -> None:
    papers = json.loads(
        (mini_root / "interim" / "paper_with_text.json").read_text(encoding="utf-8")
    )
    assert len(papers) == 200
    exp = _auswertung(mini_root / "expected" / "wahlbezirke_auswertung.csv")
    assert exp["wahlkreis_id"].to_list() == [1, 10, 38]
    assert bool((exp["anzahl_treffer"] > 0).all())
