"""Gremium je Ratsdokument aus der Drucksachennummer (Option 5).

``BV6/108/2023`` ist eine Vorlage der Bezirksvertretung 6, ``RAT/270/2023`` eine des Rates,
``OVA/117/2023/1`` ein Nachtrag im Ordnungs- und Verkehrsausschuss: das Kürzel vor dem ersten
Schrägstrich nennt das Gremium, die Nummer dahinter bei Bezirksvertretungen den Stadtbezirk. Muster,
Kürzel und Namen stehen in den Settings (``[bodies]``, docs/plans/05-gremien.md, § 2); ein Kürzel ohne
Tabelle und eine Nummer ohne Muster sind „unbekannt", sichtbar mit Anteil auf der Seite, nie eine
stille Fehlklasse. ``parse_reference`` ist eine reine Funktion über einem vorkompilierten
``BodyRules``-Objekt (hypothesis aus der Grammatik, ``deal.cases``); ``classify_papers`` ist die
Batch-Grenze mit Verträgen und schreibt eine Zeile je Korpus-ID (00-synergien.md, § 5.6).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

import deal
import polars as pl

from georep.contracts import has_columns, sorted_unique
from georep.settings import Bodies

KINDS = ("bezirksvertretung", "rat", "ausschuss", "beirat", "unbekannt")
DISTRICT_BODY, COUNCIL, COMMITTEE, ADVISORY, UNKNOWN = KINDS
KIND_LABELS = {
    DISTRICT_BODY: "Bezirksvertretung",
    COUNCIL: "Rat",
    COMMITTEE: "Ausschuss",
    ADVISORY: "Beirat",
    UNKNOWN: "unbekannt",
}
BODIES_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen von papers_gremien.parquet ändern
# Spaltennamen der Ausgabe; wer sie liest, nennt sie so (georep.analysis.bodies, der Report)
ID = "id"
REFERENCE = "reference"
BODY = "gremium"
KIND = "gremium_art"
CITY_DISTRICT = "stadtbezirk"
BODIES_COLUMNS = [ID, REFERENCE, BODY, KIND, CITY_DISTRICT]
BODIES_SCHEMA = {
    ID: pl.String,
    REFERENCE: pl.String,
    BODY: pl.String,  # Kürzel samt Nummer (BV6, RAT, OVA); null, wenn das Muster nicht trifft
    KIND: pl.String,  # eines aus KINDS
    CITY_DISTRICT: pl.Int64,  # nur bei Bezirksvertretungen
}


@dataclass(frozen=True)
class BodyRef:
    kind: str  # eines aus KINDS
    code: str | None  # Kürzel samt Nummer, etwa "BV6"; None, wenn das Muster nicht trifft
    district: int | None  # Stadtbezirk, genau bei Bezirksvertretungen


@dataclass(frozen=True)
class BodyRules:
    """Die Regeln aus ``[bodies]``, einmal kompiliert; ``from_settings`` ist die einzige Brücke."""

    pattern: re.Pattern[str]
    district_body: str
    district_body_name: str  # mit {n} für den Stadtbezirk
    council: frozenset[str]
    committees: frozenset[str]
    advisory: frozenset[str]
    names: Mapping[str, str]  # Kürzel -> Name; leer = nicht gesichert

    @classmethod
    def from_settings(cls, bodies: Bodies) -> BodyRules:
        return cls(
            pattern=re.compile(bodies.reference_pattern),
            district_body=bodies.district_body,
            district_body_name=bodies.district_body_name,
            council=frozenset(bodies.council),
            committees=frozenset(bodies.committees),
            advisory=frozenset(bodies.advisory),
            names={**bodies.council, **bodies.committees, **bodies.advisory},
        )

    def kind_of(self, code: str) -> str:
        """Die Klasse eines Kürzels ohne Nummer; Bezirksvertretungen entscheidet ``parse_reference``."""
        if code in self.council:
            return COUNCIL
        if code in self.committees:
            return COMMITTEE
        if code in self.advisory:
            return ADVISORY
        return UNKNOWN

    def name_of(self, ref: BodyRef) -> str:
        """Der Name zum Gremium; leer, wenn keiner gesichert ist (die Seite zeigt dann das Kürzel)."""
        if ref.kind == DISTRICT_BODY:
            return self.district_body_name.format(n=ref.district)
        return self.names.get(ref.code or "", "")


def _consistent(result: BodyRef) -> bool:
    return (
        result.kind in KINDS
        and (result.district is not None) == (result.kind == DISTRICT_BODY)
        and (result.district is None or result.district >= 1)
        and (result.code is not None or result.kind == UNKNOWN)
    )


@deal.pure
@deal.post(_consistent, message="Klasse aus KINDS, Stadtbezirk genau bei Bezirksvertretungen, ab 1")
def parse_reference(reference: str | None, rules: BodyRules) -> BodyRef:
    """Das Gremium einer Drucksachennummer; alles Unerwartete ist ``unbekannt``."""
    if reference is None:
        return BodyRef(UNKNOWN, None, None)
    match = rules.pattern.match(reference)
    if match is None:
        return BodyRef(UNKNOWN, None, None)
    code, number = match.group("code"), match.group("number")
    if number is not None and not number.isdecimal():
        return BodyRef(UNKNOWN, f"{code}{number}", None)
    if code == rules.district_body:
        if number is None or int(number) < 1:
            return BodyRef(UNKNOWN, f"{code}{number or ''}", None)
        return BodyRef(DISTRICT_BODY, f"{code}{number}", int(number))
    if number is not None:
        return BodyRef(UNKNOWN, f"{code}{number}", None)
    return BodyRef(rules.kind_of(code), code, None)


def _district_only_for_district_bodies(frame: pl.DataFrame) -> bool:
    is_body = frame.get_column(KIND) == DISTRICT_BODY
    return bool((frame.get_column(CITY_DISTRICT).is_null() != is_body).all())


def _same_ids(corpus: pl.DataFrame, rules: BodyRules, result: pl.DataFrame) -> bool:
    return result.height == corpus.height and set(result.get_column(ID)) == set(
        corpus.get_column(ID)
    )


@deal.pre(
    lambda corpus, rules: has_columns(corpus, ID, REFERENCE),
    message="Korpus mit id und reference",
)
@deal.post(lambda result: result.columns == BODIES_COLUMNS)
@deal.post(lambda result: sorted_unique(result, ID), message="eine Zeile je Korpus-ID, sortiert")
@deal.post(lambda result: set(result.get_column(KIND)) <= set(KINDS))
@deal.post(
    _district_only_for_district_bodies,
    message="stadtbezirk genau bei Bezirksvertretungen gesetzt",
)
@deal.ensure(_same_ids, message="genau die IDs des Korpus")
def classify_papers(corpus: pl.DataFrame, rules: BodyRules) -> pl.DataFrame:
    """Eine Zeile je Dokument: Kürzel, Klasse und Stadtbezirk aus der Drucksachennummer."""
    refs = [parse_reference(r, rules) for r in corpus.get_column(REFERENCE).to_list()]
    return pl.DataFrame(
        {
            ID: corpus.get_column(ID),
            REFERENCE: corpus.get_column(REFERENCE),
            BODY: [r.code for r in refs],
            KIND: [r.kind for r in refs],
            CITY_DISTRICT: [r.district for r in refs],
        },
        schema=BODIES_SCHEMA,
    ).sort(ID)


@deal.pre(lambda frame: has_columns(frame, KIND))
@deal.post(lambda result: tuple(result) == KINDS, message="jede Klasse kommt vor, auch mit 0")
def counts_by_kind(frame: pl.DataFrame) -> dict[str, int]:
    counted = dict(frame.group_by(KIND).len().iter_rows())
    return {kind: int(counted.get(kind, 0)) for kind in KINDS}


def summary(frame: pl.DataFrame) -> str:
    """Die Rückgabezeile des Schritts ``bodies``."""
    counts = counts_by_kind(frame)
    parts = ", ".join(f"{counts[kind]} {KIND_LABELS[kind]}" for kind in KINDS)
    return f"{frame.height} Dokumente: {parts}"
