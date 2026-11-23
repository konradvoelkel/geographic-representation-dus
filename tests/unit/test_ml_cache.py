"""Der inhaltsadressierte Modellcache (F5): Schlüssel, Atomarität, Fortsetzen nach Abbruch."""

from __future__ import annotations

import multiprocessing
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from georep.errors import SchemaError
from georep.ml.cache import (
    CacheKey,
    ModelCache,
    cache_filename,
    cache_stats,
    decode_vectors,
    encode_vector,
    input_sha256,
    with_busy_retry,
)

KEY = CacheKey(model="fake-embed:latest", digest="e" * 64, prompt="dokument-1")


def test_input_sha256_is_the_hex_digest_of_the_utf8_text() -> None:
    assert input_sha256("Grünfläche") == input_sha256("Grünfläche")
    assert len(input_sha256("")) == 64 and input_sha256("a") != input_sha256("A")


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("nomic-embed-text-v2-moe", "nomic-embed-text-v2-moe_latest.sqlite"),
        ("qwen3.6:27b", "qwen3.6_27b.sqlite"),
        ("hf.co/a/b:Q4", "hf.co_a_b_Q4.sqlite"),
    ],
)
def test_cache_filename_is_one_safe_file_per_model(model: str, expected: str) -> None:
    assert cache_filename(model) == expected


def test_put_and_get_round_trip_under_the_full_key(tmp_path: Path) -> None:
    with ModelCache(tmp_path / "ml", KEY.model) as cache:
        assert cache.put_many(KEY, [("a" * 64, b"eins"), ("b" * 64, b"zwei")]) == 2
        assert cache.known(KEY) == {"a" * 64, "b" * 64}
        assert cache.get_many(KEY, ["b" * 64, "c" * 64]) == {"b" * 64: b"zwei"}
        # Ein anderer Digest (neu gezogenes Modell) oder eine andere Prompt-Version sehen nichts.
        assert cache.known(CacheKey(KEY.model, "f" * 64, KEY.prompt)) == set()
        assert cache.known(CacheKey(KEY.model, KEY.digest, "dokument-2")) == set()


def test_a_value_can_be_marked_as_cut(tmp_path: Path) -> None:
    with ModelCache(tmp_path, KEY.model) as cache:
        cache.put_many(KEY, [("a" * 64, b"ganz"), ("b" * 64, b"halb")], truncated=["b" * 64])
        assert cache.truncated(KEY, ["a" * 64, "b" * 64, "c" * 64]) == {"b" * 64}
        assert cache.get_many(KEY, ["b" * 64]) == {"b" * 64: b"halb"}


def test_get_many_reads_more_keys_than_sqlite_takes_parameters(tmp_path: Path) -> None:
    shas = [f"{i:064x}" for i in range(2500)]
    with ModelCache(tmp_path, KEY.model) as cache:
        cache.put_many(KEY, [(sha, sha.encode()) for sha in shas])
        found = cache.get_many(KEY, shas)
    assert len(found) == 2500 and found[shas[-1]] == shas[-1].encode()


def test_entries_survive_closing_and_reopening(tmp_path: Path) -> None:
    with ModelCache(tmp_path, KEY.model) as cache:
        cache.put_many(KEY, [("a" * 64, b"eins")])
    with ModelCache(tmp_path, KEY.model) as again:
        assert again.get_many(KEY, ["a" * 64]) == {"a" * 64: b"eins"}


def test_a_failing_batch_leaves_nothing_behind(tmp_path: Path) -> None:
    with ModelCache(tmp_path, KEY.model) as cache:
        cache.put_many(KEY, [("a" * 64, b"eins")])
        broken: list[tuple[str, bytes]] = [("b" * 64, b"zwei"), ("c" * 64, object())]  # type: ignore[list-item]
        with pytest.raises(sqlite3.Error):
            cache.put_many(KEY, broken)
        assert cache.known(KEY) == {"a" * 64}


def test_a_file_of_another_model_is_refused(tmp_path: Path) -> None:
    with ModelCache(tmp_path, "a/b:c") as cache:
        cache.put_many(CacheKey("a/b:c", "d" * 64, "p"), [("a" * 64, b"x")])
    with pytest.raises(SchemaError, match=r"a/b:c"), ModelCache(tmp_path, "a_b:c") as other:
        other.known(CacheKey("a_b:c", "d" * 64, "p"))


