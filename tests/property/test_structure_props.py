"""Vorhaben 11: Zeilen, Abschnitte und das Lesen einer Spanne, für jede Eingabe.

Die Bausteine, die 11 für andere Vorhaben mitbringt (``docs/plans/11-struktur.md``, § 10, Punkt 3):
``split_lines`` in ``prep/raw_texts.py``, ``read_span`` und ``section_of`` in ``georep.spans``.
"""

from __future__ import annotations

import functools
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import polars as pl
from hypothesis import example, given, settings
from hypothesis import strategies as st

from georep.prep.raw_texts import PAGE_BREAK, split_lines
from georep.prep.structure import (
    Found,
    Structure,
    StructureRules,
    analyse,
    analyse_draft,
    name_key,
)
from georep.settings import load_settings
from georep.spans import SPAN_SCHEMA, read_span, section_of, sort_spans

# Text aus Zeilen, Seitenwechseln und den Zeichen, an denen eine Zeilenregel stolpern könnte
# (``\r``, ``\v``, Leerzeichen); dazu beliebiger Text.
PIECES = st.sampled_from(["\n", PAGE_BREAK, "\r\n", "\r", "\v", " ", "Betrifft:", "ä", ""])
TEXTS = st.lists(st.one_of(st.text(max_size=8), PIECES), max_size=12).map("".join)


@given(text=TEXTS)
@example(text="")
@example(text="\n")
@example(text="a\fb\n\nc")
def test_the_lines_cover_the_text_without_their_separators(text: str) -> None:
    """Jede Zeile ohne Trenner, die Trenner genau dazwischen, die Zeilen zusammen der ganze Text."""
    lines = split_lines(text)
    assert lines[0][0] == 0
    assert lines[-1][1] == len(text)
    for start, end in lines:
        assert "\n" not in text[start:end]
        assert PAGE_BREAK not in text[start:end]
    for (_, end), (start, _) in zip(lines, lines[1:], strict=False):
        assert text[end] in ("\n", PAGE_BREAK)
        assert start == end + 1
    rebuilt = "".join(
        text[start:end] + (text[end] if end < len(text) else "") for start, end in lines
    )
    assert rebuilt == text


# --- read_span: eine Spanne ohne Seitenkopfzeilen lesen (Frage 9.6) --------------------------------

NOISE = st.lists(st.sampled_from([r"Seite \d+", r"- \d+ -", r"x+", r"\d"]), max_size=3)


@st.composite
def text_and_span(draw: st.DrawFn) -> tuple[str, int, int]:
    text = draw(TEXTS)
    start = draw(st.integers(0, len(text)))
    end = draw(st.integers(start, len(text)))
    return text, start, end


@given(case=text_and_span())
def test_without_noise_the_span_is_read_as_it_stands(case: tuple[str, int, int]) -> None:
    """Ohne Muster ist der Ausschnitt genau die Spanne; ein Seitenwechsel wird ein Zeilenumbruch."""
    text, start, end = case
    assert read_span(text, start, end, ()) == text[start:end].replace(PAGE_BREAK, "\n")


@given(case=text_and_span(), noise=NOISE)
@example(case=("a\fSeite 2\nb", 0, 11), noise=[r"Seite \d+"])
def test_reading_drops_whole_noise_lines_and_keeps_the_rest_in_order(
    case: tuple[str, int, int], noise: list[str]
) -> None:
    """Gelesen werden genau die Zeilen der Spanne, die kein Muster ganz trifft, in ihrer Folge."""
    text, start, end = case
    lines = text[start:end].replace(PAGE_BREAK, "\n").split("\n")
    kept = [line for line in lines if not any(re.fullmatch(p, line.strip()) for p in noise)]
    assert read_span(text, start, end, noise) == "\n".join(kept)
    assert PAGE_BREAK not in read_span(text, start, end, noise)


# --- section_of: der Abschnitt der Ebene 1 je Spanne (Synergien § 1) -------------------------------


