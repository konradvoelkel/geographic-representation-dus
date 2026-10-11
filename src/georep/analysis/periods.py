"""Zwei Wahlperioden nebeneinander: dieselben Kennzahlen je Wahlbezirk und ihre Differenz.

Das Modul rechnet auf zwei Ergebnis-Frames und einer Spaltenkonvention und weiß nicht, woher sie
kommen (Option 02, docs/plans/02-zeitreihe.md, § 5 Stufe F). Verglichen werden nur Kennzahlen,
die in beiden Perioden auf demselben Zuschnitt liegen: die Treffer stammen aus demselben
Wörterbuch, die Wahlbeteiligung ist auf die Wahlbezirke der Hauptperiode umgerechnet. Die
Differenzen sind neu minus alt, die Regression setzt sie zueinander in Beziehung — ohne jede
kausale Deutung, denn es sind 41 Bezirke und zwei Zeitpunkte.
"""

from __future__ import annotations

from collections.abc import Sequence

import deal
import polars as pl

from georep.analysis.hits import DISTRICT, RATE
from georep.analysis.regression import RegressionResult, regress
from georep.contracts import has_columns, sorted_unique
from georep.errors import EmptyResultError
from georep.prep.voters import ELIGIBLE_TOTAL, TURNOUT
from georep.search.index import HITS

OLD = "_alt"
NEW = "_neu"
PERIOD_OLD = "periode_alt"
PERIOD_NEW = "periode_neu"
D_RATE = "d_trefferquote"
D_TURNOUT = "d_wahlbeteiligung"
# Die vier Größen, die beide Perioden vergleichbar führen; Reihenfolge der Ausgabespalten.
MEASURES = (HITS, ELIGIBLE_TOTAL, RATE, TURNOUT)
TOLERANCE = 1e-12


def _columns(suffix: str) -> list[str]:
    return [f"{m}{suffix}" for m in MEASURES]


def comparison_columns() -> list[str]:
    """Die Spalten von ``wahlbezirke_vergleich`` in Reihenfolge; auch das Tabellenregister liest sie."""
    return [
        DISTRICT,
        PERIOD_OLD,
        PERIOD_NEW,
        *_columns(OLD),
        *_columns(NEW),
        D_RATE,
        D_TURNOUT,
    ]


def _deltas_consistent(result: pl.DataFrame) -> bool:
    for column, delta in ((RATE, D_RATE), (TURNOUT, D_TURNOUT)):
        difference = result.get_column(f"{column}{NEW}") - result.get_column(f"{column}{OLD}")
        if not bool(((difference - result.get_column(delta)).abs() <= TOLERANCE).all()):
            return False
    return True


def _only_shared_districts(
    current: pl.DataFrame,
    previous: pl.DataFrame,
    *,
    labels: Sequence[str] = ("alt", "neu"),
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    shared = set(current.get_column(DISTRICT)) & set(previous.get_column(DISTRICT))
    return set(result.get_column(DISTRICT)) == shared


@deal.pre(
    lambda current, previous, *, labels=("alt", "neu"): (
        has_columns(current, DISTRICT, *MEASURES)
        and has_columns(previous, DISTRICT, *MEASURES)
        and sorted_unique(current, DISTRICT)
        and sorted_unique(previous, DISTRICT)
        and len(labels) == 2
        and all(labels)
        and labels[0] != labels[1]
    ),
    message="zwei Auswertungen mit je einer Zeile je Wahlbezirk und zwei verschiedenen Namen",
)
@deal.post(lambda result: result.columns == comparison_columns())
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.post(lambda result: _deltas_consistent(result), message="Differenz ist neu minus alt")
@deal.ensure(_only_shared_districts, message="genau die Wahlbezirke beider Perioden")
@deal.raises(EmptyResultError)
def compare_periods(
    current: pl.DataFrame,
    previous: pl.DataFrame,
    *,
    labels: Sequence[str] = ("alt", "neu"),
) -> pl.DataFrame:
    """Eine Zeile je Wahlbezirk, den beide Perioden kennen: beide Kennzahlsätze und ihre Differenz.

    Geschnitten wird, nicht ergänzt: ein Wahlbezirk, den nur eine Periode kennt, fällt weg statt
    mit Nullen zu erscheinen (eine Trefferquote 0 wäre eine Behauptung, keine Messung). Im Betrieb
    sind beide Mengen gleich, denn beide Perioden rechnen auf dem Zuschnitt der Hauptperiode; der
    Fall tritt auf kleinen Fixtures und bei einem Bezirk ohne Treffer auf, und die Seite nennt die
    Zahl der verglichenen Bezirke.
    """
    old = previous.select(DISTRICT, *MEASURES).rename(
        dict(zip(MEASURES, _columns(OLD), strict=True))
    )
    new = current.select(DISTRICT, *MEASURES).rename(
        dict(zip(MEASURES, _columns(NEW), strict=True))
    )
    joined = old.join(new, on=DISTRICT, how="inner").sort(DISTRICT)
    if joined.is_empty():
        raise EmptyResultError(
            "Kein Wahlbezirk kommt in beiden Perioden vor: rechnen sie auf demselben Zuschnitt?"
        )
    return joined.with_columns(
        pl.lit(labels[0]).alias(PERIOD_OLD),
        pl.lit(labels[1]).alias(PERIOD_NEW),
        (pl.col(f"{RATE}{NEW}") - pl.col(f"{RATE}{OLD}")).alias(D_RATE),
        (pl.col(f"{TURNOUT}{NEW}") - pl.col(f"{TURNOUT}{OLD}")).alias(D_TURNOUT),
    ).select(comparison_columns())


@deal.raises(EmptyResultError)
def delta_regression(comparison: pl.DataFrame) -> RegressionResult:
    """Änderung der Wahlbeteiligung (in Prozentpunkten) gegen Änderung der Trefferquote.

    Dieselbe Funktion wie für Tabelle 5, nur mit anderen Spalten: ein Bezirk, dessen Sichtbarkeit
    zwischen den Perioden gestiegen ist, hat nicht auch eine gestiegene Beteiligung — ob doch,
    sagt diese Zeile.
    """
    return regress(comparison, x=D_RATE, y=D_TURNOUT)
