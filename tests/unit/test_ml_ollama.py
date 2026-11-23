"""Das ollama-Backend der Modellnaht (F5) gegen einen Server als Tabelle, nie gegen den echten."""

from __future__ import annotations

import numpy as np
import pytest
import requests

from georep.errors import ModelError
from georep.ml.base import Embedder, GenerationOptions, Generator, full_name, model_stamp
from georep.ml.ollama import OllamaClient, OllamaEmbedder, OllamaGenerator
from tests.fakes import FakeOllama, FakeSession, fake_answer, fake_vector, response

URL = "http://ollama.test"


def _client(
    server: FakeOllama, *, retries: int = 2, backoff_s: float = 2.0, keep_alive: str = "10m"
) -> tuple[OllamaClient, list[float]]:
    """Ein Client gegen den Tabellenserver; die Pausen der Wiederholungen landen in der Liste."""
    pauses: list[float] = []
    client = OllamaClient(
        URL,
        transport=server,
        retries=retries,
        backoff_s=backoff_s,
        keep_alive=keep_alive,
        sleep=pauses.append,
    )
    return client, pauses


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("nomic-embed-text-v2-moe", "nomic-embed-text-v2-moe:latest"),
        ("qwen3.6:27b", "qwen3.6:27b"),
        ("hf.co/someone/model:Q4_K_M", "hf.co/someone/model:Q4_K_M"),
        ("registry.test:5000/library/model", "registry.test:5000/library/model:latest"),
    ],
)
def test_full_name_adds_the_default_tag_only_without_one(name: str, expected: str) -> None:
    assert full_name(name) == expected


def test_version_names_the_server() -> None:
    client, _ = _client(FakeOllama())
    assert client.version() == "0.0-fake"


def test_an_unreachable_server_is_a_model_error_at_once() -> None:
    server = FakeOllama(down=True)
    client, pauses = _client(server, retries=3)
    with pytest.raises(ModelError, match=r"nicht erreichbar.*ollama serve"):
        client.version()
    # Die Probe wiederholt nicht: ``georep ml status`` soll sofort sagen, dass nichts läuft.
    assert server.paths == ["/api/version"] and pauses == []


def test_info_finds_a_model_without_tag_and_asks_the_server_once() -> None:
    server = FakeOllama()
    client, _ = _client(server)
    first = client.info("fake-embed")
    again = client.info("fake-embed:latest")
    assert first == again and first.name == "fake-embed:latest" and first.digest == "e" * 64
    assert server.paths.count("/api/tags") == 1


def test_a_missing_model_says_how_to_get_it() -> None:
    client, _ = _client(FakeOllama())
    with pytest.raises(ModelError, match=r"ollama pull gibt-es-nicht"):
        client.info("gibt-es-nicht")


def test_embedder_returns_one_float32_row_per_text_and_sends_the_options() -> None:
    server = FakeOllama(dimension=8)
    client, _ = _client(server, keep_alive="5m")
    embedder: Embedder = OllamaEmbedder(client, "fake-embed", dimension=8, num_ctx=512)
    vectors = embedder.embed(["eins", "zwei zwei"])
    assert vectors.dtype == np.float32 and vectors.shape == (2, 8)
    assert np.allclose(vectors[1], fake_vector("zwei zwei", 8), atol=1e-7)
    path, payload = server.requests[-1]
    assert path == "/api/embed"
    assert payload == {
        "model": "fake-embed:latest",
        "input": ["eins", "zwei zwei"],
        "truncate": True,
        "options": {"num_ctx": 512},
        "keep_alive": "5m",
    }
    assert embedder.name == "fake-embed:latest" and embedder.digest == "e" * 64


def test_embedder_without_texts_asks_nothing() -> None:
    server = FakeOllama()
    client, _ = _client(server)
    vectors = OllamaEmbedder(client, "fake-embed", dimension=8).embed([])
    assert vectors.shape == (0, 8) and server.requests == []


def test_embedder_refuses_a_wrong_dimension() -> None:
    client, _ = _client(FakeOllama(dimension=8))
    with pytest.raises(ModelError, match=r"Dimension 8 statt 768"):
        OllamaEmbedder(client, "fake-embed", dimension=768).embed(["eins"])


def test_embedder_counts_tokens_and_seconds_per_call() -> None:
    client, _ = _client(FakeOllama())
    embedder = OllamaEmbedder(client, "fake-embed", dimension=8)
    embedder.embed(["a b c", "d"])
    (call,) = embedder.calls
    assert call.items == 2 and call.prompt_tokens == 4 and call.output_tokens == 0
    assert call.seconds == pytest.approx(0.004) and call.load_seconds == pytest.approx(0.001)


