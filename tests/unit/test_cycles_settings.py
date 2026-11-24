"""Die Settings von Vorhaben 17: ``[cycles]`` und ``[feeds]``.

Stadtneutral in ``defaults.toml``: Wahljahr, Muster der Haushaltsanträge, Wörter der Instrumente,
Lexikon, alles aus. Im Stadtprofil: die Wahltage mit Quelle und der Schalter; die Tests über die
drei Perioden rechnet ``duesseldorf-vergleich``, die Feeds gibt es nur in der laufenden Periode
(Messdokument 17, § 6 und § 10). Ein Tippfehler in einem Muster, eine falsche Folge der Wahltage
oder eine unbekannte Zeitzone fallen beim Laden auf.
"""

from __future__ import annotations

import tomllib
from datetime import date
from importlib import resources
from pathlib import Path

import pytest
from pydantic import ValidationError

import georep.settings as gs
from georep.settings import load_settings

NOWHERE = Path("/nonexistent")
NRW = [date(2014, 5, 25), date(2020, 9, 13), date(2025, 9, 14)]


def test_everything_is_off_by_default() -> None:
    assert gs.Cycles().enabled is False
    assert gs.Feeds().enabled is False
    block = tomllib.loads(
        resources.files("georep").joinpath("defaults.toml").read_text(encoding="utf-8")
    )
    assert block["cycles"]["enabled"] is False and block["feeds"]["enabled"] is False
    assert block["cycles"]["elections"] == [] and block["cycles"]["periods"] == []
    assert block["cycles"]["year_start_month"] == 9
    assert block["cycles"]["lexicon"] == "bundespolitik"


def test_the_city_carries_its_election_days_and_every_period_inherits_them() -> None:
    for profile in ("duesseldorf", "duesseldorf-2014", "duesseldorf-2025", "duesseldorf-vergleich"):
        cycles = load_settings(profile=profile, cwd=NOWHERE).cycles
        assert cycles.enabled, profile
        assert cycles.elections == NRW, profile
        # die Arten „zAnfrage" und „zAntrag" ergänzt das Stadtprofil, die Vorgabe bleibt
        assert cycles.instrument_types == {
            "anfrage": "anfrage",
            "antrag": "antrag",
            "haushaltsantrag": "antrag",
            "zanfrage": "anfrage",
            "zantrag": "antrag",
        }, profile


def test_only_the_comparison_profile_runs_the_tests_over_three_periods() -> None:
    periods = {
        profile: load_settings(profile=profile, cwd=NOWHERE).cycles.periods
        for profile in (
            "duesseldorf",
            "duesseldorf-2014",
            "duesseldorf-2025",
            "duesseldorf-vergleich",
            "moenchengladbach",
        )
    }
    assert periods.pop("duesseldorf-vergleich") == ["2014-2020", "duesseldorf", "2025"]
    assert set(map(tuple, periods.values())) == {()}


def test_only_the_running_period_writes_feeds() -> None:
    assert load_settings(profile="duesseldorf-2025", cwd=NOWHERE).feeds.enabled
    for profile in ("duesseldorf", "duesseldorf-2014", "duesseldorf-vergleich", "moenchengladbach"):
        assert not load_settings(profile=profile, cwd=NOWHERE).feeds.enabled, profile


def test_the_second_city_gets_rhythm_and_vocabulary_without_tests_or_feeds() -> None:
    settings = load_settings(profile="moenchengladbach", cwd=NOWHERE)
    assert settings.cycles.enabled and settings.cycles.elections == NRW
    assert settings.cycles.periods == [] and not settings.feeds.enabled


def test_election_days_stand_in_order() -> None:
    with pytest.raises(ValidationError, match="aufsteigend"):
        gs.Cycles(elections=[date(2020, 9, 13), date(2014, 5, 25)])
    with pytest.raises(ValidationError, match="aufsteigend"):
        gs.Cycles(elections=[date(2020, 9, 13), date(2020, 9, 13)])


def test_tests_over_periods_need_election_days() -> None:
    with pytest.raises(ValidationError, match="ohne Wahltag"):
        gs.Cycles(periods=["a", "b"])
    with pytest.raises(ValidationError, match="zweimal"):
        gs.Cycles(periods=["a", "a"], elections=NRW)
    with pytest.raises(ValidationError, match="Ordnername"):
        gs.Cycles(periods=["../a"], elections=NRW)


def test_a_pattern_that_does_not_compile_fails_on_load() -> None:
    with pytest.raises(ValidationError, match="budget_pattern"):
        gs.Cycles(budget_pattern="haushalt(")
    with pytest.raises(ValidationError, match="instrument_titles"):
        gs.Cycles(instrument_titles=[gs.InstrumentTitle(pattern="(", instrument="antrag")])


def test_an_unknown_instrument_or_zone_fails_on_load() -> None:
    with pytest.raises(ValidationError):
        gs.Cycles(instrument_types={"vorlage": "vorlage"})  # type: ignore[dict-item]
    with pytest.raises(ValidationError, match="Zeitzone"):
        gs.Feeds(timezone="Mars/Olympus")
