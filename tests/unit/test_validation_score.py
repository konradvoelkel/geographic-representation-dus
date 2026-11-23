"""Die Güte gegen die Labels (F4): ``georep validate score``, ohne und mit Vorhersagen."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.cli import main
from georep.validation.measures import classify_scores, ndcg_at_k
from tests.validation_project import CODEBOOK, PROJECT, fill_answers, make_project

MODEL = "claude-opus-5-5"


def fill(project: Path, who: str, label: Callable[[str], str | None]) -> None:
    fill_answers(project / "lokal", PROJECT, who, label)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["validate", "sample", PROJECT]) == 0
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    return tmp_path


def _ids(project: Path) -> list[str]:
    return (
        pl.read_csv(project / "validierung" / PROJECT / "stichprobe.csv").get_column("id").to_list()
    )


def _quality(project: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(
        (project / "validierung" / PROJECT / "guete.json").read_text(encoding="utf-8")
    )
    return loaded


@pytest.fixture
def merged(project: Path) -> dict[str, str]:
    """A und B einig bis auf eine Einheit, die die Schlichtung mit „ja" entscheidet."""
    ids = _ids(project)
    gold = {unit: ("ja" if i % 3 else "nein") for i, unit in enumerate(ids)}
    fill(project, "A", lambda unit: gold[unit])
    fill(project, "B", lambda unit: gold[unit] if unit != ids[0] else "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    fill(project, "schlichtung", lambda unit: "ja")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    return gold | {ids[0]: "ja"}


def test_score_before_merge_is_a_missing_input(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", "score", PROJECT]) == 1
    assert "validate merge" in capsys.readouterr().err


def test_score_without_a_method_reports_the_coders_and_the_positive_share(
    project: Path, merged: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", "score", PROJECT]) == 0
    out = capsys.readouterr().out
    positives = sum(1 for label in merged.values() if label == "ja")
    assert f"positiv: {positives} von 9" in out
    assert "Stufe 3 verlangt ≥ 0,8" in out
    assert "geprüft von zwei KI-Kodierern an 9 Dokumenten, nicht von Menschen" in out
    quality = _quality(project)
    assert quality["labels"] == {"ja": positives, "nein": 9 - positives}
    assert quality["positiv"]["anzahl"] == positives and quality["modell"] == MODEL
    assert quality["uebereinstimmung"]["einig"] == 8 and "verfahren" not in quality


def test_score_with_predictions_is_classify_scores_against_the_final_labels(
    project: Path, merged: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    ids = sorted(merged)
    guess = {unit: ("ja" if i < 6 else "nein") for i, unit in enumerate(ids)}
    pl.DataFrame({"id": ids, "label": [guess[u] for u in ids]}).write_parquet(
        project / "pred.parquet"
    )
    assert main(["validate", "score", PROJECT, "--pred", str(project / "pred.parquet")]) == 0
    expected = classify_scores([merged[u] for u in ids], [guess[u] for u in ids], ["ja", "nein"])
    out = capsys.readouterr().out
    assert "Verfahren: Genauigkeit" in out and "  ja: Präzision" in out
    method = _quality(project)["verfahren"]
    assert method["vorhersage"] == "pred.parquet" and len(method["vorhersage_sha256"]) == 64
    scores = method["klassifikation"]
    assert scores["genauigkeit"] == expected.accuracy
    assert scores["makro"]["f1"] == expected.macro_f1
    assert scores["klassen"][0]["praezision"] == expected.of("ja").precision
    assert scores["konfusion"]["zeilen_gold"] == [list(row) for row in expected.confusion]


@pytest.mark.parametrize(
    ("frame", "message"),
    [
        (
            lambda ids: pl.DataFrame({"id": ids[1:], "label": ["ja"] * (len(ids) - 1)}),
            "ohne Vorhersage",
        ),
        (
            lambda ids: pl.DataFrame({"id": ids, "label": ["vielleicht"] * len(ids)}),
            "außerhalb des Codebuchs",
        ),
        (lambda ids: pl.DataFrame({"id": ids}), "Spalten id und label"),
    ],
)
def test_unusable_predictions_are_named(
    project: Path,
    merged: dict[str, str],
    capsys: pytest.CaptureFixture[str],
    frame: Any,
    message: str,
) -> None:
    frame(sorted(merged)).write_parquet(project / "pred.parquet")
    assert main(["validate", "score", PROJECT, "--pred", str(project / "pred.parquet")]) == 1
    assert message in capsys.readouterr().err


RANKING = (
    CODEBOOK.replace('unit = "document"', 'unit = "query_document"')
    .replace('scale = "binary"', 'scale = "ordinal"')
    .replace('positive = "ja"', "")
    .replace('value = "ja"', 'value = "teilweise"')
    .replace('value = "nein"', 'value = "relevant"')
    .replace(
        "[[options]]\n",
        '[[options]]\nvalue = "nicht"\ndefinition = "hat nichts damit zu tun"\n\n[[options]]\n',
        1,
    )
    .replace("size = 9", "size = 6")
    .replace('stratum = "paper_type"', 'stratum = "query"')
)


def test_a_ranking_is_scored_with_ndcg_per_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    make_project(tmp_path, RANKING)
    monkeypatch.chdir(tmp_path)
    pool = pl.DataFrame(
        {"query": ["radweg"] * 3 + ["schule"] * 3, "id": ["d00", "d01", "d02", "d03", "d04", "d05"]}
    )
    pool.write_parquet(tmp_path / "pool.parquet")
    assert (
        main(["validate", "sample", PROJECT, "--population", str(tmp_path / "pool.parquet")]) == 0
    )
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    judged = {
        "radweg|d00": "relevant",
        "radweg|d01": "nicht",
        "radweg|d02": "teilweise",
        "schule|d03": "nicht",
        "schule|d04": "nicht",
        "schule|d05": "nicht",
    }
    fill(tmp_path, "A", lambda unit: judged[unit])
    fill(tmp_path, "B", lambda unit: judged[unit])
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    pred = pl.DataFrame(
        {
            "query": ["radweg"] * 4 + ["schule"],
            "id": ["d01", "d02", "x9", "d00", "d03"],
            "score": [0.9, 0.8, 0.7, 0.1, 0.5],
        }
    )
    pred.write_parquet(tmp_path / "rang.parquet")
    assert main(["validate", "score", PROJECT, "--pred", str(tmp_path / "rang.parquet")]) == 0
    expected = ndcg_at_k(["d01", "d02", "x9", "d00"], {"d00": 2.0, "d01": 0.0, "d02": 1.0}, 10)
    ranking = json.loads(
        (tmp_path / "validierung" / PROJECT / "guete.json").read_text(encoding="utf-8")
    )["verfahren"]["rangfolge"]
    assert ranking["ndcg_je_anfrage"] == {"radweg": expected, "schule": None}
    assert ranking["ndcg_mittel"] == expected and ranking["ohne_relevantes"] == 1
    assert "nDCG@10" in capsys.readouterr().out
