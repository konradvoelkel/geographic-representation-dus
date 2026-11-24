"""Vorhaben 11: Abschnitte und Kopf aus synthetischen Ratsdokumenten (``prep.structure``).

Die Texte folgen dem Katalog im Messdokument (``docs/plans/11-struktur.md``, § 3.1): ein
Formularkopf, ein Brief mit „Antrag:", einer mit Einleitungssatz, einer mit Beschlusssatz, eine
Informationsvorlage mit zitiertem Beschluss, ein Ausführungsbeschluss mit Kosten im Beschluss und
das Formular der zweiten Stadt. Keine echten Dokumente und keine echten Namen in den Tests.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import ANY

import polars as pl
import pytest

from georep.prep.structure import (
    HEAD_SCHEMA,
    BodyNames,
    StructureRules,
    analyse,
    consultation_agreement,
    head_row,
    name_key,
    office_directory,
    structure_tables,
)
from georep.settings import Settings, load_settings
from georep.spans import SPAN_SCHEMA, section_of

NOWHERE = Path("/nonexistent")
PERSON = "Erika Beispiel"  # ein erfundener Name; er darf in keiner Ausgabe stehen


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(profile="duesseldorf", cwd=NOWHERE)


@pytest.fixture(scope="module")
def rules(settings: Settings) -> StructureRules:
    return StructureRules.from_settings(settings)


@pytest.fixture(scope="module")
def names(settings: Settings) -> BodyNames:
    return BodyNames.from_settings(settings)


FORM = f"""X öffentlich nicht öffentlich
Beschlussvorlage

Betrifft: Neubau eines Radwegs am Kanal

Fachbereich: 66 - Amt für Verkehrsmanagement
Dezernentin / Dezernent: Beigeordneter {PERSON}
Beratungsfolge:
Gremium Sitzungsdatum Beratungsqualität
Ordnungs- und Verkehrsausschuss 18.10.2023 Vorberatung
Rat 09.11.2023 Entscheidung

Beschlussdarstellung:
Der Rat beschließt den Neubau des Radwegs.

Sachdarstellung:
Der Radweg schließt eine Lücke.\fSeite 2
Die Kosten trägt das Land.
"""


def _texts(structure_text: str, found: list[tuple[int, int, str]]) -> dict[str, str]:
    return {kind: structure_text[start:end] for start, end, kind in found}


def test_a_form_head_gives_sections_and_head_fields(
    rules: StructureRules, names: BodyNames
) -> None:
    found = analyse(FORM, rules, "Beschlussvorlage")
    sections = _texts(FORM, [(s.start, s.end, s.norm) for s in found.sections])
    assert sections["betreff"] == "Neubau eines Radwegs am Kanal"
    assert sections["beschlussvorschlag"] == "Der Rat beschließt den Neubau des Radwegs."
    assert sections["sachdarstellung"].startswith("Der Radweg schließt")
    assert sections["kopf_amt"] == "66 - Amt für Verkehrsmanagement"
    assert found.sources["beschlussvorschlag"] == "ueberschrift"
    row = head_row(found, rules, names)
    assert row["formular"] == "Beschlussvorlage"
    assert (row["amt_nr"], row["amt_name"]) == ("66", "Amt für Verkehrsmanagement")
    assert row["dezernat_titel"] == "Beigeordneter"
    assert row["beratungsfolge"] == [
        {
            "gremium": "Ordnungs- und Verkehrsausschuss",
            "gremium_kuerzel": "OVA",
            "datum": date(2023, 10, 18),
            "qualitaet": "Vorberatung",
        },
        {
            "gremium": "Rat",
            "gremium_kuerzel": "RAT",
            "datum": date(2023, 11, 9),
            "qualitaet": "Entscheidung",
        },
    ]
    assert row["beschlussvorschlag"] is True
    assert row["rumpf_leer"] is False


def test_the_title_span_ends_before_the_name(rules: StructureRules) -> None:
    """Vom Feld „Dezernentin / Dezernent" deckt die Spanne nur die Amtsbezeichnung."""
    found = analyse(FORM, rules, "Beschlussvorlage")
    title = next(f for f in found.head if f.kind == "dezernat")
    assert FORM[title.start : title.end] == "Beigeordneter"
    for span in (*found.head, *found.sections):
        assert PERSON not in span.value and PERSON not in span.norm


