"""Vorhaben 11: Abschnitte und Kopf eines Ratsdokuments aus seinem Rohtext (Regelwerk ``struktur-1``).

Welche Teile hat ein Ratsdokument, und wo stehen sie? Eine Vorlage der Verwaltung ist ein Formular
(``Betrifft:``, ``Fachbereich:``, ``Dezernentin / Dezernent:``, ``Beratungsfolge:`` mit der
Tabelle der Gremien, dann ``Beschlussdarstellung:`` und ``Sachdarstellung:``), ein Antrag oder eine
Anfrage ist ein Brief (Absender, Ort und Datum, „zur Sitzung der … am …", ``Betrifft:``, Anrede,
Text, Grußformel). Das Regelwerk liest beides aus dem Rohtext (Fundament F1) und liefert
**Spannen nach F3** (``georep.spans``) und je Korpus-ID **eine Kopfzeile**.

``struktur-1`` ist der Entwurf ``struktur-entwurf-1`` aus ``docs/plans/11-struktur-messung.py``
**unverändert** (Messdokument 11, § 10, Punkt 1): an 200 Dokumenten gegen zwei KI-Kodierer 188 von
200 Beschlussvorschlägen zeilengenau richtig, die Kopffelder mit Präzision 0,95 bis 1,0. Jede
Funktion hier folgt ihrem Gegenstück im Messskript Zeile für Zeile; was dazukommt, berührt keine
validierte Frage:

* die Abschnittsart **Rumpf** (Text nach dem Kopf ohne Überschrift; Synergien 2026-11, § 4):
  ein Abschnitt ``kopf_*`` endet am Ende seines letzten Kopffelds, was danach bis zur nächsten
  Überschrift steht, ist Rumpf, ebenso Text außerhalb jedes Abschnitts zwischen Betreff und
  Grußformel. Genau die Regel, mit der Vorhaben 16 die Lücke im Messskript geschlossen hat;
* die **Gremiennamen** im Kopf bekommen ihr Kürzel aus ``[bodies]`` (``BodyNames``), die Sitzung
  eines Briefs dazu den Namen im Nominativ (Kodierer und Schlichtung, Messdokument § 4.1);
* ``rumpf_leer``: nach dem Kopf steht kein Text (der Rumpf ist nicht in der Textebene des PDFs).

Die Muster stehen im Profil (``[structure]``); hier stehen nur die Arten der Abschnitte und die
Datumsformen deutscher Ratsdokumente. Kein Feld liest einen Personennamen: vom Feld „Dezernentin /
Dezernent" deckt die Spanne nur die Amtsbezeichnung, vom Unterschriftsblock nur eine
Amtsbezeichnung aus der Liste des Profils; beides prüft ein Vertrag.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import NamedTuple

import deal
import polars as pl

from georep.contracts import has_columns, one_row_per_document
from georep.prep.bodies import DISTRICT_BODY, BodyRef, BodyRules, resolve_organizations
from georep.prep.raw_texts import split_lines
from georep.settings import CITY_PLACEHOLDER, Settings
from georep.spans import SECTION_KIND, SPAN_SCHEMA, check_spans, read_span, sort_spans

STRUCTURE_RULES = (
    "struktur-1"  # Name und Version des Regelwerks; eine geschärfte Fassung ist struktur-2
)
STRUCTURE_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen der beiden Dateien ändern

# Die Arten der Abschnitte, die der Code kennt; das Profil bildet seine Labels auf sie ab.
BETREFF = "betreff"
DECISION = "beschlussvorschlag"
BODY = "rumpf"
HEAD_PREFIX = "kopf_"
HEAD_KINDS = frozenset(
    {BETREFF, "kopf_amt", "kopf_amtsleitung", "kopf_dezernat", "kopf_beratungsfolge"}
)
HEAD = "kopf"  # ``section`` der Kopffelder
# ``kind`` der Kopffelder; ``amt``, ``dezernat`` und ``beratung`` bilden das Ende des Kopfs
FIELDS = ("amt", "dezernat", "beratung", "sitzung", "datum", "formular", "unterzeichner")
HEAD_END_FIELDS = frozenset({"amt", "dezernat", "beratung"})
SOURCES = ("ueberschrift", "einleitung", "beschlusssatz", "formular")

_DATE = re.compile(r"\d{2}\.\d{2}\.\d{4}")
_NUMERIC_DATE = re.compile(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{2,4})")
_NAMED_DATE = re.compile(r"(\d{1,2})\.\s?([A-Za-zäÄ]+)\s?(\d{4})")
_HYPHEN_BREAK = re.compile(r"-\s*\n\s*(?=[a-zäöüß])")
_SPACE = re.compile(r"\s+")
_CHUNK = re.compile(r"[^\n\f]*(?:[\n\f]|$)")

BERATUNG_TYPE = pl.Struct(
    {"gremium": pl.String, "gremium_kuerzel": pl.String, "datum": pl.Date, "qualitaet": pl.String}
)
# ``dokumente_kopf.parquet``: eine Zeile je Korpus-ID; ohne Rohtext sind alle Felder leer (null)
HEAD_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "formular": pl.String(),
    "amt_nr": pl.String(),
    "amt_name": pl.String(),
    "dezernat_titel": pl.String(),
    "beratungsfolge": pl.List(BERATUNG_TYPE),
    "sitzung_gremium": pl.String(),
    "sitzung_kuerzel": pl.String(),
    "sitzung_datum": pl.Date(),
    "briefdatum": pl.Date(),
    "unterzeichner_rolle": pl.String(),
    "beschlussvorschlag": pl.Boolean(),
    "beschlussvorschlag_quelle": pl.String(),
    "rumpf_leer": pl.Boolean(),
    "extractor": pl.String(),
}


# --------------------------------------------------------------------------------------------
# Regeln
# --------------------------------------------------------------------------------------------


def _compiled(pattern: str, city: str = "") -> re.Pattern[str] | None:
    """Ein Muster aus dem Profil, ``{city}`` durch den Ort ersetzt; leer heißt „kein Muster"."""
    if not pattern:
        return None
    return re.compile(pattern.replace(CITY_PLACEHOLDER, re.escape(city)))


