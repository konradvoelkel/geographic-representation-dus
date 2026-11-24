"""Beitrag von Vorhaben 14: Vorgänge aus Drucksachennummern (``docs/plans/14-vorgaenge.md``).

Zwei Schritte nach F2, beide offline, beide hinter ``procedures.enabled``:

* ``references`` liest Titel, Text und Anlagennamen der eigenen Drucksachen und schreibt jede
  Nummer im Text als Spanne nach F3 (``verweise.parquet``, auch die ohne Ziel) und jede Kante, deren
  nennende Drucksache zum eigenen Korpus gehört (``vorgang_kanten.parquet``, schwache eingeschlossen).
* ``procedures`` setzt die Vorgänge als Wald zusammen (``dokumente_vorgang.parquet``, eine Zeile je
  Korpus-ID) und sucht je Anfrage ihre Antwort (``antwortzeiten.parquet``).

Die Rechnung liegt in ``prep.references`` und ``analysis.procedures``; hier stehen nur das Laden,
die Pfade (die dem Modul gehören, nicht ``Layout``) und die Schritte. Über die Wahl hinweg liest
das Profil die Nummern, Titel und Dokumentarten seiner Nachbarperioden aus deren Paketen
(``procedures.related``; Messdokument, Frage 9.2), und für die Vorgänge die Texte der wenigen
Nachbardrucksachen, die eine starke Kante haben können (``strong_candidates``). So rechnet jedes
Profil dieselben Vorgänge wie die Messung über die ganze Stadt, ohne auf den Lauf eines anderen
Profils zu warten.

Gesucht wird im kleingeschriebenen Textstore, wie in der Messung; die Spannen legt ``references``
danach über ``flatten_with_offsets`` (Nachzug F7, Punkt 74) auf den Rohtext, wo es ihn gibt
(``raw_bridges``), sonst bleiben sie auf dem Textstore (Synergie, Konflikt 1); ``section`` bleibt
leer bis Vorhaben 11.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

from georep.analysis.procedures import (
    ATTACHMENT_SCHEMA,
    DOCUMENT_SCHEMA,
    EDGE_SCHEMA,
    OWN,
    RawBridge,
    answer_times,
    assemble_edges,
    build_directory,
    document_roles,
    forest,
    onto_raw,
    parents,
    questions_of,
    scan,
    strong_candidates,
    supplement_pairs,
)
from georep.enrich import Contribution
from georep.errors import SchemaError
from georep.io import write_parquet
from georep.prep.bodies import BODY
from georep.prep.raw_texts import flatten_with_offsets
from georep.prep.references import ReferenceRules
from georep.records import PaperRecord
from georep.settings import profile_folder
from georep.spans import check_spans
from georep.stores import PaperStore, RawTextStore

if TYPE_CHECKING:
    from georep.http import Transport
    from georep.layout import Layout
    from georep.pipeline import Step
    from georep.settings import RelatedPeriod, Settings

# Die Schema-Version aller vier Ausgaben; sie steht an beiden Schritten (CLAUDE.md, „Jeder Step
# bekommt seine Schema-Version aus der Konstante des Moduls, das die Datei schreibt").
PROCEDURES_SCHEMA_VERSION = 1
# Das Verfahren, das die Spannen fand; steht hinter dem Extraktor des Texts in ``extractor``.
SPAN_METHOD = "drucksachen-1"


@dataclass(frozen=True)
class ProcedureFiles:
    attachments: Path  # Kopie des Anlagenpakets, von ``bootstrap`` gelegt
    spans: Path
    edges: Path
    documents: Path
    answers: Path


def procedure_files(layout: Layout) -> ProcedureFiles:
    """Die Pfade des Vorhabens; sie gehören dem Modul, nicht ``Layout`` (Synergie, § 2.1)."""
    return ProcedureFiles(
        attachments=layout.raw / "anlagen.parquet",
        spans=layout.processed / "verweise.parquet",
        edges=layout.processed / "vorgang_kanten.parquet",
        documents=layout.processed / "dokumente_vorgang.parquet",
        answers=layout.processed / "antwortzeiten.parquet",
    )


def neighbours(settings: Settings) -> list[RelatedPeriod]:
    """Die Nachbarperioden ohne die eigene (die liest ihren Korpus).

    Verglichen wird der Ordner, nicht der Name (Review K3): ``duesseldorf-vergleich`` rechnet im
    Ordner der Hauptperiode und las sie sonst als Nachbarn.
    """
    return [p for p in settings.procedures.related if profile_folder(p.profile) != settings.profile]


def related_inputs(settings: Settings, *, texts: bool) -> tuple[Path, ...]:
    """Die Pakete der Nachbarn als Eingaben: ihr Hash steht im Stamp (Frage 9.2)."""
    found: list[Path] = []
    for period in neighbours(settings):
        found.append(period.papers)
        if texts:
            found.append(period.texts)
    return tuple(found)


def read_papers(path: Path) -> list[PaperRecord]:
    """Die Paper eines Pakets: ``raw/papers.jsonl`` oder das Altformat der Arbeit (JSON-Liste)."""
    if path.suffix == ".jsonl":
        return list(PaperStore(path).load().values())
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise SchemaError(f"{path}: erwartet eine Liste von Papern im Altformat der Arbeit")
    return [PaperRecord.from_legacy(item) for item in items]


def read_attachments(path: Path | None) -> pl.DataFrame:
    """Das Anlagenpaket; ohne Paket ein leerer Frame (keine Anlagen, keine Antwortanlagen)."""
    if path is None:
        return pl.DataFrame(schema=ATTACHMENT_SCHEMA)
    frame = pl.read_parquet(path)
    if frame.schema != pl.Schema(ATTACHMENT_SCHEMA):
        raise SchemaError(f"{path}: Schema {dict(frame.schema)} statt {ATTACHMENT_SCHEMA}")
    if frame.get_column("id").n_unique() != frame.height:
        raise SchemaError(f"{path}: eine ID steht mehrfach")
    return frame


@dataclass(frozen=True)
class City:
    """Die Drucksachen der Stadt, wie das Profil sie kennt: eigene mit Text, Nachbarn ohne."""

    documents: pl.DataFrame  # DOCUMENT_SCHEMA, sortiert nach id
    file_names: dict[str, tuple[str, str]]  # Nachbar-ID -> (Profil, Dateiname des Texts)
    own_ids: list[str]


def _names(attachments: pl.DataFrame) -> pl.DataFrame:
    return attachments.select(
        "id", pl.col("anlagen").list.eval(pl.element().struct.field("name")).alias("anlagen")
    )


def load_city(settings: Settings, layout: Layout, attachments: pl.DataFrame) -> City:
    """Eigener Korpus und Nachbarperioden in einem Frame; eine ID des eigenen Korpus gewinnt."""
    own = pl.read_parquet(
        layout.corpus, columns=["id", "reference", "name", "paper_type", "date", "text"]
    ).with_columns(pl.lit(OWN).alias("periode"))
    own_ids = own.get_column("id").to_list()
    known = set(own_ids)
    rows = []
    file_names: dict[str, tuple[str, str]] = {}
    for period in neighbours(settings):
        for record in read_papers(period.papers):
            if record.id in known or record.id in file_names:
                continue
            file_names[record.id] = (period.profile, record.file_name or "")
            rows.append(
                (
                    record.id,
                    period.profile,
                    record.reference,
                    record.name,
                    record.paper_type,
                    record.date,
                    "",
                )
            )
    others = pl.DataFrame(
        rows,
        schema={k: v for k, v in DOCUMENT_SCHEMA.items() if k != "anlagen"},
        orient="row",
    )
    documents = (
        pl.concat([own.select(others.columns), others])
        .join(_names(attachments), on="id", how="left")
        .with_columns(pl.col("anlagen").fill_null([]))
        .select(list(DOCUMENT_SCHEMA))
        .sort("id")
    )
    return City(documents, file_names, own_ids)


def neighbour_texts(settings: Settings, city: City, wanted: set[str]) -> dict[str, str]:
    """Die Texte der Nachbardrucksachen in ``wanted`` aus den Textstores ihrer Pakete.

    Mehrere IDs können eine Datei teilen (Synergie § 1, „Dokument je PDF-Datei"); jede bekommt
    den Text, darum ``Dateiname -> IDs``.
    """
    by_profile: dict[str, dict[str, list[str]]] = {}
    for doc_id in sorted(wanted):
        profile, name = city.file_names[doc_id]
        if name:
            by_profile.setdefault(profile, {}).setdefault(name, []).append(doc_id)
    found: dict[str, str] = {}
    for period in neighbours(settings):
        names = by_profile.get(period.profile)
        if not names:
            continue
        store = pl.read_parquet(period.texts, columns=["name", "text"]).filter(
            pl.col("name").is_in(list(names))
        )
        for name, text in store.iter_rows():
            for doc_id in names[name]:
                found[doc_id] = text or ""
    return found


def text_extractors(layout: Layout) -> dict[str, str]:
    """Je Korpus-ID mit Text: der Extraktor des Textstores und das Verfahren der Spannen."""
    corpus = pl.read_parquet(layout.corpus, columns=["id", "file_name", "text"])
    store = pl.read_parquet(layout.texts, columns=["name", "extractor"])
    joined = corpus.filter(pl.col("text") != "").join(
        store, left_on="file_name", right_on="name", how="left"
    )
    return {
        doc_id: f"{extractor or ''}/{SPAN_METHOD}"
        for doc_id, extractor in joined.select("id", "extractor").iter_rows()
    }


def raw_bridges(
    settings: Settings, layout: Layout, own: pl.DataFrame, wanted: set[str]
) -> dict[str, RawBridge]:
    """Je ID in ``wanted`` der Rohtext mit der Stelle je Zeichen, wo er genau zum Text plättet.

    Nachzug F7 (Punkt 74, Synergie Konflikt 1): die Spannen liegen auf dem Rohtext, wo die
    Abschnitte von Vorhaben 11 liegen und die Kodierbögen von F4 lesen. Geprüft wird die Brücke
    selbst: der geplättete Rohtext muss **genau** der Text sein, in dem die Nummer gefunden wurde
    (F1 verspricht das für jedes Dokument; das verschlüsselte PDF hat keinen Rohtext). Ohne
    Rohtextstore -- auf Pages tragen nur die Hauptperiode und ihr Paket einen -- bleibt jede
    Spanne auf dem Textstore. Mehrere IDs einer Datei teilen eine Rechnung.
    """
    store = RawTextStore(layout.raw_texts)
    if not wanted or not layout.raw_texts.is_file() or not len(store):
        return {}
    names = dict(
        pl.read_parquet(layout.corpus, columns=["id", "file_name"])
        .filter(pl.col("id").is_in(list(wanted)))
        .iter_rows()
    )
    texts = dict(own.filter(pl.col("id").is_in(list(wanted))).select("id", "text").iter_rows())
    marker = settings.search.text_split_marker
    flattened: dict[str, tuple[RawBridge, str] | None] = {}  # Dateiname -> (Brücke, Text)
    found: dict[str, RawBridge] = {}
    for doc_id in sorted(wanted):
        name = names.get(doc_id) or ""
        if name not in flattened:
            raw = store.get(name)
            if raw is None:
                flattened[name] = None
            else:
                flat, offsets = flatten_with_offsets(raw, marker, store.form_feeds(name))
                extractor = str(store.rows[name]["extractor"])
                flattened[name] = ((raw, offsets, extractor), flat)
        known = flattened[name]
        if known is not None and known[1] == texts.get(doc_id):
            found[doc_id] = known[0]
    return found


def run_references(settings: Settings, layout: Layout) -> str:
    files = procedure_files(layout)
    rules = ReferenceRules.from_settings(settings.procedures)
    attachments = read_attachments(files.attachments if settings.procedures.attachments else None)
    city = load_city(settings, layout, attachments)
    directory = build_directory(city.documents, rules)
    own = city.documents.filter(pl.col("periode") == OWN)
    found = scan(own, directory, rules, text_extractors(layout))
    bridges = raw_bridges(settings, layout, own, set(found.spans.get_column("id").to_list()))
    spans = onto_raw(found.spans, bridges)
    lengths = {
        doc_id: len(bridges[doc_id][0]) if doc_id in bridges else len(text)
        for doc_id, text in own.select("id", "text").iter_rows()
    }
    check_spans(spans, lengths)
    own_ids = set(city.own_ids)
    supplements = [pair for pair in supplement_pairs(directory) if pair[0] in own_ids]
    edges = assemble_edges(found.occurrences, supplements, document_roles(city.documents, rules))
    write_parquet(spans, files.spans, schema_version=PROCEDURES_SCHEMA_VERSION)
    write_parquet(edges, files.edges, schema_version=PROCEDURES_SCHEMA_VERSION)
    strong = edges.filter("stark")
    across = edges.filter(pl.col("nach_periode") != OWN).height
    on_raw = len(set(spans.get_column("id").to_list()) & set(bridges))
    return (
        f"{spans.height} Nummern im Text ({on_raw} Dokumente auf dem Rohtext), {edges.height} "
        f"Kanten, davon {strong.height} stark und {across} in eine Nachbarperiode"
    )


def run_procedures(settings: Settings, layout: Layout) -> str:
    files = procedure_files(layout)
    rules = ReferenceRules.from_settings(settings.procedures)
    attachments = read_attachments(files.attachments if settings.procedures.attachments else None)
    city = load_city(settings, layout, attachments)
    directory = build_directory(city.documents, rules)
    roles = document_roles(city.documents, rules)
    own_edges = pl.read_parquet(files.edges)
    if own_edges.schema != pl.Schema(EDGE_SCHEMA):
        raise SchemaError(f"{files.edges}: Schema {dict(own_edges.schema)} statt {EDGE_SCHEMA}")
    others = city.documents.filter(pl.col("periode") != OWN)
    wanted = strong_candidates(others, directory, rules)
    texts = neighbour_texts(settings, city, wanted)
    candidates = others.filter(pl.col("id").is_in(list(wanted))).with_columns(
        pl.col("id").replace_strict(texts, default="").alias("text")
    )
    neighbour_ids = set(others.get_column("id").to_list())
    supplements = [pair for pair in supplement_pairs(directory) if pair[0] in neighbour_ids]
    neighbour_edges = assemble_edges(
        scan(candidates, directory, rules).occurrences, supplements, roles
    ).filter("stark")
    every = pl.concat([own_edges, neighbour_edges]).sort("von", "nach")
    parent = parents(every, roles)
    members = city.documents.get_column("id").to_list()
    documents = forest(parent, members, city.own_ids)
    gremien = pl.read_parquet(layout.papers_bodies, columns=["id", BODY])
    questions = (
        city.documents.filter(pl.col("id").is_in(questions_of(roles)))
        .select("id", "date")
        .join(gremien.rename({BODY: "gremium"}), on="id", how="left")
    )
    answers = answer_times(
        questions,
        attachments,
        every,
        roles,
        rules,
        settings.procedures.attachment_dates_invalid,
    )
    write_parquet(documents, files.documents, schema_version=PROCEDURES_SCHEMA_VERSION)
    write_parquet(answers, files.answers, schema_version=PROCEDURES_SCHEMA_VERSION)
    grouped = documents.filter(pl.col("groesse") > 1)
    answered = answers.filter(pl.col("quelle") != "keine").height
    return (
        f"{grouped.get_column('vorgang').n_unique()} Vorgänge mit {grouped.height} eigenen "
        f"Dokumenten ({len(wanted)} Nachbartexte gelesen); {answered} von {answers.height} "
        "Anfragen mit Antwort im Ratsinformationssystem"
    )


def procedure_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Die zwei Schritte, wenn das Profil sie einschaltet; ohne Schalter keiner.

    ``http`` ist die Naht von F7 (Punkt 74); beide Schritte sind offline und rufen ihn nie.
    """
    if not settings.procedures.enabled:
        return []
    from georep.pipeline import Step  # F2: ein Import auf Modulebene wäre ein Kreis

    files = procedure_files(layout)
    attachments = (files.attachments,) if settings.procedures.attachments else ()
    return [
        Step(
            "references",
            (layout.corpus, layout.texts, *attachments, *related_inputs(settings, texts=False)),
            (files.spans, files.edges),
            lambda: run_references(settings, layout),
            PROCEDURES_SCHEMA_VERSION,
            # Nachzug F7: die Spannen liegen auf dem Rohtext, wo es ihn gibt; ohne Store bleiben
            # sie auf dem Textstore, und ihr Fehlen bricht nichts ab (wie bei ``report``, F1)
            optional=(layout.raw_texts,),
        ),
        Step(
            "procedures",
            (
                layout.corpus,
                layout.papers_bodies,
                files.edges,
                *attachments,
                *related_inputs(settings, texts=True),
            ),
            (files.documents, files.answers),
            lambda: run_procedures(settings, layout),
            PROCEDURES_SCHEMA_VERSION,
        ),
    ]


CONTRIBUTION = Contribution(name="14-vorgaenge", steps=procedure_steps)
