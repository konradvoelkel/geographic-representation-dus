"""Datenmodell der Berichtsseite: aus den Parquet-Ergebnissen zu dataclasses für die Vorlage.

Polars bis zum Schluss, die Vorlage bekommt Listen von frozen dataclasses. Zeit ist Eingabe
(``now``), nie ``datetime.now()`` hier. Zahlen formatiert ``format_de`` von Hand (Dezimalkomma,
schmales geschütztes Leerzeichen als Tausendertrenner), kein ``locale``-Modul.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import deal
import polars as pl

from georep import __version__
from georep.analysis.hits import DISTRICT, RATE, TERMS
from georep.analysis.regression import RegressionPair, regression_pair
from georep.contracts import has_columns
from georep.errors import SchemaError
from georep.geo import Precinct, read_precincts
from georep.layout import Layout
from georep.prep.voters import TURNOUT
from georep.report.tables import GEOJSON_COLUMNS, GEOJSON_TABLE, PublishedTable, published
from georep.search.dictionary import all_terms
from georep.search.index import HITS, PAPER_IDS, TERM
from georep.settings import ResultsColumns, Settings

NARROW_NBSP = "\u202f"  # schmales geschütztes Leerzeichen: Tausender und vor dem Prozentzeichen
TOP_TERMS = 5  # Begriffe je Wahlbezirk in Karte und Tabelle
TOP_TERMS_CITY = 20  # trefferstärkste Begriffe stadtweit


@dataclass(frozen=True)
class TermRow:
    term: str
    hits: int  # Dokumente mit mindestens einem Treffer
    districts: tuple[int, ...]  # Wahlbezirke, deren Wörterbuch den Begriff führt


@dataclass(frozen=True)
class DistrictRow:
    id: int
    name: str
    hits: int
    eligible: int
    voters: int
    turnout: float  # Anteil 0 bis 1
    rate: float  # Treffer je Wahlberechtigtem
    terms_total: int  # Begriffe im Wörterbuch, versteckte eingeschlossen
    terms_without_hits: int
    top_terms: tuple[TermRow, ...]  # die TOP_TERMS trefferstärksten, versteckte nicht
    terms: tuple[TermRow, ...]  # alle Begriffe mit Treffer, absteigend, versteckte nicht


@dataclass(frozen=True)
class KeyFigures:
    districts: int
    precincts: int
    documents: int
    documents_with_text: int
    terms: int
    documents_hit: int  # Vereinigung aller paper_ids
    rate_median: float
    rate_min: float
    rate_max: float
    turnout_median: float


@dataclass(frozen=True)
class Download:
    name: str
    format: str
    rows: int | None
    bytes: int
    sha256: str
    description: str


@dataclass(frozen=True)
class ColumnDoc:
    table: str
    column: str
    dtype: str
    description: str
    unit: str


@dataclass(frozen=True)
class DataStand:
    election: dt.date
    period_start: dt.date
    period_end: dt.date | None  # None: laufende Periode ohne Ende
    streets_fetched: (
        dt.date | None
    )  # aus dem Stamp des Netzschritts; None = Referenzdaten der Arbeit
    pois_fetched: dt.date | None


@dataclass(frozen=True)
class ReportModel:
    generated_at: dt.datetime
    version: str
    commit: str | None
    stand: DataStand
    figures: KeyFigures
    districts: tuple[DistrictRow, ...]
    top_terms: tuple[TermRow, ...]
    hidden_terms: tuple[str, ...]
    regression: RegressionPair
    downloads: tuple[Download, ...]
    columns: tuple[ColumnDoc, ...]
    working_crs: str


# --- Zahlenformat -----------------------------------------------------------------------------


@deal.pure
@deal.pre(lambda value, decimals=0: decimals >= 0 and math.isfinite(value))
@deal.post(lambda result: "." not in result and result == result.strip() and result != "")
def format_de(value: float, decimals: int = 0) -> str:
    """``1234567.891`` mit ``decimals=1`` wird ``1 234 567,9``; eine gerundete Null trägt kein Minus."""
    rounded = round(float(value), decimals)
    if rounded == 0:
        rounded = 0.0
    grouped = f"{rounded:,.{decimals}f}"
    return grouped.replace(",", NARROW_NBSP).replace(".", ",")


def percent_de(share: float, decimals: int = 1) -> str:
    """Anteil 0 bis 1 als ``53,1 %``."""
    return f"{format_de(share * 100.0, decimals)}{NARROW_NBSP}%"


# --- Spaltenschema ------------------------------------------------------------------------------


def _table_docs(table: PublishedTable, path: Path) -> list[ColumnDoc]:
    """Spalten einer Parquet-Datei mit ihrer Bedeutung aus dem Register; beide Richtungen müssen passen."""
    schema = pl.read_parquet_schema(path)
    known = table.columns
    undocumented = [c for c in schema if c not in known]
    stale = [c for c in known if c not in schema]
    if undocumented or stale:
        raise SchemaError(
            f"{table.name}: ohne Beschreibung {undocumented}, Beschreibung ohne Spalte {stale}"
        )
    return [
        ColumnDoc(table.name, column, str(dtype), *known[column])
        for column, dtype in schema.items()
    ]


def column_docs(layout: Layout) -> tuple[ColumnDoc, ...]:
    """Spaltenschema aller veröffentlichten Tabellen und des GeoJSON (``report.tables``)."""
    docs: list[ColumnDoc] = []
    for table in published(layout):
        docs.extend(_table_docs(table, table.path(layout)))
    docs.extend(
        ColumnDoc(GEOJSON_TABLE, column, "GeoJSON-Eigenschaft", *text)
        for column, text in GEOJSON_COLUMNS.items()
    )
    return tuple(docs)


# --- Modell ---------------------------------------------------------------------------------------


def district_names(precincts: Sequence[Precinct]) -> dict[int, str]:
    """Wahlbezirk -> Name; jeder Stimmbezirk trägt den Namen seines Wahlbezirks."""
    names: dict[int, str] = {}
    for precinct in precincts:
        current = names.setdefault(precinct.district_id, precinct.district_name)
        if current != precinct.district_name:
            raise SchemaError(
                f"Wahlbezirk {precinct.district_id} trägt zwei Namen: "
                f"{current!r} und {precinct.district_name!r}"
            )
    return names


@deal.pre(
    lambda dictionary, index: (
        has_columns(dictionary, DISTRICT, TERMS) and has_columns(index, TERM, HITS)
    )
)
@deal.post(lambda result: result.columns == [DISTRICT, TERM, HITS, "districts"])
def term_counts(dictionary: pl.DataFrame, index: pl.DataFrame) -> pl.DataFrame:
    """Eine Zeile je Wahlbezirk und Begriff: Treffer und alle Wahlbezirke, die den Begriff führen."""
    pairs = dictionary.select(DISTRICT, TERMS).explode(TERMS).rename({TERMS: TERM})
    shared = pairs.group_by(TERM).agg(pl.col(DISTRICT).sort().alias("districts"))
    return (
        pairs.join(index.select(TERM, HITS), on=TERM, how="left")
        .with_columns(pl.col(HITS).fill_null(0))
        .join(shared, on=TERM, how="left")
        .sort([DISTRICT, HITS, TERM], descending=[False, True, False])
    )


def _descending(rows: Sequence[TermRow]) -> bool:
    return all(a.hits >= b.hits for a, b in zip(rows, rows[1:], strict=False))


@deal.pre(
    lambda results, counts, names, columns, hidden: (
        has_columns(results, DISTRICT, HITS, RATE, TURNOUT, columns.eligible, columns.voters)
        and has_columns(counts, DISTRICT, TERM, HITS, "districts")
    )
)
@deal.ensure(
    lambda results, counts, names, columns, hidden, result: len(result) == results.height,
    message="eine Zeile je Wahlbezirk der Auswertung",
)
@deal.post(lambda result: all(r.name and r.rate >= 0 and 0 <= r.turnout <= 1 for r in result))
@deal.post(
    lambda result: all(_descending(r.top_terms) and _descending(r.terms) for r in result),
    message="Begriffe absteigend nach Treffern",
)
@deal.raises(SchemaError)
def district_rows(
    results: pl.DataFrame,
    counts: pl.DataFrame,
    names: Mapping[int, str],
    columns: ResultsColumns,
    hidden: Sequence[str],
) -> tuple[DistrictRow, ...]:
    missing = sorted(set(results.get_column(DISTRICT)) - set(names))
    if missing:
        raise SchemaError(f"Wahlbezirke ohne Geometrie im GeoJSON: {missing}")
    rows: list[DistrictRow] = []
    for row in results.sort(DISTRICT).iter_rows(named=True):
        mine = counts.filter(pl.col(DISTRICT) == row[DISTRICT])
        shown = mine.filter(~pl.col(TERM).is_in(list(hidden)) & (pl.col(HITS) > 0))
        terms = tuple(
            TermRow(r[TERM], int(r[HITS]), tuple(r["districts"]))
            for r in shown.iter_rows(named=True)
        )
        rows.append(
            DistrictRow(
                id=int(row[DISTRICT]),
                name=names[int(row[DISTRICT])],
                hits=int(row[HITS]),
                eligible=int(row[columns.eligible]),
                voters=int(row[columns.voters]),
                turnout=float(row[TURNOUT]),
                rate=float(row[RATE]),
                terms_total=mine.height,
                terms_without_hits=mine.filter(pl.col(HITS) == 0).height,
                top_terms=terms[:TOP_TERMS],
                terms=terms,
            )
        )
    return tuple(rows)


@deal.post(lambda result: _descending(result) and len(result) <= TOP_TERMS_CITY)
def top_terms_city(counts: pl.DataFrame, hidden: Sequence[str]) -> tuple[TermRow, ...]:
    """Die trefferstärksten Begriffe stadtweit, jeder einmal, mit allen Wahlbezirken, die ihn führen."""
    best = (
        counts.filter(~pl.col(TERM).is_in(list(hidden)) & (pl.col(HITS) > 0))
        .unique(subset=[TERM], keep="first", maintain_order=True)
        .sort([HITS, TERM], descending=[True, False])
        .head(TOP_TERMS_CITY)
    )
    return tuple(
        TermRow(r[TERM], int(r[HITS]), tuple(r["districts"])) for r in best.iter_rows(named=True)
    )


def key_figures(
    results: pl.DataFrame, dictionary: pl.DataFrame, corpus: Path, precincts: int
) -> KeyFigures:
    documents, with_text = (
        pl.scan_parquet(corpus)
        .select(pl.len(), (pl.col("text") != "").sum().alias("with_text"))
        .collect()
        .row(0)
    )
    rates: list[float] = results.get_column(RATE).to_list()
    turnouts: list[float] = results.get_column(TURNOUT).to_list()
    return KeyFigures(
        districts=results.height,
        precincts=precincts,
        documents=int(documents),
        documents_with_text=int(with_text),
        terms=len(all_terms(dictionary)),
        documents_hit=int(results.get_column(PAPER_IDS).explode().drop_nulls().n_unique()),
        rate_median=statistics.median(rates),
        rate_min=min(rates),
        rate_max=max(rates),
        turnout_median=statistics.median(turnouts),
    )


def stamp_written(output: Path) -> dt.date | None:
    """Das Datum aus dem Stamp neben einer Schrittausgabe, falls der Schritt je lief."""
    stamp = output.with_name(output.name + ".stamp.json")
    if not stamp.is_file():
        return None
    try:
        written = json.loads(stamp.read_text(encoding="utf-8")).get("written")
    except ValueError:
        return None
    return dt.datetime.fromisoformat(written).date() if isinstance(written, str) else None


def data_stand(layout: Layout, settings: Settings) -> DataStand:
    return DataStand(
        election=settings.period.election_day,
        period_start=settings.period.start,
        period_end=settings.period.end,
        streets_fetched=stamp_written(layout.streets),
        pois_fetched=stamp_written(layout.pois),
    )


def build_report_model(
    layout: Layout,
    settings: Settings,
    *,
    now: dt.datetime,
    commit: str | None = None,
    downloads: Sequence[Download] = (),
) -> ReportModel:
    """Alles, was die Vorlage braucht, aus ``processed/`` und ``external/``; ``now`` ist Eingabe."""
    results = pl.read_parquet(layout.results)
    dictionary = pl.read_parquet(layout.dictionary)
    index = pl.read_parquet(layout.index)
    precincts = read_precincts(layout.districts_geojson, settings.columns, settings.geo.working_crs)
    hidden = tuple(settings.search.hide_in_display)
    counts = term_counts(dictionary, index)
    return ReportModel(
        generated_at=now,
        version=__version__,
        commit=commit,
        stand=data_stand(layout, settings),
        figures=key_figures(results, dictionary, layout.corpus, len(precincts)),
        districts=district_rows(
            results, counts, district_names(precincts), settings.columns.results, hidden
        ),
        top_terms=top_terms_city(counts, hidden),
        hidden_terms=hidden,
        regression=regression_pair(results, settings.analysis.exclude_districts),
        downloads=tuple(downloads),
        columns=column_docs(layout),
        working_crs=settings.geo.working_crs,
    )
