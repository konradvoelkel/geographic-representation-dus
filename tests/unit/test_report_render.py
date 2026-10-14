"""Rendering der Berichtsseite auf der Mini-Fixture: parsebar, vollständig, ohne Fremdressourcen."""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import deal
import pytest
from syrupy.assertion import SnapshotAssertion

from georep.geo import read_canonical_precincts
from georep.layout import Layout
from georep.report.charts import (
    choropleth,
    classify,
    legend,
    party_maps,
    rate_label,
    scatter,
    turnout_label,
)
from georep.report.geometry import SIMPLIFY_M, bounds_of, district_shapes, fit
from georep.report.model import Download, MonthRow, ReportModel, build_report_model
from georep.report.render import Visuals, external_links, kib, render_map, render_report
from georep.report.search import SearchEntry, search_payload
from georep.settings import Settings
from tests.conftest import without_literature

DOWNLOADS = (
    Download(
        "wahlbezirke_auswertung.parquet", "Parquet", 3, 12345, "a" * 64, "Auswertung je Bezirk"
    ),
    Download("wahlbezirke.geojson", "GeoJSON", 3, 2345, "b" * 64, "Flächen der Wahlbezirke"),
    Download("schema.json", "JSON", None, 345, "c" * 64, "Spaltenschema"),
)


class Counter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: dict[str, int] = {}
        self.errors = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags[tag] = self.tags.get(tag, 0) + 1


@pytest.fixture(scope="module")
def model(mini_run: Layout, default_settings: Settings) -> ReportModel:
    return build_report_model(
        mini_run,
        default_settings,
        now=dt.datetime(2026, 10, 11, 18, 30, tzinfo=dt.UTC),
        commit="abc1234",
        downloads=DOWNLOADS,
    )


@pytest.fixture(scope="module")
def visuals(model: ReportModel, mini_run: Layout, default_settings: Settings) -> Visuals:
    precincts = read_canonical_precincts(
        mini_run.precincts_geojson, default_settings.geo.working_crs
    )
    shapes = district_shapes(precincts)
    projection = fit(bounds_of(shapes), 600.0)
    rate = classify({d.id: d.rate for d in model.districts})
    turnout = classify({d.id: d.turnout for d in model.districts})
    assert model.regression is not None  # Standardprofil (Option 07)
    return Visuals(
        map_svg=choropleth(model.districts, shapes, projection, rate, turnout),
        scatter_svg=scatter(model.districts, model.regression),
        rate_legend=legend(rate, rate_label),
        turnout_legend=legend(turnout, turnout_label),
        simplify_m=SIMPLIFY_M,
        pois=0,
        party_maps_svg=party_maps(model.party_cells, shapes, projection, model.parties),
    )


@pytest.fixture(scope="module")
def page(model: ReportModel, visuals: Visuals) -> str:
    return render_report(model, visuals)


def test_page_parses_with_one_heading_and_german_language(page: str) -> None:
    parser = Counter()
    parser.feed(page)
    # Karte, Streudiagramm und (Option 04) die Parteikarten
    assert parser.tags["h1"] == 1 and parser.tags["svg"] == 3 and parser.tags["main"] == 1
    assert page.startswith("<!doctype html>") and '<html lang="de">' in page
    assert page.count('<p lang="en">') == 1
    assert "Erzeugt am 11.10.2026, 18:30 UTC mit georep" in page and "Commit abc1234" in page


def test_every_district_download_and_column_is_on_the_page(page: str, model: ReportModel) -> None:
    for district in model.districts:
        assert district.name in page and f'id="bezirk-{district.id}"' in page
    for download in DOWNLOADS:
        assert f'href="data/{download.name}"' in page and download.sha256 in page
    for column in model.columns:
        assert f"<code>{column.column}</code>" in page
    assert "schulweg" in page  # Fußnote zu versteckten Begriffen
    assert "ohne 1 und 10" not in page  # Mini: keine zweite Regression
    assert "<script src=" not in page and "<link " not in page and "@import" not in page


