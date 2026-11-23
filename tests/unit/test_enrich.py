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
from georep.enrich import Contribution, DuplicateStepError
from georep.http import Transport
from georep.io import write_bytes
from georep.layout import Layout
from georep.pipeline import Step, build_steps, run_pipeline
from georep.report.tables import PublishedTable, all_tables, csv_plan, published
from georep.settings import Settings
from tests.fakes import FakeSession, response


def _layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")


def _probe_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    target = layout.processed / "probe.parquet"
    return [Step("probe", (layout.corpus,), (target,), lambda: "nichts")]


def _late_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    target = layout.processed / "spaet.parquet"
    return [Step("spaet", (layout.corpus,), (target,), lambda: "nichts")]


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
    # Der Typ, nicht nur der Name: ein TypeError aus einem Beitrag nennt ``_probe_steps`` auch
    with pytest.raises(DuplicateStepError, match="probe"):
        build_steps(default_settings, _layout(tmp_path))


# --- Nachzug F2: ein zweiter Einhängepunkt vor ``weights`` (Synergien 2026-11, Konflikt 6) ---


def test_ein_frueher_schritt_steht_unmittelbar_vor_weights(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was ``weights`` liest (16 ``places``, 11 ``sections``), muss vor ``weights`` entstehen."""
    monkeypatch.setattr(
        georep.enrich, "CONTRIBUTIONS", (Contribution("probe", early_steps=_probe_steps),)
    )
    names = [s.name for s in build_steps(default_settings, _layout(tmp_path))]
    assert names.index("index") < names.index("probe") == names.index("weights") - 1


def test_ein_beitrag_mit_fruehen_und_spaeten_schritten(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Beitrag je Vorhaben, mit allen Schritten: früh vor ``weights``, spät vor ``report``."""
    both = Contribution("probe", early_steps=_probe_steps, steps=_late_steps)
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", (both,))
    names = [s.name for s in build_steps(default_settings, _layout(tmp_path))]
    assert names.index("probe") == names.index("weights") - 1
    assert names.index("spaet") == names.index("report") - 1


def test_frueh_und_spaet_mit_demselben_namen_sind_ein_fehler(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    twice = (Contribution("a", early_steps=_probe_steps), Contribution("b", steps=_probe_steps))
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", twice)
    with pytest.raises(DuplicateStepError, match="probe"):
        build_steps(default_settings, _layout(tmp_path))


def test_ein_frueher_schritt_mit_dem_namen_eines_kernschritts_ist_ein_fehler(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def weights(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
        return [Step("weights", (), (layout.processed / "x.parquet",), lambda: "nichts")]

    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", (Contribution("a", early_steps=weights),))
    with pytest.raises(DuplicateStepError, match="weights"):
        build_steps(default_settings, _layout(tmp_path))


# --- Nachzug F2: der Transport an den Beiträgen (Synergien 2026-11, Konflikt 7) -------------

PROBE_URL = "https://example.org/probe.json"


def _network_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    target = layout.raw / "probe.json"

    def run() -> str:
        write_bytes(target, http.get(PROBE_URL).content)
        return "geholt"

    return [Step("probe_netz", (), (target,), run, network=True)]


@pytest.mark.parametrize(
    "contribution",
    [
        Contribution("probe", early_steps=_network_steps),
        Contribution("probe", steps=_network_steps),
    ],
    ids=["frueh", "spaet"],
)
def test_ein_netzschritt_eines_beitrags_laeuft_ueber_die_session_aus_build_steps(
    tmp_path: Path,
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    contribution: Contribution,
) -> None:
    """Die Naht für Tests mit der Fake-Session (CLAUDE.md, „Nie": Netz in Unit-Tests)."""
    layout = _layout(tmp_path)
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", (contribution,))
    session = FakeSession({PROBE_URL: response(PROBE_URL, payload={"ok": 1})})
    steps = build_steps(default_settings, layout, session)
    [outcome] = run_pipeline(steps, default_settings, ["probe_netz"], online=True)
    assert outcome.status == "ausgeführt", outcome
    assert session.urls == [PROBE_URL]
    assert (layout.raw / "probe.json").read_bytes() == b'{"ok": 1}'


def test_ohne_netzschritt_entsteht_keine_session(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne ``http`` bekommt ein Beitrag eine Session, die erst beim ersten Aufruf entsteht.

    Wie bei den Netzschritten des Kerns: ``georep steps`` oder ein Lauf ohne ``--online`` legt
    keinen HTTP-Cache an.
    """
    layout = _layout(tmp_path)
    monkeypatch.setattr(
        georep.enrich,
        "CONTRIBUTIONS",
        (Contribution("probe", early_steps=_network_steps, steps=_late_steps),),
    )
    steps = build_steps(default_settings, layout)
    run_pipeline(steps, default_settings, ["probe_netz"])  # ohne --online übersprungen
    assert not layout.http_cache.exists()


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
