"""Rhythmus und vorab festgelegte Tests von Vorhaben 17 (``analysis.cycles``) an kleinen Beispielen.

Wahljahr an den Grenzen (31.08., 01.09., Wahltag, angeschnittene Monate je Periode), Haushaltsmonat
mit Gleichstand, unter dem Minimum und ohne Haushaltsanträge, die Monatstabelle lückenlos, und die
drei exakten Tests gegen Rechnungen von Hand: OLS an Zahlen mit glattem Ergebnis, das
Zwei-Wege-Modell an 3 × 3, Jonckheere-Terpstra an 2 + 2 + 1 (Messdokument 17, § 6).
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from georep.analysis.cycles import (
    BUDGET_SCHEMA,
    HYPOTHESES_EXTRA,
    MONTH_SCHEMA,
    PREREGISTERED,
    CycleRules,
    PeriodData,
    Unit,
    budget_months,
    budget_test,
    complete_years,
    cycle_hypotheses,
    election_year,
    jonckheere,
    month_table,
    multiset_permutations,
    pre_election_test,
    pre_election_years,
)
from georep.analysis.hypotheses import CONFIRMED, CORE_SCHEMA, NOT_CONFIRMED, PROVISIONAL
from georep.analysis.lexicon import document_categories, load_lexicon, parse_lexicon
from tests.unit.test_lexicon import MEASURED

NRW = (date(2014, 5, 25), date(2020, 9, 13), date(2025, 9, 14))
RULES = CycleRules.of(
    start_month=9,
    elections=NRW,
    budget_pattern=r"haushalts(begleit)?-?antrag",
    budget_minimum=5,
    instrument_types={
        "anfrage": "anfrage",
        "zanfrage": "anfrage",
        "antrag": "antrag",
        "haushaltsantrag": "antrag",
    },
    instrument_titles=[("antrag", "antrag"), (r"\b(z?anfrage|nachfrage)", "anfrage")],
    head_chars=2000,
)


# --- Wahljahr -------------------------------------------------------------------------------------


def test_the_election_year_turns_on_the_first_of_september() -> None:
    assert election_year(date(2020, 8, 31), 9) == 2019
    assert election_year(date(2020, 9, 1), 9) == 2020
    assert election_year(date(2020, 9, 13), 9) == 2020  # der Wahltag
    assert election_year(date(2021, 1, 15), 9) == 2020


@pytest.mark.parametrize(
    ("first", "last", "years"),
    [
        # die drei Datensätze, Messdokument 17, § 8.0
        (date(2014, 5, 25), date(2020, 9, 12), (2014, 2015, 2016, 2017, 2018, 2019)),
        (date(2020, 9, 13), date(2025, 9, 14), (2020, 2021, 2022, 2023, 2024)),
        (date(2025, 9, 15), date(2026, 10, 13), (2025,)),
        # der erste Monat darf angeschnitten sein, ein späterer nicht
        (date(2020, 9, 30), date(2021, 8, 31), (2020,)),
        (date(2020, 10, 1), date(2021, 8, 31), ()),
        # das letzte Wahljahr muss bis zu seinem letzten Tag reichen
        (date(2020, 9, 1), date(2021, 8, 30), ()),
        (date(2021, 1, 1), date(2020, 1, 1), ()),
    ],
)
def test_complete_years_of_a_period(first: date, last: date, years: tuple[int, ...]) -> None:
    assert complete_years(first, last, 9) == years


def test_the_pre_election_year_is_the_last_one_ending_before_the_vote() -> None:
    assert pre_election_years(range(2014, 2020), RULES) == {2019}
    assert pre_election_years(range(2020, 2025), RULES) == {2024}
    assert pre_election_years([2025], RULES) == set()  # die laufende Periode hat noch keines
    # 2014: das Jahr vor der Wahl im Mai läge vor dem Datensatz
    assert pre_election_years([2014, 2015], RULES) == set()


# --- Monate und Haushaltsmonate ---------------------------------------------------------------------


def _docs(rows: list[tuple[str, date | None, str, str, str, str, str]]) -> tuple[pl.DataFrame, ...]:
    corpus = pl.DataFrame(
        [r[:5] for r in rows],
        schema={
            "id": pl.String,
            "date": pl.Date,
            "paper_type": pl.String,
            "name": pl.String,
            "text": pl.String,
        },
        orient="row",
    )
    originators = pl.DataFrame(
        [(r[0], r[5]) for r in rows], schema=["id", "urheber_art"], orient="row"
    )
    bodies = pl.DataFrame([(r[0], r[6]) for r in rows], schema=["id", "gremium_art"], orient="row")
    return corpus, originators, bodies


def test_the_month_table_is_gapless_and_sums_to_the_corpus() -> None:
    corpus, originators, bodies = _docs(
        [
            (
                "a",
                date(2020, 8, 20),
                "Anfrage CDU",
                "Anfrage zur Schule",
                "text",
                "Fraktion",
                "rat",
            ),
            ("b", date(2020, 9, 14), "Haushaltsantrag SPD", "Mittel", "text", "Fraktion", "rat"),
            ("c", date(2020, 9, 20), "Vorlage", "Antrag auf Nachfrage", "", "Verwaltung", "rat"),
            # Oktober fehlt ganz; November mit zAnfrage
            ("d", date(2020, 11, 2), "zAnfrage Grüne", "Wege", "text", "Fraktion", "ausschuss"),
            ("e", None, "Vorlage", "Nachfrage zum Haushaltsbegleitantrag", "x", "Person", "rat"),
        ]
    )
    table = month_table(corpus, originators, bodies, RULES, years=[2020])
    assert table.schema == pl.Schema(MONTH_SCHEMA)
    assert int(table.get_column("dokumente").sum()) == 5
    dated = table.filter(pl.col("monat").is_not_null())
    # vier Monate, je Monat jede der vier Kombinationen, die vorkommen
    assert dated.get_column("monat").unique().sort().to_list() == [
        date(2020, 8, 1),
        date(2020, 9, 1),
        date(2020, 10, 1),
        date(2020, 11, 1),
    ]
    assert dated.height == 4 * 4
    # Wahljahr nur im vollständigen Wahljahr 2020, August 2020 gehört zu keinem
    by_month = dict(dated.group_by("monat").agg(pl.col("wahljahr").first()).iter_rows())
    assert by_month[date(2020, 8, 1)] is None and by_month[date(2020, 11, 1)] == 2020
    # Instrumente: Art vor Titel, im Titel „antrag" vor „anfrage"
    kinds = {
        (r["monat"], r["urheber_art"], r["instrument"])
        for r in table.filter(pl.col("dokumente") > 0).iter_rows(named=True)
    }
    assert (date(2020, 8, 1), "Fraktion", "anfrage") in kinds
    assert (date(2020, 9, 1), "Fraktion", "antrag") in kinds  # Haushaltsantrag SPD
    assert (date(2020, 9, 1), "Verwaltung", "antrag") in kinds  # „Antrag auf Nachfrage"
    assert (date(2020, 11, 1), "Fraktion", "anfrage") in kinds  # zAnfrage
    assert (None, "Person", "antrag") in kinds  # Titel mit Haushaltsbegleitantrag
    # ohne Datum am Ende, Haushaltsanträge aus Art oder Titel
    assert table.row(-1, named=True)["monat"] is None
    assert int(table.get_column("haushaltsantraege").sum()) == 2
    assert int(table.get_column("mit_text").sum()) == 4


def _months(budget: dict[tuple[int, int], int], years: list[int]) -> pl.DataFrame:
    rows = []
    for (year, month), n in budget.items():
        rows.append(
            {
                "monat": date(year, month, 1),
                "wahljahr": election_year(date(year, month, 1), 9),
                "gremium_art": "rat",
                "urheber_art": "Fraktion",
                "instrument": "antrag",
                "dokumente": n,
                "mit_text": n,
                "haushaltsantraege": n,
            }
        )
    frame = pl.DataFrame(rows, schema=MONTH_SCHEMA)
    return frame.with_columns(
        pl.when(pl.col("wahljahr").is_in(years)).then(pl.col("wahljahr")).cast(pl.Int32)
    )


def test_the_budget_month_breaks_ties_toward_the_earlier_month_of_the_election_year() -> None:
    months = _months(
        {
            (2020, 12): 3,  # Dezember und Januar gleich: der Dezember liegt im Wahljahr vorn
            (2021, 1): 3,
            (2021, 11): 4,  # 2021/22: vier im November, einer im Mai -- genau das Minimum
            (2022, 5): 1,
            (2022, 10): 4,  # 2022/23: vier, unter dem Minimum
            (2023, 9): 0,  # 2023/24: keine
        },
        years=[2020, 2021, 2022, 2023],
    )
    budget = budget_months(months, RULES)
    assert budget.schema == pl.Schema(BUDGET_SCHEMA)
    assert budget.rows() == [
        (2020, 12, 6, 3),
        (2021, 11, 5, 4),
        (2022, None, 4, None),
        (2023, None, 0, None),
    ]


# --- exakte Tests ---------------------------------------------------------------------------------


def test_multiset_permutations_lists_each_arrangement_once() -> None:
    found = multiset_permutations([0, 0, 1, 2])
    assert found.shape == (12, 4)  # 4! / 2!
    assert len({tuple(r) for r in found.tolist()}) == 12
    assert all(sorted(r) == [0, 0, 1, 2] for r in found.tolist())


def _delta_by_the_formula(table: np.ndarray, assignment: list[int]) -> float:
    """§ 8.2 wörtlich wie im Messskript: beide Matrizen doppelt zentriert, dann der Quotient."""

    def center(a: np.ndarray) -> np.ndarray:
        return a - a.mean(axis=1, keepdims=True) - a.mean(axis=0, keepdims=True) + a.mean()

    y = center(np.log1p(table))
    t = np.zeros_like(table)
    for row, column in enumerate(assignment):
        t[row, column] = 1.0
    tt = center(t)
    return float((tt * y).sum() / (tt * tt).sum())


def test_the_budget_test_on_three_by_three_by_hand() -> None:
    """Drei Wahljahre, drei Monate, je Jahr ein anderer Haushaltsmonat: 3! = 6 Zuordnungen.

    Der Haushaltsmonat ist in jedem Jahr der stärkste, also ist die beobachtete Zuordnung die
    einzige mit dem größten δ: p = 1/6. Zentriert trägt die Diagonale +2/3, jede andere Zelle −1/3
    von d = ln 31 − ln 6; ein Tausch zweier Jahre gibt δ = 0, ein Dreierzyklus −d/2, also ist sie
    auch im Betrag die einzige: zweiseitig ebenfalls 1/6.
    """
    table = np.array([[30.0, 5.0, 5.0], [5.0, 30.0, 5.0], [5.0, 5.0, 30.0]])
    result = budget_test(table, [0, 1, 2])
    assert result.count == 6
    assert result.statistic == pytest.approx(_delta_by_the_formula(table, [0, 1, 2]))
    # ln(31) − ln(6) im Zwei-Wege-Modell: jede Zelle zentriert um ±(ln 31 − ln 6)/3
    assert result.statistic == pytest.approx(math.log(31) - math.log(6))
    assert result.p == pytest.approx(1 / 6) and result.p_two_sided == pytest.approx(1 / 6)


def test_the_budget_test_counts_every_arrangement_of_repeated_months() -> None:
    table = np.array([[12.0, 4.0, 3.0], [10.0, 5.0, 2.0], [3.0, 11.0, 4.0], [2.0, 4.0, 9.0]])
    assignment = [0, 0, 1, 2]
    result = budget_test(table, assignment)
    assert result.count == 12
    deltas = [_delta_by_the_formula(table, list(r)) for r in multiset_permutations(assignment)]
    assert result.statistic == pytest.approx(_delta_by_the_formula(table, assignment))
    assert result.p == pytest.approx(sum(d >= result.statistic - 1e-12 for d in deltas) / 12)


def test_jonckheere_on_two_two_one_by_hand() -> None:
    """Gruppen {1, 2}, {3, 4}, {5}: jedes spätere Paar ist größer, JT = 4 + 2 + 2 = 8, das Maximum.

    5! / (2! 2! 1!) = 30 Zuordnungen, nur die beobachtete erreicht 8: p = 1/30.
    """
    result = jonckheere([1.0, 2.0, 3.0, 4.0, 5.0], [2, 2, 1])
    assert (result.statistic, result.count) == (8.0, 30)
    assert result.p == pytest.approx(1 / 30)
    falling = jonckheere([5.0, 4.0, 3.0, 2.0, 1.0], [2, 2, 1])
    assert falling.statistic == 0.0 and falling.p == 1.0


def test_jonckheere_counts_ties_half() -> None:
    # {1, 1}, {1}: zwei Paare, beide gleich, JT = 1; jede Zuordnung gibt dasselbe: p = 1
    result = jonckheere([1.0, 1.0, 1.0], [2, 1])
    assert result.statistic == 1.0 and result.p == 1.0 and result.count == 3


def _units() -> list[Unit]:
    """Zwei Perioden mit Anlaufjahr, zwei Vergleichsjahren und Vorwahljahr, ln-Werte gesetzt.

    Das Vorwahljahr liegt in beiden genau 0,5 über dem Mittel der Vergleichsjahre, die Reste sind
    ±0,1: δ = 0,5, Restvarianz 0,04/3, Standardfehler √(0,04/3 · 3/4) = 0,1, t = 5 bei df = 3.
    """
    logs = {
        ("A", 1): 0.7,
        ("A", 2): 1.0,
        ("A", 3): 1.2,
        ("A", 4): 1.6,
        ("B", 1): 2.9,
        ("B", 2): 2.0,
        ("B", 3): 2.2,
        ("B", 4): 2.6,
    }
    return [Unit(p, y, math.exp(v), y == 4, y == 1) for (p, y), v in logs.items()]


def test_the_pre_election_model_by_hand() -> None:
    result = pre_election_test(_units())
    assert result.delta == pytest.approx(0.5)
    assert result.se == pytest.approx(0.1)
    assert result.t == pytest.approx(5.0) and result.df == 3 and result.n == 6
    assert result.p == pytest.approx(0.0076963, abs=1e-6)  # t-Verteilung, 3 Freiheitsgrade
    # je Periode drei Kandidaten, nur die beobachtete Wahl gibt 0,5
    assert result.count == 9 and result.p_random == pytest.approx(1 / 9)


def test_with_the_first_years_the_model_has_two_more_years() -> None:
    result = pre_election_test(_units(), with_first=True)
    assert result.n == 8 and result.df == 5 and result.count == 16


def test_the_share_variant_takes_values_as_they_are() -> None:
    units = [Unit(u.period, u.year, math.log(u.value), u.pre_election, u.first) for u in _units()]
    assert pre_election_test(units, log=False).delta == pytest.approx(0.5)


# --- die ganze Tabelle an drei kleinen Perioden ---------------------------------------------------

THREE = CycleRules.of(
    start_month=9,
    elections=(date(2017, 9, 10), date(2020, 9, 13)),
    budget_pattern="haushaltsantrag",
    budget_minimum=5,
    instrument_types={"anfrage": "anfrage", "antrag": "antrag"},
    instrument_titles=[],
    head_chars=2000,
)
WORDS = ["flüchtlinge", "mietpreisbremse", "corona", "schulhof", "radweg", "spielplatz"]


def _period(name: str, first: date, last: date, budget_month: int, seed: int) -> PeriodData:
    """Ein synthetischer Datensatz: je Tag mit Rest 0 bis 2 nach 5 ein Dokument, im Haushaltsmonat
    dazu je solchem Tag ein Haushaltsantrag einer Fraktion, Texte mit Wörtern des Lexikons."""
    rnd = random.Random(seed)
    rows: list[tuple[str, date | None, str, str, str, str, str]] = []
    day = first
    number = 0
    while day <= last:
        if day.toordinal() % 5 < 3:
            number += 1
            fraction = rnd.random() < 0.45
            kind = rnd.choice(["Anfrage", "Antrag", "Vorlage"])
            text = " ".join(rnd.choice(WORDS) for _ in range(3)) if rnd.random() < 0.9 else ""
            rows.append(
                (
                    f"{name}-{number:05d}",
                    day,
                    kind,
                    f"Titel {number}",
                    text,
                    "Fraktion" if fraction else rnd.choice(["Verwaltung", "Person"]),
                    rnd.choice(["rat", "ausschuss"]),
                )
            )
            if day.month == budget_month:  # im Haushaltsmonat dazu ein Haushaltsantrag
                number += 1
                rows.append(
                    (
                        f"{name}-{number:05d}",
                        day,
                        "Haushaltsantrag",
                        "Mittel",
                        "",
                        "Fraktion",
                        "rat",
                    )
                )
        day += timedelta(days=1)
    corpus, originators, bodies = _docs(rows)
    years = complete_years(first, last, THREE.start_month)
    months = month_table(corpus, originators, bodies, THREE, years)
    categories = document_categories(corpus, load_lexicon("bundespolitik"))
    documents = (
        corpus.select("id", "date", (pl.col("text") != "").alias("mit_text"))
        .join(originators, on="id")
        .join(categories.select("id", "kategorien", "kopf"), on="id")
        .sort("id")
    )
    return PeriodData(name, months, budget_months(months, THREE), documents)


@pytest.fixture(scope="module")
def three_periods() -> list[PeriodData]:
    return [
        _period("p1", date(2014, 9, 1), date(2017, 9, 9), 11, 1),
        _period("p2", date(2017, 9, 10), date(2020, 9, 12), 12, 2),
        _period("p3", date(2020, 9, 13), date(2021, 10, 31), 2, 3),
    ]


def test_the_table_has_every_test_of_paragraph_eight_in_order(
    three_periods: list[PeriodData],
) -> None:
    table = cycle_hypotheses(three_periods, THREE, load_lexicon("bundespolitik"))
    assert list(table.schema) == [*CORE_SCHEMA, *HYPOTHESES_EXTRA]
    names = table.get_column("hypothese").to_list()
    assert names[:7] == [
        "H17.1",
        "H17.1/S1.1",
        "H17.1/S1.2",
        "H17.1/S1.3",
        "H17.1/S1.4",
        "H17.1/S1.5/anfrage",
        "H17.1/S1.5/antrag",
    ]
    assert names[7:10] == ["H17.2", "H17.2/S2.1", "H17.2/S2.2"]
    assert names[10:13] == ["H17.3", "H17.3/S3.1", "H17.3/S3.2"]
    assert names[13:23] == [f"H17.3/S3.3/{c}" for c in load_lexicon("bundespolitik").ids]
    assert names[23:] == ["H17.3/S3.4/politisch", "H17.3/S3.4/verwaltung"]
    main = table.filter(pl.col("rolle") == "Haupttest")
    assert main.get_column("hypothese").to_list() == ["H17.1", "H17.2", "H17.3"]
    assert main.get_column("ergebnis").null_count() == 0
    assert table.filter(pl.col("rolle") != "Haupttest").get_column("p_holm").null_count() == 22
    assert set(table.get_column("festgelegt")) == {PREREGISTERED}
    assert set(table.get_column("lexikon")) == {"bundespolitik 2026-11-23.1"}
    last = max(d for p in three_periods for d in p.documents.get_column("date").to_list())
    assert set(table.get_column("daten_bis")) == {last}
    rows = {r["hypothese"]: r for r in table.iter_rows(named=True)}
    assert rows["H17.1"]["n"] == 4 and rows["H17.1"]["zuordnungen"] == 4  # je Periode zwei Jahre
    assert rows["H17.1/S1.3"]["n"] == 6 and rows["H17.1/S1.3"]["zuordnungen"] == 9
    assert rows["H17.2"]["n"] == 7  # sieben vollständige Wahljahre, jedes mit Haushaltsmonat
    assert rows["H17.3"]["n"] == 7 and rows["H17.3"]["zuordnungen"] == 140  # 7! / (3! 3! 1!)
    assert len(rows["H17.3"]["anteile"]) == 3
    assert rows["H17.3"]["effekt"] == pytest.approx(
        rows["H17.3"]["anteile"][2] - rows["H17.3"]["anteile"][0]
    )


def test_the_budget_month_is_confirmed_where_the_motions_pile_up(
    three_periods: list[PeriodData],
) -> None:
    """Im synthetischen Datensatz stehen die Haushaltsanträge nur im Haushaltsmonat: H17.2 fällt."""
    table = cycle_hypotheses(three_periods, THREE, load_lexicon("bundespolitik"))
    h172 = table.filter(pl.col("hypothese") == "H17.2").row(0, named=True)
    assert h172["effekt"] > 0 and h172["p"] < 0.05 / 3 and h172["ergebnis"] == CONFIRMED
    for row in table.filter(pl.col("rolle") == "Haupttest").iter_rows(named=True):
        assert row["ergebnis"] in (CONFIRMED, NOT_CONFIRMED)


def test_an_unvalidated_lexicon_keeps_h17_3_provisional(three_periods: list[PeriodData]) -> None:
    text = MEASURED.read_text(encoding="utf-8").replace('"2026-11-23.1"', '"9999-01-01.1"', 1)
    table = cycle_hypotheses(three_periods, THREE, parse_lexicon("bundespolitik", text))
    words = dict(table.select("hypothese", "ergebnis").rows())
    assert words["H17.3"] == PROVISIONAL
    assert words["H17.1"] in (CONFIRMED, NOT_CONFIRMED)


def test_the_periods_must_stand_in_order(three_periods: list[PeriodData]) -> None:
    with pytest.raises(Exception, match="aufsteigend"):
        cycle_hypotheses(three_periods[::-1], THREE, load_lexicon("bundespolitik"))
