"""``ModelUse`` (F5): die Kennung eines Modells in einem Schritt und was sein letzter Lauf offen ließ."""

from __future__ import annotations

from georep.ml.base import EmbeddingUse, GenerationOptions, GenerationUse
from georep.ml.ollama import OllamaClient, OllamaGenerator
from tests.fakes import FAKE_URL, FakeEmbedder, FakeGenerator, FakeOllama


def test_an_embedding_use_names_model_digest_and_prompt() -> None:
    use = EmbeddingUse(FakeEmbedder(), "dok-1")
    identity = use.identity()
    assert identity["model"] == "fake-embed:latest" and identity["digest"] == "e" * 64
    assert identity["prompt"] == "dok-1"


def test_a_generation_use_carries_the_key_of_its_options() -> None:
    options = GenerationOptions(seed=3)
    use = GenerationUse(FakeGenerator(), "kurz-1", options)
    assert use.identity() == {
        "model": "fake-chat:latest",
        "digest": "c" * 64,
        "prompt": "kurz-1",
        "options": options.key(),
    }
    assert use.prompt_key() == f"kurz-1+{options.key()}"


def test_the_stamp_adds_limit_and_what_stayed_open() -> None:
    use = GenerationUse(FakeGenerator(), "kurz-1", GenerationOptions())
    assert use.stamp() == use.identity() | {"limit": 0, "open": 0}
    use.record(open=3, limit=2)
    assert use.stamp() == use.identity() | {"limit": 2, "open": 3}


def test_the_identity_asks_the_server_only_when_called() -> None:
    server = FakeOllama()
    client = OllamaClient(FAKE_URL, transport=server)
    use = GenerationUse(OllamaGenerator(client, "fake-chat"), "kurz-1", GenerationOptions())
    assert server.requests == []
    use.identity()
    use.identity()
    assert server.paths == ["/api/tags"]
