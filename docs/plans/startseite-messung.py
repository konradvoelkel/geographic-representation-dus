"""Messung zum Plan der Startseite (docs/plan-startseite-2026-11.md, § 2, § 4.2, § 4.5); nur lesen.

Zusammengeführt aus den drei Skripten des Entwurfs (messung.py, messung2.py, messung3.py,
2026-11-27). Liest einen gelaufenen Datensatz und seine Stadtseite, wahlweise die Gebäudereferenzen
NRW, und druckt die Zahlen der Tabellen in § 2 und § 4: Orte (Begriff × Wahlbezirk) mit Treffer
nach Art, Punkte (Dokument × Ort), Sammeldokumente, die letzten zwölf Monate, Gremien der Dokumente
mit Treffer, Deckung der Straßenpunkte und die Größe von ``karte.json``.

Aufruf (Pfade als Argumente, nichts Rechnerspezifisches hier):

    uv run python -I docs/plans/startseite-messung.py <datenwurzel/profil> [<wörterbuch-profil>] \
        [--gebref <gebref_EPSG25832_ASCII.zip> --ags <gemeindeschlüssel>]

``<datenwurzel/profil>`` ist etwa ``data/duesseldorf`` nach ``georep run``; die Stadtseite liest das
Skript aus ``site/`` darunter. Eine Periode mit geliehenem Wörterbuch nennt als zweites Argument den
Ordner der Hauptperiode. Das Skript importiert nichts aus ``georep``: es misst den Datensatz, nicht
den Code, und gibt damit einen zweiten Blick auf das, was ``report.startkarte`` baut.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import json
import re
import statistics
import zipfile
from collections import Counter
from pathlib import Path

import polars as pl

MAX_PLACES = 20  # report.start.max_places
WINDOW = 12  # report.start.months
ROUND_M = 25.0  # street_points.round_m


def canonical(term: str, known: frozenset[str]) -> str:
    if "str." not in term:
        return term
    long = term.replace("str.", "straße")
    return long if long in known else term


def normalize_street(name: str) -> str:
    text = name.strip().lower().replace("strasse", "straße")
    text = re.sub(r"str\.(?=$|[\s-])", "straße", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("dictionary_root", type=Path, nargs="?")
    parser.add_argument("--gebref", type=Path)
    parser.add_argument("--ags")
    args = parser.parse_args()
    root: Path = args.root
    source: Path = args.dictionary_root or root

    docs = json.loads((root / "site/data/dokumente.json").read_text(encoding="utf-8"))
    dictionary = {
        int(w): frozenset(words or ())
        for w, words in pl.read_parquet(
            source / "processed/combined_searchdict.parquet"
        ).iter_rows()
    }
    streets = pl.read_parquet(source / "processed/wahlbezirke_strassen.parquet")
    street_places = {
        (str(t).strip().lower(), int(w)) for w, lst in streets.iter_rows() for t in (lst or [])
    }
    pois = pl.read_parquet(source / "processed/wikidata_agg.parquet")
    poi_places = {
        (str(t).strip().lower(), int(w)) for w, lst in pois.iter_rows() for t in (lst or [])
    }

    by_term: dict[str, list[int]] = {}
    for district, words in dictionary.items():
        for word in words:
            by_term.setdefault(word, []).append(district)
    places: dict[tuple[str, int], set[int]] = {}
    for term, indices in docs["terms"].items():
        for district in by_term.get(term, ()):
            places.setdefault((canonical(term, dictionary[district]), district), set()).update(
                indices
            )
    kinds = Counter(
        "beides"
        if key in street_places and key in poi_places
        else "straße"
        if key in street_places
        else "Ort aus Wikidata"
        if key in poi_places
        else "sonst"
        for key in places
    )
    print(f"Dokumente in dokumente.json: {len(docs['documents'])}")
    print(f"Orte (Begriff × Wahlbezirk) mit Treffer: {len(places)}; nach Art: {dict(kinds)}")

    keys = sorted(places, key=lambda k: (k[1], k[0]))
    index = {k: i for i, k in enumerate(keys)}
    doc_places: list[set[int]] = [set() for _ in docs["documents"]]
    for key, indices in places.items():
        for i in indices:
            doc_places[i].add(index[key])
    sizes = [len(s) for s in doc_places]
    per_place = sorted(len(v) for v in places.values())
    print(
        f"Punkte (Dokument × Ort): {sum(sizes)}; je Dokument Median {statistics.median(sizes)}, "
        f"höchstens {max(sizes)}; je Ort Median {statistics.median(per_place)}, "
        f"P90 {per_place[int(len(per_place) * 0.9)]}, höchstens {per_place[-1]}, "
        f"{sum(1 for n in per_place if n == 1)} Orte mit einem Dokument"
    )
    for limit in (MAX_PLACES, 50):
        many = [i for i, n in enumerate(sizes) if n > limit]
        print(
            f"Dokumente mit mehr als {limit} Orten: {len(many)}, ihre Punkte {sum(sizes[i] for i in many)}"
        )

    dates = [dt.date.fromisoformat(d[1]) if d[1] else None for d in docs["documents"]]
    dated = [d for d in dates if d]
    first, last = min(dated), max(dated)
    month = lambda d: (d.year - first.year) * 12 + d.month - first.month  # noqa: E731
    end = month(last)
    window = (max(0, end - WINDOW + 1), end)
    chosen = [i for i, d in enumerate(dates) if d and window[0] <= month(d) <= window[1]]
    in_window = {p for i in chosen for p in doc_places[i]}
    print(
        f"Datum {first} bis {last}, {end + 1} Monate; letzte {WINDOW} Monate: {len(chosen)} Dokumente, "
        f"{sum(len(doc_places[i]) for i in chosen)} Punkte an {len(in_window)} Orten, "
        f"{sum(1 for i in chosen if sizes[i] > MAX_PLACES)} Sammeldokumente"
    )

    bodies = pl.read_parquet(
        root / "processed/papers_gremien.parquet", columns=["reference", "gremium_art"]
    )
    kind_of = dict(bodies.iter_rows())
    hit_kinds = Counter(kind_of.get(d[2], "unbekannt") for d in docs["documents"])
    total = sum(hit_kinds.values())
    print(
        "Gremium der Dokumente mit Treffer:",
        {k: f"{n} ({n / total:.1%})" for k, n in hit_kinds.most_common()},
    )

    street_hit = {k for k in places if k in street_places}
    if args.gebref and args.ags:
        located = _street_points(args.gebref, args.ags, root, source)
        covered = street_hit & set(located)
        print(
            f"Straßenorte mit Treffer {len(street_hit)}, davon mit Hausnummern im selben Wahlbezirk "
            f"{len(covered)} ({len(covered) / len(street_hit):.1%}); Paare im Wörterbuch mit "
            f"Hausnummern {len(located)}"
        )

    # karte.json grob: Orte mit Name, Dokumente mit Monat, Gremium und Orten (Sammeldokumente mit
    # Wahlbezirken); die Koordinaten als Platzhalter gleicher Länge
    rows = []
    for i, found in enumerate(doc_places):
        head = [month(dates[i]) if dates[i] else -1, 9]
        if len(found) > MAX_PLACES:
            rows.append(head + sorted({-keys[p][1] for p in found}))
        else:
            rows.append(head + sorted(found))
    blob = json.dumps(
        {"places": [[1234, 1234, k[1], 1, k[0]] for k in keys], "docs": rows},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    print(f"karte.json, geschätzt: {len(blob)} Bytes, gzip {len(gzip.compress(blob, 9))}")


def _street_points(archive: Path, ags: str, root: Path, source: Path) -> set[tuple[str, int]]:
    """Die Paare (Straße, Wahlbezirk) des Wörterbuchs mit mindestens einer Hausnummer im Wahlbezirk."""
    from pyproj import CRS, Transformer
    from shapely import STRtree, points
    from shapely.geometry import shape

    collection = json.loads((root / "interim/stimmbezirke.geojson").read_text(encoding="utf-8"))
    name = (collection.get("crs") or {}).get("properties", {}).get("name", "EPSG:4326")
    to_source = Transformer.from_crs(
        CRS.from_user_input("EPSG:25832"), CRS.from_user_input(name), always_xy=True
    )
    shapes = [shape(f["geometry"]) for f in collection["features"]]
    district = [int(f["properties"]["wahlbezirk"]) for f in collection["features"]]
    names, xs, ys = [], [], []
    with zipfile.ZipFile(archive) as opened, opened.open("gebref.txt") as raw:
        for line in io.TextIOWrapper(raw, encoding="utf-8"):
            p = line.split(";")
            if len(p) > 19 and p[3] + p[5] + p[7] + p[9] == ags:
                names.append(normalize_street(p[14]))
                xs.append(float(p[18]))
                ys.append(float(p[19]))
    sx, sy = to_source.transform(xs, ys)
    tree = STRtree(shapes)
    where, which = tree.query(points(sx, sy), predicate="intersects")
    streets = pl.read_parquet(source / "processed/wahlbezirke_strassen.parquet")
    wanted = {(normalize_street(t), int(w)) for w, lst in streets.iter_rows() for t in (lst or [])}
    found = {(names[i], district[k]) for i, k in zip(where.tolist(), which.tolist(), strict=True)}
    print(
        f"Hausnummern der Gemeinde {ags}: {len(names)}; Paket je (Straße, Wahlbezirk) auf {ROUND_M:.0f} m"
    )
    return found & wanted


if __name__ == "__main__":
    main()
