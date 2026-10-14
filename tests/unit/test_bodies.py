"""Gremium aus der Drucksachennummer: Parser, Regeln aus den Settings, Frame-Funktion."""

from __future__ import annotations

import deal
import polars as pl
import pytest

from georep.prep.bodies import (
    ADVISORY,
    BODIES_COLUMNS,
    COMMITTEE,
    COUNCIL,
    DISTRICT_BODY,
    KINDS,
    UNKNOWN,
    BodyRef,
    BodyRules,
    classify_papers,
    counts_by_kind,
    parse_reference,
    summary,
)
from georep.settings import Bodies, Settings


@pytest.fixture(scope="module")
def rules(default_settings: Settings) -> BodyRules:
    return BodyRules.from_settings(default_settings.bodies)


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        # die sechs Formen der Referenz (docs/plans/05-gremien.md, § 3.1)
        ("BV6/108/2023", BodyRef(DISTRICT_BODY, "BV6", 6)),
        ("BV10/107/2023", BodyRef(DISTRICT_BODY, "BV10", 10)),
        ("RAT/270/2023", BodyRef(COUNCIL, "RAT", None)),
        ("KUA/015/2024", BodyRef(COMMITTEE, "KUA", None)),
        ("AÖE/050/2023", BodyRef(COMMITTEE, "AÖE", None)),
        ("JURAT/001/2021", BodyRef(ADVISORY, "JURAT", None)),
        ("OVA/117/2023/1", BodyRef(COMMITTEE, "OVA", None)),
        ("BV7/233/2022/1", BodyRef(DISTRICT_BODY, "BV7", 7)),
        ("BV10/104/2020-2", BodyRef(DISTRICT_BODY, "BV10", 10)),
        ("BV10/149/2022/-1", BodyRef(DISTRICT_BODY, "BV10", 10)),
        # Punkt 57: die Nummernform vor 2019, deren Kopf eine Bezirksvertretung bedeutet
        ("171/ 23/2016", BodyRef(DISTRICT_BODY, "BV1", 1)),
        ("170/ 1/2015", BodyRef(DISTRICT_BODY, "BV10", 10)),  # der zehnte Stadtbezirk
        ("179/ 108/2019/1", BodyRef(DISTRICT_BODY, "BV9", 9)),  # mit Nachtrag
        ("01/ 113/2014 - 1", BodyRef(UNKNOWN, None, None)),  # eine Amtsnummer ist kein Gremium
        ("61/ 12/2014", BodyRef(UNKNOWN, None, None)),
        # kein Treffer des Musters
        ("11/3/2019", BodyRef(UNKNOWN, None, None)),
        ("bv1/1/2020", BodyRef(UNKNOWN, None, None)),
        ("", BodyRef(UNKNOWN, None, None)),
        (None, BodyRef(UNKNOWN, None, None)),
        # Treffer des Musters, aber keine Tabelle
        ("BV/1/2020", BodyRef(UNKNOWN, "BV", None)),
        ("BV0/1/2020", BodyRef(UNKNOWN, "BV0", None)),
        ("RAT1/1/2020", BodyRef(UNKNOWN, "RAT1", None)),
        ("XYZ/1/2020", BodyRef(UNKNOWN, "XYZ", None)),
    ],
)
def test_parse_reference_examples(
    reference: str | None, expected: BodyRef, rules: BodyRules
) -> None:
    assert parse_reference(reference, rules) == expected


def test_kinds_and_names(rules: BodyRules) -> None:
    assert KINDS == (DISTRICT_BODY, COUNCIL, COMMITTEE, ADVISORY, UNKNOWN)
    assert rules.name_of(parse_reference("BV6/108/2023", rules)) == "Bezirksvertretung 6"
    assert rules.name_of(parse_reference("RAT/270/2023", rules)) == "Rat"
    assert rules.name_of(parse_reference("OVA/1/2023", rules)) == "Ordnungs- und Verkehrsausschuss"
    assert rules.name_of(parse_reference("KUA/1/2023", rules)) == ""  # nicht gesichert
    assert rules.name_of(parse_reference("XYZ/1/2023", rules)) == ""
    assert rules.name_of(parse_reference("kaputt", rules)) == ""


