"""Parquet-Ergebnisse als CSV für Menschen und das Notebook, im Format des Altcodes."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from georep.io import atomic_path
from georep.layout import Layout


def _joined(frame: pl.DataFrame, joins: dict[str, str]) -> pl.DataFrame:
    return frame.with_columns(
        [pl.col(c).list.join(sep) for c, sep in joins.items() if c in frame.columns]
    )


def export_csv(layout: Layout) -> list[Path]:
    """Schreibt neben jede vorhandene Parquet-Datei unter processed/ eine CSV; liefert die Pfade."""
    plan: list[tuple[Path, dict[str, str], str]] = [
        (layout.voters, {}, ","),
        (layout.streets_by_district, {"suchbegriffe": "; "}, ","),
        (layout.pois_table, {}, ","),
        (layout.pois_by_district, {"suchbegriffe": "; "}, ","),
        (layout.dictionary, {"suchbegriffe": ", "}, ";"),
        (layout.index, {"paper_ids": ";"}, ","),
        (layout.results, {"suchbegriffe": "; ", "paper_ids": ";"}, ","),
    ]
    written: list[Path] = []
    for parquet, joins, separator in plan:
        if not parquet.exists():
            continue
        target = layout.guard_writable(parquet.with_suffix(".csv"))
        with atomic_path(target) as tmp:
            _joined(pl.read_parquet(parquet), joins).write_csv(tmp, separator=separator)
        written.append(target)
    return written
