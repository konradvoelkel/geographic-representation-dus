"""Vorhaben 18: ``georep search`` mit ``FakeEmbedder`` an einem kleinen Datensatz von Hand.

Nie ein Modell (CLAUDE.md): die Stückvektoren rechnet der Schritt ``embeddings`` mit dem Fake, und
die Frage bettet derselbe Fake ein. Ohne Einbetter, ohne Stückvektoren oder mit einem anderen
Modell sucht ``embedding`` mit BM25 und sagt es in einer Zeile.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt
import polars as pl
import pytest

from georep import cli
from georep.enrich.embeddings import embedding_files, model_steps
from georep.errors import ModelUnreachableError
from georep.layout import Layout
from georep.ml.base import Embedder, EmbeddingOptions
from georep.pipeline import run_pipeline
from georep.search import command as search_command
from georep.search.query import (
    Result,
    bm25_ranking,
    describe,
    embedding_ranking,
    search,
    word_index,
    word_index_path,
)
from georep.search.vectors import normalise
from georep.settings import Embeddings, Settings
from georep.stores import RawTextStore
from tests.fakes import FakeEmbedder, fake_vector

TEXTS = {
    "f1.pdf": "Der Radweg an der Schule wird verbreitert.\nRadwege und Radverkehr\fSeite zwei",
    "f2.pdf": "Baumfällungen im Südpark\nErsatzpflanzungen für gefällte Bäume",
    "f4.pdf": "Kita und Ganztag an Grundschulen",
    "f5.pdf": "Haushalt der Stadt: Produkt Radweg, Zeile 12",
}
CORPUS = [
    ("id1", "Antrag Radweg Schule", "f1.pdf"),
    ("id2", "Bäume im Park", "f2.pdf"),
    ("id4", "Kita", "f4.pdf"),
    ("id5", "Haushalt", "f5.pdf"),
    ("id9", "Ohne Text", None),
]


class Down:
    """Ein Einbetter, dessen Server nicht antwortet: schon der Digest scheitert."""

    name = "fake-embed:latest"
    dimension = 8
    options = EmbeddingOptions()

    @property
    def digest(self) -> str:
        raise ModelUnreachableError("ollama unter http://localhost:11434 nicht erreichbar")

    def embed(self, texts: Sequence[str]) -> npt.NDArray[np.float32]:
        raise ModelUnreachableError("ollama unter http://localhost:11434 nicht erreichbar")


@pytest.fixture
def settings(default_settings: Settings) -> Settings:
    small = Embeddings(enabled=True, chunk_chars=60, title_chars=20, overlap_chars=5, neighbors=2)
    return default_settings.model_copy(update={"embeddings": small})


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    layout.ensure_dirs()
    pl.DataFrame(
        [
            (i, name, f"R/{n}", dt.date(2024, 1, n + 1), f, f and f"https://ris.test/{f}")
            for n, (i, name, f) in enumerate(CORPUS)
        ],
        schema=["id", "name", "reference", "date", "file_name", "download_url"],
        orient="row",
    ).write_parquet(layout.corpus)
    store = RawTextStore(layout.raw_texts)
    for name, text in TEXTS.items():
        store.put(name, text, pages=text.count("\f") + 1, extractor="probe+roh", pdf_sha256="0")
    store.save()
    return layout


def _embedded(settings: Settings, layout: Layout, embedder: FakeEmbedder) -> None:
    steps = [s for s in model_steps(settings, layout, embedder) if s.name == "embeddings"]
    assert run_pipeline(steps, settings, models=True)[0].status == "ausgeführt"


def test_bm25_finds_the_word_and_builds_its_matrix_once(settings: Settings, layout: Layout) -> None:
    index, built = word_index(layout, settings)
    assert built and word_index_path(layout).is_file()
    hits = bm25_ranking(index, "Radweg", settings, 10)
    assert [unit for unit, _ in hits] == ["id1", "id5"]  # „Radwege" und „Radweg" sind ein Stamm
    again, built = word_index(layout, settings)
    assert not built and again.ids == index.ids
    assert bm25_ranking(again, "Radweg", settings, 10) == hits
    # ändert sich der Rohtext, baut der nächste Aufruf die Matrix neu
    store = RawTextStore(layout.raw_texts)
    store.put("f4.pdf", "Radweg zur Kita", pages=1, extractor="probe+roh", pdf_sha256="1")
    store.save()
    changed, built = word_index(layout, settings)
    assert built and "id4" in [u for u, _ in bm25_ranking(changed, "Radweg", settings, 10)]


def test_the_embedding_scores_a_unit_by_its_best_chunk(settings: Settings, layout: Layout) -> None:
    embedder = FakeEmbedder()
    _embedded(settings, layout, embedder)
    found = embedding_ranking(layout, settings, embedder, "Radweg", 10)
    assert [unit for unit, _ in found] == sorted(
        [u for u, _ in found], key=lambda u: -dict(found)[u]
    )
    assert {unit for unit, _ in found} == {"id1", "id2", "id4", "id5"}
    chunks = pl.read_parquet(embedding_files(layout).chunks)
    query = normalise(np.asarray([fake_vector("search_query: Radweg", 8)], dtype=np.float32))[0]
    best = {
        datei: float(np.max(np.asarray(rows.get_column("vektor").to_numpy()) @ query))
        for (datei,), rows in chunks.group_by("datei")
    }
    files = {i: f for i, _, f in CORPUS}
    for unit, score in found:
        assert score == pytest.approx(best[files[unit]], abs=1e-6)
    # die Frage wurde mit dem Präfix eingebettet, wie die Messung (18-anfrage-1)
    assert embedder.calls[-1] == ["search_query: Radweg"]


def test_hybrid_fuses_both_lists_with_rrf(settings: Settings, layout: Layout) -> None:
    embedder = FakeEmbedder()
    _embedded(settings, layout, embedder)
    result = search(layout, settings, "Radweg", "hybrid", 3, embedder)
    assert result.method == "hybrid" and not result.note and len(result.hits) == 3
    words = [u for u, _ in bm25_ranking(word_index(layout, settings)[0], "Radweg", settings, 100)]
    semantic = [u for u, _ in embedding_ranking(layout, settings, embedder, "Radweg", 100)]
    score = {u: 0.0 for u in {*words, *semantic}}
    for listing in (words, semantic):
        for place, unit in enumerate(listing, start=1):
            score[unit] += 1 / (60 + place)
    expected = sorted(score, key=lambda u: (-score[u], u))[:3]
    assert [h.id for h in result.hits] == expected
    assert [h.rank for h in result.hits] == [1, 2, 3]


@pytest.mark.parametrize("case", ["kein Einbetter", "keine Vektoren", "Server fehlt", "Modell"])
def test_without_model_or_vectors_the_search_falls_back_to_bm25(
    settings: Settings, layout: Layout, case: str
) -> None:
    embedder: Embedder | None = FakeEmbedder()
    if case != "keine Vektoren":
        _embedded(settings, layout, FakeEmbedder())
    if case == "kein Einbetter":
        embedder = None
    elif case == "Server fehlt":
        embedder = Down()
    elif case == "Modell":
        embedder = FakeEmbedder(digest="f" * 64)  # ein anderes Modell als das der Stücke
    result = search(layout, settings, "Radweg", "embedding", 5, embedder)
    assert result.method == "bm25" and "BM25" in result.note
    assert [h.id for h in result.hits] == ["id1", "id5"]


def test_the_hit_list_names_reference_date_title_and_link(layout: Layout) -> None:
    corpus = pl.read_parquet(layout.corpus)
    from georep.search.query import Hit

    text = describe(Result((Hit(1, 0.75, "id5"),), "bm25", "ohne Modell"), corpus, "Radweg")
    assert text.splitlines() == [
        "Hinweis: ohne Modell",
        '„Radweg" mit BM25: 1 Treffer',
        "  1  0.7500  R/3  2024-01-04  Haushalt",
        "     https://ris.test/f5.pdf",
    ]


def test_the_command_searches_and_says_when_it_falls_back(
    settings: Settings,
    layout: Layout,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _embedded(
        settings, layout, FakeEmbedder()
    )  # die Stücke sind da, der Server für die Frage nicht
    monkeypatch.setattr(cli, "load_settings", lambda **_: settings)
    monkeypatch.setattr(Layout, "from_settings", staticmethod(lambda _: layout))
    monkeypatch.setattr(search_command, "DeferredEmbedder", lambda _: Down())
    assert cli.main(["search", "Radweg", "--method", "bm25", "--n", "1"]) == 0
    out = capsys.readouterr().out
    assert "mit BM25: 1 Treffer" in out and "Hinweis" not in out and "R/0" in out
    assert cli.main(["search", "Radweg"]) == 0  # Vorgabe embedding, ohne Server: BM25
    out = capsys.readouterr().out
    assert out.startswith("Hinweis: ") and "nicht erreichbar" in out and "mit BM25" in out
    assert cli.main(["search", "   "]) == 2
    assert "leer" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main(["search", "Radweg", "--n", "0"])


def test_a_server_that_is_not_allowed_makes_the_command_search_with_bm25(
    settings: Settings,
    layout: Layout,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review Runde 1, N5: der Einbetter entsteht im ``try`` der Suche, nicht davor."""
    _embedded(settings, layout, FakeEmbedder())
    ml = settings.ml.model_copy(update={"base_url": "http://ollama.example:11434"})
    remote = settings.model_copy(update={"ml": ml})
    monkeypatch.setattr(cli, "load_settings", lambda **_: remote)
    monkeypatch.setattr(Layout, "from_settings", staticmethod(lambda _: layout))
    assert cli.main(["search", "Radweg"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Hinweis: ") and "ollama.example" in out and "mit BM25" in out
