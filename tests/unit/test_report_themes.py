"""Vorhaben 19, Stufe 3: die Unterseite ``themen.html`` und die Downloads der Politikfelder.

Messdokument ``docs/plans/19-politikfelder.md``, § 7 mit § 10. Die Bausteine an erfundenen Tabellen,
die Prüfung aus ``guete.json`` gegen die Konstanten der Messung, die echte Seite der Mini-Fixture mit
Lizenz oben und im Fuß, die Linkblöcke, die Downloads mit Lizenzzeile und Spalten, und dass keine
andere veröffentlichte Datei die Codes trägt (Frage 37: CC BY-NC-SA 4.0 nur dort).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import polars as pl
import pytest

from georep.enrich.policy_areas import CODES, NO_AREA, TABLES
from georep.errors import SchemaError
from georep.layout import Layout
from georep.report.themes import (
    BUNDESTAG_QUERIES,
    BUNDESTAG_TOTAL,
    MEASURED,
    MIN_DOCUMENTS,
    ThemesInputs,
    build_themes,
    read_check,
    share_rows,
)
from georep.settings import Settings, load_settings

REPO = Path(__file__).resolve().parents[2]
NOWHERE = Path("/nonexistent")
LICENSE = "https://creativecommons.org/licenses/by-nc-sa/4.0/deed.de"


def _settings(profile: str) -> Settings:
    return load_settings(cwd=NOWHERE, profile=profile)


# --- Die Prüfung ------------------------------------------------------------------------------------
def test_the_check_reads_guete_json_and_matches_the_measured_constants() -> None:
    check = read_check(_settings("duesseldorf"))
    assert round(check.macro_f1, 3) == MEASURED.macro_f1 == 0.704
    assert round(check.accuracy, 3) == 0.837
    assert check.units == MEASURED.units == 300 and check.agreed == 285
    assert "nicht von Menschen" in check.sentence and check.same_model
    assert MEASURED.interval == (0.620, 0.807) and MEASURED.bundestag_f1 == 0.688
    # die schwächsten Felder und die häufigste Verwechslung kommen aus guete.json (§ 4.4)
    assert [name for name, _ in check.weakest] == ["Gesundheit", "Ordnung"]
    assert check.confusion == ("Kultur", "Soziales", 3, 27)


@pytest.mark.parametrize(
    ("profile", "status"),
    [
        ("duesseldorf", "gemessen"),
        ("duesseldorf-vergleich", "gemessen"),
        ("duesseldorf-2014", "periode"),
        ("duesseldorf-2025", "periode"),
        ("moenchengladbach", "explorativ"),
    ],
)
def test_only_the_dataset_of_the_sample_is_measured(profile: str, status: str) -> None:
    check = read_check(_settings(profile))
    assert check.status == status
    assert check.measured_dataset == "Düsseldorf, Wahlperiode 2020 bis 2025"


@pytest.mark.parametrize(
    ("field", "value"),
    [("codebuch_version", "2026-12-01.2"), ("einheiten", 299), ("makro", 0.75)],
)
def test_a_new_coding_stops_the_page_until_the_constants_follow(
    tmp_path: Path, field: str, value: object
) -> None:
    source = REPO / "validierung" / "19-politikfelder"
    folder = tmp_path / "19-politikfelder"
    shutil.copytree(source, folder)
    quality = json.loads((folder / "guete.json").read_text(encoding="utf-8"))
    if field == "makro":
        quality["fragen"]["politikfeld"]["verfahren"]["makro"]["f1"] = value
    elif field == "einheiten":
        quality["fragen"]["politikfeld"]["n"] = value
    else:
        quality[field] = value
    (folder / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    settings = _settings("duesseldorf")
    moved = settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": tmp_path})}
    )
    with pytest.raises(SchemaError, match="MEASURED"):
        read_check(moved)


def test_the_bundestag_counts_are_the_queries_of_the_german_project() -> None:
    assert sum(BUNDESTAG_QUERIES.values()) == BUNDESTAG_TOTAL == 10033
    assert set(BUNDESTAG_QUERIES) == set(CODES) - {NO_AREA}


# --- Bausteine an erfundenen Tabellen ----------------------------------------------------------------
def _areas(fields: list[str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [f"d{n:03d}" for n in range(len(fields))],
            "politikfeld": fields,
            "wahrscheinlichkeit": [0.9 if f else None for f in fields],
            "abgeschnitten": [n % 2 == 0 if f else None for n, f in enumerate(fields)],
        }
    )


def test_share_rows_count_a_joint_motion_for_every_fraction() -> None:
    areas = _areas(["10"] * 20 + ["14"] * 20 + [""] * 2)
    ids = areas.get_column("id").to_list()
    keyed = pl.DataFrame(
        {
            "id": ids[:40] + ids[:10] + ids[40:],
            "schluessel": ["A"] * 40 + ["B"] * 10 + ["A", "A"],
        }
    )
    rows = share_rows(areas, keyed, ["10", "14"], {"A": "Partei A"}, MIN_DOCUMENTS)
    assert [(r.key, r.label, r.documents, r.undetermined) for r in rows] == [
        ("A", "Partei A", 40, 2),
        ("B", "B", 10, 0),
    ]
    assert rows[0].shares == (0.5, 0.5) and rows[0].top == "Verkehr"
    assert rows[1].shares is None  # unter 30 Dokumenten mit Feld keine Verteilung


def test_the_model_splits_council_and_district_bodies() -> None:
    fields = ["10", "10", "14", "20", "", "99", "23"]
    areas = _areas(fields)
    ids = areas.get_column("id").to_list()
    bodies = pl.DataFrame(
        {
            "id": ids,
            "gremium_art": ["rat", "ausschuss", "bezirksvertretung", "bezirksvertretung", "rat",
                            "beirat", "unbekannt"],
        }
    )  # fmt: skip
    results = pl.DataFrame(
        {"wahlkreis_id": [1, 2], "paper_ids": [[ids[0], ids[2]], [ids[2], ids[4]]]}
    )
    check = read_check(_settings("duesseldorf"))
    model = build_themes(
        ThemesInputs(areas, bodies, None, results, {1: "Nord", 2: "Süd"}),
        _settings("duesseldorf"),
        check,
        {},
    )
    assert model.documents == 7 and model.with_area == 6 and model.undetermined == 1
    assert model.no_area == 1 and model.areas[-1].code == NO_AREA  # 99 zuletzt
    council, district, rest = model.groups
    assert (council.documents, council.with_area, council.undetermined) == (3, 2, 1)
    assert (district.documents, district.with_area) == (2, 2)
    assert (rest.documents, rest.with_area, rest.no_area) == (2, 2, 1)
    traffic = next(a for a in model.areas if a.code == "10")
    assert traffic.council_share == 1.0 and traffic.district_share == 0.0
    assert traffic.total == 2 and traffic.bundestag_share == 800 / 10033
    assert model.fractions is None
    assert [(d.label, d.documents, d.undetermined) for d in model.districts] == [
        ("1 Nord", 2, 0),
        ("2 Süd", 1, 1),
    ]
    assert model.district_documents == 2


# --- Die Seite der Mini-Fixture -----------------------------------------------------------------------
@pytest.fixture(scope="module")
def page(mini_run: Layout) -> str:
    return (mini_run.site / "themen.html").read_text(encoding="utf-8")


def test_the_page_carries_the_license_on_top_and_in_the_footer(page: str) -> None:
    main, footer = page.split("<footer>")
    assert main.index('<p class="lizenz">') < main.index('<section id="ueberblick">')
    assert f'<a href="{LICENSE}">CC BY-NC-SA 4.0</a>' in main
    assert f'<a href="{LICENSE}">CC BY-NC-SA 4.0</a>' in footer
    assert "Übrige Ergebnisse:" in footer and "Comparative Agendas Project" in footer
    assert "comparativeagendas.net" in main and "Breunig" in main


def test_the_other_pages_keep_their_cc0_footer(mini_run: Layout) -> None:
    for name in ("akteure.html", "bedarf.html", "vorgaenge.html", "zeit.html", "spalten.html"):
        footer = (mini_run.site / name).read_text(encoding="utf-8").split("<footer>")[1]
        assert footer.startswith("\n<p>Ergebnisse: <a href="), name
        assert "BY-NC-SA" not in footer, name


def test_the_page_has_its_sections_and_names_the_check(page: str) -> None:
    for anchor in ("ueberblick", "pruefung", "perioden", "fraktionen", "wahlbezirke", "bundestag",
                   "methode"):  # fmt: skip
        assert page.count(f'id="{anchor}"') == 1, anchor
    assert "(explorativ)" not in page  # die Hauptperiode ist gemessen
    assert "geprüft von zwei KI-Kodierern desselben Modells" in page
    assert "Makro-F1 0,704 (95 % 0,620 bis 0,807)" in page
    assert "Makro-F1 0,688" in page and "Destillation" in page
    assert "ökologischer Fehlschluss" in page
    assert "Anfragen des Bundestags 1976 bis 2005" in page
    assert len(page.encode("utf-8")) < 500_000


def test_the_link_blocks_lead_to_the_page(mini_run: Layout) -> None:
    for page in (mini_run.site / "index.html", mini_run.site_details):
        assert 'href="themen.html"' in page.read_text(encoding="utf-8"), page.name


def test_the_downloads_carry_the_license_and_their_columns(
    mini_run: Layout, mini_page: str
) -> None:
    data = mini_run.site / "data"
    assert (data / "politikfelder.parquet").is_file()
    assert not (data / "politikfelder.csv").exists()  # je Dokument nur Parquet (Rückstand 35)
    assert (data / "politikfelder_anteile.parquet").is_file()
    assert (data / "politikfelder_anteile.csv").is_file()
    rows = re.findall(r'<tr><td><a href="data/(politikfelder[^"]*)">.*?</tr>', mini_page)
    assert sorted(rows) == [
        "politikfelder.parquet",
        "politikfelder_anteile.csv",
        "politikfelder_anteile.parquet",
    ]
    for line in re.findall(r'<tr><td><a href="data/politikfelder[^"]*">.*?</tr>', mini_page):
        assert "CC BY-NC-SA 4.0, nicht CC0" in line
    assert "<code>politikfelder</code>: Lizenz CC BY-NC-SA 4.0" in mini_page
    columns = (mini_run.site / "spalten.html").read_text(encoding="utf-8")
    assert columns.count('<section id="politikfelder">') == 1
    assert columns.count('<section id="politikfelder_anteile">') == 1
    schema = json.loads((data / "schema.json").read_text(encoding="utf-8"))
    assert {"politikfelder", "politikfelder_anteile"} <= set(schema["tables"])
    assert [t.name for t in TABLES] == ["politikfelder", "politikfelder_anteile"]


def test_no_other_published_file_carries_the_codes(mini_run: Layout) -> None:
    """Frage 37: die Codes stehen unter CC BY-NC-SA 4.0, getrennt vom Rest der Seite (CC0)."""
    own = {"politikfelder.parquet", "politikfelder_anteile.parquet", "politikfelder_anteile.csv"}
    for path in sorted((mini_run.site / "data").rglob("*")):
        if not path.is_file() or path.name in own:
            continue
        if path.suffix == ".parquet":
            assert "politikfeld" not in pl.read_parquet_schema(path), path.name
        elif path.suffix in {".csv", ".json", ".geojson"} and path.name != "schema.json":
            assert "politikfeld" not in path.read_text(encoding="utf-8"), path.name
