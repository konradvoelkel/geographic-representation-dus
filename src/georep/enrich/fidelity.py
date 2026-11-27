"""Treueprüfung einer Kurzfassung gegen ihre Eingabe (Vorhaben 20, deterministisch, ohne Modell).

Das Verfahren ist das des Messskripts ``docs/plans/20-kurzfassungen-messung.py`` (``belege``,
``angaben``, ``pruefe``; Messdokument § 3.1), mit Klasse e in Fassung 2 (§ 5.2, ``kategorie``) und
den drei Korrekturen aus Frage 20.12, als reine Funktionen. Geprüft wird jede **Angabe** der
Kurzfassung gegen ihre **Eingabe**, also gegen den Text, den das Modell sah (Kopfzeilen und
Abschnitte), nicht gegen das ganze Dokument: was das Modell nicht sah, kann es nur erfunden haben.

Vier Klassen, in dieser Folge erkannt; was eine Erkennung nimmt, ist für die folgenden verdeckt:

1. ``drucksache`` -- eine Drucksachennummer in einer der Formen des Stadtprofils
   (``[[procedures.forms]]``, Vorhaben 14, ``prep.references.find_hits``), als Schlüssel
   verglichen. Abweichung vom Messskript, das ein eigenes Muster hatte: so kennt die Prüfung jede
   Form jeder Stadt (Mönchengladbach ``0302/X``) und keine Stadt im Code.
2. ``datum`` -- ``TT.MM.JJJJ``, ``TT.MM.JJ``, ``TT. Monat JJJJ``, ``JJJJ-MM-TT``, ``Monat JJJJ``
   (``monat``) und ``TT.MM.``, ``TT. Monat`` ohne Jahr (``tag``), normalisiert zu (Tag, Monat,
   Jahr). Ein Jahr allein ist eine Zahl.
3. ``zahl`` -- jede Zahl in Ziffern mit Tausendertrennern und Dezimalkomma, mit Einheit (Tsd.,
   Mio., Mrd. …) skaliert, Uhrzeiten (``uhrzeit``), die Zahlwörter zwei bis zwölf, zwanzig,
   dreißig, hundert (``zahlwort``). Eine gerundete oder selbst gerechnete Zahl ist unbelegt
   (Regel 3 des Prompts; Frage 20.12).
4. ``name`` -- Kürzel (``kuerzel``), Ortsnamen des Wörterbuchs (``ort``), das Wort nach einer
   Anrede (``person``) und jedes übrige großgeschriebene Wort, das im Korpus selten ist
   (``selten``, Klasse e).

**Klasse e in Fassung 2.** Das Deutsche schreibt jedes Substantiv groß; in Fassung 1 maß die Klasse
darum Abstrakta und Zusammensetzungen statt Namen (§ 3.2). Ein seltenes Wort, das nicht in der
Eingabe steht, ist nur dann eine unbelegte Angabe, wenn es kein Abstraktum ist, kein Wort des
Korpus (in mindestens drei Dokumenten) und keine Zusammensetzung aus Wörtern des Korpus; bei
Bindestrichen gilt das je Teil ab vier Zeichen, und ein Teil aus der Eingabe deckt sich selbst.
Sonst ist es kein Name, und die Prüfung zählt es nicht als Angabe. Bestätigt an frischen 200
Dokumenten (§ 4.2).

**Frage 20.12**, drei Fehlalarme der Umbaurunde, hier behoben: „ca." vor „Monat Jahr" in der Eingabe
hielt das Muster für „Tag. Monat Jahr" und verwarf die Monatsangabe; ein von pypdf geklebtes
„Monat2022" fehlte; unregelmäßige Plurale (Votum, Voten; Thema, Themen; Gremium, Gremien) fielen
durch die Endungsliste.

**Regel 5, daneben gezählt** (Hinweis des Supervisors nach dem Review von 11, 2026-11-24): in
2014–2020 beginnt der Rumpf bei rund 4 095 Dokumenten mit dem Namen aus der Kopfzeile des
Dezernats, meist mit dem Amt davor („Beigeordnete …"). Schreibt eine Kurzfassung ihn ab, ist er
belegt und verletzt trotzdem Regel 5 (keine Personennamen). ``person_names`` zählt darum jeden
Namen hinter einer Anrede, einem Titel oder einem Amt (``summaries.person_titles``) und jeden
mehrteiligen Namen, der in der Eingabe hinter einem solchen Wort steht, auch ohne es; die Zahl
steht neben ``ok`` (``personennamen``), nicht darin. Ein Nachname allein ohne Amt bleibt ungezählt.

Was die Prüfung nicht sieht: Sachverhalte ohne Zahl und Namen, eine falsche Rolle, eine erfundene
Wirkung, Namen, die zugleich Wörter des Korpus sind. Das misst die Bewertung (Frage ``unbelegt``
des Codebuchs), nicht diese Funktionen.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import deal
import polars as pl

from georep.prep.references import ReferenceRules, find_hits

# Die vier Klassen in der Folge der Spalten von ``fidelity_row``; ``kind`` ist die Unterart.
CLASSES: tuple[str, ...] = ("zahl", "datum", "drucksache", "name")
KINDS: tuple[str, ...] = (
    "zahl",
    "zahlwort",
    "uhrzeit",
    "datum",
    "monat",
    "tag",
    "drucksache",
    "kuerzel",
    "ort",
    "person",
    "selten",
)

MONTHS: dict[str, int] = {
    "januar": 1,
    "jänner": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "febr": 2,
    "märz": 3,
    "maerz": 3,
    "mär": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}
_MONTH = (
    r"(Januar|Jänner|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|"
    r"Dezember|Jan\.|Febr?\.|Mär\.|Apr\.|Jun\.|Jul\.|Aug\.|Sept?\.|Okt\.|Nov\.|Dez\.)"
)
DATE_DIGITS = re.compile(r"(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(\d{4}|\d{2}))?(?![\d])")
DATE_WORD = re.compile(r"(?<!\d)(\d{1,2})\.\s?" + _MONTH + r"(?:\s?(\d{4}))?", re.IGNORECASE)
# Frage 20.12: ausgeschlossen ist nur „Tag. Monat Jahr" (eine Ziffer, ein Punkt, höchstens ein
# Leerzeichen davor); „ca. März 2022" zählt. Das Jahr darf am Monat kleben („Dezember2022").
MONTH_YEAR = re.compile(r"(?<!\d\.\s)(?<!\d\.)(?<!\d)\b" + _MONTH + r"\s?(\d{4})\b", re.IGNORECASE)
DATE_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
CLOCK = re.compile(r"(?<![\d.,])(\d{1,2})(?:[:.](\d{2}))?\s?Uhr\b")
FACTORS: dict[str, int] = {
    "tsd": 1000,
    "tausend": 1000,
    "t€": 1000,
    "teur": 1000,
    "mio": 10**6,
    "million": 10**6,
    "millionen": 10**6,
    "mrd": 10**9,
    "milliarde": 10**9,
    "milliarden": 10**9,
}
NUMBER = re.compile(
    r"(?<![\d.,/])(\d{1,3}(?:[.   ]\d{3})+|\d+)(?:,(\d+))?(?![\d])"
    r"(?:\s?(Tsd\.?|Tausend|T€|TEUR|Mio\.?|Millionen|Million|Mrd\.?|Milliarden|Milliarde)"
    r"(?![a-zäöüß]))?"
)
NUMBER_WORDS: dict[str, int] = {
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fünf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwölf": 12,
    "zwanzig": 20,
    "dreißig": 30,
    "hundert": 100,
}
NUMBER_WORD = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", re.IGNORECASE)
ACRONYM = re.compile(
    r"(?<![\w-])([A-ZÄÖÜ]{1,6}\s?\d{1,2}|[A-ZÄÖÜ][A-Za-zÄÖÜäöü]*[A-ZÄÖÜ][A-Za-zÄÖÜäöü]*\d{0,2})"
    r"(?![\w])"
)
ROMAN = re.compile(r"^[IVXLC]+$")
CURRENCY = frozenset({"EUR", "EURO", "TEUR"})
PERSON = re.compile(r"\b(?:Herrn?|Frau|Dr\.|Prof\.)\s+([A-ZÄÖÜ][\wäöüß-]+)")
WORD = re.compile(r"(?<![\w-])([A-ZÄÖÜ][a-zäöüß][\wäöüß]*(?:-[\wäöüß]+)*)")
ENDINGS = ("ern", "en", "er", "es", "e", "n", "s")
# Frage 20.12: Plurale auf -en zu Singularen auf -um, -a, -us, -on, -is (Voten, Themen, Gremien,
# Stadien, Basen) und zurück; der Stamm davor hat mindestens drei Zeichen.
LATIN_SINGULAR = ("um", "a", "us", "on", "is")
ABSTRACT = re.compile(r"(ung|heit|keit|schaft|ität|ion|nis|tum|ismus)(en|e|s|es|n|ses|sen)?$")
JOINTS = ("", "s", "es", "n", "en")  # Fugen einer Zusammensetzung (Klasse e, Fassung 2)
TOKEN = r"[a-zäöüß][a-zäöüß0-9]*(?:-[a-zäöüß0-9]+)*"  # Wort des Korpus für die Verbreitung
KNOWN_TOKEN = r"[a-zäöüß]{3,}"  # Wort des Korpus für Fassung 2 (Teile ab drei Zeichen)
# Regel 5: ein Name ist ein großgeschriebenes Wort ab drei Buchstaben (nicht „Nr."), mit
# Bindestrich und Initiale; der zweite Teil steht in derselben Zeile. Ohne Leerraum hinter dem
# Titel ist es ein Straßenname („Dr.-Hans-…-Weg"), kein Personenname (Regel 5, Fassung 2).
NAME = r"(?:[A-ZÄÖÜ]\.[ \t]?)?[A-ZÄÖÜ][a-zäöüß]{2,}(?:-[A-ZÄÖÜ][a-zäöüß]+)*(?![\w-])"


@dataclass(frozen=True)
class Claim:
    """Eine prüfbare Angabe der Kurzfassung und ob die Eingabe sie trägt."""

    cls: str  # eine aus CLASSES
    kind: str  # eine aus KINDS
    text: str  # wie sie in der Kurzfassung steht
    supported: bool


@dataclass(frozen=True)
class Lexicon:
    """Was die Prüfung außer der Eingabe braucht, je Profil einmal gebaut (``lexicon_from``).

    ``places`` sind die Ortsnamen des Wörterbuchs (klein, längste zuerst), ``bodies`` Kürzel ->
    Name der Gremien (Name klein), ``district_code`` und ``district_name`` das Kürzel der
    Bezirksvertretungen und ihr Name mit ``{n}``. ``frequent`` sind die Wörter, die zu häufig sind,
    um Namen zu sein (Klasse e prüft sie nicht), ``known`` die Wörter des Korpus für Fassung 2.
    ``references`` und ``codes`` sind die Formen der Drucksachennummer und die bekannten Kürzel
    (Vorhaben 14); ohne Formen gibt es die Klasse ``drucksache`` nicht, und ihre Ziffern werden als
    Zahlen geprüft.
    """

    places: tuple[str, ...] = ()
    bodies: Mapping[str, str] = field(default_factory=dict)
    district_code: str = ""
    district_name: str = "{n}"
    frequent: frozenset[str] = frozenset()
    known: frozenset[str] = frozenset()
    references: ReferenceRules | None = None
    codes: frozenset[str] = frozenset()
    # Regel 5: Anrede, Titel oder Amt vor einem Personennamen; ohne Muster zählt nichts
    person_titles: re.Pattern[str] | None = None


@dataclass(frozen=True)
class Evidence:
    """Was in einer Eingabe steht, normalisiert: die Mengen, gegen die eine Kurzfassung geprüft wird."""

    lower: str  # klein, Leerraum zu einem Zeichen, Silbentrennung am Zeilenende weg
    compact: str  # dazu ohne jeden Leerraum: pypdf klebt und trennt Wörter
    dates: frozenset[tuple[int, int, int]]
    months: frozenset[tuple[int, int]]
    days: frozenset[tuple[int, int]]
    times: frozenset[tuple[int, int]]
    numbers: frozenset[str]
    references: frozenset[str]
    persons: frozenset[str] = frozenset()  # Namen hinter Anrede, Titel oder Amt (Regel 5)


def _year(text: str | None) -> int | None:
    if not text:
        return None
    number = int(text)
    return number + 2000 if number < 100 else number


@deal.ensure(lambda value, result: Decimal(result) == value.normalize())
def number_key(value: Decimal) -> str:
    """Eine Zahl als Text ohne überflüssige Nullen und ohne Exponent: 1500000, 12.5."""
    # Das Format "f" schreibt auch eine ganze Zahl im Exponenten aus (1.5E+6 -> 1500000); quantize
    # dagegen bricht bei mehr als 28 Stellen mit InvalidOperation ab (2026-11-27, hypothesis)
    return format(value.normalize(), "f")


def _value(whole: str, fraction: str | None, unit: str | None) -> tuple[Decimal, Decimal | None]:
    """Wert einer Zahl und, mit Einheit (Tsd., Mio., Mrd.), der skalierte Wert."""
    digits = re.sub(r"[.   ]", "", whole)
    try:
        value = Decimal(f"{digits}.{fraction}" if fraction else digits)
    except InvalidOperation:
        value = Decimal(0)
    if not unit:
        return value, None
    return value, value * FACTORS.get(unit.lower().rstrip("."), 1)


def _lower(text: str) -> str:
    """Klein, Zeichen für Zeichen gleich lang: Stellen im Text bleiben Stellen im Kleintext."""
    return "".join(low if len(low := char.lower()) == 1 else char for char in text)


def normalize_text(text: str) -> str:
    """Klein, Bindestriche vereinheitlicht, Silbentrennung am Zeilenende weg, Leerraum zu einem."""
    text = text.replace("­", "").replace("‐", "-").replace("–", "-").replace("—", "-")
    # vor dem Kleinschreiben: „Verwal-\ntung" ist Silbentrennung, „Löbe-\nStraße" ein Bindestrich
    text = re.sub(r"(?<=[a-zäöüß])-\s*\n\s*(?=[a-zäöüß])", "", text)
    return re.sub(r"\s+", " ", text.lower())


def _titled_names(text: str, titles: re.Pattern[str]) -> list[tuple[int, int, str]]:
    """Namen hinter einer Kette aus Anrede, Titel und Amt: (Anfang, Ende, Name mit einem Leerzeichen)."""
    pattern = re.compile(
        rf"(?<![\w-])(?:{titles.pattern})(?:\s+(?:{titles.pattern}))*\s+"
        rf"(?P<name>{NAME}(?:[ \t]+{NAME})?)"
    )
    return [
        (m.start("name"), m.end("name"), " ".join(m.group("name").split()))
        for m in pattern.finditer(text)
    ]


def _reference_keys(text: str, lexicon: Lexicon) -> list[tuple[int, int, str]]:
    if lexicon.references is None:
        return []
    hits = find_hits(_lower(text), lexicon.references, lexicon.codes)
    return [(hit.start, hit.end, hit.reference.key) for hit in hits]


@deal.post(lambda result: result.compact == re.sub(r"\s+", "", result.lower))
def evidence(text: str, lexicon: Lexicon) -> Evidence:
    """Die Belege einer Eingabe: Daten, Monate, Tage, Uhrzeiten, Zahlen, Drucksachennummern.

    Zahlen zählen großzügig: jede Zahl mit und ohne Einheit, jede Ziffernfolge (auch die Teile von
    Daten, Nummern und Beträgen) und die Zahlwörter.
    """
    lower = normalize_text(text)
    dates: set[tuple[int, int, int]] = set()
    months: set[tuple[int, int]] = set()
    days: set[tuple[int, int]] = set()
    for d, m, y in DATE_DIGITS.findall(text):
        dd, mm, yy = int(d), int(m), _year(y)
        if 1 <= dd <= 31 and 1 <= mm <= 12:
            days.add((dd, mm))
            if yy:
                dates.add((dd, mm, yy))
                months.add((mm, yy))
    for d, name, y in DATE_WORD.findall(text):
        mm = MONTHS[name.lower().rstrip(".")]
        days.add((int(d), mm))
        if y:
            dates.add((int(d), mm, int(y)))
            months.add((mm, int(y)))
    for name, y in MONTH_YEAR.findall(text):
        months.add((MONTHS[name.lower().rstrip(".")], int(y)))
    for y, m, d in DATE_ISO.findall(text):
        dates.add((int(d), int(m), int(y)))
        days.add((int(d), int(m)))
        months.add((int(m), int(y)))
    times = {(int(h), int(mi or 0)) for h, mi in CLOCK.findall(text)}
    numbers: set[str] = set()
    for match in NUMBER.finditer(text):
        value, scaled = _value(match.group(1), match.group(2), match.group(3))
        numbers.add(number_key(value))
        if scaled is not None:
            numbers.add(number_key(scaled))
    numbers.update(str(int(run)) for run in re.findall(r"\d+", text))
    numbers.update(str(NUMBER_WORDS[word.lower()]) for word in NUMBER_WORD.findall(text))
    references = {key for _, _, key in _reference_keys(text, lexicon)}
    titles = lexicon.person_titles
    persons = {name for _, _, name in _titled_names(text, titles)} if titles else set()
    return Evidence(
        lower,
        re.sub(r"\s+", "", lower),
        frozenset(dates),
        frozenset(months),
        frozenset(days),
        frozenset(times),
        frozenset(numbers),
        frozenset(references),
        frozenset(persons),
    )


def _in_text(term: str, ev: Evidence) -> bool:
    """Ein Name steht in der Eingabe: als Teilfolge, ohne Leerraum, „str." gleich „straße"."""
    low = normalize_text(term).strip()
    variants = {
        low,
        low.replace("str.", "straße"),
        low.replace("straße", "str."),
        low.replace("ß", "ss"),
    }
    return any(v and (v in ev.lower or v.replace(" ", "") in ev.compact) for v in variants)


def _plural_forms(word: str) -> set[str]:
    """Frage 20.12: die unregelmäßigen Formen eines Wortes (Voten ↔ Votum, Themen ↔ Thema)."""
    forms: set[str] = set()
    if word.endswith("en") and len(word) - 2 >= 3:
        forms.update(word[:-2] + ending for ending in LATIN_SINGULAR)
    for ending in LATIN_SINGULAR:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            forms.add(word[: -len(ending)] + "en")
    return forms


def _stem_in_text(word: str, ev: Evidence) -> bool:
    """Ein Wort steht in der Eingabe, auch gebeugt oder als Teil eines längeren Wortes."""
    low = word.lower()
    if _in_text(low, ev):
        return True
    for ending in ENDINGS:
        if (
            low.endswith(ending)
            and len(low) - len(ending) >= 4
            and _in_text(low[: -len(ending)], ev)
        ):
            return True
    return any(_in_text(form, ev) for form in _plural_forms(low))


def _acronym_supported(token: str, ev: Evidence, lexicon: Lexicon) -> bool:
    token = token.replace(" ", "")
    low = token.lower()
    plural = len(low) > 3 and token.endswith("s") and token[-2].isupper()
    for form in {low, low[:-1] if plural else low}:
        if len(form) >= 3 and form in ev.compact:
            return True
        if re.search(rf"(?<![a-zäöüß]){re.escape(form)}(?![a-zäöüß])", ev.lower):
            return True
    upper = token.upper()
    district = lexicon.district_code
    if district and upper == district and _in_text(lexicon.district_name.split("{")[0], ev):
        return True
    match = re.fullmatch(rf"{re.escape(district)}(\d{{1,2}})", upper) if district else None
    if match and _in_text(lexicon.district_name.format(n=int(match.group(1))), ev):
        return True
    name = lexicon.bodies.get(upper, "")
    return bool(name) and _in_text(name, ev)


def decomposable(word: str, known: frozenset[str], depth: int = 0) -> bool:
    """Lässt sich das Wort in Wörter des Korpus zerlegen (Teile ab drei Zeichen, mit Fugen)?"""
    low = word.lower()
    if depth and low in known:
        return True
    if depth > 3:
        return False
    for cut in range(3, len(low) - 2):
        head, tail = low[:cut], low[cut:]
        for joint in JOINTS:
            if joint and not head.endswith(joint):
                continue
            stem = head[: len(head) - len(joint)] if joint else head
            if len(stem) < 3 or stem not in known:
                continue
            if tail in known or decomposable(tail, known, depth + 1):
                return True
    return False


def is_name(word: str, ev: Evidence, known: frozenset[str]) -> bool:
    """Klasse e, Fassung 2: ist ein seltenes Wort, das nicht in der Eingabe steht, ein Name?

    Nein, wenn es (je Teil eines Bindestrichworts ab vier Zeichen, wobei ein Teil aus der Eingabe
    sich selbst deckt) ein Abstraktum ist, ein Wort des Korpus oder eine Zusammensetzung daraus.
    Hat ein Bindestrichwort keinen Teil ab vier Zeichen, gilt das ganze Wort als ein Teil.
    """
    parts = [part for part in word.split("-") if len(part) >= 4] if "-" in word else [word]
    for part in parts or [word.replace("-", "")]:
        if len(parts) > 1 and _stem_in_text(part, ev):
            continue
        low = part.lower()
        if ABSTRACT.search(low) or low in known or decomposable(low, known):
            continue
        return True
    return False


def _overlaps(start: int, end: int, taken: Iterable[tuple[int, int]]) -> bool:
    return any(start < z and a < end for a, z in taken)


@deal.ensure(
    lambda summary, ev, lexicon, result: all(
        c.cls in CLASSES and c.kind in KINDS and c.text for c in result
    ),
    message="jede Angabe hat Klasse, Unterart und Text",
)
def claims(summary: str, ev: Evidence, lexicon: Lexicon) -> list[Claim]:
    """Alle prüfbaren Angaben einer Kurzfassung mit dem Urteil „steht in der Eingabe"."""
    out: list[Claim] = []
    masked = summary

    def mask(start: int, end: int) -> None:
        nonlocal masked
        masked = masked[:start] + " " * (end - start) + masked[end:]

    for start, end, key in _reference_keys(summary, lexicon):
        if summary[start:end].strip() and masked[start:end].strip():
            out.append(Claim("drucksache", "drucksache", summary[start:end], key in ev.references))
            mask(start, end)
    for m in DATE_ISO.finditer(masked):
        iso_year, iso_month, iso_day = (int(x) for x in m.groups())
        found = (iso_day, iso_month, iso_year) in ev.dates
        out.append(Claim("datum", "datum", m.group(0), found))
        mask(*m.span())
    for m in DATE_WORD.finditer(masked):
        d, name, y = m.groups()
        mm = MONTHS[name.lower().rstrip(".")]
        ok = (int(d), mm, int(y)) in ev.dates if y else (int(d), mm) in ev.days
        out.append(Claim("datum", "datum" if y else "tag", m.group(0), ok))
        mask(*m.span())
    for m in DATE_DIGITS.finditer(masked):
        d, mo, y = m.groups()
        dd, mm, yy = int(d), int(mo), _year(y)
        if not (1 <= dd <= 31 and 1 <= mm <= 12):
            continue
        ok = (dd, mm, yy) in ev.dates if yy else (dd, mm) in ev.days
        out.append(Claim("datum", "datum" if yy else "tag", m.group(0), ok))
        mask(*m.span())
    for m in MONTH_YEAR.finditer(masked):
        mm, yy = MONTHS[m.group(1).lower().rstrip(".")], int(m.group(2))
        out.append(Claim("datum", "monat", m.group(0), (mm, yy) in ev.months))
        mask(*m.span())
    for m in CLOCK.finditer(masked):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        out.append(Claim("zahl", "uhrzeit", m.group(0), (hour, minute) in ev.times))
        mask(*m.span())
    for m in NUMBER.finditer(masked):
        value, scaled = _value(m.group(1), m.group(2), m.group(3))
        ok = number_key(value) in ev.numbers or (
            scaled is not None and number_key(scaled) in ev.numbers
        )
        out.append(Claim("zahl", "zahl", m.group(0).strip(), ok))
        mask(*m.span())
    for m in NUMBER_WORD.finditer(masked):
        word = m.group(1)
        out.append(Claim("zahl", "zahlwort", word, str(NUMBER_WORDS[word.lower()]) in ev.numbers))
    taken: list[tuple[int, int]] = []
    for m in PERSON.finditer(masked):
        out.append(Claim("name", "person", m.group(1), _stem_in_text(m.group(1), ev)))
        taken.append(m.span(1))
    low = masked.lower()
    for term in lexicon.places:
        start = 0
        while (pos := low.find(term, start)) >= 0:
            end = start = pos + len(term)
            before = low[pos - 1] if pos else " "
            after = low[end] if end < len(low) else " "
            if before.isalnum() or (after.isalpha() and not term.endswith(".")):
                continue
            if _overlaps(pos, end, taken):
                continue
            out.append(Claim("name", "ort", masked[pos:end], _in_text(term, ev)))
            taken.append((pos, end))
    for m in ACRONYM.finditer(masked):
        token = m.group(1)
        if ROMAN.match(token) or token.upper() in CURRENCY or _overlaps(*m.span(), taken):
            continue
        if sum(c.isupper() for c in token) < 2 and not re.search(r"\d", token):
            continue
        out.append(Claim("name", "kuerzel", token, _acronym_supported(token, ev, lexicon)))
        taken.append(m.span())
    for m in WORD.finditer(masked):
        word = m.group(1)
        if _overlaps(*m.span(), taken):
            continue
        lowered = word.lower()
        if lowered in lexicon.frequent or all(p in lexicon.frequent for p in lowered.split("-")):
            continue
        if _stem_in_text(word, ev):
            out.append(Claim("name", "selten", word, True))
        elif is_name(word, ev, lexicon.known):
            out.append(Claim("name", "selten", word, False))
        taken.append(m.span())
    return out


