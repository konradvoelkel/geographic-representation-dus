from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from georep.errors import SchemaError
from georep.layout import Layout
from georep.settings import (
    Bodies,
    Period,
    UnknownProfileError,
    available_profiles,
    deep_merge,
    load_settings,
    profiles_folder,
    settings_files,
)


def test_defaults_load_without_any_file(tmp_path: Path) -> None:
    s = load_settings(cwd=tmp_path)
    assert s.data_root == Path("data")
    assert s.cache_dir == Path("data") / "cache"
    assert s.period == s.period.model_validate(
        {"start": date(2020, 9, 13), "end": date(2025, 9, 14)}
    )
    assert s.sources.oparl.endpoint.endswith("/bodies/0015/papers")
    assert set(s.columns.results.parties) == {"CDU", "GRUENE", "SPD", "FDP", "Die_Linke", "AfD"}
    assert "Düsseldorf" in s.search.exclude
    assert len(s.search.exclude) == 63


def test_local_file_overrides_deeply_and_keeps_siblings(tmp_path: Path) -> None:
    (tmp_path / "settings.local.toml").write_text(
        'data_root = "/media/x/georep"\n[sources.oparl]\ndelay_s = 3.5\n', encoding="utf-8"
    )
    s = load_settings(cwd=tmp_path)
    assert s.data_root == Path("/media/x/georep")
    assert s.sources.oparl.delay_s == 3.5
    assert s.sources.oparl.endpoint.endswith("/bodies/0015/papers")  # Geschwister bleiben
    assert s.sources.opendata.results_url  # andere Tabellen bleiben
    assert settings_files(cwd=tmp_path) == [tmp_path / "settings.local.toml"]


