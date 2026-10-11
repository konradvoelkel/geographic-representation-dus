"""Guards des Altcodes: ohne Eingabe kein Lauf, ohne Ergebnis keine Datei, falsche Spalten beim Namen."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import src.config as cfg
from georep.errors import EmptyResultError, MissingInputError, SchemaError
from src import analyse, prep_papers, prep_voters, reverse_index
from tests.conftest import MINI, PDF_FIXTURES

FIXTURE_PDFS = ["00438685.pdf", "00439409.pdf", "00519825.pdf", "00552781.pdf"]


def _paper_objects(names: list[str]) -> list[dict[str, str]]:
    return [
        {
            "id": f"p{i}",
            "name": name,
            "reference": "",
            "date": "2024-01-01",
            "paperType": "Antrag",
            "mainFile": "",
            "download_url": f"https://ris.invalid/dl/{name}",
            "paper_text": "",
        }
        for i, name in enumerate(names)
    ]


def _texts(path: Path) -> list[str]:
    return [p["paper_text"] for p in json.loads(path.read_text(encoding="utf-8"))]


@pytest.fixture
def papers_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    objects = tmp_path / "paper_objects.json"
    objects.write_text(json.dumps(_paper_objects(FIXTURE_PDFS)), encoding="utf-8")
    (tmp_path / "pdf").mkdir()
    monkeypatch.setattr(cfg, "PAPER_OBJECT_LISTE", objects)
    monkeypatch.setattr(cfg, "PAPER_WITH_TEXT_PATH", tmp_path / "paper_with_text.json")
    monkeypatch.setattr(cfg, "PDF_DUMP_PATH", tmp_path / "pdf")
    return tmp_path


def _copy_pdfs(layout: Path, names: list[str]) -> None:
    for name in names:
        shutil.copy(PDF_FIXTURES / name, layout / "pdf" / name)


def test_prep_papers_refuses_without_pdfs(papers_layout: Path) -> None:
    with pytest.raises(MissingInputError):
        prep_papers.main()
    assert not (papers_layout / "paper_with_text.json").exists()


def test_prep_papers_extracts_every_available_pdf(papers_layout: Path) -> None:
    _copy_pdfs(papers_layout, FIXTURE_PDFS)
    prep_papers.main()
    texts = _texts(papers_layout / "paper_with_text.json")
    assert len(texts) == 4
    assert all(texts)
    assert all(not t.startswith("betrifft") for t in texts)  # der Kopf vor "betrifft" ist weg


def test_prep_papers_refuses_to_shrink_the_corpus(papers_layout: Path) -> None:
    _copy_pdfs(papers_layout, FIXTURE_PDFS)
    prep_papers.main()
    for name in FIXTURE_PDFS[2:]:
        (papers_layout / "pdf" / name).unlink()
    with pytest.raises(EmptyResultError, match="2 Texte"):
        prep_papers.main()
    assert sum(1 for t in _texts(papers_layout / "paper_with_text.json") if t) == 4
    prep_papers.main(force=True)
    assert sum(1 for t in _texts(papers_layout / "paper_with_text.json") if t) == 2


def test_prep_voters_names_missing_columns(tmp_path: Path) -> None:
    raw = (MINI / "external" / "Stimmbezirk_Wahlergebnis.csv").read_bytes().decode("latin-1")
    header, body = raw.split("\n", 1)
    assert "Waehler;" in header
    broken = tmp_path / "ergebnis.csv"
    broken.write_bytes(
        (header.replace("Waehler;", "Waehlerinnen;") + "\n" + body).encode("latin-1")
    )
    with pytest.raises(SchemaError, match="Waehler"):
        prep_voters.group_data_by_district(broken)


def test_reverse_index_refuses_an_index_without_hits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    searchdict = tmp_path / "combined_searchdict.csv"
    searchdict.write_text("wahlkreis_id;suchbegriffe\n1;xyzzyplugh, quuxfoo\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "COMBINED_SEARCHDICT_PATH", searchdict)
    monkeypatch.setattr(cfg, "PAPER_WITH_TEXT_PATH", MINI / "interim" / "paper_with_text.json")
    monkeypatch.setattr(cfg, "INVERTED_INDEX_PATH", tmp_path / "inverted_index.csv")
    with pytest.raises(EmptyResultError):
        reverse_index.main()
    assert not (tmp_path / "inverted_index.csv").exists()


def test_analyse_refuses_when_dictionary_and_index_do_not_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "combined_searchdict.csv").write_text("wahlkreis_id;suchbegriffe\n1;foo\n")
    (tmp_path / "inverted_index.csv").write_text("suchbegriffe,paper_ids,anzahl_treffer\nbar,,0\n")
    (tmp_path / "waehler.csv").write_text(
        "wahlkreis_id,Wahlberechtigte_insgesamt,Waehler,wahlbeteiligung\n1,100,50,0.5\n"
    )
    monkeypatch.setattr(cfg, "COMBINED_SEARCHDICT_PATH", tmp_path / "combined_searchdict.csv")
    monkeypatch.setattr(cfg, "INVERTED_INDEX_PATH", tmp_path / "inverted_index.csv")
    monkeypatch.setattr(cfg, "AGG_VOTERS_PER_WAHLBEZIRK_PATH", tmp_path / "waehler.csv")
    monkeypatch.setattr(cfg, "AUSWERTUNG_PATH", tmp_path / "auswertung.csv")
    with pytest.raises(EmptyResultError):
        analyse.main()
    assert not (tmp_path / "auswertung.csv").exists()
