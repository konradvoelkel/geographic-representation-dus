"""format_de: für jede endliche Zahl lesbar, umkehrbar und ohne Vorzeichen auf einer gerundeten Null."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.report.model import NARROW_NBSP, format_de, percent_de

values = st.floats(min_value=-1e15, max_value=1e15, allow_nan=False, allow_infinity=False)
decimals = st.integers(0, 6)


def parse_de(text: str) -> float:
    return float(text.replace(NARROW_NBSP, "").replace(",", "."))


@given(value=values, decimals=decimals)
def test_round_trip_is_the_rounded_value(value: float, decimals: int) -> None:
    text = format_de(value, decimals)
    assert parse_de(text) == pytest.approx(round(value, decimals), abs=10.0**-decimals)
    assert format_de(parse_de(text), decimals) == text


@given(value=values, decimals=decimals)
def test_groups_of_three_and_fixed_decimals(value: float, decimals: int) -> None:
    text = format_de(value, decimals)
    integer, _, fraction = text.lstrip("-").partition(",")
    assert len(fraction) == decimals and ("," in text) == (decimals > 0)
    groups = integer.split(NARROW_NBSP)
    assert 1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])
    assert all(g.isdigit() for g in groups)


@given(value=st.integers(-(10**15), 10**15))
def test_integers_keep_every_digit(value: int) -> None:
    assert format_de(value).replace(NARROW_NBSP, "") == str(value)


@given(value=st.floats(-0.0049, 0.0049), decimals=st.integers(0, 2))
def test_a_rounded_zero_has_no_sign(value: float, decimals: int) -> None:
    assert not format_de(value, decimals).startswith("-")


@given(share=st.floats(0, 1), decimals=decimals)
def test_percent_scales_by_hundred(share: float, decimals: int) -> None:
    text = percent_de(share, decimals)
    assert text.endswith(f"{NARROW_NBSP}%")
    assert parse_de(text[: -len(f"{NARROW_NBSP}%")]) == pytest.approx(
        round(share * 100, decimals), abs=10.0**-decimals
    )
