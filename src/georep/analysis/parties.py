"""Urheber je Ratsdokument und daraus die Kennzahlen je Partei und Wahlbezirk.

Der OParl-Server der ITK Rheinland liefert für Düsseldorf keine Urheberfelder (0 von 19 108
Rohobjekten, Befund vom 2026-10-09 in ``tests/fixtures/oparl/papers_page.json``). Der Urheber steht
stattdessen in drei vorhandenen Feldern, und genau in dieser Reihenfolge wird gefragt:

1. ``oparl``: ``originatorOrganization`` über die Organisations-URLs der Settings und, wenn
   ``raw/organizations.json`` vorliegt, über die Namen der Organisationen. Greift ohne
   Codeänderung, sobald der Server die Felder füllt.
2. ``paper_type``: „Anfrage SPD", „Antrag CDU/Grüne" nennen die Fraktion im Typ; die Vorlagen der
   Verwaltung und die Eingaben nach § 24 GO NRW stehen als ganze Werte in den Settings.
3. ``name``: „Antrag der SPD-Fraktion"; befragt wird der Titel nur, wenn ein Fraktionsmarker
   darin steht, sonst zählte „die cdu-fraktion beantragt" in einer Verwaltungsvorlage mit.
4. ``text``: ein Fenster um „antrag|anfrage … fraktion" in den ersten Zeichen nach „betrifft".

Die erste Quelle mit Parteitreffer gewinnt, die anderen werden nicht mehr befragt. ``urheber_art``
ist eine Partition (genau eine Klasse je Dokument), ``parteien`` eine sortierte Menge von
Settings-Schlüsseln, bei Nicht-Fraktionen leer. Alle Muster stehen in ``defaults.toml`` unter
``[originators]``, nichts davon im Code (Vorbereitung für Option 10).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace

import deal
import polars as pl
from polars._typing import PolarsDataType

from georep.contracts import has_columns, one_row_per_document
from georep.oparl import OparlOrganization
from georep.settings import Originators, Party

# Die Partition: genau eine Klasse je Dokument, ihre Summe ist die Zahl der Dokumente.
URHEBER_ARTEN = ("Verwaltung", "Fraktion", "Person", "Eingabe", "unbekannt")
# Spaltennamen der Partition in den Bezirkstabellen, in derselben Reihenfolge wie URHEBER_ARTEN.
KLASSEN_SPALTEN = ("verwaltung", "fraktion", "person", "eingabe", "unbekannt")
QUELLEN = ("oparl", "paper_type", "name", "text", "")
ART = "urheber_art"
PARTEIEN = "parteien"
QUELLE = "quelle"
TREFFER = "treffer"
PARTEI = "partei"
EXCERPT_PAD = 30  # Zeichen links und rechts um den Treffer in der Spalte ``treffer``

ATTRIBUTION_SCHEMA: dict[str, PolarsDataType] = {
    "id": pl.String,
    ART: pl.String,
    PARTEIEN: pl.List(pl.String),
    QUELLE: pl.String,
    TREFFER: pl.String,
}


@dataclass(frozen=True)
class Classification:
    """Die Zuordnung eines Dokuments: Klasse, Parteien, Quelle und die getroffene Zeichenkette."""

    art: str
    parteien: tuple[str, ...]
    quelle: str
    treffer: str


@dataclass(frozen=True)
class Patterns:
    """Die Muster aus ``[originators]``, einmal übersetzt.

    ``classify_document`` läuft je Dokument, also 19 108 Mal; ``re.compile`` je Aufruf wäre der
    teuerste Teil des Schritts. ``from_settings`` baut die Struktur einmal, ``with_organizations``
    hängt die Abbildung aus ``raw/organizations.json`` an.
    """

    admin_types: frozenset[str]
    citizen_types: frozenset[str]
    motion_prefixes: tuple[str, ...]  # längste zuerst, damit „Haushaltsantrag" vor „Antrag" greift
    fraction: re.Pattern[str] | None
    joint: re.Pattern[str] | None
    person: re.Pattern[str] | None
    text: re.Pattern[str] | None
    parties: tuple[
        tuple[str, re.Pattern[str]], ...
    ]  # Schlüssel -> Muster, Reihenfolge der Settings
    org_suffixes: tuple[tuple[str, str], ...]  # URL-Endung -> Schlüssel, aus den Settings
    org_exact: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # URL -> Schlüssel
    head_chars: int = 600
    window_chars: int = 80

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.parties)

    @classmethod
    def from_settings(cls, originators: Originators) -> Patterns:
        return cls(
            admin_types=frozenset(originators.admin_types),
            citizen_types=frozenset(originators.citizen_types),
            motion_prefixes=tuple(
                sorted((p.lower() for p in originators.motion_prefixes), key=len, reverse=True)
            ),
            fraction=_any_of(originators.fraction_markers),
            joint=_any_of(originators.joint_markers),
            person=_any_of(originators.person_markers),
            text=_any_of(originators.text_markers),
            parties=tuple(
                (p.key, _alternation(p.patterns))
                for p in (*originators.parties, *originators.groups)
            ),
            org_suffixes=tuple(
                (url, p.key)
                for p in (*originators.parties, *originators.groups)
                for url in p.organizations
            ),
            head_chars=originators.text_head_chars,
            window_chars=originators.text_window_chars,
        )

    def with_organizations(self, organizations: Iterable[OparlOrganization]) -> Patterns:
        """Dieselben Muster, dazu die URL-zu-Partei-Abbildung aus der Organisationsseite.

        Der Name und das Kürzel jeder Organisation werden mit den Parteimustern verglichen; so
        findet „Ratsfraktion SPD/Volt" die Schlüssel SPD und VOLT, ohne dass die URL in den
        Settings stehen muss. Gelöschte Organisationen bleiben draußen.
        """
        exact: dict[str, tuple[str, ...]] = {}
        for organization in organizations:
            if organization.deleted:
                continue
            haystack = " ".join(
                part for part in (organization.name, organization.short_name) if part
            ).lower()
            found = tuple(key for key, pattern in self.parties if pattern.search(haystack))
            if found:
                exact[organization.id] = found
        return replace(self, org_exact=exact)

    def parties_for_urls(self, urls: Sequence[str]) -> tuple[tuple[str, ...], str]:
        """(Parteischlüssel, getroffene URL) für OParl-Urheber-URLs; leer, wenn keine zuordbar ist."""
        found: set[str] = set()
        matched: list[str] = []
        for url in urls:
            keys = self.org_exact.get(url, ())
            if not keys:
                keys = tuple(key for suffix, key in self.org_suffixes if url.endswith(suffix))
            if keys:
                found.update(keys)
                matched.append(url)
        return tuple(sorted(found, key=self.keys.index)), " ".join(matched)


def _any_of(patterns: Sequence[str]) -> re.Pattern[str] | None:
    """Ein Muster aus allen Markern; ``None``, wenn keine konfiguriert sind (Marker aus Settings)."""
    return re.compile("|".join(f"(?:{p})" for p in patterns)) if patterns else None


def _alternation(patterns: Sequence[str]) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns))


def _excerpt(haystack: str, start: int, end: int, pad: int = EXCERPT_PAD) -> str:
    """Der Treffer mit ``pad`` Zeichen Umgebung, damit jede Zuordnung von Hand prüfbar ist."""
    return haystack[max(0, start - pad) : end + pad].strip()


def _parties_in(haystack: str, patterns: Patterns) -> tuple[tuple[str, ...], str]:
    """(Schlüssel in der Reihenfolge der Settings, Auszug um den ersten Treffer)."""
    found: list[str] = []
    first: tuple[int, int] | None = None
    for key, pattern in patterns.parties:
        match = pattern.search(haystack)
        if match is None:
            continue
        found.append(key)
        if first is None or match.start() < first[0]:
            first = (match.start(), match.end())
    if first is None:
        return (), ""
    return tuple(found), _excerpt(haystack, *first)


def _attribution_is_consistent(
    paper_type: str | None,
    name: str | None,
    text_head: str,
    patterns: Patterns,
    originator_organizations: Sequence[str] = (),
    result: Classification | None = None,
) -> bool:
    assert result is not None
    parteien = result.parteien
    return (
        result.art in URHEBER_ARTEN
        and result.quelle in QUELLEN
        and list(parteien) == sorted(set(parteien), key=patterns.keys.index)
        and set(parteien) <= set(patterns.keys)
        and (result.art == "Fraktion" or not parteien)
        and (result.quelle != "" or result.art == "unbekannt")
    )


# deal.safe statt deal.pure: deals has()-Patcher fasst socket und stdout prozessweit an und ist
# nicht reentrant, und diese Funktion läuft je Dokument (CLAUDE.md, „Nie"). Die Vor- und
# Nachbedingungen bleiben und machen sie zum Kandidaten für crosshair (nox -s verify).
@deal.safe
@deal.pre(
    lambda paper_type, name, text_head, patterns, originator_organizations=(): (
        patterns.head_chars > 0 and patterns.window_chars > 0
    )
)
@deal.ensure(_attribution_is_consistent, message="eine Klasse, sortierte Parteien aus den Settings")
def classify_document(
    paper_type: str | None,
    name: str | None,
    text_head: str,
    patterns: Patterns,
    originator_organizations: Sequence[str] = (),
) -> Classification:
    """Die Zuordnung eines Dokuments; rein, nur aus den vier Feldern und den Mustern.

    ``text_head`` ist schon auf ``patterns.head_chars`` gekürzt und kleingeschrieben (so liegt der
    Text im Korpus); ``paper_type`` wird als ganzer Wert verglichen und sonst kleingeschrieben.
    """
    keys, url = patterns.parties_for_urls(originator_organizations)
    if keys:
        return Classification("Fraktion", keys, "oparl", url)

    typ = paper_type or ""
    if typ in patterns.admin_types:
        return Classification("Verwaltung", (), "paper_type", typ)
    if typ in patterns.citizen_types:
        return Classification("Eingabe", (), "paper_type", typ)
    rest = _without_prefix(typ.lower(), patterns.motion_prefixes)
    if rest:
        keys, hit = _parties_in(rest, patterns)
        if keys:
            return Classification("Fraktion", keys, "paper_type", hit)

    title = (name or "").lower()
    if patterns.fraction is not None and patterns.fraction.search(title):
        keys, hit = _parties_in(title, patterns)
        if keys:
            return Classification("Fraktion", keys, "name", hit)
        joint = patterns.joint.search(title) if patterns.joint is not None else None
        if joint is not None:
            return Classification("Fraktion", (), "name", _excerpt(title, *joint.span()))

    head = text_head[: patterns.head_chars]
    found = patterns.text.search(head) if patterns.text is not None else None
    if found is not None:
        pad = patterns.window_chars
        window = head[max(0, found.start() - pad) : found.end() + pad]
        keys, hit = _parties_in(window, patterns)
        if keys:
            return Classification("Fraktion", keys, "text", hit)
        return Classification("Fraktion", (), "text", _excerpt(head, *found.span()))

    person = patterns.person.search(title) if patterns.person is not None else None
    if person is not None:
        return Classification("Person", (), "name", _excerpt(title, *person.span()))
    return Classification("unbekannt", (), "", "")


def _without_prefix(value: str, prefixes: Sequence[str]) -> str:
    """``"haushaltsantrag cdu/grüne"`` ohne das längste passende Präfix: ``"cdu/grüne"``."""
    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix) :].strip()
    return value


def _one_row_per_corpus_id(
    corpus: pl.DataFrame,
    originators: Originators,
    organizations: Sequence[OparlOrganization] = (),
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return one_row_per_document(result, corpus.get_column("id").to_list())


def _classes_and_parties_are_from_the_settings(
    corpus: pl.DataFrame,
    originators: Originators,
    organizations: Sequence[OparlOrganization] = (),
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    keys = set(originators.all_keys)
    arten = set(result.get_column(ART).unique().to_list())
    quellen = set(result.get_column(QUELLE).unique().to_list())
    parteien = result.get_column(PARTEIEN).to_list()
    return (
        arten <= set(URHEBER_ARTEN)
        and quellen <= set(QUELLEN)
        and all(set(items) <= keys for items in parteien)
        and all(len(items) == len(set(items)) for items in parteien)
    )


def _only_fractions_name_parties(
    corpus: pl.DataFrame,
    originators: Originators,
    organizations: Sequence[OparlOrganization] = (),
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    other = result.filter(pl.col(ART) != "Fraktion")
    return bool((other.get_column(PARTEIEN).list.len() == 0).all())


@deal.pre(
    lambda corpus, originators, organizations=(): has_columns(
        corpus, "id", "paper_type", "name", "text"
    )
)
@deal.ensure(_one_row_per_corpus_id, message="eine Zeile je Korpus-ID, in Korpus-Reihenfolge")
@deal.ensure(
    _classes_and_parties_are_from_the_settings, message="Klassen und Parteien aus den Settings"
)
@deal.ensure(_only_fractions_name_parties, message="nur Fraktionen nennen Parteien")
def classify_originators(
    corpus: pl.DataFrame,
    originators: Originators,
    organizations: Sequence[OparlOrganization] = (),
) -> pl.DataFrame:
    """Je Korpus-ID die Klasse, die Parteien, die Quelle und die getroffene Zeichenkette.

    ``organizations`` sind die Objekte aus ``raw/organizations.json``, falls der Netzschritt
    ``organizations`` lief; ohne sie greifen nur die URL-Endungen aus den Settings, und der Schritt
    läuft auch aus der Referenz.
    """
    patterns = Patterns.from_settings(originators).with_organizations(organizations)
    needed = corpus.select(
        "id",
        "paper_type",
        "name",
        pl.col("text").str.slice(0, patterns.head_chars).alias("head"),
        *(
            [pl.col("originator_organization")]
            if "originator_organization" in corpus.columns
            else [pl.lit([], dtype=pl.List(pl.String)).alias("originator_organization")]
        ),
    ).sort("id")
    rows = [
        (
            row["id"],
            *_as_tuple(
                classify_document(
                    row["paper_type"],
                    row["name"],
                    row["head"] or "",
                    patterns,
                    row["originator_organization"] or (),
                )
            ),
        )
        for row in needed.iter_rows(named=True)
    ]
    return pl.DataFrame(rows, schema=ATTRIBUTION_SCHEMA, orient="row")


def _as_tuple(found: Classification) -> tuple[str, list[str], str, str]:
    return found.art, list(found.parteien), found.quelle, found.treffer


def originator_figures(attribution: pl.DataFrame) -> dict[str, int]:
    """Zähler je Klasse über alle Dokumente, jede Klasse mit Eintrag (auch die leeren)."""
    found = attribution.group_by(ART).len()
    by_class = dict(
        zip(found.get_column(ART).to_list(), found.get_column("len").to_list(), strict=True)
    )
    return {art: int(by_class.get(art, 0)) for art in URHEBER_ARTEN}


def documents_per_party(attribution: pl.DataFrame, parties: Iterable[Party]) -> dict[str, int]:
    """Dokumente je Partei (Mehrfachnennung: ein Papier mit zwei Parteien zählt für beide)."""
    exploded = attribution.select(pl.col(PARTEIEN).explode().alias(PARTEI)).drop_nulls()
    found = exploded.group_by(PARTEI).len()
    counts = dict(
        zip(found.get_column(PARTEI).to_list(), found.get_column("len").to_list(), strict=True)
    )
    return {p.key: int(counts.get(p.key, 0)) for p in parties}
