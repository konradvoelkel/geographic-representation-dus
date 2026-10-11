"""Tabelle 5 der Arbeit, eingefroren: lineare Regression Trefferquote -> Wahlbeteiligung in Prozent.

Gerechnet wie das Notebook (``scipy.stats.linregress``), gelesen mit Polars. Die Toleranzen
entsprechen der Rundung in der Arbeit.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from scipy.stats import linregress

from georep.analysis.ols import (
    fit_ols,
    model_frame,
    model_terms,
    models_table,
    partial_residuals,
)
from georep.analysis.regression import regress
from georep.crosswalk import area_shares, district_weights
from georep.geo import Area, read_areas, read_precincts
from georep.layout import Layout
from georep.prep.context import (
    aggregate_context,
    district_variables,
    precinct_table,
    read_context_table,
)
from georep.prep.voters import TURNOUT, read_results_csv
from georep.settings import RATE_TERM, Settings, load_settings


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


# --- Tabelle 6: Kontrollvariablen (Option 03) ---------------------------------------------------
#
# Am 2026-10-12 einmalig gegen statsmodels geprüft, in einer Wegwerf-Umgebung ohne Lockfile
# (``uv run --isolated --no-project --with statsmodels --with pandas python
# compare_statsmodels.py``; Skript im Scratchpad, Vorgehen in docs/decisions.md): statsmodels
# 0.15.0 stimmt mit ``georep.analysis.ols`` in Koeffizienten, Standardfehlern, t, p, VIF, R²,
# adjustiertem R², F und F-p aller drei Modelle bis auf eine relative Abweichung von 4,0e-14
# überein. statsmodels kommt nie ins Lockfile: es zieht pandas, und ``nox -s deps`` verbietet das.

# Modell -> (Koeffizient der Trefferquote, Standardfehler, p, R², adjustiertes R², größtes VIF)
TABLE_SIX = {
    "A": (62.13367, 60.89404, 0.313847, 0.0260015, 0.0010272, 1.0),
    "B": (41.32798, 26.88048, 0.132922, 0.8872203, 0.8746893, 4.521962),
    "C": (36.69988, 22.46108, 0.111500, 0.9278276, 0.9150913, 6.731920),
}
VIF_LIMIT = 10.0  # darüber ist ein Modell nicht mehr zu deuten (Plan 03, § 7)


@pytest.fixture(scope="module")
def controls(reference_root: Path, context_root: Path) -> tuple[pl.DataFrame, Settings]:
    """Die Modelltabelle der Referenz: Ergebnisse der Arbeit plus Kontrollvariablen."""
    settings = load_settings(cwd=Path("/nonexistent"))
    working = settings.geo.working_crs
    context = settings.context
    precincts = read_precincts(
        reference_root / "external" / "Stimmbezirke_2025.geojson", settings.columns, working
    )
    table = precinct_table(
        precincts,
        read_results_csv(
            reference_root / "external" / "Stimmbezirk_Wahlergebnis.csv", settings.columns.results
        ),
        settings.columns.results,
    )
    units = read_areas(context_root / context.files.units.file, context.units.key, working)
    weights = district_weights(
        table,
        area_shares([Area.of(p) for p in precincts], units, min_coverage=context.min_coverage),
    )
    values = read_context_table(context_root / context.files.table.file, context)
    results = pl.read_csv(
        reference_root / "processed" / "wahlbezirke_auswertung.csv", infer_schema_length=None
    )
    variables = aggregate_context(weights, values, context).join(
        district_variables(
            pl.read_csv(
                reference_root / "processed" / "wahlbezirke_waehler.csv", infer_schema_length=None
            ),
            context,
        ),
        on="wahlkreis_id",
    )
    return model_frame(results, variables), settings


@pytest.mark.slow
def test_table_six_matches_the_numbers_checked_against_statsmodels(
    controls: tuple[pl.DataFrame, Settings],
) -> None:
    frame, settings = controls
    assert frame.height == 41
    for model, terms in model_terms(settings.context).items():
        if model not in TABLE_SIX:
            continue
        fit = fit_ols(frame, TURNOUT, list(terms), y_scale=settings.context.models.y_scale)
        rate = fit.term(RATE_TERM)
        coefficient, stderr, p, r2, r2_adj, vif = TABLE_SIX[model]
        assert rate.coefficient == pytest.approx(coefficient, abs=5e-5)
        assert rate.stderr == pytest.approx(stderr, abs=5e-5)
        assert rate.p == pytest.approx(p, abs=5e-6)
        assert fit.r2 == pytest.approx(r2, abs=5e-7)
        assert fit.r2_adj == pytest.approx(r2_adj, abs=5e-7)
        assert max(t.vif or 0.0 for t in fit.terms) == pytest.approx(vif, abs=5e-6)


@pytest.mark.slow
def test_model_a_is_the_regression_of_table_five(controls: tuple[pl.DataFrame, Settings]) -> None:
    """Modell A ist Tabelle 5: ein Term, und ``fit_ols`` muss ``regress`` auf alle Stellen treffen."""
    frame, settings = controls
    fit = fit_ols(frame, TURNOUT, [RATE_TERM], y_scale=settings.context.models.y_scale)
    rate = fit.term(RATE_TERM)
    assert rate.coefficient == pytest.approx(62.1337, abs=5e-4)
    assert fit.intercept.coefficient == pytest.approx(49.1993, abs=5e-4)
    assert rate.stderr == pytest.approx(60.894, abs=5e-4)
    assert rate.p == pytest.approx(0.31385, abs=5e-5)
    assert fit.n == 41 and fit.k == 1


@pytest.mark.slow
def test_no_model_of_the_settings_is_collinear_beyond_use(
    controls: tuple[pl.DataFrame, Settings],
) -> None:
    frame, settings = controls
    table = models_table(frame, settings)
    assert set(table.get_column("stichprobe")) == {"alle", "ohne_1_10"}
    worst = (
        table.filter(pl.col("vif").is_not_null()).sort("vif", descending=True).row(0, named=True)
    )
    assert worst["vif"] < VIF_LIMIT, f"{worst['modell']} / {worst['term']}: VIF {worst['vif']:.2f}"


@pytest.mark.slow
def test_the_added_variable_plots_have_the_slope_of_their_coefficient(
    controls: tuple[pl.DataFrame, Settings],
) -> None:
    """Frisch-Waugh-Lovell: die Steigung durch die Residuen ist genau der Koeffizient."""
    frame, settings = controls
    terms = list(settings.context.models.main)
    scale = settings.context.models.y_scale
    fit = fit_ols(frame, TURNOUT, terms, y_scale=scale)
    for term in terms:
        xs, ys = partial_residuals(frame, TURNOUT, terms, term, y_scale=scale)
        slope = sum(x * y for x, y in zip(xs, ys, strict=True)) / sum(x * x for x in xs)
        assert slope == pytest.approx(fit.term(term).coefficient, rel=1e-9)
