"""Vorhaben 18: die Suche über die Einheiten eines Profils, mit Einbettung, Mischung oder BM25.

Gemessen an 50 Suchfragen der Hauptperiode (``docs/plans/18-einbettungen.md``, § 4.4 und § 5):
nDCG@10 Einbettung 0,883, Mischung 0,846, BM25 0,709. Die Einbettung ist darum die Vorgabe
(Regel aus § 3.1); die Mischung war bei Stichwörtern im Amtswortlaut am besten und steht als
``hybrid`` bereit, BM25 als ``bm25`` für einen Rechner ohne ollama.

* **Einbettung**: die Frage mit ``query_prefix`` über die Naht von F5 (``embed_texts``, Prompt
  ``18-anfrage-1``), die Stückvektoren aus ``processed/einbettungen_stuecke.parquet``; die
  Punktzahl einer Einheit ist das Maximum über ihre Stücke. Die Frage muss mit demselben Modell
  und Digest eingebettet sein wie die Stücke; sonst ist das ein ``ModelError``.
* **BM25**: über eine Wortmatrix aus Titel und Rohtext je Einheit, die der erste Aufruf baut (für
  die Hauptperiode rund 6 bis 9 s) und als ``processed/suche_wortmatrix.parquet`` neben die
  Vektoren legt. Ihr Schlüssel (Fassung, Titellänge, SHA-256 von Korpus und Rohtextstore) steht in
  den Metadaten; ändert sich eine Eingabe, baut der nächste Aufruf sie neu.
* **Mischung**: RRF über die ersten ``fusion_depth`` beider Listen.

Die Einheit ist die Datei unter ihrer kleinsten Korpus-ID (``search.units``); die Trefferliste
nennt diese ID mit Drucksache, Datum, Titel und Link der Hauptdatei.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
import polars as pl

from georep.enrich.embeddings import chunk_prompt, embedding_files, query_prompt
from georep.errors import MissingInputError, ModelError
from georep.io import atomic_path, digest
from georep.layout import Layout
from georep.ml.base import Embedder, EmbeddingUse
from georep.ml.batch import embed_texts
from georep.ml.cache import ModelCache
from georep.search.bm25 import (
    BM25_VERSION,
    Bm25Index,
    Tokenizer,
    bm25_scores,
    build_index,
    count_terms,
    ranking,
    rrf,
)
from georep.search.units import build_units, raw_frame
from georep.search.vectors import max_per_unit, normalise
from georep.settings import Settings
from georep.stores import SCHEMA_KEY, RawTextStore

Method = Literal["embedding", "hybrid", "bm25"]
METHODS: tuple[Method, ...] = ("embedding", "hybrid", "bm25")
# nDCG@10 an den 50 Suchfragen der Hauptperiode (Messdokument § 4.4); die Hinweiszeile nennt sie,
# wenn die Suche auf BM25 zurückfällt. Für andere Perioden und Städte ist nichts gemessen.
MEASURED = {"embedding": "0,883", "hybrid": "0,846", "bm25": "0,709"}
NAMES = {"embedding": "Einbettung", "hybrid": "Mischung (RRF)", "bm25": "BM25"}
WORD_INDEX_SCHEMA_VERSION = 1
KEY = "georep.key"  # der Schlüssel der Wortmatrix in ihren Parquet-Metadaten
WORD_INDEX_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "staemme": pl.List(pl.String),
    "anzahl": pl.List(pl.Int32),
}


@dataclass(frozen=True)
class Hit:
    rank: int
    score: float
    id: str


@dataclass(frozen=True)
class Result:
    """Die Treffer, das Verfahren, das sie lieferte, und warum es ein anderes als das gewünschte ist."""

    hits: tuple[Hit, ...]
    method: Method
    note: str = ""


def word_index_path(layout: Layout) -> Path:
    return layout.processed / "suche_wortmatrix.parquet"


def require(*paths: Path) -> None:
    """``MissingInputError`` mit dem Handgriff, wenn eine Eingabe des Befehls fehlt (Review, N6)."""
    for path in paths:
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; erst `georep run` für dieses Profil")


def search_units(layout: Layout, settings: Settings) -> pl.DataFrame:
    """Die Einheiten aus Korpus und Rohtextstore, wie der Schritt ``embeddings`` sie bildet."""
    require(layout.corpus, layout.raw_texts)
    corpus = pl.read_parquet(layout.corpus, columns=["id", "name", "file_name"])
    store = RawTextStore(layout.raw_texts)
    raw = raw_frame(
        (name, str(row["text"]), store.form_feeds(name)) for name, row in store.rows.items()
    )
    return build_units(corpus, raw, settings.embeddings.title_chars)


def index_key(layout: Layout, settings: Settings) -> str:
    """Was die Wortmatrix bestimmt: Fassung, Titellänge, Korpus und Rohtextstore."""
    parts = {
        "fassung": BM25_VERSION,
        "title_chars": settings.embeddings.title_chars,
        "korpus": digest(layout.corpus),
        "rohtexte": digest(layout.raw_texts),
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


def word_index(layout: Layout, settings: Settings) -> tuple[Bm25Index, bool]:
    """Die Wortmatrix aus der Datei, wenn ihr Schlüssel passt, sonst neu gebaut und gespeichert.

    Liefert die Matrix und ob sie neu gebaut ist. Der Text einer Einheit ist Titel, Leerzeile und
    Rohtext, wie in der Messung (Seitenwechsel als Zeilenwechsel; für ``\\w+`` gleich).
    """
    require(layout.corpus, layout.raw_texts)
    path = word_index_path(layout)
    key = index_key(layout, settings)
    if path.is_file():
        meta = pl.read_parquet_metadata(path)
        if meta.get(KEY) == key and meta.get(SCHEMA_KEY) == str(WORD_INDEX_SCHEMA_VERSION):
            frame = pl.read_parquet(path)
            counts = [
                Counter(dict(zip(terms, numbers, strict=True)))
                for terms, numbers in frame.select("staemme", "anzahl").iter_rows()
            ]
            return build_index(frame.get_column("id").to_list(), counts), False
    units = search_units(layout, settings)
    texts = [
        f"{title}\n\n{raw.replace(chr(12), chr(10))}"
        for title, raw in units.select("titel", "roh").iter_rows()
    ]
    counts = count_terms(texts, Tokenizer())
    ids = units.get_column("id").to_list()
    frame = pl.DataFrame(
        {
            "id": ids,
            "staemme": [list(count) for count in counts],
            "anzahl": [list(count.values()) for count in counts],
        },
        schema=WORD_INDEX_SCHEMA,
    )
    with atomic_path(path) as tmp:
        frame.write_parquet(
            tmp,
            compression="zstd",
            metadata={SCHEMA_KEY: str(WORD_INDEX_SCHEMA_VERSION), KEY: key},
        )
    return build_index(ids, counts), True


def bm25_ranking(
    index: Bm25Index, query: str, settings: Settings, depth: int
) -> list[tuple[str, float]]:
    """Die ersten ``depth`` Einheiten mit einem Token der Frage, nach BM25."""
    bm25 = settings.embeddings.bm25
    scores = bm25_scores(index, Tokenizer()(query), bm25.k1, bm25.b)
    return [(index.ids[i], float(scores[i])) for i in ranking(scores, depth, positive_only=True)]


def query_vector(
    layout: Layout, settings: Settings, embedder: Embedder, query: str
) -> npt.NDArray[np.float32]:
    """Die Frage, eingebettet über den Modellcache (Prompt ``18-anfrage-1``), normiert.

    Außerhalb von ``run_step`` setzt der Aufrufer ``retry_rejected`` selbst (``docs/todo.md``,
    Punkt 11 c); hier aus den Settings, wie ``run_step`` es täte.
    """
    use = EmbeddingUse(embedder, query_prompt(settings))
    use.reset(retry_rejected=settings.ml.retry_rejected)
    with ModelCache(layout.ml_cache, use.name) as cache:
        got = embed_texts(use, cache, [settings.ml.embedding.query_prefix + query], batch_size=1)
    if not bool(got.present[0]):
        raise ModelError(f"{use.name}: die Frage ist nicht eingebettet ({got.report.line()})")
    vector: npt.NDArray[np.float32] = normalise(got.vectors)[0]
    return vector


def _check_model(layout: Layout, settings: Settings, embedder: Embedder) -> None:
    """Frage und Stücke passen nur aus demselben Modell, Digest, Prompt-Version und Fenster.

    Der Stamp von ``embeddings`` sagt, womit die Stücke entstanden. Verglichen werden Modell und
    Digest, die Prompt-Version der Stücke mit der, die diese Settings ergäben (``chunk_prompt``),
    und der Schlüssel der Optionen (Fenster, Abschneiden) mit dem des Einbetters der Frage (Review
    Runde 1, N2). Weicht eines ab, ist das ein ``ModelError``, und die Suche fällt auf BM25 zurück.
    """
    files = embedding_files(layout)
    stamp_path = files.chunks.with_name(files.chunks.name + ".stamp.json")
    if not stamp_path.is_file():
        return
    found = json.loads(stamp_path.read_text(encoding="utf-8")).get("models", {})
    wanted = {
        "model": EmbeddingUse(embedder, "").name,
        "digest": embedder.digest,
        "prompt": chunk_prompt(settings),
        "options": embedder.options.key(),
    }
    differ = [key for key, value in wanted.items() if found.get(key) != value]
    if differ:
        said = ", ".join(f"{key} {found.get(key)} statt {wanted[key]}" for key in differ)
        raise ModelError(
            f"die Stückvektoren passen nicht zur Frage ({said}); erst `georep run --models "
            "embeddings`"
        )


def embedding_ranking(
    layout: Layout, settings: Settings, embedder: Embedder, query: str, depth: int
) -> list[tuple[str, float]]:
    """Die ersten ``depth`` Einheiten nach dem besten Stück; Gleichstände nach ID."""
    path = embedding_files(layout).chunks
    if not path.is_file():
        raise MissingInputError(
            f"{path.name} fehlt; die Stückvektoren rechnet `georep run --models embeddings`"
        )
    _check_model(layout, settings, embedder)
    chunks = pl.read_parquet(path, columns=["datei", "vektor"])
    corpus = pl.read_parquet(layout.corpus, columns=["id", "file_name"])
    units = (
        corpus.filter(pl.col("file_name").is_in(chunks.get_column("datei").unique().implode()))
        .group_by("file_name")
        .agg(pl.col("id").min())
        .sort("id")
    )
    position = {datei: i for i, datei in enumerate(units.get_column("file_name").to_list())}
    owner = np.asarray([position[d] for d in chunks.get_column("datei").to_list()], dtype=np.int64)
    vectors = np.asarray(chunks.get_column("vektor").to_numpy(), dtype=np.float32)
    sims = vectors @ query_vector(layout, settings, embedder, query)
    scores = max_per_unit(sims, owner, units.height)
    ids = units.get_column("id").to_list()
    return [(ids[i], float(scores[i])) for i in ranking(scores, depth)]


@contextmanager
def gpu_slot(lock: Path | None) -> Iterator[bool]:
    """Die GPU-Sperre nicht blockierend nehmen: ``True`` und gehalten bis zum Ende des Blocks, wenn
    sie frei ist oder keine eingestellt ist (``ml.gpu_lock``); ``False``, wenn ein anderer sie hält.

    Dieselbe Sperre wie ``flock <pfad>`` der GPU-Warteschlange (``flock(2)`` über ``fcntl``); ohne
    ``LOCK_NB`` wartete eine Suche, bis ein langer Lauf fertig ist (Review Runde 1, N1). Lässt sich
    die Datei nicht öffnen, ist das ein ``ModelError``.
    """
    if lock is None:
        yield True
        return
    try:
        handle = lock.open("a")
    except OSError as error:
        raise ModelError(f"die GPU-Sperre {lock} lässt sich nicht öffnen ({error})") from error
    with handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def search(
    layout: Layout,
    settings: Settings,
    query: str,
    method: Method,
    n: int,
    embedder: Embedder | None,
) -> Result:
    """Die ersten ``n`` Treffer. Ohne Einbetter, ohne Stückvektoren, ohne erreichbares Modell oder
    bei gehaltener GPU-Sperre sucht ``embedding`` und ``hybrid`` mit BM25 und sagt in ``note``,
    warum."""
    cfg = settings.embeddings
    require(layout.corpus)
    note = ""
    if method != "bm25":
        try:
            if embedder is None:
                raise ModelError("kein Einbettungsmodell")
            with gpu_slot(settings.ml.gpu_lock) as free:
                if not free:
                    raise ModelError(f"die GPU ist belegt (Sperre {settings.ml.gpu_lock})")
                semantic = embedding_ranking(
                    layout, settings, embedder, query, max(n, cfg.fusion_depth)
                )
        except (ModelError, MissingInputError) as error:
            note = (
                f"{error}; gesucht wird mit BM25 statt {NAMES[method]} (nDCG@10 an 50 Fragen der "
                f"Hauptperiode: {NAMES[method]} {MEASURED[method]}, BM25 {MEASURED['bm25']})"
            )
            method = "bm25"
    words: list[tuple[str, float]] = []
    if method != "embedding":
        index, _ = word_index(layout, settings)
        words = bm25_ranking(index, query, settings, max(n, cfg.fusion_depth))
    if method == "embedding":
        found = semantic[:n]
    elif method == "hybrid":
        found = rrf([[i for i, _ in words], [i for i, _ in semantic]], cfg.rrf_k, cfg.fusion_depth)[
            :n
        ]
    else:
        found = words[:n]
    hits = tuple(Hit(rank, score, unit) for rank, (unit, score) in enumerate(found, start=1))
    return Result(hits, method, note)


def describe(result: Result, corpus: pl.DataFrame, query: str) -> str:
    """Die Trefferliste als Text: Rang, Punktzahl, Drucksache, Datum, Titel, darunter der Link."""
    rows = {
        row[0]: row
        for row in corpus.filter(pl.col("id").is_in([h.id for h in result.hits]))
        .select("id", "reference", "date", "name", "download_url")
        .iter_rows()
    }
    lines = [f"Hinweis: {result.note}"] if result.note else []
    lines.append(f'„{query}" mit {NAMES[result.method]}: {len(result.hits)} Treffer')
    for hit in result.hits:
        _, reference, day, name, url = rows.get(hit.id, (hit.id, None, None, None, None))
        title = " ".join((name or "").split())
        lines.append(f"{hit.rank:>3}  {hit.score:.4f}  {reference or '–'}  {day or '–'}  {title}")
        lines.append(f"     {url or hit.id}")
    return "\n".join(lines) + "\n"
