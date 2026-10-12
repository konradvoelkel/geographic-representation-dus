"""Stimmbezirkstabelle und Flächen der Raumeinheiten auf der Mini-Fixture."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from georep.crosswalk import area_shares, district_weights
from georep.errors import EmptyResultError, SchemaError
from georep.geo import Area, Precinct, read_areas, read_precincts
from georep.layout import Layout
from georep.prep.context import (
    aggregate_context,
    district_variables,
    ordinal_score,
    precinct_table,
    read_context_table,
)
from georep.prep.voters import read_results_csv
from georep.settings import Settings, load_settings


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


# --- Tabelle der Quelle und gewichtetes Mittel ---------------------------------------------------

HEADER = "SRG_2021_Nr;SRG_2021_Name;65_bis_u80_Ant;ue80_Ant;Fluktuationsrate;Sozialer_HB"
MINIMAL = [
    "011001;Altstadt;9,8;4,8;50,7;mittel",
    "012001;Carlstadt;16,1;7,0;28,2;gering",
    "013001;Mit Komma;10,6;.;+55,4;hoch",  # anonymisiert und ein positives Vorzeichen
]


def _settings_for(tmp_path: Path, extra: str = "") -> Settings:
    """Settings mit genau zwei Variablen auf der kleinen Tabelle: eine Summe, ein Score."""
    (tmp_path / "settings.toml").write_text(
        "context.variables = [\n"
        '  { name = "anteil_65plus", label = "65+", unit = "%", kind = "sum",'
        ' columns = ["65_bis_u80_Ant", "ue80_Ant"] },\n'
        '  { name = "fluktuation", label = "Fluktuation", unit = "je 1000", kind = "value",'
        ' columns = ["Fluktuationsrate"] },\n'
        '  { name = "hb_score", label = "HB", unit = "Score", kind = "ordinal",'
        ' columns = ["Sozialer_HB"], scale = "handlungsbedarf" },\n'
        "]\n"
        'context.models = { main = ["trefferquote", "hb_score"], parties = ["trefferquote"],'
        ' single = ["hb_score"] }\n' + extra,
        encoding="utf-8",
    )
    return load_settings(cwd=tmp_path)


def _csv(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "tabelle.csv"
    path.write_bytes(("\r\n".join([HEADER, *rows]) + "\r\n").encode("utf-8"))
    return path


def test_read_context_table_converts_numbers_signs_and_levels(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path)
    frame = read_context_table(_csv(tmp_path, MINIMAL), settings.context)
    assert frame.columns == [
        "einheit",
        "einheit_name",
        "anteil_65plus",
        "fluktuation",
        "hb_score",
    ]
    assert frame.get_column("einheit").to_list() == ["011001", "012001", "013001"]
    assert frame.get_column("anteil_65plus").to_list() == pytest.approx([14.6, 23.1, None])
    assert frame.get_column("fluktuation").to_list() == pytest.approx([50.7, 28.2, 55.4])
    assert frame.get_column("hb_score").to_list() == [3.0, 1.0, 5.0]


def test_a_level_with_spaces_around_it_is_still_a_level(tmp_path: Path) -> None:
    """``_ordinal`` trimmt vor dem Nachschlagen; die Schlüssel der Zuordnung müssen es auch sein,
    sonst wird " hoch " still zu null statt zu 5 (Review 2026-10-12)."""
    settings = _settings_for(tmp_path)
    # „eher gering" kommt sonst nicht vor: so entscheidet allein die gepolsterte Schreibweise
    frame = read_context_table(
        _csv(tmp_path, [*MINIMAL, "014001;Mit Leerzeichen;5,0;1,0;20,0; eher gering "]),
        settings.context,
    )
    assert frame.get_column("hb_score").to_list() == [3.0, 1.0, 5.0, 2.0]
    assert frame.get_column("hb_score").null_count() == 0


def test_an_unknown_level_and_a_missing_column_are_schema_errors(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path)
    with pytest.raises(SchemaError, match="sehr hoch"):
        read_context_table(
            _csv(tmp_path, [*MINIMAL, "014001;Neu;5,0;1,0;20,0;sehr hoch"]), settings.context
        )
    without = tmp_path / "ohne.csv"
    without.write_bytes(b"SRG_2021_Nr;SRG_2021_Name\r\n011001;Altstadt\r\n")
    with pytest.raises(SchemaError, match="Spalten fehlen"):
        read_context_table(without, settings.context)


def test_aggregate_context_averages_with_the_weights_and_renormalises(tmp_path: Path) -> None:
    # max_missing_weight = 1: hier soll der Grenzfall "ganz ohne Wert" sichtbar werden, nicht fliegen
    settings = _settings_for(tmp_path, extra="context.max_missing_weight = 1.0\n")
    values = read_context_table(_csv(tmp_path, MINIMAL), settings.context)
    weights = pl.DataFrame(
        [(1, "011001", 0.25), (1, "012001", 0.75), (2, "013001", 1.0)],
        schema={"wahlkreis_id": pl.Int64, "einheit": pl.String, "gewicht": pl.Float64},
        orient="row",
    )
    frame = aggregate_context(weights, values, settings.context)
    assert frame.get_column("wahlkreis_id").to_list() == [1, 2]
    assert frame.get_column("anteil_65plus").to_list() == pytest.approx(
        [0.25 * 14.6 + 0.75 * 23.1, None]
    )
    assert frame.get_column("fluktuation").to_list() == pytest.approx(
        [0.25 * 50.7 + 0.75 * 28.2, 55.4]
    )
    assert frame.get_column("hb_score").to_list() == pytest.approx([0.25 * 3.0 + 0.75 * 1.0, 5.0])
    # Wahlbezirk 2 liegt ganz auf einer Einheit ohne Wert fuer anteil_65plus
    assert frame.get_column("anteil_65plus_fehlgewicht").to_list() == pytest.approx([0.0, 1.0])
    assert frame.columns[-1].endswith("_fehlgewicht")


def test_too_much_missing_weight_names_variable_and_district(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path, extra="context.max_missing_weight = 0.2\n")
    values = read_context_table(_csv(tmp_path, MINIMAL), settings.context)
    weights = pl.DataFrame(
        [(1, "011001", 0.7), (1, "013001", 0.3)],
        schema={"wahlkreis_id": pl.Int64, "einheit": pl.String, "gewicht": pl.Float64},
        orient="row",
    )
    with pytest.raises(EmptyResultError, match="anteil_65plus"):
        aggregate_context(weights, values, settings.context)
    # Unter der Schwelle renormiert das Mittel still auf die Einheiten mit Wert
    relaxed = _settings_for(tmp_path, extra="context.max_missing_weight = 0.4\n")
    frame = aggregate_context(weights, values, relaxed.context)
    assert frame.get_column("anteil_65plus").to_list() == pytest.approx([14.6])
    assert frame.get_column("anteil_65plus_fehlgewicht").to_list() == pytest.approx([0.3])


def test_ordinal_score_maps_levels_and_ignores_the_rest() -> None:
    scale = {"gering": 1, "hoch": 5}
    assert ordinal_score(" hoch ", scale) == 5
    assert ordinal_score(".", scale) is None


def test_district_variables_scale_the_voter_columns(tmp_path: Path) -> None:
    settings = load_settings(cwd=tmp_path)
    voters = pl.DataFrame(
        {"wahlkreis_id": [2, 1], "CDU_anteil": [0.25, 0.5], "AfD_anteil": [0.1, 0.2]}
    )
    with pytest.raises(SchemaError, match="GRUENE_anteil"):
        district_variables(voters, settings.context)
    only_two = settings.context.model_copy(
        update={"variables": [v for v in settings.context.variables if v.name in ("cdu", "afd")]}
    )
    frame = district_variables(voters, only_two)
    assert frame.get_column("wahlkreis_id").to_list() == [1, 2]
    assert frame.get_column("cdu").to_list() == pytest.approx([50.0, 25.0])
    assert frame.get_column("afd").to_list() == pytest.approx([20.0, 10.0])
