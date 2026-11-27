"""Der allgemeine Dialog-Haken: Zeilen je Dokument, nachgeladen beim ersten Öffnen (Vorarbeit V2).

Vorarbeit V2 aus ``docs/plan-zeigen-2026-11.md``, § 4, gebaut mit Stufe 3 von Vorhaben 14. Der
Dokumentdialog der Hauptseite (``templates/frame/script.js.j2``) zeigt die Dokumente eines
Begriffs aus ``data/dokumente.json``. Ein Beitrag hängt dort je Dokument eine Zeile an, ohne dass
``dokumente.json`` wächst (heute 2,26 MB in der Hauptperiode): er trägt einen ``DialogHook`` bei
(``georep.enrich.Contribution.dialogs``), und der Schritt ``report`` schreibt daraus
``data/<name>.json``. Das Skript des Rahmens lädt jede dieser Dateien beim ersten Öffnen des
Dialogs einmal nach (``loadJson``, Punkt 49) und hängt unter jedes Dokument, das eine Zeile hat,
„<Titel>: <Eintrag>; <Eintrag> …". Welche Dateien es gibt, steht als ``data-extras`` am
``<dialog>`` der Hauptseite. Ein zweiter Beitrag (18 ``aehnlich.json``, 26 ``beschluesse.json``)
hängt sich nur mit Daten an: ein ``DialogHook`` im eigenen Modul, kein JavaScript.

**Format 2 von ``data/<name>.json``** (2 seit Review K3: ``show``)::

    {"format": 2, "version": …, "generated_at": …,
     "title": "Vorgang",              # Vorspann der Zeile je Dokument
     "note": "…",                     # ein Satz unter der Liste: woher, wie geprüft (darf leer sein)
     "show": [2],                     # Felder eines Ziels als Text des Links (1 Datum, 2 Nr., 3 Titel)
     "labels": ["Antwort auf", …],    # die Wörter der Einträge, je einmal
     "base": "https://…/",            # dasselbe Präfix wie in dokumente.json
     "documents": [[link, datum, drucksache, titel], …],   # Ziele außerhalb von dokumente.json
     "rows": {"<Index in dokumente.json>": [[label], [label, ziel], …], …}}

Unter jedem Dokument steht je Haken eine Zeile in der Folge von ``data-extras`` (der Registerfolge),
gleich in welcher Folge die Dateien ankommen; das Wort eines Eintrags steht nur, wenn es sich gegen
den vorigen ändert („umgesetzt in A, B; geändert durch C"). Die Sätze der Dateien stehen unter der
Liste, je Haken einer, ebenfalls in Registerfolge.

Ein Eintrag ist ``[label]`` (nur das Wort, etwa „angenommen im Rat am 12.03.2024") oder
``[label, ziel]``: ``ziel >= 0`` ist der Index eines Dokuments in ``dokumente.json``, ``ziel < 0``
das Dokument ``documents[-1 - ziel]`` dieser Datei. Indizes statt Kennungen, weil
``dokumente.json`` keine Kennungen trägt und fünf Ziffern kürzer sind als eine OParl-URL; beide
Dateien schreibt derselbe Schritt aus derselben Folge (``documents.document_order``), sie können
also nicht auseinanderlaufen. Zeilen gibt es nur für Dokumente, die der Dialog zeigen kann.

Ohne JavaScript gibt es keinen Dialog; die Seite bleibt lesbar, wie sie war.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import deal

from georep.layout import Layout
from georep.settings import Settings

DIALOG_FORMAT = 2  # 2 seit Review K3: ``show`` wählt die Felder eines Ziels
DIALOG_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
# Dateien, die es unter ``data/`` schon als JSON gibt (``report.build``)
RESERVED = frozenset({"dokumente", "begriffe", "schema", "summary"})
# Die Felder eines Ziels, die ein Haken als Text des Links zeigen kann, mit ihrer Stelle in einer
# Zeile von ``documents`` (und von ``dokumente.json``): Stelle 0 ist der Link selbst.
SHOWN_FIELDS: dict[str, int] = {"datum": 1, "drucksache": 2, "titel": 3}

Entry = tuple[int, str | None]  # Index in ``DialogRows.labels`` und die Korpus-ID des Ziels


@dataclass(frozen=True)
class DialogTarget:
    """Ein Dokument, auf das ein Eintrag zeigt: Link auf das PDF, Datum, Drucksache, Titel."""

    link: str  # volle URL; leer ohne Datei
    date: dt.date | None
    reference: str
    title: str


@dataclass(frozen=True)
class DialogRows:
    """Was ein Beitrag je Dokument zeigt; ``rows`` und ``targets`` sind nach Korpus-ID geschlüsselt.

    ``targets`` nennt jedes Ziel aus ``rows``; ``dialog_payload`` nimmt davon nur, was nicht schon
    in ``dokumente.json`` steht. Die Folge der Einträge je Dokument ist die des Beitrags.
    """

    labels: tuple[str, ...]
    rows: Mapping[str, tuple[Entry, ...]]
    targets: Mapping[str, DialogTarget] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class DialogHook:
    """Ein Haken im Dokumentdialog: Datei ``data/<name>.json``, Titel, Eingaben, Zeilen."""

    name: str
    title: str  # Vorspann je Dokument, etwa „Vorgang"
    description: str  # ein Satz für die Downloads der Hauptseite
    inputs: Callable[[Layout, Settings], tuple[Path, ...]]  # was ``report`` dafür liest (Stamp)
    rows: Callable[[Layout, Settings], DialogRows]
    # None: immer, wenn der Beitrag im Register ist
    enabled: Callable[[Settings], bool] | None = None
    # Review K3 (d): die Felder eines Ziels als Text des Links, in dieser Folge; 18 zeigt je Vorschlag
    # Drucksache, Datum und Titel (Plan 18, § 7), 14 nur die Drucksache. Der Titel steht immer auch
    # als ``title`` am Link.
    show: tuple[str, ...] = ("drucksache",)

    def __post_init__(self) -> None:
        if not DIALOG_NAME.fullmatch(self.name) or self.name in RESERVED:
            raise ValueError(f"Haken {self.name!r}: [a-z][a-z0-9-]*, nicht {sorted(RESERVED)}")
        if not self.show or not set(self.show) <= set(SHOWN_FIELDS):
            raise ValueError(
                f"Haken {self.name!r}: show aus {sorted(SHOWN_FIELDS)}, nicht {self.show}"
            )

    @property
    def file_name(self) -> str:
        return f"{self.name}.json"


def all_dialogs() -> list[DialogHook]:
    """Alle Haken des Registers in Registerfolge; ein Name doppelt ist ein ``ValueError``.

    Import in der Funktion wie in ``report.pages.pages_for``: die Beiträge bauen ``DialogHook``.
    """
    from georep.enrich import CONTRIBUTIONS

    found = [hook for contribution in CONTRIBUTIONS for hook in contribution.dialogs]
    names = [hook.name for hook in found]
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        raise ValueError(f"Dialog-Haken doppelt im Register: {', '.join(twice)}")
    return found


def dialogs_for(settings: Settings) -> list[DialogHook]:
    """Die Haken, die für diese Settings gebaut werden, in Registerfolge."""
    return [hook for hook in all_dialogs() if hook.enabled is None or hook.enabled(settings)]


def dialog_names(settings: Settings) -> tuple[str, ...]:
    """Was am ``<dialog>`` der Hauptseite als ``data-extras`` steht."""
    return tuple(hook.name for hook in dialogs_for(settings))


def contributed_dialog_files(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Die Eingaben der Haken: ``report`` schreibt ihre Dateien, also zählen sie in seinem Stamp."""
    paths = [path for hook in dialogs_for(settings) for path in hook.inputs(layout, settings)]
    return tuple(dict.fromkeys(paths))


