"""``begriffe.json`` (Punkt 49): die Begriffe je Wahlbezirk liegen daneben, nicht in der Seite.

Die 41 Listen waren mit 334 KB der größte Posten der Seite und standen dort in zugeklappten
``<details>``. Jetzt lädt ``sections/50-begriffe.js`` sie beim ersten Aufklappen, und die Datei
steht wie ``dokumente.json`` mit Zeilenzahl, Größe und SHA-256 unter „Downloads".
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import replace

import deal
import pytest

from georep.layout import Layout
from georep.report.build import TERMS_NAME
from georep.report.model import ReportModel
from georep.report.terms import pairs, terms_payload

NOW = dt.datetime(2026, 10, 13, 8, 0, tzinfo=dt.UTC)


def test_the_payload_has_one_list_per_district_sorted_by_documents(mini_model: ReportModel) -> None:
    payload = terms_payload(mini_model.districts, version="9.9.9", generated_at=NOW)
    assert payload["version"] == "9.9.9" and payload["generated_at"] == NOW.isoformat()
    assert payload["fields"] == ["begriff", "dokumente"]
    found = payload["districts"]
    assert isinstance(found, dict)
    assert set(found) == {str(d.id) for d in mini_model.districts}
    for district in mini_model.districts:
        entries = found[str(district.id)]
        assert entries == [[t.term, t.hits] for t in district.terms]
        assert [e[1] for e in entries] == sorted((e[1] for e in entries), reverse=True)
        assert all(e[1] > 0 for e in entries)  # nur Begriffe mit Treffer
    assert pairs(mini_model.districts) == sum(len(v) for v in found.values())


def test_a_district_twice_breaks_the_contract(mini_model: ReportModel) -> None:
    twice = (*mini_model.districts, mini_model.districts[0])
    with pytest.raises(deal.PreContractError):
        terms_payload(twice, version="1", generated_at=NOW)


def test_an_unsorted_list_breaks_the_contract(mini_model: ReportModel) -> None:
    first = mini_model.districts[0]
    assert len(first.terms) > 1
    wrong = replace(first, terms=tuple(reversed(first.terms)))
    with pytest.raises(deal.PostContractError):
        terms_payload((wrong,), version="1", generated_at=NOW)


def test_the_file_is_written_with_the_hidden_terms_left_out(mini_run: Layout) -> None:
    payload = json.loads((mini_run.site_data / TERMS_NAME).read_text(encoding="utf-8"))
    terms = {term for entries in payload["districts"].values() for term, _ in entries}
    assert terms  # die Mini-Fixture hat Treffer
    assert "schulweg" not in terms  # hide_in_display, wie im HTML vorher
    assert (mini_run.site_data / TERMS_NAME).read_text(encoding="utf-8").count("\n") == 0


def test_the_page_names_the_file_and_loads_it_on_demand(mini_page: str, mini_run: Layout) -> None:
    section = re.search(r'<section id="begriffe">.*?</section>', mini_page, re.S)
    assert section is not None
    body = section.group(0)
    # Die Listen stehen nicht mehr im HTML, nur ihre Zahl in der Zusammenfassung
    assert '<ol class="terms">' not in body
    assert body.count("<details data-terms=") == 3  # drei Wahlbezirke der Fixture
    assert "Begriffe mit Treffer" in body and "Wird beim Aufklappen geladen." in body
    assert "<noscript>" in body and TERMS_NAME in body
    # und die Datei steht wie jede andere unter „Downloads", mit Prüfsumme
    assert f'href="data/{TERMS_NAME}"' in mini_page
    from georep.io import digest

    assert digest(mini_run.site_data / TERMS_NAME) in mini_page


def test_the_script_asks_the_frame_for_the_file_and_for_the_offline_note(mini_page: str) -> None:
    """Eine Datei, ein Versprechen, ein Satz: das Skript des Abschnitts bringt keinen zweiten mit."""
    assert "window.georep.loadJson(FILE)" in mini_page
    assert 'window.georep.offlineNote("Die Begriffsliste", FILE)' in mini_page
    assert 'offlineNote("Die Dokumentliste", DOCUMENTS)' in mini_page  # derselbe Satz im Dialog
    # Der Satz hängt seit dem Review vom 2026-10-13 am Protokoll; seine beiden Zweige prüft
    # tests/unit/test_report_js_offline.py mit node. Hier zählt nur, dass es einen gibt.
    note = re.search(r"function offlineNote\(what, path\) \{(.*?)\n  \}", mini_page, re.S)
    assert note is not None and "Dateisystem" in note.group(1)
    # Ein Zuhörer am Dokument, damit nachgeladene Begriffe ohne weitere Verdrahtung wirken
    assert 'closest("button.term")' in mini_page
