"""Stimmbezirksflächen jeder Quelle in eine kanonische Datei: der Schritt ``precincts``.

Jede Stadt liefert ihre Flächen anders: das eine Portal ein GeoJSON in EPSG:4647 mit drei Spalten
im Klartext, das nächste ein Shapefile-Zip in EPSG:25832, das nur eine fünfstellige Nummer kennt,
deren erste Stellen den Wahlbezirk tragen, und die dritte gar keine Datei, sondern die Antwort
einer ArcGIS-Operation in Esri-JSON (``identify``, docs/decisions.md, Punkt 59). Die Regeln dafür
stehen im Profil (``[precincts]``); hier entsteht daraus ``interim/stimmbezirke.geojson`` mit
genau drei Eigenschaften (``stimmbezirk``, ``wahlbezirk``, ``wahlbezirk_name``) und dem CRS der
Quelle. Alles dahinter (Overpass, GeoSearch, STRtree, Karte, Seite) kennt nur dieses Format.

Die Koordinaten bleiben unverändert: wer hier umprojizierte, rechnete zweimal und verschöbe den
Golden Master der Arbeit (docs/plans/01-staedte.md, § 2).
"""

from __future__ import annotations

import io
import json
import math
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import deal
import polars as pl
import shapefile
from pyproj import CRS

from georep.errors import SchemaError
from georep.geo import DISTRICT_NAME_PROPERTY, DISTRICT_PROPERTY, PRECINCT_PROPERTY
from georep.io import read_text_without_bom
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
    if rules.format == "esri-identify":
        return read_source_esri_identify(path, rules.source_crs)
    return read_source_geojson(path, rules.source_crs)


@deal.raises(SchemaError)
def read_json_source(path: Path) -> Any:
    """JSON einer Quelldatei: ohne BOM, und ein Fehler darin hat einen Text (Review 2026-10-14).

    Zwei Fälle, die beide Leser vorher als ``RaisesContractError`` **ohne Meldung** durchließen:
    ein Portal, das UTF-8 mit BOM ausliefert (``json.loads`` stolpert über U+FEFF), und eine
    halb geschriebene oder mit einer HTML-Fehlerseite überschriebene Datei. Beides ist ein
    Datenfall und keine Vertragsverletzung -- der Nutzer muss lesen können, **welche** Datei
    gemeint ist. ``UnicodeDecodeError`` ist ein ``ValueError``, ein Zweig deckt also beide.

    Das BOM fällt mit ``georep.io.read_text_without_bom`` weg, demselben Leser, mit dem die CSVs
    des Portals gelesen werden; eigene Logik dafür gäbe es damit zweimal.
    """
    try:
        return json.loads(read_text_without_bom(path, "utf-8"))
    except ValueError as error:
        raise SchemaError(f"{path.name}: kein lesbares JSON ({error})") from error


@deal.raises(SchemaError)
def read_source_geojson(path: Path, source_crs: str = "") -> SourcePrecincts:
    """Eine FeatureCollection, wie ein Open-Data-Portal sie liefert; ``crs``-Mitglied wenn vorhanden."""
    collection = read_json_source(path)
    features = collection.get("features") if isinstance(collection, dict) else None
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


# --- Esri-JSON: die Antwort der ArcGIS-Operation ``identify`` (Punkt 59) -------------------------
#
# Esri-JSON kennt kein Feld für „Loch". Eine Fläche ist eine Liste von Ringen, und das **Vorzeichen
# der Ringfläche** sagt, was der Ring ist: äußere Ringe laufen im Uhrzeigersinn (negative Fläche
# nach der Gaußschen Trapezformel), innere gegen den Uhrzeigersinn (ArcGIS REST API, Geometry
# Objects). GeoJSON (RFC 7946) hält es genau umgekehrt und schachtelt Löcher in die Fläche, zu der
# sie gehören. Beides ist hier zu tun, und beides ist prüfbar: die Umlaufrichtung am Vorzeichen,
# die Schachtelung an der Fläche, die dabei erhalten bleibt.

