"""Regel 1 „Einrichtung mit Stadtnamen": welche Labels sie trifft und welche nicht.

Die Regel steht in ``docs/decisions.md``, Punkt 44, und ihre Wirkung in
``docs/methodik-review-2026-10.md``. Die Beispiele hier sind die Fälle, an denen sie entworfen
wurde: ein Ort aus Wikidata, dessen Label den Stadtnamen außerhalb einer Klammer als letztes Wort
trägt (oder das Städteadjektiv), ist eine Einrichtung mit stadtweiter Bedeutung; Bahnhöfe, Parks
und Schulen bleiben Orte, auch wenn der Stadtname im Label steht.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from georep.prep.pois import POI_COLUMNS, drop_city_facilities, is_city_facility
from georep.settings import Settings, load_settings

NAME = "Düsseldorf"
ADJECTIVES = ("Düsseldorfer",)
PLACE_WORDS = ("bahnhof", "haltepunkt", "park", "wald", "garten", "gymnasium", "see")


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


@pytest.mark.parametrize(
    "label",
    [
        "Stadtwerke Düsseldorf",
        "Flughafen Düsseldorf",
        "Messe Düsseldorf",
        "Heinrich-Heine-Universität Düsseldorf",
        "Düsseldorfer Schauspielhaus",  # das Adjektiv steht vorn
        "Stadtmuseum Landeshauptstadt Düsseldorf",
        "Amerikanisches Generalkonsulat in Düsseldorf",
        "Stadtsparkasse Düsseldorf",  # „park" steckt in „Sparkasse", zählt aber nicht
    ],
)
def test_a_label_that_ends_with_the_city_name_is_a_facility(label: str) -> None:
    assert is_city_facility(label, NAME, ADJECTIVES, PLACE_WORDS)


@pytest.mark.parametrize(
    "label",
    [
        "Altes Rathaus (Düsseldorf)",  # Stadtname nur als Wikipedia-Klammerzusatz
        "Elbsee (Düsseldorf)",
        "Bahnhof Düsseldorf Flughafen",  # dem Stadtnamen folgt noch ein Wort
        "Bahnhof Düsseldorf-Rath",
        "Düsseldorf Hauptbahnhof",
        "Düsseldorf Arcaden",
        "Düsseldorfer Stadtwald",  # Gattungswort „wald"
        "Luisen-Gymnasium Düsseldorf",  # Gattungswort „gymnasium"
        "Hofgarten",  # kein Stadtname im Label
        "Grafenberger Allee",
        "",
    ],
)
def test_a_place_stays_a_place(label: str) -> None:
    assert not is_city_facility(label, NAME, ADJECTIVES, PLACE_WORDS)


def test_the_rule_reads_the_city_words_from_the_profile(settings: Settings) -> None:
    """Kein Stadtwort im Code: eine andere Stadt trifft andere Labels."""
    assert is_city_facility("Stadtwerke Mönchengladbach", "Mönchengladbach", (), PLACE_WORDS)
    assert not is_city_facility("Stadtwerke Mönchengladbach", NAME, ADJECTIVES, PLACE_WORDS)
    city = settings.city
    assert (city.name, city.adjective) == (NAME, ADJECTIVES[0])


def _pois(*labels: str) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "label": list(labels),
            "wahlkreis_id": list(range(1, len(labels) + 1)),
            "lon": [6.8] * len(labels),
            "lat": [51.2] * len(labels),
        }
    ).select(POI_COLUMNS)


def test_dropping_facilities_keeps_the_other_rows_and_their_order() -> None:
    frame = _pois("Hofgarten", "Stadtwerke Düsseldorf", "Bahnhof Düsseldorf-Rath")
    out = drop_city_facilities(frame, NAME, ADJECTIVES, PLACE_WORDS, ())
    assert out.get_column("label").to_list() == ["Hofgarten", "Bahnhof Düsseldorf-Rath"]
    assert out.columns == POI_COLUMNS


def test_the_profile_can_keep_a_single_label() -> None:
    frame = _pois("Castello Düsseldorf", "Stadtwerke Düsseldorf")
    out = drop_city_facilities(frame, NAME, ADJECTIVES, PLACE_WORDS, ("Castello Düsseldorf",))
    assert out.get_column("label").to_list() == ["Castello Düsseldorf"]


def test_without_city_words_nothing_is_dropped() -> None:
    frame = _pois("Stadtwerke Düsseldorf", "Hofgarten")
    assert_frame_equal(drop_city_facilities(frame, "", (), PLACE_WORDS, ()), frame)


def test_the_switch_and_the_word_lists_come_from_the_settings(settings: Settings) -> None:
    assert settings.search.city_facilities is True  # Regel 1 gilt für jede Stadt
    assert "bahnhof" in settings.search.place_words
    # Das Profil nimmt genau die Fälle heraus, die die Regel falsch beurteilt (Review § 4).
    assert settings.search.city_facilities_keep == ["Castello Düsseldorf"]
