"""Treueprüfung einer Kurzfassung gegen ihre Eingabe (Vorhaben 20, ``georep.enrich.fidelity``).

Die Fälle sind erfunden (Konrads Regel: keine Kurzfassung und kein Ratstext in Tests): die 14 Fälle
des Selbsttests aus dem Messskript (``docs/plans/20-kurzfassungen-messung.py``, ``selbsttest``),
die Fehlalarme der Klasse e aus der ersten Runde als Muster (Messdokument § 3.2: Abstraktum,
Wort des Korpus, Zusammensetzung, Bindestrich), Klasse e in Fassung 2 (§ 5.2) und die drei Mängel
aus Frage 20.12. Die Drucksachennummern liest die Prüfung mit den Formen des Stadtprofils
(Vorhaben 14); die Tests nehmen sie von dort.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from georep.enrich.fidelity import (
    CLASSES,
    Claim,
    Lexicon,
    check,
    claims,
    decomposable,
    evidence,
    fidelity_row,
)
from georep.prep.references import ReferenceRules
from georep.settings import load_settings

NOWHERE = Path("/nonexistent")


@pytest.fixture(scope="module")
def lex() -> Lexicon:
    """Das Lexikon des Selbsttests: drei Orte, ein Ausschuss, die Bezirksvertretung, häufige Wörter."""
    rules = ReferenceRules.from_settings(load_settings(cwd=NOWHERE).procedures)
    return Lexicon(
        places=("kölner straße", "königsallee", "benrath"),
        bodies={"OVA": "ordnungs- und verkehrsausschuss"},
        district_code="BV",
        district_name="bezirksvertretung {n}",
        frequent=frozenset(
            {
                "die",
                "der",
                "das",
                "ein",
                "eine",
                "im",
                "bis",
                "vgl",
                "herr",
                "verweis",
                "sitzung",
                "varianten",
                "förderung",
                "verwaltung",
                "antrag",
                "fraktion",
                "spd",
                "bezirksvertretung",
                "euro",
                "radweg",
            }
        ),
        known=frozenset(),
        references=rules,
        codes=frozenset({"BV", "OVA", "RAT"}),
    )


TEXT = (
    "Dokumentart: Antrag SPD\nDrucksache: BV6/108/2023\nDatum: 15.06.2023\n"
    "Titel: Radweg Kölner Str.\n\n## Beschlussvorschlag\nDie Bezirksvertretung 6 beschließt, für "
    "1.500.000,00 € bis zum 31. Dezember 2024 einen Radweg in Benrath zu bauen. Vgl. Vorlage "
    "OVA/117/2023/1 und 61/ 12/2014. Sitzung um 17.30 Uhr; Herr Müller berichtet. 3 Varianten, "
    "12,5 % Förderung."
)


@pytest.mark.parametrize(
    ("summary", "supported"),
    [
        (
            "Die SPD beantragt in der BV 6 einen Radweg an der Kölner Straße für 1,5 Mio. Euro.",
            True,
        ),
        ("Bis zum 31.12.2024 soll der Radweg in Benrath gebaut werden (BV6/108/2023).", True),
        ("Der OVA hat am 15. Juni 2023 über drei Varianten mit 12,5 % Förderung beraten.", True),
        ("Verweis auf OVA/117/2023/1 und 61/12/2014; Sitzung um 17:30 Uhr.", True),
        ("Die Bezirksvertretung 6 beantragt 2 Mio. Euro.", False),  # Betrag nicht im Text
        ("Der Radweg soll bis zum 30.06.2025 fertig sein.", False),  # Datum nicht im Text
        ("Vgl. BV6/109/2023.", False),  # andere Drucksache
        ("Der Radweg führt über die Königsallee.", False),  # Ortsname nicht im Text
        ("Herr Schmitz berichtet.", False),  # Person nicht im Text
        ("Die Rheinbahn soll den Radweg planen.", False),  # Name nicht im Text
        ("Die CDU beantragt den Radweg.", False),  # Kürzel nicht im Text
        ("Herr Müller berichtet über den Radweg in Benrath.", True),
        ("Herr Müller berichtet über den Radweg im Süden von Benrath.", False),  # Süden fehlt
        ("Die BV 6 beschließt den Radweg.", True),
    ],
)
def test_the_fourteen_cases_of_the_self_test(summary: str, supported: bool, lex: Lexicon) -> None:
    found = claims(summary, evidence(TEXT, lex), lex)
    assert found, "jeder Fall trägt mindestens eine prüfbare Angabe"
    assert all(c.supported for c in found) is supported, found


def test_each_class_is_found_with_its_kind(lex: Lexicon) -> None:
    summary = (
        "Herr Müller nennt am 15.06.2023 um 17.30 Uhr drei Varianten für 1,5 Mio. Euro in "
        "Benrath (BV6/108/2023, OVA)."
    )
    kinds = {(c.cls, c.kind) for c in claims(summary, evidence(TEXT, lex), lex)}
    assert {
        ("name", "person"),
        ("datum", "datum"),
        ("zahl", "uhrzeit"),
        ("zahl", "zahlwort"),
        ("zahl", "zahl"),
        ("name", "ort"),
        ("drucksache", "drucksache"),
        ("name", "kuerzel"),
    } <= kinds
    assert {cls for cls, _ in kinds} <= set(CLASSES)


def test_a_derived_sum_stays_unsupported(lex: Lexicon) -> None:
    """Frage 20.12: eine selbst gerechnete Summe ist richtig, steht aber nicht im Text (Regel 3)."""
    text = "## Finanzen\nZwei Kredite über 100.000 € und 50.000 €."
    found = claims("Die Kredite betragen zusammen 150.000 €.", evidence(text, lex), lex)
    assert [c.text for c in found if not c.supported] == ["150.000"]


# --- Klasse e in Fassung 2 (Messdokument § 5.2) ------------------------------------------------


def test_an_abstract_noun_is_no_name(lex: Lexicon) -> None:
    """Fehlalarm der ersten Runde: ein Abstraktum aus Wörtern der Eingabe ist kein Eigenname."""
    found = claims("Die Verwaltung plant eine Neuordnung.", evidence(TEXT, lex), lex)
    assert [c for c in found if c.kind == "selten"] == []


def test_a_word_of_the_corpus_is_no_name(lex: Lexicon) -> None:
    known = replace(lex, known=frozenset({"spielplatz"}))
    found = claims("Ein Spielplatz soll entstehen.", evidence(TEXT, known), known)
    assert [c for c in found if not c.supported] == []


def test_a_compound_of_corpus_words_is_no_name(lex: Lexicon) -> None:
    known = replace(lex, known=frozenset({"radweg", "netz"}))
    assert decomposable("Radwegnetz", known.known)
    found = claims("Das Radwegnetz wächst.", evidence(TEXT, known), known)
    assert [c for c in found if not c.supported] == []


def test_a_hyphenated_word_counts_part_by_part(lex: Lexicon) -> None:
    known = replace(lex, known=frozenset({"konzept"}))
    ev = evidence(TEXT, known)
    assert [c for c in claims("Ein Radweg-Konzept liegt vor.", ev, known) if not c.supported] == []
    left = [c for c in claims("Ein Radweg-Rheinbahn liegt vor.", ev, known) if not c.supported]
    assert [(c.kind, c.text) for c in left] == [("selten", "Radweg-Rheinbahn")]


def test_a_name_outside_text_and_corpus_stays_flagged(lex: Lexicon) -> None:
    found = claims("Die Rheinbahn soll planen.", evidence(TEXT, lex), lex)
    assert [(c.cls, c.kind, c.text, c.supported) for c in found] == [
        ("name", "selten", "Rheinbahn", False)
    ]


def test_a_frequent_word_is_not_checked(lex: Lexicon) -> None:
    assert claims("Die Verwaltung berichtet.", evidence("", lex), lex) == []


# --- Frage 20.12: drei Fehlalarme der Umbaurunde ------------------------------------------------


def test_a_month_after_circa_counts_in_the_input(lex: Lexicon) -> None:
    """„ca." vor „Monat Jahr" löste den Ausschluss für „Tag. Monat Jahr" aus."""
    ev = evidence("Baubeginn ca. März 2022, Ende Mai 2023.", lex)
    found = claims("Der Bau beginnt im März 2022.", ev, lex)
    assert [(c.kind, c.supported) for c in found if c.cls == "datum"] == [("monat", True)]
    assert all(c.supported for c in found)


