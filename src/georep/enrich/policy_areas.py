"""Beitrag von Vorhaben 19: Politikfelder nach dem Comparative Agendas Project (CAP), Weg 3b.

Messdokument ``docs/plans/19-politikfelder.md``, § 5, § 6 und § 10. Das Urteil ist Weg 3b, ein
Klassifikator (``xlm-roberta-large``, feinjustiert auf den menschlich kodierten deutschen CAP-Daten
und auf Silberlabels des lokalen Sprachmodells für 4 200 Ratsdokumente). Er braucht torch, und torch
kommt nie ins Paket (Plan § 2.8, ``uv.lock``). Darum hat das Vorhaben zwei Teile:

1. **Die Vorhersage läuft außerhalb des Pakets.** ``georep policy-areas export <profil>`` schreibt je
   Profil die Eingabe des Klassifikators (``classifier_input``): je Korpus-ID der Titel und die
   ersten ``policy_areas.chars`` Zeichen des Rohtexts von Fundament F1, Leerraum zusammengezogen,
   genau wie ``schreibe_eingabe()`` des Messskripts (ein Test hält beide bytegleich). Das
   Trainingsskript ``docs/plans/19-politikfelder-training.py --vorhersage <eingabe>`` sagt daraus im
   Trainings-Venv unter der GPU-Sperre vorher.
2. **Im Paket nur das Ergebnis**: ``georep pack --policy-areas --from <datei>`` friert es je Profil
   ein, ``bootstrap`` kopiert es, und der Beitrag reicht es geprüft weiter (unten).

Die Pfade gehören diesem Modul (Synergien 2026-11, § 2.1): wer die Tabellen liest, nimmt sie aus
``policy_area_files``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

import deal
import polars as pl

from georep.contracts import one_row_per_document
from georep.errors import MissingInputError, SchemaError
from georep.layout import Layout
from georep.settings import POLICY_AREA_CODES, Settings

POLICY_AREAS_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen der Tabellen ändern
INPUT_SCHEMA_VERSION = 1  # die Eingabe des Klassifikators (``georep policy-areas export``)
INPUT_SCHEMA = {"id": pl.String, "text": pl.String, "mit_text": pl.Boolean, "gekuerzt": pl.Boolean}

CODES = POLICY_AREA_CODES  # die 21 Hauptthemen des CAP-Master-Codebuchs und 99
NO_AREA = "99"  # kein Politikfeld erkennbar: eine Entscheidung des Klassifikators
UNDETERMINED = ""  # ohne Rohtext: keine Vorhersage
SOURCE = "klassifikator"  # ``quelle`` von Weg 3b (Weg 1 hieße ``llm``, die Einigkeitsregel ``einigkeit``)
# Die Namen der Optionen im Codebuch (``validierung/19-politikfelder/codebuch.toml``, Fassung
# 2026-11-23.1; ein Test hält beide gleich) und Kurznamen für Tabellenköpfe. Stadtneutral: die
# Hauptthemen sind die des CAP, ihre kommunale Abbildung steht im Codebuch.
NAMES: dict[str, str] = {
    "1": "Wirtschaft und Finanzen allgemein (Makroökonomie)",
    "2": "Bürgerrechte, Gleichstellung, Antidiskriminierung",
    "3": "Gesundheit und Pflege",
    "4": "Landwirtschaft, Ernährung, Tierschutz",
    "5": "Arbeit und Beschäftigung",
    "6": "Bildung und Schule",
    "7": "Umwelt und Klima",
    "8": "Energie",
    "9": "Migration und Integration",
    "10": "Verkehr",
    "12": "Recht, Ordnung und Kriminalität",
    "13": "Soziales, Kinder, Jugend, Sport",
    "14": "Wohnen und Stadtentwicklung",
    "15": "Wirtschaft, Handel, Tourismus, Bevölkerungsschutz",
    "16": "Verteidigung und Zivilschutz",
    "17": "Wissenschaft, Technik, Kommunikation",
    "18": "Außenhandel und internationale Wirtschaft",
    "19": "Internationales und Europa",
    "20": "Staat und Verwaltung",
    "21": "Öffentliche Flächen, Grün und Wasser",
    "23": "Kultur",
    "99": "kein Politikfeld erkennbar",
}
SHORT_NAMES: dict[str, str] = {
    "1": "Haushalt und Finanzen",
    "2": "Bürgerrechte",
    "3": "Gesundheit",
    "4": "Landwirtschaft",
    "5": "Arbeit",
    "6": "Bildung",
    "7": "Umwelt",
    "8": "Energie",
    "9": "Migration",
    "10": "Verkehr",
    "12": "Ordnung",
    "13": "Soziales",
    "14": "Wohnen",
    "15": "Wirtschaft",
    "16": "Verteidigung",
    "17": "Technik",
    "18": "Außenhandel",
    "19": "Internationales",
    "20": "Verwaltung",
    "21": "Flächen",
    "23": "Kultur",
    "99": "kein Feld",
}
AREAS_SCHEMA = {
    "id": pl.String,
    "politikfeld": pl.String,
    "quelle": pl.String,
    "modell": pl.String,
    "prompt": pl.String,
    "wahrscheinlichkeit": pl.Float64,
    "abgeschnitten": pl.Boolean,
}
EXAMPLES = 3  # so viele IDs nennt eine Meldung


class PolicyAreaFiles(NamedTuple):
    package: Path  # die Kopie des Pakets, die ``bootstrap`` anlegt
    areas: Path  # ``politikfelder.parquet``: eine Zeile je Korpus-ID, geprüft
    shares: Path  # ``politikfelder_anteile.parquet``: Anteile je Gremiumsart


def policy_area_files(layout: Layout) -> PolicyAreaFiles:
    """Das Paket unter ``raw/``, die beiden Tabellen unter ``processed/``."""
    return PolicyAreaFiles(
        layout.raw / "politikfelder_paket.parquet",
        layout.processed / "politikfelder.parquet",
        layout.processed / "politikfelder_anteile.parquet",
    )


def _examples(values: Sequence[str]) -> str:
    shown = ", ".join(repr(v) for v in sorted(values)[:EXAMPLES])
    return f"{len(values)}, etwa {shown}" if values else "0"


@deal.raises(SchemaError)
@deal.ensure(
    lambda frame, corpus_ids, model, result: one_row_per_document(result, corpus_ids),
    message="eine Zeile je Korpus-ID, nach id sortiert",
)
def check_areas(frame: pl.DataFrame, corpus_ids: Sequence[str], model: str) -> pl.DataFrame:
    """Das Paket gegen den Korpus prüfen und nach ``id`` sortiert zurückgeben.

    ``SchemaError``, wenn Spalten oder Typen andere sind als ``AREAS_SCHEMA``, eine ID doppelt
    steht, eine Korpus-ID fehlt oder das Paket eine fremde trägt, ein Code nicht aus ``CODES`` ist,
    eine Zeile eine andere Kennung als ``model`` oder eine andere Quelle als ``SOURCE`` nennt, oder
    eine Zeile nur halb leer ist: ohne Rohtext sind Feld, Quelle und Modell leer und
    Wahrscheinlichkeit und ``abgeschnitten`` fehlen, mit Feld ist alles gesetzt und die
    Wahrscheinlichkeit liegt in (0, 1]. Jede Meldung nennt Zahl und Beispiele.
    """
    if dict(frame.schema) != AREAS_SCHEMA:
        raise SchemaError(f"Politikfelder: Spalten {dict(frame.schema)}, erwartet {AREAS_SCHEMA}")
    ids = frame.get_column("id")
    twice = ids.filter(ids.is_duplicated()).unique().to_list()
    if twice:
        raise SchemaError(f"Politikfelder: IDs doppelt: {_examples(twice)}")
    known = set(corpus_ids)
    found = set(ids.to_list())
    missing, foreign = sorted(known - found), sorted(found - known)
    if missing or foreign:
        raise SchemaError(
            f"Politikfelder passen nicht zum Korpus: es fehlen {_examples(missing)}; "
            f"fremd sind {_examples(foreign)}"
        )
    codes = set(frame.get_column("politikfeld").unique().to_list()) - {*CODES, UNDETERMINED}
    if codes:
        raise SchemaError(f"Politikfelder: fremde Codes {sorted(codes)}; erlaubt sind {CODES}")
    filled = pl.col("politikfeld") != UNDETERMINED
    wrong = frame.filter(
        pl.when(filled)
        .then(
            (pl.col("quelle") != SOURCE)
            | (pl.col("modell") != model)
            | (pl.col("prompt") != "")
            | pl.col("abgeschnitten").is_null()
            | pl.col("wahrscheinlichkeit").is_null()
            | ~pl.col("wahrscheinlichkeit").is_between(0.0, 1.0, closed="right")
        )
        .otherwise(
            (pl.col("quelle") != "")
            | (pl.col("modell") != "")
            | (pl.col("prompt") != "")
            | pl.col("abgeschnitten").is_not_null()
            | pl.col("wahrscheinlichkeit").is_not_null()
        )
    )
    if wrong.height:
        raise SchemaError(
            f"Politikfelder: Zeilen mit anderer Quelle oder Kennung als {SOURCE}/{model} oder "
            f"halb leer: {_examples(wrong.get_column('id').to_list())}"
        )
    return frame.sort("id")


def export_path(layout: Layout) -> Path:
    """Wohin ``georep policy-areas export`` ohne ``--out`` schreibt: neben die Messdateien des Profils."""
    return layout.root / "messung" / "19-politikfelder-eingabe.parquet"


def _one_input_per_document(
    corpus: pl.DataFrame, raw: pl.DataFrame, chars: int, result: pl.DataFrame
) -> bool:
    return one_row_per_document(result, corpus.get_column("id").to_list()) and dict(
        result.schema
    ) == dict(INPUT_SCHEMA)


@deal.pre(lambda corpus, raw, chars: chars >= 1, message="chars mindestens 1")
@deal.ensure(_one_input_per_document, message="eine Eingabe je Korpus-ID, im Schema der Eingabe")
def classifier_input(corpus: pl.DataFrame, raw: pl.DataFrame, chars: int) -> pl.DataFrame:
    """Die Eingabe des Klassifikators je Korpus-ID, nach ``id`` sortiert.

    ``corpus`` trägt ``id``, ``name`` (Titel) und ``file_name``, ``raw`` den Rohtextstore von F1
    (``name`` ist der Dateiname, ``text`` der Rohtext). ``text`` ist Titel, Zeilenumbruch und die
    ersten ``chars`` Zeichen des Rohtexts, an jedem Leerraum getrennt und mit einem Leerzeichen
    verbunden, wie ``schreibe_eingabe()`` des Messskripts (``" ".join(...split())``, also mit dem
    Leerraum, den Python kennt, nicht dem von Polars). ``mit_text`` sagt, ob der Rohtext mehr als
    Leerraum trägt: nur dann sagt das Trainingsskript ein Feld voraus, sonst bliebe ein Titel ohne
    Text, an dem nichts geprüft ist. ``gekuerzt`` sagt, ob der Rohtext länger als ``chars`` ist.
    Ein Dokument, dessen Datei der Store nicht kennt, hat leeren Rohtext.
    """
    texts = dict(
        zip(raw.get_column("name").to_list(), raw.get_column("text").to_list(), strict=True)
    )
    rows = []
    for doc, title, file_name in corpus.select("id", "name", "file_name").sort("id").iter_rows():
        text = (texts.get(file_name) or "") if file_name is not None else ""
        rows.append(
            (
                doc,
                " ".join(f"{title or ''}\n{text[:chars]}".split()),
                bool(text.strip()),
                len(text) > chars,
            )
        )
    return pl.DataFrame(rows, schema=INPUT_SCHEMA, orient="row")


@deal.raises(MissingInputError)
def export_input(layout: Layout, settings: Settings) -> pl.DataFrame:
    """Die Eingabe dieses Profils aus Korpus und Rohtextstore (F1, ``Layout.raw_texts``)."""
    for path, how in (
        (layout.corpus, "`georep run corpus` baut den Korpus"),
        (layout.raw_texts, "`georep run raw_texts` liest ihn aus den PDFs (Fundament F1)"),
    ):
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; {how}")
    corpus = pl.read_parquet(layout.corpus, columns=["id", "name", "file_name"])
    raw = pl.read_parquet(layout.raw_texts, columns=["name", "text"])
    return classifier_input(corpus, raw, settings.policy_areas.chars)
