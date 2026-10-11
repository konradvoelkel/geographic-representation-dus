"""Golden Master der Gremien auf der vollen Referenz: die Zahlen aus docs/plans/05-gremien.md.

Diese Zahlen sind eingefroren: ändert eine Regel oder das Muster sie, muss das eine bewusste
Entscheidung sein (Option 05, Stufen A und B). Der Test liest nur die Referenz und rechnet, er
baut die Kette nicht nach; darum läuft er in Sekunden statt Minuten, trägt aber ``slow``, weil er
den ganzen Korpus liest.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from georep.crosswalk import DISTRICT, WEIGHT
from georep.prep.bodies import (
    ADVISORY,
    COMMITTEE,
    COUNCIL,
    DISTRICT_BODY,
    UNKNOWN,
    BodyRules,
    classify_papers,
    counts_by_kind,
    summary,
)
from georep.prep.voters import ELIGIBLE, UNIT, district_units, read_results_csv
from georep.settings import Settings

# docs/plans/05-gremien.md, § 3.1: Dokumente je Klasse auf der Referenz
KIND_COUNTS = {
    DISTRICT_BODY: 10_999,
    COUNCIL: 2_301,
    COMMITTEE: 5_360,
    ADVISORY: 448,
    UNKNOWN: 0,
}
BV_DOCUMENTS = {
    "BV1": 1_383,
    "BV2": 1_194,
    "BV3": 794,
    "BV4": 939,
    "BV5": 965,
    "BV6": 1_098,
    "BV7": 1_148,
    "BV8": 1_250,
    "BV9": 1_276,
    "BV10": 952,
}
PRECINCT_KEY = "Stimm-/ Wahlbezirk"


def _reference_corpus(reference_root: Path) -> pl.DataFrame:
    items = json.loads((reference_root / "interim" / "paper_with_text.json").read_text("utf-8"))
    return pl.DataFrame(
        {
            "id": [str(i["id"]) for i in items],
            "reference": [str(i["reference"]) for i in items],
        },
        schema={"id": pl.String, "reference": pl.String},
    )


@pytest.mark.slow
def test_every_reference_number_gets_a_body(
    reference_root: Path, default_settings: Settings
) -> None:
    rules = BodyRules.from_settings(default_settings.bodies)
    frame = classify_papers(_reference_corpus(reference_root), rules)
    assert frame.height == 19_108
    assert counts_by_kind(frame) == KIND_COUNTS
    # Das Muster trifft jede Nummer; "unbekannt" bleibt sichtbar, aber leer (Entscheidung 2).
    assert frame.get_column("gremium").null_count() == 0
    assert counts_by_kind(frame)[UNKNOWN] / frame.height == 0.0
    assert frame.get_column("gremium").n_unique() == 38
    bv = frame.filter(pl.col("gremium_art") == DISTRICT_BODY)
    assert dict(bv.group_by("gremium").len().iter_rows()) == BV_DOCUMENTS
    assert sorted(set(bv.get_column("stadtbezirk"))) == list(range(1, 11))
    assert summary(frame).startswith("19108 Dokumente: 10999 Bezirksvertretung")


@pytest.mark.slow
def test_city_districts_of_the_reference_match_the_geojson(
    reference_root: Path, default_settings: Settings
) -> None:
    columns = default_settings.columns.results
    csv = read_results_csv(reference_root / "external" / "Stimmbezirk_Wahlergebnis.csv", columns)
    pairs = {
        row["gebietnr"]: int(row[columns.city_district])
        for row in csv.iter_rows(named=True)
        if row[columns.city_district].strip().isdigit()
    }
    features = json.loads(
        (reference_root / "external" / "Stimmbezirke_2025.geojson").read_text("utf-8")
    )["features"]
    assert len(features) == 306
    agree = [
        pairs.get(str(f["properties"][PRECINCT_KEY])) == int(f["properties"]["Stadtbezirk Nr."])
        for f in features
    ]
    assert agree.count(True) == 306  # beide Quellen decken sich für jeden Stimmbezirk

    weights = district_units(csv, columns)
    assert weights.height == 42 and weights.get_column(DISTRICT).n_unique() == 41
    # Nur Wahlbezirk 40 liegt in zwei Stadtbezirken (Plan, Entscheidung 4 und Fußnote der Seite).
    multiple = weights.group_by(DISTRICT).len().filter(pl.col("len") > 1)
    assert multiple.get_column(DISTRICT).to_list() == [40]
    forty = weights.filter(pl.col(DISTRICT) == 40).sort(UNIT)
    assert forty.get_column(UNIT).to_list() == [9, 10]
    assert forty.get_column(ELIGIBLE).to_list() == [8_136, 4_430]
    assert forty.get_column(WEIGHT).to_list() == pytest.approx([0.6475, 0.3525], abs=1e-4)
    assert weights.filter(pl.col(DISTRICT) != 40).get_column(WEIGHT).to_list() == [1.0] * 40
