"""Fundament F6: Sitzungen, Tagesordnung, Beratungen und Personen aus OParl, als Netzschritte.

Drei Listen des Bodys, je ein Schritt, jeder nur mit Endpunkt im Profil (``[council]``) und nur
mit ``--online`` oder ``georep fetch`` (docs/runbook-sitzungen.md):

- ``meetings``: die Sitzungen ab dem Periodenbeginn, **ohne** Obergrenze, mit ihrer
  Tagesordnung. Ohne Obergrenze, weil eine Vorlage vom Ende einer Periode oft erst in der nächsten
  beraten wird. Die Liste ist neueste zuerst; der Abruf endet nach der ersten Seite, die ganz vor
  dem Beginn liegt (``council.stop_when_older``).
- ``consultations``: alle Beratungen des Bodys, die Verbindung Paper -- Sitzung --
  Tagesordnungspunkt, ohne die Paper neu abzurufen.
- ``persons``: alle Personen des Bodys mit ihren Mitgliedschaften, ohne Kontaktdaten (das Modell
  kennt sie nicht, ``georep.oparl.PERSON_PRIVATE_KEYS``).

Ausgaben unter ``raw/``, eine JSONL-Datei je Objektart, sortiert nach ID, mit den Schlüsseln von
OParl (``agendaItem``, ``votingRight`` …), damit eine Zeile aussieht wie das Objekt des Servers.
Die eingebetteten Objekte stehen in ihrer eigenen Datei (``agenda_items.jsonl``,
``memberships.jsonl``) und nicht noch einmal in der Zeile ihres Elternobjekts.

Ein Abruf schreibt jede Seite sofort in eine Teildatei neben der Ausgabe (``*.partial``) und hält
die URL der nächsten Seite fest (``<schritt>.progress.json``); ein Abbruch kostet so nur die
laufende Seite, und der nächste Lauf macht dort weiter. Erst ein vollständiger Abruf ersetzt die
Ausgabe, atomar: bis dahin bleibt die alte Datei, wie sie war. Mit ``modified_since`` (Schritte in
``council.incremental``) kommt nur Geändertes; es wird dann über den Bestand gelegt, Gelöschte
fallen heraus.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import deal

from georep.http import Transport
from georep.io import atomic_path, write_json
from georep.layout import Layout
from georep.oparl import (
    OparlAgendaItem,
    OparlConsultation,
    OparlMeeting,
    OparlMembership,
    OparlObject,
    OparlPerson,
)
from georep.settings import Settings
from georep.sources.oparl import ListReport, fetch_objects

# Die Version der fünf JSONL-Dateien; die drei Schritte nennen sie (tests/unit/test_pipeline_steps.py).
COUNCIL_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CouncilFiles:
    """Die Dateien der drei Schritte unter ``raw/``; Vorhaben, die sie lesen, nehmen sie von hier."""

    raw: Path

    @property
    def meetings(self) -> Path:
        return self.raw / "meetings.jsonl"

    @property
    def agenda_items(self) -> Path:
        return self.raw / "agenda_items.jsonl"

    @property
    def consultations(self) -> Path:
        return self.raw / "consultations.jsonl"

    @property
    def persons(self) -> Path:
        return self.raw / "persons.jsonl"

    @property
    def memberships(self) -> Path:
        return self.raw / "memberships.jsonl"

    def progress(self, step: str) -> Path:
        """Wo ein unterbrochener Abruf weitergeht; die Datei gibt es nur, solange er unvollständig ist."""
        return self.raw / f"{step}.progress.json"


def council_files(layout: Layout) -> CouncilFiles:
    return CouncilFiles(layout.raw)


class JsonlStore[O: OparlObject]:
    """Objekte einer Art, eine JSON-Zeile je Objekt; beim Lesen gewinnt die letzte Zeile einer ID.

    ``exclude`` nennt Felder, die in einer eigenen Datei stehen (die Tagesordnung einer Sitzung,
    die Mitgliedschaften einer Person).
    """

    def __init__(self, path: Path, model: type[O], *, exclude: frozenset[str] = frozenset()):
        self.path = path
        self.model = model
        self.exclude = exclude

    def partial(self) -> JsonlStore[O]:
        """Die Teildatei eines laufenden Abrufs, neben der Ausgabe."""
        return JsonlStore(
            self.path.with_name(self.path.name + ".partial"), self.model, exclude=self.exclude
        )

    def load(self) -> dict[str, O]:
        if not self.path.is_file():
            return {}
        found: dict[str, O] = {}
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    obj = self.model.model_validate_json(line)
                    found[obj.id] = obj
        return found

    def _line(self, obj: O) -> str:
        return obj.model_dump_json(by_alias=True, exclude_none=True, exclude=set(self.exclude))

    def append(self, objects: Iterable[O]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            for obj in objects:
                f.write(self._line(obj) + "\n")

    def save(self, objects: Iterable[O]) -> int:
        """Alle Objekte, nach ID sortiert, atomar; zwei Läufe mit derselben Antwort sind bytegleich."""
        ordered = sorted(objects, key=lambda o: o.id)
        with atomic_path(self.path) as tmp, tmp.open("w", encoding="utf-8") as f:
            for obj in ordered:
                f.write(self._line(obj) + "\n")
        return len(ordered)


def newest_modified(objects: Iterable[OparlObject]) -> dt.datetime | None:
    return max((o.modified for o in objects if o.modified is not None), default=None)


def since_for(known: Mapping[str, OparlObject], incremental: bool) -> dt.datetime | None:
    """``modified_since`` wie bei den Papers: jüngstes ``modified`` des Bestands minus ein Tag."""
    newest = newest_modified(known.values()) if incremental else None
    return None if newest is None else newest - dt.timedelta(days=1)


@deal.ensure(
    lambda base, fetched, gone, result: set(result) == (set(base) | set(fetched)) - set(gone),
    message="der Bestand und das Geholte, ohne das Gelöschte",
)
def merge[O: OparlObject](
    base: Mapping[str, O], fetched: Mapping[str, O], gone: Collection[str]
) -> dict[str, O]:
    """Das Geholte über den Bestand legen und Gelöschtes herausnehmen."""
    removed = set(gone)
    return {k: v for k, v in (dict(base) | dict(fetched)).items() if k not in removed}


@dataclass(frozen=True)
class _Run:
    """Was ein Schritt vor dem Abruf weiß: ab wann, ob er fortsetzt, wo sein Fortschritt steht.

    ``since`` gehört zum ganzen Abruf, auch über eine Unterbrechung hinweg: der Fortschritt hält
    es fest, und eine Fortsetzung fragt ohne ``modified_since`` (der ``next``-Link des Servers
    trägt den Filter schon) und legt das Ergebnis trotzdem richtig über den Bestand.
    """

    since: dt.datetime | None
    resume: str | None
    progress: Path
    pages: int = 0

    @property
    def mode(self) -> str:
        mode = f"seit {self.since.date()}" if self.since else "vollständig"
        return mode + (" (fortgesetzt)" if self.resume else "")


def _saved(progress: Path) -> tuple[str | None, dt.datetime | None, int]:
    """URL, ``since`` und Seitenzahl eines unvollständigen Abrufs; eine kaputte Datei ist keiner."""
    try:
        saved = json.loads(progress.read_text(encoding="utf-8"))
        url, since, pages = saved["next_url"], saved.get("since"), int(saved.get("pages", 0))
        if not isinstance(url, str) or not url:
            return None, None, 0
        return url, dt.datetime.fromisoformat(since) if isinstance(since, str) else None, pages
    except OSError, ValueError, KeyError, TypeError:
        return None, None, 0


def _start(progress: Path, since: dt.datetime | None, *partials: Path) -> _Run:
    """Mit Fortschritt macht der Abruf dort weiter, mit dessen ``since``; ohne ihn beginnen die
    Teildateien leer und ``since`` kommt aus dem Bestand.

    Darum ist eine Probe mit ``--max-pages`` der Anfang des Abrufs und nicht ein kleiner ganzer:
    ihr Bestand gälte sonst beim nächsten Lauf als vollständig, und ``modified_since`` holte nur
    noch, was sich seitdem geändert hat (2026-11-23, Test vor der Änderung).
    """
    resume, saved_since, pages = _saved(progress)
    if resume is not None:
        return _Run(saved_since, resume, progress, pages)
    for partial in partials:
        partial.unlink(missing_ok=True)
    return _Run(since, None, progress)


def _page_writer[O: OparlObject](
    run: _Run, write: Callable[[list[O]], None]
) -> Callable[[list[O], str | None], None]:
    """Nach jeder Seite: die Objekte in die Teildatei, dann die URL der nächsten Seite."""
    done = run.pages

    def page_done(kept: list[O], next_url: str | None) -> None:
        nonlocal done
        write(kept)
        done += 1
        write_json(
            run.progress,
            {
                "next_url": next_url,
                "pages": done,
                "since": run.since.isoformat() if run.since else None,
                "written": dt.datetime.now(dt.UTC).isoformat(),
            },
        )

    return page_done


def _finish(run: _Run, *partials: Path) -> None:
    """Nach dem letzten Blatt weg mit Teildateien und Fortschritt."""
    for partial in partials:
        partial.unlink(missing_ok=True)
    run.progress.unlink(missing_ok=True)


def _probe(run: _Run, report: ListReport, counts: str) -> str:
    """Die Zeile eines unvollständigen Abrufs (``--max-pages``): seine Zahlen, die Ausgabe nicht.

    Eine Probe schreibt keine Ausgabe (Review 2026-11-23, Befund 1): sonst ersetzte sie einen
    vollständigen Bestand durch ihre Seiten, und ``since`` käme beim nächsten Lauf aus ihr.
    """
    return (
        f"{run.mode}: {report.summary()}; Probe: {counts} bisher in der Teildatei, "
        "die Ausgabe bleibt, wie sie war; der nächste Lauf setzt fort"
    )


def _share(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "0%"


def _all_before(day: dt.date) -> Callable[[list[OparlMeeting]], bool]:
    """Liegt eine ganze Seite vor ``day``? Eine Seite ohne Beginn zählt nicht als älter."""

    def older(page: list[OparlMeeting]) -> bool:
        starts = [m.start.date() for m in page if m.start is not None]
        return bool(starts) and max(starts) < day

    return older


def _children[P: OparlObject, C: OparlObject](
    base: Mapping[str, C],
    fetched: Mapping[str, C],
    parents: Mapping[str, P],
    refetched: Mapping[str, P],
    parent_of: Callable[[C], str | None],
    gone: Collection[str],
) -> dict[str, C]:
    """Eingebettete Objekte: die eines neu geholten Elternobjekts ersetzen dessen alte ganz.

    So verschwindet ein Tagesordnungspunkt, den der Server aus einer Sitzung genommen hat, auch
    bei ``modified_since``; und keiner bleibt ohne sein Elternobjekt stehen.
    """
    kept = {k: v for k, v in base.items() if parent_of(v) not in refetched}
    return {k: v for k, v in merge(kept, fetched, gone).items() if parent_of(v) in parents}


# --- die drei Schritte ---------------------------------------------------------------------------


def run_meetings(
    settings: Settings,
    layout: Layout,
    http: Transport,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Sitzungen ab dem Periodenbeginn mit Tagesordnung nach ``meetings.jsonl`` und
    ``agenda_items.jsonl``; die Zeile nennt die Anteile mit Ergebnis und mit Beratung."""
    council, oparl = settings.council, settings.sources.oparl
    files = council_files(layout)
    meetings = JsonlStore(files.meetings, OparlMeeting, exclude=frozenset({"agenda_item"}))
    items = JsonlStore(files.agenda_items, OparlAgendaItem)
    new_meetings, new_items = meetings.partial(), items.partial()
    known = meetings.load()
    since = since_for(known, "meetings" in council.incremental)
    run = _start(files.progress("meetings"), since, new_meetings.path, new_items.path)

    def write(kept: list[OparlMeeting]) -> None:
        new_meetings.append(kept)
        new_items.append(item for meeting in kept for item in meeting.agenda_item)

    start = settings.period.start
    _, report = fetch_objects(
        http,
        council.meetings_endpoint,
        OparlMeeting,
        keep=lambda meeting: meeting.starts_on_or_after(start),
        older=_all_before(start) if council.stop_when_older else None,
        delay_s=oparl.delay_s,
        modified_since=None if run.resume else run.since,
        max_pages=oparl.max_pages or None,  # `fetch meetings --max-pages N` als Probe
        resume_from=run.resume,
        on_page=_page_writer(run, write),
        sleep=sleep,
    )
    fetched = new_meetings.load()
    if report.next_url is not None:
        found = f"{len(fetched)} Sitzungen, {len(new_items.load())} Tagesordnungspunkte"
        return _probe(run, report, found)
    base = known if run.since else {}
    all_meetings = merge(base, fetched, report.deleted_ids)
    all_items = _children(
        items.load() if run.since else {},
        new_items.load(),
        all_meetings,
        fetched,
        lambda item: item.meeting,
        report.deleted_ids,
    )
    meetings.save(all_meetings.values())
    items.save(all_items.values())
    _finish(run, new_meetings.path, new_items.path)
    result = sum(1 for item in all_items.values() if item.result)
    consulted = sum(1 for item in all_items.values() if item.consultation)
    return (
        f"{run.mode}: {report.summary()}; {len(all_meetings)} Sitzungen, "
        f"{len(all_items)} Tagesordnungspunkte, {_share(result, len(all_items))} mit Ergebnis, "
        f"{_share(consulted, len(all_items))} mit Beratung"
    )


