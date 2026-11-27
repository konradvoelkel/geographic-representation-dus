"""Das Spaltenschema auf einer eigenen Seite ``spalten.html`` (``docs/todo.md``, Punkt 36).

Bis ``v0.40.0`` stand unter den Downloads von ``details.html`` je Tabelle ein ``<details>`` mit
Spalte, Typ, Bedeutung und Einheit, in der Hauptperiode der größte Teil der 78 KB des Abschnitts.
Die Regel gilt für das ganze Register: keine Seite außer ``spalten.html`` trägt ein
Spaltenschema; dort hat jede Tabelle einen Abschnitt mit ihrem Namen als Anker, aus denselben Daten
wie ``schema.json``, und jede Downloadzeile einer Tabelle auf ``details.html`` verlinkt ihn.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from html import unescape

from georep.layout import Layout
from georep.report.build import COLUMNS_NAME, GEOJSON_NAME, SCHEMA_NAME
from georep.report.model import ColumnDoc, ReportModel
from georep.report.pages import pages_for
from georep.report.publish import page_budgets
from georep.report.render import anchors_once, render_columns
from georep.report.tables import GEOJSON_TABLE, published
from georep.settings import Settings
from tests.conftest import within_budget

_ID = re.compile(r'(?<![\w-])id="([^"]*)"')
_HREF = re.compile(r'href="([^"]*)"')
_SECTION = re.compile(r'<section id="([^"]*)"')
_HEAD = re.compile(r"<thead>(.*?)</thead>", re.S)
_TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
_ROW = re.compile(r"<tr><td><code>(.*?)</code></td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>")
_FOOTER = re.compile(r"<footer>.*?</footer>", re.S)
_GENERATED = re.compile(r"Erzeugt am [^<]*")


def schema_tables(page: str) -> int:
    """Wie viele Tabellen der Seite ein Spaltenschema sind: ihr Kopf nennt „Spalte“ und „Typ“."""
    return sum(
        1
        for head in _HEAD.findall(page)
        if {"Spalte", "Typ"} <= {unescape(cell).strip() for cell in _TH.findall(head)}
    )


def _columns(layout: Layout) -> str:
    return (layout.site / COLUMNS_NAME).read_text(encoding="utf-8")


def _details(layout: Layout) -> str:
    return layout.site_details.read_text(encoding="utf-8")


def _section(page: str, anchor: str) -> str:
    start = page.index(f'<section id="{anchor}">')
    return page[start : page.index("</section>", start)]


def _register(layout: Layout, settings: Settings) -> list[str]:
    """Die Tabellen des Registers in der Folge von ``schema.json``: veröffentlichte, dann GeoJSON."""
    return [table.name for table in published(layout, settings)] + [GEOJSON_TABLE]


def test_keine_seite_ausser_spalten_traegt_ein_spaltenschema(
    mini_run: Layout, default_settings: Settings
) -> None:
    pages = sorted(mini_run.site.rglob("*.html"))
    names = {page.name for page in pages}
    # Startseite, Auswertung, Karte und jede Unterseite des Profils sind geprüft
    subpages = {f"{page.name}.html" for page in pages_for(default_settings)}
    assert {"index.html", "details.html", "karte.html", COLUMNS_NAME} | subpages <= names
    assert subpages, "die Mini-Fixture baut keine Unterseite"
    found = {
        page.relative_to(mini_run.site).as_posix(): schema_tables(page.read_text(encoding="utf-8"))
        for page in pages
    }
    assert {name: n for name, n in found.items() if n and name != COLUMNS_NAME} == {}
    assert found[COLUMNS_NAME] == len(_register(mini_run, default_settings))
    details = _details(mini_run)
    assert "<h3>Spaltenschema</h3>" not in details and "<details>\n<summary><code>" not in details


def test_jede_tabelle_des_registers_hat_auf_spalten_ihren_abschnitt(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Je Tabelle ein Abschnitt mit ihrem Namen als Anker, genau einmal, mit den Zeilen von schema.json."""
    schema = json.loads((mini_run.site_data / SCHEMA_NAME).read_text(encoding="utf-8"))["tables"]
    register = _register(mini_run, default_settings)
    assert list(schema) == register
    page = _columns(mini_run)
    ids = _ID.findall(page)
    assert [name for name in register if ids.count(name) != 1] == []
    assert _SECTION.findall(page) == register
    for name, columns in schema.items():
        rows = [tuple(unescape(cell) for cell in row) for row in _ROW.findall(_section(page, name))]
        expected = [(c["column"], c["dtype"], c["description"], c["unit"]) for c in columns]
        assert rows == expected, name


