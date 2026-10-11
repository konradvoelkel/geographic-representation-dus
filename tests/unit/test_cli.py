from __future__ import annotations

from pathlib import Path

import pytest

from georep.cli import main


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


def test_bootstrap_run_status_export_regress(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["bootstrap"]) == 0
    assert "200 Paper und 200 Texte" in capsys.readouterr().out
    assert main(["run", "--dry-run"]) == 0
    assert "5 übersprungen, 8 geplant" in capsys.readouterr().out
    assert main(["run"]) == 0
    assert "8 ausgeführt, 5 übersprungen" in capsys.readouterr().out
    assert main(["status"]) == 0
    status = capsys.readouterr().out
    assert status.count("aktuell") >= 7 and "200 Dokumente" in status and "[Netz]" in status
    assert main(["export"]) == 0
    assert "7 CSV-Dateien" in capsys.readouterr().out
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
