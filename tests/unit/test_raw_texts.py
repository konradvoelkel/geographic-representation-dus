"""Fundament F1: der Rohtextstore neben dem Textstore (``prep/raw_texts.py``, ``stores.py``)."""

from __future__ import annotations

import shutil
from pathlib import Path

import deal
import polars as pl
import pytest

from georep.prep.extract import DEFAULT_EXTRACTOR, after_marker, extract_missing, extract_text
from georep.prep.raw_texts import (
    DEFAULT_PAGE_EXTRACTOR,
    PAGE_BREAK,
    RAW_SUFFIX,
    extract_raw_missing,
    flatten,
    raw_extractor_name,
    raw_from_pages,
)
from georep.sources.pdfs import PdfStore
from georep.stores import RAW_TEXT_SCHEMA, RAW_TEXT_SCHEMA_VERSION, RawTextStore, TextStore

FILES = ["00438685.pdf", "00439409.pdf", "00519825.pdf", "00552781.pdf"]


def _pdfs(tmp_path: Path, pdf_fixtures: Path, names: list[str]) -> PdfStore:
    pdfs = PdfStore(tmp_path / "pdf")
    pdfs.directory.mkdir()
    for name in names:
        shutil.copy(pdf_fixtures / name, pdfs.directory / name)
    return pdfs


def test_the_raw_extractor_names_library_version_and_suffix() -> None:
    name = raw_extractor_name(DEFAULT_PAGE_EXTRACTOR)
    assert name == f"{DEFAULT_EXTRACTOR.name}{RAW_SUFFIX}" and name.startswith("pypdf-")
    assert name != DEFAULT_EXTRACTOR.name  # sonst wären die beiden Stores verwechselbar


@pytest.mark.parametrize("name", FILES)
def test_the_raw_text_keeps_case_lines_pages_and_the_head(pdf_fixtures: Path, name: str) -> None:
    pages = DEFAULT_PAGE_EXTRACTOR.pages(pdf_fixtures / name)
    raw = raw_from_pages(pages)
    assert len(pages) >= 1 and raw.count(PAGE_BREAK) == len(pages) - 1
    assert "\n" in raw and raw != raw.lower()
    # Der Vorlagenkopf vor „betrifft" ist da, der Textstore schneidet ihn ab.
    assert flatten(raw, "betrifft") != normalise_all(raw)
    assert flatten(raw, "betrifft") == after_marker(extract_text(pdf_fixtures / name), "betrifft")


def normalise_all(raw: str) -> str:
    return raw.replace(PAGE_BREAK, "").replace("\n", "").lower()


def test_extract_raw_missing_uses_the_cache_and_isolates_failures(
    pdf_fixtures: Path, tmp_path: Path
) -> None:
    pdfs = _pdfs(tmp_path, pdf_fixtures, FILES)
    (pdfs.directory / "kaputt.pdf").write_bytes(b"%PDF-1.4 aber kaputt")
    raw = RawTextStore(tmp_path / "text" / "rohtexte.parquet")
    names = [*FILES, "kaputt.pdf", "fehlt.pdf"]

    first = extract_raw_missing(pdfs, raw, names)
    assert (first.extracted, first.current, first.failed, first.missing) == (4, 0, 1, 1)
    assert first.errors[0][0] == "kaputt.pdf" and "kaputt.pdf" not in RawTextStore(raw.path)
    stored = RawTextStore(raw.path)
    assert len(stored) == 4
    row = stored.rows[FILES[0]]
    assert row["extractor"] == raw_extractor_name(DEFAULT_PAGE_EXTRACTOR)
    assert row["pdf_sha256"] == pdfs.sha256(FILES[0])
    assert row["chars"] == len(str(row["text"]))
    assert row["pages"] == str(row["text"]).count(PAGE_BREAK) + 1

    second = extract_raw_missing(pdfs, RawTextStore(raw.path), names)
    assert (second.extracted, second.current) == (0, 4)

    (pdfs.directory / FILES[0]).write_bytes((pdf_fixtures / FILES[1]).read_bytes())  # PDF geändert
    third = extract_raw_missing(pdfs, RawTextStore(raw.path), FILES)
    assert (third.extracted, third.current) == (1, 3)


