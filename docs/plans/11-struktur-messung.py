"""Rechnet die Zahlen von `11-struktur.md` nach (Vorhaben 11, Stufe 1: Struktur der Dokumente).

    uv run python docs/plans/11-struktur-messung.py               # alle Zahlen, rund eine Minute
    uv run python docs/plans/11-struktur-messung.py --aufgaben    # dazu Stichprobe und Kodieraufgaben

Liest nur: den Rohtext der Messdatei (`messdaten/rohtext/<profil>.parquet`, pypdf 7.1.0, Groß- und
Kleinschreibung, Zeilen, Seiten mit `\\f`, Kopf nicht abgeschnitten), den Korpus der Hauptperiode
aus `data_root` (Stand nach `georep run`), die Beratungsfolge der Hauptperiode aus
`raw/beratungsfolge.parquet` und die `papers.jsonl` der Pakete unter `snapshots/` und
`reference/moenchengladbach/`. Schreibt nur mit `--aufgaben`: `validierung/11-struktur/stichprobe.csv`
(nur IDs) ins Repo und die Kodieraufgaben mit Textausschnitten nach `messdaten/kodierung/11-struktur/`
(nie ins Repo, plan-vorverarbeitung-2026-11.md § 4).

Das Regelwerk steht unten als TOML-Entwurf (`ENTWURF`), so wie es in Stufe 2 ins Profil kommt: ein
Block je Stadt, kein Stadtwort im Code. Personennamen werden nie ausgegeben: vom Feld
„Dezernentin / Dezernent" und vom Unterzeichner bleibt nur die Amtsbezeichnung, die Spanne deckt nur
sie, und Beispielzeilen laufen durch `schwaerzen`.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import statistics
import sys
import tempfile
import time
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from georep.prep.bodies import organization_key
from georep.settings import load_settings

ROOT = Path(__file__).resolve().parents[2]
MESSDATEN = Path("/media/konrad/xtraspace/georep/messdaten")
ROHTEXT = MESSDATEN / "rohtext"
AUFGABEN_DIR = MESSDATEN / "kodierung" / "11-struktur"
VALIDIERUNG = ROOT / "validierung" / "11-struktur"
EXTRACTOR = "struktur-entwurf-1"
SEED = 20261123  # Tag der Messung; Stichprobe und Beispielzeilen hängen nur an ihm
STICHPROBE = 200
MINDESTENS_JE_SCHICHT = 8
MAX_ZEILEN_AUFGABE = 600  # längere Dokumente werden für die Kodierer gekürzt (Feld gekuerzt)
PROFILE_PAPERS = {
    "2014-2020": ROOT / "snapshots/2014-2020/raw/papers.jsonl",
    "2025": ROOT / "snapshots/2025/raw/papers.jsonl",
    "moenchengladbach": ROOT / "reference/moenchengladbach/raw/papers.jsonl",
}

# Entwurf der Profilblöcke für Stufe 2. Label -> Abschnittsart; Ebene 2 schließt keinen Abschnitt
# der Ebene 1 (die Kosten eines Ausführungsbeschlusses stehen im Beschlussvorschlag). „leads" sind
# Einleitungssätze, die mit Doppelpunkt enden und einen Abschnitt öffnen, dessen Text in der nächsten
# Zeile beginnt; „fallback" ist der Beschlusssatz einer Vorlage ohne Überschrift, er gehört selbst
# zum Abschnitt. Die Muster werden ohne Groß/Klein-Schalter gelesen, wo nicht (?i) davorsteht.
ENTWURF = r"""
[duesseldorf]
city = "Düsseldorf"
heading = '^[ \t]*(?P<label>[A-ZÄÖÜ][^:\n]{0,60}?)[ \t]*:[ \t]*(?P<rest>[^\n]*)$'
heading_nocolon = ''
nocolon_labels = []
betreff_after_form = false
lead_blocked_in = ["beschlusslage", "stellungnahme"]   # „… fasste folgenden Beschluss: … zu beschließen:" zitiert, schlägt nicht vor
level2 = ["finanzen", "klima"]
end_markers = ['^\s*(Mit\s+)?[Ff]reundliche[n]?\s+Grü(ß|ss)e', '^\s*[Gg]ez\.', '^\s*Sehr\s+geehrte']
betreff_max_lines = 4
art = [
  ['^Haushaltsantrag', 'Haushaltsantrag'],
  ['^Antrag', 'Antrag'],
  ['^z?Anfrage', 'Anfrage'],
  ['^(Bezirksvertretung )?Eingabe', 'Eingabe'],
  ['^Vorlage aus der Politik$', 'Vorlage aus der Politik'],
]
# Eingaben nach § 24 GO tragen nur zum Teil einen Beschlussvorschlag (Kurzdarstellung ohne ihn):
# sie stehen in keiner der beiden Listen und werden getrennt gezählt.
decision_expected = ["Beschlussvorlage", "Bezirksvertretung Beschlussvorlage", "A+F Beschluss",
  "Bedarfsbeschluss", "Beschlussvorlage RPA", "Antrag", "Haushaltsantrag"]
decision_not_expected = ["Informationsvorlage", "Bezirksvertretung Informationsvorlage", "Anfrage",
  "Berichtsvorlage"]

[duesseldorf.labels]
"Betrifft" = "betreff"
"Fachbereich" = "kopf_amt"
"Amt / Institut" = "kopf_amt"
"Amt" = "kopf_amt"
"Amtsleitung" = "kopf_amtsleitung"
"Dezernentin / Dezernent" = "kopf_dezernat"
"Beratungsfolge" = "kopf_beratungsfolge"
"Beschlussdarstellung" = "beschlussvorschlag"
"Beschlussvorschlag" = "beschlussvorschlag"
"Beschlussentwurf" = "beschlussvorschlag"
"Beschlussempfehlung" = "beschlussvorschlag"
"Antrag" = "beschlussvorschlag"
"Änderungsantrag" = "beschlussvorschlag"
"Ergänzungsantrag" = "beschlussvorschlag"
"Prüfantrag" = "beschlussvorschlag"
"Haushaltsantrag" = "beschlussvorschlag"
"Sachdarstellung" = "sachdarstellung"
"Sachdarstellung / Maßnahmenbeschreibung" = "sachdarstellung"
"Kurzdarstellung" = "sachdarstellung"
"Sachlage" = "sachdarstellung"
"Sachverhalt" = "sachdarstellung"
"Stellungnahme der Verwaltung" = "stellungnahme"
"Hierzu teilt die Verwaltung mit" = "stellungnahme"
"Begründung" = "begruendung"
"Alternative" = "alternative"
"Anfrage" = "fragen"
"Fragen" = "fragen"
"Beschluss" = "beschlusslage"
"Beschlusslage" = "beschlusslage"
"Anlagen" = "anlagen"
"Anlage" = "anlagen"
"Nachrichtlich" = "nachrichtlich"
"Finanzielle Auswirkungen" = "finanzen"
"Finanzierung" = "finanzen"
"Finanzierungsart" = "finanzen"
"Kosten" = "finanzen"
"Kosten und Finanzierung" = "finanzen"
"Gesamtkosten" = "finanzen"
"Gesamtkosten und Refinanzierung" = "finanzen"
"Finanzierung des Projektes" = "finanzen"
"Investive Kosten" = "finanzen"
"Konsumtive Kosten" = "finanzen"
"Klimarelevanz" = "klima"
"Auswirkungen auf den Klimaschutz" = "klima"
"Klimaschutz" = "klima"
"Klimaanpassung" = "klima"

[[duesseldorf.leads]]
kind = "beschlussvorschlag"
pattern = '(?i)\bbeschlie(ß|ss)(en|t)\b[^:]{0,40}:\s*$'
[[duesseldorf.leads]]
kind = "beschlussvorschlag"
pattern = '(?i)\bzur\s+Abstimmung\s+(zu\s+)?(bringen|stellen)\s*:\s*$'
[[duesseldorf.leads]]
kind = "beschlussvorschlag"
pattern = '(?i)\bfolgenden\s+\w*antrag\b[^:]{0,160}:\s*$'
[[duesseldorf.leads]]
kind = "beschlussvorschlag"
pattern = '(?i)\bbeantrag(t|en)\s*:\s*$'
[[duesseldorf.leads]]
kind = "fragen"
pattern = '(?i)(folgende[n]?\s+(\w+\s+)?Fragen|Fragen\b[^:]{0,60}\bbeantworten|beantworten(\s+zu\s+lassen)?|\bfrag(t|en)\s+an|um\s+(die\s+)?Beantwortung)[^:]{0,80}:\s*$'

