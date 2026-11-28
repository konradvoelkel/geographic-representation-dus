"""Beitrag von Vorhaben 16: Stelle je Treffer, Hausnummern, Nebenregel C (Ortsbezug).

Ein **früher** Schritt (``early_steps``, hinter ``sections`` von Vorhaben 11 und vor ``weights``,
Punkt 74): die Stelle eines Treffers kommt aus den Abschnitten, und ``weights`` rechnet aus ihr die
Gewichtungen ``ortsbezug`` und ``stelle``. ``places`` liest Korpus, Rohtext (Fundament F1), die
Abschnitte, Wörterbuch, Index, die Straßen je Wahlbezirk und, wo das Profil Hausnummern nachschlägt,
das Adresspaket (``prep.addresses``); er schreibt

* ``processed/treffer_stellen.parquet``: je Vorkommen eines Begriffs eine Spanne nach F3 auf dem
  Rohtext (``kind = "ort"``, ``value`` wörtlich, ``norm`` der Begriff, ``section`` der Abschnitt
  von 11), dahinter ``stelle`` (die grobe Stelle des Vorkommens), ``im_titel``, ``listenzeile``
  und ``hausnummer``. Nur lokal: die Spannen sind Rohtext.
* ``processed/dokumente_wahlbezirke_stelle.parquet``: je Paar (Dokument, Wahlbezirk) der Suche
  eine Zeile, auch ohne Rohtext (dann ohne Stelle): beste Stelle, Erwähnungen, Nebenregel C
  (``handelt_von``) und ``wahlkreis_adresse`` (eine verortete Adresse eines Begriffs des Bezirks
  liegt im Bezirk; die Grenzstraße, Frage 9.8, als Spalte, nicht als Variante).
* ``processed/adressen_wahlbezirke.parquet``: je Adresse im Text ihr Wahlbezirk. **Nie ein
  Download**: unter den Adressen sind Anschriften von Privatpersonen (Frage 9.7).

Messdokument ``docs/plans/16-ortsbezug.md``, § 6 mit § 10; die Regeln stehen in
``search.positions``, hier steht nur, was gelesen und geschrieben wird. Die Pfade gehören diesem
Modul (Synergien 2026-11, § 2.1): wer die Stellen liest (``weights``, später 21), nimmt sie aus
``places_files``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import deal
import polars as pl

from georep.analysis.weights import document_pairs
from georep.contracts import has_columns
from georep.enrich import Contribution
from georep.enrich.sections import sections_files
from georep.http import Transport
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import Step
from georep.prep.addresses import LOCATED, AddressBook, address_files
from georep.report.downloads import has_extracted_rows, measured
from georep.report.places import CONFIRMATION
from georep.report.tables import DISTRICT_COLUMN, PublishedTable
from georep.search.dictionary import TERMS, all_terms, normalise_terms
from georep.search.matcher import FlashTextMatcher
from georep.search.positions import (
    COARSE,
    PAIR_COLUMNS,
    REST,
    PlaceRules,
    pair_positions,
    raw_hits,
    term_positions,
)
from georep.settings import Settings
from georep.spans import SPAN_SCHEMA, check_spans, empty_spans, section_of, sort_spans
from georep.stores import RAW_TEXT_SCHEMA_VERSION, RawTextStore, stored_schema_version

EXTRACTOR = "ortsbezug-1"  # Name und Fassung des Verfahrens; vor den Extraktor des Rohtexts gesetzt
PLACES_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen der drei Dateien ändern
KIND = "ort"
# Zusatzspalten der Spannen (Punkt 74): was ``search.positions.term_positions`` je Vorkommen liest
SPAN_EXTRA: dict[str, pl.DataType] = {
    "stelle": pl.String(),
    "im_titel": pl.Boolean(),
    "listenzeile": pl.Boolean(),
    "hausnummer": pl.Boolean(),
}
ADDRESS_COLUMNS = ("id", "start", "end", "begriff", "nr", "zusatz", "status", "wahlkreis_id")
ADDRESS_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "start": pl.Int64(),
    "end": pl.Int64(),
    "begriff": pl.String(),
    "nr": pl.UInt16(),
    "zusatz": pl.String(),
    "status": pl.String(),
    "wahlkreis_id": pl.Int64(),
}
PAIR_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "wahlkreis_id": pl.Int64(),
    "stelle": pl.String(),
    "erwaehnungen": pl.Int64(),
    "n_begleit": pl.Int64(),
    "n_liste": pl.Int64(),
    "handelt_von": pl.Boolean(),
    "wahlkreis_adresse": pl.Boolean(),
    "extractor": pl.String(),
}


class PlaceFiles(NamedTuple):
    spans: Path  # Spannen nach F3, je Vorkommen
    pairs: Path  # je Paar (Dokument, Wahlbezirk)
    addresses: Path  # je Adresse im Text; nur lokal


def places_files(layout: Layout) -> PlaceFiles:
    """Die drei Dateien des Schritts ``places`` unter ``processed/``."""
    return PlaceFiles(
        layout.processed / "treffer_stellen.parquet",
        layout.processed / "dokumente_wahlbezirke_stelle.parquet",
        layout.processed / "adressen_wahlbezirke.parquet",
    )


@dataclass(frozen=True)
class PlaceTables:
    spans: pl.DataFrame
    addresses: pl.DataFrame
    bridged: int  # Dokumente, deren Rohtext genau zum Textstore plättet
    without_bridge: int  # Dokumente mit Rohtext, bei denen das nicht gilt: ohne Stelle


def _documents_ok(documents: pl.DataFrame) -> bool:
    return has_columns(documents, "id", "name", "text", "raw", "form_feeds", "extractor") and (
        documents.get_column("id").n_unique() == documents.height
    )


@deal.pre(
    lambda documents, sections, terms, streets, book, rules, marker: _documents_ok(documents),
    message="id, name, text, raw, form_feeds, extractor; jede Korpus-ID einmal",
)
def place_tables(
    documents: pl.DataFrame,
    sections: pl.DataFrame,
    terms: Sequence[str],
    streets: frozenset[str],
    book: AddressBook | None,
    rules: PlaceRules,
    marker: str,
) -> PlaceTables:
    """Spannen und Adressen aller Dokumente mit Rohtext, dessen Plättung der Textstore ist.

    ``documents`` trägt je Korpus-ID den OParl-Titel (``name``), den Textstore (``text``), den
    Rohtext mit seinen ``form_feeds`` und dessen Extraktor; ohne Rohtext sind die drei null, und die
    ID hat keine Spanne. Mehrere IDs dürfen denselben Rohtext tragen (Synergien 2026-11, § 1): jede
    bekommt ihre Spannen, ``im_titel`` nach ihrem eigenen Titel. ``streets`` sind die
    Straßenbegriffe des Wörterbuchs; nur hinter ihnen wird eine Hausnummer nachgeschlagen (``book``;
    ``None``: keine Adressen). Die Abschnitte und die Spannen liegen auf demselben Rohtext.
    """
    matcher = FlashTextMatcher()
    matcher.add_terms(terms)
    span_rows: list[tuple[object, ...]] = []
    address_rows: list[tuple[object, ...]] = []
    lengths: dict[str, int] = {}
    texts: dict[str, str] = {}
    bridged = without = 0
    for doc_id, title, store, raw, feeds, raw_extractor in documents.select(
        "id", "name", "text", "raw", "form_feeds", "extractor"
    ).iter_rows():
        if raw is None:
            continue
        hits = raw_hits(raw, tuple(feeds or ()), store or "", title or "", marker, matcher, rules)
        if hits is None:
            without += 1
            continue
        bridged += 1
        lengths[doc_id], texts[doc_id] = len(raw), raw
        extractor = f"{EXTRACTOR}/{raw_extractor}"
        for hit in hits:
            span_rows.append(
                (
                    doc_id,
                    hit.start,
                    hit.end,
                    KIND,
                    raw[hit.start : hit.end],
                    hit.term,
                    "",
                    extractor,
                    "",
                    hit.in_title,
                    hit.list_line,
                    hit.house is not None,
                )
            )
            if book is None or hit.house is None or hit.term not in streets:
                continue
            number, suffix = hit.house
            status, districts = book.locate(hit.term, number, suffix)
            located: list[int | None] = [*sorted(districts)] if status in LOCATED else []
            address_rows.extend(
                (doc_id, hit.start, hit.end, hit.term, number, suffix, status, district)
                for district in (located or [None])
            )
    found = pl.DataFrame(span_rows, schema={**SPAN_SCHEMA, **SPAN_EXTRA}, orient="row")
    located_spans = section_of(found, sections) if found.height else found
    spans = sort_spans(
        located_spans.with_columns(
            pl.col("section")
            .replace_strict(COARSE, default=REST, return_dtype=pl.String)
            .alias("stelle")
        )
    )
    if spans.is_empty():
        spans = empty_spans(SPAN_EXTRA)
    check_spans(spans, lengths, texts=texts)
    addresses = pl.DataFrame(address_rows, schema=ADDRESS_SCHEMA, orient="row").sort(
        "id", "start", "wahlkreis_id", nulls_last=True
    )
    return PlaceTables(spans, addresses, bridged, without)


def _pair_schema(
    spans: pl.DataFrame,
    addresses: pl.DataFrame,
    triples: pl.DataFrame,
    house_numbers: bool,
    result: pl.DataFrame,
) -> bool:
    return result.schema == pl.Schema(PAIR_SCHEMA)


@deal.ensure(_pair_schema, message="das Schema der Paartabelle")
def pair_table(
    spans: pl.DataFrame, addresses: pl.DataFrame, triples: pl.DataFrame, *, house_numbers: bool
) -> pl.DataFrame:
    """Je Paar (Dokument, Wahlbezirk) der Suche die Stelle, Nebenregel C und die Adresse.

    ``triples`` sind (Wahlbezirk, Dokument, Begriff) aus ``analysis.weights.document_pairs``.
    ``wahlkreis_adresse`` ist wahr, wo eine verortete Adresse eines Begriffs dieses Bezirks im
    Bezirk liegt, falsch, wo das Dokument Rohtext hat und keine, und leer ohne Rohtext oder ohne
    Hausnummern im Profil. ``extractor`` ist der der Spannen, leer ohne Rohtext.
    """
    pairs = pair_positions(term_positions(spans), triples)
    extractors = spans.group_by("id").agg(pl.col("extractor").first())
    supported = (
        addresses.filter(pl.col("wahlkreis_id").is_not_null())
        .select("id", pl.col("begriff").alias("suchbegriffe"), "wahlkreis_id")
        .join(
            triples.select("id", "suchbegriffe", "wahlkreis_id"),
            on=["id", "suchbegriffe", "wahlkreis_id"],
        )
        .select("id", "wahlkreis_id")
        .unique()
        .with_columns(pl.lit(True).alias("_adresse"))
    )
    known = pl.col("stelle").is_not_null()
    return (
        pairs.join(extractors, on="id", how="left")
        .join(supported, on=["id", "wahlkreis_id"], how="left")
        .with_columns(
            pl.when(known & pl.lit(house_numbers))
            .then(pl.col("_adresse").fill_null(False))
            .otherwise(None)
            .alias("wahlkreis_adresse"),
            pl.when(known).then(pl.col("extractor")).otherwise(None).alias("extractor"),
        )
        .select(*PAIR_COLUMNS, "wahlkreis_adresse", "extractor")
        .sort("id", "wahlkreis_id")
    )


def _raw_texts(path: Path) -> pl.DataFrame:
    """``name``, ``text``, ``form_feeds``, ``extractor`` aus dem Rohtextstore; leer bei anderer
    Schema-Version oder ohne Datei, wie ``enrich.sections.raw_text_frame``."""
    schema: dict[str, pl.DataType] = {
        "name": pl.String(),
        "raw": pl.String(),
        "form_feeds": pl.List(pl.Int64()),
        "extractor": pl.String(),
    }
    if not path.exists() or stored_schema_version(path) != str(RAW_TEXT_SCHEMA_VERSION):
        return pl.DataFrame(schema=schema)
    store = RawTextStore(path)
    rows = [
        (name, str(row["text"]), list(store.form_feeds(name)), str(row["extractor"]))
        for name, row in sorted(store.rows.items())
    ]
    return pl.DataFrame(rows, schema=schema, orient="row")


def position_table(layout: Layout) -> pl.DataFrame | None:
    """Je (Dokument, Begriff) mit Stelle die beste Stelle und Nebenregel C, für ``weights``.

    ``None`` ohne die Datei oder ohne eine Spanne (ein Profil ohne Rohtext): dann rechnet
    ``weights`` keine Variante nach Stelle, denn beide wären Kopien von ``einheit``.
    """
    path = places_files(layout).spans
    if not path.is_file():
        return None
    spans = pl.read_parquet(
        path, columns=["id", "norm", "stelle", "im_titel", "listenzeile", "hausnummer"]
    )
    if spans.is_empty():
        return None
    return term_positions(spans).select("id", "suchbegriffe", "stelle", "handelt_von")


def street_terms(streets_by_district: pl.DataFrame) -> frozenset[str]:
    """Die Straßenbegriffe des Wörterbuchs, wie ``search.dictionary`` sie bildet (mit ``str.``)."""
    found = streets_by_district.select(normalise_terms(pl.col(TERMS)).alias(TERMS)).explode(TERMS)
    return frozenset(found.get_column(TERMS).drop_nulls().to_list())


def places_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Der Schritt ``places``, wenn das Profil ihn einschaltet; offline, ``http`` bleibt ungenutzt."""
    places = settings.places
    if not places.enabled:
        return []
    files = places_files(layout)
    package = address_files(layout).table
    marker = settings.search.text_split_marker

    def run() -> str:
        corpus = pl.read_parquet(layout.corpus, columns=["id", "name", "file_name", "text"])
        documents = corpus.join(
            _raw_texts(layout.raw_texts), left_on="file_name", right_on="name", how="left"
        ).select("id", "name", "text", "raw", "form_feeds", "extractor")
        dictionary = pl.read_parquet(layout.dictionary)
        book = AddressBook.from_table(pl.read_parquet(package)) if places.house_numbers else None
        tables = place_tables(
            documents,
            pl.read_parquet(sections_files(layout).sections),
            all_terms(dictionary),
            street_terms(pl.read_parquet(layout.streets_by_district)),
            book,
            PlaceRules.from_settings(settings),
            marker,
        )
        pairs = pair_table(
            tables.spans,
            tables.addresses,
            document_pairs(dictionary, pl.read_parquet(layout.index)),
            house_numbers=places.house_numbers,
        )
        write_parquet(tables.spans, files.spans, schema_version=PLACES_SCHEMA_VERSION)
        write_parquet(pairs, files.pairs, schema_version=PLACES_SCHEMA_VERSION)
        write_parquet(tables.addresses, files.addresses, schema_version=PLACES_SCHEMA_VERSION)
        located = pairs.filter(pl.col("stelle").is_not_null())
        mentions = tables.addresses.unique(["id", "start"])
        placed = tables.addresses.filter(pl.col("wahlkreis_id").is_not_null()).unique(
            ["id", "start"]
        )
        line = (
            f"{tables.bridged} Dokumente mit Rohtext"
            + (
                f" ({tables.without_bridge} ohne Brücke zum Textstore)"
                if tables.without_bridge
                else ""
            )
            + f", {tables.spans.height} Erwähnungen; {pairs.height} Paare, {located.height} mit "
            f"Stelle, davon handelt von (Nebenregel C) {int(located.get_column('handelt_von').sum())}"
        )
        if places.house_numbers:
            line += f"; {mentions.height} Adressen, {placed.height} verortet"
        return line

    inputs = (
        layout.corpus,
        layout.raw_texts,
        sections_files(layout).sections,
        layout.dictionary,
        layout.index,
        layout.streets_by_district,
    ) + ((package,) if places.house_numbers else ())
    return [Step("places", inputs, tuple(files), run, PLACES_SCHEMA_VERSION)]


