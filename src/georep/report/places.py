"""Vorhaben 16, kleine Stufe 3: die Zeilen ``ortsbezug`` und ``stelle`` und ihr Prüfsatz.

Kein Radio im Kartenumschalter und keine Unterseite (Messdokument ``docs/plans/16-ortsbezug.md``,
§ 7 mit § 10, Punkt 6; Frage 9.16): zwei Zeilen in „Was ändert die Gewichtung?" und ein Satz in
„Methode und Grenzen". Die Zeile ``ortsbezug`` sagt beides, was die Bestätigung trägt: Nebenregel
C besteht an 100 frischen Paaren, und sie trennt trotzdem nicht besser als die triviale Regel
„alles handelt von". Beide F1 trägt ``guete.json`` nicht (es kennt nur die Labels, nicht das
Verfahren); sie stehen hier als Konstanten, und ``tests/unit/test_report_places.py`` rechnet sie aus
den Labels im Repo und der Ausgabe des Verfahrens (``validierung/16-ortsbezug/verfahren.csv``) nach.

Kein Stadtwort: die Gewichte nach Stelle kommen aus ``[places]``, die Zahlen aus ``validierung/``.
"""

from __future__ import annotations

from dataclasses import dataclass

from georep.analysis.weights import ORTSBEZUG, STELLE
from georep.settings import PlacesSettings


@dataclass(frozen=True)
class RuleCheck:
    """Was die Bestätigung eines Verfahrens sagt und ``guete.json`` nicht trägt."""

    project: str  # der Ordner unter ``validation.root``
    codebook_version: str
    units: int
    f1: float  # F1 der Klasse „handelt von", hochgerechnet mit den Schichtgewichten
    trivial_f1: float  # dasselbe für „alles handelt von"


# Runde 2 (Messdokument § 4.4): ortsbezug-entwurf-2 an 100 frischen Paaren, Codebuch Fassung 2
CONFIRMATION = RuleCheck("16-ortsbezug-2-f4", "2026-11-23.2", 100, 0.828, 0.878)


def _two(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _weight(value: float) -> str:
    """Ein Gewicht, wie die Seite es schreibt: ``0,5``, ``0,25``, ``1``."""
    return f"{value:g}".replace(".", ",")


def variant_texts(places: PlacesSettings) -> dict[str, tuple[str, str]]:
    """Beschriftung und Halbsatz der beiden Zeilen; die Gewichte nach Stelle aus dem Profil."""
    weights = places.position_weights
    named = ", ".join(
        f"{label} {_weight(weights[key])}"
        for key, label in (
            ("titel", "Titel"),
            ("betreff", "Betreff"),
            ("kern", "Kern"),
            ("begleittext", "Begleittext"),
            ("rest", "Rest"),
        )
    )
    check = CONFIRMATION
    return {
        ORTSBEZUG: (
            "Ortsbezug",
            "ein Dokument zählt nur, wo ein Begriff des Wahlbezirks im Titel, im Betreff oder im "
            "Kern (Beschlussvorschlag, Fragen) steht oder im Begleittext in einer Listenzeile "
            f"oder mit Hausnummer, sonst 0; bestätigt an {check.units} Paaren (F1 "
            f"{_two(check.f1)}), trennt aber nicht besser als alle Treffer (F1 "
            f"{_two(check.trivial_f1)})",
        ),
        STELLE: (
            "nach Stelle",
            f"je Begriff nach seiner vordersten Stelle im Dokument: {named}; explorativ",
        ),
    }
