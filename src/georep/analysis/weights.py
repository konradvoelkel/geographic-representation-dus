"""Gewichtete Trefferquoten: Varianten zur binären Zählung der Arbeit.

Die Trefferquote der Arbeit ist binär: ein Dokument zählt für einen Wahlbezirk, sobald ein Begriff
seines Wörterbuchs darin vorkommt. Hier bekommt jedes Paar (Wahlbezirk, Dokument) ein Gewicht

    g(d, p) = max über die getroffenen Begriffe t von w_begriff(t) · w_art(p) · w_thema(p),

und die gewichteten Treffer eines Wahlbezirks sind die Summe der Gewichte seiner Dokumente. Jeder
Faktor liegt in [0, 1], also ist ``g ≤ 1``: ein Dokument zählt je Bezirk höchstens einmal, wie die
Vereinigung in ``analysis.hits``. Bei Einheitsgewichten ist ``g = 1`` und die Summe gleich
``anzahl_treffer`` -- das ist der Vertrag, an dem jede Variante hängt (docs/architecture.md,
„Analyse"; docs/plans/06-gewichtung.md).

Alles hier ist eine reine Funktion von Frames auf Frames: das Modul kennt keine Dateien und keine
Settings-Objekte, Regeln und Zahlen kommen als Argumente (``TypeRules``), damit dieselbe Rechnung
von außen mit jedem Frame läuft.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import deal
import polars as pl

from georep.analysis.hits import DISTRICT, hits_by_district
from georep.contracts import all_nonnegative, has_columns, in_unit_interval, sorted_unique
from georep.errors import EmptyResultError
from georep.search.index import HITS, PAPER_IDS, TERM

DOC = "id"  # Korpus-ID eines Dokuments, wie in papers.parquet und paper_ids
PAPER_TYPE = "paper_type"
WEIGHT = "gewicht"
N_DISTRICTS = "n_bezirke"
W_DISTRICT = "gewicht_bezirke"
W_IDF = "gewicht_idf"
SHARES = "anteile"  # Themenanteile je Dokument, Liste der Länge K
VARIANT = "variante"
WEIGHTED_HITS = "anzahl_treffer_gewichtet"
WEIGHTED_RATE = "trefferquote_gewichtet"

# Die festen Varianten. ``settings.FIXED_VARIANTS`` hält dieselben Namen, damit ein Regelsatz in den
# Settings keinen davon tragen kann; ein Test in tests/unit/test_weights.py hält beide gleich.
UNIT = "einheit"
BY_DISTRICTS = "bezirke"
BY_IDF = "idf"
COMBINED = "kombiniert"
TOPIC_PREFIX = "thema_"


def topic_variant(index: int) -> str:
    """Name der Variante zu Thema ``index``: ``thema_07``, damit die Namen lesbar sortieren."""
    return f"{TOPIC_PREFIX}{index:02d}"


@dataclass(frozen=True)
class TypeRules:
    """Ein Regelsatz auf ``paper_type``: geordnete (Muster, Gewicht), die erste passende gewinnt.

    Entspricht einem ``[[weights.paper_type]]``-Block der Settings, ohne dessen Modell zu kennen.
    """

    name: str
    default: float = 1.0
    rules: tuple[tuple[str, float], ...] = field(default_factory=tuple)


# --- Gewicht je Begriff -------------------------------------------------------------------------


@deal.pure
@deal.pre(lambda n: n >= 1)
@deal.post(lambda result: 0.0 < result <= 1.0)
def district_weight(n: int) -> float:
    """Spezifität nach Bezirken: ein Begriff in ``n`` Wörterbüchern zählt für jeden mit ``1/n``.

    Die Anteile eines Begriffs über die Bezirke summieren damit zu 1.
    """
    return 1.0 / n


@deal.pure
@deal.pre(lambda df, n: n >= 0 and 0 <= df <= n)
@deal.post(lambda result: 0.0 <= result <= 1.0)
def idf_weight(df: int, n: int) -> float:
    """Normierte inverse Dokumenthäufigkeit ``(ln n − ln df) / ln n`` in [0, 1], ohne Parameter.

    Ein Begriff in einem einzigen von ``n`` Dokumenten zählt 1, einer in allen 0. ``df = 0`` hat
    keine Treffer und bleibt wirkungslos (1); ``n ≤ 1`` heißt „ein Dokument ist die ganze Stadt",
    dann steht jeder vorkommende Begriff in allen Dokumenten und zählt 0.
    """
    if df <= 0:
        return 1.0
    if n <= 1:
        return 0.0
    return (math.log(n) - math.log(df)) / math.log(n)


def idf_expression(n_documents: int) -> pl.Expr:
    """``idf_weight`` als Ausdruck über ``anzahl_treffer``, spaltenweise statt je Zeile.

    Ein Eigenschaftstest hält Ausdruck und Funktion auf eine letzte Stelle zusammen: Polars teilt
    durch ein skalares Literal, indem es mit dem Kehrwert multipliziert, und das kostet ein ulp
    (gemessen 2026-10-12, tests/unit/test_weights.py). Die Schranke [0, 1] hält trotzdem.
    """
    if n_documents <= 1:
        return pl.when(pl.col(HITS) <= 0).then(pl.lit(1.0)).otherwise(pl.lit(0.0)).alias(W_IDF)
    log_n = math.log(n_documents)
    return (
        pl.when(pl.col(HITS) <= 0)
        .then(pl.lit(1.0))
        .otherwise((pl.lit(log_n) - pl.col(HITS).cast(pl.Float64).log()) / pl.lit(log_n))
        .alias(W_IDF)
    )


def _covers_the_index_terms(
    dictionary: pl.DataFrame,
    index: pl.DataFrame,
    n_documents: int,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return result.get_column(TERM).to_list() == sorted(index.get_column(TERM).to_list())


@deal.pre(
    lambda dictionary, index, n_documents: (
        has_columns(dictionary, DISTRICT, TERM) and has_columns(index, TERM, HITS)
    )
)
@deal.pre(
    lambda dictionary, index, n_documents: (
        n_documents >= 0 and bool((index.get_column(HITS) <= n_documents).all())
    ),
    message="ein Begriff kann nicht in mehr Dokumenten stehen, als es Dokumente gibt",
)
@deal.post(lambda result: result.columns == [TERM, N_DISTRICTS, HITS, W_DISTRICT, W_IDF])
@deal.post(lambda result: sorted_unique(result, TERM))
@deal.post(
    # ``.all()`` übergeht Nullen, darum die Zählung daneben: ein Begriff ohne Wahlbezirk käme sonst
    # als fehlender Wert durch und bekäme stillschweigend ein Gewicht.
    lambda result: (
        result.get_column(N_DISTRICTS).null_count() == 0
        and bool((result.get_column(N_DISTRICTS) >= 1).all())
    ),
    message="jeder Begriff des Index steht im Wörterbuch mindestens eines Wahlbezirks",
)
@deal.post(lambda result: in_unit_interval(result, W_DISTRICT, W_IDF))
@deal.ensure(_covers_the_index_terms, message="genau die Begriffe des Index")
def term_weights(dictionary: pl.DataFrame, index: pl.DataFrame, n_documents: int) -> pl.DataFrame:
    """Je Begriff: Zahl der Wahlbezirke, Dokumenthäufigkeit und die zwei Spezifitätsgewichte."""
    per_term = (
        dictionary.select(DISTRICT, TERM)
        .explode(TERM)
        .unique()
        .group_by(TERM)
        .agg(pl.len().cast(pl.Int64).alias(N_DISTRICTS))
    )
    return (
        index.select(TERM, HITS)
        .join(per_term, on=TERM, how="left")
        .with_columns((1.0 / pl.col(N_DISTRICTS)).alias(W_DISTRICT), idf_expression(n_documents))
        .select(TERM, N_DISTRICTS, HITS, W_DISTRICT, W_IDF)
        .sort(TERM)
    )


# --- Gewicht je Dokumentart ---------------------------------------------------------------------


@deal.pre(
    lambda rules, default=1.0: (
        0.0 <= default <= 1.0 and all(0.0 <= weight <= 1.0 for _, weight in rules)
    ),
    message="Gewichte einer Regel liegen in [0, 1]",
)
def compile_rules(rules: Sequence[tuple[str, float]], default: float = 1.0) -> pl.Expr:
    """Die Regeln als ein ``when``/``then``-Ausdruck auf ``paper_type``, erste passende Regel gewinnt.

    Ein Ausdruck statt kompilierter Python-Muster: Polars prüft die Regex spaltenweise
    (``(?i)`` macht sie unabhängig von Groß- und Kleinschreibung), ``map_elements`` je Zeile wäre
    hundertmal teurer. Die Regeln werden von hinten eingewickelt, damit die vordere außen steht
    und gewinnt. ``paper_type`` ohne Wert (``PaperRecord`` erlaubt es) bekommt ``default``.
    """
    expression = pl.lit(default, dtype=pl.Float64)
    for pattern, weight in reversed(list(rules)):
        expression = (
            pl.when(pl.col(PAPER_TYPE).fill_null("").str.contains(f"(?i){pattern}"))
            .then(pl.lit(weight, dtype=pl.Float64))
            .otherwise(expression)
        )
    return expression.alias(WEIGHT)


@deal.pre(lambda paper_types, rules, default=1.0: has_columns(paper_types, DOC, PAPER_TYPE))
@deal.post(lambda result: result.columns == [DOC, WEIGHT])
@deal.post(lambda result: sorted_unique(result, DOC) and in_unit_interval(result, WEIGHT))
def paper_type_weights(
    paper_types: pl.DataFrame, rules: Sequence[tuple[str, float]], default: float = 1.0
) -> pl.DataFrame:
    """Eine Zeile je Dokument: das Gewicht seiner Dokumentart nach ``rules``."""
    return paper_types.select(DOC, compile_rules(rules, default)).sort(DOC)


# --- Paare, Gewichte je Paar, Summen je Wahlbezirk ----------------------------------------------


def _pairs_match_the_union(
    dictionary: pl.DataFrame, index: pl.DataFrame, result: pl.DataFrame | None = None
) -> bool:
    """Die Paarmenge (Bezirk, Dokument) ist dieselbe, die ``hits_by_district`` vereinigt."""
    assert result is not None
    hits = hits_by_district(dictionary, index)
    expected = {
        (int(row[DISTRICT]), paper)
        for row in hits.iter_rows(named=True)
        for paper in row[PAPER_IDS]
    }
    found = {(int(d), p) for d, p in result.select(DISTRICT, DOC).unique().iter_rows()}
    return found == expected


@deal.pre(
    lambda dictionary, index: (
        has_columns(dictionary, DISTRICT, TERM) and has_columns(index, TERM, PAPER_IDS)
    )
)
@deal.post(lambda result: result.columns == [DISTRICT, DOC, TERM])
@deal.post(
    lambda result: result.height == result.unique().height, message="jedes Tripel genau einmal"
)
@deal.ensure(_pairs_match_the_union, message="dieselben Paare wie die Vereinigung der Arbeit")
@deal.raises(EmptyResultError)
def document_pairs(dictionary: pl.DataFrame, index: pl.DataFrame) -> pl.DataFrame:
    """Die Tripel (Wahlbezirk, Dokument, Begriff): jeder Treffer einzeln, vor dem Maximum."""
    triples = (
        dictionary.select(DISTRICT, TERM)
        .explode(TERM)
        .join(index.select(TERM, PAPER_IDS), on=TERM, how="inner")
        .explode(PAPER_IDS)
        .drop_nulls(PAPER_IDS)
        .rename({PAPER_IDS: DOC})
        .select(DISTRICT, DOC, TERM)
        .unique()
        .sort([DISTRICT, DOC, TERM])
    )
    if triples.is_empty():
        raise EmptyResultError(
            "Kein Suchbegriff des Wörterbuchs trifft ein Dokument des Index: keine Paare."
        )
    return triples


def _one_row_per_pair(
    pairs: pl.DataFrame,
    term_weights: pl.DataFrame | None = None,
    type_weights: pl.DataFrame | None = None,
    topic_weights: pl.DataFrame | None = None,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return result.height == pairs.select(DISTRICT, DOC).unique().height


@deal.pre(
    lambda pairs, term_weights=None, type_weights=None, topic_weights=None: (
        has_columns(pairs, DISTRICT, DOC, TERM)
        and (term_weights is None or has_columns(term_weights, TERM, WEIGHT))
        and (type_weights is None or has_columns(type_weights, DOC, WEIGHT))
        and (topic_weights is None or has_columns(topic_weights, DOC, WEIGHT))
    )
)
@deal.pre(
    lambda pairs, term_weights=None, type_weights=None, topic_weights=None: all(
        in_unit_interval(frame, WEIGHT)
        for frame in (term_weights, type_weights, topic_weights)
        if frame is not None
    ),
    message="jeder Faktor liegt in [0, 1]",
)
@deal.post(lambda result: result.columns == [DISTRICT, DOC, WEIGHT])
@deal.post(lambda result: in_unit_interval(result, WEIGHT), message="g ≤ 1 je Paar")
@deal.ensure(_one_row_per_pair, message="eine Zeile je Paar (Wahlbezirk, Dokument)")
def document_weights(
    pairs: pl.DataFrame,
    term_weights: pl.DataFrame | None = None,
    type_weights: pl.DataFrame | None = None,
    topic_weights: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Gewicht je Paar: Maximum über die Begriffe, mal Dokumentart, mal Thema.

    Ein fehlender Faktor gilt als 1, auch für einen Begriff oder ein Dokument, das im Faktorframe
    nicht vorkommt. Das Maximum steht vor den Faktoren je Dokument: die sind in der Gruppe
    konstant und nicht negativ, darum ist ``max(w_t · c) = max(w_t) · c``, und ein ``sum`` an
    dieser Stelle würde die Schranke 1 sofort brechen.
    """
    per_term = (
        pairs.select(DISTRICT, DOC, TERM).with_columns(pl.lit(1.0, dtype=pl.Float64).alias(WEIGHT))
        if term_weights is None
        else pairs.select(DISTRICT, DOC, TERM)
        .join(term_weights.select(TERM, WEIGHT), on=TERM, how="left")
        .with_columns(pl.col(WEIGHT).fill_null(1.0))
    )
    weights = per_term.group_by(DISTRICT, DOC).agg(pl.col(WEIGHT).max())
    for factor in (type_weights, topic_weights):
        if factor is None:
            continue
        weights = (
            weights.join(factor.select(DOC, pl.col(WEIGHT).alias("_faktor")), on=DOC, how="left")
            .with_columns((pl.col(WEIGHT) * pl.col("_faktor").fill_null(1.0)).alias(WEIGHT))
            .drop("_faktor")
        )
    return weights.select(DISTRICT, DOC, WEIGHT).sort([DISTRICT, DOC])


