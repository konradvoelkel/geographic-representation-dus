"""Datenmodell der Berichtsseite auf der Mini-Fixture: Zahlen gegen Polars nachgerechnet."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl
import pytest
from shapely.geometry import box

from georep.analysis.periods import compare_periods
from georep.errors import EmptyResultError, MissingInputError, SchemaError
from georep.geo import Precinct
from georep.io import write_parquet
from georep.layout import Layout
from georep.report.model import (
    NARROW_NBSP,
    TOP_TERMS,
    ColumnDoc,
    ControlModel,
    ControlTerm,
    ReportModel,
    _verdict,
    build_report_model,
    column_docs,
    district_names,
    district_rows,
    format_de,
    percent_de,
    period_comparison,
    stamp_written,
    term_counts,
    top_terms_city,
)
from georep.report.search import canonical_term
from georep.report.tables import GEOJSON_COLUMNS, TABLES, PublishedTable, published
from georep.settings import ContextVariable, Settings, load_settings

NOW = dt.datetime(2026, 10, 11, 20, 0, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def model(mini_run: Layout, default_settings: Settings) -> ReportModel:
    return build_report_model(mini_run, default_settings, now=NOW, commit="abc1234")


def test_key_figures_match_the_parquet_files(model: ReportModel, mini_run: Layout) -> None:
    results = pl.read_parquet(mini_run.results)
    figures = model.figures
    assert (figures.districts, figures.precincts) == (3, 22)
    assert (figures.documents, figures.documents_with_text) == (200, 200)
    assert (
        figures.terms == pl.read_parquet(mini_run.dictionary)["suchbegriffe"].explode().n_unique()
    )
    assert figures.documents_hit == results["paper_ids"].explode().n_unique()
    assert figures.rate_median == pytest.approx(results["trefferquote"].median())
    assert figures.rate_min == pytest.approx(results["trefferquote"].min())
    assert figures.rate_max == pytest.approx(results["trefferquote"].max())
    assert figures.turnout_median == pytest.approx(results["wahlbeteiligung"].median())
    assert model.generated_at == NOW and model.commit == "abc1234" and model.version
    assert model.working_crs == "EPSG:25832"


def test_district_rows_match_the_results(model: ReportModel, mini_run: Layout) -> None:
    results = pl.read_parquet(mini_run.results).sort("wahlkreis_id")
    dictionary = pl.read_parquet(mini_run.dictionary).sort("wahlkreis_id")
    assert [d.id for d in model.districts] == [1, 10, 38]
    assert [d.name for d in model.districts] == [
        "Altstadt, Carlstadt, Hofgarten",
        "Flingern Süd",
        "Hassels, Paulsmühle",
    ]
    for district, row, terms in zip(
        model.districts, results.iter_rows(named=True), dictionary["suchbegriffe"], strict=True
    ):
        assert district.hits == row["anzahl_treffer"]
        assert district.eligible == row["Wahlberechtigte_insgesamt"]
        assert district.voters == row["Waehler"]
        assert district.rate == pytest.approx(row["trefferquote"])
        assert district.turnout == pytest.approx(row["wahlbeteiligung"])
        assert district.terms_total == len(terms)
        assert district.terms_without_hits + len(district.terms) <= district.terms_total
        assert district.top_terms == district.terms[:TOP_TERMS]
        assert all(t.hits > 0 and district.id in t.districts for t in district.terms)
        assert all(t.term not in model.hidden_terms for t in district.terms)


def test_hidden_terms_stay_hidden_but_counted(
    model: ReportModel, mini_run: Layout, default_settings: Settings
) -> None:
    assert model.hidden_terms == ("schulweg",)  # kommt in den drei Mini-Bezirken nicht vor
    results = pl.read_parquet(mini_run.results)
    counts = term_counts(pl.read_parquet(mini_run.dictionary), pl.read_parquet(mini_run.index))
    names = {d.id: d.name for d in model.districts}
    strongest = model.districts[0].top_terms[0].term
    rows = district_rows(results, counts, names, hidden=(strongest,))
    first, before = rows[0], model.districts[0]
    assert strongest not in [t.term for t in first.terms]
    assert first.terms_total == before.terms_total  # zählt weiter
    assert len(first.terms) == len(before.terms) - 1
    assert first.hits == before.hits  # die Treffer der Auswertung ändern sich nicht
    assert strongest not in [t.term for t in top_terms_city(counts, hidden=(strongest,))]
    assert strongest in [t.term for t in top_terms_city(counts, hidden=())]


def test_regression_on_three_districts_has_no_outlier_variant(model: ReportModel) -> None:
    assert model.regression is not None  # Standardprofil: Regression vorhanden (Option 07)
    assert model.regression.all.n == 3
    assert model.regression.excluded == (1, 10)
    assert model.regression.without is None


def test_data_stand_comes_from_settings_and_stamps(model: ReportModel) -> None:
    assert model.stand.election == dt.date(2025, 9, 14)
    assert model.stand.period_start == dt.date(2020, 9, 13)
    # bootstrap kopiert die Referenz; die Netzschritte liefen nie, also kein Abrufdatum
    assert model.stand.streets_fetched is None and model.stand.pois_fetched is None


def test_column_docs_cover_every_published_column(model: ReportModel, mini_run: Layout) -> None:
    tables = published(mini_run)
    documented = {(d.table, d.column) for d in model.columns}
    for table in tables:
        for column in pl.read_parquet_schema(table.path(mini_run)):
            assert (table.name, column) in documented
    assert all(d.description for d in model.columns)
    assert {d.table for d in model.columns} == {t.name for t in tables} | {"wahlbezirke"}
    assert (
        ColumnDoc("wahlbezirke", "name", "GeoJSON-Eigenschaft", *GEOJSON_COLUMNS["name"])
        in model.columns
    )
    assert len({t.name for t in TABLES}) == len(TABLES)


def test_column_docs_refuse_mismatches(
    mini_run: Layout, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    voters = next(t for t in TABLES if t.name == "wahlbezirke_waehler")
    results = next(t for t in TABLES if t.name == "wahlbezirke_auswertung")
    wrong_path = PublishedTable(voters.name, lambda layout: layout.results, "", voters.columns)
    monkeypatch.setattr("georep.report.model.published", lambda layout, settings=None: [wrong_path])
    with pytest.raises(SchemaError, match="ohne Beschreibung"):
        column_docs(mini_run, default_settings)
    too_many = PublishedTable(results.name, lambda layout: layout.voters, "", results.columns)
    monkeypatch.setattr("georep.report.model.published", lambda layout, settings=None: [too_many])
    with pytest.raises(SchemaError, match="Beschreibung ohne Spalte"):
        column_docs(mini_run, default_settings)


def test_optional_tables_are_published_only_when_their_file_exists(mini_run: Layout) -> None:
    missing = PublishedTable(
        "fehlt", lambda layout: layout.processed / "x.parquet", "", {}, optional=True
    )
    present = PublishedTable("da", lambda layout: layout.voters, "", {}, optional=True)
    import georep.report.tables as tables

    original = list(tables.TABLES)
    tables.TABLES[:] = [*original, missing, present]
    try:
        names = [t.name for t in published(mini_run)]
    finally:
        tables.TABLES[:] = original
    assert "da" in names and "fehlt" not in names


def _precinct(precinct_id: str, district: int, name: str) -> Precinct:
    return Precinct(precinct_id, district, name, box(0, 0, 1, 1))


def test_district_names_require_one_name_per_district() -> None:
    assert district_names([_precinct("101", 1, "A"), _precinct("102", 1, "A")]) == {1: "A"}
    with pytest.raises(SchemaError, match="zwei Namen"):
        district_names([_precinct("101", 1, "A"), _precinct("102", 1, "B")])


def test_term_counts_join_dictionary_and_index() -> None:
    dictionary = pl.DataFrame(
        {"wahlkreis_id": [1, 2], "suchbegriffe": [["allee", "weg"], ["allee"]]}
    )
    index = pl.DataFrame(
        {"suchbegriffe": ["allee"], "paper_ids": [["p1", "p2"]], "anzahl_treffer": [2]}
    )
    counts = term_counts(dictionary, index)
    assert counts.rows() == [(1, "allee", 2, [1, 2]), (1, "weg", 0, [1]), (2, "allee", 2, [1, 2])]
    top = top_terms_city(counts, hidden=())
    assert [(t.term, t.hits, t.districts) for t in top] == [("allee", 2, (1, 2))]
    assert top_terms_city(counts, hidden=("allee",)) == ()


def test_district_rows_need_a_name_for_every_district(default_settings: Settings) -> None:
    results = pl.DataFrame(
        {
            "wahlkreis_id": [1],
            "anzahl_treffer": [2],
            "Wahlberechtigte_insgesamt": [100],
            "Waehler": [50],
            "wahlbeteiligung": [0.5],
            "trefferquote": [0.02],
        }
    )
    counts = pl.DataFrame(
        {"wahlkreis_id": [1], "suchbegriffe": ["allee"], "anzahl_treffer": [2], "districts": [[1]]}
    )
    rows = district_rows(results, counts, {1: "Eins"}, hidden=())
    assert rows[0].name == "Eins" and rows[0].top_terms[0].term == "allee"
    with pytest.raises(SchemaError, match="ohne Geometrie"):
        district_rows(results, counts, {2: "Zwei"}, hidden=())


def test_stamp_written_reads_the_date_or_nothing(tmp_path: Path) -> None:
    output = tmp_path / "x.json"
    assert stamp_written(output) is None
    stamp = tmp_path / "x.json.stamp.json"
    stamp.write_text("kaputt", encoding="utf-8")
    assert stamp_written(output) is None
    stamp.write_text(json.dumps({"written": "2026-10-11T18:30:00+00:00"}), encoding="utf-8")
    assert stamp_written(output) == dt.date(2026, 10, 11)
    stamp.write_text(json.dumps({"code": "0.9.0"}), encoding="utf-8")
    assert stamp_written(output) is None


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (1234567.891, 1, f"1{NARROW_NBSP}234{NARROW_NBSP}567,9"),
        (0.0, 0, "0"),
        (-0.04, 1, "0,0"),
        (-1234, 0, f"-1{NARROW_NBSP}234"),
        (999, 0, "999"),
        (0.16125, 4, "0,1613"),
        (19108, 0, f"19{NARROW_NBSP}108"),
    ],
)
def test_format_de_examples(value: float, decimals: int, expected: str) -> None:
    assert format_de(value, decimals) == expected


def test_percent_de_uses_a_narrow_space_before_the_sign() -> None:
    assert percent_de(0.531127) == f"53,1{NARROW_NBSP}%"
    assert percent_de(1.0, 0) == f"100{NARROW_NBSP}%"


def test_search_entries_are_part_of_the_model(model: ReportModel, mini_run: Layout) -> None:
    dictionary = pl.read_parquet(mini_run.dictionary)
    terms = set(dictionary["suchbegriffe"].explode().to_list()) - {"schulweg"}
    canonical = {t if canonical_term(t) not in terms else canonical_term(t) for t in terms}
    assert len(model.search) == len(canonical) + 3  # drei Wahlbezirksnamen dazu
    names = [e.term for e in model.search if e.kind == "w"]
    assert names == [d.name for d in sorted(model.districts, key=lambda d: d.name)]
    adler = next(e for e in model.search if e.term == "adlerstraße")
    assert "adlerstr." in terms and adler.kind == "s" and adler.districts == (1,)
    index = pl.read_parquet(mini_run.index).filter(
        pl.col("suchbegriffe").is_in(pl.Series(["adlerstraße", "adlerstr."]).implode())
    )
    both = set(index["paper_ids"].explode().drop_nulls().to_list())
    assert adler.documents == len(both)


# --- Option 06: Sensitivitätstabelle und Themen -------------------------------------------------


def test_the_column_names_of_the_topic_table_match_the_topics_module() -> None:
    """``report/model.py`` darf ``analysis/topics.py`` nicht importieren (sklearn), aber muss passen."""
    from georep.analysis import topics as topics_module
    from georep.report import model as report_model

    assert (report_model.TOPIC, report_model.WORDS, report_model.DOCUMENTS) == (
        topics_module.TOPIC,
        topics_module.WORDS,
        topics_module.DOCUMENTS,
    )


def test_sensitivity_has_one_row_per_variant_in_the_page_order(
    model: ReportModel, mini_run: Layout
) -> None:
    assert model.sensitivity is not None
    rows = model.sensitivity.rows
    names = [row.name for row in rows]
    weighted = pl.read_parquet(mini_run.weighted)
    assert set(names) == set(weighted.get_column("variante").unique().to_list())
    assert names[:3] == ["einheit", "bezirke", "idf"]
    assert names[3:5] == ["antraege_halb", "nur_vorlagen"]  # Reihenfolge der Settings
    assert names[5] == "kombiniert"
    topics = [row.topic for row in rows if row.topic is not None]
    assert topics == sorted(topics) and names[6:] == [f"thema_{i:02d}" for i in topics]
    assert all(row.label and row.description for row in rows if row.topic is None)


def test_sensitivity_numbers_are_the_regression_of_the_long_table(
    model: ReportModel, mini_run: Layout
) -> None:
    from georep.analysis.regression import regress

    assert model.sensitivity is not None
    results = pl.read_parquet(mini_run.results)
    weighted = pl.read_parquet(mini_run.weighted)
    for row in model.sensitivity.rows:
        frame = weighted.filter(pl.col("variante") == row.name).join(
            results.select("wahlkreis_id", "wahlbeteiligung", "trefferquote"), on="wahlkreis_id"
        )
        assert row.total == pytest.approx(frame.get_column("anzahl_treffer_gewichtet").sum())
        if row.pair is None:
            assert frame.get_column("trefferquote_gewichtet").n_unique() < 2
            continue
        expected = regress(frame, x="trefferquote_gewichtet")
        assert (row.pair.all.n, row.pair.all.slope, row.pair.all.p) == (
            expected.n,
            expected.slope,
            expected.p,
        )


def test_the_unweighted_row_carries_the_numbers_of_table_five(model: ReportModel) -> None:
    assert model.sensitivity is not None
    unit = model.sensitivity.rows[0]
    assert unit.name == "einheit" and unit.pair is not None
    assert unit.pair.all == model.regression.all  # dieselbe Regression wie Tabelle 5
    assert unit.rho == 1.0  # dieselbe Reihenfolge der Wahlbezirke


def test_three_districts_leave_no_room_for_the_second_regression(model: ReportModel) -> None:
    assert model.sensitivity is not None
    assert model.sensitivity.excluded == (1, 10)
    assert model.sensitivity.has_without is False
    assert all(row.pair is None or row.pair.without is None for row in model.sensitivity.rows)
    assert model.sensitivity.significant_without == 0


def test_topic_rows_are_numbered_and_their_shares_sum_to_one(
    model: ReportModel, mini_run: Layout
) -> None:
    assert model.sensitivity is not None
    topics = model.sensitivity.topics
    stored = pl.read_parquet(mini_run.topics)
    assert [t.index for t in topics] == stored.get_column("thema").to_list()
    assert sum(t.documents for t in topics) == pl.read_parquet(mini_run.topic_documents).height
    assert all(len(t.words) == 10 and len(set(t.words)) == 10 for t in topics)
    # Die Themen zerlegen die gezählten Treffer, also summieren ihre Anteile zu 1.
    assert sum(t.hits_share for t in topics) == pytest.approx(1.0, abs=1e-9)


def test_variant_labels_come_from_the_settings_and_name_the_factors(
    default_settings: Settings,
) -> None:
    from georep.report.model import variant_labels

    labels = variant_labels(default_settings.weights)
    assert labels["einheit"][0] == "ohne Gewichtung"
    for rule_set in default_settings.weights.paper_type:
        label, description = labels[rule_set.name]
        assert label == rule_set.label
        assert rule_set.rules[0].pattern in description and "alle anderen" in description
    assert labels["kombiniert"][0] == "kombiniert"
    for factor in default_settings.weights.combined:
        assert labels[factor][0] in labels["kombiniert"][1]


def test_sensitivity_is_absent_without_the_long_table(
    mini_run: Layout, default_settings: Settings, tmp_path: Path
) -> None:
    """Ohne ``wahlbezirke_gewichtet.parquet`` fehlt das Modellfeld, und der Abschnitt entfällt."""
    import shutil

    from georep.report.model import build_sensitivity

    bare = Layout(tmp_path / "data", tmp_path / "cache", mini_run.reference_root)
    shutil.copytree(mini_run.root, bare.root)
    bare.weighted.unlink()
    built = build_report_model(bare, default_settings, now=NOW)
    assert built.sensitivity is None
    # Mit der langen Tabelle, aber ohne Themenmodell gibt es Zeilen und keine Themen.
    shutil.copyfile(mini_run.weighted, bare.weighted)
    bare.topics.unlink()
    without_topics = build_sensitivity(bare, default_settings, pl.read_parquet(bare.results))
    assert without_topics.topics == () and len(without_topics.rows) > 3


def test_an_empty_long_table_gives_no_rows_instead_of_an_error(mini_run: Layout) -> None:
    """Eine leere Tabelle ist kein Grund für einen IndexError, weder im Vertrag noch in der CLI."""
    from georep.report.model import sensitivity_rows
    from georep.settings import Weights

    empty = pl.read_parquet(mini_run.weighted).head(0)
    assert sensitivity_rows(empty, pl.read_parquet(mini_run.results), Weights()) == ()


# --- Option 03: Kontrollvariablen und abgeleitete Daten ------------------------------------------


def test_controls_section_on_the_mini_fixture_keeps_only_what_fits(model: ReportModel) -> None:
    """n = 3: nur Modell A passt, der Rest steht als „nicht geschätzt" da."""
    controls = model.controls
    assert controls is not None
    assert [m.name for m in controls.models] == ["A"]
    assert controls.main == "A" and controls.singles == ()
    assert controls.units == 24 and controls.units_label == "Sozialräume"
    assert controls.stand == dt.date(2021, 12, 31)
    assert controls.excluded == (1, 10) and controls.rate_without is None
    assert any("B (alle)" in m for m in controls.missing)
    assert "reichen die Wahlbezirke" in controls.verdict
    rate = next(t for t in controls.models[0].terms if t.term == "trefferquote")
    assert rate.label == "Trefferquote" and rate.vif == pytest.approx(1.0)
    assert controls.models[0].terms[0].term == "(Konstante)"
    assert controls.models[0].terms[0].beta is None


