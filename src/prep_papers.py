"""
Prepares paper data by extracting text from PDFs and adding it to the paper metadata.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from loguru import logger
from pypdf import PdfReader

import src.config as cfg
from georep.errors import CorruptPdfError, EmptyResultError, MissingInputError
from src.utils import load_json_from_path, save_json_to_path


def get_text_from_pdf(path: Path) -> str:
    """Text aller Seiten, kleingeschrieben, ohne Zeilenumbrüche.

    Wirft ``FileNotFoundError``, wenn die Datei fehlt, und ``CorruptPdfError``, wenn pypdf sie
    nicht lesen kann. Bis 2026-10-11 kam in beiden Fällen ein leerer String zurück, und ein
    kaputtes PDF war von einem leeren nicht zu unterscheiden.
    """
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        with open(path, "rb") as f:
            reader = PdfReader(f)
            text = "\n".join(p.extract_text() for p in reader.pages)
    except Exception as e:  # pypdf wirft je nach Defekt PdfReadError, ValueError, KeyError, ...
        raise CorruptPdfError(f"{path.name}: {e}") from e
    return text.replace("\n", "").lower()


def _count_texts(papers: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for p in papers if p.get("paper_text"))


def main(force: bool = False) -> None:
    """Extrahiert die Texte der heruntergeladenen PDFs in den Korpus.

    Guards: ohne PDFs läuft nichts an (bis 2026-10-11 wurde dann der Korpus mit leeren Texten
    überschrieben), und ein Ergebnis mit weniger Texten als der vorhandene Korpus wird nicht
    geschrieben, es sei denn ``force=True``.
    """
    pdf_dir = Path(cfg.PDF_DUMP_PATH)
    pdfs = {p.name for p in pdf_dir.glob("*.pdf")} if pdf_dir.is_dir() else set()
    if not pdfs:
        raise MissingInputError(
            f"Keine PDFs unter {pdf_dir}; prep_papers würde den Korpus mit leeren Texten überschreiben."
        )

    papers = load_json_from_path(cfg.PAPER_OBJECT_LISTE)
    logger.info(f"{len(papers)} Paper aus Metadaten geladen, {len(pdfs)} PDFs vorhanden.")

    processed_count = 0
    error_count = 0
    missing_count = 0
    for paper in papers:
        pdf_name = (paper.get("download_url") or "").split("/")[-1]
        paper["paper_text"] = ""
        if pdf_name not in pdfs:
            missing_count += 1
            continue
        try:
            full_text = get_text_from_pdf(pdf_dir / pdf_name)
        except CorruptPdfError as e:
            logger.error(f"Fehler beim Verarbeiten von Paper {pdf_name}: {e}")
            error_count += 1
            continue
        parts = full_text.split("betrifft", 1)
        paper["paper_text"] = parts[1] if len(parts) > 1 else parts[0]
        processed_count += 1

    out = Path(cfg.PAPER_WITH_TEXT_PATH)
    n_texts = _count_texts(papers)
    if out.exists() and not force:
        existing = _count_texts(load_json_from_path(out))
        if n_texts < existing:
            raise EmptyResultError(
                f"Ergebnis hätte {n_texts} Texte, der vorhandene Korpus {existing}; "
                "nicht überschrieben (force=True erzwingt es)."
            )
    save_json_to_path(papers, out)
    logger.success(
        f"Extraktion beendet: {processed_count} extrahiert, {error_count} fehlerhaft, "
        f"{missing_count} ohne PDF, {n_texts} Texte gespeichert unter {out}"
    )


if __name__ == "__main__":
    main()
