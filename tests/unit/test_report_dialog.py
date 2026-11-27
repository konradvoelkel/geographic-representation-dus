"""Der allgemeine Dialog-Haken (Vorarbeit V2, ``report/dialog.py``, ``frame/dialog.js.j2``).

Ein Beitrag legt ``data/<name>.json`` mit Zeilen je Dokument ab, und das Skript des Rahmens lädt
die Datei beim ersten Öffnen des Dokumentdialogs nach; ``dokumente.json`` wächst nicht. Geprüft
werden das Format (Indizes in ``dokumente.json`` oder auf eigene Ziele), die Folge aus derselben
Funktion wie ``dokumente.json``, das Register (Name, Schalter, Eingaben im Stamp von ``report``),
das Schreiben und Aufräumen unter ``site/data/``, das Attribut am Dialog und die Größe des Hakens.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from dataclasses import replace
from pathlib import Path

import deal
import polars as pl
import pytest

from georep.enrich import Contribution
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.report.build import DOCUMENTS_NAME, write_dialogs
from georep.report.dialog import (
    DIALOG_FORMAT,
    DialogHook,
    DialogRows,
    DialogTarget,
    dialog_names,
    dialog_payload,
)
from georep.report.documents import DOCUMENT_COLUMNS, document_order, documents_payload
from georep.report.model import ReportModel
from georep.report.render import Visuals, environment, render_report
from georep.search.index import HITS, PAPER_IDS, TERM
from georep.settings import Settings

NOW = dt.datetime(2026, 11, 27, 12, 0, tzinfo=dt.UTC)
BASE = "https://ris.example/files/"


def _target(n: int) -> DialogTarget:
    return DialogTarget(f"{BASE}{n:05d}.pdf", dt.date(2021, 3, n), f"X/{n:03d}/2021", f"Titel {n}")


def _payload(rows: DialogRows, order: list[str]) -> dict[str, object]:
    return dialog_payload(rows, order, BASE, title="Probe", version="0.0.0", generated_at=NOW)


# --- Format ----------------------------------------------------------------------------------------
def test_ein_ziel_zeigt_in_dokumente_json_oder_auf_ein_eigenes_dokument() -> None:
    """Ein Ziel im Dialog ist sein Index dort, eines außerhalb ein negativer Index in ``documents``."""
    rows = DialogRows(
        labels=("nennt", "genannt in"),
        rows={"a": ((0, "b"), (0, "x")), "c": ((1, "a"), (1, "y"), (1, "x"))},
        targets={"x": _target(7), "y": _target(8), "b": _target(2)},
        note="ein Satz",
    )
    payload = _payload(rows, ["a", "b", "c"])
    assert payload["format"] == DIALOG_FORMAT
    assert payload["rows"] == {"0": [[0, 1], [0, -1]], "2": [[1, 0], [1, -2], [1, -1]]}
    # nur die Ziele außerhalb von dokumente.json, in der Folge ihres ersten Auftretens, relativ
    assert payload["documents"] == [
        ["00007.pdf", "2021-03-07", "X/007/2021", "Titel 7"],
        ["00008.pdf", "2021-03-08", "X/008/2021", "Titel 8"],
    ]
    assert payload["labels"] == ["nennt", "genannt in"]
    assert (payload["title"], payload["note"], payload["base"]) == ("Probe", "ein Satz", BASE)


def test_ein_eintrag_ohne_ziel_traegt_nur_sein_wort() -> None:
    """26 zeigt etwa „angenommen im Rat am 12.03.2024": ein Wort ohne Dokument."""
    rows = DialogRows(labels=("angenommen",), rows={"b": ((0, None),)})
    assert _payload(rows, ["a", "b"])["rows"] == {"1": [[0]]}


def test_zeilen_ausserhalb_des_dialogs_fallen_weg() -> None:
    """Der Dialog zeigt nur Dokumente aus ``dokumente.json``; die übrigen Zeilen kosten nur Bytes."""
    rows = DialogRows(
        labels=("nennt",),
        rows={"z": ((0, "a"),), "b": ((0, "a"),), "a": ()},
    )
    payload = _payload(rows, ["a", "b"])
    assert payload["rows"] == {"1": [[0, 0]]}
    assert payload["documents"] == []


def test_ein_ziel_ohne_angaben_ist_ein_fehler() -> None:
    """Ein Ziel außerhalb von ``dokumente.json`` braucht Link, Datum, Drucksache und Titel."""
    rows = DialogRows(labels=("nennt",), rows={"a": ((0, "x"),)})
    with pytest.raises(deal.PreContractError):
        _payload(rows, ["a"])
    with pytest.raises(deal.PreContractError):
        _payload(DialogRows(labels=(), rows={"a": ((0, None),)}), ["a"])


