"""Beitrag von Vorhaben 15: Funktion je Ratsdokument und Antragsteller je Fraktionsdokument.

Zwei Schritte, beide offline, hinter ``bodies`` und ``parties`` (sie lesen deren Ausgaben):

* ``functions`` schreibt ``processed/dokumente_funktion.parquet`` (``analysis.functions``);
* ``cosponsors`` schreibt ``processed/dokumente_antragsteller.parquet`` (``analysis.cosponsors``).

Beide fehlen ohne ``functions.enabled`` und ohne Urheber (Option 04 braucht Fraktionsnamen im
Profil). Die Regeln stehen in ``analysis``; hier steht nur, welche Dateien gelesen und geschrieben
werden. Die Pfade gehören diesem Modul (Synergien 2026-11, § 2.1): wer die Tabellen liest — 14 die
Fraktionen, 24 und 28 das Lager —, nimmt sie aus ``functions_files``.

Stufe 3 (Messdokument § 7): beide Tabellen stehen im Register der Downloads (Parquet und CSV, mit
Spaltendoku in ``schema.json``), und die Unterseite ``akteure.html`` (``report.actors``) zeigt sie,
unter demselben Schalter wie die Schritte. 24, 27 und 28 hängen dort später Abschnitte an
(``PageSection`` mit ``page="akteure"``, Vorarbeit V1).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import polars as pl

from georep.analysis.cosponsors import (
    COSPONSORS_SCHEMA_VERSION,
    CosponsorRules,
    classify_cosponsors,
    cosponsor_figures,
)
from georep.analysis.functions import (
    FUNCTIONS_SCHEMA_VERSION,
    FunctionRules,
    classify_functions,
    function_figures,
)
from georep.enrich import Contribution
from georep.http import Transport
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import Step
from georep.report.actors import PAGE_NAME, actors_data, actors_inputs, actors_links
from georep.report.pages import Page
from georep.report.tables import PublishedTable
from georep.settings import Settings


class FunctionFiles(NamedTuple):
    functions: Path
    cosponsors: Path


def functions_files(layout: Layout) -> FunctionFiles:
    """Die beiden Tabellen je Korpus-ID unter ``processed/``."""
    return FunctionFiles(
        layout.processed / "dokumente_funktion.parquet",
        layout.processed / "dokumente_antragsteller.parquet",
    )


def functions_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Die Schritte ``functions`` und ``cosponsors``, wenn das Profil sie einschaltet.

    Beide sind offline; ``http`` (Fundament F7) bleibt ungenutzt.
    """
    if not functions_enabled(settings):
        return []
    files = functions_files(layout)

    def functions() -> str:
        rules = FunctionRules.from_settings(settings.functions)
        corpus = pl.read_parquet(layout.corpus, columns=["id", "paper_type", "name", "text"])
        originators = pl.read_parquet(layout.document_originators, columns=["id", "urheber_art"])
        frame = classify_functions(corpus, originators, rules)
        write_parquet(frame, files.functions, schema_version=FUNCTIONS_SCHEMA_VERSION)
        figures = function_figures(frame)
        shares = ", ".join(
            f"{figures[name]} {name}" for name in figures if name != "rest" and figures[name]
        )
        return (
            f"{frame.height} Dokumente: {shares}; Funktion nicht erkannt {figures['rest']} "
            f"(Variante {rules.variant})"
        )

    def cosponsors() -> str:
        rules = CosponsorRules.from_settings(settings)
        corpus = pl.read_parquet(
            layout.corpus, columns=["id", "date", "paper_type", "name", "text"]
        )
        originators = pl.read_parquet(
            layout.document_originators, columns=["id", "urheber_art", "parteien"]
        )
        bodies = pl.read_parquet(layout.papers_bodies, columns=["id", "gremium_art"])
        frame = classify_cosponsors(corpus, originators, bodies, rules)
        write_parquet(frame, files.cosponsors, schema_version=COSPONSORS_SCHEMA_VERSION)
        figures = cosponsor_figures(frame)
        city = sum(
            figures[c]
            for c in (
                "allein_mehrheit",
                "allein_opposition",
                "gemeinsam_mehrheit",
                "gemeinsam_opposition",
                "ueber_grenze",
            )
        )
        return (
            f"{figures['mit_antragsteller']} Dokumente mit Antragsteller, "
            f"{figures['gemeinsam']} gemeinsam; mit Lager {city}, "
            f"davon über die Grenze {figures['ueber_grenze']}"
        )

    return [
        Step(
            "functions",
            (layout.corpus, layout.document_originators),
            (files.functions,),
            functions,
            FUNCTIONS_SCHEMA_VERSION,
        ),
        Step(
            "cosponsors",
            (layout.corpus, layout.document_originators, layout.papers_bodies),
            (files.cosponsors,),
            cosponsors,
            COSPONSORS_SCHEMA_VERSION,
        ),
    ]