def letter(
    city: str, body: str, head: str = "Antrag zur Sitzung des Rates am 24. Juni 2025"
) -> str:
    return f"""Fraktion im Rat
{city}, 12.03.2025
An den Oberbürgermeister
{head}

Betrifft: Mehr Bäume an Schulen

Sehr geehrter Herr Oberbürgermeister,
{body}
Mit freundlichen Grüßen
{PERSON}
Fraktionsvorsitzende
"""


def test_a_letter_with_a_motion_heading(
    settings: Settings, rules: StructureRules, names: BodyNames
) -> None:
    text = letter(
        settings.city.name,
        "wir bitten Sie, den folgenden Antrag zur Abstimmung zu stellen.\n\nAntrag:\n"
        "Die Verwaltung wird beauftragt, an jeder Schule zehn Bäume zu pflanzen.\n\n"
        "Begründung:\nSchatten hilft.\n",
    )
    found = analyse(text, rules, "Antrag SPD")
    sections = _texts(text, [(s.start, s.end, s.norm) for s in found.sections])
    assert sections["beschlussvorschlag"].startswith("Die Verwaltung wird beauftragt")
    assert sections["begruendung"] == "Schatten hilft."
    assert sections["rumpf"].startswith("Sehr geehrter Herr Oberbürgermeister")
    row = head_row(found, rules, names)
    assert row["briefdatum"] == date(2025, 3, 12)
    assert (row["sitzung_gremium"], row["sitzung_kuerzel"]) == ("Rat", "RAT")
    assert row["sitzung_datum"] == date(2025, 6, 24)
    assert row["unterzeichner_rolle"] == "Fraktionsvorsitzende"
    assert row["amt_nr"] is None and row["beratungsfolge"] == []


def test_a_letter_with_an_introductory_sentence(settings: Settings, rules: StructureRules) -> None:
    text = letter(
        settings.city.name,
        "wir bitten Sie, folgenden Beschluss zu fassen und zur Abstimmung zu stellen:\n"
        "Der Rat fordert mehr Bäume.\n\n",
    )
    found = analyse(text, rules, "Antrag Fraktion")
    decision = next(s for s in found.sections if s.norm == "beschlussvorschlag")
    assert text[decision.start : decision.end] == "Der Rat fordert mehr Bäume."
    assert found.sources["beschlussvorschlag"] == "einleitung"


def test_a_decision_sentence_without_a_heading(settings: Settings, rules: StructureRules) -> None:
    """Der Beschlusssatz gehört selbst zum Abschnitt; nur in Arten mit erwartetem Vorschlag."""
    text = (
        "Betrifft: Ampel an der Schule\n\n"
        "Die Bezirksvertretung 5 bittet die Verwaltung, eine Ampel aufzustellen.\n\n"
        "Begründung:\nDer Weg ist gefährlich.\n"
    )
    found = analyse(text, rules, "Antrag Fraktion")
    decision = next(s for s in found.sections if s.norm == "beschlussvorschlag")
    assert text[decision.start : decision.end].startswith("Die Bezirksvertretung 5 bittet")
    assert found.sources["beschlussvorschlag"] == "beschlusssatz"
    assert not any(s.norm == "beschlussvorschlag" for s in analyse(text, rules, "Anfrage").sections)


INFORMATION = """Betrifft: Spielplatz im Park

Amt / Institut: Bezirksverwaltungsstelle 8
Beratungsfolge:
Gremium Sitzungsdatum Beratungsqualität
Bezirksvertretung 8 12.05.2022 Kenntnisnahme
Die Bezirksvertretung 8 fasste in ihrer Sitzung folgenden Beschluss:
Beschluss:
Die Verwaltung wird gebeten, zu prüfen und dann zu beschließen:
Der Spielplatz wird erneuert.
"""


