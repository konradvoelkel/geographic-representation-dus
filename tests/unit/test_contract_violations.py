"""Verträge schlagen an: je ein Gegenbeispiel pro Vor- und Nachbedingung, das vorher still durchlief.

Die Eigenschaften selbst prüfen die hypothesis-Tests in tests/property/; hier geht es darum, dass
eine Verletzung als deal.ContractError sichtbar wird und nicht als falsches Ergebnis.
"""

from __future__ import annotations

from pathlib import Path

import deal
import polars as pl
import pytest
import requests

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
    # ein Wahlberechtigter ist die Grenze: erlaubt (Mutant > 0 -> > 1 überlebte am 2026-10-11)
    assert join_voters(hits, voters.with_columns(pl.lit(1).alias("berechtigte")), "berechtigte")[
        "trefferquote"
    ].to_list() == [1.0]


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


def test_prep_functions_require_their_columns() -> None:
    from georep.prep.pois import clean_pois
    from georep.prep.streets import streets_by_district
    from georep.prep.voters import aggregate_voters
    from georep.settings import load_settings

    columns = load_settings(cwd=Path("/nonexistent")).columns.results
    with pytest.raises(deal.PreContractError, match="Parteispalten"):
        aggregate_voters(pl.DataFrame({columns.district: ["1"]}), columns)
    with pytest.raises(deal.PreContractError):
        clean_pois(pl.DataFrame({"label": ["a"], "wahlkreis_id": [1]}), [])
    with pytest.raises(deal.PreContractError):
        streets_by_district(pl.DataFrame({"wahlbezirk_id": [1], "strassen": [["a"]]}))


def test_after_marker_needs_a_marker_and_returns_a_suffix() -> None:
    from georep.prep.extract import after_marker, normalise_text

    with pytest.raises(deal.PreContractError, match="leerer Marker"):
        after_marker("kopf betrifft rest", "")
    assert after_marker("kopf betrifft rest", "betrifft") == " rest"
    assert normalise_text("A\nB") == "ab"


def test_locate_rejects_coordinates_outside_degrees() -> None:
    import shapely

    from georep.geo import Precinct, PrecinctIndex

    square = Precinct("1", 1, "eins", shapely.box(340000, 5670000, 341000, 5671000))
    index = PrecinctIndex([square], "EPSG:25832")
    assert index.locate(6.7, 51.2) is None
    for lon, lat in ((6.7, 100.0), (200.0, 51.2)):
        with pytest.raises(deal.PreContractError, match="vertauscht"):
            index.locate(lon, lat)


def test_overpass_polygon_rejects_negative_tolerance_and_yields_closed_ring() -> None:
    import shapely

    from georep.geo import overpass_polygon

    square = shapely.box(340000, 5670000, 341000, 5671000)
    with pytest.raises(deal.PreContractError, match="Toleranz"):
        overpass_polygon(square, "EPSG:25832", tolerance_m=-1)
    ring = overpass_polygon(square, "EPSG:25832").split()
    assert len(ring) == 10 and ring[0:2] == ring[8:10]


def test_text_store_put_needs_a_name(tmp_path: Path) -> None:
    from georep.stores import TextMeta, TextStore

    with pytest.raises(deal.PreContractError, match="Dateinamen"):
        TextStore(tmp_path / "t.parquet").put("", "x", TextMeta(extractor="e"))


def test_cache_pattern_passes_value_errors_through() -> None:
    from georep.http import cache_pattern

    assert cache_pattern("https://host/path?x=1") == "host/path*"
    with pytest.raises(ValueError):
        cache_pattern("http://[::1")


def test_fetchers_declare_their_exceptions() -> None:
    """Eine fremde Ausnahme aus einem Fetcher ist eine Vertragsverletzung, keine Netzstörung."""
    from georep.sources.opendata import fetch_csv

    class Exploding:
        def get(
            self, url: str, *, params: object = None, headers: object = None
        ) -> requests.Response:
            raise RuntimeError("kein Netz, sondern ein Programmierfehler")

        def post(
            self, url: str, *, data: object = None, headers: object = None
        ) -> requests.Response:
            raise RuntimeError("nie")

    with pytest.raises(deal.RaisesContractError) as caught:
        fetch_csv(Exploding(), "https://x.invalid/a.csv")
    assert isinstance(caught.value.__cause__, RuntimeError)


# --- Option 06: Gewichtung --------------------------------------------------------------------


def _weights_index(rows: dict[str, list[str]]) -> pl.DataFrame:
    terms = sorted(rows)
    return pl.DataFrame(
        {"suchbegriffe": terms, "paper_ids": [sorted(rows[t]) for t in terms]},
        schema={"suchbegriffe": pl.String, "paper_ids": pl.List(pl.String)},
    ).with_columns(pl.col("paper_ids").list.len().cast(pl.Int64).alias("anzahl_treffer"))


def test_district_weight_refuses_zero_districts() -> None:
    from georep.analysis.weights import district_weight

    with pytest.raises(deal.PreContractError):
        district_weight(0)


def test_idf_weight_refuses_more_documents_than_there_are() -> None:
    from georep.analysis.weights import idf_weight

    with pytest.raises(deal.PreContractError):
        idf_weight(11, 10)


