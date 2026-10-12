"""Jede Polars-Stufe gegen die eingefrorene Ausgabe des Altcodes auf der Mini-Fixture.

Listen werden mit dem Trennzeichen des Altcodes verbunden, bevor verglichen wird.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from georep.prep.pois import clean_pois, pois_by_district, read_pois_json
from georep.prep.streets import read_streets_json, streets_by_district
from georep.prep.voters import ELIGIBLE_TOTAL, aggregate_voters, read_results_csv
from georep.search.dictionary import all_terms, build_dictionary
from georep.settings import Settings, load_settings


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def _expected(mini_root: Path, name: str, **kwargs: object) -> pl.DataFrame:
    return pl.read_csv(mini_root / "expected" / name, infer_schema_length=None, **kwargs)  # type: ignore[arg-type]


def _joined(frame: pl.DataFrame, column: str, sep: str) -> pl.DataFrame:
    return frame.with_columns(pl.col(column).list.join(sep))


def test_voters_match_legacy(mini_root: Path, settings: Settings) -> None:
    results = read_results_csv(
        mini_root / "external" / "Stimmbezirk_Wahlergebnis.csv", settings.columns.results
    )
    got = aggregate_voters(results, settings.columns.results)
    exp = _expected(mini_root, "wahlbezirke_waehler.csv")
    assert got.columns == exp.columns
    assert_frame_equal(got, exp, rel_tol=1e-12)


def test_streets_match_legacy(mini_root: Path) -> None:
    got = streets_by_district(read_streets_json(mini_root / "raw" / "streets_per_district.json"))
    exp = _expected(mini_root, "wahlbezirke_strassen.csv")
    assert_frame_equal(_joined(got, "suchbegriffe", "; "), exp)


def test_pois_match_legacy(mini_root: Path, settings: Settings) -> None:
    clean = clean_pois(
        read_pois_json(mini_root / "raw" / "wikipedia_dict.json"), settings.search.exclude
    )
    vis = _expected(mini_root, "wikidata_vis.csv")
    assert_frame_equal(clean, vis, rel_tol=1e-12)
    agg = _expected(mini_root, "wikidata_agg.csv")
    assert_frame_equal(_joined(pois_by_district(clean), "suchbegriffe", "; "), agg)


def test_dictionary_matches_legacy(mini_root: Path, settings: Settings) -> None:
    clean = clean_pois(
        read_pois_json(mini_root / "raw" / "wikipedia_dict.json"), settings.search.exclude
    )
    streets = streets_by_district(
        read_streets_json(mini_root / "raw" / "streets_per_district.json")
    )
    got = build_dictionary(pois_by_district(clean), streets)
    exp = _expected(mini_root, "combined_searchdict.csv", separator=";")
    assert_frame_equal(_joined(got, "suchbegriffe", ", "), exp)
    terms = all_terms(got)
    assert terms == sorted(set(terms))
    assert all("," not in t and t == t.lower() == t.strip() for t in terms)


# --- Index, Treffer, Regression -------------------------------------------------------------


def _index_sets(
    frame: pl.DataFrame, ids_column: str, split: str | None
) -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    for row in frame.iter_rows(named=True):
        ids = row[ids_column]
        if split is not None:
            ids = str(ids).split(split) if ids else []
        out[str(row["suchbegriffe"])] = frozenset(ids)
    return out


@pytest.fixture(scope="module")
def mini_chain(
    mini_root: Path, settings: Settings, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, pl.DataFrame]:
    from georep.analysis.hits import hits_by_district, join_voters
    from georep.bootstrap import seed_stores_from_legacy
    from georep.layout import Layout
    from georep.prep.papers import build_corpus
    from georep.search.index import build_index
    from georep.stores import PaperStore, TextStore

    tmp = tmp_path_factory.mktemp("chain")
    layout = Layout(tmp / "data", tmp / "cache", mini_root)
    seed_stores_from_legacy(
        layout,
        json.loads((mini_root / "interim" / "paper_with_text.json").read_text(encoding="utf-8")),
    )
    corpus = build_corpus(PaperStore(layout.papers).load().values(), TextStore(layout.texts))
    voters = aggregate_voters(
        read_results_csv(
            mini_root / "external" / "Stimmbezirk_Wahlergebnis.csv", settings.columns.results
        ),
        settings.columns.results,
    )
    clean = clean_pois(
        read_pois_json(mini_root / "raw" / "wikipedia_dict.json"), settings.search.exclude
    )
    streets = streets_by_district(
        read_streets_json(mini_root / "raw" / "streets_per_district.json")
    )
    dictionary = build_dictionary(pois_by_district(clean), streets)
    index = build_index(corpus, all_terms(dictionary))
    hits = hits_by_district(dictionary, index, settings.search.hide_in_display)
    results = join_voters(hits, voters, ELIGIBLE_TOTAL)
    return {"index": index, "results": results}


def test_index_matches_legacy(mini_root: Path, mini_chain: dict[str, pl.DataFrame]) -> None:
    exp = _expected(
        mini_root,
        "inverted_index.csv",
        schema_overrides={"suchbegriffe": pl.String, "paper_ids": pl.String},
    )
    got = mini_chain["index"]
    assert _index_sets(got, "paper_ids", None) == _index_sets(exp, "paper_ids", ";")
    assert got["anzahl_treffer"].to_list() == got["paper_ids"].list.len().to_list()
    assert got["suchbegriffe"].is_sorted()


def test_results_match_legacy(mini_root: Path, mini_chain: dict[str, pl.DataFrame]) -> None:
    exp = _expected(mini_root, "wahlbezirke_auswertung.csv").sort("wahlkreis_id")
    got = mini_chain["results"].with_columns(
        pl.col("suchbegriffe").list.join("; "), pl.col("paper_ids").list.join(";")
    )
    assert got.columns == exp.columns
    assert_frame_equal(got, exp, rel_tol=1e-12)


def test_regression_reproduces_table_5(reference_root: Path) -> None:
    from georep.analysis.regression import regress

    results = pl.read_csv(
        reference_root / "processed" / "wahlbezirke_auswertung.csv", infer_schema_length=None
    )
    full = regress(results)
    assert (full.n, round(full.slope, 4), round(full.intercept, 4)) == (41, 62.1337, 49.1993)
    assert full.r == pytest.approx(0.16125, abs=5e-5)
    assert full.p == pytest.approx(0.31385, abs=5e-5)
    assert full.r2 == pytest.approx(0.026001, abs=5e-6)
    trimmed = regress(results, exclude=(1, 10))
    assert trimmed.n == 39
    assert trimmed.slope == pytest.approx(215.3341, abs=5e-4)
    assert "n=41" in full.summary()
