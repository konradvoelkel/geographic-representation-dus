"""
This script combines search terms from two different data sources and creates a unified dataset.
The resulting dataset includes enhanced search terms by expanding certain patterns (e.g., replacing
“straße” with “str.”) and is saved as a CSV file.

Functions:
    - main: The main script function orchestrating the loading, merging, processing, and saving
      of datasets.
"""

import pandas as pd
from loguru import logger

import src.config as cfg
from georep.io import atomic_path


def main() -> None:
    logger.info("Starte Kombination von Suchbegriffen")
    df_wiki = pd.read_csv(cfg.AGG_WIKIDATA_PATH)
    df_streets = pd.read_csv(cfg.AGG_STREETS_PER_WAHLBEZIRK_PATH)
    df_combined = pd.merge(df_wiki, df_streets, on="wahlkreis_id", how="inner")
    df_combined["suchbegriffe"] = (
        df_combined["suchbegriffe_x"].fillna("") + "; " + df_combined["suchbegriffe_y"].fillna("")
    )

    def expand_street_names(terms_str):
        terms = set(s.strip().lower() for s in str(terms_str).split(";") if s.strip())
        additional_terms = set()
        for term in terms:
            if "straße" in term.lower():
                # replaces "straße" by "str."
                new_term = term.replace("straße", "str.").replace("Straße", "str.")
                additional_terms.add(new_term)

        return ", ".join(sorted(terms | additional_terms))

    df_combined["suchbegriffe"] = df_combined["suchbegriffe"].apply(expand_street_names)

    df_combined = df_combined.drop(columns=["suchbegriffe_x", "suchbegriffe_y"])
    with atomic_path(cfg.COMBINED_SEARCHDICT_PATH) as tmp:
        df_combined.to_csv(tmp, index=False, sep=";")
    logger.success(f"Suchbegriffe kombiniert. Gespeichert unter: {cfg.COMBINED_SEARCHDICT_PATH}")


if __name__ == "__main__":
    main()