Ring = Sequence[Sequence[float]]
"""Ein Esri-Ring: geschlossene Folge von Punkten, jeder mit mindestens x und y."""


def _are_numbers(values: Sequence[Any]) -> bool:
    """Endliche Zahlen, keine Wahrheitswerte.

    ``math.isfinite`` ist der Punkt: ``NaN`` und ``Infinity`` sind ``float`` und kämen sonst
    durch -- Pythons ``json`` schreibt und liest sie, auch wenn der Standard sie nicht kennt. Ein
    ``NaN`` in einer Koordinate macht die Ringfläche ``NaN``, und ``NaN`` ist weder kleiner noch
    größer als null: der Ring wäre damit weder außen noch innen und fiele **still** aus der
    Fläche heraus (Review 2026-10-14).
    """
    return all(
        isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v) for v in values
    )


def is_ring(ring: Ring) -> bool:
    """Ein Ring, wie Esri ihn schreibt: vier endliche Punkte oder mehr, geschlossen.

    Vier, weil drei Ecken plus der wiederholte Anfangspunkt das kleinste Polygon sind. Mit drei
    Punkten wäre es eine Linie; shapely machte daraus still eine Fläche ohne Fläche, und das
    Vorzeichen, an dem die Umwandlung außen von innen unterscheidet, wäre null. **Endlich**, weil
    das Vorzeichen eines ``NaN`` nichts ist: der Ring wäre weder außen noch innen (Review
    2026-10-14). Der Leser der Antwort prüft dasselbe und sagt es als ``SchemaError``, bevor der
    Vertrag greift.
    """
    if len(ring) < 4 or any(len(point) < 2 or not _are_numbers(point[:2]) for point in ring):
        return False
    return ring[0][0] == ring[-1][0] and ring[0][1] == ring[-1][1]


def _all_rings(rings: Sequence[Ring]) -> bool:
    return bool(rings) and all(is_ring(ring) for ring in rings)


@deal.pre(is_ring, message="ein geschlossener Ring mit vier Punkten oder mehr")
@deal.safe
def ring_signed_area(ring: Ring) -> float:
    """Die Gaußsche Trapezformel: bei Esri ist ein äußerer Ring negativ, ein Loch positiv.

    Dieselbe Zahl ist zweierlei: das Vorzeichen unterscheidet außen von innen, der Betrag ist die
    Fläche, die die Umwandlung nicht ändern darf.
    """
    total = 0.0
    for first, second in zip(ring, ring[1:], strict=False):
        total += first[0] * second[1] - second[0] * first[1]
    return total / 2.0


def _point_and_ring(point: Sequence[float], ring: Ring) -> bool:
    return len(point) >= 2 and is_ring(ring)


@deal.pre(_point_and_ring, message="ein Punkt mit x und y und ein geschlossener Ring")
@deal.safe
def point_in_ring(point: Sequence[float], ring: Ring) -> bool:
    """Strahlverfahren: schneidet der Strahl nach +x den Ring ungerade oft, liegt der Punkt innen.

    Ohne shapely, damit dieses Modul für eine Ja-Nein-Frage keine Geometriebibliothek lädt und
    crosshair es prüfen kann (``nox -s verify``). Ein Punkt genau auf dem Rand ist hier nicht
    entschieden; darum fragt ``_enclosing_ring`` nach jedem Punkt des Lochs und nicht nach einem.
    """
    x, y = point[0], point[1]
    inside = False
    for first, second in zip(ring, ring[1:], strict=False):
        y1, y2 = first[1], second[1]
        if (y1 > y) != (y2 > y):  # die Kante kreuzt die Höhe des Punktes, also ist y2 != y1
            crossing = first[0] + (y - y1) / (y2 - y1) * (second[0] - first[0])
            if x < crossing:
                inside = not inside
    return inside


