"""FlashText gegen das Orakel: Hunderte zufällige Texte und Begriffsmengen, Mengengleichheit."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from georep.search.matcher import FlashTextMatcher, make_matcher
from tests.property.oracle_matcher import oracle_extract

TERMS = [
    "am wehrhahn",
    "wehrhahn",
    "kö-bogen",
    "kö",
    "kölner straße",
    "kölner str.",
    "straße",
    "hofgarten",
    "hofgartenstraße",
    "alt-pempelfort",
    "düssel",
    "ölberg",
    "alleestr. 24",
    "alleestr. 24 (düsseldorf)",
    "x",
    "24",
]
WORDS = [
    "am",
    "wehrhahn",
    "kö",
    "bogen",
    "kölner",
    "straße",
    "str.",
    "hofgarten",
    "hofgartenstraße",
    "alt",
    "pempelfort",
    "24",
    "x",
    "düssel",
    "ölberg",
    "alleestr.",
    "(düsseldorf)",
    "Am",
    "KÖ",
]
SEPARATORS = [" ", ", ", "-", ".", "\n", "", "  ", ";", "ä"]

texts = st.lists(st.sampled_from(WORDS), min_size=0, max_size=12).flatmap(
    lambda words: st.lists(
        st.sampled_from(SEPARATORS), min_size=len(words), max_size=len(words)
    ).map(lambda seps: "".join(w + s for w, s in zip(words, seps, strict=True)))
)
term_sets = st.sets(st.sampled_from(TERMS), min_size=1, max_size=len(TERMS))


@settings(max_examples=400, deadline=None)
@given(text=texts, terms=term_sets)
def test_flashtext_agrees_with_the_oracle(text: str, terms: set[str]) -> None:
    assert make_matcher(sorted(terms)).extract(text) == oracle_extract(text, terms)


@given(terms=term_sets)
def test_matcher_counts_its_terms(terms: set[str]) -> None:
    matcher = FlashTextMatcher()
    matcher.add_terms(sorted(terms))
    assert len(matcher) == len(terms)


def test_oracle_examples_that_fix_the_contract() -> None:
    assert oracle_extract("Am Wehrhahn 5", ["am wehrhahn", "wehrhahn"]) == {"am wehrhahn"}
    assert oracle_extract("Wehrhahn und am Wehrhahn", ["am wehrhahn", "wehrhahn"]) == {
        "wehrhahn",
        "am wehrhahn",
    }
    assert oracle_extract("Hofgartenstraße 1", ["hofgarten"]) == set()
    assert oracle_extract("kölner straße", ["lner straße"]) == {"lner straße"}  # Umlaut ist Grenze
    assert oracle_extract("xkö", ["kö"]) == set()
    assert oracle_extract("Kö-Bogen", ["kö", "kö-bogen"]) == {"kö-bogen"}
