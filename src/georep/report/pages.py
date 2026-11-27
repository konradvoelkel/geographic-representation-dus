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

**Abschnitte aus fremden Beiträgen** (Vorarbeit V1, ``docs/plan-zeigen-2026-11.md``, § 4): ein
Beitrag hängt mit ``PageSection`` (``Contribution.sections``) einen Abschnitt an die Unterseite eines
anderen, etwa 26 an ``vorgaenge.html`` von 14. Die Seite zeigt ihre fremden Abschnitte nach ihrem
eigenen Inhalt, nach Rang, dann Name; jede Vorlage sieht ``data`` aus ihrem eigenen
``PageSection.data``. Der Schritt ``page_<name>`` liest die Eingaben der Abschnitte mit, ihre Links
nach außen sind erlaubt. Ein Ziel, das keine registrierte Seite ist, und ein Rang oder Name, den zwei
Abschnitte derselben Seite teilen, sind ein ``SectionError``; wird die Zielseite in einem Profil nicht
gebaut, entfällt der Abschnitt mit einer Zeile im Log.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import deal
from jinja2 import Environment, TemplateNotFound
from loguru import logger

from georep.errors import GeorepError
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


class SectionError(GeorepError):
    """Das Register der Abschnitte ist falsch: ein Ziel ohne Seite, ein Rang oder Name doppelt."""


@dataclass(frozen=True)
class PageSection:
    """Ein Abschnitt auf der Unterseite eines anderen Beitrags (Vorarbeit V1, F2-Nachzug).

    ``page`` ist der Name der Zielseite (``Page.name``), ``name`` der des Abschnitts, eindeutig je
    Seite. Die Vorlage liegt unter ``templates/pages/<page>/<name>.html.j2``, daneben optional
    ``<name>.css`` und ``<name>.js``; sie hängt an ihren Daten und beginnt darum mit
    ``{% if data.… %}``. ``rank`` ist die Stelle auf der Seite: kleiner zuerst, bei gleichem Rang
    der Name. Ein Rang ist je Seite eindeutig (``section_problems``); der Name als zweite Stufe
    hält die Folge auch dort fest, wo diese Prüfung nicht vorausgeht (``order_sections`` allein,
    mit abgeschalteten Verträgen).
    """

    page: str
    name: str
    rank: int
    inputs: Callable[[Layout, Settings], tuple[Path, ...]]  # liest der Schritt der Seite mit
    data: Callable[[Layout, Settings], Mapping[str, object]]  # was die Vorlage als ``data`` sieht
    enabled: Callable[[Settings], bool] | None = None  # None: immer, wenn die Zielseite gebaut wird
    links: Callable[[Settings], frozenset[str]] = no_links  # erlaubt die Zielseite zusätzlich

    def __post_init__(self) -> None:
        if not _valid_name(self.page):
            raise ValueError(f"Zielseite {self.page!r}: [a-z][a-z0-9-]*, nicht {sorted(RESERVED)}")
        if not PAGE_NAME.fullmatch(self.name):
            raise ValueError(f"Abschnittsname {self.name!r}: [a-z][a-z0-9-]*")

    @property
    def stem(self) -> str:
        """Der Pfad ohne Endung relativ zum Vorlagenordner: für Vorlage, CSS und JavaScript."""
        return f"pages/{self.page}/{self.name}"

    @property
    def template(self) -> str:
        return f"{self.stem}.html.j2"


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


def section_problems(
    pages: Collection[str], entries: Sequence[tuple[str, PageSection]]
) -> list[str]:
    """Was am Register der Abschnitte falsch ist, unabhängig vom Profil; leer, wenn nichts.

    ``pages`` sind die Namen aller registrierten Seiten, auch der in einem Profil abgeschalteten,
    ``entries`` die Abschnitte mit dem Namen ihres Beitrags. Drei Fälle, je mit Beitrag und
    Abschnitt in der Meldung: das Ziel ist keine registrierte Seite (ein Tippfehler im Namen sähe
    sonst aus wie eine abgeschaltete Seite und fiele nie auf); zwei Abschnitte derselben Seite
    teilen einen Rang (ihre Folge entschiede dann der Name, nicht die Absicht) oder einen Namen
    (dieselbe Vorlage).
    """
    problems = [
        f"{contribution}: Abschnitt {section.name} zielt auf {section.page}.html, "
        "und keine Seite im Register heißt so"
        for contribution, section in entries
        if section.page not in pages
    ]
    for what, key in (("Rang", _rank_of), ("Name", _name_of)):
        first: dict[tuple[str, int | str], str] = {}
        for contribution, section in entries:
            slot = (section.page, key(section))
            if slot in first:
                problems.append(
                    f"{section.page}.html: {what} {slot[1]} doppelt "
                    f"({first[slot]}, {contribution} {section.name})"
                )
            else:
                first[slot] = f"{contribution} {section.name}"
    return problems


def _rank_of(section: PageSection) -> int | str:
    return section.rank


def _name_of(section: PageSection) -> int | str:
    return section.name


def _order_key(section: PageSection) -> tuple[str, int, str]:
    return (section.page, section.rank, section.name)


def _unique_per_page(sections: Sequence[PageSection]) -> bool:
    ranks = {(s.page, s.rank) for s in sections}
    names = {(s.page, s.name) for s in sections}
    return len(ranks) == len(names) == len(sections)