def test_a_month_glued_to_its_year_counts_in_the_input(lex: Lexicon) -> None:
    """pypdf klebt Monat und Jahr zusammen („Dezember2022")."""
    ev = evidence("Stand der Planung: Dezember2022", lex)
    found = claims("Die Planung hat den Stand vom Dezember 2022.", ev, lex)
    assert [(c.kind, c.supported) for c in found if c.cls == "datum"] == [("monat", True)]
    assert all(c.supported for c in found)


@pytest.mark.parametrize(
    ("text", "summary"),
    [
        ("Das Votum des Beirats liegt vor.", "Die Voten liegen vor."),
        ("Die Voten der Beiräte liegen vor.", "Das Votum liegt vor."),
        ("Die Themen der Sitzung.", "Ein Thema der Sitzung."),
        ("Die Gremien beraten.", "Ein Gremium berät."),
    ],
)
def test_an_irregular_plural_of_an_input_word_is_covered(
    text: str, summary: str, lex: Lexicon
) -> None:
    """Unregelmäßige Plurale fielen durch die Endungsliste (Votum, Voten)."""
    found = claims(summary, evidence(text, lex), lex)
    assert [c for c in found if not c.supported] == []


# --- Ergebnis je Kurzfassung ---------------------------------------------------------------------


def test_an_empty_or_truncated_summary_never_passes(lex: Lexicon) -> None:
    ev = evidence(TEXT, lex)
    assert not check(None, False, ev, lex).ok
    assert not check("  ", False, ev, lex).ok
    assert not check("Die BV 6 beschließt den Radweg.", True, ev, lex).ok
    assert check("Die BV 6 beschließt den Radweg.", False, ev, lex).ok


