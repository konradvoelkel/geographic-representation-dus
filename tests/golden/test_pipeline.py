"""Die neue Kette als Ganzes: Bootstrap, Schritte, Stamps, Wiederholung, Golden Master."""

from __future__ import annotations

import json
import re
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from georep.analysis.regression import regression_pair
from georep.bootstrap import bootstrap
from georep.errors import MissingInputError
from georep.layout import Layout
from georep.pipeline import Outcome, UnknownStepError, build_steps, run_pipeline
from georep.report.search import fold, fold_ascii
from georep.report.tables import published
from georep.settings import Settings, load_settings
from tests.conftest import as_in_the_thesis

NETWORK = {"opendata", "papers", "organizations", "pdfs", "streets_osm", "pois_wiki"}
EXACT = ["wahlkreis_id", "anzahl_treffer", "Wahlberechtigte_insgesamt", "Waehler", "suchbegriffe"]
FLOATS = ["wahlkreis_id", "trefferquote", "wahlbeteiligung"]


@pytest.fixture(scope="module")
def settings() -> Settings:
    """Die Settings dieses Moduls sind die der Arbeit: eigene Regeln aus (conftest, Punkt 43)."""
    return as_in_the_thesis(load_settings(cwd=Path("/nonexistent")))


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
        "shapes": "übersprungen",
        "texts": "übersprungen",
        "voters": "übersprungen",
        "streets": "übersprungen",
        "pois": "ausgeführt",
        "dictionary": "ausgeführt",
        "corpus": "übersprungen",
        # Option 06: topics liest nur den Korpus und der ist unverändert; weights hängt am Index
        "topics": "übersprungen",
        "index": "ausgeführt",
        "timeline": "ausgeführt",  # Option 07: haengt an Index und Woerterbuch
        "results": "ausgeführt",
        # Option 05: bodies hängt nur am Korpus, body_hits an der geänderten Auswertung
        "bodies": "übersprungen",
        "body_hits": "ausgeführt",
        "weights": "ausgeführt",
        "parties": "ausgeführt",  # Option 04: haengt an results
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
    for name in (
        "dictionary",
        "index",
        "results",
        # Option 05
        "papers_bodies",
        "district_bodies",
        "bodies_table",
        "district_units",
        # Option 06: auch das Themenmodell und die Gewichte sind reproduzierbar
        "topics",
        "topic_documents",
        "topic_shares",
        "term_weights",
        "weighted",
        # Option 04
        "document_originators",
        "district_originators",
        "party_results",
        # Option 07
        "timeline",
        "district_timeline",
    ):
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
    _check_search_section(page)
    # Je Tabelle Parquet und CSV, dazu GeoJSON, Schema, Dokumentliste, summary.json (Option 01)
    assert len(list(layout.site_data.iterdir())) == 2 * len(published(layout)) + 4
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


def _check_search_section(page: str) -> None:
    """Option 08: die Suchdaten stehen in der Seite, und keine zwei Einträge fallen zusammen."""
    match = re.search(
        r'<script id="suche-daten" type="application/json">(.*?)</script>', page, re.S
    )
    assert match is not None
    payload = json.loads(match.group(1))  # json.loads löst jede Maskierung des < auf
    entries = payload["entries"]
    # 4135 kanonische Begriffe (2828 Straßen, 1239 Orte, 68 beides) plus 41 Wahlbezirksnamen.
    assert len(entries) == 4176
    assert sum(1 for e in entries if e[3] == "w") == 41
    assert ["münchener straße", [15, 16, 18, 35, 36, 37, 39], 141, "s"] in entries
    folded = [(fold(term), kind) for term, _, _, kind in entries]
    assert len(set(folded)) == len(folded)
    ascii_folded = [(fold_ascii(term), kind) for term, _, _, kind in entries]
    assert len(set(ascii_folded)) == len(ascii_folded)
    assert 'role="option"' not in page  # die Liste füllt erst das JavaScript


