"""Die geschichtete Stichprobe eines Vorhabens (``georep validate sample``, F4).

Gezogen wird ohne Zufallsgenerator: jede Einheit bekommt den Rang sha256(„<seed>|<id>"), und je
Schicht kommen die Einheiten mit den kleinsten Rängen in die Stichprobe (bottom-k). Das ist
reproduzierbar über Rechner und Bibliotheksversionen hinweg (numpy und Polars sichern ihre
Zufallsfolgen nicht über Versionen zu), unabhängig von der Zeilenfolge der Grundgesamtheit und
stabil, wenn sie wächst: eine neue Einheit verdrängt höchstens eine alte ihrer Schicht, statt alle
neu zu mischen (docs/decisions.md, „Validierung mit zwei KI-Kodierern").

Die Aufteilung auf die Schichten (``allocate``) ist rein und ganzzahlig. ``proportional`` teilt nach
den Schichtgrößen mit dem Verfahren des größten Restes; eine Schicht, die dabei leer bliebe,
bekommt eine Einheit von der Schicht mit dem größten Überschuss. ``equal`` füllt die Schichten
gleichmäßig auf, kleine ganz. Jede Zeile der Stichprobe trägt ihre Schichtgröße ``schicht_n``
(N_h): daraus rechnet ``score`` die Gewichte N_h/n_h, denn nur eine selbstgewichtende Stichprobe
(n_h/N_h überall gleich) darf man wie eine einfache auszählen.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Literal

import deal
import polars as pl

from georep.contracts import has_columns, strata_filled, unique_keys
from georep.errors import EmptyResultError, MissingInputError, SchemaError
from georep.io import atomic_path, digest, write_json
from georep.layout import Layout
from georep.settings import Settings
from georep.validation import CodingError
from georep.validation.codebook import (
    DOCUMENT_COLUMNS,
    EXTRA_COLUMNS,
    KEY_SEPARATOR,
    Codebook,
    Unit,
    load_codebook,
)
from georep.validation.paths import ValidationPaths, validation_paths

ID = "id"
STRATUM = "schicht"
STRATUM_SIZE = "schicht_n"
Allocation = Literal["proportional", "equal"]
# Spalte der Grundgesamtheit -> Spalte der Stichprobe. ``id`` ist in der Stichprobe immer der
# Schlüssel der Einheit; ein Dokument, das nicht selbst die Einheit ist, heißt darum ``dokument``.
SAMPLE_COLUMNS: dict[Unit, tuple[tuple[str, str], ...]] = {
    "document": (),
    "document_pair": (("id_a", "id_a"), ("id_b", "id_b")),
    "pair_with_span": (("id_a", "id_a"), ("id_b", "id_b"), ("start", "start"), ("end", "end")),
    "span": (("id", "dokument"), ("start", "start"), ("end", "end"), ("kind", "kind")),
    "query_document": (("query", "anfrage"), ("id", "dokument")),
    "marking": (),
}
INTEGER_COLUMNS = ("start", "end", STRATUM_SIZE)


def sample_columns(codebook: Codebook) -> tuple[tuple[str, str], ...]:
    """Die Bestandteile, die die Stichprobe neben ``id`` trägt; mit ``sample.key`` auch das Dokument."""
    base = SAMPLE_COLUMNS[codebook.unit]
    if codebook.sample.key and codebook.unit in ("document", "marking"):
        return (("id", "dokument"),)
    return base


def _allocation_holds(
    sizes: Mapping[str, int], n: int, allocation: Allocation, result: dict[str, int]
) -> bool:
    return (
        set(result) == set(sizes)
        and sum(result.values()) == n
        and all(1 <= result[s] <= sizes[s] for s in sizes)
    )


@deal.pre(
    lambda sizes, n, allocation: (
        len(sizes) > 0
        and all(size >= 1 for size in sizes.values())
        and len(sizes) <= n <= sum(sizes.values())
    ),
    message="jede Schicht nicht leer, mindestens eine Einheit je Schicht, höchstens alle",
)
@deal.ensure(
    _allocation_holds, message="die Summe ist n, jede Schicht hat 1 bis alle ihre Einheiten"
)
@deal.pure
def allocate(sizes: Mapping[str, int], n: int, allocation: Allocation) -> dict[str, int]:
    """Wie viele Einheiten jede Schicht beiträgt; ganzzahlig, die Summe ist genau ``n``.

    ``proportional``: Quote n·N_h/N, abgerundet, die fehlenden an die größten Reste (bei gleichem
    Rest an die alphabetisch erste Schicht) -- {a: 900, b: 100} mit n = 10 ergibt 9 und 1. Bleibt
    eine Schicht dabei leer, bekommt sie eine Einheit von der Schicht, die am meisten über ihrer
    Quote liegt; dann ist die Stichprobe nicht mehr selbstgewichtend, und ``score`` gewichtet.
    ``equal``: die Schichten von der kleinsten zur größten; jede nimmt den abgerundeten gleichen
    Anteil des Rests oder, wenn sie kleiner ist, sich ganz; die größten nehmen den Rest auf.
    """
    names = sorted(sizes)
    if allocation == "equal":
        result: dict[str, int] = {}
        remaining = n
        order = sorted(names, key=lambda name: (sizes[name], name))
        for i, name in enumerate(order):
            take = min(sizes[name], remaining // (len(order) - i))
            result[name] = take
            remaining -= take
        return result
    total = sum(sizes.values())
    quota = {name: Fraction(n * sizes[name], total) for name in names}
    floors = {name: n * sizes[name] // total for name in names}
    missing = n - sum(floors.values())
    lucky = sorted(names, key=lambda name: (-(quota[name] - floors[name]), name))[:missing]
    alloc = {name: floors[name] + (1 if name in lucky else 0) for name in names}
    for name in names:
        if alloc[name] == 0:
            donor = max(
                (other for other in names if alloc[other] > 1),
                key=lambda other: (alloc[other] - quota[other], other),
            )
            alloc[donor] -= 1
            alloc[name] = 1
    return alloc


def self_weighting(sizes: Mapping[str, int], drawn: Mapping[str, int]) -> bool:
    """n_h/N_h ist in jeder Schicht gleich: dann gilt jede Einheit gleich viel."""
    return len({Fraction(drawn[name], sizes[name]) for name in sizes}) <= 1


def rank(seed: int, key: str) -> str:
    """Der Rang einer Einheit beim Ziehen: SHA-256 über Seed und Schlüssel, hexadezimal."""
    return hashlib.sha256(f"{seed}{KEY_SEPARATOR}{key}".encode()).hexdigest()


def unit_frame(population: pl.DataFrame, codebook: Codebook) -> pl.DataFrame:
    """Die Grundgesamtheit mit Schlüssel ``id``, den Bestandteilen der Stichprobe und ``schicht``.

    Fehlt eine Spalte, ist ein Bestandteil des Schlüssels leer oder trägt er das Trennzeichen,
    kommt ein Schlüssel zweimal vor oder ist ein Kontextwert länger als ``text.context_chars``,
    ist das ein ``SchemaError``: die Grundgesamtheit taugt dann nicht als Liste von Einheiten.
    """
    unit = codebook.unit
    keys = codebook.key_columns
    stratum = codebook.sample.stratum
    sources = [source for source, _ in sample_columns(codebook)]
    needed = [*keys, *sources, *EXTRA_COLUMNS.get(unit, ()), *DOCUMENT_COLUMNS[unit]]
    needed += [*([stratum] if stratum else []), *codebook.text.context]
    missing = [column for column in dict.fromkeys(needed) if column not in population.columns]
    if missing:
        raise SchemaError(
            f"Grundgesamtheit ohne Spalten {missing}; die Einheit {unit} braucht {list(keys)}"
        )
    broken = population.select(
        pl.any_horizontal(
            [
                pl.col(c).is_null()
                | pl.col(c).cast(pl.String).str.contains(KEY_SEPARATOR, literal=True)
                | (pl.col(c).cast(pl.String) == "")
                for c in keys
            ]
        )
    ).to_series()
    if bool(broken.any()):
        raise SchemaError(
            f"{int(broken.sum())} Einheiten mit leerem Bestandteil oder {KEY_SEPARATOR!r} darin "
            f"(Spalten {list(keys)})"
        )
    limit = codebook.text.context_chars
    for column in codebook.text.context:
        longest = population.select(pl.col(column).cast(pl.String).str.len_chars().max()).item()
        if longest is not None and longest > limit:
            raise SchemaError(
                f"text.context {column!r}: Werte bis {longest} Zeichen; stichprobe.csv liegt im "
                f"Repo, erlaubt sind {limit} (text.context_chars)"
            )
    parts = [pl.col(column).cast(pl.String) for column in keys]
    frame = population.select(
        pl.concat_str(parts, separator=KEY_SEPARATOR).alias("_key"),
        *[pl.col(source).alias(target) for source, target in sample_columns(codebook)],
        (pl.col(stratum).cast(pl.String).fill_null("") if stratum else pl.lit("")).alias(STRATUM),
        *[pl.col(column) for column in codebook.text.context],
        *[pl.col(column).alias(f"_doc_{column}") for column in DOCUMENT_COLUMNS[unit]],
    ).rename({"_key": ID})
    if not unique_keys(frame, ID):
        doubled = frame.filter(pl.col(ID).is_duplicated()).get_column(ID).unique().sort()
        raise SchemaError(
            f"{doubled.len()} Einheiten mehrfach in der Grundgesamtheit, etwa {doubled[0]!r}"
        )
    return frame


@dataclass(frozen=True)
class Sample:
    """Die gezogene Stichprobe und ihre Schichten: Schicht -> (Grundgesamtheit, Stichprobe)."""

    frame: pl.DataFrame  # id, Bestandteile, schicht, schicht_n, Kontextspalten; nach id sortiert
    strata: dict[str, tuple[int, int]]
    population: int  # Einheiten, aus denen gezogen wurde
    without_text: int  # Einheiten, die vorher mangels Text wegfielen

    @property
    def self_weighting(self) -> bool:
        return self_weighting(
            {s: n for s, (n, _) in self.strata.items()}, {s: k for s, (_, k) in self.strata.items()}
        )


def _sample_holds(result: Sample) -> bool:
    return (
        unique_keys(result.frame, ID)
        and bool(result.frame.get_column(ID).is_sorted())
        and strata_filled(result.frame, STRATUM, {s: n for s, (_, n) in result.strata.items()})
    )


@deal.post(_sample_holds, message="jede Einheit einmal, nach id sortiert, jede Schicht belegt")
@deal.raises(SchemaError, EmptyResultError)
def draw_sample(
    population: pl.DataFrame, codebook: Codebook, texts: frozenset[str] | None = None
) -> Sample:
    """Die Stichprobe nach den Regeln des Codebuchs; ``texts`` sind die Dokumente mit Text.

    Mit ``sample.require_text`` und ``texts`` fallen Einheiten weg, deren Dokumente keinen Text
    haben: ein leerer Ausschnitt lässt sich nicht kodieren. ``sample.strata`` beschränkt auf die
    genannten Schichten. Danach gilt: jede Schicht trägt mindestens eine Einheit, und jede Zeile
    trägt die Größe ihrer Schicht in der Grundgesamtheit (``schicht_n``).
    """
    rules = codebook.sample
    frame = unit_frame(population, codebook)
    if rules.strata:
        unknown = sorted(set(rules.strata) - set(frame.get_column(STRATUM)))
        if unknown:
            raise SchemaError(f"sample.strata {unknown}: diese Schichten gibt es nicht")
        frame = frame.filter(pl.col(STRATUM).is_in(rules.strata))
    before = frame.height
    if rules.require_text and texts is not None:
        documents = [f"_doc_{c}" for c in DOCUMENT_COLUMNS[codebook.unit]]
        frame = frame.filter(pl.all_horizontal([pl.col(d).is_in(list(texts)) for d in documents]))
    if frame.is_empty():
        raise EmptyResultError("die Grundgesamtheit hat keine Einheit (mit Text)")
    sizes = {str(name): int(count) for name, count in frame.group_by(STRATUM).len().iter_rows()}
    if rules.size > frame.height:
        raise EmptyResultError(
            f"sample.size {rules.size} ist größer als die Grundgesamtheit ({frame.height} Einheiten)"
        )
    if rules.size < len(sizes):
        raise SchemaError(
            f"sample.size {rules.size} ist kleiner als die Zahl der Schichten ({len(sizes)}): "
            "jede Schicht braucht eine Einheit; sample.strata oder sample.stratum ändern"
        )
    quota = allocate(sizes, rules.size, rules.allocation)
    ranked = frame.with_columns(
        pl.Series("_rank", [rank(rules.seed, key) for key in frame.get_column(ID).to_list()])
    )
    chosen = (
        ranked.sort(["_rank", ID])
        .with_columns(pl.int_range(pl.len()).over(STRATUM).alias("_place"))
        .filter(pl.col("_place") < pl.col(STRATUM).replace_strict(quota, return_dtype=pl.Int64))
        .drop("_rank", "_place", *[c for c in ranked.columns if c.startswith("_doc_")])
        .with_columns(
            pl.col(STRATUM).replace_strict(sizes, return_dtype=pl.Int64).alias(STRATUM_SIZE)
        )
        .sort(ID)
    )
    columns = [ID, *[t for _, t in sample_columns(codebook)], STRATUM, STRATUM_SIZE]
    return Sample(
        frame=chosen.select(*columns, *codebook.text.context),
        strata={name: (sizes[name], quota[name]) for name in sorted(sizes)},
        population=frame.height,
        without_text=before - frame.height,
    )


@dataclass(frozen=True)
class SampleReport:
    path: Path
    sample: Sample

    def line(self) -> str:
        strata = len(self.sample.strata)
        dropped = (
            f", {self.sample.without_text} ohne Text weggelassen"
            if self.sample.without_text
            else ""
        )
        weighting = "" if self.sample.self_weighting else "; nicht selbstgewichtend"
        return (
            f"{self.sample.frame.height} Einheiten aus {self.sample.population}{dropped}, "
            f"{strata} Schicht{'en' if strata != 1 else ''}{weighting} -> {self.path}"
        )


def documents_with_text(corpus: Path) -> frozenset[str]:
    """Die Dokumente des Korpus mit nicht leerem Text."""
    if not corpus.is_file():
        raise MissingInputError(f"{corpus} fehlt; `georep run corpus` baut den Korpus")
    frame = pl.read_parquet(corpus, columns=["id", "text"])
    return frozenset(frame.filter(pl.col("text").str.len_chars() > 0).get_column("id").to_list())


def population_path(layout: Layout, codebook: Codebook, override: Path | None) -> Path:
    """Die Grundgesamtheit: ``override``, sonst ``sample.population`` im Profilordner, sonst der Korpus."""
    rules = codebook.sample
    return override or (layout.root / rules.population if rules.population else layout.corpus)


def write_sample(paths: ValidationPaths, frame: pl.DataFrame, meta: dict[str, object]) -> None:
    """``stichprobe.csv`` und ``stichprobe.json`` ablegen (auch für übernommene Stichproben)."""
    with atomic_path(paths.sample) as tmp:
        frame.write_csv(tmp)
    write_json(paths.sample_meta, meta)


def sample_project(
    settings: Settings,
    layout: Layout,
    project: str,
    *,
    today: dt.date,
    population: Path | None = None,
    force: bool = False,
) -> SampleReport:
    """``georep validate sample``: die Stichprobe ziehen und mit ihrem Steckbrief ablegen.

    ``stichprobe.csv`` trägt nur Schlüssel, Schicht und Schichtgröße, ``stichprobe.json`` Profil,
    Prüfsumme der Grundgesamtheit, Seed und Aufteilung; beides gehört ins Repo. Eine vorhandene
    Stichprobe bleibt ohne ``force`` stehen: wer sie neu zieht, nachdem kodiert wurde, verliert
    die Zuordnung der Antworten.
    """
    paths = validation_paths(settings, project)
    codebook = load_codebook(paths.codebook, project)
    if paths.sample.exists() and not force:
        raise CodingError(
            f"{paths.sample} gibt es schon; eine Stichprobe zieht man einmal (--force zieht neu)"
        )
    rules = codebook.sample
    source = population_path(layout, codebook, population)
    if not source.is_file():
        raise MissingInputError(f"Grundgesamtheit {source} fehlt")
    texts = documents_with_text(layout.corpus) if rules.require_text else None
    sample = draw_sample(pl.read_parquet(source), codebook, texts)
    write_sample(
        paths,
        sample.frame,
        {
            "vorhaben": project,
            "codebuch_version": codebook.version,
            "profil": layout.profile,
            "einheit": codebook.unit,
            "grundgesamtheit": source.name
            if population
            else (rules.population or "interim/papers.parquet"),
            "grundgesamtheit_sha256": digest(source),
            "einheiten": sample.population,
            "ohne_text": sample.without_text,
            "groesse": rules.size,
            "seed": rules.seed,
            "schicht": rules.stratum,
            "aufteilung": rules.allocation,
            "selbstgewichtend": sample.self_weighting,
            "schichten": {
                name: {"grundgesamtheit": total, "stichprobe": drawn}
                for name, (total, drawn) in sample.strata.items()
            },
            "gezogen": today.isoformat(),
        },
    )
    return SampleReport(paths.sample, sample)


def read_sample(paths: ValidationPaths, codebook: Codebook) -> pl.DataFrame:
    """Die abgelegte Stichprobe; alles ist Text außer ``start``, ``end`` und ``schicht_n``.

    Ohne Vorgabe rät Polars die Typen, und eine Kennung „010" würde zur Zahl 10.
    """
    if not paths.sample.is_file():
        raise MissingInputError(
            f"{paths.sample} fehlt; `georep validate sample {paths.project}` zieht sie"
        )
    columns = (ID, STRATUM, STRATUM_SIZE, *(t for _, t in sample_columns(codebook)))
    frame = pl.read_csv(paths.sample, infer_schema=False)
    if not has_columns(frame, *columns):
        raise SchemaError(
            f"{paths.sample}: Spalten {list(columns)} erwartet, da sind {frame.columns}"
        )
    return frame.with_columns(
        pl.col(STRATUM).fill_null(""),
        *[pl.col(c).cast(pl.Int64) for c in INTEGER_COLUMNS if c in frame.columns],
    )


def sample_meta(paths: ValidationPaths) -> dict[str, object]:
    """Der Steckbrief der Stichprobe aus ``stichprobe.json``."""
    if not paths.sample_meta.is_file():
        raise MissingInputError(f"{paths.sample_meta} fehlt; die Stichprobe ist unvollständig")
    loaded = json.loads(paths.sample_meta.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SchemaError(f"{paths.sample_meta}: kein JSON-Objekt")
    return loaded
