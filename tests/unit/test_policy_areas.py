"""Vorhaben 19 (Politikfelder nach dem CAP, Weg 3b): Eingabe des Klassifikators, Paket, Beitrag.

Messdokument ``docs/plans/19-politikfelder.md``, § 6 und § 10. Der Klassifikator läuft außerhalb des
Pakets; hier wird geprüft, was das Paket selbst tut: die Eingabe schreiben, bytegleich zu
``schreibe_eingabe()`` des Messskripts, mit der gemessen und trainiert wurde.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import polars as pl
import pytest

from georep.cli import main
from georep.enrich.policy_areas import (
    AREAS_SCHEMA,
    CODES,
    INPUT_SCHEMA,
    NAMES,
    SOURCE,
    check_areas,
    classifier_input,
)
from georep.errors import SchemaError
from georep.layout import Layout
from georep.pack import PackError, pack_policy_areas
from georep.settings import PolicyAreas, load_settings
from georep.validation.codebook import load_codebook

REPO = Path(__file__).resolve().parents[2]
NOWHERE = Path("/nonexistent")

# Titel und Rohtexte mit allem, worin sich Leerraum-Regeln unterscheiden: NBSP und schmales NBSP,
# Seitenumbruch, Zeilentrenner U+2028, die Trenner U+001C bis U+001F (für Python Leerraum, für
# Polars nicht), Leerraum genau an der Grenze von 1 500 Zeichen, ein Text nur aus Leerraum, eine
# Datei, die der Store nicht kennt, und ein Dokument ohne Datei.
LONG = "Beschluss" + " x" * 745 + " Ende am Rand" + " weiter" * 30
CORPUS = pl.DataFrame(
    {
        "id": ["https://oparl.example/paper/4", "https://oparl.example/paper/1",
               "https://oparl.example/paper/3", "https://oparl.example/paper/2",
               "https://oparl.example/paper/5", "https://oparl.example/paper/6"],
        "name": ["Antrag Busspur  an der  Allee", "Anfrage zur Kita\n(Nachfrage)", None,
                 "Mitteilung zum Haushalt", "Bauantrag", "Eingabe ohne Datei"],
        "file_name": ["a.pdf", "b.pdf", "c.pdf", "d.pdf", "e.pdf", None],
        "text": ["antrag", "anfrage", "", "mitteilung", "bauantrag", "eingabe"],
    }
)  # fmt: skip
RAW = pl.DataFrame(
    {
        "name": ["a.pdf", "b.pdf", "c.pdf", "d.pdf"],
        "text": [
            "Der Rat möge beschließen:\f\n\nBusspur\x1cprüfen\t und  umsetzen.",
            LONG,
            "  \n\f  ",
            "Seite 1\x1d\x1e\x1fSeite 2" + " " * 3,
        ],
    }
)


def _measurement() -> ModuleType:
    """Das Messskript von 19 als Modul; es liest beim Import nichts."""
    path = REPO / "docs" / "plans" / "19-politikfelder-messung.py"
    spec = importlib.util.spec_from_file_location("messung_19", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["messung_19"] = module
    spec.loader.exec_module(module)
    return module


def _layout(tmp_path: Path) -> Layout:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    for frame, path in ((CORPUS, layout.corpus), (RAW, layout.raw_texts)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(path)
    return layout


def test_the_input_is_byte_equal_to_the_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§ 10, Punkt 3: die Eingabe ist bytegleich zu ``schreibe_eingabe()`` (Titel und 1 500 Zeichen)."""
    layout = _layout(tmp_path)
    script = _measurement()
    ids = CORPUS.get_column("id").to_list()
    out = tmp_path / "messdaten"
    out.mkdir()
    pl.DataFrame({"id": ids[:4]}).write_csv(tmp_path / "test.csv")
    pl.DataFrame({"id": ids[4:]}).write_csv(tmp_path / "entwicklung.csv")
    for name, value in (
        ("AUSGABE", out),
        ("STICHPROBE", tmp_path / "test.csv"),
        ("ENTWICKLUNG", tmp_path / "entwicklung.csv"),
        ("SILBER", tmp_path / "keine-silbermenge.csv"),
        ("ROHTEXT", layout.raw_texts),
    ):
        monkeypatch.setattr(script, name, value)
    script.schreibe_eingabe(layout)
    measured = dict(pl.read_parquet(out / "ratsdokumente.parquet").select("id", "text").iter_rows())

    frame = classifier_input(CORPUS, RAW, PolicyAreas().chars)

    assert PolicyAreas().chars == script.WEG3_ZEICHEN == 1500
    assert dict(frame.select("id", "text").iter_rows()) == measured
    assert {i: t.encode() for i, t in frame.select("id", "text").iter_rows()} == {
        i: t.encode() for i, t in measured.items()
    }


