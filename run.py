"""Voller Lauf: Netzschritte (noch Altcode), dann die Polars-Kette.

Lädt alle Metadaten und PDFs neu und dauert Stunden; der OParl-Server brauchte am 2026-10-09
85 s pro Seite. Für die Offline-Kette allein reicht ``georep bootstrap`` und ``georep run``.
"""

from __future__ import annotations

from loguru import logger

from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.settings import load_settings
from src.dataset_oparl import main as oparl_main
from src.dataset_opendata import main as opendata_main
from src.dataset_streets import main as streets_main
from src.dataset_wikidata import main as wikidata_main
from src.prep_papers import main as papers_main


def main() -> None:
    settings = load_settings()
    layout = Layout.from_settings(settings)
    layout.ensure_dirs()
    logger.info("Netzschritte (Altcode; Phase 3 ersetzt sie)")
    oparl_main()
    opendata_main()
    streets_main()
    wikidata_main()
    papers_main()
    logger.info("Polars-Kette")
    for outcome in run_pipeline(build_steps(settings, layout), settings):
        print(outcome.line())
    logger.success("Alle Prozesse abgeschlossen")


if __name__ == "__main__":
    main()
