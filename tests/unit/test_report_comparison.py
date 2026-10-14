"""Der Städtevergleich an synthetischen Stadtseiten: Zahlen, Markenformen, Gerade je Stadt.

``tests/golden/test_publish.py`` baut zwei echte Mini-Städte und prüft, dass die Seite entsteht
und nur erlaubte Links trägt. Was auf ihr **steht**, prüfte bis zum 2026-10-13 nichts: der
Mutationslauf tötete nur 17 von 37 Mutanten in ``report/comparison.py``, und die Überlebenden
lagen in der Geometrie des Streudiagramms, in ``eligible_per_district``, im Parsen der
Regression und im Rückfall des Links auf ``./`` (docs/mutation-2026-10-13.md).

Hier stehen darum ``CitySite``-Objekte von Hand -- ohne Dateien, ohne Kette --, damit jede Zahl
nachrechenbar ist.
"""

from __future__ import annotations

import datetime as dt
import re

import pytest

from georep.report.comparison import (
    SCATTER_HEIGHT,
    SCATTER_WIDTH,
    CitySite,
    ComparisonModel,
    DistrictPoint,
    comparison_scatter,
    shared_classes,
    table_rows,
)

NOW = dt.datetime(2026, 10, 13, 9, 0, tzinfo=dt.UTC)
FIGURES = {
    "districts": 3,
    "precincts": 22,
    "documents": 200,
    # Review 2026-10-14: nicht jedes Dokument ist durchsuchbar; die Tabelle sagt es jetzt
    "documents_with_text": 150,
    "terms": 150,
    "documents_hit": 90,
    "turnout_median": 0.5,
}


def _city(
    slug: str,
    *,
    href: str = "",
    rates: tuple[float, ...] = (0.02, 0.04, 0.06),
    eligible: tuple[int, ...] = (1000, 2000, 3000),
    regression: object | None = None,
) -> CitySite:
    districts = tuple(
        DistrictPoint(
            id=i + 1, name=f"Bezirk {i + 1}", rate=rate, turnout=0.4 + 0.1 * i, eligible=n
        )
        for i, (rate, n) in enumerate(zip(rates, eligible, strict=True))
    )
    summary: dict[str, object] = {"figures": dict(FIGURES), "city": {"slug": slug, "name": slug}}
    if regression is not None:
        summary["regression"] = regression
    return CitySite(
        slug=slug,
        name=slug.capitalize(),
        href=href,
        summary=summary,
        districts=districts,
        shapes={},
    )


FIT = {"all": {"n": 3, "slope": 100.0, "intercept": 40.0, "r": 0.5, "p": 0.25, "stderr": 1.0}}


def test_the_voters_per_district_are_the_mean_and_not_the_sum() -> None:
    city = _city("a", eligible=(1000, 2000, 3000))
    assert city.eligible_per_district == pytest.approx(2000.0)
    assert _city("leer", rates=(), eligible=()).eligible_per_district == 0.0


def test_the_regression_is_read_from_the_summary_or_absent() -> None:
    """``summary.json`` ist eine Datei: jede Form, die nicht passt, heißt „keine Regression"."""
    fitted = _city("a", regression=FIT).fit
    assert fitted is not None
    assert (fitted.n, fitted.slope, fitted.intercept) == (3, 100.0, 40.0)
    assert (fitted.r, fitted.p, fitted.stderr) == (0.5, 0.25, 1.0)
    assert _city("a").fit is None  # ohne den Schlüssel
    assert _city("a", regression={"all": None}).fit is None  # „all" ist kein Objekt
    assert _city("a", regression="alles").fit is None  # „regression" ist kein Objekt


def test_the_table_row_names_the_numbers_of_the_summary() -> None:
    # Ohne ``build_comparison``: das Modell von Hand, denn die kleinen Karten brauchen Flächen.
    model = ComparisonModel(
        generated_at=NOW,
        version="0.0.0",
        commit=None,
        cities=(_city("a", href="", regression=FIT), _city("b", href="b/")),
        maps=(),
        scatter_svg="",
        rate_legend=(),
    )
    first, second = table_rows(model)
    assert first["href"] == "./"  # die erste Stadt liegt an der Wurzel
    assert second["href"] == "b/"
    assert first["districts"] == "3" and first["documents"] == "200"
    assert first["documents_with_text"] == "150"  # Review 2026-10-14
    assert first["eligible_per_district"] == "2\u202f000"  # Mittel, mit Tausendertrenner
    assert first["rate_median"] == second["rate_median"]  # derselbe Median derselben Quoten
    assert (first["r"], first["p"]) == ("0,500", "0,250")
    assert (second["r"], second["p"]) == ("—", "—")  # ohne Regression kein Wert