def test_one_row_per_document_with_text_and_cut_flags() -> None:
    frame = classifier_input(CORPUS, RAW, 1500)
    assert dict(frame.schema) == INPUT_SCHEMA
    assert frame.get_column("id").to_list() == sorted(CORPUS.get_column("id").to_list())
    rows = {r["id"].rsplit("/", 1)[1]: r for r in frame.iter_rows(named=True)}
    assert rows["4"]["text"] == (
        "Antrag Busspur an der Allee Der Rat möge beschließen: Busspur prüfen und umsetzen."
    )
    assert rows["3"] == {"id": rows["3"]["id"], "text": "", "mit_text": False, "gekuerzt": False}
    assert rows["5"]["text"] == "Bauantrag" and not rows["5"]["mit_text"]  # Datei ohne Rohtext
    assert rows["6"]["text"] == "Eingabe ohne Datei" and not rows["6"]["mit_text"]
    assert rows["1"]["gekuerzt"] and rows["1"]["mit_text"] and "Ende" not in rows["1"]["text"]
    assert not rows["4"]["gekuerzt"]


def test_export_command_writes_the_input_of_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\ncache_root = "{tmp_path / "cache"}"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    settings = load_settings(cwd=tmp_path, profile="moenchengladbach")
    layout = Layout.from_settings(settings)
    for frame, path in ((CORPUS, layout.corpus), (RAW, layout.raw_texts)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(path)
    target = tmp_path / "eingabe.parquet"

    assert main(["policy-areas", "export", "moenchengladbach", "--out", str(target)]) == 0

    assert pl.read_parquet(target).equals(classifier_input(CORPUS, RAW, 1500))
    assert "6 Dokumente, 3 mit Rohtext, davon 1 länger als 1500 Zeichen" in capsys.readouterr().out
    # ohne --out neben die Messdateien des Profils
    assert main(["policy-areas", "export", "moenchengladbach"]) == 0
    assert (layout.root / "messung" / "19-politikfelder-eingabe.parquet").is_file()
    # --profile darf nur dasselbe Profil sagen
    assert main(["--profile", "duesseldorf", "policy-areas", "export", "moenchengladbach"]) == 2


def test_export_names_the_missing_raw_text_store(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\ncache_root = "{tmp_path / "cache"}"\n',
        encoding="utf-8",
    )
    layout = Layout.from_settings(load_settings(cwd=tmp_path, profile="duesseldorf"))
    layout.corpus.parent.mkdir(parents=True, exist_ok=True)
    CORPUS.write_parquet(layout.corpus)
    assert main(["--settings", str(tmp_path / "settings.toml"), "policy-areas", "export",
                 "duesseldorf"]) == 1  # fmt: skip


def test_the_settings_block_is_off_and_outside_the_fingerprint() -> None:
    settings = load_settings(cwd=NOWHERE, profile="duesseldorf-2014")
    assert PolicyAreas().enabled is False and PolicyAreas().package is None
    changed = settings.model_copy(
        update={"policy_areas": settings.policy_areas.model_copy(update={"chars": 99})}
    )
    assert changed.fingerprint() == settings.fingerprint()
    assert settings.policy_areas.model_id == "xlm-roberta-large@80ca2a82"
    with pytest.raises(ValueError, match="weights_sha256"):
        PolicyAreas(enabled=True)
    with pytest.raises(ValueError, match="Hexziffern"):
        PolicyAreas(weights_sha256="80ca2a82")


# --- Das Paket (georep pack --policy-areas) ---------------------------------------------------------
MODEL = PolicyAreas(weights_sha256="80ca2a82" + "0" * 56).model_id
IDS = sorted(CORPUS.get_column("id").to_list())


def _areas(ids: list[str] = IDS, model: str = MODEL) -> pl.DataFrame:
    """Eine gültige Vorhersage: das letzte Dokument ohne Rohtext, die übrigen mit Feld."""
    filled = [i != ids[-1] for i in ids]
    return pl.DataFrame(
        {
            "id": ids,
            "politikfeld": [CODES[n % len(CODES)] if f else "" for n, f in enumerate(filled)],
            "quelle": [SOURCE if f else "" for f in filled],
            "modell": [model if f else "" for f in filled],
            "prompt": ["" for _ in ids],
            "wahrscheinlichkeit": [0.5 + n / 100.0 + 0.00049 if f else None
                                   for n, f in enumerate(filled)],
            "abgeschnitten": [n % 2 == 0 if f else None for n, f in enumerate(filled)],
        },
        schema=AREAS_SCHEMA,
    )  # fmt: skip


def test_the_names_are_the_options_of_the_codebook() -> None:
    codebook = load_codebook(REPO / "validierung" / "19-politikfelder" / "codebuch.toml",
                             "19-politikfelder")  # fmt: skip
    question = next(q for q in codebook.questions if q.id == "politikfeld")
    assert {o.value: o.name for o in question.options} == NAMES
    assert tuple(NAMES) == CODES


def test_a_valid_package_passes_and_comes_back_sorted() -> None:
    shuffled = _areas().sample(fraction=1.0, shuffle=True, seed=1)
    assert check_areas(shuffled, IDS, MODEL).equals(_areas())


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda f: f.drop("abgeschnitten"), "Spalten"),
        (lambda f: pl.concat([f, f.head(1)]), "doppelt"),
        (lambda f: f.tail(-1), "es fehlen 1"),
        (lambda f: f.with_columns(pl.col("id").str.replace("/6$", "/7")), "fremd sind 1"),
        (lambda f: f.with_columns(pl.lit("11").alias("politikfeld")), "fremde Codes"),
        (lambda f: f.with_columns(pl.lit("llm").alias("quelle")), "Quelle oder Kennung"),
        (lambda f: f.with_columns(pl.lit("xlm-roberta-large@00000000").alias("modell")),
         "Quelle oder Kennung"),
        (lambda f: f.with_columns(pl.lit(0.0).alias("wahrscheinlichkeit")), "halb leer"),
        (lambda f: f.with_columns(pl.lit(False).alias("abgeschnitten")), "halb leer"),
    ],
)  # fmt: skip
def test_a_wrong_package_is_a_schema_error(change: object, message: str) -> None:
    frame = change(_areas())  # type: ignore[operator]
    with pytest.raises(SchemaError, match=message):
        check_areas(frame, IDS, MODEL)


