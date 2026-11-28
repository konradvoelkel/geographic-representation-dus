"""Beitrag von Vorhaben 28: Abstimmungen je Tagesordnungspunkt (nur Ebene A) und H28.2.

Ein Offline-Schritt hinter 26, nur mit ``votes.enabled`` und dem Beratungsverlauf von 26
(``docs/plans/28-abstimmungen.md``, § 6, § 7 und § 10):

* ``votes`` liest den Beratungsverlauf ``processed/beratungsverlauf.parquet``, den
  ``council_results`` aus der Tabelle „Paper × Tagesordnungspunkt" schreibt (auf Pages aus dem
  Paket ``snapshots/duesseldorf-beschluesse/``; § 10, Punkt 1: kein eigenes Paket, kein Netz), und
  schreibt je Punkt mit Beratung Ergebnis und Mehrheitsform nach der Wortregel
  (``processed/abstimmungen.parquet``), die Zählung je Gremienart
  (``processed/abstimmungen_gremien.parquet``) und die vorab festgelegten Prüfungen
  (``processed/abstimmungen_hypothesen.parquet``). Für H28.2 liest er dazu den Korpus und die
  Urheber aus Option 04, aber nur, wo ein Zeitraum aus ``votes.windows`` in der Periode liegt.

Dazu drei veröffentlichte Tabellen und ein Abschnitt auf ``akteure.html`` von Vorhaben 15
(``Contribution.sections``, Vorarbeit V1); die Seite steht in ``report.votes``. Die Regeln stehen
in ``analysis.votes``; hier steht nur, was gelesen und geschrieben wird. Die Pfade gehören diesem
Modul (Synergien 2026-11, § 2.1).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import polars as pl

from georep.analysis.outcomes import period_key
from georep.analysis.votes import (
    H2,
    MAIN,
    R2,
    VOTES_SCHEMA_VERSION,
    HypothesisInputs,
    VoteRules,
    Window,
    body_summary,
    hypothesis_rows,
    outcome_mismatches,
    votes_table,
)
from georep.enrich import Contribution
from georep.enrich.outcomes import outcome_files
from georep.http import Transport
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import Step
from georep.prep.bodies import BodyRules
from georep.report.pages import PageSection
from georep.report.tables import PublishedTable
from georep.report.votes import (
    HOST,
    SECTION,
    votes_section_data,
    votes_section_inputs,
    votes_section_links,
)
from georep.settings import Settings


class VoteFiles(NamedTuple):
    votes: Path
    bodies: Path
    hypotheses: Path


def vote_files(layout: Layout) -> VoteFiles:
    """Die Pfade des Vorhabens; sie gehören dem Modul, nicht ``Layout`` (Synergie, § 2.1)."""
    return VoteFiles(
        votes=layout.processed / "abstimmungen.parquet",
        bodies=layout.processed / "abstimmungen_gremien.parquet",
        hypotheses=layout.processed / "abstimmungen_hypothesen.parquet",
    )


def votes_enabled(settings: Settings) -> bool:
    """Der Schritt braucht den Schalter und den Beratungsverlauf von 26 (``outcomes.enabled``)."""
    return settings.votes.enabled and settings.outcomes.enabled


def windows_of(settings: Settings) -> list[Window]:
    """Die vorab festgelegten Zeiträume, die in der Periode dieses Profils liegen, mit Mehrheit.

    Die Mehrheit ist die aus ``[majorities]`` am ersten Tag des Zeitraums; ohne Zeile dort ist sie
    unbekannt, und H28.2 ist für diesen Zeitraum nicht entscheidbar. Ohne Urheber im Profil
    (Option 04) gibt es keine Anträge der Opposition, also keinen Zeitraum.
    """
    if not (settings.originators.parties or settings.originators.groups):
        return []
    found: list[Window] = []
    for window in settings.votes.windows:
        if not window.within(settings.period):
            continue
        term = settings.majorities.on(window.start)
        majority = frozenset(term.parties) if term is not None else None
        found.append(Window(window.calculation, window.start, window.end, majority))
    return found


def votes_tested(settings: Settings) -> bool:
    """Ob das Profil eine vorab festgelegte Prüfung rechnet: der Schritt und ein Zeitraum darin.

    Ohne Zeitraum (2014 bis 2020) schreibt der Schritt die Hypothesentabelle leer, und sie ist
    kein Download; der Abschnitt sagt, wo die Prüfungen rechnen.
    """
    return votes_enabled(settings) and bool(windows_of(settings))


def party_labels(settings: Settings) -> dict[str, str]:
    """Parteischlüssel → Kurzname, in der Folge von ``[originators]`` (Parteien, dann Gruppen)."""
    parties = (*settings.originators.parties, *settings.originators.groups)
    return {party.key: party.short or party.label for party in parties}


def vote_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Der Schritt ``votes``; offline, ``http`` (Fundament F7) bleibt ungenutzt."""
    if not votes_enabled(settings):
        return []
    files = vote_files(layout)
    progress = outcome_files(layout).progress
    windows = windows_of(settings)
    tested = (layout.corpus, layout.document_originators) if windows else ()

    def run() -> str:
        rules = VoteRules.from_settings(settings.votes)
        votes = votes_table(
            pl.read_parquet(progress), BodyRules.from_settings(settings.bodies), rules
        )
        write_parquet(votes, files.votes, schema_version=VOTES_SCHEMA_VERSION)
        bodies = body_summary(votes, period_key(settings.period.start, settings.period.end))
        write_parquet(bodies, files.bodies, schema_version=VOTES_SCHEMA_VERSION)
        inputs = HypothesisInputs(
            votes,
            pl.read_parquet(layout.corpus, columns=["id", "paper_type"]) if windows else _NO_CORPUS,
            pl.read_parquet(layout.document_originators, columns=["id", "urheber_art", "parteien"])
            if windows
            else _NO_ORIGINATORS,
        )
        tests = hypothesis_rows(inputs, windows, settings.votes, party_labels(settings))
        write_parquet(tests, files.hypotheses, schema_version=VOTES_SCHEMA_VERSION)
        return _summary(votes, bodies, tests, settings)

    return [
        Step(
            "votes",
            (progress, *tested),
            (files.votes, files.bodies, files.hypotheses),
            run,
            VOTES_SCHEMA_VERSION,
        )
    ]


