"""Punkt 45: welcher Ausschuss zu einem Dokument passt, überwacht gelernt.

Jedes Dokument trägt sein Gremium aus der Drucksachennummer (Option 05), aber 13 300 der 19 108
waren nur im Rat oder in einer Bezirksvertretung. Ein leichter Klassifikator lernt auf den
Dokumenten, deren Gremium ein Ausschuss ist, und ordnet dann jedem Dokument den Ausschuss zu, der
am besten passt — oder die Restklasse, wenn er sich nicht sicher ist (querschnittliche Vorlagen
wie Haushalt, Stellenplan, Jahresabschluss).

TF-IDF und logistische Regression: die Textdarstellung kommt aus ``analysis.topics.vectorize``,
damit es eine Wahrheit darüber gibt, was ein Wort ist. Die Kette trainiert einmal und sagt vorher;
kreuzvalidiert wird in ``docs/themenmodell-2026-10-messung.py``, nicht hier — eine Messung ist
kein Schritt der Kette (docs/themenmodell-2026-10.md, § 4).

Der zweite von zwei Orten im Paket, die ``sklearn`` importieren (``tests/unit/
test_dependency_boundary.py`` hält die Grenze); ``pipeline.py`` lädt das Modul erst im Schritt.
"""

from __future__ import annotations

from dataclasses import dataclass

import deal
import numpy as np
import polars as pl
from sklearn.linear_model import LogisticRegression

from georep.analysis.topics import TopicRules, vectorize
from georep.analysis.weights import DOC
from georep.contracts import has_columns, sorted_unique
from georep.errors import EmptyResultError
from georep.prep.bodies import BODY as BODY_CODE
from georep.prep.bodies import COMMITTEE as COMMITTEE_KIND
from georep.prep.bodies import KIND as BODY_KIND
from georep.settings import Classify, Topics

TEXT = "text"
COMMITTEE = "ausschuss"  # Kürzel des passenden Ausschusses; "" ist die Restklasse
PROBABILITY = "wahrscheinlichkeit"  # des zugeordneten Ausschusses; null ohne Modell
DOCUMENTS = "dokumente"
SHARE = "anteil"
WITHOUT = "ohne_ausschussberatung"  # davon: nie in einem Ausschuss beraten
MEDIAN = "wahrscheinlichkeit_median"
REST = ""  # die Restklasse trägt kein Kürzel, damit die Spalte ein Kürzel bleibt
ASSIGNMENT_COLUMNS = [DOC, COMMITTEE, PROBABILITY]
TABLE_COLUMNS = [COMMITTEE, DOCUMENTS, SHARE, WITHOUT, MEDIAN]
ASSIGNMENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Assignment:
    """Die zwei Ausgaben: eine Zeile je Dokument und eine je zugeordnetem Ausschuss."""

    papers: pl.DataFrame  # id, ausschuss, wahrscheinlichkeit
    table: pl.DataFrame  # ausschuss, dokumente, anteil, ohne_ausschussberatung, median
    classes: tuple[str, ...] = ()  # die gelernten Klassen, in der Reihenfolge des Modells


def _table_decomposes(result: Assignment) -> bool:
    """Die Tabelle zerlegt die Dokumente ohne Rest, und die Anteile summieren zu 1."""
    table, papers = result.table, result.papers
    total = int(table.get_column(DOCUMENTS).sum())
    shares = float(table.get_column(SHARE).sum())
    return (
        table.columns == TABLE_COLUMNS
        and total == papers.height
        and (papers.height == 0 or abs(shares - 1.0) <= 1e-9)
        and bool((table.get_column(WITHOUT) <= table.get_column(DOCUMENTS)).all())
        and sorted_unique(table, COMMITTEE)
    )


def _assignment_is_whole(
    corpus: pl.DataFrame,
    bodies: pl.DataFrame,
    topics: Topics,
    classify: Classify,
    rules: TopicRules,
    result: Assignment | None = None,
) -> bool:
    """Eine Zeile je Dokument mit Text, bekannte Kürzel, Wahrscheinlichkeit über der Schwelle."""
    assert result is not None
    papers = result.papers
    codes = set(papers.get_column(COMMITTEE).to_list())
    assigned = papers.filter(pl.col(COMMITTEE) != REST)
    return (
        papers.columns == ASSIGNMENT_COLUMNS
        and sorted_unique(papers, DOC)
        and papers.height == corpus.filter(pl.col(TEXT) != "").height
        and codes <= {REST, *result.classes}
        and (
            assigned.is_empty()
            or bool(
                (assigned.get_column(PROBABILITY) >= classify.min_probability).all()
                and (assigned.get_column(PROBABILITY) <= 1.0).all()
            )
        )
        and _table_decomposes(result)
    )


def _trainable(labels: pl.Series, classify: Classify) -> list[str]:
    """Die Klassen mit genug beratenen Dokumenten, in fester Reihenfolge."""
    counted = labels.drop_nulls().value_counts()
    return sorted(
        str(code)
        for code, count in counted.iter_rows()
        if int(count) >= classify.min_documents and str(code)
    )


