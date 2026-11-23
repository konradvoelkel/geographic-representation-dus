"""Der Stapellauf (F5): nur Fehlendes rechnen, ``limit``, Fortschritt, Abbruch und Fortsetzen."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import numpy as np
import pytest

from georep.errors import ModelError, ModelUnreachableError, SchemaError
from georep.ml.base import EmbeddingOptions, EmbeddingUse, GenerationOptions, GenerationUse
from georep.ml.batch import (
    BatchReport,
    Progress,
    embed_texts,
    generate_texts,
    progress_log,
    run_batch,
)
from georep.ml.cache import FAILED, CacheKey, ModelCache, input_sha256
from georep.ml.ollama import OllamaClient, OllamaEmbedder
from tests.fakes import FAKE_URL, FakeEmbedder, FakeGenerator, FakeOllama, fake_answer, fake_vector

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
    use = EmbeddingUse(embedder, "dok-1")
    texts = ["eins", "zwei", "eins", "drei"]
    with ModelCache(tmp_path, embedder.name) as cache:
        first = embed_texts(use, cache, texts, batch_size=2)
        again = embed_texts(use, cache, texts, batch_size=2)
    assert first.present.all() and first.vectors.shape == (4, 4)
    assert np.allclose(first.vectors[2], fake_vector("eins", 4), atol=1e-7)
    assert np.array_equal(first.vectors, again.vectors)
    assert embedder.calls == [["eins", "zwei"], ["drei"]]
    assert (again.report.cached, again.report.computed) == (3, 0)


def test_embed_texts_with_limit_marks_what_is_missing_and_tells_the_use(tmp_path: Path) -> None:
    embedder = FakeEmbedder(dimension=4)
    use = EmbeddingUse(embedder, "dok-1")
    with ModelCache(tmp_path, embedder.name) as cache:
        partial = embed_texts(use, cache, ["a", "b", "c"], limit=2)
        assert (use.open, use.limit) == (1, 2)
        use.reset()  # wie run_step vor dem nächsten Lauf des Schritts
        embed_texts(use, cache, ["a", "b", "c"])
    assert partial.present.tolist() == [True, True, False]
    assert not partial.vectors[2].any() and partial.report.left == 1
    # Der zweite Lauf ohne Grenze schließt ab: nichts mehr offen.
    assert (use.open, use.limit) == (0, 0)


def test_another_window_does_not_hit_the_vectors_of_the_first(tmp_path: Path) -> None:
    """Befund 1 des Reviews (Probe 1): mit 64 statt 512 Token kam der Vektor aus dem Cache."""
    wide = FakeEmbedder(dimension=4, options=EmbeddingOptions(num_ctx=512))
    narrow = FakeEmbedder(dimension=4, options=EmbeddingOptions(num_ctx=64))
    with ModelCache(tmp_path, wide.name) as cache:
        embed_texts(EmbeddingUse(wide, "dok-1"), cache, ["langer text"])
        second = embed_texts(EmbeddingUse(narrow, "dok-1"), cache, ["langer text"])
    assert second.report.computed == 1 and narrow.calls == [["langer text"]]


def test_embed_texts_refuses_the_cache_of_another_model(tmp_path: Path) -> None:
    use = EmbeddingUse(FakeEmbedder(), "dok-1")
    with ModelCache(tmp_path, "anderes-modell") as cache, pytest.raises(SchemaError, match="Datei"):
        embed_texts(use, cache, ["a"])


def test_generate_texts_keys_on_system_prompt_and_options(tmp_path: Path) -> None:
    generator = FakeGenerator()
    options = GenerationOptions(num_predict=120)
    use = GenerationUse(generator, "kurz-1", options)
    shorter = GenerationUse(generator, "kurz-1", GenerationOptions(num_predict=60))
    with ModelCache(tmp_path, generator.name) as cache:
        first = generate_texts(use, cache, ["Text A", "Text B"], system="S")
        assert first.texts == [fake_answer("S", "Text A"), fake_answer("S", "Text B")]
        # Anderes System oder andere Optionen: neue Einträge, kein Treffer.
        generate_texts(use, cache, ["Text A"], system="T")
        generate_texts(shorter, cache, ["Text A"], system="S")
        again = generate_texts(use, cache, ["Text A", "Text B"], system="S")
        prompts = {s.prompt for s in cache.stats()}
    assert len(generator.calls) == 4 and again.report.computed == 0
    assert prompts == {use.prompt_key(), shorter.prompt_key()}
    assert use.prompt_key() == f"kurz-1+{options.key()}"


def test_a_cut_answer_is_cached_marked_and_counted(tmp_path: Path) -> None:
    """Befund 2 des Reviews (Probe 2): eine abgeschnittene Antwort lag als vollständig im Cache."""
    generator = FakeGenerator()
    use = GenerationUse(generator, "kurz-1", GenerationOptions(num_predict=2))
    with ModelCache(tmp_path, generator.name) as cache:
        first = generate_texts(use, cache, ["Text A", "Text B"])
        again = generate_texts(use, cache, ["Text A", "Text B"])
    assert first.truncated == [True, True] and first.report.truncated == 2
    assert all(text is not None and len(text.split()) == 2 for text in first.texts)
    # Aus dem Cache: nichts neu gerechnet, die Markierung bleibt.
    assert again.report.computed == 0 and again.truncated == [True, True]
    assert "2 abgeschnitten" in first.report.line()


def test_generate_texts_with_limit_leaves_none(tmp_path: Path) -> None:
    generator = FakeGenerator()
    use = GenerationUse(generator, "kurz-1", GenerationOptions())
    with ModelCache(tmp_path, generator.name) as cache:
        partial = generate_texts(use, cache, ["a", "b"], limit=1)
    assert partial.texts[0] is not None and partial.texts[1] is None
    assert (use.open, use.limit) == (1, 1)


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [(30.0, "Rest ≈ 30 s"), (600.0, "Rest ≈ 10 min"), (27_000.0, "Rest ≈ 7 h 30 min")],
)
def test_the_estimate_reads_in_seconds_minutes_or_hours(elapsed: float, expected: str) -> None:
    halfway = Progress(label="x", done=1, todo=2, cached=0, total=2, elapsed_s=elapsed)
    assert expected in halfway.line()


def test_the_report_names_what_is_left() -> None:
    report = BatchReport(total=10, cached=4, computed=3, left=3, seconds=12.34)
    assert report.line() == "10 Eingaben: 4 aus dem Cache, 3 neu, 3 offen in 12.3 s"
    done = BatchReport(total=2, cached=2, computed=0, left=0, seconds=0.0)
    assert done.line() == "2 Eingaben: 2 aus dem Cache, 0 neu in 0.0 s"


def _poisoned(
    computed: list[list[int]], poison: set[int]
) -> Callable[[Sequence[int]], list[bytes]]:
    """Wie ``_values``, aber ein Stapel mit einem Index aus ``poison`` wird abgewiesen."""

    def compute(indices: Sequence[int]) -> list[bytes]:
        computed.append(list(indices))
        if poison & set(indices):
            raise ModelError("400 input rejected")
        return [f"wert {i}".encode() for i in indices]

    return compute


def test_a_rejected_text_fails_alone_and_the_run_goes_on(cache: ModelCache) -> None:
    """Befund 7 des Reviews (Probe 9): ein dauerhaft abgewiesener Text hielt den Lauf an."""
    keys = [input_sha256(str(i)) for i in range(10)]
    computed: list[list[int]] = []
    report = run_batch(keys, _poisoned(computed, {3}), cache, KEY, batch_size=2)
    # Der Stapel [2, 3] scheitert und wird in Einzeltexte zerlegt; danach geht es weiter.
    assert computed == [[0, 1], [2, 3], [2], [3], [4, 5], [6, 7], [8, 9]]
    assert (report.computed, report.failed, report.left) == (9, 1, 0)
    assert report.failures == ((3, "400 input rejected"),)
    assert "1 gescheitert" in report.line()
    again = run_batch(keys, _poisoned(computed, {3}), cache, KEY, batch_size=2)
    assert (again.cached, again.computed, again.failed) == (9, 0, 1)


def test_a_missing_server_still_stops_the_run(cache: ModelCache) -> None:
    keys = [input_sha256(str(i)) for i in range(6)]

    def compute(indices: Sequence[int]) -> list[bytes]:
        if 4 in indices:
            raise ModelUnreachableError("ollama nicht erreichbar")
        return [b"x" for _ in indices]

    with pytest.raises(ModelUnreachableError):
        run_batch(keys, compute, cache, KEY, batch_size=2)
    assert cache.known(KEY) == set(keys[:4])


def test_ten_new_failures_in_a_row_stop_the_run_without_losing_anything(cache: ModelCache) -> None:
    """Review F5, vierte Runde, M1: der Lauf hält an und berichtet, statt abzubrechen."""
    keys = [input_sha256(str(i)) for i in range(30)]
    computed: list[list[int]] = []
    report = run_batch(keys, _poisoned(computed, set(range(30))), cache, KEY, batch_size=1)
    assert len(computed) == 10 and "10 Fehlschläge in Folge" in report.stopped
    assert (report.computed, report.failed, report.left) == (0, 10, 20)
    assert "abgebrochen" in report.line()


def test_embed_texts_marks_a_rejected_text_and_settles_it(tmp_path: Path) -> None:
    """Eine Abweisung ist erledigt, nicht offen (Review F5, dritte Runde, N1)."""
    embedder = FakeEmbedder(dimension=4, rejects={"kaputt"})
    use = EmbeddingUse(embedder, "dok-1")
    with ModelCache(tmp_path, embedder.name) as cache:
        found = embed_texts(use, cache, ["eins", "kaputt", "zwei"], batch_size=3)
    assert found.present.tolist() == [True, False, True]
    assert found.report.rejected[0][0] == 1 and found.report.failures == ()
    assert (use.open, use.failed, use.rejected) == (0, 0, 1)
    assert use.stamp()["rejected"] == 1


def test_a_text_that_times_out_fails_alone_and_the_run_goes_on(tmp_path: Path) -> None:
    """Review F5, N4: ein Lese-Timeout bei einem Text brach den ganzen Lauf ab."""
    server = FakeOllama(dimension=4, slow=["langsam"])
    client = OllamaClient(FAKE_URL, transport=server, sleep=lambda s: None)
    use = EmbeddingUse(OllamaEmbedder(client, "fake-embed", dimension=4), "dok-1")
    with ModelCache(tmp_path, use.name) as cache:
        found = embed_texts(use, cache, ["eins", "langsam", "zwei"], batch_size=3)
    assert found.present.tolist() == [True, False, True]
    assert found.report.failures[0][0] == 1 and "Zeitüberschreitung" in found.report.failures[0][1]


# --- abgewiesene Eingaben (Review F5, dritte Runde, N1) ----------------------------------------


def test_known_rejections_are_skipped_and_do_not_block_later_runs(tmp_path: Path) -> None:
    """Probe des Reviewers (p_rerun): 24 Texte, 12 abgewiesen; ab Lauf 2 hieß es „10 in Folge"."""
    texts = [f"bad{i}" if i % 2 else f"ok{i}" for i in range(24)]
    embedder = FakeEmbedder(dimension=4, rejects={t for t in texts if t.startswith("bad")})
    use = EmbeddingUse(embedder, "dok-1")
    with ModelCache(tmp_path, embedder.name) as cache:
        first = embed_texts(use, cache, texts, batch_size=4)
        calls = len(embedder.calls)
        use.reset()  # wie run_step vor dem nächsten Lauf des Schritts
        second = embed_texts(use, cache, texts, batch_size=4)
    assert (first.report.computed, len(first.report.rejected), first.report.failed) == (12, 12, 0)
    assert first.report.rejected[0] == (1, "400 input rejected")
    assert "12 abgewiesen" in first.report.line()
    assert (second.report.cached, second.report.computed, len(second.report.rejected)) == (
        12,
        0,
        12,
    )
    assert len(embedder.calls) == calls  # nichts neu gefragt
    assert (use.open, use.failed, use.rejected) == (0, 0, 12)


