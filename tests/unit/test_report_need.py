"""Die Unterseite ``bedarf.html`` (Vorhaben 22, Stufe 3).

Drei Gruppen wie bei ``akteure.html`` und ``vorgaenge.html`` (Punkte 88, 91). Die Bausteine: p in
Worten, die Power-Schwelle von § 8, kleine Karten mit Wahlbezirken ohne Wert, Streudiagramme mit
dem Stadtbezirk als Schicht. Die Prüfung der Klasse kommt aus ``guete.json`` und trägt die drei
Fälle aus § 4.1 des Messdokuments: eine geänderte Datei ändert die Seite. Die echte Seite der
Mini-Fixture: im Register, im Linkblock beider Seiten, mit Namensnennung und Veränderungshinweis,
Tag und Commit der Festlegung, den zwei Downloads mit Spaltendoku, unter dem Budget; und dieselbe
Seite ohne Fremddaten, Klassen und Hypothesen, wie in der zweiten Stadt, sagt, was fehlt.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import re
import shutil
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from shapely.geometry import box

from georep.enrich.need import PAGE, TABLES, need_files
from georep.errors import MissingInputError
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.report.build import report_fingerprint
from georep.report.need import (
    NO_VALUE,
    VALIDATION_PROJECT,
    ScatterPoint,
    build_need,
    need_data,
    need_links,
    need_scatter,
    p_text,
    power_threshold,
    read_check,
    read_inputs,
    small_map,
)
from georep.report.pages import page_frame, render_page
from georep.report.tables import published
from georep.settings import Settings
from tests.conftest import REPO

NOW = dt.datetime(2026, 11, 27, 12, 0, tzinfo=dt.UTC)
PAGE_BUDGET = 500_000  # docs/plan-zeigen-2026-11.md, § 6
SECTIONS = ("ueberblick", "quellen", "bedarf", "nennung", "grenzen")
NOWHERE = Path("/nonexistent")


def _check_settings(settings: Settings, root: Path = REPO / "validierung") -> Settings:
    return settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": root})}
    )


def _quality(tmp_path: Path, **change: Any) -> Path:
    """Eine Kopie der Prüfung mit geänderten Feldern der Frage; gibt ``validation.root`` zurück."""
    root = tmp_path / "validierung"
    folder = root / VALIDATION_PROJECT
    folder.mkdir(parents=True)
    source = REPO / "validierung" / VALIDATION_PROJECT
    shutil.copy(source / "stichprobe.json", folder / "stichprobe.json")
    quality = json.loads((source / "guete.json").read_text(encoding="utf-8"))
    entry = quality["fragen"]["ordnung_verkehr"]
    for key, value in change.items():
        if key == "interval":
            entry["treffer"]["grundgesamtheit"]["wilson95_kish"] = list(value)
        elif key == "weighted":
            entry["treffer"]["grundgesamtheit"]["schaetzer"] = value
        else:
            entry[key] = value
    (folder / "guete.json").write_text(json.dumps(quality, ensure_ascii=False), encoding="utf-8")
    return root


def _render(layout: Layout, settings: Settings) -> str:
    return render_page(
        page_frame(settings, now=NOW, commit=None),
        PAGE,
        need_data(layout, settings),
        need_links(layout, settings),
    )


def _section(page: str, name: str) -> str:
    part = page[page.index(f'<section id="{name}">') :]
    return part[: part.index("</section>")]


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).replace(" ", " ")


# --- Bausteine ------------------------------------------------------------------------------------
def test_p_in_worten() -> None:
    assert p_text(0.0429) == "0,043"
    assert p_text(0.0008) == "0,00080"
    assert p_text(0.00001) == "< 0,0001"
    assert p_text(None) == "–"


def test_die_power_schwelle_ist_die_aus_paragraph_8() -> None:
    """§ 8: bei n = 41 erkennt ein einseitiger Test mit 80 % Power nur |ρ| ≥ rund 0,39, im ersten
    Holm-Schritt (α/3) rund 0,46."""
    assert round(power_threshold(41, 0.05), 2) == 0.39
    assert round(power_threshold(41, 0.05 / 3), 2) == 0.46
    assert power_threshold(100, 0.05) < power_threshold(41, 0.05)


def test_eine_karte_zeigt_einen_wahlbezirk_ohne_wert_grau_und_nennt_ihn_in_der_legende() -> None:
    shapes = {1: box(0, 0, 1, 1), 2: box(1, 0, 2, 1), 3: box(2, 0, 3, 1)}
    panel = small_map("x", "Wert", {1: 1.0, 2: 2.0, 3: None}, shapes, {1: "A", 2: "B", 3: "C"}, str)
    assert panel.svg.count('class="district ohne"') == 1
    assert 'data-id="3" data-district="3"' in panel.svg
    assert panel.legend[-1] == ("ohne", NO_VALUE)
    full = small_map("y", "Wert", {1: 1.0, 2: 2.0, 3: 3.0}, shapes, {}, str)
    assert "ohne" not in full.svg and all(k != "ohne" for k, _ in full.legend)


def test_das_streudiagramm_traegt_den_stadtbezirk_am_mittelpunkt() -> None:
    """Zehn Stadtbezirke wären zehn Farben; statt dessen Nummer am Mittelpunkt und Linien."""
    points = [
        ScatterPoint(1, "A", 1, 1.0, 1.0),
        ScatterPoint(2, "B", 1, 3.0, 3.0),
        ScatterPoint(3, "C", 2, 5.0, 1.0),
    ]
    svg = need_scatter("s", points, "x", "y", str, str)
    assert svg.count('<g class="point"') == 3
    assert svg.count('class="centre"') == 2
    assert svg.count("<line x1=") >= 3  # je Punkt eine Linie zum Mittelpunkt, dazu das Gitter
    assert re.search(r'class="centre-label"[^>]*>1</text>', svg)
    assert need_scatter("s", [], "x", "y", str, str) == ""


# --- Die Prüfung der Klasse (Messdokument § 4.1) ----------------------------------------------------
def test_die_pruefung_im_repo_ist_fall_drei(default_settings: Settings) -> None:
    """Gemessen am 2026-11-27: 99 von 100 einig, α 0,000, die Regel der vollen Einigkeit greift
    nicht; die Seite nennt keine geprüfte Präzision."""
    check = read_check(_check_settings(default_settings))
    assert check.case == 3 and not check.alpha_ok
    assert (check.units, check.agreed, check.count("ja"), check.count("nein")) == (100, 99, 99, 1)
    assert check.population == 958 and check.measured
    assert check.models == ("claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
    assert "nicht von Menschen" in check.sentence


def test_ohne_guete_bricht_die_seite_ab(tmp_path: Path, default_settings: Settings) -> None:
    with pytest.raises(MissingInputError, match="guete.json"):
        read_check(_check_settings(default_settings, tmp_path))


@pytest.mark.parametrize(
    ("change", "case", "said", "unsaid"),
    [
        (
            {},
            3,
            (
                "kein verlässliches Maß",
                "99 von 100",
                "geprüfte Präzision nennt die Seite darum nicht",
            ),
            ("unscharf",),
        ),
        (
            {"alpha_genuegt": True, "interval": (0.85, 0.99), "weighted": 0.95},
            1,
            ("gewichtet zu 95,0 %", "85,0 % bis 99,0 %"),
            ("unscharf", "kein verlässliches Maß"),
        ),
        (
            {"alpha_genuegt": True, "interval": (0.55, 0.8), "weighted": 0.7},
            2,
            ("trifft die Klasse nur zu 70 % zu", "unscharf"),
            ("kein verlässliches Maß",),
        ),
    ],
    ids=["gemessen", "praezision", "unscharf"],
)
def test_die_drei_faelle_aus_paragraph_4_1(
    tmp_path: Path,
    mini_run: Layout,
    default_settings: Settings,
    change: dict[str, Any],
    case: int,
    said: tuple[str, ...],
    unsaid: tuple[str, ...],
) -> None:
    """Eine geänderte ``guete.json`` ändert die Seite: Präzision mit Prüfsatz, unscharf, oder
    keine Präzision. Die Grundgesamtheit heißt „ohne Ausschussberatung (vor allem
    Bezirksvertretungen)“, denn zu ihr gehören auch Rat und Beiräte (Supervisor, 2026-11-27)."""
    settings = _check_settings(default_settings, _quality(tmp_path, **change))
    assert read_check(settings).case == case
    page = _render(mini_run, settings)
    text = _text(_section(page, "ueberblick") + _section(page, "grenzen"))
    for phrase in said:
        assert phrase in text, phrase
    for phrase in unsaid:
        assert phrase not in text, phrase
    assert "ohne Ausschussberatung (vor allem Bezirksvertretungen)" in text
    assert "Dokumenten der Bezirksvertretungen trifft" not in text


# --- Die echte Seite der Mini-Fixture -------------------------------------------------------------
def test_die_seite_steht_im_register_und_in_beiden_linkbloecken(mini_run: Layout) -> None:
    page = (mini_run.site / "bedarf.html").read_text(encoding="utf-8")
    details = mini_run.site_details.read_text(encoding="utf-8")
    start = mini_run.site_index.read_text(encoding="utf-8")
    weitere = details[details.index('<section id="weitere">') :]
    assert f'<a href="bedarf.html">{PAGE.title}</a>' in weitere
    assert 'href="bedarf.html"' in start
    assert len(page.encode("utf-8")) < PAGE_BUDGET
    for name in SECTIONS:
        assert page.count(f'<section id="{name}">') == 1


def test_namensnennung_mit_veraenderungshinweis_und_festlegung_mit_tag(
    mini_run: Layout, default_settings: Settings
) -> None:
    """V5: jede Bedarfsquelle sagt im Quellenvermerk, was verändert ist. Die Tests stehen mit Tag
    und Commit ihrer Festlegung (§ 7)."""
    page = _render(mini_run, _check_settings(default_settings))
    sources = _text(_section(page, "quellen"))
    need = default_settings.context.need
    for attribution in (
        need.accidents.attribution,
        need.grid.attribution,
        need.schools.attribution,
    ):
        assert f"{attribution.title}" in sources
        assert attribution.modified in sources
    assert "Quartiersatlas" in sources and "verändert: Sozialräume auf Wahlbezirke" in sources
    tests = _section(page, "nennung")
    assert "am 23.11.2026, Commit" in _text(tests)
    assert (
        'href="https://github.com/konradvoelkel/geographic-representation-dus/commit/67f7250"'
        in tests
    )
    assert tests.count('<div class="test"') == 3


def test_keine_rangfolge_aus_bedarf_und_nennung(
    mini_run: Layout, default_settings: Settings
) -> None:
    """§ 7: keine Rangfolge „Bedarf minus Aufmerksamkeit", nichts je Partei, keine Personen."""
    page = _render(mini_run, _check_settings(default_settings))
    table = page[page.index('<table id="districts"') :]
    head = table[: table.index("</thead>")]
    assert "minus" not in head and "Differenz" not in head and "Rang" not in head
    assert "Partei" not in _text(page) and "Fraktion" not in _text(page)


