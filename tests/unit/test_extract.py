from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from georep.errors import CorruptPdfError
from georep.prep.extract import EXTRACTOR, after_marker, extract_missing, extract_text
from georep.sources.pdfs import PdfStore
from georep.stores import TextStore

FILES = ["00438685.pdf", "00439409.pdf", "00519825.pdf", "00552781.pdf"]


@pytest.mark.parametrize("name", FILES)
def test_text_is_lowercase_single_line_with_marker(pdf_fixtures: Path, name: str) -> None:
    text = extract_text(pdf_fixtures / name)
    assert text and text == text.lower() and "\n" not in text and "betrifft" in text


@pytest.mark.parametrize("name", FILES)
def test_text_after_marker_snapshot(
    pdf_fixtures: Path, name: str, snapshot: SnapshotAssertion
) -> None:
    text = extract_text(pdf_fixtures / name)
    assert {"chars": len(text), "after_betrifft": after_marker(text, "betrifft")[:120]} == snapshot


def test_missing_and_corrupt_files_raise(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        extract_text(tmp_path / "fehlt.pdf")
    (tmp_path / "kaputt.pdf").write_bytes(b"das ist kein pdf")
    with pytest.raises(CorruptPdfError, match="kaputt.pdf"):
        extract_text(tmp_path / "kaputt.pdf")


def test_after_marker_keeps_text_without_marker() -> None:
    assert after_marker("kopf betrifft: inhalt", "betrifft") == ": inhalt"
    assert after_marker("ohne marker", "betrifft") == "ohne marker"


def test_extract_missing_uses_cache_and_isolates_failures(
    pdf_fixtures: Path, tmp_path: Path
) -> None:
    pdfs = PdfStore(tmp_path / "pdf")
    pdfs.directory.mkdir()
    for name in FILES:
        shutil.copy(pdf_fixtures / name, pdfs.directory / name)
    (pdfs.directory / "kaputt.pdf").write_bytes(b"%PDF-1.4 aber kaputt")
    texts = TextStore(tmp_path / "text" / "texts.parquet")
    names = [*FILES, "kaputt.pdf", "fehlt.pdf"]

    first = extract_missing(pdfs, texts, names, "betrifft")
    assert (first.extracted, first.current, first.failed, first.missing) == (4, 0, 1, 1)
    assert first.errors[0][0] == "kaputt.pdf"
    assert texts.path.exists() and len(TextStore(texts.path)) == 4
    meta = TextStore(texts.path).meta(FILES[0])
    assert (
        meta is not None
        and meta.extractor == EXTRACTOR
        and meta.pdf_sha256 == pdfs.sha256(FILES[0])
    )
    assert not (TextStore(texts.path).get(FILES[0]) or "").startswith("betrifft")

    second = extract_missing(pdfs, TextStore(texts.path), names, "betrifft")
    assert (second.extracted, second.current) == (0, 4)

    (pdfs.directory / FILES[0]).write_bytes((pdf_fixtures / FILES[1]).read_bytes())  # PDF geändert
    third = extract_missing(pdfs, TextStore(texts.path), FILES, "betrifft")
    assert (third.extracted, third.current) == (1, 3)