def person_names(summary: str, ev: Evidence, lexicon: Lexicon) -> list[str]:
    """Regel 5: die Personennamen einer Kurzfassung, in ihrer Folge; belegt oder nicht.

    Gezählt wird ein Name hinter Anrede, Titel oder Amt (``lexicon.person_titles``) und ein
    mehrteiliger Name, der in der Eingabe hinter einem solchen Wort steht, auch wenn die
    Kurzfassung das Wort weglässt („… legt vor" statt „die Beigeordnete … legt vor"). Ohne Muster
    zählt nichts.
    """
    titles = lexicon.person_titles
    if titles is None:
        return []
    found = _titled_names(summary, titles)
    for name in sorted(n for n in ev.persons if " " in n):
        words = r"[ \t]+".join(re.escape(part) for part in name.split())
        for m in re.finditer(rf"(?<![\w-]){words}(?![\w-])", summary):
            if not _overlaps(m.start(), m.end(), [(a, z) for a, z, _ in found]):
                found.append((m.start(), m.end(), name))
    return [name for _, _, name in sorted(found)]


@dataclass(frozen=True)
class Check:
    """Das Ergebnis einer Kurzfassung: ihre Angaben und ob sie leer oder abgeschnitten ist."""

    claims: tuple[Claim, ...]
    truncated: bool
    empty: bool
    persons: tuple[str, ...] = ()  # Regel 5, neben ``ok``

    @property
    def unsupported(self) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if not c.supported)

    @property
    def ok(self) -> bool:
        """Ohne unbelegte Angabe; eine leere oder abgeschnittene Kurzfassung besteht nie."""
        return not self.unsupported and not self.truncated and not self.empty


