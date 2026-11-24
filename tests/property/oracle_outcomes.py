"""Die Regel der Beschlusslage, wie das Messskript sie rechnete: das Orakel für ``analysis.outcomes``.

Wörtlich aus ``docs/plans/26-beschluesse-messung.py`` (Commit ``94da91f``: ``Schritt.schluessel``
und ``klasse``), nur mit dem Wortschatz als Argument statt der Konstanten ``RESULT``. Wer die Regel
in ``analysis.outcomes`` umbaut, misst sich hieran (wie ``oracle_matcher.py`` für den Matcher); die
Regel selbst ist vorab festgelegt (Messdokument § 3.1) und an 150 Anträgen geprüft (§ 4.1).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Schritt:
    """Ein Tagesordnungspunkt, der eine Beratung des Antrags behandelt."""

    top: str
    sitzung: dt.datetime | None
    ordnung: int
    result: str | None

    def schluessel(self) -> tuple[str, int, str]:
        return (self.sitzung.isoformat() if self.sitzung else "", self.ordnung, self.top)


def klasse(
    steps: Sequence[Schritt], result: Mapping[str, tuple[str, str]]
) -> tuple[str, Schritt | None]:
    """(Klasse, maßgeblicher Schritt) nach der letzten Entscheidung in der Sache (§ 3.1)."""
    mit = [s for s in steps if s.result]
    for s in mit:
        if s.result not in result:
            raise SystemExit(f"unbekannter Wert von result: {s.result!r} ({s.top})")
    sache = [s for s in mit if result[s.result or ""][0] == "sache"]
    if sache:
        last = max(sache, key=Schritt.schluessel)
        return result[last.result or ""][1], last
    if mit:
        last = max(mit, key=Schritt.schluessel)
        return result[last.result or ""][1], last
    return "ohne_ergebnis", None
