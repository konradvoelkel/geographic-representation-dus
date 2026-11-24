"""Kennungen und Beträge im Rohtext: Bauleitplanung, Betrag, Termin, Verwaltungseinheit (Vorhaben 12).

Das Regelwerk ist das des Messdokuments ``docs/plans/12-kennungen.md``, und zwar genau die Fassung,
die die Validierung bestanden hat (§ 4 und § 5; zwei KI-Kodierer und ein Schlichter, kein
menschlicher Goldstandard):

* **Bauleitplanung** (``bplan``, ``fnp``), Fassung 1: ein Schlüsselwort („Bebauungsplan",
  „Flächennutzungsplanänderung") und das Nummernformat der Stadt; die Spanne ist nur die Nummer,
  eine Liste dahinter („Nr. 5481/006 und 5481/007") gibt je Nummer eine Spanne. Präzision 1,000
  (n 100), Recall 64/71.
* **Betrag** (``betrag``), Fassung 1, **ohne Rolle** (die Rolle fiel mit 0,508): Zahl mit Einheit,
  Faktor, Einheit vorn, die erste Zahl einer Spanne („5.000 bis 10.000 Euro"); Norm in Euro mit
  zwei Nachkommastellen. Präzision 0,962, Recall 84/88. Die Korrekturen der Fassung 2 bestanden
  die Bestätigung nicht (18 von 20) und fehlen hier mit Absicht.
* **Termin** (``termin``), Fassung 2, **ohne Funktion** (die Funktion ``frist`` fiel mit 15/30):
  Datum in Zahlen, Worten und ISO, auch über einen Zeilenwechsel, Monat, Quartal, Halbjahr, Jahr
  mit Zusatz, relative Angaben, und die unvollständige erste Angabe einer Spanne („10. und 11. Juni
  2023", R10). Präzision 1,000 an 30 Treffern der Bestätigung.
* **Verwaltungseinheit** (``amt``, ``dezernat``), Fassung 2: das Kopffeld der Vorlage (auch
  mehrzeilig), Namen aus einem Ämterverzeichnis, das je Lauf **aus den Kopffeldern des Korpus**
  entsteht (``office_directory``), Nummern („Amt 66"), Wörter auf -amt, Einheiten der Stadt
  („Bezirksverwaltungsstelle 10"), „Dezernat 06". Präzision 0,956, Recall 71/80.

Haushalt und Rechtsgrundlage fielen (§ 5) und sind nicht gebaut. Keine Regel ist nachgeschärft;
die Vorschläge S1 bis S10 des Schlichters bleiben im Messdokument (§ 9). Dass diese Funktionen
dieselben Spannen liefern wie das Messskript, prüft ein langsamer Test an den Labels.

Die Sprache (Schlüsselwörter, Einheiten, Monate, relative Angaben) steht in ``defaults.toml``,
Nummernformate und Kopffelder im Stadtprofil (``[identifiers]``); hier steht nur, wie Ziffern,
Leerraum und die Teile zusammengesetzt sind. Rein: keine Datei, kein Netz.

Eine Spanne folgt Fundament F3 (``georep.spans``): Zeichenpositionen im Rohtext aus F1, ``value``
wörtlich, ``section`` leer, bis Vorhaben 11 die Abschnitte liefert, dazu hinter den acht Spalten
``attr`` mit der **Form** (Punkt 74), nie einer Deutung: ``je`` und ``spanne`` bei Beträgen, ``tag``,
``monat``, ``quartal``, ``jahr``, ``relativ`` bei Terminen, ``kopf``, ``name``, ``nummer``,
``text``, ``wort`` bei Ämtern.
"""

from __future__ import annotations

import dataclasses
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

import deal
import polars as pl

from georep.contracts import has_columns
from georep.errors import SchemaError
from georep.settings import Identifiers
from georep.spans import SPAN_SCHEMA, check_spans, empty_spans, sort_spans

# Version 1: die acht Spalten von F3 und ``attr`` (Messdokument § 6 und § 10).
IDENTIFIERS_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen von kennungen.parquet ändern
# Das Verfahren in ``extractor``, vor dem Extraktor des Rohtexts: Bauleitplanung und Betrag in
# Fassung 1, Termin und Verwaltungseinheit in Fassung 2 der Messung (``kennungen-messung-v1/-v2``).
METHOD = "kennungen-1"
ATTR = "attr"
EXTRA: dict[str, pl.DataType] = {ATTR: pl.String()}
# Die Formen, die ``attr`` je Art tragen darf; ``None`` heißt: keine besondere Form.
FORMS: dict[str, frozenset[str | None]] = {
    "bplan": frozenset({None}),
    "fnp": frozenset({None}),
    "betrag": frozenset({None, "je", "spanne"}),
    "termin": frozenset({"tag", "monat", "quartal", "jahr", "relativ"}),
    "amt": frozenset({"kopf", "name", "nummer", "text", "wort"}),
    "dezernat": frozenset({"nummer"}),
}
# Die eine Überlappung, die Fassung 2 so validiert hat: eine Nummer („Amt 10", „Fachbereich 20")
# direkt vor „10 – Hauptamt" bleibt eine Spanne, und der Name nimmt die Nummer davor in seine Spanne
# (``offices.code_before``). Art, Form der früheren und Form der späteren Spanne. Gezählt am
# 2026-11-24: 3 Paare in der Hauptperiode, 8 in 2014 bis 2020, 111 in Mönchengladbach (Ämterlisten
# in sechs Dokumenten); sonst überlappen keine zwei Spannen einer Art (Review N1).
MAY_OVERLAP = ("amt", "nummer", "name")

