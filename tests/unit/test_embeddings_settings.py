"""Vorhaben 18: die Settings ``[embeddings]`` und die Präfixe in ``[ml.embedding]``."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from georep.settings import Embeddings, Settings, load_settings

NOWHERE = Path("/nonexistent")


def test_the_defaults_are_the_measured_version_and_switched_off(
    default_settings: Settings,
) -> None:
    defaults = Embeddings()
    assert not defaults.enabled
    assert (defaults.chunk_chars, defaults.title_chars, defaults.overlap_chars) == (1600, 200, 200)
    assert (defaults.document_chunks, defaults.neighbors) == (3, 10)
    assert (defaults.bm25.k1, defaults.bm25.b, defaults.rrf_k, defaults.fusion_depth) == (
        1.2,
        0.75,
        60,
        100,
    )
    assert defaults.neighbors_package is None
    embedding = default_settings.ml.embedding
    assert (embedding.document_prefix, embedding.query_prefix) == (
        "search_document: ",
        "search_query: ",
    )


def test_a_title_must_leave_room_for_more_than_the_overlap() -> None:
    with pytest.raises(ValidationError, match="Rumpf"):
        Embeddings(chunk_chars=202, title_chars=200)
    with pytest.raises(ValidationError, match="overlap_chars"):
        Embeddings(chunk_chars=500, title_chars=200, overlap_chars=298)
    assert Embeddings(chunk_chars=500, title_chars=200, overlap_chars=297).overlap_chars == 297


def test_the_package_path_and_the_prefixes_stay_out_of_the_fingerprint(
    default_settings: Settings,
) -> None:
    base = default_settings.fingerprint()
    packaged = default_settings.embeddings.model_copy(
        update={"neighbors_package": Path("anderswo/aehnliche_dokumente.parquet")}
    )
    assert default_settings.model_copy(update={"embeddings": packaged}).fingerprint() == base
    embedding = default_settings.ml.embedding.model_copy(update={"query_prefix": "frage: "})
    ml = default_settings.ml.model_copy(update={"embedding": embedding})
    assert default_settings.model_copy(update={"ml": ml}).fingerprint() == base
    shorter = default_settings.embeddings.model_copy(update={"neighbors": 5})
    assert default_settings.model_copy(update={"embeddings": shorter}).fingerprint() != base


def test_both_cities_switch_the_steps_on() -> None:
    """Die Hauptperiode und ihre Perioden erben den Schalter; Mönchengladbach prüft die Neutralität."""
    for profile in ("duesseldorf", "duesseldorf-2014", "duesseldorf-2025", "moenchengladbach"):
        assert load_settings(profile=profile, cwd=NOWHERE).embeddings.enabled, profile


def test_what_only_the_search_command_reads_stays_out_of_the_fingerprint(
    default_settings: Settings,
) -> None:
    """Review Runde 1, N4: BM25, ``rrf_k`` und ``fusion_depth`` liest nur ``georep search``.

    Kein Schritt hängt an ihnen; im Fingerprint ließe jede Änderung die ganze Kette neu laufen.
    """
    base = default_settings.fingerprint()
    cfg = default_settings.embeddings
    for change in (
        {"bm25": cfg.bm25.model_copy(update={"k1": 1.5, "b": 0.5})},
        {"rrf_k": 10},
        {"fusion_depth": 20},
    ):
        other = default_settings.model_copy(update={"embeddings": cfg.model_copy(update=change)})
        assert other.fingerprint() == base, change
