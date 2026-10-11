"""Datenmodell der Berichtsseite auf der Mini-Fixture: Zahlen gegen Polars nachgerechnet."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl
import pytest
from shapely.geometry import box

from georep.errors import SchemaError
from georep.geo import Precinct
from georep.layout import Layout
from georep.report.model import (
    COLUMN_DOCS,
    NARROW_NBSP,
    TOP_TERMS,
    ColumnDoc,
    ReportModel,
    build_report_model,
    column_docs,
    district_names,
    district_rows,
    format_de,
    percent_de,
    published_tables,
    stamp_written,
    term_counts,
    top_terms_city,
)
from georep.settings import Settings

NOW = dt.datetime(2026, 10, 11, 20, 0, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def model(mini_run: Layout, default_settings: Settings) -> ReportModel:
    return build_report_model(mini_run, default_settings, now=NOW, commit="abc1234")


def test_key_figures_match_the_parquet_files(model: ReportModel, mini_run: Layout) -> None:
    results = pl.read_parquet(mini_run.results)
    figures = model.figures
    assert (figures.districts, figures.precincts) == (3, 22)
    assert (figures.documents, figures.documents_with_text) == (200, 200)
    assert (
        figures.terms == pl.read_parquet(mini_run.dictionary)["suchbegriffe"].explode().n_unique()
    )
    assert figures.documents_hit == results["paper_ids"].explode().n_unique()
    assert figures.rate_median == pytest.approx(results["trefferquote"].median())
    assert figures.rate_min == pytest.approx(results["trefferquote"].min())
    assert figures.rate_max == pytest.approx(results["trefferquote"].max())
    assert figures.turnout_median == pytest.approx(results["wahlbeteiligung"].median())
    assert model.generated_at == NOW and model.commit == "abc1234" and model.version
    assert model.working_crs == "EPSG:25832"


def test_district_rows_match_the_results(model: ReportModel, mini_run: Layout) -> None:
    results = pl.read_parquet(mini_run.results).sort("wahlkreis_id")
    dictionary = pl.read_parquet(mini_run.dictionary).sort("wahlkreis_id")
    assert [d.id for d in model.districts] == [1, 10, 38]
    assert [d.name for d in model.districts] == [
        "Altstadt, Carlstadt, Hofgarten",
        "Flingern Süd",
        "Hassels, Paulsmühle",
    ]
    for district, row, terms in zip(
        model.districts, results.iter_rows(named=True), dictionary["suchbegriffe"], strict=True
    ):
        assert district.hits == row["anzahl_treffer"]
        assert district.eligible == row["Wahlberechtigte_insgesamt"]
        assert district.voters == row["Waehler"]
        assert district.rate == pytest.approx(row["trefferquote"])
        assert district.turnout == pytest.approx(row["wahlbeteiligung"])
        assert district.terms_total == len(terms)
        assert district.terms_without_hits + len(district.terms) <= district.terms_total
        assert district.top_terms == district.terms[:TOP_TERMS]
        assert all(t.hits > 0 and district.id in t.districts for t in district.terms)
        assert all(t.term not in model.hidden_terms for t in district.terms)


def test_hidden_terms_stay_hidden_but_counted(
    model: ReportModel, mini_run: Layout, default_settings: Settings
) -> None:
    assert model.hidden_terms == ("schulweg",)  # kommt in den drei Mini-Bezirken nicht vor
    results = pl.read_parquet(mini_run.results)
    counts = term_counts(pl.read_parquet(mini_run.dictionary), pl.read_parquet(mini_run.index))
    names = {d.id: d.name for d in model.districts}
    columns = default_settings.columns.results
    strongest = model.districts[0].top_terms[0].term
    rows = district_rows(results, counts, names, columns, hidden=(strongest,))
    first, before = rows[0], model.districts[0]
    assert strongest not in [t.term for t in first.terms]
    assert first.terms_total == before.terms_total  # zählt weiter
    assert len(first.terms) == len(before.terms) - 1
    assert first.hits == before.hits  # die Treffer der Auswertung ändern sich nicht
    assert strongest not in [t.term for t in top_terms_city(counts, hidden=(strongest,))]
    assert strongest in [t.term for t in top_terms_city(counts, hidden=())]


def test_regression_on_three_districts_has_no_outlier_variant(model: ReportModel) -> None:
    assert model.regression.all.n == 3
    assert model.regression.excluded == (1, 10)
    assert model.regression.without is None


def test_data_stand_comes_from_settings_and_stamps(model: ReportModel) -> None:
    assert model.stand.election == dt.date(2025, 9, 14)
    assert model.stand.period_start == dt.date(2020, 9, 13)
    # bootstrap kopiert die Referenz; die Netzschritte liefen nie, also kein Abrufdatum
    assert model.stand.streets_fetched is None and model.stand.pois_fetched is None


def test_column_docs_cover_every_published_column(model: ReportModel, mini_run: Layout) -> None:
    tables = published_tables(mini_run)
    documented = {(d.table, d.column) for d in model.columns}
    for table, path in tables.items():
        for column in pl.read_parquet_schema(path):
            assert (table, column) in documented
    assert all(d.description for d in model.columns)
    assert {d.table for d in model.columns} == set(tables) | {"wahlbezirke"}
    assert (
        ColumnDoc("wahlbezirke", "name", "GeoJSON-Eigenschaft", *COLUMN_DOCS["wahlbezirke"]["name"])
        in model.columns
    )


def test_column_docs_refuse_mismatches(mini_run: Layout) -> None:
    with pytest.raises(SchemaError, match="ohne Beschreibung"):
        column_docs({"wahlbezirke_waehler": mini_run.results})
    with pytest.raises(SchemaError, match="Beschreibung ohne Spalte"):
        column_docs({"wahlbezirke_auswertung": mini_run.voters})


def _precinct(precinct_id: str, district: int, name: str) -> Precinct:
    return Precinct(precinct_id, district, name, box(0, 0, 1, 1))


def test_district_names_require_one_name_per_district() -> None:
    assert district_names([_precinct("101", 1, "A"), _precinct("102", 1, "A")]) == {1: "A"}
    with pytest.raises(SchemaError, match="zwei Namen"):
        district_names([_precinct("101", 1, "A"), _precinct("102", 1, "B")])


def test_term_counts_join_dictionary_and_index() -> None:
    dictionary = pl.DataFrame(
        {"wahlkreis_id": [1, 2], "suchbegriffe": [["allee", "weg"], ["allee"]]}
    )
    index = pl.DataFrame(
        {"suchbegriffe": ["allee"], "paper_ids": [["p1", "p2"]], "anzahl_treffer": [2]}
    )
    counts = term_counts(dictionary, index)
    assert counts.rows() == [(1, "allee", 2, [1, 2]), (1, "weg", 0, [1]), (2, "allee", 2, [1, 2])]
    top = top_terms_city(counts, hidden=())
    assert [(t.term, t.hits, t.districts) for t in top] == [("allee", 2, (1, 2))]
    assert top_terms_city(counts, hidden=("allee",)) == ()


def test_district_rows_need_a_name_for_every_district(default_settings: Settings) -> None:
    results = pl.DataFrame(
        {
            "wahlkreis_id": [1],
            "anzahl_treffer": [2],
            "Wahlberechtigte_insgesamt": [100],
            "Waehler": [50],
            "wahlbeteiligung": [0.5],
            "trefferquote": [0.02],
        }
    )
    counts = pl.DataFrame(
        {"wahlkreis_id": [1], "suchbegriffe": ["allee"], "anzahl_treffer": [2], "districts": [[1]]}
    )
    columns = default_settings.columns.results
    rows = district_rows(results, counts, {1: "Eins"}, columns, hidden=())
    assert rows[0].name == "Eins" and rows[0].top_terms[0].term == "allee"
    with pytest.raises(SchemaError, match="ohne Geometrie"):
        district_rows(results, counts, {2: "Zwei"}, columns, hidden=())


def test_stamp_written_reads_the_date_or_nothing(tmp_path: Path) -> None:
    output = tmp_path / "x.json"
    assert stamp_written(output) is None
    stamp = tmp_path / "x.json.stamp.json"
    stamp.write_text("kaputt", encoding="utf-8")
    assert stamp_written(output) is None
    stamp.write_text(json.dumps({"written": "2026-10-11T18:30:00+00:00"}), encoding="utf-8")
    assert stamp_written(output) == dt.date(2026, 10, 11)
    stamp.write_text(json.dumps({"code": "0.9.0"}), encoding="utf-8")
    assert stamp_written(output) is None


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (1234567.891, 1, f"1{NARROW_NBSP}234{NARROW_NBSP}567,9"),
        (0.0, 0, "0"),
        (-0.04, 1, "0,0"),
        (-1234, 0, f"-1{NARROW_NBSP}234"),
        (999, 0, "999"),
        (0.16125, 4, "0,1613"),
        (19108, 0, f"19{NARROW_NBSP}108"),
    ],
)
def test_format_de_examples(value: float, decimals: int, expected: str) -> None:
    assert format_de(value, decimals) == expected


def test_percent_de_uses_a_narrow_space_before_the_sign() -> None:
    assert percent_de(0.531127) == f"53,1{NARROW_NBSP}%"
    assert percent_de(1.0, 0) == f"100{NARROW_NBSP}%"
