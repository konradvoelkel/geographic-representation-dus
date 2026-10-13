"""Netz als Eingabe: eine Session, die aus einer Tabelle antwortet, und echte ``requests.Response``."""

from __future__ import annotations

import json
from collections.abc import Sequence
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


class SequenceSession:
    """Antwortet auf **eine** URL mit einer Folge von Antworten, eine je Aufruf.

    Für Wiederholungen: derselbe Endpunkt antwortet erst 504, dann 200. ``FakeSession`` hält je URL
    genau eine Antwort und kann das nicht. Absichtlich streng — ein Aufruf mehr, als die Folge
    hergibt, ist ein ``IndexError`` und damit ein roter Test, nicht eine stille Wiederholung der
    letzten Antwort. So steht die Zahl der erwarteten Aufrufe in der Folge selbst.
    """

    def __init__(self, url: str, answers: Sequence[requests.Response | Exception]) -> None:
        self.url = url
        self.answers = list(answers)
        self.calls: list[tuple[str, Any]] = []

    def _answer(self, url: str, payload: Any) -> requests.Response:
        self.calls.append((url, payload))
        answer = self.answers[len(self.calls) - 1]  # erschöpft: IndexError, siehe Docstring
        if isinstance(answer, Exception):
            raise answer
        return answer

    def get(self, url: str, *, params: Any = None, headers: Any = None) -> requests.Response:
        return self._answer(url, params)

    def post(self, url: str, *, data: Any = None, headers: Any = None) -> requests.Response:
        return self._answer(url, data)
