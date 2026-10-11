from __future__ import annotations

from pathlib import Path

from georep.http import CachedTimeoutSession, cache_pattern
from georep.settings import load_settings
from georep.sources import cached_session


def test_cached_session_carries_rules_timeout_and_user_agent(tmp_path: Path) -> None:
    settings = load_settings(cwd=Path("/nonexistent"))
    session = cached_session(settings, tmp_path / "cache" / "http.sqlite")
    assert isinstance(session, CachedTimeoutSession)
    assert session.timeout_s == settings.http.timeout_s
    assert session.headers["User-Agent"] == settings.http.user_agent
    rules = session.settings.urls_expire_after or {}
    assert rules[cache_pattern(settings.sources.oparl.endpoint)] == settings.cache.oparl_pages_s
    assert rules[cache_pattern(settings.sources.osm.overpass_endpoint)] == settings.cache.overpass_s
    assert (tmp_path / "cache").is_dir()