# Leerraum ohne Zeilenwechsel, und mit höchstens einem
WS = r"[ \t\u00a0\u202f]*"
WSN = r"[ \t\u00a0\u202f]*(?:\n[ \t\u00a0\u202f]*)?"
NEVER = r"(?!x)x"  # ein Teil ohne Muster in den Settings trifft nie
YEAR = r"(?P<jahr>(?:19|20)\d{2})(?!\d)"
# Zwischen Schlüsselwort und Plannummer: ein kurzer Text ohne Ziffer, höchstens ein Zeilenwechsel
PLAN_FILL = r"(?P<fill>[^\d\n.;]{0,40}?(?:\n[^\d\n.;]{0,25}?)?)"
# Eine Zahl, wie sie vor einer Einheit steht: Tausenderpunkt, -leerzeichen, Komma, „,-"
AMOUNT_NUMBER = (
    r"(?<![\d.,\w])(?P<sign>[-−])?"
    r"(?P<num>(?:\d{1,3}(?:[.\u00a0\u202f]\d{3})+|\d{2,3}(?: \d{3})+|\d+)(?:,(?:\d{1,2}|-{1,2}|–))?)"
    r"(?![\d])"
)
AMOUNT_RANGE_NUMBER = r"(?<![\d.,\w])(?P<num>(?:\d{1,3}(?:[.\u00a0\u202f]\d{3})+|\d+)(?:,\d{1,2})?)"
A_YEAR = re.compile(r"(?:19|20)\d{2}")  # die erste Zahl einer Spanne ist keine Jahreszahl
DATE_NUMERIC = (
    r"(?<![\d.\w])(?P<tag>\d{1,2})\.[ \t]?(?P<mon>\d{1,2})\.[ \t]?(?P<jahr>(?:19|20)\d{2}|\d{2})"
    r"(?![\d]|\.\d)"
)
DATE_ISO = r"(?<![\d-])(?P<jahr>(?:19|20)\d{2})-(?P<mon>\d{2})-(?P<tag>\d{2})(?![\d-])"
ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4"}
UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
# Folgezeile eines mehrzeiligen Kopffelds
HEAD_NEXT_LINE = re.compile(r"[ \t]*\n[ \t]*(?P<v>[^\n]*?\S)[ \t]*(?=\n|$)")
HEAD_MIN_CHARS = 4  # ein Kopffeld ohne Nummer gilt ab vier Zeichen als Name
AMOUNT_RANGE_WINDOW = 40  # so weit vor einem Betrag steht die erste Zahl einer Spanne
DATE_RANGE_WINDOW = 40  # so weit vor einem Datum steht die erste Angabe einer Spanne (R10)
MONTH_RANGE_WINDOW = 25  # dito vor einem Monat („März bis Dezember 2021")
COMMITTEE_WINDOW = 30  # so weit vor einem Amtsnamen steht „Ausschuss für"
CODE_WINDOW = 12  # so weit vor einem Amtsnamen steht „64 - "


class Hit(NamedTuple):
    """Eine Kennung in einem Text: Grenzen, Art, Normwert, Form."""

    start: int
    end: int
    kind: str
    norm: str
    attr: str | None


def _one(pattern: str) -> str:
    """Ein Teil aus den Settings als Gruppe; leer trifft nie."""
    return f"(?:{pattern})" if pattern else NEVER


def _any(patterns: Iterable[str]) -> str:
    """Eine Liste aus den Settings als Alternative in ihrer Folge; leer trifft nie."""
    parts = [f"(?:{p})" for p in patterns]
    return "|".join(parts) if parts else NEVER


def _compiled(pattern: str) -> re.Pattern[str] | None:
    return re.compile(pattern) if pattern else None