def run_consultations(
    settings: Settings,
    layout: Layout,
    http: Transport,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Alle Beratungen des Bodys nach ``consultations.jsonl``: Paper, Sitzung, Punkt, Rolle."""
    council, oparl = settings.council, settings.sources.oparl
    files = council_files(layout)
    store = JsonlStore(files.consultations, OparlConsultation)
    new = store.partial()
    known = store.load()
    since = since_for(known, "consultations" in council.incremental)
    run = _start(files.progress("consultations"), since, new.path)
    _, report = fetch_objects(
        http,
        council.consultations_endpoint,
        OparlConsultation,
        delay_s=oparl.delay_s,
        modified_since=None if run.resume else run.since,
        max_pages=oparl.max_pages or None,
        resume_from=run.resume,
        on_page=_page_writer(run, new.append),
        sleep=sleep,
    )
    fetched_consultations = new.load()
    if report.next_url is not None:
        return _probe(run, report, f"{len(fetched_consultations)} Beratungen")
    merged = merge(known if run.since else {}, fetched_consultations, report.deleted_ids)
    store.save(merged.values())
    _finish(run, new.path)
    linked = sum(1 for c in merged.values() if c.meeting and c.agenda_item)
    return (
        f"{run.mode}: {report.summary()}; {len(merged)} Beratungen, "
        f"{_share(linked, len(merged))} mit Sitzung und Tagesordnungspunkt"
    )


def run_persons(
    settings: Settings,
    layout: Layout,
    http: Transport,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Alle Personen mit ihren Mitgliedschaften nach ``persons.jsonl`` und ``memberships.jsonl``.

    Die Liste ``…/memberships`` braucht es nicht: die eingebetteten Mitgliedschaften sind
    dieselben Objekte (80 von 80 gleich in der Stichprobe vom 2026-11-23).
    """
    council, oparl = settings.council, settings.sources.oparl
    files = council_files(layout)
    persons = JsonlStore(files.persons, OparlPerson, exclude=frozenset({"membership"}))
    memberships = JsonlStore(files.memberships, OparlMembership)
    new_persons, new_memberships = persons.partial(), memberships.partial()
    known = persons.load()
    since = since_for(known, "persons" in council.incremental)
    run = _start(files.progress("persons"), since, new_persons.path, new_memberships.path)

    def write(kept: list[OparlPerson]) -> None:
        new_persons.append(kept)
        new_memberships.append(m for person in kept for m in person.membership)

    _, report = fetch_objects(
        http,
        council.persons_endpoint,
        OparlPerson,
        delay_s=oparl.delay_s,
        modified_since=None if run.resume else run.since,
        max_pages=oparl.max_pages or None,
        resume_from=run.resume,
        on_page=_page_writer(run, write),
        sleep=sleep,
    )
    fetched = new_persons.load()
    if report.next_url is not None:
        found = f"{len(fetched)} Personen, {len(new_memberships.load())} Mitgliedschaften"
        return _probe(run, report, found)
    all_persons = merge(known if run.since else {}, fetched, report.deleted_ids)
    all_memberships = _children(
        memberships.load() if run.since else {},
        new_memberships.load(),
        all_persons,
        fetched,
        lambda membership: membership.person,
        report.deleted_ids,
    )
    persons.save(all_persons.values())
    memberships.save(all_memberships.values())
    _finish(run, new_persons.path, new_memberships.path)
    voting = sum(1 for m in all_memberships.values() if m.voting_right)
    ended = sum(1 for m in all_memberships.values() if m.end_date is not None)
    return (
        f"{run.mode}: {report.summary()}; {len(all_persons)} Personen, "
        f"{len(all_memberships)} Mitgliedschaften, {_share(voting, len(all_memberships))} mit "
        f"Stimmrecht, {_share(ended, len(all_memberships))} beendet"
    )
