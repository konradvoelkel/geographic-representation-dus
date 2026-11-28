"""Vorhaben 16: die Stelle eines Treffers, an synthetischen Texten (``search.positions``).

Die Regeln sind die des Messskripts (``docs/plans/16-ortsbezug-messung.py``): die grobe Stelle aus
dem Abschnitt von Vorhaben 11, die Listenzeile (``LISTE_MAX_ZEILE``, ``LISTE_MAX_VORLAUF``), die
Hausnummer (``HAUSNR`` mit dem Ausschluss der Einheiten) und Nebenregel C je Begriff und je Paar.
Muster und Grenzen kommen aus dem Stadtprofil; ein Test hält sie gleich denen des Messskripts,
denn jede Änderung wäre ein neues Verfahren (Messdokument § 6). Keine echten Dokumente.
"""

from __future__ import annotations

import ast
from pathlib import Path

import polars as pl
import pytest

from georep.prep.raw_texts import flatten
from georep.search.matcher import FlashTextMatcher
from georep.search.positions import (
    BODY,
    CORE,
    POSITIONS,
    REST,
    SUBJECT,
    TITLE,
    PlaceRules,
    coarse_position,
    house_number,
    is_list_line,
    pair_positions,
    raw_hits,
    term_positions,
)
from georep.settings import Settings, load_settings

NOWHERE = Path("/nonexistent")
SCRIPT = Path(__file__).resolve().parents[2] / "docs" / "plans" / "16-ortsbezug-messung.py"


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(profile="duesseldorf", cwd=NOWHERE)


@pytest.fixture(scope="module")
def rules(settings: Settings) -> PlaceRules:
    return PlaceRules.from_settings(settings)


def _script_constants() -> dict[str, object]:
    """``LISTE_MAX_ZEILE``, ``LISTE_MAX_VORLAUF`` und ``HAUSNR`` aus dem Messskript, ohne es zu laden."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    found: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name in ("LISTE_MAX_ZEILE", "LISTE_MAX_VORLAUF"):
            found[name] = ast.literal_eval(node.value)
        elif name == "HAUSNR" and isinstance(node.value, ast.Call):
            found[name] = ast.literal_eval(node.value.args[0])
    return found


def test_the_profile_carries_the_constants_of_the_measurement(settings: Settings) -> None:
    """§ 6: „Konstanten wie im Messskript, im Profil statt im Code, ohne Änderung"."""
    script = _script_constants()
    places = settings.places
    assert places.list_max_line == script["LISTE_MAX_ZEILE"] == 60
    assert places.list_max_lead == script["LISTE_MAX_VORLAUF"] == 12
    assert places.house_number == script["HAUSNR"]


@pytest.mark.parametrize(
    ("section", "coarse"),
    [
        ("betreff", SUBJECT),
        ("beschlussvorschlag", CORE),
        ("fragen", CORE),
        ("sachdarstellung", BODY),
        ("begruendung", BODY),
        ("stellungnahme", BODY),
        ("beschlusslage", BODY),
        ("alternative", BODY),
        ("rumpf", BODY),
        ("anlagen", REST),
        ("nachrichtlich", REST),
        ("kopf_amt", REST),
        ("", REST),
    ],
)
def test_the_coarse_position_of_a_section(section: str, coarse: str) -> None:
    assert coarse_position(section) == coarse


def test_the_positions_are_ranked_title_first() -> None:
    assert POSITIONS == (TITLE, SUBJECT, CORE, BODY, REST)


@pytest.mark.parametrize(
    ("after", "expected"),
    [
        (" 12a, Ecke", (12, "a")),
        (" 12 a ", (12, "a")),
        (" 50–54", (50, "")),
        (" 12/14", (12, "")),
        (" Nr. 5", (5, "")),
        ("  7", (7, "")),
        (" 2 Standorte", None),
        # Das gemessene Muster, unverändert (§ 3.4): ein einzelner Buchstabe hinter der Zahl ist
        # Zusatz, auch die Einheit „m"; „km", „qm" und Wörter schließt es aus. Ein Fall für eine
        # spätere Fassung, nicht für diesen Bau
        (" 150 m entfernt", (150, "m")),
        (" 150 km", None),
        (" 3,5 km", None),
        (" 2023", None),
        (" 40 %", None),
        (" 12 Uhr", None),
        (" 6 Stellplätze", None),
        (" in 12", None),
        ("12", (12, "")),
    ],
)
def test_a_house_number_directly_behind_the_street(
    rules: PlaceRules, after: str, expected: tuple[int, str] | None
) -> None:
    raw = "An der Kürtenstraße" + after
    end = len("An der Kürtenstraße")
    assert house_number(raw, end, rules.house_number) == expected


@pytest.mark.parametrize(
    ("line", "column", "expected"),
    [
        ("14 Kürtenstraße: Poller", 3, True),  # Begriff nach „14 " in einer kurzen Zeile
        ("   1. Kürtenstraße", 6, True),  # Leerraum am Rand zählt nicht zum Vorlauf
        ("Die Verwaltung prüft den Poller auf der Kürtenstraße.", 40, False),  # zu langer Vorlauf
        ("Kürtenstraße " + "x" * 47, 0, True),  # genau 60 Zeichen
        ("Kürtenstraße " + "x" * 48, 0, False),  # 61 Zeichen
        ("123456789012 Kürtenstraße", 13, False),  # 13 Zeichen Vorlauf
        ("12345678901 Kürtenstraße", 12, True),  # 12
    ],
)
def test_a_list_line(rules: PlaceRules, line: str, column: int, expected: bool) -> None:
    assert is_list_line(line, column, rules.list_max_line, rules.list_max_lead) is expected


