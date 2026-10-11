from __future__ import annotations

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
