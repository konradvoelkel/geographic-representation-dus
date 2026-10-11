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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import deal
import polars as pl

from georep.contracts import (
    all_nonnegative,
    columns_preserved,
    has_columns,
    sorted_unique,
)
from georep.crosswalk import WEIGHT, largest_remainder, unit_weights
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


# --- Option 02: Wählerzahlen eines älteren Zuschnitts -----------------------------------------
#
# Die Ratswahl-CSV von 2020 trägt keinen Wahlbezirk, und 138 ihrer 454 Zeilen sind
# Briefwahlbezirke ohne Geometrie. Der Weg ist darum: Urnenstimmbezirke lesen, die Briefwahl je
# Wahlbezirk aus der Wahlbezirks-CSV erschließen (dort steht die Gesamtzahl) und proportional zu
# den Wahlberechtigten mit Wahlschein auf die Stimmbezirke verteilen; danach übernimmt der
# Crosswalk. Jede Stufe prüft ihre Summe gegen die Quelle, denn ein Fehler in der Zuordnung wäre
# sonst erst an einer plausibel aussehenden Wahlbeteiligung zu erkennen.

SOURCE_DISTRICT = "wahlbezirk_quelle"


@dataclass(frozen=True)
class PrecinctResults:
    """Die Ergebniszeilen einer Wahl, getrennt in Urnen- und Briefwahlbezirke."""

    urn: pl.DataFrame  # eine Zeile je Stimmbezirk mit Geometrie
    postal: pl.DataFrame  # die Briefwahlbezirke; nur die Summenprobe liest sie


def _precinct_input(columns: ResultsColumns) -> list[str]:
    return [columns.precinct, columns.precinct_name, ELIGIBLE_POSTAL, *count_columns(columns)]


@deal.pre(
    lambda results, columns: (
        bool(columns.precinct)
        and bool(columns.postal_marker)
        and has_columns(results, *_precinct_input(columns))
    ),
    message="Stimmbezirksergebnis mit Nummer, Name, Wahlscheinen und allen Zählspalten",
)
@deal.ensure(
    lambda results, columns, result: (
        result.urn.height + result.postal.height == results.height
        and sorted_unique(result.urn, PRECINCT)
        and all_nonnegative(result.urn, ELIGIBLE_POSTAL, *count_columns(columns))
    ),
    message="jede Zeile ist Urne oder Briefwahl, eine Zeile je Stimmbezirk, nichts negativ",
)
@deal.raises(SchemaError)
def precinct_counts(results: pl.DataFrame, columns: ResultsColumns) -> PrecinctResults:
    """Die Zählgrößen je Stimmbezirk; Briefwahlbezirke stehen getrennt (sie haben keine Fläche)."""
    frame = results.select(
        pl.col(columns.precinct).str.strip_chars().alias(PRECINCT),
        pl.col(columns.precinct_name).alias("_name"),
        *[_to_int(c) for c in (ELIGIBLE_POSTAL, *count_columns(columns))],
    )
    postal_row = pl.col("_name").str.contains(columns.postal_marker, literal=True)
    urn = frame.filter(~postal_row).drop("_name").sort(PRECINCT)
    if urn.get_column(PRECINCT).n_unique() != urn.height:
        raise SchemaError(f"{columns.precinct}: Stimmbezirksnummern doppelt in der Ergebnis-CSV")
    return PrecinctResults(urn=urn, postal=frame.filter(postal_row).drop("_name"))


@deal.pre(
    lambda results, columns: (
        bool(columns.precinct) and has_columns(results, columns.precinct, *count_columns(columns))
    ),
    message="Wahlbezirksergebnis mit Nummer und allen Zählspalten",
)
@deal.post(lambda result: sorted_unique(result, SOURCE_DISTRICT))
def district_results(results: pl.DataFrame, columns: ResultsColumns) -> pl.DataFrame:
    """Die Zählgrößen je Wahlbezirk des alten Zuschnitts: der Maßstab, gegen den alles geprüft wird."""
    counts = count_columns(columns)
    return (
        results.select(
            _to_int(columns.precinct).alias(SOURCE_DISTRICT), *[_to_int(c) for c in counts]
        )
        .group_by(SOURCE_DISTRICT)
        .agg([pl.col(c).sum() for c in counts])
        .sort(SOURCE_DISTRICT)
    )


def _spread_in_group(missing: int, weights: Sequence[int]) -> list[int]:
    """``missing`` Personen proportional zu ``weights`` verteilen, ganzzahlig und summentreu.

    Ohne Gewichte (kein Stimmbezirk des Wahlbezirks hat Wahlscheine) wird gleichmäßig verteilt;
    das kommt in den Daten von 2020 nicht vor, wäre aber sonst eine stille Division durch Null.
    """
    total = sum(weights)
    if total == 0:
        return largest_remainder([missing / len(weights)] * len(weights))
    return largest_remainder([missing * w / total for w in weights])


