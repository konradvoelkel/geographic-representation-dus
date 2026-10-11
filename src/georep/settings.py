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


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Period(_Strict):
    """Wahlperiode; ``end`` fehlt bei einer laufenden Periode, dann ist ``election`` Pflicht."""

    start: date
    end: date | None = None
    election: date | None = (
        None  # Wahltag, dessen Ergebnis Nenner und Zuschnitt liefert; Standard: end
    )

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


class HttpSettings(_Strict):
    timeout_s: float = 180.0
    retries: int = 5
    user_agent: str = "georep"


class OparlSource(_Strict):
    endpoint: str
    delay_s: float = 1.0
    stop_when_older: bool = True
    incremental: bool = True
    pdf_limit: int = 0


class OpendataSource(_Strict):
    results_url: str
    districts_url: str


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
    district: str
    eligible: str
    voters: str
    parties: dict[str, str]
    city_district: str  # Option 05: Stadtbezirk je Stimmbezirk, für die Zuordnung der Wahlbezirke


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


class Topics(_Strict):
    """Themenmodell (TF-IDF und NMF); ``k = 0`` schaltet den Schritt ``topics`` ab."""

    k: int = 20
    min_df: int = 5
    max_df: float = 0.5
    max_features: int = 20_000
    top_words: int = 10
    stop_words: str = "de"  # Kürzel der Paketdatei analysis/stopwords_<kürzel>.txt; leer = keine
    random_state: int = 0

    @model_validator(mode="after")
    def _bounds(self) -> Topics:
        if self.k < 0:
            raise ValueError(f"topics.k {self.k} darf nicht negativ sein (0 schaltet ab)")
        if self.min_df < 1 or self.max_features < 1 or self.top_words < 1:
            raise ValueError("topics.min_df, max_features und top_words müssen mindestens 1 sein")
        if not 0.0 < self.max_df <= 1.0:
            raise ValueError(f"topics.max_df {self.max_df} liegt nicht in (0, 1]")
        if not re.fullmatch(r"[a-z]{0,8}", self.stop_words):
            raise ValueError(f"topics.stop_words {self.stop_words!r}: ein Sprachkürzel oder leer")
        return self


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

    @field_validator("cache_root", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @field_validator("profile")
    @classmethod
    def _profile_is_a_plain_name(cls, value: str) -> str:
        if value and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
            raise ValueError(
                f"profile {value!r}: nur Kleinbuchstaben, Ziffern und Bindestriche (ein Ordnername)"
            )
        return value

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

        Nicht dabei: Pfade (auch ``profile``, ein Ordnername), Log-Level, Cache-Lebensdauern und
        der Vertragsschalter ``contracts``, denn Verträge prüfen ein Ergebnis, sie ändern es nicht;
        ``bodies.names_as_of`` ist reine Anzeige (die Kürzel und Namen daneben zählen).
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
