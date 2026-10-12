"""Rechnet die Zahlen von `themenmodell-2026-10.md` nach (Punkt 1 aus `todo.md`).

    uv run python docs/themenmodell-2026-10-messung.py [--stages] [--seeded] [--classifier]

Ohne Schalter läuft alles, rund zwei Minuten auf der Referenz. Liest nur: den Korpus und die
Gremien je Dokument aus `data_root` (also den Stand nach `georep run`), schreibt nichts.

Was hier steht und nicht in einem Test: die Kohärenz der Topwörter (NPMI und UMass), die
Topwörter je Stufe der Stoppwörter, die Treue der gesäten Themen und die Kreuzvalidierung des
Klassifikators. Alles davon hängt am Korpus und am Rechner (BLAS-Threads), taugt also nicht als
Erwartungswert eines Tests; die Tests prüfen Eigenschaften (`tests/unit/test_topics.py`,
`tests/unit/test_committees.py`, `tests/golden/test_pipeline.py`).
"""

from __future__ import annotations

import sys
import time
from collections.abc import Sequence

import numpy as np
import polars as pl
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from georep.analysis.committees import assign_committees
from georep.analysis.topics import (
    TopicRules,
    dominant_topics,
    fit_topics,
    stop_words_for,
    vectorize,
)
from georep.layout import Layout
from georep.settings import Settings, load_settings

FOLDS = 5  # fünf Faltungen; classify.min_documents verlangt darum mindestens fünf Dokumente
STAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("heute (nur die Paketliste)", ()),
    ("+ Fraktionen und Personenmarker", ("fraktionen",)),
    ("+ Gremienkürzel", ("fraktionen", "gremien")),
    ("+ Namen aus Unterschrift und Amt", ("fraktionen", "gremien", "namen")),
)


def coherence(texts: Sequence[str], topics: Sequence[Sequence[str]]) -> tuple[float, float]:
    """NPMI und UMass über die Topwörter, Dokument-Kookkurrenz auf demselben Korpus.

    NPMI je Paar (w_i, w_j): ln(P(w_i, w_j) / (P(w_i)·P(w_j))) / −ln P(w_i, w_j), gemittelt über
    die Paare eines Themas und dann über die Themen; +1 heißt „kommen nur zusammen vor", 0 „sind
    unabhängig". UMass (ln (D(w_i, w_j) + 1) / D(w_i), das stärkere Wort als Bedingung) steht
    daneben, weil es die gängige zweite Zahl ist — es belohnt aber häufige Wörter und fällt
    darum, wenn Stoppwörter die häufigen Formelwörter aus den Labels nehmen.
    """
    vocabulary = sorted({word for words in topics for word in words})
    if not vocabulary:
        return float("nan"), float("nan")
    matrix = CountVectorizer(
        token_pattern=r"[a-zäöüß]{3,}", binary=True, vocabulary=vocabulary
    ).fit_transform(texts)
    counts = (matrix.T @ matrix).toarray().astype(np.float64)
    position = {word: i for i, word in enumerate(vocabulary)}
    documents = float(matrix.shape[0])
    eps = 1e-12
    npmis, umass = [], []
    for words in topics:
        index = [position[word] for word in words]
        pair_npmi, pair_umass = [], []
        for a in range(len(index)):
            for b in range(a + 1, len(index)):
                i, j = index[a], index[b]
                joint = counts[i, j] / documents
                left, right = counts[i, i] / documents, counts[j, j] / documents
                if left <= 0.0 or right <= 0.0:
                    continue
                pair_npmi.append(np.log((joint + eps) / (left * right)) / -np.log(joint + eps))
                pair_umass.append(np.log((counts[i, j] + 1.0) / counts[i, i]))
        if pair_npmi:
            npmis.append(float(np.mean(pair_npmi)))
            umass.append(float(np.mean(pair_umass)))
    return float(np.mean(npmis)), float(np.mean(umass))


def _with_sources(settings: Settings, sources: Sequence[str], seed: str) -> Settings:
    return settings.model_copy(
        update={
            "topics": settings.topics.model_copy(
                update={"stop_sources": list(sources), "seed": seed}
            )
        }
    )


