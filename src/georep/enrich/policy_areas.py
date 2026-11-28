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
   ein, ``bootstrap`` kopiert es nach ``raw/politikfelder_paket.parquet``, und der Schritt
   ``policy_areas`` dieses Beitrags (offline, ohne Modell) prüft es gegen den Korpus
   (``check_areas``: fehlende oder doppelte IDs, fremde Codes und eine fremde Kennung der Gewichte
   sind ein ``SchemaError``) und reicht es weiter: ``processed/politikfelder.parquet``, eine Zeile
   je Korpus-ID, und ``processed/politikfelder_anteile.parquet``, die Anteile je Gremiumsart.

Die Pfade gehören diesem Modul (Synergien 2026-11, § 2.1): wer die Tabellen liest, nimmt sie aus
``policy_area_files``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

import deal
import polars as pl

from georep.contracts import one_row_per_document
from georep.enrich import Contribution
from georep.errors import MissingInputError, SchemaError
from georep.http import Transport
from georep.io import write_parquet
from georep.layout import Layout
from georep.pipeline import Step
from georep.prep.bodies import KINDS
from georep.report.pages import Page, PageLicense
from georep.report.tables import PublishedTable, TableCheck
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


# --- Anteile je Gremiumsart -------------------------------------------------------------------------
ALL_BODIES = "alle"  # die Zeilen über alle Dokumente der Periode, vor den Gremiumsarten
SHARES_SCHEMA = {
    "periode": pl.String,
    "gremium_art": pl.String,
    "politikfeld": pl.String,
    "dokumente": pl.Int64,
    "anteil": pl.Float64,
    "anteil_mit_feld": pl.Float64,
}


def _shares_complete(
    areas: pl.DataFrame, bodies: pl.DataFrame, period: str, result: pl.DataFrame
) -> bool:
    totals = result.group_by("gremium_art").agg(pl.col("dokumente").sum())
    return dict(result.schema) == SHARES_SCHEMA and all(
        n == areas.height for kind, n in totals.iter_rows() if kind == ALL_BODIES
    )


@deal.ensure(
    _shares_complete, message="je Gremiumsart alle Codes, die Summe über alle ist der Korpus"
)
def shares_table(areas: pl.DataFrame, bodies: pl.DataFrame, period: str) -> pl.DataFrame:
    """Je Gremiumsart (``alle`` zuerst, dann ``prep.bodies.KINDS``) jedes Feld mit Zahl und Anteil.

    ``areas`` ist ``politikfelder.parquet``, ``bodies`` ``papers_gremien.parquet`` (``id``,
    ``gremium_art``); ein Dokument ohne Zeile dort zählt als ``unbekannt``. Je Gremiumsart mit
    mindestens einem Dokument stehen alle 22 Codes und die Zeile ohne Rohtext (``politikfeld``
    leer) da, auch mit null Dokumenten, damit die Tabelle zwischen Perioden vergleichbar bleibt.
    ``anteil`` teilt durch alle Dokumente der Gremiumsart, ``anteil_mit_feld`` nur durch die mit
    Feld (leer in der Zeile ohne Rohtext).
    """
    joined = (
        areas.select("id", "politikfeld")
        .join(bodies.select("id", "gremium_art"), on="id", how="left")
        .with_columns(pl.col("gremium_art").fill_null(KINDS[-1]))
        .sort("id")
    )
    order = (*CODES, UNDETERMINED)
    rows: list[tuple[str, str, str, int, float, float | None]] = []
    for kind in (ALL_BODIES, *KINDS):
        part = joined if kind == ALL_BODIES else joined.filter(pl.col("gremium_art") == kind)
        if part.is_empty():
            continue
        counts = dict(part.group_by("politikfeld").len().iter_rows())
        filled = part.height - int(counts.get(UNDETERMINED, 0))
        for code in order:
            n = int(counts.get(code, 0))
            with_area = None if code == UNDETERMINED else (n / filled if filled else 0.0)
            rows.append((period, kind, code, n, n / part.height, with_area))
    return pl.DataFrame(rows, schema=SHARES_SCHEMA, orient="row")


