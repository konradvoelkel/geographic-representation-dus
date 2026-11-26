"""``georep search "<frage>" [--method embedding|hybrid|bm25] [--n 10]``: die Befehlszeile von Vorhaben 18.

Unterbefehl und Ausgabe stehen hier, die Suche in ``search.query``; ``cli.py`` hängt den Parser
ein und ruft ``run`` (wie ``validate``, Fundament F4). Lokal: die Stückvektoren liegen nur dort,
wo ``georep run --models`` lief, und die Frage bettet der ollama-Server dieses Rechners ein. Ohne
ihn sucht ``embedding`` mit BM25 und sagt es in einer Zeile.
"""

from __future__ import annotations

import argparse
import sys

import polars as pl

from georep.enrich.embeddings import DeferredEmbedder
from georep.layout import Layout
from georep.search.query import METHODS, describe, search
from georep.settings import Settings


def _positive(text: str) -> int:
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"keine ganze Zahl: {text}") from error
    if value < 1:
        raise argparse.ArgumentTypeError(f"muss mindestens 1 sein: {value}")
    return value


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    found = sub.add_parser(
        "search",
        help="Ratsdokumente des Profils suchen: nach Bedeutung (Einbettung, Vorgabe), gemischt "
        "oder nach Wörtern (BM25); Vorhaben 18",
    )
    found.add_argument("query", metavar="frage", help="Stichwort oder Frage, wie in ein Suchfeld")
    found.add_argument(
        "--method",
        choices=METHODS,
        default="embedding",
        help="embedding (nDCG@10 0,883 an 50 Fragen), hybrid (RRF, 0,846; bei Stichwörtern im "
        "Amtswortlaut am besten) oder bm25 (0,709, ohne Modell)",
    )
    found.add_argument("--n", type=_positive, default=10, help="so viele Treffer (Standard 10)")


def run(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    query = " ".join(str(args.query).split())
    if not query:
        print("Fehler: die Frage ist leer", file=sys.stderr)
        return 2
    # Review Runde 1, N5: der Client entsteht erst in der Suche, in ihrem ``try`` mit Rückfall
    embedder = DeferredEmbedder(settings.ml) if args.method != "bm25" else None
    result = search(layout, settings, query, args.method, args.n, embedder)
    corpus = pl.read_parquet(
        layout.corpus, columns=["id", "reference", "date", "name", "download_url"]
    )
    print(describe(result, corpus, query), end="")
    return 0
