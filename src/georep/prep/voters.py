"""Wahlergebnis je Stimmbezirk zu Wahlbezirken aggregieren.

Entspricht ``src/prep_voters.py`` des Altcodes: Zahlen mit Leerzeichen oder Müll werden 0,
Summen je Wahlbezirk, Wahlbeteiligung als Anteil, Parteianteile an den Wählern. Dieselbe CSV
nennt je Stimmbezirk auch den Stadtbezirk; ``district_units`` typisiert die drei nötigen Spalten
und gibt sie an ``georep.crosswalk.unit_weights`` (Option 05, docs/plans/00-synergien.md, F5).
"""

from __future__ import annotations

import io
from pathlib import Path

import deal
import polars as pl

from georep.contracts import all_nonnegative, has_columns, sorted_unique
from georep.crosswalk import WEIGHT, unit_weights
from georep.errors import SchemaError
from georep.settings import ResultsColumns

DISTRICT = "wahlkreis_id"
TURNOUT = "wahlbeteiligung"
# Option 05: Spaltennamen der Zuordnung Wahlbezirk zu Stadtbezirk, kleingeschrieben wie im Crosswalk
UNIT = "stadtbezirk"
ELIGIBLE = "wahlberechtigte"


def read_results_csv(path: Path, columns: ResultsColumns) -> pl.DataFrame:
    """Liest die CSV des Open-Data-Portals (latin-1, ';') mit allen Spalten als Text."""
    text = path.read_bytes().decode(columns.encoding)
    frame = pl.read_csv(io.BytesIO(text.encode("utf-8")), separator=columns.sep, infer_schema=False)
    required = [
        columns.district,
        columns.city_district,
        columns.eligible,
        columns.voters,
        *columns.parties.values(),
    ]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise SchemaError(f"{path.name}: Pflichtspalten fehlen: {missing}")
    return frame


def _to_int(column: str) -> pl.Expr:
    # pandas: to_numeric(errors="coerce").fillna(0).astype(int); " " und Müll werden 0
    return pl.col(column).str.strip_chars().cast(pl.Int64, strict=False).fill_null(0)


@deal.pre(
    lambda results, columns: has_columns(
        results, columns.district, columns.eligible, columns.voters, *columns.parties.values()
    ),
    message="Wahlergebnis braucht Wahlbezirk, Berechtigte, Wähler und alle Parteispalten",
)
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.ensure(
    lambda results, columns, result: (
        result.height <= results.height
        and all_nonnegative(result, columns.eligible, columns.voters, *columns.parties.values())
    ),
    message="höchstens ein Wahlbezirk je Stimmbezirk, Summen nicht negativ",
)
def aggregate_voters(results: pl.DataFrame, columns: ResultsColumns) -> pl.DataFrame:
    """Eine Zeile je Wahlbezirk: Berechtigte, Wähler, Stimmen je Partei, Beteiligung, Anteile."""
    counts = [columns.eligible, columns.voters, *columns.parties.values()]
    frame = results.select(_to_int(columns.district).alias(DISTRICT), *[_to_int(c) for c in counts])
    aggregated = frame.group_by(DISTRICT).agg([pl.col(c).sum() for c in counts]).sort(DISTRICT)
    shares = [
        (pl.col(column) / pl.col(columns.voters)).alias(f"{party}_anteil")
        for party, column in columns.parties.items()
    ]
    return aggregated.with_columns(
        (pl.col(columns.voters) / pl.col(columns.eligible)).alias(TURNOUT), *shares
    )


# --- Option 05: Zuordnung Wahlbezirk zu Stadtbezirk ---------------------------------------------


@deal.pre(
    lambda results, columns: has_columns(
        results, columns.district, columns.city_district, columns.eligible
    ),
    message="Wahlergebnis braucht Wahlbezirk, Stadtbezirk und Wahlberechtigte",
)
@deal.post(
    lambda result: result.columns == [DISTRICT, UNIT, ELIGIBLE, WEIGHT],
    message="Wahlbezirk, Einheit, Zählgröße, Gewicht",
)
def district_units(results: pl.DataFrame, columns: ResultsColumns) -> pl.DataFrame:
    """Je (Wahlbezirk, Stadtbezirk) die Wahlberechtigten und ihren Anteil am Wahlbezirk.

    Die Gewichte sagen, welche Bezirksvertretungen für einen Wahlbezirk die „eigenen" sind:
    40 der 41 Wahlbezirke liegen in genau einem Stadtbezirk, einer in zwei (Plan, Entscheidung 4).
    Zeilen ohne Wahlberechtigte (Briefwahlbezirke) fallen im Crosswalk weg; die Verträge dort
    sichern Gewichte in (0, 1] und Summe 1 je Wahlbezirk zu.
    """
    typed = results.select(
        _to_int(columns.district).alias(DISTRICT),
        _to_int(columns.city_district).alias(UNIT),
        _to_int(columns.eligible).alias(ELIGIBLE),
    )
    return unit_weights(typed, UNIT, ELIGIBLE)
