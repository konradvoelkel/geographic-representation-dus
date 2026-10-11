"""Charakterisierung der PDF-Textextraktion des Altcodes auf vier echten Vorlagen (tests/fixtures/pdf)."""

from __future__ import annotations

from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from georep.errors import CorruptPdfError
from src.prep_papers import get_text_from_pdf

FILES = ["00438685.pdf", "00439409.pdf", "00519825.pdf", "00552781.pdf"]


@pytest.mark.parametrize("name", FILES)
def test_text_is_lowercase_single_line_with_betrifft(pdf_fixtures: Path, name: str) -> None:
    text = get_text_from_pdf(pdf_fixtures / name)
    assert text
    assert text == text.lower()
    assert "\n" not in text
    assert "betrifft" in text


@pytest.mark.parametrize("name", FILES)
def test_text_after_betrifft_snapshot(
    pdf_fixtures: Path, name: str, snapshot: SnapshotAssertion
) -> None:
    text = get_text_from_pdf(pdf_fixtures / name)
    after = text.split("betrifft", 1)[1][:120]  # so schneidet prep_papers.main den Vorlagenkopf ab
    assert {"chars": len(text), "after_betrifft": after} == snapshot


def test_missing_file_raises(tmp_path: Path) -> None:
    # Bis 2026-10-11 kam ein leerer String zurück; ein fehlendes PDF war von einem leeren nicht zu unterscheiden.
    with pytest.raises(FileNotFoundError):
        get_text_from_pdf(tmp_path / "fehlt.pdf")


def test_corrupt_file_raises_domain_error(tmp_path: Path) -> None:
    broken = tmp_path / "kaputt.pdf"
    broken.write_bytes(b"das ist kein pdf")
    with pytest.raises(CorruptPdfError, match="kaputt.pdf"):
        get_text_from_pdf(broken)
