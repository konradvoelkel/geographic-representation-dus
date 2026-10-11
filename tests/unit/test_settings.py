from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

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
