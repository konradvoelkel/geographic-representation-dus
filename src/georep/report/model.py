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
from dataclasses import dataclass, replace
from pathlib import Path

import deal
import polars as pl

from georep import __version__
from georep.analysis import bodies
from georep.analysis.hits import DISTRICT, RATE, TERMS
from georep.analysis.regression import RegressionPair, regression_pair, spearman
from georep.analysis.weights import (
    BY_DISTRICTS,
    BY_IDF,
    COMBINED,
    N_DISTRICTS,
    TOPIC_PREFIX,
    UNIT,
    VARIANT,
    WEIGHTED_HITS,
    WEIGHTED_RATE,
    topic_variant,
)
from georep.contracts import has_columns
from georep.errors import EmptyResultError, SchemaError
from georep.geo import Precinct, read_precincts
from georep.layout import Layout
from georep.prep import bodies as prep_bodies
from georep.prep.bodies import BodyRules
from georep.prep.voters import TURNOUT
from georep.report.search import SearchEntry, search_entries
from georep.report.tables import GEOJSON_COLUMNS, GEOJSON_TABLE, PublishedTable, published
from georep.search.dictionary import all_terms
from georep.search.index import HITS, PAPER_IDS, TERM
from georep.settings import Bodies, ResultsColumns, Settings, Weights

NARROW_NBSP = "\u202f"  # schmales geschütztes Leerzeichen: Tausender und vor dem Prozentzeichen
TOP_TERMS = 5  # Begriffe je Wahlbezirk in Karte und Tabelle
TOP_TERMS_CITY = 20  # trefferstärkste Begriffe stadtweit


@dataclass(frozen=True)
class TermRow:
    term: str
    hits: int  # Dokumente mit mindestens einem Treffer
    districts: tuple[int, ...]  # Wahlbezirke, deren Wörterbuch den Begriff führt


@dataclass(frozen=True)
class DistrictBodies:
    """Die Treffer eines Wahlbezirks nach Gremium (Option 05)."""

    own: int  # aus der Bezirksvertretung eines eigenen Stadtbezirks
    other: int  # aus einer anderen Bezirksvertretung
    council: int
    committee: int
    advisory: int
    unknown: int
    own_share: float  # ``own`` geteilt durch alle Treffer des Bezirks
    council_share: float
    own_rate: float  # ``own`` je Wahlberechtigtem
    city_districts: tuple[int, ...]  # nach Gewicht absteigend; mehr als einer ist die Ausnahme

    @property
    def shared(self) -> bool:
        """Der Wahlbezirk liegt in mehr als einem Stadtbezirk: die Fußnote der Seite gilt für ihn."""
        return len(self.city_districts) > 1


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
    # Neue Felder mit Default am Ende: Tests bauen DistrictRow positional (Option 05)
    bodies: DistrictBodies | None = None


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


# --- Option 05: Gremien ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BodyRow:
    """Eine Zeile der Gremientabelle; ``name`` ist leer, wenn die Settings keinen gesicherten kennen."""

    code: str  # Kürzel der Drucksachennummer, etwa BV6; leer, wenn keine Nummer passte
    name: str
    kind: str  # eines aus prep.bodies.KINDS
    kind_label: str  # „Bezirksvertretung", „Rat", „Ausschuss", „Beirat", „unbekannt"
    city_district: int | None
    documents: int
    with_hits: int
    local_share: float | None  # nur Bezirksvertretungen mit Treffern

    @property
    def label(self) -> str:
        """Was die Seite zeigt: der Name, sonst das Kürzel (Entscheidung 9)."""
        return self.name or self.code or "ohne Drucksachennummer"


@dataclass(frozen=True)
class BodyFigures:
    """Die Zahlen über dem Abschnitt „Gremien"."""

    documents: int
    by_kind: tuple[tuple[str, str, int, float], ...]  # (Klasse, Label, Dokumente, Anteil)
    unknown_share: float
    bodies: int  # verschiedene Kürzel
    without_name: int  # Kürzel ohne gesicherten Namen in den Settings
    hits: int  # Dokument-Bezirk-Paare über alle Wahlbezirke
    own_hits: int
    names_as_of: dt.date | None  # Stand der Namen aus den Settings


