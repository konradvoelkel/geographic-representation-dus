"""Die Funktion je Ratsdokument (Vorhaben 15), Regel für Regel an Beispielen aus dem Messdokument.

Die Regeln sind die des Stadtprofils, wie ``georep run`` sie liest; jedes Beispiel steht im
Messdokument ``docs/plans/15-funktion.md`` (§ 3.1, § 3.4) oder in seiner Validierung (§ 4.1).
Texte liegen wie im Korpus kleingeschrieben und ohne Zeilenumbrüche vor.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep.analysis.functions import (
    FUNCTIONS_SCHEMA,
    DocumentFunction,
    FunctionRules,
    classify_function,
    classify_functions,
    function_figures,
    is_consistent,
)
from georep.settings import FUNCTION_CLASSES, Settings, load_settings

NOWHERE = Path("/nonexistent")
HEAD_2014 = "vorlage 173/ 85/2014 seite 1 von 2 rsd vorlage x öffentlich nicht öffentlich  "


@pytest.fixture(scope="module")
def city() -> Settings:
    return load_settings(cwd=NOWHERE)


@pytest.fixture(scope="module")
def rules_b(city: Settings) -> FunctionRules:
    return FunctionRules.from_settings(city.functions)


@pytest.fixture(scope="module")
def rules_a(city: Settings) -> FunctionRules:
    return FunctionRules.from_settings(city.functions.model_copy(update={"variant": "A"}))


def _f(funktion: str, instrument: str, quelle: str) -> DocumentFunction:
    return DocumentFunction(funktion, instrument, quelle)


# --- 1. Dokumentart als ganzer Wert und über ihr Präfix ----------------------------------------
@pytest.mark.parametrize(
    ("paper_type", "name", "expected"),
    [
        ("Beschlussvorlage", "Neubau einer Grundschule", _f("vollzug", "beschlussvorlage", "art")),
        ("Beschlussvorlage", "Bebauungsplan Nr. 01/002", _f("vollzug", "bauleitplanung", "art")),
        ("Beschlussvorlage", "Haushaltssatzung 2024", _f("vollzug", "haushalt", "art")),
        ("Beschlussvorlage RPA", "Prüfbericht", _f("vollzug", "rechnungspruefung", "art")),
        ("A+F Beschluss", "Sanierung Turnhalle", _f("vollzug", "bau", "art")),
        (
            "Informationsvorlage",
            "Sachstand Radwege",
            _f("information", "informationsvorlage", "art"),
        ),
        ("Berichtsvorlage", "Jahresbericht", _f("information", "berichtsvorlage", "art")),
        ("Eingabe nach 24 GO", "Bericht zur Parkplatzlage", _f("initiative", "eingabe", "art")),
        (
            "Anfrage SPD",
            "Anfrage der SPD-Ratsfraktion: Kitaplätze",
            _f("kontrolle", "anfrage", "art"),
        ),
        ("Anfrage CDU", "Nachfrage zur Anfrage vom 3. März", _f("kontrolle", "nachfrage", "art")),
        ("Antrag CDU/Grüne", "Mehr Bäume im Süden", _f("initiative", "antrag", "art")),
        ("Haushaltsantrag Die Linke", "Sozialticket", _f("initiative", "haushaltsantrag", "art")),
        (
            "Antrag",
            "Änderungsantrag der FDP zum Radweg",
            _f("initiative", "aenderungsantrag", "art"),
        ),
        ("Antrag", "Prüfauftrag Tempo 30", _f("initiative", "pruefauftrag", "art")),
        ("Neue Dokumentart", "irgendwas", _f("rest", "art_unbekannt", "")),
    ],
)
def test_the_type_decides_first(
    paper_type: str, name: str, expected: DocumentFunction, rules_a: FunctionRules
) -> None:
    assert classify_function(paper_type, name, "", "Fraktion", rules_a) == expected


# --- 2. Die Sammelarten der Periode 2014 bis 2020 ---------------------------------------------
def test_a_request_about_a_resolution_is_control(rules_b: FunctionRules) -> None:
    found = classify_function(
        "Vorlage aus der Politik", "Anfrage zur Resolution Seebrücke", "", "Fraktion", rules_b
    )
    assert found == _f("kontrolle", "anfrage", "titel")


def test_the_title_word_decides_a_political_collection(rules_a: FunctionRules) -> None:
    def political(name: str) -> DocumentFunction:
        return classify_function("Vorlage aus der Politik", name, "", "Fraktion", rules_a)

    assert political("Rückfrage zum Spielplatz") == _f("kontrolle", "nachfrage", "titel")
    assert political("Resolution gegen Fremdenfeindlichkeit") == _f("symbol", "resolution", "titel")
    assert political("Antrag: Tempo 30") == _f("initiative", "antrag", "titel")
    assert political("Spielplatz") == _f("rest", "sammelart_ohne_merkmal", "")


def test_the_first_instrument_word_behind_the_letterhead_decides_otherwise(
    rules_a: FunctionRules,
) -> None:
    text = (
        HEAD_2014 + "fraktion die linke der bezirksvertretung 3 11.09.2014  antrag quartier rund um"
    )
    found = classify_function("Vorlage aus der Politik", "Quartier Bilk", text, "Fraktion", rules_a)
    assert found == _f("initiative", "antrag", "text")


def test_a_building_request_is_no_instrument_of_the_body(rules_a: FunctionRules) -> None:
    text = HEAD_2014 + "betrifft bauvoranfrage für das grundstück, dazu die anfrage der fraktion"
    found = classify_function("Vorlage aus der Politik", "Grundstück", text, "Fraktion", rules_a)
    assert found == _f(
        "kontrolle", "anfrage", "text"
    )  # das erste Wort ist keines, das zweite schon


def test_an_administrative_collection_reads_notice_against_decision(rules_a: FunctionRules) -> None:
    def admin(name: str, text: str) -> DocumentFunction:
        return classify_function("Verwaltungsvorlage", name, text, "Verwaltung", rules_a)

    assert admin("Radwege", "die verwaltung teilt mit, dass") == _f(
        "information", "informationsvorlage", "text"
    )
    assert admin("Radwege", "der rat beschließt die satzung") == _f(
        "vollzug", "beschlussvorlage", "text"
    )
    assert admin("Satzung über Gebühren", "der ausschuss empfiehlt") == _f(
        "vollzug", "satzung", "text"
    )
    assert admin("Mitteilung zur Baustelle", "anlage 1") == _f(
        "information", "informationsvorlage", "titel"
    )
    assert admin("Vergabe Reinigung", "anlage 1") == _f("vollzug", "beschlussvorlage", "titel")
    assert admin("Grünanlage", "anlage 1 " + "x" * 800 + " zur kenntnis") == _f(
        "information", "informationsvorlage", "text"
    )  # der zweite, weitere Blick
    assert admin("Grünanlage", "anlage 1") == _f("rest", "sammelart_ohne_merkmal", "")


def test_the_letterhead_of_politics_makes_an_administrative_collection_political(
    rules_a: FunctionRules,
) -> None:
    text = (
        HEAD_2014 + "spd - fraktion  der bezirksvertretung 8  an den bezirksbürgermeister  antrag"
    )
    found = classify_function("Verwaltungsvorlage", "Spielplatz", text, "Verwaltung", rules_a)
    assert found == _f("initiative", "antrag", "text")


def test_a_political_originator_makes_an_administrative_collection_political(
    rules_a: FunctionRules,
) -> None:
    """47 Anträge jener Periode liegen unter „Verwaltungsvorlage" (Punkt 62)."""
    found = classify_function("Verwaltungsvorlage", "Antrag: Spielplatz", "", "Fraktion", rules_a)
    assert found == _f("initiative", "antrag", "titel")


