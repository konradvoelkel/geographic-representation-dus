"""Antragsteller je Fraktionsdokument, ihre Fraktionen und das Lager zur Ratsmehrheit (Vorhaben 15).

``parteien`` aus Option 04 nimmt die erste Quelle mit Treffer (Punkte 59 bis 64): bei „Haushaltsantrag
CDU/Grüne" die Dokumentart, auch wenn der Titel drei Fraktionen nennt, und bei einem Titel den
ganzen Titel samt Gegenstand („Antrag Die Linke: AfD keine Plattform geben"). Für gemeinsame
Anträge reicht das nicht: es übersieht bei 281 Dokumenten Mitantragsteller (Messdokument
``docs/plans/15-funktion.md``, § 3.8). Die **Antragsteller** hier sind darum die Vereinigung aus

1. den Parteien der Dokumentart hinter dem Antragspräfix (``originators.motion_prefixes``);
2. dem **Autorenteil des Titels**: vom ersten Instrumentwort bis zum ersten Trenner;
3. dem **Verfasserblock eines Briefkopfs** (eine alte Vorlagenform, ``functions.letterhead``).

Nennt keiner der drei eine Partei, bleibt ``parteien``. Gegen zwei KI-Kodierer: Präzision
119/119, Recall 119/138 (§ 4.1). ``analysis/parties.py`` bleibt unverändert (Frage 25 an Konrad).

Danach werden Parteien zu **Fraktionen** (``functions.fractions``, mit Zeitraum: die Ratsfraktion
SPD/Volt ist eine Fraktion, keine Zusammenarbeit), und jedes Dokument bekommt ein **Lager**
gegenüber der Ratsmehrheit an seinem Datum (``[majorities]``), nur in den Gremienarten, in denen
die Mehrheit des Rates gilt. Die Mehrheit ist eine Annahme mit Quelle, nicht aus den gemeinsamen
Anträgen abgeleitet (§ 3.9).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import deal
import polars as pl
from polars._typing import PolarsDataType

from georep.analysis.parties import Patterns
from georep.contracts import has_columns, one_row_per_document
from georep.errors import SchemaError
from georep.settings import Fraction, Majorities, Settings

# Version 1: id, antragsteller, fraktionen, quelle, gemeinsam, lager (Messdokument § 6 und § 10).
COSPONSORS_SCHEMA_VERSION = (
    1  # erhöhen, wenn sich Spalten oder Typen von dokumente_antragsteller ändern
)
ANTRAGSTELLER = "antragsteller"
FRAKTIONEN = "fraktionen"
QUELLE = "quelle"
GEMEINSAM = "gemeinsam"
LAGER = "lager"
FRACTION_CLASS = "Fraktion"  # die Urheberklasse aus ``analysis.parties.URHEBER_ARTEN``
# Woher ein Antragsteller kommt; mehrere mit „+" in dieser Folge, ``parteien`` nur allein.
PARTS = ("art", "titel", "briefkopf")
FROM_ORIGINATORS = "parteien"
# Das Lager eines Dokuments gegenüber der Ratsmehrheit (§ 3.11). ``ohne_partei``: keine Fraktion
# genannt (jede Urheberklasse außer einer Fraktion mit Namen); ``ohne_lager``: das Gremium liegt
# nicht dort, wo die Mehrheit des Rates gilt, oder das Profil kennt für das Datum keine Mehrheit.
CAMPS = (
    "allein_mehrheit",
    "allein_opposition",
    "gemeinsam_mehrheit",
    "gemeinsam_opposition",
    "ueber_grenze",
    "ohne_partei",
    "ohne_lager",
)
ALONE_MAJORITY, ALONE_OPPOSITION, JOINT_MAJORITY, JOINT_OPPOSITION, ACROSS, NO_PARTY, NO_CAMP = (
    CAMPS
)

COSPONSORS_SCHEMA: dict[str, PolarsDataType] = {
    "id": pl.String,
    ANTRAGSTELLER: pl.List(pl.String),
    FRAKTIONEN: pl.List(pl.String),
    QUELLE: pl.String,
    GEMEINSAM: pl.Boolean,
    LAGER: pl.String,
}


def _alternation(patterns: Sequence[str]) -> re.Pattern[str] | None:
    return re.compile("|".join(f"(?:{p})" for p in patterns)) if patterns else None


@dataclass(frozen=True)
class CosponsorRules:
    """Die Muster aus ``[originators]``, ``[functions]`` und ``[majorities]``, einmal übersetzt."""

    parties: tuple[tuple[str, re.Pattern[str]], ...]  # Schlüssel -> Muster, Folge der Settings
    motion_prefixes: tuple[str, ...]  # klein, längstes zuerst
    author_start: re.Pattern[str] | None
    author_stop: re.Pattern[str] | None
    letterhead: re.Pattern[str] | None
    letterhead_end: re.Pattern[str] | None
    head_chars: int
    letterhead_chars: int
    fractions: tuple[Fraction, ...]
    majorities: Majorities

    @property
    def order(self) -> Mapping[str, int]:
        return {key: index for index, (key, _) in enumerate(self.parties)}

    @classmethod
    def from_settings(cls, settings: Settings) -> CosponsorRules:
        """Aus den Settings; ``SchemaError``, wenn Fraktion oder Mehrheit eine fremde Partei nennt."""
        patterns = Patterns.from_settings(settings.originators)
        known = set(patterns.keys)
        named = {
            **{f"functions.fractions {f.key}": f.parties for f in settings.functions.fractions},
            **{f"majorities {m.period}": m.parties for m in settings.majorities.terms},
        }
        for where, parties in named.items():
            unknown = sorted(set(parties) - known)
            if unknown:
                raise SchemaError(f"{where}: {unknown} stehen nicht in [originators]")
        functions = settings.functions
        return cls(
            parties=patterns.parties,
            motion_prefixes=patterns.motion_prefixes,
            author_start=_alternation(functions.author_start),
            author_stop=_alternation(functions.author_stop),
            letterhead=_alternation(functions.letterhead),
            letterhead_end=_alternation(functions.letterhead_end),
            head_chars=functions.head_chars,
            letterhead_chars=functions.letterhead_chars,
            fractions=tuple(functions.fractions),
            majorities=settings.majorities,
        )


def author_part(title: str, rules: CosponsorRules) -> str | None:
    """Der Autorenteil eines Titels: vom ersten Instrumentwort bis zum ersten Trenner danach.

    „änderungsantrag der spd-ratsfraktion zum antrag der ratsfraktionen von cdu und grünen" gibt
    „änderungsantrag der spd-ratsfraktion"; ohne Instrumentwort ``None``.
    """
    found = rules.author_start.search(title) if rules.author_start is not None else None
    if found is None:
        return None
    rest = title[found.start() :]
    cut = (
        rules.author_stop.search(rest, found.end() - found.start())
        if rules.author_stop is not None
        else None
    )
    return rest[: cut.start()] if cut is not None else rest


def letterhead_authors(text: str | None, rules: CosponsorRules) -> str | None:
    """Der Verfasserblock eines Briefkopfs: hinter dem Kopf, vor Gremium, Anrede oder Datum.

    „… nicht öffentlich  spd - fraktion  cdu - fraktion  der bezirksvertretung 8  an den
    bezirksbürgermeister …" gibt die beiden Fraktionen; der Betreff dahinter zählt nicht.
    """
    head = (text or "")[: rules.head_chars]
    found = rules.letterhead.search(head) if rules.letterhead is not None else None
    if found is None:
        return None
    segment = head[found.end() : found.end() + rules.letterhead_chars]
    cut = rules.letterhead_end.search(segment) if rules.letterhead_end is not None else None
    return segment[: cut.start()] if cut is not None else segment


def _type_rest(paper_type: str | None, prefixes: Sequence[str]) -> str:
    """„haushaltsantrag cdu/grüne" ohne das längste passende Präfix."""
    low = (paper_type or "").lower()
    for prefix in prefixes:
        if low.startswith(prefix):
            return low[len(prefix) :].strip()
    return low


