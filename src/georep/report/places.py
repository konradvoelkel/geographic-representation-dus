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

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from georep.analysis.weights import ORTSBEZUG, STELLE
from georep.errors import SchemaError
from georep.report.downloads import LabelCheck, check_files, measured, read_quality
from georep.settings import PlacesSettings, Settings

if TYPE_CHECKING:
    from georep.layout import Layout


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
# Runde 1 (§ 4.1): dieselbe Frage an 200 Paaren, Codebuch Fassung 1; die Regel dort ist nicht C
FIRST_ROUND = LabelCheck("16-ortsbezug-f4", "2026-11-23.1", 200, ())
QUESTION = "bezug"  # die Frage des Codebuchs
NO_REFERENCE = "kein_bezug"  # das Label „der Begriff meint keinen Ort im Bezirk"


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


# --- Der Befund der Kodierung für „Methode und Grenzen" (§ 7, ein Satz) -----------------------


@dataclass(frozen=True)
class PlacesRound:
    """Eine Kodierrunde, wie ``guete.json`` sie trägt."""

    units: int  # kodierte Paare (Dokument, Wahlbezirk), je eines je Dokument
    share: float  # Anteil „handelt von", hochgerechnet mit den Schichtgewichten
    no_reference: int  # Paare mit dem Label „kein Bezug": Fehltreffer des Wörterbuchs
    alpha: float  # Krippendorffs α zwischen den Kodierern


@dataclass(frozen=True)
class PlacesFinding:
    confirmation: PlacesRound  # Runde 2, Codebuch Fassung 2: die Bestätigung von C
    first: PlacesRound  # Runde 1, Codebuch Fassung 1
    sentence: str  # der Satz aus ``guete.json`` der Bestätigung, mit der Schlichtung


def _confirmation_check() -> LabelCheck:
    return LabelCheck(CONFIRMATION.project, CONFIRMATION.codebook_version, CONFIRMATION.units, ())


def places_check_files(settings: Settings) -> tuple[Path, ...]:
    """``guete.json`` und ``stichprobe.json`` beider Runden: Eingaben von ``report`` mit ``[places]``.

    Wie die Prüfsätze der Downloads (Punkt 89): eine neue Kodierung baut die Seite neu.
    """
    if not settings.places.enabled:
        return ()
    return check_files(settings, _confirmation_check(), FIRST_ROUND)


def _round(settings: Settings, check: LabelCheck) -> PlacesRound:
    read_quality(settings, check)  # bricht ab, wenn guete.json eine andere Kodierung beschreibt
    path = settings.validation.root / check.project / "guete.json"
    quality: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    try:
        question = quality["fragen"][QUESTION]
        return PlacesRound(
            units=int(quality["einheiten"]),
            share=float(question["treffer"]["grundgesamtheit"]["schaetzer"]),
            no_reference=int(question["labels"].get(NO_REFERENCE, 0)),
            alpha=float(question["krippendorff_alpha"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SchemaError(f"{path}: Feld fehlt ({error})") from error


def places_finding(layout: Layout, settings: Settings) -> PlacesFinding | None:
    """Der Befund beider Runden, wo gemessen ist und ``places`` Stellen gefunden hat; sonst ``None``.

    Gemessen ist die Hauptperiode (``stichprobe.json``, ``measured``); ohne Rohtext gibt es keine
    Stelle und keine Gewichtung „Ortsbezug", an die der Satz anschließt.
    """
    from georep.enrich.places import position_table  # der Beitrag baut auf report.tables auf

    if not settings.places.enabled or not measured(settings, CONFIRMATION.project):
        return None
    if position_table(layout) is None:
        return None
    check = _confirmation_check()
    return PlacesFinding(
        confirmation=_round(settings, check),
        first=_round(settings, FIRST_ROUND),
        sentence=read_quality(settings, check).text(),
    )
