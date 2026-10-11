"""Jede Polars-Stufe gegen die eingefrorene Ausgabe des Altcodes auf der Mini-Fixture.

Listen werden mit dem Trennzeichen des Altcodes verbunden, bevor verglichen wird.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from georep.prep.pois import clean_pois, pois_by_district, read_pois_json
from georep.prep.streets import read_streets_json, streets_by_district
from georep.prep.voters import aggregate_voters, read_results_csv
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
