"""Vorhaben 18: Vektoren je Stück und je Dokument, die Suche über Stücke und die ähnlichen Dokumente.

Messdokument ``docs/plans/18-einbettungen.md``, § 3.1 und § 6. Vektoren werden auf Länge 1 normiert,
Ähnlichkeit ist das Skalarprodukt. Die Punktzahl einer Einheit für eine Frage ist das Maximum über
ihre Stücke. Der Dokumentvektor (Fassung ``18-dokvektor-1``) ist das Mittel der normierten Vektoren
der ersten ``document_chunks`` Stücke, wieder normiert. Die Nachbarn einer Einheit sind die
``k`` Einheiten mit dem größten Skalarprodukt ihrer Dokumentvektoren, ohne die eigene Datei;
Gleichstände nach ID aufsteigend, auch an der Grenze zum ``k``-ten Platz.

Die Tabellen, die der Beitrag ``18-einbettungen`` schreibt, haben ihre Schemata und
Schema-Versionen hier; die Vektoren liegen als ``Array(Float32, dimension)``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import deal
import numpy as np
import numpy.typing as npt
import polars as pl

from georep.contracts import has_columns

Matrix = npt.NDArray[np.float32]

# Die beiden lokalen Dateien des Schritts ``embeddings``, eine Version für beide:
# processed/einbettungen_stuecke.parquet, je Stück mit Vektor eine Zeile, nach datei, stueck;
# processed/einbettungen_dokumente.parquet, je Korpus-ID mit Dokumentvektor eine Zeile, nach id.
EMBEDDINGS_SCHEMA_VERSION = 1
# processed/aehnliche_dokumente.parquet (und das Paket): je Korpus-ID mit Dokumentvektor k Zeilen
NEIGHBORS_SCHEMA_VERSION = 1
NEIGHBORS_SCHEMA = {
    "id": pl.String,
    "rang": pl.Int64,  # 1 bis k, lückenlos
    "nachbar": pl.String,  # die kleinste Korpus-ID der Nachbardatei
    "aehnlichkeit": pl.Float32,  # Skalarprodukt der Dokumentvektoren, auf vier Stellen
}
BLOCK = 2048  # Zeilen der Ähnlichkeitsmatrix je Schritt: 2 048 × 19 032 float32 sind 156 MB


def vector_dtype(dimension: int) -> pl.Array:
    return pl.Array(pl.Float32, dimension)


def chunk_vectors_schema(dimension: int) -> dict[str, pl.DataType]:
    return {
        "datei": pl.String(),
        "stueck": pl.Int32(),
        "start": pl.Int64(),
        "end": pl.Int64(),
        "vektor": vector_dtype(dimension),
    }


def document_vectors_schema(dimension: int) -> dict[str, pl.DataType]:
    return {"id": pl.String(), "datei": pl.String(), "vektor": vector_dtype(dimension)}


@deal.ensure(lambda matrix, result: result.shape == matrix.shape and result.dtype == np.float32)
def normalise(matrix: npt.NDArray[np.floating[Any]]) -> Matrix:
    """Jede Zeile auf Länge 1; eine Nullzeile bleibt null."""
    values = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(values, axis=-1, keepdims=True)
    result: Matrix = np.divide(values, norms, out=np.zeros_like(values), where=norms > 0)
    return result


@deal.pre(
    lambda places, vectors, document_chunks: (
        len(places) == vectors.shape[0]
        and document_chunks >= 1
        and (len(places) == 0 or places[0] == 0)
    ),
    message="je Stück eine Stelle und ein Vektor, das erste Stück beginnt eine Einheit",
)
@deal.ensure(
    lambda places, vectors, document_chunks, result: (
        result.shape == (sum(1 for p in places if p == 0), vectors.shape[1])
    )
)
def document_vectors(places: Sequence[int], vectors: Matrix, document_chunks: int) -> Matrix:
    """Die Dokumentvektoren aus den Stücken: Mittel der ersten ``document_chunks``, normiert.

    ``places`` ist die Stelle jedes Stücks in seiner Einheit (0 beginnt die nächste Einheit),
    ``vectors`` die normierten Stückvektoren in derselben Folge; eine Zeile je Einheit, in Folge.
    Summiert wird wie in der Messung in float64, über die Stücke in ihrer Folge; das Mittel ist
    nach dem Normieren dieselbe Richtung wie die Summe.
    """
    place = np.asarray(places, dtype=np.int64)
    unit = np.cumsum(place == 0) - 1
    total = np.zeros((int(np.count_nonzero(place == 0)), vectors.shape[1]), dtype=np.float64)
    take = place < document_chunks
    np.add.at(total, unit[take], vectors[take])
    return normalise(total.astype(np.float32))


@deal.pre(lambda sims, unit, units: len(sims) == len(unit))
@deal.ensure(lambda sims, unit, units, result: result.shape == (units,))
def max_per_unit(
    sims: npt.NDArray[np.float32], unit: npt.NDArray[np.int64], units: int
) -> npt.NDArray[np.float64]:
    """Die Punktzahl jeder Einheit: das Maximum über ihre Stücke; ohne Stück −∞."""
    values = np.full(units, -np.inf, dtype=np.float64)
    np.maximum.at(values, unit, sims)
    return values


def _top(row: npt.NDArray[np.float32], k: int) -> npt.NDArray[np.int64]:
    """Die ``k`` größten Werte einer Zeile, fallend, Gleichstände nach Position, auch an der Grenze."""
    if k <= 0:
        return np.zeros(0, dtype=np.int64)
    if k >= len(row):
        candidates = np.arange(len(row))
    else:
        threshold = np.partition(row, len(row) - k)[len(row) - k]
        candidates = np.flatnonzero(row >= threshold)
    order = np.lexsort((candidates, -row[candidates]))
    return candidates[order][:k]


def _neighbors_hold(
    units: pl.DataFrame, vectors: Matrix, k: int, result: pl.DataFrame | None = None
) -> bool:
    assert result is not None
    if dict(result.schema) != NEIGHBORS_SCHEMA:
        return False
    own = dict(zip(units["id"], units["datei"], strict=True))
    per = result.group_by("id").agg(
        pl.col("rang").alias("r"), pl.col("aehnlichkeit").alias("a"), pl.col("nachbar").alias("n")
    )
    wanted = min(k, units.height - 1)
    return all(
        rang == list(range(1, wanted + 1))
        and all(x >= y for x, y in zip(sims, sims[1:], strict=False))
        and all(own[n] != own.get(i, own[n] + "?") for n in nachbarn)
        for i, rang, sims, nachbarn in per.iter_rows()
        if i in own
    )


@deal.pre(
    lambda units, vectors, k: (
        has_columns(units, "id", "datei", "ids") and units.height == vectors.shape[0] and k >= 1
    ),
    message="je Einheit ein Dokumentvektor, k mindestens 1",
)
@deal.ensure(
    lambda units, vectors, k, result: (
        result.height == min(k, max(units.height - 1, 0)) * units.get_column("ids").list.len().sum()
    ),
    message="k Nachbarn je Korpus-ID (weniger, wenn es weniger andere Dateien gibt)",
)
@deal.ensure(_neighbors_hold, message="Rang lückenlos, Ähnlichkeit fallend, nie die eigene Datei")
def neighbor_table(units: pl.DataFrame, vectors: Matrix, k: int) -> pl.DataFrame:
    """Je Korpus-ID die ``k`` ähnlichsten anderen Dateien: ``id``, ``rang``, ``nachbar``, ``aehnlichkeit``.

    ``units`` sind die Einheiten (eine je Datei, ``id`` die kleinste ihrer ``ids``) in der Folge der
    Zeilen von ``vectors`` (normierte Dokumentvektoren). Gerechnet wird je Einheit, in Blöcken zu
    ``BLOCK`` Zeilen in float32; jede Korpus-ID einer Datei bekommt die Zeilen ihrer Einheit, und
    ``nachbar`` ist die Einheit, also die kleinste ID der Nachbardatei. Sortiert nach ``id, rang``.
    """
    ids = units.get_column("id").to_list()
    count = len(ids)
    take = min(k, max(count - 1, 0))
    neighbors = np.zeros((count, take), dtype=np.int64)
    values = np.zeros((count, take), dtype=np.float32)
    for start in range(0, count, BLOCK):
        block = vectors[start : start + BLOCK] @ vectors.T
        for r in range(block.shape[0]):
            block[r, start + r] = -np.inf
            best = _top(block[r], take)
            neighbors[start + r] = best
            values[start + r] = block[r, best]
    frame = pl.DataFrame(
        {
            "unit": np.repeat(np.arange(count), take),
            "rang": np.tile(np.arange(1, take + 1, dtype=np.int64), count),
            "nachbar": [ids[j] for j in neighbors.ravel()],
            "aehnlichkeit": np.round(values.ravel(), 4).astype(np.float32),
        },
        schema={
            "unit": pl.Int64,
            "rang": pl.Int64,
            "nachbar": pl.String,
            "aehnlichkeit": pl.Float32,
        },
    )
    members = units.select(pl.int_range(pl.len(), dtype=pl.Int64).alias("unit"), "ids").explode(
        "ids"
    )
    return (
        members.join(frame, on="unit", how="inner")
        .select(pl.col("ids").alias("id"), "rang", "nachbar", "aehnlichkeit")
        .sort("id", "rang")
    )
