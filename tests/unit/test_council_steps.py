"""Fundament F6: die Netzschritte meetings, consultations, persons gegen die Fake-Session.

Die Antworten sind die aufgezeichneten Seiten vom 2026-11-23 (``tests/fixtures/http``); die Seite
hinter ihrem ``next`` ist eine leere letzte Seite. Kein Test geht ins Netz.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest
import requests
from pydantic import ValidationError

from georep.council import COUNCIL_SCHEMA_VERSION, council_files
from georep.errors import NetworkError
from georep.layout import Layout
from georep.oparl import PERSON_PRIVATE_KEYS
from georep.pipeline import build_steps, run_pipeline
from georep.settings import Settings, load_settings
from tests.conftest import REPO
from tests.fakes import FakeSession, response

HTTP = REPO / "tests" / "fixtures" / "http"
PAPERS = REPO / "tests" / "fixtures" / "oparl" / "papers_page.json"
STEPS = ["meetings", "consultations", "persons"]
LAST = {"data": [], "pagination": {"elementsPerPage": 200}, "links": {}}


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def _layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")


def _recorded(endpoint: str, name: str) -> dict[str, requests.Response | Exception]:
    """Die aufgezeichnete Seite unter dem Endpunkt des Profils, dahinter eine leere letzte."""
    content = (HTTP / name).read_bytes()
    following = json.loads(content)["links"]["next"]
    return {
        endpoint: response(endpoint, content=content),
        following: response(following, payload=LAST),
    }


def _consultation_page() -> dict[str, Any]:
    """Die in die Paper-Seite eingebetteten Beratungen als Seite der Liste ``consultations``."""
    papers = json.loads(PAPERS.read_text(encoding="utf-8"))["data"]
    return {"data": [c for p in papers for c in p["consultation"]], "links": {}}


def _session(settings: Settings) -> FakeSession:
    council = settings.council
    return FakeSession(
        _recorded(council.meetings_endpoint, "oparl_meetings_0015.json")
        | _recorded(council.persons_endpoint, "oparl_people_0015.json")
        | {
            council.consultations_endpoint: response(
                council.consultations_endpoint, payload=_consultation_page()
            )
        }
    )


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --- Settings und Register ----------------------------------------------------------------------


def test_the_defaults_name_no_endpoint_and_the_profiles_name_their_body() -> None:
    defaults = tomllib.loads(
        (REPO / "src" / "georep" / "defaults.toml").read_text(encoding="utf-8")
    )["council"]
    assert defaults["meetings_endpoint"] == defaults["persons_endpoint"] == ""
    assert defaults["consultations_endpoint"] == ""
    for profile, body in (("duesseldorf", "0015"), ("moenchengladbach", "0011")):
        council = load_settings(profile=profile, cwd=Path("/nonexistent")).council
        assert council.meetings_endpoint.endswith(f"/bodies/{body}/meetings")
        assert council.consultations_endpoint.endswith(f"/bodies/{body}/consultations")
        assert council.persons_endpoint.endswith(f"/bodies/{body}/people")  # nicht „persons"
        assert council.incremental == ("consultations",) and council.stop_when_older


def test_incremental_names_only_the_three_steps(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('council.incremental = ["papers"]\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="incremental"):
        load_settings(cwd=tmp_path)


def test_the_steps_exist_with_their_endpoints_and_need_the_network(
    tmp_path: Path, settings: Settings
) -> None:
    steps = {s.name: s for s in build_steps(settings, _layout(tmp_path))}
    files = council_files(_layout(tmp_path))
    assert steps["meetings"].outputs == (files.meetings, files.agenda_items)
    assert steps["consultations"].outputs == (files.consultations,)
    assert steps["persons"].outputs == (files.persons, files.memberships)
    for name in STEPS:
        assert steps[name].network and steps[name].inputs == ()
        assert steps[name].schema_version == COUNCIL_SCHEMA_VERSION
    empty = settings.council.model_copy(
        update={"meetings_endpoint": "", "consultations_endpoint": "", "persons_endpoint": ""}
    )
    without = build_steps(settings.model_copy(update={"council": empty}), _layout(tmp_path))
    assert not {s.name for s in without} & set(STEPS)


def test_offline_and_dry_runs_touch_no_network(tmp_path: Path, settings: Settings) -> None:
    session = FakeSession({})
    steps = build_steps(settings, _layout(tmp_path), session, sleep=lambda _: None)
    offline = run_pipeline(steps, settings, STEPS)
    assert [o.status for o in offline] == ["übersprungen"] * 3
    planned = run_pipeline(steps, settings, STEPS, online=True, dry_run=True)
    assert [o.status for o in planned] == ["geplant"] * 3 and session.calls == []


# --- die drei Schritte ---------------------------------------------------------------------------


def test_the_three_steps_write_one_file_per_kind(tmp_path: Path, settings: Settings) -> None:
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    files = council_files(layout)
    slept: list[float] = []
    steps = build_steps(settings, layout, _session(settings), sleep=slept.append)
    outcomes = {o.step: o for o in run_pipeline(steps, settings, STEPS, online=True)}
    assert all(o.status == "ausgeführt" for o in outcomes.values())
    assert "4 Sitzungen, 11 Tagesordnungspunkte" in outcomes["meetings"].reason
    assert (
        "6 Beratungen, 100% mit Sitzung und Tagesordnungspunkt" in outcomes["consultations"].reason
    )
    assert "3 Personen, 6 Mitgliedschaften" in outcomes["persons"].reason
    assert slept == [settings.sources.oparl.delay_s] * 2  # je eine Pause vor der zweiten Seite

    meetings = _lines(files.meetings)
    assert [m["id"] for m in meetings] == sorted(m["id"] for m in meetings)
    assert all("agendaItem" not in m for m in meetings)  # die Tagesordnung steht für sich
    items = _lines(files.agenda_items)
    assert len(items) == 11 and {i["meeting"] for i in items} <= {m["id"] for m in meetings}
    assert sum(1 for i in items if "result" in i) == 8

    consultations = _lines(files.consultations)
    assert all(c["paper"] and c["meeting"] and c["agendaItem"] for c in consultations)

    persons = _lines(files.persons)
    assert len(persons) == 3 and all("membership" not in p for p in persons)
    text = files.persons.read_text(encoding="utf-8") + files.memberships.read_text(encoding="utf-8")
    assert not any(f'"{key}"' in text for key in PERSON_PRIVATE_KEYS)
    assert "entfernt" not in text
    memberships = _lines(files.memberships)
    holders = {m["person"] for m in memberships}
    assert len(memberships) == 6 and len(holders) == 2 and holders <= {p["id"] for p in persons}
    # kein Fortschritt und keine Teildatei bleibt nach einem vollständigen Abruf liegen
    assert not list(layout.raw.glob("*.progress.json")) and not list(layout.raw.glob("*.partial"))


def test_a_second_run_is_byte_identical(tmp_path: Path, settings: Settings) -> None:
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    files = council_files(layout)
    steps = build_steps(settings, layout, _session(settings), sleep=lambda _: None)
    run_pipeline(steps, settings, ["meetings", "persons"], online=True)
    first = files.meetings.read_bytes(), files.persons.read_bytes()
    again = run_pipeline(steps, settings, ["meetings", "persons"], online=True)
    assert [o.status for o in again] == ["übersprungen"] * 2  # aktuell: erst --force holt neu
    forced = build_steps(settings, layout, _session(settings), sleep=lambda _: None)
    run_pipeline(forced, settings, ["meetings", "persons"], online=True, force=True)
    assert (files.meetings.read_bytes(), files.persons.read_bytes()) == first


def test_meetings_before_the_period_are_left_out_and_end_the_fetch(
    tmp_path: Path, settings: Settings
) -> None:
    """Die Seite liegt ganz vor einem Beginn 2025: nichts bleibt, und Seite 5 wird nicht gelesen."""
    late = settings.period.model_copy(update={"start": settings.period.start.replace(year=2025)})
    later = settings.model_copy(update={"period": late})
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    session = _session(settings)
    steps = build_steps(later, layout, session, sleep=lambda _: None)
    outcome = run_pipeline(steps, later, ["meetings"], online=True)[0]
    assert "0 Sitzungen" in outcome.reason and "Rest älter als der Periodenbeginn" in outcome.reason
    assert session.urls == [settings.council.meetings_endpoint]
    assert council_files(layout).meetings.read_text(encoding="utf-8") == ""


def test_consultations_catch_up_with_modified_since(tmp_path: Path, settings: Settings) -> None:
    """Der zweite Lauf fragt nur nach Geändertem (jüngstes ``modified`` minus ein Tag), legt es
    über den Bestand und nimmt Gelöschtes heraus."""
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    files = council_files(layout)
    endpoint = settings.council.consultations_endpoint
    steps = build_steps(settings, layout, _session(settings), sleep=lambda _: None)
    run_pipeline(steps, settings, ["consultations"], online=True)
    before = {c["id"]: c for c in _lines(files.consultations)}
    newest = max(before.values(), key=lambda c: c["modified"])
    changed = dict(newest) | {"role": "Entscheidung", "modified": "2026-11-20T10:00:00+01:00"}
    gone = next(c for c in before.values() if c["id"] != newest["id"])
    page = {"data": [changed, {"id": gone["id"], "deleted": True}], "links": {}}
    session = FakeSession({endpoint: response(endpoint, payload=page)})
    rebuilt = build_steps(settings, layout, session, sleep=lambda _: None)
    outcome = run_pipeline(rebuilt, settings, ["consultations"], online=True, force=True)[0]
    assert "seit 2026-10-07" in outcome.reason and "1 gelöscht" in outcome.reason
    (url, params), *_ = session.calls
    assert url == endpoint and params["modified_since"].startswith("2026-10-07T08:55:52")
    after = {c["id"]: c for c in _lines(files.consultations)}
    assert set(after) == set(before) - {gone["id"]}
    assert after[newest["id"]]["role"] == "Entscheidung"


def test_meetings_are_fetched_whole_because_their_modified_lags(
    tmp_path: Path, settings: Settings
) -> None:
    """``meetings`` steht nicht in ``council.incremental``: ein zweiter Lauf fragt ohne
    ``modified_since`` und ersetzt den Bestand (Befund: Tagesordnung jünger als die Sitzung)."""
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    first = build_steps(settings, layout, _session(settings), sleep=lambda _: None)
    run_pipeline(first, settings, ["meetings"], online=True)
    session = _session(settings)
    again = build_steps(settings, layout, session, sleep=lambda _: None)
    outcome = run_pipeline(again, settings, ["meetings"], online=True, force=True)[0]
    assert outcome.reason.startswith("erzwungen; vollständig:")
    assert all(params is None for _, params in session.calls)


def test_an_aborted_fetch_keeps_the_old_file_and_resumes(
    tmp_path: Path, settings: Settings
) -> None:
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    files = council_files(layout)
    steps = build_steps(settings, layout, _session(settings), sleep=lambda _: None)
    run_pipeline(steps, settings, ["meetings"], online=True)
    complete = files.meetings.read_bytes()

    routes = _recorded(settings.council.meetings_endpoint, "oparl_meetings_0015.json")
    following = next(url for url in routes if url != settings.council.meetings_endpoint)
    broken = FakeSession(routes | {following: requests.ConnectionError("Server weg")})
    aborted = build_steps(settings, layout, broken, sleep=lambda _: None)
    with pytest.raises(NetworkError, match="Server weg"):
        run_pipeline(aborted, settings, ["meetings"], online=True, force=True)
    assert files.meetings.read_bytes() == complete  # die alte Ausgabe bleibt, wie sie war
    progress = json.loads(files.progress("meetings").read_text(encoding="utf-8"))
    assert progress["next_url"] == following and progress["pages"] == 1

    healed = _session(settings)
    resumed = build_steps(settings, layout, healed, sleep=lambda _: None)
    outcome = run_pipeline(resumed, settings, ["meetings"], online=True, force=True)[0]
    assert "(fortgesetzt)" in outcome.reason and healed.urls == [following]
    assert files.meetings.read_bytes() == complete  # Seite 1 aus der Teildatei, Seite 2 neu
    assert not files.progress("meetings").exists()


def _probing(settings: Settings) -> Settings:
    probe = settings.sources.oparl.model_copy(update={"max_pages": 1})
    return settings.model_copy(
        update={"sources": settings.sources.model_copy(update={"oparl": probe})}
    )


def test_max_pages_is_a_probe_and_the_next_run_goes_on_from_there(
    tmp_path: Path, settings: Settings
) -> None:
    """``fetch persons --max-pages 1`` ist der Anfang des Abrufs, nicht ein kleiner ganzer: die
    Zeile nennt die Zahlen der Probe, die Ausgabe entsteht erst mit dem letzten Blatt, und der
    nächste Lauf ohne Grenze setzt bei Seite 2 fort (Review 2026-11-23, Befund 1)."""
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    files = council_files(layout)
    session = _session(settings)
    probing = _probing(settings)
    steps = build_steps(probing, layout, session, sleep=lambda _: None)
    outcome = run_pipeline(steps, probing, ["persons"], online=True)[0]
    assert "1 Seite(n)" in outcome.reason and "weiter bei" in outcome.reason
    assert "Probe: 3 Personen, 6 Mitgliedschaften" in outcome.reason
    assert session.urls == [settings.council.persons_endpoint]
    assert not files.persons.exists() and not files.memberships.exists()
    following = json.loads((HTTP / "oparl_people_0015.json").read_text(encoding="utf-8"))
    progress = json.loads(files.progress("persons").read_text(encoding="utf-8"))
    assert progress["next_url"] == following["links"]["next"]

    rest = _session(settings)
    full = build_steps(settings, layout, rest, sleep=lambda _: None)
    outcome = run_pipeline(full, settings, ["persons"], online=True)[0]
    assert outcome.reason.startswith(
        "Ausgabe fehlt: persons.jsonl, memberships.jsonl; vollständig (fortgesetzt):"
    )
    assert rest.urls == [following["links"]["next"]] and rest.calls[0][1] is None
    assert len(_lines(files.persons)) == 3 and not files.progress("persons").exists()


def test_a_probe_does_not_make_the_next_run_incremental(tmp_path: Path, settings: Settings) -> None:
    """Beratungen holen bei vorhandenem Bestand nur Geändertes; der Bestand einer Probe zählt
    nicht als Bestand, sonst fehlte nach Probe und vollem Lauf alles außer Seite 1."""
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    endpoint = settings.council.consultations_endpoint
    following = "https://ris.invalid/consultations?page=2"
    first = _consultation_page() | {"links": {"next": following}}
    second: dict[str, Any] = {"data": [], "links": {}}
    routes: dict[str, requests.Response | Exception] = {
        endpoint: response(endpoint, payload=first),
        following: response(following, payload=second),
    }
    probing = _probing(settings)
    run_pipeline(
        build_steps(probing, layout, FakeSession(routes), sleep=lambda _: None),
        probing,
        ["consultations"],
        online=True,
    )
    session = FakeSession(routes)
    run_pipeline(
        build_steps(settings, layout, session, sleep=lambda _: None),
        settings,
        ["consultations"],
        online=True,
    )
    assert session.calls == [(following, None)]  # fortgesetzt, ohne modified_since


def test_a_probe_leaves_a_complete_output_as_it_was(tmp_path: Path, settings: Settings) -> None:
    """Review 2026-11-23, Befund 1: eine Probe auf einem vollständigen Bestand ersetzte ihn durch
    ihre eine Seite, weil ohne ``incremental`` nichts darunter lag."""
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    files = council_files(layout)
    run_pipeline(
        build_steps(settings, layout, _session(settings), sleep=lambda _: None),
        settings,
        ["meetings", "persons"],
        online=True,
    )
    complete = {path: path.read_bytes() for path in (files.meetings, files.agenda_items)}
    complete |= {path: path.read_bytes() for path in (files.persons, files.memberships)}
    # die Probe sieht nur die ersten beiden Sitzungen der Seite
    endpoint = settings.council.meetings_endpoint
    page = json.loads((HTTP / "oparl_meetings_0015.json").read_text(encoding="utf-8"))
    short = {"data": page["data"][:2], "links": {"next": f"{endpoint}?page=2"}}
    session = FakeSession(
        _recorded(settings.council.persons_endpoint, "oparl_people_0015.json")
        | {endpoint: response(endpoint, payload=short)}
    )
    probing = _probing(settings)
    outcomes = run_pipeline(
        build_steps(probing, layout, session, sleep=lambda _: None),
        probing,
        ["meetings", "persons"],
        online=True,
        force=True,
    )
    assert "Probe: 2 Sitzungen" in outcomes[0].reason
    assert {path: path.read_bytes() for path in complete} == complete


def test_starting_over_after_a_probe_is_a_full_fetch(tmp_path: Path, settings: Settings) -> None:
    """Probe auf leerem Bestand, dann „Neu beginnen" (Fortschritt gelöscht): ``since`` darf nicht
    aus der Probe kommen, der Lauf fragt also ohne ``modified_since`` von vorn."""
    layout = _layout(tmp_path)
    layout.ensure_dirs()
    files = council_files(layout)
    endpoint = settings.council.consultations_endpoint
    following = "https://ris.invalid/consultations?page=2"
    routes: dict[str, requests.Response | Exception] = {
        endpoint: response(endpoint, payload=_consultation_page() | {"links": {"next": following}}),
        following: response(following, payload={"data": [], "links": {}}),
    }
    probing = _probing(settings)
    run_pipeline(
        build_steps(probing, layout, FakeSession(routes), sleep=lambda _: None),
        probing,
        ["consultations"],
        online=True,
    )
    files.progress("consultations").unlink()
    session = FakeSession(routes)
    run_pipeline(
        build_steps(settings, layout, session, sleep=lambda _: None),
        settings,
        ["consultations"],
        online=True,
    )
    assert session.calls == [(endpoint, None), (following, None)]
    assert len(_lines(files.consultations)) == 6
