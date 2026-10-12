from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from georep.prep.pois import clean_pois, pois_by_district
from georep.prep.streets import streets_by_district
from georep.prep.voters import (
    ELIGIBLE_POSTAL,
    ELIGIBLE_TOTAL,
    PRECINCT,
    SOURCE_DISTRICT,
    VOTERS,
    aggregate_voters,
    count_columns,
    spread_postal,
)
from georep.settings import ResultsColumns, Settings, load_settings


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


cell = st.one_of(st.integers(0, 5000).map(str), st.just(" "), st.just(""), st.just("x"))


def _as_int(value: object) -> int:
    text = str(value).strip()
    return int(text) if text.isdigit() else 0


@given(
    rows=st.lists(
        st.tuples(st.integers(1, 4), cell, cell, cell, cell, cell, cell, cell, cell),
        min_size=1,
        max_size=40,
    )
)
def test_voters_aggregate_sums_per_district(
    rows: list[tuple[int, str, str, str, str, str, str, str, str]], settings: Settings
) -> None:
    columns = settings.columns.results
    names = [columns.district, columns.eligible, columns.voters, *columns.parties.values()]
    frame = pl.DataFrame(
        {n: [str(r[i]) for r in rows] for i, n in enumerate(names)},
        schema={n: pl.String for n in names},
    )
    out = aggregate_voters(frame, columns)
    assert out["wahlkreis_id"].to_list() == sorted({r[0] for r in rows})
    for row in out.iter_rows(named=True):
        mine = [r for r in rows if r[0] == row["wahlkreis_id"]]
        eligible = sum(_as_int(r[1]) for r in mine)
        voters = sum(_as_int(r[2]) for r in mine)
        assert row[ELIGIBLE_TOTAL] == eligible and row[VOTERS] == voters
        if eligible:
            assert row["wahlbeteiligung"] == pytest.approx(voters / eligible)
        for i, (party, column) in enumerate(columns.parties.items()):
            assert row[column] == sum(_as_int(r[3 + i]) for r in mine)
            if voters:
                assert row[f"{party}_anteil"] == pytest.approx(row[column] / voters)


labels = st.text(alphabet="abcäö, ", min_size=1, max_size=6)


@given(
    entries=st.lists(
        st.fixed_dictionaries(
            {
                "label": labels,
                "lon": st.floats(6.6, 6.95),
                "lat": st.floats(51.1, 51.4),
                "stimmbezirk_id": st.integers(100, 999),
                "wahlkreis_id": st.one_of(st.none(), st.integers(1, 41)),
            }
        ),
        min_size=0,
        max_size=30,
    ),
    exclude=st.sets(labels, max_size=3),
)
@example(
    entries=[
        {"label": " ", "lon": 6.75, "lat": 51.25, "stimmbezirk_id": 100, "wahlkreis_id": 1},
        {"label": ", ", "lon": 6.75, "lat": 51.25, "stimmbezirk_id": 100, "wahlkreis_id": 1},
    ],
    exclude=set(),
)
def test_clean_pois_invariants(entries: list[dict[str, object]], exclude: set[str]) -> None:
    frame = pl.DataFrame(
        entries,
        schema={
            "label": pl.String,
            "lon": pl.Float64,
            "lat": pl.Float64,
            "stimmbezirk_id": pl.Int64,
            "wahlkreis_id": pl.Int64,
        },
    )
    out = clean_pois(frame, exclude)
    assert out.columns == ["label", "wahlkreis_id", "lon", "lat"]
    # Eindeutig sind die rohen Labels; "a,b" und "ab" fallen nach dem Kommaentfernen zusammen
    # (Reihenfolge der Arbeit: erst deduplizieren, dann Kommas weg). Das Wörterbuch dedupliziert später.
    raw_labels = [str(e["label"]) for e in entries]
    assert out.height <= len(set(raw_labels))
    assert out["wahlkreis_id"].null_count() == 0
    assert all("," not in label for label in out["label"].to_list())
    assert not set(out["label"].to_list()) & set(exclude)
    # erstes Vorkommen eines Labels gewinnt, dann erst Nullwerte raus (Reihenfolge der Arbeit)
    first: dict[str, dict[str, object]] = {}
    for e in entries:
        first.setdefault(str(e["label"]), e)
    expected = [
        e
        for e in first.values()
        if e["wahlkreis_id"] is not None and str(e["label"]).replace(",", "") not in exclude
    ]
    assert out.height == len(expected)
    for row, e in zip(out.iter_rows(named=True), expected, strict=True):
        assert row["label"] == str(e["label"]).replace(",", "") and row["lon"] == e["lon"]
    grouped = pois_by_district(out)
    assert grouped["wahlkreis_id"].is_sorted()
    assert all(t == sorted(set(t)) for t in grouped["suchbegriffe"].to_list())


