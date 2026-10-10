"""
This module provides functionality to process and aggregate voter data by districts.

The module reads data from CSV files, aggregates election results for each district,
and outputs the results to a CSV file. It assists in organizing and cleaning data
for further analysis.

Functions:
    group_data_by_district: Aggregates election results by district based on input data.
    main: Coordinates the aggregation and saves the results to a CSV file.
"""

from pathlib import Path

import pandas as pd
from loguru import logger

import src.config as cfg


def group_data_by_district(path: Path) -> pd.DataFrame | None:
    try:
        logger.info(f"Lade Wahlergebnisdaten von {path}")
        transform_cols = [
            "Wahlberechtigte_insgesamt",
            "Waehler",
            "CDU_Stimmen",
            "GRUENE_Stimmen",
            "SPD_Stimmen",
            "FDP_Stimmen",
            "Die_Linke_Stimmen",
            "AfD_Stimmen",
        ]
        df_voters = pd.read_csv(path, sep=";", engine="python", encoding="latin-1")
        for col in transform_cols:
            df_voters[col] = pd.to_numeric(df_voters[col], errors="coerce").fillna(0).astype(int)
        df_voters = df_voters.rename(columns={"Kommunalwahlbezirk": "wahlkreis_id"})
        df_voters = df_voters.groupby("wahlkreis_id", as_index=False).agg(
            {
                "Wahlberechtigte_insgesamt": "sum",
                "Waehler": "sum",
                "CDU_Stimmen": "sum",
                "GRUENE_Stimmen": "sum",
                "SPD_Stimmen": "sum",
                "FDP_Stimmen": "sum",
                "Die_Linke_Stimmen": "sum",
                "AfD_Stimmen": "sum",
            }
        )
        df_voters["wahlbeteiligung"] = df_voters["Waehler"] / df_voters["Wahlberechtigte_insgesamt"]
        df_voters["CDU_anteil"] = df_voters["CDU_Stimmen"] / df_voters["Waehler"]
        df_voters["GRUENE_anteil"] = df_voters["GRUENE_Stimmen"] / df_voters["Waehler"]
        df_voters["SPD_anteil"] = df_voters["SPD_Stimmen"] / df_voters["Waehler"]
        df_voters["FDP_anteil"] = df_voters["FDP_Stimmen"] / df_voters["Waehler"]
        df_voters["Die_Linke_anteil"] = df_voters["Die_Linke_Stimmen"] / df_voters["Waehler"]
        df_voters["AfD_anteil"] = df_voters["AfD_Stimmen"] / df_voters["Waehler"]
        logger.success("Aggregation der Wahlergebnisse erfolgreich abgeschlossen.")
        return df_voters

    except Exception as e:
        logger.error(f"Fehler beim Verarbeiten der Wahlergebnisse: {e}")
        return None


def main() -> None:
    data = group_data_by_district(cfg.WAHLERGEBNIS_PATH)
    if data is not None:
        data.to_csv(cfg.AGG_VOTERS_PER_WAHLBEZIRK_PATH, index=False)
        logger.success(f"Daten gespeichert unter {cfg.AGG_VOTERS_PER_WAHLBEZIRK_PATH}")


if __name__ == "__main__":
    main()