@pytest.mark.slow
def test_weighted_variants_reproduce_table_five_and_decompose_the_count(
    tmp_path: Path, reference_root: Path, settings: Settings
) -> None:
    """Option 06 auf der Referenz: die Einheitsvariante ist Tabelle 5, die Themen zerlegen sie.

    Die Zahlen von Tabelle 5 stehen eingefroren in ``test_regression_numbers.py``; hier müssen sie
    aus ``trefferquote_gewichtet`` der Variante ``einheit`` auf dieselben Stellen fallen.
    """
    layout = _layout(tmp_path, reference_root)
    bootstrap(layout)
    run_pipeline(build_steps(settings, layout), settings)
    results = pl.read_parquet(layout.results)
    weighted = pl.read_parquet(layout.weighted)
    variants = weighted.get_column("variante").unique().to_list()
    assert "einheit" in variants and sum(1 for v in variants if v.startswith("thema_")) == 20
    assert weighted.height == len(variants) * results.height

    unit = weighted.filter(pl.col("variante") == "einheit").join(
        results.select("wahlkreis_id", "wahlbeteiligung", "anzahl_treffer"), on="wahlkreis_id"
    )
    assert (
        unit.get_column("anzahl_treffer_gewichtet")
        == unit.get_column("anzahl_treffer").cast(pl.Float64)
    ).all()
    assert int(unit.get_column("anzahl_treffer_gewichtet").sum()) == 29_573
    pair = regression_pair(unit, settings.analysis.exclude_districts, x="trefferquote_gewichtet")
    assert pair.all.n == 41
    assert pair.all.slope == pytest.approx(62.1337, abs=5e-4)
    assert pair.all.r == pytest.approx(0.16125, abs=5e-5)
    assert pair.all.p == pytest.approx(0.31385, abs=5e-5)
    assert pair.without is not None and pair.without.n == 39
    assert pair.without.slope == pytest.approx(215.3341, abs=5e-4)
    assert pair.without.r == pytest.approx(0.338461, abs=5e-6)
    assert pair.without.p == pytest.approx(0.035069, abs=5e-6)

    # Die 20 Themenvarianten zerlegen die Einheitszählung je Wahlbezirk.
    per_district = dict(
        weighted.filter(pl.col("variante").str.starts_with("thema_"))
        .group_by("wahlkreis_id")
        .agg(pl.col("anzahl_treffer_gewichtet").sum())
        .iter_rows()
    )
    for row in unit.iter_rows(named=True):
        assert per_district[row["wahlkreis_id"]] == pytest.approx(
            row["anzahl_treffer_gewichtet"], rel=1e-9
        )
    # Kein Gewicht über 1: die Summe bleibt unter der Zahl der Paare je Bezirk.
    assert (
        weighted.get_column("anzahl_treffer_gewichtet")
        <= unit.get_column("anzahl_treffer_gewichtet").max()
    ).all()
    # Die Themenbeschriftungen tragen kein Funktionswort.
    from georep.analysis.topics import load_stop_words

    stop = load_stop_words(settings.topics.stop_words)
    words = pl.read_parquet(layout.topics).get_column("woerter").to_list()
    assert all(not (set(label) & stop) for label in words)


def test_excluding_citywide_terms_lowers_the_hits(tmp_path: Path, mini_root: Path) -> None:
    """Regel 2 mit dem zweiten Schalter (decisions.md, Punkt 44): die Begriffe zählen nicht mehr.

    Standard ist „nur anzeigen"; dieser Test ist der Beleg, dass der Schalter wirkt und dass die
    Zeile des Schritts sagt, wie viele Begriffe gefallen sind.
    """
    shown = load_settings(cwd=Path("/nonexistent"))
    dropped = shown.model_copy(
        update={"search": shown.search.model_copy(update={"citywide_exclude": True})}
    )
    hits: dict[str, int] = {}
    for name, settings in (("anzeigen", shown), ("ausschliessen", dropped)):
        layout = _layout(tmp_path / name, mini_root)
        bootstrap(layout)
        outcomes = run_pipeline(build_steps(settings, layout), settings)
        hits[name] = int(pl.read_parquet(layout.results).get_column("anzahl_treffer").sum())
        line = next(o for o in outcomes if o.step == "results").reason
        assert ("stadtweite Begriffe ausgeschlossen" in line) == (name == "ausschliessen")
    assert hits["ausschliessen"] < hits["anzeigen"]
