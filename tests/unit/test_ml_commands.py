"""``georep ml status`` und ``georep ml bench`` (F5) gegen den Server als Tabelle."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep import cli
from georep.errors import ModelError
from georep.layout import Layout
from georep.ml import commands
from georep.ml.cache import CacheKey, ModelCache
from georep.ml.ollama import OllamaClient
from georep.settings import load_settings
from tests.fakes import FakeOllama, FakeSession, response

URL = "http://ollama.test"


class Clock:
    def __init__(self, step: float = 0.5) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


@pytest.fixture
def project(tmp_path: Path, mini_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\nreference_root = "{mini_root}"\n'
        f'[ml]\nbase_url = "{URL}"\n'
        '[ml.embedding]\nmodel = "fake-embed"\ndimension = 8\n'
        '[ml.generation]\nmodel = "fake-chat"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _corpus(project: Path, rows: int = 5) -> Layout:
    layout = Layout.from_settings(load_settings(cwd=project))
    layout.ensure_dirs()
    texts = [f"vorlage {i} " + "wort " * (10 * i) for i in range(rows)] + [""]
    pl.DataFrame(
        {"id": [f"https://ris.test/paper/{i}" for i in range(rows + 1)], "text": texts}
    ).write_parquet(layout.corpus)
    return layout


def _serve(monkeypatch: pytest.MonkeyPatch, server: FakeOllama) -> None:
    monkeypatch.setattr(commands, "make_transport", lambda: server)


def test_status_names_server_models_memory_and_cache(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    layout = Layout.from_settings(load_settings(cwd=project))
    with ModelCache(layout.ml_cache, "fake-embed") as cache:
        cache.put_many(CacheKey("fake-embed:latest", "e" * 64, "dok-1"), [("a" * 64, b"1234")])
    _serve(monkeypatch, FakeOllama(loaded=["fake-chat:latest"]))
    assert cli.main(["ml", "status"]) == 0
    out = capsys.readouterr().out
    assert f"ollama 0.0-fake unter {URL}" in out
    assert "Einbettung" in out and "fake-embed:latest" in out and "Digest eeeeeeeeeeee" in out
    assert "Generierung" in out and "fake-chat:latest" in out
    assert "im Speicher: fake-chat:latest" in out
    assert "dok-1" in out and "1 Einträge" in out


def test_status_says_which_model_is_missing(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    server = FakeOllama()
    del server.models["fake-chat:latest"]
    _serve(monkeypatch, server)
    assert cli.main(["ml", "status"]) == 1
    assert "fehlt; `ollama pull fake-chat`" in capsys.readouterr().out


def test_status_without_server_still_shows_the_cache(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _serve(monkeypatch, FakeOllama(down=True))
    assert cli.main(["ml", "status"]) == 1
    out = capsys.readouterr().out
    assert "nicht erreichbar" in out and "Cache" in out and "leer" in out


def test_bench_of_an_embedding_model_measures_single_and_batched_calls(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _corpus(project)
    server = FakeOllama()
    _serve(monkeypatch, server)
    assert cli.main(["ml", "bench", "fake-embed", "--n", "3", "--chars", "40"]) == 0
    out = capsys.readouterr().out
    embeds = [payload for path, payload in server.requests if path == "/api/embed"]
    # Aufwärmen, drei einzeln, einmal alle drei als Stapel
    assert [len(p["input"]) for p in embeds] == [1, 1, 1, 1, 3]
    assert all(len(text) <= 40 for p in embeds for text in p["input"])
    assert "3 Dokumente" in out and "Token/s" in out and "Hochrechnung" in out
    assert "5 Dokumente mit Text" in out and "Stapel" in out


def test_bench_of_a_generator_caps_the_answer_and_projects_the_corpus(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _corpus(project)
    server = FakeOllama()
    _serve(monkeypatch, server)
    assert cli.main(["ml", "bench", "fake-chat", "--n", "2", "--max-tokens", "3"]) == 0
    out = capsys.readouterr().out
    chats = [payload for path, payload in server.requests if path == "/api/chat"]
    assert len(chats) == 3  # Aufwärmen und zwei Dokumente
    assert chats[0]["options"]["num_predict"] == 1
    assert all(p["options"]["num_predict"] == 3 and p["think"] is False for p in chats[1:])
    assert "zusammen" in chats[1]["messages"][-1]["content"]
    assert "Ausgabe" in out and "abgeschnitten: 2 von 2" in out and "Hochrechnung" in out


def test_bench_takes_every_document_when_there_are_fewer(project: Path) -> None:
    layout = _corpus(project, rows=2)
    report = commands.bench(
        OllamaClient(URL, transport=FakeOllama()),
        "fake-embed",
        pl.read_parquet(layout.corpus),
        n=20,
        chars=100,
        max_tokens=10,
        seed=0,
        settings=load_settings(cwd=project).ml,
        clock=Clock(),
    )
    assert len(report.rows) == 2 and report.corpus_documents == 2
    assert report.mean_seconds == pytest.approx(0.5)
    assert "Hochrechnung: 2 Dokumente mit Text" in "\n".join(report.lines())


def test_bench_refuses_a_model_that_neither_embeds_nor_completes(project: Path) -> None:
    layout = _corpus(project)
    server = FakeOllama({"vision:latest": {"digest": "f" * 64, "capabilities": ["vision"]}})
    with pytest.raises(ModelError, match=r"weder Einbettung noch Text"):
        commands.bench(
            OllamaClient(URL, transport=server),
            "vision",
            pl.read_parquet(layout.corpus),
            n=2,
            chars=100,
            max_tokens=10,
            seed=0,
            settings=load_settings(cwd=project).ml,
        )


def test_bench_without_corpus_is_a_missing_input(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _serve(monkeypatch, FakeOllama())
    assert cli.main(["ml", "bench", "fake-embed"]) == 1
    assert "georep run corpus" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("count", "expected"),
    [(512, "512 B"), (2_048, "2.0 KB"), (957_680_763, "957.7 MB"), (17_420_432_739, "17.4 GB")],
)
def test_sizes_read_in_the_largest_fitting_unit(count: int, expected: str) -> None:
    assert commands._size(count) == expected


def test_status_reports_a_broken_answer_after_the_version_and_still_shows_the_cache(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Befund 8 des Reviews: nur ``version`` stand im ``try``, eine kaputte Tag-Liste brach ab."""
    session = FakeSession(
        {
            f"{URL}/api/version": response(f"{URL}/api/version", payload={"version": "0.0-fake"}),
            f"{URL}/api/tags": response(f"{URL}/api/tags", content=b"<html>kein JSON</html>"),
        }
    )
    monkeypatch.setattr(commands, "make_transport", lambda: session)
    assert cli.main(["ml", "status"]) == 1
    out = capsys.readouterr().out
    assert "unbrauchbar" in out and "Cache" in out
