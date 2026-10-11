"""Netztests der zweiten Periode: Marker ``network``, laufen nur von Hand.

    uv run pytest -m network tests/golden/test_network_period.py

Sie prüfen, dass die vier Portaldateien der Ratswahl 2020 und die erste Seite des Abrufs noch so
aussehen, wie ``settings.2014.toml`` es annimmt — Format, nicht Inhalt. In CI laufen sie nie
(der OParl-Server braucht rund 85 s je Seite, und das Portal soll nicht bei jedem Commit geladen
werden); die Zahlen hier wurden am 2026-10-12 nachgesehen. Werden sie rot, hat das Portal eine
Datei umbenannt oder umgebaut, und das Profil braucht eine Zeile Pflege.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from georep.oparl import PaperPage
from georep.settings import Settings, load_settings
from georep.sources import cached_session
from georep.sources.oparl import start_url
from georep.sources.opendata import fetch_csv, fetch_geojson

pytestmark = pytest.mark.network

REPO = Path(__file__).resolve().parents[2]
PROFILE = REPO / "settings.2014.toml"


@pytest.fixture(scope="module")
def period(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    root = tmp_path_factory.mktemp("netz")
    return load_settings(explicit=PROFILE, cwd=Path("/nonexistent")).model_copy(
        update={"data_root": root, "cache_root": root / "cache"}
    )


def test_the_precinct_result_of_2020_still_has_its_columns(period: Settings) -> None:
    columns = period.columns.results
    content = fetch_csv(
        cached_session(period, period.cache_dir / "http.sqlite"),
        period.sources.opendata.results_url,
        sep=columns.sep,
    )
    lines = content.decode(columns.encoding).splitlines()
    header = lines[0].split(columns.sep)
    for name in (columns.precinct, columns.precinct_name, columns.eligible, columns.voters):
        assert name in header
    assert all(name in header for name in columns.parties.values())
    assert len(lines) == 455  # Kopf, 316 Urnen- und 138 Briefwahlbezirke (2026-10-12)
    postal = [line for line in lines[1:] if columns.postal_marker in line]
    assert len(postal) == 138


def test_the_district_result_of_2020_has_41_rows(period: Settings) -> None:
    columns = period.columns.results
    content = fetch_csv(
        cached_session(period, period.cache_dir / "http.sqlite"),
        period.sources.opendata.district_results_url,
        sep=columns.sep,
    )
    lines = content.decode(columns.encoding).splitlines()
    assert len(lines) == 42  # Kopf und 41 Wahlbezirke
    assert lines[0].split(columns.sep)[:5] == [
        "datum",
        "wahl",
        "ags",
        columns.precinct,
        columns.precinct_name,
    ]


def test_both_geojson_files_of_2020_carry_the_expected_properties(period: Settings) -> None:
    http = cached_session(period, period.cache_dir / "http.sqlite")
    cross = period.crosswalk
    precincts = fetch_geojson(http, period.sources.opendata.districts_url)
    features = precincts["features"]
    assert len(features) == 316
    assert all(cross.precinct_id in f["properties"] for f in features)
    districts = fetch_geojson(http, period.sources.opendata.district_shapes_url)
    shapes = districts["features"]
    assert len(shapes) == 41
    assert all(cross.district_id in f["properties"] for f in shapes)
    assert all(cross.district_name in f["properties"] for f in shapes)
    assert "4647" in str(precincts.get("crs")) and "4647" in str(districts.get("crs"))


def test_the_first_page_of_the_old_period_parses_and_lies_in_it(period: Settings) -> None:
    """Eine Seite, rund 85 s: trägt ``first_page`` noch in die Periode, und passt das Format?"""
    oparl = period.sources.oparl
    url = start_url(oparl.endpoint, oparl.first_page)
    http = cached_session(period, period.cache_dir / "http.sqlite")
    answer = http.get(url)
    answer.raise_for_status()
    page = PaperPage.model_validate(answer.json())
    assert page.data
    dates = [p.date for p in page.data if p.date is not None]
    assert dates, "eine Seite ohne Datum wäre neu"
    assert max(dates) <= period.period.election_day, (
        f"Seite {oparl.first_page} trägt noch Paper der Hauptperiode ({max(dates)}): "
        "die Seitenzahl ist gewandert, first_page erhöhen"
    )
    assert page.links.next, "die Seite ist die letzte: first_page ist zu hoch"