def test_rules_are_independent_of_the_city(default_settings: Settings) -> None:
    bodies = default_settings.bodies.model_copy(
        update={
            "reference_pattern": r"^(?P<number>\d+)?(?P<code>[a-z]+)-\d+$",
            "district_body": "bz",
            "district_body_name": "Bezirk {n}",
            "council": {"rat": "Der Rat"},
            "committees": {},
            "advisory": {"jr": ""},
        }
    )
    rules = BodyRules.from_settings(bodies)
    # das Kürzel ist kanonisch Kürzel plus Nummer, egal wie das Muster sie anordnet
    assert parse_reference("3bz-17", rules) == BodyRef(DISTRICT_BODY, "bz3", 3)
    assert rules.name_of(BodyRef(DISTRICT_BODY, "bz3", 3)) == "Bezirk 3"
    assert parse_reference("rat-1", rules) == BodyRef(COUNCIL, "rat", None)
    assert parse_reference("jr-1", rules) == BodyRef(ADVISORY, "jr", None)
    assert parse_reference("BV6/108/2023", rules) == BodyRef(UNKNOWN, None, None)


def test_the_alias_of_an_older_numbering_is_data_not_code(default_settings: Settings) -> None:
    """Punkt 57: ``bodies.aliases`` übersetzt den Kopf einer alten Nummer in ein Kürzel.

    Befragt wird die Tabelle nur, wenn das Muster nicht trifft -- die Hauptperiode, in der es
    jede Nummer trifft, merkt von ihr nichts. Das Ziel entscheidet dann über die Klasse, nach
    denselben zwei Regeln wie das Muster.
    """
    bodies = default_settings.bodies.model_copy(
        update={"aliases": {"170": "BV10", "9": "RAT", "8": "JURAT", "7": "KUA"}}
    )
    rules = BodyRules.from_settings(bodies)
    assert parse_reference("170/ 1/2015", rules) == BodyRef(DISTRICT_BODY, "BV10", 10)
    assert parse_reference("9/ 1/2015", rules) == BodyRef(COUNCIL, "RAT", None)
    assert parse_reference("8/ 1/2015", rules) == BodyRef(ADVISORY, "JURAT", None)
    assert parse_reference("7/ 1/2015", rules) == BodyRef(COMMITTEE, "KUA", None)
    assert parse_reference("6/ 1/2015", rules) == BodyRef(UNKNOWN, None, None)  # kein Alias
    # Eine Nummer, die das Muster trifft, nimmt den Weg des Musters; der Kopf wird nie befragt
    assert parse_reference("RAT/270/2023", rules) == BodyRef(COUNCIL, "RAT", None)
    # Ohne Tabelle bleibt alles, wie es war (jede andere Stadt und jedes andere Profil)
    plain = BodyRules.from_settings(default_settings.bodies.model_copy(update={"aliases": {}}))
    assert plain.aliases == {}
    assert parse_reference("170/ 1/2015", plain) == BodyRef(UNKNOWN, None, None)


def test_an_alias_must_point_at_a_code_the_profile_knows(default_settings: Settings) -> None:
    """Ein Alias ins Nichts wäre „unbekannt" mit einem erfundenen Kürzel daneben."""
    for aliases, message in (
        ({"170": "BV0"}, "steht in keiner Tabelle"),  # Bezirk 0 gibt es nicht
        ({"170": "XYZ"}, "steht in keiner Tabelle"),
        ({"170": "BV"}, "steht in keiner Tabelle"),  # ohne Nummer keine Bezirksvertretung
        ({"": "BV1"}, "ist kein Kopf einer Nummer"),
        ({"170/ 1": "BV1"}, "ist kein Kopf einer Nummer"),
    ):
        with pytest.raises(ValueError, match=message):
            Bodies.model_validate(default_settings.bodies.model_dump() | {"aliases": aliases})
    # Eine Stadt ohne Muster kennt keine Kürzel, also auch keine Aliasse (Mönchengladbach)
    with pytest.raises(ValueError, match="kennt keine Kürzel"):
        Bodies(aliases={"170": "BV1"})


