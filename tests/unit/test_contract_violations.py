"""Verträge schlagen an: je ein Gegenbeispiel pro Vor- und Nachbedingung, das vorher still durchlief.

Die Eigenschaften selbst prüfen die hypothesis-Tests in tests/property/; hier geht es darum, dass
eine Verletzung als deal.ContractError sichtbar wird und nicht als falsches Ergebnis.
"""

from __future__ import annotations

from pathlib import Path

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
