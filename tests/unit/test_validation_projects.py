"""Die Vorhaben unter ``validierung/`` im Format von F4, und Vorhaben 14 nachgerechnet (Abnahme).

Vorhaben 14 hat vor F4 kodieren lassen (zwei Runden, Messdokument docs/plans/14-vorgaenge.md,
§ 4.1 und § 4.2). Seine Codebücher, Stichproben und Labels sind ins Format von F4 übertragen;
``score`` rechnet aus den Dateien im Repo genau die Zahlen des Messdokuments nach. Wo die
vorläufigen Antwortdateien lokal liegen (Konrads Rechner), rechnet ``import`` und ``merge`` die
Labels daraus nach, Zeile für Zeile.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from georep.cli import main
from georep.validation.codebook import load_codebook
from georep.validation.paths import ValidationPaths
from georep.validation.sample import read_sample

REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / "validierung"
CODING = Path("/media/konrad/xtraspace/georep/messdaten/kodierung/14-vorgaenge")
REPO_FILES = ("codebuch.toml", "stichprobe.csv", "stichprobe.json", "labels.csv", "guete.json")


# Die Vorhaben, die im Format von F4 vorliegen. Vorhaben 15 kam nach der zweiten Runde von F4
# auf main und ist noch im vorläufigen Format (docs/validierung.md, § 7).
CONVERTED = sorted(p.parent.name for p in VALIDATION.glob("1[1-4]-*/codebuch.toml"))


@pytest.mark.parametrize("folder", CONVERTED, ids=str)
def test_every_codebook_in_the_repository_is_valid(folder: str) -> None:
    """Jedes Codebuch unter validierung/ ist im Format von F4 und passt zu seiner Stichprobe."""
    codebook = load_codebook(VALIDATION / folder / "codebuch.toml", folder)
    paths = ValidationPaths(folder, VALIDATION / folder, Path("/nirgends"))
    sample = read_sample(paths, codebook)
    assert (
        sample.height == codebook.sample.size
        and sample.get_column("id").n_unique() == sample.height
    )


def _copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project: str) -> Path:
    repo = tmp_path / "repo"
    target = repo / "validierung" / project
    target.mkdir(parents=True)
    for name in REPO_FILES:
        shutil.copy(VALIDATION / project / name, target / name)
    (repo / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\n'
        f'validation.root = "{repo / "validierung"}"\n'
        f'validation.coding_root = "{tmp_path / "lokal"}"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    return target


@pytest.mark.parametrize(
    ("project", "alphas", "hits", "share", "weighted"),
    [
        # § 4.1: α 1,000 / 0,819 / 0,935; Kantenpräzision 139/150 = 0,927, gewichtet 0,922
        ("14-vorgaenge", (1.0, 0.819, 0.935), (139, 150), 0.927, 0.922),
        # § 4.2: α 1,000 / 0,922 / 0,923; Kantenpräzision 85/100 = 0,850, gewichtet 0,840
        ("14-vorgaenge-2", (1.0, 0.922, 0.923), (85, 100), 0.850, 0.840),
    ],
)
def test_score_recomputes_the_numbers_of_project_14(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    project: str,
    alphas: tuple[float, float, float],
    hits: tuple[int, int],
    share: float,
    weighted: float,
) -> None:
    target = _copy(tmp_path, monkeypatch, project)
    assert main(["validate", "score", project]) == 0
    quality: dict[str, Any] = json.loads((target / "guete.json").read_text(encoding="utf-8"))
    questions = quality["fragen"]
    found = tuple(
        round(questions[q]["krippendorff_alpha"], 3)
        for q in ("nummer_gemeint", "selbe_sache", "beziehung")
    )
    assert found == alphas
    edges = questions["selbe_sache"]["treffer"]
    assert (edges["stichprobe"]["treffer"], edges["stichprobe"]["gewertet"]) == hits
    assert round(edges["stichprobe"]["anteil"], 3) == share
    assert round(edges["grundgesamtheit"]["schaetzer"], 3) == weighted


@pytest.mark.skipif(
    not CODING.is_dir(), reason="die vorläufigen Antworten liegen nur auf Konrads Rechner"
)
@pytest.mark.parametrize("project", ["14-vorgaenge", "14-vorgaenge-2"])
def test_import_and_merge_rebuild_the_labels_of_project_14(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project: str
) -> None:
    target = _copy(tmp_path, monkeypatch, project)
    (target / "labels.csv").unlink()
    assert main(["validate", "import", project, "--from", str(CODING)]) == 0
    assert main(["validate", "merge", project, "--model", "claude-opus-5-5"]) == 0
    assert (target / "labels.csv").read_bytes() == (
        VALIDATION / project / "labels.csv"
    ).read_bytes()
