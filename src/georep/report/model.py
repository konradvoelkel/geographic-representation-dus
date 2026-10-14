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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import deal
import polars as pl

from georep import __version__
from georep.analysis import bodies, scaling
from georep.analysis import parties as parties_mod
from georep.analysis.hits import DISTRICT, RATE, TERMS, Citywide, citywide_terms
from georep.analysis.ols import ALL, CONSTANT, MAIN_MODEL, model_terms, sample_label
from georep.analysis.parties import (
    KLASSEN_SPALTEN,
    PARTEI,
    PARTEIEN,
    QUELLE,
    PartyCorrelation,
    originator_figures,
    party_correlations,
)
from georep.analysis.periods import (
    D_RATE,
    D_TURNOUT,
    NEW,
    OLD,
    PERIOD_NEW,
    PERIOD_OLD,
    delta_regression,
)
from georep.analysis.regression import RegressionPair, RegressionResult, regression_pair, spearman
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

# ``crosswalk.UNIT`` ist die Spalte der Raumeinheit (Option 03), ``weights.UNIT`` der Name der
# Einheitsvariante (Option 06); beide heißen „einheit", meinen aber Verschiedenes.
from georep.crosswalk import UNIT as CROSSWALK_UNIT
from georep.errors import EmptyResultError, MissingInputError, SchemaError
from georep.geo import Precinct, read_canonical_precincts
from georep.layout import Layout
from georep.prep import bodies as prep_bodies
from georep.prep.bodies import BodyRules
from georep.prep.context import read_indicators
from georep.prep.streets import Agreement, directory_agreement
from georep.prep.voters import ELIGIBLE_TOTAL, PRECINCT, TURNOUT, VOTERS
from georep.report.literature import literature
from georep.report.search import SearchEntry, search_entries
from georep.report.tables import GEOJSON_COLUMNS, GEOJSON_TABLE, PublishedTable, published
from georep.search.dictionary import all_terms
from georep.search.index import HITS, PAPER_IDS, TERM
from georep.settings import (
    RATE_TERM,
    Bodies,
    City,
    ContextDataset,
    ContextSettings,
    Diverging,
    LiteratureEntry,
    Party,
    ReportSource,
    Settings,
    Weights,
)

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
class DistrictMetrics:
    """Dieselben Treffer in drei weiteren Lesarten (Punkt 46, ``analysis.scaling``)."""

    per_term: float  # Treffer je Begriff im Wörterbuch
    per_1000: float  # Treffer je 1000 Wahlberechtigte: die Trefferquote mit einem Faktor
    city_mean: float  # ungewichtetes Mittel der Trefferquoten aller Wahlbezirke
    deviation: float  # Quote geteilt durch Stadtmittel, minus 1; 0 heißt genau im Mittel


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
    metrics: DistrictMetrics | None = None  # Punkt 46; None heißt: Schritt ``metrics`` lief nicht


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
    # Punkt 46: die zweite Kennzahl des Methodik-Reviews; 0,0 heißt „Schritt ``metrics`` lief nicht"
    per_term_median: float = 0.0
    per_term_min: float = 0.0
    per_term_max: float = 0.0

    @property
    def documents_without_text(self) -> int:
        """Dokumente ohne extrahierten Text; in der laufenden Periode wächst das zwischen zwei Läufen."""
        return self.documents - self.documents_with_text

    @property
    def hit_share_of_text(self) -> float | None:
        """Anteil der Dokumente mit Treffer an denen **mit Text**; None, wenn es keinen gibt.

        Review 2026-10-14: der Anteil an allen Dokumenten verwässert, wo das
        Ratsinformationssystem Hauptdateien nicht ausliefert -- in Mönchengladbach sind 489 von
        2 895 Dokumenten 16,9 %, von den 650 mit Text aber 75,2 %. Durchsucht wurde die zweite
        Menge, und nur über die sagt die Zahl etwas.
        """
        return self.documents_hit / self.documents_with_text if self.documents_with_text else None


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
    # Option 07: wann die Metadaten und die PDFs zuletzt abgerufen wurden (Stamps der Netzschritte)
    # und das Datum des neuesten Dokuments im Korpus; None, wenn der Schritt nie lief.
    papers_fetched: dt.date | None = None
    pdfs_fetched: dt.date | None = None
    newest_document: dt.date | None = None


@dataclass(frozen=True)
class MonthRow:
    """Eine Zeile der Monatsreihe; ``month`` ist leer für Dokumente ohne Datum (Option 07)."""

    month: dt.date | None
    documents: int
    with_text: int
    with_hits: int


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
    # Punkt 58: woher das Gremium kommt, (Quelle, Label, Dokumente, Anteil) in der Reihenfolge von
    # ``prep.bodies.SOURCES``, dazu die drei Zahlen über das Verhältnis der beiden Quellen. Ohne
    # den Schritt ``bodies`` neu gerechnet gibt es sie nicht, und die Vorlage lässt den Satz weg.
    by_source: tuple[tuple[str, str, int, float], ...] = ()
    confirmed: int = 0  # Nummer und Beratungsfolge nennen dasselbe Gremium
    conflicting: int = 0  # beide nennen eines, und es ist nicht dasselbe; die Nummer bleibt
    ambiguous: int = 0  # ohne Gremium aus der Nummer, und die Folge nennt mehr als eines

    def documents_from(self, *sources: str) -> int:
        """Dokumente, deren Gremium aus einer dieser Quellen kommt (``prep.bodies.SOURCES``)."""
        return sum(count for source, _, count, _ in self.by_source if source in sources)

    @property
    def from_number(self) -> int:
        """Aus der Drucksachennummer, einschließlich der älteren Nummernform (Punkt 57)."""
        return self.documents_from(prep_bodies.FROM_NUMBER, prep_bodies.FROM_ALIAS)

    @property
    def from_consultation(self) -> int:
        return self.documents_from(prep_bodies.FROM_CONSULTATION)


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
    # Punkt 45: das Kürzel des Ausschusses, aus dem das Thema gesät ist, und sein Name aus dem
    # Profil; beide leer bei einem freien Thema, der Name leer, wenn er nicht gesichert ist.
    body: str = ""
    name: str = ""

    @property
    def label(self) -> str:
        """Was auf der Seite steht: der Name, sonst das Kürzel, sonst nichts (freies Thema)."""
        return self.name or self.body


@dataclass(frozen=True)
class AssignmentRow:
    """Punkt 45: eine Zeile der Tabelle „Dokumente je passendem Ausschuss"."""

    code: str  # Kürzel; leer ist die Restklasse
    name: str  # Name aus ``[bodies]``; leer, wenn er nicht gesichert ist
    documents: int
    share: float  # Anteil an allen Dokumenten mit Text
    without: int  # davon solche ohne Ausschussberatung (nur Rat, Bezirksvertretung, Beirat)
    median: float | None  # Median der Wahrscheinlichkeit; None in der Restklasse

    @property
    def label(self) -> str:
        """Der Name, sonst das Kürzel; die Restklasse trägt beides nicht (die Vorlage benennt sie)."""
        return self.name or self.code


@dataclass(frozen=True)
class TermExample:
    """Ein Begriff als Beispiel im Text des Abschnitts; aus ``gewichte_begriffe.parquet``."""

    term: str
    hits: int
    districts: int


@dataclass(frozen=True)
class CitywideSection:
    """Regel 2: die Begriffe über der Schwelle der Dokumenthäufigkeit (decisions.md, Punkt 44).

    ``basis`` nennt die Schwelle in Worten. Die Begriffe zählen weiter mit; die Liste macht nur
    sichtbar, dass es sie gibt. Ohne Schwelle oder ohne einen Begriff darüber gibt es den
    Abschnitt nicht, dann steht im Modell ``None``.
    """

    basis: str
    rows: tuple[TermRow, ...]


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


# --- Option 03: Kontrollvariablen und abgeleitete Daten -----------------------------------------


@dataclass(frozen=True)
class ControlTerm:
    """Eine Zeile von Tabelle 6: ein Term eines Modells."""

    term: str  # Variablenname, ``(Konstante)`` für den Achsenabschnitt
    label: str  # Anzeigename aus den Settings
    unit: str
    coefficient: float
    stderr: float
    p: float
    beta: float | None
    vif: float | None


@dataclass(frozen=True)
class ControlModel:
    name: str  # A, B, C
    terms: tuple[ControlTerm, ...]
    n: int
    k: int
    r2: float
    r2_adj: float
    f_p: float


@dataclass(frozen=True)
class SingleAddition:
    """Eine Zeile von Tabelle 6b: die Trefferquote, wenn genau eine Variable dazukommt."""

    variable: str
    label: str
    unit: str
    coefficient: float
    stderr: float
    p: float
    r2_adj: float


@dataclass(frozen=True)
class ControlsSection:
    models: tuple[ControlModel, ...]  # nur die geschätzten; auf einer kleinen Stichprobe nur A
    singles: tuple[SingleAddition, ...]
    main: str  # Name des Hauptmodells, aus dem die Plots kommen
    rate_label: str
    units_label: str  # Name der Raumeinheit, aus den Settings
    units: int  # Einheiten im Crosswalk
    stand: dt.date  # Datenstand der Fremddaten
    excluded: tuple[int, ...]  # Ausreißer der zweiten Stichprobe
    rate_without: ControlTerm | None  # die Trefferquote im Hauptmodell ohne die Ausreißer
    verdict: str  # ein Satz, der aus den Zahlen folgt
    missing: tuple[str, ...]  # Modelle, die zu wenige Wahlbezirke hatten