def _keys_in(haystack: str | None, rules: CosponsorRules) -> list[str]:
    if not haystack:
        return []
    return [key for key, pattern in rules.parties if pattern.search(haystack)]


def _cosponsors_are_known_and_ordered(
    paper_type: str | None,
    name: str | None,
    text: str | None,
    originator_class: str | None,
    parteien: Sequence[str],
    rules: CosponsorRules,
    result: tuple[tuple[str, ...], str] | None = None,
) -> bool:
    assert result is not None
    keys, source = result
    order = rules.order
    known = all(k in order for k in keys) and list(keys) == sorted(set(keys), key=order.__getitem__)
    sources_ok = source in ("", FROM_ORIGINATORS) or all(
        part in PARTS for part in source.split("+")
    )
    return (
        known
        and sources_ok
        and (originator_class == FRACTION_CLASS or keys == ())
        and (source == "") == (keys == ())
    )


@deal.safe
@deal.ensure(
    _cosponsors_are_known_and_ordered, message="Schlüssel aus den Settings, in ihrer Folge"
)
def cosponsors(
    paper_type: str | None,
    name: str | None,
    text: str | None,
    originator_class: str | None,
    parteien: Sequence[str],
    rules: CosponsorRules,
) -> tuple[tuple[str, ...], str]:
    """(Antragsteller, Quelle) eines Dokuments; leer, wenn die Urheberklasse keine Fraktion ist.

    Die Antragsteller sind die Vereinigung aus Dokumentart, Autorenteil des Titels und
    Verfasserblock des Briefkopfs, in der Folge der Settings; nennt keiner eine Partei, bleibt
    ``parteien`` aus Option 04 (Quelle „parteien"). Die Quelle nennt die Teile mit Treffer.
    """
    if originator_class != FRACTION_CLASS:
        return (), ""
    order = rules.order
    found = {
        "art": _keys_in(_type_rest(paper_type, rules.motion_prefixes), rules),
        "titel": _keys_in(author_part((name or "").lower(), rules), rules),
        "briefkopf": _keys_in(letterhead_authors(text, rules), rules),
    }
    union = {key for keys in found.values() for key in keys}
    if not union:
        before = tuple(sorted({k for k in parteien if k in order}, key=order.__getitem__))
        return before, FROM_ORIGINATORS if before else ""
    source = "+".join(part for part in PARTS if found[part])
    return tuple(sorted(union, key=order.__getitem__)), source


