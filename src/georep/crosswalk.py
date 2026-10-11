"""Umrechnung von Gebietseinheiten auf Wahlbezirke.

Jede Option, die Stadtteile, Stadtbezirke, Sozialräume oder einen älteren Zuschnitt auf die
Wahlbezirke bringt, geht über dieses Modul (docs/plans/00-synergien.md, F5). Zwei Wege führen
zum selben Ziel, Gewichte je (Wahlbezirk, Einheit), die je Wahlbezirk zu 1 summieren:

* der Attribut-Crosswalk ``unit_weights``, wenn jeder Stimmbezirk seine Einheit schon als
  Eigenschaft trägt (Stadtteil, Stadtbezirk) -- dann ist die Zuordnung exakt;
* der geometrische Weg ``area_shares`` plus ``district_weights``, wenn die Einheiten eine eigene
  Gliederung sind (Raumeinheiten der Stadt, ein älterer Zuschnitt): Flächenanteile je
  Stimmbezirk, mit den Wahlberechtigten gewichtet.

Gewogen wird mit den Wahlberechtigten je Stimmbezirk, nicht mit der Fläche: Wahlberechtigte sind
die Bezugsgröße von Trefferquote und Wahlbeteiligung, reine Flächenanteile zählten Parks wie
Wohngebiete. Alle Funktionen sind rein, Frame zu Frame, mit Verträgen an der Batch-Grenze -- nicht
in der Schnittflächenschleife (306 × k Aufrufe).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import deal
import polars as pl
import shapely

from georep.contracts import (
    all_nonnegative,
    columns_preserved,
    has_columns,
    sorted_unique,
    sums_to_one,
)
from georep.errors import SchemaError
from georep.geo import Area

DISTRICT = "wahlkreis_id"
WEIGHT = "gewicht"
# Flächenanteile: eine Quellfläche (Stimmbezirk) verteilt sich auf Zielflächen (Raumeinheiten).
# Beide Schlüssel sind Text, denn die Schlüssel der Quellen tragen führende Nullen (``011001``);
# wer Int64 braucht, castet beim Join (docs/plans/00-synergien.md, § 2 Punkt 4).
SOURCE = "source_id"
TARGET = "target_id"
SHARE = "share"
COVERAGE = "coverage"
# Die Stimmbezirkstabelle, die beide Crosswalks wiegt (``georep.prep.context.precinct_table``).
PRECINCT = "stimmbezirk_id"
ELIGIBLE = "wahlberechtigte"
UNIT = "einheit"
UNIT_NAME = "einheit_name"
SHARES_SCHEMA = {SOURCE: pl.String, TARGET: pl.String, SHARE: pl.Float64, COVERAGE: pl.Float64}


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


def _shares_sum_to_one(result: pl.DataFrame) -> bool:
    return sums_to_one(result, SOURCE, SHARE, tol=1e-9)


def _valid_areas(areas: Sequence[Area]) -> bool:
    return len(areas) > 0 and all(a.geometry.area > 0 and a.geometry.is_valid for a in areas)


@deal.pre(
    lambda sources, targets, *, min_coverage=0.9: (
        _valid_areas(sources) and _valid_areas(targets) and 0.0 < min_coverage <= 1.0
    ),
    message="Quell- und Zielflächen mit Fläche, min_coverage in (0, 1]",
)
@deal.post(
    lambda result: (
        _in_unit_interval(result, SHARE)
        and bool((result.get_column(COVERAGE) > 0).all())
        and result.columns == list(SHARES_SCHEMA)
    ),
    message="Anteile in (0, 1], Bedeckung positiv, Spalten wie SHARES_SCHEMA",
)
@deal.post(_shares_sum_to_one, message="die Anteile je Quellfläche summieren zu 1")
@deal.raises(SchemaError)
def area_shares(
    sources: Sequence[Area], targets: Sequence[Area], *, min_coverage: float = 0.9
) -> pl.DataFrame:
    """Je Quellfläche die Zielflächen mit ihrem Anteil an der bedeckten Fläche.

    ``source_id``, ``target_id``, ``share`` (auf die Schnittsumme normiert, je Quelle Summe 1) und
    ``coverage`` (bedeckte Fläche geteilt durch die Fläche der Quelle, je Quelle gleich). Normiert
    wird auf die Schnittsumme und nicht auf die Quellfläche, damit die Anteile auch dann zu 1
    summieren, wenn die Grenzen zweier Portaldateien um Meter abweichen; wie groß die Abweichung
    ist, sagt ``coverage``. Liegt sie unter ``min_coverage``, ist das ein ``SchemaError``: dann
    gehören die beiden Gliederungen nicht zum selben Gebiet.

    Ein STRtree über die Zielflächen spart die 306 × 171 Schnitte; ohne ihn dauerte es Minuten.
    """
    tree = shapely.STRtree([t.geometry for t in targets])
    rows: list[tuple[str, str, float, float]] = []
    for source in sources:
        pieces = [
            (targets[int(i)].key, area)
            for i in tree.query(source.geometry)
            if (area := source.geometry.intersection(targets[int(i)].geometry).area) > 0.0
        ]
        covered = sum(area for _, area in pieces)
        coverage = covered / source.geometry.area
        if coverage < min_coverage:
            raise SchemaError(
                f"Quellfläche {source.key} ist nur zu {coverage:.4f} von Zielflächen bedeckt "
                f"(mindestens {min_coverage}); passen die beiden Gliederungen zusammen?"
            )
        rows.extend((source.key, key, area / covered, coverage) for key, area in pieces)
    # Nach den Schlüsseln sortiert, nicht nach dem Anteil: bei gleich großen Anteilen entscheidet
    # sonst das letzte Bit der Fließkommazahl über die Reihenfolge (hypothesis, 2026-10-12).
    return pl.DataFrame(rows, schema=SHARES_SCHEMA, orient="row").sort([SOURCE, TARGET])


def _districts_of_the_table(
    table: pl.DataFrame, shares: pl.DataFrame, result: pl.DataFrame | None = None
) -> bool:
    assert result is not None
    known = set(shares.get_column(SOURCE))
    counted = table.filter(pl.col(PRECINCT).is_in(known) & (pl.col(ELIGIBLE) > 0))
    return set(result.get_column(DISTRICT)) == set(counted.get_column(DISTRICT))


@deal.pre(
    lambda table, shares: (
        has_columns(table, PRECINCT, DISTRICT, ELIGIBLE)
        and all_nonnegative(table, ELIGIBLE)
        and has_columns(shares, SOURCE, TARGET, SHARE)
    ),
    message="Stimmbezirkstabelle mit Wahlberechtigten und Flächenanteile je Stimmbezirk",
)
@deal.post(lambda result: _in_unit_interval(result, WEIGHT), message="Gewichte in (0, 1]")
@deal.post(
    lambda result: sums_to_one(result, DISTRICT, WEIGHT),
    message="die Gewichte je Wahlbezirk summieren zu 1",
)
@deal.ensure(_districts_of_the_table, message="genau die Wahlbezirke mit Anteilen kommen vor")
def district_weights(table: pl.DataFrame, shares: pl.DataFrame) -> pl.DataFrame:
    """Gewicht einer Einheit im Wahlbezirk: Wahlberechtigte × Flächenanteil, je Wahlbezirk normiert.

    Eingaben: eine Zeile je Stimmbezirk (``precinct_table``) und die Flächenanteile aus
    ``area_shares``. Stimmbezirke ohne Zählgröße fallen weg wie in ``unit_weights``, darum kann
    ein Wahlbezirk fehlen, in dem niemand wahlberechtigt ist -- sonst stünde dort 0/0. Ausgabe ``wahlkreis_id``, ``einheit``, ``gewicht``, sortiert nach Wahlbezirk
    und Gewicht absteigend -- dieselbe Form wie ``unit_weights``, damit beide Wege vergleichbar
    sind. Normiert wird über die Stimmbezirke mit Anteilen, nicht über alle: ein Stimmbezirk ohne
    Zielfläche würde die Summe sonst unter 1 drücken (``area_shares`` lässt ihn aber ohnehin nicht
    durch).
    """
    # Sortieren und maintain_order: ein Join legt die Zeilenfolge nicht fest, und eine
    # Fließkommasumme hängt von ihr im letzten Bit ab; zwei Läufe sollen dieselbe Parquet-Datei
    # schreiben (2026-10-12).
    joined = (
        table.filter(pl.col(ELIGIBLE) > 0)  # wie unit_weights: ohne Zählgröße kein Gewicht
        .join(shares.select(SOURCE, TARGET, SHARE), left_on=PRECINCT, right_on=SOURCE)
        .sort([DISTRICT, TARGET, PRECINCT])
    )
    weighted = (
        joined.with_columns((pl.col(ELIGIBLE) * pl.col(SHARE)).alias("_w"))
        .group_by(DISTRICT, TARGET, maintain_order=True)
        .agg(pl.col("_w").sum())
    )
    totals = weighted.group_by(DISTRICT, maintain_order=True).agg(
        pl.col("_w").sum().alias("_total")
    )
    return (
        weighted.join(totals, on=DISTRICT)
        .with_columns((pl.col("_w") / pl.col("_total")).alias(WEIGHT))
        # Gewicht 0 fällt weg, wie in unit_weights: eine Einheit ohne Gewicht trägt zu keinem
        # Mittel bei, stünde aber als Zeile in der veröffentlichten Tabelle. Null wird ein Gewicht
        # nur, wenn ein Flächenanteil schon an der Grenze der Fließkommazahlen liegt
        # (hypothesis, 2026-10-12).
        .filter(pl.col(WEIGHT) > 0)
        .select(pl.col(DISTRICT), pl.col(TARGET).alias(UNIT), pl.col(WEIGHT))
        .sort([DISTRICT, WEIGHT, UNIT], descending=[False, True, False])
    )


# --- Option 02: ein älterer Zuschnitt auf die Wahlbezirke von heute ---------------------------
#
# ``area_shares`` oben liefert die Flächenanteile; hier kommt dazu, was eine *Periode* braucht:
# die Zuordnung innerhalb eines Zuschnitts (``assign_by_point``), der Übertrag additiver
# Zählgrößen (``transfer_counts`` mit ``largest_remainder``) und dieselbe Umrechnung als Gewichte
# je Zielbezirk (``target_weights``). Die Schlüssel bleiben, wie ``area_shares`` sie gibt; wer
# ganzzahlige Zielbezirke braucht, castet vorher (der Schritt ``precincts`` tut das, damit die
# Reste beim Runden an die numerisch sortierten Bezirke gehen).


def _targets_known(
    sources: Sequence[Area],
    targets: Sequence[Area],
    result: dict[str, str] | None = None,
) -> bool:
    assert result is not None
    return set(result) == {s.key for s in sources} and set(result.values()) <= {
        t.key for t in targets
    }


@deal.pre(lambda sources, targets: bool(sources) and bool(targets))
@deal.ensure(_targets_known, message="jede Quelle genau ein Ziel, jedes Ziel aus der Eingabe")
@deal.raises(SchemaError)
def assign_by_point(sources: Sequence[Area], targets: Sequence[Area]) -> dict[str, str]:
    """Jede Quellfläche dem Ziel, in dem ihr repräsentativer Punkt liegt.

    Für die Zuordnung Stimmbezirk zu Wahlbezirk **desselben** Zuschnitts: dort ist die Quelle
    ganz im Ziel enthalten, ein Punkt genügt und ist billiger als die Schnittfläche. Keiner oder
    mehrere Treffer sind ein Datenfehler (falsches CRS, überlappende Ziele), nicht ein Grenzfall:
    der Fehler nennt die Quelle. Für Zuschnitte, die sich unterscheiden, ist ``area_shares``
    zuständig.
    """
    tree = shapely.STRtree([t.geometry for t in targets])
    found: dict[str, str] = {}
    for source in sorted(sources, key=lambda s: s.key):
        hits = tree.query(source.geometry.representative_point(), predicate="within")
        if len(hits) != 1:
            raise SchemaError(
                f"Quelle {source.key!r}: {len(hits)} Zielflächen enthalten ihren Punkt, genau eine "
                "wird erwartet (gleicher Zuschnitt, gleiches CRS?)"
            )
        found[source.key] = targets[int(hits[0])].key
    return found


@deal.pre(
    lambda shares, counts, weight_column: (
        has_columns(shares, SOURCE, TARGET, SHARE)
        and has_columns(counts, SOURCE, weight_column)
        and all_nonnegative(counts, weight_column)
        and counts.get_column(SOURCE).n_unique() == counts.height
        and sums_to_one(shares, SOURCE, SHARE)
    ),
    message="Anteile je Quelle mit Summe 1 und genau eine nicht negative Zählgröße je Quelle",
)
@deal.post(lambda result: result.columns == [SOURCE, TARGET, WEIGHT])
@deal.post(lambda result: _in_unit_interval(result, WEIGHT), message="Gewichte in (0, 1]")
@deal.post(
    lambda result: sums_to_one(result, TARGET, WEIGHT),
    message="die Gewichte je Zielbezirk summieren zu 1",
)
def target_weights(shares: pl.DataFrame, counts: pl.DataFrame, weight_column: str) -> pl.DataFrame:
    """Gewicht jeder Quelle **am Ziel**: Flächenanteil mal Zählgröße, je Ziel auf 1 normiert.

    Damit ist ein Anteil (Wahlbeteiligung, Stimmenanteil) direkt übertragbar, ohne dass Zähler
    und Nenner getrennt gerechnet werden; ``transfer_counts`` geht den anderen Weg und ist für
    Zählgrößen das Genauere. Zeilen mit Gewicht 0 fallen weg, ein Ziel ohne Zählgröße fehlt.

    ``counts`` trägt eine Zeile je Quelle, wie bei ``transfer_counts``: eine Dublette würde den
    Join vervielfachen und die Gewichte still verschieben, statt aufzufallen.
    """
    joined = (
        shares.join(counts.select(SOURCE, weight_column), on=SOURCE, how="inner")
        .with_columns((pl.col(SHARE) * pl.col(weight_column)).alias(WEIGHT))
        .filter(pl.col(WEIGHT) > 0.0)
    )
    totals = joined.group_by(TARGET).agg(pl.col(WEIGHT).sum().alias("_total"))
    return (
        joined.join(totals, on=TARGET)
        .with_columns((pl.col(WEIGHT) / pl.col("_total")).alias(WEIGHT))
        .select(SOURCE, TARGET, WEIGHT)
        .sort([TARGET, WEIGHT, SOURCE], descending=[False, True, False])
    )


def _rounded_total(values: Sequence[float]) -> int:
    """Die Summe der Eingabe als ganze Zahl; dieselbe Rechnung im Vertrag wie in der Funktion."""
    return round(math.fsum(values))


@deal.pure
@deal.pre(
    lambda values: all(math.isfinite(v) and v >= 0.0 for v in values),
    message="nicht negative, endliche Zählgrößen",
)
@deal.ensure(
    lambda values, result: (
        len(result) == len(values)
        and sum(result) == _rounded_total(values)
        and all(abs(n - v) < 1.0 for n, v in zip(result, values, strict=True))
    ),
    message="gleiche Länge, Summe erhalten, jeder Wert weicht um weniger als 1 ab",
)
def largest_remainder(values: Sequence[float]) -> list[int]:
    """Nicht ganzzahlige Zählgrößen ganzzahlig machen, ohne die Summe zu verändern.

    Jeder Wert wird abgerundet; die fehlenden Einheiten gehen an die größten Reste, bei gleichem
    Rest an den kleineren Index (damit das Ergebnis reproduzierbar ist). Das ist das Verfahren
    des größten Restes (Hare-Niemeyer); ohne es würden 41 gerundete Bezirkswerte die Stadtsumme
    um einige Personen verfehlen.
    """
    floors = [math.floor(v) for v in values]
    rest = _rounded_total(values) - sum(floors)
    order = sorted(range(len(values)), key=lambda i: (floors[i] - values[i], i))
    result = list(floors)
    for i in order[: max(rest, 0)]:
        result[i] += 1
    return result


@deal.pre(
    lambda counts, shares, columns: (
        len(columns) > 0
        and has_columns(counts, SOURCE, *columns)
        and has_columns(shares, SOURCE, TARGET, SHARE)
        and all_nonnegative(counts, *columns)
        and counts.get_column(SOURCE).n_unique() == counts.height
        and set(shares.get_column(SOURCE)) == set(counts.get_column(SOURCE))
    ),
    message="eine Zeile je Quelle mit nicht negativen Zählgrößen, Anteile über genau diese Quellen",
)
@deal.post(lambda result: sorted_unique(result, TARGET))
@deal.ensure(
    lambda counts, shares, columns, result: columns_preserved(counts, result, columns),
    message="die Spaltensummen bleiben exakt erhalten",
)
@deal.ensure(
    lambda counts, shares, columns, result: all_nonnegative(result, *columns),
    message="keine negativen Zählgrößen",
)
def transfer_counts(
    counts: pl.DataFrame, shares: pl.DataFrame, columns: Sequence[str]
) -> pl.DataFrame:
    """Zählgrößen von den Quellflächen auf die Zielflächen übertragen, ganzzahlig und summentreu.

    Anteil mal Wert, Summe je Ziel, dann ``largest_remainder`` je Spalte. Nur additive Größen
    dürfen hier durch (Wahlberechtigte, Wähler, Stimmen); Anteile und Quoten entstehen **danach**
    aus den übertragenen Zählgrößen, nie durch Übertrag des Anteils. Sortiert wird nach dem
    Zielschlüssel, und in dieser Reihenfolge gehen die Reste: steht dort Text statt Zahlen, käme
    „10" vor „2" -- der Aufrufer castet darum vorher.
    """
    summed = (
        shares.join(counts.select(SOURCE, *columns), on=SOURCE, how="inner")
        .group_by(TARGET)
        .agg([(pl.col(SHARE) * pl.col(c)).sum().alias(c) for c in columns])
        .sort(TARGET)
    )
    return summed.with_columns(
        [
            pl.Series(c, largest_remainder(summed.get_column(c).to_list()), dtype=pl.Int64)
            for c in columns
        ]
    )