# --- Option 06: Gewichtung (docs/plans/06-gewichtung.md) ---------------------------------------


@dataclass(frozen=True)
class SensitivityRow:
    """Eine Zeile der Sensitivitätstabelle: eine Gewichtung mit beiden Regressionen."""

    name: str  # Variantenname der langen Tabelle
    label: str
    description: str  # die Formel in einem Halbsatz
    total: float  # Summe der gewichteten Treffer über alle Wahlbezirke
    pair: RegressionPair | None  # None: keine Streuung, die Zeile zeigt „—"
    rho: float | None  # Rangkorrelation zur ungewichteten Quote
    topic: int | None = None  # Themennummer, wenn die Variante ein Thema ist


@dataclass(frozen=True)
class TopicRow:
    index: int
    words: tuple[str, ...]
    documents: int  # Dokumente, deren stärkstes Thema dieses ist
    hits_share: float  # Anteil des Themas an den gezählten Treffern


@dataclass(frozen=True)
class TermExample:
    """Ein Begriff als Beispiel im Text des Abschnitts; aus ``gewichte_begriffe.parquet``."""

    term: str
    hits: int
    districts: int


@dataclass(frozen=True)
class Sensitivity:
    """Der Abschnitt „Was ändert die Gewichtung?": Zeilen, Themen und zwei Zählungen."""

    rows: tuple[SensitivityRow, ...]
    topics: tuple[TopicRow, ...]
    excluded: tuple[int, ...]
    significant_all: int  # Varianten mit p < 0,05 über alle Wahlbezirke
    significant_without: int  # dasselbe ohne die Ausreißer
    strongest: TermExample | None = None  # der Begriff in den meisten Dokumenten
    widest: TermExample | None = None  # der Begriff in den meisten Wörterbüchern
    level: float = 0.05

    @property
    def has_without(self) -> bool:
        """Hat überhaupt eine Variante eine zweite Regression? Sonst bleibt die rechte Hälfte weg.

        Auf der Mini-Fixture (drei Wahlbezirke) bleiben ohne die Ausreißer zu wenige übrig; dann
        soll die Tabelle keine Spaltengruppe „ohne 1 und 10" voller Gedankenstriche zeigen.
        """
        return any(row.pair is not None and row.pair.without is not None for row in self.rows)


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
    # Option 08: die Vorschläge der Suche; leer heißt „kein Abschnitt suche" in der Vorlage.
    search: tuple[SearchEntry, ...] = ()
    # Option 05: ohne die Tabellen der Gremien bleibt der Abschnitt weg ({% if model.bodies %})
    bodies: tuple[BodyRow, ...] = ()
    body_figures: BodyFigures | None = None
    body_regression: RegressionPair | None = None
    sensitivity: Sensitivity | None = None  # Option 06; None = ohne Abschnitt


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


# --- Option 05: Gremien im Modell -----------------------------------------------------------------


def _every_row_has_bodies(
    rows: Sequence[DistrictRow], frame: pl.DataFrame, result: tuple[DistrictRow, ...] = ()
) -> bool:
    return all(
        r.bodies is not None
        and 0.0 <= r.bodies.own_share <= 1.0
        and 0.0 <= r.bodies.council_share <= 1.0
        and r.bodies.own
        + r.bodies.other
        + r.bodies.council
        + r.bodies.committee
        + r.bodies.advisory
        + r.bodies.unknown
        == r.hits
        for r in result
    )


