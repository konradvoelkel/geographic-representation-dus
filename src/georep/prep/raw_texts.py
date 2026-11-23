"""Fundament F1: der Rohtext jedes PDFs, neben dem Text, den die Suche liest.

Der Textstore (``prep.extract``) hält den Text so, wie die Arbeit ihn las: kleingeschrieben, ohne
Zeilenumbrüche, erst ab dem Marker (``search.text_split_marker``). Für Abschnitte, Beträge,
Kopfdaten und Kurzfassungen reicht das nicht. Dieser zweite Store
(``cache_root/<profil>/text/rohtexte.parquet``, ``Layout.raw_texts``) hält denselben Extraktor
ungeglättet: Groß- und Kleinschreibung, Zeilenumbrüche, den Vorlagenkopf, und zwischen zwei Seiten
ein ``\\f`` (``stores.PAGE_BREAK``).

Die Brücke zwischen beiden ist eine Eigenschaft für **jedes** Dokument: ``flatten`` macht aus dem
Rohtext genau den Text des Textstores (``tests/property/test_raw_text_props.py``; über die ganze
Hauptperiode in ``tests/unit/test_data_packages.py``). Ein ``\\f`` im Text einer Seite -- eine
defekte Schriftkodierung liefert Steuerzeichen statt Buchstaben -- steht im Rohtext als Leerzeichen
(``stores.PAGE_BREAK_STANDIN``), damit ``\\f`` nur den Seitenwechsel bedeutet; seine Offsets stehen
in der Spalte ``form_feeds``, und ``flatten`` setzt es dort zurück (Review F1, M3). So bleibt die
Seitenstruktur eindeutig, und die Plättung ist trotzdem genau.

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
from georep.stores import PAGE_BREAK, PAGE_BREAK_STANDIN, RawTextStore

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
    "restore_form_feeds",
]

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


def _feeds_point_at_standins(raw: str, form_feeds: Sequence[int]) -> bool:
    return all(0 <= i < len(raw) and raw[i] == PAGE_BREAK_STANDIN for i in form_feeds)


# ``deal.safe``, kein ``deal.pure``: die Funktionen laufen je Dokument und rufen einander, und der
# Patcher von ``deal.has`` ist prozessweit und nicht reentrant (CLAUDE.md, „Nie").
@deal.pre(
    lambda raw, form_feeds: _feeds_point_at_standins(raw, form_feeds),
    message="ein Offset in form_feeds zeigt nicht auf ein Ersatzzeichen",
)
@deal.ensure(
    lambda raw, form_feeds, result: len(result) == len(raw),
    message="das Zurücksetzen ändert keine Länge",
)
@deal.safe
def restore_form_feeds(raw: str, form_feeds: Sequence[int]) -> str:
    """Der Text mit den ``\\f`` aus dem Text der Seiten zurück, dort, wo ``form_feeds`` hinzeigt."""
    if not form_feeds:
        return raw
    chars = list(raw)
    for i in form_feeds:
        chars[i] = PAGE_BREAK
    return "".join(chars)


@deal.ensure(
    lambda pages, result: result[0].count(PAGE_BREAK) == max(len(pages) - 1, 0),
    message="zwischen n Seiten stehen n - 1 Seitenwechsel und sonst kein Formfeed",
)
@deal.ensure(
    lambda pages, result: restore_form_feeds(*result) == PAGE_BREAK.join(pages),
    message="mit den Offsets zurückgesetzt ist der Rohtext genau die Seiten",
)
@deal.safe
def raw_from_pages(pages: Sequence[str]) -> tuple[str, tuple[int, ...]]:
    """Die Seiten eines PDFs als ein Text mit ``\\f`` dazwischen, und die Offsets der inneren ``\\f``.

    Ein ``\\f`` im Text einer Seite wird ``PAGE_BREAK_STANDIN``; seine Stelle im ganzen Text steht im
    zweiten Teil des Ergebnisses, fast immer leer.
    """
    feeds: list[int] = []
    start = 0
    for page in pages:
        found = page.find(PAGE_BREAK)
        while found != -1:
            feeds.append(start + found)
            found = page.find(PAGE_BREAK, found + 1)
        start += len(page) + len(PAGE_BREAK)
    text = PAGE_BREAK.join(page.replace(PAGE_BREAK, PAGE_BREAK_STANDIN) for page in pages)
    return text, tuple(feeds)


# Benannte Validatoren vor dem ganzen Stapel, weil ``form_feeds`` optional ist: das mypy-Plugin von
# deal modelliert ``result`` als positionalen Parameter hinter den Argumenten (CLAUDE.md, deal).
def _flatten_has_a_marker(raw: str, marker: str, form_feeds: Sequence[int]) -> bool:
    return marker != ""


def _flatten_feeds_are_valid(raw: str, marker: str, form_feeds: Sequence[int]) -> bool:
    return _feeds_point_at_standins(raw, form_feeds)


def _flattened_like_the_store(
    raw: str, marker: str, form_feeds: Sequence[int], result: str = ""
) -> bool:
    return "\n" not in result and result == result.lower()


@deal.pre(_flatten_has_a_marker, message="leerer Marker: str.split braucht einen Trenner")
@deal.pre(
    _flatten_feeds_are_valid, message="ein Offset in form_feeds zeigt nicht auf ein Ersatzzeichen"
)
@deal.ensure(
    _flattened_like_the_store, message="geplättet wie der Textstore: kleingeschrieben, eine Zeile"
)
@deal.safe
def flatten(raw: str, marker: str, form_feeds: Sequence[int]) -> str:
    """Rohtext zum Text des Textstores: Seitenwechsel zu Zeilenumbrüchen, die ``\\f`` der Seiten
    zurück, dann wie ``prep.extract`` (``normalise_text``, ``after_marker``).

    Erst die Seitenwechsel, dann die inneren ``\\f``: beide Ersetzungen behalten die Länge, die
    Offsets bleiben gültig, und kein inneres ``\\f`` wird zum Zeilenumbruch. ``form_feeds`` ist
    Pflicht (Review F1, dritte Runde): eine Vorgabe ``()`` plättete einen Aufruf ohne Offsets still
    wie Schema-Version 1; aus dem Store kommen sie mit ``RawTextStore.form_feeds(name)``.
    """
    lines = raw.replace(PAGE_BREAK, "\n")
    return after_marker(normalise_text(restore_form_feeds(lines, form_feeds)), marker)


def extract_raw_missing(
    pdfs: PdfStore,
    store: RawTextStore,
    names: Iterable[str],
    extractor: PdfPageExtractor = DEFAULT_PAGE_EXTRACTOR,
) -> ExtractReport:
    """Den Rohtext jedes Namens lesen, der fehlt oder veraltet ist; ``save`` nur, wenn etwas neu ist.

    Das Gegenstück zu ``prep.extract.extract_missing``, Zeile für Zeile dieselbe Regel: ohne PDF
    zählt ein Name als fehlend, ein defektes PDF als fehlerhaft, und in beiden Fällen bleibt ein
    alter Text stehen. Trägt die Datei eine andere Schema-Version, gilt der Store als leer
    (``RawTextStore.stale``), und jedes PDF wird neu gelesen.
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
        text, feeds = raw_from_pages(pages)
        store.put(name, text, pages=len(pages), extractor=label, pdf_sha256=sha, form_feeds=feeds)
        report.extracted += 1
    if report.extracted:
        store.save()
    return report
