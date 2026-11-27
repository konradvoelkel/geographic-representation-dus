"""Vorhaben 17 über die drei Düsseldorfer Perioden, gegen die Messung (Messdokument 17, § 3 und § 4.1).

Zwei Arten von Zahlen. **Die Validierung als Regressionstest**: an den Labels zweier KI-Kodierer
(``validierung/17-zeit/labels.csv``, 100 Treffer, zehn je Kategorie) muss die Präzision des Lexikons
Version 2026-11-23.1 bei 94 von 100 bleiben, und jeder Treffer der Stichprobe muss in der gebauten
Ausgabe noch seine Kategorie tragen; die Zahl steht in ``analysis.lexicon.VALIDATED`` und macht
H17.3 gültig. **Die vorab festgelegten Tests** (§ 8) mit den Zahlen aus § 3.1 bis § 3.3, gerundet wie
dort, bis eine neue Lexikonversion sie bewusst neu einfriert. Dazu die Spannen der Hauptperiode auf
dem Rohtext aus dem Paket: jede liegt im Rohtext und ist dort ein Treffer ihrer Kategorie.

Die Korpora entstehen wie in ``georep run``: ``bootstrap`` aus den Datenpaketen im Repo, dann die
Schritte ``corpus`` und ``bodies``, die Urheber aus Option 04, dann die reinen Funktionen der
Schritte ``cycles``, ``vocabulary`` und ``cycle_tests``.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.analysis.cycles import (
    PeriodData,
    budget_months,
    complete_years,
    cycle_hypotheses,
    month_table,
)
from georep.analysis.lexicon import (
    VALIDATED,
    document_categories,
    load_lexicon,
    vocabulary_spans,
)
from georep.analysis.parties import classify_originators
from georep.bootstrap import bootstrap_from_settings
from georep.enrich.cycles import cycle_rules
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.settings import Settings, load_settings
from georep.spans import check_spans, sort_spans
from georep.stores import RawTextStore

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / "validierung" / "17-zeit"
NOWHERE = Path("/nonexistent")
PROFILES = ("duesseldorf-2014", "duesseldorf", "duesseldorf-2025")
LEXICON = load_lexicon("bundespolitik")


@dataclass(frozen=True)
class Period:
    settings: Settings
    layout: Layout
    data: PeriodData
    corpus: pl.DataFrame


def _period(profile: str, root: Path) -> Period:
    settings = load_settings(profile=profile, cwd=NOWHERE).model_copy(
        update={"data_root": root / "data", "cache_root": root / "cache"}
    )
    layout = Layout.from_settings(settings)
    bootstrap_from_settings(layout, settings)
    outcomes = run_pipeline(build_steps(settings, layout), settings, ["corpus", "bodies"])
    assert all(o.status == "ausgeführt" for o in outcomes), [o.line() for o in outcomes]
    corpus = pl.read_parquet(layout.corpus)
    originators = classify_originators(corpus, settings.originators)
    bodies = pl.read_parquet(layout.papers_bodies)
    rules = cycle_rules(settings)
    last = settings.period.end or corpus.get_column("date").max()
    years = complete_years(settings.period.start, last, rules.start_month)  # type: ignore[arg-type]
    months = month_table(corpus, originators, bodies, rules, years)
    vocabulary = document_categories(corpus, LEXICON, settings.cycles.head_chars)
    documents = (
        corpus.select("id", "date", (pl.col("text") != "").alias("mit_text"))
        .join(originators.select("id", "urheber_art"), on="id", how="left")
        .join(vocabulary.select("id", "kategorien", "kopf"), on="id", how="left")
        .sort("id")
    )
    data = PeriodData(layout.root.name, months, budget_months(months, rules), documents)
    return Period(settings, layout, data, corpus.join(vocabulary, on="id").sort("id"))


@pytest.fixture(scope="module")
def periods(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Period]:
    root = tmp_path_factory.mktemp("cycles")
    return {p: _period(p, root) for p in PROFILES}


@pytest.fixture(scope="module")
def table(periods: dict[str, Period]) -> dict[str, dict[str, Any]]:
    rules = cycle_rules(load_settings(profile="duesseldorf-vergleich", cwd=NOWHERE))
    frame = cycle_hypotheses([periods[p].data for p in PROFILES], rules, LEXICON)
    return {str(r["hypothese"]): r for r in frame.iter_rows(named=True)}


# --- Validierung (§ 4.1) --------------------------------------------------------------------------


def test_the_coded_precision_is_94_of_100_and_every_hit_is_still_a_hit(
    periods: dict[str, Period],
) -> None:
    with (VALIDATION / "stichprobe.csv").open(encoding="utf-8") as handle:
        sample = {row["aufgabe"]: row for row in csv.DictReader(handle)}
    with (VALIDATION / "labels.csv").open(encoding="utf-8") as handle:
        labels = {
            row["aufgabe"]: json.loads(row["label"])
            for row in csv.DictReader(handle)
            if row["frage"] == "thema"
        }
    built = {
        ident: categories
        for p in periods.values()
        for ident, categories in p.corpus.select("id", "kategorien").iter_rows()
    }
    assert len(sample) == len(labels) == 100
    missing = [t for t, row in sample.items() if row["kategorie"] not in built[row["id"]]]
    assert missing == []  # die gebaute Ausgabe trägt jeden gezogenen Treffer
    right: dict[str, int] = {}
    for task, row in sample.items():
        right[row["kategorie"]] = right.get(row["kategorie"], 0) + (
            row["kategorie"] in labels[task]
        )
    assert sum(right.values()) == 94
    assert VALIDATED[(LEXICON.key, LEXICON.version)] == (94, 100)
    # je Kategorie wie § 4.1: Gendern und Ukraine 8 von 10, Klima und Energiekrise 9 von 10
    assert right == {
        "migration_asyl": 10,
        "klima_energie": 9,
        "sozialstaat": 10,
        "gendern": 8,
        "bundesverkehr": 10,
        "wohnen_bund": 10,
        "cannabis": 10,
        "corona": 10,
        "ukraine_krieg": 8,
        "energiekrise": 9,
    }


# --- Datenlage und Exposition (§ 2, § 3.1, § 3.2) ----------------------------------------------------


def test_the_fraction_documents_per_election_year(periods: dict[str, Period]) -> None:
    rows = pl.concat([periods[p].data.months for p in PROFILES]).filter(
        pl.col("wahljahr").is_not_null()
    )
    per_year = (
        rows.group_by("wahljahr")
        .agg(
            pl.col("dokumente").filter(pl.col("urheber_art") == "Fraktion").sum().alias("fraktion"),
            pl.col("dokumente").sum().alias("alle"),
        )
        .sort("wahljahr")
    )
    assert per_year.get_column("wahljahr").to_list() == list(range(2014, 2026))
    assert per_year.get_column("fraktion").to_list() == [
        1582, 1486, 1351, 1358, 1401, 1380, 1653, 1634, 1644, 1442, 1434, 1499,
    ]  # fmt: skip
    assert per_year.get_column("alle").to_list() == [
        3643, 3608, 3370, 3441, 3683, 3751, 4079, 3843, 3911, 3487, 3657, 3623,
    ]  # fmt: skip


def test_the_budget_months_are_those_of_the_exposure(periods: dict[str, Period]) -> None:
    budget = pl.concat([periods[p].data.budget for p in PROFILES])
    assert budget.get_column("monat_kalender").to_list() == [11] * 6 + [2] + [12] * 4 + [3]
    assert budget.get_column("haushaltsantraege").to_list() == [
        13, 16, 16, 16, 36, 42, 171, 118, 158, 126, 105, 166,
    ]  # fmt: skip
    assert budget.get_column("im_monat").to_list() == [
        13, 13, 12, 9, 27, 32, 136, 82, 108, 65, 63, 145,
    ]  # fmt: skip


# --- die drei Hypothesen und ihre Sensitivitäten (§ 3, § 8.5) ----------------------------------------


def _percent(value: Any) -> float:
    return round(100 * float(value), 1)


@pytest.mark.parametrize(
    ("key", "effect", "lo", "hi", "p", "p_random", "count", "n"),
    [
        ("H17.1", -4.9, -12.9, 3.8, 0.8472, 0.80, 20, 9),
        ("H17.1/S1.1", -6.8, -14.6, 1.6, 0.9183, 0.95, 20, 9),
        ("H17.1/S1.2", -6.2, -20.3, 10.4, 0.7617, 0.75, 20, 9),
        ("H17.1/S1.3", -6.8, -15.0, 2.3, 0.9005, 26 / 30, 30, 11),
        ("H17.1/S1.5/anfrage", 34.9, 3.1, 76.5, 0.0369, 0.10, 20, 9),
        ("H17.1/S1.5/antrag", 53.8, -5.5, 150.2, 0.0682, 0.20, 20, 9),
    ],
)
def test_the_pre_election_year(
    table: dict[str, dict[str, Any]],
    key: str,
    effect: float,
    lo: float,
    hi: float,
    p: float,
    p_random: float,
    count: int,
    n: int,
) -> None:
    row = table[key]
    assert (
        _percent(row["effekt"]),
        _percent(row["effekt_unten"]),
        _percent(row["effekt_oben"]),
    ) == (
        effect,
        lo,
        hi,
    )
    assert round(float(row["p"]), 4) == p
    assert math.isclose(float(row["p_randomisierung"]), p_random)
    assert (row["zuordnungen"], row["n"], row["einheit"]) == (count, n, "relativ")


def test_the_share_sensitivity_is_in_share_points(table: dict[str, dict[str, Any]]) -> None:
    row = table["H17.1/S1.4"]
    assert round(100 * float(row["effekt"]), 2) == -2.83
    assert round(float(row["p"]), 4) == 0.9941 and row["p_randomisierung"] == 1.0
    assert row["einheit"] == "anteil"


@pytest.mark.parametrize(
    ("key", "delta", "effect", "p"),
    [
        ("H17.2", 0.6047, 83.1, 1 / 27720),
        ("H17.2/S2.1", -0.1383, -12.9, 0.24592),  # zweiseitig, wie vorab festgelegt
        ("H17.2/S2.2", 0.2765, 31.9, 1 / 27720),
    ],
)
def test_the_budget_month(
    table: dict[str, dict[str, Any]], key: str, delta: float, effect: float, p: float
) -> None:
    row = table[key]
    assert round(float(row["statistik"]), 4) == delta
    assert _percent(row["effekt"]) == effect
    assert math.isclose(float(row["p"]), p, abs_tol=5e-6)
    assert (row["zuordnungen"], row["n"]) == (27720, 12)


@pytest.mark.parametrize(
    ("key", "shares", "jt", "p"),
    [
        ("H17.3", (5.98, 3.16, 3.47), 7.0, 0.98665),
        ("H17.3/S3.1", (4.66, 2.32, 2.50), 7.0, 0.98665),
        ("H17.3/S3.2", (7.10, 10.54, 4.16), 21.0, 0.50000),
        ("H17.3/S3.4/politisch", (6.29, 3.83, 4.35), None, 0.95527),
        ("H17.3/S3.4/verwaltung", (5.66, 2.58, 2.71), None, 0.99531),
    ],
)
def test_the_federal_vocabulary(
    table: dict[str, dict[str, Any]],
    key: str,
    shares: tuple[float, ...],
    jt: float | None,
    p: float,
) -> None:
    row = table[key]
    assert tuple(round(100 * s, 2) for s in row["anteile"]) == shares
    if jt is not None:
        assert row["statistik"] == jt
    assert round(float(row["p"]), 5) == p
    assert (row["zuordnungen"], row["n"]) == (5544, 12)


def test_each_category_over_the_periods(table: dict[str, dict[str, Any]]) -> None:
    """S3.3, explorativ: steigend sind nur Klima und Energie und Wohnen und Boden (je p = 0,008)."""
    p = {
        key.rsplit("/", 1)[1]: round(float(r["p"]), 5)
        for key, r in table.items()
        if "/S3.3/" in key
    }
    assert p == {
        "migration_asyl": 0.99874,
        "klima_energie": 0.00812,
        "sozialstaat": 0.93741,
        "gendern": 0.40224,
        "bundesverkehr": 0.32684,
        "wohnen_bund": 0.00812,
        "cannabis": 0.88763,
        "corona": 0.03950,
        "ukraine_krieg": 0.04365,
        "energiekrise": 0.02652,
    }
    assert {table[f"H17.3/S3.3/{k}"]["rolle"] for k in p} == {"explorativ"}


def test_holm_decides_the_family_as_in_paragraph_eight_five(
    table: dict[str, dict[str, Any]],
) -> None:
    words = {k: (r["ergebnis"], r["p_holm"]) for k, r in table.items() if r["rolle"] == "Haupttest"}
    assert words["H17.1"] == ("nicht bestätigt", 1.0)
    assert words["H17.2"][0] == "bestätigt"
    assert math.isclose(float(words["H17.2"][1]), 3 / 27720)
    # H17.3 ist gültig, weil das Lexikon validiert ist, und nicht bestätigt
    assert words["H17.3"] == ("nicht bestätigt", 1.0)
    assert {r["festgelegt"] for r in table.values()} == {"9c7b3d6"}


# --- Spannen auf dem Rohtext der Hauptperiode (Paket) -----------------------------------------------


def test_every_span_of_the_main_period_is_a_hit_in_the_raw_text(
    periods: dict[str, Period],
) -> None:
    main = periods["duesseldorf"]
    store = RawTextStore(main.layout.raw_texts)
    assert len(store) == 19091  # das Rohtextpaket der Hauptperiode
    spans, lengths, without = vocabulary_spans(
        main.corpus, store.rows, main.settings.search.text_split_marker, LEXICON
    )
    spans = sort_spans(spans)
    check_spans(spans, lengths)
    patterns = {c.id: re.compile(c.pattern) for c in LEXICON.categories}
    wrong = [
        (row["id"], row["value"])
        for row in spans.iter_rows(named=True)
        if not patterns[row["norm"]].fullmatch(
            row["value"].replace("\n", "").replace("\f", "").lower()
        )
    ]
    assert wrong == []
    # nur das verschlüsselte 00403713.pdf hat keinen Rohtext (Punkt 73)
    assert without <= 1
    assert spans.height > 6000


# --- Stufe 3: die Zahlen der Unterseite zeit.html (Messdokument § 3 und § 4.1) ---------------------


def _page_settings(profile: str) -> Settings:
    settings = load_settings(profile=profile, cwd=NOWHERE)
    return settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": REPO / "validierung"})}
    )


@pytest.fixture(scope="module")
def pages(periods: dict[str, Period]) -> dict[str, Any]:
    """Das Modell von ``zeit.html`` je Periode, aus denselben Tabellen wie oben; die Hauptperiode mit
    den Tests über alle drei, wie im Profil ``duesseldorf-vergleich`` auf Pages."""
    from georep.report.cycles import TimeInputs, build_time, read_check

    rules = cycle_rules(load_settings(profile="duesseldorf-vergleich", cwd=NOWHERE))
    frame = cycle_hypotheses([periods[p].data for p in PROFILES], rules, LEXICON)
    found = {}
    for profile, shown in (
        ("duesseldorf-2014", "duesseldorf-2014"),
        ("duesseldorf", "duesseldorf-vergleich"),
        ("duesseldorf-2025", "duesseldorf-2025"),
    ):
        period = periods[profile]
        settings = _page_settings(shown)
        bodies = pl.read_parquet(
            period.layout.papers_bodies, columns=["id", "gremium", "gremium_art", "stadtbezirk"]
        )
        documents = (
            period.data.documents.select("id", "date", "mit_text", "urheber_art", "kategorien")
            .join(bodies, on="id", how="left")
            .sort("id")
        )
        inputs = TimeInputs(
            months=period.data.months,
            budget=period.data.budget,
            documents=documents,
            hypotheses=frame if settings.cycles.periods else None,
            feeds=None,
        )
        found[profile] = (
            build_time(inputs, settings, LEXICON, read_check(settings, LEXICON)),
            settings,
        )
    return found


def _shares(model: Any, key: str) -> list[float]:
    row = next(r for r in model.vocabulary.rows if r.key == key)
    return [round(100 * c.share, 2) for c in row.cells]


@pytest.mark.parametrize(
    ("profile", "fraction", "budget", "structure", "every"),
    [
        (
            "duesseldorf-2014",
            [1582, 1486, 1351, 1358, 1401, 1380],
            [11] * 6,
            [7.30, 9.37, 6.76, 5.35, 4.37, 2.97],
            [7.33, 9.45, 6.76, 5.38, 4.37, 9.18],
        ),
        (
            "duesseldorf",
            [1653, 1634, 1644, 1442, 1434],
            [2, 12, 12, 12, 12],
            [2.79, 3.35, 3.97, 3.49, 2.22],
            [18.09, 13.57, 9.86, 5.93, 4.06],
        ),
        ("duesseldorf-2025", [1499], [3], [3.47], [4.16]),
    ],
)
def test_the_page_shows_the_years_and_the_vocabulary_of_paragraph_three(
    pages: dict[str, Any],
    profile: str,
    fraction: list[int],
    budget: list[int],
    structure: list[float],
    every: list[float],
) -> None:
    """§ 3.1 bis § 3.3: Fraktionsdokumente und Haushaltsmonat je Wahljahr, Anteile je Wahljahr."""
    model, _ = pages[profile]
    assert [y.fraction for y in model.rhythm.years] == fraction
    assert [y.budget_month for y in model.rhythm.years] == budget
    assert _shares(model, "struktur") == structure
    assert _shares(model, "alle") == every  # S3.2, mit den Ereignissen


def test_the_pre_election_years_against_the_middle_years(pages: dict[str, Any]) -> None:
    """§ 3.1, S1.6: 2020 1 380 gegen 1 399,0 (Rang 3 von 5), 2025 1 434 gegen 1 573,3 (Rang 4 von 4)."""
    old = pages["duesseldorf-2014"][0].rhythm.notes
    main = pages["duesseldorf"][0].rhythm.notes
    assert [(n.fraction, round(n.middle_mean, 1), n.rank, n.of) for n in old] == [
        (1380, 1399.0, 3, 5)
    ]
    assert [(n.fraction, round(n.middle_mean, 1), n.rank, n.of) for n in main] == [
        (1434, 1573.3, 4, 4)
    ]
    assert pages["duesseldorf-2025"][0].rhythm.notes == ()


def test_the_page_shows_the_family_with_its_words(pages: dict[str, Any]) -> None:
    model, _ = pages["duesseldorf"]
    words = {h.key: (h.result, h.p_label, h.p_holm_label) for h in model.tests.main}
    assert words == {
        "H17.1": ("nicht bestätigt", "0,847", "1,000"),
        "H17.2": ("bestätigt", "0,000036", "0,00011"),
        "H17.3": ("nicht bestätigt", "0,987", "1,000"),
    }
    h171 = next(h for h in model.tests.main if h.key == "H17.1")
    assert h171.effect.startswith("-4,9 % (90 %: -12,9 bis +3,8 %)")
    h173 = next(h for h in model.tests.main if h.key == "H17.3")
    assert h173.effect.startswith("5,98 / 3,16 / 3,47 % je Periode")
    for profile in ("duesseldorf-2014", "duesseldorf-2025"):
        other = pages[profile][0]
        assert other.tests is None and other.elsewhere is not None
        assert not other.elsewhere.computed_here


def test_the_event_traces_of_paragraph_three_five(pages: dict[str, Any]) -> None:
    """§ 3.5, explorativ: Corona im Juli 2021 bei 33 von 119, der Krieg im März 2022 bei 24 von 413."""
    events = {e.key: e for e in pages["duesseldorf"][0].events}
    corona, war = events["corona"], events["ukraine_krieg"]
    assert (corona.peak_month, corona.peak_hits, corona.peak_documents) == (
        dt.date(2021, 7, 1),
        33,
        119,
    )
    assert (war.peak_month, war.peak_hits, war.peak_documents) == (dt.date(2022, 3, 1), 24, 413)


def test_each_page_stays_under_its_budget(pages: dict[str, Any]) -> None:
    from georep.enrich.cycles import PAGE
    from georep.layout import Layout
    from georep.report.cycles import page_data, time_links
    from georep.report.pages import page_frame, render_page

    now = dt.datetime(2026, 11, 27, 12, tzinfo=dt.UTC)
    for profile, (model, settings) in pages.items():
        page = render_page(
            page_frame(settings, now=now, commit=None),
            PAGE,
            page_data(model, settings),
            time_links(Layout(NOWHERE, NOWHERE, NOWHERE), settings),
        )
        assert len(page.encode("utf-8")) < 500_000, profile
