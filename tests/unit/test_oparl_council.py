"""Fundament F6: Vertrag mit dem OParl-Server für Sitzungen, Tagesordnung, Beratungen, Personen.

Echte Antworten der Netzstichprobe vom 2026-11-23 (``tests/fixtures/http/README.md``, Abschnitt
„OParl: Sitzungen, Tagesordnung, Personen"), gekürzt und bei den Personen geschwärzt. Wie bei den
Papers schlägt ein Test an, sobald der Server Schlüssel liefert, die ein Modell nicht kennt; die
Befunde (was der Server füllt und was nicht) stehen als eigene Tests, damit ein geänderter Server
auffällt.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from georep.oparl import (
    PERSON_PRIVATE_KEYS,
    Links,
    ListPage,
    OparlAgendaItem,
    OparlConsultation,
    OparlFile,
    OparlMeeting,
    OparlMembership,
    OparlPerson,
    Pagination,
    PaperPage,
    known_aliases,
)
from tests.conftest import REPO

HTTP = REPO / "tests" / "fixtures" / "http"
BODY = HTTP / "oparl_body_0015.json"
MEETINGS = HTTP / "oparl_meetings_0015.json"
AGENDA_ITEMS = HTTP / "oparl_agendaitems_0015.json"
PEOPLE = HTTP / "oparl_people_0015.json"
MEMBERSHIPS = HTTP / "oparl_memberships_0015.json"
CONSULTATION = HTTP / "oparl_consultation_141791.json"
AGENDA_ITEM = HTTP / "oparl_agendaitem_399178.json"
MINUTES = HTTP / "oparl_file_541049.json"
PAPERS = REPO / "tests" / "fixtures" / "oparl" / "papers_page.json"

LISTS = [MEETINGS, AGENDA_ITEMS, PEOPLE, MEMBERSHIPS]


def _raw(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _page(path: Path) -> ListPage:
    return ListPage.model_validate_json(path.read_text(encoding="utf-8"))


def _files(item: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for key in keys:
        value = item.get(key)
        found.extend(value if isinstance(value, list) else [value] if value else [])
    return found


@pytest.mark.parametrize("path", LISTS, ids=lambda p: p.stem)
def test_every_recorded_list_page_has_the_envelope_of_the_paper_pages(path: Path) -> None:
    raw = _raw(path)
    assert set(raw) == {"data", "pagination", "links"}
    assert set(raw["pagination"]) <= known_aliases(Pagination)
    assert set(raw["links"]) <= known_aliases(Links)
    page = _page(path)
    assert page.data and page.pagination is not None
    assert page.pagination.elements_per_page == 200  # wie bei den Papers
    assert page.links.next is not None and "?page=" in page.links.next


def test_the_body_names_the_lists_the_profile_uses() -> None:
    """Die Endpunkte im Profil stehen im Body-Objekt; der Server nennt die Personenliste
    ``people`` und schreibt ``consultations`` und ``files`` im Plural (OParl 1.1 sagt
    ``consultation``, ``file``)."""
    body = _raw(BODY)
    assert body["meeting"].endswith("/meetings")
    assert body["person"].endswith("/people")
    assert body["membership"].endswith("/memberships")
    assert body["agendaItem"].endswith("/agendaitems")
    assert body["consultations"].endswith("/consultations")


# --- Sitzungen und Tagesordnung -----------------------------------------------------------------


@pytest.fixture(scope="module")
def meetings() -> list[OparlMeeting]:
    return [OparlMeeting.model_validate(item) for item in _page(MEETINGS).data]


def test_the_meeting_models_know_every_key_the_server_sends() -> None:
    raw = _raw(MEETINGS)["data"]
    meeting_keys = {k for m in raw for k in m}
    item_keys = {k for m in raw for a in m.get("agendaItem", []) for k in a}
    item_keys |= {k for a in _raw(AGENDA_ITEMS)["data"] for k in a} | set(_raw(AGENDA_ITEM))
    file_keys = {
        k
        for m in raw
        for f in _files(m, "invitation", "resultsProtocol", "verbatimProtocol", "auxiliaryFile")
        for k in f
    } | set(_raw(MINUTES))
    assert meeting_keys <= known_aliases(OparlMeeting), meeting_keys - known_aliases(OparlMeeting)
    assert item_keys <= known_aliases(OparlAgendaItem), item_keys - known_aliases(OparlAgendaItem)
    assert file_keys <= known_aliases(OparlFile), file_keys - known_aliases(OparlFile)


def test_meetings_are_typed_with_their_agenda(meetings: list[OparlMeeting]) -> None:
    assert len(meetings) == 4
    committee = meetings[0]
    assert committee.id.endswith("/meetings/26272") and committee.name
    assert committee.start == dt.datetime(
        2024, 12, 2, 15, 0, tzinfo=dt.timezone(dt.timedelta(hours=1))
    )
    assert committee.organization and all(o.startswith("http") for o in committee.organization)
    assert committee.participant and all("/people/" in p for p in committee.participant)
    assert len(committee.agenda_item) == 8
    assert all(item.meeting == committee.id for item in committee.agenda_item)
    assert [item.order for item in committee.agenda_item] == sorted(
        item.order or 0 for item in committee.agenda_item
    )
    joint = meetings[1]
    assert len(joint.organization) == 2  # gemeinsame Sitzung zweier Gremien
    assert [m.agenda_item for m in meetings[2:]] == [[], []]  # ohne öffentliche Tagesordnung


def test_the_server_sets_neither_state_nor_resolution(meetings: list[OparlMeeting]) -> None:
    """Befund 2026-11-23: ``cancelled``, ``meetingState``, ``resolutionText``, ``resolutionFile``
    sind auf beiden Seiten der Stichprobe leer (0 von 400 Sitzungen, 0 von 9 495 Punkten)."""
    items = [item for m in meetings for item in m.agenda_item]
    assert all(m.cancelled is None and m.meeting_state is None for m in meetings)
    assert all(i.resolution_text is None and i.resolution_file is None for i in items)
    assert all(i.start is None and i.end is None and i.public is True for i in items)


def test_the_result_is_filled_where_there_is_a_consultation(meetings: list[OparlMeeting]) -> None:
    """``result`` trägt das Ergebnis in Worten; ein Punkt ohne Beratung ist meist Verfahren."""
    items = [item for m in meetings for item in m.agenda_item]
    with_consultation = [i for i in items if i.consultation is not None]
    assert with_consultation and all(i.result for i in with_consultation)
    assert {i.result for i in items} >= {
        "einstimmig beschlossen",
        "vertagt",
        "zur Kenntnis genommen",
    }
    assert any(i.consultation is None for i in items)


def test_the_results_protocol_is_not_the_minutes(meetings: list[OparlMeeting]) -> None:
    """Befund 2026-11-23: wo der Server ``resultsProtocol`` setzt, ist es dieselbe Datei wie
    ``invitation`` und ``verbatimProtocol``, ein Nachtrag zur Tagesordnung (140 von 140 auf
    Seite 4). Die Niederschrift liegt unter ``auxiliaryFile``."""
    committee = meetings[0]
    assert committee.results_protocol is not None
    assert committee.invitation is not None and committee.verbatim_protocol is not None
    assert (
        committee.results_protocol.id == committee.invitation.id == committee.verbatim_protocol.id
    )
    assert "Niederschrift" not in (committee.results_protocol.name or "")
    minutes = [f for f in committee.auxiliary_file if (f.name or "").startswith("Niederschrift")]
    assert [f.id for f in minutes] == [_raw(MINUTES)["id"]]


def test_the_minutes_file_names_its_meeting_but_no_size() -> None:
    minutes = OparlFile.model_validate(_raw(MINUTES))
    assert minutes.name == "Niederschrift Ö" and minutes.mime_type == "application/pdf"
    assert minutes.meeting == (
        "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/meetings/26272",
    )
    assert minutes.size is None  # der Server nennt keine Größe; die Hochrechnung braucht HEAD


def test_a_meeting_without_start_counts_as_in_the_period() -> None:
    meeting = OparlMeeting.model_validate(
        {"id": "x", "start": "2020-10-31T23:30:00+01:00", "agendaItem": []}
    )
    assert meeting.starts_on_or_after(dt.date(2020, 10, 31))
    assert not meeting.starts_on_or_after(dt.date(2020, 11, 1))
    assert OparlMeeting(id="y").starts_on_or_after(dt.date(2100, 1, 1))


def test_agenda_items_of_the_list_and_the_single_object_are_the_same_model() -> None:
    single = OparlAgendaItem.model_validate(_raw(AGENDA_ITEM))
    assert single.result == "zur Kenntnis genommen" and single.number == "48"
    assert single.consultation is not None and single.consultation.endswith("/consultations/141791")
    listed = [OparlAgendaItem.model_validate(item) for item in _page(AGENDA_ITEMS).data]
    assert len(listed) == 4 and all(item.meeting for item in listed)


# --- Beratungen ----------------------------------------------------------------------------------


def test_the_consultation_links_paper_meeting_and_agenda_item() -> None:
    raw = _raw(CONSULTATION)
    assert set(raw) <= known_aliases(OparlConsultation), set(raw) - known_aliases(OparlConsultation)
    consultation = OparlConsultation.model_validate(raw)
    assert consultation.paper is not None and consultation.paper.endswith("/papers/vo/114093")
    assert consultation.agenda_item is not None and consultation.agenda_item.endswith("/399178")
    assert consultation.meeting is not None and consultation.meeting.endswith("/meetings/29513")
    assert consultation.organization == (
        "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/organizations/gr/35",
    )
    assert consultation.authoritative is True and consultation.role == "Kenntnisnahme"
    # Der Punkt nennt die Beratung, die Beratung den Punkt: die Verbindung geht in beide Richtungen
    item = OparlAgendaItem.model_validate(_raw(AGENDA_ITEM))
    assert item.consultation == consultation.id and consultation.agenda_item == item.id


def test_the_paper_pages_embed_the_same_consultations() -> None:
    """Der billigste Weg vom Paper zur Sitzung: die Paper-Liste trägt die Beratungen schon."""
    page = PaperPage.model_validate_json(PAPERS.read_text(encoding="utf-8"))
    consultations = [c for paper in page.data for c in paper.consultations]
    assert len(consultations) >= len(page.data)
    assert all(isinstance(c, OparlConsultation) for c in consultations)
    assert all(c.meeting and c.agenda_item for c in consultations)
    for paper in page.data:
        assert all(c.paper == paper.id for c in paper.consultations)
        assert {o for c in paper.consultations for o in c.organization} == set(
            paper.consultation_organizations
        )


def test_a_single_organization_url_is_read_as_a_tuple() -> None:
    consultation = OparlConsultation.model_validate({"id": "x", "organization": "https://o/1"})
    assert consultation.organization == ("https://o/1",)
    assert OparlConsultation(id="y").organization == ()


# --- Personen und Mitgliedschaften --------------------------------------------------------------


def test_the_person_model_knows_every_key_except_the_private_ones() -> None:
    raw = _raw(PEOPLE)["data"]
    person_keys = {k for p in raw for k in p}
    membership_keys = {k for p in raw for m in p.get("membership", []) for k in m}
    membership_keys |= {k for m in _raw(MEMBERSHIPS)["data"] for k in m}
    unknown = person_keys - known_aliases(OparlPerson)
    assert unknown <= PERSON_PRIVATE_KEYS, unknown - PERSON_PRIVATE_KEYS
    assert unknown >= {"phone", "email", "location", "locationObject"}  # der Server schickt sie
    assert membership_keys <= known_aliases(OparlMembership), membership_keys - known_aliases(
        OparlMembership
    )


def test_the_person_model_never_carries_contact_data() -> None:
    """Personen nur in öffentlicher Rolle: Kontaktdaten kennt das Modell nicht, also schreibt
    kein Lauf sie (Plan 2026-11, § 1)."""
    assert not PERSON_PRIVATE_KEYS & known_aliases(OparlPerson)
    for item in _page(PEOPLE).data:
        dumped = OparlPerson.model_validate(item).model_dump(by_alias=True)
        assert not PERSON_PRIVATE_KEYS & set(dumped)
        assert "entfernt" not in json.dumps(dumped, default=str)


def test_persons_carry_their_memberships() -> None:
    persons = [OparlPerson.model_validate(item) for item in _page(PEOPLE).data]
    assert len(persons) == 3
    first = persons[0]
    assert first.title == ("Dipl.Ing.",) and first.family_name == "Nachname1"
    assert len(first.membership) == 3 and all(m.person == first.id for m in first.membership)
    assert all(m.role and m.start_date for p in persons for m in p.membership)
    assert persons[2].membership == []


def test_memberships_know_their_voting_right_and_period() -> None:
    listed = [OparlMembership.model_validate(item) for item in _page(MEMBERSHIPS).data]
    assert [m.voting_right for m in listed] == [True, None, None, True]
    ended = next(m for m in listed if m.end_date is not None)
    assert ended.start_date is not None and ended.end_date is not None
    assert ended.active_on(ended.end_date) and not ended.active_on(
        ended.end_date + dt.timedelta(days=1)
    )
    assert OparlMembership(id="x").active_on(dt.date(1900, 1, 1))


def test_unknown_keys_are_ignored_in_every_new_model() -> None:
    for model in (OparlMeeting, OparlAgendaItem, OparlConsultation, OparlPerson, OparlMembership):
        assert model.model_validate({"id": "x", "neuesFeld": 1}).id == "x"


def test_recorded_files_are_small_enough_to_read_in_a_review() -> None:
    for path in [
        BODY,
        MEETINGS,
        AGENDA_ITEMS,
        PEOPLE,
        MEMBERSHIPS,
        CONSULTATION,
        AGENDA_ITEM,
        MINUTES,
    ]:
        assert path.stat().st_size < 40_000, path.name