_NO_CORPUS = pl.DataFrame(schema={"id": pl.String, "paper_type": pl.String})
_NO_ORIGINATORS = pl.DataFrame(
    schema={"id": pl.String, "urheber_art": pl.String, "parteien": pl.List(pl.String)}
)


def _summary(
    votes: pl.DataFrame, bodies: pl.DataFrame, tests: pl.DataFrame, settings: Settings
) -> str:
    """Die Zeile des Schritts: Punkte, Beschlüsse und Formen, Abweichungen von 26, H28.2."""
    total = bodies.select(pl.col(c).sum() for c in bodies.columns[2:]).row(0, named=True)
    mismatches = outcome_mismatches(votes, settings.outcomes.results).height
    line = (
        f"{votes.height} Punkte, {total['beschluesse']} Beschlüsse ({total['einstimmig']} "
        f"einstimmig, {total['mehrheitlich']} mehrheitlich, {total['ohne_angabe']} ohne Angabe, "
        f"{total['geaendert']} geändert); Wortregel und 26 verschieden an {mismatches} Punkten"
    )
    h2 = tests.filter((pl.col("hypothese") == H2) & pl.col("rechnung").is_in([MAIN, R2]))
    for row in h2.iter_rows(named=True):
        line += f"; {H2} ({row['rechnung']}) {row['angenommen']} von {row['n']} angenommen"
        if row["p_holm"] is not None:
            line += f", p_holm {row['p_holm']:.2g}"
        if row["entscheidung"] is not None:
            line += f", {row['entscheidung']}"
        if row["grund"] is not None:
            line += f" ({row['grund']})"
    return line


