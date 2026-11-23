"""Der Kodierauftrag je Kodierer (``georep validate tasks <vorhaben> --coder A|B``, F4).

Je Einheit der Stichprobe eine JSONL-Zeile: der Schlüssel, die Fragen des Codebuchs mit Optionen
und Bedingungen, je Dokument ein Ausschnitt aus dem Text mit seinen hervorgehobenen Spannen
(Schema von F3, ``georep.spans``) und eine leere Antwort. Daneben eine Antwortdatei, die der
Kodier-Agent füllt (je Zeile ``id``, ``codebuch_version``, je Frage ein Wert, ``begruendung``), und
das Codebuch als Text. Alles liegt unter ``validation.coding_root/<vorhaben>/<A|B>/``, nie im Repo:
die Ausschnitte sind Text aus Ratsdokumenten (plan-vorverarbeitung-2026-11.md, § 4, „Daten").

Was der Auftrag **nicht** trägt, ist Absicht: keine Ausgabe des geprüften Verfahrens. Die Spanne,
die selbst die Einheit ist, steht im Feld ``markiert`` und nicht noch einmal unter ``spannen``; die
Art (``kind``) einer Spanne zeigt der Auftrag nur mit ``text.show_kind``, und nie, wenn die
hervorgehobenen Spannen dieselbe Datei wie die Einheiten sind (Review 2026-11-23, Befund 2). Die
Folge der Einheiten ist je Kodierer eine andere, fest aus Seed und Kodierer.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from georep.errors import MissingInputError, SchemaError
from georep.io import digest, write_text
from georep.layout import Layout
from georep.settings import Settings
from georep.spans import check_spans
from georep.spans import excerpt as span_excerpt
from georep.validation import CodingError
from georep.validation.codebook import Codebook, load_codebook
from georep.validation.paths import Coder, Role, ValidationPaths, validation_paths
from georep.validation.sample import ID, population_path, rank, read_sample, sample_meta

MARK_OPEN, MARK_CLOSE = "⟦", "⟧"  # umschließen im Feld ``markiert`` die Spanne einer Einheit
RAW_TEXT_FILE = "rohtexte.parquet"  # der Rohtextstore von F1, neben texts.parquet


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str


def jsonl(records: Sequence[Mapping[str, Any]]) -> str:
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


def checked_spans(
    path: Path, documents: Mapping[str, Document], kinds: Sequence[str]
) -> pl.DataFrame:
    """Die Spannen (F3) der Stichprobendokumente, geprüft mit ``georep.spans.check_spans``.

    Geprüft wird gegen die Längen der gewählten Textquelle, dazu, dass ``value`` wörtlich der
    Text an der Stelle ist: sonst zeigen die Positionen auf einen anderen Text (Befund 3).
    """
    if not path.is_file():
        raise MissingInputError(f"Spannen {path} fehlen")
    frame = pl.read_parquet(path).filter(pl.col("id").is_in(sorted(documents)))
    check_spans(frame, {doc: len(d.text) for doc, d in documents.items()})
    if kinds:
        frame = frame.filter(pl.col("kind").is_in(list(kinds)))
    for row in frame.iter_rows(named=True):
        _check_value(documents[row["id"]], row)
    return frame


def _check_value(document: Document, span: Mapping[str, Any]) -> None:
    found = document.text[int(span["start"]) : int(span["end"])]
    if span.get("value") != found:
        raise SchemaError(
            f"Spanne {span['start']}..{span['end']} in {document.id!r}: dort steht {found!r}, die "
            f"Spanne sagt {span.get('value')!r}; sie kommt aus einem anderen Text (extractor "
            f"{span.get('extractor')!r})"
        )


def _window(document: Document, start: int, end: int, context: int) -> tuple[int, int]:
    if not 0 <= start < end <= len(document.text):
        raise SchemaError(
            f"Spanne {start}..{end} liegt außerhalb des Textes von {document.id!r} "
            f"({len(document.text)} Zeichen); Spannen beziehen sich auf den Text, aus dem sie "
            "gefunden wurden (text.source im Codebuch)"
        )
    before, _, after = span_excerpt(document.text, start, end, context)
    return start - len(before), end + len(after)


def show_document(
    document: Document,
    codebook: Codebook,
    spans: Sequence[Mapping[str, Any]],
    unit_span: tuple[int, int] | None = None,
) -> tuple[dict[str, Any], int]:
    """Ein Dokument im Auftrag und die Zahl seiner Spannen, die außerhalb des Ausschnitts liegen.

    Ohne Spanne der Einheit ist der Ausschnitt der Anfang des Textes (``text.chars`` Zeichen),
    sonst ``text.window`` Zeichen vor und hinter ihr (``georep.spans.excerpt``); ``markiert``
    zeigt die Spanne dann zwischen ⟦ und ⟧, und unter ``spannen`` steht sie nicht noch einmal.
    """
    text, rules = document.text, codebook.text
    if unit_span is None:
        begin, stop = 0, min(len(text), rules.chars)
    else:
        begin, stop = _window(document, *unit_span, rules.window)
    shown, outside = [], 0
    for span in spans:
        start, end = int(span["start"]), int(span["end"])
        if (start, end) == unit_span:
            continue
        if start >= begin and end <= stop:
            item: dict[str, Any] = {"start": start - begin, "end": end - begin}
            if rules.show_kind:
                item["art"] = span["kind"]
            shown.append(item | {"text": text[start:end]})
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


def questions(codebook: Codebook) -> list[dict[str, Any]]:
    """Die Fragen, wie der Auftrag sie zeigt: ohne ``positive`` und ``ignore`` (Auswertung)."""
    shown = []
    for q in codebook.questions:
        item: dict[str, Any] = {"id": q.id, "frage": q.question, "skala": q.scale}
        if q.instructions:
            item["anleitung"] = q.instructions
        if q.options:
            item["optionen"] = [
                {"wert": o.value}
                | ({"name": o.name} if o.name else {})
                | {"definition": o.definition, "beispiel": o.example}
                for o in q.options
            ]
        if q.only_if is not None:
            item["nur_wenn"] = {"frage": q.only_if.question, "antworten": q.only_if.values}
        shown.append(item)
    return shown


def _int_or_none(value: object) -> int | None:
    return None if value is None else int(str(value))


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
    }
    if unit == "query_document":
        task["anfrage"] = row["anfrage"]
    if codebook.text.context:
        task["kontext"] = {column: row.get(column) for column in codebook.text.context}
    targets: list[tuple[str, tuple[int, int] | None]]
    if unit in ("document", "marking"):
        targets = [(row.get("dokument") or row[ID], None)]
    elif unit == "document_pair":
        targets = [(row["id_a"], None), (row["id_b"], None)]
    elif unit == "pair_with_span":
        start, end = _int_or_none(row.get("start")), _int_or_none(row.get("end"))
        found = (start, end) if start is not None and end is not None else None
        targets = [(row["id_a"], None), (row["id_b"], found)]
    elif unit == "span":
        targets = [(row["dokument"], (int(row["start"]), int(row["end"])))]
    else:
        targets = [(row["dokument"], None)]
    shown, outside = [], 0
    for doc, unit_span in targets:
        record, missed = show_document(documents[doc], codebook, spans.get(doc, ()), unit_span)
        shown.append(record)
        outside += missed
    task["dokumente"] = shown
    task["fragen"] = questions(codebook)
    task["antwort"] = None
    return task, outside


def document_ids(sample: pl.DataFrame, codebook: Codebook) -> set[str]:
    columns = {
        "document": ("dokument",) if "dokument" in sample.columns else (ID,),
        "marking": ("dokument",) if "dokument" in sample.columns else (ID,),
        "document_pair": ("id_a", "id_b"),
        "pair_with_span": ("id_a", "id_b"),
        "span": ("dokument",),
        "query_document": ("dokument",),
    }[codebook.unit]
    return {str(v) for column in columns for v in sample.get_column(column).to_list()}


def answer_template(task: Mapping[str, Any], codebook: Codebook) -> dict[str, Any]:
    """Eine leere Antwortzeile: je Frage ``null``, dazu Codebuch-Version und Begründung."""
    return {
        "id": task["id"],
        "codebuch_version": codebook.version,
        **dict.fromkeys(codebook.question_ids),
        "begruendung": "",
    }


def brief(codebook: Codebook, who: Role) -> str:
    """Das Codebuch als Text für den Agenten, mit den Regeln der Antwortdatei."""
    lines = [
        f"# Codebuch {codebook.project}, Version {codebook.version}",
        "",
        f"Rolle: {'Schlichtung' if who == 'schlichtung' else f'Kodierer {who}'}. "
        f"Einheit: {codebook.unit}.",
        "",
        "## Anweisungen",
        "",
        codebook.instructions.strip(),
        "",
    ]
    for q in codebook.questions:
        lines += [f"## Frage `{q.id}` ({q.scale})", "", q.question, ""]
        if q.only_if is not None:
            values = ", ".join(f"`{v}`" for v in q.only_if.values)
            lines += [f"Nur, wenn `{q.only_if.question}` eine von {values} ist; sonst `null`.", ""]
        if q.instructions:
            lines += [q.instructions.strip(), ""]
        for option in q.options:
            name = f" ({option.name})" if option.name else ""
            lines.append(f"- `{option.value}`{name}: {option.definition}".rstrip(": "))
            if option.example:
                lines.append(f"  Beispiel: {option.example}")
        if q.options:
            lines.append("")
        if q.scale == "interval":
            lines += ["Antwort: eine Zahl, oder `null`, wenn es nichts gibt.", ""]
        if q.scale == "open":
            lines += [
                "Antwort: ein JSON-Wert wie beschrieben, oder `null`, wenn es nichts gibt.",
                "",
            ]
    lines += [
        "## Antworten",
        "",
        "`auftrag.jsonl` hat je Einheit eine Zeile. `antworten.jsonl` hat dieselben Einheiten in "
        "derselben Folge; setze in jeder Zeile je Frage den Wert (bei Optionen genau einer der "
        "Werte oben; eine Frage, die nach ihrer Bedingung nicht gestellt ist, bleibt `null`) und "
        "`begruendung` auf einen kurzen Satz (ohne längere Zitate). Ändere `id` und "
        "`codebuch_version` nicht, lass keine Zeile weg und füge keine hinzu. Lies nur die "
        "Dateien in diesem Ordner.",
    ]
    if who == "schlichtung":
        lines += [
            "",
            "Jede Zeile des Auftrags ist eine Einheit, bei der zwei Kodierer bei mindestens einer "
            "Frage verschieden geantwortet haben (`strittig`; `kodierung_1`, `kodierung_2`, je mit "
            "Begründung). Beantworte die strittigen Fragen nach dem Codebuch, nicht nach der "
            "Mehrheit oder der Länge der Begründung; jede Option ist erlaubt, auch eine dritte. "
            "Die übrigen Fragen bleiben `null`.",
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
    """Wie viele Zeilen einer Antwortdatei schon einen Wert tragen; 0 ohne Datei, -1 unlesbar."""
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return -1
            if not isinstance(record, dict):
                return -1
            values = {
                k: v
                for k, v in record.items()
                if k not in ("id", "codebuch_version", "begruendung")
            }
            count += any(v is not None for v in values.values())
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
    write_text(paths.tasks(who), jsonl(tasks))
    write_text(paths.answers(who), jsonl([answer_template(task, codebook) for task in tasks]))
    write_text(paths.brief(who), brief(codebook, who))


def unit_spans(
    layout: Layout,
    paths: ValidationPaths,
    codebook: Codebook,
    population: Path | None,
    documents: Mapping[str, Document],
) -> None:
    """Die Spannen der Einheiten ``span`` gegen ihren Text prüfen (Befund 3).

    ``value`` und ``extractor`` stehen nicht in ``stichprobe.csv`` (``value`` ist Ratstext und
    die Stichprobe liegt im Repo); sie kommen aus der Grundgesamtheit, die dieselbe sein muss wie
    beim Ziehen (Prüfsumme aus ``stichprobe.json``). Geprüft wird mit ``check_spans`` und ``value``.
    """
    source = population_path(layout, codebook, population)
    if not source.is_file():
        raise MissingInputError(f"Grundgesamtheit {source} fehlt; --population nennt sie")
    expected = sample_meta(paths).get("grundgesamtheit_sha256")
    if expected and digest(source) != expected:
        raise CodingError(
            f"Grundgesamtheit {source} ist nicht die der Stichprobe (Prüfsumme in stichprobe.json)"
        )
    if codebook.text.show_kind and codebook.text.spans == codebook.sample.population:
        raise SchemaError(
            "text.spans ist die Grundgesamtheit der Einheiten: mit text.show_kind sähen die "
            "Kodierer die Art, die das Verfahren vergeben hat (Ausgabe des Verfahrens)"
        )
    checked_spans(source, documents, ())


def task_project(
    settings: Settings,
    layout: Layout,
    project: str,
    coder: Coder,
    *,
    texts: Path | None = None,
    spans: Path | None = None,
    population: Path | None = None,
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
    if codebook.unit == "span":
        unit_spans(layout, paths, codebook, population, documents)
    span_file = spans or (layout.root / codebook.text.spans if codebook.text.spans else None)
    found: dict[str, list[dict[str, Any]]] = {}
    if span_file is not None:
        for row in checked_spans(span_file, documents, codebook.text.span_kinds).iter_rows(
            named=True
        ):
            found.setdefault(row["id"], []).append(row)
    tasks, outside = [], 0
    for row in sample.iter_rows(named=True):
        task, missed = build_task(row, codebook, documents, found)
        tasks.append(task)
        outside += missed
    tasks.sort(key=lambda task: rank(codebook.sample.seed, f"{coder}|{task['id']}"))
    write_assignment(paths, coder, tasks, codebook, force=force)
    empty = sum(1 for doc in ids if not documents[doc].text)
    return TaskReport(paths.role(coder), len(tasks), empty, outside)
