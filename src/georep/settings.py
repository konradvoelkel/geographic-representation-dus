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
from string import Formatter
from typing import Any, Literal
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import deal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from georep.contracts import is_district_code, one_threshold
from georep.errors import GeorepError, SchemaError
from georep.http import is_loopback_url

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


# Welcher Schlüssel zu welcher Quellform gehört (Punkt 65). Ein Schlüssel an der falschen Form ist
# ein stiller Irrtum: ``member`` an einem GeoJSON sagt nichts, und wer ``source_crs`` an ein
# Shapefile schreibt, glaubt, es gelte -- es gilt das ``.prj`` im Zip. ``esri-identify`` nennt
# ``source_crs``, weil es nur greift, wenn der Dienst keine ``spatialReference`` mitschickt.
PRECINCT_FORM_KEYS: dict[str, frozenset[str]] = {
    "geojson": frozenset({"source_crs", "min_areas"}),
    "shapefile-zip": frozenset({"member", "dbf_encoding"}),
    "esri-identify": frozenset({"source_crs", "min_areas"}),
}
PRECINCT_FORM_ONLY_KEYS = frozenset({"member", "dbf_encoding", "source_crs", "min_areas"})


class Precincts(_Strict):
    """Wie aus der Quellgeometrie die kanonischen Stimmbezirke werden (Option 01, Schritt ``precincts``).

    Die Eigenschaftsnamen und die Regel für den Wahlbezirk sind je Quelle verschieden und stehen
    darum im Profil; ``prep/precincts.py`` ist die einzige Stelle, die sie liest.
    """

    # Option 02: eine Periode mit fremdem Zuschnitt hat keine eigenen Wahlbezirke in der
    # Quellgeometrie; dann entfällt der Schritt ``shapes`` und der Crosswalk ordnet zu.
    enabled: bool = True
    # Punkt 65: ``esri-identify`` ist keine Datei, sondern die Antwort einer ArcGIS-Operation.
    format: Literal["geojson", "shapefile-zip", "esri-identify"] = "geojson"
    member: str = ""  # Pfad des .shp im Zip; leer = das einzige im Archiv
    source_crs: str = ""  # GeoJSON ohne crs-Mitglied, Esri-JSON ohne spatialReference; Shapefiles bringen ihr .prj mit
    id_property: str = ""  # trägt die Stimmbezirksnummer
    district_property: str = ""  # trägt die Wahlbezirksnummer
    district_from_id: tuple[int, int] | None = None  # sonst: Zeichenausschnitt [start, stop)
    name_property: str = ""  # trägt den Namen des Wahlbezirks
    names_from_results: bool = False  # sonst: Namen aus der Wahlbezirks-CSV der Quelle
    names_id_column: str = "gebiet-nr"  # Spalten dieser CSV (votemanager)
    names_name_column: str = "gebiet-name"
    # Punkt 65: wie viele Flächen die Stadt hat (0 = keine Erwartung). Eine abgeschnittene Antwort
    # eines Dienstes ist gültiges JSON und fällt sonst nirgends auf; Fetcher **und** Leser weisen
    # sie ab. Nur an den beiden Formen, die sich zählen lassen, ohne die Datei zu zerlegen: beim
    # Shapefile-Zip stünde die Zahl da, ohne je geprüft zu werden (Review 2026-10-15).
    min_areas: int = Field(default=0, ge=0)
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
        allowed = PRECINCT_FORM_KEYS[self.format]
        wrong = sorted(
            key
            for key in PRECINCT_FORM_ONLY_KEYS - allowed
            if getattr(self, key) != Precincts.model_fields[key].default
        )
        if wrong:
            raise ValueError(
                f"precincts: {wrong} gehören nicht zu format = {self.format!r}; "
                f"diese Form kennt {sorted(allowed)}"
            )
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
    # 0682/XI); dann entscheidet allein die Beratungsfolge (``organizations`` unten), und ohne
    # beides ist jedes Dokument „unbekannt" und die Tabellen bleiben leer.
    reference_pattern: str = ""
    district_body: str = ""
    district_body_name: str = "{n}"  # Anzeigename der Bezirksvertretung, {n} ist der Stadtbezirk
    # Punkt 58: Anzeigename je Kürzel einer Bezirksvertretung, wo sie keine Nummer trägt
    # (Mönchengladbach: „Bezirksvertretung Nord"). Nur Anzeige, darum nicht im Fingerprint,
    # sondern in ``report.build.report_fingerprint``; ohne Eintrag gilt ``district_body_name``.
    district_body_names: dict[str, str] = {}
    names_as_of: date | None = None  # Stand der Namen; nur Anzeige, nicht im Fingerprint
    # Review 11, K3: woher die Namen stammen, als Satzglied der Seite („Quelle sind …"); nur
    # Anzeige wie ``names_as_of``. Die Vorgabe ist der Satz, den die Seite bis 2026-11-24 fest trug.
    names_source: str = "die Organisationen des Ratsinformationssystems und Dokumenttitel"
    council: dict[str, str] = {}
    committees: dict[str, str] = {}
    advisory: dict[str, str] = {}
    # Punkt 58: die Beratungsfolge als zweite Quelle des Gremiums. ``organizations`` bildet eine
    # OParl-Organisation auf ein Kürzel ab -- als volle URL oder als ihre beiden letzten Segmente
    # (``gr/6``); gelernt wird die Tabelle mit ``georep learn-bodies`` aus der Übereinstimmung mit
    # der Drucksachennummer, nicht von Hand geraten. ``consultations`` nennt das Paket, das die
    # Folge je Dokument trägt, wenn der Abruf dieser Periode sie nicht mitbrachte (die
    # Hauptperiode Düsseldorfs: ihr Korpus kommt aus dem Altformat der Arbeit).
    organizations: dict[str, str] = {}
    consultations: Path | None = None
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

    @field_validator("consultations", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @field_validator("organizations")
    @classmethod
    def _keys_are_urls_or_tails(cls, value: dict[str, str]) -> dict[str, str]:
        """Ein Schlüssel ist eine Organisations-URL oder ihre beiden letzten Segmente.

        ``georep.prep.bodies.organization_key`` schneidet jede URL auf diese beiden Segmente
        zurück und sucht sie hier; ein Schlüssel mit drei Segmenten oder mit Leerzeichen fände
        nie etwas, und das soll beim Laden auffallen und nicht als stilles „unbekannt" enden.
        """
        for key in value:
            if not key or key.strip() != key or any(c.isspace() for c in key):
                raise ValueError(f"bodies.organizations: {key!r} ist kein Schlüssel (leer/Raum)")
            if "://" not in key and key.count("/") != 1:
                raise ValueError(
                    f"bodies.organizations: {key!r} ist weder eine URL noch zwei Segmente "
                    "wie 'gr/6'"
                )
        return value

    @model_validator(mode="after")
    def _codes_disjoint(self) -> Bodies:
        if not self.reference_pattern and not self.organizations:
            named = [
                name
                for name in (
                    "district_body",
                    "district_body_names",
                    "council",
                    "committees",
                    "advisory",
                    "aliases",
                )
                if getattr(self, name)
            ]
            if named:
                raise ValueError(
                    "bodies ohne reference_pattern und ohne organizations kennt keine Kürzel: "
                    f"bodies.{', '.join(named)}"
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
        self._targets_are_known(self.organizations, "organizations", seen)
        for code in self.district_body_names:
            if not is_district_code(code, self.district_body):
                raise ValueError(
                    f"bodies.district_body_names: {code!r} ist kein Kürzel einer "
                    f"Bezirksvertretung ({self.district_body!r} und eine Nummer)"
                )
        return self

    def _targets_are_known(self, table: dict[str, str], name: str, seen: dict[str, str]) -> None:
        """Jedes Ziel zeigt auf ein Kürzel, das dieses Profil kennt (wie bei ``aliases``)."""
        for key, code in table.items():
            if not is_district_code(code, self.district_body) and code not in seen:
                raise ValueError(
                    f"bodies.{name}: {key!r} zeigt auf {code!r}, und das steht in keiner Tabelle"
                )

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
            if not is_district_code(code, self.district_body) and code not in seen:
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
FIXED_VARIANTS = ("einheit", "bezirke", "idf", "kombiniert", "ortsbezug", "stelle")
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


# --- Vorhaben 22: Bedarf und Aufmerksamkeit (docs/plans/22-bedarf.md, § 6 und § 10) -----------
#
# Bedarfsquellen mit Punkten oder Gitterzellen statt Raumeinheiten: Unfallatlas, Zensus-Gitter,
# Schuldaten mit Schulsozialindex. Die Quellen sind bundes- oder landesweit und stehen darum in
# ``defaults.toml`` (wie die Sprache der Ratsdokumente bei Vorhaben 15, Punkt 75); das Stadtprofil
# schaltet ein und nennt Paket, Klassen und die vorab festgelegten Hypothesen. Die Gemeinde ist
# ``city.ags``.

NEED_ALTERNATIVES = ("greater", "two-sided")


class NeedAttribution(_Strict):
    """Namensnennung einer Bedarfsquelle; nur Anzeige, nicht im Fingerprint."""

    title: str = ""
    publisher: str = ""
    url: str = ""  # Datensatzseite, nicht das Archiv
    license: str = ""
    license_url: str = ""
    stand: str = ""  # so genau, wie die Quelle es sagt („2025, veröffentlicht 2026-07")
    # Vorarbeit V5 (docs/plan-zeigen-2026-11.md, § 4; docs/todo.md, Punkt 16): dl-de/by-2-0
    # verlangt im Quellenvermerk einen Hinweis, wenn die Daten verändert sind. Der Satz sagt, was
    # verändert ist („verändert: …"); leer heißt unverändert übernommen.
    modified: str = ""


class NeedAccidents(_Strict):
    """Unfälle mit Personenschaden, je Jahr ein Zip mit einer CSV (Punkte auf der Straßenachse)."""

    archives: list[str] = []
    crs: str = "EPSG:25832"
    attribution: NeedAttribution = NeedAttribution()


class NeedGrid(_Strict):
    """Gitterzellen (Einwohner, Miete): zwei Zips mit je einer CSV des 100-m-Gitters."""

    population_url: str = ""
    population_member: str = ""
    rent_url: str = ""
    rent_member: str = ""
    crs: str = "EPSG:3035"
    margin_m: float = Field(default=200.0, ge=0.0)  # Rand um die Stadt beim Vorfiltern
    attribution: NeedAttribution = NeedAttribution()


class NeedSchools(_Strict):
    """Schulen mit Koordinate (eine CSV) und ihr Sozialindex (eine zweite CSV, über die Nummer)."""

    schools_url: str = ""
    index_url: str = ""
    index_encoding: str = "cp850"
    crs: str = "EPSG:25832"
    forms: list[str] = []  # Schulformen, die in den Index je Wahlbezirk gehen
    attribution: NeedAttribution = NeedAttribution()


class NeedClasses(_Strict):
    """Klassen des passenden Ausschusses (Schritt ``committees``), die die Anteile zählen."""

    traffic: list[str] = []
    youth: list[str] = []


class NeedHypothesis(_Strict):
    """Eine vorab festgelegte Hypothese: Bedarf (x) gegen Aufmerksamkeit (y), Spearman, Holm.

    ``need`` und ``attention`` sind Spalten der Analysetabelle des Schritts ``need``
    (``wahlbezirke_bedarf`` mit den Kontrollvariablen, ``trefferquote`` und ``log_begriffe``).
    ``fixed`` ist der Commit, in dem die Hypothese vor der ersten Rechnung festgelegt wurde; er
    steht auf der Seite. Die Robustheitsrechnungen sind vorab genannt und entscheiden nicht.
    """

    name: str
    need: str
    attention: str
    alternative: Literal["greater", "two-sided"]
    fixed: str
    robust_need: list[str] = []  # dieselbe Rechnung mit einer anderen Bedarfsspalte
    robust_attention: list[str] = []  # dito Aufmerksamkeit
    robust_control: str = ""  # partielle Rangkorrelation bei fester Spalte; "" = keine
    # Review 2026-11-24, N8: die Wahlbezirke, ohne die dieselbe Rechnung noch einmal läuft (§ 8:
    # ohne 1 und 10). Vorab festgelegt wie die Hypothese, darum hier und nicht aus
    # ``analysis.exclude_districts``, das die Regression der Seite steuert und sich ändern darf.
    robust_without: list[int] = []
    # Stufe 3 (Messdokument § 7): der Tag der Festlegung neben dem Commit auf der Seite. Anzeige,
    # nicht im Fingerprint; der Commit zählt wie bisher. None: die Seite nennt nur den Commit.
    fixed_on: date | None = None


class NeedSettings(_Strict):
    """Vorhaben 22: Schalter, Paket, Quellen, Band, Tests. Ohne ``enabled`` fehlen beide Schritte,
    ohne ``fetch`` der Netzschritt ``need_data``."""

    enabled: bool = False
    package: Path | None = None  # Paket mit den Stadtauszügen; ein Pfad, nicht im Fingerprint
    band_m: float = Field(default=20.0, ge=0.0)
    neighbour_m: float = Field(default=50.0, gt=0.0)
    permutations: int = Field(default=10_000, ge=1)
    explore_permutations: int = Field(default=9_999, ge=1)
    bootstrap: int = Field(default=2_000, ge=1)
    seed: int = 22
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    accidents: NeedAccidents = NeedAccidents()
    grid: NeedGrid = NeedGrid()
    schools: NeedSchools = NeedSchools()
    classes: NeedClasses = NeedClasses()
    hypotheses: list[NeedHypothesis] = []
    explore: list[tuple[str, str]] = []  # weitere Paare (Bedarf, Aufmerksamkeit), explorativ
    delay_s: float = Field(default=2.0, ge=0.0)  # Pause zwischen zwei geladenen Archiven
    # Review 2026-11-24, N1, wie ``council.enabled`` (Review F6 2026-11-23, Befund 6): volle Abrufe
    # sind Konrads Läufe. Ohne den Schalter fehlt ``need_data``, ein bloßes ``georep fetch`` lädt
    # die zehn Archive nicht, und ``need`` rechnet aus dem Paket. Nicht im Fingerprint.
    fetch: bool = False

    @field_validator("package", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @model_validator(mode="after")
    def _complete_when_enabled(self) -> NeedSettings:
        names = [h.name for h in self.hypotheses]
        if len(names) != len(set(names)):
            raise ValueError(f"context.need.hypotheses: Namen doppelt: {names}")
        if not self.enabled:
            return self
        missing = [
            f"context.need.{name}"
            for name, value in (
                ("accidents.archives", self.accidents.archives),
                ("grid.population_url", self.grid.population_url),
                ("grid.population_member", self.grid.population_member),
                ("grid.rent_url", self.grid.rent_url),
                ("grid.rent_member", self.grid.rent_member),
                ("schools.schools_url", self.schools.schools_url),
                ("schools.index_url", self.schools.index_url),
                ("schools.forms", self.schools.forms),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"context.need.enabled: es fehlen {', '.join(missing)}")
        files = [archive_name(url) for url in self.archive_urls()]
        if len(files) != len(set(files)) or not all(files):
            raise ValueError(
                f"context.need: die Archive brauchen verschiedene Dateinamen in der URL: {files}"
            )
        return self

    def archive_urls(self) -> tuple[str, ...]:
        """Alle Archive in fester Folge: Unfälle je Jahr, Einwohner, Miete, Schulen, Index."""
        return (
            *self.accidents.archives,
            self.grid.population_url,
            self.grid.rent_url,
            self.schools.schools_url,
            self.schools.index_url,
        )

    def with_classes(self) -> bool:
        return bool(self.classes.traffic or self.classes.youth)


def archive_name(url: str) -> str:
    """Der Dateiname eines Archivs: der letzte Pfadteil der URL, dekodiert (``schuldaten.csv``)."""
    return unquote(urlsplit(url).path).rsplit("/", 1)[-1]


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
    need: NeedSettings = NeedSettings()  # Vorhaben 22: Bedarf und Aufmerksamkeit

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
    # Dokumentarten, die die Klasse nennen, aber nicht den Urheber („3 - Fraktionsantrag"): die
    # Klasse steht damit fest, die Partei kommt aus Titel oder Textkopf (oder bleibt leer).
    fraction_types: list[str] = []
    person_types: list[str] = []  # dito für einzelne Mandatsträger („6.1 - Mitgliederantrag")
    motion_prefixes: list[str] = []  # „Antrag", „Anfrage": davor steht die Art, danach die Partei
    fraction_markers: list[str] = []  # erst mit einem dieser Marker wird der Titel befragt
    joint_markers: list[str] = []  # „interfraktionell": Fraktion ohne nennbare Partei
    person_markers: list[str] = []  # „Bezirksvertreterin": Klasse Person
    text_markers: list[str] = []  # Fenster im Textkopf: Antrag/Anfrage … Fraktion
    # Briefkopf des Antragstellers: ein Muster, das **nur** im eigenen Kopf eines Dokuments
    # trifft, nie in einem zitierten Antrag. Es steht vor der Dokumentart, denn der Briefkopf
    # gehört dem Verfasser, während die Dokumentart sagt, wie das System die Vorlage geführt hat
    # (Punkt 62). Leer heißt: nur die Reihenfolge paper_type > name > text.
    letterhead_markers: list[str] = []
    # Punkt 63: Marker im Titel, hinter dem der Titel seinen **eigenen** Gegenstand nennt
    # („…; hier: Antrag der Ratsfraktion DIE LINKE"). Davor steht, worauf das Dokument sich
    # bezieht, also oft der Antrag einer anderen Fraktion. Der **letzte** Marker gewinnt; gefragt
    # wird nur bei einer Dokumentart aus ``fraction_types``, wo der ganze Titel die Quelle ist.
    title_split_markers: list[str] = []
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
        "letterhead_markers",
        "title_split_markers",
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

    @model_validator(mode="after")
    def _each_paper_type_decides_one_class(self) -> Originators:
        """Eine Dokumentart steht in höchstens einer der vier Listen (Review 2026-10-14).

        Sonst entschiede die Reihenfolge in ``classify_document``, welche Klasse gewinnt, und die
        Settings sähen aus, als wäre beides gemeint. Ein Tippfehler in einer langen Liste -- die
        Mönchengladbacher hat 14 Zeilen -- fällt damit beim Laden auf und nicht erst in einer Zahl.
        """
        lists = {
            "admin_types": self.admin_types,
            "citizen_types": self.citizen_types,
            "fraction_types": self.fraction_types,
            "person_types": self.person_types,
        }
        where: dict[str, set[str]] = {}
        for field, types in lists.items():
            for typ in set(types):  # dieselbe Art zweimal in derselben Liste ist nur Redundanz
                where.setdefault(typ, set()).add(field)
        doubled = {typ: names for typ, names in where.items() if len(names) > 1}
        if doubled:
            found = ", ".join(
                f"{typ!r} in {sorted(names)}" for typ, names in sorted(doubled.items())
            )
            raise ValueError(f"originators: Dokumentart in mehr als einer Liste ({found})")
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


class NameGuard(_Strict):
    """Vorhaben 11 und 12, Stufe 3: woran ein Download einen Personennamen erkennt.

    Ein Wert, in dem hinter einem dieser Titel (mit oder ohne Doppelpunkt) ein groß geschriebener
    Buchstabe folgt, trägt vermutlich einen Namen: der Kopf eines Dokuments läuft dort in das Feld
    der Dezernentin oder des Dezernenten hinein (in der Hauptperiode viermal). Das Muster gilt in
    Polars (Rust-Syntax), darum ohne Lookarounds; ``report.downloads.named`` setzt es zusammen.
    """

    person_titles: str = (
        r"Herrn?|Frau|Dr\.|Prof\.|Ratsherrn?|Ratsfrau|Ratsmitglied|Bürgermitglied"
        r"|(?:Ober|Bezirks)?[Bb]ürgermeister(?:in)?|Beigeordnete[rn]?|Stadtdirektor(?:in)?"
        r"|Stadtkämmer(?:er|in)|Dezernent(?:in)?|Amtsleiter(?:in)?|Bezirksvertreter(?:in)?"
        r"|Fraktionsvorsitzende[rn]?|Vorsitzende[rn]?|Sprecher(?:in)?|Geschäftsführer(?:in)?"
    )

    @field_validator("person_titles")
    @classmethod
    def _titles_compile_without_lookaround(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("report.names.person_titles: leer hieße, kein Download prüft Namen")
        if any(mark in value for mark in ("(?=", "(?!", "(?<")):
            raise ValueError(
                f"report.names.person_titles {value!r}: Polars kennt keine Lookarounds"
            )
        return _compiles([value], "report.names.person_titles")[0]


class StartSettings(_Strict):
    """Die Karte der Startseite (``docs/plan-startseite-2026-11.md``, § 4, § 5): nur Anzeige."""

    # § 4.3: ein Dokument mit mehr Orten steht als Zeile unter der Karte, nicht als Punkt
    max_places: int = Field(default=20, ge=1)
    # § 5: die Voreinstellung des Zeitreglers, Monate bis zum neuesten Dokument
    months: int = Field(default=12, ge=1)
    # Wo kein Paket Stadtteile beschriftet, steht der Stadtbezirk; sein Name hier, sonst
    # „Stadtbezirk <n>" (Schlüssel als Text, weil TOML-Schlüssel Texte sind)
    city_district_names: dict[str, str] = {}


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
    # plan-startseite, § 3 und Phase „Zeigen", § 6: die Startseite hat ihr eigenes Budget (hart
    # 150 000, Ziel 120 000), ``data/karte.json`` höchstens 500 000 Byte roh; 0 schaltet ab
    start_budget_bytes: int = Field(default=150_000, ge=0)
    map_budget_bytes: int = Field(default=500_000, ge=0)
    # Punkt 36: ``spalten.html``, das Spaltenschema aller Tabellen, hat ein eigenes Budget; mit
    # jeder neuen Tabelle wächst sie, und eine eigene Zahl merkt das früher als das der Seiten
    columns_budget_bytes: int = Field(default=500_000, ge=0)
    start: StartSettings = StartSettings()
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
    # Vorhaben 11 und 12, Stufe 3: kein Personenname in einem Download. Unter [report], weil es
    # nur die Seite betrifft und im Stamp von ``report`` zählt, nicht im Settings-Fingerprint
    names: NameGuard = NameGuard()

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
    # Punkt 68: ein Textpaket (``georep pack --texts``), dessen Store den der Referenz ersetzt,
    # wenn er genau ihre Dateien trägt; ``None`` = die Texte der Referenz.
    texts: Path | None = None
    # Fundament F1: ein Rohtextpaket (``georep pack --raw-texts``), das den Rohtextstore anlegt;
    # ``None`` = kein Paket, der Schritt ``raw_texts`` liest die PDFs, wo es sie gibt.
    raw_texts: Path | None = None

    @field_validator("texts", "raw_texts", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value


# --- Fundament F6: OParl Sitzungen und Personen
class Council(_Strict):
    """Die Listen der Sitzungen, Beratungen und Personen eines OParl-Bodys (Fundament F6).

    Die Endpunkte nennt das Profil (das Body-Objekt des Servers listet sie); leer heißt, der Schritt
    fehlt, und stadtneutral sind alle leer. ``incremental`` nennt die Schritte, die mit
    ``modified_since`` nachholen (docs/runbook-sitzungen.md, § 2).
    """

    # Review 2026-11-23, Befund 6: volle Abrufe sind Konrads Läufe (Plan 2026-11, § 4), und ein
    # neuer Schritt steht hinter einem Schalter, der zunächst aus ist (§ 7). Ohne ihn fehlen die
    # drei Schritte, und ein bloßes ``georep fetch`` nimmt sie nicht mit.
    enabled: bool = False
    meetings_endpoint: str = ""
    consultations_endpoint: str = ""
    persons_endpoint: str = ""
    incremental: tuple[Literal["meetings", "consultations", "persons"], ...] = ("consultations",)
    stop_when_older: bool = True
    # Review 2026-11-23, Befund 3: die Sitzungsliste ist nach Anlage sortiert, nicht nach Beginn;
    # ``start - created`` reichte in 400 Sitzungen von -418 bis +447 Tagen. Erst eine Seite, deren
    # jüngstes ``created`` mehr als so viele Tage vor ``period.start`` liegt, beendet den Abruf.
    created_margin_days: int = Field(default=500, ge=0)


# --- Fundament F4: Validierung (docs/validierung.md)
class Validation(_Strict):
    """Wo die Validierung liegt: Codebücher und Labels im Repo, Kodieraufträge nur lokal.

    Die Aufträge tragen Ausschnitte aus Ratsdokumenten und gehören nicht ins Repo
    (plan-vorverarbeitung-2026-11.md, § 4, „Daten"); ``coding_root`` ist darum rechnerspezifisch
    und steht auf Konrads Rechner in ``settings.local.toml``. Nichts hier ändert ein Ergebnis
    der Kette: der Block zählt nicht zum Fingerprint.
    """

    root: Path = Path("validierung")  # Codebücher, Stichproben, Labels, README je Vorhaben
    coding_root: Path | None = None  # Kodieraufträge und Antworten; None = <data_root>/kodierung
    min_alpha: float = Field(
        default=0.8, ge=0.0, le=1.0
    )  # Stufe 3 verlangt so viel α zwischen A und B

    @field_validator("coding_root", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value


# --- Fundament F5: Modelle (docs/plan-vorverarbeitung-2026-11.md, § 7)
class EmbeddingModel(_Strict):
    """Das Einbettungsmodell auf dem ollama-Server; ``dimension`` prüft jede Antwort."""

    model: str = "nomic-embed-text-v2-moe"
    dimension: int = Field(default=768, ge=1)
    num_ctx: int = Field(default=512, ge=0)  # Fenster in Token; 0 = was das Modell mitbringt
    truncate: bool = True  # längere Texte hinten abschneiden; false: ein Fehler je solchem Text
    # Vorhaben 18: die Präfixe gehören zum Modell (nomic-embed-text), nicht in den Code. Sie stehen
    # nicht im Fingerprint (``[ml]``), aber in der Prompt-Version des Schritts, sobald sie von der
    # gemessenen Fassung abweichen (``enrich.embeddings.chunk_prompt``).
    document_prefix: str = "search_document: "
    query_prefix: str = "search_query: "


class GenerationModel(_Strict):
    """Das Sprachmodell und seine Optionen; der Standard ist deterministisch (Temperatur 0, Seed)."""

    model: str = "qwen3.6:27b"
    temperature: float = Field(default=0.0, ge=0.0)
    seed: int = 0
    num_ctx: int = Field(default=8192, ge=1)
    num_predict: int = Field(default=512, ge=1)
    think: bool = False


class Ml(_Strict):
    """Der lokale Modellserver: Ort, Laufzeit, Modelle, Optionen. Nichts davon steht im Fingerprint.

    Was ein Ergebnis bestimmt (Modell, Digest, Optionen, Fenster), steht als Kennung im Stamp des
    Modellschritts, ein Teillauf als offene Eingaben (``ModelUse``, Review F5, N5).
    """

    base_url: str = Field(default="http://localhost:11434", pattern=r"^https?://")
    allow_remote: bool = False  # ein Server, der nicht auf diesem Rechner läuft, nur ausdrücklich
    timeout_s: float = Field(default=300.0, gt=0)
    retries: int = Field(default=2, ge=0, le=10)
    backoff_s: float = Field(default=2.0, ge=0)
    keep_alive: str = "10m"
    batch_size: int = Field(default=32, ge=1)
    limit: int = Field(default=0, ge=0)
    retry_rejected: bool = False  # abgewiesene Eingaben erneut fragen statt überspringen
    embedding: EmbeddingModel = EmbeddingModel()
    generation: GenerationModel = GenerationModel()
    # Vorhaben 18 (Review Runde 1, N1): die flock-Sperre der GPU, die ``georep search`` nicht
    # blockierend prüft; ist sie gehalten, sucht es mit BM25. ``None`` = keine Prüfung. Der Pfad
    # ist rechnerspezifisch und gehört in ``settings.local.toml``, nie in die Defaults.
    gpu_lock: Path | None = None

    @field_validator("gpu_lock", mode="before")
    @classmethod
    def _no_lock(cls, value: object) -> object:
        return None if value in ("", None) else value

    @model_validator(mode="after")
    def _local_unless_allowed(self) -> Ml:
        """Die Dokumente verlassen den Rechner nicht (Plan § 2.8), es sei denn, jemand sagt es."""
        if not self.allow_remote and not is_loopback_url(self.base_url):
            raise ValueError(
                f"ml.base_url = {self.base_url} zeigt nicht auf diesen Rechner; "
                "ml.allow_remote = true schaltet einen anderen Server ausdrücklich frei"
            )
        return self


# --- Vorhaben 15: Dokumentfunktion und gemeinsame Anträge (docs/plans/15-funktion.md)
# Die fünf Funktionen eines Ratsdokuments und die Restklasse „Funktion nicht erkannt" (§ 4.2), je
# Funktion die Instrumente (Unterart, nicht Teil des validierten Kriteriums). Die Tabellen stehen
# hier und nicht im Modul ``analysis.functions``, weil die Dokumentarten des Profils beim Laden gegen
# sie geprüft werden: ein Tippfehler wie „vollzug/beschlusvorlage" fällt vor dem ersten Lauf auf.
# ``erklaerung`` („Erklärung oder Appell") hieß in Messung und Codebuch ``symbol``; die Definition
# ist dieselbe (Konrad, 2026-11-27: „Symbolpolitik" ist wertend). ``CODEBOOK_FUNCTIONS`` übersetzt.
FUNCTION_CLASSES = ("kontrolle", "information", "initiative", "erklaerung", "vollzug", "rest")
CODEBOOK_FUNCTIONS = {"symbol": "erklaerung"}  # Label im Codebuch 15 -> Wert in den Daten
FUNCTION_INSTRUMENTS: dict[str, tuple[str, ...]] = {
    "kontrolle": ("anfrage", "nachfrage", "berichtsantrag"),
    "information": ("informationsvorlage", "berichtsvorlage"),
    "initiative": (
        "antrag",
        "aenderungsantrag",
        "haushaltsantrag",
        "pruefauftrag",
        "berichtsantrag",  # Variante A; Variante B zählt ihn als Kontrolle
        "eingabe",
    ),
    "erklaerung": ("resolution", "erklaerung_text"),
    "vollzug": (
        "beschlussvorlage",
        "satzung",
        "haushalt",
        "bauleitplanung",
        "besetzung",
        "dringlichkeit",
        "bau",
        "rechnungspruefung",
    ),
    # Die Restklasse trägt statt eines Instruments den Grund: eine Sammelart ohne Merkmal in Titel
    # und Textkopf, oder eine Dokumentart, die keine Tabelle kennt.
    "rest": ("sammelart_ohne_merkmal", "art_unbekannt"),
}


def function_and_instrument(value: str) -> tuple[str, str]:
    """``"vollzug/beschlussvorlage"`` als Paar; ``ValueError`` bei fremder Funktion oder Instrument."""
    function, _, instrument = value.partition("/")
    if function not in FUNCTION_INSTRUMENTS or function == "rest":
        raise ValueError(
            f"functions: {value!r} nennt keine Funktion aus {list(FUNCTION_CLASSES[:-1])}"
        )
    if instrument not in FUNCTION_INSTRUMENTS[function]:
        raise ValueError(
            f"functions: {value!r}: das Instrument gehört nicht zu {function} "
            f"({', '.join(FUNCTION_INSTRUMENTS[function])})"
        )
    return function, instrument


class EnforcementRule(_Strict):
    """Ein Instrument des Vollzugs, wenn eines der Muster im Titel steht (Satzung, Bauleitplanung …)."""

    instrument: str
    patterns: list[str]

    @field_validator("instrument")
    @classmethod
    def _known(cls, value: str) -> str:
        if value not in FUNCTION_INSTRUMENTS["vollzug"]:
            raise ValueError(f"functions.enforcement: {value!r} ist kein Instrument des Vollzugs")
        return value

    @field_validator("patterns")
    @classmethod
    def _compile(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("functions.enforcement: eine Regel braucht mindestens ein Muster")
        return _compiles(value, "functions.enforcement[].patterns")


class TextWord(_Strict):
    """Das erste Instrumentwort im Textkopf einer Sammelart und die Funktion, die es nennt."""

    pattern: str  # passt auf das ganze Wort (``re.fullmatch``)
    function: str  # "funktion/instrument"

    @field_validator("pattern")
    @classmethod
    def _compile(cls, value: str) -> str:
        return _compiles([value], "functions.text_words[].pattern")[0]

    @field_validator("function")
    @classmethod
    def _pair(cls, value: str) -> str:
        function_and_instrument(value)
        return value


def _overlap(a_from: date, a_to: date | None, b_from: date, b_to: date | None) -> bool:
    """Zwei geschlossene Zeiträume teilen einen Tag; ``None`` als Ende heißt offen."""
    return (a_to is None or b_from <= a_to) and (b_to is None or a_from <= b_to)


class Fraction(_Strict):
    """Eine Fraktion aus mehreren Parteischlüsseln mit ihrem Zeitraum (Messdokument 15, § 3.8).

    Ohne sie wäre „SPD – Volt" die stärkste Kante der laufenden Periode, und sie ist keine
    Zusammenarbeit zweier Fraktionen. Die Tabelle entfällt, sobald ``raw/organizations.json`` die
    Fraktionen der Stadt nennt (Frage 9.3).
    """

    key: str  # Schlüssel der Fraktion, etwa "SPD+VOLT"; so steht sie in ``fraktionen``
    parties: list[str]  # Parteischlüssel aus [originators], mindestens zwei
    valid_from: date
    valid_to: date | None = None  # None: offen

    @model_validator(mode="after")
    def _two_parties_in_order(self) -> Fraction:
        if len(self.parties) < 2 or len(set(self.parties)) != len(self.parties):
            raise ValueError(
                f"functions.fractions: {self.key} braucht mindestens zwei verschiedene Parteien"
            )
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError(f"functions.fractions: {self.key} endet vor seinem Beginn")
        return self

    def holds_on(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


class Functions(_Strict):
    """Funktion je Ratsdokument und Antragsteller je Fraktionsdokument (Vorhaben 15).

    Die Muster der Sprache der Ratsdokumente (Antrag, Anfrage, Resolution, Satzung …) stehen in
    ``defaults.toml``; was nur eine Stadt kennt — ihre Dokumentarten, die Sammelarten einer alten
    Vorlagenform samt deren Textregeln, ihr Briefkopf, ihre Fraktionen aus mehreren Parteien —, im
    Stadtprofil. Alle Muster sind kleingeschriebene reguläre Ausdrücke; eine Liste wird zu einer
    Alternative.
    """

    enabled: bool = False
    variant: Literal["A", "B"] = "B"
    head_chars: int = Field(default=700, ge=1)
    wide_chars: int = Field(default=3000, ge=1)
    decision_chars: int = Field(default=1200, ge=1)
    letterhead_chars: int = Field(default=240, ge=1)
    types: dict[str, str] = {}  # paper_type (ganzer Wert) -> "funktion/instrument"
    type_prefixes: dict[str, str] = {}  # Präfix (klein) -> "funktion/instrument"
    collection_political: list[str] = []
    collection_admin: list[str] = []
    symbol_title: list[str] = []
    request_title: list[str] = []
    motion_title: list[str] = []
    followup_title: list[str] = []
    amendment_title: list[str] = []
    budget_motion_title: list[str] = []
    review_title: list[str] = []
    report_title: list[str] = []
    enforcement: list[EnforcementRule] = []
    symbol_text: list[str] = []
    report_text: list[str] = []
    author_start: list[str] = []
    author_stop: list[str] = []
    text_instrument: list[str] = []
    text_words: list[TextWord] = []
    not_instruments: list[str] = []
    text_notice: list[str] = []
    text_decision: list[str] = []
    text_decision_head: list[str] = []
    title_information: list[str] = []
    title_decision: list[str] = []
    letterhead: list[str] = []
    letterhead_end: list[str] = []
    fractions: list[Fraction] = []

    @field_validator(
        "symbol_title",
        "request_title",
        "motion_title",
        "followup_title",
        "amendment_title",
        "budget_motion_title",
        "review_title",
        "report_title",
        "symbol_text",
        "report_text",
        "author_start",
        "author_stop",
        "text_instrument",
        "text_notice",
        "text_decision",
        "text_decision_head",
        "title_information",
        "title_decision",
        "letterhead",
        "letterhead_end",
    )
    @classmethod
    def _patterns_compile(cls, value: list[str]) -> list[str]:
        return _compiles(value, "functions patterns")

    @field_validator("types", "type_prefixes")
    @classmethod
    def _pairs(cls, value: dict[str, str]) -> dict[str, str]:
        for target in value.values():
            function_and_instrument(target)
        return value

    @field_validator("type_prefixes")
    @classmethod
    def _lowercase_prefixes(cls, value: dict[str, str]) -> dict[str, str]:
        wrong = sorted(p for p in value if p != p.lower() or not p.strip())
        if wrong:
            raise ValueError(
                f"functions.type_prefixes: Präfixe klein und nicht leer, nicht {wrong}"
            )
        return value

    @model_validator(mode="after")
    def _one_place_per_type(self) -> Functions:
        """Eine Dokumentart steht in höchstens einer Tabelle; sonst entschiede die Reihenfolge."""
        tables = {
            "types": set(self.types),
            "collection_political": set(self.collection_political),
            "collection_admin": set(self.collection_admin),
        }
        names = list(tables)
        for i, first in enumerate(names):
            for second in names[i + 1 :]:
                both = sorted(tables[first] & tables[second])
                if both:
                    raise ValueError(f"functions: {both} in {first} und {second}")
        return self

    @model_validator(mode="after")
    def _fractions_unique_and_disjoint(self) -> Functions:
        """Ein Schlüssel einmal, und eine Partei gehört an keinem Tag zu zwei Fraktionen."""
        keys = [f.key for f in self.fractions]
        if len(keys) != len(set(keys)):
            raise ValueError(f"functions.fractions: doppelte Schlüssel in {keys}")
        for i, first in enumerate(self.fractions):
            for second in self.fractions[i + 1 :]:
                shared = sorted(set(first.parties) & set(second.parties))
                if shared and _overlap(
                    first.valid_from, first.valid_to, second.valid_from, second.valid_to
                ):
                    raise ValueError(
                        f"functions.fractions: {shared} zugleich in {first.key} und {second.key}"
                    )
        return self


# Die Gremienarten aus ``prep.bodies.KINDS``; hier als Literal, weil ``prep.bodies`` die Settings liest.
BodyKind = Literal["bezirksvertretung", "rat", "ausschuss", "beirat", "unbekannt"]
_PARTIAL_DATE = re.compile(r"\d{4}(-\d{2}(-\d{2})?)?")


class Majority(_Strict):
    """Die Mehrheit im Rat für einen Zeitraum, mit Quelle (Vorhaben 15, 24 und 28 lesen sie).

    Eine **Annahme mit Beleg**: die Vereinbarung der Partner (gesammelt von Vorhaben 25) und die
    Drucksachen, in denen der Korpus die Mehrheit selbst nennt. Abgeleitet aus den gemeinsamen
    Anträgen ist sie nicht; für das Maß, das sie trägt, wäre das zirkulär (Messdokument 15, § 3.9).
    """

    period: str  # Anzeigename der Wahlperiode des Rates, etwa "2014-2020"
    parties: list[str]  # Parteischlüssel aus [originators]
    valid_from: date
    valid_to: date | None = None  # None: offen (laufende Periode)
    agreement: str  # die Vereinbarung in Worten
    agreement_date: str = ""  # so genau, wie die Quelle es sagt: "2021-01-19", "2025-12", "2014"
    evidence: list[str] = []  # Drucksachen des Korpus, die die Mehrheit nennen

    @model_validator(mode="after")
    def _consistent(self) -> Majority:
        if not self.parties or len(set(self.parties)) != len(self.parties):
            raise ValueError(f"majorities: {self.period} braucht verschiedene Parteien")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError(f"majorities: {self.period} endet vor seinem Beginn")
        if self.agreement_date and not _PARTIAL_DATE.fullmatch(self.agreement_date):
            raise ValueError(
                f"majorities: agreement_date {self.agreement_date!r} ist kein Datum der Form "
                "JJJJ, JJJJ-MM oder JJJJ-MM-TT"
            )
        return self

    def holds_on(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


class Majorities(_Strict):
    """Die Ratsmehrheiten der Stadt, stadtweit und nicht je Periodenprofil (Synergien 2026-11, § 1).

    ``body_kinds`` sind die Gremienarten, in denen die Mehrheit des Rates gilt; die
    Bezirksvertretungen haben eigene Mehrheiten, die im Datensatz nicht stehen (Vorhaben 27).
    """

    body_kinds: list[BodyKind] = ["rat", "ausschuss"]
    terms: list[Majority] = []

    @model_validator(mode="after")
    def _ordered_and_disjoint(self) -> Majorities:
        for before, after in zip(self.terms, self.terms[1:], strict=False):
            if after.valid_from <= before.valid_from or _overlap(
                before.valid_from, before.valid_to, after.valid_from, after.valid_to
            ):
                raise ValueError(
                    f"majorities: {before.period} und {after.period} überlappen oder stehen "
                    "nicht in der Folge ihres Beginns"
                )
        return self

    def on(self, day: date | None) -> Majority | None:
        """Die Mehrheit an einem Tag; ``None`` ohne Datum oder ohne Zeile für den Tag."""
        if day is None:
            return None
        return next((term for term in self.terms if term.holds_on(day)), None)


# --- Vorhaben 14: Vorgänge (docs/plans/14-vorgaenge.md, § 6 und § 10) ----------------------------
# Die Rollen sind das Vokabular des Verfahrens (Codebuch .2), kein Stadtwort: welche Dokumentart
# welche Rolle spielt, sagt das Stadtprofil in ``[[procedures.kinds]]``; was keine Regel trifft,
# ist ``sonst``.
ProcedureRole = Literal[
    "anfrage", "antrag", "vorlage", "information", "bedarf", "af", "eingabe", "politik", "sonst"
]
# Die Gruppen, aus denen ein Schlüssel entsteht: Kürzel und Nummer dahinter (``BV6``), ein Kopf
# aus Ziffern (alte Form ``61/12/2014``), laufende Nummer, Jahr, Wahlperiode (römisch) und der
# Nachtrag; Gruppen, die mit ``suffix`` beginnen, sind Nachtragsstellen (die erste gefüllte zählt).
REFERENCE_GROUPS = frozenset({"code", "number", "head", "serial", "year", "period"})


def _groups_of(pattern: str, field: str) -> set[str]:
    try:
        return set(re.compile(pattern).groupindex)
    except re.error as error:
        raise ValueError(f"{field}: {pattern!r} ist kein Muster ({error})") from error


class ReferenceForm(_Strict):
    """Eine Form der Drucksachennummer: ein Muster für die eigene Nummer, eines für den Text.

    ``key`` baut den Schlüssel aus den Gruppen (``str.format``): Kürzel groß, ``number`` ohne
    führende Nullen oder leer, ``serial`` als Zahl (``{serial:04d}`` füllt auf), ``period`` groß;
    ein Nachtrag hängt als ``/k`` an. ``glued`` heißt: die Gruppe ``code`` im Text ist eine ganze
    Buchstabenfolge, und gilt wird das längste bekannte Kürzel an ihrem Ende, weil pypdf Wörter
    zusammenklebt („vorlagebv6/002/2023", Messdokument § 3.1).
    """

    name: str
    reference: str  # trifft die ganze eigene Nummer (``reference``, getrimmt)
    text: str  # sucht in Titel, Text und Anlagennamen, alle kleingeschrieben
    key: str
    glued: bool = False

    @model_validator(mode="after")
    def _groups_fit(self) -> ReferenceForm:
        own = _groups_of(self.reference, "procedures.forms[].reference")
        found = _groups_of(self.text, "procedures.forms[].text")
        for groups, field in ((own, "reference"), (found, "text")):
            strange = sorted(g for g in groups - REFERENCE_GROUPS if not g.startswith("suffix"))
            if strange:
                raise ValueError(
                    f"procedures.forms {self.name!r}: unbekannte Gruppen {strange} in {field}"
                )
        try:
            needed = {name for _, name, _, _ in Formatter().parse(self.key) if name}
        except ValueError as error:
            raise ValueError(
                f"procedures.forms {self.name!r}: key {self.key!r} ({error})"
            ) from error
        missing = sorted(needed - (own & found))
        if missing or "serial" not in needed:
            raise ValueError(
                f"procedures.forms {self.name!r}: key {self.key!r} braucht serial und nur Gruppen "
                f"beider Muster; fehlt in einem: {missing}"
            )
        if self.glued and "code" not in found:
            raise ValueError(
                f"procedures.forms {self.name!r}: glued braucht die Gruppe code im Text"
            )
        return self


class KindRule(_Strict):
    """Dokumentart -> Rolle; die erste Regel, deren Muster trifft, gilt (Messdokument § 2)."""

    role: ProcedureRole
    paper_type: str  # sucht in der getrimmten, kleingeschriebenen Dokumentart
    title: str = ""  # dazu muss es im kleingeschriebenen Titel stehen; leer = gleich
    title_not: str = ""  # und darf dort nicht stehen; leer = gleich

    @field_validator("paper_type", "title", "title_not")
    @classmethod
    def _compiles(cls, value: str) -> str:
        return _compiles([value], "procedures.kinds[]")[0]


class TitleOverride(_Strict):
    """Der Titel schlägt die Dokumentart, wo beide sich widersprechen (Messdokument § 3.9, S1)."""

    role: ProcedureRole
    title: (
        str  # am Anfang des kleingeschriebenen Titels, ohne führende Leerzeichen und Doppelpunkte
    )
    to: ProcedureRole

    @field_validator("title")
    @classmethod
    def _compiles(cls, value: str) -> str:
        return _compiles([value], "procedures.title_overrides[].title")[0]


class RelatedPeriod(_Strict):
    """Eine Nachbarperiode derselben Stadt, gelesen aus ihrem Paket (Messdokument, Frage 9.2).

    ``papers`` ist ``raw/papers.jsonl`` oder das Altformat der Arbeit (eine JSON-Liste),
    ``texts`` der Textstore desselben Datensatzes. Gelesen wird nur; beide Hashes stehen im Stamp.
    """

    profile: str  # das Profil der Periode; steht als ``nach_periode`` an jeder Kante dorthin
    papers: Path
    texts: Path


class Procedures(_Strict):
    """Vorgänge aus Drucksachennummern (Vorhaben 14): Formen, Rollen, Regeln, Pakete.

    Gebaut ist die Rückfallregel (Messdokument § 5.1): stark ist eine Kante nur aus Titel,
    Anlagenname, Nachtragsnummer oder Sammelbericht; reine Textverweise bleiben schwach in den
    Daten. Muster und Tabellen der Stadt stehen im Stadtprofil, kein Stadtwort im Code.
    """

    enabled: bool = False
    forms: list[ReferenceForm] = []
    max_code_length: int = Field(default=6, ge=1)
    kinds: list[KindRule] = []
    title_overrides: list[TitleOverride] = []
    collective_titles: str = ""
    amendment_markers: str = ""
    amendment_window: int = Field(default=120, ge=0)
    answer_attachment: str = ""
    interim_attachment: str = ""
    attachment_dates_invalid: list[date] = []
    attachments: Path | None = None
    related: list[RelatedPeriod] = []
    # Review K1: Anrede oder Titel vor einem Namen; ``pack --attachments`` ersetzt den Namen dahinter
    person_titles: str = ""

    @field_validator(
        "collective_titles",
        "amendment_markers",
        "answer_attachment",
        "interim_attachment",
        "person_titles",
    )
    @classmethod
    def _compiles(cls, value: str) -> str:
        return _compiles([value], "procedures")[0]

    @field_validator("attachments", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @model_validator(mode="after")
    def _forms_when_enabled(self) -> Procedures:
        if self.enabled and not self.forms:
            raise ValueError("procedures.enabled braucht mindestens eine Form in procedures.forms")
        names = [form.name for form in self.forms]
        if len(set(names)) != len(names):
            raise ValueError(f"procedures.forms: doppelte Namen {names}")
        return self


# --- Vorhaben 18: Einbettungen, Ähnlichkeit, Suche (docs/plans/18-einbettungen.md)
class Bm25(_Strict):
    """Okapi BM25 der Wortsuche (Fassung ``18-bm25-1``): Sättigung ``k1`` und Längennorm ``b``."""

    k1: float = Field(default=1.2, gt=0)
    b: float = Field(default=0.75, ge=0, le=1)


class Embeddings(_Strict):
    """Stücke, Dokumentvektoren, Nachbarn und die Suche über sie (Vorhaben 18).

    ``chunk_chars``, ``title_chars`` und ``overlap_chars`` sind die Fassung ``18-stuecke-1``;
    ``document_chunks`` macht den Dokumentvektor (``18-dokvektor-1``), ``neighbors`` die Zahl der
    ähnlichen Dokumente. ``rrf_k`` und ``fusion_depth`` sind die Mischung (``18-rrf-1``); sie und
    ``bm25`` liest nur ``georep search`` und stehen darum nicht im Fingerprint.
    ``neighbors_package`` ist ein Pfad (nicht im Fingerprint): das Paket mit der Nachbartabelle,
    das ``bootstrap`` nach ``raw/`` legt, für eine Kette ohne Dokumentvektoren.
    """

    enabled: bool = False
    chunk_chars: int = Field(default=1600, ge=1)
    title_chars: int = Field(default=200, ge=0)
    overlap_chars: int = Field(default=200, ge=0)
    document_chunks: int = Field(default=3, ge=1)
    neighbors: int = Field(default=10, ge=1)
    bm25: Bm25 = Bm25()
    rrf_k: int = Field(default=60, ge=0)
    fusion_depth: int = Field(default=100, ge=1)
    neighbors_package: Path | None = None

    @model_validator(mode="after")
    def _a_title_leaves_room_for_the_body(self) -> Embeddings:
        """Der längste Titel samt Leerzeile lässt dem Rumpf eines Stücks Platz, mehr als die Überlappung."""
        room = self.chunk_chars - self.title_chars - 2
        if room < 1 or self.overlap_chars >= room:
            raise ValueError(
                f"embeddings: chunk_chars {self.chunk_chars} lässt nach title_chars "
                f"{self.title_chars} und der Leerzeile {room} Zeichen für den Rumpf; es braucht "
                f"mindestens eines und mehr als overlap_chars ({self.overlap_chars})"
            )
        return self

    @field_validator("neighbors_package", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value


class InstrumentTitle(_Strict):
    """Ein Muster im Titel (klein), das ein Dokument einem Instrument zuordnet (Vorhaben 17, S1.5)."""

    pattern: str
    instrument: Literal["anfrage", "antrag"]

    @field_validator("pattern")
    @classmethod
    def _pattern_compiles(cls, value: str) -> str:
        return _compiles([value], "cycles.instrument_titles[].pattern")[0]


class Cycles(_Strict):
    """Rhythmus der Ratsarbeit und bundespolitisches Vokabular (Vorhaben 17, docs/plans/17-zeit.md).

    Stadtneutral sind das Wahljahr, das Muster der Haushaltsanträge, die Wörter der Instrumente und
    das Lexikon; die Wahltage stehen im Stadtprofil (``elections``, mit Quelle), die Perioden, über
    die die vorab festgelegten Tests rechnen, im Profil, das sie rechnet (``periods``). Ohne
    ``enabled`` fehlen die Schritte ``cycles``, ``vocabulary`` und ``cycle_tests``.
    """

    enabled: bool = False
    year_start_month: int = Field(default=9, ge=1, le=12)
    elections: list[date] = []
    budget_pattern: str = r"haushalts(begleit)?-?antrag"
    budget_minimum: int = Field(default=5, ge=1)
    instrument_types: dict[str, Literal["anfrage", "antrag"]] = {}  # Präfix (klein) -> Instrument
    instrument_titles: list[InstrumentTitle] = []
    lexicon: str = Field(default="bundespolitik", pattern=r"^[a-z0-9][a-z0-9_-]*$")
    head_chars: int = Field(default=2000, ge=1)
    periods: list[str] = []  # Ordner der Profile der Stadt, in zeitlicher Folge

    @field_validator("budget_pattern")
    @classmethod
    def _budget_compiles(cls, value: str) -> str:
        return _compiles([value], "cycles.budget_pattern")[0]

    @field_validator("elections")
    @classmethod
    def _elections_ordered(cls, value: list[date]) -> list[date]:
        if value != sorted(set(value)):
            raise ValueError("cycles.elections: Wahltage aufsteigend und ohne Doppel")
        return value

    @field_validator("periods")
    @classmethod
    def _periods_are_folders(cls, value: list[str]) -> list[str]:
        for name in value:
            _plain_name(name, "cycles.periods")
        if len(set(value)) != len(value):
            raise ValueError("cycles.periods: ein Profil steht zweimal")
        return value

    @model_validator(mode="after")
    def _tests_need_elections(self) -> Cycles:
        if self.periods and not self.elections:
            raise ValueError(
                "cycles.periods braucht cycles.elections: ohne Wahltag kein Vorwahljahr"
            )
        return self


class StreetPointLabels(_Strict):
    """Die Namen der Stadtteile für die Grundkarte der Startseite (plan-startseite, § 4.1)."""

    url: str = ""  # GeoJSON der Stadt (EPSG:4326); leer: die Karte beschriftet die Stadtbezirke
    name: str = ""  # die Eigenschaft eines Features mit dem Namen

    @model_validator(mode="after")
    def _name_with_url(self) -> StreetPointLabels:
        if self.url and not self.name:
            raise ValueError("street_points.labels.name fehlt: welche Eigenschaft trägt den Namen?")
        return self


class StreetPoints(_Strict):
    """Straßenpunkte und Ortsnamen der Startkarte (plan-startseite, § 4.1, § 4.2).

    Ohne ``package`` liegt eine Straße auf der Fläche ihrer Stimmbezirke; ohne ``fetch`` fehlt der
    Netzschritt ``street_points``, wie ``need_data`` (Punkt 80).
    """

    package: Path | None = None  # Paket snapshots/<stadt>-strassenpunkte; bootstrap kopiert es
    fetch: bool = False  # schaltet nur den Netzschritt ein (wie context.need.fetch)
    url: str = ""  # Gebäudereferenzen: ein Zip mit gebref.txt, eine Zeile je Hausnummer
    round_m: float = Field(default=25.0, gt=0.0)  # Raster der Punkte in Metern
    delay_s: float = Field(default=2.0, ge=0.0)  # Pause zwischen zwei geladenen Dateien
    labels: StreetPointLabels = StreetPointLabels()

    @field_validator("package", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @model_validator(mode="after")
    def _url_when_fetching(self) -> StreetPoints:
        if self.fetch and not self.url:
            raise ValueError("street_points.fetch ohne street_points.url")
        return self


class Feeds(_Strict):
    """Atom-Feed je Wahlbezirk (Vorhaben 17); nur für eine laufende Periode sinnvoll."""

    enabled: bool = False
    entries: int = Field(default=50, ge=1, le=500)
    timezone: str = "Europe/Berlin"  # Zeitzone des Vorlagendatums: published um 00:00 Ortszeit
    # Ein Timer schreibt die Periode fort (Monitor); sonst zeigen die Feeds den Stand des Pakets,
    # und zeit.html sagt das (docs/plan-zeigen-2026-11.md, § 7)
    timer: bool = False

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"feeds.timezone {value!r} ist keine bekannte Zeitzone") from error
        return value


# --- Vorhaben 26: Beschlusslage und Antragserfolg (docs/plans/26-beschluesse.md) -----------------
# Die Klassen, die ein Wert von ``result`` tragen kann, je Stufe (Messdokument § 3.1, vorab
# festgelegt): ``sache`` ist eine Entscheidung in der Sache und ersetzt jede frühere, ``stand`` ist
# alles andere und zählt nur, wo es keine Entscheidung in der Sache gibt. ``ohne_ergebnis`` trägt
# kein Wert; es ist die Klasse eines Dokuments, für das der Datensatz keinen Eintrag hat.
OUTCOME_STAGES: dict[str, tuple[str, ...]] = {
    "sache": ("beschlossen", "geaendert", "abgelehnt", "zurueckgezogen"),
    "stand": ("erledigt", "vertagt", "offen"),
}


class OutcomeReview(_Strict):
    """Der beantragte Prüfauftrag im Beschlusstext eines Antrags (Messdokument § 3.4, Rückfall 1).

    Muster der deutschen Sprache der Ratsdokumente, keine Stadt; alle kleingeschrieben, eine Liste
    wird zu einer Alternative in ihrer Folge. Die Regel ist die vor der Stichprobe festgeschriebene
    (Commit ``94da91f``); sie fand 19 der 26 Prüfaufträge der Stichprobe (Recall 0,73) und steht
    darum nur als beschreibende Spalte da, nie auf der Seite.
    """

    marker: list[str] = []  # Beginn des Beschlusstexts; der letzte Treffer im Fenster gilt
    reason: list[str] = []  # Ende des Beschlusstexts (Begründung, Grußformel)
    reason_from: int = Field(default=40, ge=0)  # ab diesem Zeichen wird das Ende gesucht
    window: int = Field(default=2000, ge=1)  # in so vielen Zeichen vom Anfang steht der Marker
    max_chars: int = Field(default=1500, ge=1)  # höchstens so viel Beschlusstext
    review: list[str] = []  # Prüfwörter: ein Satz damit ist eine Prüfung
    not_review: list[str] = []  # Wörter mit einem Prüfwort darin, die keine Prüfung verlangen
    separable: list[str] = []  # trennbare Vorsilben eines „zu"-Infinitivs („einzurichten")
    not_verb: list[str] = []  # Wörter hinter „zu", die kein Verb sind („zu den", „zu Lasten")
    measure: list[str] = []  # weitere Formen einer festgelegten Handlung
    proviso: list[str] = []  # eine Maßnahme unter Vorbehalt der Prüfung gehört zur Prüfung
    neutral: list[str] = []  # Verben einer Prüfung oder eines Berichts: keine Maßnahme
    question: list[str] = []  # „prüfen, ob …": eine Maßnahme dahinter ist Teil der Frage
    question_chars: int = Field(default=60, ge=1)  # so weit hinter dem Prüfwort steht die Frage
    sentence: list[str] = []  # Satzgrenzen im Beschlusstext
    title: list[str] = []  # Prüfwort im Titel, wenn das Dokument keinen Text hat
    frame: list[str] = []  # Rahmensätze („bitten wir Sie"), die nichts beantragen

    @field_validator(
        "marker",
        "reason",
        "review",
        "not_review",
        "separable",
        "not_verb",
        "measure",
        "proviso",
        "question",
        "sentence",
        "title",
        "frame",
    )
    @classmethod
    def _patterns_compile(cls, value: list[str]) -> list[str]:
        return _compiles(value, "outcomes.review")


class Outcomes(_Strict):
    """Beschlusslage je Ratsdokument und Antragserfolg je Fraktion (Vorhaben 26).

    ``results`` ist der Wortschatz, den die Sitzungsleitung in ``result`` einträgt, mit Stufe und
    Klasse je Wert; er steht im Stadtprofil, und ein Wert, der fehlt, bricht den Schritt mit seinem
    Wortlaut ab, statt still ``ohne_ergebnis`` zu werden (Messdokument § 3.2). ``package`` ist die
    Tabelle „Paper × Tagesordnungspunkt" aus ``georep pack --outcomes`` für Läufe ohne Netz.
    """

    enabled: bool = False
    results: dict[str, tuple[Literal["sache", "stand"], str]] = {}
    package: Path | None = None
    practice_share: float = Field(default=0.4, gt=0.0, le=1.0)
    practice_min: int = Field(default=10, ge=1)
    followup_roles: list[ProcedureRole] = []  # Rollen aus Vorhaben 14
    review: OutcomeReview = OutcomeReview()
    # Stufe 3 (Messdokument § 3.9, § 7): die Werte aus ``results``, mit denen die Sitzungsleitung
    # einträgt, dass eine Anfrage beantwortet ist, und davon die schriftlichen; Wortlaut, keine Klasse
    answered: list[str] = []
    answered_written: list[str] = []

    @field_validator("package", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @field_validator("results")
    @classmethod
    def _class_fits_stage(cls, value: dict[str, tuple[str, str]]) -> dict[str, tuple[str, str]]:
        wrong = sorted(
            f"{result!r} = [{stage!r}, {klasse!r}]"
            for result, (stage, klasse) in value.items()
            if klasse not in OUTCOME_STAGES[stage]
        )
        if wrong:
            raise ValueError(
                f"outcomes.results: Klasse passt nicht zur Stufe in {wrong}; erlaubt sind "
                + "; ".join(f"{s}: {', '.join(k)}" for s, k in OUTCOME_STAGES.items())
            )
        if any(not result.strip() for result in value):
            raise ValueError("outcomes.results: ein leerer Wert ist kein Eintrag, sondern keiner")
        return value

    @model_validator(mode="after")
    def _enabled_needs_a_vocabulary(self) -> Outcomes:
        if self.enabled and not self.results:
            raise ValueError(
                "outcomes.enabled braucht den Wortschatz [outcomes.results] im Stadtprofil"
            )
        return self

    @model_validator(mode="after")
    def _answers_are_entries(self) -> Outcomes:
        unknown = sorted(set(self.answered) - set(self.results))
        if unknown:
            raise ValueError(f"outcomes.answered: {unknown} stehen nicht in [outcomes.results]")
        loose = sorted(set(self.answered_written) - set(self.answered))
        if loose:
            raise ValueError(f"outcomes.answered_written: {loose} stehen nicht in answered")
        return self


# --- Vorhaben 11: Struktur der Dokumente (docs/plans/11-struktur.md, § 3.2, § 6 und § 10) ----------


def _compiles_one(pattern: str, field: str) -> str:
    return _compiles([pattern], field)[0] if pattern else pattern


def _names_groups(pattern: str, groups: tuple[str, ...], field: str) -> str:
    """Ein Muster, dessen Treffer der Code nach Gruppen liest, muss diese Gruppen tragen."""
    if pattern:
        missing = [g for g in groups if g not in re.compile(pattern).groupindex]
        if missing:
            raise ValueError(f"{field}: {pattern!r} braucht die Gruppen {', '.join(missing)}")
    return pattern


CITY_PLACEHOLDER = "{city}"  # in ``structure.head`` steht der Ort der Datumszeile nur so


class StructureLead(_Strict):
    """Ein Einleitungssatz, der mit Doppelpunkt endet und einen Abschnitt ab der nächsten Zeile
    öffnet („… beschließen zu lassen:", „… folgende Fragen zu beantworten:")."""

    kind: str
    pattern: str

    @field_validator("pattern")
    @classmethod
    def _compiles(cls, value: str) -> str:
        return _compiles_one(value, "structure.leads")


class StructureFallback(_Strict):
    """Der Beschlusssatz einer Vorlage ohne Überschrift („Der Rat beschließt …"); er gehört selbst
    zum Abschnitt und wird nur in den Zeilen nach dem Kopf gesucht."""

    kind: str = "beschlussvorschlag"
    pattern: str = ""  # leer: kein Beschlusssatz
    max_lines_after_head: int = Field(default=12, ge=0)
    only_expected: bool = True  # nur in Arten mit erwartetem Beschlussvorschlag

    @field_validator("pattern")
    @classmethod
    def _compiles(cls, value: str) -> str:
        return _compiles_one(value, "structure.fallback")


class StructureHead(_Strict):
    """Die Felder des Kopfs: Beratungsfolge, Amtsbezeichnungen, Sitzung, Datumszeile, Formular."""

    consultation_header: str = ""
    quality: list[str] = []
    quality_placeholders: list[str] = []
    quality_required: bool = False
    titles: str = ""
    signer_roles: str = ""
    signer_window: int = Field(default=8, ge=0)
    closing: str = ""
    session: str = ""
    session_suffix: str = ""
    date_line: str = ""
    office: str = ""
    form_titles: list[str] = []
    head_lines: int = Field(default=30, ge=0)

    @field_validator("consultation_header", "titles", "signer_roles", "closing")
    @classmethod
    def _compiles(cls, value: str) -> str:
        return _compiles_one(value, "structure.head")

    @field_validator("session")
    @classmethod
    def _session_names_body_and_date(cls, value: str) -> str:
        return _names_groups(
            _compiles_one(value, "structure.head.session"),
            ("gremium", "datum"),
            "structure.head.session",
        )

    @field_validator("session_suffix", "date_line")
    @classmethod
    def _city_patterns_compile(cls, value: str) -> str:
        _compiles_one(value.replace(CITY_PLACEHOLDER, "Ort"), "structure.head")
        return value

    @field_validator("office")
    @classmethod
    def _office_names_number_and_name(cls, value: str) -> str:
        return _names_groups(
            _compiles_one(value, "structure.head.office"), ("nr", "name"), "structure.head.office"
        )

    @field_validator("date_line")
    @classmethod
    def _date_line_names_the_date(cls, value: str) -> str:
        _names_groups(
            value.replace(CITY_PLACEHOLDER, "Ort"), ("datum",), "structure.head.date_line"
        )
        return value


class StructureSettings(_Strict):
    """Abschnitte und Kopf je Ratsdokument (Vorhaben 11): die Muster des validierten Regelwerks.

    ``struktur-1`` ist ``struktur-entwurf-1`` aus dem Messskript unverändert (Messdokument 11,
    § 10, Punkt 1); die Stadt trägt ihre Muster im Profil, der Code kennt kein Stadtwort. Ein
    Label (``labels``) öffnet einen Abschnitt seiner Art; Arten in ``level2`` öffnen eine eigene
    Spanne, ohne den Abschnitt um sie herum zu schließen. Die Monatsnamen sind Sprache und stehen
    in ``defaults.toml``.
    """

    enabled: bool = False
    heading: str = ""
    heading_nocolon: str = ""
    betreff_after_form: bool = False
    betreff_max_lines: int = Field(default=4, ge=1)
    lead_blocked_in: list[str] = []
    level2: list[str] = []
    end_markers: list[str] = []
    art: list[tuple[str, str]] = []  # (Muster über paper_type, zusammengefasste Art), erste gewinnt
    decision_expected: list[str] = []
    decision_not_expected: list[str] = []
    labels: dict[str, str] = {}
    leads: list[StructureLead] = []
    fallback: StructureFallback = StructureFallback()
    head: StructureHead = StructureHead()
    page_noise: list[str] = []
    months: list[str] = []
    min_body_chars: int = Field(default=80, ge=0)

    @field_validator("heading", "heading_nocolon")
    @classmethod
    def _heading_names_label_and_rest(cls, value: str) -> str:
        return _names_groups(
            _compiles_one(value, "structure.heading"), ("label", "rest"), "structure.heading"
        )

    @field_validator("end_markers", "page_noise")
    @classmethod
    def _patterns_compile(cls, value: list[str]) -> list[str]:
        return _compiles(value, "structure patterns")

    @field_validator("art")
    @classmethod
    def _type_patterns_compile(cls, value: list[tuple[str, str]]) -> list[tuple[str, str]]:
        _compiles([pattern for pattern, _ in value], "structure.art")
        return value

    @model_validator(mode="after")
    def _kinds_are_label_kinds(self) -> StructureSettings:
        """Jede Art, die der Code öffnet oder sperrt, kommt aus den Labels oder einem Satz."""
        kinds = set(self.labels.values())
        opened = kinds | {lead.kind for lead in self.leads} | {self.fallback.kind}
        wrong = sorted(set(self.level2) - kinds) + sorted(set(self.lead_blocked_in) - opened)
        if wrong:
            raise ValueError(f"structure: Arten ohne Label: {', '.join(wrong)}")
        return self

    @model_validator(mode="after")
    def _enabled_needs_its_patterns(self) -> StructureSettings:
        if not self.enabled:
            return self
        if not self.heading:
            raise ValueError("structure.enabled braucht ein Muster in structure.heading")
        if len(self.months) != 12:
            raise ValueError(f"structure.months: zwölf Monatsnamen, nicht {len(self.months)}")
        return self


# --- Vorhaben 12: Kennungen und Beträge (docs/plans/12-kennungen.md, § 6 und § 10)

# Die Arten, die das Kriterium erreicht haben (Messdokument § 5): Bauleitplanung, Betrag, Termin,
# Verwaltungseinheit. Haushalt und Rechtsgrundlage fielen und sind keine Wahl.
IdentifierKind = Literal["bplan", "fnp", "betrag", "termin", "amt", "dezernat"]
IDENTIFIER_KINDS: tuple[IdentifierKind, ...] = (
    "bplan",
    "fnp",
    "betrag",
    "termin",
    "amt",
    "dezernat",
)


def _pattern_with_groups(value: str, field: str, groups: tuple[str, ...]) -> str:
    """Ein Muster, das übersetzt und die benannten Gruppen trägt, die der Code liest; leer heißt aus."""
    if not value:
        return value
    compiled = re.compile(_compiles([value], field)[0])
    missing = [group for group in groups if group not in compiled.groupindex]
    if missing:
        raise ValueError(f"{field}: {value!r} braucht die Gruppen {missing}")
    return value


class PlanNorm(_Strict):
    """Eine Schreibweise einer Plannummer und ihre Normalform (``re.fullmatch``, dann ``expand``).

    Beispiel: ``(\\d{4})[ /-]?(\\d{2})`` mit ``\\1/0\\2`` macht aus „5674/26" „5674/026".
    """

    pattern: str
    replace: str

    @model_validator(mode="after")
    def _expands(self) -> PlanNorm:
        compiled = re.compile(_compiles([self.pattern], "identifiers.plans.norms[].pattern")[0])
        try:
            compiled.sub(self.replace, "")  # übersetzt die Vorlage und prüft ihre Rückverweise
        except (re.error, IndexError) as error:
            raise ValueError(
                f"identifiers.plans.norms: {self.replace!r} passt nicht zu {self.pattern!r}"
            ) from error
        return self


class IdentifierPlans(_Strict):
    """Art 1, Bauleitplanung (Fassung 1 der Messung): Nummern von Bebauungsplänen und FNP-Änderungen.

    Die Schlüsselwörter sind die der Sprache (``defaults.toml``), das Nummernformat und seine
    Normalformen die der Stadt (Profil). Ohne ``number`` gibt es keine Bebauungspläne, ohne
    ``fnp_keyword`` keine FNP-Änderungen.
    """

    keyword: str = ""  # Bebauungsplan, B-Plan, Fluchtlinien-, Durchführungsplan
    number: str = ""  # Nummernformat der Stadt; im Profil
    norms: list[PlanNorm] = []  # die erste, die passt, gilt; sonst ohne Leerraum, groß
    list_words: str = ""  # Verbinder einer Liste von Nummern („Nr. 5481/006 und 5481/007")
    number_word: str = ""  # „Nr.", „Nummer" vor der Nummer
    fnp_keyword: str = ""  # Flächennutzungsplanänderung, FNP-Änderung, FNP
    fnp_draft: str = ""  # „(Entwurf)" zwischen Schlüsselwort und Nummer
    fnp_ordinal: str = ""  # „die 188. Änderung des Flächennutzungsplans"; Gruppe n

    @field_validator("keyword", "number", "list_words", "number_word", "fnp_keyword", "fnp_draft")
    @classmethod
    def _compile(cls, value: str) -> str:
        return _compiles([value], "identifiers.plans")[0] if value else value

    @field_validator("fnp_ordinal")
    @classmethod
    def _ordinal(cls, value: str) -> str:
        return _pattern_with_groups(value, "identifiers.plans.fnp_ordinal", ("n",))


class AmountMultiplier(_Strict):
    """Ein Faktor hinter der Zahl („2,5 Mio. €"); ``pattern`` passt auf das ganze Wort."""

    pattern: str
    factor: int = Field(ge=1)

    @field_validator("pattern")
    @classmethod
    def _compile(cls, value: str) -> str:
        return _compiles([value], "identifiers.amounts.multipliers[].pattern")[0]


class IdentifierAmounts(_Strict):
    """Art 3, Betrag (Fassung 1 der Messung, ohne Rolle): Zahl mit Einheit, Faktor, Einheit vorn."""

    units_after: list[str] = []  # Einheit hinter der Zahl („5.000 Euro", „300 T€")
    units_before: list[str] = []  # Einheit vor der Zahl („EUR 2.700")
    thousand_units: list[str] = []  # Einheiten in Tausend, ohne Leerzeichen und groß verglichen
    multipliers: list[AmountMultiplier] = []
    range_words: str = ""  # „5.000 bis 10.000 Euro": die erste Zahl erbt Einheit und Faktor
    per_words: str = ""  # „12,50 €/m²", „je Monat": der Betrag ist ein Preis je Einheit
    per_units: list[str] = []

    @field_validator("units_after", "units_before", "per_units")
    @classmethod
    def _compile_list(cls, value: list[str]) -> list[str]:
        return _compiles(value, "identifiers.amounts")

    @field_validator("range_words", "per_words")
    @classmethod
    def _compile(cls, value: str) -> str:
        return _compiles([value], "identifiers.amounts")[0] if value else value


class RelativeDate(_Strict):
    """Eine Zeitangabe ohne Datum („in der nächsten Sitzung"); ``norm`` ist ihr Normwert."""

    norm: str
    pattern: str

    @field_validator("pattern")
    @classmethod
    def _compile(cls, value: str) -> str:
        return _compiles([value], "identifiers.dates.relative[].pattern")[0]


class IdentifierDates(_Strict):
    """Art 4, Termin (Fassung 2 der Messung, ohne Funktion): Datum, Monat, Quartal, Jahr, relativ."""

    months: dict[str, int] = {}  # Muster -> Monat, in der Folge der Alternative
    quarter: str = ""  # „3. Quartal 2024" -> 2024-Q3
    half_year: str = ""  # „1. Halbjahr 2024" -> 2024-H1
    month_qualifiers: list[str] = []  # „Ende Februar 2021" -> 2021-02~ende
    year_qualifiers: list[str] = []  # „Ende 2024" -> 2024~ende
    qualifier_norms: dict[str, str] = {}  # Umschrift eines Zusatzes -> Normwert
    of_the_year: str = ""  # „Ende des Jahres 2023"
    range_words: str = ""  # „10. und 11. Juni 2023": die erste Angabe erbt Monat und Jahr
    relative: list[RelativeDate] = []

    @field_validator("months")
    @classmethod
    def _months(cls, value: dict[str, int]) -> dict[str, int]:
        _compiles(list(value), "identifiers.dates.months")
        wrong = sorted(name for name, month in value.items() if not 1 <= month <= 12)
        if wrong:
            raise ValueError(f"identifiers.dates.months: kein Monat 1 bis 12 für {wrong}")
        return value

    @field_validator("month_qualifiers", "year_qualifiers")
    @classmethod
    def _compile_list(cls, value: list[str]) -> list[str]:
        return _compiles(value, "identifiers.dates")

    @field_validator("quarter", "half_year", "of_the_year", "range_words")
    @classmethod
    def _compile(cls, value: str) -> str:
        return _compiles([value], "identifiers.dates")[0] if value else value


class IdentifierOffices(_Strict):
    """Art 6, Verwaltungseinheit (Fassung 2 der Messung): Ämter aus Kopf und Text, „Dezernat NN".

    Das Kopffeld und seine Form (Nummer und Name) sind die der Stadt (Profil); das
    Ämterverzeichnis (Name -> Nummer) entsteht je Lauf aus den Kopffeldern des Korpus, keine Liste
    im Profil (Synergien 2026-11, § 1). Ein Dezernat kommt nur aus dem Text.
    """

    head_chars: int = Field(default=6000, ge=1)  # so weit liest das Kopffeld
    head: str = ""  # Kopffeld des federführenden Amts; Gruppe v; im Profil
    head_code: str = ""  # Wert des Kopffelds als Nummer und Name; Gruppen code, name; im Profil
    number: str = ""  # „Amt 66", „Amt 01/17"; Gruppen n und u
    number_extra: str = ""  # eine zweite Nummernform der Stadt („FB 64"); Gruppe n; im Profil
    text: str = ""  # eine Einheit, die die Stadt ohne Verzeichnis nennt; Gruppe n; im Profil
    text_norm: str = ""  # ihr Normwert, mit der Nummer aus Gruppe n dahinter, wenn es eine gibt
    word: str = ""  # jedes Wort auf -amt; Gruppe name
    word_not: str = ""  # Wörter auf -amt, die kein Amt der Stadt nennen
    bracket: str = ""  # Nummer in Klammern hinter einem Namen aus dem Verzeichnis
    committee_before: str = ""  # „Ausschuss für" vor einem Namen: ein Gremium, kein Amt
    committee_words: str = ""  # ein Kopffeld mit diesen Wörtern nennt ein Gremium
    code_before: str = ""  # „64 - Amt für Wohnungswesen" im Text: die Nummer davor gehört dazu
    directory_min_count: int = Field(default=3, ge=1)  # so oft muss ein Name im Kopf stehen
    directory_min_chars: int = Field(default=8, ge=1)  # kürzere Namen nur mit directory_word
    directory_word: str = ""  # ein Name mit diesem Wort darf kürzer sein („Sportamt")
    department: str = ""  # „Dezernat 06"; Gruppe n

    @field_validator("word_not", "bracket", "committee_before", "committee_words", "code_before")
    @classmethod
    def _compile(cls, value: str) -> str:
        return _compiles([value], "identifiers.offices")[0] if value else value

    @model_validator(mode="after")
    def _groups(self) -> IdentifierOffices:
        for field, groups in (
            ("head", ("v",)),
            ("head_code", ("code", "name")),
            ("number", ("n", "u")),
            ("number_extra", ("n",)),
            ("text", ("n",)),
            ("word", ("name",)),
            ("department", ("n",)),
        ):
            _pattern_with_groups(getattr(self, field), f"identifiers.offices.{field}", groups)
        if self.text and not self.text_norm:
            raise ValueError("identifiers.offices.text braucht text_norm")
        return self


class Identifiers(_Strict):
    """Kennungen und Beträge als Spannen im Rohtext (Vorhaben 12, Schritt ``identifiers``).

    Gebaut sind genau die Arten und Fassungen, die die Validierung bestanden haben (Messdokument
    § 5): Bauleitplanung und Betrag in Fassung 1, Termin und Verwaltungseinheit in Fassung 2. Die
    Sprache steht in ``defaults.toml``, Nummernformate und Kopffelder im Stadtprofil.
    """

    enabled: bool = False
    kinds: list[IdentifierKind] = list(IDENTIFIER_KINDS)
    plans: IdentifierPlans = IdentifierPlans()
    amounts: IdentifierAmounts = IdentifierAmounts()
    dates: IdentifierDates = IdentifierDates()
    offices: IdentifierOffices = IdentifierOffices()

    @field_validator("kinds")
    @classmethod
    def _unique(cls, value: list[IdentifierKind]) -> list[IdentifierKind]:
        if len(set(value)) != len(value):
            raise ValueError(f"identifiers.kinds: doppelt in {value}")
        return value


# --- Vorhaben 20: Kurzfassungen (docs/plans/20-kurzfassungen.md, § 6 und § 10) -------------------
class Summaries(_Strict):
    """Kurzfassungen je Dokument mit einem lokalen Modell (Vorhaben 20); nie veröffentlicht.

    Das Modell steht hier und nicht in ``[ml.generation]``, weil Vorhaben 19 dort ein anderes nennen
    darf; die Optionen (Temperatur, Seed, Fenster, Antwortlänge) kommen von dort. Was die Eingabe
    bestimmt (``budget_chars``) und was die Treueprüfung (``rare_share``, ``known_documents``),
    zählt zum Fingerprint; das Modell steht zusätzlich als Kennung im Stamp des Schritts.
    """

    enabled: bool = False
    model: str = "gemma4"
    budget_chars: int = Field(default=8000, ge=1)
    rare_share: float = Field(default=0.01, gt=0.0, lt=1.0)
    known_documents: int = Field(default=3, ge=1)
    # Regel 5 (Review von 11, 2026-11-24): Anrede, Titel oder Amt vor einem Personennamen; die
    # Treueprüfung zählt Namen dahinter neben ``ok``. Leer: keine Zählung
    person_titles: str = ""

    @field_validator("person_titles")
    @classmethod
    def _compiles(cls, value: str) -> str:
        return _compiles([value], "summaries.person_titles")[0]


# --- Vorhaben 16: Ortsbezug (docs/plans/16-ortsbezug.md, § 6 und § 10) ----------------------------
# Die fünf groben Stellen eines Treffers in ihrer Rangfolge; ``search.positions`` hält dieselben
# Namen (ein Test hält beide gleich), die Gewichte nach Stelle nennen genau diese.
PLACE_POSITIONS = ("titel", "betreff", "kern", "begleittext", "rest")


class PlacesSettings(_Strict):
    """Stelle je Treffer, Hausnummern und die Gewichtungen ``ortsbezug`` und ``stelle`` (Vorhaben 16).

    ``list_max_line``, ``list_max_lead`` und ``house_number`` sind die Konstanten von Nebenregel C
    aus dem Messskript (``LISTE_MAX_ZEILE``, ``LISTE_MAX_VORLAUF``, ``HAUSNR``), unverändert: jede
    Änderung ist ein neues Verfahren und braucht eine neue Stichprobe (Messdokument § 6). Das Muster
    der Hausnummer ist sprachabhängig und steht im Stadtprofil; ``package`` ist ein Pfad wie
    ``outcomes.package`` und zählt nicht zum Fingerprint.
    """

    enabled: bool = False
    package: Path | None = None  # Paket snapshots/<stadt>-adressen; bootstrap kopiert es
    house_numbers: bool = False
    house_number: str = ""
    list_max_line: int = Field(default=60, ge=1)
    list_max_lead: int = Field(default=12, ge=0)
    position_weights: dict[str, float] = {
        "titel": 1.0,
        "betreff": 1.0,
        "kern": 1.0,
        "begleittext": 0.5,
        "rest": 0.25,
    }

    @field_validator("package", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @field_validator("house_number")
    @classmethod
    def _house_number_compiles(cls, value: str) -> str:
        return _compiles_one(value, "places.house_number")

    @field_validator("position_weights")
    @classmethod
    def _five_positions(cls, value: dict[str, float]) -> dict[str, float]:
        if sorted(value) != sorted(PLACE_POSITIONS):
            raise ValueError(
                f"places.position_weights nennt {sorted(value)}, nicht genau {PLACE_POSITIONS}"
            )
        for position, weight in value.items():
            _unit_interval(f"places.position_weights.{position}", weight)
        return value

    @model_validator(mode="after")
    def _house_numbers_need_the_pattern(self) -> PlacesSettings:
        if self.house_numbers:
            if not self.house_number:
                raise ValueError("places.house_numbers ohne places.house_number")
            _names_groups(self.house_number, ("nr", "zusatz"), "places.house_number")
        return self


# --- Vorhaben 28: Abstimmungen (docs/plans/28-abstimmungen.md, § 6, § 8 und § 10) ----------------
# Die Klassen der Wortregel (§ 8.1) in ihrer Folge; was keine Regel trifft, auch ein leerer Eintrag,
# ist ``sonstiges``. Entschieden sind nur ``angenommen`` und ``abgelehnt``: nur sie tragen eine Form.
VOTE_RESULTS: tuple[str, ...] = (
    "zurueckgezogen",
    "vertagt",
    "verwiesen",
    "abgelehnt",
    "angenommen",
    "kenntnis",
    "erledigt",
)
VOTE_OTHER = "sonstiges"
VOTE_DECIDED: tuple[str, ...] = ("angenommen", "abgelehnt")
VoteResult = Literal[
    "zurueckgezogen", "vertagt", "verwiesen", "abgelehnt", "angenommen", "kenntnis", "erledigt"
]
# Die vorab festgelegten Rechnungen von H28.2 (§ 8.6) mit eigenem Zeitraum im Profil: der Haupttest
# und die Nebenrechnung R2; R1, R3 und R4 rechnen im Zeitraum des Haupttests.
VoteCalculation = Literal["haupttest", "R2"]


class VoteRule(_Strict):
    """Eine Zeile der Wortregel: enthält ``result`` (kleingeschrieben) eines der Wörter, gilt die Klasse."""

    result: VoteResult
    words: list[str]

    @field_validator("words")
    @classmethod
    def _lowercase_and_filled(cls, value: list[str]) -> list[str]:
        if not value or any(not word or word != word.lower() for word in value):
            raise ValueError(f"votes.results: Wörter klein und nicht leer, nicht {value}")
        return value


class VoteWindow(_Strict):
    """Ein vorab festgelegter Zeitraum für H28.2 (§ 8.4), beide Grenzen einschließlich.

    Die Mehrheit gilt hier ab dem Monat ihrer Vereinbarung, nicht ab der Wahlperiode des Rates
    (anders als ``[majorities]``, Punkt 75): so steht es im Messdokument, bevor ein Ergebnis gezählt
    war. Welche Parteien die Mehrheit sind, sagt ``majorities.on(start)``.
    """

    calculation: VoteCalculation
    start: date
    end: date | None = None  # None: offen (laufende Periode)

    @model_validator(mode="after")
    def _ordered(self) -> VoteWindow:
        if self.end is not None and self.end < self.start:
            raise ValueError(f"votes.windows: {self.calculation} endet vor seinem Beginn")
        return self

    def within(self, period: Period) -> bool:
        """Ob der Zeitraum ganz in der Periode eines Profils liegt: nur dort wird er gerechnet."""
        if self.start < period.start:
            return False
        if period.end is None:
            return True
        return self.end is not None and self.end <= period.end


class Votes(_Strict):
    """Abstimmungen je Tagesordnungspunkt (Vorhaben 28, nur Ebene A nach § 5.1 des Messdokuments).

    Die Eingabe ist der Beratungsverlauf von Vorhaben 26; ohne ``outcomes.enabled`` fehlt der
    Schritt. ``results`` ist die Wortregel aus § 8.1, vorab festgelegt im Commit ``fixed``. Sie steht
    in ``defaults.toml``, weil sie die Sprache der Sitzungsleitung liest und keine Stadt, und ein Test
    hält sie gleich der des Messskripts. Was nur eine Stadt kennt (die Zeiträume der Mehrheit, die
    Fraktion der WZB-Schwelle), steht im Stadtprofil.
    """

    enabled: bool = False
    results: list[VoteRule] = []
    changed: list[str] = []  # „abweichend", „geändert": angenommen mit Änderung
    unanimous: list[str] = []  # Form einstimmig
    majority: list[str] = []  # Form mehrheitlich
    # H28.2 (§ 8.6): ein Antrag ist eine Drucksache, deren Dokumentart (klein) ``motion_type``
    # enthält und ``motion_not`` nicht; den Urheber nennt Option 04 (``dokumente_urheber``)
    motion_type: str = ""
    motion_not: str = ""
    # Parteischlüssel aus [originators], deren Anträge H28.2 auslässt: sie prüft H28.3 (WZB-Schwelle)
    excluded_parties: list[str] = []
    windows: list[VoteWindow] = []
    threshold: float = Field(default=0.25, gt=0.0, lt=1.0)  # H28.2: Anteil angenommen unter …
    min_units: int = Field(default=30, ge=1)  # darunter nicht entscheidbar
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)  # Holm über H28.1 bis H28.3, p_holm < alpha
    fixed: str = ""  # Commit der Festlegung (§ 8)
    fixed_on: date | None = None  # Tag der Festlegung; Anzeige, nicht im Fingerprint

    @field_validator("changed", "unanimous", "majority")
    @classmethod
    def _lowercase(cls, value: list[str]) -> list[str]:
        if any(not word or word != word.lower() for word in value):
            raise ValueError(f"votes: Wörter klein und nicht leer, nicht {value}")
        return value

    @model_validator(mode="after")
    def _complete(self) -> Votes:
        classes = [rule.result for rule in self.results]
        if len(set(classes)) != len(classes):
            raise ValueError(f"votes.results: eine Klasse steht zweimal in {classes}")
        calculations = [window.calculation for window in self.windows]
        if len(set(calculations)) != len(calculations):
            raise ValueError(f"votes.windows: eine Rechnung steht zweimal in {calculations}")
        if self.enabled and not (self.results and self.unanimous and self.majority):
            raise ValueError("votes.enabled braucht die Wortregel (results, unanimous, majority)")
        if self.windows and not (self.motion_type and self.fixed):
            raise ValueError("votes.windows braucht motion_type und den Commit der Festlegung")
        return self


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
    council: Council = Council()  # Fundament F6: Sitzungen, Beratungen, Personen
    validation: Validation = Validation()  # Fundament F4
    ml: Ml = Ml()  # Fundament F5: lokale Modelle über ollama
    functions: Functions = Functions()  # Vorhaben 15: Dokumentfunktion und Antragsteller
    majorities: Majorities = (
        Majorities()
    )  # Vorhaben 15: Ratsmehrheiten, stadtweit (24, 28 lesen sie)
    procedures: Procedures = Procedures()  # Vorhaben 14: Vorgänge
    embeddings: Embeddings = Embeddings()  # Vorhaben 18: Einbettungen, Ähnlichkeit, Suche
    cycles: Cycles = Cycles()  # Vorhaben 17: Rhythmus, Vokabular, Tests über Perioden
    outcomes: Outcomes = Outcomes()  # Vorhaben 26: Beschlusslage und Antragserfolg
    feeds: Feeds = Feeds()  # Vorhaben 17: Atom-Feed je Wahlbezirk
    structure: StructureSettings = StructureSettings()  # Vorhaben 11: Struktur der Dokumente
    identifiers: Identifiers = Identifiers()  # Vorhaben 12: Kennungen und Beträge
    summaries: Summaries = Summaries()  # Vorhaben 20: Kurzfassungen, nie veröffentlicht
    street_points: StreetPoints = StreetPoints()  # Startseite: Straßenpunkte, Ortsnamen
    places: PlacesSettings = PlacesSettings()  # Vorhaben 16: Ortsbezug
    votes: Votes = Votes()  # Vorhaben 28: Abstimmungen je Tagesordnungspunkt (Ebene A)

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
        Fundament F5: ``[ml]`` steht ganz draußen. Was davon ein Ergebnis bestimmt (Modell,
        Optionen, Fenster), steht als Kennung im Stamp des Modellschritts, und ``limit`` als Zahl
        der offenen Eingaben; der Rest ist Ort und Laufzeit.
        Vorhaben 14 und 26: ``procedures.attachments`` und ``outcomes.package`` sind Pfade; der
        Inhalt der Pakete steht als Eingabe im Stamp der Schritte, die ihre Kopie in ``raw/`` lesen.
        Vorhaben 22: ``context.need.package`` ist ein Pfad, die Namensnennungen der Bedarfsquellen
        sind Anzeige, ``context.need.fetch`` schaltet nur den Netzschritt ein; Archive, Band,
        Klassen und Hypothesen zählen.
        Vorhaben 17: ``feeds.timer`` ist Anzeige (ein Satz auf ``zeit.html``) und steht im Zusatz
        von ``report``.
        Startseite: ``[street_points]`` steht ganz draußen; Quelle, Raster und Namen der Stadtteile
        trägt der Stamp des Netzschritts ``street_points`` als ``extra``.
        Vorhaben 16: ``places.package`` ist ein Pfad; die Kopie des Pakets steht im Stamp von
        ``places``.
        Vorhaben 28: ``votes.fixed_on`` ist Anzeige wie bei 22; Wortregel, Zeiträume und Commit zählen.
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
                # Fundament F6: ``[council]`` betrifft nur drei Netzschritte; ihr Stamp trägt den
                # Hash als ``extra`` (``georep.council.council_digest``, Muster Punkt 53)
                "council": True,
                # Fundament F4: Pfade der Validierung und die Schwelle für Stufe 3; kein Schritt
                # der Kette liest sie.
                "validation": True,
                # Punkt 58: ``consultations`` ist ein Pfad (sein Inhalt steht im Stamp des
                # Schritts ``bodies``), ``district_body_names`` sind reine Anzeigenamen.
                "bodies": {"names_as_of", "names_source", "consultations", "district_body_names"},
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
                    # Vorhaben 22: das Paket ist ein Pfad, die Namensnennungen sind Anzeige;
                    # URLs, Band, Klassen und Hypothesen zählen.
                    "need": {
                        "package": True,
                        "fetch": True,  # N1: ob need_data im Register steht, nicht was es schreibt
                        "accidents": {"attribution"},
                        "grid": {"attribution"},
                        "schools": {"attribution"},
                        # Stufe 3: der Tag der Festlegung ist Anzeige, der Commit zählt
                        "hypotheses": {"__all__": {"fixed_on"}},
                    },
                },
                "period": {"label"},
                "sources": {"opendata": {"districts_file"}},
                "crosswalk": {"target_file"},
                # Fundament F5: nichts aus ``[ml]``. Modell, Digest, Prompt-Version, Optionen und
                # die offenen Eingaben eines Teillaufs stehen im Stamp des Modellschritts
                # (``ModelUse``); hier ließen sie jeden Schritt neu laufen (Review 2026-11-23).
                "ml": True,
                # Vorhaben 18: der Pfad des Nachbarpakets (sein Inhalt steht im Stamp von
                # neighbors) und was nur ``georep search`` liest, kein Schritt (Review, N4)
                "embeddings": {"neighbors_package", "bm25", "rrf_k", "fusion_depth"},
                # Vorhaben 14 und 26 (Review von 26, N5): die Pakete sind Pfade wie
                # ``bodies.consultations``; ``bootstrap`` kopiert sie nach ``raw/``, und die Kopie
                # steht mit ihrem SHA-256 als Eingabe im Stamp von ``references``, ``procedures``
                # und ``council_results``. Ob es ein Anlagenpaket gibt, entscheidet dort die
                # Liste der Eingaben, nicht der Fingerprint.
                "procedures": {"attachments"},
                "outcomes": {"package"},
                # Vorhaben 17, Review K2: ``feeds.timer`` ändert nur einen Satz auf zeit.html;
                # er steht im Zusatz von ``report`` und der Unterseiten (``report_fingerprint``)
                "feeds": {"timer"},
                # plan-startseite, § 4.2: der Block betrifft nur den Netzschritt ``street_points``
                # (sein Stamp trägt Quelle, Raster und Namen als ``extra``, Muster Punkt 53) und
                # ``report``, der die Kopie des Pakets als Eingabe liest; hier ließe er jeden
                # Schritt neu laufen
                "street_points": True,
                # Vorhaben 16: das Adresspaket ist ein Pfad; ``bootstrap`` kopiert es nach
                # ``external/adressen/``, und die Kopie steht als Eingabe im Stamp von ``places``
                "places": {"package"},
                # Vorhaben 28: der Tag der Festlegung ist Anzeige wie bei 22, der Commit zählt
                "votes": {"fixed_on"},
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


def profile_folder(name: str, folder: Traversable | None = None) -> str:
    """Der Ordner eines Paketprofils unter ``data_root``: sein ``profile``, wie es die Kette setzt.

    Vorhaben 14, Review K3: ``duesseldorf-vergleich`` heißt anders als die Hauptperiode, rechnet
    aber in ihrem Ordner. Wer wissen will, ob ein anderes Profil dieselben Daten meint, vergleicht
    den Ordner, nicht den Namen. Gelesen werden nur die Profile im Paket, keine lokalen Dateien.
    """
    return str(_profile_layer(name, folder).get("profile", ""))
