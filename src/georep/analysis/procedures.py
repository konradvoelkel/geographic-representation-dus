"""Kanten zwischen Drucksachen, Vorgänge als Wald, Antworten auf Anfragen (Vorhaben 14).

Aus den Fundstellen von ``prep.references`` entstehen hier drei Tabellen, gerechnet wie im
Messskript ``docs/plans/14-vorgaenge-messung.py`` (Abschnitte 3 bis 6, 11 und 13):

* **Kanten.** Eine Kante ist ein Paar (B nennt A), B ≠ A, einmal je Paar, mit den Feldern, in denen
  die Nummer steht (``titel``, ``text``, ``anlage``) und dem Nachtrag über die Nummer (``nummer``:
  ``X/1`` nennt ``X``, auch ohne Fundstelle). Ihr Typ kommt aus den Rollen beider Drucksachen
  (``prep.references.edge_type``). **Stark** ist sie nach der Rückfallregel (Messdokument § 5.1)
  nur aus Titel, Anlagenname, Nachtragsnummer oder wenn B ein Sammelbericht ist; eine reine
  Textkante bleibt schwach in den Daten und zählt nicht für Vorgang und Antwort. ``quelle`` nennt
  die stärkste Fundstelle in dieser Folge: Titel, Nummer, Anlage, Sammelbericht, sonst Text.
* **Vorgänge** sind ein Wald, keine Zusammenhangskomponenten (§ 3.5): jede Drucksache hängt am
  ältesten Dokument, das sie über eine starke typisierte Kante nennt (``TREE_TYPES``, nicht
  rückwärts in der Zeit); die Wurzel ist der Vorgang. So verschmelzen zwei Vorgänge nicht, nur
  weil ein drittes Dokument beide nennt.
* **Antworten.** Eine Anfrage hat eine Antwort, wenn eine ihrer Anlagen danach heißt
  (``procedures.answer_attachment``) oder eine Informationsvorlage sie über eine starke Kante nennt
  (Typ ``antwort``). Das Datum der Antwort ist das früheste gültige; ein Anlagendatum, das ein
  Umstellungstag ist (``attachment_dates_invalid``), zählt als Antwort ohne Datum (§ 3.6).
  ``praxis_gremium`` ist der Anteil der Anfragen desselben Gremiums mit Antwort in dieser Periode:
  ob eine Antwort als Anlage kommt, ist Praxis des Gremiums (§ 3.8), und „keine Antwort im
  Datensatz" heißt darum nicht „unbeantwortet".

Alle drei rechnen über die **ganze Stadt**, die das Profil kennt: der eigene Korpus und die
Nachbarperioden aus ihren Paketen (``procedures.related``). Ein Vorgang endet nicht an der Wahl;
2 599 Kanten der Messung überqueren eine Periodengrenze.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import deal
import polars as pl

from georep.contracts import has_columns, one_row_per_document, sorted_unique
from georep.prep.references import (
    ATTACHMENT,
    ATTACHMENT_SEPARATOR,
    EDGE_TYPES,
    NUMBER,
    QUESTION,
    SUPPLEMENT,
    TEXT,
    TITLE,
    TREE_TYPES,
    Reference,
    ReferenceRules,
    edge_type,
    find_hits,
    has_amendment_marker,
    is_answer_attachment,
    is_collective,
    known_codes,
    parse_reference,
    role_of,
)
from georep.spans import SPAN_SCHEMA, sort_spans

# Die Dokumente, über die gerechnet wird: der eigene Korpus (``periode`` leer) und die
# Nachbarperioden (``periode`` ist ihr Profil). ``text`` ist der Text des Textstores; eine
# Nachbardrucksache trägt ihn nur, wo er für eine starke Kante zählt (``strong_candidates``).
DOCUMENT_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "periode": pl.String(),
    "reference": pl.String(),
    "name": pl.String(),
    "paper_type": pl.String(),
    "date": pl.Date(),
    "text": pl.String(),
    "anlagen": pl.List(pl.String()),
}
OWN = ""  # ``periode`` des eigenen Korpus
SPAN_KIND = "drucksache"
# Die Quellen einer Kante, stärkste zuerst; ``text`` heißt schwach (Rückfallregel).
SOURCES = ("titel", "nummer", "anlage", "sammelbericht", "text")
COLLECTIVE = "sammelbericht"
EDGE_SCHEMA: dict[str, pl.DataType] = {
    "von": pl.String(),
    "nach": pl.String(),
    "typ": pl.String(),
    "felder": pl.List(pl.String()),
    "stark": pl.Boolean(),
    "quelle": pl.String(),
    "tage": pl.Int32(),
    "nach_periode": pl.String(),
}
ROOT, ALONE = "wurzel", "ohne"  # Rollen im Vorgang neben den Kantentypen
FOREST_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "vorgang": pl.String(),
    "rolle": pl.String(),
    "tiefe": pl.Int16(),
    "groesse": pl.Int32(),
}
ANSWER_SOURCES = ("anlage", "drucksache", "beide", "keine")
ANSWER_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "quelle": pl.String(),
    "antwort_datum": pl.Date(),
    "tage": pl.Int32(),
    "antwort_id": pl.String(),
    "alter_am_abruf": pl.Int32(),
    "gremium": pl.String(),
    "praxis_gremium": pl.Float64(),
}
# Das Anlagenpaket (``georep pack --attachments``): eine Zeile je Drucksache, die der Abruf kannte,
# mit ihren Anlagen in der Folge des Servers; eine Drucksache ohne Zeile ist unbekannt, eine mit
# leerer Liste hat keine Anlage.
ATTACHMENT_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "abgerufen": pl.Date(),
    "anlagen": pl.List(pl.Struct({"name": pl.String(), "datum": pl.Date()})),
}


@dataclass(frozen=True)
class Directory:
    """Das Nummernverzeichnis einer Stadt: Schlüssel -> IDs, die Nummer je ID und die Kürzel."""

    ids: Mapping[str, tuple[str, ...]]
    references: Mapping[str, Reference]
    codes: frozenset[str]

    def target(self, reference: Reference) -> str | None:
        """Die eine Drucksache hinter einer Nummer; ein Nachtrag ohne eigene über seine Grundnummer.

        Zwei Dokumente mit derselben Normalform (13 in Düsseldorf) machen die Nummer mehrdeutig;
        ein Verweis darauf wird verworfen (§ 3.1).
        """
        found = self.ids.get(reference.key)
        if not found and reference.is_supplement:
            found = self.ids.get(reference.base)
        return found[0] if found and len(found) == 1 else None


def build_directory(documents: pl.DataFrame, rules: ReferenceRules) -> Directory:
    """Das Verzeichnis aus ``id`` und ``reference`` aller Drucksachen der Stadt."""
    ids: dict[str, list[str]] = {}
    references: dict[str, Reference] = {}
    for doc_id, number in documents.select("id", "reference").iter_rows():
        parsed = parse_reference(number, rules)
        if parsed is None:
            continue
        references[doc_id] = parsed
        ids.setdefault(parsed.key, []).append(doc_id)
    return Directory(
        {key: tuple(sorted(found)) for key, found in ids.items()},
        references,
        known_codes(references.values()),
    )


def supplement_pairs(directory: Directory) -> list[tuple[str, str]]:
    """(Nachtrag, Original) über die Nummer: ``X/k`` nennt ``X``, beide eindeutig (§ 3.3)."""
    pairs = []
    for doc_id, ref in directory.references.items():
        if not ref.is_supplement:
            continue
        own, base = directory.ids.get(ref.key, ()), directory.ids.get(ref.base, ())
        if len(own) == 1 and len(base) == 1:
            pairs.append((doc_id, base[0]))
    return sorted(pairs)


@dataclass(frozen=True)
class Scan:
    """Die Fundstellen eines Durchgangs: aufgelöst je Feld und, für Texte, als Spannen."""

    occurrences: pl.DataFrame  # von, nach, feld, aend
    spans: pl.DataFrame  # Schema von georep.spans


OCCURRENCE_SCHEMA: dict[str, pl.DataType] = {
    "von": pl.String(),
    "nach": pl.String(),
    "feld": pl.String(),
    "aend": pl.Boolean(),
}


@deal.pre(lambda documents, *_args, **_kw: has_columns(documents, "id", "name", "text", "anlagen"))
def scan(
    documents: pl.DataFrame,
    directory: Directory,
    rules: ReferenceRules,
    extractors: Mapping[str, str] | None = None,
) -> Scan:
    """Alle Fundstellen in Titel, Text und Anlagennamen; Spannen für die Texte in ``extractors``.

    Eine Fundstelle wird zur Kante, wenn ihre Nummer genau eine andere Drucksache trifft und
    nicht die eigene Nummer ist. Spannen gibt es für jede Nummer im Text, auch ohne Ziel (eine
    nicht öffentliche Drucksache, ein Tippfehler); ``extractors`` nennt je ID den Text, auf den sie
    zeigen, und wer darin fehlt, bekommt keine.
    """
    wanted = extractors or {}
    occurrences: list[tuple[str, str, str, bool]] = []
    spans: list[tuple[str, int, int, str, str, str, str, str]] = []
    for doc_id, name, text, attachments in documents.select(
        "id", "name", "text", "anlagen"
    ).iter_rows():
        own = directory.references.get(doc_id)
        fields = (
            (TITLE, (name or "").lower()),
            (TEXT, text or ""),
            (ATTACHMENT, ATTACHMENT_SEPARATOR.join(attachments or []).lower()),
        )
        for field, value in fields:
            if not value:
                continue
            for hit in find_hits(value, rules, directory.codes):
                if field == TEXT and doc_id in wanted:
                    spans.append(
                        (
                            doc_id,
                            hit.start,
                            hit.end,
                            SPAN_KIND,
                            value[hit.start : hit.end],
                            hit.reference.key,
                            "",
                            wanted[doc_id],
                        )
                    )
                target = directory.target(hit.reference)
                if target is None or target == doc_id:
                    continue
                if own is not None and hit.reference.key == own.key:
                    continue
                aend = has_amendment_marker(field, value, hit.start, rules)
                occurrences.append((doc_id, target, field, aend))
    return Scan(
        pl.DataFrame(occurrences, schema=OCCURRENCE_SCHEMA, orient="row"),
        sort_spans(pl.DataFrame(spans, schema=SPAN_SCHEMA, orient="row")),
    )


# Rohtext je Dokument: Text, Stelle im Rohtext je Zeichen des geplätteten Texts
# (``prep.raw_texts.flatten_with_offsets``) und der Extraktorname des Rohtextstores.
RawBridge = tuple[str, Sequence[int], str]


def _bridged(spans: pl.DataFrame, raw: Mapping[str, RawBridge]) -> bool:
    return all(
        0 <= start < end <= len(raw[doc_id][0])
        for doc_id, start, end in spans.select("id", "start", "end").iter_rows()
        if doc_id in raw
    )


@deal.post(lambda result: result.schema == pl.Schema(SPAN_SCHEMA), message="Schema von F3")
@deal.ensure(
    lambda spans, raw, result: result.height == spans.height and _bridged(result, raw),
    message="jede Spanne bleibt, und jede auf dem Rohtext liegt in ihm",
)
def onto_raw(spans: pl.DataFrame, raw: Mapping[str, RawBridge]) -> pl.DataFrame:
    """Die Spannen des Textstores auf den Rohtext legen, wo ein Dokument ihn hat (Nachzug F7).

    ``raw`` nennt je ID den Rohtext, dessen Plättung genau der Text des Textstores ist, mit der
    Stelle jedes Zeichens im Rohtext (Punkt 74). Eine Spanne ``[i, j)`` ist dort
    ``[offsets[i], offsets[j - 1] + 1)``; ``value`` ist der Rohtext an dieser Stelle, wörtlich
    (groß geschrieben, mit einem Zeilenumbruch, über den die Nummer läuft), ``extractor`` der des
    Rohtexts mit dem Verfahren. Eine ID ohne Rohtext behält ihre Spannen auf dem Textstore; welche
    Art eine Zeile ist, sagt ihr ``extractor`` (F3).
    """
    method = {
        doc_id: extractor.rsplit("/", 1)[-1]
        for doc_id, extractor in spans.select("id", "extractor").iter_rows()
    }
    rows = []
    for doc_id, start, end, kind, value, norm, section, extractor in spans.iter_rows():
        bridge = raw.get(doc_id)
        if bridge is None:
            rows.append((doc_id, start, end, kind, value, norm, section, extractor))
            continue
        text, offsets, raw_extractor = bridge
        begin, stop = offsets[start], offsets[end - 1] + 1
        rows.append(
            (
                doc_id,
                begin,
                stop,
                kind,
                text[begin:stop],
                norm,
                section,
                f"{raw_extractor}/{method[doc_id]}",
            )
        )
    return sort_spans(pl.DataFrame(rows, schema=SPAN_SCHEMA, orient="row"))


def document_roles(documents: pl.DataFrame, rules: ReferenceRules) -> pl.DataFrame:
    """``id``, ``periode``, ``date``, ``rolle`` und ``sammelbericht`` je Drucksache der Stadt."""
    rows = [
        (doc_id, period, day, role, is_collective(name, role, rules))
        for doc_id, period, day, paper_type, name in documents.select(
            "id", "periode", "date", "paper_type", "name"
        ).iter_rows()
        for role in (role_of(paper_type, name, rules),)
    ]
    return pl.DataFrame(
        rows,
        schema={
            "id": pl.String(),
            "periode": pl.String(),
            "date": pl.Date(),
            "rolle": pl.String(),
            "sammelbericht": pl.Boolean(),
        },
        orient="row",
    ).sort("id")


def _edge_columns_hold(result: pl.DataFrame) -> bool:
    return result.schema == pl.Schema(EDGE_SCHEMA)


def _pairs_unique_and_sorted(result: pl.DataFrame) -> bool:
    keys = result.select("von", "nach").rows()
    return keys == sorted(set(keys))


def _strong_matches_source(result: pl.DataFrame) -> bool:
    """``stark`` genau bei einer Quelle außer Text, ein Nachtrag ist immer stark."""
    return bool(
        (result.get_column("stark") == (result.get_column("quelle") != "text")).all()
        and result.filter(pl.col("typ") == SUPPLEMENT).get_column("stark").all()
    )


@deal.post(_edge_columns_hold, message="Spalten und Typen von vorgang_kanten")
@deal.post(_pairs_unique_and_sorted, message="eine Zeile je (von, nach), sortiert")
@deal.post(lambda result: bool((result.get_column("von") != result.get_column("nach")).all()))
@deal.post(lambda result: set(result.get_column("typ")) <= set(EDGE_TYPES))
@deal.post(_strong_matches_source, message="stark genau bei quelle != text; nachtrag ist stark")
def assemble_edges(
    occurrences: pl.DataFrame,
    supplements: Sequence[tuple[str, str]],
    roles: pl.DataFrame,
) -> pl.DataFrame:
    """Je Paar eine Kante mit Feldern, Typ .2, Stärke nach der Rückfallregel und Abstand in Tagen.

    ``roles`` ist ``document_roles`` über alle Drucksachen der Stadt; jedes Ende einer Kante steht
    darin (die Fundstellen zeigen nur auf das Verzeichnis derselben Dokumente).
    """
    numbered = pl.DataFrame(
        [(von, nach, NUMBER, False) for von, nach in supplements],
        schema=OCCURRENCE_SCHEMA,
        orient="row",
    )
    grouped = (
        pl.concat([occurrences, numbered])
        .group_by("von", "nach")
        .agg(pl.col("feld").unique().sort().alias("felder"), pl.col("aend").any())
    )
    citing = roles.select(
        pl.col("id").alias("von"),
        pl.col("rolle").alias("von_rolle"),
        pl.col("date").alias("von_datum"),
        pl.col("sammelbericht"),
    )
    cited = roles.select(
        pl.col("id").alias("nach"),
        pl.col("rolle").alias("nach_rolle"),
        pl.col("date").alias("nach_datum"),
        pl.col("periode").alias("nach_periode"),
    )
    joined = (
        grouped.join(citing, on="von", how="inner")
        .join(cited, on="nach", how="inner")
        .sort("von", "nach")
    )
    types = [
        SUPPLEMENT if NUMBER in fields else edge_type(von_role, nach_role, aend, collective)
        for fields, von_role, nach_role, aend, collective in joined.select(
            "felder", "von_rolle", "nach_rolle", "aend", "sammelbericht"
        ).iter_rows()
    ]
    has = pl.col("felder").list.contains
    source = (
        pl.when(has(TITLE))
        .then(pl.lit(TITLE))
        .when(has(NUMBER))
        .then(pl.lit(NUMBER))
        .when(has(ATTACHMENT))
        .then(pl.lit(ATTACHMENT))
        .when(pl.col("sammelbericht"))
        .then(pl.lit(COLLECTIVE))
        .otherwise(pl.lit(TEXT))
    )
    return joined.with_columns(
        pl.Series("typ", types, dtype=pl.String),
        source.alias("quelle"),
        (pl.col("von_datum") - pl.col("nach_datum")).dt.total_days().cast(pl.Int32).alias("tage"),
    ).select(
        "von",
        "nach",
        "typ",
        "felder",
        (pl.col("quelle") != TEXT).alias("stark"),
        "quelle",
        "tage",
        "nach_periode",
    )


def strong_candidates(
    documents: pl.DataFrame, directory: Directory, rules: ReferenceRules
) -> set[str]:
    """Die Drucksachen, die eine starke Kante haben können: Fundstelle in Titel oder Anlage,
    Nachtrag über die Nummer oder Sammelbericht.

    Für sie zählt der Text mit (Felder der Kante, Änderungszeichen); jede andere hat nach der
    Rückfallregel nur schwache Kanten. So liest ein Profil von seinen Nachbarperioden nur die
    Texte, die eine starke Kante ändern können, statt alle.
    """
    without_text = documents.with_columns(pl.lit("").alias("text"))
    found = set(scan(without_text, directory, rules).occurrences.get_column("von").to_list())
    found |= {von for von, _ in supplement_pairs(directory)}
    roles = document_roles(documents, rules)
    found |= set(roles.filter(pl.col("sammelbericht")).get_column("id").to_list())
    return found & set(documents.get_column("id").to_list())


def _forest_columns_hold(result: pl.DataFrame) -> bool:
    return result.schema == pl.Schema(FOREST_SCHEMA)


def _roots_point_to_themselves(result: pl.DataFrame) -> bool:
    """``tiefe`` 0 genau dort, wo ``vorgang`` die eigene ID ist; ``groesse`` mindestens 1."""
    root = result.get_column("vorgang") == result.get_column("id")
    return bool(
        (root == (result.get_column("tiefe") == 0)).all()
        and (result.get_column("groesse") >= 1).all()
        and ((result.get_column("rolle") == ALONE) == (result.get_column("groesse") == 1)).all()
    )


class CycleError(ValueError):
    """Die Baumregel hat einen Kreis gefunden: dann wäre ein Vorgang keine Wurzel."""


def parents(edges: pl.DataFrame, roles: pl.DataFrame) -> dict[str, tuple[str, str]]:
    """Je Drucksache ihr Vorgänger im Vorgang und der Typ der Kante dorthin.

    Der Vorgänger ist das älteste Dokument, das sie über eine starke typisierte Kante nennt
    (``TREE_TYPES``), nie ein jüngeres; bei gleichem Datum die kleinere ID. Ein Dokument vom selben
    Tag ist nur Vorgänger, wenn seine ID kleiner ist: dann fällt jede Kette in (Datum, ID) streng,
    und kein Kreis ist möglich. Das Messskript ließ jede Kante vom selben Tag zu; auf den Daten
    vom 2026-11-23 zeigt keiner der sieben Vorgänger vom selben Tag auf eine größere ID, die Zahlen
    bleiben also dieselben.
    """
    cited = roles.select(pl.col("id").alias("nach"), pl.col("date").alias("nach_datum"))
    earlier = (pl.col("tage") > 0) | ((pl.col("tage") == 0) & (pl.col("nach") < pl.col("von")))
    tree = (
        edges.filter(pl.col("stark") & pl.col("typ").is_in(TREE_TYPES) & earlier)
        .join(cited, on="nach", how="inner")
        .sort("von", "nach_datum", "nach")
        .unique("von", keep="first", maintain_order=True)
    )
    return {von: (nach, typ) for von, nach, typ in tree.select("von", "nach", "typ").iter_rows()}


@deal.post(_forest_columns_hold, message="Spalten und Typen von dokumente_vorgang")
@deal.post(lambda result: sorted_unique(result, "id"), message="eine Zeile je ID, sortiert")
@deal.post(_roots_point_to_themselves, message="Wurzel genau bei tiefe 0, ohne genau bei groesse 1")
@deal.ensure(
    lambda parent, members, rows, result: one_row_per_document(result, rows),
    message="genau eine Zeile je ID in rows (Vertrag der dokumente_<attribut>, Review K2)",
)
def forest(
    parent: Mapping[str, tuple[str, str]], members: Iterable[str], rows: Sequence[str]
) -> pl.DataFrame:
    """Je ID in ``rows`` ihr Vorgang (die Wurzel), ihre Rolle, Tiefe und die Größe des Vorgangs.

    ``members`` sind alle Drucksachen der Stadt, die das Profil kennt: die Größe zählt auch die
    Mitglieder in den Nachbarperioden. Ein Kreis ist ein ``CycleError`` (``parents`` schließt ihn
    aus; der Fehler hält es fest).
    """
    root: dict[str, str] = {}
    depth: dict[str, int] = {}

    def climb(start: str) -> None:
        path: list[str] = []
        node = start
        seen: set[str] = set()
        while node not in root and node in parent:
            if node in seen:
                raise CycleError(f"Kreis im Vorgang über {node}")
            seen.add(node)
            path.append(node)
            node = parent[node][0]
        if node not in root:
            root[node], depth[node] = node, 0
        for step, item in enumerate(reversed(path), start=1):
            root[item], depth[item] = root[node], depth[node] + step

    every = sorted(set(members) | set(rows))
    for item in every:
        climb(item)
    size = Counter(root[item] for item in every)
    out = []
    for item in sorted(set(rows)):
        top = root[item]
        if item in parent:
            role = parent[item][1]
        else:
            role = ROOT if size[top] > 1 else ALONE
        out.append((item, top, role, depth[item], size[top]))
    return pl.DataFrame(out, schema=FOREST_SCHEMA, orient="row")


def _answers_hold(result: pl.DataFrame) -> bool:
    none = result.get_column("quelle") == "keine"
    empty = result.get_column("antwort_datum").is_null() & result.get_column("antwort_id").is_null()
    days = result.get_column("tage")
    return bool(
        set(result.get_column("quelle")) <= set(ANSWER_SOURCES)
        and (~none | empty).all()
        and (days.is_null() | (days >= 0)).all()
        and result.schema == pl.Schema(ANSWER_SCHEMA)
    )


@deal.post(lambda result: sorted_unique(result, "id"), message="eine Zeile je Anfrage, sortiert")
@deal.post(
    _answers_hold, message="quelle aus der Liste, keine ohne Datum und ID, tage >= 0 oder leer"
)
def answer_times(
    questions: pl.DataFrame,
    attachments: pl.DataFrame,
    edges: pl.DataFrame,
    roles: pl.DataFrame,
    rules: ReferenceRules,
    invalid_dates: Iterable[dt.date] = (),
) -> pl.DataFrame:
    """Je Anfrage ihre Antwort im Ratsinformationssystem: Quelle, Datum, Tage, Gremienpraxis.

    ``questions`` trägt ``id``, ``date`` und ``gremium`` der eigenen Anfragen, ``attachments`` das
    Anlagenpaket (``ATTACHMENT_SCHEMA``), ``edges`` die Kanten der Stadt, ``roles`` die Daten ihrer
    Dokumente. Eine Antwort vor ihrer Anfrage behält Datum und Quelle, aber keine Tage (§ 3.7).
    """
    invalid = set(invalid_dates)
    by_attachment: dict[str, tuple[bool, dt.date | None]] = {}
    fetched: dict[str, dt.date | None] = {}
    for doc_id, day, files in attachments.select("id", "abgerufen", "anlagen").iter_rows():
        fetched[doc_id] = day
        answers = [f for f in files or [] if is_answer_attachment(f["name"], rules)]
        dates = [
            f["datum"] for f in answers if f["datum"] is not None and f["datum"] not in invalid
        ]
        by_attachment[doc_id] = (bool(answers), min(dates) if dates else None)
    dated = roles.select(pl.col("id").alias("von"), pl.col("date").alias("von_datum"))
    papers = (
        edges.filter(pl.col("stark") & (pl.col("typ") == "antwort") & (pl.col("tage") >= 0))
        .join(dated, on="von", how="inner")
        .sort("nach", "von_datum", "von")
        .unique("nach", keep="first", maintain_order=True)
    )
    by_paper = {
        nach: (von, day) for nach, von, day in papers.select("nach", "von", "von_datum").iter_rows()
    }
    rows = []
    for doc_id, day, body in questions.select("id", "date", "gremium").sort("id").iter_rows():
        attached, attached_on = by_attachment.get(doc_id, (False, None))
        paper_id, paper_on = by_paper.get(doc_id, (None, None))
        source = (
            "beide"
            if attached and paper_id
            else "anlage"
            if attached
            else "drucksache"
            if paper_id
            else "keine"
        )
        candidates = [d for d in (attached_on, paper_on) if d is not None]
        answered_on = min(candidates) if candidates else None
        days = (answered_on - day).days if answered_on is not None and day is not None else None
        seen_on = fetched.get(doc_id)
        age = (seen_on - day).days if seen_on is not None and day is not None else None
        rows.append(
            (
                doc_id,
                source,
                answered_on,
                days if days is not None and days >= 0 else None,
                paper_id,
                age,
                body,
            )
        )
    frame = pl.DataFrame(
        rows,
        schema={k: v for k, v in ANSWER_SCHEMA.items() if k != "praxis_gremium"},
        orient="row",
    )
    practice = frame.group_by("gremium").agg(
        (pl.col("quelle") != "keine").mean().alias("praxis_gremium")
    )
    return (
        frame.join(practice, on="gremium", how="left", nulls_equal=True)
        .sort("id")
        .select(list(ANSWER_SCHEMA))
    )


def questions_of(roles: pl.DataFrame) -> list[str]:
    """Die eigenen Anfragen: Rolle ``anfrage`` im eigenen Korpus."""
    return (
        roles.filter((pl.col("periode") == OWN) & (pl.col("rolle") == QUESTION))
        .get_column("id")
        .to_list()
    )
