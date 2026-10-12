"""Eigenschaften der Regel „Wahlbezirk steckt in der Stimmbezirksnummer" (Option 01, Stufe B)."""

from __future__ import annotations

from hypothesis import assume, example, given
from hypothesis import strategies as st

from georep.errors import SchemaError
from georep.prep.precincts import district_from_id, is_number

digits = st.text(alphabet="0123456789", min_size=1, max_size=8)


@given(number=digits, start=st.integers(0, 6), width=st.integers(1, 4))
@example(number="10401", start=1, width=2)  # Mönchengladbach: Wahlbezirk 4
@example(number="0011", start=0, width=3)  # Neuss: Wahlbezirk 1
def test_the_cut_is_the_number_it_shows(number: str, start: int, width: int) -> None:
    cut = number[start : start + width]
    assume(is_number(cut) and int(cut) > 0)
    assert district_from_id(number, start, start + width) == int(cut)


@given(number=digits, start=st.integers(0, 6), width=st.integers(1, 4))
def test_a_cut_without_digits_or_with_only_zeroes_is_an_error(
    number: str, start: int, width: int
) -> None:
    cut = number[start : start + width]
    assume(not is_number(cut) or int(cut) == 0)
    try:
        district_from_id(number, start, start + width)
    except SchemaError:
        return
    raise AssertionError(f"{number!r}[{start}:{start + width}] = {cut!r} blieb unbemerkt")


@given(number=digits, start=st.integers(0, 4), width=st.integers(1, 3))
def test_leading_zeroes_do_not_change_the_district(number: str, start: int, width: int) -> None:
    cut = number[start : start + width]
    assume(is_number(cut) and int(cut) > 0)
    padded = number[:start] + cut.lstrip("0").rjust(width, "0") + number[start + width :]
    assert district_from_id(padded, start, start + width) == district_from_id(
        number, start, start + width
    )
