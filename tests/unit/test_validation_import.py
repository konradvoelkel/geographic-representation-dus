"""Vorläufige Antworten übernehmen (F4): ``georep validate import``, danach ``merge`` wie sonst."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl
import pytest

from georep.cli import main
from tests.validation_project import CODEBOOK, PROJECT, make_project

PROVISIONAL = (
    CODEBOOK
    + """
[provisional]
key = "aufgabe"
fields = { beschluss = "bv" }
values = { bv = { "true" = "ja", "false" = "nein" } }
reason = ["begruendung", "bemerkung"]
"""
)


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


@pytest.fixture
def provisional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, list[str]]:
    make_project(tmp_path, PROVISIONAL)
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "sample", PROJECT]) == 0
    ids = (
        pl.read_csv(tmp_path / "repo" / "validierung" / PROJECT / "stichprobe.csv")
        .get_column("id")
        .to_list()
    )
    source = tmp_path / "vorlaeufig"
    source.mkdir()
    _write(
        source / "antworten-A.jsonl",
        [{"aufgabe": u, "beschluss": True, "bemerkung": "A"} for u in ids]
        + [{"aufgabe": "fremd", "beschluss": False}],
    )
    _write(
        source / "antworten-B.jsonl",
        [{"aufgabe": u, "beschluss": u != ids[0], "begruendung": "B"} for u in ids],
    )
    _write(
        source / "schlichtung.jsonl", [{"aufgabe": ids[0], "beschluss": False, "begruendung": "S"}]
    )
    return source, ids


def test_import_converts_and_merge_counts_as_usual(
    provisional: tuple[Path, list[str]], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, ids = provisional
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
    assert main(["validate", "import", PROJECT, "--from", str(source)]) == 0
    out = capsys.readouterr().out
    assert "A: 9 Einheiten übernommen, 1 Zeilen nicht in der Stichprobe" in out
    assert "schlichtung: 1 Einheiten übernommen" in out
    answers = [
        json.loads(line)
        for line in (tmp_path / "lokal" / PROJECT / "A" / "antworten.jsonl")
        .read_text()
        .splitlines()
    ]
    assert answers[0] == {"id": ids[0], "codebuch_version": "1", "bv": "ja", "begruendung": "A"}
    assert main(["validate", "merge", PROJECT, "--model", "claude-opus-5-5"]) == 0
    labels = pl.read_csv(
        tmp_path / "repo" / "validierung" / PROJECT / "labels.csv", infer_schema=False
    )
    first = labels.filter(pl.col("id") == ids[0]).row(0, named=True)
    assert (first["kodierer_a"], first["kodierer_b"], first["schlichtung"], first["label"]) == (
        "ja",
        "nein",
        "nein",
        "nein",
    )
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
    assert after == before  # die Quelldateien bleiben, wie sie sind


def test_import_does_not_overwrite_answers_without_force(
    provisional: tuple[Path, list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    source, _ = provisional
    assert main(["validate", "import", PROJECT, "--from", str(source)]) == 0
    assert main(["validate", "import", PROJECT, "--from", str(source)]) == 1
    assert "--force" in capsys.readouterr().err
    assert main(["validate", "import", PROJECT, "--from", str(source), "--force"]) == 0


def test_a_row_without_the_key_field_is_a_schema_error(
    provisional: tuple[Path, list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    source, _ = provisional
    _write(source / "antworten-B.jsonl", [{"beschluss": True}])
    assert main(["validate", "import", PROJECT, "--from", str(source)]) == 1
    assert "ohne Schlüsselfeld 'aufgabe'" in capsys.readouterr().err


def test_a_long_adjudication_file_is_pivoted_per_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vorhaben 11 schlichtet je Feld eine Zeile: ``{"aufgabe", "feld", "wert", "begruendung"}``."""
    codebook = PROVISIONAL + 'adjudication_question = "feld"\nadjudication_value = "wert"\n'
    make_project(tmp_path, codebook)
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "sample", PROJECT]) == 0
    ids = (
        pl.read_csv(tmp_path / "repo" / "validierung" / PROJECT / "stichprobe.csv")
        .get_column("id")
        .to_list()
    )
    source = tmp_path / "vorlaeufig"
    source.mkdir()
    _write(source / "antworten-A.jsonl", [{"aufgabe": u, "beschluss": True} for u in ids])
    _write(source / "antworten-B.jsonl", [{"aufgabe": u, "beschluss": u != ids[0]} for u in ids])
    _write(
        source / "schlichtung.jsonl",
        [{"aufgabe": ids[0], "feld": "bv", "wert": "nein", "begruendung": "S"}],
    )
    assert main(["validate", "import", PROJECT, "--from", str(source)]) == 0
    adjudicated = json.loads(
        (tmp_path / "lokal" / PROJECT / "schlichtung" / "antworten.jsonl")
        .read_text()
        .splitlines()[0]
    )
    assert adjudicated == {"id": ids[0], "codebuch_version": "1", "bv": "nein", "begruendung": "S"}
    assert main(["validate", "merge", PROJECT, "--model", "claude-opus-5-5"]) == 0


def test_a_nested_adjudication_is_flattened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vorhaben 12 schlichtet ``{"aufgabe", "entscheid": {Frage: Antwort}, "begruendung"}``."""
    make_project(tmp_path, PROVISIONAL + 'adjudication_nested = "entscheid"\n')
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "sample", PROJECT]) == 0
    ids = (
        pl.read_csv(tmp_path / "repo" / "validierung" / PROJECT / "stichprobe.csv")
        .get_column("id")
        .to_list()
    )
    source = tmp_path / "vorlaeufig"
    source.mkdir()
    _write(source / "antworten-A.jsonl", [{"aufgabe": u, "beschluss": True} for u in ids])
    _write(source / "antworten-B.jsonl", [{"aufgabe": u, "beschluss": u != ids[0]} for u in ids])
    _write(source / "schlichtung.jsonl", [{"aufgabe": ids[0], "entscheid": {"beschluss": False}}])
    assert main(["validate", "import", PROJECT, "--from", str(source)]) == 0
    assert main(["validate", "merge", PROJECT, "--model", "claude-opus-5-5"]) == 0
    labels = pl.read_csv(
        tmp_path / "repo" / "validierung" / PROJECT / "labels.csv", infer_schema=False
    )
    assert labels.filter(pl.col("id") == ids[0]).row(0, named=True)["label"] == "nein"
