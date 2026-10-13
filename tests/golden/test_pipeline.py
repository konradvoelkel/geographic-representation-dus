"""Die neue Kette als Ganzes: Bootstrap, Schritte, Stamps, Wiederholung, Golden Master."""

from __future__ import annotations

import json
import re
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from georep.analysis import scaling
from georep.analysis.hits import DISTRICT, citywide_terms
from georep.analysis.regression import regression_pair
from georep.bootstrap import bootstrap
from georep.errors import MissingInputError
from georep.layout import Layout
from georep.pipeline import Outcome, UnknownStepError, build_steps, run_pipeline
from georep.prep.voters import TURNOUT
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
        # Option 05: bodies hängt nur am Korpus, body_hits an der geänderten Auswertung
        "bodies": "übersprungen",
        # Option 06: topics liest nur den Korpus und der ist unverändert; weights hängt am Index
        "topics": "übersprungen",
        # Punkt 45: der Klassifikator liest Korpus und Gremien, beide unverändert
        "committees": "übersprungen",
        "index": "ausgeführt",
        "timeline": "ausgeführt",  # Option 07: haengt an Index und Woerterbuch
        "results": "ausgeführt",
        "metrics": "ausgeführt",  # Punkt 46: haengt an results und Woerterbuch
        "body_hits": "ausgeführt",
        "weights": "ausgeführt",
        "parties": "ausgeführt",  # Option 04: haengt an results
        "report": "ausgeführt",
    }
    changed = next(o for o in third if o.step == "pois")
    assert changed.reason.startswith("Eingabe geändert")


