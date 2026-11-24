"""Eigenschaften der Kennungen und Beträge (Vorhaben 12), für alle Eingaben.

Aus dem Bauplan (Messdokument ``docs/plans/12-kennungen.md``, § 6): für jeden Text liegen alle
Spannen im Text, sind sortiert und überlappen in ihrer Art nicht; ein Betrag, deutsch geschrieben
(Tausenderpunkt, Komma, Faktor), wird dieselbe Dezimalzahl; jedes gültige Datum ergibt in jeder
Schreibweise dasselbe ISO-Datum; die Normalform einer Plannummer und eines Datums ist ein Fixpunkt;
ohne Ziffern gibt es keine Plannummer, keinen Betrag, kein Dezernat und nur relative Termine.
Beide Stadtprofile, weil ihre Muster verschieden sind.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from georep.prep.identifiers import (
    MAY_OVERLAP,
    IdentifierRules,
    find_identifiers,
    iso_date,
    plan_norm,
)
from georep.settings import load_settings

NOWHERE = Path("/nonexistent")
CITY = load_settings(cwd=NOWHERE)
SECOND = load_settings(profile="moenchengladbach", cwd=NOWHERE)
DIRECTORY = {"Umweltamt": "19", "Amt für Verkehrsmanagement": "66"}
RULES = (
    IdentifierRules.from_settings(CITY.identifiers).with_directory(DIRECTORY),
    IdentifierRules.from_settings(SECOND.identifiers),
)
MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)

# Bausteine echter Ratsdokumente: Schlüsselwörter, Einheiten, Monate, Kopffelder, Trenner.
WORDS = (
    "Bebauungsplan",
    "Bebauungspläne",
    "B-Plan",
    "Flächennutzungsplanänderung",
    "FNP",
    "Änderung des Flächennutzungsplans",
    "Nr.",
    "und",
    "bis",
    "bis zum",
    "Euro",
    "EUR",
    "€",
    "T€",
    "Mio.",
    "Tsd.",
    "je",
    "/m²",
    "Quartal",
    "Halbjahr",
    "Ende",
    "Frühjahr",
    "des Jahres",
    "in der nächsten Sitzung",
    "nach der Sommerpause",
    "innerhalb von drei Monaten",
    "Fachbereich:",
    "Amt",
    "Dezernat",
    "Umweltamt",
    "Umweltamts",
    "Gartenamt",
    "Amt für Verkehrsmanagement",
    "Ausschuss für",
    "Bezirksverwaltungsstelle",
    "FB",
    "-",
    "–",
    ",",
    ".",
    "(",
    ")",
    "+",
    "\n",
    "\f",
    " ",
    *MONTHS,
)
TOKENS = st.one_of(
    st.sampled_from(WORDS),
    st.integers(0, 99999).map(str),
    st.from_regex(r"\d{1,4}[./ -]\d{1,3}(?:[./]\d{2,4})?", fullmatch=True),
    st.text(alphabet="0123456789.,/-IVXNO äöüßA", max_size=6),
)
TEXTS = st.lists(TOKENS, max_size=40).map(" ".join)


@given(TEXTS, st.sampled_from(RULES))
def test_jede_spanne_liegt_im_text_sortiert_und_ohne_ueberlappung(
    text: str, rules: IdentifierRules
) -> None:
    """Ämter ausgenommen: „Amt 10 – Hauptamt" sind zwei Spannen, wie validiert (``MAY_OVERLAP``)."""
    hits = find_identifiers(text, rules)
    assert hits == sorted(hits, key=lambda h: (h.start, h.end, h.kind))
    ends: dict[str, int] = {}
    for hit in hits:
        assert 0 <= hit.start < hit.end <= len(text)
        if hit.kind not in MAY_OVERLAP:
            assert hit.start >= ends.get(hit.kind, 0), (hit, text)
        ends[hit.kind] = max(ends.get(hit.kind, 0), hit.end)


def test_aemter_duerfen_sich_ueberlappen() -> None:
    """Das Beispiel aus Mönchengladbach (§ 3.4): die Nummer bleibt, der Name nimmt sie mit."""
    text = "Siehe Fachbereich 20 – Kämmerei."
    rules = IdentifierRules.from_settings(SECOND.identifiers).with_directory({"Kämmerei": "20"})
    assert [(text[h.start : h.end], h.attr) for h in find_identifiers(text, rules)] == [
        ("Fachbereich 20", "nummer"),
        ("20 – Kämmerei", "name"),
    ]


