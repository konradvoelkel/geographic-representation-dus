"""Der Parser der Drucksachennummer gegen Nummern aus der eigenen Grammatik und gegen beliebigen Text."""

from __future__ import annotations

from pathlib import Path

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.prep.bodies import (
    ADVISORY,
    COMMITTEE,
    COUNCIL,
    DISTRICT_BODY,
    KINDS,
    UNKNOWN,
    BodyRef,
    BodyRules,
    classify_papers,
    counts_by_kind,
    parse_reference,
)
from georep.settings import load_settings

RULES = BodyRules.from_settings(load_settings(cwd=Path("/nonexistent")).bodies)
KNOWN = sorted(RULES.council | RULES.committees | RULES.advisory)

numbers = st.integers(1, 99)
sequence = st.integers(0, 9999)
year = st.integers(2000, 2099)
suffix = st.one_of(
    st.just(""), st.builds("/{}".format, st.integers(1, 9)), st.just("-2"), st.just("/-1")
)
foreign = st.text(alphabet="ABCXYZÄÖÜ", min_size=1, max_size=5).filter(
    lambda c: c not in KNOWN and c != RULES.district_body
)


def _kind(code: str) -> str:
    if code in RULES.council:
        return COUNCIL
    if code in RULES.committees:
        return COMMITTEE
    if code in RULES.advisory:
        return ADVISORY
    return UNKNOWN


@st.composite
def references(draw: st.DrawFn) -> tuple[str, BodyRef]:
    """Eine Drucksachennummer aus der Grammatik mit dem Gremium, das sie bedeutet."""
    tail = f"/{draw(sequence)}/{draw(year)}{draw(suffix)}"
    form = draw(st.sampled_from(["bv", "known", "foreign", "known+number", "bv-without-number"]))
    if form == "bv":
        n = draw(numbers)
        return f"{RULES.district_body}{n}{tail}", BodyRef(
            DISTRICT_BODY, f"{RULES.district_body}{n}", n
        )
    if form == "known":
        code = draw(st.sampled_from(KNOWN))
        return f"{code}{tail}", BodyRef(_kind(code), code, None)
    if form == "foreign":
        code = draw(foreign)
        return f"{code}{tail}", BodyRef(UNKNOWN, code, None)
    if form == "known+number":
        code, n = draw(st.sampled_from(KNOWN)), draw(numbers)
        return f"{code}{n}{tail}", BodyRef(UNKNOWN, f"{code}{n}", None)
    return f"{RULES.district_body}{tail}", BodyRef(UNKNOWN, RULES.district_body, None)


@given(case=references())
def test_grammar_round_trips(case: tuple[str, BodyRef]) -> None:
    reference, expected = case
    assert parse_reference(reference, RULES) == expected


@given(text=st.text(max_size=30))
def test_any_text_yields_a_consistent_reference(text: str) -> None:
    ref = parse_reference(text, RULES)
    assert ref.kind in KINDS
    assert (ref.district is not None) == (ref.kind == DISTRICT_BODY)
    assert ref.district is None or ref.district >= 1
    assert ref.code is not None or ref.kind == UNKNOWN
    if ref.kind != UNKNOWN:
        assert RULES.pattern.match(text) is not None


@given(cases=st.lists(references(), min_size=0, max_size=30), ids=st.permutations(range(30)))
def test_classify_papers_counts_what_the_parser_says(
    cases: list[tuple[str, BodyRef]], ids: list[int]
) -> None:
    corpus = pl.DataFrame(
        {
            "id": [f"p{ids[i]:02d}" for i in range(len(cases))],
            "reference": [c[0] for c in cases],
        },
        schema={"id": pl.String, "reference": pl.String},
    )
    frame = classify_papers(corpus, RULES)
    expected = {kind: sum(1 for _, ref in cases if ref.kind == kind) for kind in KINDS}
    assert counts_by_kind(frame) == expected
    assert frame.get_column("id").to_list() == sorted(corpus.get_column("id"))
    by_id = dict(zip(corpus.get_column("id"), (c[1] for c in cases), strict=True))
    for row in frame.iter_rows(named=True):
        ref = by_id[row["id"]]
        assert (row["gremium"], row["gremium_art"], row["stadtbezirk"]) == (
            ref.code,
            ref.kind,
            ref.district,
        )
