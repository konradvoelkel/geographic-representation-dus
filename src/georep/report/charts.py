"""Karte und Streudiagramm als inline SVG aus Zahlen; kein matplotlib.

Farben kommen aus CSS-Klassen (``q0`` bis ``q4``, ``dot``, ``fit``), damit die Vorlage Hell und
Dunkel über ``prefers-color-scheme`` schaltet, ohne das SVG neu zu bauen. Alles Textuelle aus den
Daten läuft durch ``html.escape``; die Vorlage fügt die Zeichenkette mit ``|safe`` ein.
"""

from __future__ import annotations

import bisect
import html
import math
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import deal
from shapely.geometry.base import BaseGeometry

from georep.analysis.regression import RegressionPair
from georep.report.geometry import Projection, label_point, svg_path
from georep.report.model import DistrictRow, format_de, percent_de

CLASSES = 5  # Quantilklassen der Choroplethe; weniger, wenn es weniger verschiedene Werte gibt
MAP_WIDTH = 600.0
SCATTER_WIDTH = 640.0
SCATTER_HEIGHT = 420.0
MARGIN = (16.0, 16.0, 48.0, 56.0)  # oben, rechts, unten, links
DOT_RADIUS = 4.0  # 8 px Marker
HIT_RADIUS = 12.0  # Trefferfläche 24 px, größer als die Marke


@dataclass(frozen=True)
class Classification:
    boundaries: tuple[float, ...]  # count - 1 Grenzen, aufsteigend; Klasse i = [b_{i-1}, b_i)
    classes: dict[int, int]  # Wahlbezirk -> Klasse 0 .. count - 1
    count: int


@dataclass(frozen=True)
class LegendEntry:
    klass: int
    label: str


@dataclass(frozen=True)
class Poi:
    """Ein Ort auf der Karte, schon in SVG-Koordinaten."""

    x: float
    y: float
    label: str
    district: int


@deal.pre(
    lambda values, n=CLASSES: (
        n >= 1 and len(values) > 0 and all(math.isfinite(v) for v in values.values())
    )
)
@deal.post(
    lambda result: (
        1 <= result.count
        and len(result.boundaries) == result.count - 1
        and all(a <= b for a, b in zip(result.boundaries, result.boundaries[1:], strict=False))
        and all(0 <= k < result.count for k in result.classes.values())
    )
)
def classify(values: Mapping[int, float], n: int = CLASSES) -> Classification:
    """Quantilklassen: so viele wie ``n``, höchstens so viele wie verschiedene Werte (Mini-Fixture: 3)."""
    distinct = sorted(set(values.values()))
    count = min(n, len(distinct))
    boundaries = (
        tuple(statistics.quantiles(values.values(), n=count, method="inclusive"))
        if count > 1
        else ()
    )
    classes = {key: bisect.bisect_right(boundaries, value) for key, value in values.items()}
    return Classification(boundaries, classes, count)


def legend(classification: Classification, fmt: Callable[[float], str]) -> tuple[LegendEntry, ...]:
    """Eine Zeile je Klasse: „unter a", „a bis unter b", „ab b"; eine einzige Klasse heißt „alle"."""
    bounds = classification.boundaries
    if not bounds:
        return (LegendEntry(0, "alle"),)
    entries = [LegendEntry(0, f"unter {fmt(bounds[0])}")]
    entries.extend(
        LegendEntry(i, f"{fmt(low)} bis unter {fmt(high)}")
        for i, (low, high) in enumerate(zip(bounds, bounds[1:], strict=False), start=1)
    )
    entries.append(LegendEntry(len(bounds), f"ab {fmt(bounds[-1])}"))
    return tuple(entries)


def _covers_range(lo: float, hi: float, n: int = 5, result: tuple[float, ...] = ()) -> bool:
    return result[0] <= lo and result[-1] >= hi


def _spread(lo: float, hi: float, n: int = 5) -> bool:
    """Endlich, ``n`` sinnvoll, und die Spanne liegt über dem Fließkomma-Rauschen der Grenzen
    (sonst läuft die Zehnerpotenz des Schritts auf 0 oder die Ticks fallen zusammen)."""
    return (
        math.isfinite(lo)
        and math.isfinite(hi)
        and 2 <= n <= 20
        and hi - lo >= 1e-9 * max(1.0, abs(lo), abs(hi))
    )