def _rings_keep_their_area(rings: Sequence[Ring], result: dict[str, Any]) -> bool:
    """Die Netto-Fläche der Ringe (außen minus Löcher) steht auch im Ergebnis.

    Esri zählt außen negativ, GeoJSON positiv; darum das Vorzeichen vor der Summe. Ein Loch, das
    dem falschen äußeren Ring zugeschlagen würde, fiele hier nicht auf -- es bleibt ein Loch.
    Eines, das als eigene Fläche durchrutschte, fällt auf: es zählte dann plus statt minus.
    """
    expected = -sum(ring_signed_area(ring) for ring in rings)
    polygons = (
        result["coordinates"]
        if result["type"] == "MultiPolygon"
        else [result["coordinates"]]  # ein Polygon ist eine Liste von Ringen
    )
    got = sum(ring_signed_area(ring) for polygon in polygons for ring in polygon)
    return abs(got - expected) <= 1e-6 * max(1.0, abs(expected))


@deal.pre(
    _all_rings, message="mindestens ein Ring, jeder geschlossen und mit vier Punkten oder mehr"
)
@deal.ensure(_rings_keep_their_area, message="die Fläche der Ringe bleibt erhalten")
@deal.raises(SchemaError)
def geometry_from_esri_rings(rings: Sequence[Ring]) -> dict[str, Any]:
    """Esri-Ringe als GeoJSON-Geometrie: ``Polygon`` bei einem äußeren Ring, sonst ``MultiPolygon``.

    Jeder Ring wird gedreht (Esri außen im Uhrzeigersinn, GeoJSON außen gegen den Uhrzeigersinn),
    und jedes Loch kommt zum kleinsten äußeren Ring, der es enthält. Mönchengladbach hat beides in
    derselben Ecke: Stimmbezirk 11003 trägt ein Loch von 1 641 m², und an dieser Stelle liegt die
    zweite, 1 639 m² große Fläche von 11001. Ohne die Schachtelung wäre das Loch eine eigene
    Fläche und die Stadt um 1 641 m² größer; ohne die Unterscheidung am Vorzeichen fiele die
    zweite Fläche von 11001 weg. Beide Ringe sind getrennt digitalisiert und darum nicht
    deckungsgleich (gemessen am 2026-10-14: 1,2 m² Überschneidung).
    """
    areas = [ring_signed_area(ring) for ring in rings]
    flat = [index for index, area in enumerate(areas) if area == 0.0]
    if flat:
        raise SchemaError(
            f"Ring {flat} ohne Fläche: ohne Vorzeichen ist nicht zu sagen, ob er außen oder "
            "innen liegt"
        )
    outer = [(ring, area) for ring, area in zip(rings, areas, strict=True) if area < 0.0]
    if not outer:
        raise SchemaError(
            f"{len(rings)} Ringe, alle gegen den Uhrzeigersinn: kein äußerer Ring; "
            "Esri schreibt äußere Ringe im Uhrzeigersinn"
        )
    parts = [[_turned(ring)] for ring, _ in outer]
    for ring, area in zip(rings, areas, strict=True):
        if area > 0.0:
            parts[_enclosing_ring(ring, outer)].append(_turned(ring))
    if len(parts) == 1:
        return {"type": "Polygon", "coordinates": parts[0]}
    return {"type": "MultiPolygon", "coordinates": parts}


def _turned(ring: Ring) -> list[list[float]]:
    """Derselbe Ring in der anderen Umlaufrichtung, auf x und y gekürzt (GeoJSON ist zweidimensional)."""
    return [[point[0], point[1]] for point in reversed(ring)]


def _enclosing_ring(hole: Ring, outer: Sequence[tuple[Ring, float]]) -> int:
    """Der kleinste äußere Ring, der das Loch enthält; verschachtelte Flächen sind damit eindeutig."""
    found = [
        (abs(area), index)
        for index, (ring, area) in enumerate(outer)
        if any(point_in_ring(point, ring) for point in hole)
    ]
    if not found:
        raise SchemaError(
            f"ein Ring gegen den Uhrzeigersinn ({abs(ring_signed_area(hole)):.0f} Flächeneinheiten) "
            f"liegt in keinem der {len(outer)} äußeren Ringe; so ist er weder Loch noch Fläche"
        )
    return min(found)[1]