def _relative(link: str, base: str) -> str:
    return link[len(base) :] if base and link.startswith(base) else link


def _targets_known(rows: DialogRows, order: Sequence[str], *_args: object, **_kw: object) -> bool:
    """Jedes Label hat einen Index, jedes Ziel steht in ``dokumente.json`` oder in ``targets``."""
    known = set(order)
    return all(
        0 <= label < len(rows.labels)
        and (target is None or target in known or target in rows.targets)
        for entries in rows.rows.values()
        for label, target in entries
    )


def _indices_resolve(
    rows: DialogRows,
    order: Sequence[str],
    base: str,
    *,
    title: str,
    version: str,
    generated_at: dt.datetime,
    show: Sequence[str] = ("drucksache",),
    result: dict[str, object] | None = None,
) -> bool:
    """Jeder Schlüssel und jedes Ziel zeigt auf ein Dokument, das es gibt."""
    assert result is not None
    documents = result["documents"]
    out = result["rows"]
    assert isinstance(documents, list) and isinstance(out, dict)
    return all(
        0 <= int(key) < len(order)
        and all(
            len(e) == 1 or (0 <= e[1] < len(order) or 0 < -e[1] <= len(documents)) for e in entries
        )
        for key, entries in out.items()
    )


@deal.pre(_targets_known, message="jedes Label und jedes Ziel ist bekannt")
@deal.ensure(_indices_resolve, message="jeder Index zeigt auf ein Dokument")
def dialog_payload(
    rows: DialogRows,
    order: Sequence[str],
    base: str,
    *,
    title: str,
    version: str,
    generated_at: dt.datetime,
    show: Sequence[str] = ("drucksache",),
) -> dict[str, object]:
    """``data/<name>.json`` aus den Zeilen eines Beitrags und der Folge von ``dokumente.json``.

    ``order`` sind die Korpus-IDs in der Folge von ``dokumente.json``, ``base`` dessen Präfix der
    Links. Zeilen für Dokumente außerhalb von ``order`` fallen weg (der Dialog zeigt sie nie).
    Die Schlüssel stehen aufsteigend, die eigenen Ziele in der Folge ihres ersten Auftretens.
    """
    position = {doc_id: i for i, doc_id in enumerate(order)}
    own: dict[str, int] = {}
    out: dict[str, list[list[int]]] = {}
    for doc_id in sorted((d for d in rows.rows if d in position), key=position.__getitem__):
        entries: list[list[int]] = []
        for label, target in rows.rows[doc_id]:
            if target is None:
                entries.append([label])
            elif target in position:
                entries.append([label, position[target]])
            else:
                entries.append([label, -1 - own.setdefault(target, len(own))])
        if entries:
            out[str(position[doc_id])] = entries
    documents = [
        [
            _relative(t.link, base),
            t.date.isoformat() if t.date is not None else "",
            t.reference,
            t.title,
        ]
        for t in (rows.targets[target] for target in own)
    ]
    return {
        "format": DIALOG_FORMAT,
        "version": version,
        "generated_at": generated_at.isoformat(),
        "title": title,
        "note": rows.note,
        "show": [SHOWN_FIELDS[name] for name in show],
        "labels": list(rows.labels),
        "base": base,
        "documents": documents,
        "rows": out,
    }