def _not_more_than_the_pairs(
    weights: pl.DataFrame,
    voters: pl.DataFrame,
    eligible_column: str,
    result: pl.DataFrame | None = None,
) -> bool:
    """Jedes Gewicht ist höchstens 1, also zählt eine Variante nie mehr als die Arbeit."""
    assert result is not None
    counts = dict(
        weights.group_by(DISTRICT).agg(pl.len().alias("n")).select(DISTRICT, "n").iter_rows()
    )
    return all(
        row[WEIGHTED_HITS] <= counts.get(row[DISTRICT], 0) + 1e-9
        for row in result.iter_rows(named=True)
    )


@deal.pre(
    lambda weights, voters, eligible_column: (
        has_columns(weights, DISTRICT, WEIGHT) and has_columns(voters, DISTRICT, eligible_column)
    )
)
@deal.pre(
    lambda weights, voters, eligible_column: bool((voters.get_column(eligible_column) > 0).all()),
    message="Wahlberechtigte je Wahlbezirk müssen positiv sein, sonst ist die Quote undefiniert",
)
@deal.post(lambda result: result.columns == [DISTRICT, WEIGHTED_HITS, WEIGHTED_RATE])
@deal.post(
    lambda result: (
        sorted_unique(result, DISTRICT) and all_nonnegative(result, WEIGHTED_HITS, WEIGHTED_RATE)
    )
)
@deal.ensure(_not_more_than_the_pairs, message="gewichtete Treffer höchstens so viele wie Paare")
def weighted_hits(
    weights: pl.DataFrame, voters: pl.DataFrame, eligible_column: str
) -> pl.DataFrame:
    """Summe der Gewichte je Wahlbezirk und die gewichtete Quote je Wahlberechtigtem.

    Die Wahlbezirke kommen aus ``voters``: ein Bezirk ohne jedes Gewicht (eine Themenvariante
    trifft ihn nicht) steht mit 0 in der Tabelle, sonst hätte jede Variante andere Zeilen.
    """
    totals = weights.group_by(DISTRICT).agg(pl.col(WEIGHT).sum().alias(WEIGHTED_HITS))
    return (
        voters.select(DISTRICT, eligible_column)
        .join(totals, on=DISTRICT, how="left")
        .with_columns(pl.col(WEIGHTED_HITS).fill_null(0.0))
        .with_columns((pl.col(WEIGHTED_HITS) / pl.col(eligible_column)).alias(WEIGHTED_RATE))
        .select(DISTRICT, WEIGHTED_HITS, WEIGHTED_RATE)
        .sort(DISTRICT)
    )


