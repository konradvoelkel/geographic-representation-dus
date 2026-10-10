from loguru import logger

from src.analyse import main as analyse_main
from src.combine_searchdicts import main as combine_main
from src.dataset_oparl import main as oparl_main
from src.dataset_opendata import main as opendata_main
from src.dataset_streets import main as streets_main
from src.dataset_wikidata import main as wikidata_main
from src.prep_papers import main as papers_main
from src.prep_streets import main as streets_agg_main
from src.prep_voters import main as voters_main
from src.prep_wiki import main as wiki_main
from src.reverse_index import main as index_main
from src.utils import setup_data_directories


def main() -> None:
    logger.info("Starte alle Prozesse")
    setup_data_directories()
    oparl_main()
    opendata_main()
    streets_main()
    wikidata_main()
    papers_main()
    voters_main()
    wiki_main()
    streets_agg_main()
    combine_main()
    index_main()
    analyse_main()
    logger.success("Alle Prozesse abgeschlossen")


if __name__ == "__main__":
    main()