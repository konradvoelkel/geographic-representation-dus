"""Normierte Kennzahlen je Wahlbezirk: Handbeispiel, Mini-Fixture, Verträge (Punkt 46)."""

from __future__ import annotations

import deal
import polars as pl
import pytest

from georep.analysis.hits import DISTRICT, RATE, TERMS
from georep.analysis.scaling import (
    CITY_MEAN,
    DEVIATION,
    METRIC_COLUMNS,
    PER_1000,
    PER_TERM,
    TERM_COUNT,
    dictionary_bias,
    district_metrics,
    relative_to,
    summary,
    unweighted_mean,
)
from georep.errors import SchemaError
from georep.layout import Layout
from georep.prep.voters import ELIGIBLE_TOTAL
from georep.search.index import HITS


def _results(rows: list[tuple[int, int, int]]) -> pl.DataFrame:
    """Wahlbezirk, Treffer, Wahlberechtigte; die Quote wie ``join_voters`` sie rechnet."""
    frame = pl.DataFrame(
        {
            DISTRICT: [r[0] for r in rows],
            HITS: [r[1] for r in rows],
            ELIGIBLE_TOTAL: [r[2] for r in rows],
        },
        schema={DISTRICT: pl.Int64, HITS: pl.Int64, ELIGIBLE_TOTAL: pl.Int64},
    )
    return frame.with_columns((pl.col(HITS) / pl.col(ELIGIBLE_TOTAL)).alias(RATE))


def _dictionary(sizes: dict[int, int]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            DISTRICT: list(sizes),
            TERMS: [[f"begriff {i}" for i in range(n)] for n in sizes.values()],
        },
        schema={DISTRICT: pl.Int64, TERMS: pl.List(pl.String)},
    )


def test_the_metrics_are_counted_by_hand() -> None:
    frame = district_metrics(
        _results([(1, 100, 10_000), (2, 60, 10_000), (3, 20, 10_000)]),
        _dictionary({1: 50, 2: 20, 3: 10}),
    )
    assert list(frame.columns) == list(METRIC_COLUMNS)
    assert frame.get_column(TERM_COUNT).to_list() == [50, 20, 10]
    assert frame.get_column(PER_TERM).to_list() == [2.0, 3.0, 2.0]
    assert frame.get_column(PER_1000).to_list() == [10.0, 6.0, 2.0]
    # Stadtmittel ist das ungewichtete Mittel der drei Quoten, nicht 180/30 000
    assert frame.get_column(CITY_MEAN).to_list() == pytest.approx([0.006, 0.006, 0.006])
    assert frame.get_column(DEVIATION).to_list() == pytest.approx([2.0 / 3.0, 0.0, -2.0 / 3.0])


def test_the_deviations_add_up_to_zero() -> None:
    frame = district_metrics(
        _results([(1, 7, 9_000), (2, 913, 11_500), (3, 40, 10_000), (4, 311, 13_000)]),
        _dictionary({1: 3, 2: 400, 3: 17, 4: 120}),
    )
    assert frame.get_column(DEVIATION).sum() == pytest.approx(0.0, abs=1e-12)


def test_a_city_without_a_single_hit_has_no_deviation() -> None:
    """Ohne Treffer ist das Stadtmittel 0, und dann gibt es keine Abweichung davon.

    Der Fall kommt vor, sobald jemand mit einer kleinen Stichprobe rechnet (``fetch pdfs
    --limit N``) oder ein neues Profil anlegt, dessen Dokumente noch nicht extrahiert sind. Ohne
    den Zweig wäre die Abweichung -1,0 je Bezirk, die Nachbedingung „die Abweichungen summieren
    sich auf 0" bräche, und der Schritt ``metrics`` risse die ganze Kette mit.
    """
    frame = district_metrics(_results([(1, 0, 10_000), (2, 0, 11_000)]), _dictionary({1: 5, 2: 7}))
    assert frame.get_column(CITY_MEAN).to_list() == [0.0, 0.0]
    assert frame.get_column(DEVIATION).to_list() == [0.0, 0.0]
    assert frame.get_column(PER_TERM).to_list() == [0.0, 0.0]


def test_a_single_district_deviates_from_itself_by_nothing() -> None:
    frame = district_metrics(_results([(7, 12, 10_000)]), _dictionary({7: 4}))
    assert frame.get_column(DEVIATION).to_list() == [0.0]


def test_a_district_without_a_dictionary_is_an_error() -> None:
    with pytest.raises(SchemaError, match="4"):
        district_metrics(_results([(4, 10, 10_000)]), _dictionary({1: 5}))


def test_an_empty_dictionary_does_not_divide_by_zero() -> None:
    frame = district_metrics(_results([(1, 0, 10_000), (2, 5, 10_000)]), _dictionary({1: 0, 2: 5}))
    assert frame.get_column(PER_TERM).to_list() == [0.0, 1.0]


def test_the_mean_is_unweighted_and_the_ratio_survives_a_zero_mean() -> None:
    frame = pl.DataFrame({"g": [1, 1, 2, 2], "v": [0.0, 0.0, 1.0, 3.0]})
    found = frame.with_columns(unweighted_mean("v", ["g"]).alias("m")).with_columns(
        relative_to("v", "m").alias("q")
    )
    assert found.get_column("m").to_list() == [0.0, 0.0, 2.0, 2.0]
    assert found.get_column("q").to_list() == [0.0, 0.0, 0.5, 1.5]


