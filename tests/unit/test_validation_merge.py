"""Zusammenführen und Schlichten (F4): ``georep validate merge``, ``labels.csv`` und README."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.cli import main
from georep.validation.codebook import Question
from georep.validation.merge import Models, _first_is_a, mark_agreement, sentence
from tests.validation_project import CODEBOOK, PROJECT, fill_answers, make_project

MODEL = "claude-opus-5-5"
OTHER = "anderes-modell"


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


def test_merge_needs_a_model_for_every_role(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ohne ``--model`` braucht jede der drei Rollen ihr Modell; sonst ist es ein Bedienfehler."""
    with pytest.raises(SystemExit) as exit_info:
        main(["validate", "merge", PROJECT, "--model-a", MODEL, "--model-b", OTHER])
    assert exit_info.value.code == 2
    assert "--model-adjudicator" in capsys.readouterr().err


def _disputed_two(project: Path) -> None:
    """A sagt überall ja, B zweimal nein; die Schlichtung entscheidet beide für ja."""
    ids = _ids(project)
    fill(project, "A", lambda unit: "ja")
    fill(project, "B", lambda unit: "nein" if unit in ids[:2] else "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    path = project / "lokal" / PROJECT / "schlichtung" / "antworten.jsonl"
    rows = [r | {"bv": "ja"} for r in _lines(path)]
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def test_merge_names_the_model_of_each_role(project: Path) -> None:
    """Frage 19 (Konrad, 2026-11-26): B ist für neue Messungen ein anderes Modell als A und die
    Schlichtung. README, guete.json und der Satz für die Seite nennen alle drei Rollen."""
    _disputed_two(project)
    args = ["--model-a", MODEL, "--model-b", OTHER, "--model-adjudicator", MODEL]
    assert main(["validate", "merge", PROJECT, *args]) == 0
    folder = project / "repo" / "validierung" / PROJECT
    quality = json.loads((folder / "guete.json").read_text(encoding="utf-8"))
    assert quality["modelle"] == {"kodierer_a": MODEL, "kodierer_b": OTHER, "schlichtung": MODEL}
    assert quality["satz"] == (
        f"geprüft von zwei KI-Kodierern ({MODEL} und {OTHER}) an 9 Dokumenten, "
        f"Schlichtung durch {MODEL}, nicht von Menschen"
    )
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert f"Kodierer A `{MODEL}`, Kodierer B `{OTHER}`, Schlichtung `{MODEL}`" in readme


def test_model_is_the_default_of_every_role_without_its_own(project: Path) -> None:
    _disputed_two(project)
    assert main(["validate", "merge", PROJECT, "--model", MODEL, "--model-b", OTHER]) == 0
    quality = json.loads(
        (project / "repo" / "validierung" / PROJECT / "guete.json").read_text(encoding="utf-8")
    )
    assert quality["modelle"] == {"kodierer_a": MODEL, "kodierer_b": OTHER, "schlichtung": MODEL}


@pytest.mark.parametrize(
    ("models", "disputed", "expected"),
    [
        # die bisherigen Labels: alle drei Rollen ein Modell, auch mit Schlichtung
        (
            Models.same("m1"),
            3,
            "geprüft von zwei KI-Kodierern desselben Modells (m1) an 5 Dokumenten, "
            "nicht von Menschen",
        ),
        # die neue Regel: B ein anderes Modell, die Schlichtung wie A
        (
            Models("m1", "m2", "m1"),
            3,
            "geprüft von zwei KI-Kodierern (m1 und m2) an 5 Dokumenten, Schlichtung durch m1, "
            "nicht von Menschen",
        ),
        # ohne Uneinigkeit hat niemand geschlichtet: der Satz nennt keine Schlichtung
        (
            Models("m1", "m2", "m1"),
            0,
            "geprüft von zwei KI-Kodierern (m1 und m2) an 5 Dokumenten, nicht von Menschen",
        ),
        # A und B gleich, die Schlichtung ein anderes Modell
        (
            Models("m1", "m1", "m3"),
            1,
            "geprüft von zwei KI-Kodierern desselben Modells (m1) an 5 Dokumenten, "
            "Schlichtung durch m3, nicht von Menschen",
        ),
    ],
)
def test_the_sentence_names_the_models(models: Models, disputed: int, expected: str) -> None:
    """Die Form des Satzes steht in docs/decisions.md, Punkt 71 (F4-Nachzug, 2026-11-27)."""
    assert sentence(models, 5, "document", disputed) == expected


def _as_before_the_models(folder: Path) -> None:
    """guete.json und README in der Form bis zum 2026-11-26: ``modell``, ein Satz ohne Modell."""
    path = folder / "guete.json"
    quality = json.loads(path.read_text(encoding="utf-8"))
    earlier = {("modell" if key == "modelle" else key): value for key, value in quality.items()} | {
        "modell": quality["modelle"]["kodierer_a"],
        "satz": f"geprüft von zwei KI-Kodierern an {quality['einheiten']} Dokumenten, "
        "nicht von Menschen",
    }
    path.write_text(json.dumps(earlier, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = folder / "README.md"
    lines = [
        line.replace(
            "zwei KI-Kodierer, unabhängig", f"zwei KI-Kodierer, Modell `{MODEL}`, unabhängig"
        )
        for line in readme.read_text(encoding="utf-8").split("\n")
        if not line.startswith("- **Modelle**:")
    ]
    readme.write_text("\n".join(lines), encoding="utf-8")


def test_restate_brings_earlier_labels_into_the_new_form_and_nothing_else(project: Path) -> None:
    """V3, Punkt 2: die bisherigen Labels bekommen Satz und Modellfelder aus dem, was guete.json
    schon nennt (ein Modell für alle Rollen); Labels, Zahlen und jede andere Zeile bleiben."""
    _disputed_two(project)
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    folder = project / "repo" / "validierung" / PROJECT
    names = ("guete.json", "README.md", "labels.csv")
    merged = {name: (folder / name).read_bytes() for name in names}
    _as_before_the_models(folder)
    assert (folder / "guete.json").read_bytes() != merged["guete.json"]
    assert main(["validate", "restate", PROJECT]) == 0
    assert {name: (folder / name).read_bytes() for name in names} == merged
    assert main(["validate", "restate", PROJECT]) == 0  # ein zweiter Lauf ändert nichts
    assert {name: (folder / name).read_bytes() for name in names} == merged


def test_restate_refuses_a_readme_that_does_not_fit_its_quality_file(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _disputed_two(project)
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    path = project / "repo" / "validierung" / PROJECT / "guete.json"
    quality = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(quality | {"uneinig": 5}, ensure_ascii=False), encoding="utf-8")
    assert main(["validate", "restate", PROJECT]) == 1
    assert "passt nicht zu guete.json" in capsys.readouterr().err


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
    assert "Kein menschlicher Goldstandard" in readme
    assert f"Kodierer A `{MODEL}`, Kodierer B `{MODEL}`, Schlichtung `{MODEL}`" in readme
    assert "Version 1" in readme and "geschichtet nach `paper_type`" in readme
    assert "Uneinigkeiten gab es keine" in readme and "die 0 Uneinigkeiten" not in readme
    assert "α ≥ 0,80" in readme  # zwei Nachkommastellen (Befund 8)
    quality = json.loads((folder / "guete.json").read_text(encoding="utf-8"))
    assert quality["satz"] == (
        f"geprüft von zwei KI-Kodierern desselben Modells ({MODEL}) an 9 Dokumenten, "
        "nicht von Menschen"
    )
    assert quality["modelle"] == {"kodierer_a": MODEL, "kodierer_b": MODEL, "schlichtung": MODEL}
    assert "modell" not in quality
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


def test_whitespace_ignore_compares_text_without_any_whitespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vorhaben 11 und 12: pypdf setzt Leerraum unterschiedlich („66 - Amt" gegen „66-Amt");
    mit ``whitespace = "ignore"`` ist das keine Uneinigkeit, das Label behält den Text von A."""
    codebook = CODEBOOK.replace(
        "[sample]",
        """[[questions]]
id = "amt"
question = "Amt im Kopf."
scale = "open"
whitespace = "ignore"

[sample]""",
    )
    make_project(tmp_path, codebook)
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "sample", PROJECT]) == 0
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    fill(tmp_path, "A", lambda u: {"bv": "ja", "amt": "66 - Amt für Verkehr"})
    fill(tmp_path, "B", lambda u: {"bv": "ja", "amt": "66-AmtfürVerkehr"})
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    amt = _labels(tmp_path).filter(pl.col("frage") == "amt")
    assert set(amt.get_column("label")) == {'"66 - Amt für Verkehr"'}
    assert set(amt.get_column("kodierer_b")) == {'"66-AmtfürVerkehr"'}
    quality = json.loads((tmp_path / "repo" / "validierung" / PROJECT / "guete.json").read_text())
    assert quality["fragen"]["amt"]["einig"] == 9


def test_markings_agree_by_text_and_occurrence() -> None:
    """Einheit marking (Recall, Vorhaben 12): gemeinsam markiert, nur bei einem, F1 = 2g/(2g+e).

    Gleich ist eine Markierung mit gleichem Text und Vorkommen; die Art gehört zu den Fragen an die
    Stelle, nicht zum Abgleich der Stellen."""
    question = Question(id="spannen", question="?", scale="spans")
    marks = [{"text": "rat", "vorkommen": 1, "art": "x"}, {"text": "sache", "vorkommen": 2}]
    first = [question.canonical(marks), question.canonical(marks)]
    second = [question.canonical(marks[:1]), question.canonical([m | {"art": "z"} for m in marks])]
    result = mark_agreement(question, first, second)
    assert (result.marks_common, result.marks_single) == (3, 1)
    assert result.alpha() == pytest.approx(6 / 7) and result.agreed == 1


def test_an_adjudication_can_name_who_decided(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Vorhaben 12: vier Entscheide traf der Auswerter nach den Regeln des Schlichters, nicht der
    Schlichter; ``herkunft`` in der Antwortzeile sagt das, README und guete.json zählen es."""
    ids = _ids(project)
    fill(project, "A", lambda unit: "ja")
    fill(project, "B", lambda unit: "nein" if unit in ids[:2] else "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    path = project / "lokal" / PROJECT / "schlichtung" / "antworten.jsonl"
    rows = _lines(path)
    for row in rows:
        row["bv"] = "ja"
        if row["id"] == ids[0]:
            row["herkunft"] = "Auswerter nach den Regeln des Schlichters, Runde 1"
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    folder = project / "repo" / "validierung" / PROJECT
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert "davon 1 Einheit: Auswerter nach den Regeln des Schlichters, Runde 1" in readme
    quality = json.loads((folder / "guete.json").read_text(encoding="utf-8"))
    assert quality["schlichtung_herkunft"] == {
        "Auswerter nach den Regeln des Schlichters, Runde 1": 1
    }


def test_an_adjudication_of_an_agreed_unit_is_passed_over(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Vorhaben 12: die vorläufige Schlichtung entschied drei Einheiten, die nach F4 einig sind
    (ein leerer Text gilt wie null); sie stören nicht, sie werden genannt."""
    ids = _ids(project)
    fill(project, "A", lambda unit: "ja")
    fill(project, "B", lambda unit: "nein" if unit == ids[0] else "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    path = project / "lokal" / PROJECT / "schlichtung" / "antworten.jsonl"
    rows = [r | {"bv": "ja"} for r in _lines(path)]
    rows.append({"id": ids[1], "codebuch_version": "1", "bv": "ja", "begruendung": "überzählig"})
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    capsys.readouterr()
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    assert "1 Schlichtungen ohne Uneinigkeit übergangen" in capsys.readouterr().out


def test_an_unordered_list_compares_as_a_set() -> None:
    """Vorhaben 15: urheber ist eine Mehrfachauswahl; die Folge der Einträge zählt nicht."""
    question = Question(id="urheber", question="?", scale="open", unordered=True)
    assert (
        question.canonical(["SPD", "CDU"]) == question.canonical(["CDU", "SPD"]) == '["CDU", "SPD"]'
    )
    assert (
        Question(id="liste", question="?", scale="open").canonical(["SPD", "CDU"])
        == '["SPD", "CDU"]'
    )
