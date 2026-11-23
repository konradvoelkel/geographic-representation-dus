"""Das ollama-Backend der Modellnaht (F5) gegen einen Server als Tabelle, nie gegen den echten."""

from __future__ import annotations

import numpy as np
import pytest
import requests

from georep.errors import ModelError, ModelRejectedError, ModelUnreachableError
from georep.ml.base import (
    Embedder,
    EmbeddingOptions,
    GenerationOptions,
    Generator,
    Reply,
    full_name,
)
from georep.ml.ollama import OllamaClient, OllamaEmbedder, OllamaGenerator
from tests.fakes import (
    FAKE_URL,
    FakeOllama,
    FakeSession,
    SequenceSession,
    fake_answer,
    fake_vector,
    response,
)

URL = FAKE_URL


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
    embedder: Embedder = OllamaEmbedder(
        client, "fake-embed", dimension=8, options=EmbeddingOptions(num_ctx=512)
    )
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


def test_embedder_without_truncation_says_so_and_leaves_the_window_to_the_model() -> None:
    server = FakeOllama(dimension=8)
    client, _ = _client(server)
    options = EmbeddingOptions(truncate=False)
    OllamaEmbedder(client, "fake-embed", dimension=8, options=options).embed(["eins"])
    _, payload = server.requests[-1]
    assert payload["truncate"] is False and "options" not in payload


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
    assert answer == Reply(fake_answer("Du fasst zusammen.", "Fasse zusammen: Text"))
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


def test_generator_says_when_an_answer_was_cut() -> None:
    """Befund 2 des Reviews: die Antwort an ``num_predict`` kam als vollständiger Text heraus."""
    client, _ = _client(FakeOllama())
    generator = OllamaGenerator(client, "fake-chat", options=GenerationOptions(num_predict=2))
    reply = generator.generate("ein langer Prompt")
    assert reply.truncated and len(reply.text.split()) == 2
    assert generator.calls[-1].truncated and generator.calls[-1].output_tokens == 2
    assert not generator.generate("x", options=GenerationOptions(num_predict=50)).truncated


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
    assert server.paths == ["/api/version", "/api/tags", "/api/tags", "/api/tags"]
    assert pauses == [1.0, 2.0]


def test_a_client_error_is_not_retried() -> None:
    server = FakeOllama()
    client, pauses = _client(server, retries=3)
    with pytest.raises(ModelError, match=r"not found"):
        client.capabilities("gibt-es-nicht")
    assert server.paths == ["/api/version", "/api/show"] and pauses == []


@pytest.mark.parametrize(
    "answer",
    [
        response(f"{URL}/api/tags", payload={"models": [{"name": 3}]}),
        response(f"{URL}/api/tags", content=b"<html>kein JSON</html>"),
    ],
)
def test_an_unusable_answer_is_a_model_error(answer: requests.Response) -> None:
    version = response(f"{URL}/api/version", payload={"version": "0.0-fake"})
    session = FakeSession({f"{URL}/api/version": version, f"{URL}/api/tags": answer})
    client = OllamaClient(URL, transport=session)
    with pytest.raises(ModelError, match=r"unbrauchbar"):
        client.info("fake-embed")


def test_loaded_lists_the_models_in_memory() -> None:
    client, _ = _client(FakeOllama(loaded=["fake-chat:latest"]))
    (running,) = client.loaded()
    assert running.name == "fake-chat:latest" and running.size_vram == 123_000_000


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


def test_a_read_timeout_is_not_retried_and_says_what_it_is() -> None:
    """Befund 4 des Reviews (Probe 3): ein Lese-Timeout lief dreimal und hieß „nicht erreichbar"."""
    version = response(f"{URL}/api/version", payload={"version": "0.0-fake"})
    session = SequenceSession(f"{URL}/api/chat", [version, requests.ReadTimeout("read timed out")])
    pauses: list[float] = []
    client = OllamaClient(URL, transport=session, timeout_s=300.0, sleep=pauses.append)
    with pytest.raises(ModelError, match=r"Zeitüberschreitung nach 300 s") as caught:
        client.chat({"model": "fake-chat:latest"})
    assert len(session.calls) == 2 and pauses == []
    # Review F5, N4: der Server antwortete auf die Probe, er ist erreichbar; die Zeit lief bei
    # diesem Text ab. Darum kein ModelUnreachableError, der den ganzen Lauf abbräche.
    assert type(caught.value) is ModelError


