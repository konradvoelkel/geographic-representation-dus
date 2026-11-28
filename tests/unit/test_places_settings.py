"""Vorhaben 16: der Block ``[places]`` (Messdokument ``docs/plans/16-ortsbezug.md``, § 6 und § 10).

Aus in den Vorgaben, an in den drei Düsseldorfer Profilen (die Perioden erben), aus in
Mönchengladbach (kein Adresspaket, keine Messung dort, § 10, Punkt 7). Die Gewichte nach Stelle
nennen genau die fünf Stellen und liegen in [0, 1], wie jeder Faktor der Gewichtung.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from georep.settings import PlacesSettings, load_settings

NOWHERE = Path("/nonexistent")


def test_the_defaults_keep_places_off() -> None:
    off = PlacesSettings()
    assert not off.enabled and not off.house_numbers and off.house_number == ""
    assert off.package is None
    assert off.position_weights == {
        "titel": 1.0,
        "betreff": 1.0,
        "kern": 1.0,
        "begleittext": 0.5,
        "rest": 0.25,
    }


@pytest.mark.parametrize("profile", ["duesseldorf", "duesseldorf-2014", "duesseldorf-2025"])
def test_the_three_profiles_of_the_city_switch_it_on(profile: str) -> None:
    places = load_settings(profile=profile, cwd=NOWHERE).places
    assert places.enabled and places.house_numbers
    assert places.package is not None and places.package.name == "duesseldorf-adressen"
    assert re.compile(places.house_number).groups >= 2


def test_the_second_city_stays_off() -> None:
    places = load_settings(profile="moenchengladbach", cwd=NOWHERE).places
    assert not places.enabled and not places.house_numbers


def test_the_house_number_pattern_must_compile() -> None:
    with pytest.raises(ValueError, match="places.house_number"):
        PlacesSettings.model_validate({"house_number": "(unclosed"})


def test_house_numbers_need_a_pattern_with_the_groups_nr_and_zusatz() -> None:
    with pytest.raises(ValueError, match="nr"):
        PlacesSettings.model_validate({"house_numbers": True, "house_number": r"\d+"})


@pytest.mark.parametrize(
    "weights",
    [
        {"titel": 1.0, "betreff": 1.0, "kern": 1.0, "begleittext": 0.5},  # eine Stelle fehlt
        {"titel": 1.0, "betreff": 1.0, "kern": 1.0, "begleittext": 0.5, "rest": 1.5},
        {"titel": 1.0, "betreff": 1.0, "kern": 1.0, "begleittext": 0.5, "rest": 0.25, "x": 1.0},
    ],
)
def test_position_weights_name_the_five_positions_in_the_unit_interval(
    weights: dict[str, float],
) -> None:
    with pytest.raises(ValueError, match="position_weights"):
        PlacesSettings.model_validate({"position_weights": weights})


def test_the_package_path_is_not_in_the_fingerprint() -> None:
    """Ein Pfad wie ``outcomes.package``: der Inhalt steht als Eingabe im Stamp von ``places``."""
    base = load_settings(profile="duesseldorf", cwd=NOWHERE)
    moved = base.model_copy(
        update={"places": base.places.model_copy(update={"package": Path("/elsewhere")})}
    )
    assert moved.fingerprint() == base.fingerprint()
