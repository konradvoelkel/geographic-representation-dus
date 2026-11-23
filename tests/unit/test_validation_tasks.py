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
from georep.spans import SPAN_SCHEMA, sort_spans
from georep.validation.codebook import Codebook
from georep.validation.tasks import Document, build_task, show_document
from tests.validation_project import CODEBOOK, PROJECT, corpus_frame, make_project


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Layout:
    layout = make_project(tmp_path)
    monkeypatch.chdir(tmp_path / "repo")
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
    assert all(
        a == {"id": a["id"], "codebuch_version": "1", "bv": None, "begruendung": ""}
        for a in answers
    )
    corpus = {row["id"]: row for row in corpus_frame().iter_rows(named=True)}
    first = tasks[0]
    doc = first["dokumente"][0]
    assert doc["id"] == first["id"] and doc["titel"] == f"Titel {first['id']}"
    assert doc["ausschnitt"] == corpus[first["id"]]["text"][:60] and doc["ausschnitt_ende"] == 60
    question = first["fragen"][0]
    assert [o["wert"] for o in question["optionen"]] == ["ja", "nein"] and first["antwort"] is None
    assert question["frage"].startswith("Enthält") and first["codebuch_version"] == "1"
    assert "positive" not in json.dumps(first)  # die Auswertung steht nicht im Auftrag
    brief = (folder / "codebuch.md").read_text(encoding="utf-8")
    assert "Kodierer A" in brief and "`ja`: Der Ausschnitt nennt" in brief


def test_the_repository_folder_carries_no_council_text(project: Layout, tmp_path: Path) -> None:
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    for path in (tmp_path / "repo" / "validierung").rglob("*"):
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
    rows[0]["bv"] = "ja"
    answers.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert main(["validate", "tasks", PROJECT, "--coder", "A"]) == 1
    assert "trägt schon Antworten (1)" in capsys.readouterr().err
    assert main(["validate", "tasks", PROJECT, "--coder", "A", "--force"]) == 0
    assert all(r["bv"] is None for r in _lines(answers))


