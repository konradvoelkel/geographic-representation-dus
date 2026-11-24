"""Vorhaben 18: die Einheiten der Suche und der Einbettungen, eine je PDF-Datei mit Rohtext.

Messdokument ``docs/plans/18-einbettungen.md``, § 3.1: die Dokumente des Korpus über ``file_name``
verbunden mit dem Rohtextstore (Fundament F1, nach Dateiname geschlüsselt), nur Dateien, deren
Rohtext ohne Leerraum nicht leer ist. Teilen sich mehrere Korpus-IDs eine Datei, steht die Einheit
unter der kleinsten ID (Zeichenfolge), sonst stünde derselbe Text zweimal in einer Trefferliste;
``ids`` nennt alle, damit jede Ausgabe je Korpus-ID eine Zeile tragen kann (Synergie 2026-11, § 1,
„Dokument je PDF-Datei"). Der Titel ist OParl ``name`` dieser ID (``prep.chunks.chunk_title``).

Der Rohtext kommt mit den Formfeeds aus dem Text der Seiten zurück (``restore_form_feeds``): so hat
die Messung ihn gelesen (ihre Datei trug dort ``\\f``), und darum sind die Stücke dieselben. Die
Länge ändert sich nicht, die Stellen ``start`` und ``end`` gelten im Store wie hier.
"""

from __future__ import annotations

from collections.abc import Iterable

import deal
import polars as pl

from georep.contracts import has_columns, sorted_unique
from georep.prep.chunks import chunk_text, chunk_title, split_chunks
from georep.prep.raw_texts import restore_form_feeds

UNIT_COLUMNS = ["id", "datei", "ids", "titel", "roh"]
CHUNK_SCHEMA = {
    "datei": pl.String,
    "stueck": pl.Int32,  # Stelle des Stücks in seiner Datei, ab 0
    "start": pl.Int64,  # Bereich im Rohtext, halboffen
    "end": pl.Int64,
    "text": pl.String,  # was das Modell sieht: Präfix, Titel, Leerzeile, Rumpf
}


def raw_frame(rows: Iterable[tuple[str, str, Iterable[int] | None]]) -> pl.DataFrame:
    """``datei``, ``roh`` aus Zeilen (Name, Rohtext, Formfeeds), mit den Formfeeds zurück.

    Nur Texte, die ohne Leerraum nicht leer sind; nach Dateiname sortiert.
    """
    kept = [
        (name, restore_form_feeds(text, tuple(feeds or ())))
        for name, text, feeds in rows
        if text.strip()
    ]
    return pl.DataFrame(kept, schema={"datei": pl.String, "roh": pl.String}, orient="row").sort(
        "datei"
    )


def _units_hold(
    corpus: pl.DataFrame, raw: pl.DataFrame, title_chars: int, result: pl.DataFrame
) -> bool:
    return (
        result.columns == UNIT_COLUMNS
        and sorted_unique(result, "id")
        and result.get_column("datei").n_unique() == result.height
        and all(ids[0] == unit for unit, ids in result.select("id", "ids").iter_rows())
    )


@deal.pre(
    lambda corpus, raw, title_chars: (
        has_columns(corpus, "id", "name", "file_name") and has_columns(raw, "datei", "roh")
    ),
    message="Korpus mit id, name, file_name; Rohtext mit datei, roh",
)
@deal.ensure(_units_hold, message="je Datei eine Einheit unter ihrer kleinsten ID, nach ID")
def build_units(corpus: pl.DataFrame, raw: pl.DataFrame, title_chars: int) -> pl.DataFrame:
    """Je Datei mit Rohtext eine Einheit: ``id`` (kleinste), ``datei``, ``ids``, ``titel``, ``roh``."""
    documents = corpus.select("id", "name", pl.col("file_name").alias("datei")).filter(
        pl.col("datei").is_not_null() & (pl.col("datei") != "")
    )
    joined = documents.join(raw, on="datei", how="inner")
    ids = joined.group_by("datei").agg(pl.col("id").sort().alias("ids"))
    first = joined.sort("id").unique(subset="datei", keep="first", maintain_order=True)
    units = first.join(ids, on="datei", how="left").sort("id")
    titles = [chunk_title(name, title_chars) for name in units.get_column("name").to_list()]
    return units.with_columns(pl.Series("titel", titles, dtype=pl.String)).select(UNIT_COLUMNS)


def _chunks_hold(
    units: pl.DataFrame, chunk_chars: int, overlap_chars: int, prefix: str, result: pl.DataFrame
) -> bool:
    per_file = result.group_by("datei").agg(
        pl.len().alias("n"), pl.col("stueck").min().alias("lo"), pl.col("stueck").max().alias("hi")
    )
    return (
        dict(result.schema) == CHUNK_SCHEMA
        and per_file.height == units.height
        and bool((per_file["lo"] == 0).all() and (per_file["hi"] == per_file["n"] - 1).all())
    )


@deal.pre(lambda units, chunk_chars, overlap_chars, prefix: units.columns == UNIT_COLUMNS)
@deal.ensure(_chunks_hold, message="jede Einheit hat Stücke, lückenlos ab 0 gezählt")
def unit_chunks(
    units: pl.DataFrame, chunk_chars: int, overlap_chars: int, prefix: str
) -> pl.DataFrame:
    """Die Stücke aller Einheiten in Folge der Einheiten, je Datei ab 0 gezählt."""
    rows: list[tuple[str, int, int, int, str]] = []
    for datei, title, raw in units.select("datei", "titel", "roh").iter_rows():
        for place, chunk in enumerate(split_chunks(title, raw, chunk_chars, overlap_chars)):
            rows.append(
                (datei, place, chunk.start, chunk.end, chunk_text(prefix, title, chunk.body))
            )
    return pl.DataFrame(rows, schema=CHUNK_SCHEMA, orient="row")
