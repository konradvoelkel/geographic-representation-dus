"""Open-Data-Portal: die zwei Formate, in denen es liefert, CSV und GeoJSON.

Dieselben zwei Funktionen holen Wahlergebnis und Stimmbezirke wie die Fremddaten je Raumeinheit
(Option 03); es gibt nur diese eine Quelle, darum nennen sie das Format und nicht den Inhalt.
Beides wird geprüft, bevor es jemand speichert: eine CSV ohne das Trennzeichen in der Kopfzeile
oder ein GeoJSON ohne Features ist ein ``FetchError``, kein stilles Weiter; die URL steht in der
Meldung, denn sie nennt die Datei.
"""

from __future__ import annotations

from typing import Any

import deal

from georep.errors import FetchError, NetworkError
from georep.http import Transport, network_errors


@deal.raises(FetchError, NetworkError)
def fetch_csv(http: Transport, url: str, *, sep: str = ";") -> bytes:
    with network_errors(url):
        response = http.get(url)
        response.raise_for_status()
        content = response.content
    header = content.split(b"\n", 1)[0]
    if not content.strip() or sep.encode() not in header:
        raise FetchError(
            f"CSV von {url}: kein Text mit '{sep}' in der Kopfzeile ({len(content)} Bytes)"
        )
    return content


@deal.raises(FetchError, NetworkError)
def fetch_geojson(http: Transport, url: str) -> dict[str, Any]:
    with network_errors(url):
        response = http.get(url)
        response.raise_for_status()
    try:
        data = response.json()
    except ValueError as error:
        raise FetchError(f"GeoJSON von {url}: kein JSON ({error})") from error
    if (
        not isinstance(data, dict)
        or data.get("type") != "FeatureCollection"
        or not data.get("features")
    ):
        raise FetchError(f"GeoJSON von {url}: keine FeatureCollection mit Features")
    return data
