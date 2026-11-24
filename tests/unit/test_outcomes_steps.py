"""Der Beitrag von Vorhaben 26 im Register: zwei Schritte, zwei Quellen, ein Paket.

``council_results`` liest den Netzlauf von Fundament F6 oder, wo er fehlt, das Paket aus
``georep pack --outcomes``; ``outcomes`` liest den Beratungsverlauf, die Rollen und Kanten von
Vorhaben 14 und die Antragsteller von Vorhaben 15 (``docs/plans/26-beschluesse.md``, § 6 und § 10).
Die Netzseite prüft die Fixture ``tests/fixtures/council/`` (ein Dutzend Paper aus dem Netzlauf der
Hauptperiode, geschwärzt), die Paketseite die Mini-Fixture, die mit dem Stadtprofil läuft.
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import polars as pl
import pytest

from georep.analysis.outcomes import (
    AGENDA_SCHEMA,
    AGENDA_SCHEMA_VERSION,
    OUTCOME_SCHEMA,
    PROGRESS_SCHEMA,
    SUCCESS_SCHEMA,
    UnknownResultError,
    classify_outcomes,
    progress,
)
from georep.bootstrap import bootstrap, bootstrap_from_settings
from georep.contracts import one_row_per_document
from georep.council import council_files
from georep.enrich import CONTRIBUTIONS
from georep.enrich.outcomes import (
    agenda_from_network,
    outcome_files,
    outcome_steps,
    read_agenda,
)
from georep.errors import MissingInputError
from georep.layout import Layout
from georep.pack import PackError, pack_outcomes
from georep.pipeline import Step, build_steps
from georep.settings import Settings
from tests.conftest import REPO
from tests.fakes import FakeSession
from tests.fixtures.make_council import BASE, PAPERS

HTTP = FakeSession({})  # beide Schritte sind offline und fragen nie
COUNCIL = REPO / "tests" / "fixtures" / "council"
PACKAGE = REPO / "snapshots" / "duesseldorf-beschluesse" / "raw"
IDS = sorted(BASE + key for key in PAPERS)
# Was die Regel aus der Fixture macht: Klasse, maßgeblicher Eintrag, Beratungen, Gremium.
EXPECTED = {
    "90981": ("zurueckgezogen", "zurückgezogen", 2, "OVA"),
    "100007": ("vertagt", "vertagt", 3, "KUA"),
    "108685": ("erledigt", "schriftlich beantwortet", 1, "BV9"),
    "89029": ("geaendert", "abweichend beschlossen", 3, "APS"),
    "100373": ("beschlossen", "einstimmig beschlossen", 2, "KUA"),
    "100041": ("beschlossen", "mehrheitlich beschlossen", 3, "RAT"),
    "90523": ("abgelehnt", "mehrheitlich abgelehnt", 1, "RAT"),
    "87916": ("ohne_ergebnis", None, 1, None),
    "94646": ("beschlossen", "einstimmig beschlossen", 4, "RAT"),
    "100162": ("beschlossen", "mehrheitlich beschlossen", 2, "SENR"),  # eine Beratung ohne Punkt
    "88452": ("ohne_ergebnis", None, 1, None),  # Haushaltssitzung 2021-02-05
    "101779": ("abgelehnt", "mehrheitlich abgelehnt", 1, "gr/400224"),  # Kürzel fehlt im Profil
}


def _layout(tmp_path: Path, *, network: bool = True, ids: list[str] = IDS) -> Layout:
    """Eine Datenwurzel mit Korpus (nur IDs und Datum) und, wenn verlangt, dem Netzlauf."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    layout.ensure_dirs()
    pl.DataFrame(
        {"id": ids, "date": [dt.date(2020, 11, 1)] * len(ids)},
        schema={"id": pl.String, "date": pl.Date},
    ).write_parquet(layout.corpus)
    if network:
        for name in ("meetings.jsonl", "agenda_items.jsonl", "consultations.jsonl"):
            shutil.copyfile(COUNCIL / name, layout.raw / name)
    return layout


def _steps(settings: Settings, layout: Layout) -> dict[str, Step]:
    return {s.name: s for s in outcome_steps(settings, layout, HTTP)}


