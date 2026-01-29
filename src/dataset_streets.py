from pathlib import Path
import osmnx as ox
import time
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.polygon import Polygon
from shapely.validation import make_valid
from src.utils import load_shapefile, save_json_to_path, validate_crs
import src.config as cfg
from loguru import logger


def repair_geometry(geom) -> Polygon | MultiPolygon:
    """
    Repairs and validates a given geometry to ensure it conforms to geometric standards or
    formats, particularly when it is found to be invalid. The function attempts to make the
    geometry valid and ensures the output is of acceptable geometric types.

    :param geom: The input geometry to be repaired. It must be a geometric object
        such as `Polygon`, `MultiPolygon`, or other valid geometry formats.
    :return: The repaired geometry. If the geometry is already valid, it returns
        the original geometry. If the given geometry is invalid, it attempts to
        repair it and return the corrected geometry as a `Polygon` or
        `MultiPolygon`. In cases where the repair fails or no valid polygons
        are found, it returns the original input geometry.
    """
    if geom.is_valid:
        return geom

    repaired = make_valid(geom)

    if not isinstance(repaired, (Polygon, MultiPolygon)):
        if hasattr(repaired, 'geoms'):
            polygons = [g for g in repaired.geoms if isinstance(g, (Polygon, MultiPolygon))]
            if polygons:
                if len(polygons) == 1:
                    return polygons[0]
                else:
                    return MultiPolygon(polygons)
        return geom
    return repaired



def get_streets_per_district(path: Path) -> dict[str, list[str]]:
    """
    Extracts street names for each district defined in a shapefile and returns
    them in a structured dictionary format. This function processes the shapefile
    to validate geometries, filters invalid entries, and queries OpenStreetMap
    (OSM) for street data within defined districts. The resultant data includes
    details such as district ID, district name, voting district ID, and associated
    street names for each district.

    This method handles invalid geometries by repairing them and skips
    unrepairable ones. It also logs progress and errors during the process for
    better traceability.

    :param path: Path to the shapefile containing district data.
    :type path: Path
    :return: A dictionary where the keys are district names and the values are
        lists of streets belonging to the respective districts.
    :rtype: dict[str, list[str]]
    """
    logger.info(f"Lade Stimmbezirke aus {path}")
    stimmbezirke = load_shapefile(path)
    stimmbezirke = validate_crs(stimmbezirke)

    # repair possibly invalid geometries
    invalid_geom = ~stimmbezirke.geometry.is_valid
    if invalid_geom.any():
        logger.warning(f"{invalid_geom.sum()} ungültige Geometrien gefunden. Starte Reparatur.")
        stimmbezirke.loc[invalid_geom, 'geometry'] = stimmbezirke.loc[invalid_geom, 'geometry'].apply(repair_geometry)

    streets_per_district = []

    logger.info(f"Starte OSM-Abfrage für {len(stimmbezirke)} Stimmbezirke.")

    for i, (idx, row) in enumerate(stimmbezirke.iterrows()):
        geometry = row.geometry
        stimmbezirk_id = row.get('Stimm-/ Wahlbezirk')
        stimmbezirk_name = row.get('Kommunalwahlbezirk Name')
        wahlbezirk_id = row.get('Kommunalwahlbezirk Nr.')
        current_count = i + 1
        # additional validation before processing
        if not isinstance(geometry, (Polygon, MultiPolygon)):
            logger.error(f"[{current_count}/{len(stimmbezirke)}] Stimmbezirk {stimmbezirk_id} hat ungültigen Geometrie-Typ: {type(geometry).__name__}")
            continue

        if not geometry.is_valid:
            logger.error(f"[{current_count}/{len(stimmbezirke)}] Stimmbezirk {stimmbezirk_id} ist ungültig. Überspringe.")
            continue

        try:
            logger.debug(f"[{current_count}/{len(stimmbezirke)}] Frage Straßen für Stimmbezirk {stimmbezirk_id} ({stimmbezirk_name}) ab.")
            streets = ox.graph_from_polygon(geometry,
                                            network_type='all',
                                            simplify=True,
                                            retain_all=False,
                                            truncate_by_edge=True)
            nodes_gdf, edges_gdf = ox.graph_to_gdfs(streets)
            street_names = set()

            if 'name' in edges_gdf.columns:
                names = edges_gdf['name'].dropna()
                for name in names:
                    if isinstance(name, str):
                        for part in name.split(','):
                            street_names.add(part.strip())

            if 'street_name' in edges_gdf.columns:
                names = edges_gdf['street_name'].dropna()
                for name in names:
                    if isinstance(name, str):
                        street_names.add(name.strip())

            street_names = sorted(list(street_names))

            district_entry = {
                'stimmbezirks_id': stimmbezirk_id,
                'stimmbezirks_name': stimmbezirk_name,
                'wahlbezirk_id': wahlbezirk_id,
                'straßen': street_names
            }
            streets_per_district.append(district_entry)
            time.sleep(cfg.DELAY)


        except Exception as e:
            logger.exception(f"[{current_count}/{len(stimmbezirke)}] Unerwarteter Fehler bei Stimmbezirk {stimmbezirk_id}: {e}")

    logger.success(f"Verarbeitung abgeschlossen. {len(streets_per_district)} Bezirke erfolgreich verarbeitet.")
    return streets_per_district

def main() -> None:
    logger.info("Starte Straßen-Download")
    ox.settings.use_cache = cfg.OSMNX_CACHING
    street_dict = get_streets_per_district(cfg.STIMMBEZIRK_SHAPEFILE_PATH)
    save_json_to_path(street_dict, cfg.STREET_PER_DISTRICT_PATH)
    logger.info(f"Ergebnis gespeichert unter {cfg.STREET_PER_DISTRICT_PATH}")

if __name__ == "__main__":
    main()

