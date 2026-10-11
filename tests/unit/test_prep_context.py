"""Stimmbezirkstabelle und Flächen der Raumeinheiten auf der Mini-Fixture."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from georep.crosswalk import area_shares, district_weights
from georep.errors import SchemaError
from georep.geo import Area, Precinct, read_areas, read_precincts
from georep.layout import Layout
from georep.prep.context import precinct_table
from georep.prep.voters import read_results_csv
from georep.settings import Settings


def _precincts(mini_root: Path, settings: Settings) -> list[Precinct]:
    return read_precincts(
        mini_root / "external" / "Stimmbezirke_2025.geojson",
        settings.columns,
        settings.geo.working_crs,
    )


def _table(mini_root: Path, settings: Settings) -> pl.DataFrame:
    columns = settings.columns.results
    results = read_results_csv(mini_root / "external" / "Stimmbezirk_Wahlergebnis.csv", columns)
    return precinct_table(_precincts(mini_root, settings), results, columns)


def test_precinct_table_has_one_row_per_precinct_with_geometry(
    mini_root: Path, default_settings: Settings
) -> None:
    table = _table(mini_root, default_settings)
    assert table.columns == ["stimmbezirk_id", "wahlkreis_id", "wahlberechtigte"]
    assert table.height == len(_precincts(mini_root, default_settings)) == 22
    assert sorted(set(table.get_column("wahlkreis_id"))) == [1, 10, 38]
    assert bool((table.get_column("wahlberechtigte") > 0).all())
    # Briefwahlbezirke stehen in der CSV, haben aber keine Fläche und fehlen hier.
    assert table.get_column("stimmbezirk_id").str.len_chars().max() == 4  # vierstellig


def test_eligible_voters_per_district_equal_the_voters_table(
    mini_run: Layout, mini_root: Path, default_settings: Settings
) -> None:
    """Die Probe, die den Crosswalk trägt: die Summe über die Stimmbezirke ist der Nenner der Arbeit."""
    table = _table(mini_root, default_settings)
    summed = (
        table.group_by("wahlkreis_id").agg(pl.col("wahlberechtigte").sum()).sort("wahlkreis_id")
    )
    voters = pl.read_parquet(mini_run.voters).sort("wahlkreis_id")
    assert (
        summed.get_column("wahlberechtigte").to_list()
        == voters.get_column("Wahlberechtigte_insgesamt").to_list()
    )


def test_a_precinct_without_a_row_in_the_results_is_a_schema_error(
    mini_root: Path, default_settings: Settings
) -> None:
    columns = default_settings.columns.results
    results = read_results_csv(mini_root / "external" / "Stimmbezirk_Wahlergebnis.csv", columns)
    without = results.filter(pl.col(columns.precinct).str.strip_chars() != "1101")
    with pytest.raises(SchemaError, match="1101"):
        precinct_table(_precincts(mini_root, default_settings), without, columns)


def test_read_areas_keys_the_units_and_refuses_duplicates(
    mini_root: Path, default_settings: Settings, tmp_path: Path
) -> None:
    path = mini_root / "context" / default_settings.context.files.units.file
    key = default_settings.context.units.key
    units = read_areas(path, key, default_settings.geo.working_crs)
    assert len(units) == 24 and all(u.geometry.area > 0 for u in units)
    keys = {u.key for u in units}
    assert len(keys) == 24 and "011001" in keys and all(len(k) == 6 for k in keys)
    with pytest.raises(SchemaError, match="fehlt"):
        read_areas(path, "GIBTSNICHT", default_settings.geo.working_crs)
    doubled = json.loads(path.read_text(encoding="utf-8"))
    doubled["features"] = [doubled["features"][0], doubled["features"][0]]
    twice = tmp_path / "doppelt.geojson"
    twice.write_text(json.dumps(doubled), encoding="utf-8")
    with pytest.raises(SchemaError, match="doppelt"):
        read_areas(twice, key, default_settings.geo.working_crs)


def test_units_cover_the_precincts_and_weights_partition_each_district(
    mini_root: Path, default_settings: Settings
) -> None:
    context = default_settings.context
    precincts = _precincts(mini_root, default_settings)
    units = read_areas(
        mini_root / "context" / context.files.units.file,
        context.units.key,
        default_settings.geo.working_crs,
    )
    shares = area_shares([Area.of(p) for p in precincts], units, min_coverage=context.min_coverage)
    # Auf der Fixture bedecken die Einheiten jeden Stimmbezirk zu 0,99999 (2026-10-12).
    assert bool((shares.get_column("coverage") > 0.999).all())
    weights = district_weights(_table(mini_root, default_settings), shares)
    sums = weights.group_by("wahlkreis_id").agg(pl.col("gewicht").sum())
    assert sums.get_column("gewicht").to_list() == pytest.approx([1.0] * 3)
    assert sorted(set(weights.get_column("wahlkreis_id"))) == [1, 10, 38]
    assert weights.get_column("einheit").n_unique() == 24
