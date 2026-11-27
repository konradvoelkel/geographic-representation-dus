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

Stufe 3 (Messdokument § 7): ``kennungen`` steht in den Downloads, als Parquet ganz, als CSV nur mit
Bauleitplanung und Beträgen, ohne Spannen, deren Text einen Namen trägt (``spans_view``), mit der
Präzision je Art (``IDENTIFIER_CHECKS``) und dem Prüfsatz aus ``validierung/12-kennungen-f4`` und
``12-kennungen-2-f4``; nur in einem gemessenen Datensatz mit Rohtext (``report.downloads``).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import deal
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
from georep.report.downloads import (
    LabelCheck,
    Measure,
    check_files,
    has_extracted_rows,
    is_named,
    measured,
    named,
    names_in,
    read_quality,
)
from georep.report.tables import CsvPlan, PublishedTable, TableCheck
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


# --- Stufe 3: die Spannen als Download (Messdokument § 7 und § 10, Punkt 8) ---------------------
# Was ``guete.json`` nicht trägt: die Präzision je Art (Art und Grenzen richtig, gewichtet mit
# ``schicht_n``, Wilson mit dem effektiven n nach Kish), so wie das Urteil in § 5 auf ihr steht.
# Bauleitplanung und Betrag (Fassung 1) an Runde 1, Termin und Verwaltungseinheit (Fassung 2) an
# der Bestätigung in Runde 2; der slow-Test ``tests/golden/test_identifiers_labels.py`` rechnet
# Anteil, n und Intervall aus den Labels im Repo nach. Der Recall gehört nicht zu dieser Phase
# (docs/plan-zeigen-2026-11.md, § 4, V3).
ROUND_1 = LabelCheck(
    project="12-kennungen-f4",
    codebook_version="1",
    units=600,
    measures=(
        Measure("Bauleitplanung", 100, share=1.0, interval=(0.957, 1.0)),
        Measure("Betrag", 100, share=0.962, interval=(0.885, 0.988)),
    ),
)
ROUND_2 = LabelCheck(
    project="12-kennungen-2-f4",
    codebook_version="2026-11-23.2",
    units=360,
    measures=(
        Measure("Termin", 30, share=1.0, interval=(0.726, 1.0)),
        Measure("Verwaltungseinheit", 100, share=0.956, interval=(0.851, 0.988)),
    ),
)
IDENTIFIER_CHECKS = (ROUND_1, ROUND_2)
# Die CSV trägt nur Bauleitplanung und Beträge (Messdokument § 7): alle Arten wären als CSV 17,8 MB
# statt 1,2 MB Parquet; diese drei Arten sind 30 180 Zeilen, 4,6 MB (Hauptperiode, 2026-11-27).
CSV_KINDS = ("bplan", "fnp", "betrag")


def _no_name_left(frame: pl.DataFrame, settings: Settings, result: pl.DataFrame) -> bool:
    return not names_in(result, named(settings))


@deal.ensure(_no_name_left, message="keine Spanne der Sicht trägt einen Namen")
def spans_view(frame: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """``kennungen``, wie es veröffentlicht wird: ohne Spannen, deren Text oder Norm einen Namen trägt.

    Eine Spanne fällt ganz weg, statt einen leeren Wert zu tragen, weil F3 ein leeres ``value``
    nur bei Positionsspannen kennt. In der Hauptperiode fällt keine (2026-11-27); in 2014 bis 2020
    wären es 13 Ämter der Form „Beigeordnete …".
    """
    pattern = named(settings)
    return frame.filter(~(is_named(pl.col("value"), pattern) | is_named(pl.col("norm"), pattern)))


def plans_and_amounts(frame: pl.DataFrame) -> pl.DataFrame:
    """Die Zeilen der CSV: Bebauungspläne, FNP-Änderungen und Beträge."""
    return frame.filter(pl.col("kind").is_in(CSV_KINDS))


def spans_shown(path: Path, settings: Settings) -> bool:
    """Nur gemessen und mit Rohtext: auf Pages die Hauptperiode (``report.downloads``)."""
    return all(measured(settings, c.project) for c in IDENTIFIER_CHECKS) and has_extracted_rows(
        path
    )


def spans_sentence(settings: Settings) -> str:
    """Der Prüfsatz: die Präzision je Art, je Runde mit dem Satz aus ihrer ``guete.json``."""
    rounds = [
        f"{', '.join(m.text() for m in check.measures)}; {read_quality(settings, check).text()}"
        for check in IDENTIFIER_CHECKS
    ]
    return (
        "Präzision je Art gegen die Labels (Art und Grenzen richtig, nach Schicht gewichtet, "
        f"95-%-Intervall): {'. '.join(rounds)}. Beträge tragen keine Rolle (Kosten, Zuschuss und "
        "Ertrag sind nicht unterschieden), Termine keine Frist."
    )


TABLES = (
    PublishedTable(
        "kennungen",
        lambda layout: identifiers_files(layout).spans,
        "Kennungen im Rohtext: Bebauungspläne, FNP-Änderungen, Beträge, Termine, Ämter und "
        "Dezernate, je mit Stelle und Normform",
        {
            "id": ("OParl-URL des Dokuments", ""),
            "start": ("Anfang der Spanne im Rohtext, ab 0", "Zeichen"),
            "end": ("Ende der Spanne im Rohtext, ausschließlich", "Zeichen"),
            "kind": (
                "bplan (Bebauungsplan), fnp (Änderung des Flächennutzungsplans), betrag, termin, "
                "amt oder dezernat",
                "",
            ),
            "value": ("der Text an der Stelle, wörtlich mit Zeilenwechseln", ""),
            "norm": (
                "Plannummer; FNP-Änderung n; Betrag in Euro mit zwei Stellen; Termin als Tag, "
                "Monat, Quartal, Jahr mit Zusatz oder relativ:Form; Amt als Nummer des "
                "Ämterverzeichnisses, sonst Name; Dezernat zweistellig",
                "",
            ),
            "section": (
                "Abschnitt (Vorhaben 11), in dem die Spanne beginnt, etwa sachdarstellung oder "
                "kopf_amt; leer außerhalb",
                "",
            ),
            "extractor": (
                "Regelwerk und Extraktor des Rohtexts, etwa kennungen-1/pypdf-7.1.0+roh",
                "",
            ),
            "attr": (
                "nur die Form, keine Deutung: je oder spanne (Betrag), tag, monat, quartal, jahr "
                "oder relativ (Termin), kopf, name, nummer, text oder wort (Amt)",
                "",
            ),
        },
        optional=True,
        enabled=lambda settings: settings.identifiers.enabled,
        csv=CsvPlan(plans_and_amounts, "nur Bebauungspläne, FNP-Änderungen und Beträge"),
        view=spans_view,
        shown=spans_shown,
        check=TableCheck(
            lambda settings: check_files(settings, *IDENTIFIER_CHECKS), spans_sentence
        ),
    ),
)

CONTRIBUTION = Contribution("12-kennungen", steps=identifiers_steps, tables=TABLES)
