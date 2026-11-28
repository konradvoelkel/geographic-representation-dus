"""Beitrag von Vorhaben 26: Beschlusslage je Ratsdokument und Antragserfolg je Fraktion.

Zwei Schritte, beide offline, hinter ``outcomes.enabled`` (``docs/plans/26-beschluesse.md``, § 6
und § 10):

* ``council_results`` schreibt den Beratungsverlauf ``processed/beratungsverlauf.parquet``: je
  Beratung eines Dokuments jeder Tagesordnungspunkt mit Gremium, Sitzung und dem Eintrag der
  Sitzungsleitung. Die Quelle ist der Netzlauf von Fundament F6 (``raw/meetings.jsonl``,
  ``agenda_items.jsonl``, ``consultations.jsonl``, gelesen mit den Modellen aus ``georep.oparl``),
  sonst das Paket, das ``bootstrap`` nach ``raw/tagesordnungspunkte.parquet`` legt: GitHub Pages
  hat kein Netz. Der Name ist nicht ``beratungsfolge``; die gehört Punkt 58.
* ``outcomes`` schreibt die Beschlusslage je Korpus-ID (``processed/beschlusslage.parquet``) und
  den Antragserfolg je Fraktion (``processed/antragserfolg.parquet``). Dazu liest er die Rollen und
  die Kanten von Vorhaben 14 und die Antragsteller von Vorhaben 15; ohne deren Schritte fehlt er.

Dazu (Stufe 3, Messdokument § 7) drei veröffentlichte Tabellen, drei Abschnitte auf
``vorgaenge.html`` von Vorhaben 14 (``Contribution.sections``, Vorarbeit V1) und der Haken
``beschluesse`` im Dokumentdialog (Vorarbeit V2); was sie zeigen, steht in ``report.outcomes``.

Die Regeln stehen in ``analysis.outcomes``; hier steht nur, was gelesen und geschrieben wird. Die
Pfade gehören diesem Modul (Synergien 2026-11, § 2.1).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import polars as pl

from georep.analysis.outcomes import (
    AGENDA_NAME,
    AGENDA_SCHEMA_VERSION,
    ANGENOMMEN,
    MOTION,
    OUTCOMES_SCHEMA_VERSION,
    OutcomeRules,
    agenda_rows,
    check_agenda,
    classify_outcomes,
    complete_outcomes,
    first_followups,
    motion_success,
    outcome_figures,
    period_key,
    progress,
    review_only,
)
from georep.council import JsonlStore, council_files
from georep.enrich import Contribution
from georep.enrich.functions import functions_files
from georep.enrich.procedures import procedure_files
from georep.errors import MissingInputError, SchemaError
from georep.http import Transport
from georep.io import write_parquet
from georep.layout import Layout
from georep.oparl import OparlAgendaItem, OparlConsultation, OparlMeeting
from georep.pipeline import Step
from georep.prep.references import ReferenceRules, role_of
from georep.report.dialog import DialogHook
from georep.report.outcomes import (
    DIALOG_NAME,
    DIALOG_TITLE,
    HOST,
    SECTION_OUTCOMES,
    SECTION_SESSION,
    SECTION_SUCCESS,
    dialog_inputs,
    dialog_rows,
    outcomes_section_data,
    outcomes_section_inputs,
    section_links,
    session_section_data,
    session_section_inputs,
    success_section_data,
    success_section_inputs,
    table_check_files,
    table_sentence,
)
from georep.report.pages import PageSection
from georep.report.tables import PublishedTable, TableCheck
from georep.settings import Settings
from georep.stores import stored_schema_version


class OutcomeFiles(NamedTuple):
    agenda: Path  # Kopie des Pakets, von ``bootstrap`` gelegt
    progress: Path
    outcomes: Path
    success: Path


def outcome_files(layout: Layout) -> OutcomeFiles:
    """Die Pfade des Vorhabens; sie gehören dem Modul, nicht ``Layout`` (Synergie, § 2.1)."""
    return OutcomeFiles(
        agenda=layout.raw / AGENDA_NAME,
        progress=layout.processed / "beratungsverlauf.parquet",
        outcomes=layout.processed / "beschlusslage.parquet",
        success=layout.processed / "antragserfolg.parquet",
    )


def network_inputs(layout: Layout) -> tuple[Path, Path, Path]:
    """Die drei Dateien des Netzlaufs (Fundament F6), aus denen die Tabelle entsteht."""
    council = council_files(layout)
    return (council.meetings, council.agenda_items, council.consultations)


def unfinished_fetches(layout: Layout) -> list[Path]:
    """Die Fortschrittsdateien offener Abrufe von ``meetings`` und ``consultations`` (Punkt 70).

    Solange eine liegt, ist der Abruf nicht zu Ende; die JSONL-Datei daneben ist dann die eines
    früheren Laufs, und ``pack --outcomes`` verweigert sie aus demselben Grund (Review 2026-11-24, K2).
    """
    council = council_files(layout)
    return [
        council.progress(s) for s in ("meetings", "consultations") if council.progress(s).is_file()
    ]


def progress_inputs(layout: Layout) -> tuple[Path, Path]:
    """Die beiden Fortschrittsdateien als optionale Eingaben: kommt eine dazu, ist der Verlauf veraltet."""
    council = council_files(layout)
    return (council.progress("meetings"), council.progress("consultations"))


def agenda_from_network(layout: Layout, papers: list[str]) -> pl.DataFrame:
    """Die Tabelle „Paper × Tagesordnungspunkt" aus dem Netzlauf, für die Dokumente ``papers``."""
    council = council_files(layout)
    return agenda_rows(
        JsonlStore(council.meetings, OparlMeeting).load(),
        JsonlStore(council.agenda_items, OparlAgendaItem).load(),
        JsonlStore(council.consultations, OparlConsultation).load().values(),
        papers,
    )


