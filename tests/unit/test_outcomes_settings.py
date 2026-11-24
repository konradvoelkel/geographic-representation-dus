"""Die Settings von Vorhaben 26: ``[outcomes]``, der Wortschatz der Sitzungsleitung und der Prüfauftrag.

Der Wortschatz steht im Stadtprofil, weil jede Sitzungsleitung ihre eigenen Wörter einträgt
(Mönchengladbach kennt andere, Messdokument ``docs/plans/26-beschluesse.md``, § 10, Punkt 6). Eine
Klasse, die nicht zu ihrer Stufe passt, soll beim Laden auffallen, nicht erst als falsche Zahl auf
der Seite: eine „Entscheidung in der Sache" ersetzt jede frühere, ein „Stand" nie (§ 3.1).
"""

from __future__ import annotations

import re
import tomllib
from importlib import resources
from pathlib import Path

import pytest
from pydantic import ValidationError

import georep.settings as gs
from georep.settings import load_settings

NOWHERE = Path("/nonexistent")

# Der Wortschatz der drei Düsseldorfer Netzläufe vom 2026-11-23 mit Stufe und Klasse, wie er vor der
# Stichprobe festgelegt wurde (Messdokument § 3.1, Commit c94ae31; Messskript ``RESULT``).
VOCABULARY = {
    "einstimmig beschlossen": ("sache", "beschlossen"),
    "mehrheitlich beschlossen": ("sache", "beschlossen"),
    "beschlossen": ("sache", "beschlossen"),
    "Empfehlung einstimmig beschlossen": ("sache", "beschlossen"),
    "Empfehlung mehrheitlich beschlossen": ("sache", "beschlossen"),
    "abweichend beschlossen": ("sache", "geaendert"),
    "Empfehlung abweichend beschlossen": ("sache", "geaendert"),
    "einstimmig abgelehnt": ("sache", "abgelehnt"),
    "mehrheitlich abgelehnt": ("sache", "abgelehnt"),
    "abgelehnt aufgrund Stimmengleichheit": ("sache", "abgelehnt"),
    "zurückgewiesen": ("sache", "abgelehnt"),
    "Empfehlung einstimmig abgelehnt": ("sache", "abgelehnt"),
    "Empfehlung mehrheitlich abgelehnt": ("sache", "abgelehnt"),
    "zurückgezogen": ("sache", "zurueckgezogen"),
    "zur Kenntnis genommen": ("stand", "erledigt"),
    "passieren lassen": ("stand", "erledigt"),
    "beantwortet": ("stand", "erledigt"),
    "schriftlich beantwortet": ("stand", "erledigt"),
    "vertagt": ("stand", "vertagt"),
    "zurückgestellt": ("stand", "vertagt"),
    "verwiesen": ("stand", "offen"),
}


def test_the_switch_is_off_and_the_defaults_carry_no_vocabulary() -> None:
    """``defaults.toml`` kennt die Sprache des Prüfauftrags, aber keinen Eintrag einer Stadt."""
    text = resources.files("georep").joinpath("defaults.toml").read_text(encoding="utf-8")
    block = tomllib.loads(text)["outcomes"]
    assert block["enabled"] is False
    assert block["results"] == {} and block["package"] == ""
    assert block["practice_share"] == 0.4 and block["practice_min"] == 10
    assert block["followup_roles"] == ["vorlage", "information", "bedarf", "af"]
    review = block["review"]
    for key in ("marker", "reason", "review", "separable", "not_verb", "measure", "neutral"):
        assert review[key], key
    assert gs.Outcomes().enabled is False


def test_the_city_carries_the_vocabulary_of_the_measurement() -> None:
    outcomes = load_settings(profile="duesseldorf", cwd=NOWHERE).outcomes
    assert dict(outcomes.results) == VOCABULARY


@pytest.mark.parametrize(
    ("profile", "folder"),
    [
        ("duesseldorf", "duesseldorf"),
        ("duesseldorf-vergleich", "duesseldorf"),  # der Vergleich *ist* die Hauptperiode (Punkt 52)
        ("duesseldorf-2014", "2014-2020"),
        ("duesseldorf-2025", "2025"),
    ],
)
def test_each_period_reads_its_own_file_of_the_package(profile: str, folder: str) -> None:
    settings = load_settings(profile=profile, cwd=NOWHERE)
    assert settings.outcomes.package == Path(
        f"snapshots/duesseldorf-beschluesse/raw/tagesordnungspunkte-{folder}.parquet"
    )
    assert dict(settings.outcomes.results) == VOCABULARY  # geerbt aus dem Stadtprofil


def test_the_second_city_stays_off() -> None:
    """Mönchengladbach trägt andere Einträge, manche ohne eindeutige Klasse (§ 10, Punkt 6)."""
    outcomes = load_settings(profile="moenchengladbach", cwd=NOWHERE).outcomes
    assert outcomes.enabled is False
    assert outcomes.results == {} and outcomes.package is None


def test_a_class_must_belong_to_its_stage() -> None:
    gs.Outcomes(results={"beschlossen": ("sache", "beschlossen"), "vertagt": ("stand", "vertagt")})
    with pytest.raises(ValidationError, match="Klasse passt nicht zur Stufe"):
        gs.Outcomes(results={"vertagt": ("sache", "vertagt")})
    with pytest.raises(ValidationError, match="Klasse passt nicht zur Stufe"):
        gs.Outcomes(results={"beschlossen": ("stand", "beschlossen")})
    with pytest.raises(ValidationError):
        gs.Outcomes.model_validate({"results": {"beschlossen": ["beschluss", "beschlossen"]}})


def test_no_value_carries_the_class_of_a_missing_entry() -> None:
    """``ohne_ergebnis`` heißt: kein Eintrag. Ein Wert, der es trüge, wäre ein Widerspruch."""
    with pytest.raises(ValidationError, match="Klasse passt nicht zur Stufe"):
        gs.Outcomes(results={"Siehe Niederschrift": ("stand", "ohne_ergebnis")})
    with pytest.raises(ValidationError, match="leerer Wert"):
        gs.Outcomes(results={" ": ("stand", "erledigt")})


def test_switching_on_needs_a_vocabulary() -> None:
    with pytest.raises(ValidationError, match=re.escape("[outcomes.results]")):
        gs.Outcomes(enabled=True)
    assert gs.Outcomes(enabled=True, results={"vertagt": ("stand", "vertagt")}).enabled


def test_a_broken_review_pattern_fails_when_loading() -> None:
    with pytest.raises(ValidationError, match="kein gültiger regulärer Ausdruck"):
        gs.OutcomeReview(review=["prüf(ung"])


def test_the_practice_share_is_a_share() -> None:
    for wrong in (0.0, 1.5):
        with pytest.raises(ValidationError):
            gs.Outcomes(practice_share=wrong)
    with pytest.raises(ValidationError):
        gs.Outcomes(practice_min=0)


def test_an_empty_package_is_none() -> None:
    assert gs.Outcomes.model_validate({"package": ""}).package is None


def test_a_followup_role_is_a_role_of_the_procedures() -> None:
    """Die Rollen der Folgevorlagen sind das Vokabular von Vorhaben 14 (``ProcedureRole``)."""
    gs.Outcomes(followup_roles=["vorlage", "information"])
    with pytest.raises(ValidationError):
        gs.Outcomes.model_validate({"followup_roles": ["verwaltungsvorlage"]})
