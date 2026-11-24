"""Beschlusslage je Ratsdokument und Antragserfolg je Fraktion (Vorhaben 26).

Was wurde aus einem Antrag? Das Ratsinformationssystem sagt es an jedem Tagesordnungspunkt, der
ihn behandelt: die Sitzungsleitung trägt in OParl ``result`` einen Wert aus einem festen Wortschatz
ein („einstimmig beschlossen", „vertagt", „zurückgezogen" …). Dieses Modul bildet die Folge dieser
Einträge auf eine Klasse ab, nach der Regel, die vor der Stichprobe festgelegt wurde
(Messdokument ``docs/plans/26-beschluesse.md``, § 3.1, Commit ``c94ae31``):

* **Maßgeblich ist die letzte Entscheidung in der Sache** über alle Beratungen des Dokuments, nach
  Beginn der Sitzung, dann Folge auf der Tagesordnung, dann ID des Punkts: beschlossen, geändert
  beschlossen, abgelehnt, zurückgezogen, auch als Empfehlung eines vorberatenden Gremiums. Eine
  spätere Entscheidung in der Sache ersetzt eine frühere; Kenntnisnahme, Vertagung und Verweisung
  ersetzen keine. Nur wenn es keine Entscheidung in der Sache gibt, zählt der letzte andere Stand,
  und ohne jeden Eintrag ist die Klasse ``ohne_ergebnis``.
* Welche Stufe (``sache`` oder ``stand``) und Klasse ein Wert trägt, sagt der Wortschatz im
  Stadtprofil (``[outcomes.results]``); ein Wert, den er nicht kennt, ist ein ``SchemaError`` mit
  seinem Wortlaut, nie still ``ohne_ergebnis``.

Geprüft an 150 Anträgen von zwei KI-Kodierern: ``klasse`` 150 von 150 gleich (§ 4.1). Der
**beantragte Prüfauftrag** (``review_only``) verfehlte dort das Kriterium (Recall 0,73) und steht
nach Rückfall 1 nur als beschreibende Spalte da (§ 5). Die **Praxiszellen** markieren Gremium-Jahre,
in denen „erledigt" eine Praxis der Sitzungsleitung ist und kein Ergebnis (BV9 2014 und 2015: jeder
Antrag „zur Kenntnis genommen"); der **Antragserfolg** je Fraktion ist beobachtet gegen erwartet nach
der Praxis der Gremien (``analysis.practice``), explorativ.

Rein: keine Datei, kein Netz. Die Verbindung Antrag → Beratung → Tagesordnungspunkt → Sitzung
(``agenda_rows``) liest die Modelle aus ``georep.oparl``, wie Fundament F6 sie lädt (Punkt 70).
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

import deal
import polars as pl
from polars._typing import PolarsDataType

from georep.analysis.practice import EXPECTED, OBSERVED, RATIO, N, observed_expected
from georep.contracts import (
    decisions_in_progress,
    entries_decide_exactly,
    has_columns,
    one_row_per_document,
    rows_unique,
    shares_bounded,
    values_known,
)
from georep.errors import SchemaError
from georep.oparl import OparlAgendaItem, OparlConsultation, OparlMeeting
from georep.prep.bodies import organization_key
from georep.settings import OUTCOME_STAGES, OutcomeReview, Outcomes

# Version 1: die drei Ausgaben aus dem Bauplan (Messdokument § 6, § 10): beratungsverlauf,
# beschlusslage, antragserfolg. Erhöhen, wenn sich eine Spalte oder ein Typ ändert.
OUTCOMES_SCHEMA_VERSION = 1
# Version 1 der Tabelle „Paper × Tagesordnungspunkt" im Paket (``georep pack --outcomes``). Eigene
# Konstante wie bei Punkt 58: das Paket ist eine Eingabe, kein Ergebnis eines Schritts.
AGENDA_SCHEMA_VERSION = 1
# Der Name der Tabelle unter ``raw/``, wohin ``bootstrap`` das Paket legt (``enrich.outcomes``).
AGENDA_NAME = "tagesordnungspunkte.parquet"

SACHE, STAND = "sache", "stand"
ANGENOMMEN = ("beschlossen", "geaendert")
NO_RESULT = "ohne_ergebnis"
# Die acht Klassen in der Folge des Messdokuments (§ 3.1), zuletzt das Dokument ohne Eintrag.
CLASSES: tuple[str, ...] = (*OUTCOME_STAGES[SACHE], *OUTCOME_STAGES[STAND], NO_RESULT)
FINAL = ("beschlossen", "geaendert", "abgelehnt", "zurueckgezogen", "erledigt")
# Rückfall 2 und die Seite (§ 5, Punkt 1): beschlossen und geändert zeigt sie als angenommen.
COARSE: dict[str, str] = {
    "beschlossen": "angenommen",
    "geaendert": "angenommen",
    "abgelehnt": "abgelehnt",
    "zurueckgezogen": "ohne_sachbeschluss",
    "erledigt": "ohne_sachbeschluss",
    "vertagt": "offen",
    "offen": "offen",
    NO_RESULT: NO_RESULT,
}
MOTION = "antrag"  # die Rolle eines Antrags in Vorhaben 14 (``procedures``)
DONE = "erledigt"

# Die Tabelle „Paper × Tagesordnungspunkt": je Beratung eines Dokuments jeder Tagesordnungspunkt,
# der sie behandelt, und eine Zeile mit ``top`` null für eine Beratung ohne Punkt im Datensatz. Was
# die Sitzungsleitung eingetragen hat, steht wörtlich da; welches Kürzel eine Organisation hat und
# welche Klasse ein Eintrag trägt, sagt erst das Profil (``progress``).
AGENDA_SCHEMA: dict[str, PolarsDataType] = {
    "id": pl.String,  # das Dokument (OParl Paper)
    "beratung": pl.String,  # OParl Consultation
    "top": pl.String,  # OParl AgendaItem; null = Beratung ohne Tagesordnungspunkt im Datensatz
    "organisationen": pl.List(pl.String),  # der Sitzung, sonst der Beratung (``organization_key``)
    "rolle": pl.String,  # Rolle der Beratung (OParl ``role``), etwa „Entscheidung"
    "sitzung": pl.Datetime("us"),  # Beginn der Sitzung, Ortszeit des Servers ohne Zone
    "nummer": pl.String,  # Nummer des Punkts auf der Tagesordnung, etwa „Ö 5.1"
    "ordnung": pl.Int32,  # Folge des Punkts in der Sitzung (OParl ``order``)
    "result": pl.String,  # der Eintrag der Sitzungsleitung, wörtlich; null = keiner
}
PROGRESS_SCHEMA: dict[str, PolarsDataType] = {
    "id": pl.String,
    "beratung": pl.String,
    "top": pl.String,
    "gremium": pl.String,  # Kürzel aus ``[bodies.organizations]``, mehrere mit „+"; sonst der Schlüssel
    "rolle": pl.String,
    "sitzung": pl.Datetime("us"),
    "nummer": pl.String,
    "ordnung": pl.Int32,
    "result": pl.String,
    "stufe": pl.String,  # sache, stand; null genau ohne Eintrag
}
# Die Folge, in der die Regel liest und in der die Tabellen stehen: Sitzung (ohne Datum zuerst),
# Punkt in der Sitzung, ID des Punkts. Die Beratung trennt nur Zeilen ohne Punkt.
PROGRESS_ORDER = ("id", "sitzung", "ordnung", "top", "beratung")
OUTCOME_SCHEMA: dict[str, PolarsDataType] = {
    "id": pl.String,
    "rolle": pl.String,  # Rolle des Dokuments (Vorhaben 14): antrag, vorlage, anfrage …
    "klasse": pl.String,  # eine aus ``CLASSES``
    "grob": pl.String,  # ``COARSE[klasse]``
    "result": pl.String,  # der maßgebliche Eintrag; null genau bei ohne_ergebnis
    "entscheidung_top": pl.String,
    "entscheidung_gremium": pl.String,
    "entscheidung_datum": pl.Date,
    "tage": pl.Int32,  # vom Datum des Dokuments bis zur Sitzung; null ohne Sitzung oder davor
    "beratungen": pl.Int16,  # Beratungen des Dokuments im Datensatz, mit und ohne Punkt
    "pruefauftrag_beantragt": pl.Boolean,  # nur angenommene Anträge; beschreibend (Rückfall 1)
    "folgevorlage": pl.String,  # erste Vorlage der Verwaltung mit starker Kante (Vorhaben 14)
    "eintrag_tragfaehig": pl.Boolean,  # nur Anträge mit Ergebnis; false in einer Praxiszelle
}
SUCCESS_SCHEMA: dict[str, PolarsDataType] = {
    "periode": pl.String,
    "gremium_art": pl.String,
    "fraktion": pl.String,
    "n": pl.Int32,  # Anträge mit Sachentscheidung (angenommen oder abgelehnt)
    "angenommen": pl.Int32,
    "erwartet": pl.Float64,  # Summe der Annahmequoten der Gremien über diese Anträge
    "beob_erw": pl.Float64,  # null, wo erwartet 0 ist
}
BASE_COLUMNS = (
    "id",
    "klasse",
    "grob",
    "result",
    "entscheidung_top",
    "entscheidung_gremium",
    "entscheidung_datum",
    "tage",
    "beratungen",
)


class UnknownResultError(SchemaError):
    """Ein Eintrag der Sitzungsleitung, den der Wortschatz des Profils nicht kennt."""


# --- Die Verbindung Antrag → Beratung → Tagesordnungspunkt → Sitzung (Fundament F6) -------------


def _agenda_fits(result: pl.DataFrame) -> bool:
    return result.schema == pl.Schema(AGENDA_SCHEMA) and rows_unique(
        result, "id", "beratung", "top"
    )


@deal.post(_agenda_fits, message="Schema der Tabelle Paper × Tagesordnungspunkt, Schlüssel einmal")
def agenda_rows(
    meetings: Mapping[str, OparlMeeting],
    items: Mapping[str, OparlAgendaItem],
    consultations: Iterable[OparlConsultation],
    papers: Collection[str],
) -> pl.DataFrame:
    """Je Beratung eines Dokuments aus ``papers`` die Tagesordnungspunkte, die sie behandeln.

    Ein Punkt gehört zu einer Beratung, wenn er sie nennt (``agendaItem.consultation``), und
    dazu der Punkt, den die Beratung nennt (``consultation.agendaItem``), wenn er in der Liste
    steht: eine vertagte Vorlage steht auf zwei Tagesordnungen, und die Beratung nennt nur den
    späteren Punkt (Punkt 70). Gremium ist die Organisation der Sitzung, sonst die der Beratung.
    Eine Beratung ohne Punkt in der Liste (die Sitzung gehört zu einer anderen Periode oder steht
    noch aus) bekommt eine Zeile mit ``top`` null; so zählt ``beratungen`` jede Beratung.
    Sortiert nach ``PROGRESS_ORDER``.
    """
    wanted = set(papers)
    by_consultation: dict[str, list[OparlAgendaItem]] = defaultdict(list)
    for item in items.values():
        if item.consultation:
            by_consultation[item.consultation].append(item)
    rows: list[tuple[object, ...]] = []
    for consultation in consultations:
        if consultation.paper not in wanted:
            continue
        linked = {item.id: item for item in by_consultation.get(consultation.id, [])}
        named = consultation.agenda_item
        if named and named in items and named not in linked:
            linked[named] = items[named]
        if not linked:
            meeting = meetings.get(consultation.meeting or "")
            rows.append(_row(consultation, None, meeting))
        for item in linked.values():
            rows.append(_row(consultation, item, meetings.get(item.meeting or "")))
    frame = pl.DataFrame(rows, schema=AGENDA_SCHEMA, orient="row")
    return frame.sort(PROGRESS_ORDER, nulls_last=False)


def _row(
    consultation: OparlConsultation, item: OparlAgendaItem | None, meeting: OparlMeeting | None
) -> tuple[object, ...]:
    organizations = (
        meeting.organization if meeting and meeting.organization else consultation.organization
    )
    start = meeting.start if meeting else None
    return (
        consultation.paper,
        consultation.id,
        item.id if item else None,
        [organization_key(url) for url in organizations],
        consultation.role,
        start.replace(tzinfo=None) if start else None,
        item.number if item else None,
        item.order if item else None,
        item.result if item else None,
    )


def check_agenda(frame: pl.DataFrame, source: str) -> pl.DataFrame:
    """Eine Tabelle „Paper × Tagesordnungspunkt" aus einem Paket: Schema und Schlüssel, sonst Abbruch."""
    if frame.schema != pl.Schema(AGENDA_SCHEMA):
        raise SchemaError(f"{source}: Schema {dict(frame.schema)} statt {AGENDA_SCHEMA}")
    if not rows_unique(frame, "id", "beratung", "top"):
        raise SchemaError(f"{source}: eine Zeile (id, beratung, top) steht mehrfach")
    return frame


