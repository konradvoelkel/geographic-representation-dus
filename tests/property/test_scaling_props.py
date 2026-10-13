"""Eigenschaften der Normierungen (Punkt 46), für alle Eingaben statt an Beispielen.

Was hier steht, gilt für jede Stadt und jede Stichprobe: die Abweichungen heben sich auf, ein
Verhältnis ist nie negativ, feste Klassen sind monoton. Der erste Shrink dieser Datei wäre der
Befund gewesen, dass eine Stadt ohne Treffer kein Stadtmittel hat (Review vom 2026-10-13).
"""

from __future__ import annotations

import math

import polars as pl
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from georep.analysis.hits import DISTRICT, RATE, TERMS
from georep.analysis.parties import PARTY_DEVIATION, PARTY_MEAN, PARTY_RATIO, SHARE
from georep.analysis.scaling import (
    CITY_MEAN,
    DEVIATION,
    PER_1000,
    PER_TERM,
    TERM_COUNT,
    deviation_from,
    dictionary_bias,
    district_metrics,
    relative_to,
    unweighted_mean,
)
from georep.prep.voters import ELIGIBLE_TOTAL
from georep.report.charts import classify_fixed
from georep.search.index import HITS

districts = st.lists(
    st.tuples(
        st.integers(1, 60),  # Wahlbezirk
        st.integers(0, 5_000),  # Treffer
        st.integers(1, 200_000),  # Wahlberechtigte
        st.integers(0, 900),  # Begriffe im Wörterbuch
    ),
    min_size=1,
    max_size=12,
    unique_by=lambda row: row[0],
)

# Vier aufsteigende Grenzen wie in ``[report.diverging]``
boundaries = st.lists(
    st.floats(-50.0, 50.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=6,
    unique=True,
).map(sorted)
finite = st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False)


def _frames(rows: list[tuple[int, int, int, int]]) -> tuple[pl.DataFrame, pl.DataFrame]:
    results = pl.DataFrame(
        {
            DISTRICT: [r[0] for r in rows],
            HITS: [r[1] for r in rows],
            ELIGIBLE_TOTAL: [r[2] for r in rows],
        },
        schema={DISTRICT: pl.Int64, HITS: pl.Int64, ELIGIBLE_TOTAL: pl.Int64},
    ).with_columns((pl.col(HITS) / pl.col(ELIGIBLE_TOTAL)).alias(RATE))
    dictionary = pl.DataFrame(
        {
            DISTRICT: [r[0] for r in rows],
            TERMS: [[f"t{i}" for i in range(r[3])] for r in rows],
        },
        schema={DISTRICT: pl.Int64, TERMS: pl.List(pl.String)},
    )
    return results, dictionary


@given(rows=districts)
@settings(max_examples=120, deadline=None)
def test_the_metrics_hold_their_contracts_for_any_city(
    rows: list[tuple[int, int, int, int]],
) -> None:
    """Die Verträge selbst sind die Eigenschaft: deal prüft sie bei jedem Aufruf.

    Dazu die drei Aussagen, die kein Vertrag trägt: die Abweichungen summieren sich auf 0 (auch
    ohne einen einzigen Treffer), ein Bezirk ohne Begriffe hat 0 Treffer je Begriff, und je 1000
    ist die Quote mal 1000 — also dieselbe Ordnung.
    """
    results, dictionary = _frames(rows)
    frame = district_metrics(results, dictionary)
    assert frame.height == len(rows)
    assert abs(sum(frame.get_column(DEVIATION).to_list())) < 1e-9 * max(len(rows), 1)
    mean = float(frame.get_column(CITY_MEAN)[0])
    for row in frame.iter_rows(named=True):
        assert math.isfinite(row[DEVIATION]) and math.isfinite(row[PER_TERM])
        # Dieselbe Rechnung in Python rundet an anderer Stelle als Polars; verglichen wird der
        # Wert, nicht das letzte Bit.
        assert row[PER_TERM] == pytest.approx(
            row[HITS] / row[TERM_COUNT] if row[TERM_COUNT] else 0.0
        )
        assert row[PER_1000] == pytest.approx(row[RATE] * 1000.0)
        assert row[DEVIATION] == pytest.approx(row[RATE] / mean - 1.0 if mean > 0 else 0.0)
        assert row[DEVIATION] >= -1.0  # nie weniger als „gar keine Treffer"


