"""Funktion je Ratsdokument: Kontrolle, Information, Initiative, Symbolpolitik, Vollzug (Vorhaben 15).

Maßgeblich ist, was das Gremium mit dem Dokument tun soll (Codebuch, Grundsatz): eine Anfrage
kontrolliert, eine Informationsvorlage informiert, ein Antrag stößt etwas an, eine Resolution
erklärt eine Haltung, eine Beschlussvorlage vollzieht. Das Regelwerk ist das des Messdokuments
``docs/plans/15-funktion.md`` (§ 3.1), gegen zwei KI-Kodierer an 150 Dokumenten geprüft:
κ = 0,905 für Variante B, 0,829 für Variante A (§ 4.1, § 5). Die Reihenfolge:

1. **Dokumentart als ganzer Wert** (``functions.types``), dann **ihr Präfix**
   (``functions.type_prefixes``, längstes zuerst): „Beschlussvorlage" ist Vollzug, „Anfrage SPD"
   Kontrolle, „Haushaltsantrag Die Linke" Initiative.
2. **Sammelarten**, deren Art die Funktion nicht nennt (Düsseldorf 2014 bis 2020): aus der Politik
   zuerst das Titelwort, dann das erste Instrumentwort im Textkopf; aus der Verwaltung der
   Briefkopf der Politik, sonst Kenntnisnahme gegen Entscheidung im Textkopf, sonst der Titel,
   sonst ein zweiter, weiterer Blick in den Text.
3. **Symbolpolitik aus dem Titel**, nur für Initiativen aus der Politik (Urheberklasse Fraktion,
   Person oder unbekannt).
4. **Variante B**: der Beschlusstext eines Antrags kann eine Erklärung sein (Symbol), und ein
   Antrag, der nur einen Bericht verlangt, ist Kontrolle.

Was keine Regel trifft, ist die Restklasse, auf der Seite „Funktion nicht erkannt" (§ 4.2): fast
immer eine Vorlage ohne Text oder mit einer Anlage am Anfang, kein Dokument ohne Funktion.

Alle Tabellen und Muster stehen in den Settings (``[functions]``), kein Wort einer Stadt im Code.
Rein: keine Datei, kein Netz; ``classify_functions`` rechnet eine Tabelle je Korpus-ID.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import deal
import polars as pl
from polars._typing import PolarsDataType

from georep.contracts import has_columns, one_row_per_document
from georep.settings import (
    FUNCTION_CLASSES,
    FUNCTION_INSTRUMENTS,
    Functions,
    function_and_instrument,
)

# Version 1: id, funktion, instrument, quelle, variante (Messdokument § 6).
FUNCTIONS_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen von dokumente_funktion ändern
FUNKTION = "funktion"
INSTRUMENT = "instrument"
QUELLE = "quelle"
VARIANTE = "variante"
REST = "rest"
# Woher die Funktion kommt: die Dokumentart, der Titel, der Text; leer genau bei der Restklasse.
SOURCES = ("art", "titel", "text", "")
FROM_TYPE, FROM_TITLE, FROM_TEXT, NOWHERE = SOURCES
# Urheberklassen (Option 04, ``analysis.parties.URHEBER_ARTEN``), die Symbolpolitik tragen
# können: die Politik, und was nicht zuzuordnen ist. Verwaltung und Eingabe nicht.
POLITICAL = ("Fraktion", "Person", "unbekannt")
ELIGIBLE = "eingabe"  # das Instrument der Eingaben nach § 24 GO NRW: nie Symbol, nie Berichtsantrag
REPORT_MOTION = "berichtsantrag"

FUNCTIONS_SCHEMA: dict[str, PolarsDataType] = {
    "id": pl.String,
    FUNKTION: pl.String,
    INSTRUMENT: pl.String,
    QUELLE: pl.String,
    VARIANTE: pl.String,
}


def _alternation(patterns: Sequence[str]) -> re.Pattern[str] | None:
    """Ein Muster aus der Liste; ``None`` für eine leere Liste (dann trifft es nie)."""
    return re.compile("|".join(f"(?:{p})" for p in patterns)) if patterns else None


def _hit(pattern: re.Pattern[str] | None, haystack: str) -> bool:
    return pattern is not None and pattern.search(haystack) is not None


@dataclass(frozen=True)
class FunctionRules:
    """``[functions]``, einmal übersetzt; ``classify_function`` läuft je Dokument."""

    variant: str
    head_chars: int
    wide_chars: int
    decision_chars: int
    types: Mapping[str, tuple[str, str]]
    prefixes: tuple[tuple[str, str, str], ...]  # (Präfix, Funktion, Instrument), längstes zuerst
    collection_political: frozenset[str]
    collection_admin: frozenset[str]
    symbol_title: re.Pattern[str] | None
    request_title: re.Pattern[str] | None
    motion_title: re.Pattern[str] | None
    followup_title: re.Pattern[str] | None
    amendment_title: re.Pattern[str] | None
    budget_motion_title: re.Pattern[str] | None
    review_title: re.Pattern[str] | None
    report_title: re.Pattern[str] | None
    enforcement: tuple[tuple[str, re.Pattern[str]], ...]
    symbol_text: re.Pattern[str] | None
    report_text: re.Pattern[str] | None
    text_instrument: re.Pattern[str] | None
    text_words: tuple[tuple[re.Pattern[str], str, str], ...]
    not_instruments: frozenset[str]
    text_notice: re.Pattern[str] | None
    text_decision: re.Pattern[str] | None
    text_decision_head: re.Pattern[str] | None
    title_information: re.Pattern[str] | None
    title_decision: re.Pattern[str] | None
    letterhead: re.Pattern[str] | None

    @property
    def text_chars(self) -> int:
        """So viele Zeichen des Texts liest das Regelwerk höchstens."""
        return max(self.head_chars, self.wide_chars, self.decision_chars)

    @classmethod
    def from_settings(cls, functions: Functions) -> FunctionRules:
        prefixes = sorted(functions.type_prefixes.items(), key=lambda kv: len(kv[0]), reverse=True)
        return cls(
            variant=functions.variant,
            head_chars=functions.head_chars,
            wide_chars=functions.wide_chars,
            decision_chars=functions.decision_chars,
            types={k: function_and_instrument(v) for k, v in functions.types.items()},
            prefixes=tuple((p, *function_and_instrument(v)) for p, v in prefixes),
            collection_political=frozenset(functions.collection_political),
            collection_admin=frozenset(functions.collection_admin),
            symbol_title=_alternation(functions.symbol_title),
            request_title=_alternation(functions.request_title),
            motion_title=_alternation(functions.motion_title),
            followup_title=_alternation(functions.followup_title),
            amendment_title=_alternation(functions.amendment_title),
            budget_motion_title=_alternation(functions.budget_motion_title),
            review_title=_alternation(functions.review_title),
            report_title=_alternation(functions.report_title),
            enforcement=tuple(
                (rule.instrument, re.compile("|".join(f"(?:{p})" for p in rule.patterns)))
                for rule in functions.enforcement
            ),
            symbol_text=_alternation(functions.symbol_text),
            report_text=_alternation(functions.report_text),
            text_instrument=_alternation(functions.text_instrument),
            text_words=tuple(
                (re.compile(word.pattern), *function_and_instrument(word.function))
                for word in functions.text_words
            ),
            not_instruments=frozenset(functions.not_instruments),
            text_notice=_alternation(functions.text_notice),
            text_decision=_alternation(functions.text_decision),
            text_decision_head=_alternation(functions.text_decision_head),
            title_information=_alternation(functions.title_information),
            title_decision=_alternation(functions.title_decision),
            letterhead=_alternation(functions.letterhead),
        )


@dataclass(frozen=True)
class DocumentFunction:
    """Funktion, Instrument und Quelle eines Dokuments."""

    funktion: str
    instrument: str
    quelle: str


def is_consistent(found: DocumentFunction) -> bool:
    """Eine der sechs Klassen, ihr Instrument, und eine Quelle genau außerhalb der Restklasse."""
    return (
        found.funktion in FUNCTION_CLASSES
        and found.instrument in FUNCTION_INSTRUMENTS[found.funktion]
        and found.quelle in SOURCES
        and (found.quelle == NOWHERE) == (found.funktion == REST)
    )


def _enforcement_instrument(title: str, default: str, rules: FunctionRules) -> str:
    """Was eine Beschlussvorlage entscheidet (Haushalt, Satzung …); die erste Regel gewinnt."""
    return next((name for name, pattern in rules.enforcement if pattern.search(title)), default)


def _initiative_instrument(title: str, default: str, rules: FunctionRules) -> str:
    if _hit(rules.budget_motion_title, title) or default == "haushaltsantrag":
        return "haushaltsantrag"
    if _hit(rules.amendment_title, title):
        return "aenderungsantrag"
    if _hit(rules.review_title, title):
        return "pruefauftrag"
    if _hit(rules.report_title, title):
        return REPORT_MOTION
    return default


def _from_text_word(word: str, rules: FunctionRules) -> tuple[str, str] | None:
    """Funktion und Instrument aus dem ersten Instrumentwort im Textkopf einer Sammelart."""
    word = word.strip("-")
    if word in rules.not_instruments:
        return None
    for pattern, function, instrument in rules.text_words:
        if pattern.fullmatch(word):
            if function == "initiative":
                return function, _initiative_instrument(word, instrument, rules)
            return function, instrument
    return None


def _notice_or_decision(text: str, rules: FunctionRules) -> str | None:
    """Das erste Merkmal im Text gewinnt: Kenntnisnahme (Information) oder Entscheidung (Vollzug)."""
    notice = rules.text_notice.search(text) if rules.text_notice is not None else None
    decision = rules.text_decision.search(text) if rules.text_decision is not None else None
    if notice is not None and (decision is None or notice.start() < decision.start()):
        return "information"
    if decision is not None or _hit(rules.text_decision_head, text):
        return "vollzug"
    return None


def _political(title: str, head: str, rules: FunctionRules) -> DocumentFunction:
    """Sammelart der Politik: Titelwort (Anfrage ohne Antrag, Symbol, Antrag), dann der Textkopf."""
    motion = _hit(rules.motion_title, title)
    if _hit(rules.request_title, title) and not motion:  # eine Anfrage zu einer Resolution
        followup = _hit(rules.followup_title, title)
        return DocumentFunction("kontrolle", "nachfrage" if followup else "anfrage", FROM_TITLE)
    if _hit(rules.symbol_title, title):
        return DocumentFunction("symbol", "resolution", FROM_TITLE)
    if motion:
        return DocumentFunction(
            "initiative", _initiative_instrument(title, "antrag", rules), FROM_TITLE
        )
    if rules.text_instrument is not None:
        for match in rules.text_instrument.finditer(head[: rules.head_chars]):
            found = _from_text_word(match.group(0), rules)
            if found is not None:
                return DocumentFunction(*found, FROM_TEXT)
    return DocumentFunction(REST, "sammelart_ohne_merkmal", NOWHERE)


def _administration(text: str, title: str, rules: FunctionRules) -> DocumentFunction:
    """Sammelart der Verwaltung: Briefkopf der Politik, Textkopf, Titel, dann der weitere Text."""
    head = text[: rules.head_chars]
    if _hit(rules.letterhead, head):  # der Briefkopf der Politik, auch ohne das Wort „fraktion"
        return _political(title, head, rules)
    found = _notice_or_decision(head, rules)
    source = FROM_TEXT
    if found is None:
        if _hit(rules.title_information, title):
            return DocumentFunction("information", "informationsvorlage", FROM_TITLE)
        if _hit(rules.title_decision, title):
            return DocumentFunction(
                "vollzug", _enforcement_instrument(title, "beschlussvorlage", rules), FROM_TITLE
            )
        found = _notice_or_decision(text[: rules.wide_chars], rules)
        if found is None:
            return DocumentFunction(REST, "sammelart_ohne_merkmal", NOWHERE)
    if found == "information":
        return DocumentFunction("information", "informationsvorlage", source)
    return DocumentFunction(
        "vollzug", _enforcement_instrument(title, "beschlussvorlage", rules), source
    )


def _from_type(typ: str, title: str, rules: FunctionRules) -> DocumentFunction:
    """Dokumentart als ganzer Wert, dann über ihr Präfix; sonst die Restklasse „art_unbekannt"."""
    if typ in rules.types:
        function, instrument = rules.types[typ]
        if function == "vollzug":
            instrument = _enforcement_instrument(title, instrument, rules)
        elif function == "initiative" and instrument != ELIGIBLE:
            instrument = _initiative_instrument(title, instrument, rules)
        return DocumentFunction(function, instrument, FROM_TYPE)
    low = typ.lower()
    for prefix, function, instrument in rules.prefixes:
        if low.startswith(prefix):
            if function == "initiative":
                instrument = _initiative_instrument(title, instrument, rules)
            elif _hit(rules.followup_title, title):
                instrument = "nachfrage"
            return DocumentFunction(function, instrument, FROM_TYPE)
    return DocumentFunction(REST, "art_unbekannt", NOWHERE)