@deal.pre(
    lambda rows, frame: has_columns(frame, DISTRICT, bodies.UNITS, *bodies.PARTS),
    message="Kennzahlen je Wahlbezirk aus wahlbezirke_gremien.parquet",
)
@deal.ensure(
    _every_row_has_bodies,
    message="jede Zeile mit Gremien, Anteile in [0, 1], Summe gleich den Treffern",
)
@deal.raises(SchemaError)
def with_bodies(rows: Sequence[DistrictRow], frame: pl.DataFrame) -> tuple[DistrictRow, ...]:
    """Dieselben Zeilen mit gefülltem ``bodies``; ein fehlender Wahlbezirk ist ein ``SchemaError``."""
    by_district = {int(r[DISTRICT]): r for r in frame.iter_rows(named=True)}
    missing = sorted(r.id for r in rows if r.id not in by_district)
    if missing:
        raise SchemaError(f"Wahlbezirke ohne Gremien-Kennzahlen: {missing}")
    filled: list[DistrictRow] = []
    for row in rows:
        values = by_district[row.id]
        filled.append(
            replace(
                row,
                bodies=DistrictBodies(
                    own=int(values[bodies.OWN]),
                    other=int(values[bodies.OTHER]),
                    council=int(values[bodies.COUNCIL_HITS]),
                    committee=int(values[bodies.COMMITTEE_HITS]),
                    advisory=int(values[bodies.ADVISORY_HITS]),
                    unknown=int(values[bodies.UNKNOWN_HITS]),
                    own_share=float(values[bodies.OWN_SHARE]),
                    council_share=float(values[bodies.COUNCIL_SHARE]),
                    own_rate=float(values[bodies.OWN_RATE]),
                    city_districts=tuple(int(u) for u in values[bodies.UNITS]),
                ),
            )
        )
    return tuple(filled)


@deal.pre(
    lambda frame, settings: has_columns(
        frame, prep_bodies.BODY, prep_bodies.KIND, bodies.DOCUMENTS, bodies.WITH_HITS
    )
)
@deal.post(
    lambda result: all(r.kind_label and r.documents >= r.with_hits for r in result),
    message="jede Klasse hat ein Label, Treffer sind eine Teilmenge",
)
def body_rows(frame: pl.DataFrame, settings: Bodies) -> tuple[BodyRow, ...]:
    """Die Gremientabelle: Kürzel, Name aus den Settings, Klasse, Dokumente, Lokalität.

    Die Namen kommen aus ``[bodies]`` (Entscheidung 9); ein Kürzel ohne gesicherten Namen steht
    ohne, die Vorlage zeigt dann das Kürzel (``BodyRow.label``). Sortiert nach Klasse in der
    Reihenfolge von ``KINDS``, darin nach Dokumenten absteigend.
    """
    rules = BodyRules.from_settings(settings)
    order = {kind: i for i, kind in enumerate(prep_bodies.KINDS)}
    rows = [
        BodyRow(
            code=str(r[prep_bodies.BODY]),
            name=rules.name_of(
                prep_bodies.BodyRef(
                    str(r[prep_bodies.KIND]),
                    str(r[prep_bodies.BODY]),
                    None
                    if r[prep_bodies.CITY_DISTRICT] is None
                    else int(r[prep_bodies.CITY_DISTRICT]),
                )
            ),
            kind=str(r[prep_bodies.KIND]),
            kind_label=prep_bodies.KIND_LABELS[str(r[prep_bodies.KIND])],
            city_district=(
                None if r[prep_bodies.CITY_DISTRICT] is None else int(r[prep_bodies.CITY_DISTRICT])
            ),
            documents=int(r[bodies.DOCUMENTS]),
            with_hits=int(r[bodies.WITH_HITS]),
            local_share=(None if r[bodies.LOCAL_SHARE] is None else float(r[bodies.LOCAL_SHARE])),
        )
        for r in frame.iter_rows(named=True)
    ]
    return tuple(sorted(rows, key=lambda r: (order[r.kind], -r.documents, r.code)))


