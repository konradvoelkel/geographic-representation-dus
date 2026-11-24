"""Vorhaben 18: ``georep pack --neighbors`` und die Rückrichtung in ``bootstrap``.

Der Rundgang ist die stärkste Zusicherung: die Nachbartabelle aus den Dokumentvektoren packen, in
eine frische Datenwurzel ohne Vektoren bootstrappen, und ``neighbors`` liefert dort dieselbe
Tabelle aus dem Paket. Dazu die Abbrüche: eine Tabelle, die selbst aus einem Paket kam, ein
Teillauf, fremde IDs, ein Ziel in der Datenwurzel.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl
import pytest

from georep.bootstrap import BootstrapReport, overlay_neighbors
from georep.enrich.embeddings import embedding_files, model_steps
from georep.io import write_parquet
from georep.layout import Layout
from georep.pack import NEIGHBORS_NAME, PackError, pack_neighbors
from georep.pipeline import run_pipeline
from georep.records import PaperRecord
from georep.search.vectors import NEIGHBORS_SCHEMA, NEIGHBORS_SCHEMA_VERSION
from georep.settings import Embeddings, Settings
from georep.stores import PaperStore, RawTextStore, stored_schema_version
from tests.fakes import FakeEmbedder

TEXTS = {
    "f1.pdf": "Radweg an der Schule\nZweite Zeile",
    "f2.pdf": "Baumfällungen im Park",
    "f3.pdf": "Kita und Ganztag",
    "f4.pdf": "Haushalt der Stadt",
}
PAPERS = [("id1", "Radweg", "f1.pdf"), ("id2", "Bäume", "f2.pdf"), ("id3", "Kita", "f3.pdf")]
PAPERS += [("id4", "Haushalt", "f4.pdf")]


@pytest.fixture
def settings(default_settings: Settings) -> Settings:
    small = Embeddings(enabled=True, chunk_chars=60, title_chars=10, overlap_chars=5, neighbors=2)
    return default_settings.model_copy(update={"embeddings": small})


def _root(tmp_path: Path, name: str) -> Layout:
    layout = Layout(tmp_path / name / "data", tmp_path / name / "cache", tmp_path / "reference")
    layout.ensure_dirs()
    PaperStore(layout.papers).save(
        [
            PaperRecord(id=i, name=n, file_name=f, download_url=f"https://ris.test/{f}")
            for i, n, f in PAPERS
        ]
    )
    pl.DataFrame(PAPERS, schema=["id", "name", "file_name"], orient="row").write_parquet(
        layout.corpus
    )
    return layout


@pytest.fixture
def layout(tmp_path: Path, settings: Settings) -> Layout:
    """Eine Datenwurzel mit Rohtext, in der ``embeddings`` und ``neighbors`` gelaufen sind."""
    layout = _root(tmp_path, "lauf")
    store = RawTextStore(layout.raw_texts)
    for name, text in TEXTS.items():
        store.put(name, text, pages=1, extractor="probe+roh", pdf_sha256="0")
    store.save()
    outcomes = run_pipeline(model_steps(settings, layout, FakeEmbedder()), settings, models=True)
    assert {o.status for o in outcomes} == {"ausgeführt"}
    return layout


TODAY = dt.date(2026, 11, 24)


def test_the_package_is_the_table_with_its_model_in_the_readme(
    tmp_path: Path, layout: Layout, settings: Settings
) -> None:
    target = tmp_path / "paket"
    report = pack_neighbors(layout, settings, target, today=TODAY)
    packed = target / NEIGHBORS_NAME
    assert [f.name for f in report.files] == [NEIGHBORS_NAME]
    assert stored_schema_version(packed) == str(NEIGHBORS_SCHEMA_VERSION)
    table = pl.read_parquet(embedding_files(layout).neighbors)
    assert pl.read_parquet(packed).equals(table)
    assert dict(report.figures) == {"Zeilen": 8, "Korpus-IDs": 4, "Nachbarn je ID": 2}
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "pack --neighbors" in readme and report.files[0].sha256 in readme
    for value in ("fake-embed:latest", "e" * 64, "18-stuecke-1+"):
        assert value in readme
    # ohne --force bleibt ein vorhandenes Paket stehen
    assert pack_neighbors(layout, settings, target).skipped == (NEIGHBORS_NAME,)


def test_the_package_bootstraps_into_a_root_without_vectors_and_gives_the_same_table(
    tmp_path: Path, layout: Layout, settings: Settings
) -> None:
    target = tmp_path / "paket"
    pack_neighbors(layout, settings, target)
    fresh = _root(tmp_path, "pages")
    report = BootstrapReport()
    overlay_neighbors(fresh, target / NEIGHBORS_NAME, report, force=False)
    assert report.copied == [embedding_files(fresh).package.name] and not report.neighbors_refused
    steps = model_steps(settings, fresh, FakeEmbedder())
    outcomes = run_pipeline(steps, settings)  # ohne --models: keine Vektoren
    assert [o.status for o in outcomes] == ["übersprungen", "ausgeführt"]
    assert "aus dem Paket" in outcomes[1].reason
    again = pl.read_parquet(embedding_files(fresh).neighbors)
    assert again.equals(pl.read_parquet(embedding_files(layout).neighbors))


def test_bootstrap_refuses_a_package_of_another_dataset_or_version(
    tmp_path: Path, layout: Layout, settings: Settings
) -> None:
    fresh = _root(tmp_path, "fremd")
    foreign = tmp_path / "fremd.parquet"
    rows = {"id": ["id1"], "rang": [1], "nachbar": ["idX"], "aehnlichkeit": [0.5]}
    write_parquet(
        pl.DataFrame(rows, schema=NEIGHBORS_SCHEMA),
        foreign,
        schema_version=NEIGHBORS_SCHEMA_VERSION,
    )
    report = BootstrapReport()
    overlay_neighbors(fresh, foreign, report, force=False)
    assert "1 von 2 IDs" in report.neighbors_refused and report.copied == []
    assert report.neighbors_refused in report.summary()
    old = tmp_path / "alt.parquet"
    rows["nachbar"] = ["id2"]
    write_parquet(pl.DataFrame(rows, schema=NEIGHBORS_SCHEMA), old, schema_version=99)
    report = BootstrapReport()
    overlay_neighbors(fresh, old, report, force=False)
    assert "Schema-Version 99" in report.neighbors_refused
    report = BootstrapReport()
    overlay_neighbors(fresh, tmp_path / "fehlt.parquet", report, force=False)
    assert report.missing == ["fehlt.parquet"]


def test_pack_refuses_a_table_that_came_from_a_package(
    tmp_path: Path, layout: Layout, settings: Settings
) -> None:
    target = tmp_path / "paket"
    pack_neighbors(layout, settings, target)
    files = embedding_files(layout)
    files.documents.unlink()  # ohne Vektoren nimmt neighbors die Kopie des Pakets
    write_parquet(
        pl.read_parquet(target / NEIGHBORS_NAME),
        files.package,
        schema_version=NEIGHBORS_SCHEMA_VERSION,
    )
    run_pipeline(model_steps(settings, layout, FakeEmbedder()), settings)
    with pytest.raises(PackError, match="fehlt"):
        pack_neighbors(layout, settings, tmp_path / "zweites", force=True)


def test_pack_refuses_neighbors_that_are_not_from_the_vectors_beside_them(
    tmp_path: Path, layout: Layout, settings: Settings
) -> None:
    files = embedding_files(layout)
    stamp = files.neighbors.with_name(files.neighbors.name + ".stamp.json")
    recorded = json.loads(stamp.read_text(encoding="utf-8"))
    recorded["inputs"][files.documents.name] = "0" * 64
    stamp.write_text(json.dumps(recorded), encoding="utf-8")
    with pytest.raises(PackError, match="nicht aus den Dokumentvektoren"):
        pack_neighbors(layout, settings, tmp_path / "paket")


def test_pack_refuses_a_partial_run_foreign_ids_and_a_target_inside(
    tmp_path: Path, layout: Layout, settings: Settings
) -> None:
    with pytest.raises(PackError, match="data_root"):
        pack_neighbors(layout, settings, layout.data_root / "paket")
    stamp = embedding_files(layout).chunks.with_name("einbettungen_stuecke.parquet.stamp.json")
    recorded = json.loads(stamp.read_text(encoding="utf-8"))
    recorded["models"]["open"] = 3
    stamp.write_text(json.dumps(recorded), encoding="utf-8")
    with pytest.raises(PackError, match="3 Eingaben offen"):
        pack_neighbors(layout, settings, tmp_path / "paket")
    recorded["models"]["open"] = 0
    stamp.write_text(json.dumps(recorded), encoding="utf-8")
    PaperStore(layout.papers).save([PaperRecord(id="id1"), PaperRecord(id="id2")])
    with pytest.raises(PackError, match="kein Paper"):
        pack_neighbors(layout, settings, tmp_path / "paket")


def test_the_command_packs_with_the_switch(
    tmp_path: Path,
    layout: Layout,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from georep import cli

    monkeypatch.setattr(cli, "load_settings", lambda **_: settings)
    monkeypatch.setattr(Layout, "from_settings", staticmethod(lambda _: layout))
    assert cli.main(["pack", "--neighbors", str(tmp_path / "paket")]) == 0
    out = capsys.readouterr().out
    assert "8 Zeilen, 4 Korpus-IDs, 2 Nachbarn je ID" in out
    assert NEIGHBORS_NAME in out
