"""Lineare Regression Trefferquote -> Wahlbeteiligung, wie im Notebook der Arbeit.

``scipy.stats.linregress`` auf ``trefferquote`` (x) und ``wahlbeteiligung`` in Prozent (y);
Tabelle 5 der Arbeit entsteht aus ``regress(results)`` und ``regress(results, exclude=(1, 10))``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import deal
import polars as pl
from scipy.stats import linregress

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
    fit = linregress(frame.get_column(x).to_numpy(), (frame.get_column(y) * y_scale).to_numpy())
    return RegressionResult(
        n=frame.height,
        slope=float(fit.slope),
        intercept=float(fit.intercept),
        r=float(fit.rvalue),
        p=float(fit.pvalue),
        stderr=float(fit.stderr),
    )
