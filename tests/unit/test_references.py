"""Drucksachennummern finden und normalisieren (Vorhaben 14, ``georep.prep.references``).

Die Formen stehen im Stadtprofil; die Tests lesen sie von dort, damit sie prüfen, was die Kette
rechnet, und nicht eine Kopie der Muster. Die Beispiele stammen aus dem Messdokument
(``docs/plans/14-vorgaenge.md``, § 3.1 und § 3.9).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from georep.prep.references import (
    EDGE_TYPES,
    Reference,
    ReferenceRules,
    edge_type,
    find_hits,
    has_amendment_marker,
    is_answer_attachment,
    is_collective,
    known_codes,
    parse_reference,
    role_of,
)
from georep.settings import Procedures, ReferenceForm, load_settings

NOWHERE = Path("/nonexistent")


@pytest.fixture(scope="module")
def dus() -> ReferenceRules:
    return ReferenceRules.from_settings(load_settings(cwd=NOWHERE).procedures)


@pytest.fixture(scope="module")
def mg() -> ReferenceRules:
    settings = load_settings(profile="moenchengladbach", cwd=NOWHERE)
    return ReferenceRules.from_settings(settings.procedures)


CODES = frozenset({"BV", "OVA", "RAT", "KUA", "AUS", "AGS"})


@pytest.mark.parametrize(
    ("number", "key", "base"),
    [
        ("BV6/108/2023", "BV6/108/2023", "BV6/108/2023"),
        ("BV06/008/2023", "BV6/8/2023", "BV6/8/2023"),  # führende Nullen fallen
        ("OVA/117/2023/1", "OVA/117/2023/1", "OVA/117/2023"),  # Nachtrag als /k
        ("OVA/117/2023 - 1", "OVA/117/2023/1", "OVA/117/2023"),
        (" AGS/072/2020 ", "AGS/72/2020", "AGS/72/2020"),
        ("61/ 12/2014", "61/12/2014", "61/12/2014"),  # alte Form, Punkt 57
        ("001/ 40/2015 - 1", "001/40/2015/1", "001/40/2015"),  # der Kopf bleibt, wie er ist
    ],
)
def test_own_numbers_of_the_city_become_keys(
    dus: ReferenceRules, number: str, key: str, base: str
) -> None:
    found = parse_reference(number, dus)
    assert found is not None
    assert (found.key, found.base) == (key, base)
    assert found.is_supplement == (key != base)


@pytest.mark.parametrize(
    ("number", "key"),
    [
        ("0302/X", "0302/X"),
        ("302/X", "0302/X"),  # die laufende Nummer vierstellig
        ("0302-1/X", "0302/X/1"),  # Nachtrag vor der Periode
        ("0302/X-1", "0302/X/1"),  # und hinter ihr
        ("1293/XI", "1293/XI"),
    ],
)
def test_numbers_of_the_second_city_become_keys(mg: ReferenceRules, number: str, key: str) -> None:
    found = parse_reference(number, mg)
    assert found is not None and found.key == key


@pytest.mark.parametrize("number", [None, "", "XYZ", "Vorlage 61/12/2014", "0302/X"])
def test_what_no_form_covers_has_no_key(dus: ReferenceRules, number: str | None) -> None:
    assert parse_reference(number, dus) is None


def test_codes_are_learned_from_the_numbers(dus: ReferenceRules) -> None:
    found = [parse_reference(n, dus) for n in ("BV6/1/2023", "OVA/2/2023/1", "61/3/2014", None)]
    assert known_codes(found) == {"BV", "OVA"}


def _keys(text: str, rules: ReferenceRules, codes: frozenset[str] = CODES) -> list[str]:
    return [hit.reference.key for hit in find_hits(text, rules, codes)]


def test_a_glued_code_is_cut_to_the_longest_known_one(dus: ReferenceRules) -> None:
    text = "beschluss zur vorlagebv6/002/2023 vom"
    (hit,) = find_hits(text, dus, CODES)
    assert hit.reference.key == "BV6/2/2023"
    assert text[hit.start : hit.end] == "bv6/002/2023"


def test_the_position_does_not_slip_on_a_sharp_s(dus: ReferenceRules) -> None:
    """``ß`` wird groß zu ``SS``; die Lage im Text bleibt die des Originals."""
    text = "großbv6/002/2023"
    (hit,) = find_hits(text, dus, CODES)
    assert text[hit.start : hit.end] == "bv6/002/2023"


def test_a_word_before_the_old_form_is_no_code(dus: ReferenceRules) -> None:
    """„vorlage 61/ 12/2014": ohne diese Regel standen 6 801 Scheintreffer „ORLAGE" da (§ 3.1)."""
    assert _keys("siehe vorlage 61/ 12/2014 und drucksache 01/ 5/2016", dus) == [
        "61/12/2014",
        "01/5/2016",
    ]


def test_an_unknown_short_code_stays_and_a_long_word_does_not(dus: ReferenceRules) -> None:
    assert _keys("xyz/1/2020", dus) == ["XYZ/1/2020"]
    assert _keys("verwaltung/1/2020", dus) == []


def test_spaces_around_the_slashes_and_a_supplement_in_the_text(dus: ReferenceRules) -> None:
    assert _keys("antrag ova / 117 / 2023 / 1 im rat", dus) == ["OVA/117/2023/1"]


def test_a_date_shaped_old_number_is_found(dus: ReferenceRules) -> None:
    """Zehn bekannte Treffer haben diese Form (§ 3.1); ob er eine Drucksache meint, sagt das
    Verzeichnis, nicht das Muster."""
    assert _keys("am 01/12/2014", dus) == ["01/12/2014"]


def test_the_second_city_reads_its_own_form(mg: ReferenceRules) -> None:
    assert _keys("zu vorlage 0265/x und 265-1/x", mg, frozenset()) == ["0265/X", "0265/X/1"]


def test_a_development_plan_number_is_found_too(mg: ReferenceRules) -> None:
    """Bebauungspläne heißen ähnlich („Nr. 437/V"); kein bekannter Treffer stand dahinter, und
    eine Nummer muss existieren, um eine Kante zu werden (§ 3.1). Gefiltert wird nicht."""
    assert _keys("bebauungsplan nr. 437/v", mg, frozenset()) == ["0437/V"]


def test_every_hit_lies_inside_its_field(dus: ReferenceRules) -> None:
    text = "rat/1/2021, ova/2/2021/1 und 61/ 3/2014 - 2"
    for hit in find_hits(text, dus, CODES):
        assert 0 <= hit.start < hit.end <= len(text)


@pytest.mark.parametrize(
    ("paper_type", "title", "role"),
    [
        ("Anfrage SPD", "Spielplatz", "anfrage"),
        ("zAnfrage REP", "", "anfrage"),
        ("Antrag CDU/Grüne", "Radweg", "antrag"),
        ("Haushaltsantrag SPD", "", "antrag"),
        ("Vorlage aus der Politik", "Anfrage der Ratsfraktion", "anfrage"),
        ("Vorlage aus der Politik", "Antrag und Anfrage", "antrag"),
        ("Vorlage aus der Politik", "Bericht", "politik"),
        ("Bedarfsbeschluss", "", "bedarf"),
        ("A+F Beschluss", "", "af"),
        ("Bezirksvertretung Informationsvorlage", "", "information"),
        ("Berichtsvorlage", "", "information"),
        ("Beschlussvorlage RPA", "", "vorlage"),
        ("Verwaltungsvorlage", "", "vorlage"),
        ("Eingabe nach 24GO", "", "eingabe"),
        ("Bezirksvertretung Eingabe nach 24Go", "", "eingabe"),
        ("Niederschrift", "", "sonst"),
        (None, None, "sonst"),
        # Der Titel schlägt die Dokumentart (§ 3.9, S1)
        ("Anfrage Bündnis 90/Die Grünen", "Antrag der Ratsfraktionen CDU und Grüne", "antrag"),
        ("Antrag SPD", " : Anfrage zum Stand", "anfrage"),
    ],
)
def test_roles_come_from_the_document_type(
    dus: ReferenceRules, paper_type: str | None, title: str | None, role: str
) -> None:
    assert role_of(paper_type, title, dus) == role


@pytest.mark.parametrize(
    ("paper_type", "role"),
    [
        ("3 - Fraktionsantrag", "antrag"),
        ("6.1 - Mitgliederantrag", "antrag"),
        ("2.1 - Berichtsvorlage", "information"),
        ("4 - Änderungsvorlage", "vorlage"),
        ("1.1 - Beratungsvorlage", "vorlage"),
    ],
)
def test_roles_of_the_second_city(mg: ReferenceRules, paper_type: str, role: str) -> None:
    assert role_of(paper_type, "", mg) == role


@pytest.mark.parametrize(
    ("citing", "cited", "amendment", "collective", "expected"),
    [
        ("information", "anfrage", False, True, "antwort"),  # vor dem Sammelbericht
        ("information", "antrag", False, True, "kontrolle"),
        ("anfrage", "antrag", False, False, "nachfrage"),  # auch nach dem Stand eines Antrags
        ("anfrage", "anfrage", False, False, "nachfrage"),
        ("vorlage", "antrag", False, False, "umsetzung"),
        ("information", "eingabe", False, False, "umsetzung"),
        ("information", "politik", False, False, "umsetzung"),
        ("antrag", "vorlage", True, False, "aenderung"),
        ("antrag", "vorlage", False, False, "bezug"),  # ohne Änderungszeichen
        ("politik", "af", True, False, "aenderung"),
        ("antrag", "anfrage", False, False, "fortsetzung"),
        ("information", "information", False, False, "fortsetzung"),
        ("af", "bedarf", False, False, "bau"),
        ("vorlage", "vorlage", True, False, "bezug"),
        ("sonst", "sonst", False, False, "bezug"),
    ],
)
def test_edge_types_follow_rule_set_two(
    citing: str, cited: str, amendment: bool, collective: bool, expected: str
) -> None:
    assert edge_type(citing, cited, amendment, collective) == expected
    assert expected in EDGE_TYPES


def test_a_collective_report_is_an_administrative_paper(dus: ReferenceRules) -> None:
    assert is_collective("Beschlusskontrolle 2023", "information", dus)
    assert is_collective("Übersicht zum Umsetzungsstand der Anträge", "vorlage", dus)
    assert not is_collective("Beschlusskontrolle 2023", "antrag", dus)
    assert not is_collective("Radweg", "information", dus)


def test_the_amendment_marker_counts_in_the_title_or_just_before(dus: ReferenceRules) -> None:
    title = "änderungsantrag der fraktion zu ova/2/2021"
    assert has_amendment_marker("titel", title, len(title) - 10, dus)
    text = "zur vorlage " + "x" * 100 + " ova/2/2021"
    assert has_amendment_marker("text", text, text.index("ova"), dus)
    far = "zur vorlage " + "x" * 130 + " ova/2/2021"
    assert not has_amendment_marker("text", far, far.index("ova"), dus)


@pytest.mark.parametrize(
    ("name", "answer"),
    [
        ("Antwort der Verwaltung", True),
        ("Beantwortung", True),
        ("Antworten der Verwaltung zu 01/ 12/2016", True),
        ("AGS 072 2020 Antwort der Verwaltung", True),
        ("Verwaltungsantwort", True),
        ("Stellungnahme der Verwaltung", True),
        ("Stellungnahme IHK", False),  # „Stellungnahme" allein ist zu breit (§ 3.6)
        ("Zwischennachricht, Antwort folgt", False),  # eine Zwischennachricht ist keine Antwort
        ("Vorlage", False),
        ("Fotos", False),
        (None, False),
    ],
)
def test_answer_attachments_by_name(dus: ReferenceRules, name: str | None, answer: bool) -> None:
    assert is_answer_attachment(name, dus) is answer


def test_without_a_pattern_no_attachment_is_an_answer(mg: ReferenceRules) -> None:
    assert not is_answer_attachment("Antwort der Verwaltung", mg)


def test_a_supplement_knows_its_base() -> None:
    assert Reference("OVA/1/2023/1", "OVA/1/2023").is_supplement
    assert not Reference("OVA/1/2023", "OVA/1/2023").is_supplement


def _form(**changes: object) -> dict[str, object]:
    form: dict[str, object] = {
        "name": "probe",
        "reference": r"(?P<serial>\d+)/(?P<year>\d{4})",
        "text": r"(?P<serial>\d+)/(?P<year>\d{4})",
        "key": "{serial}/{year}",
    }
    return form | changes


@pytest.mark.parametrize(
    "changes",
    [
        {"text": r"(?P<serial>\d+)/(?P<jahr>\d{4})"},  # unbekannte Gruppe
        {"key": "{serial}/{period}"},  # Gruppe fehlt in beiden Mustern
        {"key": "{year}"},  # ohne laufende Nummer
        {"glued": True},  # geklebt ohne Kürzel
        {"reference": "(?P<serial>"},  # kein Muster
    ],
)
def test_a_broken_form_fails_when_the_settings_load(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ReferenceForm.model_validate(_form(**changes))


def test_switching_on_needs_a_form() -> None:
    with pytest.raises(ValidationError, match="mindestens eine Form"):
        Procedures(enabled=True)
    assert Procedures(enabled=True, forms=[ReferenceForm.model_validate(_form())]).enabled
