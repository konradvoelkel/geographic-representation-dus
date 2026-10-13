"""Begriffe je Wahlbezirk für die Seite: ``data/begriffe.json``, nachgeladen beim Aufklappen.

Die 41 Listen waren mit 334 KB der größte Posten der Seite und standen dort in zugeklappten
``<details>`` — Daten, die niemand braucht, der sie nicht aufklappt (Punkt 49,
``docs/seitengroesse-2026-10.md``, § 4). Inline bleiben die trefferstärksten Begriffe stadtweit,
die stadtweiten Begriffe, die fünf häufigsten je Wahlbezirk und je Wahlbezirk seine Zahl.

Die Datei trägt je Wahlbezirk seine Begriffe **mit** Treffer, absteigend, ohne die versteckten
(``hide_in_display``) — genau die Liste, die vorher im HTML stand. Wer alle Begriffe will, auch die
ohne Treffer, nimmt ``combined_searchdict.parquet`` daneben.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import deal

from georep.report.model import DistrictRow

FIELDS = ("begriff", "dokumente")


def _one_row_per_district(
    districts: Sequence[DistrictRow], *, version: str, generated_at: dt.datetime
) -> bool:
    """Je Wahlbezirk eine Zeile, und jeder Begriff trägt Treffer.

    Die zweite Hälfte stand bis zum 2026-10-13 nur in der Nachbedingung, und crosshair hat die
    Lücke gefunden: ein ``DistrictRow`` mit einem Begriff ohne Treffer ist eine gültige Eingabe,
    und die Nachbedingung („je Begriff Name und Trefferzahl, absteigend sortiert") brach daran.
    Eine Annahme über die Eingabe gehört in die Vorbedingung -- dort nennt die Meldung den
    Aufrufer, nicht diese Funktion (`docs/decisions.md`, Punkt 53).

    Dasselbe gilt für die **Reihenfolge**: dass die Liste absteigend steht, entscheidet allein das
    Modell, und die Nachbedingung konnte es nur hinterher feststellen (`nox -s verify` fand
    ``[1, 2]`` am 2026-10-13). Die Nachbedingung bleibt trotzdem stehen -- sie beschreibt, was die
    Datei zusagt.
    """
    return (
        all(d.id >= 0 for d in districts)
        and len({d.id for d in districts}) == len(districts)
        and all(t.hits > 0 for d in districts for t in d.terms)
        and all(
            [t.hits for t in d.terms] == sorted((t.hits for t in d.terms), reverse=True)
            for d in districts
        )
    )


def _complete_and_ordered(result: dict[str, object]) -> bool:
    found = result["districts"]
    assert isinstance(found, dict)
    return all(
        isinstance(terms, list)
        and all(len(entry) == len(FIELDS) and entry[1] > 0 for entry in terms)
        and [entry[1] for entry in terms] == sorted((entry[1] for entry in terms), reverse=True)
        for terms in found.values()
    )


@deal.pre(_one_row_per_district, message="je Wahlbezirk genau eine Zeile")
@deal.post(_complete_and_ordered, message="je Begriff Name und Trefferzahl, absteigend sortiert")
def terms_payload(
    districts: Sequence[DistrictRow], *, version: str, generated_at: dt.datetime
) -> dict[str, object]:
    """Je Wahlbezirk ``[[Begriff, Dokumente], …]``, absteigend wie die Liste im Modell."""
    return {
        "version": version,
        "generated_at": generated_at.isoformat(),
        "fields": list(FIELDS),
        "districts": {str(d.id): [[t.term, t.hits] for t in d.terms] for d in districts},
    }


def pairs(districts: Sequence[DistrictRow]) -> int:
    """Paare aus Wahlbezirk und Begriff; die Zeilenzahl der Datei im Abschnitt „Downloads"."""
    return sum(len(d.terms) for d in districts)