def test_text_under_the_consultations_is_body_and_a_cited_decision_proposes_nothing(
    rules: StructureRules, names: BodyNames
) -> None:
    found = analyse(INFORMATION, rules, "Bezirksvertretung Informationsvorlage")
    sections = _texts(INFORMATION, [(s.start, s.end, s.norm) for s in found.sections])
    assert sections["kopf_beratungsfolge"].endswith("Bezirksvertretung 8 12.05.2022 Kenntnisnahme")
    assert (
        sections["rumpf"] == "Die Bezirksvertretung 8 fasste in ihrer Sitzung folgenden Beschluss:"
    )
    assert "beschlussvorschlag" not in sections  # lead_blocked_in: der zitierte Beschluss
    row = head_row(found, rules, names)
    assert (row["amt_nr"], row["amt_name"]) == (None, "Bezirksverwaltungsstelle 8")
    assert row["beratungsfolge"] == [
        {"gremium": ANY, "gremium_kuerzel": "BV8", "datum": ANY, "qualitaet": ANY}
    ]


EXECUTION = """Betrifft: Sanierung der Turnhalle

Fachbereich: 65 - Amt für Gebäudemanagement
Beschlussdarstellung:
Der Ausschuss beschließt die Sanierung.
Kosten: 1.200.000 EUR
Gesamtkosten: 1.500.000 EUR
Sachdarstellung:
Die Halle ist alt.
"""


def test_costs_inside_the_decision_are_level_two(rules: StructureRules) -> None:
    """Finanzen öffnen eine eigene Spanne, ohne den Beschlussvorschlag zu schließen; ihr
    ``section`` ist der Abschnitt der Ebene 1 um sie herum."""
    found = analyse(EXECUTION, rules, "A+F Beschluss")
    decision = next(s for s in found.sections if s.norm == "beschlussvorschlag")
    assert EXECUTION[decision.start : decision.end].endswith("Gesamtkosten: 1.500.000 EUR")
    costs = [s for s in found.sections if s.norm == "finanzen"]
    assert costs and all(s.section == "beschlussvorschlag" for s in costs)
    level1 = [s for s in found.sections if s.norm == s.section]
    for before, after in zip(level1, level1[1:], strict=False):
        assert before.end <= after.start


def test_the_form_of_the_second_city() -> None:
    settings = load_settings(profile="moenchengladbach", cwd=NOWHERE)
    rules = StructureRules.from_settings(settings)
    text = (
        "Beratungsvorlage Nr. 1234/X\nTOP: Neuer Spielplatz\n"
        "Fachbereich  FB 50 Soziales\nBeratungsfolge\nGremium Sitzungsdatum\nRat 01.02.2024\n"
        "Beschlussentwurf:\nDer Rat beschließt den Spielplatz.\n"
        "Finanzwirksamkeit:\nKeine.\nBegründung:\nKinder spielen gern.\n"
    )
    found = analyse(text, rules, "Beratungsvorlage")
    sections = _texts(text, [(s.start, s.end, s.norm) for s in found.sections])
    assert sections["betreff"] == "Neuer Spielplatz"
    assert sections["beschlussvorschlag"] == "Der Rat beschließt den Spielplatz."
    assert sections["finanzen"] == "Keine."
    row = head_row(found, rules, BodyNames.from_settings(settings))
    assert row["amt_name"] == "FB 50 Soziales"
    assert row["beratungsfolge"] == [
        {"gremium": ANY, "gremium_kuerzel": "RAT", "datum": ANY, "qualitaet": ANY}
    ]


def test_an_empty_text_has_an_empty_body(rules: StructureRules, names: BodyNames) -> None:
    found = analyse("", rules, "Antrag")
    assert found.sections == [] and found.head == []
    assert head_row(found, rules, names)["rumpf_leer"] is True


# --- Gremiennamen über [bodies] (Messdokument § 10, Punkt 6) ---------------------------------------


@pytest.mark.parametrize(
    ("written", "code"),
    [
        ("Rates", "RAT"),
        ("Stadtrates", "RAT"),  # [city].council
        ("Ordnungs- und Verkehrsausschusses", "OVA"),
        ("ordnungs-und Verkehrsausschuss", "OVA"),
        ("Bezirksvertretung10", "BV10"),
        ("Bezirksvertretung 05", "BV5"),
        ("BV3", "BV3"),
        ("AÖE", "AÖE"),
        ("Ausschuss für Mobilität", None),
        ("Bezirksvertretung", None),
    ],
)
def test_a_written_body_finds_its_code(names: BodyNames, written: str, code: str | None) -> None:
    assert names.code(written) == code


