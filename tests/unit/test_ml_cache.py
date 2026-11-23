"""Der inhaltsadressierte Modellcache (F5): Schlüssel, Atomarität, Fortsetzen nach Abbruch."""

from __future__ import annotations

import sqlite3
from pathlib import Path

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
