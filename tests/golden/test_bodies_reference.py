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

from georep.analysis.bodies import (
    COUNCIL_HITS,
    COUNCIL_SHARE,
    DOCUMENTS,
    LOCAL_SHARE,
    OTHER,
    OWN,
    OWN_SHARE,
    UNITS,
    documents_by_body,
    hits_by_body,
)
from georep.crosswalk import DISTRICT, WEIGHT
from georep.prep.bodies import (
    ADVISORY,
    BODY,
    CITY_DISTRICT,
    COMMITTEE,
    COUNCIL,
    DISTRICT_BODY,
    ID,
    KIND,
    REFERENCE,
    UNKNOWN,
    BodyRules,
    classify_papers,
    counts_by_kind,
    summary,
)
from georep.prep.voters import ELIGIBLE, UNIT, district_units, read_results_csv
from georep.search.index import HITS, PAPER_IDS
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
# § 3.3: Lokalität je Bezirksvertretung, gerundet; mit Entscheidung 4 liegt BV10 bei rund 75 %
LOCALITY = {
    "BV1": 0.744,
    "BV2": 0.717,
    "BV3": 0.841,
    "BV4": 0.835,
    "BV5": 0.804,
    "BV6": 0.618,
    "BV7": 0.743,
    "BV8": 0.759,
    "BV9": 0.757,
    "BV10": 0.749,
}


def _reference_corpus(reference_root: Path) -> pl.DataFrame:
    items = json.loads((reference_root / "interim" / "paper_with_text.json").read_text("utf-8"))
    return pl.DataFrame(
        {
            ID: [str(i["id"]) for i in items],
            REFERENCE: [str(i["reference"]) for i in items],
        },
        schema={ID: pl.String, REFERENCE: pl.String},
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
    assert frame.get_column(BODY).null_count() == 0
    assert counts_by_kind(frame)[UNKNOWN] / frame.height == 0.0
    assert frame.get_column(BODY).n_unique() == 38
    bv = frame.filter(pl.col(KIND) == DISTRICT_BODY)
    assert dict(bv.group_by(BODY).len().iter_rows()) == BV_DOCUMENTS
    assert sorted(set(bv.get_column(CITY_DISTRICT))) == list(range(1, 11))
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


def _reference_results(reference_root: Path) -> pl.DataFrame:
    """Die Auswertung der Arbeit, wie sie eingefroren ist: ``paper_ids`` als ``;``-Liste."""
    frame = pl.read_csv(
        reference_root / "processed" / "wahlbezirke_auswertung.csv",
        infer_schema_length=None,
        schema_overrides={"paper_ids": pl.String},
    )
    return frame.with_columns(pl.col(PAPER_IDS).str.split(";"))


@pytest.mark.slow
def test_metrics_per_district_on_the_frozen_results(
    reference_root: Path, default_settings: Settings
) -> None:
    """Die Kennzahlen rechnen auf der Auswertung der Arbeit, nicht auf einem neuen Lauf."""
    columns = default_settings.columns.results
    rules = BodyRules.from_settings(default_settings.bodies)
    papers = classify_papers(_reference_corpus(reference_root), rules)
    results = _reference_results(reference_root)
    csv = read_results_csv(reference_root / "external" / "Stimmbezirk_Wahlergebnis.csv", columns)
    units = district_units(csv, columns)

    frame = hits_by_body(results, papers, units, columns.eligible)
    assert frame.height == 41
    assert int(frame.get_column(HITS).sum()) == 29_573  # Dokument-Bezirk-Paare der Arbeit
    assert int(frame.get_column(OWN).sum()) == 14_399
    first = frame.filter(pl.col(DISTRICT) == 1).row(0, named=True)
    assert (first[HITS], first[OWN], first[OTHER], first[COUNCIL_HITS]) == (1894, 599, 261, 300)
    # Wahlbezirk 40 liegt in zwei Stadtbezirken; beide Bezirksvertretungen zaehlen als eigene.
    forty = frame.filter(pl.col(DISTRICT) == 40).row(0, named=True)
    assert forty[UNITS] == [9, 10]  # nach Gewicht absteigend
    assert forty[OWN_SHARE] == pytest.approx(0.771, abs=5e-4)
    assert frame.get_column(OWN_SHARE).min() == pytest.approx(0.227, abs=5e-4)  # Bezirk 17
    assert frame.get_column(OWN_SHARE).max() == pytest.approx(0.771, abs=5e-4)  # Bezirk 40
    assert frame.get_column(OWN_SHARE).n_unique() == 41  # fuenf Kartenklassen sind moeglich
    assert frame.get_column(COUNCIL_SHARE).median() == pytest.approx(0.038, abs=5e-4)

    bodies = documents_by_body(papers, results, units)
    assert bodies.height == 38
    assert int(bodies.get_column(DOCUMENTS).sum()) == 19_108
    local = {
        row[BODY]: row[LOCAL_SHARE]
        for row in bodies.filter(pl.col(LOCAL_SHARE).is_not_null()).iter_rows(named=True)
    }
    assert set(local) == set(LOCALITY)
    for code, expected in LOCALITY.items():
        assert local[code] == pytest.approx(expected, abs=5e-4), code
