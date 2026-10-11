"""Wo was liegt.

Laufzeitdaten unter ``data_root``, Caches unter ``cache_root``, der eingefrorene Datensatz der
Arbeit unter ``reference_root``, und der wird nur gelesen: ``guard_writable`` verweigert jeden
Pfad darunter (DEVELOPMENT_PLAN.md § 3.4, Regel 1). Eingaben behalten die Dateinamen und Formate
der Quellen; alles Abgeleitete ist Parquet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import deal

from georep.errors import GeorepError
from georep.settings import Settings


class ReferenceWriteError(GeorepError):
    """Ein Schritt wollte unter reference_root schreiben."""


@dataclass(frozen=True)
class Layout:
    data_root: Path
    cache_root: Path
    reference_root: Path

    @classmethod
    def from_settings(cls, settings: Settings) -> Layout:
        return cls(
            data_root=settings.data_root,
            cache_root=settings.cache_dir,
            reference_root=settings.reference_root,
        )

    def reference_view(self) -> Layout:
        """Dasselbe Layout, aber mit ``reference_root`` als Datenwurzel: zum Lesen der Referenz."""
        return Layout(
            data_root=self.reference_root,
            cache_root=self.reference_root / "cache",
            reference_root=self.reference_root,
        )

    # Verzeichnisse
    @property
    def external(self) -> Path:
        return self.data_root / "external"

    @property
    def raw(self) -> Path:
        return self.data_root / "raw"

    @property
    def interim(self) -> Path:
        return self.data_root / "interim"

    @property
    def processed(self) -> Path:
        return self.data_root / "processed"

    @property
    def pdf_dir(self) -> Path:
        return self.cache_root / "pdf"

    @property
    def text_dir(self) -> Path:
        return self.cache_root / "text"

    @property
    def http_cache(self) -> Path:
        return self.cache_root / "http.sqlite"

    # Eingaben, wie die Quellen sie liefern
    @property
    def results_csv(self) -> Path:
        return self.external / "Stimmbezirk_Wahlergebnis.csv"

    @property
    def districts_geojson(self) -> Path:
        return self.external / "Stimmbezirke_2025.geojson"

    @property
    def papers(self) -> Path:
        """Metadaten je Paper, eine JSON-Zeile je Paper (``PaperRecord``)."""
        return self.raw / "papers.jsonl"

    @property
    def pdf_manifest(self) -> Path:
        return self.pdf_dir / "manifest.jsonl"

    @property
    def texts(self) -> Path:
        """Textstore: alle extrahierten Texte mit Metadaten in einer Parquet-Datei."""
        return self.text_dir / "texts.parquet"

    @property
    def paper_objects(self) -> Path:
        """Altformat der Arbeit; nur noch unter ``reference_root`` gelesen."""
        return self.raw / "paper_objects.json"

    @property
    def paper_urls(self) -> Path:
        return self.raw / "paper_urls.json"

    @property
    def streets(self) -> Path:
        return self.raw / "streets_per_district.json"

    @property
    def pois(self) -> Path:
        return self.raw / "wikipedia_dict.json"

    # Zwischen- und Endergebnisse
    @property
    def corpus_legacy(self) -> Path:
        """Korpus im JSON-Format der Arbeit; nur noch unter ``reference_root`` gelesen."""
        return self.interim / "paper_with_text.json"

    @property
    def corpus(self) -> Path:
        return self.interim / "papers.parquet"

    @property
    def voters(self) -> Path:
        return self.processed / "wahlbezirke_waehler.parquet"

    @property
    def streets_by_district(self) -> Path:
        return self.processed / "wahlbezirke_strassen.parquet"

    @property
    def pois_table(self) -> Path:
        return self.processed / "wikidata_vis.parquet"

    @property
    def pois_by_district(self) -> Path:
        return self.processed / "wikidata_agg.parquet"

    @property
    def dictionary(self) -> Path:
        return self.processed / "combined_searchdict.parquet"

    @property
    def index(self) -> Path:
        return self.processed / "inverted_index.parquet"

    @property
    def results(self) -> Path:
        return self.processed / "wahlbezirke_auswertung.parquet"

    def runtime_dirs(self) -> tuple[Path, ...]:
        return (self.external, self.raw, self.interim, self.processed, self.pdf_dir, self.text_dir)

    def ensure_dirs(self) -> None:
        for directory in self.runtime_dirs():
            self.guard_writable(directory).mkdir(parents=True, exist_ok=True)

    @deal.ensure(lambda self, path, result: result is path)
    @deal.raises(ReferenceWriteError)  # exakter Typ; deal kennt keine Unterklassen
    def guard_writable(self, path: Path) -> Path:
        """Gibt ``path`` zurück, wenn er nicht unter ``reference_root`` liegt; sonst Fehler."""
        reference = self.reference_root.resolve()
        resolved = path.resolve()
        if resolved == reference or reference in resolved.parents:
            raise ReferenceWriteError(f"{path} liegt unter reference_root {self.reference_root}")
        return path
