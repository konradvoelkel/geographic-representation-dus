"""Die Settings von Vorhaben 15: ``[functions]`` und der stadtweite Block ``[majorities]``.

Die Tabellen der Dokumentarten nennen „funktion/instrument"; ein Tippfehler darin soll beim Laden
auffallen, nicht erst in einer Zahl der Seite (Messdokument 15, § 6). Die Mehrheiten sind eine
Annahme mit Quelle, die drei Vorhaben lesen (15, 24, 28); ihre Zeiträume dürfen sich nicht
überlappen, sonst hinge das Lager eines Dokuments an der Reihenfolge der Zeilen.
"""

from __future__ import annotations

import tomllib
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import georep.settings as gs
from georep.settings import load_settings

NOWHERE = Path("/nonexistent")


def _majority(period: str, start: date, end: date | None, **extra: Any) -> dict[str, Any]:
    return {
        "period": period,
        "parties": ["A", "B"],
        "valid_from": start,
        "valid_to": end,
        "agreement": "Vereinbarung",
        **extra,
    }


def test_the_switch_is_off_and_variant_b_is_the_default() -> None:
    functions = gs.Functions()
    assert functions.enabled is False
    assert functions.variant == "B"  # gewählt nach der Kodierung, Messdokument 15, § 5


def test_the_defaults_carry_the_language_and_no_table_of_a_city() -> None:
    """``defaults.toml`` trägt die Wörter der Ratsdokumente, die Tabellen stehen im Stadtprofil."""
    text = resources.files("georep").joinpath("defaults.toml").read_text(encoding="utf-8")
    block = tomllib.loads(text)["functions"]
    assert block["enabled"] is False
    assert block["types"] == {} and block["type_prefixes"] == {}
    assert block["collection_political"] == [] and block["collection_admin"] == []
    assert block["fractions"] == []
    assert block["symbol_title"] and block["motion_title"] and block["request_title"]


def test_a_type_names_a_function_and_one_of_its_instruments() -> None:
    assert gs.function_and_instrument("vollzug/beschlussvorlage") == ("vollzug", "beschlussvorlage")
    gs.Functions(types={"Beschlussvorlage": "vollzug/beschlussvorlage"})
    with pytest.raises(ValidationError, match="gehört nicht zu vollzug"):
        gs.Functions(types={"Beschlussvorlage": "vollzug/anfrage"})
    with pytest.raises(ValidationError, match="nennt keine Funktion"):
        gs.Functions(types={"Beschlussvorlage": "rest/art_unbekannt"})
    with pytest.raises(ValidationError, match="nennt keine Funktion"):
        gs.Functions(type_prefixes={"antrag": "antrag"})


def test_a_prefix_is_lowercase() -> None:
    with pytest.raises(ValidationError, match="klein"):
        gs.Functions(type_prefixes={"Antrag": "initiative/antrag"})


def test_a_type_stands_in_one_table_only() -> None:
    with pytest.raises(ValidationError, match="collection_admin"):
        gs.Functions(
            types={"Verwaltungsvorlage": "vollzug/beschlussvorlage"},
            collection_admin=["Verwaltungsvorlage"],
        )


def test_a_pattern_that_does_not_compile_fails_on_loading() -> None:
    with pytest.raises(ValidationError, match="kein gültiger regulärer Ausdruck"):
        gs.Functions(symbol_title=["resolution("])
    with pytest.raises(ValidationError, match="kein Instrument des Vollzugs"):
        gs.Functions.model_validate({"enforcement": [{"instrument": "antrag", "patterns": ["x"]}]})


def test_a_party_belongs_to_one_fraction_on_any_day() -> None:
    first = {"key": "A+B", "parties": ["A", "B"], "valid_from": date(2020, 11, 1)}
    gs.Functions.model_validate({"fractions": [first]})
    later = {"key": "B+C", "parties": ["B", "C"], "valid_from": date(2021, 1, 1)}
    with pytest.raises(ValidationError, match="zugleich"):
        gs.Functions.model_validate({"fractions": [first, later]})
    closed = {**first, "valid_to": date(2020, 12, 31)}
    gs.Functions.model_validate({"fractions": [closed, later]})  # nacheinander ist erlaubt
    with pytest.raises(ValidationError, match="mindestens zwei"):
        gs.Functions.model_validate(
            {"fractions": [{"key": "A", "parties": ["A"], "valid_from": date(2020, 1, 1)}]}
        )