def test_only_allowed_links_point_outside(page: str) -> None:
    links = external_links(page)
    assert links and all(link.startswith("https://") for link in links)
    assert len(set(links)) >= 8


def test_data_is_escaped(model: ReportModel, visuals: Visuals) -> None:
    first = replace(model.districts[0], name='"<b>" & Co <a href="https://evil.example/">x</a>')
    tainted = replace(model, districts=(first, *model.districts[1:]))
    page = render_report(tainted, visuals)
    assert "<b>" not in page.replace("<b>", "", 0) or "&lt;b&gt;" in page
    assert 'href="https://evil.example/"' not in page and "evil.example" in page


def test_a_foreign_link_in_the_svg_breaks_the_contract(
    model: ReportModel, visuals: Visuals
) -> None:
    bad = replace(visuals, map_svg='<svg><a href="https://evil.example/"></a></svg>')
    with pytest.raises(deal.PostContractError):
        render_report(model, bad)


def test_download_table_is_stable(
    model: ReportModel, visuals: Visuals, snapshot: SnapshotAssertion
) -> None:
    """Der Schnappschuss nimmt das Bedienelement mit (Review 2026-10-13, Befund 13).

    Die Schaltfläche der Vorschau steht vor der Tabelle und gehört zu ihr; endete der Ausschnitt
    am ``<table>``, blieben Beschriftung, ``aria-controls`` und ``aria-expanded`` ungeprüft. Die
    Fixture hat drei Download-Dateien, darum rendert dieser Test mit zwei Vorschauzeilen -- sonst
    gäbe es nichts zu klappen und keine Schaltfläche.
    """
    page = render_report(replace(model, preview_rows=2), visuals)
    cut = r'<p class="more"><button[^>]*aria-controls="downloads-table".*?</table>'
    match = re.search(cut, page, re.S)
    assert match is not None
    assert match.group(0) == snapshot


def _relative_luminance(colour: str) -> float:
    channels = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    first, second = _relative_luminance(a), _relative_luminance(b)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def test_the_accent_colour_reaches_wcag_aa_on_both_grounds_and_modes(page: str) -> None:
    """Punkt 48, Review 2026-10-13: die Links und die Schaltfläche der Vorschau sind 14,4 px groß.

    Normaler Text braucht 4,5:1. Hell lag ``--accent`` bei 4,19:1 auf ``--bg`` -- unter AA, und
    das betraf jeden Link der Seite, nicht nur die Schaltfläche. Der Test rechnet die Farben aus
    dem Rahmen nach, damit die Zahl im Kommentar nicht allein steht.
    """
    blocks = page.split("@media (prefers-color-scheme: dark)")
    assert len(blocks) == 2
    for mode, css in (("hell", blocks[0]), ("dunkel", blocks[1])):
        found = {
            name: re.search(rf"--{name}: (#[0-9a-f]{{6}})", css)
            for name in ("accent", "bg", "surface")
        }
        assert all(found.values()), (mode, found)
        accent = found["accent"].group(1)  # type: ignore[union-attr]
        for ground in ("bg", "surface"):
            colour = found[ground].group(1)  # type: ignore[union-attr]
            ratio = _contrast(accent, colour)
            assert ratio >= 4.5, f"{mode}: --accent {accent} auf --{ground} {colour} = {ratio:.2f}"


def test_kib_formats_kilobytes() -> None:
    assert kib(12345) == "12,3 KB" and kib(0) == "0,0 KB"