def test_ten_rejections_in_front_stop_one_run_but_not_the_next(tmp_path: Path) -> None:
    texts = [f"bad{i}" for i in range(10)] + ["ok"]
    embedder = FakeEmbedder(dimension=4, rejects=set(texts[:10]))
    use = EmbeddingUse(embedder, "dok-1")
    with ModelCache(tmp_path, embedder.name) as cache:
        first = embed_texts(use, cache, texts, batch_size=1)
        again = embed_texts(use, cache, texts, batch_size=1)
    assert "10 Fehlschläge in Folge" in first.report.stopped and first.report.left == 1
    assert again.report.stopped == "" and again.present.tolist() == [False] * 10 + [True]
    assert len(again.report.rejected) == 10 and again.report.computed == 1


def test_retry_rejected_asks_again_and_forgets_a_rejection_that_passes(tmp_path: Path) -> None:
    embedder = FakeEmbedder(dimension=4, rejects={"lang"})
    use = EmbeddingUse(embedder, "dok-1")
    with ModelCache(tmp_path, embedder.name) as cache:
        embed_texts(use, cache, ["kurz", "lang"])
        embedder.rejects = frozenset()
        skipped = embed_texts(use, cache, ["kurz", "lang"])
        use.reset(retry_rejected=True)  # wie run_step mit ml.retry_rejected
        retried = embed_texts(use, cache, ["kurz", "lang"])
        use.reset()
        settled = embed_texts(use, cache, ["kurz", "lang"])
    assert len(skipped.report.rejected) == 1 and skipped.report.computed == 0
    assert retried.report.computed == 1 and retried.report.rejected == ()
    assert settled.present.all() and settled.report.rejected == ()


