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
from typing import NamedTuple

import deal
import numpy as np
import numpy.typing as npt
from loguru import logger

from georep.errors import ModelError, ModelUnreachableError, SchemaError
from georep.ml.base import EmbeddingUse, GenerationUse, Vectors, full_name
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
    truncated: int = 0  # davon in diesem Lauf neu und abgeschnitten (an ``num_predict``)
    # (Index in ``keys``, Grund) je Eingabe, die das Modell abwies; sie bleibt offen
    failures: tuple[tuple[int, str], ...] = ()

    @property
    def failed(self) -> int:
        return len(self.failures)

    def line(self) -> str:
        cut = f", {self.truncated} abgeschnitten" if self.truncated else ""
        failed = f", {self.failed} gescheitert" if self.failed else ""
        left = f", {self.left} offen (limit)" if self.left else ""
        return (
            f"{self.total} Eingaben: {self.cached} aus dem Cache, {self.computed} neu{cut}"
            f"{failed}{left} in {self.seconds:.1f} s"
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


class CacheValue(NamedTuple):
    """Ein gerechneter Wert und ob er unvollständig ist; ``compute`` darf auch nackte Bytes liefern."""

    value: bytes
    truncated: bool = False


Compute = Callable[[Sequence[int]], Sequence[bytes | CacheValue]]
# So viele abgewiesene Eingaben hintereinander heißen: es liegt am Server oder am Modell, nicht an
# den Texten. Dann bricht der Lauf ab, statt den ganzen Korpus als gescheitert zu markieren.
MAX_FAILURES_IN_ROW = 10


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
    accounted = result.cached + result.computed + result.failed + result.left
    tried = result.computed + result.failed
    return accounted == result.total == len(set(keys)) and (not limit or tried <= limit)


@deal.pre(_valid_sizes, message="batch_size mindestens 1, limit nicht negativ")
@deal.ensure(
    _every_input_accounted_for,
    message="jede verschiedene Eingabe ist aus dem Cache, neu, gescheitert oder offen; "
    "versucht höchstens limit",
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

    Weist das Modell einen Stapel ab (``ModelError``), wird er in Einzeltexte zerlegt; was dann
    noch scheitert, steht mit Index und Grund in ``failures``, bleibt offen, und der Lauf geht
    weiter (Review 2026-11-23, Befund 7). Ein fehlender Server (``ModelUnreachableError``) und
    ``MAX_FAILURES_IN_ROW`` Fehlschläge in Folge brechen ab: dann liegt es nicht an einem Text.
    """
    started = clock()
    first: dict[str, int] = {}
    for index, sha in enumerate(keys):
        first.setdefault(sha, index)
    known = cache.known(key) & first.keys()
    missing = [index for sha, index in first.items() if sha not in known]
    todo = missing[:limit] if limit else missing
    name = label or key.model
    done = 0
    cut = 0
    failures: list[tuple[int, str]] = []
    in_row = 0
    for start in range(0, len(todo), batch_size):
        chunk = todo[start : start + batch_size]
        outcome = _attempt(compute, chunk)
        groups = (
            [([i], _attempt(compute, [i])) for i in chunk]
            if isinstance(outcome, ModelError) and len(chunk) > 1
            else [(chunk, outcome)]
        )
        for indices, result in groups:
            if isinstance(result, ModelError):
                failures.append((indices[0], str(result)))
                logger.warning(f"{name}: Eingabe {indices[0]} gescheitert: {result}")
                in_row += 1
                if in_row >= MAX_FAILURES_IN_ROW:
                    raise ModelError(
                        f"{name}: {in_row} Fehlschläge in Folge, zuletzt: {result}"
                    ) from result
                continue
            in_row = 0
            if len(result) != len(indices):
                raise ModelError(f"{name}: {len(result)} Werte für {len(indices)} Eingaben")
            pairs = list(zip(indices, result, strict=True))
            cache.put_many(
                key,
                [(keys[i], v.value) for i, v in pairs],
                truncated=[keys[i] for i, v in pairs if v.truncated],
            )
            done += len(indices)
            cut += sum(v.truncated for v in result)
        if progress is not None:
            tried = done + len(failures)
            progress(Progress(label, tried, len(todo), len(known), len(first), clock() - started))
    return BatchReport(
        total=len(first),
        cached=len(known),
        computed=done,
        left=len(missing) - done - len(failures),
        seconds=clock() - started,
        truncated=cut,
        failures=tuple(failures),
    )


def _attempt(compute: Compute, indices: Sequence[int]) -> list[CacheValue] | ModelError:
    """Ein Aufruf von ``compute``; eine Abweisung wird zum Wert, ein fehlender Server nicht."""
    try:
        return [v if isinstance(v, CacheValue) else CacheValue(v) for v in compute(indices)]
    except ModelUnreachableError:
        raise
    except ModelError as error:
        return error


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
    use: EmbeddingUse,
    cache: ModelCache,
    texts: Sequence[str],
    *,
    batch_size: int = 32,
    limit: int = 0,
    progress: Callable[[Progress], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Embedded:
    """Einbettungen für ``texts`` aus dem Cache und, was fehlt, vom Modell.

    Die Prompt-Version von ``use`` sagt, wie der Text vorbereitet ist (Präfix, Zuschnitt); der Text
    selbst geht so an das Modell, wie er hier steht. ``use`` erfährt danach, wie viel offen blieb.
    """
    embedder = use.embedder
    _check_cache(cache, embedder.name)
    key = CacheKey(use.name, embedder.digest, use.prompt_key())
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
        label=use.name,
        progress=progress,
        clock=clock,
    )
    use.record(open=report.left + report.failed, failed=report.failed, limit=limit)
    found = cache.get_many(key, sorted(set(shas)))
    present = np.asarray([sha in found for sha in shas], dtype=np.bool_)
    zero = bytes(4 * embedder.dimension)
    vectors = decode_vectors([found.get(sha, zero) for sha in shas], embedder.dimension)
    return Embedded(vectors, present, report)


@dataclass(frozen=True)
class Generated:
    """Eine Antwort je Prompt; ``None``, wo sie wegen ``limit`` noch fehlt.

    ``truncated`` markiert je Prompt eine Antwort, die an ``num_predict`` stieß, auch eine aus
    einem früheren Lauf: der Schritt entscheidet, ob er sie verwirft oder kennzeichnet.
    """

    texts: list[str | None]
    truncated: list[bool]
    report: BatchReport


def generate_texts(
    use: GenerationUse,
    cache: ModelCache,
    prompts: Sequence[str],
    *,
    system: str = "",
    limit: int = 0,
    progress: Callable[[Progress], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Generated:
    """Antworten auf ``prompts`` (je ein fertiger Prompt) mit gemeinsamer Systemnachricht.

    Die Eingabe im Schlüssel ist System und Prompt zusammen, die Prompt-Version im Schlüssel trägt
    den Hash der Optionen von ``use``: eine andere Ausgabelänge oder ein anderer Seed treffen nichts
    Altes. ``use`` erfährt danach, wie viel offen blieb.
    """
    generator, options = use.generator, use.options
    _check_cache(cache, generator.name)
    key = CacheKey(use.name, generator.digest, use.prompt_key())
    shas = [input_sha256(f"{system}\x00{text}") for text in prompts]

    def compute(indices: Sequence[int]) -> list[CacheValue]:
        replies = [generator.generate(prompts[i], system=system, options=options) for i in indices]
        return [CacheValue(r.text.encode("utf-8"), r.truncated) for r in replies]

    report = run_batch(
        shas,
        compute,
        cache,
        key,
        batch_size=1,
        limit=limit,
        label=use.name,
        progress=progress,
        clock=clock,
    )
    use.record(open=report.left + report.failed, failed=report.failed, limit=limit)
    distinct = sorted(set(shas))
    found = cache.get_many(key, distinct)
    cut = cache.truncated(key, distinct)
    texts = [found[sha].decode("utf-8") if sha in found else None for sha in shas]
    return Generated(texts, [sha in cut for sha in shas], report)
