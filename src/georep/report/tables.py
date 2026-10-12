"""Register der veröffentlichten Tabellen: Name, Datei, Beschreibung, Spaltendoku, CSV-Regeln.

Jede Tabelle, die auf der Berichtsseite zum Download steht, hat hier genau einen Eintrag; daraus
entstehen die Download-Liste, ``schema.json``, die CSV-Dateien (dieselben Regeln wie
``georep export``) und die Spaltentabelle der Seite. Eine Option, die Tabellen ergänzt, hängt ihre
Einträge am Ende von ``TABLES`` an (docs/plans/00-synergien.md, F2); ``optional`` kennzeichnet
Tabellen, die nur in manchen Profilen entstehen, ``enabled`` solche, die an einem Schalter in den
Settings hängen (dann zählt der Schalter, nicht die Datei: eine abgeschaltete Stufe lässt ihre
Ausgaben liegen, und die gehören nicht mehr auf die Seite). Ein Test prüft beide Richtungen gegen
die Parquet-Schemata: jede Spalte beschrieben, keine Beschreibung ohne Spalte.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import deal

from georep.analysis.ols import MODELS_SCHEMA
from georep.crosswalk import UNIT, UNIT_NAME, WEIGHT
from georep.layout import Layout
from georep.prep.context import MISSING_SUFFIX
from georep.settings import Settings


@dataclass(frozen=True)
class PublishedTable:
    name: str  # Dateistamm, etwa ``wahlbezirke_auswertung``
    path: Callable[[Layout], Path]  # die Parquet-Datei im Layout
    description: str  # ein Satz für die Download-Tabelle
    columns: Mapping[str, tuple[str, str]]  # Spalte -> (Bedeutung, Einheit)
    joins: Mapping[str, str] = field(default_factory=dict)  # Listen-Spalte -> Trenner in der CSV
    separator: str = ","  # Spaltentrenner der CSV
    optional: bool = False  # nur veröffentlichen, wenn die Datei vorliegt (profilabhängig)
    # Nur veröffentlichen, wenn die Settings die Stufe eingeschaltet lassen; ohne Settings
    # (Aufrufer ohne Konfiguration, etwa ``georep export``) zählt der Schalter nicht.
    enabled: Callable[[Settings], bool] | None = None

    # Tabellen, deren Spalten in den Settings stehen (Option 03: eine Spalte je Kontrollvariable),
    # beschreiben sich erst zur Laufzeit; ``columns`` bleibt dann leer.
    describe: Callable[[Settings], Mapping[str, tuple[str, str]]] | None = None

    def column_docs(self, settings: Settings) -> Mapping[str, tuple[str, str]]:
        """Die Spaltendoku dieser Tabelle, statisch oder aus den Settings abgeleitet."""
        return self.describe(settings) if self.describe is not None else self.columns


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
    # Option 05: Gremien (docs/plans/05-gremien.md, Entscheidung 8)
    PublishedTable(
        "wahlbezirke_gremien",
        lambda layout: layout.district_bodies,
        "Treffer je Wahlbezirk nach Gremium: eigene Bezirksvertretung, andere, Rat, Ausschüsse, Beiräte",
        {
            "wahlkreis_id": DISTRICT_COLUMN,
            "stadtbezirke": (
                "Stadtbezirke mit Wahlberechtigten dieses Wahlbezirks, nach Gewicht absteigend",
                "Liste",
            ),
            "anzahl_treffer": ("Dokumente mit mindestens einem Treffer", "Dokumente"),
            "treffer_eigene_bv": (
                "Treffer aus der Bezirksvertretung eines eigenen Stadtbezirks",
                "Dokumente",
            ),
            "treffer_andere_bv": ("Treffer aus einer anderen Bezirksvertretung", "Dokumente"),
            "treffer_rat": ("Treffer aus Vorlagen des Rates", "Dokumente"),
            "treffer_ausschuss": ("Treffer aus Vorlagen eines Ausschusses", "Dokumente"),
            "treffer_beirat": ("Treffer aus Vorlagen eines Beirats", "Dokumente"),
            "treffer_unbekannt": (
                "Treffer aus Dokumenten, deren Drucksachennummer kein bekanntes Gremium nennt",
                "Dokumente",
            ),
            "anteil_eigene_bv": (
                "treffer_eigene_bv geteilt durch anzahl_treffer",
                "Anteil 0 bis 1",
            ),
            "anteil_rat": ("treffer_rat geteilt durch anzahl_treffer", "Anteil 0 bis 1"),
            "quote_eigene_bv": (
                "treffer_eigene_bv geteilt durch Wahlberechtigte_insgesamt",
                "Dokumente je Person",
            ),
        },
        joins={"stadtbezirke": ";"},
    ),
    PublishedTable(
        "gremien",
        lambda layout: layout.bodies_table,
        "Gremien der Wahlperiode: Dokumente, Dokumente mit Treffer, Lokalität der Bezirksvertretungen",
        {
            "gremium": (
                "Kürzel der Drucksachennummer samt Nummer (BV6, RAT, OVA); leer, wenn die Nummer kein Muster trifft",
                "",
            ),
            "gremium_art": ("bezirksvertretung, rat, ausschuss, beirat oder unbekannt", ""),
            "stadtbezirk": ("Stadtbezirk einer Bezirksvertretung, sonst leer", ""),
            "dokumente": ("Dokumente der Wahlperiode mit dieser Drucksachennummer", "Dokumente"),
            "mit_treffer": (
                "davon Dokumente mit mindestens einem Treffer in mindestens einem Wahlbezirk",
                "Dokumente",
            ),
            "anteil_eigener_stadtbezirk": (
                "nur Bezirksvertretungen: Anteil ihrer Treffer in Wahlbezirken ihres Stadtbezirks",
                "Anteil 0 bis 1",
            ),
        },
    ),
    PublishedTable(
        "wahlbezirke_stadtbezirke",
        lambda layout: layout.district_units,
        "Zuordnung Wahlbezirk zu Stadtbezirk, gewichtet über die Wahlberechtigten",
        {
            "wahlkreis_id": DISTRICT_COLUMN,
            "stadtbezirk": ("Nummer des Stadtbezirks (1 bis 10)", ""),
            "wahlberechtigte": (
                "Wahlberechtigte des Wahlbezirks in diesem Stadtbezirk",
                "Personen",
            ),
            "gewicht": (
                "Anteil dieses Stadtbezirks an den Wahlberechtigten des Wahlbezirks",
                "Anteil 0 bis 1",
            ),
        },
    ),
]

# Option 06: Gewichtung (docs/plans/06-gewichtung.md). Alle vier sind ``optional``: ``topics.k = 0``
# schaltet den Schritt ``topics`` ab, und eine Datenwurzel ohne den Schritt ``weights`` soll eine
# Seite ohne den Abschnitt bauen statt mit einem Schemafehler abzubrechen (der Schritt ``report``
# nennt beide Dateien als Eingabe, meldet also vorher, was fehlt). Die Anteilsmatrix selbst bleibt
# ein Zwischenstand unter ``interim/`` und wird nicht veröffentlicht.
TABLES.append(
    PublishedTable(
        "wahlbezirke_gewichtet",
        lambda layout: layout.weighted,
        "Gewichtete Treffer und Quoten je Wahlbezirk, eine Zeile je Gewichtungsvariante",
        {
            "wahlkreis_id": DISTRICT_COLUMN,
            "variante": (
                "Name der Gewichtung: einheit (wie die Arbeit), bezirke, idf, ein Regelsatz der "
                "Dokumentart, kombiniert oder thema_NN",
                "",
            ),
            "anzahl_treffer_gewichtet": (
                "Summe der Dokumentgewichte; bei der Variante einheit gleich anzahl_treffer",
                "Dokumente",
            ),
            "trefferquote_gewichtet": (
                "anzahl_treffer_gewichtet geteilt durch Wahlberechtigte_insgesamt",
                "Dokumente je Person",
            ),
        },
        optional=True,
    )
)
TABLES.append(
    PublishedTable(
        "gewichte_begriffe",
        lambda layout: layout.term_weights,
        "Gewicht je Suchbegriff: in wie vielen Wahlbezirken und Dokumenten er vorkommt",
        {
            "suchbegriffe": ("Suchbegriff, kleingeschrieben", ""),
            "n_bezirke": ("Wahlbezirke, deren Wörterbuch den Begriff führt", "Wahlbezirke"),
            "anzahl_treffer": (
                "Dokumente mit dem Begriff, wie im invertierten Index",
                "Dokumente",
            ),
            "gewicht_bezirke": ("1 geteilt durch n_bezirke", "Anteil 0 bis 1"),
            "gewicht_idf": (
                "normierte inverse Dokumenthäufigkeit (ln N − ln df) / ln N: 1 für einen Begriff "
                "in einem einzigen Dokument, 0 für einen in allen",
                "Anteil 0 bis 1",
            ),
        },
        optional=True,
    )
)
TABLES.append(
    PublishedTable(
        "themen",
        lambda layout: layout.topics,
        "Themen des Modells (TF-IDF und NMF): die stärksten Wörter je Thema",
        {
            "thema": ("Nummer des Themas; sie gilt nur für diesen Datenstand", ""),
            "woerter": (
                "die stärksten Wörter des Themas, absteigend; sie beschreiben das Thema, "
                "sie benennen es nicht",
                "Liste",
            ),
            "dokumente": ("Dokumente, deren stärkstes Thema dieses ist", "Dokumente"),
            "gewicht_summe": ("Summe der Themenanteile über alle Dokumente", "Dokumente"),
        },
        joins={"woerter": "; "},
        optional=True,
        enabled=lambda settings: settings.topics.k > 0,
    )
)
TABLES.append(
    PublishedTable(
        "themen_dokumente",
        lambda layout: layout.topic_documents,
        "Je Dokument mit Text das stärkste Thema und sein Anteil",
        {
            "id": ("OParl-URL des Dokuments", ""),
            "thema": ("Nummer des stärksten Themas", ""),
            "anteil": ("Anteil dieses Themas am Dokument, vier Stellen", "Anteil 0 bis 1"),
        },
        optional=True,
        enabled=lambda settings: settings.topics.k > 0,
    )
)

# --- Option 03: Kontrollvariablen, ihre Umrechnung und die Modelle -------------------------------


def context_columns(settings: Settings) -> dict[str, tuple[str, str]]:
    """Spaltendoku von ``wahlbezirke_kontext``: je Variable der Settings eine Spalte."""
    context = settings.context
    units = context.units.label
    docs: dict[str, tuple[str, str]] = {"wahlkreis_id": DISTRICT_COLUMN}
    for variable in context.variables:
        origin = (
            "Spalte des Wahlergebnisses je Wahlbezirk"
            if variable.kind == "district"
            else f"gewichtetes Mittel über die {units} des Wahlbezirks"
        )
        docs[variable.name] = (f"{variable.label}, {origin}", variable.unit)
    for variable in context.unit_variables():
        docs[f"{variable.name}{MISSING_SUFFIX}"] = (
            f"Anteil des Gewichts, der bei {variable.label} auf {units} ohne Wert liegt",
            "Anteil 0 bis 1",
        )
    return docs


def _model_column(column: str) -> tuple[str, str]:
    texts: dict[str, tuple[str, str]] = {
        "modell": ("Modell: A (nur Trefferquote), B, C oder single:<Variable>", ""),
        "stichprobe": ("alle Wahlbezirke oder ohne die Ausreißer der Arbeit", ""),
        "term": ("Term des Modells; (Konstante) ist der Achsenabschnitt", ""),
        "koeffizient": ("geschätzter Koeffizient; y ist die Wahlbeteiligung in Prozent", ""),
        "standardfehler": ("Standardfehler des Koeffizienten", ""),
        "t": ("Koeffizient geteilt durch seinen Standardfehler", ""),
        "p": ("zweiseitiger p-Wert zur t-Verteilung mit n − k − 1 Freiheitsgraden", "0 bis 1"),
        "beta_std": ("standardisierter Koeffizient b · sd(x)/sd(y); leer für die Konstante", ""),
        "vif": ("Varianzinflation aus einer Hilfsregression; leer für die Konstante", ""),
        "n": ("Wahlbezirke im Modell", ""),
        "k": ("Terme ohne die Konstante", ""),
        "r2": ("Bestimmtheitsmaß des Modells", "0 bis 1"),
        "r2_adj": ("um k korrigiertes Bestimmtheitsmaß", ""),
        "f_p": ("p-Wert des F-Tests gegen das Modell nur mit Konstante", "0 bis 1"),
    }
    return texts[column]


TABLES += [
    # Option 03
    PublishedTable(
        "wahlbezirke_kontext",
        lambda layout: layout.context_table,
        "Kontrollvariablen je Wahlbezirk, aus den Fremddaten umgerechnet",
        {},
        optional=True,
        describe=context_columns,
    ),
    PublishedTable(
        "wahlbezirke_crosswalk",
        lambda layout: layout.crosswalk,
        "Gewicht jeder Raumeinheit im Wahlbezirk (Wahlberechtigte je Stimmbezirk mal Flächenanteil)",
        {
            "wahlkreis_id": DISTRICT_COLUMN,
            UNIT: ("Schlüssel der Raumeinheit in den Fremddaten", ""),
            UNIT_NAME: ("Name der Raumeinheit", ""),
            WEIGHT: ("Gewicht der Einheit im Wahlbezirk; je Wahlbezirk Summe 1", "Anteil 0 bis 1"),
        },
        optional=True,
    ),
    PublishedTable(
        "regression_kontrollen",
        lambda layout: layout.controls,
        "Tabelle 6: je Modell, Stichprobe und Term ein Koeffizient mit Standardfehler, p und VIF",
        {column: _model_column(column) for column in MODELS_SCHEMA},
        optional=True,
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


def _wanted(table: PublishedTable, layout: Layout, settings: Settings | None) -> bool:
    if table.enabled is not None and settings is not None and not table.enabled(settings):
        return False
    return not table.optional or table.path(layout).exists()


@deal.post(_unique_names, message="jede Tabelle hat einen eigenen Namen")
def published(layout: Layout, settings: Settings | None = None) -> list[PublishedTable]:
    """Die Tabellen der Seite in Reihenfolge; optionale nur, wenn ihre Datei vorliegt.

    ``settings`` schaltet Tabellen ab, deren Stufe abgeschaltet ist (``enabled``); ohne Settings
    entscheidet allein die Datei, wie bisher.
    """
    return [t for t in TABLES if _wanted(t, layout, settings)]


def csv_plan(layout: Layout) -> list[tuple[Path, dict[str, str], str]]:
    """(Parquet-Datei, Listen-Spalte -> Trenner, Spaltentrenner) je Tabelle, wie der Altcode."""
    return [(t.path(layout), dict(t.joins), t.separator) for t in (*TABLES, *EXPORT_ONLY)]
