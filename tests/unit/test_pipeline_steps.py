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
import json
import re
import shutil
from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest

import georep.enrich
from georep import __version__
from georep.analysis.cosponsors import COSPONSORS_SCHEMA_VERSION
from georep.analysis.functions import FUNCTIONS_SCHEMA_VERSION
from georep.council import COUNCIL_SCHEMA_VERSION
from georep.enrich.procedures import PROCEDURES_SCHEMA_VERSION
from georep.errors import MissingInputError
from georep.layout import Layout
from georep.pipeline import (
    METRICS_SCHEMA,
    MISSING,
    PARTIES_SCHEMA,
    Step,
    build_steps,
    input_digests,
    run_pipeline,
    stamp_mismatch,
)
from georep.prep.bodies import BODIES_SCHEMA_VERSION
from georep.prep.context import (
    CONTEXT_SCHEMA_VERSION,
    NEED_DATA_SCHEMA_VERSION,
    NEED_SCHEMA_VERSION,
)
from georep.prep.papers import CORPUS_SCHEMA_VERSION
from georep.report.build import report_fingerprint
from georep.schema import ASSIGNMENT_SCHEMA_VERSION, TOPICS_SCHEMA_VERSION, stop_words_digest
from georep.settings import Settings
from georep.stores import RAW_TEXT_SCHEMA_VERSION
from tests.fakes import FakeSession


def _layout(tmp_path: Path) -> Layout:
    """Ein Layout mit Fremddaten, damit die drei Kontextschritte im Register stehen (Punkt 53)."""
    return Layout(
        tmp_path / "data",
        tmp_path / "cache",
        tmp_path / "reference",
        context_root=tmp_path / "context",
    )


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
    # Fundament F6: die drei Netzschritte schreiben JSONL aus einem Modul
    "meetings": COUNCIL_SCHEMA_VERSION,
    "consultations": COUNCIL_SCHEMA_VERSION,
    "persons": COUNCIL_SCHEMA_VERSION,
    # Fundament F1: der Rohtextstore schreibt seine Datei selbst, der Schritt nennt seine Version
    "raw_texts": RAW_TEXT_SCHEMA_VERSION,
    # Vorhaben 15: zwei Schritte eines Beitrags (``georep.enrich.functions``)
    "functions": FUNCTIONS_SCHEMA_VERSION,
    "cosponsors": COSPONSORS_SCHEMA_VERSION,
    # Vorhaben 14: zwei Schritte eines Beitrags (F2), beide aus dem Modul, das die Dateien schreibt
    "references": PROCEDURES_SCHEMA_VERSION,
    "procedures": PROCEDURES_SCHEMA_VERSION,
    # Vorhaben 22: die Auszüge (Netz) und die Tabellen je Wahlbezirk (``georep.enrich.need``)
    "need_data": NEED_DATA_SCHEMA_VERSION,
    "need": NEED_SCHEMA_VERSION,
}


@pytest.fixture
def steps(default_settings: Settings, tmp_path: Path) -> dict[str, int]:
    layout = _layout(tmp_path)
    # Fundament F6: die drei Netzschritte stehen nur mit ``council.enabled`` im Register
    council = default_settings.council.model_copy(update={"enabled": True})
    # Vorhaben 14: die Schritte eines Beitrags stehen nur mit ihrem Schalter im Register
    procedures = default_settings.procedures.model_copy(update={"enabled": True})
    # Vorhaben 22: die zwei Schritte stehen nur mit ``context.need.enabled`` im Register
    need = default_settings.context.need.model_copy(update={"enabled": True})
    context = default_settings.context.model_copy(update={"need": need})
    settings = default_settings.model_copy(
        update={"council": council, "procedures": procedures, "context": context}
    )
    return {s.name: s.schema_version for s in build_steps(settings, layout)}


def test_each_step_carries_the_schema_version_of_its_module(steps: dict[str, int]) -> None:
    for name, version in VERSIONS.items():
        assert steps[name] == version, (name, steps[name], version)


def test_a_bumped_schema_version_makes_the_stamp_stale(
    default_settings: Settings, tmp_path: Path
) -> None:
    """Der Grund für den Test oben: sonst meldet ``stamp_mismatch`` die Änderung nie."""
    layout = _layout(tmp_path)
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


