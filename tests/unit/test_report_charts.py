"""Karte und Streudiagramm: parsebares SVG, eine Fläche je Bezirk, Klassen und Legende."""

from __future__ import annotations

import datetime as dt
import math
import xml.etree.ElementTree as ET

import deal
import pytest
from shapely.geometry import box
from syrupy.assertion import SnapshotAssertion

from georep.analysis.regression import RegressionPair, RegressionResult
from georep.contracts import next_month
from georep.geo import read_canonical_precincts
from georep.layout import Layout
from georep.report.charts import (
    Classification,
    added_variable_plot,
    bars,
    choropleth,
    classify,
    classify_fixed,
    delta_label,
    delta_scatter,
    legend,
    nice_ticks,
    party_maps,
    per_term_label,
    percent_signed_label,
    points_label,
    project_pois,
    rate_label,
    ratio_label,
    scatter,
    turnout_label,
)
from georep.report.geometry import bounds_of, district_shapes, fit
from georep.report.model import (
    NARROW_NBSP,
    DistrictRow,
    MonthRow,
    PartyCell,
    PartyRow,
    PeriodRow,
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
    precincts = read_canonical_precincts(
        mini_run.precincts_geojson, default_settings.geo.working_crs
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


def test_fixed_classes_divide_at_the_given_boundaries() -> None:
    """Punkt 46: eine divergierende Variante bekommt feste Grenzen, keine Quantile."""
    bounds = (-0.25, -0.10, 0.10, 0.25)
    found = classify_fixed({1: -0.578, 2: -0.2, 3: 0.0, 4: 0.10, 5: 1.448}, bounds)
    assert found.count == 5 and found.boundaries == bounds
    # Die Grenze selbst gehört zur oberen Klasse (wie bei classify: [b_{i-1}, b_i))
    assert found.classes == {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}
    # Vier Bezirke unter dem Mittel und einer weit darüber: feste Grenzen sagen das, Quantile
    # verteilen dieselben Werte gleichmäßig auf fünf Klassen und verschweigen es
    skewed = {1: -0.5, 2: -0.4, 3: -0.3, 4: -0.2, 5: 1.4}
    assert classify_fixed(skewed, bounds).classes == {1: 0, 2: 0, 3: 0, 4: 1, 5: 4}
    assert classify(skewed).classes == {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}
    with pytest.raises(deal.PreContractError):
        classify_fixed({1: 0.0}, ())
    with pytest.raises(deal.PreContractError):
        classify_fixed({1: 0.0}, (0.2, 0.1))  # nicht aufsteigend
    # Dieselbe Endlichkeitsbedingung wie bei ``classify``: NaN landete sonst still in der
    # obersten Klasse, und eine unendliche Grenze machte die Legende unlesbar.
    for values, bounds in (
        ({1: math.nan}, (0.0,)),
        ({1: math.inf}, (0.0,)),
        ({1: 0.0}, (math.nan,)),
        ({1: 0.0}, (0.0, math.inf)),
        ({}, (0.0,)),
    ):
        with pytest.raises(deal.PreContractError):
            classify_fixed(values, bounds)


def test_the_signed_labels_carry_their_unit() -> None:
    assert percent_signed_label(-0.25) == f"-25{NARROW_NBSP}%"
    assert percent_signed_label(0.1) == f"+10{NARROW_NBSP}%"
    assert percent_signed_label(0.0) == f"0{NARROW_NBSP}%"
    assert points_label(-0.02) == "-2,0 pp"
    assert points_label(0.005) == "+0,5 pp"
    assert ratio_label(1.25) == "1,25×"
    assert per_term_label(4.5656) == "4,57"


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


def test_nice_ticks_refuses_a_span_that_overflows() -> None:
    """crosshair fand das am 2026-10-12, nachdem die Sitzung wieder durchlief (Befund 20).

    Beide Grenzen sind endlich, ihre Differenz ist es nicht: ``hi - lo`` läuft über, und
    ``math.floor(math.log10(inf))`` wirft einen ``OverflowError`` mitten aus der Funktion. Achsen
    dieser Größe sind ein Programmierfehler des Aufrufers, also gehört der Fall in die
    Vorbedingung und nicht in eine Fallunterscheidung im Körper.
    """
    with pytest.raises(deal.PreContractError):
        nice_ticks(-7.584017912700396e307, 1.4887146273078554e308, n=2)


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
    assert model.regression is not None
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


def test_axes_map_tick_ends_onto_the_plot_frame() -> None:
    from georep.report.charts import MARGIN, Axes

    axes = Axes.fit([0.03, 0.16], [36.0, 67.0], width=640.0, height=420.0)
    top, right, bottom, left = MARGIN
    assert axes.sx(axes.x0) == pytest.approx(left)
    assert axes.sx(axes.x1) == pytest.approx(640.0 - right)
    assert axes.sy(axes.y1) == pytest.approx(top)
    assert axes.sy(axes.y0) == pytest.approx(420.0 - bottom)
    grid = ET.fromstring(axes.grid())
    assert len(grid.findall("line")) == len(axes.x_ticks) + len(axes.y_ticks)
    ticks = ET.fromstring(axes.tick_labels())
    assert len(ticks.findall("text")) == len(axes.x_ticks) + len(axes.y_ticks)
    assert "&lt;" in axes.axis_titles("<x>", "y") and "Wahlbeteiligung" in axes.axis_titles(
        "x", "Wahlbeteiligung"
    )
    flat = Axes.fit([0.1, 0.1], [50.0, 50.0])
    assert flat.x1 > flat.x0 and flat.y1 > flat.y0


# --- Option 03: Added-Variable-Plots -------------------------------------------------------------


def test_added_variable_plot_parses_and_draws_the_slope_through_the_origin() -> None:
    districts = [(1, "Altstadt"), (10, "Flingern"), (38, "Hassels"), (7, "Rath")]
    xs = [-2.0, -1.0, 1.0, 2.0]
    ys = [-4.0, -2.0, 2.0, 4.0]
    svg = added_variable_plot(
        districts,
        xs,
        ys,
        2.0,
        key="hb_score",
        title="Titel des Plots",
        x_title="x bereinigt",
        y_title="y bereinigt",
    )
    root = ET.fromstring(svg)
    assert root.tag == f"{NS}svg" and root.get("class") == "avp"
    points = root.findall(f".//{NS}g[@class='avp-point']")
    assert len(points) == 4
    assert [p.get("data-id") for p in points] == ["1", "10", "38", "7"]
    assert points[0].find(f"{NS}title").text == "1 Altstadt"  # type: ignore[union-attr]
    # Die Gerade geht durch den Ursprung: beide Enden liegen symmetrisch um die Mitte der Achsen
    line = root.find(f".//{NS}line[@class='fit fit-all']")
    assert line is not None
    x1, y1, x2, y2 = (float(line.get(a) or 0.0) for a in ("x1", "y1", "x2", "y2"))
    assert x1 < x2 and y1 > y2  # positive Steigung: SVG zählt y nach unten
    assert root.find(f"{NS}clipPath").get("id") == "avp-hb_score"  # type: ignore[union-attr]
    assert "Titel des Plots" in svg and "x bereinigt" in svg


def test_a_flat_added_variable_plot_still_draws_axes() -> None:
    """Ohne Streuung im Term greift die Mindestspanne von ``Axes.fit`` und das SVG bleibt gültig."""
    svg = added_variable_plot(
        [(1, "A"), (2, "B"), (3, "C")],
        [0.0, 0.0, 0.0],
        [-1.0, 0.0, 1.0],
        0.0,
        key="x",
        title="t",
        x_title="x",
        y_title="y",
    )
    root = ET.fromstring(svg)
    assert len(root.findall(f".//{NS}g[@class='avp-point']")) == 3
    assert root.findall(f".//{NS}g[@class='grid']")


# --- Option 04: die kleinen Karten je Partei -------------------------------------------------------


def _party_row(key: str, label: str, documents: int) -> PartyRow:
    return PartyRow(key, label, label, documents, 0, 0, 0, 41, None, None, None)


def _cells(parties: list[str], districts: list[int]) -> list[PartyCell]:
    return [
        PartyCell(district, party, district, district / 100.0, 0.2, True, district % 5)
        for party in parties
        for district in districts
    ]


def test_party_maps_hold_the_paths_once_and_use_them_per_panel() -> None:
    """Die 41 Pfade stehen einmal in <defs>; jedes Panel ist ein <g> mit 41 <use>."""
    shapes = {1: box(0, 0, 10, 10), 2: box(10, 0, 20, 10), 3: box(0, 10, 10, 20)}
    projection = fit((0.0, 0.0, 20.0, 20.0), 600.0)
    parties = [_party_row("CDU", "CDU", 2139), _party_row("SPD", "SPD", 2106)]
    svg = party_maps(_cells(["CDU", "SPD"], [1, 2, 3]), shapes, projection, parties)
    root = ET.fromstring(svg)
    defs = root.findall(f"{NS}defs")
    assert len(defs) == 1 and len(defs[0]) == len(shapes)
    panels = root.findall(f'.//{NS}g[@class="panel"]')
    assert len(panels) == len(parties)
    uses = root.findall(f".//{NS}use")
    assert len(uses) == len(parties) * len(shapes)
    assert all(u.get("href", "").startswith("#pm-") for u in uses)
    assert all(u.find(f"{NS}title") is not None for u in uses)
    assert svg.count('d="M') == len(shapes)  # jeder Pfad genau einmal
    labels = [t.text for t in root.findall(f'.//{NS}text[@class="panel-label"]')]
    assert labels == ["CDU", "SPD"]


def test_party_maps_title_names_the_numbers_and_the_missing_ballot() -> None:
    shapes = {1: box(0, 0, 10, 10)}
    projection = fit((0.0, 0.0, 10.0, 10.0), 600.0)
    party = _party_row("Die_Linke", "Die Linke", 792)
    cells = [PartyCell(1, "Die_Linke", 7, 0.0088, 0.0, False, 0)]
    svg = party_maps(cells, shapes, projection, [party])
    title = ET.fromstring(svg).find(f".//{NS}use/{NS}title")
    assert title is not None and title.text is not None
    assert "Die Linke, Wahlbezirk 1" in title.text and "7 von 792" in title.text
    assert "nicht angetreten" in title.text


def test_party_maps_are_empty_without_parties() -> None:
    assert party_maps([], {1: box(0, 0, 1, 1)}, fit((0.0, 0.0, 1.0, 1.0), 10.0), []) == ""


# --- Option 02: Streudiagramm der Änderungen ---------------------------------------------------


def _period_row(district: int, d_rate: float, d_turnout: float) -> PeriodRow:
    return PeriodRow(
        id=district,
        name=f"Bezirk {district}",
        hits_old=100,
        hits_new=120,
        rate_old=0.01,
        rate_new=0.01 + d_rate,
        turnout_old=0.50,
        turnout_new=0.50 + d_turnout,
        d_rate=d_rate,
        d_turnout=d_turnout,
    )


def test_delta_label_carries_the_sign_but_not_for_zero() -> None:
    assert delta_label(0.0042) == "+0,004"
    assert delta_label(-0.0042) == "-0,004"
    assert delta_label(0.0) == "0,000"
    assert delta_label(-0.0001) == "0,000"  # gerundete Null trägt kein Minus
    assert delta_label(1.26, 1) == "+1,3"  # format_de rundet kaufmännisch wie round()


def test_delta_scatter_draws_one_line_and_a_point_per_district() -> None:
    rows = [_period_row(1, 0.004, 0.05), _period_row(10, -0.002, -0.01), _period_row(38, 0.0, 0.02)]
    fit = RegressionResult(n=3, slope=500.0, intercept=0.5, r=0.9, p=0.2, stderr=0.1)
    svg = delta_scatter(rows, fit)
    assert svg.startswith('<svg class="scatter deltas"') and svg.endswith("</svg>")
    assert svg.count('class="dpoint"') == 3
    assert svg.count('class="fit fit-all"') == 1
    assert svg.count('class="zero"') == 2  # beide Nulllinien liegen im Bild
    assert 'data-id="10"' in svg
    assert "Trefferquote +0,004" in svg and "Wahlbeteiligung +5,0 Punkte" in svg
    assert "Änderung der Trefferquote" in svg
    # Kein Attribut des Basis-Tooltips: der Abschnitt bedient seine Punkte selbst
    assert "data-terms" not in svg


def test_delta_scatter_survives_a_single_value_on_both_axes() -> None:
    rows = [_period_row(d, 0.0, 0.0) for d in (1, 2, 3)]
    fit = RegressionResult(n=3, slope=0.0, intercept=0.0, r=0.0, p=1.0, stderr=0.0)
    svg = delta_scatter(rows, fit)
    assert svg.count('class="dpoint"') == 3 and "NaN" not in svg


# --- Option 07: Balken je Monat ----------------------------------------------------------------

THREE = [
    MonthRow(dt.date(2025, 10, 1), 12, 10, 5),
    MonthRow(dt.date(2025, 11, 1), 8, 8, 3),
    MonthRow(dt.date(2025, 12, 1), 0, 0, 0),
]


def test_bars_draw_two_rectangles_per_dated_month() -> None:
    svg = bars([*THREE, MonthRow(None, 4, 0, 0)])
    root = ET.fromstring(svg)
    rects = root.findall(f".//{NS}rect")
    assert len(rects) == 2 * len(THREE)  # der Monat ohne Datum bekommt keinen Balken
    groups = root.findall(f".//{NS}g[@class='months']/*")
    assert [g.get("data-month") for g in groups] == ["10.2025", "11.2025", "12.2025"]
    titles = [g.find(f"{NS}title") for g in groups]
    assert titles[0] is not None and titles[0].text is not None
    assert titles[0].text.startswith("Oktober 2025: 12 Dokumente, 10 mit Text, 5 mit Treffer")
    # Ein Monat ohne Dokument hat einen Balken der Höhe 0, keine Lücke
    assert rects[-1].get("height") == "0.00"


def _labels_of(svg: str) -> list[str]:
    root = ET.fromstring(svg)
    group = root.find(f".//{NS}g[@class='month-labels']")
    assert group is not None
    return [text.text or "" for text in group]


def test_bars_axes_cover_the_highest_month_and_label_the_years() -> None:
    svg = bars(THREE)
    assert f">{int(nice_ticks(0.0, 12.0)[-1])}<" in svg  # oberster y-Tick aus nice_ticks
    assert _labels_of(svg) == ["10.2025", "11.2025", "12.2025"]  # kurze Reihe: jeder Monat
    month = dt.date(2024, 11, 1)
    long_series = []
    for _ in range(26):
        long_series.append(MonthRow(month, 1, 1, 0))
        month = next_month(month)
    assert _labels_of(bars(long_series)) == ["2025", "2026"]  # lange Reihe: nur die Januare


def test_bars_need_at_least_one_dated_month() -> None:
    with pytest.raises(deal.PreContractError):
        bars([MonthRow(None, 3, 0, 0)])


def test_bars_of_three_months_are_stable(snapshot: SnapshotAssertion) -> None:
    assert bars(THREE) == snapshot


def test_bars_use_whole_numbers_on_the_y_axis() -> None:
    """Wenige Dokumente je Monat: nice_ticks gäbe 0,5er-Schritte, Dokumente sind aber ganze Zahlen."""
    svg = bars([MonthRow(dt.date(2025, 10, 1), 2, 2, 2), MonthRow(dt.date(2025, 11, 1), 1, 1, 1)])
    root = ET.fromstring(svg)
    group = root.find(f".//{NS}g[@class='ticks']")
    assert group is not None
    assert [text.text for text in group] == ["0", "1", "2"]


@pytest.mark.parametrize("count", [3, 13, 14, 18, 23, 25, 61, 300])
def test_bar_labels_never_overlap(count: int) -> None:
    """Bei 14 bis 23 Monaten mit nur einem Januar stießen die Beschriftungen aneinander
    (Abstand 37,9 bei Breite 41,8; Review 2026-10-12). Der Abstand kommt jetzt aus der Breite."""
    month = dt.date(2025, 2, 1)  # Februar: die kurzen Reihen haben nur einen Januar
    rows = []
    for _ in range(count):
        rows.append(MonthRow(month, 3, 3, 1))
        month = next_month(month)
    root = ET.fromstring(bars(rows))
    group = root.find(f".//{NS}g[@class='month-labels']")
    assert group is not None
    labels = [(float(text.get("x") or 0), text.text or "") for text in group]
    assert labels, count
    widest = max(len(text) for _, text in labels) * 6.0  # 11 px Schrift, rund 6 px je Zeichen
    gaps = [b - a for (a, _), (b, _) in zip(labels, labels[1:], strict=False)]
    assert all(gap >= widest for gap in gaps), (count, widest, gaps)