@given(rows=districts)
@settings(max_examples=60, deadline=None)
def test_the_order_of_rate_and_deviation_is_the_same(
    rows: list[tuple[int, int, int, int]],
) -> None:
    """Die Abweichung ist eine streng monotone Umrechnung der Quote — der Grund für feste Grenzen."""
    frame = district_metrics(*_frames(rows))
    pairs = list(zip(frame.get_column(RATE), frame.get_column(DEVIATION), strict=True))
    for rate_a, dev_a in pairs:
        for rate_b, dev_b in pairs:
            if rate_a < rate_b:
                assert dev_a <= dev_b


@given(
    values=st.lists(
        st.tuples(st.integers(1, 20), finite), min_size=1, max_size=20, unique_by=lambda p: p[0]
    ),
    bounds=boundaries,
)
def test_fixed_classes_are_monotone_and_within_range(
    values: list[tuple[int, float]], bounds: list[float]
) -> None:
    found = classify_fixed(dict(values), bounds)
    assert found.count == len(bounds) + 1
    assert all(0 <= k < found.count for k in found.classes.values())
    by_key = dict(values)
    for one, klass_one in found.classes.items():
        for other, klass_other in found.classes.items():
            if by_key[one] < by_key[other]:
                assert klass_one <= klass_other


@given(
    groups=st.lists(
        st.tuples(st.integers(1, 5), st.floats(0.0, 1.0, allow_nan=False)),
        min_size=1,
        max_size=20,
    )
)
def test_the_group_mean_cancels_its_deviations_and_keeps_the_ratio_positive(
    groups: list[tuple[int, float]],
) -> None:
    """Dieselbe Regel wie bei den Parteien: ungewichtetes Mittel, Abweichung, Verhältnis."""
    frame = pl.DataFrame({"g": [g for g, _ in groups], SHARE: [v for _, v in groups]})
    found = frame.with_columns(unweighted_mean(SHARE, ["g"]).alias(PARTY_MEAN)).with_columns(
        (pl.col(SHARE) - pl.col(PARTY_MEAN)).alias(PARTY_DEVIATION),
        relative_to(SHARE, PARTY_MEAN).alias(PARTY_RATIO),
        deviation_from(SHARE, PARTY_MEAN).alias("relativ"),
    )
    assert bool((found.get_column(PARTY_RATIO) >= 0.0).all())
    assert all(math.isfinite(v) for v in found.get_column(PARTY_RATIO))
    assert all(math.isfinite(v) for v in found.get_column("relativ"))
    per_group = found.group_by("g").agg(pl.col(PARTY_DEVIATION).sum().abs().alias("rest"))
    assert all(rest < 1e-9 for rest in per_group.get_column("rest").to_list())


@given(value=st.floats(0.0, 1e6, allow_nan=False), mean=st.floats(0.0, 1e6, allow_nan=False))
def test_a_group_without_a_mean_is_neither_below_nor_above_it(value: float, mean: float) -> None:
    assume(mean == 0.0 or value / mean < 1e9)
    frame = pl.DataFrame({"v": [value], "m": [mean]}).with_columns(
        relative_to("v", "m").alias("q"), deviation_from("v", "m").alias("d")
    )
    if mean == 0.0:
        assert frame.get_column("q")[0] == 0.0 and frame.get_column("d")[0] == 0.0
    else:
        assert frame.get_column("d")[0] == pytest.approx(frame.get_column("q")[0] - 1.0)


@given(rows=districts)
@settings(max_examples=120, deadline=None)
def test_the_bias_does_not_depend_on_the_order_of_the_rows(
    rows: list[tuple[int, int, int, int]],
) -> None:
    """Ein Join legt die Zeilenfolge nicht fest, und die Kennzahlen lesen positionell aus ihm.

    Vor der Sortierung in ``dictionary_bias`` unterschieden sich zwei Aufrufe mit denselben Zeilen
    in anderer Folge im letzten Bit (0,5372474566602047 gegen …46); gedruckt sieht man das nicht,
    byteidentisch wird die Datei damit aber nie. Als Eigenschaft statt als Beispiel, weil die
    Aussage für jede Stadt gilt (Review-Befund 9, 2026-10-13).
    """
    results, dictionary = _frames(rows)
    forward = dictionary_bias(district_metrics(results, dictionary), results)
    turned = dictionary_bias(
        district_metrics(results.reverse(), dictionary.reverse()), results.reverse()
    )
    assert forward == turned