[duesseldorf.fallback]
kind = "beschlussvorschlag"
pattern = '^\s*((Der|Die|Das)\s+)?[A-ZÄÖÜ][^\n]{0,120}?\b(beschließt|beschliesst|empfiehlt|beauftragt|genehmigt|bewilligt|stimmt|bittet|fordert|ersucht|möge|wird\s+gebeten|wird\s+beauftragt|wird\s+aufgefordert)\b'
max_lines_after_head = 12
only_expected = true            # nur für Arten mit erwartetem Beschlussvorschlag (sonst „Die Verwaltung wird gebeten, folgende Fragen …")

[duesseldorf.head]
consultation_header = 'Gremium\s+Sitzungsdatum(\s+Beratungsqualität)?'
quality = ["Entscheidung", "Kenntnisnahme", "Vorberatung", "Anhörung", "Empfehlung"]
quality_placeholders = ["-/-", "-"]   # Eingaben: „Anregungs- und Beschwerdeausschuss 01.02.2024 -"
quality_required = true
titles = '^\s*(Oberbürgermeister(in)?|Bürgermeister(in)?|Stadtdirektor(in)?|Stadtkämmer(er|in)|Beigeordnete[r]?)'
signer_roles = '(?i)\b(Fraktionsvorsitzende[r]?|Vorsitzende[r]?|Sprecher(in)?|Ratsherr|Ratsfrau|Ratsmitglied|Bezirksvertreter(in)?|Bürgermitglied|Geschäftsführer(in)?|Oberbürgermeister(in)?|Beigeordnete[r]?)\b'
signer_window = 8
session = '(?i)zur\s+Sitzung\s+(der|des)\s+(?P<gremium>[^\n]{3,120}?)\s+am\s+(?P<datum>\d{1,2}\.\s?(\d{1,2}\.|[A-Za-zäÄ]+)\s?\d{4})'
date_line = '^\s*{city},?\s*(den\s+)?(?P<datum>\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4})'
form_titles = ["Beschlussvorlage", "Informationsvorlage", "Bericht", "Berichtsvorlage",
  "Eingabe nach § 24 Gemeindeordnung NRW", "Antrag", "Anfrage"]
head_lines = 30

# Die Wahlperiode 2014 bis 2020 erbt alles und ändert nur, was ihr Vorlagenformular anders macht:
# die Beratungsfolge steht am Ende der ersten Seite und hat die Spalte „Ergebnis" statt
# „Beratungsqualität" (meist „-/-", weil das Ergebnis bei Drucklegung fehlt), und die Vorlagen aus
# der Politik tragen den Betreff ohne „Betrifft:" in den Zeilen unter dem Formulartitel.
[duesseldorf-2014]
base = "duesseldorf"
betreff_after_form = true
[duesseldorf-2014.head]
consultation_header = 'Gremium\s+Sitzungsdatum(\s+(Beratungsqualität|Ergebnis))?'
quality_required = false

[moenchengladbach]
city = "Mönchengladbach"
heading = '^[ \t]*(?P<label>[A-ZÄÖÜ][^:\n]{0,60}?)[ \t]*:[ \t]*(?P<rest>[^\n]*)$'
heading_nocolon = '^[ \t]*(?P<label>Fachbereich|Beratungsfolge)(?:[ \t]{2,}(?P<rest>[^\n]*)|[ \t]*)$'
nocolon_labels = ["Fachbereich", "Beratungsfolge"]
betreff_after_form = false
lead_blocked_in = []
level2 = []
end_markers = ['^\s*(Mit\s+)?[Ff]reundliche[n]?\s+Grü(ß|ss)e', '^\s*[Gg]ez\.', '^\s*Sehr\s+geehrte']
betreff_max_lines = 4
art = [
  ['Beratungsvorlage', 'Beratungsvorlage'],
  ['Berichtsvorlage', 'Berichtsvorlage'],
  ['Fraktionsantrag|Mitgliederantrag', 'Antrag'],
  ['Änderungsvorlage', 'Änderungsvorlage'],
]
decision_expected = ["Beratungsvorlage", "Antrag", "Änderungsvorlage"]
decision_not_expected = ["Berichtsvorlage"]

[moenchengladbach.labels]
"TOP" = "betreff"
"Beratungsgegenstand" = "betreff"
"Thema / Tagesordnungspunkt" = "betreff"
"Thema" = "betreff"
"Fachbereich" = "kopf_amt"
"Beteiligte Bereiche" = "kopf_beteiligt"
"Beratungsfolge" = "kopf_beratungsfolge"
"Beschlussentwurf" = "beschlussvorschlag"
"Zur Kenntnisnahme" = "kenntnisnahme"
"Begründung" = "begruendung"
"Finanzwirksamkeit" = "finanzen"
"Auswirkung auf die Kinder- und Familienfreundlichkeit" = "familie"
"Auswirkungen Kinder- und Familienfreundlichkeit" = "familie"
"Auswirkungen auf Klima und Umwelt" = "klima"
"Auswirkungen Klima und Umwelt" = "klima"
"Klimaauswirkungen" = "klima"
"Anlagen" = "anlagen"
"Anlage" = "anlagen"
"Anlage/n" = "anlagen"

[[moenchengladbach.leads]]
kind = "beschlussvorschlag"
pattern = '(?i)\bbeschlie(ß|ss)en\b[^:]{0,40}:\s*$'

[moenchengladbach.fallback]
kind = "beschlussvorschlag"
pattern = '^\s*(Der|Die|Das)\s[^\n]{0,120}?\b(beschließt|beschliesst|empfiehlt|beauftragt)\b'
max_lines_after_head = 12
only_expected = true

