"""Text aus PDFs, mit Cache je Dateiname und Extraktor-Version.

Wie in der Arbeit: alle Seiten, Zeilenumbrüche weg, kleingeschrieben, und alles vor dem ersten
Vorkommen des Markers (``betrifft``, Düsseldorfer Vorlagenkopf) verworfen. Ein Text wird nur neu
berechnet, wenn PDF-Hash oder Extraktor sich geändert haben.

Die Bibliothek steht hinter ``PdfTextExtractor``: ``name`` ist der Cache-Schlüssel im Textstore,
``extract`` liefert den rohen Text aller Seiten. ``PypdfExtractor`` ist die Implementierung der
Arbeit; ein Ersatz (pypdfium2, pymupdf) muss den Golden Master der vier Fixture-PDFs bestehen
oder seine Abweichung dokumentieren (DEVELOPMENT_PLAN.md § 3.5).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import pypdf
from pypdf import PdfReader

from georep.errors import CorruptPdfError
from georep.sources.pdfs import PdfStore
from georep.stores import TextMeta, TextStore


class PdfTextExtractor(Protocol):
    @property
    def name(self) -> str:
        """Bibliothek und Version, z. B. ``pypdf-6.6.2``; ein neuer Name macht alte Texte veraltet."""
        ...

    def extract(self, path: Path) -> str:
        """Roher Text aller Seiten, Seiten durch Zeilenumbruch getrennt; ``CorruptPdfError`` bei Defekt."""
        ...


class PypdfExtractor:
    """pypdf, wie in der Arbeit; jede Ausnahme der Bibliothek wird zu ``CorruptPdfError``."""

    @property
    def name(self) -> str:
        return f"pypdf-{pypdf.__version__}"

    def extract(self, path: Path) -> str:
        try:
            with path.open("rb") as f:
                reader = PdfReader(f)
                return "\n".join(page.extract_text() for page in reader.pages)
        # pypdf wirft je nach Defekt PdfReadError, ValueError, KeyError, ...
        except Exception as error:
            raise CorruptPdfError(f"{path.name}: {error}") from error


DEFAULT_EXTRACTOR: PdfTextExtractor = PypdfExtractor()


def normalise_text(raw: str) -> str:
    """Wie die Arbeit: Zeilenumbrüche weg, kleingeschrieben."""
    return raw.replace("\n", "").lower()


def extract_text(path: Path, extractor: PdfTextExtractor = DEFAULT_EXTRACTOR) -> str:
    """Text aller Seiten, kleingeschrieben, ohne Zeilenumbrüche; Fehler statt leerem String."""
    if not path.is_file():
        raise FileNotFoundError(path)
    return normalise_text(extractor.extract(path))


def after_marker(text: str, marker: str) -> str:
    parts = text.split(marker, 1)
    return parts[1] if len(parts) > 1 else parts[0]


@dataclass
class ExtractReport:
    extracted: int = 0
    current: int = 0
    failed: int = 0
    missing: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.extracted} extrahiert, {self.current} aktuell, {self.failed} fehlerhaft, "
            f"{self.missing} ohne PDF"
        )


def extract_missing(
    pdfs: PdfStore,
    texts: TextStore,
    names: Iterable[str],
    marker: str,
    extractor: PdfTextExtractor = DEFAULT_EXTRACTOR,
) -> ExtractReport:
    report = ExtractReport()
    for name in names:
        if not pdfs.has(name):
            report.missing += 1
            continue
        sha = pdfs.sha256(name)
        if texts.is_current(name, pdf_sha256=sha, extractor=extractor.name):
            report.current += 1
            continue
        try:
            text = after_marker(extract_text(pdfs.path(name), extractor), marker)
        except CorruptPdfError as error:
            report.failed += 1
            report.errors.append((name, str(error)))
            continue
        texts.put(name, text, TextMeta(extractor=extractor.name, pdf_sha256=sha, source="pdf"))
        report.extracted += 1
    if report.extracted:
        texts.save()
    return report
