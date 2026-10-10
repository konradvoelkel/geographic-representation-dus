"""Führt die Offline-Kette des Altcodes (``src/*.py``) mit umgebogenen Pfaden aus.

Der Altcode liest und schreibt feste Pfade aus ``src.config``. Damit Tests nie in das
Referenzverzeichnis schreiben, werden die Pfadkonstanten für die Dauer eines Laufs auf ein
Eingabe- und ein Ausgabeverzeichnis gesetzt und danach wiederhergestellt. Die Kette ist
``prep_voters → prep_wiki → prep_streets → combine_searchdicts → reverse_index → analyse``;
``prep_papers`` fehlt absichtlich, es braucht PDFs und überschreibt sonst den Korpus.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import src.config as cfg
from src import analyse, combine_searchdicts, prep_streets, prep_voters, prep_wiki, reverse_index

INPUT_FILES: dict[str, tuple[str, str]] = {
    "WAHLERGEBNIS_PATH": ("external", "Stimmbezirk_Wahlergebnis.csv"),
    "STREET_PER_DISTRICT_PATH": ("raw", "streets_per_district.json"),
    "WIKI_DICT": ("raw", "wikipedia_dict.json"),
    "PAPER_WITH_TEXT_PATH": ("interim", "paper_with_text.json"),
}
OUTPUT_FILES: dict[str, str] = {
    "AGG_VOTERS_PER_WAHLBEZIRK_PATH": "wahlbezirke_waehler.csv",
    "WIKIDATA_VIS_PATH": "wikidata_vis.csv",
    "AGG_WIKIDATA_PATH": "wikidata_agg.csv",
    "AGG_STREETS_PER_WAHLBEZIRK_PATH": "wahlbezirke_strassen.csv",
    "COMBINED_SEARCHDICT_PATH": "combined_searchdict.csv",
    "INVERTED_INDEX_PATH": "inverted_index.csv",
    "AUSWERTUNG_PATH": "wahlbezirke_auswertung.csv",
}


@contextmanager
def patched_config(inputs: Path, processed: Path) -> Iterator[None]:
    """Biegt die Pfadkonstanten in ``src.config`` um und stellt sie danach wieder her."""
    names = [*INPUT_FILES, *OUTPUT_FILES]
    saved = {name: getattr(cfg, name) for name in names}
    try:
        for name, (subdir, filename) in INPUT_FILES.items():
            setattr(cfg, name, inputs / subdir / filename)
        for name, filename in OUTPUT_FILES.items():
            setattr(cfg, name, processed / filename)
        yield
    finally:
        for name, value in saved.items():
            setattr(cfg, name, value)


def run_offline_chain(inputs: Path, processed: Path) -> None:
    """Liest unter ``inputs/{external,raw,interim}``, schreibt die sieben Ausgaben nach ``processed``."""
    processed.mkdir(parents=True, exist_ok=True)
    with patched_config(inputs, processed):
        prep_voters.main()
        prep_wiki.main()
        prep_streets.main()
        combine_searchdicts.main()
        reverse_index.main()
        analyse.main()
