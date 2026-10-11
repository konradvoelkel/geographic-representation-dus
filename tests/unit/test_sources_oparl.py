from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
import requests

from georep.errors import FetchError, NetworkError
from georep.settings import Period
from georep.sources.oparl import (
    fetch_organizations,
    fetch_papers,
    read_progress,
    start_url,
    write_progress,
)
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


# --- Option 02: Startseite und Wiederaufnahme --------------------------------------------------

PAGE4 = "https://ris.invalid/papers?page=4"
OLD = Period(start=dt.date(2014, 5, 25), end=dt.date(2020, 9, 12))


def test_start_url_is_the_endpoint_for_page_one() -> None:
    assert start_url(PAGE1, 1) == PAGE1
    assert start_url(PAGE1, 0) == PAGE1  # der Validator verhindert 0, die Funktion knickt nicht ein
    assert start_url(PAGE1, 90) == f"{PAGE1}?page=90"


def _old_routes() -> dict[str, Any]:
    """Vier Seiten ab Seite 2, alle in der alten Periode; Seite 4 ist die letzte."""
    return {
        PAGE2: _page(PAGE2, [_paper(1, "2019-01-01"), _paper(2, "2018-06-01")], PAGE3),
        PAGE3: _page(PAGE3, [_paper(3, "2017-01-01"), _paper(4, "2016-06-01")], PAGE4),
        PAGE4: _page(PAGE4, [_paper(5, "2015-01-01"), _paper(6, "2014-06-01")], None),
    }


def test_fetch_starts_at_the_given_page_and_names_both_ends() -> None:
    session = FakeSession(_old_routes())
    records, report = fetch_papers(session, PAGE1, OLD, first_page=2)
    assert session.urls == [PAGE2, PAGE3, PAGE4]
    assert len(records) == 6 and report.pages == 3
    assert report.first_url == PAGE2 and report.next_url is None
    assert "ab https://ris.invalid/papers?page=2" in report.summary()


def test_on_page_sees_every_page_and_the_next_url() -> None:
    session = FakeSession(_old_routes())
    seen: list[tuple[int, str | None]] = []
    fetch_papers(
        session,
        PAGE1,
        OLD,
        first_page=2,
        on_page=lambda kept, next_url: seen.append((len(kept), next_url)),
    )
    assert seen == [(2, PAGE3), (2, PAGE4), (2, None)]


def test_a_broken_page_leaves_the_progress_of_the_pages_before_it(tmp_path: Path) -> None:
    """Der Abbruch mitten im Abruf: die Seiten davor sind gespeichert, der Rest wird fortgesetzt."""
    progress = tmp_path / "papers.progress.json"
    routes = _old_routes()
    routes[PAGE3] = requests.ConnectionError("Verbindung weg")
    session = FakeSession(routes)
    pages = 0
    kept_ids: list[str] = []

    def done(kept: list[Any], next_url: str | None) -> None:
        nonlocal pages
        pages += 1
        kept_ids.extend(r.id for r in kept)
        write_progress(progress, next_url, pages)

    with pytest.raises(NetworkError):
        fetch_papers(session, PAGE1, OLD, first_page=2, on_page=done)
    assert read_progress(progress) == PAGE3
    assert len(kept_ids) == 2

    routes[PAGE3] = _old_routes()[PAGE3]
    records, report = fetch_papers(
        FakeSession(routes), PAGE1, OLD, resume_from=read_progress(progress), on_page=done
    )
    assert report.first_url == PAGE3 and report.next_url is None
    assert sorted(kept_ids + [r.id for r in records])[:2] == sorted(kept_ids)[:2]
    assert len({*kept_ids, *(r.id for r in records)}) == 6  # jedes Paper genau einmal
    assert read_progress(progress) is None


def test_unreadable_or_finished_progress_starts_from_the_front(tmp_path: Path) -> None:
    missing = tmp_path / "fehlt.json"
    assert read_progress(missing) is None
    broken = tmp_path / "kaputt.json"
    broken.write_text("{nicht json", encoding="utf-8")
    assert read_progress(broken) is None
    finished = tmp_path / "fertig.json"
    write_progress(finished, None, 7)
    assert read_progress(finished) is None
    assert json.loads(finished.read_text(encoding="utf-8"))["pages"] == 7
