"""Beitrag von Vorhaben 20: Kurzfassungen je Dokument mit einem lokalen Modell, nie veröffentlicht.

Messdokument ``docs/plans/20-kurzfassungen.md`` (§ 6 Bauplan, § 10 Synergie; Urteil § 5.3: bauen
mit ``gemma4``). Zwei, drei Sätze je Dokument: wer will was, worum geht es, was ist der Kern. Das
Modell sieht eine **Eingabe** aus Kopfzeilen und den Abschnitten aus Vorhaben 11 in fester Folge,
in einem Budget von Zeichen; jede Kurzfassung prüft danach ``enrich.fidelity`` deterministisch
gegen genau diese Eingabe.

**Eingabe Fassung 2** (§ 5.3, Vorbehalt 2; § 10, Punkt 3). In Fassung 1 nannte eine von vier
Kurzfassungen von gemma den Rat oder die Bezirksvertretung als Antragsteller einer Vorlage der
Verwaltung. Fassung 2 schreibt die Rolle darum in die Kopfzeilen, statt sie das Modell erraten zu
lassen: ``Absender:`` aus dem Urheber (Option 04) und den Fraktionen aus Vorhaben 15,
``Beratung:`` aus der Beratungsfolge (Punkt 58), ersatzweise aus dem Gremium der Nummer. Der
Prompt (Fassung 2) sagt in Regel 1, wie die beiden Zeilen zu lesen sind, in Regel 3, dass das
Modell nicht selbst zählt oder rechnet, und in Regel 5, dass Straßennamen keine Personennamen sind
(Fragen 20.8 und 20.12). Was davon wirkt, misst die Nachmessung vor dem Stapellauf (§ 10, Punkt 4).

**Nie veröffentlicht** (Konrad, 2026-11-23, Meta-Plan § 10, Frage 6). Beide Ausgaben liegen unter
``cache_root/<profil>/summaries/``, nicht unter ``data_root``: so greifen weder ``report`` noch
``publish`` noch ``pack`` sie, und kein Paket trägt sie. Die Antworten selbst liegen im Modellcache
von F5 (``cache_root/ml/``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NamedTuple

import deal
import polars as pl

from georep.contracts import is_district_code, one_row_per_document
from georep.enrich import Contribution
from georep.enrich.fidelity import (
    FIDELITY_COLUMNS,
    Lexicon,
    check,
    evidence,
    fidelity_row,
    lexicon_from,
)
from georep.enrich.functions import functions_files
from georep.enrich.sections import raw_text_frame, sections_files
from georep.http import Transport
from georep.io import write_parquet
from georep.layout import Layout
from georep.ml.base import GenerationOptions, GenerationUse, Generator, Reply, full_name
from georep.ml.batch import Generated, generate_texts, progress_log
from georep.ml.cache import ModelCache, input_sha256
from georep.ml.ollama import (
    OllamaGenerator,
    client_from_settings,
    generation_options,
    generator_from_settings,
)
from georep.pipeline import Step
from georep.prep.bodies import BodyRules, merge_consultations, resolve_organizations
from georep.prep.references import ReferenceRules, known_codes, parse_reference
from georep.prep.structure import BETREFF, HEAD_PREFIX, StructureRules
from georep.settings import Ml, Originators, Settings
from georep.spans import SECTION_KIND, check_spans, read_span

PROMPT_VERSION = "20-kurzfassung-2"  # Eingabe und Prompt Fassung 2; Teil des Cache-Schlüssels
SUMMARIES_SCHEMA_VERSION = 1  # kurzfassungen.parquet und kurzfassungen_treue.parquet

# Wortgleich mit Fassung 1 (Messdokument § 3.1).
SYSTEM = (
    "Du schreibst Kurzfassungen von Dokumenten aus dem Ratsinformationssystem einer deutschen "
    "Stadt für Ratsmitglieder. Du schreibst sachlich und neutral auf Deutsch und gibst nur wieder, "
    "was im Dokument steht."
)
# Fassung 2: Regel 1 nennt die Kopfzeilen der Rolle, Regel 3 verbietet selbst gezählte und
# gerechnete Zahlen (Frage 20.12), Regel 5 nimmt Straßen- und Einrichtungsnamen aus (Frage 20.8).
RULES = """Fasse das Dokument unten in zwei bis drei Sätzen zusammen, zusammen höchstens 80 Wörter.

