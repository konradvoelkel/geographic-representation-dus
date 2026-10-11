from loguru import logger

import src.config as cfg
from georep.http import Transport
from georep.io import write_bytes, write_json
from src.utils import http_session


def get_wahlergebnis(session: Transport | None = None) -> None:
    """Lädt die Wahlergebnis-CSV. Netz- und HTTP-Fehler laufen durch; bis 2026-10-11 wurden sie
    protokolliert und verschluckt, und der Lauf ging ohne Datei weiter."""
    logger.info("Lade Wahlergebnisse von OpenData-Portal herunter")
    response = (session or http_session()).get(cfg.OPENDATA_ENDPOINT_WAHLERGEBNIS)
    response.raise_for_status()
    # Bytes wie geliefert: response.text rät das Encoding, und als latin-1 neu kodiert
    # brachen die Umlaute, wenn die Vermutung falsch lag.
    write_bytes(cfg.WAHLERGEBNIS_PATH, response.content)
    logger.success(f"Wahlergebnisse gespeichert: {len(response.content)} Bytes")


def get_stimmbezirk_shapefile(session: Transport | None = None) -> None:
    logger.info("Lade Stimmbezirks-Shapefile herunter")
    response = (session or http_session()).get(cfg.OPENDATA_ENDPOINT_STIMMBEZIRK)
    response.raise_for_status()
    data = response.json()
    write_json(cfg.STIMMBEZIRK_SHAPEFILE_PATH, data, indent=4)
    logger.success(f"Stimmbezirke gespeichert: {len(data.get('features', []))} Features")


def main() -> None:
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
