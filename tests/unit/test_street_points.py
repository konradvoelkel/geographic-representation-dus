"""Straßenpunkte und Ortsnamen der Startkarte (``docs/plan-startseite-2026-11.md``, § 4.1, § 4.2).

Drei Gruppen. **Lesen und rechnen**: GebRef wird nur für die Gemeinde gelesen, ohne Hausnummer; je
(Straße, Wahlbezirk) des Wörterbuchs steht der Medoid der Hausnummern, auf das Raster gerundet.
**Der Netzschritt** ``street_points`` steht nur mit seinem Schalter im Register und schreibt die
Dateien unter ``external/startkarte/``. **Paket und bootstrap**: ``georep pack --street-points``
packt nur, was der Schritt für diese Settings schrieb, und ``bootstrap`` legt es zurück.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from shapely.geometry import box

from georep.bootstrap import bootstrap
from georep.geo import Precinct
from georep.layout import Layout
from georep.pack import PackError, pack_street_points
from georep.pipeline import build_steps, run_step
from georep.prep.streetpoints import (
    GEBREF_MEMBER,
    LABELS_FILE,
    POINTS_FILE,
    SOURCES_FILE,
    START_DIR,
    STREET_COLUMNS,
    label_points,
    medoid,
    normalize_street,
    read_house_points,
    street_point_files,
    street_points,
    street_points_digest,
)
from georep.settings import Settings, StreetPointLabels, StreetPoints
from tests.fakes import FakeSession, response

GEBREF_URL = "https://example.org/gebref/gebref_EPSG25832_ASCII.zip"
LABELS_URL = "https://example.org/stadtteile.geojson"


def _line(ags: tuple[str, str, str, str], street: str, number: str, x: float, y: float) -> str:
    land, region, kreis, gemeinde = ags
    return (
        f"N;DENW01;A;{land};Land;{region};RB;{kreis};Kreis;{gemeinde};Ort;0000;;0001;{street};"
        f"{number};;32;{x:.3f};{y:.3f};2026-10-01\n"
    )


def _archive(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(GEBREF_MEMBER, "".join(lines))
    return buffer.getvalue()


HERE = ("05", "1", "11", "000")
ELSEWHERE = ("05", "9", "11", "000")
LINES = [
    _line(HERE, "Aachener Str.", "1", 10.0, 10.0),
    _line(HERE, "Aachener Straße", "3", 20.0, 10.0),
    _line(HERE, "Aachener Strasse", "5", 30.0, 10.0),
    _line(HERE, "Aachener Straße", "200", 160.0, 10.0),  # im zweiten Wahlbezirk
    _line(HERE, "Bahnweg", "2", 40.0, 40.0),
    _line(HERE, "Nirgendwo", "1", 900.0, 900.0),  # in keinem Stimmbezirk
    _line(ELSEWHERE, "Aachener Straße", "1", 15.0, 15.0),
]


def _precincts() -> list[Precinct]:
    return [
        Precinct("0101", 1, "Eins", box(0, 0, 100, 100)),
        Precinct("0201", 2, "Zwei", box(100, 0, 200, 100)),
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ückendorfer Str.", "ückendorfer straße"),
        ("Aachener Strasse", "aachener straße"),
        ("Graf-Adolf-Str. ", "graf-adolf-straße"),
        ("Alt - Pempelfort", "alt-pempelfort"),
        ("Am  Wehrhahn", "am wehrhahn"),
        ("Strasse des 17. Juni", "straße des 17. juni"),
    ],
)
def test_a_street_name_takes_the_long_form_of_the_dictionary(raw: str, expected: str) -> None:
    assert normalize_street(raw) == expected


def test_only_the_municipality_is_read_and_no_house_number(tmp_path: Path) -> None:
    archive = tmp_path / "gebref.zip"
    archive.write_bytes(_archive(LINES))
    houses = read_house_points(archive, "05111000")
    assert houses.columns == ["strasse", "x", "y"]
    assert houses.height == 6  # die Zeile der anderen Gemeinde fehlt
    assert set(houses.get_column("strasse")) == {"aachener straße", "bahnweg", "nirgendwo"}


def test_the_medoid_is_the_point_with_the_smallest_sum_of_distances() -> None:
    xs, ys = np.array([0.0, 1.0, 10.0]), np.array([0.0, 0.0, 0.0])
    assert medoid(xs, ys) == (1.0, 0.0)
    # Gleichstand: der kleinste Ostwert, dann der kleinste Nordwert
    assert medoid(np.array([2.0, 0.0]), np.array([0.0, 0.0])) == (0.0, 0.0)
    assert medoid(np.array([5.0, 5.0]), np.array([3.0, 1.0])) == (5.0, 1.0)


def test_one_rounded_point_per_street_and_district_of_the_dictionary(tmp_path: Path) -> None:
    archive = tmp_path / "gebref.zip"
    archive.write_bytes(_archive(LINES))
    houses = read_house_points(archive, "05111000")
    streets = {1: frozenset({"aachener straße", "bahnweg"}), 2: frozenset({"bahnweg"})}
    frame = street_points(houses, _precincts(), streets, 25.0)
    assert frame.columns == list(STREET_COLUMNS)
    rows = {(r[0], r[1]): r[2:] for r in frame.iter_rows()}
    # Aachener Straße in 2 kennt das Wörterbuch dort nicht; Nirgendwo liegt in keinem Stimmbezirk
    assert set(rows) == {("aachener straße", 1), ("bahnweg", 1)}
    assert rows[("aachener straße", 1)] == (25, 0, 3)  # Medoid (20, 10), auf 25 m gerundet
    assert rows[("bahnweg", 1)] == (50, 50, 1)
    assert all(value % 25 == 0 for value in frame.get_column("x").to_list())


def test_the_labels_are_a_name_and_a_point_on_the_area() -> None:
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"Name": "Mitte", "Nummer": "011"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[6.77, 51.22], [6.79, 51.22], [6.79, 51.23], [6.77, 51.22]]],
                },
            },
            {"type": "Feature", "properties": {"Name": ""}, "geometry": None},
        ],
    }
    frame = label_points(collection, "Name", "EPSG:25832")
    assert frame.columns == ["name", "x", "y"] and frame.height == 1
    x, y = frame.row(0)[1:]
    assert 340_000 < x < 350_000 and 5_670_000 < y < 5_680_000


def test_the_digest_follows_source_grid_and_names() -> None:
    base = street_points_digest(GEBREF_URL, 25.0, LABELS_URL, "Name")
    assert len(base) == 16
    assert street_points_digest(GEBREF_URL, 50.0, LABELS_URL, "Name") != base
    assert street_points_digest(GEBREF_URL, 25.0, "", "") != base


# --- der Netzschritt ------------------------------------------------------------------------------


def _switched(settings: Settings, *, fetch: bool = False) -> Settings:
    street = StreetPoints(
        url=GEBREF_URL,
        labels=StreetPointLabels(url=LABELS_URL, name="Name"),
        delay_s=0.0,
        fetch=fetch,
    )
    return settings.model_copy(update={"street_points": street})


def test_the_network_step_waits_for_its_own_switch(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    assert "street_points" not in [s.name for s in build_steps(default_settings, layout)]
    steps = build_steps(_switched(default_settings, fetch=True), layout, FakeSession({}))
    names = [s.name for s in steps]
    step = steps[names.index("street_points")]
    assert step.network and step.extra == street_points_digest(GEBREF_URL, 25.0, LABELS_URL, "Name")
    assert names.index("dictionary") < names.index("street_points") < names.index("report")
    # [street_points] steht nicht im Settings-Fingerprint: der Schalter rechnet nichts neu
    assert _switched(default_settings, fetch=True).fingerprint() == default_settings.fingerprint()


def test_the_network_step_writes_points_names_and_sources(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    layout.ensure_dirs()
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"Name": "Mitte"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[6.77, 51.22], [6.79, 51.22], [6.79, 51.23], [6.77, 51.22]]],
                },
            }
        ],
    }
    session = FakeSession(
        {
            GEBREF_URL: response(GEBREF_URL, content=_archive(LINES)),
            LABELS_URL: response(LABELS_URL, payload=collection),
        }
    )
    settings = _switched(default_settings, fetch=True)
    # die Eingaben des Schritts: die Stimmbezirke und die Straßen je Wahlbezirk
    layout.precincts_geojson.parent.mkdir(parents=True, exist_ok=True)
    layout.precincts_geojson.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "stimmbezirk": p.precinct_id,
                            "wahlbezirk": p.district_id,
                            "wahlbezirk_name": p.district_name,
                        },
                        "geometry": json.loads(json.dumps(p.geometry.__geo_interface__)),
                    }
                    for p in _precincts()
                ],
                "crs": {"type": "name", "properties": {"name": "EPSG:25832"}},
            }
        ),
        encoding="utf-8",
    )
    pl.DataFrame(
        {"wahlkreis_id": [1, 2], "suchbegriffe": [["Aachener Straße", "Bahnweg"], ["Bahnweg"]]}
    ).write_parquet(layout.streets_by_district)
    steps = build_steps(settings, layout, session)
    step = next(s for s in steps if s.name == "street_points")
    outcome = run_step(step, settings, online=True)
    assert outcome.status == "ausgeführt", outcome.line()
    files = street_point_files(layout)
    assert pl.read_parquet(files.points).height == 2
    assert pl.read_parquet(files.labels).get_column("name").to_list() == ["Mitte"]
    sources = json.loads(files.sources.read_text(encoding="utf-8"))
    assert sources["ags"] == settings.city.ags and sources["raster_m"] == 25.0
    assert [d["url"] for d in sources["dateien"]] == [GEBREF_URL, LABELS_URL]
    assert session.urls == [GEBREF_URL, LABELS_URL]
    # Ein zweiter Lauf lädt nicht neu: die Dateien sind frisch (cache.opendata_s)
    run_step(step, settings, online=True, force=True)
    assert session.urls == [GEBREF_URL, LABELS_URL]


# --- Paket und bootstrap ----------------------------------------------------------------------------


def _extracted(layout: Layout, settings: Settings, *, labels: bool = True) -> None:
    files = street_point_files(layout)
    files.points.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {"strasse": ["bahnweg"], "wahlkreis_id": [1], "x": [50], "y": [50], "hausnummern": [1]}
    ).write_parquet(files.points)
    urls = [settings.street_points.url]
    if labels:
        pl.DataFrame({"name": ["Mitte"], "x": [1], "y": [2]}).write_parquet(files.labels)
        urls.append(settings.street_points.labels.url)
    files.sources.write_text(
        json.dumps(
            {
                "ags": settings.city.ags,
                "raster_m": settings.street_points.round_m,
                "namen": settings.street_points.labels.name,
                "dateien": [{"url": url} for url in urls],
            }
        ),
        encoding="utf-8",
    )


def test_pack_and_bootstrap_carry_the_points_there_and_back(
    tmp_path: Path, default_settings: Settings
) -> None:
    settings = _switched(default_settings)
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    _extracted(layout, settings)
    target = tmp_path / "paket"
    report = pack_street_points(layout, settings, target)
    names = [f.name for f in report.files]
    assert names == [f"external/{START_DIR}/{n}" for n in (POINTS_FILE, LABELS_FILE, SOURCES_FILE)]
    assert (target / "README.md").is_file()
    fresh = Layout(tmp_path / "neu", tmp_path / "neu-cache", tmp_path / "reference")
    bootstrap(fresh, needs_dictionary=False, seed_corpus=False, street_points=target)
    for name in (POINTS_FILE, LABELS_FILE, SOURCES_FILE):
        copied = fresh.external / START_DIR / name
        assert copied.read_bytes() == (target / "external" / START_DIR / name).read_bytes()


def test_a_package_without_labels_is_complete_without_them(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Mönchengladbach hat keine Stadtteile im Profil: das Paket trägt nur Punkte und Quellen."""
    settings = default_settings.model_copy(update={"street_points": StreetPoints(url=GEBREF_URL)})
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    _extracted(layout, settings, labels=False)
    target = tmp_path / "paket"
    report = pack_street_points(layout, settings, target)
    assert [f.name.rsplit("/", 1)[1] for f in report.files] == [POINTS_FILE, SOURCES_FILE]
    fresh = Layout(tmp_path / "neu", tmp_path / "neu-cache", tmp_path / "reference")
    result = bootstrap(fresh, needs_dictionary=False, seed_corpus=False, street_points=target)
    assert not (fresh.external / START_DIR / LABELS_FILE).exists()
    assert not [m for m in result.missing if START_DIR in str(m)]


def test_pack_refuses_what_another_profile_or_no_run_wrote(
    tmp_path: Path, default_settings: Settings
) -> None:
    settings = _switched(default_settings)
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    with pytest.raises(PackError, match="fehlen"):
        pack_street_points(layout, settings, tmp_path / "leer")
    _extracted(layout, settings)
    other = settings.model_copy(
        update={"city": settings.city.model_copy(update={"ags": "05116000"})}
    )
    with pytest.raises(PackError, match="Gemeinde"):
        pack_street_points(layout, other, tmp_path / "anders")
    files = street_point_files(layout)
    pl.read_parquet(files.points).with_columns(pl.lit("12a").alias("hausnummer")).write_parquet(
        files.points
    )
    with pytest.raises(PackError, match="Hausnummer"):
        pack_street_points(layout, settings, tmp_path / "mit-nummer")


def test_fetching_needs_a_source_and_labels_need_a_name() -> None:
    with pytest.raises(ValueError, match="url"):
        StreetPoints(fetch=True)
    with pytest.raises(ValueError, match="name"):
        StreetPointLabels(url=LABELS_URL)
    assert StreetPoints.model_validate({"package": ""}).package is None
