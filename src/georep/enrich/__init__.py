"""Beiträge der Vorverarbeitung 2026-11: Schritte, Tabellen und Unterseiten aus eigenen Modulen.

Fundament F2 des Plans ``docs/plan-vorverarbeitung-2026-11.md`` (§ 2.3, § 7). Neunzehn Vorhaben
würden sonst dieselben Stellen ändern: ``pipeline.build_steps`` (eine Funktion von rund 950
Zeilen), das Tabellenregister in ``report/tables.py`` und ``report/model.py``. Im Ausbau 2026-10
endeten an rund zwölf Stellen beide Konfliktseiten mitten in einer Funktion. Ein Vorhaben trägt
darum alles als ein ``Contribution``-Objekt bei, und die einzige gemeinsame Stelle ist das Tupel
``CONTRIBUTIONS`` unten: je Vorhaben eine Importzeile und ein Eintrag, in der Reihenfolge der
Abhängigkeiten (ein Schritt, der die Ausgabe eines anderen Beitrags liest, steht dahinter).

Wo die Beiträge landen:

* ``steps`` — die Schritte stehen in ``build_steps`` unmittelbar vor ``report``, also nach allen
  Kernschritten; ``run`` plant sie in der Reihenfolge des Registers. Die Fabrik bekommt
  ``(settings, layout, http)``: ``http`` ist der ``Transport`` aus ``build_steps``, in Tests die
  Fake-Session, sonst eine Session, die erst beim ersten Aufruf entsteht
  (``georep.http.DeferredTransport``). Ein Netzschritt nimmt ihn statt einer eigenen Session.
* ``early_steps`` — eine Fabrik mit derselben Signatur, aber ihre Schritte stehen unmittelbar
  vor ``weights``, hinter ``index``, ``results``, ``metrics`` und ``body_hits``: für Ausgaben, die
  ``weights`` liest (Vorhaben 16 ``places``, das 11 ``sections`` braucht; 13 ``families``, wenn es
  gebaut wird). Ein früher Schritt kann keine Ausgabe eines späten lesen, auch nicht aus einem
  Beitrag, der weiter vorn im Register steht: ``run`` plant alle späten danach. Ein Vorhaben mit
  beiden Arten bleibt **ein** Beitrag. ``check_unique_names`` gilt über alle Schritte, früh,
  spät und Kern; ``check_step_order`` bricht ab, wenn ein Schritt eine Ausgabe liest, die erst ein
  späterer schreibt, oder wenn zwei Schritte dieselbe Datei schreiben.
* ``tables`` — veröffentlichte Tabellen, hinter denen des Kerns (``report.tables.published``).
* ``pages`` — Unterseiten neben ``index.html`` (``report.pages``), je ein Schritt nach ``report``.

``pipeline`` und ``report.tables`` lesen das Register erst beim Aufruf (Import in der Funktion):
die Beiträge bauen ``pipeline.Step`` und ``report.tables.PublishedTable``, und ein Import auf
Modulebene wäre ein Kreis.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from georep.errors import GeorepError

if TYPE_CHECKING:
    from pathlib import Path

    from georep.http import Transport
    from georep.layout import Layout
    from georep.pipeline import Step
    from georep.report.pages import Page
    from georep.report.tables import PublishedTable
    from georep.settings import Settings


class DuplicateStepError(GeorepError):
    """Zwei Schritte tragen denselben Namen; ``run`` und ``status`` könnten sie nicht trennen."""


class DuplicateOutputError(GeorepError):
    """Zwei Schritte schreiben dieselbe Datei; der zweite überschriebe die Datei und ihren Stamp."""


class StepOrderError(GeorepError):
    """Ein Schritt liest eine Ausgabe, die erst ein späterer Schritt derselben Liste schreibt."""


def no_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Ein Beitrag ohne eigene Schritte, etwa einer, der nur eine Unterseite zeigt."""
    return []


