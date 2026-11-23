"""Fundament F1: der Rohtextstore neben dem Textstore (``prep/raw_texts.py``, ``stores.py``)."""

from __future__ import annotations

import shutil
from pathlib import Path

import deal
import polars as pl
import pytest

from georep.io import write_parquet
from georep.prep.extract import (
    DEFAULT_EXTRACTOR,
    after_marker,
    extract_missing,
    extract_text,
    normalise_text,
)
from georep.prep.raw_texts import (
    DEFAULT_PAGE_EXTRACTOR,
    PAGE_BREAK,
    RAW_SUFFIX,
    extract_raw_missing,
    flatten,
    raw_extractor_name,
    raw_from_pages,
    restore_form_feeds,
)
from georep.sources.pdfs import PdfStore
from georep.stores import RAW_TEXT_SCHEMA, RAW_TEXT_SCHEMA_VERSION, RawTextStore, TextStore

FILES = ["00438685.pdf", "00439409.pdf", "00519825.pdf", "00552781.pdf"]


def _pdfs(tmp_path: Path, pdf_fixtures: Path, names: list[str]) -> PdfStore:
    pdfs = PdfStore(tmp_path / "pdf")
    pdfs.directory.mkdir()
    for name in names:
        shutil.copy(pdf_fixtures / name, pdfs.directory / name)
    return pdfs


def test_the_raw_extractor_names_library_version_and_suffix() -> None:
    name = raw_extractor_name(DEFAULT_PAGE_EXTRACTOR)
    assert name == f"{DEFAULT_EXTRACTOR.name}{RAW_SUFFIX}" and name.startswith("pypdf-")
    assert name != DEFAULT_EXTRACTOR.name  # sonst wären die beiden Stores verwechselbar


@pytest.mark.parametrize("name", FILES)
def test_the_raw_text_keeps_case_lines_pages_and_the_head(pdf_fixtures: Path, name: str) -> None:
    pages = DEFAULT_PAGE_EXTRACTOR.pages(pdf_fixtures / name)
    raw, feeds = raw_from_pages(pages)
    assert feeds == ()  # keine der vier Fixture-PDFs trägt ein Formfeed im Seitentext
    assert len(pages) >= 1 and raw.count(PAGE_BREAK) == len(pages) - 1
    assert "\n" in raw and raw != raw.lower()
    # Der Vorlagenkopf vor „betrifft" ist da, der Textstore schneidet ihn ab.
    assert flatten(raw, "betrifft", feeds) != normalise_all(raw)
    assert flatten(raw, "betrifft", feeds) == after_marker(
        extract_text(pdf_fixtures / name), "betrifft"
    )


def normalise_all(raw: str) -> str:
    return raw.replace(PAGE_BREAK, "").replace("\n", "").lower()


def test_extract_raw_missing_uses_the_cache_and_isolates_failures(
    pdf_fixtures: Path, tmp_path: Path
) -> None:
    pdfs = _pdfs(tmp_path, pdf_fixtures, FILES)
    (pdfs.directory / "kaputt.pdf").write_bytes(b"%PDF-1.4 aber kaputt")
    raw = RawTextStore(tmp_path / "text" / "rohtexte.parquet")
    names = [*FILES, "kaputt.pdf", "fehlt.pdf"]

    first = extract_raw_missing(pdfs, raw, names)
    assert (first.extracted, first.current, first.failed, first.missing) == (4, 0, 1, 1)
    assert first.errors[0][0] == "kaputt.pdf" and "kaputt.pdf" not in RawTextStore(raw.path)
    stored = RawTextStore(raw.path)
    assert len(stored) == 4
    row = stored.rows[FILES[0]]
    assert row["extractor"] == raw_extractor_name(DEFAULT_PAGE_EXTRACTOR)
    assert row["pdf_sha256"] == pdfs.sha256(FILES[0])
    assert row["chars"] == len(str(row["text"]))
    assert row["pages"] == str(row["text"]).count(PAGE_BREAK) + 1

    second = extract_raw_missing(pdfs, RawTextStore(raw.path), names)
    assert (second.extracted, second.current) == (0, 4)

    (pdfs.directory / FILES[0]).write_bytes((pdf_fixtures / FILES[1]).read_bytes())  # PDF geändert
    third = extract_raw_missing(pdfs, RawTextStore(raw.path), FILES)
    assert (third.extracted, third.current) == (1, 3)