def test_die_zwei_tabellen_stehen_als_download_mit_spaltendoku(
    mini_run: Layout, default_settings: Settings
) -> None:
    names = {t.name for t in published(mini_run, default_settings)}
    assert {"wahlbezirke_bedarf", "bedarf_hypothesen"} <= names
    schema = json.loads((mini_run.site_data / "schema.json").read_text(encoding="utf-8"))
    for table in TABLES:
        assert (mini_run.site_data / f"{table.name}.csv").is_file()
        assert (mini_run.site_data / table.path(mini_run).name).is_file()
        assert list(pl.read_parquet_schema(table.path(mini_run))) == list(table.columns)
        described = {c["column"]: c["description"] for c in schema["tables"][table.name]}
        assert described == {name: doc[0] for name, doc in table.columns.items()}


def test_ohne_fremddaten_klassen_und_hypothesen_sagt_die_seite_was_fehlt(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Wie in der zweiten Stadt (Frage 22.6): Bedarf ohne Klassen, die Karte des
    Schulsozialindex statt des Handlungsbedarfs, keine Tests, und jeder fehlende Teil mit Grund."""
    settings = _check_settings(default_settings)
    inputs = dataclasses.replace(
        read_inputs(mini_run, settings), context=None, committees=None, tests=None, context_units=0
    )
    model = build_need(inputs, settings, None)
    assert model.classes is None and model.check is None and model.tests == ()
    assert [p.key for p in model.maps] == ["unfaelle", "schulsozialindex"]
    assert len(model.missing) == 3
    assert [s.title for s in model.sources] == [
        a.title
        for a in (
            settings.context.need.accidents.attribution,
            settings.context.need.grid.attribution,
            settings.context.need.schools.attribution,
        )
    ]


def test_der_schritt_liest_tabellen_pruefung_und_unfaelle(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    files = need_files(layout)
    steps = build_steps(default_settings, layout)
    page = next(s for s in steps if s.name == "page_bedarf")
    check = default_settings.validation.root / VALIDATION_PROJECT
    assert {files.table, files.tests, files.accidents, check / "guete.json"} <= set(page.inputs)
    report = next(s for s in steps if s.name == "report")
    assert {files.table, files.tests} <= set(report.inputs) | set(report.optional)


def test_die_namensnennung_zaehlt_im_zusatz_der_seiten(default_settings: Settings) -> None:
    """Die Namensnennung und der Tag der Festlegung sind Anzeige und stehen nicht im
    Fingerprint der Kette; die Seite zeigt sie, also muss ihr Stamp sie kennen (Punkt 53)."""
    before = report_fingerprint(default_settings)
    need = default_settings.context.need
    attribution = need.grid.attribution.model_copy(update={"modified": "verändert: anders"})
    changed = default_settings.model_copy(
        update={
            "context": default_settings.context.model_copy(
                update={
                    "need": need.model_copy(
                        update={"grid": need.grid.model_copy(update={"attribution": attribution})}
                    )
                }
            )
        }
    )
    assert changed.fingerprint() == default_settings.fingerprint()
    assert report_fingerprint(changed) != before
    moved = [h.model_copy(update={"fixed_on": dt.date(2026, 1, 1)}) for h in need.hypotheses]
    shifted = default_settings.model_copy(
        update={
            "context": default_settings.context.model_copy(
                update={"need": need.model_copy(update={"hypotheses": moved})}
            )
        }
    )
    assert report_fingerprint(shifted) != before
