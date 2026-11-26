"""Beitrag von Vorhaben 11: Abschnitte und Kopf je Ratsdokument (Struktur der Dokumente).

Ein **früher** Schritt (``early_steps``, unmittelbar vor ``weights``, Punkt 74): Vorhaben 16
rechnet die Stelle eines Treffers aus den Abschnitten, und ``weights`` liest sie. ``sections``
liest den Korpus und den Rohtext (Fundament F1) und schreibt

* ``processed/dokumente_abschnitte.parquet``: Spannen nach F3 auf dem Rohtext, Abschnitte
  (``kind = "abschnitt"``, Ebene 1 mit ``section == norm``) und Kopffelder (``section = "kopf"``);
* ``processed/dokumente_kopf.parquet``: je Korpus-ID eine Zeile mit Formular, Amt,
  Amtsbezeichnung, Beratungsfolge, Sitzung, Briefdatum, Beschlussvorschlag und ``rumpf_leer``.

Ohne Rohtext (ein Profil ohne PDFs und ohne Rohtextpaket, etwa auf Pages) läuft der Schritt
trotzdem: keine Spannen und je Korpus-ID eine leere Zeile (Messdokument 11, § 10, Punkt 10). Die
Regeln stehen in ``prep.structure``; hier steht nur, was gelesen und geschrieben wird. Die Pfade
gehören diesem Modul (Synergien 2026-11, § 2.1): wer die Abschnitte liest (12, 16, 20, 21, 24),
nimmt sie aus ``sections_files``.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import polars as pl

from georep.enrich import Contribution
from georep.http import Transport
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import Step
from georep.prep.bodies import CONSULTATION, merge_consultations
from georep.prep.structure import (
    STRUCTURE_SCHEMA_VERSION,
    BodyNames,
    StructureRules,
    consultation_agreement,
    decision_share,
    structure_tables,
)
from georep.settings import Settings
from georep.stores import RAW_TEXT_SCHEMA_VERSION, stored_schema_version


class SectionFiles(NamedTuple):
    sections: Path  # Spannen nach F3
    head: Path  # eine Zeile je Korpus-ID


def sections_files(layout: Layout) -> SectionFiles:
    """Die beiden Dateien des Schritts ``sections`` unter ``processed/``."""
    return SectionFiles(
        layout.processed / "dokumente_abschnitte.parquet",
        layout.processed / "dokumente_kopf.parquet",
    )


def raw_text_frame(path: Path) -> pl.DataFrame:
    """``name``, ``text``, ``extractor`` aus dem Rohtextstore; leer, wenn er fehlt oder eine andere
    Schema-Version trägt (dann gilt er als leer wie in ``stores.RawTextStore``)."""
    if not path.exists() or stored_schema_version(path) != str(RAW_TEXT_SCHEMA_VERSION):
        return pl.DataFrame(schema={"name": pl.String, "text": pl.String, "extractor": pl.String})
    return pl.read_parquet(path, columns=["name", "text", "extractor"])


def sections_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Der Schritt ``sections``, wenn das Profil ihn einschaltet; offline, ``http`` bleibt ungenutzt."""
    if not settings.structure.enabled:
        return []
    files = sections_files(layout)
    with_consultations = settings.bodies.consultations is not None

    def sections() -> str:
        rules = StructureRules.from_settings(settings)
        corpus = pl.read_parquet(
            layout.corpus, columns=["id", "paper_type", "file_name", CONSULTATION]
        )
        documents = corpus.join(
            raw_text_frame(layout.raw_texts), left_on="file_name", right_on="name", how="left"
        ).select("id", pl.col("paper_type").fill_null(""), "text", "extractor")
        spans, head = structure_tables(documents, rules, BodyNames.from_settings(settings))
        write_parquet(spans, files.sections, schema_version=STRUCTURE_SCHEMA_VERSION)
        write_parquet(head, files.head, schema_version=STRUCTURE_SCHEMA_VERSION)
        extra = (
            pl.read_parquet(layout.consultations, columns=["id", CONSULTATION])
            if with_consultations
            else None
        )
        found, known = consultation_agreement(
            head, merge_consultations(corpus, extra), settings.bodies.organizations
        )
        hits, expected = decision_share(head, documents, rules)
        with_text = head.filter(pl.col("extractor").is_not_null()).height
        empty = int(head.get_column("rumpf_leer").sum())
        return (
            f"{head.height} Dokumente, {with_text} mit Rohtext, {spans.height} Spannen; "
            f"Beschlussvorschlag in {hits} von {expected} Dokumenten der Arten, die einen "
            f"erwarten; Rumpf leer {empty}; Gremium der Beratungsfolge in OParl {found} von {known}"
        )

    return [
        Step(
            "sections",
            (layout.corpus, layout.raw_texts)
            + ((layout.consultations,) if with_consultations else ()),
            (files.sections, files.head),
            sections,
            STRUCTURE_SCHEMA_VERSION,
        )
    ]


CONTRIBUTION = Contribution("11-struktur", early_steps=sections_steps)
