"""Vorhaben 28 über die drei Düsseldorfer Perioden: Präzision gegen die Labels, Abweichungen von 26, H28.2.

Drei Arten von Zahlen, alle aus den Datenpaketen im Repo, wie Pages sie rechnet (``bootstrap``,
dann ``corpus``, ``bodies``, ``council_results`` und ``votes``; die Urheber aus Option 04 wie der
Schritt ``parties``, ohne Index und Wahlergebnis):

* **Die Validierung als Regressionstest** (Messdokument ``docs/plans/28-abstimmungen.md``, § 4.1):
  die gebaute Tabelle der Hauptperiode gegen ``validierung/28-abstimmungen/labels.csv`` ergibt A1 =
  90 von 92, gewichtet 0,982 (Wilson 0,928–0,995 bei n_eff 90,1), also ``RULE_CHECK``; jeder Punkt
  der Stichprobe steht in der Tabelle, und seine Form ist die Schicht, nach der er gezogen wurde.
* **Wortregel gegen den Wortschatz von 26** je Punkt (§ 10, Punkt 2): jede Abweichung gezählt und
  mit einem Beispiel genannt, nichts angeglichen.
* **H28.2** (§ 8.6) in der Hauptperiode und die Nebenrechnung R2 seit Dezember 2025; dazu die
  Beschlüsse je Periode, deren Abweichung von § 3.2 der Entscheidungseintrag erklärt.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest
from scipy import stats

from georep.analysis.parties import classify_originators, read_organizations
from georep.analysis.votes import (
    MAIN,
    R1,
    R2,
    R3,
    R4,
    Opposition,
    last_decisions,
    opposition_motions,
    outcome_mismatches,
)
from georep.bootstrap import bootstrap_from_settings
from georep.enrich.votes import vote_files
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import PARTIES_SCHEMA, build_steps, run_pipeline
from georep.report.votes import RULE_CHECK
from georep.settings import Settings, load_settings

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / "validierung" / "28-abstimmungen"
NOWHERE = Path("/nonexistent")
PROFILES = ("duesseldorf-2014", "duesseldorf", "duesseldorf-2025")
Z95 = 1.959964


@dataclass(frozen=True)
class Period:
    settings: Settings
    votes: pl.DataFrame
    bodies: pl.DataFrame
    tests: pl.DataFrame
    corpus: pl.DataFrame
    originators: pl.DataFrame


def _period(profile: str, root: Path) -> Period:
    settings = load_settings(profile=profile, cwd=NOWHERE).model_copy(
        update={"data_root": root / profile / "data", "cache_root": root / profile / "cache"}
    )
    layout = Layout.from_settings(settings)
    bootstrap_from_settings(layout, settings)
    steps = build_steps(settings, layout)
    done = run_pipeline(steps, settings, ["corpus", "bodies", "council_results"])
    assert all(o.status == "ausgeführt" for o in done), [o.line() for o in done]
    corpus = pl.read_parquet(
        layout.corpus, columns=["id", "paper_type", "name", "text", "originator_organization"]
    )
    originators = classify_originators(
        corpus, settings.originators, read_organizations(layout.organizations)
    )
    write_parquet(originators, layout.document_originators, schema_version=PARTIES_SCHEMA)
    (outcome,) = run_pipeline(steps, settings, ["votes"])
    assert outcome.status == "ausgeführt", outcome.line()
    files = vote_files(layout)
    return Period(
        settings,
        pl.read_parquet(files.votes),
        pl.read_parquet(files.bodies),
        pl.read_parquet(files.hypotheses),
        corpus.select("id", "paper_type"),
        originators,
    )


@pytest.fixture(scope="module")
def periods(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Period]:
    root = tmp_path_factory.mktemp("votes")
    return {p: _period(p, root) for p in PROFILES}


# --- A1 gegen die Labels (§ 4.1) ------------------------------------------------------------------
def _wilson(p: float, n: float) -> tuple[float, float]:
    """Wilson bei nicht ganzzahligem n, wie im Messskript (``wilson``)."""
    d = 1 + Z95 * Z95 / n
    c = (p + Z95 * Z95 / (2 * n)) / d
    h = Z95 * ((p * (1 - p) / n + Z95 * Z95 / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def test_die_wortregel_trifft_die_labels_wie_gemessen(periods: dict[str, Period]) -> None:
    votes = periods["duesseldorf"].votes.with_columns(
        pl.col("top").str.split("/").list.last().alias("key")
    )
    built = {row["key"]: row for row in votes.iter_rows(named=True)}
    labels: dict[str, dict[str, str]] = {}
    with (VALIDATION / "labels.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            labels.setdefault(row["id"], {})[row["frage"]] = row["label"]
    with (VALIDATION / "stichprobe.csv").open(encoding="utf-8") as fh:
        sample = list(csv.DictReader(fh))
    sizes = {row["schicht"]: int(row["schicht_n"]) for row in sample}
    drawn = Counter(row["schicht"] for row in sample)
    assert len(sample) == RULE_CHECK.units
    a1: list[tuple[str, bool]] = []
    for row in sample:
        mine = built[row["id"]]  # jeder Punkt der Stichprobe steht in der Tabelle
        assert mine["form"] == row["schicht"]  # gezogen nach der Form aus dem Eintrag
        label = labels[row["id"]]
        if mine["form"] in ("einstimmig", "mehrheitlich") and label["abschnitt"] == "ja":
            a1.append(
                (
                    row["schicht"],
                    (mine["ergebnis"], mine["form"]) == (label["ergebnis"], label["form"]),
                )
            )
    weights = [sizes[h] / drawn[h] for h, _ in a1]
    precision = sum(w for w, (_, ok) in zip(weights, a1, strict=True) if ok) / sum(weights)
    n_eff = sum(weights) ** 2 / sum(w * w for w in weights)
    low, high = _wilson(precision, n_eff)
    assert (sum(ok for _, ok in a1), len(a1)) == (RULE_CHECK.hits, RULE_CHECK.basis)
    assert round(precision, 3) == RULE_CHECK.level_a.precision
    assert (round(low, 3), round(high, 3)) == RULE_CHECK.level_a.interval
    assert round(n_eff, 1) == RULE_CHECK.n_eff


# --- Beschlüsse je Periode (§ 3.2 und Entscheidungseintrag) ---------------------------------------
# (Punkte, Beschlüsse, davon mit Form, Ratsbeschlüsse) aus dem Paket von 26: je Profil die Punkte
# zu den Dokumenten der Periode, auch nach ihrem Ende. Das Messskript zählte nach dem Datum der
# Sitzung (12 570, 10 856 und 1 633 in der Hauptperiode).
DECIDED = {
    "duesseldorf-2014": (28_092, 12_687, 11_685, 1_462),
    "duesseldorf": (25_439, 12_573, 10_863, 1_646),
    "duesseldorf-2025": (4_979, 2_513, 2_250, 348),
}


@pytest.mark.parametrize("profile", PROFILES)
def test_die_beschluesse_je_periode(periods: dict[str, Period], profile: str) -> None:
    bodies = periods[profile].bodies
    total = bodies.select(pl.col(c).sum() for c in bodies.columns[2:]).row(0, named=True)
    council = bodies.filter(pl.col("gremium_art") == "rat").row(0, named=True)
    assert (
        total["punkte"],
        total["beschluesse"],
        total["einstimmig"] + total["mehrheitlich"],
        council["beschluesse"],
    ) == DECIDED[profile]


def test_die_abdeckung_der_hauptperiode_bleibt_ueber_der_haelfte(
    periods: dict[str, Period],
) -> None:
    _, decided, with_form, _ = DECIDED["duesseldorf"]
    assert round(with_form / decided, 3) == RULE_CHECK.level_a.coverage


# --- Die Wortregel neben 26, je Punkt (§ 10, Punkt 2) ---------------------------------------------
MISMATCHES = {
    "duesseldorf-2014": {("passieren lassen", "angenommen", "erledigt"): 405},
    "duesseldorf": {
        ("passieren lassen", "angenommen", "erledigt"): 455,
        ("zurückgewiesen", "sonstiges", "abgelehnt"): 5,
    },
    "duesseldorf-2025": {
        ("passieren lassen", "angenommen", "erledigt"): 81,
        ("zurückgewiesen", "sonstiges", "abgelehnt"): 21,
    },
}


@pytest.mark.parametrize("profile", PROFILES)
def test_jede_abweichung_von_26_ist_gezaehlt(periods: dict[str, Period], profile: str) -> None:
    period = periods[profile]
    found = outcome_mismatches(period.votes, period.settings.outcomes.results)
    counts = Counter(found.select("result", "klasse_28", "klasse_26").rows())
    assert dict(counts) == MISMATCHES[profile]


# --- H28.2 (§ 8.6) --------------------------------------------------------------------------------
def test_h28_2_ist_in_der_hauptperiode_bestaetigt(periods: dict[str, Period]) -> None:
    tests = periods["duesseldorf"].tests
    main = tests.filter((pl.col("hypothese") == "H28.2") & (pl.col("rechnung") == MAIN)).row(
        0, named=True
    )
    p = stats.binomtest(41, 389, 0.25, alternative="less").pvalue
    assert (main["angenommen"], main["n"]) == (41, 389)  # n wie § 3.7
    assert main["p"] == pytest.approx(p)
    assert main["p_holm"] == pytest.approx(3 * p)
    assert (main["ergebnis"], main["entscheidung"]) == ("bestätigt", "bestätigt")
    side = {
        (row["rechnung"], row["partei"]): (row["angenommen"], row["n"])
        for row in tests.filter(pl.col("rechnung") != MAIN).iter_rows(named=True)
    }
    assert side == {
        (R1, None): (159, 446),
        (R3, None): (41, 481),
        (R4, "SPD"): (21, 84),
        (R4, "FDP"): (7, 57),
        (R4, "Die_Linke"): (9, 131),
        (R4, "T_FW"): (0, 66),
        (R4, "PARTEI"): (6, 57),
    }
    for hypothesis in ("H28.1", "H28.3"):
        row = tests.filter((pl.col("hypothese") == hypothesis) & (pl.col("rechnung") == MAIN)).row(
            0, named=True
        )
        assert (row["entscheidung"], row["grund"]) == ("nicht entscheidbar", "ebene_b_verworfen")


def test_kein_antrag_von_h28_2_hat_den_eintrag_passieren_lassen(periods: dict[str, Period]) -> None:
    """Der Wert, bei dem Wortregel und 26 verschieden lesen, entscheidet keinen Antrag von H28.2:
    die Zahl hängt nicht an der Abweichung."""
    period = periods["duesseldorf"]
    votes = period.settings.votes
    who = Opposition(
        frozenset({"CDU", "GRUENE"}),
        frozenset(votes.excluded_parties),
        votes.motion_type,
        votes.motion_not,
    )
    motions = opposition_motions(period.corpus, period.originators, who)
    units = last_decisions(
        period.votes,
        motions,
        ("rat",),
        ("angenommen", "abgelehnt"),
        dt.date(2021, 1, 1),
        dt.date(2025, 9, 14),
    )
    assert units.height == 389
    assert units.filter(pl.col("result") == "passieren lassen").is_empty()
    assert dict(Counter(units.get_column("result").to_list())) == {
        "mehrheitlich abgelehnt": 347,
        "mehrheitlich beschlossen": 18,
        "abweichend beschlossen": 15,
        "einstimmig beschlossen": 8,
        "einstimmig abgelehnt": 1,
    }


def test_r2_seit_dezember_2025_und_ohne_pruefung_vor_2020(periods: dict[str, Period]) -> None:
    tests = periods["duesseldorf-2025"].tests
    assert tests.select("hypothese", "rechnung").rows() == [
        ("H28.1", R2),
        ("H28.2", R2),
        ("H28.3", R2),
    ]
    r2 = tests.filter(pl.col("hypothese") == "H28.2").row(0, named=True)
    assert (r2["angenommen"], r2["n"], r2["entscheidung"]) == (0, 47, None)
    assert periods["duesseldorf-2014"].tests.is_empty()