def test_the_display_values_outside_the_fingerprint_are_in_the_report_hash(
    default_settings: Settings,
) -> None:
    """Vier Anzeigewerte lässt ``Settings.fingerprint`` aus -- und alle vier stehen auf der Seite.

    ``bodies.names_as_of``, ``period.label``, ``context.dataset`` und die ``label`` der
    Gewichtungsregeln. Ohne sie im Zusatz meldete ``georep status`` den Schritt ``report`` nach
    einer geänderten Namensnennung als „aktuell" (Review-Befund 8, 2026-10-13).
    """
    base = report_fingerprint(default_settings)
    changed: list[Settings] = [
        default_settings.model_copy(
            update={"bodies": default_settings.bodies.model_copy(update={"names_as_of": None})}
        ),
        default_settings.model_copy(
            update={"period": default_settings.period.model_copy(update={"label": "anders"})}
        ),
        default_settings.model_copy(
            update={
                "context": default_settings.context.model_copy(
                    update={
                        "dataset": default_settings.context.dataset.model_copy(
                            update={"publisher": "jemand anders"}
                        )
                    }
                )
            }
        ),
        default_settings.model_copy(
            update={
                "weights": default_settings.weights.model_copy(
                    update={
                        "paper_type": [
                            default_settings.weights.paper_type[0].model_copy(
                                update={"label": "anders beschriftet"}
                            ),
                            *default_settings.weights.paper_type[1:],
                        ]
                    }
                )
            }
        ),
    ]
    for settings in changed:
        # Der globale Fingerprint bleibt gleich -- genau darum braucht es den Zusatz.
        assert settings.fingerprint() == default_settings.fingerprint()
        assert report_fingerprint(settings) != base


def test_the_topics_step_carries_the_hash_of_its_stop_word_list(
    default_settings: Settings, tmp_path: Path
) -> None:
    """Die Stoppwortliste des Pakets prägt ``themen.parquet``, steht aber in keinem Eingabe-Hash.

    Im Fingerprint steht nur ihr **Name** (``topics.stop_words = "de"``); eine gestrichene Zeile in
    der Datei änderte das Modell und liess den Stamp gültig (Review-Befund 8, 2026-10-13).
    """
    layout = _layout(tmp_path)
    topics = next(s for s in build_steps(default_settings, layout) if s.name == "topics")
    assert topics.extra == stop_words_digest(default_settings.topics.stop_words)
    assert len(topics.extra) == 16

    folder = tmp_path / "paket"
    folder.mkdir()
    (folder / "stopwords_de.txt").write_text("und\noder\n", encoding="utf-8")
    before = stop_words_digest("de", folder)
    (folder / "stopwords_de.txt").write_text("und\n", encoding="utf-8")
    assert stop_words_digest("de", folder) != before
    # Ohne Liste gibt es keinen Zusatz, und der Schritt verhält sich wie jeder andere
    assert stop_words_digest("", folder) == ""
    assert stop_words_digest("gibtsnicht", folder) == ""