@dataclass(frozen=True)
class Lead:
    kind: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class StructureRules:
    """``[structure]`` eines Profils, einmal kompiliert; ``from_settings`` ist die einzige Brücke."""

    heading: re.Pattern[str]
    heading_nocolon: re.Pattern[str] | None
    labels: Mapping[str, str]
    level2: frozenset[str]
    lead_blocked_in: frozenset[str]
    leads: tuple[Lead, ...]
    end_markers: tuple[re.Pattern[str], ...]
    betreff_max_lines: int
    fallback_kind: str
    fallback: re.Pattern[str] | None
    fallback_lines: int
    fallback_only_expected: bool
    betreff_after_form: bool
    art_rules: tuple[tuple[re.Pattern[str], str], ...]
    decision_expected: frozenset[str]
    decision_not_expected: frozenset[str]
    consultation_header: re.Pattern[str] | None
    consultation_row: re.Pattern[str]
    quality_placeholders: frozenset[str]
    titles: re.Pattern[str] | None
    signer_roles: re.Pattern[str] | None
    signer_window: int
    closing: re.Pattern[str] | None
    session: re.Pattern[str] | None
    session_suffix: re.Pattern[str] | None
    date_line: re.Pattern[str] | None
    office: re.Pattern[str] | None
    form_titles: frozenset[str]
    head_lines: int
    months: Mapping[str, int]
    page_noise: tuple[str, ...]
    min_body_chars: int

    @classmethod
    def from_settings(cls, settings: Settings) -> StructureRules:
        """Wie ``Rules.load`` im Messskript, aus ``settings.structure`` und dem Ort der Stadt."""
        block = settings.structure
        head = block.head
        city = settings.city.name
        quality = "|".join(re.escape(q) for q in [*head.quality, *head.quality_placeholders])
        tail = (
            rf"\s+(?P<qualitaet>{quality})"
            if head.quality_required
            else rf"(\s+(?P<qualitaet>{quality}))?"
        )
        if not quality:
            tail = ""
        row = re.compile(
            r"(?P<gremium>[^\s\d].{0,150}?)\s+(?P<datum>\d{2}\.\d{2}\.\d{4})" + tail, re.S
        )
        return cls(
            heading=re.compile(block.heading or r"(?!)(?P<label>)(?P<rest>)"),
            heading_nocolon=_compiled(block.heading_nocolon),
            labels=dict(block.labels),
            level2=frozenset(block.level2),
            lead_blocked_in=frozenset(block.lead_blocked_in),
            leads=tuple(Lead(lead.kind, re.compile(lead.pattern)) for lead in block.leads),
            end_markers=tuple(re.compile(p) for p in block.end_markers),
            betreff_max_lines=block.betreff_max_lines,
            fallback_kind=block.fallback.kind,
            fallback=_compiled(block.fallback.pattern),
            fallback_lines=block.fallback.max_lines_after_head,
            fallback_only_expected=block.fallback.only_expected,
            betreff_after_form=block.betreff_after_form,
            art_rules=tuple((re.compile(p), a) for p, a in block.art),
            decision_expected=frozenset(block.decision_expected),
            decision_not_expected=frozenset(block.decision_not_expected),
            consultation_header=_compiled(head.consultation_header),
            consultation_row=row,
            quality_placeholders=frozenset(head.quality_placeholders),
            titles=_compiled(head.titles),
            signer_roles=_compiled(head.signer_roles),
            signer_window=head.signer_window,
            closing=_compiled(head.closing),
            session=_compiled(head.session),
            session_suffix=_compiled(head.session_suffix, city),
            date_line=_compiled(head.date_line, city),
            office=_compiled(head.office),
            form_titles=frozenset(head.form_titles),
            head_lines=head.head_lines,
            months={name: number for number, name in enumerate(block.months, start=1)},
            page_noise=tuple(block.page_noise),
            min_body_chars=block.min_body_chars,
        )

    def art(self, paper_type: str) -> str:
        """Die zusammengefasste Art einer Dokumentart (Fraktionsvarianten zu einer)."""
        for pattern, art in self.art_rules:
            if pattern.search(paper_type):
                return art
        return paper_type


