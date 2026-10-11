from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
import requests

from georep.errors import FetchError, NetworkError
from georep.settings import Period
from georep.sources.oparl import fetch_organizations, fetch_papers
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
    with pytest.raises(NetworkError, match="Seite 2 weg"):
        fetch_papers(FakeSession(routes), PAGE1, PERIOD)
    routes[PAGE2] = response(PAGE2, content=b"{ kaputt")
    with pytest.raises(FetchError, match="page=2"):
        fetch_papers(FakeSession(routes), PAGE1, PERIOD)
    routes[PAGE2] = response(PAGE2, payload={"data": "keine Liste", "links": {}})
    with pytest.raises(FetchError, match="page=2"):
        fetch_papers(FakeSession(routes), PAGE1, PERIOD)


# --- Option 04: Zähler für Urheberfelder und der Abruf der Organisationen -------------------------


def test_the_report_counts_papers_with_an_originator_field() -> None:
    """Der Zähler ist die Probe, ob der Server inzwischen Urheber liefert; er zählt alle gesehenen
    Paper, auch die außerhalb der Periode und die gelöschten."""
    routes = _routes()
    assert fetch_papers(FakeSession(routes), PAGE1, PERIOD)[1].originators == 0
    with_field = _paper(7, "2025-09-14")
    with_field["originatorOrganization"] = [f"{ORGANIZATIONS}/gr/49"]
    outside = _paper(8, "2026-10-07")
    outside["originatorPerson"] = [f"{ORGANIZATIONS.replace('organizations', 'persons')}/1"]
    routes[PAGE1] = _page(PAGE1, [with_field, outside], PAGE2)
    _, report = fetch_papers(FakeSession(routes), PAGE1, PERIOD)
    assert report.originators == 2 and report.kept == 2
    assert "davon 2 mit Urheberfeld" in report.summary()


ORGANIZATIONS = "https://ris.invalid/organizations"
ORG_PAGE2 = "https://ris.invalid/organizations?page=2"


def _organization(number: int, name: str, deleted: bool = False) -> dict[str, Any]:
    return {
        "id": f"{ORGANIZATIONS}/gr/{number}",
        "type": "https://schema.oparl.org/1.1/Organization",
        "name": name,
        "shortName": name.split("-")[0],
        "classification": "Fraktion",
        "membership": [f"{ORGANIZATIONS}/gr/{number}/memberships/1"],
        "deleted": deleted,
    }


def _org_page(url: str, items: list[dict[str, Any]], next_url: str | None) -> Any:
    links = {"self": url, **({"next": next_url} if next_url else {})}
    return response(url, payload={"data": items, "pagination": {"currentPage": 1}, "links": links})


def test_fetch_organizations_follows_pages_and_skips_deleted() -> None:
    routes = {
        ORGANIZATIONS: _org_page(
            ORGANIZATIONS,
            [_organization(44, "CDU-Ratsfraktion"), _organization(49, "FDP-Ratsfraktion")],
            ORG_PAGE2,
        ),
        ORG_PAGE2: _org_page(
            ORG_PAGE2,
            [
                _organization(66, "Ratsfraktion Die Linke"),
                _organization(63, "REP-Fraktion", deleted=True),
                _organization(44, "CDU-Ratsfraktion"),  # Dublette über die Seitengrenze
            ],
            None,
        ),
    }
    slept: list[float] = []
    found, pages = fetch_organizations(
        FakeSession(routes), ORGANIZATIONS, delay_s=0.25, sleep=slept.append
    )
    assert pages == 2 and slept == [0.25]
    assert [o.short_name for o in found] == ["CDU", "FDP", "Ratsfraktion Die Linke"]
    assert all(not o.deleted for o in found)
    assert found[0].classification == "Fraktion" and found[0].membership


def test_fetch_organizations_propagates_network_and_format_errors() -> None:
    routes: dict[str, Any] = {ORGANIZATIONS: requests.ConnectionError("Server weg")}
    with pytest.raises(NetworkError, match="Server weg"):
        fetch_organizations(FakeSession(routes), ORGANIZATIONS)
    routes[ORGANIZATIONS] = response(ORGANIZATIONS, content=b"{ kaputt")
    with pytest.raises(FetchError, match="Organisationsseite"):
        fetch_organizations(FakeSession(routes), ORGANIZATIONS)
    routes[ORGANIZATIONS] = response(ORGANIZATIONS, payload={"data": {"keine": "Liste"}})
    with pytest.raises(FetchError, match="Organisationsseite"):
        fetch_organizations(FakeSession(routes), ORGANIZATIONS)
