"""Eine Session pro Prüfung; CI und lokal rufen dieselben. Alle laufen in der uv-Projektumgebung."""

from __future__ import annotations

import tomllib
from pathlib import Path

import nox

nox.options.default_venv_backend = "none"
nox.options.sessions = ["lint", "typecheck", "deps", "test"]

# Pakete, die nie wieder ins Lockfile dürfen: pandas ist Konrads Vorgabe (Polars), die anderen
# zogen es transitiv (Phase 3, 2026-10-11). scikit-learn stand hier bis zum 2026-10-12 und ist seit
# Option 06 Laufzeitabhängigkeit (Konrad, 2026-10-11; decisions.md, Punkt „scikit-learn für das
# Themenmodell"): es zieht kein pandas, und der Import bleibt auf ein Modul begrenzt
# (tests/unit/test_dependency_boundary.py).
FORBIDDEN = {"pandas", "geopandas", "osmnx"}


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


# Rein-pythonische Funktionen mit deal-Verträgen; Polars-Funktionen bleiben draußen, crosshair kann
# keine Rust-Erweiterung symbolisch ausführen (docs/architecture.md, „Verträge").
VERIFY_TARGETS = [
    "georep.prep.extract.after_marker",
    "georep.prep.extract.normalise_text",
    "georep.http.cache_pattern",
    "georep.settings.deep_merge",
    "georep.sources.wiki.parse_point",
    "georep.sources.wiki.geosearch_params",
    "georep.sources.wiki.sparql_query",
    "georep.sources.overpass.overpass_query",
    "georep.sources.overpass.street_names",
    "georep.analysis.weights.district_weight",
    "georep.analysis.weights.idf_weight",
    "georep.report.model.format_de",
    "georep.report.search.canonical_term",
    "georep.report.charts.nice_ticks",
    # Punkt 45: die Ableitung der Stoppwörter aus dem Profil ist rein und total.
    "georep.analysis.topics.profile_stop_words",
    # Nicht dabei: georep.analysis.topics.name_stop_words (Punkt 45). Es rechnet zwei
    # CountVectorizer-Durchgänge über die Texte; crosshair müsste sklearn symbolisch verfolgen.
    # Seine Eigenschaften prüfen tests/property/test_topics_props.py und die Verträge zur
    # Laufzeit. Ebenso nicht dabei: georep.prep.bodies.parse_reference (Option 05). Sein Parameter ist ein
    # BodyRules, dessen Feld ``pattern`` den Typ ``re.Pattern[str] | None`` hat; crosshair baut für
    # den Union-Zweig einen symbolischen String und ruft ``re.compile`` darauf, was mit
    # ``re.PatternError: missing ), unterminated subpattern`` aus dem eigenen Proxy fliegt und die
    # ganze Sitzung abbricht, bevor sie berichtet (crosshair 0.0.111, Python 3.14, geprüft am
    # 2026-10-12). Ein Artefakt des Werkzeugs, kein Befund: die Funktion kompiliert keinen Regex
    # aus Daten, nur ``bodies.reference_pattern`` aus den Settings. Angegriffen wird sie weiter von
    # ``deal.cases`` in tests/property/test_contract_cases.py.
    "georep.prep.context.ordinal_score",  # Option 03
    "georep.analysis.parties.classify_document",  # Option 04
    "georep.crosswalk.largest_remainder",  # Option 02
    "georep.prep.precincts.district_from_id",  # Option 01
    "georep.prep.pois.is_city_facility",  # Regel 1, decisions.md Punkt 44
    "tests.property.oracle_matcher.oracle_extract",
]


@nox.session
def verify(session: nox.Session) -> None:
    """crosshair sucht Gegenbeispiele zu den deal-Verträgen der rein-pythonischen Funktionen.

    Rot nur bei einem Gegenbeispiel (Exit 1); „Not confirmed" ist eine Zeitangabe, kein Befund,
    darum --report_all. Rund drei Minuten bei 20 s CPU je Bedingung (2026-10-11). Der erste Lauf
    fand street_names({"elements": 0}) -> TypeError; der Lauf am 2026-10-12 fand zwei
    Gegenbeispiele in classify_document (eine Organisation, die auf einen Schlüssel außerhalb der
    Parteiliste zeigt, und ein doppelter Schlüssel in der Liste; beide behoben).
    """
    session.run(
        "uv",
        "run",
        "crosshair",
        "check",
        *VERIFY_TARGETS,
        "--analysis_kind",
        "deal",
        "--report_all",
        "--per_condition_timeout",
        "20",
        *session.posargs,
    )


@nox.session
def mutate(session: nox.Session) -> None:
    """Mutationstest mit pytest-gremlins über search/ und analysis/, einmal pro Phase, kein Gate.

    ``analysis/topics.py`` bleibt außen vor (Kommentar unten); seine Zahlen stehen datiert in
    docs/mutation-2026-10-12.md.

    Subprocess-Executor, kein fork (mutmut 3 blockierte so mit Polars, docs/mutation-2026-10-11.md).
    Rund 100 s mit sechs Arbeitern (2026-10-11); der Bericht liegt unter coverage/gremlins/ (gitignored),
    die Zahlen und die Deutung der Überlebenden stehen datiert in docs/mutation-2026-10-11.md.
    """
    session.run(
        "uv",
        "run",
        "pytest",
        "tests/unit",
        "tests/property",
        "tests/golden",
        "-m",
        "not slow and not network and not bench",
        "-p",
        "no:cacheprovider",
        "--gremlins",
        # Ohne analysis/topics.py: jeder Mutant dort laesst die schnelle Suite laufen, und die
        # rechnet seit Option 06 mehrfach NMF; der Lauf vom 2026-10-12 war nach 35 Minuten noch
        # nicht durch. Das Modul misst man gezielt (docs/mutation-2026-10-12.md).
        "--gremlin-targets=src/georep/search,src/georep/analysis/hits.py,"
        "src/georep/analysis/regression.py,src/georep/analysis/weights.py,"
        # Punkt 45: der Klassifikator gehört dazu, sein Modell rechnet in der schnellen Suite
        # nur auf 39 synthetischen Dokumenten (anders als das Themenmodell oben).
        "src/georep/analysis/committees.py",
        "--gremlin-report=console,json",
        "--gremlin-workers=6",
        "--gremlin-mutant-timeout=60",
        *session.posargs,
    )


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
