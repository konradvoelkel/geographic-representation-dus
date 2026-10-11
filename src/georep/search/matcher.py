"""Schlüsselwortsuche hinter einem Protokoll.

``FlashTextMatcher`` ist die Implementierung der Arbeit (Aho-Corasick-artiger Trie, reines
Python, Version 2.7 von 2018). Wer sie gegen pyahocorasick oder ein Rust-Modul tauscht, erfüllt
``KeywordMatcher``; der Vertrag ist Mengengleichheit der gefundenen Begriffe, keine Toleranz.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from flashtext import KeywordProcessor


class KeywordMatcher(Protocol):
    def add_terms(self, terms: Iterable[str]) -> None: ...

    def extract(self, text: str) -> set[str]:
        """Die Begriffe aus ``add_terms``, die in ``text`` vorkommen (Wortgrenzen, ohne Groß/Klein)."""
        ...


class FlashTextMatcher:
    def __init__(self) -> None:
        self._processor = KeywordProcessor(case_sensitive=False)

    def add_terms(self, terms: Iterable[str]) -> None:
        self._processor.add_keywords_from_list(list(terms))

    def extract(self, text: str) -> set[str]:
        found: list[str] = self._processor.extract_keywords(text)
        return set(found)

    def __len__(self) -> int:
        size: int = len(self._processor)
        return size


def make_matcher(terms: Iterable[str]) -> KeywordMatcher:
    matcher = FlashTextMatcher()
    matcher.add_terms(terms)
    return matcher