def test_jede_tabelle_der_downloads_verlinkt_ihren_abschnitt(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Jede Zeile einer Tabelle (Parquet, CSV, GeoJSON) verlinkt ``spalten.html#<tabelle>``."""
    details = _details(mini_run)
    start = details.index('<section id="downloads">')
    downloads = details[start : details.index("</section>", start)]
    rows = re.findall(r'<tr><td><a href="data/([^"]+)">.*?</tr>', downloads)
    owner = {
        name: table.name
        for table in published(mini_run, default_settings)
        for name in table.download_names(mini_run)
    } | {GEOJSON_NAME: GEOJSON_TABLE}
    assert set(owner) <= set(rows)
    for name in rows:
        row = re.search(rf'<tr><td><a href="data/{re.escape(name)}">.*?</tr>', downloads)
        assert row is not None
        links = [h for h in _HREF.findall(row.group(0)) if h.startswith(COLUMNS_NAME)]
        assert links == ([f"{COLUMNS_NAME}#{owner[name]}"] if name in owner else []), name
    # Jeder Link der Seite auf spalten.html trifft einen Anker dort
    ids = set(_ID.findall(_columns(mini_run)))
    targets = [
        h.split("#", 1)[1] for h in _HREF.findall(details) if h.startswith(f"{COLUMNS_NAME}#")
    ]
    assert targets and set(targets) <= ids
    # An der Stelle der Überschrift ein Satz mit Link auf die Seite und auf schema.json
    after = downloads[downloads.index("</table>") :]
    sentence = next(line for line in after.splitlines() if f'href="{COLUMNS_NAME}"' in line)
    assert f'href="data/{SCHEMA_NAME}"' in sentence


def test_spalten_hat_kopf_und_fuss_wie_die_unterseiten(
    mini_run: Layout, default_settings: Settings
) -> None:
    page = _columns(mini_run)
    assert page.startswith("<!doctype html>") and '<html lang="de">' in page
    header = page[page.index("<header>") : page.index("</header>")]
    hrefs = _HREF.findall(header)
    assert "index.html" in hrefs and "details.html#downloads" in hrefs
    assert ">Zur Startseite" in header and ">Details" in header
    assert f'href="data/{SCHEMA_NAME}"' in header
    # Der Fuß ist der der Unterseiten; nur der Zeitpunkt ist je Schritt ein anderer
    subpage = mini_run.site / f"{pages_for(default_settings)[0].name}.html"
    footer = _FOOTER.findall(page)
    other = _FOOTER.findall(subpage.read_text(encoding="utf-8"))
    assert len(footer) == len(other) == 1
    assert _GENERATED.sub("", footer[0]) == _GENERATED.sub("", other[0])
    # Kein Skript, kein Dialog: die Seite ist zum Lesen da
    assert "<script" not in page and "<dialog" not in page


def test_spalten_bleibt_unter_ihrem_budget(mini_run: Layout, default_settings: Settings) -> None:
    budget = default_settings.report.columns_budget_bytes
    assert budget == 500_000
    assert page_budgets(default_settings)[COLUMNS_NAME] == budget
    assert within_budget((mini_run.site / COLUMNS_NAME).stat().st_size, budget)


def test_spalten_schreibt_der_schritt_report(mini_run: Layout) -> None:
    """Neben ``details.html`` und ``karte.html``, ohne eigenen Stamp (der hängt an der Startseite)."""
    assert (mini_run.site / COLUMNS_NAME).is_file()
    assert not (mini_run.site / f"{COLUMNS_NAME}.stamp.json").exists()


def test_spalten_escapt_die_beschreibungen(mini_model: ReportModel) -> None:
    first = mini_model.columns[0]
    tainted = replace(first, description='<b>fett</b> & "Zitat"', unit="<i>")
    page = render_columns(replace(mini_model, columns=(tainted, *mini_model.columns[1:])))
    assert "<b>fett</b>" not in page and "&lt;b&gt;fett&lt;/b&gt; &amp;" in page
    assert "<i>" not in page


def test_der_anker_jeder_tabelle_steht_genau_einmal(mini_model: ReportModel) -> None:
    """Die Nachbedingung von ``render_columns``: eine zweite gleiche id ließe den Link danebenzeigen."""
    tables = list(dict.fromkeys(column.table for column in mini_model.columns))
    assert len(tables) > 1
    sections = "".join(f'<section id="{table}"></section>' for table in tables)
    assert anchors_once(mini_model, sections)
    assert not anchors_once(mini_model, sections + f'<p id="{tables[0]}"></p>')
    assert not anchors_once(mini_model, sections.replace(f'id="{tables[0]}"', 'id="x"'))
    # Eine Tabelle mit einem neuen Namen bekommt ihren Abschnitt, ohne dass sonst etwas zählt
    extra = ColumnDoc("probe_tabelle", "a", "Int64", "eine Spalte", "")
    page = render_columns(replace(mini_model, columns=(*mini_model.columns, extra)))
    assert page.count('id="probe_tabelle"') == 1 and anchors_once(mini_model, page)
