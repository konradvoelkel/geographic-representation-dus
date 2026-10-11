"""Eine Session pro Prüfung; CI und lokal rufen dieselben. Alle laufen in der uv-Projektumgebung."""

from __future__ import annotations

import re
from pathlib import Path

import nox

nox.options.default_venv_backend = "none"
nox.options.sessions = ["lint", "typecheck", "baseline", "test"]

# Nur die flachen Altcode-Module: src/ als Verzeichnis liesse mypy src/georep/ zugleich als
# src.georep.* und georep.* sehen und abbrechen.
LEGACY = [*sorted(str(p) for p in Path("src").glob("*.py")), "run.py"]
# Altcode-Baseline (docs/baseline-2026-10-10.md): 18 Fehler unter Python 3.12 und den alten Pins,
# 14 unter dem Lockfile mit Python 3.14 vom 2026-10-10. Gilt der strengere Wert.
LEGACY_MYPY_ERRORS = 14


@nox.session
def lint(session: nox.Session) -> None:
    session.run("uv", "run", "ruff", "check", ".")
    session.run("uv", "run", "ruff", "format", "--check", ".")


@nox.session
def typecheck(session: nox.Session) -> None:
    """Strict für neuen Code (tests/, ab Phase 2 src/georep/)."""
    session.run("uv", "run", "mypy")


@nox.session
def baseline(session: nox.Session) -> None:
    """Altcode: nicht schlechter als die Baseline, nicht sauber."""
    out = session.run(
        "uv",
        "run",
        "mypy",
        "--config-file=",
        "--ignore-missing-imports",
        "--python-version",
        "3.14",
        *LEGACY,
        success_codes=[0, 1],
        silent=True,
    )
    text = out if isinstance(out, str) else ""
    match = re.search(r"Found (\d+) error", text)
    errors = int(match.group(1)) if match else 0
    session.log(f"Altcode mypy: {errors} Fehler (Baseline {LEGACY_MYPY_ERRORS})")
    if errors > LEGACY_MYPY_ERRORS:
        session.error(f"Altcode ist schlechter geworden: {errors} > {LEGACY_MYPY_ERRORS}\n{text}")


@nox.session
def test(session: nox.Session) -> None:
    session.run("uv", "run", "pytest", "-m", "not slow and not network", *session.posargs)


@nox.session
def golden(session: nox.Session) -> None:
    """Volles Referenzkorpus, Sekunden."""
    session.run("uv", "run", "pytest", "-m", "slow", *session.posargs)
