import json

import requests
from loguru import logger

import src.config as cfg


def get_wahlergebnis() -> None:
    try:
        logger.info("Lade Wahlergebnisse von OpenData-Portal herunter")
        response = requests.get(cfg.OPENDATA_ENDPOINT_WAHLERGEBNIS)
        response.raise_for_status()

        with open(cfg.WAHLERGEBNIS_PATH, "w", encoding="latin-1") as f:
            f.write(response.text)
        logger.success("Wahlergebnisse erfolgreich gespeichert.")
    except Exception as e:
        logger.error(f"Fehler beim Abruf der Wahlergebnisse: {e}")


def get_stimmbezirk_shapefile() -> None:
    try:
        logger.info("Lade Stimmbezirks-Shapefile herunter")
        response = requests.get(cfg.OPENDATA_ENDPOINT_STIMMBEZIRK)
        response.raise_for_status()
        data = response.json()

        with open(cfg.STIMMBEZIRK_SHAPEFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.success("Stimmbezirks-Shapefile erfolgreich gespeichert.")
    except Exception as e:
        logger.error(f"Fehler beim Abruf des Shapefiles: {e}")


def main():
    if not cfg.WAHLERGEBNIS_PATH.exists():
        get_wahlergebnis()
    else:
        logger.info("Wahlergebnis bereits vorhanden.")

    if not cfg.STIMMBEZIRK_SHAPEFILE_PATH.exists():
        get_stimmbezirk_shapefile()
    else:
        logger.info("Stimmbezirks-Shapefile bereits vorhanden.")


if __name__ == "__main__":
    main()