@dataclass(frozen=True)
class IdentifierRules:
    """Die übersetzten Muster eines Profils und das Ämterverzeichnis eines Laufs."""

    kinds: frozenset[str]
    # Art 1
    plan: re.Pattern[str] | None
    plan_more: re.Pattern[str] | None
    plan_norms: tuple[tuple[re.Pattern[str], str], ...]
    fnp: re.Pattern[str] | None
    fnp_ordinal: re.Pattern[str] | None
    # Art 3
    amount_after: re.Pattern[str]
    amount_before: re.Pattern[str]
    amount_range: re.Pattern[str]
    amount_per: re.Pattern[str]
    multipliers: tuple[tuple[re.Pattern[str], int], ...]
    thousand_units: frozenset[str]
    # Art 4
    months: tuple[tuple[re.Pattern[str], int], ...]
    date_numeric: re.Pattern[str]
    date_text: re.Pattern[str]
    date_iso: re.Pattern[str]
    quarter: re.Pattern[str]
    half_year: re.Pattern[str]
    month_qualified: re.Pattern[str]
    month_year: re.Pattern[str]
    year_qualified: re.Pattern[str]
    qualifier_norms: Mapping[str, str]
    range_day: re.Pattern[str]
    range_day_month: re.Pattern[str]
    range_day_numeric: re.Pattern[str]
    range_month: re.Pattern[str]
    relative: tuple[tuple[str, re.Pattern[str]], ...]
    # Art 6
    head_chars: int
    head: re.Pattern[str] | None
    head_code: re.Pattern[str] | None
    office_number: re.Pattern[str] | None
    office_extra: re.Pattern[str] | None
    office_text: re.Pattern[str] | None
    office_text_norm: str
    office_word: re.Pattern[str] | None
    office_word_not: re.Pattern[str] | None
    committee_before: re.Pattern[str] | None
    committee_words: re.Pattern[str] | None
    code_before: re.Pattern[str] | None
    bracket: str
    department: re.Pattern[str] | None
    directory_min_count: int
    directory_min_chars: int
    directory_word: str
    # je Lauf: Name -> Nummer aus den Kopffeldern (``office_directory``)
    directory: Mapping[str, str] = dataclasses.field(default_factory=dict)
    directory_names: re.Pattern[str] | None = None

    @classmethod
    def from_settings(cls, settings: Identifiers) -> IdentifierRules:
        """Die Muster aus ``[identifiers]``, ohne Ämterverzeichnis (``with_directory``)."""
        plans, amounts, dates, offices = (
            settings.plans,
            settings.amounts,
            settings.dates,
            settings.offices,
        )
        number_word = _one(plans.number_word)
        number = _one(plans.number)
        tail = r"(?:" + number_word + WSN + r")?(?<![\w/.-])(?P<n>" + number + r")(?![\d/])"
        multiplier = r"(?P<mult>" + _any(m.pattern for m in amounts.multipliers) + r")"
        month = r"(?P<monat>" + _any(dates.months) + r")"
        range_tail = r"[ \t\n]*(?:" + _one(dates.range_words) + r")[ \t\n]*$"
        return cls(
            kinds=frozenset(settings.kinds),
            plan=re.compile(_one(plans.keyword) + PLAN_FILL + tail) if plans.number else None,
            plan_more=(
                re.compile(WSN + r"(?:" + _one(plans.list_words) + r")" + WSN + tail)
                if plans.number
                else None
            ),
            plan_norms=tuple((re.compile(n.pattern), n.replace) for n in plans.norms),
            fnp=(
                re.compile(
                    _one(plans.fnp_keyword)
                    + WSN
                    + r"(?:"
                    + _one(plans.fnp_draft)
                    + WSN
                    + r")?(?:"
                    + number_word
                    + WSN
                    + r")?(?P<n>\d{1,3}[a-z]?)(?![\d/.,])"
                )
                if plans.fnp_keyword
                else None
            ),
            fnp_ordinal=_compiled(plans.fnp_ordinal),
            amount_after=re.compile(
                AMOUNT_NUMBER
                + WSN
                + r"(?:"
                + multiplier
                + WSN
                + r")?(?P<unit>"
                + _any(amounts.units_after)
                + r")"
            ),
            amount_before=re.compile(
                r"(?P<unit>"
                + _any(amounts.units_before)
                + r")[ \t\u00a0]?"
                + AMOUNT_NUMBER
                + r"(?:"
                + WS
                + multiplier
                + r")?"
            ),
            amount_range=re.compile(
                AMOUNT_RANGE_NUMBER + WS + r"(?:" + _one(amounts.range_words) + r")" + WS + r"$"
            ),
            amount_per=re.compile(
                WS
                + r"(?:"
                + _one(amounts.per_words)
                + r")"
                + WS
                + r"(?:"
                + _any(amounts.per_units)
                + r")"
            ),
            multipliers=tuple((re.compile(m.pattern), m.factor) for m in amounts.multipliers),
            thousand_units=frozenset(amounts.thousand_units),
            months=tuple((re.compile(name), number) for name, number in dates.months.items()),
            date_numeric=re.compile(DATE_NUMERIC),
            date_text=re.compile(r"(?<![\d\w])(?P<tag>\d{1,2})\.?" + WSN + month + WSN + YEAR),
            date_iso=re.compile(DATE_ISO),
            quarter=re.compile(
                r"(?P<q>[1-4]|I{1,3}|IV)\.?"
                + WS
                + r"(?P<art>"
                + _one(dates.quarter)
                + r"|"
                + _one(dates.half_year)
                + r")(?:es|s)?"
                + WS
                + YEAR
            ),
            half_year=re.compile(_one(dates.half_year)),
            month_qualified=re.compile(
                r"(?P<q>" + _any(dates.month_qualifiers) + r")[ \t\n]+" + month + WSN + YEAR
            ),
            month_year=re.compile(r"(?<![\d.][ \t])(?<![\d.])" + month + WSN + YEAR),
            year_qualified=re.compile(
                r"(?P<q>"
                + _any(dates.year_qualifiers)
                + r")[ \t\n]+(?:"
                + _one(dates.of_the_year)
                + r"[ \t\n]+)?"
                + YEAR
            ),
            qualifier_norms=dict(dates.qualifier_norms),
            range_day=re.compile(r"(?<![\d\w.])(?P<tag>\d{1,2})\." + range_tail),
            range_day_month=re.compile(
                r"(?<![\d\w.])(?P<tag>\d{1,2})\.[ \t]*" + month + range_tail
            ),
            range_day_numeric=re.compile(
                r"(?<![\d\w.])(?P<tag>\d{1,2})\.(?P<mon>\d{1,2})\." + range_tail
            ),
            range_month=re.compile(r"(?<![\w.])" + month + range_tail),
            relative=tuple((r.norm, re.compile(r.pattern)) for r in dates.relative),
            head_chars=offices.head_chars,
            head=_compiled(offices.head),
            head_code=_compiled(offices.head_code),
            office_number=_compiled(offices.number),
            office_extra=_compiled(offices.number_extra),
            office_text=_compiled(offices.text),
            office_text_norm=offices.text_norm,
            office_word=_compiled(offices.word),
            office_word_not=_compiled(offices.word_not),
            committee_before=_compiled(offices.committee_before),
            committee_words=_compiled(offices.committee_words),
            code_before=_compiled(offices.code_before),
            bracket=offices.bracket,
            department=_compiled(offices.department),
            directory_min_count=offices.directory_min_count,
            directory_min_chars=offices.directory_min_chars,
            directory_word=offices.directory_word,
        )

    def with_directory(self, directory: Mapping[str, str]) -> IdentifierRules:
        """Dieselben Regeln mit dem Ämterverzeichnis eines Laufs (Name -> Nummer).

        Längere Namen zuerst, damit „Amt für Soziales und Jugend" vor „Amt für Soziales" steht;
        gleich lange in der Folge des Verzeichnisses. Ein Leerzeichen im Namen trifft jeden
        Leerraum, auch einen Zeilenwechsel; ein Genitiv-s und eine Nummer in Klammern dahinter
        gehören zur Spanne.
        """
        if not directory:
            return dataclasses.replace(self, directory={}, directory_names=None)
        names = sorted(directory, key=len, reverse=True)
        pattern = re.compile(
            r"(?<![\w-])(?P<name>"
            + "|".join(re.escape(name).replace(r"\ ", r"[ \t\n]+") for name in names)
            + r")(?:e?s)?(?![\w-])(?P<klammer>"
            + WS
            + _one(self.bracket)
            + r")?"
        )
        return dataclasses.replace(self, directory=dict(directory), directory_names=pattern)


