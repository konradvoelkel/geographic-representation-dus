from __future__ import annotations

from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from georep.cli import main
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.report.tables import csv_plan
from georep.settings import load_settings


@pytest.fixture
def project(tmp_path: Path, mini_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\nreference_root = "{mini_root}"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_steps_lists_the_chain(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["steps"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("opendata") and "[Netz]" in out
    assert "results" in out and "inverted_index.parquet" in out


def _step_counts(project: Path) -> tuple[int, int]:
    """(Offline-Schritte, Netzschritte) aus dem Register, damit neue Schritte keine Literale brechen."""
    settings = load_settings(cwd=project)
    steps = build_steps(settings, Layout.from_settings(settings))
    network = sum(1 for s in steps if s.network)
    return len(steps) - network, network


def test_bootstrap_run_status_export_regress(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["bootstrap"]) == 0
    assert "200 Paper und 200 Texte" in capsys.readouterr().out
    offline, network = _step_counts(project)
    assert main(["run", "--dry-run"]) == 0
    assert f"{network} übersprungen, {offline} geplant" in capsys.readouterr().out
    assert main(["run"]) == 0
    out = capsys.readouterr().out
    assert f"{offline} ausgeführt, {network} übersprungen" in out
    assert "report       ausgeführt" in out
    assert (project / "data" / "site" / "index.html").exists()
    assert main(["status"]) == 0
    status = capsys.readouterr().out
    assert status.count("aktuell") >= 7 and "200 Dokumente" in status and "[Netz]" in status
    assert main(["export"]) == 0
    # Zahl aus dem Register, damit eine neue Tabelle keine Literale bricht (F6-Konvention)
    written = len(csv_plan(Layout.from_settings(load_settings(cwd=project))))
    assert f"{written} CSV-Dateien" in capsys.readouterr().out
    assert (project / "data" / "processed" / "wahlbezirke_auswertung.csv").exists()
    assert main(["regress"]) == 0
    assert capsys.readouterr().out.startswith("alle: n=3")
    assert main(["regress", "--exclude", "1"]) == 1  # zwei Bezirke reichen nicht
    assert "mindestens 3" in capsys.readouterr().err


def test_domain_errors_exit_with_one(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "index"]) == 1
    assert "bootstrap" in capsys.readouterr().err


def test_unknown_step_is_a_domain_error(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "gibtsnicht"]) == 1
    assert "Unbekannte Schritte" in capsys.readouterr().err


def test_missing_settings_file_exits_with_one(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--settings", "fehlt.toml", "steps"]) == 1
    assert "fehlt.toml" in capsys.readouterr().err


def test_usage_errors_exit_with_two(project: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--nope"])
    assert exit_info.value.code == 2


def test_fetch_plans_network_steps_and_texts(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["bootstrap"])
    capsys.readouterr()
    assert main(["run", "--dry-run", "--online", "opendata", "papers"]) == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith("2 geplant") and "Netz aus" not in out


def test_steps_output_is_stable(
    project: Path, capsys: pytest.CaptureFixture[str], snapshot: SnapshotAssertion
) -> None:
    assert main(["steps"]) == 0
    assert capsys.readouterr().out == snapshot


def test_fetch_with_limit_runs_only_the_named_step(
    project: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import requests

    from georep.settings import Settings, load_settings
    from tests.fakes import FakeSession, response

    src = load_settings(cwd=project).sources
    routes: dict[str, requests.Response | Exception] = {
        src.opendata.results_url: response(src.opendata.results_url, content=b"a;b\n1;2\n"),
        src.opendata.districts_url: response(
            src.opendata.districts_url, payload={"type": "FeatureCollection", "features": [{}]}
        ),
    }
    seen: list[int] = []

    def fake_session(settings: Settings, path: Path) -> FakeSession:
        seen.append(settings.sources.oparl.pdf_limit)
        return FakeSession(routes)

    monkeypatch.setattr("georep.pipeline.cached_session", fake_session)
    assert main(["fetch", "opendata", "--limit", "7"]) == 0
    out = capsys.readouterr().out
    assert "opendata     ausgeführt" in out and "1 ausgeführt" in out
    assert seen == [7]


def test_regress_without_results_is_a_domain_error(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["regress"]) == 1
    assert "wahlbezirke_auswertung.parquet" in capsys.readouterr().err


def test_profile_writes_one_file_per_offline_step(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["bootstrap"])
    capsys.readouterr()
    assert main(["profile", "--out", "prof", "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "voters       ausgeführt    erzwungen; 3 Wahlbezirke, 3 Paare mit Stadtbezirk" in out
    offline, _ = _step_counts(project)
    assert out.count("function calls") == offline
    assert out.count("Anzeige: uv run snakeviz") == offline
    assert len(list((project / "prof").glob("*.prof"))) == offline
    assert main(["profile", "opendata", "--out", "prof"]) == 0
    assert "Netz aus" in capsys.readouterr().out
    assert len(list((project / "prof").glob("*.prof"))) == offline


def test_contracts_setting_reaches_deal(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import deal

    @deal.pre(lambda x: x > 0)
    def positive(x: int) -> int:
        return x

    settings = project / "settings.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + 'contracts = "off"\n', encoding="utf-8"
    )
    assert main(["status"]) == 0
    assert "Verträge off" in capsys.readouterr().out
    assert positive(-1) == -1
    settings.write_text(
        settings.read_text(encoding="utf-8").replace('"off"', '"on"'), encoding="utf-8"
    )
    assert main(["status"]) == 0
    assert "Verträge on" in capsys.readouterr().out
    with pytest.raises(deal.PreContractError):
        positive(-1)
