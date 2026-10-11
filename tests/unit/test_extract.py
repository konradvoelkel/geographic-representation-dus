from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from georep.errors import CorruptPdfError
from georep.prep.extract import (
    DEFAULT_EXTRACTOR,
    PdfTextExtractor,
    after_marker,
    extract_missing,
    extract_text,
)
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
        and meta.extractor == DEFAULT_EXTRACTOR.name
        and meta.pdf_sha256 == pdfs.sha256(FILES[0])
    )
    assert not (TextStore(texts.path).get(FILES[0]) or "").startswith("betrifft")

    second = extract_missing(pdfs, TextStore(texts.path), names, "betrifft")
    assert (second.extracted, second.current) == (0, 4)

    (pdfs.directory / FILES[0]).write_bytes((pdf_fixtures / FILES[1]).read_bytes())  # PDF geändert
    third = extract_missing(pdfs, TextStore(texts.path), FILES, "betrifft")
    assert (third.extracted, third.current) == (1, 3)


class _FakeExtractor:
    """Erfüllt ``PdfTextExtractor`` ohne Bibliothek: liefert festen Text mit Umbrüchen und Großbuchstaben."""

    name = "fake-1"

    def extract(self, path: Path) -> str:
        return f"Kopf {path.name}\nBETRIFFT: Inhalt\n"


def test_default_extractor_names_library_and_version() -> None:
    assert DEFAULT_EXTRACTOR.name.startswith("pypdf-") and DEFAULT_EXTRACTOR.name != "pypdf-"


def test_extract_missing_keys_the_cache_by_extractor_name(
    pdf_fixtures: Path, tmp_path: Path
) -> None:
    pdfs = PdfStore(tmp_path / "pdf")
    pdfs.directory.mkdir()
    shutil.copy(pdf_fixtures / FILES[0], pdfs.directory / FILES[0])
    texts = TextStore(tmp_path / "text" / "texts.parquet")
    fake: PdfTextExtractor = _FakeExtractor()

    assert extract_text(pdfs.path(FILES[0]), fake) == f"kopf {FILES[0]}betrifft: inhalt"
    first = extract_missing(pdfs, texts, FILES[:1], "betrifft", fake)
    assert (first.extracted, first.current) == (1, 0)
    stored = TextStore(texts.path)
    meta = stored.meta(FILES[0])
    assert meta is not None and meta.extractor == "fake-1" and meta.source == "pdf"
    assert stored.get(FILES[0]) == ": inhalt"

    # Derselbe Hash, anderer Extraktor: der Text gilt als veraltet und wird neu berechnet.
    second = extract_missing(pdfs, TextStore(texts.path), FILES[:1], "betrifft")
    assert (second.extracted, second.current) == (1, 0)
    renewed = TextStore(texts.path).meta(FILES[0])
    assert renewed is not None and renewed.extractor == DEFAULT_EXTRACTOR.name