def check(summary: str | None, truncated: bool, ev: Evidence, lexicon: Lexicon) -> Check:
    """Die Prüfung einer Kurzfassung; ``None`` und Leerraum sind leer."""
    if summary is None or not summary.strip():
        return Check((), truncated, True)
    found = tuple(claims(summary, ev, lexicon))
    return Check(found, truncated, False, tuple(person_names(summary, ev, lexicon)))


FIDELITY_COLUMNS: dict[str, pl.DataType] = {
    "angaben": pl.Int32(),
    **{f"unbelegt_{cls}": pl.Int32() for cls in CLASSES},
    "personennamen": pl.Int32(),  # Regel 5, zählt nicht für ``ok``
    "ok": pl.Boolean(),
}


@deal.ensure(
    lambda outcome, result: (
        sum(int(result[f"unbelegt_{c}"]) for c in CLASSES) <= int(result["angaben"])
    ),
    message="nie mehr unbelegte als Angaben",
)
def fidelity_row(outcome: Check) -> dict[str, int | bool]:
    """Die Zählung einer Kurzfassung je Klasse, ohne ihren Text (``kurzfassungen_treue.parquet``)."""
    row: dict[str, int | bool] = {"angaben": len(outcome.claims)}
    for cls in CLASSES:
        row[f"unbelegt_{cls}"] = sum(1 for c in outcome.unsupported if c.cls == cls)
    row["personennamen"] = len(outcome.persons)
    row["ok"] = outcome.ok
    return row


