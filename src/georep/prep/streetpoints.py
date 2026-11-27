"""Straßenpunkte und Ortsnamen der Startkarte (``docs/plan-startseite-2026-11.md``, § 4.1, § 4.2).

Ein Punkt der Startkarte ist ein **Ort = (Begriff, Wahlbezirk)**. Für eine Straße liegt er am
Medoid der Hauskoordinaten dieser Straße im Wahlbezirk, auf ``round_m`` gerundet; die Koordinaten
kommen aus den Gebäudereferenzen NRW (GebRef, Geobasis NRW, Datenlizenz Deutschland Zero 2.0), je
Hausnummer ein Punkt. Gelesen wird nur die Gemeinde des Profils (``city.ags``), und behalten wird
je (Straße, Wahlbezirk) **ein** Punkt und die Zahl der Hausnummern, keine Hausnummer: ein Punkt an
einer Adresse wäre die Tabelle „Dokument × Adresse", die Vorhaben 16 ausschließt (§ 4.2).

Die Namen der Stadtteile (Beschriftung der Grundkarte) kommen als Name und Punkt auf der Fläche aus
einer GeoJSON-Datei der Stadt, wo das Profil eine nennt; sonst beschriftet die Karte die
Stadtbezirke. Beides schreibt der Netzschritt ``street_points`` (nur mit
``street_points.fetch``), ``georep pack --street-points`` packt es nach
``snapshots/<stadt>-strassenpunkte/``, und ``bootstrap`` legt das Paket nach
``external/startkarte/``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import re
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

import deal
import numpy as np
import polars as pl
import shapely
from shapely.geometry import shape

from georep.geo import LONLAT, Precinct, transformer
from georep.io import digest
from georep.layout import Layout

GEBREF_MEMBER = "gebref.txt"  # die eine Datei im Archiv mit einer Zeile je Hausnummer
# Felder einer Zeile von gebref.txt (Semikolon, UTF-8): Land, Regierungsbezirk, Kreis und Gemeinde
# ergeben zusammen den amtlichen Gemeindeschlüssel; dann Straßenname, Hausnummer, Zusatz, Zone,
# Ost- und Nordwert in EPSG:25832.
_LAND, _REGION, _KREIS, _GEMEINDE = 3, 5, 7, 9
_STREET = 14
_EAST, _NORTH = 18, 19
_FIELDS = 21
GEBREF_CRS = "EPSG:25832"
STREET_COLUMNS = ("strasse", "wahlkreis_id", "x", "y", "hausnummern")
LABEL_COLUMNS = ("name", "x", "y")
STREET_POINTS_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen der beiden Dateien ändern
START_DIR = "startkarte"  # unter external/ und cache_root/: die Dateien der Startkarte
POINTS_FILE = "strassenpunkte.parquet"
LABELS_FILE = "stadtteile.parquet"
SOURCES_FILE = "quellen.json"
START_FILES = (POINTS_FILE, LABELS_FILE, SOURCES_FILE)
_MEDOID_BLOCK = 2_000  # Zeilen je Block der Abstandsmatrix, damit sie klein bleibt


class StreetPointFiles(NamedTuple):
    archives: Path  # die geladenen Dateien, von allen Profilen geteilt
    points: Path
    labels: Path
    sources: Path


def street_point_files(layout: Layout) -> StreetPointFiles:
    """Wo die Dateien der Startkarte liegen: ``external/startkarte/``, geladen in ``cache_root``."""
    folder = layout.external / START_DIR
    return StreetPointFiles(
        layout.cache_root / START_DIR,
        folder / POINTS_FILE,
        folder / LABELS_FILE,
        folder / SOURCES_FILE,
    )


_ABBREVIATION = re.compile(r"str\.(?=$|[\s-])")
_DASH = re.compile(r"\s*-\s*")
_SPACE = re.compile(r"\s+")


@deal.pure
@deal.post(lambda result: result == result.strip() and result == result.lower())
def normalize_street(name: str) -> str:
    """Ein Straßenname so, wie das Wörterbuch ihn als Langform führt: klein, ``straße`` ausgeschrieben.

    GebRef schreibt ``Ückendorfer Str.`` neben ``Halbuschstraße``, das Wörterbuch kennt die
    Langform und die Variante mit ``str.``; ein Ort der Startkarte trägt die Langform (§ 4.2).
    """
    text = name.strip().lower().replace("strasse", "straße")
    text = _ABBREVIATION.sub("straße", text)
    text = _DASH.sub("-", text)
    return _SPACE.sub(" ", text).strip()


def ags_of(parts: Sequence[str]) -> str:
    """Der Gemeindeschlüssel einer Zeile: Land, Regierungsbezirk, Kreis, Gemeinde."""
    return parts[_LAND] + parts[_REGION] + parts[_KREIS] + parts[_GEMEINDE]


def _lines(archive: Path) -> Iterator[str]:
    with zipfile.ZipFile(archive) as opened, opened.open(GEBREF_MEMBER) as raw:
        yield from io.TextIOWrapper(raw, encoding="utf-8")


def read_house_points(archive: Path, ags: str) -> pl.DataFrame:
    """Straße (normalisiert) und Koordinate je Hausnummer der Gemeinde ``ags``; keine Hausnummer.

    Die Hausnummer selbst wird nicht gelesen. Eine Zeile mit zu wenigen Feldern oder ohne
    Koordinate fällt weg; die Gemeinde hat in GebRef keine.
    """
    streets: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    for line in _lines(archive):
        parts = line.rstrip("\n").split(";")
        if len(parts) < _FIELDS or ags_of(parts) != ags:
            continue
        try:
            x, y = float(parts[_EAST]), float(parts[_NORTH])
        except ValueError:
            continue
        streets.append(normalize_street(parts[_STREET]))
        xs.append(x)
        ys.append(y)
    return pl.DataFrame(
        {"strasse": streets, "x": xs, "y": ys},
        schema={"strasse": pl.String, "x": pl.Float64, "y": pl.Float64},
    )


def _one_of_the_points(xs: np.ndarray, ys: np.ndarray, result: tuple[float, float]) -> bool:
    return bool(np.any((xs == result[0]) & (ys == result[1])))


@deal.pre(lambda xs, ys: len(xs) == len(ys) > 0)
@deal.ensure(_one_of_the_points, message="der Medoid ist einer der Punkte")
def medoid(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    """Der Punkt der Menge mit der kleinsten Summe der Abstände zu allen anderen.

    Bei Gleichstand der mit dem kleinsten Ost-, dann Nordwert, damit das Paket von Lauf zu Lauf
    gleich ist. Die Abstandsmatrix entsteht in Blöcken; die längste Straße eines Wahlbezirks hat
    einige hundert Hausnummern.
    """
    order = np.lexsort((ys, xs))
    sx, sy = xs[order], ys[order]
    sums = np.concatenate(
        [
            np.hypot(
                sx[i : i + _MEDOID_BLOCK, None] - sx[None, :],
                sy[i : i + _MEDOID_BLOCK, None] - sy[None, :],
            ).sum(axis=1)
            for i in range(0, len(sx), _MEDOID_BLOCK)
        ]
    )
    best = int(np.argmin(sums))
    return float(sx[best]), float(sy[best])


def _rounded(value: float, step: float) -> int:
    return int(round(value / step) * step)


def to_crs(houses: pl.DataFrame, source: str, target: str) -> pl.DataFrame:
    """Die Koordinaten der Hausnummern in ein anderes CRS; gleich, wenn beide dasselbe sind."""
    if source == target:
        return houses
    xs, ys = transformer(source, target).transform(
        houses.get_column("x").to_numpy(), houses.get_column("y").to_numpy()
    )
    return houses.with_columns(pl.Series("x", xs), pl.Series("y", ys))


def street_points(
    houses: pl.DataFrame,
    precincts: Sequence[Precinct],
    streets: Mapping[int, frozenset[str]],
    round_m: float,
) -> pl.DataFrame:
    """Je (Straße, Wahlbezirk) des Wörterbuchs der Medoid seiner Hausnummern, gerundet.

    ``houses`` im Arbeits-CRS (EPSG:25832, wie GebRef), ``precincts`` die kanonischen Stimmbezirke
    im selben CRS, ``streets`` die Straßen des Wörterbuchs je Wahlbezirk, normalisiert. Eine
    Hausnummer gehört zum Wahlbezirk des Stimmbezirks, der sie enthält; eine außerhalb aller fällt
    weg. Behalten wird nur ein Paar, das das Wörterbuch kennt: genau die Orte, die eine Seite
    zeigen kann.
    """
    tree = shapely.STRtree([p.geometry for p in precincts])
    points = shapely.points(houses.get_column("x").to_numpy(), houses.get_column("y").to_numpy())
    where, which = tree.query(points, predicate="intersects")
    district = np.full(houses.height, -1, dtype=np.int64)
    ids = np.array([p.district_id for p in precincts], dtype=np.int64)
    # Ein Punkt auf einer gemeinsamen Grenze liegt in zwei Stimmbezirken; der erste in der Folge
    # der Abfrage gewinnt, damit jede Hausnummer genau einen Wahlbezirk hat.
    first = np.unique(where, return_index=True)[1]
    district[where[first]] = ids[which[first]]
    located = houses.with_columns(pl.Series("wahlkreis_id", district)).filter(
        pl.col("wahlkreis_id") >= 0
    )
    rows: list[tuple[str, int, int, int, int]] = []
    for key, group in located.group_by("strasse", "wahlkreis_id"):
        name, number = str(key[0]), int(str(key[1]))
        if name not in streets.get(number, frozenset()):
            continue
        x, y = medoid(group.get_column("x").to_numpy(), group.get_column("y").to_numpy())
        rows.append((name, number, _rounded(x, round_m), _rounded(y, round_m), group.height))
    return pl.DataFrame(
        rows,
        schema={
            "strasse": pl.String,
            "wahlkreis_id": pl.Int64,
            "x": pl.Int64,
            "y": pl.Int64,
            "hausnummern": pl.Int64,
        },
        orient="row",
    ).sort("wahlkreis_id", "strasse")


def label_points(geojson: Mapping[str, object], name: str, working_crs: str) -> pl.DataFrame:
    """Name und Punkt auf der Fläche je Feature (``representative_point``), im Arbeits-CRS, auf Meter.

    GeoJSON ist EPSG:4326 (RFC 7946). Ein Feature ohne Namen fällt weg.
    """
    to_working = transformer(LONLAT, working_crs)
    rows: list[tuple[str, int, int]] = []
    features = geojson.get("features")
    for feature in features if isinstance(features, list) else []:
        label = str((feature.get("properties") or {}).get(name) or "").strip()
        if not label:
            continue
        point = shape(feature["geometry"]).representative_point()
        x, y = to_working.transform(point.x, point.y)
        rows.append((label, int(round(x)), int(round(y))))
    return pl.DataFrame(
        rows, schema={"name": pl.String, "x": pl.Int64, "y": pl.Int64}, orient="row"
    ).sort("name")


def described(path: Path, url: str) -> dict[str, object]:
    """Eine geladene Datei für ``quellen.json``: URL, Name, Bytes, SHA-256, Tag des Abrufs."""
    fetched = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.UTC).date()
    return {
        "url": url,
        "datei": path.name,
        "bytes": path.stat().st_size,
        "sha256": digest(path),
        "abgerufen": fetched.isoformat(),
    }


def fresh(path: Path, *, max_age_s: int, now: float) -> bool:
    """Liegt die Datei da und ist jünger als ``max_age_s``? Dann wird sie nicht geladen."""
    return path.is_file() and now - path.stat().st_mtime < max_age_s


@deal.post(lambda result: len(result) == 16)
def street_points_digest(url: str, round_m: float, labels_url: str, labels_name: str) -> str:
    """Der Zusatz im Stamp von ``street_points`` (Muster Punkt 53): ``[street_points]`` steht nicht
    im Settings-Fingerprint, Quelle, Raster und Namen der Stadtteile ändern aber das Ergebnis."""
    payload = json.dumps([url, round_m, labels_url, labels_name], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
