"""Eigenschaften der Ausschnitte um eine Spanne (Fundament F3)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from georep.spans import excerpt


@st.composite
def text_and_span(draw: st.DrawFn) -> tuple[str, int, int, int]:
    text = draw(st.text(min_size=1, max_size=400))
    start = draw(st.integers(0, len(text) - 1))
    end = draw(st.integers(start + 1, len(text)))
    return text, start, end, draw(st.integers(0, 50))


@given(text_and_span())
def test_die_mitte_ist_die_spanne_und_der_rand_ist_begrenzt(
    case: tuple[str, int, int, int],
) -> None:
    text, start, end, context = case
    before, middle, after = excerpt(text, start, end, context)
    assert middle == text[start:end]
    assert len(before) <= context and len(after) <= context
    assert text[start - len(before) : end + len(after)] == before + middle + after
