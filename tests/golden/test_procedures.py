"""Vorhaben 14 über die Pakete im Repo: die Zahlen des Messdokuments, nachgerechnet.

Stadtweit, aus genau den Paketen, die die Profile nennen (``procedures.related``, die Pakete von
Mönchengladbach, die Anlagenpakete): Kanten, starke Kanten, Vorgänge und Antworten wie im
Messdokument (``docs/plans/14-vorgaenge.md``, § 3.3, § 3.6 und § 5.1, gemessen am 2026-11-23).
Danach je Düsseldorfer Periode die beiden Schritte selbst, mit den anderen Perioden als Nachbarn:
die eigenen Kanten der drei Profile ergeben zusammen die Stadt, und jede Drucksache hat in ihrem
Profil denselben Vorgang und dieselbe Antwort wie in der Rechnung über die ganze Stadt.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep.analysis.procedures import (
    DOCUMENT_SCHEMA,
    answer_times,
    assemble_edges,
    build_directory,
    document_roles,
    forest,
    parents,
    scan,
    supplement_pairs,
)
from georep.enrich.procedures import (
    procedure_files,
    read_attachments,
    read_papers,
    run_procedures,
    run_references,
)
from georep.io import write_parquet
from georep.layout import Layout
from georep.prep.papers import CORPUS_SCHEMA_VERSION, build_corpus
from georep.prep.references import QUESTION, ReferenceRules
from georep.settings import Settings, load_settings
from georep.stores import TextStore

pytestmark = pytest.mark.slow

NOWHERE = Path("/nonexistent")
DUS_PROFILES = ("duesseldorf-2014", "duesseldorf", "duesseldorf-2025")


def _documents(papers: Path, texts: Path, period: str, attachments: pl.DataFrame) -> pl.DataFrame:
    store = TextStore(texts)
    rows = [
        (
            r.id,
            period,
            r.reference,
            r.name,
            r.paper_type,
            r.date,
            store.get(r.file_name or "") or "",
        )
        for r in read_papers(papers)
    ]
    names = attachments.select(
        "id", pl.col("anlagen").list.eval(pl.element().struct.field("name")).alias("anlagen")
    )
    return (
        pl.DataFrame(
            rows, schema={k: v for k, v in DOCUMENT_SCHEMA.items() if k != "anlagen"}, orient="row"
        )
        .join(names, on="id", how="left")
        .with_columns(pl.col("anlagen").fill_null([]))
        .select(list(DOCUMENT_SCHEMA))
    )


class City:
    def __init__(self, settings: Settings, packages: list[tuple[str, Path, Path]]) -> None:
        self.settings = settings
        self.rules = ReferenceRules.from_settings(settings.procedures)
        self.attachments = read_attachments(settings.procedures.attachments)
        self.documents = pl.concat(
            [_documents(p, t, period, self.attachments) for period, p, t in packages]
        ).sort("id")
        directory = build_directory(self.documents, self.rules)
        self.roles = document_roles(self.documents, self.rules)
        self.edges = assemble_edges(
            scan(self.documents, directory, self.rules).occurrences,
            supplement_pairs(directory),
            self.roles,
        )
        ids = self.documents.get_column("id").to_list()
        self.forest = forest(parents(self.edges, self.roles), ids, ids)
        # Über die Stadt ist jede Periode „eigen": alle Anfragen, nicht nur die mit leerer Periode
        asked = self.roles.filter(pl.col("rolle") == QUESTION).get_column("id")
        questions = self.documents.filter(pl.col("id").is_in(asked.implode())).select(
            "id", "date", pl.lit(None, pl.String).alias("gremium")
        )
        self.answers = answer_times(
            questions,
            self.attachments,
            self.edges,
            self.roles,
            self.rules,
            settings.procedures.attachment_dates_invalid,
        )
        self.period = dict(self.documents.select("id", "periode").iter_rows())


@pytest.fixture(scope="module")
def dus() -> City:
    settings = load_settings(cwd=NOWHERE)
    related = [(p.profile, p.papers, p.texts) for p in settings.procedures.related]
    assert [profile for profile, _, _ in related] == list(DUS_PROFILES)
    return City(settings, related)


@pytest.fixture(scope="module")
def mg() -> City:
    settings = load_settings(profile="moenchengladbach", cwd=NOWHERE)
    root = settings.reference_root
    return City(
        settings,
        [
            (
                "moenchengladbach",
                root / "raw" / "papers.jsonl",
                root / "cache" / "text" / "texts.parquet",
            )
        ],
    )


def test_the_edges_of_the_measurement(dus: City, mg: City) -> None:
    """§ 3.3 und § 5.1: 14 483 und 387 Kanten, davon 3 392 und 171 stark."""
    assert (dus.edges.height, mg.edges.height) == (14_483, 387)
    assert (dus.edges.filter("stark").height, mg.edges.filter("stark").height) == (3_392, 171)
    across = dus.edges.filter(
        pl.col("von").replace_strict(dus.period) != pl.col("nach").replace_strict(dus.period)
    )
    assert (across.height, across.filter("stark").height) == (2_599, 254)
    strong = dict(
        pl.concat([dus.edges, mg.edges]).filter("stark").group_by("typ").len().iter_rows()
    )
    assert strong == {
        "umsetzung": 1_500,
        "aenderung": 593,
        "kontrolle": 566,
        "nachtrag": 337,
        "bezug": 322,
        "fortsetzung": 105,
        "nachfrage": 73,
        "antwort": 67,
    }


def _procedures(city: City) -> tuple[int, int, int]:
    grouped = city.forest.filter(pl.col("groesse") > 1)
    largest = grouped.get_column("groesse").max()
    assert isinstance(largest, int)
    return grouped.get_column("vorgang").n_unique(), grouped.height, largest


def test_the_procedures_of_the_measurement(dus: City, mg: City) -> None:
    """§ 5.1: Düsseldorf 2 169 Vorgänge mit 4 643 Dokumenten, größter 7; Mönchengladbach 99 mit 217."""
    assert _procedures(dus) == (2_169, 4_643, 7)
    assert _procedures(mg) == (99, 217, 4)


def test_the_answers_of_the_measurement(dus: City) -> None:
    """§ 5.1: 3 237 von 8 168 Anfragen, 3 213 davon an der Anlage; Median 18 Tage bei n = 1 948."""
    answered = dus.answers.filter(pl.col("quelle") != "keine")
    assert (dus.answers.height, answered.height) == (8_168, 3_237)
    assert answered.filter(pl.col("quelle") != "drucksache").height == 3_213
    days = dus.answers.get_column("tage").drop_nulls()
    assert (days.len(), days.median()) == (1_948, 18.0)


def test_each_period_computes_the_same_city(dus: City, tmp_path: Path) -> None:
    """Die Schritte je Profil, mit den anderen Perioden aus ihren Paketen (Frage 9.2)."""
    edges, forests, answers = [], [], []
    for profile in DUS_PROFILES:
        settings = load_settings(profile=profile, cwd=NOWHERE)
        layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", profile)
        layout.ensure_dirs()
        (own,) = [p for p in settings.procedures.related if p.profile == profile]
        corpus = build_corpus(read_papers(own.papers), TextStore(own.texts))
        write_parquet(corpus, layout.corpus, schema_version=CORPUS_SCHEMA_VERSION)
        layout.texts.write_bytes(own.texts.read_bytes())  # der Extraktor der Spannen
        pl.DataFrame(
            {
                "id": corpus.get_column("id"),
                "gremium": pl.Series([None] * corpus.height, dtype=pl.String),
            }
        ).write_parquet(layout.papers_bodies)
        files = procedure_files(layout)
        assert settings.procedures.attachments is not None
        files.attachments.write_bytes(settings.procedures.attachments.read_bytes())
        run_references(settings, layout)
        run_procedures(settings, layout)
        edges.append(pl.read_parquet(files.edges))
        forests.append(pl.read_parquet(files.documents))
        answers.append(pl.read_parquet(files.answers))
    # ``nach_periode`` ist je Profil leer für die eigenen Drucksachen, in der Stadt deren Periode
    union = pl.concat(edges).sort("von", "nach")
    columns = [c for c in union.columns if c != "nach_periode"]
    assert union.select(columns).equals(dus.edges.select(columns))
    same = pl.col("von").replace_strict(dus.period) == pl.col("nach").replace_strict(dus.period)
    expected = dus.edges.select(pl.when(same).then(pl.lit("")).otherwise("nach_periode"))
    assert union.get_column("nach_periode").equals(expected.to_series(), check_names=False)
    assert pl.concat(forests).sort("id").equals(dus.forest)
    keys = ["id", "quelle", "antwort_datum", "tage", "antwort_id", "alter_am_abruf"]
    assert pl.concat(answers).sort("id").select(keys).equals(dus.answers.select(keys))
