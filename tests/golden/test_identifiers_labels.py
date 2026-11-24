"""Vorhaben 12 gegen seine Validierung: Präzision und Recall der gebauten Arten an den Labels.

Die Labels zweier KI-Kodierer und eines Schlichters (``validierung/12-kennungen/labels.csv``, Runde 1,
650 Aufgaben; ``labels-2.csv``, Runde 2, 410 Aufgaben; kein menschlicher Goldstandard) gegen die
Spannen, die ``identifier_spans`` aus dem Rohtextpaket der Hauptperiode baut. Die Zahlen sind die
des Messdokuments ``docs/plans/12-kennungen.md`` (§ 4.1, § 4.3, § 4.4), auf denen das Urteil in § 5
steht; ein Umbau, der eine davon ändert, ist kein Refactoring. Gerechnet wie im Messskript: eine
Präzisionsaufgabe ist richtig, wenn die Art stimmt und die Grenzen richtig sind (streng), gewichtet
mit ``schicht_n`` durch die Zahl der Aufgaben der Schicht in der Stichprobe; der Recall ungewichtet,
streng über gleiche Grenzen, ohne Tabellenbeträge.

* Bauleitplanung und Betrag (Fassung 1) an Runde 1: die Präzisionsaufgaben sind Spannen genau
  dieser Fassung und stehen alle in der Ausgabe.
* Termin und Verwaltungseinheit (Fassung 2) an Runde 2 (die Bestätigung): auch hier steht jede
  Aufgabe in der Ausgabe. Dazu an Runde 1 die Entwurfsschätzung aus § 4.3 (eine Spanne zählt für
  eine Aufgabe, wenn sie die markierte Stelle überlappt), weil nur sie den Recall der Termine misst.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest

from georep.prep.identifiers import IdentifierRules, identifier_spans, office_directory
from georep.settings import load_settings

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / "validierung" / "12-kennungen"
RAW = REPO / "snapshots" / "duesseldorf-rohtexte" / "cache" / "text" / "rohtexte.parquet"
NOWHERE = Path("/nonexistent")
ART = {
    "bplan": "1 Bauleitplanung",
    "fnp": "1 Bauleitplanung",
    "produkt": "2 Haushalt",
    "sachkonto": "2 Haushalt",
    "psp": "2 Haushalt",
    "investition": "2 Haushalt",
    "betrag": "3 Betrag",
    "termin": "4 Termin",
    "recht": "5 Rechtsgrundlage",
    "amt": "6 Verwaltungseinheit",
    "dezernat": "6 Verwaltungseinheit",
    "keine": "keine",
}


@dataclass(frozen=True)
class Round:
    tasks: dict[str, dict[str, str]]  # aufgabe -> Zeile der Stichprobe
    labels: dict[str, dict[str, object]]  # aufgabe -> frage -> Endlabel
    spans: pl.DataFrame  # die gebauten Spannen der Dokumente dieser Stichprobe


def _round(sample: str, labels: str, texts: pl.DataFrame, rules: IdentifierRules) -> Round:
    with (VALIDATION / sample).open(encoding="utf-8") as handle:
        tasks = {row["aufgabe"]: row for row in csv.DictReader(handle)}
    found: dict[str, dict[str, object]] = {}
    with (VALIDATION / labels).open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            found.setdefault(row["aufgabe"], {})[row["frage"]] = json.loads(row["label"])
    documents = pl.DataFrame(
        sorted({(row["datei"], row["datei"]) for row in tasks.values()}),
        schema={"id": pl.String(), "file_name": pl.String()},
        orient="row",
    )
    return Round(tasks, found, identifier_spans(texts, documents, rules))


@pytest.fixture(scope="module")
def built() -> tuple[Round, Round]:
    """Beide Runden, gebaut mit dem Stadtprofil und dem Ämterverzeichnis aus allen Kopffeldern."""
    settings = load_settings(cwd=NOWHERE)
    texts = pl.read_parquet(RAW, columns=["name", "text", "extractor"]).sort("name")
    rules = IdentifierRules.from_settings(settings.identifiers)
    rules = rules.with_directory(office_directory(texts.get_column("text"), rules))
    return (
        _round("stichprobe.csv", "labels.csv", texts, rules),
        _round("stichprobe-2.csv", "labels-2.csv", texts, rules),
    )


def _by_file(spans: pl.DataFrame) -> dict[str, list[tuple[int, int, str]]]:
    found: dict[str, list[tuple[int, int, str]]] = {}
    for name, start, end, kind in spans.select("id", "start", "end", "kind").iter_rows():
        found.setdefault(name, []).append((start, end, ART[kind]))
    return found


def _precision(round_: Round, art: str, *, overlap: bool = False) -> tuple[float, int]:
    """Gewichtete strenge Präzision und Zahl der Aufgaben einer Art.

    Die Quote einer Schicht zählt wie im Messskript über alle Präzisionsaufgaben der Stichprobe.
    Ohne ``overlap`` muss jede Aufgabe genau als Spanne der Ausgabe stehen; mit ``overlap`` zählt
    die gebaute Spanne, die die markierte Stelle am meisten überlappt, gegen die richtigen Grenzen
    des Labels (Entwurfsschätzung, § 4.3), und eine Aufgabe ohne überlappende Spanne entfällt.
    """
    quota = Counter(t["schicht"] for t in round_.tasks.values() if t["typ"] == "praezision")
    spans = _by_file(round_.spans)
    hits: list[tuple[bool, float]] = []
    for name, task in round_.tasks.items():
        if task["typ"] != "praezision" or task["art"] != art:
            continue
        label = round_.labels[name]
        start, end = int(task["start"]), int(task["end"])
        same_art = [s for s in spans.get(task["datei"], []) if s[2] == art]
        right_art = ART[str(label["art"])] == art
        weight = int(task["schicht_n"]) / quota[task["schicht"]]
        if not overlap:
            assert (start, end, art) in same_art, f"{name}: die Spanne fehlt in der Ausgabe"
            hits.append((right_art and label["grenzen"] == "richtig", weight))
            continue
        touching = [s for s in same_art if s[0] < end and start < s[1]]
        if not touching:
            continue
        best = max(touching, key=lambda s: min(end, s[1]) - max(start, s[0]))
        if label["art"] == "keine":
            bounds = None
        elif label["grenzen"] == "richtig":
            bounds = (start, end)
        else:
            corrected = label.get("grenzen_korrigiert")
            bounds = (int(corrected[0]), int(corrected[1])) if isinstance(corrected, list) else None
        hits.append((right_art and bounds == (best[0], best[1]), weight))
    total = sum(w for _, w in hits)
    return sum(w for ok, w in hits if ok) / total, len(hits)


def _recall(round_: Round, art: str) -> tuple[int, int]:
    """Gefundene und alle Spannen einer Art in den Recall-Dokumenten, streng, ohne Tabellenbeträge."""
    spans = _by_file(round_.spans)
    found = total = 0
    for name, task in round_.tasks.items():
        if task["typ"] != "recall":
            continue
        labelled = round_.labels[name]["spannen"]
        assert isinstance(labelled, list)
        built = {(s[0], s[1]) for s in spans.get(task["datei"], []) if s[2] == art}
        for span in labelled:
            if ART[span["art"]] != art or span["tabelle"]:
                continue
            total += 1
            found += (span["start"], span["end"]) in built
    return found, total


def test_bauleitplanung_und_betrag_an_runde_1(built: tuple[Round, Round]) -> None:
    """§ 4.1: Präzision 1,000 und 0,962 (je n 100), Recall 64/71 und 84/88."""
    first, _ = built
    precision, n = _precision(first, "1 Bauleitplanung")
    assert (round(precision, 3), n) == (1.0, 100)
    assert _recall(first, "1 Bauleitplanung") == (64, 71)
    precision, n = _precision(first, "3 Betrag")
    assert (round(precision, 3), n) == (0.962, 100)
    assert _recall(first, "3 Betrag") == (84, 88)


def test_termin_und_verwaltungseinheit_an_runde_2(built: tuple[Round, Round]) -> None:
    """§ 4.4, die Bestätigung der Fassung 2: Termin 1,000 (n 30), Verwaltungseinheit 0,956 (n 100)
    und Recall 71/80."""
    _, second = built
    precision, n = _precision(second, "4 Termin")
    assert (round(precision, 3), n) == (1.0, 30)
    precision, n = _precision(second, "6 Verwaltungseinheit")
    assert (round(precision, 3), n) == (0.956, 100)
    assert _recall(second, "6 Verwaltungseinheit") == (71, 80)


def test_termin_und_verwaltungseinheit_an_runde_1(built: tuple[Round, Round]) -> None:
    """§ 4.3, die Entwurfsschätzung der Fassung 2 an den alten Labels: Termin Präzision 1,000 und
    Recall 200/200, Verwaltungseinheit 0,976 und 51/52. Die Regeln sind an diesen Fällen
    entwickelt; die Zahlen halten fest, dass der Bau die Fassung 2 ist, nicht ihre Güte."""
    first, _ = built
    precision, _ = _precision(first, "4 Termin", overlap=True)
    assert round(precision, 3) == 1.0
    assert _recall(first, "4 Termin") == (200, 200)
    precision, _ = _precision(first, "6 Verwaltungseinheit", overlap=True)
    assert round(precision, 3) == 0.976
    assert _recall(first, "6 Verwaltungseinheit") == (51, 52)
