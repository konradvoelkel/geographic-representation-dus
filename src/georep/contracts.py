"""Verträge (deal): der Schalter aus ``settings.contracts`` und die Prädikate, aus denen sie bestehen.

Verträge prüfen Vor- und Nachbedingungen an Batch-Grenzen (DEVELOPMENT_PLAN.md § 4, Phase 6).
Eine Verletzung ist ein Programmierfehler, kein Domänenfehler: sie läuft als ``deal.ContractError``
durch und wird nicht am Rand gefangen. ``"off"`` ruft ``deal.disable``, die Funktionen laufen dann
ohne Prüfung; der gemessene Overhead steht in ``docs/profiling/README.md``. Der Schalter wirkt
prozessweit und zählt nicht zum Settings-Fingerprint.

Die Prädikate hier sind reine Funktionen auf Polars-Frames, damit ein Vertrag am Decorator lesbar
bleibt (``sorted_unique(result, DISTRICT)``) und dieselbe Eigenschaft überall dasselbe heißt.
"""

from __future__ import annotations

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


def clean_terms(terms: list[str]) -> bool:
    """Suchbegriffe, wie das Wörterbuch sie liefert: nicht leer, getrimmt, kleingeschrieben, ohne Komma."""
    return all(t and t == t.strip().lower() and "," not in t for t in terms)