@deal.pre(
    lambda corpus, bodies, topics, classify, rules: (
        has_columns(corpus, DOC, TEXT) and has_columns(bodies, DOC, BODY_CODE, BODY_KIND)
    )
)
@deal.ensure(_assignment_is_whole, message="eine Zeile je Dokument, Restklasse unter der Schwelle")
@deal.raises(EmptyResultError)
def assign_committees(
    corpus: pl.DataFrame,
    bodies: pl.DataFrame,
    topics: Topics,
    classify: Classify,
    rules: TopicRules,
) -> Assignment:
    """Lernt auf den Ausschussdokumenten und ordnet jedem Dokument den passenden Ausschuss zu.

    Weniger als zwei Klassen über ``classify.min_documents`` sind keine Entscheidung: dann bleibt
    alles in der Restklasse und die Wahrscheinlichkeit leer. Ein dünner Korpus ist eine
    Eigenschaft der Daten, kein Fehler (die Mini-Fixture hat zwei Klassen, Mönchengladbach keine).
    """
    texts = corpus.filter(pl.col(TEXT) != "").select(DOC, TEXT).sort(DOC)
    known = (
        texts.join(bodies.select(DOC, BODY_CODE, BODY_KIND), on=DOC, how="left")
        .with_columns(
            pl.when(
                (pl.col(BODY_KIND) == COMMITTEE_KIND)
                & pl.col(BODY_CODE).is_in(sorted(rules.committees))
            )
            .then(pl.col(BODY_CODE))
            .otherwise(None)
            .alias(COMMITTEE)
        )
        .get_column(COMMITTEE)
    )
    classes = _trainable(known, classify)
    if len(classes) < 2:
        return _without_a_model(texts, known)
    matrix, _ = vectorize(texts.get_column(TEXT).to_list(), topics, rules)
    training = np.asarray([code in classes for code in known.to_list()])
    model = LogisticRegression(
        C=classify.regularisation,
        max_iter=classify.max_iterations,
        random_state=classify.random_state,
    )
    model.fit(matrix[training], np.asarray(known.to_list())[training])
    learned = [str(code) for code in model.classes_]
    probabilities = np.asarray(model.predict_proba(matrix), dtype=np.float64)
    best = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    papers = pl.DataFrame(
        {
            DOC: texts.get_column(DOC),
            COMMITTEE: [
                learned[int(position)] if value >= classify.min_probability else REST
                for position, value in zip(best, confidence, strict=True)
            ],
            PROBABILITY: [
                float(value) if value >= classify.min_probability else None for value in confidence
            ],
        },
        schema={DOC: pl.String, COMMITTEE: pl.String, PROBABILITY: pl.Float64},
    )
    return Assignment(papers=papers, table=_table(papers, known), classes=tuple(sorted(learned)))


def _without_a_model(texts: pl.DataFrame, known: pl.Series) -> Assignment:
    """Alles in die Restklasse: zu wenige Klassen, um überhaupt zu wählen."""
    papers = pl.DataFrame(
        {
            DOC: texts.get_column(DOC),
            COMMITTEE: [REST] * texts.height,
            PROBABILITY: [None] * texts.height,
        },
        schema={DOC: pl.String, COMMITTEE: pl.String, PROBABILITY: pl.Float64},
    )
    return Assignment(papers=papers, table=_table(papers, known), classes=())


def _table(papers: pl.DataFrame, known: pl.Series) -> pl.DataFrame:
    """Je zugeordnetem Ausschuss: Dokumente, Anteil, davon ohne Ausschussberatung, Median.

    „Ohne Ausschussberatung" sind die Dokumente, deren Drucksachennummer kein Ausschusskürzel
    trägt: sie waren nur im Rat, in einer Bezirksvertretung oder in einem Beirat. Genau sie
    beantworten Konrads Frage, wie weit die Zuordnung über die beratenen Dokumente hinausreicht.
    """
    total = papers.height
    return (
        papers.with_columns(known.alias("beraten"))
        .group_by(COMMITTEE)
        .agg(
            pl.len().cast(pl.Int64).alias(DOCUMENTS),
            pl.col("beraten").is_null().sum().cast(pl.Int64).alias(WITHOUT),
            pl.col(PROBABILITY).median().alias(MEDIAN),
        )
        .with_columns((pl.col(DOCUMENTS) / total if total else pl.lit(0.0)).alias(SHARE))
        .select(TABLE_COLUMNS)
        .sort(COMMITTEE)
    )


def summary(assignment: Assignment) -> str:
    """Die Rückgabezeile des Schritts ``committees``."""
    rest = assignment.table.filter(pl.col(COMMITTEE) == REST)
    without = int(rest.get_column(DOCUMENTS).sum())
    assigned = assignment.papers.height - without
    committees = len([c for c in assignment.table.get_column(COMMITTEE).to_list() if c])
    return (
        f"{assignment.papers.height} Dokumente: {assigned} einem von {committees} Ausschüssen "
        f"zugeordnet, {without} in der Restklasse"
    )