def test_majorities_are_ordered_and_disjoint() -> None:
    a = _majority("eins", date(2014, 5, 25), date(2020, 10, 31))
    b = _majority("zwei", date(2020, 11, 1), None)
    found = gs.Majorities.model_validate({"terms": [a, b]})
    assert found.on(date(2020, 10, 31)).period == "eins"  # type: ignore[union-attr]
    assert found.on(date(2020, 11, 1)).period == "zwei"  # type: ignore[union-attr]
    assert found.on(date(2014, 5, 24)) is None
    assert found.on(None) is None
    with pytest.raises(ValidationError, match="überlappen"):
        gs.Majorities.model_validate({"terms": [a, _majority("zwei", date(2020, 10, 1), None)]})
    with pytest.raises(ValidationError, match="überlappen"):
        gs.Majorities.model_validate({"terms": [b, a]})


def test_a_majority_says_its_source_and_its_date_as_precisely_as_the_source() -> None:
    gs.Majority(**_majority("eins", date(2021, 1, 1), None, agreement_date="2021-01-19"))
    gs.Majority(**_majority("eins", date(2021, 1, 1), None, agreement_date="2025-12"))
    with pytest.raises(ValidationError, match="kein Datum"):
        gs.Majority(**_majority("eins", date(2021, 1, 1), None, agreement_date="Januar 2021"))
    with pytest.raises(ValidationError, match="endet vor"):
        gs.Majority(**_majority("eins", date(2021, 1, 1), date(2020, 1, 1)))


def test_the_majority_applies_to_council_and_committees_by_default() -> None:
    assert gs.Majorities().body_kinds == ["rat", "ausschuss"]


def test_both_blocks_are_settings_fields_and_count_in_the_fingerprint() -> None:
    settings = load_settings(cwd=NOWHERE)
    assert isinstance(settings.functions, gs.Functions)
    assert isinstance(settings.majorities, gs.Majorities)
    other = settings.model_copy(
        update={"functions": settings.functions.model_copy(update={"variant": "A"})}
    )
    assert other.fingerprint() != settings.fingerprint()


def _defaults_block() -> dict[str, Any]:
    text = resources.files("georep").joinpath("defaults.toml").read_text(encoding="utf-8")
    block: dict[str, Any] = tomllib.loads(text)["functions"]
    return block


def test_the_defaults_carry_no_word_of_one_city_or_one_state() -> None:
    """Review 2026-11-24, M3: der Tippfehler einer Quelle und § 60 GO NRW gehören ins Stadtprofil."""
    block = _defaults_block()
    words = [
        *block["review_title"],
        *(p for rule in block["enforcement"] for p in rule["patterns"]),
    ]
    assert "pürfantrag" not in words
    assert not [w for w in words if "60er" in w]


def test_the_city_adds_its_words_to_the_language_and_keeps_the_rest() -> None:
    """deep_merge ersetzt Listen: das Stadtprofil wiederholt die Liste und hängt seine Wörter an.
    Läuft die Sprache in ``defaults.toml`` weiter, fällt die Kopie hier auf."""
    block = _defaults_block()
    city = load_settings(cwd=NOWHERE).functions
    assert city.review_title == [*block["review_title"], "pürfantrag"]
    defaults = {rule["instrument"]: rule["patterns"] for rule in block["enforcement"]}
    found = {rule.instrument: rule.patterns for rule in city.enforcement}
    assert list(found) == list(defaults)
    assert found == defaults | {"dringlichkeit": [*defaults["dringlichkeit"], "60er-beschluss"]}
    second = load_settings(profile="moenchengladbach", cwd=NOWHERE).functions
    assert second.review_title == block["review_title"]
    assert {rule.instrument: rule.patterns for rule in second.enforcement} == defaults
