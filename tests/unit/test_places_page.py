"""Vorhaben 16, kleine Stufe 3: der Satz in „Methode und Grenzen" und der Download.

Der Satz kommt aus beiden ``guete.json`` (Runde 1 und Bestätigung, ``validierung/16-ortsbezug-f4``
und ``16-ortsbezug-2-f4``): der hochgerechnete Anteil „handelt von", die Fehltreffer des
Wörterbuchs („kein Bezug"), α und der Satz über die Kodierer (Messdokument
``docs/plans/16-ortsbezug.md``, § 7 mit § 10, Punkte 6 und 8). Er steht nur, wo gemessen ist und
der Schritt ``places`` Stellen hat. Der Download ``dokumente_wahlbezirke_stelle`` steht nur als
Parquet (die CSV wäre rund 3 MB) und unter denselben Bedingungen wie die Downloads von 11 und 12:
gemessen und mit Rohtext. Spannen und Adressen werden nie veröffentlicht.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep.enrich.places import PAIR_SCHEMA, places_files
from georep.layout import Layout
from georep.report.places import CONFIRMATION, FIRST_ROUND, places_check_files, places_finding
from georep.report.tables import all_tables
from georep.settings import Settings, load_settings

NOWHERE = Path("/nonexistent")


def _layout(tmp_path: Path, settings: Settings) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference", settings.profile)


def _spans(layout: Layout, rows: int) -> None:
    path = places_files(layout).spans
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "id": ["d1"] * rows,
            "norm": ["kürtenstraße"] * rows,
            "stelle": ["betreff"] * rows,
            "im_titel": [False] * rows,
            "listenzeile": [False] * rows,
            "hausnummer": [False] * rows,
        },
        schema={
            "id": pl.String,
            "norm": pl.String,
            "stelle": pl.String,
            "im_titel": pl.Boolean,
            "listenzeile": pl.Boolean,
            "hausnummer": pl.Boolean,
        },
    ).write_parquet(path)


def test_the_finding_reads_both_rounds_from_their_guete(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path, default_settings)
    _spans(layout, 1)
    found = places_finding(layout, default_settings)
    assert found is not None
    confirmation, first = found.confirmation, found.first
    assert (
        (confirmation.units, first.units) == (CONFIRMATION.units, FIRST_ROUND.units) == (100, 200)
    )
    assert confirmation.share == pytest.approx(0.7831, abs=1e-4)
    assert first.share == pytest.approx(0.8210, abs=1e-4)
    assert (confirmation.no_reference, first.no_reference) == (10, 5)
    assert confirmation.alpha == pytest.approx(0.974, abs=1e-3)
    assert first.alpha == pytest.approx(0.917, abs=1e-3)
    assert found.sentence.startswith("geprüft von zwei KI-Kodierern desselben Modells")
    assert "nicht von Menschen" in found.sentence


def test_no_finding_without_positions(tmp_path: Path, default_settings: Settings) -> None:
    layout = _layout(tmp_path, default_settings)
    assert places_finding(layout, default_settings) is None  # keine Datei
    _spans(layout, 0)
    assert places_finding(layout, default_settings) is None  # kein Rohtext, keine Spanne


@pytest.mark.parametrize("profile", ["duesseldorf-2014", "moenchengladbach"])
def test_no_finding_where_nothing_is_measured(tmp_path: Path, profile: str) -> None:
    settings = load_settings(profile=profile, cwd=NOWHERE)
    layout = _layout(tmp_path, settings)
    _spans(layout, 1)
    assert places_finding(layout, settings) is None


def test_the_report_reads_the_checks_only_with_places(default_settings: Settings) -> None:
    files = places_check_files(default_settings)
    assert {p.parent.name for p in files} == {CONFIRMATION.project, FIRST_ROUND.project}
    assert {p.name for p in files} == {"guete.json", "stichprobe.json"}
    assert places_check_files(load_settings(profile="moenchengladbach", cwd=NOWHERE)) == ()


def _pairs(layout: Layout, extractor: str | None) -> Path:
    path = places_files(layout).pairs
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "id": "d1",
        "wahlkreis_id": 1,
        "stelle": None if extractor is None else "titel",
        "erwaehnungen": None if extractor is None else 1,
        "n_begleit": None if extractor is None else 0,
        "n_liste": None if extractor is None else 0,
        "handelt_von": None if extractor is None else True,
        "wahlkreis_adresse": None if extractor is None else False,
        "extractor": extractor,
    }
    pl.DataFrame([row], schema=PAIR_SCHEMA).write_parquet(path)
    return path


def test_the_download_is_parquet_only_where_measured_with_raw_text(
    tmp_path: Path, default_settings: Settings
) -> None:
    [table] = [t for t in all_tables() if t.name == "dokumente_wahlbezirke_stelle"]
    assert table.csv is None and table.shown is not None
    layout = _layout(tmp_path, default_settings)
    assert table.path(layout) == places_files(layout).pairs
    assert table.download_names(layout) == ("dokumente_wahlbezirke_stelle.parquet",)
    assert set(table.column_docs(default_settings)) == set(PAIR_SCHEMA)
    with_text = _pairs(layout, "ortsbezug-1/pypdf-7.1.0+roh")
    assert table.shown(with_text, default_settings)
    period = load_settings(profile="duesseldorf-2014", cwd=NOWHERE)
    assert not table.shown(with_text, period)
    without = _pairs(_layout(tmp_path / "leer", default_settings), None)
    assert not table.shown(without, default_settings)
    assert table.enabled is not None
    assert not table.enabled(load_settings(profile="moenchengladbach", cwd=NOWHERE))


def test_neither_spans_nor_addresses_are_published() -> None:
    names = {t.name for t in all_tables()}
    assert "treffer_stellen" not in names and "adressen_wahlbezirke" not in names
