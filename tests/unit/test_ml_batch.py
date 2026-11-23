"""Der Stapellauf (F5): nur Fehlendes rechnen, ``limit``, Fortschritt, Abbruch und Fortsetzen."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import numpy as np
import pytest

from georep.errors import ModelError, SchemaError
from georep.ml.base import GenerationOptions
from georep.ml.batch import (
    BatchReport,
    Progress,
    embed_texts,
    generate_texts,
    progress_log,
    run_batch,
)
from georep.ml.cache import CacheKey, ModelCache, input_sha256
from tests.fakes import FakeEmbedder, FakeGenerator, fake_answer, fake_vector

KEY = CacheKey("fake-embed:latest", "e" * 64, "p-1")


class Clock:
    """Eine Uhr, die bei jedem Ablesen um ``step`` Sekunden vorgeht."""

    def __init__(self, step: float = 1.0) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[ModelCache]:
    with ModelCache(tmp_path / "ml", KEY.model) as opened:
        yield opened


def _values(computed: list[list[int]]) -> Callable[[Sequence[int]], list[bytes]]:
    """Rechnet „wert i" je Index und hält die Stapel fest."""

    def compute(indices: Sequence[int]) -> list[bytes]:
        computed.append(list(indices))
        return [f"wert {i}".encode() for i in indices]

    return compute


def test_only_missing_and_distinct_inputs_are_computed(cache: ModelCache) -> None:
    keys = [input_sha256(t) for t in ["a", "b", "a", "c", "d"]]
    cache.put_many(KEY, [(keys[1], b"alt")])
    computed: list[list[int]] = []
    report = run_batch(keys, _values(computed), cache, KEY, batch_size=2)
    # "a" zweimal, aber einmal gerechnet (an der ersten Stelle); "b" lag schon im Cache.
    assert computed == [[0, 3], [4]]
    assert report == BatchReport(total=4, cached=1, computed=3, left=0, seconds=report.seconds)
    assert cache.get_many(KEY, [keys[0]]) == {keys[0]: b"wert 0"}


def test_limit_stops_after_so_many_new_inputs_and_the_next_run_continues(
    cache: ModelCache,
) -> None:
    keys = [input_sha256(str(i)) for i in range(7)]
    computed: list[list[int]] = []
    first = run_batch(keys, _values(computed), cache, KEY, batch_size=2, limit=3)
    assert (first.computed, first.left) == (3, 4) and computed == [[0, 1], [2]]
    second = run_batch(keys, _values(computed), cache, KEY, batch_size=2)
    assert (second.cached, second.computed, second.left) == (3, 4, 0)
    assert computed[2:] == [[3, 4], [5, 6]]


def test_an_abort_keeps_every_finished_batch(cache: ModelCache) -> None:
    keys = [input_sha256(str(i)) for i in range(6)]

    def compute(indices: Sequence[int]) -> list[bytes]:
        if 4 in indices:
            raise KeyboardInterrupt
        return [b"x" for _ in indices]

    with pytest.raises(KeyboardInterrupt):
        run_batch(keys, compute, cache, KEY, batch_size=2)
    assert cache.known(KEY) == set(keys[:4])


def test_a_compute_that_returns_the_wrong_count_is_a_model_error(cache: ModelCache) -> None:
    with pytest.raises(ModelError, match=r"1 Werte für 2 Eingaben"):
        run_batch(["a" * 64, "b" * 64], lambda idx: [b"x"], cache, KEY, batch_size=2)
    assert cache.known(KEY) == set()


def test_progress_reports_each_batch_with_an_estimate(cache: ModelCache) -> None:
    seen: list[Progress] = []
    keys = [input_sha256(str(i)) for i in range(5)]
    cache.put_many(KEY, [(keys[0], b"alt")])
    run_batch(
        keys,
        lambda idx: [b"x"] * len(idx),
        cache,
        KEY,
        batch_size=2,
        progress=seen.append,
        clock=Clock(),
    )
    assert [(p.done, p.todo, p.cached, p.total) for p in seen] == [(2, 4, 1, 5), (4, 4, 1, 5)]
    # Eine Sekunde je Ablesen: nach dem ersten Stapel 1 s für 2, also 1 s für die übrigen 2.
    assert seen[0].eta_s == pytest.approx(1.0) and seen[-1].eta_s == 0.0
    assert "2/4 neu" in seen[0].line() and "1 aus dem Cache" in seen[0].line()


def test_progress_without_work_has_no_estimate() -> None:
    idle = Progress(label="x", done=0, todo=0, cached=3, total=3, elapsed_s=0.0)
    assert idle.eta_s is None and "nichts zu rechnen" in idle.line()


