"""Die Seite kennt keine Stadt, sie liest sie (Option 01, Stufe D).

Drei Prüfungen: der Code enthält kein Stadtwort mehr (``grep`` als Test), eine erfundene Stadt
rendert ohne Düsseldorf, und ``summary.json`` trägt dieselben Zahlen wie die Kacheln.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import replace
from pathlib import Path

import pytest

from georep.layout import Layout
from georep.report.model import ReportModel, build_report_model, summary_payload
from georep.report.render import Links, Visuals, allowed_links, page_links, render_report
from georep.report.tables import party_columns
from georep.settings import City, ReportSource, Settings, load_settings
from tests.conftest import REPO

CITY_WORDS = ("Düsseldorf", "duesseldorf", "Düsseldorfer", "Q1718", "0015", "betrifft")
PROFILES = REPO / "src" / "georep" / "profiles"


def _sources() -> list[Path]:
    root = REPO / "src" / "georep"
    return [
        path
        for pattern in ("*.py", "*.j2", "*.css", "*.js", "*.toml")
        for path in root.rglob(pattern)
        if PROFILES not in path.parents
    ]


def test_no_city_word_outside_the_profiles() -> None:
    """Option 10: der Code kennt keine Stadt; jedes Stadtwort steht in ``profiles/<slug>.toml``."""
    found: dict[str, list[str]] = {}
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        hits = sorted({word for word in CITY_WORDS if word in text})
        if hits:
            found[str(path.relative_to(REPO))] = hits
    assert found == {}, f"Stadtwörter im Code: {found}"


def test_the_profile_is_where_the_city_words_live() -> None:
    text = (PROFILES / "duesseldorf.toml").read_text(encoding="utf-8")
    assert all(word in text for word in ("Düsseldorf", "Q1718", "0015", "betrifft"))


# --- Vorlage mit einer erfundenen Stadt -------------------------------------------------------

OTHERLAND = City(
    slug="anderstadt",
    name="Anderstadt",
    genitive="Anderstadts",
    adjective="Anderstädter",
    ags="05999000",
    publisher="Stadt Anderstadt",
    council="Rat",
    election="Ratswahl 2025",
)
SOURCE = ReportSource(
    name="Ratswahl 2025 je Stimmbezirk",
    publisher="Stadt Anderstadt",
    url="https://portal.anderstadt.invalid/",
    license="Datenlizenz Deutschland – Zero – Version 2.0",
    license_url="https://www.govdata.de/dl-de/zero-2-0",
    checked=dt.date(2026, 10, 12),
)


def test_the_duesseldorf_page_still_speaks_of_duesseldorf(mini_page: str) -> None:
    page = mini_page
    assert "Düsseldorfer Ratsdokumenten" in page
    assert "Landeshauptstadt Düsseldorf" in page
    assert "Datenlizenz Deutschland Namensnennung 2.0" in page
    assert "betrifft" in page  # der Marker steht in „Methode und Grenzen"


def test_another_city_renders_without_a_duesseldorf_word(
    mini_model: ReportModel, mini_visuals: Visuals, default_settings: Settings
) -> None:
    other = replace(mini_model, city=OTHERLAND, sources=(SOURCE,), marker="gegenstand")
    links: Links = page_links(default_settings)
    allowed = links.allowed | {SOURCE.url, SOURCE.license_url}
    page = render_report(other, mini_visuals, replace(links, allowed=allowed))
    assert "Anderstädter Ratsdokumenten" in page and "Stadt Anderstadt" in page
    assert not any(word in page for word in ("Düsseldorf", "Düsseldorfer"))
    assert "gegenstand" in page and "betrifft" not in page


def test_the_allowlist_is_built_from_the_profile(default_settings: Settings) -> None:
    allowed = allowed_links(default_settings)
    assert "https://opendata.duesseldorf.de/" in allowed
    assert "https://www.govdata.de/dl-de/by-2-0" in allowed
    assert "https://github.com/konradvoelkel/geographic-representation-dus" in allowed
    assert "https://example.invalid/" not in allowed


def test_party_columns_come_from_the_profile(default_settings: Settings) -> None:
    docs = party_columns(default_settings)
    assert docs["GRUENE_Stimmen"] == ("Stimmen für Bündnis 90/Die Grünen", "Stimmen")
    assert docs["CDU_anteil"][1] == "Anteil 0 bis 1"
    assert len(docs) == 12  # sechs Parteien, Stimmen und Anteil


# --- summary.json ------------------------------------------------------------------------------


def test_summary_json_carries_the_numbers_of_the_tiles(mini_run: Layout) -> None:
    payload = json.loads(mini_run.site_summary.read_text(encoding="utf-8"))
    assert payload["city"]["slug"] == "duesseldorf" and payload["city"]["name"] == "Düsseldorf"
    assert payload["figures"]["districts"] == 3
    assert payload["regression"]["all"]["n"] == 3
    assert payload["stand"]["election"] == "2025-09-14"
    assert payload["version"] and payload["generated_at"]


def test_summary_payload_matches_the_model(mini_run: Layout, default_settings: Settings) -> None:
    model = build_report_model(
        mini_run, default_settings, now=dt.datetime(2026, 10, 12, 9, 0, tzinfo=dt.UTC)
    )
    payload = summary_payload(model)
    assert payload["figures"]["rate_median"] == pytest.approx(model.figures.rate_median)
    assert payload["figures"]["documents"] == model.figures.documents
    assert payload["regression"]["all"]["r"] == pytest.approx(model.regression.all.r)
    assert json.loads(json.dumps(payload)) == payload  # JSON-tauglich, ohne Umwege


def test_summary_is_a_download_and_the_schema_describes_it(mini_run: Layout) -> None:
    schema = json.loads((mini_run.site_data / "schema.json").read_text(encoding="utf-8"))
    assert "figures.districts" in schema["summary"]
    assert "data/summary.json" in mini_run.site_index.read_text(encoding="utf-8")


def test_other_cities_are_a_line_in_the_header(mini_run: Layout, tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[publish]\ncities = ["duesseldorf", "moenchengladbach"]\n', encoding="utf-8"
    )
    settings = load_settings(cwd=tmp_path)
    model = build_report_model(
        mini_run, settings, now=dt.datetime(2026, 10, 12, 9, 0, tzinfo=dt.UTC)
    )
    assert [other.slug for other in model.other_cities] == ["moenchengladbach"]
    assert model.other_cities[0].href == "moenchengladbach/"
