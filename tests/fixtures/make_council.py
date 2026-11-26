"""Die Fixture ``tests/fixtures/council/``: ein Dutzend Paper mit ihren Beratungen, Punkten und Sitzungen.

Vorhaben 26 (``docs/plans/26-beschluesse.md``, § 6). Aus dem Netzlauf vom 2026-11-23 der Hauptperiode
(``<data_root>/duesseldorf/raw/*.jsonl``, Fundament F6) gezogen, für genau die Paper in ``PAPERS``:
ihre Beratungen, jeder Tagesordnungspunkt, der eine davon nennt oder den eine nennt, und deren
Sitzungen -- dieselbe Verbindung wie ``analysis.outcomes.agenda_rows``. Neu erzeugen nur mit dem
Netzlauf auf dem Rechner (er liegt nicht im Repo)::

    uv run python -m tests.fixtures.make_council /media/konrad/xtraspace/georep/data/duesseldorf/raw

**Geschwärzt wie F6**: geschrieben werden nur die Felder, die die Verbindung braucht (IDs, Sitzung,
Beginn, Organisation, Nummer, Folge, Beratung, Ergebnis, Rolle, Paper). Bezeichnungen der Punkte,
Namen und Anlagen der Sitzungen, Orte und Teilnehmer fehlen; sie lesen die Schritte nicht, und in
ihnen können Namen von Personen stehen.
"""

from __future__ import annotations

import sys
from pathlib import Path

from georep.council import JsonlStore
from georep.oparl import OparlAgendaItem, OparlConsultation, OparlMeeting

FIXTURE = Path(__file__).resolve().parent / "council"
BASE = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers/vo/"
# Paper -> was es zeigt; acht davon gehören zur Mini-Fixture (``tests/fixtures/mini``).
PAPERS = {
    "90981": "Antrag: verwiesen, dann zurückgezogen (Mini)",
    "100007": "Vorlage: dreimal vertagt (Mini)",
    "108685": "Anfrage: vertagt, dann schriftlich beantwortet (Mini)",
    "89029": "Vorlage: beschlossen, Empfehlung, zuletzt abweichend beschlossen (Mini)",
    "100373": "Vorlage: beschlossen, danach zur Kenntnis genommen (Mini)",
    "100041": "Vorlage: vertagt, passieren lassen, zuletzt mehrheitlich beschlossen (Mini)",
    "90523": "Antrag: mehrheitlich abgelehnt (Mini)",
    "87916": "Vorlage: Tagesordnungspunkt ohne Ergebnis (Mini)",
    "94646": "Vorlage: Empfehlung abweichend beschlossen, zuletzt beschlossen (Mini)",
    "100162": "Antrag: eine Beratung ohne Tagesordnungspunkt im Datensatz",
    "88452": "Haushaltsantrag in der Haushaltssitzung des Rates vom 2021-02-05, ohne Ergebnis",
    "101779": "Haushaltsantrag in einem Gremium ohne Kürzel im Profil (gr/400224, Frage 9.17)",
}
MEETING_FIELDS = {"id", "type", "start", "end", "organization"}
ITEM_FIELDS = {"id", "type", "meeting", "number", "order", "consultation", "result"}
CONSULTATION_FIELDS = {
    "id",
    "type",
    "paper",
    "agenda_item",
    "meeting",
    "organization",
    "role",
    "authoritative",
}


def main(raw: Path) -> None:
    wanted = {BASE + key for key in PAPERS}
    consultations = [
        c
        for c in JsonlStore(raw / "consultations.jsonl", OparlConsultation).load().values()
        if c.paper in wanted
    ]
    ids = {c.id for c in consultations}
    all_items = JsonlStore(raw / "agenda_items.jsonl", OparlAgendaItem).load()
    items = {
        i.id: i
        for i in all_items.values()
        if i.consultation in ids or any(c.agenda_item == i.id for c in consultations)
    }
    meetings = {
        m.id: m
        for m in JsonlStore(raw / "meetings.jsonl", OparlMeeting).load().values()
        if m.id in {i.meeting for i in items.values()} | {c.meeting for c in consultations}
    }
    FIXTURE.mkdir(parents=True, exist_ok=True)
    for name, objects, fields in (
        ("consultations.jsonl", sorted(consultations, key=lambda o: o.id), CONSULTATION_FIELDS),
        ("agenda_items.jsonl", sorted(items.values(), key=lambda o: o.id), ITEM_FIELDS),
        ("meetings.jsonl", sorted(meetings.values(), key=lambda o: o.id), MEETING_FIELDS),
    ):
        lines = [
            o.model_dump_json(by_alias=True, exclude_none=True, include=fields) for o in objects
        ]
        (FIXTURE / name).write_text("".join(line + "\n" for line in lines), encoding="utf-8")
        print(f"{name}: {len(lines)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
