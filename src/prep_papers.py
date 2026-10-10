"""
Prepares paper data by extracting text from PDFs and adding it to the paper metadata.
"""
from pathlib import Path

from loguru import logger
from pypdf import PdfReader

import src.config as cfg
from src.utils import load_json_from_path, save_json_to_path


def get_text_from_pdf(path: Path) -> str:
    try:
        with open(path, 'rb') as f:
            reader = PdfReader(f)
            text = "\n".join(p.extract_text() for p in reader.pages)
            return text.replace('\n', '').lower()
    except Exception as e:
        logger.warning(f"Fehler beim Extrahieren von Text aus PDF: {e}")
        return ""

def main() -> None:
    # Load copy of raw paper metadata
    papers = load_json_from_path(cfg.PAPER_OBJECT_LISTE).copy()
    logger.info(f"{len(papers)} Paper aus Metadaten geladen.")

    processed_count = 0
    error_count = 0


    for i, paper in enumerate(papers, start=1):
        try:
            logger.info(f"Verarbeite Paper {i}/{len(papers)}")
            pdf_name = paper.get('download_url').split('/')[-1]
            if pdf_name and Path(cfg.PDF_DUMP_PATH / pdf_name).exists():
                full_text = get_text_from_pdf(Path(cfg.PDF_DUMP_PATH / pdf_name))
                parts = full_text.split('betrifft', 1)

                paper['paper_text'] = parts[1] if len(parts) > 1 else parts[0]
                processed_count += 1
            else:
                paper['paper_text'] = ''
                logger.warning(f"PDF nicht gefunden: {pdf_name}")
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten von Paper {pdf_name}: {e}")
            paper['paper_text'] = ''
            error_count += 1

    save_json_to_path(papers, cfg.PAPER_WITH_TEXT_PATH)
    logger.success(f"Extraktion beendet. Erfolgreich: {processed_count}, Fehler: {error_count}")
    logger.info(f"Ergebnisse gespeichert unter {cfg.PAPER_WITH_TEXT_PATH}")

if __name__ == "__main__":
    main()