"""Antragsteller, Fraktionen und Lager je Fraktionsdokument (Vorhaben 15), an Beispielen.

Die Fälle stehen im Messdokument ``docs/plans/15-funktion.md``, § 3.8 bis § 3.11; die Regeln sind
die des Stadtprofils. ``parteien`` aus Option 04 ist die Eingabe, gegen die die Antragsteller sich
bewähren müssen: sie nimmt die erste Quelle mit Treffer und übersieht Mitantragsteller.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from georep.analysis.cosponsors import (
    CAMPS,
    COSPONSORS_SCHEMA,
    CosponsorRules,
    author_part,
    camp,
    classify_cosponsors,
    cosponsor_figures,
    cosponsors,
    fractions_on,
    letterhead_authors,
)
from georep.errors import SchemaError
from georep.settings import Majorities, Settings, load_settings

NOWHERE = Path("/nonexistent")
HEAD_2014 = "vorlage 175/ 104/2016 seite 1 von 2 rsd vorlage x öffentlich nicht öffentlich  "


@pytest.fixture(scope="module")
def city() -> Settings:
    return load_settings(cwd=NOWHERE)


@pytest.fixture(scope="module")
def rules(city: Settings) -> CosponsorRules:
    return CosponsorRules.from_settings(city)


def _who(
    rules: CosponsorRules,
    name: str,
    paper_type: str = "Antrag",
    text: str = "",
    parteien: tuple[str, ...] = (),
) -> tuple[tuple[str, ...], str]:
    return cosponsors(paper_type, name, text, "Fraktion", parteien, rules)


def test_an_amendment_names_its_own_authors_not_those_of_the_motion(rules: CosponsorRules) -> None:
    name = (
        "Änderungsantrag der SPD-Ratsfraktion zum Antrag der Ratsfraktionen von CDU und "
        "BÜNDNIS 90/DIE GRÜNEN"
    )
    assert author_part(name.lower(), rules) == "änderungsantrag der spd-ratsfraktion"
    assert _who(rules, name) == (("SPD",), "titel")


def test_the_subject_after_a_separator_is_no_author(rules: CosponsorRules) -> None:
    found = _who(
        rules, "Antrag Die Linke: AfD keine Plattform geben", parteien=("Die_Linke", "AfD")
    )
    assert found == (("Die_Linke",), "titel")


def test_a_joint_type_and_three_fractions_in_the_title_make_three(rules: CosponsorRules) -> None:
    """RAT/510/2023: `parteien` nahm nur die Dokumentart."""
    name = (
        "Haushaltsantrag der Ratsfraktionen von CDU, BÜNDNIS 90/DIE GRÜNEN und SPD zum "
        "Haushalt 2024"
    )
    found = _who(rules, name, "Haushaltsantrag CDU/Grüne", parteien=("CDU", "GRUENE"))
    assert found == (("CDU", "GRUENE", "SPD"), "art+titel")


def test_the_letterhead_of_2014_names_two_fractions(rules: CosponsorRules) -> None:
    text = (
        HEAD_2014 + "spd - fraktion  cdu - fraktion  der bezirksvertretung 8  an den "
        "bezirksbürgermeister  antrag zur fdp-forderung"
    )
    assert letterhead_authors(text, rules) == "  spd - fraktion  cdu - fraktion  "
    found = _who(rules, "Spielplatz", "Vorlage aus der Politik", text, parteien=("CDU",))
    assert found == (("CDU", "SPD"), "briefkopf")


def test_without_any_part_the_parties_of_option_04_remain(rules: CosponsorRules) -> None:
    assert _who(rules, "Spielplatz", "Vorlage aus der Politik", parteien=("FDP",)) == (
        ("FDP",),
        "parteien",
    )
    assert _who(rules, "Interfraktioneller Antrag", "Antrag") == ((), "")


def test_only_a_fraction_has_cosponsors(rules: CosponsorRules) -> None:
    found = cosponsors("Beschlussvorlage", "Antrag der CDU", "", "Verwaltung", ("CDU",), rules)
    assert found == ((), "")


def test_spd_and_volt_are_one_fraction_from_november_2020(
    city: Settings, rules: CosponsorRules
) -> None:
    order = rules.order
    fractions = city.functions.fractions
    assert fractions_on(("SPD", "VOLT"), date(2021, 3, 1), fractions, order) == ("SPD+VOLT",)
    assert fractions_on(("SPD",), date(2021, 3, 1), fractions, order) == ("SPD+VOLT",)
    assert fractions_on(("SPD",), date(2020, 10, 15), fractions, order) == ("SPD",)  # alter Rat
    assert fractions_on(("SPD", "CDU"), None, fractions, order) == ("CDU", "SPD")
    assert fractions_on(("PARTEI", "T_FW", "GRUENE"), date(2025, 12, 1), fractions, order) == (
        "GRUENE",
        "T_FW+PARTEI",
    )


@pytest.mark.parametrize(
    ("fractions", "majority", "expected"),
    [
        ((), {"CDU", "GRUENE"}, "ohne_partei"),
        (("CDU",), {"CDU", "GRUENE"}, "allein_mehrheit"),
        (("AfD",), {"CDU", "GRUENE"}, "allein_opposition"),
        (("CDU", "GRUENE"), {"CDU", "GRUENE"}, "gemeinsam_mehrheit"),
        (("FDP", "SPD+VOLT"), {"CDU", "GRUENE"}, "gemeinsam_opposition"),
        (("CDU", "FDP", "GRUENE", "SPD+VOLT"), {"CDU", "GRUENE"}, "ueber_grenze"),
        (("CDU",), None, "ohne_lager"),
        ((), None, "ohne_lager"),
    ],
)
def test_the_camp_of_a_document(
    fractions: tuple[str, ...], majority: set[str] | None, expected: str
) -> None:
    assert camp(fractions, majority) == expected


def test_a_party_unknown_to_the_settings_in_a_majority_fails_loudly(city: Settings) -> None:
    term = city.majorities.terms[0].model_copy(update={"parties": ["SPD", "PIRATEN"]})
    broken = city.model_copy(
        update={"majorities": city.majorities.model_copy(update={"terms": [term]})}
    )
    with pytest.raises(SchemaError, match="PIRATEN"):
        CosponsorRules.from_settings(broken)


def test_every_packaged_majority_and_fraction_names_known_parties() -> None:
    for profile in ("duesseldorf", "duesseldorf-2014", "duesseldorf-2025", "moenchengladbach"):
        CosponsorRules.from_settings(load_settings(profile=profile, cwd=NOWHERE))


def test_the_frame_has_one_row_per_corpus_id_with_the_camp_at_the_city_level(
    rules: CosponsorRules,
) -> None:
    corpus = pl.DataFrame(
        {
            "id": ["e", "d", "c", "b", "a"],
            "date": [
                date(2021, 5, 1),
                date(2021, 5, 1),
                date(2020, 10, 1),
                date(2021, 5, 1),
                date(2021, 5, 1),
            ],
            "paper_type": [
                "Beschlussvorlage",
                "Antrag CDU/Grüne",
                "Antrag SPD",
                "Antrag",
                "Antrag FDP",
            ],
            "name": [
                "Schule",
                "Mehr Bäume",
                "Radweg",
                "Antrag der Fraktionen CDU, SPD/Volt und FDP: Resolution gegen Antisemitismus",
                "Spielplatz",
            ],
            "text": ["", "", "", "", ""],
        }
    )
    originators = pl.DataFrame(
        {
            "id": ["a", "b", "c", "d", "e"],
            "urheber_art": ["Fraktion", "Fraktion", "Fraktion", "Fraktion", "Verwaltung"],
            "parteien": [["FDP"], ["CDU"], ["SPD"], ["CDU", "GRUENE"], []],
        }
    )
    bodies = pl.DataFrame(
        {
            "id": ["a", "b", "c", "d", "e"],
            "gremium_art": ["bezirksvertretung", "rat", "rat", "ausschuss", "rat"],
        }
    )
    frame = classify_cosponsors(corpus, originators, bodies, rules)
    assert frame.schema == pl.Schema(COSPONSORS_SCHEMA)
    rows = {r["id"]: r for r in frame.iter_rows(named=True)}
    assert list(rows) == ["a", "b", "c", "d", "e"]
    assert rows["a"]["lager"] == "ohne_lager"  # Bezirksvertretung: dort gilt die Ratsmehrheit nicht
    assert rows["b"]["fraktionen"] == ["CDU", "SPD+VOLT", "FDP"]
    assert rows["b"]["gemeinsam"] is True
    assert rows["b"]["lager"] == "ueber_grenze"
    assert rows["c"]["fraktionen"] == ["SPD"]  # vor dem 2020-11-01: der alte Rat
    assert rows["c"]["lager"] == "allein_mehrheit"  # und seine Mehrheit, die Ampel
    assert rows["d"]["lager"] == "gemeinsam_mehrheit"
    assert rows["e"]["antragsteller"] == [] and rows["e"]["lager"] == "ohne_partei"
    figures = cosponsor_figures(frame)
    assert figures["mit_antragsteller"] == 4 and figures["gemeinsam"] == 2
    assert sum(figures[c] for c in CAMPS) == frame.height


def test_without_majorities_no_document_has_a_camp(city: Settings) -> None:
    rules = CosponsorRules.from_settings(city.model_copy(update={"majorities": Majorities()}))
    corpus = pl.DataFrame(
        {
            "id": ["a"],
            "date": [date(2021, 5, 1)],
            "paper_type": ["Antrag CDU"],
            "name": ["x"],
            "text": [""],
        }
    )
    originators = pl.DataFrame({"id": ["a"], "urheber_art": ["Fraktion"], "parteien": [["CDU"]]})
    bodies = pl.DataFrame({"id": ["a"], "gremium_art": ["rat"]})
    frame = classify_cosponsors(corpus, originators, bodies, rules)
    assert frame.get_column("lager").to_list() == ["ohne_lager"]


def test_the_second_city_keeps_its_fractions_apart_until_its_new_council() -> None:
    """Review 2026-11-24, M2: „FDP / VOLT" und „DIE LINKE / DIE PARTEI" gibt es erst im Rat ab
    2025; in den Texten 2020 bis 2025 steht „volt" nie, und die Briefköpfe nennen Linke und PARTEI
    getrennt."""
    settings = load_settings(profile="moenchengladbach", cwd=NOWHERE)
    rules = CosponsorRules.from_settings(settings)
    fractions = settings.functions.fractions
    assert fractions_on(("FDP",), date(2024, 6, 1), fractions, rules.order) == ("FDP",)
    assert fractions_on(("Die_Linke", "PARTEI"), date(2025, 8, 19), fractions, rules.order) == (
        "Die_Linke",
        "PARTEI",
    )
    assert fractions_on(("FDP", "VOLT"), date(2025, 11, 1), fractions, rules.order) == ("FDP+VOLT",)
