"""Wo was liegt.

Laufzeitdaten unter ``data_root``, Caches unter ``cache_root``, der eingefrorene Datensatz der
Arbeit unter ``reference_root`` und die Fremddaten unter ``context_root``; die beiden letzten
werden nur gelesen: ``guard_writable`` verweigert jeden Pfad darunter (docs/architecture.md,
„Sicherheit", Regel 1). Eingaben behalten die Dateinamen und Formate der Quellen; alles
Abgeleitete ist Parquet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import deal

from georep.errors import GeorepError
from georep.settings import Settings


class ReferenceWriteError(GeorepError):
    """Ein Schritt wollte unter einer nur lesbaren Wurzel schreiben: ``reference_root``
    (eingefrorener Datensatz der Arbeit) oder ``context_root`` (Fremddaten im Repo)."""


@dataclass(frozen=True)
class Layout:
    data_root: Path
    cache_root: Path
    reference_root: Path
    # Eine Stadt oder Periode neben der Hauptperiode: Unterordner unter data_root und cache_root
    # (PDF-Namen sind je OParl-Body vergeben, Stamps und Textstore je Periode eigen); leer = flach.
    # Der HTTP-Cache bleibt geteilt, sein Schlüssel ist die URL.
    profile: str = ""
    # Option 03: Fremddaten je Raumeinheit, im Repo unter context/; wird nur gelesen.
    # None = keine Kontextdaten, dann fehlen die Schritte context_data, context und controls.
    context_root: Path | None = None
    # Option 02: Dateiname des Stimmbezirks-GeoJSON unter external/; ein Periodenprofil nennt
    # sein Jahr (``Stimmbezirke_2020.geojson``), damit der Ordner nicht lügt.
    districts_file: str = "Stimmbezirke_2025.geojson"
    # Option 01: die übrigen Dateinamen der Quellen, auch sie aus dem Profil. Leer heißt „gibt es
    # für diese Stadt nicht" (Straßenverzeichnis, Wahlbezirksnamen der votemanager-Präsentation).
    results_file: str = "Stimmbezirk_Wahlergebnis.csv"
    streets_file: str = ""
    district_names_file: str = ""

    @classmethod
    def from_settings(cls, settings: Settings) -> Layout:
        return cls(
            data_root=settings.data_root,
            cache_root=settings.cache_dir,
            reference_root=settings.reference_root,
            profile=settings.profile,
            context_root=settings.context.root,
            districts_file=settings.sources.opendata.districts_file,
            results_file=settings.sources.opendata.results_file,
            streets_file=settings.sources.opendata.streets_file,
            district_names_file=settings.sources.opendata.district_names_file,
        )

    def reference_view(self) -> Layout:
        """Dasselbe Layout, aber mit ``reference_root`` als Datenwurzel: zum Lesen der Referenz."""
        return Layout(
            data_root=self.reference_root,
            cache_root=self.reference_root / "cache",
            reference_root=self.reference_root,
            context_root=self.context_root,
            districts_file=self.districts_file,
            results_file=self.results_file,
            streets_file=self.streets_file,
            district_names_file=self.district_names_file,
        )

    def for_profile(self, profile: str, districts_file: str | None = None) -> Layout:
        """Dasselbe Layout für ein anderes Profil, etwa die Hauptperiode (``""``) derselben Stadt.

        ``districts_file`` nennt das Stimmbezirks-GeoJSON des anderen Profils, wenn es anders
        heißt (der Crosswalk liest so den Zielzuschnitt); ohne Angabe bleibt der eigene Name.
        """
        return Layout(
            data_root=self.data_root,
            cache_root=self.cache_root,
            reference_root=self.reference_root,
            profile=profile,
            context_root=self.context_root,
            districts_file=self.districts_file if districts_file is None else districts_file,
            results_file=self.results_file,
            streets_file=self.streets_file,
            district_names_file=self.district_names_file,
        )

    # Verzeichnisse
    @property
    def root(self) -> Path:
        """Die Datenwurzel des Profils: ``data_root`` oder ``data_root/<profil>``."""
        return self.data_root / self.profile if self.profile else self.data_root

    @property
    def cache(self) -> Path:
        return self.cache_root / self.profile if self.profile else self.cache_root

    @property
    def external(self) -> Path:
        return self.root / "external"

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def interim(self) -> Path:
        return self.root / "interim"

    @property
    def processed(self) -> Path:
        return self.root / "processed"

    @property
    def pdf_dir(self) -> Path:
        return self.cache / "pdf"

    @property
    def text_dir(self) -> Path:
        return self.cache / "text"

    @property
    def http_cache(self) -> Path:
        return self.cache_root / "http.sqlite"

    # Eingaben, wie die Quellen sie liefern
    @property
    def results_csv(self) -> Path:
        return self.external / self.results_file

    @property
    def districts_geojson(self) -> Path:
        return self.external / self.districts_file

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

    # Die Berichtsseite: eine in sich geschlossene index.html, daneben die Download-Dateien
    @property
    def site(self) -> Path:
        return self.root / "site"

    @property
    def site_index(self) -> Path:
        return self.site / "index.html"

    @property
    def site_data(self) -> Path:
        return self.site / "data"

    # Option 05: Gremien je Dokument, Kennzahlen je Wahlbezirk und je Gremium, Stadtbezirke
    @property
    def papers_bodies(self) -> Path:
        """Ein Gremium je Dokument; nicht veröffentlicht (aus der Drucksachennummer ableitbar)."""
        return self.processed / "papers_gremien.parquet"

    @property
    def district_bodies(self) -> Path:
        return self.processed / "wahlbezirke_gremien.parquet"

    @property
    def bodies_table(self) -> Path:
        return self.processed / "gremien.parquet"

    @property
    def district_units(self) -> Path:
        """Wahlbezirk zu Stadtbezirk mit Gewicht; zweite Ausgabe des Schritts ``voters``."""
        return self.processed / "wahlbezirke_stadtbezirke.parquet"

    # Option 06: Gewichtung und Themenmodell (docs/plans/06-gewichtung.md)
    @property
    def topics(self) -> Path:
        """Ein Thema je Zeile: Nummer, stärkste Wörter, dominierte Dokumente."""
        return self.processed / "themen.parquet"

    @property
    def topic_documents(self) -> Path:
        """Je Dokument mit Text das dominante Thema und sein Anteil."""
        return self.processed / "themen_dokumente.parquet"

    @property
    def topic_shares(self) -> Path:
        """Die volle Anteilsmatrix (K Zahlen je Dokument): Eingabe von ``weights``, nicht veröffentlicht."""
        return self.interim / "themen_anteile.parquet"

    @property
    def term_weights(self) -> Path:
        """Gewicht je Suchbegriff: Wahlbezirke, die ihn führen, und Dokumenthäufigkeit."""
        return self.processed / "gewichte_begriffe.parquet"

    @property
    def weighted(self) -> Path:
        """Lange Tabelle: eine Zeile je Wahlbezirk und Gewichtungsvariante."""
        return self.processed / "wahlbezirke_gewichtet.parquet"

    # Option 03: Fremddaten je Raumeinheit, Umrechnung auf Wahlbezirke, Kontrollvariablen
    @deal.pre(
        lambda self, file_name: self.context_root is not None,
        message="context_source braucht context_root; ohne Kontextdaten gibt es die Schritte nicht",
    )
    def context_source(self, file_name: str) -> Path:
        """Eine Datei des Kontextdatensatzes unter ``context_root``; die Namen stehen in den Settings.

        ``bootstrap`` kopiert sie nach ``external/``, der Netzschritt ``context_data`` holt sie
        frisch; gelesen wird immer die Kopie unter ``external/``, nie diese hier.
        """
        assert self.context_root is not None  # Vorbedingung; mypy sieht den Vertrag nicht
        return self.context_root / file_name

    @property
    def crosswalk(self) -> Path:
        """Gewichte je (Wahlbezirk, Raumeinheit) aus Stimmbezirksflächen und Wahlberechtigten."""
        return self.processed / "wahlbezirke_crosswalk.parquet"

    @property
    def context_table(self) -> Path:
        """Die Kontrollvariablen je Wahlbezirk, aus den Fremddaten umgerechnet."""
        return self.processed / "wahlbezirke_kontext.parquet"

    @property
    def controls(self) -> Path:
        """Tabelle 6: je Modell, Stichprobe und Term ein Koeffizient mit Standardfehler, p und VIF."""
        return self.processed / "regression_kontrollen.parquet"

    # Option 04: Urheber und Parteien
    @property
    def organizations(self) -> Path:
        """Fraktionen und Gremien, wie der OParl-Endpunkt sie liefert (eine Seite, Netzschritt)."""
        return self.raw / "organizations.json"

    @property
    def document_originators(self) -> Path:
        return self.processed / "dokumente_urheber.parquet"

    @property
    def district_originators(self) -> Path:
        return self.processed / "wahlbezirke_urheber.parquet"

    @property
    def party_results(self) -> Path:
        return self.processed / "wahlbezirke_parteien.parquet"

    # Option 02: Zuschnitt und Ergebnis eines älteren Wahlbezirkszuschnitts, Zuordnung der
    # Stimmbezirke auf die Hauptperiode, Vergleich zweier Perioden, Fortschritt des Abrufs
    @property
    def district_shapes_geojson(self) -> Path:
        """Die Wahlbezirksflächen der eigenen Periode (nur ein Periodenprofil mit Crosswalk)."""
        return self.external / "Kommunalwahlbezirke.geojson"

    @property
    def district_results_csv(self) -> Path:
        """Wahlergebnis je Wahlbezirk der eigenen Periode; liefert die Briefwähler je Bezirk."""
        return self.external / "Wahlbezirk_Wahlergebnis.csv"

    @property
    def precinct_assignment(self) -> Path:
        """Stimmbezirk der Periode -> Wahlbezirk der Periode und Anteil je Zielbezirk."""
        return self.processed / "stimmbezirke_zuordnung.parquet"

    @property
    def comparison(self) -> Path:
        """Beide Perioden je Wahlbezirk nebeneinander (Schritt ``compare``, Hauptperiode)."""
        return self.processed / "wahlbezirke_vergleich.parquet"

    @property
    def papers_progress(self) -> Path:
        """Die zuletzt vollständig gespeicherte OParl-Seite, für die Wiederaufnahme des Abrufs."""
        return self.raw / "papers.progress.json"

    def target_view(self, settings: Settings) -> Layout:
        """Das Layout, aus dem Flächen und Namen der Wahlbezirke kommen.

        Ohne Crosswalk ist es dieses selbst. Ein Periodenprofil mit Crosswalk rechnet auf den
        Wahlbezirken der Hauptperiode: Flächen, Namen und damit die Karte und die Bezirkstabelle
        der Seite kommen dann aus deren Stimmbezirks-GeoJSON, nicht aus dem eigenen (Option 02).
        """
        if not settings.crosswalk.enabled:
            return self
        return self.for_profile("", settings.crosswalk.target_file)

    # Option 01: Quellen, die es nur in manchen Städten gibt, der kanonische Stand der
    # Stimmbezirke und die Schnittstelle des Städtevergleichs
    @property
    def streets_directory(self) -> Path | None:
        """Das Straßenverzeichnis der Wahl (votemanager), wenn die Stadt eines veröffentlicht."""
        return self.external / self.streets_file if self.streets_file else None

    @property
    def district_names_csv(self) -> Path | None:
        """Wahlbezirksnamen, wenn die Geometrie keine trägt (votemanager-Wahlbezirks-CSV)."""
        return self.external / self.district_names_file if self.district_names_file else None

    @property
    def precincts_geojson(self) -> Path:
        """Die kanonischen Stimmbezirke: feste Eigenschaften, CRS der Quelle (Schritt ``shapes``)."""
        return self.interim / "stimmbezirke.geojson"

    @property
    def site_summary(self) -> Path:
        """Option 01: Kernzahlen und Regression als JSON; die Schnittstelle des Städtevergleichs."""
        return self.site_data / "summary.json"

    def runtime_dirs(self) -> tuple[Path, ...]:
        return (
            self.external,
            self.raw,
            self.interim,
            self.processed,
            self.pdf_dir,
            self.text_dir,
            self.site,
            self.site_data,
        )

    def ensure_dirs(self) -> None:
        for directory in self.runtime_dirs():
            self.guard_writable(directory).mkdir(parents=True, exist_ok=True)

    @deal.ensure(lambda self, path, result: result is path)
    @deal.raises(ReferenceWriteError)  # exakter Typ; deal kennt keine Unterklassen
    def guard_writable(self, path: Path) -> Path:
        """Gibt ``path`` zurück, wenn er unter keiner nur lesbaren Wurzel liegt; sonst Fehler."""
        resolved = path.resolve()
        roots = {"reference_root": self.reference_root} | (
            {"context_root": self.context_root} if self.context_root is not None else {}
        )
        for name, root in roots.items():
            readonly = root.resolve()
            if resolved == readonly or readonly in resolved.parents:
                raise ReferenceWriteError(f"{path} liegt unter {name} {root}")
        return path
