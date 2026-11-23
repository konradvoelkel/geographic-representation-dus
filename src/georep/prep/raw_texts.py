"""Fundament F1: der Rohtext jedes PDFs, neben dem Text, den die Suche liest.

Der Textstore (``prep.extract``) hält den Text so, wie die Arbeit ihn las: kleingeschrieben, ohne
Zeilenumbrüche, erst ab dem Marker (``search.text_split_marker``). Für Abschnitte, Beträge,
Kopfdaten und Kurzfassungen reicht das nicht. Dieser zweite Store
(``cache_root/<profil>/text/rohtexte.parquet``, ``Layout.raw_texts``) hält denselben Extraktor
ungeglättet: Groß- und Kleinschreibung, Zeilenumbrüche, den Vorlagenkopf, und zwischen zwei Seiten
ein ``\\f`` (``stores.PAGE_BREAK``).

Die Brücke zwischen beiden ist eine Eigenschaft für jedes Dokument: ``flatten`` macht aus dem
Rohtext genau den Text des Textstores (``tests/property/test_raw_text_props.py``; über die ganze
Hauptperiode in ``tests/unit/test_data_packages.py``). Die eine Ausnahme ist eine Seite, deren Text
selbst ein ``\\f`` trägt -- eine defekte Schriftkodierung liefert Steuerzeichen statt Buchstaben.
Dort steht im Rohtext ein Leerzeichen (``PAGE_BREAK_STANDIN``), damit ``\\f`` nur den Seitenwechsel
bedeutet; geplättet steht dann ein Leerzeichen, wo der Textstore das ``\\f`` behält.

Dieselbe Bibliothek in derselben Version wie der Textstore (``pypdf==7.1.0``, Punkt 67), dieselbe
Fehlerbehandlung (``CorruptPdfError`` zählt als fehlerhaft, ein alter Text bleibt stehen), dieselbe
Regel für den Cache: neu gelesen wird nur, wenn PDF-Hash oder Extraktor sich geändert haben.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

import deal

from georep.errors import CorruptPdfError
from georep.prep.extract import ExtractReport, PypdfExtractor, after_marker, normalise_text
from georep.sources.pdfs import PdfStore
from georep.stores import PAGE_BREAK, RawTextStore

__all__ = [
    "DEFAULT_PAGE_EXTRACTOR",
    "PAGE_BREAK",
    "PAGE_BREAK_STANDIN",
    "RAW_SUFFIX",
    "PdfPageExtractor",
    "extract_raw_missing",
    "flatten",
    "raw_extractor_name",
    "raw_from_pages",
]

# Ein ``\f`` innerhalb einer Seite wird zu diesem Zeichen. So bleibt der Seitenwechsel eindeutig,
# und jede Seite behält ihre Länge: ein Offset innerhalb einer Seite ist der des Extraktors.
PAGE_BREAK_STANDIN = " "
# Der Zusatz am Extraktornamen (``pypdf-7.1.0+roh``). Ohne ihn stünde derselbe Name an zwei
# verschiedenen Texten, und wer die Stores verwechselt, merkte es an keiner Zeile.
RAW_SUFFIX = "+roh"


class PdfPageExtractor(Protocol):
    @property
    def name(self) -> str:
        """Bibliothek und Version wie bei ``PdfTextExtractor``; ein neuer Name macht alte Texte veraltet."""
        ...

    def pages(self, path: Path) -> list[str]:
        """Der rohe Text jeder Seite, in Reihenfolge; ``CorruptPdfError`` bei Defekt."""
        ...


DEFAULT_PAGE_EXTRACTOR: PdfPageExtractor = PypdfExtractor()


def raw_extractor_name(extractor: PdfPageExtractor) -> str:
    """Der Name, unter dem der Rohtextstore einen Text führt: der des Extraktors mit Zusatz."""
    return f"{extractor.name}{RAW_SUFFIX}"


# Kein ``deal.pure``: die Funktion läuft je Dokument, und der Patcher von ``deal.has`` ist
# prozessweit und nicht reentrant (CLAUDE.md, „Nie").
@deal.ensure(
    lambda pages, result: result.count(PAGE_BREAK) == max(len(pages) - 1, 0),
    message="zwischen n Seiten stehen n - 1 Seitenwechsel",
)
@deal.safe
def raw_from_pages(pages: Sequence[str]) -> str:
    """Die Seiten eines PDFs als ein Text, getrennt durch ``\\f``; ein ``\\f`` in einer Seite wird Leerzeichen."""
    return PAGE_BREAK.join(page.replace(PAGE_BREAK, PAGE_BREAK_STANDIN) for page in pages)


# ``deal.safe`` statt ``deal.pure``: ``normalise_text`` und ``after_marker`` sind selbst rein, und
# ein reiner Aufruf in einem reinen Aufruf ist genau der reentrante Patch, den CLAUDE.md verbietet.
@deal.pre(
    lambda raw, marker: marker != "", message="leerer Marker: str.split braucht einen Trenner"
)
@deal.ensure(
    lambda raw, marker, result: "\n" not in result and result == result.lower(),
    message="geplättet wie der Textstore: kleingeschrieben, eine Zeile",
)
@deal.safe
def flatten(raw: str, marker: str) -> str:
    """Rohtext zum Text des Textstores: Seitenwechsel zu Zeilenumbrüchen, dann wie ``prep.extract``."""
    return after_marker(normalise_text(raw.replace(PAGE_BREAK, "\n")), marker)


def extract_raw_missing(
    pdfs: PdfStore,
    store: RawTextStore,
    names: Iterable[str],
    extractor: PdfPageExtractor = DEFAULT_PAGE_EXTRACTOR,
) -> ExtractReport:
    """Den Rohtext jedes Namens lesen, der fehlt oder veraltet ist; ``save`` nur, wenn etwas neu ist.

    Das Gegenstück zu ``prep.extract.extract_missing``, Zeile für Zeile dieselbe Regel: ohne PDF
    zählt ein Name als fehlend, ein defektes PDF als fehlerhaft, und in beiden Fällen bleibt ein
    alter Text stehen.
    """
    report = ExtractReport()
    label = raw_extractor_name(extractor)
    for name in names:
        if not pdfs.has(name):
            report.missing += 1
            continue
        sha = pdfs.sha256(name)
        if store.is_current(name, pdf_sha256=sha, extractor=label):
            report.current += 1
            continue
        try:
            pages = extractor.pages(pdfs.path(name))
        except CorruptPdfError as error:
            report.failed += 1
            report.errors.append((name, str(error)))
            continue
        store.put(name, raw_from_pages(pages), pages=len(pages), extractor=label, pdf_sha256=sha)
        report.extracted += 1
    if report.extracted:
        store.save()
    return report
