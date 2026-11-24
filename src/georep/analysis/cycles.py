"""Rhythmus der Ratsarbeit und die vorab festgelegten Tests über die Perioden (Vorhaben 17).

Messdokument ``docs/plans/17-zeit.md``: § 8 legt drei Hypothesen fest, bevor eine Ergebnisgröße
gerechnet war (Commit ``9c7b3d6``, 2026-11-23 19:45), § 3 rechnet sie mit dem Messskript
``docs/plans/17-zeit-messung.py``. Dieses Modul rechnet dieselben Tests aus den Ausgaben der
Schritte, rein und ohne Settings (die Regeln kommen als ``CycleRules``):

* **Wahljahr** (§ 8.0): vom ersten Tag des ``start_month`` bis zum Tag davor im Folgejahr, benannt
  nach dem Jahr seines Beginns. Vollständig ist ein Wahljahr in einer Periode, wenn die Periode es
  abdeckt; nur sein erster Monat darf um die Tage vor der Wahl gekürzt sein (die Hauptperiode
  beginnt am 13. September 2020 und hat das Wahljahr 2020/21). Monate außerhalb vollständiger
  Wahljahre gehören zu keinem. Monatsreihen sind autokorreliert; darum vergleichen alle drei Tests
  ganze Wahljahre oder denselben Kalendermonat über Jahre.
* **H17.1 Wahlzyklus**: ln der Fraktionsdokumente je Wahljahr, OLS mit einer Konstanten je Periode
  und einem Effekt des Vorwahljahrs, t einseitig; das Anlaufjahr (erstes Wahljahr) bleibt draußen.
  Das Vorwahljahr einer Wahl ist das letzte vollständige Wahljahr, das vor ihr endet.
* **H17.2 Haushaltsrhythmus**: ln(1 + Fraktionsdokumente) je Wahljahr und Kalendermonat, ein
  Zwei-Wege-Modell mit Effekt des Haushaltsmonats, Randomisierung über alle Zuordnungen der
  beobachteten Haushaltsmonate zu den Wahljahren (ganze Jahre werden vertauscht).
* **H17.3 Bundespolitisches Vokabular**: Anteil der Dokumente mit Text und Treffer einer
  Strukturkategorie je Wahljahr, Jonckheere-Terpstra exakt über alle Zuordnungen der Wahljahre zu
  den Perioden, einseitig steigend; gewertet erst, wenn das Lexikon validiert ist.

Holm über die drei Haupttests (``analysis.hypotheses``); die Sensitivitäten aus § 8 stehen als
eigene Zeilen in derselben Tabelle und bestätigen nichts.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations, product

import deal
import numpy as np
import polars as pl
from scipy import stats

from georep.analysis.hypotheses import check_hypotheses, family, hypothesis_frame
from georep.analysis.lexicon import EVENT, MIN_PRECISION, STRUCTURE, Lexicon, validated_precision

__all__ = [
    "BUDGET_SCHEMA",
    "HYPOTHESES_EXTRA",
    "MONTH_SCHEMA",
    "PREREGISTERED",
    "CycleRules",
    "PeriodData",
    "PreElection",
    "Randomization",
    "Unit",
    "budget_months",
    "budget_test",
    "complete_years",
    "cycle_hypotheses",
    "election_year",
    "jonckheere",
    "month_table",
    "multiset_permutations",
    "pre_election_test",
    "pre_election_years",
]


# Die Urheberklassen aus Option 04 (``analysis.parties.URHEBER_ARTEN``), wie § 8.0 sie nennt
FRACTION = "Fraktion"
ADMINISTRATION = "Verwaltung"
POLITICAL = ("Fraktion", "Person", "unbekannt")
OTHER = "sonst"  # weder Anfrage noch Antrag (S1.5)
SPRING = (3, 4, 5, 6)  # S1.2: März bis Juni, die Monate der Pandemie im Vorwahljahr 2019/20
PREREGISTERED = "9c7b3d6"  # Commit der Festlegung von H17.1 bis H17.3 (2026-11-23 19:45)
_TIE = 1e-12  # eine Zuordnung zählt, wenn ihre Statistik bis auf Rundung so groß ist

MONTH_SCHEMA: dict[str, pl.DataType] = {
    "monat": pl.Date(),
    "wahljahr": pl.Int32(),
    "gremium_art": pl.String(),
    "urheber_art": pl.String(),
    "instrument": pl.String(),
    "dokumente": pl.Int64(),
    "mit_text": pl.Int64(),
    "haushaltsantraege": pl.Int64(),
}
MONTH_KEY = ("monat", "gremium_art", "urheber_art", "instrument")
BUDGET_SCHEMA: dict[str, pl.DataType] = {
    "wahljahr": pl.Int32(),
    "monat_kalender": pl.Int8(),
    "haushaltsantraege": pl.Int64(),
    "im_monat": pl.Int64(),
}
HYPOTHESES_EXTRA: dict[str, pl.DataType] = {
    "rolle": pl.String(),  # Haupttest, Sensitivität, explorativ
    "mass": pl.String(),
    "test": pl.String(),
    "statistik": pl.Float64(),  # t (H17.1), δ (H17.2), JT (H17.3)
    "effekt": pl.Float64(),
    "effekt_unten": pl.Float64(),  # 90 %, nur H17.1
    "effekt_oben": pl.Float64(),
    "einheit": pl.String(),  # relativ: exp(δ) − 1; anteil: Differenz zweier Anteile
    "p_randomisierung": pl.Float64(),  # nur H17.1: welches Jahr je Periode das Vorwahljahr ist
    "zuordnungen": pl.Int64(),
    "anteile": pl.List(pl.Float64()),  # nur H17.3: der gepoolte Anteil je Periode in Folge
    "lexikon": pl.String(),
    "daten_bis": pl.Date(),
}


# --- Wahljahr -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CycleRules:
    """Die Regeln aus ``[cycles]``; alle Muster auf kleingeschriebene Art und Titel."""

    start_month: int = 9
    elections: tuple[date, ...] = ()
    budget_pattern: str = r"haushalts(begleit)?-?antrag"
    budget_minimum: int = 5
    instrument_types: tuple[tuple[str, str], ...] = ()  # (Präfix, Instrument), längstes zuerst
    instrument_titles: tuple[tuple[str, str], ...] = ()  # (Muster, Instrument), erstes gewinnt
    head_chars: int = 2000

    @classmethod
    def of(
        cls,
        *,
        start_month: int,
        elections: Iterable[date],
        budget_pattern: str,
        budget_minimum: int,
        instrument_types: Mapping[str, str],
        instrument_titles: Iterable[tuple[str, str]],
        head_chars: int,
    ) -> CycleRules:
        return cls(
            start_month=start_month,
            elections=tuple(sorted(elections)),
            budget_pattern=budget_pattern,
            budget_minimum=budget_minimum,
            instrument_types=tuple(
                sorted(instrument_types.items(), key=lambda kv: (-len(kv[0]), kv[0]))
            ),
            instrument_titles=tuple(instrument_titles),
            head_chars=head_chars,
        )


def election_year(day: date, start_month: int) -> int:
    """Das Wahljahr eines Tages: das Jahr, in dem es begann."""
    return day.year - (day.month < start_month)


def _year_start(year: int, start_month: int) -> date:
    return date(year, start_month, 1)


def _year_last_day(year: int, start_month: int) -> date:
    return date(year + 1, start_month, 1) - timedelta(days=1)


def _wahljahr_order(start_month: int) -> tuple[int, ...]:
    """Die Kalendermonate in der Folge des Wahljahrs, etwa 9, 10, …, 12, 1, …, 8."""
    return tuple((start_month - 1 + i) % 12 + 1 for i in range(12))


@deal.pre(
    lambda first, last, start_month: 1 <= start_month <= 12,
    message="start_month ist ein Kalendermonat",
)
@deal.ensure(
    lambda first, last, start_month, result: (
        list(result) == sorted(set(result))
        and all(
            date(first.year, first.month, 1) <= _year_start(w, start_month)
            and _year_last_day(w, start_month) <= last
            for w in result
        )
    ),
    message="aufsteigend, und jedes Wahljahr liegt in der Periode (der erste Monat darf angeschnitten sein)",
)
def complete_years(first: date, last: date, start_month: int) -> tuple[int, ...]:
    """Die vollständigen Wahljahre einer Periode von ``first`` bis ``last`` (beide einschließlich).

    Ein Wahljahr ist vollständig, wenn es spätestens im Monat von ``first`` beginnt und
    spätestens an ``last`` endet: nur sein erster Monat darf um die Tage vor dem Beginn der Periode
    gekürzt sein (§ 8.0, „angeschnittene Monate"; die Jahreskonstante nimmt das mit).
    """
    if last < first:
        return ()
    month_of_first = date(first.year, first.month, 1)
    candidates = range(election_year(first, start_month), election_year(last, start_month) + 1)
    return tuple(
        w
        for w in candidates
        if month_of_first <= _year_start(w, start_month) and _year_last_day(w, start_month) <= last
    )


def pre_election_years(years: Iterable[int], rules: CycleRules) -> frozenset[int]:
    """Die Vorwahljahre unter ``years``: je Wahl das letzte Wahljahr, das vor dem Wahltag endet."""
    available = sorted(set(years))
    found: set[int] = set()
    for day in rules.elections:
        before = [w for w in available if _year_last_day(w, rules.start_month) < day]
        if before and election_year(day, rules.start_month) - 1 == before[-1]:
            found.add(before[-1])
    return frozenset(found)


# --- Monate je Periode ----------------------------------------------------------------------------


def _instrument(rules: CycleRules) -> pl.Expr:
    kind = pl.col("paper_type").fill_null("").str.to_lowercase()
    title = pl.col("name").fill_null("").str.to_lowercase()
    conditions = [(kind.str.starts_with(p), i) for p, i in rules.instrument_types] + [
        (title.str.contains(p), i) for p, i in rules.instrument_titles
    ]
    if not conditions:
        return pl.lit(OTHER)
    (first, value), *rest = conditions
    chain = pl.when(first).then(pl.lit(value))
    for condition, value in rest:
        chain = chain.when(condition).then(pl.lit(value))  # type: ignore[assignment]
    return chain.otherwise(pl.lit(OTHER))


def _budget_motion(rules: CycleRules) -> pl.Expr:
    return pl.col("paper_type").fill_null("").str.to_lowercase().str.contains(
        rules.budget_pattern
    ) | pl.col("name").fill_null("").str.to_lowercase().str.contains(rules.budget_pattern)


def _wahljahr_of(column: str, rules: CycleRules, years: Sequence[int]) -> pl.Expr:
    year = (
        pl.col(column).dt.year() - (pl.col(column).dt.month() < rules.start_month).cast(pl.Int32)
    ).cast(pl.Int32)
    return pl.when(year.is_in(list(years))).then(year).otherwise(None).cast(pl.Int32)


def _month_table_is_sound(
    corpus: pl.DataFrame,
    originators: pl.DataFrame,
    bodies: pl.DataFrame,
    rules: CycleRules,
    years: Sequence[int],
    result: pl.DataFrame | None = None,
) -> bool:
    if result is None or result.schema != pl.Schema(MONTH_SCHEMA):
        return False
    sums = result.select(pl.col("dokumente", "mit_text", "haushaltsantraege").sum()).row(0)
    dated = result.filter(pl.col("monat").is_not_null())
    gapless = all(
        group.height == dated.get_column("monat").n_unique()
        for _, group in dated.group_by(list(MONTH_KEY[1:]))
    )
    in_years = dated.filter(pl.col("wahljahr").is_not_null()).get_column("wahljahr")
    return (
        sums[0] == corpus.height
        and sums[1] <= sums[0]
        and bool((result.get_column("haushaltsantraege") <= result.get_column("dokumente")).all())
        and set(in_years.to_list()) <= set(years)
        and gapless
        and result.equals(result.sort(list(MONTH_KEY), nulls_last=True, maintain_order=True))
    )


@deal.pre(
    lambda corpus, originators, bodies, rules, years: (
        set(corpus.columns) >= {"id", "date", "paper_type", "name", "text"}
        and set(originators.columns) >= {"id", "urheber_art"}
        and set(bodies.columns) >= {"id", "gremium_art"}
    ),
    message="Korpus mit id, date, paper_type, name, text; Urheber und Gremien je id",
)
@deal.ensure(
    _month_table_is_sound,
    message="summiert zur Zahl der Dokumente, Haushaltsanträge <= Dokumente, jede Kombination in "
    "jedem Monat, Wahljahr nur in vollständigen Wahljahren, sortiert",
)
def month_table(
    corpus: pl.DataFrame,
    originators: pl.DataFrame,
    bodies: pl.DataFrame,
    rules: CycleRules,
    years: Sequence[int],
) -> pl.DataFrame:
    """``zeit_monate``: Dokumente je Monat, Gremienart, Urheberklasse und Instrument.

    Lückenlos: jede Kombination aus Gremienart, Urheberklasse und Instrument, die in der Periode
    vorkommt, steht in jedem Monat vom ersten bis zum letzten (mit 0, wo nichts kam); Dokumente ohne
    Datum stehen in Zeilen ohne Monat am Ende. ``wahljahr`` ist leer außerhalb der vollständigen
    Wahljahre ``years``. ``haushaltsantraege`` zählt Dokumente, deren Art oder Titel dem Muster
    folgt (§ 8.2), ``instrument`` ist die vorab festgelegte Regel von S1.5.
    """
    frame = (
        corpus.select("id", "date", "paper_type", "name", "text")
        .join(originators.select("id", "urheber_art"), on="id", how="left")
        .join(bodies.select("id", "gremium_art"), on="id", how="left")
        .sort("id")
        .select(
            pl.col("date").dt.truncate("1mo").alias("monat"),
            pl.col("gremium_art"),
            pl.col("urheber_art"),
            _instrument(rules).alias("instrument"),
            (pl.col("text").fill_null("") != "").alias("_text"),
            _budget_motion(rules).alias("_haushalt"),
        )
    )
    counts = frame.group_by(list(MONTH_KEY)).agg(
        pl.len().cast(pl.Int64).alias("dokumente"),
        pl.col("_text").sum().cast(pl.Int64).alias("mit_text"),
        pl.col("_haushalt").sum().cast(pl.Int64).alias("haushaltsantraege"),
    )
    dated = counts.filter(pl.col("monat").is_not_null())
    undated = counts.filter(pl.col("monat").is_null())
    if dated.height:
        months = pl.date_range(
            dated.get_column("monat").min(),  # type: ignore[arg-type]
            dated.get_column("monat").max(),  # type: ignore[arg-type]
            interval="1mo",
            eager=True,
        ).alias("monat")
        keys = dated.select(list(MONTH_KEY[1:])).unique()
        dated = (
            pl.DataFrame([months])
            .join(keys, how="cross")
            .join(dated, on=list(MONTH_KEY), how="left", nulls_equal=True)
            .with_columns(pl.col("dokumente", "mit_text", "haushaltsantraege").fill_null(0))
        )
    return (
        pl.concat([dated, undated], how="vertical_relaxed")
        .with_columns(_wahljahr_of("monat", rules, years).alias("wahljahr"))
        .select(list(MONTH_SCHEMA))
        .cast(MONTH_SCHEMA)  # type: ignore[arg-type]
        .sort(list(MONTH_KEY), nulls_last=True, maintain_order=True)
    )


def _budget_is_sound(
    months: pl.DataFrame, rules: CycleRules, result: pl.DataFrame | None = None
) -> bool:
    if result is None or result.schema != pl.Schema(BUDGET_SCHEMA):
        return False
    rows = result.rows(named=True)
    return [r["wahljahr"] for r in rows] == sorted({r["wahljahr"] for r in rows}) and all(
        (r["monat_kalender"] is None) == (r["haushaltsantraege"] < rules.budget_minimum)
        and (r["monat_kalender"] is None) == (r["im_monat"] is None)
        and (r["im_monat"] is None or 0 < r["im_monat"] <= r["haushaltsantraege"])
        for r in rows
    )


@deal.ensure(
    _budget_is_sound,
    message="je vollständigem Wahljahr eine Zeile, aufsteigend; ein Haushaltsmonat genau ab dem "
    "Minimum, mit 0 < im_monat <= haushaltsantraege",
)
def budget_months(months: pl.DataFrame, rules: CycleRules) -> pl.DataFrame:
    """``haushaltsmonate``: je vollständigem Wahljahr der Monat mit den meisten Haushaltsanträgen.

    Bei Gleichstand gewinnt der frühere Monat im Wahljahr; unter ``budget_minimum`` Haushaltsanträgen
    im Wahljahr gibt es keinen (§ 8.2). ``haushaltsantraege`` zählt das ganze Wahljahr, ``im_monat``
    den Haushaltsmonat.
    """
    order = _wahljahr_order(rules.start_month)
    in_years = months.filter(pl.col("wahljahr").is_not_null())
    per_month = (
        in_years.group_by("wahljahr", pl.col("monat").dt.month().alias("kal"))
        .agg(pl.col("haushaltsantraege").sum())
        .sort("wahljahr", "kal")
    )
    rows = []
    for year in sorted(set(in_years.get_column("wahljahr").to_list())):
        cells = [
            (int(r["haushaltsantraege"]), int(r["kal"]))
            for r in per_month.filter(pl.col("wahljahr") == year).iter_rows(named=True)
        ]
        total = sum(n for n, _ in cells)
        best = max(cells, key=lambda c: (c[0], -order.index(c[1]))) if cells else (0, 0)
        found = total >= rules.budget_minimum and best[0] > 0
        rows.append(
            {
                "wahljahr": year,
                "monat_kalender": best[1] if found else None,
                "haushaltsantraege": total,
                "im_monat": best[0] if found else None,
            }
        )
    return pl.DataFrame(rows, schema=BUDGET_SCHEMA)


# --- Exakte Tests ---------------------------------------------------------------------------------


def multiset_permutations(labels: Sequence[int]) -> np.ndarray:
    """Alle verschiedenen Anordnungen einer Multimenge, eine je Zeile (n! / ∏ k! Zeilen).

    Je Wert die Stellen, die er besetzt, als Kombination der noch freien; so entsteht jede
    Anordnung genau einmal. Rekursiv über die verschiedenen Werte, darum ohne ``deal.pure``.
    """
    counts = Counter(labels)
    keys = sorted(counts)
    current = [0] * len(labels)
    found: list[tuple[int, ...]] = []

    def place(index: int, free: tuple[int, ...]) -> None:
        if index == len(keys):
            found.append(tuple(current))
            return
        key = keys[index]
        for chosen in combinations(free, counts[key]):
            for position in chosen:
                current[position] = key
            taken = set(chosen)
            place(index + 1, tuple(f for f in free if f not in taken))

    place(0, tuple(range(len(labels))))
    return np.array(found, dtype=np.int64).reshape(len(found), len(labels))


@dataclass(frozen=True)
class Randomization:
    """Ein exakter Test über alle Zuordnungen."""

    statistic: float  # δ (H17.2) oder JT (H17.3)
    p: float  # einseitig: Anteil der Zuordnungen mit Statistik mindestens so groß
    p_two_sided: float | None  # H17.2: Anteil mindestens so groß im Betrag; JT: keiner
    count: int  # Zahl der Zuordnungen


def _double_center(table: np.ndarray) -> np.ndarray:
    return (
        table - table.mean(axis=1, keepdims=True) - table.mean(axis=0, keepdims=True) + table.mean()
    )


def _budget_args_ok(table: np.ndarray, assignment: Sequence[int]) -> bool:
    return (
        table.ndim == 2
        and table.shape[0] == len(assignment) >= 2
        and len(set(assignment)) >= 2
        and all(0 <= a < table.shape[1] for a in assignment)
        and bool((table >= 0).all())
    )


def _p_in_range(table: np.ndarray, assignment: Sequence[int], result: Randomization) -> bool:
    return (
        1 / result.count - _TIE <= result.p <= 1.0
        and result.p_two_sided is not None
        and 1 / result.count - _TIE <= result.p_two_sided <= 1.0
    )


@deal.pre(
    _budget_args_ok,
    message="Tabelle Wahljahre × Monate, nicht negativ; je Wahljahr eine Spalte, mindestens zwei verschiedene",
)
@deal.ensure(_p_in_range, message="p in [1 / Zuordnungen, 1]")
def budget_test(table: np.ndarray, assignment: Sequence[int]) -> Randomization:
    """H17.2: δ des Zwei-Wege-Modells und der Randomisierungstest über die Haushaltsmonate.

    ``table`` hat je Wahljahr eine Zeile und je Monat (in der Folge des Wahljahrs) eine Spalte,
    ``assignment`` je Wahljahr die Spalte seines Haushaltsmonats. Das Modell ist
    ln(1 + y) = α_w + β_m + δ · [m Haushaltsmonat von w] + ε; δ̂ ist der Quotient aus der doppelt
    zentrierten Tabelle und dem doppelt zentrierten Indikator (§ 8.2). Weil jede Zeile genau eine
    Eins trägt, ist der Nenner für jede Zuordnung derselbe Multimenge gleich und der Zähler die
    Summe der zentrierten Zellen der Zuordnung; das spart die Matrix je Zuordnung, ohne an δ̂ etwas
    zu ändern. Gezählt wird über alle verschiedenen Anordnungen der beobachteten Haushaltsmonate.
    """
    centered = _double_center(np.log1p(np.asarray(table, dtype=np.float64)))
    rows, columns = centered.shape
    observed = np.asarray(assignment, dtype=np.int64)
    counts = np.bincount(observed, minlength=columns).astype(np.float64)
    share = counts / rows
    denominator = float((counts * (1 - share) ** 2 + (rows - counts) * share**2).sum())
    every = multiset_permutations([int(a) for a in assignment])
    deltas = centered[np.arange(rows)[None, :], every].sum(axis=1) / denominator
    delta = float(centered[np.arange(rows), observed].sum() / denominator)
    return Randomization(
        statistic=delta,
        p=float((deltas >= delta - _TIE).mean()),
        p_two_sided=float((np.abs(deltas) >= abs(delta) - _TIE).mean()),
        count=len(deltas),
    )


def _jt_args_ok(values: Sequence[float], sizes: Sequence[int]) -> bool:
    return (
        len(sizes) >= 2
        and all(s >= 1 for s in sizes)
        and sum(sizes) == len(values)
        and all(math.isfinite(v) for v in values)
    )


def _jt_p_in_range(values: Sequence[float], sizes: Sequence[int], result: Randomization) -> bool:
    return 1 / result.count - _TIE <= result.p <= 1.0 and result.p_two_sided is None


@deal.pre(_jt_args_ok, message="mindestens zwei nicht leere Gruppen, endliche Werte")
@deal.ensure(_jt_p_in_range, message="p in [1 / Zuordnungen, 1]")
def jonckheere(values: Sequence[float], sizes: Sequence[int]) -> Randomization:
    """Jonckheere-Terpstra für eine steigende Folge der Gruppen, exakt über alle Zuordnungen.

    ``values`` stehen nach Gruppen geordnet, ``sizes`` nennt, wie viele zu jeder Gruppe gehören.
    JT zählt über alle Paare aus einer früheren und einer späteren Gruppe, wie oft der spätere Wert
    größer ist (Gleichstand halb). p ist der Anteil der Zuordnungen der Werte zu Gruppen dieser
    Größen mit JT mindestens so groß (§ 8.3).
    """
    v = np.asarray(values, dtype=np.float64)
    pairs = (v[:, None] < v[None, :]) * 1.0 + (v[:, None] == v[None, :]) * 0.5
    labels = np.repeat(np.arange(len(sizes)), sizes)
    every = multiset_permutations([int(label) for label in labels])
    later = every[:, :, None] < every[:, None, :]
    jts = (later * pairs[None, :, :]).sum(axis=(1, 2))
    jt = float(((labels[:, None] < labels[None, :]) * pairs).sum())
    return Randomization(
        statistic=jt, p=float((jts >= jt - _TIE).mean()), p_two_sided=None, count=len(jts)
    )


@dataclass(frozen=True)
class Unit:
    """Ein Wahljahr im Modell von H17.1."""

    period: str
    year: int
    value: float
    pre_election: bool
    first: bool  # Anlaufjahr: das erste vollständige Wahljahr der Periode


@dataclass(frozen=True)
class PreElection:
    delta: float
    se: float
    t: float
    df: int
    p: float  # t einseitig, δ > 0
    lo: float  # 90 %, einseitig 95 %
    hi: float
    p_random: float  # welches Jahr je Periode das Vorwahljahr ist
    count: int
    n: int


def _usable(units: Sequence[Unit], with_first: bool) -> list[Unit]:
    return [u for u in units if with_first or not u.first]


def _pre_election_args_ok(
    units: Sequence[Unit], *, log: bool = True, with_first: bool = False
) -> bool:
    used = _usable(units, with_first)
    periods = {u.period for u in used}
    return (
        bool(periods)
        and all(
            sum(u.pre_election for u in used if u.period == p) == 1
            and sum(not u.pre_election for u in used if u.period == p) >= 1
            for p in periods
        )
        and (not log or all(u.value > 0 for u in used))
        and len(used) > len(periods) + 1
    )


def _fit(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    residuals = y - x @ beta
    df = len(y) - x.shape[1]
    variance = float(residuals @ residuals) / df
    covariance = variance * np.linalg.inv(x.T @ x)
    return beta, np.sqrt(np.diag(covariance)), df


@deal.pre(
    _pre_election_args_ok,
    message="je Periode genau ein Vorwahljahr und mindestens ein Vergleichsjahr, Werte > 0 für ln, "
    "mehr Jahre als Parameter",
)
def pre_election_test(
    units: Sequence[Unit], *, log: bool = True, with_first: bool = False
) -> PreElection:
    """H17.1: OLS y = μ_Periode + δ · Vorwahljahr, t einseitig auf δ > 0 (§ 8.1).

    ``y`` ist ln des Werts (oder der Wert selbst, S1.4). Ohne ``with_first`` bleiben die Anlaufjahre
    draußen; S1.3 nimmt sie als Vergleich. Die Randomisierung setzt je Periode jedes ihrer Jahre
    einmal als Vorwahljahr und zählt, wie oft δ mindestens so groß wird; sie wird berichtet und
    entscheidet nicht (sie kann 1 / Zahl der Zuordnungen nicht unterschreiten).
    """
    used = _usable(units, with_first)
    periods = list(dict.fromkeys(u.period for u in used))
    y = np.array([math.log(u.value) if log else u.value for u in used], dtype=np.float64)
    x = np.array(
        [[1.0 if u.period == p else 0.0 for p in periods] + [float(u.pre_election)] for u in used],
        dtype=np.float64,
    )
    beta, se, df = _fit(y, x)
    delta, error = float(beta[-1]), float(se[-1])
    t = delta / error
    q = float(stats.t.ppf(0.95, df))
    candidates = [[i for i, u in enumerate(used) if u.period == p] for p in periods]
    larger = 0
    total = 0
    for chosen in product(*candidates):
        shuffled = x.copy()
        shuffled[:, -1] = 0.0
        shuffled[list(chosen), -1] = 1.0
        coefficients, *_ = np.linalg.lstsq(shuffled, y, rcond=None)
        total += 1
        larger += int(coefficients[-1] >= delta - _TIE)
    return PreElection(
        delta=delta,
        se=error,
        t=t,
        df=df,
        p=float(stats.t.sf(t, df)),
        lo=delta - q * error,
        hi=delta + q * error,
        p_random=larger / total,
        count=total,
        n=len(used),
    )


# --- Die Tabelle der Hypothesen -------------------------------------------------------------------


@dataclass(frozen=True)
class PeriodData:
    """Was ``cycle_tests`` je Periode liest; ``documents`` je Korpus-ID mit Datum, Text ja oder nein,
    Urheberklasse und den Kategorien des Lexikons (``kategorien``, ``kopf``)."""

    name: str
    months: pl.DataFrame  # zeit_monate
    budget: pl.DataFrame  # haushaltsmonate
    documents: pl.DataFrame  # id, date, mit_text, urheber_art, kategorien, kopf

    @property
    def years(self) -> tuple[int, ...]:
        found = self.months.get_column("wahljahr").drop_nulls().unique().sort()
        return tuple(int(w) for w in found)


def _year_sums(
    period: PeriodData, keep: pl.Expr, *, without_months: Sequence[int] = ()
) -> dict[int, float]:
    frame = period.months.filter(
        pl.col("wahljahr").is_not_null() & ~pl.col("monat").dt.month().is_in(list(without_months))
    )
    sums = frame.group_by("wahljahr").agg(
        pl.when(keep).then(pl.col("dokumente")).otherwise(0).sum().alias("y")
    )
    return {int(w): float(y) for w, y in sums.iter_rows()}


def _units(
    periods: Sequence[PeriodData], rules: CycleRules, values: Mapping[str, Mapping[int, float]]
) -> list[Unit]:
    units = []
    for period in periods:
        years = period.years
        treated = pre_election_years(years, rules)
        if not treated or not years:
            continue
        for year in years:
            units.append(
                Unit(
                    period.name, year, values[period.name][year], year in treated, year == years[0]
                )
            )
    return units


def _relative(row: PreElection) -> tuple[float, float, float]:
    return math.exp(row.delta) - 1, math.exp(row.lo) - 1, math.exp(row.hi) - 1


def _budget_table(
    periods: Sequence[PeriodData], rules: CycleRules, keep: pl.Expr, value: pl.Expr
) -> tuple[np.ndarray, list[int], list[int]]:
    """Die Tabelle Wahljahre mit Haushaltsmonat × Monate (Folge des Wahljahrs) und die Zuordnung."""
    order = _wahljahr_order(rules.start_month)
    budget = pl.concat([p.budget for p in periods]).filter(pl.col("monat_kalender").is_not_null())
    years = [int(w) for w in budget.get_column("wahljahr")]
    assignment = [order.index(int(m)) for m in budget.get_column("monat_kalender")]
    months = pl.concat([p.months for p in periods]).filter(pl.col("wahljahr").is_in(years))
    cells = months.group_by("wahljahr", pl.col("monat").dt.month().alias("kal")).agg(
        pl.when(keep).then(value).otherwise(0).sum().alias("y")
    )
    table = np.zeros((len(years), 12))
    for year, month, y in cells.iter_rows():
        table[years.index(int(year)), order.index(int(month))] = float(y)
    return table, years, assignment


def _shares(
    periods: Sequence[PeriodData], flag: pl.Expr, subset: pl.Expr
) -> tuple[list[float], list[int], list[float]]:
    """Je Wahljahr der Anteil mit ``flag`` unter den Dokumenten mit Text in ``subset``; die Größe
    jeder Periode in Wahljahren und ihr gepoolter Anteil."""
    values: list[float] = []
    sizes: list[int] = []
    pooled: list[float] = []
    for period in periods:
        docs = period.documents.filter(
            pl.col("mit_text") & subset & pl.col("wahljahr").is_in(list(period.years))
        )
        per_year = (
            docs.group_by("wahljahr")
            .agg(flag.sum().alias("a"), pl.len().alias("n"))
            .sort("wahljahr")
        )
        rows = [(int(a), int(n)) for _, a, n in per_year.iter_rows()]
        values += [a / n for a, n in rows]
        sizes.append(len(rows))
        pooled.append(sum(a for a, _ in rows) / max(1, sum(n for _, n in rows)))
    return values, sizes, pooled


def _with_years(periods: Sequence[PeriodData], rules: CycleRules) -> list[PeriodData]:
    out = []
    for period in periods:
        documents = period.documents.with_columns(
            _wahljahr_of("date", rules, period.years).alias("wahljahr")
        )
        out.append(PeriodData(period.name, period.months, period.budget, documents))
    return out


def _periods_are_ordered(
    periods: Sequence[PeriodData], rules: CycleRules, lexicon: Lexicon
) -> bool:
    years = [w for p in periods for w in p.years]
    return len(periods) >= 2 and years == sorted(set(years))


@deal.pre(
    _periods_are_ordered,
    message="mindestens zwei Perioden, ihre vollständigen Wahljahre aufsteigend und disjunkt",
)
def cycle_hypotheses(
    periods: Sequence[PeriodData], rules: CycleRules, lexicon: Lexicon
) -> pl.DataFrame:
    """``zeit_hypothesen``: die drei Haupttests mit Holm und ihre Sensitivitäten, Folge wie § 8.

    Die Perioden stehen in zeitlicher Folge. H17.1 nimmt die Perioden, die ein Vorwahljahr haben
    (abgeschlossene); H17.2 alle Wahljahre mit Haushaltsmonat; H17.3 alle Perioden als geordnete
    Gruppen. H17.3 ist ``vorläufig``, solange ``lexicon`` nicht mit Präzision >= 0,9 validiert ist.
    """
    periods = _with_years(periods, rules)
    structure = set(lexicon.of_kind(STRUCTURE))
    events = set(lexicon.of_kind(EVENT))
    names = {c.id: c.name for c in lexicon.categories}
    fraction = pl.col("urheber_art") == FRACTION
    political = pl.col("urheber_art").is_in(list(POLITICAL))
    days: list[date] = [
        d for p in periods for d in p.documents.get_column("date").drop_nulls().to_list()
    ]
    last_day = max(days) if days else None
    common = {"lexikon": lexicon.label, "daten_bis": last_day}
    rows: list[dict[str, object]] = []

    # H17.1 Wahlzyklus und seine Sensitivitäten (§ 8.1)
    def h171(key: str, role: str, measure: str, keep: pl.Expr, **options: object) -> None:
        log = bool(options.get("log", True))
        without = options.get("without_months", ())
        values = {
            p.name: _year_sums(p, keep, without_months=without)  # type: ignore[arg-type]
            for p in periods
        }
        if options.get("share"):
            everything = {p.name: _year_sums(p, pl.lit(True)) for p in periods}
            values = {
                n: {w: v / everything[n][w] for w, v in years.items()}
                for n, years in values.items()
            }
        result = pre_election_test(
            _units(periods, rules, values), log=log, with_first=bool(options.get("with_first"))
        )
        effect = _relative(result) if log else (result.delta, result.lo, result.hi)
        rows.append(
            {
                "hypothese": key,
                "rolle": role,
                "mass": measure,
                "test": "OLS mit Konstante je Periode, t einseitig (δ > 0); Randomisierung "
                "des Vorwahljahrs berichtet",
                "statistik": result.t,
                "effekt": effect[0],
                "effekt_unten": effect[1],
                "effekt_oben": effect[2],
                "einheit": "relativ" if log else "anteil",
                "p": result.p,
                "p_randomisierung": result.p_random,
                "zuordnungen": result.count,
                "n": result.n,
                "festgelegt": PREREGISTERED,
            }
        )

    h171("H17.1", "Haupttest", "ln der Fraktionsdokumente je Wahljahr, ohne Anlaufjahr", fraction)
    h171("H17.1/S1.1", "Sensitivität", "ln der politischen Dokumente je Wahljahr", political)
    h171(
        "H17.1/S1.2",
        "Sensitivität",
        "ln der Fraktionsdokumente je Wahljahr ohne März bis Juni",
        fraction,
        without_months=SPRING,
    )
    h171(
        "H17.1/S1.3",
        "Sensitivität",
        "ln der Fraktionsdokumente je Wahljahr, Anlaufjahre als Vergleich",
        fraction,
        with_first=True,
    )
    h171(
        "H17.1/S1.4",
        "Sensitivität",
        "Anteil der Fraktionsdokumente an allen Dokumenten je Wahljahr",
        fraction,
        log=False,
        share=True,
    )
    for instrument in ("anfrage", "antrag"):
        h171(
            f"H17.1/S1.5/{instrument}",
            "Sensitivität",
            f"ln der Fraktionsdokumente je Wahljahr, nur Instrument {instrument}",
            fraction & (pl.col("instrument") == instrument),
        )

    # H17.2 Haushaltsrhythmus (§ 8.2)
    def h172(key: str, role: str, measure: str, keep: pl.Expr, value: pl.Expr, two: bool) -> None:
        table, years, assignment = _budget_table(periods, rules, keep, value)
        result = budget_test(table, assignment)
        rows.append(
            {
                "hypothese": key,
                "rolle": role,
                "mass": measure,
                "test": "Zwei-Wege-Modell, Randomisierung über alle Zuordnungen der "
                + ("Haushaltsmonate, zweiseitig" if two else "Haushaltsmonate, einseitig"),
                "statistik": result.statistic,
                "effekt": math.exp(result.statistic) - 1,
                "einheit": "relativ",
                "p": result.p_two_sided if two else result.p,
                "zuordnungen": result.count,
                "n": len(years),
                "festgelegt": PREREGISTERED,
            }
        )

    documents = pl.col("dokumente")
    h172(
        "H17.2",
        "Haupttest",
        "ln(1 + Fraktionsdokumente) je Wahljahr und Kalendermonat, Haushaltsmonat gegen denselben "
        "Kalendermonat ohne Haushalt",
        fraction,
        documents,
        two=False,
    )
    h172(
        "H17.2/S2.1",
        "Sensitivität",
        "dasselbe ohne die Haushaltsanträge",
        fraction,
        documents - pl.col("haushaltsantraege"),
        two=True,
    )
    h172(
        "H17.2/S2.2",
        "Sensitivität",
        "dasselbe mit allen Dokumenten",
        pl.lit(True),
        documents,
        two=False,
    )

    # H17.3 Bundespolitisches Vokabular (§ 8.3)
    def h173(key: str, role: str, measure: str, flag: pl.Expr, subset: pl.Expr) -> None:
        values, sizes, pooled = _shares(periods, flag, subset)
        result = jonckheere(values, sizes)
        rows.append(
            {
                "hypothese": key,
                "rolle": role,
                "mass": measure,
                "test": "Jonckheere-Terpstra exakt über alle Zuordnungen der Wahljahre zu den "
                "Perioden, einseitig steigend",
                "statistik": result.statistic,
                "effekt": pooled[-1] - pooled[0],
                "einheit": "anteil",
                "p": result.p,
                "zuordnungen": result.count,
                "anteile": pooled,
                "n": len(values),
                "festgelegt": PREREGISTERED,
            }
        )

    def any_of(column: str, wanted: Iterable[str]) -> pl.Expr:
        return pl.col(column).list.set_intersection(pl.lit(sorted(wanted))).list.len() > 0

    everyone = pl.lit(True)
    h173(
        "H17.3",
        "Haupttest",
        "Anteil der Dokumente mit Text und Treffer einer Strukturkategorie je Wahljahr, Titel "
        "und Text",
        any_of("kategorien", structure),
        everyone,
    )
    h173(
        "H17.3/S3.1",
        "Sensitivität",
        f"dasselbe in Titel und den ersten {rules.head_chars} Zeichen",
        any_of("kopf", structure),
        everyone,
    )
    h173(
        "H17.3/S3.2",
        "Sensitivität",
        "dasselbe mit allen Kategorien, auch den Ereignissen",
        any_of("kategorien", structure | events),
        everyone,
    )
    for category in lexicon.ids:
        h173(
            f"H17.3/S3.3/{category}",
            "explorativ",
            f"Anteil mit Treffer der Kategorie {names[category]}",
            any_of("kategorien", [category]),
            everyone,
        )
    h173(
        "H17.3/S3.4/politisch",
        "Sensitivität",
        "Strukturkategorien unter den politischen Dokumenten",
        any_of("kategorien", structure),
        political,
    )
    h173(
        "H17.3/S3.4/verwaltung",
        "Sensitivität",
        "Strukturkategorien unter den Dokumenten der Verwaltung",
        any_of("kategorien", structure),
        pl.col("urheber_art") == ADMINISTRATION,
    )

    precision = validated_precision(lexicon)
    valid = precision is not None and precision >= MIN_PRECISION
    main = {str(r["hypothese"]): float(r["p"]) for r in rows if r["rolle"] == "Haupttest"}  # type: ignore[arg-type]
    decided = family(main, valid={"H17.3": valid})
    for row in rows:
        row.update(common)
        key = str(row["hypothese"])
        if key in decided:
            row["p_holm"], row["ergebnis"] = decided[key]
    frame = hypothesis_frame(rows, HYPOTHESES_EXTRA)
    check_hypotheses(frame)
    return frame
