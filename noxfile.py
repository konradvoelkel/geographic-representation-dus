"""Eine Session pro Prüfung; CI und lokal rufen dieselben. Alle laufen in der uv-Projektumgebung."""

from __future__ import annotations

import concurrent.futures
import subprocess
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
    # Punkt 59: die Esri-Ringe. Beide sind rein-pythonisch und total unter ihren Vorbedingungen;
    # der Leser der Antwort ist es nicht (er liest eine Datei) und steht darum nicht hier.
    "georep.prep.precincts.ring_signed_area",
    "georep.prep.precincts.point_in_ring",
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
    # Punkt 58: die zweite Quelle des Gremiums. Beide Funktionen sind rein und total über
    # Sequenz und Mapping -- anders als ``parse_reference`` kennen sie kein ``re.Pattern``.
    "georep.prep.bodies.organization_key",
    "georep.prep.bodies.resolve_organizations",
    "georep.prep.context.ordinal_score",  # Option 03
    "georep.analysis.parties.classify_document",  # Option 04
    "georep.crosswalk.largest_remainder",  # Option 02
    "georep.prep.precincts.district_from_id",  # Option 01
    "georep.prep.pois.is_city_facility",  # Regel 1, decisions.md Punkt 44
    # --- Punkt 53 (2026-10-13): neun Kandidaten aus den Modulen des Ausbaus, je einzeln mit
    # ``uv run crosshair check <ziel> --analysis_kind deal --per_condition_timeout 20`` geprüft.
    # **Vier** fanden ein Gegenbeispiel, und alle vier waren echt -- eine Annahme über die
    # Eingabe, die nur in der Nachbedingung stand: ``report.terms.terms_payload`` (ein Begriff
    # ohne Treffer, und eine Liste in falscher Folge), ``report.geometry.fit`` (eine unendliche
    # Grenze), ``report.model.body_figures`` (eine fremde Gremienklasse als ``KeyError``, eine
    # negative Dokumentzahl) und ``report.charts.bars`` (``width=nan``). Alle vier haben jetzt
    # eine Vorbedingung; ``bars`` bleibt trotzdem draußen, siehe unten.
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


