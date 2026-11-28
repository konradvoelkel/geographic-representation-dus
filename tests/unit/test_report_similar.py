"""Ähnliche Dokumente im Dokumentdialog und als Download (Vorhaben 18, Stufe 3, ``report/similar.py``).

Geprüft werden die Zeilen des Hakens (fünf je Dokument nach Rang, die Ziele außerhalb von
``dokumente.json`` mit Link, Datum, Drucksache und Titel), wo er erscheint (nur gemessen, mit
Nachbarpaket und mit Zeilen), der Satz aus ``guete.json`` mit der Präzision@5 nur bei genügendem
α, das Modell mit Lizenz und Quelle, die Zahl der Präzision gegen Labels und Paket im Repo, der
Download nur als Parquet mit Spaltendoku und die Liste im Skript des Rahmens.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.enrich import CONTRIBUTIONS, Contribution
from georep.enrich.embeddings import embedding_files
from georep.errors import SchemaError
from georep.io import write_parquet
from georep.layout import Layout
from georep.report.build import DOCUMENTS_NAME, write_dialogs
from georep.report.dialog import dialog_names, dialog_payload
from georep.report.model import ReportModel
from georep.report.render import environment
from georep.report.similar import (
    ANCHORS,
    DIALOG_NAME,
    HIT_LABELS,
    IN_DIALOG,
    MEASURED_MODEL,
    MODEL_LICENSE,
    MODEL_SOURCE,
    NEIGHBORS_CHECK,
    QUESTION,
    TABLE_NAME,
    dialog_rows,
    dialog_shown,
    similar_enabled,
    similar_sentence,
    table_shown,
)
from georep.report.tables import published
from georep.search.vectors import NEIGHBORS_SCHEMA, NEIGHBORS_SCHEMA_VERSION
from georep.settings import Settings, load_settings
from tests.conftest import REPO

NOWHERE = Path("/nonexistent")
PROJECT = NEIGHBORS_CHECK.project
PACKAGE = REPO / "snapshots" / "duesseldorf-aehnlich" / "raw" / "aehnliche_dokumente_paket.parquet"


def _quality() -> dict[str, Any]:
    path = REPO / "validierung" / PROJECT / "guete.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _with_validation(settings: Settings, root: Path) -> Settings:
    return settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": root})}
    )


def _corpus(n: int) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [f"d{i:02d}" for i in range(n)],
            "name": [f"Titel {i}" for i in range(n)],
            "reference": [f"X/{i:03d}/2021" for i in range(n)],
            "date": [dt.date(2021, 1, 1) + dt.timedelta(days=i) for i in range(n)],
            "download_url": [f"http://ris.example/files/{i:05d}.pdf" for i in range(n)],
        }
    )


def _neighbors(ids: list[str], k: int = 10) -> pl.DataFrame:
    """Je ID die ``k`` folgenden im Kreis, Rang 1 zuerst, mit fallender Ähnlichkeit."""
    rows = [
        (doc_id, rang, ids[(i + rang) % len(ids)], 1.0 - rang / 100)
        for i, doc_id in enumerate(ids)
        for rang in range(1, k + 1)
    ]
    return pl.DataFrame(rows, schema=NEIGHBORS_SCHEMA, orient="row")


def _layout(
    tmp_path: Path, settings: Settings, corpus: pl.DataFrame, table: pl.DataFrame
) -> Layout:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference", settings.profile)
    layout.corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus.write_parquet(layout.corpus)
    path = embedding_files(layout).neighbors
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(table, path, schema_version=NEIGHBORS_SCHEMA_VERSION)
    return layout


# --- Die Zeilen des Hakens ---------------------------------------------------------------------
def test_im_dialog_die_ersten_fuenf_nach_rang(tmp_path: Path, default_settings: Settings) -> None:
    corpus = _corpus(12)
    ids = corpus.get_column("id").to_list()
    layout = _layout(tmp_path, default_settings, corpus, _neighbors(ids))
    rows = dialog_rows(layout, default_settings)
    assert rows.labels == ("",)
    assert rows.rows["d00"] == tuple((0, f"d{r:02d}") for r in range(1, IN_DIALOG + 1))
    assert all(len(entries) == IN_DIALOG for entries in rows.rows.values())
    assert set(rows.rows) == set(ids)
    target = rows.targets["d03"]
    # wie dokumente.json: https, Datum, Drucksache, der Titel des Korpus
    assert target.link == "https://ris.example/files/00003.pdf"
    assert (target.date, target.reference, target.title) == (
        dt.date(2021, 1, 4),
        "X/003/2021",
        "Titel 3",
    )
    assert "nicht von Menschen" in rows.note


def test_die_datei_zeigt_eigene_ziele_als_liste_mit_drucksache_datum_titel(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Ein Ziel außerhalb von ``dokumente.json`` steht mit Link, Datum, Drucksache, Titel in der Datei."""
    corpus = _corpus(12)
    ids = corpus.get_column("id").to_list()
    layout = _layout(tmp_path, default_settings, corpus, _neighbors(ids))
    hook = next(h for c in CONTRIBUTIONS for h in c.dialogs if h.name == DIALOG_NAME)
    order = ids[:3]  # nur drei stehen im Dialog
    payload = dialog_payload(
        hook.rows(layout, default_settings),
        order,
        "https://ris.example/files/",
        title=hook.title,
        version="0",
        generated_at=dt.datetime(2026, 11, 28, tzinfo=dt.UTC),
        show=hook.show,
        listed=hook.listed,
    )
    assert payload["list"] is True and payload["show"] == [2, 1, 3]
    assert payload["title"] == "Ähnliche Dokumente"
    rows = payload["rows"]
    assert isinstance(rows, dict) and set(rows) == {"0", "1", "2"}
    # d00 zeigt auf d01 und d02 im Dialog, dann auf drei eigene Ziele
    assert rows["0"] == [1, 2, -1, -2, -3]
    documents = payload["documents"]
    assert isinstance(documents, list)
    assert documents[0] == ["00003.pdf", "2021-01-04", "X/003/2021", "Titel 3"]