def _postal_totals_match(
    urn: pl.DataFrame,
    assignment: Mapping[str, int],
    districts: pl.DataFrame,
    counts: Sequence[str],
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return columns_preserved(districts, result, counts)


@deal.pre(
    lambda urn, assignment, districts, counts: (
        len(counts) > 0
        and has_columns(urn, PRECINCT, ELIGIBLE_POSTAL, *counts)
        and has_columns(districts, SOURCE_DISTRICT, *counts)
        and set(urn.get_column(PRECINCT)) == set(assignment)
        and set(assignment.values()) == set(districts.get_column(SOURCE_DISTRICT))
    ),
    message="Zuordnung über genau die Urnenstimmbezirke und genau die Wahlbezirke der CSV",
)
@deal.post(lambda result: sorted_unique(result, PRECINCT))
@deal.ensure(_postal_totals_match, message="jede Spaltensumme gleich der Wahlbezirks-CSV")
@deal.raises(SchemaError)
def spread_postal(
    urn: pl.DataFrame,
    assignment: Mapping[str, int],
    districts: pl.DataFrame,
    counts: Sequence[str],
) -> pl.DataFrame:
    """Die Briefwahl eines Wahlbezirks auf seine Stimmbezirke verteilen, nach Wahlscheinen gewichtet.

    Was die Wahlbezirkszeile mehr ausweist als die Summe ihrer Urnenstimmbezirke, ist die
    Briefwahl: ein Modell, keine Messung, denn die Briefwahlbezirke haben keine Geometrie. Als
    Verteilschlüssel dienen die Wahlberechtigten mit Sperrvermerk, also die mit Wahlschein; die
    Alternative (alle Wahlberechtigten) verschiebt die Wahlbeteiligung je Bezirk um bis zu 5,1
    Prozentpunkte (Plan § 3.4, Frage 2.4). Die Wahlberechtigten selbst werden nicht verteilt, sie
    stehen vollständig bei den Urnenstimmbezirken; dass das stimmt, ist die Summenprobe, die
    zugleich die geometrische Zuordnung absichert.
    """
    ordered = urn.with_columns(
        pl.col(PRECINCT).replace_strict(assignment, return_dtype=pl.Int64).alias(SOURCE_DISTRICT)
    ).sort([SOURCE_DISTRICT, PRECINCT])
    seen = ordered.group_by(SOURCE_DISTRICT).agg([pl.col(c).sum() for c in counts])
    gap = (
        districts.join(seen, on=SOURCE_DISTRICT, suffix="_urne")
        .select(SOURCE_DISTRICT, *[(pl.col(c) - pl.col(f"{c}_urne")).alias(c) for c in counts])
        .sort(SOURCE_DISTRICT)
    )
    off = gap.filter(pl.col(ELIGIBLE_TOTAL) != 0)
    if off.height:
        raise SchemaError(
            "Zuordnung passt nicht zur Wahlbezirks-CSV: in "
            f"{off.height} Wahlbezirken weichen die Wahlberechtigten der Urnenstimmbezirke ab "
            f"(zuerst {off.get_column(SOURCE_DISTRICT).to_list()[:5]})"
        )
    negative = [c for c in counts if not bool((gap.get_column(c) >= 0).all())]
    if negative:
        raise SchemaError(
            f"Mehr Urnenstimmen als im Wahlbezirk gemeldet, Spalten {negative}: die Zuordnung der "
            "Stimmbezirke zu den Wahlbezirken kann nicht stimmen"
        )
    spread: dict[str, list[int]] = {c: [] for c in counts if c != ELIGIBLE_TOTAL}
    gaps = {
        int(row[SOURCE_DISTRICT]): {c: int(row[c]) for c in spread}
        for row in gap.iter_rows(named=True)
    }
    for district, group in ordered.group_by(SOURCE_DISTRICT, maintain_order=True):
        weights = [int(w) for w in group.get_column(ELIGIBLE_POSTAL).to_list()]
        for column, values in spread.items():
            values.extend(_spread_in_group(gaps[int(district[0])][column], weights))
    return (
        ordered.with_columns(
            [(pl.col(c) + pl.Series(c, v, dtype=pl.Int64)).alias(c) for c, v in spread.items()]
        )
        .drop(SOURCE_DISTRICT)
        .sort(PRECINCT)
    )


@deal.pre(
    lambda postal, gap_column, expected: bool(gap_column) and has_columns(postal, gap_column),
    message="Briefwahlzeilen mit der geprüften Zählspalte",
)
@deal.raises(SchemaError)
def check_postal_total(postal: pl.DataFrame, gap_column: str, expected: int) -> int:
    """Die Briefwahlzeilen müssen genau die Lücke füllen, die die Urnenstimmbezirke lassen.

    Zwei unabhängige Wege zur selben Zahl: die Summe der 138 Briefwahlbezirke und die Differenz
    zwischen den 41 Wahlbezirkszeilen und ihren Urnenstimmbezirken. Stimmen sie nicht überein,
    ist eine der drei Dateien nicht die, für die wir sie halten.
    """
    found = int(postal.get_column(gap_column).sum())
    if found != expected:
        raise SchemaError(
            f"Briefwahl: die Briefwahlbezirke melden {found} in {gap_column}, aus den "
            f"Wahlbezirkszeilen folgen {expected}; die drei Dateien passen nicht zusammen"
        )
    return found
