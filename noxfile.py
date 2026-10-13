"""Eine Session pro Prüfung; CI und lokal rufen dieselben. Alle laufen in der uv-Projektumgebung."""

from __future__ import annotations

import shlex
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
    # Punkt 46: feste Klassengrenzen; rein, total und ohne Polars
    "georep.report.charts.classify_fixed",
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
    # --- Punkt 53 (2026-10-13): acht Kandidaten aus den Modulen des Ausbaus, je einzeln mit
    # ``uv run crosshair check <ziel> --analysis_kind deal --per_condition_timeout 20`` geprüft.
    # Drei fanden ein Gegenbeispiel, und alle drei waren echt -- eine Annahme über die Eingabe,
    # die nur in der Nachbedingung stand: ``report.terms.terms_payload`` (ein Begriff ohne
    # Treffer), ``report.geometry.fit`` (eine unendliche Grenze) und ``report.model.body_figures``
    # (eine fremde Gremienklasse als ``KeyError``). Alle drei haben jetzt eine Vorbedingung, und
    # danach ist die Sitzung grün.
    "georep.prep.precincts.canonical_precincts",  # Option 01, 21 s
    "georep.prep.voters.canonical_names",  # Option 02, 21 s
    "georep.report.terms.terms_payload",  # Punkt 49
    "georep.report.search.search_payload",  # Option 08, 20 s
    "georep.report.charts.classify",  # Quantilklassen, 22 s
    "georep.report.charts.legend_for",  # Punkt 46, 21 s
    "georep.report.geometry.fit",
    "georep.report.model.body_figures",  # Option 05
    "georep.report.publish.render_comparison",  # Option 01, 25 s
    # Nicht dabei, mit gemessenem Grund: ``report.charts.bars`` (am 2026-10-13 probiert, Exit 1
    # nach 18 s). Sein Gegenbeispiel ist eine Dokumentzahl mit 300 Stellen neben einer denormalen
    # Leinwand, an der die Vorbedingung von ``nice_ticks`` scheitert; die Vorbedingung, die das
    # abfinge („die Dokumentzahl passt in eine Fließkommazahl"), wäre eine Aussage über crosshair
    # und nicht über dieses Programm. Die endlichen, positiven Maße stehen trotzdem jetzt in
    # seiner Vorbedingung -- das war der erste, echte Teil desselben Befunds.
    # Nicht probiert, weil der Typ es ausschließt: alles mit ``pl.DataFrame``, ``Path``,
    # ``Traversable`` oder shapely-Geometrie in der Signatur (docs/architecture.md, „Verträge").
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


# Die Ziele der Mutationssitzung: alles, was gemessen ist, damit der nächste Lauf dieselbe Liste
# hat (docs/mutation-2026-10-11.md, -12.md, -13.md). Nicht dabei, mit Grund und Zahl:
#
#   src/georep/analysis/topics.py   jeder Mutant rechnet NMF; der Lauf vom 2026-10-12 war nach
#                                   35 Minuten nicht durch (docs/mutation-2026-10-12.md).
#   src/georep/report/model.py      noch nicht gemessen: 1 900 Zeilen, und das Modell entsteht in
#   src/georep/report/charts.py     jedem Test der Seite neu. Ein eigener Lauf, wenn jemand ihn
#   src/georep/report/build.py      misst; Stand 2026-10-13 ungemessen und darum nicht behauptet.
#
# Die Zeiten der dreizehn Module von 2026-10-13 stehen in docs/mutation-2026-10-13.md, § Zahlen;
# zusammen rund 20 Minuten im Zuschnitt je Modul. Wer nur einen Teil will, gibt
# ``--gremlin-targets=…`` als Posargs mit -- die letzte Angabe gewinnt. Genau das tut der
# wöchentliche Qualitätslauf (.github/workflows/quality.yml) mit den acht Modulen unter 90 s.
GREMLIN_TARGETS = ",".join(
    [
        # 2026-10-11 und -12
        "src/georep/search",
        "src/georep/analysis/hits.py",
        "src/georep/analysis/regression.py",
        "src/georep/analysis/weights.py",
        # 2026-10-13: die dreizehn Module, die seit v0.11.0 dazukamen oder sich stark änderten
        "src/georep/analysis/committees.py",
        "src/georep/analysis/scaling.py",
        "src/georep/analysis/parties.py",
        "src/georep/analysis/timeline.py",
        "src/georep/analysis/periods.py",
        "src/georep/analysis/ols.py",
        "src/georep/prep/pois.py",
        "src/georep/prep/precincts.py",
        "src/georep/crosswalk.py",
        "src/georep/report/publish.py",
        "src/georep/report/terms.py",
        "src/georep/report/comparison.py",
        "src/georep/report/search.py",
    ]
)


