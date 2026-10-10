import time

import geopandas as gpd
import requests
from loguru import logger
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from tqdm import tqdm

import src.config as cfg
import src.utils as utils


def get_district_for_poi(articles: list[dict]) -> list[dict]:
    """
    Determines the electoral district for a given list of geographical points of interest (POIs),
    represented as articles. It reads district boundaries from a shapefile, checks which
    district contains each POI, and updates the article data with the corresponding district
    information.

    :param articles: A list of dictionaries, each representing an article containing
                     geolocation data (longitude and latitude) and additional information.
    :type articles: list[dict]

    :return: A list of dictionaries with updated information. Articles where an electoral
             district match is found will include `stimmbezirk_id` (district ID) and
             `wahlkreis_id` (electoral district number) keys. Articles without a match
             remain unchanged.
    :rtype: list[dict]
    """
    shapefile_path = cfg.STIMMBEZIRK_SHAPEFILE_PATH
    if not shapefile_path.exists():
        logger.error(f"Shapefile nicht gefunden unter {shapefile_path}")
        return articles

    logger.info("Lade Stimmbezirke für räumliche Zuordnung der SPARQL-Daten...")
    stimmbezirke = gpd.read_file(shapefile_path)
    stimmbezirke = stimmbezirke.to_crs(cfg.CRS)

    for article in articles:
        point = Point(article["lon"], article["lat"])

        # Get the district in which the point lies
        match = stimmbezirke[stimmbezirke.contains(point)]

        if not match.empty:
            bezirk_data = match.iloc[0]
            stimm_id = bezirk_data.get("Stimm-/ Wahlbezirk")
            wahl_id = bezirk_data.get("Kommunalwahlbezirk Nr.")

            article["stimmbezirk_id"] = int(stimm_id) if stimm_id is not None else None
            article["wahlkreis_id"] = int(wahl_id) if wahl_id is not None else None
            logger.success(f"POI {article['label']} wurde erfolgreich einem Bezirk zugeordnet.")
        else:
            logger.warning(f"POI {article['label']} konnte keinem Bezirk zugeordnet werden.")

    return articles


def get_data_from_sparql() -> list[dict]:
    """
    Fetches and processes data from a SPARQL endpoint, returning a list of article details
    with geolocation, labels, and metadata. The function sends a GET request to the SPARQL
    endpoint, parses the JSON response, extracts individual fields from the result, and
    formats them into dictionaries stored within the returned list.

    :param None: This function does not accept any arguments.
    :raises requests.RequestException: If the GET request to the SPARQL endpoint fails
        due to network, timeout, or other request-level errors.
    :raises ValueError: If the response cannot be decoded or does not match the expected
        structure.
    :return: A list of dictionaries, each containing the following keys:
        - `title` (str): The title of the article.
        - `wikidata_id` (str): The Wikidata identifier.
        - `label` (str): The human-readable label of the item.
        - `lon` (float): The longitude coordinate.
        - `lat` (float): The latitude coordinate.
        - `url` (str): The URL of the article.
        - `stimmbezirk_id` (None): Placeholder for "stimmbezirk_id", currently uninitialized.
        - `wahlkreis_id` (None): Placeholder for "wahlkreis_id", currently uninitialized.
    :rtype: list[dict]
    """
    headers = {"User-Agent": cfg.USER_AGENT, "Accept": "application/json; charset=utf-8"}
    response = requests.get(
        cfg.WIKIDATA_ENDPOINT, params={"query": cfg.QUERY, "format": "json"}, headers=headers
    )
    response.encoding = "utf-8"

    articles = []
    if response.status_code == 200:
        data = response.json()
        for result in data["results"]["bindings"]:
            coord_str = result["coord"]["value"]
            coords = coord_str.replace("Point(", "").replace(")", "").split()

            articles.append(
                {
                    "label": result["itemLabel"]["value"],
                    "lon": float(coords[0]),
                    "lat": float(coords[1]),
                    "url": result["article"]["value"],
                    "stimmbezirk_id": None,
                    "wahlkreis_id": None,
                }
            )
    logger.info(f"{len(articles)} Artikel über SPARQL gefunden.")
    articles = get_district_for_poi(articles)
    return articles


