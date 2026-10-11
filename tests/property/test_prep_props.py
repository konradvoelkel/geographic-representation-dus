from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from georep.prep.pois import clean_pois, pois_by_district
from georep.prep.streets import streets_by_district
from georep.prep.voters import aggregate_voters
from georep.settings import Settings, load_settings


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
        assert row[columns.eligible] == eligible and row[columns.voters] == voters
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
