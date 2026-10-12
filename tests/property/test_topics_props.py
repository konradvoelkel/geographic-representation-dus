"""Eigenschaften der Stoppwortableitung (Punkt 45, docs/themenmodell-2026-10.md, § 2).

Beide Funktionen sind rein auf Settings beziehungsweise auf einer Liste von Texten, und die
Invarianten hier gelten für jede Eingabe: aus einem Profil können nur Wörter kommen, die das
Tokenmuster des Modells bildet, und ein Name muss in einem Namensfenster stehen und die Schwelle
halten. Die Verträge des Modells selbst (``k`` Themen, Zeilensummen 1, Saat zuerst) hängen am
Frame und stehen als deal-Nachbedingung in ``analysis/topics.py``.
"""

from __future__ import annotations

import re

from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.topics import (
    TOKEN_PATTERN,
    TopicRules,
    name_stop_words,
    profile_stop_words,
)
from georep.settings import STOP_SOURCES, Bodies, Originators, Party

TOKEN = re.compile(f"^{TOKEN_PATTERN}$")
WORD = re.compile(TOKEN_PATTERN)

name = st.text(alphabet="abcdefgäöüß /-\\.", min_size=0, max_size=14)
party = st.builds(
    lambda key, label, short, patterns: Party(
        key=key or "X", label=label, short=short, patterns=list(patterns)
    ),
    st.text(alphabet="ABCDEF_", min_size=1, max_size=6),
    name,
    name,
    st.lists(
        st.sampled_from([r"\bcdu\b", "grüne", "bündnis ?90", "tierschutz"]),
        min_size=1,
        max_size=3,
        unique=True,
    ),
)
code = st.text(alphabet="ABCDEFGÄÖÜ", min_size=1, max_size=6)
# Ein Bodies mit Kürzeln verlangt ein Muster (sonst trägt die Nummer keines, Option 01).
PATTERN = r"^(?P<code>[A-ZÄÖÜ]+?)(?P<number>\d{1,2})?/\d+/\d{4}$"
sources = st.lists(st.sampled_from(STOP_SOURCES), unique=True).map(tuple)


# Die Schlüssel der Parteien müssen eindeutig sein (Settings-Validator von Option 04).
parties = st.lists(party, max_size=4, unique_by=lambda p: p.key)


@given(parties=parties, codes=st.lists(code, max_size=5), picked=sources)
def test_only_real_tokens_come_out_of_a_profile(
    parties: list[Party], codes: list[str], picked: tuple[str, ...]
) -> None:
    """Jedes abgeleitete Wort ist kleingeschrieben und bildet allein ein Token des Modells.

    Sonst stünde in der Liste etwas, das in keinem Dokument vorkommen kann (ein Kürzel aus zwei
    Buchstaben, ein Regex-Zeichen) — harmlos, aber die Messung in § 2.1 zählte es mit.
    """
    bodies = Bodies(
        reference_pattern=PATTERN, district_body="BV", committees={c: "" for c in codes}
    )
    words = profile_stop_words(Originators(parties=parties), bodies, picked)
    assert all(TOKEN.fullmatch(word) for word in words), sorted(words)
    assert all(word == word.lower() for word in words)


@given(parties=parties, codes=st.lists(code, max_size=4))
def test_without_a_source_nothing_is_derived(parties: list[Party], codes: list[str]) -> None:
    bodies = Bodies(
        reference_pattern=PATTERN, district_body="BV", committees={c: "" for c in codes}
    )
    assert profile_stop_words(Originators(parties=parties), bodies, ()) == frozenset()


@given(
    before=st.lists(st.sampled_from(["strasse", "verkehr", "beschluss"]), max_size=4),
    behind=st.lists(st.sampled_from(["mustermann", "meier", "schulz"]), min_size=2, max_size=4),
    documents=st.integers(min_value=1, max_value=12),
    share=st.floats(min_value=0.1, max_value=1.0),
)
def test_a_name_stands_in_a_window_and_holds_the_share(
    before: list[str], behind: list[str], documents: int, share: float
) -> None:
    """Jedes gefundene Wort steht hinter dem Marker und erfüllt die Schwelle.

    Geprüft wird gegen die Definition, nicht gegen eine Liste: ein Wort ist ein Name, wenn der
    Anteil seiner Dokumente, die ein Fenster haben, über ``name_share`` liegt.
    """
    rules = TopicRules(
        name_markers=("gez.",),
        name_window=60,
        name_min_documents=1,
        name_share=share,
        with_names=True,
    )
    texts = [" ".join(before) + " gez. " + " ".join(behind) for _ in range(documents)]
    found = name_stop_words(texts, rules)
    # Was im Fenster steht, ist das Hinten ohne das letzte Wort (das wäre abgeschnitten).
    in_window = set(behind[:-1])
    everywhere = set(before) | set(behind)
    assert found <= everywhere
    assert all(word in in_window for word in found), (found, in_window)
    for word in in_window:
        # Ein Wort, das nur im Fenster steht, hat Anteil 1 und muss jede Schwelle halten.
        if word not in before:
            assert word in found, (word, found, share)


@given(texts=st.lists(st.text(alphabet="abc äöüß.", max_size=30), max_size=8))
def test_arbitrary_texts_never_raise(texts: list[str]) -> None:
    """Ein Korpus ohne jedes Fenster oder ohne jedes Wort ist kein Fehler, nur eine leere Menge."""
    rules = TopicRules(name_markers=("gez.",), with_names=True, name_min_documents=1)
    found = name_stop_words(texts, rules)
    assert all(WORD.fullmatch(word) for word in found)
