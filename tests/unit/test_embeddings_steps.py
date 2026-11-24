"""Der Beitrag von Vorhaben 18: Einbettungen mit ``FakeEmbedder``, Nachbarn aus Vektoren oder Paket.

Nie ein Modell (CLAUDE.md, F5): der Einbetter ist ``tests.fakes.FakeEmbedder``, dessen Vektor eine
Funktion des Texts ist. Der Datensatz ist klein und von Hand: eine Datei, die sich zwei Korpus-IDs
teilen, eine mit Rohtext nur aus Leerraum, ein Dokument ohne Datei, und genug weitere, damit jede
Einheit zwei Nachbarn hat.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from georep.contracts import one_row_per_document
from georep.enrich import CONTRIBUTIONS
from georep.enrich.embeddings import (
    CHUNK_PROMPT,
    QUERY_PROMPT,
    chunk_prompt,
    embedding_files,
    embeddings_steps,
    model_steps,
    query_prompt,
)
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import Step, build_steps, run_pipeline
from georep.search.vectors import NEIGHBORS_SCHEMA, NEIGHBORS_SCHEMA_VERSION
from georep.settings import Embeddings, Settings
from georep.stores import RawTextStore
from tests.fakes import FakeEmbedder, FakeSession

HTTP = FakeSession({})
TEXTS = {
    "f1.pdf": "Radweg an der Schule\nZweite Zeile mit mehr Text\fSeite zwei",
    "f2.pdf": "Baumfällungen im Park\n" + "\n".join(f"Zeile {i} über Bäume" for i in range(8)),
    "f3.pdf": " \n\f\t",
    "f4.pdf": "Kita und Ganztag",
    "f5.pdf": "Haushalt der Stadt\nProdukt und Zeile",
}
CORPUS = [
    ("id1", "Antrag Radweg", "f1.pdf"),
    ("id2", "Bäume  im\nPark", "f2.pdf"),
    ("id3", "Leer", "f3.pdf"),
    ("id4", "Ohne Datei", None),
    ("id5", "Antrag Radweg, zweite ID", "f1.pdf"),
    ("id6", "Kita", "f4.pdf"),
    ("id7", "Haushalt", "f5.pdf"),
]


@pytest.fixture
def settings(default_settings: Settings) -> Settings:
    small = Embeddings(enabled=True, chunk_chars=40, title_chars=10, overlap_chars=5, neighbors=2)
    return default_settings.model_copy(update={"embeddings": small})


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    layout.ensure_dirs()
    corpus = pl.DataFrame(CORPUS, schema=["id", "name", "file_name"], orient="row")
    corpus.write_parquet(layout.corpus)
    store = RawTextStore(layout.raw_texts)
    for name, text in TEXTS.items():
        store.put(name, text, pages=text.count("\f") + 1, extractor="probe+roh", pdf_sha256="0")
    store.save()
    return layout


def _steps(settings: Settings, layout: Layout, embedder: FakeEmbedder) -> dict[str, Step]:
    return {s.name: s for s in model_steps(settings, layout, embedder)}


def test_the_contribution_is_registered_and_switched_by_the_profile(
    settings: Settings, layout: Layout, default_settings: Settings
) -> None:
    assert "18-einbettungen" in [c.name for c in CONTRIBUTIONS]
    names = [s.name for s in embeddings_steps(settings, layout, HTTP)]
    assert names == ["embeddings", "neighbors"]
    off = settings.model_copy(update={"embeddings": Embeddings()})
    assert embeddings_steps(off, layout, HTTP) == []
    every = [s.name for s in build_steps(settings, layout, HTTP)]
    assert every.index("cosponsors") < every.index("embeddings") < every.index("neighbors")
    assert every.index("neighbors") == every.index("report") - 1


def test_the_steps_read_and_write_what_the_plan_names(settings: Settings, layout: Layout) -> None:
    steps = _steps(settings, layout, FakeEmbedder())
    files = embedding_files(layout)
    assert steps["embeddings"].inputs == (layout.corpus, layout.raw_texts)
    assert steps["embeddings"].outputs == (files.chunks, files.documents)
    assert steps["embeddings"].models is not None
    assert steps["neighbors"].inputs == ()
    assert steps["neighbors"].optional == (files.documents, files.package)
    assert files.neighbors == layout.processed / "aehnliche_dokumente.parquet"
    assert files.package == layout.raw / "aehnliche_dokumente_paket.parquet"


def test_the_measured_settings_keep_the_measured_prompt_versions(
    default_settings: Settings,
) -> None:
    """Mit den Werten der Messung trifft der Lauf ihre Vektoren im Modellcache."""
    assert chunk_prompt(default_settings) == CHUNK_PROMPT == "18-stuecke-1"
    assert query_prompt(default_settings) == QUERY_PROMPT == "18-anfrage-1"
    embedding = default_settings.ml.embedding.model_copy(update={"document_prefix": "doc: "})
    other = default_settings.model_copy(
        update={"ml": default_settings.ml.model_copy(update={"embedding": embedding})}
    )
    assert chunk_prompt(other).startswith("18-stuecke-1+") and chunk_prompt(other) != CHUNK_PROMPT
    assert query_prompt(other) == QUERY_PROMPT
    shorter = default_settings.embeddings.model_copy(update={"chunk_chars": 1200})
    assert chunk_prompt(default_settings.model_copy(update={"embeddings": shorter})) != CHUNK_PROMPT


def test_a_run_with_models_writes_vectors_and_neighbors(settings: Settings, layout: Layout) -> None:
    embedder = FakeEmbedder()
    steps = _steps(settings, layout, embedder)
    outcomes = run_pipeline(list(steps.values()), settings, models=True)
    assert [(o.step, o.status) for o in outcomes] == [
        ("embeddings", "ausgeführt"),
        ("neighbors", "ausgeführt"),
    ]
    files = embedding_files(layout)
    chunks = pl.read_parquet(files.chunks)
    assert chunks.columns == ["datei", "stueck", "start", "end", "vektor"]
    assert chunks.schema["vektor"] == pl.Array(pl.Float32, embedder.dimension)
    assert set(chunks.get_column("datei")) == {"f1.pdf", "f2.pdf", "f4.pdf", "f5.pdf"}
    assert chunks.filter(pl.col("datei") == "f2.pdf").height > 1  # f2 braucht mehrere Stücke
    norms = np.linalg.norm(chunks.get_column("vektor").to_numpy(), axis=1)
    assert np.allclose(norms, 1.0, atol=1e-6)
    # was das Modell sah: Präfix, Titel, Leerzeile, Rumpf
    seen = [text for call in embedder.calls for text in call]
    assert seen[0] == "search_document: Antrag Rad\n\nRadweg an der Schule"
    documents = pl.read_parquet(files.documents)
    with_text = ["id1", "id2", "id5", "id6", "id7"]
    assert one_row_per_document(documents, with_text)
    one, five = (
        documents.filter(pl.col("id") == i).get_column("vektor").to_numpy()[0]
        for i in ("id1", "id5")
    )
    assert np.array_equal(one, five)  # dieselbe Datei, derselbe Vektor
    neighbors = pl.read_parquet(files.neighbors)
    assert dict(neighbors.schema) == NEIGHBORS_SCHEMA
    assert neighbors.group_by("id").len().sort("id").rows() == [(i, 2) for i in with_text]
    for _, rows in neighbors.group_by("id"):
        assert rows.get_column("rang").to_list() == [1, 2]
        assert rows.get_column("aehnlichkeit").is_sorted(descending=True)
    own = dict(CORPUS_FILES)
    assert all(own[i] != own[n] for i, n in neighbors.select("id", "nachbar").iter_rows())
    assert set(neighbors.get_column("nachbar")) <= {"id1", "id2", "id6", "id7"}  # nie id5
    stamp = json.loads(steps["embeddings"].stamp_path.read_text(encoding="utf-8"))
    assert stamp["models"]["prompt"] == chunk_prompt(settings) != CHUNK_PROMPT  # kleine Stücke
    assert stamp["models"]["open"] == 0


CORPUS_FILES = [(i, f) for i, _, f in CORPUS]


def test_the_neighbors_are_the_most_similar_other_files(settings: Settings, layout: Layout) -> None:
    steps = _steps(settings, layout, FakeEmbedder())
    run_pipeline(list(steps.values()), settings, models=True)
    files = embedding_files(layout)
    documents = pl.read_parquet(files.documents).filter(pl.col("id") != "id5")
    ids = documents.get_column("id").to_list()
    matrix = documents.get_column("vektor").to_numpy()
    sims = matrix @ matrix.T
    expected = []
    for row, unit in enumerate(ids):
        order = sorted((j for j in range(len(ids)) if j != row), key=lambda j: (-sims[row, j], j))
        expected += [(unit, rank, ids[j]) for rank, j in enumerate(order[:2], start=1)]
    got = pl.read_parquet(files.neighbors).filter(pl.col("id") != "id5")
    assert got.select("id", "rang", "nachbar").rows() == expected


def test_a_partial_run_leaves_documents_without_all_first_chunks_out(
    settings: Settings, layout: Layout
) -> None:
    limited = settings.model_copy(update={"ml": settings.ml.model_copy(update={"limit": 3})})
    steps = _steps(limited, layout, FakeEmbedder())
    outcome = run_pipeline([steps["embeddings"]], limited, models=True)[0]
    assert outcome.status == "ausgeführt" and "offen" in outcome.reason
    files = embedding_files(layout)
    assert pl.read_parquet(files.chunks).get_column("datei").to_list() == ["f1.pdf"] * 3
    stamp = json.loads(steps["embeddings"].stamp_path.read_text(encoding="utf-8"))
    assert stamp["models"]["open"] > 0
    # f1 hat drei Stücke, alle gerechnet: nur seine IDs haben einen Dokumentvektor
    assert pl.read_parquet(files.documents).get_column("id").to_list() == ["id1", "id5"]


def test_without_vectors_the_neighbors_come_from_the_package(
    settings: Settings, layout: Layout
) -> None:
    steps = _steps(settings, layout, FakeEmbedder())
    outcomes = run_pipeline(list(steps.values()), settings)  # ohne --models
    assert [(o.step, o.status) for o in outcomes] == [
        ("embeddings", "übersprungen"),
        ("neighbors", "ausgeführt"),
    ]
    files = embedding_files(layout)
    assert pl.read_parquet(files.neighbors).height == 0
    assert "leere Tabelle" in outcomes[1].reason
    packed = pl.DataFrame(
        {
            "id": ["id2", "id1"],
            "rang": [1, 1],
            "nachbar": ["id1", "id2"],
            "aehnlichkeit": [0.5] * 2,
        },
        schema=NEIGHBORS_SCHEMA,
    )
    write_parquet(packed, files.package, schema_version=NEIGHBORS_SCHEMA_VERSION)
    again = run_pipeline([steps["neighbors"]], settings)[0]
    assert again.status == "ausgeführt" and "aus dem Paket" in again.reason
    assert pl.read_parquet(files.neighbors).get_column("id").to_list() == ["id1", "id2"]
    assert run_pipeline([steps["neighbors"]], settings)[0].reason == "aktuell"
    # sind die Dokumentvektoren da, gelten sie, und das Paket tritt zurück
    run_pipeline(list(steps.values()), settings, models=True)
    assert pl.read_parquet(files.neighbors).height == 10


def test_a_package_with_other_columns_is_a_schema_error(settings: Settings, layout: Layout) -> None:
    from georep.errors import SchemaError

    files = embedding_files(layout)
    write_parquet(pl.DataFrame({"id": ["id1"]}), files.package, schema_version=1)
    steps = _steps(settings, layout, FakeEmbedder())
    with pytest.raises(SchemaError, match="aehnliche_dokumente"):
        run_pipeline([steps["neighbors"]], settings)


def test_a_rejected_chunk_leaves_its_document_without_a_vector(
    settings: Settings, layout: Layout
) -> None:
    """2014 bis 2020: ein Dokument mit Zeichensalat (Steuerzeichen) hat Stücke über 512 Token, und
    ollama weist sie trotz ``truncate`` ab (400). Abgewiesen ist erledigt (F5): der Schritt ist
    aktuell, das Dokument hat keinen Dokumentvektor und keine Nachbarn, die übrigen schon."""
    from georep.search.units import build_units, raw_frame, unit_chunks

    corpus = pl.read_parquet(layout.corpus)
    store = RawTextStore(layout.raw_texts)
    raw = raw_frame((n, str(r["text"]), store.form_feeds(n)) for n, r in store.rows.items())
    chunks = unit_chunks(build_units(corpus, raw, 10), 40, 5, "search_document: ")
    first = chunks.filter(pl.col("datei") == "f2.pdf").get_column("text")[0]
    steps = _steps(settings, layout, FakeEmbedder(rejects={first}))
    outcomes = run_pipeline(list(steps.values()), settings, models=True)
    assert [o.status for o in outcomes] == ["ausgeführt", "ausgeführt"]
    assert "1 abgewiesen" in outcomes[0].reason
    assert "1 ohne eines der ersten 3 Stücke" in outcomes[0].reason
    files = embedding_files(layout)
    assert "id2" not in pl.read_parquet(files.documents).get_column("id").to_list()
    neighbors = pl.read_parquet(files.neighbors)
    assert "id2" not in set(neighbors.get_column("id")) | set(neighbors.get_column("nachbar"))
    again = run_pipeline([steps["embeddings"]], settings, models=True)[0]
    assert again.status == "übersprungen" and again.reason == "aktuell, 1 Eingaben abgewiesen"
