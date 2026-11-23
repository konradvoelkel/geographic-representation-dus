"""Beobachtet gegen erwartet: eine Einheit gegen die Praxis der Schichten, in denen sie handelt.

Der Kontrollanteil einer Fraktion ist zum großen Teil Praxis des Gremiums: in den Ausschüssen
wird mehr gefragt als im Rat und in den Bezirksvertretungen (Messdokument
``docs/plans/15-funktion.md``, § 3.7). Ein roher Anteil je Fraktion misst darum vor allem, wo sie
ihre Dokumente stellt. Die **indirekte Standardisierung** rechnet je Schicht (Gremium und Periode)
den Anteil über alle Dokumente der Schicht und summiert ihn über die Dokumente der Einheit:
das ist die Zahl, die die Einheit hätte, wenn sie in jedem ihrer Gremien so handelte wie alle dort.
Beobachtet durch erwartet über 1 heißt: mehr als die Praxis ihrer Gremien.

Gebaut für Vorhaben 15 (Instrumente je Fraktion), genutzt von Vorhaben 14 (Antworten je Fraktion;
Synergien 2026-11, § 1). Rein, ohne Settings; welche Spalten Einheit, Ergebnis und Schichten sind,
sagt der Aufrufer. Die Seite nennt das Verhältnis „explorativ" (§ 5).
"""

from __future__ import annotations

from collections.abc import Sequence

import deal
import polars as pl

from georep.contracts import has_columns

N = "n"
OBSERVED = "beobachtet"
EXPECTED = "erwartet"
RATIO = "verhaeltnis"
_RATE = "__anteil_der_schicht"


def _arguments_fit(
    frame: pl.DataFrame,
    *,
    unit: str,
    outcome: str,
    strata: Sequence[str],
    by: Sequence[str] = (),
) -> bool:
    names = {unit, outcome, *strata}
    return (
        has_columns(frame, unit, outcome, *strata)
        and frame.schema[outcome] == pl.Boolean
        and frame.get_column(outcome).null_count() == 0
        and len(strata) > 0
        and set(by) <= set(strata)
        and len(names) == 2 + len(set(strata))
        and _RATE not in frame.columns
    )


def _bounds_hold(
    frame: pl.DataFrame,
    *,
    unit: str,
    outcome: str,
    strata: Sequence[str],
    by: Sequence[str] = (),
    result: pl.DataFrame | None = None,
) -> bool:
    """Die Spalten in Folge, je Einheit eine Zeile, 0 ≤ beobachtet, erwartet ≤ n."""
    assert result is not None
    keys = [*by, unit]
    tol = 1e-9
    return (
        result.columns == [*keys, N, OBSERVED, EXPECTED, RATIO]
        and result.select(keys).is_unique().all()
        and bool(((result[OBSERVED] >= 0) & (result[OBSERVED] <= result[N])).all())
        and bool(((result[EXPECTED] >= -tol) & (result[EXPECTED] <= result[N] + tol)).all())
    )


@deal.pre(_arguments_fit, message="Einheit, Ergebnis (bool ohne null) und Schichten; by in strata")
@deal.ensure(
    _bounds_hold, message="eine Zeile je Einheit, beobachtet und erwartet zwischen 0 und n"
)
def observed_expected(
    frame: pl.DataFrame,
    *,
    unit: str,
    outcome: str,
    strata: Sequence[str],
    by: Sequence[str] = (),
) -> pl.DataFrame:
    """Je Einheit (und ``by``): Zahl, beobachtet, erwartet und ihr Verhältnis.

    ``frame`` hat eine Zeile je Dokument. ``unit`` ist ein Wert oder eine Liste: ein gemeinsames
    Dokument zählt für jede Einheit darin, ein Dokument ohne Einheit (leere Liste, ``null``) nur für
    den Anteil seiner Schicht. ``outcome`` ist bool (etwa „ist Kontrolle"). Der Anteil einer Schicht
    (``strata``, etwa Periode und Gremium) ist der Mittelwert von ``outcome`` über ihre Dokumente,
    jedes einmal. ``by`` sind Spalten, nach denen das Ergebnis getrennt bleibt (etwa die Periode);
    sie müssen Schichten sein, damit eine Einheit nur gegen ihre eigene Gruppe gemessen wird.
    ``verhaeltnis`` ist ``null``, wo ``erwartet`` 0 ist (die Gremien der Einheit kennen das
    Ergebnis gar nicht). Sortiert nach ``by`` und Einheit.
    """
    strata = list(strata)
    keys = [*by, unit]
    rates = frame.group_by(strata).agg(pl.col(outcome).cast(pl.Float64).mean().alias(_RATE))
    rows = frame.select(*strata, unit, outcome)
    if isinstance(frame.schema[unit], pl.List):
        rows = rows.explode(unit)
    rows = rows.filter(pl.col(unit).is_not_null())
    joined = rows.join(rates, on=strata, how="left", nulls_equal=True)
    return (
        joined.group_by(keys)
        .agg(
            pl.len().alias(N),
            pl.col(outcome).sum().alias(OBSERVED),
            pl.col(_RATE).sum().alias(EXPECTED),
        )
        .with_columns(
            pl.when(pl.col(EXPECTED) > 0)
            .then(pl.col(OBSERVED) / pl.col(EXPECTED))
            .otherwise(None)
            .alias(RATIO)
        )
        .select(*keys, N, OBSERVED, EXPECTED, RATIO)
        .sort(keys, nulls_last=True)
    )
