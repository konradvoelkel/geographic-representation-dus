"""
This module provides functionality to process and aggregate street data by districts.

The module reads data from JSON files, aggregates street names for each district,
and outputs the results to a CSV file. It assists in organizing and cleaning data
for further analysis.

Functions:
    group_streets_by_district: Aggregates street names by district based on input data.
    main: Coordinates the aggregation and saves the results to a CSV file.
"""

from pathlib import Path

import pandas as pd
from loguru import logger

import src.config as cfg


def group_streets_by_district(path: Path) -> pd.DataFrame:
    logger.info(f"Aggregation für Straßen pro Wahlbezirk gestartet. Datei: {path}")
    df_strassen = pd.read_json(path)
    df_strassen = df_strassen.explode('straßen')
    df_strassen.drop(columns=['stimmbezirks_id'], inplace=True)
    df_strassen['wahlbezirk_id'] = df_strassen['wahlbezirk_id'].astype(int)

    df_strassen = df_strassen.groupby('wahlbezirk_id', as_index=False).agg({
                                                            'straßen': lambda x: '; '.join(sorted(set(x)))})
    df_strassen = df_strassen.rename(columns={'straßen': 'suchbegriffe',
                                              'wahlbezirk_id': 'wahlkreis_id'})
    return df_strassen


def main() -> None:
    data = group_streets_by_district(cfg.STREET_PER_DISTRICT_PATH)
    data.to_csv(cfg.AGG_STREETS_PER_WAHLBEZIRK_PATH, index=False)
    logger.success(f"Daten gespeichert unter {cfg.AGG_STREETS_PER_WAHLBEZIRK_PATH}")



if __name__ == "__main__":
    main()