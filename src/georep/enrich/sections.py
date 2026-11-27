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

Stufe 3 (Messdokument § 7): ``dokumente_kopf`` steht als Parquet in den Downloads, ohne CSV, ohne
die Rolle des Unterzeichners und ohne Werte, die einen Namen tragen (``head_view``), mit dem
Prüfsatz aus ``validierung/11-struktur-f4/guete.json`` und den Zahlen von ``struktur-1`` gegen die
Labels (``HEAD_CHECK``); nur in einem gemessenen Datensatz mit Rohtext (``report.downloads``). Die
Abschnitte selbst bleiben unveröffentlicht: sie sind Rohtext.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import deal
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
from georep.report.downloads import (
    LabelCheck,
    Measure,
    capitalized,
    check_files,
    has_extracted_rows,
    is_named,
    measured,
    named,
    names_in,
    read_quality,
    without_name,
)
from georep.report.tables import PublishedTable, TableCheck
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


# --- Stufe 3: der Kopf als Download (Messdokument § 7, docs/plan-zeigen-2026-11.md, § 5) -------
# Was ``guete.json`` nicht trägt: ``struktur-1`` gegen die Endlabels der 200 Dokumente (§ 4.1);
# der slow-Test ``tests/golden/test_structure_numbers.py`` rechnet jede Zahl aus
# ``validierung/11-struktur-f4/labels.csv`` gegen diese Konstante nach.
HEAD_CHECK = LabelCheck(
    project="11-struktur-f4",
    codebook_version="2026-11-23",
    units=200,
    measures=(
        Measure("Beschlussvorschlag zeilengenau", 200, hits=188),
        Measure("Amt", 125, hits=125),
        Measure("Amtsbezeichnung", 69, hits=69),
        Measure("Zeilen der Beratungsfolge", 168, hits=160),
        Measure("Briefdatum", 73, hits=73),
        Measure("Datum der Sitzung", 48, hits=48),
    ),
)
# Nicht im Download: die Rolle im Unterschriftsblock. Sie stammt aus der Liste des Profils und ist
# kein Name, aber „Oberbürgermeister" oder „Fraktionsvorsitzender" unter einem Brief zeigt auf eine
# Person, und § 7 sieht keinen Unterzeichner vor.
WITHHELD = ("unterzeichner_rolle",)
# Freitext im Kopf: hier kann ein Name stehen, wenn der Kopf in das nächste Feld läuft
FREE_TEXT = ("formular", "amt_name", "sitzung_gremium")


def _no_name_left(frame: pl.DataFrame, settings: Settings, result: pl.DataFrame) -> bool:
    return not names_in(result, named(settings))


