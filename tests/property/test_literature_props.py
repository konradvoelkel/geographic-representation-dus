"""Die Rendering-Invariante der Literaturübersicht (Punkt 47).

Für jede Liste von Einträgen gilt: jeder steht genau einmal auf der Seite, in der Reihenfolge der
Datei, und jeder Link, den er mitbringt, steht in der Allowlist. Das ist eine Eigenschaft über alle
Eingaben, also ein hypothesis-Test und kein Beispiel (CLAUDE.md, „Commits").
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import replace

from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from georep.report.model import ReportModel
from georep.report.render import ALLOWED_LINKS, Visuals, external_links, model_links, render_report
from georep.settings import LiteratureEntry

ANCHOR = re.compile(r'<li id="lit-([a-z][a-z0-9-]*)"')
# Buchstaben und Leerzeichen: so kann kein erzeugter Text zufällig wie ein Anker aussehen.
words = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=40).map(str.strip)
keys = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=12).filter(
    lambda value: value[0].isalpha()
)


@st.composite
def entries(draw: st.DrawFn, key: str) -> LiteratureEntry:
    """Ein gültiger Eintrag zu einem gegebenen Schlüssel: mit URL, mit DOI oder mit beidem."""
    kind = draw(st.sampled_from(("url", "doi", "both")))
    path = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-/", min_size=1, max_size=20))
    suffix = draw(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789.-", min_size=1, max_size=12)
    )
    return LiteratureEntry(
        key=key,
        authors=draw(words.filter(bool)),
        title=draw(words.filter(bool)),
        year=draw(st.integers(1900, 2100)),
        venue=draw(words.filter(bool)),
        url=f"https://beispiel.invalid/{path}" if kind in ("url", "both") else "",
        doi=f"10.1234/{suffix}" if kind in ("doi", "both") else "",
        accessed=dt.date(2026, 10, 13) if kind in ("url", "both") else None,
        note=draw(words),
        pending=draw(st.booleans()),
    )


@st.composite
def literature_lists(draw: st.DrawFn) -> tuple[LiteratureEntry, ...]:
    chosen = draw(st.lists(keys, min_size=0, max_size=6, unique=True))
    return tuple(draw(entries(key)) for key in chosen)


@given(found=literature_lists())
@hsettings(max_examples=40, deadline=None)
def test_every_entry_once_and_in_the_order_of_the_file(
    found: tuple[LiteratureEntry, ...], mini_model: ReportModel, mini_visuals: Visuals
) -> None:
    page = render_report(replace(mini_model, literature=found), mini_visuals)
    assert ANCHOR.findall(page) == [entry.key for entry in found]
    assert ("<h2>Literatur und verwandte Arbeiten</h2>" in page) == bool(found)


@given(found=literature_lists())
@hsettings(max_examples=40, deadline=None)
def test_every_link_of_an_entry_is_allowed_and_rendered(
    found: tuple[LiteratureEntry, ...], mini_model: ReportModel, mini_visuals: Visuals
) -> None:
    model = replace(mini_model, literature=found)
    page = render_report(model, mini_visuals)
    allowed = ALLOWED_LINKS | model_links(model)
    expected = {link for entry in found for link in entry.links}
    assert expected <= allowed
    assert expected <= set(external_links(page))
    # Die Nachbedingung von ``render_report`` hat schon gegriffen; hier steht, warum sie hält.
    assert set(external_links(page)) <= allowed
