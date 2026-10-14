"""Die Seite, die wirklich veröffentlicht wird: Hauptperiode mit beiden Periodenabschnitten.

Review-Befund 3 (2026-10-14): ``index.html`` der veröffentlichten Seite wog 932 274 von 1 000 000
Byte, und **kein Test** rechnete sie. Das Budget stand in vier Tests, aber keiner baute die Seite,
die GitHub Pages hochlädt: ``tests/golden/test_pipeline.py`` rechnet die Hauptperiode ohne
Vergleich, ``test_period_pipeline.py`` den Vergleich auf der Mini-Fixture (Seite rund 100 KB), und
genau die Kombination aus voller Referenz, ``duesseldorf-vergleich`` und dem Link auf die laufende
Periode fiel durch jedes Netz.

Dieser Test baut sie: ``reference/`` als Hauptperiode, ``snapshots/2014-2020/`` als zweite Periode,
das Profil ``duesseldorf-vergleich``. Von der alten Periode laufen nur die Schritte, die der
Vergleich braucht (``COMPARE_NEEDS``) -- ihr Themenmodell und ihr Klassifikator kosten zusammen
17 s und stehen auf keiner Seite, die hier gemessen wird. Die Hauptperiode rechnet **einmal**, mit
den Settings des Vergleichsprofils: ein Lauf mit dem Standardprofil davor wäre wegen des
Fingerprints für nichts (``[compare]`` zählt mit).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import pytest

from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.pipeline import Outcome, build_steps, run_pipeline
from georep.report.publish import publish_sites
from georep.settings import Settings, load_settings
from tests.conftest import REFERENCE, REPO, within_budget

SNAPSHOT = REPO / "snapshots" / "2014-2020"
PERIOD_PROFILE = "duesseldorf-2014"
COMPARE_PROFILE = "duesseldorf-vergleich"
NOWHERE = Path("/nonexistent")
# Was der Schritt ``compare`` von der alten Periode liest: ihre Auswertung und ihr Wörterbuch
# (``test_period_pipeline.py::test_the_comparison_needs_the_same_dictionary`` hält das fest).
COMPARE_NEEDS = [
    "precincts",
    "voters",
    "streets",
    "pois",
    "dictionary",
    "corpus",
    "index",
    "results",
]


@dataclass(frozen=True)
class PublishedRun:
    settings: Settings
    layout: Layout
    period: Layout


@pytest.fixture(scope="module")
def published(tmp_path_factory: pytest.TempPathFactory) -> PublishedRun:
    root = tmp_path_factory.mktemp("veroeffentlicht")
    compare = load_settings(profile=COMPARE_PROFILE, cwd=NOWHERE).model_copy(
        update={"data_root": root / "data", "cache_root": root / "cache"}
    )
    base = Layout.from_settings(compare)
    assert bootstrap(base, context_files=compare.context.files.names()).missing == []

    period_settings = load_settings(profile=PERIOD_PROFILE, cwd=NOWHERE).model_copy(
        update={
            "data_root": root / "data",
            "cache_root": root / "cache",
            "reference_root": SNAPSHOT,
        }
    )
    period = Layout.from_settings(period_settings)
    assert bootstrap(period, needs_dictionary=False).missing == []

    # Reihenfolge: erst die Hauptperiode ohne ``compare`` und ``report`` (die alte Periode liest
    # ihre Stadtbezirke, Option 05), dann die alte Periode, dann der Vergleich und die Seite. Ein
    # früherer Lauf mit ``compare`` bräche mit MissingInputError ab, und das wäre richtig so.
    steps = build_steps(compare, base)
    network = {s.name for s in steps if s.network}
    LAST = ("compare", "report")
    before = [s.name for s in steps if s.name not in LAST]
    _check(run_pipeline(steps, compare, before), network)
    _check(
        run_pipeline(build_steps(period_settings, period), period_settings, COMPARE_NEEDS),
        network,
    )
    done = run_pipeline(build_steps(compare, base), compare)
    _check(done, network)
    assert {o.step for o in done if o.status == "ausgeführt"} == set(LAST), [o.line() for o in done]
    return PublishedRun(compare, base, period)


def _check(outcomes: list[Outcome], network: set[str]) -> None:
    """Jeder Offline-Schritt ist gelaufen oder übersprungen; ein anderer Status ist ein Fehler."""
    broken = [
        o.line()
        for o in outcomes
        if o.step not in network and o.status not in ("ausgeführt", "übersprungen")
    ]
    assert not broken, broken


def test_the_published_main_page_stays_within_the_budget(published: PublishedRun) -> None:
    """Die eine Seite, die GitHub Pages hochlädt, gegen ``report.page_budget_bytes``.

    Gemessen am 2026-10-14: 932 274 von 1 000 000 Byte. Reißt das Budget, ist das eine
    Entscheidung (einen Abschnitt kürzen oder die Zahl heben), kein Testdetail.
    """
    budget = published.settings.report.page_budget_bytes
    size = published.layout.site_index.stat().st_size
    assert within_budget(size, budget), f"{size} von {budget} Byte"
    page = published.layout.site_index.read_text(encoding="utf-8")
    # Genau die Kombination, die vorher kein Test baute: beide Periodenabschnitte auf einer Seite
    assert '<section id="perioden">' in page and '<section id="laufend">' in page
    assert 'href="2014-2020/"' in page and 'href="2025/"' in page
    assert published.layout.reference_root.resolve() == REFERENCE  # die volle Referenz der Arbeit


def test_publish_reports_no_page_over_budget(published: PublishedRun, tmp_path: Path) -> None:
    """``PublishSummary.over_budget`` ist die Prüfung, die ``--strict-budget`` in CI rot macht."""
    summary = publish_sites(
        published.settings,
        published.layout,
        now=dt.datetime(2026, 10, 14, tzinfo=dt.UTC),
        out=tmp_path / "site",
    )
    assert summary.over_budget == ()
    assert summary.cities == ("duesseldorf",) and summary.missing == ("moenchengladbach",)
    # Mit einem winzigen Budget nennt dieselbe Rechnung jede Seite; so greift der Schalter in CI
    tight = published.settings.model_copy(
        update={"report": published.settings.report.model_copy(update={"page_budget_bytes": 1})}
    )
    strict = publish_sites(
        tight,
        published.layout,
        now=dt.datetime(2026, 10, 14, tzinfo=dt.UTC),
        out=tmp_path / "site",
    )
    assert "index.html" in strict.over_budget and "über dem Budget" in strict.line()


pytestmark = pytest.mark.slow
