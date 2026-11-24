"""Drucksachennummern in Titel, Text und Anlagennamen: Schlüssel, Fundstellen, Rollen (Vorhaben 14).

Eine Drucksache nennt eine andere über ihre Nummer: ``OVA/117/2023``, in der alten Form
``61/ 12/2014``, in Mönchengladbach ``0302/X``. Welche Formen eine Stadt hat, sagt ihr Profil
(``[[procedures.forms]]``): je Form ein Muster für die eigene Nummer, eines für den Text und eine
Vorlage für den **Schlüssel**, die Normalform ohne führende Nullen und Leerzeichen, mit einem
Nachtrag als ``/k`` (``OVA/117/2023/1``). Über den Schlüssel findet eine Fundstelle ihr Ziel im
Nummernverzeichnis (``analysis.procedures``); der Code kennt keine Stadt.

Das Verfahren ist das des Messskripts ``docs/plans/14-vorgaenge-messung.py`` (Funktionen
``treffer``, ``key_ref``, ``art2``, ``kantentyp2``), hier als reine Funktionen über vorkompilierten
Regeln. Drei Eigenheiten stehen im Messdokument, § 3.1:

* **Geklebte Kürzel.** pypdf klebt Wörter zusammen („…zur vorlagebv6/002/2023"). Eine Form mit
  ``glued`` nimmt darum die ganze Buchstabenfolge vor der Nummer und kürzt sie auf das längste
  bekannte Kürzel an ihrem Ende; die Kürzel lernt das Verfahren aus den Nummern selbst.
* **Ein Wort ist kein Kürzel.** Ohne bekanntes Kürzel bleibt die Folge nur, wenn sie höchstens
  ``max_code_length`` Zeichen hat und an ihrer Nummer keine andere Form beginnt („vorlage 61/
  12/2014" gehört der alten Form).
* **Datumsform und Bebauungsplan** werden nicht gefiltert: unter den bekannten Treffern sind es zehn
  beziehungsweise keiner, und eine Nummer muss existieren, um eine Kante zu werden.

``edge_type`` ist die Typregel .2 (Messdokument § 3.9), die die Rückfallregel behält (§ 5.1).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import get_args

import deal

from georep.settings import ProcedureRole, Procedures

# Die Rollen, die die Typregel kennt, an einer Stelle: ``settings.ProcedureRole`` (Review, Nit);
# ``sonst`` trifft keine Regel.
ROLES: tuple[str, ...] = get_args(ProcedureRole)
QUESTION, MOTION, PROPOSAL, INFORMATION = "anfrage", "antrag", "vorlage", "information"
POLITICAL = (
    "antrag",
    "politik",
)  # „Vorlage aus der Politik" ohne Titelwort ist ein Antrag alter Art
ADMINISTRATIVE = ("vorlage", "information")  # Verwaltungsvorlagen: nur sie sind Sammelberichte
# Die Kantentypen .2; ``nachtrag`` kommt aus der Nummer, nicht aus den Rollen.
EDGE_TYPES = (
    "antwort",
    "kontrolle",
    "nachfrage",
    "umsetzung",
    "aenderung",
    "fortsetzung",
    "bau",
    "nachtrag",
    "bezug",
)
SUPPLEMENT = "nachtrag"
# Die Typen, über die ein Vorgang wächst (Messskript ``TYPISIERT_2``): ``bezug`` ist kein Vorgang,
# und ein Sammelbericht (``kontrolle``) nennt viele Vorgänge, ohne zu einem zu gehören.
TREE_TYPES = ("antwort", "nachfrage", "umsetzung", "aenderung", "nachtrag", "bau", "fortsetzung")
# Die Felder einer Fundstelle; ``nummer`` ist der Nachtrag über die eigene Nummer, ohne Fundstelle.
FIELDS = ("anlage", "nummer", "text", "titel")
TITLE, TEXT, ATTACHMENT, NUMBER = "titel", "text", "anlage", "nummer"
ATTACHMENT_SEPARATOR = " | "  # zwischen den Namen der Anlagen einer Drucksache, wie im Messskript


@dataclass(frozen=True)
class CompiledForm:
    name: str
    reference: re.Pattern[str]
    text: re.Pattern[str]
    key: str
    glued: bool


@dataclass(frozen=True)
class KindPattern:
    role: str
    paper_type: re.Pattern[str]
    title: re.Pattern[str] | None
    title_not: re.Pattern[str] | None


@dataclass(frozen=True)
class OverridePattern:
    role: str
    title: re.Pattern[str]
    to: str


@dataclass(frozen=True)
class ReferenceRules:
    """Die vorkompilierten Regeln eines Profils; einmal je Lauf gebaut, je Dokument gelesen."""

    forms: tuple[CompiledForm, ...]
    max_code_length: int
    kinds: tuple[KindPattern, ...]
    overrides: tuple[OverridePattern, ...]
    collective: re.Pattern[str] | None
    amendment: re.Pattern[str] | None
    amendment_window: int
    answer: re.Pattern[str] | None
    interim: re.Pattern[str] | None

    @classmethod
    def from_settings(cls, procedures: Procedures) -> ReferenceRules:
        def optional(pattern: str) -> re.Pattern[str] | None:
            return re.compile(pattern) if pattern else None

        return cls(
            forms=tuple(
                CompiledForm(
                    form.name,
                    re.compile(form.reference),
                    re.compile(form.text),
                    form.key,
                    form.glued,
                )
                for form in procedures.forms
            ),
            max_code_length=procedures.max_code_length,
            kinds=tuple(
                KindPattern(
                    rule.role,
                    re.compile(rule.paper_type),
                    optional(rule.title),
                    optional(rule.title_not),
                )
                for rule in procedures.kinds
            ),
            overrides=tuple(
                OverridePattern(rule.role, re.compile(rule.title), rule.to)
                for rule in procedures.title_overrides
            ),
            collective=optional(procedures.collective_titles),
            amendment=optional(procedures.amendment_markers),
            amendment_window=procedures.amendment_window,
            answer=optional(procedures.answer_attachment),
            interim=optional(procedures.interim_attachment),
        )


@dataclass(frozen=True)
class Reference:
    """Eine Drucksachennummer in Normalform: Schlüssel, Grundnummer ohne Nachtrag, Kürzel."""

    key: str
    base: str
    code: str = ""  # das Kürzel, wo die Form eines hat (``BV``); daraus lernt ``known_codes``

    @property
    def is_supplement(self) -> bool:
        """Ein Nachtrag: der Schlüssel trägt hinter der Grundnummer ein ``/k``."""
        return self.key != self.base


@dataclass(frozen=True)
class Hit:
    """Eine Fundstelle: die Nummer in Normalform und ihre Lage im gelesenen Feld (halboffen)."""

    reference: Reference
    start: int
    end: int


def _suffix(groups: Mapping[str, str | None]) -> str:
    """Die erste gefüllte Nachtragsstelle (Gruppen ``suffix…``), sonst leer."""
    for name in sorted(groups):
        value = groups[name]
        if name.startswith("suffix") and value:
            return value
    return ""


def _reference(form: CompiledForm, groups: Mapping[str, str | None], code: str) -> Reference:
    number = groups.get("number")
    values: dict[str, object] = {
        "code": code,
        "number": str(int(number)) if number else "",
        "head": groups.get("head") or "",
        "serial": int(groups["serial"] or 0),
        "year": groups.get("year") or "",
        "period": (groups.get("period") or "").upper(),
    }
    base = form.key.format(**values)
    suffix = _suffix(groups)
    return Reference(f"{base}/{int(suffix)}" if suffix else base, base, code)


@deal.safe
def parse_reference(reference: str | None, rules: ReferenceRules) -> Reference | None:
    """Die eigene Nummer eines Dokuments in Normalform; ``None``, wenn keine Form sie ganz trifft.

    Die Formen gelten in ihrer Folge im Profil; Düsseldorf hat die heutige vor der alten (Punkt 57),
    und jede der 48 313 Nummern der vier Datensätze trifft genau eine (Messdokument § 3.1).
    """
    if not reference:
        return None
    stripped = reference.strip()
    for form in rules.forms:
        match = form.reference.fullmatch(stripped)
        if match is not None:
            groups = match.groupdict()
            return _reference(form, groups, (groups.get("code") or "").upper())
    return None


def known_codes(references: Iterable[Reference | None]) -> frozenset[str]:
    """Die Kürzel der bekannten Nummern einer Stadt: ihre Liste für geklebte Wörter (§ 3.1)."""
    return frozenset(ref.code for ref in references if ref is not None and ref.code)


def _glued_code(run: str, codes: frozenset[str]) -> tuple[str, int] | None:
    """Das längste bekannte Kürzel am Ende von ``run`` und seine Lage darin, sonst ``None``.

    Verglichen wird groß geschrieben, gemessen im Original: ``ß`` wird groß zu ``SS``, und die Lage
    im Text darf daran nicht verrutschen.
    """
    for start in range(len(run)):
        tail = run[start:].upper()
        if tail in codes:
            return tail, start
    return None


@deal.safe
@deal.ensure(
    lambda text, rules, codes, result: all(0 <= h.start < h.end <= len(text) for h in result),
    message="jede Fundstelle liegt im gelesenen Feld",
)
def find_hits(text: str, rules: ReferenceRules, codes: frozenset[str]) -> list[Hit]:
    """Alle Drucksachennummern in einem kleingeschriebenen Feld, Form für Form in Textfolge.

    Eine Stelle kann zwei Formen treffen (``bv 61/12/2014`` als ``BV61/…`` und als ``61/…``); beide
    kommen heraus, und welche eine Drucksache meint, entscheidet das Nummernverzeichnis.
    """
    found = [list(form.text.finditer(text)) for form in rules.forms]
    hits: list[Hit] = []
    for index, (form, matches) in enumerate(zip(rules.forms, found, strict=True)):
        others = {m.start() for i, ms in enumerate(found) if i != index for m in ms}
        for match in matches:
            hit = _hit(form, match, codes, others, rules.max_code_length)
            if hit is not None:
                hits.append(hit)
    return hits


def _hit(
    form: CompiledForm,
    match: re.Match[str],
    codes: frozenset[str],
    others: set[int],
    max_code_length: int,
) -> Hit | None:
    groups = match.groupdict()
    start = match.start()
    code = ""
    if form.glued:
        run = groups.get("code") or ""
        known = _glued_code(run, codes)
        if known is not None:
            code, offset = known
            start = match.start("code") + offset
        else:
            # Ein Wort vor der alten Form ist kein Kürzel; die andere Form nimmt die Stelle.
            number = groups.get("number")
            if (number and match.start("number") in others) or len(run.upper()) > max_code_length:
                return None
            code = run.upper()
    elif groups.get("code"):
        code = (groups["code"] or "").upper()
    return Hit(_reference(form, groups, code), start, match.end())


@deal.safe
@deal.ensure(lambda paper_type, title, rules, result: result in ROLES)
def role_of(paper_type: str | None, title: str | None, rules: ReferenceRules) -> str:
    """Die Rolle im Vorgang aus Dokumentart und, wo das Profil es verlangt, Titel; sonst ``sonst``.

    Danach schlägt der Titel die Dokumentart, wo beide sich widersprechen (``overrides``).
    """
    kind = (paper_type or "").strip().lower()
    name = (title or "").lower()
    role = "sonst"
    for rule in rules.kinds:
        if (
            rule.paper_type.search(kind)
            and (rule.title is None or rule.title.search(name))
            and (rule.title_not is None or not rule.title_not.search(name))
        ):
            role = rule.role
            break
    head = name.lstrip(" :")
    for override in rules.overrides:
        if role == override.role and override.title.match(head):
            return override.to
    return role


@deal.safe
def is_collective(title: str | None, role: str, rules: ReferenceRules) -> bool:
    """Ein Sammelbericht: eine Verwaltungsvorlage mit einem Titelwort aus dem Profil (R3, § 3.9)."""
    return (
        rules.collective is not None
        and role in ADMINISTRATIVE
        and rules.collective.search((title or "").lower()) is not None
    )


@deal.safe
def has_amendment_marker(field: str, value: str, start: int, rules: ReferenceRules) -> bool:
    """Steht ein Änderungszeichen zur Fundstelle? Im Titel irgendwo, sonst kurz davor (§ 3.9)."""
    if rules.amendment is None:
        return False
    window = value if field == TITLE else value[max(0, start - rules.amendment_window) : start]
    return rules.amendment.search(window) is not None


@deal.safe
def is_answer_attachment(name: str | None, rules: ReferenceRules) -> bool:
    """Eine Anlage, deren Name sie als Antwort der Verwaltung ausweist, keine Zwischennachricht."""
    low = (name or "").lower()
    return (
        rules.answer is not None
        and rules.answer.search(low) is not None
        and (rules.interim is None or rules.interim.search(low) is None)
    )


@deal.safe
@deal.ensure(lambda citing, cited, amendment, collective, result: result in EDGE_TYPES)
def edge_type(citing: str, cited: str, amendment: bool, collective: bool) -> str:
    """Der Typ .2 einer Kante aus den Rollen: ``citing`` nennt ``cited`` (Messskript ``kantentyp2``).

    Die Folge ist die Entscheidung: eine Antwort geht einem Sammelbericht vor, und eine Anfrage, die
    etwas nennt, ist immer eine Nachfrage (auch nach dem Stand eines Antrags, Codebuch .2).
    ``aenderung`` braucht ein Änderungszeichen; ohne bleibt dieselbe Kante ``bezug``.
    """
    if cited == QUESTION and citing == INFORMATION:
        return "antwort"
    if collective:
        return "kontrolle"
    if citing == QUESTION:
        return "nachfrage"
    if cited in (*POLITICAL, "eingabe") and citing in ADMINISTRATIVE:
        return "umsetzung"
    if citing in POLITICAL and cited in (PROPOSAL, "bedarf", "af", *POLITICAL):
        return "aenderung" if amendment else "bezug"
    if citing in POLITICAL and cited in (QUESTION, INFORMATION):
        return "fortsetzung"
    if cited == "bedarf" and citing == "af":
        return "bau"
    if citing == INFORMATION and cited == INFORMATION:
        return "fortsetzung"
    return "bezug"
