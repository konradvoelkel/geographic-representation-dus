"""Text aus PDFs, mit Cache je Dateiname und Extraktor-Version.

Wie in der Arbeit: alle Seiten mit pypdf, Zeilenumbrüche weg, kleingeschrieben, und alles vor
dem ersten Vorkommen des Markers (``betrifft``, Düsseldorfer Vorlagenkopf) verworfen. Ein Text
wird nur neu berechnet, wenn PDF-Hash oder Extraktor sich geändert haben.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pypdf
from pypdf import PdfReader

from georep.errors import CorruptPdfError
from georep.sources.pdfs import PdfStore
from georep.stores import TextMeta, TextStore

EXTRACTOR = f"pypdf-{pypdf.__version__}"


def extract_text(path: Path) -> str:
    """Text aller Seiten, kleingeschrieben, ohne Zeilenumbrüche; Fehler statt leerem String."""
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        with path.open("rb") as f:
            reader = PdfReader(f)
            text = "\n".join(page.extract_text() for page in reader.pages)
    except Exception as error:  # pypdf wirft je nach Defekt PdfReadError, ValueError, KeyError, ...
        raise CorruptPdfError(f"{path.name}: {error}") from error
    return text.replace("\n", "").lower()


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
    pdfs: PdfStore, texts: TextStore, names: Iterable[str], marker: str
) -> ExtractReport:
    report = ExtractReport()
    for name in names:
        if not pdfs.has(name):
            report.missing += 1
            continue
        sha = pdfs.sha256(name)
        if texts.is_current(name, pdf_sha256=sha, extractor=EXTRACTOR):
            report.current += 1
            continue
        try:
            text = after_marker(extract_text(pdfs.path(name)), marker)
        except CorruptPdfError as error:
            report.failed += 1
            report.errors.append((name, str(error)))
            continue
        texts.put(name, text, TextMeta(extractor=EXTRACTOR, pdf_sha256=sha, source="pdf"))
        report.extracted += 1
    if report.extracted:
        texts.save()
    return report
