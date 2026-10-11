"""Orte aus Wikidata (SPARQL) und Wikipedia (GeoSearch je Stimmbezirk), zugeordnet per STRtree.

Rohformat wie in der Arbeit (``wikipedia_dict.json``): SPARQL-Treffer mit ``url``, GeoSearch-Treffer
mit ``pageid`` und ``dist``, beide mit ``stimmbezirk_id`` und ``wahlkreis_id`` (``None``, wenn der
Punkt in keinem Stimmbezirk liegt). GeoSearch-Treffer zählen nur für den Bezirk, dessen Bounding Box
abgefragt wurde und der den Punkt enthält, wie in der Arbeit.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any

from georep.errors import FetchError
from georep.geo import Precinct, PrecinctIndex, lonlat_bounds
from georep.http import Transport


def sparql_query(entity: str, language: str) -> str:
    """Alle Wikidata-Objekte mit Koordinaten in der Verwaltungseinheit ``entity`` (P131*)
    samt Wikipedia-Artikel in ``language``."""
    return f"""
SELECT ?item ?itemLabel ?coord ?article WHERE {{
  ?item wdt:P625 ?coord.
  ?item wdt:P131* wd:{entity}.
  ?article schema:about ?item;
           schema:isPartOf <https://{language}.wikipedia.org/>;
           schema:name ?articleName.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{language}". }}
}}
"""


def parse_point(value: str) -> tuple[float, float]:
    """``Point(6.77 51.23)`` (WKT, lon lat) -> (lon, lat); alles andere ist ein ``FetchError``."""
    inner = value.strip()
    if not inner.startswith("Point(") or not inner.endswith(")"):
        raise FetchError(f"Keine WKT-Koordinate: {value!r}")
    try:
        lon, lat = (float(part) for part in inner[6:-1].split())
    except ValueError as error:  # nicht zwei Teile oder keine Zahlen
        raise FetchError(f"Keine WKT-Koordinate: {value!r} ({error})") from error
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise FetchError(f"Keine WKT-Koordinate in Grad: {value!r}")
    return lon, lat


def _assign(entry: dict[str, Any], hit: Precinct | None) -> dict[str, Any]:
    entry["stimmbezirk_id"] = int(hit.precinct_id) if hit else None
    entry["wahlkreis_id"] = hit.district_id if hit else None
    return entry


def fetch_sparql_pois(
    http: Transport, endpoint: str, query: str, index: PrecinctIndex
) -> list[dict[str, Any]]:
    response = http.get(
        endpoint,
        params={"query": query, "format": "json"},
        headers={"Accept": "application/json; charset=utf-8"},
    )
    response.raise_for_status()
    try:
        bindings = response.json()["results"]["bindings"]
    except (ValueError, KeyError, TypeError) as error:
        raise FetchError(f"SPARQL {endpoint}: keine Bindings ({error})") from error
    pois: list[dict[str, Any]] = []
    for binding in bindings:
        try:
            lon, lat = parse_point(binding["coord"]["value"])
            entry = {
                "label": binding["itemLabel"]["value"],
                "lon": lon,
                "lat": lat,
                "url": binding["article"]["value"],
            }
        except (KeyError, TypeError) as error:
            raise FetchError(
                f"SPARQL {endpoint}: Binding ohne coord, itemLabel oder article ({error!r})"
            ) from error
        pois.append(_assign(entry, index.locate(lon, lat)))
    return pois


def geosearch_params(bbox: tuple[float, float, float, float], limit: int) -> dict[str, Any]:
    """Wikipedia-API: ``gsbbox`` ist top|left|bottom|right, also max_lat|min_lon|min_lat|max_lon."""
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "action": "query",
        "list": "geosearch",
        "gsbbox": f"{max_lat}|{min_lon}|{min_lat}|{max_lon}",
        "gslimit": limit,
        "format": "json",
    }


def fetch_geosearch_pois(
    http: Transport,
    api: str,
    precincts: Iterable[Precinct],
    index: PrecinctIndex,
    working_crs: str,
    *,
    limit: int = 500,
    delay_s: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    pois: list[dict[str, Any]] = []
    for precinct in precincts:
        params = geosearch_params(lonlat_bounds(precinct.geometry, working_crs), limit)
        response = http.get(api, params=params)
        response.raise_for_status()
        hits = response.json().get("query", {}).get("geosearch", [])
        for hit in hits:
            located = index.locate(float(hit["lon"]), float(hit["lat"]))
            if located is None or located.precinct_id != precinct.precinct_id:
                continue  # zählt nur für den abgefragten Bezirk, wie in der Arbeit
            entry = {
                "label": hit["title"],
                "pageid": hit["pageid"],
                "lat": float(hit["lat"]),
                "lon": float(hit["lon"]),
                "dist": hit.get("dist", 0),
            }
            pois.append(_assign(entry, located))
        if delay_s > 0:
            sleep(delay_s)
    return pois