[moenchengladbach.head]
consultation_header = 'Gremium\s+Sitzungsdatum(\s+Beratungsqualität)?'
quality = []
quality_placeholders = []
quality_required = false
titles = '^\s*(Oberbürgermeister(in)?|Bürgermeister(in)?|Stadtdirektor(in)?|Stadtkämmer(er|in)|Beigeordnete[r]?)'
signer_roles = '(?i)\b(Fraktionsvorsitzende[r]?|Vorsitzende[r]?|Sprecher(in)?|Ratsherr|Ratsfrau|Ratsmitglied|Bezirksvertreter(in)?|Geschäftsführer(in)?|Oberbürgermeister(in)?|Beigeordnete[r]?|Stadtdirektor(in)?|Stadtkämmer(er|in))\b'
signer_window = 8
session = ''
date_line = '^\s*{city},?\s*(den\s+)?(?P<datum>\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4})'
form_titles = []
head_lines = 30
"""

MONATE = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}


# --------------------------------------------------------------------------------------------
# Regelwerk
# --------------------------------------------------------------------------------------------


def merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in over.items():
        out[key] = (
            merge(out[key], value)
            if isinstance(value, dict) and isinstance(out.get(key), dict)
            else value
        )
    return out


@dataclass(frozen=True)
class Lead:
    kind: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class Rules:
    """Ein Profilblock aus `ENTWURF`, kompiliert."""

    name: str
    city: str
    heading: re.Pattern[str]
    heading_nocolon: re.Pattern[str] | None
    labels: dict[str, str]
    level2: frozenset[str]
    lead_blocked_in: frozenset[str]
    leads: tuple[Lead, ...]
    end_markers: tuple[re.Pattern[str], ...]
    betreff_max_lines: int
    fallback_kind: str
    fallback: re.Pattern[str]
    fallback_lines: int
    fallback_only_expected: bool
    betreff_after_form: bool
    art_rules: tuple[tuple[re.Pattern[str], str], ...]
    decision_expected: frozenset[str]
    decision_not_expected: frozenset[str]
    consultation_header: re.Pattern[str]
    consultation_row: re.Pattern[str]
    quality_required: bool
    quality_placeholders: frozenset[str]
    titles: re.Pattern[str]
    signer_roles: re.Pattern[str]
    signer_window: int
    session: re.Pattern[str] | None
    date_line: re.Pattern[str]
    form_titles: frozenset[str]
    head_lines: int

    @classmethod
    def load(cls, name: str) -> Rules:
        blocks: dict[str, Any] = tomllib.loads(ENTWURF)
        block: dict[str, Any] = blocks[name]
        while "base" in block:  # wie die Periodenprofile: der Block überschreibt seine Basis
            child = {k: v for k, v in block.items() if k != "base"}
            block = merge(blocks[block["base"]], child)
        head = block["head"]
        quality = "|".join(re.escape(q) for q in [*head["quality"], *head["quality_placeholders"]])
        tail = (
            rf"\s+(?P<qualitaet>{quality})"
            if head["quality_required"]
            else rf"(\s+(?P<qualitaet>{quality}))?"
        )
        if not quality:
            tail = ""
        row = re.compile(
            r"(?P<gremium>[^\s\d].{0,150}?)\s+(?P<datum>\d{2}\.\d{2}\.\d{4})" + tail, re.S
        )
        return cls(
            name=name,
            city=block["city"],
            heading=re.compile(block["heading"]),
            heading_nocolon=re.compile(block["heading_nocolon"])
            if block["heading_nocolon"]
            else None,
            labels=dict(block["labels"]),
            level2=frozenset(block["level2"]),
            lead_blocked_in=frozenset(block["lead_blocked_in"]),
            leads=tuple(Lead(lead["kind"], re.compile(lead["pattern"])) for lead in block["leads"]),
            end_markers=tuple(re.compile(p) for p in block["end_markers"]),
            betreff_max_lines=int(block["betreff_max_lines"]),
            fallback_kind=block["fallback"]["kind"],
            fallback=re.compile(block["fallback"]["pattern"]),
            fallback_lines=int(block["fallback"]["max_lines_after_head"]),
            fallback_only_expected=bool(block["fallback"]["only_expected"]),
            betreff_after_form=bool(block["betreff_after_form"]),
            art_rules=tuple((re.compile(p), a) for p, a in block["art"]),
            decision_expected=frozenset(block["decision_expected"]),
            decision_not_expected=frozenset(block["decision_not_expected"]),
            consultation_header=re.compile(head["consultation_header"]),
            consultation_row=row,
            quality_required=bool(head["quality_required"]),
            quality_placeholders=frozenset(head["quality_placeholders"]),
            titles=re.compile(head["titles"]),
            signer_roles=re.compile(head["signer_roles"]),
            signer_window=int(head["signer_window"]),
            session=re.compile(head["session"]) if head["session"] else None,
            date_line=re.compile(head["date_line"].replace("{city}", re.escape(block["city"]))),
            form_titles=frozenset(head["form_titles"]),
            head_lines=int(head["head_lines"]),
        )

    def art(self, paper_type: str) -> str:
        for pattern, art in self.art_rules:
            if pattern.search(paper_type):
                return art
        return paper_type


@dataclass(frozen=True)
class Span:
    """F3: eine Stelle im Rohtext. `0 <= start < end <= len(text)`."""

    id: str
    start: int
    end: int
    kind: str
    value: str
    norm: str
    section: str
    extractor: str = EXTRACTOR


@dataclass
class Event:
    line: int
    typ: str  # heading, lead, end
    kind: str
    label: str
    content: int  # Zeichenposition, an der der Abschnittstext beginnt
    source: str  # ueberschrift, einleitung, beschlusssatz


@dataclass
class Result:
    sections: list[Span] = field(default_factory=list)
    head: list[Span] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)  # Abschnittsart -> erste Quelle
    lines: list[tuple[int, int]] = field(default_factory=list)


def split_lines(text: str) -> list[tuple[int, int]]:
    """(Anfang, Ende) jeder Zeile; Zeilenumbruch und Seitenwechsel trennen, das Ende ohne Trenner."""
    out: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"[\n\f]", text):
        out.append((start, match.start()))
        start = match.end()
    out.append((start, len(text)))
    return out


def norm_ws(value: str) -> str:
    value = re.sub(r"-\s*\n\s*(?=[a-zäöüß])", "", value)  # Trennstrich am Zeilenende
    return re.sub(r"\s+", " ", value).strip()


def trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def find_events(text: str, lines: Sequence[tuple[int, int]], rules: Rules) -> list[Event]:
    events: list[Event] = []
    for i, (s, e) in enumerate(lines):
        line = text[s:e]
        nxt = lines[i + 1][0] if i + 1 < len(lines) else e
        match = rules.heading.match(line)
        label = norm_ws(match.group("label")) if match else ""
        if match is None or label not in rules.labels:
            match = rules.heading_nocolon.match(line) if rules.heading_nocolon else None
            label = norm_ws(match.group("label")) if match else ""
        if match is not None and label in rules.labels:
            rest = match.group("rest") or ""
            content = s + match.start("rest") if rest.strip() else nxt
            events.append(Event(i, "heading", rules.labels[label], label, content, "ueberschrift"))
            continue
        if line.rstrip().endswith(":"):
            window = " ".join(text[a:b] for a, b in lines[max(0, i - 2) : i + 1])
            lead = next((lead for lead in rules.leads if lead.pattern.search(window)), None)
            if lead is not None:
                events.append(Event(i, "lead", lead.kind, line.strip(), nxt, "einleitung"))
                continue
        if any(marker.match(line) for marker in rules.end_markers):
            events.append(Event(i, "end", "", line.strip(), e, ""))
    return events


def cut_betreff(text: str, start: int, end: int, rules: Rules) -> int:
    """Der Betreff endet an der ersten Leerzeile nach Text oder nach `betreff_max_lines` Zeilen."""
    seen = 0
    pos = start
    for raw in re.finditer(r"[^\n\f]*(?:[\n\f]|$)", text[start:end]):
        chunk = raw.group(0)
        if not chunk:
            break
        if chunk.strip():
            seen += 1
            pos = start + raw.start() + len(chunk.rstrip("\n\f"))
            if seen >= rules.betreff_max_lines:
                return pos
        elif seen:
            return pos
    return end


def analyse(doc_id: str, text: str, rules: Rules, paper_type: str = "") -> Result:
    result = Result(lines=split_lines(text))
    lines = result.lines
    events = find_events(text, lines, rules)
    open1: Event | None = None
    open2: Event | None = None

    def close(event: Event | None, end: int) -> None:
        if event is None:
            return
        start, stop = trim(text, event.content, end)
        if event.kind == "betreff":
            stop = trim(text, start, cut_betreff(text, start, stop, rules))[1]
            for a, b in lines:  # ein Beschlusssatz direkt unter dem Betreff gehört nicht mehr dazu
                if start < a < stop and rules.fallback.match(text[a:b]):
                    stop = trim(text, start, a)[1]
                    break
        if stop > start:
            result.sections.append(
                Span(doc_id, start, stop, "abschnitt", event.label, event.kind, event.kind)
            )
            result.sources.setdefault(event.kind, event.source)

    for event in events:
        pos = lines[event.line][0]
        if event.typ == "end":
            close(open2, pos)
            close(open1, pos)
            open1 = open2 = None
        elif (
            event.typ == "lead"
            and open1 is not None
            and (open1.kind == event.kind or open1.kind in rules.lead_blocked_in)
        ):
            continue
        elif event.kind in rules.level2:
            close(open2, pos)
            open2 = event
        else:
            close(open2, pos)
            close(open1, pos)
            open2 = None
            open1 = event
    close(open2, len(text))
    close(open1, len(text))

    allowed = not rules.fallback_only_expected or rules.art(paper_type) in rules.decision_expected
    if allowed and not any(span.norm == rules.fallback_kind for span in result.sections):
        add_fallback(doc_id, text, rules, result, events)
    if rules.betreff_after_form and not any(span.norm == "betreff" for span in result.sections):
        add_betreff_after_form(doc_id, text, rules, result)
    result.sections.sort(key=lambda span: (span.start, span.end))
    result.head = head_fields(doc_id, text, rules, result)
    return result


def add_betreff_after_form(doc_id: str, text: str, rules: Rules, result: Result) -> None:
    """Periode 2014–2020: der Betreff steht ohne Label in den Zeilen unter dem Formulartitel."""
    lines = result.lines
    for i, (s, e) in enumerate(lines[: rules.head_lines]):
        if norm_ws(text[s:e]) in rules.form_titles:
            body = [(a, b) for a, b in lines[i + 1 : i + 1 + 12]]
            first = next((k for k, (a, b) in enumerate(body) if text[a:b].strip()), None)
            if first is None:
                return
            stop_k = first
            for k in range(first, min(len(body), first + rules.betreff_max_lines)):
                a, b = body[k]
                if not text[a:b].strip() or rules.fallback.match(text[a:b]):
                    break
                stop_k = k
            start, stop = trim(text, body[first][0], body[stop_k][1])
            if stop > start:
                result.sections.append(
                    Span(doc_id, start, stop, "abschnitt", "", "betreff", "betreff")
                )
                result.sources.setdefault("betreff", "formular")
            return


def add_fallback(
    doc_id: str, text: str, rules: Rules, result: Result, events: Sequence[Event]
) -> None:
    """Beschlusssatz ohne Überschrift: die ersten Zeilen nach dem Kopf, bis zur nächsten Überschrift."""
    head_kinds = {"betreff", "kopf_amt", "kopf_amtsleitung", "kopf_dezernat", "kopf_beratungsfolge"}
    head_events = [e for e in events if e.typ == "heading" and e.kind in head_kinds]
    if not head_events:
        return
    last = head_events[-1]
    after = [
        e for e in events if e.line > last.line and e.typ != "end" and e.kind not in rules.level2
    ]
    stop_line = after[0].line if after else len(result.lines)
    first_line = last.line + 1
    if last.kind == "kopf_beratungsfolge":
        # die Tabellenzeilen der Beratungsfolge überspringen
        rows = [s for s in result.sections if s.norm == "kopf_beratungsfolge"]
        if rows:
            end_pos = rows[-1].end
            first_line = next(
                (i for i, (s, _e) in enumerate(result.lines) if s >= end_pos), len(result.lines)
            )
    for i in range(first_line, min(stop_line, first_line + rules.fallback_lines)):
        s, e = result.lines[i]
        if rules.fallback.match(text[s:e]):
            ends = [ev for ev in events if ev.line > i and ev.kind not in rules.level2]
            stop = result.lines[ends[0].line][0] if ends else len(text)
            start, stop = trim(text, s, stop)
            if stop > start:
                kind = rules.fallback_kind
                label = norm_ws(text[s:e])[:40]
                result.sections.append(Span(doc_id, start, stop, "abschnitt", label, kind, kind))
                result.sources.setdefault(kind, "beschlusssatz")
            return


def parse_date(value: str) -> str:
    value = value.strip()
    numeric = re.fullmatch(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{2,4})", value)
    named = re.fullmatch(r"(\d{1,2})\.\s?([A-Za-zäÄ]+)\s?(\d{4})", value)
    try:
        if numeric:
            year = int(numeric.group(3))
            year = year + 2000 if year < 100 else year
            return date(year, int(numeric.group(2)), int(numeric.group(1))).isoformat()
        if named and named.group(2).lower() in MONATE:
            month = MONATE[named.group(2).lower()]
            return date(int(named.group(3)), month, int(named.group(1))).isoformat()
    except ValueError:
        return ""
    return ""


def head_fields(doc_id: str, text: str, rules: Rules, result: Result) -> list[Span]:
    spans: list[Span] = []
    by_kind: dict[str, list[Span]] = defaultdict(list)
    for span in result.sections:
        by_kind[span.norm].append(span)
    if by_kind["kopf_amt"]:
        span = by_kind["kopf_amt"][0]
        value = norm_ws(text[span.start : span.end])
        if 0 < len(value) <= 150:
            match = re.match(r"(?P<nr>\d{2}(?:/\d{1,3})?)\s*-?\s*(?P<name>.*)$", value)
            norm = f"{match.group('nr')} {match.group('name')}".strip() if match else value
            spans.append(Span(doc_id, span.start, span.end, "amt", value, norm, "kopf"))
    if by_kind["kopf_dezernat"]:
        span = by_kind["kopf_dezernat"][0]
        match = rules.titles.match(text[span.start : span.end])
        if match:
            # nur die Amtsbezeichnung; der Name dahinter wird nie gelesen
            start, stop = trim(text, span.start + match.start(), span.start + match.end())
            title = text[start:stop]
            spans.append(Span(doc_id, start, stop, "dezernat", title, title, "kopf"))
        else:
            spans.append(Span(doc_id, span.start, span.start + 1, "dezernat", "", "", "kopf"))
    if by_kind["kopf_beratungsfolge"]:
        block = by_kind["kopf_beratungsfolge"][0]
        header = rules.consultation_header.search(text, block.start, block.end)
        pos = header.end() if header else block.start
        for row in rules.consultation_row.finditer(text, pos, block.end):
            gremium = norm_ws(row.group("gremium"))
            if len(gremium) > 150 or re.search(r"\d{2}\.\d{2}\.\d{4}", gremium):
                continue
            quality = row.groupdict().get("qualitaet") or ""
            quality = "" if quality in rules.quality_placeholders else quality
            norm = f"{gremium}|{parse_date(row.group('datum'))}|{quality}"
            start, stop = trim(text, row.start(), row.end())
            spans.append(
                Span(doc_id, start, stop, "beratung", norm_ws(text[start:stop]), norm, "kopf")
            )
    top = result.lines[: rules.head_lines]
    head_end = top[-1][1] if top else 0
    if rules.session is not None:
        match = rules.session.search(text, 0, head_end)
        if match:
            norm = f"{norm_ws(match.group('gremium'))}|{parse_date(match.group('datum'))}"
            spans.append(
                Span(
                    doc_id,
                    match.start(),
                    match.end(),
                    "sitzung",
                    norm_ws(match.group(0)),
                    norm,
                    "kopf",
                )
            )
    for s, e in top:
        match = rules.date_line.match(text[s:e])
        if match:
            value = match.group("datum")
            spans.append(
                Span(
                    doc_id,
                    s + match.start("datum"),
                    s + match.end("datum"),
                    "datum",
                    value,
                    parse_date(value),
                    "kopf",
                )
            )
            break
    for s, e in top:
        if norm_ws(text[s:e]) in rules.form_titles:
            start, stop = trim(text, s, e)
            spans.append(
                Span(doc_id, start, stop, "formular", text[start:stop], norm_ws(text[s:e]), "kopf")
            )
            break
    signer = signer_role(text, rules, result.lines)
    if signer is not None:
        spans.append(
            Span(doc_id, signer[0], signer[1], "unterzeichner", signer[2], signer[2], "kopf")
        )
    spans.sort(key=lambda span: (span.start, span.end))
    return spans


def signer_role(
    text: str, rules: Rules, lines: Sequence[tuple[int, int]]
) -> tuple[int, int, str] | None:
    """Amtsbezeichnung im Unterschriftsblock; Namen werden übergangen, nie gespeichert."""
    closing = re.compile(r"^\s*((Mit\s+)?[Ff]reundliche[n]?\s+Grü(ß|ss)e|[Gg]ez\.)")
    for i, (s, e) in enumerate(lines):
        if closing.match(text[s:e]):
            for a, b in lines[i : i + rules.signer_window]:
                match = rules.signer_roles.search(text[a:b])
                if match:
                    role = match.group(0)
                    return a + match.start(), a + match.end(), role[0].upper() + role[1:]
            return None
    return None


def check_contract(text: str, spans: Iterable[Span]) -> None:
    for span in spans:
        assert 0 <= span.start < span.end <= len(text), span


# --------------------------------------------------------------------------------------------
# Daten
# --------------------------------------------------------------------------------------------


def load_profile(profile: str) -> pl.DataFrame:
    """Korpus mit Rohtext: id, reference, date, paper_type, file_name, text, pages, chars."""
    if profile == "duesseldorf":
        settings = load_settings(cwd=ROOT, profile="duesseldorf")
        corpus = Path(settings.data_root) / "duesseldorf" / "interim" / "papers.parquet"
        papers = pl.read_parquet(corpus).select(
            "id", "reference", "date", "paper_type", "file_name"
        )
    else:
        papers = (
            pl.read_ndjson(PROFILE_PAPERS[profile], infer_schema_length=None)
            .select("id", "reference", "date", "paper_type", "file_name")
            .with_columns(pl.col("date").str.to_date(strict=False))
        )
    raw = pl.read_parquet(ROHTEXT / f"{profile}.parquet").select("name", "text", "pages", "chars")
    joined = papers.join(raw, left_on="file_name", right_on="name", how="inner")
    return joined.with_columns(
        pl.col("text").fill_null(""), pl.col("paper_type").fill_null("")
    ).sort("id")


def wilson(part: int, whole: int, z: float = 1.959964) -> str:
    """95-%-Intervall nach Wilson, in Prozent."""
    if not whole:
        return "–"
    p = part / whole
    d = 1 + z * z / whole
    c = p + z * z / (2 * whole)
    h = z * ((p * (1 - p) / whole + z * z / (4 * whole * whole)) ** 0.5)
    return f"{100 * (c - h) / d:.1f}–{100 * (c + h) / d:.1f} %"


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:5.1f} %" if whole else "    – "


def schwaerzen(line: str) -> str:
    """Personennamen hinter Anrede, Titel oder gez. durch ‹Name› ersetzen (für Beispielzeilen).

    Grob und absichtlich zu streng: eine Anredezeile wird ganz ersetzt, Initialen mit Nachnamen
    ebenso. Was ins Messdokument kommt, wird trotzdem von Hand gelesen.
    """
    if re.match(r"\s*(Sehr\s+geehrte|[Gg]ez\.|Mit\s+freundlichen)", line):
        return re.match(r"\s*(\S+(\s+geehrte)?)", line).group(1) + " ‹…›"  # type: ignore[union-attr]
    line = re.sub(r"\b[A-ZÄÖÜ]\.\s?[A-ZÄÖÜ][a-zäöüß\-]+", "‹Name›", line)
    line = re.sub(
        r"\b(Herrn?|Frau|[Gg]ez\.|Dr\.|Prof\.)(\s+(Dr\.|Prof\.))*\s+[A-ZÄÖÜ][\w\-]+(\s+[A-ZÄÖÜ][\w\-]+)?",
        r"\1 ‹Name›",
        line,
    )
    return line[:110]


# --------------------------------------------------------------------------------------------
# Messungen
# --------------------------------------------------------------------------------------------

KINDS = [
    "betreff",
    "beschlussvorschlag",
    "sachdarstellung",
    "begruendung",
    "fragen",
    "stellungnahme",
    "beschlusslage",
    "alternative",
    "kenntnisnahme",
    "finanzen",
    "klima",
    "familie",
    "anlagen",
]
HEAD = ["amt", "dezernat", "beratung", "sitzung", "datum", "formular", "unterzeichner"]


def heading_catalog(
    frame: pl.DataFrame, rules: Rules, minimum: float = 0.02, top: int = 14
) -> None:
    """§ 3.1: Zeilen der Form „Label:" je Art, Anteil der Dokumente."""
    pattern = re.compile(r"^\s*([A-ZÄÖÜ][^:\n]{0,60}?)\s*:\s*(.*)$", re.M)
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    sizes: Counter[str] = Counter()
    for paper_type, text in frame.select("paper_type", "text").iter_rows():
        art = rules.art(paper_type)
        sizes[art] += 1
        counts[art].update(
            {norm_ws(m.group(1)) for m in pattern.finditer(text.replace("\f", "\n"))}
        )
    for art, size in sizes.most_common():
        shown = [
            f"{label} {100 * c / size:.0f}"
            for label, c in sorted(counts[art].items(), key=lambda kv: (-kv[1], kv[0]))[:top]
            if c / size >= minimum
        ]
        print(f"  {art} ({size}): " + "; ".join(schwaerzen(s) for s in shown))


