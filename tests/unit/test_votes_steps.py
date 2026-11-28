"""Der Beitrag von Vorhaben 28 im Register: ein Schritt hinter 26, Settings, Profile, Mini-Fixture.

Messdokument ``docs/plans/28-abstimmungen.md``, § 6 und § 10: der Schritt ``votes`` liest den
Beratungsverlauf von 26 (kein eigenes Paket, kein Netz) und schreibt drei Tabellen; an ist er, wo
das Paket von 26 die Punkte trägt (die drei Düsseldorfer Perioden), aus in der zweiten Stadt.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from georep.analysis.hypotheses import check_hypotheses
from georep.analysis.votes import (
    BODIES_SCHEMA,
    HYPOTHESES_SCHEMA,
    HYPOTHESIS_KEY,
    MAIN,
    R2,
    VOTES_SCHEMA,
    VOTES_SCHEMA_VERSION,
)
from georep.enrich import CONTRIBUTIONS
from georep.enrich.outcomes import outcome_files
from georep.enrich.votes import vote_files, vote_steps, votes_enabled, windows_of
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.settings import Period, Settings, Votes, VoteWindow, available_profiles, load_settings
from georep.stores import stored_schema_version
from tests.fakes import FakeSession

HTTP = FakeSession({})  # der Schritt ist offline und fragt nie
NOWHERE = Path("/nonexistent")


def _layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")


# --- Settings -------------------------------------------------------------------------------------
def test_die_vorgabe_ist_aus_und_traegt_die_wortregel() -> None:
    defaults = load_settings(profile="moenchengladbach", cwd=NOWHERE).votes
    assert not defaults.enabled
    assert [rule.result for rule in defaults.results] == [
        "zurueckgezogen",
        "vertagt",
        "verwiesen",
        "abgelehnt",
        "angenommen",
        "kenntnis",
        "erledigt",
    ]
    assert (defaults.threshold, defaults.min_units, defaults.alpha) == (0.25, 30, 0.05)
    assert (defaults.motion_type, defaults.motion_not) == ("antrag", "anfrage")


@pytest.mark.parametrize(
    ("profile", "on", "windows"),
    [
        ("duesseldorf", True, [MAIN]),
        ("duesseldorf-vergleich", True, [MAIN]),
        ("duesseldorf-2014", True, []),
        ("duesseldorf-2025", True, [R2]),
        ("moenchengladbach", False, []),
    ],
)
def test_an_wo_das_paket_von_26_die_punkte_traegt(
    profile: str, on: bool, windows: list[str]
) -> None:
    settings = load_settings(profile=profile, cwd=NOWHERE)
    assert votes_enabled(settings) is on
    assert [w.calculation for w in windows_of(settings)] == windows
    if on:
        assert settings.outcomes.package is not None  # das Paket trägt die Punkte (§ 10, Punkt 1)
        assert settings.votes.fixed == "97ebb52" and settings.votes.excluded_parties


def test_die_zeitraeume_sind_die_aus_paragraf_8_4_mit_der_mehrheit_am_beginn() -> None:
    settings = load_settings(cwd=NOWHERE)
    (main,) = windows_of(settings)
    assert (main.start, main.end, main.majority) == (
        dt.date(2021, 1, 1),
        dt.date(2025, 9, 14),
        frozenset({"CDU", "GRUENE"}),
    )
    (r2,) = windows_of(load_settings(profile="duesseldorf-2025", cwd=NOWHERE))
    assert (r2.start, r2.end, r2.majority) == (
        dt.date(2025, 12, 1),
        None,
        frozenset({"CDU", "GRUENE"}),
    )


@pytest.mark.parametrize(
    ("start", "end", "period_end", "inside"),
    [
        (dt.date(2021, 1, 1), dt.date(2025, 9, 14), dt.date(2025, 9, 14), True),
        (dt.date(2021, 1, 1), None, dt.date(2025, 9, 14), False),  # offen, die Periode nicht
        (dt.date(2021, 1, 1), dt.date(2025, 9, 15), dt.date(2025, 9, 14), False),
        (dt.date(2020, 9, 1), dt.date(2025, 9, 14), dt.date(2025, 9, 14), False),
        (dt.date(2025, 12, 1), None, None, True),
    ],
)
def test_ein_zeitraum_rechnet_nur_ganz_in_der_periode(
    start: dt.date, end: dt.date | None, period_end: dt.date | None, inside: bool
) -> None:
    period = Period(
        start=dt.date(2020, 9, 13), end=period_end, election=dt.date(2020, 9, 13), label="P"
    )
    assert VoteWindow(calculation="haupttest", start=start, end=end).within(period) is inside


@pytest.mark.parametrize(
    "broken",
    [
        {"enabled": True},  # ohne Wortregel
        {"unanimous": ["Einstimmig"]},  # Wörter klein
        {"results": [{"result": "vertagt", "words": ["a"]}, {"result": "vertagt", "words": ["b"]}]},
        {"results": [{"result": "vertagt", "words": []}]},
        {"windows": [{"calculation": "haupttest", "start": "2021-01-01"}]},  # ohne Commit
        {
            "motion_type": "antrag",
            "fixed": "x",
            "windows": [
                {"calculation": "R2", "start": "2021-01-01"},
                {"calculation": "R2", "start": "2022-01-01"},
            ],
        },
        {"windows": [{"calculation": "R2", "start": "2022-01-01", "end": "2021-01-01"}]},
    ],
)
def test_falsche_settings_fallen_beim_laden_auf(broken: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Votes.model_validate(broken)


def test_der_tag_der_festlegung_ist_anzeige_der_commit_zaehlt() -> None:
    settings = load_settings(cwd=NOWHERE)
    other_day = settings.model_copy(
        update={"votes": settings.votes.model_copy(update={"fixed_on": dt.date(2030, 1, 1)})}
    )
    other_commit = settings.model_copy(
        update={"votes": settings.votes.model_copy(update={"fixed": "0000000"})}
    )
    assert other_day.fingerprint() == settings.fingerprint()
    assert other_commit.fingerprint() != settings.fingerprint()


# --- Register -------------------------------------------------------------------------------------
def test_der_schritt_steht_hinter_26_und_liest_den_beratungsverlauf(
    tmp_path: Path, default_settings: Settings
) -> None:
    # hinter 28 steht seit Vorhaben 19 nur noch 19 (Plan der Phase „Zeigen“, § 10 Punkt 3 von 19)
    assert [c.name for c in CONTRIBUTIONS][-2:] == ["28-abstimmungen", "19-politikfelder"]
    layout = _layout(tmp_path)
    names = [s.name for s in build_steps(default_settings, layout)]
    assert names.index("council_results") < names.index("votes") < names.index("report")
    (step,) = vote_steps(default_settings, layout, HTTP)
    files = vote_files(layout)
    assert step.inputs == (
        outcome_files(layout).progress,
        layout.corpus,
        layout.document_originators,
    )
    assert step.outputs == (files.votes, files.bodies, files.hypotheses)
    assert step.schema_version == VOTES_SCHEMA_VERSION and not step.network


def test_ohne_zeitraum_liest_der_schritt_nur_den_beratungsverlauf(tmp_path: Path) -> None:
    settings = load_settings(profile="duesseldorf-2014", cwd=NOWHERE)
    layout = _layout(tmp_path)
    (step,) = vote_steps(settings, layout, HTTP)
    assert step.inputs == (outcome_files(layout).progress,)


def test_ohne_26_oder_schalter_fehlt_der_schritt(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    off = default_settings.model_copy(
        update={"outcomes": default_settings.outcomes.model_copy(update={"enabled": False})}
    )
    assert vote_steps(off, layout, HTTP) == []
    off = default_settings.model_copy(
        update={"votes": default_settings.votes.model_copy(update={"enabled": False})}
    )
    assert vote_steps(off, layout, HTTP) == []


@pytest.mark.parametrize("profile", available_profiles())
def test_der_schritt_steht_genau_wo_er_an_ist(tmp_path: Path, profile: str) -> None:
    settings = load_settings(profile=profile, cwd=NOWHERE).model_copy(
        update={"data_root": tmp_path / "data", "cache_root": tmp_path / "cache"}
    )
    names = [s.name for s in build_steps(settings, Layout.from_settings(settings))]
    assert ("votes" in names) is votes_enabled(settings)


# --- Mini-Fixture ---------------------------------------------------------------------------------
def test_die_mini_fixture_schreibt_drei_tabellen(
    mini_run: Layout, default_settings: Settings
) -> None:
    files = vote_files(mini_run)
    votes = pl.read_parquet(files.votes)
    bodies = pl.read_parquet(files.bodies)
    tests = pl.read_parquet(files.hypotheses)
    assert votes.schema == pl.Schema(VOTES_SCHEMA)
    assert bodies.schema == pl.Schema(BODIES_SCHEMA)
    assert tests.schema == pl.Schema(HYPOTHESES_SCHEMA)
    for path in files:
        assert stored_schema_version(path) == str(VOTES_SCHEMA_VERSION)
    progress = pl.read_parquet(outcome_files(mini_run).progress)
    assert votes.height == progress.filter(pl.col("top").is_not_null()).height
    assert bodies.get_column("punkte").sum() == votes.height
    check_hypotheses(tests, 0.05, key=HYPOTHESIS_KEY, strict=True, m=3)
    assert tests.filter(pl.col("rechnung") == MAIN).get_column("hypothese").to_list() == [
        "H28.1",
        "H28.2",
        "H28.3",
    ]
