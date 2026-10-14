from __future__ import annotations

import datetime as dt
import io
import pstats
from pathlib import Path

import pytest

from georep.bootstrap import bootstrap_from_settings
from georep.layout import Layout
from georep.pipeline import Step, build_steps
from georep.profiling import profile_step
from georep.settings import Settings, load_settings


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def _steps(tmp_path: Path, mini_root: Path, settings: Settings) -> dict[str, Step]:
    layout = Layout(tmp_path / "data", tmp_path / "cache", mini_root)
    bootstrap_from_settings(layout, settings)
    return {s.name: s for s in build_steps(settings, layout)}


def test_profile_runs_the_real_step_and_writes_a_dated_file(
    tmp_path: Path, mini_root: Path, settings: Settings
) -> None:
    steps = _steps(tmp_path, mini_root, settings)
    out = tmp_path / "prof"
    result = profile_step(steps["voters"], settings, out, top=5, today=dt.date(2026, 10, 11))
    assert result.outcome.status == "ausgeführt" and result.outcome.reason.startswith("erzwungen")
    assert result.path == out / "2026-10-11-voters.prof" and result.path.is_file()
    # run_step ist der äußerste profilierte Frame und steht nach kumulierter Zeit immer oben.
    assert "function calls" in result.table and "run_step" in result.table
    assert "Ordered by: cumulative time" in result.table
    by_own_time = profile_step(steps["voters"], settings, out, top=5, sort="tottime")
    assert "Ordered by: internal time" in by_own_time.table
    reloaded = io.StringIO()
    pstats.Stats(str(result.path), stream=reloaded).print_stats(5)
    assert "function calls" in reloaded.getvalue()
    assert steps["voters"].outputs[0].exists() and steps["voters"].stamp_path.exists()


def test_network_step_without_online_leaves_no_file(
    tmp_path: Path, mini_root: Path, settings: Settings
) -> None:
    steps = _steps(tmp_path, mini_root, settings)
    result = profile_step(steps["opendata"], settings, tmp_path / "prof")
    assert result.outcome.status == "übersprungen" and "Netz aus" in result.outcome.reason
    assert result.path is None and result.table == ""
    assert not (tmp_path / "prof").exists()
