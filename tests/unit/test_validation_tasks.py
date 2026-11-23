"""Der Kodierauftrag (F4): ``georep validate tasks``, Ausschnitte, Spannen, nichts im Repo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.cli import main
from georep.errors import SchemaError
from georep.layout import Layout
from georep.validation.codebook import Codebook
from georep.validation.tasks import Document, build_task, excerpt
from tests.validation_project import CODEBOOK, PROJECT, corpus_frame, make_project


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Layout:
    layout = make_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["validate", "sample", PROJECT]) == 0
    return layout


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _codebook(text: str = CODEBOOK) -> Codebook:
    import tomllib

    return Codebook.model_validate(tomllib.loads(text))


def test_tasks_write_assignment_answers_and_brief_locally(
    project: Layout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", "tasks", PROJECT, "--coder", "A"]) == 0
    assert "9 Einheiten" in capsys.readouterr().out
    folder = tmp_path / "lokal" / PROJECT / "A"
    tasks = _lines(folder / "auftrag.jsonl")
    answers = _lines(folder / "antworten.jsonl")
    assert len(tasks) == 9 and [a["id"] for a in answers] == [t["id"] for t in tasks]
    assert all(a == {"id": a["id"], "label": None, "begruendung": ""} for a in answers)
    corpus = {row["id"]: row for row in corpus_frame().iter_rows(named=True)}
    first = tasks[0]
    doc = first["dokumente"][0]
    assert doc["id"] == first["id"] and doc["titel"] == f"Titel {first['id']}"
    assert doc["ausschnitt"] == corpus[first["id"]]["text"][:60] and doc["ausschnitt_ende"] == 60
    assert [o["wert"] for o in first["optionen"]] == ["ja", "nein"] and first["antwort"] is None
    assert first["frage"].startswith("Enthält") and first["codebuch_version"] == "1"
    brief = (folder / "codebuch.md").read_text(encoding="utf-8")
    assert "Kodierer A" in brief and "`ja`: Der Ausschnitt nennt" in brief


def test_the_repository_folder_carries_no_council_text(project: Layout, tmp_path: Path) -> None:
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    for path in (tmp_path / "validierung").rglob("*"):
        if path.is_file():
            assert "der rat beschliesst" not in path.read_text(encoding="utf-8"), path


def test_the_two_coders_see_the_same_units_in_different_orders(
    project: Layout, tmp_path: Path
) -> None:
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    first = [t["id"] for t in _lines(tmp_path / "lokal" / PROJECT / "A" / "auftrag.jsonl")]
    second = [t["id"] for t in _lines(tmp_path / "lokal" / PROJECT / "B" / "auftrag.jsonl")]
    assert sorted(first) == sorted(second) and first != second


def test_started_answers_are_not_overwritten_without_force(
    project: Layout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", "tasks", PROJECT, "--coder", "A"]) == 0
    answers = tmp_path / "lokal" / PROJECT / "A" / "antworten.jsonl"
    rows = _lines(answers)
    rows[0]["label"] = "ja"
    answers.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert main(["validate", "tasks", PROJECT, "--coder", "A"]) == 1
    assert "trägt schon Antworten (1)" in capsys.readouterr().err
    assert main(["validate", "tasks", PROJECT, "--coder", "A", "--force"]) == 0
    assert all(r["label"] is None for r in _lines(answers))


def test_a_sample_of_another_profile_is_refused(
    project: Layout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    meta = tmp_path / "validierung" / PROJECT / "stichprobe.json"
    data = json.loads(meta.read_text(encoding="utf-8"))
    meta.write_text(json.dumps(data | {"profil": "anders"}), encoding="utf-8")
    assert main(["validate", "tasks", PROJECT, "--coder", "B"]) == 1
    assert "Profil 'anders'" in capsys.readouterr().err


def test_raw_texts_come_from_the_raw_store_by_file_name(project: Layout, tmp_path: Path) -> None:
    (tmp_path / "validierung" / PROJECT / "codebuch.toml").write_text(
        CODEBOOK.replace("[text]\n", '[text]\nsource = "raw"\n'), encoding="utf-8"
    )
    raw = corpus_frame().select(
        pl.col("file_name").alias("name"), pl.lit("Erste Zeile\nGROSS geschrieben").alias("text")
    )
    store = tmp_path / "rohtext.parquet"
    raw.write_parquet(store)
    assert main(["validate", "tasks", PROJECT, "--coder", "A"]) == 1  # neben dem Textstore fehlt er
    assert main(["validate", "tasks", PROJECT, "--coder", "A", "--texts", str(store)]) == 0
    task = _lines(tmp_path / "lokal" / PROJECT / "A" / "auftrag.jsonl")[0]
    assert task["dokumente"][0]["ausschnitt"] == "Erste Zeile\nGROSS geschrieben"


def test_spans_of_a_document_are_highlighted_inside_the_excerpt(
    project: Layout, tmp_path: Path
) -> None:
    texts = dict(corpus_frame().select("id", "text").iter_rows())
    spans = pl.DataFrame(
        {
            "id": ["d00", "d00", "d01"],
            "start": [0, 100, 4],
            "end": [4, 104, 7],
            "kind": ["wort", "wort", "wort"],
            "value": [texts["d00"][0:4], texts["d00"][100:104], texts["d01"][4:7]],
            "norm": ["n1", "n2", "n3"],
        }
    )
    spans.write_parquet(tmp_path / "spannen.parquet")
    for name in ("d00", "d01"):
        sample = tmp_path / "validierung" / PROJECT / "stichprobe.csv"
        frame = pl.read_csv(sample)
        if name not in frame.get_column("id").to_list():
            frame = pl.concat(
                [frame.head(frame.height - 1), pl.DataFrame({"id": [name], "schicht": ["Antrag"]})]
            )
            frame.sort("id").write_csv(sample)
    args = [
        "validate",
        "tasks",
        PROJECT,
        "--coder",
        "A",
        "--spans",
        str(tmp_path / "spannen.parquet"),
    ]
    assert main(args) == 0
    tasks = {t["id"]: t for t in _lines(tmp_path / "lokal" / PROJECT / "A" / "auftrag.jsonl")}
    shown = tasks["d00"]["dokumente"][0]["spannen"]
    assert shown == [
        {"start": 0, "end": 4, "art": "wort", "text": "text"}
    ]  # 100..104 liegt hinter 60
    assert "value" not in json.dumps(tasks["d00"]) and "n1" not in json.dumps(tasks["d00"])


def test_a_span_whose_value_is_not_its_text_names_both(
    project: Layout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F3: ``value`` ist der Text an der Stelle, wörtlich; weicht er ab, zeigen die Positionen auf
    einen anderen Text (etwa Spannen aus dem Rohtext in einem Auftrag aus dem Korpus)."""
    sample = pl.read_csv(tmp_path / "validierung" / PROJECT / "stichprobe.csv")
    first = sample.get_column("id")[0]
    pl.DataFrame(
        {
            "id": [first],
            "start": [0],
            "end": [4],
            "kind": ["wort"],
            "value": ["TEXT"],
            "extractor": ["roh"],
        }
    ).write_parquet(tmp_path / "spannen.parquet")
    args = [
        "validate",
        "tasks",
        PROJECT,
        "--coder",
        "A",
        "--spans",
        str(tmp_path / "spannen.parquet"),
    ]
    assert main(args) == 1
    err = capsys.readouterr().err
    assert "'TEXT'" in err and "'text'" in err and "roh" in err


