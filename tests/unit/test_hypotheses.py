"""Der gemeinsame Kern der vorab festgelegten Hypothesen (``analysis.hypotheses``).

Holm gegen Rechnungen von Hand, die Wortwahl des Ergebnisses und die Prüfung einer
Hypothesentabelle: Vorhaben 17 baut den Kern, Vorhaben 22 und später 21, 24, 27 nutzen ihn
(Synergien 2026-11, § 1).
"""

from __future__ import annotations

import polars as pl
import pytest

from georep.analysis.hypotheses import (
    CONFIRMED,
    CORE_SCHEMA,
    NOT_CONFIRMED,
    PROVISIONAL,
    check_hypotheses,
    family,
    holm,
    hypothesis_frame,
)
from georep.errors import SchemaError


def test_holm_by_hand_for_the_three_tests_of_vorhaben_17() -> None:
    """Die Zahlen aus dem Messdokument 17, § 8.5: 0,847, 1/27 720 und 0,987."""
    adjusted = holm({"H17.1": 0.847, "H17.2": 1 / 27720, "H17.3": 0.987})
    assert list(adjusted) == ["H17.1", "H17.2", "H17.3"]  # Folge der Eingabe
    # sortiert: H17.2 mal 3, H17.1 mal 2 (über 1 gekappt), H17.3 mal 1 (laufendes Maximum)
    assert adjusted["H17.2"].p_holm == pytest.approx(3 / 27720)
    assert adjusted["H17.1"].p_holm == 1.0
    assert adjusted["H17.3"].p_holm == 1.0
    assert [a.rejected for a in adjusted.values()] == [False, True, False]


def test_holm_steps_down_and_stops_at_the_first_failure() -> None:
    """m = 4, α = 0,05: Schwellen 0,0125, 0,0167, 0,025, 0,05; die dritte fällt, die vierte mit."""
    adjusted = holm({"a": 0.01, "b": 0.015, "c": 0.03, "d": 0.04})
    assert [round(a.p_holm, 6) for a in adjusted.values()] == [0.04, 0.045, 0.06, 0.06]
    assert [a.rejected for a in adjusted.values()] == [True, True, False, False]


def test_holm_gives_ties_the_same_adjusted_value() -> None:
    adjusted = holm({"x": 0.02, "y": 0.02, "z": 0.5})
    assert adjusted["x"].p_holm == adjusted["y"].p_holm == pytest.approx(0.06)
    assert adjusted["z"].p_holm == 0.5


def test_holm_with_one_hypothesis_is_the_test_itself() -> None:
    assert holm({"nur": 0.05})["nur"].p_holm == 0.05
    assert holm({"nur": 0.05})["nur"].rejected  # p <= α verwirft
    assert not holm({"nur": 0.0500001})["nur"].rejected


def test_holm_rejects_a_p_value_outside_the_unit_interval() -> None:
    with pytest.raises(Exception, match="p-Werte"):
        holm({"a": 1.5})


def test_family_words_the_result_and_marks_invalid_as_provisional() -> None:
    result = family({"H1": 0.001, "H2": 0.9, "H3": 0.002}, valid={"H3": False})
    assert result["H1"][0] == pytest.approx(0.003)
    assert result["H1"][1] == CONFIRMED
    assert result["H2"][0] == pytest.approx(0.9)
    assert result["H2"][1] == NOT_CONFIRMED
    # gültig erst mit validiertem Maß: Holm verwirft, das Ergebnis bleibt vorläufig
    assert result["H3"][1] == PROVISIONAL


