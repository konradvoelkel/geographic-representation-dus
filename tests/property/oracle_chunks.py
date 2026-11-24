"""Das ``zerteile`` der Messung von Vorhaben 18, wörtlich: das Orakel für ``georep.prep.chunks``.

Kopiert aus ``docs/plans/18-einbettungen-messung.py`` (Stand des Urteils, 2026-11-24), nur die
beiden Konstanten ``STUECK_MAX`` und ``UEBERLAPPUNG`` sind Parameter mit den Werten der Messung als
Vorgabe, damit hypothesis kleine Budgets probieren kann. Die Vektoren im Modellcache gehören zu
genau diesen Rümpfen; wer ``split_chunks`` umbaut, misst sich an dieser Datei
(``tests/property/test_chunks_props.py``), wie ein neuer Matcher an ``oracle_matcher.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

STUECK_MAX = 1600  # Titel + Leerzeile + Rumpf eines Stücks, in Zeichen
UEBERLAPPUNG = 200  # Zeichen der letzten Zeilen des vorigen Stücks


def zeilen_von(roh: str, budget: int) -> list[str]:
    zeilen: list[str] = []
    for zeile in roh.replace("\f", "\n").split("\n"):
        zeile = zeile.rstrip()
        if not zeile.strip():
            continue
        while len(zeile) > budget:
            schnitt = zeile.rfind(" ", 0, budget + 1)
            if schnitt <= 0:
                schnitt = budget
            kopf = zeile[:schnitt].rstrip()
            if kopf.strip():
                zeilen.append(kopf)
            zeile = zeile[schnitt:].lstrip()
        if zeile.strip():
            zeilen.append(zeile)
    return zeilen


def _laenge(zeilen: Sequence[str], start: int, ende: int) -> int:
    return sum(len(z) for z in zeilen[start:ende]) + max(0, ende - start - 1)


def zerteile(
    titel: str, roh: str, stueck_max: int = STUECK_MAX, ueberlappung: int = UEBERLAPPUNG
) -> list[str]:
    """Fassung 18-stuecke-1: Rümpfe der Stücke (ohne Präfix und Titel), § 3.1."""
    budget = stueck_max - len(titel) - 2
    zeilen = zeilen_von(roh, budget)
    ruempfe: list[str] = []
    start = 0
    while start < len(zeilen):
        ende = start + 1
        while ende < len(zeilen) and _laenge(zeilen, start, ende + 1) <= budget:
            ende += 1
        ruempfe.append("\n".join(zeilen[start:ende]))
        if ende >= len(zeilen):
            break
        neu = ende
        while neu - 1 > start and _laenge(zeilen, neu - 1, ende) <= ueberlappung:
            neu -= 1
        while _laenge(zeilen, neu, ende + 1) > budget:
            neu += 1
        start = neu
    return ruempfe


def titel_von(name: str | None, titel_max: int = 200) -> str:
    return " ".join((name or "").split())[:titel_max]
