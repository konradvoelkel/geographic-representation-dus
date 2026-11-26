"""Das Paket von Vorhaben 22: ``georep pack --need`` und ``bootstrap`` als Gegenrichtung.

Synergien 2026-11, Konflikt 11: abgeleitete Auszüge kommen nur über ``pack`` nach
``snapshots/<stadt>-bedarf/``, nicht nach ``context/``; ``bootstrap`` legt sie nach
``external/bedarf/``. Was die echten Pakete tragen, hält ``tests/unit/test_data_packages.py`` fest.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from georep.bootstrap import bootstrap, bootstrap_from_settings
from georep.io import write_json, write_parquet
from georep.layout import Layout
from georep.pack import PackError, pack_need
from georep.prep.context import (
    ACCIDENTS_FILE,
    ACCIDENTS_SCHEMA,
    GRID_FILE,
    GRID_SCHEMA,
    NEED_DIR,
    NEED_FILES,
    SCHOOLS_FILE,
    SCHOOLS_SCHEMA,
    SOURCES_FILE,
)
from georep.settings import Settings

NAMES = [f"external/{NEED_DIR}/{name}" for name in NEED_FILES]


def _switched(settings: Settings, on: bool = True) -> Settings:
    need = settings.context.need.model_copy(update={"enabled": on})
    return settings.model_copy(
        update={"context": settings.context.model_copy(update={"need": need})}
    )


def _run(tmp_path: Path, settings: Settings, *, rows: int = 2) -> Layout:
    """Eine Datenwurzel mit den vier Auszügen, wie ``need_data`` sie für ``settings`` schreibt."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    folder = layout.external / NEED_DIR
    accidents = pl.DataFrame(
        {
            "jahr": [2021] * rows,
            "monat": [5] * rows,
            "kategorie": [3] * rows,
            "rad": [0] * rows,
            "fuss": [1] * rows,
            "x": [1.0] * rows,
            "y": [2.0] * rows,
        },
        schema=ACCIDENTS_SCHEMA,
    )
    grid = pl.DataFrame(
        {"x": [1], "y": [2], "einwohner": [3], "miete": [9.5], "miete_zeichen": [None]},
        schema=GRID_SCHEMA,
    )
    schools = pl.DataFrame(
        {"schulnummer": ["1"], "schulform": ["02"], "x": [1.0], "y": [2.0], "sozialindex": [4]},
        schema=SCHOOLS_SCHEMA,
    )
    for frame, name in ((accidents, ACCIDENTS_FILE), (grid, GRID_FILE), (schools, SCHOOLS_FILE)):
        write_parquet(frame, folder / name, schema_version=1)
    archive = [
        {"url": url, "datei": "x", "bytes": 1, "sha256": "0" * 64, "abgerufen": "2026-11-24"}
        for url in settings.context.need.archive_urls()
    ]
    write_json(folder / SOURCES_FILE, {"ags": settings.city.ags, "archive": archive})
    return layout


def test_pack_need_writes_the_four_extracts_and_bootstrap_brings_them_back(
    tmp_path: Path, default_settings: Settings, mini_root: Path
) -> None:
    settings = _switched(default_settings)
    layout = _run(tmp_path / "lauf", settings)
    target = tmp_path / "paket"
    report = pack_need(layout, settings, target)
    assert [entry.name for entry in report.files] == NAMES
    assert dict(report.figures) == {"Archive": 10, "Unfälle": 2, "Gitterzellen": 1, "Schulen": 1}
    assert (target / "README.md").is_file() and "pack --need" in (target / "README.md").read_text(
        encoding="utf-8"
    )
    fresh = Layout(tmp_path / "neu", tmp_path / "neu-cache", tmp_path / "ohne-eigene-auszuege")
    copied = bootstrap(fresh, need=target)
    assert {f"external/{NEED_DIR}/{n}" for n in copied.copied} >= set(NAMES)
    for name in NAMES:
        assert (fresh.root / name).read_bytes() == (target / name).read_bytes()


def test_pack_need_keeps_what_is_there_without_force(
    tmp_path: Path, default_settings: Settings
) -> None:
    settings = _switched(default_settings)
    layout = _run(tmp_path / "lauf", settings)
    target = tmp_path / "paket"
    pack_need(layout, settings, target)
    assert set(pack_need(layout, settings, target).skipped) == set(NAMES)
    assert pack_need(layout, settings, target, force=True).skipped == ()


def test_pack_need_refuses_without_the_switch_and_with_missing_or_foreign_extracts(
    tmp_path: Path, default_settings: Settings
) -> None:
    settings = _switched(default_settings)
    layout = _run(tmp_path / "lauf", settings)
    with pytest.raises(PackError, match="enabled"):
        pack_need(layout, _switched(default_settings, on=False), tmp_path / "a")
    described = json.loads((layout.external / NEED_DIR / SOURCES_FILE).read_text(encoding="utf-8"))
    write_json(layout.external / NEED_DIR / SOURCES_FILE, {**described, "ags": "05116000"})
    with pytest.raises(PackError, match="anderen"):
        pack_need(layout, settings, tmp_path / "b")
    (layout.external / NEED_DIR / GRID_FILE).unlink()
    with pytest.raises(PackError, match=GRID_FILE):
        pack_need(layout, settings, tmp_path / "c")


def test_pack_need_refuses_an_empty_extract(tmp_path: Path, default_settings: Settings) -> None:
    settings = _switched(default_settings)
    layout = _run(tmp_path / "lauf", settings, rows=0)
    with pytest.raises(PackError, match=ACCIDENTS_FILE):
        pack_need(layout, settings, tmp_path / "paket")


def test_the_reference_brings_its_own_extracts_before_the_package(
    tmp_path: Path, default_settings: Settings, mini_root: Path
) -> None:
    """Wie die Beratungsfolge (Punkt 58): bringt der Datensatz eigene Auszüge mit, gelten seine."""
    settings = _switched(default_settings)
    package = tmp_path / "paket"
    pack_need(_run(tmp_path / "lauf", settings), settings, package)
    layout = Layout(tmp_path / "data", tmp_path / "cache", mini_root)
    report = bootstrap(layout, need=package)
    own = mini_root / "external" / NEED_DIR / ACCIDENTS_FILE
    assert (layout.external / NEED_DIR / ACCIDENTS_FILE).read_bytes() == own.read_bytes()
    assert report.missing == []


def test_without_the_switch_bootstrap_copies_nothing_and_a_missing_package_is_named(
    tmp_path: Path, default_settings: Settings, mini_root: Path
) -> None:
    off = Layout(tmp_path / "aus", tmp_path / "aus-cache", mini_root)
    bootstrap_from_settings(off, _switched(default_settings, on=False))
    assert not (off.external / NEED_DIR).exists()
    nowhere = Layout(tmp_path / "leer", tmp_path / "leer-cache", tmp_path / "keine-referenz")
    report = bootstrap(nowhere, need=tmp_path / "gibt-es-nicht")
    assert set(NEED_FILES) <= set(report.missing)