@dataclass(frozen=True)
class Contribution:
    """Was ein Vorhaben beiträgt; jedes Feld darf leer bleiben."""

    name: str  # das Vorhaben, etwa ``14-vorgaenge``; steht in Fehlermeldungen
    steps: Callable[[Settings, Layout, Transport], list[Step]] = no_steps
    tables: tuple[PublishedTable, ...] = ()
    pages: tuple[Page, ...] = ()
    # Nachzug F2 (Synergien 2026-11, Konflikt 6): Schritte vor ``weights``. Am Ende, damit kein
    # Aufruf mit Positionen seine Bedeutung ändert.
    early_steps: Callable[[Settings, Layout, Transport], list[Step]] = no_steps


# Je Vorhaben eine Zeile, in der Reihenfolge der Abhängigkeiten (Plan, § 3). Die Importe stehen hier
# und nicht oben: jedes Beitragsmodul baut ein ``Contribution`` aus diesem Modul.
from georep.enrich.cycles import CONTRIBUTION as CYCLES  # noqa: E402  (Vorhaben 17)
from georep.enrich.embeddings import CONTRIBUTION as EMBEDDINGS  # noqa: E402  (Vorhaben 18)
from georep.enrich.functions import CONTRIBUTION as FUNCTIONS  # noqa: E402  (Vorhaben 15)
from georep.enrich.outcomes import CONTRIBUTION as OUTCOMES  # noqa: E402  (Vorhaben 26)
from georep.enrich.procedures import CONTRIBUTION as PROCEDURES  # noqa: E402  (Vorhaben 14)
from georep.enrich.sections import CONTRIBUTION as SECTIONS  # noqa: E402  (Vorhaben 11)

CONTRIBUTIONS: tuple[Contribution, ...] = (
    FUNCTIONS,
    PROCEDURES,
    EMBEDDINGS,
    CYCLES,
    OUTCOMES,
    SECTIONS,
)


def contributed_early_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Die frühen Schritte aller Beiträge (vor ``weights``) in Registerfolge."""
    return [
        step
        for contribution in CONTRIBUTIONS
        for step in contribution.early_steps(settings, layout, http)
    ]


def contributed_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Die späten Schritte aller Beiträge (vor ``report``) in Registerfolge."""
    return [
        step
        for contribution in CONTRIBUTIONS
        for step in contribution.steps(settings, layout, http)
    ]


def check_unique_names(steps: Sequence[Step]) -> None:
    """``DuplicateStepError``, wenn zwei Schritte gleich heißen; die Meldung nennt den Namen."""
    counts = Counter(step.name for step in steps)
    twice = sorted(name for name, count in counts.items() if count > 1)
    if twice:
        raise DuplicateStepError(f"Schritte doppelt im Register: {', '.join(twice)}")


def check_step_order(steps: Sequence[Step]) -> None:
    """Jede Datei hat höchstens einen Schreiber, und kein Schritt liest eine spätere Ausgabe.

    ``run`` plant in Listenfolge. Liest ein Schritt, was erst ein späterer schreibt, findet er im
    ersten Lauf nichts und im zweiten einen alten Stand; das kann ein früher Beitrag (vor
    ``weights``) leicht tun, der eine Ausgabe eines späten liest (Review F7, M1). Gezählt werden
    die Eingaben und die optionalen (``Step.optional``, Fundament F1): beider Hash steht im
    Stamp. Eine Datei, die kein Schritt schreibt, ist kein Fall dieser Prüfung. Die Meldungen
    nennen Schritte und Datei.
    """
    writer: dict[Path, tuple[int, str]] = {}
    twice: list[str] = []
    for position, step in enumerate(steps):
        for path in step.outputs:
            if path in writer:
                twice.append(f"{path.name} ({writer[path][1]}, {step.name})")
            else:
                writer[path] = (position, step.name)
    if twice:
        raise DuplicateOutputError(f"Ausgaben doppelt im Register: {'; '.join(twice)}")
    backward = [
        f"{step.name} liest {path.name}, das erst {writer[path][1]} schreibt"
        for position, step in enumerate(steps)
        for path in (*step.inputs, *step.optional)
        if path in writer and writer[path][0] > position
    ]
    if backward:
        raise StepOrderError(f"Schritte lesen eine spätere Ausgabe: {'; '.join(backward)}")
