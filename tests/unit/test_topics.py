"""Das Themenmodell auf synthetischen Texten: drei Wortfamilien, drei Themen.

Einzelne Zahlen des Modells prüft kein Test: zwischen Rechnern (andere BLAS-Bibliothek) weichen
sie in den letzten Stellen ab. Geprüft werden die Eigenschaften, auf denen die Gewichtung aufbaut:
genau ``k`` Themen, Anteile mit Zeilensumme 1, Labels aus den Wörtern der Familie, zwei Aufrufe im
selben Prozess gleich.
"""

from __future__ import annotations

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from georep.analysis.topics import dominant_topics, fit_topics, load_stop_words
from georep.errors import EmptyResultError
from georep.settings import Topics

FAMILIES = (
    ("strasse", "verkehr", "parken", "radweg"),
    ("schule", "kita", "bildung", "unterricht"),
    ("grundstueck", "bauvorhaben", "stellplatz", "bebauung"),
)


def _corpus(documents: int = 12, filler: str = "") -> pl.DataFrame:
    rows = [
        {
            "id": f"p{i:02d}",
            "text": " ".join(FAMILIES[i % len(FAMILIES)] * 2) + f" wort{i} {filler}",
        }
        for i in range(documents)
    ]
    return pl.DataFrame(rows, schema={"id": pl.String, "text": pl.String})


def _settings(**overrides: object) -> Topics:
    base: dict[str, object] = {
        "k": 3,
        "min_df": 1,
        "max_df": 1.0,
        "max_features": 100,
        "top_words": 4,
        "stop_words": "de",
        "random_state": 0,
    }
    return Topics(**(base | overrides))  # type: ignore[arg-type]


def test_stop_words_are_lowercase_and_cover_the_function_words() -> None:
    words = load_stop_words("de")
    assert len(words) > 150
    assert {"und", "oder", "sich", "nicht", "dass", "auch"} <= words
    assert all(word == word.strip().lower() and word for word in words)
    assert "düsseldorf" not in words and "beschluss" not in words  # Eigennamen, Sachwörter
    assert load_stop_words("") == frozenset()


def test_an_unknown_language_is_a_domain_error() -> None:
    with pytest.raises(EmptyResultError, match="Stoppwortliste"):
        load_stop_words("xx")


def test_each_word_family_dominates_one_topic_and_appears_in_its_label() -> None:
    model = fit_topics(_corpus(), _settings())
    assert model.topics.height == 3
    labels = [set(words) for words in model.topics.get_column("woerter").to_list()]
    for family in FAMILIES:
        assert any(set(family) <= label for label in labels), (family, labels)
    assert model.topics.get_column("dokumente").to_list() == [4, 4, 4]
    assert model.topics.get_column("thema").to_list() == [0, 1, 2]


def test_the_shares_of_a_document_sum_to_one() -> None:
    model = fit_topics(_corpus(), _settings())
    sums = model.shares.get_column("anteile").list.sum().to_list()
    assert all(value == pytest.approx(1.0, abs=1e-9) for value in sums)
    assert model.shares.get_column("id").to_list() == sorted(_corpus().get_column("id").to_list())


def test_two_runs_give_the_same_frames() -> None:
    first = fit_topics(_corpus(), _settings())
    second = fit_topics(_corpus(), _settings())
    assert_frame_equal(first.shares, second.shares)
    assert_frame_equal(first.topics, second.topics)


def test_documents_without_text_are_left_out() -> None:
    corpus = pl.concat(
        [
            _corpus(),
            pl.DataFrame(
                {"id": ["p99"], "text": [""]}, schema={"id": pl.String, "text": pl.String}
            ),
        ]
    )
    model = fit_topics(corpus, _settings())
    assert "p99" not in model.shares.get_column("id").to_list()
    assert int(model.topics.get_column("dokumente").sum()) == 12


def test_fewer_documents_than_topics_is_a_domain_error() -> None:
    with pytest.raises(EmptyResultError, match="Dokumente mit Text"):
        fit_topics(_corpus(2), _settings())


def test_an_empty_vocabulary_is_a_domain_error() -> None:
    """Nur Stoppwörter und Zahlen: nach dem Beschneiden bleibt kein Wort übrig."""
    corpus = pl.DataFrame(
        {"id": [f"p{i}" for i in range(5)], "text": ["und oder 2025"] * 5},
        schema={"id": pl.String, "text": pl.String},
    )
    with pytest.raises(EmptyResultError, match="Kein Wort"):
        fit_topics(corpus, _settings(min_df=1))


def test_dominant_topic_breaks_a_tie_for_the_smaller_number() -> None:
    shares = pl.DataFrame(
        {"id": ["p2", "p1"], "anteile": [[0.5, 0.5], [0.25, 0.75]]},
        schema={"id": pl.String, "anteile": pl.List(pl.Float64)},
    )
    found = dominant_topics(shares)
    assert found.get_column("id").to_list() == ["p1", "p2"]  # sortiert
    assert dict(found.select("id", "thema").iter_rows()) == {"p1": 1, "p2": 0}
    assert dict(found.select("id", "anteil").iter_rows()) == {"p1": 0.75, "p2": 0.5}


def test_dominant_topic_rounds_the_share() -> None:
    shares = pl.DataFrame(
        {"id": ["p1"], "anteile": [[0.123456789, 0.876543211]]},
        schema={"id": pl.String, "anteile": pl.List(pl.Float64)},
    )
    assert dominant_topics(shares).get_column("anteil").to_list() == [0.8765]


def test_a_vocabulary_smaller_than_k_is_a_domain_error() -> None:
    """nndsvda verlangt ``k <= min(Dokumente, Wörter)``; zu wenige Wörter sind kein Programmfehler."""
    corpus = pl.DataFrame(
        {"id": [f"p{i}" for i in range(5)], "text": ["strasse verkehr"] * 5},
        schema={"id": pl.String, "text": pl.String},
    )
    with pytest.raises(EmptyResultError, match="Wörter"):
        fit_topics(corpus, _settings(k=4, min_df=1))