# --- alle Varianten in einer langen Tabelle -----------------------------------------------------


def _product(frames: Sequence[pl.DataFrame], key: str) -> pl.DataFrame | None:
    """Das Produkt mehrerer Faktorframes über ``key``; ohne Frames gibt es keinen Faktor."""
    if not frames:
        return None
    product = frames[0].select(key, WEIGHT)
    for other in frames[1:]:
        product = (
            product.join(other.select(key, pl.col(WEIGHT).alias("_o")), on=key, how="left")
            .with_columns((pl.col(WEIGHT) * pl.col("_o").fill_null(1.0)).alias(WEIGHT))
            .drop("_o")
        )
    return product


def topic_count(topic_shares: pl.DataFrame) -> int:
    """Die Zahl der Themen aus der Anteilsmatrix; alle Zeilen haben dieselbe Länge."""
    lengths = topic_shares.get_column(SHARES).list.len().unique().to_list()
    if len(lengths) != 1:
        raise EmptyResultError(f"Themenanteile mit verschiedenen Längen: {sorted(lengths)}")
    return int(lengths[0])


def _sorted_by_variant_and_district(result: pl.DataFrame) -> bool:
    keys = list(result.select(VARIANT, DISTRICT).iter_rows())
    return keys == sorted(keys) and len(keys) == len(set(keys))


