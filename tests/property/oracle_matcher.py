"""Referenz-Implementierung des Matcher-Vertrags, bewusst naiv und lesbar.

Vertrag (so verhält sich FlashText, die Implementierung der Arbeit, und so entstand der Golden
Master): Treffer beginnen am Textanfang oder nach einem Grenzzeichen, enden am Textende oder vor
einem Grenzzeichen, der längste passende Begriff gewinnt, Treffer überlappen nicht, Groß/Klein
zählt nicht. Wortzeichen sind nur ASCII-Buchstaben, Ziffern und Unterstrich; Umlaute und ß sind
Grenzen. Das Grenzzeichen, das einen Treffer beendet, wird verbraucht: der nächste Treffer kann
frühestens dahinter beginnen (hypothesis fand am 2026-10-11 ``köölberg`` mit ``kö`` und ``ölberg``,
FlashText liefert nur ``kö``). Ein Ersatz-Matcher (pyahocorasick, Rust) muss dieses Orakel bestehen
oder seine Abweichung am Golden Master belegen. Python bleibt das Orakel, wie bubatzblick es für Rust hält.
"""

from __future__ import annotations

import string
from collections.abc import Iterable

WORD_CHARS = frozenset(string.ascii_letters + string.digits + "_")


def oracle_extract(text: str, terms: Iterable[str]) -> set[str]:
    lowered = text.lower()
    ordered = sorted({t.lower() for t in terms if t}, key=len, reverse=True)
    found: set[str] = set()
    n = len(lowered)
    i = 0
    while i < n:
        if i == 0 or lowered[i - 1] not in WORD_CHARS:
            for term in ordered:
                end = i + len(term)
                if lowered.startswith(term, i) and (end == n or lowered[end] not in WORD_CHARS):
                    found.add(term)
                    i = end + 1  # das beendende Grenzzeichen ist verbraucht
                    break
            else:
                i += 1
            continue
        i += 1
    return found
