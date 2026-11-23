"""Die Modellnaht: was ein Schritt von einem lokalen Modell braucht, unabhängig vom Backend.

Zwei Protokolle wie ``KeywordMatcher`` und ``PdfTextExtractor`` (docs/architecture.md, „Nähte"):
``Embedder`` macht aus Texten Vektoren, ``Generator`` aus einem Prompt einen Text. Beide nennen
``name`` und ``digest``. ``ModelUse`` ist ein Modell in einem Schritt: mit der Prompt-Version und
dem Schlüssel der Optionen ist das die Kennung, die im Stamp des Schritts steht (``Step.models``) und
den Cache adressiert (``georep.ml.cache``); dazu hält sie, wie viele Eingaben der letzte Lauf offen
ließ. Ein anderes Modell, ein neu gezogenes mit demselben Namen, ein geänderter Prompt oder ein
Teillauf machen den Schritt damit veraltet.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Protocol

import deal
import numpy as np
import numpy.typing as npt

Vectors = npt.NDArray[np.float32]


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


@dataclass(frozen=True)
class EmbeddingOptions:
    """Was außer Modell und Text eine Einbettung bestimmt: das Fenster und was mit dem Rest geschieht.

    ``num_ctx`` ist das Fenster in Token (0: was das Modell mitbringt), ``truncate`` schneidet einen
    längeren Text hinten ab; ohne ist er ein Fehler des Servers. Beides gehört in den Schlüssel:
    derselbe Text gibt mit 64 Token einen anderen Vektor als mit 512 (Review 2026-11-23, Befund 1).
    """

    num_ctx: int = 0
    truncate: bool = True

    def key(self) -> str:
        """Kurzer Hash beider Werte: Teil des Cache-Schlüssels und der Kennung im Stamp."""
        text = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(text.encode()).hexdigest()[:12]


class Embedder(Protocol):
    """Text zu Vektor. ``name`` und ``digest`` bezeichnen das Modell, ``dimension`` die Vektorlänge,
    ``options`` Fenster und Abschneiden.

    ``embed`` liefert eine Zeile je Text als float32, in der Reihenfolge der Eingabe; ein leerer
    Stapel ist eine Matrix mit null Zeilen und ``dimension`` Spalten.
    """

    @property
    def name(self) -> str: ...

    @property
    def digest(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    @property
    def options(self) -> EmbeddingOptions: ...

    def embed(self, texts: Sequence[str]) -> Vectors: ...


@dataclass(frozen=True)
class Reply:
    """Die Antwort eines Generators; ``truncated``: sie stieß an ``num_predict`` und ist unvollständig."""

    text: str
    truncated: bool = False


class Generator(Protocol):
    """Prompt zu Antwort. ``options`` ersetzt für einen Aufruf die Optionen, mit denen er gebaut ist.

    Die Antwort sagt, ob sie abgeschnitten ist (Review 2026-11-23, Befund 2): ein Text allein
    hätte eine halbe Kurzfassung als ganze in den Cache gelegt.
    """

    @property
    def name(self) -> str: ...

    @property
    def digest(self) -> str: ...

    def generate(
        self, prompt: str, *, system: str = "", options: GenerationOptions | None = None
    ) -> Reply: ...


@dataclass(frozen=True)
class Call:
    """Ein Aufruf, wie der Server ihn misst: Grundlage für Durchsatz und Hochrechnung."""

    items: int  # Texte im Aufruf (ein Stapel Einbettungen, eine Antwort)
    prompt_tokens: int
    output_tokens: int
    seconds: float  # Rechenzeit des Servers ohne das Laden des Modells
    load_seconds: float
    truncated: bool = False  # die Antwort stieß an ``num_predict``
    prompt_seconds: float = 0.0  # davon das Lesen der Eingabe
    output_seconds: float = 0.0  # davon das Schreiben der Antwort


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


class ModelStamp(Protocol):
    """Was ``Step.models`` vom Modell eines Schritts braucht: Kennung und Stamp.

    ``identity`` ist, was den Schritt veraltet macht, wenn es sich ändert (Modell, Digest,
    Prompt-Version, Optionen); ``stamp`` ist ``identity`` plus das Ergebnis des letzten Laufs
    (``limit``, ``open``, ``failed``, ``rejected``). Beide fragen den Server erst beim Aufruf.
    ``reset`` setzt das Ergebnis vor einem Lauf auf null; die Stapelläufe summieren hinein.
    """

    def identity(self) -> dict[str, str]: ...

    def stamp(self) -> dict[str, object]: ...

    def reset(self) -> None: ...


class ModelUse:
    """Ein Modell in einem Schritt: die eine Quelle für Stamp, Cache-Schlüssel und offene Eingaben.

    Der Schritt baut sie einmal (``EmbeddingUse``, ``GenerationUse``) und reicht dieselbe an
    ``Step.models`` und an ``embed_texts`` oder ``generate_texts``; so können Kennung im Stamp und
    Schlüssel im Cache nicht auseinanderlaufen. Der Stapellauf trägt mit ``record`` ein, wie viele
    Eingaben offen blieben und unter welchem ``limit``; ``stamp`` schreibt beides in den Stamp, und
    ``stamp_mismatch`` meldet einen Teillauf als „offen: n Eingaben" (Review 2026-11-23, Befund 3).
    """

    def __init__(self, model: Embedder | Generator, prompt: str, options_key: str = "") -> None:
        self.model = model
        self.prompt = prompt
        self.options_key = options_key
        self.limit = 0
        self.open = 0  # offen nach dem Lauf: wegen ``limit`` oder gescheitert (Zeit, 5xx)
        self.failed = 0  # davon gescheitert; beim nächsten Lauf zuletzt
        self.rejected = 0  # vom Modell abgewiesen: erledigt, nicht offen, aber im Status genannt

    @property
    def name(self) -> str:
        return full_name(self.model.name)

    def prompt_key(self) -> str:
        """Die Prompt-Version im Cache-Schlüssel: mit dem Schlüssel der Optionen, wo es welche gibt."""
        return f"{self.prompt}+{self.options_key}" if self.options_key else self.prompt

    def identity(self) -> dict[str, str]:
        found = {"model": self.name, "digest": self.model.digest, "prompt": self.prompt}
        return found | ({"options": self.options_key} if self.options_key else {})

    def stamp(self) -> dict[str, object]:
        return {
            **self.identity(),
            "limit": self.limit,
            "open": self.open,
            "failed": self.failed,
            "rejected": self.rejected,
        }

    def record(self, *, open: int, limit: int, failed: int = 0, rejected: int = 0) -> None:
        """Ein Stapellauf trägt ein. Mehrere im selben Schritt summieren sich (Review F5, N3);
        ``limit`` ist das größte, unter dem einer lief."""
        self.open += open
        self.failed += failed
        self.rejected += rejected
        self.limit = max(self.limit, limit)

    def reset(self) -> None:
        """Vor jedem Lauf des Schritts (``run_step``): die Zahlen gelten je Lauf, nicht je Prozess."""
        self.open = self.failed = self.rejected = self.limit = 0


class EmbeddingUse(ModelUse):
    """Ein Einbettungsmodell in einem Schritt; ``prompt`` sagt, wie der Text vorbereitet ist.

    Der Schlüssel der Optionen kommt vom Einbetter selbst (Fenster, Abschneiden), damit kein
    Schritt ihn vergessen kann.
    """

    def __init__(self, embedder: Embedder, prompt: str) -> None:
        super().__init__(embedder, prompt, embedder.options.key())
        self.embedder = embedder


class GenerationUse(ModelUse):
    """Ein Generator in einem Schritt, mit den Optionen, unter denen er rechnet."""

    def __init__(self, generator: Generator, prompt: str, options: GenerationOptions) -> None:
        super().__init__(generator, prompt, options.key())
        self.generator = generator
        self.options = options
