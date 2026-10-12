"""Rendering der Berichtsseite auf der Mini-Fixture: parsebar, vollständig, ohne Fremdressourcen."""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import deal
import pytest
from syrupy.assertion import SnapshotAssertion

from georep.geo import read_precincts
from georep.layout import Layout
from georep.report.charts import (
    choropleth,
    classify,
    legend,
    rate_label,
    scatter,
    turnout_label,
)
from georep.report.geometry import SIMPLIFY_M, bounds_of, district_shapes, fit
from georep.report.model import Download, ReportModel, build_report_model
from georep.report.render import Visuals, external_links, kib, render_map, render_report
from georep.report.search import SearchEntry, search_payload
from georep.settings import Settings

DOWNLOADS = (
    Download(
        "wahlbezirke_auswertung.parquet", "Parquet", 3, 12345, "a" * 64, "Auswertung je Bezirk"
    ),
    Download("wahlbezirke.geojson", "GeoJSON", 3, 2345, "b" * 64, "Flächen der Wahlbezirke"),
    Download("schema.json", "JSON", None, 345, "c" * 64, "Spaltenschema"),
)


class Counter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: dict[str, int] = {}
        self.errors = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags[tag] = self.tags.get(tag, 0) + 1


@pytest.fixture(scope="module")
def model(mini_run: Layout, default_settings: Settings) -> ReportModel:
    return build_report_model(
        mini_run,
        default_settings,
        now=dt.datetime(2026, 10, 11, 18, 30, tzinfo=dt.UTC),
        commit="abc1234",
        downloads=DOWNLOADS,
    )


@pytest.fixture(scope="module")
def visuals(model: ReportModel, mini_run: Layout, default_settings: Settings) -> Visuals:
    precincts = read_precincts(
        mini_run.districts_geojson, default_settings.columns, default_settings.geo.working_crs
    )
    shapes = district_shapes(precincts)
    projection = fit(bounds_of(shapes), 600.0)
    rate = classify({d.id: d.rate for d in model.districts})
    turnout = classify({d.id: d.turnout for d in model.districts})
    return Visuals(
        map_svg=choropleth(model.districts, shapes, projection, rate, turnout),
        scatter_svg=scatter(model.districts, model.regression),
        rate_legend=legend(rate, rate_label),
        turnout_legend=legend(turnout, turnout_label),
        simplify_m=SIMPLIFY_M,
        pois=0,
    )


@pytest.fixture(scope="module")
def page(model: ReportModel, visuals: Visuals) -> str:
    return render_report(model, visuals)


def test_page_parses_with_one_heading_and_german_language(page: str) -> None:
    parser = Counter()
    parser.feed(page)
    assert parser.tags["h1"] == 1 and parser.tags["svg"] == 2 and parser.tags["main"] == 1
    assert page.startswith("<!doctype html>") and '<html lang="de">' in page
    assert page.count('<p lang="en">') == 1
    assert "Erzeugt am 11.10.2026, 18:30 UTC mit georep" in page and "Commit abc1234" in page


def test_every_district_download_and_column_is_on_the_page(page: str, model: ReportModel) -> None:
    for district in model.districts:
        assert district.name in page and f'id="bezirk-{district.id}"' in page
    for download in DOWNLOADS:
        assert f'href="data/{download.name}"' in page and download.sha256 in page
    for column in model.columns:
        assert f"<code>{column.column}</code>" in page
    assert "schulweg" in page  # Fußnote zu versteckten Begriffen
    assert "ohne 1 und 10" not in page  # Mini: keine zweite Regression
    assert "<script src=" not in page and "<link " not in page and "@import" not in page


def test_only_allowed_links_point_outside(page: str) -> None:
    links = external_links(page)
    assert links and all(link.startswith("https://") for link in links)
    assert len(set(links)) >= 8


def test_data_is_escaped(model: ReportModel, visuals: Visuals) -> None:
    first = replace(model.districts[0], name='"<b>" & Co <a href="https://evil.example/">x</a>')
    tainted = replace(model, districts=(first, *model.districts[1:]))
    page = render_report(tainted, visuals)
    assert "<b>" not in page.replace("<b>", "", 0) or "&lt;b&gt;" in page
    assert 'href="https://evil.example/"' not in page and "evil.example" in page


def test_a_foreign_link_in_the_svg_breaks_the_contract(
    model: ReportModel, visuals: Visuals
) -> None:
    bad = replace(visuals, map_svg='<svg><a href="https://evil.example/"></a></svg>')
    with pytest.raises(deal.PostContractError):
        render_report(model, bad)


def test_download_table_is_stable(page: str, snapshot: SnapshotAssertion) -> None:
    match = re.search(r'<table id="downloads-table">.*?</table>', page, re.S)
    assert match is not None
    assert match.group(0) == snapshot


def test_kib_formats_kilobytes() -> None:
    assert kib(12345) == "12,3 KB" and kib(0) == "0,0 KB"


def test_map_page_escapes_script_end_and_allows_only_leaflet_and_osm(
    model: ReportModel, visuals: Visuals
) -> None:
    districts = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"wahlkreis_id": 1, "name": "x</script><b>", "klasse": 0},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[6.7, 51.2], [6.8, 51.2], [6.8, 51.3], [6.7, 51.2]]],
                },
            }
        ],
    }
    places = {"type": "FeatureCollection", "features": []}
    page = render_map(model, districts, places, visuals.rate_legend)
    assert "</script><b>" not in page and "\\u003c/script>\\u003cb>" in page
    assert "<!--" not in page.split('type="application/json"', 1)[1].split("</script>", 1)[0]
    assert set(external_links(page)) == {
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
        "https://www.openstreetmap.org/copyright",
    }
    assert page.count("<script") == 4 and "tile.openstreetmap.org" in page


