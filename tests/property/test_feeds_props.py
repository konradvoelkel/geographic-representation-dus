"""Eigenschaften der Atom-Feeds (``report.feeds``) für zufällige Titel, Daten und Links.

Jeder Feed ist wohlgeformt, besteht die Regeln aus RFC 4287 und des Projekts und gibt die Titel
unverändert zurück, bis auf die Zeichen, die XML 1.0 verbietet; dieselben Dokumente geben dieselben
Bytes, in jeder Folge (Messdokument 17, § 6).
"""

from __future__ import annotations

import datetime as dt
import random
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from hypothesis import given
from hypothesis import strategies as st

from georep.report.feeds import (
    ATOM,
    FeedDocument,
    FeedHead,
    atom_problems,
    clean_text,
    feed_id,
    newest_entries,
    render_feed,
)

BERLIN = ZoneInfo("Europe/Berlin")
HEAD = FeedHead(feed_id("stadt/2025", "wahlbezirk-07"), "Wahlbezirk 7", "Neues", "1.2.3")

titles = st.text(min_size=0, max_size=60)
links = st.one_of(
    st.just(""),
    st.builds(
        lambda path: f"https://ris.example/{path}",
        st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=0x2FF), max_size=20),
    ),
)
documents = st.lists(
    st.builds(
        FeedDocument,
        id=st.builds(lambda n: f"https://ris.example/papers/{n}", st.integers(0, 10**6)),
        reference=st.sampled_from(("", "A/001/2025", "BV 7/0012/2026")),
        name=titles,
        day=st.dates(min_value=dt.date(2025, 1, 1), max_value=dt.date(2026, 12, 31)),
        modified=st.one_of(
            st.none(),
            st.datetimes(min_value=dt.datetime(2025, 1, 1), max_value=dt.datetime(2027, 1, 1)).map(
                lambda m: m.replace(microsecond=0, tzinfo=dt.UTC)
            ),
        ),
        link=links,
    ),
    max_size=12,
    unique_by=lambda d: d.id,
)


@given(documents, st.integers(min_value=1, max_value=12))
def test_every_feed_is_valid_and_gives_its_titles_back(
    found: list[FeedDocument], limit: int
) -> None:
    entries = newest_entries(found, limit, BERLIN)
    text = render_feed(HEAD, entries)
    assert atom_problems(text) == []
    root = ET.fromstring(text.encode("utf-8"))
    read = [e.findtext(f"{{{ATOM}}}title") or "" for e in root.findall(f"{{{ATOM}}}entry")]
    assert read == [clean_text(e.title) for e in entries]
    assert len(read) == min(limit, len(found))


@given(documents, st.randoms(use_true_random=False))
def test_the_same_documents_give_the_same_bytes_in_any_order(
    found: list[FeedDocument], rnd: random.Random
) -> None:
    shuffled = list(found)
    rnd.shuffle(shuffled)
    first = render_feed(HEAD, newest_entries(found, 50, BERLIN))
    assert render_feed(HEAD, newest_entries(shuffled, 50, BERLIN)) == first
