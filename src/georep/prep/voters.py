"""Wahlergebnis je Stimmbezirk zu Wahlbezirken aggregieren.

Entspricht ``src/prep_voters.py`` des Altcodes: Zahlen mit Leerzeichen oder Müll werden 0,
Summen je Wahlbezirk, Wahlbeteiligung als Anteil, Parteianteile an den Wählern. Dieselbe CSV
nennt je Stimmbezirk auch den Stadtbezirk; ``district_units`` typisiert die drei nötigen Spalten
und gibt sie an ``georep.crosswalk.unit_weights`` (Option 05, docs/plans/00-synergien.md, F5).

Die Spalten der Quelle heißen je Wahl anders (2025: ``Wahlberechtigte_insgesamt``, ``Waehler``,
``CDU_Stimmen``; 2020: ``A``, ``B``, ``D1``). Beim Lesen werden sie auf die kanonischen Namen
gebracht, damit ``wahlbezirke_waehler.parquet`` in jeder Periode dasselbe Schema trägt und die
Auswertung sie nicht aus den Settings erfragen muss; für die Hauptperiode ist das ein No-op
(Option 02, docs/plans/02-zeitreihe.md, § 2).
"""

from __future__ import annotations

import io
from collections.abc import Iterable
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

# Option 02: kanonische Namen der veröffentlichten Zählgrößen, gleich in jeder Periode (die
# Namen der Arbeit). Nicht zu verwechseln mit ``ELIGIBLE`` darüber: das ist die kleingeschriebene
# Spalte der Crosswalk-Tabelle (Option 05).
ELIGIBLE_TOTAL = "Wahlberechtigte_insgesamt"
VOTERS = "Waehler"
# Nur innerhalb der Umrechnung gebraucht (Verteilschlüssel der Briefwahl), nie veröffentlicht.
ELIGIBLE_POSTAL = "Wahlberechtigte_mit_Wahlschein"
PRECINCT = "stimmbezirk_id"


def party_column(party: str) -> str:
    """``CDU`` wird ``CDU_Stimmen``: der kanonische Name der Stimmen einer Partei."""
    return f"{party}_Stimmen"


def canonical_names(columns: ResultsColumns) -> dict[str, str]:
    """Quellspalte -> kanonischer Name. Für die Hauptperiode ist jede Zuordnung die Identität."""
    names = {columns.eligible: ELIGIBLE_TOTAL, columns.voters: VOTERS}
    if columns.eligible_postal:
        names[columns.eligible_postal] = ELIGIBLE_POSTAL
    for party, column in columns.parties.items():
        names[column] = party_column(party)
    return names


def count_columns(columns: ResultsColumns) -> list[str]:
    """Die kanonischen Zählspalten in Ausgabereihenfolge: Berechtigte, Wähler, Stimmen je Partei."""
    return [ELIGIBLE_TOTAL, VOTERS, *(party_column(p) for p in columns.parties)]


def read_results_csv(path: Path, columns: ResultsColumns) -> pl.DataFrame:
    """Liest die CSV des Open-Data-Portals (Kodierung aus den Settings, ';') mit allen Spalten als Text.

    Die Zählspalten tragen danach die kanonischen Namen; alle übrigen Spalten bleiben, wie die
    Quelle sie nennt (der Wahlbezirk, die Stimmbezirksnummer, der Gebietsname).
    """
    text = path.read_bytes().decode(columns.encoding)
    frame = pl.read_csv(io.BytesIO(text.encode("utf-8")), separator=columns.sep, infer_schema=False)
    required = [columns.eligible, columns.voters, *columns.parties.values()]
    # Wahlbezirk und Stadtbezirk nennt nicht jede Wahl: die Ratswahl 2020 trägt beides nicht,
    # der Wahlbezirk kommt dort aus der Zuordnung (Option 02) und der Stadtbezirk aus der
    # Hauptperiode (Option 05 rechnet auf dem Zielzuschnitt).
    required += [c for c in (columns.district, columns.city_district) if c]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise SchemaError(f"{path.name}: Pflichtspalten fehlen: {missing}")
    names = canonical_names(columns)
    return frame.rename({c: names[c] for c in frame.columns if c in names})


def _to_int(column: str) -> pl.Expr:
    # pandas: to_numeric(errors="coerce").fillna(0).astype(int); " " und Müll werden 0
    return pl.col(column).str.strip_chars().cast(pl.Int64, strict=False).fill_null(0)


@deal.pre(
    lambda aggregated, parties: (
        has_columns(aggregated, DISTRICT, ELIGIBLE_TOTAL, VOTERS)
        and has_columns(aggregated, *(party_column(p) for p in parties))
    ),
    message="Summen je Wahlbezirk mit den kanonischen Zählspalten",
)
@deal.ensure(
    lambda aggregated, parties, result: (
        result.height == aggregated.height and has_columns(result, TURNOUT)
    ),
    message="dieselben Zeilen, dazu Beteiligung und Parteianteile",
)
def with_shares(aggregated: pl.DataFrame, parties: Iterable[str]) -> pl.DataFrame:
    """Beteiligung und Parteianteile aus den Zählgrößen; der gemeinsame Schluss beider Perioden.

    Anteile entstehen immer **nach** dem Übertrag aus den übertragenen Zählgrößen, nie durch
    Übertrag eines Anteils (Option 02, Plan § 2).
    """
    shares = [
        (pl.col(party_column(party)) / pl.col(VOTERS)).alias(f"{party}_anteil") for party in parties
    ]
    return aggregated.with_columns(
        (pl.col(VOTERS) / pl.col(ELIGIBLE_TOTAL)).alias(TURNOUT), *shares
    )


@deal.pre(
    lambda results, columns: (
        bool(columns.district) and has_columns(results, columns.district, *count_columns(columns))
    ),
    message="Wahlergebnis braucht Wahlbezirk, Berechtigte, Wähler und alle Parteispalten",
)
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.ensure(
    lambda results, columns, result: (
        result.height <= results.height and all_nonnegative(result, *count_columns(columns))
    ),
    message="höchstens ein Wahlbezirk je Stimmbezirk, Summen nicht negativ",
)
def aggregate_voters(results: pl.DataFrame, columns: ResultsColumns) -> pl.DataFrame:
    """Eine Zeile je Wahlbezirk: Berechtigte, Wähler, Stimmen je Partei, Beteiligung, Anteile.

    Der Weg der Hauptperiode: die CSV trägt den Wahlbezirk je Stimmbezirk, es wird nur summiert.
    """
    counts = count_columns(columns)
    frame = results.select(_to_int(columns.district).alias(DISTRICT), *[_to_int(c) for c in counts])
    aggregated = frame.group_by(DISTRICT).agg([pl.col(c).sum() for c in counts]).sort(DISTRICT)
    return with_shares(aggregated, columns.parties)


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
