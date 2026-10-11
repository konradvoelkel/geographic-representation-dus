"""Die neue Kette als Ganzes: Bootstrap, Schritte, Stamps, Wiederholung, Golden Master."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from georep.bootstrap import bootstrap
from georep.errors import MissingInputError
from georep.layout import Layout
from georep.pipeline import Outcome, UnknownStepError, build_steps, run_pipeline
from georep.report.tables import published
from georep.settings import Settings, load_settings

NETWORK = {"opendata", "papers", "pdfs", "streets_osm", "pois_wiki"}
EXACT = ["wahlkreis_id", "anzahl_treffer", "Wahlberechtigte_insgesamt", "Waehler", "suchbegriffe"]
FLOATS = ["wahlkreis_id", "trefferquote", "wahlbeteiligung"]


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def _layout(tmp_path: Path, reference: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", reference)


def _results_as_legacy(path: Path) -> pl.DataFrame:
    return (
        pl.read_parquet(path)
        .with_columns(pl.col("suchbegriffe").list.join("; "))
        .sort("wahlkreis_id")
    )


def _compare_results(got: pl.DataFrame, expected_csv: Path) -> None:
    exp = pl.read_csv(expected_csv, infer_schema_length=None).sort("wahlkreis_id")
    assert_frame_equal(got.select(EXACT), exp.select(EXACT))
    assert_frame_equal(got.select(FLOATS), exp.select(FLOATS), rel_tol=1e-12)


def test_pipeline_runs_skips_and_reruns(
    tmp_path: Path, mini_root: Path, settings: Settings
) -> None:
    layout = _layout(tmp_path, mini_root)
    bootstrap(layout)
    steps = build_steps(settings, layout)

    def offline(outcomes: list[Outcome]) -> dict[str, str]:
        return {o.step: o.status for o in outcomes if o.step not in NETWORK}

    planned = run_pipeline(steps, settings, dry_run=True)
    n_offline = sum(1 for s in steps if not s.network)
    assert set(offline(planned).values()) == {"geplant"} and len(offline(planned)) == n_offline
    assert all(
        o.status == "übersprungen" and "Netz aus" in o.reason for o in planned if o.step in NETWORK
    )
    assert not layout.results.exists()

    first = run_pipeline(steps, settings)
    assert set(offline(first).values()) == {"ausgeführt"}
    assert all(s.stamp_path.exists() for s in steps if s.name not in NETWORK)
    _compare_results(
        _results_as_legacy(layout.results), mini_root / "expected" / "wahlbezirke_auswertung.csv"
    )

    second = run_pipeline(steps, settings)
    assert set(offline(second).values()) == {"übersprungen"}
    assert all(o.reason == "aktuell" for o in second if o.step not in NETWORK)

    forced = run_pipeline(steps, settings, ["results"], force=True)
    assert [(o.step, o.status) for o in forced] == [("results", "ausgeführt")]

    # Eine geänderte Eingabe zieht ihre Nachfolger nach sich
    layout.pois.write_text(
        layout.pois.read_text(encoding="utf-8").replace("Kunstakademie", "Kunstakademíe", 1),
        encoding="utf-8",
    )
    third = run_pipeline(steps, settings)
    assert offline(third) == {
        "texts": "übersprungen",
        "voters": "übersprungen",
        "streets": "übersprungen",
        "pois": "ausgeführt",
        "dictionary": "ausgeführt",
        "corpus": "übersprungen",
        "index": "ausgeführt",
        "results": "ausgeführt",
        "report": "ausgeführt",
    }
    changed = next(o for o in third if o.step == "pois")
    assert changed.reason.startswith("Eingabe geändert")


def test_missing_corpus_names_bootstrap(
    tmp_path: Path, mini_root: Path, settings: Settings
) -> None:
    layout = _layout(tmp_path, mini_root)
    bootstrap(layout)
    with pytest.raises(MissingInputError, match="bootstrap"):
        run_pipeline(build_steps(settings, layout), settings, ["index"])


def test_unknown_step_is_an_error(tmp_path: Path, mini_root: Path, settings: Settings) -> None:
    with pytest.raises(UnknownStepError, match="unbekannt"):
        run_pipeline(build_steps(settings, _layout(tmp_path, mini_root)), settings, ["unbekannt"])


def test_two_runs_write_identical_parquet(
    tmp_path: Path, mini_root: Path, settings: Settings
) -> None:
    a, b = _layout(tmp_path / "a", mini_root), _layout(tmp_path / "b", mini_root)
    for layout in (a, b):
        bootstrap(layout)
        run_pipeline(build_steps(settings, layout), settings)
    for name in ("dictionary", "index", "results"):
        assert getattr(a, name).read_bytes() == getattr(b, name).read_bytes(), name


@pytest.mark.slow
def test_pipeline_reproduces_the_thesis_results(
    tmp_path: Path, reference_root: Path, settings: Settings
) -> None:
    layout = _layout(tmp_path, reference_root)
    bootstrap(layout)
    outcomes = run_pipeline(build_steps(settings, layout), settings)
    assert all(o.status == "ausgeführt" for o in outcomes if o.step not in NETWORK)
    page = layout.site_index.read_text(encoding="utf-8")
    assert "41 Kommunalwahlbezirke" in page and page.count('id="bezirk-') == 41
    assert layout.site_index.stat().st_size < 1_500_000  # Budget der Seite, Meta-Plan 2026-10 § 2
    assert len(list(layout.site_data.iterdir())) == 2 * len(published(layout)) + 3
    assert (layout.site / "karte.html").stat().st_size < 1_000_000
    _compare_results(
        _results_as_legacy(layout.results),
        reference_root / "processed" / "wahlbezirke_auswertung.csv",
    )
    got = pl.read_parquet(layout.index)
    exp = pl.read_csv(
        reference_root / "processed" / "inverted_index.csv",
        infer_schema_length=None,
        schema_overrides={"suchbegriffe": pl.String, "paper_ids": pl.String},
    )
    got_sets = {r["suchbegriffe"]: frozenset(r["paper_ids"]) for r in got.iter_rows(named=True)}
    exp_sets = {
        r["suchbegriffe"]: frozenset(str(r["paper_ids"]).split(";"))
        if r["paper_ids"]
        else frozenset()
        for r in exp.iter_rows(named=True)
    }
    assert got_sets == exp_sets