def test_the_four_fixture_pdfs_flatten_to_the_text_store(
    pdf_fixtures: Path, tmp_path: Path
) -> None:
    """Die Abnahme von F1 an echten PDFs: beide Schritte, ein Extraktor, dieselben Texte."""
    pdfs = _pdfs(tmp_path, pdf_fixtures, FILES)
    texts = TextStore(tmp_path / "text" / "texts.parquet")
    raw = RawTextStore(tmp_path / "text" / "rohtexte.parquet")
    extract_missing(pdfs, texts, FILES, "betrifft")
    extract_raw_missing(pdfs, raw, FILES)
    for name in FILES:
        stored = RawTextStore(raw.path)
        assert flatten(stored.get(name) or "", "betrifft", stored.form_feeds(name)) == TextStore(
            texts.path
        ).get(name)


def test_the_store_file_carries_its_schema(pdf_fixtures: Path, tmp_path: Path) -> None:
    raw = RawTextStore(tmp_path / "text" / "rohtexte.parquet")
    extract_raw_missing(_pdfs(tmp_path, pdf_fixtures, FILES[:1]), raw, FILES[:1])
    assert pl.read_parquet_schema(raw.path) == RAW_TEXT_SCHEMA
    stored = pl.read_parquet_metadata(raw.path)["georep.schema_version"]
    assert stored == str(RAW_TEXT_SCHEMA_VERSION)


def test_an_empty_store_saves_an_empty_file(tmp_path: Path) -> None:
    """Ohne PDFs (CI, Pages) schreibt der Schritt einen leeren Store, statt zu scheitern."""
    raw = RawTextStore(tmp_path / "text" / "rohtexte.parquet")
    report = extract_raw_missing(PdfStore(tmp_path / "pdf"), raw, ["a.pdf", "b.pdf"])
    assert (report.extracted, report.missing) == (0, 2) and not raw.path.exists()
    raw.save()
    assert pl.read_parquet(raw.path).height == 0 and len(RawTextStore(raw.path)) == 0


def test_a_form_feed_inside_a_page_is_a_space_with_its_offset() -> None:
    """Die defekte Schriftkodierung (``00532917.pdf`` und acht PDFs aus 2014 bis 2020) liefert
    ``\\f`` im Seitentext. Im Rohtext steht dort ein Leerzeichen, die Offsets stehen daneben, und
    ``flatten`` setzt sie zurück (Review F1, M3): geplättet ist es genau der Text des Textstores."""
    raw, feeds = raw_from_pages(["Kopf\x0cA", "Seite\f2 \f"])
    assert (raw, feeds) == ("Kopf A\fSeite 2  ", (4, 12, 15))
    assert restore_form_feeds(raw, feeds) == "Kopf\fA\fSeite\f2 \f"
    assert flatten(raw, "betrifft", feeds) == "kopf\faseite\f2 \f"
    assert raw_from_pages([]) == ("", ()) and raw_from_pages([""]) == ("", ())


def test_a_marker_made_by_the_standin_does_not_cut_the_text() -> None:
    """Gefunden vom Review F1: mit einem Leerzeichen statt des ``\\f`` entstand ein Marker „a b"."""
    pages = ["Kopf a\fb Rest"]
    old = after_marker(normalise_text("\n".join(pages)), "a b")
    raw, feeds = raw_from_pages(pages)
    assert old == "kopf a\fb rest" and flatten(raw, "a b", feeds) == old