# --------------------------------------------------------------------------------------------
# Gremiennamen
# --------------------------------------------------------------------------------------------


def name_key(name: str) -> str:
    """Ein Gremiumsname ohne Groß- und Kleinschreibung, Satzzeichen und Genitivendung.

    „Ausschusses für Gesundheit und Soziales" und „Ausschuss für Gesundheit und Soziales" haben
    denselben Schlüssel, ebenso „Rates" und „Rat": je Wort fallen ``e`` und ``s`` am Ende weg, auf
    beiden Seiten gleich, also unterscheidet der Schlüssel zwei Namen nur, wo sie sich in mehr als
    der Endung unterscheiden. Ziffern zählen ohne führende Null.
    """
    words = re.findall(r"\w+", name.casefold())
    return " ".join(str(int(w)) if w.isdigit() else (w.rstrip("es") or w) for w in words)


@dataclass(frozen=True)
class BodyNames:
    """Gremiumsname, wie ein Dokument ihn schreibt, zu Kürzel und Name aus ``[bodies]``.

    Keine zweite Tabelle (Synergien 2026-11, § 1): die Namen kommen aus ``BodyRules`` (Rat,
    Ausschüsse, Beiräte, die Bezirksvertretungen über ``district_body_name``), dazu die Kürzel
    selbst („AÖE") und der Name des Rates in Worten aus ``[city].council`` („Stadtrat"). Ein
    Schlüssel, der auf zwei Kürzel zeigt, fällt weg: geraten wird nicht.
    """

    rules: BodyRules
    by_key: Mapping[str, str]
    district: tuple[re.Pattern[str], ...]  # „Bezirksvertretung 5", „BV5" -> Nummer in der Gruppe n

    @classmethod
    def from_settings(cls, settings: Settings) -> BodyNames:
        rules = BodyRules.from_settings(settings.bodies)
        candidates: dict[str, set[str]] = defaultdict(set)
        for code in (*rules.council, *rules.committees, *rules.advisory):
            candidates[name_key(code)].add(code)
            if rules.names.get(code):
                candidates[name_key(rules.names[code])].add(code)
        for code, name in rules.district_body_names.items():
            candidates[name_key(name)].add(code)
            candidates[name_key(code)].add(code)
        if len(rules.council) == 1 and settings.city.council:
            candidates[name_key(settings.city.council)].add(next(iter(rules.council)))
        by_key = {key: next(iter(codes)) for key, codes in candidates.items() if len(codes) == 1}
        before, _, after = settings.bodies.district_body_name.partition("{n}")
        # nur mit Wort davor: eine nackte Zahl ist kein Gremium
        district = [
            rf"{re.escape(word)}\s*0*(?P<n>\d+){re.escape(tail)}"
            for word, tail in ((before.strip(), after.strip()), (rules.district_body, ""))
            if word
        ]
        return cls(rules, by_key, tuple(re.compile(pattern, re.I) for pattern in district))

    def code(self, name: str) -> str | None:
        """Das Kürzel zu einem geschriebenen Namen, ``None``, wenn ``[bodies]`` ihn nicht kennt."""
        district = next(
            (found for p in self.district if (found := p.fullmatch(name.strip()))), None
        )
        if district is not None and self.rules.district_body:
            code = f"{self.rules.district_body}{int(district.group('n'))}"
            return self.by_key.get(name_key(name), code)
        return self.by_key.get(name_key(name))

    def name(self, code: str) -> str:
        """Der Name des Kürzels aus ``[bodies]``; leer, wenn keiner gesichert ist."""
        if code in self.rules.district_body_names or (
            self.rules.district_body
            and code.startswith(self.rules.district_body)
            and code[len(self.rules.district_body) :].isdigit()
        ):
            number = code[len(self.rules.district_body) :]
            district = int(number) if number.isdigit() else 1
            return self.rules.name_of(BodyRef(DISTRICT_BODY, code, district))
        return self.rules.name_of(BodyRef(self.rules.kind_of(code), code, None))


# --------------------------------------------------------------------------------------------
# Regelwerk (Messskript: split_lines, norm_ws, trim, find_events, cut_betreff, analyse …)
# --------------------------------------------------------------------------------------------


