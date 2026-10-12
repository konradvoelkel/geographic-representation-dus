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
from georep.contracts import has_columns, one_row_per_document, sorted_unique, unique_keys
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
CONSULTED = "beraten"  # das Kürzel, in dem das Dokument wirklich beraten wurde; null sonst
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
    # Genau die Dokumente des Korpus mit Text, in sortierter Folge: ein Join dazwischen darf
    # weder eine Zeile verlieren noch eine verdoppeln noch die Zuordnung verschieben. Derselbe
    # Vertrag wie bei den anderen Tabellen je Dokument (00-synergien.md, § 5.6).
    return (
        papers.columns == ASSIGNMENT_COLUMNS
        and one_row_per_document(
            papers, corpus.filter(pl.col(TEXT) != "").get_column(DOC).to_list(), DOC
        )
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
@deal.pre(
    lambda corpus, bodies, topics, classify, rules: unique_keys(bodies, DOC),
    message="eine Zeile je Dokument in den Gremien, sonst verlängert der Join den Korpus",
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
    labelled = _labelled(corpus, bodies, rules)
    classes = _trainable(labelled.get_column(CONSULTED), classify)
    if len(classes) < 2:
        return _outputs(
            labelled.with_columns(
                pl.lit(REST).alias(COMMITTEE), pl.lit(None, pl.Float64).alias(PROBABILITY)
            ),
            (),
        )
    # Die Matrix entsteht aus derselben Spalte desselben Frames, aus dem auch die Kürzel kommen:
    # Zeile i der Matrix ist Zeile i von ``labelled``, und kein Join liegt mehr dazwischen.
    matrix, _ = vectorize(labelled.get_column(TEXT).to_list(), topics, rules)
    consulted = labelled.get_column(CONSULTED).to_list()
    training = np.asarray([code in classes for code in consulted])
    model = LogisticRegression(
        C=classify.regularisation,
        max_iter=classify.max_iterations,
        random_state=classify.random_state,
    )
    model.fit(matrix[training], np.asarray(consulted)[training])
    learned = [str(code) for code in model.classes_]
    probabilities = np.asarray(model.predict_proba(matrix), dtype=np.float64)
    best = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    enough = confidence >= classify.min_probability
    return _outputs(
        labelled.with_columns(
            pl.Series(
                COMMITTEE,
                [learned[int(p)] if ok else REST for p, ok in zip(best, enough, strict=True)],
                dtype=pl.String,
            ),
            pl.Series(
                PROBABILITY,
                [float(v) if ok else None for v, ok in zip(confidence, enough, strict=True)],
                dtype=pl.Float64,
            ),
        ),
        tuple(sorted(learned)),
    )


def _labelled(corpus: pl.DataFrame, bodies: pl.DataFrame, rules: TopicRules) -> pl.DataFrame:
    """Ein Frame mit Text und beratenem Ausschuss je Dokument, nach Dokument sortiert.

    Der Join legt die Zeilenfolge nicht fest (``crosswalk.py``, ``prep/context.py``), und alles
    Weitere liest positionell aus diesem Frame: darum wird **nach** dem Join sortiert, und weil
    ``id`` eindeutig ist (Vorbedingung über ``bodies``, Korpus-ID im Korpus), ist die Folge damit
    bestimmt. Ein Dokument, das in den Gremien fehlt, bekommt null und zählt als „ohne
    Ausschussberatung" -- ein linker Join, kein innerer.
    """
    return (
        corpus.filter(pl.col(TEXT) != "")
        .select(DOC, TEXT)
        .join(bodies.select(DOC, BODY_CODE, BODY_KIND), on=DOC, how="left")
        .with_columns(
            pl.when(
                (pl.col(BODY_KIND) == COMMITTEE_KIND)
                & pl.col(BODY_CODE).is_in(sorted(rules.committees))
            )
            .then(pl.col(BODY_CODE))
            .otherwise(None)
            .alias(CONSULTED)
        )
        .select(DOC, TEXT, CONSULTED)
        .sort(DOC)
    )


def _outputs(assigned: pl.DataFrame, classes: tuple[str, ...]) -> Assignment:
    """Beide Ausgaben aus einem Frame: keine Spalte wandert zwischen zwei Frames."""
    return Assignment(
        papers=assigned.select(DOC, COMMITTEE, PROBABILITY),
        table=_table(assigned),
        classes=classes,
    )


def _table(assigned: pl.DataFrame) -> pl.DataFrame:
    """Je zugeordnetem Ausschuss: Dokumente, Anteil, davon ohne Ausschussberatung, Median.

    „Ohne Ausschussberatung" sind die Dokumente, deren Drucksachennummer kein Ausschusskürzel
    trägt: sie waren nur im Rat, in einer Bezirksvertretung oder in einem Beirat. Genau sie
    beantworten Konrads Frage, wie weit die Zuordnung über die beratenen Dokumente hinausreicht.
    """
    total = assigned.height
    return (
        assigned.group_by(COMMITTEE)
        .agg(
            pl.len().cast(pl.Int64).alias(DOCUMENTS),
            pl.col(CONSULTED).is_null().sum().cast(pl.Int64).alias(WITHOUT),
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
