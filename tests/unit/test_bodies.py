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
    merge_consultations,
    organization_key,
    parse_reference,
    resolve_organizations,
    source_counts,
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


# --- Punkt 58: die Beratungsfolge als zweite Quelle -------------------------------------------

ORG = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/organizations"


def _folge(pairs: dict[str, list[str]]) -> pl.DataFrame:
    """Beratungsfolge je Dokument, wie Korpus und Paket sie tragen (volle Organisations-URLs)."""
    return pl.DataFrame(
        {
            "id": list(pairs),
            "consultation_organizations": [[f"{ORG}/{k}" for k in v] for v in pairs.values()],
        },
        schema={"id": pl.String, "consultation_organizations": pl.List(pl.String)},
    )


@pytest.fixture
def with_organizations(default_settings: Settings) -> BodyRules:
    """Die Regeln der Hauptperiode plus eine kleine, gelernte Abbildung (gr/6 ist der Rat)."""
    return BodyRules.from_settings(
        default_settings.bodies.model_copy(
            update={
                "organizations": {
                    "gr/6": "RAT",
                    "gr/32": "BV1",
                    "gr/25": "OVA",
                    f"{ORG}/gr/22": "JHA",  # auch eine volle URL ist ein Schlüssel
                }
            }
        )
    )


def test_organization_key_cuts_a_url_to_its_last_two_segments() -> None:
    assert organization_key(f"{ORG}/gr/6") == "gr/6"
    assert organization_key("gr/6") == "gr/6"
    assert organization_key("gr") == "gr"  # weniger als zwei Segmente bleiben, wie sie sind
    assert organization_key("") == ""


def test_resolve_organizations_is_sorted_unique_and_forgets_the_unknown(
    with_organizations: BodyRules,
) -> None:
    mapping = with_organizations.organizations
    assert resolve_organizations([f"{ORG}/gr/6"], mapping) == ("RAT",)
    assert resolve_organizations([f"{ORG}/gr/22"], mapping) == ("JHA",)  # Schlüssel als URL
    assert resolve_organizations([f"{ORG}/gr/25", f"{ORG}/gr/6"], mapping) == ("OVA", "RAT")
    assert resolve_organizations([f"{ORG}/gr/6", f"{ORG}/gr/6"], mapping) == ("RAT",)
    assert resolve_organizations([f"{ORG}/gr/999"], mapping) == ()
    assert resolve_organizations([], mapping) == ()
    assert resolve_organizations([f"{ORG}/gr/6"], {}) == ()


def test_the_number_decides_and_the_consultation_only_fills_the_gaps(
    with_organizations: BodyRules,
) -> None:
    """Punkt 58: vier Fälle in einem Frame -- ergänzt, bestätigt, Widerspruch, mehrdeutig."""
    corpus = pl.DataFrame(
        {
            "id": ["p1", "p2", "p3", "p4", "p5"],
            # p1 Amtsnummer (die Folge ergänzt), p2 bestätigt, p3 Widerspruch, p4 mehrdeutig,
            # p5 Amtsnummer ohne auflösbare Folge
            "reference": ["61/ 12/2014", "RAT/1/2021", "OVA/2/2021", "61/ 13/2014", "61/ 14/2014"],
        }
    )
    folge = _folge(
        {
            "p1": ["gr/32"],
            "p2": ["gr/6"],
            "p3": ["gr/6"],
            "p4": ["gr/6", "gr/25"],
            "p5": ["gr/999"],
        }
    )
    frame = classify_papers(corpus, with_organizations, folge)
    assert frame.get_column("gremium").to_list() == ["BV1", "RAT", "OVA", None, None]
    assert frame.get_column("quelle").to_list() == [
        "beratungsfolge",
        "nummer",
        "nummer",
        "unbekannt",
        "unbekannt",
    ]
    assert frame.get_column("stadtbezirk").to_list() == [1, None, None, None, None]
    assert frame.get_column("folge_gremium").to_list() == ["BV1", "RAT", "RAT", None, None]
    assert frame.get_column("folge_anzahl").to_list() == [1, 1, 1, 2, 0]
    counts = source_counts(frame)
    assert counts.documents == 5 and counts.from_consultation == 1
    assert (counts.confirmed, counts.conflicting, counts.ambiguous) == (1, 1, 1)
    assert counts.line() == ("Beratungsfolge: 1 ergänzt, 1 bestätigt, 1 Widerspruch, 1 mehrdeutig")
    assert summary(frame).endswith(counts.line())


