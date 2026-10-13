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

import deal

from georep.errors import FetchError, NetworkError
from georep.geo import Precinct, overpass_polygon
from georep.http import Transport, network_errors

OSM_FILTER = (
    '["highway"]["name"]["area"!~"yes"]'
    '["highway"!~"abandoned|construction|planned|platform|proposed|raceway|razed"]'
    '["service"!~"private"]'
)
# Der Standard steht in ``defaults.toml`` unter ``sources.osm.query_timeout_s`` samt Messung; hier
# liegt er, damit die Funktion allein aufrufbar bleibt (Tests, ``deal.cases``, crosshair).
DEFAULT_QUERY_TIMEOUT_S = 25


@deal.pure
def overpass_query(polygon_latlon: str, *, timeout_s: int = DEFAULT_QUERY_TIMEOUT_S) -> str:
    """Die Abfrage eines Stimmbezirks; ``timeout_s`` ist das ``[timeout:…]`` des Servers.

    Die Zahl ist kein Netz-Timeout des Clients (der steht in ``http.timeout_s``), sondern das
    Rechenbudget, das Overpass der Abfrage selbst gibt -- und zugleich Teil des POST-Bodys und
    damit des Cache-Schlüssels (docs/decisions.md, Punkte 9 und 54).
    """
    return f'[out:json][timeout:{timeout_s}];way{OSM_FILTER}(poly:"{polygon_latlon}");out tags;'


@deal.pure
@deal.post(
    lambda result: result == sorted(set(result)) and all(n and n == n.strip() for n in result)
)
def street_names(data: dict[str, Any]) -> list[str]:
    """Eindeutige, sortierte Namen aller Ways; ``a, b`` wird zu ``a`` und ``b`` wie in der Arbeit.

    Total über jedes dict: was kein Way mit ``tags.name`` als String ist, wird übergangen
    (crosshair fand am 2026-10-11 ``{"elements": 0}`` als Gegenbeispiel zum alten Code).
    """
    names: set[str] = set()
    elements = data.get("elements")
    for element in elements if isinstance(elements, list) else []:
        tags = element.get("tags") if isinstance(element, dict) else None
        name = tags.get("name") if isinstance(tags, dict) else None
        if isinstance(name, str):
            names.update(part.strip() for part in name.split(",") if part.strip())
    return sorted(names)


@deal.raises(FetchError, NetworkError)
def fetch_street_names(
    http: Transport,
    endpoint: str,
    polygon_latlon: str,
    *,
    timeout_s: int = DEFAULT_QUERY_TIMEOUT_S,
) -> list[str]:
    with network_errors(endpoint):
        response = http.post(
            endpoint, data={"data": overpass_query(polygon_latlon, timeout_s=timeout_s)}
        )
        response.raise_for_status()
    try:
        data = response.json()
    except ValueError as error:
        raise FetchError(f"Overpass {endpoint}: kein JSON ({error})") from error
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
        remark = data.get("remark", "") if isinstance(data, dict) else type(data).__name__
        raise FetchError(f"Overpass {endpoint}: Antwort ohne elements ({remark})")
    return street_names(data)


def fetch_streets_per_precinct(
    http: Transport,
    endpoint: str,
    precincts: Iterable[Precinct],
    working_crs: str,
    *,
    tolerance_m: float = 2.0,
    query_timeout_s: int = DEFAULT_QUERY_TIMEOUT_S,
    delay_s: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Das Rohformat der Arbeit: je Stimmbezirk ID, Name, Wahlbezirk und die Straßenliste."""
    entries: list[dict[str, Any]] = []
    for precinct in precincts:
        polygon = overpass_polygon(precinct.geometry, working_crs, tolerance_m=tolerance_m)
        names = fetch_street_names(http, endpoint, polygon, timeout_s=query_timeout_s)
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
