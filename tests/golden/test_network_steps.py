"""Netzschritte gegen eine Fake-Session: Opendata, Metadaten, PDFs, Texte, dann der Korpus."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import polars as pl
import pytest
import requests

from georep.bootstrap import bootstrap
from georep.errors import NetworkError
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.settings import Settings, load_settings
from georep.sources.oparl import read_progress
from georep.stores import PaperStore, TextStore
from tests.conftest import MINI, PDF_FIXTURES
from tests.fakes import FakeSession, response

NAMES = ["00438685.pdf", "00439409.pdf"]


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def _paper(i: int, name: str, date: str) -> dict[str, Any]:
    return {
        "id": f"https://ris.invalid/papers/{i}",
        "name": f"P{i}",
        "reference": f"r{i}",
        "date": date,
        "paperType": "Antrag",
        "mainFile": {
            "id": f"https://ris.invalid/files/{i}",
            "fileName": name,
            "downloadUrl": f"https://ris.invalid/downloadfiles/{name}",
        },
        "modified": f"{date}T11:00:00+02:00",
    }


def _session(settings: Settings) -> FakeSession:
    src = settings.sources
    csv = (MINI / "external" / "Stimmbezirk_Wahlergebnis.csv").read_bytes()
    geo = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": None}],
    }
    page = {
        "data": [
            _paper(1, NAMES[0], "2024-05-01"),
            _paper(2, NAMES[1], "2021-02-02"),
            _paper(3, "x.pdf", "2019-01-01"),
        ],
        "links": {"self": src.oparl.endpoint},
    }
    routes: dict[str, Any] = {
        src.opendata.results_url: response(src.opendata.results_url, content=csv),
        src.opendata.districts_url: response(src.opendata.districts_url, payload=geo),
        src.oparl.endpoint: response(src.oparl.endpoint, payload=page),
    }
    for name in NAMES:
        url = f"https://ris.invalid/downloadfiles/{name}"
        routes[url] = response(url, content=(PDF_FIXTURES / name).read_bytes())
    return FakeSession(routes)


def test_online_run_fetches_everything_then_skips(tmp_path: Path, settings: Settings) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    session = _session(settings)
    slept: list[float] = []
    steps = build_steps(settings, layout, session, sleep=slept.append)
    names = ["opendata", "papers", "pdfs", "texts", "corpus"]

    offline = run_pipeline(steps, settings, names[:3])
    assert [o.status for o in offline[:3]] == ["übersprungen"] * 3
    assert all("Netz aus" in o.reason for o in offline[:3])

    first = run_pipeline(steps, settings, names, online=True)
    assert [o.status for o in first] == ["ausgeführt"] * 5
    assert layout.results_csv.exists() and layout.districts_geojson.exists()
    assert [r.file_name for r in PaperStore(layout.papers).load().values()] == NAMES  # 2019 draußen
    assert "vollständig" in first[1].reason and "2 im Zeitraum" in first[1].reason
    assert (
        "2 geladen" in first[2].reason
        and sorted(p.name for p in layout.pdf_dir.glob("*.pdf")) == NAMES
    )
    assert "2 extrahiert" in first[3].reason and len(TextStore(layout.texts)) == 2
    corpus = pl.read_parquet(layout.corpus)
    assert corpus.height == 2 and all(len(t) > 500 for t in corpus["text"].to_list())
    assert slept == [1.0, 1.0]  # eine Pause je PDF-Download, keine zwischen Seiten (eine Seite)

    second = run_pipeline(steps, settings, names, online=True)
    assert [o.status for o in second] == ["übersprungen"] * 5

    forced = run_pipeline(steps, settings, ["papers"], online=True, force=True)
    assert forced[0].status == "ausgeführt" and "seit 2024-04-30" in forced[0].reason
    assert session.calls[-1][1] == {"modified_since": "2024-04-30T11:00:00+02:00"}


def test_context_data_fetches_the_three_portal_files(tmp_path: Path, settings: Settings) -> None:
    """Option 03: der Netzschritt holt Tabelle, Flächen und Erläuterungen nach ``external/``.

    Die Fake-Session antwortet mit den Kopfzeilen der Mini-Fixture, nicht mit den ganzen Dateien:
    geprüft wird der Schritt, nicht der Inhalt des Portals.
    """
    files = settings.context.files
    layout = Layout(
        tmp_path / "data", tmp_path / "cache", tmp_path / "reference", context_root=MINI / "context"
    )
    table = (MINI / "context" / files.table.file).read_bytes().split(b"\r\n")[0] + b"\r\n"
    units = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {settings.context.units.key: "011001"},
                "geometry": None,
            }
        ],
    }
    routes: dict[str, Any] = {
        files.table.url: response(files.table.url, content=table),
        files.units.url: response(files.units.url, payload=units),
        files.indicators.url: response(files.indicators.url, content=b"Indikator;Berechnung\r\n"),
    }
    steps = build_steps(settings, layout, FakeSession(routes))
    step = next(s for s in steps if s.name == "context_data")
    assert step.network and [p.name for p in step.outputs] == list(files.names())

    first = run_pipeline(steps, settings, ["context_data"], online=True)
    assert first[0].status == "ausgeführt" and "1 Sozialräume" in first[0].reason
    for name in files.names():
        assert (layout.external / name).exists()
    assert (layout.external / files.table.file).read_bytes() == table
    assert run_pipeline(steps, settings, ["context_data"], online=True)[0].status == "übersprungen"


def test_without_context_root_the_three_steps_are_absent(
    tmp_path: Path, settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    names = [s.name for s in build_steps(settings, layout)]
    assert "context_data" not in names and layout.context_root is None


def test_streets_and_pois_steps_use_recorded_answers(
    tmp_path: Path, settings: Settings, reference_root: Path
) -> None:
    import json

    from tests.conftest import REPO

    http = REPO / "tests" / "fixtures" / "http"
    src = settings.sources
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    layout.ensure_dirs()
    collection = json.loads(
        (reference_root / "external" / "Stimmbezirke_2025.geojson").read_text(encoding="utf-8")
    )
    one = {
        **collection,
        "features": [
            f for f in collection["features"] if f["properties"]["Stimm-/ Wahlbezirk"] == "1302"
        ],
    }
    layout.districts_geojson.write_text(json.dumps(one), encoding="utf-8")
    routes: dict[str, Any] = {
        src.osm.overpass_endpoint: response(
            src.osm.overpass_endpoint,
            payload=json.loads((http / "overpass_1302.json").read_text(encoding="utf-8")),
        ),
        src.wikidata.sparql_endpoint: response(
            src.wikidata.sparql_endpoint,
            payload=json.loads((http / "wikidata_sparql.json").read_text(encoding="utf-8")),
        ),
        src.wikidata.wikipedia_api: response(
            src.wikidata.wikipedia_api,
            payload=json.loads(
                (http / "wikipedia_geosearch_1302.json").read_text(encoding="utf-8")
            ),
        ),
    }
    steps = build_steps(settings, layout, FakeSession(routes), sleep=lambda _: None)
    outcomes = run_pipeline(
        steps, settings, ["streets_osm", "pois_wiki", "streets", "pois"], online=True
    )
    assert [o.status for o in outcomes] == ["ausgeführt"] * 4
    streets = json.loads(layout.streets.read_text(encoding="utf-8"))
    reference = next(
        e
        for e in json.loads(
            (reference_root / "raw" / "streets_per_district.json").read_text(encoding="utf-8")
        )
        if e["stimmbezirks_id"] == "1302"
    )
    assert streets == [reference]
    pois = json.loads(layout.pois.read_text(encoding="utf-8"))
    assert len(pois) == 25 + 2 and all("wahlkreis_id" in p for p in pois)
    assert "1 Stimmbezirke, 11 Straßennamen" in outcomes[0].reason
    assert "25 per SPARQL, 2 per GeoSearch" in outcomes[1].reason
    assert layout.streets_by_district.exists() and layout.pois_by_district.exists()


# --- Option 04: der Netzschritt organizations und die Quelle „oparl" ------------------------------


def test_organizations_step_feeds_the_party_attribution(tmp_path: Path, settings: Settings) -> None:
    """Mit ``raw/organizations.json`` ordnet ``parties`` ein Paper mit ``originatorOrganization``
    der FDP zu, Quelle ``oparl``; die Route antwortet mit der aufgezeichneten Seite vom 2026-10-11."""
    from georep.analysis.parties import ART, PARTEIEN, QUELLE, read_organizations

    layout = Layout(tmp_path / "data", tmp_path / "cache", MINI)
    bootstrap(layout)
    fixture = (MINI.parent / "oparl" / "organizations_page.json").read_text(encoding="utf-8")
    endpoint = settings.sources.oparl.organizations_endpoint
    session = FakeSession({endpoint: response(endpoint, content=fixture.encode())})
    steps = build_steps(settings, layout, session, sleep=lambda _: None)
    outcome = run_pipeline(steps, settings, ["organizations"], online=True)[0]
    assert outcome.status == "ausgeführt" and "12 Organisationen auf 1 Seite(n)" in outcome.reason
    found = read_organizations(layout.organizations)
    assert len(found) == 12 and {o.short_name for o in found} >= {"FDP", "AfD"}

    # Die Offline-Kette einmal rechnen, damit parties seine Eingaben hat
    offline = [s.name for s in steps if not s.network]
    assert all(o.status == "ausgeführt" for o in run_pipeline(steps, settings, offline))

    # Ein Paper mit Urheberfeld in den Store schieben und die Kette ab corpus neu rechnen
    store = PaperStore(layout.papers)
    records = store.load()
    one = sorted(records)[0]
    fdp = next(o for o in found if o.short_name == "FDP")
    store.save(
        [
            *(r for key, r in records.items() if key != one),
            records[one].model_copy(update={"originator_organization": (fdp.id,)}),
        ]
    )
    # Der Schritt parties muss organizations.json als Eingabe sehen: Schritte neu aufbauen
    rebuilt = build_steps(settings, layout, session, sleep=lambda _: None)
    parties_step = next(s for s in rebuilt if s.name == "parties")
    assert layout.organizations in parties_step.inputs
    run_pipeline(rebuilt, settings, ["corpus", "parties"], force=True)
    attribution = pl.read_parquet(layout.document_originators)
    row = attribution.filter(pl.col("id") == one).row(0, named=True)
    assert (row[ART], row[QUELLE], row[PARTEIEN]) == ("Fraktion", "oparl", ["FDP"])
    # Alle anderen Dokumente bleiben bei den Mustern
    assert attribution.filter(pl.col(QUELLE) == "oparl").height == 1


def test_the_parties_step_runs_without_the_organizations_file(
    tmp_path: Path, settings: Settings
) -> None:
    """Ohne den Netzschritt greifen nur die URL-Endungen der Settings; die Kette läuft trotzdem."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", MINI)
    bootstrap(layout)
    steps = build_steps(settings, layout)
    parties_step = next(s for s in steps if s.name == "parties")
    assert layout.organizations not in parties_step.inputs and not layout.organizations.exists()
    outcomes = run_pipeline(steps, settings, [s.name for s in steps if not s.network])
    assert all(o.status == "ausgeführt" for o in outcomes)
    assert "Organisationen" not in next(o for o in outcomes if o.step == "parties").reason
    assert pl.read_parquet(layout.document_originators).height == 200


