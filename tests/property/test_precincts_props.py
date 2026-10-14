"""Eigenschaften der Regel „Wahlbezirk steckt in der Stimmbezirksnummer" (Option 01, Stufe B).

Dazu die Eigenschaften der Esri-Ringumwandlung (Punkt 65): Umlaufrichtung, Löcher und die Fläche,
die dabei erhalten bleibt. Beispiele dafür stehen in ``tests/unit/test_precincts.py`` an der
echten Antwort des Dienstes; hier gilt es für alle Rechtecke, die hypothesis baut.
"""

from __future__ import annotations

import deal
import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st
from shapely.geometry import shape

from georep.errors import SchemaError
from georep.prep.precincts import (
    district_from_id,
    geometry_from_esri_rings,
    is_number,
    is_ring,
    ring_signed_area,
)

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


# --- Esri-Ringe (Punkt 65) ------------------------------------------------------------------
#
# Rechtecke genügen: die Umwandlung entscheidet am Vorzeichen der Fläche und an der
# Punkt-im-Ring-Frage, und beides hängt nicht an der Zahl der Ecken. Die Koordinaten bleiben in
# der Größenordnung eines UTM-Wertes, damit die Summen so rechnen wie in Mönchengladbach.

coordinates = st.floats(min_value=300_000.0, max_value=400_000.0, allow_nan=False)
sizes = st.floats(min_value=1.0, max_value=1_000.0, allow_nan=False)
# Die Trapezformel summiert Produkte in der Größenordnung von 1,6e11 zu einer Fläche von 1 bis
# 1e6: die Auslöschung kostet rund 2e-4 Flächeneinheiten (fünf Glieder mal eps mal 1,6e11). Darum
# vergleicht jede Zahl mit beiden Toleranzen; relativ allein wäre für ein 1-m²-Rechteck zu scharf.
AREA_REL, AREA_ABS = 1e-9, 1e-2


def rectangle(x: float, y: float, width: float, height: float) -> list[list[float]]:
    """Ein Rechteck im Uhrzeigersinn, wie Esri einen äußeren Ring schreibt (negative Fläche)."""
    return [[x, y], [x, y + height], [x + width, y + height], [x + width, y], [x, y]]


@given(x=coordinates, y=coordinates, width=sizes, height=sizes)
def test_a_clockwise_ring_is_negative_and_the_turned_one_is_positive(
    x: float, y: float, width: float, height: float
) -> None:
    """Das Vorzeichen ist die ganze Unterscheidung, und Drehen wechselt es, ohne die Fläche zu ändern."""
    ring = rectangle(x, y, width, height)
    assert is_ring(ring) and is_ring(list(reversed(ring)))
    assert ring_signed_area(ring) < 0.0
    assert ring_signed_area(ring) == pytest.approx(
        -ring_signed_area(list(reversed(ring))), rel=AREA_REL, abs=AREA_ABS
    )
    assert abs(ring_signed_area(ring)) == pytest.approx(width * height, rel=AREA_REL, abs=AREA_ABS)


@given(x=coordinates, y=coordinates, size=sizes, hole=st.floats(0.1, 0.4))
def test_a_counter_clockwise_inner_ring_becomes_a_hole_and_loses_its_area(
    x: float, y: float, size: float, hole: float
) -> None:
    """Die Fläche des Lochs fehlt im Ergebnis; ohne Schachtelung käme sie dazu."""
    inner = size * hole
    rings = [
        rectangle(x, y, size, size),
        list(reversed(rectangle(x + inner, y + inner, inner, inner))),
    ]
    geometry = geometry_from_esri_rings(rings)
    assert geometry["type"] == "Polygon" and len(geometry["coordinates"]) == 2
    exterior, interior = geometry["coordinates"]
    assert ring_signed_area(exterior) > 0.0 > ring_signed_area(interior)  # RFC 7946
    assert shape(geometry).area == pytest.approx(
        size * size - inner * inner, rel=AREA_REL, abs=AREA_ABS
    )


@given(x=coordinates, y=coordinates, size=sizes, second=st.floats(0.1, 0.9))
def test_a_second_clockwise_ring_is_a_second_area_and_adds_to_it(
    x: float, y: float, size: float, second: float
) -> None:
    """Zwei äußere Ringe nebeneinander: ein MultiPolygon, dessen Fläche die Summe ist."""
    apart = size * second
    rings = [rectangle(x, y, size, size), rectangle(x + size + 1.0, y, apart, apart)]
    geometry = geometry_from_esri_rings(rings)
    assert geometry["type"] == "MultiPolygon" and len(geometry["coordinates"]) == 2
    assert shape(geometry).area == pytest.approx(
        size * size + apart * apart, rel=AREA_REL, abs=AREA_ABS
    )


@given(
    x=coordinates,
    y=coordinates,
    size=sizes,
    hole=st.floats(0.1, 0.4),
    turn=st.booleans(),
)
def test_the_net_area_of_the_rings_is_the_area_of_the_geometry(
    x: float, y: float, size: float, hole: float, turn: bool
) -> None:
    """Die Nachbedingung der Umwandlung, hier von außen geprüft: Esri zählt außen negativ.

    Dieselbe Formel, einmal über die Quellringe und einmal über das Ergebnis von shapely: so
    hängt die Eigenschaft nicht daran, dass der Vertrag im Code richtig geschrieben ist.
    """
    inner = size * hole
    second = rectangle(x + inner, y + inner, inner, inner)
    rings = [rectangle(x, y, size, size), list(reversed(second)) if turn else second]
    expected = -sum(ring_signed_area(ring) for ring in rings)
    assert shape(geometry_from_esri_rings(rings)).area == pytest.approx(
        expected, rel=AREA_REL, abs=AREA_ABS
    )


@given(
    ring=st.lists(st.lists(coordinates, min_size=2, max_size=2), min_size=0, max_size=3),
)
def test_a_ring_with_fewer_than_four_points_is_no_ring(ring: list[list[float]]) -> None:
    """Drei Ecken und der wiederholte Anfangspunkt sind das Kleinste; darunter ist es eine Linie."""
    assert not is_ring(ring)
    with pytest.raises(deal.PreContractError):
        ring_signed_area(ring)
    with pytest.raises(deal.PreContractError):
        geometry_from_esri_rings([ring])
