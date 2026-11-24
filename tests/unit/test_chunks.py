"""Vorhaben 18: Stücke nach ``18-stuecke-1`` an Beispielen (Bauplan § 6, ``docs/plans/18-einbettungen.md``)."""

from __future__ import annotations

import deal
import pytest

from georep.prep.chunks import Chunk, chunk_lines, chunk_text, chunk_title, split_chunks


def test_blank_lines_and_page_breaks_separate_lines_and_vanish() -> None:
    raw = "Kopf  \n\n   \fZweite Zeile\n\t\nDritte"
    assert chunk_lines(raw, 100) == [(0, 4), (12, 24), (27, 33)]
    assert [raw[s:e] for s, e in chunk_lines(raw, 100)] == ["Kopf", "Zweite Zeile", "Dritte"]
    assert split_chunks("T", raw, 100, 10) == [Chunk("Kopf\nZweite Zeile\nDritte", 0, 33)]


def test_a_line_over_the_budget_breaks_at_the_last_space_or_hard() -> None:
    # Budget 6: „aaa bbb" bricht an der Leerstelle, „cccccccccc" ohne Leerstelle hart nach 6
    raw = "aaa bbb cccccccccc"
    assert [raw[s:e] for s, e in chunk_lines(raw, 6)] == ["aaa", "bbb", "cccccc", "cccc"]
    assert chunk_lines(raw, 6) == [(0, 3), (4, 7), (8, 14), (14, 18)]


def test_the_next_chunk_repeats_the_last_lines_up_to_the_overlap() -> None:
    raw = "eins\nzwei\ndrei\nvier\nfuenf"
    # Rumpfbudget 14 - 0 - 2 = 12: „eins\nzwei" (9), „+\ndrei" wäre 14 > 12
    chunks = split_chunks("", raw, 14, 4)
    assert [c.body for c in chunks] == ["eins\nzwei", "zwei\ndrei", "drei\nvier", "vier\nfuenf"]
    # ohne Überlappung beginnt jedes Stück mit einer neuen Zeile
    assert [c.body for c in split_chunks("", raw, 14, 0)] == ["eins\nzwei", "drei\nvier", "fuenf"]
    assert [(c.start, c.end) for c in chunks] == [(0, 9), (5, 14), (10, 19), (15, 25)]


def test_a_long_title_leaves_less_room_for_the_body() -> None:
    raw = "abc def ghi"
    assert [c.body for c in split_chunks("", raw, 9, 0)] == ["abc def", "ghi"]
    assert [c.body for c in split_chunks("Titel", raw, 9, 0)] == ["ab", "c", "de", "f", "gh", "i"]
    with pytest.raises(deal.PreContractError):
        split_chunks("Titel", raw, 7, 0)  # kein Zeichen für den Rumpf


def test_whitespace_alone_gives_no_chunk() -> None:
    assert split_chunks("T", " \n\f\t\xa0", 1600, 200) == []
    assert split_chunks("T", "", 1600, 200) == []


def test_the_title_is_collapsed_and_cut_like_the_measurement() -> None:
    assert chunk_title("  Antrag\n der   SPD ", 200) == "Antrag der SPD"
    assert chunk_title(None, 200) == ""
    # geschnitten nach dem Zusammenziehen; ein Leerzeichen am Schnitt bleibt (so steht es im Cache)
    assert chunk_title("ab cd", 3) == "ab "


def test_the_model_sees_prefix_title_blank_line_body() -> None:
    assert chunk_text("search_document: ", "Titel", "Rumpf") == "search_document: Titel\n\nRumpf"


def test_the_measured_sizes_hold_for_a_long_document() -> None:
    """Die Werte der Messung: 1 600 Zeichen samt Titel, 200 Zeichen Überlappung."""
    raw = "\n".join(f"Zeile {i} " + "x" * (i % 90) for i in range(400))
    title = chunk_title("Ein Titel von mittlerer Länge " * 3, 200)
    chunks = split_chunks(title, raw, 1600, 200)
    assert len(chunks) > 10
    assert all(len(title) + 2 + len(c.body) <= 1600 for c in chunks)
    assert chunks[0].start == 0 and chunks[-1].end == len(raw)
