"""Die Zahlen von ``bedarf.html`` aus den Paketen im Repo (Vorhaben 22, Stufe 3).

Die Tabellen entstehen wie in ``georep run`` (``bootstrap`` aus den Paketen, die Schritte bis
``need``, wie in ``test_need_numbers.py``). Die Hauptperiode trägt, was die Seite über die Klasse
sagt: 958 der Dokumente der Klasse mit Treffer ohne Ausschussberatung (``guete.json``, Messdokument
§ 4.1) von rund 1 425 (die Klassen gelten je Rechner, Punkt 80), die Prüfung als Fall 3, drei
Tests, drei Karten. Die zweite Stadt ist der Prüfstein: Bedarf ohne Klassen und ohne Tests, zwei
Karten, drei Sätze, was fehlt. Beide Seiten bleiben unter dem Budget von 500 KB.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import pytest

from georep.bootstrap import bootstrap_from_settings
from georep.enrich.need import PAGE
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.report.need import NeedModel, need_data, need_links
from georep.report.pages import page_frame, render_page
from georep.settings import Settings, load_settings

pytestmark = pytest.mark.slow

NOWHERE = Path("/nonexistent")
PAGE_BUDGET = 500_000
CLASSIFIED = 20  # Dokumente der Klasse mit Treffer: je Rechner (Punkt 80, 18 Dokumente wechseln)
STEPS = {
    "duesseldorf": [
        "shapes",
        "voters",
        "context",
        "streets",
        "pois",
        "dictionary",
        "corpus",
        "bodies",
        "committees",
        "index",
        "results",
        "need",
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
    steps = build_steps(settings, layout)
    outcomes = run_pipeline(steps, settings, STEPS[profile] or None)
    assert all(o.status != "fehlgeschlagen" for o in outcomes), [o.line() for o in outcomes]
    return Dataset(settings, layout)


@pytest.fixture(scope="module")
def datasets(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Dataset]:
    root = tmp_path_factory.mktemp("need_page")
    return {p: _dataset(p, root) for p in STEPS}


def _model(dataset: Dataset) -> NeedModel:
    model = need_data(dataset.layout, dataset.settings)["bedarf"]
    assert isinstance(model, NeedModel)
    return model


def _page(dataset: Dataset) -> str:
    return render_page(
        page_frame(dataset.settings, now=dt.datetime(2026, 11, 27, tzinfo=dt.UTC), commit=None),
        PAGE,
        need_data(dataset.layout, dataset.settings),
        need_links(dataset.layout, dataset.settings),
    )


def test_the_main_period_names_the_check_of_the_class(datasets: dict[str, Dataset]) -> None:
    model = _model(datasets["duesseldorf"])
    assert model.classes is not None and model.check is not None
    assert model.check.population == 958
    assert model.classes.with_hit == pytest.approx(1_425, abs=CLASSIFIED)
    assert model.check.case == 3
    assert [t.name for t in model.tests] == ["H1", "H2", "H3"]
    assert [t.result for t in model.tests] == ["bestätigt", "nicht bestätigt", "nicht bestätigt"]
    assert [p.key for p in model.maps] == ["unfaelle", "handlungsbedarf", "unter18"]
    assert model.accidents.total == 11_501 and round(model.accidents.shared) == 3_170
    assert model.accidents.sharp_rank == pytest.approx(0.980, abs=5e-4)
    assert model.school_need is not None and model.school_need[0] == pytest.approx(0.772, abs=5e-4)
    assert model.power is not None and [round(v, 2) for v in model.power] == [0.39, 0.46]
    assert model.missing == ()
    assert len(_page(datasets["duesseldorf"]).encode("utf-8")) < PAGE_BUDGET


def test_the_second_city_shows_need_without_classes(datasets: dict[str, Dataset]) -> None:
    """Frage 22.6: Unfälle, Einwohner, Miete und Schulsozialindex, aber keine Anteile der Klassen
    und keine Tests; die Seite sagt es."""
    model = _model(datasets["moenchengladbach"])
    assert model.classes is None and model.check is None and model.tests == ()
    assert [p.key for p in model.maps] == ["unfaelle", "schulsozialindex"]
    assert len(model.missing) == 3
    assert len(model.districts) == 33
    page = _page(datasets["moenchengladbach"])
    assert len(page.encode("utf-8")) < PAGE_BUDGET
    assert "In diesem Profil fehlt" in page and 'class="test"' not in page