def test_a_pattern_without_the_group_code_is_unknown_not_an_error() -> None:
    """Die Settings erzwingen die Gruppen; ein von Hand gebautes BodyRules nicht (crosshair, 2026-10-12)."""
    import re

    broken = BodyRules(
        pattern=re.compile("(.*)"),
        district_body="BV",
        district_body_name="Bezirksvertretung {n}",
        council=frozenset(),
        committees=frozenset(),
        advisory=frozenset(),
        names={},
    )
    assert parse_reference("RAT/1/2020", broken) == BodyRef(UNKNOWN, None, None)
    assert parse_reference("", broken) == BodyRef(UNKNOWN, None, None)


def test_classify_papers_on_the_mini_fixture(mini_run: object, rules: BodyRules) -> None:
    from georep.layout import Layout

    assert isinstance(mini_run, Layout)
    corpus = pl.read_parquet(mini_run.corpus, columns=["id", "reference"])
    frame = classify_papers(corpus, rules)
    assert frame.columns == BODIES_COLUMNS
    assert frame.schema["stadtbezirk"] == pl.Int64 and frame.schema["gremium"] == pl.String
    assert frame.height == 200 and frame.get_column("id").is_sorted()
    assert counts_by_kind(frame) == {
        DISTRICT_BODY: 93,
        COMMITTEE: 86,
        COUNCIL: 16,
        ADVISORY: 5,
        UNKNOWN: 0,
    }
    assert summary(frame) == (
        "200 Dokumente: 93 Bezirksvertretung, 16 Rat, 86 Ausschuss, 5 Beirat, 0 unbekannt"
    )
    bv = frame.filter(pl.col("gremium_art") == DISTRICT_BODY)
    assert bv.get_column("stadtbezirk").null_count() == 0
    assert frame.filter(pl.col("gremium_art") != DISTRICT_BODY)["stadtbezirk"].null_count() == (
        frame.height - bv.height
    )


def test_classify_papers_keeps_every_id_and_marks_unknowns(rules: BodyRules) -> None:
    corpus = pl.DataFrame(
        {
            "id": ["p3", "p1", "p2", "p4"],
            "reference": ["RAT/1/2021", "BV2/5/2022", "11/3/2019", None],
            "text": ["", "", "", ""],
        }
    )
    frame = classify_papers(corpus, rules)
    assert frame.get_column("id").to_list() == ["p1", "p2", "p3", "p4"]
    assert frame.get_column("gremium").to_list() == ["BV2", None, "RAT", None]
    assert frame.get_column("gremium_art").to_list() == [DISTRICT_BODY, UNKNOWN, COUNCIL, UNKNOWN]
    assert frame.get_column("stadtbezirk").to_list() == [2, None, None, None]
    assert counts_by_kind(frame)[COMMITTEE] == 0  # jede Klasse kommt vor, auch leer
    with pytest.raises(deal.PreContractError):
        classify_papers(corpus.drop("reference"), rules)


# --- Option 01: eine Stadt, deren Nummern kein Kürzel tragen ----------------------------------


def test_numbers_without_a_body_code_are_all_unknown() -> None:
    """Ohne ``reference_pattern`` gibt es kein Kürzel: jedes Dokument ist „unbekannt".

    Mönchengladbachs Drucksachennummern sind laufende Nummer und Wahlperiode (``0682/XI``,
    Stichprobe 2026-10-12); aus ihnen ist das Gremium nicht zu erschließen.
    """
    rules = BodyRules.from_settings(Bodies())
    assert parse_reference("0682/XI", rules) == BodyRef(UNKNOWN, None, None)
    assert parse_reference("RAT/270/2023", rules) == BodyRef(UNKNOWN, None, None)
    corpus = pl.DataFrame({"id": ["a", "b"], "reference": ["0682/XI", None]})
    frame = classify_papers(corpus, rules)
    assert frame.get_column("gremium_art").to_list() == [UNKNOWN, UNKNOWN]