def test_the_four_fixture_pdfs_flatten_to_the_text_store(
    pdf_fixtures: Path, tmp_path: Path
) -> None:
    """Die Abnahme von F1 an echten PDFs: beide Schritte, ein Extraktor, dieselben Texte."""
    pdfs = _pdfs(tmp_path, pdf_fixtures, FILES)
    texts = TextStore(tmp_path / "text" / "texts.parquet")
    raw = RawTextStore(tmp_path / "text" / "rohtexte.parquet")
    extract_missing(pdfs, texts, FILES, "betrifft")
    extract_raw_missing(pdfs, raw, FILES)
    for name in FILES:
        assert flatten(RawTextStore(raw.path).get(name) or "", "betrifft") == TextStore(
            texts.path
        ).get(name)


def test_the_store_file_carries_its_schema(pdf_fixtures: Path, tmp_path: Path) -> None:
    raw = RawTextStore(tmp_path / "text" / "rohtexte.parquet")
    extract_raw_missing(_pdfs(tmp_path, pdf_fixtures, FILES[:1]), raw, FILES[:1])
    assert pl.read_parquet_schema(raw.path) == RAW_TEXT_SCHEMA
    stored = pl.read_parquet_metadata(raw.path)["georep.schema_version"]
    assert stored == str(RAW_TEXT_SCHEMA_VERSION)


def test_an_empty_store_saves_an_empty_file(tmp_path: Path) -> None:
    """Ohne PDFs (CI, Pages) schreibt der Schritt einen leeren Store, statt zu scheitern."""
    raw = RawTextStore(tmp_path / "text" / "rohtexte.parquet")
    report = extract_raw_missing(PdfStore(tmp_path / "pdf"), raw, ["a.pdf", "b.pdf"])
    assert (report.extracted, report.missing) == (0, 2) and not raw.path.exists()
    raw.save()
    assert pl.read_parquet(raw.path).height == 0 and len(RawTextStore(raw.path)) == 0


def test_a_form_feed_inside_a_page_becomes_a_space() -> None:
    """Die defekte Schriftkodierung der Hauptperiode (``00532917.pdf``) liefert ``\\f`` im Seitentext."""
    raw = raw_from_pages(["Kopf\x0cA", "Seite 2"])
    assert raw == "Kopf A\fSeite 2"
    assert raw_from_pages([]) == "" and raw_from_pages([""]) == ""


def test_the_store_refuses_a_row_whose_page_count_lies(tmp_path: Path) -> None:
    """Der Vertrag an der Batch-Grenze: ``save`` prüft jede Zeile einmal, nicht ``put`` je Dokument."""
    raw = RawTextStore(tmp_path / "rohtexte.parquet")
    raw.put("a.pdf", "eins\fzwei", pages=3, extractor="x+roh", pdf_sha256="0" * 64)
    with pytest.raises(deal.PreContractError):
        raw.save()
    raw.put("a.pdf", "eins\fzwei", pages=2, extractor="x+roh", pdf_sha256="0" * 64)
    raw.save()
    assert RawTextStore(raw.path).is_current("a.pdf", pdf_sha256="0" * 64, extractor="x+roh")
    assert not RawTextStore(raw.path).is_current("a.pdf", pdf_sha256="1" * 64, extractor="x+roh")
    assert not RawTextStore(raw.path).is_current("a.pdf", pdf_sha256="0" * 64, extractor="y+roh")
    assert not RawTextStore(raw.path).is_current("b.pdf", pdf_sha256="0" * 64, extractor="x+roh")


def test_flatten_needs_a_marker() -> None:
    with pytest.raises(deal.PreContractError):
        flatten("Kopf\nBetrifft: Rest", "")
    assert flatten("Kopf\fBetrifft: Rest", "betrifft") == ": rest"