def test_the_seeded_topics_keep_their_invariants_on_the_mini_fixture(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Punkt 45: keine Zahlen, nur die Eigenschaften — die Zahlen hängen am Rechner.

    Das Themenmodell ist je Rechner und je Thread-Zahl reproduzierbar, nicht darüber hinaus
    (STATUS.md, „Bekannt"); geprüft werden darum Zeilenzahlen, die Zerlegung und die Saat.
    """
    topics = pl.read_parquet(mini_run.topics)
    shares = pl.read_parquet(mini_run.topic_shares)
    assert topics.height == default_settings.topics.k
    assert topics.get_column("thema").to_list() == list(range(default_settings.topics.k))
    codes = [c for c in topics.get_column("gremium").to_list() if c is not None]
    # Die Mini-Fixture hat zwei Ausschüsse über der Schwelle; die Zahl folgt aus den Settings,
    # nicht aus einer Konstante: höchstens ``k - free``, jedes Kürzel höchstens einmal.
    assert 0 < len(codes) <= default_settings.topics.k - default_settings.topics.free
    assert len(codes) == len(set(codes)) <= len(default_settings.bodies.committees)
    assert set(codes) <= set(default_settings.bodies.committees)
    sums = shares.get_column("anteile").list.sum().to_list()
    assert all(abs(value - 1.0) <= 1e-9 for value in sums)
    assert shares.height == pl.read_parquet(mini_run.topic_documents).height


def test_the_committee_assignment_keeps_its_invariants_on_the_mini_fixture(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Punkt 45: Zeilenzahlen, Zerlegung und Schwelle, keine Zahlen des Modells."""
    papers = pl.read_parquet(mini_run.papers_committee)
    table = pl.read_parquet(mini_run.committee_table)
    corpus = pl.read_parquet(mini_run.corpus, columns=["id", "text"])
    with_text = corpus.filter(pl.col("text") != "").height
    assert papers.height == with_text
    assert papers.get_column("id").to_list() == sorted(papers.get_column("id").to_list())
    assert int(table.get_column("dokumente").sum()) == with_text
    assert float(table.get_column("anteil").sum()) == pytest.approx(1.0, abs=1e-9)
    codes = {c for c in table.get_column("ausschuss").to_list() if c}
    assert codes <= set(default_settings.bodies.committees)
    assigned = papers.filter(pl.col("ausschuss") != "")
    assert (
        assigned.get_column("wahrscheinlichkeit") >= default_settings.classify.min_probability
    ).all()
    assert assigned.get_column("wahrscheinlichkeit").null_count() == 0
    # Die Restklasse trägt keine Wahrscheinlichkeit, die anderen Zeilen eine.
    rest = table.filter(pl.col("ausschuss") == "")
    assert rest.height <= 1
    assert all(value is None for value in rest.get_column("wahrscheinlichkeit_median").to_list())


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
        # Punkt 45
        "papers_committee",
        "committee_table",
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
    # Budget der Seite: eine Zahl, in den Settings (Punkt 50, docs/seitengroesse-2026-10.md, § 7)
    assert layout.site_index.stat().st_size < settings.report.page_budget_bytes
    _check_search_section(page)
    # Je Tabelle Parquet und CSV, dazu GeoJSON, Schema, Dokumentliste, summary.json (Option 01)
    # und die Begriffe je Wahlbezirk (Punkt 49)
    assert len(list(layout.site_data.iterdir())) == 2 * len(published(layout)) + 5
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


# Regeln an (die Vorgaben): die Zahlen, die der Lauf über die volle Referenz am 2026-10-12 ergab.
# Sie sind bewusst gespeicherte Erwartungswerte dieses Repos, nicht die der Arbeit (decisions.md,
# Punkte 43 und 44); wer sie ändert, ändert die Methodik und schreibt es dort und im Review auf.
WITH_RULES = {
    "pois": 1196,  # von 1309; 113 Einrichtungen mit Stadtnamen
    "terms": 5727,  # von 5841
    "hits": 29_010,  # von 29 573
    "citywide": 55,  # Begriffe über dem 99-%-Quantil (64 Dokumente)
    "districts_changed": 12,
}
WITH_RULES_TABLE_FIVE = (79.9539, 48.1709, 0.1891, 0.23641)  # Steigung, Achse, r, p
WITH_RULES_WITHOUT_OUTLIERS = (216.2416, 40.5715, 0.3351, 0.03705)
# Punkt 46: die zweite Kennzahl des Methodik-Reviews, am 2026-10-13 auf der Referenz gemessen
# (docs/skalierung-2026-10.md, § 2.3 und § 3.3). Mit ihr bleibt vom Zusammenhang nichts, nicht
# einmal das Vorzeichen -- und die einzige Spalte, in der Tabelle 5 ein signifikantes p zeigt,
# verschwindet.
PER_TERM = {"terms": 6877, "min": 2.2485, "median": 4.5656, "max": 9.5472, "city_mean": 0.061808}
PER_TERM_TABLE = (-0.5570, 55.7576, -0.1118, 0.48644)  # Steigung, Achse, r, p
PER_TERM_WITHOUT_OUTLIERS = (-0.2400, 54.4333, -0.0419, 0.80000)


@pytest.mark.slow
def test_the_rules_change_the_reference_as_measured(
    tmp_path: Path, reference_root: Path, default_settings: Settings
) -> None:
    """Derselbe Lauf mit den Vorgaben, also mit den Regeln an (docs/methodik-review-2026-10.md, § 4).

    Der Test daneben (``test_pipeline_reproduces_the_thesis_results``) hält die exakte
    Reproduktion mit abgeschalteten Regeln; dieser hält, was die Regeln daran ändern. Beide
    zusammen sind die Golden-Master-Politik aus decisions.md, Punkt 43.
    """
    layout = _layout(tmp_path, reference_root)
    bootstrap(layout)
    run_pipeline(build_steps(default_settings, layout), default_settings)
    assert pl.read_parquet(layout.pois_table).height == WITH_RULES["pois"]
    index = pl.read_parquet(layout.index)
    assert index.height == WITH_RULES["terms"]
    results = pl.read_parquet(layout.results)
    assert int(results.get_column("anzahl_treffer").sum()) == WITH_RULES["hits"]
    found = citywide_terms(
        index,
        quantile=default_settings.search.citywide_quantile,
        median_factor=default_settings.search.citywide_median_factor,
    )
    assert found.threshold == 64 and len(found.terms) == WITH_RULES["citywide"]
    assert "stadtwerke düsseldorf" not in index.get_column("suchbegriffe").to_list()
    # Straßen sind nie betroffen: der stärkste Begriff der Arbeit steht unverändert im Index
    assert "grafenberger allee" in index.get_column("suchbegriffe").to_list()

    pair = regression_pair(results, default_settings.analysis.exclude_districts)
    assert pair.without is not None
    for got, (slope, intercept, r, p) in (
        (pair.all, WITH_RULES_TABLE_FIVE),
        (pair.without, WITH_RULES_WITHOUT_OUTLIERS),
    ):
        assert got.slope == pytest.approx(slope, abs=5e-4)
        assert got.intercept == pytest.approx(intercept, abs=5e-4)
        assert got.r == pytest.approx(r, abs=5e-5)
        assert got.p == pytest.approx(p, abs=5e-5)
    # Der Befund der Arbeit bleibt: über alle 41 Bezirke ist der Zusammenhang nicht signifikant
    assert pair.all.n == 41 and pair.all.p > 0.05

    # Genau zwölf Wahlbezirke tragen andere Trefferzahlen als die Arbeit, keiner mehr als vorher
    thesis = pl.read_csv(
        reference_root / "processed" / "wahlbezirke_auswertung.csv", infer_schema_length=None
    ).select("wahlkreis_id", "anzahl_treffer")
    changed = (
        thesis.join(
            results.select("wahlkreis_id", "anzahl_treffer"), on="wahlkreis_id", suffix="_neu"
        )
        .with_columns((pl.col("anzahl_treffer_neu") - pl.col("anzahl_treffer")).alias("differenz"))
        .filter(pl.col("differenz") != 0)
    )
    assert changed.height == WITH_RULES["districts_changed"]
    assert bool((changed.get_column("differenz") < 0).all())
    assert changed.filter(pl.col("wahlkreis_id") == 10).get_column("differenz").item() == -177

    # Punkt 46: die normierten Kennzahlen und die zweite Regression, am 2026-10-13 gemessen
    # (docs/skalierung-2026-10.md, § 2.3 und § 3.3)
    metrics = pl.read_parquet(layout.district_metrics)
    assert metrics.height == 41
    assert int(metrics.get_column(scaling.TERM_COUNT).sum()) == PER_TERM["terms"]
    per_term = metrics.get_column(scaling.PER_TERM)
    assert float(per_term.min()) == pytest.approx(PER_TERM["min"], abs=5e-5)  # type: ignore[arg-type]
    assert float(per_term.median()) == pytest.approx(PER_TERM["median"], abs=5e-5)  # type: ignore[arg-type]
    assert float(per_term.max()) == pytest.approx(PER_TERM["max"], abs=5e-5)  # type: ignore[arg-type]
    assert float(metrics.get_column(scaling.CITY_MEAN)[0]) == pytest.approx(
        PER_TERM["city_mean"], abs=5e-7
    )
    second = regression_pair(
        metrics.join(results.select(DISTRICT, TURNOUT), on=DISTRICT, how="inner"),
        default_settings.analysis.exclude_districts,
        x=scaling.PER_TERM,
        y=TURNOUT,
    )
    assert second.without is not None
    for got, (slope, intercept, r, p_value) in (
        (second.all, PER_TERM_TABLE),
        (second.without, PER_TERM_WITHOUT_OUTLIERS),
    ):
        assert got.slope == pytest.approx(slope, abs=5e-4)
        assert got.intercept == pytest.approx(intercept, abs=5e-4)
        assert got.r == pytest.approx(r, abs=5e-5)
        assert got.p == pytest.approx(p_value, abs=5e-5)
    # Der Befund haelt auch mit der normierten Kennzahl, und die Spalte, die in Tabelle 5 ein
    # signifikantes p zeigt, verschwindet: sie haengt an der Groesse der Woerterbuecher.
    assert second.all.p > 0.05 and second.without.p > 0.05

    page = layout.site_index.read_text(encoding="utf-8")
    assert layout.site_index.stat().st_size < default_settings.report.page_budget_bytes
    assert "Stadtweite Begriffe" in page and "Zwei Regeln weichen bewusst" in page