def word_document_counts(corpus_lower: pl.Series, pattern: str) -> pl.DataFrame:
    """Je Wort (Muster ``pattern``) die Zahl der Dokumente, in denen es steht: ``wort``, ``dokumente``."""
    counts = (
        corpus_lower.fill_null("")
        .str.extract_all(pattern)
        .list.unique()
        .explode()
        .drop_nulls()
        .value_counts()
    )
    return counts.rename({counts.columns[0]: "wort", counts.columns[1]: "dokumente"}).sort("wort")


def lexicon_from(
    corpus_lower: pl.Series,
    places: Iterable[str],
    bodies: Mapping[str, str],
    *,
    district_code: str,
    district_name: str,
    rare_share: float,
    known_documents: int,
    references: ReferenceRules | None = None,
    codes: frozenset[str] = frozenset(),
    person_titles: str = "",
) -> Lexicon:
    """Das Lexikon eines Profils aus dem kleingeschriebenen Korpus und den Werten des Profils.

    ``frequent``: Wörter in mindestens ``rare_share`` der Dokumente mit Text (Messdokument § 3.1:
    1 %); ``known``: Wörter ab drei Buchstaben in mindestens ``known_documents`` Dokumenten
    (Fassung 2: drei). Ortsnamen ab vier Zeichen, längste zuerst; Gremiennamen klein.
    """
    texts = corpus_lower.fill_null("").filter(corpus_lower.fill_null("") != "")
    frequent = word_document_counts(texts, TOKEN).filter(
        pl.col("dokumente") >= rare_share * texts.len()
    )
    known = word_document_counts(texts, KNOWN_TOKEN).filter(pl.col("dokumente") >= known_documents)
    named = sorted({p.lower() for p in places if len(p) >= 4}, key=lambda p: (-len(p), p))
    return Lexicon(
        places=tuple(named),
        bodies={code: name.lower() for code, name in bodies.items() if name},
        district_code=district_code,
        district_name=district_name.lower(),
        frequent=frozenset(frequent.get_column("wort").to_list()),
        known=frozenset(known.get_column("wort").to_list()),
        references=references,
        codes=codes,
        person_titles=re.compile(person_titles) if person_titles else None,
    )
