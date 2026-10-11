"""Rendering der Berichtsseite auf der Mini-Fixture: parsebar, vollständig, ohne Fremdressourcen."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import replace
from html.parser import HTMLParser

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
from georep.report.render import Visuals, external_links, kib, render_report
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
