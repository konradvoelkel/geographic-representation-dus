"""``ModelUse`` (F5): die Kennung eines Modells in einem Schritt und was sein letzter Lauf offen ließ."""

from __future__ import annotations

from georep.ml.base import EmbeddingOptions, EmbeddingUse, GenerationOptions, GenerationUse
from georep.ml.ollama import OllamaClient, OllamaGenerator
from tests.fakes import FAKE_URL, FakeEmbedder, FakeGenerator, FakeOllama


def test_an_embedding_use_names_model_digest_and_prompt() -> None:
    use = EmbeddingUse(FakeEmbedder(), "dok-1")
    identity = use.identity()
    assert identity["model"] == "fake-embed:latest" and identity["digest"] == "e" * 64
    assert identity["prompt"] == "dok-1"


def test_an_embedding_use_keys_on_window_and_truncation() -> None:
    """Befund 1 des Reviews: das Fenster des Einbetters fehlte in Schlüssel und Kennung."""
    uses = [
        EmbeddingUse(FakeEmbedder(options=options), "dok-1")
        for options in (
            EmbeddingOptions(num_ctx=512),
            EmbeddingOptions(num_ctx=64),
            EmbeddingOptions(num_ctx=512, truncate=False),
        )
    ]
    assert len({use.identity()["options"] for use in uses}) == 3
    assert len({use.prompt_key() for use in uses}) == 3
    assert uses[0].prompt_key() == f"dok-1+{EmbeddingOptions(num_ctx=512).key()}"


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
    assert use.stamp() == use.identity() | {"limit": 0, "open": 0, "failed": 0, "rejected": 0}
    use.record(open=3, failed=1, rejected=2, limit=2)
    assert use.stamp() == use.identity() | {"limit": 2, "open": 3, "failed": 1, "rejected": 2}


def test_the_identity_asks_the_server_only_when_called() -> None:
    server = FakeOllama()
    client = OllamaClient(FAKE_URL, transport=server)
    use = GenerationUse(OllamaGenerator(client, "fake-chat"), "kurz-1", GenerationOptions())
    assert server.requests == []
    use.identity()
    use.identity()
    assert server.paths == ["/api/version", "/api/tags"]
