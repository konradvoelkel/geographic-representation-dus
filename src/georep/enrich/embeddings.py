"""Beitrag von Vorhaben 18: Einbettungen der Stücke und Dokumente, ähnliche Dokumente.

Zwei Schritte hinter allen Kernschritten (``docs/plans/18-einbettungen.md``, § 6 und § 10):

* ``embeddings`` (mit Modell, läuft nur mit ``georep run --models``, Fundament F5): liest Korpus
  und Rohtextstore (Fundament F1), zerteilt nach ``18-stuecke-1`` (``prep.chunks``), bettet über
  ``embed_texts`` und den Modellcache ein und schreibt **nur lokal**
  ``processed/einbettungen_stuecke.parquet`` (``datei``, ``stueck``, ``start``, ``end``, ``vektor``)
  und ``processed/einbettungen_dokumente.parquet`` (``id``, ``datei``, ``vektor``; je Korpus-ID
  eine Zeile, IDs ohne Rohtext fehlen). Die Vektoren sind auf Länge 1 normiert.
* ``neighbors`` (offline): schreibt ``processed/aehnliche_dokumente.parquet`` aus den
  Dokumentvektoren (``search.vectors.neighbor_table``). Gibt es keine -- auf GitHub Pages und in
  CI, wo kein Modell rechnet --, nimmt er das Paket, das ``bootstrap`` nach ``raw/`` gelegt hat
  (``[embeddings].neighbors_package``), und ohne beides eine leere Tabelle mit demselben Schema.

Beide fehlen ohne ``embeddings.enabled``. Die Pfade gehören diesem Modul (Synergien 2026-11, § 2.1):
wer sie liest -- ``georep search``, ``georep pack --neighbors``, später der Dokumentdialog --,
nimmt sie aus ``embedding_files``.

Die Prompt-Version ist ``18-stuecke-1`` (Stücke) und ``18-anfrage-1`` (Suchfragen), solange
Präfix und Zuschnitt die gemessenen sind; sonst hängt ein kurzer Hash daran. So kann eine Änderung
an ``[ml.embedding]`` (außerhalb des Fingerprints) die Kennung im Stamp nicht verfehlen, und ein
Lauf mit den gemessenen Werten trifft die Vektoren der Messung im Modellcache.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import NamedTuple

import numpy as np
import polars as pl

from georep.enrich import Contribution
from georep.errors import SchemaError
from georep.http import Transport
from georep.io import write_parquet
from georep.layout import Layout
from georep.ml.base import Embedder, EmbeddingUse
from georep.ml.batch import embed_texts, progress_log
from georep.ml.cache import ModelCache
from georep.ml.ollama import client_from_settings, embedder_from_settings
from georep.pipeline import Step
from georep.search.units import build_units, raw_frame, unit_chunks
from georep.search.vectors import (
    EMBEDDINGS_SCHEMA_VERSION,
    NEIGHBORS_SCHEMA,
    NEIGHBORS_SCHEMA_VERSION,
    chunk_vectors_schema,
    document_vectors,
    document_vectors_schema,
    neighbor_table,
    normalise,
)
from georep.settings import Settings
from georep.stores import RawTextStore

CHUNK_PROMPT = "18-stuecke-1"
QUERY_PROMPT = "18-anfrage-1"
# Was die Fassung 1 festlegt (Messdokument § 3.1). Weicht ein Wert ab, ist es eine andere Fassung.
CHUNK_VERSION_1 = {
    "document_prefix": "search_document: ",
    "chunk_chars": 1600,
    "title_chars": 200,
    "overlap_chars": 200,
}
QUERY_VERSION_1 = {"query_prefix": "search_query: "}
PROGRESS_EVERY_S = 60.0


class EmbeddingFiles(NamedTuple):
    chunks: Path  # lokal
    documents: Path  # lokal
    neighbors: Path
    package: Path  # die Kopie des Nachbarpakets, die bootstrap anlegt


def embedding_files(layout: Layout) -> EmbeddingFiles:
    """Die Dateien des Beitrags: zwei lokale mit Vektoren, die Nachbartabelle, die Paketkopie."""
    return EmbeddingFiles(
        layout.processed / "einbettungen_stuecke.parquet",
        layout.processed / "einbettungen_dokumente.parquet",
        layout.processed / "aehnliche_dokumente.parquet",
        layout.raw / "aehnliche_dokumente_paket.parquet",
    )


def _versioned(base: str, values: dict[str, object], measured: dict[str, object]) -> str:
    """``base``, wenn die Werte die gemessenen sind; sonst ``base`` mit einem Hash der Werte."""
    if values == measured:
        return base
    text = json.dumps(values, sort_keys=True, ensure_ascii=False)
    return f"{base}+{hashlib.sha256(text.encode()).hexdigest()[:8]}"


def chunk_prompt(settings: Settings) -> str:
    """Die Prompt-Version der Stücke: Präfix des Modells und Zuschnitt bestimmen den Text."""
    cfg = settings.embeddings
    values: dict[str, object] = {
        "document_prefix": settings.ml.embedding.document_prefix,
        "chunk_chars": cfg.chunk_chars,
        "title_chars": cfg.title_chars,
        "overlap_chars": cfg.overlap_chars,
    }
    return _versioned(CHUNK_PROMPT, values, dict(CHUNK_VERSION_1))


def query_prompt(settings: Settings) -> str:
    """Die Prompt-Version der Suchfragen: nur das Präfix bestimmt den Text."""
    values: dict[str, object] = {"query_prefix": settings.ml.embedding.query_prefix}
    return _versioned(QUERY_PROMPT, values, dict(QUERY_VERSION_1))


def embeddings_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Die Schritte ``embeddings`` und ``neighbors``, wenn das Profil sie einschaltet.

    Das Modell kommt aus ``[ml]``; gefragt wird der Server erst, wenn ``embeddings`` laufen darf
    (Fundament F5). ``http`` (Fundament F7) bleibt ungenutzt: ollama spricht seine eigene Naht.
    """
    if not settings.embeddings.enabled:
        return []
    embedder = embedder_from_settings(settings.ml, client_from_settings(settings.ml))
    return model_steps(settings, layout, embedder)


