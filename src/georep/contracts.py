"""Verträge (deal) an- und abschalten: ``settings.contracts`` entscheidet beim Start.

Verträge prüfen Vor- und Nachbedingungen an Batch-Grenzen (DEVELOPMENT_PLAN.md § 4, Phase 6).
Eine Verletzung ist ein Programmierfehler, kein Domänenfehler: sie läuft als ``deal.ContractError``
durch und wird nicht am Rand gefangen. ``"off"`` ruft ``deal.disable``, die Funktionen laufen dann
ohne Prüfung; der gemessene Overhead steht in ``docs/profiling/README.md``. Der Schalter wirkt
prozessweit und zählt nicht zum Settings-Fingerprint.
"""

from __future__ import annotations

from typing import Literal

import deal

Mode = Literal["on", "off"]


def configure(mode: Mode) -> None:
    """Prozessweit: ``"on"`` prüft, ``"off"`` prüft nicht. Ohne deals Umgebungswarnung: der Schalter ist Absicht."""
    if mode == "off":
        deal.disable(warn=False)
    else:
        deal.enable(warn=False)
