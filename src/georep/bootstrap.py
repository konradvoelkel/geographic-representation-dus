"""Einen eingefrorenen Datensatz nach ``data_root`` übernehmen.

Rohdaten und Wahlergebnis werden kopiert; aus dem Korpus der Arbeit (``paper_with_text.json``)
entstehen ``raw/papers.jsonl`` (Metadaten) und der Textstore (Texte, Herkunft ``reference``, ohne
PDF-Hash, weil die PDFs nicht Teil der Referenz sind). Die Fremddaten unter ``context_root``
(Option 03) kommen auf demselben Weg nach ``external/``; fehlen sie, ist das kein Abbruch, sondern
eine Zeile im Bericht. Ein Schnappschuss, der aus einem echten Lauf stammt (Option 02: die
Wahlperiode 2014 bis 2020), trägt ``raw/papers.jsonl`` und den Textstore schon im eigenen Format;
dann werden sie nur kopiert. Vorhandenes bleibt stehen, ``force=True`` überschreibt. Der Lauf
nennt, wie viele Dateien er kopiert, übersprungen und nicht gefunden hat.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from georep.io import atomic_path
from georep.layout import Layout
from georep.records import PaperRecord
from georep.sources.pdfs import PdfStore
from georep.stores import PaperStore, TextMeta, TextStore

REFERENCE_EXTRACTOR = "pypdf (Arbeit, Januar 2026)"


@dataclass
class BootstrapReport:
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    papers: int | None = None  # None = Stores nicht neu geschrieben
    texts: int | None = None
    seed_corpus: bool = (
        True  # False: Stores absichtlich leer gelassen (Option 07, laufende Periode)
    )

    def summary(self) -> str:
        if not self.seed_corpus:
            stores = "Stores nicht aus der Referenz gefüllt (bootstrap.seed_corpus = false)"
        elif self.papers is not None:
            stores = f"{self.papers} Paper und {self.texts} Texte aus der Referenz"
        else:
            stores = "Stores vorhanden"
        return (
            f"{len(self.copied)} Dateien kopiert, {len(self.skipped)} übersprungen, "
            f"{len(self.missing)} in Referenz oder Kontext nicht gefunden; {stores}"
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


def _copy_input(
    layout: Layout, source: Path, target: Path, report: BootstrapReport, *, force: bool
) -> None:
    layout.guard_writable(target)
    if not source.is_file():
        report.missing.append(source.name)
        return
    if target.exists() and not force:
        report.skipped.append(target.name)
        return
    with atomic_path(target) as tmp:
        shutil.copyfile(source, tmp)
    report.copied.append(target.name)


def seed_stores_from_native(layout: Layout, reference: Layout) -> tuple[int, int]:
    """Metadaten und Textstore eines Schnappschusses im eigenen Format kopieren; liefert die Zahlen.

    Option 02: der Schnappschuss einer zweiten Periode entsteht aus einem echten Lauf, nicht aus
    dem Korpus der Arbeit. Er trägt darum ``raw/papers.jsonl`` und ``cache/text/texts.parquet``
    unverändert; kopieren genügt, nichts wird umgerechnet.
    """
    for source, target in ((reference.papers, layout.papers), (reference.texts, layout.texts)):
        with atomic_path(layout.guard_writable(target)) as tmp:
            shutil.copyfile(source, tmp)
    return len(PaperStore(layout.papers).load()), len(TextStore(layout.texts))


def bootstrap(
    layout: Layout,
    *,
    force: bool = False,
    context_files: Sequence[str] = (),
    needs_dictionary: bool = True,
    seed_corpus: bool = True,
) -> BootstrapReport:
    """Die Eingaben aus ``reference_root`` übernehmen.

    ``context_files`` sind die Namen aus ``settings.context.files``; ohne ``context_root``
    leer (Option 03). ``needs_dictionary`` ist die Naht von Option 02: ein Periodenprofil mit
    ``period.dictionary = "base"`` braucht keine Straßen und Orte in seiner Referenz, es liest
    das Wörterbuch der Hauptperiode. Dann sind die beiden Dateien nicht fehlend, sondern nicht
    zuständig. ``seed_corpus`` ist die Naht von Option 07: ein Profil mit laufender Periode
    bekommt die Eingaben der Referenz, aber keine Paper und Texte der Hauptperiode; die holt
    sein Netzschritt ``papers`` selbst.
    """
    reference = layout.reference_view()
    layout.ensure_dirs()
    PdfStore(layout.pdf_dir).ensure()
    report = BootstrapReport(seed_corpus=seed_corpus)
    pairs = [
        (reference.results_csv, layout.results_csv),
        (reference.districts_geojson, layout.districts_geojson),
    ]
    if needs_dictionary:
        pairs += [(reference.streets, layout.streets), (reference.pois, layout.pois)]
    # Option 01: zwei Quellen, die nur manche Städte veröffentlichen (votemanager)
    for source, target in (
        (reference.streets_directory, layout.streets_directory),
        (reference.district_names_csv, layout.district_names_csv),
    ):
        if source is not None and target is not None and source.is_file():
            _copy_input(layout, source, target, report, force=force)
    if layout.context_root is not None:
        # Option 03: dieselbe Mechanik für die Fremddaten; der Netzschritt context_data holt sie frisch.
        pairs += [(layout.context_source(name), layout.external / name) for name in context_files]
    for source, target in pairs:
        _copy_input(layout, source, target, report, force=force)
    # Option 02: die zwei Eingaben des Crosswalks, wenn der Schnappschuss sie mitbringt
    for source, target in (
        (reference.district_shapes_geojson, layout.district_shapes_geojson),
        (reference.district_results_csv, layout.district_results_csv),
    ):
        if source.is_file():
            _copy_input(layout, source, target, report, force=force)

    if seed_corpus:  # Option 07: ein Profil mit laufender Periode füllt keine Stores
        fresh = force or not (layout.papers.exists() and layout.texts.exists())
        if reference.papers.is_file() and reference.texts.is_file():
            if fresh:
                report.papers, report.texts = seed_stores_from_native(layout, reference)
        elif not reference.corpus_legacy.is_file():
            report.missing.append(reference.corpus_legacy.name)
        elif fresh:
            items = json.loads(reference.corpus_legacy.read_text(encoding="utf-8"))
            report.papers, report.texts = seed_stores_from_legacy(layout, items)
    logger.success(f"Bootstrap aus {layout.reference_root}: {report.summary()}")
    return report
