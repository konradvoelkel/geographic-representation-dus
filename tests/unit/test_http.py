from __future__ import annotations

from typing import Any

import pytest
import requests
from requests.adapters import HTTPAdapter

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


def test_user_agent_names_the_project() -> None:
    assert "georep" in make_session().headers["User-Agent"]
