"""Den eingefrorenen Datensatz der Arbeit nach ``data_root`` übernehmen.

Rohdaten und Wahlergebnis werden kopiert; aus dem Korpus der Arbeit (``paper_with_text.json``)
entstehen ``raw/papers.jsonl`` (Metadaten) und der Textstore (Texte, Herkunft ``reference``, ohne
PDF-Hash, weil die PDFs nicht Teil der Referenz sind). Vorhandenes bleibt stehen, ``force=True``
überschreibt. Der Lauf nennt, wie viele Dateien er kopiert, übersprungen und nicht gefunden hat.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from georep.io import atomic_path
from georep.layout import Layout
from georep.records import PaperRecord
from georep.stores import PaperStore, TextMeta, TextStore

REFERENCE_EXTRACTOR = "pypdf (Arbeit, Januar 2026)"


@dataclass
class BootstrapReport:
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    papers: int | None = None  # None = Stores nicht neu geschrieben
    texts: int | None = None

    def summary(self) -> str:
        stores = (
            f"{self.papers} Paper und {self.texts} Texte aus der Referenz"
            if self.papers is not None
            else "Stores vorhanden"
        )
        return (
            f"{len(self.copied)} Dateien kopiert, {len(self.skipped)} übersprungen, "
            f"{len(self.missing)} in der Referenz nicht gefunden; {stores}"
        )


def seed_stores_from_legacy(layout: Layout, items: list[dict[str, Any]]) -> tuple[int, int]:
    """``paper_with_text.json``-Einträge nach PaperStore und TextStore; liefert (Paper, Texte)."""
    records = [PaperRecord.from_legacy(item) for item in items]
    PaperStore(layout.guard_writable(layout.papers)).save(records)
    texts = TextStore(layout.guard_writable(layout.texts))
    stored = 0
    for item, record in zip(items, records, strict=True):
        text = item.get("paper_text") or ""
        if record.file_name and text:
            texts.put(
                record.file_name, text, TextMeta(extractor=REFERENCE_EXTRACTOR, source="reference")
            )
            stored += 1
    texts.save()
    return len(records), stored


def bootstrap(layout: Layout, *, force: bool = False) -> BootstrapReport:
    reference = layout.reference_view()
    layout.ensure_dirs()
    report = BootstrapReport()
    pairs = [
        (reference.results_csv, layout.results_csv),
        (reference.districts_geojson, layout.districts_geojson),
        (reference.streets, layout.streets),
        (reference.pois, layout.pois),
    ]
    for source, target in pairs:
        layout.guard_writable(target)
        if not source.is_file():
            report.missing.append(source.name)
            continue
        if target.exists() and not force:
            report.skipped.append(target.name)
            continue
        with atomic_path(target) as tmp:
            shutil.copyfile(source, tmp)
        report.copied.append(target.name)

    if not reference.corpus_legacy.is_file():
        report.missing.append(reference.corpus_legacy.name)
    elif force or not (layout.papers.exists() and layout.texts.exists()):
        items = json.loads(reference.corpus_legacy.read_text(encoding="utf-8"))
        report.papers, report.texts = seed_stores_from_legacy(layout, items)
    logger.success(f"Bootstrap aus {layout.reference_root}: {report.summary()}")
    return report