# --- Beratungsverlauf: Kürzel und Stufe aus dem Profil ---------------------------------------------


def _progress_fits(result: pl.DataFrame) -> bool:
    stage_known = result.get_column("stufe").is_null() == result.get_column("result").is_null()
    return (
        result.schema == pl.Schema(PROGRESS_SCHEMA)
        and rows_unique(result, "id", "beratung", "top")
        and bool(stage_known.all())
        and values_known(result, "stufe", (SACHE, STAND))
    )


@deal.pre(lambda agenda, organizations, results: agenda.schema == pl.Schema(AGENDA_SCHEMA))
@deal.post(_progress_fits, message="Schema des Beratungsverlaufs, Stufe genau bei einem Eintrag")
def progress(
    agenda: pl.DataFrame,
    organizations: Mapping[str, str],
    results: Mapping[str, tuple[str, str]],
) -> pl.DataFrame:
    """Der Beratungsverlauf: die Tabelle mit Gremium und Stufe je Punkt, in derselben Folge.

    ``organizations`` ist ``[bodies.organizations]`` (Schlüssel → Kürzel); eine Organisation, die
    die Tabelle nicht kennt, steht mit ihrem Schlüssel da (``gr/400224``), mehrere mit „+". Ein
    Eintrag, den ``results`` nicht kennt, bricht mit ``UnknownResultError`` ab: Wortlaut, Zahl und
    ein Punkt als Beleg.
    """
    entered = agenda.get_column("result").drop_nulls()
    unknown = Counter(value for value in entered.to_list() if value not in results)
    if unknown:
        examples = {
            value: str(agenda.filter(pl.col("result") == value).get_column("top").min())
            for value in unknown
        }
        raise UnknownResultError(
            "Einträge, die [outcomes.results] nicht kennt: "
            + "; ".join(f"{value!r} ({n}×, etwa {examples[value]})" for value, n in unknown.items())
        )
    gremium = [
        "+".join(organizations.get(key, key) for key in keys) or None
        for keys in agenda.get_column("organisationen").to_list()
    ]
    stage = {value: stage for value, (stage, _) in results.items()}
    return (
        agenda.with_columns(
            pl.Series("gremium", gremium, dtype=pl.String),
            pl.col("result")
            .replace_strict(stage, default=None, return_dtype=pl.String)
            .alias("stufe"),
        )
        .select(list(PROGRESS_SCHEMA))
        .sort(PROGRESS_ORDER, nulls_last=False)
    )


