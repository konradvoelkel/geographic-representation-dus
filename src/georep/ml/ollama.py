"""Das Backend der Modellnaht: ein ollama-Server über HTTP, ohne die Python-Bibliothek von ollama.

Sechs Endpunkte genügen: ``/api/version`` (läuft der Server?), ``/api/tags`` (Modelle mit Digest),
``/api/show`` (Fähigkeiten: ``embedding``, ``completion``, ``thinking``), ``/api/ps`` (was im
Speicher liegt), ``/api/embed`` und ``/api/chat``. Gesprochen wird über das ``Transport``-Protokoll
aus ``georep.http``, also mit derselben Testnaht wie jede Quelle; die Antworten prüft pydantic an
der Grenze, wie OParl in ``georep.oparl``. Jeder Fehler ist ein ``ModelError``: ein fehlendes
Modell, eine abgewiesene Anfrage, eine unbrauchbare Antwort; ein Server, der nicht erreichbar ist
oder nicht innerhalb von ``timeout_s`` antwortet, ist die Unterklasse ``ModelUnreachableError``.
Wiederholt werden, mit Backoff und begrenzt, eine abgelehnte Verbindung und 429 und 5xx; ein
Lese-Timeout nicht (er käme beim selben Text wieder), ein 4xx auch nicht.
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

from georep.errors import ModelError, ModelUnreachableError
from georep.http import TimeoutSession, Transport
from georep.ml.base import (
    Call,
    EmbeddingOptions,
    GenerationOptions,
    ModelInfo,
    Reply,
    Vectors,
    full_name,
)
from georep.settings import Ml

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
    model_info: dict[str, Any] = Field(default_factory=dict)


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
    prompt_eval_duration: int = 0
    eval_count: int = 0
    eval_duration: int = 0


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
        # Befund 5 des Reviews: ``None`` ungeprüft, sonst das Ergebnis der einen Probe. Ein
        # fehlender Server wird einmal gefragt, ohne Wiederholung, und dann nie wieder; einer, der
        # einmal lief, wird bei einer abgelehnten Verbindung wie bisher wiederholt.
        self._running: bool | None = None
        self._shows: dict[str, _Show] = {}

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
        if path != "/api/version":
            self._require_server()
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
            except requests.ConnectionError as error:
                # Auch ConnectTimeout: der Server nahm die Verbindung nicht an. Nur das wird
                # wiederholt, ein Lese-Timeout nicht (Review 2026-11-23, Befund 4).
                problem = f"nicht erreichbar ({error}); läuft `ollama serve`?"
                continue
            except requests.Timeout as error:
                raise ModelUnreachableError(
                    f"{url}: Zeitüberschreitung nach {self.timeout_s:g} s (ml.timeout_s)"
                ) from error
            except requests.RequestException as error:
                raise ModelError(f"{url}: {error}") from error
            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError as error:
                    raise ModelError(f"{url}: Antwort unbrauchbar, kein JSON") from error
            problem = f"antwortete {resp.status_code}: {_error_text(resp)}"
            if resp.status_code not in RETRY_STATUSES:
                raise ModelError(f"{url} {problem}")
        if problem.startswith("nicht erreichbar"):
            raise ModelUnreachableError(f"ollama unter {self.base_url} {problem}")
        raise ModelError(f"ollama unter {self.base_url} {problem}")

    @staticmethod
    def _parse[R: _Reply](kind: type[R], data: object, path: str) -> R:
        try:
            return kind.model_validate(data)
        except ValidationError as error:
            raise ModelError(f"{path}: Antwort unbrauchbar: {error}") from error

    def _require_server(self) -> None:
        """Die eine Probe je Client; ohne Server ist jeder weitere Aufruf sofort ein Fehler."""
        if self._running is None:
            try:
                self.version()
            except ModelUnreachableError:
                self._running = False
                raise
        if self._running is False:
            raise ModelUnreachableError(
                f"ollama unter {self.base_url} nicht erreichbar; läuft `ollama serve`?"
            )

    @deal.raises(ModelError, ModelUnreachableError)
    def version(self) -> str:
        """Die Version des Servers. Eine Probe, darum ohne Wiederholung: fehlt er, sofort Bescheid."""
        data = self._call("GET", "/api/version", retries=0)
        found = self._parse(_Version, data, "/api/version").version
        self._running = True
        return found

    @deal.raises(ModelError, ModelUnreachableError)
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

    @deal.raises(ModelError, ModelUnreachableError)
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

    def _show(self, name: str) -> _Show:
        wanted = full_name(name)
        if wanted not in self._shows:
            data = self._call("POST", "/api/show", {"model": wanted})
            self._shows[wanted] = self._parse(_Show, data, "/api/show")
        return self._shows[wanted]

    @deal.raises(ModelError, ModelUnreachableError)
    def capabilities(self, name: str) -> tuple[str, ...]:
        """Was ein Modell kann (``embedding``, ``completion``, ``thinking`` …), aus ``/api/show``."""
        return self._show(name).capabilities

    @deal.raises(ModelError, ModelUnreachableError)
    def dimension(self, name: str) -> int:
        """Die Vektorlänge eines Einbettungsmodells (``<familie>.embedding_length`` in ``/api/show``)."""
        show = self._show(name)
        lengths = [v for k, v in show.model_info.items() if k.endswith(".embedding_length")]
        if "embedding" not in show.capabilities or len(lengths) != 1:
            raise ModelError(f"{full_name(name)} ist kein Einbettungsmodell mit einer Vektorlänge")
        return int(lengths[0])

    @deal.raises(ModelError, ModelUnreachableError)
    def loaded(self) -> list[Running]:
        """Die Modelle im Speicher des Servers; eine Probe ohne Wiederholung."""
        data = self._call("GET", "/api/ps", retries=0)
        return self._parse(_Ps, data, "/api/ps").models

    @deal.raises(ModelError, ModelUnreachableError)
    def embed(self, payload: dict[str, Any]) -> _Embed:
        return self._parse(_Embed, self._call("POST", "/api/embed", payload), "/api/embed")

    @deal.raises(ModelError, ModelUnreachableError)
    def chat(self, payload: dict[str, Any]) -> _Chat:
        return self._parse(_Chat, self._call("POST", "/api/chat", payload), "/api/chat")


class OllamaEmbedder:
    """``Embedder`` über ``/api/embed``. Zu lange Texte schneidet der Server ab (``truncate``).

    ``num_ctx`` ist das Fenster in Token; 0 heißt: was das Modell mitbringt
    (``nomic-embed-text-v2-moe`` liest 512 Token, ein längerer Text wird hinten abgeschnitten).
    ``calls`` hält je Aufruf Token und Sekunden fest.
    """

    def __init__(
        self,
        client: OllamaClient,
        model: str,
        *,
        dimension: int,
        options: EmbeddingOptions | None = None,
    ) -> None:
        self.client = client
        self.name = full_name(model)
        self.dimension = dimension
        self.options = options if options is not None else EmbeddingOptions()
        self.calls: list[Call] = []

    @property
    def digest(self) -> str:
        return self.client.info(self.name).digest

    @deal.raises(ModelError, ModelUnreachableError)
    @deal.ensure(lambda self, texts, result: result.shape == (len(texts), self.dimension))
    def embed(self, texts: Sequence[str]) -> Vectors:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        payload: dict[str, Any] = {
            "model": self.name,
            "input": list(texts),
            "truncate": self.options.truncate,
        }
        if self.options.num_ctx:
            payload["options"] = {"num_ctx": self.options.num_ctx}
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
                prompt_seconds=(reply.total_duration - reply.load_duration) / NANOSECONDS,
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

    @deal.raises(ModelError, ModelUnreachableError)
    def generate(
        self, prompt: str, *, system: str = "", options: GenerationOptions | None = None
    ) -> Reply:
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
                prompt_seconds=reply.prompt_eval_duration / NANOSECONDS,
                output_seconds=reply.eval_duration / NANOSECONDS,
            )
        )
        return Reply(reply.message.content, truncated=reply.done_reason == "length")


# --- aus den Settings -----------------------------------------------------------------------
# Die einzige Stelle, an der ``[ml]`` zu Objekten wird; ein Schritt in ``build_steps`` baut so
# Client und Modell, ohne mit dem Server zu sprechen (das tut erst ``Step.models`` oder ``run``).


_SHARED: dict[str, OllamaClient] = {}


def client_from_settings(ml: Ml, *, transport: Transport | None = None) -> OllamaClient:
    """Der Client aus ``[ml]``. Ohne ``transport`` ist es je Settings einer für den ganzen Prozess:
    alle Modellschritte teilen die eine Probe des Servers und die Tags (Befund 5 des Reviews)."""
    if transport is None and ml.model_dump_json() in _SHARED:
        return _SHARED[ml.model_dump_json()]
    client = OllamaClient(
        ml.base_url,
        transport=transport,
        timeout_s=ml.timeout_s,
        retries=ml.retries,
        backoff_s=ml.backoff_s,
        keep_alive=ml.keep_alive,
    )
    if transport is None:
        _SHARED[ml.model_dump_json()] = client
    return client


def generation_options(ml: Ml) -> GenerationOptions:
    gen = ml.generation
    return GenerationOptions(
        temperature=gen.temperature,
        seed=gen.seed,
        num_ctx=gen.num_ctx,
        num_predict=gen.num_predict,
        think=gen.think,
    )


def embedder_from_settings(ml: Ml, client: OllamaClient) -> OllamaEmbedder:
    emb = ml.embedding
    options = EmbeddingOptions(num_ctx=emb.num_ctx, truncate=emb.truncate)
    return OllamaEmbedder(client, emb.model, dimension=emb.dimension, options=options)


def generator_from_settings(
    ml: Ml, client: OllamaClient, *, model: str | None = None
) -> OllamaGenerator:
    """Der Generator aus ``[ml.generation]``; ``model`` nimmt ein anderes Modell mit denselben Optionen."""
    chosen = model if model is not None else ml.generation.model
    return OllamaGenerator(client, chosen, options=generation_options(ml))
