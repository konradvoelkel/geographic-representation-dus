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
import hashlib
import json
import os
import time
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import deal

from georep.errors import GeorepError
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

    def line(self, obj: O) -> str:
        return obj.model_dump_json(by_alias=True, exclude_none=True, exclude=set(self.exclude))

    def append(self, objects: Iterable[O]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            for obj in objects:
                f.write(self.line(obj) + "\n")

    def save(self, objects: Iterable[O]) -> int:
        """Alle Objekte, nach ID sortiert, atomar; zwei Läufe mit derselben Antwort sind bytegleich."""
        ordered = sorted(objects, key=lambda o: o.id)
        with atomic_path(self.path) as tmp, tmp.open("w", encoding="utf-8") as f:
            for obj in ordered:
                f.write(self.line(obj) + "\n")
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


class CouncilFetchError(GeorepError):
    """Ein Abruf kann nicht weiter: seine Teildatei ist verschwunden oder er läuft schon."""


# Die Marge von ``modified_since`` (jüngstes ``modified`` minus ein Tag) und zugleich das höchste
# Alter eines Fortschritts, der noch fortgesetzt wird: was älter ist, hätte zwischen seinen Seiten
# Änderungen verpassen können, die ``since`` beim nächsten Mal nicht mehr sieht (Review
# 2026-11-23, Befund 2).
SINCE_MARGIN = dt.timedelta(days=1)


def fetch_key(settings: Settings, endpoint: str) -> dict[str, str]:
    """Wofür ein Fortschritt gilt: Endpunkt, Periodenbeginn und ein Hash der Regeln ``[council]``.

    Weicht eines ab, wird er verworfen; eine Fortsetzung mit anderem Endpunkt oder Beginn mischte
    zwei Abrufe in eine Ausgabe.
    """
    rules = json.dumps(settings.council.model_dump(mode="json"), sort_keys=True)
    return {
        "endpoint": endpoint,
        "period_start": settings.period.start.isoformat(),
        "rules": hashlib.sha256(rules.encode()).hexdigest()[:16],
    }


def _line_ends(path: Path) -> list[int]:
    """Die Byte-Enden aller vollständigen Zeilen; eine halbe letzte Zeile zählt nicht."""
    data = path.read_bytes()
    return [i + 1 for i, byte in enumerate(data) if byte == 0x0A]


@dataclass
class _Cursor:
    """Der Fortschritt eines Listenabrufs und seine Teildateien, eine je Ausgabe.

    Nach jeder Seite: die Objekte an die Teildateien anhängen und mit ``fsync`` auf die Platte
    bringen, **dann** den Fortschritt schreiben -- mit der URL der nächsten Seite, der Zahl der
    Zeilen je Teildatei, den bisher gelöschten IDs und ``since``. Eine Fortsetzung kürzt jede
    Teildatei auf die Zeilen, die der Fortschritt nennt (eine halbe letzte Zeile nach einem Abbruch
    fällt weg); fehlt eine oder ist sie kürzer, ist er alt oder gehört er zu einem anderen
    Endpunkt, Periodenbeginn oder anderen Regeln, wird er verworfen und der Abruf beginnt von vorn
    (Review 2026-11-23, Befunde 2 und 5).
    """

    progress: Path
    partials: tuple[Path, ...]
    key: dict[str, str]
    since: dt.datetime | None
    started: dt.datetime
    resume: str | None = None
    pages: int = 0
    lines: dict[str, int] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)
    note: str = ""

    @classmethod
    def open(
        cls,
        progress: Path,
        partials: tuple[Path, ...],
        key: dict[str, str],
        since: dt.datetime | None,
    ) -> _Cursor:
        """Den Fortschritt fortsetzen, wenn er taugt; sonst leere Teildateien und ``since``."""
        now = dt.datetime.now(dt.UTC)
        saved = _read_progress(progress)
        note = ""
        if saved is not None:
            problem = _resume_problem(saved, partials, key, now)
            if problem is None:
                lines = {p.name: int(saved["lines"][p.name]) for p in partials}
                for partial in partials:
                    keep = lines[partial.name]
                    os.truncate(partial, _line_ends(partial)[keep - 1] if keep else 0)
                return cls(
                    progress,
                    partials,
                    key,
                    _when(saved.get("since")),
                    _when(saved["started"]) or now,
                    saved["next_url"],
                    int(saved["pages"]),
                    lines,
                    [str(i) for i in saved["deleted"]],
                )
            note = f"Fortschritt verworfen ({problem}); "
        progress.unlink(missing_ok=True)
        for partial in partials:
            partial.parent.mkdir(parents=True, exist_ok=True)
            partial.write_bytes(b"")
        empty = {p.name: 0 for p in partials}
        return cls(progress, partials, key, since, now, lines=empty, note=note)

    @property
    def mode(self) -> str:
        mode = f"seit {self.since.date()}" if self.since else "vollständig"
        return self.note + mode + (" (fortgesetzt)" if self.resume else "")

    @property
    def request_since(self) -> dt.datetime | None:
        """Eine Fortsetzung fragt ohne Filter: der ``next``-Link des Servers trägt ihn schon."""
        return None if self.resume else self.since

    def append[O: OparlObject](self, store: JsonlStore[O], objects: Iterable[O]) -> None:
        text = "".join(store.line(obj) + "\n" for obj in objects)
        with store.path.open("a", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        self.lines[store.path.name] += text.count("\n")

    def page(self, deleted: Iterable[str], next_url: str | None) -> None:
        """Nach den Teildateien der Fortschritt: so nennt er nie Zeilen, die nicht dastehen."""
        self.deleted.extend(i for i in deleted if i not in self.deleted)
        self.pages += 1
        write_json(
            self.progress,
            {
                "next_url": next_url,
                "pages": self.pages,
                "since": self.since.isoformat() if self.since else None,
                "started": self.started.isoformat(),
                "written": dt.datetime.now(dt.UTC).isoformat(),
                "key": self.key,
                "lines": self.lines,
                "deleted": self.deleted,
            },
        )

    def require_partials(self) -> None:
        """Am Ende muss jede Teildatei noch da sein; sonst hat ein anderer Lauf sie genommen."""
        missing = [p.name for p in self.partials if not p.is_file()]
        if missing:
            raise CouncilFetchError(
                f"{', '.join(missing)} fehlt am Ende des Abrufs; lief ein zweiter Abruf? "
                "Den Schritt noch einmal starten"
            )

    def finish(self) -> None:
        for partial in self.partials:
            partial.unlink(missing_ok=True)
        self.progress.unlink(missing_ok=True)

    def probe(self, report: ListReport, counts: str) -> str:
        """Die Zeile eines unvollständigen Abrufs (``--max-pages``): seine Zahlen, keine Ausgabe.

        Eine Probe schreibt keine Ausgabe (Review 2026-11-23, Befund 1): sonst ersetzte sie einen
        vollständigen Bestand durch ihre Seiten, und ``since`` käme beim nächsten Lauf aus ihr.
        """
        return (
            f"{self.mode}: {report.summary()}; Probe: {counts} bisher in der Teildatei, "
            "die Ausgabe bleibt, wie sie war; der nächste Lauf setzt fort"
        )


def _when(value: object) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value) if isinstance(value, str) else None


