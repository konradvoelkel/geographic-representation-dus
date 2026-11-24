"""Vorhaben 15 über die drei Düsseldorfer Perioden und die zweite Stadt, gegen die Messung.

Zwei Arten von Zahlen. **Die Validierung als Regressionstest**: an den Labels zweier KI-Kodierer
(``validierung/15-funktion/labels.csv``, 150 Dokumente) muss κ der Funktion für Variante B bei
0,905 bleiben (Kriterium ≥ 0,7), die Präzision der Fraktionen bei 119/119. Ein Umbau der Regeln,
der eine dieser Zahlen senkt, ist kein Refactoring (Messdokument ``docs/plans/15-funktion.md``,
§ 4.1 und § 6). **Die Abdeckung**: die Tabelle der Funktionen je Periode (§ 3.2), die gemeinsamen
Dokumente (§ 3.8), das Maß K3 (§ 3.11), und dass jede Dokumentart jeder Periode eine Zeile in den
Tabellen hat (Synergien 2026-11, § 1).

Die Korpora entstehen wie in ``georep run``: ``bootstrap`` aus den Datenpaketen im Repo, dann die
Schritte ``corpus`` und ``bodies``, die Urheber aus Option 04.
"""

from __future__ import annotations

import csv
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest

from georep.analysis.cosponsors import CosponsorRules, classify_cosponsors
from georep.analysis.functions import FunctionRules, classify_functions, function_figures
from georep.analysis.parties import classify_originators
from georep.analysis.practice import RATIO, observed_expected
from georep.bootstrap import bootstrap_from_settings
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.settings import Settings, load_settings
from georep.validation.measures import cohen_kappa

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / "validierung" / "15-funktion"
NOWHERE = Path("/nonexistent")
# Profil -> Schlüssel der Periode im Codebuch (``[fraktionen]``)
PERIODS = {"duesseldorf-2014": "2014-2020", "duesseldorf": "2020-2025", "duesseldorf-2025": "2025-"}


@dataclass(frozen=True)
class Period:
    settings: Settings
    documents: pl.DataFrame  # Korpus, Urheber, Gremium, Funktion A und B, Antragsteller


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
    a = FunctionRules.from_settings(settings.functions.model_copy(update={"variant": "A"}))
    b = FunctionRules.from_settings(settings.functions)
    cosponsors = classify_cosponsors(
        corpus, originators, bodies, CosponsorRules.from_settings(settings)
    )
    documents = (
        corpus.select("id", "date", "paper_type")
        .join(originators.select("id", "urheber_art", "parteien"), on="id")
        .join(bodies.select("id", "gremium", "gremium_art"), on="id", how="left")
        .join(
            classify_functions(corpus, originators, a).select(
                "id", pl.col("funktion").alias("funktion_a")
            ),
            on="id",
        )
        .join(
            classify_functions(corpus, originators, b).select("id", "funktion", "instrument"),
            on="id",
        )
        .join(cosponsors, on="id")
        .sort("id")
    )
    return Period(settings, documents)


@pytest.fixture(scope="module")
def periods(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Period]:
    root = tmp_path_factory.mktemp("functions")
    return {p: _period(p, root) for p in (*PERIODS, "moenchengladbach")}


# --- Abdeckung (§ 3.2, § 3.3) ---------------------------------------------------------------------
# Variante B je Periode: Kontrolle, Information, Initiative, Symbol, Vollzug, Rest. Variante A in
# § 3.2; B verschiebt 186 Berichtsanträge in die Kontrolle (77, 89, 20) und 71 Erklärungen ins
# Symbol (32, 37, 2), in Mönchengladbach 27 Berichtsanträge.
COVERAGE_B = {
    "duesseldorf-2014": (5_395, 3_790, 6_049, 55, 5_695, 1_231),
    "duesseldorf": (4_039, 4_203, 5_084, 52, 5_730, 0),
    "duesseldorf-2025": (1_096, 791, 972, 3, 1_233, 0),
    "moenchengladbach": (27, 1_018, 585, 5, 1_260, 0),
}


