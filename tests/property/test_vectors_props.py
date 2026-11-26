"""Vorhaben 18: Dokumentvektoren und Nachbartabelle als Eigenschaften über beliebige Vektoren.

Bauplan § 6: die Nachbartabelle hat ``k`` Zeilen je ID und nie die eigene Datei; ``rang`` ist
lückenlos, ``aehnlichkeit`` fallend. Dazu: die Nachbarn sind die ähnlichsten anderen Dateien,
Gleichstände nach ID, auch an der Grenze (gleiche Vektoren kommen vor: Formulare, Dubletten).
"""

from __future__ import annotations

import numpy as np
import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.search.vectors import document_vectors, max_per_unit, neighbor_table, normalise

# Vektoren aus wenigen Werten, damit Gleichstände häufig sind
VALUES = st.sampled_from([0.0, 1.0, -1.0, 0.5])


@st.composite
def units_and_vectors(draw: st.DrawFn) -> tuple[pl.DataFrame, np.ndarray, int]:
    count = draw(st.integers(1, 9))
    dimension = draw(st.integers(1, 4))
    rows = draw(
        st.lists(
            st.lists(VALUES, min_size=dimension, max_size=dimension),
            min_size=count,
            max_size=count,
        )
    )
    shared = draw(st.lists(st.integers(1, 3), min_size=count, max_size=count))  # IDs je Datei
    units = pl.DataFrame(
        {
            "id": [f"u{i:02d}a" for i in range(count)],
            "datei": [f"f{i}.pdf" for i in range(count)],
            "ids": [[f"u{i:02d}{chr(97 + j)}" for j in range(n)] for i, n in enumerate(shared)],
        }
    )
    return units, normalise(np.asarray(rows, dtype=np.float32)), draw(st.integers(1, 5))


@given(data=units_and_vectors())
def test_k_rows_per_id_never_the_own_file_ranked_by_similarity(
    data: tuple[pl.DataFrame, np.ndarray, int],
) -> None:
    units, vectors, k = data
    table = neighbor_table(units, vectors, k)
    take = min(k, units.height - 1)
    every_id = [i for ids in units.get_column("ids").to_list() for i in ids]
    assert table.get_column("id").to_list() == sorted(i for i in every_id for _ in range(take))
    unit_of = {i: row for row, ids in enumerate(units.get_column("ids").to_list()) for i in ids}
    position = {u: row for row, u in enumerate(units.get_column("id").to_list())}
    sims = vectors @ vectors.T
    for unit, rows in table.group_by("id"):
        row = unit_of[str(unit[0])]
        expected = sorted(
            (j for j in range(units.height) if j != row), key=lambda j: (-sims[row, j], j)
        )[:take]
        assert [position[n] for n in rows.get_column("nachbar").to_list()] == expected
        assert rows.get_column("rang").to_list() == list(range(1, take + 1))
        assert rows.get_column("aehnlichkeit").is_sorted(descending=True)


@given(
    counts=st.lists(st.integers(1, 6), min_size=1, max_size=6),
    document_chunks=st.integers(1, 4),
    seed=st.integers(0, 2**16),
)
def test_a_document_vector_is_the_normalised_mean_of_its_first_chunks(
    counts: list[int], document_chunks: int, seed: int
) -> None:
    rng = np.random.default_rng(seed)
    vectors = normalise(rng.normal(size=(sum(counts), 3)).astype(np.float32))
    places = [p for n in counts for p in range(n)]
    got = document_vectors(places, vectors, document_chunks)
    start = 0
    for row, n in enumerate(counts):
        mean = vectors[start : start + min(n, document_chunks)].astype(np.float64).sum(axis=0)
        assert np.allclose(got[row], mean / np.linalg.norm(mean), atol=1e-5)
        start += n


@given(
    sims=st.lists(st.floats(-1, 1, width=32), min_size=1, max_size=12),
    units=st.integers(1, 4),
    seed=st.integers(0, 99),
)
def test_the_score_of_a_unit_is_the_maximum_over_its_chunks(
    sims: list[float], units: int, seed: int
) -> None:
    unit = np.random.default_rng(seed).integers(0, units, size=len(sims))
    got = max_per_unit(np.asarray(sims, dtype=np.float32), unit, units)
    for u in range(units):
        mine = [s for s, owner in zip(sims, unit, strict=True) if owner == u]
        assert got[u] == (np.float32(max(mine)) if mine else -np.inf)