# --- Einheiten als Funktion --------------------------------------------------------------------

DOC = Document("d1", "Titel", "0123456789" * 10)


def test_a_span_unit_shows_a_window_and_marks_its_span() -> None:
    codebook = _codebook(CODEBOOK.replace("[text]\n", "[text]\nwindow = 5\n"))
    record, outside = excerpt(DOC, codebook, [], (20, 23))
    assert (record["ausschnitt_start"], record["ausschnitt_ende"]) == (15, 28)
    assert record["ausschnitt"] == "5678901234567"
    assert record["spanne"] == {"start": 5, "end": 8, "text": "012"}
    assert record["markiert"] == "56789⟦012⟧34567" and outside == 0


def test_a_span_outside_the_text_names_the_source() -> None:
    with pytest.raises(SchemaError, match="außerhalb des Textes"):
        excerpt(DOC, _codebook(), [], (95, 101))


def test_a_pair_shows_both_documents_and_a_query_shows_its_question() -> None:
    other = Document("d2", "Zweiter", "abc")
    documents = {"d1": DOC, "d2": other}
    pair = _codebook(CODEBOOK.replace('unit = "document"', 'unit = "document_pair"'))
    task, _ = build_task({"id": "d1|d2", "id_a": "d1", "id_b": "d2"}, pair, documents, {})
    assert [d["id"] for d in task["dokumente"]] == ["d1", "d2"]
    query = _codebook(
        CODEBOOK.replace('unit = "document"', 'unit = "query_document"').replace(
            "[text]\n", '[text]\ncontext = ["wahlbezirk"]\n'
        )
    )
    row = {"id": "radweg|d2", "anfrage": "radweg", "dokument": "d2", "wahlbezirk": "7"}
    task, _ = build_task(row, query, documents, {})
    assert task["anfrage"] == "radweg" and task["kontext"] == {"wahlbezirk": "7"}
    assert task["dokumente"][0]["ausschnitt"] == "abc"