def read_agenda(layout: Layout, papers: list[str]) -> tuple[pl.DataFrame, str]:
    """(Tabelle, Quelle): der Netzlauf, wenn alle drei Dateien da sind und kein Abruf offen ist,
    sonst das Paket.

    Der Netzlauf gilt vor dem Paket: er ist die Quelle des Pakets und wo er liegt, jünger. Ein
    offener Abruf (``unfinished_fetches``) zählt nicht als Netzlauf. Fehlt beides, ist das ein
    ``MissingInputError`` mit beiden Wegen, kein leerer Verlauf, der jedes Dokument still
    ``ohne_ergebnis`` machte.
    """
    network = network_inputs(layout)
    unfinished = unfinished_fetches(layout)
    if all(path.is_file() for path in network) and not unfinished:
        return agenda_from_network(layout, papers), "Netzlauf"
    package = outcome_files(layout).agenda
    if package.is_file():
        version = stored_schema_version(package)
        if version != str(AGENDA_SCHEMA_VERSION):  # Review 2026-11-24, N10
            raise SchemaError(
                f"{package}: Schema-Version {version}, gelesen wird {AGENDA_SCHEMA_VERSION}; das "
                "Paket braucht ein neues `georep pack --outcomes`"
            )
        frame = check_agenda(pl.read_parquet(package), str(package))
        return frame.filter(pl.col("id").is_in(papers)), "Paket"
    missing = [str(path) for path in (*network, package) if not path.is_file()]
    open_fetches = (
        f"; Abruf unvollständig: {', '.join(str(path) for path in unfinished)}"
        if unfinished
        else ""
    )
    raise MissingInputError(
        "Schritt council_results: weder der Netzlauf (`georep fetch meetings consultations`, "
        "Fundament F6) noch das Paket ([outcomes].package, `georep bootstrap`) liegt vor"
        + (f"; fehlt: {', '.join(missing)}" if missing else "")
        + open_fetches
    )


def outcomes_built(settings: Settings) -> bool:
    """Ob der Schritt ``outcomes`` gebaut wird: 26 an, Vorhaben 14 an und die Antragsteller von 15
    (``functions.enabled`` mit Urhebern). Sonst steht nur der Beratungsverlauf da."""
    return (
        settings.outcomes.enabled
        and settings.procedures.enabled
        and settings.functions.enabled
        and bool(settings.originators.parties)
    )


def progress_built(settings: Settings) -> bool:
    """Ob ``council_results`` den Beratungsverlauf schreibt: ``outcomes.enabled``."""
    return settings.outcomes.enabled


