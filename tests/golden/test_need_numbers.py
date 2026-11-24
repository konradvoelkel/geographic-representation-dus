"""Vorhaben 22 auf der Hauptperiode: die Zahlen des Messdokuments aus dem Paket nachgerechnet.

``docs/plans/22-bedarf.md``, § 3.2 bis § 3.5: der Schritt ``need`` rechnet aus dem Paket
``snapshots/duesseldorf-bedarf`` und dem Datensatz der Arbeit (mit dem Textpaket, Punkt 68) dieselben
Zahlen wie das Messskript. Ein Umbau, der eine davon bewegt, ist kein Refactoring; die drei Urteile
über H1 bis H3 sind vorab festgelegt (Commit 67f7250) und dürfen sich nur mit den Daten ändern.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep.bootstrap import bootstrap_from_settings
from georep.enrich.need import need_files
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.settings import load_settings

pytestmark = pytest.mark.slow

NOWHERE = Path("/nonexistent")
STEPS = [
    "shapes",
    "voters",
    "context",
    "streets",
    "pois",
    "dictionary",
    "corpus",
    "bodies",
    "committees",
    "index",
    "results",
    "need",
]


@pytest.fixture(scope="module")
def need_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[pl.DataFrame, pl.DataFrame]:
    root = tmp_path_factory.mktemp("need_run")
    settings = load_settings(profile="duesseldorf", cwd=NOWHERE).model_copy(
        update={"data_root": root / "data", "cache_root": root / "cache"}
    )
    layout = Layout.from_settings(settings)
    bootstrap_from_settings(layout, settings)
    outcomes = run_pipeline(build_steps(settings, layout), settings, STEPS)
    assert all(o.status == "ausgeführt" for o in outcomes), [o.line() for o in outcomes]
    files = need_files(layout)
    return pl.read_parquet(files.table), pl.read_parquet(files.tests)


def test_the_need_table_has_the_totals_of_the_measurement(
    need_run: tuple[pl.DataFrame, pl.DataFrame],
) -> None:
    table, _ = need_run
    assert table.height == 41
    assert float(table.get_column("einwohner_zensus").sum()) == 611_134
    assert float(table.get_column("unfaelle").sum()) == pytest.approx(
        11_499
    )  # 11 501, 2 ohne Wahlbezirk
    assert float(table.get_column("unfaelle_geteilt").sum()) == pytest.approx(3_170)
    assert (
        float(table.get_column("schulen").sum()) == 88
        and float(table.get_column("schulen_mit_index").sum()) == 87
    )
    assert int(table.get_column("dok_verkehr").sum()) > 0
    # Spannweiten aus § 3.2 und § 3.3
    assert table.get_column("einwohner_zensus").min() == 12_039
    assert table.get_column("einwohner_zensus").max() == 18_317
    assert table.get_column("unfaelle_je_1000").max() == pytest.approx(58.4, abs=0.05)
    assert table.get_column("miete_qm").median() == pytest.approx(9.21, abs=0.005)
    assert table.get_column("anteil_verkehr").median() == pytest.approx(0.207, abs=0.0005)


def test_the_three_hypotheses_come_out_as_measured(
    need_run: tuple[pl.DataFrame, pl.DataFrame],
) -> None:
    _, tests = need_run
    main = {
        row["hypothese"]: row for row in tests.filter(pl.col("rechnung") == "haupttest").to_dicts()
    }
    assert list(main) == ["H1", "H2", "H3"]
    expected = {
        "H1": (0.343, 0.051, 0.593, 0.0143, 0.0429, "bestätigt"),
        "H2": (-0.336, -0.620, -0.031, 0.0346, 0.0692, "nicht bestätigt"),
        "H3": (-0.059, -0.408, 0.312, 0.6474, 0.6474, "nicht bestätigt"),
    }
    # § 8: H2 ist zweiseitig; p_Holm 0,0692 liegt über 0,05, also keine der beiden Richtungen
    readings = {
        "H1": "Aufmerksamkeit folgt dem Bedarf",
        "H2": "kein Zusammenhang nachweisbar",
        "H3": "kein Zusammenhang nachweisbar",
    }
    for name, (rho, low, high, p, p_holm, result) in expected.items():
        row = main[name]
        assert (row["wert"], row["ci_lo"], row["ci_hi"]) == pytest.approx(
            (rho, low, high), abs=5e-4
        )
        assert (row["p"], row["p_holm"]) == pytest.approx((p, p_holm), abs=5e-5)
        assert row["ergebnis"] == result and row["festgelegt"] == "67f7250" and row["n"] == 41
        assert row["deutung"] == readings[name]


def test_the_robustness_without_districts_1_and_10_comes_out_as_measured(
    need_run: tuple[pl.DataFrame, pl.DataFrame],
) -> None:
    """§ 3.4, Zeile „ohne Wahlbezirke 1 und 10 (n = 39)": 0,417, −0,411, −0,144.

    Die Liste steht seit Review 2026-11-24, N8, in der Hypothese des Profils (``robust_without``)
    und nicht mehr in ``analysis.exclude_districts``; die Zahlen bleiben.
    """
    _, tests = need_run
    rows = {
        row["hypothese"]: row
        for row in tests.filter(pl.col("rechnung") == "robustheit").to_dicts()
        if row["ohne"]
    }
    assert list(rows) == ["H1", "H2", "H3"]
    for name, rho in (("H1", 0.417), ("H2", -0.411), ("H3", -0.144)):
        assert rows[name]["ohne"] == [1, 10] and rows[name]["n"] == 39
        assert rows[name]["wert"] == pytest.approx(rho, abs=5e-4)


def test_the_explorative_rows_come_out_as_measured(
    need_run: tuple[pl.DataFrame, pl.DataFrame],
) -> None:
    _, tests = need_run
    values = {
        (row["hypothese"], row["rechnung"]): row["wert"]
        for row in tests.filter(pl.col("explorativ")).to_dicts()
        if row["hypothese"] is not None
    }
    assert values[("H1", "innerhalb")] == pytest.approx(-0.062, abs=5e-4)
    assert values[("H3", "innerhalb")] == pytest.approx(0.465, abs=5e-4)
    assert values[("H1", "moran_residuen")] == pytest.approx(0.341, abs=5e-4)
    assert values[("H2", "moran_residuen")] == pytest.approx(0.050, abs=5e-4)
    assert values[("H3", "moran_residuen")] == pytest.approx(0.262, abs=5e-4)
    pairs = {
        (row["bedarf"], row["aufmerksamkeit"]): row["wert"]
        for row in tests.filter(pl.col("rechnung") == "paar").to_dicts()
    }
    assert pairs[("hb_score", "sozialindex_schulen")] == pytest.approx(0.772, abs=5e-4)
    assert pairs[("hb_score", "wahlbeteiligung")] == pytest.approx(-0.941, abs=5e-4)