def get_wikidata_for_bbox(bbox: tuple) -> list[dict]:
    """
    Fetches Wikipedia geolocation data for a specified bounding box (bbox).

    This function retrieves geolocation articles from the Wikipedia API's
    GeoSearch feature within the specified bounding box coordinates.
    If the API request fails or no data exists in the specified bbox,
    an empty list will be returned.

    :param bbox: A tuple containing the bounding box coordinates in the format
                 (minx, miny, maxx, maxy) where:
                 - minx: Minimum longitude
                 - miny: Minimum latitude
                 - maxx: Maximum longitude
                 - maxy: Maximum latitude
    :return: A list of dictionaries containing the retrieved geolocation
             data from the Wikipedia API. Each dictionary includes the keys:
              - title: Title of the article
              - pageid: Page ID of the article
              - lat: Latitude of the location
              - lon: Longitude of the location
              - dist: Distance to the point from the center of the bbox
              - stimmbezirk_id: Additional field initially set to None
              - wahlkreis_id: Additional field initially set to None
    """
    minx, miny, maxx, maxy = bbox

    endpoint = cfg.WIKIPEDIA_ENDPOINT
    geosearch_limit = cfg.GEOSEARCH_LIMIT
    user_agent = cfg.USER_AGENT

    gsbbox = f"{maxy}|{minx}|{miny}|{maxx}"

    params = {
        "action": "query",
        "list": "geosearch",
        "gsbbox": gsbbox,
        "gslimit": geosearch_limit,
        "format": "json",
    }

    try:
        response = requests.get(endpoint, params=params, headers={"User-Agent": user_agent})
        response.raise_for_status()
        data = response.json()

        if "query" in data and "geosearch" in data["query"]:
            articles = []
            for article in data["query"]["geosearch"]:
                articles.append(
                    {
                        "label": article["title"],
                        "pageid": article["pageid"],
                        "lat": article["lat"],
                        "lon": article["lon"],
                        "dist": article.get("dist", 0),
                        "stimmbezirk_id": None,
                        "wahlkreis_id": None,
                    }
                )
            return articles
        return []

    except Exception as e:
        logger.error(f"Fehler bei API-Abfrage für bbox {bbox}: {e}")
        return []


def get_articles_for_shapefile() -> list[dict]:
    """
    Retrieves articles for each district in a shapefile and returns a list of dictionaries with updated information.
    Articles where an electoral district match is found will include `stimmbezirk_id` (district ID) and
    `wahlkreis_id` (electoral district number) keys. Articles without a match remain unchanged.

    :rtype: list[dict]
    """
    shapefile_path = cfg.STIMMBEZIRK_SHAPEFILE_PATH
    logger.info(f"Lade Stimmbezirke für Wikipedia-Suche aus {shapefile_path}")
    shapefile = utils.load_shapefile(shapefile_path)
    crs = cfg.CRS
    delay = cfg.DELAY
    shapefile = shapefile.to_crs(crs)

    articles_list: list[dict] = []

    logger.info(f"Starte BBox-Abfrage für {len(shapefile)} Stimmbezirke.")
    for _id, stimmbezirk in tqdm(shapefile.iterrows()):
        # Calculate Bounding Box
        geom: BaseGeometry = stimmbezirk.geometry
        bbox: tuple[float, float, float, float] = geom.bounds  # (minx, miny, maxx, maxy)

        # Get Wahlkreis-Name, if available
        wahlbezirk_nr = stimmbezirk.get("Kommunalwahlbezirk Nr.", None)
        stimmbezirk_id = stimmbezirk.get("Stimm-/ Wahlbezirk", None)

        if stimmbezirk_id is not None and hasattr(stimmbezirk_id, "item"):
            stimmbezirk_id = stimmbezirk_id.item()
        if wahlbezirk_nr is not None and hasattr(wahlbezirk_nr, "item"):
            wahlbezirk_nr = wahlbezirk_nr.item()

        # API-call with Bounding Box
        try:
            articles = get_wikidata_for_bbox(bbox)

            # Filter points within the polygon
            for article in articles:
                point = Point(article["lon"], article["lat"])
                if utils.point_in_polygon(point, stimmbezirk.geometry):
                    article["stimmbezirk_id"] = stimmbezirk_id
                    article["wahlkreis_id"] = wahlbezirk_nr
                    articles_list.append(article)

        except Exception as e:
            logger.exception(f"Unerwarteter Fehler bei Stimmbezirk {stimmbezirk_id}: {e}")

        time.sleep(delay)
        logger.success(f"Verarbeitung abgeschlossen. {len(articles_list)} Artikel gefunden.")
    return articles_list


def main() -> None:
    """
    Main function for orchestrating the Wikidata/Wikipedia data acquisition process.

    This function performs the following steps:
    1. Logs the start of the data acquisition process.
    2. Executes a SPARQL query to retrieve data and appends the results to a collection.
    3. Performs a spatial search using a shapefile and appends the results to the same collection.
    4. Saves the collected data as a JSON file at a specified location.
    5. Logs the success of the data-saving operation.

    :return: None
    """
    logger.info("Starte Wikidata/Wikipedia Datenerfassung")

    all_articles = []

    logger.info("Führe SPARQL-Abfrage aus...")
    sparql_articles = get_data_from_sparql()
    all_articles.extend(sparql_articles)

    logger.info("Starte räumliche Suche über Shapefile...")
    shapefile_articles = get_articles_for_shapefile()
    all_articles.extend(shapefile_articles)

    utils.save_json_to_path(all_articles, cfg.WIKI_DICT)
    logger.success(f"Ergebnisse gespeichert unter {cfg.WIKI_DICT}")


if __name__ == "__main__":
    main()