def test_the_row_counts_unsupported_claims_per_class(lex: Lexicon) -> None:
    result = check(
        "Herr Schmitz will 2 Mio. Euro bis zum 30.06.2025.", False, evidence(TEXT, lex), lex
    )
    row = fidelity_row(result)
    assert row["angaben"] == len(result.claims) == 3
    assert (row["unbelegt_zahl"], row["unbelegt_datum"], row["unbelegt_name"]) == (1, 1, 1)
    assert row["unbelegt_drucksache"] == 0
    assert row["ok"] is False


def test_a_claim_is_a_plain_value() -> None:
    claim = Claim("zahl", "zahl", "12", True)
    assert (claim.cls, claim.kind, claim.text, claim.supported) == ("zahl", "zahl", "12", True)


def test_a_hyphen_at_line_end_before_a_capital_stays(lex: Lexicon) -> None:
    """„Lindenhof-\\nStraße" ist ein Bindestrich, „Planungs-\\nweg" eine Silbentrennung (wie § 3.1)."""
    places = replace(lex, places=("lindenhof-straße", "planungsweg"))
    ev = evidence("Ausbau der Lindenhof-\nStraße und am Planungs-\nweg.", places)
    found = claims("Die Lindenhof-Straße und der Planungsweg werden ausgebaut.", ev, places)
    assert [(c.kind, c.supported) for c in found if c.kind == "ort"] == [
        ("ort", True),
        ("ort", True),
    ]
