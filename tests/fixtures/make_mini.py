"""Erzeugt die Mini-Fixture ``tests/fixtures/mini/`` deterministisch aus den Referenzdaten.

Aufruf aus dem Repo-Wurzelverzeichnis::

    uv run python -m tests.fixtures.make_mini

Auswahl: die Wahlbezirke 1 (meiste Treffer), 10 (Ausreißer) und 38 (wenigste Treffer) der Arbeit;
200 Dokumente, davon 150 mit mindestens einem Treffer in diesen Bezirken und 50 ohne, jeweils als
feste Stichprobe über sortierte IDs; dazu die Stimmbezirke dieser drei Wahlbezirke aus dem
GeoJSON des Open-Data-Portals (seit 2026-10-11, für den Schritt ``report``). Die Dateien unter
``expected/`` stammen aus einem Lauf des Altcodes (pandas) auf genau diesen Eingaben, Stand Tag
v0.2.0, und sind der Golden Master der Polars-Kette; siehe ``mini/README.md`` zum Neuerzeugen.

``--period`` schreibt stattdessen ``tests/fixtures/mini-2014/``, die erfundene zweite
Wahlperiode (Option 02); ihre Herkunft steht in ``mini-2014/README.md``.
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import shapely
from shapely.geometry import box, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from georep.geo import LONLAT, geojson_crs, project, read_precincts, repaired, transformer
from georep.layout import Layout
from georep.records import PaperRecord
from georep.settings import load_settings
from georep.stores import PaperStore, TextMeta, TextStore

REPO = Path(__file__).resolve().parents[2]
REFERENCE = REPO / "reference"
CONTEXT = REPO / "context"
MINI = Path(__file__).resolve().parent / "mini"
DISTRICTS = frozenset({1, 10, 38})
N_HIT = 150
N_MISS = 50
# Eine Schnittfläche darunter ist Grenzrauschen zweier Portaldateien, keine gemeinsame Fläche.
MIN_OVERLAP_M2 = 1.0


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
    return data


def _dump_json(data: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def select_paper_ids(papers: list[dict[str, Any]]) -> list[str]:
    searchdict = pl.read_csv(REFERENCE / "processed" / "combined_searchdict.csv", separator=";")
    terms: set[str] = set()
    for row in searchdict.filter(pl.col("wahlkreis_id").is_in(list(DISTRICTS))).iter_rows(
        named=True
    ):
        terms.update(t.strip() for t in str(row["suchbegriffe"]).split(",") if t.strip())
    index = pl.read_csv(REFERENCE / "processed" / "inverted_index.csv")
    hit_ids: set[str] = set()
    for row in index.filter(pl.col("suchbegriffe").is_in(list(terms))).iter_rows(named=True):
        if row["paper_ids"]:
            hit_ids.update(str(row["paper_ids"]).split(";"))
    with_text = sorted(p["id"] for p in papers if p.get("paper_text"))
    hits_sorted = [i for i in with_text if i in hit_ids]
    step = max(1, len(hits_sorted) // N_HIT)
    chosen_hits = hits_sorted[::step][:N_HIT]
    misses = [i for i in with_text if i not in hit_ids][:N_MISS]
    return chosen_hits + misses


def write_inputs() -> None:
    papers = _load_json(REFERENCE / "interim" / "paper_with_text.json")
    keep = set(select_paper_ids(papers))
    _dump_json([p for p in papers if p["id"] in keep], MINI / "interim" / "paper_with_text.json")

    pois = _load_json(REFERENCE / "raw" / "wikipedia_dict.json")
    _dump_json(
        [p for p in pois if p.get("wahlkreis_id") is None or p["wahlkreis_id"] in DISTRICTS],
        MINI / "raw" / "wikipedia_dict.json",
    )

    streets = _load_json(REFERENCE / "raw" / "streets_per_district.json")
    _dump_json(
        [s for s in streets if s["wahlbezirk_id"] in DISTRICTS],
        MINI / "raw" / "streets_per_district.json",
    )

    # Byte-treu filtern: der Altcode liest latin-1 mit ';', die Datei traegt eine UTF-8-BOM.
    src = REFERENCE / "external" / "Stimmbezirk_Wahlergebnis.csv"
    lines = src.read_bytes().decode("latin-1").splitlines(keepends=True)
    header = lines[0].rstrip("\r\n").split(";")
    col = header.index("Kommunalwahlbezirk")
    body = [
        ln
        for ln in lines[1:]
        if ln.split(";")[col].strip().isdigit() and int(ln.split(";")[col]) in DISTRICTS
    ]
    dst = MINI / "external" / "Stimmbezirk_Wahlergebnis.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes("".join([lines[0], *body]).encode("latin-1"))

    write_geojson()
    write_context()


def write_geojson() -> int:
    """Die Stimmbezirke der drei Wahlbezirke als FeatureCollection mit dem ``crs`` der Quelle.

    Kompakt geschrieben (kein Einzug): 22 Features, rund 95 KB statt der 1,8 MB der Referenz.
    Liefert die Zahl der Features.
    """
    src = REFERENCE / "external" / "Stimmbezirke_2025.geojson"
    with src.open(encoding="utf-8") as f:
        collection: dict[str, Any] = json.load(f)
    features = [
        feature
        for feature in collection["features"]
        if feature["properties"]["Kommunalwahlbezirk Nr."] in DISTRICTS
    ]
    subset = {key: (features if key == "features" else value) for key, value in collection.items()}
    dst = MINI / "external" / "Stimmbezirke_2025.geojson"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        json.dump(subset, f, ensure_ascii=False)
    return len(features)


def context_units() -> list[str]:
    """Die Schlüssel der Raumeinheiten, die die 22 Stimmbezirke der Mini-Fixture schneiden.

    Beide GeoJSON-Dateien kommen in verschiedenen CRS aus dem Portal; verglichen wird im
    Arbeits-CRS der Settings. Berührungen ohne Fläche fallen weg (``MIN_OVERLAP_M2``).
    """
    settings = load_settings(cwd=Path("/nonexistent"))
    working = settings.geo.working_crs
    precincts = unary_union(
        [
            p.geometry
            for p in read_precincts(
                MINI / "external" / "Stimmbezirke_2025.geojson", settings.columns, working
            )
        ]
    )
    units = json.loads((CONTEXT / settings.context.files.units.file).read_text(encoding="utf-8"))
    trans = transformer(geojson_crs(units, LONLAT), working)
    key = settings.context.units.key
    keep: list[str] = []
    for feature in units["features"]:
        geometry = repaired(project(shape(feature["geometry"]), trans))
        if geometry.intersection(precincts).area > MIN_OVERLAP_M2:
            keep.append(str(feature["properties"][key]))
    return sorted(keep)


def write_context() -> tuple[int, int]:
    """``mini/context/``: die Raumeinheiten der drei Wahlbezirke und die Tabelle dazu.

    Die Erläuterungsdatei der Indikatoren wird unverändert übernommen (13 KB, keine Daten je
    Einheit). Liefert (Zeilen der Tabelle, Features).
    """
    settings = load_settings(cwd=Path("/nonexistent"))
    files, table = settings.context.files, settings.context.table
    keys = set(context_units())
    target = MINI / "context"
    target.mkdir(parents=True, exist_ok=True)

    # Byte-treu filtern wie beim Wahlergebnis: UTF-8, ';', CRLF, Dezimalkomma bleiben, wie sie sind.
    lines = (CONTEXT / files.table.file).read_bytes().decode("utf-8").splitlines(keepends=True)
    column = lines[0].rstrip("\r\n").split(table.sep).index(table.key)
    body = [ln for ln in lines[1:] if ln.split(table.sep)[column].strip() in keys]
    (target / files.table.file).write_bytes("".join([lines[0], *body]).encode("utf-8"))

    units = json.loads((CONTEXT / files.units.file).read_text(encoding="utf-8"))
    key = settings.context.units.key
    features = [f for f in units["features"] if str(f["properties"][key]) in keys]
    subset = {k: (features if k == "features" else v) for k, v in units.items()}
    with (target / files.units.file).open("w", encoding="utf-8") as f:
        json.dump(subset, f, ensure_ascii=False)
    (target / files.indicators.file).write_bytes((CONTEXT / files.indicators.file).read_bytes())
    return len(body), len(features)


# --- Option 02: die synthetische Mini-Periode --------------------------------------------------
#
# ``tests/fixtures/mini-2014/`` ist der Referenzdatensatz einer zweiten Wahlperiode: ein eigener
# Stimmbezirkszuschnitt, eigene Wahlbezirksflächen, ein Wahlergebnis im Format der Ratswahl 2020
# (mit Briefwahlbezirken ohne Geometrie) und 100 Dokumente mit zurückdatiertem Datum. Alles ist
# **erfunden**: die Zahlen sind aus dem Mini-Ergebnis von 2025 mit festen Faktoren gerechnet und
# bilden keine Wahl ab. Die Fixture prüft die Kette, nicht die Geschichte.

MINI_2014 = Path(__file__).resolve().parent / "mini-2014"
PERIOD_PROFILE = "2014-2020"
SPLIT_EVERY = 4  # jeder vierte Stimmbezirk wird an der Senkrechten durch seinen Schwerpunkt geteilt
YEARS_BACK = 6  # 2020-09-14 bis 2025-09-12 wird 2014-09-14 bis 2019-09-12, ganz in der Periode
POSTAL_SHARE = 0.8  # so viele der Wahlberechtigten mit Wahlschein wählen auch per Brief
POSTAL_ROWS = 2  # Briefwahlbezirke je Wahlbezirk
TURNOUT = 0.45  # Grundwert der erfundenen Wahlbeteiligung
TURNOUT_SPREAD = 0.04  # je Stimmbezirk ein fester Zuschlag, damit nicht alle Bezirke gleich sind
WITH_CERTIFICATE = 0.30  # Anteil der Wahlberechtigten mit Sperrvermerk W
OLD_DISTRICTS = (101, 110, 138)  # Wahlbezirke des alten Zuschnitts, absichtlich anders geschnitten
PARTIES = ("CDU", "GRUENE", "SPD", "FDP", "Die_Linke", "AfD")
RESULT_HEADER = (
    "datum;wahl;ags;gebiet-nr;gebiet-name;max-schnellmeldungen;anz-schnellmeldungen;"
    "A1;A2;A3;A;B;B2;C;D;D1;D2;D3;D4;D5;D6"
)
ELECTION_ROW = "13.09.2020;Ratswahl;05111000"


@dataclass(frozen=True)
class Piece:
    """Ein Stück eines Stimmbezirks von 2025: die Keimzelle eines Stimmbezirks der alten Periode."""

    key: str
    district_2025: int
    share: float  # Flächenanteil am Stimmbezirk von 2025
    eligible: int
    votes: tuple[int, ...]  # je Partei, in der Reihenfolge von PARTIES
    geometry: BaseGeometry


def _mini_counts() -> dict[str, tuple[int, tuple[int, ...]]]:
    """Wahlberechtigte und Parteistimmen je Stimmbezirk aus dem Mini-Ergebnis von 2025."""
    text = (MINI / "external" / "Stimmbezirk_Wahlergebnis.csv").read_bytes().decode("latin-1")
    frame = pl.read_csv(io.BytesIO(text.encode("utf-8")), separator=";", infer_schema=False)
    found: dict[str, tuple[int, tuple[int, ...]]] = {}
    for row in frame.iter_rows(named=True):
        key = str(row["gebietnr"]).strip()
        eligible = str(row["Wahlberechtigte_insgesamt"]).strip()
        if not eligible.isdigit():
            continue  # Briefwahlbezirke von 2025 tragen keine Wahlberechtigten
        votes = tuple(int(str(row[f"{p}_Stimmen"]).strip() or 0) for p in PARTIES)
        found[key] = (int(eligible), votes)
    return found


def _halves(geometry: BaseGeometry) -> list[BaseGeometry]:
    """Links und rechts der Senkrechten durch den Schwerpunkt; beide Hälften oder keine."""
    minx, miny, maxx, maxy = geometry.bounds
    middle = geometry.centroid.x
    left = shapely.intersection(geometry, box(minx, miny, middle, maxy))
    right = shapely.intersection(geometry, box(middle, miny, maxx, maxy))
    if left.is_empty or right.is_empty or left.area <= 0 or right.area <= 0:
        return [geometry]
    return [left, right]


def _pieces() -> list[Piece]:
    """Die 22 Stimmbezirke von 2025 zu 28 Stücken, jedes mit seinem Anteil an Zahlen und Fläche."""
    collection = json.loads(
        (MINI / "external" / "Stimmbezirke_2025.geojson").read_text(encoding="utf-8")
    )
    counts = _mini_counts()
    features = sorted(collection["features"], key=lambda f: f["properties"]["Stimm-/ Wahlbezirk"])
    pieces: list[Piece] = []
    for index, feature in enumerate(features):
        key = str(feature["properties"]["Stimm-/ Wahlbezirk"])
        district = int(feature["properties"]["Kommunalwahlbezirk Nr."])
        eligible, votes = counts[key]
        geometry = shape(feature["geometry"])
        parts = _halves(geometry) if index % SPLIT_EVERY == 0 else [geometry]
        for suffix, part in zip("ab" if len(parts) == 2 else " ", parts, strict=True):
            share = part.area / geometry.area
            pieces.append(
                Piece(
                    key=f"{key}{suffix.strip()}",
                    district_2025=district,
                    share=share,
                    eligible=max(1, round(share * eligible)),
                    votes=tuple(round(share * v) for v in votes),
                    geometry=part,
                )
            )
    return pieces


def _merge_across_districts(pieces: list[Piece]) -> list[Piece]:
    """Zwei Stücke verschiedener Wahlbezirke zu einem Stimmbezirk vereinigen.

    Die drei Mini-Wahlbezirke liegen räumlich getrennt; ohne solche mehrteiligen Stimmbezirke wäre
    jeder Flächenanteil 1 und der Crosswalk eine Identität. In den echten Daten liegen 83 der 316
    Stimmbezirke von 2020 in mehr als einem Wahlbezirk von 2025, und genau dieser Fall soll in der
    Fixture vorkommen.
    """
    by_district: dict[int, list[Piece]] = {}
    for piece in pieces:
        by_district.setdefault(piece.district_2025, []).append(piece)
    first, second, third = (by_district[d] for d in sorted(by_district))
    merges = [(first[0], third[0]), (second[1], third[1])]
    merged: list[Piece] = []
    for left, right in merges:
        merged.append(
            Piece(
                key=f"{left.key}m",
                district_2025=left.district_2025,
                share=1.0,
                eligible=left.eligible + right.eligible,
                votes=tuple(a + b for a, b in zip(left.votes, right.votes, strict=True)),
                geometry=shapely.unary_union([left.geometry, right.geometry]),
            )
        )
    gone = {id(p) for pair in merges for p in pair}
    return sorted([p for p in pieces if id(p) not in gone] + merged, key=lambda p: p.key)


def _old_districts(precincts: list[Piece]) -> dict[int, list[Piece]]:
    """Die Stimmbezirke in drei Gruppen, geschnitten nach Nummer statt nach Lage.

    Der alte Zuschnitt soll sich vom neuen unterscheiden; eine Aufteilung nach der sortierten
    Nummer tut das zuverlässig und bleibt eine Zerlegung (jeder Stimmbezirk in genau einer Gruppe).
    """
    size = len(precincts)
    bounds = [0, size // 3, 2 * size // 3, size]
    return {
        district: precincts[bounds[i] : bounds[i + 1]] for i, district in enumerate(OLD_DISTRICTS)
    }


def _result_row(key: str, name: str, eligible: int, voters: int, votes: Sequence[int]) -> str:
    """Eine Zeile im Format der Ratswahl 2020: A1, A2, A3, A, B, B2, C, D, D1 bis D6."""
    with_certificate = round(WITH_CERTIFICATE * eligible)
    valid = sum(votes)
    fields = [
        ELECTION_ROW,
        key,
        name,
        "1",
        "1",
        str(eligible - with_certificate),
        str(with_certificate),
        "0",
        str(eligible),
        str(voters),
        str(voters if eligible == 0 else 0),
        "0",
        str(valid),
        *[str(v) for v in votes],
    ]
    return ";".join(fields)


def _turnout(index: int) -> float:
    """Eine Wahlbeteiligung je Stimmbezirk, deterministisch gestreut (0,45 bis 0,49)."""
    return TURNOUT + TURNOUT_SPREAD * (index % 5) / 4


def _voters(index: int, piece: Piece) -> int:
    return round(_turnout(index) * piece.eligible)


def _urn_rows(precincts: Sequence[Piece]) -> list[str]:
    return [
        _result_row(
            p.key,
            f"{p.key} Stimmbezirk",
            p.eligible,
            _voters(i, p),
            _scaled_votes(p, _voters(i, p)),
        )
        for i, p in enumerate(precincts)
    ]


def _scaled_votes(piece: Piece, voters: int) -> list[int]:
    """Die Stimmen auf die Wähler des Stücks skaliert; die letzte Partei nimmt den Rest auf."""
    total = sum(piece.votes)
    if total == 0:
        return [0] * len(PARTIES)
    scaled = [round(voters * v / total) for v in piece.votes]
    scaled[-1] += voters - sum(scaled)
    return [max(0, v) for v in scaled]


def _postal_rows(district: int, precincts: Sequence[Piece]) -> list[str]:
    """Zwei Briefwahlbezirke je Wahlbezirk: keine Wahlberechtigten, nur Wähler und Stimmen."""
    certificates = sum(round(WITH_CERTIFICATE * p.eligible) for p in precincts)
    total = round(POSTAL_SHARE * certificates)
    urn_votes = [
        sum(_scaled_votes(p, _voters(j, p))[i] for j, p in enumerate(precincts))
        for i in range(len(PARTIES))
    ]
    urn_total = sum(urn_votes)
    rows = []
    for index in range(POSTAL_ROWS):
        voters = total // POSTAL_ROWS + (total % POSTAL_ROWS if index == 0 else 0)
        if urn_total == 0:
            votes = [0] * len(PARTIES)
        else:
            votes = [round(voters * v / urn_total) for v in urn_votes]
            votes[-1] = max(0, votes[-1] + voters - sum(votes))
        rows.append(
            _result_row(
                f"{district}{90 + index}",
                f"{district}{90 + index} Briefwahlbezirk",
                0,
                voters,
                votes,
            )
        )
    return rows


def _district_row(district: int, rows: Sequence[str]) -> str:
    """Die Wahlbezirkszeile als Summe ihrer Stimmbezirks- und Briefwahlzeilen."""
    values = [[int(f) for f in row.split(";")[7:]] for row in rows]
    summed = [sum(v[i] for v in values) for i in range(len(values[0]))]
    head = [
        ELECTION_ROW,
        f"{district:03d}",
        f"{district:03d} Wahlbezirk",
        str(len(rows)),
        str(len(rows)),
    ]
    return ";".join([*head, *[str(v) for v in summed]])


def _feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4647"}},
        "features": features,
    }


def _write_geojson(path: Path, features: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_feature_collection(features), f, ensure_ascii=False)


def _write_documents(root: Path) -> tuple[int, int]:
    """Jedes zweite Mini-Dokument, um YEARS_BACK Jahre zurückdatiert, im nativen Format.

    Kennungen, Drucksachennummern und URLs bleiben, wie sie sind: die Fixture prüft die Kette,
    nicht die Herkunft, und zwei Perioden mit denselben Kennungen sind für den Vergleich
    unerheblich (er rechnet auf Wahlbezirken, nicht auf Dokumenten).
    """
    items = _load_json(MINI / "interim" / "paper_with_text.json")[::2]
    layout = Layout(root, root / "cache", root)
    records = []
    for item in items:
        record = PaperRecord.from_legacy(item)
        shifted = (
            record.date.replace(year=record.date.year - YEARS_BACK)
            if record.date is not None
            else None
        )
        records.append(record.model_copy(update={"date": shifted}))
    (root / "raw").mkdir(parents=True, exist_ok=True)
    PaperStore(root / "raw" / "papers.jsonl").save(records)
    texts = TextStore(layout.text_dir / "texts.parquet")
    stored = 0
    for item, record in zip(items, records, strict=True):
        text = item.get("paper_text") or ""
        if record.file_name and text:
            texts.put(
                record.file_name, text, TextMeta(extractor=FIXTURE_EXTRACTOR, source="fixture")
            )
            stored += 1
    texts.save()
    return len(records), stored


FIXTURE_EXTRACTOR = "Mini-Fixture (synthetisch)"


def write_period_fixture() -> str:
    """Schreibt ``tests/fixtures/mini-2014/`` deterministisch; liefert eine Zeile mit den Zahlen."""
    precincts = _merge_across_districts(_pieces())
    groups = _old_districts(precincts)
    _write_geojson(
        MINI_2014 / "external" / "Stimmbezirke_2020.geojson",
        [
            {
                "type": "Feature",
                "properties": {"Stimmbezchar": p.key},
                "geometry": mapping(p.geometry),
            }
            for p in precincts
        ],
    )
    _write_geojson(
        MINI_2014 / "external" / "Kommunalwahlbezirke.geojson",
        [
            {
                "type": "Feature",
                "properties": {
                    "Kommunalwahlbezirk": district,
                    "Name": f"Wahlbezirk {district} (synthetisch)",
                    "Stand": "01.01.2020",
                },
                "geometry": mapping(shapely.unary_union([p.geometry for p in members])),
            }
            for district, members in groups.items()
        ],
    )
    precinct_rows: list[str] = []
    district_rows: list[str] = []
    for district, members in groups.items():
        urn = _urn_rows(members)
        postal = _postal_rows(district, members)
        precinct_rows += urn + postal
        district_rows.append(_district_row(district, urn + postal))
    (MINI_2014 / "external" / "Stimmbezirk_Wahlergebnis.csv").write_text(
        "\n".join([RESULT_HEADER, *precinct_rows]) + "\n", encoding="utf-8"
    )
    (MINI_2014 / "external" / "Wahlbezirk_Wahlergebnis.csv").write_text(
        "\n".join([RESULT_HEADER, *district_rows]) + "\n", encoding="utf-8"
    )
    papers, texts = _write_documents(MINI_2014)
    return (
        f"{len(precincts)} Stimmbezirke in {len(groups)} Wahlbezirken, "
        f"{len(precinct_rows)} Ergebniszeilen, {papers} Dokumente, {texts} Texte"
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--period" in args:
        print(f"mini-2014 fixture geschrieben: {write_period_fixture()}")
        return
    write_inputs()
    n_docs = len(_load_json(MINI / "interim" / "paper_with_text.json"))
    n_precincts = len(
        json.loads((MINI / "external" / "Stimmbezirke_2025.geojson").read_text())["features"]
    )
    n_units = len(context_units())
    print(
        f"mini fixture geschrieben: {n_docs} Dokumente, {n_precincts} Stimmbezirke, "
        f"{n_units} Raumeinheiten, Wahlbezirke {sorted(DISTRICTS)}"
    )


if __name__ == "__main__":
    main()
