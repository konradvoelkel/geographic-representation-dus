"""Der Beitrag von Vorhaben 15 im Register: zwei Schritte, zwei Tabellen je Korpus-ID.

Die Mini-Fixture läuft mit dem Stadtprofil, das die Schritte einschaltet; ihre 200 Dokumente
stammen aus der Hauptperiode, in der jede Dokumentart eine Zeile hat (Messdokument
``docs/plans/15-funktion.md``, § 3.2: Restklasse 0).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from georep.analysis.cosponsors import CAMPS, COSPONSORS_SCHEMA
from georep.analysis.functions import FUNCTIONS_SCHEMA
from georep.contracts import one_row_per_document
from georep.enrich.functions import functions_files, functions_steps
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.settings import Originators, Settings
from tests.fakes import FakeSession

HTTP = FakeSession({})  # beide Schritte sind offline und fragen nie


def _layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")


def test_the_two_steps_stand_behind_parties_and_bodies(
    tmp_path: Path, default_settings: Settings
) -> None:
    names = [s.name for s in build_steps(default_settings, _layout(tmp_path))]
    assert names.index("functions") > names.index("parties") > names.index("bodies")
    assert names.index("cosponsors") == names.index("functions") + 1
    assert names.index("report") > names.index("cosponsors")


def test_the_switch_and_the_originators_decide_whether_the_steps_exist(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    off = default_settings.functions.model_copy(update={"enabled": False})
    assert (
        functions_steps(default_settings.model_copy(update={"functions": off}), layout, HTTP) == []
    )
    without = default_settings.model_copy(update={"originators": Originators()})
    assert functions_steps(without, layout, HTTP) == []
    assert [s.name for s in functions_steps(default_settings, layout, HTTP)] == [
        "functions",
        "cosponsors",
    ]


def test_the_steps_read_what_they_need_and_write_under_processed(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    steps = {s.name: s for s in functions_steps(default_settings, layout, HTTP)}
    files = functions_files(layout)
    assert steps["functions"].outputs == (files.functions,)
    assert steps["cosponsors"].outputs == (files.cosponsors,)
    assert files.functions == layout.processed / "dokumente_funktion.parquet"
    assert files.cosponsors == layout.processed / "dokumente_antragsteller.parquet"
    assert layout.document_originators in steps["functions"].inputs
    assert layout.papers_bodies in steps["cosponsors"].inputs


def test_the_mini_run_writes_one_row_per_corpus_id(mini_run: Layout) -> None:
    ids = pl.read_parquet(mini_run.corpus, columns=["id"]).get_column("id").to_list()
    files = functions_files(mini_run)
    functions = pl.read_parquet(files.functions)
    cosponsors = pl.read_parquet(files.cosponsors)
    assert functions.schema == pl.Schema(FUNCTIONS_SCHEMA)
    assert cosponsors.schema == pl.Schema(COSPONSORS_SCHEMA)
    assert one_row_per_document(functions, ids) and one_row_per_document(cosponsors, ids)
    assert functions.filter(pl.col("funktion") == "rest").height == 0  # jede Art hat eine Zeile
    assert set(functions.get_column("variante").to_list()) == {"B"}
    assert set(cosponsors.get_column("lager").to_list()) <= set(CAMPS)
    originators = pl.read_parquet(mini_run.document_originators, columns=["id", "urheber_art"])
    named = cosponsors.join(originators, on="id").filter(pl.col("antragsteller").list.len() > 0)
    assert named.height > 0 and set(named.get_column("urheber_art").to_list()) == {"Fraktion"}
