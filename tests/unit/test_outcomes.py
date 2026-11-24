"""Vorhaben 26: die Beschlusslage je Dokument, an Beispielen (``georep.analysis.outcomes``).

Die Regel ist die vorab festgelegte (Messdokument ``docs/plans/26-beschluesse.md``, § 3.1): die
letzte Entscheidung in der Sache, sonst der letzte Stand, sonst ``ohne_ergebnis``. Die Beispiele
hier sind die aus § 6 des Bauplans und die Grenzfälle, an denen die Verbindung Antrag → Beratung →
Tagesordnungspunkt hängt (Punkt 70). Was für alle Eingaben gilt, prüft
``tests/property/test_outcomes_props.py``.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl
import pytest

from georep.analysis import outcomes as oc
from georep.errors import SchemaError
from georep.oparl import OparlAgendaItem, OparlConsultation, OparlMeeting
from georep.settings import load_settings

NOWHERE = Path("/nonexistent")
SETTINGS = load_settings(profile="duesseldorf", cwd=NOWHERE)
RESULTS = dict(SETTINGS.outcomes.results)
RULES = oc.ReviewRules.from_settings(SETTINGS.outcomes.review)
ORGS = {"gr/1": "RAT", "gr/2": "AUS", "gr/3": "BV1"}
BASE = "https://example.org/oparl"


def _step(
    doc: str,
    top: str | None,
    when: str | None,
    result: str | None,
    *,
    order: int | None = 1,
    body: str = "gr/1",
    consultation: str | None = None,
) -> dict[str, object]:
    return {
        "id": doc,
        "beratung": consultation or f"{doc}/b",
        "top": top,
        "organisationen": [body],
        "rolle": "Entscheidung",
        "sitzung": dt.datetime.fromisoformat(when) if when else None,
        "nummer": "Ö 1" if top else None,
        "ordnung": order if top else None,
        "result": result,
    }


def _agenda(*steps: dict[str, object]) -> pl.DataFrame:
    return pl.DataFrame(list(steps), schema=oc.AGENDA_SCHEMA).sort(
        oc.PROGRESS_ORDER, nulls_last=False
    )


def _base(*steps: dict[str, object], date: str = "2021-01-01") -> pl.DataFrame:
    docs = sorted({str(s["id"]) for s in steps} | {"d"})
    corpus = pl.DataFrame(
        {"id": docs, "date": [dt.date.fromisoformat(date)] * len(docs)},
        schema={"id": pl.String, "date": pl.Date},
    )
    verlauf = oc.progress(_agenda(*steps), ORGS, RESULTS)
    return oc.classify_outcomes(corpus, verlauf, RESULTS)


def _decide(*steps: dict[str, object]) -> tuple[str, str | None]:
    row = _base(*steps).filter(pl.col("id") == "d").row(0, named=True)
    return row["klasse"], row["entscheidung_top"]


# --- Die Regel an den Beispielen des Bauplans (§ 6) ------------------------------------------------


def test_adjourned_then_decided_is_decided() -> None:
    assert _decide(
        _step("d", "t1", "2021-02-01T17:00", "vertagt"),
        _step("d", "t2", "2021-03-01T17:00", "einstimmig beschlossen"),
    ) == ("beschlossen", "t2")


def test_referred_then_withdrawn_is_withdrawn() -> None:
    assert _decide(
        _step("d", "t1", "2021-02-01T17:00", "verwiesen", body="gr/1"),
        _step("d", "t2", "2021-03-01T17:00", "zurückgezogen", body="gr/2"),
    ) == ("zurueckgezogen", "t2")


def test_a_recommendation_is_replaced_by_the_later_decision() -> None:
    assert _decide(
        _step("d", "t1", "2021-02-01T17:00", "Empfehlung einstimmig beschlossen", body="gr/2"),
        _step("d", "t2", "2021-03-01T17:00", "mehrheitlich abgelehnt", body="gr/1"),
    ) == ("abgelehnt", "t2")


def test_a_later_notice_does_not_replace_a_decision() -> None:
    assert _decide(
        _step("d", "t1", "2021-02-01T17:00", "einstimmig beschlossen", body="gr/3"),
        _step("d", "t2", "2021-03-01T17:00", "zur Kenntnis genommen", body="gr/1"),
    ) == ("beschlossen", "t1")


def test_only_adjourned_is_adjourned() -> None:
    assert _decide(
        _step("d", "t1", "2021-02-01T17:00", "vertagt"),
        _step("d", "t2", "2021-03-01T17:00", "zurückgestellt"),
    ) == ("vertagt", "t2")


def test_items_without_an_entry_leave_no_result() -> None:
    assert _decide(
        _step("d", "t1", "2021-02-01T17:00", None), _step("d", "t2", "2021-03-01T17:00", None)
    ) == ("ohne_ergebnis", None)


def test_in_the_same_meeting_the_order_on_the_agenda_decides() -> None:
    same = "2021-02-01T17:00"
    assert _decide(
        _step("d", "t9", same, "mehrheitlich abgelehnt", order=7),
        _step("d", "t1", same, "abweichend beschlossen", order=3),
    ) == ("abgelehnt", "t9")


def test_a_later_meeting_on_the_same_day_decides() -> None:
    """Die Uhrzeit zählt, nicht nur der Tag: die Regel liest den Beginn der Sitzung."""
    assert _decide(
        _step("d", "t1", "2021-02-01T18:00", "zurückgezogen", order=1),
        _step("d", "t2", "2021-02-01T10:00", "einstimmig beschlossen", order=9),
    ) == ("zurueckgezogen", "t1")


def test_an_item_without_order_counts_as_order_zero() -> None:
    same = "2021-02-01T17:00"
    assert _decide(
        _step("d", "t2", same, "einstimmig beschlossen", order=None),
        _step("d", "t1", same, "mehrheitlich abgelehnt", order=0),
    ) == ("beschlossen", "t2")  # gleich auf, dann die ID des Punkts


def test_a_meeting_without_start_comes_first() -> None:
    assert _decide(
        _step("d", "t1", None, "mehrheitlich abgelehnt"),
        _step("d", "t2", "2021-02-01T17:00", "abweichend beschlossen"),
    ) == ("geaendert", "t2")


def test_a_document_without_consultation_has_no_result() -> None:
    frame = _base(_step("x", "t1", "2021-02-01T17:00", "vertagt"))
    row = frame.filter(pl.col("id") == "d").row(0, named=True)
    assert (row["klasse"], row["grob"], row["beratungen"], row["tage"]) == (
        "ohne_ergebnis",
        "ohne_ergebnis",
        0,
        None,
    )


# --- Spalten der Beschlusslage -------------------------------------------------------------------


def test_the_coarse_class_joins_decided_and_changed() -> None:
    frame = _base(
        _step("a", "t1", "2021-02-01T17:00", "einstimmig beschlossen"),
        _step("b", "t2", "2021-02-01T17:00", "abweichend beschlossen"),
        _step("c", "t3", "2021-02-01T17:00", "passieren lassen"),
        _step("d", "t4", "2021-02-01T17:00", "verwiesen"),
    )
    assert dict(frame.select("id", "grob").iter_rows()) == {
        "a": "angenommen",
        "b": "angenommen",
        "c": "ohne_sachbeschluss",
        "d": "offen",
    }


def test_days_count_from_the_document_to_the_meeting_and_never_backwards() -> None:
    later = _base(_step("d", "t1", "2021-01-15T17:00", "vertagt"), date="2021-01-01")
    assert later.row(0, named=True)["tage"] == 14
    earlier = _base(_step("d", "t1", "2020-12-15T17:00", "vertagt"), date="2021-01-01")
    row = earlier.row(0, named=True)
    assert row["tage"] is None and row["entscheidung_datum"] == dt.date(2020, 12, 15)


def test_every_consultation_counts_also_one_without_an_item() -> None:
    frame = _base(
        _step("d", "t1", "2021-02-01T17:00", "vertagt", consultation="b1"),
        _step("d", None, None, None, consultation="b2"),
    )
    assert frame.row(0, named=True)["beratungen"] == 2


def test_the_body_comes_from_the_profile_or_stays_a_key() -> None:
    agenda = _agenda(
        {**_step("a", "t1", None, None), "organisationen": ["gr/1"]},
        {**_step("b", "t2", None, None), "organisationen": ["gr/99"]},
        {**_step("c", "t3", None, None), "organisationen": ["gr/2", "gr/3"]},
        {**_step("d", "t4", None, None), "organisationen": []},
    )
    verlauf = oc.progress(agenda, ORGS, RESULTS)
    assert verlauf.get_column("gremium").to_list() == ["RAT", "gr/99", "AUS+BV1", None]


def test_the_stage_comes_from_the_vocabulary() -> None:
    verlauf = oc.progress(
        _agenda(
            _step("a", "t1", None, "zurückgewiesen"),
            _step("b", "t2", None, "beantwortet"),
            _step("c", "t3", None, None),
        ),
        ORGS,
        RESULTS,
    )
    assert verlauf.get_column("stufe").to_list() == ["sache", "stand", None]


def test_an_unknown_entry_stops_with_its_wording() -> None:
    """Ein neuer Wert des Servers soll auffallen, nicht still ``ohne_ergebnis`` werden (§ 3.2)."""
    agenda = _agenda(
        _step("a", "t1", None, "Siehe Niederschrift"),
        _step("b", "t2", None, "Siehe Niederschrift"),
        _step("c", "t3", None, "vertagt"),
    )
    with pytest.raises(oc.UnknownResultError, match=r"'Siehe Niederschrift' \(2×, etwa t1\)"):
        oc.progress(agenda, ORGS, RESULTS)


# --- Die Verbindung aus den OParl-Objekten (Punkt 70) ---------------------------------------------


def _meeting(key: str, start: str, *orgs: str) -> OparlMeeting:
    return OparlMeeting.model_validate(
        {"id": key, "start": start, "organization": [f"{BASE}/organizations/{o}" for o in orgs]}
    )


def _item(key: str, meeting: str, consultation: str | None, result: str | None) -> OparlAgendaItem:
    return OparlAgendaItem.model_validate(
        {"id": key, "meeting": meeting, "number": "Ö 3", "order": 4}
        | ({"consultation": consultation} if consultation else {})
        | ({"result": result} if result else {})
    )


def _consultation(
    key: str, paper: str, *, meeting: str | None = None, item: str | None = None, org: str = ""
) -> OparlConsultation:
    data: dict[str, object] = {"id": key, "paper": paper, "role": "Entscheidung"}
    if meeting:
        data["meeting"] = meeting
    if item:
        data["agendaItem"] = item
    if org:
        data["organization"] = [f"{BASE}/organizations/{org}"]
    return OparlConsultation.model_validate(data)


def test_an_adjourned_paper_finds_both_items() -> None:
    """Die Beratung nennt nur den späteren Punkt; der frühere nennt die Beratung (Punkt 70)."""
    meetings = {
        "m1": _meeting("m1", "2021-02-01T17:00:00+01:00", "gr/2"),
        "m2": _meeting("m2", "2021-03-01T17:00:00+01:00", "gr/2"),
    }
    items = {
        "i1": _item("i1", "m1", "c1", "vertagt"),
        "i2": _item("i2", "m2", "c1", "einstimmig beschlossen"),
    }
    agenda = oc.agenda_rows(meetings, items, [_consultation("c1", "p1", item="i2")], {"p1"})
    assert agenda.get_column("top").to_list() == ["i1", "i2"]
    assert agenda.get_column("organisationen").to_list() == [["gr/2"], ["gr/2"]]


def test_the_item_a_consultation_names_counts_even_if_it_names_another() -> None:
    meetings = {"m1": _meeting("m1", "2021-02-01T17:00:00+01:00", "gr/1")}
    items = {"i1": _item("i1", "m1", "c9", "zurückgezogen")}
    agenda = oc.agenda_rows(meetings, items, [_consultation("c1", "p1", item="i1")], {"p1"})
    assert agenda.select("beratung", "top", "result").rows() == [("c1", "i1", "zurückgezogen")]


def test_a_consultation_without_item_keeps_a_row_with_its_meeting() -> None:
    meetings = {"m1": _meeting("m1", "2021-02-01T17:00:00+01:00", "gr/3")}
    agenda = oc.agenda_rows(
        meetings, {}, [_consultation("c1", "p1", meeting="m1", org="gr/1")], {"p1"}
    )
    row = agenda.row(0, named=True)
    assert row["top"] is None and row["result"] is None and row["ordnung"] is None
    assert row["organisationen"] == ["gr/3"]  # die Sitzung vor der Beratung
    assert row["sitzung"] == dt.datetime(2021, 2, 1, 17, 0)


def test_without_meeting_the_body_of_the_consultation_counts() -> None:
    agenda = oc.agenda_rows({}, {}, [_consultation("c1", "p1", org="gr/1")], {"p1"})
    assert agenda.row(0, named=True)["organisationen"] == ["gr/1"]
    assert agenda.row(0, named=True)["sitzung"] is None


def test_the_start_is_the_local_time_of_the_server() -> None:
    """Sommer- und Winterzeit tragen verschiedene Versätze; gelesen wird die Uhrzeit der Sitzung."""
    meetings = {
        "m1": _meeting("m1", "2021-07-01T17:00:00+02:00", "gr/1"),
        "m2": _meeting("m2", "2021-12-01T17:00:00+01:00", "gr/1"),
    }
    items = {"i1": _item("i1", "m1", "c1", None), "i2": _item("i2", "m2", "c1", None)}
    agenda = oc.agenda_rows(meetings, items, [_consultation("c1", "p1")], {"p1"})
    assert agenda.get_column("sitzung").to_list() == [
        dt.datetime(2021, 7, 1, 17, 0),
        dt.datetime(2021, 12, 1, 17, 0),
    ]


def test_only_the_papers_of_the_corpus_are_read() -> None:
    agenda = oc.agenda_rows(
        {}, {}, [_consultation("c1", "p1"), _consultation("c2", "p2")], {"p2", "p3"}
    )
    assert agenda.get_column("id").to_list() == ["p2"]


def test_a_package_with_another_schema_is_refused() -> None:
    frame = _agenda(_step("d", "t1", None, None)).drop("rolle")
    with pytest.raises(SchemaError, match="Schema"):
        oc.check_agenda(frame, "paket.parquet")
    doubled = pl.concat([_agenda(_step("d", "t1", None, None))] * 2)
    with pytest.raises(SchemaError, match="mehrfach"):
        oc.check_agenda(doubled, "paket.parquet")


# --- Der beantragte Prüfauftrag (Rückfall 1: beschreibend) ---------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Codebuch, Frage auftrag: das Beispiel eines Prüfauftrags
        (
            "antrag: die verwaltung wird gebeten zu prüfen, ob an der einmündung ein zebrastreifen "
            "eingerichtet werden kann. begründung: die kinder",
            True,
        ),
        # das Beispiel eines Sachbeschlusses
        (
            "antrag: die bezirksvertretung bittet die verwaltung, am pilgerweg ein hinweisschild "
            "anzubringen. begründung: der weg",
            False,
        ),
        # eine Maßnahme neben einem Bericht ist kein Prüfauftrag
        (
            "antrag: die verwaltung wird beauftragt, einen beirat einzurichten und bis jahresende "
            "zu berichten. begründung: es",
            False,
        ),
        # eine Maßnahme unter dem Vorbehalt der Prüfung ist einer
        (
            "antrag: die verwaltung wird gebeten zu prüfen, ob eine ampel aufgestellt werden kann; "
            "wenn die prüfung positiv ausfällt, ist sie aufzustellen. begründung: es",
            True,
        ),
        # Mittel für eine Untersuchung sind eine Maßnahme
        (
            "antrag: für die untersuchung werden 20.000 euro im haushalt bereitgestellt. "
            "begründung: es",
            False,
        ),
        # ein Bericht allein
        ("antrag: die verwaltung berichtet über den sachstand der sanierung. begründung: es", True),
    ],
)
def test_the_examples_of_the_codebook(text: str, expected: bool) -> None:
    assert oc.review_only("Antrag", text, RULES) == (expected, "text")


def test_the_decision_text_ends_at_the_reasoning() -> None:
    segment, found = oc.decision_text(
        "betreff: radweg antrag: die stadt richtet einen radweg ein. begründung: prüfen", RULES
    )
    assert found and segment == " die stadt richtet einen radweg ein. "


def test_without_marker_the_beginning_is_read() -> None:
    assert oc.review_only("Antrag", "die verwaltung möge berichten.", RULES) == (True, "anfang")


def test_without_text_the_title_decides() -> None:
    assert oc.review_only("Prüfauftrag Radweg", "", RULES) == (True, "titel")
    assert oc.review_only("Radweg anlegen", None, RULES) == (False, "titel")


def test_a_question_is_not_a_measure() -> None:
    """Ein Satz ohne Prüfwort mit Fragezeichen legt nichts fest."""
    text = "antrag: wird der radweg eingerichtet? die verwaltung wird um einen bericht gebeten. "
    assert oc.review_only("Antrag", text, RULES) == (True, "text")


# --- Was an Vorhaben 14 hängt: mit einer Rollen-Fixture --------------------------------------------

REVIEW_ALL = pl.DataFrame(schema={"id": pl.String, "pruefauftrag": pl.Boolean})
NO_FOLLOWUPS = pl.DataFrame(schema={"id": pl.String, "folgevorlage": pl.String})
OUTCOME_RULES = oc.OutcomeRules.from_settings(SETTINGS.outcomes)


def _roles(**roles: str) -> pl.DataFrame:
    return pl.DataFrame({"id": list(roles), "rolle": list(roles.values())})


def _motions(n_done: int, n_other: int, *, body: str = "gr/3", year: int = 2015) -> pl.DataFrame:
    steps = [
        _step(f"e{i:02d}", f"te{i:02d}", f"{year}-03-01T17:00", "zur Kenntnis genommen", body=body)
        for i in range(n_done)
    ] + [
        _step(f"o{i:02d}", f"to{i:02d}", f"{year}-03-01T17:00", "einstimmig beschlossen", body=body)
        for i in range(n_other)
    ]
    return _base(*steps, date=f"{year}-01-01")


def test_a_practice_cell_needs_the_share_and_the_count() -> None:
    base = _motions(10, 15)  # 10 von 25 = 0,4: gerade eine Zelle
    roles = _roles(**dict.fromkeys(base.get_column("id").to_list(), "antrag"))
    done = oc.complete_outcomes(base, roles, REVIEW_ALL, NO_FOLLOWUPS, OUTCOME_RULES)
    flags = dict(done.select("id", "eintrag_tragfaehig").iter_rows())
    assert flags["e00"] is False and flags["o00"] is True
    assert flags["d"] is None  # ohne Ergebnis: nichts zu tragen
    few = _motions(9, 0)  # 100 %, aber nur neun
    roles = _roles(**dict.fromkeys(few.get_column("id").to_list(), "antrag"))
    done = oc.complete_outcomes(few, roles, REVIEW_ALL, NO_FOLLOWUPS, OUTCOME_RULES)
    assert done.filter(pl.col("klasse") == "erledigt").get_column("eintrag_tragfaehig").all()
    below = _motions(10, 16)  # 10 von 26 < 0,4
    roles = _roles(**dict.fromkeys(below.get_column("id").to_list(), "antrag"))
    done = oc.complete_outcomes(below, roles, REVIEW_ALL, NO_FOLLOWUPS, OUTCOME_RULES)
    assert done.get_column("eintrag_tragfaehig").drop_nulls().all()


def test_a_practice_cell_counts_only_motions_and_flags_only_them() -> None:
    base = _motions(10, 0)
    ids = base.get_column("id").to_list()
    # dieselben Einträge, aber Vorlagen: kein Antrag, keine Zelle, keine Markierung
    done = oc.complete_outcomes(
        base, _roles(**dict.fromkeys(ids, "vorlage")), REVIEW_ALL, NO_FOLLOWUPS, OUTCOME_RULES
    )
    assert done.get_column("eintrag_tragfaehig").null_count() == done.height


def test_the_review_column_stands_only_at_accepted_motions() -> None:
    base = _base(
        _step("a", "t1", "2021-02-01T17:00", "einstimmig beschlossen"),
        _step("b", "t2", "2021-02-01T17:00", "mehrheitlich abgelehnt"),
        _step("c", "t3", "2021-02-01T17:00", "abweichend beschlossen"),
    )
    roles = _roles(a="antrag", b="antrag", c="vorlage", d="antrag")
    review = pl.DataFrame({"id": ["a", "b", "c"], "pruefauftrag": [True, True, True]})
    done = oc.complete_outcomes(base, roles, review, NO_FOLLOWUPS, OUTCOME_RULES)
    assert dict(done.select("id", "pruefauftrag_beantragt").iter_rows()) == {
        "a": True,
        "b": None,
        "c": None,
        "d": None,
    }
    assert done.schema == pl.Schema(oc.OUTCOME_SCHEMA)


def test_the_first_followup_is_the_earliest_strong_edge_of_the_administration() -> None:
    edges = pl.DataFrame(
        {
            "von": ["v2", "v1", "q1", "v3", "v0"],
            "nach": ["a", "a", "a", "a", "b"],
            "stark": [True, True, True, False, True],
        }
    )
    roles = _roles(v0="vorlage", v1="information", v2="vorlage", v3="vorlage", q1="antrag")
    dates = pl.DataFrame(
        {
            "id": ["v0", "v1", "v2", "v3", "q1"],
            "date": [dt.date(2022, 1, d) for d in (1, 9, 3, 1, 1)],
        }
    )
    found = oc.first_followups(edges, roles, dates, OUTCOME_RULES.followup_roles)
    # v3 ist schwach, q1 ein Antrag: es bleibt v2 vor v1 (früher)
    assert found.rows() == [("a", "v2"), ("b", "v0")]


def test_the_followup_stands_only_at_motions() -> None:
    base = _base(_step("a", "t1", "2021-02-01T17:00", "einstimmig beschlossen"))
    roles = _roles(a="antrag", d="vorlage")
    followups = pl.DataFrame({"id": ["a", "d"], "folgevorlage": ["v1", "v2"]})
    done = oc.complete_outcomes(base, roles, REVIEW_ALL, followups, OUTCOME_RULES)
    assert dict(done.select("id", "folgevorlage").iter_rows()) == {"a": "v1", "d": None}


# --- Antragserfolg je Fraktion (explorativ) --------------------------------------------------------


def test_success_is_observed_against_the_practice_of_the_bodies() -> None:
    outcomes = pl.DataFrame(
        {
            "id": ["1", "2", "3", "4", "5", "6"],
            "rolle": ["antrag"] * 5 + ["vorlage"],
            "klasse": [
                "beschlossen",
                "abgelehnt",
                "geaendert",
                "abgelehnt",
                "erledigt",
                "beschlossen",
            ],
            "eintrag_tragfaehig": [True, True, True, True, False, None],
        }
    )
    cosponsors = pl.DataFrame(
        {"id": ["1", "2", "3", "4"], "fraktionen": [["A"], ["B"], ["A", "B"], []]},
        schema={"id": pl.String, "fraktionen": pl.List(pl.String)},
    )
    bodies = pl.DataFrame(
        {
            "id": ["1", "2", "3", "4", "5", "6"],
            "gremium": ["RAT", "RAT", "BV1", "BV1", "BV1", "RAT"],
            "gremium_art": [
                "rat",
                "rat",
                "bezirksvertretung",
                "bezirksvertretung",
                "bezirksvertretung",
                "rat",
            ],
        }
    )
    success = oc.motion_success(outcomes, cosponsors, bodies, "2020-2025")
    assert success.schema == pl.Schema(oc.SUCCESS_SCHEMA)
    rows = {(r["gremium_art"], r["fraktion"]): r for r in success.iter_rows(named=True)}
    # Rat: Quote 1/2; A hat 1 von 1 bei erwartet 0,5, B 0 von 1
    assert (rows[("rat", "A")]["n"], rows[("rat", "A")]["angenommen"]) == (1, 1)
    assert rows[("rat", "A")]["erwartet"] == pytest.approx(0.5)
    assert rows[("rat", "A")]["beob_erw"] == pytest.approx(2.0)
    assert rows[("rat", "B")]["beob_erw"] == pytest.approx(0.0)
    # BV1: Quote 1/2 aus Antrag 3 (A und B) und 4 (ohne Fraktion); 5 ist erledigt und zählt nicht
    assert rows[("bezirksvertretung", "B")]["erwartet"] == pytest.approx(0.5)
    assert set(rows) == {
        ("rat", "A"),
        ("rat", "B"),
        ("bezirksvertretung", "A"),
        ("bezirksvertretung", "B"),
    }
    assert success.get_column("periode").unique().to_list() == ["2020-2025"]


def test_the_period_key() -> None:
    assert oc.period_key(dt.date(2020, 9, 13), dt.date(2025, 9, 14)) == "2020-2025"
    assert oc.period_key(dt.date(2025, 9, 15), None) == "2025-"


def test_a_point_named_by_two_consultations_decides_the_same_in_any_order() -> None:
    """Review 2026-11-24, N3: die Beratung ist der letzte Schlüssel, nicht die Zeilenfolge.

    Nennen zwei Beratungen denselben Punkt einer Sitzung ohne Organisation, kommt das Gremium aus
    der Beratung; welche Zeile gilt, darf nicht an der Folge der Eingabe hängen.
    """
    rows = [
        {
            **_step("d", "t1", "2021-02-01T17:00", "vertagt", consultation="b1"),
            "organisationen": [],
        },
        {
            **_step("d", "t1", "2021-02-01T17:00", "vertagt", consultation="b2"),
            "organisationen": [],
        },
    ]
    rows[0]["organisationen"], rows[1]["organisationen"] = ["gr/1"], ["gr/2"]
    verlauf = oc.progress(_agenda(*rows), ORGS, RESULTS)
    forward = oc.decisions(verlauf, RESULTS)
    backward = oc.decisions(verlauf.reverse(), RESULTS)
    assert forward.equals(backward)
    assert forward.row(0, named=True)["entscheidung_gremium"] == "AUS"  # die Beratung b2


def test_an_empty_entry_is_no_entry() -> None:
    """Review 2026-11-24, N4: ``result = ""`` ist kein Eintrag, wie im Messskript (``if s.result``)."""
    meetings = {"m1": _meeting("m1", "2021-02-01T17:00:00+01:00", "gr/1")}
    items = {
        "i1": OparlAgendaItem.model_validate(
            {"id": "i1", "meeting": "m1", "consultation": "c1", "result": ""}
        )
    }
    agenda = oc.agenda_rows(meetings, items, [_consultation("c1", "p1")], {"p1"})
    assert agenda.get_column("result").to_list() == [None]
    verlauf = oc.progress(agenda, ORGS, RESULTS)
    assert verlauf.get_column("stufe").to_list() == [None]
