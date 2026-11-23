"""Beiträge der Vorverarbeitung 2026-11 (Fundament F2, docs/plan-vorverarbeitung-2026-11.md, § 7).

Ein Vorhaben trägt Schritte, Tabellen und Unterseiten über ``georep.enrich.CONTRIBUTIONS`` bei und
berührt ``build_steps`` nicht. Die Tests setzen das Register über ``monkeypatch`` und prüfen die
Stelle, an der ein Beitrag landet.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

import georep.enrich
from georep.enrich import Contribution
from georep.layout import Layout
from georep.pipeline import Step, build_steps
from georep.report.tables import PublishedTable, all_tables, csv_plan, published
from georep.settings import Settings


def _layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")


def _probe_steps(settings: Settings, layout: Layout) -> list[Step]:
    target = layout.processed / "probe.parquet"
    return [Step("probe", (layout.corpus,), (target,), lambda: "nichts")]


def test_ohne_beitraege_bleibt_das_register_wie_es_war(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _layout(tmp_path)
    before = [s.name for s in build_steps(default_settings, layout)]
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", ())
    assert [s.name for s in build_steps(default_settings, layout)] == before


def test_ein_beitrag_steht_unmittelbar_vor_dem_bericht(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        georep.enrich, "CONTRIBUTIONS", (Contribution("probe", steps=_probe_steps),)
    )
    names = [s.name for s in build_steps(default_settings, _layout(tmp_path))]
    assert names.index("probe") == names.index("report") - 1


def test_zwei_beitraege_mit_demselben_schritt_sind_ein_fehler(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    twice = (Contribution("a", steps=_probe_steps), Contribution("b", steps=_probe_steps))
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", twice)
    with pytest.raises(Exception, match="probe"):
        build_steps(default_settings, _layout(tmp_path))


def _probe_table() -> PublishedTable:
    return PublishedTable(
        "probe_tabelle",
        lambda layout: layout.processed / "probe_tabelle.parquet",
        "Eine Tabelle aus einem Beitrag",
        {"id": ("Kennung des Dokuments", "")},
        optional=True,
    )


def test_eine_beigetragene_tabelle_steht_hinter_denen_des_kerns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _layout(tmp_path)
    layout.processed.mkdir(parents=True)
    pl.DataFrame({"id": ["a"]}).write_parquet(layout.processed / "probe_tabelle.parquet")
    monkeypatch.setattr(
        georep.enrich, "CONTRIBUTIONS", (Contribution("probe", tables=(_probe_table(),)),)
    )
    assert [t.name for t in all_tables()][-1] == "probe_tabelle"
    assert published(layout)[-1].name == "probe_tabelle"
    assert layout.processed / "probe_tabelle.parquet" in [row[0] for row in csv_plan(layout)]


def test_ein_beitrag_darf_keinen_tabellennamen_des_kerns_tragen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = all_tables()[0]
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", (Contribution("probe", tables=(core,)),))
    with pytest.raises(Exception, match=core.name):
        all_tables()
