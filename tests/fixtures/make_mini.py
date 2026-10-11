"""Erzeugt die Mini-Fixture ``tests/fixtures/mini/`` deterministisch aus den Referenzdaten.

Aufruf aus dem Repo-Wurzelverzeichnis::

    uv run python -m tests.fixtures.make_mini

Auswahl: die Wahlbezirke 1 (meiste Treffer), 10 (Ausreißer) und 38 (wenigste Treffer) der Arbeit;
200 Dokumente, davon 150 mit mindestens einem Treffer in diesen Bezirken und 50 ohne, jeweils als
feste Stichprobe über sortierte IDs; dazu die Stimmbezirke dieser drei Wahlbezirke aus dem
GeoJSON des Open-Data-Portals (seit 2026-10-11, für den Schritt ``report``). Die Dateien unter
``expected/`` stammen aus einem Lauf des Altcodes (pandas) auf genau diesen Eingaben, Stand Tag
v0.2.0, und sind der Golden Master der Polars-Kette; siehe ``mini/README.md`` zum Neuerzeugen.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

REPO = Path(__file__).resolve().parents[2]
REFERENCE = REPO / "reference"
MINI = Path(__file__).resolve().parent / "mini"
DISTRICTS = frozenset({1, 10, 38})
N_HIT = 150
N_MISS = 50


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


def main() -> None:
    write_inputs()
    n_docs = len(_load_json(MINI / "interim" / "paper_with_text.json"))
    n_precincts = len(
        json.loads((MINI / "external" / "Stimmbezirke_2025.geojson").read_text())["features"]
    )
    print(
        f"mini fixture geschrieben: {n_docs} Dokumente, {n_precincts} Stimmbezirke, "
        f"Wahlbezirke {sorted(DISTRICTS)}"
    )


if __name__ == "__main__":
    main()
