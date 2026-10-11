from loguru import logger

import src.config as cfg
from georep.http import Transport
from georep.io import write_bytes, write_json
from src.utils import http_session


def get_wahlergebnis(session: Transport | None = None) -> None:
    try:
        logger.info("Lade Wahlergebnisse von OpenData-Portal herunter")
        response = (session or http_session()).get(cfg.OPENDATA_ENDPOINT_WAHLERGEBNIS)
        response.raise_for_status()

        # Bytes wie geliefert: bis 2026-10-11 wurde response.text (geratenes Encoding) als
        # latin-1 geschrieben; bei falscher Vermutung brachen die Umlaute.
        write_bytes(cfg.WAHLERGEBNIS_PATH, response.content)
        logger.success("Wahlergebnisse erfolgreich gespeichert.")
    except Exception as e:
        logger.error(f"Fehler beim Abruf der Wahlergebnisse: {e}")


def get_stimmbezirk_shapefile(session: Transport | None = None) -> None:
    try:
        logger.info("Lade Stimmbezirks-Shapefile herunter")
        response = (session or http_session()).get(cfg.OPENDATA_ENDPOINT_STIMMBEZIRK)
        response.raise_for_status()
        data = response.json()

        write_json(cfg.STIMMBEZIRK_SHAPEFILE_PATH, data, indent=4)
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
