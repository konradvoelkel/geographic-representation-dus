"""Jeder Schritt trägt die Schema-Version seiner Ausgabe (Review-Befund 3, 2026-10-13).

Die Version steht im Modul, das die Datei schreibt (``BODIES_SCHEMA_VERSION`` und so weiter) oder
für die zwei Modelle in ``georep.schema``, damit das Register sie ohne sklearn kennt; sie landet
über ``write_parquet`` in den Parquet-Metadaten. Sie muss aber auch am ``Step`` stehen:
nur dann schreibt ``write_stamp`` sie in den Stamp, und nur dann kann ``stamp_mismatch`` je
„Schema geändert" melden. Fehlt sie dort, bleibt der Stamp nach einer Schemaänderung gültig und
die Kette rechnet mit einer Datei weiter, deren Spalten sich geändert haben.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest

from georep import __version__
from georep.layout import Layout
from georep.pipeline import (
    METRICS_SCHEMA,
    PARTIES_SCHEMA,
    Step,
    build_steps,
    stamp_mismatch,
)
from georep.prep.bodies import BODIES_SCHEMA_VERSION
from georep.prep.context import CONTEXT_SCHEMA_VERSION
from georep.prep.papers import CORPUS_SCHEMA_VERSION
from georep.report.build import report_fingerprint
from georep.schema import ASSIGNMENT_SCHEMA_VERSION, TOPICS_SCHEMA_VERSION
from georep.settings import Settings

VERSIONS = {
    "corpus": CORPUS_SCHEMA_VERSION,
    "bodies": BODIES_SCHEMA_VERSION,
    "topics": TOPICS_SCHEMA_VERSION,
    "committees": ASSIGNMENT_SCHEMA_VERSION,
    # Punkt 46: der neue Schritt und die drei Spalten mehr in wahlbezirke_parteien
    "metrics": METRICS_SCHEMA,
    "parties": PARTIES_SCHEMA,
    # Punkt 53: beide Ausgaben sind seit dem 2026-10-13 sortiert
    "context": CONTEXT_SCHEMA_VERSION,
}


@pytest.fixture
def steps(default_settings: Settings, tmp_path: Path) -> dict[str, int]:
    layout = Layout(
        tmp_path / "data",
        tmp_path / "cache",
        tmp_path / "reference",
        # Mit Fremddaten, damit die drei Kontextschritte im Register stehen (Punkt 53).
        context_root=tmp_path / "context",
    )
    return {s.name: s.schema_version for s in build_steps(default_settings, layout)}


def test_each_step_carries_the_schema_version_of_its_module(steps: dict[str, int]) -> None:
    for name, version in VERSIONS.items():
        assert steps[name] == version, (name, steps[name], version)


def test_a_bumped_schema_version_makes_the_stamp_stale(
    default_settings: Settings, tmp_path: Path
) -> None:
    """Der Grund für den Test oben: sonst meldet ``stamp_mismatch`` die Änderung nie."""
    layout = Layout(
        tmp_path / "data",
        tmp_path / "cache",
        tmp_path / "reference",
        # Mit Fremddaten, damit die drei Kontextschritte im Register stehen (Punkt 53).
        context_root=tmp_path / "context",
    )
    step = next(s for s in build_steps(default_settings, layout) if s.name == "topics")
    stamped: dict[str, object] = {
        "schema_version": step.schema_version,
        "code_version": "0.0.0",
        "settings_fingerprint": default_settings.fingerprint(),
        "inputs": {},
    }
    assert stamp_mismatch(stamped, step, default_settings) != "Schema geändert"
    stamped["schema_version"] = step.schema_version - 1
    assert stamp_mismatch(stamped, step, default_settings) == "Schema geändert"


# --- Punkt 53: der Zusatz im Stamp des Schritts ``report`` --------------------------------------


def test_only_the_report_step_carries_an_extra(default_settings: Settings, tmp_path: Path) -> None:
    """Der Zusatz ist die Ausnahme, nicht die Regel: ein alter Stamp bleibt sonst gültig."""
    layout = Layout(
        tmp_path / "data",
        tmp_path / "cache",
        tmp_path / "reference",
        # Mit Fremddaten, damit die drei Kontextschritte im Register stehen (Punkt 53).
        context_root=tmp_path / "context",
    )
    found = {s.name: s.extra for s in build_steps(default_settings, layout)}
    assert found["report"] == report_fingerprint(default_settings)
    assert len(found["report"]) == 16
    assert [name for name, extra in found.items() if extra] == ["report"]


def test_a_changed_extra_makes_the_stamp_stale(default_settings: Settings, tmp_path: Path) -> None:
    """Ein Vorlagenwechsel machte den Stamp bis zum 2026-10-13 nicht ungültig.

    Er trug nur die Code-Version des Pakets; ohne Versionssprung brauchte die Seite nach einer
    Änderung an ``templates/sections/*.j2`` ein ``georep run report --force`` (STATUS, „Bekannt").
    Geprüft an einem Schritt ohne Eingaben, damit nur diese Regel im Spiel ist.
    """
    bare = Step("probe", (), (tmp_path / "out.json",), lambda: "")
    old_style: dict[str, object] = {
        "schema_version": bare.schema_version,
        "settings": default_settings.fingerprint(),
        "code": __version__,
        "inputs": {},
    }
    # Ein Stamp von vor diesem Feld bleibt gültig, solange der Schritt keinen Zusatz trägt
    assert stamp_mismatch(old_style, bare, default_settings) is None
    with_extra = replace(bare, extra="642286a2a9c672c6")
    assert stamp_mismatch(old_style, with_extra, default_settings) == (
        "Vorlagen oder Anzeige geändert"
    )
    stamped = dict(old_style) | {"extra": with_extra.extra}
    assert stamp_mismatch(stamped, with_extra, default_settings) is None
    assert stamp_mismatch(stamped, replace(with_extra, extra="0" * 16), default_settings) == (
        "Vorlagen oder Anzeige geändert"
    )


def test_a_changed_class_boundary_changes_the_fingerprint(default_settings: Settings) -> None:
    """``[report]`` ist aus dem Settings-Fingerprint ausgenommen -- im Zusatz zählt es trotzdem.

    Richtig war die Ausnahme für die Parquet-Dateien, nicht für ``index.html``: ``georep status``
    meldete den Schritt nach einer geänderten Klassengrenze als „aktuell" (STATUS, „Bekannt").
    """
    changed = default_settings.model_copy(
        update={
            "report": default_settings.report.model_copy(update={"table_preview_rows": 7}),
        }
    )
    assert changed.fingerprint() == default_settings.fingerprint()  # der Grund für den Zusatz
    assert report_fingerprint(changed) != report_fingerprint(default_settings)
    budget = default_settings.model_copy(
        update={"report": default_settings.report.model_copy(update={"page_budget_bytes": 1})}
    )
    assert report_fingerprint(budget) != report_fingerprint(default_settings)


def test_a_changed_package_file_changes_the_fingerprint(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Gezählt werden alle Dateien unter ``templates/`` und ``literatur.toml`` daneben."""
    package = tmp_path / "paket"
    (package / "templates" / "sections").mkdir(parents=True)
    (package / "templates" / "report.html.j2").write_text("<p>eins</p>", encoding="utf-8")
    (package / "templates" / "sections" / "10-a.html.j2").write_text("a", encoding="utf-8")
    (package / "templates" / "sections" / "10-a.js").write_text("js", encoding="utf-8")
    (package / "literatur.toml").write_text("literature = []\n", encoding="utf-8")
    before = report_fingerprint(default_settings, package)
    # Eine Zeile im JavaScript eines Abschnitts zählt wie eine Zeile in der Vorlage
    (package / "templates" / "sections" / "10-a.js").write_text("js2", encoding="utf-8")
    after_js = report_fingerprint(default_settings, package)
    (package / "literatur.toml").write_text("literature = [] # \n", encoding="utf-8")
    after_toml = report_fingerprint(default_settings, package)
    assert len({before, after_js, after_toml}) == 3
    # Und der Hash des Pakets ist ein anderer als der dieses Gerüsts
    assert before != report_fingerprint(default_settings)


# --- Punkt 53: das Register gegen die Konstanten und gegen die Dateien --------------------------


def test_the_stamp_version_is_the_version_of_the_file_it_stands_next_to(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Der Stamp liegt neben der ersten Ausgabe; beide müssen dieselbe Schema-Version nennen.

    Die Version steht zweimal: in den Parquet-Metadaten (``write_parquet``) und am ``Step``, von
    wo sie in den Stamp wandert. Nur über den Stamp kann ``stamp_mismatch`` je „Schema geändert"
    melden — und nur wenn beide Zahlen dieselbe sind, heißt die Meldung, was sie sagt (Lehre aus
    Punkt 45, geprüft seit 2026-10-13 auch gegen die Datei).
    """
    checked = 0
    for step in build_steps(default_settings, mini_run):
        first = step.outputs[0]
        if step.network or first.suffix != ".parquet" or not first.is_file():
            continue
        stored = pl.read_parquet_metadata(first)["georep.schema_version"]
        assert stored == str(step.schema_version), (step.name, first.name, stored)
        checked += 1
    # Heute 18: texts, voters, context, streets, pois, dictionary, corpus, bodies, topics,
    # committees, index, timeline, results, metrics, body_hits, weights, controls, parties.
    assert checked == 18, checked


def _step_versions_in_source() -> dict[str, str]:
    """Schrittname -> Ausdruck, den ``pipeline.py`` als ``schema_version`` übergibt.

    Gelesen wird der **Quelltext**, nicht der Laufzeitwert: nur so fällt auf, wenn jemand eine Zahl
    hinschreibt statt die Konstante seines Moduls zu nennen. Ein Wertvergleich sähe das nie, denn
    die meisten Versionen sind 1 (Review-Befund 3, 2026-10-13).
    """
    tree = ast.parse(Path("src/georep/pipeline.py").read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "Step" or not node.args:
            continue
        name = node.args[0]
        if not isinstance(name, ast.Constant) or not isinstance(name.value, str):
            continue
        version: ast.expr | None = node.args[4] if len(node.args) >= 5 else None
        for keyword in node.keywords:
            if keyword.arg == "schema_version":
                version = keyword.value
        if version is not None:
            found[name.value] = ast.unparse(version)
    return found


# ``stores.TEXT_SCHEMA_VERSION`` gehört zu keinem Schritt: der Textstore schreibt seine Datei
# selbst (``cache_root/<profil>/text/texts.parquet``), sie ist keine Ausgabe des Registers und
# trägt darum auch keinen Stamp. Jede andere Konstante muss im Register ankommen.
SCHEMA_CONSTANTS_WITHOUT_A_STEP = {"georep.stores.TEXT_SCHEMA_VERSION"}


def test_a_step_names_its_constant_instead_of_a_number() -> None:
    """Jeder Schritt mit eigener Schema-Version nennt die Konstante seines Moduls."""
    versions = _step_versions_in_source()
    assert set(versions) == set(VERSIONS), (sorted(versions), sorted(VERSIONS))
    for step, expression in versions.items():
        assert expression.isidentifier(), (step, expression)
        assert "SCHEMA" in expression, (step, expression)


def test_every_schema_constant_of_the_package_belongs_to_a_step() -> None:
    """Eine neue Schema-Konstante ohne Schritt wäre eine Version, die nirgends ankommt.

    Genau das war der Befund hinter Punkt 45: die Zahl stand im Modul und in den
    Parquet-Metadaten, aber nicht am ``Step``, und ``stamp_mismatch`` konnte sie nie melden.
    Gescannt wird **das ganze Paket**, nicht eine Handvoll Module, und geprüft wird die
    **Zuordnung** über den Namen, nicht die Gleichheit der Zahl.
    """
    constants: dict[str, str] = {}
    for file in sorted(Path("src/georep").rglob("*.py")):
        module = ".".join(file.with_suffix("").parts[1:])
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            value = node.value
            if not (isinstance(target, ast.Name) and "SCHEMA" in target.id):
                continue
            if isinstance(value, ast.Constant) and isinstance(value.value, int):
                constants[f"{module}.{target.id}"] = target.id
    assert len(constants) >= 7, constants  # heute sieben, mit TEXT_SCHEMA_VERSION
    used = set(_step_versions_in_source().values())
    missing = {
        name
        for name, short in constants.items()
        if short not in used and name not in SCHEMA_CONSTANTS_WITHOUT_A_STEP
    }
    assert not missing, f"Schema-Konstanten, die kein Schritt nennt: {sorted(missing)}"