@dataclass(frozen=True)
class DerivedVariable:
    name: str
    label: str
    unit: str
    definition: str  # aus der Erläuterungsdatei der Quelle
    source: str
    transform: str


@dataclass(frozen=True)
class DerivedData:
    """Abschnitt „Abgeleitete Daten": was aus den Fremddaten wurde, mit Lizenz und Stand."""

    title: str
    url: str
    publisher: str
    license: str
    license_url: str
    stand: dt.date
    fetched: dt.date
    attribution: str
    units_label: str
    units: int
    districts: int
    variables: tuple[DerivedVariable, ...]


@dataclass(frozen=True)
class PartyRow:
    """Eine Zeile der Parteitabelle: Umfang und der Abgleich mit den Hochburgen."""

    key: str
    label: str
    short: str  # Kürzel für den engen Spaltenkopf der Bezirkstabelle
    documents: int  # alle Dokumente der Partei in der Wahlperiode
    hits: int  # Summe der Treffer über die Wahlbezirke (Mehrfachnennung je Bezirk)
    alone: int  # davon Dokumente, deren einziger Urheber die Partei ist
    districts_hit: int  # Wahlbezirke mit mindestens einem Treffer
    n: int  # Wahlbezirke, in denen die Partei angetreten ist
    r: float | None  # Pearson zwischen anteil_dokumente und stimmenanteil
    p: float | None
    rho: float | None  # Spearman, nicht auf der Seite, aber in der Tabelle zum Download
    # Punkt 46: die drei Varianten als Mittel über die Wahlbezirke. Das Mittel der 41 Zahlen, die
    # die Karte zeigt, nicht das Verhältnis der Mittelwerte: die Spalte soll die Karte
    # zusammenfassen (docs/skalierung-2026-10.md, § 8, Annahme 3).
    mean_share: float = 0.0
    mean_deviation: float = 0.0
    mean_ratio: float = 0.0


@dataclass(frozen=True)
class PartyCell:
    """Eine schattierte Zelle: Anteil der Parteidokumente mit Treffer in diesem Wahlbezirk."""

    district: int
    party: str
    hits: int
    share: float  # anteil_dokumente
    vote_share: float
    ran: bool
    klass: int  # Quantilklasse je Partei, 0 bis 4
    # Punkt 46: dieselbe Zelle relativ zum Mittel aller Parteien dieses Wahlbezirks. Anders als
    # ``klass`` sind die beiden Klassen gemeinsam gerechnet: Abweichung und Verhältnis sind über
    # die Parteien vergleichbar, der Anteil ist es nicht.
    deviation: float = 0.0  # Anteil minus Mittel; mal 100 sind es Prozentpunkte
    ratio: float = 0.0  # Anteil geteilt durch Mittel; 1 heißt genau im Mittel
    klass_deviation: int = 0
    klass_ratio: int = 0


@dataclass(frozen=True)
class OriginatorRow:
    district: int
    name: str
    hits: int
    verwaltung: int
    fraktion: int
    person: int
    eingabe: int
    unbekannt: int


@dataclass(frozen=True)
class OriginatorFigures:
    """Die Deckung der Zuordnung über alle Dokumente, für den Text des Abschnitts."""

    documents: int
    verwaltung: int
    fraktion: int
    person: int
    eingabe: int
    unbekannt: int
    with_two_parties: int
    from_oparl: int  # Dokumente, deren Urheber der Server geliefert hat (Stand 2026-10-09: null)

    @property
    def classified(self) -> int:
        return self.documents - self.unbekannt

    @property
    def coverage(self) -> float:
        return self.classified / self.documents if self.documents else 0.0


# --- Option 02: die Periode und, wenn eingeschaltet, der Vergleich mit einer zweiten -----------


@dataclass(frozen=True)
class PeriodInfo:
    """Welche Wahlperiode die Seite zeigt; alle Periodentexte der Vorlage kommen hieraus."""

    profile: str  # Ordnername des Profils; "" ist die Hauptperiode
    title: str  # „Wahlperiode 2020 bis 2025", aus ``period.title``
    start: dt.date
    end: dt.date | None
    election: dt.date  # Wahltag, dessen Ergebnis Nenner und Zuschnitt liefert
    converted: bool  # die Wahlzahlen sind auf den Zuschnitt dieser Auswertung umgerechnet

    @property
    def years(self) -> str:
        """``2020 to 2025`` beziehungsweise ``2025 onwards``: für die englische Kurzfassung."""
        return f"{self.start.year} to {self.end.year}" if self.end else f"{self.start.year} onwards"


@dataclass(frozen=True)
class PeriodRow:
    """Ein Wahlbezirk in beiden Perioden, mit den beiden Änderungen."""

    id: int
    name: str
    hits_old: int
    hits_new: int
    rate_old: float
    rate_new: float
    turnout_old: float
    turnout_new: float
    d_rate: float
    d_turnout: float


@dataclass(frozen=True)
class PeriodComparison:
    """Der Abschnitt „Zwei Wahlperioden": Zeilen, Regressionen und die beiden Sensitivitätszahlen."""

    previous: str  # Name der älteren Periode
    current: str
    rows: tuple[PeriodRow, ...]
    districts: int  # Wahlbezirke der Auswertung; weniger Zeilen heißt, einer fehlt in einer Periode
    regression: RegressionResult  # der Änderungen gegeneinander
    previous_pair: RegressionPair  # Tabelle 5 der älteren Periode
    precincts: int  # Stimmbezirke des alten Zuschnitts
    split: int  # davon auf mehr als einen Zielbezirk verteilt
    min_coverage: float  # kleinste Abdeckung einer Quellfläche durch die Zielbezirke
    subpage: str  # Pfad der Unterseite der älteren Periode, relativ zur Hauptseite

    @property
    def split_share(self) -> float:
        return self.split / self.precincts if self.precincts else 0.0


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
    regression: RegressionPair | None  # None: keine Wahlbeteiligung zur Periode (Option 07)
    downloads: tuple[Download, ...]
    columns: tuple[ColumnDoc, ...]
    working_crs: str
    # Option 02: die Periode dieser Seite; Pflichtfeld, darum vor den Feldern mit Default
    period: PeriodInfo
    # Option 08: die Vorschläge der Suche; leer heißt „kein Abschnitt suche" in der Vorlage.
    search: tuple[SearchEntry, ...] = ()
    # Option 05: ohne die Tabellen der Gremien bleibt der Abschnitt weg ({% if model.bodies %})
    bodies: tuple[BodyRow, ...] = ()
    body_figures: BodyFigures | None = None
    body_regression: RegressionPair | None = None
    # Regel 2 (decisions.md, Punkt 44): die stadtweiten Begriffe; None heißt „keine Schwelle".
    citywide: CitywideSection | None = None
    # Regel 1 (ebenda): ob Einrichtungen mit Stadtnamen aus dem Wörterbuch gefallen sind. Die
    # Vorlage nennt die Regel nur dann in „Methode und Grenzen".
    city_facilities: bool = False
    # Punkt 45: Dokumente je passendem Ausschuss; leer heißt „kein Klassifikator, keine Tabelle"
    assignment: tuple[AssignmentRow, ...] = ()
    assignment_threshold: float = 0.0  # ``classify.min_probability``: darunter die Restklasse
    sensitivity: Sensitivity | None = None  # Option 06; None = ohne Abschnitt
    controls: ControlsSection | None = None  # Option 03; None ohne Kontextdaten
    derived: DerivedData | None = None  # Option 03

    # Option 04: der Abschnitt „Urheber und Parteien"; ohne den Schritt ``parties`` bleibt er leer
    # und die Vorlage lässt ihn weg (``{% if model.parties %}``).
    parties: tuple[PartyRow, ...] = ()
    party_cells: tuple[PartyCell, ...] = ()
    originators: tuple[OriginatorRow, ...] = ()
    originator_figures: OriginatorFigures | None = None

    def cells_for(self, district: int) -> tuple[PartyCell, ...]:
        """Die Zellen eines Wahlbezirks in der Spaltenreihenfolge der Parteitabelle.

        ``party_cells`` ist nach (Partei, Bezirk) sortiert, also alphabetisch nach Schlüssel;
        die Spalten der Tabelle folgen den Settings. Ohne diese Umsortierung stünden die Zahlen
        unter den falschen Köpfen.
        """
        found = {c.party: c for c in self.party_cells if c.district == district}
        return tuple(found[p.key] for p in self.parties if p.key in found)

    # Option 02: der optionale Vergleich mit einer zweiten Periode
    comparison: PeriodComparison | None = None
    # Option 01: alles, was die Vorlage an Worten braucht und nicht aus den Daten kommt. Die
    # Felder stehen am Ende und haben Vorgaben, damit ein Merge mechanisch bleibt
    # (docs/plans/00-synergien.md, § 2); ``build_report_model`` füllt sie immer.
    city: City | None = None
    sources: tuple[ReportSource, ...] = ()
    # Punkt 47: die Literaturübersicht; leer heißt „kein Abschnitt Literatur" in der Vorlage. Die
    # Einträge kommen aus ``report/literatur.toml`` und aus ``[[report.literature]]`` des Profils.
    literature: tuple[LiteratureEntry, ...] = ()
    ris_url: str = ""  # Ratsinformationssystem; die Methode verlinkt es
    marker: str = ""  # search.text_split_marker; die Methode nennt ihn
    notes: tuple[str, ...] = ()  # stadtspezifische Sätze für „Methode und Grenzen"
    agreement: Agreement | None = None  # Flächen gegen das Straßenverzeichnis der Wahl
    data_note: str = ""  # Herkunft von Straßen und Orten ohne eigenen Abruf
    # Punkt 46: dieselbe Regression mit x = Treffer je Begriff im Wörterbuch; None ohne den
    # Schritt ``metrics``. Tabelle 5 (``regression``) bleibt unberührt.
    per_term_regression: RegressionPair | None = None
    # Punkt 46: die gemessene Verzerrung für „Methode und Grenzen"; None ohne Streuung
    bias: scaling.DictionaryBias | None = None
    # Option 07
    timeline: tuple[MonthRow, ...] = ()
    monitoring_url: str = ""  # relativer Link auf die Seite der laufenden Periode; leer = keiner
    # Review 2026-10-14: der Rückweg einer Unterseite. Eine Periode rechnet in ihrem eigenen
    # Ordner unter der Stadt, und ``pages.yml`` wie ``deploy/bin/georep-monitor.sh`` legen ihre
    # Seite nach ``<stadt>/site/<profil>/``; von dort führt ``../`` zur Hauptperiode. Leer heißt
    # „diese Seite ist die Hauptseite ihrer Stadt". Relativ und darum nicht in der Allowlist der
    # externen Links (die prüft nur ``http(s)://``).
    parent_url: str = ""
    # Punkt 48: so viele Zeilen zeigt eine lange Tabelle; 0 klappt nichts ein. Die Vorlage baut
    # daraus die CSS-Regel der Vorschau und die Schaltfläche (docs/seitengroesse-2026-10.md, § 3).
    preview_rows: int = 3


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