def coverage(
    frame: pl.DataFrame,
    rules: Rules,
    results: dict[str, Result],
    kinds: Sequence[str],
    head: Sequence[str],
) -> None:
    sizes: Counter[str] = Counter()
    found: dict[str, Counter[str]] = defaultdict(Counter)
    for doc_id, paper_type in frame.select("id", "paper_type").iter_rows():
        art = rules.art(paper_type)
        sizes[art] += 1
        result = results[doc_id]
        found[art].update({s.norm for s in result.sections})
        found[art].update({s.kind for s in result.head if s.value})
    cols = [k for k in kinds if any(found[a][k] for a in sizes)] + [
        h for h in head if any(found[a][h] for a in sizes)
    ]
    print("  " + " | ".join(["Art", "n", *cols]))
    total: Counter[str] = Counter()
    for art, size in sizes.most_common():
        total.update(found[art])
        print(
            "  " + " | ".join([art, str(size), *(pct(found[art][c], size).strip() for c in cols)])
        )
    n = sum(sizes.values())
    print("  " + " | ".join(["alle", str(n), *(pct(total[c], n).strip() for c in cols)]))


def decision_stats(
    frame: pl.DataFrame, rules: Rules, results: dict[str, Result], show: int = 0
) -> dict[str, float]:
    """§ 3.3: Beschlussvorschlag dort, wo die Art einen erwarten lässt, und dort, wo nicht."""
    sizes: Counter[str] = Counter()
    hits: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    lengths: list[int] = []
    multi = 0
    long = 0
    misses: list[tuple[str, str]] = []
    empty = 0
    hollow = (
        0  # nach dem Kopf weniger als 80 Zeichen: der Rumpf steckt im Bild oder in Formularfeldern
    )
    for doc_id, ref, paper_type, text in frame.select(
        "id", "reference", "paper_type", "text"
    ).iter_rows():
        art = rules.art(paper_type)
        if not text.strip():
            empty += 1
            continue
        sizes[art] += 1
        spans = [s for s in results[doc_id].sections if s.norm == "beschlussvorschlag"]
        if spans:
            hits[art] += 1
            if art in rules.decision_expected:
                sources[results[doc_id].sources["beschlussvorschlag"]] += 1
                lengths.append(spans[0].end - spans[0].start)
                multi += len(spans) > 1
                long += spans[0].end - spans[0].start > 4000
        elif art in rules.decision_expected:
            misses.append((doc_id, ref))
            result = results[doc_id]
            head_end = max(
                (
                    s.end
                    for s in result.sections
                    if s.norm.startswith("kopf") or s.norm == "betreff"
                ),
                default=0,
            )
            body = re.sub(r"Seite \d+|\s", "", text[head_end:])
            hollow += len(body) < 80
    exp_n = sum(sizes[a] for a in rules.decision_expected)
    exp_h = sum(hits[a] for a in rules.decision_expected)
    not_n = sum(sizes[a] for a in rules.decision_not_expected)
    not_h = sum(hits[a] for a in rules.decision_not_expected)
    print(f"  ohne Rohtext (nicht gezählt): {empty}")
    print(
        f"  erwartet: {exp_h} von {exp_n} gefunden ({pct(exp_h, exp_n).strip()}, {wilson(exp_h, exp_n)})"
    )
    print(
        f"  von den {exp_n - exp_h} ohne Fund: nach dem Kopf unter 80 Zeichen Text {hollow}, "
        f"die Regel findet nichts {exp_n - exp_h - hollow}; ohne die ersten: {exp_h} von {exp_n - hollow} "
        f"({pct(exp_h, exp_n - hollow).strip()})"
    )
    for art in sorted(rules.decision_expected, key=lambda a: -sizes[a]):
        if sizes[art]:
            print(f"    {art}: {hits[art]} von {sizes[art]} ({pct(hits[art], sizes[art]).strip()})")
    print(
        f"  nicht erwartet: {not_h} von {not_n} mit Beschlussvorschlag ({pct(not_h, not_n).strip()}, {wilson(not_h, not_n)})"
    )
    for art in sorted(rules.decision_not_expected, key=lambda a: -sizes[a]):
        if sizes[art]:
            print(f"    {art}: {hits[art]} von {sizes[art]} ({pct(hits[art], sizes[art]).strip()})")
    rest = [
        a
        for a in sizes
        if a not in rules.decision_expected and a not in rules.decision_not_expected
    ]
    for art in sorted(rest, key=lambda a: -sizes[a]):
        print(
            f"  weder noch: {art}: {hits[art]} von {sizes[art]} ({pct(hits[art], sizes[art]).strip()})"
        )
    if lengths:
        print(
            "  Quelle (erwartete Arten): "
            + ", ".join(f"{k} {v} ({pct(v, exp_h).strip()})" for k, v in sources.most_common())
        )
        q = statistics.quantiles(lengths, n=10)
        print(
            f"  Länge in Zeichen: Median {statistics.median(lengths):.0f}, 10 % {q[0]:.0f}, 90 % {q[-1]:.0f}; "
            f"über 4000 Zeichen {long} ({pct(long, exp_h).strip()}); mehr als eine Spanne {multi} ({pct(multi, exp_h).strip()})"
        )
    if show and misses:
        rng = random.Random(SEED)
        texts = dict(frame.select("id", "text").iter_rows())
        print(
            f"  Beispiele ohne Beschlussvorschlag (Seed {SEED}), je die ersten Zeilen nach dem Kopf:"
        )
        for doc_id, ref in sorted(rng.sample(misses, min(show, len(misses)))):
            result = results[doc_id]
            text = texts[doc_id]
            head_end = max(
                (
                    s.end
                    for s in result.sections
                    if s.norm.startswith("kopf") or s.norm == "betreff"
                ),
                default=0,
            )
            body = [
                text[s:e].strip() for s, e in result.lines if s >= head_end and text[s:e].strip()
            ]
            print(f"    {ref}: " + " ⏎ ".join(schwaerzen(b) for b in body[:3]))
    return {
        "expected": exp_h / exp_n if exp_n else float("nan"),
        "not_expected": not_h / not_n if not_n else float("nan"),
    }


