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
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

import deal
import numpy as np

from georep.errors import SchemaError
from georep.ml.base import Vectors, full_name

CACHE_SCHEMA_VERSION = 3  # 2: Spalte ``truncated``; 3: Tabelle ``failures`` (Review F5, N1)
REJECTED = "abgewiesen"  # das Modell wies die Eingabe ab; erledigt, bis jemand erneut fragt
FAILED = (
    "gescheitert"  # ein Fehlschlag ohne Abweisung (Zeit, 5xx); offen, beim nächsten Lauf zuletzt
)
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
    truncated INTEGER NOT NULL DEFAULT 0,
    written TEXT NOT NULL,
    PRIMARY KEY (digest, prompt, input_sha256)
);
CREATE TABLE IF NOT EXISTS failures (
    digest TEXT NOT NULL,
    prompt TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    kind TEXT NOT NULL,
    reason TEXT NOT NULL,
    written TEXT NOT NULL,
    PRIMARY KEY (digest, prompt, input_sha256)
);
"""


_BUSY = ("SQLITE_BUSY", "SQLITE_LOCKED")


def with_busy_retry[T](
    action: Callable[[], T], *, attempts: int = 12, sleep: Callable[[float], None] = time.sleep
) -> T:
    """``action`` noch einmal, solange SQLite „besetzt" meldet; jeder andere Fehler sofort.

    Der Wechsel einer neuen Datei auf WAL braucht die Datei für sich, und SQLite antwortet darauf
    ``SQLITE_BUSY``, ohne den eigenen Wartemechanismus zu benutzen: öffnen mehrere Läufe dieselbe
    neue Datei zugleich, scheitern die übrigen (Review 2026-11-23, Befund 6; Probe 2 und 3).
    Gewartet wird 0,05 s, dann jeweils doppelt so lange, höchstens 2 s, zusammen rund 15 s.
    """
    for attempt in range(attempts):
        try:
            return action()
        except sqlite3.OperationalError as error:
            busy = getattr(error, "sqlite_errorname", "") in _BUSY or "locked" in str(error)
            if not busy or attempt + 1 == attempts:
                raise
            sleep(min(0.05 * 2**attempt, 2.0))
    raise AssertionError("unerreichbar")  # pragma: no cover


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
    path: Path  # die Datei, aus der die Zahlen stammen; ihr Name muss nicht zum Modell passen


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

        def prepare() -> None:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            with conn:
                conn.executescript(_TABLES)
                conn.execute(
                    "INSERT OR IGNORE INTO meta VALUES ('model', ?), ('schema_version', ?)",
                    (self.model, str(CACHE_SCHEMA_VERSION)),
                )

        try:
            with_busy_retry(prepare)
        except sqlite3.Error:
            conn.close()
            raise
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

    def put_many(
        self, key: CacheKey, items: Iterable[tuple[str, bytes]], *, truncated: Iterable[str] = ()
    ) -> int:
        """Schreibt einen Stapel in einer Transaktion; scheitert ein Eintrag, bleibt keiner.

        ``truncated`` nennt die Eingaben, deren Wert unvollständig ist (eine Antwort an
        ``num_predict``): sie liegen im Cache, damit ein deterministisches Modell sie nicht bei
        jedem Lauf neu rechnet, und ``truncated`` liefert sie markiert zurück.
        """
        cut = set(truncated)
        written = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        rows = [
            (key.digest, key.prompt, sha, value, int(sha in cut), written) for sha, value in items
        ]
        with self.connection:
            self.connection.executemany(
                "INSERT OR REPLACE INTO entries "
                "(digest, prompt, input_sha256, value, truncated, written) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            # Ein Wert erledigt jeden früheren Fehlschlag derselben Eingabe, in derselben Transaktion.
            self.connection.executemany(
                "DELETE FROM failures WHERE digest = ? AND prompt = ? AND input_sha256 = ?",
                [(key.digest, key.prompt, row[2]) for row in rows],
            )
        return len(rows)

    def put_failure(self, key: CacheKey, sha: str, kind: str, reason: str) -> None:
        """Merkt sich, dass eine Eingabe scheiterte (``REJECTED`` oder ``FAILED``), mit Grund."""
        written = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO failures VALUES (?, ?, ?, ?, ?, ?)",
                (key.digest, key.prompt, sha, kind, reason, written),
            )

    def failures(self, key: CacheKey) -> dict[str, tuple[str, str]]:
        """Je gescheiterter Eingabe unter ``key``: (Art, Grund)."""
        rows = self.connection.execute(
            "SELECT input_sha256, kind, reason FROM failures WHERE digest = ? AND prompt = ?",
            (key.digest, key.prompt),
        )
        return {sha: (kind, reason) for sha, kind, reason in rows}

    def truncated(self, key: CacheKey, shas: Sequence[str]) -> set[str]:
        """Die Eingaben unter ``shas``, deren Wert als unvollständig markiert ist."""
        found: set[str] = set()
        for start in range(0, len(shas), CHUNK):
            chunk = list(shas[start : start + CHUNK])
            marks = ",".join("?" * len(chunk))
            rows = self.connection.execute(
                "SELECT input_sha256 FROM entries WHERE digest = ? AND prompt = ? "
                f"AND truncated = 1 AND input_sha256 IN ({marks})",
                (key.digest, key.prompt, *chunk),
            )
            found.update(sha for (sha,) in rows)
        return found

    def stats(self) -> list[CacheStat]:
        rows = self.connection.execute(
            "SELECT digest, prompt, COUNT(*), SUM(LENGTH(value)) FROM entries "
            "GROUP BY digest, prompt ORDER BY digest, prompt"
        )
        return [CacheStat(self.model, d, p, n, size, self.path) for d, p, n, size in rows]


def cache_stats(root: Path) -> list[CacheStat]:
    """Einträge und Bytes je Modell, Digest und Prompt-Version über alle Dateien unter ``root``.

    Nur lesend (``mode=ro``): ``georep ml status`` legt keine Tabelle an und schreibt keine Zeile,
    auch nicht in eine Datei, die gerade ein Lauf füllt. Eine Datei ohne ``meta`` oder ohne
    ``entries`` gehört nicht zum Modellcache und wird übersprungen (Review 2026-11-23, Befund 8).
    """
    found: list[CacheStat] = []
    for path in sorted(root.glob("*.sqlite")) if root.is_dir() else []:
        found.extend(_file_stats(path))
    return sorted(found, key=lambda s: (s.model, s.digest, s.prompt))


def _file_stats(path: Path) -> list[CacheStat]:
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=30.0)
    except sqlite3.Error:
        return []
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'model'").fetchone()
        if row is None:
            return []
        rows = conn.execute(
            "SELECT digest, prompt, COUNT(*), SUM(LENGTH(value)) FROM entries "
            "GROUP BY digest, prompt ORDER BY digest, prompt"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [CacheStat(row[0], d, p, n, size, path) for d, p, n, size in rows]
