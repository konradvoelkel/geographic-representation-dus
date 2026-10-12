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

from georep.analysis.regression import RegressionPair, RegressionResult
from georep.report.geometry import Projection, label_point, svg_path
from georep.report.model import (
    DistrictRow,
    PartyCell,
    PartyRow,
    PeriodRow,
    format_de,
    percent_de,
)

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


def own_share_label(value: float) -> str:
    """Option 05: der Anteil der eigenen Bezirksvertretung, ganze Prozent (Legende und Tooltip)."""
    return percent_de(value, 0)


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
    if row.bodies is not None:  # Option 05: eine Zeile mehr im Tooltip
        pairs["data-own"] = f"{format_de(row.bodies.own)} ({own_share_label(row.bodies.own_share)})"
    return " ".join(f'{key}="{_attr(value)}"' for key, value in pairs.items())


def choropleth(
    rows: Sequence[DistrictRow],
    shapes: Mapping[int, BaseGeometry],
    projection: Projection,
    rate: Classification,
    turnout: Classification,
    pois: Sequence[Poi] = (),
    extra_classes: Mapping[str, Classification] = {},
) -> str:
    """Eine ``<path>`` je Wahlbezirk mit Klasse nach der Trefferquote; die Wahlbeteiligungsklasse
    steht daneben als ``data-class-turnout``, der Umschalter tauscht nur die Klasse. Weitere
    Kennzahlen (``extra_classes``, Option 5: Gremien) bekommen je ein ``data-class-<name>``; das
    JavaScript schaltet sie über ein Radio mit demselben ``value`` und eine Legende
    ``#legend-<name>``. Die Orte tragen Name und Wahlbezirk als ``data``-Attribute für den Tooltip."""
    by_id = {row.id: row for row in rows}
    extra = {
        key: classification
        for key, classification in extra_classes.items()
        if key not in ("rate", "turnout")
    }
    parts = [
        f'<svg class="map" viewBox="{projection.view_box}" role="img" '
        'aria-labelledby="map-title" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="map-title">Karte der {len(rows)} Kommunalwahlbezirke</title>',
        '<g class="districts" fill-rule="evenodd">',
    ]
    for district, geometry in sorted(shapes.items()):
        row = by_id[district]
        parts.append(
            f'<path class="district q{rate.classes[district]}" '
            f'data-class-rate="{rate.classes[district]}" '
            f'data-class-turnout="{turnout.classes[district]}" '
            + "".join(
                f'data-class-{key}="{classification.classes[district]}" '
                for key, classification in extra.items()
            )
            + f'{district_attributes(row)} tabindex="0" d="{svg_path(geometry, projection)}">'
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


# --- Option 03: Added-Variable-Plots zum Hauptmodell ---------------------------------------------

AVP_WIDTH = 330.0
AVP_HEIGHT = 250.0
AVP_MARGIN = (22.0, 12.0, 44.0, 48.0)  # oben, rechts, unten, links; schmaler als das Streudiagramm


def added_variable_plot(
    districts: Sequence[tuple[int, str]],
    xs: Sequence[float],
    ys: Sequence[float],
    slope: float,
    *,
    key: str,
    title: str,
    x_title: str,
    y_title: str,
) -> str:
    """Ein partielles Streudiagramm: Residuen eines Terms gegen Residuen der Wahlbeteiligung.

    Beide Größen sind um die übrigen Terme bereinigt (Frisch-Waugh-Lovell), darum geht die Gerade
    durch den Ursprung und ihre Steigung ist genau der Koeffizient des Terms. ``districts`` sind
    (Nummer, Name) in der Reihenfolge der Punkte; sie tragen nur ``data-id`` und einen kurzen
    ``<title>``, nicht die ganzen Tooltip-Attribute des Streudiagramms: vier Plots mit je 41
    Punkten kosteten so 95 KB statt 37 KB, und Tooltip gibt es auf Karte und Streudiagramm.
    ``key`` macht die IDs im Dokument eindeutig.
    """
    axes = Axes.fit(xs, ys, width=AVP_WIDTH, height=AVP_HEIGHT, x_span=1.0, margin=AVP_MARGIN)
    clip = f"avp-{key}"
    parts = [
        f'<svg class="avp" viewBox="0 0 {_num(AVP_WIDTH)} {_num(AVP_HEIGHT)}" role="img" '
        f'aria-labelledby="{clip}-title" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="{clip}-title">{html.escape(title)}</title>',
        axes.clip_path(clip),
        axes.grid(),
        axes.axis_lines(),
        axes.tick_labels(),
        axes.axis_titles(x_title, y_title),
        f'<g class="fits" clip-path="url(#{clip})">'
        f'<line class="fit fit-all" x1="{_num(axes.sx(axes.x0))}" '
        f'y1="{_num(axes.sy(slope * axes.x0))}" x2="{_num(axes.sx(axes.x1))}" '
        f'y2="{_num(axes.sy(slope * axes.x1))}"/></g>',
        '<g class="dots">',
    ]
    for (district, name), x, y in zip(districts, xs, ys, strict=True):
        cx, cy = _num(axes.sx(x)), _num(axes.sy(y))
        parts.append(
            f'<g class="avp-point" data-id="{district}" tabindex="0">'
            f"<title>{html.escape(f'{district} {name}')}</title>"
            f'<circle class="hit" cx="{cx}" cy="{cy}" r="{_num(HIT_RADIUS)}"/>'
            f'<circle class="dot" cx="{cx}" cy="{cy}" r="{_num(DOT_RADIUS)}"/>'
            f'<text class="dot-label" x="{_num(axes.sx(x) + 5)}" '
            f'y="{_num(axes.sy(y) - 5)}">{district}</text></g>'
        )
    parts.append("</g></svg>")
    return "".join(parts)


# --- Option 04: sechs kleine Karten in einem SVG --------------------------------------------------

PANEL_COLUMNS = 3  # 3 x 2 bei sechs Parteien; die Zeilenzahl folgt aus der Zahl der Parteien
PANEL_GAP = 10.0  # SVG-Einheiten zwischen den Panels
PANEL_LABEL = 18.0  # Platz über jedem Panel für die Beschriftung


def _share_label(value: float) -> str:
    return percent_de(value, 1)


def _panel_title(party: PartyRow, district: int, cell: PartyCell | None) -> str:
    """Der ``<title>`` einer Fläche: Treffer, Anteil und Stimmenanteil im Klartext."""
    if cell is None:
        return f"{party.label}, Wahlbezirk {district}: keine Daten"
    votes = percent_de(cell.vote_share, 1) if cell.ran else "nicht angetreten"
    return (
        f"{party.label}, Wahlbezirk {district}: {format_de(cell.hits)} von "
        f"{format_de(party.documents)} Dokumenten ({_share_label(cell.share)}), "
        f"Stimmenanteil {votes}"
    )


def party_maps(
    cells: Sequence[PartyCell],
    shapes: Mapping[int, BaseGeometry],
    projection: Projection,
    parties: Sequence[PartyRow],
    *,
    columns: int = PANEL_COLUMNS,
) -> str:
    """Ein SVG mit einer kleinen Karte je Partei; die 41 Flächen stehen einmal in ``<defs>``.

    Die Pfade sind der teuerste Teil der Seite (28 KB für 41 Flächen); sechs eigenständige SVGs
    wären sechsmal so groß. Hier liegen sie einmal als ``<path id="pm-N">`` in ``<defs>``, und
    jedes Panel ist ein ``<g transform>`` mit 41 ``<use>``, die nur die Klasse und den ``<title>``
    tragen. Die Quantilklassen sind je Partei gerechnet (``PartyCell.klass``), nicht gemeinsam:
    bei einer gemeinsamen Skala läge die AfD mit 71 Treffern überall in der untersten Klasse.
    """
    if not parties or not shapes:
        return ""
    by_party: dict[str, dict[int, PartyCell]] = {}
    for cell in cells:
        by_party.setdefault(cell.party, {})[cell.district] = cell
    scale = 1.0 / columns
    panel_w = projection.width * scale
    panel_h = projection.height * scale
    rows = (len(parties) + columns - 1) // columns
    width = columns * panel_w + (columns - 1) * PANEL_GAP
    height = rows * (panel_h + PANEL_LABEL) + (rows - 1) * PANEL_GAP
    parts = [
        f'<svg class="party-maps" viewBox="0 0 {_num(width)} {_num(height)}" role="img" '
        'aria-labelledby="party-maps-title" xmlns="http://www.w3.org/2000/svg">',
        '<title id="party-maps-title">Je Partei eine Karte: Anteil der Dokumente der Partei, '
        "die den Wahlbezirk erwähnen</title>",
        "<defs>",
    ]
    parts.extend(
        f'<path id="pm-{district}" d="{svg_path(geometry, projection)}"/>'
        for district, geometry in sorted(shapes.items())
    )
    parts.append("</defs>")
    for index, party in enumerate(parties):
        column, row = index % columns, index // columns
        x = column * (panel_w + PANEL_GAP)
        y = row * (panel_h + PANEL_LABEL + PANEL_GAP)
        mine = by_party.get(party.key, {})
        parts.append(f'<g class="panel" transform="translate({_num(x)} {_num(y)})">')
        parts.append(f'<text class="panel-label" x="0" y="12">{html.escape(party.label)}</text>')
        parts.append(f'<g transform="translate(0 {_num(PANEL_LABEL)}) scale({scale:.6f})">')
        for district in sorted(shapes):
            found = mine.get(district)
            klass = found.klass if found is not None else 0
            parts.append(
                f'<use href="#pm-{district}" class="district q{klass}">'
                f"<title>{html.escape(_panel_title(party, district, found))}</title></use>"
            )
        parts.append("</g></g>")
    parts.append("</svg>")
    return "".join(parts)


# --- Option 02: Streudiagramm der Änderungen zwischen zwei Wahlperioden ------------------------


def delta_label(value: float, decimals: int = 3) -> str:
    """Eine Änderung mit Vorzeichen: ``+0,004``, ``-1,2``; eine gerundete Null bleibt ohne."""
    text = format_de(value, decimals)
    if text.startswith("-") or set(text) <= {"0", ","}:
        return text
    return f"+{text}"


def delta_scatter(
    rows: Sequence[PeriodRow],
    regression: RegressionResult,
    *,
    width: float = SCATTER_WIDTH,
    height: float = SCATTER_HEIGHT,
) -> str:
    """Änderung der Trefferquote (x) gegen Änderung der Wahlbeteiligung in Prozentpunkten (y).

    Dieselben Achsen wie ``scatter`` (Fundament F7), eine Gerade statt zwei, und die Punkte
    tragen nur ``data-id`` und einen eigenen ``<title>``: das Basis-JavaScript des Rahmens
    bedient ``.point``, dieser Abschnitt bedient ``.dpoint`` selbst (templates/sections).
    """
    xs = [row.d_rate for row in rows]
    ys = [row.d_turnout * 100.0 for row in rows]
    # Die Null gehört in ein Diagramm von Änderungen: sie trennt Zunahme von Abnahme, auch wenn
    # alle Punkte auf einer Seite liegen. Darum spannen die Achsen sie immer mit auf.
    axes = Axes.fit([*xs, 0.0], [*ys, 0.0], width=width, height=height, x_span=0.002, y_span=1.0)
    parts = [
        f'<svg class="scatter deltas" viewBox="0 0 {_num(width)} {_num(height)}" role="img" '
        'aria-labelledby="deltas-title" xmlns="http://www.w3.org/2000/svg">',
        '<title id="deltas-title">Änderung der Trefferquote gegen Änderung der Wahlbeteiligung '
        "je Wahlbezirk</title>",
        axes.clip_path("deltas-plot"),
        axes.grid(),
        axes.axis_lines(),
        axes.tick_labels(),
        axes.axis_titles("Änderung der Trefferquote", "Änderung der Wahlbeteiligung in Punkten"),
        '<g class="fits" clip-path="url(#deltas-plot)">',
        f'<line class="fit fit-all" x1="{_num(axes.sx(axes.x0))}" '
        f'y1="{_num(axes.sy(regression.slope * axes.x0 + regression.intercept))}" '
        f'x2="{_num(axes.sx(axes.x1))}" '
        f'y2="{_num(axes.sy(regression.slope * axes.x1 + regression.intercept))}"/>',
    ]
    # Die Nulllinien: links von x = 0 ist die Sichtbarkeit gefallen, unter y = 0 die Beteiligung
    parts.append(
        f'<line class="zero" x1="{_num(axes.sx(0.0))}" x2="{_num(axes.sx(0.0))}" '
        f'y1="{_num(axes.top)}" y2="{_num(axes.top + axes.plot_h)}"/>'
        f'<line class="zero" y1="{_num(axes.sy(0.0))}" y2="{_num(axes.sy(0.0))}" '
        f'x1="{_num(axes.left)}" x2="{_num(axes.left + axes.plot_w)}"/>'
    )
    parts.append('</g><g class="dots">')
    for row, x, y in zip(rows, xs, ys, strict=True):
        cx, cy = _num(axes.sx(x)), _num(axes.sy(y))
        title = (
            f"{row.id} {row.name}: Trefferquote {delta_label(row.d_rate)}, "
            f"Wahlbeteiligung {delta_label(row.d_turnout * 100.0, 1)} Punkte"
        )
        parts.append(
            f'<g class="dpoint" data-id="{row.id}" tabindex="0">'
            f"<title>{html.escape(title)}</title>"
            f'<circle class="hit" cx="{cx}" cy="{cy}" r="{_num(HIT_RADIUS)}"/>'
            f'<circle class="dot" cx="{cx}" cy="{cy}" r="{_num(DOT_RADIUS)}"/>'
            f'<text class="dot-label" x="{_num(axes.sx(x) + 6)}" y="{_num(axes.sy(y) - 6)}">'
            f"{row.id}</text>"
            "</g>"
        )
    parts.append("</g></svg>")
    return "".join(parts)
