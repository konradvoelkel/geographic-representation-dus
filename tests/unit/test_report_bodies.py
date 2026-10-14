"""Der Abschnitt „Gremien" der Berichtsseite: Modell, dritte Kennzahl der Karte, Abschnitt (Option 05)."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import deal
import polars as pl
import pytest

from georep.analysis import bodies as analysis_bodies
from georep.layout import Layout
from georep.prep import bodies as prep_bodies
from georep.report.build import build_site
from georep.report.charts import district_attributes, own_share_label
from georep.report.model import (
    BodyRow,
    ReportModel,
    assignment_rows,
    body_figures,
    body_rows,
    build_report_model,
    with_bodies,
)
from georep.report.render import Visuals, render_report
from georep.settings import Settings


class Parsed(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.rows = 0
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if tag == "tr":
            self.rows += 1


@pytest.fixture(scope="module")
def model(mini_run: Layout, default_settings: Settings) -> ReportModel:
    return build_report_model(
        mini_run,
        default_settings,
        now=dt.datetime(2026, 10, 12, 9, 0, tzinfo=dt.UTC),
        commit="abc1234",
    )


# --- Modell ---------------------------------------------------------------------------------------


def test_every_district_carries_its_bodies(model: ReportModel, mini_run: Layout) -> None:
    frame = pl.read_parquet(mini_run.district_bodies)
    expected = {int(r["wahlkreis_id"]): r for r in frame.iter_rows(named=True)}
    assert len(model.districts) == len(expected)
    for row in model.districts:
        assert row.bodies is not None
        values = expected[row.id]
        assert row.bodies.own == values[analysis_bodies.OWN]
        assert row.bodies.other == values[analysis_bodies.OTHER]
        assert row.bodies.council == values[analysis_bodies.COUNCIL_HITS]
        assert row.bodies.own_share == pytest.approx(values[analysis_bodies.OWN_SHARE])
        assert row.bodies.own_rate == pytest.approx(values[analysis_bodies.OWN_RATE])
        assert row.bodies.city_districts == tuple(values[analysis_bodies.UNITS])
        parts = (
            row.bodies.own,
            row.bodies.other,
            row.bodies.council,
            row.bodies.committee,
            row.bodies.advisory,
            row.bodies.unknown,
        )
        assert sum(parts) == row.hits
    # Die Mini-Fixture hat keinen Wahlbezirk in zwei Stadtbezirken.
    assert [d.id for d in model.districts if d.bodies and d.bodies.shared] == []


def test_a_missing_district_in_the_metrics_is_a_schema_error(
    model: ReportModel, mini_run: Layout
) -> None:
    from georep.errors import SchemaError

    frame = pl.read_parquet(mini_run.district_bodies).head(1)
    with pytest.raises(SchemaError, match="ohne Gremien-Kennzahlen"):
        with_bodies(model.districts, frame)


def test_body_table_names_come_from_the_settings(model: ReportModel) -> None:
    by_code = {r.code: r for r in model.bodies}
    assert by_code["RAT"].name == "Rat" and by_code["RAT"].kind_label == "Rat"
    assert by_code["BV1"].name == "Bezirksvertretung 1"
    assert by_code["BV1"].city_district == 1
    assert by_code["OVA"].name == "Ordnungs- und Verkehrsausschuss"
    # Ein Kürzel ohne gesicherten Namen zeigt das Kürzel (Entscheidung 9).
    assert by_code["KUA"].name == "" and by_code["KUA"].label == "KUA"
    kinds = [r.kind for r in model.bodies]
    assert kinds == sorted(kinds, key=prep_bodies.KINDS.index)  # nach Klasse, dann Dokumente
    for group in (prep_bodies.DISTRICT_BODY, prep_bodies.COMMITTEE):
        counts = [r.documents for r in model.bodies if r.kind == group]
        assert counts == sorted(counts, reverse=True)


def test_body_figures_decompose_the_documents(model: ReportModel, mini_run: Layout) -> None:
    figures = model.body_figures
    assert figures is not None
    assert figures.documents == 200
    assert dict((kind, count) for kind, _, count, _ in figures.by_kind) == {
        prep_bodies.DISTRICT_BODY: 93,
        prep_bodies.COUNCIL: 16,
        prep_bodies.COMMITTEE: 86,
        prep_bodies.ADVISORY: 5,
        prep_bodies.UNKNOWN: 0,
    }
    assert figures.unknown_share == 0.0
    assert sum(share for _, _, _, share in figures.by_kind) == pytest.approx(1.0)
    assert figures.hits == sum(d.hits for d in model.districts)
    assert figures.own_hits == 26 + 22 + 9  # § 3.3 des Plans
    assert figures.without_name > 0  # ungesicherte Kürzel sind sichtbar, nicht erfunden
    # Der Stand der Namen aus dem Profil; seit POA und ACI dazukamen der 2026-10-14 (Punkt 58)
    assert figures.names_as_of == dt.date(2026, 10, 14)


def test_regression_on_three_districts_exists(model: ReportModel) -> None:
    assert model.body_regression is not None
    assert model.body_regression.all.n == 3
    # Mit nur drei Bezirken bleiben nach dem Ausschluss zu wenige übrig.
    assert model.body_regression.without is None


def test_figures_without_documents_stay_at_zero(default_settings: Settings) -> None:
    empty = pl.DataFrame(
        {
            prep_bodies.BODY: [],
            prep_bodies.KIND: [],
            prep_bodies.CITY_DISTRICT: [],
            analysis_bodies.DOCUMENTS: [],
            analysis_bodies.WITH_HITS: [],
            analysis_bodies.LOCAL_SHARE: [],
        },
        schema={
            prep_bodies.BODY: pl.String,
            prep_bodies.KIND: pl.String,
            prep_bodies.CITY_DISTRICT: pl.Int64,
            analysis_bodies.DOCUMENTS: pl.Int64,
            analysis_bodies.WITH_HITS: pl.Int64,
            analysis_bodies.LOCAL_SHARE: pl.Float64,
        },
    )
    rows = body_rows(empty, default_settings.bodies)
    figures = body_figures(rows, (), default_settings.bodies)
    assert rows == () and figures.documents == 0 and figures.unknown_share == 0.0


def test_an_unknown_kind_is_a_violated_precondition(default_settings: Settings) -> None:
    """crosshair, 2026-10-13: eine fremde Klasse flog als ``KeyError`` ohne Fehlertext.

    ``BodyRow.kind`` ist „eines aus prep.bodies.KINDS"; das stand nur im Typkommentar. Jetzt sagt
    die Vorbedingung es, und die Meldung nennt den Aufrufer statt die Zählschleife.
    """
    wrong = BodyRow("XX", "", "gremium", "Gremium", None, 3, 1, None)
    with pytest.raises(deal.PreContractError):
        body_figures((wrong,), (), default_settings.bodies)
    # Mit einer bekannten Klasse geht dieselbe Zeile durch
    right = BodyRow("XX", "", prep_bodies.UNKNOWN, "unbekannt", None, 3, 1, None)
    assert body_figures((right,), (), default_settings.bodies).documents == 3


# --- Karte und Tooltip ----------------------------------------------------------------------------


def test_tooltip_attributes_name_the_own_district_body(model: ReportModel) -> None:
    row = model.districts[0]
    assert row.bodies is not None
    attributes = district_attributes(row)
    assert f'data-own="{row.bodies.own}' in attributes
    assert own_share_label(row.bodies.own_share) in attributes
    # Ohne Gremien fehlt das Attribut, der Tooltip lässt die Zeile weg.
    assert "data-own" not in district_attributes(replace(row, bodies=None))


def test_body_name_with_markup_is_escaped(model: ReportModel) -> None:
    tainted = replace(
        model,
        bodies=(
            BodyRow(
                '<b>&"',
                '"<b>" & Co <a href="https://evil.example/">x</a>',
                "rat",
                "Rat",
                None,
                1,
                1,
                None,
            ),
            *model.bodies[1:],
        ),
    )
    page = render_report(tainted, _visuals(model))
    assert 'href="https://evil.example/"' not in page and "evil.example" in page
    assert "&lt;b&gt;" in page


def _visuals(model: ReportModel) -> Visuals:
    return Visuals(
        map_svg="<svg></svg>",
        scatter_svg="<svg></svg>",
        rate_legend=(),
        turnout_legend=(),
        simplify_m=0.0,
        pois=0,
    )


# --- Abschnitt und gebaute Seite ------------------------------------------------------------------


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory, mini_root: Path, default_settings: Settings
) -> str:
    """Die Seite, wie ``build_site`` sie baut: mit der dritten Kennzahl und ihrer Legende."""
    from georep.bootstrap import bootstrap_from_settings
    from georep.pipeline import build_steps, run_pipeline

    root = tmp_path_factory.mktemp("site_bodies")
    layout = Layout(root / "data", root / "cache", mini_root)
    bootstrap_from_settings(layout, default_settings)
    run_pipeline(build_steps(default_settings, layout), default_settings)
    build_site(
        layout, default_settings, now=dt.datetime(2026, 10, 12, 9, 0, tzinfo=dt.UTC), commit=None
    )
    return layout.site_index.read_text(encoding="utf-8")


def test_the_section_is_on_the_page_with_both_tables(built: str) -> None:
    parsed = Parsed(built)
    assert "gremien" in parsed.ids
    assert {"gremien-bezirke", "gremien-liste", "legend-bodies"} <= set(parsed.ids)
    section = built[
        built.index('<section id="gremien">') : built.index(
            "</section>", built.index('<section id="gremien">')
        )
    ]
    rows = re.findall(r'<tr data-id="(\d+)">', section)
    assert rows == ["1", "10", "38"]  # drei Wahlbezirke der Mini-Fixture
    assert "Bezirksvertretung 1" in section and "Rat" in section
    assert "BV6/108/2023" in section  # das Beispiel der Einleitung


def test_the_map_offers_the_third_metric(built: str) -> None:
    assert '<input type="radio" name="metric" value="bodies">' in built
    assert 'id="legend-bodies"' in built
    paths = re.findall(r'data-class-bodies="(\d+)"', built)
    assert len(paths) == 3 and set(paths) <= {"0", "1", "2"}
    # Genau eine Legende ist beim Laden sichtbar: die der Trefferquote.
    legends = re.findall(r'<div class="legend" id="legend-(\w+)"( hidden)?>', built)
    assert [name for name, hidden in legends if not hidden] == ["rate"]
    # Punkt 46 hat drei Normierungen dazugestellt; die drei Einfaerbungen von vorher bleiben
    assert {"rate", "turnout", "bodies"} <= {name for name, _ in legends}


def test_the_methods_section_explains_the_rule(built: str) -> None:
    methods = built[built.index('<section id="methode">') :]
    assert "Drucksachennummer" in methods and "wahlbezirke_stadtbezirke" in methods


def test_the_new_tables_are_downloads_with_a_schema(built: str) -> None:
    for name in ("wahlbezirke_gremien", "gremien", "wahlbezirke_stadtbezirke"):
        assert f"{name}.parquet" in built and f"{name}.csv" in built
    assert "treffer_eigene_bv" in built and "anteil_eigener_stadtbezirk" in built


# --- Punkt 45: die Tabelle der passenden Ausschüsse hängt am Schalter, nicht nur an der Datei --


def test_the_assignment_table_follows_the_switch_and_the_committees(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Wie der Themenblock: die Datei eines früheren Laufs bleibt liegen, gehört aber nicht auf
    die Seite, wenn der Schalter aus ist oder das Profil keine Ausschüsse kennt."""
    assert assignment_rows(mini_run, default_settings)  # Vorgabe: Schalter an, Ausschüsse da
    off = default_settings.model_copy(
        update={"classify": default_settings.classify.model_copy(update={"enabled": False})}
    )
    assert assignment_rows(mini_run, off) == ()
    without = default_settings.model_copy(
        update={"bodies": default_settings.bodies.model_copy(update={"committees": {}})}
    )
    assert assignment_rows(mini_run, without) == ()


