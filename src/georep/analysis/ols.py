"""Multiple lineare Regression mit numpy und scipy: Tabelle 6 der Berichtsseite.

Warum nicht statsmodels: es hängt von pandas ab, und das verbietet ``nox -s deps`` (Konrads
Vorgabe, docs/decisions.md). Gebraucht werden Koeffizienten, Standardfehler, t, p, R²,
adjustiertes R², der F-Test und VIF -- zusammen rund hundert Zeilen über ``numpy.linalg.lstsq``
und ``scipy.stats``. Die Zahlen sind einmal gegen statsmodels geprüft (Stufe D.3 des Plans) und
stehen als Konstanten in ``tests/golden/test_regression_numbers.py``.

``regress`` aus ``analysis.regression`` bleibt der Weg für Tabelle 5 (Fundament F3); ein Test
zeigt, dass ``fit_ols`` mit einem Term dasselbe liefert.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import deal
import numpy as np
import numpy.typing as npt
import polars as pl
from scipy.stats import f as f_distribution
from scipy.stats import t as t_distribution

from georep.analysis.hits import DISTRICT, RATE
from georep.contracts import has_columns
from georep.errors import EmptyResultError
from georep.prep.voters import TURNOUT
from georep.settings import RATE_TERM, ContextSettings, Settings

CONSTANT = "(Konstante)"  # Zeile der Achsenabschnitte in der langen Tabelle
MAX_CONDITION = 1e12  # darüber ist die Designmatrix praktisch singulär
Vector = npt.NDArray[np.float64]


@dataclass(frozen=True)
class TermStats:
    """Ein Term eines Modells mit allem, was Tabelle 6 je Zeile zeigt."""

    term: str
    coefficient: float
    stderr: float
    t: float
    p: float
    beta: float | None  # standardisierter Koeffizient; None für die Konstante
    vif: float | None  # Varianzinflation; None für die Konstante


@dataclass(frozen=True)
class OlsResult:
    n: int
    k: int  # Terme ohne die Konstante
    terms: tuple[TermStats, ...]  # die Konstante zuerst
    r2: float
    r2_adj: float
    f: float
    f_p: float
    residuals: tuple[float, ...]
    fitted: tuple[float, ...]

    @property
    def intercept(self) -> TermStats:
        return self.terms[0]

    def term(self, name: str) -> TermStats:
        return next(t for t in self.terms if t.term == name)

    def summary(self) -> str:
        head = f"n={self.n}, k={self.k}, R²={self.r2:.4f}, korrigiert {self.r2_adj:.4f}, F-p={self.f_p:.5f}"
        rows = [
            f"  {t.term:<22} {t.coefficient:>12.4f} {t.stderr:>10.4f} p={t.p:.5f}"
            + (f" VIF={t.vif:.2f}" if t.vif is not None else "")
            for t in self.terms
        ]
        return "\n".join([head, *rows])


def _design(frame: pl.DataFrame, terms: Sequence[str]) -> Vector:
    columns = [frame.get_column(t).to_numpy().astype(np.float64) for t in terms]
    return np.column_stack([np.ones(frame.height), *columns])


def _r_squared(y: Vector, residuals: Vector) -> tuple[float, float]:
    """(R², Summe der quadrierten Abweichungen von y)."""
    rss = float(residuals @ residuals)
    tss = float(((y - y.mean()) ** 2).sum())
    return 1.0 - rss / tss, tss


def _vif(matrix: Vector, index: int) -> float:
    """Varianzinflation von Spalte ``index`` der Designmatrix (ohne die Konstante gezählt)."""
    columns = matrix.shape[1] - 1
    if columns < 2:
        return 1.0
    target = matrix[:, index + 1]
    others = np.column_stack(
        [matrix[:, 0], *(matrix[:, j + 1] for j in range(columns) if j != index)]
    )
    coefficients, *_ = np.linalg.lstsq(others, target, rcond=None)
    r2, _ = _r_squared(target, target - others @ coefficients)
    return float("inf") if r2 >= 1.0 else 1.0 / (1.0 - r2)


def _sane(result: OlsResult) -> bool:
    return (
        0.0 <= result.r2 <= 1.0
        and result.r2_adj <= result.r2
        and all(0.0 <= t.p <= 1.0 and t.stderr >= 0.0 for t in result.terms)
        and all(t.vif is None or t.vif >= 1.0 - 1e-9 for t in result.terms)
        and 0.0 <= result.f_p <= 1.0
        and len(result.residuals) == len(result.fitted) == result.n
    )


@deal.pre(
    lambda frame, y, terms, *, y_scale=1.0: (
        has_columns(frame, y, *terms)
        and len(set(terms)) == len(list(terms)) > 0
        and y_scale > 0
        and frame.height >= len(list(terms)) + 2
    ),
    message="Spalten vorhanden, Terme verschieden, y_scale positiv, n mindestens k + 2",
)
@deal.post(_sane, message="R² in [0, 1], adjustiert nicht größer, p in [0, 1], VIF mindestens 1")
@deal.raises(EmptyResultError)
def fit_ols(
    frame: pl.DataFrame, y: str, terms: Sequence[str], *, y_scale: float = 1.0
) -> OlsResult:
    """Kleinste Quadrate von ``y`` (mal ``y_scale``) auf ``terms`` plus Konstante.

    Standardfehler aus σ² (XᵀX)⁻¹, p zweiseitig über die t-Verteilung mit n − k − 1
    Freiheitsgraden, F-Test gegen das Modell nur mit Konstante, VIF je Term aus einer
    Hilfsregression auf die übrigen Terme, standardisierte Koeffizienten als b · sd(x)/sd(y)
    (die Einheiten der Terme sind verschieden). Ohne Streuung in ``y`` oder bei praktisch
    singulärer Designmatrix gibt es kein Ergebnis: ``EmptyResultError``.
    """
    names = list(terms)
    matrix = _design(frame, names)
    target = frame.get_column(y).to_numpy().astype(np.float64) * y_scale
    if np.ptp(target) == 0.0:
        raise EmptyResultError(f"Regression braucht Streuung in {y}: alle Werte gleich.")
    condition = float(np.linalg.cond(matrix))
    if not np.isfinite(condition) or condition > MAX_CONDITION:
        raise EmptyResultError(
            f"Designmatrix praktisch singulär (Konditionszahl {condition:.3g}): "
            f"die Terme {names} sind linear abhängig."
        )
    coefficients, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    fitted = matrix @ coefficients
    residuals = target - fitted
    n, k = frame.height, len(names)
    df = n - k - 1
    r2, tss = _r_squared(target, residuals)
    rss = float(residuals @ residuals)
    sigma2 = rss / df
    covariance = sigma2 * np.linalg.inv(matrix.T @ matrix)
    stderr = np.sqrt(np.diag(covariance))
    scores = coefficients / stderr
    p_values = 2.0 * t_distribution.sf(np.abs(scores), df)
    sd_y = float(target.std(ddof=1))
    statistic = ((tss - rss) / k) / sigma2
    stats = [
        TermStats(
            CONSTANT,
            float(coefficients[0]),
            float(stderr[0]),
            float(scores[0]),
            float(p_values[0]),
            None,
            None,
        )
    ]
    for i, name in enumerate(names):
        sd_x = float(matrix[:, i + 1].std(ddof=1))
        stats.append(
            TermStats(
                name,
                float(coefficients[i + 1]),
                float(stderr[i + 1]),
                float(scores[i + 1]),
                float(p_values[i + 1]),
                float(coefficients[i + 1] * sd_x / sd_y) if sd_y > 0 else 0.0,
                _vif(matrix, i),
            )
        )
    return OlsResult(
        n=n,
        k=k,
        terms=tuple(stats),
        r2=r2,
        r2_adj=1.0 - (1.0 - r2) * (n - 1) / df,
        f=float(statistic),
        f_p=float(f_distribution.sf(statistic, k, df)),
        residuals=tuple(residuals.tolist()),
        fitted=tuple(fitted.tolist()),
    )


@deal.pre(
    lambda frame, y, terms, term, *, y_scale=1.0: term in set(terms),
    message="der Term gehört zum Modell",
)
@deal.raises(EmptyResultError)
def partial_residuals(
    frame: pl.DataFrame, y: str, terms: Sequence[str], term: str, *, y_scale: float = 1.0
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(x-Residuen, y-Residuen) für ein Added-Variable-Plot nach Frisch-Waugh-Lovell.

    Beide Größen werden auf die übrigen Terme regressiert; die Steigung der Gerade durch die
    Residuen ist genau der Koeffizient des Terms im vollen Modell (ein Test prüft das). Bleibt
    kein weiterer Term, sind es die zentrierten Rohwerte.
    """
    others = [t for t in terms if t != term]
    y_values = frame.get_column(y).to_numpy().astype(np.float64) * y_scale
    x_values = frame.get_column(term).to_numpy().astype(np.float64)
    if not others:
        return (
            tuple((x_values - x_values.mean()).tolist()),
            tuple((y_values - y_values.mean()).tolist()),
        )
    matrix = _design(frame, others)

    def residual(values: Vector) -> Vector:
        coefficients, *_ = np.linalg.lstsq(matrix, values, rcond=None)
        return values - matrix @ coefficients

    return tuple(residual(x_values).tolist()), tuple(residual(y_values).tolist())


