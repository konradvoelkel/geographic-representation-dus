"""Monatsreihe (Option 07): Handbeispiel, Lücken, Dokumente ohne Datum, Mini-Fixture."""

from __future__ import annotations

import datetime as dt

import deal
import polars as pl
import pytest

from georep.analysis.timeline import (
    DISTRICT_MONTHS_SCHEMA,
    MONTHLY_SCHEMA,
    district_months,
    monthly_series,
)
from georep.layout import Layout

DICTIONARY = pl.DataFrame(
    {"wahlkreis_id": [1, 2], "suchbegriffe": [["allee", "weg"], ["weg"]]},
    schema={"wahlkreis_id": pl.Int64, "suchbegriffe": pl.List(pl.String)},
)
INDEX = pl.DataFrame(
    {
        "suchbegriffe": ["allee", "weg"],
        "paper_ids": [["a", "c"], []],
        "anzahl_treffer": [2, 0],
    },
    schema={"suchbegriffe": pl.String, "paper_ids": pl.List(pl.String), "anzahl_treffer": pl.Int64},
)


def _meta(rows: list[tuple[str, dt.date | None, bool]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [r[0] for r in rows],
            "date": [r[1] for r in rows],
            "mit_text": [r[2] for r in rows],
        },
        schema={"id": pl.String, "date": pl.Date, "mit_text": pl.Boolean},
    )


META = _meta(
    [
        ("a", dt.date(2025, 10, 1), True),
        ("b", dt.date(2025, 10, 20), True),
        ("c", dt.date(2026, 1, 5), True),
        ("d", None, False),
    ]
)


def test_monthly_series_fills_the_gap_and_keeps_the_undated_last() -> None:
    frame = monthly_series(META, INDEX)
    assert frame.schema == MONTHLY_SCHEMA
    assert frame.rows() == [
        (dt.date(2025, 10, 1), 2, 2, 1),
        (dt.date(2025, 11, 1), 0, 0, 0),  # lückenlos, auch ohne Dokument
        (dt.date(2025, 12, 1), 0, 0, 0),
        (dt.date(2026, 1, 1), 1, 1, 1),
        (None, 1, 0, 0),  # Dokument ohne Datum: zählt zur Summe, zu keinem Monat
    ]
    assert int(frame.get_column("dokumente").sum()) == META.height


def test_monthly_series_without_any_date_has_one_row() -> None:
    only = _meta([("d", None, False)])
    empty_index = INDEX.clear()
    frame = monthly_series(only, empty_index)
    assert frame.rows() == [(None, 1, 0, 0)]


def test_district_months_counts_each_document_once_per_district() -> None:
    frame = district_months(DICTIONARY, INDEX, META)
    assert frame.schema == DISTRICT_MONTHS_SCHEMA
    # Bezirk 1 führt allee und weg, getroffen sind a (Oktober) und c (Januar); Bezirk 2 nur weg
    assert frame.rows() == [(1, dt.date(2025, 10, 1), 1), (1, dt.date(2026, 1, 1), 1)]
    # Ein Dokument mit zwei Begriffen desselben Bezirks zählt einmal
    both = INDEX.with_columns(pl.Series("paper_ids", [["a", "c"], ["a"]]))
    assert district_months(DICTIONARY, both, META).rows() == [
        (1, dt.date(2025, 10, 1), 1),
        (1, dt.date(2026, 1, 1), 1),
        (2, dt.date(2025, 10, 1), 1),
    ]


def test_an_undated_document_with_a_hit_gets_the_empty_month() -> None:
    index = INDEX.with_columns(pl.Series("paper_ids", [["a", "d"], []]))
    meta = _meta([("a", dt.date(2025, 10, 1), True), ("d", None, True)])
    assert district_months(DICTIONARY, index, meta).rows() == [
        (1, dt.date(2025, 10, 1), 1),
        (1, None, 1),
    ]


def test_the_contracts_refuse_inconsistent_input() -> None:
    with pytest.raises(deal.PreContractError):
        monthly_series(META.drop("mit_text"), INDEX)
    # Ein Treffer in einem Dokument ohne Text kann aus dem Korpustext nicht entstehen
    with pytest.raises(deal.PreContractError):
        monthly_series(META, INDEX.with_columns(pl.Series("paper_ids", [["d"], []])))
    with pytest.raises(deal.PreContractError):
        district_months(DICTIONARY, INDEX.with_columns(pl.Series("paper_ids", [["x"], []])), META)
    with pytest.raises(deal.PreContractError):
        district_months(DICTIONARY.drop("suchbegriffe"), INDEX, META)


def test_the_mini_fixture_matches_a_plain_polars_count(mini_run: Layout) -> None:
    corpus = pl.read_parquet(mini_run.corpus, columns=["id", "date", "text"])
    meta = corpus.select("id", "date", (pl.col("text") != "").alias("mit_text"))
    index = pl.read_parquet(mini_run.index)
    frame = monthly_series(meta, index)
    expected = (
        corpus.group_by(pl.col("date").dt.truncate("1mo").alias("monat"))
        .agg(pl.len().alias("dokumente"))
        .sort("monat")
    )
    dated = frame.filter(pl.col("dokumente") > 0).select("monat", "dokumente")
    assert dated.rows() == expected.rows()
    assert int(frame.get_column("dokumente").sum()) == corpus.height
    assert frame.get_column("monat").to_list()[0] == dt.date(2020, 9, 1)

    per_district = district_months(pl.read_parquet(mini_run.dictionary), index, meta)
    results = (
        pl.read_parquet(mini_run.results)
        .select("wahlkreis_id", "anzahl_treffer")
        .sort("wahlkreis_id")
    )
    sums = (
        per_district.group_by("wahlkreis_id")
        .agg(pl.col("anzahl_treffer").sum())
        .sort("wahlkreis_id")
    )
    assert sums.rows() == results.rows()
