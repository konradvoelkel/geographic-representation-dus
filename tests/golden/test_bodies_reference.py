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
    CONSULTATION,
    CONSULTATION_COUNT,
    COUNCIL,
    DISTRICT_BODY,
    FROM_CONSULTATION,
    FROM_NUMBER,
    ID,
    KIND,
    REFERENCE,
    SOURCE,
    UNKNOWN,
    BodyRules,
    classify_papers,
    counts_by_kind,
    source_counts,
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


# Punkt 57: die Nummernform vor 2019 im Paket der Wahlperiode 2014 bis 2020. Die Zahlen sind
# gemessen am 2026-10-14 und eingefroren; ändert ein Muster oder die Aliastabelle sie, ist das eine
# Entscheidung. „vorher" heißt: nur mit reference_pattern, ohne bodies.aliases.
PERIOD_PACKAGE = Path(__file__).resolve().parents[2] / "snapshots" / "2014-2020"
PERIOD_DOCUMENTS = 22_215
PERIOD_BEFORE = {
    DISTRICT_BODY: 2_539,
    COUNCIL: 338,
    COMMITTEE: 1_193,
    ADVISORY: 75,
    UNKNOWN: 18_070,
}
PERIOD_AFTER = {
    DISTRICT_BODY: 13_244,  # 2 539 + 10 705 aus der alten Nummernform
    COUNCIL: 338,
    COMMITTEE: 1_193,
    ADVISORY: 75,
    UNKNOWN: 7_365,  # 7 313 Amtsnummern plus 52 Nummern mit Kürzel ohne Tabelle
}


def _period_corpus() -> pl.DataFrame:
    """Die Metadaten des Pakets, wie ``bootstrap`` sie kopiert (eine JSON-Zeile je Paper)."""
    rows = [
        json.loads(line)
        for line in (PERIOD_PACKAGE / "raw" / "papers.jsonl").read_text("utf-8").splitlines()
    ]
    return pl.DataFrame(
        {
            ID: [str(r["id"]) for r in rows],
            REFERENCE: [str(r.get("reference") or "") for r in rows],
        },
        schema={ID: pl.String, REFERENCE: pl.String},
    )


@pytest.mark.slow
def test_the_old_numbering_of_the_period_yields_its_district_bodies(
    default_settings: Settings,
) -> None:
    """Die zehn Köpfe ``170`` bis ``179`` holen 10 705 Dokumente aus „unbekannt" heraus.

    Die Hauptperiode ist davon unberührt (der Test oben): dort trifft das Muster jede Nummer, und
    die Aliastabelle wird nur befragt, wenn es nicht trifft.
    """
    bodies = default_settings.bodies
    assert sorted(bodies.aliases) == [str(170 + n) for n in range(10)]
    frame = classify_papers(_period_corpus(), BodyRules.from_settings(bodies))
    assert frame.height == PERIOD_DOCUMENTS
    assert counts_by_kind(frame) == PERIOD_AFTER
    without = classify_papers(
        _period_corpus(), BodyRules.from_settings(bodies.model_copy(update={"aliases": {}}))
    )
    assert counts_by_kind(without) == PERIOD_BEFORE
    recovered = PERIOD_BEFORE[UNKNOWN] - PERIOD_AFTER[UNKNOWN]
    assert recovered == 10_705 and PERIOD_AFTER[UNKNOWN] / PERIOD_DOCUMENTS < 0.34
    # Jeder der zehn Stadtbezirke kommt vor, und keine andere Klasse ändert sich
    gained = frame.filter(pl.col(KIND) == DISTRICT_BODY).join(
        without.filter(pl.col(KIND) == DISTRICT_BODY), on=ID, how="anti"
    )
    assert gained.height == recovered
    assert sorted(set(gained.get_column(CITY_DISTRICT))) == list(range(1, 11))
    assert set(gained.get_column(BODY)) == {f"BV{n}" for n in range(1, 11)}


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


# --- Punkt 58: die Beratungsfolge als zweite Quelle, auf den echten Daten ----------------------

# Gemessen am 2026-10-14 mit der Tabelle [bodies.organizations] des Profils (36 Einträge, gelernt
# mit `georep learn-bodies`, Reinheit 99,1 %). Die Zahlen sind eingefroren: ändert eine Zeile der
# Tabelle oder die Regel sie, ist das eine Entscheidung und keine Überraschung.
MAIN_CONSULTATION = {"ergaenzt": 0, "bestaetigt": 16_902, "widerspruch": 145, "mehrdeutig": 0}
PERIOD_CONSULTATION = {
    "ergaenzt": 5_469,
    "bestaetigt": 14_419,
    "widerspruch": 30,
    "mehrdeutig": 1_541,
}
PERIOD_WITH_CONSULTATION = {
    DISTRICT_BODY: 13_245,  # 13 244 aus der Nummer plus eines aus der Folge
    COUNCIL: 1_664,  # 338 plus 1 326
    COMMITTEE: 4_814,  # 1 193 plus 3 621
    ADVISORY: 596,  # 75 plus 521
    UNKNOWN: 1_896,  # 7 365 minus 5 469; 8,5 % statt 33,2 %
}
PACKAGE = Path(__file__).resolve().parents[2] / "snapshots" / "duesseldorf-beratungsfolge"


