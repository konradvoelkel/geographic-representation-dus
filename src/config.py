"""

Module for setting up logging configurations and defining endpoints, paths, queries, and related constants.

This module provides basic logging setup, defines various API endpoints, SPARQL queries, folder
and file paths, and other configuration variables. These constants and configurations are
used across the application for managing data, endpoints, and query executions.

"""
import sys
from pathlib import Path

from loguru import logger


#Logging-Setup
def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG"
    )

setup_logging()

# URLs
OPARL_ENDPOINT = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers"
WIKIPEDIA_ENDPOINT = "https://de.wikipedia.org/w/api.php"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
OPENDATA_ENDPOINT_WAHLERGEBNIS = "https://opendata.duesseldorf.de/sites/default/files/KW_Rat_2025_09_14_Endgültiges_Ergebnis_Stimmbezirke_0.csv"
OPENDATA_ENDPOINT_STIMMBEZIRK = "https://opendata.duesseldorf.de/sites/default/files/Stimmbezirke%202025_ETRS89_EPSG4647.geojson"

# SPARQL-Query (Wikidata)
LANGUAGE = "de"
TARGET_ENTITY = "Q1718"  # Düsseldorf
QUERY = """
SELECT ?item ?itemLabel ?coord ?article WHERE {
  ?item wdt:P625 ?coord.
  ?item wdt:P131* wd:Q1718.  # liegt in Verwaltungseinheit Düsseldorf
  ?article schema:about ?item;
           schema:isPartOf <https://de.wikipedia.org/>;
           schema:name ?articleName.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de". }
}
"""
USER_AGENT = "Wikipedia-Geodata-Extractor/1.0 (Python/Bachelorarbeit)"
WIKI_EXCLUDE_LIST = [
    "Düsseldorf",
    "Düssel",
    "Stadtbezirk 1", "Altstadt", "Carlstadt", "Stadtmitte", "Pempelfort", "Derendorf", "Golzheim",
"Stadtbezirk 2", "Flingern-Nord", "Flingern-Süd", "Düsseltal", "Flingern",
"Stadtbezirk 3", "Oberbilk", "Unterbilk", "Bilk", "Friedrichstadt", "Hafen", "Hamm", "Flehe", "Volmerswerth",
"Stadtbezirk 4", "Oberkassel", "Heerdt", "Lörick", "Niederkassel",
"Stadtbezirk 5", "Stockum", "Lohausen", "Kaiserswerth", "Wittlaer", "Kalkum", "Angermund",
"Stadtbezirk 6", "Lichtenbroich", "Unterrath", "Rath", "Mörsenbroich",
"Stadtbezirk 7", "Gerresheim", "Grafenberg", "Ludenberg", "Hubbelrath", "Knittkuhl",
"Stadtbezirk 8", "Eller", "Lierenfeld", "Vennhausen", "Unterbach",
"Stadtbezirk 9", "Wersten", "Holthausen", "Reisholz", "Benrath", "Urdenbach", "Hassels", "Itter", "Himmelgeist",
"Stadtbezirk 10", "Garath", "Hellerhof"
]

# Geodata
CRS = "EPSG:4326"
GEOSEARCH_LIMIT = 500
OSMNX_CACHING = False

# Requests
DELAY = 1

# Directory-paths
ROOT = Path(__file__).parent.parent.resolve()
RAW_DATA_PATH = ROOT / "data" / "raw"
EXTERNAL_DATA_PATH = ROOT / "data" / "external"
INTERIM_DATA_PATH = ROOT / "data" / "interim"
PROCESSED_DATA_PATH = ROOT / "data" / "processed"

# Filepaths
# external data
STIMMBEZIRK_SHAPEFILE_PATH = EXTERNAL_DATA_PATH / "Stimmbezirke_2025.geojson"
WAHLERGEBNIS_PATH = EXTERNAL_DATA_PATH / "Stimmbezirk_Wahlergebnis.csv"

#Raw Data: Import-Step
PAPER_URL_LISTE = RAW_DATA_PATH / "paper_urls.json"
PAPER_OBJECT_LISTE = RAW_DATA_PATH / "paper_objects.json"
PDF_DUMP_PATH = RAW_DATA_PATH / "oparl_paper_pdf"
STREET_PER_DISTRICT_PATH = RAW_DATA_PATH / "streets_per_district.json"
WIKI_DICT = RAW_DATA_PATH / "wikipedia_dict.json"
#Prepped data
PAPER_WITH_TEXT_PATH = INTERIM_DATA_PATH / "paper_with_text.json"
# Final data for analyzing
AGG_STREETS_PER_WAHLBEZIRK_PATH = PROCESSED_DATA_PATH / "wahlbezirke_strassen.csv"
AGG_VOTERS_PER_WAHLBEZIRK_PATH = PROCESSED_DATA_PATH / "wahlbezirke_waehler.csv"
AGG_WIKIDATA_PATH = PROCESSED_DATA_PATH / "wikidata_agg.csv"
COMBINED_SEARCHDICT_PATH = PROCESSED_DATA_PATH / "combined_searchdict.csv"
INVERTED_INDEX_PATH = PROCESSED_DATA_PATH / "inverted_index.csv"
WIKIDATA_VIS_PATH = PROCESSED_DATA_PATH / "wikidata_vis.csv"
AUSWERTUNG_PATH = PROCESSED_DATA_PATH / "wahlbezirke_auswertung.csv"


# Start and End dates of the observation period
START = "2020-09-13"
ENDE = "2025-09-14"

