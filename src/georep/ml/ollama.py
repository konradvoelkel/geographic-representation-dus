"""Das Backend der Modellnaht: ein ollama-Server über HTTP, ohne die Python-Bibliothek von ollama.

Sechs Endpunkte genügen: ``/api/version`` (läuft der Server?), ``/api/tags`` (Modelle mit Digest),
``/api/show`` (Fähigkeiten: ``embedding``, ``completion``, ``thinking``), ``/api/ps`` (was im
Speicher liegt), ``/api/embed`` und ``/api/chat``. Gesprochen wird über das ``Transport``-Protokoll
aus ``georep.http``, also mit derselben Testnaht wie jede Quelle; die Antworten prüft pydantic an
der Grenze, wie OParl in ``georep.oparl``. Jeder Fehler ist ein ``ModelError``: ein nicht
erreichbarer Server, ein fehlendes Modell, eine unbrauchbare Antwort. 429 und 5xx werden mit
Backoff wiederholt, begrenzt; ein 4xx sagt, dass die Anfrage falsch ist, und kommt sofort heraus.
Die Retry-Regel der Session aus ``make_session`` hilft hier nicht: sie wiederholt nur GET und HEAD,
und ``embed`` wie ``chat`` sind POST (docs/decisions.md, „Modelle lokal über ollama").
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from typing import Any, Literal

import deal
import numpy as np
import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from georep.errors import ModelError
from georep.http import TimeoutSession, Transport
from georep.ml.base import Call, GenerationOptions, ModelInfo, Vectors, full_name

DEFAULT_URL = "http://localhost:11434"
RETRY_STATUSES = (429, 500, 502, 503, 504)
NANOSECONDS = 1e9
_JSON = {"Content-Type": "application/json"}


class _Reply(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class _Version(_Reply):
    version: str


class _TagDetails(_Reply):
    family: str = ""
    parameter_size: str = ""
    quantization_level: str = ""


class _Tag(_Reply):
    name: str
    digest: str
    size: int = 0
    modified_at: str = ""
    details: _TagDetails = _TagDetails()


class _Tags(_Reply):
    models: list[_Tag] = Field(default_factory=list)


class _Show(_Reply):
    capabilities: tuple[str, ...] = ()


class Running(_Reply):
    """Ein Modell im Speicher des Servers (``/api/ps``): Größe im Grafikspeicher, Ablauf."""

    name: str
    size_vram: int = 0
    expires_at: str = ""


class _Ps(_Reply):
    models: list[Running] = Field(default_factory=list)


class _Embed(_Reply):
    embeddings: list[list[float]]
    total_duration: int = 0
    load_duration: int = 0
    prompt_eval_count: int = 0


class _Message(_Reply):
    content: str = ""


class _Chat(_Reply):
    message: _Message
    done_reason: str = ""
    total_duration: int = 0
    load_duration: int = 0
    prompt_eval_count: int = 0
    eval_count: int = 0


def _error_text(resp: requests.Response) -> str:
    """Die Fehlermeldung des Servers (``{"error": …}``), sonst der Anfang des Körpers."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    return str(body.get("error", body)) if isinstance(body, dict) else str(body)[:200]


