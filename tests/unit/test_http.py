from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.response import HTTPResponse

from georep.http import RETRY_STATUSES, make_session


def _capture(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake_request(
        self: requests.Session, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        seen.update(kwargs)
        response = requests.Response()
        response.status_code = 200
        return response

    monkeypatch.setattr(requests.Session, "request", fake_request)
    return seen


def test_default_timeout_is_passed_to_every_call(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture(monkeypatch)
    make_session(timeout_s=7).get("https://example.invalid/x")
    assert seen["timeout"] == 7


def test_explicit_timeout_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture(monkeypatch)
    make_session(timeout_s=7).get("https://example.invalid/x", timeout=3)
    assert seen["timeout"] == 3


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_retry_is_mounted_for_both_schemes(scheme: str) -> None:
    adapter = make_session(retries=3).get_adapter(f"{scheme}://example.invalid/")
    assert isinstance(adapter, HTTPAdapter)
    retry = adapter.max_retries
    assert retry.total == 3
    assert set(RETRY_STATUSES) <= set(retry.status_forcelist)
    assert retry.backoff_factor > 0
    # Punkt 55: 504 und 429 stehen in der Liste, POST aber nicht in den Methoden -- die
    # Overpass-Abfrage ist ein POST und wird darum hier nicht wiederholt, sondern in
    # georep.sources.overpass mit injizierbarer Pause. Wer POST hier aufnimmt, wiederholt doppelt.
    assert retry.allowed_methods is not None
    assert "POST" not in retry.allowed_methods and {"GET", "HEAD"} <= set(retry.allowed_methods)


def test_user_agent_names_the_project() -> None:
    assert "georep" in make_session().headers["User-Agent"]


def test_cached_session_serves_repeats_from_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []

    def fake_send(
        self: requests.Session, request: requests.PreparedRequest, **kwargs: Any
    ) -> requests.Response:
        sent.append(str(request.url))
        body = b'{"ok": true}'
        raw = HTTPResponse(
            body=io.BytesIO(body),
            headers={"Content-Type": "application/json"},
            status=200,
            preload_content=False,
            request_url=str(request.url),
        )
        resp = requests.Response()
        resp.status_code = 200
        resp.url = str(request.url)
        resp.request = request
        resp.raw = raw
        resp._content = body
        resp.headers["Content-Type"] = "application/json"
        return resp

    monkeypatch.setattr(requests.Session, "send", fake_send)
    session = make_session(
        cache_path=tmp_path / "http.sqlite",
        cache_rules={"api.invalid/cached*": 3600, "api.invalid/never*": 0},
    )
    for _ in range(3):
        assert session.get("https://api.invalid/cached/x").json() == {"ok": True}
    assert sent.count("https://api.invalid/cached/x") == 1
    for _ in range(2):
        session.get("https://api.invalid/never/y")
    assert sent.count("https://api.invalid/never/y") == 2
    for _ in range(2):
        session.get("https://other.invalid/z")  # keine Regel: nicht gecacht
    assert sent.count("https://other.invalid/z") == 2
    assert (tmp_path / "http.sqlite").exists()


def test_cache_pattern_drops_scheme_and_adds_wildcard() -> None:
    from georep.http import cache_pattern

    assert (
        cache_pattern("https://ris.invalid/Oparl/bodies/0015/papers")
        == "ris.invalid/Oparl/bodies/0015/papers*"
    )


def test_a_url_with_a_query_string_still_gets_its_cache_rule() -> None:
    """Punkt 62: die Flächen einer Stadt dürfen eine Operation sein (``identify?…&f=json``).

    ``cache_pattern`` lässt den Query-String weg und endet mit ``*``; dass requests-cache damit
    trotzdem die ganze Anfrage trifft, ist eine Annahme über eine fremde Bibliothek und darum ein
    Test: sie vergleicht die **vollständige** URL ohne Schema gegen das Muster. Trifft es nicht
    mehr, wird die Antwort nicht gecacht und jeder Lauf holt sie neu (1 MB).
    """
    from requests_cache.policy.expiration import get_url_expiration

    from georep.http import cache_pattern

    url = (
        "https://geo.invalid/server/rest/services/Wahlen/MapServer/identify"
        "?geometry=310000,5662000,328000,5681000&layers=all:16&returnGeometry=true&f=json"
    )
    assert cache_pattern(url).endswith("/MapServer/identify*")
    assert get_url_expiration(url, {cache_pattern(url): 3600}) == 3600
    # Und sie trifft nicht alles: ein anderer Pfad desselben Dienstes bleibt ungecacht
    assert get_url_expiration(url.replace("/identify?", "/query?"), {cache_pattern(url): 3600}) is (
        None
    )
