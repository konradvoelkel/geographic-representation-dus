"""Vorhaben 11: Zeilen, Abschnitte und das Lesen einer Spanne, für jede Eingabe.

Die Bausteine, die 11 für andere Vorhaben mitbringt (``docs/plans/11-struktur.md``, § 10, Punkt 3):
``split_lines`` in ``prep/raw_texts.py``, ``read_span`` und ``section_of`` in ``georep.spans``.
"""

from __future__ import annotations

import re

import polars as pl
from hypothesis import example, given
from hypothesis import strategies as st

from georep.prep.raw_texts import PAGE_BREAK, split_lines
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
