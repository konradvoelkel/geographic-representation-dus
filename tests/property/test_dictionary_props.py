from __future__ import annotations

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.search.dictionary import all_terms, build_dictionary, normalise_terms

raw_terms = st.lists(
    st.text(alphabet="abcßüö -.,()1 ", min_size=0, max_size=12).map(lambda s: s.replace(",", "")),
    min_size=0,
    max_size=8,
)


def _normalise(terms: list[str]) -> list[str]:
    frame = pl.DataFrame({"t": [terms]}, schema={"t": pl.List(pl.String)})
    out: list[str] = frame.select(normalise_terms(pl.col("t"))).item(0, 0).to_list()
    return out


@given(terms=raw_terms)
def test_normalised_terms_are_clean_sorted_unique_and_idempotent(terms: list[str]) -> None:
    out = _normalise(terms)
    assert out == sorted(set(out))
    assert all(t and t == t.strip() == t.lower() for t in out)
    expected_inputs = {t.strip().lower() for t in terms if t.strip()}
    assert expected_inputs <= set(out)
    for t in out:
        if "straße" in t:
            assert t.replace("straße", "str.") in out
    assert _normalise(out) == out


@given(
    pois=st.dictionaries(st.integers(1, 5), raw_terms, min_size=1, max_size=5),
    streets=st.dictionaries(st.integers(1, 5), raw_terms, min_size=1, max_size=5),
)
def test_dictionary_keeps_only_districts_present_in_both_sources(
    pois: dict[int, list[str]], streets: dict[int, list[str]]
) -> None:
    pois_df = pl.DataFrame(
        {"wahlkreis_id": list(pois), "suchbegriffe": list(pois.values())},
        schema={"wahlkreis_id": pl.Int64, "suchbegriffe": pl.List(pl.String)},
    )
    streets_df = pl.DataFrame(
        {"wahlkreis_id": list(streets), "suchbegriffe": list(streets.values())},
        schema={"wahlkreis_id": pl.Int64, "suchbegriffe": pl.List(pl.String)},
    )
    out = build_dictionary(pois_df, streets_df)
    assert out["wahlkreis_id"].to_list() == sorted(set(pois) & set(streets))
    for district, terms in zip(
        out["wahlkreis_id"].to_list(), out["suchbegriffe"].to_list(), strict=True
    ):
        assert terms == _normalise(pois[district] + streets[district])
    assert all_terms(out) == sorted({t for terms in out["suchbegriffe"].to_list() for t in terms})