def test_map_page_escapes_script_end_and_allows_only_leaflet_and_osm(
    model: ReportModel, visuals: Visuals
) -> None:
    districts = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"wahlkreis_id": 1, "name": "x</script><b>", "klasse": 0},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[6.7, 51.2], [6.8, 51.2], [6.8, 51.3], [6.7, 51.2]]],
                },
            }
        ],
    }
    places = {"type": "FeatureCollection", "features": []}
    page = render_map(model, districts, places, visuals.rate_legend)
    assert "</script><b>" not in page and "\\u003c/script>\\u003cb>" in page
    assert "<!--" not in page.split('type="application/json"', 1)[1].split("</script>", 1)[0]
    assert set(external_links(page)) == {
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
        "https://www.openstreetmap.org/copyright",
    }
    assert page.count("<script") == 4 and "tile.openstreetmap.org" in page


def _optional_sections() -> set[str]:
    """Abschnitte, die an einem Modellteil hängen und ohne ihn fehlen dürfen.

    Die Vorlage sagt es selbst: wer mit ``{% if model.`` beginnt, zeigt sich nur mit seinem Teil
    des Modells (Konvention aus docs/plans/00-synergien.md, § 5.1). So muss diese Zeile nicht je
    Option angefasst werden.
    """
    from importlib import resources

    from georep.report.render import sections

    folder = resources.files("georep.report") / "templates" / "sections"
    optional = set()
    for part in sections():
        source = (folder / part.template.removeprefix("sections/")).read_text(encoding="utf-8")
        if source.lstrip().startswith("{% if model."):
            optional.add(part.name)
    return optional


def test_sections_render_in_numeric_order(page: str) -> None:
    from georep.report.render import sections

    parts = sections()
    numbers = [s.number for s in parts]
    assert numbers == sorted(numbers) and len(set(numbers)) == len(numbers)
    order = [s.name for s in parts]
    # Die vorhandenen Abschnitte in ihrer Reihenfolge; neue Optionen schieben sich dazwischen
    # (docs/plans/00-synergien.md, Paragraf 5.1), darum relativ geprueft, nicht als Praefix.
    fixed = [
        "kernzahlen",
        "karte",
        "zusammenhang",
        "wahlbezirke",
        "begriffe",
        "methode",
        "downloads",
    ]
    assert [name for name in order if name in fixed] == fixed
    # Die gezeigten Abschnitte stehen in Nummernfolge, es gibt keinen weiteren, und fehlen darf
    # nur, wer sich ausdrücklich an einen Modellteil hängt (Option 02: „perioden").
    shown = [s.name for s in parts if f'<section id="{s.name}">' in page]
    positions = [page.index(f'<section id="{name}">') for name in shown]
    assert positions == sorted(positions)
    assert {s.name for s in parts} - set(shown) <= _optional_sections()
    assert page.count("<section ") == len(shown)
    # Die Schnittstelle der Abschnitts-Skripte (Punkt 49: loadJson, forget, offlineNote dazu)
    interface = page.split("window.georep = {", 1)[1].split("};", 1)[0]
    for member in ("select", "showDocuments", "rows", "loadJson", "forget", "offlineNote"):
        assert f"{member}: {member}" in interface, member


def test_every_optional_section_hangs_on_a_model_part() -> None:
    """Ohne Vergleich fehlt „perioden"; das Modell hat den Teil, und die Vorlage nennt ihn."""
    assert "perioden" in _optional_sections()