def stages(corpus: pl.DataFrame, bodies: pl.DataFrame, settings: Settings) -> None:
    """Die vier Stufen der Stoppwörter, je mit freier NMF: Topwörter und Kohärenz."""
    texts = corpus.filter(pl.col("text") != "").get_column("text").to_list()
    print(f"\n=== Stufen der Stoppwörter (freie NMF, k = {settings.topics.k}) ===")
    for label, sources in STAGES:
        changed = _with_sources(settings, sources, "none")
        rules = TopicRules.from_settings(changed)
        start = time.perf_counter()
        model = fit_topics(corpus, changed.topics, rules, bodies)
        words = [list(row) for row in model.topics.get_column("woerter").to_list()]
        npmi, umass = coherence(texts, words)
        stop = len(stop_words_for(texts, changed.topics, rules))
        print(
            f"\n--- {label}: NPMI {npmi:+.4f}, UMass {umass:+.3f}, "
            f"{stop} Stoppwörter, {time.perf_counter() - start:.1f} s"
        )
        counted = dict(dominant_topics(model.shares).group_by("thema").agg(pl.len()).iter_rows())
        for number, row in enumerate(words):
            print(f"{number:2d} [{counted.get(number, 0):5d}] {', '.join(row)}")


def seeded(corpus: pl.DataFrame, bodies: pl.DataFrame, settings: Settings) -> None:
    """Das gesäte Modell: Themen mit Namen, Kohärenz und Treue je Ausschuss."""
    texts = corpus.filter(pl.col("text") != "").get_column("text").to_list()
    start = time.perf_counter()
    model = fit_topics(corpus, settings.topics, TopicRules.from_settings(settings), bodies)
    words = [list(row) for row in model.topics.get_column("woerter").to_list()]
    npmi, umass = coherence(texts, words)
    codes = model.topics.get_column("gremium").to_list()
    print(
        f"\n=== Gesäte Themen: NPMI {npmi:+.4f}, UMass {umass:+.3f}, "
        f"{sum(1 for c in codes if c)} von {len(codes)} gesät, {time.perf_counter() - start:.1f} s"
    )
    dominant = dominant_topics(model.shares)
    counted = dict(dominant.group_by("thema").agg(pl.len()).iter_rows())
    for row in model.topics.iter_rows(named=True):
        name = row["gremium"] or "(frei)"
        print(
            f"{row['thema']:2d} {name:7s} [{counted.get(row['thema'], 0):5d}] "
            f"{', '.join(row['woerter'])}"
        )
    # Treue: wie viele Dokumente eines Ausschusses haben sein Thema als stärkstes, und wie rein
    # ist das Thema (Anteil der Dokumente dieses Ausschusses an allen mit diesem Thema).
    # Nach dem Join sortieren: die Zeilenfolge eines Joins ist nicht festgelegt (crosswalk.py).
    # Hier wird nur gefiltert und gezählt, aber die Regel gilt auch für eine Messung.
    joined = dominant.join(bodies.select("id", "gremium", "gremium_art"), on="id", how="left").sort(
        "id"
    )
    print("\nTreue und Reinheit je gesätem Thema:")
    for number, code in enumerate(codes):
        if not code:
            continue
        own = joined.filter(pl.col("gremium") == code)
        theirs = joined.filter(pl.col("thema") == number)
        hit = own.filter(pl.col("thema") == number).height
        pure = theirs.filter(pl.col("gremium") == code).height
        print(
            f"  {code:6s} {hit}/{own.height} = {hit / max(own.height, 1):.2f}, "
            f"Reinheit {pure / max(theirs.height, 1):.2f} ({theirs.height} Dokumente)"
        )


