"""Der Beitrag von Vorhaben 22 im Register: ``need_data`` mit Fake-Session, ``need`` auf der Mini-Kette.

Kein Netz (CLAUDE.md, „Nie"): die Archive baut ``tests/need_archives.py`` in der Form der Quellen,
und die Fake-Session liefert sie aus. Die Koordinaten liegen in Stimmbezirken der Mini-Fixture.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import polars as pl
import pytest
import requests

from georep.analysis.need import HYPOTHESES_SCHEMA
from georep.crosswalk import DISTRICT
from georep.enrich.need import need_files, need_steps
from georep.errors import FetchError
from georep.geo import read_canonical_precincts, transformer
from georep.io import digest
from georep.layout import Layout
from georep.pipeline import Step, build_steps, run_step
from georep.prep.context import (
    ACCIDENTS_SCHEMA,
    GRID_SCHEMA,
    NEED_TABLE_SCHEMA,
    SCHOOLS_SCHEMA,
)
from georep.settings import NeedHypothesis, Settings
from tests.fakes import FakeSession, response
from tests.need_archives import write_accident_archive, write_grid_archives, write_school_files

SITE = "https://quelle.example.org/"
Routes = dict[str, requests.Response | Exception]
ARCHIVES = [f"{SITE}u/Unfallorte{year}_EPSG25832_CSV.zip" for year in (2020, 2021, 2025)]


def _enabled(settings: Settings, **update: object) -> Settings:
    need = settings.context.need
    grid = need.grid.model_copy(
        update={
            "population_url": f"{SITE}z/Zensus2022_Bevoelkerungszahl.zip",
            "rent_url": f"{SITE}z/Zensus2022_Durchschn_Nettokaltmiete.zip",
        }
    )
    schools = need.schools.model_copy(
        update={
            "schools_url": f"{SITE}s/schuldaten.csv",
            "index_url": f"{SITE}s/schulliste_sj_25_26_open_data.csv",
        }
    )
    accidents = need.accidents.model_copy(update={"archives": ARCHIVES})
    changed = need.model_copy(
        update={
            "enabled": True,
            "accidents": accidents,
            "grid": grid,
            "schools": schools,
            "delay_s": 0.0,
            **update,
        }
    )
    return settings.model_copy(
        update={"context": settings.context.model_copy(update={"need": changed})}
    )


def _step(steps: list[Step], name: str) -> Step:
    return next(step for step in steps if step.name == name)


@pytest.fixture
def world(
    tmp_path: Path, mini_precincts: Path, default_settings: Settings
) -> tuple[Layout, Routes, dict[str, int]]:
    """Eine Datenwurzel mit den Stimmbezirken der Mini-Fixture und die Archive auf einer Fake-Session."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference", "stadt")
    layout.ensure_dirs()
    shutil.copyfile(mini_precincts, layout.precincts_geojson)
    working = default_settings.geo.working_crs
    precincts = read_canonical_precincts(layout.precincts_geojson, working)
    inside = [p.geometry.representative_point() for p in precincts[:6]]
    ags = default_settings.city.ags
    folder = tmp_path / "archive"
    folder.mkdir()
    rows = [
        {"ags": ags, "month": 10, "category": 2, "bike": 1, "foot": 0, "x": point.x, "y": point.y}
        for point in inside[:3]
    ]
    paths = [
        write_accident_archive(folder / url.rsplit("/", 1)[1], form, rows)
        for form, url in enumerate(ARCHIVES)
    ]
    to_grid = transformer(working, "EPSG:3035")
    cells = []
    for point, people in zip(inside, (10, 20, 30, 40, 50, 60), strict=True):
        x, y = to_grid.transform(point.x, point.y)
        cells.append((round(x), round(y), str(people), "9,00", ""))
    corner = precincts[0].geometry.bounds
    x, y = to_grid.transform(corner[0] - 150.0, corner[1] - 150.0)
    cells.append((round(x), round(y), "999", "", ""))  # im Rechteck, in keinem Stimmbezirk
    population, rent = write_grid_archives(folder, cells)
    schools_csv, index_csv = write_school_files(
        folder,
        [
            ("100020", "02", ags, round(inside[0].x), round(inside[0].y), "5"),
            ("100010", "02", ags, round(inside[1].x), round(inside[1].y), "ohne"),
            ("100030", "02", "05911000", 1, 2, "9"),
        ],
    )
    settings = _enabled(default_settings)
    urls = settings.context.need.archive_urls()
    files = [*paths, population, rent, schools_csv, index_csv]
    routes: Routes = {
        url: response(url, content=path.read_bytes()) for url, path in zip(urls, files, strict=True)
    }
    sizes = {url: path.stat().st_size for url, path in zip(urls, files, strict=True)}
    return layout, routes, sizes


def test_without_the_switch_there_is_no_step(tmp_path: Path, default_settings: Settings) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    off = default_settings.context.need.model_copy(update={"enabled": False})
    settings = default_settings.model_copy(
        update={"context": default_settings.context.model_copy(update={"need": off})}
    )
    assert need_steps(settings, layout, FakeSession({})) == []


