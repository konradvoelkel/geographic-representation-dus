"""Der Parser der Drucksachennummer und die Zuordnung Wahlbezirk zu Stadtbezirk als Eigenschaften."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.bodies import (
    COUNCIL_SHARE,
    DOCUMENTS,
    OTHER,
    OWN,
    OWN_RATE,
    OWN_SHARE,
    PARTS,
    WITH_HITS,
    documents_by_body,
    hits_by_body,
)
from georep.crosswalk import DISTRICT, WEIGHT
from georep.prep.bodies import (
    ADVISORY,
    BODY,  # noqa: F811 -- Spaltenname, nicht die Klasse
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
from georep.prep.voters import ELIGIBLE, UNIT, district_units
from georep.search.index import HITS
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


# --- Zuordnung Wahlbezirk zu Stadtbezirk --------------------------------------------------------

COLUMNS = load_settings(cwd=Path("/nonexistent")).columns.results
cell = st.one_of(st.integers(0, 5000).map(str), st.just(" "), st.just(""), st.just("x"))


def _as_int(value: str) -> int:
    text = value.strip()
    return int(text) if text.isdigit() else 0


@given(
    rows=st.lists(st.tuples(st.integers(1, 4), st.integers(1, 3), cell), min_size=1, max_size=40)
)
def test_district_units_weighs_eligible_voters(rows: list[tuple[int, int, str]]) -> None:
    """Wie ``read_results_csv`` sie liefert: alle Zellen Text, Müll und Leerzeichen zählen 0."""
    frame = pl.DataFrame(
        {
            COLUMNS.district: [str(r[0]) for r in rows],
            COLUMNS.city_district: [str(r[1]) for r in rows],
            COLUMNS.eligible: [r[2] for r in rows],
        },
        schema={
            COLUMNS.district: pl.String,
            COLUMNS.city_district: pl.String,
            COLUMNS.eligible: pl.String,
        },
    )
    weights = district_units(frame, COLUMNS)
    totals: dict[int, int] = {}
    pairs: dict[tuple[int, int], int] = {}
    for district, unit, raw in rows:
        n = _as_int(raw)
        totals[district] = totals.get(district, 0) + n
        pairs[district, unit] = pairs.get((district, unit), 0) + n
    # Wahlbezirke ohne Wahlberechtigte fehlen; alle anderen kommen mit Summe 1 vor.
    expected = {d for d, total in totals.items() if total > 0}
    assert set(weights.get_column(DISTRICT)) == expected
    for row in weights.iter_rows(named=True):
        key = (row[DISTRICT], row[UNIT])
        assert row[ELIGIBLE] == pairs[key] > 0
        assert row[WEIGHT] == pytest.approx(pairs[key] / totals[row[DISTRICT]])
    for district in expected:
        mine = weights.filter(pl.col(DISTRICT) == district)
        assert mine.get_column(WEIGHT).sum() == pytest.approx(1.0)
        assert mine.get_column(ELIGIBLE).sum() == totals[district]


@given(factor=st.integers(2, 1000))
def test_scaling_the_counts_leaves_the_weights_alone(factor: int) -> None:
    rows = [(40, 9, 8136), (40, 10, 4430), (41, 10, 3000)]

    def build(scale: int) -> pl.DataFrame:
        return pl.DataFrame(
            {
                COLUMNS.district: [str(r[0]) for r in rows],
                COLUMNS.city_district: [str(r[1]) for r in rows],
                COLUMNS.eligible: [str(r[2] * scale) for r in rows],
            }
        )

    one = district_units(build(1), COLUMNS)
    many = district_units(build(factor), COLUMNS)
    assert one.get_column(WEIGHT).to_list() == pytest.approx(many.get_column(WEIGHT).to_list())
    assert one.drop(ELIGIBLE, WEIGHT).equals(many.drop(ELIGIBLE, WEIGHT))


# --- Kennzahlen je Wahlbezirk -------------------------------------------------------------------

ELIGIBLE_COLUMN = "Wahlberechtigte_insgesamt"
kinds = st.sampled_from(KINDS)
city_districts = st.integers(1, 10)


@st.composite
def scenario(draw: st.DrawFn) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Dokumente mit zufaelliger Klasse, Wahlbezirke mit zufaelligen Treffern und Stadtbezirken."""
    n = draw(st.integers(1, 12))
    rows = []
    for i in range(n):
        kind = draw(kinds)
        unit = draw(city_districts) if kind == DISTRICT_BODY else None
        code = f"BV{unit}" if unit is not None else draw(st.sampled_from(["RAT", "OVA", "X"]))
        rows.append((f"p{i:02d}", code, kind, unit))
    papers = pl.DataFrame(
        {
            "id": [r[0] for r in rows],
            "gremium": [r[1] for r in rows],
            "gremium_art": [r[2] for r in rows],
            "stadtbezirk": [r[3] for r in rows],
        },
        schema={
            "id": pl.String,
            "gremium": pl.String,
            "gremium_art": pl.String,
            "stadtbezirk": pl.Int64,
        },
    )
    districts = draw(st.lists(st.integers(1, 5), min_size=1, max_size=4, unique=True))
    unit_rows: list[tuple[int, int, float]] = []
    for district in districts:
        units_here = draw(st.lists(city_districts, min_size=1, max_size=2, unique=True))
        share = 1.0 / len(units_here)
        unit_rows.extend((district, u, share) for u in units_here)
    units = pl.DataFrame(
        {
            "wahlkreis_id": [r[0] for r in unit_rows],
            "stadtbezirk": [r[1] for r in unit_rows],
            "wahlberechtigte": [1000 for _ in unit_rows],
            "gewicht": [r[2] for r in unit_rows],
        }
    )
    ids = papers.get_column("id").to_list()
    hits = {d: sorted(draw(st.sets(st.sampled_from(ids), max_size=len(ids)))) for d in districts}
    results = pl.DataFrame(
        {
            "wahlkreis_id": districts,
            "paper_ids": [hits[d] for d in districts],
            "anzahl_treffer": [len(hits[d]) for d in districts],
            ELIGIBLE_COLUMN: [1000 + d for d in districts],
            "wahlbeteiligung": [0.5 for _ in districts],
        }
    )
    return results, papers, units


