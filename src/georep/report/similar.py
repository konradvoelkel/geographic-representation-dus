"""Ähnliche Dokumente im Dokumentdialog und als Download (Vorhaben 18, Stufe 3).

Stufe 3 von Vorhaben 18 nach ``docs/plans/18-einbettungen.md`` (§ 7, § 10) und
``docs/plan-zeigen-2026-11.md`` (§ 4 V2, § 6). Kein Abschnitt und keine Unterseite:

* **Im Dialog** hängt sich 18 nur mit Daten an den Haken von V2 (``report.dialog``):
  ``data/aehnlich.json`` trägt je Dokument des Dialogs die ersten ``IN_DIALOG`` Nachbarn aus
  ``processed/aehnliche_dokumente.parquet`` nach Rang, als Index in ``dokumente.json`` oder als
  eigenes Ziel mit Link, Datum, Drucksache und Titel. Der Dialog zeigt sie als Liste zum Aufklappen
  (``DialogHook.listed``), je Vorschlag Drucksache, Datum und Titel als Link (``show``).
* **Als Download** die ganze Tabelle, zehn je Dokument, nur als Parquet (CSV: ``docs/todo.md``,
  Punkt 35), mit Spaltendoku und dem Satz unter den Downloads.
* **Der Satz** unter der Liste und unter den Downloads (``similar_sentence``): das Modell mit Lizenz
  und Quelle, die Präzision@5 mit Intervall aus der Kodierung, nur wenn α genügt, der Satz aus
  ``guete.json`` und dass nur dieser Datensatz geprüft ist (Frage 9.10).
* **Wo.** Nur, wo das Profil das Nachbarpaket nennt (``similar_enabled``: die Hauptperiode und ihr
  Vergleich), der Datensatz zur Stichprobe gehört (``report.downloads.measured``) und die Tabelle
  Zeilen hat; eine Datenwurzel ohne Paketkopie schreibt eine leere Tabelle und zeigt nichts. Die
  anderen Profile zeigen weder Zeile noch Download noch Fehler.

Die Präzision@5 trägt ``guete.json`` nicht: sie ist eine Zahl des Verfahrens gegen die Endlabels
(Messdokument § 4.4) und steht darum als geprüfte Konstante hier (``NEIGHBORS_CHECK``, wie
``HEAD_CHECK`` von 11); ``tests/unit/test_report_similar.py`` rechnet sie aus Labels und Paket im
Repo nach, und ``read_quality`` bricht ab, wenn ``guete.json`` eine andere Kodierung beschreibt.
Keine Vektoren und keine freie Suche auf der Seite (Fragen 9.1, 9.3, 9.7). Kein Stadtwort: Stadt und
Periode kommen aus den Settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from georep.errors import SchemaError
from georep.layout import Layout
from georep.report.dialog import DialogRows, DialogTarget
from georep.report.documents import listed_link
from georep.report.downloads import (
    QUALITY,
    LabelCheck,
    Measure,
    capitalized,
    check_files,
    measured,
    read_quality,
)
from georep.settings import Settings

DIALOG_NAME = "aehnlich"  # data/aehnlich.json
TABLE_NAME = "aehnliche_dokumente"
DIALOG_TITLE = "Ähnliche Dokumente"
IN_DIALOG = 5  # Vorschläge je Dokument im Dialog (Plan § 7); der Download trägt alle zehn
# Das Modell der Messung (Messdokument § 2). Lizenz und Quelle hat der Supervisor am 2026-11-28 auf
# der Modellseite nachgesehen (Frage 47, Messdokument Frage 9.6); ``ollama show --license`` ist leer.
MEASURED_MODEL = "nomic-embed-text-v2-moe"
MODEL_LICENSE = "Apache-2.0"
MODEL_SOURCE = "https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe"
QUESTION = "aehnlich"  # die Frage des Codebuchs
HIT_LABELS = ("gleiches_thema", "gleiche_sache")  # ein Treffer der Präzision (Messdokument § 3.1)
ANCHORS = 50  # Dokumente, deren fünf Vorschläge kodiert sind
# Was ``guete.json`` nicht trägt: die Einbettung gegen die Endlabels, Rang 1 bis 5 der 50 Anker
# (Messdokument § 4.4); nachgerechnet in ``test_die_praezision_folgt_aus_labels_und_paket``.
NEIGHBORS_CHECK = LabelCheck(
    project="18-einbettungen-nachbarn",
    codebook_version="2026-11-23.1",
    units=383,
    measures=(Measure("Präzision@5", 250, hits=208),),
)
TABLE_DESCRIPTION = (
    "Die zehn ähnlichsten Ratsdokumente je Dokument nach der Einbettung von Titel und Text: Rang, "
    "Nachbar, Ähnlichkeit; nur Dokumente mit Rohtext, nie dieselbe PDF-Datei"
)
DIALOG_DESCRIPTION = (
    "Ähnliche Dokumente je Dokument des Dialogs: die fünf nächsten, als Index in dokumente.json "
    "oder mit Link, Datum, Drucksache und Titel; der Dokumentdialog lädt die Datei beim ersten "
    "Öffnen nach"
)
COLUMNS: dict[str, tuple[str, str]] = {
    "id": ("OParl-URL des Dokuments", ""),
    "rang": ("1 bis 10, 1 ist das ähnlichste", ""),
    "nachbar": (
        "OParl-URL des ähnlichen Dokuments: die kleinste Korpus-ID seiner PDF-Datei, nie dieselbe "
        "Datei wie id",
        "",
    ),
    "aehnlichkeit": (
        "Skalarprodukt der normierten Dokumentvektoren (Mittel der ersten drei Stücke), auf vier "
        "Stellen gerundet; je id fallend",
        "-1 bis 1",
    ),
}


# --- Wo es erscheint ---------------------------------------------------------------------------
def similar_enabled(settings: Settings) -> bool:
    """Die Schritte sind an, und das Profil nennt das Nachbarpaket (Plan § 10: nur die Hauptperiode)."""
    return settings.embeddings.enabled and bool(settings.embeddings.neighbors_package)


def has_rows(path: Path) -> bool:
    """Ob die Nachbartabelle da ist und eine Zeile hat; ohne Paketkopie ist sie leer."""
    return path.is_file() and int(pl.scan_parquet(path).select(pl.len()).collect().item()) > 0


def table_shown(path: Path, settings: Settings) -> bool:
    """``PublishedTable.shown``: nur gemessen und mit Zeilen."""
    return measured(settings, NEIGHBORS_CHECK.project) and has_rows(path)


def dialog_shown(layout: Layout, settings: Settings) -> bool:
    """``DialogHook.shown``: wie der Download, an derselben Tabelle."""
    from georep.enrich.embeddings import embedding_files

    return table_shown(embedding_files(layout).neighbors, settings)


# --- Der Satz ----------------------------------------------------------------------------------
def similar_check_files(settings: Settings) -> tuple[Path, ...]:
    """``guete.json`` und ``stichprobe.json`` der Kodierung im Repo: Eingaben von ``report``."""
    return check_files(settings, NEIGHBORS_CHECK)


def alpha_sufficient(settings: Settings) -> bool:
    """``alpha_genuegt`` der Frage in ``guete.json``; ohne Feld ist es ein ``SchemaError``."""
    path = settings.validation.root / NEIGHBORS_CHECK.project / QUALITY
    quality: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    try:
        return bool(quality["fragen"][QUESTION]["alpha_genuegt"])
    except (KeyError, TypeError) as error:
        raise SchemaError(f"{path}: Feld fehlt ({error})") from error


def similar_sentence(settings: Settings, *, dialog: bool) -> str:
    """Der Satz unter der Liste im Dialog (``dialog``) oder unter den Downloads.

    Was die Vorschläge sind und mit welchem Modell (Lizenz, Quelle), die Präzision@5 mit Intervall
    nach Wilson nur bei genügendem α, der Satz aus ``guete.json`` (``Quality.text``: mit der
    Schlichtung, wenn sie dasselbe Modell war) und der Datensatz, an dem allein geprüft ist.
    ``SchemaError``, wenn ``guete.json`` eine andere Kodierung beschreibt als ``NEIGHBORS_CHECK``.
    """
    from georep.report.model import format_de

    quality = read_quality(settings, NEIGHBORS_CHECK)
    what = (
        f"je Dokument die {'fünf' if dialog else 'zehn'} mit der ähnlichsten Einbettung von "
        "Titel und Text"
        + ("" if dialog else " (die ersten fünf stehen im Dokumentdialog)")
        + f", gerechnet mit dem Modell {MEASURED_MODEL} (Lizenz {MODEL_LICENSE}, Quelle "
        f"{MODEL_SOURCE})."
    )
    if alpha_sufficient(settings):
        (measure,) = NEIGHBORS_CHECK.measures
        share, low, high = measure.bounds()
        checked = (
            f" Von den ersten fünf betrafen {measure.hits} von {measure.units} Vorschlägen zu "
            f"{ANCHORS} Dokumenten dieselbe Sache oder dasselbe Thema ({measure.label} "
            f"{format_de(share, 3)}, 95-%-Intervall nach Wilson {format_de(low, 3)}–"
            f"{format_de(high, 3)}), {quality.text()}."
        )
    else:
        checked = (
            f" {capitalized(quality.text())}; die beiden stimmen zu wenig überein, darum steht "
            "hier keine Zahl zur Güte."
        )
    scope = f" Geprüft nur an {settings.city.name}, {settings.period.title}."
    if dialog:
        return f"{DIALOG_TITLE}: {what}{checked}{scope}"
    return f"{capitalized(what)}{checked}{scope}"


def table_sentence(settings: Settings) -> str:
    """``TableCheck.sentence`` des Downloads."""
    return similar_sentence(settings, dialog=False)


# --- Die Zeilen des Hakens ---------------------------------------------------------------------
def dialog_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Was ``report`` für ``data/aehnlich.json`` liest: Nachbarn, Korpus, Kodierung."""
    from georep.enrich.embeddings import embedding_files

    return (embedding_files(layout).neighbors, layout.corpus, *similar_check_files(settings))


