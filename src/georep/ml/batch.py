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

from georep.errors import ModelError, ModelRejectedError, ModelUnreachableError, SchemaError
from georep.ml.base import EmbeddingUse, GenerationUse, Vectors, full_name
from georep.ml.cache import (
    REJECTED,
    CacheKey,
    ModelCache,
    decode_vectors,
    encode_vector,
    input_sha256,
)


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
    """Verschiedene Eingaben: aus dem Cache, neu, abgewiesen, gescheitert, offen wegen ``limit``.

    ``rejected`` sind die Eingaben, die das Modell abwies, aus früheren Läufen (übersprungen) und
    aus diesem; sie sind erledigt. ``failures`` sind die Fehlschläge dieses Laufs ohne Abweisung
    (Zeit, 5xx); sie bleiben offen. Beide als (Index in ``keys``, Grund).
    """

    total: int
    cached: int
    computed: int
    left: int
    seconds: float
    truncated: int = 0  # davon in diesem Lauf neu und abgeschnitten (an ``num_predict``)
    failures: tuple[tuple[int, str], ...] = ()
    rejected: tuple[tuple[int, str], ...] = ()
    skipped: int = 0  # davon aus früheren Läufen, in diesem nicht gefragt

    @property
    def failed(self) -> int:
        return len(self.failures)

    def line(self) -> str:
        cut = f", {self.truncated} abgeschnitten" if self.truncated else ""
        rejected = f", {len(self.rejected)} abgewiesen" if self.rejected else ""
        failed = f", {self.failed} gescheitert" if self.failed else ""
        left = f", {self.left} offen (limit)" if self.left else ""
        return (
            f"{self.total} Eingaben: {self.cached} aus dem Cache, {self.computed} neu{cut}"
            f"{rejected}{failed}{left} in {self.seconds:.1f} s"
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
    retry_rejected: bool = False,
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
    retry_rejected: bool = False,
) -> bool:
    settled = result.cached + result.computed + len(result.rejected)
    accounted = settled + result.failed + result.left
    tried = result.computed + result.failed + len(result.rejected) - result.skipped
    return accounted == result.total == len(set(keys)) and (not limit or tried <= limit)


@deal.pre(_valid_sizes, message="batch_size mindestens 1, limit nicht negativ")
@deal.ensure(
    _every_input_accounted_for,
    message="jede verschiedene Eingabe ist aus dem Cache, neu, abgewiesen, gescheitert oder offen; "
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
    retry_rejected: bool = False,
) -> BatchReport:
    """Rechnet die fehlenden Eingaben in Stapeln; ``compute`` bekommt Indizes in ``keys``.

    ``keys`` ist je Eingabe ihr SHA-256 (``input_sha256``); doppelte werden einmal gerechnet, an
    ihrer ersten Stelle. ``compute`` liefert je Index einen Wert, in derselben Reihenfolge.

    Scheitert ein Stapel (``ModelError``), wird er in Einzeltexte zerlegt; was dann noch
    scheitert, steht mit Index und Grund im Bericht, und der Lauf geht weiter (Review F5, Befund 7).
    Eine Abweisung (``ModelRejectedError``) merkt sich der Cache mit Grund: sie ist erledigt, und
    spätere Läufe fragen sie nicht wieder, außer mit ``retry_rejected`` (dritte Runde, N1). Jeder
    andere Fehlschlag bleibt offen. Ein fehlender Server (``ModelUnreachableError``) und
    ``MAX_FAILURES_IN_ROW`` neue Fehlschläge in Folge brechen ab: dann liegt es nicht an einem Text.
    Was bis dahin abgewiesen wurde, ist gemerkt; der nächste Lauf kommt also weiter.
    """
    started = clock()
    first: dict[str, int] = {}
    for index, sha in enumerate(keys):
        first.setdefault(sha, index)
    known = cache.known(key) & first.keys()
    noted = {sha: note for sha, note in cache.failures(key).items() if sha in first}
    missing = [index for sha, index in first.items() if sha not in known]
    skipped = (
        []
        if retry_rejected
        else [i for i in missing if noted.get(keys[i], ("", ""))[0] == REJECTED]
    )
    skip = set(skipped)
    candidates = [i for i in missing if i not in skip]
    todo = candidates[:limit] if limit else candidates
    name = label or key.model
    done = 0
    cut = 0
    failures: list[tuple[int, str]] = []
    rejected = [(i, noted[keys[i]][1]) for i in skipped]
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
                index = indices[0]
                if isinstance(result, ModelRejectedError):
                    cache.put_failure(key, keys[index], REJECTED, str(result))
                    rejected.append((index, str(result)))
                else:
                    failures.append((index, str(result)))
                logger.warning(f"{name}: Eingabe {index} gescheitert: {result}")
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
            tried = done + len(failures) + len(rejected) - len(skipped)
            progress(Progress(label, tried, len(todo), len(known), len(first), clock() - started))
    return BatchReport(
        total=len(first),
        cached=len(known),
        computed=done,
        left=len(candidates) - done - len(failures) - (len(rejected) - len(skipped)),
        seconds=clock() - started,
        truncated=cut,
        failures=tuple(failures),
        rejected=tuple(sorted(rejected)),
        skipped=len(skipped),
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
    retry_rejected: bool = False,
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
        retry_rejected=retry_rejected,
    )
    use.record(
        open=report.left + report.failed,
        failed=report.failed,
        rejected=len(report.rejected),
        limit=limit,
    )
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
    retry_rejected: bool = False,
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
        retry_rejected=retry_rejected,
    )
    use.record(
        open=report.left + report.failed,
        failed=report.failed,
        rejected=len(report.rejected),
        limit=limit,
    )
    distinct = sorted(set(shas))
    found = cache.get_many(key, distinct)
    cut = cache.truncated(key, distinct)
    texts = [found[sha].decode("utf-8") if sha in found else None for sha in shas]
    return Generated(texts, [sha in cut for sha in shas], report)
