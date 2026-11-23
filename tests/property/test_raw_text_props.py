"""Fundament F1: der Rohtext ergibt, geplättet, genau den Text des Textstores.

Die zentrale Eigenschaft des zweiten Stores (docs/plan-vorverarbeitung-2026-11.md, § 7): wer den
Rohtext eines Dokuments nimmt, die Seitenwechsel zu Zeilenumbrüchen macht und dann rechnet wie
``prep/extract.py`` (``normalise_text``, ``after_marker``), bekommt den Text, den die Suche liest.
Nur dann ist eine Stelle, die ein späteres Vorhaben im Rohtext findet, dieselbe Stelle, die die
Suche zählt. Das gilt ohne Ausnahme (Review F1, M3): trägt eine Seite selbst ein ``\\f``, steht im
Rohtext dort ein Leerzeichen, damit ``\\f`` nur den Seitenwechsel bedeutet, und ``flatten`` setzt
es über die Offsets in ``form_feeds`` zurück.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from georep.prep.extract import after_marker, extract_missing, normalise_text
from georep.prep.raw_texts import (
    PAGE_BREAK,
    PAGE_BREAK_STANDIN,
    extract_raw_missing,
    flatten,
    flatten_with_offsets,
    raw_from_pages,
    restore_form_feeds,
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


@given(pages=DIRTY_PAGES, marker=MARKERS)
@example(pages=["Kopf a\fb Rest"], marker="a b")  # Review F1: der Marker aus dem Ersatzzeichen
@example(pages=["Kopf\fBetrifft x", "y"], marker="betrifft")
def test_the_flattened_raw_text_is_the_text_of_the_store(pages: list[str], marker: str) -> None:
    """Rohtext → ``\\f`` zu ``\\n``, innere ``\\f`` zurück → ``normalise_text`` → ``after_marker``
    ist genau der Text, den ``extract_missing`` aus denselben Seiten bildet -- auch für Seiten, die
    selbst ein ``\\f`` tragen (Review F1, M3: ohne Ausnahme)."""
    store_text = after_marker(normalise_text("\n".join(pages)), marker)
    raw, feeds = raw_from_pages(pages)
    assert flatten(raw, marker, feeds) == store_text


@given(pages=DIRTY_PAGES)
def test_a_page_break_means_a_page_break_and_nothing_else(pages: list[str]) -> None:
    raw, feeds = raw_from_pages(pages)
    assert raw.count(PAGE_BREAK) == max(len(pages) - 1, 0)
    assert list(feeds) == sorted(feeds) and all(raw[i] == PAGE_BREAK_STANDIN for i in feeds)
    assert restore_form_feeds(raw, feeds) == PAGE_BREAK.join(pages)
    if pages:
        parts = raw.split(PAGE_BREAK)
        # Jede Seite behält ihre Länge; nur ein ``\f`` darin ist ersetzt.
        assert parts == [page.replace(PAGE_BREAK, PAGE_BREAK_STANDIN) for page in pages]


# --- Nachzug F1: die Stelle im Rohtext je Zeichen (Synergien 2026-11, Konflikt 1) -------------


def each_character_is_its_source_lowercased(text: str, offsets: Sequence[int], source: str) -> bool:
    """Jedes Zeichen des geplätteten Texts ist die Kleinschreibung des Zeichens an seiner Stelle.

    ``source`` ist der Rohtext mit den ``\f`` der Seiten zurück (``restore_form_feeds``). Gleiche
    Offsets nebeneinander sind eine Gruppe: die Kleinschreibung eines Zeichens kann mehrere sein
    (``"İ".lower()``), und die Gruppe ist dann genau sie -- am Anfang darf der Marker sie teilen.
    Die einzige Kontextregel von ``str.lower`` ist das Schluss-Sigma (Σ wird ς). Schneller Weg für
    die Hauptperiode: sind die Zeichen an den Offsets, kleingeschrieben, schon der Text, gilt es
    für jedes (gleich lang heißt: kein Zeichen wurde zu mehreren).
    """
    if "".join(map(source.__getitem__, offsets)).lower() == text:
        return True
    i = 0
    while i < len(text):
        at, j = offsets[i], i
        while j < len(text) and offsets[j] == at:
            j += 1
        lowered, chunk = source[at].lower(), text[i:j]
        if not (
            chunk == lowered
            or (i == 0 and lowered.endswith(chunk))
            or (source[at] == "Σ" and chunk == "ς")
        ):
            return False
        i = j
    return True


@given(pages=DIRTY_PAGES, marker=MARKERS)
@example(pages=["Kopf a\fb Rest"], marker="a b")  # der Marker aus dem Ersatzzeichen
@example(pages=["İİ Kopf\nBetrifft: ΑΣ Σ x\f", "İ\nende"], marker="betrifft")
@example(pages=["ẞ\n\nß a", "", "\n"], marker="ß")  # der Marker ist ein Rohtextzeichen
def test_flatten_with_offsets_is_flatten_with_a_place_in_the_raw_text(
    pages: list[str], marker: str
) -> None:
    """Der Text ist genau der von ``flatten``, je Zeichen eine Stelle im Rohtext, aufsteigend, nie
    auf einem Zeilenumbruch oder Seitenwechsel, und dort steht das Zeichen in Großschreibung."""
    raw, feeds = raw_from_pages(pages)
    text, offsets = flatten_with_offsets(raw, marker, feeds)
    assert text == flatten(raw, marker, feeds)
    assert len(offsets) == len(text)
    assert list(offsets) == sorted(offsets)
    assert all(raw[at] not in ("\n", PAGE_BREAK) for at in offsets)
    assert each_character_is_its_source_lowercased(text, offsets, restore_form_feeds(raw, feeds))


@given(pages=DIRTY_PAGES, marker=MARKERS)
def test_an_inner_form_feed_maps_to_its_stored_offset(pages: list[str], marker: str) -> None:
    """Ein ``\f`` aus dem Text einer Seite steht im geplätteten Text und zeigt auf die Stelle,
    die ``form_feeds`` nennt (Review F1, M3; im Paket ``00532917.pdf`` mit 41)."""
    raw, feeds = raw_from_pages(pages)
    text, offsets = flatten_with_offsets(raw, marker, feeds)
    assert {offsets[i] for i, char in enumerate(text) if char == PAGE_BREAK} <= set(feeds)


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
        st.sampled_from([f"{i:08d}.pdf" for i in range(6)]), DIRTY_PAGES, max_size=6
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
        raw_text = stored_raw.get(name) or ""
        assert flatten(raw_text, marker, stored_raw.form_feeds(name)) == stored_texts.get(name)
    shutil.rmtree(root)
