"""Handbeispiele der Gewichtung: kleine Frames, nachgerechnete Zahlen.

Die Eigenschaften, die für alle Eingaben gelten, stehen in ``tests/property/test_weights_props.py``;
hier steht, was die Formel in einem Fall tun soll, den man im Kopf nachrechnet.
"""

from __future__ import annotations

import math

import polars as pl
import pytest

from georep.analysis.hits import hits_by_district, join_voters
from georep.analysis.weights import (
    BY_DISTRICTS,
    BY_IDF,
    COMBINED,
    UNIT,
    TypeRules,
    district_weight,
    document_pairs,
    document_weights,
    idf_expression,
    idf_weight,
    paper_type_weights,
    term_weights,
    topic_count,
    topic_variant,
    variants,
    weighted_hits,
)
from georep.errors import EmptyResultError
from georep.settings import FIXED_VARIANTS, TOPIC_PREFIX, load_settings

ELIGIBLE = "Wahlberechtigte_insgesamt"


def _dictionary(rows: dict[int, list[str]]) -> pl.DataFrame:
    return pl.DataFrame(
        {"wahlkreis_id": list(rows), "suchbegriffe": [sorted(v) for v in rows.values()]},
        schema={"wahlkreis_id": pl.Int64, "suchbegriffe": pl.List(pl.String)},
    )


def _index(rows: dict[str, list[str]]) -> pl.DataFrame:
    terms = sorted(rows)
    return pl.DataFrame(
        {"suchbegriffe": terms, "paper_ids": [sorted(rows[t]) for t in terms]},
        schema={"suchbegriffe": pl.String, "paper_ids": pl.List(pl.String)},
    ).with_columns(pl.col("paper_ids").list.len().cast(pl.Int64).alias("anzahl_treffer"))


def _voters(districts: list[int], eligible: int = 100) -> pl.DataFrame:
    return pl.DataFrame(
        {"wahlkreis_id": districts, ELIGIBLE: [eligible] * len(districts)},
        schema={"wahlkreis_id": pl.Int64, ELIGIBLE: pl.Int64},
    )


