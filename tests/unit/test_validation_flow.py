"""Ein Durchlauf von der Stichprobe bis zur Zahl, über die Mini-Fixture und mit Fake-Labels (F4).

So, wie der Supervisor ein Vorhaben validieren lässt (docs/validierung.md, § 3): ``bootstrap`` und
``run corpus`` bauen den Korpus der 200 Dokumente, ``sample`` zieht 24 geschichtet nach
Dokumentart, ``tasks`` schreibt die Aufträge für A und B, zwei „Kodierer" füllen sie nach einer
festen Regel (B weicht bei drei Einheiten ab), ``merge`` schreibt den Auftrag der Schlichtung, die
„Schlichtung" entscheidet, ``merge`` legt die Labels ab, und ``score`` misst ein „Verfahren" gegen
sie. Jede Zahl in ``guete.json`` wird mit den Maßen direkt nachgerechnet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.cli import main
from georep.layout import Layout
from georep.settings import load_settings
from georep.validation.measures import classify_scores, cohen_kappa, krippendorff_alpha
from tests.validation_project import fill_answers

PROJECT = "99-durchlauf"
MODEL = "fake-kodierer"
CODEBOOK = """\
project = "99-durchlauf"
version = "2026-11-23"
unit = "document"
instructions = "Lies Titel und Ausschnitt. ja, wenn eine Forderung oder ein Auftrag dasteht."

[[questions]]
id = "fordert"
question = "Fordert das Dokument etwas von der Verwaltung?"
scale = "binary"
positive = ["ja"]

[[questions.options]]
value = "ja"
definition = "Eine Forderung oder ein Auftrag an die Verwaltung."
example = "Die Verwaltung wird beauftragt, ..."

[[questions.options]]
value = "nein"
definition = "Nur Information, Frage oder Bericht."

[sample]
size = 24
seed = 20261123
stratum = "paper_type"

[text]
chars = 400
"""


@pytest.fixture
def project(tmp_path: Path, mini_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\nreference_root = "{mini_root}"\n'
        f'context.root = "{mini_root / "context"}"\n'
        f'validation.root = "{tmp_path / "repo" / "validierung"}"\n'
        f'validation.coding_root = "{tmp_path / "kodierung"}"\n',
        encoding="utf-8",
    )
    folder = tmp_path / "repo" / "validierung" / PROJECT
    folder.mkdir(parents=True)
    (folder / "codebuch.toml").write_text(CODEBOOK, encoding="utf-8")
    monkeypatch.chdir(tmp_path / "repo")
    return tmp_path


def _tasks(project: Path, who: str) -> dict[str, dict[str, Any]]:
    path = project / "kodierung" / PROJECT / who / "auftrag.jsonl"
    return {
        task["id"]: task
        for task in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    }


def test_from_sample_to_number_with_fake_labels(project: Path) -> None:
    assert main(["bootstrap"]) == 0
    assert main(["run", "corpus"]) == 0
    assert main(["validate", "sample", PROJECT]) == 0
    sample = pl.read_csv(project / "repo" / "validierung" / PROJECT / "stichprobe.csv")
    assert sample.height == 24 and sample.get_column("id").n_unique() == 24
    for coder in ("A", "B"):
        assert main(["validate", "tasks", PROJECT, "--coder", coder]) == 0

    # Die Regel der Fake-Kodierer liest nur ihren eigenen Auftrag, wie ein Agent.
    tasks = _tasks(project, "A")
    assert tasks.keys() == _tasks(project, "B").keys()

    def rule(unit: str) -> str:
        text = tasks[unit]["dokumente"][0]["ausschnitt"]
        return "ja" if "beauftragt" in text or "antrag" in text else "nein"

    ids = sorted(tasks)
    flipped = set(ids[:3])

    def other(unit: str) -> str:
        return rule(unit) if unit not in flipped else ("nein" if rule(unit) == "ja" else "ja")

    fill_answers(project / "kodierung", PROJECT, "A", rule, "fordert")
    fill_answers(project / "kodierung", PROJECT, "B", other, "fordert")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0
    adjudication = project / "kodierung" / PROJECT / "schlichtung" / "auftrag.jsonl"
    assert sorted(
        json.loads(line)["id"] for line in adjudication.read_text().splitlines()
    ) == sorted(flipped)
    fill_answers(project / "kodierung", PROJECT, "schlichtung", rule, "fordert")
    assert main(["validate", "merge", PROJECT, "--model", MODEL]) == 0

    labels = pl.read_csv(project / "repo" / "validierung" / PROJECT / "labels.csv").sort("id")
    assert labels.get_column("frage").unique().to_list() == ["fordert"]
    assert labels.get_column("label").to_list() == [rule(unit) for unit in ids]

    # Ein „Verfahren", das nur auf den Titel schaut
    titles = {unit: tasks[unit]["dokumente"][0]["titel"].lower() for unit in ids}
    guess = {unit: "ja" if "antrag" in titles[unit] else "nein" for unit in ids}
    pl.DataFrame({"id": ids, "label": [guess[u] for u in ids]}).write_parquet(
        project / "pred.parquet"
    )
    assert main(["validate", "score", PROJECT, "--pred", str(project / "pred.parquet")]) == 0

    quality = json.loads(
        (project / "repo" / "validierung" / PROJECT / "guete.json").read_text(encoding="utf-8")
    )
    first, second = [rule(u) for u in ids], [other(u) for u in ids]
    assert quality["fragen"]["fordert"]["einig"] == 21
    assert quality["fragen"]["fordert"]["cohen_kappa"] == cohen_kappa(first, second)
    assert quality["fragen"]["fordert"]["krippendorff_alpha_nominal"] == krippendorff_alpha(
        list(zip(first, second, strict=True)), "nominal", ["ja", "nein"]
    )
    expected = classify_scores(first, [guess[u] for u in ids], ["ja", "nein"])
    assert quality["fragen"]["fordert"]["verfahren"]["genauigkeit"] == expected.accuracy
    assert quality["satz"] == "geprüft von zwei KI-Kodierern an 24 Dokumenten, nicht von Menschen"
    assert quality["modell"] == MODEL and quality["codebuch_version"] == "2026-11-23"

    # Im Repo-Ordner liegen nur Schlüssel, Labels und Zahlen, kein Ratstext.
    corpus = pl.read_parquet(Layout.from_settings(load_settings(cwd=project / "repo")).corpus)
    snippets = [t[100:140] for t in corpus.get_column("text").to_list() if len(t) > 140]
    for path in (project / "repo" / "validierung").rglob("*"):
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            assert not any(snippet in content for snippet in snippets), path