# --- Register und Schalter ------------------------------------------------------------------------


def test_the_contribution_stands_behind_fourteen_and_fifteen(
    tmp_path: Path, default_settings: Settings
) -> None:
    names = [c.name for c in CONTRIBUTIONS]
    assert names.index("26-beschluesse") > names.index("14-vorgaenge") > -1
    assert names.index("26-beschluesse") > names.index("15-funktion")
    steps = [s.name for s in build_steps(default_settings, _layout(tmp_path, network=False))]
    assert steps.index("outcomes") == steps.index("council_results") + 1
    assert steps.index("council_results") > steps.index("procedures") > steps.index("cosponsors")
    assert steps.index("report") > steps.index("outcomes")


def test_the_switch_and_the_neighbours_decide_which_steps_exist(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path, network=False)
    assert list(_steps(default_settings, layout)) == ["council_results", "outcomes"]
    off = default_settings.outcomes.model_copy(update={"enabled": False})
    assert _steps(default_settings.model_copy(update={"outcomes": off}), layout) == {}
    # ohne Vorhaben 14 oder 15 steht nur der Beratungsverlauf da
    no_procedures = default_settings.procedures.model_copy(update={"enabled": False})
    alone = default_settings.model_copy(update={"procedures": no_procedures})
    assert list(_steps(alone, layout)) == ["council_results"]
    no_functions = default_settings.functions.model_copy(update={"enabled": False})
    alone = default_settings.model_copy(update={"functions": no_functions})
    assert list(_steps(alone, layout)) == ["council_results"]


def test_the_steps_read_what_they_need_and_write_under_processed(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path, network=False)
    steps = {s.name: s for s in outcome_steps(default_settings, layout, HTTP)}
    files = outcome_files(layout)
    council = council_files(layout)
    assert files.agenda == layout.raw / "tagesordnungspunkte.parquet"
    assert files.progress == layout.processed / "beratungsverlauf.parquet"
    assert steps["council_results"].inputs == (layout.corpus,)
    assert steps["council_results"].optional == (
        council.meetings,
        council.agenda_items,
        council.consultations,
        files.agenda,
    )
    assert steps["outcomes"].outputs == (files.outcomes, files.success)
    assert files.progress in steps["outcomes"].inputs
    assert layout.processed / "vorgang_kanten.parquet" in steps["outcomes"].inputs
    assert layout.processed / "dokumente_antragsteller.parquet" in steps["outcomes"].inputs
    # Punkt 58 behält seinen Namen: raw/beratungsfolge.parquet ist die Folge der Gremien
    assert files.progress.name != layout.consultations.name


# --- council_results: Netzlauf und Paket -----------------------------------------------------------


