"""Netz und Modelle als Eingabe: Sessions, die aus einer Tabelle antworten, echte ``requests.Response``,
dazu Einbetter, Generator und ollama-Server ohne Modell (Fundament F5)."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
import requests

from georep.errors import ModelRejectedError
from georep.ml.base import EmbeddingOptions, GenerationOptions, Reply


def response(
    url: str, *, status: int = 200, content: bytes = b"", payload: object = None
) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp.url = url
    resp.reason = "OK" if status < 400 else "Error"
    resp._content = json.dumps(payload).encode() if payload is not None else content
    return resp


class FakeSession:
    """Antwortet aus ``routes`` (URL -> Response oder Exception) und zählt die Aufrufe mit Parametern."""

    def __init__(self, routes: dict[str, requests.Response | Exception]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, Any]] = []

    def get(self, url: str, *, params: Any = None, headers: Any = None) -> requests.Response:
        self.calls.append((url, params))
        answer = self.routes[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def post(self, url: str, *, data: Any = None, headers: Any = None) -> requests.Response:
        self.calls.append((url, data))
        answer = self.routes[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    @property
    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]


class SequenceSession:
    """Antwortet auf **eine** URL mit einer Folge von Antworten, eine je Aufruf.

    Für Wiederholungen: derselbe Endpunkt antwortet erst 504, dann 200. ``FakeSession`` hält je URL
    genau eine Antwort und kann das nicht. Absichtlich streng — ein Aufruf mehr, als die Folge
    hergibt, ist ein ``IndexError`` und damit ein roter Test, nicht eine stille Wiederholung der
    letzten Antwort. So steht die Zahl der erwarteten Aufrufe in der Folge selbst.
    """

    def __init__(self, url: str, answers: Sequence[requests.Response | Exception]) -> None:
        self.url = url
        self.answers = list(answers)
        self.calls: list[tuple[str, Any]] = []

    def _answer(self, url: str, payload: Any) -> requests.Response:
        self.calls.append((url, payload))
        answer = self.answers[len(self.calls) - 1]  # erschöpft: IndexError, siehe Docstring
        if isinstance(answer, Exception):
            raise answer
        return answer

    def get(self, url: str, *, params: Any = None, headers: Any = None) -> requests.Response:
        return self._answer(url, params)

    def post(self, url: str, *, data: Any = None, headers: Any = None) -> requests.Response:
        return self._answer(url, data)


# --- Fundament F5: Modelle als Eingabe -------------------------------------------------------
# Kein Test ruft je ein echtes Modell oder den ollama-Server (docs/architecture.md, „Modelle").
# Die Fakes sind deterministisch: eine Einbettung ist eine Funktion des SHA-256 ihres Texts, eine
# Antwort eine Funktion des SHA-256 von System und Prompt. Damit ist jeder Cache-Treffer prüfbar.


def fake_vector(text: str, dimension: int) -> list[float]:
    """Ein Einheitsvektor aus dem SHA-256 des Texts: gleicher Text, gleicher Vektor, auf jedem Rechner."""
    blocks = -(-dimension * 2 // 32)
    raw = b"".join(hashlib.sha256(f"{i}:{text}".encode()).digest() for i in range(blocks))
    values = [
        int.from_bytes(raw[2 * j : 2 * j + 2], "big") / 32767.5 - 1.0 for j in range(dimension)
    ]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def fake_answer(system: str, prompt: str) -> str:
    """Eine feste Antwort je (System, Prompt); die ersten zwölf Zeichen des Hashs machen sie prüfbar."""
    key = hashlib.sha256(f"{system}\x00{prompt}".encode()).hexdigest()[:12]
    return f"Kurzfassung {key}: {len(prompt)} Zeichen gelesen."


class FakeEmbedder:
    """Erfüllt ``georep.ml.base.Embedder`` ohne Modell; ``calls`` hält jeden Stapel fest."""

    def __init__(
        self,
        name: str = "fake-embed:latest",
        dimension: int = 8,
        digest: str = "e" * 64,
        options: EmbeddingOptions | None = None,
        rejects: frozenset[str] | set[str] = frozenset(),
    ) -> None:
        self.name = name
        self.dimension = dimension
        self.digest = digest
        self.options = options if options is not None else EmbeddingOptions()
        self.rejects = frozenset(rejects)
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> npt.NDArray[np.float32]:
        """Ein Stapel mit einem Text aus ``rejects`` wird ganz abgewiesen, wie vom Server (400)."""
        self.calls.append(list(texts))
        if self.rejects & set(texts):
            raise ModelRejectedError("400 input rejected")
        rows = [fake_vector(t, self.dimension) for t in texts]
        return np.asarray(rows, dtype=np.float32).reshape(len(rows), self.dimension)


class FakeGenerator:
    """Erfüllt ``georep.ml.base.Generator`` ohne Modell: die Antwort kommt aus ``fake_answer``."""

    def __init__(self, name: str = "fake-chat:latest", digest: str = "c" * 64) -> None:
        self.name = name
        self.digest = digest
        self.calls: list[tuple[str, str]] = []

    def generate(
        self, prompt: str, *, system: str = "", options: GenerationOptions | None = None
    ) -> Reply:
        """Wie ``FakeOllama``: mehr Wörter als ``num_predict`` werden abgeschnitten und markiert."""
        self.calls.append((system, prompt))
        words = fake_answer(system, prompt).split()
        limit = options.num_predict if options is not None else 0
        cut = 0 < limit < len(words)
        return Reply(" ".join(words[:limit] if cut else words), truncated=cut)


# Loopback wie der echte Server, aber ein Port ohne Dienst: ginge ein Test doch ins Netz, bekäme er
# eine abgelehnte Verbindung und nie eine Antwort. FakeOllama ist der Transport, nicht dieser Port.
FAKE_URL = "http://127.0.0.1:11999"

FAKE_MODELS: dict[str, dict[str, Any]] = {
    "fake-embed:latest": {"digest": "e" * 64, "capabilities": ["embedding"], "size": 1000},
    "fake-chat:latest": {
        "digest": "c" * 64,
        "capabilities": ["completion", "thinking"],
        "size": 2000,
    },
    "plain-chat:7b": {"digest": "d" * 64, "capabilities": ["completion"], "size": 3000},
}


class FakeOllama:
    """Ein ollama-Server als Tabelle: ``Transport`` mit deterministischen Antworten auf ``/api/*``.

    Einbettungen kommen aus ``fake_vector``, Chat-Antworten aus ``fake_answer`` (auf
    ``num_predict`` Wörter gekürzt, dann ``done_reason = "length"``). ``down`` lässt jeden Aufruf
    mit ``ConnectionError`` scheitern; ``failures`` lässt die ersten Aufrufe mit diesen Statuscodes
    antworten (für die Wiederholungen). ``requests`` hält (Pfad, Nutzlast) jedes Aufrufs fest.
    """

    def __init__(
        self,
        models: dict[str, dict[str, Any]] | None = None,
        *,
        base_url: str = FAKE_URL,
        dimension: int = 8,
        down: bool = False,
        failures: Sequence[int] = (),
        loaded: Sequence[str] = (),
        slow: Sequence[str] = (),
        rejects: Sequence[str] = (),
    ) -> None:
        self.models = dict(FAKE_MODELS if models is None else models)
        self.base_url = base_url
        self.dimension = dimension
        self.down = down
        self.failures = list(failures)
        self.loaded = list(loaded)
        self.slow = set(slow)  # Texte, bei denen /api/embed in den Lese-Timeout läuft
        self.rejects = set(rejects)  # Texte, die /api/embed mit 400 abweist
        self.requests: list[tuple[str, Any]] = []

    @property
    def paths(self) -> list[str]:
        return [path for path, _ in self.requests]

    def _path(self, url: str) -> str:
        assert url.startswith(self.base_url), url
        return url[len(self.base_url) :]

    def _gate(self, url: str) -> requests.Response | None:
        if self.down:
            raise requests.ConnectionError(f"Connection refused: {url}")
        # Die Fehlerfolge trifft die Arbeit, nicht die Probe des Clients (``/api/version``).
        if self.failures and not url.endswith("/api/version"):
            status = self.failures.pop(0)
            return response(url, status=status, payload={"error": f"Fehler {status}"})
        return None

    def get(self, url: str, *, params: Any = None, headers: Any = None) -> requests.Response:
        path = self._path(url)
        self.requests.append((path, params))
        failed = self._gate(url)
        if failed is not None:
            return failed
        if path == "/api/version":
            return response(url, payload={"version": "0.0-fake"})
        if path == "/api/tags":
            tags = [
                {
                    "name": name,
                    "model": name,
                    "digest": spec["digest"],
                    "size": spec.get("size", 0),
                    "modified_at": "2026-11-23T00:00:00Z",
                    "details": {
                        "family": "fake",
                        "parameter_size": "1B",
                        "quantization_level": "F16",
                    },
                }
                for name, spec in self.models.items()
            ]
            return response(url, payload={"models": tags})
        if path == "/api/ps":
            running = [
                {"name": n, "size_vram": 123_000_000, "expires_at": "2026-11-23T01:00:00Z"}
                for n in self.loaded
            ]
            return response(url, payload={"models": running})
        return response(url, status=404, payload={"error": "404 page not found"})

    def post(self, url: str, *, data: Any = None, headers: Any = None) -> requests.Response:
        path = self._path(url)
        payload = json.loads(data) if data else {}
        self.requests.append((path, payload))
        failed = self._gate(url)
        if failed is not None:
            return failed
        name = payload.get("model", "")
        spec = self.models.get(name) or self.models.get(f"{name}:latest")
        if spec is None:
            return response(url, status=404, payload={"error": f"model '{name}' not found"})
        if path == "/api/show":
            embeds = "embedding" in spec["capabilities"]
            info = {"fake.embedding_length": self.dimension} if embeds else {"fake.block_count": 2}
            return response(url, payload={"capabilities": spec["capabilities"], "model_info": info})
        if path == "/api/embed":
            texts = payload["input"]
            if self.slow & set(texts):
                raise requests.ReadTimeout(f"read timed out: {url}")
            if self.rejects & set(texts):
                return response(url, status=400, payload={"error": "input length exceeds context"})
            return response(
                url,
                payload={
                    "model": name,
                    "embeddings": [fake_vector(t, self.dimension) for t in texts],
                    "total_duration": 2_000_000 * len(texts) + 1_000_000,
                    "load_duration": 1_000_000,
                    "prompt_eval_count": sum(len(t.split()) for t in texts),
                },
            )
        if path == "/api/chat":
            messages = payload["messages"]
            system = next((m["content"] for m in messages if m["role"] == "system"), "")
            prompt = messages[-1]["content"]
            words = fake_answer(system, prompt).split()
            limit = payload.get("options", {}).get("num_predict", 0)
            cut = 0 < limit < len(words)
            content = " ".join(words[:limit] if cut else words)
            return response(
                url,
                payload={
                    "model": name,
                    "message": {"role": "assistant", "content": content},
                    "done": True,
                    "done_reason": "length" if cut else "stop",
                    "total_duration": 50_000_000,
                    "load_duration": 10_000_000,
                    "prompt_eval_count": len(prompt.split()) + len(system.split()),
                    "prompt_eval_duration": 10_000_000,
                    "eval_count": len(content.split()),
                    "eval_duration": 30_000_000,
                },
            )
        return response(url, status=404, payload={"error": "404 page not found"})
