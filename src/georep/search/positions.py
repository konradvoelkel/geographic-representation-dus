"""Vorhaben 16: die Stelle eines Treffers im Dokument und Nebenregel C (Ortsbezug).

Die Suche zählt einen Begriff, wo er im Textstore steht (kleingeschrieben, ohne Zeilenumbrüche, ab
dem Marker). Hier bekommt jedes Vorkommen seine Stelle: über ``prep.raw_texts.flatten_with_offsets``
(Fundament F1) liegt es auf dem Rohtext, wo die Abschnitte von Vorhaben 11 liegen
(``spans.section_of``), und aus dem Abschnitt wird eine von fünf **groben Stellen**: Titel (der
Begriff steht auch im OParl-Titel), Betreff, Kern (Beschlussvorschlag, Fragen einer Anfrage),
Begleittext (Sachdarstellung, Begründung, Stellungnahme, zitierter Beschluss, Alternative, Rumpf),
Rest (Anlagenliste, „Nachrichtlich", Kopf, hinter dem Schluss). Die beste Stelle ist die vorderste
in dieser Folge (Messdokument ``docs/plans/16-ortsbezug.md``, § 3.0).

**Nebenregel C** (``ortsbezug-entwurf-2``, bestätigt an 100 frischen Paaren, § 4.4): ein Begriff
handelt in einem Dokument von seinem Ort, wenn er im Titel, im Betreff oder im Kern steht, oder im
Begleittext in einer **Listenzeile** (die Zeile ohne Leerraum am Rand hat höchstens
``list_max_line`` Zeichen, vor dem Begriff stehen in ihr höchstens ``list_max_lead``) oder mit einer
**Hausnummer** dahinter. Ein Paar (Dokument, Wahlbezirk) handelt von einem Ort des Bezirks, wenn
einer seiner Begriffe es tut. Die Konstanten und das Muster der Hausnummer stehen im Stadtprofil
(``[places]``), unverändert wie im Messskript; das Messskript ``docs/plans/16-ortsbezug-messung.py``
ist die Referenz, und ``tests/golden/test_places_numbers.py`` hält den Schritt an seiner Ausgabe
für die 300 kodierten Paare fest.

Alles hier ist rein: Texte und Frames hinein, Treffer und Frames heraus; Dateien liest
``enrich.places``.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import deal
import polars as pl

from georep.contracts import has_columns
from georep.prep.raw_texts import flatten_with_offsets, split_lines

if TYPE_CHECKING:
    from georep.search.matcher import FlashTextMatcher
    from georep.settings import Settings

# Die fünf groben Stellen in ihrer Rangfolge; ``settings.PLACE_POSITIONS`` hält dieselben Namen.
TITLE = "titel"
SUBJECT = "betreff"
CORE = "kern"
BODY = "begleittext"
REST = "rest"
POSITIONS = (TITLE, SUBJECT, CORE, BODY, REST)
RANK: Mapping[str, int] = {position: rank for rank, position in enumerate(POSITIONS)}
# Nebenregel C: was in diesen Stellen steht, handelt immer von seinem Ort
LEADING = frozenset({TITLE, SUBJECT, CORE})
# Der Abschnitt der Ebene 1 aus Vorhaben 11 (``norm``) und seine grobe Stelle. Jeder andere
# Abschnitt (Anlagenliste, „Nachrichtlich", ``kopf_*``) und jede Stelle außerhalb aller Abschnitte
# (Kopf vor dem Betreff, hinter der Grußformel) ist Rest. Die Namen sind der Katalog von 11, kein
# Wort einer Stadt: das Profil bildet seine Überschriften auf sie ab.
COARSE: Mapping[str, str] = {
    "betreff": SUBJECT,
    "beschlussvorschlag": CORE,
    "fragen": CORE,
    "sachdarstellung": BODY,
    "begruendung": BODY,
    "stellungnahme": BODY,
    "beschlusslage": BODY,
    "alternative": BODY,
    "rumpf": BODY,
}

TERM = "suchbegriffe"  # wie ``search.index.TERM``
DOC = "id"
DISTRICT = "wahlkreis_id"
POSITION = "stelle"
MENTIONS = "erwaehnungen"
IN_BODY = "n_begleit"
IN_LIST = "n_liste"
ABOUT = "handelt_von"
TERM_COLUMNS = (DOC, TERM, POSITION, MENTIONS, IN_BODY, IN_LIST, ABOUT)
PAIR_COLUMNS = (DOC, DISTRICT, POSITION, MENTIONS, IN_BODY, IN_LIST, ABOUT)


@deal.pure
@deal.post(lambda result: result in POSITIONS and result != TITLE)
def coarse_position(section: str) -> str:
    """Die grobe Stelle eines Vorkommens aus seinem Abschnitt; jeder unbekannte ist Rest."""
    return COARSE.get(section, REST)


# Kein ``deal.pure``: die Funktion läuft je Vorkommen (66 004 in der Hauptperiode), und der
# Patcher von ``deal.has`` ist prozessweit und nicht reentrant (CLAUDE.md, „Nie").
@deal.pre(
    lambda line, column, max_line, max_lead: (
        0 <= column <= len(line) and max_line >= 1 and max_lead >= 0
    )
)
def is_list_line(line: str, column: int, max_line: int, max_lead: int) -> bool:
    """Steht der Begriff an Spalte ``column`` von ``line`` vorn in einer kurzen Zeile?

    Wie das Messskript: die Zeile ohne Leerraum am Rand hat höchstens ``max_line`` Zeichen, und
    vor dem Begriff stehen ohne den Leerraum am Anfang höchstens ``max_lead`` („14 ", „1. ").
    """
    lead = len(line) - len(line.lstrip())
    return len(line.strip()) <= max_line and column - lead <= max_lead


def house_number(raw: str, end: int, pattern: re.Pattern[str] | None) -> tuple[int, str] | None:
    """Die Hausnummer direkt hinter Stelle ``end`` als (Nummer, Zusatz klein), sonst ``None``.

    ``pattern`` ist ``places.house_number`` mit den Gruppen ``nr`` und ``zusatz``; ``None``
    heißt „das Profil kennt keine Hausnummer". Ein Bereich („50–54") nennt seine erste Nummer.
    """
    if pattern is None:
        return None
    found = pattern.match(raw, end)
    if found is None:
        return None
    return int(found.group("nr")), (found.group("zusatz") or "").lower()


@dataclass(frozen=True)
class PlaceRules:
    """Die Konstanten von Nebenregel C aus ``[places]``, das Muster übersetzt."""

    list_max_line: int
    list_max_lead: int
    house_number: re.Pattern[str] | None

    @classmethod
    def from_settings(cls, settings: Settings) -> PlaceRules:
        places = settings.places
        return cls(
            places.list_max_line,
            places.list_max_lead,
            re.compile(places.house_number) if places.house_number else None,
        )


@dataclass(frozen=True)
class RawHit:
    """Ein Vorkommen im Rohtext: Begriff, Spanne, im Titel, Listenzeile, Hausnummer dahinter."""

    term: str
    start: int
    end: int
    in_title: bool
    list_line: bool
    house: tuple[int, str] | None


def _hits_lie_on_the_raw_text(
    raw: str,
    form_feeds: Sequence[int],
    store: str,
    title: str,
    marker: str,
    matcher: FlashTextMatcher,
    rules: PlaceRules,
    result: list[RawHit] | None = None,
) -> bool:
    if result is None:
        return True
    starts = [hit.start for hit in result]
    return starts == sorted(starts) and all(0 <= hit.start < hit.end <= len(raw) for hit in result)


@deal.ensure(_hits_lie_on_the_raw_text, message="Spannen im Rohtext, nach Anfang geordnet")
def raw_hits(
    raw: str,
    form_feeds: Sequence[int],
    store: str,
    title: str,
    marker: str,
    matcher: FlashTextMatcher,
    rules: PlaceRules,
) -> list[RawHit] | None:
    """Jedes Vorkommen eines Begriffs, auf den Rohtext gelegt; ``None`` ohne Brücke.

    Gesucht wird im geplätteten Rohtext mit demselben Matcher wie im Index, und nur, wenn er
    **genau** der Textstore ``store`` ist: sonst wäre eine Stelle nicht die, die die Suche zählt
    (Messdokument § 3.0; Fundament F1 verspricht die Gleichheit für jedes Dokument). Eine Spanne
    ``[a, b)`` im geplätteten Text ist im Rohtext ``[offsets[a], offsets[b - 1] + 1)``.
    ``title`` ist der OParl-Titel; ein Begriff, den derselbe Matcher dort findet, steht „im Titel".
    """
    flat, offsets = flatten_with_offsets(raw, marker, form_feeds)
    if flat != store:
        return None
    in_title = matcher.extract(title.lower()) if title else set()
    lines = split_lines(raw)
    starts = [start for start, _ in lines]
    hits: list[RawHit] = []
    for term, a, b in matcher.spans(flat):
        start, end = offsets[a], offsets[b - 1] + 1
        line_start, line_end = lines[bisect.bisect_right(starts, start) - 1]
        hits.append(
            RawHit(
                term,
                start,
                end,
                term in in_title,
                is_list_line(
                    raw[line_start:line_end],
                    start - line_start,
                    rules.list_max_line,
                    rules.list_max_lead,
                ),
                house_number(raw, end, rules.house_number),
            )
        )
    return hits


# --- je (Dokument, Begriff) und je (Dokument, Wahlbezirk) ----------------------------------------

_SPAN_INPUT = ("id", "norm", "stelle", "im_titel", "listenzeile", "hausnummer")


def _one_row_per_term(spans: pl.DataFrame, result: pl.DataFrame) -> bool:
    return result.height == spans.select("id", "norm").unique().height and list(
        result.columns
    ) == list(TERM_COLUMNS)


@deal.pre(lambda spans: has_columns(spans, *_SPAN_INPUT))
@deal.ensure(_one_row_per_term, message="eine Zeile je (Dokument, Begriff) mit Vorkommen")
def term_positions(spans: pl.DataFrame) -> pl.DataFrame:
    """Je (Dokument, Begriff): beste Stelle, Vorkommen, davon im Begleittext und dort in einer
    Liste oder mit Hausnummer, und Nebenregel C (``handelt_von``).

    ``spans`` sind die Vorkommen mit ``norm`` (dem Begriff), ``stelle`` (der groben Stelle des
    Vorkommens), ``im_titel``, ``listenzeile`` und ``hausnummer``. Steht der Begriff im Titel, ist
    seine beste Stelle der Titel, wo immer er im Text steht (Messdokument § 3.0).
    """
    rank = pl.col(POSITION).replace_strict(RANK, return_dtype=pl.Int64)
    in_body = pl.col(POSITION) == BODY
    ranks = (
        spans.group_by(DOC, "norm")
        .agg(
            rank.min().alias("_rang"),
            pl.len().cast(pl.Int64).alias(MENTIONS),
            in_body.sum().cast(pl.Int64).alias(IN_BODY),
            (in_body & (pl.col("listenzeile") | pl.col("hausnummer")))
            .sum()
            .cast(pl.Int64)
            .alias(IN_LIST),
            pl.col("im_titel").any().alias("_titel"),
        )
        .with_columns(
            pl.when(pl.col("_titel")).then(RANK[TITLE]).otherwise(pl.col("_rang")).alias("_rang")
        )
    )
    return (
        ranks.with_columns(
            pl.col("_rang")
            .replace_strict({rank: name for name, rank in RANK.items()}, return_dtype=pl.String)
            .alias(POSITION),
            ((pl.col("_rang") <= RANK[CORE]) | (pl.col(IN_LIST) >= 1)).alias(ABOUT),
        )
        .rename({"norm": TERM})
        .select(TERM_COLUMNS)
        .sort(DOC, TERM)
    )


def _one_row_per_pair(terms: pl.DataFrame, triples: pl.DataFrame, result: pl.DataFrame) -> bool:
    return result.height == triples.select(DOC, DISTRICT).unique().height and list(
        result.columns
    ) == list(PAIR_COLUMNS)


@deal.pre(
    lambda terms, triples: (
        has_columns(terms, *TERM_COLUMNS) and has_columns(triples, DISTRICT, DOC, TERM)
    )
)
@deal.ensure(_one_row_per_pair, message="eine Zeile je Paar (Dokument, Wahlbezirk)")
def pair_positions(terms: pl.DataFrame, triples: pl.DataFrame) -> pl.DataFrame:
    """Je Paar (Dokument, Wahlbezirk) der Suche: die beste Stelle seiner Begriffe, die Summen und
    Nebenregel C (einer der Begriffe handelt von seinem Ort).

    ``triples`` sind (Wahlbezirk, Dokument, Begriff) wie ``analysis.weights.document_pairs``:
    jedes Paar der Suche, auch eines ohne Rohtext. Dort bleiben Stelle, Zählungen und Urteil leer
    (null): über die Stelle ist nichts bekannt, und jede Gewichtung zählt das Paar wie bisher.
    """
    joined = triples.select(DISTRICT, DOC, TERM).join(
        terms.select(DOC, TERM, POSITION, MENTIONS, IN_BODY, IN_LIST, ABOUT),
        on=[DOC, TERM],
        how="left",
    )
    rank = pl.col(POSITION).replace_strict(RANK, return_dtype=pl.Int64, default=None)
    known = pl.col(POSITION).is_not_null()
    pairs = joined.group_by(DOC, DISTRICT).agg(
        rank.min().alias("_rang"),
        pl.col(MENTIONS).sum().alias(MENTIONS),
        pl.col(IN_BODY).sum().alias(IN_BODY),
        pl.col(IN_LIST).sum().alias(IN_LIST),
        pl.col(ABOUT).any().alias(ABOUT),
        known.any().alias("_bekannt"),
    )
    unknown = ~pl.col("_bekannt")
    return (
        pairs.with_columns(
            pl.col("_rang")
            .replace_strict(
                {rank: name for name, rank in RANK.items()}, return_dtype=pl.String, default=None
            )
            .alias(POSITION),
            *(
                pl.when(unknown).then(None).otherwise(pl.col(column)).alias(column)
                for column in (MENTIONS, IN_BODY, IN_LIST, ABOUT)
            ),
        )
        .select(PAIR_COLUMNS)
        .sort(DOC, DISTRICT)
    )