# --- Register: Schalter, Schritt ----------------------------------------------------------------------
def policy_areas_enabled(settings: Settings) -> bool:
    """Der Schalter des Schritts, der Tabellen und der Seite: ``policy_areas.enabled``."""
    return settings.policy_areas.enabled


def policy_areas_extra(settings: Settings) -> str:
    """Der Zusatz im Stamp (Muster Punkt 53): was den Schritt bestimmt, steht nicht im Fingerprint."""
    areas = settings.policy_areas
    payload = {"chars": areas.chars, "weights_sha256": areas.weights_sha256}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def policy_area_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Der Schritt ``policy_areas``, wenn das Profil ihn einschaltet; offline, ``http`` bleibt ungenutzt."""
    if not policy_areas_enabled(settings):
        return []
    files = policy_area_files(layout)

    def policy_areas() -> str:
        from georep.report.model import period_info

        ids = pl.read_parquet(layout.corpus, columns=["id"]).get_column("id").to_list()
        frame = check_areas(pl.read_parquet(files.package), ids, settings.policy_areas.model_id)
        write_parquet(frame, files.areas, schema_version=POLICY_AREAS_SCHEMA_VERSION)
        bodies = pl.read_parquet(layout.papers_bodies, columns=["id", "gremium_art"])
        shares = shares_table(frame, bodies, period_info(settings).title)
        write_parquet(shares, files.shares, schema_version=POLICY_AREAS_SCHEMA_VERSION)
        counts = (
            frame.filter(pl.col("politikfeld") != UNDETERMINED)
            .group_by("politikfeld")
            .len()
            .sort("len", "politikfeld", descending=[True, False])
        )
        top = ", ".join(f"{code} {SHORT_NAMES[code]} {n}" for code, n in counts.head(3).iter_rows())
        return (
            f"{frame.height} Dokumente, {counts.get_column('len').sum()} mit Politikfeld "
            f"({top}, …); {shares.height} Zeilen Anteile"
        )

    return [
        Step(
            "policy_areas",
            (files.package, layout.corpus, layout.papers_bodies),
            (files.areas, files.shares),
            policy_areas,
            POLICY_AREAS_SCHEMA_VERSION,
            extra=policy_areas_extra(settings),
        )
    ]


# --- Stufe 3 (Messdokument § 7 mit § 10): Tabellen und Seite ----------------------------------------
CC_BY_NC_SA = "https://creativecommons.org/licenses/by-nc-sa/4.0/deed.de"
LICENSE_NOTE = (
    "Lizenz CC BY-NC-SA 4.0, nicht CC0: Codes nach dem Comparative Agendas Project (CAP), "
    "German Policy Agendas Project"
)
_ID = ("OParl-URL des Dokuments", "")
_EMPTY = "; leer ohne Rohtext"


def _check_sentence(settings: Settings) -> str:
    """Der Satz unter den Downloads: Lizenz und Prüfung, aus ``guete.json`` (wie ``themen.html``)."""
    from georep.report.model import format_de, percent_de
    from georep.report.themes import read_check

    check = read_check(settings)
    where = {
        "gemessen": "an diesem Datensatz",
        # Die Auswertung nennt weder eine andere Stadt (test_second_city.py) noch das Wahljahr einer
        # anderen Periode (test_period_pipeline.py); themen.html nennt den Datensatz der Prüfung.
        "periode": "nur in einer anderen Periode derselben Stadt, für diese angenommen",
        "explorativ": "nur an einem Datensatz einer anderen Stadt, für diesen explorativ",
    }[check.status]
    return (
        f"{LICENSE_NOTE}; dasselbe gilt für politikfelder_anteile. Das Feld je Dokument sagt ein "
        f"Klassifikator voraus, {check.sentence}, {where}: Makro-F1 {format_de(check.macro_f1, 3)}, "
        f"Genauigkeit {percent_de(check.accuracy, 1)}. Mehr auf themen.html."
    )


def _check_files(settings: Settings) -> tuple[Path, ...]:
    from georep.report.themes import check_files

    return check_files(settings)


TABLES = (
    PublishedTable(
        "politikfelder",
        lambda layout: policy_area_files(layout).areas,
        f"Politikfeld je Ratsdokument nach dem CAP, von einem Klassifikator; {LICENSE_NOTE}",
        {
            "id": _ID,
            "politikfeld": (
                "Hauptthema des CAP: 1 bis 10, 12 bis 21, 23, oder 99 (kein Politikfeld erkennbar)"
                f"{_EMPTY}; die Namen nennt themen.html",
                "",
            ),
            "quelle": (f"klassifikator (Weg 3b){_EMPTY}", ""),
            "modell": (
                f"xlm-roberta-large@ und die ersten acht Ziffern des SHA-256 der Gewichte{_EMPTY}",
                "",
            ),
            "prompt": ("leer: kein Sprachmodell", ""),
            "wahrscheinlichkeit": (
                f"Softmax des gewählten Themas, auf drei Stellen{_EMPTY}",
                "Anteil 0 bis 1",
            ),
            "abgeschnitten": (
                "der Klassifikator sah nicht den ganzen Text: Rohtext über policy_areas.chars "
                f"Zeichen oder Eingabe über 256 Token{_EMPTY}",
                "",
            ),
        },
        enabled=policy_areas_enabled,
        csv=None,  # Rückstand 35: je Dokument nur Parquet
        check=TableCheck(files=_check_files, sentence=_check_sentence),
    ),
    PublishedTable(
        "politikfelder_anteile",
        lambda layout: policy_area_files(layout).shares,
        f"Anteile der Politikfelder je Gremiumsart in dieser Periode; {LICENSE_NOTE}",
        {
            "periode": ("Wahlperiode des Datensatzes", ""),
            "gremium_art": (
                "alle, dann bezirksvertretung, rat, ausschuss, beirat oder unbekannt wie in gremien",
                "",
            ),
            "politikfeld": ("Hauptthema wie in politikfelder; leer: ohne Rohtext", ""),
            "dokumente": ("Dokumente der Gremiumsart mit diesem Feld", "Dokumente"),
            "anteil": ("dokumente durch alle Dokumente der Gremiumsart", "Anteil 0 bis 1"),
            "anteil_mit_feld": (
                "dokumente durch die Dokumente der Gremiumsart mit Feld; leer in der Zeile ohne "
                "Rohtext",
                "Anteil 0 bis 1",
            ),
        },
        enabled=policy_areas_enabled,
    ),
)


def _page_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    from georep.report.themes import themes_inputs

    return themes_inputs(layout, settings)


def _page_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    from georep.report.themes import themes_data

    return themes_data(layout, settings)


def _page_links(layout: Layout, settings: Settings) -> frozenset[str]:
    from georep.report.themes import themes_links

    return themes_links(layout, settings)


PAGE = Page(
    "themen",
    "Politikfelder nach dem Comparative Agendas Project",
    "Welches Politikfeld die Ratsdokumente tragen, je Gremium, Fraktion und Wahlbezirk, neben "
    "dem Bundestag.",
    inputs=_page_inputs,
    data=_page_data,
    enabled=policy_areas_enabled,
    links=_page_links,
    license=PageLicense(
        what="Politikfelder und die Zahlen dieser Seite",
        name="CC BY-NC-SA 4.0",
        url=CC_BY_NC_SA,
        attribution="Codes nach dem Comparative Agendas Project; German Policy Agendas Project, "
        "Breunig, Guinaudeau und Schnatterer 2021",
        scope="den Politikfeldern",
        label="Themen",
    ),
)

CONTRIBUTION = Contribution(
    "19-politikfelder", steps=policy_area_steps, tables=TABLES, pages=(PAGE,)
)
