"""Kennzahlen je Wahlbezirk und je Gremium: Mini-Fixture, Handbeispiele, Verträge."""

from __future__ import annotations

import deal
import polars as pl
import pytest

from georep.analysis.bodies import (
    ADVISORY_HITS,
    BODY_COLUMNS,
    COMMITTEE_HITS,
    COUNCIL_HITS,
    COUNCIL_SHARE,
    DISTRICT_BODY_COLUMNS,
    DOCUMENTS,
    LOCAL_SHARE,
    NO_BODY,
    OTHER,
    OWN,
    OWN_RATE,
    OWN_SHARE,
    UNITS,
    UNKNOWN_HITS,
    WITH_HITS,
    documents_by_body,
    hits_by_body,
    regression_frame,
    summary,
)
from georep.errors import SchemaError
from georep.layout import Layout
from georep.prep.bodies import (
    ADVISORY,
    BODY,
    CITY_DISTRICT,
    COMMITTEE,
    COUNCIL,
    DISTRICT_BODY,
    ID,
    KIND,
    UNKNOWN,
    BodyRules,
    classify_papers,
)
from georep.prep.voters import district_units, read_results_csv
from georep.settings import Settings

ELIGIBLE = "Wahlberechtigte_insgesamt"


def _papers(rows: list[tuple[str, str | None, str, int | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            ID: [r[0] for r in rows],
            BODY: [r[1] for r in rows],
            KIND: [r[2] for r in rows],
            CITY_DISTRICT: [r[3] for r in rows],
        },
        schema={ID: pl.String, BODY: pl.String, KIND: pl.String, CITY_DISTRICT: pl.Int64},
    )


def _units(rows: list[tuple[int, int, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "wahlkreis_id": [r[0] for r in rows],
            CITY_DISTRICT: [r[1] for r in rows],
            "wahlberechtigte": [1000 for _ in rows],
            "gewicht": [r[2] for r in rows],
        }
    )


def _results(rows: list[tuple[int, list[str], int]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "wahlkreis_id": [r[0] for r in rows],
            "paper_ids": [r[1] for r in rows],
            "anzahl_treffer": [len(r[1]) for r in rows],
            ELIGIBLE: [r[2] for r in rows],
            "wahlbeteiligung": [0.5 for _ in rows],
        }
    )


# --- Handbeispiele -------------------------------------------------------------------------------


def test_own_district_body_for_a_district_in_two_city_districts() -> None:
    """Wie Wahlbezirk 40: BV9 und BV10 zählen beide als eigene (fragen.md 5.1)."""
    papers = _papers(
        [
            ("a", "BV9", DISTRICT_BODY, 9),
            ("b", "BV10", DISTRICT_BODY, 10),
            ("c", "BV3", DISTRICT_BODY, 3),
            ("d", "RAT", COUNCIL, None),
            ("e", "OVA", COMMITTEE, None),
            ("f", "JURAT", ADVISORY, None),
            ("g", "XYZ", UNKNOWN, None),
        ]
    )
    # Absichtlich in der „falschen" Reihenfolge: die Ausgabe sortiert selbst nach Gewicht.
    units = _units([(40, 10, 0.353), (40, 9, 0.647)])
    results = _results([(40, ["a", "b", "c", "d", "e", "f", "g"], 1000)])
    frame = hits_by_body(results, papers, units, ELIGIBLE)
    assert frame.columns == DISTRICT_BODY_COLUMNS
    row = frame.row(0, named=True)
    assert row[UNITS] == [9, 10]  # nach Gewicht absteigend, der Hauptstadtbezirk vorn
    assert (row[OWN], row[OTHER]) == (2, 1)
    assert (row[COUNCIL_HITS], row[COMMITTEE_HITS], row[ADVISORY_HITS], row[UNKNOWN_HITS]) == (
        1,
        1,
        1,
        1,
    )
    assert row[OWN_SHARE] == pytest.approx(2 / 7)
    assert row[COUNCIL_SHARE] == pytest.approx(1 / 7)
    assert row[OWN_RATE] == pytest.approx(2 / 1000)


def test_a_district_without_hits_keeps_every_class_at_zero() -> None:
    papers = _papers([("a", "BV1", DISTRICT_BODY, 1)])
    units = _units([(1, 1, 1.0), (2, 2, 1.0)])
    results = _results([(1, ["a"], 500), (2, [], 400)])
    frame = hits_by_body(results, papers, units, ELIGIBLE)
    # Genau ein Treffer ist die Grenze des „mehr als null Treffer" in der Anteilsrechnung.
    single = frame.filter(pl.col("wahlkreis_id") == 1).row(0, named=True)
    assert single["anzahl_treffer"] == 1 and single[OWN] == 1
    assert single[OWN_SHARE] == 1.0 and single[COUNCIL_SHARE] == 0.0
    empty = frame.filter(pl.col("wahlkreis_id") == 2).row(0, named=True)
    assert [empty[c] for c in (OWN, OTHER, COUNCIL_HITS, COMMITTEE_HITS)] == [0, 0, 0, 0]
    # Ohne Treffer ist der Anteil 0, nicht null und keine Division durch 0.
    assert empty[OWN_SHARE] == 0.0 and empty[COUNCIL_SHARE] == 0.0 and empty[OWN_RATE] == 0.0
    assert empty[UNITS] == [2]
    assert frame.get_column("wahlkreis_id").to_list() == [1, 2]


def test_no_district_has_hits_at_all() -> None:
    """Ohne jeden Treffer ist ``paper_ids`` eine Spalte aus leeren Listen, also List(Null)."""
    papers = _papers([("a", "BV1", DISTRICT_BODY, 1)])
    units = _units([(1, 1, 1.0)])
    results = _results([(1, [], 500), (2, [], 400)])
    assert results.schema["paper_ids"] == pl.List(pl.Null)  # der Fall, den hypothesis fand
    frame = hits_by_body(results, papers, units, ELIGIBLE)
    assert frame.get_column(OWN).to_list() == [0, 0]
    assert documents_by_body(papers, results, units).get_column(WITH_HITS).to_list() == [0]


def test_a_hit_on_a_document_without_a_body_row_is_a_schema_error() -> None:
    papers = _papers([("a", "BV1", DISTRICT_BODY, 1)])
    units = _units([(1, 1, 1.0)])
    results = _results([(1, ["a", "fehlt"], 500)])
    with pytest.raises(SchemaError, match="fehlt"):
        hits_by_body(results, papers, units, ELIGIBLE)


def test_zero_eligible_voters_violate_the_precondition() -> None:
    papers = _papers([("a", "BV1", DISTRICT_BODY, 1)])
    units = _units([(1, 1, 1.0)])
    results = _results([(1, ["a"], 0)])
    with pytest.raises(deal.PreContractError):
        hits_by_body(results, papers, units, ELIGIBLE)


def test_locality_per_body_counts_hits_in_its_own_city_district() -> None:
    papers = _papers(
        [
            ("a", "BV9", DISTRICT_BODY, 9),
            ("b", "BV9", DISTRICT_BODY, 9),
            ("c", "BV9", DISTRICT_BODY, 9),  # ohne Treffer
            ("d", "RAT", COUNCIL, None),
            ("e", None, UNKNOWN, None),
        ]
    )
    units = _units([(35, 9, 1.0), (17, 3, 1.0)])
    results = _results([(35, ["a", "d"], 500), (17, ["a", "b", "e"], 600)])
    frame = documents_by_body(papers, results, units)
    assert frame.columns == BODY_COLUMNS
    by_code = {row[BODY]: row for row in frame.iter_rows(named=True)}
    assert set(by_code) == {"BV9", "RAT", NO_BODY}  # das Kürzel null wird der leere String
    bv = by_code["BV9"]
    assert (bv[DOCUMENTS], bv[WITH_HITS]) == (3, 2)
    # Paare: a in 35 (eigen), a in 17 (fremd), b in 17 (fremd) -> 1 von 3
    assert bv[LOCAL_SHARE] == pytest.approx(1 / 3)
    assert by_code["RAT"][LOCAL_SHARE] is None  # kein eigener Stadtbezirk
    assert (by_code[NO_BODY][DOCUMENTS], by_code[NO_BODY][WITH_HITS]) == (1, 1)
    assert int(frame.get_column(DOCUMENTS).sum()) == papers.height


def test_a_body_without_hits_has_no_locality() -> None:
    papers = _papers([("a", "BV1", DISTRICT_BODY, 1), ("b", "BV2", DISTRICT_BODY, 2)])
    units = _units([(1, 1, 1.0)])
    results = _results([(1, ["a"], 500)])
    frame = documents_by_body(papers, results, units)
    by_code = {row[BODY]: row for row in frame.iter_rows(named=True)}
    assert by_code["BV1"][LOCAL_SHARE] == pytest.approx(1.0)
    assert by_code["BV2"][WITH_HITS] == 0 and by_code["BV2"][LOCAL_SHARE] is None


def test_regression_frame_carries_the_metrics_and_the_turnout() -> None:
    papers = _papers([("a", "BV1", DISTRICT_BODY, 1)])
    units = _units([(1, 1, 1.0)])
    results = _results([(1, ["a"], 500)])
    districts = hits_by_body(results, papers, units, ELIGIBLE)
    frame = regression_frame(districts, results)
    assert frame.columns == ["wahlkreis_id", OWN_SHARE, OWN_RATE, "wahlbeteiligung"]
    assert frame.height == 1


# --- Mini-Fixture --------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def mini_bodies(mini_run: Layout, default_settings: Settings) -> pl.DataFrame:
    rules = BodyRules.from_settings(default_settings.bodies)
    return classify_papers(pl.read_parquet(mini_run.corpus, columns=[ID, "reference"]), rules)


@pytest.fixture(scope="module")
def mini_units(mini_run: Layout, default_settings: Settings) -> pl.DataFrame:
    columns = default_settings.columns.results
    return district_units(read_results_csv(mini_run.results_csv, columns), columns)


def test_mini_fixture_matches_the_frozen_numbers(
    mini_run: Layout, mini_bodies: pl.DataFrame, mini_units: pl.DataFrame
) -> None:
    """docs/plans/05-gremien.md, § 3.3: je Wahlbezirk (Treffer, eigene BV, andere BV, Rat)."""
    results = pl.read_parquet(mini_run.results)
    frame = hits_by_body(results, mini_bodies, mini_units, ELIGIBLE)
    got = {
        row["wahlkreis_id"]: (row["anzahl_treffer"], row[OWN], row[OTHER], row[COUNCIL_HITS])
        for row in frame.iter_rows(named=True)
    }
    # Eigene Zahlen dieses Repos, nicht die der Arbeit: sie sind am 2026-10-12 mit Regel 1
    # („Einrichtung mit Stadtnamen", decisions.md Punkt 44) gesunken, weil der Mini-Fixture 37
    # Labels wie „Kunstakademie Düsseldorf" aus dem Wörterbuch fallen (1: 96 -> 89, 10: 63 -> 59).
    assert got == {1: (89, 26, 13, 9), 10: (59, 22, 10, 4), 38: (14, 9, 0, 0)}
    assert frame.get_column(UNITS).to_list() == [[1], [2], [9]]
    # Der Bezirk 38 hat keine Rats-Treffer: die Spalte bleibt, der Wert ist 0.
    assert frame.filter(pl.col("wahlkreis_id") == 38).row(0, named=True)[COUNCIL_SHARE] == 0.0
    assert frame.get_column(OWN_SHARE).n_unique() == 3  # drei Kartenklassen sind möglich
    assert "41 Wahlbezirke" not in summary(frame, mini_bodies)


def test_mini_fixture_body_table(
    mini_run: Layout, mini_bodies: pl.DataFrame, mini_units: pl.DataFrame
) -> None:
    results = pl.read_parquet(mini_run.results)
    frame = documents_by_body(mini_bodies, results, mini_units)
    assert int(frame.get_column(DOCUMENTS).sum()) == 200
    assert frame.get_column(BODY).is_sorted() and frame.get_column(BODY).n_unique() == frame.height
    kinds = dict(frame.group_by(KIND).agg(pl.col(DOCUMENTS).sum()).iter_rows())
    assert kinds == {DISTRICT_BODY: 93, COUNCIL: 16, COMMITTEE: 86, ADVISORY: 5}
    local = frame.filter(pl.col(LOCAL_SHARE).is_not_null())
    assert set(local.get_column(KIND)) == {DISTRICT_BODY}
    assert bool(((local.get_column(LOCAL_SHARE) >= 0) & (local.get_column(LOCAL_SHARE) <= 1)).all())


def test_summary_names_districts_bodies_and_own_hits(
    mini_run: Layout, mini_bodies: pl.DataFrame, mini_units: pl.DataFrame
) -> None:
    results = pl.read_parquet(mini_run.results)
    districts = hits_by_body(results, mini_bodies, mini_units, ELIGIBLE)
    bodies = documents_by_body(mini_bodies, results, mini_units)
    line = summary(districts, bodies)
    assert line.startswith("3 Wahlbezirke, ")
    assert f"{26 + 22 + 9} von {89 + 59 + 14} Treffern" in line