@given(case=scenario())
def test_classes_add_up_and_own_is_a_subset_of_the_district_bodies(
    case: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame],
) -> None:
    results, papers, units = case
    frame = hits_by_body(results, papers, units, ELIGIBLE_COLUMN)
    assert frame.get_column(DISTRICT).to_list() == sorted(results.get_column(DISTRICT))
    kind_of = dict(zip(papers.get_column("id"), papers.get_column("gremium_art"), strict=True))
    unit_of = dict(zip(papers.get_column("id"), papers.get_column("stadtbezirk"), strict=True))
    mine = {
        d: set(units.filter(pl.col(DISTRICT) == d).get_column(UNIT))
        for d in results.get_column(DISTRICT)
    }
    hits = dict(zip(results.get_column(DISTRICT), results.get_column("paper_ids"), strict=True))
    for row in frame.iter_rows(named=True):
        ids = list(hits[row[DISTRICT]])
        bv = [i for i in ids if kind_of[i] == DISTRICT_BODY]
        own = [i for i in bv if unit_of[i] in mine[row[DISTRICT]]]
        assert row[OWN] == len(own) and row[OTHER] == len(bv) - len(own)
        assert row[OWN] <= len(bv)  # eigene sind eine Teilmenge der Bezirksvertretungen
        assert sum(row[part] for part in PARTS) == len(ids) == row[HITS]
        assert 0.0 <= row[OWN_SHARE] <= 1.0 and 0.0 <= row[COUNCIL_SHARE] <= 1.0
        assert row[OWN_RATE] >= 0.0


@given(case=scenario())
def test_every_document_counts_at_exactly_one_body(
    case: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame],
) -> None:
    results, papers, units = case
    frame = documents_by_body(papers, results, units)
    assert int(frame.get_column(DOCUMENTS).sum()) == papers.height
    assert frame.get_column(BODY).to_list() == sorted(set(papers.get_column("gremium")))
    hit_ids = {i for ids in results.get_column("paper_ids") for i in ids}
    expected = (
        papers.filter(pl.col("id").is_in(list(hit_ids))).group_by("gremium").len().sort("gremium")
    )
    got = dict(zip(frame.get_column(BODY), frame.get_column(WITH_HITS), strict=True))
    assert {k: got[k] for k in expected.get_column("gremium")} == dict(expected.iter_rows())
