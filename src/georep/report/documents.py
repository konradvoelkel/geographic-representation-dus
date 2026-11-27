"""Dokumente je Begriff für die Seite: ``data/dokumente.json``, nachgeladen beim ersten Klick.

Nur Dokumente mit mindestens einem Treffer in einem sichtbaren Begriff, ohne Texte: Datum,
Drucksache, Titel, Art und der Link auf das PDF im Ratsinformationssystem (ein gemeinsames Präfix,
je Dokument nur der Rest). Begriffe zeigen als Indizes auf die Dokumentliste, neueste zuerst.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence

import deal
import polars as pl

from georep.analysis.parties import ART, PARTEIEN
from georep.contracts import has_columns
from georep.search.index import HITS, PAPER_IDS, TERM

DOCUMENT_COLUMNS = ["id", "name", "reference", "date", "paper_type", "download_url"]
# Reihenfolge je Dokument im JSON; das JavaScript des Rahmens liest sie über diese Indizes.
# Option 04 hängt ``urheber`` an (Label der Partei oder die Klasse); eine weitere Option darf
# ebenso anhängen, nie dazwischen schieben (docs/plans/00-synergien.md, § 1).
FIELDS = ("link", "datum", "drucksache", "titel", "art", "urheber")


def _https(url: str) -> str:
    return "https://" + url[len("http://") :] if url.startswith("http://") else url


def listed_link(url: str, base: str) -> str:
    """Der Link eines Dokuments, wie ``dokumente.json`` ihn trägt: als https, ohne das Präfix.

    Review N4: ``report.build.write_dialogs`` vergleicht damit den ersten und letzten Link.
    """
    full = _https(url)
    return full[len(base) :] if base and full.startswith(base) else full


def download_base(urls: Sequence[str]) -> str:
    """Das gemeinsame Verzeichnis der Download-URLs, als https; leer, wenn es keines gibt."""
    if not urls:
        return ""
    first = urls[0].rsplit("/", 1)[0] + "/"
    return _https(first) if all(u.startswith(first) for u in urls) else ""


def originator_labels(
    attribution: pl.DataFrame | None, parties: Mapping[str, str]
) -> dict[str, str]:
    """Je Dokument-ID ein Wort für den Dialog: die Parteien, sonst die Klasse.

    ``parties`` bildet Schlüssel auf Label ab (``GRUENE`` -> ``Bündnis 90/Die Grünen``). Ohne
    Zuordnungstabelle (der Schritt ``parties`` lief nicht) bleibt die Abbildung leer und das Feld
    je Dokument ein leerer String; das JavaScript lässt die Zeile dann weg.
    """
    if attribution is None:
        return {}
    found: dict[str, str] = {}
    for row in attribution.select("id", ART, PARTEIEN).iter_rows(named=True):
        keys = row[PARTEIEN] or []
        labels = [parties.get(key, key) for key in keys]
        found[row["id"]] = ", ".join(labels) if labels else str(row[ART])
    return found


def _inputs_complete(
    corpus: pl.DataFrame,
    index: pl.DataFrame,
    hidden: Sequence[str],
    *,
    version: str,
    generated_at: dt.datetime,
    originators: Mapping[str, str] = {},
) -> bool:
    return has_columns(corpus, *DOCUMENT_COLUMNS) and has_columns(index, TERM, PAPER_IDS, HITS)


def _visible(index: pl.DataFrame, hidden: Sequence[str]) -> pl.DataFrame:
    return index.filter(~pl.col(TERM).is_in(list(hidden)) & (pl.col(HITS) > 0))


def _listed(corpus: pl.DataFrame, visible: pl.DataFrame) -> pl.DataFrame:
    """Die Dokumente des Dialogs in seiner Folge: neueste zuerst, bei gleichem Datum nach ID."""
    ids = visible.get_column(PAPER_IDS).explode().drop_nulls().unique().to_list()
    return (
        corpus.filter(pl.col("id").is_in(ids))
        .select(DOCUMENT_COLUMNS)
        .sort(["date", "id"], descending=[True, False])
    )


def document_order(corpus: pl.DataFrame, index: pl.DataFrame, hidden: Sequence[str]) -> list[str]:
    """Die Korpus-IDs in der Folge von ``dokumente.json``: Index ``i`` dort ist ``result[i]``.

    Vorarbeit V2 (``report.dialog``): die Dateien der Dialog-Haken zeigen mit diesen Indizes auf
    die Dokumente des Dialogs; ``documents_payload`` baut seine Liste aus derselben Funktion.
    """
    return _listed(corpus, _visible(index, hidden)).get_column("id").to_list()


@deal.pre(_inputs_complete, message="Korpus-Metadaten und Index mit ihren Pflichtspalten")
def documents_payload(
    corpus: pl.DataFrame,
    index: pl.DataFrame,
    hidden: Sequence[str],
    *,
    version: str,
    generated_at: dt.datetime,
    originators: Mapping[str, str] = {},
) -> dict[str, object]:
    visible = _visible(index, hidden)
    documents = _listed(corpus, visible)
    position = {paper_id: i for i, paper_id in enumerate(documents.get_column("id").to_list())}
    urls: list[str] = documents.get_column("download_url").to_list()
    base = download_base(urls)
    rows = [
        [
            listed_link(url, base),
            row["date"].isoformat() if row["date"] is not None else "",
            row["reference"] or "",
            row["name"] or "",
            row["paper_type"] or "",
            originators.get(row["id"], ""),  # Option 04
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