def _same_districts_everywhere(result: pl.DataFrame) -> bool:
    per_variant = result.group_by(VARIANT).agg(pl.col(DISTRICT).sort())
    districts = {tuple(row) for row in per_variant.get_column(DISTRICT).to_list()}
    return len(districts) == 1


def _unit_and_topics_reproduce_the_count(
    dictionary: pl.DataFrame,
    index: pl.DataFrame,
    paper_types: pl.DataFrame,
    voters: pl.DataFrame,
    eligible_column: str,
    n_documents: int,
    type_rules: Sequence[TypeRules] = (),
    combined: Sequence[str] = (),
    topic_shares: pl.DataFrame | None = None,
    result: pl.DataFrame | None = None,
) -> bool:
    """Einheitsgewichte zählen wie die Arbeit, und die Themen zerlegen genau diese Zählung."""
    assert result is not None
    unit = dict(result.filter(pl.col(VARIANT) == UNIT).select(DISTRICT, WEIGHTED_HITS).iter_rows())
    counted = dict(hits_by_district(dictionary, index).select(DISTRICT, HITS).iter_rows())
    for district, hits in unit.items():
        if hits != float(counted.get(district, 0)):
            return False
    if topic_shares is None:
        return True
    per_topic = (
        result.filter(pl.col(VARIANT).str.starts_with(TOPIC_PREFIX))
        .group_by(DISTRICT)
        .agg(pl.col(WEIGHTED_HITS).sum())
    )
    return all(
        abs(row[WEIGHTED_HITS] - unit[row[DISTRICT]]) <= 1e-9 * max(1.0, unit[row[DISTRICT]])
        for row in per_topic.iter_rows(named=True)
    )


