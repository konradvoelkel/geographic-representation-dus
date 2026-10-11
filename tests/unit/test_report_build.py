"""Der Schritt report auf der Mini-Fixture: Dateien, Prüfsummen, Schema, Seite."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from georep.export import csv_plan, write_csv
from georep.io import digest
from georep.layout import Layout
from georep.report.build import (
    DOCUMENTS_NAME,
    GEOJSON_NAME,
    MAP_NAME,
    SCHEMA_NAME,
    SiteSummary,
    current_commit,
)
from georep.report.model import COLUMN_DOCS, published_tables


def test_site_has_index_map_and_fifteen_download_files(mini_run: Layout) -> None:
    assert mini_run.site_index.is_file() and (mini_run.site / MAP_NAME).is_file()
    names = sorted(p.name for p in mini_run.site_data.iterdir())
    expected = sorted(
        [p.name for p in published_tables(mini_run).values()]
        + [f"{t}.csv" for t in published_tables(mini_run)]
        + [GEOJSON_NAME, SCHEMA_NAME, DOCUMENTS_NAME]
    )
    assert names == expected and len(names) == 15
    assert mini_run.site_index.with_name("index.html.stamp.json").is_file()


def test_page_lists_every_file_with_its_checksum(mini_run: Layout) -> None:
    page = mini_run.site_index.read_text(encoding="utf-8")
    for path in mini_run.site_data.iterdir():
        assert f'href="data/{path.name}"' in page
        assert digest(path) in page


def test_parquet_copies_are_byte_identical(mini_run: Layout) -> None:
    for parquet in published_tables(mini_run).values():
        assert (mini_run.site_data / parquet.name).read_bytes() == parquet.read_bytes()


def test_csv_downloads_follow_the_export_rules(mini_run: Layout, tmp_path: Path) -> None:
    plan = {parquet: (joins, sep) for parquet, joins, sep in csv_plan(mini_run)}
    for name, parquet in published_tables(mini_run).items():
        joins, separator = plan[parquet]
        write_csv(parquet, tmp_path / f"{name}.csv", joins, separator)
        assert (mini_run.site_data / f"{name}.csv").read_bytes() == (
            tmp_path / f"{name}.csv"
        ).read_bytes()
        frame = pl.read_csv(
            mini_run.site_data / f"{name}.csv", separator=separator, infer_schema=False
        )
        assert frame.columns == list(pl.read_parquet_schema(parquet))


def test_geojson_and_schema_are_consistent_with_the_tables(mini_run: Layout) -> None:
    geojson = json.loads((mini_run.site_data / GEOJSON_NAME).read_text(encoding="utf-8"))
    assert [f["properties"]["wahlkreis_id"] for f in geojson["features"]] == [1, 10, 38]
    assert set(geojson["features"][0]["properties"]) == set(COLUMN_DOCS["wahlbezirke"])
    schema = json.loads((mini_run.site_data / SCHEMA_NAME).read_text(encoding="utf-8"))
    assert set(schema["tables"]) == set(published_tables(mini_run)) | {"wahlbezirke"}
    for table, parquet in published_tables(mini_run).items():
        assert [c["column"] for c in schema["tables"][table]] == list(
            pl.read_parquet_schema(parquet)
        )
        assert all(c["description"] for c in schema["tables"][table])
    assert schema["version"] and schema["generated_at"]


def test_summary_line_counts_files_and_megabytes() -> None:
    assert SiteSummary(41, 17, 1_234_567).line() == "41 Wahlbezirke, 17 Dateien, 1,2 MB"


def test_map_page_embeds_districts_and_places(mini_run: Layout) -> None:
    page = (mini_run.site / MAP_NAME).read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>") and 'href="index.html"' in page
    assert page.count("leaflet@1.9.4") == 2 and page.count('integrity="sha256-') == 2
    districts = json.loads(
        page.split('<script id="districts" type="application/json">')[1].split("</script>")[0]
    )
    assert [f["properties"]["wahlkreis_id"] for f in districts["features"]] == [1, 10, 38]
    assert all(
        "klasse" in f["properties"] and "quote_text" in f["properties"]
        for f in districts["features"]
    )
    places = json.loads(
        page.split('<script id="places" type="application/json">')[1].split("</script>")[0]
    )
    assert places["features"] and places["features"][0]["geometry"]["type"] == "Point"


def test_current_commit_prefers_the_ci_variable_and_tolerates_no_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GITHUB_SHA", "0123456789abcdef")
    assert current_commit() == "0123456"
    monkeypatch.delenv("GITHUB_SHA")
    assert current_commit(tmp_path) is None
    here = current_commit()
    assert here is None or len(here) >= 7