# --- Punkt 58: die beiden Quellen des Gremiums auf der Seite -----------------------------------


def test_the_figures_carry_the_sources_and_the_cross_check(model: ReportModel) -> None:
    """Die Mini-Fixture trägt die Beratungsfolge ihrer 200 Dokumente, und jede Nummer trifft.

    Darum kommen alle 200 Gremien aus der Nummer, keines aus der Folge -- und die Folge bestätigt,
    wo sie eindeutig ist. Die Anteile zerlegen die Dokumente, das ist die Zusicherung.
    """
    figures = model.body_figures
    assert figures is not None
    assert {source for source, _, _, _ in figures.by_source} == set(prep_bodies.SOURCES)
    assert sum(count for _, _, count, _ in figures.by_source) == figures.documents == 200
    assert sum(share for _, _, _, share in figures.by_source) == pytest.approx(1.0)
    assert figures.from_number == 200 and figures.from_consultation == 0
    assert figures.confirmed > 0 and figures.conflicting + figures.ambiguous >= 0
    assert figures.documents_from(prep_bodies.FROM_NOWHERE) == 0
    # Die Labels kommen aus prep.bodies, damit Seite und Schrittzeile dasselbe Wort benutzen
    assert dict((s, label) for s, label, _, _ in figures.by_source) == prep_bodies.SOURCE_LABELS


