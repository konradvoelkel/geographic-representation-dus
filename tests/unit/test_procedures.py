"""Kanten, Vorgänge und Antworten an einer kleinen Stadt mit bekannten Kanten (Vorhaben 14).

Die Stadt steht in ``tests/procedures_city.py``: vierzehn eigene Drucksachen und zwei einer
Nachbarperiode, je mit dem Grund, aus dem sie eine Kante hat oder keine. Dazu die Rückfallregel
(stark aus Titel, Anlage, Nachtragsnummer, Sammelbericht; Text schwach) und die beiden bekannten
Fehler der Validierung als dokumentierte Grenze.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import deal
import polars as pl
import pytest

from georep.analysis.procedures import (
    EDGE_SCHEMA,
    OWN,
    CycleError,
    answer_times,
    assemble_edges,
    build_directory,
    document_roles,
    forest,
    onto_raw,
    parents,
    questions_of,
    scan,
    strong_candidates,
    supplement_pairs,
)
from georep.prep.raw_texts import flatten_with_offsets
from georep.prep.references import ReferenceRules
from georep.settings import load_settings
from georep.spans import SPAN_SCHEMA, check_spans
from tests.procedures_city import (
    ANSWERS,
    DOCUMENTS,
    EDGES,
    FOREST,
    OWN_IDS,
    attachments,
    documents,
)

RULES = ReferenceRules.from_settings(load_settings(cwd=Path("/nonexistent")).procedures)


def _edges() -> pl.DataFrame:
    docs = documents()
    directory = build_directory(docs, RULES)
    found = scan(docs, directory, RULES)
    return assemble_edges(
        found.occurrences, supplement_pairs(directory), document_roles(docs, RULES)
    )


def test_every_known_edge_comes_out_and_no_other() -> None:
    expected = pl.DataFrame(EDGES, schema=EDGE_SCHEMA, orient="row")
    assert _edges().equals(expected)


def test_only_text_is_weak_under_the_fallback_rule() -> None:
    """Rückfallregel (Messdokument § 5.1): stark aus Titel, Anlage, Nummer, Sammelbericht."""
    edges = _edges()
    assert set(edges.filter("stark").get_column("quelle")) == {
        "titel",
        "nummer",
        "anlage",
        "sammelbericht",
    }
    weak = edges.filter(~pl.col("stark"))
    assert weak.select("von", "nach", "quelle").rows() == [("p05", "p02", "text")]


def test_spans_are_text_positions_of_every_number() -> None:
    """Spannen nur für Stellen im Text (Konflikt 1), auch eigene und unbekannte Nummern."""
    docs = documents().filter(pl.col("periode") == OWN)
    directory = build_directory(documents(), RULES)
    extractors = {doc_id: "probe/drucksachen-1" for doc_id in OWN_IDS}
    spans = scan(docs, directory, RULES, extractors).spans
    assert spans.schema == pl.Schema(SPAN_SCHEMA)
    assert spans.select("id", "value", "norm").rows() == [
        ("p05", "ova/2/2021", "OVA/2/2021"),
        ("p06", "rat/1/2021", "RAT/1/2021"),
        ("p14", "rat/13/2021", "RAT/13/2021"),
    ]
    assert set(spans.get_column("section")) == {""}
    lengths = dict(docs.select("id", pl.col("text").str.len_chars().cast(pl.Int64)).iter_rows())
    check_spans(spans, lengths)


def test_the_forest_spans_the_neighbouring_period() -> None:
    docs = documents()
    tree = parents(_edges(), document_roles(docs, RULES))
    found = forest(tree, docs.get_column("id").to_list(), OWN_IDS)
    assert found.rows() == FOREST


def test_answers_come_from_attachments_and_answering_papers() -> None:
    docs = documents()
    roles = document_roles(docs, RULES)
    questions = docs.filter(pl.col("id").is_in(questions_of(roles))).select(
        "id", "date", pl.lit("BV1").alias("gremium")
    )
    found = answer_times(questions, attachments(), _edges(), roles, RULES, [dt.date(2019, 7, 3)])
    assert found.rows() == ANSWERS


def test_an_answer_before_its_question_keeps_its_date_but_no_days() -> None:
    docs = documents()
    roles = document_roles(docs, RULES)
    early = attachments().with_columns(
        pl.when(pl.col("id") == "p07")
        .then(pl.lit([{"name": "Antwort", "datum": dt.date(2021, 1, 1)}]))
        .otherwise(pl.col("anlagen"))
        .alias("anlagen")
    )
    questions = docs.filter(pl.col("id") == "p07").select(
        "id", "date", pl.lit("BV1").alias("gremium")
    )
    (row,) = answer_times(questions, early, _edges(), roles, RULES).rows(named=True)
    assert row["antwort_datum"] == dt.date(2021, 1, 1) and row["tage"] is None


def test_strong_candidates_are_the_papers_that_can_have_a_strong_edge() -> None:
    docs = documents()
    directory = build_directory(docs, RULES)
    assert strong_candidates(docs, directory, RULES) == {
        "n02",
        "p02",
        "p03",
        "p04",
        "p06",
        "p08",
        "p12",
        "p13",
    }


def test_a_same_day_edge_points_only_to_a_smaller_id() -> None:
    """Zwei Drucksachen vom selben Tag, die einander nennen, wären sonst ein Kreis."""
    roles = pl.DataFrame(
        {
            "id": ["a", "b"],
            "periode": ["", ""],
            "date": [dt.date(2021, 1, 1)] * 2,
            "rolle": ["antrag", "antrag"],
            "sammelbericht": [False, False],
        }
    )
    edges = pl.DataFrame(
        [
            ("a", "b", "aenderung", ["titel"], True, "titel", 0, ""),
            ("b", "a", "aenderung", ["titel"], True, "titel", 0, ""),
        ],
        schema=EDGE_SCHEMA,
        orient="row",
    )
    assert parents(edges, roles) == {"b": ("a", "aenderung")}


def test_a_cycle_is_an_error() -> None:
    with pytest.raises(CycleError):
        forest({"a": ("b", "x"), "b": ("a", "x")}, ["a", "b"], ["a"])


@pytest.mark.parametrize(
    ("title", "attachment", "case"),
    [
        # e7a023ba6de0: ein Bauantrag führt den des Nachbargrundstücks als Anlage (Vergleichsfall)
        ("Bauantrag Kronenstraße 31", "Bauantrag OVA/2/2021 Nachbargrundstück", "anlage"),
        # 883a584c6d63: der Titel nennt einen Mittelbeschluss nur als Finanzierungsquelle
        ("Bänke, finanziert aus OVA/2/2021", "", "titel"),
    ],
)
def test_the_two_known_errors_stay_strong(title: str, attachment: str, case: str) -> None:
    """Die zwei Fehler der Rückfallregel an beiden Stichproben (104 / 106, § 5.1) sind beide
    ``bezug`` und stark; die Regel kennt kein Zeichen, das sie trennte (Frage 9.14, Fassung .3)."""
    docs = documents()
    probe = pl.DataFrame(
        [
            (
                "z99",
                "",
                "OVA/50/2021",
                title,  # Spalten in der Folge von DOCUMENT_SCHEMA: Titel vor Dokumentart
                "Beschlussvorlage",
                dt.date(2021, 9, 1),
                "",
                [attachment] if attachment else [],
            )
        ],
        schema=docs.schema,
        orient="row",
    )
    city = pl.concat([docs, probe])
    directory = build_directory(city, RULES)
    edges = assemble_edges(
        scan(probe, directory, RULES).occurrences, [], document_roles(city, RULES)
    )
    assert edges.select("von", "nach", "typ", "stark", "quelle").rows() == [
        ("z99", "p02", "bezug", True, case)
    ]


# --- Nachzug F7: die Spannen liegen auf dem Rohtext ---------------------------------------------


def test_spans_move_onto_the_raw_text_where_it_flattens_to_the_store() -> None:
    """Über ``flatten_with_offsets`` (Punkt 74): dieselbe Stelle, im Rohtext gezählt, wörtlich.

    Eine Nummer über einen Zeilenumbruch ist im Rohtext eine Spanne mit dem Umbruch darin; der
    Kopf vor dem Marker und die Großschreibung stehen nur dort.
    """
    raw = "Vorlagenkopf RAT/0/2000\fBetrifft: Antrag zu RAT/1/\n2021 und\nOVA/2/2021"
    text, offsets = flatten_with_offsets(raw, "betrifft", ())
    doc_id, period, number, kind, title, day, _text, _files = DOCUMENTS[4]  # p05
    files: list[str] = []
    row = (doc_id, period, number, title, kind, day, text, files)  # Folge von DOCUMENT_SCHEMA
    docs = pl.DataFrame([row], schema=documents().schema, orient="row")
    directory = build_directory(documents(), RULES)
    store = scan(docs, directory, RULES, {"p05": "probe/drucksachen-1"}).spans
    assert store.get_column("value").to_list() == ["rat/1/2021", "ova/2/2021"]
    moved = onto_raw(store, {"p05": (raw, offsets, "probe+roh")})
    assert moved.get_column("value").to_list() == ["RAT/1/\n2021", "OVA/2/2021"]
    assert set(moved.get_column("extractor")) == {"probe+roh/drucksachen-1"}
    for start, end, value in moved.select("start", "end", "value").iter_rows():
        assert raw[start:end] == value
    check_spans(moved, {"p05": len(raw)})


def test_a_document_without_raw_text_keeps_its_store_spans() -> None:
    """Ohne Rohtext (Pages hat ihn nur für die Hauptperiode) bleibt die Spanne auf dem Textstore,
    und ``extractor`` sagt es."""
    docs = documents().filter(pl.col("periode") == OWN)
    directory = build_directory(documents(), RULES)
    store = scan(
        docs, directory, RULES, {doc_id: "probe/drucksachen-1" for doc_id in OWN_IDS}
    ).spans
    assert onto_raw(store, {}).equals(store)


def test_the_forest_has_one_row_per_document_and_refuses_a_twin() -> None:
    """Review K2: ``dokumente_vorgang`` folgt dem Vertrag aller ``dokumente_<attribut>``
    (``contracts.one_row_per_document``); eine doppelte ID ist ein Programmierfehler, kein Fall
    zum stillen Zusammenlegen."""
    assert forest({}, ["a", "b"], ["b", "a"]).get_column("id").to_list() == ["a", "b"]
    with pytest.raises(deal.ContractError):
        forest({}, ["a"], ["a", "a"])
