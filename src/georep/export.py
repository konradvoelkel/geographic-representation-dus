"""Parquet-Ergebnisse als CSV für Menschen und das Notebook, im Format des Altcodes.

Dieselben Regeln (Listen-Trenner, Spaltentrenner) nutzt der Schritt ``report`` für die
Download-Dateien, darum stehen Plan und Schreiber hier und nicht in der CLI.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import polars as pl

from georep.io import atomic_path
from georep.layout import Layout
from georep.report.tables import csv_plan


def _joined(frame: pl.DataFrame, joins: Mapping[str, str]) -> pl.DataFrame:
    # Der Cast auf Text ist für Zahlenlisten nötig (Option 05: stadtbezirke ist List(Int64));
    # bei Textlisten ändert er nichts, die Ausgabe der vorhandenen Tabellen bleibt gleich.
    return frame.with_columns(
        [
            pl.col(c).cast(pl.List(pl.String)).list.join(sep)
            for c, sep in joins.items()
            if c in frame.columns
        ]
    )


def write_csv(parquet: Path, target: Path, joins: Mapping[str, str], separator: str) -> None:
    """Eine Parquet-Datei als CSV, atomar; Listen werden mit ihrem Trenner zu Text."""
    with atomic_path(target) as tmp:
        _joined(pl.read_parquet(parquet), joins).write_csv(tmp, separator=separator)


def export_csv(layout: Layout) -> list[Path]:
    """Schreibt neben jede vorhandene Parquet-Datei unter processed/ eine CSV; liefert die Pfade."""
    written: list[Path] = []
    for parquet, joins, separator in csv_plan(layout):
        if not parquet.exists():
            continue
        target = layout.guard_writable(parquet.with_suffix(".csv"))
        write_csv(parquet, target, joins, separator)
        written.append(target)
    return written
