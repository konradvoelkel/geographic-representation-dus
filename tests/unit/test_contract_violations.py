"""Verträge schlagen an: je ein Gegenbeispiel pro Vor- und Nachbedingung, das vorher still durchlief.

Die Eigenschaften selbst prüfen die hypothesis-Tests in tests/property/; hier geht es darum, dass
eine Verletzung als deal.ContractError sichtbar wird und nicht als falsches Ergebnis.
"""

from __future__ import annotations

import deal
import polars as pl
import pytest

from georep.analysis.hits import hits_by_district, join_voters
from georep.analysis.regression import regress
from georep.search.dictionary import all_terms, build_dictionary
from georep.search.index import build_index

DICT_SCHEMA = {"wahlkreis_id": pl.Int64(), "suchbegriffe": pl.List(pl.String)}


def _dictionary(rows: dict[int, list[str]]) -> pl.DataFrame:
    return pl.DataFrame(
        {"wahlkreis_id": list(rows), "suchbegriffe": list(rows.values())}, schema=DICT_SCHEMA
    )


def test_build_dictionary_requires_both_columns() -> None:
    good = _dictionary({1: ["kö"]})
    with pytest.raises(deal.PreContractError, match="wahlkreis_id"):
        build_dictionary(good.rename({"suchbegriffe": "terms"}), good)


def test_all_terms_requires_the_term_column() -> None:
    with pytest.raises(deal.PreContractError):
        all_terms(pl.DataFrame({"x": [1]}))


def test_build_index_rejects_uppercase_duplicate_or_empty_terms() -> None:
    corpus = pl.DataFrame({"id": ["a"], "text": ["kö bogen"]})
    for terms in (["Kö"], ["kö", "kö"], [], ["kö,bogen"]):
        with pytest.raises(deal.PreContractError, match="kleingeschrieben"):
            build_index(corpus, terms)
    with pytest.raises(deal.PreContractError):
        build_index(corpus.rename({"text": "inhalt"}), ["kö"])


def test_hits_by_district_requires_index_columns() -> None:
    index = pl.DataFrame({"suchbegriffe": ["kö"], "paper_ids": [["a"]]})
    with pytest.raises(deal.PreContractError):
        hits_by_district(_dictionary({1: ["kö"]}), index)


def test_join_voters_requires_positive_eligible_voters() -> None:
    hits = pl.DataFrame(
        {"wahlkreis_id": [1], "paper_ids": [["a"]], "anzahl_treffer": [1]},
        schema={
            "wahlkreis_id": pl.Int64,
            "paper_ids": pl.List(pl.String),
            "anzahl_treffer": pl.Int64,
        },
    )
    voters = pl.DataFrame({"wahlkreis_id": [1], "berechtigte": [0]})
    with pytest.raises(deal.PreContractError, match="positiv"):
        join_voters(hits, voters, "berechtigte")
    assert join_voters(hits, voters.with_columns(pl.lit(50).alias("berechtigte")), "berechtigte")[
        "trefferquote"
    ].to_list() == [0.02]


def test_regress_requires_its_columns_and_a_positive_scale() -> None:
    frame = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3],
            "trefferquote": [0.1, 0.2, 0.4],
            "wahlbeteiligung": [0.5, 0.6, 0.7],
        }
    )
    assert regress(frame).n == 3
    with pytest.raises(deal.PreContractError):
        regress(frame.drop("trefferquote"))
    with pytest.raises(deal.PreContractError):
        regress(frame, y_scale=0)
