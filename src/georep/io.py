"""Atomare Schreibvorgänge: Temporärdatei im Zielverzeichnis, fsync, ``os.replace``.

Ein Abbruch durch Exception, Signal oder Stromausfall hinterlässt entweder die alte Datei oder
die neue, nie eine halbe. Das ist Regel 2 in docs/architecture.md, „Sicherheit".
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import polars as pl


def _fsync_path(path: Path, *, directory: bool = False) -> None:
    flags = os.O_RDONLY | (os.O_DIRECTORY if directory else 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def atomic_path(target: Path) -> Iterator[Path]:
    """Liefert einen temporären Pfad neben ``target``; bei Erfolg ersetzt er ``target`` atomar.

    Für Schreiber, die selbst öffnen (``DataFrame.write_parquet``, ``to_csv``). Wirft der Block
    eine Exception oder legt die Datei nicht an, bleibt ``target`` unverändert und die
    Temporärdatei verschwindet.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        yield tmp
        if not tmp.exists():
            raise FileNotFoundError(f"Schreiber hat {tmp} nicht angelegt")
        _fsync_path(tmp)
        os.replace(tmp, target)
        _fsync_path(target.parent, directory=True)
    finally:
        tmp.unlink(missing_ok=True)


def write_bytes(target: Path, data: bytes) -> None:
    with atomic_path(target) as tmp:
        tmp.write_bytes(data)


def write_text(target: Path, text: str, *, encoding: str = "utf-8") -> None:
    with atomic_path(target) as tmp:
        tmp.write_text(text, encoding=encoding)


def write_json(target: Path, data: object, *, indent: int | None = 2) -> None:
    """JSON mit ``ensure_ascii=False``: Umlaute bleiben lesbar, wie im Altcode."""
    write_text(target, json.dumps(data, ensure_ascii=False, indent=indent))


def write_parquet(frame: pl.DataFrame, target: Path, *, schema_version: int) -> None:
    """Parquet mit zstd, atomar; ``schema_version`` steht in den Metadaten (Lehre bubatzblick:
    ein Cache muss sein eigenes Ausgabeschema kennen)."""
    with atomic_path(target) as tmp:
        frame.write_parquet(
            tmp, compression="zstd", metadata={"georep.schema_version": str(schema_version)}
        )