def model_steps(settings: Settings, layout: Layout, embedder: Embedder) -> list[Step]:
    """Die beiden Schritte mit einem gegebenen Einbetter; Tests geben ``FakeEmbedder``."""
    cfg = settings.embeddings
    files = embedding_files(layout)
    use = EmbeddingUse(embedder, chunk_prompt(settings))

    def embeddings() -> str:
        corpus = pl.read_parquet(layout.corpus, columns=["id", "name", "file_name"])
        store = RawTextStore(layout.raw_texts)
        raw = raw_frame(
            (name, str(row["text"]), store.form_feeds(name)) for name, row in store.rows.items()
        )
        units = build_units(corpus, raw, cfg.title_chars)
        chunks = unit_chunks(
            units, cfg.chunk_chars, cfg.overlap_chars, settings.ml.embedding.document_prefix
        )
        with ModelCache(layout.ml_cache, use.name) as cache:
            got = embed_texts(
                use,
                cache,
                chunks.get_column("text").to_list(),
                batch_size=settings.ml.batch_size,
                limit=settings.ml.limit,
                progress=progress_log(PROGRESS_EVERY_S),
            )
        vectors = normalise(got.vectors)
        present = pl.Series("present", got.present)
        dimension = embedder.dimension
        stored = chunks.with_columns(present).filter(pl.col("present"))
        write_parquet(
            pl.DataFrame(
                {
                    "datei": stored.get_column("datei"),
                    "stueck": stored.get_column("stueck"),
                    "start": stored.get_column("start"),
                    "end": stored.get_column("end"),
                    "vektor": vectors[got.present],
                },
                schema=chunk_vectors_schema(dimension),
            ),
            files.chunks,
            schema_version=EMBEDDINGS_SCHEMA_VERSION,
        )
        documents = _document_frame(units, chunks, vectors, got.present, cfg.document_chunks)
        write_parquet(
            documents.cast(document_vectors_schema(dimension)),  # type: ignore[arg-type]
            files.documents,
            schema_version=EMBEDDINGS_SCHEMA_VERSION,
        )
        ids = corpus.height
        without = ids - int(units.get_column("ids").list.len().sum())
        missing = int(units.get_column("ids").list.len().sum()) - documents.height
        return (
            f"{units.height} Dateien, {chunks.height} Stücke ({got.report.line()}); "
            f"Dokumentvektoren für {documents.height} von {ids} Korpus-IDs, {without} ohne "
            f"Rohtext, {missing} ohne eines der ersten {cfg.document_chunks} Stücke (offen oder "
            f"abgewiesen; Prompt {use.prompt})"
        )

    def neighbors() -> str:
        if files.documents.is_file():
            documents = pl.read_parquet(files.documents)
            if documents.height:
                units = (
                    documents.sort("id")
                    .group_by("datei", maintain_order=True)
                    .agg(
                        pl.col("id").first(),
                        pl.col("id").alias("ids"),
                        pl.col("vektor").first(),
                    )
                    .sort("id")
                )
                matrix = np.asarray(units.get_column("vektor").to_numpy(), dtype=np.float32)
                frame = neighbor_table(units.select("id", "datei", "ids"), matrix, cfg.neighbors)
                write_parquet(frame, files.neighbors, schema_version=NEIGHBORS_SCHEMA_VERSION)
                return (
                    f"{frame.height} Zeilen, {cfg.neighbors} Nachbarn je Korpus-ID aus "
                    f"{units.height} Dokumentvektoren"
                )
        if files.package.is_file():
            packed = pl.read_parquet(files.package)
            if dict(packed.schema) != NEIGHBORS_SCHEMA:
                raise SchemaError(
                    f"{files.package}: Spalten {dict(packed.schema)}, erwartet {NEIGHBORS_SCHEMA}"
                )
            frame = packed.sort("id", "rang")
            write_parquet(frame, files.neighbors, schema_version=NEIGHBORS_SCHEMA_VERSION)
            return (
                f"{frame.height} Zeilen aus dem Paket für {frame.get_column('id').n_unique()} "
                "Korpus-IDs; keine Dokumentvektoren"
            )
        write_parquet(
            pl.DataFrame(schema=NEIGHBORS_SCHEMA),
            files.neighbors,
            schema_version=NEIGHBORS_SCHEMA_VERSION,
        )
        return "keine Dokumentvektoren und kein Paket: leere Tabelle"

    return [
        Step(
            "embeddings",
            (layout.corpus, layout.raw_texts),
            (files.chunks, files.documents),
            embeddings,
            EMBEDDINGS_SCHEMA_VERSION,
            models=use,
        ),
        Step(
            "neighbors",
            (),
            (files.neighbors,),
            neighbors,
            NEIGHBORS_SCHEMA_VERSION,
            optional=(files.documents, files.package),
        ),
    ]


