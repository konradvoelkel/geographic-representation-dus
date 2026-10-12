"""Laufzeit-Benchmarks der heißen Pfade: Matcher, Extraktion, Aggregation, Index-Join.

Nur in ``nox -s bench``: pytest-benchmark speichert jeden Lauf unter ``.benchmarks/`` (gitignored)
und vergleicht mit dem zuletzt gespeicherten; rot ab 20 % langsamer im Minimum, denn das Minimum ist
die Statistik mit dem geringsten Rauschen (Mittelwert und Maximum tragen GC und Scheduler mit), und
10 % lagen am 2026-10-11 noch unter dem Rauschen der Submillisekunden-Stufen (``docs/profiling/README.md``). Die
Eingaben sind die Mini-Fixture (200 Dokumente, drei Wahlbezirke) und die vier PDF-Fixtures; die
Baseline-Zahlen stehen datiert in ``docs/profiling/README.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from georep.analysis.bodies import hits_by_body
from georep.analysis.hits import hits_by_district, join_voters
from georep.analysis.weights import (
    TypeRules,
    document_pairs,
    document_weights,
    variants,
    weighted_hits,
)
from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.bodies import ID, REFERENCE, BodyRules, classify_papers
from georep.prep.extract import extract_text
from georep.prep.voters import aggregate_voters, read_results_csv
from georep.search.dictionary import all_terms, build_dictionary
from georep.search.index import build_index, total_hits
from georep.search.matcher import make_matcher
from georep.settings import Settings, load_settings

pytestmark = pytest.mark.bench

PDFS = ["00438685.pdf", "00439409.pdf", "00519825.pdf", "00552781.pdf"]


@dataclass(frozen=True)
class MiniRun:
    """Die Zwischenergebnisse eines Offline-Laufs auf der Mini-Fixture, einmal je Modul geladen."""

    settings: Settings
    results_csv: pl.DataFrame
    pois_by_district: pl.DataFrame
    streets_by_district: pl.DataFrame
    dictionary: pl.DataFrame
    terms: list[str]
    corpus: pl.DataFrame
    index: pl.DataFrame
    voters: pl.DataFrame
    results: pl.DataFrame  # Option 05
    units: pl.DataFrame  # Option 05
    paper_types: pl.DataFrame  # Option 06


@pytest.fixture(scope="module")
def mini(tmp_path_factory: pytest.TempPathFactory, mini_root: Path) -> MiniRun:
    settings = load_settings(cwd=Path("/nonexistent"))
    root = tmp_path_factory.mktemp("bench")
    layout = Layout(root / "data", root / "cache", mini_root)
    bootstrap(layout)
    run_pipeline(build_steps(settings, layout), settings)
    dictionary = pl.read_parquet(layout.dictionary)
    return MiniRun(
        settings=settings,
        results_csv=read_results_csv(layout.results_csv, settings.columns.results),
        pois_by_district=pl.read_parquet(layout.pois_by_district),
        streets_by_district=pl.read_parquet(layout.streets_by_district),
        dictionary=dictionary,
        terms=all_terms(dictionary),
        corpus=pl.read_parquet(layout.corpus, columns=["id", "text"]),
        index=pl.read_parquet(layout.index),
        voters=pl.read_parquet(layout.voters),
        results=pl.read_parquet(layout.results),
        units=pl.read_parquet(layout.district_units),
        paper_types=pl.read_parquet(layout.corpus, columns=["id", "paper_type"]),
    )


def test_matcher_build(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    matcher = benchmark(make_matcher, mini.terms)
    assert matcher.extract(mini.terms[0]) == {mini.terms[0]}


def test_matcher_extract_over_corpus(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    matcher = make_matcher(mini.terms)
    texts = [text for text in mini.corpus.get_column("text").to_list() if text]

    def run() -> int:
        return sum(len(matcher.extract(text)) for text in texts)

    assert benchmark(run) > 0


def test_index_step(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    frame = benchmark(build_index, mini.corpus, mini.terms)
    assert total_hits(frame) > 0


@pytest.mark.parametrize("name", PDFS)
def test_extract_pdf(benchmark: BenchmarkFixture, pdf_fixtures: Path, name: str) -> None:
    text = benchmark(extract_text, pdf_fixtures / name)
    assert "betrifft" in text


def test_aggregate_voters(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    frame = benchmark(aggregate_voters, mini.results_csv, mini.settings.columns.results)
    assert frame.height == 3


def test_build_dictionary(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    frame = benchmark(build_dictionary, mini.pois_by_district, mini.streets_by_district)
    assert frame.height == 3


def test_hits_and_voter_join(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    search, columns = mini.settings.search, mini.settings.columns.results

    def run() -> pl.DataFrame:
        hits = hits_by_district(mini.dictionary, mini.index, search.hide_in_display)
        return join_voters(hits, mini.voters, columns.eligible)

    assert benchmark(run).height == 3


# --- Option 05: Parser über dem Korpus und die Aggregation je Wahlbezirk


def test_classify_papers(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    rules = BodyRules.from_settings(mini.settings.bodies)
    corpus = mini.corpus.select(ID, pl.lit("BV6/108/2023").alias(REFERENCE))
    frame = benchmark(classify_papers, corpus, rules)
    assert frame.height == 200


def test_hits_by_body(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    rules = BodyRules.from_settings(mini.settings.bodies)
    papers = classify_papers(mini.corpus.select(ID, pl.lit("RAT/1/2023").alias(REFERENCE)), rules)
    eligible = mini.settings.columns.results.eligible
    frame = benchmark(hits_by_body, mini.results, papers, mini.units, eligible)
    assert frame.height == 3


def test_weights_step(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    """Option 06: Paare, Gewichte je Paar und Summen je Wahlbezirk, ohne Themenmodell.

    Das Themenmodell selbst ist kein Benchmark: NMF ist gegen die Textmenge empfindlich und
    schwankt mit der BLAS-Bibliothek, dafür ist ``georep profile topics`` da.
    """
    columns = mini.settings.columns.results
    rules = [
        TypeRules(
            rule_set.name,
            rule_set.default,
            tuple((rule.pattern, rule.weight) for rule in rule_set.rules),
        )
        for rule_set in mini.settings.weights.paper_type
    ]

    def run() -> pl.DataFrame:
        return variants(
            mini.dictionary,
            mini.index,
            mini.paper_types,
            mini.voters,
            columns.eligible,
            mini.corpus.height,
            rules,
            mini.settings.weights.combined,
            None,
        )

    assert benchmark(run).height == (3 + len(rules) + 1) * 3


def test_document_weights_over_the_pairs(benchmark: BenchmarkFixture, mini: MiniRun) -> None:
    pairs = document_pairs(mini.dictionary, mini.index)
    columns = mini.settings.columns.results

    def run() -> pl.DataFrame:
        return weighted_hits(document_weights(pairs), mini.voters, columns.eligible)

    assert benchmark(run).height == 3