@deal.pre(
    lambda dictionary, index, paper_types, voters, eligible_column, n_documents, type_rules=(), combined=(), topic_shares=None: (
        has_columns(paper_types, DOC, PAPER_TYPE)
        and (topic_shares is None or has_columns(topic_shares, DOC, SHARES))
    )
)
@deal.pre(
    lambda dictionary, index, paper_types, voters, eligible_column, n_documents, type_rules=(), combined=(), topic_shares=None: (
        set(combined) <= {BY_DISTRICTS, BY_IDF, *(rule.name for rule in type_rules)}
    ),
    message="kombiniert multipliziert nur bekannte Faktoren",
)
@deal.post(lambda result: result.columns == [DISTRICT, VARIANT, WEIGHTED_HITS, WEIGHTED_RATE])
@deal.post(lambda result: _sorted_by_variant_and_district(result))
@deal.post(lambda result: all_nonnegative(result, WEIGHTED_HITS, WEIGHTED_RATE))
@deal.post(
    lambda result: _same_districts_everywhere(result),
    message="jede Variante trägt dieselben Wahlbezirke",
)
@deal.ensure(
    _unit_and_topics_reproduce_the_count,
    message="Einheitsgewichte gleich anzahl_treffer, Themen zerlegen sie",
)
@deal.raises(EmptyResultError)
def variants(
    dictionary: pl.DataFrame,
    index: pl.DataFrame,
    paper_types: pl.DataFrame,
    voters: pl.DataFrame,
    eligible_column: str,
    n_documents: int,
    type_rules: Sequence[TypeRules] = (),
    combined: Sequence[str] = (),
    topic_shares: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Alle Gewichtungsvarianten als lange Tabelle: eine Zeile je Wahlbezirk und Variante.

    Varianten sind Zeilen, nicht Spalten: eine neue Variante kommt ohne Schemaänderung hinzu, und
    ``wahlbezirke_auswertung.parquet`` bleibt byteidentisch (Golden Master der Arbeit).
    """
    pairs = document_pairs(dictionary, index)
    terms = term_weights(dictionary, index, n_documents)
    term_factors = {
        BY_DISTRICTS: terms.select(TERM, pl.col(W_DISTRICT).alias(WEIGHT)),
        BY_IDF: terms.select(TERM, pl.col(W_IDF).alias(WEIGHT)),
    }
    type_factors = {
        rule.name: paper_type_weights(paper_types, rule.rules, rule.default) for rule in type_rules
    }
    rows: list[pl.DataFrame] = []

    def add(
        name: str,
        term: pl.DataFrame | None = None,
        paper_type: pl.DataFrame | None = None,
        topic: pl.DataFrame | None = None,
    ) -> None:
        hits = weighted_hits(
            document_weights(pairs, term, paper_type, topic), voters, eligible_column
        )
        rows.append(hits.with_columns(pl.lit(name, dtype=pl.String).alias(VARIANT)))

    add(UNIT)
    add(BY_DISTRICTS, term=term_factors[BY_DISTRICTS])
    add(BY_IDF, term=term_factors[BY_IDF])
    for name, frame in type_factors.items():
        add(name, paper_type=frame)
    if combined:
        add(
            COMBINED,
            term=_product([term_factors[f] for f in combined if f in term_factors], TERM),
            paper_type=_product([type_factors[f] for f in combined if f in type_factors], DOC),
        )
    if topic_shares is not None:
        for topic in range(topic_count(topic_shares)):
            add(
                topic_variant(topic),
                topic=topic_shares.select(
                    DOC, pl.col(SHARES).list.get(topic).cast(pl.Float64).alias(WEIGHT)
                ),
            )
    return (
        pl.concat(rows)
        .select(DISTRICT, VARIANT, WEIGHTED_HITS, WEIGHTED_RATE)
        .sort([VARIANT, DISTRICT])
    )