class Found(NamedTuple):
    """Eine Spanne nach F3 ohne ``id`` und ``extractor``; ``0 <= start < end <= len(text)``."""

    start: int
    end: int
    kind: str
    value: str
    norm: str
    section: str


@dataclass
class _Event:
    line: int
    typ: str  # heading, lead, end
    kind: str
    label: str
    content: int  # Zeichenposition, an der der Abschnittstext beginnt
    source: str  # ueberschrift, einleitung, beschlusssatz


@dataclass
class Structure:
    """Was das Regelwerk in einem Dokument findet."""

    sections: list[Found] = field(default_factory=list)
    head: list[Found] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)  # Abschnittsart -> erste Quelle
    lines: list[tuple[int, int]] = field(default_factory=list)
    headings: list[tuple[int, int]] = field(default_factory=list)  # Überschriften der Ebene 1
    body_empty: bool = True


def norm_ws(value: str) -> str:
    """Trennstrich am Zeilenende weg, Leerraum zu einem Leerzeichen, Ränder weg."""
    return _SPACE.sub(" ", _HYPHEN_BREAK.sub("", value)).strip()


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _find_events(
    text: str, lines: Sequence[tuple[int, int]], rules: StructureRules
) -> list[_Event]:
    events: list[_Event] = []
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
            events.append(_Event(i, "heading", rules.labels[label], label, content, "ueberschrift"))
            continue
        if line.rstrip().endswith(":"):
            window = " ".join(text[a:b] for a, b in lines[max(0, i - 2) : i + 1])
            lead = next((lead for lead in rules.leads if lead.pattern.search(window)), None)
            if lead is not None:
                events.append(_Event(i, "lead", lead.kind, line.strip(), nxt, "einleitung"))
                continue
        if any(marker.match(line) for marker in rules.end_markers):
            events.append(_Event(i, "end", "", line.strip(), e, ""))
    return events


def _cut_betreff(text: str, start: int, end: int, rules: StructureRules) -> int:
    """Der Betreff endet an der ersten Leerzeile nach Text oder nach ``betreff_max_lines`` Zeilen."""
    seen = 0
    pos = start
    for raw in _CHUNK.finditer(text[start:end]):
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


def analyse(text: str, rules: StructureRules, paper_type: str = "") -> Structure:
    """Abschnitte, Rumpf und Kopf eines Dokuments; die Spannen tragen noch keine ID."""
    result = analyse_draft(text, rules, paper_type)
    _add_body(text, rules, result)
    return result


