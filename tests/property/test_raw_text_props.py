"""Fundament F1: der Rohtext ergibt, geplättet, genau den Text des Textstores.

Die zentrale Eigenschaft des zweiten Stores (docs/plan-vorverarbeitung-2026-11.md, § 7): wer den
Rohtext eines Dokuments nimmt, die Seitenwechsel zu Zeilenumbrüchen macht und dann rechnet wie
``prep/extract.py`` (``normalise_text``, ``after_marker``), bekommt den Text, den die Suche liest.
Nur dann ist eine Stelle, die ein späteres Vorhaben im Rohtext findet, dieselbe Stelle, die die
Suche zählt. Die Ausnahme ist eine Seite, deren Text selbst ein ``\\f`` trägt; dort steht im Rohtext
ein Leerzeichen, damit ``\\f`` nur den Seitenwechsel bedeutet (eine Stelle in der Hauptperiode,
``tests/unit/test_data_packages.py``).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.prep.extract import after_marker, extract_missing, normalise_text
from georep.prep.raw_texts import (
    PAGE_BREAK,
    PAGE_BREAK_STANDIN,
    extract_raw_missing,
    flatten,
    raw_from_pages,
)
from georep.sources.pdfs import PdfStore
from georep.stores import RawTextStore, TextStore

MARKERS = st.sampled_from(["betrifft", "Betrifft", "ß", "a b"])
# Seitentext ohne Seitenwechsel: Groß- und Sonderbuchstaben, deren Kleinschreibung mehr als ein
# Zeichen ist (İ), Zeilenumbrüche aller Art und Stücke, die den Marker enthalten. Nur Zeichen, die
# UTF-8 kodieren kann: einzelne Surrogate schreibt Parquet nicht, und ein Extraktor liefert keine.
FRAGMENTS = st.sampled_from(
    ["Betrifft:", "BETRIFFT", "\n", "\r\n", "\v", "İ", "Σ", "ẞ", "ä Ö", "a b", " ", "\t"]
)
PAGE = st.lists(
    st.one_of(
        st.text(st.characters(codec="utf-8", exclude_characters=PAGE_BREAK), max_size=12), FRAGMENTS
    ),
    max_size=8,
).map("".join)
PAGES = st.lists(PAGE, max_size=6)
# Wie oben, aber eine Seite darf selbst ein ``\f`` tragen (die defekte Schriftkodierung).
DIRTY_PAGES = st.lists(
    st.lists(st.one_of(PAGE, st.just(PAGE_BREAK)), max_size=4).map("".join), max_size=6
)


@given(pages=PAGES, marker=MARKERS)
def test_the_flattened_raw_text_is_the_text_of_the_store(pages: list[str], marker: str) -> None:
    """Rohtext → ``\\f`` zu ``\\n`` → ``normalise_text`` → ``after_marker`` = der Textstore."""
    store_text = after_marker(normalise_text("\n".join(pages)), marker)
    assert flatten(raw_from_pages(pages), marker) == store_text


@given(pages=DIRTY_PAGES)
def test_a_page_break_means_a_page_break_and_nothing_else(pages: list[str]) -> None:
    raw = raw_from_pages(pages)
    assert raw.count(PAGE_BREAK) == max(len(pages) - 1, 0)
    if pages:
        parts = raw.split(PAGE_BREAK)
        # Jede Seite behält ihre Länge; nur ein ``\f`` darin ist ersetzt.
        assert parts == [page.replace(PAGE_BREAK, PAGE_BREAK_STANDIN) for page in pages]


@given(pages=DIRTY_PAGES, marker=MARKERS)
def test_a_page_with_its_own_form_feed_differs_only_there(pages: list[str], marker: str) -> None:
    """Die eine bekannte Abweichung: geplättet steht ein Leerzeichen, wo der Store ein ``\\f`` hat."""
    clean = [page.replace(PAGE_BREAK, PAGE_BREAK_STANDIN) for page in pages]
    assert flatten(raw_from_pages(pages), marker) == after_marker(
        normalise_text("\n".join(clean)), marker
    )


class _Pages:
    """Ein Extraktor ohne Bibliothek: je Dateiname eine feste Liste von Seiten."""

    name = "fake-seiten-1"

    def __init__(self, pages: dict[str, list[str]]) -> None:
        self.by_name = pages

    def pages(self, path: Path) -> list[str]:
        return self.by_name[path.name]

    def extract(self, path: Path) -> str:
        return "\n".join(self.pages(path))


@given(
    documents=st.dictionaries(
        st.sampled_from([f"{i:08d}.pdf" for i in range(6)]), PAGES, max_size=6
    ),
    marker=MARKERS,
)
def test_both_stores_from_one_extractor_agree_on_every_document(
    tmp_path_factory: pytest.TempPathFactory, documents: dict[str, list[str]], marker: str
) -> None:
    """Beide Schritte über dieselben PDFs: für jedes Dokument ist der geplättete Rohtext der Text."""
    root = tmp_path_factory.mktemp("roh")
    pdfs = PdfStore(root / "pdf")
    pdfs.directory.mkdir()
    for name in documents:
        (pdfs.directory / name).write_bytes(f"%PDF {name}".encode())
    fake = _Pages(documents)
    texts = TextStore(root / "text" / "texts.parquet")
    raw = RawTextStore(root / "text" / "rohtexte.parquet")
    extract_missing(pdfs, texts, documents, marker, fake)
    extract_raw_missing(pdfs, raw, documents, fake)
    stored_texts, stored_raw = TextStore(texts.path), RawTextStore(raw.path)
    assert set(stored_raw.rows) == set(stored_texts.rows) == set(documents)
    for name in documents:
        assert flatten(stored_raw.get(name) or "", marker) == stored_texts.get(name)
    shutil.rmtree(root)
