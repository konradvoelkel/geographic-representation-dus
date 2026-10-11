from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import requests

from georep.records import PaperRecord
from georep.sources.pdfs import PdfStore
from tests.fakes import FakeSession, response

PDF = b"%PDF-1.4\n%fake\n"


def _record(name: str) -> PaperRecord:
    return PaperRecord(
        id=f"p-{name}",
        date=dt.date(2024, 1, 1),
        file_name=name or None,
        download_url=f"https://ris.invalid/dl/{name}" if name else None,
    )


def test_download_isolates_failures_and_writes_manifest(tmp_path: Path) -> None:
    urls = {n: f"https://ris.invalid/dl/{n}" for n in ("a.pdf", "b.pdf", "c.pdf", "d.pdf")}
    session = FakeSession(
        {
            urls["a.pdf"]: response(urls["a.pdf"], content=PDF),
            urls["b.pdf"]: requests.ConnectionError("kaputt"),
            urls["c.pdf"]: response(urls["c.pdf"], status=500),
            urls["d.pdf"]: response(urls["d.pdf"], content=b"<html>404</html>"),
        }
    )
    store = PdfStore(tmp_path / "pdf")
    slept: list[float] = []
    report = store.download(session, [_record(n) for n in urls], delay_s=0.1, sleep=slept.append)
    assert (report.downloaded, report.failed, report.skipped) == (1, 3, 0)
    assert [u for u, _ in report.errors] == [urls["b.pdf"], urls["c.pdf"], urls["d.pdf"]]
    assert "kein PDF" in report.errors[2][1]
    assert store.names() == {"a.pdf"} and store.has("a.pdf") and not store.has("d.pdf")
    assert len(slept) == 4  # Pause nach jedem Versuch, nicht nach Übersprungenem
    lines = [json.loads(line) for line in store.manifest.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 1 and lines[0]["name"] == "a.pdf" and lines[0]["size"] == len(PDF)
    assert lines[0]["sha256"] == store.sha256("a.pdf")


def test_download_skips_existing_and_records_without_url_and_honours_limit(tmp_path: Path) -> None:
    store = PdfStore(tmp_path / "pdf")
    store.directory.mkdir()
    (store.directory / "a.pdf").write_bytes(PDF)
    urls = {n: f"https://ris.invalid/dl/{n}" for n in ("b.pdf", "c.pdf")}
    session = FakeSession({u: response(u, content=PDF) for u in urls.values()})
    report = store.download(
        session, [_record("a.pdf"), _record(""), _record("b.pdf"), _record("c.pdf")], limit=1
    )
    assert (report.downloaded, report.skipped, report.failed) == (1, 2, 0)
    assert session.urls == [urls["b.pdf"]]
    assert store.names() == {"a.pdf", "b.pdf"}
