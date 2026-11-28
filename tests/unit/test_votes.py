"""Vorhaben 28, Ebene A: die Wortregel, die Tabelle je Punkt, die Zählung je Gremienart, H28.2.

Messdokument ``docs/plans/28-abstimmungen.md``, § 8 (vorab festgelegt, Commit ``97ebb52``) und
§ 10: die Eingabe ist der Beratungsverlauf von 26, die Wortregel bleibt das Verfahren, und ein Test
vergleicht sie je Wert mit den Klassen von 26. Die Zahlen der Pakete und die Präzision gegen die
Labels prüft ``tests/golden/test_votes_numbers.py``.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import polars as pl
import pytest
from scipy import stats

from georep.analysis.hypotheses import CONFIRMED, check_hypotheses
from georep.analysis.outcomes import PROGRESS_SCHEMA
from georep.analysis.votes import (
    BODIES_SCHEMA,
    H1,
    H2,
    H3,
    HYPOTHESIS_KEY,
    LEVEL_B_REJECTED,
    MAIN,
    NEITHER,
    NO_MAJORITY,
    R1,
    R2,
    R3,
    R4,
    REFUTED,
    TOO_FEW,
    UNDECIDABLE,
    VOTES_SCHEMA,
    HypothesisInputs,
    Opposition,
    VoteRules,
    Window,
    agrees_with_outcomes,
    binomial_less,
    body_summary,
    form_of,
    hypothesis_rows,
    is_changed,
    last_decisions,
    opposition_motions,
    outcome_mismatches,
    result_class,
    votes_table,
)
from georep.errors import SchemaError
from georep.prep.bodies import BodyRules, kind_of_code
from georep.settings import Votes, load_settings

REPO = Path(__file__).resolve().parents[2]
NOWHERE = Path("/nonexistent")
SETTINGS = load_settings(cwd=NOWHERE)
RULES = VoteRules.from_settings(SETTINGS.votes)
BODIES = BodyRules.from_settings(SETTINGS.bodies)


def _measurement() -> ModuleType:
    """Das Messskript von 28 als Modul; es liest beim Import nichts."""
    path = REPO / "docs" / "plans" / "28-abstimmungen-messung.py"
    spec = importlib.util.spec_from_file_location("messung_28", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["messung_28"] = module
    spec.loader.exec_module(module)
    return module


# --- Die Wortregel (§ 8.1) ------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("result", "klasse", "form", "changed"),
    [
        ("einstimmig beschlossen", "angenommen", "einstimmig", False),
        ("mehrheitlich beschlossen", "angenommen", "mehrheitlich", False),
        ("Empfehlung einstimmig beschlossen", "angenommen", "einstimmig", False),
        ("abweichend beschlossen", "angenommen", "ohne_angabe", True),
        ("passieren lassen", "angenommen", "ohne_angabe", False),
        ("mehrheitlich abgelehnt", "abgelehnt", "mehrheitlich", False),
        # nach der Definition mehrheitlich, die Regel liest „ohne_angabe" (§ 3.1, bleibt so)
        ("abgelehnt aufgrund Stimmengleichheit", "abgelehnt", "ohne_angabe", False),
        ("zurückgezogen", "zurueckgezogen", None, False),
        ("vertagt", "vertagt", None, False),
        ("zurückgestellt", "vertagt", None, False),
        ("verwiesen", "verwiesen", None, False),
        ("zur Kenntnis genommen", "kenntnis", None, False),
        ("schriftlich beantwortet", "kenntnis", None, False),
        ("erledigt", "erledigt", None, False),
        ("zurückgewiesen", "sonstiges", None, False),
        ("", "sonstiges", None, False),
        (None, "sonstiges", None, False),
    ],
)
def test_die_wortregel_gibt_klasse_form_und_merker(
    result: str | None, klasse: str, form: str | None, changed: bool
) -> None:
    assert result_class(result, RULES) == klasse
    assert form_of(result, RULES) == form
    assert is_changed(result, RULES) is changed


def test_die_erste_zutreffende_regel_gilt() -> None:
    """„zurückgezogen" steht vor „abgelehnt", „vertagt" vor „beschlossen" (Folge aus § 8.1)."""
    assert result_class("Antrag zurückgezogen, Rest abgelehnt", RULES) == "zurueckgezogen"
    assert result_class("vertagt, nicht beschlossen", RULES) == "vertagt"


def test_die_wortregel_der_settings_ist_die_des_messskripts() -> None:
    """Die Regel ist vorab festgelegt (Commit 97ebb52) und gemessen; sie steht wörtlich in den
    Settings, und jeder Wert des Düsseldorfer Wortschatzes bekommt dieselbe Klasse und Form."""
    m = _measurement()
    assert RULES.results == m.ERGEBNIS_REGELN
    values = [*SETTINGS.outcomes.results, "", "Antrag erledigt", "Zugestimmt", "abgesetzt"]
    for value in values:
        assert result_class(value, RULES) == m.ergebnis(value), value
        assert form_of(value, RULES) == m.form_aus_result(value), value
        assert is_changed(value, RULES) == m.geaendert(value), value


# --- Die Wortregel neben dem Wortschatz von 26 (§ 10, Punkt 2) ------------------------------------
def test_wortregel_und_26_lesen_genau_zwei_werte_verschieden() -> None:
    """Je Wert des Düsseldorfer Wortschatzes: angenommen ⇔ beschlossen oder geändert, abgelehnt ⇔
    abgelehnt, zurückgezogen ⇔ zurückgezogen. Verschieden sind genau zwei Werte, beide gezählt,
    keiner angeglichen: „passieren lassen" (28 angenommen, 26 erledigt) und „zurückgewiesen" (28
    sonstiges, 26 abgelehnt)."""
    found = {
        value: (result_class(value, RULES), klasse)
        for value, (_, klasse) in SETTINGS.outcomes.results.items()
        if not agrees_with_outcomes(result_class(value, RULES), klasse)
    }
    assert found == {
        "passieren lassen": ("angenommen", "erledigt"),
        "zurückgewiesen": ("sonstiges", "abgelehnt"),
    }


def test_die_abweichungen_von_26_stehen_je_punkt() -> None:
    votes = votes_table(_progress(_ITEMS), BODIES, RULES)
    found = outcome_mismatches(votes, SETTINGS.outcomes.results)
    assert found.get_column("result").to_list() == ["passieren lassen"]
    assert found.row(0, named=True) == {
        "top": "t5",
        "result": "passieren lassen",
        "klasse_28": "angenommen",
        "klasse_26": "erledigt",
    }


# --- Die Tabelle je Punkt -------------------------------------------------------------------------
_ITEMS: list[tuple[str, str | None, str | None, str | None, dt.datetime]] = [
    # (Dokument, Punkt, Gremium, Eintrag, Sitzung)
    ("p1", "t1", "RAT", "einstimmig beschlossen", dt.datetime(2022, 3, 1, 15)),
    ("p1", "t2", "BV6", "mehrheitlich abgelehnt", dt.datetime(2022, 2, 1, 15)),
    ("p2", "t3", "gr/400224", "vertagt", dt.datetime(2022, 4, 1, 15)),
    ("p2", None, None, None, dt.datetime(2022, 5, 1, 15)),  # Beratung ohne Punkt: keine Einheit
    ("p3", "t4", "AWM+RAT", "abweichend beschlossen", dt.datetime(2022, 6, 1, 15)),
    ("p3", "t5", None, "passieren lassen", dt.datetime(2022, 7, 1, 15)),
    ("p3", "t6", "RAT", None, dt.datetime(2026, 12, 1, 15)),  # Sitzung steht aus
]


def _progress(
    rows: Sequence[tuple[str, str | None, str | None, str | None, dt.datetime]],
) -> pl.DataFrame:
    return pl.DataFrame(
        [
            (paper, f"b-{paper}-{top}", top, body, "-", start, "1", 1, result, None)
            for paper, top, body, result, start in rows
        ],
        schema=PROGRESS_SCHEMA,
        orient="row",
    )


def test_je_punkt_eine_zeile_mit_ergebnis_form_und_gremienart() -> None:
    votes = votes_table(_progress(_ITEMS), BODIES, RULES)
    assert votes.schema == pl.Schema(VOTES_SCHEMA)
    assert votes.get_column("top").to_list() == ["t1", "t2", "t3", "t4", "t5", "t6"]
    rows = {row["top"]: row for row in votes.iter_rows(named=True)}
    assert (rows["t1"]["ergebnis"], rows["t1"]["form"], rows["t1"]["gremium_art"]) == (
        "angenommen",
        "einstimmig",
        "rat",
    )
    assert (rows["t2"]["form"], rows["t2"]["gremium_art"]) == ("mehrheitlich", "bezirksvertretung")
    assert (rows["t3"]["form"], rows["t3"]["form_quelle"], rows["t3"]["gremium_art"]) == (
        None,
        None,
        "unbekannt",  # ein Schlüssel ohne Kürzel im Profil
    )
    # mehrere Organisationen: die Art der ersten, das Gremium wie bei 26
    assert (rows["t4"]["gremium"], rows["t4"]["gremium_art"]) == ("AWM+RAT", "ausschuss")
    assert rows["t4"]["geaendert"] is True and rows["t4"]["form"] == "ohne_angabe"
    assert rows["t5"]["gremium_art"] == "unbekannt"
    assert (rows["t6"]["ergebnis"], rows["t6"]["result"]) == ("sonstiges", None)
    assert rows["t1"]["form_quelle"] == "result" and rows["t1"]["datum"] == dt.date(2022, 3, 1)
    assert rows["t1"]["paper"] == "p1"


def test_ein_punkt_zweier_beratungen_bricht_ab() -> None:
    rows = [*_ITEMS, ("p9", "t1", "RAT", "vertagt", dt.datetime(2022, 3, 1, 15))]
    with pytest.raises(SchemaError, match="t1"):
        votes_table(_progress(rows), BODIES, RULES)


def test_je_gremienart_summieren_die_teile_zu_den_beschluessen() -> None:
    votes = votes_table(_progress(_ITEMS), BODIES, RULES)
    bodies = body_summary(votes, "2020-2025")
    assert bodies.schema == pl.Schema(BODIES_SCHEMA)
    assert bodies.get_column("gremium_art").to_list() == [
        "rat",
        "ausschuss",
        "bezirksvertretung",
        "unbekannt",
    ]
    rat = bodies.filter(pl.col("gremium_art") == "rat").row(0, named=True)
    assert (rat["punkte"], rat["mit_eintrag"], rat["beschluesse"], rat["einstimmig"]) == (
        2,
        1,
        1,
        1,
    )
    unknown = bodies.filter(pl.col("gremium_art") == "unbekannt").row(0, named=True)
    # t3 vertagt, t5 passieren lassen: ein Beschluss (angenommen) ohne Form
    assert (unknown["punkte"], unknown["beschluesse"], unknown["ohne_angabe"]) == (2, 1, 1)
    assert bodies.get_column("periode").unique().to_list() == ["2020-2025"]
    assert bodies.get_column("punkte").sum() == votes.height


def test_die_gremienarten_stehen_in_der_folge_des_messdokuments() -> None:
    rows = [
        ("p1", f"t{i}", body, "einstimmig beschlossen", dt.datetime(2022, 3, 1, 15))
        for i, body in enumerate(("gr/1", "BV1", "INTR", "AWM", "RAT"))
    ]
    bodies = body_summary(votes_table(_progress(rows), BODIES, RULES), "2020-2025")
    assert bodies.get_column("gremium_art").to_list() == [
        "rat",
        "ausschuss",
        "bezirksvertretung",
        "beirat",
        "unbekannt",
    ]


# --- H28.2 (§ 8.6) --------------------------------------------------------------------------------
def _votes(rows: list[tuple[str, str, str, str, dt.date]]) -> pl.DataFrame:
    """(Punkt, Dokument, Gremienart, Ergebnis, Tag) als Tabelle je Punkt."""
    return pl.DataFrame(
        [
            (
                top,
                paper,
                dt.datetime.combine(day, dt.time(15)),
                day,
                "X",
                kind,
                "1",
                klasse,
                klasse,
                False,
                "mehrheitlich" if klasse in ("angenommen", "abgelehnt") else None,
                "result" if klasse in ("angenommen", "abgelehnt") else None,
            )
            for top, paper, kind, klasse, day in rows
        ],
        schema=VOTES_SCHEMA,
        orient="row",
    )


def _corpus(types: dict[str, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {"id": list(types), "paper_type": list(types.values())},
        schema={"id": pl.String, "paper_type": pl.String},
    )


def _originators(parties: dict[str, list[str]], art: str = "Fraktion") -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": list(parties),
            "urheber_art": [art] * len(parties),
            "parteien": list(parties.values()),
        },
        schema={"id": pl.String, "urheber_art": pl.String, "parteien": pl.List(pl.String)},
    )


WHO = Opposition(frozenset({"A", "B"}), frozenset({"X"}), "antrag", "anfrage")


def test_anträge_allein_der_opposition_ohne_ausgelassene_fraktion() -> None:
    corpus = _corpus(
        {
            "m1": "Antrag C",
            "m2": "Antrag A/C",  # mit der Mehrheit
            "m3": "Antrag X",  # die Fraktion der WZB-Schwelle
            "m4": "Anfrage C",  # keine Initiative
            "m5": "Haushaltsantrag D",
            "m6": "Beschlussvorlage",
            "m7": "Antrag",  # ohne Partei
        }
    )
    originators = _originators(
        {
            "m1": ["C"],
            "m2": ["A", "C"],
            "m3": ["X"],
            "m4": ["C"],
            "m5": ["D"],
            "m6": ["C"],
            "m7": [],
        }
    )
    found = opposition_motions(corpus, originators, WHO)
    assert found.get_column("id").to_list() == ["m1", "m5"]
    person = _originators({"m1": ["C"]}, art="Person")
    assert opposition_motions(corpus, person, WHO).is_empty()


def test_der_letzte_entschiedene_beschluss_im_zeitraum_zaehlt() -> None:
    votes = _votes(
        [
            ("t1", "m1", "rat", "abgelehnt", dt.date(2021, 3, 1)),
            ("t2", "m1", "rat", "angenommen", dt.date(2022, 3, 1)),  # später: maßgeblich
            ("t3", "m1", "rat", "vertagt", dt.date(2023, 3, 1)),  # keine Entscheidung
            ("t4", "m1", "ausschuss", "abgelehnt", dt.date(2024, 3, 1)),  # anderes Gremium
            ("t5", "m2", "rat", "angenommen", dt.date(2020, 12, 31)),  # vor dem Zeitraum
            ("t6", "m3", "rat", "abgelehnt", dt.date(2025, 9, 14)),  # letzter Tag zählt
            ("t7", "m3", "rat", "angenommen", dt.date(2025, 9, 15)),  # danach nicht
        ]
    )
    motions = pl.DataFrame(
        {"id": ["m1", "m2", "m3"], "parteien": [["C"], ["C"], ["D"]]},
        schema={"id": pl.String, "parteien": pl.List(pl.String)},
    )
    found = last_decisions(
        votes,
        motions,
        ("rat",),
        ("angenommen", "abgelehnt"),
        dt.date(2021, 1, 1),
        dt.date(2025, 9, 14),
    )
    assert found.select("id", "top").rows() == [("m1", "t2"), ("m3", "t6")]
    wider = last_decisions(
        votes, motions, ("rat",), ("angenommen", "abgelehnt", "vertagt"), dt.date(2021, 1, 1), None
    )
    assert wider.select("id", "top").rows() == [("m1", "t3"), ("m3", "t7")]


@pytest.mark.parametrize(("k", "n"), [(0, 30), (41, 389), (12, 30), (30, 30)])
def test_binomialtest_und_grenzen_wie_scipy(k: int, n: int) -> None:
    test = binomial_less(k, n, 0.25)
    assert test.p == pytest.approx(stats.binomtest(k, n, 0.25, alternative="less").pvalue)
    interval = stats.binomtest(k, n, 0.25).proportion_ci(confidence_level=0.90, method="exact")
    assert test.lower == pytest.approx(interval.low)
    assert test.upper == pytest.approx(interval.high)


def _scenario(accepted: int, rejected: int) -> HypothesisInputs:
    rows: list[tuple[str, str, str, str, dt.date]] = []
    types: dict[str, str] = {}
    parties: dict[str, list[str]] = {}
    for i in range(accepted + rejected):
        paper = f"m{i:03d}"
        klasse = "angenommen" if i < accepted else "abgelehnt"
        rows.append((f"t{i:03d}", paper, "rat", klasse, dt.date(2022, 1, 1)))
        rows.append((f"u{i:03d}", paper, "ausschuss", "angenommen", dt.date(2021, 6, 1)))
        types[paper] = "Antrag"
        parties[paper] = ["C"] if i % 2 else ["C", "D"]
    return HypothesisInputs(_votes(rows), _corpus(types), _originators(parties))


VOTES = Votes(
    excluded_parties=["X"],
    motion_type="antrag",
    motion_not="anfrage",
    fixed="97ebb52",
)
MAIN_WINDOW = Window(MAIN, dt.date(2021, 1, 1), dt.date(2025, 9, 14), frozenset({"A", "B"}))
LABELS = {"A": "A", "B": "B", "C": "C", "D": "D", "X": "X"}


def _main(frame: pl.DataFrame, hypothesis: str = H2) -> dict[str, object]:
    rows = frame.filter((pl.col("hypothese") == hypothesis) & (pl.col("rechnung") == MAIN))
    assert rows.height == 1
    return rows.row(0, named=True)


def test_h28_2_wird_mit_holm_ueber_drei_hypothesen_bestaetigt() -> None:
    frame = hypothesis_rows(_scenario(4, 56), [MAIN_WINDOW], VOTES, LABELS)
    check_hypotheses(frame, 0.05, key=HYPOTHESIS_KEY, strict=True, m=3)
    row = _main(frame)
    expected = stats.binomtest(4, 60, 0.25, alternative="less").pvalue
    assert (row["n"], row["angenommen"]) == (60, 4)
    assert row["p"] == pytest.approx(expected)
    assert row["p_holm"] == pytest.approx(min(1.0, 3 * expected))  # H28.1 und H28.3 zählen mit
    assert (row["ergebnis"], row["entscheidung"], row["grund"]) == (CONFIRMED, CONFIRMED, None)
    assert row["festgelegt"] == "97ebb52"
    assert frame.get_column("hypothese").to_list()[:3] == [H1, H2, H3]


def test_h28_1_und_h28_3_sind_ohne_ebene_b_nicht_entscheidbar() -> None:
    frame = hypothesis_rows(_scenario(4, 56), [MAIN_WINDOW], VOTES, LABELS)
    for hypothesis in (H1, H3):
        row = _main(frame, hypothesis)
        assert (row["p"], row["p_holm"], row["ergebnis"], row["n"]) == (None, None, None, None)
        assert (row["entscheidung"], row["grund"]) == (UNDECIDABLE, LEVEL_B_REJECTED)


def test_ein_hoher_anteil_widerlegt_h28_2() -> None:
    row = _main(hypothesis_rows(_scenario(30, 30), [MAIN_WINDOW], VOTES, LABELS))
    assert row["ergebnis"] == "nicht bestätigt"
    assert isinstance(row["ci_unten"], float) and row["ci_unten"] > 0.25
    assert (row["entscheidung"], row["grund"]) == (REFUTED, None)


def test_dazwischen_ist_h28_2_nicht_entscheidbar() -> None:
    row = _main(hypothesis_rows(_scenario(13, 47), [MAIN_WINDOW], VOTES, LABELS))
    assert row["ergebnis"] == "nicht bestätigt"
    assert (row["entscheidung"], row["grund"]) == (UNDECIDABLE, NEITHER)


def test_unter_dreissig_antraegen_entscheidet_h28_2_nicht() -> None:
    frame = hypothesis_rows(_scenario(1, 28), [MAIN_WINDOW], VOTES, LABELS)
    row = _main(frame)
    assert row["n"] == 29 and row["p"] is not None
    assert (row["p_holm"], row["ergebnis"]) == (None, None)  # außerhalb der Familie
    assert (row["entscheidung"], row["grund"]) == (UNDECIDABLE, TOO_FEW)
    check_hypotheses(frame, 0.05, key=HYPOTHESIS_KEY, strict=True, m=3)


def test_ohne_mehrheit_ist_h28_2_nicht_entscheidbar() -> None:
    window = Window(MAIN, MAIN_WINDOW.start, MAIN_WINDOW.end, None)
    row = _main(hypothesis_rows(_scenario(4, 56), [window], VOTES, LABELS))
    assert (row["n"], row["entscheidung"], row["grund"]) == (None, UNDECIDABLE, NO_MAJORITY)


def test_die_nebenrechnungen_entscheiden_nicht() -> None:
    frame = hypothesis_rows(_scenario(4, 56), [MAIN_WINDOW], VOTES, LABELS)
    side = frame.filter(pl.col("rechnung") != MAIN)
    assert side.select("rechnung", "partei").rows() == [
        (R1, None),
        (R3, None),
        (R4, "C"),
        (R4, "D"),
    ]
    assert side.get_column("entscheidung").null_count() == side.height
    assert side.get_column("p_holm").null_count() == side.height
    r1 = side.filter(pl.col("rechnung") == R1).row(0, named=True)
    assert (r1["n"], r1["angenommen"]) == (60, 60)  # in den Ausschüssen alles angenommen
    r4 = {
        row["partei"]: row["n"]
        for row in side.filter(pl.col("rechnung") == R4).iter_rows(named=True)
    }
    assert r4 == {"C": 60, "D": 30}  # ein gemeinsamer Antrag zählt bei beiden


def test_r2_rechnet_ohne_entscheidung_und_ohne_weitere_nebenrechnungen() -> None:
    window = Window(R2, dt.date(2021, 1, 1), None, frozenset({"A", "B"}))
    frame = hypothesis_rows(_scenario(4, 56), [window], VOTES, LABELS)
    assert frame.select("hypothese", "rechnung").rows() == [(H1, R2), (H2, R2), (H3, R2)]
    assert frame.get_column("entscheidung").null_count() == 3
    assert frame.get_column("p_holm").null_count() == 3
    h2 = frame.filter(pl.col("hypothese") == H2).row(0, named=True)
    assert (h2["n"], h2["angenommen"], h2["bis"]) == (60, 4, None)
    assert (
        frame.filter(pl.col("hypothese") != H2).get_column("grund").to_list()
        == [LEVEL_B_REJECTED] * 2
    )


def test_ohne_zeitraum_ist_die_tabelle_leer_mit_schema() -> None:
    frame = hypothesis_rows(_scenario(4, 56), [], VOTES, LABELS)
    assert frame.is_empty()
    check_hypotheses(frame, 0.05, key=HYPOTHESIS_KEY, strict=True, m=3)


def test_die_klasse_eines_kuerzels_ist_die_von_bodies() -> None:
    assert [kind_of_code(code, BODIES) for code in ("RAT", "AWM", "BV1", "INTR", "gr/1", "BV")] == [
        "rat",
        "ausschuss",
        "bezirksvertretung",
        "beirat",
        "unbekannt",
        "unbekannt",
    ]
