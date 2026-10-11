"""Guards: falsche Spalten beim Namen, ohne Treffer kein Index, ohne Überschneidung keine Auswertung."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep.analysis.hits import hits_by_district, join_voters
from georep.errors import EmptyResultError, SchemaError
from georep.prep.voters import read_results_csv
from georep.search.index import build_index
from georep.settings import load_settings
from tests.conftest import MINI


def test_results_csv_names_missing_columns(tmp_path: Path) -> None:
    raw = (MINI / "external" / "Stimmbezirk_Wahlergebnis.csv").read_bytes().decode("latin-1")
    header, body = raw.split("\n", 1)
    assert "Waehler;" in header
    broken = tmp_path / "ergebnis.csv"
    broken.write_bytes(
        (header.replace("Waehler;", "Waehlerinnen;") + "\n" + body).encode("latin-1")
    )
    columns = load_settings(cwd=Path("/nonexistent")).columns.results
    with pytest.raises(SchemaError, match="Waehler"):
        read_results_csv(broken, columns)


def test_index_refuses_without_a_single_hit() -> None:
    corpus = pl.DataFrame({"id": ["a", "b"], "text": ["hallo welt", ""]})
    with pytest.raises(EmptyResultError, match="2 Dokumenten"):
        build_index(corpus, ["xyzzyplugh", "quuxfoo"])


def test_hits_refuse_disjoint_dictionary_and_index() -> None:
    dictionary = pl.DataFrame({"wahlkreis_id": [1], "suchbegriffe": [["foo"]]})
    index = pl.DataFrame(
        {"suchbegriffe": ["bar"], "paper_ids": [["p1"]], "anzahl_treffer": [1]},
        schema={
            "suchbegriffe": pl.String,
            "paper_ids": pl.List(pl.String),
            "anzahl_treffer": pl.Int64,
        },
    )
    with pytest.raises(EmptyResultError):
        hits_by_district(dictionary, index)
    hits = pl.DataFrame(
        {
            "wahlkreis_id": [1],
            "suchbegriffe": [["foo"]],
            "paper_ids": [["p1"]],
            "anzahl_treffer": [1],
        }
    )
    voters = pl.DataFrame({"wahlkreis_id": [2], "Wahlberechtigte_insgesamt": [100]})
    with pytest.raises(EmptyResultError):
        join_voters(hits, voters, "Wahlberechtigte_insgesamt")