def test_controls_and_derived_are_none_without_context_data(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    from georep.bootstrap import bootstrap
    from georep.pipeline import build_steps, run_pipeline

    layout = Layout(tmp_path / "data", tmp_path / "cache", mini_root)
    bootstrap(layout)
    run_pipeline(build_steps(default_settings, layout), default_settings)
    plain = build_report_model(layout, default_settings, now=NOW)
    assert plain.controls is None and plain.derived is None
    assert {d.table for d in plain.columns} == {t.name for t in published(layout)} | {"wahlbezirke"}


def test_derived_data_names_source_licence_and_transform(model: ReportModel) -> None:
    derived = model.derived
    assert derived is not None
    assert derived.title and derived.publisher and derived.url.startswith("https://")
    assert derived.license_url == "https://www.govdata.de/dl-de/by-2-0"
    assert derived.stand == dt.date(2021, 12, 31) and derived.fetched == dt.date(2026, 10, 12)
    assert derived.districts == 3 and derived.units == 24
    assert derived.license in derived.attribution and derived.publisher in derived.attribution
    assert derived.title in derived.attribution
    by_name = {v.name: v for v in derived.variables}
    assert set(by_name) == {v.name for v in model_settings_variables()}
    assert "Score" in by_name["hb_score"].transform
    assert by_name["hb_score"].definition  # Definition aus der Erläuterungsdatei
    assert by_name["cdu"].transform == "Stimmenanteil mal 100"
    assert by_name["cdu"].definition == "" and "Wahlergebnis" in by_name["cdu"].source
    assert "Summe der Spalten" in by_name["anteil_65plus"].transform


def model_settings_variables() -> list[ContextVariable]:
    return list(load_settings(cwd=Path("/nonexistent")).context.variables)


def _control_model(name: str, coefficient: float, p: float, r2: float) -> ControlModel:
    terms = (
        ControlTerm("(Konstante)", "Achsenabschnitt", "", 50.0, 1.0, 0.0, None, None),
        ControlTerm("trefferquote", "Trefferquote", "", coefficient, 1.0, p, 0.3, 1.2),
        ControlTerm("hb_score", "Sozialer Handlungsbedarf", "", -9.0, 0.5, 0.0, -0.9, 1.4),
    )
    return ControlModel(name, terms, 41, 2, r2, r2 - 0.01, 0.0001)


def test_the_verdict_names_both_p_values_in_all_four_cases() -> None:
    """Der Satz vergleicht Modell A und das Hauptmodell; beide p entscheiden, was er sagt."""
    cases = {
        # (p in A, p im Hauptmodell) -> was der Satz tragen muss
        (0.01, 0.02): "wie mit den Kontrollvariablen",  # beide signifikant
        (0.01, 0.13): "nicht mehr von Null zu unterscheiden",  # nur A signifikant
        (0.31, 0.02): "erst mit den Kontrollvariablen",  # nur das Hauptmodell
        (0.31, 0.13): "und auch mit den Kontrollvariablen",  # keines von beiden
    }
    for (p_a, p_b), marker in cases.items():
        text = _verdict(
            [_control_model("A", 62.0, p_a, 0.03), _control_model("B", 40.0, p_b, 0.89)], "B", ()
        )
        assert marker in text, (p_a, p_b, text)
        # Beide p-Werte stehen im Satz, keiner wird unterschlagen
        assert format_de(p_a, 3) in text and format_de(p_b, 3) in text, (p_a, p_b, text)
    # Ohne Signifikanz behauptet der Satz keine Richtung
    neither = _verdict(
        [_control_model("A", 62.0, 0.31, 0.03), _control_model("B", 40.0, 0.13, 0.89)], "B", ()
    )
    assert "höher" not in neither and "niedriger" not in neither
    assert "erklären die Kontrollvariablen" not in neither  # Modell A zeigt ja nichts


def test_the_verdict_follows_the_numbers(tmp_path: Path) -> None:
    """Der Satz zur Deutung entsteht aus p, Vorzeichen und R², nicht aus festem Text."""
    simple = _control_model("A", 62.0, 0.01, 0.03)
    nearby = ControlTerm("trefferquote", "Trefferquote", "", 41.0, 1.0, 0.02, 0.3, 1.2)
    significant = _verdict([simple, _control_model("B", 40.0, 0.01, 0.89)], "B", (1, 10), nearby)
    assert "signifikant" in significant and "höher" in significant
    assert "0,89" in significant and "Sozialer Handlungsbedarf" in significant
    assert "ohne die Wahlbezirke 1 und 10" in significant
    negative = _verdict([simple, _control_model("B", -40.0, 0.01, 0.89)], "B", ())
    assert "niedriger" in negative and "ohne die Wahlbezirke" not in negative
    insignificant = _verdict([simple, _control_model("B", 40.0, 0.13, 0.89)], "B", ())
    assert "nicht mehr von Null zu unterscheiden" in insignificant
    assert "keine Ursache" in insignificant
    assert _verdict([simple], "B", ()).startswith("Für Modelle mit Kontrollvariablen")


def test_a_tiny_p_is_plain_text_for_the_autoescape() -> None:
    """Der Satz ist Text, kein HTML: ein `<` darf nicht als Entity hineingeraten."""
    text = _verdict(
        [_control_model("A", 62.0, 0.0000001, 0.03), _control_model("B", 40.0, 0.0002, 0.89)],
        "B",
        (),
    )
    assert "< 0,001" in text and "&lt;" not in text


def test_the_outlier_clause_compares_the_coefficients() -> None:
    """„Ähnlich" muss gemessen sein: gleiches Vorzeichen, beide p auf derselben Seite von 0,05
    und die relative Abweichung unter der Grenze; sonst nennt der Satz die Zahlen."""
    models = [_control_model("A", 62.0, 0.31, 0.03), _control_model("B", 40.0, 0.13, 0.89)]

    def without(coefficient: float, p: float) -> ControlTerm:
        return ControlTerm("trefferquote", "Trefferquote", "", coefficient, 1.0, p, 0.3, 1.2)

    near = _verdict(models, "B", (1, 10), without(42.0, 0.15))
    assert "ohne die Wahlbezirke 1 und 10 sieht es ähnlich aus" in near

    # Der Fall der Referenz: 68,03 statt 41,33 ist keine Ähnlichkeit mehr
    far = _verdict(models, "B", (1, 10), without(68.03, 0.099))
    assert "sieht es ähnlich aus" not in far
    assert "68,03" in far and "0,099" in far and "ohne die Wahlbezirke 1 und 10" in far

    # Anderes Vorzeichen oder andere Seite von 0,05: ebenfalls nicht ähnlich
    flipped = _verdict(models, "B", (1, 10), without(-42.0, 0.15))
    assert "sieht es ähnlich aus" not in flipped and "-42,00" in flipped
    crossed = _verdict(models, "B", (1, 10), without(42.0, 0.01))
    assert "sieht es ähnlich aus" not in crossed and "0,010" in crossed

    # Ohne zweite Stichprobe sagt der Satz dazu nichts
    assert "Wahlbezirke 1 und 10" not in _verdict(models, "B", (), None)


def test_the_attribution_comes_from_the_settings(tmp_path: Path) -> None:
    """Namensnennung ist Herausgeber, Datensatz und Lizenz aus den Settings -- kein fester Text.

    Eine andere Stadt nennt eine andere Lizenz; stünde „dl-de/by-2-0" fest im Code, wäre die
    Namensnennung dann falsch (Review 2026-10-12).
    """
    from georep.report.model import _attribution

    dataset = load_settings(cwd=Path("/nonexistent")).context.dataset
    here = _attribution(dataset)
    assert dataset.publisher in here and dataset.title in here and dataset.license in here

    other = dataset.model_copy(
        update={
            "publisher": "Stadt Beispielstadt, Amt für Zahlen",
            "title": "Sozialbericht 2030",
            "license": "Creative Commons Zero 1.0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/deed.de",
        }
    )
    text = _attribution(other)
    assert "Stadt Beispielstadt, Amt für Zahlen" in text and "Sozialbericht 2030" in text
    assert "Creative Commons Zero 1.0" in text
    assert "dl-de" not in text and "Quartiersatlas" not in text


# --- Option 04: der Abschnitt „Urheber und Parteien" -----------------------------------------------


def test_the_party_section_matches_polars(mini_run: Layout, default_settings: Settings) -> None:
    """Die drei Listen des Modells gegen die drei Parquet-Tabellen nachgerechnet."""
    model = build_report_model(
        mini_run, default_settings, now=dt.datetime(2026, 10, 12, tzinfo=dt.UTC)
    )
    party_table = pl.read_parquet(mini_run.party_results)
    attribution = pl.read_parquet(mini_run.document_originators)
    assert len(model.parties) == len(default_settings.originators.parties)
    assert [p.key for p in model.parties] == [p.key for p in default_settings.originators.parties]
    assert [p.label for p in model.parties] == [
        p.label for p in default_settings.originators.parties
    ]
    for party in model.parties:
        mine = party_table.filter(pl.col("partei") == party.key)
        assert party.hits == int(mine.get_column("anzahl_treffer").sum())
        assert party.alone == int(mine.get_column("treffer_allein").sum())
        assert party.documents == int(mine.get_column("dokumente_partei").to_list()[0])
        assert party.n == mine.filter(pl.col("angetreten")).height
        assert party.districts_hit == mine.filter(pl.col("anzahl_treffer") > 0).height
    assert len(model.party_cells) == party_table.height
    assert all(0 <= c.klass <= 4 for c in model.party_cells)

    figures = model.originator_figures
    assert figures is not None
    assert figures.documents == attribution.height
    assert figures.classified + figures.unbekannt == figures.documents
    assert 0.0 <= figures.coverage <= 1.0
    assert figures.from_oparl == 0  # die Mini-Fixture trägt keine Urheberfelder

    districts = pl.read_parquet(mini_run.district_originators)
    assert len(model.originators) == districts.height
    for row in model.originators:
        assert row.verwaltung + row.fraktion + row.person + row.eingabe + row.unbekannt == row.hits
        assert row.name  # jeder Bezirk trägt den Namen aus dem GeoJSON


def test_cells_for_follows_the_column_order_not_the_sort_order(
    mini_run: Layout, default_settings: Settings
) -> None:
    """``party_cells`` ist alphabetisch nach Schlüssel sortiert, die Spalten folgen den Settings."""
    model = build_report_model(
        mini_run, default_settings, now=dt.datetime(2026, 10, 12, tzinfo=dt.UTC)
    )
    keys = [p.key for p in model.parties]
    assert keys[0] == "CDU" and keys[-1] == "AfD"  # Settings-Reihenfolge, nicht alphabetisch
    assert sorted(keys) != keys  # sonst prüfte der Test nichts
    for row in model.originators:
        assert [c.party for c in model.cells_for(row.district)] == keys
        assert all(c.district == row.district for c in model.cells_for(row.district))


def test_without_the_parties_step_the_section_stays_empty(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    """Ein Lauf ohne den Schritt ``parties`` lässt die vier Modellfelder leer; die Vorlage
    blendet den Abschnitt dann aus."""
    from georep.bootstrap import bootstrap
    from georep.pipeline import build_steps, run_pipeline

    layout = Layout(tmp_path / "data", tmp_path / "cache", mini_root)
    bootstrap(layout)
    steps = [
        s for s in build_steps(default_settings, layout) if s.name not in ("parties", "report")
    ]
    run_pipeline(steps, default_settings, [s.name for s in steps if not s.network])
    assert not layout.party_results.exists()
    model = build_report_model(
        layout, default_settings, now=dt.datetime(2026, 10, 12, tzinfo=dt.UTC)
    )
    assert model.parties == () and model.party_cells == ()
    assert model.originators == () and model.originator_figures is None
    assert model.cells_for(1) == ()


# --- Option 02: der Vergleich im Modell, auch wenn eine Rechnung kein Ergebnis hat -------------

REPO = Path(__file__).resolve().parents[2]
COMPARE_PROFILE = "duesseldorf-vergleich"
LABELS = ("Wahlperiode 2014 bis 2020", "Wahlperiode 2020 bis 2025")


def _results(rates: list[float], turnouts: list[float]) -> pl.DataFrame:
    districts = list(range(1, len(rates) + 1))
    return pl.DataFrame(
        {
            "wahlkreis_id": districts,
            "anzahl_treffer": [round(r * 10_000) for r in rates],
            "Wahlberechtigte_insgesamt": [10_000] * len(rates),
            "trefferquote": rates,
            "wahlbeteiligung": turnouts,
        }
    ).sort("wahlkreis_id")


def _compared(tmp_path: Path, old: pl.DataFrame, new: pl.DataFrame) -> tuple[Layout, Settings]:
    """Eine Datenwurzel mit gerechnetem Vergleich und der Zuordnung der älteren Periode."""
    settings = load_settings(profile=COMPARE_PROFILE, cwd=Path("/nonexistent")).model_copy(
        update={"data_root": tmp_path / "data", "cache_root": tmp_path / "cache"}
    )
    layout = Layout.from_settings(settings)
    other = layout.for_profile(settings.compare.period)
    for target in (layout, other):
        target.ensure_dirs()
    write_parquet(compare_periods(new, old, labels=LABELS), layout.comparison, schema_version=1)
    write_parquet(old, other.results, schema_version=1)
    write_parquet(
        pl.DataFrame({"stimmbezirk_id": ["0101", "0102"], "abdeckung": [1.0, 0.99]}),
        other.precinct_assignment,
        schema_version=1,
    )
    return layout, settings


def test_period_comparison_reads_both_periods_and_the_assignment(tmp_path: Path) -> None:
    old = _results([0.001, 0.002, 0.003], [0.40, 0.50, 0.60])
    new = _results([0.002, 0.002, 0.005], [0.45, 0.48, 0.70])
    layout, settings = _compared(tmp_path, old, new)
    comparison = period_comparison(layout, settings, {1: "Eins", 2: "Zwei", 3: "Drei"}, 3, "alt/")
    assert comparison is not None
    assert [r.name for r in comparison.rows] == ["Eins", "Zwei", "Drei"]
    assert comparison.previous == LABELS[0] and comparison.current == LABELS[1]
    assert comparison.precincts == 2 and comparison.split == 0
    assert comparison.min_coverage == pytest.approx(0.99)
    assert comparison.regression.n == 3 and comparison.previous_pair.all.n == 3


def test_a_comparison_without_spread_is_a_domain_error_not_a_contract_error(
    tmp_path: Path,
) -> None:
    """Eine Regression ohne Streuung ist ein Domänenfehler; er muss lesbar nach außen kommen.

    Mit konstanter Trefferquote der älteren Periode rechnet ``regression_pair`` nichts; früher
    wurde daraus ein ``deal.RaisesContractError`` ohne Meldung, weil ``deal.raises`` den
    ``EmptyResultError`` nicht nannte.
    """
    old = _results([0.002, 0.002, 0.002], [0.40, 0.50, 0.60])
    new = _results([0.001, 0.003, 0.006], [0.45, 0.48, 0.70])
    layout, settings = _compared(tmp_path, old, new)
    with pytest.raises(EmptyResultError, match="Streuung in trefferquote"):
        period_comparison(layout, settings, {1: "Eins", 2: "Zwei", 3: "Drei"}, 3, "alt/")


def test_a_missing_assignment_names_the_run_that_is_missing(tmp_path: Path) -> None:
    old = _results([0.001, 0.002, 0.003], [0.40, 0.50, 0.60])
    new = _results([0.002, 0.002, 0.005], [0.45, 0.48, 0.70])
    layout, settings = _compared(tmp_path, old, new)
    layout.for_profile(settings.compare.period).precinct_assignment.unlink()
    with pytest.raises(MissingInputError, match="2014-2020"):
        period_comparison(layout, settings, {1: "Eins", 2: "Zwei", 3: "Drei"}, 3, "alt/")


# --- Option 07: Monitoring der laufenden Wahlperiode ------------------------------------------


def test_key_figures_know_the_documents_without_text(model: ReportModel) -> None:
    figures = model.figures
    assert figures.documents_without_text == figures.documents - figures.documents_with_text
    assert figures.documents_without_text == 0  # die Mini-Fixture hat zu jedem Paper einen Text


def test_data_stand_reads_the_stamps_of_the_network_steps(mini_run: Layout) -> None:
    from georep.report.model import data_stand, newest_document

    settings = load_settings(cwd=Path("/nonexistent"))
    stand = data_stand(mini_run, settings)
    # bootstrap kopiert die Referenz: papers und pdfs liefen nie, also kein Abrufdatum
    assert stand.papers_fetched is None and stand.pdfs_fetched is None
    assert stand.newest_document == pl.read_parquet(mini_run.corpus)["date"].max()
    assert newest_document(mini_run.corpus) == dt.date(2025, 9, 4)


def test_the_timeline_of_the_model_is_the_parquet_table(
    model: ReportModel, mini_run: Layout
) -> None:
    frame = pl.read_parquet(mini_run.timeline)
    assert len(model.timeline) == frame.height
    assert [row.month for row in model.timeline] == frame["monat"].to_list()
    assert sum(row.documents for row in model.timeline) == model.figures.documents
    assert all(row.with_hits <= row.with_text <= row.documents for row in model.timeline)
    assert model.monitoring_url == ""  # Standard: kein Abschnitt auf der Hauptseite


def test_the_report_switches_turn_off_regression_and_name_the_monitoring_page(
    mini_run: Layout,
) -> None:
    settings = load_settings(cwd=Path("/nonexistent"))
    switched = settings.model_copy(
        update={
            "report": settings.report.model_copy(
                update={"regression": False, "monitoring_url": "2025/"}
            )
        }
    )
    model = build_report_model(mini_run, switched, now=NOW)
    assert model.regression is None and model.monitoring_url == "2025/"
    assert model.timeline  # die Monatsreihe bleibt


def test_key_figures_count_documents_without_text(mini_run: Layout, tmp_path: Path) -> None:
    """Die laufende Periode hat zwischen Abruf und Extraktion Dokumente ohne Text."""
    from georep.report.model import key_figures

    corpus = pl.read_parquet(mini_run.corpus)
    blanked = corpus.with_columns(
        pl.when(pl.int_range(pl.len()) < 3).then(pl.lit("")).otherwise(pl.col("text")).alias("text")
    )
    path = tmp_path / "papers.parquet"
    blanked.write_parquet(path)
    figures = key_figures(
        pl.read_parquet(mini_run.results), pl.read_parquet(mini_run.dictionary), path, 22
    )
    assert figures.documents == corpus.height
    assert figures.documents_with_text == corpus.height - 3
    assert figures.documents_without_text == 3
