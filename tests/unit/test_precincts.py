"""Der Schritt ``precincts``: aus GeoJSON, Shapefile-Zip oder Esri-JSON die kanonischen Stimmbezirke.

Das Shapefile im Test schreibt pyshp selbst; so hängt der Test an keiner Datei, die jemand
abrufen müsste, und prüft trotzdem den Weg, den Mönchengladbach nahm (Option 01, Stufe B). Die
Esri-Ringe sind das Gegenstück dazu: dort ist die **echte** Antwort des Dienstes die Eingabe
(``tests/fixtures/mg/``, Punkt 62), weil die Ringfolge einer Stadt nicht nachzubauen ist.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import deal
import pytest
import shapefile
from pydantic import ValidationError
from shapely.geometry import shape

from georep.errors import SchemaError
from georep.geo import read_canonical_precincts
from georep.prep.precincts import (
    canonical_precincts,
    district_from_id,
    district_names_from_csv,
    geometry_from_esri_rings,
    is_ring,
    point_in_ring,
    read_source,
    read_source_esri_identify,
    read_source_geojson,
    read_source_shapefile_zip,
    ring_signed_area,
)
from georep.settings import Precincts, ResultsColumns, Settings, load_settings
from tests.conftest import REPO

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


@pytest.mark.parametrize(
    "crs",
    [
        {"type": "name", "properties": {"name": 25832}},  # Zahl statt Text
        {"type": "name", "properties": "EPSG:25832"},  # kein Objekt
        {"type": "name"},  # ohne properties
        "EPSG:25832",  # crs selbst kein Objekt
    ],
)
def test_a_crs_member_in_an_unexpected_shape_falls_back_instead_of_breaking(
    tmp_path: Path, crs: object
) -> None:
    """Beide Prüfungen am ``crs``-Mitglied sind nötig, nicht eine von beiden.

    Ein Portal, das ``crs`` anders schreibt als erwartet, darf keinen ``AttributeError`` oder
    ``TypeError`` auslösen: dann gilt das CRS des Profils (Mutant ``and`` zu ``or``, 2026-10-13).
    """
    path = tmp_path / "flaechen.geojson"
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": [{"properties": {}}], "crs": crs}),
        encoding="utf-8",
    )
    assert read_source_geojson(path, "EPSG:25832").crs == "EPSG:25832"


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


# --- Esri-Ringe (Punkt 62) ------------------------------------------------------------------

IDENTIFY = Precincts(
    format="esri-identify",
    source_crs="EPSG:25832",
    id_property="Nummer",
    district_from_id=(1, 3),
    names_from_results=True,
)
IDENTIFY_FILE = "Stimmbezirke_Kommunalwahl_2025.json"
# Die beiden mehrringigen Flächen der Stadt, aus derselben Antwort geschnitten; sie liegen bei den
# aufgezeichneten Antworten und nicht im Paket, weil ihr Wahlbezirk (10) nicht zur Fixture gehört.
MULTIRING = REPO / "tests" / "fixtures" / "http" / "identify_mg_mehrringig.json"


def _clockwise(x: float, y: float, size: float) -> list[list[float]]:
    """Ein Quadrat im Uhrzeigersinn, wie Esri einen äußeren Ring schreibt (negative Fläche)."""
    return [[x, y], [x, y + size], [x + size, y + size], [x + size, y], [x, y]]


def _identify(
    path: Path,
    rings_per_area: dict[str, list[list[list[float]]]],
    reference: dict[str, Any] | None = None,
) -> Path:
    """Eine ``identify``-Antwort, wie der Dienst sie schickt: ``results`` mit Ringen je Treffer."""
    if reference is None:
        reference = {"wkid": 25832, "latestWkid": 25832}
    path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "layerId": 16,
                        "displayFieldName": "Nummer",
                        "value": number,
                        "attributes": {"OBJECTID": str(index + 1), "Nummer": number},
                        "geometryType": "esriGeometryPolygon",
                        "geometry": {"rings": rings, "spatialReference": reference},
                    }
                    for index, (number, rings) in enumerate(rings_per_area.items())
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_the_service_answer_of_the_second_city_is_read_like_a_file(mg_root: Path) -> None:
    """Die 17 Stimmbezirke der drei Wahlbezirke, wie der Dienst sie am 2026-10-14 lieferte."""
    source = read_source_esri_identify(mg_root / "external" / IDENTIFY_FILE)
    assert source.crs == "EPSG:25832"  # aus spatialReference, nicht aus dem Profil
    numbers = sorted(f["properties"]["Nummer"] for f in source.features)
    assert len(numbers) == 17 and numbers[0] == "10401" and numbers[-1] == "32305"
    assert {n[1:3] for n in numbers} == {"04", "09", "23"}
    assert {f["geometry"]["type"] for f in source.features} == {"Polygon"}
    # Die Attribute des Dienstes bleiben, wie er sie formatiert: die OBJECTID kommt als Text
    assert all(isinstance(f["properties"]["OBJECTID"], str) for f in source.features)
    assert source == read_source(mg_root / "external" / IDENTIFY_FILE, IDENTIFY)


def test_the_area_of_the_converted_rings_is_the_area_of_the_rings(mg_root: Path) -> None:
    """Unabhängiges Orakel: die Trapezformel über die Quellringe, nicht der Weg des Codes.

    Esri zählt äußere Ringe negativ und Löcher positiv; die Netto-Fläche ist darum das negierte
    Vorzeichen der Summe über **alle** Ringe der Antwort. shapely rechnet sie nach der Umwandlung
    aus der Schachtelung aus -- stimmen beide Zahlen, ist kein Loch zur Fläche geworden.
    """
    payload = json.loads((mg_root / "external" / IDENTIFY_FILE).read_text(encoding="utf-8"))
    rings = [ring for entry in payload["results"] for ring in entry["geometry"]["rings"]]
    expected = -sum(ring_signed_area(ring) for ring in rings)
    source = read_source_esri_identify(mg_root / "external" / IDENTIFY_FILE)
    got = sum(shape(f["geometry"]).area for f in source.features)
    assert got == pytest.approx(expected, abs=0.01)
    assert got == pytest.approx(20_024_527.60, abs=0.01)  # 20,02 km², gemessen am 2026-10-14
    assert all(shape(f["geometry"]).is_valid for f in source.features)


def test_a_clockwise_second_ring_is_an_area_and_a_counter_clockwise_one_is_a_hole() -> None:
    """Die beiden mehrringigen Flächen Mönchengladbachs, dieselbe Ecke, zwei verschiedene Fälle.

    11001 trägt einen zweiten Ring **im** Uhrzeigersinn: eine zweite Fläche, ein MultiPolygon.
    11003 trägt einen gegen den Uhrzeigersinn: ein Loch im einen Polygon. Nach dem Betrag der
    Fläche sind beide Ringe gleich groß -- nur das Vorzeichen unterscheidet sie, und genau daran
    hängt, ob 1 639 m² dazukommen oder 1 641 m² fehlen.
    """
    payload = json.loads(MULTIRING.read_text(encoding="utf-8"))
    by_number = {e["attributes"]["Nummer"]: e["geometry"]["rings"] for e in payload["results"]}
    assert sorted(by_number) == ["11001", "11003"]

    both = {number: geometry_from_esri_rings(rings) for number, rings in by_number.items()}
    assert both["11001"]["type"] == "MultiPolygon" and len(both["11001"]["coordinates"]) == 2
    assert all(len(polygon) == 1 for polygon in both["11001"]["coordinates"])  # kein Loch
    assert both["11003"]["type"] == "Polygon" and len(both["11003"]["coordinates"]) == 2  # ein Loch

    assert shape(both["11001"]).area == pytest.approx(196_437.50, abs=0.01)
    assert shape(both["11003"]).area == pytest.approx(189_140.42, abs=0.01)
    # Dieselbe Ecke, getrennt digitalisiert: die zweite Fläche von 11001 füllt das Loch von 11003
    # fast genau aus (1,2 m² Überschneidung, gemessen am 2026-10-14).
    assert shape(both["11001"]).intersection(shape(both["11003"])).area == pytest.approx(
        1.2, abs=0.1
    )


def test_the_winding_of_the_result_is_the_one_geojson_asks_for() -> None:
    """RFC 7946: äußere Ringe gegen den Uhrzeigersinn (positiv), Löcher im Uhrzeigersinn."""
    outer = _clockwise(0.0, 0.0, 100.0)
    hole = list(reversed(_clockwise(40.0, 40.0, 20.0)))  # gegen den Uhrzeigersinn: ein Loch
    geometry = geometry_from_esri_rings([outer, hole])
    assert geometry["type"] == "Polygon"
    exterior, interior = geometry["coordinates"]
    assert ring_signed_area(exterior) > 0.0 and ring_signed_area(interior) < 0.0
    assert shape(geometry).area == pytest.approx(100 * 100 - 20 * 20)


def test_a_hole_belongs_to_the_smallest_outer_ring_that_holds_it() -> None:
    """Zwei geschachtelte Flächen: das Loch gehört zur inneren, sonst stimmte die Fläche zweimal nicht."""
    big = _clockwise(0.0, 0.0, 100.0)
    small = _clockwise(10.0, 10.0, 50.0)
    hole = list(reversed(_clockwise(20.0, 20.0, 10.0)))
    geometry = geometry_from_esri_rings([big, small, hole])
    assert geometry["type"] == "MultiPolygon"
    assert [len(polygon) for polygon in geometry["coordinates"]] == [1, 2]
    assert shape(geometry).area == pytest.approx(100 * 100 + 50 * 50 - 10 * 10)


@pytest.mark.parametrize(
    ("rings", "message"),
    [
        ([list(reversed(_clockwise(0.0, 0.0, 10.0)))], "kein äußerer Ring"),
        # drei Punkte auf einer Geraden: geschlossen, lang genug, Fläche null
        (
            [_clockwise(0.0, 0.0, 10.0), [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 0.0]]],
            "ohne Fläche",
        ),
        (
            [_clockwise(0.0, 0.0, 10.0), list(reversed(_clockwise(100.0, 100.0, 5.0)))],
            "liegt in keinem",
        ),
    ],
)
def test_rings_that_say_nothing_about_inside_and_outside_are_refused(
    rings: list[list[list[float]]], message: str
) -> None:
    """Ohne Vorzeichen (Fläche null), ohne äußeren Ring oder mit einem Loch im Nichts: Datenfall."""
    with pytest.raises(SchemaError, match=message):
        geometry_from_esri_rings(rings)


@pytest.mark.parametrize(
    ("ring", "message"),
    [
        ([[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]], "3 Punkte, ein Ring hat vier"),
        ([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], "nicht geschlossen"),
        ([[0.0, 0.0], [1.0], [1.0, 1.0], [0.0, 0.0]], "Folge von Punkten"),
        ([[0.0, 0.0], "x", [1.0, 1.0], [0.0, 0.0]], "Folge von Punkten"),
    ],
)
def test_a_ring_the_formula_cannot_read_is_a_schema_error(
    tmp_path: Path, ring: list[Any], message: str
) -> None:
    """Weniger als vier Punkte, nicht geschlossen, kein Punktpaar: der Leser sagt es, nicht ein Vertrag.

    Ein Vertrag wäre hier falsch: eine fremde Antwort ist ein Datenfall, und ``contracts = "off"``
    liefe sonst in einen ``TypeError`` mitten in der Trapezformel.
    """
    path = _identify(tmp_path / "identify.json", {"10401": [ring]})
    with pytest.raises(SchemaError, match=message):
        read_source_esri_identify(path)


@pytest.mark.parametrize(
    "payload",
    [
        {"results": []},
        {"results": "viele"},
        {"error": {"code": 400, "message": "Unable to complete operation."}},
        [],
    ],
)
def test_an_answer_without_results_is_a_schema_error(tmp_path: Path, payload: Any) -> None:
    path = tmp_path / "identify.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SchemaError, match="keine results"):
        read_source_esri_identify(path)


def test_a_result_without_geometry_names_the_parameter_that_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "identify.json"
    path.write_text(
        json.dumps({"results": [{"attributes": {"Nummer": "10401"}}]}), encoding="utf-8"
    )
    with pytest.raises(SchemaError, match="returnGeometry=true"):
        read_source_esri_identify(path)


def test_the_crs_comes_from_the_spatial_reference_and_latest_wins(tmp_path: Path) -> None:
    """``latestWkid`` ist der EPSG-Code, ``wkid`` darf eine Esri-Nummer sein (102100 = 3857)."""
    rings = {"10401": [_clockwise(0.0, 0.0, 10.0)]}
    esri = _identify(tmp_path / "esri.json", rings, {"wkid": 102100, "latestWkid": 3857})
    assert read_source_esri_identify(esri).crs == "EPSG:3857"
    only = _identify(tmp_path / "only.json", rings, {"wkid": 25832})
    assert read_source_esri_identify(only).crs == "EPSG:25832"


def test_without_a_spatial_reference_the_profile_decides(tmp_path: Path) -> None:
    path = _identify(tmp_path / "ohne.json", {"10401": [_clockwise(0.0, 0.0, 10.0)]}, {})
    assert read_source_esri_identify(path, "EPSG:25832").crs == "EPSG:25832"
    assert read_source_esri_identify(path).crs == ""


def test_two_crs_in_one_answer_are_refused(tmp_path: Path) -> None:
    """Die kanonische Datei trägt genau ein CRS; zwei Codes wären eine Annahme, welcher gilt."""
    path = tmp_path / "zwei.json"
    path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "attributes": {"Nummer": number},
                        "geometry": {
                            "rings": [_clockwise(0.0, 0.0, 10.0)],
                            "spatialReference": {"wkid": wkid},
                        },
                    }
                    for number, wkid in (("10401", 25832), ("10402", 4647))
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SchemaError, match="mehr als ein CRS"):
        read_source_esri_identify(path)


def test_a_ring_that_is_no_ring_breaks_the_contract_of_the_pure_functions() -> None:
    """Die reinen Funktionen verlangen einen Ring; geprüft hat ihn der Leser (Design by Contract)."""
    assert not is_ring([[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]])  # drei Punkte
    assert not is_ring([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])  # offen
    assert not is_ring([[0.0, 0.0], [0.0], [1.0, 1.0], [0.0, 0.0]])  # Punkt ohne y
    with pytest.raises(deal.PreContractError):
        ring_signed_area([[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]])
    with pytest.raises(deal.PreContractError):
        geometry_from_esri_rings([])
    with pytest.raises(deal.PreContractError):
        point_in_ring([0.0], _clockwise(0.0, 0.0, 10.0))


def test_point_in_ring_counts_the_crossings() -> None:
    square = _clockwise(0.0, 0.0, 10.0)
    assert point_in_ring([5.0, 5.0], square)
    assert not point_in_ring([15.0, 5.0], square)
    assert not point_in_ring([5.0, 15.0], square)
    assert not point_in_ring([-5.0, 5.0], square)


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


def test_a_district_name_stays_text_even_when_it_looks_like_a_number(tmp_path: Path) -> None:
    """Die CSV wird ohne Schema-Erkennung gelesen: ``0815`` ist ein Name, keine 815.

    Polars würde die Spalte sonst als Zahl lesen und die führende Null verlieren; die Namen der
    Wahlbezirke sind Text (Mutant ``infer_schema=False`` zu ``True``, 2026-10-13).
    """
    path = tmp_path / "wahlbezirke.csv"
    path.write_text(
        "datum;wahl;gebiet-nr;gebiet-name\n14.09.2025;Ratswahl;07;0815\n", encoding="utf-8"
    )
    columns = ResultsColumns(
        encoding="utf-8",
        district="x",
        city_district="",
        eligible="A",
        voters="B",
        parties={"CDU": "D1"},
    )
    assert district_names_from_csv(path, VOTEMANAGER, columns) == {7: "0815"}


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


@pytest.mark.parametrize(
    ("form", "key", "value"),
    [
        ("geojson", "member", "a/b.shp"),
        ("geojson", "dbf_encoding", "latin-1"),
        ("esri-identify", "member", "a/b.shp"),
        ("esri-identify", "dbf_encoding", "latin-1"),
        ("shapefile-zip", "source_crs", "EPSG:25832"),
    ],
)
def test_the_source_form_decides_which_keys_the_profile_may_set(
    form: str, key: str, value: str
) -> None:
    """Ein Schlüssel an der falschen Quellform ist ein stiller Irrtum, also ein Fehler (Punkt 62).

    ``source_crs`` an einem Shapefile sieht aus, als gälte es; es gilt das ``.prj`` im Zip. Und
    ``dbf_encoding`` an einem Esri-JSON hat nichts, worauf es wirken könnte.
    """
    rules: dict[str, Any] = {
        "format": form,
        "id_property": "Nummer",
        "district_from_id": (1, 3),
        "names_from_results": True,
    }
    assert Precincts.model_validate(rules).format == form
    with pytest.raises(ValidationError, match=key):
        Precincts.model_validate(rules | {key: value})


def test_a_disabled_step_keeps_the_keys_of_the_period_profile() -> None:
    """``precincts.enabled = false`` (Option 02) prüft nichts: der Schritt ``shapes`` entfällt."""
    assert not Precincts(enabled=False, member="a/b.shp", source_crs="EPSG:4647").enabled


def test_the_default_profile_reads_its_geojson_with_the_portal_columns(tmp_path: Path) -> None:
    rules = load_settings(cwd=tmp_path).precincts
    assert rules.format == "geojson" and rules.district_from_id is None
    assert rules.id_property == "Stimm-/ Wahlbezirk"
    assert rules.district_property == "Kommunalwahlbezirk Nr."
    assert rules.name_property == "Kommunalwahlbezirk Name"


# --- der Zuschnitt der Fixture (Punkt 62, Befund 2) -----------------------------------------


def test_the_fixture_maker_cuts_the_identify_answer_and_writes_json(
    tmp_path: Path, mg_root: Path
) -> None:
    """``write_identify_json`` schneidet die ``results`` und fasst keine Zahl an.

    Vorher schob ``make_mini_mg`` die Flächen jeder Quellform durch ``write_shapefile_zip``: mit
    der ``identify``-Antwort hieß das ``BadZipFile``, und im Erfolgsfall läge ein Zip unter dem
    Namen einer JSON-Datei. Der Test ist die Gegenprobe auf die Datei im Repo: derselbe Zuschnitt
    muss sie **zeichengleich** wieder herstellen, sonst ist die Fixture nicht reproduzierbar.
    """
    from tests.fixtures.make_mini_mg import write_identify_json

    committed = mg_root / "external" / IDENTIFY_FILE
    numbers = {
        str(e["attributes"]["Nummer"])
        for e in json.loads(committed.read_text(encoding="utf-8"))["results"]
    }
    again = tmp_path / IDENTIFY_FILE
    write_identify_json(committed, again, numbers, "Nummer")
    assert again.read_text(encoding="utf-8") == committed.read_text(encoding="utf-8")

    one = tmp_path / "einer.json"
    write_identify_json(committed, one, {"10404"}, "Nummer")
    source = read_source_esri_identify(one)
    assert [f["properties"]["Nummer"] for f in source.features] == ["10404"]


# --- Befund 4: NaN und Infinity in einer Koordinate ------------------------------------------


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_a_coordinate_that_is_not_finite_is_refused(tmp_path: Path, bad: str) -> None:
    """Pythons ``json`` liest ``NaN`` und ``Infinity``, obwohl der Standard sie nicht kennt.

    Eine solche Koordinate macht die Ringfläche ``NaN``, und ``NaN`` ist weder kleiner noch
    größer als null: der Ring wäre weder außen noch innen und fiele **still** aus der Fläche
    heraus -- bei einer mehrringigen Fläche ohne jede Meldung, bei einer einringigen als
    irreführendes „kein äußerer Ring" (Review 2026-10-14).
    """
    path = tmp_path / "identify.json"
    path.write_text(
        '{"results":[{"attributes":{"Nummer":"10401"},"geometry":{"rings":[[[0,0],[0,'
        + bad
        + "],[10,10],[10,0],[0,0]]]}}]}",
        encoding="utf-8",
    )
    with pytest.raises(SchemaError, match="endlichen Zahlen"):
        read_source_esri_identify(path)


def test_the_contract_of_the_pure_functions_demands_finite_rings() -> None:
    """Dieselbe Bedingung als Vertrag: ohne sie rechnete die Trapezformel ``NaN`` aus."""
    nan_ring = [[0.0, 0.0], [0.0, float("nan")], [10.0, 10.0], [10.0, 0.0], [0.0, 0.0]]
    assert not is_ring(nan_ring)
    assert not is_ring([[0.0, 0.0], [float("inf"), 0.0], [1.0, 1.0], [0.0, 0.0]])
    with pytest.raises(deal.PreContractError):
        ring_signed_area(nan_ring)
    with pytest.raises(deal.PreContractError):
        geometry_from_esri_rings([nan_ring])


# --- Befund 5: BOM und kaputtes JSON in beiden JSON-Lesern -----------------------------------


@pytest.mark.parametrize(
    "reader", [read_source_geojson, read_source_esri_identify], ids=["geojson", "esri-identify"]
)
@pytest.mark.parametrize(
    ("content", "ids"),
    [
        (b"", "leer"),
        (b"<html>Wartung</html>", "html"),
        (b'{"results":[', "abgebrochen"),
        (b"\xff\xfe{}", "falsche Kodierung"),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_a_file_that_is_no_json_names_itself(
    tmp_path: Path, reader: Any, content: bytes, ids: str
) -> None:
    """Vorher endete beides als ``RaisesContractError`` **ohne Text**: welche Datei, stand nicht da.

    Eine halb geschriebene Datei, eine HTML-Fehlerseite unter dem Namen der Antwort oder falsche
    Bytes sind Datenfälle. ``UnicodeDecodeError`` ist ein ``ValueError``, ein Zweig deckt beide.
    """
    path = tmp_path / "flaechen.json"
    path.write_bytes(content)
    with pytest.raises(SchemaError, match="kein lesbares JSON"):
        reader(path)


@pytest.mark.parametrize("reader", [read_source_geojson, read_source_esri_identify])
def test_a_utf8_bom_in_front_of_the_json_is_no_error(tmp_path: Path, reader: Any) -> None:
    """Ein Portal, das UTF-8 mit BOM ausliefert, ist kein Fehlerfall, sondern ein Portal.

    Dasselbe BOM nimmt ``georep.io.read_text_without_bom`` den CSVs des Portals weg; ohne ihn
    stolperte ``json.loads`` über U+FEFF, und die Meldung nannte eine Spalte 1.
    """
    ring = _clockwise(0.0, 0.0, 10.0)
    payload = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:25832"}},
        "features": [{"properties": {"Nummer": "10401"}, "geometry": {"type": "Polygon"}}],
        "results": [
            {
                "attributes": {"Nummer": "10401"},
                "geometry": {"rings": [ring], "spatialReference": {"wkid": 25832}},
            }
        ],
    }
    path = tmp_path / "mit-bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8"))
    source = reader(path)
    assert [f["properties"]["Nummer"] for f in source.features] == ["10401"]
    assert source.crs == "EPSG:25832"


def test_a_json_list_instead_of_an_object_is_a_schema_error(tmp_path: Path) -> None:
    """``[]`` ist lesbares JSON und hat kein ``get``; das endete als ``AttributeError``."""
    path = tmp_path / "liste.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(SchemaError, match="keine Features"):
        read_source_geojson(path)
    with pytest.raises(SchemaError, match="keine results"):
        read_source_esri_identify(path)


# --- Befund 9 und 17: welchem äußeren Ring ein Loch gehört ------------------------------------


def test_a_hole_goes_to_the_ring_that_holds_all_of_it_not_one_corner() -> None:
    """Befund 17: ein einzelner Punkt im Ring genügt nicht, sonst entscheidet die Fläche falsch.

    Hier ragt eine Ecke des Lochs in einen **kleineren** äußeren Ring, der es nicht enthält. Mit
    ``any`` traf dieser kleinere Ring, und weil die Zuordnung den kleinsten Treffer nahm, bekam er
    das Loch -- das Ergebnis war ein Polygon mit einem Loch, das darüber hinausragt. Jetzt
    schließt schon das umschließende Rechteck ihn aus, und ``all`` wäre die zweite Schranke.
    """
    big = _clockwise(0.0, 0.0, 100.0)
    small = _clockwise(90.0, 90.0, 20.0)  # kleiner und überlappt die Ecke von big
    hole = list(reversed(_clockwise(80.0, 80.0, 19.0)))  # ganz in big, eine Ecke auch in small
    assert point_in_ring(hole[2], small) and not point_in_ring(hole[0], small)

    geometry = geometry_from_esri_rings([big, small, hole])
    assert geometry["type"] == "MultiPolygon"
    # Das Loch sitzt im ersten Teil (big), nicht im zweiten (small)
    assert [len(polygon) for polygon in geometry["coordinates"]] == [2, 1]
    assert shape(geometry).area == pytest.approx(100 * 100 + 20 * 20 - 19 * 19)


def test_a_hole_that_shares_an_edge_still_finds_its_ring() -> None:
    """Der Rückfall auf ``any``: auf dem Rand ist das Strahlverfahren nicht entschieden.

    Dieses Loch teilt die rechte und die obere Kante seines Rings; drei seiner fünf Punkte liegen
    damit genau auf dem Rand und gelten als außen. ``all`` findet so keinen Ring -- ohne den
    Rückfall wäre eine gültige Fläche ein ``SchemaError``.
    """
    outer = _clockwise(0.0, 0.0, 100.0)
    hole = list(reversed(_clockwise(50.0, 50.0, 50.0)))
    assert not all(point_in_ring(point, outer) for point in hole)
    assert any(point_in_ring(point, outer) for point in hole)

    geometry = geometry_from_esri_rings([outer, hole])
    assert geometry["type"] == "Polygon" and len(geometry["coordinates"]) == 2
    assert shape(geometry).area == pytest.approx(100 * 100 - 50 * 50)
