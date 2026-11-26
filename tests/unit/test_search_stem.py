"""Vorhaben 18: der Snowball-Stemmer für Deutsch gegen die Beispielliste des Projekts.

Die Liste ist die der klassischen Fassung (vor Snowball 3.0), die die Messung benutzt hat; im Repo
liegt jedes 17. Paar (``tests/fixtures/snowball/README.md``: Quelle, Commit, Lizenz, Prüfsummen).
"""

from __future__ import annotations

import hashlib

import pytest

from georep.search.stem import stem
from tests.conftest import REPO

FIXTURE = REPO / "tests" / "fixtures" / "snowball" / "deutsch.tsv"


def _pairs() -> list[tuple[str, str]]:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    return [(word, root) for word, root in (line.split("\t") for line in lines)]


def test_the_fixture_is_the_subset_its_readme_names() -> None:
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert digest == "fa0bf3b910764147ae57076ac67c901451a7cb23c64ffe2260f340975c47e7ba"
    assert len(_pairs()) == 2061


def test_every_pair_of_the_list() -> None:
    wrong = [(word, root, stem(word)) for word, root in _pairs() if stem(word) != root]
    assert wrong == []


@pytest.mark.parametrize(
    ("word", "root"),
    [
        # die zehn Paare, an denen das Messskript seinen Stemmer vor jedem Lauf prüfte
        ("aufeinanderfolgenden", "aufeinanderfolg"),
        ("kategorien", "kategori"),
        ("häuser", "haus"),
        ("ergebnisse", "ergebnis"),
        ("radwege", "radweg"),
        ("radweg", "radweg"),
        ("schulen", "schul"),
        ("kindertageseinrichtungen", "kindertageseinricht"),
        ("straße", "strass"),
        ("möglichkeiten", "moglich"),
        # der bekannte Mangel (Messdokument § 3.6): „sicherer" und „Sicherheit" werden zum Pronomen
        ("sicherer", "sich"),
        ("sicherheit", "sich"),
        ("sich", "sich"),
    ],
)
def test_words_of_the_measurement(word: str, root: str) -> None:
    assert stem(word) == root
