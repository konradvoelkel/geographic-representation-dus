"""Shim für den Altcode: die alten Konstanten, abgeleitet aus ``georep.settings`` und ``georep.layout``.

Bis 2026-10-11 standen hier Pfade unter ``<repo>/data`` und alle Parameter fest im Code. Jetzt
kommen sie aus ``defaults.toml``, ``settings.toml``, ``settings.local.toml`` und ``GEOREP_*``;
Laufzeitdaten liegen unter ``data_root``, der Datensatz der Arbeit unter ``reference_root`` und
wird nur gelesen (``georep bootstrap`` kopiert ihn). Dieses Modul verschwindet mit dem letzten
Altcode-Leser.
"""

import sys
from pathlib import Path

from loguru import logger

from georep.layout import Layout
from georep.settings import load_settings

_settings = load_settings()
_layout = Layout.from_settings(_settings)


def setup_logging(level: str | None = None) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level or _settings.log_level,
    )


setup_logging()

# URLs
OPARL_ENDPOINT = _settings.sources.oparl.endpoint
WIKIPEDIA_ENDPOINT = _settings.sources.wikidata.wikipedia_api
WIKIDATA_ENDPOINT = _settings.sources.wikidata.sparql_endpoint
OPENDATA_ENDPOINT_WAHLERGEBNIS = _settings.sources.opendata.results_url
OPENDATA_ENDPOINT_STIMMBEZIRK = _settings.sources.opendata.districts_url

# SPARQL-Query (Wikidata)
LANGUAGE = _settings.sources.wikidata.language
TARGET_ENTITY = _settings.sources.wikidata.entity


def build_sparql_query(entity: str = TARGET_ENTITY, language: str = LANGUAGE) -> str:
    """Alle Wikidata-Objekte mit Koordinaten in der Verwaltungseinheit ``entity`` (P131*)
    samt Wikipedia-Artikel in ``language``."""
    return f"""
SELECT ?item ?itemLabel ?coord ?article WHERE {{
  ?item wdt:P625 ?coord.
  ?item wdt:P131* wd:{entity}.
  ?article schema:about ?item;
           schema:isPartOf <https://{language}.wikipedia.org/>;
           schema:name ?articleName.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{language}". }}
}}
"""


QUERY = build_sparql_query()
USER_AGENT = _settings.http.user_agent
WIKI_EXCLUDE_LIST = list(_settings.search.exclude)

# Geodata
CRS = _settings.geo.output_crs
GEOSEARCH_LIMIT = _settings.sources.wikidata.geosearch_limit
OSMNX_CACHING = False

# Requests
DELAY = _settings.sources.oparl.delay_s
HTTP_TIMEOUT_S = _settings.http.timeout_s
HTTP_RETRIES = _settings.http.retries

# Directory-paths
ROOT = Path(__file__).parent.parent.resolve()
RAW_DATA_PATH = _layout.raw
EXTERNAL_DATA_PATH = _layout.external
INTERIM_DATA_PATH = _layout.interim
PROCESSED_DATA_PATH = _layout.processed

# Filepaths: Eingaben wie geliefert
STIMMBEZIRK_SHAPEFILE_PATH = _layout.districts_geojson
WAHLERGEBNIS_PATH = _layout.results_csv
PAPER_URL_LISTE = _layout.paper_urls
PAPER_OBJECT_LISTE = _layout.paper_objects
PDF_DUMP_PATH = _layout.pdf_dir
STREET_PER_DISTRICT_PATH = _layout.streets
WIKI_DICT = _layout.pois
# Korpus im Altformat
PAPER_WITH_TEXT_PATH = _layout.corpus_legacy
# Ergebnisse des Altcodes (CSV); die Polars-Schritte schreiben daneben Parquet
AGG_STREETS_PER_WAHLBEZIRK_PATH = _layout.processed / "wahlbezirke_strassen.csv"
AGG_VOTERS_PER_WAHLBEZIRK_PATH = _layout.processed / "wahlbezirke_waehler.csv"
AGG_WIKIDATA_PATH = _layout.processed / "wikidata_agg.csv"
COMBINED_SEARCHDICT_PATH = _layout.processed / "combined_searchdict.csv"
INVERTED_INDEX_PATH = _layout.processed / "inverted_index.csv"
WIKIDATA_VIS_PATH = _layout.processed / "wikidata_vis.csv"
AUSWERTUNG_PATH = _layout.processed / "wahlbezirke_auswertung.csv"

# Beobachtungszeitraum, ISO-Strings wie im Altcode
START = _settings.period.start.isoformat()
ENDE = _settings.period.end.isoformat()
