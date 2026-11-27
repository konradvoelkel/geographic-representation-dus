"""Bausteine der Startkarte (``report/startkarte.py``, plan-startseite, § 4): Orte, Pfade, Stadtbezirke."""

from __future__ import annotations

import re

import polars as pl
from shapely.geometry import Polygon, box

from georep.report.geometry import fit
from georep.report.startkarte import (
    canonical,
    compact_path,
    default_window,
    main_city_district,
    place_documents,
)


def test_a_term_with_str_falls_to_the_long_form_only_where_the_district_knows_it() -> None:
    assert canonical("aachener str.", frozenset({"aachener straße", "aachener str."})) == (
        "aachener straße"
    )
    assert canonical("aachener str.", frozenset({"aachener str."})) == "aachener str."
    assert canonical("königsallee", frozenset()) == "königsallee"


def test_a_place_is_a_term_in_a_district_and_both_spellings_meet() -> None:
    """§ 4.2: eine Straße über zwei Wahlbezirke hat zwei Orte; Lang- und Kurzform fallen zusammen."""
    dictionary = {
        1: frozenset({"aachener straße", "aachener str.", "hofgarten"}),
        2: frozenset({"aachener straße"}),
    }
    terms = {"aachener straße": [0, 3], "aachener str.": [5], "hofgarten": [1]}
    found = place_documents(terms, dictionary)
    assert found == {
        ("aachener straße", 1): {0, 3, 5},
        ("aachener straße", 2): {0, 3},
        ("hofgarten", 1): {1},
    }


def test_the_window_is_the_last_months_up_to_the_newest_document() -> None:
    assert default_window(60, 61, 12) == (49, 60)  # Hauptperiode: Oktober 2024 bis September 2025
    assert default_window(5, 14, 12) == (0, 5)  # kürzer als zwölf Monate: ab dem ersten
    assert default_window(70, 61, 12) == (49, 60)  # nie hinter das Ende der Reihe


def test_a_compact_path_is_integer_and_relative() -> None:
    projection = fit((0.0, 0.0, 1000.0, 500.0), 2000.0)
    path = compact_path(box(0, 0, 100, 100), projection)
    assert re.fullmatch(r"M\d+ \d+l(-?\d+[ -]?)+z", path), path
    # Ein Loch ist ein eigener Ring; ein Ring, der beim Runden zu einem Punkt zerfällt, fällt weg
    ring = Polygon([(0, 0), (400, 0), (400, 400), (0, 400)], [[(100, 100), (200, 100), (200, 200)]])
    assert compact_path(ring, projection).count("M") == 2
    assert compact_path(box(0, 0, 0.1, 0.1), projection) == ""


def test_a_split_district_counts_to_its_larger_city_district() -> None:
    rows = pl.DataFrame(
        {
            "wahlkreis_id": [39, 40, 40],
            "stadtbezirk": [9, 9, 10],
            "wahlberechtigte": [100, 65, 35],
            "gewicht": [1.0, 0.65, 0.35],
        }
    )
    assert main_city_district(rows) == {39: 9, 40: 9}
