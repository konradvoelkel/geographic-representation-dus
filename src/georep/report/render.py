"""Rendering der Berichtsseite: Jinja2 mit Autoescape, eine Vorlage im Paket, alles inline.

Die Seite ist eine einzige ``index.html`` ohne externe Ressourcen; die einzigen Links nach außen
stehen in ``ALLOWED_LINKS``, und die Nachbedingung von ``render_report`` prüft das. SVGs kommen
fertig aus ``georep.report.charts`` (dort schon escaped) und werden mit ``|safe`` eingefügt.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable

import deal
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from georep.errors import SchemaError
from georep.report.charts import (
    LegendEntry,
    delta_label,
    month_de,
    percent_signed_label,
    points_label,
    ratio_label,
)
from georep.report.model import ReportModel, format_de, percent_de
from georep.report.search import search_payload

REPOSITORY = "https://github.com/konradvoelkel/geographic-representation-dus"
THESIS = "https://github.com/lubar102/geographic-representation-dus"
ARCHITECTURE = f"{REPOSITORY}/blob/main/docs/architecture.md"
DECISIONS = f"{REPOSITORY}/blob/main/docs/decisions.md"
OSM_COPYRIGHT = "https://www.openstreetmap.org/copyright"
WIKIDATA = "https://www.wikidata.org/"
WIKIPEDIA = "https://de.wikipedia.org/"
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/deed.de"
GPL = "https://www.gnu.org/licenses/gpl-3.0.de.html"
ODBL = "https://opendatacommons.org/licenses/odbl/1-0/"
# Option 01: die Links, die auf jeder Stadtseite stehen. Portal, Ratsinformationssystem und die
# Lizenzen der Daten sind je Stadt verschieden; sie stehen im Profil und kommen über
# ``model_links`` hinzu, sind also per Konstruktion erlaubt — Links aus Daten weiterhin nicht.
ALLOWED_LINKS = frozenset(
    {
        REPOSITORY,
        THESIS,
        ARCHITECTURE,
        DECISIONS,
        OSM_COPYRIGHT,
        WIKIDATA,
        WIKIPEDIA,
        CC0,
        GPL,
        ODBL,
    }
)
_EXTERNAL = re.compile(r'(?:href|src)="(https?://[^"]*)"')


def model_links(model: ReportModel) -> frozenset[str]:
    """Links, die aus den Settings kommen und darum nicht als Konstante in ``ALLOWED_LINKS`` stehen.

    Option 01: das Ratsinformationssystem und die Quellen der Stadt mit ihren Lizenzen.
    Option 03: Datensatzseite und Lizenz der Fremddaten; eine andere Stadt nennt andere, und die
    Nachbedingung von ``render_report`` soll trotzdem greifen.
    Punkt 47: die Links der Literaturübersicht. Sie stehen in ``report/literatur.toml`` und im
    Profil, also in Dateien des Pakets -- per Konstruktion erlaubt wie die Quellen, und keine
    Zitation zwingt eine Konstante mit einem Ortsnamen in den Code.
    """
    found = {model.ris_url} | {
        url for source in model.sources for url in (source.url, source.license_url)
    }
    found |= {link for entry in model.literature for link in entry.links}
    if model.derived is not None:
        found |= {model.derived.url, model.derived.license_url}
    return frozenset(u for u in found if u)


# Die Leaflet-Variante (karte.html) ist die eine Ausnahme von „keine Fremdressourcen": Leaflet 1.9.4
# per SHA-256 gepinnt (Subresource Integrity, Hashes am 2026-10-11 aus den Dateien berechnet und
# gleich den offiziellen), Kacheln von OpenStreetMap mit Namensnennung.
LEAFLET = {
    "css": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "css_sri": "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=",
    "js": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "js_sri": "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
}
MAP_ALLOWED_LINKS = frozenset({LEAFLET["css"], LEAFLET["js"], OSM_COPYRIGHT, REPOSITORY})
LIGHT_RAMP = ("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b")  # wie --q0 bis --q4 hell


@dataclass(frozen=True)
class Visuals:
    """Die fertigen SVGs und Legenden, getrennt vom Modell, weil sie Geometrie brauchen."""

    map_svg: str
    scatter_svg: str | None  # None: keine Regression zur Periode (Option 07)
    rate_legend: Sequence[LegendEntry]
    turnout_legend: Sequence[LegendEntry]
    simplify_m: float
    pois: int  # gezeichnete Orte; 0 blendet den Schalter aus
    # Neue Kennzahlen stehen mit Default am Ende: leer blendet Radio und Legende aus (Option 05)
    bodies_legend: Sequence[LegendEntry] = ()
    # Option 03: je Term des Hauptmodells (Beschriftung, SVG); leer ohne Kontextdaten
    partial_svgs: Sequence[tuple[str, str]] = ()
    party_maps_svg: str = ""  # Option 04: leer, solange der Schritt ``parties`` nicht lief
    # Option 02: das Streudiagramm der Änderungen; leer, wenn die Seite nur eine Periode zeigt
    delta_svg: str = ""
    bars_svg: str = ""  # Option 07: Balken je Monat; leer = kein Abschnitt „Je Monat"
    # Punkt 46: die drei Normierungen der Karte; leer, solange der Schritt ``metrics`` fehlt
    hits_legend: Sequence[LegendEntry] = ()
    per_term_legend: Sequence[LegendEntry] = ()
    deviation_legend: Sequence[LegendEntry] = ()
    # Punkt 46: die beiden divergierenden Legenden des Parteiabschnitts
    party_points_legend: Sequence[LegendEntry] = ()
    party_ratio_legend: Sequence[LegendEntry] = ()


def date_de(value: dt.date) -> str:
    return f"{value.day:02d}.{value.month:02d}.{value.year}"


def datetime_de(value: dt.datetime) -> str:
    return f"{date_de(value.date())}, {value:%H:%M} {value.tzname() or 'UTC'}"


def kib(size: int) -> str:
    """Dateigröße in KB (1000 Byte) mit einer Nachkommastelle, wie der Finder sie zeigt."""
    return f"{format_de(size / 1000, 1)}{chr(0x202F)}KB"


def environment() -> Environment:
    env = Environment(
        loader=PackageLoader("georep.report", "templates"),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["num"] = format_de
    env.filters["pct"] = percent_de
    env.filters["date_de"] = date_de
    env.filters["datetime_de"] = datetime_de
    env.filters["kib"] = kib
    env.filters["delta"] = delta_label  # Option 02: Änderung mit Vorzeichen
    env.filters["month_de"] = month_de  # Option 07: „Oktober 2025" in der Monatstabelle
    # Punkt 46: die Beschriftungen der Varianten „relativ zum Mittel"
    env.filters["signed_pct"] = percent_signed_label
    env.filters["points"] = points_label
    env.filters["ratio"] = ratio_label
    return env


def external_links(html: str) -> list[str]:
    return _EXTERNAL.findall(html)


@dataclass(frozen=True)
class Section:
    """Ein Abschnitt der Seite: ``templates/sections/NN-name.html.j2`` mit optionalem CSS und JS."""

    number: int
    name: str
    template: str  # Pfad relativ zum Vorlagenordner, für ``{% include %}``
    css: str
    js: str


_SECTION_FILE = re.compile(r"^(\d{2})-([a-z][a-z0-9-]*)\.html\.j2$")


def _numbered_in_order(result: tuple[Section, ...]) -> bool:
    numbers = [s.number for s in result]
    return len(result) > 0 and numbers == sorted(numbers) and len(set(numbers)) == len(numbers)


@deal.post(_numbered_in_order, message="Abschnitte in Nummernfolge, jede Nummer einmal")
@deal.raises(SchemaError)
def sections(folder: Traversable | None = None) -> tuple[Section, ...]:
    """Die Abschnitte der Seite aus ``templates/sections/`` in Nummernfolge.

    Eine Option fügt einen Abschnitt als neue Datei ein; die Nummer bestimmt die Stelle
    (docs/plans/00-synergien.md, § 5.1). Ein ``.css`` oder ``.js`` ohne Vorlage gleichen Namens ist
    ein Fehler, damit kein Stil ins Leere zeigt. ``folder`` ist die Testnaht.
    """
    if folder is None:
        folder = resources.files("georep.report") / "templates" / "sections"
    names = sorted(entry.name for entry in folder.iterdir())
    found: list[Section] = []
    for name in names:
        match = _SECTION_FILE.match(name)
        if match is None:
            continue
        stem = name.removesuffix(".html.j2")
        css = folder / f"{stem}.css"
        js = folder / f"{stem}.js"
        found.append(
            Section(
                int(match.group(1)),
                match.group(2),
                f"sections/{name}",
                css.read_text(encoding="utf-8") if css.is_file() else "",
                js.read_text(encoding="utf-8") if js.is_file() else "",
            )
        )
    stems = {s.template.removeprefix("sections/").removesuffix(".html.j2") for s in found}
    orphans = [
        n
        for n in names
        if (n.endswith(".css") or n.endswith(".js")) and n.rsplit(".", 1)[0] not in stems
    ]
    if orphans:
        raise SchemaError(f"Abschnittsdateien ohne Vorlage: {orphans}")
    return tuple(found)


def _json_for_script(data: object) -> str:
    """JSON für ein ``<script type="application/json">``: kein ``<`` im Text, als ``\\u003c`` kodiert.

    ``</`` allein zu maskieren reicht nicht: ``<!--`` gefolgt von ``<script`` versetzt den
    HTML-Tokenizer in „script data double escaped", und das echte ``</script>`` wird verschluckt
    (Review 2026-10-12). ``\\u003c`` ist gültiges JSON und für den Tokenizer unsichtbar.
    """
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


@deal.post(lambda result: result.startswith("<!doctype html>") and 'lang="de"' in result)
@deal.ensure(
    lambda model, visuals, result: (
        set(external_links(result)) <= ALLOWED_LINKS | model_links(model)
    ),
    message="nur die erlaubten Links nach außen, keine externen Ressourcen",
)
def render_report(model: ReportModel, visuals: Visuals) -> str:
    template = environment().get_template("report.html.j2")
    parts = sections()
    return template.render(
        model=model,
        visuals=visuals,
        sections=[s.template for s in parts],
        section_css="".join(s.css for s in parts if s.css),
        section_js="\n".join(s.js for s in parts if s.js),
        tables=list(dict.fromkeys(column.table for column in model.columns)),
        search_json=_json_for_script(search_payload(model.search)),
        links={
            "repository": REPOSITORY,
            "thesis": THESIS,
            "architecture": ARCHITECTURE,
            "decisions": DECISIONS,
            # Option 01: das Ratsinformationssystem nennt das Profil, nicht der Code
            "ris": model.ris_url,
            "osm": OSM_COPYRIGHT,
            "wikidata": WIKIDATA,
            "wikipedia": WIKIPEDIA,
            "cc0": CC0,
            "gpl": GPL,
            "odbl": ODBL,
        },
    )


@deal.post(lambda result: result.startswith("<!doctype html>") and 'lang="de"' in result)
@deal.post(
    lambda result: set(external_links(result)) <= MAP_ALLOWED_LINKS,
    message="nur Leaflet (gepinnt) und OpenStreetMap nach außen",
)
def render_map(
    model: ReportModel,
    districts: Mapping[str, object],
    places: Mapping[str, object],
    legend: Sequence[LegendEntry],
) -> str:
    """Die zweite Datei ``karte.html``: dieselben Flächen auf OpenStreetMap-Kacheln, braucht Netz."""
    template = environment().get_template("map.html.j2")
    return template.render(
        model=model,
        leaflet=LEAFLET,
        links={"osm": OSM_COPYRIGHT, "repository": REPOSITORY},
        districts_json=_json_for_script(districts),
        pois_json=_json_for_script(places),
        colors_json=_json_for_script(list(LIGHT_RAMP)),
        legend_json=_json_for_script([[entry.klass, entry.label] for entry in legend]),
    )