def _rows() -> list[dict[str, object]]:
    adjusted = family({"H1": 0.001, "H2": 0.4})
    return [
        {
            "hypothese": "H1",
            "p": 0.001,
            "p_holm": adjusted["H1"][0],
            "ergebnis": adjusted["H1"][1],
            "n": 9,
            "festgelegt": "9c7b3d6",
            "rolle": "Haupttest",
        },
        {
            "hypothese": "H2",
            "p": 0.4,
            "p_holm": adjusted["H2"][0],
            "ergebnis": adjusted["H2"][1],
            "n": 9,
            "festgelegt": "9c7b3d6",
            "rolle": "Haupttest",
        },
        {
            "hypothese": "H1/S1",
            "p": 0.2,
            "p_holm": None,
            "ergebnis": None,
            "n": 9,
            "festgelegt": "9c7b3d6",
            "rolle": "Sensitivität",
        },
    ]


def test_the_frame_puts_the_core_first_and_extra_columns_behind() -> None:
    frame = hypothesis_frame(_rows(), {"rolle": pl.String()})
    assert list(frame.schema.items())[: len(CORE_SCHEMA)] == list(CORE_SCHEMA.items())
    assert frame.columns[-1] == "rolle"
    check_hypotheses(frame)


def test_a_sensitivity_has_neither_holm_nor_result() -> None:
    rows = _rows()
    rows[2]["ergebnis"] = CONFIRMED
    with pytest.raises(SchemaError, match="außerhalb der Familie"):
        check_hypotheses(hypothesis_frame(rows, {"rolle": pl.String()}))


def test_a_confirmed_result_needs_holm_to_reject() -> None:
    rows = _rows()
    rows[1]["ergebnis"] = CONFIRMED
    with pytest.raises(SchemaError, match="bestätigt"):
        check_hypotheses(hypothesis_frame(rows, {"rolle": pl.String()}))


def test_a_stored_holm_value_must_be_the_one_of_its_family() -> None:
    rows = _rows()
    rows[0]["p_holm"] = 0.001  # unkorrigiert statt Holm
    with pytest.raises(SchemaError, match="Holm"):
        check_hypotheses(hypothesis_frame(rows, {"rolle": pl.String()}))


def test_an_unknown_word_is_no_result() -> None:
    rows = _rows()
    rows[1]["ergebnis"] = "widerlegt"
    with pytest.raises(SchemaError, match="widerlegt"):
        check_hypotheses(hypothesis_frame(rows, {"rolle": pl.String()}))


def test_the_core_columns_must_stand_first_and_in_order() -> None:
    frame = hypothesis_frame(_rows(), {"rolle": pl.String()})
    swapped = frame.select("p", "hypothese", *frame.columns[2:])
    with pytest.raises(SchemaError, match="beginnt nicht"):
        check_hypotheses(swapped)


def test_two_rows_cannot_name_the_same_hypothesis() -> None:
    rows = _rows()
    rows[2]["hypothese"] = "H1"
    with pytest.raises(SchemaError, match="doppelt"):
        check_hypotheses(hypothesis_frame(rows, {"rolle": pl.String()}))


def test_an_extra_column_cannot_take_a_core_name() -> None:
    with pytest.raises(SchemaError, match="Namen des Kerns"):
        hypothesis_frame(_rows(), {"p": pl.Float64()})


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("p", 1.2, "liegt nicht in"),
        ("p", float("nan"), "liegt nicht in"),
        ("n", None, "n oder festgelegt"),
        ("festgelegt", None, "n oder festgelegt"),
        ("p_holm", 1.5, r"\[p, 1\]"),
    ],
)
def test_each_core_rule_names_its_row(column: str, value: object, message: str) -> None:
    rows = _rows()
    rows[1][column] = value
    with pytest.raises(SchemaError, match=message):
        check_hypotheses(hypothesis_frame(rows, {"rolle": pl.String()}))


def test_not_confirmed_needs_holm_to_keep() -> None:
    rows = _rows()
    rows[0]["ergebnis"] = NOT_CONFIRMED  # p_holm 0,002 verwirft
    with pytest.raises(SchemaError, match="obwohl Holm verwirft"):
        check_hypotheses(hypothesis_frame(rows, {"rolle": pl.String()}))
