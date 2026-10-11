"""Speicher für Metadaten und Texte, beide wiederaufnehmbar und atomar.

``PaperStore``: ``raw/papers.jsonl``, eine Zeile je Paper, sortiert nach ID; neuere ``modified``
gewinnt. ``TextStore``: ``cache/text/texts.parquet`` mit Text, Extraktor, PDF-Hash und Herkunft je
Dateiname, damit ein Text nur neu entsteht, wenn PDF oder Extraktor sich geändert haben
(docs/architecture.md, „Datenhaltung").
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import deal
import polars as pl
from pydantic import BaseModel, ConfigDict

from georep.io import atomic_path, write_parquet
from georep.records import PaperRecord


@dataclass(frozen=True)
class UpsertReport:
    added: int
    updated: int
    unchanged: int
    total: int

    def summary(self) -> str:
        return f"{self.added} neu, {self.updated} aktualisiert, {self.unchanged} unverändert, {self.total} gesamt"


class PaperStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @deal.post(
        lambda result: all(key == record.id for key, record in result.items()),
        message="der Schlüssel ist die Paper-ID",
    )
    def load(self) -> dict[str, PaperRecord]:
        if not self.path.exists():
            return {}
        records: dict[str, PaperRecord] = {}
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = PaperRecord.model_validate_json(line)
                    records[record.id] = record
        return records

    def save(self, records: Iterable[PaperRecord]) -> int:
        ordered = sorted(records, key=lambda r: r.id)
        with atomic_path(self.path) as tmp, tmp.open("w", encoding="utf-8") as f:
            for record in ordered:
                f.write(record.model_dump_json())
                f.write("\n")
        return len(ordered)

    @deal.post(lambda result: result.added + result.updated <= result.total)
    def upsert(self, incoming: Iterable[PaperRecord]) -> UpsertReport:
        existing = self.load()
        added = updated = unchanged = 0
        for record in incoming:
            current = existing.get(record.id)
            if current is None:
                existing[record.id] = record
                added += 1
            elif current == record:
                unchanged += 1
            elif (
                record.modified is None
                or current.modified is None
                or record.modified >= current.modified
            ):
                existing[record.id] = record
                updated += 1
            else:
                unchanged += 1
        self.save(existing.values())
        return UpsertReport(added, updated, unchanged, len(existing))


class TextMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    extractor: str
    pdf_sha256: str | None = None
    source: str = "pdf"
    chars: int = 0


TEXT_SCHEMA = {
    "name": pl.String,
    "text": pl.String,
    "extractor": pl.String,
    "pdf_sha256": pl.String,
    "source": pl.String,
    "chars": pl.Int64,
}
TEXT_SCHEMA_VERSION = 1


class TextStore:
    """Alle Texte in einer Parquet-Datei mit Metadaten je Dateiname.

    19108 einzelne Dateien mit je zwei fsync kosteten am 2026-10-11 zwei Minuten; eine Datei,
    einmal atomar geschrieben, kostet unter einer Sekunde. Änderungen sammeln sich im Speicher,
    ``save`` schreibt.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._rows: dict[str, dict[str, object]] | None = None

    @property
    def rows(self) -> dict[str, dict[str, object]]:
        if self._rows is None:
            if self.path.exists():
                frame = pl.read_parquet(self.path)
                self._rows = {str(r["name"]): r for r in frame.iter_rows(named=True)}
            else:
                self._rows = {}
        return self._rows

    def __len__(self) -> int:
        return len(self.rows)

    def __contains__(self, name: str) -> bool:
        return name in self.rows

    def meta(self, name: str) -> TextMeta | None:
        row = self.rows.get(name)
        if row is None:
            return None
        return TextMeta(
            extractor=str(row["extractor"]),
            pdf_sha256=str(row["pdf_sha256"]) if row["pdf_sha256"] is not None else None,
            source=str(row["source"]),
            chars=int(row["chars"]),  # type: ignore[call-overload]
        )

    def get(self, name: str) -> str | None:
        row = self.rows.get(name)
        return str(row["text"]) if row is not None else None

    @deal.pre(
        lambda self, name, text, meta: name != "", message="ein Text braucht einen Dateinamen"
    )
    def put(self, name: str, text: str, meta: TextMeta) -> None:
        self.rows[name] = {
            "name": name,
            "text": text,
            "extractor": meta.extractor,
            "pdf_sha256": meta.pdf_sha256,
            "source": meta.source,
            "chars": len(text),
        }

    def is_current(self, name: str, *, pdf_sha256: str | None, extractor: str) -> bool:
        """Text braucht keine Neuberechnung, wenn Extraktor und PDF-Hash übereinstimmen."""
        meta = self.meta(name)
        return meta is not None and meta.extractor == extractor and meta.pdf_sha256 == pdf_sha256

    def save(self) -> None:
        frame = pl.DataFrame([self.rows[name] for name in sorted(self.rows)], schema=TEXT_SCHEMA)
        write_parquet(frame, self.path, schema_version=TEXT_SCHEMA_VERSION)
