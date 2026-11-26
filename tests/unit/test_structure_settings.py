"""Die Settings von Vorhaben 11: ``[structure]``, die Muster der Dokumentstruktur je Stadt.

``struktur-1`` ist der validierte Entwurf ``struktur-entwurf-1`` unverändert
(``docs/plans/11-struktur.md``, § 10, Punkt 1): die Profilblöcke müssen genau die Muster des
Messskripts tragen, sonst gälte die Validierung (188 von 200) nicht mehr für den gebauten Schritt.
Ein Tippfehler in einem Muster soll beim Laden auffallen, nicht erst in einer Zahl.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from importlib import resources
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pydantic import ValidationError

import georep.settings as gs
from georep.settings import load_settings

NOWHERE = Path("/nonexistent")
REPO = Path(__file__).resolve().parents[2]
MEASUREMENT = REPO / "docs" / "plans" / "11-struktur-messung.py"
# Profil -> Block des Entwurfs im Messskript
DRAFT_BLOCKS = {
    "duesseldorf": "duesseldorf",
    "duesseldorf-2025": "duesseldorf",
    "duesseldorf-vergleich": "duesseldorf",
    "duesseldorf-2014": "duesseldorf-2014",
    "moenchengladbach": "moenchengladbach",
}


def _measurement() -> ModuleType:
    spec = importlib.util.spec_from_file_location("struktur_messung", MEASUREMENT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("struktur_messung", module)
    spec.loader.exec_module(module)
    return module


def _draft(name: str) -> dict[str, Any]:
    """Ein Block aus ``ENTWURF``, mit seiner Basis gemischt wie im Messskript."""
    module = _measurement()
    blocks: dict[str, Any] = tomllib.loads(module.ENTWURF)
    block: dict[str, Any] = blocks[name]
    while "base" in block:
        child = {k: v for k, v in block.items() if k != "base"}
        block = module.merge(blocks[block["base"]], child)
    return block


def test_the_switch_is_off_and_the_defaults_name_no_city() -> None:
    structure = gs.StructureSettings()
    assert structure.enabled is False
    text = resources.files("georep").joinpath("defaults.toml").read_text(encoding="utf-8")
    block = tomllib.loads(text)["structure"]
    assert block["enabled"] is False
    assert block["labels"] == {} and block["leads"] == [] and block["art"] == []
    assert block["heading"] == "" and block["page_noise"] == []
    # die Monatsnamen sind Sprache, keine Stadt: beide Städte lesen sie
    assert len(block["months"]) == 12


@pytest.mark.parametrize("profile", list(DRAFT_BLOCKS))
def test_each_profile_carries_the_validated_draft_unchanged(profile: str) -> None:
    """Jedes Muster des Entwurfs steht unverändert im Profil (Konflikt 8 der Synergien)."""
    draft = _draft(DRAFT_BLOCKS[profile])
    settings = load_settings(profile=profile, cwd=NOWHERE)
    structure = settings.structure
    assert structure.enabled is True
    assert settings.city.name == draft["city"]
    for key in (
        "heading",
        "heading_nocolon",
        "betreff_after_form",
        "lead_blocked_in",
        "level2",
        "end_markers",
        "betreff_max_lines",
        "decision_expected",
        "decision_not_expected",
        "labels",
    ):
        assert getattr(structure, key) == draft[key], key
    assert [list(pair) for pair in structure.art] == draft["art"]
    assert [lead.model_dump() for lead in structure.leads] == draft["leads"]
    assert structure.fallback.model_dump() == draft["fallback"]
    head = structure.head.model_dump()
    for key, value in draft["head"].items():
        assert head[key] == value, key


def test_the_closing_of_the_signature_block_is_the_one_of_the_draft() -> None:
    """Im Messskript stand die Grußformel des Unterschriftsblocks im Code (``signer_role``); jetzt
    im Profil, mit demselben Muster."""
    for profile in ("duesseldorf", "moenchengladbach"):
        head = load_settings(profile=profile, cwd=NOWHERE).structure.head
        assert head.closing == r"^\s*((Mit\s+)?[Ff]reundliche[n]?\s+Grü(ß|ss)e|[Gg]ez\.)"


def test_a_broken_pattern_fails_when_loading() -> None:
    with pytest.raises(ValidationError, match="kein gültiger regulärer Ausdruck"):
        gs.StructureSettings(end_markers=["(unclosed"])
    with pytest.raises(ValidationError, match="kein gültiger regulärer Ausdruck"):
        gs.StructureLead(kind="fragen", pattern="[")


def test_the_heading_names_its_label_and_rest() -> None:
    with pytest.raises(ValidationError, match="label"):
        gs.StructureSettings(heading=r"^(?P<label>\w+):")
    gs.StructureSettings(heading=r"^(?P<label>\w+):(?P<rest>.*)$")


def test_a_level_two_kind_is_a_kind_of_the_labels() -> None:
    with pytest.raises(ValidationError, match="finanzen"):
        gs.StructureSettings(labels={"Betrifft": "betreff"}, level2=["finanzen"])


def test_the_session_and_the_date_line_name_their_groups() -> None:
    with pytest.raises(ValidationError, match="gremium"):
        gs.StructureHead(session=r"zur Sitzung (?P<datum>\d+)")
    with pytest.raises(ValidationError, match="datum"):
        gs.StructureHead(date_line=r"^\s*{city}, \d+")
    gs.StructureHead(date_line=r"^\s*{city},?\s*(?P<datum>\d{1,2}\.\d{1,2}\.\d{2,4})")


def test_an_enabled_block_needs_a_heading_and_twelve_months() -> None:
    with pytest.raises(ValidationError, match="heading"):
        gs.StructureSettings(enabled=True, months=[f"m{i}" for i in range(12)])
    with pytest.raises(ValidationError, match="zwölf"):
        gs.StructureSettings(
            enabled=True, heading=r"^(?P<label>\w+):(?P<rest>.*)$", months=["januar"]
        )
