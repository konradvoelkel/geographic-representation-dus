"""Eigenschaften der Urheber-Zuordnung: Partition, Teilmengen, Groß- und Kleinschreibung, Kopf."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.hits import DISTRICT
from georep.analysis.parties import (
    ART,
    KLASSEN_SPALTEN,
    PARTEIEN,
    QUELLE,
    QUELLEN,
    URHEBER_ARTEN,
    Patterns,
    classify_document,
    classify_originators,
    originators_by_district,
    party_hits,
)
from georep.settings import Originators, Settings, load_settings

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
    # Review 2026-10-14: die Formen, mit denen Mönchengladbach arbeitet
    "3 - fraktionsantrag",
    "6.1 - mitgliederantrag",
    "1.1 - beratungsvorlage",
    "hier:",
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


# Review 2026-10-14: die Eigenschaften müssen für **beide** Konfigurationsformen gelten. Düsseldorf
# leitet die Klasse aus Antragspräfix, Titel und Textkopf ab und bringt einen Briefkopfmarker mit;
# Mönchengladbach entscheidet sie allein aus der Dokumentart (``fraction_types``, ``person_types``)
# und schneidet den Titel an seinem Bezugsmarker. Beide Profile liegen im Paket, also sind es die
# echten Regelsätze und keine erfundenen.
PROFILES = ("duesseldorf", "moenchengladbach")


@pytest.fixture(scope="module", params=PROFILES)
def originators(request: pytest.FixtureRequest) -> Originators:
    return load_settings(profile=str(request.param), cwd=Path("/nonexistent")).originators


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


# --- Kennzahlen: Partition, Schranken, Konstanz ----------------------------------------------------

ids = st.text(alphabet="abcde", min_size=1, max_size=2)
arten = st.sampled_from(URHEBER_ARTEN)


@st.composite
def corpora(draw: st.DrawFn) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, list[str]]:
    """Zufällige Dokumente mit Zuordnung, zufällige Trefferlisten je Bezirk, passende Wählerzeilen."""
    keys = ["CDU", "SPD"]
    document_ids = sorted(draw(st.lists(ids, min_size=1, max_size=8, unique=True)))
    rows = []
    for document in document_ids:
        art = draw(arten)
        parteien = (
            sorted(draw(st.lists(st.sampled_from(keys), max_size=2, unique=True)))
            if art == "Fraktion"
            else []
        )
        rows.append((document, art, parteien))
    documents = pl.DataFrame(
        rows,
        schema={"id": pl.String, ART: pl.String, PARTEIEN: pl.List(pl.String)},
        orient="row",
    )
    districts = draw(st.lists(st.integers(1, 5), min_size=1, max_size=4, unique=True))
    hits = [
        sorted(draw(st.lists(st.sampled_from(document_ids), max_size=5, unique=True)))
        for _ in districts
    ]
    results = pl.DataFrame(
        {
            DISTRICT: sorted(districts),
            "paper_ids": [h for _, h in sorted(zip(districts, hits, strict=True))],
        },
        schema={DISTRICT: pl.Int64, "paper_ids": pl.List(pl.String)},
    ).with_columns(pl.col("paper_ids").list.len().cast(pl.Int64).alias("anzahl_treffer"))
    voters = pl.DataFrame(
        {
            DISTRICT: sorted(districts),
            "Wahlberechtigte_insgesamt": [1000] * len(districts),
            "CDU_Stimmen": [draw(st.integers(0, 400)) for _ in districts],
            "SPD_Stimmen": [draw(st.integers(0, 400)) for _ in districts],
        },
        schema={
            DISTRICT: pl.Int64,
            "Wahlberechtigte_insgesamt": pl.Int64,
            "CDU_Stimmen": pl.Int64,
            "SPD_Stimmen": pl.Int64,
        },
    ).with_columns(
        (pl.col("CDU_Stimmen") / 800).alias("CDU_anteil"),
        (pl.col("SPD_Stimmen") / 800).alias("SPD_anteil"),
    )
    return results, documents, voters, keys


@given(data=corpora())
def test_the_partition_and_the_bounds_hold_for_random_data(
    default_settings: Settings, data: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, list[str]]
) -> None:
    """Die Verträge der beiden Batch-Funktionen gelten für beliebige Zuordnungen und Trefferlisten
    (die Laufzeitverträge selbst prüfen hier mit; ein Gegenbeispiel wäre ein ContractError)."""
    results, documents, voters, keys = data
    by_district = originators_by_district(results, documents)
    assert by_district.height == results.height
    for row in by_district.iter_rows(named=True):
        assert sum(row[c] for c in KLASSEN_SPALTEN) == row["anzahl_treffer"]

    parties = [p for p in default_settings.originators.parties if p.key in keys]
    table = party_hits(results, documents, voters, parties)
    assert table.height == results.height * len(parties)
    totals = {key: documents.filter(pl.col(PARTEIEN).list.contains(key)).height for key in keys}
    for row in table.iter_rows(named=True):
        assert 0 <= row["treffer_allein"] <= row["anzahl_treffer"] <= row["dokumente_partei"]
        assert row["dokumente_partei"] == totals[row["partei"]]
        assert 0.0 <= row["anteil_dokumente"] <= 1.0
        assert row["angetreten"] == (row["stimmen"] > 0)
    # Die Treffer einer Partei im Bezirk können nie mehr sein als die Treffer des Bezirks
    joined = table.join(results.select(DISTRICT, "anzahl_treffer"), on=DISTRICT, suffix="_bezirk")
    assert (
        joined.select(pl.col("anzahl_treffer") <= pl.col("anzahl_treffer_bezirk")).to_series().all()
    )
