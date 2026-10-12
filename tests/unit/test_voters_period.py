"""Wählerzahlen eines älteren Zuschnitts: Stimmbezirke lesen, Briefwahl verteilen, übertragen.

Alle Zahlen hier sind von Hand gerechnet. Der Aufbau folgt dem Format der Ratswahl 2020
(``A`` Wahlberechtigte, ``A2`` davon mit Wahlschein, ``B`` Wähler, ``D1`` bis ``Dn`` Stimmen,
keine Wahlbezirksspalte, Briefwahlbezirke mit ``A`` = 0), nur klein: zwei Wahlbezirke, drei
Urnenstimmbezirke, zwei Briefwahlbezirke, zwei Parteien.
"""

from __future__ import annotations

import deal
import polars as pl
import pytest

from georep.crosswalk import SHARE, SOURCE, TARGET, transfer_counts
from georep.errors import SchemaError
from georep.prep.voters import (
    ELIGIBLE_POSTAL,
    ELIGIBLE_TOTAL,
    PRECINCT,
    SOURCE_DISTRICT,
    TURNOUT,
    VOTERS,
    check_postal_total,
    count_columns,
    district_results,
    precinct_counts,
    spread_postal,
    with_shares,
)
from georep.settings import ResultsColumns

COLUMNS = ResultsColumns(
    sep=";",
    encoding="utf-8",
    district="",
    city_district="",
    precinct="gebiet-nr",
    precinct_name="gebiet-name",
    eligible="A",
    voters="B",
    eligible_postal="A2",
    postal_marker="Briefwahlbezirk",
    parties={"CDU": "D1", "SPD": "D2"},
)
ASSIGNMENT = {"0101": 1, "0102": 1, "0201": 2}
CDU, SPD = "CDU_Stimmen", "SPD_Stimmen"


def _renamed(rows: list[tuple[str, str, int, int, int, int, int]]) -> pl.DataFrame:
    """Die Ergebnis-CSV, wie ``read_results_csv`` sie liefert: kanonische Namen, Werte als Text."""
    names = ["gebiet-nr", "gebiet-name", ELIGIBLE_TOTAL, ELIGIBLE_POSTAL, VOTERS, CDU, SPD]
    return pl.DataFrame(
        {name: [str(row[i]) for row in rows] for i, name in enumerate(names)},
        schema=dict.fromkeys(names, pl.String),
    )


PRECINCT_ROWS = [
    ("0101", "0101 Schule", 100, 30, 50, 30, 20),
    ("0102", "0102 Schule", 200, 20, 100, 60, 40),
    ("0190", "0190 Briefwahlbezirk", 0, 0, 40, 24, 16),
    ("0201", "0201 Turnhalle", 300, 50, 150, 90, 60),
    ("0290", "0290 Briefwahlbezirk", 0, 0, 30, 18, 12),
]
DISTRICT_ROWS = [
    ("001", "001 Nord", 300, 50, 190, 114, 76),
    ("002", "002 Sued", 300, 50, 180, 108, 72),
]


def test_precinct_counts_separate_the_postal_districts() -> None:
    found = precinct_counts(_renamed(PRECINCT_ROWS), COLUMNS)
    assert found.urn.get_column(PRECINCT).to_list() == ["0101", "0102", "0201"]
    assert found.postal.get_column(PRECINCT).to_list() == ["0190", "0290"]
    assert found.urn.get_column(ELIGIBLE_TOTAL).to_list() == [100, 200, 300]
    assert found.urn.get_column(ELIGIBLE_POSTAL).to_list() == [30, 20, 50]
    assert int(found.postal.get_column(ELIGIBLE_TOTAL).sum()) == 0
    assert found.urn.schema[VOTERS] == pl.Int64


def test_precinct_counts_refuse_duplicate_numbers() -> None:
    doubled = [*PRECINCT_ROWS, ("0101", "0101 noch mal", 1, 1, 1, 1, 1)]
    with pytest.raises(SchemaError, match="doppelt"):
        precinct_counts(_renamed(doubled), COLUMNS)


def test_district_results_sum_per_district() -> None:
    frame = district_results(_renamed(DISTRICT_ROWS), COLUMNS)
    assert frame.get_column(SOURCE_DISTRICT).to_list() == [1, 2]
    assert frame.get_column(VOTERS).to_list() == [190, 180]


def test_spread_postal_distributes_by_the_postal_eligible_and_keeps_the_sums() -> None:
    urn = precinct_counts(_renamed(PRECINCT_ROWS), COLUMNS).urn
    districts = district_results(_renamed(DISTRICT_ROWS), COLUMNS)
    counts = count_columns(COLUMNS)
    complete = spread_postal(urn, ASSIGNMENT, districts, counts)
    assert complete.get_column(PRECINCT).to_list() == ["0101", "0102", "0201"]
    # Bezirk 1: 40 Briefwähler im Verhältnis 30 zu 20, also 24 und 16
    assert complete.get_column(VOTERS).to_list() == [74, 116, 180]
    # 24 CDU-Stimmen im Verhältnis 30 zu 20 sind 14,4 und 9,6: der groessere Rest bekommt die Eins
    assert complete.get_column(CDU).to_list() == [44, 70, 108]
    assert complete.get_column(SPD).to_list() == [30, 46, 72]
    # Die Wahlberechtigten bleiben unberührt, sie stehen ganz bei den Urnenstimmbezirken
    assert complete.get_column(ELIGIBLE_TOTAL).to_list() == [100, 200, 300]
    for column in counts:
        assert int(complete.get_column(column).sum()) == int(districts.get_column(column).sum())