# --- Die lange Tabelle: je Modell, Stichprobe und Term eine Zeile --------------------------------

MODELS_SCHEMA = {
    "modell": pl.String,
    "stichprobe": pl.String,
    "term": pl.String,
    "koeffizient": pl.Float64,
    "standardfehler": pl.Float64,
    "t": pl.Float64,
    "p": pl.Float64,
    "beta_std": pl.Float64,
    "vif": pl.Float64,
    "n": pl.Int64,
    "k": pl.Int64,
    "r2": pl.Float64,
    "r2_adj": pl.Float64,
    "f_p": pl.Float64,
}
ALL = "alle"
MAIN_MODEL = "B"  # das Hauptmodell: Trefferquote plus die Kontrollvariablen aus context.models.main


def sample_label(excluded: Iterable[int]) -> str:
    """Name der Stichprobe ohne Ausreißer, aus den Nummern: ``ohne_1_10``."""
    return "ohne_" + "_".join(str(d) for d in excluded)


def model_frame(results: pl.DataFrame, context: pl.DataFrame) -> pl.DataFrame:
    """Wahlbeteiligung, Trefferquote und die Kontrollvariablen in einer Tabelle je Wahlbezirk."""
    return (
        results.select(DISTRICT, TURNOUT, pl.col(RATE).alias(RATE_TERM))
        .join(context, on=DISTRICT, how="inner")
        .sort(DISTRICT)
    )


