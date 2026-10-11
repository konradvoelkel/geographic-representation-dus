from __future__ import annotations

import datetime as dt
from pathlib import Path

from georep.oparl import PaperPage
from georep.records import PaperRecord, file_name_from
from georep.stores import PaperStore, TextMeta, TextStore
from tests.conftest import REPO


def _record(i: int, modified: str | None = None, name: str = "A") -> PaperRecord:
    return PaperRecord(
        id=f"p{i:03d}",
        name=name,
        date=dt.date(2024, 1, 1),
        file_name=f"{i}.pdf",
        download_url=f"https://ris.invalid/dl/{i}.pdf",
        modified=dt.datetime.fromisoformat(modified) if modified else None,
    )


def test_record_from_oparl_fixture() -> None:
    page = PaperPage.model_validate_json(
        (REPO / "tests" / "fixtures" / "oparl" / "papers_page.json").read_text(encoding="utf-8")
    )
    records = [PaperRecord.from_oparl(p) for p in page.data]
    assert all(r.file_name and r.file_name.endswith(".pdf") for r in records)
    assert all(r.download_url and r.download_url.endswith(r.file_name or "") for r in records)
    assert all(r.modified is not None and r.modified.tzinfo is not None for r in records)
    assert records[0].paper_type == page.data[0].paper_type


def test_record_from_legacy_entry() -> None:
    record = PaperRecord.from_legacy(
        {
            "id": "u1",
            "name": "A",
            "reference": "r",
            "date": "2024-05-01",
            "paperType": "Antrag",
            "mainFile": "f1",
            "download_url": "https://ris.invalid/dl/00000001.pdf",
            "paper_text": "x",
        }
    )
    assert record.file_name == "00000001.pdf" and record.date == dt.date(2024, 5, 1)
    assert record.paper_type == "Antrag" and record.modified is None
    assert file_name_from(None, "x.pdf") == "x.pdf" and file_name_from("", None) is None


def test_paper_store_roundtrip_sorted_and_upsert(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "raw" / "papers.jsonl")
    assert store.load() == {}
    store.save([_record(2), _record(1)])
    assert list(store.load()) == ["p001", "p002"]
    report = store.upsert([_record(1), _record(3, "2025-01-01T00:00:00+00:00")])
    assert (report.added, report.updated, report.unchanged, report.total) == (1, 0, 1, 3)
    older = _record(3, "2024-01-01T00:00:00+00:00", name="älter")
    newer = _record(3, "2026-01-01T00:00:00+00:00", name="neuer")
    assert store.upsert([older]).updated == 0  # älteres modified verliert
    assert store.upsert([newer]).updated == 1
    assert store.load()["p003"].name == "neuer"
    assert "1 neu" in store.upsert([_record(9)]).summary()


def test_text_store_put_get_save_and_currency(tmp_path: Path) -> None:
    store = TextStore(tmp_path / "text" / "texts.parquet")
    assert len(store) == 0 and store.get("a.pdf") is None
    store.put("a.pdf", "hallo welt", TextMeta(extractor="pypdf-6", pdf_sha256="abc"))
    store.put("b.pdf", "", TextMeta(extractor="pypdf-6", source="reference"))
    store.save()
    again = TextStore(tmp_path / "text" / "texts.parquet")
    assert again.get("a.pdf") == "hallo welt" and "a.pdf" in again and len(again) == 2
    assert again.meta("a.pdf") == TextMeta(extractor="pypdf-6", pdf_sha256="abc", chars=10)
    assert again.meta("b.pdf") == TextMeta(extractor="pypdf-6", source="reference", chars=0)
    assert again.is_current("a.pdf", pdf_sha256="abc", extractor="pypdf-6")
    assert not again.is_current("a.pdf", pdf_sha256="abd", extractor="pypdf-6")
    assert not again.is_current("a.pdf", pdf_sha256="abc", extractor="pypdf-7")
    assert not again.is_current("b.pdf", pdf_sha256=None, extractor="pypdf-7")
    assert again.is_current("b.pdf", pdf_sha256=None, extractor="pypdf-6")