class OllamaClient:
    """Die HTTP-Seite: eine Anfrage, begrenzte Wiederholungen, geprüfte Antwort, ``ModelError``.

    ``transport`` ist die Testnaht; ohne Angabe entsteht beim ersten Aufruf eine Session mit
    ``timeout_s`` je Anfrage. Der Konstruktor spricht nicht mit dem Server: ``build_steps`` darf
    einen Client bauen, ohne dass ein Server läuft. Tags und Fähigkeiten werden je Prozess einmal
    gefragt; ein Lauf, der ein Modell neu zieht, braucht einen neuen Client.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        *,
        transport: Transport | None = None,
        timeout_s: float = 300.0,
        retries: int = 2,
        backoff_s: float = 2.0,
        keep_alive: str = "10m",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_s = backoff_s
        self.keep_alive = keep_alive
        self.sleep = sleep
        self._transport = transport
        self._infos: dict[str, ModelInfo] = {}
        self._capabilities: dict[str, tuple[str, ...]] = {}

    @property
    def transport(self) -> Transport:
        if self._transport is None:
            self._transport = TimeoutSession(self.timeout_s)
        return self._transport

    def _call(
        self,
        method: Literal["GET", "POST"],
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        retries: int | None = None,
    ) -> object:
        url = self.base_url + path
        attempts = (self.retries if retries is None else retries) + 1
        problem = ""
        for attempt in range(attempts):
            if attempt:
                self.sleep(self.backoff_s * 2 ** (attempt - 1))
            try:
                if method == "GET":
                    resp = self.transport.get(url)
                else:
                    resp = self.transport.post(url, data=json.dumps(payload), headers=_JSON)
            except requests.RequestException as error:
                problem = f"nicht erreichbar ({error}); läuft `ollama serve`?"
                continue
            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError as error:
                    raise ModelError(f"{url}: Antwort unbrauchbar, kein JSON") from error
            problem = f"antwortete {resp.status_code}: {_error_text(resp)}"
            if resp.status_code not in RETRY_STATUSES:
                raise ModelError(f"{url} {problem}")
        raise ModelError(f"ollama unter {self.base_url} {problem}")

    @staticmethod
    def _parse[R: _Reply](kind: type[R], data: object, path: str) -> R:
        try:
            return kind.model_validate(data)
        except ValidationError as error:
            raise ModelError(f"{path}: Antwort unbrauchbar: {error}") from error

    @deal.raises(ModelError)
    def version(self) -> str:
        """Die Version des Servers. Eine Probe, darum ohne Wiederholung: fehlt er, sofort Bescheid."""
        data = self._call("GET", "/api/version", retries=0)
        return self._parse(_Version, data, "/api/version").version

    @deal.raises(ModelError)
    def models(self) -> list[ModelInfo]:
        """Alle Modelle des Servers mit Digest, nach Namen sortiert; füllt den Speicher für ``info``."""
        tags = self._parse(_Tags, self._call("GET", "/api/tags"), "/api/tags")
        found = [
            ModelInfo(
                name=tag.name,
                digest=tag.digest,
                size=tag.size,
                family=tag.details.family,
                parameter_size=tag.details.parameter_size,
                quantization=tag.details.quantization_level,
                modified=tag.modified_at,
            )
            for tag in tags.models
        ]
        self._infos = {info.name: info for info in found}
        return sorted(found, key=lambda info: info.name)

    @deal.raises(ModelError)
    def info(self, name: str) -> ModelInfo:
        """Ein Modell mit Digest; fehlt es, sagt der Fehler, wie man es holt."""
        wanted = full_name(name)
        if wanted not in self._infos:
            self.models()
        if wanted not in self._infos:
            raise ModelError(
                f"Modell {wanted} fehlt auf dem Server unter {self.base_url}; `ollama pull {name}`"
            )
        return self._infos[wanted]

    @deal.raises(ModelError)
    def capabilities(self, name: str) -> tuple[str, ...]:
        """Was ein Modell kann (``embedding``, ``completion``, ``thinking`` …), aus ``/api/show``."""
        wanted = full_name(name)
        if wanted not in self._capabilities:
            data = self._call("POST", "/api/show", {"model": wanted})
            self._capabilities[wanted] = self._parse(_Show, data, "/api/show").capabilities
        return self._capabilities[wanted]

    @deal.raises(ModelError)
    def loaded(self) -> list[Running]:
        """Die Modelle im Speicher des Servers; eine Probe ohne Wiederholung."""
        data = self._call("GET", "/api/ps", retries=0)
        return self._parse(_Ps, data, "/api/ps").models

    @deal.raises(ModelError)
    def embed(self, payload: dict[str, Any]) -> _Embed:
        return self._parse(_Embed, self._call("POST", "/api/embed", payload), "/api/embed")

    @deal.raises(ModelError)
    def chat(self, payload: dict[str, Any]) -> _Chat:
        return self._parse(_Chat, self._call("POST", "/api/chat", payload), "/api/chat")


class OllamaEmbedder:
    """``Embedder`` über ``/api/embed``. Zu lange Texte schneidet der Server ab (``truncate``).

    ``num_ctx`` ist das Fenster in Token; 0 heißt: was das Modell mitbringt
    (``nomic-embed-text-v2-moe`` liest 512 Token, ein längerer Text wird hinten abgeschnitten).
    ``calls`` hält je Aufruf Token und Sekunden fest.
    """

    def __init__(
        self, client: OllamaClient, model: str, *, dimension: int, num_ctx: int = 0
    ) -> None:
        self.client = client
        self.name = full_name(model)
        self.dimension = dimension
        self.num_ctx = num_ctx
        self.calls: list[Call] = []

    @property
    def digest(self) -> str:
        return self.client.info(self.name).digest

    @deal.raises(ModelError)
    @deal.ensure(lambda self, texts, result: result.shape == (len(texts), self.dimension))
    def embed(self, texts: Sequence[str]) -> Vectors:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        payload: dict[str, Any] = {"model": self.name, "input": list(texts), "truncate": True}
        if self.num_ctx:
            payload["options"] = {"num_ctx": self.num_ctx}
        payload["keep_alive"] = self.client.keep_alive
        reply = self.client.embed(payload)
        if len(reply.embeddings) != len(texts):
            raise ModelError(
                f"{self.name}: {len(reply.embeddings)} Einbettungen für {len(texts)} Texte"
            )
        wrong = {len(row) for row in reply.embeddings} - {self.dimension}
        if wrong:
            raise ModelError(f"{self.name}: Dimension {min(wrong)} statt {self.dimension}")
        self.calls.append(
            Call(
                items=len(texts),
                prompt_tokens=reply.prompt_eval_count,
                output_tokens=0,
                seconds=(reply.total_duration - reply.load_duration) / NANOSECONDS,
                load_seconds=reply.load_duration / NANOSECONDS,
            )
        )
        return np.asarray(reply.embeddings, dtype=np.float32)


class OllamaGenerator:
    """``Generator`` über ``/api/chat``: optional eine Systemnachricht, dann der Prompt.

    ``think`` geht nur an Modelle mit der Fähigkeit ``thinking``; für alle anderen bleibt es aus der
    Anfrage, und ``think = true`` ist dort ein Fehler statt einer still ignorierten Option.
    """

    def __init__(
        self, client: OllamaClient, model: str, *, options: GenerationOptions | None = None
    ) -> None:
        self.client = client
        self.name = full_name(model)
        self.options = options if options is not None else GenerationOptions()
        self.calls: list[Call] = []

    @property
    def digest(self) -> str:
        return self.client.info(self.name).digest

    @deal.raises(ModelError)
    def generate(
        self, prompt: str, *, system: str = "", options: GenerationOptions | None = None
    ) -> str:
        chosen = options if options is not None else self.options
        messages = [{"role": "system", "content": system}] if system else []
        payload: dict[str, Any] = {
            "model": self.name,
            "messages": [*messages, {"role": "user", "content": prompt}],
            "stream": False,
            "options": chosen.payload(),
            "keep_alive": self.client.keep_alive,
        }
        if "thinking" in self.client.capabilities(self.name):
            payload["think"] = chosen.think
        elif chosen.think:
            raise ModelError(f"{self.name} kann nicht denken; ml.generation.think = false")
        reply = self.client.chat(payload)
        self.calls.append(
            Call(
                items=1,
                prompt_tokens=reply.prompt_eval_count,
                output_tokens=reply.eval_count,
                seconds=(reply.total_duration - reply.load_duration) / NANOSECONDS,
                load_seconds=reply.load_duration / NANOSECONDS,
                truncated=reply.done_reason == "length",
            )
        )
        return reply.message.content
