"""PDF-Store: Dateien unter ``cache_root/pdf/<dateiname>``, Herkunft im Manifest.

Download seriell mit Pause (der Server ist langsam, nicht wir), Fehler je Datei isoliert, eine
Antwort ohne ``%PDF`` in den ersten 1024 Bytes zählt als Fehler und landet nicht auf der Platte,
Schreiben atomar. ``limit`` begrenzt die Zahl neuer Downloads je Lauf.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import requests

from georep.errors import CorruptPdfError
from georep.http import Transport
from georep.io import write_bytes
from georep.records import PaperRecord


@dataclass
class DownloadReport:
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.downloaded} geladen, {self.skipped} übersprungen, {self.failed} fehlgeschlagen"
        )


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PdfStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.manifest = directory / "manifest.jsonl"

    def ensure(self) -> None:
        """Verzeichnis und (leeres) Manifest anlegen: das Manifest ist die Eingabe des Textschritts."""
        self.directory.mkdir(parents=True, exist_ok=True)
        self.manifest.touch()

    def path(self, name: str) -> Path:
        return self.directory / name

    def has(self, name: str) -> bool:
        path = self.path(name)
        return path.is_file() and path.stat().st_size > 0

    def names(self) -> set[str]:
        if not self.directory.is_dir():
            return set()
        return {p.name for p in self.directory.glob("*.pdf") if p.stat().st_size > 0}

    def sha256(self, name: str) -> str:
        return sha256_of(self.path(name))

    def _record(self, name: str, url: str, content: bytes) -> None:
        entry = {
            "name": name,
            "url": url,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
            "fetched_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        }
        with self.manifest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def download(
        self,
        http: Transport,
        records: Iterable[PaperRecord],
        *,
        delay_s: float = 0.0,
        limit: int | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> DownloadReport:
        self.ensure()
        existing = self.names()
        report = DownloadReport()
        for record in records:
            if limit is not None and report.downloaded >= limit:
                break
            name, url = record.file_name, record.download_url
            if not name or not url or name in existing:
                report.skipped += 1
                continue
            try:
                response = http.get(url)
                response.raise_for_status()
                content = response.content
                if b"%PDF" not in content[:1024]:
                    raise CorruptPdfError("Antwort ist kein PDF")
                write_bytes(self.path(name), content)
            except (requests.RequestException, CorruptPdfError, OSError) as error:
                report.failed += 1
                report.errors.append((url, str(error)))
            else:
                existing.add(name)
                report.downloaded += 1
                self._record(name, url, content)
            if delay_s > 0:
                sleep(delay_s)
        return report