def model_terms(context: ContextSettings) -> dict[str, tuple[str, ...]]:
    """Die Modelle in der Reihenfolge der Tabelle: A, B, C und je eine Variable einzeln."""
    models: dict[str, tuple[str, ...]] = {
        "A": (RATE_TERM,),
        "B": tuple(context.models.main),
        "C": tuple(context.models.parties),
    }
    for name in context.models.single:
        models[f"single:{name}"] = (RATE_TERM, name)
    return models


@deal.post(
    lambda result: list(result.columns) == list(MODELS_SCHEMA),
    message="die Spalten der langen Tabelle",
)
def models_table(frame: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """Jedes Modell aus den Settings für jede Stichprobe; zu kleine Stichproben fehlen.

    Ein Modell braucht n ≥ k + 2 Wahlbezirke; auf einer kleinen Fixture (n = 3) bleibt darum nur
    das Modell mit einem Term. Was fehlt, fehlt als Zeile -- die Seite zeigt dann nur, was
    gerechnet werden konnte.
    """
    context = settings.context
    excluded = list(settings.analysis.exclude_districts)
    samples: list[tuple[str, pl.DataFrame]] = [(ALL, frame)]
    if excluded:
        samples.append((sample_label(excluded), frame.filter(~pl.col(DISTRICT).is_in(excluded))))
    rows: list[tuple[object, ...]] = []
    for model, terms in model_terms(context).items():
        for sample, data in samples:
            if data.height < len(terms) + 2:
                continue
            try:
                fit = fit_ols(data, TURNOUT, terms, y_scale=context.models.y_scale)
            except EmptyResultError:
                continue
            rows.extend(
                (
                    model,
                    sample,
                    stats.term,
                    stats.coefficient,
                    stats.stderr,
                    stats.t,
                    stats.p,
                    stats.beta,
                    stats.vif,
                    fit.n,
                    fit.k,
                    fit.r2,
                    fit.r2_adj,
                    fit.f_p,
                )
                for stats in fit.terms
            )
    return pl.DataFrame(rows, schema=MODELS_SCHEMA, orient="row")