def test_eine_leere_tabelle_zeigt_nichts(
    tmp_path: Path, default_settings: Settings, mini_run: Layout
) -> None:
    """Ohne Paketkopie schreibt ``neighbors`` eine leere Tabelle: kein Haken, kein Download."""
    layout = _layout(tmp_path, default_settings, _corpus(3), pl.DataFrame(schema=NEIGHBORS_SCHEMA))
    assert similar_enabled(default_settings)
    assert not dialog_shown(layout, default_settings)
    assert not table_shown(embedding_files(layout).neighbors, default_settings)
    assert DIALOG_NAME not in dialog_names(default_settings, layout)
    # die Mini-Kette hat kein Paket ihrer IDs, ihr Dialog lädt die Vorgänge und die Beschlüsse
    details = mini_run.site_details.read_text(encoding="utf-8")
    assert 'data-extras="vorgaenge beschluesse"' in details
    assert not (mini_run.site_data / f"{DIALOG_NAME}.json").exists()
    assert TABLE_NAME not in {t.name for t in published(mini_run, default_settings)}


@pytest.mark.parametrize(
    ("profile", "shown"),
    [
        ("duesseldorf", True),
        ("duesseldorf-2014", False),
        ("duesseldorf-2025", False),
        ("duesseldorf-vergleich", True),  # rechnet im Ordner der Hauptperiode
        ("moenchengladbach", False),
    ],
)
def test_nur_gemessen_und_mit_paket(tmp_path: Path, profile: str, shown: bool) -> None:
    """Frage 9.10 und plan-zeigen § 6: Nachbarn gibt es auf der Seite nur in der Hauptperiode."""
    settings = load_settings(profile=profile, cwd=NOWHERE)
    corpus = _corpus(12)
    layout = _layout(tmp_path, settings, corpus, _neighbors(corpus.get_column("id").to_list()))
    on = similar_enabled(settings) and dialog_shown(layout, settings)
    assert on is shown
    assert (DIALOG_NAME in dialog_names(settings, layout)) is shown
    assert (TABLE_NAME in {t.name for t in published(layout, settings)}) is shown


