"""Die Startseite und der Umzug der Auswertung nach ``details.html`` (plan-startseite-2026-11.md).

Stufe U (§ 3, § 9): der Schritt ``report`` schreibt den bisherigen Inhalt als ``details.html``, und
``index.html`` ist eine vorläufige Startseite mit Kopf, Linkblock, einem ``<noscript>``-Satz und dem
Skript, das alte Anker nach ``details.html`` weiterleitet. Die eigenen Schlüssel der Startseite
(ids mit ``start-``, in der Adresse ``zeitraum`` und ``gremium``) sind reserviert: keine id auf
``details.html`` darf einer sein, sonst bliebe ein alter Link auf der Startseite hängen.
"""

from __future__ import annotations

import re

import pytest

from georep.layout import Layout
from georep.report.model import ReportModel
from georep.report.pages import page_links
from georep.report.render import sections
from georep.report.start import START_KEYS, START_PREFIX, redirect_script
from georep.settings import Settings

_ID = re.compile(r'(?<![\w-])id="([^"]*)"')
_SECTION = re.compile(r'<section id="([^"]*)"')
_HREF = re.compile(r'href="([^"]*)"')


def _ids(page: str) -> list[str]:
    return _ID.findall(page)


def _details(layout: Layout) -> str:
    return layout.site_details.read_text(encoding="utf-8")


def _start(layout: Layout) -> str:
    return layout.site_index.read_text(encoding="utf-8")


def test_the_report_step_writes_details_and_a_start_page(mini_run: Layout) -> None:
    assert mini_run.site_details == mini_run.site / "details.html"
    assert mini_run.site_details.is_file() and mini_run.site_index.is_file()
    # Der Stamp bleibt an der Startseite (Layout.site_index, plan-startseite, § 3)
    assert mini_run.site_index.with_name("index.html.stamp.json").is_file()
    assert not mini_run.site_details.with_name("details.html.stamp.json").exists()


def test_details_carries_every_section_of_the_profile(
    mini_run: Layout, mini_model: ReportModel
) -> None:
    """Jeder Abschnitt der Auswertung steht auf ``details.html``, keiner auf der Startseite.

    Auf der Mini-Fixture fehlt nur „Zwei Wahlperioden": das Standardprofil rechnet keinen
    Vergleich. Mit allen Abschnitten prüft es ``tests/golden/test_published_page.py`` an der
    veröffentlichten Seite.
    """
    assert mini_model.comparison is None and mini_model.monitoring_url
    expected = [s.name for s in sections() if s.name != "perioden"]
    assert _SECTION.findall(_details(mini_run)) == expected
    assert not set(_SECTION.findall(_start(mini_run))) & {s.name for s in sections()}


def test_details_keeps_title_and_links_back_to_the_start_page(mini_run: Layout) -> None:
    page = _details(mini_run)
    assert "<title>Geografische Repräsentation in " in page
    assert '<p class="meta" data-start="1"><a href="index.html">Zur Startseite</a></p>' in page


def test_no_id_on_details_takes_a_key_of_the_start_page(mini_run: Layout) -> None:
    """Die Weiterleitung lässt jeden Anker der Startseite stehen; auf ``details.html`` gibt es keinen."""
    ids = _ids(_details(mini_run))
    assert ids
    assert not [i for i in ids if i.startswith(START_PREFIX) or i in START_KEYS]
    # Der Schlüssel der Suche auf details.html (15-suche.js) ist keiner der Startseite
    assert "suche" not in START_KEYS
    own = _ids(_start(mini_run))
    assert own and all(i.startswith(START_PREFIX) for i in own), own


def _forwards(page: str) -> re.Pattern[str]:
    """Der reguläre Ausdruck der Weiterleitung, aus der Seite gelesen; in Python dieselbe Syntax."""
    match = re.search(r"!/(.+?)/\.test\(h\)", page)
    assert match is not None
    return re.compile(match.group(1))


@pytest.mark.parametrize(
    ("anchor", "stays"),
    [
        ("suche=Benrath", False),
        ("suche=grafenberger%20allee", False),
        ("bezirk-17", False),
        ("kernzahlen", False),
        ("downloads", False),
        ("zeitraumx", False),
        ("start-karte", True),
        ("zeitraum=2024-10..2025-09&gremium=OVA", True),
        ("gremium=OVA", True),
        ("zeitraum", True),
    ],
)
def test_the_start_page_forwards_old_anchors_to_details(
    mini_run: Layout, anchor: str, stays: bool
) -> None:
    page = _start(mini_run)
    head = page[: page.index("</head>")]
    assert redirect_script() in head  # ganz oben, vor dem Stil
    assert head.index(redirect_script()) < head.index("<style>")
    assert 'location.replace("details.html"+location.hash)' in redirect_script()
    assert (_forwards(page).match(anchor) is not None) is stays


def test_the_start_page_links_details_downloads_and_every_subpage(
    mini_run: Layout, default_settings: Settings
) -> None:
    page = _start(mini_run)
    hrefs = _HREF.findall(page)
    assert "details.html" in hrefs and "details.html#downloads" in hrefs
    for link in page_links(default_settings):
        assert link.href in hrefs
    ids = set(_ids(_details(mini_run)))
    targets = [h.split("#", 1)[1] for h in hrefs if h.startswith("details.html#")]
    assert targets and all(t in ids for t in targets), targets


def test_the_start_page_is_small_and_says_what_works_without_script(mini_run: Layout) -> None:
    """In U reicht klein; das Budget von 150 000 Byte kommt mit der Karte in Stufe B."""
    page = _start(mini_run)
    assert len(page.encode("utf-8")) < 50_000
    noscript = re.findall(r"<noscript>(.*?)</noscript>", page, re.S)
    assert len(noscript) == 1 and 'href="details.html"' in noscript[0]
    # Die Zeile „Weitere Städte" setzt publish auch hier (plan-startseite, § 3)
    assert page.count("<!--georep:weitere-staedte-->") == 1