def test_the_store_refuses_a_row_whose_page_count_lies(tmp_path: Path) -> None:
    """Der Vertrag an der Batch-Grenze: ``save`` prüft jede Zeile einmal, nicht ``put`` je Dokument."""
    raw = RawTextStore(tmp_path / "rohtexte.parquet")
    raw.put("a.pdf", "eins\fzwei", pages=3, extractor="x+roh", pdf_sha256="0" * 64)
    with pytest.raises(deal.PreContractError):
        raw.save()
    raw.put("a.pdf", "eins\fzwei", pages=2, extractor="x+roh", pdf_sha256="0" * 64, form_feeds=[3])
    with pytest.raises(deal.PreContractError):  # an Offset 3 steht kein Ersatzzeichen
        raw.save()
    raw.put("a.pdf", "ein \fzwei", pages=2, extractor="x+roh", pdf_sha256="0" * 64, form_feeds=[3])
    raw.save()
    assert RawTextStore(raw.path).form_feeds("a.pdf") == (3,)
    assert RawTextStore(raw.path).form_feeds("b.pdf") == ()
    assert RawTextStore(raw.path).is_current("a.pdf", pdf_sha256="0" * 64, extractor="x+roh")
    assert not RawTextStore(raw.path).is_current("a.pdf", pdf_sha256="1" * 64, extractor="x+roh")
    assert not RawTextStore(raw.path).is_current("a.pdf", pdf_sha256="0" * 64, extractor="y+roh")
    assert not RawTextStore(raw.path).is_current("b.pdf", pdf_sha256="0" * 64, extractor="x+roh")


def test_a_store_of_another_schema_version_reads_as_empty_and_is_rewritten(
    pdf_fixtures: Path, tmp_path: Path
) -> None:
    """Review F1, N3: eine Datei mit Version 1 hat keine Offsets; ihre Zeilen gelten nicht."""
    pdfs = _pdfs(tmp_path, pdf_fixtures, FILES[:1])
    path = tmp_path / "text" / "rohtexte.parquet"
    path.parent.mkdir()
    old = {k: v for k, v in RAW_TEXT_SCHEMA.items() if k != "form_feeds"}
    frame = pl.DataFrame(
        [
            {
                "name": FILES[0],
                "text": "alt",
                "pages": 1,
                "chars": 3,
                "extractor": raw_extractor_name(DEFAULT_PAGE_EXTRACTOR),
                "pdf_sha256": pdfs.sha256(FILES[0]),
            }
        ],
        schema=old,
    )
    write_parquet(frame, path, schema_version=1)
    stale = RawTextStore(path)
    assert len(stale) == 0 and "Schema-Version 1" in stale.stale
    report = extract_raw_missing(pdfs, stale, FILES[:1])
    assert (report.extracted, report.current) == (1, 0)
    assert pl.read_parquet_metadata(path)["georep.schema_version"] == str(RAW_TEXT_SCHEMA_VERSION)
    assert RawTextStore(path).stale == "" and RawTextStore(path).get(FILES[0]) != "alt"


def test_flatten_needs_a_marker() -> None:
    with pytest.raises(deal.PreContractError):
        flatten("Kopf\nBetrifft: Rest", "", ())
    assert flatten("Kopf\fBetrifft: Rest", "betrifft", ()) == ": rest"


def test_flatten_needs_the_offsets_of_the_form_feeds() -> None:
    """Review F1, dritte Runde: mit der Vorgabe ``form_feeds=()`` plättete ein Aufruf ohne Offsets
    still wie Schema-Version 1 -- an einem Dokument mit Formfeeds im Seitentext falsch. Wer keine
    Offsets hat, sagt es jetzt mit ``()``; wer aus dem Store liest, nimmt ``form_feeds(name)``."""
    with pytest.raises(TypeError):
        flatten("Kopf\fBetrifft: Rest", "betrifft")  # type: ignore[call-arg]
    assert flatten("Kopf A\fBetrifft: Rest", "betrifft", (4,)) == ": rest"