def dialog_rows(layout: Layout, settings: Settings) -> DialogRows:
    """``DialogHook.rows``: je Dokument die ersten ``IN_DIALOG`` Nachbarn nach Rang, mit ihren Zielen.

    Ein Ziel trägt Link (https), Datum, Drucksache und den Titel, wie ``dokumente.json`` sie
    schreibt; ``dialog_payload`` nimmt davon nur, was dort nicht steht. Das eine Wort ist leer: der
    Titel des Hakens sagt, was die Einträge sind. Ohne Zeilen bleibt auch der Satz leer.
    """
    from georep.enrich.embeddings import embedding_files

    table = (
        pl.read_parquet(embedding_files(layout).neighbors, columns=["id", "rang", "nachbar"])
        .filter(pl.col("rang") <= IN_DIALOG)
        .sort("id", "rang")
    )
    if table.is_empty():
        return DialogRows(labels=(), rows={})
    wanted = table.get_column("nachbar").unique().to_list()
    corpus = pl.read_parquet(
        layout.corpus, columns=["id", "reference", "name", "date", "download_url"]
    ).filter(pl.col("id").is_in(wanted))
    targets = {
        str(row["id"]): DialogTarget(
            listed_link(row["download_url"] or "", ""),
            row["date"],
            str(row["reference"] or ""),
            str(row["name"] or ""),
        )
        for row in corpus.iter_rows(named=True)
    }
    grouped = table.group_by("id", maintain_order=True).agg(pl.col("nachbar"))
    # ``bootstrap`` übernimmt das Paket nur, wenn jeder Nachbar ein Paper ist; ein unbekanntes Ziel
    # fiele trotzdem weg, statt ohne Drucksache dazustehen
    rows = {
        str(doc_id): tuple((0, str(n)) for n in neighbours if n in targets)
        for doc_id, neighbours in grouped.iter_rows()
    }
    return DialogRows(
        labels=("",),
        rows=rows,
        targets=targets,
        note=similar_sentence(settings, dialog=True),
    )