def analyse_draft(text: str, rules: StructureRules, paper_type: str = "") -> Structure:
    """Genau ``analyse`` des Messskripts (``struktur-entwurf-1``): Abschnitte und Kopf, ohne Rumpf.

    Die Kopffelder sind hier schon fertig; ``analyse`` zerlegt danach nur die Abschnitte
    ``kopf_*`` in Kopf und Rumpf. Getrennt, damit ein Test beide Regelwerke Zeile für Zeile
    vergleichen kann.
    """
    result = Structure(lines=split_lines(text))
    lines = result.lines
    events = _find_events(text, lines, rules)
    result.headings = [
        lines[event.line]
        for event in events
        if event.typ == "heading" and event.kind not in rules.level2
    ]
    open1: _Event | None = None
    open2: _Event | None = None

    def close(event: _Event | None, end: int) -> None:
        if event is None:
            return
        start, stop = _trim(text, event.content, end)
        if event.kind == BETREFF:
            stop = _trim(text, start, _cut_betreff(text, start, stop, rules))[1]
            for a, b in lines:  # ein Beschlusssatz direkt unter dem Betreff gehört nicht mehr dazu
                if start < a < stop and rules.fallback and rules.fallback.match(text[a:b]):
                    stop = _trim(text, start, a)[1]
                    break
        if stop > start:
            result.sections.append(
                Found(start, stop, SECTION_KIND, event.label, event.kind, event.kind)
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
        _add_fallback(text, rules, result, events)
    if rules.betreff_after_form and not any(span.norm == BETREFF for span in result.sections):
        _add_betreff_after_form(text, rules, result)
    result.sections.sort(key=lambda span: (span.start, span.end))
    result.head = _head_fields(text, rules, result)
    return result


def _add_betreff_after_form(text: str, rules: StructureRules, result: Structure) -> None:
    """Alte Vorlagenform: der Betreff steht ohne Label in den Zeilen unter dem Formulartitel."""
    lines = result.lines
    for i, (s, e) in enumerate(lines[: rules.head_lines]):
        if norm_ws(text[s:e]) in rules.form_titles:
            body = list(lines[i + 1 : i + 1 + 12])
            first = next((k for k, (a, b) in enumerate(body) if text[a:b].strip()), None)
            if first is None:
                return
            stop_k = first
            for k in range(first, min(len(body), first + rules.betreff_max_lines)):
                a, b = body[k]
                if not text[a:b].strip() or (rules.fallback and rules.fallback.match(text[a:b])):
                    break
                stop_k = k
            start, stop = _trim(text, body[first][0], body[stop_k][1])
            if stop > start:
                result.sections.append(Found(start, stop, SECTION_KIND, "", BETREFF, BETREFF))
                result.sources.setdefault(BETREFF, "formular")
            return


def _add_fallback(
    text: str, rules: StructureRules, result: Structure, events: Sequence[_Event]
) -> None:
    """Beschlusssatz ohne Überschrift: die ersten Zeilen nach dem Kopf, bis zur nächsten Überschrift."""
    if rules.fallback is None:
        return
    head_events = [e for e in events if e.typ == "heading" and e.kind in HEAD_KINDS]
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
            start, stop = _trim(text, s, stop)
            if stop > start:
                kind = rules.fallback_kind
                label = norm_ws(text[s:e])[:40]
                result.sections.append(Found(start, stop, SECTION_KIND, label, kind, kind))
                result.sources.setdefault(kind, "beschlusssatz")
            return


def parse_date(value: str, months: Mapping[str, int]) -> str:
    """Ein Datum wie geschrieben („24.06.2025", „24. Juni 2025") als ISO; leer, wenn keines."""
    value = value.strip()
    numeric = _NUMERIC_DATE.fullmatch(value)
    named = _NAMED_DATE.fullmatch(value)
    try:
        if numeric:
            year = int(numeric.group(3))
            year = year + 2000 if year < 100 else year
            return date(year, int(numeric.group(2)), int(numeric.group(1))).isoformat()
        if named and named.group(2).lower() in months:
            month = months[named.group(2).lower()]
            return date(int(named.group(3)), month, int(named.group(1))).isoformat()
    except ValueError:
        return ""
    return ""


def _head_fields(text: str, rules: StructureRules, result: Structure) -> list[Found]:
    spans: list[Found] = []
    by_kind: dict[str, list[Found]] = defaultdict(list)
    for span in result.sections:
        by_kind[span.norm].append(span)
    if by_kind["kopf_amt"]:
        span = by_kind["kopf_amt"][0]
        value = norm_ws(text[span.start : span.end])
        if 0 < len(value) <= 150:
            match = rules.office.match(value) if rules.office else None
            norm = f"{match.group('nr')} {match.group('name')}".strip() if match else value
            spans.append(Found(span.start, span.end, "amt", value, norm, HEAD))
    if by_kind["kopf_dezernat"]:
        span = by_kind["kopf_dezernat"][0]
        match = rules.titles.match(text[span.start : span.end]) if rules.titles else None
        if match:
            # nur die Amtsbezeichnung; der Name dahinter wird nie gelesen
            start, stop = _trim(text, span.start + match.start(), span.start + match.end())
            title = text[start:stop]
            spans.append(Found(start, stop, "dezernat", title, title, HEAD))
        else:
            spans.append(Found(span.start, span.start + 1, "dezernat", "", "", HEAD))
    if by_kind["kopf_beratungsfolge"]:
        block = by_kind["kopf_beratungsfolge"][0]
        header = (
            rules.consultation_header.search(text, block.start, block.end)
            if rules.consultation_header
            else None
        )
        pos = header.end() if header else block.start
        for row in rules.consultation_row.finditer(text, pos, block.end):
            gremium = norm_ws(row.group("gremium"))
            if len(gremium) > 150 or _DATE.search(gremium):
                continue
            quality = row.groupdict().get("qualitaet") or ""
            quality = "" if quality in rules.quality_placeholders else quality
            norm = f"{gremium}|{parse_date(row.group('datum'), rules.months)}|{quality}"
            start, stop = _trim(text, row.start(), row.end())
            spans.append(Found(start, stop, "beratung", norm_ws(text[start:stop]), norm, HEAD))
    top = result.lines[: rules.head_lines]
    head_end = top[-1][1] if top else 0
    if rules.session is not None:
        match = rules.session.search(text, 0, head_end)
        if match:
            datum = parse_date(match.group("datum"), rules.months)
            norm = f"{norm_ws(match.group('gremium'))}|{datum}"
            spans.append(
                Found(match.start(), match.end(), "sitzung", norm_ws(match.group(0)), norm, HEAD)
            )
    for s, e in top:
        match = rules.date_line.match(text[s:e]) if rules.date_line else None
        if match:
            value = match.group("datum")
            start, stop = s + match.start("datum"), s + match.end("datum")
            spans.append(Found(start, stop, "datum", value, parse_date(value, rules.months), HEAD))
            break
    for s, e in top:
        if norm_ws(text[s:e]) in rules.form_titles:
            start, stop = _trim(text, s, e)
            spans.append(Found(start, stop, "formular", text[start:stop], norm_ws(text[s:e]), HEAD))
            break
    signer = _signer_role(text, rules, result.lines)
    if signer is not None:
        spans.append(Found(signer[0], signer[1], "unterzeichner", signer[2], signer[2], HEAD))
    spans.sort(key=lambda span: (span.start, span.end))
    return spans


def _signer_role(
    text: str, rules: StructureRules, lines: Sequence[tuple[int, int]]
) -> tuple[int, int, str] | None:
    """Amtsbezeichnung im Unterschriftsblock; Namen werden übergangen, nie gespeichert."""
    if rules.closing is None or rules.signer_roles is None:
        return None
    for i, (s, e) in enumerate(lines):
        if rules.closing.match(text[s:e]):
            for a, b in lines[i : i + rules.signer_window]:
                match = rules.signer_roles.search(text[a:b])
                if match:
                    role = match.group(0)
                    return a + match.start(), a + match.end(), role[0].upper() + role[1:]
            return None
    return None


# --------------------------------------------------------------------------------------------
# Rumpf: Text nach dem Kopf ohne Überschrift (Synergien 2026-11, § 4; Vorhaben 16, § 3.0)
# --------------------------------------------------------------------------------------------


def _add_body(text: str, rules: StructureRules, result: Structure) -> None:
    """Rumpf und ``rumpf_leer``; die Abschnitte der Ebene 2 bekommen ihren Abschnitt der Ebene 1.

    Rumpf ist, was im Abschnitt ``kopf_*`` hinter dem letzten Kopffeld (Amt, Amtsbezeichnung,
    Zeile der Beratungsfolge) steht, und was außerhalb jedes Abschnitts der Ebene 1 zwischen dem
    Ende des ersten Betreffs und der ersten Grußformel danach steht -- ohne die Zeilen der
    Überschriften der Ebene 1 („Sachdarstellung:" allein ist kein Text; eine Überschrift der
    Ebene 2 steht wie in jedem Abschnitt in ihm und teilt ihn nicht). Der Abschnitt ``kopf_*``
    endet dann am letzten Kopffeld; seine Felder sind schon gelesen, also ändert sich keines.
    """
    head_end = max((f.end for f in result.head if f.kind in HEAD_END_FIELDS), default=0)
    betreff = [s for s in result.sections if s.norm == BETREFF]
    betreff_end = betreff[0].end if betreff else 0
    closing = len(text)
    if rules.closing is not None:
        for s, e in result.lines:
            if s >= betreff_end and rules.closing.match(text[s:e]):
                closing = s
                break
    level1 = [s for s in result.sections if s.norm not in rules.level2]
    level2 = [s for s in result.sections if s.norm in rules.level2]
    body: list[tuple[int, int]] = []
    kept: list[Found] = []
    for span in level1:
        if span.norm.startswith(HEAD_PREFIX) and span.end > head_end:
            body.append((max(span.start, head_end), span.end))
            if span.start < head_end:
                start, stop = _trim(text, span.start, head_end)
                if stop > start:
                    kept.append(span._replace(start=start, end=stop))
            continue
        kept.append(span)
    position = betreff_end
    for span in sorted(level1, key=lambda s: s.start):
        if span.start > position:
            body.append((position, min(span.start, closing)))
        position = max(position, span.end)
    if position < closing:
        body.append((position, closing))
    covered = sorted([*((s.start, s.end) for s in kept), *result.headings])
    pieces: list[Found] = []
    for start, stop in _merge(body):
        for a, b in _outside(start, stop, covered):
            a, b = _trim(text, a, b)
            if b > a:
                pieces.append(Found(a, b, SECTION_KIND, "", BODY, BODY))
    level1_after = sorted([*kept, *pieces], key=lambda s: (s.start, s.end))
    result.sections = sorted(
        [*level1_after, *(_enclosed(span, level1_after) for span in level2)],
        key=lambda s: (s.start, s.end),
    )
    head_stop = max(
        (s.end for s in level1_after if s.norm.startswith(HEAD_PREFIX) or s.norm == BETREFF),
        default=0,
    )
    head_stop = max(head_stop, head_end)
    rest = read_span(text, min(head_stop, len(text)), len(text), rules.page_noise)
    result.body_empty = len(_SPACE.sub("", rest)) < rules.min_body_chars


def _merge(ranges: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for start, stop in sorted(r for r in ranges if r[1] > r[0]):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], stop))
        else:
            out.append((start, stop))
    return out


