"""Verträge (deal): der Schalter aus ``settings.contracts`` und die Prädikate, aus denen sie bestehen.

Verträge prüfen Vor- und Nachbedingungen an Batch-Grenzen (docs/architecture.md, „Verträge").
Eine Verletzung ist ein Programmierfehler, kein Domänenfehler: sie läuft als ``deal.ContractError``
durch und wird nicht am Rand gefangen. ``"off"`` ruft ``deal.disable``, die Funktionen laufen dann
ohne Prüfung; der gemessene Overhead steht in ``docs/profiling/README.md``. Der Schalter wirkt
prozessweit und zählt nicht zum Settings-Fingerprint.

Die Prädikate hier sind reine Funktionen auf Polars-Frames, damit ein Vertrag am Decorator lesbar
bleibt (``sorted_unique(result, DISTRICT)``) und dieselbe Eigenschaft überall dasselbe heißt.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Literal

import deal
import polars as pl

Mode = Literal["on", "off"]


def configure(mode: Mode) -> None:
    """Prozessweit: ``"on"`` prüft, ``"off"`` prüft nicht. Ohne deals Umgebungswarnung: der Schalter ist Absicht."""
    if mode == "off":
        deal.disable(warn=False)
    else:
        deal.enable(warn=False)


def has_columns(frame: pl.DataFrame, *columns: str) -> bool:
    return set(columns) <= set(frame.columns)


def sorted_unique(frame: pl.DataFrame, column: str) -> bool:
    """Die Spalte ist aufsteigend sortiert und ohne Dubletten: eine Zeile je Schlüssel."""
    series = frame.get_column(column)
    return bool(series.is_sorted()) and series.n_unique() == frame.height


def lists_sorted_unique(frame: pl.DataFrame, column: str) -> bool:
    """Jede Liste der Spalte ist sortiert und ohne Dubletten (eine Begriffs- oder ID-Liste)."""
    return all(items == sorted(set(items)) for items in frame.get_column(column).to_list())


def all_nonnegative(frame: pl.DataFrame, *columns: str) -> bool:
    return all(bool((frame.get_column(c) >= 0).all()) for c in columns)


def in_unit_interval(frame: pl.DataFrame, *columns: str) -> bool:
    """Jede Spalte liegt in [0, 1]: ein Gewicht ist ein Anteil, nie größer als das Ganze."""
    return all(
        bool(((frame.get_column(c) >= 0.0) & (frame.get_column(c) <= 1.0)).all()) for c in columns
    )


def clean_terms(terms: list[str]) -> bool:
    """Suchbegriffe, wie das Wörterbuch sie liefert: nicht leer, getrimmt, kleingeschrieben, ohne Komma."""
    return all(t and t == t.strip().lower() and "," not in t for t in terms)


def one_row_per_document(
    frame: pl.DataFrame, corpus_ids: Iterable[str], column: str = "id"
) -> bool:
    """Genau eine Zeile je Korpus-ID: die Spalte ist aufsteigend, eindeutig und trägt genau die IDs.

    Der gemeinsame Vertrag der Tabellen ``dokumente_<attribut>.parquet``
    (docs/plans/00-synergien.md, § 5.6): Option 04 bringt den Urheber, 05 das Gremium, 06 die
    Gewichte, alle mit demselben Schlüssel.
    """
    return sorted_unique(frame, column) and frame.get_column(column).to_list() == sorted(corpus_ids)


def sums_to_one(frame: pl.DataFrame, group: str, column: str, tol: float = 1e-9) -> bool:
    """Die Spalte summiert je Gruppe zu 1: Gewichte einer Umrechnung je Zielbezirk."""
    sums = frame.group_by(group).agg(pl.col(column).sum())
    return bool(((sums.get_column(column) - 1.0).abs() <= tol).all())


def shares_in_unit_interval(frame: pl.DataFrame, *columns: str) -> bool:
    """Jede Spalte ist ein Anteil: Wert in [0, 1] und nie null."""
    return all(
        frame.get_column(c).null_count() == 0
        and bool(((frame.get_column(c) >= 0.0) & (frame.get_column(c) <= 1.0)).all())
        for c in columns
    )


def parts_sum_to(frame: pl.DataFrame, parts: Sequence[str], total: str) -> bool:
    """Die Teile ergeben je Zeile die Gesamtzahl: eine Zerlegung ohne Rest und ohne Doppelzählung."""
    if not has_columns(frame, total, *parts):
        return False
    checked = frame.select(pl.sum_horizontal(parts).alias("_parts"), pl.col(total))
    return bool((checked.get_column("_parts") == checked.get_column(total)).all())


def columns_preserved(before: pl.DataFrame, after: pl.DataFrame, columns: Sequence[str]) -> bool:
    """Jede Zählspalte hat nach der Umrechnung dieselbe Summe wie vorher, ganzzahlig genau.

    Die Nachbedingung des Übertrags auf einen anderen Gebietszuschnitt: Wahlberechtigte, Wähler
    und Stimmen sind additiv, also darf die Stadtsumme sich nicht um eine Person verschieben.
    Vorher darf gerundet werden (Anteile sind Fließkomma), nachher muss es ganzzahlig stimmen.
    """
    return all(
        int(after.get_column(c).sum()) == round(float(before.get_column(c).sum())) for c in columns
    )


# Option 07: Monitoring. Eine Monatsreihe hat zwei Eigenheiten, die ``sorted_unique`` nicht deckt:
# der Schlüssel ist ein Paar, und eine Zeile darf einen leeren Monat tragen (Dokumente ohne Datum).
def next_month(month: date) -> date:
    """Der Erste des folgenden Monats."""
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


def months_in_order(frame: pl.DataFrame, column: str) -> bool:
    """Monatserste, lückenlos aufsteigend, jeder einmal; höchstens ein leerer, und der am Ende."""
    months = frame.get_column(column).to_list()
    dated = [m for m in months if m is not None]
    if months[: len(dated)] != dated or len(months) - len(dated) > 1:
        return False  # leere Monate nur am Ende, und höchstens einer
    return all(m.day == 1 for m in dated) and all(
        next_month(a) == b for a, b in zip(dated, dated[1:], strict=False)
    )


def keys_sorted_unique(frame: pl.DataFrame, *columns: str) -> bool:
    """Die Spalten bilden einen aufsteigend sortierten Schlüssel, jeder einmal; leere zuletzt.

    Ein leerer Wert wird zu ``(1,)`` und steht damit in seiner Spalte hinter jedem ``(0, Wert)``;
    so vergleicht Python nie ``None`` mit einem Datum.
    """
    rows = frame.select(*columns).rows()
    keys = [tuple((1,) if value is None else (0, value) for value in row) for row in rows]
    return keys == sorted(keys) and len(set(rows)) == len(rows)


def one_threshold(quantile: float, median_factor: float) -> bool:
    """Genau eine Schwelle für die stadtweiten Begriffe, oder keine (decisions.md, Punkt 44b).

    Ein Quantil liegt in [0, 1), ein Vielfaches des Medians ist nicht negativ, und beide zugleich
    wären zwei Wahrheiten. Dasselbe Prädikat prüft den Vertrag von ``citywide_terms`` und der
    Validator von ``settings.Search``, damit die Regel nur an einer Stelle steht.
    """
    return 0.0 <= quantile < 1.0 and median_factor >= 0.0 and not (quantile and median_factor)
