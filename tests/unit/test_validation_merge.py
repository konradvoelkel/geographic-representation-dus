"""Zusammenführen und Schlichten (F4): ``georep validate merge``, ``labels.csv`` und README."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.cli import main
from georep.validation.merge import _first_is_a
from tests.validation_project import CODEBOOK, PROJECT, fill_answers, make_project

MODEL = "claude-opus-5-5"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_project(tmp_path)
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "sample", PROJECT]) == 0
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    return tmp_path


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def fill(project: Path, who: str, label: Callable[[str], object]) -> None:
    fill_answers(project / "lokal", PROJECT, who, label)


def _ids(project: Path) -> list[str]:
    sample = project / "repo" / "validierung" / PROJECT / "stichprobe.csv"
    return pl.read_csv(sample).get_column("id").to_list()


def _labels(project: Path) -> pl.DataFrame:
    return pl.read_csv(
        project / "repo" / "validierung" / PROJECT / "labels.csv", infer_schema=False
    ).with_columns(pl.all().fill_null(""))


def test_merge_needs_complete_answers(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 1
    assert "ohne Antwort 9" in capsys.readouterr().err


def test_merge_needs_the_model(project: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["validate", "merge", PROJECT])
    assert exit_info.value.code == 2


def test_agreeing_coders_give_labels_without_adjudication(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fill(project, "A", lambda unit: "ja")
    fill(project, "B", lambda unit: "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    out = capsys.readouterr().out
    assert "bv: 9 Einheiten, einig 9 von 9 (100,0 %)" in out and "0 Uneinigkeiten" in out
    folder = project / "repo" / "validierung" / PROJECT
    labels = _labels(project)
    assert labels.columns == ["id", "frage", "kodierer_a", "kodierer_b", "schlichtung", "label"]
    assert labels.get_column("label").to_list() == ["ja"] * 9
    assert labels.get_column("schlichtung").to_list() == [""] * 9
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert f"Modell `{MODEL}`" in readme and "Kein menschlicher Goldstandard" in readme
    assert "Version 1" in readme and "geschichtet nach `paper_type`" in readme
    assert "Uneinigkeiten gab es keine" in readme and "die 0 Uneinigkeiten" not in readme
    assert "α ≥ 0,80" in readme  # zwei Nachkommastellen (Befund 8)
    quality = json.loads((folder / "guete.json").read_text(encoding="utf-8"))
    assert quality["satz"] == "geprüft von zwei KI-Kodierern an 9 Dokumenten, nicht von Menschen"
    # alle sagen ja: keine Streuung, α ist nicht definiert und genügt darum nie
    assert quality["fragen"]["bv"]["krippendorff_alpha_nominal"] is None
    assert quality["fragen"]["bv"]["alpha_genuegt"] is False
    assert not (project / "lokal" / PROJECT / "schlichtung").exists()


def test_disagreements_go_to_adjudication_and_then_into_the_labels(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _ids(project)
    first = {unit: ("ja" if i % 2 else "nein") for i, unit in enumerate(ids)}
    disputed = ids[:2]

    def flip(unit: str) -> str:
        return first[unit] if unit not in disputed else ("ja" if first[unit] == "nein" else "nein")

    fill(project, "A", lambda unit: first[unit])
    fill(project, "B", flip)
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    assert "Schlichtung offen: 2 Einheiten" in capsys.readouterr().out
    folder = project / "lokal" / PROJECT / "schlichtung"
    tasks = _lines(folder / "auftrag.jsonl")
    assert sorted(t["id"] for t in tasks) == sorted(disputed)
    assert all(t["strittig"] == ["bv"] for t in tasks)
    labels_seen = {t["kodierung_1"]["bv"] for t in tasks} | {t["kodierung_2"]["bv"] for t in tasks}
    assert labels_seen == {"ja", "nein"} and tasks[0]["dokumente"]
    assert "Schlichtung" in (folder / "codebuch.md").read_text(encoding="utf-8")
    assert not (project / "repo" / "validierung" / PROJECT / "labels.csv").exists()

    fill(project, "schlichtung", lambda unit: "ja" if unit == disputed[0] else None)
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    assert "Schlichtung offen: 1 Einheiten" in capsys.readouterr().out
    assert _lines(folder / "antworten.jsonl")[0]["bv"] is not None  # nicht überschrieben

    fill(project, "schlichtung", lambda unit: "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    assert "Labels ->" in capsys.readouterr().out
    rows = {row["id"]: row for row in _labels(project).iter_rows(named=True)}
    for unit in ids:
        if unit in disputed:
            assert rows[unit]["schlichtung"] == "ja" and rows[unit]["label"] == "ja"
        else:
            assert rows[unit]["schlichtung"] == "" and rows[unit]["label"] == first[unit]
    readme = (project / "repo" / "validierung" / PROJECT / "README.md").read_text(encoding="utf-8")
    assert "die 2 Uneinigkeiten entschied ein dritter Agent" in readme
    assert "7 von 9 (77,8 %)" in readme
    for path in (project / "repo" / "validierung").rglob("*"):
        if path.is_file():  # Begründungen bleiben lokal
            assert "meint" not in path.read_text(encoding="utf-8"), path
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0  # Labels neu, gleich


def test_a_stale_adjudication_is_refused_until_force_resets_it(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Befund 6: nach einer Neukodierung passt die Schlichtung nicht mehr zu den Uneinigkeiten."""
    ids = _ids(project)
    fill(project, "A", lambda unit: "ja")
    fill(project, "B", lambda unit: "nein" if unit == ids[0] else "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    fill(project, "schlichtung", lambda unit: "ja")
    fill(project, "B", lambda unit: "nein" if unit == ids[1] else "ja")  # B kodiert neu
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 1
    assert "passt nicht mehr" in capsys.readouterr().err
    assert main(["validate", "merge", PROJECT, "--model", MODEL, "--force"]) == 0
    tasks = _lines(project / "lokal" / PROJECT / "schlichtung" / "auftrag.jsonl")
    assert [t["id"] for t in tasks] == [ids[1]]


def test_the_order_of_the_two_codings_depends_on_the_unit() -> None:
    """Befund 8: die Schlichtung sieht nicht immer A zuerst."""
    firsts = {_first_is_a(7, f"d{i}") for i in range(20)}
    assert firsts == {True, False}


@pytest.mark.parametrize(
    ("break_it", "message", "absent"),
    [
        (lambda rows: rows[0].update(bv="vielleicht"), "ungültige Antwort 1", "fehlt"),
        (lambda rows: rows.append(dict(rows[0])), "doppelt 1", "fehlt"),
        (lambda rows: rows.pop(), "fehlt 1", "doppelt"),
        (lambda rows: rows[0].update(id="fremd"), "unbekannte id 1", "doppelt"),
        (lambda rows: rows[0].update(id=""), "leere id 1", "doppelt"),
        (lambda rows: rows[0].update(codebuch_version="0"), "andere codebuch_version 1", "fehlt"),
    ],
)
def test_a_broken_answer_file_is_named(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    break_it: Callable[[list[dict[str, Any]]], object],
    message: str,
    absent: str,
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
    assert absent not in err  # ein ungültiges Label zählt nicht zusätzlich als „fehlt"


TWO_QUESTIONS = CODEBOOK.replace(
    "[sample]",
    """[[questions]]
id = "zeile"
question = "Erste Zeile des Beschlussvorschlags."
scale = "interval"
only_if = { question = "bv", values = ["ja"] }

[sample]""",
)


def test_a_conditional_question_is_merged_where_it_is_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    make_project(tmp_path, TWO_QUESTIONS)
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "sample", PROJECT]) == 0
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    ids = _ids(tmp_path)
    gate = {u: ("ja" if i < 5 else "nein") for i, u in enumerate(ids)}

    def coding(shift: int) -> Callable[[str], object]:
        return lambda u: {
            "bv": gate[u],
            "zeile": (ids.index(u) + shift) if gate[u] == "ja" else None,
        }

    fill(tmp_path, "A", coding(0))
    # B: dieselbe Schranke, eine Zeile anders, und bei ids[5] „ja" mit Zeile 3
    fill(
        tmp_path,
        "B",
        lambda u: (
            {"bv": "ja", "zeile": 3}
            if u == ids[5]
            else {
                "bv": gate[u],
                "zeile": (ids.index(u) + (1 if u == ids[0] else 0)) if gate[u] == "ja" else None,
            }
        ),
    )
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    tasks = {
        t["id"]: t for t in _lines(tmp_path / "lokal" / PROJECT / "schlichtung" / "auftrag.jsonl")
    }
    assert tasks[ids[0]]["strittig"] == ["zeile"] and tasks[ids[5]]["strittig"] == ["bv", "zeile"]
    path = tmp_path / "lokal" / PROJECT / "schlichtung" / "antworten.jsonl"
    rows = _lines(path)
    for row in rows:  # ids[0]: Zeile 0; ids[5]: doch „nein", also keine Zeile
        row |= {"bv": None, "zeile": 0} if row["id"] == ids[0] else {"bv": "nein", "zeile": None}
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    labels = _labels(tmp_path)
    zeilen = labels.filter(pl.col("frage") == "zeile")
    assert zeilen.height == 6  # fünf mit „ja" bei beiden, dazu ids[5], wo B „ja" sagte
    row5 = zeilen.filter(pl.col("id") == ids[5]).row(0, named=True)
    assert (row5["kodierer_a"], row5["kodierer_b"], row5["label"]) == ("", "3", "")
    assert labels.filter(pl.col("frage") == "bv").height == 9
    quality = json.loads(
        (tmp_path / "repo" / "validierung" / PROJECT / "guete.json").read_text(encoding="utf-8")
    )
    assert quality["fragen"]["zeile"]["n"] == 6 and quality["fragen"]["zeile"]["beide"] == 5
    assert quality["fragen"]["zeile"]["krippendorff_alpha_skala"] is not None


