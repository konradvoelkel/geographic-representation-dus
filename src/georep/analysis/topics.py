"""Themen je Dokument: TF-IDF und NMF über die Texte des Korpus.

Der einzige Ort im Paket, der ``sklearn`` importiert (docs/decisions.md, Punkt „scikit-learn für
das Themenmodell"; ``tests/unit/test_dependency_boundary.py`` hält die Grenze). Der Import kostet
rund 0,4 s, darum lädt ``pipeline.py`` das Modul erst im Schritt ``topics``.

Das Modell verteilt jedes Dokument mit Text auf ``k`` Themen: die Zeilen von ``W`` sind nach L1
normiert und damit Anteile, die je Dokument zu 1 summieren. Das ist die Eigenschaft, aus der die
Themenvarianten in ``analysis.weights`` die Einheitszählung genau zerlegen. Ein Thema trägt als
Beschriftung seine stärksten Wörter; das beschreibt es, es benennt es nicht, und die Nummern
gelten nur für diesen Datenstand.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

import deal
import numpy as np
import polars as pl
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

from georep.analysis.weights import DOC, SHARES
from georep.contracts import has_columns, lists_sorted_unique, sorted_unique
from georep.errors import EmptyResultError
from georep.settings import Topics

TOPIC = "thema"
WORDS = "woerter"
DOCUMENTS = "dokumente"
WEIGHT_SUM = "gewicht_summe"
SHARE = "anteil"
TEXT = "text"
# Wörter aus Buchstaben, mindestens drei; Zahlen und Drucksachennummern sind keine Themen.
TOKEN_PATTERN = r"[a-zäöüß]{3,}"


@dataclass(frozen=True)
class TopicModel:
    """Die zwei Ausgaben des Modells: Anteile je Dokument und eine Zeile je Thema."""

    shares: pl.DataFrame  # id, anteile (Liste der Länge k, Summe 1)
    topics: pl.DataFrame  # thema, woerter, dokumente, gewicht_summe


@deal.post(
    lambda result: all(word and word == word.strip().lower() for word in result),
    message="Stoppwörter sind kleingeschrieben, getrimmt und nicht leer",
)
@deal.raises(EmptyResultError)
def load_stop_words(name: str) -> frozenset[str]:
    """Die Paketdatei ``stopwords_<name>.txt``; ``name = ""`` heißt: keine Stoppwörter.

    Eine Zeile ein Wort, ``#`` kommentiert, leere Zeilen zählen nicht (wie ``defaults.toml`` über
    ``importlib.resources``, damit die Liste im Wheel liegt).
    """
    if not name:
        return frozenset()
    source = resources.files("georep.analysis") / f"stopwords_{name}.txt"
    if not source.is_file():
        raise EmptyResultError(
            f"Keine Stoppwortliste für {name!r}: {source.name} liegt nicht im Paket."
        )
    words = frozenset(
        line.strip()
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )
    if not words:
        raise EmptyResultError(f"Die Stoppwortliste {source.name} enthält kein Wort.")
    return words


@deal.pre(lambda shares, decimals=4: has_columns(shares, DOC, SHARES) and decimals >= 0)
@deal.post(lambda result: result.columns == [DOC, TOPIC, SHARE])
@deal.post(lambda result: sorted_unique(result, DOC))
def dominant_topics(shares: pl.DataFrame, decimals: int = 4) -> pl.DataFrame:
    """Je Dokument das stärkste Thema und dessen Anteil, gerundet: die veröffentlichte Tabelle.

    Die volle Anteilsmatrix bleibt ein Zwischenstand (``interim/themen_anteile.parquet``); als CSV
    wären 19 033 × 20 Zahlen rund 4 MB. Bei Gleichstand gewinnt das kleinere Thema
    (``list.arg_max`` nimmt das erste), damit zwei Läufe dieselbe Tabelle schreiben.
    """
    return shares.select(
        DOC,
        pl.col(SHARES).list.arg_max().cast(pl.Int64).alias(TOPIC),
        pl.col(SHARES).list.max().round(decimals).alias(SHARE),
    ).sort(DOC)


def _l1_rows(matrix: np.ndarray, k: int) -> np.ndarray:
    """Zeilen auf Summe 1; eine Zeile ohne Masse wird gleichverteilt, damit die Zerlegung hält."""
    dense = np.asarray(matrix, dtype=np.float64)
    sums = dense.sum(axis=1, keepdims=True)
    return np.where(sums > 0.0, dense / np.where(sums > 0.0, sums, 1.0), 1.0 / k)


def _model_is_whole(
    corpus: pl.DataFrame, settings: Topics, result: TopicModel | None = None
) -> bool:
    """Genau ``k`` Themen, Zeilensummen 1, jedes Dokument mit Text einmal, Labels vollständig."""
    assert result is not None
    sums = result.shares.get_column(SHARES).list.sum()
    documents = corpus.filter(pl.col(TEXT) != "").height
    return (
        result.topics.height == settings.k
        and result.shares.height == documents
        and bool(((sums - 1.0).abs() <= 1e-9).all())
        and bool((result.shares.get_column(SHARES).list.len() == settings.k).all())
        and result.topics.get_column(TOPIC).to_list() == list(range(settings.k))
        and bool((result.topics.get_column(WORDS).list.len() <= settings.top_words).all())
        and lists_sorted_unique(result.topics.select(pl.col(WORDS).list.sort()), WORDS)
        and int(result.topics.get_column(DOCUMENTS).sum()) == documents
    )


@deal.pre(lambda corpus, settings: has_columns(corpus, DOC, TEXT))
@deal.pre(lambda corpus, settings: settings.k >= 1, message="ohne Thema gibt es nichts zu rechnen")
@deal.ensure(_model_is_whole, message="k Themen, Anteile je Dokument mit Summe 1, Labels")
@deal.raises(EmptyResultError)
def fit_topics(corpus: pl.DataFrame, settings: Topics) -> TopicModel:
    """TF-IDF über die Texte, dann NMF mit ``k`` Themen; die Anteile sind L1-normierte Zeilen von W.

    NMF statt LDA: auf den 19 033 Texten der Referenz 3,8 s gegen 47 s, und LDA lieferte Themen
    aus Funktionswörtern (gemessen 2026-10-11, docs/decisions.md). ``init="nndsvda"`` ist
    deterministisch, zwei Läufe im selben Prozess liefern dieselben Zahlen.
    """
    texts = corpus.filter(pl.col(TEXT) != "").select(DOC, TEXT).sort(DOC)
    if texts.height < settings.k:
        raise EmptyResultError(
            f"{settings.k} Themen brauchen mindestens so viele Dokumente mit Text, "
            f"{texts.height} vorhanden."
        )
    stop_words = sorted(load_stop_words(settings.stop_words))
    vectorizer = TfidfVectorizer(
        token_pattern=TOKEN_PATTERN,
        min_df=settings.min_df,
        max_df=settings.max_df,
        max_features=settings.max_features,
        sublinear_tf=True,
        stop_words=stop_words or None,
        # Float64, nicht Float32: mit Float32 unterläuft das Residuum in sklearns eigener
        # Fehlerformel bei einer fast exakten Zerlegung unter null, die Wurzel davon ist nan, und
        # damit fällt die Abbruchprüfung von ``tol`` still aus (gemessen 2026-10-12 auf der
        # synthetischen Fixture). Auf der Referenz liefern beide dieselben 120 Iterationen und
        # denselben Fehler; Float64 kostet dort 1,4 s mehr. Das ist die Ruhe wert.
        dtype=np.float64,
    )
    try:
        counts = vectorizer.fit_transform(texts.get_column(TEXT).to_list())
    except ValueError as error:
        # „after pruning, no terms remain": min_df und max_df haben das Vokabular geleert.
        raise EmptyResultError(
            f"Kein Wort überlebt min_df={settings.min_df} und max_df={settings.max_df} "
            f"auf {texts.height} Dokumenten: {error}"
        ) from error
    if counts.shape[1] < settings.k:
        # nndsvda zerlegt in k Faktoren und braucht dafür k <= min(Dokumente, Wörter); sonst wirft
        # sklearn ein ValueError. Zu wenige Wörter sind eine Eigenschaft der Daten, kein
        # Programmierfehler: ein Domänenfehler mit dem Grund, nicht eine Vertragsverletzung.
        raise EmptyResultError(
            f"{settings.k} Themen brauchen mindestens so viele Wörter im Vokabular, "
            f"{counts.shape[1]} überleben min_df={settings.min_df} und max_df={settings.max_df} "
            f"auf {texts.height} Dokumenten."
        )
    model = NMF(
        n_components=settings.k,
        init="nndsvda",
        solver="cd",
        max_iter=settings.max_iter,
        tol=settings.tol,
        random_state=settings.random_state,
    )
    shares = pl.DataFrame(
        {
            DOC: texts.get_column(DOC),
            SHARES: _l1_rows(model.fit_transform(counts), settings.k).tolist(),
        },
        schema={DOC: pl.String, SHARES: pl.List(pl.Float64)},
    )
    return TopicModel(shares=shares, topics=_topic_rows(model, vectorizer, shares, settings))


def _topic_rows(
    model: NMF, vectorizer: TfidfVectorizer, shares: pl.DataFrame, settings: Topics
) -> pl.DataFrame:
    """Eine Zeile je Thema: stärkste Wörter, dominierte Dokumente, Summe der Anteile."""
    vocabulary = vectorizer.get_feature_names_out()
    words = [
        [
            str(vocabulary[position])
            # stable, damit zwei gleich starke Wörter immer in derselben Folge stehen
            for position in np.argsort(-component, kind="stable")[: settings.top_words]
        ]
        for component in np.asarray(model.components_, dtype=np.float64)
    ]
    counted = dict(
        dominant_topics(shares)
        .group_by(TOPIC)
        .agg(pl.len().cast(pl.Int64).alias(DOCUMENTS))
        .iter_rows()
    )
    totals = (
        shares.select(pl.col(SHARES).list.get(topic).sum()).item() for topic in range(settings.k)
    )
    return pl.DataFrame(
        {
            TOPIC: list(range(settings.k)),
            WORDS: words,
            DOCUMENTS: [int(counted.get(topic, 0)) for topic in range(settings.k)],
            WEIGHT_SUM: list(totals),
        },
        schema={
            TOPIC: pl.Int64,
            WORDS: pl.List(pl.String),
            DOCUMENTS: pl.Int64,
            WEIGHT_SUM: pl.Float64,
        },
    )
