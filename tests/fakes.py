"""Netz als Eingabe: eine Session, die aus einer Tabelle antwortet, und echte ``requests.Response``."""

from __future__ import annotations

import json
from typing import Any

import requests


def response(
    url: str, *, status: int = 200, content: bytes = b"", payload: object = None
) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp.url = url
    resp.reason = "OK" if status < 400 else "Error"
    resp._content = json.dumps(payload).encode() if payload is not None else content
    return resp


class FakeSession:
    """Antwortet aus ``routes`` (URL -> Response oder Exception) und zählt die Aufrufe mit Parametern."""

    def __init__(self, routes: dict[str, requests.Response | Exception]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, Any]] = []

    def get(self, url: str, *, params: Any = None, headers: Any = None) -> requests.Response:
        self.calls.append((url, params))
        answer = self.routes[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def post(self, url: str, *, data: Any = None, headers: Any = None) -> requests.Response:
        self.calls.append((url, data))
        answer = self.routes[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    @property
    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]