# Die Mutationssitzung läuft **je Modul eine eigene Sitzung** mit genau den Testdateien, die das
# Modul benutzen: nur so bleibt sie in Minuten statt in Stunden. Der Grund steht in
# docs/mutation-2026-10-13.md -- die abdeckungsgeführte Testauswahl von pytest-gremlins liefert
# hier keine Daten, und ohne sie lässt gremlins je Mutant **alle** übergebenen Tests laufen. Mit
# ``tests/unit tests/property tests/golden`` als Auswahl ist das die ganze schnelle Suite je
# Mutant; der Review vom 2026-10-13 hat gemessen, dass dann nach 240 s noch kein einziger Mutant
# durch war.
#
# Schlüssel -> (Ziele, Testdateien). Die Zeiten der dreizehn Module von 2026-10-13 stehen in
# docs/mutation-2026-10-13.md, § Zahlen. Nicht dabei, mit Grund:
#
#   src/georep/analysis/topics.py   jeder Mutant rechnet NMF; der Lauf vom 2026-10-12 war nach
#                                   35 Minuten nicht durch, gezielt je Modul vier Minuten
#                                   (docs/mutation-2026-10-12.md).
#   src/georep/report/model.py      noch nicht gemessen: zusammen rund 3 500 Zeilen, und das
#   src/georep/report/charts.py     Modell entsteht in jedem Test der Seite neu. Ein eigener Lauf,
#   src/georep/report/build.py      wenn jemand ihn misst; darum hier nichts behauptet.
MUTATION_SCOPE: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # --- 2026-10-13: die dreizehn Module, die seit v0.11.0 dazukamen oder sich stark änderten
    "terms": (
        ("src/georep/report/terms.py",),
        ("tests/unit/test_report_terms.py",),
    ),
    "scaling": (
        ("src/georep/analysis/scaling.py",),
        (
            "tests/unit/test_scaling.py",
            "tests/unit/test_report_metrics.py",
            "tests/property/test_scaling_props.py",
        ),
    ),
    "timeline": (
        ("src/georep/analysis/timeline.py",),
        ("tests/unit/test_timeline.py", "tests/property/test_timeline_props.py"),
    ),
    "periods": (
        ("src/georep/analysis/periods.py",),
        (
            "tests/unit/test_periods.py",
            "tests/property/test_periods_props.py",
            "tests/golden/test_period_pipeline.py",
        ),
    ),
    "precincts": (
        ("src/georep/prep/precincts.py",),
        ("tests/unit/test_precincts.py", "tests/property/test_precincts_props.py"),
    ),
    "pois": (
        ("src/georep/prep/pois.py",),
        (
            "tests/unit/test_city_facilities.py",
            "tests/unit/test_contract_violations.py",
            "tests/property/test_city_facility_props.py",
            "tests/property/test_prep_props.py",
            "tests/golden/test_polars_parity.py",
        ),
    ),
    "committees": (
        ("src/georep/analysis/committees.py",),
        ("tests/unit/test_committees.py", "tests/unit/test_contract_violations.py"),
    ),
    "search": (
        ("src/georep/report/search.py",),
        (
            "tests/unit/test_report_search.py",
            "tests/unit/test_report_js_fold.py",
            "tests/unit/test_report_render.py",
            "tests/property/test_search_props.py",
        ),
    ),
    "ols": (
        ("src/georep/analysis/ols.py",),
        (
            "tests/unit/test_ols.py",
            "tests/property/test_ols_props.py",
            "tests/golden/test_regression_numbers.py",
        ),
    ),
    "crosswalk": (
        ("src/georep/crosswalk.py",),
        (
            "tests/unit/test_crosswalk.py",
            "tests/unit/test_crosswalk_areas.py",
            "tests/unit/test_voters_period.py",
            "tests/unit/test_voters_units.py",
            "tests/unit/test_prep_context.py",
            "tests/property/test_crosswalk_props.py",
            "tests/golden/test_crosswalk_geometry.py",
            "tests/golden/test_crosswalk_methods.py",
        ),
    ),
    "comparison": (
        ("src/georep/report/comparison.py",),
        (
            "tests/unit/test_report_comparison.py",
            "tests/unit/test_report_build.py",
            "tests/golden/test_publish.py",
        ),
    ),
    "publish": (
        ("src/georep/report/publish.py",),
        ("tests/unit/test_report_build.py", "tests/golden/test_publish.py"),
    ),
    "parties": (
        ("src/georep/analysis/parties.py",),
        (
            "tests/unit/test_parties.py",
            "tests/unit/test_report_parties_scaling.py",
            "tests/unit/test_contract_violations.py",
            "tests/property/test_parties_props.py",
            "tests/golden/test_parties_numbers.py",
        ),
    ),
    # --- 2026-10-11 und -12: die vier älteren Ziele. Ihre Testdateien stehen hier zum ersten Mal
    # als Zuschnitt; die Zeiten sind **nicht** gemessen (die alten Läufe gingen über die ganze
    # Suite mit sechs Arbeitern, docs/mutation-2026-10-11.md).
    "dictionary": (
        ("src/georep/search",),
        (
            "tests/unit/test_citywide_terms.py",
            "tests/unit/test_guards.py",
            "tests/property/test_dictionary_props.py",
            "tests/property/test_matcher_contract.py",
            "tests/property/test_citywide_props.py",
        ),
    ),
    "hits": (
        ("src/georep/analysis/hits.py",),
        (
            "tests/unit/test_citywide_terms.py",
            "tests/unit/test_contract_violations.py",
            "tests/property/test_hits_props.py",
            "tests/property/test_citywide_props.py",
        ),
    ),
    "regression": (
        ("src/georep/analysis/regression.py",),
        (
            "tests/unit/test_regression.py",
            "tests/unit/test_report_charts.py",
            "tests/unit/test_contract_violations.py",
            "tests/golden/test_regression_numbers.py",
        ),
    ),
    "weights": (
        ("src/georep/analysis/weights.py",),
        (
            "tests/unit/test_weights.py",
            "tests/unit/test_contract_violations.py",
            "tests/property/test_weights_props.py",
        ),
    ),
}
# Die acht Module, die am 2026-10-13 unter 90 s brauchten; der wöchentliche Qualitätslauf nimmt
# genau diese (.github/workflows/quality.yml).
FAST_SCOPE = (
    "terms",
    "scaling",
    "timeline",
    "periods",
    "precincts",
    "pois",
    "committees",
    "search",
)


