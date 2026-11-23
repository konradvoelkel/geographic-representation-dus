"""Der Kodierauftrag je Kodierer (``georep validate tasks <vorhaben> --coder A|B``, F4).

Je Einheit der Stichprobe eine JSONL-Zeile: der Schlüssel, die Frage, je Dokument ein Ausschnitt
aus dem Text mit seinen hervorgehobenen Spannen (Schema von F3), die Optionen des Codebuchs und
eine leere Antwort. Daneben eine Antwortdatei, die der Kodier-Agent füllt (je Zeile ``id``,
``label``, ``begruendung``), und das Codebuch als Text. Alles liegt unter
``validation.coding_root/<vorhaben>/<A|B>/``, nie im Repo: die Ausschnitte sind Text aus
Ratsdokumenten (plan-vorverarbeitung-2026-11.md, § 4, „Daten").

Was der Auftrag **nicht** trägt, ist Absicht: keine Ausgabe des geprüften Verfahrens (außer der
Spanne, die selbst die Einheit ist, und Kontextspalten, die das Codebuch ausdrücklich nennt) und
nichts vom anderen Kodierer. Die Folge der Einheiten ist je Kodierer eine andere, fest aus Seed
und Kodierer, damit Reihenfolgeeffekte nicht bei beiden gleich wirken.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from georep.errors import MissingInputError, SchemaError
from georep.io import write_text
from georep.layout import Layout
from georep.settings import Settings
from georep.validation import CodingError
from georep.validation.codebook import Codebook, load_codebook
from georep.validation.paths import Coder, Role, ValidationPaths, validation_paths
from georep.validation.sample import ID, rank, read_sample, sample_meta

# Die Spalten, die eine Spannentabelle nach F3 tragen muss; value, norm, section und extractor
# zeigt der Auftrag nicht (sie sind Ausgabe des Verfahrens).
SPAN_COLUMNS = ("id", "start", "end", "kind")
MARK_OPEN, MARK_CLOSE = "⟦", "⟧"  # umschließen im Feld ``markiert`` die Spanne einer Einheit span
RAW_TEXT_FILE = "rohtexte.parquet"  # der Rohtextstore von F1, neben texts.parquet


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str


def _jsonl(records: Sequence[Mapping[str, Any]]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)


def load_documents(
    layout: Layout, codebook: Codebook, ids: set[str], texts: Path | None = None
) -> dict[str, Document]:
    """Titel und Text der Dokumente; die Quelle nennt ``text.source`` im Codebuch.

    ``corpus`` liest ``interim/papers.parquet`` (kleingeschrieben, ohne Zeilenumbrüche),
    ``raw`` den Rohtextstore von F1 über den Dateinamen der Hauptdatei, standardmäßig
    ``rohtexte.parquet`` neben dem Textstore, sonst ``texts`` (etwa die Messdatei aus Phase 0).
    Ein Dokument, das die Quelle nicht kennt, hat leeren Text.
    """
    if not layout.corpus.is_file():
        raise MissingInputError(f"{layout.corpus} fehlt; `georep run corpus` baut den Korpus")
    corpus = pl.read_parquet(layout.corpus, columns=["id", "name", "file_name", "text"]).filter(
        pl.col("id").is_in(sorted(ids))
    )
    if codebook.text.source == "raw":
        store = texts or layout.texts.with_name(RAW_TEXT_FILE)
        if not store.is_file():
            raise MissingInputError(
                f"Rohtextstore {store} fehlt; --texts nennt einen anderen (F1, messdaten/rohtext)"
            )
        raw = pl.read_parquet(store, columns=["name", "text"]).rename({"name": "file_name"})
        corpus = corpus.drop("text").join(raw, on="file_name", how="left")
    unknown = sorted(ids - set(corpus.get_column("id")))
    if unknown:
        raise SchemaError(
            f"{len(unknown)} Dokumente der Stichprobe fehlen im Korpus, etwa {unknown[0]!r}"
        )
    return {
        row["id"]: Document(row["id"], row["name"] or "", row["text"] or "")
        for row in corpus.iter_rows(named=True)
    }


def load_spans(path: Path, ids: set[str], kinds: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    """Die Spannen (F3) der Stichprobendokumente, je Dokument nach Anfang sortiert."""
    if not path.is_file():
        raise MissingInputError(f"Spannen {path} fehlen")
    frame = pl.read_parquet(path)
    missing = [column for column in SPAN_COLUMNS if column not in frame.columns]
    if missing:
        raise SchemaError(f"{path}: Spannen ohne Spalten {missing} (Schema von F3)")
    frame = frame.filter(pl.col("id").is_in(sorted(ids)))
    if kinds:
        frame = frame.filter(pl.col("kind").is_in(list(kinds)))
    spans: dict[str, list[dict[str, Any]]] = {}
    for row in frame.sort(["id", "start", "end"]).iter_rows(named=True):
        spans.setdefault(row["id"], []).append(row)
    return spans


def _check_span(document: Document, start: int, end: int, source: str) -> None:
    if not 0 <= start < end <= len(document.text):
        raise SchemaError(
            f"Spanne {start}..{end} liegt außerhalb des Textes von {document.id!r} "
            f"({len(document.text)} Zeichen aus {source!r}); Spannen beziehen sich auf den Text, "
            "aus dem sie gefunden wurden (text.source im Codebuch)"
        )


def excerpt(
    document: Document,
    codebook: Codebook,
    spans: Sequence[Mapping[str, Any]],
    unit_span: tuple[int, int] | None = None,
) -> tuple[dict[str, Any], int]:
    """Ein Dokument im Auftrag und die Zahl seiner Spannen, die außerhalb des Ausschnitts liegen.

    Ohne Spanne der Einheit ist der Ausschnitt der Anfang des Textes (``text.chars`` Zeichen),
    sonst ``text.window`` Zeichen vor und hinter ihr; ``markiert`` zeigt die Spanne dann im
    Ausschnitt zwischen ⟦ und ⟧. Die Offsets der Spannen sind relativ zum Ausschnitt.
    """
    text, rules = document.text, codebook.text
    if unit_span is None:
        begin, stop = 0, min(len(text), rules.chars)
    else:
        _check_span(document, *unit_span, rules.source)
        begin = max(0, unit_span[0] - rules.window)
        stop = min(len(text), unit_span[1] + rules.window)
    shown, outside = [], 0
    for span in spans:
        start, end = int(span["start"]), int(span["end"])
        _check_span(document, start, end, rules.source)
        if start >= begin and end <= stop:
            shown.append(
                {
                    "start": start - begin,
                    "end": end - begin,
                    "art": span["kind"],
                    "text": text[start:end],
                }
            )
        else:
            outside += 1
    record: dict[str, Any] = {"id": document.id}
    if rules.title:
        record["titel"] = document.title
    record |= {
        "zeichen": len(text),
        "ausschnitt_start": begin,
        "ausschnitt_ende": stop,
        "ausschnitt": text[begin:stop],
    }
    if unit_span is not None:
        start, end = unit_span
        record["spanne"] = {"start": start - begin, "end": end - begin, "text": text[start:end]}
        record["markiert"] = (
            text[begin:start] + MARK_OPEN + text[start:end] + MARK_CLOSE + text[end:stop]
        )
    record["spannen"] = shown
    return record, outside


def options(codebook: Codebook) -> list[dict[str, str]]:
    return [
        {"wert": o.value, "definition": o.definition, "beispiel": o.example}
        for o in codebook.options
    ]


def build_task(
    row: Mapping[str, Any],
    codebook: Codebook,
    documents: Mapping[str, Document],
    spans: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, Any], int]:
    """Eine Zeile des Auftrags aus einer Zeile der Stichprobe; dazu die Spannen außerhalb."""
    unit = codebook.unit
    task: dict[str, Any] = {
        "id": row[ID],
        "vorhaben": codebook.project,
        "codebuch_version": codebook.version,
        "frage": codebook.question,
    }
    if unit == "query_document":
        task["anfrage"] = row["anfrage"]
    if codebook.text.context:
        task["kontext"] = {column: row.get(column) for column in codebook.text.context}
    targets: list[tuple[str, tuple[int, int] | None]]
    if unit == "document":
        targets = [(row[ID], None)]
    elif unit == "document_pair":
        targets = [(row["id_a"], None), (row["id_b"], None)]
    elif unit == "span":
        targets = [(row["dokument"], (int(row["start"]), int(row["end"])))]
    else:
        targets = [(row["dokument"], None)]
    shown, outside = [], 0
    for doc, unit_span in targets:
        record, missed = excerpt(documents[doc], codebook, spans.get(doc, ()), unit_span)
        shown.append(record)
        outside += missed
    task["dokumente"] = shown
    task["optionen"] = options(codebook)
    task["antwort"] = None
    return task, outside


def document_ids(sample: pl.DataFrame, codebook: Codebook) -> set[str]:
    columns = {
        "document": (ID,),
        "document_pair": ("id_a", "id_b"),
        "span": ("dokument",),
        "query_document": ("dokument",),
    }[codebook.unit]
    return {str(v) for column in columns for v in sample.get_column(column).to_list()}


def brief(codebook: Codebook, who: Role) -> str:
    """Das Codebuch als Text für den Agenten, mit den Regeln der Antwortdatei."""
    lines = [
        f"# Codebuch {codebook.project}, Version {codebook.version}",
        "",
        f"Rolle: {'Schlichtung' if who == 'schlichtung' else f'Kodierer {who}'}. "
        f"Einheit: {codebook.unit}. Skala: {codebook.scale}.",
        "",
        "## Frage",
        "",
        codebook.question,
        "",
        "## Anweisungen",
        "",
        codebook.instructions.strip(),
        "",
        "## Optionen" + (" (aufsteigend)" if codebook.scale == "ordinal" else ""),
        "",
    ]
    for option in codebook.options:
        lines.append(f"- `{option.value}`: {option.definition}")
        if option.example:
            lines.append(f"  Beispiel: {option.example}")
    lines += [
        "",
        "## Antworten",
        "",
        "`auftrag.jsonl` hat je Einheit eine Zeile. `antworten.jsonl` hat dieselben Einheiten in "
        "derselben Folge; setze in jeder Zeile `label` auf genau einen der Werte oben und "
        "`begruendung` auf einen kurzen Satz (ohne längere Zitate). Ändere `id` nicht, lass keine "
        "Zeile weg und füge keine hinzu. Lies nur die Dateien in diesem Ordner.",
    ]
    if who == "schlichtung":
        lines += [
            "",
            "Jede Zeile des Auftrags ist eine Einheit, bei der zwei Kodierer verschieden "
            "geantwortet haben (`kodierung_1`, `kodierung_2`, je mit Begründung). Entscheide nach "
            "dem Codebuch, nicht nach der Mehrheit oder der Länge der Begründung; jede Option ist "
            "erlaubt, auch eine dritte.",
        ]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class TaskReport:
    folder: Path
    units: int
    empty: int  # Dokumente ohne Text im Auftrag
    outside: int  # Spannen außerhalb des Ausschnitts

    def line(self) -> str:
        notes = [
            f"{self.empty} Dokumente ohne Text" if self.empty else "",
            f"{self.outside} Spannen außerhalb der Ausschnitte" if self.outside else "",
        ]
        tail = "; ".join(n for n in notes if n)
        return f"{self.units} Einheiten -> {self.folder}" + (f" ({tail})" if tail else "")


def answers_started(path: Path) -> int:
    """Wie viele Zeilen einer Antwortdatei schon ein Label tragen; 0, wenn es sie nicht gibt."""
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return -1
            count += isinstance(record, dict) and record.get("label") is not None
    return count


def write_assignment(
    paths: ValidationPaths,
    who: Role,
    tasks: Sequence[Mapping[str, Any]],
    codebook: Codebook,
    *,
    force: bool,
) -> None:
    """Auftrag, leere Antworten und Codebuch eines Agenten schreiben; begonnene Antworten bleiben."""
    started = answers_started(paths.answers(who))
    if started and not force:
        raise CodingError(
            f"{paths.answers(who)} trägt schon Antworten ({'unlesbar' if started < 0 else started}); "
            "--force schreibt einen neuen Auftrag und leert sie"
        )
    write_text(paths.tasks(who), _jsonl(tasks))
    write_text(
        paths.answers(who),
        _jsonl([{"id": task["id"], "label": None, "begruendung": ""} for task in tasks]),
    )
    write_text(paths.brief(who), brief(codebook, who))


def task_project(
    settings: Settings,
    layout: Layout,
    project: str,
    coder: Coder,
    *,
    texts: Path | None = None,
    spans: Path | None = None,
    force: bool = False,
) -> TaskReport:
    """``georep validate tasks``: den Auftrag eines Kodierers aus Stichprobe und Text bauen."""
    paths = validation_paths(settings, project)
    codebook = load_codebook(paths.codebook, project)
    sample = read_sample(paths, codebook)
    profile = sample_meta(paths).get("profil")
    if profile != layout.profile:
        raise CodingError(
            f"die Stichprobe kommt aus dem Profil {profile!r}, der Aufruf nutzt {layout.profile!r}"
        )
    ids = document_ids(sample, codebook)
    documents = load_documents(layout, codebook, ids, texts)
    span_file = spans or (layout.root / codebook.text.spans if codebook.text.spans else None)
    found = load_spans(span_file, ids, codebook.text.span_kinds) if span_file else {}
    tasks, outside = [], 0
    for row in sample.iter_rows(named=True):
        task, missed = build_task(row, codebook, documents, found)
        tasks.append(task)
        outside += missed
    tasks.sort(key=lambda task: rank(codebook.sample.seed, f"{coder}|{task['id']}"))
    write_assignment(paths, coder, tasks, codebook, force=force)
    empty = sum(1 for doc in ids if not documents[doc].text)
    return TaskReport(paths.role(coder), len(tasks), empty, outside)
