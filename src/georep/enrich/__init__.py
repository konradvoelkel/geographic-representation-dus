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
  spät und Kern.
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
    from georep.http import Transport
    from georep.layout import Layout
    from georep.pipeline import Step
    from georep.report.pages import Page
    from georep.report.tables import PublishedTable
    from georep.settings import Settings


class DuplicateStepError(GeorepError):
    """Zwei Schritte tragen denselben Namen; ``run`` und ``status`` könnten sie nicht trennen."""


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


# Je Vorhaben eine Zeile, in der Reihenfolge der Abhängigkeiten (Plan, § 3).
CONTRIBUTIONS: tuple[Contribution, ...] = ()


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
