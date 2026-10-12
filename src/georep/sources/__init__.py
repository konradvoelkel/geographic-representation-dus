"""Quellen: reine Fetch-Funktionen über das ``Transport``-Protokoll, ohne Dateizugriff."""

from __future__ import annotations

from pathlib import Path

import requests

from georep.http import cache_pattern, make_session
from georep.settings import Settings


def cached_session(settings: Settings, cache_path: Path) -> requests.Session:
    """Die eine Session für alle Quellen: Timeout, Retry, User-Agent, Cache-Regeln je Quelle."""
    src, ttl = settings.sources, settings.cache
    rules = {
        cache_pattern(src.oparl.endpoint): ttl.oparl_pages_s,
        cache_pattern(src.opendata.results_url): ttl.opendata_s,
        cache_pattern(src.opendata.districts_url): ttl.opendata_s,
        cache_pattern(src.wikidata.sparql_endpoint): ttl.wikidata_s,
        cache_pattern(src.wikidata.wikipedia_api): ttl.wikipedia_s,
        cache_pattern(src.osm.overpass_endpoint): ttl.overpass_s,
        # Option 03: die Fremddaten je Raumeinheit kommen vom selben Portal, also dieselbe Dauer.
        **{cache_pattern(f.url): ttl.opendata_s for f in settings.context.files.all()},
    }
    return make_session(
        timeout_s=settings.http.timeout_s,
        retries=settings.http.retries,
        user_agent=settings.http.user_agent,
        cache_path=cache_path,
        cache_rules=rules,
    )