def test_progress_log_speaks_at_most_every_so_many_seconds() -> None:
    lines: list[str] = []
    clock = Clock(step=10.0)
    log = progress_log(every_s=25.0, clock=clock, write=lines.append)
    for done in range(1, 7):
        log(Progress(label="t", done=done, todo=6, cached=0, total=6, elapsed_s=done))
    # Ablesungen bei 10, 20, … 60 s: geschrieben wird beim ersten, nach 25 s Ruhe und am Ende.
    assert [line.split(":")[0] for line in lines] == ["t", "t", "t"]
    assert "6/6 neu" in lines[-1]


def test_embed_texts_returns_vectors_in_input_order_and_reuses_the_cache(tmp_path: Path) -> None:
    embedder = FakeEmbedder(dimension=4)
    texts = ["eins", "zwei", "eins", "drei"]
    with ModelCache(tmp_path, embedder.name) as cache:
        first = embed_texts(embedder, cache, texts, prompt="dok-1", batch_size=2)
        again = embed_texts(embedder, cache, texts, prompt="dok-1", batch_size=2)
    assert first.present.all() and first.vectors.shape == (4, 4)
    assert np.allclose(first.vectors[2], fake_vector("eins", 4), atol=1e-7)
    assert np.array_equal(first.vectors, again.vectors)
    assert embedder.calls == [["eins", "zwei"], ["drei"]]
    assert (again.report.cached, again.report.computed) == (3, 0)


def test_embed_texts_with_limit_marks_what_is_missing(tmp_path: Path) -> None:
    embedder = FakeEmbedder(dimension=4)
    with ModelCache(tmp_path, embedder.name) as cache:
        partial = embed_texts(embedder, cache, ["a", "b", "c"], prompt="dok-1", limit=2)
    assert partial.present.tolist() == [True, True, False]
    assert not partial.vectors[2].any() and partial.report.left == 1


def test_embed_texts_refuses_the_cache_of_another_model(tmp_path: Path) -> None:
    with ModelCache(tmp_path, "anderes-modell") as cache, pytest.raises(SchemaError, match="Datei"):
        embed_texts(FakeEmbedder(), cache, ["a"], prompt="dok-1")


def test_generate_texts_keys_on_system_prompt_and_options(tmp_path: Path) -> None:
    generator = FakeGenerator()
    options = GenerationOptions(num_predict=120)
    with ModelCache(tmp_path, generator.name) as cache:
        first = generate_texts(
            generator, cache, ["Text A", "Text B"], system="S", prompt="kurz-1", options=options
        )
        assert first.texts == [fake_answer("S", "Text A"), fake_answer("S", "Text B")]
        # Anderes System oder andere Optionen: neue Einträge, kein Treffer.
        generate_texts(generator, cache, ["Text A"], system="T", prompt="kurz-1", options=options)
        generate_texts(
            generator,
            cache,
            ["Text A"],
            system="S",
            prompt="kurz-1",
            options=GenerationOptions(num_predict=60),
        )
        again = generate_texts(
            generator, cache, ["Text A", "Text B"], system="S", prompt="kurz-1", options=options
        )
        prompts = {s.prompt for s in cache.stats()}
    assert len(generator.calls) == 4 and again.report.computed == 0
    assert prompts == {
        f"kurz-1+{options.key()}",
        f"kurz-1+{GenerationOptions(num_predict=60).key()}",
    }


def test_generate_texts_with_limit_leaves_none(tmp_path: Path) -> None:
    generator = FakeGenerator()
    with ModelCache(tmp_path, generator.name) as cache:
        partial = generate_texts(
            generator, cache, ["a", "b"], prompt="kurz-1", options=GenerationOptions(), limit=1
        )
    assert partial.texts[0] is not None and partial.texts[1] is None


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [(30.0, "Rest ≈ 30 s"), (600.0, "Rest ≈ 10 min"), (27_000.0, "Rest ≈ 7 h 30 min")],
)
def test_the_estimate_reads_in_seconds_minutes_or_hours(elapsed: float, expected: str) -> None:
    halfway = Progress(label="x", done=1, todo=2, cached=0, total=2, elapsed_s=elapsed)
    assert expected in halfway.line()


def test_the_report_names_what_is_left() -> None:
    report = BatchReport(total=10, cached=4, computed=3, left=3, seconds=12.34)
    assert report.line() == "10 Eingaben: 4 aus dem Cache, 3 neu, 3 offen (limit) in 12.3 s"
    done = BatchReport(total=2, cached=2, computed=0, left=0, seconds=0.0)
    assert done.line() == "2 Eingaben: 2 aus dem Cache, 0 neu in 0.0 s"