@given(
    entries=st.lists(
        st.tuples(
            st.integers(1, 5),
            st.lists(st.text(alphabet="abc ", min_size=1, max_size=4), max_size=6),
        ),
        max_size=12,
    )
)
def test_streets_by_district_sorted_unique(entries: list[tuple[int, list[str]]]) -> None:
    frame = pl.DataFrame(
        {"wahlbezirk_id": [e[0] for e in entries], "straßen": [e[1] for e in entries]},
        schema={"wahlbezirk_id": pl.Int64, "straßen": pl.List(pl.String)},
    )
    out = streets_by_district(frame)
    assert out["wahlkreis_id"].to_list() == sorted({e[0] for e in entries if e[1]})
    for district, terms in zip(
        out["wahlkreis_id"].to_list(), out["suchbegriffe"].to_list(), strict=True
    ):
        assert terms == sorted({s for e in entries if e[0] == district for s in e[1]})


# --- Option 02: Verteilung der Briefwahl auf die Stimmbezirke eines Wahlbezirks ----------------

PERIOD_COLUMNS = ResultsColumns(
    sep=";",
    encoding="utf-8",
    district="",
    city_district="",
    precinct="gebiet-nr",
    precinct_name="gebiet-name",
    eligible="A",
    voters="B",
    eligible_postal="A2",
    postal_marker="Briefwahlbezirk",
    parties={"CDU": "D1"},
)
PERIOD_COUNTS = count_columns(PERIOD_COLUMNS)


@st.composite
def postal_case(draw: st.DrawFn) -> tuple[pl.DataFrame, dict[str, int], pl.DataFrame]:
    """Urnenstimmbezirke in bis zu drei Wahlbezirken und eine dazu passende Wahlbezirkszeile."""
    size = draw(st.integers(min_value=1, max_value=8))
    districts = draw(st.lists(st.integers(1, 3), min_size=size, max_size=size))
    eligible = draw(st.lists(st.integers(1, 5000), min_size=size, max_size=size))
    postal_key = [draw(st.integers(0, e)) for e in eligible]
    voters = [draw(st.integers(0, e)) for e in eligible]
    votes = [draw(st.integers(0, v)) for v in voters]
    keys = [f"{i:04d}" for i in range(size)]
    urn = pl.DataFrame(
        {
            PRECINCT: keys,
            ELIGIBLE_POSTAL: postal_key,
            ELIGIBLE_TOTAL: eligible,
            VOTERS: voters,
            "CDU_Stimmen": votes,
        },
        schema={
            PRECINCT: pl.String,
            ELIGIBLE_POSTAL: pl.Int64,
            ELIGIBLE_TOTAL: pl.Int64,
            VOTERS: pl.Int64,
            "CDU_Stimmen": pl.Int64,
        },
    ).sort(PRECINCT)
    assignment = dict(zip(keys, districts, strict=True))
    sums = urn.with_columns(
        pl.col(PRECINCT).replace_strict(assignment, return_dtype=pl.Int64).alias(SOURCE_DISTRICT)
    ).group_by(SOURCE_DISTRICT)
    rows = []
    for row in (
        sums.agg([pl.col(c).sum() for c in PERIOD_COUNTS])
        .sort(SOURCE_DISTRICT)
        .iter_rows(named=True)
    ):
        extra_voters = draw(st.integers(0, 2000))
        rows.append(
            {
                SOURCE_DISTRICT: row[SOURCE_DISTRICT],
                ELIGIBLE_TOTAL: row[ELIGIBLE_TOTAL],
                VOTERS: row[VOTERS] + extra_voters,
                "CDU_Stimmen": row["CDU_Stimmen"] + draw(st.integers(0, extra_voters)),
            }
        )
    return (
        urn,
        assignment,
        pl.DataFrame(
            rows,
            schema={SOURCE_DISTRICT: pl.Int64, **dict.fromkeys(PERIOD_COUNTS, pl.Int64)},
        ).sort(SOURCE_DISTRICT),
    )


@given(case=postal_case())
def test_spread_postal_is_sum_preserving_and_monotone(
    case: tuple[pl.DataFrame, dict[str, int], pl.DataFrame],
) -> None:
    urn, assignment, districts = case
    complete = spread_postal(urn, assignment, districts, PERIOD_COUNTS)
    for column in PERIOD_COUNTS:
        assert int(complete.get_column(column).sum()) == int(districts.get_column(column).sum())
        assert bool((complete.get_column(column) >= 0).all())
    assert complete.get_column(ELIGIBLE_TOTAL).to_list() == urn.get_column(ELIGIBLE_TOTAL).to_list()
    added = dict(
        zip(
            complete.get_column(PRECINCT).to_list(),
            [
                int(after) - int(before)
                for after, before in zip(
                    complete.get_column(VOTERS).to_list(),
                    urn.get_column(VOTERS).to_list(),
                    strict=True,
                )
            ],
            strict=True,
        )
    )
    weights = dict(
        zip(
            urn.get_column(PRECINCT).to_list(),
            urn.get_column(ELIGIBLE_POSTAL).to_list(),
            strict=True,
        )
    )
    # Mehr Wahlscheine, nicht weniger Briefwähler, innerhalb desselben Wahlbezirks
    for a in added:
        for b in added:
            if assignment[a] == assignment[b] and weights[a] > weights[b]:
                assert added[a] >= added[b]
