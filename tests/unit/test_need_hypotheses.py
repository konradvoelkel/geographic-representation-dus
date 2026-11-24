"""Die Tests von Vorhaben 22 an Handbeispielen: Permutation, Bootstrap, Holm, Moran's I, Schichten.

Bauplan ``docs/plans/22-bedarf.md``, § 6: der Permutationstest gegen ``scipy.stats.spearmanr`` bei
großem n (p auf zwei Stellen), Holm gegen eine Handrechnung, gleicher Seed gleiche Tabelle. Die
Zahlen der Messung selbst prüft ``tests/golden/test_need_numbers.py`` am Paket.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest
from scipy import stats
from shapely.geometry import box

from georep.analysis.need import (
    CONFIRMED,
    FOLLOWS,
    HYPOTHESES_SCHEMA,
    NO_LINK,
    NOT_CONFIRMED,
    UNEQUAL,
    bootstrap_interval,
    holm,
    hypothesis_table,
    interpretation,
    morans_i,
    neighbours,
    partial_spearman,
    permutation_test,
    spearman,
    verdict,
    within_strata,
)
from georep.errors import SchemaError
from georep.settings import NeedHypothesis, NeedSettings


def _correlated(n: int, strength: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    return x, strength * x + rng.normal(size=n)


@pytest.mark.parametrize(
    ("alternative", "scipy_alternative"), [("greater", "greater"), ("two-sided", "two-sided")]
)
def test_the_permutation_p_agrees_with_scipy_at_large_n(
    alternative: str, scipy_alternative: str
) -> None:
    x, y = _correlated(300, 0.12, seed=1)
    rho, p = permutation_test(
        x, y, alternative=alternative, permutations=20_000, rng=np.random.default_rng(7)
    )
    expected = stats.spearmanr(x, y, alternative=scipy_alternative)
    assert rho == pytest.approx(expected.statistic)
    assert p is not None and abs(p - expected.pvalue) < 0.01
    assert 0.0 < p <= 1.0


def test_the_permutation_p_is_never_zero_and_counts_the_observed_order() -> None:
    x = np.arange(10, dtype=float)
    rho, p = permutation_test(
        x, x, alternative="greater", permutations=99, rng=np.random.default_rng(0)
    )
    assert rho == pytest.approx(1.0)
    assert p == pytest.approx(1 / 100)  # keine Permutation erreicht rho = 1, also (1 + 0) / 100


def test_without_spread_there_is_no_test_and_no_draw() -> None:
    rng = np.random.default_rng(3)
    state = rng.bit_generator.state
    assert permutation_test(
        np.ones(5), np.arange(5.0), alternative="greater", permutations=10, rng=rng
    ) == (None, None)
    assert rng.bit_generator.state == state
    assert spearman(np.arange(2.0), np.arange(2.0)) is None


def test_the_bootstrap_interval_brackets_rho_and_is_reproducible() -> None:
    x, y = _correlated(41, 1.0, seed=2)
    low, high = bootstrap_interval(x, y, draws=500, rng=np.random.default_rng(22))
    rho = spearman(x, y)
    assert low is not None and high is not None and rho is not None
    assert low < rho < high
    assert bootstrap_interval(x, y, draws=500, rng=np.random.default_rng(22)) == (low, high)
    assert bootstrap_interval(x[:2], y[:2], draws=5, rng=np.random.default_rng(0)) == (None, None)


def test_holm_by_hand() -> None:
    # sortiert 0,01 · 3 = 0,03; 0,03 · 2 = 0,06; 0,04 · 1 = 0,04 -> monoton 0,06
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    # die Zahlen der Messung (§ 3.4)
    assert holm([0.0143, 0.0346, 0.6474]) == pytest.approx([0.0429, 0.0692, 0.6474])
    assert holm([0.5, 0.9]) == pytest.approx([1.0, 1.0])
    assert holm([]) == []


def test_the_verdict_is_holm_against_alpha() -> None:
    assert verdict(0.0429, 0.05) == CONFIRMED
    assert verdict(0.05, 0.05) == NOT_CONFIRMED
    assert verdict(None, 0.05) == NOT_CONFIRMED


@pytest.mark.parametrize(
    ("alternative", "rho", "p_holm", "expected"),
    [
        # § 8, H2: zweiseitig, drei Ausgänge
        ("two-sided", 0.3, 0.01, FOLLOWS),
        ("two-sided", -0.3, 0.01, UNEQUAL),
        ("two-sided", -0.336, 0.0692, NO_LINK),  # die Messung (§ 3.4)
        ("two-sided", 0.3, 0.05, NO_LINK),  # Holm verwirft erst unter alpha
        # einseitig (rho > 0) gibt es nur zwei: ein negatives rho prüft der Test nicht
        ("greater", 0.343, 0.0429, FOLLOWS),
        ("greater", -0.9, 0.01, NO_LINK),
        ("greater", 0.1, 0.6, NO_LINK),
        # ohne Test keine Deutung
        ("two-sided", None, None, None),
        ("greater", 0.2, None, None),
    ],
)
def test_the_reading_has_the_words_of_section_8(
    alternative: str, rho: float | None, p_holm: float | None, expected: str | None
) -> None:
    """Review 2026-11-24, K1: ``ergebnis`` sagte bei H2 nicht, in welche Richtung Holm verwirft."""
    assert interpretation(alternative, rho, p_holm, 0.05) == expected


def test_within_strata_removes_a_pure_stratum_effect() -> None:
    """Zwischen den Schichten hängt y an x, innerhalb nicht: rho innen nahe 0, außen groß."""
    rng = np.random.default_rng(4)
    strata = np.repeat(np.arange(6), 7)
    level = strata.astype(float)
    x = level + rng.normal(scale=0.1, size=strata.size)
    y = level + rng.normal(scale=0.1, size=strata.size)
    overall = spearman(x, y)
    inside, p = within_strata(x, y, strata, permutations=999, rng=np.random.default_rng(1))
    assert overall is not None and overall > 0.9
    assert inside is not None and abs(inside) < 0.35
    assert p is not None and p > 0.05


def test_within_one_stratum_is_the_plain_rank_correlation() -> None:
    x, y = _correlated(20, 0.5, seed=5)
    inside, _ = within_strata(
        x, y, np.zeros(20, dtype=np.int64), permutations=9, rng=np.random.default_rng(0)
    )
    assert inside == pytest.approx(spearman(x, y))


def _line(n: int) -> np.ndarray:
    weights = np.zeros((n, n))
    for i in range(n - 1):
        weights[i, i + 1] = weights[i + 1, i] = 1.0
    return weights


def test_morans_i_sees_clusters_and_alternation() -> None:
    rng = np.random.default_rng(0)
    clustered, p_clustered = morans_i(
        np.repeat([0.0, 1.0], 10), _line(20), permutations=999, rng=rng
    )
    alternating, p_alternating = morans_i(
        np.tile([0.0, 1.0], 10), _line(20), permutations=999, rng=rng
    )
    assert (
        clustered is not None and clustered > 0.8 and p_clustered is not None and p_clustered < 0.01
    )
    assert (
        alternating is not None
        and alternating < -0.9
        and p_alternating is not None
        and p_alternating > 0.9
    )


def test_morans_i_without_neighbours_or_spread_is_undefined() -> None:
    rng = np.random.default_rng(0)
    assert morans_i(np.arange(4.0), np.zeros((4, 4)), permutations=9, rng=rng) == (None, None)
    assert morans_i(np.ones(4), _line(4), permutations=9, rng=rng) == (None, None)


def test_neighbours_need_a_shared_edge_not_a_corner() -> None:
    areas = [
        box(0, 0, 100, 100),
        box(100, 0, 200, 100),
        box(200, 0, 300, 100),
        box(300, 100, 400, 200),
    ]
    matrix = neighbours(areas, 50.0)
    assert matrix.tolist() == [
        [0.0, 1.0, 0.0, 0.0],
        [1.0, 0.0, 1.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],  # die Ecke bei (300, 100) zählt nicht
        [0.0, 0.0, 0.0, 0.0],
    ]


def test_partial_spearman_removes_a_common_driver() -> None:
    rng = np.random.default_rng(6)
    z = rng.normal(size=200)
    x, y = z + rng.normal(scale=0.3, size=200), z + rng.normal(scale=0.3, size=200)
    assert spearman(x, y) is not None and spearman(x, y) > 0.7  # type: ignore[operator]
    assert abs(partial_spearman(x, y, z) or 1.0) < 0.2


# --- die Tabelle ---------------------------------------------------------------------------------

H1 = NeedHypothesis(
    name="H1",
    need="x",
    attention="y",
    alternative="greater",
    fixed="abc1234",
    robust_need=["x2"],
    robust_without=[1],
)
H2 = NeedHypothesis(
    name="H2",
    need="x",
    attention="z",
    alternative="two-sided",
    fixed="abc1234",
    robust_control="x2",
    robust_without=[1],
)


def _frame(n: int = 12) -> pl.DataFrame:
    x, y = _correlated(n, 2.0, seed=8)
    return pl.DataFrame(
        {
            "wahlkreis_id": list(range(1, n + 1)),
            "stadtbezirk": [1 + i // 4 for i in range(n)],
            "x": x,
            "x2": x * 2.0 + 1.0,
            "y": y,
            "z": np.random.default_rng(9).normal(size=n),
        }
    )


def _settings(**update: object) -> NeedSettings:
    base = NeedSettings(
        hypotheses=[H1, H2],
        explore=[("x", "z")],
        permutations=199,
        explore_permutations=99,
        bootstrap=99,
    )
    return base.model_copy(update=update)


def test_the_table_has_the_core_first_and_rows_in_their_order() -> None:
    frame = _frame()
    table = hypothesis_table(frame, _settings(), weights=_line(frame.height))
    assert table.schema == pl.Schema(HYPOTHESES_SCHEMA)
    assert table.columns[:6] == ["hypothese", "p", "p_holm", "ergebnis", "n", "festgelegt"]
    assert table.columns[6] == "deutung"  # die erste Spalte hinter dem Kern
    assert table.select("hypothese", "rechnung").rows() == [
        ("H1", "haupttest"),
        ("H1", "robustheit"),
        ("H1", "robustheit"),
        ("H2", "haupttest"),
        ("H2", "robustheit"),
        ("H2", "robustheit"),
        ("H1", "innerhalb"),
        ("H2", "innerhalb"),
        ("H1", "moran_residuen"),
        ("H1", "moran_bedarf"),
        ("H1", "moran_aufmerksamkeit"),
        ("H2", "moran_residuen"),
        ("H2", "moran_bedarf"),
        ("H2", "moran_aufmerksamkeit"),
        (None, "paar"),
    ]
    main = table.filter(pl.col("rechnung") == "haupttest")
    assert main.get_column("ergebnis").to_list()[0] == CONFIRMED  # y hängt stark an x
    assert main.get_column("deutung").to_list()[0] == FOLLOWS
    assert table.filter(pl.col("rechnung") != "haupttest").get_column("deutung").null_count() == 13
    assert table.filter(pl.col("explorativ")).get_column("festgelegt").null_count() == 9
    robust = table.filter(pl.col("rechnung") == "robustheit")
    assert robust.get_column("ohne").to_list() == [[1], [], [1], []]
    assert robust.get_column("kontrolle").to_list() == ["", "", "", "x2"]
    # x2 ist eine streng monotone Funktion von x: dieselben Ränge, dasselbe rho
    assert robust.row(1, named=True)["wert"] == pytest.approx(main.row(0, named=True)["wert"])


def test_the_districts_left_out_belong_to_each_hypothesis() -> None:
    """Review 2026-11-24, N8: die Liste der Robustheit ist vorab festgelegt und steht in der
    Hypothese, nicht in ``analysis.exclude_districts``, das eine andere Rechnung steuert."""
    frame = _frame()
    h1 = H1.model_copy(update={"robust_without": [3, 2]})
    h2 = H2.model_copy(update={"robust_without": []})
    table = hypothesis_table(frame, _settings(hypotheses=[h1, h2]), weights=_line(frame.height))
    robust = table.filter(pl.col("rechnung") == "robustheit")
    assert robust.get_column("ohne").to_list() == [[2, 3], [], []]
    assert robust.get_column("n").to_list()[0] == frame.height - 2


def test_the_same_seed_writes_the_same_table() -> None:
    frame = _frame()
    first = hypothesis_table(frame, _settings(), weights=_line(frame.height))
    assert first.equals(hypothesis_table(frame, _settings(), weights=_line(frame.height)))
    other = hypothesis_table(frame, _settings(seed=23), weights=_line(frame.height))
    assert not first.equals(other)


def test_a_missing_value_leaves_the_district_out_and_n_says_so() -> None:
    frame = _frame().with_columns(
        pl.when(pl.col("wahlkreis_id") == 3).then(None).otherwise(pl.col("y")).alias("y")
    )
    table = hypothesis_table(frame, _settings(), weights=_line(frame.height))
    assert table.filter(pl.col("rechnung") == "haupttest").get_column("n").to_list() == [11, 12]


def test_a_test_without_values_keeps_its_row_and_its_place_in_holm() -> None:
    """Review 2026-11-24, N2: ohne Werte bleibt die Zeile mit ``p`` null, ohne Ergebnis und Deutung;
    Holm rechnet über alle drei vorab festgelegten Tests (m = 3), nicht über die zwei mit p."""
    third = NeedHypothesis(
        name="H3", need="x2", attention="y", alternative="greater", fixed="abc1234"
    )
    frame = _frame().with_columns(pl.lit(None, dtype=pl.Float64).alias("z"))
    settings = _settings(hypotheses=[H1, H2, third])
    table = hypothesis_table(frame, settings, weights=_line(frame.height))
    h1, h2, h3 = table.filter(pl.col("rechnung") == "haupttest").to_dicts()
    assert (h2["p"], h2["p_holm"], h2["ergebnis"], h2["deutung"], h2["n"]) == (
        None,
        None,
        None,
        None,
        0,
    )
    assert [h1["p_holm"], h3["p_holm"]] == pytest.approx(
        [holm([h1["p"], 1.0, h3["p"]])[i] for i in (0, 2)]
    )
    assert h1["p_holm"] != pytest.approx(holm([h1["p"], h3["p"]])[0])  # nicht m = 2
    # Haupttest, zweimal Robustheit, innerhalb, dreimal Moran: alle ohne Wert
    assert table.filter(pl.col("hypothese") == "H2").get_column("wert").null_count() == 7


def test_a_column_the_hypotheses_name_must_exist() -> None:
    frame = _frame().drop("z")
    with pytest.raises(SchemaError, match="'z'"):
        hypothesis_table(frame, _settings(), weights=_line(frame.height))


def test_without_hypotheses_and_pairs_the_table_is_empty_with_its_schema() -> None:
    frame = _frame()
    table = hypothesis_table(frame, NeedSettings(), weights=_line(frame.height))
    assert table.height == 0 and table.schema == pl.Schema(HYPOTHESES_SCHEMA)
