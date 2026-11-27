"""Die Folge der fremden Abschnitte einer Unterseite hängt nicht an der Folge des Registers (V1).

Ein Beitrag hängt Abschnitte an die Unterseite eines anderen (``docs/plan-zeigen-2026-11.md``, § 4).
Welcher Beitrag im Register vorn steht, folgt der Merge-Reihenfolge (Synergien 2026-11, § 2.1);
auf der Seite soll das nicht zu sehen sein. Für jede Verteilung von Abschnitten mit je Seite
eindeutigem Rang und Namen auf Beiträge und jede Folge der Beiträge und der Abschnitte darin:
dieselben Abschnitte je Seite, nach Rang aufsteigend.
"""

from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import patch

from hypothesis import given
from hypothesis import strategies as st

import georep.enrich
from georep.enrich import Contribution
from georep.layout import Layout
from georep.report.pages import Page, PageSection, order_sections, sections_for
from georep.settings import Settings, load_settings

SETTINGS = load_settings(cwd=Path("/nonexistent"))
PAGES = ("akteure", "vorgaenge", "zeit")
NAMES = st.from_regex(r"[a-z][a-z0-9-]{0,6}", fullmatch=True)


def _key(section: PageSection) -> tuple[str, int, str]:
    return (section.page, section.rank, section.name)


def _nothing(layout: Layout, settings: Settings) -> dict[str, object]:
    return {}


def _page(name: str) -> Page:
    return Page(name, name, "Probe.", inputs=lambda layout, settings: (), data=_nothing)


def _section(page: str, name: str, rank: int) -> PageSection:
    return PageSection(page, name, rank, inputs=lambda layout, settings: (), data=_nothing)


@st.composite
def registers(draw: st.DrawFn) -> list[PageSection]:
    """Abschnitte über bis zu drei Seiten, Rang und Name je Seite eindeutig."""
    found: list[PageSection] = []
    for page in PAGES:
        names = draw(st.lists(NAMES, max_size=5, unique=True))
        ranks = draw(
            st.lists(st.integers(-50, 50), min_size=len(names), max_size=len(names), unique=True)
        )
        found.extend(_section(page, n, r) for n, r in zip(names, ranks, strict=True))
    return found


def _by_page(sections: list[PageSection], seed: int, shares: int) -> tuple[Contribution, ...]:
    """Die Abschnitte auf ``shares`` Beiträge verteilt, Beiträge und Abschnitte gemischt."""
    order = random.Random(seed)
    mixed = sections.copy()
    order.shuffle(mixed)
    contributions = [
        Contribution(f"{n:02d}-gast", sections=tuple(mixed[n::shares])) for n in range(shares)
    ]
    contributions.append(Contribution("14-gastgeber", pages=tuple(map(_page, PAGES))))
    order.shuffle(contributions)
    return tuple(contributions)


@given(sections=registers(), seeds=st.lists(st.integers(0, 2**32), min_size=2, max_size=2))
def test_die_folge_haengt_nicht_am_register(sections: list[PageSection], seeds: list[int]) -> None:
    results = []
    for seed in seeds:
        shares = 1 + seed % 4
        with patch.object(georep.enrich, "CONTRIBUTIONS", _by_page(sections, seed, shares)):
            results.append(sections_for(SETTINGS))
    assert results[0] == results[1]
    for page, found in results[0].items():
        assert [s.page for s in found] == [page] * len(found)
        assert [s.rank for s in found] == sorted(s.rank for s in found)
    shown = [s for found in results[0].values() for s in found]
    assert sorted(shown, key=_key) == sorted(sections, key=_key)


@given(sections=registers(), seed=st.integers(0, 2**32))
def test_order_sections_ist_eine_sortierung(sections: list[PageSection], seed: int) -> None:
    mixed = sections.copy()
    random.Random(seed).shuffle(mixed)
    assert order_sections(mixed) == order_sections(sections)
    assert [(s.page, s.rank) for s in order_sections(mixed)] == sorted(
        (s.page, s.rank) for s in sections
    )