def classifier(corpus: pl.DataFrame, bodies: pl.DataFrame, settings: Settings) -> None:
    """Die Güte des passenden Ausschusses: Kreuzvalidierung und Sicherheit je Gremienart."""
    rules = TopicRules.from_settings(settings)
    # Erst den Join, dann sortieren, dann daraus die Texte **und** die Klassen nehmen: die
    # Zeilenfolge eines Joins ist nicht festgelegt, und Zeile i der Matrix muss zu Klasse i
    # gehören (dieselbe Lehre wie in analysis/committees.py, Review vom 2026-10-13).
    labelled = (
        corpus.filter(pl.col("text") != "")
        .select("id", "text")
        .join(bodies.select("id", "gremium", "gremium_art"), on="id", how="left")
        .with_columns(
            pl.when(
                (pl.col("gremium_art") == "ausschuss")
                & pl.col("gremium").is_in(sorted(settings.bodies.committees))
            )
            .then(pl.col("gremium"))
            .otherwise(None)
            .alias("klasse")
        )
        .select("id", "text", "klasse")
        .sort("id")
    )
    start = time.perf_counter()
    matrix, _ = vectorize(labelled.get_column("text").to_list(), settings.topics, rules)
    labels = labelled.get_column("klasse")
    counted = {
        str(code): int(n)
        for code, n in labels.drop_nulls().value_counts().iter_rows()
        if int(n) >= settings.classify.min_documents
    }
    rows = np.asarray([code in counted for code in labels.to_list()])
    y = np.asarray(labels.to_list())[rows]
    print(
        f"\n=== Klassifikator: {len(counted)} Klassen, {int(rows.sum())} Trainingsdokumente, "
        f"TF-IDF {matrix.shape} in {time.perf_counter() - start:.1f} s"
    )
    model = LogisticRegression(
        C=settings.classify.regularisation,
        max_iter=settings.classify.max_iterations,
        random_state=settings.classify.random_state,
    )
    start = time.perf_counter()
    predicted = cross_val_predict(
        model,
        matrix[rows],
        y,
        cv=StratifiedKFold(FOLDS, shuffle=True, random_state=settings.classify.random_state),
    )
    print(
        f"Kreuzvalidierung ({FOLDS} Faltungen, {time.perf_counter() - start:.1f} s): "
        f"Genauigkeit {float((predicted == y).mean()):.3f}, "
        f"Makro-F1 {float(f1_score(y, predicted, average='macro')):.3f}"
    )
    classes = sorted(counted)
    table = confusion_matrix(y, predicted, labels=classes)
    print("häufigste Verwechslungen:")
    pairs = [
        (int(table[a, b]), classes[a], classes[b])
        for a in range(len(classes))
        for b in range(len(classes))
        if a != b
    ]
    for n, left, right in sorted(pairs, reverse=True)[:10]:
        print(f"  {left} -> {right}: {n}")
    print("je Klasse (n, Trefferquote):")
    for code in classes:
        mine = y == code
        print(
            f"  {code:6s} n={int(mine.sum()):4d} richtig {float((predicted[mine] == code).mean()):.2f}"
        )

    # Die Zuordnung der Kette: wie sicher ist sie je Gremienart, und wie viele fallen unter die
    # Schwelle? Das ist Konrads Frage, ob sich jedes Schriftstück zuordnen lässt.
    found = assign_committees(corpus, bodies, settings.topics, settings.classify, rules)
    joined = found.papers.join(
        bodies.select("id", "gremium", "gremium_art"), on="id", how="left"
    ).sort("id")
    print(f"\nZuordnung der Kette (Schwelle {settings.classify.min_probability:.2f}):")
    for kind in ("ausschuss", "bezirksvertretung", "rat", "beirat"):
        mine = joined.filter(pl.col("gremium_art") == kind)
        rest = mine.filter(pl.col("ausschuss") == "").height
        print(
            f"  {kind:18s} n={mine.height:6d} Restklasse {rest:6d} "
            f"({rest / max(mine.height, 1):.1%})"
        )
    own = joined.filter(pl.col("gremium_art") == "ausschuss")
    print(
        f"  von den Ausschussdokumenten treffen "
        f"{own.filter(pl.col('ausschuss') == pl.col('gremium')).height} von {own.height} "
        f"ihr eigenes Gremium"
    )


def main(argv: Sequence[str]) -> int:
    settings = load_settings()
    layout = Layout.from_settings(settings)
    corpus = pl.read_parquet(layout.corpus, columns=["id", "text"])
    bodies = pl.read_parquet(layout.papers_bodies)
    print(
        f"{corpus.height} Dokumente, {corpus.filter(pl.col('text') != '').height} mit Text; "
        f"Gremien aus {layout.papers_bodies}"
    )
    wanted = set(argv) & {"--stages", "--seeded", "--classifier"}
    if not wanted or "--stages" in wanted:
        stages(corpus, bodies, settings)
    if not wanted or "--seeded" in wanted:
        seeded(corpus, bodies, settings)
    if not wanted or "--classifier" in wanted:
        classifier(corpus, bodies, settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
