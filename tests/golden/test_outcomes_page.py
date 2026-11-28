"""Die Gäste von Vorhaben 26 auf ``vorgaenge.html`` und der Haken, aus den Paketen im Repo (Stufe 3).

Die Korpora entstehen wie in ``georep run``: ``bootstrap`` aus den Datenpaketen, ``corpus`` und
``bodies``, die Urheber aus Option 04, dann ``cosponsors`` (15), ``references`` und ``procedures``
(14), ``council_results`` und ``outcomes`` (26). Die Hauptperiode trägt die Zahlen der Messung
(Messdokument § 3.3 bis § 3.10, Stand 2026-11-28): 5 099 Anträge, 289 ohne Ergebnis, 155 davon in
einer Sitzung; 2014 bis 2020 die Praxiszellen (240 Anträge); die zweite Stadt nur den Satz, was
fehlt. Die Seite bleibt unter 500 KB, die drei Gäste zusammen unter rund 30 KB, ``beschluesse.json``
unter 300 KB, auch wenn jedes Dokument des Korpus im Dialog stünde.
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
from georep.report.dialog import dialog_payload
from georep.report.outcomes import (
    OutcomesModel,
    SessionModel,
    SuccessModel,
    dialog_rows,
    outcomes_section_data,
    session_section_data,
    success_section_data,
)
from georep.report.pages import build_page, sections_for
from georep.settings import Settings, load_settings

pytestmark = pytest.mark.slow

NOWHERE = Path("/nonexistent")
PAGE_BUDGET = 500_000
GUESTS_BUDGET = 32_000  # Plan § 7: „unter 30 KB“ für drei Tabellen
DIALOG_BUDGET = 300_000
PROFILES = ("duesseldorf", "duesseldorf-2014", "moenchengladbach")


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
    corpus = pl.read_parquet(layout.corpus)
    write_parquet(
        classify_originators(corpus, settings.originators),
        layout.document_originators,
        schema_version=1,
    )
    names = ["cosponsors", "references", "procedures"]
    if settings.outcomes.enabled:
        names += ["council_results", "outcomes"]
    rest = run_pipeline(steps, settings, names)
    assert all(o.status == "ausgeführt" for o in rest), [o.line() for o in rest]
    return Dataset(settings, layout)


@pytest.fixture(scope="module")
def datasets(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Dataset]:
    root = tmp_path_factory.mktemp("outcomes_page")
    return {p: _dataset(p, root / p) for p in PROFILES}


def _outcomes(dataset: Dataset) -> OutcomesModel:
    model = outcomes_section_data(dataset.layout, dataset.settings)["beschlusslage"]
    assert isinstance(model, OutcomesModel)
    return model


def test_die_beschlusslage_der_hauptperiode(datasets: dict[str, Dataset]) -> None:
    model = _outcomes(datasets["duesseldorf"])
    t = model.total
    assert model.on and not model.explorative and t is not None
    assert (t.motions, t.practice, t.missing) == (5_099, 0, 289)
    assert (t.accepted, t.changed, t.rejected, t.withdrawn) == (3_245, 660, 1_028, 406)
    assert (t.done, t.pending) == (88, 43)
    assert model.session is not None
    assert (model.session.body, model.session.day, model.session.motions) == (
        "Rat",
        dt.date(2021, 2, 5),
        155,
    )
    assert model.cells == ()
    council = next(r for r in model.rows if r.code == "RAT")
    assert council.counts.motions == 1_067


def test_die_praxiszellen_von_2014_bis_2020(datasets: dict[str, Dataset]) -> None:
    model = _outcomes(datasets["duesseldorf-2014"])
    assert model.total is not None and model.total.practice == 240
    assert [(c.body, c.year) for c in model.cells] == [
        ("Bezirksvertretung 9", 2014),
        ("Bezirksvertretung 9", 2015),
        ("Bezirksvertretung 9", 2016),
        ("Rat", 2016),
    ]
    assert sum(r.counts.practice for r in model.rows) <= 240


def test_der_erfolg_und_die_antworten_der_hauptperiode(datasets: dict[str, Dataset]) -> None:
    dataset = datasets["duesseldorf"]
    success = success_section_data(dataset.layout, dataset.settings)["antragserfolg"]
    assert isinstance(success, SuccessModel) and success.on
    council, districts = success.groups
    assert council.majority_ratio is not None and council.others_ratio is not None
    assert council.majority_ratio > 1.5 > 0.5 > council.others_ratio
    assert districts.majority_ratio == pytest.approx(1.0, abs=0.02)
    assert [r.label for r in council.rows] == sorted(
        (r.label for r in council.rows), key=str.casefold
    )
    session = session_section_data(dataset.layout, dataset.settings)["sitzung"]
    assert isinstance(session, SessionModel) and session.on and session.total is not None
    assert session.total.questions == 3_952
    council_row = next(r for r in session.rows if r.code == "RAT")
    assert council_row.share(council_row.answered) > 0.95 > council_row.share(council_row.attached)


def test_die_zweite_stadt_sagt_was_fehlt(datasets: dict[str, Dataset]) -> None:
    dataset = datasets["moenchengladbach"]
    model = _outcomes(dataset)
    assert not model.on and model.missing
    (guests,) = (v for k, v in sections_for(dataset.settings).items() if k == PAGE.name)
    assert [s.name for s in guests] == ["beschlusslage"]


@pytest.mark.parametrize("profile", PROFILES)
def test_die_seite_bleibt_unter_ihrem_budget(datasets: dict[str, Dataset], profile: str) -> None:
    dataset = datasets[profile]
    guests = sections_for(dataset.settings).get(PAGE.name, ())
    build_page(
        dataset.layout,
        dataset.settings,
        PAGE,
        guests,
        now=dt.datetime(2026, 11, 28, tzinfo=dt.UTC),
        commit=None,
    )
    html = PAGE.output(dataset.layout).read_text(encoding="utf-8")
    assert len(html.encode("utf-8")) < PAGE_BUDGET
    size = 0
    for guest in guests:
        start = html.index(f'<section id="{guest.name}">')
        size += len(html[start : html.index("</section>", start)].encode("utf-8"))
    assert size < GUESTS_BUDGET


@pytest.mark.parametrize("profile", ["duesseldorf", "duesseldorf-2014"])
def test_beschluesse_json_bleibt_unter_300_kb(datasets: dict[str, Dataset], profile: str) -> None:
    """Eine Obergrenze: jedes Dokument des Korpus im Dialog; ``dokumente.json`` trägt weniger."""
    import json

    dataset = datasets[profile]
    rows = dialog_rows(dataset.layout, dataset.settings)
    order = pl.read_parquet(dataset.layout.corpus, columns=["id"]).get_column("id").to_list()
    payload = dialog_payload(
        rows,
        order,
        "",
        title="Beschlusslage",
        version="0.0.0",
        generated_at=dt.datetime(2026, 11, 28, tzinfo=dt.UTC),
    )
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    assert len(text.encode("utf-8")) < DIALOG_BUDGET