def _outside(start: int, stop: int, covered: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Die Teile von ``[start, stop)``, die kein Abschnitt aus ``covered`` deckt."""
    out: list[tuple[int, int]] = []
    position = start
    for a, b in covered:
        if b <= position or a >= stop:
            continue
        if a > position:
            out.append((position, a))
        position = max(position, b)
    if position < stop:
        out.append((position, stop))
    return out


def _enclosed(span: Found, level1: Sequence[Found]) -> Found:
    """Eine Spanne der Ebene 2 nennt in ``section`` den Abschnitt der Ebene 1 um ihren Anfang."""
    around = next((s for s in level1 if s.start <= span.start < s.end), None)
    return span._replace(section=around.norm if around else "")


# --------------------------------------------------------------------------------------------
# Batch: Spannen und Kopfzeilen je Korpus-ID
# --------------------------------------------------------------------------------------------


def _iso(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def head_row(structure: Structure, rules: StructureRules, names: BodyNames) -> dict[str, object]:
    """Die Zeile in ``dokumente_kopf`` (ohne ``id`` und ``extractor``) aus den Kopffeldern."""

    def first(kind: str) -> Found | None:
        return next((f for f in structure.head if f.kind == kind), None)

    amt = first("amt")
    office = rules.office.match(amt.value) if amt and rules.office else None
    if amt is None:
        amt_nr = amt_name = None
    elif office is not None:
        amt_nr, amt_name = office.group("nr"), office.group("name").strip() or None
    else:
        amt_nr, amt_name = None, amt.value
    dezernat = first("dezernat")
    rows: list[dict[str, object]] = []
    for found in structure.head:
        if found.kind == "beratung":
            gremium, datum, quality = found.norm.rsplit("|", 2)
            rows.append(
                {
                    "gremium": gremium,
                    "gremium_kuerzel": names.code(gremium),
                    "datum": _iso(datum),
                    "qualitaet": quality or None,
                }
            )
    session = first("sitzung")
    session_body: str | None = None
    session_code: str | None = None
    session_date: date | None = None
    if session is not None:
        written, datum = session.norm.rsplit("|", 1)
        if rules.session_suffix is not None:
            written = rules.session_suffix.sub("", written)
        session_code = names.code(written)
        session_body = (names.name(session_code) if session_code else "") or written
        session_date = _iso(datum)
    letter = first("datum")
    signer = first("unterzeichner")
    form = first("formular")
    return {
        "formular": form.norm if form else None,
        "amt_nr": amt_nr,
        "amt_name": amt_name,
        "dezernat_titel": (dezernat.value or None) if dezernat else None,
        "beratungsfolge": rows,
        "sitzung_gremium": session_body,
        "sitzung_kuerzel": session_code,
        "sitzung_datum": session_date,
        "briefdatum": _iso(letter.norm) if letter else None,
        "unterzeichner_rolle": signer.value if signer else None,
        "beschlussvorschlag": any(s.norm == DECISION for s in structure.sections),
        "beschlussvorschlag_quelle": structure.sources.get(DECISION),
        "rumpf_leer": structure.body_empty,
    }


def _documents_ok(documents: pl.DataFrame) -> bool:
    return has_columns(documents, "id", "paper_type", "text", "extractor") and bool(
        documents.get_column("id").is_unique().all()
    )


def _no_name_in_the_head(
    documents: pl.DataFrame,
    rules: StructureRules,
    names: BodyNames,
    result: tuple[pl.DataFrame, pl.DataFrame],
) -> bool:
    """Amtsbezeichnung und Unterzeichner stammen aus den Listen des Profils, also kein Name."""
    head = result[1]
    titles = head.get_column("dezernat_titel").drop_nulls().unique().to_list()
    roles = head.get_column("unterzeichner_rolle").drop_nulls().unique().to_list()
    return all(rules.titles is not None and rules.titles.fullmatch(t) for t in titles) and all(
        rules.signer_roles is not None and rules.signer_roles.fullmatch(r) for r in roles
    )


def _one_head_row_each(
    documents: pl.DataFrame,
    rules: StructureRules,
    names: BodyNames,
    result: tuple[pl.DataFrame, pl.DataFrame],
) -> bool:
    spans, head = result
    return (
        one_row_per_document(head, documents.get_column("id").to_list())
        and list(head.schema.items()) == list(HEAD_SCHEMA.items())
        and spans.columns == list(SPAN_SCHEMA)
    )


@deal.pre(
    lambda documents, rules, names: _documents_ok(documents),
    message="id, paper_type, text, extractor; jede ID einmal",
)
@deal.ensure(_one_head_row_each, message="je Korpus-ID eine Kopfzeile, Schema fest")
@deal.ensure(_no_name_in_the_head, message="Amtsbezeichnung und Unterzeichner aus dem Profil")
def structure_tables(
    documents: pl.DataFrame, rules: StructureRules, names: BodyNames
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Spannen (``dokumente_abschnitte``) und Kopfzeilen (``dokumente_kopf``) aller Dokumente.

    ``documents`` trägt je Korpus-ID ``paper_type``, den Rohtext ``text`` und dessen Extraktor;
    ohne Rohtext sind beide null, und die Kopfzeile bleibt leer. Mehrere IDs dürfen denselben
    Rohtext tragen (eine PDF-Datei für mehrere Paper): jede bekommt Spannen und Zeile (Synergien
    2026-11, § 1). ``extractor`` der Spannen ist das Regelwerk und der Extraktor des Rohtexts,
    damit keine Position auf den falschen Text zeigt. Die Spannen bestehen ``check_spans`` gegen
    die Länge jedes Rohtexts; Folge und Schema nach F3.
    """
    span_rows: list[tuple[str, int, int, str, str, str, str, str]] = []
    head_rows: list[dict[str, object]] = []
    lengths: dict[str, int] = {}
    for doc_id, paper_type, text, raw_extractor in (
        documents.select("id", "paper_type", "text", "extractor").sort("id").iter_rows()
    ):
        if text is None:
            empty: dict[str, object] = dict.fromkeys(HEAD_SCHEMA)
            empty["id"] = doc_id
            head_rows.append(empty)
            continue
        extractor = f"{STRUCTURE_RULES}/{raw_extractor}"
        found = analyse(text, rules, paper_type or "")
        lengths[doc_id] = len(text)
        span_rows.extend(
            (doc_id, f.start, f.end, f.kind, f.value, f.norm, f.section, extractor)
            for f in (*found.sections, *found.head)
        )
        head_rows.append({"id": doc_id, **head_row(found, rules, names), "extractor": extractor})
    spans = sort_spans(pl.DataFrame(span_rows, schema=SPAN_SCHEMA, orient="row"))
    check_spans(spans, lengths)
    head = pl.DataFrame(head_rows, schema=HEAD_SCHEMA)
    return spans, head


def consultation_agreement(
    head: pl.DataFrame, consultations: pl.DataFrame, organizations: Mapping[str, str]
) -> tuple[int, int]:
    """Wie viele Zeilen der Beratungsfolge im Kopf ihr Gremium in der OParl-Beratungsfolge
    desselben Dokuments finden: (gefunden, Zeilen mit Kürzel und mit OParl-Folge).

    Labels aus den Daten selbst (Messdokument 11, § 4.1: 95,7 %): OParl hält die tatsächliche
    Beratung, der Kopf die geplante, also ist das eine untere Schranke der Präzision. Die
    Organisationen werden über ``[bodies.organizations]`` aufgelöst, wie im Schritt ``bodies``
    (``resolve_organizations``, Punkt 58).
    """
    codes = {
        doc_id: set(resolve_organizations(orgs or [], organizations))
        for doc_id, orgs in consultations.select("id", "consultation_organizations").iter_rows()
    }
    found = known = 0
    for doc_id, rows in head.select("id", "beratungsfolge").iter_rows():
        oparl = codes.get(doc_id)
        if not rows or not oparl:
            continue
        for row in rows:
            if row["gremium_kuerzel"]:
                known += 1
                found += row["gremium_kuerzel"] in oparl
    return found, known


def office_directory(head: pl.DataFrame) -> pl.DataFrame:
    """Das Ämterverzeichnis eines Laufs: je Amtsnummer der häufigste Name und die Zahl der Dokumente.

    Keine Liste im Profil (Synergien 2026-11, § 1): wer Ämter braucht (12, 24), nimmt sie aus
    ``dokumente_kopf``. Bei Gleichstand gewinnt der alphabetisch erste Name.
    """
    named = head.filter(pl.col("amt_nr").is_not_null())
    counts = named.group_by("amt_nr", "amt_name").agg(pl.len().alias("dokumente"))
    best = counts.sort(["amt_nr", "dokumente", "amt_name"], descending=[False, True, False])
    totals = named.group_by("amt_nr").agg(pl.len().alias("dokumente"))
    return (
        best.unique("amt_nr", keep="first", maintain_order=True)
        .select("amt_nr", "amt_name")
        .join(totals, on="amt_nr")
        .sort("amt_nr")
    )


def decision_share(
    head: pl.DataFrame, documents: pl.DataFrame, rules: StructureRules
) -> tuple[int, int]:
    """In wie vielen Dokumenten mit Text, deren Art einen Beschlussvorschlag erwarten lässt, das
    Regelwerk einen findet: (gefunden, Dokumente). Messdokument § 3.4: 10 506 von 10 784."""
    expected = {
        doc_id
        for doc_id, paper_type, text in documents.select("id", "paper_type", "text").iter_rows()
        if text is not None
        and text.strip()
        and rules.art(paper_type or "") in rules.decision_expected
    }
    found = head.filter(pl.col("id").is_in(sorted(expected)) & pl.col("beschlussvorschlag"))
    return found.height, len(expected)
