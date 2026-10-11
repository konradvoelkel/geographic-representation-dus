from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from georep.layout import Layout
from georep.settings import Period, deep_merge, load_settings, settings_files


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
    ):
        (tmp_path / "settings.toml").write_text(f"[topics]\n{bad}\n", encoding="utf-8")
        with pytest.raises(ValidationError, match="topics"):
            load_settings(cwd=tmp_path)


def test_fingerprint_sees_weights_and_topics(tmp_path: Path) -> None:
    base = load_settings(cwd=tmp_path)
    (tmp_path / "settings.toml").write_text("[topics]\nk = 5\n", encoding="utf-8")
    assert load_settings(cwd=tmp_path).fingerprint() != base.fingerprint()
    (tmp_path / "settings.toml").write_text('[weights]\ncombined = ["idf"]\n', encoding="utf-8")
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
    assert len(o.admin_types) == 8 and len(o.citizen_types) == 2
    # Die längsten Antragspräfixe zuerst, sonst bleibt von „Haushaltsantrag CDU/Grüne" ein Rest
    assert o.motion_prefixes[0] == "Haushaltsantrag"
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


def test_base_dictionary_needs_a_profile(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('[period]\ndictionary = "base"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="dictionary"):
        load_settings(cwd=tmp_path)
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


# --- Option 02: die beiden Profildateien im Repo ----------------------------------------------

REPO = Path(__file__).resolve().parents[2]
NOWHERE = Path("/nonexistent")  # kein settings.local.toml dazwischen, die Datei allein zählt


def test_period_profile_describes_the_old_cut_and_its_own_data_root() -> None:
    settings = load_settings(explicit=REPO / "settings.2014.toml", cwd=NOWHERE)
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
    period = load_settings(explicit=REPO / "settings.2014.toml", cwd=NOWHERE)
    compared = load_settings(explicit=REPO / "settings.vergleich.toml", cwd=NOWHERE)
    assert compared.profile == "" and compared.compare.period == period.profile
    prints = {base.fingerprint(), period.fingerprint(), compared.fingerprint()}
    assert len(prints) == 3


def test_period_profile_puts_everything_under_its_own_root(tmp_path: Path) -> None:
    settings = load_settings(explicit=REPO / "settings.2014.toml", cwd=NOWHERE).model_copy(
        update={"data_root": tmp_path / "data", "cache_root": tmp_path / "cache"}
    )
    layout = Layout.from_settings(settings)
    assert layout.root == tmp_path / "data" / "2014-2020"
    assert layout.districts_geojson.name == "Stimmbezirke_2020.geojson"
    assert layout.texts == tmp_path / "cache" / "2014-2020" / "text" / "texts.parquet"
    target = layout.for_profile("", settings.crosswalk.target_file)
    assert target.districts_geojson == tmp_path / "data" / "external" / "Stimmbezirke_2025.geojson"