def _matcher(*terms: str) -> FlashTextMatcher:
    matcher = FlashTextMatcher()
    matcher.add_terms(terms)
    return matcher


def test_raw_hits_lie_on_the_raw_text(rules: PlaceRules) -> None:
    """Die Stelle im Rohtext ist die des Textstores über ``flatten_with_offsets``; ein Begriff
    über einen Zeilenumbruch liegt im Rohtext mit dem Umbruch."""
    raw = "Kopf\nBetrifft: Poller Kürten\nstraße 12\fSeite 2: Am Wehrhahn"
    store = flatten(raw, "betrifft", ())
    assert store == ": poller kürtenstraße 12seite 2: am wehrhahn"
    found = raw_hits(
        raw, (), store, "Poller", "betrifft", _matcher("kürtenstraße", "am wehrhahn"), rules
    )
    assert found is not None
    assert [(h.term, raw[h.start : h.end]) for h in found] == [
        ("kürtenstraße", "Kürten\nstraße"),
        ("am wehrhahn", "Am Wehrhahn"),
    ]
    first, second = found
    assert first.house == (12, "") and second.house is None
    assert not first.in_title and not second.in_title


def test_a_term_in_the_title_is_marked(rules: PlaceRules) -> None:
    raw = "Betrifft: Kürtenstraße"
    store = flatten(raw, "betrifft", ())
    found = raw_hits(
        raw, (), store, "Antrag zur Kürtenstraße", "betrifft", _matcher("kürtenstraße"), rules
    )
    assert found is not None and [h.in_title for h in found] == [True]


def test_without_the_bridge_there_are_no_hits(rules: PlaceRules) -> None:
    """Plättet der Rohtext nicht genau zum Textstore, ist keine Stelle sicher (Messdokument § 3.0)."""
    assert raw_hits("Betrifft: A", (), ": b", "", "betrifft", _matcher("a"), rules) is None


def _spans(rows: list[tuple[str, str, str, bool, bool, bool]]) -> pl.DataFrame:
    """id, norm (Begriff), stelle, im_titel, listenzeile, hausnummer -- was ``term_positions`` liest."""
    return pl.DataFrame(
        rows,
        schema={
            "id": pl.String,
            "norm": pl.String,
            "stelle": pl.String,
            "im_titel": pl.Boolean,
            "listenzeile": pl.Boolean,
            "hausnummer": pl.Boolean,
        },
        orient="row",
    )


def test_rule_c_per_term() -> None:
    """Nebenregel C: Titel, Betreff oder Kern; sonst eine Listenzeile oder eine Hausnummer im
    Begleittext. Eine Liste im Rest zählt nicht."""
    spans = _spans(
        [
            ("d1", "a", BODY, True, False, False),  # im Titel
            ("d1", "b", CORE, False, False, False),  # im Kern
            ("d1", "c", BODY, False, False, False),
            ("d1", "c", BODY, False, False, False),  # zweimal Begleittext, ohne Liste
            ("d1", "e", BODY, False, True, False),  # Listenzeile im Begleittext
            ("d1", "f", BODY, False, False, True),  # Hausnummer im Begleittext
            ("d1", "g", REST, False, True, True),  # Liste im Rest zählt nicht
        ]
    )
    terms = term_positions(spans)
    assert terms.columns == [
        "id",
        "suchbegriffe",
        "stelle",
        "erwaehnungen",
        "n_begleit",
        "n_liste",
        "handelt_von",
    ]
    rows = {r["suchbegriffe"]: r for r in terms.iter_rows(named=True)}
    assert {t: rows[t]["stelle"] for t in rows} == {
        "a": TITLE,
        "b": CORE,
        "c": BODY,
        "e": BODY,
        "f": BODY,
        "g": REST,
    }
    assert {t: rows[t]["handelt_von"] for t in rows} == {
        "a": True,
        "b": True,
        "c": False,
        "e": True,
        "f": True,
        "g": False,
    }
    assert rows["c"]["erwaehnungen"] == 2 and rows["c"]["n_begleit"] == 2
    assert rows["e"]["n_liste"] == 1 and rows["g"]["n_liste"] == 0


def test_pairs_take_the_best_term_and_keep_pairs_without_position() -> None:
    terms = term_positions(
        _spans(
            [
                ("d1", "a", BODY, False, False, False),
                ("d1", "b", SUBJECT, False, False, False),
                ("d2", "a", BODY, False, False, False),
            ]
        )
    )
    triples = pl.DataFrame(
        {
            "wahlkreis_id": [1, 1, 2, 2, 3],
            "id": ["d1", "d1", "d1", "d2", "d3"],
            "suchbegriffe": ["a", "b", "a", "a", "a"],
        },
        schema={"wahlkreis_id": pl.Int64, "id": pl.String, "suchbegriffe": pl.String},
    )
    pairs = pair_positions(terms, triples)
    assert pairs.columns == [
        "id",
        "wahlkreis_id",
        "stelle",
        "erwaehnungen",
        "n_begleit",
        "n_liste",
        "handelt_von",
    ]
    got = {
        (r["id"], r["wahlkreis_id"]): (r["stelle"], r["handelt_von"])
        for r in pairs.iter_rows(named=True)
    }
    assert got == {
        ("d1", 1): (SUBJECT, True),
        ("d1", 2): (BODY, False),
        ("d2", 2): (BODY, False),
        ("d3", 3): (None, None),  # kein Rohtext: keine Stelle, kein Urteil
    }
    assert pairs.filter(pl.col("id") == "d3").get_column("erwaehnungen").to_list() == [None]
