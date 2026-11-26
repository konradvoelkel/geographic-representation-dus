"""Vorhaben 18 über die ganze Hauptperiode, aus den Paketen im Repo (``pytest -m slow``).

Zwei Zahlen der Messung (``docs/plans/18-einbettungen.md``, § 3.2 und § 3.6), nachgerechnet mit dem
Code des Schritts und des Suchbefehls statt mit dem Messskript:

* **47 407 Stücke** über die 19 032 Einheiten (Korpus der Arbeit, Rohtextpaket), dieselbe Zahl wie
  das ``zerteile`` der Messung auf ihrer Rohtextdatei;
* **die BM25-Rangfolgen der 50 Suchfragen**, je die ersten zehn IDs, gegen die gespeicherte Liste
  aus der Messung (``tests/fixtures/search/bm25_50_fragen.json``, 488 IDs; drei Fragen haben
  weniger als zehn Treffer).

Für die Einbettung gibt es hier nur Invarianten (das Nachbarpaket, ``test_data_packages.py``): die
GPU rundet je Rechner anders, wie das Themenmodell je Thread-Zahl (CLAUDE.md).
"""

from __future__ import annotations

import json

import polars as pl
import pytest

from georep.records import PaperRecord
from georep.search.bm25 import Tokenizer, bm25_scores, build_index, count_terms, ranking
from georep.search.units import build_units, raw_frame, unit_chunks
from tests.conftest import REPO

RAW = REPO / "snapshots" / "duesseldorf-rohtexte" / "cache" / "text" / "rohtexte.parquet"
LEGACY = REPO / "reference" / "interim" / "paper_with_text.json"
FIXTURE = REPO / "tests" / "fixtures" / "search" / "bm25_50_fragen.json"


@pytest.fixture(scope="module")
def units() -> pl.DataFrame:
    items = json.loads(LEGACY.read_text(encoding="utf-8"))
    records = [PaperRecord.from_legacy(item) for item in items]
    corpus = pl.DataFrame(
        [(r.id, r.name, r.file_name) for r in records],
        schema={"id": pl.String, "name": pl.String, "file_name": pl.String},
        orient="row",
    )
    raw = pl.read_parquet(RAW, columns=["name", "text", "form_feeds"])
    return build_units(corpus, raw_frame(raw.iter_rows()), 200)


@pytest.mark.slow
def test_the_main_period_has_the_measured_chunks(units: pl.DataFrame) -> None:
    assert units.height == 19032
    assert int(units.get_column("ids").list.len().sum()) == 19032  # geteilte Dateien sind leer
    chunks = unit_chunks(units, 1600, 200, "search_document: ")
    assert chunks.height == 47407
    assert chunks.get_column("text").n_unique() == 47312  # 95 Stücke wiederholen sich wörtlich
    assert chunks.get_column("text").str.len_chars().max() == 1617


@pytest.mark.slow
def test_bm25_ranks_the_fifty_questions_like_the_measurement(units: pl.DataFrame) -> None:
    texts = [
        f"{title}\n\n{raw.replace(chr(12), chr(10))}"
        for title, raw in units.select("titel", "roh").iter_rows()
    ]
    tokenize = Tokenizer()
    index = build_index(units.get_column("id").to_list(), count_terms(texts, tokenize))
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(expected) == 50
    for question in expected:
        scores = bm25_scores(index, tokenize(question["anfrage"]), 1.2, 0.75)
        found = [index.ids[i] for i in ranking(scores, 10, positive_only=True)]
        assert found == question["bm25"], question["id"]
