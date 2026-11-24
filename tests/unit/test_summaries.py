"""Eingabe, Prompt und Rolle der Kurzfassungen (Vorhaben 20, ``georep.enrich.summaries``).

Alle Texte sind erfunden (Konrads Regel: keine Kurzfassung und kein Ratstext in Tests); die
Abschnitte stehen als fertige ``SectionText``, wie sie der Schritt aus den Spannen von Vorhaben 11
mit ``read_span`` liest.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from georep.enrich.summaries import (
    CORE,
    MARK,
    MIN_FALLBACK_CHARS,
    PROMPT_VERSION,
    RULES,
    SECTIONS,
    SYSTEM,
    UNKNOWN,
    SectionText,
    SummaryMeta,
    cut,
    deliberation,
    fraction_label,
    header,
    party_labels,
    prompt,
    role_frame,
    sender,
    summaries_dir,
    summaries_files,
    summary_input,
)
from georep.layout import Layout
from georep.pack import package_files
from georep.prep.bodies import BodyRules
from georep.settings import Settings, Summaries, load_settings

NOWHERE = Path("/nonexistent")
META = SummaryMeta(
    "d1",
    "Beschlussvorlage",
    "OVA/7/2025",
    date(2025, 3, 4),
    "Neue Bänke am Kanalufer",
    "Verwaltung",
    "Ordnungs- und Verkehrsausschuss",
)


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=NOWHERE)


def section(kind: str, start: int, end: int, text: str) -> SectionText:
    return SectionText(kind, start, end, text)


def test_the_header_names_sender_and_deliberation() -> None:
    assert header(META).splitlines() == [
        "Dokumentart: Beschlussvorlage",
        "Absender: Verwaltung",
        "Beratung: Ordnungs- und Verkehrsausschuss",
        "Drucksache: OVA/7/2025",
        "Datum: 04.03.2025",
        "Titel: Neue Bänke am Kanalufer",
    ]
    blank = SummaryMeta("d2", "", "", None, "")
    assert header(blank).splitlines() == [
        "Dokumentart: unbekannt",
        f"Absender: {UNKNOWN}",
        f"Beratung: {UNKNOWN}",
        "Drucksache: unbekannt",
        "Datum: unbekannt",
        "Titel: unbekannt",
    ]


def test_sections_come_in_fixed_order_under_their_headings() -> None:
    found = summary_input(
        META,
        [
            section("sachdarstellung", 300, 400, "Die Bänke sind alt."),
            section("betreff", 10, 40, "Neue Bänke"),
            section("beschlussvorschlag", 100, 200, "Der Ausschuss beschließt drei Bänke."),
        ],
        "",
        8000,
    )
    assert found.source == "abschnitte"
    assert found.sections == ("betreff", "beschlussvorschlag", "sachdarstellung")
    assert found.text == (
        header(META) + "\n\n## Betreff\nNeue Bänke\n\n## Beschlussvorschlag\nDer Ausschuss "
        "beschließt drei Bänke.\n\n## Sachdarstellung\nDie Bänke sind alt."
    )
    assert not found.truncated
    assert found.chars == len("Neue Bänke") + len("Der Ausschuss beschließt drei Bänke.") + len(
        "Die Bänke sind alt."
    )


def test_level_two_inside_a_taken_section_and_unknown_kinds_stay_out() -> None:
    found = summary_input(
        META,
        [
            section("beschlussvorschlag", 100, 300, "Der Ausschuss beschließt. Kosten 5 €."),
            section("finanzen", 200, 250, "Kosten 5 €."),  # Ebene 2 im Beschlussvorschlag
            section("kopf_amt", 0, 20, "Amt 66"),
            section("anlagen", 400, 500, "Anlage 1"),
            section("finanzen", 600, 650, "Die Mittel stehen bereit."),
        ],
        "",
        8000,
    )
    assert found.sections == ("beschlussvorschlag", "finanzen")
    assert found.text.count("## Finanzen") == 1
    assert "Die Mittel stehen bereit." in found.text
    assert "Amt 66" not in found.text and "Anlage 1" not in found.text


def test_empty_sections_are_skipped_and_same_titles_share_a_heading() -> None:
    found = summary_input(
        META,
        [
            section("begruendung", 100, 150, "Erstens."),
            section("begruendung", 200, 250, "Zweitens."),
            section("fragen", 300, 310, "  \n "),
        ],
        "",
        8000,
    )
    assert found.sections == ("begruendung",)
    assert "## Begründung\nErstens.\n\nZweitens." in found.text
    assert "## Fragen" not in found.text


def test_the_budget_cuts_at_a_line_end_and_nothing_follows() -> None:
    long = "Erste Zeile des Vorschlags.\n" + "lang " * 40
    found = summary_input(
        META,
        [
            section("beschlussvorschlag", 0, 500, long),
            section("sachdarstellung", 600, 700, "Kommt nicht mehr."),
        ],
        "",
        50,
    )
    assert found.truncated
    assert found.sections == ("beschlussvorschlag",)
    assert found.text.endswith("## Beschlussvorschlag\nErste Zeile des Vorschlags." + MARK)
    assert found.chars <= 50 + len(MARK)


def test_cut_falls_back_to_a_word_end_and_then_to_the_room() -> None:
    assert cut("eins zwei drei vier", 12) == "eins zwei" + MARK
    assert cut("x" * 40, 10) == "x" * 10 + MARK
    assert (
        cut("kurz\n" + "y" * 40, 30) == "kurz\n" + "y" * 25 + MARK
    )  # Zeile zu früh: Wortende fehlt


def test_without_a_core_section_the_raw_text_follows_the_subject() -> None:
    fallback = "Hierzu teilt das Amt mit: Die Bänke werden im Frühjahr aufgestellt."
    found = summary_input(
        META,
        [section("betreff", 10, 40, "Neue Bänke"), section("finanzen", 50, 60, "Keine Kosten.")],
        fallback,
        8000,
    )
    assert found.source == "rohtext"
    assert found.sections == ("betreff", "text")
    assert found.text.endswith("## Betreff\nNeue Bänke\n\n## Text\n" + fallback)
    assert "Keine Kosten." not in found.text
    assert not set(found.sections) & CORE


def test_the_fallback_is_cut_in_the_remaining_budget() -> None:
    found = summary_input(META, [section("betreff", 0, 10, "Bänke")], "wort " * 100, 40)
    assert found.source == "rohtext" and found.truncated
    assert found.chars <= 40 + len(MARK)


def test_no_text_after_the_head_gives_no_input() -> None:
    """Frage 20.6: ohne Text nach dem Kopf schreibt der Schritt keine Kurzfassung."""
    found = summary_input(
        META, [section("betreff", 0, 10, "Bänke")], "x" * (MIN_FALLBACK_CHARS - 1), 8000
    )
    assert (found.source, found.text, found.sections, found.chars) == ("ohne_text", "", (), 0)


def test_the_prompt_is_the_rules_and_the_input() -> None:
    found = summary_input(META, [section("fragen", 0, 20, "Wann kommen die Bänke?")], "", 8000)
    assert prompt(found) == RULES + found.text
    assert RULES.endswith("Dokument:\n\n")


def test_prompt_version_two_carries_the_three_changes() -> None:
    """Fassung 2: Rolle aus den Kopfzeilen (§ 5.3), nicht selbst zählen (20.12), Straßen (20.8)."""
    assert PROMPT_VERSION == "20-kurzfassung-2"
    rules = RULES.splitlines()
    assert "„Absender“" not in RULES  # die Anführungszeichen sind die der Fassung 1
    assert any(line.startswith("1.") and '„Absender"' in line for line in rules)
    assert any(line.startswith("3.") and "Zähle und rechne nicht selbst" in line for line in rules)
    assert any(line.startswith("5.") and "Straßen-" in line for line in rules)
    assert SYSTEM.startswith("Du schreibst Kurzfassungen von Dokumenten")
    assert [kind for kind, _ in SECTIONS][:3] == ["betreff", "beschlussvorschlag", "fragen"]


# --- Rolle ---------------------------------------------------------------------------------------


def test_the_sender_follows_the_originator_class(settings: Settings) -> None:
    labels = party_labels(settings.originators)
    assert sender("Verwaltung", [], labels) == "Verwaltung"
    assert sender("Fraktion", ["GRUENE"], labels) == "Fraktion Bündnis 90/Die Grünen"
    assert sender("Fraktion", ["SPD+VOLT"], labels) == "Fraktion SPD/Volt"
    assert sender("Fraktion", ["CDU", "GRUENE", "FDP"], labels) == (
        "Fraktionen CDU, Bündnis 90/Die Grünen und FDP"
    )
    assert sender("Fraktion", [], labels) == "Fraktion"
    assert sender("Person", [], labels) == "einzelnes Mitglied eines Gremiums"
    assert sender("Eingabe", [], labels).startswith("Einwohnerinnen oder Einwohner")
    assert sender("unbekannt", [], labels) == UNKNOWN
    assert sender(None, [], labels) == UNKNOWN


def test_a_fraction_key_reads_with_party_names() -> None:
    assert fraction_label("A+B", {"A": "Alpha", "B": "Beta"}) == "Alpha/Beta"
    assert fraction_label("C", {}) == "C"


def test_deliberation_names_the_bodies_of_the_consultation(settings: Settings) -> None:
    rules = BodyRules.from_settings(settings.bodies)
    base = "https://example.org/oparl/bodies/1/organizations/"
    assert deliberation([f"{base}gr/6", f"{base}gr/37"], None, rules) == "Bezirksvertretung 6, Rat"
    assert deliberation([f"{base}gr/999999"], "OVA", rules) == rules.names["OVA"]
    assert deliberation([], "BV3", rules) == "Bezirksvertretung 3"
    assert deliberation([], None, rules) == UNKNOWN
    assert deliberation([], "XYZ", rules) == "XYZ"  # ohne gesicherten Namen das Kürzel


def test_the_role_frame_has_one_row_per_id_and_tolerates_missing_sources(
    settings: Settings,
) -> None:
    originators = pl.DataFrame({"id": ["a", "b"], "urheber_art": ["Verwaltung", "Fraktion"]})
    fractions = pl.DataFrame({"id": ["a", "b"], "fraktionen": [[], ["CDU"]]})
    bodies = pl.DataFrame({"id": ["a", "b"], "gremium": ["BV2", "RAT"]})
    frame = role_frame(["b", "a", "c"], originators, fractions, bodies, None, settings)
    assert frame.columns == ["id", "absender", "beratung"]
    assert frame.rows() == [
        ("a", "Verwaltung", "Bezirksvertretung 2"),
        ("b", "Fraktion CDU", "Rat"),
        ("c", UNKNOWN, UNKNOWN),
    ]
    bare = role_frame(["a"], None, None, None, None, settings)
    assert bare.rows() == [("a", UNKNOWN, UNKNOWN)]


# --- nie veröffentlicht --------------------------------------------------------------------------


def test_the_outputs_live_under_the_cache_never_under_the_data_root(
    tmp_path: Path, settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", profile="p")
    folder = summaries_dir(layout)
    assert folder.is_relative_to(tmp_path / "cache" / "p")
    for path in summaries_files(layout):
        assert path.is_relative_to(folder)
        assert not path.is_relative_to(layout.data_root)
        assert not path.is_relative_to(layout.site)
    packed = [source for source, _ in package_files(layout, settings)]
    assert not any(source.is_relative_to(folder) for source in packed)


# --- Settings ------------------------------------------------------------------------------------


def test_the_settings_default_to_off_with_gemma(settings: Settings) -> None:
    """Urteil § 5.3: gebaut wird mit gemma4; der Schalter ist aus, bis ein Profil ihn setzt."""
    block = settings.summaries
    assert (block.enabled, block.model, block.budget_chars) == (False, "gemma4", 8000)
    assert (block.rare_share, block.known_documents) == (0.01, 3)
    assert re.fullmatch(block.person_titles, "Beigeordnete")  # Regel 5, Review von 11


@pytest.mark.parametrize(
    "bad",
    [
        {"budget_chars": 0},
        {"rare_share": 0.0},
        {"rare_share": 1.0},
        {"known_documents": 0},
        {"person_titles": "Herr("},
    ],
)
def test_the_settings_refuse_impossible_values(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Summaries.model_validate(bad)


# --- Beratung aus dem Kopf von 11 und rumpf_leer (Antworten des Supervisors, 2026-11-24) ---------

HEAD_ROWS = [
    {"gremium": "Bauausschuss", "gremium_kuerzel": None, "datum": None, "qualitaet": "Vorberatung"},
    {
        "gremium": "Rat der Stadt",
        "gremium_kuerzel": "RAT",
        "datum": None,
        "qualitaet": "Entscheidung",
    },
    {"gremium": "Bezirksvertretung 3", "gremium_kuerzel": "BV3", "datum": None, "qualitaet": "-/-"},
]


def test_deliberation_takes_the_head_rows_in_order_with_their_quality(settings: Settings) -> None:
    """Der Kopf trägt Folge und Qualität (11: Tripel 160/168, Folge 27/27 gegen die Labels)."""
    rules = BodyRules.from_settings(settings.bodies)
    base = "https://example.org/oparl/bodies/1/organizations/"
    assert deliberation([f"{base}gr/6"], None, rules, head=HEAD_ROWS) == (
        "Bauausschuss (Vorberatung), Rat (Entscheidung), Bezirksvertretung 3"
    )
    # ohne Zeile im Kopf die OParl-Folge (Punkt 58), wie bisher
    assert deliberation([f"{base}gr/6"], None, rules, head=[]) == "Rat"


def test_the_role_frame_reads_the_head(settings: Settings) -> None:
    head = pl.DataFrame(
        {"id": ["a", "b"], "beratungsfolge": [HEAD_ROWS[:2], []]},
        schema={
            "id": pl.String,
            "beratungsfolge": pl.List(
                pl.Struct(
                    {
                        "gremium": pl.String,
                        "gremium_kuerzel": pl.String,
                        "datum": pl.Date,
                        "qualitaet": pl.String,
                    }
                )
            ),
        },
    )
    bodies = pl.DataFrame({"id": ["a", "b"], "gremium": ["BV2", "BV2"]})
    frame = role_frame(["a", "b"], None, None, bodies, None, settings, head=head)
    assert frame.get_column("beratung").to_list() == [
        "Bauausschuss (Vorberatung), Rat (Entscheidung)",
        "Bezirksvertretung 2",
    ]


def test_an_empty_body_gives_no_input_even_with_a_long_fallback() -> None:
    """Frage 20.6: ``rumpf_leer`` aus dem Kopf von 11, zusätzlich zur Grenze von 50 Zeichen."""
    head_only = [section("betreff", 0, 10, "Bänke")]
    found = summary_input(META, head_only, "x" * 500, 8000, body_empty=True)
    assert found.source == "ohne_text"
    kept = summary_input(
        META, [section("fragen", 0, 20, "Wann kommen die Bänke?")], "", 8000, body_empty=True
    )
    assert kept.source == "abschnitte"  # ein Kernabschnitt trägt, der Schalter gilt im Rückfall