def _kind_shares_add_up(result: BodyFigures) -> bool:
    expected = 1.0 if result.documents else 0.0
    total = sum(share for _, _, _, share in result.by_kind)
    counted = sum(count for _, _, count, _ in result.by_kind)
    return (
        abs(total - expected) <= 1e-9
        and counted == result.documents
        and 0.0 <= result.unknown_share <= 1.0
    )


@deal.post(
    _kind_shares_add_up, message="die Klassen zerlegen die Dokumente, Anteile summieren zu 1"
)
def body_figures(
    rows: Sequence[BodyRow], districts: Sequence[DistrictRow], settings: Bodies
) -> BodyFigures:
    """Dokumente je Klasse mit Anteil, Anteil „unbekannt", Treffer und Stand der Namen."""
    documents = sum(r.documents for r in rows)
    per_kind = {kind: 0 for kind in prep_bodies.KINDS}
    for row in rows:
        per_kind[row.kind] += row.documents
    by_kind = tuple(
        (kind, prep_bodies.KIND_LABELS[kind], count, count / documents if documents else 0.0)
        for kind, count in per_kind.items()
    )
    own = sum(d.bodies.own for d in districts if d.bodies)
    return BodyFigures(
        documents=documents,
        by_kind=by_kind,
        unknown_share=per_kind[prep_bodies.UNKNOWN] / documents if documents else 0.0,
        bodies=len(rows),
        without_name=sum(1 for r in rows if not r.name),
        hits=sum(d.hits for d in districts),
        own_hits=own,
        names_as_of=settings.names_as_of,
    )


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


# --- Option 06: die Zahlen des Abschnitts „Was ändert die Gewichtung?" -------------------------

LEVEL = 0.05  # Signifikanzniveau, über das der Abschnitt zählt; wie Tabelle 5 der Arbeit
# Die Spalten von ``themen.parquet``. Sie stehen hier als Literale und nicht als Import, weil
# ``analysis/topics.py`` sklearn mitbringt und die Berichtsseite es nicht laden soll; ein Test in
# tests/unit/test_report_model.py hält beide Seiten gleich.
TOPIC = "thema"
WORDS = "woerter"
DOCUMENTS = "dokumente"
_FIXED_LABELS: dict[str, tuple[str, str]] = {
    UNIT: (
        "ohne Gewichtung",
        "jedes Dokument mit mindestens einem Treffer zählt 1 – die Trefferquote der Arbeit",
    ),
    BY_DISTRICTS: (
        "Spezifität nach Wahlbezirken",
        "ein Begriff, den n Wörterbücher führen, zählt für jeden davon 1/n",
    ),
    BY_IDF: (
        "Spezifität nach Dokumenthäufigkeit",
        "ein Begriff in df von N Dokumenten zählt (ln N − ln df) / ln N: je häufiger, je weniger",
    ),
}


def variant_labels(weights: Weights) -> dict[str, tuple[str, str]]:
    """Beschriftung und Formel je Variante; die Regelsätze bringen ihre Beschriftung mit.

    Nichts davon steht in den Daten: die festen Varianten sind im Code benannt, die Regelsätze in
    den Settings (``[[weights.paper_type]] label``), und die Kombination zählt ihre Faktoren auf.
    """
    labels = dict(_FIXED_LABELS)
    for rule_set in weights.paper_type:
        rules = "; ".join(
            f"Dokumentarten nach dem Muster {rule.pattern} zählen {format_de(rule.weight, 2)}"
            for rule in rule_set.rules
        )
        default = f"alle anderen {format_de(rule_set.default, 2)}"
        labels[rule_set.name] = (rule_set.label, f"{rules}, {default}" if rules else default)
    if weights.combined:
        named = ", ".join(labels.get(f, (f, ""))[0] for f in weights.combined)
        labels[COMBINED] = ("kombiniert", f"Produkt der Faktoren: {named}")
    return labels


def _variant_frame(weighted: pl.DataFrame, results: pl.DataFrame, name: str) -> pl.DataFrame:
    return weighted.filter(pl.col(VARIANT) == name).join(
        results.select(DISTRICT, TURNOUT, RATE), on=DISTRICT, how="inner"
    )


