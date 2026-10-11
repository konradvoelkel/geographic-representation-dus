"""Den eingefrorenen Datensatz der Arbeit nach ``data_root`` übernehmen.

Damit läuft die Offline-Kette ohne Netz: Rohdaten und Wahlergebnis werden kopiert, der Korpus
mit den extrahierten Texten einmalig nach Parquet gewandelt. Vorhandene Dateien bleiben stehen,
``force=True`` überschreibt. Der Lauf nennt, wie viele Dateien er kopiert, übersprungen und
nicht gefunden hat.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl
from loguru import logger

from georep.io import atomic_path
from georep.layout import Layout

CORPUS_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen von papers.parquet ändern


@dataclass
class BootstrapReport:
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    corpus_rows: int | None = None  # None = Parquet nicht neu geschrieben

    def summary(self) -> str:
        corpus = (
            f"Korpus mit {self.corpus_rows} Dokumenten nach Parquet"
            if self.corpus_rows is not None
            else "Korpus-Parquet vorhanden"
        )
        return (
            f"{len(self.copied)} Dateien kopiert, {len(self.skipped)} übersprungen, "
            f"{len(self.missing)} in der Referenz nicht gefunden; {corpus}"
        )


def legacy_corpus_to_parquet(json_path: Path, parquet_path: Path) -> int:
    """``paper_with_text.json`` des Altcodes nach ``papers.parquet``; liefert die Zeilenzahl."""
    frame = (
        pl.read_json(json_path)
        .select(
            pl.col("id").cast(pl.String),
            pl.col("name").cast(pl.String),
            pl.col("reference").cast(pl.String),
            pl.col("date").cast(pl.String).str.to_date("%Y-%m-%d", strict=False),
            pl.col("paperType").cast(pl.String).alias("paper_type"),
            pl.col("mainFile").cast(pl.String).alias("main_file"),
            pl.col("download_url").cast(pl.String),
            pl.col("paper_text").cast(pl.String).fill_null("").alias("text"),
        )
        .sort("id")
    )
    with atomic_path(parquet_path) as tmp:
        frame.write_parquet(
            tmp,
            compression="zstd",
            metadata={"georep.schema_version": str(CORPUS_SCHEMA_VERSION)},
        )
    return frame.height


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

    if reference.corpus_legacy.is_file() and (force or not layout.corpus.exists()):
        report.corpus_rows = legacy_corpus_to_parquet(
            reference.corpus_legacy, layout.guard_writable(layout.corpus)
        )
    logger.success(f"Bootstrap aus {layout.reference_root}: {report.summary()}")
    return report
