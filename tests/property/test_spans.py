"""Eigenschaften der Ausschnitte um eine Spanne und der Folge der Spannen (Fundament F3)."""

from __future__ import annotations

from random import Random

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.spans import SPAN_SCHEMA, check_spans, excerpt, sort_spans


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


# --- Nachzug F3: Zusatzspalten hinter den acht (Synergien 2026-11, Konflikt 3) ------------------

LENGTHS = {"a": 7, "b": 30, "c": 1}
EXTRA_TYPES: dict[str, pl.DataType] = {
    "attr": pl.String(),
    "zeile": pl.UInt32(),
    "ja": pl.Boolean(),
}


@st.composite
def span_rows(draw: st.DrawFn) -> dict[str, object]:
    key = draw(st.sampled_from(sorted(LENGTHS)))
    start = draw(st.integers(0, LENGTHS[key] - 1))
    end = draw(st.integers(start + 1, LENGTHS[key]))
    return {
        "id": key,
        "start": start,
        "end": end,
        "kind": draw(st.sampled_from(["betrag", "abschnitt", "ort"])),
        "value": "",
        "norm": draw(st.sampled_from(["", "1.5"])),
        "section": draw(st.sampled_from(["", "kopf"])),
        "extractor": draw(st.sampled_from(["probe", "roh"])),
        "attr": draw(st.one_of(st.none(), st.sampled_from(["kopf", "dezimal"]))),
        "zeile": draw(st.integers(0, 3)),
        "ja": draw(st.booleans()),
    }


@st.composite
def spans_with_extras(draw: st.DrawFn) -> tuple[pl.DataFrame, list[str]]:
    """Spannen in beliebiger Zeilenfolge, mit null bis drei Zusatzspalten in beliebiger Folge;
    auch die acht stehen in beliebiger Spaltenfolge (``sort_spans`` ordnet sie)."""
    rows = draw(st.lists(span_rows(), max_size=12))
    extras = draw(st.lists(st.sampled_from(sorted(EXTRA_TYPES)), unique=True, max_size=3))
    schema = {**SPAN_SCHEMA, **{name: EXTRA_TYPES[name] for name in extras}}
    frame = pl.DataFrame(
        [{name: row[name] for name in schema} for row in rows], schema=schema, orient="row"
    )
    columns = draw(st.permutations(list(schema)))
    return frame.select(columns), extras


@given(spans_with_extras())
def test_zusatzspalten_stehen_hinter_den_acht_und_aendern_die_folge_nicht(
    case: tuple[pl.DataFrame, list[str]],
) -> None:
    """``sort_spans`` behält jede Zusatzspalte hinter den acht, in ihrer Folge in der Eingabe, und
    ordnet die Zeilen genau wie ohne sie; ``check_spans`` nimmt das Ergebnis an."""
    frame, extras = case
    ordered = sort_spans(frame)
    in_input = [name for name in frame.columns if name not in SPAN_SCHEMA]
    assert ordered.columns == [*SPAN_SCHEMA, *in_input]
    assert sorted(in_input) == sorted(extras)
    assert ordered.select(list(SPAN_SCHEMA)).equals(sort_spans(frame.select(list(SPAN_SCHEMA))))
    # jede Zeile behält ihre Zusatzwerte: dieselbe Menge ganzer Zeilen vor und nach dem Sortieren
    assert sorted(map(repr, ordered.rows())) == sorted(
        map(repr, frame.select(ordered.columns).rows())
    )
    check_spans(ordered, LENGTHS)


@given(st.lists(span_rows(), max_size=12), st.randoms(use_true_random=False))
def test_die_folge_haengt_nicht_an_der_folge_der_eingabe(
    rows: list[dict[str, object]], random: Random
) -> None:
    """Review F7, N2: zwei Spannen mit gleichem ``id, start, end, kind`` (etwa aus zwei
    Extraktoren) stehen nach ``sort_spans`` in derselben Folge, wie auch immer sie kamen."""
    frame = pl.DataFrame(
        [{name: row[name] for name in SPAN_SCHEMA} for row in rows],
        schema=SPAN_SCHEMA,
        orient="row",
    )
    shuffled = list(range(frame.height))
    random.shuffle(shuffled)
    assert sort_spans(frame[shuffled]).equals(sort_spans(frame))