def test_a_sample_of_another_profile_is_refused(
    project: Layout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    meta = tmp_path / "repo" / "validierung" / PROJECT / "stichprobe.json"
    data = json.loads(meta.read_text(encoding="utf-8"))
    meta.write_text(json.dumps(data | {"profil": "anders"}), encoding="utf-8")
    assert main(["validate", "tasks", PROJECT, "--coder", "B"]) == 1
    assert "Profil 'anders'" in capsys.readouterr().err


def test_raw_texts_come_from_the_raw_store_by_file_name(project: Layout, tmp_path: Path) -> None:
    (tmp_path / "repo" / "validierung" / PROJECT / "codebuch.toml").write_text(
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


def spans_frame(rows: list[tuple[str, int, int, str]], texts: dict[str, str]) -> pl.DataFrame:
    """Spannen im Schema von F3, ``value`` wörtlich aus dem Text."""
    return sort_spans(
        pl.DataFrame(
            {
                "id": [r[0] for r in rows],
                "start": [r[1] for r in rows],
                "end": [r[2] for r in rows],
                "kind": [r[3] for r in rows],
                "value": [texts[r[0]][r[1] : r[2]] for r in rows],
                "norm": ["n"] * len(rows),
                "section": [""] * len(rows),
                "extractor": ["test"] * len(rows),
            },
            schema=SPAN_SCHEMA,
        )
    )


@pytest.fixture
def antraege(project: Layout, tmp_path: Path) -> dict[str, str]:
    """Die Stichprobe neu: alle 15 Anträge (d00 bis d14); die Texte je Dokument."""
    (tmp_path / "repo" / "validierung" / PROJECT / "codebuch.toml").write_text(
        CODEBOOK.replace("size = 9", "size = 15").replace(
            'stratum = "paper_type"', 'stratum = "paper_type"\nstrata = ["Antrag"]'
        ),
        encoding="utf-8",
    )
    assert main(["validate", "sample", PROJECT, "--force"]) == 0
    return dict(corpus_frame().select("id", "text").iter_rows())


def _tasks_with(tmp_path: Path, spans: pl.DataFrame) -> dict[str, dict[str, object]]:
    spans.write_parquet(tmp_path / "spannen.parquet")
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
    return {t["id"]: t for t in _lines(tmp_path / "lokal" / PROJECT / "A" / "auftrag.jsonl")}


def test_spans_of_a_document_are_highlighted_without_their_kind(
    antraege: dict[str, str], tmp_path: Path
) -> None:
    spans = spans_frame(
        [("d00", 0, 4, "wort"), ("d00", 100, 104, "wort"), ("d01", 4, 7, "wort")], antraege
    )
    tasks = _tasks_with(tmp_path, spans)
    shown = tasks["d00"]["dokumente"][0]["spannen"]  # type: ignore[index]
    assert shown == [{"start": 0, "end": 4, "text": "text"}]  # 100..104 liegt hinter 60
    assert '"art"' not in json.dumps(tasks["d00"]) and '"n"' not in json.dumps(tasks["d00"])


def test_show_kind_shows_the_kind(antraege: dict[str, str], tmp_path: Path) -> None:
    (tmp_path / "repo" / "validierung" / PROJECT / "codebuch.toml").write_text(
        CODEBOOK.replace("size = 9", "size = 15")
        .replace('stratum = "paper_type"', 'stratum = "paper_type"\nstrata = ["Antrag"]')
        .replace("[text]\n", "[text]\nshow_kind = true\n"),
        encoding="utf-8",
    )
    tasks = _tasks_with(tmp_path, spans_frame([("d00", 0, 4, "wort")], antraege))
    assert tasks["d00"]["dokumente"][0]["spannen"] == [  # type: ignore[index]
        {"start": 0, "end": 4, "art": "wort", "text": "text"}
    ]


def test_spans_outside_the_schema_of_f3_are_refused(
    antraege: dict[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Befund 3: ``check_spans`` prüft Schema, Folge und Grenzen gegen die gewählte Textquelle."""
    spans = spans_frame([("d00", 0, 4, "wort"), ("d01", 4, 7, "wort")], antraege).reverse()
    spans.write_parquet(tmp_path / "spannen.parquet")
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
    assert "nicht nach id, start, end, kind sortiert" in capsys.readouterr().err


def test_a_span_whose_value_is_not_its_text_names_both(
    antraege: dict[str, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F3: ``value`` ist der Text an der Stelle, wörtlich; weicht er ab, zeigen die Positionen auf
    einen anderen Text (etwa Spannen aus dem Rohtext in einem Auftrag aus dem Korpus)."""
    spans = spans_frame([("d00", 0, 4, "wort")], antraege).with_columns(
        pl.lit("TEXT").alias("value"), pl.lit("roh").alias("extractor")
    )
    spans.write_parquet(tmp_path / "spannen.parquet")
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


SPAN_UNITS = (
    CODEBOOK.replace('unit = "document"', 'unit = "span"')
    .replace("size = 9", "size = 2")
    .replace('stratum = "paper_type"', 'stratum = "kind"\npopulation = "spannen.parquet"')
)


def test_a_span_unit_is_checked_against_its_text_and_not_shown_twice(
    project: Layout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Befunde 2 und 3: die Einheitsspanne steht in ``markiert``, nicht noch einmal unter
    ``spannen``, und ihr ``value`` wird gegen den Text des Auftrags geprüft."""
    texts = dict(corpus_frame().select("id", "text").iter_rows())
    spans = spans_frame([("d00", 0, 4, "wort"), ("d00", 9, 12, "wort")], texts)
    spans.write_parquet(project.root / "spannen.parquet")
    (tmp_path / "repo" / "validierung" / PROJECT / "codebuch.toml").write_text(
        SPAN_UNITS.replace("[text]\n", '[text]\nspans = "spannen.parquet"\n'), encoding="utf-8"
    )
    assert main(["validate", "sample", PROJECT, "--force"]) == 0
    assert main(["validate", "tasks", PROJECT, "--coder", "A"]) == 0
    tasks = {t["id"]: t for t in _lines(tmp_path / "lokal" / PROJECT / "A" / "auftrag.jsonl")}
    doc = tasks["d00|0|4|wort"]["dokumente"][0]
    assert doc["markiert"].startswith("⟦text⟧")
    assert [s["start"] for s in doc["spannen"]] == [9]  # die andere Spanne, nicht die eigene
    spans.with_columns(pl.lit("TEXT").alias("value")).write_parquet(
        project.root / "spannen.parquet"
    )
    assert main(["validate", "tasks", PROJECT, "--coder", "A", "--force"]) == 1
    assert "nicht die der Stichprobe" in capsys.readouterr().err


def test_showing_the_kind_of_the_units_own_spans_is_refused(
    project: Layout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    texts = dict(corpus_frame().select("id", "text").iter_rows())
    spans_frame([("d00", 0, 4, "wort"), ("d01", 0, 4, "zahl")], texts).write_parquet(
        project.root / "spannen.parquet"
    )
    (tmp_path / "repo" / "validierung" / PROJECT / "codebuch.toml").write_text(
        SPAN_UNITS.replace("[text]\n", '[text]\nspans = "spannen.parquet"\nshow_kind = true\n'),
        encoding="utf-8",
    )
    assert main(["validate", "sample", PROJECT, "--force"]) == 0
    assert main(["validate", "tasks", PROJECT, "--coder", "A"]) == 1
    assert "Ausgabe des Verfahrens" in capsys.readouterr().err


# --- Einheiten als Funktion --------------------------------------------------------------------

DOC = Document("d1", "Titel", "0123456789" * 10)


def test_a_span_unit_shows_a_window_and_marks_its_span() -> None:
    codebook = _codebook(CODEBOOK.replace("[text]\n", "[text]\nwindow = 5\n"))
    record, outside = show_document(DOC, codebook, [], (20, 23))
    assert (record["ausschnitt_start"], record["ausschnitt_ende"]) == (15, 28)
    assert record["ausschnitt"] == "5678901234567"
    assert record["spanne"] == {"start": 5, "end": 8, "text": "012"}
    assert record["markiert"] == "56789⟦012⟧34567" and outside == 0


def test_a_span_outside_the_text_names_the_source() -> None:
    with pytest.raises(SchemaError, match="außerhalb des Textes"):
        show_document(DOC, _codebook(), [], (95, 101))


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


def test_a_pair_with_span_shows_a_window_in_the_second_document() -> None:
    """Vorhaben 14: zwei Dokumente, die Fundstelle als Fenster in B; ohne Fundstelle der Anfang."""
    other = Document("d2", "B", "x" * 50 + "AUS/008/2026" + "y" * 50)
    documents = {"d1": DOC, "d2": other}
    codebook = _codebook(
        CODEBOOK.replace('unit = "document"', 'unit = "pair_with_span"').replace(
            "[text]\n", "[text]\nwindow = 10\n"
        )
    )
    row = {"id": "d1|d2", "id_a": "d1", "id_b": "d2", "start": "50", "end": "62"}
    task, _ = build_task(row, codebook, documents, {})
    second = task["dokumente"][1]
    assert second["markiert"] == "x" * 10 + "⟦AUS/008/2026⟧" + "y" * 10
    task, _ = build_task(row | {"start": None, "end": None}, codebook, documents, {})
    assert "markiert" not in task["dokumente"][1] and task["dokumente"][1]["ausschnitt_start"] == 0