def _ordered_variants(weighted: pl.DataFrame, weights: Weights) -> list[str]:
    """Die Reihenfolge der Seite: feste Varianten, Regelsätze, Kombination, dann die Themen."""
    present = set(weighted.get_column(VARIANT).unique().to_list())
    wanted = [UNIT, BY_DISTRICTS, BY_IDF, *(r.name for r in weights.paper_type), COMBINED]
    topics = sorted(name for name in present if name.startswith(TOPIC_PREFIX))
    return [name for name in wanted if name in present] + topics


def _rows_match_the_file(
    weighted: pl.DataFrame,
    results: pl.DataFrame,
    weights: Weights,
    exclude: Sequence[int] = (),
    result: tuple[SensitivityRow, ...] | None = None,
) -> bool:
    assert result is not None
    names = [row.name for row in result]
    topics = [row.topic for row in result if row.topic is not None]
    return (
        set(names) == set(weighted.get_column(VARIANT).unique().to_list())
        and len(names) == len(set(names))
        and names[0] == UNIT
        and result[0].rho in (None, 1.0)
        and topics == sorted(topics)
    )


@deal.pre(
    lambda weighted, results, weights, exclude=(): (
        has_columns(weighted, DISTRICT, VARIANT, WEIGHTED_HITS, WEIGHTED_RATE)
        and has_columns(results, DISTRICT, TURNOUT, RATE)
    )
)
@deal.ensure(
    _rows_match_the_file, message="eine Zeile je Variante, einheit zuerst, Themen in Folge"
)
def sensitivity_rows(
    weighted: pl.DataFrame,
    results: pl.DataFrame,
    weights: Weights,
    exclude: Sequence[int] = (),
) -> tuple[SensitivityRow, ...]:
    """Je Variante beide Regressionen und die Rangkorrelation zur ungewichteten Quote."""
    labels = variant_labels(weights)
    rows: list[SensitivityRow] = []
    for name in _ordered_variants(weighted, weights):
        frame = _variant_frame(weighted, results, name)
        try:
            pair: RegressionPair | None = regression_pair(frame, exclude, x=WEIGHTED_RATE)
        except EmptyResultError:
            # Eine Variante ohne Streuung (alle Quoten gleich, etwa ein Thema ohne Treffer) hat
            # keine Regression; die Zeile zeigt „—", das ist kein Fehler.
            pair = None
        label, description = labels.get(name, (name, ""))
        number = int(name.removeprefix(TOPIC_PREFIX)) if name.startswith(TOPIC_PREFIX) else None
        rows.append(
            SensitivityRow(
                name=name,
                label=label,
                description=description,
                total=float(frame.get_column(WEIGHTED_HITS).sum()),
                pair=pair,
                rho=spearman(frame, WEIGHTED_RATE, RATE),
                topic=number,
            )
        )
    return tuple(rows)


@deal.pre(lambda topics, weighted: has_columns(topics, TOPIC, WORDS, DOCUMENTS))
@deal.post(
    lambda result: [row.index for row in result] == sorted(row.index for row in result),
    message="Themen in Nummernreihenfolge",
)
def topic_rows(topics: pl.DataFrame, weighted: pl.DataFrame) -> tuple[TopicRow, ...]:
    """Je Thema die stärksten Wörter, die dominierten Dokumente und der Anteil an den Treffern."""
    counted = float(weighted.filter(pl.col(VARIANT) == UNIT).get_column(WEIGHTED_HITS).sum() or 0.0)
    totals = dict(
        weighted.filter(pl.col(VARIANT).str.starts_with(TOPIC_PREFIX))
        .group_by(VARIANT)
        .agg(pl.col(WEIGHTED_HITS).sum())
        .iter_rows()
    )
    return tuple(
        TopicRow(
            index=int(row[TOPIC]),
            words=tuple(row[WORDS]),
            documents=int(row[DOCUMENTS]),
            hits_share=(
                totals.get(topic_variant(int(row[TOPIC])), 0.0) / counted if counted > 0 else 0.0
            ),
        )
        for row in topics.sort(TOPIC).iter_rows(named=True)
    )


