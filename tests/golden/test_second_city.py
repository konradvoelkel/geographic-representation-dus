"""Die ganze Offline-Kette für die zweite Stadt (Option 01, Stufe E).

Eingaben: ``tests/fixtures/mg/`` (drei Wahlbezirke Mönchengladbachs aus der Netzstichprobe vom
2026-10-12, siehe das README dort). Geprüft wird, dass dieselbe Kette mit einem anderen Profil
läuft, dass die Summen je Wahlbezirk denen der Wahlbezirks-CSV der Quelle gleichen (das ist der
Golden Master dieser Stufe) und dass die Seite die Stadt nennt, deren Profil gilt.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest

from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.streets import directory_agreement
from georep.prep.voters import DISTRICT, ELIGIBLE, VOTERS
from georep.settings import Settings, load_settings
from tests.conftest import REPO

MG = REPO / "tests" / "fixtures" / "mg"
NETWORK = {"opendata", "papers", "pdfs", "streets_osm", "pois_wiki"}


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(profile="moenchengladbach", cwd=Path("/nonexistent"))


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory, settings: Settings) -> Layout:
    root = tmp_path_factory.mktemp("mg_run")
    layout = replace(
        Layout.from_settings(settings),
        data_root=root / "data",
        cache_root=root / "cache",
        reference_root=MG,
    )
    bootstrap(layout)
    outcomes = run_pipeline(build_steps(settings, layout), settings)
    failed = [o for o in outcomes if o.step not in NETWORK and o.status != "ausgeführt"]
    assert not failed, [o.line() for o in failed]
    return layout


def test_the_profile_puts_the_second_city_in_its_own_folder(run: Layout) -> None:
    assert run.profile == "moenchengladbach"
    assert run.root.name == "moenchengladbach" and run.root.parent.name == "data"
    assert run.pdf_dir == run.cache_root / "moenchengladbach" / "pdf"
    assert run.http_cache == run.cache_root / "http.sqlite"  # geteilt, Schlüssel ist die URL


def test_bootstrap_takes_the_package_format(run: Layout) -> None:
    """Das Paket der zweiten Stadt bringt Stores mit; es gibt kein ``paper_with_text.json``."""
    assert run.papers.is_file() and run.texts.is_file()
    assert run.results_csv.is_file() and run.districts_source.suffix == ".zip"
    assert run.streets_directory is not None and run.streets_directory.is_file()
    assert run.district_names_csv is not None and run.district_names_csv.is_file()


def test_the_precincts_step_reads_the_shapefile_zip(run: Layout, settings: Settings) -> None:
    import json

    canonical = json.loads(run.precincts_geojson.read_text(encoding="utf-8"))
    assert canonical["crs"]["properties"]["name"] == "EPSG:25832"
    districts = {f["properties"]["wahlbezirk"] for f in canonical["features"]}
    assert districts == {2, 10, 22}
    names = {f["properties"]["wahlbezirk_name"] for f in canonical["features"]}
    assert names == {"Rheindahlen-Land", "Alter Markt/Gründerzeitviertel", "Amtsgericht/Innenstadt"}


def test_the_sums_per_district_match_the_source(run: Layout, settings: Settings) -> None:
    """Golden Master der Stufe: die Aggregation der Stimmbezirke gleicht der Wahlbezirks-CSV."""
    columns = settings.columns.results
    assert run.district_names_csv is not None
    expected = pl.read_csv(
        run.district_names_csv, separator=columns.sep, infer_schema=False, encoding="utf8"
    ).select(
        pl.col("gebiet-nr").cast(pl.Int64).alias(DISTRICT),
        pl.col("A").cast(pl.Int64).alias(ELIGIBLE),
        pl.col("B").cast(pl.Int64).alias(VOTERS),
        pl.col("D1").cast(pl.Int64).alias("CDU_Stimmen"),
        pl.col("D2").cast(pl.Int64).alias("SPD_Stimmen"),
        pl.col("D3").cast(pl.Int64).alias("GRUENE_Stimmen"),
    ).sort(DISTRICT)
    got = pl.read_parquet(run.voters).select(expected.columns).sort(DISTRICT)
    assert got.to_dicts() == expected.to_dicts()


def test_the_page_names_the_city_of_the_profile(run: Layout) -> None:
    page = run.site_index.read_text(encoding="utf-8")
    assert "Mönchengladbacher Ratsdokumenten" in page
    assert "Stadt Mönchengladbach" in page and "Düsseldorf" not in page
    assert page.count('id="bezirk-') == 3
    assert "Weitere Städte" in page and "Düsseldorf</a>" in page.replace("Düsseldorf", "Düsseldorf")


def test_the_summary_is_the_interface_of_the_second_city(run: Layout) -> None:
    import json

    payload = json.loads(run.site_summary.read_text(encoding="utf-8"))
    assert payload["city"]["slug"] == "moenchengladbach" and payload["city"]["ags"] == "05116000"
    assert payload["figures"]["districts"] == 3 and payload["figures"]["precincts"] == 17
    assert payload["regression"]["without"] is None  # exclude_districts ist leer (Frage 1.6)


def test_running_again_changes_nothing(run: Layout, settings: Settings) -> None:
    again = run_pipeline(build_steps(settings, run), settings)
    assert all(o.status == "übersprungen" for o in again)


# --- Übereinstimmung mit dem Straßenverzeichnis der Wahl ---------------------------------------


def test_directory_agreement_measures_the_geometry_against_the_directory(
    run: Layout, settings: Settings
) -> None:
    assert run.streets_directory is not None
    agreement = directory_agreement(
        run.streets, run.streets_directory, settings.columns.results, settings.precincts
    )
    assert 0.0 <= agreement.precinct_share <= 1.0
    assert 0.0 <= agreement.district_share <= 1.0
    assert agreement.district_share >= agreement.precinct_share  # gröber kann nur besser sein
    assert agreement.matched <= agreement.streets and agreement.streets > 0
    assert agreement.line()


def test_the_page_names_the_agreement_and_the_date_of_the_geometry(run: Layout) -> None:
    page = run.site_index.read_text(encoding="utf-8")
    assert "Straßenverzeichnis" in page and "08.06.2022" in page


def test_the_marker_share_of_the_sample_is_recorded(run: Layout) -> None:
    """Frage 1.5: in der Stichprobe vom 2026-10-12 trägt kein Dokument den Marker ``betrifft``.

    Ohne Marker durchsucht die Kette den ganzen Text (``after_marker`` schneidet dann nichts);
    der volle Lauf in Stufe G misst den Anteil über die echte Wahlperiode neu.
    """
    texts = pl.read_parquet(run.texts)
    with_marker = sum("betrifft" in t.lower() for t in texts.get_column("text").to_list())
    assert (with_marker, texts.height) == (0, 5)
