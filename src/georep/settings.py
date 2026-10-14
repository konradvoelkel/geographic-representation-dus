"""Konfiguration: gepackte ``defaults.toml``, darüber TOML-Dateien im Arbeitsverzeichnis, darüber Umgebung.

Reihenfolge (spätere gewinnen): ``defaults.toml`` im Paket < ``profiles/<profil>.toml`` im Paket <
``./settings.toml`` < ``./settings.local.toml`` < ``$GEOREP_SETTINGS`` bzw. ``--settings`` <
Umgebungsvariablen ``GEOREP_<FELD>`` (verschachtelt mit ``__``). Die TOML-Schichten werden tief gemischt, es reicht also der geänderte Schlüssel. Unbekannte
Schlüssel sind ein Fehler (Tippfehler sollen auffallen). Muster wie in Konrads bubatzblick:
``tomllib`` plus pydantic, Begründungen als Kommentar neben der Zahl.

``defaults.toml`` ist stadtneutral; alles Stadtspezifische (Endpunkte, Spaltennamen, Lizenztexte,
Ausschlussliste) steht in genau einer Datei je Stadt unter ``profiles/``. Welches Profil gilt, sagt
``--profile``, sonst ``GEOREP_PROFILE``, sonst ``default_profile`` aus den TOML-Schichten; ein
Profil darf mit ``base`` auf einem anderen aufsetzen (eine Periode derselben Stadt, Option 02)
(docs/plans/01-staedte.md, § 2).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from datetime import date
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, Literal

import deal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from georep.contracts import one_threshold
from georep.errors import GeorepError, SchemaError

LOG_LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
PROFILE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")  # ein Ordnername unter data_root, kein Pfad


class UnknownProfileError(GeorepError):
    """``--profile`` oder ``GEOREP_PROFILE`` nennt ein Profil, das es im Paket nicht gibt."""


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
    # Option 01: auch die übrigen Dateinamen nennt das Profil; leer heißt „gibt es für diese Stadt
    # nicht" (Straßenverzeichnis und Wahlbezirksnamen der votemanager-Präsentation).
    results_file: str = "Stimmbezirk_Wahlergebnis.csv"
    streets_url: str = ""
    streets_file: str = ""
    district_names_url: str = ""
    district_names_file: str = ""

    @field_validator("districts_file", "results_file")
    @classmethod
    def _plain_file_name(cls, value: str) -> str:
        if not value or "/" in value or value != Path(value).name:
            raise ValueError(f"sources.opendata: {value!r} ist ein Dateiname, kein Pfad")
        return value

    @field_validator("streets_file", "district_names_file")
    @classmethod
    def _plain_file_name_or_empty(cls, value: str) -> str:
        if value and ("/" in value or value != Path(value).name):
            raise ValueError(f"sources.opendata: {value!r} ist ein Dateiname, kein Pfad")
        return value

    @model_validator(mode="after")
    def _url_needs_a_file_name(self) -> OpendataSource:
        # Umgekehrt nicht: ein Dateiname ohne URL ist eine Datei, die im Paket der Stadt liegt
        # (reference/<slug>/external/) und nicht abgerufen wird.
        for key, url, file in (
            ("streets", self.streets_url, self.streets_file),
            ("district_names", self.district_names_url, self.district_names_file),
        ):
            if url and not file:
                raise ValueError(f"sources.opendata.{key}_url ohne {key}_file: wohin damit?")
        return self


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
    # Punkt 54: das ``[timeout:…]`` der Abfrage selbst, nicht der Netz-Timeout (``http.timeout_s``).
    # Unter 5 s rechnet keine Instanz die Polygonabfrage durch, über 180 s weist jede sie ab.
    query_timeout_s: int = Field(default=25, ge=5, le=180)
    # Punkt 55: Wiederholungen je Stimmbezirk bei 504 und 429. Nicht ``http.retries``: die Regel
    # der Session erlaubt GET und HEAD, die Overpass-Abfrage ist ein POST.
    retries: int = Field(default=3, ge=0, le=10)


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
    """Die Spalten der Wahlergebnis-CSV dieser Stadt und ihre Abbildung auf die Namen der Arbeit.

    ``parties`` bildet den Schlüssel der Auswertung (``CDU``, ``GRUENE``, …) auf die Quellspalte ab
    (Düsseldorf ``CDU_Stimmen``, votemanager ``D1``); ``party_names`` nennt den Anzeigenamen, wo er
    vom Schlüssel abweicht. Den Wahlbezirk führt entweder eine Spalte (``district``) oder er steckt
    in der Stimmbezirksnummer (``district_from_precinct``), Option 01.
    """

    sep: str = ";"
    encoding: str = "latin-1"
    district: str = ""  # leer: der Wahlbezirk kommt aus der Zuordnung des Crosswalks (Option 02)
    eligible: str
    voters: str
    parties: dict[str, str]
    # Option 05: Stadtbezirk je Stimmbezirk, für die Zuordnung der Wahlbezirke. Leer heißt: die
    # Nummer trägt ihn (``city_district_from_precinct``, Option 01) oder die Stadt führt keinen.
    city_district: str = ""
    precinct: str = ""  # Option 03: Stimmbezirk in der CSV; "" = kein Crosswalk über Stimmbezirke
    # Option 02: Gebietsname je Zeile (darin steht der postal_marker der Briefwahlbezirke),
    # Wahlberechtigte mit Wahlschein (Verteilschlüssel der Briefwahl) und der Marker selbst;
    # die Stimmbezirksnummer steht oben (Option 03).
    precinct_name: str = ""
    eligible_postal: str = ""
    postal_marker: str = ""
    # Option 01: der Wahlbezirk steckt bei votemanager in den Zeichen [start, stop) der
    # Stimmbezirksnummer; ``party_names`` nennt den Anzeigenamen, wo er vom Schlüssel abweicht.
    district_from_precinct: tuple[int, int] | None = None
    # Option 01: ebenso der Stadtbezirk. Mönchengladbach führt Stadtbezirk, Wahlbezirk und
    # Stimmbezirk in einer Nummer (``10401`` → Stadtbezirk 1, Wahlbezirk 4, Stimmbezirk 1).
    city_district_from_precinct: tuple[int, int] | None = None
    party_names: dict[str, str] = {}

    def display_name(self, party: str) -> str:
        """Der Name, wie die Seite ihn schreibt; ohne Eintrag der Schlüssel selbst."""
        return self.party_names.get(party, party)

    @model_validator(mode="after")
    def _one_way_to_the_district(self) -> ResultsColumns:
        if self.district and self.district_from_precinct is not None:
            raise ValueError(
                "columns.results: district und district_from_precinct schließen sich aus"
            )
        if self.city_district and self.city_district_from_precinct is not None:
            raise ValueError(
                "columns.results: city_district und city_district_from_precinct schließen sich aus"
            )
        for name in ("district_from_precinct", "city_district_from_precinct"):
            span: tuple[int, int] | None = getattr(self, name)
            if span is None:
                continue
            start, stop = span
            if not self.precinct:
                raise ValueError(f"columns.results.{name} braucht precinct")
            if not 0 <= start < stop:
                raise ValueError(f"columns.results.{name} {(start, stop)}: [start, stop)")
        unknown = sorted(set(self.party_names) - set(self.parties))
        if unknown:
            raise ValueError(f"columns.results.party_names ohne Partei: {unknown}")
        return self


class Columns(_Strict):
    # Die Eigenschaften der Quellgeometrie; ``read_precincts`` liest damit eine Quelldatei (der
    # Crosswalk einer anderen Periode, Option 02, die Raumeinheiten, Option 03). Der kanonische
    # Stand (Option 01) hat feste Namen und braucht sie nicht: eine Stadt ohne Crosswalk und ohne
    # Fremddaten lässt sie leer, der Validator von ``Settings`` verlangt sie, wo sie nötig sind.
    district_id: str = ""
    district_name: str = ""
    precinct_id: str = ""
    results: ResultsColumns


class Precincts(_Strict):
    """Wie aus der Quellgeometrie die kanonischen Stimmbezirke werden (Option 01, Schritt ``precincts``).

    Die Eigenschaftsnamen und die Regel für den Wahlbezirk sind je Quelle verschieden und stehen
    darum im Profil; ``prep/precincts.py`` ist die einzige Stelle, die sie liest.
    """

    # Option 02: eine Periode mit fremdem Zuschnitt hat keine eigenen Wahlbezirke in der
    # Quellgeometrie; dann entfällt der Schritt ``shapes`` und der Crosswalk ordnet zu.
    enabled: bool = True
    format: Literal["geojson", "shapefile-zip"] = "geojson"
    member: str = ""  # Pfad des .shp im Zip; leer = das einzige im Archiv
    source_crs: str = ""  # nur für GeoJSON ohne crs-Mitglied; Shapefiles bringen ihr .prj mit
    id_property: str = ""  # trägt die Stimmbezirksnummer
    district_property: str = ""  # trägt die Wahlbezirksnummer
    district_from_id: tuple[int, int] | None = None  # sonst: Zeichenausschnitt [start, stop)
    name_property: str = ""  # trägt den Namen des Wahlbezirks
    names_from_results: bool = False  # sonst: Namen aus der Wahlbezirks-CSV der Quelle
    names_id_column: str = "gebiet-nr"  # Spalten dieser CSV (votemanager)
    names_name_column: str = "gebiet-name"
    dbf_encoding: str = "utf-8"  # pyshp liest .dbf oft als latin-1; Fehler werden ersetzt

    @model_validator(mode="after")
    def _exactly_one_rule_each(self) -> Precincts:
        if not self.enabled:
            return self
        if not self.id_property:
            raise ValueError("precincts.id_property fehlt: welche Eigenschaft trägt die Nummer?")
        if bool(self.district_property) == (self.district_from_id is not None):
            raise ValueError("precincts: genau eines von district_property und district_from_id")
        if bool(self.name_property) == self.names_from_results:
            raise ValueError("precincts: genau eines von name_property und names_from_results")
        if (
            self.district_from_id is not None
            and not 0 <= self.district_from_id[0] < (self.district_from_id[1])
        ):
            raise ValueError(f"precincts.district_from_id {self.district_from_id}: [start, stop)")
        return self


class Search(_Strict):
    text_split_marker: str  # Option 01: das Profil nennt ihn, er ist je Stadt verschieden
    hide_in_display: list[str] = []
    exclude: list[str] = []
    # Regel 1 „Einrichtung mit Stadtnamen" (docs/decisions.md, Punkt 44); Begründung je Schlüssel
    # in defaults.toml. ``city_facilities = false`` reproduziert die Arbeit exakt.
    city_facilities: bool = True
    place_words: list[str] = []
    city_facilities_keep: list[str] = []
    # Regel 2 „stadtweite Begriffe": genau eine der beiden Schwellen, beide 0 = keine Liste.
    # Die Regel zeigt nur an, sie ändert keine Zahl (decisions.md, Punkt 44b).
    citywide_quantile: float = 0.0
    citywide_median_factor: float = 0.0

    @field_validator("text_split_marker")
    @classmethod
    def _marker_not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "search.text_split_marker darf nicht leer sein (str.split braucht einen Trenner)"
            )
        return value

    @model_validator(mode="after")
    def _rules_are_usable(self) -> Search:
        # Die Regel „genau eine Schwelle" steht als Prädikat in georep.contracts und prüft
        # damit auch den Vertrag von ``analysis.hits.citywide_terms``.
        if not one_threshold(self.citywide_quantile, self.citywide_median_factor):
            raise ValueError(
                "search: ein Quantil liegt in [0, 1), ein Vielfaches des Medians ist nicht "
                "negativ, und genau eines von citywide_quantile und citywide_median_factor "
                f"gilt; hier {self.citywide_quantile} und {self.citywide_median_factor}"
            )
        # Ohne Gattungswörter wäre Regel 1 still eine andere: „Stadtname zuletzt" allein erklärt
        # jeden Bahnhof und jeden Park mit Stadtnamen zur Einrichtung (decisions.md, Punkt 44a).
        if self.city_facilities and not [word for word in self.place_words if word.strip()]:
            raise ValueError(
                "search.place_words ist leer, obwohl city_facilities an ist: die Regel wäre "
                "dann „Stadtname zuletzt genügt“ und träfe Bahnhöfe und Parks mit. Entweder "
                "Gattungswörter nennen oder city_facilities = false setzen"
            )
        return self


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

    # Option 01: leer heißt „die Nummern dieser Stadt tragen kein Kürzel" (Mönchengladbach:
    # 0682/XI); dann ist jedes Dokument „unbekannt", und die Tabellen bleiben leer.
    reference_pattern: str = ""
    district_body: str = ""
    district_body_name: str = "{n}"  # Anzeigename der Bezirksvertretung, {n} ist der Stadtbezirk
    names_as_of: date | None = None  # Stand der Namen; nur Anzeige, nicht im Fingerprint
    council: dict[str, str] = {}
    committees: dict[str, str] = {}
    advisory: dict[str, str] = {}
    # Punkt 57: eine ältere Nummernform derselben Stadt, deren Kopf kein Kürzel ist. Abbildung
    # „Kopf der Nummer (alles vor dem ersten /) -> Kürzel", nur befragt, wenn das Muster nicht
    # trifft. Ein Ziel, das in keiner Tabelle steht, wäre ein Alias ins Nichts; der Validator
    # unten lässt nur Kürzel zu, die das Profil kennt.
    aliases: dict[str, str] = {}

    @field_validator("reference_pattern")
    @classmethod
    def _pattern_has_code_and_number(cls, value: str) -> str:
        if not value:
            return value
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
        if not self.reference_pattern:
            named = [
                name
                for name in ("district_body", "council", "committees", "advisory", "aliases")
                if getattr(self, name)
            ]
            if named:
                raise ValueError(
                    f"bodies ohne reference_pattern kennt keine Kürzel: bodies.{', '.join(named)}"
                )
            return self
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
        self._aliases_resolve(seen)
        return self

    def _aliases_resolve(self, seen: dict[str, str]) -> None:
        """Jedes Ziel in ``bodies.aliases`` muss ein Kürzel sein, das dieses Profil kennt.

        Sonst übersetzte das Profil eine alte Nummernform in ein Gremium, das es nicht gibt -- und
        das Ergebnis wäre „unbekannt" mit einem erfundenen Kürzel daneben (Punkt 57).
        """
        for head, code in self.aliases.items():
            if not head or "/" in head:
                raise ValueError(
                    f"bodies.aliases: {head!r} ist kein Kopf einer Nummer (leer oder mit /)"
                )
            number = code.removeprefix(self.district_body) if code != self.district_body else ""
            is_district = (
                code.startswith(self.district_body)
                and number.isascii()
                and number.isdigit()
                and int(number) >= 1
            )
            if not is_district and code not in seen:
                raise ValueError(
                    f"bodies.aliases: {head!r} zeigt auf {code!r}, und das steht in keiner Tabelle"
                )

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
# Punkt 45: woher die Stoppwörter neben der Paketliste kommen. „fraktionen" und „gremien" lesen das
# Profil (Option 04 und 05), „namen" den Korpus; der Code kennt keine Partei und kein Gremium.
STOP_SOURCES = ("fraktionen", "gremien", "namen")
SEEDS = ("none", "committees")  # Punkt 45: woraus die Saat des Themenmodells kommt


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
    # Punkt 45: Stoppwörter aus dem Profil und aus dem Korpus, Saat je Ausschuss
    stop_sources: list[str] = []  # Teilmenge von STOP_SOURCES; leer = nur die Paketliste
    stop_keep: list[str] = []  # Wörter, die trotz einer Quelle bleiben (Sachwort in einem Namen)
    name_markers: list[str] = []  # Unterschrift und Amtsbezeichnung; dahinter steht ein Name
    name_window: int = 60  # Zeichen hinter dem Marker
    name_min_documents: int = 5  # so viele Fenster muss ein Wort haben, sonst ist es ein Tippfehler
    name_share: float = 0.8  # und so viel seiner Dokumente müssen Fenster sein
    seed: str = "none"  # eines aus SEEDS
    free: int = 0  # Themen ohne Saat; die gesäten sind ``k - free`` viele, höchstens die Ausschüsse
    seed_words: int = 30  # Saatwörter je Ausschuss (Log-Odds mit Dirichlet-Prior)
    seed_min_documents: int = 10  # weniger beratene Dokumente, kein eigenes Thema
    seed_prior: float = 1000.0  # Stärke des Dirichlet-Priors in Pseudo-Token

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
        unknown = [s for s in self.stop_sources if s not in STOP_SOURCES]
        if unknown or len(self.stop_sources) != len(set(self.stop_sources)):
            raise ValueError(
                f"topics.stop_sources {self.stop_sources}: unbekannte oder doppelte Quelle; "
                f"bekannt sind {list(STOP_SOURCES)}"
            )
        if self.name_window < 1 or self.name_min_documents < 1:
            raise ValueError("topics.name_window und name_min_documents müssen mindestens 1 sein")
        if not 0.0 < self.name_share <= 1.0:
            raise ValueError(f"topics.name_share {self.name_share} liegt nicht in (0, 1]")
        if self.seed not in SEEDS:
            raise ValueError(f"topics.seed {self.seed!r}: eines aus {list(SEEDS)}")
        if self.free < 0 or (self.k > 0 and self.free > self.k):
            # Mit ``k = 0`` ist das Themenmodell aus, und ``free`` sagt nichts mehr.
            raise ValueError(f"topics.free {self.free} liegt nicht zwischen 0 und k = {self.k}")
        if self.seed_words < 1 or self.seed_min_documents < 1 or not self.seed_prior > 0.0:
            raise ValueError(
                "topics.seed_words, seed_min_documents und seed_prior müssen positiv sein"
            )
        return self


class Classify(_Strict):
    """Punkt 45: der passende Ausschuss je Dokument (TF-IDF und logistische Regression).

    Die Textdarstellung kommt aus ``[topics]`` (Tokenmuster, ``min_df``, ``max_df``,
    ``max_features``, Stoppwörter): es gibt eine Wahrheit darüber, was ein Wort ist, und sie steht
    dort. Hier stehen nur die Parameter des Klassifikators.
    """

    enabled: bool = True  # false nimmt den Schritt aus dem Register
    min_documents: int = 10  # eine Klasse braucht so viele beratene Dokumente
    min_probability: float = 0.4  # darunter: Restklasse (querschnittliche Vorlage)
    regularisation: float = 1.0  # C der logistischen Regression
    max_iterations: int = 1000  # lbfgs
    random_state: int = 0

    @model_validator(mode="after")
    def _bounds(self) -> Classify:
        if self.min_documents < 5:
            # Fünf Faltungen brauchen fünf Dokumente; darunter ist eine Klasse nicht messbar.
            raise ValueError(f"classify.min_documents {self.min_documents} ist kleiner als 5")
        if not 0.0 < self.min_probability < 1.0:
            raise ValueError(
                f"classify.min_probability {self.min_probability} liegt nicht in (0, 1)"
            )
        if not self.regularisation > 0.0 or self.max_iterations < 1:
            raise ValueError("classify.regularisation und max_iterations müssen positiv sein")
        return self


# --- Option 03: Kontextdaten und Kontrollvariablen (docs/plans/03-kontrollvariablen.md) ----------

RATE_TERM = "trefferquote"  # der eine Term, der keine Kontextvariable ist: die Kennzahl der Arbeit


class ContextFile(_Strict):
    """Eine Datei des Kontextdatensatzes: Portal-URL und lokaler Name (unter ``root`` und ``external/``)."""

    url: str = ""
    file: str = ""


class ContextFiles(_Strict):
    table: ContextFile = ContextFile()  # Tabelle je Raumeinheit
    units: ContextFile = ContextFile()  # Flächen der Raumeinheiten als GeoJSON
    indicators: ContextFile = ContextFile()  # Definitionen der Indikatoren

    def all(self) -> tuple[ContextFile, ...]:
        """Die Dateien in fester Reihenfolge: Tabelle, Flächen, Erläuterung."""
        return (self.table, self.units, self.indicators)

    def names(self) -> tuple[str, ...]:
        """Die lokalen Dateinamen; ``bootstrap`` kopiert sie, die Schritte lesen sie aus ``external/``."""
        return tuple(f.file for f in self.all())


class ContextDataset(_Strict):
    """Namensnennung und Stand, nur für die Seite; zählt nicht zum Fingerprint."""

    title: str = ""
    url: str = ""
    publisher: str = ""
    license: str = ""
    license_url: str = ""
    # Option 01: ohne Kontextdaten gibt es keinen Stand; der Validator unten verlangt beide
    # Daten, sobald ``context.root`` auf einen Datensatz zeigt.
    stand: date | None = None
    # Abrufdatum der Dateien unter root; gilt, solange der Netzschritt nie lief
    fetched: date | None = None


class ContextTable(_Strict):
    sep: str = ";"
    encoding: str = "utf-8"
    decimal: str = ","
    missing: list[str] = ["."]  # Marker für fehlende oder anonymisierte Werte
    key: str = ""
    name: str = ""
    indicator: str = ""  # Spalten der Erläuterungsdatei
    definition: str = ""


class ContextUnits(_Strict):
    label: str = ""  # Name der Raumeinheit auf der Seite
    key: str = ""  # GeoJSON-Eigenschaft mit dem Schlüssel der Einheit


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
    main: list[str] = []
    parties: list[str] = []
    single: list[str] = []

    @field_validator("y_scale")
    @classmethod
    def _positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("context.models.y_scale muss positiv sein")
        return value


class ContextSettings(_Strict):
    # None = keine Kontextdaten: die Schritte context_data, context und controls fehlen dann
    root: Path | None = None
    max_missing_weight: float = 0.1
    min_coverage: float = 0.9
    dataset: ContextDataset = ContextDataset()
    files: ContextFiles = ContextFiles()
    table: ContextTable = ContextTable()
    units: ContextUnits = ContextUnits()
    scales: dict[str, dict[str, int]] = {}
    variables: list[ContextVariable] = []
    models: ContextModels = ContextModels()

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
        # Option 01: eine Stadt ohne Kontextdatensatz lässt den ganzen Block weg; wer ihn hat,
        # muss ihn vollständig beschreiben, denn die Namensnennung der Lizenz hängt daran.
        if self.root is not None:
            missing = [
                f"context.{name}"
                for name, value in (
                    ("dataset.title", self.dataset.title),
                    ("dataset.url", self.dataset.url),
                    ("dataset.publisher", self.dataset.publisher),
                    ("dataset.stand", self.dataset.stand),
                    ("dataset.fetched", self.dataset.fetched),
                    ("files.table.file", self.files.table.file),
                    ("files.units.file", self.files.units.file),
                    ("table.key", self.table.key),
                    ("units.key", self.units.key),
                    ("variables", self.variables),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"context.root ist gesetzt, es fehlen: {', '.join(missing)}")
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
    # Eigenschaften der beiden GeoJSON-Dateien des alten Zuschnitts; ``[columns]`` beschreibt
    # weiter den Zielzuschnitt, damit die Berichtsseite des Profils ihn unverändert liest.
    precinct_id: str = ""  # Stimmbezirksnummer im Stimmbezirks-GeoJSON der Periode
    district_id: str = ""  # Wahlbezirksnummer in Kommunalwahlbezirke.geojson
    district_name: str = ""  # Wahlbezirksname dort
    min_coverage: float = 0.95  # kleinste zulässige Abdeckung einer Quellfläche durch die Ziele
    # Punkt 51: kleinster Anteil der Quellfläche, der als Schnittstück zählt. Darunter ist es ein
    # Splitter aus der Fließkomma-Arithmetik (eine geteilte Grenze schneidet sich in ~4,44e-16)
    # und fällt vor der Normierung weg; 0 schaltet die Schwelle ab. Die Zahl steht hier als
    # Literal und nicht als Import von ``crosswalk.MIN_SHARE``: ``georep.geo`` liest die Settings,
    # und ``crosswalk`` liest ``geo`` -- der Import wäre ein Zyklus. Ein Test hält beide zusammen
    # (``tests/unit/test_crosswalk.py``).
    min_share: float = 1e-9

    @field_validator("min_coverage")
    @classmethod
    def _coverage_is_a_share(cls, value: float) -> float:
        if not 0.0 < value <= 1.0:
            raise ValueError(f"crosswalk.min_coverage {value}: ein Anteil in (0, 1]")
        return value

    @field_validator("min_share")
    @classmethod
    def _threshold_is_a_small_share(cls, value: float) -> float:
        if not 0.0 <= value < 1.0:
            raise ValueError(f"crosswalk.min_share {value}: ein Anteil in [0, 1)")
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
    # Anzeigename der älteren Periode in der Vergleichstabelle; leer = der Profilname. Er steht in
    # der Parquet-Datei und zählt darum zum Fingerprint, anders als period.label.
    label: str = ""

    @field_validator("period")
    @classmethod
    def _profile_name(cls, value: str) -> str:
        return _plain_name(value, "compare.period")


# --- Option 01: Stadt, Quellen der Seite, Veröffentlichung ---------------------------------------


class City(_Strict):
    """Die Stadt in Worten: alles, was auf der Seite steht, statt eines Literals im Code.

    ``slug`` ist der Ordnername im veröffentlichten Ordner und der Schlüssel in ``publish.cities``;
    er muss dem Dateinamen des Profils gleichen (``profiles/<slug>.toml``).
    """

    slug: str
    name: str  # „Düsseldorf"
    genitive: str  # „Düsseldorfs"
    adjective: str  # „Düsseldorfer"
    ags: str  # Amtlicher Gemeindeschlüssel, achtstellig; Schlüssel der votemanager-Dateien
    publisher: str  # Herausgeber der amtlichen Daten, wörtlich für den Fuß der Seite
    council: str = "Stadtrat"
    election: str = "Ratswahl"  # Name der Wahl, deren Ergebnis die Nenner liefert

    @field_validator("slug")
    @classmethod
    def _slug_is_a_plain_name(cls, value: str) -> str:
        if not PROFILE_NAME.fullmatch(value):
            raise ValueError(f"city.slug {value!r}: nur Kleinbuchstaben, Ziffern und Bindestriche")
        return value

    @field_validator("ags")
    @classmethod
    def _ags_has_eight_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{8}", value):
            raise ValueError(f"city.ags {value!r}: achtstelliger amtlicher Gemeindeschlüssel")
        return value


class ReportSource(_Strict):
    """Eine Quelle, wie sie im Fuß der Seite steht: Name, Herausgeber, Link, Lizenz, Prüfdatum.

    Die Links sind per Konstruktion erlaubt (``render.allowed_links``); ein leeres ``license``
    heißt „vom Anbieter nicht angegeben" und wird auch so gedruckt (Frage 1.4).
    """

    name: str
    publisher: str
    url: str
    license: str = ""
    license_url: str = ""
    checked: date | None = None

    @field_validator("url", "license_url")
    @classmethod
    def _https(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            raise ValueError(f"report.sources: {value!r} ist keine https-URL")
        return value

    @model_validator(mode="after")
    def _license_link_needs_a_license(self) -> ReportSource:
        if self.license_url and not self.license:
            raise ValueError(f"report.sources {self.name!r}: Lizenz-Link ohne Lizenzname")
        return self


DOI = re.compile(r"10\.\d{4,9}/\S+")  # Präfix „10.", Registrant, Schrägstrich, Suffix
LITERATURE_KEY = re.compile(r"[a-z][a-z0-9-]*")  # wird zur Anker-ID ``lit-<key>`` auf der Seite


class LiteratureEntry(_Strict):
    """Ein Eintrag der Literaturübersicht (``docs/todo.md``, Punkt 5).

    Die stadtneutralen Einträge stehen in ``report/literatur.toml``, stadtspezifische als
    ``[[report.literature]]`` im Profil; beide werden mit diesem Modell gelesen
    (``georep.report.literature``). ``note`` trägt den einen oder zwei Sätzen, was die Arbeit
    beiträgt und wie dieses Vorhaben sich dazu verhält — ohne sie wäre die Liste eine Linksammlung.
    ``pending`` markiert einen Eintrag, dessen Angaben nachzutragen sind (die Arbeit, auf der dieses
    Programm aufsetzt, ist nicht öffentlich, und ihr Titel steht nirgends im Repo); die Seite sagt
    das sichtbar, statt eine Zitation zu behaupten, die nicht geprüft ist. Bei ``pending`` darf
    neben Jahr und Link auch ``title`` leer bleiben -- ein formulierter Titel in einem ``<cite>``
    wäre eine Behauptung, und die Vorlage schreibt stattdessen „[Titel nachzutragen]".
    """

    key: str
    authors: str
    venue: str  # Ort oder Institution: Hochschule, Verlag, Herausgeber, Plattform
    # Wörtlich wie auf der Titelseite oder in der Beschreibung der Quelle. Leer ist nur mit
    # ``pending`` erlaubt und heißt „der Titel ist nicht bekannt": die Seite schreibt dann
    # „[Titel nachzutragen]", statt eine Formulierung in ein ``<cite>`` zu setzen.
    title: str = ""
    year: int | None = None  # Pflicht, außer bei ``pending``
    url: str = ""
    doi: str = ""
    accessed: date | None = None  # Abrufdatum; bei einer URL Pflicht, bei einem DOI nicht
    # Ein oder zwei Sätze, was die Arbeit beiträgt und wie dieses Vorhaben sich dazu verhält.
    # Pflicht: ohne sie wäre die Übersicht eine Linksammlung, und der Vergleich mit dem README
    # (tests/unit/test_report_literature.py) wäre für einen leeren Wert tautologisch.
    note: str
    pending: bool = False  # Angaben nachzutragen; die Seite schreibt es dazu

    @field_validator("key")
    @classmethod
    def _key_is_an_anchor(cls, value: str) -> str:
        if not LITERATURE_KEY.fullmatch(value):
            raise ValueError(f"literature.key {value!r}: Kleinbuchstaben, Ziffern und Bindestriche")
        return value

    @field_validator("authors", "venue")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("literature: Autor und Ort oder Institution sind Pflicht")
        return value

    @field_validator("note")
    @classmethod
    def _says_what_it_contributes(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("literature.note: ein Satz zum Beitrag gehört zu jedem Eintrag")
        return value

    @field_validator("accessed")
    @classmethod
    def _plausible_date(cls, value: date | None) -> date | None:
        """Ein festes Fenster, kein Vergleich mit heute.

        Die untere Grenze ist das Jahr, in dem das Web öffentlich wurde: ein Abrufdatum davor ist
        ein Tippfehler, keine Angabe. „Nicht nach heute" wäre oben genauer, holte aber die Uhr in
        die Validierung der Settings, und Zeit ist in diesem Programm eine Eingabe, kein
        Seiteneffekt (docs/decisions.md, Punkt 10): dieselbe Datei wäre morgen gültig und gestern
        nicht, und ein Testlauf hinge am Kalender. Das Fenster fängt, was es fangen soll -- 1969
        oder 2126 (Review 2026-10-13).
        """
        if value is not None and not 1990 <= value.year <= 2100:
            raise ValueError(f"literature.accessed {value}: ein Abrufdatum zwischen 1990 und 2100")
        return value

    @field_validator("year")
    @classmethod
    def _plausible_year(cls, value: int | None) -> int | None:
        if value is not None and not 1900 <= value <= 2100:
            raise ValueError(f"literature.year {value}: eine Jahreszahl zwischen 1900 und 2100")
        return value

    @field_validator("url")
    @classmethod
    def _https(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            raise ValueError(f"literature.url: {value!r} ist keine https-URL")
        return value

    @field_validator("doi")
    @classmethod
    def _looks_like_a_doi(cls, value: str) -> str:
        if value and not DOI.fullmatch(value):
            raise ValueError(f"literature.doi {value!r}: ein DOI beginnt mit 10. und trägt ein /")
        return value

    @model_validator(mode="after")
    def _findable_and_dated(self) -> LiteratureEntry:
        """Ohne URL oder DOI ist ein Eintrag nicht nachprüfbar, und eine URL braucht ein Datum.

        Die eine Ausnahme ist ``pending``: ein Eintrag, der aus dem Literaturverzeichnis einer
        nicht öffentlichen Arbeit nachzutragen ist, hat noch keinen Link, kein Jahr und
        womöglich keinen bekannten Titel. Er steht trotzdem auf der Seite, damit die Lücke
        benannt ist und nicht vergessen wird; Autor und Ort oder Institution bleiben auch dann
        Pflicht, und sei es als „nachzutragen".
        """
        if not self.pending and not self.title.strip():
            raise ValueError(f"literature {self.key!r}: ohne pending ist der Titel Pflicht")
        if not self.pending and not self.url and not self.doi:
            raise ValueError(f"literature {self.key!r}: entweder url oder doi muss dastehen")
        if not self.pending and self.year is None:
            raise ValueError(f"literature {self.key!r}: ohne pending gehört ein Jahr dazu")
        if self.url and self.accessed is None:
            raise ValueError(f"literature {self.key!r}: eine URL braucht ein Abrufdatum")
        return self

    @property
    def doi_url(self) -> str:
        """Der DOI als Link; leer ohne DOI. Steht in der Allowlist der Seite (``model_links``)."""
        return f"https://doi.org/{self.doi}" if self.doi else ""

    @property
    def links(self) -> tuple[str, ...]:
        """Alle Links, die dieser Eintrag auf die Seite bringt; ``render.model_links`` liest sie."""
        return tuple(link for link in (self.doi_url, self.url) if link)


# Punkt 46: die festen Klassengrenzen der divergierenden Varianten. Sie stehen unter ``[report]``
# und zählen damit nicht zum Fingerprint: eine andere Grenze färbt die Karte um, sie rechnet keine
# Zahl neu.
class Diverging(_Strict):
    """Klassengrenzen der Varianten „relativ zum Mittel" (``docs/skalierung-2026-10.md``, § 3, § 4).

    Vier Grenzen ergeben fünf Klassen, die mittlere heißt „etwa im Mittel". Quantile wären hier
    falsch: die Abweichung vom Stadtmittel ist eine streng monotone Umrechnung der Trefferquote,
    und Quantilklassen darüber wären genau die Klassen der Quote, nur anders gefärbt.
    """

    district_percent: list[float] = [-0.25, -0.10, 0.10, 0.25]
    party_points: list[float] = [-0.02, -0.005, 0.005, 0.02]
    party_ratio: list[float] = [0.5, 0.8, 1.25, 2.0]

    @field_validator("district_percent", "party_points", "party_ratio")
    @classmethod
    def _four_ascending_boundaries(cls, value: list[float]) -> list[float]:
        if len(value) != 4:
            raise ValueError(f"report.diverging: vier Grenzen ergeben fünf Klassen, {value} nicht")
        if any(a >= b for a, b in zip(value, value[1:], strict=False)):
            raise ValueError(f"report.diverging {value}: die Grenzen müssen aufsteigen")
        return value

    @model_validator(mode="after")
    def _the_middle_class_holds_the_middle(self) -> Diverging:
        """Die mittlere Klasse muss das Mittel einschließen, sonst divergiert nichts.

        Eine Abweichung ist um 0 neutral, ein Verhältnis um 1; liegen beide Innengrenzen auf
        derselben Seite davon, heißt „die Mitte" eine Klasse, in der niemand im Mittel liegt, und
        orange gegen blau bedeutet nicht mehr „darunter gegen darüber".
        """
        for name, neutral in (
            ("district_percent", 0.0),
            ("party_points", 0.0),
            ("party_ratio", 1.0),
        ):
            inner = getattr(self, name)[1:3]
            if not inner[0] < neutral < inner[1]:
                raise ValueError(
                    f"report.diverging.{name} {getattr(self, name)}: die mittlere Klasse muss "
                    f"{neutral:g} einschließen"
                )
        return self


class Report(_Strict):
    """Was im Kopf und Fuß der Seite steht und nicht aus den Daten kommt."""

    sources: list[ReportSource] = []
    # Punkt 47: stadtspezifische Literatur (die Arbeit zu dieser Stadt). Die stadtneutralen
    # Einträge stehen nicht hier, sondern in ``report/literatur.toml``: ``deep_merge`` ersetzt
    # Listen, ein Profil könnte die Paketliste also nur überschreiben, nicht ergänzen.
    literature: list[LiteratureEntry] = []
    ris_url: str = ""  # Ratsinformationssystem, für den Satz über die Dokumente
    # Punkt 48: so viele Zeilen zeigt eine lange Tabelle, bevor die Schaltfläche kommt. 0 heißt
    # „nichts einklappen"; mehr als 50 wäre keine Vorschau mehr (die längste Tabelle der Seite
    # ist die Monatsreihe mit 61 Zeilen).
    table_preview_rows: int = Field(default=3, ge=0, le=50)
    # Punkt 50: das Budget der Seite. Der Schritt ``report`` meldet eine Überschreitung in seiner
    # Zeile, der slow-Test prüft dieselbe Zahl; 0 schaltet beides ab. Eine Verabredung, keine
    # Grenze der Technik (docs/seitengroesse-2026-10.md, § 7).
    page_budget_bytes: int = Field(default=1_000_000, ge=0)
    notes: list[str] = []  # Sätze, die nur für diese Stadt in „Methode und Grenzen" gehören
    data_note: str = ""  # woher Straßen und Orte stammen, wenn kein Netzschritt gelaufen ist
    # Option 07: Teile der Seite, die eine laufende Periode nicht hat oder zusätzlich trägt.
    regression: bool = (
        True  # False: kein Streudiagramm, keine Tabelle 5, kein Umschalter Wahlbeteiligung
    )
    monitoring_url: str = (
        ""  # relativer Link auf die Seite der laufenden Periode; leer = kein Abschnitt
    )
    # Punkt 46: die Grenzen der divergierenden Varianten; je Stadt änderbar, siehe Diverging
    diverging: Diverging = Diverging()

    @field_validator("monitoring_url")
    @classmethod
    def _relative_link(cls, value: str) -> str:
        # Die Seite erlaubt nach außen nur die Links der Allowlist (report.render); der Link auf die
        # laufende Periode ist ein Unterordner derselben Dokumentwurzel, nie ein fremder Host.
        if "://" in value or value.startswith("//"):
            raise ValueError(
                f"report.monitoring_url {value!r}: nur ein relativer Link (kein ://, kein //)"
            )
        return value


class Publish(_Strict):
    """Welche Städte ``georep publish`` zusammenträgt; die erste liegt an der Wurzel."""

    cities: list[str] = []

    @field_validator("cities")
    @classmethod
    def _plain_unique_slugs(cls, value: list[str]) -> list[str]:
        wrong = [c for c in value if not PROFILE_NAME.fullmatch(c)]
        if wrong:
            raise ValueError(f"publish.cities {wrong}: keine Ordnernamen")
        if len(set(value)) != len(value):
            raise ValueError(f"publish.cities {value}: jede Stadt höchstens einmal")
        return value


# Option 07: Monitoring der laufenden Wahlperiode
class Bootstrap(_Strict):
    """Was ``georep bootstrap`` aus der Referenz übernimmt; ein Profil mit laufender Periode füllt keine Stores."""

    seed_corpus: bool = (
        True  # False: nur die Eingaben kopieren, papers.jsonl und Textstore bleiben leer
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GEOREP_",
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    data_root: Path = Path("data")
    cache_root: Path | None = None
    reference_root: Path = Path("reference")
    # Unterordner je Stadt oder Periode unter data_root und cache_root; leer = flach. Der Wert
    # kommt aus dem Profil, nie aus GEOREP_PROFILE: das wählt nur das Profil (siehe
    # load_settings). Jedes Paketprofil setzt ihn — eine Stadt ihren Slug, eine Periode ihren
    # Namen (Punkt 52, Frage 1.7); flach ist seitdem nur noch, was jemand von Hand leert.
    # Darum der Alias: GEOREP_PROFILE landet nicht hier. Der Alias trägt das Präfix selbst, weil
    # pydantic-settings es auf Aliase nicht anwendet — ohne es setzte eine nackte Variable
    # PROFILE_FOLDER den Ordner (Review 2026-10-12). Die TOML-Schichten schreiben weiter `profile`.
    profile: str = Field("", validation_alias=AliasChoices("georep_profile_folder"))
    contracts: Literal["on", "off"] = "on"
    log_level: str = "INFO"
    period: Period
    http: HttpSettings = HttpSettings()
    cache: CacheSettings = CacheSettings()
    sources: Sources
    geo: Geo = Geo()
    columns: Columns
    search: Search
    analysis: Analysis = Analysis()
    bodies: Bodies = Bodies()  # Option 05; leer: die Nummern tragen kein Kürzel (Option 01)
    weights: Weights = Weights()  # Option 06
    topics: Topics = Topics()  # Option 06
    context: ContextSettings = ContextSettings()  # Option 03; leer: keine Kontextdaten (Option 01)

    originators: Originators = Originators()  # Option 04
    crosswalk: Crosswalk = Crosswalk()  # Option 02
    compare: Compare = Compare()  # Option 02
    precincts: Precincts  # Option 01: Regeln der Quellgeometrie, je Stadt im Profil
    # Option 01: der gewählte Profilname (``load_settings`` schreibt ihn hierher), die Stadt in
    # Worten, die Quellen für Kopf und Fuß der Seite und die Städte der Veröffentlichung.
    default_profile: str = ""
    city: City
    report: Report = Report()
    bootstrap: Bootstrap = Bootstrap()  # Option 07
    publish: Publish = Publish()
    classify: Classify = Classify()  # Punkt 45: passender Ausschuss je Dokument

    @property
    def base_profile(self) -> str:
        """Der Ordner der Hauptperiode dieser Stadt: ihr Slug (Punkt 52).

        Dort liegt, was eine Periode derselben Stadt von der Hauptperiode liest: das Wörterbuch
        (``period.dictionary = "base"``) und der Zuschnitt der Wahlbezirke
        (``crosswalk.enabled``, ``Layout.target_view``). Der Slug ist der Dateiname des
        Stadtprofils (``_slugs_match_their_file``), und eine Periode erbt ihn über ``base``.
        Dass die Hauptperiode wirklich dort rechnet, hält ein Test über alle Paketprofile fest
        (``tests/unit/test_settings.py``); dass ein Profil mit dem Wörterbuch der Hauptperiode
        einen anderen Ordner hat, verlangt ``_period_profile_is_consistent``.
        """
        return self.city.slug

    @model_validator(mode="after")
    def _context_needs_the_geometry_columns(self) -> Settings:
        """Option 03 liest die Stimmbezirke als Quelldatei; dann müssen ihre Spalten dastehen."""
        if self.context.root is not None and not self.columns.precinct_id:
            raise ValueError(
                "context.root ist gesetzt: columns.precinct_id, district_id und district_name "
                "nennen die Eigenschaften der Quellgeometrie und sind dann Pflicht"
            )
        return self

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
        if self.period.dictionary == "base":
            # Zwei Faelle, zwei Saetze: derselbe Ordner ist derselbe Lauf, und die leere Angabe
            # ist gar kein Ordner, sondern die Wurzel darueber (Review 2026-10-13).
            if self.profile == self.base_profile:
                raise ValueError(
                    'period.dictionary = "base" liest die Hauptperiode unter profile '
                    f"{self.base_profile!r}; mit demselben profile wäre das derselbe Lauf"
                )
            if not self.profile:
                raise ValueError(
                    'period.dictionary = "base" liest die Hauptperiode unter profile '
                    f'{self.base_profile!r} und braucht einen eigenen Ordner; profile = "" '
                    "ist die Datenwurzel selbst, in der die Ordner der Profile und site/ liegen"
                )
        if self.crosswalk.enabled:
            if self.period.dictionary != "base":
                raise ValueError(
                    "crosswalk.enabled rechnet auf den Zuschnitt der Hauptperiode um und braucht "
                    'period.dictionary = "base"'
                )
            empty = [
                key
                for key in ("precinct", "precinct_name", "eligible_postal", "postal_marker")
                if not getattr(columns, key)
            ]
            if empty:
                raise ValueError(f"crosswalk.enabled braucht columns.results.{', '.join(empty)}")
            blank = [
                key
                for key in ("precinct_id", "district_id", "district_name")
                if not getattr(self.crosswalk, key)
            ]
            if blank:
                raise ValueError(f"crosswalk.enabled braucht crosswalk.{', '.join(blank)}")
            # Option 01: der Crosswalk liest den Zielzuschnitt als Quelldatei, mit diesen Namen
            unnamed = [
                key
                for key in ("district_id", "district_name", "precinct_id")
                if not getattr(self.columns, key)
            ]
            if unnamed:
                raise ValueError(f"crosswalk.enabled braucht columns.{', '.join(unnamed)}")
        elif not columns.district and columns.district_from_precinct is None:
            raise ValueError(
                "columns.results.district ist leer: der Wahlbezirk kommt dann aus der Zuordnung "
                "(crosswalk.enabled) oder aus der Stimmbezirksnummer (district_from_precinct)"
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
        Option 07: ``bootstrap`` sagt, was kopiert wird, und ``report`` ist Anzeige; kein
        Parquet-Ergebnis hängt an einem der beiden.
        """
        payload = self.model_dump(
            mode="json",
            exclude={
                "data_root": True,
                "cache_root": True,
                "reference_root": True,
                "profile": True,
                # Option 01: die Auswahl der Schicht und die Anzeigetexte der Seite zählen nicht,
                # die Stadt und die Liste der veröffentlichten Städte zählen.
                "default_profile": True,
                "report": True,
                "bootstrap": True,  # Option 07: was bootstrap kopiert, ändert kein Ergebnis
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


# --- Option 01: Paketprofile ---------------------------------------------------------------------

PROFILE_ENV = "GEOREP_PROFILE"
MAX_PROFILE_DEPTH = 4  # Stadt, Periode, Variante; tiefer wird niemand lesen


def profiles_folder() -> Traversable:
    return resources.files("georep") / "profiles"


# Benannter Validator, weil das Argument optional ist: ein Lambda bekäme es nicht (CLAUDE.md, deal).
def _profiles_sorted(folder: Traversable | None = None, result: list[str] | None = None) -> bool:
    return result is not None and result == sorted(result)


@deal.ensure(
    _profiles_sorted, message="Profile alphabetisch, damit Listen und Fehlermeldungen stabil sind"
)
def available_profiles(folder: Traversable | None = None) -> list[str]:
    """Die Namen der Paketprofile (``profiles/<name>.toml``), alphabetisch."""
    return sorted(
        entry.name.removesuffix(".toml")
        for entry in (folder or profiles_folder()).iterdir()
        if entry.name.endswith(".toml")
    )


def _read_profile(name: str, folder: Traversable | None = None) -> dict[str, Any]:
    known = available_profiles(folder)
    if name not in known:
        raise UnknownProfileError(f"Profil {name!r} gibt es nicht; vorhanden: {', '.join(known)}")
    return tomllib.loads(((folder or profiles_folder()) / f"{name}.toml").read_text("utf-8"))


def profile_chain(name: str, folder: Traversable | None = None) -> list[str]:
    """Das Profil und die Profile, auf denen es aufsetzt, von der Wurzel an.

    Eine Periode oder Variante derselben Stadt setzt mit ``base = "<stadt>"`` auf deren Profil auf
    und überschreibt nur, was anders ist (Option 02 als Periode von Option 01); die Stadt selbst
    hat kein ``base``. So steht ``[city]`` genau einmal im Paket.
    """
    chain: list[str] = []
    current = name
    while current:
        if current in chain:
            raise SchemaError(f"Profile verweisen im Kreis: {[*chain, current]}")
        chain.insert(0, current)
        if len(chain) > MAX_PROFILE_DEPTH:
            raise SchemaError(f"Profilkette zu tief: {chain}")
        current = str(_read_profile(current, folder).get("base", ""))
    return chain


def _profile_layer(name: str, folder: Traversable | None = None) -> dict[str, Any]:
    """Die TOML-Schicht eines Paketprofils samt seiner Grundlagen; ``base`` selbst bleibt draußen."""
    merged: dict[str, Any] = {}
    for step in profile_chain(name, folder):
        layer = _read_profile(step, folder)
        layer.pop("base", None)
        merged = deep_merge(merged, layer)
    return merged


def load_settings(
    explicit: Path | None = None,
    cwd: Path | None = None,
    *,
    profile: str | None = None,
    profiles_dir: Traversable | None = None,
) -> Settings:
    """Alle Schichten in Leserichtung; ``profile`` gewinnt über ``GEOREP_PROFILE`` und die Dateien.

    Das Profil liegt zwischen ``defaults.toml`` und den Dateien im Arbeitsverzeichnis: Konrads
    ``settings.local.toml`` mit ``data_root`` auf xtraspace gewinnt also auch über ein Stadtprofil
    (docs/plans/01-staedte.md, § 2). ``profiles_dir`` ist die Testnaht.
    """
    defaults_text = (resources.files("georep") / "defaults.toml").read_text(encoding="utf-8")
    base: dict[str, Any] = tomllib.loads(defaults_text)
    files = [(path, _read_toml(path)) for path in settings_files(explicit, cwd)]
    chosen = profile or os.environ.get(PROFILE_ENV) or _selected_profile(base, files)
    merged = deep_merge(base, _profile_layer(chosen, profiles_dir))
    for _path, layer in files:
        merged = deep_merge(merged, layer)
    merged["default_profile"] = chosen
    _slugs_match_their_file(chosen, profiles_dir)
    return Settings(**merged)


def _slugs_match_their_file(name: str, folder: Traversable | None = None) -> None:
    """Wer ``city.slug`` setzt, muss so heißen wie seine Datei und darunter rechnen.

    So kann ein Profil eine Periode derselben Stadt sein (``duesseldorf-2014`` erbt den Slug) oder
    eine eigene Stadt (``moenchengladbach`` setzt ihn), und niemand verwechselt beides. Wer den
    Slug setzt, ist die Stadt, und die Hauptperiode einer Stadt rechnet unter ihrem Slug (Punkt
    52): darum muss dasselbe Profil ``profile`` auf denselben Wert setzen -- ``Settings.base_profile``
    verlässt sich darauf, und geerbt käme dort der leere Ordner aus ``defaults.toml`` heraus.
    """
    for step in profile_chain(name, folder):
        layer = _read_profile(step, folder)
        city = layer.get("city")
        slug = city.get("slug") if isinstance(city, dict) else None
        if slug is None:
            continue
        if slug != step:
            raise SchemaError(
                f"Profil {step!r}: city.slug ist {slug!r}; der Slug muss dem Dateinamen gleichen"
            )
        if layer.get("profile") != slug:
            raise SchemaError(
                f"Profil {step!r}: city.slug ist {slug!r}, profile ist {layer.get('profile')!r}; "
                "die Hauptperiode einer Stadt rechnet unter ihrem Slug, das Profil muss ihn "
                "also auch als profile setzen"
            )


def _selected_profile(base: dict[str, Any], files: list[tuple[Path, dict[str, Any]]]) -> str:
    """``default_profile`` aus den TOML-Schichten; die spätere Datei gewinnt."""
    name = str(base.get("default_profile", ""))
    for _path, layer in files:
        if "default_profile" in layer:
            name = str(layer["default_profile"])
    return name