def test_the_scatter_carries_one_marker_per_district_and_a_shape_per_city() -> None:
    """Je Stadt eine Markenform: Farbe allein ist keine Kodierung (Skill ``dataviz``)."""
    svg = comparison_scatter((_city("a", regression=FIT), _city("b")))
    assert svg.count('<circle class="dot"') == 3  # die erste Stadt: Kreise
    assert svg.count('<rect class="dot"') == 3  # die zweite: Quadrate
    assert svg.count('class="dots s0"') == 1 and svg.count('class="dots s1"') == 1
    # Die Gerade gibt es nur für die Stadt, die eine Regression mitbringt
    assert svg.count('class="fit"') == 1 and 'class="fits s0"' in svg


def test_the_fit_line_ends_where_the_regression_says() -> None:
    """Die Gerade geht über den Wertebereich **dieser** Stadt, y = Steigung · x + Achsenabschnitt.

    Mit Steigung 100 und Abschnitt 40 liegt sie bei x = 0,02 auf 42 % und bei x = 0,06 auf 46 %;
    in SVG wächst y nach unten, das linke Ende liegt also tiefer als das rechte.
    """
    svg = comparison_scatter((_city("a", regression=FIT),))
    ends = re.search(
        r'<line class="fit" x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"', svg
    )
    assert ends is not None
    x1, y1, x2, y2 = (float(v) for v in ends.groups())
    dots = _numbers(svg, r'<circle class="dot" cx="([-\d.]+)" cy="([-\d.]+)"')
    # Die Enden sitzen über dem kleinsten und dem größten x der Stadt
    assert x1 == pytest.approx(min(x for x, _ in dots))
    assert x2 == pytest.approx(max(x for x, _ in dots))
    # y = 100 · x + 40: bei 0,02 sind das 42, bei 0,06 sind es 46 -- und 42 liegt tiefer
    assert y1 > y2
    span = (y1 - y2) / (46.0 - 42.0)
    assert span > 0 and (y1 - y2) == pytest.approx(4.0 * span)


def test_the_square_sits_on_the_same_point_as_a_circle_would() -> None:
    """Das Quadrat ist 7 Einheiten groß und um 3,5 nach links oben versetzt: dieselbe Mitte."""
    circles = _numbers(
        comparison_scatter((_city("a"),)), r'<circle class="dot" cx="([-\d.]+)" cy="([-\d.]+)"'
    )
    squares = _numbers(
        comparison_scatter((_city("x"), _city("a"))),
        r'<rect class="dot" x="([-\d.]+)" y="([-\d.]+)"',
    )
    assert len(circles) == len(squares) == 3
    for (cx, cy), (x, y) in zip(circles, squares, strict=True):
        assert x == pytest.approx(cx - 3.5, abs=0.01)
        assert y == pytest.approx(cy - 3.5, abs=0.01)


def test_the_turnout_is_drawn_in_percent_and_grows_upwards() -> None:
    """y ist die Wahlbeteiligung mal 100; in SVG wächst y nach unten, der höhere Wert liegt oben."""
    svg = comparison_scatter((_city("a"),))
    points = _numbers(svg, r'<circle class="dot" cx="([-\d.]+)" cy="([-\d.]+)"')
    assert [y for _, y in points] == sorted((y for _, y in points), reverse=True)
    assert "Wahlbeteiligung in %" in svg
    assert all(0.0 <= y <= SCATTER_HEIGHT and 0.0 <= x <= SCATTER_WIDTH for x, y in points)


def test_the_classes_are_shared_over_both_cities() -> None:
    """Getrennte Quantile verglichen Farben, die nichts miteinander zu tun haben."""
    cities = (_city("a", rates=(0.01, 0.02, 0.03)), _city("b", rates=(0.04, 0.05, 0.06)))
    classes = shared_classes(cities)
    assert len(classes.classes) == 6  # eine Klasse je Wahlbezirk beider Städte
    first = [classes.classes[i] for i in range(3)]
    second = [classes.classes[i] for i in range(3, 6)]
    assert max(first) <= min(second)  # die kleineren Quoten liegen in den kleineren Klassen


def _numbers(svg: str, pattern: str) -> list[tuple[float, float]]:
    return [(float(a), float(b)) for a, b in re.findall(pattern, svg)]