# --- Option 02: Wiederaufnahme des Abrufs im Schritt papers -----------------------------------


def _period_session(settings: Settings, broken_page: str | None = None) -> FakeSession:
    """Drei Metadatenseiten ab Seite 2; ``broken_page`` lässt eine davon scheitern."""
    endpoint = settings.sources.oparl.endpoint
    pages = {
        f"{endpoint}?page={n}": {
            "data": [_paper(n * 10 + i, f"{n}{i}.pdf", f"201{n}-0{i + 1}-01") for i in range(2)],
            "links": {
                "self": f"{endpoint}?page={n}",
                **({"next": f"{endpoint}?page={n + 1}"} if n < 4 else {}),
            },
        }
        for n in (2, 3, 4)
    }
    routes: dict[str, Any] = {url: response(url, payload=page) for url, page in pages.items()}
    if broken_page is not None:
        routes[broken_page] = requests.ConnectionError("Verbindung weg")
    return FakeSession(routes)


def _period_settings(settings: Settings, tmp_path: Path) -> Settings:
    oparl = settings.sources.oparl.model_copy(update={"first_page": 2, "incremental": False})
    sources = settings.sources.model_copy(update={"oparl": oparl})
    period = settings.period.model_copy(
        update={"start": dt.date(2010, 1, 1), "end": dt.date(2019, 12, 31)}
    )
    return settings.model_copy(
        update={
            "sources": sources,
            "period": period,
            "data_root": tmp_path / "data",
            "cache_root": tmp_path / "cache",
        }
    )


