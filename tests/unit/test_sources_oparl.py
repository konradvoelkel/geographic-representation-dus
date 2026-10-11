from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
import requests

from georep.errors import FetchError
from georep.settings import Period
from georep.sources.oparl import fetch_papers
from tests.fakes import FakeSession, response

PAGE1 = "https://ris.invalid/papers"
PAGE2 = "https://ris.invalid/papers?page=2"
PAGE3 = "https://ris.invalid/papers?page=3"
PERIOD = Period(start=dt.date(2020, 9, 13), end=dt.date(2025, 9, 14))


def _paper(i: int, date: str, deleted: bool = False) -> dict[str, Any]:
    return {
        "id": f"https://ris.invalid/papers/{i}",
        "type": "https://schema.oparl.org/1.1/Paper",
        "name": f"P{i}",
        "reference": f"r{i}",
        "date": date,
        "paperType": "Antrag",
        "mainFile": {
            "id": f"https://ris.invalid/files/{i}",
            "fileName": f"{i:08d}.pdf",
            "downloadUrl": f"https://ris.invalid/downloadfiles/{i:08d}.pdf",
        },
        "created": f"{date}T10:00:00+02:00",
        "modified": f"{date}T11:00:00+02:00",
        "deleted": deleted,
    }


def _page(url: str, papers: list[dict[str, Any]], next_url: str | None) -> Any:
    links = {"self": url, **({"next": next_url} if next_url else {})}
    return response(
        url, payload={"data": papers, "pagination": {"elementsPerPage": 2}, "links": links}
    )


def _routes() -> dict[str, Any]:
    return {
        PAGE1: _page(PAGE1, [_paper(1, "2026-10-07"), _paper(2, "2025-09-14")], PAGE2),
        PAGE2: _page(
            PAGE2, [_paper(3, "2021-02-02", deleted=True), _paper(4, "2020-09-13")], PAGE3
        ),
        PAGE3: _page(PAGE3, [_paper(5, "2019-12-31"), _paper(6, "2015-01-01")], None),
    }


def test_fetch_keeps_period_skips_deleted_and_stops_when_older() -> None:
    session = FakeSession(_routes())
    slept: list[float] = []
    records, report = fetch_papers(session, PAGE1, PERIOD, delay_s=0.5, sleep=slept.append)
    assert [r.id.rsplit("/", 1)[-1] for r in records] == [
        "2",
        "4",
    ]  # Grenzen einschließlich, 3 gelöscht
    assert records[0].file_name == "00000002.pdf" and records[0].modified is not None
    assert (report.pages, report.seen, report.kept, report.stopped_early) == (3, 6, 2, True)
    assert "Rest älter" in report.summary()
    assert session.urls == [PAGE1, PAGE2, PAGE3]
    assert slept == [0.5, 0.5]


def test_fetch_without_early_stop_follows_all_links_until_last_page() -> None:
    routes = _routes()
    routes[PAGE3] = _page(PAGE3, [_paper(5, "2019-12-31")], None)
    _, report = fetch_papers(FakeSession(routes), PAGE1, PERIOD, stop_when_older=False)
    assert (report.pages, report.stopped_early) == (3, False)


def test_modified_since_goes_only_on_the_first_request() -> None:
    session = FakeSession(_routes())
    since = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
    fetch_papers(session, PAGE1, PERIOD, modified_since=since, max_pages=2)
    assert session.calls[0] == (PAGE1, {"modified_since": "2026-10-01T00:00:00+00:00"})
    assert session.calls[1] == (PAGE2, None)
    assert len(session.calls) == 2


def test_fetch_propagates_network_and_format_errors() -> None:
    routes = _routes()
    routes[PAGE2] = requests.ConnectionError("Seite 2 weg")
    with pytest.raises(requests.ConnectionError):
        fetch_papers(FakeSession(routes), PAGE1, PERIOD)
    routes[PAGE2] = response(PAGE2, content=b"{ kaputt")
    with pytest.raises(FetchError, match="page=2"):
        fetch_papers(FakeSession(routes), PAGE1, PERIOD)
    routes[PAGE2] = response(PAGE2, payload={"data": "keine Liste", "links": {}})
    with pytest.raises(FetchError, match="page=2"):
        fetch_papers(FakeSession(routes), PAGE1, PERIOD)
