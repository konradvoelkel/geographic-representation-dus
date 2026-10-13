"""Der Schritt report auf der Mini-Fixture: Dateien, Prüfsummen, Schema, Seite."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from georep.export import write_csv
from georep.io import digest
from georep.layout import Layout
from georep.report.build import (
    DOCUMENTS_NAME,
    GEOJSON_NAME,
    MAP_NAME,
    SCHEMA_NAME,
    SUMMARY_NAME,
    TERMS_NAME,
    SiteSummary,
    current_commit,
)
from georep.report.tables import GEOJSON_COLUMNS, csv_plan, published
from georep.settings import Settings


def test_site_has_index_map_and_every_download_file(mini_run: Layout) -> None:
    assert mini_run.site_index.is_file() and (mini_run.site / MAP_NAME).is_file()
    names = sorted(p.name for p in mini_run.site_data.iterdir())
    tables = published(mini_run)
    expected = sorted(
        [t.path(mini_run).name for t in tables]
        + [f"{t.name}.csv" for t in tables]
        + [GEOJSON_NAME, SCHEMA_NAME, DOCUMENTS_NAME, SUMMARY_NAME, TERMS_NAME]
    )
    # Je Tabelle Parquet und CSV, dazu GeoJSON, Schema, Dokumentliste, summary.json (Option 01)
    # und die Begriffe je Wahlbezirk (Punkt 49)
    assert names == expected and len(names) == 2 * len(tables) + 5
    assert mini_run.site_index.with_name("index.html.stamp.json").is_file()


def test_page_lists_every_file_with_its_checksum(mini_run: Layout) -> None:
    page = mini_run.site_index.read_text(encoding="utf-8")
    for path in mini_run.site_data.iterdir():
        assert f'href="data/{path.name}"' in page
        assert digest(path) in page


def test_parquet_copies_are_byte_identical(mini_run: Layout) -> None:
    for table in published(mini_run):
        parquet = table.path(mini_run)
        assert (mini_run.site_data / parquet.name).read_bytes() == parquet.read_bytes()


def test_csv_downloads_follow_the_export_rules(mini_run: Layout, tmp_path: Path) -> None:
    plan = {parquet: (joins, sep) for parquet, joins, sep in csv_plan(mini_run)}
    for table in published(mini_run):
        name, parquet = table.name, table.path(mini_run)
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
    assert set(geojson["features"][0]["properties"]) == set(GEOJSON_COLUMNS)
    schema = json.loads((mini_run.site_data / SCHEMA_NAME).read_text(encoding="utf-8"))
    tables = published(mini_run)
    assert set(schema["tables"]) == {t.name for t in tables} | {"wahlbezirke"}
    for table in tables:
        assert [c["column"] for c in schema["tables"][table.name]] == list(
            pl.read_parquet_schema(table.path(mini_run))
        )
        assert all(c["description"] for c in schema["tables"][table.name])
    assert schema["version"] and schema["generated_at"]


def test_summary_line_counts_files_and_megabytes() -> None:
    assert SiteSummary(41, 17, 1_234_567).line() == "41 Wahlbezirke, 17 Dateien, 1,2 MB"


def test_the_summary_line_says_when_the_page_is_over_its_budget() -> None:
    """Punkt 50: sonst merkt eine wachsende Seite erst der slow-Test -- oder niemand."""
    inside = SiteSummary(41, 53, 13_200_000, 958_527, 1_000_000)
    assert not inside.over_budget() and "Budget" not in inside.line()
    over = SiteSummary(41, 53, 13_300_000, 1_050_000, 1_000_000)
    assert over.over_budget()
    assert over.line().endswith("; Seite über dem Budget (1,05 von 1,00 MB)")
    assert not SiteSummary(41, 53, 1, 9_999_999, 0).over_budget()  # 0 schaltet die Prüfung ab


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


def test_topics_switched_off_leave_no_trace_on_the_page(
    mini_run: Layout, default_settings: Settings, tmp_path: Path
) -> None:
    """``topics.k = 0`` in einer gelaufenen Datenwurzel: die alten Themendateien bleiben liegen,
    aber die Seite zeigt sie nicht mehr. Sonst stünden dort 20 Themen mit 0,0 % Anteil."""
    import datetime as dt
    import shutil

    from georep.report.build import build_site
    from georep.settings import Topics

    layout = Layout(tmp_path / "data", tmp_path / "cache", mini_run.reference_root)
    shutil.copytree(mini_run.root, layout.root)
    assert layout.topics.exists() and layout.topic_documents.exists()
    without = default_settings.model_copy(update={"topics": Topics(k=0)})
    build_site(layout, without, now=dt.datetime(2026, 10, 12, tzinfo=dt.UTC), commit=None)

    import re

    page = layout.site_index.read_text(encoding="utf-8")
    assert "Die 20 Themen" not in page and "stärkste Wörter" not in page
    section = re.search(r'<section id="gewichtung">.*?</section>', page, re.S)
    assert section is not None  # die Gewichtung selbst bleibt
    assert "Thema " not in section.group(0)  # aber keine Themenzeile mehr
    assert "ohne Gewichtung" in section.group(0)
    names = sorted(p.name for p in layout.site_data.iterdir())
    assert not [n for n in names if n.startswith("themen")], names
    assert "wahlbezirke_gewichtet.parquet" in names
    schema = json.loads((layout.site_data / SCHEMA_NAME).read_text(encoding="utf-8"))
    assert "themen" not in schema["tables"] and "themen_dokumente" not in schema["tables"]


# --- Option 07: Monitoring der laufenden Wahlperiode ------------------------------------------


def test_the_month_section_and_its_two_tables_are_on_the_page(mini_run: Layout) -> None:
    page = mini_run.site_index.read_text(encoding="utf-8")
    assert '<section id="monate">' in page and 'class="bars"' in page
    assert page.count('class="bars"') == 1 and page.count('class="scatter"') == 1
    names = {p.name for p in mini_run.site_data.iterdir()}
    for stem in ("monatsreihe", "wahlbezirke_monate"):
        assert {f"{stem}.parquet", f"{stem}.csv"} <= names
        assert f'href="data/{stem}.parquet"' in page
    schema = json.loads((mini_run.site_data / SCHEMA_NAME).read_text(encoding="utf-8"))
    assert {"monatsreihe", "wahlbezirke_monate"} <= set(schema["tables"])
    # Die Monatsreihe der Seite summiert zum Korpus
    rows = pl.read_parquet(mini_run.site_data / "monatsreihe.parquet")
    assert int(rows["dokumente"].sum()) == pl.read_parquet(mini_run.corpus).height
