"""Der Schritt ``precincts``: aus GeoJSON oder Shapefile-Zip die kanonischen Stimmbezirke.

Das Shapefile im Test schreibt pyshp selbst; so hängt der Test an keiner Datei, die jemand
abrufen müsste, und prüft trotzdem den Weg, den Mönchengladbach nimmt (Option 01, Stufe B).
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
import shapefile
from pydantic import ValidationError

from georep.errors import SchemaError
from georep.geo import read_canonical_precincts
from georep.prep.precincts import (
    canonical_precincts,
    district_from_id,
    district_names_from_csv,
    read_source,
    read_source_geojson,
    read_source_shapefile_zip,
)
from georep.settings import Precincts, ResultsColumns, Settings, load_settings

MG_CRS_WKT = (
    'PROJCS["ETRS89_UTM_zone_32N",GEOGCS["GCS_ETRS_1989",DATUM["D_ETRS_1989",'
    'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],'
    'UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
    'PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",0.0],'
    'PARAMETER["Central_Meridian",9.0],PARAMETER["Scale_Factor",0.9996],'
    'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]'
)
VOTEMANAGER = Precincts(
    format="shapefile-zip",
    id_property="Nummer",
    district_from_id=(1, 3),
    names_from_results=True,
)


def _square(x: float, y: float) -> list[list[tuple[float, float]]]:
    return [[(x, y), (x + 100, y), (x + 100, y + 100), (x, y + 100), (x, y)]]


def _shapefile_zip(path: Path, numbers: tuple[str, ...], *, prj: bool = True) -> Path:
    """Ein Zip mit einem Shapefile aus je einem Quadrat pro Nummer, wie Mönchengladbach es liefert."""
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf) as writer:
        writer.field("OBJECTID", "N")
        writer.field("Nummer", "C", size=5)
        for index, number in enumerate(numbers):
            writer.poly(_square(310_000.0 + index * 200, 5_662_000.0))
            writer.record(index + 1, number)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Wahlen/Stimmbezirke_MG.shp", shp.getvalue())
        archive.writestr("Wahlen/Stimmbezirke_MG.shx", shx.getvalue())
        archive.writestr("Wahlen/Stimmbezirke_MG.dbf", dbf.getvalue())
        if prj:
            archive.writestr("Wahlen/Stimmbezirke_MG.prj", MG_CRS_WKT)
    return path


# --- district_from_id -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("precinct_id", "cut", "expected"),
    [("10401", (1, 3), 4), ("32201", (1, 3), 22), ("0011", (0, 3), 1), ("2501", (0, 3), 250)],
)
def test_district_from_id_cuts_the_number(
    precinct_id: str, cut: tuple[int, int], expected: int
) -> None:
    assert district_from_id(precinct_id, *cut) == expected


@pytest.mark.parametrize("precinct_id", ["10001", "B0097", "1", "", "1²3", "1٣4"])
def test_district_from_id_refuses_a_cut_that_is_no_number(precinct_id: str) -> None:
    """Auch Ziffern, die keine sind: crosshair fand am 2026-10-12 ``district_from_id('²', 0, 1)``.

    ``'²'.isdigit()`` ist wahr, ``int('²')`` wirft; und arabisch-indische Ziffern würde ``int``
    zwar lesen, eine Stimmbezirksnummer besteht aber aus ASCII-Ziffern.
    """
    with pytest.raises(SchemaError, match="Wahlbezirksnummer"):
        district_from_id(precinct_id, 1, 3)


# --- Quellformen ----------------------------------------------------------------------------


def test_geojson_source_keeps_the_crs_member_of_the_portal(mini_root: Path) -> None:
    source = read_source_geojson(mini_root / "external" / "Stimmbezirke_2025.geojson")
    assert len(source.features) == 22 and "4647" in source.crs


def test_geojson_without_crs_member_falls_back_to_the_profile(tmp_path: Path) -> None:
    path = tmp_path / "flaechen.geojson"
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": [{"properties": {}}]}),
        encoding="utf-8",
    )
    assert read_source_geojson(path, "EPSG:25832").crs == "EPSG:25832"
    assert read_source_geojson(path).crs == ""
    path.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
    with pytest.raises(SchemaError, match="keine Features"):
        read_source_geojson(path)


def test_shapefile_zip_is_read_without_unpacking_and_brings_its_crs(tmp_path: Path) -> None:
    path = _shapefile_zip(tmp_path / "Wahlen.zip", ("10401", "10402", "32201"))
    source = read_source_shapefile_zip(path)
    assert source.crs == "EPSG:25832"
    assert [f["properties"]["Nummer"] for f in source.features] == ["10401", "10402", "32201"]
    assert source.features[0]["geometry"]["type"] == "Polygon"
    assert source == read_source(path, VOTEMANAGER)


def test_shapefile_zip_without_prj_is_refused_instead_of_guessing(tmp_path: Path) -> None:
    path = _shapefile_zip(tmp_path / "ohne-prj.zip", ("10401",), prj=False)
    with pytest.raises(SchemaError, match="prj"):
        read_source_shapefile_zip(path)


def test_two_shapefiles_in_one_zip_ask_for_the_member(tmp_path: Path) -> None:
    path = _shapefile_zip(tmp_path / "zwei.zip", ("10401",))
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("Wahlen/Wahllokale_MG.shp", b"x")
    with pytest.raises(SchemaError, match="precincts.member"):
        read_source_shapefile_zip(path)
    assert read_source_shapefile_zip(path, "Wahlen/Stimmbezirke_MG.shp").features


# --- canonical_precincts --------------------------------------------------------------------


def test_duesseldorf_keeps_its_coordinates_and_names(
    mini_root: Path, default_settings: Settings
) -> None:
    source = read_source(
        mini_root / "external" / "Stimmbezirke_2025.geojson", default_settings.precincts
    )
    canonical = canonical_precincts(source, default_settings.precincts)
    assert len(canonical["features"]) == 22
    assert {f["properties"]["wahlbezirk"] for f in canonical["features"]} == {1, 10, 38}
    assert canonical["crs"]["properties"]["name"] == source.crs
    # Kein Reprojizieren: die Geometrie ist dieselbe Struktur wie in der Quelle (Golden Master)
    assert [f["geometry"] for f in canonical["features"]] == [
        f["geometry"] for f in source.features
    ]
    names = {f["properties"]["wahlbezirk_name"] for f in canonical["features"]}
    assert all(name for name in names) and len(names) == 3


def test_votemanager_rules_take_the_district_from_the_number_and_the_name_from_the_csv(
    tmp_path: Path,
) -> None:
    source = read_source_shapefile_zip(
        _shapefile_zip(tmp_path / "w.zip", ("10401", "10402", "32201"))
    )
    canonical = canonical_precincts(source, VOTEMANAGER, {4: "Venn", 22: "Wickrath-Land"})
    properties = [f["properties"] for f in canonical["features"]]
    assert [p["wahlbezirk"] for p in properties] == [4, 4, 22]
    assert [p["wahlbezirk_name"] for p in properties] == ["Venn", "Venn", "Wickrath-Land"]
    assert set(properties[0]) == {"stimmbezirk", "wahlbezirk", "wahlbezirk_name"}
    with pytest.raises(SchemaError, match="kein Name"):
        canonical_precincts(source, VOTEMANAGER, {4: "Venn"})


def test_canonical_refuses_a_source_without_crs_or_without_the_id(tmp_path: Path) -> None:
    source = read_source_shapefile_zip(_shapefile_zip(tmp_path / "w.zip", ("10401",)))
    with pytest.raises(SchemaError, match="kein CRS"):
        canonical_precincts(type(source)(source.features, ""), VOTEMANAGER, {4: "Venn"})
    wrong = Precincts(
        format="shapefile-zip", id_property="Nr", district_from_id=(1, 3), names_from_results=True
    )
    with pytest.raises(SchemaError, match="ohne 'Nr'"):
        canonical_precincts(source, wrong, {4: "Venn"})


def test_a_feature_without_geometry_is_a_schema_error(tmp_path: Path) -> None:
    """Sonst stolperte erst der Vertrag mit einem leeren RaisesContractError (Review 2026-10-12)."""
    path = tmp_path / "flaechen.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:25832"}},
                "features": [{"properties": {"Nr": "10401", "Name": "Venn"}, "geometry": None}],
            }
        ),
        encoding="utf-8",
    )
    rules = Precincts(id_property="Nr", district_from_id=(1, 3), names_from_results=True)
    with pytest.raises(SchemaError, match="Geometrie"):
        canonical_precincts(read_source_geojson(path), rules, {4: "Venn"})


def test_the_canonical_file_is_what_read_precincts_wants(tmp_path: Path) -> None:
    source = read_source_shapefile_zip(_shapefile_zip(tmp_path / "w.zip", ("10401", "32201")))
    target = tmp_path / "stimmbezirke.geojson"
    target.write_text(
        json.dumps(canonical_precincts(source, VOTEMANAGER, {4: "Venn", 22: "Wickrath-Land"})),
        encoding="utf-8",
    )
    precincts = read_canonical_precincts(target, "EPSG:25832")
    assert [p.precinct_id for p in precincts] == ["10401", "32201"]
    assert [p.district_id for p in precincts] == [4, 22]
    assert [p.district_name for p in precincts] == ["Venn", "Wickrath-Land"]
    assert all(p.geometry.is_valid and p.geometry.area == pytest.approx(10_000) for p in precincts)


def test_read_precincts_names_the_step_when_the_properties_are_the_source_ones(
    mini_root: Path,
) -> None:
    with pytest.raises(SchemaError, match="georep run shapes"):
        read_canonical_precincts(mini_root / "external" / "Stimmbezirke_2025.geojson", "EPSG:25832")


# --- Namen aus der Wahlbezirks-CSV ----------------------------------------------------------


def test_district_names_come_from_the_votemanager_csv(tmp_path: Path) -> None:
    path = tmp_path / "wahlbezirke.csv"
    path.write_text(
        "datum;wahl;gebiet-nr;gebiet-name\n"
        "14.09.2025;Ratswahl;01;Rheindahlen/Mennrath\n"
        "14.09.2025;Ratswahl;04;Venn\n"
        "14.09.2025;Ratswahl;;Summe\n",
        encoding="utf-8",
    )
    columns = ResultsColumns(
        encoding="utf-8",
        district="x",
        city_district="",
        eligible="A",
        voters="B",
        parties={"CDU": "D1"},
    )
    assert district_names_from_csv(path, VOTEMANAGER, columns) == {
        1: "Rheindahlen/Mennrath",
        4: "Venn",
    }
    path.write_text("datum;wahl\n14.09.2025;Ratswahl\n", encoding="utf-8")
    with pytest.raises(SchemaError, match="Spalten fehlen"):
        district_names_from_csv(path, VOTEMANAGER, columns)


# --- Settings-Validatoren -------------------------------------------------------------------


def test_precincts_rules_demand_exactly_one_way_to_the_district_and_the_name() -> None:
    with pytest.raises(ValidationError, match="district_from_id"):
        Precincts(id_property="Nummer", name_property="Name")
    with pytest.raises(ValidationError, match="district_from_id"):
        Precincts(id_property="Nummer", district_property="Nr", district_from_id=(1, 3))
    with pytest.raises(ValidationError, match="names_from_results"):
        Precincts(id_property="Nummer", district_from_id=(1, 3))
    with pytest.raises(ValidationError, match=r"\[start, stop\)"):
        Precincts(id_property="Nummer", district_from_id=(3, 1), names_from_results=True)


def test_the_default_profile_reads_its_geojson_with_the_portal_columns(tmp_path: Path) -> None:
    rules = load_settings(cwd=tmp_path).precincts
    assert rules.format == "geojson" and rules.district_from_id is None
    assert rules.id_property == "Stimm-/ Wahlbezirk"
    assert rules.district_property == "Kommunalwahlbezirk Nr."
    assert rules.name_property == "Kommunalwahlbezirk Name"
