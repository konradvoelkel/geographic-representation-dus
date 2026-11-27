"""Startseite: die Voreinstellung des Zeitreglers für beliebige Perioden (plan-startseite, § 5)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from georep.report.startkarte import default_window


@given(newest=st.integers(-5, 200), months=st.integers(1, 120), span=st.integers(1, 36))
def test_the_window_lies_in_the_period_ends_at_the_newest_month_and_is_at_most_span_long(
    newest: int, months: int, span: int
) -> None:
    first, last = default_window(newest, months, span)
    assert 0 <= first <= last <= months - 1
    assert last - first + 1 <= span
    assert last == min(max(newest, 0), months - 1)
    assert last - first + 1 == min(span, last + 1)