@given(TEXTS, st.sampled_from(RULES))
def test_ohne_ziffern_nur_relative_termine_und_aemter(text: str, rules: IdentifierRules) -> None:
    letters = "".join(c for c in text if not c.isdigit())
    for hit in find_identifiers(letters, rules):
        assert hit.kind in {"termin", "amt"}, hit
        if hit.kind == "termin":
            assert hit.attr == "relativ", hit


def _german(value: Decimal) -> str:
    """Ein Betrag, wie eine Vorlage ihn schreibt: Tausenderpunkt, Komma, zwei Nachkommastellen."""
    whole, _, cents = f"{value:.2f}".partition(".")
    groups: list[str] = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return ".".join(groups) + ("," + cents if cents != "00" else "")


@given(
    st.decimals(min_value=Decimal("1.00"), max_value=Decimal("999999999.99"), places=2),
    st.sampled_from(["Euro", "EUR", "€"]),
)
def test_ein_deutsch_geschriebener_betrag_wird_dieselbe_zahl(value: Decimal, unit: str) -> None:
    text = f"Die Kosten betragen {_german(value)} {unit} brutto."
    found = [h for h in find_identifiers(text, RULES[0]) if h.kind == "betrag"]
    assert [Decimal(h.norm) for h in found] == [value]


@given(
    st.decimals(min_value=Decimal("0.1"), max_value=Decimal("999.9"), places=1),
    st.sampled_from([("Mio.", 1_000_000), ("Mrd.", 1_000_000_000), ("Tsd.", 1000)]),
)
def test_ein_faktor_multipliziert(value: Decimal, multiplier: tuple[str, int]) -> None:
    written = f"{value}".replace(".", ",")
    text = f"rund {written} {multiplier[0]} Euro"
    found = [h for h in find_identifiers(text, RULES[0]) if h.kind == "betrag"]
    assert [Decimal(h.norm) for h in found] == [(value * multiplier[1]).quantize(Decimal("0.01"))]


DAYS = st.dates(min_value=date(1950, 1, 1), max_value=date(2040, 12, 31))


@given(DAYS, st.integers(0, 3), st.sampled_from(RULES))
def test_jedes_datum_in_jeder_schreibweise_wird_dasselbe_iso_datum(
    day: date, form: int, rules: IdentifierRules
) -> None:
    written = (
        f"{day.day:02d}.{day.month:02d}.{day.year}",
        f"{day.day}.{day.month}.{day.year}",
        f"{day.day}. {MONTHS[day.month - 1]} {day.year}",
        day.isoformat(),
    )[form]
    found = [
        h for h in find_identifiers(f"Sitzung am {written} im Rathaus", rules) if h.kind == "termin"
    ]
    assert [h.norm for h in found] == [day.isoformat()]


@given(DAYS)
def test_ein_iso_datum_ist_ein_fixpunkt(day: date) -> None:
    """Die Normalform eines Tages, wieder gelesen, ist sie selbst."""
    norm = iso_date(day.day, day.month, day.year)
    assert norm == day.isoformat()
    found = find_identifiers(f"Stand {norm}.", RULES[0])
    assert [h.norm for h in found] == [norm]


@given(DAYS)
def test_kein_ungueltiger_tag(day: date) -> None:
    """Der Tag nach dem letzten eines Monats ist nie ein Datum desselben Monats."""
    last = (day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    assert iso_date(last.day + 1, last.month, last.year) is None


PLAN_NUMBERS = st.one_of(
    st.from_regex(r"\d{4}[ \t]?[/-][ \t]?\d{2,3}|\d{4} \d{3}|\d{2}[/-]\d{3}", fullmatch=True),
)


@given(PLAN_NUMBERS)
def test_die_normalform_einer_plannummer_ist_ein_fixpunkt(number: str) -> None:
    once = plan_norm(number, RULES[0])
    assert plan_norm(once, RULES[0]) == once
    assert " " not in once and "\t" not in once


@given(st.from_regex(r"\d{1,4}/(?:[NOSW]|[IVX]{1,4})", fullmatch=True))
def test_die_normalform_der_zweiten_stadt_ist_ein_fixpunkt(number: str) -> None:
    once = plan_norm(number, RULES[1])
    assert plan_norm(once, RULES[1]) == once == number.upper()


@given(PLAN_NUMBERS)
def test_eine_plannummer_hinter_dem_schluesselwort_wird_gefunden(number: str) -> None:
    text = f"Bebauungsplan Nr. {number} "
    found = [h for h in find_identifiers(text, RULES[0]) if h.kind == "bplan"]
    assert [text[h.start : h.end] for h in found] == [number]
    assert [h.norm for h in found] == [plan_norm(number, RULES[0])]
