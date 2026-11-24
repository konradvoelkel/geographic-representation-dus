"""Der Beitrag von Vorhaben 12 im Register: ein Schritt, eine Spannen-Tabelle.

Die Mini-Fixture hat keine PDFs und also keinen Rohtext; die Spannen kommen hier aus einem kleinen
Rohtextstore und einem Korpus, die der Test selbst schreibt.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from georep.enrich.identifiers import identifiers_files, identifiers_steps, raw_text_frame
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.prep.identifiers import ATTR, IDENTIFIERS_SCHEMA_VERSION, METHOD
from georep.settings import Settings
from georep.spans import SPAN_SCHEMA
from georep.stores import RawTextStore
from tests.fakes import FakeSession

HTTP = FakeSession({})  # der Schritt ist offline und fragt nie
HEAD = "Fachbereich: 52 - Sportamt\nBetreff: Turnhalle\n"


def _layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")


def _inputs(layout: Layout, texts: dict[str, str], documents: dict[str, str | None]) -> None:
    layout.raw_texts.parent.mkdir(parents=True, exist_ok=True)
    store = RawTextStore(layout.raw_texts)
    for name, text in texts.items():
        store.put(name, text, pages=1, extractor="pypdf-7.1.0+roh", pdf_sha256="0")
    store.save()
    layout.corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus = pl.DataFrame(
        {"id": list(documents), "file_name": list(documents.values())},
        schema={"id": pl.String(), "file_name": pl.String()},
    )
    write_parquet(corpus, layout.corpus, schema_version=1)


def test_der_schritt_steht_hinter_den_schritten_von_15_und_vor_dem_bericht(
    tmp_path: Path, default_settings: Settings
) -> None:
    step = next(s for s in identifiers_steps(default_settings, _layout(tmp_path), HTTP))
    names = [s.name for s in build_steps(default_settings, _layout(tmp_path))]
    # hinter den Beiträgen, die vor ihm im Register stehen, und irgendwo vor dem Bericht: ein
    # späterer Beitrag darf sich dazwischen hängen (Review N3)
    assert names.index("cosponsors") < names.index("identifiers") < names.index("report")
    assert step.inputs == (_layout(tmp_path).raw_texts, _layout(tmp_path).corpus)
    assert step.outputs == (identifiers_files(_layout(tmp_path)).spans,)
    assert step.schema_version == IDENTIFIERS_SCHEMA_VERSION


def test_der_schalter_entscheidet(tmp_path: Path, default_settings: Settings) -> None:
    off = default_settings.identifiers.model_copy(update={"enabled": False})
    without = default_settings.model_copy(update={"identifiers": off})
    assert identifiers_steps(without, _layout(tmp_path), HTTP) == []
    assert "identifiers" not in [s.name for s in build_steps(without, _layout(tmp_path))]


def test_der_schritt_schreibt_die_spannen_jeder_korpus_id(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    sport = [HEAD] * 3  # drei Kopffelder: „Sportamt" kommt ins Verzeichnis
    texts = {f"{i}.pdf": head + "Das Sportamt zahlt 5.000 Euro." for i, head in enumerate(sport)}
    texts["leer.pdf"] = "Bebauungsplan Nr. 03/017"
    _inputs(layout, texts, {"p0": "0.pdf", "p1": "1.pdf", "p2": "2.pdf", "q": "2.pdf", "x": None})
    (step,) = identifiers_steps(default_settings, layout, HTTP)
    message = step.run()
    spans = pl.read_parquet(identifiers_files(layout).spans)
    assert spans.columns == [*SPAN_SCHEMA, ATTR]
    assert pl.read_parquet_metadata(identifiers_files(layout).spans)["georep.schema_version"] == "1"
    # leer.pdf hat keine Korpus-ID; q teilt die Datei mit p2 und bekommt dieselben Spannen
    assert sorted(set(spans.get_column("id"))) == ["p0", "p1", "p2", "q"]
    sport_name = spans.filter((pl.col("kind") == "amt") & (pl.col(ATTR) == "name"))
    assert set(sport_name.get_column("norm")) == {"52"}
    assert set(spans.get_column("extractor")) == {f"{METHOD}/pypdf-7.1.0+roh"}
    assert message.startswith(f"{spans.height} Spannen in 4 Dokumenten aus 3 Rohtexten: ")
    assert message.endswith("Ämterverzeichnis 1 Namen")


def test_ohne_rohtext_eine_leere_tabelle(tmp_path: Path, default_settings: Settings) -> None:
    """Ein Profil ohne PDFs und ohne Rohtextpaket: der Lauf scheitert nicht (Konflikt 14)."""
    layout = _layout(tmp_path)
    _inputs(layout, {}, {"p": "a.pdf"})
    (step,) = identifiers_steps(default_settings, layout, HTTP)
    assert step.run() == "kein Rohtext: 0 Spannen"
    spans = pl.read_parquet(identifiers_files(layout).spans)
    assert spans.height == 0
    assert spans.columns == [*SPAN_SCHEMA, ATTR]


def test_ein_rohtextstore_mit_alter_version_gilt_als_leer(tmp_path: Path) -> None:
    path = tmp_path / "rohtexte.parquet"
    old = pl.DataFrame({"name": ["a.pdf"], "text": ["5.000 Euro"], "extractor": ["x"]})
    write_parquet(old, path, schema_version=1)
    frame, stale = raw_text_frame(path)
    assert frame.height == 0
    assert stale == "rohtexte.parquet trägt Schema-Version 1, gelesen wird 2"
