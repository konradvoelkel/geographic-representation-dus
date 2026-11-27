"""Die Settings von Vorhaben 22: ``[context.need]`` mit Quellen, Band, Klassen und Hypothesen.

Die Quellen sind bundes- oder landesweit und stehen in ``defaults.toml``; das Stadtprofil schaltet
ein (Messdokument ``docs/plans/22-bedarf.md``, § 6 und § 10). Ein eingeschalteter Block ohne Archiv
soll beim Laden auffallen, nicht erst im Netzschritt.
"""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import georep.settings as gs
from georep.settings import Settings, archive_name, load_settings

NOWHERE = Path("/nonexistent")


def _need(settings: Settings, **update: Any) -> Settings:
    need = settings.context.need.model_copy(update=update)
    context = settings.context.model_copy(update={"need": need})
    return settings.model_copy(update={"context": context})


def test_the_switch_is_off_and_the_block_sits_at_the_end_of_context() -> None:
    need = gs.NeedSettings()
    assert need.enabled is False
    assert need.package is None
    assert (need.band_m, need.permutations, need.bootstrap, need.seed) == (20.0, 10_000, 2_000, 22)
    assert list(gs.ContextSettings.model_fields)[-1] == "need"


def test_need_data_has_its_own_switch_outside_the_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review 2026-11-24, N1: der Netzschritt hat einen eigenen Schalter wie ``council.enabled``.

    Er ist aus, auch im Stadtprofil; er steht nicht im Fingerprint, damit ein Abruf die Kette nicht
    neu rechnen lässt, und eine Umgebungsvariable schaltet ihn für eine Shell ein.
    """
    monkeypatch.delenv("GEOREP_CONTEXT__NEED__FETCH", raising=False)
    assert gs.NeedSettings().fetch is False
    settings = load_settings(cwd=NOWHERE)
    assert settings.context.need.enabled and settings.context.need.fetch is False
    assert _need(settings, fetch=True).fingerprint() == settings.fingerprint()
    monkeypatch.setenv("GEOREP_CONTEXT__NEED__FETCH", "true")
    switched = load_settings(cwd=NOWHERE)
    assert switched.context.need.fetch is True
    assert switched.context.need.hypotheses == settings.context.need.hypotheses


def test_the_profile_names_the_districts_of_the_robustness_in_each_hypothesis() -> None:
    """§ 8: alle drei auch ohne die Wahlbezirke 1 und 10, vorab festgelegt (Review 2026-11-24, N8)."""
    settings = load_settings(cwd=NOWHERE)
    assert [h.robust_without for h in settings.context.need.hypotheses] == [[1, 10]] * 3
    changed = settings.model_copy(
        update={"analysis": settings.analysis.model_copy(update={"exclude_districts": [2]})}
    )
    assert changed.context.need.hypotheses == settings.context.need.hypotheses


def test_the_defaults_name_the_sources_but_no_city() -> None:
    text = resources.files("georep").joinpath("defaults.toml").read_text(encoding="utf-8")
    block = tomllib.loads(text)["context"]["need"]
    assert block["enabled"] is False
    assert block["hypotheses"] == [] and block["explore"] == []
    assert block["classes"] == {"traffic": [], "youth": []}
    assert len(block["accidents"]["archives"]) == 6  # 2020 bis 2025, die Hauptperiode
    assert block["schools"]["forms"] == ["02"]
    for part in ("accidents", "grid", "schools"):
        assert block[part]["attribution"]["license_url"] == "https://www.govdata.de/dl-de/by-2-0"


def test_every_archive_has_its_own_file_name() -> None:
    need = load_settings(cwd=NOWHERE).context.need
    names = [archive_name(url) for url in need.archive_urls()]
    assert len(names) == 10 and len(set(names)) == 10
    assert names[0] == "Unfallorte2020_EPSG25832_CSV.zip"
    assert names[-2:] == ["schuldaten.csv", "schulliste_sj_25_26_open_data.csv"]


def test_archive_name_decodes_the_last_part_of_the_path() -> None:
    assert archive_name("https://example.org/a/b%C3%BC.csv?x=1") == "bü.csv"
    assert archive_name("https://example.org/") == ""


def test_switched_on_without_an_archive_is_an_error_naming_the_key() -> None:
    with pytest.raises(ValidationError, match=r"accidents\.archives"):
        gs.NeedSettings(enabled=True)


def test_two_archives_with_the_same_file_name_are_an_error() -> None:
    need = load_settings(cwd=NOWHERE).context.need
    twice = need.accidents.model_copy(
        update={"archives": ["https://a.org/x.zip", "https://b.org/x.zip"]}
    )
    with pytest.raises(ValidationError, match="Dateinamen"):
        gs.NeedSettings.model_validate(
            {**need.model_dump(), "enabled": True, "accidents": twice.model_dump()}
        )


def test_hypothesis_names_are_unique_and_the_alternative_is_known() -> None:
    base = {"need": "x", "attention": "y", "alternative": "greater", "fixed": "abc1234"}
    with pytest.raises(ValidationError, match="doppelt"):
        gs.NeedSettings(hypotheses=[{"name": "H1", **base}, {"name": "H1", **base}])  # type: ignore[list-item]
    with pytest.raises(ValidationError):
        gs.NeedHypothesis(name="H1", **{**base, "alternative": "less"})  # type: ignore[arg-type]


def test_an_empty_package_is_no_package() -> None:
    assert gs.NeedSettings(package="").package is None  # type: ignore[arg-type]
    assert gs.NeedSettings(package="snapshots/x").package == Path("snapshots/x")  # type: ignore[arg-type]


def test_package_and_attribution_do_not_count_but_the_band_does() -> None:
    settings = load_settings(cwd=NOWHERE)
    before = settings.fingerprint()
    assert _need(settings, package=Path("anderswo")).fingerprint() == before
    attribution = settings.context.need.accidents.attribution.model_copy(update={"stand": "neu"})
    accidents = settings.context.need.accidents.model_copy(update={"attribution": attribution})
    assert _need(settings, accidents=accidents).fingerprint() == before
    assert _need(settings, band_m=10.0).fingerprint() != before
    archives = settings.context.need.accidents.model_copy(
        update={"archives": ["https://a.org/x.zip"]}
    )
    assert _need(settings, accidents=archives).fingerprint() != before


def test_every_attribution_says_what_is_changed() -> None:
    """V5 (docs/plan-zeigen-2026-11.md, § 4; docs/todo.md, Punkt 16): dl-de/by-2-0 verlangt einen
    Veränderungshinweis im Quellenvermerk, wo die Daten bearbeitet sind. Alle drei Bedarfsquellen
    sind auf die Gemeinde zugeschnitten und je Wahlbezirk umgerechnet; das Feld sagt es, leer
    hieße unverändert. Es ist Anzeige und zählt nicht zum Fingerprint."""
    assert gs.NeedAttribution().modified == ""
    settings = load_settings(cwd=NOWHERE)
    need = settings.context.need
    for source in (need.accidents, need.grid, need.schools):
        assert source.attribution.modified.startswith("verändert: ")
    attribution = need.grid.attribution.model_copy(update={"modified": "verändert: anders"})
    grid = need.grid.model_copy(update={"attribution": attribution})
    assert _need(settings, grid=grid).fingerprint() == settings.fingerprint()


def test_the_day_of_the_fixing_is_shown_but_does_not_count() -> None:
    """Stufe 3 (Messdokument § 7): die Seite sagt „vorab festgelegt am 2026-11-23, Commit
    67f7250". Der Commit zählt zum Fingerprint wie bisher, der Tag ist Anzeige."""
    import datetime as dt

    settings = load_settings(cwd=NOWHERE)
    hypotheses = settings.context.need.hypotheses
    assert [(h.fixed, h.fixed_on) for h in hypotheses] == [("67f7250", dt.date(2026, 11, 23))] * 3
    moved = [h.model_copy(update={"fixed_on": dt.date(2026, 1, 1)}) for h in hypotheses]
    assert _need(settings, hypotheses=moved).fingerprint() == settings.fingerprint()
    assert (
        gs.NeedHypothesis(
            name="H", need="x", attention="y", alternative="greater", fixed="abc"
        ).fixed_on
        is None
    )