def _example(frame: pl.DataFrame, by: str, then: str) -> TermExample | None:
    """Der Begriff mit dem größten Wert in ``by``; bei Gleichstand entscheidet ``then``, dann der Name."""
    if frame.is_empty():
        return None
    row = frame.sort([by, then, TERM], descending=[True, True, False]).row(0, named=True)
    return TermExample(str(row[TERM]), int(row[HITS]), int(row[N_DISTRICTS]))


def build_sensitivity(layout: Layout, settings: Settings, results: pl.DataFrame) -> Sensitivity:
    """Der ganze Abschnitt aus ``wahlbezirke_gewichtet.parquet`` und (wenn da) ``themen.parquet``."""
    weighted = pl.read_parquet(layout.weighted)
    rows = sensitivity_rows(
        weighted, results, settings.weights, settings.analysis.exclude_districts
    )
    topics = topic_rows(pl.read_parquet(layout.topics), weighted) if layout.topics.exists() else ()
    terms = (
        pl.read_parquet(layout.term_weights, columns=[TERM, N_DISTRICTS, HITS])
        if layout.term_weights.exists()
        else pl.DataFrame(schema={TERM: pl.String, N_DISTRICTS: pl.Int64, HITS: pl.Int64})
    )
    return Sensitivity(
        rows=rows,
        topics=topics,
        excluded=tuple(settings.analysis.exclude_districts),
        significant_all=sum(1 for r in rows if r.pair and r.pair.all.p < LEVEL),
        significant_without=sum(
            1 for r in rows if r.pair and r.pair.without and r.pair.without.p < LEVEL
        ),
        strongest=_example(terms, HITS, N_DISTRICTS),
        widest=_example(terms, N_DISTRICTS, HITS),
        level=LEVEL,
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
    names = district_names(precincts)
    # Option 05: die drei Tabellen der Gremien; die Namen kommen aus den Settings
    district_bodies = pl.read_parquet(layout.district_bodies)
    rows = with_bodies(
        district_rows(results, counts, names, settings.columns.results, hidden),
        district_bodies,
    )
    table = body_rows(pl.read_parquet(layout.bodies_table), settings.bodies)
    return ReportModel(
        generated_at=now,
        version=__version__,
        commit=commit,
        stand=data_stand(layout, settings),
        figures=key_figures(results, dictionary, layout.corpus, len(precincts)),
        districts=rows,
        top_terms=top_terms_city(counts, hidden),
        hidden_terms=hidden,
        regression=regression_pair(results, settings.analysis.exclude_districts),
        downloads=tuple(downloads),
        columns=column_docs(layout),
        working_crs=settings.geo.working_crs,
        search=search_entries(
            dictionary,
            index,
            pl.read_parquet(layout.streets_by_district),
            pl.read_parquet(layout.pois_table),
            results,
            names,
            hidden,
        ),
        bodies=table,
        body_figures=body_figures(table, rows, settings.bodies),
        body_regression=_body_regression(district_bodies, results, settings),
        # Option 06: ohne die lange Tabelle gibt es den Abschnitt nicht
        sensitivity=(
            build_sensitivity(layout, settings, results) if layout.weighted.exists() else None
        ),
    )


def _body_regression(
    district_bodies: pl.DataFrame, results: pl.DataFrame, settings: Settings
) -> RegressionPair | None:
    """Wahlbeteiligung gegen die Quote der eigenen Bezirksvertretung; None ohne Streuung (Mini)."""
    frame = bodies.regression_frame(district_bodies, results)
    try:
        return regression_pair(frame, settings.analysis.exclude_districts, x=bodies.OWN_RATE)
    except EmptyResultError:
        return None
