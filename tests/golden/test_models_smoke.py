"""Rauchtest gegen den echten ollama-Server (Fundament F5): nur von Hand, nie in CI.

Der Marker ``models`` hält ihn aus jeder nox-Session; ``uv run pytest -m models`` startet ihn, wenn
``ollama serve`` läuft und die Modelle aus ``[ml]`` gezogen sind. Er kostet ein paar Sekunden
Grafikkarte: zwei Einbettungen, zwei Antworten mit höchstens 16 Token, eine kleine Runde durch den
Cache in ``tmp_path``. Jeder andere Test nimmt die Fakes aus ``tests/fakes.py``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from georep.ml.base import EmbeddingUse
from georep.ml.batch import embed_texts
from georep.ml.cache import ModelCache
from georep.ml.ollama import (
    client_from_settings,
    embedder_from_settings,
    generation_options,
    generator_from_settings,
)
from georep.settings import load_settings

pytestmark = pytest.mark.models

TEXTS = ["Radverkehr in der Innenstadt", "Haushaltsplan und Stellenplan"]


def test_the_configured_models_answer_and_the_cache_holds(tmp_path: Path) -> None:
    ml = load_settings(cwd=Path("/nonexistent")).ml
    client = client_from_settings(ml)
    assert client.version()
    embedder = embedder_from_settings(ml, client)
    vectors = embedder.embed(TEXTS)
    assert vectors.shape == (2, ml.embedding.dimension)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-3)
    assert len(embedder.digest) == 64
    with ModelCache(tmp_path, embedder.name) as cache:
        use = EmbeddingUse(embedder, "rauchtest")
        first = embed_texts(use, cache, TEXTS)
        again = embed_texts(use, cache, TEXTS)
    assert (first.report.computed, again.report.computed) == (2, 0)
    assert np.allclose(first.vectors, vectors, atol=1e-4)

    generator = generator_from_settings(ml, client)
    options = replace(generation_options(ml), num_predict=16)
    question = "Antworte mit einem einzigen Wort: Welche Farbe hat Gras?"
    answer = generator.generate(question, options=options)
    assert answer.text.strip() and "<think>" not in answer.text
    assert generator.generate(question, options=options) == answer  # Temperatur 0, fester Seed