def _classification_is_consistent(
    paper_type: str | None,
    name: str | None,
    text: str | None,
    originator_class: str | None,
    rules: FunctionRules,
    result: DocumentFunction | None = None,
) -> bool:
    assert result is not None
    return is_consistent(result)


# deal.safe statt deal.pure: deals has()-Patcher ist nicht reentrant und patcht prozessweit, und
# diese Funktion läuft je Dokument (CLAUDE.md, „Nie").
@deal.safe
@deal.ensure(_classification_is_consistent, message="eine Funktion, ihr Instrument, ihre Quelle")
def classify_function(
    paper_type: str | None,
    name: str | None,
    text: str | None,
    originator_class: str | None,
    rules: FunctionRules,
) -> DocumentFunction:
    """Die Funktion eines Dokuments aus Art, Titel, Textanfang und Urheberklasse (Option 04).

    ``text`` ist der kleingeschriebene Text des Korpus (oder sein Anfang); ``originator_class``
    die Klasse aus ``dokumente_urheber``, ``None`` heißt „unbekannt".
    """
    typ = (paper_type or "").strip()
    title = (name or "").lower()
    body = text or ""
    origin = originator_class or "unbekannt"
    if typ in rules.collection_political or (typ in rules.collection_admin and origin in POLITICAL):
        found = _political(title, body[: rules.head_chars], rules)
    elif typ in rules.collection_admin:
        found = _administration(body, title, rules)
    else:
        found = _from_type(typ, title, rules)
    political_initiative = (
        found.funktion == "initiative" and origin in POLITICAL and found.instrument != ELIGIBLE
    )
    if political_initiative and _hit(rules.symbol_title, title):
        return DocumentFunction("symbol", "resolution", FROM_TITLE)
    if political_initiative and rules.variant == "B":
        decision = body[: rules.decision_chars]
        if _hit(rules.symbol_text, decision):
            return DocumentFunction("symbol", "erklaerung_text", FROM_TEXT)
        if found.instrument == REPORT_MOTION:
            return DocumentFunction("kontrolle", REPORT_MOTION, found.quelle)
        if _hit(rules.report_text, decision):
            return DocumentFunction("kontrolle", REPORT_MOTION, FROM_TEXT)
    return found


