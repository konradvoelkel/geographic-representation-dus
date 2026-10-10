"""Charakterisierung der PDF-Textextraktion des Altcodes auf vier echten Vorlagen (tests/fixtures/pdf)."""

from __future__ import annotations

from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

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


def test_missing_file_yields_empty_string(tmp_path: Path) -> None:
    # Heutiges Verhalten: Warnung und leerer String. Phase 1 macht daraus einen Fehler.
    assert get_text_from_pdf(tmp_path / "fehlt.pdf") == ""
