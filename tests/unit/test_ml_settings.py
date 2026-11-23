"""Die Settings der Modellnaht (F5): Vorgaben, Fingerprint, Fabriken ohne Netz, Ort des Caches."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from georep.layout import Layout
from georep.ml.base import EmbeddingOptions, GenerationOptions
from georep.ml.ollama import (
    OllamaEmbedder,
    OllamaGenerator,
    client_from_settings,
    embedder_from_settings,
    generator_from_settings,
)
from georep.settings import load_settings
from tests.fakes import FakeOllama


def _with(tmp_path: Path, block: str) -> str:
    """Der Fingerprint mit einem zusätzlichen ``[ml]``-Block in ``settings.toml``."""
    (tmp_path / "settings.toml").write_text(block, encoding="utf-8")
    return load_settings(cwd=tmp_path).fingerprint()


def test_the_defaults_name_the_local_models_and_deterministic_options() -> None:
    ml = load_settings(cwd=Path("/nonexistent")).ml
    assert ml.base_url == "http://localhost:11434"
    assert (ml.embedding.model, ml.embedding.dimension) == ("nomic-embed-text-v2-moe", 768)
    assert ml.generation.model == "qwen3.6:27b"
    assert (ml.generation.temperature, ml.generation.seed, ml.generation.think) == (0.0, 0, False)
    assert ml.limit == 0


@pytest.mark.parametrize(
    "block",
    [
        '[ml]\nbase_url = "http://127.0.0.1:11434"\n',
        "[ml]\ntimeout_s = 30.0\n",
        "[ml]\nretries = 0\n",
        "[ml]\nbackoff_s = 0.5\n",
        '[ml]\nkeep_alive = "1h"\n',
        "[ml]\nbatch_size = 8\n",
        "[ml]\nlimit = 500\n",
        '[ml.embedding]\nmodel = "nomic-embed-text"\n',
        "[ml.embedding]\nnum_ctx = 256\n",
        "[ml.embedding]\ntruncate = false\n",
        '[ml.generation]\nmodel = "gemma4"\n',
        "[ml.generation]\ntemperature = 0.2\n",
        "[ml.generation]\nseed = 1\n",
        "[ml.generation]\nnum_ctx = 4096\n",
        "[ml.generation]\nnum_predict = 120\n",
        "[ml.generation]\nthink = true\n",
    ],
)
def test_no_ml_value_changes_the_global_fingerprint(tmp_path: Path, block: str) -> None:
    """Befund 3 des Reviews: Modell, Optionen und ``limit`` stehen im Stamp des Modellschritts.

    Im globalen Fingerprint ließen sie jeden Schritt neu laufen, auch die ohne Modell, und der
    Merge von F5 hätte die ganze Kette einmal neu gerechnet.
    """
    base = load_settings(cwd=Path("/nonexistent")).fingerprint()
    assert _with(tmp_path, block) == base


@pytest.mark.parametrize(
    "block",
    [
        "[ml]\nunbekannt = 1\n",
        "[ml]\nbatch_size = 0\n",
        "[ml]\nlimit = -1\n",
        "[ml]\nretries = -1\n",
        "[ml.embedding]\ndimension = 0\n",
        "[ml.generation]\nnum_predict = 0\n",
        "[ml.generation]\ntemperature = -0.1\n",
        '[ml]\nbase_url = "localhost:11434"\n',
    ],
)
def test_wrong_values_are_refused(tmp_path: Path, block: str) -> None:
    (tmp_path / "settings.toml").write_text(block, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_settings(cwd=tmp_path)


def test_the_factories_build_without_asking_the_server(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[ml]\nbase_url = "http://ollama.test"\nretries = 4\nkeep_alive = "2m"\n'
        "[ml.generation]\nnum_predict = 120\nseed = 9\n",
        encoding="utf-8",
    )
    ml = load_settings(cwd=tmp_path).ml
    server = FakeOllama()
    client = client_from_settings(ml, transport=server)
    assert (client.base_url, client.retries, client.keep_alive) == ("http://ollama.test", 4, "2m")
    embedder = embedder_from_settings(ml, client)
    generator = generator_from_settings(ml, client)
    other = generator_from_settings(ml, client, model="gemma4")
    assert isinstance(embedder, OllamaEmbedder) and isinstance(generator, OllamaGenerator)
    assert embedder.name == "nomic-embed-text-v2-moe:latest" and embedder.dimension == 768
    assert embedder.options == EmbeddingOptions(num_ctx=ml.embedding.num_ctx, truncate=True)
    assert generator.options == GenerationOptions(
        temperature=0.0, seed=9, num_ctx=ml.generation.num_ctx, num_predict=120, think=False
    )
    assert other.name == "gemma4:latest" and other.options == generator.options
    assert server.requests == []


def test_the_model_cache_lies_under_cache_root_shared_by_all_profiles() -> None:
    settings = load_settings(cwd=Path("/nonexistent"))
    layout = Layout.from_settings(settings)
    assert layout.ml_cache == layout.cache_root / "ml"
    assert layout.for_profile("andere-periode").ml_cache == layout.ml_cache
