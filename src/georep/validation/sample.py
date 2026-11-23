"""Die geschichtete Stichprobe eines Vorhabens (``georep validate sample``, F4).

Gezogen wird ohne Zufallsgenerator: jede Einheit bekommt den Rang sha256(„<seed>|<id>"), und je
Schicht kommen die Einheiten mit den kleinsten Rängen in die Stichprobe (bottom-k). Das ist
reproduzierbar über Rechner und Bibliotheksversionen hinweg (numpy und Polars sichern ihre
Zufallsfolgen nicht über Versionen zu), unabhängig von der Zeilenfolge der Grundgesamtheit und
stabil, wenn sie wächst: eine neue Einheit verdrängt höchstens eine alte ihrer Schicht, statt alle
neu zu mischen (docs/decisions.md, „Validierung mit zwei KI-Kodierern").

Die Aufteilung auf die Schichten (``allocate``) ist rein und ganzzahlig. ``proportional`` gibt
jeder Schicht eine Einheit und verteilt den Rest nach ihrer Größe mit dem Verfahren des größten
Restes; ``equal`` füllt die Schichten gleichmäßig auf, kleine ganz.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
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
    KEY_COLUMNS,
    KEY_SEPARATOR,
    Codebook,
    Unit,
    load_codebook,
)
from georep.validation.paths import ValidationPaths, validation_paths

ID = "id"
STRATUM = "schicht"
Allocation = Literal["proportional", "equal"]
# Spalte der Grundgesamtheit -> Spalte der Stichprobe. ``id`` ist in der Stichprobe immer der
# Schlüssel der Einheit; ein Dokument, das nicht selbst die Einheit ist, heißt darum ``dokument``.
SAMPLE_COLUMNS: dict[Unit, tuple[tuple[str, str], ...]] = {
    "document": (),
    "document_pair": (("id_a", "id_a"), ("id_b", "id_b")),
    "span": (("id", "dokument"), ("start", "start"), ("end", "end")),
    "query_document": (("query", "anfrage"), ("id", "dokument")),
}


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

    ``proportional``: jede Schicht eine Einheit, die übrigen n − H nach den Gewichten N_h − 1
    (was eine Schicht über ihre eine Einheit hinaus hat), abgerundet, die fehlenden an die
    größten Reste, bei gleichem Rest an die alphabetisch erste Schicht. Ein Anteil überschreitet
    seine Schicht nie, weil n ≤ N. ``equal``: die Schichten von der kleinsten zur größten; jede
    nimmt den abgerundeten gleichen Anteil des Rests oder, wenn sie kleiner ist, sich ganz; die
    größten nehmen auf, was die kleinen nicht füllen.
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
    rest = n - len(names)
    weights = {name: sizes[name] - 1 for name in names}
    total = sum(weights.values())
    if total == 0:
        return dict.fromkeys(names, 1)
    floors = {name: rest * weights[name] // total for name in names}
    remainders = {name: rest * weights[name] % total for name in names}
    missing = rest - sum(floors.values())
    lucky = sorted(names, key=lambda name: (-remainders[name], name))[:missing]
    return {name: 1 + floors[name] + (1 if name in lucky else 0) for name in names}


def rank(seed: int, key: str) -> str:
    """Der Rang einer Einheit beim Ziehen: SHA-256 über Seed und Schlüssel, hexadezimal."""
    return hashlib.sha256(f"{seed}{KEY_SEPARATOR}{key}".encode()).hexdigest()


def unit_frame(population: pl.DataFrame, codebook: Codebook) -> pl.DataFrame:
    """Die Grundgesamtheit mit Schlüssel ``id``, den Bestandteilen der Stichprobe und ``schicht``.

    Fehlt eine Spalte, ist ein Bestandteil leer oder trägt er das Trennzeichen, oder kommt ein
    Schlüssel zweimal vor, ist das ein ``SchemaError``: die Grundgesamtheit taugt dann nicht als
    Liste von Einheiten.
    """
    keys = KEY_COLUMNS[codebook.unit]
    stratum = codebook.sample.stratum
    needed = [*keys, *([stratum] if stratum else []), *codebook.text.context]
    missing = [column for column in needed if column not in population.columns]
    if missing:
        raise SchemaError(
            f"Grundgesamtheit ohne Spalten {missing}; die Einheit {codebook.unit} braucht {list(keys)}"
        )
    parts = [pl.col(column).cast(pl.String) for column in keys]
    frame = population.select(
        pl.concat_str(parts, separator=KEY_SEPARATOR).alias("_key"),
        *[pl.col(source).alias(target) for source, target in SAMPLE_COLUMNS[codebook.unit]],
        (pl.col(stratum).cast(pl.String).fill_null("") if stratum else pl.lit("")).alias(STRATUM),
        *[pl.col(column) for column in codebook.text.context],
        *[pl.col(column).alias(f"_doc_{column}") for column in DOCUMENT_COLUMNS[codebook.unit]],
    )
    broken = population.select(
        pl.any_horizontal(
            [
                pl.col(c).is_null()
                | pl.col(c).cast(pl.String).str.contains(KEY_SEPARATOR, literal=True)
                for c in keys
            ]
        )
    ).to_series()
    if bool(broken.any()):
        raise SchemaError(
            f"{int(broken.sum())} Einheiten mit leerem Bestandteil oder {KEY_SEPARATOR!r} darin "
            f"(Spalten {list(keys)})"
        )
    frame = frame.rename({"_key": ID})
    if not unique_keys(frame, ID):
        doubled = frame.filter(pl.col(ID).is_duplicated()).get_column(ID).unique().sort()
        raise SchemaError(
            f"{doubled.len()} Einheiten mehrfach in der Grundgesamtheit, etwa {doubled[0]!r}"
        )
    return frame


@dataclass(frozen=True)
class Sample:
    """Die gezogene Stichprobe und ihre Schichten: Schicht -> (Grundgesamtheit, Stichprobe)."""

    frame: pl.DataFrame  # id, Bestandteile, schicht, Kontextspalten; sortiert nach id
    strata: dict[str, tuple[int, int]]
    population: int  # Einheiten, aus denen gezogen wurde
    without_text: int  # Einheiten, die vorher mangels Text wegfielen


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
    genannten Schichten. Danach gilt: jede Schicht trägt mindestens eine Einheit.
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
        .sort(ID)
    )
    return Sample(
        frame=chosen,
        strata={name: (sizes[name], quota[name]) for name in sorted(sizes)},
        population=frame.height,
        without_text=before - frame.height,
    )


def doc_columns_present(frame: pl.DataFrame, unit: Unit) -> bool:
    """Die Stichprobe trägt die Spalten, aus denen ``tasks`` ihre Dokumente liest."""
    return has_columns(frame, ID, STRATUM, *(target for _, target in SAMPLE_COLUMNS[unit]))


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
        return (
            f"{self.sample.frame.height} Einheiten aus {self.sample.population}{dropped}, "
            f"{strata} Schicht{'en' if strata != 1 else ''} -> {self.path}"
        )


def documents_with_text(corpus: Path) -> frozenset[str]:
    """Die Dokumente des Korpus mit nicht leerem Text."""
    if not corpus.is_file():
        raise MissingInputError(f"{corpus} fehlt; `georep run corpus` baut den Korpus")
    frame = pl.read_parquet(corpus, columns=["id", "text"])
    return frozenset(frame.filter(pl.col("text").str.len_chars() > 0).get_column("id").to_list())


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

    Die Grundgesamtheit ist ``population`` (Befehlszeile), sonst ``sample.population`` relativ
    zum Profilordner, sonst der Korpus. ``stichprobe.csv`` trägt nur Schlüssel und Schichten,
    ``stichprobe.json`` Profil, Prüfsumme der Grundgesamtheit, Seed und Aufteilung; beides
    gehört ins Repo. Eine vorhandene Stichprobe bleibt ohne ``force`` stehen: wer sie neu zieht,
    nachdem kodiert wurde, verliert die Zuordnung der Antworten.
    """
    paths = validation_paths(settings, project)
    codebook = load_codebook(paths.codebook, project)
    if paths.sample.exists() and not force:
        raise CodingError(
            f"{paths.sample} gibt es schon; eine Stichprobe zieht man einmal (--force zieht neu)"
        )
    rules = codebook.sample
    source = population or (layout.root / rules.population if rules.population else layout.corpus)
    if not source.is_file():
        raise MissingInputError(f"Grundgesamtheit {source} fehlt")
    texts = documents_with_text(layout.corpus) if rules.require_text else None
    sample = draw_sample(pl.read_parquet(source), codebook, texts)
    with atomic_path(paths.sample) as tmp:
        sample.frame.write_csv(tmp)
    write_json(
        paths.sample_meta,
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
            "schichten": {
                name: {"grundgesamtheit": total, "stichprobe": drawn}
                for name, (total, drawn) in sample.strata.items()
            },
            "gezogen": today.isoformat(),
        },
    )
    return SampleReport(paths.sample, sample)


