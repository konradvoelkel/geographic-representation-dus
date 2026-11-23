"""Der Stapellauf eines Modells über viele Eingaben: fortsetzbar, begrenzbar, mit Hochrechnung.

``run_batch`` rechnet nur, was unter dem Schlüssel noch nicht im Cache liegt, jede verschiedene
Eingabe einmal, in Stapeln zu ``batch_size``; jeder Stapel ist eine Transaktion. ``limit`` begrenzt
die neuen Eingaben eines Laufs (``georep run --models --limit N``), und ein Abbruch, auch mit
Strg-C, verliert höchstens den laufenden Stapel: der nächste Lauf fängt dort an. Nach jedem Stapel
geht ein ``Progress`` an den Aufrufer, mit der Restzeit aus dem bisherigen Tempo dieses Laufs.

``embed_texts`` und ``generate_texts`` sind die beiden Wege für Schritte: sie bilden den Schlüssel
(Eingabe ist, was das Modell sieht), lassen ``run_batch`` laufen und lesen alle Ergebnisse aus dem
Cache zurück, auch die früherer Läufe. Was wegen ``limit`` fehlt, ist markiert, nicht erfunden.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import deal
import numpy as np
import numpy.typing as npt
from loguru import logger

from georep.errors import ModelError, SchemaError
from georep.ml.base import Embedder, GenerationOptions, Generator, Vectors, full_name
from georep.ml.cache import CacheKey, ModelCache, decode_vectors, encode_vector, input_sha256


def _duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    hours, minutes = divmod(round(seconds / 60), 60)
    return f"{hours} h {minutes:02d} min"


@dataclass(frozen=True)
class Progress:
    """Stand eines Laufs nach einem Stapel. ``todo`` zählt die neuen Eingaben dieses Laufs."""

    label: str
    done: int
    todo: int
    cached: int
    total: int
    elapsed_s: float

    @property
    def eta_s(self) -> float | None:
        """Restzeit aus dem Tempo dieses Laufs; ``None``, solange nichts gerechnet ist."""
        if not self.done:
            return None
        return self.elapsed_s / self.done * (self.todo - self.done)

    def line(self) -> str:
        if not self.todo:
            return f"{self.label}: nichts zu rechnen, {self.cached} aus dem Cache"
        eta = self.eta_s
        rest = f", Rest ≈ {_duration(eta)}" if eta is not None else ""
        pace = f"; {self.elapsed_s / self.done:.2f} s je Eingabe" if self.done else ""
        share = 100 * self.done / self.todo
        return (
            f"{self.label}: {self.done}/{self.todo} neu ({share:.1f} %), "
            f"{self.cached} aus dem Cache{pace}{rest}"
        )


@dataclass(frozen=True)
class BatchReport:
    """Verschiedene Eingaben: aus dem Cache, in diesem Lauf gerechnet, offen wegen ``limit``."""

    total: int
    cached: int
    computed: int
    left: int
    seconds: float

    def line(self) -> str:
        left = f", {self.left} offen (limit)" if self.left else ""
        return (
            f"{self.total} Eingaben: {self.cached} aus dem Cache, {self.computed} neu{left} "
            f"in {self.seconds:.1f} s"
        )


def progress_log(
    every_s: float = 30.0,
    *,
    clock: Callable[[], float] = time.monotonic,
    write: Callable[[str], None] = logger.info,
) -> Callable[[Progress], None]:
    """Ein ``progress`` für lange Läufe: die erste Zeile, dann höchstens alle ``every_s``, und die letzte."""
    last: list[float] = []

    def log(progress: Progress) -> None:
        now = clock()
        if not last or now - last[0] >= every_s or progress.done == progress.todo:
            write(progress.line())
            last[:] = [now]

    return log


Compute = Callable[[Sequence[int]], Sequence[bytes]]


# Benannte Validatoren mit der ganzen Signatur: deal bindet Schlüsselwortparameter samt Vorgaben
# nur an Validatoren, die sie nennen, und das mypy-Plugin prüft die Signatur (CLAUDE.md, deal).
def _valid_sizes(
    keys: Sequence[str],
    compute: Compute,
    cache: ModelCache,
    key: CacheKey,
    *,
    batch_size: int = 1,
    limit: int = 0,
    label: str = "",
    progress: Callable[[Progress], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> bool:
    return batch_size >= 1 and limit >= 0


def _every_input_accounted_for(
    keys: Sequence[str],
    compute: Compute,
    cache: ModelCache,
    key: CacheKey,
    result: BatchReport,
    *,
    batch_size: int = 1,
    limit: int = 0,
    label: str = "",
    progress: Callable[[Progress], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> bool:
    accounted = result.cached + result.computed + result.left
    return accounted == result.total == len(set(keys)) and (not limit or result.computed <= limit)


@deal.pre(_valid_sizes, message="batch_size mindestens 1, limit nicht negativ")
@deal.ensure(
    _every_input_accounted_for,
    message="jede verschiedene Eingabe ist aus dem Cache, neu oder offen; neu höchstens limit",
)
def run_batch(
    keys: Sequence[str],
    compute: Compute,
    cache: ModelCache,
    key: CacheKey,
    *,
    batch_size: int = 1,
    limit: int = 0,
    label: str = "",
    progress: Callable[[Progress], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> BatchReport:
    """Rechnet die fehlenden Eingaben in Stapeln; ``compute`` bekommt Indizes in ``keys``.

    ``keys`` ist je Eingabe ihr SHA-256 (``input_sha256``); doppelte werden einmal gerechnet, an
    ihrer ersten Stelle. ``compute`` liefert je Index einen Wert, in derselben Reihenfolge.
    """
    started = clock()
    first: dict[str, int] = {}
    for index, sha in enumerate(keys):
        first.setdefault(sha, index)
    known = cache.known(key) & first.keys()
    missing = [index for sha, index in first.items() if sha not in known]
    todo = missing[:limit] if limit else missing
    done = 0
    for start in range(0, len(todo), batch_size):
        chunk = todo[start : start + batch_size]
        values = compute(chunk)
        if len(values) != len(chunk):
            raise ModelError(f"{label or key.model}: {len(values)} Werte für {len(chunk)} Eingaben")
        cache.put_many(key, [(keys[i], value) for i, value in zip(chunk, values, strict=True)])
        done += len(chunk)
        if progress is not None:
            progress(Progress(label, done, len(todo), len(known), len(first), clock() - started))
    return BatchReport(
        total=len(first),
        cached=len(known),
        computed=done,
        left=len(missing) - done,
        seconds=clock() - started,
    )


def _check_cache(cache: ModelCache, model: str) -> None:
    if cache.model != full_name(model):
        raise SchemaError(f"Cache-Datei {cache.path} gehört zu {cache.model}, nicht zu {model}")


@dataclass(frozen=True)
class Embedded:
    """Eine Zeile je Eingabe; wo ``present`` falsch ist (wegen ``limit``), steht ein Nullvektor."""

    vectors: Vectors
    present: npt.NDArray[np.bool_]
    report: BatchReport


def embed_texts(
    embedder: Embedder,
    cache: ModelCache,
    texts: Sequence[str],
    *,
    prompt: str,
    batch_size: int = 32,
    limit: int = 0,
    progress: Callable[[Progress], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Embedded:
    """Einbettungen für ``texts`` aus dem Cache und, was fehlt, vom Modell.

    ``prompt`` ist die Prompt-Version: bei Einbettungen sagt sie, wie der Text vorbereitet ist
    (Präfix, Zuschnitt). Der Text selbst geht so an das Modell, wie er hier steht.
    """
    _check_cache(cache, embedder.name)
    key = CacheKey(full_name(embedder.name), embedder.digest, prompt)
    shas = [input_sha256(text) for text in texts]

    def compute(indices: Sequence[int]) -> list[bytes]:
        return [encode_vector(row) for row in embedder.embed([texts[i] for i in indices])]

    report = run_batch(
        shas,
        compute,
        cache,
        key,
        batch_size=batch_size,
        limit=limit,
        label=embedder.name,
        progress=progress,
        clock=clock,
    )
    found = cache.get_many(key, sorted(set(shas)))
    present = np.asarray([sha in found for sha in shas], dtype=np.bool_)
    zero = bytes(4 * embedder.dimension)
    vectors = decode_vectors([found.get(sha, zero) for sha in shas], embedder.dimension)
    return Embedded(vectors, present, report)


@dataclass(frozen=True)
class Generated:
    """Eine Antwort je Prompt; ``None``, wo sie wegen ``limit`` noch fehlt."""

    texts: list[str | None]
    report: BatchReport


def generate_texts(
    generator: Generator,
    cache: ModelCache,
    prompts: Sequence[str],
    *,
    prompt: str,
    options: GenerationOptions,
    system: str = "",
    limit: int = 0,
    progress: Callable[[Progress], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Generated:
    """Antworten auf ``prompts`` (je ein fertiger Prompt) mit gemeinsamer Systemnachricht.

    Die Eingabe im Schlüssel ist System und Prompt zusammen, die Prompt-Version im Schlüssel trägt
    den Hash der Optionen: eine andere Ausgabelänge oder ein anderer Seed treffen nichts Altes.
    """
    _check_cache(cache, generator.name)
    key = CacheKey(full_name(generator.name), generator.digest, f"{prompt}+{options.key()}")
    shas = [input_sha256(f"{system}\x00{text}") for text in prompts]

    def compute(indices: Sequence[int]) -> list[bytes]:
        return [
            generator.generate(prompts[i], system=system, options=options).encode("utf-8")
            for i in indices
        ]

    report = run_batch(
        shas,
        compute,
        cache,
        key,
        batch_size=1,
        limit=limit,
        label=generator.name,
        progress=progress,
        clock=clock,
    )
    found = cache.get_many(key, sorted(set(shas)))
    texts = [found[sha].decode("utf-8") if sha in found else None for sha in shas]
    return Generated(texts, report)
