from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator
from pathlib import Path

import deal
import pytest
from hypothesis import HealthCheck
from hypothesis import settings as hypothesis_settings

from georep.bootstrap import bootstrap_from_settings
from georep.geo import read_canonical_precincts
from georep.io import write_json
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.precincts import canonical_precincts, read_source
from georep.report.charts import choropleth, classify, legend, rate_label, scatter, turnout_label
from georep.report.geometry import SIMPLIFY_M, bounds_of, district_shapes, fit
from georep.report.model import ReportModel, build_report_model
from georep.report.render import Visuals
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
MG = REPO / "tests" / "fixtures" / "mg"  # Option 01: die Netzstichprobe der zweiten Stadt
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
def context_root() -> Path:
    """Die Fremddaten des Repos (Option 03); die Mini-Fixture hat ihre eigenen unter ``mini/context``."""
    return REPO / "context"


@pytest.fixture(scope="session")
def pdf_fixtures() -> Path:
    return PDF_FIXTURES


def canonical_precincts_file(source: Path, target_dir: Path, settings: Settings) -> Path:
    """Die kanonischen Stimmbezirke aus einer Quelldatei, wie der Schritt ``shapes`` sie schreibt.

    Tests, die Flächen lesen, aber keine Kette laufen lassen, holen sie hier (Option 01: alles
    hinter dem Schritt kennt nur die kanonische Datei). Die Koordinaten bleiben die der Quelle.
    """
    data = canonical_precincts(read_source(source, settings.precincts), settings.precincts)
    target = target_dir / "stimmbezirke.geojson"
    write_json(target, data, indent=None)
    return target


@pytest.fixture(scope="session")
def reference_precincts(
    tmp_path_factory: pytest.TempPathFactory, default_settings: Settings
) -> Path:
    """Die 306 Stimmbezirke der Referenz, kanonisch, einmal je Sitzung."""
    return canonical_precincts_file(
        REFERENCE / "external" / "Stimmbezirke_2025.geojson",
        tmp_path_factory.mktemp("reference_precincts"),
        default_settings,
    )


@pytest.fixture(scope="session")
def mini_precincts(tmp_path_factory: pytest.TempPathFactory, default_settings: Settings) -> Path:
    """Die 22 Stimmbezirke der Mini-Fixture, kanonisch, einmal je Sitzung."""
    return canonical_precincts_file(
        MINI / "external" / "Stimmbezirke_2025.geojson",
        tmp_path_factory.mktemp("mini_precincts"),
        default_settings,
    )


@pytest.fixture(scope="session")
def default_settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def as_in_the_thesis(settings: Settings) -> Settings:
    """Dieselben Settings mit abgeschalteten eigenen Regeln: so rechnet die Kette wie die Arbeit.

    Golden-Master-Tests gegen ``reference/`` und ``tests/fixtures/mini/expected/`` nehmen diese
    Settings; die Regeln, die von der Arbeit abweichen, stehen je als Schalter in
    ``defaults.toml`` und sind hier aufgezählt (docs/decisions.md, Punkte 43 und 44). Alles
    andere im Testlauf rechnet mit den Vorgaben, also mit den Regeln an.
    """
    return settings.model_copy(
        update={"search": settings.search.model_copy(update={"city_facilities": False})}
    )


def within_budget(size: int, budget: int) -> bool:
    """Punkt 50: ``report.page_budget_bytes`` von 0 heißt „keine Prüfung" -- auch im Test.

    Die vier Zusicherungen über die Größe von ``index.html`` lesen die Zahl aus den Settings und
    wurden mit 0 rot, obwohl 0 sie abschalten soll (Review 2026-10-13). Sie gehen darum über
    diesen Helfer, so wie ``SiteSummary.over_budget`` es im Programm tut.
    """
    return not budget or size < budget


LITERATURE_SECTION = '<section id="literatur">'