# --- Die Regel: letzte Entscheidung in der Sache, sonst letzter Stand -----------------------------


def decisions(progress: pl.DataFrame, results: Mapping[str, tuple[str, str]]) -> pl.DataFrame:
    """Je Dokument mit mindestens einem Eintrag der maßgebliche Punkt und seine Klasse.

    Gewählt wird der späteste Punkt der Stufe ``sache``, sonst der späteste überhaupt; „spätest"
    nach Sitzungsbeginn (ohne Datum zuerst), Folge in der Sitzung (ohne Folge wie 0), ID des
    Punkts und, wo zwei Beratungen denselben Punkt nennen, ID der Beratung (Review 2026-11-24, N3).
    Das Ergebnis hängt nur von der Menge der Zeilen ab, nicht von ihrer Folge.
    """
    klasse = {value: klasse for value, (_, klasse) in results.items()}
    return (
        progress.filter(pl.col("result").is_not_null())
        .with_columns(
            (pl.col("stufe") == SACHE).cast(pl.Int8).alias("__rang"),
            pl.col("ordnung").fill_null(0).alias("__ordnung"),
        )
        .sort(["id", "__rang", "sitzung", "__ordnung", "top", "beratung"], nulls_last=False)
        .group_by("id", maintain_order=True)
        .last()
        .select(
            "id",
            pl.col("result").replace_strict(klasse, return_dtype=pl.String).alias("klasse"),
            "result",
            pl.col("top").alias("entscheidung_top"),
            pl.col("gremium").alias("entscheidung_gremium"),
            pl.col("sitzung").dt.date().alias("entscheidung_datum"),
        )
        .sort("id")
    )