def test_the_network_run_gives_the_classes_of_the_measurement(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    step = _steps(default_settings, layout)["council_results"]
    line = step.run()
    assert "aus dem Netzlauf für 12 Dokumente" in line
    verlauf = pl.read_parquet(outcome_files(layout).progress)
    assert verlauf.schema == pl.Schema(PROGRESS_SCHEMA)
    corpus = pl.read_parquet(layout.corpus)
    base = classify_outcomes(corpus, verlauf, dict(default_settings.outcomes.results))
    found = {
        r["id"].removeprefix(BASE): (
            r["klasse"],
            r["result"],
            r["beratungen"],
            r["entscheidung_gremium"],
        )
        for r in base.iter_rows(named=True)
    }
    assert found == EXPECTED


def test_the_package_holds_what_the_network_run_gives(tmp_path: Path) -> None:
    """Für die Paper der Fixture steht im Paket der Hauptperiode genau, was der Netzlauf gibt."""
    agenda = agenda_from_network(_layout(tmp_path), IDS)
    packed = pl.read_parquet(PACKAGE / "tagesordnungspunkte-duesseldorf.parquet").filter(
        pl.col("id").is_in(IDS)
    )
    assert packed.equals(agenda)
    assert pl.read_parquet_metadata(PACKAGE / "tagesordnungspunkte-duesseldorf.parquet")[
        "georep.schema_version"
    ] == str(AGENDA_SCHEMA_VERSION)


def test_without_network_the_package_is_read(tmp_path: Path) -> None:
    layout = _layout(tmp_path, network=False)
    shutil.copyfile(
        PACKAGE / "tagesordnungspunkte-duesseldorf.parquet", outcome_files(layout).agenda
    )
    agenda, source = read_agenda(layout, IDS)
    assert source == "Paket" and agenda.get_column("id").unique().sort().to_list() == IDS
    network, source = read_agenda(_layout(tmp_path / "netz"), IDS)
    assert source == "Netzlauf" and network.equals(agenda)


def test_without_network_and_package_the_step_stops(tmp_path: Path) -> None:
    """Ein leerer Verlauf machte jedes Dokument still ``ohne_ergebnis``; das wäre falsch."""
    layout = _layout(tmp_path, network=False)
    with pytest.raises(MissingInputError, match=r"weder der Netzlauf .* noch das Paket"):
        read_agenda(layout, IDS)
    (layout.raw / "meetings.jsonl").write_text("", encoding="utf-8")  # ein halber Netzlauf
    with pytest.raises(MissingInputError, match="consultations.jsonl"):
        read_agenda(layout, IDS)


def test_an_unknown_entry_of_the_server_stops_the_step(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    known = dict(default_settings.outcomes.results)
    del known["zurückgezogen"]
    settings = default_settings.model_copy(
        update={"outcomes": default_settings.outcomes.model_copy(update={"results": known})}
    )
    with pytest.raises(UnknownResultError, match="'zurückgezogen'"):
        _steps(settings, layout)["council_results"].run()


# --- pack --outcomes und bootstrap ----------------------------------------------------------------


def test_pack_writes_the_table_under_the_name_of_the_profile(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    report = pack_outcomes(
        layout, default_settings, tmp_path / "paket", today=dt.date(2026, 11, 24)
    )
    name = "raw/tagesordnungspunkte-duesseldorf.parquet"
    assert [f.name for f in report.files] == [name]
    assert dict(report.figures)["Dokumente mit Beratung"] == 12
    packed = pl.read_parquet(tmp_path / "paket" / name)
    assert packed.schema == pl.Schema(AGENDA_SCHEMA)
    assert packed.equals(agenda_from_network(layout, IDS))
    assert (tmp_path / "paket" / "README.md").is_file()
    again = pack_outcomes(layout, default_settings, tmp_path / "paket")
    assert again.skipped == (name,)


def test_pack_refuses_an_incomplete_or_empty_run(
    tmp_path: Path, default_settings: Settings
) -> None:
    with pytest.raises(PackError, match="fehlen"):
        pack_outcomes(_layout(tmp_path / "a", network=False), default_settings, tmp_path / "p")
    layout = _layout(tmp_path / "b")
    council_files(layout).progress("meetings").write_text("{}", encoding="utf-8")
    with pytest.raises(PackError, match="Abruf unvollständig"):
        pack_outcomes(layout, default_settings, tmp_path / "p")
    empty = _layout(tmp_path / "c", ids=[BASE + "87916", BASE + "88452"])  # beide ohne Eintrag
    with pytest.raises(PackError, match="kein Tagesordnungspunkt"):
        pack_outcomes(empty, default_settings, tmp_path / "p")
    with pytest.raises(PackError, match="liegt in data_root"):
        pack_outcomes(layout, default_settings, layout.data_root / "paket")


def test_pack_refuses_an_entry_the_profile_does_not_know(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    known = dict(default_settings.outcomes.results)
    del known["vertagt"]
    settings = default_settings.model_copy(
        update={"outcomes": default_settings.outcomes.model_copy(update={"results": known})}
    )
    with pytest.raises(UnknownResultError, match="'vertagt'"):
        pack_outcomes(layout, settings, tmp_path / "paket")


def test_bootstrap_copies_the_package_only_with_the_switch(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    off = default_settings.outcomes.model_copy(update={"enabled": False})
    bootstrap_from_settings(layout, default_settings.model_copy(update={"outcomes": off}))
    assert not outcome_files(layout).agenda.exists()
    bootstrap_from_settings(layout, default_settings)
    assert (
        outcome_files(layout).agenda.read_bytes()
        == (PACKAGE / "tagesordnungspunkte-duesseldorf.parquet").read_bytes()
    )


def test_the_mini_fixture_brings_the_rows_of_its_documents(mini_root: Path) -> None:
    """``tests/fixtures/mini/raw/`` trägt die Zeilen ihrer 200 Dokumente aus dem Paket (make_mini)."""
    own = pl.read_parquet(mini_root / "raw" / "tagesordnungspunkte.parquet")
    package = pl.read_parquet(PACKAGE / "tagesordnungspunkte-duesseldorf.parquet")
    assert own.equals(package.filter(pl.col("id").is_in(own.get_column("id").implode())))
    assert own.get_column("id").n_unique() == 200


def test_bootstrap_prefers_the_table_of_the_frozen_dataset(tmp_path: Path) -> None:
    """Wie bei Punkt 58: bringt der eingefrorene Datensatz eine eigene Tabelle mit, gilt seine."""
    reference = tmp_path / "reference"
    (reference / "raw").mkdir(parents=True)
    own = pl.DataFrame(schema=AGENDA_SCHEMA)
    own.write_parquet(reference / "raw" / "tagesordnungspunkte.parquet")
    layout = Layout(tmp_path / "data", tmp_path / "cache", reference)
    bootstrap(layout, outcomes=PACKAGE / "tagesordnungspunkte-2025.parquet", seed_corpus=False)
    assert pl.read_parquet(outcome_files(layout).agenda).height == 0


# --- Der Lauf der Mini-Fixture (Paket, Rollen und Kanten aus 14, Antragsteller aus 15) ----------


def test_the_mini_run_writes_one_row_per_corpus_id(mini_run: Layout) -> None:
    ids = pl.read_parquet(mini_run.corpus, columns=["id"]).get_column("id").to_list()
    files = outcome_files(mini_run)
    verlauf = pl.read_parquet(files.progress)
    lage = pl.read_parquet(files.outcomes)
    erfolg = pl.read_parquet(files.success)
    assert verlauf.schema == pl.Schema(PROGRESS_SCHEMA)
    assert lage.schema == pl.Schema(OUTCOME_SCHEMA)
    assert erfolg.schema == pl.Schema(SUCCESS_SCHEMA)
    assert one_row_per_document(lage, ids)
    # die 200 Dokumente der Mini-Fixture, wie sie die Hauptperiode klassifiziert
    assert dict(lage.group_by("klasse").len().iter_rows()) == {
        "beschlossen": 83,
        "geaendert": 10,
        "abgelehnt": 7,
        "zurueckgezogen": 4,
        "erledigt": 86,
        "vertagt": 5,
        "offen": 1,
        "ohne_ergebnis": 4,
    }
    motions = lage.filter(pl.col("rolle") == "antrag")
    assert motions.height == 33
    assert motions.filter(pl.col("klasse") != "ohne_ergebnis").height == 32
    assert set(erfolg.get_column("periode").to_list()) == {"2020-2025"}


def test_the_package_path_equals_the_network_path_for_the_same_rows(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Derselbe Verlauf aus dem Netzlauf und aus dem Paket, mit den Kürzeln des Profils."""
    organizations = dict(default_settings.bodies.organizations)
    results = dict(default_settings.outcomes.results)
    network = progress(agenda_from_network(_layout(tmp_path), IDS), organizations, results)
    packed = pl.read_parquet(PACKAGE / "tagesordnungspunkte-duesseldorf.parquet").filter(
        pl.col("id").is_in(IDS)
    )
    assert progress(packed, organizations, results).equals(network)


def test_the_outcomes_step_raises_no_deprecation_warning(
    tmp_path: Path, mini_run: Layout, default_settings: Settings
) -> None:
    """Review 2026-11-24, K1: ``is_in`` mit einer Series ist in Polars veraltet (``implode``)."""
    import warnings

    shutil.copytree(mini_run.data_root, tmp_path / "data")
    layout = Layout(
        tmp_path / "data",
        tmp_path / "cache",
        mini_run.reference_root,
        default_settings.profile,
    )
    step = _steps(default_settings, layout)["outcomes"]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        step.run()
    assert [str(w.message)[:60] for w in caught if issubclass(w.category, DeprecationWarning)] == []