def test_a_rejection_from_the_server_is_recorded_with_its_reason(tmp_path: Path) -> None:
    server = FakeOllama(dimension=4, rejects=["zu lang"])
    client = OllamaClient(FAKE_URL, transport=server, sleep=lambda s: None)
    use = EmbeddingUse(OllamaEmbedder(client, "fake-embed", dimension=4), "dok-1")
    with ModelCache(tmp_path, use.name) as cache:
        found = embed_texts(use, cache, ["kurz", "zu lang"], batch_size=2)
    ((index, reason),) = found.report.rejected
    assert index == 1 and "input length exceeds context" in reason
    assert found.report.failures == ()


def test_failed_inputs_go_last_and_do_not_use_up_the_limit(cache: ModelCache) -> None:
    """Review F5, dritte Runde, N2: drei Fehlschläge vorne, ``--limit 3``, und kein Lauf kam weiter."""
    keys = [input_sha256(str(i)) for i in range(9)]
    computed: list[list[int]] = []
    runs = [run_batch(keys, _poisoned(computed, {0, 1, 2}), cache, KEY, limit=3) for _ in range(4)]
    assert [(r.computed, r.failed) for r in runs] == [(0, 3), (3, 0), (3, 0), (0, 3)]
    assert [i for batch in computed[3:9] for i in batch] == [3, 4, 5, 6, 7, 8]
    assert {kind for kind, _ in cache.failures(KEY).values()} == {FAILED}
    assert set(cache.failures(KEY)) == set(keys[:3])