@deal.ensure(_no_name_left, message="kein Wert der Sicht trägt einen Namen")
def head_view(frame: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """``dokumente_kopf``, wie es veröffentlicht wird: ohne Unterzeichner, ohne Werte mit Namen.

    Ein Freitext, in dem hinter einem Titel ein Name beginnt (``report.downloads.named``), wird
    leer; in der Hauptperiode vier Amtszeilen, in die das Feld der Dezernentin oder des Dezernenten
    läuft. Ebenso das Gremium einer Zeile der Beratungsfolge.
    """
    pattern = named(settings)
    gremium = pl.field("gremium")
    return frame.drop(WITHHELD).with_columns(
        *(without_name(column, pattern) for column in FREE_TEXT),
        pl.col("beratungsfolge").list.eval(
            pl.element().struct.with_fields(
                pl.when(is_named(gremium, pattern)).then(None).otherwise(gremium).alias("gremium")
            )
        ),
    )


def head_shown(path: Path, settings: Settings) -> bool:
    """Nur gemessen und mit Rohtext: auf Pages die Hauptperiode (``report.downloads``)."""
    return measured(settings, HEAD_CHECK.project) and has_extracted_rows(path)


def head_sentence(settings: Settings) -> str:
    """Der Prüfsatz unter den Downloads: der Satz aus ``guete.json``, dann die Zahlen aus § 4.1."""
    quality = read_quality(settings, HEAD_CHECK)
    decision, *head = HEAD_CHECK.measures
    return (
        f"{capitalized(quality.text())}. Gegen ihre Labels richtig (95-%-Intervall nach "
        f"Wilson): {decision.text()}; im Kopf {', '.join(m.text() for m in head)}. Ohne die "
        "Abschnitte selbst und ohne Unterzeichner."
    )


_ID = ("OParl-URL des Dokuments", "")


def head_columns(settings: Settings) -> dict[str, tuple[str, str]]:
    """Die Spaltendoku der Sicht; ``rumpf_leer`` nennt die Schwelle aus den Settings."""
    return {
        "id": _ID,
        "formular": (
            "Titel des Formulars im Kopf (Beschlussvorlage, Informationsvorlage, Antrag, Anfrage "
            "…) aus der Liste des Profils; leer ohne Formularkopf",
            "",
        ),
        "amt_nr": ("Nummer des federführenden Amts im Kopffeld, etwa 66 oder 01/13", ""),
        "amt_name": (
            "Name des federführenden Amts im Kopffeld, ohne erkannte Nummer das ganze Feld; leer, "
            "wo ein Name darin stünde",
            "",
        ),
        "dezernat_titel": (
            "Amtsbezeichnung im Feld der Dezernentin oder des Dezernenten, aus der Liste des "
            "Profils; nie ein Name",
            "",
        ),
        "beratungsfolge": (
            "Zeilen der Beratungsfolge im Kopf: gremium wie geschrieben, gremium_kuerzel aus dem "
            "Profil, datum, qualitaet (Entscheidung, Vorberatung …)",
            "Liste",
        ),
        "sitzung_gremium": (
            "Gremium der Sitzung, zu der ein Brief eingereicht ist: der Name aus dem Profil, wo "
            "sitzung_kuerzel gesetzt ist, sonst wie im Text ohne den Ort dahinter",
            "",
        ),
        "sitzung_kuerzel": ("Kürzel dieses Gremiums aus dem Profil; leer ohne Zuordnung", ""),
        "sitzung_datum": ("Datum dieser Sitzung", "Datum"),
        "briefdatum": ("Datum des Briefs, aus der Zeile mit Ort und Datum", "Datum"),
        "beschlussvorschlag": ("das Dokument trägt einen Beschlussvorschlag", ""),
        "beschlussvorschlag_quelle": (
            "woran er erkannt ist: ueberschrift, einleitung (ein Satz wie „… zu beschließen:“) "
            "oder beschlusssatz ohne Überschrift; leer ohne Vorschlag",
            "",
        ),
        "rumpf_leer": (
            f"weniger als {settings.structure.min_body_chars} Zeichen Text hinter dem Betreff, "
            "ohne Kopf, Seitenkopfzeilen und Leerraum",
            "",
        ),
        "extractor": (
            "Regelwerk und Extraktor des Rohtexts, etwa struktur-1/pypdf-7.1.0+roh; leer ohne "
            "Rohtext",
            "",
        ),
    }


TABLES = (
    PublishedTable(
        "dokumente_kopf",
        lambda layout: sections_files(layout).head,
        "Kopf je Ratsdokument: Formular, federführendes Amt, Amtsbezeichnung, Beratungsfolge, "
        "Sitzung, Briefdatum, Beschlussvorschlag; ohne Namen",
        {},
        optional=True,
        enabled=lambda settings: settings.structure.enabled,
        describe=head_columns,
        csv=None,
        view=head_view,
        shown=head_shown,
        check=TableCheck(lambda settings: check_files(settings, HEAD_CHECK), head_sentence),
    ),
)

CONTRIBUTION = Contribution("11-struktur", early_steps=sections_steps, tables=TABLES)
