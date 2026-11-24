"""Lexika: Kategorien mit Mustern, als Paketdatei mit Version (Vorhaben 17, bundespolitisches Vokabular).

Ein Lexikon liegt als ``georep/lexika/<name>.toml`` im Paket: ``[meta]`` mit Name und Version, je
Kategorie ein ``[[kategorie]]`` mit Kennung, Name, Art (``struktur`` zählt für H17.3, ``ereignis``
nur für Ereignisspuren und Sensitivitäten), Definition und Mustern, dazu ``[[lokal]]`` für
Ortsereignisse, die nicht bundespolitisch sind und nicht geprüft (sie werden geladen, aber nicht
gezählt). Das Lexikon ist deutschsprachig, aber nicht städtisch; ein Stadtprofil nennt den Namen der
Datei (``cycles.lexicon``). Jede Änderung ist eine neue Version, und jede Zahl nennt die Version, mit
der sie gerechnet ist (``lexikon`` in jeder Ausgabe, der Hash der Datei im Stamp).

Ein Muster ist ein regulärer Ausdruck in der gemeinsamen Teilmenge von Rust-regex (Polars) und
Python ``re`` (keine Lookarounds). Es läuft wie gemessen (``docs/plans/17-zeit-messung.py``) auf Titel
und Text, beide kleingeschrieben und ohne Zeilenumbrüche wie im Textstore: ein Dokument trägt eine
Kategorie, wenn eines ihrer Muster in ``titel + " " + text`` vorkommt. Polars zählt die Dokumente,
Python ``re`` findet die Stellen für die Spannen; ``parse_lexicon`` übersetzt jedes Muster mit beiden.

**Validiert** ist ein Lexikon erst mit einer Präzision von mindestens 0,9 an 100 kodierten Treffern
(Kriterium des Briefings, Messdokument 17, § 4); bis dahin heißt H17.3 „vorläufig". Die gemessene
Präzision steht in ``VALIDATED`` mit ihrer Quelle; ein slow-Test rechnet sie aus den Labels nach.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources

import deal
import polars as pl

from georep.contracts import one_row_per_document
from georep.errors import SchemaError
from georep.prep.raw_texts import flatten_with_offsets
from georep.spans import SPAN_SCHEMA, empty_spans

__all__ = [
    "EVENT",
    "KINDS",
    "MIN_PRECISION",
    "STRUCTURE",
    "VALIDATED",
    "SPAN_KIND",
    "VOCABULARY_SCHEMA",
    "VOCABULARY_SCHEMA_VERSION",
    "Category",
    "Lexicon",
    "document_categories",
    "find_in_text",
    "load_lexicon",
    "parse_lexicon",
    "validated_precision",
    "vocabulary_spans",
]

VOCABULARY_SCHEMA_VERSION = 1  # dokumente_bundesvokabular.parquet und die Spannen dazu
SPAN_KIND = "bundesvokabular"  # ``kind`` der Spannen; ``norm`` ist die Kategorie
STRUCTURE = "struktur"
EVENT = "ereignis"
LOCAL = "lokal"
KINDS = (STRUCTURE, EVENT)
MIN_PRECISION = 0.9  # Kriterium des Briefings (Meta-Plan, § 11, Vorhaben 17)

# Richtige von gewerteten Treffern je Lexikon und Version. Quelle für bundespolitik 2026-11-23.1:
# validierung/17-zeit/labels.csv (Endlabels zweier KI-Kodierer und eines Schlichters, 2026-11-23),
# Messdokument 17, § 4.1; tests/golden/test_cycles_numbers.py rechnet 94 von 100 dort nach.
VALIDATED: dict[tuple[str, str], tuple[int, int]] = {
    ("bundespolitik", "2026-11-23.1"): (94, 100),
}

VOCABULARY_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "kategorien": pl.List(pl.String()),
    "kopf": pl.List(pl.String()),
    "lexikon": pl.String(),
}


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    kind: str  # ``struktur``, ``ereignis`` oder ``lokal``
    definition: str
    patterns: tuple[str, ...]

    @property
    def pattern(self) -> str:
        """Alle Muster als eine Alternative, jedes in einer Gruppe ohne Fang."""
        return "|".join(f"(?:{m})" for m in self.patterns)


@dataclass(frozen=True)
class Lexicon:
    key: str  # der Dateiname ohne Endung, etwa ``bundespolitik``
    name: str
    version: str
    categories: tuple[Category, ...]  # ``[[kategorie]]`` in Dateifolge
    local: tuple[Category, ...]  # ``[[lokal]]``: geladen, nicht gezählt
    digest: str  # SHA-256 der Datei

    @property
    def label(self) -> str:
        """Name und Version, wie sie an jeder Ausgabe stehen: ``bundespolitik 2026-11-23.1``."""
        return f"{self.key} {self.version}"

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(c.id for c in self.categories)

    def of_kind(self, kind: str) -> tuple[str, ...]:
        return tuple(c.id for c in self.categories if c.kind == kind)


def _category(raw: dict[str, object], kind: str | None, where: str) -> Category:
    for field in ("id", "name", "muster"):
        if field not in raw:
            raise SchemaError(f"{where}: Feld {field} fehlt")
    patterns = raw["muster"]
    if (
        not isinstance(patterns, list)
        or not patterns
        or not all(isinstance(m, str) and m for m in patterns)
    ):
        raise SchemaError(f"{where}: muster ist keine Liste nicht leerer Zeichenketten")
    found_kind = str(raw.get("art", kind or ""))
    if kind is None and found_kind not in KINDS:
        raise SchemaError(f"{where}: art {found_kind!r} ist keine von {', '.join(KINDS)}")
    for m in patterns:
        try:
            re.compile(m)
            pl.Series([""]).str.contains(m)
        except (re.error, pl.exceptions.PolarsError) as error:
            raise SchemaError(f"{where}: Muster {m!r} übersetzt nicht: {error}") from error
    return Category(
        id=str(raw["id"]),
        name=str(raw["name"]),
        kind=found_kind,
        definition=str(raw.get("definition", "")),
        patterns=tuple(patterns),
    )


def parse_lexicon(key: str, text: str) -> Lexicon:
    """Ein Lexikon aus dem Text seiner Datei; ``SchemaError`` nennt, was fehlt oder nicht übersetzt."""
    raw = tomllib.loads(text)
    meta = raw.get("meta", {})
    if not meta.get("version") or not meta.get("name"):
        raise SchemaError(f"Lexikon {key}: [meta] braucht name und version")
    categories = tuple(
        _category(c, None, f"Lexikon {key}, Kategorie {i + 1}")
        for i, c in enumerate(raw.get("kategorie", []))
    )
    local = tuple(
        _category(c, LOCAL, f"Lexikon {key}, lokal {i + 1}")
        for i, c in enumerate(raw.get("lokal", []))
    )
    if not categories:
        raise SchemaError(f"Lexikon {key}: keine [[kategorie]]")
    ids = [c.id for c in (*categories, *local)]
    twice = sorted({i for i in ids if ids.count(i) > 1})
    if twice:
        raise SchemaError(f"Lexikon {key}: Kennungen doppelt: {', '.join(twice)}")
    return Lexicon(
        key=key,
        name=str(meta["name"]),
        version=str(meta["version"]),
        categories=categories,
        local=local,
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def load_lexicon(key: str) -> Lexicon:
    """Das Lexikon ``georep/lexika/<key>.toml`` aus dem Paket."""
    source = resources.files("georep") / "lexika" / f"{key}.toml"
    if not source.is_file():
        raise SchemaError(f"Lexikon {key!r} gibt es nicht im Paket (georep/lexika/{key}.toml)")
    return parse_lexicon(key, source.read_text(encoding="utf-8"))


def validated_precision(lexicon: Lexicon) -> float | None:
    """Die kodierte Präzision dieser Version, sonst ``None`` (dann ist H17.3 vorläufig)."""
    found = VALIDATED.get((lexicon.key, lexicon.version))
    return None if found is None else found[0] / found[1]


def _categories_are_the_lexicon_s(
    corpus: pl.DataFrame,
    lexicon: Lexicon,
    head_chars: int = 2000,
    result: pl.DataFrame | None = None,
) -> bool:
    if result is None or not one_row_per_document(result, corpus.get_column("id").to_list()):
        return False
    order = {c: i for i, c in enumerate(lexicon.ids)}
    for found, head in zip(result.get_column("kategorien"), result.get_column("kopf"), strict=True):
        cats, heads = found.to_list(), head.to_list()
        ranks = [order.get(c, -1) for c in cats]
        if -1 in ranks or ranks != sorted(set(ranks)) or not set(heads) <= set(cats):
            return False
    return True


@deal.pre(
    lambda corpus, lexicon, head_chars=2000: (
        set(corpus.columns) >= {"id", "name", "text"} and head_chars > 0
    ),
    message="Korpus mit id, name, text; head_chars > 0",
)
@deal.ensure(
    _categories_are_the_lexicon_s,
    message="eine Zeile je Korpus-ID; kategorien in Lexikonfolge, eindeutig; kopf ⊆ kategorien",
)
def document_categories(
    corpus: pl.DataFrame, lexicon: Lexicon, head_chars: int = 2000
) -> pl.DataFrame:
    """Je Korpus-ID die Kategorien des Lexikons in Titel und Text und in Titel und Textkopf.

    Wie gemessen: Titel kleingeschrieben, ein Leerzeichen, der Text des Textstores (schon klein und
    ohne Zeilenumbrüche); ``kopf`` liest nur die ersten ``head_chars`` Zeichen des Texts (S3.1). Ein
    Dokument ohne Text trägt, was sein Titel trägt; H17.3 zählt nur Dokumente mit Text.
    """
    title = pl.col("name").fill_null("").str.to_lowercase()
    text = pl.col("text").fill_null("")
    search = title + pl.lit(" ") + text
    head = title + pl.lit(" ") + text.str.slice(0, head_chars)

    def listed(source: pl.Expr) -> pl.Expr:
        return pl.concat_list(
            [pl.when(source.str.contains(c.pattern)).then(pl.lit(c.id)) for c in lexicon.categories]
        ).list.drop_nulls()

    return (
        corpus.select(
            pl.col("id"),
            listed(search).alias("kategorien"),
            listed(head).alias("kopf"),
            pl.lit(lexicon.label).alias("lexikon"),
        )
        .cast(VOCABULARY_SCHEMA)  # type: ignore[arg-type]
        .sort("id")
    )


def find_in_text(text: str, categories: Sequence[Category]) -> list[tuple[int, int, str]]:
    """Die Stellen der Kategorien in einem Text: ``(start, end, kennung)``, nach Stelle sortiert.

    Je Kategorie die nicht überlappenden Treffer ihrer Alternative von links (``re.finditer``), wie
    die Stichprobe der Messung sie zog; zwei Kategorien dürfen dieselbe Stelle treffen.
    """
    found = [
        (m.start(), m.end(), c.id)
        for c in categories
        for m in re.finditer(c.pattern, text)
        if m.end() > m.start()
    ]
    return sorted(found)


def vocabulary_spans(
    documents: pl.DataFrame,
    raw_rows: Mapping[str, Mapping[str, object]],
    marker: str,
    lexicon: Lexicon,
) -> tuple[pl.DataFrame, dict[str, int], int]:
    """Die Treffer des Lexikons im Text als Spannen nach F3, mit Stellen im **Rohtext**.

    ``documents`` trägt je Korpus-ID ``file_name``, ``text`` (den des Textstores) und
    ``kategorien``; ``raw_rows`` ist der Rohtextstore je Dateiname (``RawTextStore.rows``). Gesucht
    wird wie gemessen im kleingeschriebenen Text, je Kategorie des Dokuments; über
    ``flatten_with_offsets`` (Punkt 74) wird eine Stelle ``[i, j)`` dort zu
    ``[offsets[i], offsets[j - 1] + 1)`` im Rohtext, und ``value`` ist der Rohtext an dieser Stelle,
    mit Groß- und Kleinschreibung und einem Zeilenumbruch, wo das Wort über eine Zeile lief.
    ``extractor`` nennt den Rohtext und die Lexikonversion, ``section`` bleibt leer, bis Vorhaben 11
    die Abschnitte bringt. Ein Treffer im Titel ist keine Stelle im Text und keine Spanne.

    Gibt die Spannen, je Dokument mit Spannen die Länge seines Rohtexts (für ``check_spans``) und
    die Zahl der Dokumente mit Kategorie, aber ohne passenden Rohtext (kein Rohtext, oder die
    Plättung ergibt nicht den Text des Textstores, etwa bei einem veralteten Store).
    """
    by_id = {c.id: c for c in lexicon.categories}
    rows: list[tuple[str, int, int, str, str, str, str, str]] = []
    lengths: dict[str, int] = {}
    without = 0
    bridges: dict[str, tuple[int, ...] | None] = {}
    for ident, file_name, text, categories in documents.select(
        "id", "file_name", "text", "kategorien"
    ).iter_rows():
        if not categories or not text:
            continue
        raw_row = raw_rows.get(file_name or "")
        if raw_row is None:
            without += 1
            continue
        raw = str(raw_row["text"])
        if file_name not in bridges:
            stored = raw_row.get("form_feeds")
            feeds = tuple(int(f) for f in stored) if isinstance(stored, list | tuple) else ()
            flat, offsets = flatten_with_offsets(raw, marker, feeds)
            bridges[file_name] = offsets if flat == text else None
        bridge = bridges[file_name]
        if bridge is None:
            without += 1
            continue
        extractor = f"{raw_row['extractor']}; {lexicon.label}"
        for start, end, category in find_in_text(
            text, [by_id[c] for c in categories if c in by_id]
        ):
            first, last = bridge[start], bridge[end - 1] + 1
            rows.append((ident, first, last, SPAN_KIND, raw[first:last], category, "", extractor))
        lengths[ident] = len(raw)
    frame = pl.DataFrame(rows, schema=SPAN_SCHEMA, orient="row") if rows else empty_spans()
    return frame, lengths, without
