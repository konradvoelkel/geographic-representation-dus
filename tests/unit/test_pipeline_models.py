"""Schritte mit Modell (F5): nur mit ``--models``, Kennung des Modells im Stamp, CLI-Schalter."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from georep import cli
from georep.errors import ModelError, ModelUnreachableError
from georep.layout import Layout
from georep.pipeline import Step, freshness, run_pipeline, run_step
from georep.profiling import profile_step
from georep.settings import Settings, load_settings

IDENTITY = {"model": "fake-embed:latest", "digest": "e" * 64, "prompt": "dok-1"}


class Use:
    """Ein ``ModelStamp`` als Tabelle: ``identity`` zählt die Fragen, ``open`` setzt der Lauf."""

    def __init__(
        self, identity: Callable[[], dict[str, str]], asked: list[int] | None = None
    ) -> None:
        self._identity = identity
        self.asked = [] if asked is None else asked
        self.limit = 0
        self.open = 0
        self.failed = 0

    def identity(self) -> dict[str, str]:
        self.asked.append(1)
        return self._identity()

    def stamp(self) -> dict[str, object]:
        return {**self.identity(), "limit": self.limit, "open": self.open, "failed": self.failed}


def _model_step(
    out: Path,
    identity: dict[str, str],
    asked: list[int],
    *,
    name: str = "modell",
    leaves_open: int = 0,
    failed: int = 0,
) -> Step:
    use = Use(lambda: dict(identity), asked)

    def run() -> str:
        out.write_text("ergebnis", encoding="utf-8")
        use.limit, use.open, use.failed = (2 if leaves_open else 0), leaves_open, failed
        return "1 Ergebnis"

    return Step(name, (), (out,), run, models=use)


@pytest.fixture
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def test_a_model_step_is_skipped_without_the_switch_and_asks_nothing(
    tmp_path: Path, settings: Settings
) -> None:
    asked: list[int] = []
    outcome = run_step(_model_step(tmp_path / "out.txt", IDENTITY, asked), settings)
    assert outcome.status == "übersprungen" and "--models" in outcome.reason
    assert asked == [] and not (tmp_path / "out.txt").exists()


def test_with_the_switch_it_runs_and_stamps_the_model(tmp_path: Path, settings: Settings) -> None:
    step = _model_step(tmp_path / "out.txt", IDENTITY, [])
    assert run_step(step, settings, models=True).status == "ausgeführt"
    stamp = json.loads(step.stamp_path.read_text(encoding="utf-8"))
    assert stamp["models"] == IDENTITY | {"limit": 0, "open": 0, "failed": 0}
    assert run_step(step, settings, models=True).reason == "aktuell"


def test_a_partial_run_is_not_current(tmp_path: Path, settings: Settings) -> None:
    """Befund 3 des Reviews: ein Lauf mit ``limit`` ließ Eingaben offen und galt danach als aktuell."""
    out = tmp_path / "out.txt"
    partial = _model_step(out, IDENTITY, [], leaves_open=3)
    run_step(partial, settings, models=True)
    stamp = json.loads(partial.stamp_path.read_text(encoding="utf-8"))
    assert stamp["models"]["open"] == 3 and stamp["models"]["limit"] == 2
    assert freshness(partial, settings) == (False, "offen: 3 Eingaben")
    complete = _model_step(out, IDENTITY, [])
    assert run_step(complete, settings, models=True).reason.startswith("offen: 3 Eingaben")
    assert freshness(complete, settings) == (True, "aktuell")


def test_a_run_with_failed_inputs_says_how_many_failed(tmp_path: Path, settings: Settings) -> None:
    out = tmp_path / "out.txt"
    step = _model_step(out, IDENTITY, [], leaves_open=2, failed=1)
    run_step(step, settings, models=True)
    assert freshness(step, settings) == (False, "offen: 2 Eingaben, davon 1 gescheitert")


def test_another_digest_or_prompt_makes_the_step_stale(tmp_path: Path, settings: Settings) -> None:
    out = tmp_path / "out.txt"
    run_step(_model_step(out, IDENTITY, []), settings, models=True)
    for changed in ({"digest": "f" * 64}, {"prompt": "dok-2"}, {"model": "anderes:latest"}):
        fresh, reason = freshness(_model_step(out, IDENTITY | changed, []), settings)
        assert not fresh and reason == "Modell oder Prompt geändert"


def test_a_step_without_model_keeps_its_stamp_as_before(tmp_path: Path, settings: Settings) -> None:
    out = tmp_path / "plain.txt"

    def run() -> str:
        out.write_text("x", encoding="utf-8")
        return "1"

    step = Step("plain", (), (out,), run)
    run_step(step, settings)
    assert "models" not in json.loads(step.stamp_path.read_text(encoding="utf-8"))
    assert freshness(step, settings) == (True, "aktuell")


def test_run_pipeline_passes_the_switch_on(tmp_path: Path, settings: Settings) -> None:
    steps = [_model_step(tmp_path / "out.txt", IDENTITY, [])]
    assert run_pipeline(steps, settings)[0].status == "übersprungen"
    assert run_pipeline(steps, settings, models=True)[0].status == "ausgeführt"


# --- die Kommandozeile -----------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path, mini_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\nreference_root = "{mini_root}"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _only_model_steps(
    monkeypatch: pytest.MonkeyPatch, identity: Callable[[], dict[str, str]], seen: list[Settings]
) -> None:
    """``build_steps`` der CLI liefert nur einen Modellschritt; ``seen`` hält die Settings fest."""

    def build(settings: Settings, layout: Layout) -> list[Step]:
        seen.append(settings)
        out = layout.processed / "modell.txt"

        def run() -> str:
            out.write_text("x", encoding="utf-8")
            return "1 Ergebnis"

        return [Step("modell", (), (out,), run, models=Use(identity))]

    monkeypatch.setattr(cli, "build_steps", build)


def test_cli_runs_model_steps_only_with_models(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[Settings] = []
    _only_model_steps(monkeypatch, lambda: dict(IDENTITY), seen)
    assert cli.main(["steps"]) == 0
    assert "[Modell]" in capsys.readouterr().out
    assert cli.main(["run"]) == 0
    assert "Modelle aus" in capsys.readouterr().out
    assert cli.main(["run", "--models", "--limit", "3"]) == 0
    assert "modell       ausgeführt" in capsys.readouterr().out
    assert seen[-1].ml.limit == 3 and seen[0].ml.limit == 0


def test_cli_limit_without_models_is_an_operating_error(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["run", "--limit", "3"]) == 2
    assert "--limit gilt nur mit --models" in capsys.readouterr().err


# --- ohne Server (Befund 5 des Reviews) ----------------------------------------------------------


def _down() -> dict[str, str]:
    raise ModelUnreachableError("ollama unter http://ollama.test nicht erreichbar")


def test_a_missing_server_fails_the_model_step_instead_of_the_run(
    tmp_path: Path, settings: Settings
) -> None:
    step = Step("modell", (), (tmp_path / "out.txt",), lambda: "1", models=Use(_down))
    outcome = run_step(step, settings, models=True)
    assert outcome.status == "fehlgeschlagen" and "nicht erreichbar" in outcome.reason


def test_a_dry_run_still_plans_a_model_step_without_server(
    tmp_path: Path, settings: Settings
) -> None:
    step = Step("modell", (), (tmp_path / "out.txt",), lambda: "1", models=Use(_down))
    outcome = run_step(step, settings, models=True, dry_run=True)
    assert outcome.status == "geplant" and outcome.reason.startswith("Frische unbekannt")


def test_a_model_error_while_running_fails_the_step(tmp_path: Path, settings: Settings) -> None:
    def run() -> str:
        raise ModelError("10 Fehlschläge in Folge")

    step = Step("modell", (), (tmp_path / "out.txt",), run, models=Use(lambda: dict(IDENTITY)))
    outcome = run_step(step, settings, models=True)
    assert outcome.status == "fehlgeschlagen" and "in Folge" in outcome.reason
    assert not step.stamp_path.exists()


def test_cli_prints_every_line_and_exits_1_when_a_model_step_failed(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def build(settings: Settings, layout: Layout) -> list[Step]:
        out = layout.processed / "danach.txt"

        def run() -> str:
            out.write_text("x", encoding="utf-8")
            return "1 Datei"

        return [
            Step("modell", (), (layout.processed / "modell.txt",), lambda: "1", models=Use(_down)),
            Step("danach", (), (out,), run),
        ]

    monkeypatch.setattr(cli, "build_steps", build)
    assert cli.main(["run", "--models"]) == 1
    out = capsys.readouterr().out
    assert "modell       fehlgeschlagen" in out and "danach       ausgeführt" in out
    assert "1 fehlgeschlagen" in out


def test_cli_status_says_unknown_without_server(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _only_model_steps(monkeypatch, lambda: dict(IDENTITY), [])
    assert cli.main(["run", "--models"]) == 0
    _only_model_steps(monkeypatch, _down, [])
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    line = next(x for x in capsys.readouterr().out.splitlines() if x.startswith("modell "))
    assert "unbekannt" in line and "offen" not in line
    assert "nicht erreichbar" in line and "[Modell]" in line


def test_profile_runs_a_model_step_with_models(tmp_path: Path, settings: Settings) -> None:
    out = tmp_path / "out.txt"
    step = _model_step(out, IDENTITY, [])
    skipped = profile_step(step, settings, tmp_path / "prof", models=False)
    assert skipped.path is None and "--models" in skipped.outcome.reason
    ran = profile_step(step, settings, tmp_path / "prof", models=True)
    assert ran.outcome.status == "ausgeführt" and ran.path is not None and ran.path.exists()


def test_cli_refuses_a_negative_limit(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Befund 9 des Reviews (Probe 8): ``--limit -5`` kam als ``ml.limit = -5`` am Validator vorbei."""
    with pytest.raises(SystemExit) as stopped:
        cli.main(["run", "--models", "--limit", "-5"])
    assert stopped.value.code == 2 and "nicht negativ" in capsys.readouterr().err


def test_the_model_limit_is_validated_like_the_settings(settings: Settings) -> None:
    assert cli._with_model_limit(settings, 7).ml.limit == 7
    with pytest.raises(ValidationError):
        cli._with_model_limit(settings, -1)
