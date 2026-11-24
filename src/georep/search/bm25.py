"""Vorhaben 18: die Wortsuche BM25 mit deutschem Stemmer, die Rangfolge und die Mischung (RRF).

Fassung ``18-bm25-1`` der Messung (``docs/plans/18-einbettungen.md``, § 3.1): Token ``\\w+`` in
Kleinschreibung, je Token der Snowball-Stemmer (``georep.search.stem``), keine Stoppwortliste.
Okapi BM25 mit ``k1`` und ``b`` aus den Settings (1,2 und 0,75), IDF = ln(1 + (N − n + 0,5) /
(n + 0,5)) wie Lucene, mittlere Länge über alle Einheiten. Die Suchfrage geht durch dieselbe
Zerlegung, jedes verschiedene Token zählt einmal; Einheiten ohne ein Token der Frage stehen nicht in
der Rangfolge. Die Punktzahlen rechnen in derselben Folge wie das Messskript und sind darum
bitgleich mit ihm (``tests/unit/test_search_slow.py``: die Rangfolgen der 50 Suchfragen).

Die Mischung ist Reciprocal Rank Fusion (Cormack, Clarke, Büttcher 2009) über die ersten
``depth`` Einheiten jeder Liste, je mit Gewicht 1: s(d) = Σ 1 / (k + Rang). Gleichstände in allen
Verfahren nach ID aufsteigend.

Ohne Polars und ohne Settings: Einheiten sind Positionen in ``Bm25Index.ids``.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

import deal
import numpy as np
import numpy.typing as npt
from scipy import sparse

from georep.search.stem import stem

BM25_VERSION = "18-bm25-1"  # Zerlegung, Stemmer und Formel; steht im Schlüssel der Wortmatrix
WORD = re.compile(r"\w+")

Scores = npt.NDArray[np.float64]


@dataclass
class Tokenizer:
    """Token ``\\w+`` in Kleinschreibung, gestemmt; jedes verschiedene Wort wird einmal gestemmt."""

    stemming: bool = True
    seen: dict[str, str] = field(default_factory=dict)

    def __call__(self, text: str) -> list[str]:
        words = WORD.findall(text.lower())
        if not self.stemming:
            return words
        seen = self.seen
        found = []
        for word in words:
            root = seen.get(word)
            if root is None:
                root = seen[word] = stem(word)
            found.append(root)
        return found


@dataclass(frozen=True)
class Bm25Index:
    """Die Wortmatrix (Einheiten × Token, Häufigkeiten als float64, spaltenweise) und ihr Vokabular."""

    ids: tuple[str, ...]
    vocabulary: dict[str, int]
    matrix: sparse.csc_matrix
    lengths: npt.NDArray[np.float64]  # Token je Einheit

    @property
    def size(self) -> int:
        return len(self.ids)


def _index_holds(
    ids: Sequence[str], counts: Sequence[Counter[str]], result: Bm25Index | None = None
) -> bool:
    assert result is not None
    return (
        result.matrix.shape == (len(ids), len(result.vocabulary))
        and bool(np.all(result.lengths == np.asarray([sum(c.values()) for c in counts])))
        and list(result.ids) == list(ids)
    )


@deal.pre(
    lambda ids, counts: len(ids) == len(counts) and len(set(ids)) == len(ids),
    message="je Einheit eine Zählung, jede ID einmal",
)
@deal.ensure(_index_holds, message="Matrix, Längen und IDs passen zu den Zählungen")
def build_index(ids: Sequence[str], counts: Sequence[Counter[str]]) -> Bm25Index:
    """Die Wortmatrix aus den Token-Zählungen je Einheit; das Vokabular alphabetisch."""
    vocabulary = {term: i for i, term in enumerate(sorted({t for c in counts for t in c}))}
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for row, count in enumerate(counts):
        for term, n in count.items():
            rows.append(row)
            cols.append(vocabulary[term])
            data.append(float(n))
    matrix = sparse.csc_matrix(
        (np.asarray(data, dtype=np.float64), (rows, cols)),
        shape=(len(ids), len(vocabulary)),
        dtype=np.float64,
    )
    matrix.sort_indices()
    lengths = np.asarray([float(sum(c.values())) for c in counts], dtype=np.float64)
    return Bm25Index(tuple(ids), vocabulary, matrix, lengths)


def count_terms(texts: Iterable[str], tokenize: Callable[[str], list[str]]) -> list[Counter[str]]:
    """Je Text die Häufigkeit jedes Tokens."""
    return [Counter(tokenize(text)) for text in texts]


@deal.pre(lambda index, tokens, k1, b: k1 > 0 and 0 <= b <= 1)
@deal.ensure(
    lambda index, tokens, k1, b, result: result.shape == (index.size,) and bool(np.all(result >= 0))
)
def bm25_scores(index: Bm25Index, tokens: Sequence[str], k1: float, b: float) -> Scores:
    """Die Punktzahl jeder Einheit für die Token einer Frage; jedes verschiedene Token einmal.

    Die Rechnung steht in derselben Folge wie im Messskript (``Bm25.punkte``), damit die
    Punktzahlen bitgleich sind: IDF mal Häufigkeit mal (k1 + 1), geteilt durch Häufigkeit plus Norm.
    """
    values = np.zeros(index.size, dtype=np.float64)
    if index.size == 0 or not index.lengths.any():
        return values  # keine Einheit trägt ein Token, also trifft keine
    matrix = index.matrix
    df = np.diff(matrix.indptr)
    idf = np.log(1.0 + (index.size - df + 0.5) / (df + 0.5))
    norm = k1 * (1.0 - b + b * index.lengths / index.lengths.mean())
    for token in dict.fromkeys(tokens):
        column = index.vocabulary.get(token)
        if column is None:
            continue
        lo, hi = matrix.indptr[column], matrix.indptr[column + 1]
        rows = matrix.indices[lo:hi]
        tf = matrix.data[lo:hi]
        values[rows] += idf[column] * tf * (k1 + 1.0) / (tf + norm[rows])
    return values


# Benannte Validatoren vor dem Stapel, weil ``positive_only`` optional ist (CLAUDE.md, deal).
def _depth_valid(values: Scores, depth: int, positive_only: bool = False) -> bool:
    return depth >= 0


def _ranked(
    values: Scores, depth: int, positive_only: bool = False, result: Sequence[int] = ()
) -> bool:
    return (
        len(result) <= depth
        and len(set(result)) == len(result)
        and all(not positive_only or values[i] > 0 for i in result)
        and all(
            (values[a], -a) >= (values[b], -b) for a, b in zip(result, result[1:], strict=False)
        )
    )


@deal.pre(_depth_valid)
@deal.ensure(_ranked, message="nach Punktzahl fallend, Gleichstände nach Position aufsteigend")
def ranking(values: Scores, depth: int, positive_only: bool = False) -> list[int]:
    """Die Positionen der besten ``depth`` Einheiten; ``positive_only`` lässt Null und weniger weg.

    Stabil sortiert über aufsteigende Positionen: Gleichstände bleiben nach Position, und die
    Einheiten stehen nach ID, also nach ID.
    """
    index = np.arange(len(values))
    if positive_only:
        index = index[values > 0]
    if len(index) == 0:
        return []
    order = index[np.argsort(-values[index], kind="stable")]
    return [int(i) for i in order[:depth]]


def _fused_in_order(
    rankings: Sequence[Sequence[str]], k: int, depth: int, result: list[tuple[str, float]]
) -> bool:
    ids = [i for i, _ in result]
    return len(ids) == len(set(ids)) and all(
        (-a[1], a[0]) <= (-b[1], b[0]) for a, b in zip(result, result[1:], strict=False)
    )


@deal.pre(lambda rankings, k, depth: k >= 0 and depth >= 0)
@deal.ensure(_fused_in_order, message="jede ID einmal, nach Punktzahl fallend, dann nach ID")
def rrf(rankings: Sequence[Sequence[str]], k: int, depth: int) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion über die ersten ``depth`` jeder Liste: Σ 1 / (k + Rang), Rang ab 1.

    Eine ID außerhalb der ersten ``depth`` einer Liste bekommt von ihr nichts. Das Ergebnis ist
    nach Punktzahl fallend, bei Gleichstand nach ID aufsteigend, und nicht gekürzt.
    """
    fused: dict[str, float] = {}
    for listing in rankings:
        for place, unit in enumerate(listing[:depth], start=1):
            fused[unit] = fused.get(unit, 0.0) + 1.0 / (k + place)
    return sorted(fused.items(), key=lambda pair: (-pair[1], pair[0]))
