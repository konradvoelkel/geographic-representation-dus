"""Karte und Streudiagramm: parsebares SVG, eine Fläche je Bezirk, Klassen und Legende."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import deal
import pytest
from syrupy.assertion import SnapshotAssertion

from georep.analysis.regression import RegressionResult
from georep.geo import read_precincts
from georep.layout import Layout
from georep.report.charts import (
    Classification,
    choropleth,
    classify,
    legend,
    nice_ticks,
    project_pois,
    rate_label,
    scatter,
    turnout_label,
)
from georep.report.geometry import bounds_of, district_shapes, fit
from georep.report.model import (
    NARROW_NBSP,
    DistrictRow,
    RegressionPair,
    ReportModel,
    TermRow,
    build_report_model,
)
from georep.settings import Settings

NS = "{http://www.w3.org/2000/svg}"


def pois_of(svg: str) -> int:
    return svg.count("<circle cx=")


@pytest.fixture(scope="module")
def model(mini_run: Layout, default_settings: Settings) -> ReportModel:
    import datetime as dt

    return build_report_model(
        mini_run, default_settings, now=dt.datetime(2026, 10, 11, tzinfo=dt.UTC)
    )


@pytest.fixture(scope="module")
def map_svg(model: ReportModel, mini_run: Layout, default_settings: Settings) -> str:
    precincts = read_precincts(
        mini_run.districts_geojson, default_settings.columns, default_settings.geo.working_crs
    )
    shapes = district_shapes(precincts)
    projection = fit(bounds_of(shapes), 600.0)
    rate = classify({d.id: d.rate for d in model.districts})
    turnout = classify({d.id: d.turnout for d in model.districts})
    pois = project_pois([(340_000.0, 5_670_000.0, "Rheinturm <&>", 1)], projection)
    return choropleth(model.districts, shapes, projection, rate, turnout, pois)


def test_classify_uses_at_most_as_many_classes_as_distinct_values() -> None:
    three = classify({1: 0.3, 2: 0.1, 3: 0.2})
    assert three.count == 3 and len(three.boundaries) == 2
    assert three.classes == {1: 2, 2: 0, 3: 1}
    one = classify({1: 0.5, 2: 0.5})
    assert one.count == 1 and one.boundaries == () and one.classes == {1: 0, 2: 0}
    many = classify({i: float(i) for i in range(1, 42)})
    assert many.count == 5 and sorted(set(many.classes.values())) == [0, 1, 2, 3, 4]
    assert all(a <= b for a, b in zip(many.boundaries, many.boundaries[1:], strict=False))
    with pytest.raises(deal.PreContractError):
        classify({})


def test_legend_names_the_class_bounds() -> None:
    entries = legend(Classification((0.05, 0.07), {}, 3), rate_label)
    assert [e.label for e in entries] == ["unter 0,050", "0,050 bis unter 0,070", "ab 0,070"]
    assert [e.klass for e in entries] == [0, 1, 2]
    assert legend(Classification((), {}, 1), turnout_label) == (
        legend(Classification((), {}, 1), rate_label)
    )
    assert legend(Classification((0.5,), {}, 2), turnout_label)[1].label == f"ab 50,0{NARROW_NBSP}%"


def test_nice_ticks_examples() -> None:
    assert nice_ticks(0.026, 0.163) == pytest.approx((0.0, 0.05, 0.1, 0.15, 0.2))
    assert nice_ticks(35.6, 66.9) == pytest.approx((30.0, 40.0, 50.0, 60.0, 70.0))
    assert nice_ticks(0.0, 1.0, 3) == pytest.approx((0.0, 0.5, 1.0))
    with pytest.raises(deal.PreContractError):
        nice_ticks(1.0, 1.0)


def test_map_has_one_path_per_district_and_parses(map_svg: str, model: ReportModel) -> None:
    root = ET.fromstring(map_svg)
    paths = root.findall(f".//{NS}path")
    assert len(paths) == len(model.districts) == 3
    assert [p.get("data-id") for p in paths] == ["1", "10", "38"]
    for path in paths:
        assert path.get("class", "").startswith("district q")
        assert path.get("data-class-rate") in {"0", "1", "2"}
        assert path.get("data-class-turnout") in {"0", "1", "2"}
        assert path.get("d", "").startswith("M") and path.get("tabindex") == "0"
        assert path.find(f"{NS}title") is not None
    width, height = (float(v) for v in root.get("viewBox", "").split()[2:])
    assert width == 600.0 and height > 0
    circles = root.findall(f".//{NS}g[@class='pois']/{NS}circle")
    assert len(circles) == 1 and circles[0].get("data-name") == "Rheinturm <&>"
    assert circles[0].get("data-district") == "1"
    title = circles[0].find(f"{NS}title")
    assert title is not None and title.text == "Rheinturm <&> (Wahlbezirk 1)"
    assert isinstance(pois_of(map_svg), int)
    assert [t.text for t in root.findall(f".//{NS}g[@class='map-labels']/{NS}text")] == [
        "1",
        "10",
        "38",
    ]


def test_map_escapes_names_and_terms() -> None:
    row = DistrictRow(
        7,
        '"<b>" & Co',
        1,
        2,
        1,
        0.5,
        0.5,
        1,
        0,
        (TermRow("<i>&", 1, (7,)),),
        (TermRow("<i>&", 1, (7,)),),
    )
    from shapely.geometry import box

    shapes = {7: box(0, 0, 10, 10)}
    projection = fit(bounds_of(shapes), 100.0)
    svg = choropleth([row], shapes, projection, classify({7: 0.5}), classify({7: 0.5}))
    root = ET.fromstring(svg)
    path = root.find(f".//{NS}path")
    assert (
        path is not None
        and path.get("data-name") == '"<b>" & Co'
        and path.get("data-terms") == "<i>&"
    )
    assert "<b>" not in svg.replace("&lt;b&gt;", "")


def test_scatter_has_a_point_per_district_and_both_lines(model: ReportModel) -> None:
    pair = RegressionPair(
        all=RegressionResult(3, 60.0, 49.0, 0.2, 0.3, 1.0),
        excluded=(1, 10),
        without=RegressionResult(3, 200.0, 40.0, 0.3, 0.03, 1.0),
    )
    root = ET.fromstring(scatter(model.districts, pair))
    points = root.findall(f".//{NS}g[@class='point']")
    assert [p.get("data-id") for p in points] == ["1", "10", "38"]
    for point in points:
        hit, dot = point.findall(f"{NS}circle")
        assert float(hit.get("r", "0")) >= 12 and float(dot.get("r", "0")) == 4
        assert point.find(f"{NS}title") is not None and point.find(f"{NS}text") is not None
    fits = root.findall(f".//{NS}line[@class='fit fit-all']") + root.findall(
        f".//{NS}line[@class='fit fit-without']"
    )
    assert len(fits) == 2
    only_all = ET.fromstring(scatter(model.districts, model.regression))
    assert len(only_all.findall(f".//{NS}g[@class='fits']/{NS}line")) == 1
    assert root.findall(f".//{NS}g[@class='ticks']/{NS}text")


def test_scatter_survives_identical_values() -> None:
    rows = [DistrictRow(i, f"B{i}", 1, 10, 5, 0.5, 0.1, 1, 0, (), ()) for i in (1, 2, 3)]
    pair = RegressionPair(RegressionResult(3, 0.0, 50.0, 0.0, 1.0, 0.0), (1, 10), None)
    assert ET.fromstring(scatter(rows, pair)).findall(f".//{NS}g[@class='point']")


def test_legend_of_the_mini_fixture_is_stable(
    model: ReportModel, snapshot: SnapshotAssertion
) -> None:
    rate = legend(classify({d.id: d.rate for d in model.districts}), rate_label)
    turnout = legend(classify({d.id: d.turnout for d in model.districts}), turnout_label)
    assert [(e.klass, e.label) for e in rate + turnout] == snapshot
