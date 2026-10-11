"""Die Seite kennt keine Stadt, sie liest sie (Option 01, Stufe D).

Drei Prüfungen: der Code enthält kein Stadtwort mehr (``grep`` als Test), eine erfundene Stadt
rendert ohne Düsseldorf, und ``summary.json`` trägt dieselben Zahlen wie die Kacheln.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
from dataclasses import replace
from pathlib import Path

import pytest

from georep.layout import Layout
from georep.report.model import ReportModel, build_report_model, summary_payload
from georep.report.render import ALLOWED_LINKS, Visuals, model_links, render_report
from georep.report.tables import party_columns
from georep.settings import City, ReportSource, Settings
from tests.conftest import REPO

CITY_WORDS = ("Düsseldorf", "duesseldorf", "Düsseldorfer", "Q1718", "0015", "betrifft")
PROFILES = REPO / "src" / "georep" / "profiles"
PACKAGE = REPO / "src" / "georep"
# defaults.toml nennt den Slug des Standardprofils (default_profile) und verweist in Kommentaren
# auf die Profildateien; beides muss es dürfen, sonst wüsste `georep` ohne --profile nichts.
DEFAULTS = PACKAGE / "defaults.toml"


def _string_constants(path: Path) -> list[str]:
    """Alle Zeichenketten eines Moduls außer den Docstrings.

    Prosa darf die Stadt der Arbeit als Beispiel nennen; ein Wert darf es nicht. Was zählt, ist
    also nicht das Wort im Text, sondern das Wort in einer Konstante (Option 10).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node not in docstrings
    ]


def test_no_city_value_in_the_code() -> None:
    """Option 10: kein Stadtwert im Code; jeder steht in ``profiles/<slug>.toml``."""
    found: dict[str, list[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        hits = sorted(
            {word for text in _string_constants(path) for word in CITY_WORDS if word in text}
        )
        if hits:
            found[str(path.relative_to(REPO))] = hits
    assert found == {}, f"Stadtwerte im Code: {found}"


def test_no_city_word_in_the_templates() -> None:
    """Die Seite spricht von der Stadt des Profils, nie von einer bestimmten."""
    found: dict[str, list[str]] = {}
    for pattern in ("*.j2", "*.css", "*.js"):
        for path in sorted((PACKAGE / "report" / "templates").rglob(pattern)):
            text = path.read_text(encoding="utf-8")
            hits = sorted({word for word in CITY_WORDS if word in text})
            if hits:
                found[str(path.relative_to(REPO))] = hits
    assert found == {}, f"Stadtwörter in der Vorlage: {found}"


def test_only_the_selector_names_a_city_in_the_defaults() -> None:
    lines = [
        line
        for line in DEFAULTS.read_text(encoding="utf-8").splitlines()
        if any(word in line for word in CITY_WORDS)
    ]
    assert lines, "defaults.toml muss das Standardprofil nennen"
    assert all(
        line.startswith("default_profile") or line.lstrip().startswith("#") or "#" in line
        for line in lines
    ), lines


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
    mini_model: ReportModel, mini_visuals: Visuals
) -> None:
    other = replace(
        mini_model, city=OTHERLAND, sources=(SOURCE,), marker="gegenstand", notes=(), derived=None
    )
    page = render_report(other, mini_visuals)
    assert "Anderstädter Ratsdokumenten" in page and "Stadt Anderstadt" in page
    assert not any(word in page for word in ("Düsseldorf", "Düsseldorfer"))
    assert "gegenstand" in page and "betrifft" not in page


def test_the_allowlist_is_built_from_the_model(mini_model: ReportModel) -> None:
    allowed = ALLOWED_LINKS | model_links(mini_model)
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
    figures = payload["figures"]
    regression = payload["regression"]
    assert isinstance(figures, dict) and isinstance(regression, dict)
    assert figures["rate_median"] == pytest.approx(model.figures.rate_median)
    assert figures["documents"] == model.figures.documents
    assert regression["all"]["r"] == pytest.approx(model.regression.all.r)
    assert json.loads(json.dumps(payload)) == payload  # JSON-tauglich, ohne Umwege


def test_summary_is_a_download_and_the_schema_describes_it(mini_run: Layout) -> None:
    schema = json.loads((mini_run.site_data / "schema.json").read_text(encoding="utf-8"))
    assert "figures.districts" in schema["summary"]
    assert "data/summary.json" in mini_run.site_index.read_text(encoding="utf-8")


def test_the_report_step_links_no_other_city(mini_run: Layout, mini_page: str) -> None:
    """Der Schritt ``report`` weiß nicht, welche Stadtseiten es gibt; ``publish`` weiß es.

    Stünde die Zeile schon hier, trüge die veröffentlichte Seite tote Links, solange das Paket
    der zweiten Stadt fehlt (Review 2026-10-12).
    """
    assert "Weitere Städte" not in mini_page
    assert "vergleich.html" not in mini_page and "moenchengladbach/" not in mini_page
    # Die Stelle, die ``georep publish`` füllt (Stufe F); hier steht nur die Marke
    assert mini_page.count("<!--georep:weitere-staedte-->") == 1