def test_section_css_and_js_need_a_template_sibling(tmp_path: Path) -> None:
    from georep.errors import SchemaError
    from georep.report.render import sections

    (tmp_path / "15-suche.html.j2").write_text('<section id="suche"></section>\n', encoding="utf-8")
    (tmp_path / "15-suche.css").write_text(".suche {}\n", encoding="utf-8")
    (tmp_path / "15-suche.js").write_text("void 0;\n", encoding="utf-8")
    (tmp_path / "10-kernzahlen.html.j2").write_text("<section></section>\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("ignoriert\n", encoding="utf-8")
    parts = sections(tmp_path)
    assert [(s.number, s.name) for s in parts] == [(10, "kernzahlen"), (15, "suche")]
    assert parts[1].css.startswith(".suche") and parts[1].js.startswith("void")
    assert parts[0].css == "" and parts[0].template == "sections/10-kernzahlen.html.j2"
    (tmp_path / "99-fehlt.js").write_text("", encoding="utf-8")
    with pytest.raises(SchemaError, match="ohne Vorlage"):
        sections(tmp_path)
    (tmp_path / "99-fehlt.js").unlink()
    (tmp_path / "15-doppelt.html.j2").write_text("<section></section>\n", encoding="utf-8")
    with pytest.raises(deal.PostContractError):
        sections(tmp_path)


def test_extra_classes_become_data_attributes_for_the_switch(
    model: ReportModel, visuals: Visuals
) -> None:
    import re as _re

    assert 'data-class-rate="' in visuals.map_svg and "data-class-bodies" not in visuals.map_svg
    from shapely.geometry import box

    from georep.report.charts import Classification, choropleth
    from georep.report.geometry import bounds_of, fit

    shapes = {d.id: box(0, 0, 10, 10) for d in model.districts}
    projection = fit(bounds_of(shapes), 100.0)
    one = Classification((), {d.id: 0 for d in model.districts}, 1)
    svg = choropleth(
        model.districts, shapes, projection, one, one, extra_classes={"bodies": one, "rate": one}
    )
    assert len(_re.findall(r'data-class-bodies="0"', svg)) == len(model.districts)
    assert svg.count('data-class-rate="') == len(model.districts)


def _search_block(page: str) -> str:
    match = re.search(
        r'<script id="suche-daten" type="application/json">(.*?)</script>', page, re.S
    )
    assert match is not None
    return match.group(1)


def _search_json(page: str) -> object:
    """Der Block ist gültiges JSON, wie ``_json_for_script`` das ``<`` auch maskiert.

    ``json.loads`` löst beide Schreibweisen auf, das alte ``<\\/`` ebenso wie ``\\u003c``; der Test
    kennt die Maskierung darum nicht und bleibt richtig, wenn sie sich ändert.
    """
    return json.loads(_search_block(page))


def test_search_data_is_a_readable_json_block(page: str, model: ReportModel) -> None:
    assert _search_json(page) == json.loads(json.dumps(search_payload(model.search)))
    assert page.count("<script") == 3  # Basis-Skript, Abschnitts-Skripte, der JSON-Block


def test_a_term_that_would_end_the_script_is_escaped(model: ReportModel, visuals: Visuals) -> None:
    tainted = replace(model, search=(SearchEntry("x</script><b>", (1,), 0, "s"),))
    page = render_report(tainted, visuals)
    # Was zählt, ist nicht die Schreibweise der Maskierung, sondern dass im Block nichts steht,
    # was der HTML-Tokenizer für das Ende des Skripts halten kann; der Begriff kommt heil zurück.
    assert "</script" not in _search_block(page).lower()
    assert "</script><b>" not in page
    assert _search_json(page) == json.loads(json.dumps(search_payload(tainted.search)))


def test_the_search_field_is_a_combobox_with_a_label(page: str, model: ReportModel) -> None:
    assert '<section id="suche">' in page and "Straße oder Ort" in page
    assert 'role="combobox"' in page and 'aria-autocomplete="list"' in page
    assert 'aria-expanded="false"' in page and 'role="listbox"' in page
    for match in re.finditer(r'aria-controls="([^"]+)"', page):
        assert f'id="{match.group(1)}"' in page
    assert '<label for="suche-feld">' in page and 'id="suche-feld"' in page
    assert f"{len(model.search)}" in page  # „Durchsucht n Straßen, Orte und Wahlbezirke"
    assert 'role="option"' not in page  # die Liste füllt erst das JavaScript


def test_a_model_without_search_entries_has_no_search_section(
    model: ReportModel, visuals: Visuals
) -> None:
    page = render_report(replace(model, search=()), visuals)
    assert '<section id="suche">' not in page and 'id="suche-daten"' not in page


# --- Option 06: Abschnitt „Was ändert die Gewichtung?" ------------------------------------------


def test_the_weighting_section_has_one_row_per_variant(page: str, model: ReportModel) -> None:
    assert model.sensitivity is not None
    section = re.search(r'<section id="gewichtung">.*?</section>', page, re.S)
    assert section is not None
    body = re.search(r"<tbody>(.*?)</tbody>", section.group(0), re.S)
    assert body is not None
    assert body.group(1).count("<tr") == len(model.sensitivity.rows)
    for row in model.sensitivity.rows:
        label = f"Thema {row.topic}" if row.topic is not None else row.label
        assert label in section.group(0)
    assert "Thema 0" in section.group(0) and "ohne Gewichtung" in section.group(0)


def test_the_weighting_section_shows_a_dash_where_there_is_no_regression(
    page: str, model: ReportModel
) -> None:
    """Drei Wahlbezirke: keine zweite Regression, also keine Spaltengruppe „ohne 1 und 10"."""
    assert model.sensitivity is not None and not model.sensitivity.has_without
    section = re.search(r'<section id="gewichtung">.*?</section>', page, re.S)
    assert section is not None and "ohne 1 und 10" not in section.group(0)
    flat = [row for row in model.sensitivity.rows if row.pair is None or row.rho is None]
    if flat:
        assert "—" in section.group(0)
    # Die Kopfzeile hat so viele sortierbare Spalten wie jede Zeile Zellen.
    header = re.search(r"<thead>.*?</thead>", section.group(0), re.S)
    assert header is not None and header.group(0).count('data-sort="num"') == 8  # Summe, 6, rho


def test_the_english_paragraph_counts_the_weightings(page: str, model: ReportModel) -> None:
    assert model.sensitivity is not None
    expected = (
        f"Under {model.sensitivity.significant_all} of {len(model.sensitivity.rows)} "
        "weightings of the same documents, the unweighted count included,"
    )
    assert expected in page
    # Der Nenner zählt die Einheitszeile mit, darum heißt sie nicht „alternative".
    assert "alternative weightings" not in page


def test_the_weighting_section_adds_no_external_link(page: str) -> None:
    section = re.search(r'<section id="gewichtung">.*?</section>', page, re.S)
    assert section is not None and external_links(section.group(0)) == []


# --- Option 03: Kontrollvariablen und abgeleitete Daten ------------------------------------------


def test_the_two_new_sections_render_with_their_numbers(page: str, model: ReportModel) -> None:
    controls, derived = model.controls, model.derived
    assert controls is not None and derived is not None
    assert '<section id="kontrollvariablen">' in page
    assert '<section id="abgeleitete-daten">' in page
    assert "<h2>Kontrollvariablen</h2>" in page and "<h2>Abgeleitete Daten</h2>" in page
    for m in controls.models:
        assert f"Modell {m.name}" in page
    assert controls.verdict in page
    assert controls.units_label in page and derived.attribution in page
    assert f'href="{derived.url}"' in page and derived.license in page
    for variable in derived.variables:
        assert f"<code>{variable.name}</code>" in page and variable.label in page
    # Die Mini-Fixture hat n = 3: der Hinweis auf nicht geschätzte Modelle steht da
    assert "Nicht geschätzt" in page and "B (alle)" in page
    assert "Datenlizenz" in page and "31.12.2021" in page


def test_the_page_without_context_data_has_neither_section(
    model: ReportModel, visuals: Visuals
) -> None:
    plain = render_report(replace(model, controls=None, derived=None), visuals)
    assert "kontrollvariablen" not in plain and "abgeleitete-daten" not in plain
    assert "Kontrollvariablen abgeleitet aus" not in plain  # der Satz im Fuß fehlt auch
    assert plain.startswith("<!doctype html>")


def test_the_partial_plots_appear_with_their_captions(model: ReportModel, visuals: Visuals) -> None:
    plots = [("Sozialer Handlungsbedarf (Steigung -9,91)", '<svg class="avp"></svg>')]
    page = render_report(model, replace(visuals, partial_svgs=plots))
    assert "Beitrag jedes Terms" in page
    assert "Sozialer Handlungsbedarf (Steigung −9,91)".replace("−", "-") in page
    assert '<svg class="avp"></svg>' in page and "<figcaption>" in page


def test_the_dataset_link_of_the_settings_is_allowed(page: str, model: ReportModel) -> None:
    """Die Datensatzseite steht nicht in ALLOWED_LINKS, sondern kommt aus den Settings."""
    from georep.report.render import ALLOWED_LINKS, model_links

    assert model.derived is not None
    assert model.derived.url not in ALLOWED_LINKS
    assert model.derived.url in model_links(model)
    assert set(external_links(page)) <= ALLOWED_LINKS | model_links(model)


def test_the_method_section_mentions_the_control_variables(page: str, model: ReportModel) -> None:
    """00-synergien.md § 5.1: jede Option hängt ihren Absatz ans Ende von `60-methode`."""
    assert model.derived is not None
    method = page[page.index('<section id="methode">') : page.index('<section id="abgeleitete')]
    assert "Die Kontrollvariablen sind Fremddaten" in method
    assert model.derived.units_label in method and "Datenstand" in method


# --- Option 04: der Abschnitt „Urheber und Parteien" -----------------------------------------------


def test_the_party_section_has_the_maps_both_tables_and_every_cell(
    page: str, model: ReportModel
) -> None:
    assert '<section id="parteien">' in page
    assert (
        page.index('id="zusammenhang"')
        < page.index('id="parteien"')
        < page.index('id="wahlbezirke"')
    )
    assert page.count('class="panel"') == len(model.parties)
    assert page.count('<use href="#pm-') == len(model.parties) * len(model.districts)
    assert page.count('<path id="pm-') == len(model.districts)  # die Pfade nur einmal
    # Je Wahlbezirk eine Zeile mit einer Zelle je Partei
    # Punkt 46: die Zellen tragen die q-Klasse ihrer Stufe (im Rahmen als Tönung definiert), weil
    # dieselbe Radiogruppe Karten und Zellen umschaltet und eine Skala trägt, nicht zwei.
    cells = sum(page.count(f'class="num q{k}"') for k in range(5))
    assert cells == len(model.districts) * len(model.parties) == len(model.party_cells)
    for party in model.parties:
        assert f">{party.label}</th>" in page  # Parteitabelle nennt den vollen Namen
        assert f'title="{party.label}">{party.short}</th>' in page  # Bezirkstabelle das Kürzel
    assert "Bonferroni" in page and "nicht angetreten" not in page.split('id="parteien"')[0]


def test_the_section_states_the_coverage_and_the_method_names_its_limits(
    page: str, model: ReportModel
) -> None:
    figures = model.originator_figures
    assert figures is not None
    assert f"{figures.verwaltung} Vorlagen der Verwaltung" in page.replace("\u202f", "")
    # Punkt 59: der Satz zählt die Quellen und nennt keine Beispiele einer einzelnen Stadt
    plain = page.replace(" ", "")
    for label, count in figures.sources:
        assert f"{count} {label}" in plain
    assert "anfrage cdu-fraktion vom 28. Juli 2023" not in page
    assert "Zum Urheber:" in page  # der Absatz in „Methode und Grenzen"
    assert page.index('id="methode"') < page.index("Zum Urheber:")
    assert "nicht angetreten" in page  # die Grenze steht im Methodentext


def test_the_section_disappears_without_the_parties_step(
    model: ReportModel, visuals: Visuals
) -> None:
    """Ohne Modellteil kein Abschnitt: die Vorlage steht in {% if model.parties %}."""
    empty = replace(model, parties=(), party_cells=(), originators=(), originator_figures=None)
    page = render_report(empty, replace(visuals, party_maps_svg=""))
    assert '<section id="parteien">' not in page and "Urheber und Parteien" not in page
    assert '<section id="wahlbezirke">' in page  # der Rest der Seite bleibt
    assert "Zum Urheber:" not in page


# --- Option 07: Monitoring der laufenden Wahlperiode ------------------------------------------

MONTHS = (
    MonthRow(dt.date(2025, 10, 1), 12, 10, 5),
    MonthRow(dt.date(2025, 11, 1), 8, 8, 3),
    MonthRow(None, 1, 0, 0),
)


@pytest.fixture(scope="module")
def open_page(model: ReportModel, visuals: Visuals) -> str:
    """Die Seite eines Profils mit laufender Periode: ohne Regression, mit Monatsreihe und Link."""
    from georep.report.charts import bars

    stand = replace(
        model.stand,
        period_end=None,
        papers_fetched=dt.date(2026, 10, 11),
        pdfs_fetched=dt.date(2026, 10, 12),
        newest_document=dt.date(2025, 11, 2),
    )
    open_model = replace(
        model, stand=stand, regression=None, timeline=MONTHS, monitoring_url="2025/"
    )
    return render_report(open_model, replace(visuals, scatter_svg=None, bars_svg=bars(MONTHS)))


def test_the_month_section_has_a_row_per_month_and_two_bars(open_page: str) -> None:
    parser = Counter()
    parser.feed(open_page)
    # Die Zahl der SVGs auf der Seite wächst mit jeder Option; geprüft wird, dass genau ein
    # Balkendiagramm da ist und kein Streudiagramm (Option 07).
    assert parser.tags["h1"] == 1
    assert open_page.count('class="bars"') == 1 and 'class="scatter"' not in open_page
    assert '<section id="monate">' in open_page
    import re as _re

    body = _re.search(r'<table id="monate-tabelle".*?<tbody>(.*?)</tbody>', open_page, _re.S)
    assert body is not None and body.group(1).count("<tr>") == len(MONTHS)
    assert "Oktober 2025" in open_page and "November 2025" in open_page
    assert "ohne Datum" in open_page  # die Zeile ohne Monat
    assert open_page.count('class="bar bar-documents"') == 2  # nur die datierten Monate
    # Ohne den Literaturabschnitt: der zitiert fremde Arbeiten und darf Monatsnamen nennen
    assert "Dezember" not in without_literature(open_page)


def test_without_regression_the_page_drops_scatter_and_the_turnout_switch(
    open_page: str, page: str
) -> None:
    assert '<section id="zusammenhang">' not in open_page
    assert "Tabelle 5 der Arbeit" not in open_page
    assert 'class="scatter"' not in open_page
    assert 'value="turnout"' not in open_page and 'id="legend-turnout"' not in open_page
    assert 'id="legend-rate"' in open_page  # die Trefferquote färbt die Karte weiter
    assert "no regression" in open_page  # englische Kurzfassung sagt, warum
    # Kopf: offenes Ende, Abrufdaten, neuestes Dokument, Dokumente ohne Text
    assert "heute (laufende Wahlperiode)" in open_page
    assert "Metadaten abgerufen am 11.10.2026, PDFs am 12.10.2026" in open_page
    assert "neuestes Dokument vom 02.11.2025" in open_page
    assert "laufende Wahlperiode: die Trefferquote misst die Dokumente seit dem" in open_page
    # Der Methodenabsatz verspricht keine Regression, die es auf dieser Seite nicht gibt
    assert "lineare Regression setzt sie zur Wahlbeteiligung" not in open_page
    assert "lineare Regression setzt sie zur Wahlbeteiligung" in page


def test_the_monitoring_link_is_relative_and_only_there_when_set(
    open_page: str, model: ReportModel, visuals: Visuals
) -> None:
    assert '<section id="laufend">' in open_page and 'href="2025/"' in open_page
    assert "2025/" not in external_links(open_page)
    # Leer heißt: kein Abschnitt. Die Seite des Standardprofils trägt ihn seit Punkt 56, weil
    # Düsseldorf eine laufende Periode fortschreibt; eine Stadt ohne sie hat den Schlüssel leer.
    without = render_report(replace(model, monitoring_url=""), visuals)
    assert '<section id="laufend">' not in without and 'href="2025/"' not in without


def test_the_hit_tile_relates_to_the_documents_with_text(
    model: ReportModel, visuals: Visuals
) -> None:
    """Review 2026-10-14: wo Dokumente ohne Text liegen, nennt die Kachel beide Anteile.

    Mönchengladbach hat 489 Dokumente mit Treffer aus 2 895, aber nur 650 mit Text: „16,9 % aller
    Dokumente" allein ist eine Aussage über das Ratsinformationssystem, nicht über die Stadt. Wo
    jedes Dokument Text hat, wäre die zweite Zahl dieselbe und bleibt darum weg.
    """
    figures = replace(model.figures, documents=200, documents_with_text=50, documents_hit=40)
    page = render_report(replace(model, figures=figures), visuals)
    assert "20,0\u202f% aller Dokumente, 80,0\u202f% der 50 mit Text" in page
    full = render_report(replace(model, figures=replace(figures, documents_with_text=200)), visuals)
    assert "mit Text" not in full.split('<div class="label">Dokumente mit Treffer</div>')[1][:300]


def test_a_subpage_links_back_to_the_main_period(model: ReportModel, visuals: Visuals) -> None:
    """Review 2026-10-14: eine Periodenseite liegt unter der Stadt und braucht einen Rückweg.

    Der Link ist relativ (``../``) und taucht darum nicht unter den externen Links auf; die
    Hauptseite hat ihn nicht, denn sie *ist* die Wurzel ihrer Stadt.
    """
    page = render_report(replace(model, parent_url="../"), visuals)
    assert (
        '<p class="meta" data-parent="1"><a href="../">Zur Hauptperiode Düsseldorfs</a></p>' in page
    )
    assert "../" not in external_links(page)
    assert 'data-parent="1"' not in render_report(replace(model, parent_url=""), visuals)


def test_the_month_column_sorts_by_number_not_by_name(open_page: str) -> None:
    """Nach Text sortiert stünde April vor Oktober; der Wert ist Jahr mal zwölf plus Monat."""
    import re as _re

    head = _re.search(r'<table id="monate-tabelle".*?</thead>', open_page, _re.S)
    assert head is not None and '<th scope="col" data-sort="num">Monat</th>' in head.group(0)
    values = _re.findall(
        r'<td data-value="(\d+)">(?:[A-ZÄÖÜ][a-zä-ü]+ \d{4}|ohne Datum)</td>', open_page
    )
    assert [int(v) for v in values] == [2025 * 12 + 10, 2025 * 12 + 11, 999999]


@pytest.mark.parametrize(
    ("missing", "expected"), [(1, "ein Dokument ohne Text"), (7, "7 Dokumente ohne Text")]
)
def test_documents_without_text_appear_in_the_head_and_the_tile(
    model: ReportModel, visuals: Visuals, missing: int, expected: str
) -> None:
    """Zwischen Abruf und Extraktion hat die laufende Periode Dokumente ohne Text."""
    figures = replace(model.figures, documents_with_text=model.figures.documents - missing)
    page = render_report(replace(model, figures=figures), visuals)
    assert expected in page  # Datenstand im Kopf
    assert f"mit Text, {missing} ohne</div>" in page  # Kachel Ratsdokumente
    # Ohne fehlende Texte sagt die Seite nichts dazu (Mini-Fixture: jedes Paper hat Text)
    whole = render_report(model, visuals)
    assert "ohne Text" not in whole and "mit Text, " not in whole