def head_stats(frame: pl.DataFrame, rules: Rules, results: dict[str, Result]) -> None:
    """§ 3.4: Kopf: Beratungsqualität, Gremien, Titel, Datum gegen das Dokumentdatum."""
    quality: Counter[str] = Counter()
    titles: Counter[str] = Counter()
    untitled = 0
    roles: Counter[str] = Counter()
    rows_per_doc: Counter[int] = Counter()
    lag_ok = lag_n = 0
    dates = dict(frame.select("id", "date").iter_rows())
    signer_docs = 0
    closing = re.compile(r"(?m)^\s*((Mit\s+)?[Ff]reundliche[n]?\s+Grü(ß|ss)e|[Gg]ez\.)")
    texts = dict(frame.select("id", "text").iter_rows())
    for doc_id in frame["id"]:
        rows = [s for s in results[doc_id].head if s.kind == "beratung"]
        rows_per_doc[len(rows)] += 1
        for row in rows:
            gremium, datum, qual = row.norm.split("|")
            quality[qual or "(ohne)"] += 1
            paper_date = dates[doc_id]
            if datum and paper_date is not None:
                lag_n += 1
                lag = (date.fromisoformat(datum) - paper_date).days
                lag_ok += -14 <= lag <= 400
        for span in results[doc_id].head:
            if span.kind == "dezernat":
                if span.value:
                    titles[span.value] += 1
                else:
                    untitled += 1
            if span.kind == "unterzeichner":
                roles[span.value] += 1
        signer_docs += bool(closing.search(texts[doc_id]))
    print(
        "  Beratungsqualität je Zeile: " + ", ".join(f"{k} {v}" for k, v in quality.most_common())
    )
    print(
        "  Zeilen der Beratungsfolge je Dokument: "
        + ", ".join(f"{k}: {v}" for k, v in sorted(rows_per_doc.items()))
    )
    print(
        f"  Sitzungsdatum 14 Tage vor bis 400 Tage nach dem Dokumentdatum: {lag_ok} von {lag_n} ({pct(lag_ok, lag_n).strip()}, {wilson(lag_ok, lag_n)})"
    )
    print(
        "  Amtsbezeichnung im Feld Dezernent: "
        + ", ".join(f"{k} {v}" for k, v in titles.most_common())
        + f"; ohne erkannte Bezeichnung {untitled}"
    )
    print(
        f"  Dokumente mit Grußformel oder gez.: {signer_docs}; Amtsbezeichnung im Unterschriftsblock: {sum(roles.values())} ({pct(sum(roles.values()), signer_docs).strip()}): "
        + ", ".join(f"{k} {v}" for k, v in roles.most_common(8))
    )


