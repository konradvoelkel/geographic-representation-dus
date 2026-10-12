"""Der Abschnitt „Gremien" der Berichtsseite: Modell, dritte Kennzahl der Karte, Abschnitt (Option 05)."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

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
    assert figures.names_as_of == dt.date(2026, 10, 11)


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
    from georep.bootstrap import bootstrap
    from georep.pipeline import build_steps, run_pipeline

    root = tmp_path_factory.mktemp("site_bodies")
    layout = Layout(root / "data", root / "cache", mini_root)
    bootstrap(layout)
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
    assert {name for name, _ in legends} == {"rate", "turnout", "bodies"}


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