@nox.session
def mutate(session: nox.Session) -> None:
    """Mutationstest mit pytest-gremlins, **eine Sitzung je Modul**, kein Gate.

    ``nox -s mutate`` nimmt alle Schlüssel aus ``MUTATION_SCOPE``; Posargs ohne Bindestrich wählen
    einzelne Schlüssel aus (``nox -s mutate -- scaling ols``), Posargs mit Bindestrich gehen an
    pytest weiter (``-- fast --gremlin-workers=2``). ``fast`` ist die Abkürzung für die acht
    Module unter 90 s.

    Subprocess-Executor, kein fork (mutmut 3 blockierte so mit Polars, docs/mutation-2026-10-11.md).
    **Drei Arbeiter, nicht sechs**: mit sechs wurde die Sitzung am 2026-10-12 unter der Last von
    acht parallelen Agenten abgeschossen, und der Rechner hat dreizehn Kerne, von denen Polars und
    BLAS schon welche nehmen.

    Warum je Modul und nicht alles auf einmal: die abdeckungsgeführte Testauswahl von gremlins
    liefert hier keine Daten (docs/mutation-2026-10-13.md), und ohne sie lässt gremlins **jeden**
    Mutanten gegen **alle** übergebenen Tests laufen. Die Zahlen und die Deutung der Überlebenden
    stehen datiert in docs/mutation-2026-10-1{1,2,3}.md.
    """
    keys = [a for a in session.posargs if not a.startswith("-")]
    flags = [a for a in session.posargs if a.startswith("-")]
    if keys == ["fast"]:
        keys = list(FAST_SCOPE)
    unknown = [k for k in keys if k not in MUTATION_SCOPE]
    if unknown:
        session.error(f"Unbekannte Module: {unknown}; bekannt: {sorted(MUTATION_SCOPE)}")
    for key in keys or list(MUTATION_SCOPE):
        targets, tests = MUTATION_SCOPE[key]
        session.log(f"--- {key}: {', '.join(targets)}")
        session.run(
            "uv",
            "run",
            "pytest",
            *tests,
            "-m",
            "not slow and not network and not bench",
            "-p",
            "no:cacheprovider",
            "--gremlins",
            f"--gremlin-targets={','.join(targets)}",
            "--gremlin-report=console,json",
            "--gremlin-workers=3",
            "--gremlin-mutant-timeout=60",
            *flags,
        )


@nox.session
def alone(session: nox.Session) -> None:
    """Reihenfolgeunabhängigkeit: jede Testdatei einmal allein, dann die Suite rückwärts.

    Zwei Prüfungen, kein Gate für einen Push, aber **rot bei einem Befund** (Punkt 53):

    1. **Jede Datei allein.** Ein Test, der nur grün ist, weil ein anderer vorher eine Datei
       geschrieben hat, fällt sonst nie auf -- genau das war
       ``test_a_city_that_lost_its_run_leaves_the_published_folder`` am 2026-10-12. Drei Dateien
       parallel. Exit 5 („keine Tests gesammelt") ist **kein** Fehler: in dieser Datei trägt jeder
       Test ``slow`` oder ``network``. Jeder andere Exit-Code wird gesammelt und am Ende zu
       ``session.error`` -- ein ``|| echo`` an dieser Stelle frisst den Exit-Code (CLAUDE.md).
    2. **Die ganze schnelle Suite rückwärts.** ``-p no:randomly`` gibt es hier nicht; die
       Reihenfolge kommt aus ``--co`` und wird umgedreht. Beides läuft ohne Shell, damit keine
       Pipe einen Exit-Code verschluckt und kein parametrierter Testname mit Leerzeichen
       (``-auf'm``) in Wörter zerfällt.

    Gemessen am 2026-10-13: 97 Dateien, 94 grün und 3 ohne schnelle Tests; rückwärts 1065 Tests
    in 228 s.
    Keine Abhängigkeit gefunden.
    """
    marker = "not slow and not network and not bench"
    files = sorted(
        str(path)
        for folder in ("tests/unit", "tests/golden", "tests/property")
        for path in Path(folder).glob("test_*.py")
    )
    base = ["uv", "run", "pytest", "-m", marker, "-p", "no:cacheprovider", "--no-cov"]
    session.log(f"{len(files)} Testdateien je allein, drei parallel")

    def one(path: str) -> tuple[str, int]:
        done = subprocess.run([*base, path], capture_output=True, text=True, check=False)
        return path, done.returncode

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(one, files))
    # Exit 5 heißt "nichts gesammelt" und ist hier erlaubt; alles andere ist ein Befund.
    empty = [path for path, code in results if code == 5]
    broken = [(path, code) for path, code in results if code not in (0, 5)]
    session.log(
        f"{len(results) - len(empty) - len(broken)} grün, {len(empty)} ohne schnelle Tests "
        f"({', '.join(Path(p).name for p in empty) or '-'}), {len(broken)} rot"
    )
    if broken:
        session.error(f"Dateien, die allein nicht grün sind: {broken}")

    session.log("und einmal rückwärts")
    # Kein zusaetzliches ``-q``: ``addopts`` traegt schon eines, und ``-qq`` druckt statt der
    # Test-IDs nur eine Zeile je Datei (2026-10-13 genau darauf gelaufen).
    collected = subprocess.run([*base[:-1], "--co"], capture_output=True, text=True, check=False)
    if collected.returncode != 0:
        session.error(f"Sammeln misslang (Exit {collected.returncode}): {collected.stderr[-500:]}")
    nodes = [line for line in collected.stdout.splitlines() if "::" in line]
    if not nodes:
        session.error("Sammeln lieferte keine Test-IDs")
    session.log(f"{len(nodes)} Tests rückwärts")
    session.run(*base[:-1], "--no-cov", *reversed(nodes))


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