def _document_frame(
    units: pl.DataFrame,
    chunks: pl.DataFrame,
    vectors: np.ndarray,
    present: np.ndarray,
    document_chunks: int,
) -> pl.DataFrame:
    """Je Korpus-ID einer Datei, deren erste ``document_chunks`` Stücke alle da sind, ihr Vektor.

    Fehlt eines davon (ein Teillauf mit ``--limit``, ein abgewiesener Text), bekommt die Datei
    keinen Dokumentvektor: das Mittel über die übrigen wäre ein anderer Vektor.
    """
    head = chunks.with_columns(pl.Series("present", present)).filter(
        pl.col("stueck") < document_chunks
    )
    complete = set(
        head.group_by("datei")
        .agg(pl.col("present").all())
        .filter(pl.col("present"))
        .get_column("datei")
        .to_list()
    )
    keep = np.asarray([d in complete for d in chunks.get_column("datei").to_list()], dtype=np.bool_)
    places = chunks.get_column("stueck").to_numpy()[keep]
    matrix = document_vectors(places.tolist(), vectors[keep], document_chunks)
    files = chunks.filter(pl.Series(keep)).filter(pl.col("stueck") == 0).get_column("datei")
    by_file = pl.DataFrame(
        {"datei": files, "vektor": matrix}, schema_overrides={"datei": pl.String}
    )
    return (
        units.select(pl.col("ids").alias("id"), "datei")
        .explode("id")
        .join(by_file, on="datei", how="inner")
        .select("id", "datei", "vektor")
        .sort("id")
    )


CONTRIBUTION = Contribution("18-einbettungen", steps=embeddings_steps)
