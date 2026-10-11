import json
import time
from collections.abc import Iterable
from contextlib import ExitStack
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests
from loguru import logger
from tqdm import tqdm

import src.config as cfg
from georep.http import Transport
from georep.io import write_bytes, write_json
from src.utils import http_session


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


@dataclass
class DownloadReport:
    """Was ein Download-Lauf getan hat; ein Lauf nennt die Zahlen, auf die er gewirkt hat."""

    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.downloaded} geladen, {self.skipped} übersprungen, {self.failed} fehlgeschlagen"
        )


def download_paper_metadata(endpoint: str, session: Transport | None = None) -> PaperList:
    """Lädt die Paper-Metadaten seitenweise über die OParl-Schnittstelle.

    Bekannte IDs aus einem früheren Lauf werden übersprungen (Resume). Nach jeder Seite steht
    der Zwischenstand atomar auf der Platte. Ein Netz- oder Formatfehler bricht den Lauf ab,
    nachdem der Zwischenstand gespeichert ist; die nächste Ausführung setzt dort wieder auf.
    Bis 2026-10-11 verschluckte ein ``return`` im ``finally`` jeden Fehler und lieferte eine
    stille Teilliste.
    """
    pages_progress_bar = tqdm(desc="Verarbeitete Seiten: ", unit=" Seite(n)")

    known_ids, existing_papers_raw = _check_for_existing_papers()
    if known_ids:
        logger.info(
            f"Resume aktiv: {len(known_ids)} Paper-IDs lokal bekannt -> überspringe bekannte Einträge."
        )
    else:
        logger.info("Kein lokaler Stand gefunden -> vollständiger Download.")

    papers = PaperList()
    url_liste: list[str] = []

    with ExitStack() as stack:
        http: Transport = session if session is not None else stack.enter_context(http_session())
        try:
            while True:
                response = http.get(endpoint)
                response.raise_for_status()
                page = response.json()

                for p in page["data"]:
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

                        papers.add_paper(
                            Paper(
                                p.get("id", None),
                                p.get("name", None),
                                p.get("reference", None),
                                p.get("date", None),
                                p.get("paperType", None),
                                mainfile_id,
                                download_url,
                            )
                        )
                        if paper_id:
                            known_ids.add(paper_id)

                write_json(
                    cfg.PAPER_OBJECT_LISTE,
                    [asdict(p) for p in papers] + existing_papers_raw,
                    indent=2,
                )
                url_liste.append(endpoint)
                write_json(cfg.PAPER_URL_LISTE, url_liste, indent=4)

                if "next" not in page["links"]:
                    logger.info("Letzte Seite erreicht.")
                    break

                endpoint = page["links"]["next"]
                time.sleep(cfg.DELAY)
                pages_progress_bar.update(1)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error(f"Abbruch beim Download der Metadaten nach {len(url_liste)} Seiten: {e}")
            raise
        finally:
            write_json(
                cfg.PAPER_OBJECT_LISTE, [asdict(p) for p in papers] + existing_papers_raw, indent=2
            )
            pages_progress_bar.close()
    return papers


def download_paper_pdf(
    paper_list: Any, session: Transport | None = None, target_dir: Path | None = None
) -> DownloadReport:
    """Lädt die PDFs der Paper nach ``target_dir`` (Standard: ``cfg.PDF_DUMP_PATH``).

    Vorhandene Dateien werden übersprungen, Paper ohne URL ebenso. Ein Fehler betrifft nur
    seine Datei: er wird gezählt, protokolliert, und der Lauf geht weiter. Bis 2026-10-11
    beendete der erste Fehler alle weiteren Downloads.
    """
    target = Path(target_dir) if target_dir is not None else Path(cfg.PDF_DUMP_PATH)
    target.mkdir(parents=True, exist_ok=True)
    existing = {f.name for f in target.iterdir()}
    report = DownloadReport()
    progress_bar = tqdm(desc="Heruntergeladene Dateien: ", unit="Datei(en)")

    with ExitStack() as stack:
        http: Transport = session if session is not None else stack.enter_context(http_session())
        try:
            for paper in _as_paper_iter(paper_list):
                url = paper.download_url
                if not url:
                    logger.warning(
                        f"Überspringe Paper ohne download_url (id={paper.id}, mainFile={paper.mainFile})"
                    )
                    report.skipped += 1
                    continue
                name = url.split("/")[-1]
                if name in existing:
                    report.skipped += 1
                    continue
                try:
                    response = http.get(url)
                    response.raise_for_status()
                    write_bytes(target / name, response.content)
                except (requests.RequestException, OSError) as e:
                    report.failed += 1
                    report.errors.append((url, str(e)))
                    logger.error(f"Fehler beim Herunterladen von {url}: {e}")
                    continue
                existing.add(name)
                report.downloaded += 1
                progress_bar.update(1)
        finally:
            progress_bar.close()
            logger.success(f"PDF-Download: {report.summary()}")
    return report


def main() -> None:
    # setup_data_directories()
    paper_list = download_paper_metadata(cfg.OPARL_ENDPOINT)
    # paper_list = load_json_from_path(cfg.PAPER_OBJECT_LISTE)
    download_paper_pdf(paper_list)


if __name__ == "__main__":
    main()