@nox.session
def mutate(session: nox.Session) -> None:
    """Mutationstest mit pytest-gremlins über die gemessenen Module, kein Gate.

    Subprocess-Executor, kein fork (mutmut 3 blockierte so mit Polars, docs/mutation-2026-10-11.md).
    **Drei Arbeiter, nicht sechs**: mit sechs wurde die Sitzung am 2026-10-12 unter der Last von
    acht parallelen Agenten abgeschossen, und der Rechner hat dreizehn Kerne, von denen Polars und
    BLAS schon welche nehmen. Der Bericht liegt unter coverage/gremlins/ (gitignored), die Zahlen
    und die Deutung der Überlebenden stehen datiert in docs/mutation-2026-10-1{1,2,3}.md.

    Die Testauswahl je Mutant ist **aus**: ``--cov`` in ``addopts`` lässt den Abdeckungsvorlauf
    von gremlins leer ausgehen (zwei Warnungen im Lauf, mit ``--gremlin-explain`` bestätigt), und
    ohne Daten fällt es auf alle übergebenen Tests zurück. Für die Quote ist das richtig -- kein
    Mutant überlebt, weil ein Test fehlte --, für die Laufzeit teuer: wer ein einzelnes Modul
    messen will, übergibt auch nur dessen Testdateien (docs/mutation-2026-10-13.md).
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
        f"--gremlin-targets={GREMLIN_TARGETS}",
        "--gremlin-report=console,json",
        "--gremlin-workers=3",
        "--gremlin-mutant-timeout=60",
        *session.posargs,
    )


@nox.session
def alone(session: nox.Session) -> None:
    """Reihenfolgeunabhängigkeit: jede Testdatei einmal allein, dann die Suite rückwärts.

    Zwei Prüfungen, beide ohne Gate-Anspruch und beide von Hand (Punkt 53):

    1. **Jede Datei allein.** Ein Test, der nur grün ist, weil ein anderer vorher eine Datei
       geschrieben hat, fällt sonst nie auf -- genau das war
       ``test_a_city_that_lost_its_run_leaves_the_published_folder`` am 2026-10-12. Drei Dateien
       parallel; „keine Tests gesammelt" (Exit 5) ist kein Fehler, sondern eine Datei, in der
       jeder Test ``slow`` oder ``network`` trägt.
    2. **Die ganze schnelle Suite rückwärts.** ``-p no:randomly`` gibt es hier nicht; die
       Reihenfolge kommt aus ``--co`` und wird umgedreht. ``xargs -d '\\n'`` statt
       Wort-Trennung, denn ein parametrierter Testname enthält Leerzeichen (``-auf'm``).

    Gemessen am 2026-10-13: 97 Dateien, 94 grün und 3 ohne schnelle Tests; rückwärts 1061 Tests
    in 103 s, Exit 0. Keine Abhängigkeit gefunden.
    """
    marker = "not slow and not network and not bench"
    files = sorted(
        str(path)
        for folder in ("tests/unit", "tests/golden", "tests/property")
        for path in Path(folder).glob("test_*.py")
    )
    session.log(f"{len(files)} Testdateien je allein, drei parallel")
    quoted = " ".join(shlex.quote(f) for f in files)
    session.run(
        "bash",
        "-c",
        f"printf '%s\\n' {quoted} | xargs -P 3 -d '\\n' -I{{}} "
        f"uv run pytest {{}} -m {shlex.quote(marker)} -p no:cacheprovider --no-cov "
        "|| echo 'mindestens eine Datei allein nicht gruen (Exit 5 = nur slow/network)'",
        external=True,
    )
    session.log("und einmal rückwärts")
    session.run(
        "bash",
        "-c",
        f"uv run pytest -m {shlex.quote(marker)} --co -p no:cacheprovider 2>/dev/null "
        "| grep '::' | tac > \"${TMPDIR:-/tmp}/georep-nodes-rev.txt\" && "
        "xargs -a \"${TMPDIR:-/tmp}/georep-nodes-rev.txt\" -d '\\n' --max-args=100000 "
        "uv run pytest -p no:cacheprovider --no-cov",
        external=True,
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