def oparl_check(frame: pl.DataFrame, results: dict[str, Result]) -> None:
    """§ 4.1: Gremien des Kopfs gegen die Beratungsfolge aus OParl (Labels aus den Daten selbst)."""
    settings = load_settings(cwd=ROOT, profile="duesseldorf")
    bodies = settings.bodies
    consult = pl.read_parquet(
        Path(settings.data_root) / "duesseldorf" / "raw" / "beratungsfolge.parquet"
    )
    codes_of: dict[str, set[str]] = {}
    for doc_id, orgs in consult.select("id", "consultation_organizations").iter_rows():
        codes_of[doc_id] = {
            bodies.organizations[k]
            for k in (organization_key(o) for o in orgs)
            if k in bodies.organizations
        }
    names: dict[str, str] = {}
    for table in (bodies.council, bodies.committees, bodies.advisory):
        names.update({name: code for code, name in table.items() if name})
    for code in set(bodies.organizations.values()):
        match = re.fullmatch(re.escape(bodies.district_body) + r"(\d+)", code)
        if match:
            names[bodies.district_body_name.format(n=match.group(1))] = code
    rows = known = hit = 0
    docs = docs_all = 0
    recall_n = recall_hit = 0
    pairs: dict[str, Counter[str]] = defaultdict(Counter)
    for doc_id in frame["id"]:
        head_rows = [s.norm.split("|")[0] for s in results[doc_id].head if s.kind == "beratung"]
        oparl = codes_of.get(doc_id)
        if not head_rows or not oparl:
            continue
        docs += 1
        mapped = {names[g] for g in head_rows if g in names}
        ok = True
        for gremium in head_rows:
            rows += 1
            if gremium in names:
                known += 1
                hit += names[gremium] in oparl
                ok &= names[gremium] in oparl
        docs_all += ok
        for code in oparl:
            if code in names.values():
                recall_n += 1
                recall_hit += code in mapped
        if len(set(head_rows)) == 1 and len(oparl) == 1:
            pairs[head_rows[0]][next(iter(oparl))] += 1
    print(f"  Dokumente mit Kopfzeilen und OParl-Beratungsfolge: {docs}")
    print(
        f"  Kopfzeilen: {rows}, davon Gremiumsname im Profil: {known} ({pct(known, rows).strip()})"
    )
    print(
        f"  davon Kürzel in der OParl-Beratungsfolge des Dokuments: {hit} ({pct(hit, known).strip()}, {wilson(hit, known)}) — Präzision des Gremiums, untere Schranke"
    )
    print(
        f"  Dokumente, in denen jede zuordenbare Kopfzeile in OParl steht: {docs_all} ({pct(docs_all, docs).strip()})"
    )
    print(
        f"  OParl-Gremien mit Namen im Profil, die im Kopf stehen: {recall_hit} von {recall_n} ({pct(recall_hit, recall_n).strip()})"
    )
    unnamed = {code for table in (bodies.committees,) for code, name in table.items() if not name}
    print(
        "  Vorschlag für Namen ohne Eintrag im Profil (eine Kopfzeile, ein OParl-Gremium; Mehrheit, mindestens 10):"
    )
    for gremium, counter in sorted(pairs.items(), key=lambda kv: -sum(kv[1].values())):
        code, n = counter.most_common(1)[0]
        total = sum(counter.values())
        if code in unnamed and n >= 10:
            print(f"    {code} = {gremium!r}  ({n} von {total})")


def output_sizes(frame: pl.DataFrame, results: dict[str, Result]) -> None:
    """§ 6: Größe der beiden Ausgaben von Stufe 2 als Parquet (zstd), in ein Wegwerfverzeichnis."""
    spans = [
        s for doc_id in frame["id"] for s in [*results[doc_id].sections, *results[doc_id].head]
    ]
    table = pl.DataFrame(
        {
            "id": [s.id for s in spans],
            "start": [s.start for s in spans],
            "end": [s.end for s in spans],
            "kind": [s.kind for s in spans],
            "value": [s.value for s in spans],
            "norm": [s.norm for s in spans],
            "section": [s.section for s in spans],
            "extractor": [s.extractor for s in spans],
        },
        schema_overrides={"start": pl.UInt32, "end": pl.UInt32},
    ).sort("id", "start")
    head = table.filter(pl.col("section") == "kopf")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "abschnitte.parquet"
        table.write_parquet(path, compression="zstd")
        size_spans = path.stat().st_size
        head_path = Path(tmp) / "kopf.csv"
        head.drop("start", "end", "extractor").write_csv(head_path)
        size_csv = head_path.stat().st_size
    print(f"  Spannen: {table.height} Zeilen, als Parquet (zstd) {size_spans / 1e6:.1f} MB")
    print(f"  davon Kopf: {head.height} Zeilen, als CSV ohne Offsets {size_csv / 1e6:.1f} MB")


