"""Eigenschaften der Gewichtung: was für jedes Wörterbuch und jeden Index gelten muss.

Die Strategien sind die aus ``test_hits_props.py`` (dieselben Begriffe, dieselben Dokument-IDs),
damit die Zählung der Arbeit und ihre gewichteten Varianten über denselben Eingaben verglichen
werden. Die eine Eigenschaft, an der alles hängt: Einheitsgewichte reproduzieren
``hits_by_district`` exakt, nicht ungefähr.
"""

from __future__ import annotations

import math

import polars as pl
from hypothesis import assume, given
from hypothesis import strategies as st

from georep.analysis.hits import hits_by_district
from georep.analysis.regression import spearman
from georep.analysis.weights import (
    BY_DISTRICTS,
    BY_IDF,
    TOPIC_PREFIX,
    UNIT,
    TypeRules,
    district_weight,
    document_pairs,
    document_weights,
    idf_weight,
    term_weights,
    variants,
    weighted_hits,
)

ELIGIBLE = "Wahlberechtigte_insgesamt"
TERMS = ["kö", "kö-bogen", "straße", "hofgarten", "am wehrhahn", "wehrhahn", "ölberg"]
PAPERS = ["p1", "p2", "p3", "p4", "p5", "p6"]
TYPES = ["Antrag SPD", "Beschlussvorlage", "Anfrage", "Informationsvorlage", "A+F Beschluss"]

ids = st.lists(st.sampled_from(PAPERS), min_size=0, max_size=len(PAPERS), unique=True)
index_rows = st.dictionaries(st.sampled_from(TERMS), ids, min_size=1, max_size=len(TERMS))
dictionary_rows = st.dictionaries(
    st.integers(1, 4),
    st.lists(st.sampled_from(TERMS), min_size=1, max_size=5, unique=True),
    min_size=1,
    max_size=4,
)
weight_lists = st.lists(st.floats(0.0, 1.0), min_size=len(TERMS), max_size=len(TERMS))


def _dictionary(rows: dict[int, list[str]]) -> pl.DataFrame:
    return pl.DataFrame(
        {"wahlkreis_id": list(rows), "suchbegriffe": [sorted(set(v)) for v in rows.values()]},
        schema={"wahlkreis_id": pl.Int64, "suchbegriffe": pl.List(pl.String)},
    )