def test_without_the_mapping_nothing_changes(default_settings: Settings) -> None:
    """Ein Profil ohne ``[bodies.organizations]`` rechnet wie vor Punkt 58, auch mit Folge."""
    plain = BodyRules.from_settings(
        default_settings.bodies.model_copy(update={"organizations": {}})
    )
    corpus = pl.DataFrame({"id": ["p1"], "reference": ["61/ 12/2014"]})
    frame = classify_papers(corpus, plain, _folge({"p1": ["gr/32"]}))
    assert frame.get_column("gremium_art").to_list() == [UNKNOWN]
    assert frame.get_column("folge_anzahl").to_list() == [0]
    assert source_counts(frame).line() == ""
    assert summary(frame) == (
        "1 Dokumente: 0 Bezirksvertretung, 0 Rat, 0 Ausschuss, 0 Beirat, 1 unbekannt"
    )


def test_the_alias_is_its_own_source(default_settings: Settings) -> None:
    rules = BodyRules.from_settings(default_settings.bodies)
    assert parse_reference("171/ 23/2016", rules).source == "alias"
    assert parse_reference("RAT/270/2023", rules).source == "nummer"
    assert parse_reference("BV6/1/2023", rules).source == "nummer"
    assert parse_reference("61/ 12/2014", rules).source == "unbekannt"
    assert parse_reference("XYZ/1/2020", rules).source == "unbekannt"
    # Die Herkunft ist keine Identität: dasselbe Gremium bleibt dasselbe (``compare=False``)
    assert BodyRef(COUNCIL, "RAT", None, "nummer") == BodyRef(
        COUNCIL, "RAT", None, "beratungsfolge"
    )


def test_merge_consultations_lets_the_document_win(with_organizations: BodyRules) -> None:
    own = _folge({"p1": ["gr/6"], "p2": [], "p3": []})
    extra = _folge({"p1": ["gr/25"], "p2": ["gr/32"], "p9": ["gr/6"]})
    merged = merge_consultations(own, extra)
    assert merged.columns == ["id", "consultation_organizations"]
    assert merged.height == 3  # p9 steht nur im Paket und fällt weg
    by_id = dict(
        zip(
            merged.get_column("id").to_list(),
            merged.get_column("consultation_organizations").to_list(),
            strict=True,
        )
    )
    assert by_id["p1"] == [f"{ORG}/gr/6"]  # das Dokument selbst gewinnt
    assert by_id["p2"] == [f"{ORG}/gr/32"]  # aus dem Paket aufgefüllt
    assert by_id["p3"] == []
    assert merge_consultations(own, None).to_dicts() == own.to_dicts()


def test_a_consultation_target_must_be_a_code_the_profile_knows(
    default_settings: Settings,
) -> None:
    for organizations, message in (
        ({"gr/6": "XYZ"}, "steht in keiner Tabelle"),
        ({"gr/6": "BV0"}, "steht in keiner Tabelle"),
        ({"gr 6": "RAT"}, "ist kein Schlüssel"),
        ({"": "RAT"}, "ist kein Schlüssel"),
        ({"organizations/gr/6": "RAT"}, "weder eine URL noch zwei Segmente"),
    ):
        with pytest.raises(ValueError, match=message):
            Bodies.model_validate(
                default_settings.bodies.model_dump() | {"organizations": organizations}
            )


def test_a_city_without_a_pattern_may_still_know_bodies_from_the_consultation() -> None:
    """Mönchengladbach: keine Nummer trägt ein Kürzel, die Beratungsfolge nennt die Gremien.

    Dann sind die Kürzeltabellen erlaubt, obwohl ``reference_pattern`` leer ist; ohne beides
    bleiben sie verboten, weil ein Kürzel dann nie zustande käme.
    """
    bodies = Bodies(
        district_body="BV",
        district_body_name="Bezirksvertretung {n}",
        district_body_names={"BV1": "Bezirksvertretung Nord"},
        council={"RAT": "Rat"},
        organizations={"gr/83": "RAT", "gr/117": "BV1"},
    )
    rules = BodyRules.from_settings(bodies)
    corpus = pl.DataFrame({"id": ["a", "b"], "reference": ["0682/XI", "0683/XI"]})
    frame = classify_papers(corpus, rules, _folge({"a": ["gr/117"], "b": ["gr/83", "gr/117"]}))
    assert frame.get_column("gremium").to_list() == ["BV1", None]
    assert frame.get_column("gremium_art").to_list() == [DISTRICT_BODY, UNKNOWN]
    assert frame.get_column("stadtbezirk").to_list() == [1, None]
    assert rules.name_of(BodyRef(DISTRICT_BODY, "BV1", 1)) == "Bezirksvertretung Nord"
    assert rules.name_of(BodyRef(DISTRICT_BODY, "BV2", 2)) == "Bezirksvertretung 2"
    with pytest.raises(ValueError, match="kennt keine Kürzel"):
        Bodies(district_body_names={"BV1": "Bezirksvertretung Nord"})
    with pytest.raises(ValueError, match="ist kein Kürzel einer Bezirksvertretung"):
        Bodies.model_validate(bodies.model_dump() | {"district_body_names": {"RAT": "Rat"}})