def outcome_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Die Schritte ``council_results`` und, mit 14 und 15, ``outcomes``; offline.

    ``http`` (Fundament F7) bleibt ungenutzt. ``outcomes`` braucht die Rollen und Kanten von
    Vorhaben 14 (``procedures.enabled``) und die Antragsteller von Vorhaben 15
    (``functions.enabled`` mit Urhebern); fehlt eines, steht nur der Beratungsverlauf da.
    """
    if not settings.outcomes.enabled:
        return []
    files = outcome_files(layout)
    rules = OutcomeRules.from_settings(settings.outcomes)

    def council_results() -> str:
        papers = pl.read_parquet(layout.corpus, columns=["id"]).get_column("id").to_list()
        agenda, source = read_agenda(layout, papers)
        frame = progress(agenda, dict(settings.bodies.organizations), rules.results)
        write_parquet(frame, files.progress, schema_version=OUTCOMES_SCHEMA_VERSION)
        items = frame.filter(pl.col("top").is_not_null())
        return (
            f"{frame.height} Zeilen aus dem {source} für {frame.get_column('id').n_unique()} "
            f"Dokumente, {items.height} Tagesordnungspunkte, davon "
            f"{items.get_column('result').is_not_null().sum()} mit Eintrag"
        )

    steps = [
        Step(
            "council_results",
            (layout.corpus,),
            (files.progress,),
            council_results,
            OUTCOMES_SCHEMA_VERSION,
            optional=(*network_inputs(layout), files.agenda, *progress_inputs(layout)),
        )
    ]
    if not outcomes_built(settings):
        return steps
    edges = procedure_files(layout).edges
    cosponsors = functions_files(layout).cosponsors

    def outcomes() -> str:
        corpus = pl.read_parquet(
            layout.corpus, columns=["id", "date", "paper_type", "name", "text"]
        )
        verlauf = pl.read_parquet(files.progress)
        base = classify_outcomes(corpus.select("id", "date"), verlauf, rules.results)
        reference_rules = ReferenceRules.from_settings(settings.procedures)
        roles = pl.DataFrame(
            {
                "id": corpus.get_column("id"),
                "rolle": [
                    role_of(paper_type, name, reference_rules)
                    for paper_type, name in corpus.select("paper_type", "name").iter_rows()
                ],
            },
            schema={"id": pl.String, "rolle": pl.String},
        )
        accepted = (
            base.join(roles, on="id")
            .filter((pl.col("rolle") == MOTION) & pl.col("klasse").is_in(list(ANGENOMMEN)))
            .get_column("id")
        )
        review = pl.DataFrame(
            [
                (doc_id, review_only(name, text, rules.review)[0])
                for doc_id, name, text in corpus.filter(pl.col("id").is_in(accepted.implode()))
                .select("id", "name", "text")
                .iter_rows()
            ],
            schema={"id": pl.String, "pruefauftrag": pl.Boolean},
            orient="row",
        )
        followups = first_followups(
            pl.read_parquet(edges, columns=["von", "nach", "stark"]),
            roles,
            corpus.select("id", "date"),
            rules.followup_roles,
        )
        frame = complete_outcomes(base, roles, review, followups, rules)
        write_parquet(frame, files.outcomes, schema_version=OUTCOMES_SCHEMA_VERSION)
        success = motion_success(
            frame,
            pl.read_parquet(cosponsors, columns=["id", "fraktionen"]),
            pl.read_parquet(layout.papers_bodies, columns=["id", "gremium", "gremium_art"]),
            period_key(settings.period.start, settings.period.end),
        )
        write_parquet(success, files.success, schema_version=OUTCOMES_SCHEMA_VERSION)
        motions = frame.filter(pl.col("dokument_rolle") == MOTION)
        entered = motions.filter(pl.col("klasse") != "ohne_ergebnis").height
        practice = motions.filter(~pl.col("eintrag_tragfaehig").fill_null(True)).height
        figures = outcome_figures(frame)
        share = f"{100 * entered / motions.height:.1f} %" if motions.height else "–"
        return (
            f"{frame.height} Dokumente ({', '.join(f'{n} {k}' for k, n in figures.items() if n)}); "
            f"Anträge {motions.height}, mit Ergebnis {entered} ({share}), in Praxiszellen "
            f"{practice}; Antragserfolg {success.height} Zeilen"
        )

    steps.append(
        Step(
            "outcomes",
            (files.progress, layout.corpus, edges, cosponsors, layout.papers_bodies),
            (files.outcomes, files.success),
            outcomes,
            OUTCOMES_SCHEMA_VERSION,
        )
    )
    return steps


# --- Stufe 3 (Messdokument § 7, § 10): Tabellen, Abschnitte auf vorgaenge.html, Dialog -------------
_ID = ("OParl-URL der Drucksache (Korpus-ID)", "")
_BODY = (
    "Kürzel des Gremiums der Sitzung aus bodies.organizations, mehrere mit „+“, sonst der "
    "Schlüssel der Organisation; leer ohne Organisation"
)
_MOTIONS = "Anträge"


def without_review(frame: pl.DataFrame, settings: Settings) -> pl.DataFrame:
    """Die veröffentlichte Beschlusslage: ohne ``pruefauftrag_beantragt`` (Rückfall 1, § 5).

    Die Regel des beantragten Prüfauftrags verfehlte die vorab festgelegte Präzision (57 von 65,
    Recall 0,73); die Spalte bleibt im Datensatz als Beschreibung, wird aber nicht veröffentlicht,
    wie die verworfenen Spannen von 12 (Punkt 89).
    """
    return frame.drop("pruefauftrag_beantragt")


TABLES = (
    PublishedTable(
        "beschlusslage",
        lambda layout: outcome_files(layout).outcomes,
        "Beschlusslage je Ratsdokument: Klasse aus der letzten Entscheidung in der Sache, "
        "Gremium und Tag, Beratungen, Folgevorlage (nur Parquet); geprüft nur für Anträge",
        {
            "id": _ID,
            "dokument_rolle": (
                "Rolle des Dokuments nach Vorhaben 14: antrag, vorlage, anfrage, information "
                "und weitere; nicht die Rolle einer Beratung (beratungsverlauf.beratung_rolle) "
                "und nicht die Stellung im Vorgang (dokumente_vorgang.rolle)",
                "",
            ),
            "klasse": (
                "beschlossen, geaendert, abgelehnt, zurueckgezogen, erledigt (ohne Abstimmung), "
                "vertagt (zuletzt vertagt), offen (verwiesen, danach nichts im Datensatz) oder "
                "ohne_ergebnis, aus der letzten Entscheidung in der Sache, sonst dem letzten "
                "Stand; an Anträgen geprüft, für die übrigen Rollen nur beschreibend",
                "",
            ),
            "grob": (
                "angenommen (beschlossen, geaendert), abgelehnt, ohne_sachbeschluss "
                "(zurueckgezogen, erledigt), offen (vertagt, offen) oder ohne_ergebnis",
                "",
            ),
            "result": (
                "der maßgebliche Eintrag der Sitzungsleitung, wörtlich; leer bei ohne_ergebnis",
                "",
            ),
            "entscheidung_top": (
                "OParl-AgendaItem des maßgeblichen Tagesordnungspunkts; leer bei ohne_ergebnis",
                "",
            ),
            "entscheidung_gremium": (_BODY.replace("der Sitzung", "dieses Punkts"), ""),
            "entscheidung_datum": ("Tag der Sitzung dieses Punkts", ""),
            "tage": (
                "vom Datum des Dokuments bis zu dieser Sitzung; leer ohne Sitzung oder wenn sie "
                "vor dem Dokument liegt",
                "Tage",
            ),
            "beratungen": (
                "Beratungen des Dokuments in diesem Datensatz, mit und ohne Tagesordnungspunkt",
                "Beratungen",
            ),
            "folgevorlage": (
                "nur Anträge: die erste Drucksache der Verwaltung, die den Antrag über eine starke "
                "Verbindung von Vorhaben 14 nennt; eine Untergrenze, denn die Verbindungen kennen "
                "nur Drucksachen dieses Datensatzes (eine Folgevorlage der nächsten Periode fehlt)",
                "",
            ),
            "eintrag_tragfaehig": (
                "nur Anträge mit Ergebnis: falsch in einem Gremium-Jahr, in dem mindestens "
                "outcomes.practice_share der Anträge mit Ergebnis und mindestens "
                "outcomes.practice_min nur „erledigt“ sind; dort ist der Eintrag eine Praxis der "
                "Sitzungsleitung, kein Ergebnis",
                "",
            ),
        },
        optional=True,  # ohne den Schritt outcomes (etwa ohne Urheber) fehlt die Datei, nicht die Seite
        enabled=outcomes_built,
        csv=None,  # docs/todo.md, Punkt 35: je Dokument nur Parquet
        view=without_review,
        check=TableCheck(table_check_files, table_sentence),
    ),
    PublishedTable(
        "beratungsverlauf",
        lambda layout: outcome_files(layout).progress,
        "Beratungsverlauf je Ratsdokument: jede Beratung mit ihren Tagesordnungspunkten, Gremium, "
        "Sitzung und dem Eintrag der Sitzungsleitung, wörtlich (nur Parquet)",
        {
            "id": _ID,
            "beratung": ("OParl-Consultation: eine Beratung des Dokuments", ""),
            "top": (
                "OParl-AgendaItem, der Tagesordnungspunkt; leer, wenn die Beratung keinen Punkt in "
                "den Sitzungen dieser Periode hat",
                "",
            ),
            "gremium": (_BODY, ""),
            "beratung_rolle": (
                "Rolle der Beratung im Ratsinformationssystem (OParl role: Entscheidung, "
                "Kenntnisnahme, Vorberatung, Anhörung oder „-“); nicht die Rolle des Dokuments "
                "(beschlusslage.dokument_rolle) und nicht die Stellung im Vorgang "
                "(dokumente_vorgang.rolle)",
                "",
            ),
            "sitzung": ("Beginn der Sitzung, Ortszeit des Servers ohne Zone", ""),
            "nummer": ("Nummer des Punkts auf der Tagesordnung", ""),
            "ordnung": ("Folge des Punkts in der Sitzung (OParl order)", ""),
            "result": ("Eintrag der Sitzungsleitung (OParl result), wörtlich; leer: keiner", ""),
            "stufe": (
                "sache (beschlossen, geändert, abgelehnt, zurückgezogen, auch als Empfehlung) "
                "oder stand (Kenntnisnahme, Vertagung, Verweisung), nach outcomes.results; leer "
                "ohne Eintrag",
                "",
            ),
        },
        enabled=progress_built,
        csv=None,  # docs/todo.md, Punkt 35: je Punkt nur Parquet
    ),
    PublishedTable(
        "antragserfolg",
        lambda layout: outcome_files(layout).success,
        "Antragserfolg je Fraktion und Gremienart: Anträge mit Sachentscheidung, angenommen, "
        "erwartet nach der Praxis der Gremien (explorativ; die Klassen wie in beschlusslage)",
        {
            "periode": ("die Periode der Dokumente, etwa 2020-2025; offen: 2025-", ""),
            "gremium_art": (
                "rat, ausschuss, bezirksvertretung, beirat oder unbekannt: die Art des Gremiums "
                "der Drucksache",
                "",
            ),
            "fraktion": ("Fraktion aus den Antragstellern von Vorhaben 15", ""),
            "n": (
                "Anträge mit Sachentscheidung (angenommen oder abgelehnt); ein gemeinsamer Antrag "
                "zählt für jede beteiligte Fraktion, einer in einer Praxiszelle für keine",
                _MOTIONS,
            ),
            "angenommen": ("davon angenommen, auch mit Änderungen", _MOTIONS),
            "erwartet": (
                "Summe der Annahmequoten der Gremien der Drucksachen über diese Anträge "
                "(indirekte Standardisierung, je Gremienart Summe gleich angenommen)",
                _MOTIONS,
            ),
            "beob_erw": (
                "angenommen geteilt durch erwartet; leer, wo erwartet 0 ist",
                "Verhältnis",
            ),
        },
        optional=True,  # ohne den Schritt outcomes (etwa ohne Urheber) fehlt die Datei, nicht die Seite
        enabled=outcomes_built,
    ),
)

SECTIONS = (
    PageSection(
        HOST,
        SECTION_OUTCOMES,
        30,
        inputs=outcomes_section_inputs,
        data=outcomes_section_data,
        links=section_links,
    ),
    PageSection(
        HOST,
        SECTION_SUCCESS,
        31,
        inputs=success_section_inputs,
        data=success_section_data,
        enabled=outcomes_built,
    ),
    PageSection(
        HOST,
        SECTION_SESSION,
        32,
        inputs=session_section_inputs,
        data=session_section_data,
        enabled=outcomes_built,
    ),
)

DIALOG = DialogHook(
    DIALOG_NAME,
    DIALOG_TITLE,
    "Beschlusslage je Antrag des Dialogs: Klasse, Gremium und Tag der Entscheidung; der "
    "Dokumentdialog lädt die Datei beim ersten Öffnen nach",
    inputs=dialog_inputs,
    rows=dialog_rows,
    enabled=outcomes_built,
)

CONTRIBUTION = Contribution(
    "26-beschluesse",
    steps=outcome_steps,
    tables=TABLES,
    sections=SECTIONS,
    dialogs=(DIALOG,),
)
