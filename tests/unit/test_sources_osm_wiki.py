"""Overpass und Wiki gegen die aufgezeichneten Antworten und die Referenz der Arbeit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from georep.errors import FetchError
from georep.geo import Precinct, PrecinctIndex, read_canonical_precincts
from georep.settings import Settings, load_settings
from georep.sources.overpass import (
    OSM_FILTER,
    fetch_street_names,
    fetch_streets_per_precinct,
    overpass_query,
    street_names,
)
from georep.sources.wiki import (
    fetch_geosearch_pois,
    fetch_sparql_pois,
    geosearch_params,
    parse_point,
    sparql_query,
)
from tests.conftest import REPO
from tests.fakes import FakeSession, response

HTTP = REPO / "tests" / "fixtures" / "http"


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


@pytest.fixture(scope="module")
def precincts(reference_precincts: Path, settings: Settings) -> list[Precinct]:
    return read_canonical_precincts(reference_precincts, settings.geo.working_crs)


def _reference_streets(reference_root: Path) -> dict[str, list[str]]:
    data = json.loads(
        (reference_root / "raw" / "streets_per_district.json").read_text(encoding="utf-8")
    )
    return {e["stimmbezirks_id"]: sorted(e["straßen"]) for e in data}


def _reference_pois(reference_root: Path) -> list[dict[str, Any]]:
    pois: list[dict[str, Any]] = json.loads(
        (reference_root / "raw" / "wikipedia_dict.json").read_text(encoding="utf-8")
    )
    return pois


@pytest.mark.parametrize("precinct_id", ["1302", "9802"])
def test_recorded_overpass_answers_reproduce_the_reference_streets(
    reference_root: Path, precinct_id: str
) -> None:
    data = json.loads((HTTP / f"overpass_{precinct_id}.json").read_text(encoding="utf-8"))
    assert street_names(data) == _reference_streets(reference_root)[precinct_id]


def test_overpass_query_carries_the_osmnx_filter_and_recorded_query_matches() -> None:
    query = overpass_query("51.1 6.7 51.2 6.8")
    assert OSM_FILTER in query and 'poly:"51.1 6.7 51.2 6.8"' in query
    recorded = (HTTP / "overpass_1302.query.txt").read_text(encoding="utf-8")
    assert OSM_FILTER in recorded


def test_the_query_timeout_is_a_setting_and_reaches_every_post_body(
    precincts: list[Precinct], settings: Settings
) -> None:
    """Punkt 54: ``[timeout:…]`` kommt aus ``sources.osm.query_timeout_s``, nicht aus dem Code.

    Die aufgezeichneten Abfragen tragen 60 beziehungsweise 90 (`tests/fixtures/http/README.md`);
    der Schlüssel der Fake-Session ist die URL, nicht der Abfragetext, darum bleiben sie gültig.
    """
    assert settings.sources.osm.query_timeout_s == 25
    assert overpass_query("51.1 6.7").startswith("[out:json][timeout:25];")
    assert overpass_query("51.1 6.7", timeout_s=30).startswith("[out:json][timeout:30];")

    endpoint = settings.sources.osm.overpass_endpoint
    data = json.loads((HTTP / "overpass_1302.json").read_text(encoding="utf-8"))
    session = FakeSession({endpoint: response(endpoint, payload=data)})
    first = next(p for p in precincts if p.precinct_id == "1302")
    fetch_streets_per_precinct(
        session,
        endpoint,
        [first],
        settings.geo.working_crs,
        query_timeout_s=30,
        delay_s=0,
        sleep=lambda _: None,
    )
    assert session.calls[0][1]["data"].startswith("[out:json][timeout:30];")


def test_fetch_streets_per_precinct_writes_the_legacy_shape(
    precincts: list[Precinct], settings: Settings, reference_root: Path
) -> None:
    endpoint = settings.sources.osm.overpass_endpoint
    data = json.loads((HTTP / "overpass_1302.json").read_text(encoding="utf-8"))
    session = FakeSession({endpoint: response(endpoint, payload=data)})
    slept: list[float] = []
    first = next(p for p in precincts if p.precinct_id == "1302")
    entries = fetch_streets_per_precinct(
        session, endpoint, [first], settings.geo.working_crs, delay_s=1.0, sleep=slept.append
    )
    assert entries == [
        {
            "stimmbezirks_id": "1302",
            "stimmbezirks_name": "Altstadt, Carlstadt, Hofgarten",
            "wahlbezirk_id": 1,
            "straßen": _reference_streets(reference_root)["1302"],
        }
    ]
    assert slept == [1.0]
    body = session.calls[0][1]["data"]
    assert body.startswith("[out:json]") and "(poly:" in body


def test_fetch_street_names_rejects_answers_without_elements(settings: Settings) -> None:
    endpoint = settings.sources.osm.overpass_endpoint
    session = FakeSession(
        {endpoint: response(endpoint, payload={"remark": "runtime error: timeout"})}
    )
    with pytest.raises(FetchError, match="timeout"):
        fetch_street_names(session, endpoint, "51 6 51 7")


def test_parse_point_and_sparql_query() -> None:
    assert parse_point("Point(6.77365 51.23054)") == (6.77365, 51.23054)
    for bad in ("51.2, 6.7", "Point(a b)", "Point(1 2 3)", "Point(500 51)", "Point(6.7 91)"):
        with pytest.raises(FetchError, match="Koordinate"):
            parse_point(bad)
    query = sparql_query("Q2066", "fr")
    assert "wd:Q2066." in query and "fr.wikipedia.org" in query and 'language "fr"' in query
    assert sparql_query("Q1718", "de") == (HTTP / "wikidata_sparql.query.txt").read_text(
        encoding="utf-8"
    )


def test_recorded_sparql_pois_match_the_reference_assignment(
    precincts: list[Precinct], settings: Settings, reference_root: Path
) -> None:
    endpoint = settings.sources.wikidata.sparql_endpoint
    data = json.loads((HTTP / "wikidata_sparql.json").read_text(encoding="utf-8"))
    session = FakeSession({endpoint: response(endpoint, payload=data)})
    index = PrecinctIndex(precincts, settings.geo.working_crs)
    pois = fetch_sparql_pois(session, endpoint, "egal", index)
    assert len(pois) == 25 and all(
        {"label", "lon", "lat", "url", "stimmbezirk_id", "wahlkreis_id"} == set(p) for p in pois
    )
    # Vergleich über die Artikel-URL: Labels sind nicht eindeutig ("Itter" ist Stadtteil und Bach)
    reference = {p["url"]: p for p in _reference_pois(reference_root) if "url" in p}
    compared = 0
    for poi in pois:
        ref = reference.get(poi["url"])
        if (
            ref is None
            or abs(ref["lon"] - poi["lon"]) > 1e-6
            or abs(ref["lat"] - poi["lat"]) > 1e-6
        ):
            continue  # seit November 2025 neu in Wikidata oder Koordinate verschoben (z. B. Itter)
        assert (poi["stimmbezirk_id"], poi["wahlkreis_id"]) == (
            ref["stimmbezirk_id"],
            ref["wahlkreis_id"],
        ), poi["label"]
        compared += 1
    assert compared >= 20
    assert session.calls[0][1]["format"] == "json"


def test_recorded_geosearch_keeps_only_points_inside_the_queried_precinct(
    precincts: list[Precinct], settings: Settings, reference_root: Path
) -> None:
    api = settings.sources.wikidata.wikipedia_api
    data = json.loads((HTTP / "wikipedia_geosearch_1302.json").read_text(encoding="utf-8"))
    params = json.loads((HTTP / "wikipedia_geosearch_1302.params.json").read_text(encoding="utf-8"))
    session = FakeSession({api: response(api, payload=data)})
    index = PrecinctIndex(precincts, settings.geo.working_crs)
    first = next(p for p in precincts if p.precinct_id == "1302")
    pois = fetch_geosearch_pois(
        session, api, [first], index, settings.geo.working_crs, limit=500, delay_s=0
    )
    reference = sorted(
        p["label"]
        for p in _reference_pois(reference_root)
        if "pageid" in p and str(p.get("stimmbezirk_id")).lstrip("0") == "1302"
    )
    assert sorted(p["label"] for p in pois) == reference
    assert all(p["stimmbezirk_id"] == 1302 and p["wahlkreis_id"] == 1 for p in pois)
    sent = session.calls[0][1]
    assert sent["gsbbox"] == params["gsbbox"] and sent["gslimit"] == 500
    assert geosearch_params((6.7, 51.2, 6.8, 51.3), 10)["gsbbox"] == "51.3|6.7|51.2|6.8"


def test_sparql_binding_without_fields_is_a_fetch_error(
    precincts: list[Precinct], settings: Settings
) -> None:
    endpoint = settings.sources.wikidata.sparql_endpoint
    broken = {"results": {"bindings": [{"itemLabel": {"value": "Ohne Koordinate"}}]}}
    session = FakeSession({endpoint: response(endpoint, payload=broken)})
    with pytest.raises(FetchError, match="coord"):
        fetch_sparql_pois(
            session, endpoint, "egal", PrecinctIndex(precincts, settings.geo.working_crs)
        )


def test_geosearch_hit_without_coordinates_is_a_fetch_error(
    precincts: list[Precinct], settings: Settings
) -> None:
    api = settings.sources.wikidata.wikipedia_api
    broken = {"query": {"geosearch": [{"title": "Ohne Ort", "pageid": 1}]}}
    session = FakeSession({api: response(api, payload=broken)})
    index = PrecinctIndex(precincts, settings.geo.working_crs)
    with pytest.raises(FetchError, match="lon"):
        fetch_geosearch_pois(
            session, api, precincts[:1], index, settings.geo.working_crs, delay_s=0
        )


def test_street_names_ignores_malformed_elements() -> None:
    """crosshair fand am 2026-10-11 street_names({'elements': 0}) -> TypeError."""
    assert street_names({"elements": 0}) == []
    broken = [0, {"tags": 1}, {"tags": {"name": "B, A"}}, {"tags": {"name": 5}}, {}]
    assert street_names({"elements": broken}) == ["A", "B"]


def test_fetch_street_names_rejects_non_object_answers(settings: Settings) -> None:
    endpoint = settings.sources.osm.overpass_endpoint
    session = FakeSession({endpoint: response(endpoint, payload=[1, 2])})
    with pytest.raises(FetchError, match="elements"):
        fetch_street_names(session, endpoint, "51 6 51 7")