# --- 3. Symbolpolitik aus dem Titel, nur aus der Politik ---------------------------------------
def test_a_resolution_motion_is_symbolic(rules_a: FunctionRules) -> None:
    found = classify_function(
        "Antrag", "Resolution zum russischen Angriff auf die Ukraine", "", "Fraktion", rules_a
    )
    assert found == _f("symbol", "resolution", "titel")


def test_an_information_about_a_resolution_stays_information(rules_a: FunctionRules) -> None:
    """RAT/374/2021: die Verwaltung berichtet über eine Resolution."""
    name = "Resolution zur Stärkung der Kommunalfinanzen"
    found = classify_function("Informationsvorlage", name, "", "Verwaltung", rules_a)
    assert found == _f("information", "informationsvorlage", "art")


def test_a_petition_is_never_symbolic(rules_b: FunctionRules) -> None:
    found = classify_function(
        "Eingabe nach 24 GO", "Resolution für den Frieden", "", "Eingabe", rules_b
    )
    assert found == _f("initiative", "eingabe", "art")


# --- 4. Variante B ----------------------------------------------------------------------------
def test_variant_b_reads_a_declaration_in_the_resolution_text(
    rules_a: FunctionRules, rules_b: FunctionRules
) -> None:
    text = "beschlussvorschlag: der rat verurteilt die lieferung von panzern"
    args = ("Antrag", "Keine Panzer für die Türkei", text, "Fraktion")
    assert classify_function(*args, rules_a) == _f("initiative", "antrag", "art")
    assert classify_function(*args, rules_b) == _f("symbol", "erklaerung_text", "text")