def fractions_on(
    parties: Sequence[str],
    day: date | None,
    fractions: Sequence[Fraction],
    order: Mapping[str, int],
) -> tuple[str, ...]:
    """Die Fraktionen zu Parteischlüsseln an einem Tag, eindeutig, in der Folge der Settings.

    Eine Partei, die an diesem Tag zu einer Fraktion aus mehreren Parteien gehört, wird deren
    Schlüssel („SPD+VOLT" ab 2020-11-01); sonst bleibt sie ihre eigene Fraktion. Ohne Datum
    wird nichts zusammengefasst. Die Folge: die erste Partei einer Fraktion in den Settings.
    """
    held = [f for f in fractions if day is not None and f.holds_on(day)]
    unit = {party: f.key for f in held for party in f.parties}
    members = {f.key: f.parties for f in held}

    def rank(key: str) -> int:
        return min(order.get(p, len(order)) for p in members.get(key, [key]))

    return tuple(sorted({unit.get(p, p) for p in parties}, key=lambda k: (rank(k), k)))


def _camp_is_known(
    fractions: Sequence[str], majority: Collection[str] | None, result: str | None = None
) -> bool:
    assert result is not None
    return result in CAMPS and (result == NO_CAMP) == (majority is None)


@deal.safe
@deal.ensure(_camp_is_known, message="eines der sieben Lager; ohne Mehrheit ohne_lager")
def camp(fractions: Sequence[str], majority: Collection[str] | None) -> str:
    """Das Lager eines Dokuments mit diesen Fraktionen gegenüber der Mehrheit.

    ``majority`` sind die Fraktionen der Mehrheit, ``None`` heißt: hier gilt keine (Gremium
    außerhalb der Stadtebene oder kein Zeitraum im Profil). Eine Fraktion der Mehrheit und eine
    der Opposition zusammen sind „über die Grenze".
    """
    if majority is None:
        return NO_CAMP
    distinct = set(fractions)
    if not distinct:
        return NO_PARTY
    inside = {f in majority for f in distinct}
    if len(distinct) == 1:
        return ALONE_MAJORITY if inside == {True} else ALONE_OPPOSITION
    if inside == {True}:
        return JOINT_MAJORITY
    if inside == {False}:
        return JOINT_OPPOSITION
    return ACROSS


