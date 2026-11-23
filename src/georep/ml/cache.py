"""Inhaltsadressierter Cache der Modellergebnisse unter ``cache_root/ml/``: eine SQLite-Datei je Modell.

Der Schlüssel eines Eintrags ist (Digest des Modells, Prompt-Version, SHA-256 der Eingabe). Die
Eingabe ist, was das Modell sieht: bei einer Einbettung der Text samt Präfix, bei einem Generator
System und Prompt (``georep.ml.batch``). Ein Eintrag gilt also genau für dieses Modell in diesem
Stand und diese Eingabe; wer das Modell neu zieht, bekommt einen neuen Digest und rechnet neu, die
alten Einträge bleiben liegen. Der Cache ist von allen Profilen geteilt wie ``http.sqlite``: derselbe
Text gibt mit demselben Modell dasselbe Ergebnis, gleich aus welcher Periode er kommt.

SQLite statt Parquet-Scherben (docs/decisions.md, „Modelle lokal über ollama"): ein Stapel ist eine
Transaktion, also atomar, und was vor einem Abbruch festgeschrieben war, bleibt; Nachschlagen über
den Primärschlüssel braucht keinen Index im Speicher, und zwei Läufe dürfen dieselbe Datei lesen,
während einer schreibt (WAL). Parquet bleibt das Format der Ausgaben und Pakete: ein Schritt liest
aus dem Cache und schreibt seine Tabelle.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

import deal
import numpy as np

from georep.errors import SchemaError
from georep.ml.base import Vectors, full_name

CACHE_SCHEMA_VERSION = 1
CHUNK = 500  # Schlüssel je SELECT; SQLite nimmt höchstens 32 766 Parameter, ältere 999
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
# Mit Rowid, nicht ``WITHOUT ROWID``: so liegt der Primärschlüssel in einem eigenen Index ohne die
# Werte, und ``known`` liest nur ihn. Gemessen am 2026-11-23 mit 50 000 Einbettungen zu 3 KB: alle
# Schlüssel 50 ms statt 708 ms, alle Werte 1,6 s statt 4,6 s (docs/decisions.md, Modellnaht).
_TABLES = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entries (
    digest TEXT NOT NULL,
    prompt TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    value BLOB NOT NULL,
    written TEXT NOT NULL,
    PRIMARY KEY (digest, prompt, input_sha256)
);
"""


@dataclass(frozen=True)
class CacheKey:
    """Modell (voller Name), sein Digest und die Prompt-Version: alles am Schlüssel außer der Eingabe."""

    model: str
    digest: str
    prompt: str


@dataclass(frozen=True)
class CacheStat:
    model: str
    digest: str
    prompt: str
    entries: int
    bytes: int


def input_sha256(text: str) -> str:
    """Der Teil des Schlüssels, der die Eingabe bezeichnet."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@deal.pure
@deal.ensure(lambda model, result: _UNSAFE.search(result) is None)
@deal.ensure(lambda model, result: result.endswith(".sqlite"))
def cache_filename(model: str) -> str:
    """Eine Datei je Modell, ihr Name ohne Schrägstrich und Doppelpunkt: ``qwen3.6:27b`` -> ``qwen3.6_27b.sqlite``."""
    return _UNSAFE.sub("_", full_name(model)) + ".sqlite"


def encode_vector(vector: Vectors) -> bytes:
    """Ein Vektor als float32 in fester Byte-Reihenfolge (little endian), wie er im Cache liegt."""
    return np.asarray(vector, dtype="<f4").tobytes()


@deal.pre(lambda blobs, dimension: dimension > 0)
@deal.ensure(lambda blobs, dimension, result: result.shape == (len(blobs), dimension))
def decode_vectors(blobs: Sequence[bytes], dimension: int) -> Vectors:
    """Die Gegenrichtung von ``encode_vector`` für viele Einträge auf einmal: eine Zeile je Blob."""
    flat = np.frombuffer(b"".join(blobs), dtype="<f4").astype(np.float32)
    return flat.reshape(len(blobs), dimension)


class ModelCache:
    """Die Datei eines Modells. Öffnet erst beim ersten Zugriff; ein Stapel ist eine Transaktion.

    ``known`` liefert die Eingaben, die zu einem Schlüssel schon im Cache liegen, ``get_many``
    ihre Werte, ``put_many`` schreibt einen Stapel ganz oder gar nicht. Eine Datei, deren
    ``meta`` ein anderes Modell nennt (zwei Namen mit demselben Dateinamen), ist ein
    ``SchemaError``, kein stilles Mischen.
    """

    def __init__(self, root: Path, model: str) -> None:
        self.root = root
        self.model = full_name(model)
        self.path = root / cache_filename(model)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> ModelCache:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = self._open()
        return self._conn

    def _open(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        with conn:
            conn.executescript(_TABLES)
            conn.execute(
                "INSERT OR IGNORE INTO meta VALUES ('model', ?), ('schema_version', ?)",
                (self.model, str(CACHE_SCHEMA_VERSION)),
            )
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        if meta["model"] != self.model or meta["schema_version"] != str(CACHE_SCHEMA_VERSION):
            conn.close()
            raise SchemaError(
                f"{self.path} gehört zu {meta['model']} (Schema {meta['schema_version']}), "
                f"nicht zu {self.model} (Schema {CACHE_SCHEMA_VERSION})"
            )
        return conn

    def known(self, key: CacheKey) -> set[str]:
        rows = self.connection.execute(
            "SELECT input_sha256 FROM entries WHERE digest = ? AND prompt = ?",
            (key.digest, key.prompt),
        )
        return {sha for (sha,) in rows}

    def get_many(self, key: CacheKey, shas: Sequence[str]) -> dict[str, bytes]:
        found: dict[str, bytes] = {}
        for start in range(0, len(shas), CHUNK):
            chunk = list(shas[start : start + CHUNK])
            marks = ",".join("?" * len(chunk))
            rows = self.connection.execute(
                "SELECT input_sha256, value FROM entries "
                f"WHERE digest = ? AND prompt = ? AND input_sha256 IN ({marks})",
                (key.digest, key.prompt, *chunk),
            )
            found.update(rows)
        return found

    def put_many(self, key: CacheKey, items: Iterable[tuple[str, bytes]]) -> int:
        """Schreibt einen Stapel in einer Transaktion; scheitert ein Eintrag, bleibt keiner."""
        written = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        rows = [(key.digest, key.prompt, sha, value, written) for sha, value in items]
        with self.connection:
            self.connection.executemany(
                "INSERT OR REPLACE INTO entries VALUES (?, ?, ?, ?, ?)", rows
            )
        return len(rows)

    def stats(self) -> list[CacheStat]:
        rows = self.connection.execute(
            "SELECT digest, prompt, COUNT(*), SUM(LENGTH(value)) FROM entries "
            "GROUP BY digest, prompt ORDER BY digest, prompt"
        )
        return [CacheStat(self.model, d, p, n, size) for d, p, n, size in rows]


def cache_stats(root: Path) -> list[CacheStat]:
    """Einträge und Bytes je Modell, Digest und Prompt-Version über alle Dateien unter ``root``."""
    found: list[CacheStat] = []
    for path in sorted(root.glob("*.sqlite")) if root.is_dir() else []:
        conn = sqlite3.connect(path, timeout=30.0)
        try:
            (model,) = conn.execute("SELECT value FROM meta WHERE key = 'model'").fetchone()
        finally:
            conn.close()
        with ModelCache(root, model) as cache:
            found.extend(cache.stats())
    return sorted(found, key=lambda s: (s.model, s.digest, s.prompt))