def test_a_server_that_goes_away_mid_run_is_retried_then_unreachable() -> None:
    server = FakeOllama()
    client, pauses = _client(server, retries=2, backoff_s=1.0)
    client.version()
    server.down = True
    with pytest.raises(ModelUnreachableError, match=r"nicht erreichbar"):
        client.info("fake-embed")
    assert server.paths == ["/api/version", "/api/tags", "/api/tags", "/api/tags"]
    assert pauses == [1.0, 2.0]


def test_a_missing_server_is_asked_once_and_never_waited_for() -> None:
    """Befund 5 des Reviews (Probe 4): drei Modellschritte warteten je 6 s auf denselben Server."""
    server = FakeOllama(down=True)
    client, pauses = _client(server, retries=2, backoff_s=1.0)
    embedder = OllamaEmbedder(client, "fake-embed", dimension=8)
    for ask in (lambda: client.info("fake-embed"), lambda: embedder.embed(["a"]), client.models):
        with pytest.raises(ModelUnreachableError, match=r"nicht erreichbar"):
            ask()
    assert server.paths == ["/api/version"] and pauses == []


def test_another_request_error_is_a_model_error_at_once() -> None:
    version = response(f"{URL}/api/version", payload={"version": "0.0-fake"})
    session = SequenceSession(f"{URL}/api/tags", [version, requests.TooManyRedirects("zu viele")])
    client = OllamaClient(URL, transport=session)
    with pytest.raises(ModelError, match=r"zu viele") as caught:
        client.info("fake-embed")
    assert type(caught.value) is ModelError and len(session.calls) == 2


def test_the_client_refuses_a_server_elsewhere_unless_allowed() -> None:
    """Befund 11 des Reviews: auch ein Client von Hand schickt nichts an einen fremden Rechner."""
    with pytest.raises(ModelError, match=r"kein Server auf diesem Rechner.*allow_remote"):
        OllamaClient("http://anderer-rechner:11434", transport=FakeOllama())
    assert OllamaClient("http://anderer-rechner:11434", allow_remote=True).allow_remote


def test_the_session_ignores_proxies_and_netrc_from_the_environment() -> None:
    """Ein ``HTTP_PROXY`` aus der Umgebung leitete sonst auch localhost über einen Proxy."""
    assert OllamaClient(URL).transport.trust_env is False  # type: ignore[attr-defined]


def test_a_rejected_input_is_its_own_error_and_a_missing_model_is_not() -> None:
    """Review F5, N1: nur eine Abweisung der Eingabe (4xx außer 404) merkt sich der Stapellauf."""
    server = FakeOllama(rejects=["zu lang"])
    client, _ = _client(server)
    embedder = OllamaEmbedder(client, "fake-embed", dimension=8)
    with pytest.raises(ModelRejectedError, match=r"400.*exceeds context"):
        embedder.embed(["zu lang"])
    with pytest.raises(ModelError, match=r"not found") as caught:
        client.capabilities("gibt-es-nicht")
    assert type(caught.value) is ModelError


@pytest.mark.parametrize(
    ("status", "kind", "tries"),
    [
        (400, ModelRejectedError, 1),
        (413, ModelRejectedError, 1),
        (422, ModelRejectedError, 1),
        (401, ModelUnreachableError, 1),
        (403, ModelUnreachableError, 1),
        (404, ModelError, 1),
        (408, ModelError, 3),
        (409, ModelError, 3),
        (425, ModelError, 3),
        (429, ModelError, 3),
        (500, ModelError, 3),
        (503, ModelError, 3),
    ],
)
def test_each_status_has_its_meaning(status: int, kind: type[ModelError], tries: int) -> None:
    """Review F5, vierte Runde, M3: nur 400, 413, 422 sind eine Abweisung der Eingabe.

    408, 409, 425 sind vorübergehend wie 429 (wiederholt, dann „gescheitert"); 401 und 403 sind
    die Konfiguration, kein Fehler des Texts: der Lauf bricht ab und merkt sich nichts.
    """
    version = response(f"{URL}/api/version", payload={"version": "0.0-fake"})
    answer = response(f"{URL}/api/embed", status=status, payload={"error": f"e{status}"})
    session = SequenceSession(f"{URL}/api/embed", [version, *[answer] * tries])
    client = OllamaClient(URL, transport=session, retries=2, sleep=lambda s: None)
    with pytest.raises(ModelError) as caught:
        client.embed({"model": "fake-embed:latest", "input": ["t"]})
    assert type(caught.value) is kind and len(session.calls) == 1 + tries