def test_without_the_file_the_figures_have_no_sources(
    model: ReportModel, default_settings: Settings
) -> None:
    """Ohne ``papers_gremien.parquet`` gibt es die Zahlen nicht, und die Vorlage lässt den Satz weg."""
    assert model.bodies and model.body_figures
    plain = body_figures(model.bodies, model.districts, default_settings.bodies)
    assert plain.by_source == () and plain.from_number == 0
    assert (plain.confirmed, plain.conflicting, plain.ambiguous) == (0, 0, 0)


def test_the_section_names_both_sources_with_their_shares(built: str) -> None:
    section = built[
        built.index('<section id="gremien">') : built.index(
            "</section>", built.index('<section id="gremien">')
        )
    ]
    # ``percent_de`` setzt ein schmales geschütztes Leerzeichen vor das Prozentzeichen
    plain = section.replace("\u202f", " ").replace("\u00a0", " ")
    assert "nennt bei 200 der 200 Dokumente (100,0 %) das Gremium" in plain
    assert "Die zweite Quelle ist die <em>Beratungsfolge</em>" in plain
    assert "0 Dokumente (0,0 %) bekommen ihr Gremium so" in plain
    assert "Wo beide Quellen etwas sagen, bleibt die Nummer" in plain
    assert "sie stimmen in 156 Fällen überein und widersprechen sich in 2" in plain


