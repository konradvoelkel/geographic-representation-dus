"""Die ganze Kette für ein Periodenprofil, offline auf der synthetischen Mini-Periode.

Erst läuft die Hauptperiode auf ``tests/fixtures/mini/``, dann das Profil aus
``settings.2014.toml`` auf ``tests/fixtures/mini-2014/`` mit derselben Datenwurzel: so liest es
das Wörterbuch und den Zielzuschnitt der Hauptperiode, wie es auf Konrads Rechner auch wäre. Die
Fixture ist erfunden (``tests/fixtures/mini-2014/README.md``); geprüft wird die Kette, nicht die
Wahl: dass die Zuordnung eine Zerlegung ist, dass die Summen der Wahlbezirks-CSV erhalten
bleiben, dass die Wählertabelle das Schema der Hauptperiode trägt und dass die Seite baut.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest

from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.pipeline import Outcome, build_steps, run_pipeline
from georep.prep.voters import (
    ELIGIBLE_TOTAL,
    PRECINCT,
    SOURCE_DISTRICT,
    VOTERS,
    read_results_csv,
)
from georep.settings import Settings, load_settings

REPO = Path(__file__).resolve().parents[2]
MINI_2014 = REPO / "tests" / "fixtures" / "mini-2014"
PROFILE = REPO / "settings.2014.toml"
NOWHERE = Path("/nonexistent")
TARGET_DISTRICTS = [1, 10, 38]
# Option 02 fügt ``precincts`` ein und lässt ``streets_osm`` und ``pois_wiki`` weg; welche
# Schritte es sonst gibt, bestimmen die anderen Optionen, darum kommt die Liste aus dem Register.
WITHOUT = ("streets_osm", "pois_wiki")


@dataclass(frozen=True)
class PeriodRun:
    settings: Settings
    layout: Layout
    base: Layout
    outcomes: list[Outcome]


@pytest.fixture(scope="module")
def period_run(
    tmp_path_factory: pytest.TempPathFactory, default_settings: Settings, mini_root: Path
) -> PeriodRun:
    root = tmp_path_factory.mktemp("period")
    base = Layout(root / "data", root / "cache", mini_root)
    bootstrap(base)
    run_pipeline(build_steps(default_settings, base), default_settings)
    settings = load_settings(explicit=PROFILE, cwd=NOWHERE).model_copy(
        update={
            "data_root": root / "data",
            "cache_root": root / "cache",
            "reference_root": MINI_2014,
        }
    )
    layout = Layout.from_settings(settings)
    report = bootstrap(layout, needs_dictionary=False)
    assert report.missing == [], report.summary()
    outcomes = run_pipeline(build_steps(settings, layout), settings)
    return PeriodRun(settings, layout, base, outcomes)


def test_the_profile_runs_every_offline_step_and_skips_them_on_the_second_run(
    period_run: PeriodRun,
) -> None:
    steps = build_steps(period_run.settings, period_run.layout)
    names = [s.name for s in steps]
    offline = {s.name for s in steps if not s.network}
    # Das Wörterbuch kommt von der Basis, darum fehlen die beiden Netzschritte
    assert not set(WITHOUT) & set(names)
    # Die Zuordnung steht unmittelbar vor den Wählern, die sie braucht
    assert names.index("precincts") == names.index("voters") - 1
    done = {o.step: o.status for o in period_run.outcomes if o.step in offline}
    assert set(done.values()) == {"ausgeführt"}, done
    again = run_pipeline(steps, period_run.settings)
    assert {o.status for o in again if o.step in offline} == {"übersprungen"}


def test_the_profile_writes_into_its_own_subfolder(period_run: PeriodRun) -> None:
    layout, base = period_run.layout, period_run.base
    assert layout.root == base.data_root / "2014-2020"
    assert layout.texts != base.texts and layout.texts.is_file()
    assert layout.site_index.is_file() and base.site_index.is_file()
    shared = set(layout.runtime_dirs()) & set(base.runtime_dirs())
    assert not shared


def test_the_assignment_is_a_partition_with_split_precincts(period_run: PeriodRun) -> None:
    frame = pl.read_parquet(period_run.layout.precinct_assignment)
    assert frame.columns == [
        PRECINCT,
        SOURCE_DISTRICT,
        "wahlbezirk_quelle_name",
        "wahlkreis_id",
        "anteil",
        "abdeckung",
    ]
    assert frame.get_column(PRECINCT).n_unique() == 26
    sums = frame.group_by(PRECINCT).agg(pl.col("anteil").sum())
    assert sums.get_column("anteil").to_list() == pytest.approx([1.0] * sums.height, abs=1e-9)
    assert sorted(set(frame.get_column("wahlkreis_id"))) == TARGET_DISTRICTS
    assert sorted(set(frame.get_column(SOURCE_DISTRICT))) == [101, 110, 138]
    # Die zwei mehrteiligen Stimmbezirke liegen in zwei Zielbezirken
    assert frame.height == 28
    assert frame.filter(pl.col("anteil") < 1.0).height == 4
    assert frame.get_column("abdeckung").min() == pytest.approx(1.0, abs=1e-9)
    assert all(name for name in frame.get_column("wahlbezirk_quelle_name").to_list())


def test_the_voters_table_has_the_schema_of_the_main_period(period_run: PeriodRun) -> None:
    got = pl.read_parquet(period_run.layout.voters)
    expected = pl.read_parquet(period_run.base.voters)
    assert got.schema == expected.schema
    assert got.get_column("wahlkreis_id").to_list() == TARGET_DISTRICTS
    # Die Stadtsumme der Wahlbezirks-CSV bleibt exakt erhalten, Wahlberechtigte wie Wähler
    columns = period_run.settings.columns.results
    districts = read_results_csv(period_run.layout.district_results_csv, columns)
    for column in (ELIGIBLE_TOTAL, VOTERS):
        total = int(
            districts.get_column(column).str.strip_chars().cast(pl.Int64, strict=False).sum()
        )
        assert int(got.get_column(column).sum()) == total
    turnout = got.get_column("wahlbeteiligung").to_list()
    assert all(0.0 < t < 1.0 for t in turnout)


def test_the_dictionary_comes_byte_identical_from_the_main_period(period_run: PeriodRun) -> None:
    assert period_run.layout.dictionary.read_bytes() == period_run.base.dictionary.read_bytes()
    assert (
        period_run.layout.streets_by_district.read_bytes()
        == period_run.base.streets_by_district.read_bytes()
    )


def test_the_period_page_builds_on_the_target_districts(period_run: PeriodRun) -> None:
    page = period_run.layout.site_index.read_text(encoding="utf-8")
    assert "13.09.2020" in page  # der Wahltag, dessen Ergebnis den Nenner liefert
    assert page.count('id="bezirk-') == len(TARGET_DISTRICTS)
    assert (period_run.layout.site / "karte.html").is_file()


def test_the_corpus_of_the_period_lies_inside_the_period(period_run: PeriodRun) -> None:
    dates = pl.read_parquet(period_run.layout.corpus, columns=["date"]).get_column("date").to_list()
    period = period_run.settings.period
    assert period.end is not None
    assert min(dates) >= period.start and max(dates) <= period.end
    assert len(dates) == 100