@deal.raises(SchemaError)
def read_source_esri_identify(path: Path, source_crs: str = "") -> SourcePrecincts:
    """Die Antwort der Operation ``identify``: ``results`` mit ``attributes`` und ``geometry.rings``.

    Warum ``identify`` und nicht ``query`` steht in docs/decisions.md, Punkt 59. Das CRS hängt
    hier an jeder Geometrie (``spatialReference``) und nicht am Dokument wie bei GeoJSON; die
    Eigenschaften sind die ``attributes`` des Treffers, so wie der Dienst sie formatiert (eine
    ``OBJECTID`` kommt als Text).
    """
    payload = read_json_source(path)
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results:
        raise SchemaError(f"{path.name}: keine results; eine identify-Antwort hat results[]")
    features: list[dict[str, Any]] = []
    for index, entry in enumerate(results):
        if not isinstance(entry, dict):
            raise SchemaError(f"{path.name}: results[{index}] ist kein Objekt")
        attributes = entry.get("attributes")
        features.append(
            {
                "type": "Feature",
                "properties": dict(attributes) if isinstance(attributes, dict) else {},
                "geometry": geometry_from_esri_rings(_checked_rings(path.name, index, entry)),
            }
        )
    return SourcePrecincts(features, _wkid_crs(path.name, results) or source_crs)


def _checked_rings(name: str, index: int, entry: Mapping[str, Any]) -> list[Ring]:
    """Die Ringe eines Treffers, geprüft, bevor eine Formel darauf rechnet.

    Eine fremde Antwort wird hier zum ``SchemaError``, nicht zum ``TypeError`` in der
    Trapezformel und nicht zur Vertragsverletzung: ein Dienst, der etwas anderes schickt als
    angekündigt, ist ein Datenfall und kein Programmierfehler.
    """
    geometry = entry.get("geometry")
    rings = geometry.get("rings") if isinstance(geometry, dict) else None
    if not isinstance(rings, list) or not rings:
        raise SchemaError(
            f"{name}: results[{index}] ohne geometry.rings; die Abfrage braucht returnGeometry=true"
        )
    checked: list[Ring] = []
    for number, ring in enumerate(rings):
        where = f"{name}: results[{index}], Ring {number}"
        if not isinstance(ring, list) or not all(
            isinstance(point, list) and len(point) >= 2 and _are_numbers(point[:2])
            for point in ring
        ):
            raise SchemaError(f"{where} ist keine Folge von Punkten [x, y] mit endlichen Zahlen")
        if len(ring) < 4:
            raise SchemaError(f"{where}: {len(ring)} Punkte, ein Ring hat vier oder mehr")
        if not is_ring(ring):
            raise SchemaError(f"{where} ist nicht geschlossen: {ring[0][:2]} != {ring[-1][:2]}")
        checked.append(ring)
    return checked


def _wkid_crs(name: str, results: Sequence[Any]) -> str:
    """``EPSG:<wkid>`` aus ``spatialReference``; ``latestWkid`` gilt vor ``wkid``.

    Esri führt neben den EPSG-Codes eigene Nummern (102100 für EPSG:3857); wo beide stehen, ist
    ``latestWkid`` der EPSG-Code. Zwei verschiedene Codes in einer Antwort sind ein Fehler -- die
    kanonische Datei trägt genau ein CRS. Steht keiner da, gilt ``precincts.source_crs``.
    """
    codes = set()
    for entry in results:
        geometry = entry.get("geometry") if isinstance(entry, dict) else None
        reference = geometry.get("spatialReference") if isinstance(geometry, dict) else None
        if not isinstance(reference, dict):
            continue
        code = reference.get("latestWkid", reference.get("wkid"))
        if isinstance(code, int) and not isinstance(code, bool):
            codes.add(code)
    if len(codes) > 1:
        raise SchemaError(f"{name}: {sorted(codes)} -- mehr als ein CRS in einer Antwort")
    return f"EPSG:{codes.pop()}" if codes else ""


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
    text = read_text_without_bom(path, columns.encoding)
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
        if not feature.get("geometry"):
            raise SchemaError(f"Stimmbezirk {precinct_id}: kein Geometrie-Mitglied im Feature")
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
