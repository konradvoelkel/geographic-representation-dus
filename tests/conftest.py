from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
# Phase 2 benennt data/ in reference/ um; bis dahin ist data/ der eingefrorene Datensatz der Arbeit.
REFERENCE = REPO / "data"
MINI = REPO / "tests" / "fixtures" / "mini"
PDF_FIXTURES = REPO / "tests" / "fixtures" / "pdf"


@pytest.fixture(scope="session")
def reference_root() -> Path:
    return REFERENCE


@pytest.fixture(scope="session")
def mini_root() -> Path:
    return MINI


@pytest.fixture(scope="session")
def pdf_fixtures() -> Path:
    return PDF_FIXTURES
