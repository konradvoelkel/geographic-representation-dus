"""Der Schritt ``summaries`` (Vorhaben 20) mit ``FakeGenerator``: nie ein Modell, nie ein Ratstext.

Der Datensatz ist klein und erfunden: Rohtexte mit Seitenkopfzeile und Seitenwechsel, die
Abschnitte von Vorhaben 11 als Positionsspannen (``value`` leer, gelesen wird über ``read_span``),
ein Kopf mit Beratungsfolge und ``rumpf_leer``, ein Dokument ohne Rohtext.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from georep.contracts import one_row_per_document
from georep.enrich import CONTRIBUTIONS
from georep.enrich.fidelity import FIDELITY_COLUMNS
from georep.enrich.sections import sections_files
from georep.enrich.summaries import (
    PROMPT_VERSION,
    SUMMARIES_SCHEMA_VERSION,
    SUMMARY_SCHEMA,
    model_steps,
    summaries_files,
    summaries_steps,
    summary_inputs,
)
from georep.errors import ModelRejectedError
from georep.io import write_parquet
from georep.layout import Layout
from georep.ml.base import GenerationOptions, Reply
from georep.pipeline import Step, build_steps, run_pipeline
from georep.prep.structure import HEAD_SCHEMA, STRUCTURE_SCHEMA_VERSION
from georep.settings import Settings, Summaries
from georep.spans import SPAN_SCHEMA, sort_spans
from georep.stores import RawTextStore
from tests.fakes import FakeGenerator, FakeSession

HTTP = FakeSession({})
BETREFF = "Betrifft: Neue Bänke am Kanalufer"
VORSCHLAG = "Beschlussdarstellung:\nDer Ausschuss beschließt drei Bänke.\nSeite 2\nfür 4.500 €."
TEXT_A = f"{BETREFF}\n{VORSCHLAG}\fSachdarstellung:\nDie Bänke sind alt."
TEXT_B = "Betrifft: Mitteilung\nHierzu teilt das Amt mit: Die Bänke werden im Frühjahr aufgestellt."
TEXT_C = "Betrifft: Nur ein Kopf"
TEXTS = {"a.pdf": TEXT_A, "b.pdf": TEXT_B, "c.pdf": TEXT_C}
CORPUS = [
    ("a", "Bänke am Kanalufer", "OVA/7/2025", date(2025, 3, 4), "Beschlussvorlage", "a.pdf"),
    ("b", "Mitteilung zu Bänken", "BV2/1/2025", date(2025, 3, 5), "Informationsvorlage", "b.pdf"),
    ("c", "Nur ein Kopf", "BV2/2/2025", date(2025, 3, 6), "Informationsvorlage", "c.pdf"),
    ("d", "Ohne Datei", "BV2/3/2025", date(2025, 3, 7), "Antrag", None),
]


def _span(
    doc: str, text: str, piece: str, norm: str, section: str | None = None
) -> dict[str, object]:
    start = text.index(piece)
    return {
        "id": doc,
        "start": start,
        "end": start + len(piece),
        "kind": "abschnitt",
        "value": "",
        "norm": norm,
        "section": section or norm,
        "extractor": "probe+roh/struktur-1",
    }


@pytest.fixture
def settings(default_settings: Settings) -> Settings:
    return default_settings.model_copy(
        update={"summaries": Summaries(enabled=True, model="fake-chat")}
    )


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    layout.ensure_dirs()
    corpus = pl.DataFrame(
        CORPUS,
        schema=["id", "name", "reference", "date", "paper_type", "file_name"],
        orient="row",
    ).with_columns(
        pl.lit([], dtype=pl.List(pl.String)).alias("consultation_organizations"),
        pl.col("name").str.to_lowercase().alias("text"),
    )
    corpus.write_parquet(layout.corpus)
    store = RawTextStore(layout.raw_texts)
    for name, text in TEXTS.items():
        store.put(name, text, pages=text.count("\f") + 1, extractor="probe+roh", pdf_sha256="0")
    store.save()
    vorschlag = TEXT_A[TEXT_A.index("Der Ausschuss") : TEXT_A.index("\f")]
    spans = sort_spans(
        pl.DataFrame(
            [
                _span("a", TEXT_A, BETREFF, "betreff"),
                _span("a", TEXT_A, vorschlag, "beschlussvorschlag"),
                _span("a", TEXT_A, "4.500 €.", "finanzen", "beschlussvorschlag"),  # Ebene 2
                _span("a", TEXT_A, "Die Bänke sind alt.", "sachdarstellung"),
                _span("b", TEXT_B, "Betrifft: Mitteilung", "betreff"),
                _span("c", TEXT_C, TEXT_C, "betreff"),
            ],
            schema=SPAN_SCHEMA,
        )
    )
    files = sections_files(layout)
    write_parquet(spans, files.sections, schema_version=STRUCTURE_SCHEMA_VERSION)
    folge = [
        {
            "gremium": "Bauausschuss",
            "gremium_kuerzel": None,
            "datum": None,
            "qualitaet": "Vorberatung",
        },
        {"gremium": "Rat", "gremium_kuerzel": "RAT", "datum": None, "qualitaet": "Entscheidung"},
    ]
    head = pl.DataFrame(
        {
            "id": ["a", "b", "c", "d"],
            "beratungsfolge": [folge, [], [], None],
            "rumpf_leer": [False, False, True, None],
        },
        schema={k: HEAD_SCHEMA[k] for k in ("id", "beratungsfolge", "rumpf_leer")},
    )
    full = pl.DataFrame(schema=HEAD_SCHEMA).vstack(
        head.with_columns(
            [
                pl.lit(None, dtype=t).alias(c)
                for c, t in HEAD_SCHEMA.items()
                if c not in head.columns
            ]
        ).select(list(HEAD_SCHEMA))
    )
    write_parquet(full, files.head, schema_version=STRUCTURE_SCHEMA_VERSION)
    return layout


def _step(settings: Settings, layout: Layout, generator: object | None = None) -> Step:
    steps = model_steps(settings, layout, generator or FakeGenerator())  # type: ignore[arg-type]
    assert [s.name for s in steps] == ["summaries"]
    return steps[0]


def test_the_contribution_is_registered_after_the_sections(default_settings: Settings) -> None:
    names = [c.name for c in CONTRIBUTIONS]
    assert names[-1] == "20-kurzfassungen" and names.index("11-struktur") < names.index(
        "20-kurzfassungen"
    )
    off = default_settings.model_copy(update={"summaries": Summaries(enabled=False)})
    layout = Layout(Path("/nonexistent/d"), Path("/nonexistent/c"), Path("/nonexistent/r"))
    assert summaries_steps(off, layout, HTTP) == []


def test_the_step_reads_and_writes_what_the_plan_names(settings: Settings, layout: Layout) -> None:
    step = _step(settings, layout)
    files = summaries_files(layout)
    sections = sections_files(layout)
    assert step.outputs == (files.summaries, files.fidelity)
    assert set(step.inputs) == {layout.corpus, layout.raw_texts, sections.sections, sections.head}
    assert step.schema_version == SUMMARIES_SCHEMA_VERSION
    assert step.models is not None and step.models.identity()["prompt"] == PROMPT_VERSION
    for path in step.outputs:
        assert path.is_relative_to(layout.cache_root) and not path.is_relative_to(layout.data_root)


def test_the_inputs_read_the_spans_without_page_noise(settings: Settings, layout: Layout) -> None:
    inputs = summary_inputs(settings, layout)
    assert sorted(inputs) == ["a", "b", "c"]  # d hat keinen Rohtext
    a = inputs["a"]
    assert a.source == "abschnitte"
    assert a.sections == ("betreff", "beschlussvorschlag", "sachdarstellung")
    assert "Seite 2" not in a.text  # page_noise des Profils, gelesen mit read_span
    assert "Der Ausschuss beschließt drei Bänke." in a.text
    assert "Beratung: Bauausschuss (Vorberatung), Rat (Entscheidung)" in a.text
    assert "Absender: nicht angegeben" in a.text  # ohne Urhebertabelle
    assert inputs["b"].source == "rohtext"
    assert "Die Bänke werden im Frühjahr aufgestellt." in inputs["b"].text
    assert inputs["c"].source == "ohne_text"  # rumpf_leer, Frage 20.6


def test_a_run_with_models_writes_both_tables(settings: Settings, layout: Layout) -> None:
    outcome = run_pipeline([_step(settings, layout)], settings, models=True)[0]
    assert outcome.status == "ausgeführt", outcome.reason
    files = summaries_files(layout)
    summaries = pl.read_parquet(files.summaries)
    assert summaries.schema == pl.Schema(SUMMARY_SCHEMA)
    assert one_row_per_document(summaries, ["a", "b", "c"])
    rows = {r["id"]: r for r in summaries.iter_rows(named=True)}
    assert rows["a"]["text"].startswith("Kurzfassung ") and rows["a"]["grund"] is None
    assert (rows["c"]["text"], rows["c"]["grund"]) == (None, "ohne_text")
    assert rows["b"]["eingabe_quelle"] == "rohtext"
    assert {r["modell"] for r in rows.values()} == {"fake-chat:latest"}
    assert {r["prompt"] for r in rows.values()} == {PROMPT_VERSION}
    fidelity = pl.read_parquet(files.fidelity)
    assert fidelity.schema == pl.Schema({"id": pl.String(), **FIDELITY_COLUMNS})
    assert fidelity.get_column("id").to_list() == ["a", "b"]
    again = run_pipeline([_step(settings, layout)], settings, models=True)[0]
    assert again.status == "übersprungen" and again.reason == "aktuell"


def test_a_partial_run_leaves_documents_open(settings: Settings, layout: Layout) -> None:
    ml = settings.ml.model_copy(update={"limit": 1})
    limited = settings.model_copy(update={"ml": ml})
    outcome = run_pipeline([_step(limited, layout)], limited, models=True)[0]
    assert outcome.status == "ausgeführt"
    summaries = pl.read_parquet(summaries_files(layout).summaries)
    assert summaries.get_column("grund").to_list().count("offen") == 1
    assert pl.read_parquet(summaries_files(layout).fidelity).height == 1
    full = run_pipeline([_step(settings, layout)], settings, models=True)[0]
    assert full.status == "ausgeführt" and "offen: 1 Eingaben" in full.reason


def test_a_truncated_answer_is_kept_and_never_passes(settings: Settings, layout: Layout) -> None:
    generation = settings.ml.generation.model_copy(update={"num_predict": 2})
    short = settings.model_copy(
        update={"ml": settings.ml.model_copy(update={"generation": generation})}
    )
    run_pipeline([_step(short, layout)], short, models=True)
    summaries = pl.read_parquet(summaries_files(layout).summaries)
    assert summaries.filter(pl.col("text").is_not_null()).get_column("abgeschnitten").all()
    assert not pl.read_parquet(summaries_files(layout).fidelity).get_column("ok").any()


class RejectingGenerator(FakeGenerator):
    """Weist jeden Prompt ab, der ``marker`` enthält, wie ollama mit 400."""

    def __init__(self, marker: str) -> None:
        super().__init__()
        self.marker = marker

    def generate(
        self, prompt: str, *, system: str = "", options: GenerationOptions | None = None
    ) -> Reply:
        if self.marker in prompt:
            raise ModelRejectedError(f"400: {self.marker}")
        return super().generate(prompt, system=system, options=options)


def test_a_rejected_document_has_no_summary_and_says_why(
    settings: Settings, layout: Layout
) -> None:
    step = _step(settings, layout, RejectingGenerator("Frühjahr"))
    outcome = run_pipeline([step], settings, models=True)[0]
    assert outcome.status == "ausgeführt"
    rows = dict(
        pl.read_parquet(summaries_files(layout).summaries).select("id", "grund").iter_rows()
    )
    assert rows == {"a": None, "b": "abgewiesen", "c": "ohne_text"}
    again = run_pipeline(
        [_step(settings, layout, RejectingGenerator("Frühjahr"))], settings, models=True
    )
    assert again[0].reason == "aktuell, 1 Eingaben abgewiesen"


def test_without_models_the_step_is_skipped_and_asks_no_server(
    settings: Settings, layout: Layout
) -> None:
    steps = build_steps(settings, layout, HTTP)
    mine = [s for s in steps if s.name == "summaries"]
    assert len(mine) == 1 and mine[0].models is not None
    assert run_pipeline(mine, settings)[0].status == "übersprungen"


def test_the_command_recomputes_the_flagged_claims(settings: Settings, layout: Layout) -> None:
    """``georep summary`` nennt die beanstandeten Angaben, ohne dass eine Datei sie trägt: die
    Antwort von ``FakeGenerator`` nennt eine Zeichenzahl, die in keiner Eingabe steht."""
    from georep.enrich.summary_command import one_document

    run_pipeline([_step(settings, layout)], settings, models=True)
    lines = one_document("OVA/7/2025", layout, settings)
    assert any(line.startswith("  unbelegt (zahl/zahl): ") for line in lines), lines
    assert not any("Angaben nicht nachrechenbar" in line for line in lines)
