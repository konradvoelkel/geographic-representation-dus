"""Vorhaben 11: Zeilen, Abschnitte und das Lesen einer Spanne, für jede Eingabe.

Die Bausteine, die 11 für andere Vorhaben mitbringt (``docs/plans/11-struktur.md``, § 10, Punkt 3):
``split_lines`` in ``prep/raw_texts.py``, ``read_span`` und ``section_of`` in ``georep.spans``.
"""

from __future__ import annotations

from hypothesis import example, given
from hypothesis import strategies as st

from georep.prep.raw_texts import PAGE_BREAK, split_lines

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