Regeln:
1. Der erste Satz sagt, wer was will oder mitteilt (wer beantragt, beschließen lassen will, fragt oder berichtet) und worum es geht. Wer das Dokument einbringt, steht unter „Absender"; die Gremien unter „Beratung" beraten oder entscheiden darüber, sie beantragen es nicht.
2. Danach das Wesentliche: der Kern des Beschlussvorschlags, der Fragen oder der Mitteilung, dazu Ort, Betrag und Frist, wenn das Dokument sie nennt.
3. Zahlen, Beträge, Daten, Drucksachennummern und Namen nur, wenn sie im Dokument stehen, und genau so geschrieben wie dort. Zähle und rechne nicht selbst: keine Summe, keine Anzahl aufgezählter Punkte, die das Dokument nicht nennt.
4. Füge nichts hinzu, was nicht im Dokument steht: kein Wissen von außen, keine Bewertung, keine Vermutung.
5. Keine Personennamen; nenne Personen nach ihrer Rolle (etwa „die Verwaltung", „die Fraktion", „die Bezirksvertretung"). Straßen-, Platz- und Einrichtungsnamen sind keine Personennamen; nenne sie, wie sie im Dokument stehen.
6. Antworte nur mit der Kurzfassung als Fließtext, ohne Überschrift, ohne Aufzählung, ohne Einleitung.

Dokument:

"""

# Die Abschnitte aus Vorhaben 11 in der Folge, in der sie das Budget füllen, mit ihrer Überschrift
# in der Eingabe; Kopf, Beratungsfolge, Anlagen und „Nachrichtlich" bleiben draußen (§ 3.1).
SECTIONS: tuple[tuple[str, str], ...] = (
    ("betreff", "Betreff"),
    ("beschlussvorschlag", "Beschlussvorschlag"),
    ("fragen", "Fragen"),
    ("sachdarstellung", "Sachdarstellung"),
    ("begruendung", "Begründung"),
    ("stellungnahme", "Stellungnahme der Verwaltung"),
    ("beschlusslage", "Zitierter Beschluss"),
    ("finanzen", "Finanzen"),
    ("klima", "Klima"),
    ("alternative", "Alternative"),
)
# Ohne einen dieser Abschnitte steht nach dem Betreff der Rohtext ab dem Ende des Kopfs (Rückfall).
CORE = frozenset(
    {"beschlussvorschlag", "fragen", "sachdarstellung", "begruendung", "stellungnahme"}
)
FALLBACK_TITLE = "Text"
MARK = " […]"  # hinter einem gekürzten Abschnitt; danach kommt nichts mehr
# Frage 20.6: ein Rückfall mit weniger Text nach dem Kopf hat keinen Inhalt, nur den Betreff; dafür
# schreibt der Schritt keine Kurzfassung (``text`` null, ``grund`` ohne_text). Die Grenze ist die
# des Messskripts, unter der es den ganzen Rohtext samt Kopf nahm.
MIN_FALLBACK_CHARS = 50
UNKNOWN = "nicht angegeben"
CONSULTATION = "consultation_organizations"

SOURCES = ("abschnitte", "rohtext", "ohne_text")  # woher die Eingabe kommt
REASONS = ("ohne_text", "offen", "abgewiesen")  # warum ``text`` null ist

# Die Absender je Urheberklasse aus Option 04; die Fraktionen nennt Vorhaben 15. Teil der Eingabe
# und darum der Prompt-Version: wer sie ändert, zählt PROMPT_VERSION hoch.
SENDERS: dict[str, str] = {
    "Verwaltung": "Verwaltung",
    "Person": "einzelnes Mitglied eines Gremiums",
    "Eingabe": "Einwohnerinnen oder Einwohner (Eingabe)",
}
FRACTION = "Fraktion"


@dataclass(frozen=True)
class SummaryMeta:
    """Die Kopfzeilen eines Dokuments: Metadaten aus dem Korpus und die Rolle (Fassung 2)."""

    id: str
    paper_type: str
    reference: str
    date: date | None
    title: str
    sender: str = UNKNOWN
    deliberation: str = UNKNOWN


@dataclass(frozen=True)
class SectionText:
    """Ein Abschnitt aus Vorhaben 11 mit seinem gelesenen Text (``spans.read_span``)."""

    kind: str  # ``norm`` des Abschnitts, etwa ``beschlussvorschlag``
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class SummaryInput:
    """Was das Modell als Dokument sieht, und woraus es entstand."""

    id: str
    text: str  # Kopfzeilen und Abschnitte; leer bei ``ohne_text``
    source: str  # eine aus SOURCES
    sections: tuple[str, ...]  # die Abschnitte in der Eingabe, in ihrer Folge
    truncated: bool  # ein Abschnitt endet mit MARK, oder einer fiel weg
    chars: int  # Abschnittstext ohne Kopfzeilen


def date_de(value: date | None) -> str:
    return f"{value.day:02d}.{value.month:02d}.{value.year}" if value else "unbekannt"


def header(meta: SummaryMeta) -> str:
    """Die sechs Kopfzeilen der Eingabe Fassung 2."""
    return (
        f"Dokumentart: {meta.paper_type or 'unbekannt'}\n"
        f"Absender: {meta.sender or UNKNOWN}\n"
        f"Beratung: {meta.deliberation or UNKNOWN}\n"
        f"Drucksache: {meta.reference or 'unbekannt'}\n"
        f"Datum: {date_de(meta.date)}\n"
        f"Titel: {meta.title or 'unbekannt'}"
    )


@deal.pre(lambda body, room: room > 0)
@deal.ensure(lambda body, room, result: len(result) <= room + len(MARK) and result.endswith(MARK))
def cut(body: str, room: int) -> str:
    """Auf höchstens ``room`` Zeichen, am letzten Zeilen- oder Wortende davor, mit MARK."""
    end = body.rfind("\n", 0, room)
    if end < room // 2:
        end = body.rfind(" ", 0, room)
    if end < room // 2:
        end = room
    return body[:end].rstrip() + MARK


# Benannte Validatoren mit der ganzen Signatur: deal bindet Schlüsselwortparameter samt Vorgaben
# nur an Validatoren, die sie nennen (CLAUDE.md, deal; wie ``ml.batch``).
def _budget_positive(
    meta: SummaryMeta,
    sections: Sequence[SectionText],
    fallback: str,
    budget: int,
    *,
    body_empty: bool = False,
) -> bool:
    return budget > 0


def _input_fits(
    meta: SummaryMeta,
    sections: Sequence[SectionText],
    fallback: str,
    budget: int,
    result: SummaryInput,
    *,
    body_empty: bool = False,
) -> bool:
    return (
        result.source in SOURCES
        and result.chars <= budget + len(MARK)
        and (result.source == "ohne_text") == (result.text == "")
        and result.id == meta.id
    )


@deal.pre(_budget_positive, message="das Budget ist positiv")
@deal.ensure(_input_fits, message="Quelle bekannt, Budget gehalten, leer genau ohne Text")
def summary_input(
    meta: SummaryMeta,
    sections: Sequence[SectionText],
    fallback: str,
    budget: int,
    *,
    body_empty: bool = False,
) -> SummaryInput:
    """Die Eingabe eines Dokuments: Kopfzeilen, dann die Abschnitte in fester Folge im Budget.

    ``sections`` sind die Abschnitte aus Vorhaben 11 mit ihrem gelesenen Text, ``fallback`` der
    gelesene Rohtext ab dem Ende des Kopfs. Abschnitte außerhalb von SECTIONS fallen weg; ein
    Abschnitt, der einen schon genommenen überlappt (Ebene 2 im Text eines Abschnitts der Ebene
    1), wird übersprungen; ein leerer auch. Der Abschnitt, der das Budget sprengt, endet mit
    ``cut``, danach kommt nichts mehr (so beschreibt es § 3.1; das Messskript nahm nach einer
    Kürzung am Zeilenende noch Abschnitte, solange Platz blieb). Ohne einen Kernabschnitt (CORE) steht nach dem Betreff der
    Rückfall unter „Text" im verbliebenen Budget; ist er kürzer als MIN_FALLBACK_CHARS oder sagt der
    Kopf von 11, dass nach ihm kein Text steht (``body_empty``, ``rumpf_leer``), gibt es keine
    Eingabe (``ohne_text``, Frage 20.6). Abschnitte gleichen Titels hintereinander stehen unter
    einer Überschrift.
    """
    order = {kind: i for i, (kind, _) in enumerate(SECTIONS)}
    titles = dict(SECTIONS)
    ordered = sorted(
        (s for s in sections if s.kind in order), key=lambda s: (order[s.kind], s.start)
    )
    used: list[tuple[int, int]] = []
    parts: list[tuple[str, str]] = []
    room, truncated = budget, False
    for section in ordered:
        if room <= 0:
            truncated = True
            break
        if any(section.start < b and a < section.end for a, b in used):
            continue
        body = section.text.strip()
        if not body:
            continue
        if len(body) > room:
            body, truncated = cut(body, room), True
        used.append((section.start, section.end))
        parts.append((section.kind, body))
        room -= len(body)
        if truncated:
            break  # nach dem gekürzten Abschnitt kommt nichts mehr
    source = "abschnitte"
    if not any(kind in CORE for kind, _ in parts):
        parts = [(kind, body) for kind, body in parts if kind == "betreff"]
        rest = fallback.strip()
        if body_empty or len(rest) < MIN_FALLBACK_CHARS:
            return SummaryInput(meta.id, "", "ohne_text", (), False, 0)
        source = "rohtext"
        room = budget - sum(len(body) for _, body in parts)
        truncated = any(body.endswith(MARK) for _, body in parts)
        if room <= 0:
            rest, truncated = "", True
        elif len(rest) > room:
            rest, truncated = cut(rest, room), True
        if rest:
            parts.append((FALLBACK_TITLE.lower(), rest))
    blocks: list[str] = []
    for kind, body in parts:
        title = titles.get(kind, FALLBACK_TITLE)
        if blocks and blocks[-1].startswith(f"## {title}\n"):
            blocks[-1] += "\n\n" + body
        else:
            blocks.append(f"## {title}\n{body}")
    return SummaryInput(
        meta.id,
        header(meta) + "\n\n" + "\n\n".join(blocks),
        source,
        tuple(dict.fromkeys(kind for kind, _ in parts)),
        truncated,
        sum(len(body) for _, body in parts),
    )


def prompt(entry: SummaryInput) -> str:
    """Der Prompt eines Dokuments: Regeln und Eingabe; die Systemnachricht ist SYSTEM."""
    return RULES + entry.text


# --- Rolle (Eingabe Fassung 2) -------------------------------------------------------------------


def party_labels(originators: Originators) -> dict[str, str]:
    """Schlüssel -> Anzeigename der Parteien und Gruppen aus Option 04."""
    return {party.key: party.label for party in (*originators.parties, *originators.groups)}


def fraction_label(key: str, labels: Mapping[str, str]) -> str:
    """Eine Fraktion aus Vorhaben 15: ``SPD+VOLT`` heißt mit den Namen ihrer Parteien ``SPD/Volt``."""
    return "/".join(labels.get(part, part) for part in key.split("+"))


def _join(names: Sequence[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} und {names[-1]}"


@deal.ensure(lambda kind, fractions, labels, result: bool(result))
def sender(kind: str | None, fractions: Sequence[str], labels: Mapping[str, str]) -> str:
    """Der Absender aus der Urheberklasse (Option 04) und den Fraktionen (Vorhaben 15).

    Eine Fraktion heißt mit ihrem Namen, mehrere gemeinsam mit „und"; ohne genannte Fraktion bleibt
    die Klasse („Fraktion"). Unbekannt heißt UNKNOWN, nie ein geratener Absender.
    """
    if kind == FRACTION:
        names = [fraction_label(key, labels) for key in fractions]
        if not names:
            return FRACTION
        return f"{FRACTION} {names[0]}" if len(names) == 1 else f"Fraktionen {_join(names)}"
    return SENDERS.get(kind or "", UNKNOWN)


def known_body_name(code: str, rules: BodyRules) -> str:
    """Der gesicherte Name eines Kürzels aus ``[bodies]``; leer, wo keiner gesichert ist."""
    if is_district_code(code, rules.district_body):
        named = rules.district_body_names.get(code)
        return named or rules.district_body_name.format(n=int(code[len(rules.district_body) :]))
    return rules.names.get(code) or ""


def body_label(code: str, rules: BodyRules) -> str:
    """Der Name eines Gremienkürzels, wie die Seite ihn zeigt; ohne gesicherten Namen das Kürzel."""
    if is_district_code(code, rules.district_body):
        named = rules.district_body_names.get(code)
        return named or rules.district_body_name.format(n=int(code[len(rules.district_body) :]))
    return rules.names.get(code) or code


def _deliberation_named(
    organizations: Sequence[str],
    own: str | None,
    rules: BodyRules,
    result: str,
    *,
    head: Sequence[Mapping[str, object]] = (),
) -> bool:
    return bool(result)


def _quality(value: object) -> str:
    """Die Qualität einer Zeile der Beratungsfolge; ein Platzhalter („-", „-/-") ist keine."""
    text = " ".join(str(value or "").split())
    return "" if re.fullmatch(r"[-/ ]*", text) else text


@deal.ensure(_deliberation_named, message='die Zeile nennt Gremien oder „nicht angegeben"')
def deliberation(
    organizations: Sequence[str],
    own: str | None,
    rules: BodyRules,
    *,
    head: Sequence[Mapping[str, object]] = (),
) -> str:
    """Die Gremien der Beratung, in dieser Folge der Quellen:

    1. die Zeilen der Beratungsfolge aus dem Kopf des Dokuments (Vorhaben 11, ``beratungsfolge``
       in ``dokumente_kopf.parquet``), in ihrer Folge und mit ihrer Qualität („Rat
       (Entscheidung)"). Geprüft in 11: Gremium, Datum und Qualität je Zeile 160 von 168 (168 mit
       dem Platzhalter „-" als keine), die Folge 27 von 27 Dokumenten mit zwei und mehr Zeilen
       gegen dieselben Labels (Bau-Agent 20, 2026-11-24). Das Gremium heißt wie in ``[bodies]``,
       wo der Kopf ein Kürzel mit gesichertem Namen kennt, sonst wie geschrieben;
    2. sonst die OParl-Beratungsfolge (Punkt 58), nach Kürzel geordnet, weil OParl keine Folge
       kennt, und darum ohne Qualität;
    3. sonst das Gremium der Nummer.
    """
    rows: list[str] = []
    for row in head:
        code = row.get("gremium_kuerzel")
        known = known_body_name(code, rules) if isinstance(code, str) and code else ""
        written = " ".join(str(row.get("gremium") or "").split())
        name = known or written or (code if isinstance(code, str) else "")
        if name:
            quality = _quality(row.get("qualitaet"))
            rows.append(f"{name} ({quality})" if quality else name)
    if rows:
        return ", ".join(dict.fromkeys(rows))
    codes = list(resolve_organizations(organizations, rules.organizations))
    if not codes and own:
        codes = [own]
    names = list(dict.fromkeys(body_label(code, rules) for code in codes))
    return ", ".join(names) if names else UNKNOWN


def role_frame(
    ids: Iterable[str],
    originators: pl.DataFrame | None,
    fractions: pl.DataFrame | None,
    bodies: pl.DataFrame | None,
    consultations: pl.DataFrame | None,
    settings: Settings,
    *,
    head: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Je ID ``absender`` und ``beratung``; jede Quelle darf fehlen (``None``).

    ``originators``: ``id``, ``urheber_art`` (Option 04); ``fractions``: ``id``, ``fraktionen``
    (Vorhaben 15); ``bodies``: ``id``, ``gremium`` (Option 05); ``consultations``: ``id``,
    ``consultation_organizations`` (Punkt 58, Korpus und Paket schon zusammengeführt); ``head``:
    ``id``, ``beratungsfolge`` (Vorhaben 11, Liste mit ``gremium``, ``gremium_kuerzel``,
    ``qualitaet``).
    """
    kinds = _texts(originators, "urheber_art")
    own = _texts(bodies, "gremium")
    groups = _lists(fractions, "fraktionen")
    folge = _lists(consultations, "consultation_organizations")
    heads = _structs(head, "beratungsfolge")
    labels = party_labels(settings.originators)
    rules = BodyRules.from_settings(settings.bodies)
    rows = [
        (
            doc,
            sender(kinds.get(doc), groups.get(doc) or [], labels),
            deliberation(folge.get(doc) or [], own.get(doc), rules, head=heads.get(doc) or []),
        )
        for doc in sorted(set(ids))
    ]
    return pl.DataFrame(
        rows, schema={"id": pl.String, "absender": pl.String, "beratung": pl.String}, orient="row"
    )


def _texts(frame: pl.DataFrame | None, column: str) -> dict[str, str]:
    """ID -> Text einer Spalte; leer, wo die Quelle oder die Spalte fehlt, ohne Nullwerte."""
    if frame is None or column not in frame.columns:
        return {}
    pairs = frame.select("id", column).drop_nulls().iter_rows()
    return {str(doc): str(value) for doc, value in pairs}


def _structs(frame: pl.DataFrame | None, column: str) -> dict[str, list[dict[str, object]]]:
    """ID -> Liste von Strukturen (die Beratungsfolge des Kopfs); leer, wo sie fehlt."""
    if frame is None or column not in frame.columns:
        return {}
    pairs = frame.select("id", column).drop_nulls().iter_rows()
    return {str(doc): [dict(row) for row in rows] for doc, rows in pairs}


def _lists(frame: pl.DataFrame | None, column: str) -> dict[str, list[str]]:
    """ID -> Liste einer Listenspalte; leer, wo die Quelle oder die Spalte fehlt."""
    if frame is None or column not in frame.columns:
        return {}
    pairs = frame.select("id", column).drop_nulls().iter_rows()
    return {str(doc): [str(v) for v in values] for doc, values in pairs}


# --- Ausgaben ------------------------------------------------------------------------------------


class SummaryFiles(NamedTuple):
    summaries: Path
    fidelity: Path


def summaries_dir(layout: Layout) -> Path:
    """``cache_root/<profil>/summaries/``: nie unter ``data_root`` (Frage 6)."""
    return layout.cache / "summaries"


def summaries_files(layout: Layout) -> SummaryFiles:
    """Die beiden Tabellen des Schritts; beide ohne Platz auf der Seite und in keinem Paket."""
    folder = summaries_dir(layout)
    return SummaryFiles(folder / "kurzfassungen.parquet", folder / "kurzfassungen_treue.parquet")


SUMMARY_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "text": pl.String(),  # null: noch nicht gerechnet, abgewiesen oder ohne Text (``grund``)
    "grund": pl.String(),  # eines aus REASONS genau dort, wo ``text`` null ist
    "modell": pl.String(),
    "digest": pl.String(),
    "prompt": pl.String(),
    "abgeschnitten": pl.Boolean(),  # die Antwort stieß an ``num_predict``
    "eingabe_quelle": pl.String(),  # eines aus SOURCES
    "eingabe_gekuerzt": pl.Boolean(),
}


def _summaries_hold(
    inputs: Mapping[str, SummaryInput], got: Generated, use: GenerationUse, result: pl.DataFrame
) -> bool:
    texts = result.get_column("text").is_null()
    reasons = result.get_column("grund")
    return (
        one_row_per_document(result, inputs)
        and (texts == reasons.is_not_null()).all()
        and reasons.drop_nulls().is_in(list(REASONS)).all()
    )


@deal.ensure(_summaries_hold, message="eine Zeile je ID mit Rohtext; text null genau mit grund")
def summary_frame(
    inputs: Mapping[str, SummaryInput], got: Generated, use: GenerationUse
) -> pl.DataFrame:
    """``kurzfassungen.parquet``: je ID mit Rohtext die Kurzfassung oder der Grund, warum keine.

    ``got`` sind die Antworten auf die Prompts der Eingaben mit Text, in der Folge der sortierten
    IDs. Fehlt eine Antwort, ist sie abgewiesen (der Cache hat sie als Abweisung gemerkt) oder offen
    (noch nicht gefragt, gescheitert).
    """
    asked = [doc for doc in sorted(inputs) if inputs[doc].source != "ohne_text"]
    answers = dict(zip(asked, zip(got.texts, got.truncated, strict=True), strict=True))
    rejected = {asked[index] for index, _ in got.report.rejected}
    shas = {doc: input_sha256(f"{SYSTEM}\x00{prompt(inputs[doc])}") for doc in asked}
    rejected_shas = {shas[doc] for doc in rejected}
    rows = []
    for doc in sorted(inputs):
        entry = inputs[doc]
        text, cut_off = answers.get(doc, (None, False))
        if entry.source == "ohne_text":
            reason: str | None = "ohne_text"
        elif text is not None:
            reason = None
        else:
            reason = "abgewiesen" if shas[doc] in rejected_shas else "offen"
        rows.append(
            (
                doc,
                text,
                reason,
                use.name,
                use.generator.digest,
                use.prompt,
                bool(cut_off) if text is not None else False,
                entry.source,
                entry.truncated,
            )
        )
    return pl.DataFrame(rows, schema=SUMMARY_SCHEMA, orient="row")


def fidelity_frame(
    summaries: pl.DataFrame, inputs: Mapping[str, SummaryInput], lexicon: Lexicon
) -> pl.DataFrame:
    """``kurzfassungen_treue.parquet``: je Kurzfassung die Zählung der Treueprüfung, ohne Text."""
    rows = []
    for doc, text, cut_off in (
        summaries.filter(pl.col("text").is_not_null())
        .select("id", "text", "abgeschnitten")
        .iter_rows()
    ):
        result = check(text, bool(cut_off), evidence(inputs[doc].text, lexicon), lexicon)
        rows.append({"id": doc, **fidelity_row(result)})
    return pl.DataFrame(rows, schema={"id": pl.String(), **FIDELITY_COLUMNS})


def _optional(path: Path) -> pl.DataFrame | None:
    return pl.read_parquet(path) if path.is_file() else None


def summary_inputs(
    settings: Settings, layout: Layout, ids: Iterable[str] | None = None
) -> dict[str, SummaryInput]:
    """Die Eingaben (Fassung 2) je Korpus-ID mit Rohtext; mit ``ids`` nur für diese.

    Die Abschnitte kommen aus Vorhaben 11 als Positionsspannen; gelesen wird ihr Text nur mit
    ``read_span`` und den Seitenmustern des Profils (``structure.page_noise``), keine eigene
    Säuberung. Der Rückfall ist der Rohtext ab dem Ende des Kopfs (Betreff und Kopffelder), wie
    § 3.1; ``rumpf_leer`` aus dem Kopf von 11 und die Rolle kommen aus ``role_frame``.
    """
    wanted = None if ids is None else set(ids)
    corpus = pl.read_parquet(
        layout.corpus,
        columns=["id", "name", "reference", "date", "paper_type", "file_name", CONSULTATION],
    )
    if wanted is not None:
        corpus = corpus.filter(pl.col("id").is_in(sorted(wanted)))
    raw = raw_text_frame(layout.raw_texts).select("name", "text")
    docs = (
        corpus.join(raw, left_on="file_name", right_on="name", how="inner")
        .filter(pl.col("text").fill_null("") != "")
        .sort("id")
    )
    texts = dict(docs.select("id", "text").iter_rows())
    files = sections_files(layout)
    spans = pl.read_parquet(files.sections).filter(
        (pl.col("kind") == SECTION_KIND) & pl.col("id").is_in(sorted(texts))
    )
    check_spans(spans, {doc: len(text) for doc, text in texts.items()}, positions={SECTION_KIND})
    by_doc: dict[str, list[tuple[str, int, int]]] = {}
    for doc, start, end, norm in spans.select("id", "start", "end", "norm").iter_rows():
        by_doc.setdefault(doc, []).append((norm, start, end))
    head = pl.read_parquet(files.head, columns=["id", "beratungsfolge", "rumpf_leer"])
    empty = dict(head.select("id", "rumpf_leer").drop_nulls().iter_rows())
    extra = _optional(layout.consultations) if settings.bodies.consultations is not None else None
    roles = role_frame(
        texts,
        _optional(layout.document_originators),
        _optional(functions_files(layout).cosponsors),
        _optional(layout.papers_bodies),
        merge_consultations(
            corpus.select("id", CONSULTATION),
            extra.select("id", CONSULTATION) if extra is not None else None,
        ),
        settings,
        head=head,
    )
    role = {doc: (who, where) for doc, who, where in roles.iter_rows()}
    noise = StructureRules.from_settings(settings).page_noise
    kinds = {kind for kind, _ in SECTIONS}
    budget = settings.summaries.budget_chars
    out: dict[str, SummaryInput] = {}
    for row in docs.iter_rows(named=True):
        doc, raw_text = row["id"], row["text"]
        found = by_doc.get(doc, [])
        sections = [
            SectionText(norm, start, end, read_span(raw_text, start, end, noise))
            for norm, start, end in found
            if norm in kinds
        ]
        fallback = ""
        if not any(s.kind in CORE and s.text.strip() for s in sections):
            head_end = max(
                (end for norm, _, end in found if norm == BETREFF or norm.startswith(HEAD_PREFIX)),
                default=0,
            )
            fallback = read_span(raw_text, head_end, len(raw_text), noise)
        who, where = role.get(doc, (UNKNOWN, UNKNOWN))
        meta = SummaryMeta(
            doc,
            row["paper_type"] or "",
            row["reference"] or "",
            row["date"],
            row["name"] or "",
            who,
            where,
        )
        out[doc] = summary_input(
            meta, sections, fallback, budget, body_empty=bool(empty.get(doc, False))
        )
    return out


def lexicon_for(settings: Settings, layout: Layout) -> Lexicon:
    """Das Lexikon der Treueprüfung für ein Profil: Korpus, Wörterbuch, Gremien, Nummern, Ämter."""
    corpus = pl.read_parquet(layout.corpus, columns=["reference", "text"])
    places: list[str] = []
    if layout.dictionary.is_file():
        terms = pl.read_parquet(layout.dictionary, columns=["suchbegriffe"])
        places = [str(t) for t in terms.get_column("suchbegriffe").explode().drop_nulls()]
    rules = ReferenceRules.from_settings(settings.procedures)
    bodies = settings.bodies
    block = settings.summaries
    return lexicon_from(
        corpus.get_column("text"),
        places,
        {**bodies.council, **bodies.committees},
        district_code=bodies.district_body,
        district_name=bodies.district_body_name,
        rare_share=block.rare_share,
        known_documents=block.known_documents,
        references=rules if rules.forms else None,
        codes=known_codes(parse_reference(r, rules) for r in corpus.get_column("reference")),
        person_titles=block.person_titles,
    )


class DeferredGenerator:
    """Der Generator aus ``[ml]`` mit dem Modell aus ``[summaries]``; der Client entsteht erst beim
    ersten ``digest`` oder ``generate`` (wie ``enrich.embeddings.DeferredEmbedder``, Review 18, N5):
    ``build_steps``, ``steps`` und ``status`` fragen den Server nie, und ein unerlaubtes
    ``ml.base_url`` ist erst mit ``--models`` ein ``ModelError``."""

    def __init__(self, ml: Ml, model: str) -> None:
        self.ml = ml
        self.name = full_name(model)
        self._model = model
        self._inner: OllamaGenerator | None = None

    def _generator(self) -> OllamaGenerator:
        if self._inner is None:
            self._inner = generator_from_settings(
                self.ml, client_from_settings(self.ml), model=self._model
            )
        return self._inner

    @property
    def digest(self) -> str:
        return self._generator().digest

    def generate(
        self, prompt: str, *, system: str = "", options: GenerationOptions | None = None
    ) -> Reply:
        return self._generator().generate(prompt, system=system, options=options)


def summaries_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Der Schritt ``summaries``, wenn das Profil ihn und die Abschnitte von 11 einschaltet.

    Er läuft nur mit ``georep run --models`` (Fundament F5); ``http`` bleibt ungenutzt.
    """
    if not settings.summaries.enabled or not settings.structure.enabled:
        return []
    return model_steps(settings, layout, DeferredGenerator(settings.ml, settings.summaries.model))


def model_steps(settings: Settings, layout: Layout, generator: Generator) -> list[Step]:
    """Der Schritt mit einem gegebenen Generator; Tests geben ``FakeGenerator``."""
    files = summaries_files(layout)
    sections = sections_files(layout)
    use = GenerationUse(generator, PROMPT_VERSION, generation_options(settings.ml))
    optional = (
        layout.document_originators,
        functions_files(layout).cosponsors,
        layout.papers_bodies,
        layout.dictionary,
    ) + ((layout.consultations,) if settings.bodies.consultations is not None else ())

    def summaries() -> str:
        inputs = summary_inputs(settings, layout)
        asked = [inputs[doc] for doc in sorted(inputs) if inputs[doc].source != "ohne_text"]
        with ModelCache(layout.ml_cache, use.name) as cache:
            got = generate_texts(
                use,
                cache,
                [prompt(entry) for entry in asked],
                system=SYSTEM,
                limit=settings.ml.limit,
                progress=progress_log(),
            )
        frame = summary_frame(inputs, got, use)
        fidelity = fidelity_frame(frame, inputs, lexicon_for(settings, layout))
        write_parquet(frame, files.summaries, schema_version=SUMMARIES_SCHEMA_VERSION)
        write_parquet(fidelity, files.fidelity, schema_version=SUMMARIES_SCHEMA_VERSION)
        reasons = frame.get_column("grund").value_counts()
        missing = ", ".join(f"{n} {r}" for r, n in reasons.drop_nulls().sort("grund").iter_rows())
        names = int(fidelity.get_column("personennamen").sum()) if fidelity.height else 0
        ok = int(fidelity.get_column("ok").sum()) if fidelity.height else 0
        return (
            f"{frame.height} Dokumente mit Rohtext ({got.report.line()}); ohne Kurzfassung: "
            f"{missing or 'keine'}; Treue ohne unbelegte Angabe {ok} von {fidelity.height}, "
            f"Personennamen {names} (Prompt {use.prompt})"
        )

    return [
        Step(
            "summaries",
            (layout.corpus, layout.raw_texts, sections.sections, sections.head),
            (files.summaries, files.fidelity),
            summaries,
            SUMMARIES_SCHEMA_VERSION,
            models=use,
            optional=optional,
        )
    ]


CONTRIBUTION = Contribution("20-kurzfassungen", steps=summaries_steps)