def test_a_failed_input_that_succeeds_later_is_forgotten(cache: ModelCache) -> None:
    keys = [input_sha256(str(i)) for i in range(3)]
    run_batch(keys, _poisoned([], {1}), cache, KEY)
    assert set(cache.failures(KEY)) == {keys[1]}
    report = run_batch(keys, _poisoned([], set()), cache, KEY)
    assert report.computed == 1 and cache.failures(KEY) == {}


def test_known_failures_do_not_count_towards_ten_in_a_row(tmp_path: Path) -> None:
    """Review F5, vierte Runde, M1 (Probe c): zwölf bekannte Fehlschläge am Ende hielten jeden Lauf an."""
    texts = [f"s{i}" if i % 2 else f"ok{i}" for i in range(24)]
    failing = {t for t in texts if t.startswith("s")}
    computed: list[list[int]] = []
    keys = [input_sha256(t) for t in texts]
    poison = {i for i, t in enumerate(texts) if t in failing}
    with ModelCache(tmp_path, KEY.model) as cache:
        first = run_batch(keys, _poisoned(computed, poison), cache, KEY, batch_size=4)
        second = run_batch(keys, _poisoned(computed, poison), cache, KEY, batch_size=4)
    assert (first.computed, first.failed, first.stopped) == (12, 12, "")
    assert (second.cached, second.failed, second.stopped) == (12, 12, "")
