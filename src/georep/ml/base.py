"""Die Modellnaht: was ein Schritt von einem lokalen Modell braucht, unabhängig vom Backend.

Zwei Protokolle wie ``KeywordMatcher`` und ``PdfTextExtractor`` (docs/architecture.md, „Nähte"):
``Embedder`` macht aus Texten Vektoren, ``Generator`` aus einem Prompt einen Text. Beide nennen
``name`` und ``digest``; zusammen mit einer Prompt-Version ist das die Kennung, die im Stamp eines
Schritts steht (``model_stamp``) und den Cache adressiert (``georep.ml.cache``). Ein anderes Modell,
ein neu gezogenes mit demselben Namen oder ein geänderter Prompt machen den Schritt damit veraltet.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Protocol

import deal
import numpy as np
import numpy.typing as npt

Vectors = npt.NDArray[np.float32]
ModelStamp = Callable[[], dict[str, str]]


@dataclass(frozen=True)
class GenerationOptions:
    """Die Optionen eines Generators, die das Ergebnis bestimmen; der Standard ist deterministisch.

    ``temperature = 0`` und ein fester ``seed`` machen eine Antwort je Rechner und Modell
    reproduzierbar (nicht über Rechner hinweg: die Rechenwege der GPU unterscheiden sich).
    ``num_ctx`` ist das Kontextfenster in Token, ``num_predict`` die Höchstzahl der Ausgabetoken,
    ``think`` schaltet die Denkspur von Modellen wie qwen3.6 ein; aus kostet sie keine Token und
    steht nicht in der Antwort.
    """

    temperature: float = 0.0
    seed: int = 0
    num_ctx: int = 8192
    num_predict: int = 512
    think: bool = False

    def payload(self) -> dict[str, float | int]:
        """Die ``options`` einer ollama-Anfrage; ``think`` gehört nicht hinein, sondern daneben."""
        return {
            "temperature": self.temperature,
            "seed": self.seed,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
        }

    def key(self) -> str:
        """Kurzer Hash aller Optionen: Teil des Cache-Schlüssels und der Kennung im Stamp."""
        text = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(text.encode()).hexdigest()[:12]


class Embedder(Protocol):
    """Text zu Vektor. ``name`` und ``digest`` bezeichnen das Modell, ``dimension`` die Vektorlänge.

    ``embed`` liefert eine Zeile je Text als float32, in der Reihenfolge der Eingabe; ein leerer
    Stapel ist eine Matrix mit null Zeilen und ``dimension`` Spalten.
    """

    @property
    def name(self) -> str: ...

    @property
    def digest(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> Vectors: ...


class Generator(Protocol):
    """Prompt zu Text. ``options`` ersetzt für einen Aufruf die Optionen, mit denen er gebaut ist."""

    @property
    def name(self) -> str: ...

    @property
    def digest(self) -> str: ...

    def generate(
        self, prompt: str, *, system: str = "", options: GenerationOptions | None = None
    ) -> str: ...


@dataclass(frozen=True)
class Call:
    """Ein Aufruf, wie der Server ihn misst: Grundlage für Durchsatz und Hochrechnung."""

    items: int  # Texte im Aufruf (ein Stapel Einbettungen, eine Antwort)
    prompt_tokens: int
    output_tokens: int
    seconds: float  # Rechenzeit des Servers ohne das Laden des Modells
    load_seconds: float
    truncated: bool = False  # die Antwort stieß an ``num_predict``


@dataclass(frozen=True)
class ModelInfo:
    """Ein Modell auf dem Server; ``digest`` ist der SHA-256 seines Manifests."""

    name: str
    digest: str
    size: int
    family: str = ""
    parameter_size: str = ""
    quantization: str = ""
    modified: str = ""


@deal.pure
@deal.ensure(lambda name, result: result.startswith(name))
@deal.ensure(lambda name, result: ":" in result.rsplit("/", 1)[-1])
def full_name(name: str) -> str:
    """Der Name, unter dem ollama ein Modell führt: ohne Tag im letzten Pfadstück heißt es ``:latest``.

    Der Doppelpunkt eines Registry-Ports (``host:5000/modell``) ist kein Tag, darum zählt nur das
    Stück hinter dem letzten Schrägstrich.
    """
    last = name.rsplit("/", 1)[-1]
    return name if ":" in last else f"{name}:latest"


def model_stamp(
    model: Embedder | Generator, prompt: str, options: GenerationOptions | None = None
) -> ModelStamp:
    """Die Kennung für ``Step.models``: Modellname, Digest, Prompt-Version, bei Generatoren die Optionen.

    Erst der Aufruf fragt den Digest ab (beim ollama-Backend über ``/api/tags``), also erst, wenn
    der Schritt mit ``--models`` laufen darf; ``georep steps`` und ein Lauf ohne Schalter fragen
    nichts.
    """

    def stamp() -> dict[str, str]:
        found = {"model": model.name, "digest": model.digest, "prompt": prompt}
        return found | ({"options": options.key()} if options is not None else {})

    return stamp