def test_the_row_without_a_code_says_what_it_is(default_settings: Settings) -> None:
    """Punkt 58: die Sammelzeile heißt „ohne erkanntes Gremium", nicht „ohne Drucksachennummer".

    Sie zählt die Dokumente, für die keine Quelle ein Gremium nennt. In Mönchengladbach haben
    alle davon eine Drucksachennummer **und** eine Beratungsfolge -- die Folge nennt nur mehrere
    Gremien. Und sie ist kein Kürzel ohne Namen: in der Zahl darunter zählt sie nicht mit.
    """
    frame = pl.DataFrame(
        {
            prep_bodies.BODY: ["", "OVA"],
            prep_bodies.KIND: [prep_bodies.UNKNOWN, prep_bodies.COMMITTEE],
            prep_bodies.CITY_DISTRICT: [None, None],
            analysis_bodies.DOCUMENTS: [1275, 10],
            analysis_bodies.WITH_HITS: [0, 5],
            analysis_bodies.LOCAL_SHARE: [None, None],
        },
        schema={
            prep_bodies.BODY: pl.String,
            prep_bodies.KIND: pl.String,
            prep_bodies.CITY_DISTRICT: pl.Int64,
            analysis_bodies.DOCUMENTS: pl.Int64,
            analysis_bodies.WITH_HITS: pl.Int64,
            analysis_bodies.LOCAL_SHARE: pl.Float64,
        },
    )
    rows = body_rows(frame, default_settings.bodies)
    labels = {row.code: row.label for row in rows}
    assert labels[""] == "ohne erkanntes Gremium"
    assert labels["OVA"] == "Ordnungs- und Verkehrsausschuss"
    # Ein Kürzel ohne gesicherten Namen zählt, die Zeile ohne Kürzel nicht
    assert body_figures(rows, (), default_settings.bodies).without_name == 0


