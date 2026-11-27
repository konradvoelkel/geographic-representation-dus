"""Startseite: Eigenschaften des Medoids und der Straßennamen für beliebige Eingaben (plan-startseite, § 4.2)."""

from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from georep.prep.streetpoints import medoid, normalize_street

COORDS = st.integers(-5_000, 5_000).map(float)
POINTS = st.lists(st.tuples(COORDS, COORDS), min_size=1, max_size=40)


def _sum(points: list[tuple[float, float]], x: float, y: float) -> float:
    return float(sum(((px - x) ** 2 + (py - y) ** 2) ** 0.5 for px, py in points))


@given(points=POINTS)
def test_the_medoid_is_a_point_of_the_set_with_the_smallest_sum(
    points: list[tuple[float, float]],
) -> None:
    xs = np.array([p[0] for p in points])
    ys = np.array([p[1] for p in points])
    x, y = medoid(xs, ys)
    assert (x, y) in points
    best = min(_sum(points, px, py) for px, py in points)
    assert _sum(points, x, y) <= best + 1e-6


@given(points=POINTS)
def test_the_medoid_does_not_depend_on_the_order(points: list[tuple[float, float]]) -> None:
    forward = medoid(np.array([p[0] for p in points]), np.array([p[1] for p in points]))
    reverse = medoid(np.array([p[0] for p in points][::-1]), np.array([p[1] for p in points][::-1]))
    assert forward == reverse


@given(name=st.text(alphabet="abcStrasße.- ", max_size=30))
def test_normalizing_a_street_name_twice_changes_nothing(name: str) -> None:
    once = normalize_street(name)
    assert normalize_street(once) == once
