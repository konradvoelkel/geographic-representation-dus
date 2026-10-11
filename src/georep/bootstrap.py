"""Den eingefrorenen Datensatz der Arbeit nach ``data_root`` übernehmen.

Damit läuft die Offline-Kette ohne Netz: Rohdaten, Wahlergebnis und der Korpus im Altformat
werden kopiert; der Schritt ``corpus`` der Pipeline wandelt ihn nach Parquet. Vorhandene Dateien
bleiben stehen, ``force=True`` überschreibt. Der Lauf nennt, wie viele Dateien er kopiert,
übersprungen und nicht gefunden hat.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field

from loguru import logger

from georep.io import atomic_path
from georep.layout import Layout


@dataclass
class BootstrapReport:
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{len(self.copied)} Dateien kopiert, {len(self.skipped)} übersprungen, "
            f"{len(self.missing)} in der Referenz nicht gefunden"
        )


def bootstrap(layout: Layout, *, force: bool = False) -> BootstrapReport:
    reference = layout.reference_view()
    layout.ensure_dirs()
    report = BootstrapReport()
    pairs = [
        (reference.results_csv, layout.results_csv),
        (reference.districts_geojson, layout.districts_geojson),
        (reference.paper_objects, layout.paper_objects),
        (reference.paper_urls, layout.paper_urls),
        (reference.streets, layout.streets),
        (reference.pois, layout.pois),
        (reference.corpus_legacy, layout.corpus_legacy),
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
    logger.success(f"Bootstrap aus {layout.reference_root}: {report.summary()}")
    return report
