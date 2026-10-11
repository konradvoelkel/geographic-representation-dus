import json
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests
from loguru import logger
from tqdm import tqdm

import src.config as cfg
from georep.io import write_bytes, write_json


@dataclass
class Paper:
    # Fields from OParl-Metadata scheme
    id: str = field()
    name: str = field()
    reference: str = field()
    date: str = field()
    paperType: str = field()
    mainFile: str = field()
    download_url: str = field()
    # Additional fields for analysis
    paper_text: str = field(default="")


class PaperList(list[Paper]):
    def add_paper(self, paper: Paper) -> None:
        self.append(paper)

    def save_as_json(self, path: Path) -> None:
        write_json(Path(path), [asdict(paper) for paper in self], indent=2)

    def __str__(self):
        return "\n".join(str(paper) for paper in self)


def _as_paper_iter(papers_like: Any) -> Iterable[Paper]:
    """
    Converts the input data into an iterable of `Paper` objects. This function supports
    various input types and ensures uniformity by transforming all compatible input
    structures into a list of `Paper` objects.

    :param papers_like: Input data that can be of type `None`, `Paper`, `dict`, `list`,
        `tuple`, or `PaperList`. If the input is `None`, an empty list is returned. If
        the input is a single `Paper` or a dict representation of a paper, it is
        wrapped in a list. If the input is a collection, each item is processed and
        converted to a `Paper` object if applicable.
    :type papers_like: Any

    :return: An iterable containing `Paper` objects derived from the input data.
    :rtype: Iterable[Paper]
    """
    if papers_like is None:
        return []
    if isinstance(papers_like, Paper):
        return [papers_like]
    if isinstance(papers_like, dict):
        return [_paper_from_dict(papers_like)]
    if isinstance(papers_like, (list, tuple, PaperList)):
        out: list[Paper] = []
        for item in papers_like:
            if isinstance(item, Paper):
                out.append(item)
            elif isinstance(item, dict):
                out.append(_paper_from_dict(item))
        return out
    return []


def _paper_from_dict(d: dict[str, Any]) -> Paper:
    """
    Converts a JSON dictionary into a Paper object. Accepts both 'download_url' and the OParl-standard 'downloadUrl'.
    """
    return Paper(
        id=d.get("id"),
        name=d.get("name"),
        reference=d.get("reference"),
        date=d.get("date"),
        paperType=d.get("paperType"),
        mainFile=d.get("mainFile"),
        download_url=d.get("download_url"),
        paper_text=d.get("paper_text", ""),
    )


def _check_for_existing_papers() -> tuple[set[str], list[dict]]:
    """
    Checks for existing papers by reading from a JSON file. The JSON file is expected to contain
    a list of paper objects. Each paper object must be a dictionary with an 'id' key to be
    considered valid. If the file does not exist or if the contents are not valid, an empty
    set and list will be returned.

    :returns:
        A tuple where the first element is a set of known paper IDs (extracted from the 'id'
        key of valid paper objects), and the second element is a list of paper objects
        (dictionaries) loaded from the JSON file.
    :rtype: tuple[set[str], list[dict]]
    """
    papers_json_path = Path(cfg.PAPER_OBJECT_LISTE)

    if not papers_json_path.exists():
        return set(), []

    try:
        with open(papers_json_path, encoding="utf-8") as f:
            known_paper = json.load(f)
        if not isinstance(known_paper, list):
            return set(), []
        known_ids = {p.get("id") for p in known_paper if isinstance(p, dict) and p.get("id")}
        return known_ids, known_paper
    except Exception:
        return set(), []


