"""Vorhaben 16, kleine Stufe 3: zwei Zeilen in „Was ändert die Gewichtung?" (``report.places``).

Die Zeile ``ortsbezug`` sagt, dass Nebenregel C an 100 frischen Paaren bestätigt ist und trotzdem
nicht besser trennt als alle Treffer; ``stelle`` heißt explorativ und nennt die Gewichte aus dem
Profil (Messdokument ``docs/plans/16-ortsbezug.md``, § 7 mit § 10, Punkt 6). Die beiden F1 trägt
``guete.json`` nicht; sie stehen als Konstanten in ``report.places`` und werden hier aus den
Labels im Repo nachgerechnet (``validierung/16-ortsbezug-2-f4/``, die Ausgabe des Verfahrens aus
``validierung/16-ortsbezug/verfahren.csv``), wie es das Messskript tut (``f1_weighted``).
"""

from __future__ import annotations

import csv
from pathlib import Path

import polars as pl

from georep.analysis.weights import ORTSBEZUG, STELLE, UNIT
from georep.report.model import sensitivity_rows
from georep.report.places import CONFIRMATION, variant_texts
from georep.settings import PlacesSettings, Weights

REPO = Path(__file__).resolve().parents[2]
ROUND_2 = REPO / "validierung" / "16-ortsbezug-2-f4"
VERFAHREN = REPO / "validierung" / "16-ortsbezug" / "verfahren.csv"


def _weighted() -> pl.DataFrame:
    rows = [
        (district, name, hits, hits / 100.0)
        for name, scale in ((UNIT, 1.0), (ORTSBEZUG, 0.8), (STELLE, 0.9), ("bezirke", 0.5))
        for district, hits in ((1, 10.0 * scale), (2, 20.0 * scale), (3, 15.0 * scale))
    ]
    return pl.DataFrame(
        rows,
        schema={
            "wahlkreis_id": pl.Int64,
            "variante": pl.String,
            "anzahl_treffer_gewichtet": pl.Float64,
            "trefferquote_gewichtet": pl.Float64,
        },
        orient="row",
    )


def _results() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3],
            "wahlbeteiligung": [0.4, 0.5, 0.6],
            "trefferquote": [0.1, 0.2, 0.15],
        }
    )


def test_the_two_rows_follow_the_fixed_ones_with_their_sentences() -> None:
    rows = sensitivity_rows(_weighted(), _results(), Weights(), places=PlacesSettings())
    assert [row.name for row in rows] == [UNIT, "bezirke", ORTSBEZUG, STELLE]
    texts = {row.name: (row.label, row.description) for row in rows}
    label, description = texts[ORTSBEZUG]
    assert label == "Ortsbezug"
    assert "bestätigt an 100 Paaren (F1 0,83)" in description
    assert "trennt aber nicht besser als alle Treffer (F1 0,88)" in description
    label, description = texts[STELLE]
    assert label == "nach Stelle" and "explorativ" in description
    assert "Begleittext 0,5" in description and "Rest 0,25" in description


def test_the_weights_of_the_profile_name_the_row() -> None:
    places = PlacesSettings(
        position_weights={
            "titel": 1.0,
            "betreff": 1.0,
            "kern": 0.75,
            "begleittext": 0.5,
            "rest": 0.0,
        }
    )
    _, description = variant_texts(places)[STELLE]
    assert "Kern 0,75" in description and "Rest 0" in description


def _f1(rows: list[tuple[bool, bool, float]]) -> float:
    """Das F1 der Klasse „handelt von", hochgerechnet mit den Schichtgewichten (Messskript)."""
    tp = sum(w for truth, said, w in rows if truth and said)
    fp = sum(w for truth, said, w in rows if not truth and said)
    fn = sum(w for truth, said, w in rows if truth and not said)
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    return 2 * precision * recall / (precision + recall)


def test_the_confirmation_is_recomputed_from_the_labels_in_the_repo() -> None:
    with (ROUND_2 / "stichprobe.csv").open(encoding="utf-8") as handle:
        strata = {row["id"]: row["schicht"] for row in csv.DictReader(handle)}
    with (ROUND_2 / "stichprobe.csv").open(encoding="utf-8") as handle:
        sizes = {row["schicht"]: int(row["schicht_n"]) for row in csv.DictReader(handle)}
    drawn = {s: list(strata.values()).count(s) for s in sizes}
    with (ROUND_2 / "labels.csv").open(encoding="utf-8") as handle:
        labels = {
            row["id"]: row["label"] == "handelt_von"
            for row in csv.DictReader(handle)
            if row["frage"] == "bezug"
        }
    with VERFAHREN.open(encoding="utf-8") as handle:
        said = {row["aufgabe"]: row["ortsbezug"] == "true" for row in csv.DictReader(handle)}
    rows = [
        (labels[task], said[task], sizes[strata[task]] / drawn[strata[task]]) for task in strata
    ]
    assert len(rows) == CONFIRMATION.units == 100
    assert round(_f1(rows), 3) == CONFIRMATION.f1 == 0.828
    assert round(_f1([(truth, True, w) for truth, _, w in rows]), 3) == CONFIRMATION.trivial_f1
    assert CONFIRMATION.trivial_f1 == 0.878
