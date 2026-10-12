"""Jeder Schritt trägt die Schema-Version seiner Ausgabe (Review-Befund 3, 2026-10-13).

Die Version steht im Modul, das die Datei schreibt (``BODIES_SCHEMA_VERSION`` und so weiter) oder
für die zwei Modelle in ``georep.schema``, damit das Register sie ohne sklearn kennt; sie landet
über ``write_parquet`` in den Parquet-Metadaten. Sie muss aber auch am ``Step`` stehen:
nur dann schreibt ``write_stamp`` sie in den Stamp, und nur dann kann ``stamp_mismatch`` je
„Schema geändert" melden. Fehlt sie dort, bleibt der Stamp nach einer Schemaänderung gültig und
die Kette rechnet mit einer Datei weiter, deren Spalten sich geändert haben.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from georep.layout import Layout
from georep.pipeline import METRICS_SCHEMA, PARTIES_SCHEMA, build_steps, stamp_mismatch
from georep.prep.bodies import BODIES_SCHEMA_VERSION
from georep.prep.papers import CORPUS_SCHEMA_VERSION
from georep.schema import ASSIGNMENT_SCHEMA_VERSION, TOPICS_SCHEMA_VERSION
from georep.settings import Settings

VERSIONS = {
    "corpus": CORPUS_SCHEMA_VERSION,
    "bodies": BODIES_SCHEMA_VERSION,
    "topics": TOPICS_SCHEMA_VERSION,
    "committees": ASSIGNMENT_SCHEMA_VERSION,
    # Punkt 46: der neue Schritt und die drei Spalten mehr in wahlbezirke_parteien
    "metrics": METRICS_SCHEMA,
    "parties": PARTIES_SCHEMA,
}


@pytest.fixture
def steps(default_settings: Settings, tmp_path: Path) -> dict[str, int]:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    return {s.name: s.schema_version for s in build_steps(default_settings, layout)}


def test_each_step_carries_the_schema_version_of_its_module(steps: dict[str, int]) -> None:
    for name, version in VERSIONS.items():
        assert steps[name] == version, (name, steps[name], version)


def test_a_bumped_schema_version_makes_the_stamp_stale(
    default_settings: Settings, tmp_path: Path
) -> None:
    """Der Grund für den Test oben: sonst meldet ``stamp_mismatch`` die Änderung nie."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    step = next(s for s in build_steps(default_settings, layout) if s.name == "topics")
    stamped: dict[str, object] = {
        "schema_version": step.schema_version,
        "code_version": "0.0.0",
        "settings_fingerprint": default_settings.fingerprint(),
        "inputs": {},
    }
    assert stamp_mismatch(stamped, step, default_settings) != "Schema geändert"
    stamped["schema_version"] = step.schema_version - 1
    assert stamp_mismatch(stamped, step, default_settings) == "Schema geändert"
