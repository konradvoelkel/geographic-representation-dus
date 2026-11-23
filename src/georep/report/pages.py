"""Unterseiten neben ``index.html``: je Vorhaben eine Seite im Rahmen der Hauptseite.

Fundament F2 der Vorverarbeitung 2026-11 (``docs/plan-vorverarbeitung-2026-11.md``, § 2.4 und § 7).
``index.html`` hat bis zum Budget von 1,0 MB (Punkt 50) rund 60 KB Luft; neue Inhalte kommen darum
auf eigene Seiten, wie ``karte.html`` und die Periodenseiten. Eine Unterseite

* steht als ``Page`` in einem Beitrag (``georep.enrich.Contribution.pages``) und wird nur gebaut,
  wenn ``enabled(settings)`` gilt;
* hat ihre Vorlage unter ``templates/pages/<name>.html.j2``, daneben optional ``<name>.css`` und
  ``<name>.js``; der Rahmen (``templates/page.html.j2``) bindet dieselben Teilvorlagen ein wie die
  Hauptseite (``templates/frame/``), also dieselben Farben hell und dunkel, denselben
  Dokumentdialog, dieselbe Vorschau langer Tabellen;
* entsteht in einem eigenen Schritt ``page_<name>`` hinter ``report`` (``pipeline.build_steps``);
* steht auf der Hauptseite im Abschnitt „Weitere Auswertungen" (``ReportModel.pages``).

Die Vorlage der Seite bekommt ``model`` (der Rahmen: Stadt, Periode, Version, Zeitpunkt; dieselben
Namen wie auf der Hauptseite, damit die Teilvorlagen unverändert gelten) und ``data``, das Mapping
aus ``Page.data``. Links nach außen: nur die der Hauptseite und die, die der Aufrufer ausdrücklich
erlaubt.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import deal
from jinja2 import Environment

from georep.io import write_text
from georep.layout import Layout
from georep.report.model import PageLink, PeriodInfo, period_info
from georep.report.render import (
    ALLOWED_LINKS,
    CC0,
    GPL,
    REPOSITORY,
    environment,
    external_links,
)
from georep.settings import City, Settings

PAGE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
RESERVED = frozenset({"index", "karte", "vergleich"})  # Dateien, die es neben den Seiten schon gibt


def _valid_name(name: str) -> bool:
    return bool(PAGE_NAME.fullmatch(name)) and name not in RESERVED


def no_links(settings: Settings) -> frozenset[str]:
    """Eine Seite ohne eigene Links nach außen."""
    return frozenset()


@dataclass(frozen=True)
class Page:
    """Eine Unterseite: Datei ``<name>.html``, Titel, ein Satz, Eingaben, Daten für die Vorlage."""

    name: str
    title: str
    lead: str  # ein Satz: unter dem Titel der Seite und neben dem Link auf der Hauptseite
    inputs: Callable[[Layout, Settings], tuple[Path, ...]]  # was der Schritt liest (Stamp)
    data: Callable[[Layout, Settings], Mapping[str, object]]  # was die Vorlage als ``data`` sieht
    enabled: Callable[[Settings], bool] | None = (
        None  # None: immer, wenn der Beitrag im Register ist
    )
    # Links nach außen, die diese Seite zusätzlich zeigen darf (etwa das Ratsinformationssystem)
    links: Callable[[Settings], frozenset[str]] = no_links

    def __post_init__(self) -> None:
        if not _valid_name(self.name):
            raise ValueError(f"Seitenname {self.name!r}: [a-z][a-z0-9-]*, nicht {sorted(RESERVED)}")

    @property
    def template(self) -> str:
        return f"pages/{self.name}.html.j2"

    def output(self, layout: Layout) -> Path:
        return layout.site / f"{self.name}.html"


@dataclass(frozen=True)
class PageFrame:
    """Der Rahmen einer Unterseite; heißt in der Vorlage ``model`` wie auf der Hauptseite."""

    city: City
    period: PeriodInfo
    version: str
    commit: str | None
    generated_at: dt.datetime
    preview_rows: int


def pages_for(settings: Settings) -> list[Page]:
    """Die Unterseiten aller Beiträge, die für diese Settings gebaut werden, in Registerfolge.

    Import in der Funktion: die Beiträge bauen ``Page`` aus diesem Modul.
    """
    from georep.enrich import CONTRIBUTIONS

    found = [
        page
        for contribution in CONTRIBUTIONS
        for page in contribution.pages
        if page.enabled is None or page.enabled(settings)
    ]
    names = [page.name for page in found]
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        raise ValueError(f"Unterseiten doppelt im Register: {', '.join(twice)}")
    return found


def page_links(settings: Settings) -> tuple[PageLink, ...]:
    """Die Einträge des Abschnitts „Weitere Auswertungen" auf der Hauptseite."""
    return tuple(PageLink(f"{p.name}.html", p.title, p.lead) for p in pages_for(settings))


def page_frame(settings: Settings, *, now: dt.datetime, commit: str | None) -> PageFrame:
    from georep import __version__

    return PageFrame(
        city=settings.city,
        period=period_info(settings),
        version=__version__,
        commit=commit,
        generated_at=now,
        preview_rows=settings.report.table_preview_rows,
    )


def _assets(name: str) -> tuple[str, str]:
    """CSS und JavaScript der Seite aus ``templates/pages/``; fehlt eine Datei, ist es leer."""
    folder = resources.files("georep.report") / "templates" / "pages"
    css, js = folder / f"{name}.css", folder / f"{name}.js"
    return (
        css.read_text(encoding="utf-8") if css.is_file() else "",
        js.read_text(encoding="utf-8") if js.is_file() else "",
    )


def _only_allowed_links(
    frame: PageFrame,
    page: Page,
    data: Mapping[str, object],
    allowed: frozenset[str] = frozenset(),
    env: Environment | None = None,
    result: str = "",
) -> bool:
    """Nachbedingung von ``render_page``: nur die Links der Hauptseite und die ausdrücklich erlaubten.

    Eine benannte Funktion vor dem Decorator-Stapel, weil das deal-Plugin für mypy ``result`` als
    positionalen Parameter modelliert (CLAUDE.md, „Arbeitsweise", deal).
    """
    return set(external_links(result)) <= ALLOWED_LINKS | allowed


@deal.ensure(_only_allowed_links, message="nur die erlaubten Links nach außen")
@deal.post(lambda result: result.startswith("<!doctype html>") and 'lang="de"' in result)
def render_page(
    frame: PageFrame,
    page: Page,
    data: Mapping[str, object],
    allowed: frozenset[str] = frozenset(),
    env: Environment | None = None,
) -> str:
    """Die Unterseite als HTML; ``env`` ist die Testnaht für Vorlagen außerhalb des Pakets."""
    css, js = _assets(page.name)
    template = (env or environment()).get_template("page.html.j2")
    return template.render(
        model=frame,
        page=page,
        data=data,
        page_css=css,
        page_js=js,
        links={"repository": REPOSITORY, "cc0": CC0, "gpl": GPL},
    )


def build_page(
    layout: Layout, settings: Settings, page: Page, *, now: dt.datetime, commit: str | None
) -> str:
    """Der Schritt ``page_<name>``: Seite rendern, schreiben, eine Zeile für die Ausgabe."""
    html = render_page(
        page_frame(settings, now=now, commit=commit),
        page,
        page.data(layout, settings),
        page.links(settings),
    )
    target = layout.guard_writable(page.output(layout))
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text(target, html)
    return f"{target.name}, {len(html.encode('utf-8')) / 1024:.1f} KB"