def test_an_interrupted_metadata_fetch_resumes_at_the_next_page(
    tmp_path: Path, settings: Settings
) -> None:
    period = _period_settings(settings, tmp_path)
    layout = Layout.from_settings(period)
    endpoint = period.sources.oparl.endpoint
    broken = f"{endpoint}?page=3"

    steps = build_steps(period, layout, _period_session(period, broken), sleep=lambda _: None)
    with pytest.raises(NetworkError):
        run_pipeline(steps, period, ["papers"], online=True)
    assert read_progress(layout.papers_progress) == broken
    assert len(PaperStore(layout.papers).load()) == 2  # nur Seite 2 ist gespeichert

    session = _period_session(period)
    outcome = run_pipeline(
        build_steps(period, layout, session, sleep=lambda _: None),
        period,
        ["papers"],
        online=True,
    )[0]
    assert outcome.status == "ausgeführt" and "fortgesetzt" in outcome.reason
    assert session.urls == [broken, f"{endpoint}?page=4"]  # Seite 2 wird nicht erneut geladen
    assert len(PaperStore(layout.papers).load()) == 6
    assert not layout.papers_progress.exists()


def test_force_repeats_the_step_but_keeps_the_resume_point(
    tmp_path: Path, settings: Settings
) -> None:
    """``--force`` umgeht den Stamp, nicht den Netz-Cursor.

    Der Fortschritt existiert nur nach einem abgebrochenen Abruf. Ihn bei ``--force`` zu löschen
    hieße, drei Stunden noch einmal zu laden, ohne dass eine einzige Zeile anders würde: der
    Store schreibt dieselben Paper noch einmal. Wer wirklich von vorn will, löscht die Datei;
    README und Plan sagen das.
    """
    period = _period_settings(settings, tmp_path)
    layout = Layout.from_settings(period)
    endpoint = period.sources.oparl.endpoint
    broken = f"{endpoint}?page=3"
    steps = build_steps(period, layout, _period_session(period, broken), sleep=lambda _: None)
    with pytest.raises(NetworkError):
        run_pipeline(steps, period, ["papers"], online=True)
    assert read_progress(layout.papers_progress) == broken

    session = _period_session(period)
    outcome = run_pipeline(
        build_steps(period, layout, session, sleep=lambda _: None),
        period,
        ["papers"],
        online=True,
        force=True,
    )[0]
    assert outcome.status == "ausgeführt" and "erzwungen" in outcome.reason
    assert session.urls[0] == broken  # nicht wieder bei first_page
    assert not layout.papers_progress.exists()
