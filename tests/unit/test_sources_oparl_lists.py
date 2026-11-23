"""Fundament F6: der Listenabruf für Sitzungen, Beratungen und Personen, gegen die Fake-Session."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
import requests

from georep.errors import FetchError, NetworkError
from georep.oparl import OparlConsultation, OparlMeeting, OparlPerson
from georep.sources.oparl import fetch_objects
from tests.conftest import REPO
from tests.fakes import FakeSession, response

LIST = "https://ris.invalid/meetings"
PAGE2 = f"{LIST}?page=2"
PAGE3 = f"{LIST}?page=3"
HTTP = REPO / "tests" / "fixtures" / "http"


def _meeting(i: int, day: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"https://ris.invalid/meetings/{i}",
        "start": f"{day}T15:00:00+01:00",
        "modified": f"{day}T18:00:00+01:00",
        **extra,
    }


def _page(items: list[dict[str, Any]], next_url: str | None = None) -> dict[str, Any]:
    links = {"self": LIST} | ({"next": next_url} if next_url else {})
    return {"data": items, "pagination": {"elementsPerPage": 200}, "links": links}


def _session(*pages: dict[str, Any]) -> FakeSession:
    urls = [LIST, PAGE2, PAGE3][: len(pages)]
    return FakeSession(
        {url: response(url, payload=page) for url, page in zip(urls, pages, strict=True)}
    )


def _three_pages() -> FakeSession:
    return _session(
        _page([_meeting(9, "2026-03-01"), _meeting(8, "2025-11-01")], PAGE2),
        _page([_meeting(7, "2024-05-01")], PAGE3),
        _page([_meeting(6, "2021-01-01")]),
    )


def test_fetch_objects_follows_the_links_to_the_last_page() -> None:
    slept: list[float] = []
    session = _three_pages()
    found, report = fetch_objects(session, LIST, OparlMeeting, delay_s=1.0, sleep=slept.append)
    assert [m.id.rsplit("/", 1)[1] for m in found] == ["9", "8", "7", "6"]
    assert all(isinstance(m, OparlMeeting) for m in found)
    assert (report.pages, report.seen, report.kept) == (3, 4, 4)
    assert report.first_url == LIST and report.next_url is None and not report.stopped_early
    assert session.urls == [LIST, PAGE2, PAGE3] and slept == [1.0, 1.0]
    assert "3 Seite(n), 4 gesehen, 4 behalten" in report.summary()


def test_keep_filters_objects_and_older_stops_after_the_first_old_page() -> None:
    """Die Listen sind neueste zuerst: eine Seite, die ganz vor dem Beginn liegt, ist die letzte."""
    start = dt.date(2025, 1, 1)
    session = _three_pages()
    seen_pages: list[tuple[int, str | None]] = []
    found, report = fetch_objects(
        session,
        LIST,
        OparlMeeting,
        keep=lambda m: m.starts_on_or_after(start),
        older=lambda page: all(not m.starts_on_or_after(start) for m in page),
        on_page=lambda kept, next_url: seen_pages.append((len(kept), next_url)),
    )
    assert [m.id.rsplit("/", 1)[1] for m in found] == ["9", "8"]
    assert report.stopped_early and report.pages == 2 and report.seen == 3 and report.kept == 2
    assert session.urls == [LIST, PAGE2]  # Seite 3 wird nicht mehr gelesen
    assert seen_pages == [(2, PAGE2), (0, None)]
    assert "Rest älter als der Periodenbeginn" in report.summary()


def test_modified_since_goes_only_on_the_first_request() -> None:
    session = _three_pages()
    since = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    fetch_objects(session, LIST, OparlMeeting, modified_since=since)
    assert session.calls[0] == (LIST, {"modified_since": since.isoformat()})
    assert [params for _, params in session.calls[1:]] == [None, None]


def test_deleted_objects_land_in_the_report_and_not_in_the_result() -> None:
    gone = _meeting(8, "2025-11-01", deleted=True)
    session = _session(
        _page([_meeting(9, "2026-03-01"), _meeting(8, "2025-11-01")], PAGE2),
        _page([gone, {"id": "https://ris.invalid/meetings/5", "deleted": True}]),
    )
    found, report = fetch_objects(session, LIST, OparlMeeting)
    assert [m.id.rsplit("/", 1)[1] for m in found] == ["9"]
    assert [i.rsplit("/", 1)[1] for i in report.deleted_ids] == ["8", "5"]
    assert report.kept == 1 and report.seen == 4 and "2 gelöscht" in report.summary()


def test_an_object_on_two_pages_is_kept_once() -> None:
    """Rutscht die Liste während des Abrufs (neue Sitzungen vorn), steht ein Objekt zweimal da."""
    session = _session(
        _page([_meeting(9, "2026-03-01"), _meeting(8, "2025-11-01")], PAGE2),
        _page([_meeting(8, "2025-11-01"), _meeting(7, "2024-05-01")]),
    )
    found, report = fetch_objects(session, LIST, OparlMeeting)
    assert [m.id.rsplit("/", 1)[1] for m in found] == ["9", "8", "7"]
    assert report.seen == 4 and report.kept == 3


def test_max_pages_names_where_the_fetch_would_go_on_and_resume_starts_there() -> None:
    session = _three_pages()
    found, report = fetch_objects(session, LIST, OparlMeeting, max_pages=1)
    assert len(found) == 2 and report.pages == 1 and report.next_url == PAGE2
    assert "weiter bei" in report.summary()
    again = _three_pages()
    rest, resumed = fetch_objects(again, LIST, OparlMeeting, resume_from=report.next_url)
    assert again.urls == [PAGE2, PAGE3] and resumed.first_url == PAGE2
    assert [m.id.rsplit("/", 1)[1] for m in rest] == ["7", "6"]


def test_network_and_format_errors_are_the_two_errors_of_a_fetcher() -> None:
    def fails(answer: requests.Response | Exception) -> None:
        fetch_objects(FakeSession({LIST: answer}), LIST, OparlMeeting)

    with pytest.raises(NetworkError):
        fails(requests.ConnectionError("weg"))
    with pytest.raises(NetworkError):
        fails(response(LIST, status=503))
    with pytest.raises(FetchError, match="keine gültige Seite"):
        fails(response(LIST, content=b"<html>"))
    with pytest.raises(FetchError, match="OparlMeeting"):
        fails(response(LIST, payload=_page([{"name": "ohne id"}])))


def test_the_recorded_pages_go_through_the_fetcher() -> None:
    """Die aufgezeichneten Seiten, wie der Server sie schickt: Sitzungen mit Tagesordnung,
    Personen ohne Kontaktdaten; ``next`` zeigt auf die nächste Seite."""
    for name, model, count in (
        ("oparl_meetings_0015.json", OparlMeeting, 4),
        ("oparl_people_0015.json", OparlPerson, 3),
    ):
        content = (HTTP / name).read_bytes()
        found, report = fetch_objects(
            FakeSession({LIST: response(LIST, content=content)}), LIST, model, max_pages=1
        )
        assert len(found) == count and report.next_url is not None, name
    single = (HTTP / "oparl_consultation_141791.json").read_text(encoding="utf-8")
    page = f'{{"data": [{single}], "links": {{}}}}'.encode()
    found_c, _ = fetch_objects(
        FakeSession({LIST: response(LIST, content=page)}), LIST, OparlConsultation
    )
    assert found_c[0].agenda_item is not None and found_c[0].paper is not None
