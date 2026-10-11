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
import tomllib
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

LOG_LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Period(_Strict):
    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self) -> Period:
        if self.end < self.start:
            raise ValueError(f"period.end {self.end} liegt vor period.start {self.start}")
        return self


class HttpSettings(_Strict):
    timeout_s: float = 180.0
    retries: int = 5
    user_agent: str = "georep"


class OparlSource(_Strict):
    endpoint: str
    delay_s: float = 1.0


class OpendataSource(_Strict):
    results_url: str
    districts_url: str


class WikidataSource(_Strict):
    sparql_endpoint: str
    wikipedia_api: str
    entity: str
    language: str = "de"
    geosearch_limit: int = 500


class OsmSource(_Strict):
    overpass_endpoint: str
    delay_s: float = 1.0


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


class Columns(_Strict):
    district_id: str
    district_name: str
    precinct_id: str
    results: ResultsColumns


class Search(_Strict):
    text_split_marker: str = "betrifft"
    hide_in_display: list[str] = []
    exclude: list[str] = []


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GEOREP_", env_nested_delimiter="__", extra="forbid", frozen=True
    )

    data_root: Path = Path("data")
    cache_root: Path | None = None
    reference_root: Path = Path("reference")
    contracts: Literal["on", "off"] = "on"
    log_level: str = "INFO"
    period: Period
    http: HttpSettings = HttpSettings()
    cache: CacheSettings = CacheSettings()
    sources: Sources
    geo: Geo = Geo()
    columns: Columns
    search: Search = Search()

    @field_validator("cache_root", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

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
        """Kurzer Hash aller Parameter, die ein Ergebnis beeinflussen; Pfade und Log-Level nicht."""
        payload = self.model_dump(
            mode="json",
            exclude={"data_root", "cache_root", "reference_root", "log_level", "cache"},
        )
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


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
