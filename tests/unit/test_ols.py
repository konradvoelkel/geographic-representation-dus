"""OLS an Handbeispielen und an den Rändern: exakte Fälle, Fehler, kleine Stichproben."""

from __future__ import annotations

from pathlib import Path

import deal
import polars as pl
import pytest
from scipy.stats import t as t_distribution

from georep.analysis.ols import (
    ALL,
    CONSTANT,
    fit_ols,
    model_frame,
    model_terms,
    models_table,
    partial_residuals,
    sample_label,
)
from georep.analysis.regression import regress
from georep.errors import EmptyResultError
from georep.layout import Layout
from georep.prep.voters import TURNOUT
from georep.settings import RATE_TERM, Settings, load_settings


def _frame(rows: list[tuple[float, float, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        rows, schema={"y": pl.Float64, "a": pl.Float64, "b": pl.Float64}, orient="row"
    )


def test_an_exact_plane_is_fitted_without_residuals() -> None:
    """y = 2 + 3a - b auf vier Punkten: Koeffizienten exakt, R² = 1, Residuen 0."""
    rows = [(2.0, 0.0, 0.0), (5.0, 1.0, 0.0), (1.0, 0.0, 1.0), (7.0, 2.0, 1.0)]
    fit = fit_ols(_frame(rows), "y", ["a", "b"])
    assert fit.n == 4 and fit.k == 2
    assert fit.intercept.coefficient == pytest.approx(2.0)
    assert fit.term("a").coefficient == pytest.approx(3.0)
    assert fit.term("b").coefficient == pytest.approx(-1.0)
    assert fit.r2 == pytest.approx(1.0) and fit.r2_adj == pytest.approx(1.0)
    assert all(abs(r) < 1e-9 for r in fit.residuals)
    assert fit.terms[0].term == CONSTANT and fit.terms[0].vif is None


def test_the_bivariate_fit_equals_the_regression_of_the_thesis(
    mini_run: Layout, default_settings: Settings
) -> None:
    results = pl.read_parquet(mini_run.results)
    frame = model_frame(results, pl.read_parquet(mini_run.context_table))
    fit = fit_ols(frame, TURNOUT, [RATE_TERM], y_scale=100.0)
    old = regress(results)
    assert fit.term(RATE_TERM).coefficient == pytest.approx(old.slope, rel=1e-9)
    assert fit.intercept.coefficient == pytest.approx(old.intercept, rel=1e-9)
    assert fit.term(RATE_TERM).stderr == pytest.approx(old.stderr, rel=1e-9)
    assert fit.term(RATE_TERM).p == pytest.approx(old.p, rel=1e-9)
    assert fit.r2 == pytest.approx(old.r2, rel=1e-9)


def test_y_scale_multiplies_coefficients_but_not_p_or_r2() -> None:
    rows = [(0.4, 1.0, 2.0), (0.5, 2.0, 1.0), (0.45, 3.0, 4.0), (0.6, 4.0, 2.0), (0.7, 5.0, 5.0)]
    one = fit_ols(_frame(rows), "y", ["a"])
    hundred = fit_ols(_frame(rows), "y", ["a"], y_scale=100.0)
    assert hundred.term("a").coefficient == pytest.approx(one.term("a").coefficient * 100.0)
    assert hundred.term("a").p == pytest.approx(one.term("a").p)
    assert hundred.r2 == pytest.approx(one.r2)
    assert hundred.term("a").beta == pytest.approx(one.term("a").beta)


def test_a_duplicated_term_is_refused_as_a_singular_design() -> None:
    rows = [(1.0, 1.0, 1.0), (2.0, 2.0, 2.0), (3.0, 3.1, 3.1), (4.0, 3.9, 3.9), (5.0, 5.0, 5.0)]
    with pytest.raises(EmptyResultError, match="singulär"):
        fit_ols(_frame(rows), "y", ["a", "b"])


def test_without_variance_in_y_there_is_no_fit() -> None:
    rows = [(3.0, 1.0, 0.0), (3.0, 2.0, 1.0), (3.0, 3.0, 2.0), (3.0, 4.0, 5.0)]
    with pytest.raises(EmptyResultError, match="Streuung"):
        fit_ols(_frame(rows), "y", ["a"])


def test_too_few_rows_violate_the_contract() -> None:
    rows = [(1.0, 1.0, 2.0), (2.0, 2.0, 1.0), (3.0, 3.0, 4.0)]
    with pytest.raises(deal.PreContractError):
        fit_ols(_frame(rows), "y", ["a", "b"])  # n = 3, k = 2: ein Freiheitsgrad fehlt


def test_the_standardised_coefficient_is_the_correlation_in_the_bivariate_case() -> None:
    rows = [(1.0, 2.0, 0.0), (2.0, 3.5, 0.0), (3.0, 3.0, 0.0), (4.0, 6.0, 0.0), (5.0, 7.0, 0.0)]
    frame = _frame(rows)
    fit = fit_ols(frame, "y", ["a"])
    expected = pl.corr(pl.col("y"), pl.col("a"))
    assert fit.term("a").beta == pytest.approx(frame.select(expected).item())


def test_partial_residuals_of_a_single_term_are_the_centred_values() -> None:
    rows = [(1.0, 2.0, 0.0), (2.0, 3.0, 1.0), (3.0, 4.0, 2.0), (4.0, 7.0, 3.0)]
    xs, ys = partial_residuals(_frame(rows), "y", ["a"], "a")
    assert sum(xs) == pytest.approx(0.0) and sum(ys) == pytest.approx(0.0)
    assert xs == pytest.approx([2.0 - 4.0, 3.0 - 4.0, 4.0 - 4.0, 7.0 - 4.0])


def test_models_table_skips_what_is_too_small_and_keeps_the_rest(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Auf der Mini-Fixture (n = 3) passt nur ein Modell mit einem Term; der Rest fehlt als Zeile."""
    frame = model_frame(pl.read_parquet(mini_run.results), pl.read_parquet(mini_run.context_table))
    assert frame.height == 3
    table = models_table(frame, default_settings)
    assert set(table.get_column("modell")) == {"A"}
    assert set(table.get_column("stichprobe")) == {ALL}  # ohne 1 und 10 bleibt ein Bezirk
    assert set(table.get_column("term")) == {CONSTANT, RATE_TERM}
    assert table.get_column("n").unique().to_list() == [3]


def test_model_terms_follow_the_settings(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        'context.models = { main = ["trefferquote", "hb_score"], '
        'parties = ["trefferquote", "cdu"], single = ["cdu", "afd"] }\n',
        encoding="utf-8",
    )
    models = model_terms(load_settings(cwd=tmp_path).context)
    assert models["A"] == (RATE_TERM,)
    assert models["B"] == (RATE_TERM, "hb_score")
    assert models["C"] == (RATE_TERM, "cdu")
    assert models["single:afd"] == (RATE_TERM, "afd")
    assert list(models) == ["A", "B", "C", "single:cdu", "single:afd"]


def test_sample_label_names_the_excluded_districts() -> None:
    assert sample_label([1, 10]) == "ohne_1_10"


def test_the_vif_of_two_terms_is_one_over_one_minus_their_squared_correlation() -> None:
    """Bei zwei Termen ist die Varianzinflation exakt 1/(1 − r²); das prüft die Hilfsregression.

    Die VIF-Zahlen der echten Modelle stehen nur im slow-Test, und `nox -s mutate` lässt den aus;
    ohne diesen Test überlebten die Mutanten in `_vif` (2026-10-12).
    """
    rows = [(1.0, 1.0, 2.0), (2.0, 2.0, 1.0), (3.0, 3.0, 5.0), (4.0, 4.0, 3.0), (5.0, 6.0, 9.0)]
    frame = _frame(rows)
    fit = fit_ols(frame, "y", ["a", "b"])
    correlation = frame.select(pl.corr(pl.col("a"), pl.col("b"))).item()
    expected = 1.0 / (1.0 - correlation**2)
    assert fit.term("a").vif == pytest.approx(expected)
    assert fit.term("b").vif == pytest.approx(expected)  # bei k = 2 teilen sich beide den Wert
    assert expected > 1.5  # die beiden Terme erklären sich spürbar gegenseitig
    # Mit nur einem Term gibt es nichts zu erklären
    assert fit_ols(frame, "y", ["a"]).term("a").vif == 1.0


def test_an_orthogonal_design_gives_the_numbers_of_the_closed_form() -> None:
    """Alle Zahlen eines Zwei-Term-Modells gegen die geschlossene Form (2026-10-13).

    Bei einem zentrierten, orthogonalen Design (``Σa = Σb = 0``, ``a·b = 0``) steht jede Zahl in
    einer Formel: ``b_j = (x_j·y)/(x_j·x_j)``, ``σ² = RSS/(n−k−1)``,
    ``se_j = sqrt(σ²/(x_j·x_j))``, ``F = ((TSS−RSS)/k)/σ²``,
    ``R²_korr = 1 − (1−R²)(n−1)/(n−k−1)``, ``β_j = b_j · sd(x_j)/sd(y)``. Das ist ein Orakel und
    keine zweite Fassung der Rechnung: der Code löst ein Normalgleichungssystem mit ``lstsq``.

    Vorher prüfte kein schneller Test F, R²_korr, ``beta`` oder die Zuordnung von
    Standardfehler, t und p **je Term**; die Zahlen der echten Modelle stehen nur im slow-Test
    gegen statsmodels, und der Mutationslauf lässt ihn aus. Elf Mutanten überlebten deshalb
    (docs/mutation-2026-10-13.md): die Indexverschiebung ``i + 1`` zu ``i - 1`` fällt bei einem
    einzigen Term nicht auf, denn dann ist ``matrix[:, -1]`` dieselbe Spalte.
    """
    a = [-1.0, -1.0, 0.0, 0.0, 1.0, 1.0]
    b = [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0]
    y = [1.0, 4.0, 2.0, 5.0, 6.0, 8.0]
    frame = _frame([(y[i], a[i], b[i]) for i in range(len(y))])
    fit = fit_ols(frame, "y", ["a", "b"])

    n, k = len(y), 2
    mean_y = sum(y) / n
    aa, bb = sum(v * v for v in a), sum(v * v for v in b)
    coefficient = {
        "a": sum(a[i] * y[i] for i in range(n)) / aa,
        "b": sum(b[i] * y[i] for i in range(n)) / bb,
    }
    fitted = [mean_y + coefficient["a"] * a[i] + coefficient["b"] * b[i] for i in range(n)]
    rss = sum((y[i] - fitted[i]) ** 2 for i in range(n))
    tss = sum((value - mean_y) ** 2 for value in y)
    sigma2 = rss / (n - k - 1)
    r2 = 1.0 - rss / tss
    sd_y = (tss / (n - 1)) ** 0.5

    assert fit.n == n and fit.k == k
    assert fit.intercept.coefficient == pytest.approx(mean_y)
    assert fit.r2 == pytest.approx(r2)
    assert fit.r2_adj == pytest.approx(1.0 - (1.0 - r2) * (n - 1) / (n - k - 1))
    assert fit.f == pytest.approx(((tss - rss) / k) / sigma2)
    for name, squares in (("a", aa), ("b", bb)):
        stats = fit.term(name)
        stderr = (sigma2 / squares) ** 0.5
        sd_x = (squares / (n - 1)) ** 0.5  # die Spalte ist zentriert
        assert stats.coefficient == pytest.approx(coefficient[name]), name
        assert stats.stderr == pytest.approx(stderr), name
        assert stats.t == pytest.approx(coefficient[name] / stderr), name
        # p zweiseitig aus der t-Verteilung mit n - k - 1 Freiheitsgraden; scipy ist das Orakel
        assert stats.p == pytest.approx(
            2.0 * t_distribution.sf(abs(coefficient[name] / stderr), n - k - 1)
        ), name
        assert stats.beta == pytest.approx(coefficient[name] * sd_x / sd_y), name
        assert stats.vif == pytest.approx(1.0), name  # orthogonal: keine Varianzinflation
    # Die Terme stehen in verschiedenen Spalten: derselbe Standardfehler wäre ein Indexfehler.
    assert fit.term("a").stderr != pytest.approx(fit.term("b").stderr)


def test_the_summary_names_every_term_with_its_numbers() -> None:
    rows = [(1.0, 1.0, 2.0), (2.0, 2.0, 1.0), (3.0, 3.0, 5.0), (4.0, 4.0, 3.0), (5.0, 6.0, 9.0)]
    text = fit_ols(_frame(rows), "y", ["a", "b"]).summary()
    assert "n=5, k=2" in text and "R²=" in text and "F-p=" in text
    assert text.count("\n") == 3 and "VIF=" in text  # Kopf plus Konstante und zwei Terme
    assert "(Konstante)" in text and text.count("VIF=") == 2  # die Konstante hat keines
