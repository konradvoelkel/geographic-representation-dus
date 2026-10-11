"""Straßennamen je Stimmbezirk direkt von Overpass, ohne osmnx und ohne Graphaufbau.

Der Filter bildet ``network_type="all"`` von osmnx nach, weil die Referenz der Arbeit damit
entstand: Wege mit ``highway`` und ``name``, ohne ``area=yes``, ohne stillgelegte oder geplante
Typen, ohne ``service=private``. Namen mit Komma werden geteilt wie in der Arbeit. Treue gegen
die Referenz: ``tests/fixtures/http/README.md``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any

from georep.errors import FetchError
from georep.geo import Precinct, overpass_polygon
from georep.http import Transport

OSM_FILTER = (
    '["highway"]["name"]["area"!~"yes"]'
    '["highway"!~"abandoned|construction|planned|platform|proposed|raceway|razed"]'
    '["service"!~"private"]'
)


def overpass_query(polygon_latlon: str, *, timeout_s: int = 90) -> str:
    return f'[out:json][timeout:{timeout_s}];way{OSM_FILTER}(poly:"{polygon_latlon}");out tags;'


def street_names(data: dict[str, Any]) -> list[str]:
    """Eindeutige, sortierte Namen aller Ways; ``a, b`` wird zu ``a`` und ``b`` wie in der Arbeit."""
    names: set[str] = set()
    for element in data.get("elements", []):
        name = element.get("tags", {}).get("name")
        if isinstance(name, str):
            names.update(part.strip() for part in name.split(",") if part.strip())
    return sorted(names)


def fetch_street_names(http: Transport, endpoint: str, polygon_latlon: str) -> list[str]:
    response = http.post(endpoint, data={"data": overpass_query(polygon_latlon)})
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as error:
        raise FetchError(f"Overpass {endpoint}: kein JSON ({error})") from error
    if "elements" not in data:
        raise FetchError(f"Overpass {endpoint}: Antwort ohne elements ({data.get('remark', '')})")
    return street_names(data)


def fetch_streets_per_precinct(
    http: Transport,
    endpoint: str,
    precincts: Iterable[Precinct],
    working_crs: str,
    *,
    tolerance_m: float = 2.0,
    delay_s: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Das Rohformat der Arbeit: je Stimmbezirk ID, Name, Wahlbezirk und die Straßenliste."""
    entries: list[dict[str, Any]] = []
    for precinct in precincts:
        polygon = overpass_polygon(precinct.geometry, working_crs, tolerance_m=tolerance_m)
        names = fetch_street_names(http, endpoint, polygon)
        entries.append(
            {
                "stimmbezirks_id": precinct.precinct_id,
                "stimmbezirks_name": precinct.district_name,
                "wahlbezirk_id": precinct.district_id,
                "straßen": names,
            }
        )
        if delay_s > 0:
            sleep(delay_s)
    return entries