def test_an_unknown_source_is_a_violated_precondition(default_settings: Settings) -> None:
    """crosshair, 2026-10-14: eine fremde Quelle flog als ``KeyError`` ohne Fehlertext (Punkt 58).

    ``source_counts`` liefert immer genau die vier Quellen; ein von Hand gebautes ``SourceCounts``
    nicht, und die Beschriftung aus ``prep.bodies.SOURCE_LABELS`` fand dann keinen Eintrag.
    """
    wrong = prep_bodies.SourceCounts((("nummer", 0), ("\x00", 0)), 0, 0, 0)
    with pytest.raises(deal.PreContractError):
        body_figures((), (), default_settings.bodies, wrong)
    right = prep_bodies.SourceCounts(tuple((s, 0) for s in prep_bodies.SOURCES), 0, 0, 0)
    assert body_figures((), (), default_settings.bodies, right).by_source[0][0] == "nummer"


def test_without_a_second_source_the_section_says_nothing_about_it(model: ReportModel) -> None:
    """Review 2026-10-14: der Wächter der Vorlage ist ``has_second_source``, nicht ``by_source``.

    Ein Profil ohne ``[bodies.organizations]`` bekommt vier Nullen in ``by_source`` -- und bekam
    damit einen Absatz „0 Dokumente (0,0 %) bekommen ihr Gremium so". Jetzt fehlt der Absatz, und
    die Zeile „Je Quelle" fehlt auch, weil nur eine Quelle etwas beigetragen hat.
    """
    figures = model.body_figures
    assert figures is not None and figures.has_second_source  # die Fixture hat eine Folge
    alone = replace(
        figures,
        by_source=tuple(
            (source, label, count if source == prep_bodies.FROM_NUMBER else 0, 0.0)
            for source, label, count, _ in figures.by_source
        ),
        confirmed=0,
        conflicting=0,
        ambiguous=0,
    )
    assert not alone.has_second_source and len(alone.sources) == 1
    page = render_report(replace(model, body_figures=alone), _visuals(model))
    assert "Die zweite Quelle ist die <em>Beratungsfolge</em>" not in page
    assert "Je Quelle:" not in page
    # Mit Folge stehen beide da, und die Beschriftungen kommen aus prep.bodies.SOURCE_LABELS
    with_folge = render_report(model, _visuals(model))
    assert "Die zweite Quelle ist die <em>Beratungsfolge</em>" in with_folge
    assert prep_bodies.SOURCE_LABELS[prep_bodies.FROM_NUMBER] in with_folge


def test_an_old_data_root_loses_the_sources_instead_of_the_page(
    tmp_path: Path, mini_run: Layout, default_settings: Settings
) -> None:
    """Review 2026-10-14: ``papers_gremien.parquet`` ohne die Spalten aus Schema 2 ist eine Zeile.

    Vorher las das Modell die Datei ohne Prüfung, und die Vorbedingung von ``source_counts`` flog
    als ``PreContractError`` mitten im Seitenbau -- für eine Datenwurzel, in der der Schritt
    ``bodies`` zuletzt vor Punkt 58 lief. Jetzt fehlen die Quellen im Abschnitt, und der Rest der
    Seite entsteht.
    """
    from georep.io import write_parquet
    from georep.report.model import _source_counts

    old = pl.read_parquet(mini_run.papers_bodies).select(
        prep_bodies.ID, prep_bodies.REFERENCE, prep_bodies.BODY, prep_bodies.KIND
    )
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    layout.processed.mkdir(parents=True, exist_ok=True)
    write_parquet(old, layout.papers_bodies, schema_version=1)
    assert _source_counts(layout) is None
    # Ohne die Datei ebenso, und mit allen Spalten kommen die Zahlen
    assert _source_counts(Layout(tmp_path / "leer", tmp_path / "c", tmp_path / "r")) is None
    counts = _source_counts(mini_run)
    assert counts is not None and counts.documents == 200
