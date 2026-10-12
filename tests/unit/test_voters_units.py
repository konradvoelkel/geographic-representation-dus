"""Zuordnung Wahlbezirk zu Stadtbezirk: die Brücke von der Wahlergebnis-CSV zum Crosswalk (Option 05)."""

from __future__ import annotations

import json
from pathlib import Path

import deal
import polars as pl
import pytest

from georep.crosswalk import DISTRICT, WEIGHT
from georep.errors import SchemaError
from georep.prep.voters import ELIGIBLE, UNIT, district_units, read_results_csv
from georep.settings import ResultsColumns, Settings
from tests.conftest import MINI

RESULTS_CSV = MINI / "external" / "Stimmbezirk_Wahlergebnis.csv"
PRECINCTS_GEOJSON = MINI / "external" / "Stimmbezirke_2025.geojson"
PRECINCT_KEY = "Stimm-/ Wahlbezirk"  # im GeoJSON; in der CSV heißt die Spalte gebietnr


def test_mini_fixture_maps_every_district_to_one_city_district(
    default_settings: Settings,
) -> None:
    columns = default_settings.columns.results
    frame = district_units(read_results_csv(RESULTS_CSV, columns), columns)
    assert frame.columns == [DISTRICT, UNIT, ELIGIBLE, WEIGHT]
    assert frame.schema[UNIT] == pl.Int64 and frame.schema[ELIGIBLE] == pl.Int64
    # Die Mini-Fixture hat keinen Mehrfachfall (docs/plans/05-gremien.md, § 3.2).
    assert frame.get_column(DISTRICT).to_list() == [1, 10, 38]
    assert frame.get_column(UNIT).to_list() == [1, 2, 9]
    assert frame.get_column(WEIGHT).to_list() == [1.0, 1.0, 1.0]
    assert all(n > 0 for n in frame.get_column(ELIGIBLE))


def city_districts_of_csv(columns: ResultsColumns) -> dict[str, int]:
    """Stimmbezirk -> Stadtbezirk aus der CSV; Zeilen ohne Zahl (Briefwahl) fallen weg."""
    csv = read_results_csv(RESULTS_CSV, columns)
    return {
        row["gebietnr"]: int(row[columns.city_district])
        for row in csv.iter_rows(named=True)
        if row[columns.city_district].strip().isdigit()
    }


def test_city_district_of_the_csv_agrees_with_the_geojson(default_settings: Settings) -> None:
    """Beide Quellen nennen den Stadtbezirk je Stimmbezirk; der Crosswalk gilt nur, wenn sie sich decken."""
    pairs = city_districts_of_csv(default_settings.columns.results)
    features = json.loads(PRECINCTS_GEOJSON.read_text("utf-8"))["features"]
    found = [
        (str(f["properties"][PRECINCT_KEY]), int(f["properties"]["Stadtbezirk Nr."]))
        for f in features
    ]
    assert len(found) == 22  # alle Stimmbezirke der Mini-Fixture
    missing = [precinct for precinct, _ in found if precinct not in pairs]
    assert missing == []
    assert [pairs[p] for p, _ in found] == [unit for _, unit in found]


def test_missing_city_district_column_is_a_schema_error(
    tmp_path: Path, default_settings: Settings
) -> None:
    raw = RESULTS_CSV.read_bytes().decode("latin-1")
    header, body = raw.split("\n", 1)
    assert "Stadtbezirk;" in header
    broken = tmp_path / "ergebnis.csv"
    broken.write_bytes(
        (header.replace("Stadtbezirk;", "Bezirk;", 1) + "\n" + body).encode("latin-1")
    )
    with pytest.raises(SchemaError, match="Stadtbezirk"):
        read_results_csv(broken, default_settings.columns.results)


def test_district_units_needs_the_source_columns(default_settings: Settings) -> None:
    columns = default_settings.columns.results
    frame = pl.DataFrame({columns.district: ["1"], columns.eligible: ["5"]})
    with pytest.raises(deal.PreContractError):
        district_units(frame, columns)


# --- Option 01: votemanager führt keinen Stadtbezirk als Spalte --------------------------------


VOTEMANAGER = ResultsColumns(
    sep=";",
    encoding="utf-8",
    precinct="gebiet-nr",
    district_from_precinct=(1, 3),
    city_district_from_precinct=(0, 1),
    eligible="A",
    voters="B",
    parties={"CDU": "D1"},
)
VOTEMANAGER_CSV = (
    "datum;ags;gebiet-nr;gebiet-name;A;B;D1",
    "14.09.2025;05116000;10401;Venn I;1000;500;200",
    "14.09.2025;05116000;10402;Venn II;1200;600;250",
    "14.09.2025;05116000;32201;Wickrath I;800;400;100",
)


def test_city_district_comes_from_the_precinct_number(tmp_path: Path) -> None:
    """Mönchengladbach führt Stadtbezirk, Wahlbezirk und Stimmbezirk in einer Nummer (10401)."""
    path = tmp_path / "Open-Data-05116000-Ratswahl-Stimmbezirk.csv"
    path.write_text("\n".join(VOTEMANAGER_CSV) + "\n", encoding="utf-8")
    frame = district_units(read_results_csv(path, VOTEMANAGER), VOTEMANAGER)
    assert frame.columns == [DISTRICT, UNIT, ELIGIBLE, WEIGHT]
    assert frame.rows() == [(4, 1, 2200, 1.0), (22, 3, 800, 1.0)]