def test_only_the_report_and_topics_steps_carry_an_extra(
    default_settings: Settings, tmp_path: Path
) -> None:
    """Der Zusatz ist die Ausnahme, nicht die Regel: ein alter Stamp bleibt sonst gültig."""
    layout = _layout(tmp_path)
    found = {s.name: s.extra for s in build_steps(default_settings, layout)}
    assert found["report"] == report_fingerprint(default_settings)
    assert len(found["report"]) == 16
    assert sorted(name for name, extra in found.items() if extra) == ["report", "topics"]


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
        "Paketdateien oder Anzeige geändert"
    )
    stamped = dict(old_style) | {"extra": with_extra.extra}
    assert stamp_mismatch(stamped, with_extra, default_settings) is None
    assert stamp_mismatch(stamped, replace(with_extra, extra="0" * 16), default_settings) == (
        "Paketdateien oder Anzeige geändert"
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
    # Heute 19 im Kern: texts, raw_texts, voters, context, streets, pois, dictionary, corpus,
    # bodies, topics, committees, index, timeline, results, metrics, body_hits, weights, controls,
    # parties; dazu je ein Parquet-Schritt der Beiträge aus dem Register (Vorhaben 15: zwei).
    contributed = [
        s
        for s in georep.enrich.contributed_steps(default_settings, mini_run, FakeSession({}))
        if s.outputs[0].suffix == ".parquet" and not s.network  # Vorhaben 22: need_data ist Netz
    ]
    assert checked == 19 + len(contributed), checked


def _step_versions_in_source() -> dict[str, str]:
    """Schrittname -> Ausdruck, den ``pipeline.py`` oder ein Beitrag als ``schema_version`` übergibt.

    Gelesen wird der **Quelltext**, nicht der Laufzeitwert: nur so fällt auf, wenn jemand eine Zahl
    hinschreibt statt die Konstante seines Moduls zu nennen. Ein Wertvergleich sähe das nie, denn
    die meisten Versionen sind 1 (Review-Befund 3, 2026-10-13).
    """
    # Fundament F2: die Schritte der Vorhaben stehen in ``georep/enrich/``, nicht in ``pipeline.py``
    sources = [Path("src/georep/pipeline.py"), *sorted(Path("src/georep/enrich").glob("*.py"))]
    nodes = [
        node
        for source in sources
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
    ]
    found: dict[str, str] = {}
    for node in nodes:
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
SCHEMA_CONSTANTS_WITHOUT_A_STEP = {
    "georep.stores.TEXT_SCHEMA_VERSION",
    # Punkt 58, Review 2026-10-14: die Version der Parquet-Datei, die ``georep pack
    # --consultations`` schreibt. Sie gehört zu einem Befehl und nicht zu einem Schritt; der
    # Schritt ``bodies`` **liest** die Datei nur, und seine eigene Version ist
    # ``prep.bodies.BODIES_SCHEMA_VERSION``.
    "georep.pack.CONSULTATIONS_SCHEMA_VERSION",
    # Fundament F5: die Version der SQLite-Datei des Modellcaches. Kein Schritt schreibt sie als
    # Ausgabe; der Cache prüft sie selbst beim Öffnen (``ModelCache._open``), und die Ausgabe
    # eines Modellschritts trägt die Version ihres eigenen Moduls.
    "georep.ml.cache.CACHE_SCHEMA_VERSION",
    # Vorhaben 14: wie die Beratungsfolge die Version der Datei, die ``georep pack --attachments``
    # schreibt; die Schritte ``references`` und ``procedures`` lesen sie nur.
    "georep.pack.ATTACHMENTS_SCHEMA_VERSION",
}


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


# --- Review F1, Befund M1: der Bericht ohne Rohtextstore ----------------------------------------


def test_the_report_runs_on_a_data_root_without_a_raw_text_store(
    mini_run: Layout, default_settings: Settings, tmp_path: Path
) -> None:
    """Eine Datenwurzel von vor Fundament F1 hat keinen ``rohtexte.parquet``.

    ``georep run report`` brach dort ab, weil der Store eine harte Eingabe von ``report`` war, und
    der Hinweis „hilft `georep bootstrap`" stimmte nur für die Hauptperiode. Der Store ist nur
    Eingabe, wenn es ihn gibt; die Seite sagt dann nichts über den Rohtext.
    """
    data, cache = tmp_path / "data", tmp_path / "cache"
    shutil.copytree(mini_run.data_root, data)
    shutil.copytree(mini_run.cache_root, cache)
    layout = Layout(
        data, cache, mini_run.reference_root, mini_run.profile, context_root=mini_run.context_root
    )
    layout.raw_texts.unlink()
    # ``--force`` wie im Befund: ohne die Eingabe bleibt der alte Stamp gültig
    steps = build_steps(default_settings, layout)
    outcomes = run_pipeline(steps, default_settings, ["report"], force=True)
    assert [(o.step, o.status) for o in outcomes] == [("report", "ausgeführt")]
    report = next(s for s in steps if s.name == "report")
    assert report.optional == (layout.raw_texts,) and layout.texts in report.inputs
    # Die fehlende Datei steht im Stamp; kommt sie dazu, ist der Stamp veraltet
    stamped = json.loads(report.stamp_path.read_text(encoding="utf-8"))
    assert stamped["inputs"][layout.raw_texts.name] == MISSING
    assert stamp_mismatch(stamped, report, default_settings) is None
    shutil.copyfile(mini_run.raw_texts, layout.raw_texts)
    assert stamp_mismatch(stamped, report, default_settings) == (
        f"Eingabe geändert: {layout.raw_texts.name}"
    )


def _old_raw_store(path: Path) -> None:
    """Ein Rohtextstore in Schema-Version 1: ohne ``form_feeds``, mit Version 1 in den Metadaten."""
    from georep.io import write_parquet
    from georep.stores import RAW_TEXT_SCHEMA

    columns = {k: v for k, v in RAW_TEXT_SCHEMA.items() if k != "form_feeds"}
    row = {"name": "a.pdf", "text": "alt", "pages": 1, "chars": 3, "extractor": "x+roh"}
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(pl.DataFrame([row | {"pdf_sha256": "0"}], schema=columns), path, schema_version=1)


def test_raw_texts_says_it_wrote_an_old_store_empty_when_there_are_no_pdfs(
    default_settings: Settings, tmp_path: Path
) -> None:
    """Review F1, dritte Runde: der Schritt meldete „neu gelesen", auch wenn kein PDF da war."""
    import datetime as dt

    from georep.records import PaperRecord
    from georep.sources.pdfs import PdfStore
    from georep.stores import PaperStore, RawTextStore

    layout = _layout(tmp_path)
    record = PaperRecord(id="p1", name="A", date=dt.date(2024, 1, 1), file_name="a.pdf")
    PaperStore(layout.papers).save([record])
    PdfStore(layout.pdf_dir).ensure()
    _old_raw_store(layout.raw_texts)
    steps = build_steps(default_settings, layout)
    [outcome] = run_pipeline(steps, default_settings, ["raw_texts"])
    assert "ohne PDFs leer neu geschrieben, weil rohtexte.parquet trägt Schema-Version 1" in (
        outcome.reason
    )
    assert "neu gelesen" not in outcome.reason
    assert len(RawTextStore(layout.raw_texts)) == 0 and RawTextStore(layout.raw_texts).stale == ""


# --- Vorhaben 14: Eingaben gleichen Namens aus verschiedenen Ordnern ----------------------------


def _twins(tmp_path: Path) -> tuple[Step, Path, Path]:
    """Ein Schritt mit zwei Eingaben gleichen Namens, wie die Pakete zweier Nachbarperioden."""
    first, second = tmp_path / "a" / "papers.jsonl", tmp_path / "b" / "papers.jsonl"
    for path in (first, second):
        path.parent.mkdir(parents=True)
        path.write_text("{}\n", encoding="utf-8")
    out = tmp_path / "out.parquet"
    return Step("probe", (first, second), (out,), lambda: "nichts"), first, second


def test_two_inputs_with_the_same_name_both_reach_the_stamp(
    default_settings: Settings, tmp_path: Path
) -> None:
    """Der Stamp schlüsselte die Eingaben nach Dateinamen; zwei ``papers.jsonl`` (die Pakete von
    2014 bis 2020 und der laufenden Periode) teilten einen Schlüssel, und eine Änderung am ersten
    blieb unbemerkt (Vorhaben 14, 2026-11-24). ``compare`` hat dasselbe mit den Ergebnissen beider
    Perioden."""
    step, first, second = _twins(tmp_path)
    stamped: dict[str, object] = {
        "schema_version": step.schema_version,
        "settings": default_settings.fingerprint(),
        "extra": "",
        "code": __version__,
        "inputs": input_digests(step),
    }
    assert stamp_mismatch(stamped, step, default_settings) is None
    first.write_text('{"neu": 1}\n', encoding="utf-8")
    reason = stamp_mismatch(stamped, step, default_settings)
    assert reason is not None and str(first) in reason


def test_a_unique_name_keeps_its_key(tmp_path: Path) -> None:
    """Nur gleichnamige Eingaben bekommen den Pfad als Schlüssel; jeder andere Stamp bleibt gültig."""
    step, first, second = _twins(tmp_path)
    unique = replace(step, inputs=(first,))
    assert set(input_digests(unique)) == {"papers.jsonl"}
    assert set(input_digests(step)) == {str(first), str(second)}


def test_a_missing_input_is_named_with_its_full_path(
    default_settings: Settings, tmp_path: Path
) -> None:
    """Ein fehlendes Paket aus dem Repo heißt mit vollem Pfad, und der Hinweis auf ``bootstrap``
    gilt nur für die Datenwurzel (Review von Vorhaben 14, 2026-11-24)."""
    missing = Path("snapshots") / "fehlt" / "papers.jsonl"
    step = Step("probe", (missing,), (tmp_path / "out.parquet",), lambda: "nichts")
    with pytest.raises(MissingInputError, match=re.escape(str(missing.resolve()))) as found:
        run_pipeline([step], default_settings)
    assert "Arbeitsverzeichnis" in str(found.value)