def without_literature(page: str) -> str:
    """Die Seite ohne den Abschnitt „Literatur und verwandte Arbeiten" (Punkt 47).

    Ein Test, der ein Wort oder eine Jahreszahl im **ganzen** HTML sucht, muss diesen Abschnitt
    auslassen: er zitiert fremde Veröffentlichungen und nennt darum Jahre und Monate, die nichts
    mit der Periode oder den Daten dieser Seite zu tun haben (zwei Tests wurden daran am
    2026-10-13 rot). Dieselbe Lehre wie bei der Profiltabelle und bei ``data-value``: ein Test
    prüft die Stelle, die er meint, nicht das ganze Dokument.
    """
    start = page.find(LITERATURE_SECTION)
    if start < 0:
        return page
    end = page.index("</section>", start) + len("</section>")
    return page[:start] + page[end:]


def mg_settings() -> Settings:
    """Das Profil der zweiten Stadt, auf die Größe der Netzstichprobe gebracht (Option 01).

    Die Probe hat acht Ratsdokumente. Das Themenmodell (Option 06) braucht mindestens so viele
    Texte wie Themen und zählt ein Wort erst ab ``min_df`` Dokumenten; das ist eine Grenze der
    Probe, nicht des Profils, und steht darum hier und nicht in ``profiles/``.
    """
    base = load_settings(profile="moenchengladbach", cwd=Path("/nonexistent"))
    return base.model_copy(update={"topics": base.topics.model_copy(update={"k": 3, "min_df": 1})})


@pytest.fixture(scope="session")
def mini_run(tmp_path_factory: pytest.TempPathFactory, default_settings: Settings) -> Layout:
    """Die Offline-Kette einmal je Sitzung auf der Mini-Fixture: Tests lesen daraus, schreiben nie hinein.

    Das Profil kommt aus den Settings, also liegt der Lauf unter dem Slug der Stadt (Punkt 52) —
    wie auf einem echten Rechner. Tests nehmen ihre Pfade darum aus diesem ``Layout`` und nie aus
    ``tmp_path / "data" / …``.
    """
    root = tmp_path_factory.mktemp("mini_run")
    layout = Layout(
        root / "data",
        root / "cache",
        MINI,
        default_settings.profile,
        context_root=MINI / "context",
    )
    # Punkt 58, Review 2026-10-14: dieselbe Verdrahtung wie `georep bootstrap`; die
    # Beratungsfolge der 200 Dokumente bringt die Fixture selbst mit, und sie gilt vor dem
    # Paket, das das Profil nennt (``bootstrap_from_settings``).
    bootstrap_from_settings(layout, default_settings)
    run_pipeline(build_steps(default_settings, layout), default_settings)
    return layout


@pytest.fixture(scope="session")
def mini_model(mini_run: Layout, default_settings: Settings) -> ReportModel:
    """Das Modell der Mini-Fixture mit fester Zeit; Option 01 prüft Kopf, Fuß und Methode daran."""
    return build_report_model(
        mini_run,
        default_settings,
        now=dt.datetime(2026, 10, 12, 9, 0, tzinfo=dt.UTC),
        commit="abc1234",
    )


@pytest.fixture(scope="session")
def mini_visuals(mini_model: ReportModel, mini_run: Layout, default_settings: Settings) -> Visuals:
    precincts = read_canonical_precincts(
        mini_run.precincts_geojson, default_settings.geo.working_crs
    )
    shapes = district_shapes(precincts)
    projection = fit(bounds_of(shapes), 600.0)
    rate = classify({d.id: d.rate for d in mini_model.districts})
    turnout = classify({d.id: d.turnout for d in mini_model.districts})
    assert mini_model.regression is not None  # Option 07: im Modell optional
    return Visuals(
        map_svg=choropleth(mini_model.districts, shapes, projection, rate, turnout),
        scatter_svg=scatter(mini_model.districts, mini_model.regression),
        rate_legend=legend(rate, rate_label),
        turnout_legend=legend(turnout, turnout_label),
        simplify_m=SIMPLIFY_M,
        pois=0,
    )


@pytest.fixture(scope="session")
def mini_page(mini_run: Layout) -> str:
    """Die gebaute Seite der Mini-Fixture, wie der Schritt ``report`` sie geschrieben hat."""
    return mini_run.site_index.read_text(encoding="utf-8")
