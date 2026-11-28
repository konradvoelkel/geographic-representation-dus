"""Vorhaben 16: Hausnummer → Stimm- und Wahlbezirk (``prep.addresses``, ``georep pack --addresses``).

Drei Gruppen. **Lesen**: GebRef nur für die Gemeinde, mit Nummer und Zusatz. **Zuordnen**: über
``crosswalk.point_shares`` mit Band 0; eine Hausnummer auf der Grenze zweier Stimmbezirke steht mit
beiden da, eine außerhalb fällt weg; das Paket trägt keine Koordinate. **Nachschlagen** wie das
Messskript (``genau``, ``ohne_zusatz``, ``mit_zusatz``, ``nein``, ``strasse_unbekannt``). Dazu das
Paket hin und zurück: ``pack --addresses`` aus dem Archiv der Straßenpunkte, ``bootstrap`` nach
``external/adressen/``.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import polars as pl
import pytest
from shapely.geometry import box

from georep.bootstrap import bootstrap
from georep.geo import Precinct
from georep.layout import Layout
from georep.pack import PackError, pack_addresses
from georep.prep.addresses import (
    ADDRESS_DIR,
    ADDRESS_FILE,
    ADDRESS_SCHEMA,
    EXACT,
    NO_NUMBER,
    OTHER_SUFFIX,
    SOURCES_FILE,
    UNKNOWN_STREET,
    WITHOUT_SUFFIX,
    AddressBook,
    address_files,
    address_table,
    read_house_numbers,
)
from georep.prep.streetpoints import GEBREF_MEMBER, street_point_files
from georep.settings import Settings, archive_name

HERE = ("05", "1", "11", "000")
ELSEWHERE = ("05", "9", "11", "000")


def _line(
    ags: tuple[str, str, str, str], street: str, number: str, suffix: str, x: float, y: float
) -> str:
    land, region, kreis, gemeinde = ags
    return (
        f"N;DENW01;A;{land};Land;{region};RB;{kreis};Kreis;{gemeinde};Ort;0000;;0001;{street};"
        f"{number};{suffix};32;{x:.3f};{y:.3f};2026-10-01\n"
    )


LINES = [
    _line(HERE, "Aachener Str.", "1", "", 10.0, 10.0),
    _line(HERE, "Aachener Straße", "3", "A", 20.0, 10.0),
    _line(HERE, "Aachener Straße", "100", "", 100.0, 50.0),  # auf der Grenze: beide Stimmbezirke
    _line(HERE, "Aachener Straße", "200", "", 160.0, 10.0),  # im zweiten Wahlbezirk
    _line(HERE, "Bahnweg", "2", "", 40.0, 40.0),
    _line(HERE, "Bahnweg", "x", "", 40.0, 40.0),  # keine Nummer
    _line(HERE, "Nirgendwo", "1", "", 900.0, 900.0),  # in keinem Stimmbezirk
    _line(ELSEWHERE, "Aachener Straße", "7", "", 15.0, 15.0),
]


def _archive(path: Path, lines: list[str]) -> Path:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(GEBREF_MEMBER, "".join(lines))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buffer.getvalue())
    return path


def _precincts() -> list[Precinct]:
    return [
        Precinct("0101", 1, "Eins", box(0, 0, 100, 100)),
        Precinct("0201", 2, "Zwei", box(100, 0, 200, 100)),
    ]


def test_only_the_municipality_with_number_and_suffix_is_read(tmp_path: Path) -> None:
    houses = read_house_numbers(_archive(tmp_path / "gebref.zip", LINES), "05111000")
    assert houses.columns == ["strasse", "nr", "zusatz", "x", "y"]
    assert houses.select("strasse", "nr", "zusatz").rows() == [
        ("aachener straße", 1, ""),
        ("aachener straße", 3, "a"),
        ("aachener straße", 100, ""),
        ("aachener straße", 200, ""),
        ("bahnweg", 2, ""),
        ("nirgendwo", 1, ""),
    ]


def test_each_address_gets_the_precincts_of_its_point(tmp_path: Path) -> None:
    houses = read_house_numbers(_archive(tmp_path / "gebref.zip", LINES), "05111000")
    table, outside = address_table(houses, _precincts())
    assert table.schema == pl.Schema(ADDRESS_SCHEMA)
    assert outside == 1  # Nirgendwo 1
    assert "x" not in table.columns and "y" not in table.columns
    assert table.rows() == [
        ("aachener straße", 1, "", "0101", 1),
        ("aachener straße", 3, "a", "0101", 1),
        ("aachener straße", 100, "", "0101", 1),
        ("aachener straße", 100, "", "0201", 2),
        ("aachener straße", 200, "", "0201", 2),
        ("bahnweg", 2, "", "0101", 1),
    ]


@pytest.mark.parametrize(
    ("term", "number", "suffix", "status", "districts"),
    [
        ("aachener straße", 3, "a", EXACT, {1}),
        ("aachener str.", 1, "", EXACT, {1}),  # die Variante des Wörterbuchs
        ("aachener straße", 1, "b", WITHOUT_SUFFIX, {1}),  # Zusatz gibt es nicht, die Nummer schon
        ("aachener straße", 3, "", OTHER_SUFFIX, set()),  # 3 gibt es nur als 3a
        ("aachener straße", 100, "", EXACT, {1, 2}),  # auf der Grenze
        ("aachener straße", 5, "", NO_NUMBER, set()),
        ("kölner straße", 1, "", UNKNOWN_STREET, set()),
    ],
)
def test_an_address_is_looked_up_like_the_measurement(
    tmp_path: Path, term: str, number: int, suffix: str, status: str, districts: set[int]
) -> None:
    houses = read_house_numbers(_archive(tmp_path / "gebref.zip", LINES), "05111000")
    book = AddressBook.from_table(address_table(houses, _precincts())[0])
    assert book.locate(term, number, suffix) == (status, frozenset(districts))


def _precincts_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "stimmbezirk": p.precinct_id,
                            "wahlbezirk": p.district_id,
                            "wahlbezirk_name": p.district_name,
                        },
                        "geometry": json.loads(json.dumps(p.geometry.__geo_interface__)),
                    }
                    for p in _precincts()
                ],
                "crs": {"type": "name", "properties": {"name": "EPSG:25832"}},
            }
        ),
        encoding="utf-8",
    )


def test_pack_and_bootstrap_carry_the_addresses_there_and_back(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    archive = street_point_files(layout).archives / archive_name(default_settings.street_points.url)
    _archive(archive, LINES)
    _precincts_file(layout.target_view(default_settings).precincts_geojson)
    target = tmp_path / "paket"
    report = pack_addresses(layout, default_settings, target)
    names = [f.name for f in report.files]
    assert names == [f"external/{ADDRESS_DIR}/{n}" for n in (ADDRESS_FILE, SOURCES_FILE)]
    assert dict(report.figures)["Hausnummern"] == 6
    assert dict(report.figures)["außerhalb der Stimmbezirke"] == 1
    packed = pl.read_parquet(target / names[0])
    assert packed.height == 6 and set(packed.columns) == set(ADDRESS_SCHEMA)
    sources = json.loads((target / names[1]).read_text(encoding="utf-8"))
    assert sources["ags"] == default_settings.city.ags
    assert sources["archiv"]["url"] == default_settings.street_points.url
    assert sources["archiv"]["bytes"] == archive.stat().st_size
    assert (target / "README.md").is_file()
    fresh = Layout(tmp_path / "neu", tmp_path / "neu-cache", tmp_path / "reference")
    bootstrap(fresh, needs_dictionary=False, seed_corpus=False, addresses=target)
    copied = address_files(fresh)
    assert copied.table.read_bytes() == (target / names[0]).read_bytes()
    assert copied.sources.read_bytes() == (target / names[1]).read_bytes()


def test_pack_refuses_without_archive_or_house_numbers(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    with pytest.raises(PackError, match="street_points"):
        pack_addresses(layout, default_settings, tmp_path / "leer")
    off = default_settings.model_copy(
        update={"places": default_settings.places.model_copy(update={"house_numbers": False})}
    )
    with pytest.raises(PackError, match="house_numbers"):
        pack_addresses(layout, off, tmp_path / "aus")