# --- Normalformen ------------------------------------------------------------------------------


def plan_norm(number: str, rules: IdentifierRules) -> str:
    """Eine Plannummer in Normalform: die erste Regel des Profils, die passt, sonst ohne Leerraum, groß.

    Mit Schrägstrich oder Bindestrich fallen Leerzeichen und Tabulatoren vorher weg („5674 / 26").
    """
    compact = re.sub(r"[ \t]", "", number) if "/" in number or "-" in number else number
    for pattern, replace in rules.plan_norms:
        found = pattern.fullmatch(compact)
        if found:
            return found.expand(replace)
    return re.sub(r"\s+", "", compact).upper()


def amount_norm(
    number: str, sign: str | None, multiplier: str | None, unit: str, rules: IdentifierRules
) -> Decimal | None:
    """Ein Betrag in Euro mit zwei Nachkommastellen; ``None``, wenn die Zahl keine ist.

    Tausenderpunkte und -leerzeichen fallen weg, das Komma wird ein Punkt, „,-" heißt „,00"; der
    Faktor kommt aus ``multipliers`` (das erste Muster, das das ganze Wort trifft), eine Einheit in
    Tausend (``thousand_units``) multipliziert mit 1000. Ein Minus vorn macht ihn negativ.
    """
    digits = re.sub(r"[.\u00a0\u202f ]", "", number)
    digits = re.sub(r",(?:-{1,2}|–)$", "", digits).replace(",", ".")
    try:
        value = Decimal(digits)
    except InvalidOperation:
        return None
    factor = Decimal(1)
    if multiplier:
        factor = next(
            (Decimal(f) for p, f in rules.multipliers if p.fullmatch(multiplier)), Decimal(1)
        )
    if unit.replace(" ", "").upper() in rules.thousand_units:
        factor *= 1000
    value *= factor
    if sign and sign.strip() != "+":
        value = -value
    try:
        return value.quantize(Decimal("0.01"))
    except InvalidOperation:  # mehr Stellen, als Decimal hält: keine Zahl eines Ratsdokuments
        return None


def _a_day_exactly_when_the_calendar_has_it(
    day: int, month: int, year: int, result: str | None = None
) -> bool:
    try:
        exists = 1950 <= year <= 2040 and date(year, month, day).day == day
    except ValueError:
        exists = False
    return result == (f"{year:04d}-{month:02d}-{day:02d}" if exists else None)


