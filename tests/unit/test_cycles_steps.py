"""Der Beitrag von Vorhaben 17 im Register: vier Schritte, ihre Schalter, Eingaben und Ausgaben.

Die Mini-Fixture läuft mit dem Stadtprofil, das ``cycles`` und ``vocabulary`` einschaltet; ihre 200
Dokumente reichen vom September 2020 bis September 2025, also über die fünf Wahljahre der
Hauptperiode. ``cycle_tests`` und ``feeds`` laufen hier auf eigenen kleinen Ordnern: die Tests über
drei Perioden an synthetischen Daten, die Feeds an Korpus, Wörterbuch und Index der Mini-Fixture.
Die Zahlen der Messung prüft ``tests/golden/test_cycles_numbers.py`` an den echten Perioden.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import polars as pl
import pytest

import georep.enrich
from georep.analysis.cycles import MONTH_SCHEMA, months_match_timeline
from georep.analysis.hits import hits_by_district
from georep.analysis.hypotheses import CONFIRMED, check_hypotheses
from georep.analysis.lexicon import (
    SPAN_KIND,
    VOCABULARY_SCHEMA,
    document_categories,
    load_lexicon,
    vocabulary_spans,
)
from georep.contracts import one_row_per_document
from georep.enrich.cycles import feed_dir, time_files, time_steps
from georep.errors import MissingInputError, SchemaError
from georep.layout import Layout
from georep.pipeline import build_steps, run_step
from georep.prep.raw_texts import flatten
from georep.report.feeds import FEEDS_SCHEMA, atom_problems
from georep.settings import Originators, Settings, load_settings
from georep.spans import SPAN_SCHEMA, check_spans, sort_spans
from tests.fakes import FakeSession
from tests.unit.test_cycles import THREE, _period

HTTP = FakeSession({})  # alle vier Schritte sind offline und fragen nie
NOWHERE = Path("/nonexistent")
LEXICON = load_lexicon("bundespolitik")


def _layout(tmp_path: Path, profile: str = "") -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference", profile)


def test_the_contribution_stands_in_the_register_behind_vorhaben_15() -> None:
    names = [c.name for c in georep.enrich.CONTRIBUTIONS]
    assert "17-zeit" in names and names.index("17-zeit") > names.index("15-funktion")


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("duesseldorf", ["cycles", "vocabulary"]),
        ("duesseldorf-2014", ["cycles", "vocabulary"]),
        ("duesseldorf-2025", ["cycles", "vocabulary", "feeds"]),
        ("duesseldorf-vergleich", ["cycles", "vocabulary", "cycle_tests"]),
        ("moenchengladbach", ["cycles", "vocabulary"]),
    ],
)
def test_each_package_profile_gets_its_steps_in_a_valid_order(
    tmp_path: Path, profile: str, expected: list[str]
) -> None:
    settings = load_settings(profile=profile, cwd=NOWHERE).model_copy(
        update={"data_root": tmp_path / "data", "cache_root": tmp_path / "cache"}
    )
    layout = Layout.from_settings(settings)
    assert [s.name for s in time_steps(settings, layout, HTTP)] == expected
    # build_steps prüft Namen und Folge (check_step_order) über alle Schritte
    names = [s.name for s in build_steps(settings, layout, HTTP)]
    assert names.index("cycles") > max(names.index(n) for n in ("bodies", "timeline", "parties"))
    assert names.index("report") > names.index(expected[-1])


def test_the_switches_decide_which_steps_exist(tmp_path: Path, default_settings: Settings) -> None:
    layout = _layout(tmp_path)
    off = default_settings.cycles.model_copy(update={"enabled": False})
    assert time_steps(default_settings.model_copy(update={"cycles": off}), layout, HTTP) == []
    # ohne Urheber (Option 04) gibt es keine Monatstabelle, das Vokabular schon
    without = default_settings.model_copy(update={"originators": Originators()})
    assert [s.name for s in time_steps(without, layout, HTTP)] == ["vocabulary"]
    feeds = default_settings.feeds.model_copy(update={"enabled": True})
    only = default_settings.model_copy(update={"cycles": off, "feeds": feeds})
    assert [s.name for s in time_steps(only, layout, HTTP)] == ["feeds"]


def test_the_steps_read_what_they_need_and_write_under_processed(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    steps = {s.name: s for s in time_steps(default_settings, layout, HTTP)}
    files = time_files(layout)
    assert steps["cycles"].inputs == (
        layout.corpus,
        layout.document_originators,
        layout.papers_bodies,
        layout.timeline,
    )
    assert steps["cycles"].outputs == (files.months, files.budget)
    assert steps["vocabulary"].inputs == (layout.corpus,)
    assert steps["vocabulary"].optional == (layout.raw_texts,)
    assert steps["vocabulary"].outputs == (files.vocabulary, files.spans)
    # die Datei des Lexikons und seine Version stehen im Stamp
    assert LEXICON.label in steps["vocabulary"].extra
    assert LEXICON.digest[:16] in steps["vocabulary"].extra
    assert files.vocabulary.name == "dokumente_bundesvokabular.parquet"


def test_the_mini_run_writes_months_budget_and_vocabulary(mini_run: Layout) -> None:
    files = time_files(mini_run)
    corpus = pl.read_parquet(mini_run.corpus, columns=["id"])
    months = pl.read_parquet(files.months)
    assert months.schema == pl.Schema(MONTH_SCHEMA)
    assert int(months.get_column("dokumente").sum()) == corpus.height
    assert months_match_timeline(months, pl.read_parquet(mini_run.timeline))
    assert sorted(set(months.get_column("wahljahr").drop_nulls().to_list())) == [
        2020,
        2021,
        2022,
        2023,
        2024,
    ]
    budget = pl.read_parquet(files.budget)
    assert budget.get_column("wahljahr").to_list() == [2020, 2021, 2022, 2023, 2024]
    vocabulary = pl.read_parquet(files.vocabulary)
    assert vocabulary.schema == pl.Schema(VOCABULARY_SCHEMA)
    assert one_row_per_document(vocabulary, corpus.get_column("id").to_list())
    assert set(vocabulary.get_column("lexikon")) == {LEXICON.label}
    spans = pl.read_parquet(files.spans)
    assert list(spans.schema.items()) == list(SPAN_SCHEMA.items())
    assert spans.equals(sort_spans(spans))


# --- Spannen auf dem Rohtext ----------------------------------------------------------------------


def test_the_spans_point_into_the_raw_text_with_its_case_and_line_breaks() -> None:
    raw = "Kopf der Vorlage\nBetrifft: Unterbringung Geflüch\ntete\fSeite zwei: die Mietpreisbremse"
    text = flatten(raw, "betrifft", ())
    assert "geflüchtete" in text and "mietpreisbremse" in text
    corpus = pl.DataFrame(
        {
            "id": ["a", "b", "c", "d"],
            "name": ["Titel", "Asyl im Titel", "Mietpreisbremse", "Titel"],
            "text": [text, text, "die mietpreisbremse", text + " anders"],
            "file_name": ["x.pdf", "x.pdf", "ohne.pdf", "y.pdf"],
        }
    )
    found = document_categories(corpus, LEXICON)
    raw_rows = {
        "x.pdf": {"text": raw, "form_feeds": None, "extractor": "pypdf-7.1.0+roh"},
        "y.pdf": {"text": raw, "form_feeds": None, "extractor": "pypdf-7.1.0+roh"},
    }
    spans, lengths, without = vocabulary_spans(
        corpus.join(found.select("id", "kategorien"), on="id"), raw_rows, "betrifft", LEXICON
    )
    spans = sort_spans(spans)
    check_spans(spans, lengths)
    rows = spans.rows(named=True)
    # zwei Korpus-IDs teilen eine Datei: beide bekommen die Spannen; der Titeltreffer „Asyl" nicht
    assert [(r["id"], r["value"], r["norm"]) for r in rows] == [
        ("a", "Geflüch\ntete", "migration_asyl"),
        ("a", "Mietpreisbremse", "wohnen_bund"),
        ("b", "Geflüch\ntete", "migration_asyl"),
        ("b", "Mietpreisbremse", "wohnen_bund"),
    ]
    assert all(raw[r["start"] : r["end"]] == r["value"] for r in rows)
    assert {r["kind"] for r in rows} == {SPAN_KIND} and {r["section"] for r in rows} == {""}
    assert {r["extractor"] for r in rows} == {f"pypdf-7.1.0+roh; {LEXICON.label}"}
    # „c" hat keinen Rohtext, „d" einen, der nicht zu seinem Text plättet
    assert without == 2 and lengths == {"a": len(raw), "b": len(raw)}


# --- Tests über drei Perioden ---------------------------------------------------------------------


def _write_period(layout: Layout, period_name: str, first: date, last: date, month: int) -> None:
    period = _period(period_name, first, last, month, seed=len(period_name) + month)
    files = time_files(layout)
    layout.processed.mkdir(parents=True, exist_ok=True)
    layout.interim.mkdir(parents=True, exist_ok=True)
    period.months.write_parquet(files.months)
    period.budget.write_parquet(files.budget)
    period.documents.select(
        "id", "kategorien", "kopf", pl.lit(LEXICON.label).alias("lexikon")
    ).write_parquet(files.vocabulary)
    period.documents.select(
        "id",
        "date",
        pl.when(pl.col("mit_text")).then(pl.lit("x")).otherwise(pl.lit("")).alias("text"),
    ).write_parquet(layout.corpus)
    period.documents.select("id", "urheber_art").write_parquet(layout.document_originators)


def _three(tmp_path: Path, default_settings: Settings) -> tuple[Settings, Layout]:
    cycles = default_settings.cycles.model_copy(
        update={
            "periods": ["p1", "p2", "p3"],
            "elections": list(THREE.elections),
            "instrument_types": {"anfrage": "anfrage", "antrag": "antrag"},
            "instrument_titles": [],
        }
    )
    settings = default_settings.model_copy(
        update={
            "data_root": tmp_path / "data",
            "cache_root": tmp_path / "cache",
            "profile": "p2",
            "cycles": cycles,
        }
    )
    return settings, Layout.from_settings(settings)


def test_the_tests_name_the_missing_period(tmp_path: Path, default_settings: Settings) -> None:
    settings, layout = _three(tmp_path, default_settings)
    (step,) = [s for s in time_steps(settings, layout, HTTP) if s.name == "cycle_tests"]
    with pytest.raises(MissingInputError, match="p1/processed/zeit_monate.parquet"):
        run_step(step, settings)


def test_the_tests_run_over_three_periods_from_their_folders(
    tmp_path: Path, default_settings: Settings
) -> None:
    settings, layout = _three(tmp_path, default_settings)
    for name, first, last, month in (
        ("p1", date(2014, 9, 1), date(2017, 9, 9), 11),
        ("p2", date(2017, 9, 10), date(2020, 9, 12), 12),
        ("p3", date(2020, 9, 13), date(2021, 10, 31), 2),
    ):
        _write_period(layout.for_profile(name), name, first, last, month)
    (step,) = [s for s in time_steps(settings, layout, HTTP) if s.name == "cycle_tests"]
    # die Dateien des eigenen Ordners stehen zuletzt, die der anderen tragen ihren Hash in extra
    assert step.inputs[-5:] == (
        time_files(layout).months,
        time_files(layout).budget,
        time_files(layout).vocabulary,
        layout.corpus,
        layout.document_originators,
    )
    outcome = run_step(step, settings)
    assert outcome.status == "ausgeführt", outcome.line()
    table = pl.read_parquet(time_files(layout).hypotheses)
    check_hypotheses(table)
    assert dict(table.select("hypothese", "ergebnis").rows())["H17.2"] == CONFIRMED
    assert run_step(step, settings).status == "übersprungen"
    # eine andere Periode ändert sich: ihr Hash steht in extra, der Schritt ist veraltet
    other = time_files(layout.for_profile("p1")).budget
    pl.read_parquet(other).with_columns(pl.col("haushaltsantraege") + 1).write_parquet(other)
    rebuilt = next(s for s in time_steps(settings, layout, HTTP) if s.name == "cycle_tests")
    assert run_step(rebuilt, settings).status == "ausgeführt"


def test_the_tests_refuse_a_period_counted_with_another_lexicon(
    tmp_path: Path, default_settings: Settings
) -> None:
    settings, layout = _three(tmp_path, default_settings)
    for name, first, last, month in (
        ("p1", date(2014, 9, 1), date(2017, 9, 9), 11),
        ("p2", date(2017, 9, 10), date(2020, 9, 12), 12),
        ("p3", date(2020, 9, 13), date(2021, 10, 31), 2),
    ):
        _write_period(layout.for_profile(name), name, first, last, month)
    old = time_files(layout.for_profile("p3")).vocabulary
    pl.read_parquet(old).with_columns(pl.lit("bundespolitik 0").alias("lexikon")).write_parquet(old)
    (step,) = [s for s in time_steps(settings, layout, HTTP) if s.name == "cycle_tests"]
    with pytest.raises(SchemaError, match="bundespolitik 0"):
        run_step(step, settings)


# --- Feeds ---------------------------------------------------------------------------------------


def test_the_feeds_of_the_mini_fixture(
    tmp_path: Path, mini_run: Layout, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", NOWHERE, mini_run.profile)
    for source, target in (
        (mini_run.corpus, layout.corpus),
        (mini_run.dictionary, layout.dictionary),
        (mini_run.index, layout.index),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, target)
    feeds = default_settings.feeds.model_copy(update={"enabled": True, "entries": 3})
    off = default_settings.cycles.model_copy(update={"enabled": False})
    settings = default_settings.model_copy(update={"feeds": feeds, "cycles": off})
    (step,) = time_steps(settings, layout, HTTP)
    stale = feed_dir(layout) / "wahlbezirk-99.xml"
    stale.parent.mkdir(parents=True)
    stale.write_text("alt", encoding="utf-8")
    outcome = run_step(step, settings)
    assert outcome.status == "ausgeführt", outcome.line()
    manifest = pl.read_parquet(time_files(layout).feeds)
    assert manifest.schema == pl.Schema(FEEDS_SCHEMA)
    districts = hits_by_district(pl.read_parquet(layout.dictionary), pl.read_parquet(layout.index))
    assert manifest.height == districts.height
    assert not stale.exists()  # einen Wahlbezirk 99 gibt es nicht
    written = sorted(feed_dir(layout).glob("*.xml"))
    assert [f"feeds/{p.name}" for p in written] == manifest.get_column("datei").to_list()
    for path in written:
        assert atom_problems(path.read_text(encoding="utf-8")) == [], path.name
    assert manifest.get_column("eintraege").max() == 3
    assert (manifest.get_column("eintraege") <= manifest.get_column("dokumente")).all()
    before = {p.name: p.read_bytes() for p in written}
    again = run_step(step, settings, force=True)
    assert "0 geändert" in again.reason
    assert {p.name: p.read_bytes() for p in sorted(feed_dir(layout).glob("*.xml"))} == before