@deal.pure
@deal.pre(_spread)
@deal.post(
    lambda result: (
        len(result) >= 2 and all(a < b for a, b in zip(result, result[1:], strict=False))
    ),
    message="aufsteigende Ticks",
)
@deal.ensure(_covers_range, message="die Ticks decken den Wertebereich")
def nice_ticks(lo: float, hi: float, n: int = 5) -> tuple[float, ...]:
    """Rund ``n`` Ticks mit Schritt 1, 2 oder 5 mal einer Zehnerpotenz, die ``[lo, hi]`` einschließen."""
    raw = (hi - lo) / (n - 1)
    magnitude = 10.0 ** math.floor(math.log10(raw))
    residual = raw / magnitude
    factor = 1.0 if residual <= 1 else 2.0 if residual <= 2 else 5.0 if residual <= 5 else 10.0
    step = factor * magnitude
    first = math.floor(lo / step)
    last = math.ceil(hi / step)
    while first * step > lo:  # Rundung von lo / step über eine ganze Zahl hinweg
        first -= 1
    while last * step < hi:
        last += 1
    return tuple(i * step for i in range(first, last + 1))


def _decimals(step: float) -> int:
    return max(0, -math.floor(math.log10(step)))


def _num(value: float) -> str:
    return f"{value:.2f}"


def _attr(text: str) -> str:
    return html.escape(text, quote=True)


def rate_label(value: float) -> str:
    return format_de(value, 3)


def turnout_label(value: float) -> str:
    return percent_de(value, 1)


def _title(row: DistrictRow) -> str:
    return (
        f"{row.id} {row.name}: {format_de(row.hits)} Dokumente, Trefferquote {rate_label(row.rate)}, "
        f"Wahlbeteiligung {turnout_label(row.turnout)}"
    )


def district_attributes(row: DistrictRow) -> str:
    """``data-``-Attribute, aus denen das JavaScript Tooltip und Markierung speist."""
    terms = ", ".join(t.term for t in row.top_terms)
    pairs = {
        "data-id": str(row.id),
        "data-name": row.name,
        "data-hits": format_de(row.hits),
        "data-eligible": format_de(row.eligible),
        "data-rate": rate_label(row.rate),
        "data-turnout": turnout_label(row.turnout),
        "data-terms": terms,
    }
    return " ".join(f'{key}="{_attr(value)}"' for key, value in pairs.items())


def choropleth(
    rows: Sequence[DistrictRow],
    shapes: Mapping[int, BaseGeometry],
    projection: Projection,
    rate: Classification,
    turnout: Classification,
    pois: Sequence[Poi] = (),
) -> str:
    """Eine ``<path>`` je Wahlbezirk mit Klasse nach der Trefferquote; die Wahlbeteiligungsklasse
    steht daneben als ``data-class-turnout``, der Umschalter tauscht nur die Klasse. Die Orte
    tragen Name und Wahlbezirk als ``data-``-Attribute für den Tooltip."""
    by_id = {row.id: row for row in rows}
    parts = [
        f'<svg class="map" viewBox="{projection.view_box}" role="img" '
        'aria-labelledby="map-title" xmlns="http://www.w3.org/2000/svg">',
        '<title id="map-title">Karte der 41 Kommunalwahlbezirke</title>',
        '<g class="districts" fill-rule="evenodd">',
    ]
    for district, geometry in sorted(shapes.items()):
        row = by_id[district]
        parts.append(
            f'<path class="district q{rate.classes[district]}" '
            f'data-class-rate="{rate.classes[district]}" '
            f'data-class-turnout="{turnout.classes[district]}" '
            f'{district_attributes(row)} tabindex="0" d="{svg_path(geometry, projection)}">'
            f"<title>{html.escape(_title(row))}</title></path>"
        )
    parts.append("</g>")
    if pois:
        parts.append('<g class="pois" aria-hidden="true">')
        parts.extend(
            f'<circle cx="{_num(p.x)}" cy="{_num(p.y)}" r="2" data-name="{_attr(p.label)}" '
            f'data-district="{p.district}"><title>{html.escape(p.label)} '
            f"(Wahlbezirk {p.district})</title></circle>"
            for p in pois
        )
        parts.append("</g>")
    parts.append('<g class="map-labels" aria-hidden="true">')
    for district, geometry in sorted(shapes.items()):
        x, y = label_point(geometry, projection)
        parts.append(f'<text x="{_num(x)}" y="{_num(y)}">{district}</text>')
    parts.append("</g></svg>")
    return "".join(parts)