def _one_row_per_corpus_id(
    corpus: pl.DataFrame,
    originators: pl.DataFrame,
    rules: FunctionRules,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return one_row_per_document(result, corpus.get_column("id").to_list())


def _rows_are_consistent(
    corpus: pl.DataFrame,
    originators: pl.DataFrame,
    rules: FunctionRules,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    rows = result.select(FUNKTION, INSTRUMENT, QUELLE).unique().iter_rows()
    return result.schema == pl.Schema(FUNCTIONS_SCHEMA) and all(
        is_consistent(DocumentFunction(*row)) for row in rows
    )


@deal.pre(
    lambda corpus, originators, rules: (
        has_columns(corpus, "id", "paper_type", "name", "text")
        and has_columns(originators, "id", "urheber_art")
    )
)
@deal.ensure(_one_row_per_corpus_id, message="eine Zeile je Korpus-ID, nach id sortiert")
@deal.ensure(_rows_are_consistent, message="Schema, Funktion, Instrument und Quelle passen")
def classify_functions(
    corpus: pl.DataFrame, originators: pl.DataFrame, rules: FunctionRules
) -> pl.DataFrame:
    """Je Korpus-ID Funktion, Instrument, Quelle und Variante (``dokumente_funktion.parquet``).

    ``originators`` ist ``dokumente_urheber`` (Option 04); ein Dokument ohne Zeile dort zählt als
    Urheber „unbekannt". Gelesen werden nur die ersten ``rules.text_chars`` Zeichen des Texts.
    """
    needed = (
        corpus.select(
            "id",
            "paper_type",
            "name",
            pl.col("text").str.slice(0, rules.text_chars).alias("text"),
        )
        .join(originators.select("id", "urheber_art"), on="id", how="left")
        .sort("id")
    )
    rows = [
        (
            row[0],
            *_as_tuple(classify_function(row[1], row[2], row[3], row[4], rules)),
            rules.variant,
        )
        for row in needed.iter_rows()
    ]
    return pl.DataFrame(rows, schema=FUNCTIONS_SCHEMA, orient="row")


def _as_tuple(found: DocumentFunction) -> tuple[str, str, str]:
    return found.funktion, found.instrument, found.quelle


def function_figures(frame: pl.DataFrame) -> dict[str, int]:
    """Dokumente je Funktion, in der Folge von ``FUNCTION_CLASSES``, fehlende als 0."""
    found = dict(frame.group_by(FUNKTION).len().iter_rows())
    return {name: int(found.get(name, 0)) for name in FUNCTION_CLASSES}
