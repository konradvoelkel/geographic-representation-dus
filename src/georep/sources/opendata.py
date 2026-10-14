"""Open-Data-Portale und votemanager-Präsentationen: CSV, GeoJSON und Shapefile-Zip.

Dieselben Funktionen holen Wahlergebnis und Stimmbezirke wie die Fremddaten je Raumeinheit
(Option 03); es gibt nur diese eine Quelle, darum nennen sie das Format und nicht den Inhalt.
Alles wird geprüft, bevor es jemand speichert: eine CSV ohne das Trennzeichen in der Kopfzeile,
ein GeoJSON ohne Features oder ein Zip ohne vollständiges Shapefile ist ein ``FetchError``, kein
stilles Weiter; die URL steht in der Meldung, denn sie nennt die Datei.

Die Stimmbezirksflächen holt ``fetch_districts_file`` byteweise, wie die Quelle sie liefert (ein
Zip überlebt kein Umschreiben, Option 01); was daraus wird, entscheidet der Schritt ``shapes``.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any, Literal

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


# --- Option 01: die Stimmbezirksflächen, wie die Quelle sie liefert ------------------------------

SHAPEFILE_MEMBERS = (".shp", ".dbf", ".prj")


@deal.raises(FetchError, NetworkError)
def fetch_districts_file(
    http: Transport,
    url: str,
    *,
    fmt: Literal["geojson", "shapefile-zip", "esri-identify"] = "geojson",
) -> bytes:
    """Die Flächen als Bytes, nach Format geprüft und dann unverändert.

    Die URL darf einen Query-String tragen: die Flächen einer Stadt können eine Operation eines
    ArcGIS-Dienstes sein und keine Datei (``identify?geometry=…&f=json``, Punkt 59). Ein ``&``
    liest TOML wörtlich, der Abruf bleibt ein GET, und ``http.cache_pattern`` deckt die Anfrage
    mit seinem ``*`` ab -- am Cache ist dafür nichts zu ändern.
    """
    with network_errors(url):
        response = http.get(url)
        response.raise_for_status()
        content = response.content
    if fmt == "shapefile-zip":
        _check_shapefile_zip(url, content)
    elif fmt == "esri-identify":
        _check_identify(url, content)
    else:
        _check_feature_collection(url, content)
    return content


def _check_feature_collection(url: str, content: bytes) -> None:
    try:
        data = json.loads(content)
    except ValueError as error:
        raise FetchError(f"Stimmbezirke von {url}: kein JSON ({error})") from error
    if (
        not isinstance(data, dict)
        or data.get("type") != "FeatureCollection"
        or not data.get("features")
    ):
        raise FetchError(f"Stimmbezirke von {url}: keine FeatureCollection mit Features")


def _check_identify(url: str, content: bytes) -> None:
    """Esri-JSON mit ``results[]``, jeder Treffer mit Ringen.

    Ein ArcGIS-Dienst meldet seine Fehler **mit HTTP 200** und einem ``error``-Objekt; ohne diese
    Prüfung landete die Fehlermeldung als Datei in ``external/`` und der Schritt ``shapes`` wäre
    der erste, dem etwas auffällt.
    """
    try:
        data = json.loads(content)
    except ValueError as error:
        raise FetchError(f"Stimmbezirke von {url}: kein JSON ({error})") from error
    if not isinstance(data, dict):
        raise FetchError(f"Stimmbezirke von {url}: kein Esri-JSON-Objekt")
    if "error" in data:
        raise FetchError(f"Stimmbezirke von {url}: der Dienst meldet {data['error']}")
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise FetchError(f"Stimmbezirke von {url}: keine results in der identify-Antwort")
    without = sum(not _has_rings(entry) for entry in results)
    if without:
        raise FetchError(
            f"Stimmbezirke von {url}: {without} von {len(results)} Treffern ohne "
            "geometry.rings; die Abfrage braucht returnGeometry=true"
        )


def _has_rings(entry: Any) -> bool:
    geometry = entry.get("geometry") if isinstance(entry, dict) else None
    return isinstance(geometry, dict) and bool(geometry.get("rings"))


def _check_shapefile_zip(url: str, content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as error:
        raise FetchError(f"Stimmbezirke von {url}: kein Zip ({error})") from error
    stems = {n.removesuffix(".shp") for n in names if n.endswith(".shp")}
    complete = [s for s in stems if all(f"{s}{ext}" in names for ext in SHAPEFILE_MEMBERS)]
    if not complete:
        raise FetchError(
            f"Stimmbezirke von {url}: kein Shapefile mit {list(SHAPEFILE_MEMBERS)} im Zip "
            f"({len(names)} Mitglieder)"
        )
