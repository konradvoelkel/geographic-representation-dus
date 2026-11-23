"""Zusammenführen und Schlichten (F4): ``georep validate merge``, ``labels.csv`` und README."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.cli import main
from tests.validation_project import PROJECT, fill_answers, make_project

MODEL = "claude-opus-5-5"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["validate", "sample", PROJECT]) == 0
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    return tmp_path


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def fill(project: Path, who: str, label: Callable[[str], str | None]) -> None:
    fill_answers(project / "lokal", PROJECT, who, label)


def _ids(project: Path) -> list[str]:
    return (
        pl.read_csv(project / "validierung" / PROJECT / "stichprobe.csv").get_column("id").to_list()
    )


def test_merge_needs_complete_answers(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 1
    assert "ohne Label 9" in capsys.readouterr().err


def test_merge_needs_the_model(project: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["validate", "merge", PROJECT])
    assert exit_info.value.code == 2


def test_agreeing_coders_give_labels_without_adjudication(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fill(project, "A", lambda unit: "ja")
    fill(project, "B", lambda unit: "ja" if unit != _ids(project)[0] else "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    out = capsys.readouterr().out
    assert "9 Einheiten, einig 9 (100,0 %)" in out and "0 Uneinigkeiten" in out
    folder = project / "validierung" / PROJECT
    labels = pl.read_csv(folder / "labels.csv", schema_overrides={"schlichtung": pl.String})
    assert labels.columns == ["id", "kodierer_a", "kodierer_b", "schlichtung", "label"]
    assert labels.get_column("label").to_list() == ["ja"] * 9
    assert labels.get_column("schlichtung").fill_null("").to_list() == [""] * 9
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert f"Modell `{MODEL}`" in readme and "Kein menschlicher Goldstandard" in readme
    assert "Version 1" in readme and "geschichtet nach `paper_type`" in readme
    assert "Uneinigkeiten gab es keine" in readme and "die 0 Uneinigkeiten" not in readme
    quality = json.loads((folder / "guete.json").read_text(encoding="utf-8"))
    assert quality["satz"] == "geprüft von zwei KI-Kodierern an 9 Dokumenten, nicht von Menschen"
    # alle sagen ja: keine Streuung, α und κ sind nicht definiert, Stufe 3 also nicht erreicht
    assert quality["uebereinstimmung"]["krippendorff_alpha_nominal"] is None
    assert quality["alpha_genuegt"] is False
    assert not (project / "lokal" / PROJECT / "schlichtung").exists()


def test_disagreements_go_to_adjudication_and_then_into_the_labels(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _ids(project)
    first = {unit: ("ja" if i % 2 else "nein") for i, unit in enumerate(ids)}
    disputed = ids[:2]
    fill(project, "A", lambda unit: first[unit])
    fill(
        project,
        "B",
        lambda unit: (
            first[unit] if unit not in disputed else ("ja" if first[unit] == "nein" else "nein")
        ),
    )
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    assert "Schlichtung offen: 2 von 2" in capsys.readouterr().out
    folder = project / "lokal" / PROJECT / "schlichtung"
    tasks = _lines(folder / "auftrag.jsonl")
    assert sorted(t["id"] for t in tasks) == sorted(disputed)
    assert {t["kodierung_1"]["label"] for t in tasks} | {
        t["kodierung_2"]["label"] for t in tasks
    } == {"ja", "nein"}
    assert tasks[0]["kodierung_1"]["begruendung"].startswith("A meint")
    assert "Schlichtung" in (folder / "codebuch.md").read_text(encoding="utf-8")
    assert not (project / "validierung" / PROJECT / "labels.csv").exists()

    fill(project, "schlichtung", lambda unit: "ja" if unit == disputed[0] else None)
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    assert "Schlichtung offen: 1 von 2" in capsys.readouterr().out
    assert _lines(folder / "antworten.jsonl")[0]["label"] is not None  # nicht überschrieben

    fill(project, "schlichtung", lambda unit: "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    assert "Labels ->" in capsys.readouterr().out
    labels = pl.read_csv(
        project / "validierung" / PROJECT / "labels.csv",
        schema_overrides={"schlichtung": pl.String},
    )
    rows = {row["id"]: row for row in labels.iter_rows(named=True)}
    for unit in ids:
        if unit in disputed:
            assert rows[unit]["schlichtung"] == "ja" and rows[unit]["label"] == "ja"
        else:
            assert rows[unit]["schlichtung"] in (None, "") and rows[unit]["label"] == first[unit]
    readme = (project / "validierung" / PROJECT / "README.md").read_text(encoding="utf-8")
    assert "die 2 Uneinigkeiten entschied ein dritter Agent" in readme
    assert "77,8 %" in readme  # 7 von 9 einig
    for path in (project / "validierung").rglob("*"):
        if path.is_file():  # Begründungen bleiben lokal
            assert "meint" not in path.read_text(encoding="utf-8"), path

    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 1
    assert "--force" in capsys.readouterr().err
    assert main(["validate", "merge", PROJECT, "--model", MODEL, "--force"]) == 0


@pytest.mark.parametrize(
    ("break_it", "message"),
    [
        (lambda rows: rows[0].update(label="vielleicht"), "Label nicht im Codebuch 1"),
        (lambda rows: rows.append(dict(rows[0])), "doppelt 1"),
        (lambda rows: rows.pop(), "fehlt 1"),
        (lambda rows: rows[0].update(id="fremd"), "unbekannte id 1"),
    ],
)
def test_a_broken_answer_file_is_named(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    break_it: Callable[[list[dict[str, Any]]], object],
    message: str,
) -> None:
    fill(project, "A", lambda unit: "ja")
    fill(project, "B", lambda unit: "ja")
    path = project / "lokal" / PROJECT / "B" / "antworten.jsonl"
    rows = _lines(path)
    break_it(rows)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 1
    err = capsys.readouterr().err
    assert "B/antworten.jsonl: nicht vollständig" in err and message in err
