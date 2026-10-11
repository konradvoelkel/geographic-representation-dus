from __future__ import annotations

import pytest
import requests

from georep.errors import FetchError
from georep.sources.opendata import fetch_districts_geojson, fetch_results_csv
from tests.fakes import FakeSession, response

URL = "https://opendata.invalid/x"


def test_results_csv_passes_through_bytes_when_header_has_separator() -> None:
    body = "﻿datum;gebietname\n14.09.2025;Flingern-Süd\n".encode("latin-1", errors="replace")
    assert fetch_results_csv(FakeSession({URL: response(URL, content=body)}), URL) == body


@pytest.mark.parametrize("body", [b"", b"   \n", b"<html>Wartung</html>\n"])
def test_results_csv_rejects_empty_or_foreign_content(body: bytes) -> None:
    with pytest.raises(FetchError, match="Kopfzeile"):
        fetch_results_csv(FakeSession({URL: response(URL, content=body)}), URL)


def test_results_csv_propagates_http_errors() -> None:
    with pytest.raises(requests.HTTPError):
        fetch_results_csv(FakeSession({URL: response(URL, status=503)}), URL)


def test_districts_geojson_requires_a_feature_collection() -> None:
    good = {"type": "FeatureCollection", "features": [{"type": "Feature"}]}
    assert fetch_districts_geojson(FakeSession({URL: response(URL, payload=good)}), URL) == good
    bad: object
    for bad in ({"type": "FeatureCollection", "features": []}, {"type": "Feature"}, []):
        with pytest.raises(FetchError):
            fetch_districts_geojson(FakeSession({URL: response(URL, payload=bad)}), URL)
    with pytest.raises(FetchError, match="kein JSON"):
        fetch_districts_geojson(FakeSession({URL: response(URL, content=b"nicht json")}), URL)
