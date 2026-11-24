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

from georep.contracts import is_district_code
from georep.layout import Layout
from georep.prep.bodies import BodyRules, resolve_organizations
from georep.settings import Originators, Settings

PROMPT_VERSION = "20-kurzfassung-2"  # Eingabe und Prompt Fassung 2; Teil des Cache-Schlüssels

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
       wo der Kopf ein Kürzel kennt, sonst wie geschrieben;
    2. sonst die OParl-Beratungsfolge (Punkt 58), nach Kürzel geordnet, weil OParl keine Folge
       kennt, und darum ohne Qualität;
    3. sonst das Gremium der Nummer.
    """
    rows: list[str] = []
    for row in head:
        code = row.get("gremium_kuerzel")
        name = body_label(code, rules) if isinstance(code, str) and code else ""
        name = name or " ".join(str(row.get("gremium") or "").split())
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
