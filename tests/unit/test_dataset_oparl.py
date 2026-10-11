"""Download-Funktionen des Altcodes gegen eine Fake-Session: Fehler pro Datei, Resume, Bericht."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import requests

import src.config as cfg
from src.dataset_oparl import Paper, download_paper_metadata, download_paper_pdf

PDF = b"%PDF-1.4\n%fake\n"


def _response(
    url: str, *, status: int = 200, content: bytes = b"", payload: object = None
) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.url = url
    response.reason = "OK" if status < 400 else "Error"
    response._content = json.dumps(payload).encode() if payload is not None else content
    return response


class FakeSession:
    """Antwortet aus einer Tabelle URL -> Response oder Exception und zählt die Aufrufe."""

    def __init__(self, routes: dict[str, requests.Response | Exception]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url: str, *, params: Any = None, headers: Any = None) -> requests.Response:
        self.calls.append(url)
        answer = self.routes[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


def _paper(i: int, url: str) -> Paper:
    return Paper(
        id=f"p{i}",
        name=f"Paper {i}",
        reference="",
        date="2024-01-01",
        paperType="Antrag",
        mainFile="",
        download_url=url,
    )


def test_pdf_download_isolates_failures(tmp_path: Path) -> None:
    urls = [f"https://ris.invalid/dl/{n}.pdf" for n in ("a", "b", "c")]
    session = FakeSession(
        {
            urls[0]: _response(urls[0], content=PDF),
            urls[1]: requests.ConnectionError("kaputt"),
            urls[2]: _response(urls[2], content=PDF),
        }
    )
    report = download_paper_pdf([_paper(i, u) for i, u in enumerate(urls)], session, tmp_path)
    assert (report.downloaded, report.failed, report.skipped) == (2, 1, 0)
    assert report.errors == [(urls[1], "kaputt")]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.pdf", "c.pdf"]
    assert (tmp_path / "a.pdf").read_bytes() == PDF


def test_pdf_download_counts_http_errors_as_failures(tmp_path: Path) -> None:
    url = "https://ris.invalid/dl/x.pdf"
    report = download_paper_pdf(
        [_paper(1, url)], FakeSession({url: _response(url, status=500)}), tmp_path
    )
    assert (report.downloaded, report.failed) == (0, 1)
    assert not (tmp_path / "x.pdf").exists()


def test_pdf_download_skips_existing_files_without_touching_the_network(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").write_bytes(PDF)
    session = FakeSession({})
    report = download_paper_pdf(
        [_paper(1, "https://ris.invalid/dl/a.pdf"), _paper(2, "")], session, tmp_path
    )
    assert (report.downloaded, report.skipped, report.failed) == (0, 2, 0)
    assert session.calls == []


@pytest.fixture
def metadata_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cfg, "PAPER_OBJECT_LISTE", tmp_path / "paper_objects.json")
    monkeypatch.setattr(cfg, "PAPER_URL_LISTE", tmp_path / "paper_urls.json")
    monkeypatch.setattr(cfg, "DELAY", 0)
    return tmp_path


PAGE1 = "https://ris.invalid/papers"
PAGE2 = "https://ris.invalid/papers?page=2"


def _pages() -> dict[str, requests.Response | Exception]:
    page1 = {
        "data": [
            {
                "id": "u1",
                "name": "A",
                "reference": "r1",
                "date": "2024-05-01",
                "paperType": "Antrag",
                "mainFile": {"id": "f1", "downloadUrl": "https://ris.invalid/dl/f1.pdf"},
            },
            {
                "id": "u2",
                "name": "alt",
                "reference": "r2",
                "date": "2019-01-01",
                "paperType": "Antrag",
                "mainFile": {"id": "f2", "downloadUrl": "https://ris.invalid/dl/f2.pdf"},
            },
        ],
        "links": {"next": PAGE2},
    }
    page2 = {
        "data": [
            {
                "id": "u3",
                "name": "C",
                "reference": "r3",
                "date": "2021-02-02",
                "paperType": "Anfrage",
                "auxiliaryFile": [{"id": "f3", "downloadUrl": "https://ris.invalid/dl/f3.pdf"}],
            },
        ],
        "links": {},
    }
    return {PAGE1: _response(PAGE1, payload=page1), PAGE2: _response(PAGE2, payload=page2)}


def test_metadata_follows_pages_and_filters_by_period(metadata_paths: Path) -> None:
    papers = download_paper_metadata(PAGE1, FakeSession(_pages()))
    assert [p.id for p in papers] == ["u1", "u3"]
    assert papers[1].download_url == "https://ris.invalid/dl/f3.pdf"
    saved = json.loads((metadata_paths / "paper_objects.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in saved] == ["u1", "u3"]
    assert json.loads((metadata_paths / "paper_urls.json").read_text()) == [PAGE1, PAGE2]


def test_metadata_failure_raises_after_saving_partial_state(metadata_paths: Path) -> None:
    routes = _pages()
    routes[PAGE2] = requests.ConnectionError("Seite 2 weg")
    with pytest.raises(requests.ConnectionError):
        download_paper_metadata(PAGE1, FakeSession(routes))
    saved = json.loads((metadata_paths / "paper_objects.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in saved] == ["u1"]


def test_metadata_resume_skips_known_ids(metadata_paths: Path) -> None:
    known = [
        {
            "id": "u1",
            "name": "A",
            "reference": "r1",
            "date": "2024-05-01",
            "paperType": "Antrag",
            "mainFile": "f1",
            "download_url": "https://ris.invalid/dl/f1.pdf",
            "paper_text": "",
        }
    ]
    (metadata_paths / "paper_objects.json").write_text(json.dumps(known), encoding="utf-8")
    papers = download_paper_metadata(PAGE1, FakeSession(_pages()))
    assert [p.id for p in papers] == ["u3"]
    saved = json.loads((metadata_paths / "paper_objects.json").read_text(encoding="utf-8"))
    assert sorted(p["id"] for p in saved) == ["u1", "u3"]