def _consultation_of_jsonl(path: Path) -> pl.DataFrame:
    """``id`` und ``consultation_organizations`` aus einer ``papers.jsonl``, wie der Korpus sie trägt."""
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]
    return pl.DataFrame(
        {
            ID: [str(r["id"]) for r in rows],
            CONSULTATION: [[str(o) for o in (r.get(CONSULTATION) or ())] for r in rows],
        },
        schema={ID: pl.String, CONSULTATION: pl.List(pl.String)},
    )


@pytest.mark.slow
def test_the_consultation_confirms_the_numbers_of_the_main_period(
    reference_root: Path, default_settings: Settings
) -> None:
    """Punkt 58: in der Hauptperiode trifft die Nummer jede Zeile; die Folge ist die Gegenprobe.

    Sie bestätigt 16 903 von 17 049 Zuordnungen mit eindeutiger Folge und widerspricht 146 (0,9 %)
    -- und ändert keine einzige, weil die Nummer entscheidet. Die 146 sind keine Fehler des
    Parsers: sechs Kürzel teilen ihre Organisation mit einem anderen (GLA und RPAU mit dem Rat,
    BAU mit SEBD), und die Folge kann sie darum nicht auseinanderhalten.
    """
    rules = BodyRules.from_settings(default_settings.bodies)
    assert len(default_settings.bodies.organizations) == 36
    folge = pl.read_parquet(PACKAGE / "raw" / "beratungsfolge.parquet").select(ID, CONSULTATION)
    corpus = _reference_corpus(reference_root)
    frame = classify_papers(corpus, rules, folge)
    assert frame.height == 19_108
    assert counts_by_kind(frame) == KIND_COUNTS  # die Nummer entscheidet: nichts ändert sich
    counts = source_counts(frame)
    assert dict(counts.per_source)[FROM_NUMBER] == 19_108
    assert dict(counts.per_source)[FROM_CONSULTATION] == MAIN_CONSULTATION["ergaenzt"]
    assert counts.confirmed == MAIN_CONSULTATION["bestaetigt"]
    assert counts.conflicting == MAIN_CONSULTATION["widerspruch"]
    assert counts.ambiguous == MAIN_CONSULTATION["mehrdeutig"]
    # Das Paket trägt ein Dokument mehr als die Referenz (KUA/023/2026); der Korpus entscheidet.
    assert pl.read_parquet(PACKAGE / "raw" / "beratungsfolge.parquet").height == 19_109


@pytest.mark.slow
def test_the_consultation_halves_the_unknown_bodies_of_the_old_period(
    default_settings: Settings,
) -> None:
    """Punkt 58, die Hauptwirkung: „unbekannt" fällt in der Periode 2014 bis 2020 auf 8,5 %.

    5 469 der 7 365 Dokumente ohne Gremium bekommen eines, weil ihre Beratungsfolge genau **eine
    Organisation** nennt; 1 541 bleiben unbekannt, weil sie mehrere nennt (dazu der Modulkopf von
    ``georep.prep.bodies``), die übrigen 325 haben keine Folge oder eine Organisation, die die
    Tabelle nicht kennt. Bei den Dokumenten mit Kürzel und eindeutiger Folge sind 14 419 bestätigt
    und 30 widersprochen (0,2 %).
    """
    rules = BodyRules.from_settings(default_settings.bodies)
    folge = _consultation_of_jsonl(PERIOD_PACKAGE / "raw" / "papers.jsonl")
    assert int((folge.get_column(CONSULTATION).list.len() > 0).sum()) == 22_066
    frame = classify_papers(_period_corpus(), rules, folge)
    assert frame.height == PERIOD_DOCUMENTS
    assert counts_by_kind(frame) == PERIOD_WITH_CONSULTATION
    unknown = PERIOD_WITH_CONSULTATION[UNKNOWN]
    assert unknown / PERIOD_DOCUMENTS < 0.086 and PERIOD_AFTER[UNKNOWN] / PERIOD_DOCUMENTS > 0.33
    counts = source_counts(frame)
    assert dict(counts.per_source)[FROM_CONSULTATION] == PERIOD_CONSULTATION["ergaenzt"]
    assert counts.confirmed == PERIOD_CONSULTATION["bestaetigt"]
    assert counts.conflicting == PERIOD_CONSULTATION["widerspruch"]
    assert counts.ambiguous == PERIOD_CONSULTATION["mehrdeutig"]
    assert PERIOD_AFTER[UNKNOWN] - unknown == PERIOD_CONSULTATION["ergaenzt"]
    # Jede ergänzte Zeile trägt ihr Kürzel und, bei einer Bezirksvertretung, ihren Stadtbezirk
    added = frame.filter(pl.col(SOURCE) == FROM_CONSULTATION)
    assert added.height == PERIOD_CONSULTATION["ergaenzt"]
    assert added.get_column(BODY).null_count() == 0
    assert set(added.get_column(KIND)) <= {DISTRICT_BODY, COUNCIL, COMMITTEE, ADVISORY}
    assert added.get_column(CONSULTATION_COUNT).to_list() == [1] * added.height
