"""Invarianten der Modellnaht (F5) für alle Eingaben: Stapellauf, Fortsetzen, Vektoren im Cache."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from georep.ml.batch import run_batch
from georep.ml.cache import CacheKey, ModelCache, decode_vectors, encode_vector
from tests.fakes import fake_vector

KEY = CacheKey("fake-embed:latest", "e" * 64, "p-1")
keys = st.lists(st.sampled_from([f"{i:064x}" for i in range(12)]), max_size=30)


@given(
    keys=keys,
    batch_size=st.integers(1, 5),
    limits=st.lists(st.integers(0, 6), min_size=1, max_size=4),
)
def test_runs_with_limits_compute_every_distinct_input_exactly_once(
    keys: list[str], batch_size: int, limits: list[int]
) -> None:
    """Beliebig viele Läufe mit beliebigen Grenzen, dann einer ohne: jede Eingabe genau einmal."""
    computed: list[str] = []

    def compute(indices: Sequence[int]) -> list[bytes]:
        computed.extend(keys[i] for i in indices)
        return [keys[i].encode() for i in indices]

    with tempfile.TemporaryDirectory() as tmp, ModelCache(Path(tmp), KEY.model) as cache:
        for limit in [*limits, 0]:
            report = run_batch(keys, compute, cache, KEY, batch_size=batch_size, limit=limit)
            assert report.total == len(set(keys))
            assert report.computed <= (limit or report.total)
        assert report.left == 0
        assert sorted(computed) == sorted(set(keys))
        assert cache.get_many(KEY, sorted(set(keys))) == {k: k.encode() for k in set(keys)}


@given(
    rows=st.lists(
        st.lists(
            st.floats(width=32, allow_nan=False, allow_infinity=False), min_size=3, max_size=3
        ),
        max_size=6,
    )
)
def test_vectors_survive_the_cache_bit_for_bit(rows: list[list[float]]) -> None:
    matrix = np.asarray(rows, dtype=np.float32).reshape(len(rows), 3)
    back = decode_vectors([encode_vector(row) for row in matrix], 3)
    assert back.tobytes() == matrix.tobytes()


@given(text=st.text(max_size=40), dimension=st.integers(1, 40))
def test_fake_vectors_are_unit_length_and_stable(text: str, dimension: int) -> None:
    vector = fake_vector(text, dimension)
    assert len(vector) == dimension and fake_vector(text, dimension) == vector
    assert abs(sum(v * v for v in vector) - 1.0) < 1e-9