def run_rules(frame: pl.DataFrame, rules: Rules) -> dict[str, Result]:
    out: dict[str, Result] = {}
    for doc_id, text, paper_type in frame.select("id", "text", "paper_type").iter_rows():
        result = analyse(doc_id, text, rules, paper_type)
        check_contract(text, [*result.sections, *result.head])
        out[doc_id] = result
    return out


Cache = dict[tuple[str, str], dict[str, Result]]


def transfer(
    profiles: Sequence[str],
    frames: dict[str, pl.DataFrame],
    rule_sets: dict[str, list[Rules]],
    cache: Cache,
) -> None:
    """§ 3.6: dasselbe Regelwerk auf den anderen Profilen."""
    cols = [
        "betreff",
        "beschlussvorschlag (erwartet)",
        "beschlussvorschlag (nicht erwartet)",
        "amt",
        "beratung",
        "qualität",
        "finanzen",
        "klima",
    ]
    print("  " + " | ".join(["Profil", "Regeln", "n", *cols]))
    for profile in profiles:
        frame = frames[profile]
        for rules in rule_sets[profile]:
            t0 = time.perf_counter()
            if (profile, rules.name) not in cache:
                cache[profile, rules.name] = run_rules(frame, rules)
            done = cache[profile, rules.name]
            n = 0
            c: Counter[str] = Counter()
            exp_n = not_n = 0
            for doc_id, paper_type in frame.select("id", "paper_type").iter_rows():
                n += 1
                result = done[doc_id]
                norms = {s.norm for s in result.sections}
                kinds = {s.kind for s in result.head if s.value}
                art = rules.art(paper_type)
                c["betreff"] += "betreff" in norms
                if art in rules.decision_expected:
                    exp_n += 1
                    c["beschlussvorschlag (erwartet)"] += "beschlussvorschlag" in norms
                elif art in rules.decision_not_expected:
                    not_n += 1
                    c["beschlussvorschlag (nicht erwartet)"] += "beschlussvorschlag" in norms
                c["amt"] += "amt" in kinds
                c["beratung"] += "beratung" in kinds
                c["qualität"] += any(
                    s.kind == "beratung" and s.norm.split("|")[2] for s in result.head
                )
                c["finanzen"] += "finanzen" in norms
                c["klima"] += "klima" in norms
            denom = {
                "beschlussvorschlag (erwartet)": exp_n,
                "beschlussvorschlag (nicht erwartet)": not_n,
            }
            cells = [
                pct(c[k], denom.get(k, n)).strip() + (f" von {denom[k]}" if k in denom else "")
                for k in cols
            ]
            print(
                "  "
                + " | ".join([profile, rules.name, str(n), *cells])
                + f"  ({time.perf_counter() - t0:.1f} s)"
            )


def type_breakdown(frame: pl.DataFrame, rules: Rules, results: dict[str, Result]) -> None:
    """2014–2020: die Formularzeile im Kopf teilt „Verwaltungsvorlage" in Beschluss- und Informationsvorlage."""
    forms: dict[str, Counter[str]] = defaultdict(Counter)
    for doc_id, paper_type in frame.select("id", "paper_type").iter_rows():
        form = next((s.norm for s in results[doc_id].head if s.kind == "formular"), "(keine)")
        forms[rules.art(paper_type)][form] += 1
    for art in ("Verwaltungsvorlage", "Vorlage aus der Politik"):
        total = sum(forms[art].values())
        print(
            f"  {art} ({total}): "
            + ", ".join(f"{k} {v} ({pct(v, total).strip()})" for k, v in forms[art].most_common(6))
        )


def label_counts(frame: pl.DataFrame, labels: Sequence[str]) -> None:
    """Dokumente mit einer Überschriftzeile „Label:" je Label (für § 3.1: was kein Formularfeld ist)."""
    for label in labels:
        pattern = rf"(?m)^\s*{re.escape(label)}\s*:"
        n = frame.filter(pl.col("text").str.contains(pattern)).height
        print(f"  Überschrift „{label}:“ in {n} Dokumenten ({pct(n, frame.height).strip()})")


def old_form(frame: pl.DataFrame) -> None:
    """2014–2020: welche Spalte die Tabelle der Beratungsfolge hat, und wie oft das Ergebnis fehlt."""
    ergebnis = frame.filter(pl.col("text").str.contains(r"Gremium\s+Sitzungsdatum\s+Ergebnis"))
    qualitaet = frame.filter(
        pl.col("text").str.contains(r"Gremium\s+Sitzungsdatum\s+Beratungsqualität")
    )
    offen = ergebnis.filter(pl.col("text").str.contains(r"\d{2}\.\d{2}\.\d{4}\s+-/-")).height
    print(
        f"  Kopf mit Spalte „Ergebnis“: {ergebnis.height}, mit „Beratungsqualität“: {qualitaet.height}; "
        f"von den ersten mit „-/-“ hinter einem Sitzungsdatum: {offen} ({pct(offen, ergebnis.height).strip()})"
    )


def special_findings(frame: pl.DataFrame) -> None:
    """Nebenbefunde: was „A+F Beschluss" ist; Kopf ohne „Betrifft"."""
    af = frame.filter(pl.col("paper_type") == "A+F Beschluss")
    n_af = af.height
    ausf = af.filter(
        pl.col("text").str.contains(r"(?i)ausführungs-\s*und\s*finanzierungsbeschlus")
    ).height
    anreg = af.filter(pl.col("text").str.contains(r"(?i)anregungen\s+und\s+beschwerden")).height
    print(
        f"  A+F Beschluss: {n_af}, davon mit „Ausführungs- und Finanzierungsbeschluss“ im Text {ausf}, mit „Anregungen und Beschwerden“ {anreg}"
    )
    empty = frame.filter(pl.col("text").str.strip_chars() == "").height
    print(f"  Dokumente mit leerem Rohtext: {empty} von {frame.height}")


# --------------------------------------------------------------------------------------------
# Stichprobe und Kodieraufgaben (F4 baut den Rahmen; Format vorläufig)
# --------------------------------------------------------------------------------------------


def allocate(sizes: dict[str, int], total: int, minimum: int) -> dict[str, int]:
    """Proportional mit Mindestzahl je Schicht, Rest nach größtem Bruchteil; nie mehr als die Schicht hat."""
    alloc = {k: min(v, minimum) for k, v in sizes.items()}
    rest = total - sum(alloc.values())
    pool = {k: v - alloc[k] for k, v in sizes.items() if v > alloc[k]}
    pool_total = sum(pool.values())
    raw = {k: rest * v / pool_total for k, v in pool.items()}
    for k, v in raw.items():
        alloc[k] += min(int(v), sizes[k] - alloc[k])
    left = total - sum(alloc.values())
    for k in sorted(raw, key=lambda k: (-(raw[k] - int(raw[k])), k)):
        if left == 0:
            break
        if alloc[k] < sizes[k]:
            alloc[k] += 1
            left -= 1
    return alloc


def sample(frame: pl.DataFrame, rules: Rules) -> list[tuple[str, str, float]]:
    with_text = frame.filter(pl.col("text").str.strip_chars() != "")
    strata: dict[str, list[str]] = defaultdict(list)
    for doc_id, paper_type in with_text.select("id", "paper_type").iter_rows():
        strata[rules.art(paper_type)].append(doc_id)
    sizes = {k: len(v) for k, v in strata.items()}
    alloc = allocate(sizes, STICHPROBE, MINDESTENS_JE_SCHICHT)
    rng = random.Random(SEED)
    chosen: list[tuple[str, str, float]] = []
    for art in sorted(strata):
        ids = sorted(strata[art])
        for doc_id in sorted(rng.sample(ids, alloc[art])):
            chosen.append((doc_id, art, sizes[art] / alloc[art]))
    print("  Schicht | Dokumente mit Text | Stichprobe | Gewicht")
    for art in sorted(strata, key=lambda a: -sizes[a]):
        print(f"  {art} | {sizes[art]} | {alloc[art]} | {sizes[art] / alloc[art]:.2f}")
    return chosen