def _as_built(
    dictionary: dict[int, list[str]], index: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Index wie ``build_index`` ihn liefert: genau die Begriffe des Wörterbuchs, ohne Treffer leer.

    Die Strategien würfeln Wörterbuch und Index unabhängig; in der Kette entsteht der Index aber
    aus den Begriffen des Wörterbuchs, und ``term_weights`` besteht darauf (sonst bekäme ein
    Begriff ohne Wahlbezirk stillschweigend ein Gewicht).
    """
    terms = {term for terms in dictionary.values() for term in terms}
    return {term: index.get(term, []) for term in sorted(terms)}


def _index(rows: dict[str, list[str]]) -> pl.DataFrame:
    terms = sorted(rows)
    return pl.DataFrame(
        {"suchbegriffe": terms, "paper_ids": [sorted(rows[t]) for t in terms]},
        schema={"suchbegriffe": pl.String, "paper_ids": pl.List(pl.String)},
    ).with_columns(pl.col("paper_ids").list.len().cast(pl.Int64).alias("anzahl_treffer"))


def _voters(districts: list[int]) -> pl.DataFrame:
    return pl.DataFrame(
        {"wahlkreis_id": sorted(districts), ELIGIBLE: [100] * len(districts)},
        schema={"wahlkreis_id": pl.Int64, ELIGIBLE: pl.Int64},
    )


def _term_factor(terms: list[str], weights: list[float]) -> pl.DataFrame:
    return pl.DataFrame(
        {"suchbegriffe": terms, "gewicht": weights[: len(terms)]},
        schema={"suchbegriffe": pl.String, "gewicht": pl.Float64},
    )


def _overlapping(dictionary: dict[int, list[str]], index: dict[str, list[str]]) -> bool:
    """Ohne ein Paar (Bezirk, Dokument) ist die Rechnung ein Domänenfehler, der separat geprüft wird."""
    return any(index.get(term) for terms in dictionary.values() for term in terms)


@given(dictionary=dictionary_rows, index=index_rows)
def test_unit_weights_reproduce_the_count_of_the_thesis_exactly(
    dictionary: dict[int, list[str]], index: dict[str, list[str]]
) -> None:
    index = _as_built(dictionary, index)
    assume(_overlapping(dictionary, index))
    dict_df, index_df = _dictionary(dictionary), _index(index)
    voters = _voters(list(dictionary))
    counted = dict(
        hits_by_district(dict_df, index_df).select("wahlkreis_id", "anzahl_treffer").iter_rows()
    )
    weighted = weighted_hits(document_weights(document_pairs(dict_df, index_df)), voters, ELIGIBLE)
    for row in weighted.iter_rows(named=True):
        # Float64 gleich Int64: exakt, keine Toleranz. Ein Bezirk ohne Begriff im Index zählt 0.
        assert row["anzahl_treffer_gewichtet"] == float(counted.get(row["wahlkreis_id"], 0))


@given(dictionary=dictionary_rows, index=index_rows, weights=weight_lists)
def test_every_weight_stays_in_the_unit_interval_and_lowers_no_sum(
    dictionary: dict[int, list[str]], index: dict[str, list[str]], weights: list[float]
) -> None:
    """Gewichte in [0, 1], und ein kleineres Begriffsgewicht erhöht keine Bezirkssumme."""
    index = _as_built(dictionary, index)
    assume(_overlapping(dictionary, index))
    dict_df, index_df = _dictionary(dictionary), _index(index)
    voters = _voters(list(dictionary))
    pairs = document_pairs(dict_df, index_df)
    terms = sorted(index)
    small = _term_factor(terms, weights)
    big = _term_factor(terms, [min(1.0, w + 0.1) for w in weights])
    with_small = document_weights(pairs, small)
    with_big = document_weights(pairs, big)
    assert (
        (with_small.get_column("gewicht") >= 0.0) & (with_small.get_column("gewicht") <= 1.0)
    ).all()
    lower = dict(
        weighted_hits(with_small, voters, ELIGIBLE)
        .select("wahlkreis_id", "anzahl_treffer_gewichtet")
        .iter_rows()
    )
    higher = dict(
        weighted_hits(with_big, voters, ELIGIBLE)
        .select("wahlkreis_id", "anzahl_treffer_gewichtet")
        .iter_rows()
    )
    assert all(lower[d] <= higher[d] + 1e-12 for d in lower)


@given(dictionary=dictionary_rows, index=index_rows)
def test_the_district_shares_of_a_term_sum_to_one(
    dictionary: dict[int, list[str]], index: dict[str, list[str]]
) -> None:
    frame = term_weights(_dictionary(dictionary), _index(_as_built(dictionary, index)), len(PAPERS))
    for row in frame.iter_rows(named=True):
        shares = row["n_bezirke"] * row["gewicht_bezirke"]
        assert math.isclose(shares, 1.0, rel_tol=1e-12)
        assert row["gewicht_bezirke"] == district_weight(row["n_bezirke"])
        # Toleranz, weil Polars durch ein Literal per Kehrwert teilt (ein ulp, test_weights.py).
        assert math.isclose(
            row["gewicht_idf"], idf_weight(row["anzahl_treffer"], len(PAPERS)), abs_tol=1e-15
        )


@given(
    df=st.integers(0, 500),
    more=st.integers(1, 500),
    n=st.integers(500, 20_000),
)
def test_idf_falls_monotonically_in_the_document_frequency(df: int, more: int, n: int) -> None:
    assume(df + more <= n)
    rarer, common = idf_weight(df, n), idf_weight(df + more, n)
    assert 0.0 <= common <= rarer <= 1.0
    if df >= 1:
        assert rarer > common or common == 0.0


@given(
    dictionary=dictionary_rows,
    index=index_rows,
    types=st.lists(st.sampled_from(TYPES), min_size=len(PAPERS), max_size=len(PAPERS)),
    shares=st.lists(
        st.lists(st.floats(0.0, 1.0), min_size=3, max_size=3),
        min_size=len(PAPERS),
        max_size=len(PAPERS),
    ),
)
def test_the_topic_variants_decompose_the_unit_count(
    dictionary: dict[int, list[str]],
    index: dict[str, list[str]],
    types: list[str],
    shares: list[list[float]],
) -> None:
    """Die Anteile summieren je Dokument zu 1, also summieren die Themenvarianten zur Einheit."""
    index = _as_built(dictionary, index)
    assume(_overlapping(dictionary, index))
    assume(all(sum(row) > 0 for row in shares))
    normalised = [[value / sum(row) for value in row] for row in shares]
    frame = variants(
        _dictionary(dictionary),
        _index(index),
        pl.DataFrame(
            {"id": PAPERS, "paper_type": types}, schema={"id": pl.String, "paper_type": pl.String}
        ),
        _voters(list(dictionary)),
        ELIGIBLE,
        len(PAPERS),
        [TypeRules("antraege_halb", 1.0, (("^z?(antrag|anfrage)", 0.5),))],
        [BY_IDF, "antraege_halb"],
        pl.DataFrame(
            {"id": PAPERS, "anteile": normalised},
            schema={"id": pl.String, "anteile": pl.List(pl.Float64)},
        ),
    )
    unit = dict(
        frame.filter(pl.col("variante") == UNIT)
        .select("wahlkreis_id", "anzahl_treffer_gewichtet")
        .iter_rows()
    )
    per_district = (
        frame.filter(pl.col("variante").str.starts_with(TOPIC_PREFIX))
        .group_by("wahlkreis_id")
        .agg(pl.col("anzahl_treffer_gewichtet").sum())
    )
    for row in per_district.iter_rows(named=True):
        assert math.isclose(
            row["anzahl_treffer_gewichtet"], unit[row["wahlkreis_id"]], rel_tol=1e-9, abs_tol=1e-9
        )
    # Keine Variante zählt mehr als die Arbeit, und jede trägt dieselben Wahlbezirke.
    assert (frame.get_column("anzahl_treffer_gewichtet") <= max(unit.values()) + 1e-9).all()
    assert frame.height == frame.get_column("variante").n_unique() * len(unit)


@given(dictionary=dictionary_rows, index=index_rows)
def test_spearman_of_the_unit_variant_against_the_unweighted_rate_is_one(
    dictionary: dict[int, list[str]], index: dict[str, list[str]]
) -> None:
    index = _as_built(dictionary, index)
    assume(_overlapping(dictionary, index))
    dict_df, index_df = _dictionary(dictionary), _index(index)
    voters = _voters(list(dictionary))
    frame = variants(dict_df, index_df, _types_frame(), voters, ELIGIBLE, len(PAPERS))
    unit = frame.filter(pl.col("variante") == UNIT)
    reference = unit.select("wahlkreis_id", pl.col("trefferquote_gewichtet").alias("trefferquote"))
    joined = unit.join(reference, on="wahlkreis_id", how="inner")
    rho = spearman(joined, "trefferquote_gewichtet", "trefferquote")
    assert rho is None or rho == 1.0
    for name in (BY_DISTRICTS, BY_IDF):
        other = frame.filter(pl.col("variante") == name).join(reference, on="wahlkreis_id")
        value = spearman(other, "trefferquote_gewichtet", "trefferquote")
        assert value is None or -1.0 <= value <= 1.0


def _types_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {"id": PAPERS, "paper_type": [TYPES[i % len(TYPES)] for i in range(len(PAPERS))]},
        schema={"id": pl.String, "paper_type": pl.String},
    )
