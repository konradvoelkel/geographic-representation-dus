"""Beitrag von Vorhaben 12: Kennungen und Beträge als Spannen im Rohtext.

Ein Schritt, offline, vor ``report``:

* ``identifiers`` schreibt ``processed/kennungen.parquet`` (``prep.identifiers``): Bebauungsplan-
  und FNP-Nummern, Euro-Beträge ohne Rolle, Zeitangaben ohne Funktion, Ämter und Dezernate, je als
  Spanne nach F3 mit ``attr`` dahinter, für jede Korpus-ID der Datei.

Er fehlt ohne ``identifiers.enabled``. Ohne Rohtext (ein Profil ohne PDFs und ohne Rohtextpaket,
etwa auf GitHub Pages außer der Hauptperiode) schreibt er dieselbe Tabelle leer, statt den Lauf
scheitern zu lassen (Synergien 2026-11, Konflikt 14). Die Regeln stehen in ``prep.identifiers``;
hier steht nur, welche Dateien gelesen und geschrieben werden. Die Pfade gehören diesem Modul
(Synergien 2026-11, § 2.1): wer die Spannen liest — 21 die Beträge, 24 die Ämter, 29 die
Plannummern —, nimmt sie aus ``identifiers_files``.

``section`` kommt aus den Abschnitten von Vorhaben 11 (``dokumente_abschnitte.parquet``,
``spans.section_of``), einer optionalen Eingabe; das Ämterverzeichnis entsteht je Lauf aus den
Kopffeldern des Korpus.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import polars as pl

from georep.enrich import Contribution
from georep.enrich.sections import sections_files
from georep.http import Transport
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import Step
from georep.prep.identifiers import (
    DOCUMENT_COLUMNS,
    IDENTIFIERS_SCHEMA_VERSION,
    TEXT_COLUMNS,
    IdentifierRules,
    identifier_figures,
    identifier_spans,
    office_directory,
)
from georep.settings import Settings
from georep.spans import SPAN_SCHEMA
from georep.stores import RAW_TEXT_SCHEMA_VERSION, stored_schema_version


class IdentifierFiles(NamedTuple):
    spans: Path


def identifiers_files(layout: Layout) -> IdentifierFiles:
    """Die Spannen unter ``processed/``."""
    return IdentifierFiles(layout.processed / "kennungen.parquet")


def raw_text_frame(path: Path) -> tuple[pl.DataFrame, str]:
    """Der Rohtextstore als Tabelle (``name``, ``text``, ``extractor``) und, wenn er nicht gilt, warum.

    Eine Datei mit anderer Schema-Version gilt als leer, wie ``stores.RawTextStore`` sie liest.
    """
    empty = pl.DataFrame(schema=dict.fromkeys(TEXT_COLUMNS, pl.String()))
    version = stored_schema_version(path)
    if version != str(RAW_TEXT_SCHEMA_VERSION):
        return (
            empty,
            f"{path.name} trägt Schema-Version {version}, gelesen wird {RAW_TEXT_SCHEMA_VERSION}",
        )
    return pl.read_parquet(path, columns=list(TEXT_COLUMNS)), ""


def identifiers_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Der Schritt ``identifiers``, wenn das Profil ihn einschaltet.

    Offline; ``http`` (Fundament F7) bleibt ungenutzt.
    """
    if not settings.identifiers.enabled:
        return []
    files = identifiers_files(layout)
    # Vorhaben 11: die Abschnitte als optionale Eingabe (ihr Hash steht im Stamp, Fundament F1);
    # ``sections`` ist ein früher Schritt und läuft vorher, ohne ``structure.enabled`` fehlt die
    # Datei, und ``section`` bleibt leer
    abschnitte = sections_files(layout).sections

    def identifiers() -> str:
        texts, stale = raw_text_frame(layout.raw_texts)
        documents = pl.read_parquet(layout.corpus, columns=list(DOCUMENT_COLUMNS))
        rules = IdentifierRules.from_settings(settings.identifiers)
        files_of_corpus = documents.select("file_name").drop_nulls().unique()
        heads = (
            texts.filter(pl.col("text").is_not_null())
            .join(files_of_corpus, left_on="name", right_on="file_name", how="semi")
            .sort("name")
            .get_column("text")
        )
        directory = office_directory(heads, rules)
        sections = (
            pl.read_parquet(abschnitte, columns=list(SPAN_SCHEMA)) if abschnitte.exists() else None
        )
        spans = identifier_spans(texts, documents, rules.with_directory(directory), sections)
        write_parquet(spans, files.spans, schema_version=IDENTIFIERS_SCHEMA_VERSION)
        if heads.len() == 0:
            reason = f" ({stale})" if stale else ""
            return f"kein Rohtext{reason}: 0 Spannen"
        figures = identifier_figures(spans)
        kinds = ", ".join(f"{figures[k]} {k}" for k in settings.identifiers.kinds)
        return (
            f"{spans.height} Spannen in {figures['dokumente']} Dokumenten aus {heads.len()} "
            f"Rohtexten: {kinds}; Ämterverzeichnis {len(directory)} Namen"
        )

    return [
        Step(
            "identifiers",
            (layout.raw_texts, layout.corpus),
            (files.spans,),
            identifiers,
            IDENTIFIERS_SCHEMA_VERSION,
            optional=(abschnitte,),
        )
    ]


CONTRIBUTION = Contribution("12-kennungen", steps=identifiers_steps)