def _base_fits(
    corpus: pl.DataFrame,
    progress: pl.DataFrame,
    results: Mapping[str, tuple[str, str]],
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    days = result.get_column("tage")
    return (
        result.columns == list(BASE_COLUMNS)
        and one_row_per_document(result, corpus.get_column("id").to_list())
        and values_known(result, "klasse", CLASSES)
        and entries_decide_exactly(result)
        and decisions_in_progress(result, progress)
        and bool((days.drop_nulls() >= 0).all())
    )


@deal.pre(lambda corpus, progress, results: has_columns(corpus, "id", "date"))
@deal.ensure(_base_fits, message="eine Zeile je Korpus-ID, Klasse bekannt, Punkt im Verlauf")
def classify_outcomes(
    corpus: pl.DataFrame, progress: pl.DataFrame, results: Mapping[str, tuple[str, str]]
) -> pl.DataFrame:
    """Die Beschlusslage je Korpus-ID, ohne was Vorhaben 14 beiträgt (Rolle, Folgevorlage).

    ``tage`` zählt vom Datum des Dokuments bis zur Sitzung des maßgeblichen Punkts und ist null,
    wo die Sitzung davor liegt (140 Anträge der drei Perioden, gezählt, nicht verwendet; § 3.6).
    ``beratungen`` zählt jede Beratung des Dokuments im Datensatz, auch eine ohne Punkt.
    """
    counted = progress.group_by("id").agg(pl.col("beratung").n_unique().alias("beratungen"))
    frame = (
        corpus.select("id", "date")
        .join(decisions(progress, results), on="id", how="left")
        .join(counted, on="id", how="left")
        .sort("id")
    )
    days = (pl.col("entscheidung_datum") - pl.col("date")).dt.total_days()
    return frame.select(
        "id",
        pl.col("klasse").fill_null(NO_RESULT),
        pl.col("klasse")
        .fill_null(NO_RESULT)
        .replace_strict(COARSE, return_dtype=pl.String)
        .alias("grob"),
        "result",
        "entscheidung_top",
        "entscheidung_gremium",
        "entscheidung_datum",
        pl.when(days >= 0).then(days).otherwise(None).cast(pl.Int32).alias("tage"),
        pl.col("beratungen").fill_null(0).cast(pl.Int16),
    )


# --- Der beantragte Prüfauftrag (Rückfall 1: beschreibend, nie auf der Seite) --------------------


def _alternation(patterns: Sequence[str]) -> re.Pattern[str] | None:
    """Ein Muster aus der Liste, jede Alternative in ihrer Folge; ``None`` für eine leere Liste."""
    return re.compile("|".join(f"(?:{p})" for p in patterns)) if patterns else None


@dataclass(frozen=True)
class ReviewRules:
    """``[outcomes.review]``, einmal übersetzt; ``review_only`` läuft je Antrag."""

    marker: re.Pattern[str] | None
    reason: re.Pattern[str] | None
    reason_from: int
    window: int
    max_chars: int
    review: re.Pattern[str] | None
    not_review: re.Pattern[str] | None
    measure: re.Pattern[str] | None
    proviso: re.Pattern[str] | None
    neutral: frozenset[str]
    question: re.Pattern[str] | None
    question_chars: int
    sentence: re.Pattern[str] | None
    title: re.Pattern[str] | None
    frame: re.Pattern[str] | None

    @classmethod
    def from_settings(cls, review: OutcomeReview) -> ReviewRules:
        # Die zwei Formen des „zu"-Infinitivs stehen vor den übrigen Maßnahmen, wie im Messskript:
        # trennbar („einzurichten"), und frei, wo hinter „zu" kein Artikel oder keine Wendung steht.
        infinitives = []
        if review.separable:
            infinitives.append(rf"\b[a-zäöüß]*(?:{'|'.join(review.separable)})zu[a-zäöüß]{{3,}}n\b")
        not_verb = rf"(?!(?:{'|'.join(review.not_verb)})\b)" if review.not_verb else ""
        infinitives.append(rf"\bzu {not_verb}[a-zäöüß]{{3,}}n\b")
        return cls(
            marker=_alternation(review.marker),
            reason=_alternation(review.reason),
            reason_from=review.reason_from,
            window=review.window,
            max_chars=review.max_chars,
            review=_alternation(review.review),
            not_review=_alternation(review.not_review),
            measure=_alternation([*infinitives, *review.measure]),
            proviso=_alternation(review.proviso),
            neutral=frozenset(review.neutral),
            question=_alternation(review.question),
            question_chars=review.question_chars,
            sentence=_alternation(review.sentence),
            title=_alternation(review.title),
            frame=_alternation(review.frame),
        )


def decision_text(text: str | None, rules: ReviewRules) -> tuple[str, bool]:
    """(Beschlusstext, Marker gefunden) im kleingeschriebenen Text eines Antrags.

    Vom letzten Marker im Fenster bis zur Begründung, höchstens ``max_chars`` Zeichen; ohne
    Marker der Anfang bis zur Begründung oder bis zum Ende des Fensters.
    """
    t = text or ""
    found_reason = rules.reason.search(t, rules.reason_from) if rules.reason else None
    end = found_reason.start() if found_reason else min(len(t), rules.window)
    start, found = 0, False
    if rules.marker is not None:
        for match in rules.marker.finditer(t, 0, min(end, rules.window)):
            start, found = match.end(), True
    return t[start:end][: rules.max_chars], found


def sentences(segment: str, rules: ReviewRules) -> list[str]:
    """Die Sätze und Listenpunkte eines Beschlusstexts, ohne leere."""
    parts = rules.sentence.split(segment) if rules.sentence else [segment]
    return [part for part in parts if part and part.strip()]


def has_measure(part: str, rules: ReviewRules) -> bool:
    """Legt dieser Teil eines Satzes eine Handlung fest (eine Form außerhalb von ``neutral``)?"""
    if rules.measure is None:
        return False
    for match in rules.measure.finditer(part):
        text = match.group(0)
        word = text.split()[-1] if text.startswith("zu ") else text
        head = word.split()
        if not head or head[0] in rules.neutral or word in rules.neutral:
            continue
        return True
    return False


def review_only(title: str | None, text: str | None, rules: ReviewRules) -> tuple[bool, str]:
    """(Prüfauftrag, Quelle): verlangt der Antrag von der Verwaltung **nur** eine Prüfung?

    Ein Satz mit Prüfwort ist eine Prüfung; er trägt zusätzlich eine Maßnahme, wenn vor dem
    Prüfwort eine steht oder danach eine folgt, die nicht in einer Frage („prüfen, ob …") und
    nicht unter Vorbehalt steht. Ein Satz ohne Prüfwort und ohne Fragezeichen ist eine Maßnahme,
    wenn er eine Handlung festlegt. Prüfauftrag heißt: mindestens eine Prüfung, keine Maßnahme.
    Quelle ``text`` (Marker gefunden), ``anfang`` (ohne Marker) oder ``titel`` (kein Text).
    """
    segment, found = decision_text(text, rules)
    if not found and not (text or "").strip():
        hit = rules.title is not None and rules.title.search((title or "").lower()) is not None
        return hit, "titel"
    reviews = measures = 0
    for sentence in sentences(segment, rules):
        if rules.frame is not None and rules.frame.search(sentence):
            continue
        cleaned = rules.not_review.sub(" ", sentence) if rules.not_review else sentence
        word = rules.review.search(cleaned) if rules.review else None
        if word:
            reviews += 1
            if rules.proviso is not None and rules.proviso.search(cleaned):
                continue
            tail = cleaned[word.end() :]
            asks = rules.question is not None and rules.question.search(
                tail[: rules.question_chars]
            )
            if has_measure(cleaned[: word.start()], rules) or (
                not asks and has_measure(tail, rules)
            ):
                measures += 1
        elif "?" not in cleaned and has_measure(cleaned, rules):
            measures += 1
    return reviews > 0 and measures == 0, "text" if found else "anfang"


# --- Was an Vorhaben 14 hängt: Rolle, Praxiszellen, Folgevorlage ----------------------------------


@dataclass(frozen=True)
class OutcomeRules:
    """``[outcomes]``, einmal übersetzt."""

    results: Mapping[str, tuple[str, str]]
    practice_share: float
    practice_min: int
    followup_roles: frozenset[str]
    review: ReviewRules

    @classmethod
    def from_settings(cls, outcomes: Outcomes) -> OutcomeRules:
        return cls(
            results=dict(outcomes.results),
            practice_share=outcomes.practice_share,
            practice_min=outcomes.practice_min,
            followup_roles=frozenset(outcomes.followup_roles),
            review=ReviewRules.from_settings(outcomes.review),
        )


def practice_cells(outcomes: pl.DataFrame, share: float, minimum: int) -> pl.DataFrame:
    """Gremium-Jahre, in denen „erledigt" eine Praxis der Sitzungsleitung ist (§ 3.4, § 5).

    Gezählt werden die Anträge mit einer Sitzung des maßgeblichen Punkts, je Gremium und Jahr
    dieser Sitzung; eine Zelle ist eine Praxiszelle, wenn mindestens ``minimum`` davon „erledigt"
    sind und ihr Anteil mindestens ``share`` ist. ``gremium``, ``jahr``, ``n``, ``erledigt``,
    sortiert. Hängt nur von Gremium, Jahr und Klasse der Anträge ab.
    """
    return (
        outcomes.filter((pl.col("rolle") == MOTION) & pl.col("entscheidung_datum").is_not_null())
        .group_by(
            pl.col("entscheidung_gremium").alias("gremium"),
            pl.col("entscheidung_datum").dt.year().alias("jahr"),
        )
        .agg(pl.len().alias("n"), (pl.col("klasse") == DONE).sum().alias(DONE))
        .filter((pl.col(DONE) >= minimum) & (pl.col(DONE) >= share * pl.col("n")))
        .sort("gremium", "jahr", nulls_last=False)
    )


def first_followups(
    edges: pl.DataFrame, roles: pl.DataFrame, dates: pl.DataFrame, followup_roles: Collection[str]
) -> pl.DataFrame:
    """Je Dokument die erste Folgevorlage: eine Drucksache der Verwaltung, die es stark nennt.

    ``edges`` sind die Kanten aus Vorhaben 14 (``von`` nennt ``nach``, ``stark``), ``roles`` die
    Rollen (``id``, ``rolle``), ``dates`` die Daten der nennenden Drucksachen. „Erste" heißt:
    frühestes Datum, dann kleinste ID. ``id``, ``folgevorlage``, sortiert nach ``id``.
    """
    followers = roles.filter(pl.col("rolle").is_in(list(followup_roles))).select(
        pl.col("id").alias("von")
    )
    return (
        edges.filter(pl.col("stark"))
        .select("von", "nach")
        .join(followers, on="von", how="semi")
        .join(dates.select(pl.col("id").alias("von"), "date"), on="von", how="left")
        .sort(["nach", "date", "von"], nulls_last=True)
        .group_by("nach", maintain_order=True)
        .first()
        .select(pl.col("nach").alias("id"), pl.col("von").alias("folgevorlage"))
        .sort("id")
    )


def _complete_fits(
    base: pl.DataFrame,
    roles: pl.DataFrame,
    review: pl.DataFrame,
    followups: pl.DataFrame,
    rules: OutcomeRules,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    motion = (pl.col("rolle") == MOTION) & pl.col("klasse").is_in(list(ANGENOMMEN))
    entered = (pl.col("rolle") == MOTION) & (pl.col("klasse") != NO_RESULT)
    return (
        result.schema == pl.Schema(OUTCOME_SCHEMA)
        and one_row_per_document(result, base.get_column("id").to_list())
        and result.filter(~motion).get_column("pruefauftrag_beantragt").null_count()
        == result.filter(~motion).height
        and result.filter(motion).get_column("pruefauftrag_beantragt").null_count() == 0
        and result.filter(~entered).get_column("eintrag_tragfaehig").null_count()
        == result.filter(~entered).height
        and result.filter(entered).get_column("eintrag_tragfaehig").null_count() == 0
        and result.filter(pl.col("eintrag_tragfaehig").not_())
        .get_column("klasse")
        .is_in([DONE])
        .all()
    )


@deal.pre(
    lambda base, roles, review, followups, rules: (
        has_columns(roles, "id", "rolle")
        and has_columns(review, "id", "pruefauftrag")
        and has_columns(followups, "id", "folgevorlage")
    )
)
@deal.ensure(
    _complete_fits, message="Prüfauftrag nur bei angenommenen Anträgen, Praxis nur bei Anträgen"
)
def complete_outcomes(
    base: pl.DataFrame,
    roles: pl.DataFrame,
    review: pl.DataFrame,
    followups: pl.DataFrame,
    rules: OutcomeRules,
) -> pl.DataFrame:
    """Die Beschlusslage mit dem, was an Vorhaben 14 hängt.

    ``roles`` (``id``, ``rolle``) aus Vorhaben 14; ``review`` (``id``, ``pruefauftrag``) aus
    ``review_only`` für die Anträge; ``followups`` aus ``first_followups``. Der beantragte
    Prüfauftrag steht nur bei angenommenen Anträgen (sonst null), die Folgevorlage nur bei
    Anträgen, die Tragfähigkeit des Eintrags nur bei Anträgen mit Ergebnis: false, wo der Antrag
    „erledigt" ist und in einer Praxiszelle liegt, sonst true. Sortiert nach ``id``.
    """
    with_roles = base.join(roles.select("id", "rolle"), on="id", how="left").sort("id")
    cells = practice_cells(with_roles, rules.practice_share, rules.practice_min).select(
        pl.col("gremium").alias("entscheidung_gremium"),
        pl.col("jahr").alias("__jahr"),
        pl.lit(True).alias("__zelle"),
    )
    motion = pl.col("rolle") == MOTION
    accepted = motion & pl.col("klasse").is_in(list(ANGENOMMEN))
    practice = (pl.col("klasse") == DONE) & pl.col("__zelle").fill_null(False)
    return (
        with_roles.with_columns(pl.col("entscheidung_datum").dt.year().alias("__jahr"))
        .join(cells, on=["entscheidung_gremium", "__jahr"], how="left", nulls_equal=True)
        .join(review.select("id", "pruefauftrag"), on="id", how="left")
        .join(followups.select("id", "folgevorlage"), on="id", how="left")
        .sort("id")
        .select(
            "id",
            "rolle",
            *BASE_COLUMNS[1:],
            pl.when(accepted)
            .then(pl.col("pruefauftrag").fill_null(False))
            .otherwise(None)
            .alias("pruefauftrag_beantragt"),
            pl.when(motion).then(pl.col("folgevorlage")).otherwise(None).alias("folgevorlage"),
            pl.when(motion & (pl.col("klasse") != NO_RESULT))
            .then(~practice)
            .otherwise(None)
            .alias("eintrag_tragfaehig"),
        )
    )


# --- Antragserfolg je Fraktion (explorativ, § 3.10) -----------------------------------------------


def _success_fits(
    outcomes: pl.DataFrame,
    cosponsors: pl.DataFrame,
    bodies: pl.DataFrame,
    period: str,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return (
        result.schema == pl.Schema(SUCCESS_SCHEMA)
        and rows_unique(result, "periode", "gremium_art", "fraktion")
        and shares_bounded(result, "n", "angenommen")
        and result.equals(result.sort("periode", "gremium_art", "fraktion", nulls_last=True))
    )


@deal.pre(
    lambda outcomes, cosponsors, bodies, period: (
        has_columns(outcomes, "id", "rolle", "klasse", "eintrag_tragfaehig")
        and has_columns(cosponsors, "id", "fraktionen")
        and has_columns(bodies, "id", "gremium", "gremium_art")
    )
)
@deal.ensure(_success_fits, message="je Gremienart und Fraktion eine Zeile, n >= angenommen >= 0")
def motion_success(
    outcomes: pl.DataFrame, cosponsors: pl.DataFrame, bodies: pl.DataFrame, period: str
) -> pl.DataFrame:
    """Antragserfolg je Fraktion und Gremienart, beobachtet gegen erwartet (explorativ, § 3.10).

    Gezählt werden die Anträge mit Sachentscheidung (angenommen oder abgelehnt) und tragfähigem
    Eintrag. Erwartet ist die Summe der Annahmequoten der Gremien der Drucksache über die Anträge
    der Fraktion (indirekte Standardisierung, ``analysis.practice``); ein gemeinsamer Antrag
    zählt für jede beteiligte Fraktion, ein Antrag ohne Fraktion nur für die Quote seines
    Gremiums. Getrennt nach Gremienart, weil im Rat Erfolg fast nur Mehrheit heißt (§ 3.10).
    """
    decided = (
        outcomes.filter(
            (pl.col("rolle") == MOTION)
            & pl.col("klasse").is_in([*ANGENOMMEN, "abgelehnt"])
            & pl.col("eintrag_tragfaehig").fill_null(True)
        )
        .select("id", pl.col("klasse").is_in(list(ANGENOMMEN)).alias("angenommen"))
        .join(cosponsors.select("id", "fraktionen"), on="id", how="left")
        .join(bodies.select("id", "gremium", "gremium_art"), on="id", how="left")
        .sort("id")
    )
    ratios = observed_expected(
        decided,
        unit="fraktionen",
        outcome="angenommen",
        strata=["gremium_art", "gremium"],
        by=["gremium_art"],
    )
    return ratios.select(
        pl.lit(period, dtype=pl.String).alias("periode"),
        "gremium_art",
        pl.col("fraktionen").alias("fraktion"),
        pl.col(N).cast(pl.Int32).alias("n"),
        pl.col(OBSERVED).cast(pl.Int32).alias("angenommen"),
        pl.col(EXPECTED).alias("erwartet"),
        pl.col(RATIO).alias("beob_erw"),
    ).sort("periode", "gremium_art", "fraktion", nulls_last=True)


def period_key(start: dt.date, end: dt.date | None) -> str:
    """Der Schlüssel einer Periode in ``antragserfolg``: „2020-2025", „2025-"."""
    return f"{start.year}-{end.year}" if end is not None else f"{start.year}-"


def outcome_figures(frame: pl.DataFrame) -> dict[str, int]:
    """Dokumente je Klasse in der Folge von ``CLASSES``, für die Zeile des Schritts."""
    counts = dict(frame.group_by("klasse").len().iter_rows())
    return {name: int(counts.get(name, 0)) for name in CLASSES}
