"""Themen je Dokument: TF-IDF und NMF über die Texte des Korpus.

Der einzige Ort im Paket, der ``sklearn`` importiert (docs/decisions.md, Punkt „scikit-learn für
das Themenmodell"; ``tests/unit/test_dependency_boundary.py`` hält die Grenze). Der Import kostet
rund 0,4 s, darum lädt ``pipeline.py`` das Modul erst im Schritt ``topics``.

Das Modell verteilt jedes Dokument mit Text auf ``k`` Themen: die Zeilen von ``W`` sind nach L1
normiert und damit Anteile, die je Dokument zu 1 summieren. Das ist die Eigenschaft, aus der die
Themenvarianten in ``analysis.weights`` die Einheitszählung genau zerlegen.

Punkt 45 (docs/themenmodell-2026-10.md) macht aus den Themen etwas Lesbares. Zwei Änderungen:

* **Stoppwörter aus dem Profil und aus dem Korpus.** Fraktions- und Personennamen prägten die
  Themen (Thema 3 „antrag, gez, fraktion, cdu, grünen"). ``TopicRules`` leitet sie aus
  ``[originators]`` und ``[bodies]`` ab — dieselben Muster, die Option 04 und 05 schon pflegen —
  und erkennt Personennamen daran, dass ein Wort fast nur in einem Namensfenster steht (hinter
  einer Unterschrift oder einer Amtsbezeichnung).
* **Gesäte Themen je Ausschuss.** Mit ``topics.seed = "committees"`` bekommt jeder Ausschuss mit
  genug beratenen Dokumenten ein Thema, dessen Wortmatrix fest aus seinen unterscheidenden Wörtern
  gebaut ist (Log-Odds mit Dirichlet-Prior gegen die anderen Ausschüsse); die ``free`` übrigen
  Themen rechnen freie NMF auf dem Rest. Ein Thema trägt damit das Kürzel seines Gremiums (Spalte
  ``gremium``), und die Seite nennt den Namen aus dem Profil. Ohne Saat bleibt alles wie in Option
  06: die Wörter beschreiben das Thema, sie benennen es nicht, und die Nummern gelten nur für
  diesen Datenstand.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib import resources

import deal
import numpy as np
import polars as pl
from polars.datatypes import DataTypeClass
from scipy.sparse import csr_matrix
from sklearn.decomposition import NMF, non_negative_factorization
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

from georep.analysis.weights import DOC, SHARES
from georep.contracts import has_columns, lists_sorted_unique, sorted_unique
from georep.errors import EmptyResultError
from georep.prep.bodies import BODY as BODY_CODE
from georep.prep.bodies import COMMITTEE
from georep.prep.bodies import KIND as BODY_KIND
from georep.settings import Bodies, Originators, Settings, Topics

TOPIC = "thema"
WORDS = "woerter"
DOCUMENTS = "dokumente"
WEIGHT_SUM = "gewicht_summe"
SHARE = "anteil"
TEXT = "text"
BODY = "gremium"  # Kürzel des gesäten Ausschusses; null bei einem freien Thema
TOPIC_COLUMNS = [TOPIC, BODY, WORDS, DOCUMENTS, WEIGHT_SUM]
TOPIC_SCHEMA: dict[str, pl.DataType | DataTypeClass] = {
    TOPIC: pl.Int64,
    BODY: pl.String,
    WORDS: pl.List(pl.String),
    DOCUMENTS: pl.Int64,
    WEIGHT_SUM: pl.Float64,
}
# Wörter aus Buchstaben, mindestens drei; Zahlen und Drucksachennummern sind keine Themen.
TOKEN_PATTERN = r"[a-zäöüß]{3,}"
_WORD = re.compile(TOKEN_PATTERN)
# Zeilen je Block, wenn der Rest der gesäten Zerlegung gerechnet wird: 512 × 20 000 Float64 sind
# 80 MB, und die dichte Matrix (19 033 × 20 000) wären 3 GB.
_ROWS_PER_BLOCK = 512


@dataclass(frozen=True)
class TopicModel:
    """Die zwei Ausgaben des Modells: Anteile je Dokument und eine Zeile je Thema."""

    shares: pl.DataFrame  # id, anteile (Liste der Länge k, Summe 1)
    topics: pl.DataFrame  # thema, gremium, woerter, dokumente, gewicht_summe


@dataclass(frozen=True)
class TopicRules:
    """Was das Modell über ``[topics]`` hinaus braucht, einmal aus den Settings zusammengetragen.

    Dieselbe Rolle wie ``prep.bodies.BodyRules``: ``from_settings`` ist die einzige Brücke zwischen
    den Settings und dem Rechnen, und die Vorgaben hier sind der Stand von Option 06 (keine Quelle,
    keine Saat), damit ein Aufruf ohne Regeln rechnet wie bisher.
    """

    stop_words: frozenset[str] = frozenset()  # aus dem Profil abgeleitet, ohne ``stop_keep``
    keep: frozenset[str] = frozenset()  # Sachwörter, die eine Quelle sonst mitnähme
    name_markers: tuple[str, ...] = ()  # Unterschrift, Amtsbezeichnung (stadtneutral, deutsch)
    person_patterns: tuple[str, ...] = ()  # Personenmarker aus [originators], als Regex
    name_window: int = 60
    name_min_documents: int = 5
    name_share: float = 0.8
    head_chars: int = 600  # so weit reicht der Textkopf, in dem die Personenmarker stehen
    with_names: bool = False  # Quelle „namen" an
    seed: str = "none"
    free: int = 0
    seed_words: int = 30
    seed_min_documents: int = 10
    seed_prior: float = 1000.0
    committees: frozenset[str] = field(default_factory=frozenset)  # Kürzel aus [bodies.committees]

    @classmethod
    def from_settings(cls, settings: Settings) -> TopicRules:
        topics = settings.topics
        keep = frozenset(word.lower() for word in topics.stop_keep)
        derived = profile_stop_words(settings.originators, settings.bodies, topics.stop_sources)
        return cls(
            stop_words=frozenset(derived - keep),
            keep=keep,
            name_markers=tuple(marker.lower() for marker in topics.name_markers),
            person_patterns=tuple(settings.originators.person_markers),
            name_window=topics.name_window,
            name_min_documents=topics.name_min_documents,
            name_share=topics.name_share,
            head_chars=settings.originators.text_head_chars,
            with_names="namen" in topics.stop_sources,
            seed=topics.seed,
            free=topics.free,
            seed_words=topics.seed_words,
            seed_min_documents=topics.seed_min_documents,
            seed_prior=topics.seed_prior,
            committees=frozenset(settings.bodies.committees),
        )


def _letters(*values: str) -> set[str]:
    """Die Buchstabenfolgen eines Namens oder Musters, kleingeschrieben.

    Aus einem Regex kommen dabei auch Bruchstücke (``frak`` und ``ion`` aus ``frak\\w{0,2}ion``).
    Das ist harmlos: ein Bruchstück bildet allein kein Token und steht darum in keinem Dokument.
    """
    return {word for value in values for word in _WORD.findall(value.lower())}


def profile_stop_words(
    originators: Originators, bodies: Bodies, sources: Sequence[str]
) -> frozenset[str]:
    """Stoppwörter aus dem Profil: Parteien, Fraktionen, Personenmarker, Gremienkürzel.

    Keine zweite Liste: die Namen und Muster pflegen schon Option 04 (``[originators]``) und
    Option 05 (``[bodies]``). Von den Gremien kommen nur die **Kürzel**, nicht die Namen — ein
    „Verkehrsausschuss" ist ein Themenwort, ein „OVA" ist es nicht.
    """
    words: set[str] = set()
    if "fraktionen" in sources:
        for party in (*originators.parties, *originators.groups):
            words |= _letters(party.key, party.label, party.short, *party.patterns)
        words |= _letters(
            *originators.fraction_markers,
            *originators.joint_markers,
            *originators.person_markers,
        )
    if "gremien" in sources:
        words |= _letters(
            bodies.district_body, *bodies.council, *bodies.committees, *bodies.advisory
        )
    return frozenset(words)


def _name_windows(text: str, rules: TopicRules, person: re.Pattern[str] | None) -> str:
    """Die Textstücke hinter einem Namensmarker; das letzte, abgeschnittene Wort fällt weg."""
    pieces: list[str] = []
    for marker in rules.name_markers:
        position = 0
        while (found := text.find(marker, position)) >= 0:
            position = found + len(marker)
            pieces.append(text[position : position + rules.name_window])
    if person is not None:
        head = text[: rules.head_chars]
        for match in person.finditer(head):
            pieces.append(head[match.end() : match.end() + rules.name_window])
    return " ".join(piece.rsplit(None, 1)[0] for piece in pieces if " " in piece.strip())


def name_stop_words(texts: Sequence[str], rules: TopicRules) -> frozenset[str]:
    """Wörter, die fast nur in einem Namensfenster stehen: Personennamen und Grußformeln.

    Zwei Durchgänge: der erste zählt die Dokumente je Wort in den Fenstern, der zweite dieselben
    Wörter im ganzen Text. Liegt der Anteil über ``name_share``, kommt das Wort kaum anders vor als
    hinter einer Unterschrift oder einem Amt und ist damit ein Name. Ein Sachwort („straße") steht
    überall und bleibt. Gemessen am 2026-10-12: 254 Wörter, 1,8 s über 19 033 Texte.
    """
    if not rules.with_names or not rules.name_markers:
        return frozenset()
    person = re.compile("|".join(rules.person_patterns)) if rules.person_patterns else None
    windows = [_name_windows(text, rules, person) for text in texts]
    if not any(windows):
        return frozenset()
    counter = CountVectorizer(
        token_pattern=TOKEN_PATTERN, binary=True, min_df=rules.name_min_documents
    )
    try:
        in_windows = counter.fit_transform(windows)
    except ValueError:
        # „no terms remain": zu wenige Fenster für ``name_min_documents``. Kein Name, kein Fehler.
        return frozenset()
    vocabulary = [str(word) for word in counter.get_feature_names_out()]
    window_documents = np.asarray(in_windows.sum(axis=0)).ravel()
    everywhere = np.asarray(
        CountVectorizer(token_pattern=TOKEN_PATTERN, binary=True, vocabulary=vocabulary)
        .fit_transform(texts)
        .sum(axis=0)
    ).ravel()
    shares = window_documents / np.maximum(everywhere, 1)
    return frozenset(
        word for word, share in zip(vocabulary, shares, strict=True) if share >= rules.name_share
    )


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


def _codes_are_unique_and_first(frame: pl.DataFrame) -> bool:
    """Jeder Ausschuss hat höchstens ein Thema, und die gesäten Themen stehen vorn."""
    codes = frame.sort(TOPIC).get_column(BODY).to_list()
    named = [code for code in codes if code is not None]
    return len(named) == len(set(named)) and codes[: len(named)] == named


def _model_is_whole(
    corpus: pl.DataFrame,
    settings: Topics,
    rules: TopicRules | None = None,
    bodies: pl.DataFrame | None = None,
    result: TopicModel | None = None,
) -> bool:
    """Genau ``k`` Themen, Zeilensummen 1, jedes Dokument mit Text einmal, Labels vollständig."""
    assert result is not None
    sums = result.shares.get_column(SHARES).list.sum()
    documents = corpus.filter(pl.col(TEXT) != "").height
    return (
        result.topics.height == settings.k
        and result.topics.columns == TOPIC_COLUMNS
        and result.shares.height == documents
        and bool(((sums - 1.0).abs() <= 1e-9).all())
        and bool((result.shares.get_column(SHARES).list.len() == settings.k).all())
        and result.topics.get_column(TOPIC).to_list() == list(range(settings.k))
        and bool((result.topics.get_column(WORDS).list.len() <= settings.top_words).all())
        and lists_sorted_unique(result.topics.select(pl.col(WORDS).list.sort()), WORDS)
        and int(result.topics.get_column(DOCUMENTS).sum()) == documents
        and _codes_are_unique_and_first(result.topics)
    )


def _committee_rows(
    texts: pl.DataFrame, bodies: pl.DataFrame | None, settings: Topics, rules: TopicRules
) -> list[tuple[str, np.ndarray]]:
    """Die Ausschüsse, die ein eigenes Thema bekommen, je mit den Zeilen ihrer Dokumente.

    Reihenfolge: nach Zahl der beratenen Dokumente absteigend, bei Gleichstand nach Kürzel — damit
    zwei Läufe dieselben Themen in derselben Folge säen. Es werden höchstens ``k - free`` viele.
    """
    seats = settings.k - rules.free
    if rules.seed != "committees" or bodies is None or seats <= 0 or not rules.committees:
        return []
    joined = (
        texts.with_row_index("zeile")
        .join(bodies.select(DOC, BODY_CODE, BODY_KIND), on=DOC, how="inner")
        .filter(
            (pl.col(BODY_KIND) == COMMITTEE) & pl.col(BODY_CODE).is_in(sorted(rules.committees))
        )
    )
    grouped = {
        str(code): np.asarray(sorted(rows), dtype=np.int64)
        for code, rows in joined.group_by(BODY_CODE).agg(pl.col("zeile")).iter_rows()
    }
    chosen = sorted(grouped, key=lambda code: (-len(grouped[code]), code))
    return [
        (code, grouped[code]) for code in chosen if len(grouped[code]) >= rules.seed_min_documents
    ][:seats]


def _seed_words(
    counts: csr_matrix,
    vocabulary: Sequence[str],
    groups: list[tuple[str, np.ndarray]],
    rules: TopicRules,
) -> dict[str, list[int]]:
    """Die unterscheidenden Wörter je Ausschuss: Log-Odds mit Dirichlet-Prior (Monroe u. a. 2008).

    Verglichen wird ein Ausschuss gegen alle anderen Ausschüsse, nicht gegen den ganzen Korpus:
    gesucht ist, was *diesen* Ausschuss von den übrigen trennt, nicht was eine Ausschussvorlage von
    einem Antrag trennt. Der Prior kommt aus den Wortzahlen des ganzen Korpus, auf
    ``seed_prior`` Pseudo-Token gebracht; er dämpft Wörter, die nur ein paar Mal vorkommen.
    """
    total = np.asarray(counts.sum(axis=0)).ravel().astype(np.float64)
    alpha = total / max(total.sum(), 1.0) * rules.seed_prior
    prior = alpha.sum()
    committee_rows = np.concatenate([rows for _, rows in groups])
    everywhere = np.asarray(counts[committee_rows].sum(axis=0)).ravel().astype(np.float64)
    seeds: dict[str, list[int]] = {}
    for code, rows in groups:
        inside = np.asarray(counts[rows].sum(axis=0)).ravel().astype(np.float64)
        outside = everywhere - inside
        n_in, n_out = inside.sum(), outside.sum()
        delta = np.log((inside + alpha) / np.maximum(n_in + prior - inside - alpha, 1e-9)) - np.log(
            (outside + alpha) / np.maximum(n_out + prior - outside - alpha, 1e-9)
        )
        sigma = np.sqrt(1.0 / (inside + alpha) + 1.0 / (outside + alpha))
        # Ein Wort, das dieser Ausschuss nie benutzt, ist kein Saatwort -- auch wenn sein z
        # positiv ausfällt: steht es in keinem Ausschuss, sind beide Zahlen 0, und allein der
        # kleinere Nenner des kleineren Ausschusses hebt es nach oben (gemessen 2026-10-13 an der
        # synthetischen Fixture: „haushalt" aus dem einen Ratsdokument wurde Saat aller drei).
        score = np.where(inside > 0.0, delta / sigma, -np.inf)
        order = np.argsort(-score, kind="stable")[: rules.seed_words]
        seeds[code] = [int(position) for position in order if np.isfinite(score[position])]
    assert len(vocabulary) == counts.shape[1]
    return seeds


def _seed_profile(
    matrix: csr_matrix,
    counts: csr_matrix,
    vocabulary: Sequence[str],
    groups: list[tuple[str, np.ndarray]],
    rules: TopicRules,
) -> np.ndarray:
    """Die feste Wortmatrix der gesäten Themen: Saatwörter mit dem Gewicht ihres Ausschusses.

    Das Gewicht ist der TF-IDF-Mittelwert des Wortes in den Dokumenten des Ausschusses, auf die
    Saatwörter beschränkt und je Zeile auf Länge 1 gebracht. Mit binären Gewichten (jedes Saatwort
    gleich) fiel die Kohärenz von +0,364 auf +0,217, weil die Labels dann alphabetisch ausfallen
    (gemessen 2026-10-12 auf der Referenz).
    """
    seeds = _seed_words(counts, vocabulary, groups, rules)
    profile = np.zeros((len(groups), matrix.shape[1]), dtype=np.float64)
    for row, (code, rows) in enumerate(groups):
        centroid = np.asarray(matrix[rows].mean(axis=0)).ravel()
        for position in seeds[code]:
            # Jedes Saatwort steht in den Dokumenten seines Ausschusses (``_seed_words`` lässt
            # nur solche durch), also ist sein Zentroid positiv und es gibt keinen Ersatzwert.
            profile[row, position] = centroid[position]
        length = float(np.linalg.norm(profile[row]))
        if length > 0.0:
            profile[row] /= length
        else:
            # Ein Ausschuss ohne ein einziges eigenes Wort hätte ein Thema ohne Wörter; das kann
            # erst ab ``seed_min_documents`` Dokumenten passieren, wenn alle dasselbe sagen wie
            # die anderen. Gleichverteilt über seine Dokumente ist dann die ehrlichste Zeile.
            profile[row] = centroid / max(float(np.linalg.norm(centroid)), 1e-12)
    return profile


def _residual(matrix: csr_matrix, weights: np.ndarray, profile: np.ndarray) -> csr_matrix:
    """``max(X − W·H, 0)``, nur auf dem Träger von X gerechnet.

    Außerhalb des Trägers ist ``max(0 − W·H, 0) = 0``, weil beide Faktoren nicht negativ sind: das
    Ergebnis ist also exakt und bleibt sparse. Blockweise, weil die dichte Differenz 3 GB wäre.
    """
    data = np.empty_like(matrix.data)
    for begin in range(0, matrix.shape[0], _ROWS_PER_BLOCK):
        end = min(begin + _ROWS_PER_BLOCK, matrix.shape[0])
        low, high = int(matrix.indptr[begin]), int(matrix.indptr[end])
        fitted = weights[begin:end] @ profile
        rows = np.repeat(np.arange(end - begin), np.diff(matrix.indptr[begin : end + 1]))
        data[low:high] = np.maximum(
            matrix.data[low:high] - fitted[rows, matrix.indices[low:high]], 0.0
        )
    rest = csr_matrix((data, matrix.indices.copy(), matrix.indptr.copy()), shape=matrix.shape)
    rest.eliminate_zeros()
    return rest


def _fit_free(
    matrix: csr_matrix, settings: Topics, components: int
) -> tuple[np.ndarray, np.ndarray]:
    """Freie NMF: ``init="nndsvda"`` ist deterministisch, zwei Läufe im Prozess sind gleich."""
    model = NMF(
        n_components=components,
        init="nndsvda",
        solver="cd",
        max_iter=settings.max_iter,
        tol=settings.tol,
        random_state=settings.random_state,
    )
    return model.fit_transform(matrix), np.asarray(model.components_, dtype=np.float64)


def _fit_seeded(
    matrix: csr_matrix,
    counts: csr_matrix,
    vocabulary: Sequence[str],
    groups: list[tuple[str, np.ndarray]],
    settings: Topics,
    rules: TopicRules,
) -> tuple[np.ndarray, np.ndarray]:
    """Gesäte Themen mit fester Wortmatrix, freie Themen auf dem Rest.

    ``update_H=False`` ist der Unterschied zu einer bloßen Initialisierung: mit ``init="custom"``
    und freiem H wanderte das Modell binnen 58 Iterationen von der Saat weg und nur 0 bis 23 % der
    Dokumente eines Ausschusses hatten noch sein Thema (gemessen 2026-10-12). Festgehalten sind es
    71 bis 99 %, und die Themen heißen nach ihrem Ausschuss.
    """
    profile = _seed_profile(matrix, counts, vocabulary, groups, rules)
    seeded, _, _ = non_negative_factorization(
        matrix,
        H=profile,
        n_components=len(groups),
        init="custom",
        update_H=False,
        solver="cd",
        max_iter=settings.max_iter,
        tol=settings.tol,
        random_state=settings.random_state,
    )
    free = settings.k - len(groups)
    if free <= 0:
        return np.asarray(seeded, dtype=np.float64), profile
    weights, components = _fit_free(_residual(matrix, seeded, profile), settings, free)
    return np.hstack([np.asarray(seeded, dtype=np.float64), weights]), np.vstack(
        [profile, components]
    )


def stop_words_for(documents: Sequence[str], settings: Topics, rules: TopicRules) -> frozenset[str]:
    """Die Stoppwörter eines Laufs: Paketliste, Profil, Namen aus dem Korpus, minus ``stop_keep``."""
    return (
        frozenset(load_stop_words(settings.stop_words))
        | rules.stop_words
        | name_stop_words(documents, rules)
    ) - rules.keep


@deal.raises(EmptyResultError)
def vectorize(
    documents: Sequence[str], settings: Topics, rules: TopicRules
) -> tuple[csr_matrix, list[str]]:
    """TF-IDF über die Texte: die eine Wahrheit darüber, was hier ein Wort ist.

    Das Themenmodell und der Klassifikator des passenden Ausschusses (``analysis.committees``,
    Punkt 45) lesen beide hier; ``[classify]`` hat darum keine eigenen Textparameter.
    """
    vectorizer = TfidfVectorizer(
        token_pattern=TOKEN_PATTERN,
        min_df=settings.min_df,
        max_df=settings.max_df,
        max_features=settings.max_features,
        sublinear_tf=True,
        stop_words=sorted(stop_words_for(documents, settings, rules)) or None,
        # Float64, nicht Float32: mit Float32 unterläuft das Residuum in sklearns eigener
        # Fehlerformel bei einer fast exakten Zerlegung unter null, die Wurzel davon ist nan, und
        # damit fällt die Abbruchprüfung von ``tol`` still aus (gemessen 2026-10-12 auf der
        # synthetischen Fixture). Auf der Referenz liefern beide dieselben 120 Iterationen und
        # denselben Fehler; Float64 kostet dort 1,4 s mehr. Das ist die Ruhe wert.
        dtype=np.float64,
    )
    try:
        matrix = vectorizer.fit_transform(documents).tocsr()
    except ValueError as error:
        # „after pruning, no terms remain": min_df und max_df haben das Vokabular geleert.
        raise EmptyResultError(
            f"Kein Wort überlebt min_df={settings.min_df} und max_df={settings.max_df} "
            f"auf {len(documents)} Dokumenten: {error}"
        ) from error
    return matrix, [str(word) for word in vectorizer.get_feature_names_out()]


@deal.pre(lambda corpus, settings, rules=None, bodies=None: has_columns(corpus, DOC, TEXT))
@deal.pre(
    lambda corpus, settings, rules=None, bodies=None: settings.k >= 1,
    message="ohne Thema gibt es nichts zu rechnen",
)
@deal.ensure(_model_is_whole, message="k Themen, Anteile je Dokument mit Summe 1, Labels")
@deal.raises(EmptyResultError)
def fit_topics(
    corpus: pl.DataFrame,
    settings: Topics,
    rules: TopicRules | None = None,
    bodies: pl.DataFrame | None = None,
) -> TopicModel:
    """TF-IDF über die Texte, dann NMF mit ``k`` Themen; die Anteile sind L1-normierte Zeilen von W.

    NMF statt LDA: auf den 19 033 Texten der Referenz 3,8 s gegen 47 s, und LDA lieferte Themen
    aus Funktionswörtern (gemessen 2026-10-11, docs/decisions.md). ``init="nndsvda"`` ist
    deterministisch, zwei Läufe im selben Prozess liefern dieselben Zahlen.

    ``rules`` bringt die Stoppwörter aus dem Profil und die Saat (Punkt 45); ohne sie rechnet die
    Funktion wie in Option 06. ``bodies`` ist ``papers_gremien.parquet`` und nur für die Saat da.
    """
    rules = rules or TopicRules()
    texts = corpus.filter(pl.col(TEXT) != "").select(DOC, TEXT).sort(DOC)
    if texts.height < settings.k:
        raise EmptyResultError(
            f"{settings.k} Themen brauchen mindestens so viele Dokumente mit Text, "
            f"{texts.height} vorhanden."
        )
    documents = texts.get_column(TEXT).to_list()
    matrix, vocabulary = vectorize(documents, settings, rules)
    if matrix.shape[1] < settings.k:
        # nndsvda zerlegt in k Faktoren und braucht dafür k <= min(Dokumente, Wörter); sonst wirft
        # sklearn ein ValueError. Zu wenige Wörter sind eine Eigenschaft der Daten, kein
        # Programmierfehler: ein Domänenfehler mit dem Grund, nicht eine Vertragsverletzung.
        raise EmptyResultError(
            f"{settings.k} Themen brauchen mindestens so viele Wörter im Vokabular, "
            f"{matrix.shape[1]} überleben min_df={settings.min_df} und max_df={settings.max_df} "
            f"auf {texts.height} Dokumenten."
        )
    groups = _committee_rows(texts, bodies, settings, rules)
    if groups:
        counts = CountVectorizer(token_pattern=TOKEN_PATTERN, vocabulary=vocabulary).fit_transform(
            documents
        )
        weights, components = _fit_seeded(
            matrix, counts.tocsr(), vocabulary, groups, settings, rules
        )
    else:
        weights, components = _fit_free(matrix, settings, settings.k)
    shares = pl.DataFrame(
        {DOC: texts.get_column(DOC), SHARES: _l1_rows(weights, settings.k).tolist()},
        schema={DOC: pl.String, SHARES: pl.List(pl.Float64)},
    )
    codes = [code for code, _ in groups]
    return TopicModel(
        shares=shares, topics=_topic_rows(components, vocabulary, shares, settings, codes)
    )


def _topic_rows(
    components: np.ndarray,
    vocabulary: Sequence[str],
    shares: pl.DataFrame,
    settings: Topics,
    codes: Sequence[str],
) -> pl.DataFrame:
    """Eine Zeile je Thema: Gremium, stärkste Wörter, dominierte Dokumente, Summe der Anteile."""
    words = [
        [
            str(vocabulary[position])
            # stable, damit zwei gleich starke Wörter immer in derselben Folge stehen
            for position in np.argsort(-component, kind="stable")[: settings.top_words]
            # ein gesätes Thema hat nur seine Saatwörter; Nullen wären kein Label
            if component[position] > 0.0
        ]
        for component in np.asarray(components, dtype=np.float64)
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
            BODY: [codes[topic] if topic < len(codes) else None for topic in range(settings.k)],
            WORDS: words,
            DOCUMENTS: [int(counted.get(topic, 0)) for topic in range(settings.k)],
            WEIGHT_SUM: list(totals),
        },
        schema=TOPIC_SCHEMA,
    )
