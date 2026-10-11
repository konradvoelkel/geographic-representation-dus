"""Open-Data-Portal Düsseldorf: Wahlergebnis-CSV und Stimmbezirks-GeoJSON.

Beides wird geprüft, bevor es jemand speichert: eine CSV ohne das Trennzeichen in der Kopfzeile
oder ein GeoJSON ohne Features ist ein ``FetchError``, kein stilles Weiter.
"""

from __future__ import annotations

from typing import Any

import deal

from georep.errors import FetchError, NetworkError
from georep.http import Transport, network_errors


@deal.raises(FetchError, NetworkError)
def fetch_results_csv(http: Transport, url: str, *, sep: str = ";") -> bytes:
    with network_errors(url):
        response = http.get(url)
        response.raise_for_status()
        content = response.content
    header = content.split(b"\n", 1)[0]
    if not content.strip() or sep.encode() not in header:
        raise FetchError(
            f"Wahlergebnis von {url}: keine CSV mit '{sep}' in der Kopfzeile ({len(content)} Bytes)"
        )
    return content


@deal.raises(FetchError, NetworkError)
def fetch_districts_geojson(http: Transport, url: str) -> dict[str, Any]:
    with network_errors(url):
        response = http.get(url)
        response.raise_for_status()
    try:
        data = response.json()
    except ValueError as error:
        raise FetchError(f"Stimmbezirke von {url}: kein JSON ({error})") from error
    if (
        not isinstance(data, dict)
        or data.get("type") != "FeatureCollection"
        or not data.get("features")
    ):
        raise FetchError(f"Stimmbezirke von {url}: keine FeatureCollection mit Features")
    return data
