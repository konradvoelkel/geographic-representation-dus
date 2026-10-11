"""Eine Session pro Prüfung; CI und lokal rufen dieselben. Alle laufen in der uv-Projektumgebung."""

from __future__ import annotations

import tomllib
from pathlib import Path

import nox

nox.options.default_venv_backend = "none"
nox.options.sessions = ["lint", "typecheck", "deps", "test"]

# Pakete, die nie wieder ins Lockfile dürfen: pandas ist Konrads Vorgabe (Polars), die anderen
# zogen es transitiv (Phase 3, 2026-10-11).
FORBIDDEN = {"pandas", "geopandas", "osmnx", "scikit-learn"}


@nox.session
def lint(session: nox.Session) -> None:
    session.run("uv", "run", "ruff", "check", ".")
    session.run("uv", "run", "ruff", "format", "--check", ".")


@nox.session
def typecheck(session: nox.Session) -> None:
    session.run("uv", "run", "mypy")


@nox.session
def deps(session: nox.Session) -> None:
    """Das Lockfile enthält keines der verbotenen Pakete, auch nicht transitiv."""
    lock = tomllib.loads(Path("uv.lock").read_text(encoding="utf-8"))
    names = {pkg["name"] for pkg in lock.get("package", [])}
    found = sorted(FORBIDDEN & names)
    if found:
        session.error(f"Verbotene Pakete im Lockfile: {found}")
    session.log(f"Lockfile: {len(names)} Pakete, keines von {sorted(FORBIDDEN)}")


@nox.session
def test(session: nox.Session) -> None:
    """Schnelle Suite parallel; Abdeckung ist eine Untergrenze, kein Ziel (Skript, Kapitel Testing)."""
    session.run(
        "uv",
        "run",
        "pytest",
        "-n",
        "auto",
        "-m",
        "not slow and not network and not bench",
        "--cov=georep",
        "--cov-report=term-missing:skip-covered",
        "--cov-fail-under=90",
        *session.posargs,
    )


@nox.session
def golden(session: nox.Session) -> None:
    """Volle Referenz, Sekunden."""
    session.run("uv", "run", "pytest", "-m", "slow", *session.posargs)


@nox.session
def bench(session: nox.Session) -> None:
    """Heiße Pfade gegen den letzten gespeicherten Lauf in .benchmarks/ (gitignored).

    Rot ab 20 % langsamer im Minimum: 10 % lagen unter dem gemessenen Rauschen (12,7 % zwischen sechs
    Läufen gleichen Codes bei den 1-ms-Polars-Stufen, 2026-10-11), 20 % liegen über allem Gemessenen
    und fangen jede echte Verschlechterung von Matcher (Rauschen 9 %) und Extraktion (4 %). Der erste
    Lauf auf einem Rechner legt nur die Baseline an, denn ``--benchmark-compare-fail`` ohne
    Vergleichslauf ist für pytest-benchmark ein Bedienfehler (Exit 4, 2026-10-11). Die Zahlen, die
    bleiben sollen, stehen datiert in docs/profiling/README.md.
    """
    saved = sorted(Path(".benchmarks").glob("*/*.json"))
    if saved:
        session.log(f"Vergleich gegen {saved[-1].name}")
        compare = ["--benchmark-compare", "--benchmark-compare-fail=min:20%"]
    else:
        session.log("Keine Baseline in .benchmarks/: dieser Lauf legt sie an, kein Vergleich")
        compare = []
    session.run(
        "uv",
        "run",
        "pytest",
        "tests/bench",
        "-m",
        "bench",
        "--benchmark-autosave",
        # Die CPU-Taktfrequenz (hz_actual) schwankt zwischen zwei Läufen auf demselben Rechner;
        # ohne den Filter druckt jeder Vergleich die komplette cpuinfo zweimal.
        "-W",
        "ignore:Benchmark machine_info is different",
        *compare,
        *session.posargs,
    )


@nox.session
def profile(session: nox.Session) -> None:
    """cProfile eines echten Schritts, ``nox -s profile -- index``; Anzeige: ``uv run snakeviz <datei>``."""
    session.run("uv", "run", "georep", "profile", *session.posargs)
