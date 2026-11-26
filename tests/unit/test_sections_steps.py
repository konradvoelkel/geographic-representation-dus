"""Der Beitrag von Vorhaben 11 im Register: ein früher Schritt, zwei Dateien.

``sections`` steht vor ``weights`` (Punkt 74), weil Vorhaben 16 die Stelle eines Treffers aus den
Abschnitten rechnet und ``weights`` sie liest. Die Mini-Fixture hat keine PDFs und also keinen
Rohtext: dort schreibt der Schritt je Korpus-ID eine leere Zeile und keine Spanne, ohne zu scheitern
(Messdokument 11, § 10, Punkt 10). Mit Rohtext entstehen Spannen für jede ID, auch für zwei, die
eine Datei teilen.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from georep.bootstrap import bootstrap_from_settings
from georep.contracts import one_row_per_document
from georep.enrich.sections import sections_files, sections_steps
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.structure import HEAD_SCHEMA, STRUCTURE_SCHEMA_VERSION
from georep.settings import Settings
from georep.spans import SPAN_SCHEMA, check_spans
from georep.stores import RawTextStore, stored_schema_version
from tests.fakes import FakeSession

HTTP = FakeSession({})  # der Schritt ist offline und fragt nie

TEXT = """Betrifft: Neubau eines Radwegs

Fachbereich: 66 - Amt für Verkehrsmanagement
Beratungsfolge:
Gremium Sitzungsdatum Beratungsqualität
Rat 09.11.2023 Entscheidung
Beschlussdarstellung:
Der Rat beschließt den Neubau.
Sachdarstellung:
Der Radweg schließt eine Lücke.
"""


def _layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")


def test_the_step_stands_early_right_before_weights(
    tmp_path: Path, default_settings: Settings
) -> None:
    names = [s.name for s in build_steps(default_settings, _layout(tmp_path))]
    assert names.index("body_hits") < names.index("sections") < names.index("weights")
    assert names.index("sections") > names.index("raw_texts")
    assert names.index("sections") > names.index("corpus")


def test_the_switch_decides_whether_the_step_exists(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    off = default_settings.structure.model_copy(update={"enabled": False})
    assert (
        sections_steps(default_settings.model_copy(update={"structure": off}), layout, HTTP) == []
    )
    [step] = sections_steps(default_settings, layout, HTTP)
    files = sections_files(layout)
    assert step.outputs == (files.sections, files.head)
    assert files.sections == layout.processed / "dokumente_abschnitte.parquet"
    assert files.head == layout.processed / "dokumente_kopf.parquet"
    assert {layout.corpus, layout.raw_texts} <= set(step.inputs)
    assert step.schema_version == STRUCTURE_SCHEMA_VERSION


def test_without_raw_text_every_corpus_id_gets_an_empty_row(mini_run: Layout) -> None:
    ids = pl.read_parquet(mini_run.corpus, columns=["id"]).get_column("id").to_list()
    files = sections_files(mini_run)
    head = pl.read_parquet(files.head)
    spans = pl.read_parquet(files.sections)
    assert head.schema == pl.Schema(HEAD_SCHEMA)
    assert one_row_per_document(head, ids)
    assert head.get_column("extractor").null_count() == len(ids)
    assert spans.schema == pl.Schema(SPAN_SCHEMA) and spans.height == 0
    for path in files:
        assert stored_schema_version(path) == str(STRUCTURE_SCHEMA_VERSION)


def test_with_raw_text_each_id_gets_spans_also_when_two_share_a_file(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", mini_root, default_settings.profile)
    bootstrap_from_settings(layout, default_settings)
    steps = build_steps(default_settings, layout)
    run_pipeline(steps, default_settings, ["corpus"])
    corpus = pl.read_parquet(layout.corpus, columns=["id", "file_name"]).sort("id")
    first, second = corpus.get_column("id").to_list()[:2]
    shared = corpus.get_column("file_name").to_list()[0]
    # zwei Korpus-IDs zeigen gleich auf dieselbe Datei (19 108 Paper, 19 093 Dateien in der
    # Hauptperiode, Synergien 2026-11, § 1)
    store = RawTextStore(layout.raw_texts)
    store.put(shared, TEXT, pages=1, extractor="pypdf-7.1.0+roh", pdf_sha256="0" * 64)
    store.save()
    patched = pl.read_parquet(layout.corpus).with_columns(
        pl.when(pl.col("id") == second)
        .then(pl.lit(shared))
        .otherwise(pl.col("file_name"))
        .alias("file_name")
    )
    patched.write_parquet(layout.corpus)
    [outcome] = run_pipeline(steps, default_settings, ["sections"])
    assert outcome.status == "ausgeführt", outcome.line()
    assert "2 mit Rohtext" in outcome.reason
    files = sections_files(layout)
    spans = pl.read_parquet(files.sections)
    head = pl.read_parquet(files.head)
    check_spans(spans, {first: len(TEXT), second: len(TEXT)})
    assert set(spans.get_column("id").to_list()) == {first, second}
    mine = spans.filter(pl.col("id") == first).drop("id")
    assert mine.equals(spans.filter(pl.col("id") == second).drop("id"))
    decided = head.filter(pl.col("beschlussvorschlag")).get_column("id").to_list()
    assert decided == sorted([first, second])
