"""Eigenschaften der Regel „Einrichtung mit Stadtnamen" (Review § 3.1, decisions.md Punkt 44).

Die Regel ist eine reine Funktion auf einem Label und zwei Wortlisten; die Invarianten hier gelten
für jede Eingabe. ``deal.cases`` greift die Verträge daneben in ``test_contract_cases.py`` an.
"""

from __future__ import annotations

import polars as pl
from hypothesis import assume, given
from hypothesis import strategies as st

from georep.prep.pois import POI_COLUMNS, drop_city_facilities, is_city_facility

CITY = ("Düsseldorf", "Düsseldorfer")
PLACE_WORDS = ("bahnhof", "park", "wald", "garten", "gymnasium")

word = st.text(alphabet="abcdeäöüß-. ", min_size=0, max_size=12)
labels = st.one_of(
    word,
    st.builds(lambda a, b: f"{a} Düsseldorf {b}".strip(), word, word),
    st.builds(lambda a: f"{a} Düsseldorf".strip(), word),
    st.builds(lambda a: f"Düsseldorfer {a}".strip(), word),
    st.builds(lambda a: f"{a} (Düsseldorf)".strip(), word),
    st.builds(lambda a: f"Bahnhof Düsseldorf-{a}".strip(), word),
)
city_words = st.lists(st.sampled_from(["Düsseldorf", "Düsseldorfer"]), max_size=2).map(tuple)
place_words = st.lists(st.sampled_from(PLACE_WORDS), max_size=3).map(tuple)


@given(label=labels, places=place_words)
def test_without_a_city_word_nothing_is_a_facility(label: str, places: tuple[str, ...]) -> None:
    """Ohne Stadtwort im Profil greift die Regel nie: eine Stadt ohne Namen schließt nichts aus."""
    assert not is_city_facility(label, (), places)


@given(label=labels, cities=city_words, places=place_words)
def test_a_label_without_the_city_word_is_never_a_facility(
    label: str, cities: tuple[str, ...], places: tuple[str, ...]
) -> None:
    assume(not any(c.lower() in label.lower() for c in cities))
    assert not is_city_facility(label, cities, places)


@given(label=labels, cities=city_words, places=place_words)
def test_the_rule_ignores_case(
    label: str, cities: tuple[str, ...], places: tuple[str, ...]
) -> None:
    assert is_city_facility(label, cities, places) == is_city_facility(
        label.upper(), cities, places
    )


@given(label=labels, cities=city_words, places=place_words, extra=st.sampled_from(PLACE_WORDS))
def test_one_more_place_word_never_turns_a_place_into_a_facility(
    label: str, cities: tuple[str, ...], places: tuple[str, ...], extra: str
) -> None:
    """Die Gattungswortliste wirkt nur in eine Richtung: mehr Wörter heißt höchstens weniger Treffer."""
    before = is_city_facility(label, cities, places)
    after = is_city_facility(label, cities, (*places, extra))
    assert after <= before


@given(
    rows=st.lists(st.tuples(labels, st.integers(1, 41)), min_size=0, max_size=20),
    cities=city_words,
    places=place_words,
    keep=st.lists(labels, max_size=3),
)
def test_dropping_facilities_only_removes_rows(
    rows: list[tuple[str, int]],
    cities: tuple[str, ...],
    places: tuple[str, ...],
    keep: list[str],
) -> None:
    frame = pl.DataFrame(
        {
            "label": [r[0] for r in rows],
            "wahlkreis_id": [r[1] for r in rows],
            "lon": [6.8] * len(rows),
            "lat": [51.2] * len(rows),
        },
        schema={"label": pl.String, "wahlkreis_id": pl.Int64, "lon": pl.Float64, "lat": pl.Float64},
    ).select(POI_COLUMNS)
    out = drop_city_facilities(frame, cities, places, keep)
    assert out.columns == POI_COLUMNS
    assert out.height <= frame.height
    kept = out.get_column("label").to_list()
    assert kept == [label for label in frame.get_column("label").to_list() if label in set(kept)]
    # Jede entfernte Zeile ist eine Einrichtung, die nicht in der Ausnahmeliste steht
    removed = [label for label in frame.get_column("label").to_list() if label not in set(kept)]
    assert all(is_city_facility(label, cities, places) for label in removed)
    assert not set(removed) & set(keep)
