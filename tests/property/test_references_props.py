"""Vorhaben 14: jede erzeugte Drucksachennummer kommt als derselbe Schlüssel heraus.

Für jede Form der beiden Stadtprofile gilt Schlüssel(Formatieren(x)) = x: wie immer die Nummer
geschrieben ist (führende Nullen, Leerzeichen um die Trenner, Nachtrag vorn oder hinten), die
eigene Nummer und dieselbe Nummer im kleingeschriebenen Text ergeben denselben Schlüssel. Die
Formen kommen aus den Profilen, nicht aus einer Kopie (``tests/unit/test_references.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from georep.prep.references import ReferenceRules, find_hits, parse_reference
from georep.settings import load_settings

NOWHERE = Path("/nonexistent")
DUS = ReferenceRules.from_settings(load_settings(cwd=NOWHERE).procedures)
MG = ReferenceRules.from_settings(load_settings(profile="moenchengladbach", cwd=NOWHERE).procedures)
CODES = ("BV", "OVA", "RAT", "KUA", "AUS", "AGS", "SCHUA", "JHA")


@dataclass(frozen=True)
class Written:
    """Eine Nummer: so, wie sie im Feld ``reference`` steht, so im Text, und ihr Schlüssel."""

    reference: str
    text: str
    key: str


def _zeros(value: int, width: int, padded: bool) -> str:
    return f"{value:0{width}d}" if padded else str(value)


@st.composite
def current(draw: st.DrawFn) -> Written:
    """``BV6/108/2023``, ``OVA/117/2023/1``: Kürzel, Nummer dahinter, laufende Nummer, Jahr."""
    code = draw(st.sampled_from(CODES))
    number = draw(st.one_of(st.none(), st.integers(1, 20)))
    serial = draw(st.integers(1, 999))
    year = draw(st.integers(2000, 2030))
    suffix = draw(st.one_of(st.none(), st.integers(1, 9)))
    padded = draw(st.booleans())
    head = code + ("" if number is None else _zeros(number, 2, padded))
    body = f"{head}/{_zeros(serial, 3, padded)}/{year}"
    own = body + (
        "" if suffix is None else draw(st.sampled_from(["/", " - ", "-", " / "])) + str(suffix)
    )
    spaced = draw(st.sampled_from(["/", " /", "/ ", " / "]))
    text = body.lower().replace("/", spaced) + ("" if suffix is None else f"/{suffix}")
    base = f"{code}{'' if number is None else number}/{serial}/{year}"
    return Written(own, text, base + ("" if suffix is None else f"/{suffix}"))


@st.composite
def old(draw: st.DrawFn) -> Written:
    """``61/ 12/2014 - 1`` (Punkt 57): der Kopf aus Ziffern bleibt, wie er ist."""
    head = draw(st.from_regex(r"[0-9]{2,3}", fullmatch=True))
    serial = draw(st.integers(1, 999))
    year = draw(st.integers(2000, 2030))
    suffix = draw(st.one_of(st.none(), st.integers(1, 9)))
    space = draw(st.sampled_from(["", " ", "  "]))
    body = f"{head}/{space}{serial}/{year}"
    tail = "" if suffix is None else f" - {suffix}"
    base = f"{head}/{serial}/{year}"
    return Written(body + tail, body + tail, base + ("" if suffix is None else f"/{suffix}"))


ROMAN = ("IX", "X", "XI", "XII")


@st.composite
def second_city(draw: st.DrawFn) -> Written:
    """``0302/X``, ``0302-1/X``, ``0302/X-1``: laufende Nummer, Wahlperiode, Nachtrag."""
    serial = draw(st.integers(100, 9999))
    period = draw(st.sampled_from(ROMAN))
    suffix = draw(st.one_of(st.none(), st.integers(1, 9)))
    padded = draw(st.booleans())
    number = _zeros(serial, 4, padded)
    front = draw(st.booleans())
    if suffix is None:
        own = f"{number}/{period}"
    elif front:
        own = f"{number}-{suffix}/{period}"
    else:
        own = f"{number}/{period}-{suffix}"
    return Written(
        own, own.lower(), f"{serial:04d}/{period}" + ("" if suffix is None else f"/{suffix}")
    )


@given(written=st.one_of(current(), old()))
def test_own_number_and_text_give_the_same_key(written: Written) -> None:
    parsed = parse_reference(written.reference, DUS)
    assert parsed is not None and parsed.key == written.key
    # Ein Komma direkt hinter dem Nachtrag beendet ihn (``(?![\d.,])``, wie gemessen: „/1,5 Mio.");
    # darum steht hier ein Leerzeichen.
    text = f"siehe {written.text} und"
    found = find_hits(text, DUS, frozenset(CODES))
    assert written.key in [hit.reference.key for hit in found]
    for hit in found:
        assert text.index(written.text) <= hit.start < hit.end <= len(text)


@given(written=second_city())
def test_the_second_city_gives_the_same_key(written: Written) -> None:
    parsed = parse_reference(written.reference, MG)
    assert parsed is not None and parsed.key == written.key
    found = find_hits(f"zu vorlage {written.text} vom", MG, frozenset())
    assert [hit.reference.key for hit in found] == [written.key]


@given(written=current(), word=st.sampled_from(["vorlage", "zur", "antragder", "drucksache"]))
def test_a_glued_word_does_not_change_the_key(written: Written, word: str) -> None:
    """pypdf klebt das Wort davor an das Kürzel; das längste bekannte Kürzel am Ende gilt."""
    found = find_hits(f"{word}{written.text} vom", DUS, frozenset(CODES))
    assert written.key in [hit.reference.key for hit in found]