def read_sample(paths: ValidationPaths, codebook: Codebook) -> pl.DataFrame:
    """Die abgelegte Stichprobe, mit den Spalten, die ihre Einheit braucht."""
    if not paths.sample.is_file():
        raise MissingInputError(
            f"{paths.sample} fehlt; `georep validate sample {paths.project}` zieht sie"
        )
    columns = (ID, STRATUM, *(target for _, target in SAMPLE_COLUMNS[codebook.unit]))
    frame = pl.read_csv(
        paths.sample,
        schema_overrides=dict.fromkeys(
            (c for c in columns if c not in ("start", "end")), pl.String
        ),
    )
    if not has_columns(frame, *columns):
        raise SchemaError(
            f"{paths.sample}: Spalten {list(columns)} erwartet, da sind {frame.columns}"
        )
    return frame.with_columns(pl.col(STRATUM).fill_null(""))


def sample_meta(paths: ValidationPaths) -> dict[str, object]:
    """Der Steckbrief der Stichprobe aus ``stichprobe.json``."""
    if not paths.sample_meta.is_file():
        raise MissingInputError(f"{paths.sample_meta} fehlt; die Stichprobe ist unvollständig")
    loaded = json.loads(paths.sample_meta.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SchemaError(f"{paths.sample_meta}: kein JSON-Objekt")
    return loaded