def test_die_folge_ist_die_von_dokumente_json() -> None:
    """``document_order`` ist die Folge, aus der ``documents_payload`` seine Liste baut."""
    corpus = pl.DataFrame(
        {
            "id": ["p1", "p2", "p3", "p4"],
            "name": ["A", "B", "C", "D"],
            "reference": ["R1", "R2", "R3", "R4"],
            "date": [dt.date(2021, 1, 1), dt.date(2022, 1, 1), dt.date(2022, 1, 1), None],
            "paper_type": ["Antrag"] * 4,
            "download_url": [f"{BASE}{n}.pdf" for n in range(1, 5)],
        }
    ).select(DOCUMENT_COLUMNS)
    index = pl.DataFrame(
        {TERM: ["Bach", "Wald"], PAPER_IDS: [["p1", "p3"], ["p2", "p4"]], HITS: [2, 2]}
    )
    order = document_order(corpus, index, ["Wald"])
    payload = documents_payload(corpus, index, ["Wald"], version="0", generated_at=NOW)
    references = [row[2] for row in payload["documents"]]  # type: ignore[attr-defined]
    assert order == ["p3", "p1"] and references == ["R3", "R1"]
    # ohne Datum zuerst, wie ``sort(descending=True)`` von Polars es seit jeher legt
    assert document_order(corpus, index, []) == ["p4", "p2", "p3", "p1"]


# --- Register ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["dokumente", "begriffe", "schema", "summary", "Gross", "a_b"])
def test_ein_name_unter_data_ist_nur_einmal_zu_haben(name: str) -> None:
    with pytest.raises(ValueError, match="Haken"):
        DialogHook(name, "T", "D", inputs=lambda layout, s: (), rows=lambda layout, s: _empty())


def _empty() -> DialogRows:
    return DialogRows(labels=(), rows={})


def _probe(layout_file: str = "probe.parquet", *, on: bool = True) -> DialogHook:
    return DialogHook(
        "probe",
        "Probe",
        "Probe je Dokument",
        inputs=lambda layout, settings: (layout.processed / layout_file,),
        rows=_probe_rows,
        enabled=lambda settings: on,
    )


def _probe_rows(layout: Layout, settings: Settings) -> DialogRows:
    ids = pl.read_parquet(layout.corpus, columns=["id"]).get_column("id").to_list()
    return DialogRows(
        labels=("Probe zu",),
        rows={doc_id: ((0, ids[0]),) for doc_id in ids},
        targets={ids[0]: DialogTarget("", None, "R", "T")},
        note="Probe, nicht geprüft",
    )


def _register(monkeypatch: pytest.MonkeyPatch, *hooks: DialogHook) -> None:
    import georep.enrich
    import georep.report.pages

    monkeypatch.setattr(
        georep.enrich, "CONTRIBUTIONS", (Contribution("probe", dialogs=tuple(hooks)),)
    )
    monkeypatch.setattr(georep.report.pages, "pages_folder", lambda: Path("/nonexistent/pages"))