def test_term_weights_refuse_an_index_with_more_hits_than_documents() -> None:
    from georep.analysis.weights import term_weights

    with pytest.raises(deal.PreContractError, match="Dokument"):
        term_weights(_dictionary({1: ["kö"]}), _weights_index({"kö": ["p1", "p2"]}), 1)


def test_compile_rules_refuses_a_weight_above_one() -> None:
    from georep.analysis.weights import compile_rules

    with pytest.raises(deal.PreContractError, match=r"\[0, 1\]"):
        compile_rules((("^antrag", 1.5),))


def test_document_weights_refuse_a_factor_outside_the_unit_interval() -> None:
    """Ein Gewicht über 1 würde die Schranke g ≤ 1 brechen und mehr Treffer zählen als es gibt."""
    from georep.analysis.weights import document_pairs, document_weights

    pairs = document_pairs(_dictionary({1: ["kö"]}), _weights_index({"kö": ["p1"]}))
    too_much = pl.DataFrame(
        {"suchbegriffe": ["kö"], "gewicht": [1.5]},
        schema={"suchbegriffe": pl.String, "gewicht": pl.Float64},
    )
    with pytest.raises(deal.PreContractError, match=r"\[0, 1\]"):
        document_weights(pairs, too_much)


def test_weighted_hits_refuse_districts_without_voters() -> None:
    from georep.analysis.weights import weighted_hits

    weights = pl.DataFrame(
        {"wahlkreis_id": [1], "id": ["p1"], "gewicht": [1.0]},
        schema={"wahlkreis_id": pl.Int64, "id": pl.String, "gewicht": pl.Float64},
    )
    voters = pl.DataFrame(
        {"wahlkreis_id": [1], "Wahlberechtigte_insgesamt": [0]},
        schema={"wahlkreis_id": pl.Int64, "Wahlberechtigte_insgesamt": pl.Int64},
    )
    with pytest.raises(deal.PreContractError, match="Wahlberechtigte"):
        weighted_hits(weights, voters, "Wahlberechtigte_insgesamt")


def test_variants_refuse_an_unknown_factor_in_combined() -> None:
    from georep.analysis.weights import variants

    voters = pl.DataFrame(
        {"wahlkreis_id": [1], "Wahlberechtigte_insgesamt": [100]},
        schema={"wahlkreis_id": pl.Int64, "Wahlberechtigte_insgesamt": pl.Int64},
    )
    types = pl.DataFrame(
        {"id": ["p1"], "paper_type": ["Antrag"]},
        schema={"id": pl.String, "paper_type": pl.String},
    )
    with pytest.raises(deal.PreContractError, match="kombiniert"):
        variants(
            _dictionary({1: ["kö"]}),
            _weights_index({"kö": ["p1"]}),
            types,
            voters,
            "Wahlberechtigte_insgesamt",
            2,
            [],
            ["gibtsnicht"],
            None,
        )


def test_term_weights_refuse_a_term_the_dictionary_does_not_have() -> None:
    """Ein Begriff im Index, den kein Wörterbuch führt, bekäme stillschweigend das Gewicht 1."""
    from georep.analysis.weights import term_weights

    with pytest.raises(deal.PostContractError, match="Wörterbuch"):
        term_weights(_dictionary({1: ["kö"]}), _weights_index({"kö": ["p1"], "fremd": ["p2"]}), 4)


# --- Option 04: die Schranken je Partei und Bezirk -------------------------------------------------


def test_party_hits_above_the_district_total_breaks_the_contract() -> None:
    """Review-Befund 3: die zweite Schranke aus § 5 C des Plans. Ein Bezirk, dessen
    ``anzahl_treffer`` kleiner ist als seine ``paper_ids``, ergäbe für eine Partei mehr Treffer
    als der Bezirk überhaupt hat; das lief vorher still durch."""
    from georep.analysis.parties import ART, PARTEIEN, party_hits
    from georep.settings import load_settings

    documents = pl.DataFrame(
        {"id": ["a", "b"], ART: ["Fraktion", "Fraktion"], PARTEIEN: [["CDU"], ["CDU"]]},
        schema={"id": pl.String, ART: pl.String, PARTEIEN: pl.List(pl.String)},
    )
    voters = pl.DataFrame(
        {"wahlkreis_id": [1], "Wahlberechtigte_insgesamt": [100], "CDU_Stimmen": [40]},
        schema={
            "wahlkreis_id": pl.Int64,
            "Wahlberechtigte_insgesamt": pl.Int64,
            "CDU_Stimmen": pl.Int64,
        },
    ).with_columns(CDU_anteil=pl.lit(0.4))
    parties = [
        p for p in load_settings(cwd=Path("/nonexistent")).originators.parties if p.key == "CDU"
    ]

    def results(hits: int) -> pl.DataFrame:
        return pl.DataFrame(
            {"wahlkreis_id": [1], "paper_ids": [["a", "b"]], "anzahl_treffer": [hits]},
            schema={
                "wahlkreis_id": pl.Int64,
                "paper_ids": pl.List(pl.String),
                "anzahl_treffer": pl.Int64,
            },
        )

    assert party_hits(results(2), documents, voters, parties).height == 1  # stimmig
    with pytest.raises(deal.PostContractError, match="Schranken"):
        party_hits(results(1), documents, voters, parties)
