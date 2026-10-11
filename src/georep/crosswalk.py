"""Umrechnung von Gebietseinheiten auf Wahlbezirke.

Jede Option, die Stadtteile, Stadtbezirke, Sozialräume oder einen älteren Zuschnitt auf die
Wahlbezirke bringt, geht über dieses Modul (docs/plans/00-synergien.md, F5): ``unit_weights`` ist
der Attribut-Crosswalk, der je Wahlbezirk die Einheiten mit einer Zählgröße je Stimmbezirk
(Wahlberechtigte) wiegt. Flächenanteile (``area_shares``) und der Übertrag von Zählgrößen auf
einen anderen Zuschnitt (``transfer_counts``) kommen mit den Optionen 3 und 2 hinzu; alle
Funktionen sind rein, Frame zu Frame, mit Verträgen an der Batch-Grenze.
"""

from __future__ import annotations

import deal
import polars as pl

from georep.contracts import all_nonnegative, has_columns, sums_to_one

DISTRICT = "wahlkreis_id"
WEIGHT = "gewicht"


def _in_unit_interval(frame: pl.DataFrame, column: str) -> bool:
    series = frame.get_column(column)
    return bool((series > 0).all()) and bool((series <= 1.0).all())


def _districts_with_weight(
    frame: pl.DataFrame,
    unit: str,
    weight: str,
    district: str = DISTRICT,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    expected = set(frame.filter(pl.col(weight) > 0).get_column(district))
    return set(result.get_column(DISTRICT)) == expected


@deal.pre(
    lambda frame, unit, weight, district=DISTRICT: (
        has_columns(frame, district, unit, weight) and all_nonnegative(frame, weight)
    ),
    message="Stimmbezirkstabelle mit Wahlbezirk, Einheit und nicht negativer Zählgröße",
)
@deal.post(lambda result: _in_unit_interval(result, WEIGHT), message="Gewichte in (0, 1]")
@deal.post(
    lambda result: sums_to_one(result, DISTRICT, WEIGHT),
    message="die Gewichte je Wahlbezirk summieren zu 1",
)
@deal.ensure(_districts_with_weight, message="jeder Wahlbezirk mit Zählgröße kommt vor")
def unit_weights(
    frame: pl.DataFrame, unit: str, weight: str, district: str = DISTRICT
) -> pl.DataFrame:
    """Je (Wahlbezirk, Einheit) die Summe von ``weight`` und ihr Anteil am Wahlbezirk.

    Eingabe: eine Zeile je Stimmbezirk mit Wahlbezirk, Einheit (Stadtteil, Stadtbezirk, …) und
    einer ganzzahligen Zählgröße; der Aufrufer hat die Spalten schon typisiert. Ausgabe:
    ``wahlkreis_id``, ``<unit>``, ``<weight>`` (Summe), ``gewicht``; sortiert nach Wahlbezirk,
    Gewicht absteigend, Einheit. Zeilen mit Zählgröße 0 (Briefwahlbezirke ohne Wahlberechtigte)
    fallen weg, darum kann ein Wahlbezirk ohne Zählgröße fehlen.
    """
    grouped = (
        frame.select(pl.col(district).alias(DISTRICT), pl.col(unit), pl.col(weight))
        .filter(pl.col(weight) > 0)
        .group_by(DISTRICT, unit)
        .agg(pl.col(weight).sum())
    )
    totals = grouped.group_by(DISTRICT).agg(pl.col(weight).sum().alias("_total"))
    return (
        grouped.join(totals, on=DISTRICT)
        .with_columns((pl.col(weight) / pl.col("_total")).alias(WEIGHT))
        .drop("_total")
        .sort([DISTRICT, WEIGHT, unit], descending=[False, True, False])
    )