def download_paper_metadata(endpoint: str) -> PaperList:
    """
    Downloads and processes metadata for academic papers from the specified API endpoint. The function
    utilizes pagination to handle large datasets and resumes downloads by skipping known paper IDs
    to avoid redundant requests. The metadata is filtered based on a configured date range and then
    saved as a JSON file. Additionally, all URLs accessed during the process are logged into a separate file.

    :param endpoint: The API endpoint to start retrieving paper metadata from.
    :type endpoint: str
    :return: A PaperList object containing all the downloaded and processed papers.
    :rtype: PaperList
    :raises JSONDecodeError: Raised if the response from the API is not valid JSON.
    :raises KeyError: Raised if expected keys are missing in the API response.
    :raises Exception: Encapsulates other unexpected errors encountered during processing.
    """
    pages_progress_bar = tqdm(desc="Verarbeitete Seiten: ", unit=" Seite(n)")
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=5)
    session.mount("http://", adapter)

    known_ids, existing_papers_raw = _check_for_existing_papers()
    if known_ids:
        logger.info(
            f"Resume aktiv: {len(known_ids)} Paper-IDs lokal bekannt -> überspringe bekannte Einträge."
        )
    else:
        logger.info("Kein lokaler Stand gefunden -> vollständiger Download.")

    papers = PaperList()
    url_liste = []

    try:
        while True:
            response = session.get(endpoint)
            response.raise_for_status()
            response = response.json()

            for p in response["data"]:
                paper_id = p.get("id")
                if paper_id in known_ids:
                    continue

                mainfile_id = None
                download_url = None
                paper_date = p.get("date")

                if cfg.START <= paper_date <= cfg.ENDE:
                    if p.get("mainFile") is not None:
                        mainfile = p.get("mainFile")
                        mainfile_id = mainfile.get("id", None)
                        download_url = mainfile.get("downloadUrl", None)
                    elif p.get("auxiliaryFile") is not None and len(p.get("auxiliaryFile")) > 0:
                        mainfile = p.get("auxiliaryFile")[0]
                        mainfile_id = mainfile.get("id", None)
                        download_url = mainfile.get("downloadUrl", None)

                    paper_dc = Paper(
                        p.get("id", None),
                        p.get("name", None),
                        p.get("reference", None),
                        p.get("date", None),
                        p.get("paperType", None),
                        mainfile_id,
                        download_url,
                    )

                    papers.add_paper(paper_dc)

                    if paper_id:
                        known_ids.add(paper_id)
                else:
                    continue

            papers.save_as_json(cfg.PAPER_OBJECT_LISTE)

            combined = [asdict(p) for p in papers] + existing_papers_raw
            write_json(cfg.PAPER_OBJECT_LISTE, combined, indent=2)

            url_liste.append(endpoint)
            write_json(cfg.PAPER_URL_LISTE, url_liste, indent=4)

            if "next" not in response["links"]:
                logger.info("Letzte Seite erreicht.")
                break

            endpoint = response.get("links", {}).get("next")

            time.sleep(cfg.DELAY)
            pages_progress_bar.update(1)
    except Exception as e:
        logger.exception(f"Unerwarteter Fehler beim Download der Metadaten: {e}")

    finally:
        combined = [asdict(p) for p in papers] + existing_papers_raw
        write_json(cfg.PAPER_OBJECT_LISTE, combined, indent=2)

        pages_progress_bar.close()
        session.close()
        # Phase 1: ein return im finally verschluckt jede Exception des try-Blocks (B012).
        # Fällt mit der neuen Fehlerbehandlung des Downloads; bis dahin bewusst so belassen.
        return papers  # noqa: B012


def download_paper_pdf(paperList: PaperList) -> None:
    """
    Downloads PDF files for papers listed in the provided PaperList object.

    This function iterates over the list of papers and attempts to download their
    corresponding PDFs from the specified `download_url`. If a paper has an empty
    or invalid `download_url`, the paper is skipped. Files that have already
    been downloaded, based on their presence in the download directory, are also skipped.
    A progress bar tracks the number of successfully downloaded files.

    In the event of download errors, the error count is logged and exceptions
    are caught and reported without terminating the process. The function ensures
    that resources such as sessions and progress bars are properly cleaned up
    upon completion or error.

    :param paperList: List of papers for which PDF downloads should be attempted.
    :type paperList: PaperList
    :return: None
    """
    progress_bar = tqdm(desc="Heruntergeladene Dateien: ", unit="Datei(en)")
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=5)
    session.mount("http://", adapter)
    download_err_counter = 0
    try:
        for paper in _as_paper_iter(paperList):
            url = paper.download_url
            if not url:
                logger.warning(
                    f"Überspringe Paper ohne download_url (id={paper.id}, mainFile={paper.mainFile})"
                )
                continue
            if url.split("/")[-1] in [f.name for f in Path(cfg.PDF_DUMP_PATH).iterdir()]:
                continue

            response = session.get(url)
            response.raise_for_status()

            write_bytes(Path(cfg.PDF_DUMP_PATH) / url.split("/")[-1], response.content)

            progress_bar.update(1)
    except Exception as e:
        download_err_counter += 1
        logger.error(f"Fehler beim Herunterladen von {url}: {e}")
    finally:
        logger.success(f"Anzahl Fehler beim Herunterladen: {download_err_counter}")
        progress_bar.close()
        session.close()


def main() -> None:
    # setup_data_directories()
    paper_list = download_paper_metadata(cfg.OPARL_ENDPOINT)
    # paper_list = load_json_from_path(cfg.PAPER_OBJECT_LISTE)
    download_paper_pdf(paper_list)


if __name__ == "__main__":
    main()