def _one_row_per_corpus_id(
    corpus: pl.DataFrame,
    originators: pl.DataFrame,
    bodies: pl.DataFrame,
    rules: CosponsorRules,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return one_row_per_document(result, corpus.get_column("id").to_list())


def _rows_are_consistent(
    corpus: pl.DataFrame,
    originators: pl.DataFrame,
    bodies: pl.DataFrame,
    rules: CosponsorRules,
    result: pl.DataFrame | None = None,
) -> bool:
    """Schema; ``gemeinsam`` genau bei zwei Fraktionen; nur Fraktionen haben Antragsteller."""
    assert result is not None
    fraction_ids = set(
        originators.filter(pl.col("urheber_art") == FRACTION_CLASS).get_column("id").to_list()
    )
    with_cosponsors = set(
        result.filter(pl.col(ANTRAGSTELLER).list.len() > 0).get_column("id").to_list()
    )
    return (
        result.schema == pl.Schema(COSPONSORS_SCHEMA)
        and bool(
            (result.get_column(GEMEINSAM) == (result.get_column(FRAKTIONEN).list.len() >= 2)).all()
        )
        and set(result.get_column(LAGER).unique().to_list()) <= set(CAMPS)
        and with_cosponsors <= fraction_ids
    )


def _fractions_are_the_image(
    corpus: pl.DataFrame,
    originators: pl.DataFrame,
    bodies: pl.DataFrame,
    rules: CosponsorRules,
    result: pl.DataFrame | None = None,
) -> bool:
    """``fraktionen`` ist das Bild von ``antragsteller`` unter der Fraktionstabelle am Datum.

    Unabhängig von ``fractions_on`` gerechnet, sonst prüfte der Vertrag die Funktion mit sich
    selbst (Bauplan § 6, Review 2026-11-24).
    """
    assert result is not None
    days = dict(corpus.select("id", "date").iter_rows())
    for doc_id, keys, fractions in result.select("id", ANTRAGSTELLER, FRAKTIONEN).iter_rows():
        day = days.get(doc_id)
        held = [f for f in rules.fractions if day is not None and f.holds_on(day)]
        image = {next((f.key for f in held if key in f.parties), key) for key in keys}
        if len(fractions) != len(set(fractions)) or set(fractions) != image:
            return False
    return True


def _camp_only_where_a_majority_holds(
    corpus: pl.DataFrame,
    originators: pl.DataFrame,
    bodies: pl.DataFrame,
    rules: CosponsorRules,
    result: pl.DataFrame | None = None,
) -> bool:
    """``ohne_lager`` genau dort, wo das Gremium nicht auf der Stadtebene liegt oder das Profil
    für das Datum keine Mehrheit kennt (Bauplan § 6, Review 2026-11-24)."""
    assert result is not None
    days = dict(corpus.select("id", "date").iter_rows())
    kinds = dict(bodies.select("id", "gremium_art").iter_rows())
    levels = set(rules.majorities.body_kinds)
    return all(
        (lager == NO_CAMP)
        != (kinds.get(doc_id) in levels and rules.majorities.on(days.get(doc_id)) is not None)
        for doc_id, lager in result.select("id", LAGER).iter_rows()
    )


@deal.pre(
    lambda corpus, originators, bodies, rules: (
        has_columns(corpus, "id", "date", "paper_type", "name", "text")
        and has_columns(originators, "id", "urheber_art", "parteien")
        and has_columns(bodies, "id", "gremium_art")
    )
)
@deal.ensure(_one_row_per_corpus_id, message="eine Zeile je Korpus-ID, nach id sortiert")
@deal.ensure(_rows_are_consistent, message="Schema, gemeinsam, Lager, nur Fraktionen")
@deal.ensure(_fractions_are_the_image, message="fraktionen ist das Bild der Antragsteller am Datum")
@deal.ensure(
    _camp_only_where_a_majority_holds,
    message="ohne_lager genau dort, wo keine Mehrheit des Rates gilt",
)
def classify_cosponsors(
    corpus: pl.DataFrame,
    originators: pl.DataFrame,
    bodies: pl.DataFrame,
    rules: CosponsorRules,
) -> pl.DataFrame:
    """Je Korpus-ID Antragsteller, Fraktionen, Quelle, gemeinsam, Lager (``dokumente_antragsteller``).

    ``originators`` ist ``dokumente_urheber`` (Option 04), ``bodies`` ist ``papers_gremien``
    (Option 05); ein Dokument ohne Zeile dort hat Urheber „unbekannt" beziehungsweise kein
    Gremium, also kein Lager.
    """
    order = rules.order
    kinds = set(rules.majorities.body_kinds)
    needed = (
        corpus.select(
            "id",
            "date",
            "paper_type",
            "name",
            pl.col("text").str.slice(0, rules.head_chars).alias("text"),
        )
        .join(originators.select("id", "urheber_art", "parteien"), on="id", how="left")
        .join(bodies.select("id", "gremium_art"), on="id", how="left")
        .sort("id")
    )
    rows = []
    for doc_id, day, paper_type, name, text, origin, parteien, kind in needed.iter_rows():
        keys, source = cosponsors(paper_type, name, text, origin, parteien or (), rules)
        fractions = fractions_on(keys, day, rules.fractions, order)
        term = rules.majorities.on(day) if kind in kinds else None
        majority = None if term is None else fractions_on(term.parties, day, rules.fractions, order)
        rows.append(
            (
                doc_id,
                list(keys),
                list(fractions),
                source,
                len(fractions) >= 2,
                camp(fractions, majority),
            )
        )
    return pl.DataFrame(rows, schema=COSPONSORS_SCHEMA, orient="row")


def cosponsor_figures(frame: pl.DataFrame) -> dict[str, int]:
    """Dokumente mit Antragsteller, davon gemeinsam, und je Lager (alle sieben, fehlende als 0)."""
    camps = dict(frame.group_by(LAGER).len().iter_rows())
    return {
        "mit_antragsteller": int((frame.get_column(ANTRAGSTELLER).list.len() > 0).sum()),
        GEMEINSAM: int(frame.get_column(GEMEINSAM).sum()),
        **{name: int(camps.get(name, 0)) for name in CAMPS},
    }
