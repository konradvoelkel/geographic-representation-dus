"""
This module provides functionality to process and aggregate Wikipedia data by districts.

The module reads data from JSON files, cleans and aggregates POI information for each district,
and outputs the results to a CSV file. It assists in organizing and cleaning data
for further analysis.

Functions:
    clean_wikidata: Cleans and prepares Wikipedia data for aggregation.
    group_data_by_district: Aggregates POI information by district based on input data.
    main: Coordinates the cleaning, aggregation, and saves the results to a CSV file.
"""
from pathlib import Path

import pandas as pd
from loguru import logger

import src.config as cfg


def clean_wikidata(path: Path) -> pd.DataFrame:
    logger.info(f"Wikipedia-Daten werden aufbereitet: {path}")
    df_wiki = pd.read_json(path)
    df_wiki = df_wiki.drop(columns='stimmbezirk_id')
    df_wiki = df_wiki.drop_duplicates(subset=['label']).dropna(subset=['wahlkreis_id'])
    df_wiki['label'] = df_wiki['label'].str.replace(',', '', regex=False)
    df_wiki['wahlkreis_id'] = df_wiki['wahlkreis_id'].astype(int)
    df_wiki = df_wiki[~df_wiki['label'].isin(cfg.WIKI_EXCLUDE_LIST)]
    df_wiki = df_wiki[['label', 'wahlkreis_id', 'lon', 'lat']]
    return df_wiki

def group_data_by_district(df: pd.DataFrame) -> pd.DataFrame:
    df = df.groupby('wahlkreis_id', as_index=False).agg({
                                         'label': lambda x: '; '.join(sorted(set(x)))})
    df = df.rename(columns={'label': 'suchbegriffe'})
    return df

def main() -> None:
    data = clean_wikidata(cfg.WIKI_DICT)
    data.to_csv(cfg.WIKIDATA_VIS_PATH, index=False)
    data = group_data_by_district(data)
    data.to_csv(cfg.AGG_WIKIDATA_PATH, index=False)
    logger.success(f"Datei gespeichert unter  {cfg.AGG_WIKIDATA_PATH}")


if __name__ == "__main__":
    main()