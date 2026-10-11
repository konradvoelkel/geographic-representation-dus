"""Rendering der Berichtsseite: Jinja2 mit Autoescape, eine Vorlage im Paket, alles inline.

Die Seite ist eine einzige ``index.html`` ohne externe Ressourcen; die einzigen Links nach außen
stehen in ``ALLOWED_LINKS``, und die Nachbedingung von ``render_report`` prüft das. SVGs kommen
fertig aus ``georep.report.charts`` (dort schon escaped) und werden mit ``|safe`` eingefügt.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from dataclasses import dataclass

import deal
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from georep.report.charts import LegendEntry
from georep.report.model import ReportModel, format_de, percent_de

REPOSITORY = "https://github.com/konradvoelkel/geographic-representation-dus"
THESIS = "https://github.com/lubar102/geographic-representation-dus"
ARCHITECTURE = f"{REPOSITORY}/blob/main/docs/architecture.md"
OPENDATA = "https://opendata.duesseldorf.de/"
OPARL = "https://ris-oparl.itk-rheinland.de/"
OSM_COPYRIGHT = "https://www.openstreetmap.org/copyright"
WIKIDATA = "https://www.wikidata.org/"
WIKIPEDIA = "https://de.wikipedia.org/"
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/deed.de"
ODBL = "https://opendatacommons.org/licenses/odbl/1-0/"
# Lizenzen des Open-Data-Portals, nachgesehen am 2026-10-11 auf den Datensatzseiten:
# Ratswahl 2025 „Datenlizenz Deutschland Namensnennung 2.0", Stimmbezirkseinteilung
# „Datenlizenz Deutschland – Zero – Version 2.0".
DL_DE_BY = "https://www.govdata.de/dl-de/by-2-0"
DL_DE_ZERO = "https://www.govdata.de/dl-de/zero-2-0"
ALLOWED_LINKS = frozenset(
    {
        REPOSITORY,
        THESIS,
        ARCHITECTURE,
        OPENDATA,
        OPARL,
        OSM_COPYRIGHT,
        WIKIDATA,
        WIKIPEDIA,
        CC0,
        ODBL,
        DL_DE_BY,
        DL_DE_ZERO,
    }
)
_EXTERNAL = re.compile(r'(?:href|src)="(https?://[^"]*)"')


@dataclass(frozen=True)
class Visuals:
    """Die fertigen SVGs und Legenden, getrennt vom Modell, weil sie Geometrie brauchen."""

    map_svg: str
    scatter_svg: str
    rate_legend: Sequence[LegendEntry]
    turnout_legend: Sequence[LegendEntry]
    simplify_m: float
    pois: int  # gezeichnete Orte; 0 blendet den Schalter aus


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
    return env


def external_links(html: str) -> list[str]:
    return _EXTERNAL.findall(html)


@deal.post(lambda result: result.startswith("<!doctype html>") and 'lang="de"' in result)
@deal.post(
    lambda result: set(external_links(result)) <= ALLOWED_LINKS,
    message="nur die erlaubten Links nach außen, keine externen Ressourcen",
)
def render_report(model: ReportModel, visuals: Visuals) -> str:
    template = environment().get_template("report.html.j2")
    return template.render(
        model=model,
        visuals=visuals,
        tables=list(dict.fromkeys(column.table for column in model.columns)),
        links={
            "repository": REPOSITORY,
            "thesis": THESIS,
            "architecture": ARCHITECTURE,
            "opendata": OPENDATA,
            "oparl": OPARL,
            "osm": OSM_COPYRIGHT,
            "wikidata": WIKIDATA,
            "wikipedia": WIKIPEDIA,
            "cc0": CC0,
            "odbl": ODBL,
            "dl_de_by": DL_DE_BY,
            "dl_de_zero": DL_DE_ZERO,
        },
    )
