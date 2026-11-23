"""``georep ml status`` und ``georep ml bench``: ist der Modellserver bereit, und wie schnell ist ein Modell?

``status`` fragt den Server (Version, die Modelle aus ``[ml]`` mit Digest, was im Speicher liegt)
und zählt den Modellcache je Modell, Digest und Prompt-Version; Exit 1, wenn der Server fehlt oder
ein Modell aus den Settings nicht auf ihm liegt. ``bench`` misst ein Modell an ``n`` Dokumenten des
Korpus: zuerst ein Aufruf zum Aufwärmen (das Laden zählt nicht), dann jedes Dokument einzeln, bei
Einbettungen zusätzlich alle in einem Stapel. Es druckt Sekunden je Dokument, Token je Sekunde
für Eingabe und Ausgabe und die Hochrechnung auf die Dokumente mit Text. Der Cache bleibt dabei
unberührt: gemessen wird das Modell, nicht der Cache. Die Zahlen gehören datiert, mit der
Rechnerlast daneben, nach ``docs/profiling/README.md``.
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import polars as pl

from georep.errors import MissingInputError, ModelError
from georep.http import Transport
from georep.layout import Layout
from georep.ml.base import Call, full_name
from georep.ml.cache import cache_stats
from georep.ml.ollama import (
    OllamaClient,
    OllamaEmbedder,
    OllamaGenerator,
    client_from_settings,
    generation_options,
)
from georep.settings import Ml, Settings

# Der Prompt des Rauchtests, kein Prompt eines Vorhabens: zwei Sätze, damit die Ausgabe kurz und
# die Messung mit ``--max-tokens`` vergleichbar bleibt.
BENCH_SYSTEM = "Du fasst Dokumente aus einem Ratsinformationssystem sachlich auf Deutsch zusammen."
BENCH_PROMPT = "Fasse das folgende Dokument in zwei Sätzen zusammen.\n\n{text}"


def make_transport() -> Transport | None:
    """Die Testnaht der Befehle: ``None`` heißt eine echte Session mit dem Timeout aus ``[ml]``."""
    return None


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ml = sub.add_parser("ml", help="lokale Modelle: Server, Modelle, Cache, Durchsatz")
    ml_sub = ml.add_subparsers(dest="ml_command", required=True)
    ml_sub.add_parser("status", help="Server erreichbar? Modelle aus [ml]? Modellcache je Modell")
    bench = ml_sub.add_parser("bench", help="Durchsatz eines Modells an n Dokumenten des Korpus")
    bench.add_argument("model", help="Modellname auf dem Server, etwa qwen3.6:27b")
    bench.add_argument("--n", type=int, default=20, help="so viele Dokumente (Standard 20)")
    bench.add_argument(
        "--chars", type=int, default=8000, help="je Dokument höchstens so viele Zeichen"
    )
    bench.add_argument(
        "--max-tokens", type=int, default=120, help="Generatoren: höchstens so viele Token Antwort"
    )
    bench.add_argument("--seed", type=int, default=0, help="Seed der Stichprobe")


def _size(count: float) -> str:
    for unit, factor in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if count >= factor:
            return f"{count / factor:.1f} {unit}"
    return f"{count:.0f} B"


def status_lines(client: OllamaClient, ml: Ml, cache_root: Path) -> tuple[list[str], int]:
    """Die Zeilen von ``georep ml status`` und der Exit-Code (1: Server oder Modell fehlt)."""
    lines: list[str] = []
    code = 0
    # Der ganze Serverblock im ``try``: eine kaputte Antwort nach der Version soll die Zeilen
    # davor und den Cache nicht kosten (Review 2026-11-23, Befund 8).
    try:
        lines.append(f"ollama {client.version()} unter {client.base_url}")
        everything = client.models()
        for role, model in (
            ("Einbettung", ml.embedding.model),
            ("Generierung", ml.generation.model),
        ):
            found = next((m for m in everything if m.name == full_name(model)), None)
            if found is None:
                lines.append(f"{role:<12} {full_name(model)}  fehlt; `ollama pull {model}`")
                code = 1
                continue
            lines.append(
                f"{role:<12} {found.name}  vorhanden, Digest {found.digest[:12]}, "
                f"{_size(found.size)}, {found.family} {found.parameter_size} {found.quantization}"
            )
        running = client.loaded()
        memory = ", ".join(f"{r.name} ({_size(r.size_vram)} Grafikspeicher)" for r in running)
        lines.append(f"im Speicher: {memory or 'nichts'}")
        lines.append(f"auf dem Server: {len(everything)} Modelle")
    except ModelError as error:
        lines.append(str(error))
        code = 1
    stats = cache_stats(cache_root)
    lines.append(f"Cache {cache_root}: {'leer' if not stats else ''}".rstrip())
    # Je Datei, nicht je Modellname: eine umbenannte Datei hat einen anderen Namen als ihr Modell
    # (Review F5, dritte Runde, N6).
    for path in sorted({s.path for s in stats}):
        here = [s for s in stats if s.path == path]
        lines.append(f"  {here[0].model}  Datei {path.name}, {_size(path.stat().st_size)}")
        lines.extend(
            f"    Digest {s.digest[:12]}  {s.prompt}  {s.entries} Einträge, {_size(s.bytes)}"
            for s in here
        )
    return lines, code


@dataclass(frozen=True)
class BenchRow:
    id: str
    chars: int
    call: Call
    wall_s: float

    def line(self) -> str:
        cut = "  abgeschnitten" if self.call.truncated else ""
        return (
            f"  {self.id}  {self.chars:>6} Zeichen  {self.call.prompt_tokens:>6} Token ein  "
            f"{self.call.output_tokens:>4} Token aus  {self.wall_s:6.2f} s{cut}"
        )


@dataclass(frozen=True)
class BenchReport:
    model: str
    digest: str
    kind: str  # "Einbettung" oder "Text"
    seed: int
    chars: int
    max_tokens: int
    rows: list[BenchRow]
    load_seconds: float
    corpus_documents: int  # mit Text
    corpus_total: int
    corpus_mean_chars: float  # bis ``chars`` gekappt, wie die Stichprobe
    batch_seconds: float | None = None
    example: str = ""

    @property
    def mean_seconds(self) -> float:
        return statistics.fmean(r.wall_s for r in self.rows) if self.rows else 0.0

    def _rate(self, tokens: Callable[[Call], int], seconds: Callable[[Call], float]) -> float:
        total = sum(seconds(r.call) for r in self.rows)
        return sum(tokens(r.call) for r in self.rows) / total if total else 0.0

    def summary(self) -> list[str]:
        n = len(self.rows)
        walls = [r.wall_s for r in self.rows]
        median = statistics.median(walls) if walls else 0.0
        prompt_rate = self._rate(lambda c: c.prompt_tokens, lambda c: c.prompt_seconds)
        lines = [
            f"{self.model} (Digest {self.digest[:12]}, {self.kind}), {n} Dokumente aus dem Korpus "
            f"(Seed {self.seed}), je höchstens {self.chars} Zeichen"
            + (f", höchstens {self.max_tokens} Token Antwort" if self.kind == "Text" else ""),
            f"Laden (beim Aufwärmen, nicht gezählt): {self.load_seconds:.1f} s",
            f"je Dokument: Mittel {self.mean_seconds:.2f} s, Median {median:.2f} s; "
            f"Eingabe {prompt_rate:.0f} Token/s",
        ]
        if self.kind == "Text":
            output_rate = self._rate(lambda c: c.output_tokens, lambda c: c.output_seconds)
            cut = sum(r.call.truncated for r in self.rows)
            lines[-1] += f", Ausgabe {output_rate:.1f} Token/s; abgeschnitten: {cut} von {n}"
        sample_chars = statistics.fmean(r.chars for r in self.rows) if self.rows else 0.0
        lines.append(
            f"Stichprobe im Mittel {sample_chars:.0f} Zeichen, Korpus {self.corpus_mean_chars:.0f} "
            f"(beide bis {self.chars} gekappt)"
        )
        hours = self.mean_seconds * self.corpus_documents / 3600
        lines.append(
            f"Hochrechnung: {self.corpus_documents} Dokumente mit Text (Korpus {self.corpus_total}) "
            f"≈ {hours:.1f} h einzeln"
        )
        if self.batch_seconds is not None and n:
            per = self.batch_seconds / n
            lines.append(
                f"Stapel: alle {n} in einem Aufruf {self.batch_seconds:.2f} s, {per:.3f} s je "
                f"Dokument, hochgerechnet ≈ {per * self.corpus_documents / 3600:.2f} h"
            )
        if self.example:
            lines.append(f"Beispiel (erstes Dokument): {self.example[:200]}")
        return lines

    def lines(self) -> list[str]:
        return [*(r.line() for r in self.rows), *self.summary()]


def bench(
    client: OllamaClient,
    model: str,
    corpus: pl.DataFrame,
    *,
    n: int,
    chars: int,
    max_tokens: int,
    seed: int,
    settings: Ml,
    clock: Callable[[], float] = time.perf_counter,
    on_row: Callable[[BenchRow], None] | None = None,
) -> BenchReport:
    """Misst ``model`` an ``n`` zufälligen Dokumenten mit Text (fester Seed, nach ID geordnet)."""
    capabilities = client.capabilities(model)
    if "embedding" in capabilities:
        kind = "Einbettung"
    elif "completion" in capabilities:
        kind = "Text"
    else:
        raise ModelError(f"{full_name(model)} kann weder Einbettung noch Text: {capabilities}")
    digest = client.info(model).digest
    with_text = corpus.filter(pl.col("text").str.len_chars() > 0)
    sample = with_text.sample(min(n, with_text.height), seed=seed).sort("id")
    documents = [(row["id"], row["text"][:chars]) for row in sample.iter_rows(named=True)]
    rows: list[BenchRow] = []
    example = ""
    batch_seconds: float | None = None
    if kind == "Einbettung":
        embedder = OllamaEmbedder(client, model, dimension=client.dimension(model))
        embedder.embed(["ok"])
        load = embedder.calls[-1].load_seconds
        for doc_id, text in documents:
            started = clock()
            embedder.embed([text])
            rows.append(BenchRow(doc_id, len(text), embedder.calls[-1], clock() - started))
            if on_row is not None:
                on_row(rows[-1])
        started = clock()
        embedder.embed([text for _, text in documents])
        batch_seconds = clock() - started
    else:
        options = replace(generation_options(settings), num_predict=max_tokens)
        generator = OllamaGenerator(client, model, options=options)
        generator.generate("ok", options=replace(options, num_predict=1))
        load = generator.calls[-1].load_seconds
        for doc_id, text in documents:
            started = clock()
            answer = generator.generate(BENCH_PROMPT.format(text=text), system=BENCH_SYSTEM)
            rows.append(BenchRow(doc_id, len(text), generator.calls[-1], clock() - started))
            example = example or answer.text
            if on_row is not None:
                on_row(rows[-1])
    capped = with_text.select(pl.col("text").str.len_chars().clip(upper_bound=chars).mean())
    return BenchReport(
        model=full_name(model),
        digest=digest,
        kind=kind,
        seed=seed,
        chars=chars,
        max_tokens=max_tokens,
        rows=rows,
        load_seconds=load,
        corpus_documents=with_text.height,
        corpus_total=corpus.height,
        corpus_mean_chars=float(capped.item() or 0.0),
        batch_seconds=batch_seconds,
        example=example,
    )


def run(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    client = client_from_settings(settings.ml, transport=make_transport())
    if args.ml_command == "status":
        lines, code = status_lines(client, settings.ml, layout.ml_cache)
        print("\n".join(lines))
        return code
    if not layout.corpus.exists():
        raise MissingInputError(
            f"{layout.corpus} fehlt; `georep bootstrap && georep run corpus` baut den Korpus"
        )
    corpus = pl.read_parquet(layout.corpus, columns=["id", "text"])
    report = bench(
        client,
        args.model,
        corpus,
        n=args.n,
        chars=args.chars,
        max_tokens=args.max_tokens,
        seed=args.seed,
        settings=settings.ml,
        on_row=lambda row: print(row.line(), flush=True),
    )
    print("\n".join(report.summary()))
    return 0
