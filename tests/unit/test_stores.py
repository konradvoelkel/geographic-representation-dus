from __future__ import annotations

import datetime as dt
from pathlib import Path

from georep.oparl import OparlPaper, PaperPage
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


# --- Option 04: Urheberfelder im Record ----------------------------------------------------------


def test_record_carries_the_originator_tuples_from_oparl() -> None:
    paper = OparlPaper.model_validate(
        {
            "id": "https://ris.invalid/papers/1",
            "date": "2024-01-02",
            "originatorPerson": ["https://ris.invalid/persons/7"],
            "originatorOrganization": ["https://ris.invalid/organizations/gr/49"],
            "underDirectionOf": ["https://ris.invalid/organizations/amt/66"],
            "consultation": [
                {"organization": ["https://ris.invalid/organizations/gr/25"]},
                {"organization": "https://ris.invalid/organizations/gr/6"},
            ],
        }
    )
    record = PaperRecord.from_oparl(paper)
    assert record.originator_person == ("https://ris.invalid/persons/7",)
    assert record.originator_organization == ("https://ris.invalid/organizations/gr/49",)
    assert record.under_direction_of == ("https://ris.invalid/organizations/amt/66",)
    assert record.consultation_organizations == (
        "https://ris.invalid/organizations/gr/25",
        "https://ris.invalid/organizations/gr/6",
    )
    assert hash(record)  # frozen und hashbar: Tupel, keine Listen
    assert record.has_originator


def test_legacy_lines_without_the_new_keys_still_load(tmp_path: Path) -> None:
    """Die 19 108 Zeilen aus ``from_legacy`` tragen die Schlüssel nicht; Standard ist leer."""
    path = tmp_path / "raw" / "papers.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text('{"id":"p1","name":"A","date":"2024-01-01"}\n', encoding="utf-8")
    record = PaperStore(path).load()["p1"]
    assert record.originator_person == () and record.consultation_organizations == ()
    assert not record.has_originator
    legacy = PaperRecord.from_legacy({"id": "u1", "download_url": "https://ris.invalid/dl/1.pdf"})
    assert legacy.originator_organization == () and not legacy.has_originator


def test_upsert_replaces_a_legacy_record_with_the_server_record(tmp_path: Path) -> None:
    """Ohne ``modified`` auf beiden Seiten gewinnt der eingehende Record: die Urheber kommen an."""
    store = PaperStore(tmp_path / "raw" / "papers.jsonl")
    store.save([_record(1)])
    with_originator = _record(1).model_copy(
        update={"originator_organization": ("https://ris.invalid/organizations/gr/49",)}
    )
    assert _record(1) != with_originator  # Gleichheit sieht die neuen Felder
    report = store.upsert([with_originator])
    assert (report.added, report.updated, report.unchanged) == (0, 1, 0)
    assert store.load()["p001"].originator_organization == (
        "https://ris.invalid/organizations/gr/49",
    )
    assert store.upsert([with_originator]).unchanged == 1  # idempotent nach dem Roundtrip


# --- Option 07: Monitoring der laufenden Wahlperiode ------------------------------------------


def test_upsert_removes_deleted_papers_and_counts_only_the_known_ones(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "raw" / "papers.jsonl")
    store.save([_record(1), _record(2), _record(3)])
    report = store.upsert([_record(4)], deleted=["p002", "p999", "p002"])
    assert (report.added, report.removed, report.total) == (1, 1, 3)  # p999 kannte der Store nicht
    assert list(store.load()) == ["p001", "p003", "p004"]
    assert "1 entfernt" in report.summary()
    # Ohne Löschung nennt die Zusammenfassung keine Entfernung
    assert "entfernt" not in store.upsert([_record(5)]).summary()
    # Eine Löschung gewinnt über ein Update derselben ID im gleichen Aufruf
    both = store.upsert([_record(5, name="neu")], deleted=["p005"])
    assert both.removed == 1 and "p005" not in store.load()


def test_two_upserts_without_change_write_identical_bytes(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "raw" / "papers.jsonl")
    store.upsert([_record(2), _record(1)], deleted=["p009"])
    first = store.path.read_bytes()
    store.upsert([_record(1), _record(2)], deleted=["p009"])
    assert store.path.read_bytes() == first


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
