"""Vertrag mit dem OParl-Server: echte Antwort vom 2026-10-09, typisiert gelesen."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from georep.oparl import (
    Links,
    OparlFile,
    OparlOrganization,
    OparlPaper,
    OrganizationPage,
    Pagination,
    PaperPage,
    known_aliases,
)
from tests.conftest import REPO

FIXTURE = REPO / "tests" / "fixtures" / "oparl" / "papers_page.json"
ORGANIZATIONS = REPO / "tests" / "fixtures" / "oparl" / "organizations_page.json"


@pytest.fixture(scope="module")
def page() -> PaperPage:
    return PaperPage.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def test_page_structure(page: PaperPage) -> None:
    assert len(page.data) == 6
    assert page.pagination is not None and page.pagination.elements_per_page == 200
    assert page.links.next is not None and page.links.next.endswith("?page=2")
    assert page.links.self_ is not None


def test_papers_are_typed(page: PaperPage) -> None:
    for paper in page.data:
        assert paper.type == "https://schema.oparl.org/1.1/Paper"
        assert paper.id.startswith("http://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers/")
        assert isinstance(paper.date, dt.date)
        assert paper.created is not None and paper.created.tzinfo is not None
        assert paper.paper_type


def test_primary_file_prefers_main_file_then_first_auxiliary(page: PaperPage) -> None:
    with_main = [p for p in page.data if p.main_file is not None]
    without_main = [p for p in page.data if p.main_file is None]
    assert len(with_main) == 5 and len(without_main) == 1
    for paper in with_main:
        assert paper.primary_file is paper.main_file
        assert paper.download_url is not None and paper.download_url.endswith(".pdf")
    # Der echte Fall ohne mainFile hat eine auxiliaryFile: die Ersatzregel der Arbeit greift.
    orphan = without_main[0]
    assert orphan.auxiliary_file
    assert orphan.primary_file is orphan.auxiliary_file[0]
    assert orphan.download_url == orphan.auxiliary_file[0].download_url
    assert OparlPaper(id="x").download_url is None


def test_in_period_is_inclusive_and_false_without_date() -> None:
    paper = OparlPaper(id="x", date=dt.date(2025, 9, 14))
    assert paper.in_period(dt.date(2020, 9, 13), dt.date(2025, 9, 14))
    assert not paper.in_period(dt.date(2020, 9, 13), dt.date(2025, 9, 13))
    assert not OparlPaper(id="x").in_period(dt.date(2000, 1, 1), dt.date(2100, 1, 1))
    # Laufende Periode ohne Ende: alles ab dem Beginn zaehlt, davor nichts, ohne Datum nie
    assert paper.in_period(dt.date(2025, 9, 14), None)
    assert not paper.in_period(dt.date(2025, 9, 15), None)
    assert not OparlPaper(id="x").in_period(dt.date(2000, 1, 1), None)


def test_model_knows_every_key_the_server_sends() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert set(raw) == {"data", "pagination", "links"}
    assert set(raw["pagination"]) <= known_aliases(Pagination)
    assert set(raw["links"]) <= known_aliases(Links)
    paper_keys = {k for item in raw["data"] for k in item}
    file_keys = {
        k
        for item in raw["data"]
        for f in [item.get("mainFile"), *item.get("auxiliaryFile", [])]
        if f
        for k in f
    }
    assert paper_keys <= known_aliases(OparlPaper), paper_keys - known_aliases(OparlPaper)
    assert file_keys <= known_aliases(OparlFile), file_keys - known_aliases(OparlFile)


def test_unknown_keys_are_ignored_not_fatal() -> None:
    paper = OparlPaper.model_validate({"id": "x", "date": "2024-01-02", "neuesFeld": 1})
    assert paper.date == dt.date(2024, 1, 2)


def test_fixture_file_is_small_enough_to_read_in_a_review() -> None:
    assert Path(FIXTURE).stat().st_size < 40_000
    assert Path(ORGANIZATIONS).stat().st_size < 40_000


# --- Option 04: Urheberfelder und Organisationen -------------------------------------------------


def test_the_server_sends_no_originator_fields_yet(page: PaperPage) -> None:
    """Befund vom 2026-10-09: keines der sechs Paper trägt originatorPerson, originatorOrganization
    oder underDirectionOf, auch nicht der Antrag FDP (vo/114086). Die Felder sind leer, nicht None,
    und ``consultation_organizations`` liefert das beratende Gremium aus ``consultation``."""
    assert all(not paper.has_originator for paper in page.data)
    assert all(paper.originator_organization == () for paper in page.data)
    fdp = next(p for p in page.data if p.id.endswith("/vo/114086"))
    assert fdp.paper_type == "Antrag FDP" and fdp.originator_person == ()
    assert fdp.consultation_organizations == (
        "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/organizations/gr/25",
    )


def test_originator_fields_are_tuples_of_urls_and_survive_a_roundtrip() -> None:
    paper = OparlPaper.model_validate(
        {
            "id": "x",
            "originatorPerson": ["https://ris.invalid/persons/1"],
            "originatorOrganization": ["https://ris.invalid/organizations/gr/49"],
            "underDirectionOf": ["https://ris.invalid/organizations/amt/66"],
            "consultation": [
                {"organization": ["https://ris.invalid/organizations/gr/25"], "role": "x"},
                {"organization": "https://ris.invalid/organizations/gr/6"},
                {"organization": ["https://ris.invalid/organizations/gr/25"]},
                {"role": "ohne Organisation"},
            ],
        }
    )
    assert paper.has_originator
    assert paper.originator_organization == ("https://ris.invalid/organizations/gr/49",)
    assert paper.under_direction_of == ("https://ris.invalid/organizations/amt/66",)
    assert paper.consultation_organizations == (
        "https://ris.invalid/organizations/gr/25",
        "https://ris.invalid/organizations/gr/6",
    )
    again = OparlPaper.model_validate_json(paper.model_dump_json(by_alias=True))
    assert again == paper  # consultation bleibt eine Liste; hashbar wird erst PaperRecord
    assert set(OparlPaper.model_dump(paper, by_alias=True)) >= {
        "originatorPerson",
        "originatorOrganization",
        "underDirectionOf",
    }


@pytest.fixture(scope="module")
def organizations() -> OrganizationPage:
    return OrganizationPage.model_validate_json(ORGANIZATIONS.read_text(encoding="utf-8"))


def test_organizations_page_is_typed(organizations: OrganizationPage) -> None:
    assert len(organizations.data) == 12 and organizations.links.next is None
    assert organizations.pagination is not None and organizations.pagination.current_page == 1
    by_short = {o.short_name: o for o in organizations.data}
    fdp = by_short["FDP"]
    assert fdp.id.endswith("/organizations/gr/49") and fdp.name == "FDP-Ratsfraktion"
    assert fdp.classification == "Fraktion" and fdp.organization_type is None
    assert fdp.start_date == dt.date(1998, 1, 1) and fdp.end_date is None
    assert len(fdp.membership) > 10 and all(m.startswith("http") for m in fdp.membership)
    assert fdp.active_on(dt.date(2023, 1, 1)) and not fdp.active_on(dt.date(1997, 12, 31))
    assert not fdp.deleted and fdp.modified is not None
    partei = by_short["Die PARTEI"]
    assert partei.classification is None and partei.end_date == dt.date(2025, 10, 31)
    assert not partei.active_on(dt.date(2025, 11, 1)) and partei.active_on(dt.date(2025, 10, 31))
    assert {o.classification for o in organizations.data} == {
        "Fraktion",
        "Bezirk",
        "Ausschuss",
        "Gremium",
        None,
    }


def test_model_knows_every_key_the_server_sends_for_organizations() -> None:
    raw = json.loads(ORGANIZATIONS.read_text(encoding="utf-8"))
    assert set(raw) == {"data", "pagination", "links"}
    keys = {k for item in raw["data"] for k in item}
    assert keys <= known_aliases(OparlOrganization), keys - known_aliases(OparlOrganization)
    assert "organizationType" not in keys  # der Server kennt nur classification


def test_organization_without_dates_is_always_active() -> None:
    org = OparlOrganization(id="x")
    assert org.active_on(dt.date(1900, 1, 1)) and org.membership == ()
