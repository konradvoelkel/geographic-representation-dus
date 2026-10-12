"""Lineare Regression Trefferquote -> Wahlbeteiligung, wie im Notebook der Arbeit.

``scipy.stats.linregress`` auf ``trefferquote`` (x) und ``wahlbeteiligung`` in Prozent (y);
Tabelle 5 der Arbeit entsteht aus ``regress(results)`` und ``regress(results, exclude=(1, 10))``.
``spearman`` vergleicht daneben zwei Kennzahlen im Rang: wie ähnlich ordnet eine gewichtete Quote
die Wahlbezirke der ungewichteten?
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import deal
import polars as pl
from scipy.stats import linregress, spearmanr

from georep.analysis.hits import DISTRICT, RATE
from georep.contracts import has_columns
from georep.errors import EmptyResultError
from georep.prep.voters import TURNOUT


@dataclass(frozen=True)
class RegressionResult:
    n: int
    slope: float
    intercept: float
    r: float
    p: float
    stderr: float

    @property
    def r2(self) -> float:
        return self.r * self.r

    def summary(self) -> str:
        return (
            f"n={self.n}: y = {self.slope:.4f}·x + {self.intercept:.4f}, r={self.r:.4f}, "
            f"R²={self.r2:.4f}, p={self.p:.5f}"
        )


@dataclass(frozen=True)
class RegressionPair:
    """Tabelle 5: alle Wahlbezirke und dieselbe Regression ohne die Ausreißer.

    ``without`` ist None, wenn keine Ausreißer benannt sind (``analysis.exclude_districts`` leer)
    oder ohne sie zu wenige Bezirke bleiben.
    """

    all: RegressionResult
    excluded: tuple[int, ...]
    without: RegressionResult | None


@deal.pre(
    lambda results, exclude=(), *, x=RATE, y=TURNOUT, y_scale=100.0: (
        has_columns(results, DISTRICT, x, y) and y_scale > 0
    )
)
@deal.post(
    lambda result: (
        result.n >= 3
        and -1.0 <= result.r <= 1.0
        and 0.0 <= result.p <= 1.0
        and result.stderr >= 0.0
    ),
    message="r in [-1, 1], p in [0, 1], Standardfehler nicht negativ",
)
@deal.raises(EmptyResultError)
def regress(
    results: pl.DataFrame,
    exclude: Iterable[int] = (),
    *,
    x: str = RATE,
    y: str = TURNOUT,
    y_scale: float = 100.0,
) -> RegressionResult:
    frame = results.filter(~pl.col(DISTRICT).is_in(list(exclude)))
    if frame.height < 3:
        raise EmptyResultError(
            f"Regression braucht mindestens 3 Wahlbezirke, {frame.height} vorhanden."
        )
    if frame.get_column(x).n_unique() < 2:
        # scipy 1.18 liefert hier Steigung 0, r 0 und einen Standardfehler von 1e17 mit einer
        # RuntimeWarning; ältere Versionen warfen ValueError. Beides ist kein Ergebnis.
        raise EmptyResultError(f"Regression braucht Streuung in {x}: alle Werte gleich.")
    if frame.get_column(y).n_unique() < 2:
        # Dieselbe Luecke auf der anderen Achse: scipy liefert dann r und p als NaN und die
        # Nachbedingung schlaegt an (Option 02, 2026-10-12; mit den Differenzen zweier Perioden
        # auf kleinen Daten kommt der Fall vor, mit echten Wahlbeteiligungen nie).
        raise EmptyResultError(f"Regression braucht Streuung in {y}: alle Werte gleich.")
    fit = linregress(frame.get_column(x).to_numpy(), (frame.get_column(y) * y_scale).to_numpy())
    return RegressionResult(
        n=frame.height,
        slope=float(fit.slope),
        intercept=float(fit.intercept),
        r=float(fit.rvalue),
        p=float(fit.pvalue),
        stderr=float(fit.stderr),
    )


@deal.post(
    lambda result: result.without is None or result.without.n <= result.all.n,
    message="ohne Ausreißer bleiben höchstens so viele Bezirke wie mit",
)
@deal.raises(EmptyResultError)
def regression_pair(
    results: pl.DataFrame,
    exclude: Iterable[int] = (),
    *,
    x: str = RATE,
    y: str = TURNOUT,
    y_scale: float = 100.0,
) -> RegressionPair:
    """Beide Spalten von Tabelle 5 für eine Kennzahl ``x``: alle Bezirke und ohne ``exclude``.

    Dieselbe Funktion rechnet jede Kennzahlvariante (gewichtete Quoten, andere Perioden), darum
    sind ``x`` und ``y`` Parameter; die Ausreißer kommen aus ``settings.analysis.exclude_districts``.
    """
    excluded = tuple(exclude)
    without: RegressionResult | None = None
    if excluded:
        try:
            without = regress(results, exclude=excluded, x=x, y=y, y_scale=y_scale)
        except EmptyResultError:
            without = None
    return RegressionPair(
        all=regress(results, x=x, y=y, y_scale=y_scale), excluded=excluded, without=without
    )


@deal.pre(lambda frame, x, reference: has_columns(frame, x, reference))
@deal.post(
    lambda result: result is None or -1.0 <= result <= 1.0,
    message="eine Rangkorrelation liegt in [-1, 1]; None heißt: nicht definiert",
)
def spearman(frame: pl.DataFrame, x: str, reference: str) -> float | None:
    """Rangkorrelation zweier Kennzahlspalten; ``None``, wenn eine Spalte keine Streuung hat.

    Für die Sensitivitätstabelle: ``spearman(frame, "trefferquote_gewichtet", "trefferquote")``
    sagt, ob eine Gewichtung die Reihenfolge der Wahlbezirke ändert oder nur deren Abstände. Eine
    Variante ohne Streuung (alle Quoten gleich) hat keinen Rang und darum kein Ergebnis -- das ist
    kein Fehler, die Tabelle zeigt dort „—".
    """
    if frame.height < 3:
        return None
    if frame.get_column(x).n_unique() < 2 or frame.get_column(reference).n_unique() < 2:
        return None
    rho = float(
        spearmanr(frame.get_column(x).to_numpy(), frame.get_column(reference).to_numpy()).statistic
    )
    # Bindungen in beiden Spalten können scipy zu nan führen; das ist kein Ergebnis.
    return None if math.isnan(rho) else max(-1.0, min(1.0, rho))
