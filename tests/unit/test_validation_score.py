"""Die Güte gegen die Labels (F4): ``georep validate score``, Gewichte, Vorhersagen, Rangfolgen."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.cli import main
from georep.validation.measures import classify_scores, ndcg_at_k, stratified_share
from tests.validation_project import CODEBOOK, PROJECT, fill_answers, make_project

MODEL = "claude-opus-5-5"


def fill(project: Path, who: str, label: Callable[[str], object]) -> None:
    fill_answers(project / "lokal", PROJECT, who, label)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_project(tmp_path)
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "sample", PROJECT]) == 0
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    return tmp_path


def _sample(project: Path) -> pl.DataFrame:
    return pl.read_csv(project / "repo" / "validierung" / PROJECT / "stichprobe.csv")


def _quality(project: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(
        (project / "repo" / "validierung" / PROJECT / "guete.json").read_text(encoding="utf-8")
    )
    return loaded


@pytest.fixture
def merged(project: Path) -> dict[str, str]:
    """A und B einig bis auf eine Einheit, die die Schlichtung mit „ja" entscheidet."""
    ids = _sample(project).get_column("id").to_list()
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


def test_score_weights_the_strata_and_keeps_the_sample_share_apart(
    project: Path, merged: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Befund 1: je Schicht, in der Stichprobe und für die Grundgesamtheit (N_h/n_h)."""
    assert main(["validate", "score", PROJECT]) == 0
    out = capsys.readouterr().out
    positives = sum(1 for label in merged.values() if label == "ja")
    assert f"in der Stichprobe {positives} von 9" in out and "gewichtet mit N_h/n_h" in out
    assert "Stufe 3 verlangt ≥ 0,80" in out
    assert "geprüft von zwei KI-Kodierern an 9 Dokumenten, nicht von Menschen" in out
    sample = _sample(project)
    hits: dict[str, tuple[int, int]] = {}
    for unit, layer in sample.select("id", "schicht").iter_rows():
        x, m = hits.get(layer, (0, 0))
        hits[layer] = (x + (merged[unit] == "ja"), m + 1)
    sizes = dict(sample.select("schicht", "schicht_n").unique().iter_rows())
    expected = stratified_share(hits, sizes)
    found = _quality(project)["fragen"]["bv"]
    assert found["labels"] == {"ja": positives, "nein": 9 - positives}
    assert found["treffer"]["stichprobe"]["treffer"] == positives
    assert found["treffer"]["grundgesamtheit"]["schaetzer"] == expected.estimate
    assert found["treffer"]["grundgesamtheit"]["selbstgewichtend"] is False
    assert set(found["treffer"]["je_schicht"]) == {"Antrag", "Anfrage", "Vorlage"}
    assert found["einig"] == 8 and _quality(project)["modell"] == MODEL


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
    assert "Verfahren: Genauigkeit" in out and "für die Grundgesamtheit" in out
    quality = _quality(project)
    assert quality["vorhersage"]["datei"] == "pred.parquet"
    scores = quality["fragen"]["bv"]["verfahren"]
    assert scores["genauigkeit"] == expected.accuracy
    assert scores["makro"]["f1"] == expected.macro_f1
    assert scores["klassen"][0]["praezision"] == expected.of("ja").precision
    assert scores["konfusion"]["zeilen_gold"] == [list(row) for row in expected.confusion]
    assert 0.0 <= scores["genauigkeit_grundgesamtheit"]["schaetzer"] <= 1.0


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
        (lambda ids: pl.DataFrame({"id": ids}), "Spalten id, frage und label"),
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
    .replace('scale = "binary"\npositive = ["ja"]', 'scale = "ordinal"')
    .replace('value = "ja"', 'value = "teilweise"')
    .replace('value = "nein"', 'value = "relevant"')
    .replace(
        "[[questions.options]]\n",
        '[[questions.options]]\nvalue = "nicht"\ndefinition = "hat nichts damit zu tun"\n\n'
        "[[questions.options]]\n",
        1,
    )
    .replace("size = 9", "size = 6")
    .replace('stratum = "paper_type"', 'stratum = "query"')
)
JUDGED = {
    "radweg|d00": "relevant",
    "radweg|d01": "nicht",
    "radweg|d02": "teilweise",
    "schule|d03": "nicht",
    "schule|d04": "nicht",
    "schule|d05": "nicht",
}


@pytest.fixture
def ranked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_project(tmp_path, RANKING)
    monkeypatch.chdir(tmp_path / "repo")
    pool = pl.DataFrame(
        {"query": ["radweg"] * 3 + ["schule"] * 3, "id": ["d00", "d01", "d02", "d03", "d04", "d05"]}
    )
    pool.write_parquet(tmp_path / "pool.parquet")
    assert (
        main(["validate", "sample", PROJECT, "--population", str(tmp_path / "pool.parquet")]) == 0
    )
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0
    fill_answers(tmp_path / "lokal", PROJECT, "A", lambda unit: JUDGED[unit])
    fill_answers(tmp_path / "lokal", PROJECT, "B", lambda unit: JUDGED[unit])
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    return tmp_path


def test_a_ranking_is_scored_with_ndcg_over_the_judged_documents(
    ranked: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pred = pl.DataFrame(
        {
            "query": ["radweg"] * 4 + ["schule"],
            "id": ["d01", "d02", "x9", "d00", "d03"],
            "score": [0.9, 0.8, 0.85, 0.1, 0.5],
        }
    )
    pred.write_parquet(ranked / "rang.parquet")
    assert main(["validate", "score", PROJECT, "--pred", str(ranked / "rang.parquet")]) == 0
    expected = ndcg_at_k(
        {"d01": 0.9, "d02": 0.8, "d00": 0.1}, {"d00": 2.0, "d01": 0.0, "d02": 1.0}, 10
    )
    ranking = json.loads(
        (ranked / "repo" / "validierung" / PROJECT / "guete.json").read_text(encoding="utf-8")
    )["rangfolge"]
    assert ranking["ndcg_je_anfrage"] == {"radweg": expected, "schule": None}
    assert ranking["ndcg_mittel"] == expected and ranking["ohne_relevantes"] == 1
    assert ranking["judged_at_k"]["radweg"] == 0.75  # x9 ist nicht geurteilt
    assert "nDCG@10" in capsys.readouterr().out


@pytest.mark.parametrize("bad", [float("nan"), None, float("inf")])
def test_a_score_that_is_not_finite_is_a_schema_error(
    ranked: Path, capsys: pytest.CaptureFixture[str], bad: float | None
) -> None:
    """Befund 4: ``None`` und NaN standen vorn; jetzt sind sie ein Fehler."""
    pl.DataFrame(
        {"query": ["radweg", "radweg"], "id": ["d00", "d01"], "score": [bad, 0.3]},
        schema={"query": pl.String, "id": pl.String, "score": pl.Float64},
    ).write_parquet(ranked / "rang.parquet")
    assert main(["validate", "score", PROJECT, "--pred", str(ranked / "rang.parquet")]) == 1
    assert "nicht endlich" in capsys.readouterr().err
