"""Vorhaben 16: die Treffer mit Stelle sind genau die Treffer der Suche, für jeden Rohtext.

Die Eigenschaft, an der jede Stelle hängt (Messdokument ``docs/plans/16-ortsbezug.md``, § 3.0 und
§ 6, Tests): wer im geplätteten Rohtext sucht (``flatten_with_offsets``, Fundament F1) und die
Spannen über die Offsets auf den Rohtext legt, findet **dieselben** Begriffe wie ``build_index`` auf
dem Textstore -- als Menge gegen das Orakel des Matchers (``tests/property/oracle_matcher.py``) --,
und jede Spanne trägt im Rohtext genau den Begriff, kleingeschrieben und ohne die Zeilenumbrüche,
die die Plättung entfernt. Dazu: jede Erwähnung hat genau eine grobe Stelle.
"""

from __future__ import annotations

import re

from hypothesis import example, given
from hypothesis import strategies as st

from georep.prep.raw_texts import flatten
from georep.search.matcher import FlashTextMatcher
from georep.search.positions import POSITIONS, TITLE, PlaceRules, coarse_position, raw_hits
from tests.property.oracle_matcher import oracle_extract

MARKER = "betrifft"
TERMS = ["kürtenstraße", "kürten", "am wehrhahn", "wehrhahn", "kö", "ölberg", "a-b", "straße"]
PIECES = st.sampled_from(
    [
        "Kürtenstraße",
        "Kürten",
        "\nstraße",
        "Am Wehrhahn",
        "am\nWehrhahn",
        "KÖ",
        "ölberg",
        "A-B",
        "Betrifft:",
        " ",
        "\n",
        "\f",
        "12a",
        "-",
        ",",
        "x",
    ]
)
RAW = st.lists(PIECES, max_size=14).map("".join)
RULES = PlaceRules(
    list_max_line=60, list_max_lead=12, house_number=re.compile(r"\s(?P<nr>\d+)(?P<zusatz>[a-z])?")
)


def _matcher() -> FlashTextMatcher:
    matcher = FlashTextMatcher()
    matcher.add_terms(TERMS)
    return matcher


@given(raw=RAW)
@example(raw="Betrifft: Kürten\nstraße 12a")
@example(raw="Betrifft:KÖölberg")
def test_hits_with_position_are_the_hits_of_the_index(raw: str) -> None:
    store = flatten(raw, MARKER, ())
    matcher = _matcher()
    found = raw_hits(raw, (), store, "", MARKER, matcher, RULES)
    assert found is not None
    assert {h.term for h in found} == matcher.extract(store) == oracle_extract(store, TERMS)
    for hit in found:
        piece = raw[hit.start : hit.end]
        assert piece.replace("\n", "").replace("\f", "").lower() == hit.term
    starts = [h.start for h in found]
    assert starts == sorted(starts) and len(set(starts)) == len(starts)


@given(section=st.text(max_size=20))
@example(section="beschlussvorschlag")
@example(section="")
def test_every_mention_has_exactly_one_coarse_position(section: str) -> None:
    """Jeder Abschnitt, auch ein unbekannter oder keiner, ist genau eine Stelle; nie der Titel."""
    found = coarse_position(section)
    assert found in POSITIONS and found != TITLE