def test_the_summary_names_the_spread() -> None:
    frame = district_metrics(
        _results([(1, 100, 10_000), (2, 60, 10_000)]), _dictionary({1: 50, 2: 20})
    )
    assert summary(frame) == "2 Wahlbezirke, 70 Begriffe, 2,000 bis 3,000 Treffer je Begriff"


def test_missing_columns_violate_the_contract() -> None:
    with pytest.raises(deal.PreContractError):
        district_metrics(pl.DataFrame({DISTRICT: [1]}), _dictionary({1: 5}))


# --- Die Verzerrung durch die Wörterbuchgröße (Mutationslauf 2026-10-13) -----------------------
#
# ``dictionary_bias`` hatte keinen eigenen Test: elf der 25 Überlebenden lagen in ihm und in
# ``_pearson`` (docs/mutation-2026-10-13.md). Die Zahlen des Methodenabsatzes der Seite hingen
# damit allein am slow-Test.


def _bias_inputs(
    rows: list[tuple[int, int, int]], sizes: dict[int, int]
) -> tuple[pl.DataFrame, pl.DataFrame]:
    results = _results(rows)
    return district_metrics(results, _dictionary(sizes)), results


# Treffer = 2 · Begriffe + 10 und Wahlberechtigte linear in den Treffern: beide Korrelationen sind
# damit genau 1, und „Treffer je Begriff" (3,0 / 2,5 / 2,3333) fällt mit der Größe — die
# Überkorrektur, von der der Methodenabsatz spricht.
LINEAR = [(1, 30, 10_000), (2, 50, 11_000), (3, 70, 12_000)]
SIZES = {1: 10, 2: 20, 3: 30}


def test_the_bias_is_the_correlation_counted_by_hand() -> None:
    found = dictionary_bias(*_bias_inputs(LINEAR, SIZES))
    assert found is not None
    assert found.districts == 3
    assert found.hits_terms == pytest.approx(1.0)
    assert found.hits_eligible == pytest.approx(1.0)
    assert -1.0 <= found.per_term_terms < 0.0  # die Quote je Begriff fällt mit der Größe
    assert (found.terms_min, found.terms_max) == (10, 30)
    assert found.eligible_spread == pytest.approx(1.2)


def test_a_negative_correlation_keeps_its_sign() -> None:
    """Die Zahl ist Pearson und kein Betrag: ein fallender Zusammenhang ist negativ."""
    found = dictionary_bias(
        *_bias_inputs([(1, 70, 10_000), (2, 50, 11_000), (3, 30, 12_000)], SIZES)
    )
    assert found is not None
    assert found.hits_terms == pytest.approx(-1.0)
    assert found.hits_eligible == pytest.approx(-1.0)
    assert found.eligible_spread == pytest.approx(1.2)


def test_two_districts_are_too_few_for_a_correlation() -> None:
    """Die Grenze ist drei: mit zwei Punkten ist r immer ±1 und sagt nichts (``frame.height < 3``)."""
    assert dictionary_bias(*_bias_inputs(LINEAR[:2], {1: 10, 2: 20})) is None
    # Genau drei reichen: die Grenze liegt zwischen diesen beiden Fällen.
    assert dictionary_bias(*_bias_inputs(LINEAR, SIZES)) is not None


def test_without_spread_in_one_column_there_is_no_bias() -> None:
    """Zwei verschiedene Werte reichen, einer nicht (``n_unique() < 2``)."""
    assert dictionary_bias(*_bias_inputs(LINEAR, {1: 20, 2: 20, 3: 20})) is None
    same_hits = [(1, 50, 10_000), (2, 50, 11_000), (3, 50, 12_000)]
    assert dictionary_bias(*_bias_inputs(same_hits, SIZES)) is None
    # Zwei verschiedene Größen über drei Bezirke genügen.
    assert dictionary_bias(*_bias_inputs(LINEAR, {1: 10, 2: 10, 3: 30})) is not None


def test_a_district_without_voters_has_no_spread_of_voters() -> None:
    """``eligible_spread`` ist 0, wo die kleinste Wahlberechtigtenzahl 0 ist (keine Division)."""
    metrics = district_metrics(_results(LINEAR), _dictionary(SIZES))
    results = pl.DataFrame(
        {DISTRICT: [1, 2, 3], ELIGIBLE_TOTAL: [10_000, 11_000, 0]},
        schema={DISTRICT: pl.Int64, ELIGIBLE_TOTAL: pl.Int64},
    )
    found = dictionary_bias(metrics, results)
    assert found is not None and found.eligible_spread == 0.0


def test_the_mini_fixture_matches_polars(mini_run: Layout) -> None:
    frame = pl.read_parquet(mini_run.district_metrics)
    results = pl.read_parquet(mini_run.results)
    dictionary = pl.read_parquet(mini_run.dictionary)
    assert frame.height == results.height
    sizes = dict(dictionary.select(DISTRICT, pl.col(TERMS).list.len()).iter_rows())
    assert dict(frame.select(DISTRICT, TERM_COUNT).iter_rows()) == sizes
    expected = dict(results.select(DISTRICT, RATE).iter_rows())
    mean = sum(expected.values()) / len(expected)
    for row in frame.iter_rows(named=True):
        assert row[PER_TERM] == pytest.approx(row[HITS] / sizes[row[DISTRICT]])
        assert row[PER_1000] == pytest.approx(expected[row[DISTRICT]] * 1000.0)
        assert row[CITY_MEAN] == pytest.approx(mean)
        assert row[DEVIATION] == pytest.approx(expected[row[DISTRICT]] / mean - 1.0)
