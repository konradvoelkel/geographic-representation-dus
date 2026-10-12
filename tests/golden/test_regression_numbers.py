"""Tabelle 5 der Arbeit, eingefroren: lineare Regression Trefferquote -> Wahlbeteiligung in Prozent.

Gerechnet wie das Notebook (``scipy.stats.linregress``), gelesen mit Polars. Die Toleranzen
entsprechen der Rundung in der Arbeit.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from scipy.stats import linregress

from georep.analysis.regression import regress
from georep.layout import Layout


def _xy(path: Path, exclude: frozenset[int] = frozenset()) -> tuple[list[float], list[float]]:
    df = pl.read_csv(path, infer_schema_length=None).filter(
        ~pl.col("wahlkreis_id").is_in(list(exclude))
    )
    return df["trefferquote"].to_list(), (df["wahlbeteiligung"] * 100).to_list()


def test_all_41_districts(reference_root: Path) -> None:
    x, y = _xy(reference_root / "processed" / "wahlbezirke_auswertung.csv")
    assert len(x) == 41
    r = linregress(x, y)
    assert r.slope == pytest.approx(62.1337, abs=5e-4)
    assert r.intercept == pytest.approx(49.1993, abs=5e-4)
    assert r.rvalue == pytest.approx(0.16125, abs=5e-5)
    assert r.pvalue == pytest.approx(0.31385, abs=5e-5)
    assert r.rvalue**2 == pytest.approx(0.026001, abs=5e-6)


def test_without_outliers_1_and_10(reference_root: Path) -> None:
    """Tabelle 5 nennt 216,4 / 40,45 / 0,34 / 0,03422 / 0,1156; die committeten Daten ergeben die
    Werte unten (Neuberechnung 2026-10-10). Die Spalte mit allen Daten stimmt exakt, diese nicht:
    vermutlich ein früherer Datenstand der Arbeit. Eingefroren wird, was die Daten heute liefern."""
    x, y = _xy(
        reference_root / "processed" / "wahlbezirke_auswertung.csv", exclude=frozenset({1, 10})
    )
    assert len(x) == 39
    r = linregress(x, y)
    assert r.slope == pytest.approx(215.3341, abs=5e-4)
    assert r.intercept == pytest.approx(40.5046, abs=5e-4)
    assert r.rvalue == pytest.approx(0.338461, abs=5e-6)
    assert r.pvalue == pytest.approx(0.035069, abs=5e-6)
    assert r.rvalue**2 == pytest.approx(0.114556, abs=5e-6)


# --- Option 06: Die Einheitsvariante der Gewichtung ist Tabelle 5 ------------------------------


def test_unit_variant_regresses_like_the_unweighted_rate(mini_run: Layout) -> None:
    """Dieselbe Regression über ``trefferquote_gewichtet`` der Variante einheit wie über ``trefferquote``.

    Die Zahlen der Referenz prüft der slow-Test in ``test_pipeline.py``; hier geht es darum, dass
    die lange Tabelle dieselbe Kennzahl trägt, nicht eine ähnliche.
    """
    results = pl.read_parquet(mini_run.results)
    unit = (
        pl.read_parquet(mini_run.weighted)
        .filter(pl.col("variante") == "einheit")
        .join(
            results.select("wahlkreis_id", "wahlbeteiligung", "anzahl_treffer"), on="wahlkreis_id"
        )
    )
    assert unit.height == results.height
    assert (
        unit.get_column("anzahl_treffer_gewichtet")
        == unit.get_column("anzahl_treffer").cast(pl.Float64)
    ).all()
    weighted = regress(unit, x="trefferquote_gewichtet")
    plain = regress(results)
    assert (weighted.n, weighted.slope, weighted.intercept, weighted.r, weighted.p) == (
        plain.n,
        plain.slope,
        plain.intercept,
        plain.r,
        plain.p,
    )