def line_number(lines: Sequence[tuple[int, int]], pos: int) -> int:
    """1-basierte Zeilennummer der Zeile, in der `pos` liegt."""
    for i, (s, e) in enumerate(lines):
        if s <= pos <= e:
            return i + 1
    return len(lines)


def write_tasks(
    frame: pl.DataFrame,
    rules: Rules,
    chosen: Sequence[tuple[str, str, float]],
    results: dict[str, Result],
) -> None:
    VALIDIERUNG.mkdir(parents=True, exist_ok=True)
    with (VALIDIERUNG / "stichprobe.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["id", "schicht", "gewicht"])
        for doc_id, art, weight in chosen:
            writer.writerow([doc_id, art, f"{weight:.4f}"])
    AUFGABEN_DIR.mkdir(parents=True, exist_ok=True)
    rows = {r["id"]: r for r in frame.iter_rows(named=True)}
    rng = random.Random(SEED + 1)
    order = list(chosen)
    rng.shuffle(order)  # Kodierer sehen die Schichten gemischt
    with (
        (AUFGABEN_DIR / "aufgaben.jsonl").open("w", encoding="utf-8") as tasks,
        (AUFGABEN_DIR / "regel.jsonl").open("w", encoding="utf-8") as rule_out,
    ):
        for number, (doc_id, art, _weight) in enumerate(order, start=1):
            row = rows[doc_id]
            text = row["text"]
            result = results[doc_id]
            lines = result.lines
            pages = [i + 1 for i, (s, _e) in enumerate(lines) if s > 0 and text[s - 1] == "\f"]
            task_id = f"11-struktur-{number:03d}"
            tasks.write(
                json.dumps(
                    {
                        "vorhaben": "11-struktur",
                        "aufgabe": task_id,
                        "id": doc_id,
                        "drucksache": row["reference"],
                        "dokumentart": row["paper_type"],
                        "zeilen": [text[s:e] for s, e in lines[:MAX_ZEILEN_AUFGABE]],
                        "seitenanfang_zeilen": [p for p in pages if p <= MAX_ZEILEN_AUFGABE],
                        "gekuerzt": len(lines) > MAX_ZEILEN_AUFGABE,
                        "codebuch": "validierung/11-struktur/codebuch.toml",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            decisions = [s for s in result.sections if s.norm == "beschlussvorschlag"]
            first = decisions[0] if decisions else None
            rule_out.write(
                json.dumps(
                    {
                        "aufgabe": task_id,
                        "id": doc_id,
                        "schicht": art,
                        "beschlussvorschlag": {
                            "vorhanden": first is not None,
                            "erste_zeile": line_number(lines, first.start) if first else None,
                            "letzte_zeile": line_number(lines, first.end) if first else None,
                            "quelle": result.sources.get("beschlussvorschlag"),
                        },
                        "kopf": [
                            {"art": s.kind, "wert": s.norm, "zeile": line_number(lines, s.start)}
                            for s in result.head
                            if s.kind in ("amt", "dezernat", "beratung", "sitzung", "datum")
                        ],
                        "extractor": EXTRACTOR,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"  geschrieben: {VALIDIERUNG / 'stichprobe.csv'} ({len(chosen)} IDs)")
    print(
        f"  geschrieben: {AUFGABEN_DIR / 'aufgaben.jsonl'} und regel.jsonl (lokal, nicht im Repo)"
    )
    size = (AUFGABEN_DIR / "aufgaben.jsonl").stat().st_size
    cut = sum(1 for doc_id, _art, _w in chosen if len(results[doc_id].lines) > MAX_ZEILEN_AUFGABE)
    print(
        f"  aufgaben.jsonl: {size / 1e3:.0f} KB, gekürzt (über {MAX_ZEILEN_AUFGABE} Zeilen): {cut}"
    )


# --------------------------------------------------------------------------------------------


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aufgaben", action="store_true", help="Stichprobe und Kodieraufgaben schreiben"
    )
    args = parser.parse_args(argv)
    t_start = time.perf_counter()
    print(
        f"Lauf am {date.today().isoformat()}, Last (uptime): {os.getloadavg()[0]:.1f} / {os.getloadavg()[1]:.1f} / {os.getloadavg()[2]:.1f}"
    )
    dus = Rules.load("duesseldorf")
    dus2014 = Rules.load("duesseldorf-2014")
    mg = Rules.load("moenchengladbach")

    print("§ 2 Datenlage")
    frames = {p: load_profile(p) for p in ("duesseldorf", "2014-2020", "2025", "moenchengladbach")}
    for profile, frame in frames.items():
        size = (ROHTEXT / f"{profile}.parquet").stat().st_size
        print(f"  {profile}: Messdatei {size / 1e6:.1f} MB")
        print(
            f"  {profile}: {frame.height} Dokumente mit Rohtextzeile, {frame['chars'].sum()} Zeichen, "
            f"{frame['pages'].sum()} Seiten, {frame.filter(pl.col('text').str.contains(chr(12))).height} mit Seitenwechsel"
        )
    main_frame = frames["duesseldorf"]
    special_findings(main_frame)
    label_counts(
        main_frame,
        [
            "Finanzielle Auswirkungen",
            "Finanzierung",
            "Klimarelevanz",
            "Klimaschutz",
            "Klimaanpassung",
        ],
    )

    print('\n§ 3.1 Überschriften „Label:" je Art (Hauptperiode, Anteil der Dokumente in %, ab 2 %)')
    heading_catalog(main_frame, dus)

    t0 = time.perf_counter()
    results = run_rules(main_frame, dus)
    cache: Cache = {("duesseldorf", dus.name): results}
    t_rules = time.perf_counter() - t0
    n_spans = sum(len(r.sections) + len(r.head) for r in results.values())
    print(
        f"\n§ 3.2 Regelwerk auf der Hauptperiode: {len(results)} Dokumente, {n_spans} Spannen, {t_rules:.1f} s; Vertrag 0 <= start < end <= len(text) hält für alle"
    )

    output_sizes(main_frame, results)

    print("\n§ 3.3 Abdeckung je Art (Anteil der Dokumente mit mindestens einer Spanne)")
    coverage(main_frame, dus, results, KINDS, HEAD)

    print("\n§ 3.4 Beschlussvorschlag")
    decision_stats(main_frame, dus, results, show=12)

    print("\n§ 3.5 Kopf")
    head_stats(main_frame, dus, results)

    print("\n§ 4.1 Gremien des Kopfs gegen OParl")
    oparl_check(main_frame, results)

    print("\n§ 3.6 Übertrag auf die anderen Profile")
    transfer(
        ["duesseldorf", "2014-2020", "2025", "moenchengladbach"],
        frames,
        {
            "duesseldorf": [dus],
            "2014-2020": [dus, dus2014],
            "2025": [dus],
            "moenchengladbach": [dus, mg],
        },
        cache,
    )
    old = cache["2014-2020", dus2014.name]
    type_breakdown(frames["2014-2020"], dus2014, old)
    old_form(frames["2014-2020"])
    print("  Beschlussvorschlag 2014–2020 je Art (Block duesseldorf-2014):")
    decision_stats(frames["2014-2020"], dus2014, old, show=0)
    mg_results = cache["moenchengladbach", mg.name]
    print("  Mönchengladbach mit eigenem Block, Abdeckung je Art:")
    coverage(frames["moenchengladbach"], mg, mg_results, KINDS, HEAD)
    print("  Mönchengladbach, Beschlussvorschlag:")
    decision_stats(frames["moenchengladbach"], mg, mg_results, show=6)

    print(f"\n§ 4.2 Stichprobe (geschichtet nach Art, Seed {SEED})")
    chosen = sample(main_frame, dus)
    expected = sum(1 for _id, art, _w in chosen if art in dus.decision_expected)
    print(f"  davon Arten mit erwartetem Beschlussvorschlag: {expected}")
    print(
        f"  Kriterium „mindestens 90 % der Stichprobe“ heißt mindestens {math.ceil(0.9 * STICHPROBE)} von {STICHPROBE}; "
        f"Wilson bei 180: {wilson(180, STICHPROBE)}, bei 190: {wilson(190, STICHPROBE)}"
    )
    if args.aufgaben:
        write_tasks(main_frame, dus, chosen, results)
    print(
        f"\nLaufzeit gesamt: {time.perf_counter() - t_start:.0f} s, Last am Ende: {os.getloadavg()[0]:.1f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
