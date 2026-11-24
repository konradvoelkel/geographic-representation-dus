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
    City,
    neighbour_texts,
    procedure_files,
    procedure_steps,
)
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.papers import CORPUS_SCHEMA_VERSION, build_corpus
from georep.records import PaperRecord
from georep.settings import (
    RelatedPeriod,
    Settings,
    available_profiles,
    load_settings,
    profile_folder,
)
from georep.spans import SPAN_SCHEMA
from georep.stores import PAGE_BREAK, PaperStore, RawTextStore, TextMeta, TextStore
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
RAW_IDS = ("p05", "p14")  # eigene Drucksachen mit Rohtext; p06 hat keinen


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
    # Rohtext für zwei eigene Drucksachen: Kopf mit einer Nummer vor dem Marker, eine Seite, dann
    # der Text groß geschrieben. Geplättet ist er genau der Text des Textstores (F1).
    raw = RawTextStore(layout.raw_texts)
    for doc_id in RAW_IDS:
        text = next(row[6] for row in DOCUMENTS if row[0] == doc_id)
        raw.put(
            f"{doc_id}.pdf",
            f"KOPF RAT/0/2000 BETRIFFT{PAGE_BREAK}{text.upper()}",
            pages=2,
            extractor="probe-1+roh",
            pdf_sha256="",
        )
    raw.save()
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
    # Nachzug F7: auf dem Rohtext, wo es ihn gibt, sonst auf dem Textstore; extractor sagt welcher
    assert spans.select("id", "value", "extractor").rows() == [
        ("p05", "OVA/2/2021", "probe-1+roh/drucksachen-1"),
        ("p06", "rat/1/2021", "probe-1/drucksachen-1"),
        ("p14", "RAT/13/2021", "probe-1+roh/drucksachen-1"),
    ]
    raw = RawTextStore(layout.raw_texts)
    for doc_id, start, end, value in spans.select("id", "start", "end", "value").iter_rows():
        if doc_id in RAW_IDS:
            assert (raw.get(f"{doc_id}.pdf") or "")[start:end] == value
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


def test_the_comparison_profile_does_not_read_its_own_period_as_a_neighbour(
    tmp_path: Path,
) -> None:
    """Review K3: ``duesseldorf-vergleich`` rechnet im Ordner der Hauptperiode, heißt aber anders.

    Der Abgleich über den Profilnamen hielt die Hauptperiode dort für einen Nachbarn und las ihr
    Paket; über den Ordner ist sie das eigene Profil, in jedem Profil der Stadt.
    """
    layout = Layout(tmp_path, tmp_path, tmp_path)
    for profile in ("duesseldorf", "duesseldorf-vergleich", "duesseldorf-2014", "duesseldorf-2025"):
        settings = load_settings(profile=profile, cwd=Path("/nonexistent"))
        own = [
            p for p in settings.procedures.related if profile_folder(p.profile) == settings.profile
        ]
        assert len(own) == 1, profile
        inputs = set(procedure_steps(settings, layout, OFFLINE)[1].inputs)
        assert own[0].papers not in inputs and own[0].texts not in inputs, profile
        assert len(inputs & {p.papers for p in settings.procedures.related}) == 2, profile


def test_every_profile_builds_its_register_in_order(tmp_path: Path) -> None:
    """Review B1: ``build_steps`` prüft die Folge (``check_step_order``, F7) in jedem Paketprofil;
    die beiden Schritte lesen nichts, was erst ein späterer schreibt."""
    for profile in available_profiles():
        settings = load_settings(profile=profile, cwd=Path("/nonexistent"))
        names = [s.name for s in build_steps(settings, Layout(tmp_path, tmp_path, tmp_path))]
        if settings.procedures.enabled:
            assert names.index("bodies") < names.index("references") < names.index("procedures")
            assert names.index("procedures") < names.index("report"), profile


def test_two_neighbour_papers_of_one_file_both_get_its_text(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Review, Nit (Synergie § 1, „Dokument je PDF-Datei"): mehrere IDs teilen eine Datei; jede
    bekommt den Text, nicht nur die letzte."""
    store = TextStore(tmp_path / "texts.parquet")
    store.put("f.pdf", "der text", TextMeta(extractor="probe-1"))
    store.save()
    period = RelatedPeriod(profile=NEIGHBOUR, papers=tmp_path / "p.jsonl", texts=store.path)
    settings = default_settings.model_copy(
        update={"procedures": default_settings.procedures.model_copy(update={"related": [period]})}
    )
    city = City(
        pl.DataFrame(), {"x1": (NEIGHBOUR, "f.pdf"), "x2": (NEIGHBOUR, "f.pdf")}, own_ids=[]
    )
    assert neighbour_texts(settings, city, {"x1", "x2"}) == {"x1": "der text", "x2": "der text"}
