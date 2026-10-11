"""Register der veröffentlichten Tabellen: Name, Datei, Beschreibung, Spaltendoku, CSV-Regeln.

Jede Tabelle, die auf der Berichtsseite zum Download steht, hat hier genau einen Eintrag; daraus
entstehen die Download-Liste, ``schema.json``, die CSV-Dateien (dieselben Regeln wie
``georep export``) und die Spaltentabelle der Seite. Eine Option, die Tabellen ergänzt, hängt ihre
Einträge am Ende von ``TABLES`` an (docs/plans/00-synergien.md, F2); ``optional`` kennzeichnet
Tabellen, die nur in manchen Profilen entstehen. Ein Test prüft beide Richtungen gegen die
Parquet-Schemata: jede Spalte beschrieben, keine Beschreibung ohne Spalte.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import deal

from georep.layout import Layout


@dataclass(frozen=True)
class PublishedTable:
    name: str  # Dateistamm, etwa ``wahlbezirke_auswertung``
    path: Callable[[Layout], Path]  # die Parquet-Datei im Layout
    description: str  # ein Satz für die Download-Tabelle
    columns: Mapping[str, tuple[str, str]]  # Spalte -> (Bedeutung, Einheit)
    joins: Mapping[str, str] = field(default_factory=dict)  # Listen-Spalte -> Trenner in der CSV
    separator: str = ","  # Spaltentrenner der CSV
    optional: bool = False  # nur veröffentlichen, wenn die Datei vorliegt (profilabhängig)


DISTRICT_COLUMN = ("Nummer des Kommunalwahlbezirks (1 bis 41)", "")
_VOTER_COLUMNS: dict[str, tuple[str, str]] = {
    "wahlkreis_id": DISTRICT_COLUMN,
    "Wahlberechtigte_insgesamt": ("Wahlberechtigte, Summe über die Stimmbezirke", "Personen"),
    "Waehler": ("Wählerinnen und Wähler, Summe über die Stimmbezirke", "Personen"),
    "CDU_Stimmen": ("Stimmen für die CDU", "Stimmen"),
    "GRUENE_Stimmen": ("Stimmen für Bündnis 90/Die Grünen", "Stimmen"),
    "SPD_Stimmen": ("Stimmen für die SPD", "Stimmen"),
    "FDP_Stimmen": ("Stimmen für die FDP", "Stimmen"),
    "Die_Linke_Stimmen": ("Stimmen für Die Linke", "Stimmen"),
    "AfD_Stimmen": ("Stimmen für die AfD", "Stimmen"),
    "wahlbeteiligung": ("Wähler geteilt durch Wahlberechtigte", "Anteil 0 bis 1"),
    "CDU_anteil": ("Stimmenanteil der CDU an den Wählern", "Anteil 0 bis 1"),
    "GRUENE_anteil": ("Stimmenanteil von Bündnis 90/Die Grünen an den Wählern", "Anteil 0 bis 1"),
    "SPD_anteil": ("Stimmenanteil der SPD an den Wählern", "Anteil 0 bis 1"),
    "FDP_anteil": ("Stimmenanteil der FDP an den Wählern", "Anteil 0 bis 1"),
    "Die_Linke_anteil": ("Stimmenanteil von Die Linke an den Wählern", "Anteil 0 bis 1"),
    "AfD_anteil": ("Stimmenanteil der AfD an den Wählern", "Anteil 0 bis 1"),
}

# Reihenfolge = Reihenfolge der Downloads auf der Seite. Neue Einträge hängen Optionen unten an.
TABLES: list[PublishedTable] = [
    PublishedTable(
        "wahlbezirke_auswertung",
        lambda layout: layout.results,
        "Auswertung je Wahlbezirk: Treffer, Begriffe, Dokument-IDs, Wähler, Trefferquote",
        {
            "wahlkreis_id": DISTRICT_COLUMN,
            "suchbegriffe": (
                "Begriffe des Wörterbuchs, wie die Arbeit sie anzeigt (ohne die versteckten)",
                "Liste",
            ),
            "paper_ids": ("OParl-URLs der Dokumente mit mindestens einem Treffer", "Liste"),
            "anzahl_treffer": (
                "Dokumente mit mindestens einem Treffer, Länge von paper_ids",
                "Dokumente",
            ),
            **{k: v for k, v in _VOTER_COLUMNS.items() if k != "wahlkreis_id"},
            "trefferquote": (
                "anzahl_treffer geteilt durch Wahlberechtigte_insgesamt",
                "Dokumente je Person",
            ),
        },
        joins={"suchbegriffe": "; ", "paper_ids": ";"},
    ),
    PublishedTable(
        "inverted_index",
        lambda layout: layout.index,
        "Invertierter Index: je Begriff die Dokumente mit Treffer",
        {
            "suchbegriffe": ("Suchbegriff, kleingeschrieben", ""),
            "paper_ids": ("OParl-URLs der Dokumente, in denen der Begriff vorkommt", "Liste"),
            "anzahl_treffer": ("Länge von paper_ids", "Dokumente"),
        },
        joins={"paper_ids": ";"},
    ),
    PublishedTable(
        "combined_searchdict",
        lambda layout: layout.dictionary,
        "Wörterbuch je Wahlbezirk mit allen Begriffen",
        {
            "wahlkreis_id": DISTRICT_COLUMN,
            "suchbegriffe": (
                "alle Begriffe des Wörterbuchs: Straßen und Orte, mit str.-Varianten, auch versteckte",
                "Liste",
            ),
        },
        joins={"suchbegriffe": ", "},
        separator=";",
    ),
    PublishedTable(
        "wahlbezirke_waehler",
        lambda layout: layout.voters,
        "Wahlergebnis der Ratswahl 2025 je Wahlbezirk",
        dict(_VOTER_COLUMNS),
    ),
    PublishedTable(
        "wikidata_vis",
        lambda layout: layout.pois_table,
        "Orte mit Koordinate und Wahlbezirk",
        {
            "label": ("Name des Orts aus Wikidata oder Wikipedia, Kommas entfernt", ""),
            "wahlkreis_id": DISTRICT_COLUMN,
            "lon": ("geografische Länge", "Grad, EPSG:4326"),
            "lat": ("geografische Breite", "Grad, EPSG:4326"),
        },
    ),
    PublishedTable(
        "wahlbezirke_strassen",
        lambda layout: layout.streets_by_district,
        "Straßennamen je Wahlbezirk",
        {
            "wahlkreis_id": DISTRICT_COLUMN,
            "suchbegriffe": ("Straßennamen aus OpenStreetMap", "Liste"),
        },
        joins={"suchbegriffe": "; "},
    ),
]

# Nur für ``georep export`` (CSV neben der Parquet-Datei), nicht auf der Seite.
EXPORT_ONLY: list[PublishedTable] = [
    PublishedTable(
        "wikidata_agg",
        lambda layout: layout.pois_by_district,
        "Orte je Wahlbezirk als Begriffsliste",
        {"wahlkreis_id": DISTRICT_COLUMN, "suchbegriffe": ("Ortsnamen", "Liste")},
        joins={"suchbegriffe": "; "},
    ),
]

# ``wahlbezirke.geojson`` ist keine Parquet-Tabelle, steht aber mit denselben Eigenschaften im Schema.
GEOJSON_TABLE = "wahlbezirke"
GEOJSON_COLUMNS: dict[str, tuple[str, str]] = {
    "wahlkreis_id": DISTRICT_COLUMN,
    "name": ("Name des Kommunalwahlbezirks laut Open-Data-Portal", ""),
    "anzahl_treffer": ("Dokumente mit mindestens einem Treffer", "Dokumente"),
    "trefferquote": (
        "anzahl_treffer geteilt durch Wahlberechtigte_insgesamt",
        "Dokumente je Person",
    ),
    "wahlbeteiligung": ("Wähler geteilt durch Wahlberechtigte", "Anteil 0 bis 1"),
}


def _unique_names(result: list[PublishedTable]) -> bool:
    names = [t.name for t in result]
    return len(names) == len(set(names))


@deal.post(_unique_names, message="jede Tabelle hat einen eigenen Namen")
def published(layout: Layout) -> list[PublishedTable]:
    """Die Tabellen der Seite in Reihenfolge; optionale nur, wenn ihre Datei vorliegt."""
    return [t for t in TABLES if not t.optional or t.path(layout).exists()]


def csv_plan(layout: Layout) -> list[tuple[Path, dict[str, str], str]]:
    """(Parquet-Datei, Listen-Spalte -> Trenner, Spaltentrenner) je Tabelle, wie der Altcode."""
    return [(t.path(layout), dict(t.joins), t.separator) for t in (*TABLES, *EXPORT_ONLY)]