def test_der_bericht_liest_die_eingaben_der_haken(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``report`` schreibt ``data/<name>.json``, also stehen die Eingaben in seinem Stamp."""
    _register(monkeypatch, _probe())
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    report = next(s for s in build_steps(default_settings, layout) if s.name == "report")
    assert layout.processed / "probe.parquet" in report.inputs
    assert dialog_names(default_settings) == ("probe",)
    _register(monkeypatch, _probe(on=False))
    report = next(s for s in build_steps(default_settings, layout) if s.name == "report")
    assert layout.processed / "probe.parquet" not in report.inputs
    assert dialog_names(default_settings) == ()


def test_zwei_haken_desselben_namens_sind_ein_fehler(
    default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(monkeypatch, _probe(), _probe())
    with pytest.raises(ValueError, match="doppelt"):
        dialog_names(default_settings)


# --- Schreiben, Attribut, Größe ---------------------------------------------------------------------
def _copy(mini_run: Layout, tmp_path: Path) -> Layout:
    """Korpus, Index und ``dokumente.json`` der Mini-Kette in einer eigenen Wurzel (nie hinein schreiben)."""
    layout = Layout(
        tmp_path / "data", tmp_path / "cache", mini_run.reference_root, mini_run.profile
    )
    for source, target in (
        (mini_run.corpus, layout.corpus),
        (mini_run.index, layout.index),
        (mini_run.site_data / DOCUMENTS_NAME, layout.site_data / DOCUMENTS_NAME),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return layout


def test_der_bericht_schreibt_die_datei_und_raeumt_sie_wieder_weg(
    mini_run: Layout,
    mini_model: ReportModel,
    default_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _copy(mini_run, tmp_path)
    _register(monkeypatch, _probe())
    downloads = write_dialogs(layout, mini_model, default_settings)
    listed = json.loads((layout.site_data / DOCUMENTS_NAME).read_text(encoding="utf-8"))
    payload = json.loads((layout.site_data / "probe.json").read_text(encoding="utf-8"))
    assert payload["base"] == listed["base"] and payload["title"] == "Probe"
    # jedes Dokument des Dialogs hat eine Zeile, und jede zeigt auf das eigene Ziel
    assert set(payload["rows"]) == {str(i) for i in range(len(listed["documents"]))}
    assert {json.dumps(v) for v in payload["rows"].values()} <= {"[[0, -1]]", "[[0, 0]]"}
    assert [(d.name, d.format, d.rows) for d in downloads] == [
        ("probe.json", "JSON", len(listed["documents"]))
    ]
    # abgeschaltet: die Datei fährt nicht mit
    _register(monkeypatch, _probe(on=False))
    assert write_dialogs(layout, mini_model, default_settings) == []
    assert not (layout.site_data / "probe.json").exists()


def test_eine_fremde_folge_in_dokumente_json_bricht_ab(
    mini_run: Layout,
    mini_model: ReportModel,
    default_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passt ``dokumente.json`` nicht zur Folge, zeigten die Indizes auf andere Dokumente."""
    from georep.errors import SchemaError

    layout = _copy(mini_run, tmp_path)
    target = layout.site_data / DOCUMENTS_NAME
    listed = json.loads(target.read_text(encoding="utf-8"))
    target.write_text(json.dumps(listed | {"documents": listed["documents"][1:]}), encoding="utf-8")
    _register(monkeypatch, _probe())
    with pytest.raises(SchemaError, match="Folge"):
        write_dialogs(layout, mini_model, default_settings)


def test_der_dialog_nennt_seine_dateien_nur_mit_haken(
    mini_model: ReportModel, mini_visuals: Visuals
) -> None:
    without = render_report(replace(mini_model, dialogs=()), mini_visuals)
    assert '<dialog id="docs" aria-labelledby="docs-title"><form' in without
    assert "data-extras" not in without
    with_hooks = render_report(replace(mini_model, dialogs=("a", "b")), mini_visuals)
    assert '<dialog id="docs" aria-labelledby="docs-title" data-extras="a b"><form' in with_hooks


def test_der_haken_bleibt_bei_rund_einem_kilobyte() -> None:
    """Plan § 5: der Haken unter rund 1 KB auf ``index.html``; die Erklärung ist ein Jinja-Kommentar.

    Review K3 (Folge in Registerfolge, Sätze unter der Liste, Wort nur beim Wechsel, Felder aus
    ``show``) kostet rund 300 Byte; die Grenze ist darum 1 400, nicht 1 000.
    """
    env = environment()
    hook = env.get_template("frame/dialog.js.j2").render()
    assert len(hook.encode("utf-8")) < 1_400
    assert "Vorarbeit" not in hook  # kein Kommentar im ausgelieferten Skript
    script = env.get_template("frame/script.js.j2").render()
    assert hook in script and "extras(items, data.documents);" in script


# --- Review Runde 1, K3 (2026-11-27): 18 und 26 hängen sich wirklich nur mit Daten an ------------
def test_ein_haken_waehlt_die_felder_seiner_ziele() -> None:
    """(d): 18 zeigt je Vorschlag Drucksache, Datum und Titel sichtbar, 14 nur die Drucksache."""
    rows = DialogRows(labels=("ähnlich",), rows={"a": ((0, "x"),)}, targets={"x": _target(7)})
    payload = dialog_payload(
        rows,
        ["a"],
        BASE,
        title="Ähnlich",
        version="0",
        generated_at=NOW,
        show=("drucksache", "datum", "titel"),
    )
    assert payload["format"] == DIALOG_FORMAT == 2
    assert payload["show"] == [2, 1, 3]
    assert _payload(rows, ["a"])["show"] == [2]  # die Vorgabe: nur die Drucksache
    with pytest.raises(ValueError, match="show"):
        DialogHook(
            "probe",
            "T",
            "D",
            inputs=lambda layout, s: (),
            rows=lambda layout, s: _empty(),
            show=("link",),
        )


def test_das_skript_haelt_folge_notizen_und_woerter_nach_dem_format() -> None:
    """(a) je Haken ein Platzhalter in der Folge von data-extras, nicht in der Ankunftsfolge;
    (b) die Sätze unter der Liste; (c) ein Wort nur, wenn es wechselt; (d) die Felder aus ``show``."""
    hook = environment().get_template("frame/dialog.js.j2").render()
    assert "EXTRAS.map" in hook  # (a) und (b): Platzhalter je Haken, angelegt vor dem Laden
    assert 'line(dialog, "", "note extra")' in hook  # (b): hinter <ol>, also unter der Liste
    assert "e[0] === row[k - 1][0]" in hook  # (c)
    assert "x.show.map" in hook  # (d)