@pytest.mark.parametrize("profile", list(COVERAGE_B))
def test_the_functions_of_each_period_are_those_of_the_measurement(
    periods: dict[str, Period], profile: str
) -> None:
    figures = function_figures(periods[profile].documents)
    assert tuple(figures.values()) == COVERAGE_B[profile]


@pytest.mark.parametrize("profile", list(COVERAGE_B))
def test_every_type_of_every_period_has_a_row_in_the_tables(
    periods: dict[str, Period], profile: str
) -> None:
    """Eine neue Dokumentart soll auffallen, nicht still in die Restklasse fallen."""
    unknown = periods[profile].documents.filter(pl.col("instrument") == "art_unbekannt")
    assert unknown.height == 0, sorted(set(unknown.get_column("paper_type").to_list()))


# --- Gemeinsame Dokumente (§ 3.8) -----------------------------------------------------------------
JOINT = {"duesseldorf-2014": 1_397, "duesseldorf": 1_202, "duesseldorf-2025": 204}


@pytest.mark.parametrize("profile", list(JOINT))
def test_the_joint_documents_are_those_of_the_measurement(
    periods: dict[str, Period], profile: str
) -> None:
    documents = periods[profile].documents
    assert int(documents.get_column("gemeinsam").sum()) == JOINT[profile]
    afd = documents.filter(pl.col("gemeinsam") & pl.col("fraktionen").list.contains("AfD"))
    assert afd.height == 0  # die AfD stellt in keiner Periode ein Dokument gemeinsam (§ 3.10)


# --- K3 (§ 3.11) -----------------------------------------------------------------------------------
# Initiativen mit Beteiligung der Opposition in Rat und Ausschüssen, davon mit einer Fraktion der
# Mehrheit; Variante B. Die Mehrheit gilt je Wahlperiode des Rates ab dem 1. November nach der Wahl
# (Profil, [majorities]), nicht je Datensatz wie in der Messung; das verschiebt die Dokumente
# zwischen Wahl und 31. Oktober 2020 zur Ampel.
# Messung (Variante B): 49 / 653, 43 / 1 336, 0 / 312.
K3 = {"duesseldorf-2014": (49, 653), "duesseldorf": (41, 1_333), "duesseldorf-2025": (0, 312)}


@pytest.mark.parametrize("profile", list(K3))
def test_k3_on_the_city_level(periods: dict[str, Period], profile: str) -> None:
    initiatives = periods[profile].documents.filter(
        pl.col("funktion").is_in(["initiative", "symbol"])
    )
    counts = dict(initiatives.group_by("lager").len().iter_rows())
    opposition = sum(
        counts.get(c, 0) for c in ("allein_opposition", "gemeinsam_opposition", "ueber_grenze")
    )
    assert (counts.get("ueber_grenze", 0), opposition) == K3[profile]


# --- Kontrolle je Fraktion gegen die Praxis der Gremien (§ 3.7) ---------------------------------
# Beobachtet durch erwartet, Fraktionsdokumente der Funktionen Kontrolle, Initiative und Symbol
# (Variante A wie in der Messung), Schicht das Gremium. 2020-2025 und ab 2025 sind es die Zahlen
# der Messung. 2014-2020 nicht: 105 Fraktionsdokumente haben dort kein Gremium, und das Messskript
# gab ihnen beim Join ohne null-Schlüssel keine Erwartung (CDU 0,99, SPD 0,79, Tierschutz/FW 1,53);
# observed_expected führt sie als eigene Schicht.
PRACTICE = {
    "duesseldorf-2014": {"CDU": 0.98, "SPD": 0.78, "GRUENE": 0.82, "FDP": 0.6, "T_FW": 1.45},
    "duesseldorf": {"CDU": 0.74, "GRUENE": 0.86, "SPD+VOLT": 1.02, "T_FW": 1.67, "AfD": 1.75},
    "duesseldorf-2025": {"CDU": 0.66, "GRUENE": 0.95, "AfD": 1.2, "T_FW+PARTEI": 1.06},
}