@st.composite
def sections_and_spans(draw: st.DrawFn) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Abschnitte der Ebene 1 ohne Überlappung je Dokument, dazu Spannen irgendwo im Text."""
    rows: list[dict[str, object]] = []
    probes: list[dict[str, object]] = []
    for doc in draw(st.lists(st.sampled_from(["a", "b", "c"]), unique=True, max_size=3)):
        cuts = sorted(draw(st.lists(st.integers(0, 60), unique=True, max_size=8)))
        for start, end in zip(cuts[::2], cuts[1::2], strict=False):
            kind = draw(st.sampled_from(["betreff", "beschlussvorschlag", "rumpf", "kopf_amt"]))
            rows.append(_span(doc, start, end, "abschnitt", kind, kind))
            # eine Spanne der Ebene 2 im Abschnitt: sie bestimmt keinen Abschnitt
            if draw(st.booleans()):
                rows.append(_span(doc, start, end, "abschnitt", "finanzen", kind))
        for start in draw(st.lists(st.integers(0, 59), max_size=6)):
            probes.append(_span(doc, start, start + 1, "betrag", "", ""))
    return sort_spans(pl.DataFrame(rows, schema=SPAN_SCHEMA)), sort_spans(
        pl.DataFrame(probes, schema=SPAN_SCHEMA)
    )


def _span(doc: str, start: int, end: int, kind: str, norm: str, section: str) -> dict[str, object]:
    return {
        "id": doc,
        "start": start,
        "end": end,
        "kind": kind,
        "value": "",
        "norm": norm,
        "section": section,
        "extractor": "probe",
    }


@given(case=sections_and_spans())
def test_each_span_gets_the_level_one_section_it_starts_in(
    case: tuple[pl.DataFrame, pl.DataFrame],
) -> None:
    """Je Spanne der Abschnitt der Ebene 1, in dem ihr Anfang liegt, sonst leer; Zeilen und Spalten
    bleiben, wie sie waren."""
    sections, spans = case
    level1 = [
        (row["id"], row["start"], row["end"], row["norm"])
        for row in sections.iter_rows(named=True)
        if row["norm"] == row["section"]
    ]
    result = section_of(spans, sections)
    assert result.columns == spans.columns
    assert result.drop("section").equals(spans.drop("section"))
    for row, found in zip(spans.iter_rows(named=True), result["section"], strict=True):
        expected = [n for d, s, e, n in level1 if d == row["id"] and s <= row["start"] < e]
        assert found == (expected[0] if expected else "")


# --- Das Regelwerk: struktur-1 ist der Entwurf unverändert, und der Rumpf hält die Abschnitte -----

# Zeilen eines Ratsdokuments aus dem Katalog (Messdokument § 3.1), dazu Leerzeilen und Seitenköpfe
LINES = st.sampled_from(
    [
        "Betrifft: Radweg am Kanal",
        "Fachbereich: 66 - Amt für Verkehrsmanagement",
        "Amt / Institut: Bezirksverwaltungsstelle 8",
        "Dezernentin / Dezernent: Beigeordneter Erika Beispiel",
        "Beratungsfolge:",
        "Gremium Sitzungsdatum Beratungsqualität",
        "Rat 09.11.2023 Entscheidung",
        "Bezirksvertretung 8 12.05.2022 Kenntnisnahme",
        "Beschlussdarstellung:",
        "Antrag:",
        "Der Rat beschließt den Neubau.",
        "Die Verwaltung wird beauftragt, zu prüfen.",
        "wir bitten Sie, folgenden Antrag zu beschließen:",
        "Die Verwaltung wird gebeten, folgende Fragen zu beantworten:",
        "Sachdarstellung:",
        "Begründung:",
        "Beschluss:",
        "Kosten: 5 EUR",
        "Finanzierung:",
        "Anlagen:",
        "Sehr geehrte Damen und Herren,",
        "Mit freundlichen Grüßen",
        "Fraktionsvorsitzender",
        "Text ohne Überschrift.",
        "zur Sitzung des Rates am 03.02.2022",
        "Beschlussvorlage",
        "Seite 2",
        "",
        "  ",
    ]
)
DOCUMENTS = st.tuples(
    st.lists(LINES, max_size=24),
    st.lists(st.sampled_from(["\n", PAGE_BREAK]), min_size=24, max_size=24),
)
PAPER_TYPES_LIST = ["Beschlussvorlage", "Antrag SPD", "Anfrage", "Informationsvorlage"]
PAPER_TYPES = st.sampled_from(PAPER_TYPES_LIST)


def _join(lines: list[str], breaks: list[str]) -> str:
    return "".join(line + brk for line, brk in zip(lines, breaks, strict=False))


@functools.cache
def _measurement() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "struktur_messung",
        Path(__file__).resolve().parents[2] / "docs/plans/11-struktur-messung.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("struktur_messung", module)
    spec.loader.exec_module(module)
    return module


@functools.cache
def _rules() -> StructureRules:
    return StructureRules.from_settings(load_settings(profile="duesseldorf", cwd=Path("/x")))


@settings(deadline=None)
@given(document=DOCUMENTS, paper_type=PAPER_TYPES)
def test_struktur_1_is_the_draft_of_the_measurement(
    document: tuple[list[str], list[str]], paper_type: str
) -> None:
    """Abschnitte, Kopffelder und Quellen wie ``analyse`` im Messskript, für jedes Dokument."""
    text = _join(*document)
    module = _measurement()
    old = module.analyse("d", text, module.Rules.load("duesseldorf"), paper_type)
    new = analyse_draft(text, _rules(), paper_type)

    def plain(spans: list[Any]) -> list[tuple[Any, ...]]:
        return [(s.start, s.end, s.kind, s.value, s.norm, s.section) for s in spans]

    assert [tuple(s) for s in new.sections] == plain(old.sections)
    assert [tuple(s) for s in new.head] == plain(old.head)
    assert new.sources == old.sources


@settings(deadline=None)
@given(document=DOCUMENTS, paper_type=PAPER_TYPES)
# hypothesis, 2026-11-24: der Beschlusssatz ohne Überschrift lag im Entwurf im Abschnitt des Amts
@example(
    document=(
        ["Fachbereich: 66 - Amt für Verkehrsmanagement", "Der Rat beschließt den Neubau."],
        ["\n"] * 24,
    ),
    paper_type="Beschlussvorlage",
)
def test_the_level_one_sections_never_overlap_and_stay_in_the_text(
    document: tuple[list[str], list[str]], paper_type: str
) -> None:
    text = _join(*document)
    found = analyse(text, _rules(), paper_type)
    level1 = [s for s in found.sections if s.norm == s.section]
    for span in (*found.sections, *found.head):
        assert 0 <= span.start < span.end <= len(text)
    for before, after in zip(level1, level1[1:], strict=False):
        assert before.end <= after.start
    for span in found.sections:
        if (
            span.norm != span.section
        ):  # Ebene 2: liegt in ihrem Abschnitt der Ebene 1 oder in keinem
            around = [s for s in level1 if s.start <= span.start < s.end]
            assert span.section == (around[0].norm if around else "")


@settings(deadline=None)
@given(document=DOCUMENTS, paper_type=PAPER_TYPES)
def test_page_breaks_and_line_breaks_separate_alike(
    document: tuple[list[str], list[str]], paper_type: str
) -> None:
    """Ob zwei Zeilen ein Zeilenumbruch oder ein Seitenwechsel trennt, ändert keinen Abschnitt."""
    lines, breaks = document
    with_pages = analyse(_join(lines, breaks), _rules(), paper_type)
    flat = analyse(_join(lines, ["\n"] * len(breaks)), _rules(), paper_type)
    assert with_pages.sections == flat.sections


# Für die Ebene 2 nur Zeilen ohne Fenster: Einleitungssätze und Beschlusssätze lesen die Zeilen
# davor oder die ersten Zeilen nach dem Kopf, und eine eingefügte Zeile verschöbe das Fenster.
PLAIN_LINES = LINES.filter(
    lambda line: (
        not line.startswith(("wir bitten", "Die Verwaltung", "Der Rat", "Kosten", "Finanz"))
    )
)


@settings(deadline=None)
@given(lines=st.lists(PLAIN_LINES, max_size=24), at=st.integers(0, 24))
def test_a_level_two_heading_splits_no_level_one_section(lines: list[str], at: int) -> None:
    """Eine Überschrift der Ebene 2 („Finanzierung:") teilt keinen Abschnitt der Ebene 1
    (Messdokument § 6, Tests): gegen dieselbe Zeile als Text („Finanzierung.", gleich lang) sind
    die Abschnitte der Ebene 1 dieselben, Rumpf eingeschlossen."""
    rules = _rules()
    heading = analyse("\n".join([*lines[:at], "Finanzierung:", *lines[at:]]), rules, "Anfrage")
    text = analyse("\n".join([*lines[:at], "Finanzierung.", *lines[at:]]), rules, "Anfrage")

    def level1(found: Structure) -> list[Found]:
        return [s for s in found.sections if s.norm == s.section]

    assert level1(heading) == level1(text)
    assert not any(s.norm == "finanzen" for s in text.sections)


@settings(deadline=None)
@given(document=DOCUMENTS, paper_type=PAPER_TYPES)
def test_the_analysis_is_the_same_on_a_second_run(
    document: tuple[list[str], list[str]], paper_type: str
) -> None:
    text = _join(*document)
    assert analyse(text, _rules(), paper_type) == analyse(text, _rules(), paper_type)


@given(name=st.text())
@example(name="Fläche in m²")  # georep run 2026-11-24, Profil 2014 bis 2020: int("²") warf
def test_the_name_key_takes_every_text(name: str) -> None:
    """Der Schlüssel eines Gremiumsnamens ist für jeden Text definiert und ändert sich nicht mehr."""
    key = name_key(name)
    assert name_key(key) == key


@functools.cache
def _rules_of(profile: str) -> StructureRules:
    return StructureRules.from_settings(load_settings(profile=profile, cwd=Path("/x")))


@settings(deadline=None)
@given(
    document=DOCUMENTS,
    paper_type=st.sampled_from([*PAPER_TYPES_LIST, "Vorlage aus der Politik"]),
    profile=st.sampled_from(["duesseldorf", "duesseldorf-2014"]),
)
# Review 11, K2 (2026-11-24): in 2014 bis 2020 kürzte die Nachbearbeitung acht
# Beschlussvorschläge auf „Antrag", weil der Betreff unter dem Formulartitel in ihnen begann
@example(
    document=(
        [
            "Fraktion im Rat",
            "Antrag:",
            "Antrag",
            "Mehr Bänke im Park",
            "",
            "Die Verwaltung wird beauftragt, im Park zehn Bänke aufzustellen.",
            "",
            "Begründung:",
            "Man will sitzen.",
        ],
        ["\n"] * 24,
    ),
    paper_type="Vorlage aus der Politik",
    profile="duesseldorf-2014",
)
def test_the_decision_proposal_stays_as_the_draft_found_it(
    document: tuple[list[str], list[str]], paper_type: str, profile: str
) -> None:
    """Die Nachbearbeitung (Rumpf, Überlappung) ändert keinen Beschlussvorschlag des Entwurfs:
    gerade er ist an den Labels geprüft (188 von 200)."""
    text = _join(*document)
    rules = _rules_of(profile)

    def decisions(found: Structure) -> list[tuple[int, int]]:
        return [(s.start, s.end) for s in found.sections if s.norm == "beschlussvorschlag"]

    assert decisions(analyse(text, rules, paper_type)) == decisions(
        analyse_draft(text, rules, paper_type)
    )
