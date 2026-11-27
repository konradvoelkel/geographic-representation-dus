"""Grundgesamtheit der Prüfstichprobe von Vorhaben 14 (Frage 9.18; `14-vorgaenge.md`, § 4.3).

    uv run python docs/plans/14-vorgaenge-pruefung.py   # nach `georep run`, Profil duesseldorf
    uv run georep validate sample 14-vorgaenge-3-f4

Die Einheiten sind die starken Kanten der Rückfallregel (`processed/vorgang_kanten.parquet`,
`stark`), wie `georep validate sample` sie für die Einheit `pair_with_span` liest: `kante` (die
ersten zwölf Hexzeichen von SHA-1 über „von|nach", wie im Messskript), `id_a` (A, die genannte
Drucksache, `nach`), `id_b` (B, die nennende, `von`), `start` und `end` der Fundstelle im Rohtext
von B, `quelle` (die Schicht: `titel`, `anlage`, `nummer`, `sammelbericht`) und als Kontext für
den Auftrag Drucksachennummer, Dokumentart und Datum beider sowie die Fundstelle in Worten.

Weg bleiben die Kanten in eine Nachbarperiode (`nach_periode`; ihre Dokumente liegen nicht im
Korpus des Profils, aus dem `validate tasks` die Ausschnitte liest) und die Kanten, die schon in
Stichprobe 1 oder 2 kodiert sind (`validierung/14-vorgaenge-f4/`, `14-vorgaenge-2-f4/`). Eine
Fundstelle im Text bekommt nur der Sammelbericht: dort nennt B A in einer eigenen Zeile, und der
Auftrag zeigt B als Fenster um sie; Titel, Anlagenname und Nummer sieht der Kodierer im Titel und
im Kontext. Die Spanne kommt aus `processed/verweise.parquet` und muss im Rohtext von B wörtlich
stehen, sonst bleibt sie leer. Kein Netz, kein Modell; geschrieben wird nur unter `data_root`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl

from georep.analysis.procedures import build_directory
from georep.enrich.procedures import load_city, procedure_files, read_attachments
from georep.io import write_parquet
from georep.layout import Layout
from georep.prep.references import ATTACHMENT_SEPARATOR, ReferenceRules, find_hits
from georep.settings import load_settings
from georep.stores import RawTextStore

REPO = Path(__file__).resolve().parents[2]
EARLIER = ("14-vorgaenge-f4", "14-vorgaenge-2-f4")
TARGET = "interim/vorgang_kanten_rueckfall.parquet"  # sample.population im Codebuch
WHERE = {
    "titel": "Titel von B",
    "nummer": "Drucksachennummer von B (Nachtrag zu A)",
    "sammelbericht": "Text von B",
}
SCHEMA_VERSION = 1


def kante(von: str, nach: str) -> str:
    return hashlib.sha1(f"{von}|{nach}".encode()).hexdigest()[:12]


def main() -> None:
    settings = load_settings()
    layout = Layout.from_settings(settings)
    files = procedure_files(layout)
    edges = pl.read_parquet(files.edges).filter(pl.col("stark") & (pl.col("nach_periode") == ""))
    earlier = pl.concat(
        [
            pl.read_csv(REPO / "validierung" / name / "stichprobe.csv", infer_schema=False).select(
                "id_a", "id_b"
            )
            for name in EARLIER
        ]
    )
    before = edges.height
    edges = edges.join(earlier, left_on=["nach", "von"], right_on=["id_a", "id_b"], how="anti")
    print(f"{before} starke Kanten in der Periode, {before - edges.height} schon kodiert")

    rules = ReferenceRules.from_settings(settings.procedures)
    attachments = read_attachments(files.attachments if settings.procedures.attachments else None)
    city = load_city(settings, layout, attachments)
    directory = build_directory(city.documents, rules)
    docs = city.documents.select("id", "reference", "name", "paper_type", "date", "anlagen")
    by_id = {row["id"]: row for row in docs.iter_rows(named=True)}
    corpus = pl.read_parquet(layout.corpus, columns=["id", "file_name"])
    file_names = dict(corpus.iter_rows())
    wanted = sorted(set(edges.get_column("von")))
    spans = pl.read_parquet(files.spans).filter(pl.col("id").is_in(wanted))
    raw = RawTextStore(layout.raw_texts)

    rows = []
    for edge in edges.sort("von", "nach").iter_rows(named=True):
        a, b, source = by_id[edge["nach"]], by_id[edge["von"]], edge["quelle"]
        start = end = None
        where = WHERE.get(source, "")
        if source == "sammelbericht":
            text = raw.get(file_names.get(b["id"]) or "") or ""
            for span in spans.filter(pl.col("id") == b["id"]).sort("start").iter_rows(named=True):
                hits = directory.ids.get(span["norm"], ())
                if hits == (a["id"],) and text[span["start"] : span["end"]] == span["value"]:
                    start, end = span["start"], span["end"]
                    break
        if source == "anlage":
            names = [
                name
                for name in (b["anlagen"] or [])
                if any(
                    directory.target(hit.reference) == a["id"]
                    for hit in find_hits(name.lower(), rules, directory.codes)
                )
            ]
            where = "Anlage von B: " + ATTACHMENT_SEPARATOR.join(names) if names else "Anlage von B"
        rows.append(
            {
                "kante": kante(edge["von"], edge["nach"]),
                "id_a": a["id"],
                "id_b": b["id"],
                "start": start,
                "end": end,
                "quelle": source,
                "drucksache_a": a["reference"] or "",
                "drucksache_b": b["reference"] or "",
                "art_a": a["paper_type"] or "",
                "art_b": b["paper_type"] or "",
                "datum_a": str(a["date"] or ""),
                "datum_b": str(b["date"] or ""),
                "fundstelle": where,
            }
        )
    frame = pl.DataFrame(
        rows,
        schema={
            "kante": pl.String,
            "id_a": pl.String,
            "id_b": pl.String,
            "start": pl.Int64,
            "end": pl.Int64,
            **{c: pl.String for c in ("quelle", "drucksache_a", "drucksache_b", "art_a", "art_b")},
            **{c: pl.String for c in ("datum_a", "datum_b", "fundstelle")},
        },
    ).sort("kante")
    if frame.get_column("kante").n_unique() != frame.height:
        raise SystemExit("zwei Kanten mit demselben Schlüssel")
    write_parquet(frame, layout.root / TARGET, schema_version=SCHEMA_VERSION)
    for source, group in frame.group_by("quelle", maintain_order=False):
        located = group.filter(pl.col("start").is_not_null()).height
        print(f"  {source[0]}: {group.height} Kanten, {located} mit Fundstelle im Text")
    longest = frame.select(pl.col("fundstelle").str.len_chars().max()).item()
    print(f"{frame.height} Kanten -> {layout.root / TARGET} (längste Fundstelle {longest} Zeichen)")


if __name__ == "__main__":
    main()