# deal.safe statt deal.pure: die Funktion läuft je gefundenem Datum (CLAUDE.md, „Nie").
@deal.ensure(
    _a_day_exactly_when_the_calendar_has_it,
    message="ein ISO-Datum genau dann, wenn der Kalender den Tag zwischen 1950 und 2040 kennt",
)
@deal.safe
def iso_date(day: int, month: int, year: int) -> str | None:
    """Ein gültiges Datum zwischen 1950 und 2040 als ``JJJJ-MM-TT``; sonst ``None``.

    Der Februar hat in jedem durch vier teilbaren Jahr 29 Tage (im Bereich stimmt das).
    """
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1950 <= year <= 2040):
        return None
    days = [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    if day > days:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _year4(year: str) -> int:
    return int(year) if len(year) == 4 else 2000 + int(year)


def _month_number(name: str, rules: IdentifierRules) -> int:
    """Der Monat eines Monatsnamens; 0, wenn kein Muster ihn trifft."""
    return next((number for p, number in rules.months if p.fullmatch(name)), 0)


# --- Art 1: Bauleitplanung --------------------------------------------------------------------


def plan_numbers(text: str, rules: IdentifierRules) -> Iterator[Hit]:
    """Bebauungsplan- und FNP-Nummern; die Spanne ist die Nummer, nicht das Schlüsselwort."""
    if rules.plan is not None and rules.plan_more is not None:
        for found in rules.plan.finditer(text):
            yield Hit(
                found.start("n"), found.end("n"), "bplan", plan_norm(found.group("n"), rules), None
            )
            position = found.end("n")
            while more := rules.plan_more.match(text, position):
                yield Hit(
                    more.start("n"), more.end("n"), "bplan", plan_norm(more.group("n"), rules), None
                )
                position = more.end("n")
    for pattern in (rules.fnp, rules.fnp_ordinal):
        if pattern is None:
            continue
        for found in pattern.finditer(text):
            norm = f"FNP-Änderung {found.group('n')}"
            yield Hit(found.start("n"), found.end("n"), "fnp", norm, None)


# --- Art 3: Betrag ----------------------------------------------------------------------------


def amounts(text: str, rules: IdentifierRules) -> Iterator[Hit]:
    """Euro-Beträge ohne Rolle: Einheit dahinter, die erste Zahl einer Spanne, Einheit davor.

    Eine Einheit hinter einer Zahl kann nicht zugleich vor der nächsten stehen, und keine zwei
    Beträge überlappen. ``attr`` ist ``je`` für einen Preis je Einheit, ``spanne`` für die erste Zahl
    einer Spanne, sonst leer.
    """
    taken: list[tuple[int, int]] = []
    units: set[int] = set()
    found_amounts: list[tuple[int, int, Decimal, bool]] = []
    for found in rules.amount_after.finditer(text):
        value = amount_norm(
            found.group("num"), found.group("sign"), found.group("mult"), found.group("unit"), rules
        )
        if value is None:
            continue
        start = found.start("sign") if found.group("sign") else found.start("num")
        found_amounts.append((start, found.end(), value, False))
        taken.append((start, found.end()))
        units.update(range(found.start("unit"), found.end("unit")))
        first = rules.amount_range.search(text, max(0, start - AMOUNT_RANGE_WINDOW), start)
        if first and not A_YEAR.fullmatch(first.group("num")):
            inherited = amount_norm(
                first.group("num"), None, found.group("mult"), found.group("unit"), rules
            )
            if inherited is not None:
                found_amounts.append((first.start("num"), first.end("num"), inherited, True))
                taken.append((first.start("num"), first.end("num")))
    for found in rules.amount_before.finditer(text):
        if found.start("unit") in units or A_YEAR.fullmatch(found.group("num")):
            continue
        if any(a < found.end() and found.start() < b for a, b in taken):
            continue
        value = amount_norm(
            found.group("num"), found.group("sign"), found.group("mult"), found.group("unit"), rules
        )
        if value is None:
            continue
        found_amounts.append((found.start(), found.end(), value, False))
        taken.append((found.start(), found.end()))
    for start, end, value, is_range in found_amounts:
        form = "spanne" if is_range else ("je" if rules.amount_per.match(text, end) else None)
        yield Hit(start, end, "betrag", f"{value}", form)


# --- Art 4: Termin ----------------------------------------------------------------------------


def dates(text: str, rules: IdentifierRules) -> Iterator[Hit]:
    """Zeitangaben ohne Funktion; eine Stelle belegt nur die erste Regel, die sie trifft.

    Die Folge: Datum in Worten (mit der ersten Angabe einer Spanne, R10), in Zahlen (dito), ISO,
    Quartal und Halbjahr, Monat mit Zusatz, Monat und Jahr (mit dem ersten Monat einer Spanne),
    Jahr mit Zusatz, relative Angaben in der Folge der Settings.
    """
    taken: list[tuple[int, int]] = []

    def free(start: int, end: int) -> bool:
        return not any(a < end and start < b for a, b in taken)

    def take(start: int, end: int, norm: str, form: str) -> Hit:
        taken.append((start, end))
        return Hit(start, end, "termin", norm, form)

    def first_of_range(start: int, month: int, year: int) -> Iterator[Hit]:
        """Die unvollständige erste Angabe vor „und"/„bis" erbt Monat und Jahr (R10)."""
        low = max(0, start - DATE_RANGE_WINDOW)
        before = text[low:start]
        for pattern in (rules.range_day_month, rules.range_day_numeric, rules.range_day):
            found = pattern.search(before)
            if not found:
                continue
            groups = found.groupdict()
            inherited = month
            if groups.get("monat"):
                inherited = _month_number(found.group("monat"), rules)
                end = low + found.end("monat")
            elif groups.get("mon"):
                inherited = int(found.group("mon"))
                end = low + found.end("mon") + 1
            else:
                end = low + found.end("tag") + 1
            iso = iso_date(int(found.group("tag")), inherited, year)
            if iso and free(low + found.start(), end):
                yield take(low + found.start(), end, iso, "tag")
            return

    for found in rules.date_text.finditer(text):
        month = _month_number(found.group("monat"), rules)
        iso = iso_date(int(found.group("tag")), month, int(found.group("jahr")))
        if iso and free(found.start(), found.end()):
            yield take(found.start(), found.end(), iso, "tag")
            yield from first_of_range(found.start(), month, int(found.group("jahr")))
    for found in rules.date_numeric.finditer(text):
        day, month_digits, year = found.group("tag"), found.group("mon"), found.group("jahr")
        if len(year) == 2 and (len(day) != 2 or len(month_digits) != 2):
            continue  # „3.2.10" ist eher eine Gliederungsnummer
        iso = iso_date(int(day), int(month_digits), _year4(year))
        if iso and free(found.start(), found.end()):
            yield take(found.start(), found.end(), iso, "tag")
            yield from first_of_range(found.start(), int(month_digits), _year4(year))
    for found in rules.date_iso.finditer(text):
        iso = iso_date(int(found.group("tag")), int(found.group("mon")), int(found.group("jahr")))
        if iso and free(found.start(), found.end()):
            yield take(found.start(), found.end(), iso, "tag")
    for found in rules.quarter.finditer(text):
        number = ROMAN.get(found.group("q"), found.group("q"))
        half = rules.half_year.fullmatch(found.group("art")) is not None
        if half and number not in {"1", "2"}:
            continue
        if free(found.start(), found.end()):
            norm = f"{found.group('jahr')}-{'H' if half else 'Q'}{number}"
            yield take(found.start(), found.end(), norm, "quartal")
    for found in rules.month_qualified.finditer(text):
        month = _month_number(found.group("monat"), rules)
        if month and free(found.start(), found.end()):
            norm = f"{found.group('jahr')}-{month:02d}~{found.group('q').lower()}"
            yield take(found.start(), found.end(), norm, "monat")
    for found in rules.month_year.finditer(text):
        month = _month_number(found.group("monat"), rules)
        if month and free(found.start(), found.end()):
            yield take(found.start(), found.end(), f"{found.group('jahr')}-{month:02d}", "monat")
            low = max(0, found.start() - MONTH_RANGE_WINDOW)
            first = rules.range_month.search(text[low : found.start()])
            if first:
                start = low + first.start()
                inherited = _month_number(first.group("monat"), rules)
                end = start + len(first.group("monat"))
                if inherited and free(start, end):
                    norm = f"{found.group('jahr')}-{inherited:02d}"
                    yield take(start, end, norm, "monat")
    for found in rules.year_qualified.finditer(text):
        if free(found.start(), found.end()):
            qualifier = found.group("q").lower().translate(UMLAUT)
            qualifier = rules.qualifier_norms.get(qualifier, qualifier)
            yield take(found.start(), found.end(), f"{found.group('jahr')}~{qualifier}", "jahr")
    for norm, pattern in rules.relative:
        for found in pattern.finditer(text):
            if free(found.start(), found.end()):
                yield take(found.start(), found.end(), norm, "relativ")


# --- Art 6: Verwaltungseinheit ----------------------------------------------------------------


def head_office(value: str, rules: IdentifierRules) -> tuple[str, str] | None:
    """(Nummer, Name) aus dem Wert eines Kopffelds; ohne Nummer der Name als beides.

    Ein Wert unter vier Zeichen oder mit Doppelpunkt am Ende ist kein Amt (ein leeres Feld, auf
    das die nächste Feldbezeichnung folgt).
    """
    found = rules.head_code.match(value.strip()) if rules.head_code is not None else None
    if found:
        return found.group("code"), re.sub(r"\s+", " ", found.group("name")).strip()
    flat = re.sub(r"\s+", " ", value).strip()
    if len(flat) >= HEAD_MIN_CHARS and not flat.endswith(":"):
        return flat, flat
    return None


def office_directory(texts: Iterable[str], rules: IdentifierRules) -> dict[str, str]:
    """Das Ämterverzeichnis eines Laufs aus den Kopffeldern: Name -> häufigste Nummer.

    Ein Name kommt hinein, wenn ihn mindestens ``directory_min_count`` Kopffelder mit Nummer tragen,
    wenn er lang genug ist oder ``directory_word`` enthält („Sportamt") und wenn er kein Gremium
    nennt. Bei gleicher Häufigkeit gilt die Nummer, die zuerst kam; die Folge der Namen ist die
    ihres ersten Vorkommens. ``texts`` in fester Folge (nach Dateiname), sonst schwankt beides.
    """
    if rules.head is None:
        return {}
    by_name: dict[str, Counter[str]] = {}
    for text in texts:
        for found in rules.head.finditer(text[: rules.head_chars]):
            office = head_office(found.group("v"), rules)
            if office and office[0] != office[1]:
                by_name.setdefault(office[1], Counter())[office[0]] += 1
    word = rules.directory_word.lower()
    return {
        name: codes.most_common(1)[0][0]
        for name, codes in by_name.items()
        if sum(codes.values()) >= rules.directory_min_count
        and (len(name) >= rules.directory_min_chars or (word != "" and word in name.lower()))
        and not (rules.committee_words is not None and rules.committee_words.search(name))
    }


def _overlaps(start: int, end: int, taken: Sequence[tuple[int, int]]) -> bool:
    return any(a < end and start < b for a, b in taken)


def _offices_first_pass(text: str, rules: IdentifierRules) -> Iterator[Hit]:
    """Kopffeld, Namen aus dem Verzeichnis, Nummern, die zweite Nummernform, Dezernate (Fassung 1)."""
    taken: list[tuple[int, int]] = []
    if rules.head is not None:
        for found in rules.head.finditer(text[: rules.head_chars]):
            office = head_office(found.group("v"), rules)
            if office:
                taken.append((found.start("v"), found.end("v")))
                yield Hit(found.start("v"), found.end("v"), "amt", office[0], "kopf")
    if rules.directory_names is not None:
        for found in rules.directory_names.finditer(text):
            if _overlaps(found.start(), found.end(), taken):
                continue
            window = text[max(0, found.start() - COMMITTEE_WINDOW) : found.start()]
            if rules.committee_before is not None and rules.committee_before.search(window):
                continue  # „Ausschuss für Umwelt" nennt ein Gremium, kein Amt
            name = re.sub(r"\s+", " ", found.group("name"))
            taken.append((found.start(), found.end()))
            yield Hit(found.start(), found.end(), "amt", rules.directory[name], "name")
    if rules.office_number is not None:
        for found in rules.office_number.finditer(text):
            if _overlaps(found.start(), found.end(), taken):
                continue
            norm = found.group("n") + (f"/{found.group('u')}" if found.group("u") else "")
            yield Hit(found.start(), found.end(), "amt", norm, "nummer")
    if rules.office_extra is not None:
        for found in rules.office_extra.finditer(text):
            if _overlaps(found.start(), found.end(), taken):
                continue
            yield Hit(found.start(), found.end(), "amt", found.group("n"), "nummer")
    if rules.department is not None:
        for found in rules.department.finditer(text):
            yield Hit(
                found.start(), found.end(), "dezernat", f"{int(found.group('n')):02d}", "nummer"
            )


def offices(text: str, rules: IdentifierRules) -> Iterator[Hit]:
    """Ämter und Dezernate (Fassung 2): die erste Runde, dazu die Nummer vor einem Namen
    („64 - Amt für Wohnungswesen"), Folgezeilen eines mehrzeiligen Kopffelds, die Einheiten der
    Stadt im Text und Wörter auf -amt, jeweils nur an freien Stellen."""
    hits: list[Hit] = []
    for hit in _offices_first_pass(text, rules):
        if hit.attr == "name" and rules.code_before is not None:
            low = max(0, hit.start - CODE_WINDOW)
            code = rules.code_before.search(text[low : hit.start])
            if code:
                norm = code.group(0).split("-")[0].split("–")[0].strip()
                # an der Fundstelle beginnen, nicht um die Länge des Treffers vor dem Namen: ``$``
                # trifft auch vor einem Zeilenwechsel am Ende des Fensters (Review K1, 2026-11-24)
                hit = hit._replace(start=low + code.start(), norm=norm)
        hits.append(hit)
    taken = [(h.start, h.end) for h in hits if h.kind == "amt"]
    if rules.head is not None and rules.head_code is not None:
        for found in rules.head.finditer(text[: rules.head_chars]):
            position = found.end("v")
            while True:
                line = HEAD_NEXT_LINE.match(text, position)
                if not line or not rules.head_code.match(line.group("v")):
                    break
                office = head_office(line.group("v"), rules)
                if office and not _overlaps(line.start("v"), line.end("v"), taken):
                    taken.append((line.start("v"), line.end("v")))
                    hits.append(Hit(line.start("v"), line.end("v"), "amt", office[0], "kopf"))
                position = line.end("v")
    if rules.office_text is not None:
        for found in rules.office_text.finditer(text):
            if _overlaps(found.start(), found.end(), taken):
                continue
            number = found.group("n")
            norm = f"{rules.office_text_norm} {number}" if number else rules.office_text_norm
            taken.append((found.start(), found.end()))
            hits.append(Hit(found.start(), found.end(), "amt", norm, "text"))
    if rules.office_word is not None:
        for found in rules.office_word.finditer(text):
            name = found.group("name")
            if rules.office_word_not is not None and rules.office_word_not.search(name):
                continue
            if _overlaps(found.start(), found.end(), taken):
                continue
            taken.append((found.start(), found.end()))
            hits.append(
                Hit(found.start(), found.end(), "amt", rules.directory.get(name, name), "wort")
            )
    yield from hits


# --- Ein Text, dann der Korpus ----------------------------------------------------------------


def _hits_in_text(text: str, rules: IdentifierRules, result: list[Hit] | None = None) -> bool:
    assert result is not None
    return all(0 <= h.start < h.end <= len(text) for h in result) and result == sorted(
        result, key=lambda h: (h.start, h.end, h.kind)
    )


# deal.safe statt deal.pure: die Funktion läuft je Dokument, und der Patcher von deal.has ist
# prozessweit und nicht reentrant (CLAUDE.md, „Nie").
@deal.safe
@deal.ensure(_hits_in_text, message="jede Kennung liegt im Text, nach Start, Ende und Art sortiert")
def find_identifiers(text: str, rules: IdentifierRules) -> list[Hit]:
    """Alle Kennungen der Arten aus ``rules.kinds`` in einem Rohtext, nach Start, Ende und Art."""
    hits: list[Hit] = []
    if rules.kinds & {"bplan", "fnp"}:
        hits.extend(plan_numbers(text, rules))
    if "betrag" in rules.kinds:
        hits.extend(amounts(text, rules))
    if "termin" in rules.kinds:
        hits.extend(dates(text, rules))
    if rules.kinds & {"amt", "dezernat"}:
        hits.extend(offices(text, rules))
    chosen = [h for h in hits if h.kind in rules.kinds]
    chosen.sort(key=lambda h: (h.start, h.end, h.kind))
    return chosen


TEXT_COLUMNS = ("name", "text", "extractor")  # aus dem Rohtextstore (F1)
DOCUMENT_COLUMNS = ("id", "file_name")  # aus dem Korpus


def _lengths(texts: pl.DataFrame, documents: pl.DataFrame) -> dict[str, int]:
    """Je Korpus-ID die Länge des Rohtexts ihrer Datei."""
    joined = documents.join(
        texts.select("name", pl.col("text").str.len_chars().alias("length")),
        left_on="file_name",
        right_on="name",
        how="inner",
    )
    return dict(zip(joined.get_column("id").to_list(), joined.get_column("length"), strict=True))


def _spans_hold(
    texts: pl.DataFrame,
    documents: pl.DataFrame,
    rules: IdentifierRules,
    result: pl.DataFrame | None = None,
) -> bool:
    """F3 mit ``attr`` dahinter, jede Spanne in ihrem Text, ``value`` wörtlich der Text."""
    assert result is not None
    if result.columns != [*SPAN_SCHEMA, ATTR] or result.schema[ATTR] != pl.String():
        return False
    try:
        check_spans(result, _lengths(texts, documents))
    except SchemaError:
        return False
    return True


def _norms_and_forms_hold(
    texts: pl.DataFrame,
    documents: pl.DataFrame,
    rules: IdentifierRules,
    result: pl.DataFrame | None = None,
) -> bool:
    """Ein Betrag ist eine Dezimalzahl, ein Termin hat eine Normform des Codebuchs .2, jede Form
    gehört zu ihrer Art, und innerhalb einer Art überlappen zwei Spannen eines Dokuments nur als das
    Paar aus ``MAY_OVERLAP`` (``overlaps_are_allowed``)."""
    assert result is not None
    relative = {norm for norm, _ in rules.relative}
    for kind, norm, attr in result.select("kind", "norm", ATTR).unique().iter_rows():
        if attr not in FORMS.get(kind, frozenset()):
            return False
        if kind == "betrag" and not re.fullmatch(r"-?\d+\.\d{2}", norm):
            return False
        if kind == "termin" and not (norm in relative or DATE_NORM.fullmatch(norm)):
            return False
    return overlaps_are_allowed(result)


def overlaps_are_allowed(spans: pl.DataFrame) -> bool:
    """Zwei Spannen derselben Art eines Dokuments überlappen nur als das Paar aus ``MAY_OVERLAP``.

    Die frühere trägt die Form ``nummer``, die spätere ``name``, beginnt hinter ihr, endet nicht vor
    ihr und beginnt mit einer Ziffer, vor der in der Nummer keine Ziffer steht: der Name hat die
    Nummer nach vorn in seine Spanne genommen („Amt 10" und „10 – Hauptamt"), nicht mitten in ihr
    begonnen. Jedes andere Paar ist ein Fehler. Erst die Spannen, die eine
    frühere überlappen (das späteste Ende davor über ``cum_max``), dann je solche Spanne jede
    frühere, die sie überlappt; das sind wenige.
    """
    kind, first, second = MAY_OVERLAP
    rows = spans.select("id", "kind", "start", "end", "value", ATTR).with_row_index("zeile")
    later = (
        rows.sort("id", "kind", "start", "end")
        .with_columns(pl.col("end").cum_max().shift(1).over("id", "kind").alias("before"))
        .filter(pl.col("start") < pl.col("before"))
        .drop("before")
    )
    if later.height == 0:
        return True
    pairs = later.join(rows, on=["id", "kind"], suffix="_frueh").filter(
        (pl.col("zeile_frueh") != pl.col("zeile"))
        & (pl.col("start_frueh") <= pl.col("start"))
        & (pl.col("end_frueh") > pl.col("start"))
    )
    allowed = (
        (pl.col("kind") == kind)
        & (pl.col(f"{ATTR}_frueh") == first)
        & (pl.col(ATTR) == second)
        & (pl.col("start_frueh") < pl.col("start"))
        & (pl.col("end_frueh") <= pl.col("end"))
        & pl.col("value").str.contains(r"^\d")
        # die Nummer beginnt dort, wo der Name beginnt, nicht mitten in ihr (Review K1)
        & ~pl.col("value_frueh")
        .str.slice(pl.col("start") - pl.col("start_frueh") - 1, 1)
        .str.contains(r"\d")
    )
    return pairs.filter(~allowed.fill_null(False)).height == 0


# Normformen eines Termins nach Codebuch .2: Tag, Monat (mit Zusatz), Quartal, Halbjahr, Jahr mit
# Zusatz
DATE_NORM = re.compile(r"\d{4}-\d{2}-\d{2}|\d{4}-\d{2}(?:~[a-z]+)?|\d{4}-[QH][1-4]|\d{4}~[a-z]+")


@deal.pre(
    lambda texts, documents, rules: (
        has_columns(texts, *TEXT_COLUMNS) and has_columns(documents, *DOCUMENT_COLUMNS)
    ),
    message="Rohtexte mit name, text, extractor; Korpus mit id, file_name",
)
@deal.ensure(_spans_hold, message="Spannen nach F3 mit attr, jede in ihrem Text, sortiert")
@deal.ensure(_norms_and_forms_hold, message="Normwerte und Formen je Art, keine Überlappung")
def identifier_spans(
    texts: pl.DataFrame, documents: pl.DataFrame, rules: IdentifierRules
) -> pl.DataFrame:
    """Die Spannen aller Kennungen je Korpus-ID (``processed/kennungen.parquet``).

    ``texts`` ist der Rohtextstore (je Dateiname ein Text, F1), ``documents`` der Korpus mit
    ``id`` und ``file_name``. **Jede** Korpus-ID, deren Paper die Datei trägt, bekommt die Spannen
    der Datei (Synergien 2026-11, § 1); eine Datei ohne Korpus-ID fällt weg, ein Dokument ohne
    Rohtext hat keine Spanne. ``extractor`` ist ``kennungen-1/`` vor dem Extraktor des Rohtexts.
    ``rules`` trägt das Ämterverzeichnis schon (``with_directory``).
    """
    files = documents.select("file_name").drop_nulls().unique()
    usable = (
        texts.select(*TEXT_COLUMNS)
        .filter(pl.col("text").is_not_null())
        .join(files, left_on="name", right_on="file_name", how="semi")
        .sort("name")
    )
    rows: list[tuple[str, int, int, str, str, str, str, str | None]] = []
    for name, text, extractor in usable.iter_rows():
        label = f"{METHOD}/{extractor}"
        for hit in find_identifiers(text, rules):
            value = text[hit.start : hit.end]
            rows.append((name, hit.start, hit.end, hit.kind, value, hit.norm, label, hit.attr))
    if not rows:
        return empty_spans(EXTRA)
    found = pl.DataFrame(
        rows,
        schema={
            "file_name": pl.String(),
            "start": pl.Int64(),
            "end": pl.Int64(),
            "kind": pl.String(),
            "value": pl.String(),
            "norm": pl.String(),
            "extractor": pl.String(),
            ATTR: pl.String(),
        },
        orient="row",
    )
    spans = (
        documents.select(*DOCUMENT_COLUMNS)
        .drop_nulls()
        .join(found, on="file_name", how="inner")
        .with_columns(pl.lit("").alias("section"))
    )
    return sort_spans(spans.select(*SPAN_SCHEMA, ATTR))


def identifier_figures(spans: pl.DataFrame) -> dict[str, int]:
    """Spannen je Art in der Folge der Arten, dazu Dokumente mit mindestens einer Spanne."""
    found = dict(spans.group_by("kind").len().iter_rows())
    figures = {kind: int(found.get(kind, 0)) for kind in FORMS}
    figures["dokumente"] = spans.get_column("id").n_unique()
    return figures