def _table_docs(table: PublishedTable, path: Path, settings: Settings) -> list[ColumnDoc]:
    """Spalten einer Parquet-Datei mit ihrer Bedeutung aus dem Register; beide Richtungen müssen passen."""
    schema = pl.read_parquet_schema(path)
    known = table.column_docs(settings)
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


def column_docs(layout: Layout, settings: Settings) -> tuple[ColumnDoc, ...]:
    """Spaltenschema aller veröffentlichten Tabellen und des GeoJSON (``report.tables``).

    ``settings`` braucht zweierlei: wer seine Spalten daraus ableitet (Option 03: eine Spalte
    je Kontrollvariable), und das Register, um Tabellen abgeschalteter Stufen auszulassen
    (Option 06).
    """
    docs: list[ColumnDoc] = []
    for table in published(layout, settings):
        docs.extend(_table_docs(table, table.path(layout), settings))
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
    lambda results, counts, names, hidden: (
        has_columns(results, DISTRICT, HITS, RATE, TURNOUT, ELIGIBLE_TOTAL, VOTERS)
        and has_columns(counts, DISTRICT, TERM, HITS, "districts")
    )
)
@deal.ensure(
    lambda results, counts, names, hidden, result: len(result) == results.height,
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
                eligible=int(row[ELIGIBLE_TOTAL]),
                voters=int(row[VOTERS]),
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


def _every_row_has_metrics(
    rows: Sequence[DistrictRow], frame: pl.DataFrame, result: tuple[DistrictRow, ...] = ()
) -> bool:
    return all(r.metrics is not None and r.metrics.per_term >= 0.0 for r in result)


@deal.pre(
    lambda rows, frame: has_columns(
        frame, DISTRICT, scaling.PER_TERM, scaling.PER_1000, scaling.CITY_MEAN, scaling.DEVIATION
    ),
    message="Kennzahlen je Wahlbezirk aus wahlbezirke_kennzahlen.parquet",
)
@deal.ensure(_every_row_has_metrics, message="jede Zeile mit Kennzahlen")
@deal.raises(SchemaError)
def with_metrics(rows: Sequence[DistrictRow], frame: pl.DataFrame) -> tuple[DistrictRow, ...]:
    """Dieselben Zeilen mit gefülltem ``metrics``; ein fehlender Wahlbezirk ist ein ``SchemaError``."""
    by_district = {int(r[DISTRICT]): r for r in frame.iter_rows(named=True)}
    missing = sorted(r.id for r in rows if r.id not in by_district)
    if missing:
        raise SchemaError(f"Wahlbezirke ohne normierte Kennzahlen: {missing}")
    return tuple(
        replace(
            row,
            metrics=DistrictMetrics(
                per_term=float(by_district[row.id][scaling.PER_TERM]),
                per_1000=float(by_district[row.id][scaling.PER_1000]),
                city_mean=float(by_district[row.id][scaling.CITY_MEAN]),
                deviation=float(by_district[row.id][scaling.DEVIATION]),
            ),
        )
        for row in rows
    )


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


def _kinds_are_known(
    rows: Sequence[BodyRow],
    districts: Sequence[DistrictRow],
    settings: Bodies,
    sources: prep_bodies.SourceCounts | None = None,
) -> bool:
    """Jede Zeile trägt eine bekannte Klasse und nicht negative, geordnete Zahlen.

    Die Annahme stand bis zum 2026-10-13 nur im Typkommentar von ``BodyRow.kind``, und crosshair
    hat sie als ``KeyError`` gefunden: ``per_kind[row.kind] += …`` fliegt bei jeder anderen Klasse
    mit einem leeren Fehlertext, statt zu sagen, wer sie geliefert hat. Als Vorbedingung nennt die
    Meldung den Aufrufer (`docs/decisions.md`, Punkt 53). Dasselbe gilt für
    ``0 <= with_hits <= documents``: mit einer negativen Dokumentzahl lieferte die Funktion einen
    Anteil von 2,0 und einen „unbekannt"-Anteil von -1,0, und die Nachbedingung brach -- auch das
    ein crosshair-Gegenbeispiel vom 2026-10-13.
    """
    return all(
        row.kind in prep_bodies.KINDS and 0 <= row.with_hits <= row.documents for row in rows
    )


@deal.pre(_kinds_are_known, message="jede Gremienzeile trägt eine Klasse aus prep.bodies.KINDS")
@deal.post(
    _kind_shares_add_up, message="die Klassen zerlegen die Dokumente, Anteile summieren zu 1"
)
def body_figures(
    rows: Sequence[BodyRow],
    districts: Sequence[DistrictRow],
    settings: Bodies,
    sources: prep_bodies.SourceCounts | None = None,
) -> BodyFigures:
    """Dokumente je Klasse mit Anteil, Anteil „unbekannt", Treffer und Stand der Namen.

    ``sources`` sind die Zahlen aus ``papers_gremien.parquet`` (Punkt 58): woher das Gremium
    kommt, und wie oft sich die beiden Quellen bestätigen, widersprechen oder nichts entscheiden.
    """
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
        by_source=(
            ()
            if sources is None
            else tuple(
                (
                    source,
                    prep_bodies.SOURCE_LABELS[source],
                    count,
                    count / sources.documents if sources.documents else 0.0,
                )
                for source, count in sources.per_source
            )
        ),
        confirmed=0 if sources is None else sources.confirmed,
        conflicting=0 if sources is None else sources.conflicting,
        ambiguous=0 if sources is None else sources.ambiguous,
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


@deal.pre(lambda counts, found: has_columns(counts, TERM, HITS, "districts"))
@deal.post(lambda result: result is None or (bool(result.basis) and bool(result.rows)))
def citywide_section(counts: pl.DataFrame, found: Citywide) -> CitywideSection | None:
    """Die Zeilen der Liste „stadtweite Begriffe": Begriff, Dokumente, Wahlbezirke.

    ``found`` kommt aus ``citywide_terms`` über den Index; die Wahlbezirke je Begriff stehen in
    ``counts`` (ein Begriff kann in mehreren Wörterbüchern stehen). Ohne Schwelle gibt es keinen
    Abschnitt — und auch keinen, wenn kein Begriff über der Schwelle liegt: „Diese 0 Begriffe …"
    über einer leeren Tabelle wäre eine Behauptung ohne Inhalt.
    """
    if not found.basis:
        return None
    rows = (
        counts.filter(pl.col(TERM).is_in(list(found.terms)))
        .unique(subset=[TERM], keep="first")
        .sort([HITS, TERM], descending=[True, False])
    )
    found_rows = tuple(
        TermRow(r[TERM], int(r[HITS]), tuple(r["districts"])) for r in rows.iter_rows(named=True)
    )
    return CitywideSection(basis=found.basis, rows=found_rows) if found_rows else None


def key_figures(
    results: pl.DataFrame,
    dictionary: pl.DataFrame,
    corpus: Path,
    precincts: int,
    per_term: Sequence[float] = (),
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
        # Punkt 46: leer, solange der Schritt ``metrics`` nicht gelaufen ist
        per_term_median=statistics.median(per_term) if per_term else 0.0,
        per_term_min=min(per_term, default=0.0),
        per_term_max=max(per_term, default=0.0),
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


def newest_document(corpus: Path) -> dt.date | None:
    """Das größte Dokumentdatum im Korpus; None, wenn keines ein Datum hat (Option 07)."""
    value = pl.scan_parquet(corpus).select(pl.col("date").max()).collect().item()
    return value if isinstance(value, dt.date) else None


def month_rows(timeline: Path) -> tuple[MonthRow, ...]:
    """Die Monatsreihe aus ``processed/monatsreihe.parquet`` in Reihenfolge (Option 07)."""
    frame = pl.read_parquet(timeline)
    return tuple(
        MonthRow(row["monat"], int(row["dokumente"]), int(row["mit_text"]), int(row["mit_treffer"]))
        for row in frame.iter_rows(named=True)
    )


def data_stand(layout: Layout, settings: Settings) -> DataStand:
    return DataStand(
        election=settings.period.election_day,
        period_start=settings.period.start,
        period_end=settings.period.end,
        streets_fetched=stamp_written(layout.streets),
        pois_fetched=stamp_written(layout.pois),
        papers_fetched=stamp_written(layout.papers),
        pdfs_fetched=stamp_written(layout.pdf_manifest),
        newest_document=newest_document(layout.corpus),
    )


# --- Option 06: die Zahlen des Abschnitts „Was ändert die Gewichtung?" -------------------------

LEVEL = 0.05  # Signifikanzniveau, über das der Abschnitt zählt; wie Tabelle 5 der Arbeit
# Die Spalten von ``themen.parquet``. Sie stehen hier als Literale und nicht als Import, weil
# ``analysis/topics.py`` sklearn mitbringt und die Berichtsseite es nicht laden soll; ein Test in
# tests/unit/test_report_model.py hält beide Seiten gleich.
TOPIC = "thema"
TOPIC_BODY = "gremium"  # Punkt 45: Kürzel des gesäten Ausschusses, null bei einem freien Thema
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
    """Eine Gewichtungsvariante neben der Wahlbeteiligung, nach Wahlbezirk sortiert.

    Sortiert, weil die Regression darüber läuft: ein Join legt die Zeilenfolge nicht fest, und
    eine Fließkommasumme in anderer Folge gibt ein anderes letztes Bit (2026-10-13).
    """
    return (
        weighted.filter(pl.col(VARIANT) == name)
        .join(results.select(DISTRICT, TURNOUT, RATE), on=DISTRICT, how="inner")
        .sort(DISTRICT)
    )


def _ordered_variants(
    weighted: pl.DataFrame, weights: Weights, with_topics: bool = True
) -> list[str]:
    """Die Reihenfolge der Seite: feste Varianten, Regelsätze, Kombination, dann die Themen.

    Ohne Themenmodell (``topics.k = 0``) bleiben die ``thema_NN``-Zeilen weg, auch wenn eine
    Datei aus einem früheren Lauf sie noch enthält: die Seite zeigt die Konfiguration, nicht den
    Rest eines abgeschalteten Schritts.
    """
    present = set(weighted.get_column(VARIANT).unique().to_list())
    wanted = [UNIT, BY_DISTRICTS, BY_IDF, *(r.name for r in weights.paper_type), COMBINED]
    topics = sorted(name for name in present if name.startswith(TOPIC_PREFIX))
    return [name for name in wanted if name in present] + (topics if with_topics else [])


def _rows_match_the_file(
    weighted: pl.DataFrame,
    results: pl.DataFrame,
    weights: Weights,
    exclude: Sequence[int] = (),
    with_topics: bool = True,
    topic_labels: Mapping[int, str] | None = None,
    result: tuple[SensitivityRow, ...] | None = None,
) -> bool:
    assert result is not None
    names = [row.name for row in result]
    topics = [row.topic for row in result if row.topic is not None]
    in_file = set(weighted.get_column(VARIANT).unique().to_list())
    expected = in_file if with_topics else {n for n in in_file if not n.startswith(TOPIC_PREFIX)}
    return (
        set(names) == expected
        and len(names) == len(set(names))
        # Eine leere Tabelle gibt keine Zeilen; sonst steht die Einheitszeile zuerst.
        and (not names or (names[0] == UNIT and result[0].rho in (None, 1.0)))
        and topics == sorted(topics)
    )


@deal.pre(
    lambda weighted, results, weights, exclude=(), with_topics=True, topic_labels=None: (
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
    with_topics: bool = True,
    topic_labels: Mapping[int, str] | None = None,
) -> tuple[SensitivityRow, ...]:
    """Je Variante beide Regressionen und die Rangkorrelation zur ungewichteten Quote."""
    labels = variant_labels(weights)
    rows: list[SensitivityRow] = []
    for name in _ordered_variants(weighted, weights, with_topics):
        frame = _variant_frame(weighted, results, name)
        try:
            pair: RegressionPair | None = regression_pair(frame, exclude, x=WEIGHTED_RATE)
        except EmptyResultError:
            # Eine Variante ohne Streuung (alle Quoten gleich, etwa ein Thema ohne Treffer) hat
            # keine Regression; die Zeile zeigt „—", das ist kein Fehler.
            pair = None
        label, description = labels.get(name, (name, ""))
        number = int(name.removeprefix(TOPIC_PREFIX)) if name.startswith(TOPIC_PREFIX) else None
        if number is not None:
            # Punkt 45: ein gesätes Thema trägt den Namen seines Ausschusses, ein freies keinen;
            # die Nummer steht in der Vorlage davor, die Formel wiederholt sich nicht je Zeile.
            label, description = (topic_labels or {}).get(number, ""), ""
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


@deal.pre(lambda topics, weighted, names=None: has_columns(topics, TOPIC, WORDS, DOCUMENTS))
@deal.post(
    lambda result: [row.index for row in result] == sorted(row.index for row in result),
    message="Themen in Nummernreihenfolge",
)
def topic_rows(
    topics: pl.DataFrame, weighted: pl.DataFrame, names: Mapping[str, str] | None = None
) -> tuple[TopicRow, ...]:
    """Je Thema die stärksten Wörter, die dominierten Dokumente und der Anteil an den Treffern.

    ``names`` bildet das Gremienkürzel auf seinen Namen ab (``[bodies]``, Punkt 45); ein Kürzel
    ohne gesicherten Namen steht als Kürzel auf der Seite, ein freies Thema ohne beides.
    """
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
            body=str(row.get(TOPIC_BODY) or ""),
            name=(names or {}).get(str(row.get(TOPIC_BODY) or ""), ""),
        )
        for row in topics.sort(TOPIC).iter_rows(named=True)
    )


def _example(frame: pl.DataFrame, by: str, then: str) -> TermExample | None:
    """Der Begriff mit dem größten Wert in ``by``; bei Gleichstand entscheidet ``then``, dann der Name."""
    if frame.is_empty():
        return None
    row = frame.sort([by, then, TERM], descending=[True, True, False]).row(0, named=True)
    return TermExample(str(row[TERM]), int(row[HITS]), int(row[N_DISTRICTS]))


# --- Punkt 45: Dokumente je passendem Ausschuss -------------------------------------------------

# Die Spalten von ``ausschuss_zuordnung.parquet``, als Literale wie bei den Themen: die Seite soll
# ``analysis/committees.py`` und damit sklearn nicht laden (ein Test hält beide Seiten gleich).
ASSIGNED = "ausschuss"
ASSIGNED_DOCUMENTS = "dokumente"
ASSIGNED_SHARE = "anteil"
ASSIGNED_WITHOUT = "ohne_ausschussberatung"
ASSIGNED_MEDIAN = "wahrscheinlichkeit_median"


def assignment_rows(layout: Layout, settings: Settings) -> tuple[AssignmentRow, ...]:
    """Die Tabelle der passenden Ausschüsse, Namen aus dem Profil; leer ohne den Schritt.

    Sortiert nach Dokumenten absteigend, bei Gleichstand nach Kürzel; die Restklasse steht zuletzt,
    weil sie keine Zuordnung ist, sondern ihr Fehlen.

    Die Tabelle hängt am Schalter und an den Ausschüssen des Profils, nicht an der Datei: genau
    die beiden Bedingungen, unter denen ``build_steps`` den Schritt ``committees`` ins Register
    nimmt. Die Datei eines früheren Laufs bleibt sonst liegen und käme auf die Seite, obwohl die
    Kette sie nicht mehr rechnet -- dieselbe Überlegung wie beim Themenblock (``topics.k = 0``).
    """
    if not settings.classify.enabled or not settings.bodies.committees:
        return ()
    if not layout.committee_table.exists():
        return ()
    frame = pl.read_parquet(layout.committee_table)
    names = BodyRules.from_settings(settings.bodies).names
    rows = [
        AssignmentRow(
            code=str(r[ASSIGNED] or ""),
            name=names.get(str(r[ASSIGNED] or ""), ""),
            documents=int(r[ASSIGNED_DOCUMENTS]),
            share=float(r[ASSIGNED_SHARE]),
            without=int(r[ASSIGNED_WITHOUT]),
            median=None if r[ASSIGNED_MEDIAN] is None else float(r[ASSIGNED_MEDIAN]),
        )
        for r in frame.iter_rows(named=True)
    ]
    return tuple(sorted(rows, key=lambda row: (row.code == "", -row.documents, row.code)))


def build_sensitivity(layout: Layout, settings: Settings, results: pl.DataFrame) -> Sensitivity:
    """Der ganze Abschnitt aus ``wahlbezirke_gewichtet.parquet`` und (wenn da) ``themen.parquet``."""
    weighted = pl.read_parquet(layout.weighted)
    with_topics = settings.topics.k > 0
    # Die Themen hängen am Schalter, nicht an der Datei: mit ``topics.k = 0`` bleiben die Dateien
    # eines früheren Laufs liegen, gehören aber nicht mehr auf die Seite.
    topics = (
        topic_rows(
            pl.read_parquet(layout.topics),
            weighted,
            BodyRules.from_settings(settings.bodies).names,
        )
        if with_topics and layout.topics.exists()
        else ()
    )
    rows = sensitivity_rows(
        weighted,
        results,
        settings.weights,
        settings.analysis.exclude_districts,
        with_topics,
        {row.index: row.label for row in topics},
    )
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


# --- Option 04: Urheber und Parteien ---------------------------------------------------------------


def _mean(values: Iterable[float]) -> float:
    """Das ungewichtete Mittel, 0,0 ohne Werte (Punkt 46, dieselbe Regel wie ``scaling``)."""
    found = list(values)
    return statistics.fmean(found) if found else 0.0


def _party_classification(cells: Sequence[PartyCell], party: str) -> dict[int, int]:
    """Quantilklassen je Partei, nicht gemeinsam: die AfD läge sonst überall in der untersten.

    ``classify`` nimmt von sich aus weniger Klassen, wenn es weniger verschiedene Werte gibt (bei
    der AfD mit 70 Treffern über 41 Bezirke sind das wenige).
    """
    from georep.report.charts import classify

    mine = {c.district: c.share for c in cells if c.party == party}
    return classify(mine).classes if mine else {}


@deal.pre(
    lambda party_table, correlations, originators, parties, names, diverging: has_columns(
        party_table,
        DISTRICT,
        PARTEI,
        HITS,
        parties_mod.SHARE,
        "stimmenanteil",
        "angetreten",
        parties_mod.PARTY_DEVIATION,
        parties_mod.PARTY_RATIO,
    )
)
@deal.post(
    lambda result: all(
        0 <= c.klass <= 4 and 0 <= c.klass_deviation <= 4 and 0 <= c.klass_ratio <= 4
        for c in result[1]
    ),
    message="Quantilklassen q0 bis q4, auch die beiden divergierenden",
)
def party_section(
    party_table: pl.DataFrame,
    correlations: Sequence[PartyCorrelation],
    originators: pl.DataFrame,
    parties: Sequence[Party],
    names: Mapping[int, str],
    diverging: Diverging,
) -> tuple[tuple[PartyRow, ...], tuple[PartyCell, ...], tuple[OriginatorRow, ...]]:
    """Die drei Listen des Abschnitts aus den drei Parquet-Tabellen des Schritts ``parties``."""
    # Lokal, weil ``report.charts`` dieses Modul importiert (DistrictRow, PartyCell, format_de):
    # ein Import oben wäre ein Zyklus. Dasselbe tut ``_party_classification`` mit ``classify``.
    from georep.report.charts import classify_fixed

    raw = [
        PartyCell(
            district=int(row[DISTRICT]),
            party=str(row[PARTEI]),
            hits=int(row[HITS]),
            share=float(row[parties_mod.SHARE]),
            vote_share=float(row["stimmenanteil"]),
            ran=bool(row["angetreten"]),
            klass=0,
            deviation=float(row[parties_mod.PARTY_DEVIATION]),
            ratio=float(row[parties_mod.PARTY_RATIO]),
        )
        for row in party_table.sort([PARTEI, DISTRICT]).iter_rows(named=True)
    ]
    classes = {
        party: _party_classification(raw, party) for party in dict.fromkeys(c.party for c in raw)
    }
    # Punkt 46: die beiden neuen Varianten klassieren über alle Parteien gemeinsam und an festen
    # Grenzen -- erst das macht die sechs Karten vergleichbar, und darum geht es bei ihnen.
    keyed = dict(enumerate(raw))
    deviation_classes = classify_fixed(
        {i: c.deviation for i, c in keyed.items()}, diverging.party_points
    ).classes
    ratio_classes = classify_fixed(
        {i: c.ratio for i, c in keyed.items()}, diverging.party_ratio
    ).classes
    cells = tuple(
        replace(
            cell,
            klass=classes[cell.party].get(cell.district, 0),
            klass_deviation=deviation_classes[i],
            klass_ratio=ratio_classes[i],
        )
        for i, cell in keyed.items()
    )
    alone = dict(
        party_table.group_by(PARTEI).agg(pl.col("treffer_allein").sum()).iter_rows()
        if "treffer_allein" in party_table.columns
        else []
    )
    by_key = {c.key: c for c in correlations}
    # Punkt 46: die drei Mittel über die Wahlbezirke, also über genau die Zahlen der Karten
    mine = {key: [c for c in cells if c.party == key] for key in by_key}
    # Reihenfolge und Label kommen aus den Settings, nicht aus der Tabelle
    rows = tuple(
        PartyRow(
            key=party.key,
            label=party.label,
            short=party.column_label,
            documents=by_key[party.key].documents,
            hits=by_key[party.key].hits,
            alone=int(alone.get(party.key, 0)),
            districts_hit=by_key[party.key].districts_hit,
            n=by_key[party.key].n,
            r=by_key[party.key].r,
            p=by_key[party.key].p,
            rho=by_key[party.key].rho,
            mean_share=_mean(c.share for c in mine[party.key]),
            mean_deviation=_mean(c.deviation for c in mine[party.key]),
            mean_ratio=_mean(c.ratio for c in mine[party.key]),
        )
        for party in parties
        if party.key in by_key
    )
    classes_columns = list(KLASSEN_SPALTEN)
    districts = tuple(
        OriginatorRow(
            district=int(row[DISTRICT]),
            name=names.get(int(row[DISTRICT]), ""),
            hits=int(row[HITS]),
            **{column: int(row[column]) for column in classes_columns},
        )
        for row in originators.sort(DISTRICT).iter_rows(named=True)
    )
    return rows, cells, districts


def originator_overview(attribution: pl.DataFrame) -> OriginatorFigures:
    """Die Zähler für den Text: Klassen, Kooperationspapiere, Zuordnungen aus OParl."""
    counted = originator_figures(attribution)
    return OriginatorFigures(
        documents=attribution.height,
        verwaltung=counted["Verwaltung"],
        fraktion=counted["Fraktion"],
        person=counted["Person"],
        eingabe=counted["Eingabe"],
        unbekannt=counted["unbekannt"],
        with_two_parties=attribution.filter(pl.col(PARTEIEN).list.len() >= 2).height,
        from_oparl=attribution.filter(pl.col(QUELLE) == "oparl").height,
    )


def source_precincts(layout: Layout, settings: Settings, fallback: int) -> int:
    """Die Stimmbezirke, aus denen die Zahlen dieser Seite stammen.

    Ohne Umrechnung sind das die des gezeigten Zuschnitts. Ein Periodenprofil mit Crosswalk zeigt
    die Flächen der Hauptperiode, seine Zahlen kommen aber aus dem eigenen, älteren Zuschnitt;
    die Kernzahl soll die Herkunft nennen, nicht die Zeichnung (Option 02).
    """
    if not settings.crosswalk.enabled or not layout.precinct_assignment.is_file():
        return fallback
    assignment = pl.read_parquet(layout.precinct_assignment, columns=[PRECINCT])
    return int(assignment.get_column(PRECINCT).n_unique())


def period_info(settings: Settings) -> PeriodInfo:
    """Option 02: die Periode der Seite aus den Settings; nichts davon steht in der Vorlage."""
    return PeriodInfo(
        profile=settings.profile,
        title=settings.period.title,
        start=settings.period.start,
        end=settings.period.end,
        election=settings.period.election_day,
        converted=settings.crosswalk.enabled,
    )


def _period_rows(comparison: pl.DataFrame, names: Mapping[int, str]) -> tuple[PeriodRow, ...]:
    return tuple(
        PeriodRow(
            id=int(row[DISTRICT]),
            name=names[int(row[DISTRICT])],
            hits_old=int(row[f"{HITS}{OLD}"]),
            hits_new=int(row[f"{HITS}{NEW}"]),
            rate_old=float(row[f"{RATE}{OLD}"]),
            rate_new=float(row[f"{RATE}{NEW}"]),
            turnout_old=float(row[f"{TURNOUT}{OLD}"]),
            turnout_new=float(row[f"{TURNOUT}{NEW}"]),
            d_rate=float(row[D_RATE]),
            d_turnout=float(row[D_TURNOUT]),
        )
        for row in comparison.sort(DISTRICT).iter_rows(named=True)
    )


@deal.ensure(
    lambda layout, settings, names, districts, subpage, result: (
        result is None or 0 < len(result.rows) <= districts
    ),
    message="mindestens ein und höchstens ein Wahlbezirk je Zeile der Auswertung",
)
# deal vergleicht exakte Typen: beide Domänenfehler müssen hier stehen, sonst wird aus einem
# lesbaren Fehler ein RaisesContractError ohne Meldung (CLAUDE.md, „deal (Phase 6)").
@deal.raises(EmptyResultError, MissingInputError)
def period_comparison(
    layout: Layout,
    settings: Settings,
    names: Mapping[int, str],
    districts: int,
    subpage: str,
) -> PeriodComparison | None:
    """Option 02: der Vergleich, wenn ``compare.period`` gesetzt und die Tabelle gerechnet ist.

    Fehlt die Vergleichstabelle, fehlt der Abschnitt: der Schritt ``compare`` läuft nur mit dem
    Profil ``duesseldorf-vergleich``, und ohne ihn ist die Seite die von ``main``. Fehlt
    dagegen die Zuordnung der älteren Periode, ist das kein fehlender Abschnitt, sondern ein
    unvollständiger Lauf — und ein ``MissingInputError``, der sagt, welcher.

    Eine Regression ohne Streuung (alle Trefferquoten der älteren Periode gleich) ist ein
    ``EmptyResultError``; beide Fehler stehen in ``deal.raises`` und kommen als Domänenfehler am
    Rand an, nicht als Vertragsverletzung.
    """
    if not settings.compare.period or not layout.comparison.is_file():
        return None
    other = layout.for_profile(settings.compare.period)
    if not other.precinct_assignment.is_file():
        raise MissingInputError(
            f"Vergleich mit dem Profil {settings.compare.period!r}: "
            f"{other.precinct_assignment} fehlt. Erst dieses Profil vollständig rechnen "
            "(`georep --settings <profil>.toml run`), dann den Vergleich."
        )
    comparison = pl.read_parquet(layout.comparison)
    rows = _period_rows(comparison, names)
    assignment = pl.read_parquet(other.precinct_assignment)
    per_precinct = assignment.group_by(PRECINCT).agg(pl.len(), pl.col("abdeckung").min())
    return PeriodComparison(
        previous=str(comparison.get_column(PERIOD_OLD).item(0)),
        current=str(comparison.get_column(PERIOD_NEW).item(0)),
        rows=rows,
        districts=districts,
        regression=delta_regression(comparison),
        previous_pair=regression_pair(
            pl.read_parquet(other.results), settings.analysis.exclude_districts
        ),
        precincts=per_precinct.height,
        split=per_precinct.filter(pl.col("len") > 1).height,
        min_coverage=min(per_precinct.get_column("abdeckung").to_list()),
        subpage=subpage,
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
    # Option 01 und 02: die Flächen kommen aus dem kanonischen Stand; ein Periodenprofil mit
    # fremdem Zuschnitt liest den der Hauptperiode (``target_view``).
    geometry = layout.target_view(settings)
    precincts = read_canonical_precincts(geometry.precincts_geojson, settings.geo.working_crs)
    hidden = tuple(settings.search.hide_in_display)
    counts = term_counts(dictionary, index)
    names = district_names(precincts)
    # Option 05: die drei Tabellen der Gremien; die Namen kommen aus den Settings
    district_bodies = pl.read_parquet(layout.district_bodies)
    rows = with_bodies(
        district_rows(results, counts, names, hidden),
        district_bodies,
    )
    # Punkt 46: die normierten Lesarten; ohne den Schritt ``metrics`` bleibt ``metrics`` leer und
    # die Vorlage zeigt nur die Trefferquote.
    if layout.district_metrics.exists():
        rows = with_metrics(rows, pl.read_parquet(layout.district_metrics))
    table = body_rows(pl.read_parquet(layout.bodies_table), settings.bodies)
    units = crosswalk_units(layout)  # Option 03: 0 ohne Kontextdaten
    # Option 04: der Abschnitt entsteht nur, wenn der Schritt ``parties`` gelaufen ist
    parties: tuple[PartyRow, ...] = ()
    cells: tuple[PartyCell, ...] = ()
    districts: tuple[OriginatorRow, ...] = ()
    figures: OriginatorFigures | None = None
    if layout.party_results.exists() and layout.document_originators.exists():
        party_table = pl.read_parquet(layout.party_results)
        attribution = pl.read_parquet(layout.document_originators)
        parties, cells, districts = party_section(
            party_table,
            party_correlations(party_table),
            pl.read_parquet(layout.district_originators),
            settings.originators.parties,
            names,
            settings.report.diverging,
        )
        figures = originator_overview(attribution)
    return ReportModel(
        generated_at=now,
        version=__version__,
        commit=commit,
        stand=data_stand(layout, settings),
        figures=key_figures(
            results,
            dictionary,
            layout.corpus,
            source_precincts(layout, settings, len(precincts)),
            # Punkt 46: die Spannweite der zweiten Kennzahl für die Kernzahlen
            [r.metrics.per_term for r in rows if r.metrics is not None],
        ),
        districts=rows,
        top_terms=top_terms_city(counts, hidden),
        hidden_terms=hidden,
        # Regel 2: die Begriffe über der Schwelle, nur zur Anzeige (decisions.md, Punkt 44b)
        citywide=citywide_section(
            counts,
            citywide_terms(
                index,
                quantile=settings.search.citywide_quantile,
                median_factor=settings.search.citywide_median_factor,
            ),
        ),
        city_facilities=settings.search.city_facilities,
        regression=(
            regression_pair(results, settings.analysis.exclude_districts)
            if settings.report.regression
            else None  # Option 07: zur laufenden Periode gibt es keine Wahlbeteiligung
        ),
        downloads=tuple(downloads),
        columns=column_docs(layout, settings),
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
        assignment=assignment_rows(layout, settings),
        assignment_threshold=settings.classify.min_probability,
        body_figures=body_figures(
            table,
            rows,
            settings.bodies,
            # Punkt 58: die Quellen je Dokument; die Datei ist Eingabe des Schritts ``report``
            prep_bodies.source_counts(pl.read_parquet(layout.papers_bodies))
            if layout.papers_bodies.exists()
            else None,
        ),
        body_regression=_body_regression(district_bodies, results, settings),
        # Punkt 46: die zweite Kennzahl des Methodik-Reviews mit eigener Regression (§ 2.6)
        per_term_regression=_per_term_regression(layout, results, settings),
        bias=(
            scaling.dictionary_bias(pl.read_parquet(layout.district_metrics), results)
            if layout.district_metrics.exists()
            else None
        ),
        # Option 06: ohne die lange Tabelle gibt es den Abschnitt nicht
        # Option 07: die Sensitivitätstabelle ist Tabelle 5 je Gewichtungsvariante; ohne
        # Wahlbeteiligung zur Periode gibt es sie nicht, so wie es das Streudiagramm nicht gibt.
        sensitivity=(
            build_sensitivity(layout, settings, results)
            if layout.weighted.exists() and settings.report.regression
            else None
        ),
        controls=controls_section(layout, settings, units),
        derived=derived_data(layout, settings, units),
        # Option 04
        parties=parties,
        party_cells=cells,
        originators=districts,
        originator_figures=figures,
        # Option 02
        period=period_info(settings),
        comparison=period_comparison(
            layout, settings, names, results.height, f"{settings.compare.period}/"
        ),
        # Option 01: die Stadt, ihre Quellen und die Messung gegen das Straßenverzeichnis
        city=settings.city,
        sources=tuple(settings.report.sources),
        literature=literature(settings),  # Punkt 47
        ris_url=settings.report.ris_url,
        marker=settings.search.text_split_marker,
        notes=tuple(settings.report.notes),
        agreement=street_agreement(layout, settings),
        data_note=settings.report.data_note,
        timeline=month_rows(layout.timeline),  # Option 07
        monitoring_url=settings.report.monitoring_url,
        # Eine Periode liegt unter der Stadt, nicht an ihrer Stelle: genau dann gibt es einen
        # Rückweg. Abgeleitet und kein Settings-Schlüssel, weil derselbe Vergleich schon
        # entscheidet, wo die Seite landet (Punkt 52, ``Settings.base_profile``).
        parent_url="../" if settings.profile != settings.base_profile else "",
        preview_rows=settings.report.table_preview_rows,  # Punkt 48
    )


def _per_term_regression(
    layout: Layout, results: pl.DataFrame, settings: Settings
) -> RegressionPair | None:
    """Tabelle 5, aber mit x = Treffer je Begriff im Wörterbuch (Punkt 46).

    Die stärkste Verzerrung der Methode ist, dass ein Bezirk mit großem Wörterbuch häufiger
    getroffen wird (r = 0,7595 auf der Referenz); diese Kennzahl nimmt sie heraus. ``None`` ohne
    den Schritt ``metrics`` und ohne Wahlbeteiligung zur Periode (Option 07).
    """
    if not settings.report.regression or not layout.district_metrics.exists():
        return None
    # Sortiert wie jeder Frame, über den eine Regression läuft (2026-10-13).
    frame = (
        pl.read_parquet(layout.district_metrics)
        .join(results.select(DISTRICT, TURNOUT), on=DISTRICT, how="inner")
        .sort(DISTRICT)
    )
    try:
        return regression_pair(
            frame, settings.analysis.exclude_districts, x=scaling.PER_TERM, y=TURNOUT
        )
    except EmptyResultError:
        # Zu wenige Bezirke oder keine Streuung: die Seite lässt den Block dann weg, statt zu
        # scheitern (derselbe Umgang wie bei der Regression der Gremien).
        return None


def _body_regression(
    district_bodies: pl.DataFrame, results: pl.DataFrame, settings: Settings
) -> RegressionPair | None:
    """Wahlbeteiligung gegen die Quote der eigenen Bezirksvertretung; None ohne Streuung (Mini)."""
    frame = bodies.regression_frame(district_bodies, results)
    try:
        return regression_pair(frame, settings.analysis.exclude_districts, x=bodies.OWN_RATE)
    except EmptyResultError:
        return None


# --- Option 03: die beiden Abschnitte aus den Parquet-Dateien ------------------------------------

RATE_LABEL = "Trefferquote"  # dieselbe Kennzahl wie im Streudiagramm
SINGLE = "single:"


def _term_row(row: Mapping[str, object], context: ContextSettings) -> ControlTerm:
    name = str(row["term"])
    label, unit = (
        ("Achsenabschnitt", "")
        if name == CONSTANT
        else (RATE_LABEL, "Dokumente je Person")
        if name == RATE_TERM
        else (context.variable(name).label, context.variable(name).unit)
    )
    beta, vif = row["beta_std"], row["vif"]
    return ControlTerm(
        term=name,
        label=label,
        unit=unit,
        coefficient=float(row["koeffizient"]),  # type: ignore[arg-type]
        stderr=float(row["standardfehler"]),  # type: ignore[arg-type]
        p=float(row["p"]),  # type: ignore[arg-type]
        beta=None if beta is None else float(beta),  # type: ignore[arg-type]
        vif=None if vif is None else float(vif),  # type: ignore[arg-type]
    )


ALPHA = 0.05  # Signifikanzniveau, auf das sich die Arbeit und Tabelle 5 beziehen
# „Ähnlich" heißt: gleiches Vorzeichen, beide p auf derselben Seite von ALPHA und der Koeffizient
# höchstens um diesen Anteil verschoben. Eine Anzeigeschwelle, kein Test: sie entscheidet nur, ob
# der Satz die zweite Stichprobe zusammenfasst oder ihre Zahlen nennt.
SIMILAR_WITHIN = 0.25


def _p(value: float) -> str:
    """p für den Fließtext; unter einem Promille nennt die Zahl nichts mehr.

    Reiner Text, kein HTML: der Satz geht durch das Autoescape der Vorlage.
    """
    return "< 0,001" if value < 0.001 else format_de(value, 3)


def _lead(simple: ControlModel, best: ControlModel, rate: ControlTerm) -> str:
    """Der erste Satzteil: was Modell A und das Hauptmodell zusammen über die Kennzahl sagen.

    Vier Fälle, denn beide p zählen: ein Koeffizient, der ohne Kontrollvariablen nicht von Null zu
    unterscheiden ist, kann mit ihnen nichts verlieren, und umgekehrt.
    """
    plain = next(t for t in simple.terms if t.term == RATE_TERM)
    direction = "höher" if rate.coefficient > 0 else "niedriger"
    effect = (
        f": je Dokument und Wahlberechtigtem liegt die Beteiligung "
        f"{format_de(abs(rate.coefficient), 1)} Prozentpunkte {direction}"
    )
    if plain.p < ALPHA and rate.p < ALPHA:
        return (
            f"Der Zusammenhang der {RATE_LABEL} mit der Wahlbeteiligung ist in Modell "
            f"{simple.name} (p = {_p(plain.p)}) wie mit den Kontrollvariablen "
            f"(p = {_p(rate.p)}) auf dem {int(ALPHA * 100)}-%-Niveau signifikant{effect}"
        )
    if plain.p < ALPHA:
        return (
            f"Modell {simple.name} zeigt einen auf dem {int(ALPHA * 100)}-%-Niveau signifikanten "
            f"Zusammenhang (p = {_p(plain.p)}); mit den Kontrollvariablen ist der Koeffizient der "
            f"{RATE_LABEL} nicht mehr von Null zu unterscheiden (p = {_p(rate.p)}), was Modell "
            f"{simple.name} zeigt, erklären die Kontrollvariablen"
        )
    if rate.p < ALPHA:
        return (
            f"Modell {simple.name} findet mit p = {_p(plain.p)} keinen Zusammenhang; erst mit den "
            f"Kontrollvariablen wird der Koeffizient der {RATE_LABEL} auf dem "
            f"{int(ALPHA * 100)}-%-Niveau signifikant (p = {_p(rate.p)}){effect}"
        )
    return (
        f"Modell {simple.name} findet mit p = {_p(plain.p)} keinen Zusammenhang, und auch mit den "
        f"Kontrollvariablen ist der Koeffizient der {RATE_LABEL} nicht von Null zu unterscheiden "
        f"(p = {_p(rate.p)})"
    )


def _similar(rate: ControlTerm, without: ControlTerm) -> bool:
    """Ob die zweite Stichprobe dasselbe erzählt: Vorzeichen, Seite von ALPHA, Höhe."""
    same_side = (rate.p < ALPHA) == (without.p < ALPHA)
    same_sign = (rate.coefficient >= 0) == (without.coefficient >= 0)
    if not (same_side and same_sign) or rate.coefficient == 0:
        return False
    return abs(without.coefficient - rate.coefficient) / abs(rate.coefficient) <= SIMILAR_WITHIN


def _without_clause(rate: ControlTerm, without: ControlTerm | None, excluded: Sequence[int]) -> str:
    """Was die Stichprobe ohne die Ausreißer ändert -- zusammengefasst oder mit den Zahlen."""
    if without is None or not excluded:
        return ""
    districts = f"; ohne die Wahlbezirke {_join(excluded)}"
    if _similar(rate, without):
        return f"{districts} sieht es ähnlich aus"
    return (
        f"{districts} liegt der Koeffizient bei {format_de(without.coefficient, 2)} "
        f"(p = {_p(without.p)})"
    )


def _verdict(
    models: Sequence[ControlModel],
    main: str,
    excluded: Sequence[int],
    without: ControlTerm | None = None,
) -> str:
    """Ein Satz zur Deutung, der aus den Zahlen folgt: p beider Modelle, Vorzeichen, R², stärkster Term."""
    # Ohne ein Modell neben A gibt es nichts zu deuten: die Stichprobe war zu klein.
    best = next((m for m in models if m.name == main and m.k > 1), None)
    simple = next((m for m in models if m.name == "A"), None)
    if best is None or simple is None:
        return (
            "Für Modelle mit Kontrollvariablen reichen die Wahlbezirke dieser Stichprobe nicht aus."
        )
    rate = next(t for t in best.terms if t.term == RATE_TERM)
    strongest = max(
        (t for t in best.terms if t.term not in (CONSTANT, RATE_TERM)),
        key=lambda t: abs(t.beta or 0.0),
        default=None,
    )
    gain = (
        f". Modell {best.name} erklärt R² = {format_de(best.r2, 2)} der Streuung gegenüber "
        f"{format_de(simple.r2, 2)} in Modell {simple.name}"
    )
    strong = (
        f"; den größten Beitrag leistet {strongest.label} "
        f"(standardisiert {format_de(strongest.beta or 0.0, 2)})"
        if strongest is not None
        else ""
    )
    note = (
        f". Bei n = {best.n} Wahlbezirken und {best.k} Termen ist das eine Beschreibung, "
        "keine Ursache" + _without_clause(rate, without, excluded)
    )
    return _lead(simple, best, rate) + gain + strong + note + "."


def _join(numbers: Sequence[int]) -> str:
    return " und ".join(str(n) for n in numbers)


def controls_section(layout: Layout, settings: Settings, units: int) -> ControlsSection | None:
    """Tabelle 6, Tabelle 6b und der Satz zur Deutung aus ``regression_kontrollen.parquet``."""
    if not layout.controls.exists():
        return None
    table = pl.read_parquet(layout.controls)
    context = settings.context
    excluded = tuple(settings.analysis.exclude_districts)
    sample = table.filter(pl.col("stichprobe") == ALL)
    models: list[ControlModel] = []
    singles: list[SingleAddition] = []
    for name in model_terms(context):
        rows = sample.filter(pl.col("modell") == name)
        if rows.is_empty():
            continue
        head = rows.row(0, named=True)
        terms = tuple(_term_row(r, context) for r in rows.iter_rows(named=True))
        if name.startswith(SINGLE):
            variable = context.variable(name.removeprefix(SINGLE))
            rate = next(t for t in terms if t.term == RATE_TERM)
            singles.append(
                SingleAddition(
                    variable=variable.name,
                    label=variable.label,
                    unit=variable.unit,
                    coefficient=rate.coefficient,
                    stderr=rate.stderr,
                    p=rate.p,
                    r2_adj=float(head["r2_adj"]),
                )
            )
            continue
        models.append(
            ControlModel(
                name=name,
                terms=terms,
                n=int(head["n"]),
                k=int(head["k"]),
                r2=float(head["r2"]),
                r2_adj=float(head["r2_adj"]),
                f_p=float(head["f_p"]),
            )
        )
    main = MAIN_MODEL if any(m.name == MAIN_MODEL for m in models) else "A"
    without = table.filter(
        (pl.col("stichprobe") != ALL) & (pl.col("modell") == main) & (pl.col("term") == RATE_TERM)
    )
    rate_without = None if without.is_empty() else _term_row(without.row(0, named=True), context)
    estimated = {(r["modell"], r["stichprobe"]) for r in table.iter_rows(named=True)}
    possible = [
        (name, s)
        for name in model_terms(context)
        for s in ([ALL, sample_label(excluded)] if excluded else [ALL])
    ]
    return ControlsSection(
        models=tuple(models),
        singles=tuple(singles),
        main=main,
        rate_label=RATE_LABEL,
        units_label=context.units.label,
        units=units,
        stand=_dataset_date(context.dataset.stand, "stand"),
        excluded=excluded,
        rate_without=rate_without,
        verdict=_verdict(models, main, excluded, rate_without),
        missing=tuple(f"{m} ({s})" for m, s in possible if (m, s) not in estimated),
    )


def _dataset_date(value: dt.date | None, field: str) -> dt.date:
    """Stand und Abrufdatum des Kontextdatensatzes; ohne sie ist die Namensnennung unvollständig.

    Der Validator der Settings verlangt beide, sobald ``context.root`` auf einen Datensatz zeigt
    (Option 01: eine Stadt ohne Kontextdaten lässt den Block weg); hier steht die Zusicherung
    noch einmal, weil ein von Hand gebautes ``ContextSettings`` sie umgehen kann.
    """
    if value is None:
        raise SchemaError(f"context.dataset.{field} fehlt, der Datensatz ist nicht zitierbar")
    return value


DEFINITION_LIMIT = 220  # Zeichen; die Quelle erklaert manche Indizes über tausend Zeichen lang


def first_sentence(text: str, limit: int = DEFINITION_LIMIT) -> str:
    """Der erste Satz, wenn der Text zu lang für eine Tabellenzelle ist; sonst der ganze Text.

    Die Quelle beschreibt ihre Indizes ausführlich; die Tabelle „Abgeleitete Daten" zeigt den
    Anfang und verweist auf die Datensatzseite, sonst füllt eine Zelle den halben Bildschirm.
    """
    if len(text) <= limit:
        return text
    cut = text.find(". ")
    shortened = text[: cut + 1] if 0 < cut <= limit else text[:limit].rsplit(" ", 1)[0]
    return shortened.rstrip(".") + " …"


def _attribution(dataset: ContextDataset) -> str:
    """Namensnennung, wie die Lizenz sie verlangt: wer, was, unter welcher Lizenz.

    Alle drei Teile kommen aus den Settings; eine andere Stadt nennt eine andere Lizenz, und ein
    fester Kurzname (``dl-de/by-2-0``) wäre dann schlicht falsch.
    """
    return f"{dataset.publisher}: {dataset.title}, {dataset.license}"


def derived_data(layout: Layout, settings: Settings, units: int) -> DerivedData | None:
    """Abschnitt „Abgeleitete Daten": je Variable Definition, Quelle, Umrechnung; Lizenz und Stand."""
    context = settings.context
    if not layout.context_table.exists():
        return None
    indicators = read_indicators(layout.external / context.files.indicators.file, context)
    districts = int(pl.scan_parquet(layout.context_table).select(pl.len()).collect().item())
    weighted = (
        f"{context.units.label} auf Wahlbezirke, gewichtet mit den Wahlberechtigten je "
        "Stimmbezirk und dem Flächenanteil"
    )
    variables = tuple(
        DerivedVariable(
            name=variable.name,
            label=variable.label,
            unit=variable.unit,
            definition=first_sentence(indicators.get(variable.indicator.strip(), "")),
            source=(
                "Wahlergebnis der Ratswahl je Wahlbezirk"
                if variable.kind == "district"
                else context.dataset.title
            ),
            transform=(
                "Stimmenanteil mal 100"
                if variable.kind == "district"
                else "Stufen gering bis hoch als Score 1 bis 5, dann " + weighted
                if variable.kind == "ordinal"
                else ("Summe der Spalten, dann " if variable.kind == "sum" else "") + weighted
            ),
        )
        for variable in context.variables
    )
    fetched = stamp_written(layout.external / context.files.table.file)
    return DerivedData(
        title=context.dataset.title,
        url=context.dataset.url,
        publisher=context.dataset.publisher,
        license=context.dataset.license,
        license_url=context.dataset.license_url,
        stand=_dataset_date(context.dataset.stand, "stand"),
        fetched=fetched or _dataset_date(context.dataset.fetched, "fetched"),
        attribution=_attribution(context.dataset),
        units_label=context.units.label,
        units=units,
        districts=districts,
        variables=variables,
    )


def crosswalk_units(layout: Layout) -> int:
    """Wie viele Raumeinheiten im Crosswalk vorkommen; 0 ohne Kontextdaten."""
    if not layout.crosswalk.exists():
        return 0
    return int(
        pl.scan_parquet(layout.crosswalk).select(pl.col(CROSSWALK_UNIT).n_unique()).collect().item()
    )


def street_agreement(layout: Layout, settings: Settings) -> Agreement | None:
    """Die Übereinstimmung der Flächen mit dem Straßenverzeichnis, wo die Stadt eines hat."""
    directory = layout.streets_directory
    if directory is None or not directory.is_file() or not layout.streets.is_file():
        return None
    return directory_agreement(
        layout.streets, directory, settings.columns.results, settings.precincts
    )


# --- summary.json: die Schnittstelle des Städtevergleichs --------------------------------------

SUMMARY_FIELDS: dict[str, str] = {
    "city.slug": "Ordnername der Stadt im veröffentlichten Ordner",
    "city.name": "Name der Stadt",
    "city.ags": "amtlicher Gemeindeschlüssel",
    "city.election": "Name der Wahl, deren Ergebnis die Nenner liefert",
    "stand.election": "Wahltag, dessen Ergebnis die Nenner liefert (ISO-Datum)",
    "stand.period_start": "Beginn der Wahlperiode (ISO-Datum)",
    "stand.period_end": "Ende der Wahlperiode (ISO-Datum) oder null bei laufender Periode",
    "figures.districts": "Zahl der Kommunalwahlbezirke",
    "figures.precincts": "Zahl der Stimmbezirke",
    "figures.documents": "Zahl der Ratsdokumente der Periode",
    "figures.documents_with_text": "davon mit extrahiertem Text",
    "figures.documents_hit": "Dokumente mit mindestens einem Treffer",
    "figures.terms": "Begriffe im Wörterbuch",
    "figures.rate_median": "Median der Trefferquote (Dokumente je Wahlberechtigtem)",
    "figures.rate_min": "kleinste Trefferquote",
    "figures.rate_max": "größte Trefferquote",
    "figures.turnout_median": "Median der Wahlbeteiligung (Anteil 0 bis 1)",
    "regression.all": "Regression Trefferquote auf Wahlbeteiligung über alle Wahlbezirke: n, slope, intercept, r, r2, p, stderr",
    "regression.without": "dieselbe Regression ohne analysis.exclude_districts, oder null",
    "regression.excluded": "die ausgeschlossenen Wahlbezirke",
    "version": "Version von georep, die die Seite gebaut hat",
    "generated_at": "Zeitpunkt des Baus (ISO-8601, UTC)",
}


def _regression_json(fit: RegressionResult | None) -> dict[str, float | int] | None:
    """Eine Regression als JSON: n, Steigung, Achsenabschnitt, r, p, R² und Standardfehler."""
    if fit is None:
        return None
    return {
        "n": fit.n,
        "slope": fit.slope,
        "intercept": fit.intercept,
        "r": fit.r,
        "r2": fit.r2,
        "p": fit.p,
        "stderr": fit.stderr,
    }


def summary_payload(model: ReportModel) -> dict[str, object]:
    """Kernzahlen, Regression und Datenstand als JSON-taugliches Dict.

    Das ist die Schnittstelle des Städtevergleichs und für Dritte: ``georep publish`` liest je
    Stadt nur den veröffentlichten Ordner, nie Zwischenergebnisse (docs/plans/01-staedte.md, § 2).
    Die Felder sind in ``SUMMARY_FIELDS`` beschrieben; ``schema.json`` druckt sie mit.
    """
    figures = model.figures
    if model.city is None:  # build_report_model setzt die Stadt immer; von Hand gebaut nicht
        raise SchemaError("summary.json braucht die Stadt; das Modell trägt keine")
    return {
        "city": {
            "slug": model.city.slug,
            "name": model.city.name,
            "ags": model.city.ags,
            "election": model.city.election,
        },
        "stand": {
            "election": model.stand.election.isoformat(),
            "period_start": model.stand.period_start.isoformat(),
            "period_end": model.stand.period_end.isoformat() if model.stand.period_end else None,
        },
        "figures": {
            "districts": figures.districts,
            "precincts": figures.precincts,
            "documents": figures.documents,
            "documents_with_text": figures.documents_with_text,
            "documents_hit": figures.documents_hit,
            "terms": figures.terms,
            "rate_median": figures.rate_median,
            "rate_min": figures.rate_min,
            "rate_max": figures.rate_max,
            "turnout_median": figures.turnout_median,
        },
        # Option 07: eine laufende Periode hat keine Wahlbeteiligung und damit keine Regression;
        # der Städtevergleich liest das Feld tolerant (``report.comparison.Site.fit``).
        "regression": (
            {
                "all": _regression_json(model.regression.all),
                "without": _regression_json(model.regression.without),
                "excluded": list(model.regression.excluded),
            }
            if model.regression is not None
            else None
        ),
        "version": model.version,
        "generated_at": model.generated_at.isoformat(),
    }
