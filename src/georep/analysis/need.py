"""Bedarf gegen Aufmerksamkeit je Wahlbezirk: die vorab festgelegten Tests und was neben ihnen steht.

Vorhaben 22 (``docs/plans/22-bedarf.md``, § 8 und § 3.5). Je Hypothese Spearmans rho zwischen einer
Bedarfsspalte (x) und einer Aufmerksamkeitsspalte (y), p aus einem Permutationstest, ein
Perzentil-Bootstrap-Intervall für rho und Holm über alle vorab festgelegten Tests. Daneben, vorab
genannt und nicht entscheidend, die Robustheitsrechnungen; danach, **explorativ**, die Rechnung
innerhalb der Stadtbezirke (Ränge um den Mittelwert ihres Stadtbezirks bereinigt), Moran's I der
Residuen und der beiden Seiten, und weitere Paare mit dem asymptotischen p von scipy.

Die Zufallszahlen kommen aus zwei Generatoren und werden in genau der Folge des Messskripts
gezogen (``docs/plans/22-bedarf-messung.py``): ``seed`` je Hypothese erst die Permutationen, dann
die Bootstrap-Ziehungen; ``seed + 1`` erst die Rechnung innerhalb der Stadtbezirke für alle
Hypothesen, dann Moran's I je Hypothese für Residuen, x und y. Dann ergibt derselbe Lauf dieselben
Zahlen wie die Messung, und zwei Läufe schreiben dieselbe Datei. Die Permutationen werden einzeln
gezogen (``rng.permutation(n)`` zieht dasselbe wie ``rng.permutation(y)``), die Korrelationen aber
für alle zugleich berechnet; beobachteter und permutierter Wert entstehen aus derselben Formel, damit
ein gleicher Wert auch bitgleich ist.

Rein und ohne Netz; die Spalten und Parameter nennt der Aufrufer über ``NeedSettings``. ``holm``
und die Wortwahl ``bestätigt``/``nicht bestätigt`` sind eine **Übergangslösung**, bis Vorhaben 17
``analysis/hypotheses.py`` mit dem gemeinsamen Kern bringt (Synergien 2026-11, § 1); dann werden sie
von dort genommen.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import deal
import numpy as np
import numpy.typing as npt
import polars as pl
import shapely
from scipy import stats
from shapely.geometry.base import BaseGeometry

from georep.contracts import has_columns
from georep.errors import SchemaError
from georep.settings import NeedHypothesis, NeedSettings

# Die Schema-Version der Tabelle ist die des Schritts, der sie schreibt (``need``,
# ``prep.context.NEED_SCHEMA_VERSION``); eine zweite Konstante hier käme an keinem Stamp an.
DISTRICT = "wahlkreis_id"
STRATUM = "stadtbezirk"
# Der Haupttest zählt ein permutiertes rho, das dem beobachteten bis auf Fließkomma gleicht, als
# mindestens so extrem (Messskript, ``spearman_test``); die explorativen Rechnungen tun das nicht.
TIE = 1e-12
CONFIRMED = "bestätigt"
NOT_CONFIRMED = "nicht bestätigt"

# Rechnungen je Zeile, in der Folge der Datei.
MAIN = "haupttest"
ROBUST = "robustheit"
WITHIN = "innerhalb"
MORAN_RESIDUALS = "moran_residuen"
MORAN_NEED = "moran_bedarf"
MORAN_ATTENTION = "moran_aufmerksamkeit"
PAIR = "paar"

# Der Kern der Hypothesentabellen (Synergien 2026-11, § 1) vorn, dann die Spalten von 22.
HYPOTHESES_SCHEMA: dict[str, pl.DataType] = {
    "hypothese": pl.String(),
    "p": pl.Float64(),
    "p_holm": pl.Float64(),
    "ergebnis": pl.String(),
    "n": pl.Int64(),
    "festgelegt": pl.String(),
    "rechnung": pl.String(),
    "explorativ": pl.Boolean(),
    "bedarf": pl.String(),
    "aufmerksamkeit": pl.String(),
    "kontrolle": pl.String(),
    "ohne": pl.List(pl.Int64()),
    "mass": pl.String(),
    "wert": pl.Float64(),
    "ci_lo": pl.Float64(),
    "ci_hi": pl.Float64(),
    "test": pl.String(),
    "alternative": pl.String(),
    "permutationen": pl.Int64(),
    "seed": pl.Int64(),
}

Floats = npt.NDArray[np.float64]


def _row_correlations(a: Floats, rows: Floats) -> Floats:
    """Pearsons r zwischen ``a`` und jeder Zeile von ``rows``; NaN ohne Streuung."""
    centred = a - a.mean()
    others = rows - rows.mean(axis=1, keepdims=True)
    denominator = np.sqrt((centred @ centred) * (others * others).sum(axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.asarray((others @ centred) / denominator, dtype=np.float64)


def _pairwise_correlations(rows_a: Floats, rows_b: Floats) -> Floats:
    """Pearsons r je Zeilenpaar zweier gleich großer Matrizen; NaN ohne Streuung."""
    a = rows_a - rows_a.mean(axis=1, keepdims=True)
    b = rows_b - rows_b.mean(axis=1, keepdims=True)
    denominator = np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.asarray((a * b).sum(axis=1) / denominator, dtype=np.float64)


def _permutations(n: int, count: int, rng: np.random.Generator) -> npt.NDArray[np.intp]:
    """``count`` Permutationen von ``range(n)``, einzeln gezogen wie im Messskript."""
    if count == 0:
        return np.zeros((0, n), dtype=np.intp)
    return np.stack([rng.permutation(n) for _ in range(count)])


def ranks(values: Floats) -> Floats:
    """Ränge mit Mittelrang bei Gleichstand (``scipy.stats.rankdata``)."""
    return np.asarray(stats.rankdata(values), dtype=np.float64)


def spearman(x: Floats, y: Floats) -> float | None:
    """Spearmans rho; ``None`` unter drei Werten oder ohne Streuung in einer Seite."""
    if len(x) < 3:
        return None
    rx, ry = ranks(x), ranks(y)
    if rx.std() == 0 or ry.std() == 0:
        return None
    value = float(np.corrcoef(rx, ry)[0, 1])
    return value if math.isfinite(value) else None


@deal.pre(
    lambda x, y, *, alternative, permutations, rng: (
        len(x) == len(y) and alternative in ("greater", "two-sided") and permutations > 0
    ),
    message="gleich lange Seiten, bekannte Alternative, mindestens eine Permutation",
)
@deal.post(
    lambda result: result[1] is None or 0.0 < result[1] <= 1.0,
    message="p in (0, 1] oder unbestimmt",
)
def permutation_test(
    x: Floats, y: Floats, *, alternative: str, permutations: int, rng: np.random.Generator
) -> tuple[float | None, float | None]:
    """Spearmans rho und p aus ``permutations`` Permutationen von y.

    ``greater`` zählt die permutierten rho ab dem beobachteten (einseitig, rho > 0),
    ``two-sided`` die ab seinem Betrag. p ist ``(1 + Treffer) / (Permutationen + 1)``, nie 0. Ohne
    rho (zu wenige Werte, keine Streuung) zieht die Funktion nichts und gibt ``(None, None)``.
    """
    rho = spearman(x, y)
    if rho is None:
        return None, None
    rx, ry = ranks(x), ranks(y)
    shuffled = _row_correlations(rx, ry[_permutations(len(y), permutations, rng)])
    if alternative == "greater":
        hits = int((shuffled >= rho - TIE).sum())
    else:
        hits = int((np.abs(shuffled) >= abs(rho) - TIE).sum())
    return rho, (1 + hits) / (permutations + 1)


def _ordered_or_open(result: tuple[float | None, float | None]) -> bool:
    low, high = result
    if low is None or high is None:
        return low is None and high is None
    return low <= high


@deal.pre(lambda x, y, *, draws, rng: len(x) == len(y) and draws > 0)
@deal.post(_ordered_or_open, message="beide Grenzen oder keine, untere zuerst")
def bootstrap_interval(
    x: Floats, y: Floats, *, draws: int, rng: np.random.Generator
) -> tuple[float | None, float | None]:
    """95-%-Perzentil-Intervall für rho aus ``draws`` Ziehungen mit Zurücklegen.

    Eine Ziehung ohne Streuung in einer Seite zählt nicht, verbraucht aber ihre Zufallszahlen
    (Messskript). Ohne eine gültige Ziehung ist das Intervall unbestimmt.
    """
    n = len(x)
    if n < 3:
        return None, None
    picks = np.stack([rng.integers(0, n, n) for _ in range(draws)])
    a = np.asarray(stats.rankdata(x[picks], axis=1), dtype=np.float64)
    b = np.asarray(stats.rankdata(y[picks], axis=1), dtype=np.float64)
    valid = (a.std(axis=1) > 0) & (b.std(axis=1) > 0)
    if not valid.any():
        return None, None
    values = _pairwise_correlations(a[valid], b[valid])
    low, high = np.percentile(values, [2.5, 97.5])
    return float(low), float(high)


def _demeaned(values: Floats, strata: npt.NDArray[np.int64]) -> Floats:
    """Werte minus den Mittelwert ihrer Schicht (die Residuen einer Regression auf Schichtdummys)."""
    out = values.copy()
    for stratum in np.unique(strata):
        mask = strata == stratum
        out[mask] = values[mask] - values[mask].mean()
    return out


def within_strata(
    x: Floats,
    y: Floats,
    strata: npt.NDArray[np.int64],
    *,
    permutations: int,
    rng: np.random.Generator,
) -> tuple[float | None, float | None]:
    """Rangkorrelation innerhalb der Schichten und ihr zweiseitiges p aus Permutationen der Reste.

    Die Ränge von x und y werden je Schicht um ihren Mittelwert bereinigt und dann korreliert: das
    fragt, ob der Zusammenhang auch zwischen Nachbarn derselben Bezirksvertretung gilt, nicht nur
    zwischen den Stadtbezirken (Messdokument § 3.5). Explorativ.
    """
    if len(x) < 3:
        return None, None
    ex, ey = _demeaned(ranks(x), strata), _demeaned(ranks(y), strata)
    observed = float(_row_correlations(ex, ey[np.newaxis, :])[0])
    if not math.isfinite(observed):
        return None, None
    shuffled = _row_correlations(ex, ey[_permutations(len(ey), permutations, rng)])
    hits = int((np.abs(shuffled) >= abs(observed)).sum())
    return observed, (1 + hits) / (permutations + 1)


def _moran_values(rows: Floats, weights: Floats) -> Floats:
    n = rows.shape[1]
    total = weights.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.asarray(
            n * ((rows @ weights) * rows).sum(axis=1) / (total * (rows * rows).sum(axis=1)),
            dtype=np.float64,
        )


@deal.pre(
    lambda values, weights, *, permutations, rng: (
        weights.shape == (len(values), len(values)) and bool((weights >= 0).all())
    ),
    message="eine quadratische, nicht negative Nachbarschaft passend zu den Werten",
)
def morans_i(
    values: Floats, weights: Floats, *, permutations: int, rng: np.random.Generator
) -> tuple[float | None, float | None]:
    """Moran's I mit zeilennormierten Gewichten und p aus Permutationen (einseitig, I darüber).

    Eine Zeile ohne Nachbarn bleibt null. Ohne Streuung oder ohne eine einzige Nachbarschaft ist I
    unbestimmt, und es wird nichts gezogen.
    """
    sums = weights.sum(axis=1, keepdims=True)
    normed = np.divide(weights, sums, out=np.zeros_like(weights), where=sums > 0)
    centred = values - values.mean()
    if normed.sum() == 0 or not centred @ centred > 0:
        return None, None
    observed = float(_moran_values(centred[np.newaxis, :], normed)[0])
    if not math.isfinite(observed):
        return None, None
    shuffled = _moran_values(centred[_permutations(len(centred), permutations, rng)], normed)
    return observed, (1 + int((shuffled >= observed).sum())) / (permutations + 1)


def partial_spearman(x: Floats, y: Floats, z: Floats) -> float | None:
    """Partielle Rangkorrelation von x und y bei festem z: Residuen der Ränge, dann korreliert."""
    if len(x) < 4:
        return None
    rx, ry, rz = ranks(x), ranks(y), ranks(z)
    design = np.column_stack([np.ones_like(rz), rz])
    ex = rx - design @ np.linalg.lstsq(design, rx, rcond=None)[0]
    ey = ry - design @ np.linalg.lstsq(design, ry, rcond=None)[0]
    if ex.std() == 0 or ey.std() == 0:
        return None
    value = float(np.corrcoef(ex, ey)[0, 1])
    return value if math.isfinite(value) else None


def rank_residuals(x: Floats, y: Floats) -> Floats:
    """Residuen der Rangregression y ~ x (für Moran's I nach dem Test)."""
    rx, ry = ranks(x), ranks(y)
    design = np.column_stack([np.ones_like(rx), rx])
    return np.asarray(ry - design @ np.linalg.lstsq(design, ry, rcond=None)[0], dtype=np.float64)


# --- Übergang bis Vorhaben 17 (analysis/hypotheses.py): Holm und die Wortwahl ----------------


@deal.pure
@deal.pre(lambda p_values: all(0.0 <= p <= 1.0 for p in p_values), message="p in [0, 1]")
@deal.ensure(
    lambda p_values, result: (
        len(result) == len(p_values)
        and all(a >= p for a, p in zip(result, p_values, strict=True))
        and all(0.0 <= a <= 1.0 for a in result)
    ),
    message="je p ein angepasstes, nie kleiner, höchstens 1",
)
def holm(p_values: Sequence[float]) -> list[float]:
    """Holm-angepasste p in der Folge der Eingabe (schrittweise, monoton, höchstens 1)."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: (p_values[i], i))
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


def verdict(p_holm: float | None, alpha: float) -> str:
    """``bestätigt`` genau dann, wenn Holm bei ``alpha`` verwirft; sonst ``nicht bestätigt``."""
    return CONFIRMED if p_holm is not None and p_holm < alpha else NOT_CONFIRMED


# --- Nachbarschaft und die Tabelle ---------------------------------------------------------------


def neighbours(areas: Sequence[BaseGeometry], threshold_m: float) -> Floats:
    """Nachbarschaft der Wahlbezirke für Moran's I: 1, wo sie eine Grenze teilen, sonst 0.

    So wie das Messskript (§ 3.5): ein Wahlbezirk ist Nachbar, wenn der Schnitt seines um 1 m
    gepufferten Nachbarn mit ihm einen Umfang über ``threshold_m`` hat -- also rund die Hälfte davon
    an gemeinsamer Grenze; eine Berührung in einem Punkt zählt nicht. Ein STRtree spart die Paare,
    deren Umschläge sich nicht berühren.
    """
    buffered = [area.buffer(1.0) for area in areas]
    tree = shapely.STRtree(list(areas))
    matrix = np.zeros((len(areas), len(areas)), dtype=np.float64)
    for i, grown in enumerate(buffered):
        for j in tree.query(grown):
            j = int(j)
            if i != j and grown.intersection(areas[j]).length > threshold_m:
                matrix[i, j] = 1.0
    return matrix


def _columns(frame: pl.DataFrame, need: NeedSettings) -> list[str]:
    wanted: list[str] = [DISTRICT, STRATUM]
    for h in need.hypotheses:
        wanted += [h.need, h.attention, *h.robust_need, *h.robust_attention]
        wanted += [h.robust_control] if h.robust_control else []
    for a, b in need.explore:
        wanted += [a, b]
    return list(dict.fromkeys(wanted))


def _row(**values: object) -> dict[str, object]:
    row: dict[str, object] = dict.fromkeys(HYPOTHESES_SCHEMA)
    row["ohne"] = []
    row["kontrolle"] = ""
    row.update(values)
    return row


def _pairs(frame: pl.DataFrame, a: str, b: str) -> tuple[Floats, Floats, pl.DataFrame]:
    sub = frame.drop_nulls([a, b])
    return (
        sub.get_column(a).cast(pl.Float64).to_numpy(),
        sub.get_column(b).cast(pl.Float64).to_numpy(),
        sub,
    )


def _robust_rows(
    frame: pl.DataFrame, h: NeedHypothesis, exclude: Sequence[int]
) -> list[dict[str, object]]:
    """Die vorab genannten Robustheitsrechnungen (rho ohne p; sie entscheiden nicht)."""
    rows: list[dict[str, object]] = []
    common = {"hypothese": h.name, "festgelegt": h.fixed, "rechnung": ROBUST, "explorativ": False}
    common |= {"mass": "spearman"}
    if exclude:
        x, y, sub = _pairs(
            frame.filter(~pl.col(DISTRICT).is_in(list(exclude))), h.need, h.attention
        )
        rows.append(
            _row(
                **common,
                bedarf=h.need,
                aufmerksamkeit=h.attention,
                ohne=sorted(exclude),
                wert=spearman(x, y),
                n=sub.height,
            )
        )
    for column in h.robust_need:
        x, y, sub = _pairs(frame, column, h.attention)
        rows.append(
            _row(
                **common,
                bedarf=column,
                aufmerksamkeit=h.attention,
                wert=spearman(x, y),
                n=sub.height,
            )
        )
    for column in h.robust_attention:
        x, y, sub = _pairs(frame, h.need, column)
        rows.append(
            _row(**common, bedarf=h.need, aufmerksamkeit=column, wert=spearman(x, y), n=sub.height)
        )
    if h.robust_control:
        sub = frame.drop_nulls([h.need, h.attention, h.robust_control])
        value = partial_spearman(
            *(
                sub.get_column(c).cast(pl.Float64).to_numpy()
                for c in (h.need, h.attention, h.robust_control)
            )
        )
        rows.append(
            _row(
                **common,
                bedarf=h.need,
                aufmerksamkeit=h.attention,
                kontrolle=h.robust_control,
                wert=value,
                n=sub.height,
            )
        )
    return rows


def _table_holds(result: pl.DataFrame, alpha: float) -> bool:
    if result.schema != pl.Schema(HYPOTHESES_SCHEMA):
        return False
    for column in ("p", "p_holm"):
        values = result.get_column(column).drop_nulls()
        if not bool(((values >= 0) & (values <= 1)).all()):
            return False
    main = result.filter(pl.col("rechnung") == MAIN)
    for p, p_holm, ergebnis in main.select("p", "p_holm", "ergebnis").rows():
        if p is not None and (p_holm is None or p_holm < p):
            return False
        if ergebnis != verdict(p_holm, alpha):
            return False
    others = result.filter(pl.col("rechnung") != MAIN)
    return others.get_column("ergebnis").null_count() == others.height


def _arguments_fit(
    frame: pl.DataFrame,
    need: NeedSettings,
    *,
    weights: Floats,
    exclude: Sequence[int] = (),
) -> bool:
    return (
        has_columns(frame, DISTRICT, STRATUM)
        and bool(frame.get_column(DISTRICT).is_sorted())
        and frame.get_column(DISTRICT).n_unique() == frame.height
        and weights.shape == (frame.height, frame.height)
    )


def _result_holds(
    frame: pl.DataFrame,
    need: NeedSettings,
    *,
    weights: Floats,
    exclude: Sequence[int] = (),
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return _table_holds(result, need.alpha)


@deal.pre(
    _arguments_fit, message="eine Zeile je Wahlbezirk, sortiert, mit Schicht und Nachbarschaft"
)
@deal.ensure(
    _result_holds, message="Schema, p in [0, 1], p_holm >= p, Ergebnis genau bei Holm unter alpha"
)
@deal.raises(SchemaError)
def hypothesis_table(
    frame: pl.DataFrame,
    need: NeedSettings,
    *,
    weights: Floats,
    exclude: Sequence[int] = (),
) -> pl.DataFrame:
    """Alle Zeilen von ``bedarf_hypothesen.parquet`` für eine Analysetabelle je Wahlbezirk.

    ``frame`` ist nach ``wahlkreis_id`` sortiert und trägt ``stadtbezirk`` und jede Spalte, die die
    Hypothesen und Paare nennen (sonst ``SchemaError`` mit den Namen); ``weights`` ist die
    Nachbarschaft in derselben Folge (``neighbours``), ``exclude`` die Wahlbezirke der
    Robustheitsrechnung „ohne Ausreißer" (``analysis.exclude_districts``). Eine Zeile ohne Wert
    in x oder y fällt aus der jeweiligen Rechnung, und ``n`` sagt, wie viele blieben.

    Folge der Zeilen: je Hypothese der Haupttest und ihre Robustheit, dann explorativ je Hypothese
    die Rechnung innerhalb der Stadtbezirke, dann je Hypothese Moran's I der Residuen, des Bedarfs
    und der Aufmerksamkeit, dann die Paare.
    """
    missing = [c for c in _columns(frame, need) if c not in frame.columns]
    if missing:
        raise SchemaError(f"Analysetabelle des Bedarfs: Spalten fehlen: {missing}")
    rows: list[dict[str, object]] = []

    # Vorab festgelegt: ein Generator, je Hypothese erst Permutationen, dann Bootstrap (§ 8).
    rng = np.random.default_rng(need.seed)
    main: list[dict[str, object]] = []
    for h in need.hypotheses:
        x, y, sub = _pairs(frame, h.need, h.attention)
        rho, p = permutation_test(
            x, y, alternative=h.alternative, permutations=need.permutations, rng=rng
        )
        low, high = (
            bootstrap_interval(x, y, draws=need.bootstrap, rng=rng)
            if rho is not None
            else (None, None)
        )
        main.append(
            _row(
                hypothese=h.name,
                p=p,
                n=sub.height,
                festgelegt=h.fixed,
                rechnung=MAIN,
                explorativ=False,
                bedarf=h.need,
                aufmerksamkeit=h.attention,
                mass="spearman",
                wert=rho,
                ci_lo=low,
                ci_hi=high,
                test="permutation",
                alternative=h.alternative,
                permutationen=need.permutations,
                seed=need.seed,
            )
        )
    adjusted = holm([1.0 if r["p"] is None else float(r["p"]) for r in main])  # type: ignore[arg-type]
    for h, row, p_holm in zip(need.hypotheses, main, adjusted, strict=True):
        row["p_holm"] = None if row["p"] is None else p_holm
        row["ergebnis"] = verdict(row["p_holm"], need.alpha)  # type: ignore[arg-type]
        rows.append(row)
        rows += _robust_rows(frame, h, exclude)

    # Explorativ (§ 3.5): ein zweiter Generator, erst innerhalb der Stadtbezirke, dann Moran's I.
    explore_rng = np.random.default_rng(need.seed + 1)
    count = need.explore_permutations
    common = {"explorativ": True, "permutationen": count, "seed": need.seed + 1}
    for h in need.hypotheses:
        x, y, sub = _pairs(frame, h.need, h.attention)
        strata = sub.get_column(STRATUM).to_numpy()
        value, p = within_strata(x, y, strata, permutations=count, rng=explore_rng)
        rows.append(
            _row(
                **common,
                hypothese=h.name,
                p=p,
                n=sub.height,
                rechnung=WITHIN,
                bedarf=h.need,
                aufmerksamkeit=h.attention,
                mass="spearman",
                wert=value,
                test="permutation",
                alternative="two-sided",
            )
        )
    for h in need.hypotheses:
        x, y, sub = _pairs(frame, h.need, h.attention)
        keep = frame.get_column(DISTRICT).is_in(sub.get_column(DISTRICT).to_list()).to_numpy()
        w = weights[np.ix_(keep, keep)]
        for rechnung, values in (
            (MORAN_RESIDUALS, rank_residuals(x, y)),
            (MORAN_NEED, ranks(x)),
            (MORAN_ATTENTION, ranks(y)),
        ):
            value, p = morans_i(values, w, permutations=count, rng=explore_rng)
            rows.append(
                _row(
                    **common,
                    hypothese=h.name,
                    p=p,
                    n=sub.height,
                    rechnung=rechnung,
                    bedarf=h.need,
                    aufmerksamkeit=h.attention,
                    mass="moran_i",
                    wert=value,
                    test="permutation",
                    alternative="greater",
                )
            )
    for a, b in need.explore:
        x, y, sub = _pairs(frame, a, b)
        value = spearman(x, y)
        p = float(stats.spearmanr(x, y).pvalue) if value is not None else None
        rows.append(
            _row(
                explorativ=True,
                n=sub.height,
                rechnung=PAIR,
                bedarf=a,
                aufmerksamkeit=b,
                mass="spearman",
                wert=value,
                p=p,
                test="asymptotisch",
                alternative="two-sided",
            )
        )
    return pl.DataFrame(rows, schema=HYPOTHESES_SCHEMA, orient="row")
