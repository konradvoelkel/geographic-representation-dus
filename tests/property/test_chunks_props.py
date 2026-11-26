"""Vorhaben 18: die Stücke für das Einbettungsmodell, als Eigenschaften über beliebige Rohtexte.

Bauplan ``docs/plans/18-einbettungen.md``, § 6: jedes Stück hat ohne Präfix höchstens
``chunk_chars`` Zeichen; jede Zeile des Rohtexts (ohne Leerraum) steht in mindestens einem Stück;
die Überlappung zweier benachbarter Stücke ist höchstens ``overlap_chars``. Dazu die Treue zur
Messung: die Rümpfe sind die des ``zerteile`` aus dem Messskript (``oracle_chunks.py``), denn zu
genau ihnen liegen die Vektoren im Modellcache.
"""

from __future__ import annotations

from hypothesis import example, given
from hypothesis import strategies as st

from georep.prep.chunks import TITLE_SEPARATOR, chunk_lines, chunk_text, chunk_title, split_chunks
from tests.property.oracle_chunks import titel_von, zeilen_von, zerteile

# Zeilenenden aller Art, Leerraum, den ``strip`` kennt, aber ``rfind(" ")`` nicht (Tab, NBSP), und
# Wörter verschiedener Länge, damit Zeilen über dem Budget an einer Leerstelle oder hart brechen.
PIECES = st.sampled_from(
    ["a", "bb", "Wort", "Langeswortohneleerstelle", " ", "  ", "\n", "\f", "\t", "\xa0", "\r", "ä"]
)
RAW = st.lists(PIECES, max_size=60).map("".join)
TITLES = st.text(st.sampled_from("ab \n\t"), max_size=8)


@st.composite
def budgets(draw: st.DrawFn) -> tuple[str, int, int]:
    """Ein Titel, ``chunk_chars`` mit einem Rumpfbudget von 1 bis 30 und eine Überlappung."""
    title = titel_von(draw(TITLES))
    chunk_chars = len(title) + len(TITLE_SEPARATOR) + draw(st.integers(1, 30))
    return title, chunk_chars, draw(st.integers(0, 20))


@given(raw=RAW, setting=budgets())
@example(raw="  xx yy", setting=("", 5, 0))  # führender Leerraum vor der ersten Leerstelle
@example(raw="a\fb\n\nc", setting=("t", 6, 3))
def test_the_bodies_are_those_of_the_measurement(raw: str, setting: tuple[str, int, int]) -> None:
    title, chunk_chars, overlap = setting
    bodies = [c.body for c in split_chunks(title, raw, chunk_chars, overlap)]
    assert bodies == zerteile(title, raw, chunk_chars, overlap)


@given(raw=RAW, budget=st.integers(1, 30))
def test_each_line_is_a_piece_of_the_raw_text(raw: str, budget: int) -> None:
    """``raw[start:end]`` ist die Zeile der Messung; daran hängen ``start`` und ``end`` der Stücke."""
    assert [raw[s:e] for s, e in chunk_lines(raw, budget)] == zeilen_von(raw, budget)


@given(raw=RAW, setting=budgets())
def test_every_chunk_fits_and_every_line_is_in_one(raw: str, setting: tuple[str, int, int]) -> None:
    title, chunk_chars, overlap = setting
    chunks = split_chunks(title, raw, chunk_chars, overlap)
    spans = chunk_lines(raw, chunk_chars - len(title) - 2)
    for chunk in chunks:
        assert len(chunk_text("", title, chunk.body)) <= chunk_chars
        # der Rumpf sind genau die Zeilen im Bereich des Stücks, verbunden mit ``\n``
        inside = [raw[s:e] for s, e in spans if chunk.start <= s and e <= chunk.end]
        assert chunk.body == "\n".join(inside) != ""
    # jede Zeile (ohne Leerraum) steht in mindestens einem Stück
    for start, end in spans:
        assert any(c.start <= start and end <= c.end for c in chunks), (start, end)
    assert len(chunks) <= len(spans)
    assert (chunks == []) == (raw.strip() == "")


@given(raw=RAW, setting=budgets())
def test_two_neighbouring_chunks_share_at_most_the_overlap(
    raw: str, setting: tuple[str, int, int]
) -> None:
    """Gemeinsam sind die Zeilen im Bereich beider; zusammen mit ihren Umbrüchen höchstens ``overlap``."""
    title, chunk_chars, overlap = setting
    spans = chunk_lines(raw, chunk_chars - len(title) - 2)
    chunks = split_chunks(title, raw, chunk_chars, overlap)
    for first, second in zip(chunks, chunks[1:], strict=False):
        shared = [
            e - s for s, e in spans if first.start <= s and e <= first.end and second.start <= s
        ]
        assert sum(shared) + max(0, len(shared) - 1) <= overlap
        assert first.start < second.start and first.end < second.end


@given(name=st.one_of(st.none(), st.text(max_size=40)), limit=st.integers(0, 30))
def test_the_title_is_the_title_of_the_measurement(name: str | None, limit: int) -> None:
    assert chunk_title(name, limit) == titel_von(name, limit)
