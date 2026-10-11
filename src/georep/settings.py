"""Konfiguration: gepackte ``defaults.toml``, darüber TOML-Dateien im Arbeitsverzeichnis, darüber Umgebung.

Reihenfolge (spätere gewinnen): ``defaults.toml`` im Paket < ``./settings.toml`` < ``./settings.local.toml``
< ``$GEOREP_SETTINGS`` bzw. ``--settings`` < Umgebungsvariablen ``GEOREP_<FELD>`` (verschachtelt mit
``__``). Die TOML-Schichten werden tief gemischt, es reicht also der geänderte Schlüssel. Unbekannte
Schlüssel sind ein Fehler (Tippfehler sollen auffallen). Muster wie in Konrads bubatzblick:
``tomllib`` plus pydantic, Begründungen als Kommentar neben der Zahl.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import deal
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

LOG_LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
PROFILE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")  # ein Ordnername unter data_root, kein Pfad


def _plain_name(value: str, key: str) -> str:
    if value and not PROFILE_NAME.fullmatch(value):
        raise ValueError(
            f"{key} {value!r}: nur Kleinbuchstaben, Ziffern und Bindestriche (ein Ordnername)"
        )
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Period(_Strict):
    """Wahlperiode; ``end`` fehlt bei einer laufenden Periode, dann ist ``election`` Pflicht."""

    start: date
    end: date | None = None
    election: date | None = (
        None  # Wahltag, dessen Ergebnis Nenner und Zuschnitt liefert; Standard: end
    )
    # Option 02: Anzeigename der Periode auf der Seite (leer = aus den Jahren abgeleitet, ``title``)
    # und Herkunft des Wörterbuchs: "base" liest Straßen und Orte der Hauptperiode (Profil "").
    label: str = ""
    dictionary: Literal["own", "base"] = "own"

    @field_validator("end", "election", mode="before")
    @classmethod
    def _empty_is_open(cls, value: object) -> object:
        # Der tiefe Merge laesst end aus defaults.toml stehen; ein Profil mit laufender Periode
        # schreibt end = "" und macht sie damit ausdruecklich offen.
        return None if value == "" else value

    @model_validator(mode="after")
    def _ordered(self) -> Period:
        if self.end is not None and self.end < self.start:
            raise ValueError(f"period.end {self.end} liegt vor period.start {self.start}")
        if self.end is None and self.election is None:
            raise ValueError("period.election ist Pflicht, wenn period.end offen ist")
        return self

    @property
    def election_day(self) -> date:
        """Der Wahltag, dessen Ergebnis Nenner und Zuschnitt liefert: ``election``, sonst ``end``.

        Bei einer geschlossenen Periode ist es die Wahl an ihrem Ende; bei einer laufenden die Wahl
        vor ihrem Beginn (Option 7: ``start = 2025-09-15``, ``election = 2025-09-14``), darum gibt
        es keine Ordnung zwischen ``election`` und ``start``.
        """
        if self.election is not None:
            return self.election
        assert self.end is not None  # der Validator verlangt eines von beiden
        return self.end

    @property
    def title(self) -> str:
        """``label``, sonst „Wahlperiode 2014 bis 2020" beziehungsweise „Wahlperiode seit 2025"."""
        if self.label:
            return self.label
        if self.end is None:
            return f"Wahlperiode seit {self.start.year}"
        return f"Wahlperiode {self.start.year} bis {self.end.year}"


class HttpSettings(_Strict):
    timeout_s: float = 180.0
    retries: int = 5
    user_agent: str = "georep"


class OparlSource(_Strict):
    endpoint: str
    organizations_endpoint: str = ""  # Option 04: Fraktionen und Gremien, eine Seite
    delay_s: float = 1.0
    stop_when_older: bool = True
    incremental: bool = True
    pdf_limit: int = 0
    max_pages: int = 0  # Option 04: 0 = alle; `fetch papers --max-pages N` setzt es für einen Lauf

    first_page: int = (
        1  # Option 02: Seite, bei der der Abruf beginnt (die Liste ist neueste zuerst)
    )

    @field_validator("first_page")
    @classmethod
    def _first_page_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError(f"sources.oparl.first_page {value}: OParl zählt Seiten ab 1")
        return value


class OpendataSource(_Strict):
    results_url: str
    districts_url: str
    # Option 02: Wahlbezirksflächen und -ergebnis eines älteren Zuschnitts (leer = nicht abrufen)
    # und der Dateiname, unter dem das Stimmbezirks-GeoJSON in external/ liegt.
    district_shapes_url: str = ""
    district_results_url: str = ""
    districts_file: str = "Stimmbezirke_2025.geojson"

    @field_validator("districts_file")
    @classmethod
    def _plain_file_name(cls, value: str) -> str:
        if not value or "/" in value or value != Path(value).name:
            raise ValueError(f"sources.opendata.districts_file {value!r}: ein Dateiname, kein Pfad")
        return value


class WikidataSource(_Strict):
    sparql_endpoint: str
    wikipedia_api: str
    entity: str
    language: str = "de"
    geosearch_limit: int = 500
    delay_s: float = 1.0


class OsmSource(_Strict):
    overpass_endpoint: str
    delay_s: float = 1.0
    simplify_m: float = 2.0


class Sources(_Strict):
    oparl: OparlSource
    opendata: OpendataSource
    wikidata: WikidataSource
    osm: OsmSource


class CacheSettings(_Strict):
    """Lebensdauer gecachter HTTP-Antworten in Sekunden je Quelle; 0 = nie cachen."""

    oparl_pages_s: int = 3600
    opendata_s: int = 2_592_000
    wikidata_s: int = 2_592_000
    wikipedia_s: int = 2_592_000
    overpass_s: int = 2_592_000


class Geo(_Strict):
    working_crs: str = "EPSG:25832"
    output_crs: str = "EPSG:4326"


class ResultsColumns(_Strict):
    sep: str = ";"
    encoding: str = "latin-1"
    district: str = ""  # leer: der Wahlbezirk kommt aus der Zuordnung des Crosswalks (Option 02)
    eligible: str
    voters: str
    parties: dict[str, str]
    city_district: str  # Option 05: Stadtbezirk je Stimmbezirk, für die Zuordnung der Wahlbezirke
    precinct: str = ""  # Option 03: Stimmbezirk in der CSV; "" = kein Crosswalk über Stimmbezirke
    # Option 02: Wahlberechtigte mit Wahlschein je Stimmbezirk (Verteilschlüssel der Briefwahl)
    # und der Namensmarker der Briefwahlbezirke; die Stimmbezirksnummer steht oben (Option 03).
    eligible_postal: str = ""
    postal_marker: str = ""


class Columns(_Strict):
    district_id: str
    district_name: str
    precinct_id: str
    results: ResultsColumns


class Search(_Strict):
    text_split_marker: str = "betrifft"
    hide_in_display: list[str] = []
    exclude: list[str] = []

    @field_validator("text_split_marker")
    @classmethod
    def _marker_not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "search.text_split_marker darf nicht leer sein (str.split braucht einen Trenner)"
            )
        return value


class Analysis(_Strict):
    """Auswertungsparameter, die mehr als ein Modul lesen; Begründung je Zahl in ``defaults.toml``."""

    exclude_districts: list[int] = []  # Tabelle 5 „ohne Ausreißer"; leer = keine zweite Regression


# Option 05
class Bodies(_Strict):
    """Gremium je Ratsdokument aus der Drucksachennummer; Muster, Kürzel und Namen nur hier.

    ``reference_pattern`` braucht die Gruppen ``code`` (Kürzel) und ``number`` (die Nummer dahinter,
    bei Bezirksvertretungen der Stadtbezirk). Die drei Tabellen ordnen Kürzel ihrer Klasse zu
    (Rat, Ausschuss, Beirat) und nennen den Namen (leer = nicht gesichert); ``district_body`` ist
    das Kürzel der Bezirksvertretungen. Ein Kürzel in zwei Tabellen wäre eine doppelte Wahrheit.
    """

    reference_pattern: str
    district_body: str
    district_body_name: str = "{n}"  # Anzeigename der Bezirksvertretung, {n} ist der Stadtbezirk
    names_as_of: date | None = None  # Stand der Namen; nur Anzeige, nicht im Fingerprint
    council: dict[str, str] = {}
    committees: dict[str, str] = {}
    advisory: dict[str, str] = {}

    @field_validator("reference_pattern")
    @classmethod
    def _pattern_has_code_and_number(cls, value: str) -> str:
        try:
            groups = re.compile(value).groupindex
        except re.error as error:
            raise ValueError(f"bodies.reference_pattern ist kein Muster: {error}") from error
        missing = [g for g in ("code", "number") if g not in groups]
        if missing:
            raise ValueError(f"bodies.reference_pattern braucht die Gruppen {missing}")
        return value

    @model_validator(mode="after")
    def _codes_disjoint(self) -> Bodies:
        if not self.district_body:
            raise ValueError("bodies.district_body darf nicht leer sein")
        tables = {"council": self.council, "committees": self.committees, "advisory": self.advisory}
        seen: dict[str, str] = {}
        for table, codes in tables.items():
            for code in codes:
                if code in seen:
                    raise ValueError(
                        f"Kürzel {code} steht in bodies.{seen[code]} und bodies.{table}"
                    )
                seen[code] = table
        if self.district_body in seen:
            raise ValueError(
                f"bodies.district_body {self.district_body!r} steht auch in "
                f"bodies.{seen[self.district_body]}"
            )
        return self

    @property
    def codes(self) -> frozenset[str]:
        """Alle Kürzel der drei Tabellen (ohne die Bezirksvertretungen)."""
        return frozenset(self.council) | frozenset(self.committees) | frozenset(self.advisory)


# --- Option 06: Gewichtung (docs/plans/06-gewichtung.md) ----------------------------------------

# Namen, die die festen Varianten der gewichteten Trefferquote tragen; ein Regelsatz darf keinen
# davon tragen und nicht wie ein Thema heißen (``thema_NN``).
FIXED_VARIANTS = ("einheit", "bezirke", "idf", "kombiniert")
TOPIC_PREFIX = "thema_"
_VARIANT_NAME = re.compile(r"[a-z][a-z0-9_]*")


def _unit_interval(field: str, value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} {value} liegt nicht in [0, 1]; Gewichte sind Anteile")
    return value


class PaperTypeRule(_Strict):
    """Eine Regel: Regex auf ``paper_type`` (ohne Groß/Klein) und das Gewicht, wenn sie trifft."""

    pattern: str
    weight: float

    @field_validator("pattern")
    @classmethod
    def _pattern_compiles(cls, value: str) -> str:
        try:
            re.compile(value, re.IGNORECASE)
        except re.error as error:
            raise ValueError(
                f"pattern {value!r} ist kein gültiger regulärer Ausdruck: {error}"
            ) from error
        return value

    @field_validator("weight")
    @classmethod
    def _weight_in_unit_interval(cls, value: float) -> float:
        return _unit_interval("weight", value)


class PaperTypeVariant(_Strict):
    """Ein Regelsatz = eine Variante: geordnete Regeln, die erste passende gewinnt, sonst ``default``."""

    name: str
    label: str  # Beschriftung der Zeile auf der Berichtsseite
    default: float = 1.0
    rules: list[PaperTypeRule] = []

    @field_validator("name")
    @classmethod
    def _plain_and_not_reserved(cls, value: str) -> str:
        if not _VARIANT_NAME.fullmatch(value):
            raise ValueError(f"name {value!r}: nur Kleinbuchstaben, Ziffern und Unterstriche")
        if value in FIXED_VARIANTS or value.startswith(TOPIC_PREFIX):
            raise ValueError(
                f"name {value!r} ist für eine feste Variante reserviert ({FIXED_VARIANTS}, {TOPIC_PREFIX}NN)"
            )
        return value

    @field_validator("default")
    @classmethod
    def _default_in_unit_interval(cls, value: float) -> float:
        return _unit_interval("default", value)


class Weights(_Strict):
    """Varianten der gewichteten Trefferquote; alle Gewichte liegen in [0, 1]."""

    combined: list[str] = []  # Faktoren der Variante ``kombiniert`` (Produkt); leer = keine Zeile
    paper_type: list[PaperTypeVariant] = []

    @model_validator(mode="after")
    def _names_unique_and_factors_known(self) -> Weights:
        names = [v.name for v in self.paper_type]
        if len(names) != len(set(names)):
            raise ValueError(f"weights.paper_type: Variantennamen nicht eindeutig: {names}")
        known = {"bezirke", "idf", *names}
        unknown = [f for f in self.combined if f not in known]
        if unknown or len(self.combined) != len(set(self.combined)):
            raise ValueError(
                f"weights.combined {self.combined}: unbekannte oder doppelte Faktoren; "
                f"bekannt sind {sorted(known)}"
            )
        return self


MAX_TOPICS = 99  # ``thema_NN``: zwei Stellen, damit die Variantennamen numerisch sortieren


class Topics(_Strict):
    """Themenmodell (TF-IDF und NMF); ``k = 0`` schaltet den Schritt ``topics`` ab."""

    k: int = 20
    min_df: int = 5
    max_df: float = 0.5
    max_features: int = 20_000
    top_words: int = 10
    stop_words: str = "de"  # Kürzel der Paketdatei analysis/stopwords_<kürzel>.txt; leer = keine
    max_iter: int = 200  # Obergrenze der NMF-Iterationen
    tol: float = 1e-3  # Abbruchschwelle; mit 1e-4 läuft NMF in die Obergrenze (defaults.toml)
    random_state: int = 0

    @model_validator(mode="after")
    def _bounds(self) -> Topics:
        if self.k < 0:
            raise ValueError(f"topics.k {self.k} darf nicht negativ sein (0 schaltet ab)")
        if self.k > MAX_TOPICS:
            # Die Varianten heißen thema_NN mit zwei Stellen; thema_100 stünde beim Sortieren
            # zwischen thema_10 und thema_11, und die Tabelle der Seite käme durcheinander.
            raise ValueError(f"topics.k {self.k} ist größer als {MAX_TOPICS} (zweistellige Namen)")
        if self.min_df < 1 or self.max_features < 1 or self.top_words < 1:
            raise ValueError("topics.min_df, max_features und top_words müssen mindestens 1 sein")
        if not 0.0 < self.max_df <= 1.0:
            raise ValueError(f"topics.max_df {self.max_df} liegt nicht in (0, 1]")
        if self.max_iter < 1 or not self.tol > 0.0:
            raise ValueError(
                f"topics.max_iter {self.max_iter} mindestens 1, topics.tol {self.tol} positiv"
            )
        if not re.fullmatch(r"[a-z]{0,8}", self.stop_words):
            raise ValueError(f"topics.stop_words {self.stop_words!r}: ein Sprachkürzel oder leer")
        return self


# --- Option 03: Kontextdaten und Kontrollvariablen (docs/plans/03-kontrollvariablen.md) ----------

RATE_TERM = "trefferquote"  # der eine Term, der keine Kontextvariable ist: die Kennzahl der Arbeit


class ContextFile(_Strict):
    """Eine Datei des Kontextdatensatzes: Portal-URL und lokaler Name (unter ``root`` und ``external/``)."""

    url: str
    file: str


class ContextFiles(_Strict):
    table: ContextFile  # Tabelle je Raumeinheit
    units: ContextFile  # Flächen der Raumeinheiten als GeoJSON
    indicators: ContextFile  # Definitionen der Indikatoren

    def all(self) -> tuple[ContextFile, ...]:
        """Die Dateien in fester Reihenfolge: Tabelle, Flächen, Erläuterung."""
        return (self.table, self.units, self.indicators)

    def names(self) -> tuple[str, ...]:
        """Die lokalen Dateinamen; ``bootstrap`` kopiert sie, die Schritte lesen sie aus ``external/``."""
        return tuple(f.file for f in self.all())


class ContextDataset(_Strict):
    """Namensnennung und Stand, nur für die Seite; zählt nicht zum Fingerprint."""

    title: str
    url: str
    publisher: str
    license: str
    license_url: str
    stand: date
    fetched: date  # Abrufdatum der Dateien unter root; gilt, solange der Netzschritt nie lief


class ContextTable(_Strict):
    sep: str = ";"
    encoding: str = "utf-8"
    decimal: str = ","
    missing: list[str] = ["."]  # Marker für fehlende oder anonymisierte Werte
    key: str
    name: str
    indicator: str  # Spalten der Erläuterungsdatei
    definition: str


class ContextUnits(_Strict):
    label: str  # Name der Raumeinheit auf der Seite
    key: str  # GeoJSON-Eigenschaft mit dem Schlüssel der Einheit


VariableKind = Literal["value", "sum", "ordinal", "district"]


class ContextVariable(_Strict):
    name: str
    label: str
    unit: str
    kind: VariableKind
    columns: list[str]
    scale: str | None = None  # nur ordinal
    factor: float = 1.0  # Skalierung der Quellspalten (district: Anteil 0..1 mal 100)
    indicator: str = ""  # Zeile der Erläuterungsdatei mit der Definition; leer = keine

    @model_validator(mode="after")
    def _columns_fit_the_kind(self) -> ContextVariable:
        if not self.columns:
            raise ValueError(f"context.variables {self.name!r}: columns darf nicht leer sein")
        if self.kind != "sum" and len(self.columns) != 1:
            raise ValueError(
                f"context.variables {self.name!r}: kind {self.kind!r} braucht genau eine Spalte"
            )
        if (self.kind == "ordinal") != (self.scale is not None):
            raise ValueError(
                f"context.variables {self.name!r}: scale gehört genau zu kind = 'ordinal'"
            )
        if self.name == RATE_TERM:
            raise ValueError(f"context.variables: {RATE_TERM!r} ist der Term der Trefferquote")
        return self


class ContextModels(_Strict):
    """Termlisten der Modelle; ``single`` nennt je Zeile von Tabelle 6b eine Variable neben der Trefferquote."""

    y_scale: float = 100.0
    main: list[str]
    parties: list[str]
    single: list[str]

    @field_validator("y_scale")
    @classmethod
    def _positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("context.models.y_scale muss positiv sein")
        return value


class ContextSettings(_Strict):
    # None = keine Kontextdaten: die Schritte context_data, context und controls fehlen dann
    root: Path | None
    max_missing_weight: float
    min_coverage: float
    dataset: ContextDataset
    files: ContextFiles
    table: ContextTable
    units: ContextUnits
    scales: dict[str, dict[str, int]]
    variables: list[ContextVariable]
    models: ContextModels

    @field_validator("root", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @field_validator("max_missing_weight", "min_coverage")
    @classmethod
    def _share(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError(f"Anteil {value} liegt nicht in [0, 1]")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> ContextSettings:
        for name, scale in self.scales.items():
            if not scale or len(set(scale.values())) != len(scale):
                raise ValueError(f"context.scales.{name}: Stufen ohne Dubletten in den Werten")
        names = [v.name for v in self.variables]
        if len(names) != len(set(names)):
            raise ValueError(f"context.variables: Namen doppelt: {names}")
        for variable in self.variables:
            if variable.scale is not None and variable.scale not in self.scales:
                raise ValueError(
                    f"context.variables {variable.name!r}: Skala {variable.scale!r} fehlt in context.scales"
                )
        known = {RATE_TERM, *names}
        for model_name in ("main", "parties", "single"):
            terms = getattr(self.models, model_name)
            unknown = [t for t in terms if t not in known]
            if unknown or len(terms) != len(set(terms)):
                raise ValueError(
                    f"context.models.{model_name}: unbekannte oder doppelte Terme {unknown or terms}"
                )
        return self

    def variable(self, name: str) -> ContextVariable:
        return next(v for v in self.variables if v.name == name)

    def unit_variables(self) -> tuple[ContextVariable, ...]:
        """Variablen, die aus der Tabelle je Raumeinheit kommen und umgerechnet werden müssen."""
        return tuple(v for v in self.variables if v.kind != "district")

    def district_variables(self) -> tuple[ContextVariable, ...]:
        """Variablen, die schon je Wahlbezirk vorliegen (Spalten der Wählertabelle)."""
        return tuple(v for v in self.variables if v.kind == "district")


# --- Option 04: Urheber und Parteien -------------------------------------------------------------


def _compiles(patterns: list[str], field: str) -> list[str]:
    """Jedes Muster muss übersetzen; ein Tippfehler in der TOML soll beim Laden auffallen."""
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(
                f"{field}: {pattern!r} ist kein gültiger regulärer Ausdruck ({error})"
            ) from error
    return patterns


class Party(_Strict):
    """Eine Partei, Fraktion oder Gruppe: Schlüssel, Anzeigename, Muster, OParl-Organisationen.

    ``key`` einer ``[[originators.parties]]`` muss in ``columns.results.parties`` stehen (dort
    hängt die Stimmenspalte); ``[[originators.groups]]`` sind Fraktionen ohne Stimmenspalte.
    ``patterns`` sind kleingeschriebene reguläre Ausdrücke, ``organizations`` volle oder teilweise
    OParl-Organisations-URLs, die auf diese Partei zeigen.
    """

    key: str
    label: str
    short: str = ""  # Kürzel für enge Spaltenköpfe; leer = ``label``
    patterns: list[str]
    organizations: list[str] = []

    @property
    def column_label(self) -> str:
        return self.short or self.label

    @field_validator("patterns")
    @classmethod
    def _patterns_compile(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("eine Partei braucht mindestens ein Muster")
        return _compiles(value, "originators.parties[].patterns")


class Originators(_Strict):
    """Wie der Urheber eines Dokuments aus ``paperType``, Titel und Textkopf gelesen wird.

    Alles Stadtspezifische steht hier und nicht im Code (Vorbereitung für Option 10): eine zweite
    Kommune bringt andere ``paperType``-Werte und andere Fraktionsnamen mit.
    """

    admin_types: list[str] = []  # paperType-Werte der Verwaltung: Vorlagen ohne Urheber im Typ
    citizen_types: list[str] = []  # Eingaben nach § 24 GO NRW: Bürgeranträge
    motion_prefixes: list[str] = []  # „Antrag", „Anfrage": davor steht die Art, danach die Partei
    fraction_markers: list[str] = []  # erst mit einem dieser Marker wird der Titel befragt
    joint_markers: list[str] = []  # „interfraktionell": Fraktion ohne nennbare Partei
    person_markers: list[str] = []  # „Bezirksvertreterin": Klasse Person
    text_markers: list[str] = []  # Fenster im Textkopf: Antrag/Anfrage … Fraktion
    name_party_markers: list[str] = []  # schwaches Tor: Antragsklammer ohne das Wort „Fraktion"
    text_head_chars: int = 600  # so viele Zeichen des Texts nach „betrifft" werden gelesen
    text_window_chars: int = 80  # Fenster links und rechts um den Treffer im Textkopf
    parties: list[Party] = []
    groups: list[Party] = []

    @field_validator(
        "fraction_markers",
        "joint_markers",
        "person_markers",
        "text_markers",
        "name_party_markers",
    )
    @classmethod
    def _markers_compile(cls, value: list[str]) -> list[str]:
        return _compiles(value, "originators markers")

    @field_validator("text_head_chars", "text_window_chars")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(f"originators: Zeichenzahl muss positiv sein, nicht {value}")
        return value

    @model_validator(mode="after")
    def _keys_are_unique(self) -> Originators:
        keys = [p.key for p in (*self.parties, *self.groups)]
        doubled = sorted({k for k in keys if keys.count(k) > 1})
        if doubled:
            raise ValueError(f"originators: doppelte Parteischlüssel {doubled}")
        return self

    @property
    def all_keys(self) -> tuple[str, ...]:
        """Alle Schlüssel, Parteien vor Gruppen; die Reihenfolge der Settings bleibt erhalten."""
        return tuple(p.key for p in (*self.parties, *self.groups))


# Option 02: Umrechnung eines älteren Zuschnitts auf die Wahlbezirke der Hauptperiode (Profil "")
class Crosswalk(_Strict):
    enabled: bool = False
    target_file: str = (
        "Stimmbezirke_2025.geojson"  # Stimmbezirksdatei der Hauptperiode (Zielzuschnitt)
    )
    min_coverage: float = 0.95  # kleinste zulässige Abdeckung einer Quellfläche durch die Ziele

    @field_validator("min_coverage")
    @classmethod
    def _coverage_is_a_share(cls, value: float) -> float:
        if not 0.0 < value <= 1.0:
            raise ValueError(f"crosswalk.min_coverage {value}: ein Anteil in (0, 1]")
        return value

    @field_validator("target_file")
    @classmethod
    def _plain_file_name(cls, value: str) -> str:
        if not value or value != Path(value).name:
            raise ValueError(f"crosswalk.target_file {value!r}: ein Dateiname, kein Pfad")
        return value


# Option 02: Vergleich zweier Perioden; läuft auf der Hauptperiode gegen ein Periodenprofil
class Compare(_Strict):
    period: str = ""  # Profil der älteren Periode; leer = kein Schritt compare

    @field_validator("period")
    @classmethod
    def _profile_name(cls, value: str) -> str:
        return _plain_name(value, "compare.period")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GEOREP_", env_nested_delimiter="__", extra="forbid", frozen=True
    )

    data_root: Path = Path("data")
    cache_root: Path | None = None
    reference_root: Path = Path("reference")
    profile: str = (
        ""  # Unterordner je Stadt oder Periode unter data_root und cache_root; leer = flach
    )
    contracts: Literal["on", "off"] = "on"
    log_level: str = "INFO"
    period: Period
    http: HttpSettings = HttpSettings()
    cache: CacheSettings = CacheSettings()
    sources: Sources
    geo: Geo = Geo()
    columns: Columns
    search: Search = Search()
    analysis: Analysis = Analysis()
    bodies: Bodies  # Option 05
    weights: Weights = Weights()  # Option 06
    topics: Topics = Topics()  # Option 06
    context: ContextSettings  # Option 03

    originators: Originators = Originators()  # Option 04
    crosswalk: Crosswalk = Crosswalk()  # Option 02
    compare: Compare = Compare()  # Option 02

    @model_validator(mode="after")
    def _party_keys_have_a_vote_column(self) -> Settings:
        # Option 04: nur ein Schlüssel mit Stimmenspalte bekommt die Hochburg-Kennzahl; Gruppen
        # ohne Spalte gehören in [[originators.groups]], sonst fehlt <Partei>_anteil beim Abgleich.
        unknown = sorted(
            p.key for p in self.originators.parties if p.key not in self.columns.results.parties
        )
        if unknown:
            raise ValueError(
                f"originators.parties: {unknown} stehen nicht in columns.results.parties "
                f"({sorted(self.columns.results.parties)}); ohne Stimmenspalte gehören sie "
                "nach originators.groups"
            )
        return self

    @field_validator("cache_root", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @field_validator("profile")
    @classmethod
    def _profile_is_a_plain_name(cls, value: str) -> str:
        return _plain_name(value, "profile")

    @model_validator(mode="after")
    def _period_profile_is_consistent(self) -> Settings:
        """Option 02: Basiswörterbuch, Crosswalk und Vergleich brauchen einander und ein Profil."""
        columns = self.columns.results
        if self.period.dictionary == "base" and not self.profile:
            raise ValueError(
                'period.dictionary = "base" liest die Hauptperiode und braucht darum ein profile'
            )
        if self.crosswalk.enabled:
            if self.period.dictionary != "base":
                raise ValueError(
                    "crosswalk.enabled rechnet auf den Zuschnitt der Hauptperiode um und braucht "
                    'period.dictionary = "base"'
                )
            empty = [
                key
                for key in ("precinct", "eligible_postal", "postal_marker")
                if not getattr(columns, key)
            ]
            if empty:
                raise ValueError(f"crosswalk.enabled braucht columns.results.{', '.join(empty)}")
        elif not columns.district:
            raise ValueError(
                "columns.results.district ist leer: der Wahlbezirk kommt dann aus der Zuordnung, "
                "dafür muss crosswalk.enabled gesetzt sein"
            )
        if self.compare.period and self.compare.period == self.profile:
            raise ValueError(f"compare.period {self.compare.period!r} ist das eigene Profil")
        return self

    @field_validator("log_level")
    @classmethod
    def _known_level(cls, value: str) -> str:
        level = value.upper()
        if level not in LOG_LEVELS:
            raise ValueError(f"log_level {value!r} ist keiner von {LOG_LEVELS}")
        return level

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Die TOML-Schichten kommen als init-Werte herein; die Umgebung steht davor und gewinnt.
        return (env_settings, init_settings)

    @property
    def cache_dir(self) -> Path:
        return self.cache_root if self.cache_root is not None else self.data_root / "cache"

    def fingerprint(self) -> str:
        """Kurzer Hash aller Parameter, die ein Ergebnis beeinflussen.

        Nicht dabei: Pfade (auch ``profile``, ein Ordnername), Log-Level, Cache-Lebensdauern, der
        Vertragsschalter ``contracts``, denn Verträge prüfen ein Ergebnis, sie ändern es nicht, und
        reine Anzeigewerte (00-synergien.md, § 5.4): ``bodies.names_as_of`` (die Kürzel und Namen
        daneben zählen) und die Beschriftung eines Regelsatzes der Gewichtung -- eine umformulierte
        Überschrift soll nicht die ganze Kette neu rechnen lassen. Option 03: ``context.root`` und
        die lokalen Dateinamen sind Pfade, ``context.dataset`` ist reine Anzeige (Namensnennung,
        Stand, Abrufdatum); URLs, Spalten, Skalen und Modelle zählen.
        Option 02: ``period.label`` und Dateinamen (``sources.opendata.districts_file``,
        ``crosswalk.target_file``) sind Anzeige beziehungsweise Pfad; ``compare.period`` zählt,
        denn es entscheidet, ob die Seite den Vergleich trägt.
        """
        payload = self.model_dump(
            mode="json",
            exclude={
                "data_root": True,
                "cache_root": True,
                "reference_root": True,
                "profile": True,
                "log_level": True,
                "cache": True,
                "contracts": True,
                "bodies": {"names_as_of"},
                # Nur Anzeige: die Beschriftung eines Regelsatzes auf der Berichtsseite.
                "weights": {"paper_type": {"__all__": {"label"}}},
                "context": {
                    "root": True,
                    "dataset": True,
                    "files": {
                        "table": {"file"},
                        "units": {"file"},
                        "indicators": {"file"},
                    },
                },
                "period": {"label"},
                "sources": {"opendata": {"districts_file"}},
                "crosswalk": {"target_file"},
            },
        )
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


# deal.safe, nicht deal.pure: deals has()-Patcher für socket und stdout ist nicht reentrant, und
# deep_merge ruft sich selbst; nach dem Aufruf blieben die Patches stehen (2026-10-11).
@deal.safe
@deal.ensure(
    lambda base, override, result: set(result) == set(base) | set(override),
    message="die Schlüssel sind die Vereinigung beider Tabellen",
)
def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Mischt ``override`` in eine Kopie von ``base``; Tabellen rekursiv, alles andere ersetzt."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def settings_files(explicit: Path | None = None, cwd: Path | None = None) -> list[Path]:
    """Die TOML-Dateien in Leserichtung; nur vorhandene, die explizite muss existieren."""
    here = Path.cwd() if cwd is None else cwd
    candidates = [here / "settings.toml", here / "settings.local.toml"]
    env_file = os.environ.get("GEOREP_SETTINGS")
    if env_file:
        candidates.append(Path(env_file))
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"Settings-Datei fehlt: {explicit}")
        candidates.append(explicit)
    return [p for p in candidates if p.is_file()]


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_settings(explicit: Path | None = None, cwd: Path | None = None) -> Settings:
    defaults_text = (resources.files("georep") / "defaults.toml").read_text(encoding="utf-8")
    merged: dict[str, Any] = tomllib.loads(defaults_text)
    for path in settings_files(explicit, cwd):
        merged = deep_merge(merged, _read_toml(path))
    return Settings(**merged)