# --- Stufe 3 (§ 7 mit § 10, Punkt 5): Tabellen und der Abschnitt auf akteure.html ---------------
_BODY_COUNT = "Tagesordnungspunkte"
TABLES = (
    PublishedTable(
        "abstimmungen",
        lambda layout: vote_files(layout).votes,
        "Ergebnis und Mehrheitsform je Tagesordnungspunkt mit Beratung, aus dem Eintrag der "
        "Sitzungsleitung nach der vorab festgelegten Wortregel (nur Parquet)",
        {
            "top": ("OParl-AgendaItem, der Schlüssel", ""),
            "paper": ("das Dokument (Korpus-ID, OParl-Paper)", ""),
            "sitzung": ("Beginn der Sitzung, Ortszeit des Servers ohne Zone", ""),
            "datum": ("Tag der Sitzung", ""),
            "gremium": (
                "Kürzel des Gremiums der Sitzung aus bodies.organizations, mehrere mit „+“, "
                "sonst der Schlüssel der Organisation",
                "",
            ),
            "gremium_art": (
                "rat, ausschuss, bezirksvertretung, beirat oder unbekannt, aus der ersten "
                "Organisation der Sitzung",
                "",
            ),
            "nummer": ("Nummer des Punkts auf der Tagesordnung", ""),
            "result": ("Eintrag der Sitzungsleitung (OParl result), wörtlich; leer: keiner", ""),
            "ergebnis": (
                "angenommen, abgelehnt, vertagt, verwiesen, zurueckgezogen, kenntnis, erledigt "
                "oder sonstiges, nach der ersten Regel aus votes.results",
                "",
            ),
            "geaendert": ("der Eintrag nennt eine Änderung („abweichend beschlossen“)", ""),
            "form": (
                "einstimmig (ohne Gegenstimme), mehrheitlich oder ohne_angabe; nur bei "
                "angenommen oder abgelehnt",
                "",
            ),
            "form_quelle": ("woher die Form kommt: result; leer ohne Form", ""),
        },
        optional=True,  # ohne den Schritt (etwa ohne Urheber) fehlt die Datei, nicht die Seite
        enabled=votes_enabled,
        csv=None,  # docs/todo.md, Punkt 35: je Punkt nur Parquet, eine CSV wäre groß und nicht gebraucht
    ),
    PublishedTable(
        "abstimmungen_gremien",
        lambda layout: vote_files(layout).bodies,
        "Beschlüsse je Gremienart: angenommen, abgelehnt, einstimmig, mehrheitlich, geändert "
        "(explorativ)",
        {
            "periode": ("die Periode der Dokumente, etwa 2020-2025; offen: 2025-", ""),
            "gremium_art": ("rat, ausschuss, bezirksvertretung, beirat oder unbekannt", ""),
            "punkte": (
                "Tagesordnungspunkte mit Beratung zu den Dokumenten der Periode",
                _BODY_COUNT,
            ),
            "mit_eintrag": ("davon mit Eintrag der Sitzungsleitung", _BODY_COUNT),
            "beschluesse": ("davon angenommen oder abgelehnt", _BODY_COUNT),
            "angenommen": ("Beschlüsse mit Ergebnis angenommen, auch geändert", _BODY_COUNT),
            "abgelehnt": ("Beschlüsse mit Ergebnis abgelehnt", _BODY_COUNT),
            "einstimmig": ("Beschlüsse ohne Gegenstimme", _BODY_COUNT),
            "mehrheitlich": ("Beschlüsse mit mindestens einer Gegenstimme", _BODY_COUNT),
            "ohne_angabe": ("Beschlüsse, deren Eintrag keine Form nennt", _BODY_COUNT),
            "geaendert": ("angenommen mit Änderung („abweichend beschlossen“)", _BODY_COUNT),
        },
        optional=True,  # ohne den Schritt (etwa ohne Urheber) fehlt die Datei, nicht die Seite
        enabled=votes_enabled,
    ),
    PublishedTable(
        "abstimmungen_hypothesen",
        lambda layout: vote_files(layout).hypotheses,
        "Die vorab festgelegten Prüfungen H28.1 bis H28.3 und die Nebenrechnungen von H28.2, je "
        "Zeile eine Rechnung; nur in Perioden, in denen ein Zeitraum der Prüfungen liegt",
        {
            "hypothese": ("Kennung der vorab festgelegten Hypothese, H28.1 bis H28.3", ""),
            "p": (
                "p-Wert des einseitigen exakten Binomialtests, unkorrigiert; leer, wo nicht "
                "gerechnet",
                "Anteil 0 bis 1",
            ),
            "p_holm": ("nach Holm über H28.1 bis H28.3, nur beim Haupttest", "Anteil 0 bis 1"),
            "ergebnis": ("bestätigt oder nicht bestätigt nach Holm, nur beim Haupttest", ""),
            "n": ("Anträge der Rechnung; leer, wo nicht gerechnet", "Anträge"),
            "festgelegt": (
                "Commit, in dem die Hypothese vor der ersten Zählung festgelegt wurde",
                "",
            ),
            "rechnung": (
                "haupttest, R1 (Ausschüsse), R2 (ab der neuen Mehrheit), R3 (auch nicht "
                "entschiedene Anträge) oder R4 (je Fraktion)",
                "",
            ),
            "partei": ("nur R4: Parteischlüssel der Fraktion aus originators", ""),
            "entscheidung": (
                "bestätigt, widerlegt oder nicht entscheidbar, nur beim Haupttest",
                "",
            ),
            "grund": (
                "warum nicht entscheidbar oder nicht gerechnet: ebene_b_verworfen, "
                "ebene_a_verfehlt, zu_wenige, keine_mehrheit, weder_noch",
                "",
            ),
            "angenommen": ("davon angenommen (auch geändert)", "Anträge"),
            "anteil": ("angenommen durch n", "Anteil 0 bis 1"),
            "schwelle": ("die Schwelle des Tests, H0: Anteil mindestens so groß", "Anteil 0 bis 1"),
            "ci_unten": ("untere einseitige 95-%-Grenze nach Clopper-Pearson", "Anteil 0 bis 1"),
            "ci_oben": ("obere einseitige 95-%-Grenze nach Clopper-Pearson", "Anteil 0 bis 1"),
            "von": ("erster Tag des Zeitraums der Sitzungen", ""),
            "bis": ("letzter Tag des Zeitraums; leer: offen", ""),
        },
        optional=True,
        enabled=votes_tested,
    ),
)

SECTIONS = (
    PageSection(
        HOST,
        SECTION,
        10,
        inputs=votes_section_inputs,
        data=votes_section_data,
        links=votes_section_links,
    ),
)

CONTRIBUTION = Contribution("28-abstimmungen", steps=vote_steps, tables=TABLES, sections=SECTIONS)