def functions_enabled(settings: Settings) -> bool:
    """Der Schalter der Schritte, der Tabellen und der Seite: ``functions.enabled`` und Urheber."""
    return settings.functions.enabled and bool(settings.originators.parties)


_ID = ("OParl-URL des Dokuments", "")
TABLES = (
    PublishedTable(
        "dokumente_funktion",
        lambda layout: functions_files(layout).functions,
        "Funktion je Ratsdokument: Kontrolle, Information, Initiative, Erklärung oder Appell, Vollzug, "
        "mit Instrument und Quelle",
        {
            "id": _ID,
            "funktion": (
                "kontrolle, information, initiative, erklaerung (Erklärung oder Appell), vollzug oder rest "
                "(auf der Seite "
                "„Funktion nicht erkannt“); genau eine je Dokument",
                "",
            ),
            "instrument": (
                "Unterart der Funktion, etwa anfrage, berichtsantrag, informationsvorlage, antrag, "
                "resolution, beschlussvorlage; bei rest der Grund (sammelart_ohne_merkmal, "
                "art_unbekannt)",
                "",
            ),
            "quelle": (
                "woher die Funktion kommt: art (Dokumentart), titel oder text; leer genau bei rest",
                "",
            ),
            "variante": (
                "Variante des Regelwerks, A oder B; B liest den Beschlusstext eines Antrags "
                "(Erklärung als erklaerung, Berichtswunsch als Kontrolle)",
                "",
            ),
        },
        optional=True,
        enabled=functions_enabled,
    ),
    PublishedTable(
        "dokumente_antragsteller",
        lambda layout: functions_files(layout).cosponsors,
        "Antragsteller je Ratsdokument: Parteien, Fraktionen, gemeinsam oder allein, Lager zur "
        "Ratsmehrheit",
        {
            "id": _ID,
            "antragsteller": (
                "Parteischlüssel aus Dokumentart, Autorenteil des Titels und Briefkopf, in der "
                "Folge des Profils; leer außer bei der Urheberklasse Fraktion",
                "Liste",
            ),
            "fraktionen": (
                "dieselben als Fraktionen am Datum des Dokuments (zwei Parteien einer Fraktion "
                "sind ein Schlüssel wie SPD+VOLT)",
                "Liste",
            ),
            "quelle": (
                "woher die Antragsteller kommen: art, titel, briefkopf, mehrere mit +; parteien, "
                "wenn keiner der drei eine Partei nennt (dann wie in dokumente_urheber); leer ohne "
                "Antragsteller",
                "",
            ),
            "gemeinsam": ("mindestens zwei Fraktionen", ""),
            "lager": (
                "gegenüber der Ratsmehrheit am Datum: allein_mehrheit, allein_opposition, "
                "gemeinsam_mehrheit, gemeinsam_opposition, ueber_grenze, ohne_partei (keine "
                "Fraktion genannt) oder ohne_lager (Gremium außerhalb der Gremien, in denen die "
                "Ratsmehrheit gilt, oder keine Mehrheit im Profil)",
                "",
            ),
        },
        joins={"antragsteller": "; ", "fraktionen": "; "},
        optional=True,
        enabled=functions_enabled,
    ),
)

PAGE = Page(
    PAGE_NAME,
    "Akteure: Funktionen und gemeinsame Anträge",
    "Welche Funktion ein Ratsdokument hat, welche Instrumente die Fraktionen nutzen und wer mit "
    "wem Anträge stellt.",
    inputs=actors_inputs,
    data=actors_data,
    enabled=functions_enabled,
    links=actors_links,
)

CONTRIBUTION = Contribution("15-funktion", steps=functions_steps, tables=TABLES, pages=(PAGE,))
