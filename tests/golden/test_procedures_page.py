"""Die Zahlen von ``vorgaenge.html`` aus den Paketen im Repo (Vorhaben 14, Stufe 3).

Die Korpora entstehen wie in ``georep run``: ``bootstrap`` aus den Datenpaketen, die Schritte
``corpus`` und ``bodies``, die Urheber aus Option 04, dann ``cosponsors`` (Vorhaben 15),
``references`` und ``procedures``. Die Hauptperiode trägt die Zahlen, die auf der Seite stehen
(Antworten, Antwortzeiten, Kandidaten, Vorgänge, beobachtet gegen erwartet je Fraktion; Stand
``v0.35.0``, 2026-11-27), die zweite Stadt ist der Prüfstein: keine Anfragen, also nur Vorgänge,
und jede Überschrift explorativ. Beide Seiten bleiben unter dem Budget von 500 KB.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest

from georep.analysis.parties import classify_originators
from georep.bootstrap import bootstrap_from_settings
from georep.enrich.procedures import PAGE
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.report.pages import page_frame, render_page
from georep.report.procedures import (
    ProceduresModel,
    dialog_rows,
    procedures_data,
    procedures_links,
)
from georep.settings import Settings, load_settings

pytestmark = pytest.mark.slow

NOWHERE = Path("/nonexistent")
PAGE_BUDGET = 500_000


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
    first = run_pipeline(steps, settings, ["corpus", "bodies"])
    assert all(o.status == "ausgeführt" for o in first), [o.line() for o in first]
    # Die Urheber wie im Schritt ``parties``, ohne dessen Wahlergebnisse: die Seite liest nur
    # ``urheber_art``, ``cosponsors`` die Parteien.
    corpus = pl.read_parquet(layout.corpus)
    originators = classify_originators(corpus, settings.originators)
    write_parquet(originators, layout.document_originators, schema_version=1)
    rest = run_pipeline(steps, settings, ["cosponsors", "references", "procedures"])
    assert all(o.status == "ausgeführt" for o in rest), [o.line() for o in rest]
    return Dataset(settings, layout)


@pytest.fixture(scope="module")
def datasets(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Dataset]:
    root = tmp_path_factory.mktemp("procedures_page")
    return {p: _dataset(p, root) for p in ("duesseldorf", "moenchengladbach")}


def _model(dataset: Dataset) -> ProceduresModel:
    model = procedures_data(dataset.layout, dataset.settings)["vorgaenge"]
    assert isinstance(model, ProceduresModel)
    return model


def test_the_answers_of_the_main_period(datasets: dict[str, Dataset]) -> None:
    model = _model(datasets["duesseldorf"])
    a = model.answers
    assert a is not None and model.check.measured and not model.explorative
    assert (a.questions, a.answered, a.by_attachment, a.by_paper_only) == (3_952, 1_239, 1_223, 16)
    t = a.times
    assert (t.dated, t.median, t.q1, t.q3, t.p90) == (1_238, 18.0, 13.0, 71.0, 139.0)
    assert (len(a.bodies), len(a.session_bodies), a.names) == (27, 15, 712)
    council = next(b for b in a.bodies if b.code == "RAT")
    assert (council.questions, council.answered, council.in_session) == (633, 0, True)
    assert len(model.candidates) == 110
    assert model.candidates[0].reference == "AGS/072/2020"  # die älteste, wie § 3.8


def test_the_fractions_against_the_practice_of_the_bodies(datasets: dict[str, Dataset]) -> None:
    """Explorativ (Frage 14): beobachtet gegen erwartet; AfD und PARTEI unter zehn erwarteten."""
    rows = {f.key: f for f in _model(datasets["duesseldorf"]).fractions}
    ratios = {k: round(r.ratio, 2) for k, r in rows.items() if r.ratio is not None}
    assert ratios == {
        "SPD+VOLT": 0.95,
        "GRUENE": 1.01,
        "CDU": 1.03,
        "FDP": 1.03,
        "Die_Linke": 1.07,
        "T_FW": 1.11,
    }
    assert rows["AfD"].questions == 129 and rows["AfD"].ratio is None


def test_the_procedures_of_the_main_period(datasets: dict[str, Dataset]) -> None:
    """Nach der Rückfallregel: rund 1 500 Vorgänge der Periode, fast alle Paare (§ 5.1)."""
    v = _model(datasets["duesseldorf"]).procedures
    assert (v.procedures, v.members, v.pairs, v.largest, v.across) == (1_525, 3_100, 1_346, 7, 109)
    assert (v.edges, v.strong, v.weak, v.strong_across) == (7_310, 1_960, 5_350, 167)
    assert dict((t, n) for t, _, n in v.by_type) == {
        "umsetzung": 1_086,
        "aenderung": 356,
        "bezug": 162,
        "nachtrag": 137,
        "kontrolle": 80,
        "nachfrage": 48,
        "fortsetzung": 48,
        "antwort": 43,
    }
    rows = dialog_rows(datasets["duesseldorf"].layout, datasets["duesseldorf"].settings)
    assert (len(rows.rows), sum(len(e) for e in rows.rows.values())) == (3_512, 3_920)


def test_the_second_city_has_procedures_but_no_questions(datasets: dict[str, Dataset]) -> None:
    model = _model(datasets["moenchengladbach"])
    assert model.answers is None and model.explorative and model.missing
    v = model.procedures
    assert (v.procedures, v.members, v.sizes) == (99, 217, ((2, 82), (3, 15), (4, 2)))
    assert (v.edges, v.strong) == (387, 171)


@pytest.mark.parametrize("profile", ["duesseldorf", "moenchengladbach"])
def test_the_page_stays_under_its_budget(datasets: dict[str, Dataset], profile: str) -> None:
    dataset = datasets[profile]
    html = render_page(
        page_frame(dataset.settings, now=dt.datetime(2026, 11, 27, tzinfo=dt.UTC), commit=None),
        PAGE,
        procedures_data(dataset.layout, dataset.settings),
        procedures_links(dataset.layout, dataset.settings),
    )
    assert len(html.encode("utf-8")) < PAGE_BUDGET
