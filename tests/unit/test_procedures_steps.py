"""Der Beitrag von Vorhaben 14 als Schritte: Pfade, Eingaben, Stamps, Nachbarperioden.

Die kleine Stadt aus ``tests/procedures_city.py`` liegt hier als Lauf: eigener Korpus mit
Textstore, Gremien, Anlagenpaket, und die Nachbarperiode als Paket (``raw/papers.jsonl`` und
Textstore), wie ``procedures.related`` sie nennt. Die Schritte schreiben dieselben Kanten,
Vorgänge und Antworten wie die Funktionen über die ganze Stadt; die Kanten tragen nur die eigenen
Drucksachen als nennende.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep.analysis.procedures import EDGE_SCHEMA, FOREST_SCHEMA
from georep.bootstrap import bootstrap, bootstrap_from_settings
from georep.enrich import CONTRIBUTIONS
from georep.enrich.procedures import (
    PROCEDURES_SCHEMA_VERSION,
    procedure_files,
    procedure_steps,
)
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.papers import CORPUS_SCHEMA_VERSION, build_corpus
from georep.records import PaperRecord
from georep.settings import RelatedPeriod, Settings, load_settings
from georep.spans import SPAN_SCHEMA
from georep.stores import PaperStore, TextMeta, TextStore
from tests.fakes import FakeSession
from tests.procedures_city import (
    ANSWERS,
    DOCUMENTS,
    EDGES,
    FOREST,
    NEIGHBOUR,
    attachments,
)

# Beide Schritte sind offline; eine Session ohne Routen fiele bei jedem Aufruf auf.
OFFLINE = FakeSession({})


def _records(own: bool) -> list[PaperRecord]:
    return [
        PaperRecord(id=i, name=n, reference=r, date=d, paper_type=t, file_name=f"{i}.pdf")
        for i, p, r, t, n, d, _x, _a in DOCUMENTS
        if (not p) == own
    ]


def _texts(path: Path, own: bool) -> None:
    store = TextStore(path)
    for i, p, _r, _t, _n, _d, text, _a in DOCUMENTS:
        if (not p) == own:
            store.put(f"{i}.pdf", text, TextMeta(extractor="probe-1"))
    store.save()


@pytest.fixture
def city_run(tmp_path: Path, default_settings: Settings) -> tuple[Layout, Settings]:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", "stadt")
    layout.ensure_dirs()
    _texts(layout.texts, own=True)
    corpus = build_corpus(_records(own=True), TextStore(layout.texts))
    write_parquet(corpus, layout.corpus, schema_version=CORPUS_SCHEMA_VERSION)
    pl.DataFrame({"id": corpus.get_column("id"), "gremium": ["BV1"] * corpus.height}).write_parquet(
        layout.papers_bodies
    )
    attachments().write_parquet(procedure_files(layout).attachments)
    neighbour = tmp_path / "nachbar"
    PaperStore(neighbour / "raw" / "papers.jsonl").save(_records(own=False))
    _texts(neighbour / "texts.parquet", own=False)
    procedures = default_settings.procedures.model_copy(
        update={
            "enabled": True,
            "attachments": tmp_path / "paket" / "anlagen.parquet",
            "related": [
                RelatedPeriod(
                    profile=NEIGHBOUR,
                    papers=neighbour / "raw" / "papers.jsonl",
                    texts=neighbour / "texts.parquet",
                )
            ],
        }
    )
    return layout, default_settings.model_copy(update={"procedures": procedures})


def test_the_steps_write_the_known_city(city_run: tuple[Layout, Settings]) -> None:
    layout, settings = city_run
    steps = procedure_steps(settings, layout, OFFLINE)
    assert [s.name for s in steps] == ["references", "procedures"]
    assert {s.schema_version for s in steps} == {PROCEDURES_SCHEMA_VERSION}
    outcomes = run_pipeline(steps, settings)
    assert [o.status for o in outcomes] == ["ausgeführt", "ausgeführt"]
    files = procedure_files(layout)
    own_edges = [row for row in EDGES if row[0].startswith("p")]
    assert pl.read_parquet(files.edges).equals(
        pl.DataFrame(own_edges, schema=EDGE_SCHEMA, orient="row")
    )
    assert pl.read_parquet(files.documents).equals(
        pl.DataFrame(FOREST, schema=FOREST_SCHEMA, orient="row")
    )
    assert pl.read_parquet(files.answers).rows() == ANSWERS
    spans = pl.read_parquet(files.spans)
    assert spans.schema == pl.Schema(SPAN_SCHEMA)
    assert set(spans.get_column("extractor")) == {"probe-1/drucksachen-1"}
    again = run_pipeline(steps, settings)
    assert [o.status for o in again] == ["übersprungen", "übersprungen"]


def test_a_changed_neighbour_package_makes_both_steps_stale(
    city_run: tuple[Layout, Settings],
) -> None:
    """Frage 9.2: die Pakete der Nachbarn sind Eingaben, ihr Hash steht im Stamp."""
    layout, settings = city_run
    steps = procedure_steps(settings, layout, OFFLINE)
    run_pipeline(steps, settings)
    papers = settings.procedures.related[0].papers
    papers.write_text(papers.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert [o.status for o in run_pipeline(steps, settings, dry_run=True)] == [
        "geplant",
        "geplant",
    ]


def test_the_own_profile_is_never_its_own_neighbour(city_run: tuple[Layout, Settings]) -> None:
    layout, settings = city_run
    own = RelatedPeriod(
        profile=settings.default_profile, papers=Path("/fehlt.jsonl"), texts=Path("/fehlt.parquet")
    )
    procedures = settings.procedures.model_copy(
        update={"related": [*settings.procedures.related, own]}
    )
    steps = procedure_steps(settings.model_copy(update={"procedures": procedures}), layout, OFFLINE)
    assert Path("/fehlt.jsonl") not in steps[0].inputs


def test_without_the_switch_there_is_no_step(tmp_path: Path, default_settings: Settings) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref")
    off = default_settings.procedures.model_copy(update={"enabled": False})
    settings = default_settings.model_copy(update={"procedures": off})
    names = [s.name for s in build_steps(settings, layout)]
    assert "references" not in names and "procedures" not in names


def test_the_register_carries_the_contribution() -> None:
    """Genau einmal im Register; andere Vorhaben hängen sich davor und dahinter an (Synergie § 2.1)."""
    assert [c.name for c in CONTRIBUTIONS].count("14-vorgaenge") == 1


def test_bootstrap_copies_the_attachment_package(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    """Wie die Beratungsfolge (Punkt 58): das Paket kommt nach raw/, gelesen wird nur die Kopie."""
    package = tmp_path / "paket" / "raw" / "anlagen.parquet"
    package.parent.mkdir(parents=True)
    attachments().write_parquet(package)
    layout = Layout(tmp_path / "data", tmp_path / "cache", mini_root)
    report = bootstrap(layout, attachments=package)
    target = procedure_files(layout).attachments
    assert target.read_bytes() == package.read_bytes()
    assert target.name in report.copied
    switched_off = Layout(tmp_path / "data2", tmp_path / "cache2", mini_root)
    off = default_settings.procedures.model_copy(update={"enabled": False})
    bootstrap_from_settings(switched_off, default_settings.model_copy(update={"procedures": off}))
    assert not procedure_files(switched_off).attachments.exists()


def test_the_city_profiles_switch_the_steps_on(tmp_path: Path, default_settings: Settings) -> None:
    """Düsseldorf (alle drei Perioden erben es) und Mönchengladbach; die Schritte vor ``report``."""
    names = [s.name for s in build_steps(default_settings, Layout(tmp_path, tmp_path, tmp_path))]
    assert names[names.index("references") :][:3] == ["references", "procedures", "report"]
    for profile in ("duesseldorf-2014", "duesseldorf-2025", "moenchengladbach"):
        assert load_settings(profile=profile, cwd=Path("/nonexistent")).procedures.enabled
