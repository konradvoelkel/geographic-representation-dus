"""Vorhaben 18: der Snowball-Stemmer für Deutsch, klassische Fassung, ohne Abhängigkeit.

Die Wortsuche (BM25, ``georep.search.bm25``) braucht einen Stemmer, damit „Radwege" und „Radweg"
dasselbe Token sind. Dies ist der Algorithmus von snowballstem.org in der Fassung vor Snowball 3.0
(Prelude ß → ss und u/y zwischen Vokalen, R1 und R2, Schritte 1 bis 3, Postlude ohne Umlautpunkte;
seit 2009 mit der Regel für „-nisse"), genau so, wie die Messung von Vorhaben 18 ihn benutzt hat
(``docs/plans/18-einbettungen-messung.py``, ``stem_de``; Messdokument § 3.1). Snowball 3.0 hat den
deutschen Stemmer 2023 bis 2025 geändert (ae/oe/ue, -erin, -ln, -et); eine neue Fassung wäre eine
neue Messung der Suche, nicht eine Pflege dieser Datei.

Eine eigene Umsetzung statt der Bibliothek ``snowballstemmer`` (Frage 9.4 des Messdokuments, wie
``krippendorff`` in F4): rund 70 Zeilen, geprüft gegen die Beispielliste des Projekts zu dieser
Fassung (``tests/fixtures/snowball/``, jedes 17. der 35 033 Wörter; die volle Liste stimmt in allen
35 033, geprüft am 2026-11-24).
"""

from __future__ import annotations

from collections.abc import Sequence

import deal

VOWELS = frozenset("aeiouyäöü")
S_ENDINGS = frozenset("bdfghklmnrt")  # vor einem -s, das Schritt 1 streicht
ST_ENDINGS = frozenset("bdfghklmnt")  # vor einem -st, das Schritt 2 streicht
STEP1 = ("ern", "em", "er", "en", "es", "e", "s")
STEP2 = ("est", "en", "er", "st")
STEP3 = ("isch", "lich", "heit", "keit", "end", "ung", "ig", "ik")


def _region(word: str, start: int) -> int:
    """Der Beginn der Region nach dem ersten Nicht-Vokal, der auf einen Vokal folgt (ab ``start``)."""
    i = start
    while i < len(word) and word[i] not in VOWELS:
        i += 1
    while i < len(word) and word[i] in VOWELS:
        i += 1
    return min(i + 1, len(word))


def _longest(word: str, endings: Sequence[str]) -> str:
    for ending in sorted(endings, key=len, reverse=True):
        if word.endswith(ending):
            return ending
    return ""


@deal.ensure(lambda word, result: len(result) <= len(word.replace("ß", "ss")))
@deal.ensure(lambda word, result: not set(result) & set("äöüß"))
@deal.safe
def stem(word: str) -> str:
    """Der Stamm eines kleingeschriebenen Worts: Prelude, R1/R2, Schritte 1 bis 3, Postlude."""
    letters = list(word.replace("ß", "ss"))
    for i in range(1, len(letters) - 1):
        if letters[i] in "uy" and letters[i - 1] in VOWELS and letters[i + 1] in VOWELS:
            letters[i] = letters[i].upper()
    s = "".join(letters)
    if len(s) < 3:
        r1 = r2 = len(s)
    else:
        first = _region(s, 0)
        r2 = _region(s, first)
        r1 = max(first, 3)
    # Schritt 1
    ending = _longest(s, STEP1)
    if ending and len(s) - len(ending) >= r1:
        if ending in ("em", "ern", "er"):
            s = s[: -len(ending)]
        elif ending in ("e", "en", "es"):
            s = s[: -len(ending)]
            if s.endswith("niss"):
                s = s[:-1]
        elif ending == "s" and len(s) >= 2 and s[-2] in S_ENDINGS:
            s = s[:-1]
    # Schritt 2
    ending = _longest(s, STEP2)
    if ending and len(s) - len(ending) >= r1:
        if ending in ("en", "er", "est"):
            s = s[: -len(ending)]
        elif ending == "st" and len(s) >= 3 and s[-3] in ST_ENDINGS and len(s) - 3 >= 3:
            s = s[:-2]
    # Schritt 3
    ending = _longest(s, STEP3)
    if ending and len(s) - len(ending) >= r2:
        if ending in ("end", "ung"):
            s = s[: -len(ending)]
            if s.endswith("ig") and len(s) - 2 >= r2 and not s[:-2].endswith("e"):
                s = s[:-2]
        elif ending in ("ig", "ik", "isch"):
            if not s[: -len(ending)].endswith("e"):
                s = s[: -len(ending)]
        elif ending in ("lich", "heit"):
            s = s[: -len(ending)]
            for before in ("er", "en"):
                if s.endswith(before) and len(s) - 2 >= r1:
                    s = s[:-2]
                    break
        elif ending == "keit":
            s = s[:-4]
            inner = _longest(s, ("lich", "ig"))
            if inner and len(s) - len(inner) >= r2:
                s = s[: -len(inner)]
    return (
        s.replace("U", "u").replace("Y", "y").replace("ä", "a").replace("ö", "o").replace("ü", "u")
    )