def test_the_session_is_named_in_the_nominative(
    settings: Settings, rules: StructureRules, names: BodyNames
) -> None:
    head = f"Antrag zur Sitzung des Rates der Landeshauptstadt {settings.city.name} am 03.02.2022"
    found = analyse(letter(settings.city.name, "Text.\n", head=head), rules, "Antrag")
    row = head_row(found, rules, names)
    assert (row["sitzung_gremium"], row["sitzung_kuerzel"]) == ("Rat", "RAT")
    head = "Anfrage zur Sitzung des AÖE am 07.11.2024"
    row = head_row(
        analyse(letter(settings.city.name, "Text.\n", head=head), rules, "Anfrage"), rules, names
    )
    assert row["sitzung_kuerzel"] == "AÖE"
    assert row["sitzung_gremium"] == settings.bodies.committees["AÖE"]


def test_the_key_ignores_case_punctuation_and_the_genitive() -> None:
    assert name_key("Ausschusses für Umwelt-, Klima- und Verbraucherschutz") == name_key(
        "Ausschuss für Umwelt-, Klima- und Verbraucherschutz"
    )
    assert name_key("Rates") == name_key("Rat") != name_key("Rathaus")


# --- Batch: je Korpus-ID eine Zeile, Spannen nach F3 -------------------------------------------------


def test_every_corpus_id_gets_its_row_also_when_ids_share_a_file(
    rules: StructureRules, names: BodyNames
) -> None:
    documents = pl.DataFrame(
        {
            "id": ["c", "a", "b"],
            "paper_type": ["Beschlussvorlage", "Beschlussvorlage", "Anfrage"],
            "text": [FORM, FORM, None],
            "extractor": ["pypdf-7.1.0+roh", "pypdf-7.1.0+roh", None],
        }
    )
    spans, head = structure_tables(documents, rules, names)
    assert head.get_column("id").to_list() == ["a", "b", "c"]
    assert list(head.schema.items()) == list(HEAD_SCHEMA.items())
    assert list(spans.schema) == list(SPAN_SCHEMA)
    # zwei IDs mit derselben Datei: dieselben Spannen, je mit ihrer ID
    a = spans.filter(pl.col("id") == "a").drop("id")
    assert a.height and a.equals(spans.filter(pl.col("id") == "c").drop("id"))
    assert spans.filter(pl.col("id") == "b").height == 0
    empty = head.filter(pl.col("id") == "b").row(0, named=True)
    assert all(value is None for key, value in empty.items() if key != "id")
    assert set(spans.get_column("extractor").to_list()) == {"struktur-1/pypdf-7.1.0+roh"}


def test_the_sections_answer_section_of(rules: StructureRules, names: BodyNames) -> None:
    """Eine Spanne eines anderen Vorhabens im Beschlussvorschlag bekommt diesen Abschnitt."""
    documents = pl.DataFrame(
        {"id": ["a"], "paper_type": ["Beschlussvorlage"], "text": [FORM], "extractor": ["x"]}
    )
    spans, _ = structure_tables(documents, rules, names)
    at = FORM.index("Neubau des Radwegs")
    probe = pl.DataFrame(
        [("a", at, at + 6, "probe", "Neubau", "", "", "x")], schema=SPAN_SCHEMA, orient="row"
    )
    assert section_of(probe, spans).get_column("section").to_list() == ["beschlussvorschlag"]


def test_the_head_rows_agree_with_the_consultations_of_the_server(
    settings: Settings, rules: StructureRules, names: BodyNames
) -> None:
    documents = pl.DataFrame(
        {"id": ["a"], "paper_type": ["Beschlussvorlage"], "text": [FORM], "extractor": ["x"]}
    )
    _, head = structure_tables(documents, rules, names)
    consultations = pl.DataFrame(
        {"id": ["a"], "consultation_organizations": [["https://server/organizations/gr/6"]]}
    )
    # RAT steht in der Folge des Servers, OVA (gr/25) nicht: eine von zwei Zeilen
    assert consultation_agreement(head, consultations, settings.bodies.organizations) == (1, 2)


def test_the_office_directory_takes_the_most_frequent_name() -> None:
    head = pl.DataFrame(
        {
            "amt_nr": ["52", "52", "52", None, "66"],
            "amt_name": ["Sportamt", "Sportamt", "Sport-Amt", "Bezirksverwaltungsstelle 1", "Amt"],
        }
    )
    assert office_directory(head).rows() == [("52", "Sportamt", 3), ("66", "Amt", 1)]
