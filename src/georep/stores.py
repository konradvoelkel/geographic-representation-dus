"""Speicher für Metadaten und Texte, beide wiederaufnehmbar und atomar.

``PaperStore``: ``raw/papers.jsonl``, eine Zeile je Paper, sortiert nach ID; neuere ``modified``
gewinnt. ``TextStore``: ``cache/text/<dateiname>.txt`` plus ``index.json`` mit Extraktor,
PDF-Hash und Herkunft je Text, damit ein Text nur neu entsteht, wenn PDF oder Extraktor sich
geändert haben (DEVELOPMENT_PLAN.md § 3.3).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from georep.io import atomic_path, write_json, write_text
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


class TextStore:
    """Texte unter ``<dir>/<name>.txt``; der Index kennt je Name Extraktor, PDF-Hash, Herkunft."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.index_path = directory / "index.json"
        self._index: dict[str, TextMeta] | None = None

    @property
    def index(self) -> dict[str, TextMeta]:
        if self._index is None:
            if self.index_path.exists():
                raw = json.loads(self.index_path.read_text(encoding="utf-8"))
                self._index = {name: TextMeta.model_validate(meta) for name, meta in raw.items()}
            else:
                self._index = {}
        return self._index

    def __len__(self) -> int:
        return len(self.index)

    def __contains__(self, name: str) -> bool:
        return name in self.index

    def meta(self, name: str) -> TextMeta | None:
        return self.index.get(name)

    def path(self, name: str) -> Path:
        return self.directory / f"{name}.txt"

    def get(self, name: str) -> str | None:
        if name not in self.index:
            return None
        return self.path(name).read_text(encoding="utf-8")

    def put(self, name: str, text: str, meta: TextMeta) -> None:
        write_text(self.path(name), text)
        self.index[name] = meta.model_copy(update={"chars": len(text)})

    def is_current(self, name: str, *, pdf_sha256: str | None, extractor: str) -> bool:
        """Text braucht keine Neuberechnung, wenn Extraktor und PDF-Hash übereinstimmen."""
        meta = self.meta(name)
        return meta is not None and meta.extractor == extractor and meta.pdf_sha256 == pdf_sha256

    def save_index(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        write_json(
            self.index_path,
            {name: meta.model_dump(mode="json") for name, meta in sorted(self.index.items())},
            indent=None,
        )
