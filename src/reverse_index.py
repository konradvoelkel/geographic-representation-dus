"""
This script creates an inverted index for a given set of search terms and paper texts.
The index is used to efficiently find papers that contain specific search terms.

Functions:
    - load_data: Loads search terms and paper texts from CSV and JSON files.
    - index_documents: Creates an inverted index based on the loaded data.
    - main: Orchestrates the loading, indexing, and saving of the inverted index.
"""
import pandas as pd
from flashtext import KeywordProcessor
from loguru import logger

import src.config as cfg


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    logger.info("Lade combined_searchdict und Paper-Texte...")
    # load searchdict
    df_search = pd.read_csv(cfg.COMBINED_SEARCHDICT_PATH, sep=';')

    # load papers
    df_paper = pd.read_json(cfg.PAPER_WITH_TEXT_PATH)

    return df_search, df_paper


def index_documents() -> None:
    df_search, df_paper = load_data()
    such_series = df_search['suchbegriffe'].str.lower().str.split(r'\s*,\s*').apply(lambda x: [s for s in x if s])

    # Step 1: Preparing KeywordProcessors
    keyword_processor = KeywordProcessor(case_sensitive=False)
    alle_begriffe = set(term for sublist in such_series for term in sublist)
    keyword_processor.add_keywords_from_list(list(alle_begriffe))

    # Step 2: Searching and Creating Inverted Index
    logger.info(f"Erstelle Invertierten Index. Suche nach {len(alle_begriffe)} Begriffen in {len(df_paper)} Dokumenten.")
    index = {b: [] for b in alle_begriffe}
    for dok in df_paper.itertuples():
        gefundene_begriffe = keyword_processor.extract_keywords(dok.paper_text)
        for b in set(gefundene_begriffe):
            index[b].append(dok.id)

    # Step 3: Creating DataFrame for Index
    logger.info(f"Konvertiere Index mit {len(index)} Begriffen in DataFrame...")
    rows = []
    for term, ids in index.items():
        unique_ids = sorted(list(set(str(i) for i in ids if i is not None)))
        rows.append({
            'suchbegriffe': term,
            'paper_ids': ';'.join(unique_ids),
            'anzahl_treffer': len(unique_ids)
        })

    df_index = pd.DataFrame(rows)

    # Step 4: Saving DataFrame
    if df_index.empty:
        logger.warning("Der Index ist leer! Es wurden keine Treffer gefunden.")
    else:
        df_index.to_csv(cfg.INVERTED_INDEX_PATH, index=False)
        logger.success(f"Invertierter Index als CSV gespeichert unter: {cfg.INVERTED_INDEX_PATH}")





def main() -> None:
    try:
        index_documents()
    except Exception as e:
        logger.exception(f"Kritischer Fehler beim Erstellen des Reverse-Index: {e}")


if __name__ == "__main__":
    main()