# --- Der Satz ----------------------------------------------------------------------------------
def test_der_satz_kommt_aus_guete_json(default_settings: Settings) -> None:
    note = similar_sentence(default_settings, dialog=True)
    quality = _quality()
    assert note.startswith("Ähnliche Dokumente: ")
    assert quality["satz"] in note and "geschlichtet von demselben Modell" in note
    # Präzision@5 mit Intervall nach Wilson, n und Anker
    assert "0,832" in note and "0,781–0,873" in note
    assert "208 von 250" in note and f"{ANCHORS} Dokumenten" in note
    assert MEASURED_MODEL in note and MODEL_LICENSE in note and MODEL_SOURCE in note
    # nur die Hauptperiode ist geprüft (Frage 9.10)
    assert f"{default_settings.city.name}, {default_settings.period.title}" in note
    assert "nur" in note.split(default_settings.city.name)[0].rsplit(".", 1)[-1]
    table = similar_sentence(default_settings, dialog=False)
    assert table[0].isupper() and quality["satz"] in table and "0,832" in table
    assert "zehn" in table and "fünf" in table


def test_ohne_genuegendes_alpha_keine_praezision(
    tmp_path: Path, default_settings: Settings
) -> None:
    shutil.copytree(REPO / "validierung" / PROJECT, tmp_path / PROJECT)
    quality = _quality()
    quality["fragen"][QUESTION]["alpha_genuegt"] = False
    (tmp_path / PROJECT / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    note = similar_sentence(_with_validation(default_settings, tmp_path), dialog=True)
    assert "0,832" not in note and "Präzision" not in note
    assert quality["satz"][1:] in note and MEASURED_MODEL in note  # groß am Satzanfang


def test_ein_geaenderter_satz_aendert_den_hinweis(
    tmp_path: Path, default_settings: Settings
) -> None:
    shutil.copytree(REPO / "validierung" / PROJECT, tmp_path / PROJECT)
    quality = _quality() | {"satz": "geprüft von niemandem, nur zum Test"}
    (tmp_path / PROJECT / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    note = similar_sentence(_with_validation(default_settings, tmp_path), dialog=True)
    assert "geprüft von niemandem, nur zum Test" in note


def test_eine_andere_kodierung_bricht_ab(tmp_path: Path, default_settings: Settings) -> None:
    """Die Zahl 208 von 250 gilt nur für dieses Codebuch an diesen 383 Paaren."""
    shutil.copytree(REPO / "validierung" / PROJECT, tmp_path / PROJECT)
    quality = _quality() | {"codebuch_version": "2027-01-01.1"}
    (tmp_path / PROJECT / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    with pytest.raises(SchemaError, match="Codebuch"):
        similar_sentence(_with_validation(default_settings, tmp_path), dialog=True)


def test_die_praezision_folgt_aus_labels_und_paket() -> None:
    """Die Zahl im Satz, nachgerechnet wie im Messskript (``--auswertung``): Rang 1 bis 5 der
    Anker im Nachbarpaket gegen die Endlabels; ein Treffer ist dieselbe Sache oder dasselbe Thema."""
    sample = pl.read_csv(
        REPO / "validierung" / PROJECT / "stichprobe.csv", infer_schema_length=0
    ).select("id", "id_a", "id_b")
    labels = pl.read_csv(REPO / "validierung" / PROJECT / "labels.csv", infer_schema_length=0)
    labels = labels.filter(pl.col("frage") == QUESTION).select("id", "label")
    anchors = sample.get_column("id_a").unique().to_list()
    top = (
        pl.read_parquet(PACKAGE)
        .filter(pl.col("id").is_in(anchors) & (pl.col("rang") <= 5))
        .select(pl.col("id").alias("id_a"), pl.col("nachbar").alias("id_b"))
    )
    judged = top.join(sample, on=["id_a", "id_b"], how="inner").join(labels, on="id", how="inner")
    (measure,) = NEIGHBORS_CHECK.measures
    assert len(anchors) == ANCHORS and top.height == judged.height == measure.units
    assert judged.filter(pl.col("label").is_in(list(HIT_LABELS))).height == measure.hits
    quality = _quality()
    assert (quality["codebuch_version"], quality["einheiten"]) == (
        NEIGHBORS_CHECK.codebook_version,
        NEIGHBORS_CHECK.units,
    )


def test_das_gemessene_modell_ist_die_vorgabe(default_settings: Settings) -> None:
    """Der Satz nennt das Modell der Messung; wer ``[ml.embedding].model`` ändert, misst neu."""
    assert default_settings.ml.embedding.model == MEASURED_MODEL
    assert MODEL_SOURCE.endswith(f"/{MEASURED_MODEL}")


# --- Der Download ------------------------------------------------------------------------------
def test_der_download_nur_als_parquet_mit_spaltendoku(default_settings: Settings) -> None:
    table = next(t for c in CONTRIBUTIONS for t in c.tables if t.name == TABLE_NAME)
    assert table.csv is None  # zehn je Dokument, Rückstand 35
    assert set(table.columns) == set(NEIGHBORS_SCHEMA)
    assert table.check is not None
    assert table.check.sentence(default_settings) == similar_sentence(
        default_settings, dialog=False
    )
    root = default_settings.validation.root
    assert root / PROJECT / "guete.json" in table.check.files(default_settings)


def test_der_bericht_schreibt_aehnlich_json_neben_dokumente_json(
    mini_run: Layout,
    mini_model: ReportModel,
    default_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mit einer Nachbartabelle der Mini-IDs: je Dokument des Dialogs fünf Einträge, Satz dabei.

    Nur der Haken von 18 im Register: die übrigen lesen Dateien, die diese Wurzel nicht hat."""
    import georep.enrich
    from georep.enrich.embeddings import DIALOG

    monkeypatch.setattr(
        georep.enrich, "CONTRIBUTIONS", (Contribution("18-einbettungen", dialogs=(DIALOG,)),)
    )
    layout = Layout(
        tmp_path / "data", tmp_path / "cache", mini_run.reference_root, mini_run.profile
    )
    for source, target in (
        (mini_run.corpus, layout.corpus),
        (mini_run.index, layout.index),
        (mini_run.site_data / DOCUMENTS_NAME, layout.site_data / DOCUMENTS_NAME),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    ids = sorted(pl.read_parquet(layout.corpus, columns=["id"]).get_column("id").to_list())
    path = embedding_files(layout).neighbors
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(_neighbors(ids), path, schema_version=NEIGHBORS_SCHEMA_VERSION)
    assert dialog_names(default_settings, layout) == (DIALOG_NAME,)
    downloads = write_dialogs(layout, mini_model, default_settings)
    listed = json.loads((layout.site_data / DOCUMENTS_NAME).read_text(encoding="utf-8"))
    payload = json.loads((layout.site_data / f"{DIALOG_NAME}.json").read_text(encoding="utf-8"))
    assert payload["list"] is True and payload["base"] == listed["base"]
    assert set(payload["rows"]) == {str(i) for i in range(len(listed["documents"]))}
    assert all(len(entries) == IN_DIALOG for entries in payload["rows"].values())
    assert "nicht von Menschen" in payload["note"]
    assert f"{DIALOG_NAME}.json" in {d.name for d in downloads}
    # leer: die Datei fährt nicht mit
    write_parquet(
        pl.DataFrame(schema=NEIGHBORS_SCHEMA), path, schema_version=NEIGHBORS_SCHEMA_VERSION
    )
    assert f"{DIALOG_NAME}.json" not in {
        d.name for d in write_dialogs(layout, mini_model, default_settings)
    }
    assert not (layout.site_data / f"{DIALOG_NAME}.json").exists()


# --- Das Skript des Rahmens --------------------------------------------------------------------
def test_der_haken_zeigt_eine_liste_wenn_die_datei_es_sagt() -> None:
    """Fünf Vorschläge mit Titel wären als eine Zeile ein Absatz unter jedem Dokument: mit ``list``
    stehen sie aufklappbar unter dem Titel, je Vorschlag ein Listenpunkt."""
    hook = environment().get_template("frame/dialog.js.j2").render()
    assert 'x.list && el(div, "details")' in hook
    assert 'el(box, "summary").textContent = x.title' in hook and 'el(list, "li")' in hook