@pytest.mark.parametrize("profile", list(PRACTICE))
def test_control_against_the_practice_of_the_bodies(
    periods: dict[str, Period], profile: str
) -> None:
    documents = (
        periods[profile]
        .documents.filter(
            (pl.col("urheber_art") == "Fraktion")
            & pl.col("funktion_a").is_in(["kontrolle", "initiative", "symbol"])
        )
        .with_columns((pl.col("funktion_a") == "kontrolle").alias("kontrolle"))
    )
    found = observed_expected(
        documents, unit="fraktionen", outcome="kontrolle", strata=("gremium",)
    )
    ratios = {row["fraktionen"]: round(row[RATIO], 2) for row in found.iter_rows(named=True)}
    assert {k: ratios[k] for k in PRACTICE[profile]} == PRACTICE[profile]


# --- Validierung als Regressionstest (§ 4.1) ----------------------------------------------------
def _labels() -> dict[str, dict[str, object]]:
    found: dict[str, dict[str, object]] = {}
    with (VALIDATION / "labels.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            found.setdefault(row["aufgabe"], {})[row["frage"]] = json.loads(row["label"])
    return found


def _codebook_fractions() -> dict[str, list[str]]:
    book = tomllib.loads((VALIDATION / "codebuch.toml").read_text(encoding="utf-8"))
    return {period: [f["id"] for f in rows] for period, rows in book["fraktionen"].items()}


def _option(fraction: str, options: list[str]) -> str:
    """Die Fraktion als Option des Codebuchs: „SPD/Volt (auch nur SPD oder nur Volt genannt)"."""
    if fraction in options:
        return fraction
    parties = set(fraction.split("+"))
    return next((o for o in options if parties <= set(o.split("+"))), fraction)


@dataclass(frozen=True)
class Sample:
    labels: dict[str, dict[str, object]]
    rows: dict[str, dict[str, object]]  # Regelwerk je Dokument, mit Periode des Codebuchs
    fractions: dict[str, list[str]]  # Optionen des Codebuchs je Periode


@pytest.fixture(scope="module")
def sample(periods: dict[str, Period]) -> Sample:
    labels = _labels()
    rows: dict[str, dict[str, object]] = {}
    for profile, key in PERIODS.items():
        found = periods[profile].documents.filter(pl.col("id").is_in(list(labels)))
        for row in found.iter_rows(named=True):
            rows[row["id"]] = row | {"periode": key}
    with (VALIDATION / "stichprobe.csv").open(encoding="utf-8") as fh:
        assert {r["id"] for r in csv.DictReader(fh)} == set(labels) == set(rows)
    return Sample(labels, rows, _codebook_fractions())


def test_kappa_of_the_function_stays_where_the_coding_put_it(sample: Sample) -> None:
    """Basis nach Frage 17: das Regelwerk gibt eine Funktion, das Label ist nicht „unklar"."""
    basis = sorted(
        i
        for i, row in sample.rows.items()
        if row["funktion"] != "rest" and sample.labels[i]["funktion"] != "unklar"
    )
    assert len(basis) == 135
    for column, hits, kappa in (("funktion", 125, 0.905), ("funktion_a", 117, 0.829)):
        rule = [str(sample.rows[i][column]) for i in basis]
        label = [str(sample.labels[i]["funktion"]) for i in basis]
        assert sum(r == lab for r, lab in zip(rule, label, strict=True)) == hits
        found = cohen_kappa(rule, label)
        assert found is not None and round(found, 3) == kappa
        assert found >= 0.7  # das Kriterium (Briefing)


def test_the_cosponsors_are_right_wherever_they_name_a_fraction(sample: Sample) -> None:
    """Präzision 119/119, Recall 119/138, gemeinsam 26 von 30 mit genau denselben Fraktionen."""
    tp = fp = fn = joint = exact = 0
    for i, row in sample.rows.items():
        options = sample.fractions[str(row["periode"])]
        rule = (
            {_option(f, options) for f in row["fraktionen"]}  # type: ignore[attr-defined]
            if row["urheber_art"] == "Fraktion"
            else set()
        )
        label = {x for x in sample.labels[i]["urheber"] if x in options}  # type: ignore[attr-defined]
        tp += len(rule & label)
        fp += len(rule - label)
        fn += len(label - rule)
        if len(label) >= 2:
            joint += 1
            exact += rule == label
    assert (tp, tp + fp, tp + fn) == (119, 119, 138)
    assert (exact, joint) == (26, 30)
