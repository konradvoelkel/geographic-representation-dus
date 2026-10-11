from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import deal
import pytest
from hypothesis import HealthCheck
from hypothesis import settings as hypothesis_settings

from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.settings import Settings, load_settings

# Profile: "dev" (Standard) ist schnell, "ci" gründlicher; Auswahl über HYPOTHESIS_PROFILE.
# Fixtures mit Modul-Scope in Property-Tests sind Absicht (Referenz-GeoJSON einmal lesen).
hypothesis_settings.register_profile(
    "dev",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
hypothesis_settings.register_profile(
    "ci",
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

REPO = Path(__file__).resolve().parents[1]
# Der eingefrorene Datensatz der Arbeit; wird nur gelesen.
REFERENCE = REPO / "reference"
MINI = REPO / "tests" / "fixtures" / "mini"
PDF_FIXTURES = REPO / "tests" / "fixtures" / "pdf"


@pytest.fixture(autouse=True)
def _reset_contracts() -> Iterator[None]:
    """deal schaltet prozessweit; ein Test, der Verträge abschaltet, darf keinen anderen anstecken."""
    yield
    deal.reset()


@pytest.fixture(scope="session")
def reference_root() -> Path:
    return REFERENCE


@pytest.fixture(scope="session")
def mini_root() -> Path:
    return MINI


@pytest.fixture(scope="session")
def pdf_fixtures() -> Path:
    return PDF_FIXTURES


@pytest.fixture(scope="session")
def default_settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


@pytest.fixture(scope="session")
def mini_run(tmp_path_factory: pytest.TempPathFactory, default_settings: Settings) -> Layout:
    """Die Offline-Kette einmal je Sitzung auf der Mini-Fixture: Tests lesen daraus, schreiben nie hinein."""
    root = tmp_path_factory.mktemp("mini_run")
    layout = Layout(root / "data", root / "cache", MINI)
    bootstrap(layout)
    run_pipeline(build_steps(default_settings, layout), default_settings)
    return layout
