"""Dokumente je Begriff für die Seite: ``data/dokumente.json``, nachgeladen beim ersten Klick.

Nur Dokumente mit mindestens einem Treffer in einem sichtbaren Begriff, ohne Texte: Datum,
Drucksache, Titel, Art und der Link auf das PDF im Ratsinformationssystem (ein gemeinsames Präfix,
je Dokument nur der Rest). Begriffe zeigen als Indizes auf die Dokumentliste, neueste zuerst.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import deal
import polars as pl

from georep.contracts import has_columns
from georep.search.index import HITS, PAPER_IDS, TERM

DOCUMENT_COLUMNS = ["id", "name", "reference", "date", "paper_type", "download_url"]
FIELDS = ("link", "datum", "drucksache", "titel", "art")  # Reihenfolge je Dokument im JSON


def _https(url: str) -> str:
    return "https://" + url[len("http://") :] if url.startswith("http://") else url


def download_base(urls: Sequence[str]) -> str:
    """Das gemeinsame Verzeichnis der Download-URLs, als https; leer, wenn es keines gibt."""
    if not urls:
        return ""
    first = urls[0].rsplit("/", 1)[0] + "/"
    return _https(first) if all(u.startswith(first) for u in urls) else ""


def _inputs_complete(
    corpus: pl.DataFrame,
    index: pl.DataFrame,
    hidden: Sequence[str],
    *,
    version: str,
    generated_at: dt.datetime,
) -> bool:
    return has_columns(corpus, *DOCUMENT_COLUMNS) and has_columns(index, TERM, PAPER_IDS, HITS)


@deal.pre(_inputs_complete, message="Korpus-Metadaten und Index mit ihren Pflichtspalten")
def documents_payload(
    corpus: pl.DataFrame,
    index: pl.DataFrame,
    hidden: Sequence[str],
    *,
    version: str,
    generated_at: dt.datetime,
) -> dict[str, object]:
    visible = index.filter(~pl.col(TERM).is_in(list(hidden)) & (pl.col(HITS) > 0))
    ids = visible.get_column(PAPER_IDS).explode().drop_nulls().unique().to_list()
    documents = (
        corpus.filter(pl.col("id").is_in(ids))
        .select(DOCUMENT_COLUMNS)
        .sort(["date", "id"], descending=[True, False])
    )
    position = {paper_id: i for i, paper_id in enumerate(documents.get_column("id").to_list())}
    urls: list[str] = documents.get_column("download_url").to_list()
    base = download_base(urls)
    rows = [
        [
            _https(url)[len(base) :] if base and _https(url).startswith(base) else _https(url),
            row["date"].isoformat() if row["date"] is not None else "",
            row["reference"] or "",
            row["name"] or "",
            row["paper_type"] or "",
        ]
        for row, url in zip(documents.iter_rows(named=True), urls, strict=True)
    ]
    terms = {
        row[TERM]: sorted(position[p] for p in row[PAPER_IDS] if p in position)
        for row in visible.sort(TERM).iter_rows(named=True)
    }
    return {
        "version": version,
        "generated_at": generated_at.isoformat(),
        "fields": list(FIELDS),
        "base": base,
        "documents": rows,
        "terms": terms,
    }
