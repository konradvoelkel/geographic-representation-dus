"""Eigenschaften der Urheber-Zuordnung: Partition, Teilmengen, Groß- und Kleinschreibung, Kopf."""

from __future__ import annotations

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.parties import (
    ART,
    PARTEIEN,
    QUELLE,
    QUELLEN,
    URHEBER_ARTEN,
    Patterns,
    classify_document,
    classify_originators,
)
from georep.settings import Originators, Settings

# Bausteine, aus denen echte Titel und Typen bestehen: Antragsarten, Parteinamen, Rauschen.
WORDS = (
    "antrag",
    "anfrage",
    "haushaltsantrag",
    "beschlussvorlage",
    "eingabe nach 24go",
    "cdu",
    "spd",
    "fdp",
    "afd",
    "die linke",
    "grüne",
    "bündnis 90",
    "tierschutz",
    "die partei",
    "volt",
    "fraktion",
    "ratsfraktion",
    "interfraktionell",
    "bezirksvertreterin",
    "herrn",
    "tempo 30",
    "kalkumer schloss",
    "betrifft",
    "/",
    "-",
    ",",
    " vom 3. august 2023",
)
phrases = st.lists(st.sampled_from(WORDS), max_size=8).map(" ".join)


@pytest.fixture(scope="module")
def originators(default_settings: Settings) -> Originators:
    return default_settings.originators


@pytest.fixture(scope="module")
def patterns(originators: Originators) -> Patterns:
    return Patterns.from_settings(originators)


@given(paper_type=phrases, name=phrases, text=phrases)
def test_every_document_lands_in_exactly_one_class(
    patterns: Patterns, paper_type: str, name: str, text: str
) -> None:
    """Die Partition und die Teilmengen gelten für jede Eingabe, auch für Unsinn."""
    found = classify_document(paper_type, name, text, patterns)
    assert found.art in URHEBER_ARTEN and found.quelle in QUELLEN
    assert set(found.parteien) <= set(patterns.keys)
    assert list(found.parteien) == sorted(set(found.parteien), key=patterns.keys.index)
    if found.art != "Fraktion":
        assert found.parteien == ()
    if found.quelle == "":
        assert found.art == "unbekannt" and found.treffer == ""


@given(paper_type=phrases, name=phrases, text=phrases)
def test_the_title_is_read_case_insensitively(
    patterns: Patterns, paper_type: str, name: str, text: str
) -> None:
    """Nur der Titel wird kleingeschrieben verglichen; ``paper_type`` ist ein ganzer Wert."""
    plain = classify_document(paper_type, name, text, patterns)
    loud = classify_document(paper_type, name.upper(), text, patterns)
    assert (plain.art, plain.parteien, plain.quelle) == (loud.art, loud.parteien, loud.quelle)


@given(paper_type=phrases, name=phrases, head=phrases, tail=phrases)
def test_text_beyond_the_head_changes_nothing(
    patterns: Patterns, paper_type: str, name: str, head: str, tail: str
) -> None:
    short = head[: patterns.head_chars]
    padded = short + " " + "z" * patterns.head_chars + " " + tail
    one = classify_document(paper_type, name, short, patterns)
    other = classify_document(paper_type, name, padded, patterns)
    # Die Klasse, die Parteien und die Quelle sind gleich; ``treffer`` ist ein Auszug mit Umgebung
    # und darf die Füllzeichen rechts vom Treffer mitnehmen.
    assert (one.art, one.parteien, one.quelle) == (other.art, other.parteien, other.quelle)


@given(
    rows=st.lists(
        st.tuples(
            st.text(alphabet="abc0123456789", min_size=1, max_size=5), phrases, phrases, phrases
        ),
        max_size=12,
    )
)
def test_the_batch_keeps_one_row_per_document_in_order(
    originators: Originators, rows: list[tuple[str, str, str, str]]
) -> None:
    """``classify_originators`` liefert genau die Korpus-IDs, sortiert, und stimmt mit der
    Einzelfunktion überein (der Batch rechnet nichts anderes als die Schleife)."""
    by_id = {row[0]: row for row in rows}
    corpus = pl.DataFrame(
        {
            "id": list(by_id),
            "paper_type": [r[1] for r in by_id.values()],
            "name": [r[2] for r in by_id.values()],
            "text": [r[3] for r in by_id.values()],
        },
        schema={"id": pl.String, "paper_type": pl.String, "name": pl.String, "text": pl.String},
    )
    found = classify_originators(corpus, originators)
    assert found.get_column("id").to_list() == sorted(by_id)
    patterns = Patterns.from_settings(originators)
    for row in found.iter_rows(named=True):
        _, paper_type, name, text = by_id[row["id"]]
        one = classify_document(paper_type, name, text, patterns)
        assert (row[ART], tuple(row[PARTEIEN]), row[QUELLE]) == (one.art, one.parteien, one.quelle)