# --- kleine Stufe 3: das Paar als Download (Messdokument § 7 mit § 10, Punkt 6) ------------------


def pairs_shown(path: Path, settings: Settings) -> bool:
    """Nur gemessen und mit Rohtext, wie die Downloads von 11 und 12: auf Pages die Hauptperiode."""
    return measured(settings, CONFIRMATION.project) and has_extracted_rows(path)


PAIR_COLUMNS_DOC: dict[str, tuple[str, str]] = {
    "id": ("OParl-URL des Dokuments", ""),
    "wahlkreis_id": DISTRICT_COLUMN,
    "stelle": (
        "vorderste Stelle eines Begriffs des Wahlbezirks im Dokument: titel (steht auch im "
        "OParl-Titel), betreff, kern (Beschlussvorschlag, Fragen), begleittext (Sachdarstellung, "
        "Begründung, Stellungnahme, zitierter Beschluss, Text ohne Überschrift), rest; leer ohne "
        "Rohtext",
        "",
    ),
    "erwaehnungen": ("Vorkommen der Begriffe des Wahlbezirks im Text", "Anzahl"),
    "n_begleit": ("davon im Begleittext", "Anzahl"),
    "n_liste": ("davon im Begleittext in einer Listenzeile oder mit Hausnummer dahinter", "Anzahl"),
    "handelt_von": (
        "Nebenregel C: ein Begriff steht im Titel, im Betreff oder im Kern oder im Begleittext in "
        "einer Listenzeile oder mit Hausnummer; leer ohne Rohtext",
        "",
    ),
    "wahlkreis_adresse": (
        "eine Adresse im Text (ein Begriff des Wahlbezirks mit Hausnummer) liegt nach dem "
        "Adresspaket in diesem Wahlbezirk; leer ohne Rohtext oder ohne Hausnummern im Profil",
        "",
    ),
    "extractor": (
        "Verfahren und Extraktor des Rohtexts, etwa ortsbezug-1/pypdf-7.1.0+roh; leer ohne Rohtext",
        "",
    ),
}

TABLES = (
    PublishedTable(
        "dokumente_wahlbezirke_stelle",
        lambda layout: places_files(layout).pairs,
        "Stelle je Paar aus Dokument und Wahlbezirk: wo die Begriffe des Bezirks stehen, ob das "
        "Dokument von einem Ort im Bezirk handelt (Nebenregel C) und ob eine Adresse dort liegt; "
        "ohne Adressen und Textstellen",
        PAIR_COLUMNS_DOC,
        optional=True,
        enabled=lambda settings: settings.places.enabled,
        csv=None,  # als CSV rund 3 MB (Rückstand 35); die Spannen und Adressen nie
        shown=pairs_shown,
    ),
)

CONTRIBUTION: Contribution = Contribution("16-ortsbezug", early_steps=places_steps, tables=TABLES)