@deal.pre(_unique_per_page, message="Rang und Name je Seite eindeutig")
@deal.ensure(
    lambda sections, result: (
        [_order_key(s) for s in result] == sorted(_order_key(s) for s in sections)
    ),
    message="dieselben Abschnitte, nach Seite, Rang und Name",
)
def order_sections(sections: Sequence[PageSection]) -> tuple[PageSection, ...]:
    """Die feste Folge der Abschnitte: je Seite nach Rang, dann Name, nie nach dem Register."""
    return tuple(sorted(sections, key=_order_key))


def sections_for(settings: Settings) -> dict[str, tuple[PageSection, ...]]:
    """Die fremden Abschnitte je Unterseite, die für diese Settings gebaut wird, in fester Folge.

    Erst das Register, unabhängig vom Profil: ``SectionError``, wenn ``section_problems`` etwas
    findet. Dann das Profil: ein abgeschalteter Abschnitt fehlt still, wie eine abgeschaltete Seite;
    einer, dessen Zielseite hier nicht gebaut wird (ihr Schalter ist aus), entfällt mit einer Zeile
    im Log, ohne Fehler. Import in der Funktion wie in ``pages_for``.
    """
    from georep.enrich import CONTRIBUTIONS

    registered = {page.name for contribution in CONTRIBUTIONS for page in contribution.pages}
    entries = [(c.name, section) for c in CONTRIBUTIONS for section in c.sections]
    problems = section_problems(registered, entries)
    if problems:
        raise SectionError(f"Abschnitte im Register falsch: {'; '.join(problems)}")
    built = {page.name for page in pages_for(settings)}
    kept: list[PageSection] = []
    for contribution, section in entries:
        if section.enabled is not None and not section.enabled(settings):
            continue
        if section.page in built:
            kept.append(section)
        else:
            logger.info(
                f"Abschnitt {section.name} ({contribution}) entfällt: {section.page}.html wird "
                f"im Profil {settings.profile or settings.city.slug} nicht gebaut"
            )
    found: dict[str, tuple[PageSection, ...]] = {}
    for section in order_sections(kept):
        found[section.page] = (*found.get(section.page, ()), section)
    return found


def page_inputs(
    layout: Layout, settings: Settings, page: Page, sections: Sequence[PageSection]
) -> tuple[Path, ...]:
    """Was der Schritt ``page_<name>`` liest: die Eingaben der Seite, dann die ihrer Abschnitte.

    Jede Datei einmal, in der Folge ihres ersten Auftretens.
    """
    paths = [*page.inputs(layout, settings)]
    paths.extend(path for section in sections for path in section.inputs(layout, settings))
    return tuple(dict.fromkeys(paths))


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


def _asset(env: Environment, path: str) -> str:
    """Eine Datei neben den Vorlagen (CSS, JavaScript); fehlt sie, ist sie leer.

    Über den Loader statt über ``importlib.resources``, damit die Testnaht ``env`` von
    ``render_page`` auch das CSS und JavaScript der Abschnitte trägt (Vorarbeit V1).
    """
    if env.loader is None:
        return ""
    try:
        source, _, _ = env.loader.get_source(env, path)
    except TemplateNotFound:
        return ""
    return source


SectionContent = tuple[PageSection, Mapping[str, object]]  # ein Abschnitt und seine Daten


def _only_allowed_links(
    frame: PageFrame,
    page: Page,
    data: Mapping[str, object],
    allowed: frozenset[str] = frozenset(),
    env: Environment | None = None,
    sections: Sequence[SectionContent] = (),
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
    sections: Sequence[SectionContent] = (),
) -> str:
    """Die Unterseite als HTML; ``env`` ist die Testnaht für Vorlagen außerhalb des Pakets.

    ``sections`` sind die fremden Abschnitte mit ihren Daten, schon in der Folge der Seite
    (``sections_for``). Ihr CSS steht hinter dem der Seite, ihr JavaScript dahinter im selben
    Skriptblock, wie bei den Abschnitten der Hauptseite (``render.render_report``).
    """
    env = env or environment()
    stems = [f"pages/{page.name}", *(section.stem for section, _ in sections)]
    css = "".join(_asset(env, f"{stem}.css") for stem in stems)
    js = "\n".join(code for stem in stems if (code := _asset(env, f"{stem}.js")))
    return env.get_template("page.html.j2").render(
        model=frame,
        page=page,
        data=data,
        sections=sections,
        page_css=css,
        page_js=js,
        links={"repository": REPOSITORY, "cc0": CC0, "gpl": GPL},
    )


def build_page(
    layout: Layout,
    settings: Settings,
    page: Page,
    sections: Sequence[PageSection] = (),
    *,
    now: dt.datetime,
    commit: str | None,
) -> str:
    """Der Schritt ``page_<name>``: Seite mit ihren Abschnitten rendern, schreiben, eine Zeile."""
    allowed = page.links(settings).union(*(section.links(settings) for section in sections))
    html = render_page(
        page_frame(settings, now=now, commit=commit),
        page,
        page.data(layout, settings),
        allowed,
        sections=tuple((section, section.data(layout, settings)) for section in sections),
    )
    target = layout.guard_writable(page.output(layout))
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text(target, html)
    return f"{target.name}, {len(html.encode('utf-8')) / 1024:.1f} KB"