def project_points(
    points: Sequence[tuple[float, float]], projection: Projection
) -> list[tuple[float, float]]:
    """Punkte im Arbeits-CRS auf die Karte."""
    return [projection.point(x, y) for x, y in points]


def project_pois(
    points: Sequence[tuple[float, float, str, int]], projection: Projection
) -> list[Poi]:
    """(x, y, Name, Wahlbezirk) im Arbeits-CRS zu Orten auf der Karte."""
    return [Poi(*projection.point(x, y), label, district) for x, y, label, district in points]


@dataclass(frozen=True)
class Axes:
    """Achsen eines Diagramms: Ränder, Wertebereich aus ``nice_ticks``, Skalen und die SVG-Teile,
    die jedes Punkt- oder Balkendiagramm gleich zeichnet (Gitter, Achsenlinien, Ticks, Titel).

    Herausgezogen aus ``scatter`` (Fundament F7), damit weitere Diagramme (Added-Variable-Plots,
    Differenzen zweier Perioden, Balken je Monat) dieselben Achsen bekommen; die Ausgabe von
    ``scatter`` ist dabei byteidentisch geblieben.
    """

    width: float
    height: float
    x_ticks: tuple[float, ...]
    y_ticks: tuple[float, ...]
    margin: tuple[float, float, float, float] = MARGIN  # oben, rechts, unten, links

    @classmethod
    def fit(
        cls,
        xs: Sequence[float],
        ys: Sequence[float],
        *,
        width: float = SCATTER_WIDTH,
        height: float = SCATTER_HEIGHT,
        x_span: float = 0.01,
        y_span: float = 1.0,
        margin: tuple[float, float, float, float] = MARGIN,
    ) -> Axes:
        """Ticks aus den Daten; ohne Streuung wird eine kleine Spanne (``x_span``, ``y_span``) angenommen."""
        x_ticks = nice_ticks(min(xs), max(xs) if max(xs) > min(xs) else min(xs) + x_span)
        y_ticks = nice_ticks(min(ys), max(ys) if max(ys) > min(ys) else min(ys) + y_span)
        return cls(width, height, x_ticks, y_ticks, margin)

    @property
    def top(self) -> float:
        return self.margin[0]

    @property
    def right(self) -> float:
        return self.margin[1]

    @property
    def bottom(self) -> float:
        return self.margin[2]

    @property
    def left(self) -> float:
        return self.margin[3]

    @property
    def plot_w(self) -> float:
        return self.width - self.left - self.right

    @property
    def plot_h(self) -> float:
        return self.height - self.top - self.bottom

    @property
    def x0(self) -> float:
        return self.x_ticks[0]

    @property
    def x1(self) -> float:
        return self.x_ticks[-1]

    @property
    def y0(self) -> float:
        return self.y_ticks[0]

    @property
    def y1(self) -> float:
        return self.y_ticks[-1]

    def sx(self, x: float) -> float:
        return self.left + (x - self.x0) / (self.x1 - self.x0) * self.plot_w

    def sy(self, y: float) -> float:
        return self.top + (self.y1 - y) / (self.y1 - self.y0) * self.plot_h

    def clip_path(self, clip_id: str = "plot") -> str:
        return (
            f'<clipPath id="{clip_id}"><rect x="{_num(self.left)}" y="{_num(self.top)}" '
            f'width="{_num(self.plot_w)}" height="{_num(self.plot_h)}"/></clipPath>'
        )

    def grid(self) -> str:
        parts = ['<g class="grid">']
        parts.extend(
            f'<line x1="{_num(self.left)}" x2="{_num(self.left + self.plot_w)}" '
            f'y1="{_num(self.sy(t))}" y2="{_num(self.sy(t))}"/>'
            for t in self.y_ticks
        )
        parts.extend(
            f'<line y1="{_num(self.top)}" y2="{_num(self.top + self.plot_h)}" '
            f'x1="{_num(self.sx(t))}" x2="{_num(self.sx(t))}"/>'
            for t in self.x_ticks
        )
        parts.append("</g>")
        return "".join(parts)

    def axis_lines(self) -> str:
        return (
            '<g class="axis">'
            f'<line x1="{_num(self.left)}" x2="{_num(self.left + self.plot_w)}" '
            f'y1="{_num(self.top + self.plot_h)}" y2="{_num(self.top + self.plot_h)}"/>'
            f'<line x1="{_num(self.left)}" x2="{_num(self.left)}" '
            f'y1="{_num(self.top)}" y2="{_num(self.top + self.plot_h)}"/>'
            "</g>"
        )

    def tick_labels(self) -> str:
        x_dec = _decimals(self.x_ticks[1] - self.x_ticks[0])
        y_dec = _decimals(self.y_ticks[1] - self.y_ticks[0])
        parts = ['<g class="ticks">']
        parts.extend(
            f'<text x="{_num(self.sx(t))}" y="{_num(self.top + self.plot_h + 18)}" '
            f'text-anchor="middle">{format_de(t, x_dec)}</text>'
            for t in self.x_ticks
        )
        parts.extend(
            f'<text x="{_num(self.left - 8)}" y="{_num(self.sy(t))}" text-anchor="end" '
            f'dominant-baseline="middle">{format_de(t, y_dec)}</text>'
            for t in self.y_ticks
        )
        parts.append("</g>")
        return "".join(parts)

    def axis_titles(self, x_title: str, y_title: str) -> str:
        return (
            f'<text class="axis-label" x="{_num(self.left + self.plot_w / 2)}" '
            f'y="{_num(self.height - 8)}" text-anchor="middle">{html.escape(x_title)}</text>'
            f'<text class="axis-label" transform="translate(14 {_num(self.top + self.plot_h / 2)}) '
            f'rotate(-90)" text-anchor="middle">{html.escape(y_title)}</text>'
        )


