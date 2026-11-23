"""Maße der Validierung: Übereinstimmung zweier Kodierer und Güte eines Verfahrens (F4).

Zwei Fragen, zwei Gruppen von Maßen (docs/validierung.md, § 5):

- **Wie einig sind sich die beiden Kodierer?** Prozentuale Übereinstimmung mit Wilson-Intervall,
  Cohens κ und Krippendorffs α (nominal, ordinal, intervall). Stufe 3 eines Vorhabens verlangt
  α ≥ 0,8 (plan-vorverarbeitung-2026-11.md, § 2.6); darunter ist das Codebuch zu unscharf.
- **Wie gut trifft ein Verfahren die geschlichteten Labels?** Präzision, Recall und F1 je Klasse,
  mikro und makro gemittelt, mit Wilson-Intervall, wo die Größe ein Anteil ist; die
  Konfusionsmatrix; für Rangfolgen nDCG@k.

Alles hier ist rein und rechnet in reinem Python auf Sequenzen von Labels (Strings): keine Polars,
kein numpy, kein scikit-learn. scikit-learn darf nur in zwei Modulen von ``analysis/`` stehen
(``tests/unit/test_dependency_boundary.py``); die Tests vergleichen mit ihm
(``cohen_kappa_score``, ``precision_recall_fscore_support``, ``ndcg_score``), Krippendorffs α mit
den Rechenbeispielen aus Krippendorff (2011), Wilson mit einer Rechnung von Hand. Reines Python
hat einen zweiten Grund: crosshair kann es symbolisch prüfen (``nox -s verify``), numpy nicht.

Was undefiniert ist, ist ``None`` und nicht 0 oder NaN: κ, wenn beide Kodierer immer dasselbe
eine Label vergeben (die Zufallsübereinstimmung ist dann 1), α, wenn die Kodierungen nur einen
Wert kennen (keine Streuung, an der sich Übereinstimmung zeigen könnte), Präzision einer Klasse,
die das Verfahren nie vergibt, nDCG einer Anfrage ohne ein einziges relevantes Dokument. Die
Makromittel folgen scikit-learn (``zero_division=0``): eine undefinierte Klasse zählt dort als 0.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import deal

from georep.contracts import is_number, labels_known, proportion_or_none

# Quantil 0,975 der Standardnormalverteilung: das zweiseitige 95-%-Intervall. Fest, weil jede Zahl
# der Seite dasselbe Niveau nennen soll; ein anderes Niveau wäre eine zweite Wahrheit.
Z95 = 1.959963984540054
Level = Literal["nominal", "ordinal", "interval"]
LEVELS: tuple[Level, ...] = ("nominal", "ordinal", "interval")
Interval = tuple[float, float]


def _wilson_holds(successes: int, trials: int, result: Interval) -> bool:
    low, high = result
    return 0.0 <= low <= successes / trials <= high <= 1.0


@deal.pre(
    lambda successes, trials: 0 <= successes <= trials and trials > 0,
    message="ein Anteil: 0 ≤ Treffer ≤ Versuche, mindestens ein Versuch",
)
@deal.ensure(_wilson_holds, message="das Intervall liegt in [0, 1] und enthält den Anteil")
@deal.pure
def wilson_interval(successes: int, trials: int) -> Interval:
    """Das 95-%-Intervall nach Wilson für den Anteil ``successes / trials``.

    Wilson statt Wald, weil die Stichproben klein sind und Anteile nahe 1 liegen sollen
    (Präzision ≥ 0,95): das Wald-Intervall reicht dort über 1 hinaus und ist bei 0 oder n
    Treffern null breit. Die Formel ist (p + z²/2n ± z·√(p(1−p)/n + z²/4n²)) / (1 + z²/n).
    Mathematisch liegt der Anteil immer im Intervall; ``min`` und ``max`` fangen nur die Rundung
    bei 0 und n Treffern (dort ist die eine Grenze exakt der Anteil).
    """
    return _wilson(successes, trials)


def _wilson(successes: int, trials: int) -> Interval:
    """``wilson_interval`` ohne Vertrag, für ``classify_scores``: zwei ``deal.pure`` ineinander
    sind zwei verschachtelte Patcher, und deals ``has()`` ist nicht reentrant (CLAUDE.md)."""
    p = successes / trials
    z2 = Z95 * Z95
    denominator = 1.0 + z2 / trials
    centre = (p + z2 / (2 * trials)) / denominator
    half = Z95 * math.sqrt(p * (1.0 - p) / trials + z2 / (4 * trials * trials)) / denominator
    return max(0.0, min(p, centre - half)), min(1.0, max(p, centre + half))


@deal.pre(
    lambda first, second: len(first) == len(second), message="je Einheit ein Label von beiden"
)
@deal.post(proportion_or_none, message="ein Anteil, oder None ohne Einheit")
@deal.pure
def agreement(first: Sequence[str], second: Sequence[str]) -> float | None:
    """Der Anteil der Einheiten, an denen beide dasselbe Label vergeben haben."""
    if not first:
        return None
    return sum(1 for a, b in zip(first, second, strict=True) if a == b) / len(first)


def _kappa_bounded(first: Sequence[str], second: Sequence[str], result: float | None) -> bool:
    return result is None or -1.0 - 1e-12 <= result <= 1.0 + 1e-12


@deal.pre(
    lambda first, second: len(first) == len(second) and len(first) > 0,
    message="je Einheit ein Label von beiden, mindestens eine Einheit",
)
@deal.ensure(_kappa_bounded, message="κ liegt in [-1, 1]")
@deal.pure
def cohen_kappa(first: Sequence[str], second: Sequence[str]) -> float | None:
    """Cohens κ zweier Kodierer: (p_o − p_e) / (1 − p_e), p_e aus den beiden Randverteilungen.

    Ganzzahlig gerechnet, damit „undefiniert" eine exakte Bedingung ist und keine Rundung:
    mit n Einheiten, a übereinstimmenden und s = Σ_c n_A(c)·n_B(c) ist κ = (n·a − s) / (n² − s),
    und n² = s heißt, beide haben immer dasselbe eine Label vergeben. Symmetrisch in den beiden
    Kodierern; gleich ``sklearn.metrics.cohen_kappa_score`` ohne Gewichte.
    """
    n = len(first)
    agreed = sum(1 for a, b in zip(first, second, strict=True) if a == b)
    counts_first, counts_second = Counter(first), Counter(second)
    chance = sum(count * counts_second[label] for label, count in counts_first.items())
    if n * n == chance:
        return None
    return (n * agreed - chance) / (n * n - chance)


def _units_fit(
    units: Sequence[Sequence[str | None]], level: Level, categories: Sequence[str]
) -> bool:
    if len(set(categories)) != len(categories):
        return False
    if level == "interval":
        numbers = [float(c) for c in categories if is_number(c)]
        if len(numbers) != len(categories) or len(set(numbers)) != len(numbers):
            return False
    return all(labels_known([v for v in unit if v is not None], categories) for unit in units)


def _alpha_at_most_one(
    units: Sequence[Sequence[str | None]],
    level: Level,
    categories: Sequence[str],
    result: float | None,
) -> bool:
    return result is None or (math.isfinite(result) and result <= 1.0 + 1e-12)


@deal.pre(
    _units_fit,
    message="jeder Wert ist eine der Kategorien; Kategorien eindeutig, intervall: eindeutige Zahlen",
)
@deal.ensure(_alpha_at_most_one, message="α ist höchstens 1")
@deal.pure
def krippendorff_alpha(
    units: Sequence[Sequence[str | None]], level: Level, categories: Sequence[str]
) -> float | None:
    """Krippendorffs α über Einheiten mit beliebig vielen Kodierern; ``None`` ist ein fehlender Wert.

    Nach Krippendorff (2011), „Computing Krippendorff's Alpha-Reliability", über die
    Koinzidenzmatrix: jede Einheit mit m ≥ 2 Werten trägt jedes geordnete Wertepaar mit dem
    Gewicht 1/(m − 1) bei; α = 1 − (n − 1) · Σ o_ck δ²_ck / Σ n_c n_k δ²_ck. Einheiten mit weniger
    als zwei Werten sind nicht paarbar und fallen weg. ``categories`` legt die Werte fest und für
    ``ordinal`` ihre Reihenfolge (die erste ist die niedrigste); für ``interval`` sind es Zahlen in
    Textform („1" bis „5"). Die ordinale Distanz hängt nur an den beobachteten Häufigkeiten:
    δ²_ck = (Σ_{g=c..k} n_g − (n_c + n_k)/2)².

    ``None``, wenn die paarbaren Werte nur eine Kategorie kennen: dann ist die erwartete
    Uneinigkeit null und α nicht definiert. Zwei identische Kodierungen mit mindestens zwei
    Kategorien ergeben genau 1.
    """
    index = {category: i for i, category in enumerate(categories)}
    size = len(categories)
    coincidence = [[0.0] * size for _ in range(size)]
    for unit in units:
        values = [index[value] for value in unit if value is not None]
        if len(values) < 2:
            continue
        weight = 1.0 / (len(values) - 1)
        counts = Counter(values)
        for c, n_c in counts.items():
            for k, n_k in counts.items():
                coincidence[c][k] += n_c * (n_k - (1 if c == k else 0)) * weight
    totals = [sum(row) for row in coincidence]
    if sum(1 for total in totals if total > 0) < 2:
        return None
    delta = _distances(level, categories, totals)
    observed = sum(
        coincidence[c][k] * delta[c][k] for c in range(size) for k in range(size) if c != k
    )
    expected = sum(
        totals[c] * totals[k] * delta[c][k] for c in range(size) for k in range(size) if c != k
    )
    return 1.0 - (sum(totals) - 1.0) * observed / expected


def _distances(
    level: Level, categories: Sequence[str], totals: Sequence[float]
) -> list[list[float]]:
    """Die quadrierte Distanz δ²_ck je Paar von Kategorien für das Skalenniveau."""
    size = len(categories)
    if level == "nominal":
        return [[0.0 if c == k else 1.0 for k in range(size)] for c in range(size)]
    if level == "interval":
        numbers = [float(category) for category in categories]
        return [[(numbers[c] - numbers[k]) ** 2 for k in range(size)] for c in range(size)]
    distances = [[0.0] * size for _ in range(size)]
    for c in range(size):
        for k in range(size):
            low, high = min(c, k), max(c, k)
            between = sum(totals[low : high + 1]) - (totals[c] + totals[k]) / 2.0
            distances[c][k] = between * between
    return distances


@dataclass(frozen=True)
class ClassScore:
    """Eine Klasse: Zählung und Güte des Verfahrens gegen die Labels."""

    label: str
    support: int  # Einheiten mit diesem Label (Goldstandard)
    predicted: int  # Einheiten, denen das Verfahren dieses Label gibt
    true_positive: int
    precision: float | None  # None: das Verfahren vergibt das Label nie
    recall: float | None  # None: kein Label dieser Klasse in der Stichprobe
    f1: float | None
    precision_interval: Interval | None
    recall_interval: Interval | None


@dataclass(frozen=True)
class Classification:
    """Präzision, Recall, F1 je Klasse und gemittelt, mit der Konfusionsmatrix (Zeilen: Gold)."""

    n: int
    labels: tuple[str, ...]
    classes: tuple[ClassScore, ...]
    accuracy: float
    accuracy_interval: Interval
    micro_precision: float
    micro_recall: float
    micro_f1: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    confusion: tuple[tuple[int, ...], ...]

    def of(self, label: str) -> ClassScore:
        return next(score for score in self.classes if score.label == label)


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _classification_fits(
    gold: Sequence[str], predicted: Sequence[str], labels: Sequence[str]
) -> bool:
    return (
        len(gold) == len(predicted) > 0
        and len(set(labels)) == len(labels) > 0
        and labels_known(gold, labels)
        and labels_known(predicted, labels)
    )


def _scores_are_proportions(result: Classification) -> bool:
    values = [
        result.accuracy,
        result.micro_precision,
        result.micro_recall,
        result.micro_f1,
        result.macro_precision,
        result.macro_recall,
        result.macro_f1,
    ] + [v for c in result.classes for v in (c.precision, c.recall, c.f1) if v is not None]
    cells = sum(sum(row) for row in result.confusion)
    return all(0.0 <= v <= 1.0 for v in values) and cells == result.n


@deal.pre(
    _classification_fits,
    message="gleich viele Labels, mindestens eins, alle aus der Liste, die Liste eindeutig",
)
@deal.post(
    _scores_are_proportions, message="jede Güte in [0, 1], die Matrix zählt jede Einheit einmal"
)
@deal.pure
def classify_scores(
    gold: Sequence[str], predicted: Sequence[str], labels: Sequence[str]
) -> Classification:
    """Präzision, Recall und F1 je Klasse, mikro und makro, mit Wilson-Intervallen.

    Einlabelig: jede Einheit hat genau ein Gold- und ein vorhergesagtes Label. Die Mikromittel
    über alle Klassen sind dann gleich der Genauigkeit (jeder Fehler ist ein falsch Positiver der
    einen und ein falsch Negativer der anderen Klasse) und haben deren Wilson-Intervall. Präzision
    und Recall einer Klasse sind Anteile und bekommen ihr eigenes; F1 und die Makromittel sind
    keine Anteile und bekommen keines. Die Makromittel sind ungewichtete Mittel über die Klassen,
    die im Goldstandard vorkommen oder vergeben werden (scikit-learn mit ``labels`` = diese Klassen
    und ``zero_division=0``); das Makro-F1 ist das Mittel der F1 je Klasse, nicht das F1 der
    beiden Makromittel.
    """
    n = len(gold)
    position = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for g, p in zip(gold, predicted, strict=True):
        matrix[position[g]][position[p]] += 1
    classes = []
    for i, label in enumerate(labels):
        support = sum(matrix[i])
        guessed = sum(row[i] for row in matrix)
        hit = matrix[i][i]
        precision = hit / guessed if guessed else None
        recall = hit / support if support else None
        classes.append(
            ClassScore(
                label=label,
                support=support,
                predicted=guessed,
                true_positive=hit,
                precision=precision,
                recall=recall,
                f1=_f1(precision, recall),
                precision_interval=_wilson(hit, guessed) if guessed else None,
                recall_interval=_wilson(hit, support) if support else None,
            )
        )
    correct = sum(matrix[i][i] for i in range(len(labels)))
    accuracy = correct / n

    # Befund 5 (Review 2026-11-23): eine Klasse, die weder im Goldstandard vorkommt noch vergeben
    # wird, sagt nichts über das Verfahren und zöge jedes Makromittel nach unten.
    present = [c for c in classes if c.support or c.predicted]

    def mean(values: list[float | None]) -> float:
        return sum(v or 0.0 for v in values) / len(values)

    return Classification(
        n=n,
        labels=tuple(labels),
        classes=tuple(classes),
        accuracy=accuracy,
        accuracy_interval=_wilson(correct, n),
        micro_precision=accuracy,
        micro_recall=accuracy,
        micro_f1=accuracy,
        macro_precision=mean([c.precision for c in present]),
        macro_recall=mean([c.recall for c in present]),
        macro_f1=mean([c.f1 for c in present]),
        confusion=tuple(tuple(row) for row in matrix),
    )


def _ranking_fits(scores: Mapping[str, float], gains: Mapping[str, float], k: int) -> bool:
    return (
        k >= 1
        and all(math.isfinite(v) for v in scores.values())
        and all(math.isfinite(g) and g >= 0.0 for g in gains.values())
        and math.isfinite(sum(gains.values()))
    )


def _ndcg_bounded(
    scores: Mapping[str, float], gains: Mapping[str, float], k: int, result: float | None
) -> bool:
    return result is None or 0.0 <= result <= 1.0 + 1e-9


def _discount(rank: int, k: int) -> float:
    return 1.0 / math.log2(rank + 2) if rank < k else 0.0


def _tie_averaged_dcg(groups: Sequence[Sequence[float]], k: int) -> float:
    """DCG@k über Gruppen gleicher Punktzahl in absteigender Folge: jede Gruppe trägt das Mittel
    ihrer Gewinne mal die Summe ihrer Abschläge, wie ``sklearn.metrics.ndcg_score``."""
    total, rank = 0.0, 0
    for group in groups:
        discounts = sum(_discount(r, k) for r in range(rank, rank + len(group)))
        total += sum(group) / len(group) * discounts
        rank += len(group)
    return total


@deal.pre(
    _ranking_fits,
    message="k ≥ 1, Punktzahlen endlich, Gewinne ≥ 0 und endlich, auch summiert",
)
@deal.ensure(_ndcg_bounded, message="nDCG liegt in [0, 1]")
@deal.pure
def ndcg_at_k(scores: Mapping[str, float], gains: Mapping[str, float], k: int) -> float | None:
    """nDCG@k einer Anfrage über die geurteilten Dokumente: Punktzahlen des Verfahrens gegen Urteile.

    ``gains`` sind die geurteilten Dokumente mit ihrer Relevanz (die Stufe des Codebuchs, 0 für
    die niedrigste), ``scores`` die Punktzahlen des Verfahrens. Gewertet werden nur geurteilte
    Dokumente (die „condensed list" nach Sakai 2007): ein nicht geurteiltes Dokument zählt weder
    als relevant noch als irrelevant, statt still als 0 die Zahl zu drücken. Ein geurteiltes
    Dokument ohne Punktzahl steht hinter allen mit Punktzahl. Gleichstände werden gemittelt, der
    Gewinn ist linear, Σ rel_i / log2(i + 1) über die ersten k Ränge -- beides wie
    ``sklearn.metrics.ndcg_score``. ``None``, wenn kein geurteiltes Dokument Relevanz über 0 hat.
    """
    ideal = _tie_averaged_dcg([[g] for g in sorted(gains.values(), reverse=True)], k)
    if ideal <= 0.0:
        return None
    ranked: dict[float, list[float]] = {}
    for doc, gain in gains.items():
        if doc in scores:
            ranked.setdefault(scores[doc], []).append(gain)
    groups = [ranked[score] for score in sorted(ranked, reverse=True)]
    unscored = [gain for doc, gain in gains.items() if doc not in scores]
    if unscored:
        groups.append(unscored)
    return min(1.0, _tie_averaged_dcg(groups, k) / ideal)


# --- Gewichte: die geschichtete Stichprobe (Befund 1 des Reviews, 2026-11-23) -------------------


@dataclass(frozen=True)
class StratifiedShare:
    """Ein Anteil, geschätzt für die Grundgesamtheit aus einer geschichteten Stichprobe."""

    estimate: float
    interval: Interval
    effective_n: float  # Kishs effektive Stichprobengröße (Σ w)² / Σ w²
    population: int  # Σ N_h über die Schichten mit mindestens einer gewerteten Einheit


def _shares_fit(hits: Mapping[str, tuple[int, int]], sizes: Mapping[str, int]) -> bool:
    return (
        bool(hits)
        and set(hits) <= set(sizes)
        and all(0 <= x <= m and m >= 1 for x, m in hits.values())
        and all(sizes[h] >= hits[h][1] for h in hits)
    )


def _share_holds(
    hits: Mapping[str, tuple[int, int]], sizes: Mapping[str, int], result: StratifiedShare
) -> bool:
    low, high = result.interval
    return (
        0.0 <= low <= result.estimate <= high <= 1.0
        and 0.0 < result.effective_n <= sum(m for _, m in hits.values()) + 1e-9
    )


@deal.pre(_shares_fit, message="je Schicht 0 ≤ Treffer ≤ gewertet ≥ 1, und gewertet ≤ N_h")
@deal.ensure(_share_holds, message="Schätzer im Intervall, n_eff höchstens die Zahl der Einheiten")
@deal.pure
def stratified_share(
    hits: Mapping[str, tuple[int, int]], sizes: Mapping[str, int]
) -> StratifiedShare:
    """Σ_h W_h · x_h/m_h mit W_h = N_h/N, und ein Wilson-Intervall mit Kishs effektivem n.

    ``hits`` nennt je Schicht (Treffer x_h, gewertete Einheiten m_h), ``sizes`` die Schichtgrößen
    N_h der Grundgesamtheit; jede gewertete Einheit trägt das Gewicht N_h/m_h. Das Intervall ist
    das nach Wilson für den Schätzer bei n_eff = (Σ w)² / Σ w² = N² / Σ_h N_h²/m_h (Kish 1965):
    geschlossen, ohne Zufall, in [0, 1], und anders als ein Bootstrap oder die geschichtete
    Normalnäherung nicht null breit, wenn Schichten nur Treffer haben. Bei einer
    selbstgewichtenden Stichprobe ist n_eff = n und alles fällt auf den einfachen Anteil zurück.
    Schichten ohne gewertete Einheit tragen nichts bei; ihr Anteil an N fehlt dem Schätzer.
    """
    population = sum(sizes[h] for h in hits)
    estimate = sum(sizes[h] * x / m for h, (x, m) in hits.items()) / population
    effective = population * population / sum(sizes[h] * sizes[h] / m for h, (_, m) in hits.items())
    effective = min(effective, float(sum(m for _, m in hits.values())))
    return StratifiedShare(estimate, _wilson_share(estimate, effective), effective, population)


def _wilson_share(p: float, n: float) -> Interval:
    """Wilson für einen Anteil ``p`` bei (auch nicht ganzzahligem) ``n``."""
    z2 = Z95 * Z95
    denominator = 1.0 + z2 / n
    centre = (p + z2 / (2 * n)) / denominator
    half = Z95 * math.sqrt(max(0.0, p * (1.0 - p)) / n + z2 / (4 * n * n)) / denominator
    return max(0.0, min(p, centre - half)), min(1.0, max(p, centre + half))


def weighted_accuracy(
    gold: Sequence[str], predicted: Sequence[str], strata: Sequence[str], sizes: Mapping[str, int]
) -> StratifiedShare:
    """Die Genauigkeit eines Verfahrens, für die Grundgesamtheit geschätzt (Gewichte N_h/n_h)."""
    hits: dict[str, tuple[int, int]] = {}
    for g, p, h in zip(gold, predicted, strata, strict=True):
        x, m = hits.get(h, (0, 0))
        hits[h] = (x + (g == p), m + 1)
    return stratified_share(hits, sizes)
