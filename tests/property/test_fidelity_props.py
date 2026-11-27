"""Eigenschaften der Treueprüfung (Vorhaben 20, ``georep.enrich.fidelity``; Messdokument § 6).

1. Was die Prüfung in einem Text als Angabe findet, ist gegen denselben Text belegt, auch mit
   beliebigem Text davor und dahinter (getrennt durch eine Leerzeile): eine Kurzfassung, die nur
   abschreibt, besteht immer.
2. Die Normalisierung von Text und Zahl ist idempotent.
3. Ein Betrag in drei Schreibweisen (1.500.000 €, 1,5 Mio. €, 1 500 000 Euro) belegt sich
   gegenseitig.

Die Bausteine der Kurzfassungen sind erfunden; kein Ratstext.
"""

from __future__ import annotations

from decimal import Decimal
from functools import cache
from pathlib import Path

from hypothesis import example, given
from hypothesis import strategies as st

from georep.enrich.fidelity import Lexicon, claims, evidence, normalize_text, number_key
from georep.prep.references import ReferenceRules
from georep.settings import load_settings

NOWHERE = Path("/nonexistent")


@cache
def lexicon() -> Lexicon:
    """Einmal je Prozess gebaut; keine Fixture, weil ``given`` die Argumente von rechts füllt."""
    rules = ReferenceRules.from_settings(load_settings(cwd=NOWHERE).procedures)
    return Lexicon(
        places=("kölner straße", "nordpark", "am wehr"),
        bodies={"OVA": "ordnungs- und verkehrsausschuss", "RAT": "rat"},
        district_code="BV",
        district_name="bezirksvertretung {n}",
        frequent=frozenset({"die", "der", "das", "und", "ein", "eine", "verwaltung"}),
        known=frozenset({"weg", "netz", "platz"}),
        references=rules,
        codes=frozenset({"BV", "OVA", "RAT"}),
    )


MONTHS = ("Januar", "März", "Mai", "Juli", "Oktober", "Dezember")
day = st.integers(1, 28)
month = st.integers(1, 12)
year = st.integers(2014, 2030)
amount = st.integers(1, 9_999_999)

blocks = st.one_of(
    st.builds(lambda d, m, y: f"{d:02d}.{m:02d}.{y}", day, month, year),
    st.builds(lambda d, m, y: f"{d}. {MONTHS[m % len(MONTHS)]} {y}", day, month, year),
    st.builds(lambda m, y: f"{MONTHS[m % len(MONTHS)]} {y}", month, year),
    st.builds(lambda h, mi: f"{h}.{mi:02d} Uhr", st.integers(7, 22), st.integers(0, 59)),
    st.builds(lambda v: f"{v:,}".replace(",", ".") + " €", amount),
    st.builds(lambda v: f"{v} Euro", amount),
    st.builds(lambda v, c: f"{v},{c:02d} %", st.integers(0, 99), st.integers(0, 99)),
    st.builds(lambda n, s, y: f"BV{n}/{s:03d}/{y}", st.integers(1, 10), st.integers(1, 400), year),
    st.builds(lambda s, y: f"OVA/{s}/{y}/1", st.integers(1, 400), year),
    st.sampled_from(("drei", "zwölf", "hundert")),
    st.sampled_from(("Herr Kranich", "Frau Dr. Elster", "Prof. Wiesel")),
    st.sampled_from(("Kölner Straße", "Nordpark", "am Wehr")),
    st.sampled_from(("BV 3", "OVA", "KiTa", "ÖPNV")),
    st.sampled_from(("Rheinufer", "Hafenbecken", "Lindenhof", "Wiesenweg-Netz")),
    st.sampled_from(("die Verwaltung", "und", "ein", "will", "beschließt", "fragt")),
)
filler = st.text(
    alphabet=st.characters(codec="utf-8", exclude_categories=("Cs", "Cc")), max_size=60
)


@given(st.lists(blocks, min_size=1, max_size=8), filler, filler)
# 2026-11-27, Gegenbeispiel aus dem Worktree von 22: 29 Stellen nach dem Text lassen
# number_key(Decimal("1E+28")) mit quantize über die Kontextgenauigkeit von 28 Stellen laufen
@example(parts=["1 €"], before="", after="1" + "0" * 28)
def test_what_is_found_in_a_text_is_supported_by_it(
    parts: list[str], before: str, after: str
) -> None:
    lex = lexicon()
    summary = " ".join(parts) + "."
    # Leerzeilen trennen: ein Muster mit \s? (Datum, Nummer) reicht über höchstens ein Zeichen
    ev = evidence(f"{before}\n\n{summary}\n\n{after}", lex)
    unsupported = [c for c in claims(summary, ev, lex) if not c.supported]
    assert unsupported == []


@given(st.text(max_size=200))
def test_text_normalisation_is_idempotent(text: str) -> None:
    once = normalize_text(text)
    assert normalize_text(once) == once


@given(st.decimals(min_value=0, max_value=10**12, allow_nan=False, places=4))
@example(Decimal("1E+28"))
def test_number_normalisation_is_idempotent(value: Decimal) -> None:
    once = number_key(value)
    assert number_key(Decimal(once)) == once


def _dotted(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _spaced(value: int) -> str:
    return f"{value:,}".replace(",", " ")


@given(st.integers(10, 99_999))
def test_an_amount_in_three_spellings_supports_itself(tenths: int) -> None:
    lex = lexicon()
    value = tenths * 100_000  # ein Vielfaches von 0,1 Mio.
    millions = f"{Decimal(tenths) / 10:f}"
    if "." in millions:
        millions = millions.rstrip("0").rstrip(".")
    millions = millions.replace(".", ",")
    spellings = (f"{_dotted(value)} €", f"{millions} Mio. €", f"{_spaced(value)} Euro")
    for written in spellings:
        ev = evidence(f"Der Betrag ist {written}.", lex)
        for other in spellings:
            found = [c for c in claims(f"Es geht um {other}.", ev, lex) if c.cls == "zahl"]
            assert found and all(c.supported for c in found), (written, other, found)
