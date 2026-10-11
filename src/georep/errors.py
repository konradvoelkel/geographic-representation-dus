"""Domänenfehler: erwartbare Zustände, die ein Schritt meldet, statt still weiterzumachen.

Vertragsverletzungen (deal, ab Phase 6) sind keine Domänenfehler; sie sind Programmierfehler
und laufen durch. Diese Klassen hier werden an genau einer Stelle behandelt: am Rand, wo der
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
