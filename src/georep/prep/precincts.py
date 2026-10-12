"""Stimmbezirksflächen jeder Quelle in eine kanonische Datei: der Schritt ``precincts``.

Jede Stadt liefert ihre Flächen anders: das eine Portal ein GeoJSON in EPSG:4647 mit drei Spalten
im Klartext, das nächste ein Shapefile-Zip in EPSG:25832, das nur eine fünfstellige Nummer kennt,
deren erste Stellen den Wahlbezirk tragen. Die Regeln dafür stehen im Profil (``[precincts]``);
hier entsteht daraus ``interim/stimmbezirke.geojson`` mit genau drei Eigenschaften
(``stimmbezirk``, ``wahlbezirk``, ``wahlbezirk_name``) und dem CRS der Quelle. Alles dahinter
(Overpass, GeoSearch, STRtree, Karte, Seite) kennt nur dieses Format.

Die Koordinaten bleiben unverändert: wer hier umprojizierte, rechnete zweimal und verschöbe den
Golden Master der Arbeit (docs/plans/01-staedte.md, § 2).
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import deal
import polars as pl
import shapefile
from pyproj import CRS

from georep.errors import SchemaError
from georep.geo import DISTRICT_NAME_PROPERTY, DISTRICT_PROPERTY, PRECINCT_PROPERTY
from georep.settings import Precincts, ResultsColumns


@dataclass(frozen=True)
class SourcePrecincts:
    """Die Flächen, wie die Quelle sie liefert: GeoJSON-Features und der Name ihres CRS."""

    features: list[dict[str, Any]]
    crs: str


def read_source(path: Path, rules: Precincts) -> SourcePrecincts:
    """Liest die Quelldatei nach ``rules.format``; eine neue Quellform ist eine weitere Funktion."""
    if rules.format == "shapefile-zip":
        return read_source_shapefile_zip(path, rules.member, rules.dbf_encoding)
    return read_source_geojson(path, rules.source_crs)


@deal.raises(SchemaError)
def read_source_geojson(path: Path, source_crs: str = "") -> SourcePrecincts:
    """Eine FeatureCollection, wie ein Open-Data-Portal sie liefert; ``crs``-Mitglied wenn vorhanden."""
    collection = json.loads(path.read_text(encoding="utf-8"))
    features = collection.get("features")
    if not isinstance(features, list) or not features:
        raise SchemaError(f"{path.name}: keine Features")
    crs = collection.get("crs")
    named = ""
    if isinstance(crs, dict):
        properties = crs.get("properties")
        if isinstance(properties, dict) and isinstance(properties.get("name"), str):
            named = str(properties["name"])
    return SourcePrecincts(features, named or source_crs)


@deal.raises(SchemaError)
def read_source_shapefile_zip(
    path: Path, member: str = "", dbf_encoding: str = "utf-8"
) -> SourcePrecincts:
    """Ein Shapefile aus dem Zip, ohne es auszupacken: pyshp liest ``.shp``, ``.dbf``, ``.shx``.

    ``member`` ist der Pfad des ``.shp`` im Archiv; ohne Angabe gilt das einzige. Das CRS kommt aus
    dem ``.prj`` (WKT) über pyproj, nicht aus einer Annahme.
    """
    with zipfile.ZipFile(path) as archive:
        shp_name = member or _single_shp(path, archive)
        stem = shp_name.removesuffix(".shp")
        parts = {
            suffix: archive.read(f"{stem}{suffix}")
            for suffix in (".shp", ".shx", ".dbf")
            if f"{stem}{suffix}" in archive.namelist()
        }
        missing = [s for s in (".shp", ".shx", ".dbf") if s not in parts]
        if missing:
            raise SchemaError(f"{path.name}: {stem} ohne {missing}")
        prj = f"{stem}.prj"
        if prj not in archive.namelist():
            raise SchemaError(f"{path.name}: {prj} fehlt, das CRS wäre geraten")
        crs = CRS.from_wkt(archive.read(prj).decode("utf-8", errors="replace"))
        with shapefile.Reader(
            shp=io.BytesIO(parts[".shp"]),
            shx=io.BytesIO(parts[".shx"]),
            dbf=io.BytesIO(parts[".dbf"]),
            encoding=dbf_encoding,
            encodingErrors="replace",
        ) as reader:
            features = [
                {
                    "type": "Feature",
                    "properties": dict(record.record.as_dict()),
                    "geometry": record.shape.__geo_interface__,
                }
                for record in reader.iterShapeRecords()
            ]
    if not features:
        raise SchemaError(f"{path.name}: {stem} ohne Geometrie")
    return SourcePrecincts(features, _crs_name(crs))


def _single_shp(path: Path, archive: zipfile.ZipFile) -> str:
    found = [name for name in archive.namelist() if name.endswith(".shp")]
    if len(found) != 1:
        raise SchemaError(
            f"{path.name}: {len(found)} Shapefiles im Archiv ({found}); "
            "precincts.member nennt das gewünschte"
        )
    return found[0]


def _crs_name(crs: CRS) -> str:
    """``EPSG:25832``, wenn pyproj den Code erkennt; sonst der WKT, den ``CRS`` wieder einliest."""
    code = crs.to_epsg()
    return f"EPSG:{code}" if code is not None else crs.to_wkt()


def is_number(text: str) -> bool:
    """Eine Folge von ASCII-Ziffern, die ``int`` lesen kann.

    Nicht ``str.isdigit``: das ist für ``²`` wahr, ``int('²')`` wirft (crosshair, 2026-10-12), und
    arabisch-indische Ziffern läse ``int`` zwar, eine Gebietsnummer besteht aber aus 0 bis 9.
    """
    return bool(text) and text.isascii() and text.isdigit()


@deal.pre(lambda precinct_id, start, stop: 0 <= start < stop, message="Ausschnitt [start, stop)")
@deal.post(lambda result: result > 0, message="Wahlbezirke sind positiv numeriert")
@deal.raises(SchemaError)
def district_from_id(precinct_id: str, start: int, stop: int) -> int:
    """Der Wahlbezirk als Zeichenausschnitt der Stimmbezirksnummer (Mönchengladbach ``10401`` → 4).

    votemanager führt den Wahlbezirk nicht als Spalte; die Zuordnung steckt in der Nummer
    (docs/plans/01-staedte.md, § 3.2). Für jede Stadt ist sie durch Summenvergleich bestätigt.
    """
    cut = precinct_id[start:stop]
    if not is_number(cut) or int(cut) <= 0:
        raise SchemaError(
            f"Stimmbezirk {precinct_id!r}: Zeichen {start} bis {stop} sind {cut!r}, "
            "keine Wahlbezirksnummer"
        )
    return int(cut)


def district_names_from_csv(
    path: Path, rules: Precincts, columns: ResultsColumns
) -> dict[int, str]:
    """Wahlbezirk → Name aus der Wahlbezirks-CSV der Quelle (votemanager: ``gebiet-nr;gebiet-name``)."""
    text = path.read_bytes().decode(columns.encoding)
    frame = pl.read_csv(io.BytesIO(text.encode("utf-8")), separator=columns.sep, infer_schema=False)
    missing = [
        c for c in (rules.names_id_column, rules.names_name_column) if c not in frame.columns
    ]
    if missing:
        raise SchemaError(f"{path.name}: Spalten fehlen: {missing}")
    names: dict[int, str] = {}
    for row in frame.iter_rows(named=True):
        number = str(row[rules.names_id_column]).strip()
        if not is_number(number):
            continue
        names[int(number)] = str(row[rules.names_name_column]).strip()
    if not names:
        raise SchemaError(f"{path.name}: keine Wahlbezirksnummern in {rules.names_id_column}")
    return names


def _canonical(result: dict[str, Any]) -> bool:
    features = result["features"]
    if not features:
        return False
    properties = [f["properties"] for f in features]
    keys = {PRECINCT_PROPERTY, DISTRICT_PROPERTY, DISTRICT_NAME_PROPERTY}
    ids = [p[PRECINCT_PROPERTY] for p in properties]
    return (
        all(set(p) == keys for p in properties)
        and len(set(ids)) == len(ids)
        and all(p[DISTRICT_PROPERTY] > 0 and p[DISTRICT_NAME_PROPERTY] for p in properties)
        and bool(result.get("crs"))
    )


@deal.post(
    _canonical,
    message="genau drei Eigenschaften, eindeutige Stimmbezirke, benannte Wahlbezirke, CRS gesetzt",
)
@deal.raises(SchemaError)
def canonical_precincts(
    source: SourcePrecincts, rules: Precincts, names: Mapping[int, str] | None = None
) -> dict[str, Any]:
    """Die kanonische FeatureCollection; Geometrie und CRS der Quelle bleiben, wie sie sind."""
    if not source.crs:
        raise SchemaError(
            "die Quelle nennt kein CRS; precincts.source_crs muss es sagen, sonst wird es geraten"
        )
    features: list[dict[str, Any]] = []
    for feature in source.features:
        properties = feature.get("properties") or {}
        if rules.id_property not in properties:
            raise SchemaError(
                f"Stimmbezirk ohne {rules.id_property!r}; vorhanden: {sorted(properties)}"
            )
        precinct_id = str(properties[rules.id_property]).strip()
        district = _district_of(precinct_id, properties, rules)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    PRECINCT_PROPERTY: precinct_id,
                    DISTRICT_PROPERTY: district,
                    DISTRICT_NAME_PROPERTY: _name_of(district, properties, rules, names),
                },
                "geometry": feature["geometry"],
            }
        )
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": source.crs}},
        "features": features,
    }


def _district_of(precinct_id: str, properties: Mapping[str, Any], rules: Precincts) -> int:
    if rules.district_from_id is not None:
        start, stop = rules.district_from_id
        return district_from_id(precinct_id, start, stop)
    if rules.district_property not in properties:
        raise SchemaError(
            f"Stimmbezirk {precinct_id}: {rules.district_property!r} fehlt; "
            "vorhanden: " + str(sorted(properties))
        )
    value = str(properties[rules.district_property]).strip()
    if not is_number(value):
        raise SchemaError(f"Stimmbezirk {precinct_id}: Wahlbezirk {value!r} ist keine Zahl")
    return int(value)


def _name_of(
    district: int,
    properties: Mapping[str, Any],
    rules: Precincts,
    names: Mapping[int, str] | None,
) -> str:
    if rules.names_from_results:
        if names is None or district not in names:
            raise SchemaError(
                f"Wahlbezirk {district}: kein Name in der Wahlbezirks-CSV "
                f"({sorted(names or {})[:5]}…)"
            )
        return names[district]
    if not str(properties.get(rules.name_property, "")).strip():
        raise SchemaError(f"Wahlbezirk {district}: {rules.name_property!r} fehlt oder ist leer")
    return str(properties[rules.name_property]).strip()
