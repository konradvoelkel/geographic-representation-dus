"""Die ganze Offline-Kette für die zweite Stadt (Option 01, Stufe E).

Eingaben: ``tests/fixtures/mg/`` (drei Wahlbezirke Mönchengladbachs aus der Netzstichprobe vom
2026-10-12, siehe das README dort). Geprüft wird, dass dieselbe Kette mit einem anderen Profil
läuft, dass die Summen je Wahlbezirk denen der Wahlbezirks-CSV der Quelle gleichen (das ist der
Golden Master dieser Stufe) und dass die Seite die Stadt nennt, deren Profil gilt.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.bootstrap import bootstrap_from_settings
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.streets import directory_agreement
from georep.prep.voters import DISTRICT, ELIGIBLE_TOTAL, VOTERS
from georep.settings import Settings
from tests.conftest import MG, REPO, mg_settings

NETWORK = {"opendata", "papers", "organizations", "pdfs", "streets_osm", "pois_wiki"}


@pytest.fixture(scope="module")
def settings() -> Settings:
    return mg_settings()


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory, settings: Settings) -> Layout:
    root = tmp_path_factory.mktemp("mg_run")
    layout = replace(
        Layout.from_settings(settings),
        data_root=root / "data",
        cache_root=root / "cache",
        reference_root=MG,
    )
    bootstrap_from_settings(layout, settings)
    outcomes = run_pipeline(build_steps(settings, layout), settings)
    failed = [o for o in outcomes if o.step not in NETWORK and o.status != "ausgeführt"]
    assert not failed, [o.line() for o in failed]
    return layout


def test_the_profile_puts_the_second_city_in_its_own_folder(run: Layout) -> None:
    assert run.profile == "moenchengladbach"
    assert run.root.name == "moenchengladbach" and run.root.parent.name == "data"
    assert run.pdf_dir == run.cache_root / "moenchengladbach" / "pdf"
    assert run.http_cache == run.cache_root / "http.sqlite"  # geteilt, Schlüssel ist die URL


def test_the_steps_declare_the_street_directory_they_read(run: Layout, settings: Settings) -> None:
    """Was ein Schritt liest, steht in seinen Eingaben; sonst merkt kein Stamp eine Änderung."""
    steps = {s.name: s for s in build_steps(settings, run)}
    assert run.streets_directory is not None
    assert run.streets_directory in steps["streets"].inputs
    assert run.streets_directory in steps["report"].inputs
    assert run.streets_directory in steps["opendata"].outputs


def test_bootstrap_takes_the_package_format(run: Layout) -> None:
    """Das Paket der zweiten Stadt bringt Stores mit; es gibt kein ``paper_with_text.json``."""
    assert run.papers.is_file() and run.texts.is_file()
    assert run.results_csv.is_file() and run.districts_geojson.suffix == ".json"
    assert run.streets_directory is not None and run.streets_directory.is_file()
    assert run.district_names_csv is not None and run.district_names_csv.is_file()


def test_the_precincts_step_reads_the_service_answer(run: Layout, settings: Settings) -> None:
    """Die kanonische Datei der zweiten Stadt, festgenagelt an Zahl, Namen und Fläche (Befund 8).

    Die Flächensumme ist der Prüfpunkt, der die Quellform verrät: sie kommt aus den Esri-Ringen
    über die Schachtelung der Löcher, und sie ist auf den Quadratmeter dieselbe, die die Ringe
    der Antwort nach der Trapezformel ergeben (``tests/unit/test_precincts.py`` rechnet sie dort
    gegen das unabhängige Orakel). Ein stiller Wechsel der Quellform oder eine vereinfachte
    Dienstantwort (``maxAllowableOffset``) fällt hier auf, die Zahl der Flächen allein zeigte es
    nicht -- die 17 Stimmbezirke hat auch das Shapefile von 2022.
    """
    import json

    from shapely.geometry import shape

    canonical = json.loads(run.precincts_geojson.read_text(encoding="utf-8"))
    assert canonical["crs"]["properties"]["name"] == "EPSG:25832"
    assert len(canonical["features"]) == 17
    districts = {f["properties"]["wahlbezirk"] for f in canonical["features"]}
    assert districts == {4, 9, 23}
    names = {f["properties"]["wahlbezirk_name"] for f in canonical["features"]}
    assert names == {"Hardt", "Hermges/Dahl/Ohler", "Dorfbroich/Hövel"}
    area = sum(shape(f["geometry"]).area for f in canonical["features"])
    assert area == pytest.approx(20_024_527.60, abs=0.01)  # m², gemessen am 2026-10-14
    # Jede Fläche ist ein einfaches Polygon; mehrringig sind in dieser Stadt nur 11001 und 11003,
    # und die gehören zu Wahlbezirk 10 (``tests/fixtures/http/identify_mg_mehrringig.json``).
    assert {f["geometry"]["type"] for f in canonical["features"]} == {"Polygon"}


def test_the_sums_per_district_match_the_source(run: Layout, settings: Settings) -> None:
    """Golden Master der Stufe: die Aggregation der Stimmbezirke gleicht der Wahlbezirks-CSV."""
    columns = settings.columns.results
    assert run.district_names_csv is not None
    expected = (
        pl.read_csv(
            run.district_names_csv, separator=columns.sep, infer_schema=False, encoding="utf8"
        )
        .select(
            pl.col("gebiet-nr").cast(pl.Int64).alias(DISTRICT),
            pl.col("A").cast(pl.Int64).alias(ELIGIBLE_TOTAL),
            pl.col("B").cast(pl.Int64).alias(VOTERS),
            pl.col("D1").cast(pl.Int64).alias("CDU_Stimmen"),
            pl.col("D2").cast(pl.Int64).alias("SPD_Stimmen"),
            pl.col("D3").cast(pl.Int64).alias("GRUENE_Stimmen"),
        )
        .sort(DISTRICT)
    )
    got = pl.read_parquet(run.voters).select(expected.columns).sort(DISTRICT)
    assert got.to_dicts() == expected.to_dicts()


def test_the_page_names_the_city_of_the_profile(run: Layout) -> None:
    page = run.site_index.read_text(encoding="utf-8")
    assert "Mönchengladbacher Ratsdokumenten" in page
    assert "Stadt Mönchengladbach" in page
    assert page.count('id="bezirk-') == 3
    # Die Zeile „Weitere Städte" setzt erst ``georep publish``: eine Seite aus ``georep run``
    # steht für sich und nennt keine andere Stadt (Review 2026-10-12).
    assert "Düsseldorf" not in page and "vergleich.html" not in page


def test_the_summary_is_the_interface_of_the_second_city(run: Layout) -> None:
    import json

    payload = json.loads(run.site_summary.read_text(encoding="utf-8"))
    assert payload["city"]["slug"] == "moenchengladbach" and payload["city"]["ags"] == "05116000"
    assert payload["figures"]["districts"] == 3 and payload["figures"]["precincts"] == 17
    assert payload["regression"]["without"] is None  # exclude_districts ist leer (Frage 1.6)


def test_running_again_changes_nothing(run: Layout, settings: Settings) -> None:
    again = run_pipeline(build_steps(settings, run), settings)
    assert all(o.status == "übersprungen" for o in again)


def test_the_steps_of_a_city_without_context(settings: Settings) -> None:
    """Welche Schritte eine zweite Stadt laufen lässt.

    Kontextdaten bringt Mönchengladbach nicht mit, die Schritte entfallen statt mit einem leeren
    Regelsatz zu laufen. Die Flächen (``shapes``), die Gremien und seit Punkt 59 die Urheber
    laufen -- die Gremien mit der Beratungsfolge, denn die Drucksachennummer nennt hier keines.
    """
    names = [step.name for step in build_steps(settings, Layout.from_settings(settings))]
    assert "context" not in names and "controls" not in names
    assert "shapes" in names and "bodies" in names and "topics" in names
    # Punkt 45 und 58: die Ausschüsse stehen im Profil, der Klassifikator ist trotzdem aus --
    # nur 650 der 2 895 Dokumente tragen Text, und welche das sind, entscheidet der Server.
    assert settings.bodies.committees and not settings.classify.enabled
    assert "committees" not in names
    # Punkt 58: die Nummer trägt kein Kürzel, die Beratungsfolge die Gremien
    assert not settings.bodies.reference_pattern and len(settings.bodies.organizations) == 27
    # Punkt 59: die Fraktionen stehen im Profil, also läuft der Schritt ``parties``
    assert "parties" in names
    assert [p.key for p in settings.originators.parties] == [
        "CDU",
        "SPD",
        "GRUENE",
        "FDP",
        "Die_Linke",
        "AfD",
    ]
    assert settings.originators.fraction_types == ["3 - Fraktionsantrag"]
    assert settings.originators.person_types == ["6.1 - Mitgliederantrag"]


def test_the_paper_type_carries_the_originator_of_the_second_city(run: Layout) -> None:
    """Punkt 59: hier nennt die Dokumentart die Klasse, nicht der Titel und nicht der Textkopf.

    Die Fixture trägt fünf ``3 - Fraktionsantrag`` und eine ``6.2 - Berichtsvorlage
    Sondergremien``; die Klasse kommt bei allen sechs aus ``paper_type``, die Partei bei den
    Fraktionsanträgen aus Titel oder Briefkopf.
    """
    attribution = pl.read_parquet(run.document_originators)
    assert attribution.height == 6
    classes = dict(attribution.group_by("urheber_art").len().iter_rows())
    assert classes == {"Fraktion": 5, "Verwaltung": 1}
    assert set(attribution.get_column("quelle").to_list()) <= {"paper_type", "name", "text"}
    page = run.site_index.read_text(encoding="utf-8")
    assert 'id="parteien"' in page and "Urheber und Parteien" in page


# --- Übereinstimmung mit dem Straßenverzeichnis der Wahl ---------------------------------------


def test_directory_agreement_measures_the_geometry_against_the_directory(
    run: Layout, settings: Settings
) -> None:
    assert run.streets_directory is not None
    agreement = directory_agreement(
        run.streets, run.streets_directory, settings.columns.results, settings.precincts
    )
    assert 0.0 <= agreement.precinct_share <= 1.0
    assert 0.0 <= agreement.district_share <= 1.0
    assert agreement.district_share >= agreement.precinct_share  # gröber kann nur besser sein
    assert agreement.matched <= agreement.streets and agreement.streets > 0
    assert agreement.line()


def test_the_page_names_the_agreement_and_the_date_of_the_geometry(run: Layout) -> None:
    page = run.site_index.read_text(encoding="utf-8")
    assert "amtliche Straßenverzeichnis der Wahl kennt" in page
    assert "demselben Stimmbezirk" in page and "demselben Wahlbezirk" in page
    # Der Stand der Flächen, aus den Notizen des Profils: seit Punkt 62 der des Wahltags
    assert "Kommunalwahl 2025 Stimmbezirke" in page and "alle 179" in page


def test_the_marker_share_of_the_sample_is_recorded(run: Layout) -> None:
    """Frage 1.5: in der Stichprobe vom 2026-10-12 trägt kein Dokument den Marker ``betrifft``.

    Ohne Marker durchsucht die Kette den ganzen Text (``after_marker`` schneidet dann nichts);
    der volle Lauf in Stufe G misst den Anteil über die echte Wahlperiode neu.
    """
    texts = pl.read_parquet(run.texts)
    with_marker = sum("betrifft" in t.lower() for t in texts.get_column("text").to_list())
    assert (with_marker, texts.height) == (0, 5)


# --- Netzschritte gegen die Aufzeichnungen vom 2026-10-12 --------------------------------------


def test_the_network_steps_of_the_second_city_use_the_recorded_answers(
    tmp_path: Path, settings: Settings
) -> None:
    """Dieselben Schritte, dieselben Aufzeichnungen wie bei Düsseldorf, nur ein anderes Profil.

    Ein Stimmbezirk (10404, Wahlbezirk 04) genügt: die Fake-Session antwortet je URL einmal, und
    geprüft wird, dass Overpass-, SPARQL- und GeoSearch-Antwort durch die Kette kommen.
    """
    import json

    from tests.fakes import FakeSession, response

    http = REPO / "tests" / "fixtures" / "http"
    source = settings.sources
    layout = replace(
        Layout.from_settings(settings),
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
        reference_root=MG,
    )
    bootstrap_from_settings(layout, settings)
    run_pipeline(build_steps(settings, layout), settings, ["shapes"])
    canonical = json.loads(layout.precincts_geojson.read_text(encoding="utf-8"))
    one = {
        **canonical,
        "features": [f for f in canonical["features"] if f["properties"]["stimmbezirk"] == "10404"],
    }
    assert one["features"], "Stimmbezirk 10404 fehlt in der Fixture"
    layout.precincts_geojson.write_text(json.dumps(one), encoding="utf-8")
    routes: dict[str, Any] = {
        source.osm.overpass_endpoint: response(
            source.osm.overpass_endpoint,
            payload=json.loads((http / "overpass_mg_10404.json").read_text(encoding="utf-8")),
        ),
        source.wikidata.sparql_endpoint: response(
            source.wikidata.sparql_endpoint,
            payload=json.loads((http / "wikidata_sparql_mg.json").read_text(encoding="utf-8")),
        ),
        source.wikidata.wikipedia_api: response(
            source.wikidata.wikipedia_api,
            payload=json.loads(
                (http / "wikipedia_geosearch_mg_10404.json").read_text(encoding="utf-8")
            ),
        ),
    }
    steps = build_steps(settings, layout, FakeSession(routes), sleep=lambda _: None)
    outcomes = run_pipeline(steps, settings, ["streets_osm", "pois_wiki"], online=True, force=True)
    assert [o.status for o in outcomes] == ["ausgeführt", "ausgeführt"]

    streets = json.loads(layout.streets.read_text(encoding="utf-8"))
    assert [e["stimmbezirks_id"] for e in streets] == ["10404"]
    assert streets[0]["wahlbezirk_id"] == 4
    assert "Vorster Straße" in streets[0]["straßen"]  # der Name, den das Verzeichnis dort führt

    pois = json.loads(layout.pois.read_text(encoding="utf-8"))
    assert pois and all("label" in entry for entry in pois)
    assert any(entry.get("url") for entry in pois)  # SPARQL-Treffer tragen die Artikel-URL