def scatter(
    rows: Sequence[DistrictRow],
    regression: RegressionPair,
    *,
    width: float = SCATTER_WIDTH,
    height: float = SCATTER_HEIGHT,
) -> str:
    """Trefferquote (x) gegen Wahlbeteiligung in Prozent (y), Punkte mit Nummer, beide Geraden."""
    xs = [row.rate for row in rows]
    ys = [row.turnout * 100.0 for row in rows]
    axes = Axes.fit(xs, ys, width=width, height=height)
    parts = [
        f'<svg class="scatter" viewBox="0 0 {_num(width)} {_num(height)}" role="img" '
        'aria-labelledby="scatter-title" xmlns="http://www.w3.org/2000/svg">',
        '<title id="scatter-title">Trefferquote gegen Wahlbeteiligung je Wahlbezirk</title>',
        axes.clip_path(),
        axes.grid(),
        axes.axis_lines(),
        axes.tick_labels(),
        axes.axis_titles("Trefferquote (Dokumente je Wahlberechtigtem)", "Wahlbeteiligung in %"),
        '<g class="fits" clip-path="url(#plot)">',
    ]
    fits = [("fit-all", regression.all)]
    if regression.without is not None:
        fits.append(("fit-without", regression.without))
    x0, x1 = axes.x0, axes.x1
    for cls, fit in fits:
        parts.append(
            f'<line class="fit {cls}" x1="{_num(axes.sx(x0))}" '
            f'y1="{_num(axes.sy(fit.slope * x0 + fit.intercept))}" '
            f'x2="{_num(axes.sx(x1))}" y2="{_num(axes.sy(fit.slope * x1 + fit.intercept))}"/>'
        )
    parts.append('</g><g class="dots">')
    for row, x, y in zip(rows, xs, ys, strict=True):
        cx, cy = _num(axes.sx(x)), _num(axes.sy(y))
        parts.append(
            f'<g class="point" {district_attributes(row)} tabindex="0">'
            f"<title>{html.escape(_title(row))}</title>"
            f'<circle class="hit" cx="{cx}" cy="{cy}" r="{_num(HIT_RADIUS)}"/>'
            f'<circle class="dot" cx="{cx}" cy="{cy}" r="{_num(DOT_RADIUS)}"/>'
            f'<text class="dot-label" x="{_num(axes.sx(x) + 6)}" y="{_num(axes.sy(y) - 6)}">{row.id}</text>'
            "</g>"
        )
    parts.append("</g></svg>")
    return "".join(parts)