def test_variant_b_counts_a_report_motion_as_control(
    rules_a: FunctionRules, rules_b: FunctionRules
) -> None:
    args = ("Antrag CDU", "Sachstand Schulbau", "", "Fraktion")
    assert classify_function(*args, rules_a) == _f("initiative", "berichtsantrag", "art")
    assert classify_function(*args, rules_b) == _f("kontrolle", "berichtsantrag", "art")
    text = "die verwaltung wird gebeten, im nächsten ausschuss zu berichten"
    found = classify_function("Antrag SPD", "Schulbau", text, "Fraktion", rules_b)
    assert found == _f("kontrolle", "berichtsantrag", "text")


def test_variant_b_leaves_the_administration_alone(rules_b: FunctionRules) -> None:
    text = "der rat fordert die landesregierung auf"
    found = classify_function("Beschlussvorlage", "Kita", text, "Verwaltung", rules_b)
    assert found.funktion == "vollzug"


# --- Mönchengladbach: alle 16 Arten über die Tabelle --------------------------------------------
def test_every_type_of_the_second_city_goes_through_the_table() -> None:
    settings = load_settings(profile="moenchengladbach", cwd=NOWHERE)
    rules = FunctionRules.from_settings(settings.functions)
    types = (
        *settings.originators.admin_types,
        *settings.originators.fraction_types,
        *settings.originators.person_types,
    )
    assert len(types) == 16
    found = {t: classify_function(t, "Spielplatz", "", None, rules) for t in types}
    assert {f.quelle for f in found.values()} == {"art"}
    assert {f.funktion for f in found.values()} == {"vollzug", "information", "initiative"}
    motion = classify_function(
        "3 - Fraktionsantrag", "Resolution: Gegen jeden Antisemitismus", "", "Fraktion", rules
    )
    assert motion == _f("symbol", "resolution", "titel")


# --- die Tabelle je Korpus-ID ---------------------------------------------------------------------
def test_the_frame_has_one_row_per_corpus_id_and_unknown_originators_count_as_unknown(
    rules_b: FunctionRules,
) -> None:
    corpus = pl.DataFrame(
        {
            "id": ["c", "a", "b"],
            "paper_type": ["Anfrage SPD", "Beschlussvorlage", "Antrag"],
            "name": ["Kitas", "Schule", "Resolution für Europa"],
            "text": ["", "", None],
        }
    )
    originators = pl.DataFrame({"id": ["a", "c"], "urheber_art": ["Verwaltung", "Fraktion"]})
    frame = classify_functions(corpus, originators, rules_b)
    assert frame.schema == pl.Schema(FUNCTIONS_SCHEMA)
    assert frame.get_column("id").to_list() == ["a", "b", "c"]
    assert frame.get_column("funktion").to_list() == ["vollzug", "symbol", "kontrolle"]
    assert set(frame.get_column("variante").to_list()) == {"B"}
    assert function_figures(frame) == dict.fromkeys(FUNCTION_CLASSES, 0) | {
        "vollzug": 1,
        "symbol": 1,
        "kontrolle": 1,
    }


def test_consistency_names_the_three_conditions() -> None:
    assert is_consistent(_f("vollzug", "satzung", "art"))
    assert not is_consistent(_f("vollzug", "anfrage", "art"))  # fremdes Instrument
    assert not is_consistent(_f("rest", "art_unbekannt", "art"))  # Rest mit Quelle
    assert not is_consistent(_f("kontrolle", "anfrage", ""))  # Funktion ohne Quelle
