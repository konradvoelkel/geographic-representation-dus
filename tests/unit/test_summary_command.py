"""``georep summary`` (Vorhaben 20): Kurzfassungen lokal lesen, nie unter ``site/``.

Die Ausgaben des Schritts und der Korpus sind kleine erfundene Tabellen in ``tmp_path``; kein
Modell, kein Ratstext.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from georep.cli import main
from georep.enrich.fidelity import FIDELITY_COLUMNS
from georep.enrich.summaries import SUMMARY_SCHEMA, summaries_dir, summaries_files
from georep.layout import Layout
from georep.settings import load_settings

ORG = "https://example.org/oparl/bodies/1/organizations/"


@pytest.fixture
def layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Layout:
    (tmp_path / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\ncache_root = "{tmp_path / "cache"}"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    found = Layout.from_settings(load_settings(cwd=tmp_path))
    found.processed.mkdir(parents=True)
    found.interim.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["a", "b", "c"],
            "reference": ["BV2/1/2025", "RAT/9/2024", "OVA/7/2025"],
            "date": [date(2025, 2, 1), date(2024, 12, 1), date(2025, 3, 4)],
            "name": ["Bänke am Kanal", "Haushalt", "Ampel an der Schule"],
            "paper_type": ["Bezirksvertretung Beschlussvorlage", "Beschlussvorlage", "Antrag"],
            "consultation_organizations": [[f"{ORG}gr/33"], [f"{ORG}gr/6"], [f"{ORG}gr/33"]],
            "file_name": [None, None, None],
        },
        schema_overrides={"consultation_organizations": pl.List(pl.String), "file_name": pl.String},
    ).write_parquet(found.corpus)
    pl.DataFrame({"id": ["a", "b", "c"], "gremium": ["BV2", "RAT", "OVA"]}).write_parquet(
        found.papers_bodies
    )
    return found


def write_outputs(layout: Layout) -> None:
    files = summaries_files(layout)
    files.summaries.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "id": ["a", "b", "c"],
            "text": [
                "Die Verwaltung schlägt neue Bänke vor.",
                None,
                "Eine Fraktion will eine Ampel.",
            ],
            "grund": [None, "offen", None],
            "modell": ["fake-chat:latest"] * 3,
            "digest": ["c" * 64] * 3,
            "prompt": ["20-kurzfassung-2"] * 3,
            "abgeschnitten": [False, False, True],
            "eingabe_quelle": ["abschnitte", "abschnitte", "rohtext"],
            "eingabe_gekuerzt": [False, False, False],
        },
        schema=SUMMARY_SCHEMA,
    ).write_parquet(files.summaries)
    pl.DataFrame(
        {
            "id": ["a", "c"],
            "angaben": [3, 2],
            "unbelegt_zahl": [0, 1],
            "unbelegt_datum": [0, 0],
            "unbelegt_drucksache": [0, 0],
            "unbelegt_name": [0, 0],
            "personennamen": [1, 0],
            "ok": [True, False],
        },
        schema={"id": pl.String, **FIDELITY_COLUMNS},
    ).write_parquet(files.fidelity)


def test_one_document_by_reference(layout: Layout, capsys: pytest.CaptureFixture[str]) -> None:
    write_outputs(layout)
    assert main(["summary", "bv2/1/2025"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "BV2/1/2025 vom 01.02.2025: Bänke am Kanal"
    assert out[1].startswith(
        "Modell fake-chat:latest, Digest cccccccccccc, Prompt 20-kurzfassung-2"
    )
    assert out[2] == "Die Verwaltung schlägt neue Bänke vor."
    assert out[3] == "Treue: 3 Angaben, ohne unbelegte Angabe; Personennamen 1 (Regel 5)"
    assert out[4].startswith("  Angaben nicht nachrechenbar: ")  # ohne Abschnitte von 11


def test_one_document_by_id_with_flags(layout: Layout, capsys: pytest.CaptureFixture[str]) -> None:
    write_outputs(layout)
    assert main(["summary", "c"]) == 0
    out = capsys.readouterr().out
    assert "[abgeschnitten]" in out
    assert "Treue: 2 Angaben, unbelegt: zahl 1" in out
    assert main(["summary", "b"]) == 0
    assert "(keine Kurzfassung: offen)" in capsys.readouterr().out


def test_a_list_per_body_since_a_date(layout: Layout, capsys: pytest.CaptureFixture[str]) -> None:
    """BV 2: a nach der Nummer, c nach der Beratungsfolge (gr/33); b ist ein anderes Gremium."""
    write_outputs(layout)
    assert main(["summary", "--body", "bv2", "--since", "2025-01-01"]) == 0
    out = capsys.readouterr().out
    assert out.index("BV2/1/2025") < out.index("OVA/7/2025")
    assert "RAT/9/2024" not in out


def test_the_html_list_stays_in_the_cache(
    layout: Layout, capsys: pytest.CaptureFixture[str]
) -> None:
    write_outputs(layout)
    assert main(["summary", "--body", "RAT", "--html"]) == 0
    written = summaries_dir(layout) / "vorlagenspiegel-RAT-alle.html"
    assert written.is_file()
    assert not written.is_relative_to(layout.data_root)
    page = written.read_text(encoding="utf-8")
    assert "Haushalt" in page and "nicht zur Veröffentlichung" in page
    assert "<script" not in page and "http" not in page  # keine Fremdressource


def test_missing_outputs_and_bad_usage(layout: Layout, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["summary", "a"]) == 1
    assert "georep run summaries --models" in capsys.readouterr().err
    write_outputs(layout)
    assert main(["summary"]) == 2
    assert main(["summary", "a", "--body", "RAT"]) == 2
    assert main(["summary", "XYZ/1/2000"]) == 1
    with pytest.raises(SystemExit):
        main(["summary", "--body", "RAT", "--since", "gestern"])