def test_spread_postal_names_a_mismatch_in_the_eligible_voters() -> None:
    urn = precinct_counts(_renamed(PRECINCT_ROWS), COLUMNS).urn
    wrong = district_results(
        _renamed([("001", "001 Nord", 299, 50, 190, 114, 76), DISTRICT_ROWS[1]]), COLUMNS
    )
    with pytest.raises(SchemaError, match="passt nicht zur Wahlbezirks-CSV"):
        spread_postal(urn, ASSIGNMENT, wrong, count_columns(COLUMNS))


def test_spread_postal_refuses_more_urn_votes_than_the_district_reports() -> None:
    urn = precinct_counts(_renamed(PRECINCT_ROWS), COLUMNS).urn
    fewer = district_results(
        _renamed([("001", "001 Nord", 300, 50, 100, 114, 76), DISTRICT_ROWS[1]]), COLUMNS
    )
    with pytest.raises(SchemaError, match="Mehr Urnenstimmen"):
        spread_postal(urn, ASSIGNMENT, fewer, count_columns(COLUMNS))


def test_spread_postal_needs_an_assignment_over_exactly_these_precincts() -> None:
    urn = precinct_counts(_renamed(PRECINCT_ROWS), COLUMNS).urn
    districts = district_results(_renamed(DISTRICT_ROWS), COLUMNS)
    with pytest.raises(deal.PreContractError):
        spread_postal(urn, {"0101": 1}, districts, count_columns(COLUMNS))
    with pytest.raises(deal.PreContractError):
        spread_postal(urn, {**ASSIGNMENT, "0999": 3}, districts, count_columns(COLUMNS))


def test_spread_postal_shares_equally_without_any_postal_eligible() -> None:
    rows = [
        ("0101", "0101 Schule", 100, 0, 50, 30, 20),
        ("0102", "0102 Schule", 200, 0, 100, 60, 40),
        ("0201", "0201 Turnhalle", 300, 0, 150, 90, 60),
    ]
    urn = precinct_counts(_renamed(rows), COLUMNS).urn
    districts = district_results(
        _renamed(
            [
                ("001", "001 Nord", 300, 0, 160, 90, 60),
                ("002", "002 Sued", 300, 0, 150, 90, 60),
            ]
        ),
        COLUMNS,
    )
    complete = spread_postal(urn, ASSIGNMENT, districts, count_columns(COLUMNS))
    assert complete.get_column(VOTERS).to_list() == [55, 105, 150]  # 10 zu gleichen Teilen


def test_check_postal_total_compares_two_independent_ways() -> None:
    found = precinct_counts(_renamed(PRECINCT_ROWS), COLUMNS)
    assert check_postal_total(found.postal, VOTERS, 70) == 70
    with pytest.raises(SchemaError, match="passen nicht zusammen"):
        check_postal_total(found.postal, VOTERS, 71)


def test_the_transferred_table_has_the_schema_of_the_main_period() -> None:
    """Der ganze Weg in klein: Stimmbezirke, Briefwahl, Übertrag, Anteile."""
    urn = precinct_counts(_renamed(PRECINCT_ROWS), COLUMNS).urn
    districts = district_results(_renamed(DISTRICT_ROWS), COLUMNS)
    counts = count_columns(COLUMNS)
    complete = spread_postal(urn, ASSIGNMENT, districts, counts)
    # Stimmbezirk 0101 halb in Zielbezirk 7, halb in 8; 0102 ganz in 7, 0201 ganz in 8
    shares = pl.DataFrame(
        {
            SOURCE: ["0101", "0101", "0102", "0201"],
            TARGET: [7, 8, 7, 8],
            SHARE: [0.5, 0.5, 1.0, 1.0],
        }
    )
    moved = transfer_counts(complete.rename({PRECINCT: SOURCE}), shares, counts)
    frame = with_shares(moved.rename({TARGET: "wahlkreis_id"}), COLUMNS.parties)
    assert frame.columns == [
        "wahlkreis_id",
        ELIGIBLE_TOTAL,
        VOTERS,
        CDU,
        SPD,
        TURNOUT,
        "CDU_anteil",
        "SPD_anteil",
    ]
    assert frame.get_column(ELIGIBLE_TOTAL).to_list() == [250, 350]
    assert int(frame.get_column(VOTERS).sum()) == 370
    row = frame.row(0, named=True)
    assert row[TURNOUT] == pytest.approx(row[VOTERS] / row[ELIGIBLE_TOTAL])
    assert row["CDU_anteil"] == pytest.approx(row[CDU] / row[VOTERS])