def test_generator_sends_deterministic_options_and_switches_thinking_off() -> None:
    server = FakeOllama()
    client, _ = _client(server)
    options = GenerationOptions(temperature=0.0, seed=7, num_ctx=4096, num_predict=64, think=False)
    generator: Generator = OllamaGenerator(client, "fake-chat", options=options)
    answer = generator.generate("Fasse zusammen: Text", system="Du fasst zusammen.")
    assert answer == fake_answer("Du fasst zusammen.", "Fasse zusammen: Text")
    path, payload = server.requests[-1]
    assert path == "/api/chat"
    assert payload["messages"] == [
        {"role": "system", "content": "Du fasst zusammen."},
        {"role": "user", "content": "Fasse zusammen: Text"},
    ]
    assert payload["options"] == {"temperature": 0.0, "seed": 7, "num_ctx": 4096, "num_predict": 64}
    assert payload["think"] is False and payload["stream"] is False


def test_generator_leaves_think_out_for_a_model_that_cannot_think() -> None:
    server = FakeOllama()
    client, _ = _client(server)
    OllamaGenerator(client, "plain-chat:7b", options=GenerationOptions()).generate("Hallo")
    _, payload = server.requests[-1]
    assert "think" not in payload
    assert [m["role"] for m in payload["messages"]] == ["user"]


def test_thinking_on_a_model_that_cannot_think_is_an_error() -> None:
    client, _ = _client(FakeOllama())
    generator = OllamaGenerator(client, "plain-chat:7b", options=GenerationOptions(think=True))
    with pytest.raises(ModelError, match=r"kann nicht denken"):
        generator.generate("Hallo")


def test_generator_records_a_cut_answer() -> None:
    client, _ = _client(FakeOllama())
    generator = OllamaGenerator(client, "fake-chat", options=GenerationOptions(num_predict=2))
    assert len(generator.generate("ein langer Prompt").split()) == 2
    assert generator.calls[-1].truncated and generator.calls[-1].output_tokens == 2


def test_call_options_override_the_defaults() -> None:
    server = FakeOllama()
    client, _ = _client(server)
    generator = OllamaGenerator(client, "fake-chat", options=GenerationOptions(num_predict=50))
    generator.generate("x", options=GenerationOptions(num_predict=3, seed=1))
    assert server.requests[-1][1]["options"]["num_predict"] == 3


def test_a_server_error_is_retried_with_backoff() -> None:
    server = FakeOllama(failures=[503, 500])
    client, pauses = _client(server, retries=2, backoff_s=2.0)
    vectors = OllamaEmbedder(client, "fake-embed", dimension=8).embed(["eins"])
    assert vectors.shape == (1, 8)
    assert pauses == [2.0, 4.0]


def test_a_persistent_server_error_ends_as_model_error_after_bounded_retries() -> None:
    server = FakeOllama(failures=[503] * 5)
    client, pauses = _client(server, retries=2, backoff_s=1.0)
    with pytest.raises(ModelError, match=r"503"):
        client.info("fake-embed")
    assert len(server.requests) == 3 and pauses == [1.0, 2.0]


def test_a_client_error_is_not_retried() -> None:
    server = FakeOllama()
    client, pauses = _client(server, retries=3)
    with pytest.raises(ModelError, match=r"not found"):
        client.capabilities("gibt-es-nicht")
    assert len(server.requests) == 1 and pauses == []


@pytest.mark.parametrize(
    "answer",
    [
        response(f"{URL}/api/tags", payload={"models": [{"name": 3}]}),
        response(f"{URL}/api/tags", content=b"<html>kein JSON</html>"),
    ],
)
def test_an_unusable_answer_is_a_model_error(answer: requests.Response) -> None:
    session = FakeSession({f"{URL}/api/tags": answer})
    client = OllamaClient(URL, transport=session)
    with pytest.raises(ModelError, match=r"unbrauchbar"):
        client.info("fake-embed")


def test_loaded_lists_the_models_in_memory() -> None:
    client, _ = _client(FakeOllama(loaded=["fake-chat:latest"]))
    (running,) = client.loaded()
    assert running.name == "fake-chat:latest" and running.size_vram == 123_000_000


def test_model_stamp_asks_the_server_only_when_called() -> None:
    server = FakeOllama()
    client, _ = _client(server)
    generator = OllamaGenerator(client, "fake-chat", options=GenerationOptions(seed=3))
    stamp = model_stamp(generator, "kurzfassung-1", generator.options)
    assert server.requests == []
    assert stamp() == {
        "model": "fake-chat:latest",
        "digest": "c" * 64,
        "prompt": "kurzfassung-1",
        "options": GenerationOptions(seed=3).key(),
    }
    stamp()
    assert server.paths == ["/api/tags"]


def test_options_key_changes_with_every_option() -> None:
    base = GenerationOptions()
    keys = {
        base.key(),
        GenerationOptions(temperature=0.1).key(),
        GenerationOptions(seed=1).key(),
        GenerationOptions(num_ctx=1024).key(),
        GenerationOptions(num_predict=1).key(),
        GenerationOptions(think=True).key(),
    }
    assert len(keys) == 6 and base.key() == GenerationOptions().key()


def test_dimension_comes_from_the_model_info_of_an_embedding_model() -> None:
    client, _ = _client(FakeOllama(dimension=8))
    assert client.dimension("fake-embed") == 8
    with pytest.raises(ModelError, match=r"kein Einbettungsmodell"):
        client.dimension("fake-chat")
