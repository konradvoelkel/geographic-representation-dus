from __future__ import annotations

import io
import json
import zipfile

import pytest
import requests

from georep.errors import FetchError, NetworkError
from georep.sources.opendata import fetch_csv, fetch_districts_file, fetch_geojson
from tests.fakes import FakeSession, response

URL = "https://opendata.invalid/x"


def test_results_csv_passes_through_bytes_when_header_has_separator() -> None:
    body = "﻿datum;gebietname\n14.09.2025;Flingern-Süd\n".encode("latin-1", errors="replace")
    assert fetch_csv(FakeSession({URL: response(URL, content=body)}), URL) == body


@pytest.mark.parametrize("body", [b"", b"   \n", b"<html>Wartung</html>\n"])
def test_results_csv_rejects_empty_or_foreign_content(body: bytes) -> None:
    with pytest.raises(FetchError, match="Kopfzeile"):
        fetch_csv(FakeSession({URL: response(URL, content=body)}), URL)


def test_results_csv_turns_http_and_network_errors_into_domain_errors() -> None:
    with pytest.raises(NetworkError, match="503"):
        fetch_csv(FakeSession({URL: response(URL, status=503)}), URL)
    with pytest.raises(NetworkError, match="keine Verbindung") as caught:
        fetch_csv(FakeSession({URL: requests.ConnectionError("keine Verbindung")}), URL)
    assert isinstance(caught.value.__cause__, requests.ConnectionError)


def test_geojson_requires_a_feature_collection() -> None:
    good = {"type": "FeatureCollection", "features": [{"type": "Feature"}]}
    assert fetch_geojson(FakeSession({URL: response(URL, payload=good)}), URL) == good
    bad: object
    for bad in ({"type": "FeatureCollection", "features": []}, {"type": "Feature"}, []):
        with pytest.raises(FetchError):
            fetch_geojson(FakeSession({URL: response(URL, payload=bad)}), URL)
    with pytest.raises(FetchError, match="kein JSON"):
        fetch_geojson(FakeSession({URL: response(URL, content=b"nicht json")}), URL)


def test_districts_file_requires_a_feature_collection() -> None:
    """Option 01: dieselbe Prüfung, aber die Bytes der Quelle bleiben, wie sie sind."""
    good = {"type": "FeatureCollection", "features": [{"type": "Feature"}]}
    session = FakeSession({URL: response(URL, payload=good)})
    assert json.loads(fetch_districts_file(session, URL)) == good
    bad: object
    for bad in ({"type": "FeatureCollection", "features": []}, {"type": "Feature"}, []):
        with pytest.raises(FetchError):
            fetch_districts_file(FakeSession({URL: response(URL, payload=bad)}), URL)
    with pytest.raises(FetchError, match="kein JSON"):
        fetch_districts_file(FakeSession({URL: response(URL, content=b"nicht json")}), URL)


# --- Option 01: Shapefile-Zip als zweite Quellform (Mönchengladbach) ---------------------------


def _zip_bytes(names: tuple[str, ...]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, b"x")
    return buffer.getvalue()


def test_districts_file_requires_a_complete_shapefile_in_the_zip() -> None:
    complete = _zip_bytes(
        (
            "Wahlen/Stimmbezirke_MG.shp",
            "Wahlen/Stimmbezirke_MG.dbf",
            "Wahlen/Stimmbezirke_MG.prj",
            "Wahlen/Stimmbezirke_MG.shx",
        )
    )
    session = FakeSession({URL: response(URL, content=complete)})
    assert fetch_districts_file(session, URL, fmt="shapefile-zip") == complete
    for broken in (_zip_bytes(("a.shp", "a.dbf")), _zip_bytes(("liesmich.txt",))):
        with pytest.raises(FetchError, match="Shapefile"):
            fetch_districts_file(
                FakeSession({URL: response(URL, content=broken)}), URL, fmt="shapefile-zip"
            )
    with pytest.raises(FetchError, match="kein Zip"):
        fetch_districts_file(
            FakeSession({URL: response(URL, content=b"PK-nicht")}), URL, fmt="shapefile-zip"
        )


# --- Punkt 59: Esri-JSON als dritte Quellform (eine ArcGIS-Operation, keine Datei) -------------

IDENTIFY_URL = (
    "https://geo.invalid/server/rest/services/Wahlen/MapServer/identify"
    "?geometry=310000,5662000,328000,5681000&geometryType=esriGeometryEnvelope&sr=25832"
    "&layers=all:16&tolerance=0&returnGeometry=true&f=json"
)
RING = [[0.0, 0.0], [0.0, 10.0], [10.0, 10.0], [10.0, 0.0], [0.0, 0.0]]


def test_districts_file_fetches_an_identify_answer_with_its_query_string() -> None:
    """Die Flächen können eine Operation sein; der Query-String gehört zur URL und bleibt dran."""
    good = {
        "results": [
            {
                "attributes": {"Nummer": "10401"},
                "geometry": {"rings": [RING], "spatialReference": {"wkid": 25832}},
            }
        ]
    }
    session = FakeSession({IDENTIFY_URL: response(IDENTIFY_URL, payload=good)})
    content = fetch_districts_file(session, IDENTIFY_URL, fmt="esri-identify")
    assert json.loads(content) == good


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"results": []}, "keine results"),
        ({"results": [{"attributes": {"Nummer": "10401"}}]}, "ohne geometry.rings"),
        ({"results": [{"geometry": {"rings": []}}]}, "ohne geometry.rings"),
        ([], "kein Esri-JSON-Objekt"),
        (
            {"error": {"code": 400, "message": "Unable to complete operation."}},
            "der Dienst meldet",
        ),
    ],
)
def test_an_identify_answer_that_carries_no_areas_is_a_fetch_error(
    payload: object, message: str
) -> None:
    """Ein ArcGIS-Dienst meldet seine Fehler mit HTTP 200; ohne diese Prüfung lägen sie als Datei da."""
    with pytest.raises(FetchError, match=message):
        fetch_districts_file(
            FakeSession({URL: response(URL, payload=payload)}), URL, fmt="esri-identify"
        )
    with pytest.raises(FetchError, match="kein JSON"):
        fetch_districts_file(
            FakeSession({URL: response(URL, content=b"<html>Wartung</html>")}),
            URL,
            fmt="esri-identify",
        )