def test_environment_beats_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "settings.toml").write_text('data_root = "./aus-datei"\n', encoding="utf-8")
    monkeypatch.setenv("GEOREP_DATA_ROOT", "./aus-umgebung")
    monkeypatch.setenv("GEOREP_SOURCES__OPARL__DELAY_S", "7")
    s = load_settings(cwd=tmp_path)
    assert s.data_root == Path("aus-umgebung")
    assert s.sources.oparl.delay_s == 7.0


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text("[sources.oparl]\ndeley_s = 2\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="deley_s"):
        load_settings(cwd=tmp_path)


def test_period_must_be_ordered(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        "[period]\nstart = 2025-01-01\nend = 2020-01-01\n", encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="period.end"):
        load_settings(cwd=tmp_path)


def test_explicit_file_must_exist(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_settings(explicit=tmp_path / "fehlt.toml", cwd=tmp_path)


def test_fingerprint_ignores_paths_but_sees_parameters(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text('data_root = "/anderswo"\n', encoding="utf-8")
    moved = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text("[period]\nend = 2024-12-31\n", encoding="utf-8")
    changed = load_settings(cwd=tmp_path)
    assert base.fingerprint() == moved.fingerprint()
    assert base.fingerprint() != changed.fingerprint()


def test_deep_merge_replaces_lists_and_scalars_but_merges_tables() -> None:
    merged = deep_merge({"a": {"x": 1, "y": [1, 2]}, "b": 1}, {"a": {"y": [3]}, "c": 2})
    assert merged == {"a": {"x": 1, "y": [3]}, "b": 1, "c": 2}


def test_settings_are_frozen(tmp_path: Path) -> None:
    s = load_settings(cwd=tmp_path)
    with pytest.raises(ValidationError):
        s.data_root = Path("/x")


def test_log_level_comes_from_environment_and_is_validated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEOREP_LOG_LEVEL", "debug")
    assert load_settings(cwd=tmp_path).log_level == "DEBUG"
    monkeypatch.setenv("GEOREP_LOG_LEVEL", "laut")
    with pytest.raises(ValidationError, match="log_level"):
        load_settings(cwd=tmp_path)


def test_fingerprint_ignores_contracts_switch(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text('contracts = "off"\n', encoding="utf-8")
    off = load_settings(cwd=tmp_path)
    assert off.contracts == "off" and base.fingerprint() == off.fingerprint()


def test_text_split_marker_must_not_be_empty(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('[search]\ntext_split_marker = ""\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="text_split_marker"):
        load_settings(cwd=tmp_path)


def test_profile_must_be_a_plain_folder_name(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('profile = "../x"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="profile"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text('profile = "2014-2020"\n', encoding="utf-8")
    assert load_settings(cwd=tmp_path).profile == "2014-2020"


def test_profile_does_not_change_the_fingerprint(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text('profile = "x"\n', encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() == base.fingerprint()


def test_open_period_needs_an_election_day(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[period]\nstart = 2025-09-15\nend = ""\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="period"):
        load_settings(cwd=tmp_path)
    # end aus defaults.toml bleibt beim tiefen Merge stehen; end = "" macht die Periode offen
    (tmp_path / "settings.toml").write_text(
        '[period]\nstart = 2025-09-15\nend = ""\nelection = 2025-09-14\n', encoding="utf-8"
    )
    merged = load_settings(cwd=tmp_path)
    assert merged.period.end is None and merged.period.election_day == date(2025, 9, 14)
    closed = load_settings(cwd=Path("/nonexistent"))
    assert closed.period.election is None and closed.period.election_day == closed.period.end


def test_open_period_model_requires_election_but_no_order_to_start() -> None:
    with pytest.raises(ValidationError, match="election ist Pflicht"):
        Period(start=date(2025, 9, 15))
    # Die laufende Periode beginnt am Tag nach der Wahl, deren Ergebnis sie misst (Option 7)
    open_period = Period(start=date(2025, 9, 15), election=date(2025, 9, 14), end=None)
    assert open_period.end is None and open_period.election_day == date(2025, 9, 14)
    with pytest.raises(ValidationError, match="period.end"):
        Period(start=date(2025, 9, 15), end=date(2025, 1, 1))


# --- Option 05: Gremien -----------------------------------------------------------------------


def test_bodies_tables_load_with_disjoint_codes(tmp_path: Path) -> None:
    import re

    s = load_settings(cwd=tmp_path)
    pattern = re.compile(s.bodies.reference_pattern)
    assert {"code", "number"} <= set(pattern.groupindex)
    assert s.bodies.district_body and s.bodies.district_body not in s.bodies.committees
    assert "{n}" in s.bodies.district_body_name
    assert s.bodies.council and s.bodies.committees and s.bodies.advisory
    assert set(s.bodies.council).isdisjoint(s.bodies.committees)
    assert set(s.bodies.committees).isdisjoint(s.bodies.advisory)
    assert set(s.bodies.council).isdisjoint(s.bodies.advisory)
    assert s.bodies.names_as_of is not None
    assert s.columns.results.city_district


def test_bodies_code_in_two_tables_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[bodies.advisory]\nRAT = "noch einmal"\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="RAT"):
        load_settings(cwd=tmp_path)


def test_bodies_district_body_may_not_be_a_table_code(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('[bodies]\ndistrict_body = "RAT"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="district_body"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text('[bodies]\ndistrict_body = ""\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="district_body"):
        load_settings(cwd=tmp_path)


def test_bodies_pattern_needs_the_groups_code_and_number(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[bodies]\nreference_pattern = "^(?P<kuerzel>[A-Z]+)/"\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="code"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        '[bodies]\nreference_pattern = "^(?P<code>[A-Z]+"\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="reference_pattern"):
        load_settings(cwd=tmp_path)


def test_fingerprint_sees_body_codes_but_not_the_date_of_the_names(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text('[bodies.committees]\nNEU = ""\n', encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() != base.fingerprint()
    (tmp_path / "settings.toml").write_text(
        "[bodies]\nnames_as_of = 2030-01-01\n", encoding="utf-8"
    )
    assert load_settings(cwd=tmp_path).fingerprint() == base.fingerprint()


# --- Option 06: Gewichtung --------------------------------------------------------------------


def test_weights_and_topics_defaults_are_loaded(tmp_path: Path) -> None:
    s = load_settings(cwd=tmp_path)
    assert [v.name for v in s.weights.paper_type] == ["antraege_halb", "nur_vorlagen"]
    assert s.weights.paper_type[0].rules[0].weight == 0.5
    assert s.weights.paper_type[1].rules[0].weight == 0.0
    assert all(v.label for v in s.weights.paper_type)
    assert s.weights.combined == ["idf", "antraege_halb"]
    assert s.topics.k == 20 and s.topics.stop_words == "de" and 0 < s.topics.max_df <= 1


def test_overpass_query_timeout_stays_between_five_and_180_seconds(tmp_path: Path) -> None:
    """Punkt 54: unter 5 s antwortet keine Instanz, über 180 s weist jede die Abfrage ab."""
    assert load_settings(cwd=tmp_path).sources.osm.query_timeout_s == 25
    for value in (4, 181):
        (tmp_path / "settings.toml").write_text(
            f"[sources.osm]\nquery_timeout_s = {value}\n", encoding="utf-8"
        )
        with pytest.raises(ValidationError, match="query_timeout_s"):
            load_settings(cwd=tmp_path)


def test_paper_type_weight_must_lie_between_zero_and_one(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[[weights.paper_type]]\nname = "x"\nlabel = "x"\n'
        'rules = [{ pattern = "^antrag", weight = 1.5 }]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="weight"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        '[[weights.paper_type]]\nname = "x"\nlabel = "x"\ndefault = -0.1\nrules = []\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="default"):
        load_settings(cwd=tmp_path)


def test_paper_type_pattern_must_compile(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[[weights.paper_type]]\nname = "x"\nlabel = "x"\n'
        'rules = [{ pattern = "(antrag", weight = 0.5 }]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="pattern"):
        load_settings(cwd=tmp_path)


def test_paper_type_variant_names_are_unique_and_not_reserved(tmp_path: Path) -> None:
    twice = (
        '[[weights.paper_type]]\nname = "x"\nlabel = "x"\nrules = []\n'
        '[[weights.paper_type]]\nname = "x"\nlabel = "x"\nrules = []\n'
        '[weights]\ncombined = ["idf"]\n'
    )
    (tmp_path / "settings.toml").write_text(twice, encoding="utf-8")
    with pytest.raises(ValidationError, match="eindeutig"):
        load_settings(cwd=tmp_path)
    for reserved in ("einheit", "idf", "bezirke", "kombiniert", "thema_03"):
        (tmp_path / "settings.toml").write_text(
            f'[[weights.paper_type]]\nname = "{reserved}"\nlabel = "x"\nrules = []\n'
            '[weights]\ncombined = ["idf"]\n',
            encoding="utf-8",
        )
        with pytest.raises(ValidationError, match="name"):
            load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        '[[weights.paper_type]]\nname = "Nur Vorlagen"\nlabel = "x"\nrules = []\n'
        '[weights]\ncombined = ["idf"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="name"):
        load_settings(cwd=tmp_path)


def test_combined_names_only_known_factors(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[weights]\ncombined = ["idf", "gibtsnicht"]\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="combined"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        '[weights]\ncombined = ["idf", "idf"]\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="combined"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text("[weights]\ncombined = []\n", encoding="utf-8")
    assert load_settings(cwd=tmp_path).weights.combined == []


def test_topics_k_zero_is_allowed_and_bounds_are_checked(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text("[topics]\nk = 0\n", encoding="utf-8")
    assert load_settings(cwd=tmp_path).topics.k == 0
    for bad in (
        "k = -1",
        "max_df = 0",
        "max_df = 1.5",
        "min_df = 0",
        "top_words = 0",
        'stop_words = "../x"',
        "max_iter = 0",
        "tol = 0",
        "k = 100",
        'stop_sources = ["parteien"]',
        'stop_sources = ["gremien", "gremien"]',
        "name_window = 0",
        "name_share = 0",
        "name_share = 1.5",
        "name_min_documents = 0",
        'seed = "ausschuesse"',
        "free = -1",
        "free = 21",
        "seed_words = 0",
        "seed_min_documents = 0",
        "seed_prior = 0",
    ):
        (tmp_path / "settings.toml").write_text(f"[topics]\n{bad}\n", encoding="utf-8")
        with pytest.raises(ValidationError, match="topics"):
            load_settings(cwd=tmp_path)


def test_the_topic_stop_word_sources_and_the_seed_are_loaded(tmp_path: Path) -> None:
    """Punkt 45: die Stoppwortquellen und die Saat stehen in den Settings, nicht im Code."""
    topics = load_settings(cwd=tmp_path).topics
    assert set(topics.stop_sources) == {"fraktionen", "gremien", "namen"}
    assert topics.seed == "committees" and 0 < topics.free < topics.k
    assert "gez." in topics.name_markers and topics.name_window > 0
    assert 0.0 < topics.name_share <= 1.0 and topics.seed_prior > 0.0


def test_classify_defaults_and_bounds(tmp_path: Path) -> None:
    """Punkt 45: der Klassifikator des passenden Ausschusses."""
    classify = load_settings(cwd=tmp_path).classify
    assert classify.enabled and classify.min_documents >= 5
    assert 0.0 < classify.min_probability < 1.0 and classify.regularisation > 0.0
    for bad in (
        "min_documents = 1",
        "min_probability = 0",
        "min_probability = 1",
        "regularisation = 0",
        "max_iterations = 0",
    ):
        (tmp_path / "settings.toml").write_text(f"[classify]\n{bad}\n", encoding="utf-8")
        with pytest.raises(ValidationError, match="classify"):
            load_settings(cwd=tmp_path)


def test_fingerprint_sees_weights_and_topics(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text("[topics]\nk = 5\n", encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() != base.fingerprint()
    (tmp_path / "settings.toml").write_text('[weights]\ncombined = ["idf"]\n', encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() != base.fingerprint()
    (tmp_path / "settings.toml").write_text("[topics]\nstop_sources = []\n", encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() != base.fingerprint()
    (tmp_path / "settings.toml").write_text("[classify]\nmin_probability = 0.5\n", encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() != base.fingerprint()


def test_topics_k_stops_at_99_so_the_variant_names_sort(tmp_path: Path) -> None:
    """``thema_100`` stünde zwischen ``thema_10`` und ``thema_11``; zwei Stellen sind die Grenze."""
    (tmp_path / "settings.toml").write_text("[topics]\nk = 99\n", encoding="utf-8")
    assert load_settings(cwd=tmp_path).topics.k == 99
    (tmp_path / "settings.toml").write_text("[topics]\nk = 100\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="99"):
        load_settings(cwd=tmp_path)


def test_a_label_is_an_display_value_and_stays_out_of_the_fingerprint(tmp_path: Path) -> None:
    """Die Beschriftung eines Regelsatzes steht nur auf der Seite; sie darf keinen Lauf auslösen."""
    rules = (
        '[weights]\ncombined = ["idf", "x"]\n'
        '[[weights.paper_type]]\nname = "x"\nlabel = "{}"\n'
        'rules = [{{ pattern = "^antrag", weight = 0.5 }}]\n'
    )
    (tmp_path / "settings.toml").write_text(rules.format("Anträge halb"), encoding="utf-8")
    first = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(rules.format("Anträge, Anfragen"), encoding="utf-8")
    second = load_settings(cwd=tmp_path)
    assert first.weights.paper_type[0].label != second.weights.paper_type[0].label
    assert first.fingerprint() == second.fingerprint()
    # Das Gewicht derselben Regel zählt dagegen sehr wohl.
    (tmp_path / "settings.toml").write_text(
        rules.format("Anträge halb").replace("0.5", "0.25"), encoding="utf-8"
    )
    assert load_settings(cwd=tmp_path).fingerprint() != first.fingerprint()


# --- Option 03: Kontextdaten und Kontrollvariablen ---------------------------------------------


def test_context_defaults_name_files_variables_and_models(tmp_path: Path) -> None:
    s = load_settings(cwd=tmp_path)
    context = s.context
    assert context.root == Path("context")
    assert context.files.table.file.endswith(".csv")
    assert context.files.units.file.endswith(".geojson")
    assert context.files.indicators.file.endswith(".csv")
    names = [v.name for v in context.variables]
    assert len(names) == len(set(names)) and "trefferquote" not in names
    for model in (context.models.main, context.models.parties, context.models.single):
        assert all(term == "trefferquote" or term in names for term in model)
    assert context.models.main[0] == "trefferquote" and len(context.models.main) >= 2
    assert all(v.scale in context.scales for v in context.variables if v.kind == "ordinal")
    assert 0 < context.max_missing_weight < 1 and 0 < context.min_coverage <= 1
    assert context.dataset.license_url.startswith("https://")


def test_context_root_empty_means_no_context_data(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('[context]\nroot = ""\n', encoding="utf-8")
    assert load_settings(cwd=tmp_path).context.root is None


def test_context_model_with_unknown_variable_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[context.models]\nmain = ["trefferquote", "gibtsnicht"]\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="gibtsnicht"):
        load_settings(cwd=tmp_path)


def test_context_scale_values_must_be_distinct(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[context.scales.handlungsbedarf]\ngering = 1\n"eher gering" = 1\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="handlungsbedarf"):
        load_settings(cwd=tmp_path)


def test_context_ordinal_variable_needs_a_known_scale(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        "[[context.variables]]\n"
        'name = "x"\nlabel = "x"\nunit = ""\nkind = "ordinal"\ncolumns = ["Sozialer_HB"]\n'
        'scale = "fehlt"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="fehlt"):
        load_settings(cwd=tmp_path)


def test_unknown_key_in_context_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text("[context]\nwurzel = 1\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="wurzel"):
        load_settings(cwd=tmp_path)


def test_fingerprint_ignores_context_paths_and_display_values_but_sees_models(
    tmp_path: Path,
) -> None:
    base = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        '[context]\nroot = "/anderswo"\n[context.dataset]\nfetched = 2030-01-01\n'
        '[context.files.table]\nfile = "andere.csv"\n',
        encoding="utf-8",
    )
    assert load_settings(cwd=tmp_path).fingerprint() == base.fingerprint()
    (tmp_path / "settings.toml").write_text(
        '[context.models]\nmain = ["trefferquote"]\n', encoding="utf-8"
    )
    assert load_settings(cwd=tmp_path).fingerprint() != base.fingerprint()


# --- Option 04: Urheber und Parteien -------------------------------------------------------------


def test_originators_defaults_describe_duesseldorf(tmp_path: Path) -> None:
    o = load_settings(cwd=tmp_path).originators
    assert [p.key for p in o.parties] == ["CDU", "GRUENE", "SPD", "FDP", "Die_Linke", "AfD"]
    assert [g.key for g in o.groups] == ["T_FW", "PARTEI", "VOLT"]
    assert o.all_keys == (
        "CDU",
        "GRUENE",
        "SPD",
        "FDP",
        "Die_Linke",
        "AfD",
        "T_FW",
        "PARTEI",
        "VOLT",
    )
    # Punkt 60: neun Verwaltungs- und drei Eingabearten, je eine davon nur in der Periode
    # 2014 bis 2020 („Verwaltungsvorlage", „Bezirksvertretung Eingabe nach 24Go")
    assert len(o.admin_types) == 9 and len(o.citizen_types) == 3
    assert "Verwaltungsvorlage" in o.admin_types
    # Punkt 59: diese Stadt braucht die beiden Listen nicht -- ihre Dokumentarten nennen die
    # Fraktion selbst, und wo nicht, entscheiden Titel und Textkopf
    assert o.fraction_types == [] and o.person_types == []
    # Die längsten Antragspräfixe zuerst, sonst bleibt von „Haushaltsantrag CDU/Grüne" ein Rest
    assert o.motion_prefixes[0] == "Haushaltsantrag"
    # Punkt 60 und 62: zwei Textmarker, und der Vorlagenkopf der älteren Periode steht als
    # Briefkopfmarker daneben -- der gilt vor der Dokumentart, der Textmarker danach
    assert len(o.text_markers) == 2
    assert len(o.letterhead_markers) == 1 and "rsd" in o.letterhead_markers[0]
    assert o.text_head_chars == 600 and o.text_window_chars == 80
    assert all(p.organizations for p in o.parties)  # jede Partei kennt ihre OParl-Organisation


def test_party_keys_must_have_a_vote_column(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[[originators.parties]]\nkey = "XYZ"\nlabel = "X"\npatterns = ["x"]\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="columns.results.parties"):
        load_settings(cwd=tmp_path)


def test_doubled_party_keys_and_broken_patterns_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[[originators.groups]]\nkey = "T_FW"\nlabel = "A"\npatterns = ["a"]\n'
        '[[originators.groups]]\nkey = "T_FW"\nlabel = "B"\npatterns = ["b"]\n'
        '[[originators.groups]]\nkey = "PARTEI"\nlabel = "C"\npatterns = ["c"]\n'
        '[[originators.groups]]\nkey = "VOLT"\nlabel = "D"\npatterns = ["d"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="doppelte Parteischlüssel"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        '[originators]\ntext_markers = ["(unbalanciert"]\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="regulärer Ausdruck"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        "[originators]\ntext_head_chars = 0\n", encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="positiv"):
        load_settings(cwd=tmp_path)


def test_a_changed_pattern_changes_the_fingerprint(tmp_path: Path) -> None:
    """Die Muster bestimmen das Ergebnis, also zählen sie zum Fingerprint; der Pfad nicht."""
    base = load_settings(cwd=Path("/nonexistent")).fingerprint()
    (tmp_path / "settings.toml").write_text(
        "[originators]\ntext_head_chars = 800\n", encoding="utf-8"
    )
    assert load_settings(cwd=tmp_path).fingerprint() != base


# --- Option 02: Periode als Profil -----------------------------------------------------------


def test_period_label_and_dictionary_have_defaults_and_a_derived_title() -> None:
    closed = Period(start=date(2014, 5, 25), end=date(2020, 9, 12), election=date(2020, 9, 13))
    assert closed.label == "" and closed.dictionary == "own"
    assert closed.title == "Wahlperiode 2014 bis 2020"
    assert Period(start=date(2025, 9, 15), election=date(2025, 9, 14)).title == (
        "Wahlperiode seit 2025"
    )
    assert Period(start=date(2014, 5, 25), end=date(2020, 9, 12), label="Rat 2014").title == (
        "Rat 2014"
    )


def test_base_dictionary_names_the_case_it_collides_with(tmp_path: Path) -> None:
    """Zwei Faelle, zwei Saetze (Review 2026-10-13, Befund 10).

    Mit dem Ordner der Hauptperiode waere es derselbe Lauf; mit ``""`` waere es die Datenwurzel
    selbst, in der die Ordner der Profile und ``site/`` liegen -- kein eigener Ordner.
    """
    (tmp_path / "settings.toml").write_text('[period]\ndictionary = "base"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="derselbe Lauf"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        'profile = ""\n[period]\ndictionary = "base"\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="Datenwurzel selbst"):
        load_settings(cwd=tmp_path)


def test_base_dictionary_needs_a_profile_of_its_own(tmp_path: Path) -> None:
    """Punkt 52: die Hauptperiode liegt unter dem Slug; wer sie liest, braucht einen anderen Ordner."""
    (tmp_path / "settings.toml").write_text('[period]\ndictionary = "base"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="dictionary"):
        load_settings(cwd=tmp_path)  # Ordner des Profils = base_profile: es läse sich selbst
    (tmp_path / "settings.toml").write_text(
        'profile = ""\n[period]\ndictionary = "base"\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="dictionary"):
        load_settings(cwd=tmp_path)  # flach wäre kein eigener Ordner
    (tmp_path / "settings.toml").write_text(
        'profile = "alt"\n[period]\ndictionary = "base"\n', encoding="utf-8"
    )
    assert load_settings(cwd=tmp_path).period.dictionary == "base"
    (tmp_path / "settings.toml").write_text('[period]\ndictionary = "fremd"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="dictionary"):
        load_settings(cwd=tmp_path)


def test_first_page_defaults_to_one_and_must_be_positive(tmp_path: Path) -> None:
    assert load_settings(cwd=tmp_path).sources.oparl.first_page == 1
    (tmp_path / "settings.toml").write_text("[sources.oparl]\nfirst_page = 0\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="first_page"):
        load_settings(cwd=tmp_path)


def test_opendata_source_knows_district_files_and_the_precinct_file_name(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path).sources.opendata
    assert base.district_shapes_url == "" and base.district_results_url == ""
    assert base.districts_file == "Stimmbezirke_2025.geojson"
    (tmp_path / "settings.toml").write_text(
        '[sources.opendata]\ndistricts_file = "a/b.geojson"\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="districts_file"):
        load_settings(cwd=tmp_path)


def _crosswalk_profile(extra: str = "") -> str:
    return (
        'profile = "alt"\n[period]\ndictionary = "base"\n'
        '[columns.results]\ndistrict = ""\nprecinct = "gebiet-nr"\n'
        'precinct_name = "gebiet-name"\neligible = "A"\n'
        'voters = "B"\neligible_postal = "A2"\npostal_marker = "Briefwahl"\n'
        '[crosswalk]\nenabled = true\nprecinct_id = "Stimmbezchar"\n'
        'district_id = "Kommunalwahlbezirk"\ndistrict_name = "Name"\n' + extra
    )


def test_results_without_district_column_need_crosswalk_and_precinct_keys(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('[columns.results]\ndistrict = ""\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="crosswalk"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(_crosswalk_profile(), encoding="utf-8")
    columns = load_settings(cwd=tmp_path).columns.results
    assert (columns.district, columns.precinct, columns.eligible_postal, columns.postal_marker) == (
        "",
        "gebiet-nr",
        "A2",
        "Briefwahl",
    )
    without_marker = _crosswalk_profile().replace('postal_marker = "Briefwahl"\n', "")
    (tmp_path / "settings.toml").write_text(without_marker, encoding="utf-8")
    with pytest.raises(ValidationError, match="postal_marker"):
        load_settings(cwd=tmp_path)
    without_name = _crosswalk_profile().replace('precinct_name = "gebiet-name"\n', "")
    (tmp_path / "settings.toml").write_text(without_name, encoding="utf-8")
    with pytest.raises(ValidationError, match="precinct_name"):
        load_settings(cwd=tmp_path)


def test_crosswalk_names_the_properties_of_the_old_geojson_files(tmp_path: Path) -> None:
    """Der alte Zuschnitt bringt seine Eigenschaftsnamen mit; ``[columns]`` bleibt der Zielzuschnitt."""
    base = load_settings(cwd=tmp_path).crosswalk
    assert (base.precinct_id, base.district_id, base.district_name) == ("", "", "")
    (tmp_path / "settings.toml").write_text(_crosswalk_profile(), encoding="utf-8")
    settings = load_settings(cwd=tmp_path)
    assert settings.crosswalk.precinct_id == "Stimmbezchar"
    assert (settings.crosswalk.district_id, settings.crosswalk.district_name) == (
        "Kommunalwahlbezirk",
        "Name",
    )
    # Der Zielzuschnitt behält die Spalten der Hauptperiode, sonst fände die Seite keine Namen.
    assert settings.columns.district_name == "Kommunalwahlbezirk Name"
    without_id = _crosswalk_profile().replace('district_id = "Kommunalwahlbezirk"\n', "")
    (tmp_path / "settings.toml").write_text(without_id, encoding="utf-8")
    with pytest.raises(ValidationError, match="crosswalk.district_id"):
        load_settings(cwd=tmp_path)


def test_crosswalk_needs_base_dictionary_and_counts_to_the_fingerprint(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    assert base.crosswalk.enabled is False and base.crosswalk.min_coverage == 0.95
    assert base.crosswalk.target_file == "Stimmbezirke_2025.geojson"
    (tmp_path / "settings.toml").write_text(
        _crosswalk_profile().replace('dictionary = "base"', 'dictionary = "own"'), encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="crosswalk"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(_crosswalk_profile(), encoding="utf-8")
    enabled = load_settings(cwd=tmp_path)
    assert enabled.crosswalk.enabled and enabled.fingerprint() != base.fingerprint()
    (tmp_path / "settings.toml").write_text(
        _crosswalk_profile("min_coverage = 1.5\n"), encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="min_coverage"):
        load_settings(cwd=tmp_path)


def test_compare_period_is_a_profile_name_not_the_own_one(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    assert base.compare.period == ""
    (tmp_path / "settings.toml").write_text('[compare]\nperiod = "2014-2020"\n', encoding="utf-8")
    compared = load_settings(cwd=tmp_path)
    assert compared.compare.period == "2014-2020" and compared.fingerprint() != base.fingerprint()
    (tmp_path / "settings.toml").write_text('[compare]\nperiod = "../x"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="compare"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        'profile = "alt"\n[compare]\nperiod = "alt"\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="compare"):
        load_settings(cwd=tmp_path)


def test_labels_and_file_names_stay_out_of_the_fingerprint(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text(
        '[period]\nlabel = "Anders"\n[sources.opendata]\ndistricts_file = "x.geojson"\n'
        '[crosswalk]\ntarget_file = "y.geojson"\n',
        encoding="utf-8",
    )
    renamed = load_settings(cwd=tmp_path)
    assert renamed.period.label == "Anders" and renamed.fingerprint() == base.fingerprint()


# --- Option 01: was eine zweite Stadt nicht hat -----------------------------------------------


def test_a_second_city_needs_neither_context_data_nor_a_number_pattern() -> None:
    """Nicht jede Stadt hat einen Quartiersatlas, und nicht jedes RIS nennt das Gremium in der Nummer.

    Mönchengladbach veröffentlicht keinen Datensatz je Raumeinheit (Option 03), und seine
    Drucksachennummern tragen kein Kürzel (``0682/XI``, Stichprobe 2026-10-12, Option 05):
    ``reference_pattern`` bleibt leer, und die Kontextschritte entfallen. Seit Punkt 58 kommen die
    Gremien dort aus der Beratungsfolge, und darum stehen die Kürzeltabellen trotzdem im Profil --
    der Validator erlaubt sie, sobald eine der beiden Quellen da ist.
    """
    settings = load_settings(profile="moenchengladbach", cwd=Path("/nonexistent"))
    assert settings.context.root is None and not settings.context.variables
    assert settings.bodies.reference_pattern == ""
    assert settings.bodies.organizations and settings.bodies.district_body == "BV"
    assert set(settings.bodies.district_body_names) == {"BV1", "BV2", "BV3", "BV4"}
    # Ohne beide Quellen bleiben die Tabellen verboten: ein Kürzel käme dann nie zustande.
    with pytest.raises(ValueError, match="kennt keine Kürzel"):
        Bodies(district_body="BV", council={"RAT": "Rat"})


# --- Option 02: die beiden Profildateien im Repo ----------------------------------------------

REPO = Path(__file__).resolve().parents[2]
NOWHERE = Path("/nonexistent")  # kein settings.local.toml dazwischen, die Datei allein zählt


def test_period_profile_describes_the_old_cut_and_its_own_data_root() -> None:
    settings = load_settings(profile="duesseldorf-2014", cwd=NOWHERE)
    assert settings.profile == "2014-2020"
    assert settings.reference_root == Path("snapshots/2014-2020")
    assert (settings.period.start, settings.period.end) == (date(2014, 5, 25), date(2020, 9, 12))
    assert settings.period.election_day == date(2020, 9, 13)
    assert settings.period.title == "Wahlperiode 2014 bis 2020"
    assert settings.period.dictionary == "base"
    assert settings.sources.oparl.first_page == 90 and not settings.sources.oparl.incremental
    assert settings.columns.results.encoding == "utf-8"
    assert settings.columns.results.district == "" and settings.crosswalk.enabled
    # Reihenfolge und Namen der Parteien wie in der Hauptperiode, nur andere Quellspalten.
    base = load_settings(cwd=NOWHERE)
    assert list(settings.columns.results.parties) == list(base.columns.results.parties)
    assert settings.columns.results.parties["GRUENE"] == "D3"
    assert all(url for url in (settings.sources.opendata.district_shapes_url,))


def test_the_two_profiles_differ_from_the_main_period_in_the_fingerprint() -> None:
    base = load_settings(cwd=NOWHERE)
    period = load_settings(profile="duesseldorf-2014", cwd=NOWHERE)
    compared = load_settings(profile="duesseldorf-vergleich", cwd=NOWHERE)
    # Der Vergleich rechnet die Hauptperiode, erbt also ihren Ordner (Punkt 52), und liest daneben
    # den der älteren Periode.
    assert compared.profile == base.profile == compared.base_profile
    assert compared.compare.period == period.profile
    prints = {base.fingerprint(), period.fingerprint(), compared.fingerprint()}
    assert len(prints) == 3


def test_period_profile_puts_everything_under_its_own_root(tmp_path: Path) -> None:
    settings = load_settings(profile="duesseldorf-2014", cwd=NOWHERE).model_copy(
        update={"data_root": tmp_path / "data", "cache_root": tmp_path / "cache"}
    )
    layout = Layout.from_settings(settings)
    assert layout.root == tmp_path / "data" / "2014-2020"
    assert layout.districts_geojson.name == "Stimmbezirke_2020.geojson"
    assert layout.texts == tmp_path / "cache" / "2014-2020" / "text" / "texts.parquet"
    # Der Zuschnitt der Hauptperiode liegt unter deren Slug, nicht flach (Punkt 52)
    target = layout.target_view(settings)
    own = tmp_path / "data" / settings.base_profile
    assert target.districts_geojson == own / "external" / "Stimmbezirke_2025.geojson"


# --- Option 01: Paketprofile ------------------------------------------------------------------


def _package_profile(folder: Path, slug: str, body: str = "") -> Path:
    """Ein Profil im Testordner, das auf dem echten Stadtprofil aufsetzt.

    Seit die Düsseldorfer Werte im Profil stehen, nennt ein vollständiges Profil Quellen, Spalten,
    Gremien, Fremddaten und Urheber; ein Testprofil erbt sie mit ``base`` und überschreibt nur, was
    es zeigen will (Option 01, ``profile_chain``).
    """
    package = Path(str(profiles_folder() / "duesseldorf.toml"))
    (folder / "duesseldorf.toml").write_text(package.read_text(encoding="utf-8"), encoding="utf-8")
    path = folder / f"{slug}.toml"
    path.write_text(
        f'base = "duesseldorf"\nprofile = "{slug}"\n'
        f'[city]\nslug = "{slug}"\nname = "Teststadt"\ngenitive = "Teststadts"\n'
        f'adjective = "Teststädter"\nags = "05000000"\npublisher = "Stadt Teststadt"\n' + body,
        encoding="utf-8",
    )
    return path


def test_default_profile_is_duesseldorf_and_lies_under_its_slug(tmp_path: Path) -> None:
    s = load_settings(cwd=tmp_path)
    assert s.default_profile == "duesseldorf" and s.city.slug == "duesseldorf"
    assert s.profile == "duesseldorf"  # Punkt 52: ein Slug für jede Stadt, auch für diese
    assert s.city.name == "Düsseldorf" and s.city.ags == "05111000"
    assert [source.name for source in s.report.sources] and all(
        source.url.startswith("https://") for source in s.report.sources
    )
    assert s.publish.cities == ["duesseldorf", "moenchengladbach"]


def test_the_default_profile_keeps_every_value_of_the_thesis(tmp_path: Path) -> None:
    """Die Werte, die aus defaults.toml ins Profil gezogen sind, kommen unverändert wieder heraus.

    Der Golden Master der Kette hängt an jedem einzelnen davon; am 2026-10-12 war der Vergleich
    der gemischten TOML-Schichten vor und nach dem Umzug leer (kein Schlüssel verloren, keiner
    geändert). Geprüft werden die Werte, nicht die Menge der Schlüssel: jede weitere Option legt
    hier welche dazu.
    """
    settings = load_settings(cwd=tmp_path)
    assert (settings.period.start, settings.period.end) == (date(2020, 9, 13), date(2025, 9, 14))
    assert settings.sources.oparl.endpoint.endswith("/bodies/0015/papers")
    assert settings.sources.wikidata.entity == "Q1718"
    assert settings.sources.opendata.results_file == "Stimmbezirk_Wahlergebnis.csv"
    assert settings.sources.opendata.districts_file == "Stimmbezirke_2025.geojson"
    columns = settings.columns
    assert (columns.district_id, columns.district_name, columns.precinct_id) == (
        "Kommunalwahlbezirk Nr.",
        "Kommunalwahlbezirk Name",
        "Stimm-/ Wahlbezirk",
    )
    assert (columns.results.sep, columns.results.encoding) == (";", "latin-1")
    assert columns.results.district == "Kommunalwahlbezirk"
    assert columns.results.eligible == "Wahlberechtigte_insgesamt"
    assert columns.results.voters == "Waehler"
    assert columns.results.parties == {
        "CDU": "CDU_Stimmen",
        "GRUENE": "GRUENE_Stimmen",
        "SPD": "SPD_Stimmen",
        "FDP": "FDP_Stimmen",
        "Die_Linke": "Die_Linke_Stimmen",
        "AfD": "AfD_Stimmen",
    }
    precincts = settings.precincts
    assert (precincts.enabled, precincts.format) == (True, "geojson")
    assert precincts.id_property == "Stimm-/ Wahlbezirk"
    assert precincts.district_property == "Kommunalwahlbezirk Nr."
    assert precincts.name_property == "Kommunalwahlbezirk Name"
    assert columns.results.party_names == {
        "GRUENE": "Bündnis 90/Die Grünen",
        "Die_Linke": "Die Linke",
    }
    assert columns.results.precinct == "gebietnr"
    assert settings.search.text_split_marker == "betrifft"
    assert settings.search.hide_in_display == ["schulweg"]
    assert len(settings.search.exclude) == 63 and "Düsseldorf" in settings.search.exclude
    assert settings.analysis.exclude_districts == [1, 10]
    # Option 03 bis 06 haben ihre Tabellen mitgebracht; auch sie stehen jetzt im Profil
    assert settings.bodies.district_body and settings.context.variables
    assert settings.originators.parties


def test_profile_argument_selects_a_package_profile_between_defaults_and_files(
    tmp_path: Path,
) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    _package_profile(profiles, "test-stadt")
    (tmp_path / "settings.toml").write_text("[sources.oparl]\ndelay_s = 9\n", encoding="utf-8")
    s = load_settings(cwd=tmp_path, profile="test-stadt", profiles_dir=profiles)
    assert s.profile == "test-stadt" and s.city.slug == "test-stadt"
    assert s.search.text_split_marker == "betrifft"  # aus dem Stadtprofil geerbt (base)
    assert s.sources.oparl.delay_s == 9  # settings.toml über dem Profil
    assert s.sources.oparl.endpoint  # alles andere kommt aus defaults.toml
    (tmp_path / "settings.toml").write_text(
        '[search]\ntext_split_marker = "aus-datei"\n', encoding="utf-8"
    )
    assert (
        load_settings(
            cwd=tmp_path, profile="test-stadt", profiles_dir=profiles
        ).search.text_split_marker
        == "aus-datei"
    )


def test_default_profile_key_in_a_file_selects_the_profile(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    _package_profile(profiles, "test-stadt")
    (tmp_path / "settings.local.toml").write_text(
        'default_profile = "test-stadt"\n', encoding="utf-8"
    )
    assert load_settings(cwd=tmp_path, profiles_dir=profiles).city.slug == "test-stadt"


def test_unknown_profile_names_the_available_ones(tmp_path: Path) -> None:
    with pytest.raises(UnknownProfileError, match="duesseldorf"):
        load_settings(cwd=tmp_path, profile="gibtsnicht")
    assert "duesseldorf" in available_profiles()


def test_every_package_profile_has_its_own_folder_and_the_city_keeps_its_slug() -> None:
    """Punkt 52: ``base_profile`` ist der Slug, also muss die Hauptperiode dort liegen.

    Sonst wäre die Zusage eine Lüge: ein Periodenprofil mit ``period.dictionary = "base"`` suchte
    das Wörterbuch in einem Ordner, in dem niemand rechnet. Zwei Profile dürfen sich einen Ordner
    teilen, wenn eines das andere nur um einen Schritt erweitert (der Vergleich die Hauptperiode).
    """
    cities: dict[str, str] = {}  # Ordner -> Stadt, die darin rechnet
    for name in available_profiles():
        settings = load_settings(profile=name, cwd=NOWHERE)
        assert settings.base_profile == settings.city.slug
        if settings.period.dictionary == "base":
            assert settings.profile not in ("", settings.base_profile), name
        else:
            assert settings.profile == settings.base_profile, name
        # Zwei Profile in einem Ordner sind nur dieselbe Stadt (Hauptperiode und ihr Vergleich);
        # zwei Städte darin überschrieben sich gegenseitig (Review 2026-10-13, Befund 5).
        assert cities.setdefault(settings.profile, settings.city.slug) == settings.city.slug, name
    assert cities == {
        "duesseldorf": "duesseldorf",
        "2014-2020": "duesseldorf",
        "2025": "duesseldorf",
        "moenchengladbach": "moenchengladbach",
    }


def test_profile_slug_must_match_the_file_name(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    content = _package_profile(profiles, "b").read_text(encoding="utf-8")
    (profiles / "b.toml").unlink()
    (profiles / "a.toml").write_text(content, encoding="utf-8")
    with pytest.raises(SchemaError, match="city.slug"):
        load_settings(cwd=tmp_path, profile="a", profiles_dir=profiles)


def test_a_city_profile_must_use_its_slug_as_its_folder(tmp_path: Path) -> None:
    """Punkt 52 zur Ladezeit: ``Settings.base_profile`` ist der Slug, also muss er der Ordner sein.

    Der Slug steht in einem Stadtprofil zweimal -- als ``profile`` (der Ordner) und als
    ``city.slug`` (der Name). Dass beide zusammenpassen, prüft das Laden und nicht erst ein Test
    über das Paket (Review 2026-10-13, Befund 11).
    """
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    path = _package_profile(profiles, "test-stadt")
    path.write_text(
        path.read_text(encoding="utf-8").replace('profile = "test-stadt"', 'profile = "anders"'),
        encoding="utf-8",
    )
    with pytest.raises(SchemaError, match="unter ihrem Slug"):
        load_settings(cwd=tmp_path, profile="test-stadt", profiles_dir=profiles)


def test_environment_selects_the_profile_but_never_sets_the_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEOREP_PROFILE", "duesseldorf")
    s = load_settings(cwd=tmp_path)
    # Die Variable wählt das Profil; den Ordner setzt das Profil selbst (hier sein Slug)
    assert s.city.slug == "duesseldorf" and s.profile == s.city.slug
    monkeypatch.setenv("GEOREP_PROFILE", "gibtsnicht")
    with pytest.raises(UnknownProfileError):
        load_settings(cwd=tmp_path)
    assert load_settings(cwd=tmp_path, profile="duesseldorf").city.slug == "duesseldorf"


def test_only_prefixed_variables_reach_the_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jede Umgebungsvariable von georep traegt GEOREP_; eine nackte setzt nichts.

    Der Alias am Feld ``profile`` haelt GEOREP_PROFILE davon ab, den Unterordner zu setzen (das
    waehlt nur das Profil). Er darf dabei nicht das Praefix umgehen (Review 2026-10-12).
    """
    monkeypatch.setenv("PROFILE_FOLDER", "fremd")
    settings = load_settings(cwd=tmp_path)
    assert settings.profile == settings.city.slug  # der Slug aus dem Profil, nicht „fremd"
    monkeypatch.setenv("GEOREP_PROFILE_FOLDER", "eigen")
    assert load_settings(cwd=tmp_path).profile == "eigen"


def test_fingerprint_sees_city_sources_and_publish_but_not_the_selector(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text('default_profile = "duesseldorf"\n', encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() == base.fingerprint()
    (tmp_path / "settings.toml").write_text('[city]\nname = "Anders"\n', encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() != base.fingerprint()
    (tmp_path / "settings.toml").write_text("[publish]\ncities = []\n", encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() != base.fingerprint()


def test_publish_cities_are_plain_unique_slugs(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text(
        '[publish]\ncities = ["duesseldorf", "duesseldorf"]\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="publish.cities"):
        load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text('[publish]\ncities = ["../x"]\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="publish.cities"):
        load_settings(cwd=tmp_path)


# --- Option 07: Monitoring -------------------------------------------------------------------


def test_report_and_bootstrap_switches_stay_out_of_the_fingerprint(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    assert base.bootstrap.seed_corpus and base.report.regression
    # Stadtneutral ist der Link leer; das Profil Düsseldorfs setzt ihn, seit snapshots/2025 im
    # Repo liegt und auch GitHub Pages die Unterseite baut (Punkt 56, 2026-10-14).
    assert base.report.monitoring_url == "2025/"
    (tmp_path / "settings.toml").write_text(
        "[bootstrap]\nseed_corpus = false\n[report]\nregression = false\n"
        'monitoring_url = "laufend/"\n',
        encoding="utf-8",
    )
    switched = load_settings(cwd=tmp_path)
    assert not switched.bootstrap.seed_corpus and not switched.report.regression
    assert switched.report.monitoring_url == "laufend/"
    assert switched.fingerprint() == base.fingerprint()  # Anzeige, kein Parquet-Ergebnis


def test_only_a_city_profile_links_the_page_of_the_current_period(tmp_path: Path) -> None:
    """Punkt 56: der Link steht auf der Stadtseite, denn nur dort liegt die Unterseite daneben.

    ``pages.yml`` und ``deploy/bin/georep-monitor.sh`` legen die laufende Periode nach
    ``<stadt>/site/<profil>/``. Von einer Unterseite aus zeigte ``2025/`` darum in einen Ordner,
    den es nicht gibt (``2014-2020/2025/``), oder auf sich selbst.
    """
    links = {
        name: load_settings(profile=name, cwd=tmp_path).report.monitoring_url
        for name in available_profiles()
    }
    assert links == {
        "duesseldorf": "2025/",
        "duesseldorf-vergleich": "2025/",  # dieselbe Seite, nur mit einem Schritt mehr
        "duesseldorf-2014": "",
        "duesseldorf-2025": "",
        "moenchengladbach": "",
    }
    # Der Link zeigt auf den Ordner eines Profils, das es wirklich gibt
    monitor = load_settings(profile="duesseldorf-2025", cwd=tmp_path)
    assert links["duesseldorf"] == f"{monitor.profile}/"


def test_monitoring_url_must_be_a_relative_link(tmp_path: Path) -> None:
    for bad in ("https://example.invalid/2025/", "//example.invalid/2025/"):
        (tmp_path / "settings.toml").write_text(
            f'[report]\nmonitoring_url = "{bad}"\n', encoding="utf-8"
        )
        with pytest.raises(ValidationError, match="nur ein relativer Link"):
            load_settings(cwd=tmp_path)


def test_profile_2025_is_an_open_period_seeded_from_its_own_snapshot(tmp_path: Path) -> None:
    s = load_settings(profile="duesseldorf-2025", cwd=tmp_path)
    assert s.profile == "2025" and s.default_profile == "duesseldorf-2025"
    assert s.city.name == "Düsseldorf"  # base = "duesseldorf": dieselbe Stadt, andere Periode
    assert s.period.dictionary == "base"  # Straßen und Orte der Hauptperiode, eingefroren
    assert s.context.root is None and s.topics.k == 0  # was die Regression braucht, entfällt
    assert s.period.start == date(2025, 9, 15) and s.period.end is None
    assert s.period.election_day == date(2025, 9, 14)
    # Punkt 56: die Referenz dieses Profils ist sein eigener Schnappschuss, nicht der Korpus der
    # Arbeit -- darum darf und soll ``bootstrap`` die Stores daraus füllen (nur leere).
    assert s.reference_root == Path("snapshots/2025")
    assert s.bootstrap.seed_corpus and not s.report.regression
    assert s.report.monitoring_url == ""  # diese Seite *ist* die laufende Periode
    # Alles andere bleibt wie im Stadtprofil: Quellen, Suche
    assert s.sources.oparl.endpoint.endswith("/bodies/0015/papers")
    assert s.sources.oparl.stop_when_older and s.sources.oparl.incremental
    assert len(s.search.exclude) == 63
    assert s.fingerprint() != load_settings(cwd=tmp_path).fingerprint()  # andere Periode


# --- Punkt 46: die Klassengrenzen der divergierenden Varianten -------------------------------------


def test_diverging_boundaries_must_be_four_ascending_and_hold_the_middle() -> None:
    """Review-Befund 21: vier aufsteigende Grenzen, und die mittlere Klasse enthält das Mittel."""
    from pydantic import ValidationError

    from georep.settings import Diverging

    assert Diverging().district_percent == [-0.25, -0.10, 0.10, 0.25]
    for field, broken in (
        ("district_percent", [-0.25, -0.10, 0.10]),  # nur drei Grenzen
        ("party_points", [-0.02, 0.005, -0.005, 0.02]),  # nicht aufsteigend
        ("district_percent", [0.10, 0.20, 0.30, 0.40]),  # 0 liegt nicht in der Mitte
        ("party_points", [-0.04, -0.03, -0.02, -0.01]),  # alles unter 0
        ("party_ratio", [0.1, 0.2, 0.3, 0.4]),  # 1 liegt nicht in der Mitte
    ):
        with pytest.raises(ValidationError):
            Diverging(**{field: broken})
    # Das Verhältnis darf die Mitte um 1 legen, nicht um 0
    assert Diverging(party_ratio=[0.25, 0.75, 1.5, 3.0]).party_ratio[1] == 0.75
