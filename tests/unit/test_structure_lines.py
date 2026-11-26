"""Vorhaben 11: die Zeilen eines Rohtexts mit Positionen (``prep.raw_texts.split_lines``)."""

from __future__ import annotations

from georep.prep.raw_texts import split_lines


def test_newline_and_page_break_separate_lines() -> None:
    text = "Betrifft: Radweg\nFachbereich: 66\fSeite 2"
    assert split_lines(text) == [(0, 16), (17, 32), (33, 40)]
    assert [text[s:e] for s, e in split_lines(text)] == [
        "Betrifft: Radweg",
        "Fachbereich: 66",
        "Seite 2",
    ]


def test_an_empty_text_is_one_empty_line() -> None:
    assert split_lines("") == [(0, 0)]


def test_a_trailing_separator_ends_with_an_empty_line() -> None:
    assert split_lines("a\n") == [(0, 1), (2, 2)]


def test_carriage_return_is_part_of_the_line() -> None:
    """Wie im Messskript trennen nur ``\\n`` und ``\\f``; ein ``\\r`` bleibt in der Zeile."""
    assert split_lines("a\r\nb") == [(0, 2), (3, 4)]