def test_stats_count_entries_and_bytes_per_digest_and_prompt(tmp_path: Path) -> None:
    other = CacheKey(KEY.model, KEY.digest, "dokument-2")
    with ModelCache(tmp_path, KEY.model) as cache:
        cache.put_many(KEY, [("a" * 64, b"1234"), ("b" * 64, b"12")])
        cache.put_many(other, [("a" * 64, b"1")])
    with ModelCache(tmp_path, "fake-chat") as chat:
        chat.put_many(CacheKey("fake-chat:latest", "c" * 64, "k-1"), [("a" * 64, b"abc")])
    rows = [(s.model, s.prompt, s.entries, s.bytes) for s in cache_stats(tmp_path)]
    assert rows == [
        ("fake-chat:latest", "k-1", 1, 3),
        ("fake-embed:latest", "dokument-1", 2, 6),
        ("fake-embed:latest", "dokument-2", 1, 1),
    ]
    assert cache_stats(tmp_path / "fehlt") == []


def test_a_cache_writes_nothing_until_used(tmp_path: Path) -> None:
    ModelCache(tmp_path / "ml", KEY.model).close()
    assert not (tmp_path / "ml").exists()


def test_vectors_round_trip_as_little_endian_float32() -> None:
    rows = np.asarray([[0.5, -1.25, 3.0], [0.0, 1e-8, -2.5]], dtype=np.float32)
    blobs = [encode_vector(row) for row in rows]
    assert all(len(blob) == 12 for blob in blobs)
    back = decode_vectors(blobs, 3)
    assert back.dtype == np.float32 and np.array_equal(back, rows)
    assert decode_vectors([], 3).shape == (0, 3)


def test_a_busy_database_is_tried_again() -> None:
    """Befund 6 des Reviews: ``PRAGMA journal_mode=WAL`` antwortet ``SQLITE_BUSY`` ohne zu warten."""
    calls: list[int] = []
    pauses: list[float] = []

    def busy_twice() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise sqlite3.OperationalError("database is locked")
        return "wal"

    assert with_busy_retry(busy_twice, sleep=pauses.append) == "wal"
    assert len(calls) == 3 and len(pauses) == 2 and pauses[0] < pauses[1]


def test_another_database_error_is_not_tried_again() -> None:
    def broken() -> str:
        raise sqlite3.OperationalError("no such table: meta")

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        with_busy_retry(broken, sleep=lambda s: None)


BATCHES = 20


def _writer(root: str, worker: int, start: Any, results: Any) -> None:
    """Ein Prozess, der eine neue Cache-Datei öffnet und Stapel schreibt (Probe 2 des Reviews).

    ``start`` ist eine Schranke für alle Prozesse und den Test: erst wenn jeder bereit ist, öffnen
    alle zugleich. Ohne sie kämen die Prozesse nacheinander an und stießen nie zusammen.
    """
    start.wait()
    try:
        with ModelCache(Path(root), KEY.model) as cache:
            for batch in range(BATCHES):
                rows = [(f"{worker:04d}{batch:04d}{i:056d}", b"\0" * 3072) for i in range(32)]
                cache.put_many(KEY, rows)
                cache.known(KEY)
        results.put("ok")
    except sqlite3.Error as error:
        results.put(f"{worker}: {error!r}")


def test_processes_opening_a_new_cache_file_together_all_get_in(tmp_path: Path) -> None:
    context = multiprocessing.get_context("forkserver")
    workers_per_round = 6
    for round_ in range(4):
        root = tmp_path / f"runde-{round_}"
        start = context.Barrier(workers_per_round + 1)
        results = context.Queue()
        workers = [
            context.Process(target=_writer, args=(str(root), w, start, results))
            for w in range(workers_per_round)
        ]
        for worker in workers:
            worker.start()
        start.wait(timeout=120)
        answers = [results.get(timeout=120) for _ in workers]
        for worker in workers:
            worker.join(timeout=120)
        assert answers == ["ok"] * workers_per_round, answers
        with ModelCache(root, KEY.model) as cache:
            assert len(cache.known(KEY)) == workers_per_round * BATCHES * 32