def test_sections_render_in_numeric_order(page: str) -> None:
    from georep.report.render import sections

    parts = sections()
    numbers = [s.number for s in parts]
    assert numbers == sorted(numbers) and len(set(numbers)) == len(numbers)
    order = [s.name for s in parts]
    # Die vorhandenen Abschnitte in ihrer Reihenfolge; neue Optionen schieben sich dazwischen
    # (docs/plans/00-synergien.md, Paragraf 5.1), darum relativ geprueft, nicht als Praefix.
    fixed = [
        "kernzahlen",
        "karte",
        "zusammenhang",
        "wahlbezirke",
        "begriffe",
        "methode",
        "downloads",
    ]
    assert [name for name in order if name in fixed] == fixed
    positions = [page.index(f'<section id="{s.name}">') for s in parts]
    assert positions == sorted(positions)
    assert page.count("<section ") == len(parts)
    assert "window.georep = { select: select, showDocuments: showDocuments" in page


def test_section_css_and_js_need_a_template_sibling(tmp_path: Path) -> None:
    from georep.errors import SchemaError
    from georep.report.render import sections

    (tmp_path / "15-suche.html.j2").write_text('<section id="suche"></section>\n', encoding="utf-8")
    (tmp_path / "15-suche.css").write_text(".suche {}\n", encoding="utf-8")
    (tmp_path / "15-suche.js").write_text("void 0;\n", encoding="utf-8")
    (tmp_path / "10-kernzahlen.html.j2").write_text("<section></section>\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("ignoriert\n", encoding="utf-8")
    parts = sections(tmp_path)
    assert [(s.number, s.name) for s in parts] == [(10, "kernzahlen"), (15, "suche")]
    assert parts[1].css.startswith(".suche") and parts[1].js.startswith("void")
    assert parts[0].css == "" and parts[0].template == "sections/10-kernzahlen.html.j2"
    (tmp_path / "99-fehlt.js").write_text("", encoding="utf-8")
    with pytest.raises(SchemaError, match="ohne Vorlage"):
        sections(tmp_path)
    (tmp_path / "99-fehlt.js").unlink()
    (tmp_path / "15-doppelt.html.j2").write_text("<section></section>\n", encoding="utf-8")
    with pytest.raises(deal.PostContractError):
        sections(tmp_path)


def test_extra_classes_become_data_attributes_for_the_switch(
    model: ReportModel, visuals: Visuals
) -> None:
    import re as _re

    assert 'data-class-rate="' in visuals.map_svg and "data-class-bodies" not in visuals.map_svg
    from shapely.geometry import box

    from georep.report.charts import Classification, choropleth
    from georep.report.geometry import bounds_of, fit

    shapes = {d.id: box(0, 0, 10, 10) for d in model.districts}
    projection = fit(bounds_of(shapes), 100.0)
    one = Classification((), {d.id: 0 for d in model.districts}, 1)
    svg = choropleth(
        model.districts, shapes, projection, one, one, extra_classes={"bodies": one, "rate": one}
    )
    assert len(_re.findall(r'data-class-bodies="0"', svg)) == len(model.districts)
    assert svg.count('data-class-rate="') == len(model.districts)


def _search_block(page: str) -> str:
    match = re.search(
        r'<script id="suche-daten" type="application/json">(.*?)</script>', page, re.S
    )
    assert match is not None
    return match.group(1)


def _search_json(page: str) -> object:
    """Der Block ist gültiges JSON, wie ``_json_for_script`` das ``<`` auch maskiert.

    ``json.loads`` löst beide Schreibweisen auf, das alte ``<\\/`` ebenso wie ``\\u003c``; der Test
    kennt die Maskierung darum nicht und bleibt richtig, wenn sie sich ändert.
    """
    return json.loads(_search_block(page))


def test_search_data_is_a_readable_json_block(page: str, model: ReportModel) -> None:
    assert _search_json(page) == json.loads(json.dumps(search_payload(model.search)))
    assert page.count("<script") == 3  # Basis-Skript, Abschnitts-Skripte, der JSON-Block


def test_a_term_that_would_end_the_script_is_escaped(model: ReportModel, visuals: Visuals) -> None:
    tainted = replace(model, search=(SearchEntry("x</script><b>", (1,), 0, "s"),))
    page = render_report(tainted, visuals)
    # Was zählt, ist nicht die Schreibweise der Maskierung, sondern dass im Block nichts steht,
    # was der HTML-Tokenizer für das Ende des Skripts halten kann; der Begriff kommt heil zurück.
    assert "</script" not in _search_block(page).lower()
    assert "</script><b>" not in page
    assert _search_json(page) == json.loads(json.dumps(search_payload(tainted.search)))


def test_the_search_field_is_a_combobox_with_a_label(page: str, model: ReportModel) -> None:
    assert '<section id="suche">' in page and "Straße oder Ort" in page
    assert 'role="combobox"' in page and 'aria-autocomplete="list"' in page
    assert 'aria-expanded="false"' in page and 'role="listbox"' in page
    for match in re.finditer(r'aria-controls="([^"]+)"', page):
        assert f'id="{match.group(1)}"' in page
    assert '<label for="suche-feld">' in page and 'id="suche-feld"' in page
    assert f"{len(model.search)}" in page  # „Durchsucht n Straßen, Orte und Wahlbezirke"
    assert 'role="option"' not in page  # die Liste füllt erst das JavaScript


def test_a_model_without_search_entries_has_no_search_section(
    model: ReportModel, visuals: Visuals
) -> None:
    page = render_report(replace(model, search=()), visuals)
    assert '<section id="suche">' not in page and 'id="suche-daten"' not in page
