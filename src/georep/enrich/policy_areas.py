"""Beitrag von Vorhaben 19: Politikfelder nach dem Comparative Agendas Project (CAP), Weg 3b.

Messdokument ``docs/plans/19-politikfelder.md``, § 5, § 6 und § 10. Das Urteil ist Weg 3b, ein
Klassifikator (``xlm-roberta-large``, feinjustiert auf den menschlich kodierten deutschen CAP-Daten
und auf Silberlabels des lokalen Sprachmodells für 4 200 Ratsdokumente). Er braucht torch, und torch
kommt nie ins Paket (Plan § 2.8, ``uv.lock``). Darum hat das Vorhaben zwei Teile:

1. **Die Vorhersage läuft außerhalb des Pakets.** ``georep policy-areas export <profil>`` schreibt je
   Profil die Eingabe des Klassifikators (``classifier_input``): je Korpus-ID der Titel und die
   ersten ``policy_areas.chars`` Zeichen des Rohtexts von Fundament F1, Leerraum zusammengezogen,
   genau wie ``schreibe_eingabe()`` des Messskripts (ein Test hält beide bytegleich). Das
   Trainingsskript ``docs/plans/19-politikfelder-training.py --vorhersage <eingabe>`` sagt daraus im
   Trainings-Venv unter der GPU-Sperre vorher.
2. **Im Paket nur das Ergebnis**: ``georep pack --policy-areas --from <datei>`` friert es je Profil
   ein, ``bootstrap`` kopiert es, und der Beitrag reicht es geprüft weiter (unten).

Die Pfade gehören diesem Modul (Synergien 2026-11, § 2.1): wer die Tabellen liest, nimmt sie aus
``policy_area_files``.
"""

from __future__ import annotations

from pathlib import Path

import deal
import polars as pl

from georep.contracts import one_row_per_document
from georep.errors import MissingInputError
from georep.layout import Layout
from georep.settings import Settings

INPUT_SCHEMA_VERSION = 1  # die Eingabe des Klassifikators (``georep policy-areas export``)
INPUT_SCHEMA = {"id": pl.String, "text": pl.String, "mit_text": pl.Boolean, "gekuerzt": pl.Boolean}


def export_path(layout: Layout) -> Path:
    """Wohin ``georep policy-areas export`` ohne ``--out`` schreibt: neben die Messdateien des Profils."""
    return layout.root / "messung" / "19-politikfelder-eingabe.parquet"


def _one_input_per_document(
    corpus: pl.DataFrame, raw: pl.DataFrame, chars: int, result: pl.DataFrame
) -> bool:
    return one_row_per_document(result, corpus.get_column("id").to_list()) and dict(
        result.schema
    ) == dict(INPUT_SCHEMA)


@deal.pre(lambda corpus, raw, chars: chars >= 1, message="chars mindestens 1")
@deal.ensure(_one_input_per_document, message="eine Eingabe je Korpus-ID, im Schema der Eingabe")
def classifier_input(corpus: pl.DataFrame, raw: pl.DataFrame, chars: int) -> pl.DataFrame:
    """Die Eingabe des Klassifikators je Korpus-ID, nach ``id`` sortiert.

    ``corpus`` trägt ``id``, ``name`` (Titel) und ``file_name``, ``raw`` den Rohtextstore von F1
    (``name`` ist der Dateiname, ``text`` der Rohtext). ``text`` ist Titel, Zeilenumbruch und die
    ersten ``chars`` Zeichen des Rohtexts, an jedem Leerraum getrennt und mit einem Leerzeichen
    verbunden, wie ``schreibe_eingabe()`` des Messskripts (``" ".join(...split())``, also mit dem
    Leerraum, den Python kennt, nicht dem von Polars). ``mit_text`` sagt, ob der Rohtext mehr als
    Leerraum trägt: nur dann sagt das Trainingsskript ein Feld voraus, sonst bliebe ein Titel ohne
    Text, an dem nichts geprüft ist. ``gekuerzt`` sagt, ob der Rohtext länger als ``chars`` ist.
    Ein Dokument, dessen Datei der Store nicht kennt, hat leeren Rohtext.
    """
    texts = dict(
        zip(raw.get_column("name").to_list(), raw.get_column("text").to_list(), strict=True)
    )
    rows = []
    for doc, title, file_name in corpus.select("id", "name", "file_name").sort("id").iter_rows():
        text = (texts.get(file_name) or "") if file_name is not None else ""
        rows.append(
            (
                doc,
                " ".join(f"{title or ''}\n{text[:chars]}".split()),
                bool(text.strip()),
                len(text) > chars,
            )
        )
    return pl.DataFrame(rows, schema=INPUT_SCHEMA, orient="row")


@deal.raises(MissingInputError)
def export_input(layout: Layout, settings: Settings) -> pl.DataFrame:
    """Die Eingabe dieses Profils aus Korpus und Rohtextstore (F1, ``Layout.raw_texts``)."""
    for path, how in (
        (layout.corpus, "`georep run corpus` baut den Korpus"),
        (layout.raw_texts, "`georep run raw_texts` liest ihn aus den PDFs (Fundament F1)"),
    ):
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; {how}")
    corpus = pl.read_parquet(layout.corpus, columns=["id", "name", "file_name"])
    raw = pl.read_parquet(layout.raw_texts, columns=["name", "text"])
    return classifier_input(corpus, raw, settings.policy_areas.chars)