def test_the_two_steps_stand_before_report_and_only_need_data_uses_the_network(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    steps = build_steps(
        _enabled(default_settings, hypotheses=[], explore=[]), layout, FakeSession({})
    )
    names = [s.name for s in steps]
    assert names.index("need") == names.index("need_data") + 1
    assert names.index("report") > names.index("need") > names.index("results")
    assert _step(steps, "need_data").network and not _step(steps, "need").network
    files = need_files(layout)
    assert files.archives == layout.cache_root / "bedarf"
    assert files.accidents == layout.external / "bedarf" / "unfaelle.parquet"
    assert files.table == layout.processed / "wahlbezirke_bedarf.parquet"
    assert _step(steps, "need").outputs == (files.table,)  # ohne Hypothesen keine zweite Datei


def test_need_data_fetches_cuts_out_the_municipality_and_describes_the_archives(
    world: tuple[Layout, Routes, dict[str, int]], default_settings: Settings
) -> None:
    layout, routes, sizes = world
    settings = _enabled(default_settings)
    http = FakeSession(routes)
    step = _step(need_steps(settings, layout, http), "need_data")
    outcome = run_step(step, settings, online=True)
    assert outcome.status == "ausgeführt", outcome.reason
    files = need_files(layout)
    accidents = pl.read_parquet(files.accidents)
    grid = pl.read_parquet(files.grid)
    schools = pl.read_parquet(files.schools)
    assert accidents.schema == pl.Schema(ACCIDENTS_SCHEMA) and accidents.height == 9
    assert sorted(set(accidents.get_column("jahr"))) == [2020, 2021, 2025]
    assert grid.schema == pl.Schema(GRID_SCHEMA)
    assert sorted(grid.get_column("einwohner").to_list()) == [10, 20, 30, 40, 50, 60]
    assert schools.schema == pl.Schema(SCHOOLS_SCHEMA)
    assert schools.select("schulnummer", "sozialindex").rows() == [("100010", None), ("100020", 5)]
    described = json.loads(files.sources.read_text(encoding="utf-8"))
    assert described["ags"] == settings.city.ags
    assert [a["url"] for a in described["archive"]] == list(settings.context.need.archive_urls())
    for entry in described["archive"]:
        archive = files.archives / entry["datei"]
        assert entry["bytes"] == sizes[entry["url"]] == archive.stat().st_size
        assert entry["sha256"] == digest(archive)
    assert sorted(http.urls) == sorted(routes)
    assert "7 Archive, 7 davon geladen" in outcome.reason


def test_a_fresh_archive_is_not_fetched_twice_and_an_old_one_is(
    world: tuple[Layout, Routes, dict[str, int]], default_settings: Settings
) -> None:
    layout, routes, _ = world
    settings = _enabled(default_settings)
    first = FakeSession(routes)
    run_step(_step(need_steps(settings, layout, first), "need_data"), settings, online=True)
    again = FakeSession(routes)
    outcome = run_step(
        _step(need_steps(settings, layout, again), "need_data"), settings, online=True, force=True
    )
    assert again.urls == [] and "0 davon geladen" in outcome.reason
    old = need_files(layout).archives / "schuldaten.csv"
    week = settings.cache.opendata_s + 3600
    os.utime(old, (old.stat().st_atime - week, old.stat().st_mtime - week))
    late = FakeSession(routes)
    run_step(
        _step(need_steps(settings, layout, late), "need_data"), settings, online=True, force=True
    )
    assert late.urls == [settings.context.need.schools.schools_url]


def test_an_answer_that_is_no_zip_stops_the_step_before_anything_is_written(
    world: tuple[Layout, Routes, dict[str, int]], default_settings: Settings
) -> None:
    layout, routes, _ = world
    settings = _enabled(default_settings)
    broken = dict(routes)
    broken[ARCHIVES[1]] = response(ARCHIVES[1], content=b"<html>Wartung</html>")
    with pytest.raises(FetchError, match="kein Zip"):
        run_step(
            _step(need_steps(settings, layout, FakeSession(broken)), "need_data"),
            settings,
            online=True,
        )
    assert not need_files(layout).accidents.exists()
    assert not (need_files(layout).archives / ARCHIVES[1].rsplit("/", 1)[1]).exists()


H = NeedHypothesis(
    name="H1",
    need="unfaelle_je_1000",
    attention="dok_je_1000_ew",
    alternative="greater",
    fixed="abc1234",
    robust_need=["unfaelle"],
)


def test_need_on_the_mini_chain_writes_a_row_per_district_and_the_tests(
    world: tuple[Layout, Routes, dict[str, int]],
    mini_run: Layout,
    default_settings: Settings,
    tmp_path: Path,
) -> None:
    """Die Mini-Kette, kopiert, mit den Auszügen aus der Fake-Session; der Lauf selbst bleibt unberührt."""
    layout, routes, _ = world
    copy = Layout(
        tmp_path / "kette",
        layout.cache_root,
        mini_run.reference_root,
        mini_run.profile,
        context_root=mini_run.context_root,
    )
    shutil.copytree(mini_run.root, copy.root)
    settings = _enabled(
        default_settings,
        hypotheses=[H],
        explore=[("einwohner_zensus", "dok")],
        permutations=99,
        explore_permutations=99,
        bootstrap=99,
    )
    steps = need_steps(settings, copy, FakeSession(routes))
    assert run_step(steps[0], settings, online=True).status == "ausgeführt"
    outcome = run_step(steps[1], settings)
    assert outcome.status == "ausgeführt", outcome.reason
    files = need_files(copy)
    table = pl.read_parquet(files.table)
    assert table.schema == pl.Schema(NEED_TABLE_SCHEMA)
    districts = pl.read_parquet(mini_run.results, columns=[DISTRICT]).get_column(DISTRICT).to_list()
    assert table.get_column(DISTRICT).to_list() == sorted(districts)
    assert float(table.get_column("einwohner_zensus").sum()) == pytest.approx(210.0)
    # neun Unfälle im Oktober 2020, 2021 und 2025; die Periode endet im September 2025
    assert float(table.get_column("unfaelle").sum()) == pytest.approx(6.0)
    assert float(table.get_column("schulen").sum()) == pytest.approx(2.0)
    assert (
        table.get_column("dok").to_list()
        == pl.read_parquet(mini_run.results).sort(DISTRICT).get_column("anzahl_treffer").to_list()
    )
    tests = pl.read_parquet(files.tests)
    assert tests.schema == pl.Schema(HYPOTHESES_SCHEMA)
    assert tests.get_column("rechnung").to_list()[:2] == ["haupttest", "robustheit"]
    assert tests.filter(pl.col("rechnung") == "haupttest").get_column("festgelegt").to_list() == [
        "abc1234"
    ]
    assert "H1" in outcome.reason
    # ein zweiter Lauf auf denselben Eingaben schreibt dieselben Dateien
    before = {path: digest(path) for path in (files.table, files.tests)}
    run_step(steps[1], settings, force=True)
    assert {path: digest(path) for path in (files.table, files.tests)} == before


def test_need_data_pauses_between_two_archives_it_fetches(
    world: tuple[Layout, Routes, dict[str, int]],
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Anfrage nach der anderen, mit Pause dazwischen (wie die Fremddaten geladen wurden)."""
    layout, routes, _ = world
    pauses: list[float] = []
    monkeypatch.setattr("georep.enrich.need.time.sleep", pauses.append)
    settings = _enabled(default_settings, delay_s=0.5)
    run_step(
        _step(need_steps(settings, layout, FakeSession(routes)), "need_data"), settings, online=True
    )
    assert pauses == [0.5] * (len(routes) - 1)
    pauses.clear()
    run_step(
        _step(need_steps(settings, layout, FakeSession(routes)), "need_data"),
        settings,
        online=True,
        force=True,
    )
    assert pauses == []  # nichts geladen, nichts abzuwarten


def test_without_context_data_the_hypotheses_on_its_variables_are_left_out(
    world: tuple[Layout, Routes, dict[str, int]],
    mini_run: Layout,
    default_settings: Settings,
    tmp_path: Path,
) -> None:
    """Das Stadtprofil nennt H2 und H3 über Variablen des Quartiersatlas; ohne ``context.root`` fehlen sie.

    Statt eines ``SchemaError`` rechnet der Schritt, was ohne Fremddaten geht (H1), und sagt in seiner
    Zeile, was wegfiel; die Kontexttabelle ist dann keine Eingabe.
    """
    layout, routes, _ = world
    copy = Layout(tmp_path / "kette", layout.cache_root, mini_run.reference_root, mini_run.profile)
    shutil.copytree(mini_run.root, copy.root)
    settings = _enabled(default_settings, permutations=99, explore_permutations=99, bootstrap=99)
    assert [h.name for h in settings.context.need.hypotheses] == ["H1", "H2", "H3"]
    steps = need_steps(settings, copy, FakeSession(routes))
    assert copy.context_table not in steps[1].inputs
    assert run_step(steps[0], settings, online=True).status == "ausgeführt"
    outcome = run_step(steps[1], settings)
    assert "ohne Fremddaten oder Klassen nicht gerechnet: H2, H3" in outcome.reason
    tests = pl.read_parquet(need_files(copy).tests)
    assert set(tests.drop_nulls("hypothese").get_column("hypothese")) == {"H1"}


def test_without_classes_the_hypotheses_on_the_shares_are_left_out(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Ohne Klassifikator trügen ``anteil_verkehr`` und ``anteil_jugend`` keinen Wert: H1 und H3 fallen weg."""
    layout = Layout(
        tmp_path / "data", tmp_path / "cache", tmp_path / "reference", context_root=tmp_path
    )
    off = default_settings.classify.model_copy(update={"enabled": False})
    settings = _enabled(default_settings).model_copy(update={"classify": off})
    need = _step(need_steps(settings, layout, FakeSession({})), "need")
    assert layout.papers_committee not in need.inputs
    assert need_files(layout).tests in need.outputs  # H2 und Paare ohne Klassen bleiben
