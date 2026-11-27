"""Die Karte der Startseite: Orte, Dokumente je Monat und Gremium, Grundkarte (plan-startseite, § 4).

Ein Punkt ist ein **Ort = (Begriff, Wahlbezirk)**, die Einheit, in der die Auswertung zählt: eine
Straße über sieben Wahlbezirke hat sieben Punkte, und ein Dokument steht an allen, wie es in allen
sieben zählt. Ein Begriff mit ``str.`` fällt auf seine Langform, wenn derselbe Wahlbezirk beide
kennt. Die Lage (§ 4.2, ``ART_*``): ein Ort aus Wikidata an seiner Koordinate im Wahlbezirk; eine
Straße am Punkt aus dem Paket der Straßenpunkte (Medoid der Hausnummern im Wahlbezirk, gerundet),
sonst auf der Fläche der Stimmbezirke des Wahlbezirks, die das Straßenverzeichnis für sie nennt,
sonst auf der Fläche des Wahlbezirks. Hausnummern aus den Texten werden nie zu Punkten.

``data/karte.json``, Format 1 (§ 4.5): ``start`` (erster Monat), ``months`` (Dokumente mit Treffer je
Monat, aus der Monatsreihe), ``gremien`` (``[kürzel, name, art]``), ``places`` (``[x, y, wahlbezirk,
art, name]``, auf die ``viewBox`` der Karte projiziert, ganze Zahlen) und ``docs`` (je Dokument in der
Folge von ``dokumente.json`` ``[monat, gremium, ort, …]``). Ein Dokument mit mehr als
``report.start.max_places`` Orten (ein Sammeldokument, § 4.3) trägt statt der Orte seine Wahlbezirke
als negative Zahlen: es steht als Zeile unter der Karte, nicht als Punkt, und zählt in den Flächen.
Dazu ``window`` (die Voreinstellung des Reglers), ``arten`` (die Arten der Gremien mit ihrem Wort)
und ``arts`` (der Satz zur Lage je Art). Die Zählung der Auswertung bleibt unberührt.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import deal
import polars as pl
import shapely
from shapely.geometry.base import BaseGeometry

from georep.geo import LONLAT, Precinct, read_canonical_precincts, transformer
from georep.layout import Layout
from georep.prep.bodies import KINDS, UNKNOWN
from georep.prep.streetpoints import normalize_street, street_point_files
from georep.report.charts import Classification, classify, legend, month_de
from georep.report.geometry import SIMPLIFY_M, Projection, bounds_of, fit
from georep.report.model import ReportModel, format_de
from georep.settings import Settings

START_WIDTH = 2000.0  # Breite der viewBox; eine ganze Zahl sind in beiden Städten rund zehn Meter
KARTE_NAME = "karte.json"
FORMAT = 1
ART_WIKIDATA, ART_HOUSES, ART_PRECINCTS, ART_DISTRICT = range(4)
ART_SENTENCES = (
    "Koordinate aus Wikidata",
    "Mitte der Hausnummern dieser Straße im Wahlbezirk",
    "ungefähr: Fläche der Stimmbezirke, die das Straßenverzeichnis für sie nennt",
    "ungefähr: Fläche des Wahlbezirks",
)
TOP_PLACES = 20  # „Als Liste" (§ 4.8)
UNKNOWN_BODY = ""  # Kürzel eines Dokuments ohne erkanntes Gremium
KIND_PLURALS = {
    "bezirksvertretung": "Bezirksvertretungen",
    "rat": "Rat",
    "ausschuss": "Ausschüsse",
    "beirat": "Beiräte",
    UNKNOWN: "Gremium unbekannt",
}
ZOOM_MARGIN = 0.06  # Rand um einen Stadtbezirk beim Vergrößern, als Anteil seiner Ausdehnung
PathPart = tuple[int, str, str]  # Nummer, Name, Pfad


@dataclass(frozen=True)
class Place:
    term: str  # die Langform des Begriffs, so wie das Wörterbuch ihn führt
    name: str  # der Name zum Zeigen, in der Schreibweise der Quelle
    district: int
    x: int
    y: int
    art: int


@dataclass(frozen=True)
class Body:
    code: str
    name: str
    kind: str


@dataclass(frozen=True)
class CityDistrict:
    number: int
    label: str
    view_box: tuple[int, int, int, int]
    path: str  # die Grenze, ein SVG-Pfad


@dataclass(frozen=True)
class StartMap:
    """Alles, was die Startseite und ``karte.json`` von der Karte brauchen."""

    width: int
    height: int
    start: dt.date  # erster Monat der Periode
    months: tuple[int, ...]  # Dokumente mit Treffer je Monat (Monatsreihe)
    bodies: tuple[Body, ...]
    places: tuple[Place, ...]
    docs: tuple[tuple[int, ...], ...]
    window: tuple[int, int]  # Voreinstellung: die letzten Monate bis zum neuesten Dokument
    max_places: int
    districts: tuple[PathPart, ...]
    city_district_of: Mapping[int, int]  # Wahlbezirk -> Stadtbezirk
    city_districts: tuple[CityDistrict, ...]
    labels: tuple[tuple[str, int, int], ...]
    period_ended: bool

    def month(self, index: int) -> dt.date:
        year, month = divmod(self.start.month - 1 + index, 12)
        return dt.date(self.start.year + year, month + 1, 1)

    def in_window(self, doc: Sequence[int]) -> bool:
        return self.window[0] <= doc[0] <= self.window[1]

    def window_label(self) -> str:
        first, last = (month_de(self.month(i)) for i in self.window)
        text = first if first == last else f"{first} bis {last}"
        if self.period_ended and self.window[1] == len(self.months) - 1:
            text += ", Ende der Wahlperiode"
        return text

    def district_counts(self) -> dict[int, int]:
        """Dokumente je Wahlbezirk im voreingestellten Zeitraum; ein Dokument einmal je Bezirk."""
        counts = {number: 0 for number, _, _ in self.districts}
        for doc in self.docs:
            if self.in_window(doc):
                for number in doc_districts(doc, self.places):
                    if number in counts:
                        counts[number] += 1
        return counts

    def place_counts(self) -> list[int]:
        counts = [0] * len(self.places)
        for doc in self.docs:
            if self.in_window(doc) and len(doc) > 2 and doc[2] >= 0:
                for place in doc[2:]:
                    counts[place] += 1
        return counts

    def top(self) -> list[tuple[Place, int]]:
        """Die Orte mit den meisten Dokumenten im voreingestellten Zeitraum, höchstens 20."""
        counts = self.place_counts()
        ranked = sorted(
            (i for i, n in enumerate(counts) if n),
            key=lambda i: (-counts[i], self.places[i].name, self.places[i].district),
        )
        return [(self.places[i], counts[i]) for i in ranked[:TOP_PLACES]]

    def window_documents(self) -> int:
        return sum(1 for doc in self.docs if self.in_window(doc))

    def window_places(self) -> int:
        return sum(1 for n in self.place_counts() if n)


def doc_districts(doc: Sequence[int], places: Sequence[Place]) -> set[int]:
    """Die Wahlbezirke eines Eintrags von ``docs``: aus seinen Orten oder, negativ, direkt."""
    if len(doc) > 2 and doc[2] < 0:
        return {-value for value in doc[2:]}
    return {places[p].district for p in doc[2:]}


def point_radius(count: int) -> float:
    """Radius eines Kreises in Pixeln, Fläche proportional zur Zahl (wie ``radius`` in karte.js)."""
    return 2.5 + 1.2 * math.sqrt(count)


# --- Orte -----------------------------------------------------------------------------------------


@deal.pure
def canonical(term: str, known: frozenset[str]) -> str:
    """Die Langform eines Begriffs mit ``str.``, wenn derselbe Wahlbezirk sie kennt; sonst er selbst."""
    if "str." not in term:
        return term
    long = term.replace("str.", "straße")
    return long if long in known else term


def place_documents(
    terms: Mapping[str, Sequence[int]], dictionary: Mapping[int, frozenset[str]]
) -> dict[tuple[str, int], set[int]]:
    """Je Ort (Langform, Wahlbezirk) die Indizes in ``dokumente.json`` der Dokumente, die ihn nennen."""
    by_term: dict[str, list[int]] = {}
    for district, words in dictionary.items():
        for word in words:
            by_term.setdefault(word, []).append(district)
    found: dict[tuple[str, int], set[int]] = {}
    for term, indices in terms.items():
        for district in by_term.get(term, ()):
            key = (canonical(term, dictionary[district]), district)
            found.setdefault(key, set()).update(indices)
    return found


@dataclass(frozen=True)
class Locator:
    """Woher die Lage eines Orts kommt (§ 4.2), alles im Arbeits-CRS."""

    pois: Mapping[tuple[str, int], tuple[float, float, str]]  # (Begriff, Wahlbezirk) -> x, y, Name
    street_points: Mapping[tuple[str, int], tuple[float, float]]
    street_names: Mapping[tuple[str, int], str]
    street_precincts: Mapping[str, frozenset[str]]  # Straße (Langform) -> Stimmbezirke
    precincts: Mapping[str, Precinct]
    districts: Mapping[int, BaseGeometry]

    def locate(self, term: str, district: int) -> tuple[float, float, int, str]:
        """``(x, y, art, name)`` eines Orts."""
        key = (term, district)
        if key in self.pois:
            x, y, poi_name = self.pois[key]
            return x, y, ART_WIKIDATA, poi_name
        name = self.street_names.get(key, term)
        if key in self.street_points:
            x, y = self.street_points[key]
            return x, y, ART_HOUSES, name
        ids = sorted(
            i
            for i in self.street_precincts.get(normalize_street(term), frozenset())
            if i in self.precincts and self.precincts[i].district_id == district
        )
        if ids:
            point = shapely.unary_union(
                [self.precincts[i].geometry for i in ids]
            ).representative_point()
            return float(point.x), float(point.y), ART_PRECINCTS, name
        point = self.districts[district].representative_point()
        return float(point.x), float(point.y), ART_DISTRICT, name


def _locator(
    layout: Layout,
    settings: Settings,
    shapes: Mapping[int, BaseGeometry],
) -> Locator:
    """Die Quellen der Lage aus dem Lauf: Orte, Paket der Straßenpunkte, Straßenverzeichnis."""
    working = settings.geo.working_crs
    source = (
        layout if settings.period.dictionary == "own" else layout.for_profile(settings.base_profile)
    )
    pois: dict[tuple[str, int], tuple[float, float, str]] = {}
    if layout.pois_table.is_file():
        frame = pl.read_parquet(layout.pois_table, columns=["label", "wahlkreis_id", "lon", "lat"])
        frame = frame.sort("label", "wahlkreis_id", "lon", "lat")
        xs, ys = transformer(LONLAT, working).transform(
            frame.get_column("lon").to_numpy(), frame.get_column("lat").to_numpy()
        )
        for (label, district, _, _), x, y in zip(frame.iter_rows(), xs, ys, strict=True):
            key = (str(label).strip().lower(), int(district))
            pois.setdefault(key, (float(x), float(y), str(label).strip()))
    names: dict[tuple[str, int], str] = {}
    if layout.streets_by_district.is_file():
        for district, words in pl.read_parquet(layout.streets_by_district).iter_rows():
            for word in words or ():
                names.setdefault((str(word).strip().lower(), int(district)), str(word).strip())
    points: dict[tuple[str, int], tuple[float, float]] = {}
    files = street_point_files(layout)
    if files.points.is_file():
        for street, district, x, y in (
            pl.read_parquet(files.points).select("strasse", "wahlkreis_id", "x", "y").iter_rows()
        ):
            points[(str(street), int(district))] = (float(x), float(y))
    street_precincts: dict[str, set[str]] = {}
    if source.streets.is_file():
        for row in json.loads(source.streets.read_text(encoding="utf-8")):
            for street in row.get("straßen", ()):
                street_precincts.setdefault(normalize_street(str(street)), set()).add(
                    str(row["stimmbezirks_id"])
                )
    geojson = (
        source.precincts_geojson if source.precincts_geojson.is_file() else layout.precincts_geojson
    )
    precincts = (
        {p.precinct_id: p for p in read_canonical_precincts(geojson, working)}
        if geojson.is_file()
        else {}
    )
    return Locator(
        pois,
        points,
        names,
        {k: frozenset(v) for k, v in street_precincts.items()},
        precincts,
        shapes,
    )


# --- Grundkarte -----------------------------------------------------------------------------------


def _ring_path(coords: Sequence[tuple[float, float]], projection: Projection) -> str:
    points: list[tuple[int, int]] = []
    for x, y in coords:
        px, py = projection.point(x, y)
        point = (round(px), round(py))
        if not points or point != points[-1]:
            points.append(point)
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(set(points)) < 3:
        return ""
    steps = " ".join(
        f"{b[0] - a[0]} {b[1] - a[1]}" for a, b in zip(points, points[1:], strict=False)
    )
    return f"M{points[0][0]} {points[0][1]}l{steps}z".replace(" -", "-")


def _polygons(geometry: BaseGeometry) -> list[shapely.Polygon]:
    if isinstance(geometry, shapely.Polygon):
        return [geometry]
    return [g for g in getattr(geometry, "geoms", []) if isinstance(g, shapely.Polygon)]


@deal.post(lambda result: result == "" or (result.startswith("M") and result.endswith("z")))
def compact_path(geometry: BaseGeometry, projection: Projection) -> str:
    """Ein ``d``-Attribut aus ganzen Zahlen mit relativen Schritten; Löcher als eigene Ringe.

    Die Hauptkarte schreibt zwei Nachkommastellen absolut (``geometry.svg_path``); auf der
    Startseite zählt jedes Byte (150 000), und eine ganze Zahl der viewBox von 2 000 sind rund zehn
    Meter, weniger als die Vereinfachung um 15 m.
    """
    parts = [
        _ring_path(list(ring.coords), projection)
        for polygon in _polygons(geometry)
        for ring in (polygon.exterior, *polygon.interiors)
    ]
    return "".join(part for part in parts if part)


def main_city_district(rows: pl.DataFrame) -> dict[int, int]:
    """Je Wahlbezirk der Stadtbezirk mit dem größten Anteil (``wahlbezirke_stadtbezirke``).

    Ein Wahlbezirk in zwei Stadtbezirken (Düsseldorf: 40 in 9 und 10) zählt ganz zum größeren; die
    Grenzen der Stadtbezirke auf der Startkarte folgen darum den Wahlbezirken.
    """
    found: dict[int, int] = {}
    best: dict[int, float] = {}
    for district, city_district, weight in (
        rows.select("wahlkreis_id", "stadtbezirk", "gewicht")
        .sort("wahlkreis_id", "stadtbezirk")
        .iter_rows()
    ):
        if district not in best or float(weight) > best[district]:
            found[int(district)], best[int(district)] = int(city_district), float(weight)
    return found


def _box(
    bounds: tuple[float, float, float, float], aspect: float, projection: Projection
) -> tuple[int, int, int, int]:
    """Das Rechteck der viewBox um ``bounds`` (Arbeits-CRS), mit Rand, im Seitenverhältnis der Karte."""
    (x0, y0), (x1, y1) = (
        projection.point(bounds[0], bounds[3]),
        projection.point(bounds[2], bounds[1]),
    )
    w, h = (x1 - x0) * (1 + 2 * ZOOM_MARGIN), (y1 - y0) * (1 + 2 * ZOOM_MARGIN)
    if w / h < aspect:
        w = h * aspect
    else:
        h = w / aspect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return (round(cx - w / 2), round(cy - h / 2), math.ceil(w), math.ceil(h))


def _city_districts(
    settings: Settings,
    precincts: Sequence[Precinct],
    city_district_of: Mapping[int, int],
    projection: Projection,
    aspect: float,
) -> tuple[CityDistrict, ...]:
    by_unit: dict[int, list[BaseGeometry]] = {}
    for precinct in precincts:
        unit = city_district_of.get(precinct.district_id)
        if unit is not None:
            by_unit.setdefault(unit, []).append(precinct.geometry)
    names = settings.report.start.city_district_names
    found = []
    for unit, parts in sorted(by_unit.items()):
        merged = shapely.unary_union(parts).simplify(SIMPLIFY_M, preserve_topology=True)
        found.append(
            CityDistrict(
                unit,
                names.get(str(unit), f"Stadtbezirk {unit}"),
                _box(tuple(float(v) for v in merged.bounds), aspect, projection),  # type: ignore[arg-type]
                compact_path(merged, projection),
            )
        )
    return tuple(found)


# --- Zusammenbau ------------------------------------------------------------------------------------


def month_index(start: dt.date, day: dt.date) -> int:
    return (day.year - start.year) * 12 + day.month - start.month


@deal.pre(lambda newest, months, span: months >= 1 and span >= 1)
@deal.post(lambda result: 0 <= result[0] <= result[1])
def default_window(newest: int, months: int, span: int) -> tuple[int, int]:
    """Die letzten ``span`` Monate bis zum Monat des neuesten Dokuments, innerhalb der Periode."""
    last = min(max(newest, 0), months - 1)
    return (max(0, last - span + 1), last)


def _bodies(model: ReportModel, codes: set[str]) -> tuple[Body, ...]:
    """Die Gremien der Dokumente mit Treffer: Art in der Folge von ``KINDS``, darin nach Namen."""
    order = {kind: i for i, kind in enumerate(KINDS)}
    known = {row.code: row for row in model.bodies}
    found = [
        Body(
            code,
            known[code].label if code in known else (code or "ohne erkanntes Gremium"),
            known[code].kind if code in known else UNKNOWN,
        )
        for code in codes
    ]

    def key(body: Body) -> tuple[int, int, str]:
        row = known.get(body.code)
        number = row.city_district if row is not None and row.city_district is not None else 0
        return (order.get(body.kind, len(order)), number, body.name)

    return tuple(sorted(found, key=key))


def build_start_map(
    layout: Layout,
    settings: Settings,
    model: ReportModel,
    precincts: Sequence[Precinct],
    shapes: Mapping[int, BaseGeometry],
    terms: Mapping[str, Sequence[int]],
    order: Sequence[str],
) -> StartMap:
    """Die Karte aus dem Lauf: Orte und ihre Lage, Dokumente, Grundkarte (§ 4).

    ``terms`` und ``order`` sind die von ``dokumente.json`` (je Begriff die Indizes, die Korpus-IDs
    in der Folge der Datei); ``precincts`` die kanonischen Stimmbezirke der gerechneten Wahlbezirke,
    ``shapes`` ihre vereinfachten Flächen wie auf ``details.html``.
    """
    dictionary = {
        int(w): frozenset(words or ())
        for w, words in pl.read_parquet(layout.dictionary).iter_rows()
    }
    found = place_documents(terms, dictionary)
    locator = _locator(layout, settings, shapes)
    projection = fit(bounds_of(shapes), START_WIDTH)
    places: list[Place] = []
    for term, district in sorted(found, key=lambda key: (key[1], key[0])):
        x, y, art, name = locator.locate(term, district)
        px, py = projection.point(x, y)
        places.append(Place(term, name, district, round(px), round(py), art))
    index = {(p.term, p.district): i for i, p in enumerate(places)}
    doc_places: list[set[int]] = [set() for _ in order]
    for key, indices in found.items():
        for i in indices:
            doc_places[i].add(index[key])

    corpus = pl.read_parquet(layout.corpus, columns=["id", "date"])
    dates = dict(corpus.iter_rows())
    bodies_of: dict[str, str] = {}
    if layout.papers_bodies.is_file():
        frame = pl.read_parquet(layout.papers_bodies, columns=["id", "gremium"])
        bodies_of = {str(i): str(g) if g else UNKNOWN_BODY for i, g in frame.iter_rows()}
    dated = [(row.month, row.with_hits) for row in model.timeline if row.month is not None]
    start = min(m for m, _ in dated) if dated else model.stand.period_start.replace(day=1)
    bodies = _bodies(model, {bodies_of.get(paper, UNKNOWN_BODY) for paper in order})
    body_index = {body.code: i for i, body in enumerate(bodies)}
    rows: list[tuple[int, ...]] = []
    for paper, at in zip(order, doc_places, strict=True):
        day = dates.get(paper)
        month = month_index(start, day) if day is not None else -1
        body = body_index[bodies_of.get(paper, UNKNOWN_BODY)]
        if len(at) > settings.report.start.max_places:
            rows.append((month, body, *(-d for d in sorted({places[p].district for p in at}))))
        else:
            rows.append((month, body, *sorted(at)))
    newest = max((row[0] for row in rows), default=0)
    # Die Monatsreihe kann einen Monat ohne Dokument auslassen; die Leiste braucht jeden
    span = max([newest, *(month_index(start, m) for m, _ in dated)]) + 1
    counts = [0] * span
    for day, hits in dated:
        counts[month_index(start, day)] = hits
    months = tuple(counts)

    names = {row.id: row.name for row in model.districts}
    districts = tuple(
        (number, names.get(number, ""), compact_path(shape, projection))
        for number, shape in sorted(shapes.items())
    )
    city_district_of = (
        main_city_district(pl.read_parquet(layout.district_units))
        if layout.district_units.is_file()
        else {}
    )
    aspect = projection.width / projection.height
    city_districts = _city_districts(settings, precincts, city_district_of, projection, aspect)
    files = street_point_files(layout)
    if files.labels.is_file():
        label_rows = pl.read_parquet(files.labels).select("name", "x", "y").iter_rows()
        labels = tuple(
            (str(name), *(round(v) for v in projection.point(float(x), float(y))))
            for name, x, y in label_rows
        )
    else:
        labels = tuple(
            (c.label, c.view_box[0] + c.view_box[2] // 2, c.view_box[1] + c.view_box[3] // 2)
            for c in city_districts
        )
    return StartMap(
        width=round(projection.width),
        height=math.ceil(projection.height),
        start=start,
        months=months,
        bodies=bodies,
        places=tuple(places),
        docs=tuple(rows),
        window=default_window(newest, len(months), settings.report.start.months),
        max_places=settings.report.start.max_places,
        districts=districts,
        city_district_of=city_district_of,
        city_districts=city_districts,
        labels=labels,  # type: ignore[arg-type]
        period_ended=model.stand.period_end is not None,
    )


def karte_payload(
    start_map: StartMap, *, version: str, generated_at: dt.datetime
) -> dict[str, object]:
    """``data/karte.json`` im Format 1 (§ 4.5)."""
    kinds = list(dict.fromkeys(body.kind for body in start_map.bodies))
    return {
        "format": FORMAT,
        "version": version,
        "generated_at": generated_at.isoformat(),
        "start": start_map.start.strftime("%Y-%m"),
        "window": list(start_map.window),
        "ended": start_map.period_ended,
        "max_places": start_map.max_places,
        "months": list(start_map.months),
        "arts": list(ART_SENTENCES),
        "arten": [[kind, KIND_PLURALS.get(kind, kind)] for kind in kinds],
        "gremien": [[b.code, b.name, b.kind] for b in start_map.bodies],
        "places": [[p.x, p.y, p.district, p.art, p.name] for p in start_map.places],
        "docs": [list(doc) for doc in start_map.docs],
    }


def choropleth(start_map: StartMap) -> tuple[Classification, dict[int, int]]:
    """Die Klassen der Flächen im voreingestellten Zeitraum, wie ``charts.classify`` (§ 4.7)."""
    counts = start_map.district_counts()
    return classify({k: float(v) for k, v in counts.items()}), counts


def count_label(value: float) -> str:
    return format_de(value, 0) if float(value).is_integer() else format_de(value, 1)


def choropleth_legend(classes: Classification) -> tuple[tuple[int, str], ...]:
    return tuple((e.klass, e.label) for e in legend(classes, count_label))
