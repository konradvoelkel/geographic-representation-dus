"""Schritte mit Modell (F5): nur mit ``--models``, Kennung des Modells im Stamp, CLI-Schalter."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from georep import cli
from georep.errors import ModelError
from georep.layout import Layout
from georep.pipeline import Step, freshness, run_pipeline, run_step
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

    def identity(self) -> dict[str, str]:
        self.asked.append(1)
        return self._identity()

    def stamp(self) -> dict[str, object]:
        return {**self.identity(), "limit": self.limit, "open": self.open}


def _model_step(
    out: Path,
    identity: dict[str, str],
    asked: list[int],
    *,
    name: str = "modell",
    leaves_open: int = 0,
) -> Step:
    use = Use(lambda: dict(identity), asked)

    def run() -> str:
        out.write_text("ergebnis", encoding="utf-8")
        use.limit, use.open = (2 if leaves_open else 0), leaves_open
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
    assert stamp["models"] == IDENTITY | {"limit": 0, "open": 0}
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


def test_cli_status_names_an_unreachable_model_server_instead_of_failing(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def down() -> dict[str, str]:
        raise ModelError("ollama unter http://ollama.test nicht erreichbar")

    _only_model_steps(monkeypatch, lambda: dict(IDENTITY), [])
    assert cli.main(["run", "--models"]) == 0
    _only_model_steps(monkeypatch, down, [])
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    line = next(x for x in capsys.readouterr().out.splitlines() if x.startswith("modell "))
    assert "offen" in line and "nicht erreichbar" in line and "[Modell]" in line