def _types(rows: dict[str, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {"id": list(rows), "paper_type": list(rows.values())},
        schema={"id": pl.String, "paper_type": pl.String},
    )


def test_variant_names_match_the_reserved_names_of_the_settings() -> None:
    """Ein Regelsatz in den Settings darf keinen der festen Namen tragen; beide Listen müssen passen."""
    assert FIXED_VARIANTS == (UNIT, BY_DISTRICTS, BY_IDF, COMBINED)
    assert topic_variant(7) == f"{TOPIC_PREFIX}07" == "thema_07"
    assert topic_variant(19) == "thema_19"


def test_district_weight_splits_a_term_between_its_districts() -> None:
    assert district_weight(1) == 1.0
    assert district_weight(2) == 0.5
    assert district_weight(7) == pytest.approx(1 / 7)
    assert sum(district_weight(7) for _ in range(7)) == pytest.approx(1.0)


def test_idf_weight_is_one_in_a_single_document_and_zero_in_all() -> None:
    assert idf_weight(1, 100) == 1.0
    assert idf_weight(100, 100) == 0.0
    assert idf_weight(10, 100) == pytest.approx(0.5)
    assert idf_weight(0, 100) == 1.0  # ohne Treffer ohne Wirkung
    assert idf_weight(0, 0) == 1.0
    assert idf_weight(1, 1) == 0.0  # ein Dokument ist die ganze Stadt
    assert idf_weight(5, 100) > idf_weight(50, 100)


def test_idf_expression_is_the_scalar_function() -> None:
    frame = pl.DataFrame(
        {"anzahl_treffer": [0, 1, 5, 205, 19_033]}, schema={"anzahl_treffer": pl.Int64}
    )
    found = frame.select(idf_expression(19_033)).get_column("gewicht_idf").to_list()
    assert found == [idf_weight(df, 19_033) for df in (0, 1, 5, 205, 19_033)]
    assert found[1] == 1.0 and found[-1] == 0.0


def test_term_weights_count_districts_and_documents() -> None:
    dictionary = _dictionary({1: ["hofgarten", "königsallee"], 2: ["königsallee"], 3: ["kö"]})
    index = _index({"hofgarten": ["p1"], "königsallee": ["p1", "p2"], "kö": []})
    frame = term_weights(dictionary, index, 4)
    rows = {r["suchbegriffe"]: r for r in frame.iter_rows(named=True)}
    assert rows["königsallee"]["n_bezirke"] == 2
    assert rows["königsallee"]["gewicht_bezirke"] == 0.5
    assert rows["hofgarten"]["gewicht_bezirke"] == 1.0
    assert rows["königsallee"]["gewicht_idf"] == pytest.approx(
        (math.log(4) - math.log(2)) / math.log(4)
    )
    assert rows["kö"]["gewicht_idf"] == 1.0  # ohne Treffer


def test_term_weights_refuse_more_hits_than_documents() -> None:
    dictionary = _dictionary({1: ["a"]})
    index = _index({"a": ["p1", "p2", "p3"]})
    with pytest.raises(Exception, match="Dokument"):
        term_weights(dictionary, index, 2)


def test_paper_type_rules_hit_the_faction_variants_but_not_the_administration() -> None:
    """Das Präfixmuster der Settings deckt die 30 Fraktionsvarianten und lässt Vorlagen in Ruhe."""
    rules = tuple(
        (rule.pattern, rule.weight) for rule in load_settings(cwd=None).weights.paper_type[0].rules
    )
    types = _types(
        {
            "p1": "Antrag SPD",
            "p2": "Beschlussvorlage",
            "p3": "zAnfrage REP",
            "p4": "Haushaltsantrag AFD",
            "p5": "Eingabe nach 24GO",
            "p6": "A+F Beschluss",
            "p7": "Bedarfsbeschluss",
            "p8": "Bezirksvertretung Informationsvorlage",
        }
    )
    weights = dict(paper_type_weights(types, rules).iter_rows())
    assert weights == {
        "p1": 0.5,
        "p2": 1.0,
        "p3": 0.5,
        "p4": 0.5,
        "p5": 0.5,
        "p6": 1.0,
        "p7": 1.0,
        "p8": 1.0,
    }


def test_paper_type_rules_are_ordered_and_tolerate_a_missing_type() -> None:
    types = pl.DataFrame(
        {"id": ["p1", "p2"], "paper_type": ["Antrag SPD", None]},
        schema={"id": pl.String, "paper_type": pl.String},
    )
    ordered = paper_type_weights(types, (("^antrag", 0.25), ("^antrag spd", 1.0)), default=0.75)
    assert dict(ordered.iter_rows()) == {"p1": 0.25, "p2": 0.75}  # erste Regel gewinnt


def test_document_weights_take_the_maximum_over_the_terms_not_the_sum() -> None:
    """Zwei Begriffe in einem Dokument dürfen das Gewicht nicht über 1 treiben."""
    dictionary = _dictionary({1: ["a", "b"]})
    index = _index({"a": ["p1"], "b": ["p1"]})
    pairs = document_pairs(dictionary, index)
    assert pairs.height == 2  # zwei Tripel, ein Paar
    terms = pl.DataFrame(
        {"suchbegriffe": ["a", "b"], "gewicht": [0.25, 0.75]},
        schema={"suchbegriffe": pl.String, "gewicht": pl.Float64},
    )
    weights = document_weights(pairs, terms)
    assert weights.height == 1 and weights.get_column("gewicht").to_list() == [0.75]


def test_document_weights_multiply_the_factors_per_document() -> None:
    dictionary = _dictionary({1: ["a"]})
    index = _index({"a": ["p1", "p2"]})
    pairs = document_pairs(dictionary, index)
    terms = pl.DataFrame(
        {"suchbegriffe": ["a"], "gewicht": [0.5]},
        schema={"suchbegriffe": pl.String, "gewicht": pl.Float64},
    )
    types = pl.DataFrame(
        {"id": ["p1"], "gewicht": [0.5]}, schema={"id": pl.String, "gewicht": pl.Float64}
    )
    topics = pl.DataFrame(
        {"id": ["p1", "p2"], "gewicht": [0.5, 0.25]},
        schema={"id": pl.String, "gewicht": pl.Float64},
    )
    found = dict(document_weights(pairs, terms, types, topics).select("id", "gewicht").iter_rows())
    assert found == {"p1": 0.5 * 0.5 * 0.5, "p2": 0.5 * 1.0 * 0.25}  # p2 fehlt in types: Faktor 1


def test_unit_weights_reproduce_the_count_of_the_thesis() -> None:
    dictionary = _dictionary({1: ["a", "b"], 2: ["b"], 3: ["c"]})
    index = _index({"a": ["p1"], "b": ["p1", "p2"], "c": []})
    voters = _voters([1, 2, 3])
    counted = join_voters(hits_by_district(dictionary, index), voters, ELIGIBLE)
    weighted = weighted_hits(document_weights(document_pairs(dictionary, index)), voters, ELIGIBLE)
    expected = dict(counted.select("wahlkreis_id", "anzahl_treffer").iter_rows())
    found = dict(weighted.select("wahlkreis_id", "anzahl_treffer_gewichtet").iter_rows())
    assert found[1] == float(expected[1]) == 2.0
    assert found[2] == float(expected[2]) == 2.0
    assert found[3] == float(expected[3]) == 0.0  # Begriff ohne Treffer: Zeile mit 0
    rates = dict(weighted.select("wahlkreis_id", "trefferquote_gewichtet").iter_rows())
    assert rates[1] == dict(counted.select("wahlkreis_id", "trefferquote").iter_rows())[1]


def test_document_pairs_without_overlap_is_a_domain_error() -> None:
    with pytest.raises(EmptyResultError, match="keine Paare"):
        document_pairs(_dictionary({1: ["a"]}), _index({"a": []}))


def test_topic_count_refuses_rows_of_different_length() -> None:
    uneven = pl.DataFrame(
        {"id": ["p1", "p2"], "anteile": [[1.0], [0.5, 0.5]]},
        schema={"id": pl.String, "anteile": pl.List(pl.Float64)},
    )
    with pytest.raises(EmptyResultError, match="Längen"):
        topic_count(uneven)


def test_variants_builds_every_row_and_the_topics_decompose_the_count() -> None:
    dictionary = _dictionary({1: ["a", "b"], 2: ["b"]})
    index = _index({"a": ["p1"], "b": ["p1", "p2"]})
    types = _types({"p1": "Antrag SPD", "p2": "Beschlussvorlage"})
    shares = pl.DataFrame(
        {"id": ["p1", "p2"], "anteile": [[0.25, 0.75], [1.0, 0.0]]},
        schema={"id": pl.String, "anteile": pl.List(pl.Float64)},
    )
    rules = [TypeRules("antraege_halb", 1.0, (("^z?(antrag|anfrage)", 0.5),))]
    frame = variants(
        dictionary,
        index,
        types,
        _voters([1, 2]),
        ELIGIBLE,
        4,
        rules,
        [BY_IDF, "antraege_halb"],
        shares,
    )
    names = frame.get_column("variante").unique().sort().to_list()
    assert names == [
        "antraege_halb",
        "bezirke",
        "einheit",
        "idf",
        "kombiniert",
        "thema_00",
        "thema_01",
    ]
    values = {
        (r["variante"], r["wahlkreis_id"]): r["anzahl_treffer_gewichtet"]
        for r in frame.iter_rows(named=True)
    }
    assert values[(UNIT, 1)] == 2.0 and values[(UNIT, 2)] == 2.0
    assert values[(BY_DISTRICTS, 1)] == 1.5  # p1 über "a" (1 Bezirk), p2 über "b" (2 Bezirke)
    assert values[("antraege_halb", 1)] == 1.5
    assert values[("thema_00", 1)] + values[("thema_01", 1)] == values[(UNIT, 1)]


def test_variants_without_topics_and_without_rules_has_only_the_fixed_rows() -> None:
    dictionary = _dictionary({1: ["a"]})
    index = _index({"a": ["p1"]})
    frame = variants(
        dictionary, index, _types({"p1": "Antrag"}), _voters([1]), ELIGIBLE, 2, [], [], None
    )
    assert frame.get_column("variante").to_list() == [BY_DISTRICTS, UNIT, BY_IDF]
