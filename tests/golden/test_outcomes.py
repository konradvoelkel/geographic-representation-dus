"""Vorhaben 26 über die drei Düsseldorfer Perioden, gegen die Messung und gegen die Labels.

Zwei Arten von Zahlen. **Die Abdeckung**: die Klassen der Anträge je Periode und ihr Anteil mit
Ergebnis (Messdokument ``docs/plans/26-beschluesse.md``, § 3.4), die 155 Haushaltsanträge der
Ratssitzung vom 2021-02-05 ohne Eintrag (§ 3.3) und die Praxiszellen (§ 5). **Die Validierung als
Regressionstest**: an den Labels zweier KI-Kodierer (``validierung/26-beschluesse/labels.csv``,
150 Anträge) bleibt ``ergebnis`` bei 150 von 150 und der beantragte Prüfauftrag bei 57 von 65, mit
genau den acht Fehlern aus § 4.1 -- der Prüfauftrag ist nach Rückfall 1 eine beschreibende Spalte,
und eine bessere Regel wäre eine neue Messung, kein Refactoring.

Die Korpora entstehen wie in ``georep run``: ``bootstrap`` aus den Datenpaketen im Repo (darunter
``snapshots/duesseldorf-beschluesse``), dann ``corpus`` und ``bodies``; der Beratungsverlauf kommt
aus dem Paket, denn hier gibt es keinen Netzlauf. Die Rollen nimmt die Regel von Vorhaben 14.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest

from georep.analysis.cosponsors import CosponsorRules, classify_cosponsors
from georep.analysis.outcomes import (
    CLASSES,
    OutcomeRules,
    classify_outcomes,
    complete_outcomes,
    motion_success,
    period_key,
    practice_cells,
    progress,
    review_only,
)
from georep.analysis.parties import classify_originators
from georep.bootstrap import bootstrap_from_settings
from georep.enrich.outcomes import read_agenda
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.references import ReferenceRules, role_of
from georep.settings import Settings, load_settings

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / "validierung" / "26-beschluesse"
NOWHERE = Path("/nonexistent")
PROFILES = ("duesseldorf-2014", "duesseldorf", "duesseldorf-2025")
NO_FOLLOWUPS = pl.DataFrame(schema={"id": pl.String, "folgevorlage": pl.String})


@dataclass(frozen=True)
class Period:
    settings: Settings
    corpus: pl.DataFrame
    progress: pl.DataFrame
    outcomes: pl.DataFrame  # mit Rolle, Prüfauftrag und Praxiszelle; ohne Folgevorlage
    success: pl.DataFrame
    cosponsors: pl.DataFrame  # die Antragsteller von 15, gegen die der Erfolg gezählt wird
    bodies: pl.DataFrame


def _period(profile: str, root: Path) -> Period:
    settings = load_settings(profile=profile, cwd=NOWHERE).model_copy(
        update={"data_root": root / "data", "cache_root": root / "cache"}
    )
    layout = Layout.from_settings(settings)
    bootstrap_from_settings(layout, settings)
    done = run_pipeline(build_steps(settings, layout), settings, ["corpus", "bodies"])
    assert all(o.status == "ausgeführt" for o in done), [o.line() for o in done]
    corpus = pl.read_parquet(layout.corpus)
    ids = corpus.get_column("id").to_list()
    agenda, source = read_agenda(layout, ids)
    assert source == "Paket"
    rules = OutcomeRules.from_settings(settings.outcomes)
    verlauf = progress(agenda, dict(settings.bodies.organizations), rules.results)
    base = classify_outcomes(corpus.select("id", "date"), verlauf, rules.results)
    references = ReferenceRules.from_settings(settings.procedures)
    roles = pl.DataFrame(
        {
            "id": ids,
            "rolle": [
                role_of(t, n, references) for t, n in corpus.select("paper_type", "name").rows()
            ],
        }
    )
    review = pl.DataFrame(
        [
            (i, review_only(n, t, rules.review)[0])
            for i, n, t in corpus.select("id", "name", "text").rows()
        ],
        schema={"id": pl.String, "pruefauftrag": pl.Boolean},
        orient="row",
    )
    outcomes = complete_outcomes(base, roles, review, NO_FOLLOWUPS, rules)
    bodies = pl.read_parquet(layout.papers_bodies)
    cosponsors = classify_cosponsors(
        corpus,
        classify_originators(corpus, settings.originators),
        bodies,
        CosponsorRules.from_settings(settings),
    )
    success = motion_success(
        outcomes, cosponsors, bodies, period_key(settings.period.start, settings.period.end)
    )
    return Period(settings, corpus, verlauf, outcomes, success, cosponsors, bodies)


@pytest.fixture(scope="module")
def periods(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Period]:
    root = tmp_path_factory.mktemp("outcomes")
    return {p: _period(p, root) for p in PROFILES}


# --- Abdeckung (§ 3.3, § 3.4, § 5) ----------------------------------------------------------------
# Anträge je Periode in der Folge von ``CLASSES``: beschlossen, geaendert, abgelehnt, zurueckgezogen,
# erledigt, vertagt, offen, ohne_ergebnis -- die Tabelle aus § 3.4, auch für 2014 bis 2020 mit dem
# eigenen Abruf der Beratungen (Frage 9.10) unverändert.
MOTIONS = {
    "duesseldorf-2014": (1_696, 226, 421, 252, 354, 29, 12, 208),
    "duesseldorf": (2_585, 660, 1_028, 406, 88, 31, 12, 289),
    "duesseldorf-2025": (420, 96, 335, 57, 2, 5, 0, 13),
}
WITH_RESULT = {"duesseldorf-2014": 2_990, "duesseldorf": 4_810, "duesseldorf-2025": 915}


@pytest.mark.parametrize("profile", PROFILES)
def test_the_motions_of_each_period_have_the_classes_of_the_measurement(
    periods: dict[str, Period], profile: str
) -> None:
    motions = periods[profile].outcomes.filter(pl.col("dokument_rolle") == "antrag")
    counts = dict(motions.group_by("klasse").len().iter_rows())
    assert tuple(counts.get(name, 0) for name in CLASSES) == MOTIONS[profile]
    assert motions.filter(pl.col("klasse") != "ohne_ergebnis").height == WITH_RESULT[profile]


def test_the_main_period_has_a_result_for_more_than_eighty_percent(
    periods: dict[str, Period],
) -> None:
    """Das zweite Kriterium des Briefings: 94,3 % der Anträge der Hauptperiode (§ 5)."""
    motions = periods["duesseldorf"].outcomes.filter(pl.col("dokument_rolle") == "antrag")
    assert motions.height == 5_099
    assert WITH_RESULT["duesseldorf"] / motions.height == pytest.approx(0.9433, abs=1e-4)


def test_the_budget_meeting_of_2021_carries_no_entry(periods: dict[str, Period]) -> None:
    """155 der 289 Anträge ohne Ergebnis stehen in der Haushaltssitzung des Rates (§ 3.3)."""
    period = periods["duesseldorf"]
    without = period.outcomes.filter(
        (pl.col("dokument_rolle") == "antrag") & (pl.col("klasse") == "ohne_ergebnis")
    ).select("id")
    in_meeting = (
        period.progress.filter(
            (pl.col("gremium") == "RAT") & (pl.col("sitzung").dt.date() == dt.date(2021, 2, 5))
        )
        .join(without, on="id", how="semi")
        .get_column("id")
        .n_unique()
    )
    assert (without.height, in_meeting) == (289, 155)


def test_the_practice_cells_are_those_of_the_measurement(periods: dict[str, Period]) -> None:
    """BV9 2014 bis 2016 und der Rat 2016; 240 Anträge, deren Eintrag nicht trägt (§ 5)."""
    for profile, period in periods.items():
        rules = period.settings.outcomes
        cells = practice_cells(period.outcomes, rules.practice_share, rules.practice_min)
        flagged = period.outcomes.filter(pl.col("eintrag_tragfaehig").not_())
        if profile == "duesseldorf-2014":
            assert cells.select("gremium", "jahr").rows() == [
                ("BV9", 2014),
                ("BV9", 2015),
                ("BV9", 2016),
                ("RAT", 2016),
            ]
            assert flagged.height == 240
            assert set(flagged.get_column("klasse").to_list()) == {"erledigt"}
        else:
            assert cells.height == 0 and flagged.height == 0, profile


def test_the_requested_review_is_a_lower_bound_of_the_measurement(
    periods: dict[str, Period],
) -> None:
    """390, 739, 125 angenommene Anträge mit Prüfauftrag nach der Regel (§ 3.4, Untergrenzen)."""
    found = [
        int(period.outcomes.get_column("pruefauftrag_beantragt").sum())
        for period in periods.values()
    ]
    assert found == [390, 739, 125]


def test_success_counts_every_decided_motion_of_a_fraction_once_per_fraction(
    periods: dict[str, Period],
) -> None:
    """Review 2026-11-24, N2: ``n`` und ``angenommen`` je Gremienart und Fraktion, unabhängig gezählt.

    Jeder Antrag mit Sachentscheidung zählt einmal für jede Fraktion, die ihn stellt (auch wenn
    15 sie zweimal nennte), keiner ohne Fraktion; je Gremienart verteilt die Standardisierung
    genau die Annahmen, die es gab. „SPD" (vor dem 2020-11-01) und „SPD+VOLT" bleiben getrennt,
    wie 15 die Fraktionen liefert.
    """
    for profile, period in periods.items():
        decided = period.outcomes.filter(
            (pl.col("dokument_rolle") == "antrag")
            & pl.col("klasse").is_in(["beschlossen", "geaendert", "abgelehnt"])
        )
        counted = (
            decided.join(period.cosponsors.select("id", "fraktionen"), on="id")
            .join(period.bodies.select("id", "gremium_art"), on="id", how="left")
            .with_columns(pl.col("fraktionen").list.unique().alias("fraktion"))
            .explode("fraktion")
            .filter(pl.col("fraktion").is_not_null())
            .group_by("gremium_art", "fraktion")
            .agg(
                pl.len().cast(pl.Int32).alias("n"),
                pl.col("klasse")
                .is_in(["beschlossen", "geaendert"])
                .sum()
                .cast(pl.Int32)
                .alias("angenommen"),
            )
            .sort("gremium_art", "fraktion")
        )
        success = period.success.sort("gremium_art", "fraktion")
        assert success.select("gremium_art", "fraktion", "n", "angenommen").equals(counted), profile
        sums = success.group_by("gremium_art").agg(
            pl.col("angenommen").sum(), pl.col("erwartet").sum()
        )
        assert sums.get_column("angenommen").to_list() == pytest.approx(
            sums.get_column("erwartet").to_list()
        ), profile


# --- Validierung als Regressionstest (§ 4.1) ------------------------------------------------------

ERRORS = {  # Regel gegen Label beim Prüfauftrag, § 4.1
    "BV1/009/2022": ("pruefauftrag", "sachbeschluss"),
    "BV5/053/2024": ("sachbeschluss", "pruefauftrag"),
    "JURAT/032/2024": ("sachbeschluss", "pruefauftrag"),
    "BV5/077/2025": ("sachbeschluss", "pruefauftrag"),
    "BV1/111/2025": ("sachbeschluss", "pruefauftrag"),
    "176/ 85/2016": ("sachbeschluss", "pruefauftrag"),
    "BV8/190/2022": ("sachbeschluss", "pruefauftrag"),
    "BV1/188/2022": ("sachbeschluss", "pruefauftrag"),
}


def _labels() -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    with (VALIDATION / "labels.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            found.setdefault(row["id"], {})[row["frage"]] = row["label"]
    return found


def test_the_labels_of_the_coders_are_met(periods: dict[str, Period]) -> None:
    labels = _labels()
    assert len(labels) == 150
    outcomes = pl.concat([p.outcomes for p in periods.values()])
    references = pl.concat([p.corpus.select("id", "reference") for p in periods.values()])
    rows = {
        r["id"]: r
        for r in outcomes.join(references, on="id")
        .filter(pl.col("id").is_in(list(labels)))
        .iter_rows(named=True)
    }
    assert len(rows) == 150
    assert sum(rows[i]["klasse"] == labels[i]["ergebnis"] for i in labels) == 150
    asked = {i: lab["auftrag"] for i, lab in labels.items() if lab.get("auftrag")}
    assert len(asked) == 65
    rule = {
        i: "pruefauftrag" if rows[i]["pruefauftrag_beantragt"] else "sachbeschluss" for i in asked
    }
    wrong = {rows[i]["reference"]: (rule[i], asked[i]) for i in asked if rule[i] != asked[i]}
    assert wrong == ERRORS


def _wilson(k: float, n: float, z: float = 1.959964) -> tuple[float, float]:
    """Wilson bei nicht ganzzahligem n, wie im Messskript (``wilson``)."""
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5
    return (c - h) / d, (c + h) / d


def test_outcomes_check_follows_from_the_labels_and_the_progress(
    periods: dict[str, Period],
) -> None:
    """``OUTCOMES_CHECK`` (Stufe 3) aus Labels, Stichprobe und gebautem Verlauf, wie ``--auswertung``.

    Nach Rückfall 1 zählt ``ergebnis``: ungewichtet an den 150, gewichtet mit den Schichtgrößen
    (Wilson bei Kishs n_eff), und die Fälle, deren Folge mehr verlangte als das Nachschlagen eines
    Eintrags (mehrere Einträge, mehrere Beratungen, Verweisung, Empfehlung, Vertagung mit späterem
    Eintrag, maßgeblich nicht der letzte; § 4.1: 17 von 17).
    """
    from georep.report.outcomes import OUTCOMES_CHECK

    labels = _labels()
    with (VALIDATION / "stichprobe.csv").open(encoding="utf-8", newline="") as handle:
        sample = list(csv.DictReader(handle))
    outcomes = pl.concat([p.outcomes for p in periods.values()])
    klasse = dict(outcomes.select("id", "klasse").iter_rows())
    results = {k: v for p in periods.values() for k, v in p.settings.outcomes.results.items()}
    steps = (
        pl.concat([p.progress for p in periods.values()])
        .filter(pl.col("top").is_not_null())
        .with_columns(pl.col("ordnung").fill_null(0))
    )
    by_id = {
        doc: group.sort("sitzung", "ordnung", "top", nulls_last=False)
        for (doc,), group in steps.group_by("id")
    }
    units: list[tuple[str, int, bool]] = []
    hard = hard_ok = 0
    for row in sample:
        doc = row["id"]
        ok = klasse[doc] == labels[doc]["ergebnis"]
        units.append((row["schicht"], int(row["schicht_n"]), ok))
        mine = by_id.get(doc, steps.clear())
        entered = mine.filter(pl.col("result").is_not_null())
        values = entered.get_column("result").to_list()
        features = {
            len(values) >= 2,
            mine.get_column("beratung").n_unique() >= 2,
            "verwiesen" in values,
            any(v.startswith("Empfehlung") for v in values),
            any(v in ("vertagt", "zurückgestellt") for v in values) and len(values) >= 2,
            bool(values) and results[values[-1]][1] != klasse[doc],
        }
        if True in features:
            hard += 1
            hard_ok += ok
    rule = OUTCOMES_CHECK
    assert (sum(ok for *_, ok in units), len(units)) == (rule.hits, rule.basis)
    sizes = {stratum: size for stratum, size, _ in units}
    total = sum(sizes.values())
    estimate = sum(
        sizes[h]
        / total
        * sum(ok for s, _, ok in units if s == h)
        / sum(1 for s, *_ in units if s == h)
        for h in sizes
    )
    weights = [sizes[s] / sum(1 for t, *_ in units if t == s) for s, *_ in units]
    n_eff = sum(weights) ** 2 / sum(w * w for w in weights)
    low, high = _wilson(estimate * n_eff, n_eff)
    assert round(estimate, 3) == rule.weighted
    assert (round(low, 3), round(high, 3)) == rule.weighted_interval
    assert round(n_eff, 1) == rule.n_eff
    assert (hard_ok, hard) == (rule.hard_hits, rule.hard_basis)
