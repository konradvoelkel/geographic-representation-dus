from __future__ import annotations

import pytest

import src.config as cfg


def test_default_query_targets_duesseldorf_in_german() -> None:
    assert "wd:Q1718." in cfg.QUERY
    assert "https://de.wikipedia.org/" in cfg.QUERY
    assert 'wikibase:language "de"' in cfg.QUERY


def test_query_follows_entity_and_language() -> None:
    query = cfg.build_sparql_query("Q2066", "fr")  # Neuss, auf Französisch
    assert "wd:Q2066." in query
    assert "https://fr.wikipedia.org/" in query
    assert 'wikibase:language "fr"' in query
    assert "Q1718" not in query


def test_log_level_defaults_to_info() -> None:
    assert cfg.log_level_from_env(env={}) == "INFO"


def test_log_level_reads_env_case_insensitively() -> None:
    assert cfg.log_level_from_env(env={"GEOREP_LOG_LEVEL": "debug"}) == "DEBUG"


def test_unknown_log_level_is_an_error() -> None:
    with pytest.raises(ValueError, match="GEOREP_LOG_LEVEL"):
        cfg.log_level_from_env(env={"GEOREP_LOG_LEVEL": "laut"})