def _pack_layout(tmp_path: Path) -> tuple[Layout, object]:
    settings = load_settings(cwd=NOWHERE, profile="duesseldorf").model_copy(
        update={"policy_areas": PolicyAreas(weights_sha256="80ca2a82" + "0" * 56)}
    )
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    layout.corpus.parent.mkdir(parents=True, exist_ok=True)
    CORPUS.write_parquet(layout.corpus)
    return layout, settings


def test_pack_freezes_the_prediction_with_a_complete_readme(tmp_path: Path) -> None:
    layout, settings = _pack_layout(tmp_path)
    source = tmp_path / "politikfelder.parquet"
    _areas().write_parquet(source)
    target = tmp_path / "snapshots" / "duesseldorf-politikfelder"

    report = pack_policy_areas(layout, settings, target, source=source)  # type: ignore[arg-type]

    packed = pl.read_parquet(target / "processed" / "politikfelder.parquet")
    assert packed.drop("wahrscheinlichkeit").equals(_areas().drop("wahrscheinlichkeit"))
    assert packed.get_column("wahrscheinlichkeit").to_list()[:2] == [0.5, 0.51]  # drei Stellen
    assert dict(report.figures) == {"Dokumente": 6, "mit Politikfeld": 5, "ohne Rohtext": 1,
                                    "abgeschnitten": 3}  # fmt: skip
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert report.files[0].sha256 in readme and "CC BY-NC-SA 4.0" in readme
    assert "80ca2a82" + "0" * 56 in readme and MODEL in readme
    assert "[…]" not in readme and "nachzutragen" not in readme  # kein Gerüst, fertig
    assert "Comparative Agendas Project" in readme and "Breunig" in readme
    assert "Dieses Paket ist das des geprüften Datensatzes" in readme
    # ein vorhandenes Paket bleibt ohne --force, wie bei den übrigen
    again = pack_policy_areas(layout, settings, target, source=source)  # type: ignore[arg-type]
    assert again.skipped == ("processed/politikfelder.parquet",) and not again.readme_written


def test_pack_refuses_a_prediction_of_another_corpus(tmp_path: Path) -> None:
    layout, settings = _pack_layout(tmp_path)
    source = tmp_path / "politikfelder.parquet"
    _areas(IDS[:-1]).write_parquet(source)
    with pytest.raises(PackError, match="es fehlen 1"):
        pack_policy_areas(layout, settings, tmp_path / "ziel", source=source)  # type: ignore[arg-type]
    assert not (tmp_path / "ziel" / "processed").exists()


def test_pack_command_wants_policy_areas_and_from_together(tmp_path: Path) -> None:
    assert main(["pack", "--policy-areas", str(tmp_path / "ziel")]) == 2
    assert main(["pack", "--from", "x.parquet", str(tmp_path / "ziel")]) == 2