def _read_progress(progress: Path) -> dict[str, Any] | None:
    """Der gespeicherte Fortschritt, wenn er einen Fortsetzungspunkt nennt; sonst None."""
    try:
        saved = json.loads(progress.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    if not isinstance(saved, dict) or not isinstance(saved.get("next_url"), str):
        return None
    return saved if saved["next_url"] else None


def _resume_problem(
    saved: dict[str, Any], partials: tuple[Path, ...], key: dict[str, str], now: dt.datetime
) -> str | None:
    """Warum ein Fortschritt nicht fortgesetzt wird, oder None, wenn er es wird."""
    try:
        started = _when(saved["started"])
        lines = {p.name: int(saved["lines"][p.name]) for p in partials}
        if not isinstance(saved["deleted"], list) or int(saved["pages"]) < 0:
            return "unlesbar"
    except KeyError, TypeError, ValueError:
        return "unlesbar, ohne Zeilen oder Schlüssel"
    if saved.get("key") != key:
        stored = saved.get("key")
        known: dict[str, Any] = stored if isinstance(stored, dict) else {}
        names = {"endpoint": "Endpunkt", "period_start": "Periodenbeginn", "rules": "Regeln"}
        changed = [names[k] for k in key if known.get(k) != key[k]]
        return ", ".join(changed) + " geändert"
    if started is None or now - started > SINCE_MARGIN:
        return f"älter als {SINCE_MARGIN.days} Tag"
    for partial in partials:
        if not partial.is_file():
            return f"Teildatei fehlt: {partial.name}"
        if len(_line_ends(partial)) < lines[partial.name]:
            return f"Teildatei kürzer als der Fortschritt: {partial.name}"
    return None


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
    run = _Cursor.open(
        files.progress("meetings"),
        (new_meetings.path, new_items.path),
        fetch_key(settings, council.meetings_endpoint),
        since_for(known, "meetings" in council.incremental),
    )

    def page_done(kept: list[OparlMeeting], deleted: tuple[str, ...], next_url: str | None) -> None:
        run.append(new_meetings, kept)
        run.append(new_items, [item for meeting in kept for item in meeting.agenda_item])
        run.page(deleted, next_url)

    start = settings.period.start
    _, report = fetch_objects(
        http,
        council.meetings_endpoint,
        OparlMeeting,
        keep=lambda meeting: meeting.starts_on_or_after(start),
        older=_all_before(start) if council.stop_when_older else None,
        delay_s=oparl.delay_s,
        modified_since=run.request_since,
        max_pages=oparl.max_pages or None,  # `fetch meetings --max-pages N` als Probe
        resume_from=run.resume,
        on_page=page_done,
        sleep=sleep,
    )
    run.require_partials()
    fetched = new_meetings.load()
    if report.next_url is not None:
        found = f"{len(fetched)} Sitzungen, {len(new_items.load())} Tagesordnungspunkte"
        return run.probe(report, found)
    base = known if run.since else {}
    all_meetings = merge(base, fetched, run.deleted)
    all_items = _children(
        items.load() if run.since else {},
        new_items.load(),
        all_meetings,
        fetched,
        lambda item: item.meeting,
        run.deleted,
    )
    meetings.save(all_meetings.values())
    items.save(all_items.values())
    run.finish()
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
    run = _Cursor.open(
        files.progress("consultations"),
        (new.path,),
        fetch_key(settings, council.consultations_endpoint),
        since_for(known, "consultations" in council.incremental),
    )

    def page_done(
        kept: list[OparlConsultation], deleted: tuple[str, ...], next_url: str | None
    ) -> None:
        run.append(new, kept)
        run.page(deleted, next_url)

    _, report = fetch_objects(
        http,
        council.consultations_endpoint,
        OparlConsultation,
        delay_s=oparl.delay_s,
        modified_since=run.request_since,
        max_pages=oparl.max_pages or None,
        resume_from=run.resume,
        on_page=page_done,
        sleep=sleep,
    )
    run.require_partials()
    fetched_consultations = new.load()
    if report.next_url is not None:
        return run.probe(report, f"{len(fetched_consultations)} Beratungen")
    merged = merge(known if run.since else {}, fetched_consultations, run.deleted)
    store.save(merged.values())
    run.finish()
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
    run = _Cursor.open(
        files.progress("persons"),
        (new_persons.path, new_memberships.path),
        fetch_key(settings, council.persons_endpoint),
        since_for(known, "persons" in council.incremental),
    )

    def page_done(kept: list[OparlPerson], deleted: tuple[str, ...], next_url: str | None) -> None:
        run.append(new_persons, kept)
        run.append(new_memberships, [m for person in kept for m in person.membership])
        run.page(deleted, next_url)

    _, report = fetch_objects(
        http,
        council.persons_endpoint,
        OparlPerson,
        delay_s=oparl.delay_s,
        modified_since=run.request_since,
        max_pages=oparl.max_pages or None,
        resume_from=run.resume,
        on_page=page_done,
        sleep=sleep,
    )
    run.require_partials()
    fetched = new_persons.load()
    if report.next_url is not None:
        found = f"{len(fetched)} Personen, {len(new_memberships.load())} Mitgliedschaften"
        return run.probe(report, found)
    all_persons = merge(known if run.since else {}, fetched, run.deleted)
    all_memberships = _children(
        memberships.load() if run.since else {},
        new_memberships.load(),
        all_persons,
        fetched,
        lambda membership: membership.person,
        run.deleted,
    )
    persons.save(all_persons.values())
    memberships.save(all_memberships.values())
    run.finish()
    voting = sum(1 for m in all_memberships.values() if m.voting_right)
    ended = sum(1 for m in all_memberships.values() if m.end_date is not None)
    return (
        f"{run.mode}: {report.summary()}; {len(all_persons)} Personen, "
        f"{len(all_memberships)} Mitgliedschaften, {_share(voting, len(all_memberships))} mit "
        f"Stimmrecht, {_share(ended, len(all_memberships))} beendet"
    )
