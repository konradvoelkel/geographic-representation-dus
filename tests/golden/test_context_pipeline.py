"""Die Kette mit Fremddaten: die drei Schritte, ihre Stamps und ihre Wiederholbarkeit."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.pipeline import build_steps, freshness, run_pipeline
from georep.settings import Settings, load_settings

OFFLINE = {"context", "controls"}


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def _layout(root: Path, mini_root: Path) -> Layout:
    return Layout(root / "data", root / "cache", mini_root, context_root=mini_root / "context")


def _run(root: Path, mini_root: Path, settings: Settings) -> Layout:
    layout = _layout(root, mini_root)
    bootstrap(layout, context_files=settings.context.files.names())
    outcomes = run_pipeline(build_steps(settings, layout), settings)
    assert {o.step for o in outcomes} >= OFFLINE
    assert all(o.status == "ausgeführt" for o in outcomes if o.step in OFFLINE)
    return layout


def test_context_and_controls_run_then_skip(
    tmp_path: Path, mini_root: Path, settings: Settings
) -> None:
    layout = _run(tmp_path, mini_root, settings)
    assert layout.context_table.exists() and layout.crosswalk.exists()
    assert layout.controls.exists()
    steps = {s.name: s for s in build_steps(settings, layout)}
    for name in OFFLINE:
        fresh, reason = freshness(steps[name], settings)
        assert fresh and reason == "aktuell", name

    context = pl.read_parquet(layout.context_table)
    assert context.height == 3 and context.columns[0] == "wahlkreis_id"
    names = [v.name for v in settings.context.variables]
    assert all(n in context.columns for n in names)
    assert all(
        f"{v.name}_fehlgewicht" in context.columns for v in settings.context.unit_variables()
    )
    crosswalk = pl.read_parquet(layout.crosswalk)
    assert crosswalk.columns == ["wahlkreis_id", "einheit", "einheit_name", "gewicht"]
    assert crosswalk.get_column("einheit_name").null_count() == 0
    sums = crosswalk.group_by("wahlkreis_id").agg(pl.col("gewicht").sum())
    assert sums.get_column("gewicht").to_list() == pytest.approx([1.0] * 3)


def test_a_changed_context_table_pulls_controls_and_report_along(
    tmp_path: Path, mini_root: Path, settings: Settings
) -> None:
    layout = _run(tmp_path, mini_root, settings)
    steps = build_steps(settings, layout)
    # Eine geaenderte Eingabe der Fremddaten: context, controls und report laufen neu, der Rest nicht
    table = layout.external / settings.context.files.table.file
    table.write_bytes(table.read_bytes().replace(b"mittel", b"hoch", 1))
    again = {o.step: o.status for o in run_pipeline(steps, settings)}
    assert again["context"] == "ausgeführt" and again["controls"] == "ausgeführt"
    assert again["voters"] == again["results"] == "übersprungen"


def test_two_runs_write_identical_parquet(
    tmp_path: Path, mini_root: Path, settings: Settings
) -> None:
    a = _run(tmp_path / "a", mini_root, settings)
    b = _run(tmp_path / "b", mini_root, settings)
    for name in ("context_table", "crosswalk", "controls"):
        assert getattr(a, name).read_bytes() == getattr(b, name).read_bytes(), name


def test_without_context_data_the_chain_is_the_old_one(
    tmp_path: Path, mini_root: Path, settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", mini_root)
    bootstrap(layout)
    names = [s.name for s in build_steps(settings, layout)]
    assert not OFFLINE & set(names) and "context_data" not in names
    outcomes = run_pipeline(build_steps(settings, layout), settings)
    assert all(o.status in ("ausgeführt", "übersprungen") for o in outcomes)
    assert not layout.context_table.exists() and not layout.controls.exists()
    assert layout.site_index.exists()
