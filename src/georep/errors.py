"""Domänenfehler: erwartbare Zustände, die ein Schritt meldet, statt still weiterzumachen.

Vertragsverletzungen (deal, seit Phase 6) sind keine Domänenfehler; sie sind Programmierfehler
und laufen durch. deal.raises vergleicht exakte Typen, keine Unterklassen: darum wandeln die
Fetcher jede requests-Ausnahme in ``NetworkError`` um, statt die Unterklassen aufzuzählen. Diese Klassen hier werden an genau einer Stelle behandelt: am Rand, wo der
Lauf gestartet wurde (``run.py``, später die CLI), mit Exit-Code ungleich null.
"""

from __future__ import annotations


class GeorepError(Exception):
    """Basis aller Domänenfehler."""


class MissingInputError(GeorepError):
    """Eine Eingabe fehlt oder ist leer; der Schritt läuft gar nicht erst an."""


class EmptyResultError(GeorepError):
    """Ein Schritt hätte ein leeres oder kleineres Ergebnis geschrieben; er schreibt nichts."""


class SchemaError(GeorepError):
    """Eine Eingabe hat nicht die erwarteten Spalten, Schlüssel oder die erwartete Form."""


class CorruptPdfError(GeorepError):
    """pypdf kann die Datei nicht lesen, oder eine Antwort ist kein PDF."""


class FetchError(GeorepError):
    """Eine Quelle hat geantwortet, aber nicht mit dem, was wir brauchen (leer, falsches Format)."""


class NetworkError(GeorepError):
    """Eine Quelle war nicht erreichbar oder antwortete nach allen Wiederholungen mit einem Fehlerstatus."""