META = CODEBOOK.replace(
    "[sample]",
    """[[questions]]
id = "unsicher"
question = "Ist eine der Antworten unsicher?"
scale = "binary"
positive = ["ja"]
adjudicate = false

[[questions.options]]
value = "ja"

[[questions.options]]
value = "nein"

[sample]""",
)


def test_a_question_without_adjudication_keeps_its_disagreement_unlabelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vorhaben 11: Meta-Fragen wie „unsicher" gehen nicht an die Schlichtung (adjudicate = false)."""
    make_project(tmp_path, META)
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "sample", PROJECT]) == 0
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    ids = _ids(tmp_path)
    fill(tmp_path, "A", lambda u: {"bv": "ja", "unsicher": "nein"})
    fill(tmp_path, "B", lambda u: {"bv": "ja", "unsicher": "ja" if u == ids[0] else "nein"})
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    assert not (tmp_path / "lokal" / PROJECT / "schlichtung").exists()
    row = _labels(tmp_path).filter((pl.col("id") == ids[0]) & (pl.col("frage") == "unsicher"))
    assert row.row(0, named=True)["label"] == "" and row.row(0, named=True)["kodierer_b"] == "ja"


def test_an_empty_text_counts_as_no_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Vorhaben 12: „norm: leer bei keine" -- ein leerer Text ist keine Antwort, auch wo die Frage
    nicht gestellt ist, und bei einer offenen Frage dasselbe wie ``null``."""
    codebook = CODEBOOK.replace(
        "[sample]",
        """[[questions]]
id = "norm"
question = "Normalisierter Wert."
scale = "open"
only_if = { question = "bv", values = ["ja"] }

[sample]""",
    )
    make_project(tmp_path, codebook)
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "sample", PROJECT]) == 0
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    ids = _ids(tmp_path)
    fill(
        tmp_path,
        "A",
        lambda u: {"bv": "nein", "norm": ""} if u == ids[0] else {"bv": "ja", "norm": ""},
    )
    fill(
        tmp_path,
        "B",
        lambda u: {"bv": "nein", "norm": None} if u == ids[0] else {"bv": "ja", "norm": None},
    )
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    norms = _labels(tmp_path).filter(pl.col("frage") == "norm")
    assert norms.height == 8 and set(norms.get_column("label")) == {"null"}
