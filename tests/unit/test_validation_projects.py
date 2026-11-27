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


# Die Vorhaben im Format von F4: je ein Ordner <vorhaben>-f4 neben dem unveränderten Ordner der
# Messung, deren Messskript die alten Dateien liest (docs/validierung.md, § 3).
CONVERTED = sorted(p.parent.name for p in VALIDATION.glob("*-f4/codebuch.toml"))


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


# Jedes Vorhaben mit Labels: guete.json von merge, dazu README und die Labels.
QUALITY = sorted(p.parent.name for p in VALIDATION.glob("*/guete.json"))
ROLES = ("kodierer_a", "kodierer_b", "schlichtung")


@pytest.mark.parametrize("folder", QUALITY, ids=str)
def test_every_quality_file_names_the_model_of_each_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, folder: str
) -> None:
    """Frage 19: alle Labels bis zum 2026-11-26 kodierten und schlichteten Agenten desselben
    Modells. ``restate`` hat Satz und Modellfelder in die Form von Punkt 71 gebracht; ein Lauf über
    den Stand im Repo ändert kein Byte, auch nicht an Labels und Zahlen (V3, Punkt 2)."""
    source = VALIDATION / folder
    files = ["guete.json", "README.md", *(p.name for p in source.glob("labels*.csv"))]
    target = tmp_path / "repo" / "validierung" / folder
    target.mkdir(parents=True)
    for name in files:
        shutil.copy(source / name, target / name)
    (tmp_path / "repo" / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\n'
        f'validation.root = "{tmp_path / "repo" / "validierung"}"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "repo")
    assert main(["validate", "restate", folder]) == 0
    for name in files:
        assert (target / name).read_bytes() == (source / name).read_bytes(), name
    quality: dict[str, Any] = json.loads((source / "guete.json").read_text(encoding="utf-8"))
    assert quality["modelle"] == dict.fromkeys(ROLES, "claude-opus-5-5") and "modell" not in quality
    assert quality["satz"].startswith(
        "geprüft von zwei KI-Kodierern desselben Modells (claude-opus-5-5) an "
    )
    readme = (source / "README.md").read_text(encoding="utf-8")
    assert "- **Modelle**: Kodierer A `claude-opus-5-5`, Kodierer B `claude-opus-5-5`" in readme


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
        ("14-vorgaenge-f4", (1.0, 0.819, 0.935), (139, 150), 0.927, 0.922),
        # § 4.2: α 1,000 / 0,922 / 0,923; Kantenpräzision 85/100 = 0,850, gewichtet 0,840
        ("14-vorgaenge-2-f4", (1.0, 0.922, 0.923), (85, 100), 0.850, 0.840),
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
@pytest.mark.parametrize("project", ["14-vorgaenge-f4", "14-vorgaenge-2-f4"])
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


def test_score_recomputes_the_agreement_of_project_11(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/plans/11-struktur.md § 4.1: 200 von 200 gleich (114 mit Vorschlag zeilengenau), nur
    sitzung 199 von 200 (α 0,99); amt vergleicht ohne Leerraum wie die Messung."""
    target = _copy(tmp_path, monkeypatch, "11-struktur-f4")
    assert main(["validate", "score", "11-struktur-f4"]) == 0
    questions = json.loads((target / "guete.json").read_text(encoding="utf-8"))["fragen"]
    for question in ("bv_vorhanden", "amt", "dezernat_titel", "beratungsfolge", "briefdatum"):
        assert (questions[question]["einig"], questions[question]["beide"]) == (200, 200), question
    for question in ("bv_erste_zeile", "bv_letzte_zeile"):
        assert (questions[question]["einig"], questions[question]["beide"]) == (114, 114), question
    assert questions["sitzung"]["einig"] == 199
    assert round(questions["sitzung"]["krippendorff_alpha"], 2) == 0.99


@pytest.mark.parametrize(
    ("project", "measurement", "agreement", "share"),
    [
        # docs/plans/12-kennungen.md § 4.4: Art 360/360 (α 1,000), Grenzen 354/357 (α 0,939),
        # Norm 340/357 (α 0,952); die Präzision je Art rechnet das Messskript, nicht F4
        (
            "12-kennungen-2-f4",
            "12-kennungen",
            {"art": (360, 360, 1.0), "grenzen": (354, 357, 0.939), "norm": (340, 357, 0.952)},
            None,
        ),
        # docs/plans/16-ortsbezug.md § 4.1: bezug 195/200 (α 0,917), Begriffe 200/200; unsicher
        # A 22, B 28, beide 15, also 180 gleich; Belegzeile ohne Label in 26; handelt von je
        # Schicht 73/75, 40/49, 51/76, hochgerechnet 0,821
        (
            "16-ortsbezug-f4",
            "16-ortsbezug",
            {
                "bezug": (195, 200, 0.917),
                "begriffe_kein_bezug": (200, 200, 1.0),
                "unsicher": (180, 200, None),
                "beleg_zeile": (174, 200, None),
            },
            ({"titel_betreff": 73, "kern": 40, "begleit_rest": 51}, 0.821),
        ),
        # § 4.4: bezug 99/100 (α 0,974), Begriffe 100/100; unsicher A 11, B 8, beide 6, also 93
        # gleich; Belegzeile ohne Label in 16; handelt von 32/34, 23/32, 22/34, hochgerechnet 0,783
        (
            "16-ortsbezug-2-f4",
            "16-ortsbezug",
            {
                "bezug": (99, 100, 0.974),
                "begriffe_kein_bezug": (100, 100, 1.0),
                "unsicher": (93, 100, None),
                "beleg_zeile": (84, 100, None),
            },
            ({"titel_betreff": 32, "kern": 23, "begleit_rest": 22}, 0.783),
        ),
    ],
)
def test_import_from_the_labels_of_a_measurement_rebuilds_its_numbers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    project: str,
    measurement: str,
    agreement: dict[str, tuple[int, int, float | None]],
    share: tuple[dict[str, int], float] | None,
) -> None:
    """V3, Punkt 4: aus den Labeldateien der Messungen (``validierung/<messung>/labels*.csv``, im
    Repo) rechnen ``import``, ``merge`` und ``score`` die Zahlen der Messdokumente nach; Labels und
    guete.json sind die im Repo, bis auf das Datum des Laufs."""
    target = tmp_path / "repo" / "validierung" / project
    target.mkdir(parents=True)
    for name in ("codebuch.toml", "stichprobe.csv", "stichprobe.json"):
        shutil.copy(VALIDATION / project / name, target / name)
    (tmp_path / "repo" / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\n'
        f'validation.root = "{tmp_path / "repo" / "validierung"}"\n'
        f'validation.coding_root = "{tmp_path / "lokal"}"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "repo")
    source = VALIDATION / measurement
    assert main(["validate", "import", project, "--from", str(source)]) == 0
    assert main(["validate", "merge", project, "--model", "claude-opus-5-5"]) == 0
    assert main(["validate", "score", project]) == 0
    assert (target / "labels.csv").read_bytes() == (
        VALIDATION / project / "labels.csv"
    ).read_bytes()
    quality: dict[str, Any] = json.loads((target / "guete.json").read_text(encoding="utf-8"))
    committed = json.loads((VALIDATION / project / "guete.json").read_text(encoding="utf-8"))
    assert quality | {"datum": committed["datum"]} == committed
    for question, (agreed, both, alpha) in agreement.items():
        found = quality["fragen"][question]
        assert (found["einig"], found["beide"]) == (agreed, both), question
        if alpha is not None:
            assert round(found["krippendorff_alpha"], 3) == alpha, question
    if share is not None:
        strata, weighted = share
        hits = quality["fragen"]["bezug"]["treffer"]
        assert {s: v["treffer"] for s, v in hits["je_schicht"].items()} == strata
        assert round(hits["grundgesamtheit"]["schaetzer"], 3) == weighted


def test_score_recomputes_the_agreement_of_project_12(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/plans/12-kennungen.md § 4.1: Art 600/600, Grenzen 597/597, Normwert 555/597 (α 0,929),
    Rolle 90/98 (0,901), Funktion 89/100 (0,850); vier Entscheide vom Auswerter."""
    target = _copy(tmp_path, monkeypatch, "12-kennungen-f4")
    assert main(["validate", "score", "12-kennungen-f4"]) == 0
    quality = json.loads((target / "guete.json").read_text(encoding="utf-8"))
    expected = {
        "art": (600, 600, 1.0),
        "grenzen": (597, 597, 1.0),
        "norm": (555, 597, 0.929),
        "rolle": (90, 98, 0.901),
        "frist": (89, 100, 0.85),
    }
    for question, (agreed, both, alpha) in expected.items():
        found = quality["fragen"][question]
        assert (found["einig"], found["beide"]) == (agreed, both), question
        assert round(found["krippendorff_alpha"], 3) == alpha, question
    assert quality["schlichtung_herkunft"] == {
        "Auswerter nach den Regeln des Schlichters, Runde 1": 4
    }


def test_score_recomputes_the_agreement_of_project_15(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/plans/15-funktion.md § 4.1: funktion 149/150 (α 0,992), urheber 150/150 (1,000),
    adressat 148/150 (0,970)."""
    target = _copy(tmp_path, monkeypatch, "15-funktion-f4")
    assert main(["validate", "score", "15-funktion-f4"]) == 0
    questions = json.loads((target / "guete.json").read_text(encoding="utf-8"))["fragen"]
    expected = {"funktion": (149, 0.992), "urheber": (150, 1.0), "adressat": (148, 0.97)}
    for question, (agreed, alpha) in expected.items():
        assert questions[question]["einig"] == agreed, question
        assert round(questions[question]["krippendorff_alpha"], 3) == alpha, question


def test_score_recomputes_the_agreement_of_project_17(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/plans/17-zeit.md § 4.1: thema 96/100, α 0,957 mit der Menge als einem Wert; ebene
    96/100, α 0,928."""
    target = _copy(tmp_path, monkeypatch, "17-zeit-f4")
    assert main(["validate", "score", "17-zeit-f4"]) == 0
    questions = json.loads((target / "guete.json").read_text(encoding="utf-8"))["fragen"]
    for question, alpha in (("thema", 0.957), ("ebene", 0.928)):
        assert questions[question]["einig"] == 96, question
        assert round(questions[question]["krippendorff_alpha"], 3) == alpha, question
