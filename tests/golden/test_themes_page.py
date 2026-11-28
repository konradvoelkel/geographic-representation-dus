"""Die Zahlen von ``themen.html`` aus den Paketen im Repo (Vorhaben 19, Stufe 3).

Die Tabellen entstehen wie in ``georep run`` (``bootstrap`` aus den Paketen, die Schritte bis
``policy_areas``). Die Hauptperiode trägt die Felder, an denen geprüft ist (Messdokument § 4.2):
19 032 der 19 108 Dokumente mit Feld, Verkehr vorn, alle Fraktionen nach derselben Regel, 41
Wahlbezirke. Die zweite Stadt ist der Prüfstein: jede Überschrift „explorativ“. Beide Seiten
bleiben unter dem Budget von 500 KB.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import pytest

from georep.bootstrap import bootstrap_from_settings
from georep.enrich.policy_areas import PAGE
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.report.pages import page_frame, render_page
from georep.report.themes import ThemesModel, themes_data, themes_links
from georep.settings import Settings, load_settings

pytestmark = pytest.mark.slow

NOWHERE = Path("/nonexistent")
PAGE_BUDGET = 500_000
STEPS = {
    "duesseldorf": [
        "shapes",
        "voters",
        "streets",
        "pois",
        "dictionary",
        "corpus",
        "bodies",
        "index",
        "results",
        "parties",
        "cosponsors",
        "policy_areas",
    ],
    "moenchengladbach": [],  # die ganze Kette, wie test_second_city.py
}


@dataclass(frozen=True)
class Dataset:
    settings: Settings
    layout: Layout


def _dataset(profile: str, root: Path) -> Dataset:
    settings = load_settings(profile=profile, cwd=NOWHERE).model_copy(
        update={"data_root": root / "data", "cache_root": root / "cache"}
    )
    layout = Layout.from_settings(settings)
    bootstrap_from_settings(layout, settings)
    outcomes = run_pipeline(build_steps(settings, layout), settings, STEPS[profile] or None)
    assert all(o.status != "fehlgeschlagen" for o in outcomes), [o.line() for o in outcomes]
    return Dataset(settings, layout)


@pytest.fixture(scope="module")
def datasets(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Dataset]:
    root = tmp_path_factory.mktemp("themes_page")
    return {p: _dataset(p, root) for p in STEPS}


def _model(dataset: Dataset) -> ThemesModel:
    model = themes_data(dataset.layout, dataset.settings)["themen"]
    assert isinstance(model, ThemesModel)
    return model


def _page(dataset: Dataset) -> str:
    return render_page(
        page_frame(dataset.settings, now=dt.datetime(2026, 11, 28, tzinfo=dt.UTC), commit=None),
        PAGE,
        themes_data(dataset.layout, dataset.settings),
        themes_links(dataset.layout, dataset.settings),
    )


def test_the_main_period_shows_the_measured_fields(datasets: dict[str, Dataset]) -> None:
    model = _model(datasets["duesseldorf"])
    assert model.check.status == "gemessen"
    assert (model.documents, model.with_area, model.undetermined) == (19_108, 19_032, 76)
    assert model.areas[0].code == "10" and model.areas[0].total == 4_990
    assert sum(a.total for a in model.areas) == model.with_area
    assert len(model.districts) == 41
    assert model.fractions is not None and len(model.fractions) >= 5
    shown = [r for r in model.fractions if r.shares is not None]
    assert shown and all(r.documents >= 30 for r in shown)
    assert all(r.shares is None for r in model.fractions if r.documents < 30)
    page = _page(datasets["duesseldorf"])
    assert "(explorativ)" not in page
    assert len(page.encode("utf-8")) < PAGE_BUDGET


def test_the_second_city_is_explorative(datasets: dict[str, Dataset]) -> None:
    model = _model(datasets["moenchengladbach"])
    assert model.check.status == "explorativ"
    assert (model.documents, model.with_area) == (2_895, 650)
    page = _page(datasets["moenchengladbach"])
    assert page.count("(explorativ)</h2>") == 3  # Periode, Fraktion, Wahlbezirk
    assert "Explorativ:" in page and "Düsseldorf, Wahlperiode 2020 bis 2025" in page
    assert len(page.encode("utf-8")) < PAGE_BUDGET
