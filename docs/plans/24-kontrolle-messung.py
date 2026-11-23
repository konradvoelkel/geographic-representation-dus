"""Rechnet die Zahlen von `24-kontrolle.md` nach (Vorhaben 24 „Anfragen als Kontrolle in der Kooperation").

    uv run python docs/plans/24-kontrolle-messung.py [--stichprobe] [--sim N]

Liest nur, was `georep run` je Düsseldorfer Profil schreibt (`interim/papers.parquet`,
`processed/papers_gremien.parquet`, `processed/dokumente_urheber.parquet`; Pfade aus
`georep --profile <p> paths`) und den Rohtext aus Phase 0 (`$GEOREP_MESSDATEN/rohtext/`, Groß- und
Kleinschreibung, Zeilen), der die Kopffelder der Vorlagen („Fachbereich:", „Amt / Institut:") trägt.

Die Tabelle der Dezernate (welche Person führt welches Dezernat mit welchen Ämtern, seit wann, und
welche Fraktion sie vorgeschlagen hat) steht unten als `DEZERNATE` und `INHABER`, mit Quelle; die
Rohquellen liegen lokal unter `/media/konrad/xtraspace/georep/fremddaten/dezernate/` (README mit
SHA-256). Stufe 2 legt beides ins Stadtprofil.

Was das Skript rechnet (Messdokument § 3):

1. die Anfragen der drei Perioden mit Urheber, Gremium und Zeitfenster der Kooperation;
2. die Kopffelder der Verwaltungsvorlagen (Amt), daraus das Amtsverzeichnis und die Gegenprobe der
   Tabelle `DEZERNATE` (stimmt das Amt im Kopf mit dem Dezernat der Tabelle zum Datum überein?);
3. vier Wege der Zuordnung Anfrage → Dezernat (Antwort als eigene Drucksache, Fachausschuss, Amt im
   Text, Klassifikator Text → Amt) mit Abdeckung je Weg und Übereinstimmung der Wege untereinander;
4. Fallzahl je Fraktion × Dezernat × Halbjahr für die vorab festgelegte Prüfung (§ 8), **ohne** die
   Zellen nach Partner und eigen zu trennen;
5. die Teststärke des vorab festgelegten Modells durch Simulation (`--sim`, Wiederholungen je
   Effektgröße, Standard 400).

Mit `--stichprobe` schreibt es die geschichtete Stichprobe von 100 Anfragen nach
`validierung/24-kontrolle/stichprobe.csv` (nur IDs und Schicht) und die Kodieraufgaben ohne die
Ausgabe des Verfahrens nach `$GEOREP_MESSDATEN/kodierung/24-kontrolle/aufgaben.jsonl` (nie ins Repo),
dazu leere Antwortdateien für zwei Kodierer. Ohne den Schalter prüft es nur, ob die gespeicherte
Stichprobe noch dieselbe ist. Das Codebuch (`validierung/24-kontrolle/codebuch.toml`) ist von Hand
geschrieben und wird nur gelesen.

Die Hypothese H1 wird **nicht** gerechnet (Messdokument § 8: erst nach der Validierung der
Zuordnung). Laufzeit rund zwei Minuten mit 400 Wiederholungen je Effektgröße.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

os.environ.setdefault("POLARS_MAX_THREADS", "4")
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
ROHTEXT = MESSDATEN / "rohtext"
KODIERUNG = MESSDATEN / "kodierung" / "24-kontrolle"
AUFGABEN = KODIERUNG / "aufgaben.jsonl"
STICHPROBE = REPO / "validierung" / "24-kontrolle" / "stichprobe.csv"
CODEBUCH = REPO / "validierung" / "24-kontrolle" / "codebuch.toml"
SEED = 24
TEXTANFANG = 3000  # Zeichen Rohtext je Kodieraufgabe

# Die drei Düsseldorfer Datensätze: (Profil, Name der Periode)
PROFILE = (
    ("duesseldorf-2014", "2014-2020"),
    ("duesseldorf", "2020-2025"),
    ("duesseldorf-2025", "2025-"),
)

# --- Profil (Stufe 2: Stadtprofil, Block [oversight]) --------------------------------------------
# Ratsmehrheit je Periode (Belege: 15-funktion.md, § 3.9) und das Kalenderhalbjahr, ab dem sie als
# Kooperation gilt (Messdokument § 8: das Halbjahr der Vereinbarung). Schlüssel wie `parteien`.
MEHRHEIT: dict[str, tuple[tuple[str, ...], str]] = {
    "2014-2020": (("SPD", "GRUENE", "FDP"), "2014-2"),
    "2020-2025": (("CDU", "GRUENE"), "2021-1"),
    "2025-": (("CDU", "GRUENE"), "2025-2"),
}
# Fraktionen aus mehreren Parteien: ab 2020 SPD/Volt, ab 2025 Freie Wähler/Tierschutz/PARTEI (15, § 3.7).
FRAKTION_AB: dict[str, dict[str, str]] = {
    "2014-2020": {},
    "2020-2025": {"VOLT": "SPD"},
    "2025-": {"VOLT": "SPD", "PARTEI": "T_FW"},
}

# Wer ein Dezernat führt (Regel aus § 8, in dieser Reihenfolge): belegter Vorschlag einer Fraktion,
# Vorschlagsrecht der Kooperationsvereinbarung, belegte Parteimitgliedschaft, sonst keine.
# Quelle: fremddaten/dezernate/beigeordnete.tsv und README (Abruf 2026-11-23).
INHABER: dict[str, tuple[str | None, str]] = {
    "Elbers": ("CDU", "Partei des OB"),
    "Geisel": ("SPD", "Partei des OB"),
    "Keller (OB)": ("CDU", "Partei des OB"),
    "Keller": ("CDU", "Mitgliedschaft"),
    "Abrahams": ("CDU", "Mitgliedschaft (nur Presseüberschrift)"),
    "Bonin": ("CDU", "Mitgliedschaft (nur Presseüberschrift)"),
    "Meyer-Falcke": ("FDP", "Vorschlag"),
    "Hintzsche": ("SPD", "Mitgliedschaft"),
    "Stulgies": ("GRUENE", "Vorschlag"),
    "Lohe": ("CDU", "Mitgliedschaft"),
    "Schneider": ("SPD", "Vorschlag"),
    "Zuschke": (None, "nicht belegt (Vorschlag des OB 2016)"),
    "Zaum": ("CDU", "Vorschlag"),
    "Rauterkus": ("CDU", "Vorschlagsrecht Kooperation 2021"),
    "Kral": ("GRUENE", "Vorschlagsrecht Kooperation 2021"),
    "Koch": ("GRUENE", "Vorschlagsrecht Kooperation 2021"),
    "Zur": ("FDP", "Vorschlagsrecht Kooperation 2021"),
    "Wagner": ("CDU", "Vorschlagsrecht Kooperation 2021 (Dezernat 04)"),
    "Beyer": (None, "gemeinsamer Vorschlag CDU und Grüne"),
    "vakant": (None, "vakant, Vertretung"),
}

# Dezernat, Inhaber, gültig von (einschließlich) bis (ausschließlich), Ämter. Aus den
# Dezernatsverteilungsplänen 01.02.2018, 01.07.2021, 01.08.2022, 01.10.2023, 01.09.2024, 01.01.2026,
# den Vorstandsseiten 2014 bis 2016 und den Wahlvorlagen im Datensatz (RAT/323/2021, RAT/326/2021,
# RAT/116/2022, RAT/119/2022, RAT/295/2023). Die Nummern 01 bis 09 gab es vor 2017 nicht; sie stehen
# hier für dieselben Bereiche. Umbaudaten ohne Beleg: 2017-06 (66 zu 03, 33 zu 04, 64 zu 07).
DEZERNATE: tuple[tuple[str, str, str, str | None, tuple[str, ...]], ...] = (
    ("01", "Elbers", "2014-01-01", "2014-09-01", ("01", "13", "80")),
    ("01", "Geisel", "2014-09-01", "2020-11-01", ("01", "13", "80")),
    ("01", "Keller (OB)", "2020-11-01", "2021-07-01", ("01", "13", "80")),
    ("01", "Keller (OB)", "2021-07-01", None, ("01", "13")),
    ("02", "Abrahams", "2014-01-01", "2015-10-01", ("02", "20", "21", "22", "67")),
    ("02", "vakant", "2015-10-01", "2015-11-01", ("02", "20", "21", "22", "67")),
    ("02", "Schneider", "2015-11-01", "2016-05-01", ("02", "20", "21", "22", "67")),
    ("02", "Schneider", "2016-05-01", "2026-01-01", ("02", "20", "21", "22", "23", "67")),
    ("02", "Schneider", "2026-01-01", "2026-10-01", ("02", "20", "21", "22", "23", "67", "69")),
    ("02", "Schneider", "2026-10-01", None, ("02", "20", "21", "22")),
    ("03", "Bonin", "2014-01-01", "2015-12-01", ("03", "23", "60", "61", "62", "63", "65")),
    ("03", "vakant", "2015-12-01", "2016-05-01", ("03", "23", "60", "61", "62", "63", "65")),
    ("03", "vakant", "2016-05-01", "2016-09-01", ("03", "60", "61", "62", "63", "65")),
    ("03", "Zuschke", "2016-09-01", "2017-06-01", ("03", "60", "61", "62", "63", "65")),
    ("03", "Zuschke", "2017-06-01", "2021-07-01", ("03", "61", "62", "63", "65", "66")),
    ("03", "Zuschke", "2021-07-01", "2026-01-01", ("03", "61", "62", "63", "64", "65")),
    ("03", "Zuschke", "2026-01-01", "2026-10-01", ("03", "61", "62", "63", "64", "65", "66")),
    ("03", "Zuschke", "2026-10-01", None, ("03", "61", "62", "63", "64", "65")),
    ("04", "Meyer-Falcke", "2014-01-01", "2017-06-01", ("04", "10", "11", "16", "53")),
    ("04", "Meyer-Falcke", "2017-06-01", "2020-09-01", ("04", "10", "11", "16", "33", "53")),
    ("04", "vakant", "2020-09-01", "2021-07-01", ("04", "10", "11", "16", "33", "53")),
    ("04", "Rauterkus", "2021-07-01", "2022-08-01", ("04", "10", "16", "33", "80")),
    ("04", "Rauterkus", "2022-08-01", "2023-04-01", ("04", "10", "16", "80")),
    ("04", "vakant", "2023-04-01", "2023-08-01", ("04", "10", "16", "80")),
    ("04", "vakant", "2023-08-01", "2023-10-01", ("04", "10", "16")),
    ("04", "Wagner", "2023-10-01", "2024-09-01", ("04", "10", "16")),
    ("04", "Wagner", "2024-09-01", None, ("04", "10", "16", "33")),
    ("05", "Kral", "2021-07-01", "2022-06-01", ("05", "66", "69")),
    ("05", "Kral", "2022-06-01", "2026-01-01", ("05", "19", "39", "66", "68", "69")),
    ("05", "Kral", "2026-01-01", None, ("05", "19", "68")),
    ("06", "Hintzsche", "2014-01-01", "2017-06-01", ("06", "40", "50", "51", "52", "54", "64")),
    ("06", "Hintzsche", "2017-06-01", "2022-05-01", ("06", "40", "50", "51", "52", "54")),
    ("06", "Hintzsche", "2022-05-01", "2022-08-01", ("06", "40", "50", "51", "52")),
    ("06", "Hintzsche", "2022-08-01", "2024-09-01", ("06", "40", "50", "51")),
    ("06", "Hintzsche", "2024-09-01", None, ("06", "37", "40", "50", "51", "52")),
    ("07", "Keller", "2014-01-01", "2017-01-01", ("07", "12", "30", "32", "33", "66")),
    ("07", "vakant", "2017-01-01", "2017-06-01", ("07", "12", "30", "32", "33", "66")),
    ("07", "Zaum", "2017-06-01", "2021-07-01", ("07", "12", "30", "32", "64")),
    ("07", "Zaum", "2021-07-01", "2023-08-01", ("07", "12", "30", "32", "37", "53")),
    ("07", "Zaum", "2023-08-01", "2024-09-01", ("07", "12", "30", "37", "53", "80")),
    ("07", "Zaum", "2024-09-01", "2026-01-01", ("07", "12", "30", "32", "53", "80")),
    ("07", "Zaum", "2026-01-01", None, ("07", "12", "30", "32", "80")),
    ("08", "Stulgies", "2014-01-01", "2021-07-01", ("08", "19", "37", "39", "68")),
    ("08", "Stulgies", "2021-07-01", "2022-06-01", ("08", "19", "39", "68")),
    ("08", "Zur", "2022-08-01", "2023-08-01", ("08", "33", "52")),
    ("08", "Zur", "2023-08-01", "2024-07-01", ("08", "32", "33", "52")),
    ("08", "vakant", "2024-07-01", "2024-09-01", ("08", "32", "33", "52")),
    ("09", "Lohe", "2014-01-01", "2017-06-01", ("09", "41")),
    ("09", "Lohe", "2017-06-01", "2022-05-01", ("09", "41", "40/603", "40/604")),
    ("09", "Koch", "2022-05-01", "2026-01-01", ("09", "41", "40/603", "40/604", "54")),
    ("09", "Koch", "2026-01-01", None, ("09", "41", "40/603", "40/604", "53", "54")),
    ("IN", "Beyer", "2026-10-01", None, ("23", "66", "67", "69")),
)

# Für das Codebuch: neutrale Bezeichnung ohne Person und ohne Zeitangaben; was ein Dezernat am Datum
# umfasst, sagt allein die Liste seiner Ämter.
BEZEICHNUNG: dict[str, str] = {
    "01": "Oberbürgermeister",
    "02": "Kämmerin bzw. Kämmerer (Finanzen)",
    "IN": "Infrastruktur",
}

AMT_NAMEN: dict[str, str] = {
    "01": "Büro Oberbürgermeister, Ratsangelegenheiten, Bezirksverwaltungsstellen, Gleichstellung",
    "02": "Bauinvestitionscontrolling",
    "03": "Integrierte Stadt- und Verkehrsplanung",
    "04": "Arbeitssicherheit, Digitalisierungsbeauftragter",
    "05": "Schienengebundener Personennahverkehr",
    "06": "Kompetenzzentrum Großveranstaltungen",
    "07": "Compliance, Regionale Angelegenheiten",
    "08": "Dezernatsbüro Umwelt",
    "09": "Dezernatsbüro Kultur",
    "10": "Hauptamt",
    "11": "Personalamt",
    "12": "Amt für Statistik und Wahlen",
    "13": "Amt für Kommunikation",
    "16": "Amt für Zentrale Dienste",
    "19": "Amt für Umwelt- und Verbraucherschutz",
    "20": "Kämmerei",
    "21": "Stadtkasse",
    "22": "Steueramt",
    "23": "Amt für Gebäudemanagement",
    "30": "Rechtsamt",
    "32": "Ordnungsamt",
    "33": "Amt für Einwohnerwesen (Bürgerservice)",
    "37": "Feuerwehr, Rettungsdienst und Bevölkerungsschutz",
    "39": "Amt für Verbraucherschutz",
    "40": "Amt für Schule und Bildung",
    "40/603": "Volkshochschule",
    "40/604": "Clara-Schumann-Musikschule",
    "41": "Kulturamt und Kulturinstitute",
    "50": "Amt für Soziales",
    "51": "Jugendamt",
    "52": "Sportamt",
    "53": "Gesundheitsamt",
    "54": "Amt für Migration und Integration",
    "60": "Bauverwaltungsamt",
    "61": "Stadtplanungsamt",
    "62": "Vermessungs- und Katasteramt",
    "63": "Bauaufsichtsamt",
    "64": "Amt für Wohnungswesen",
    "65": "Liegenschaftsamt",
    "66": "Amt für Verkehrsmanagement",
    "67": "Stadtentwässerungsbetrieb",
    "68": "Garten-, Friedhofs- und Forstamt",
    "69": "Amt für Brücken-, Tunnel- und Stadtbahnbau",
    "80": "Wirtschaftsförderung",
}

# Wie eine Anfrage ein Amt beim Namen nennt (kleingeschrieben; Wortanfang). Nur eindeutige Namen; die
# Feuerwehr steht nicht darin, weil Anfragen sie als Gegenstand nennen, nicht als Adressaten.
AMT_MUSTER: dict[str, str] = {
    "12": r"amt für statistik und wahlen|wahlamt",
    "19": r"umweltamt|amt für umwelt- und verbraucherschutz|amt für umweltschutz",
    "20": r"kämmerei",
    "22": r"steueramt",
    "23": r"amt für gebäudemanagement|gebäudemanagement \(igm\)|\bigm\b",
    "30": r"rechtsamt",
    "32": r"ordnungsamt|ordnungs- und servicedienst|\bosd\b",
    "33": r"amt für einwohnerwesen|bürgerbüro|bürgerservice",
    "40": r"schulverwaltungsamt|amt für schule und bildung",
    "40/603": r"volkshochschule|\bvhs\b",
    "41": r"kulturamt",
    "50": r"sozialamt|amt für soziales",
    "51": r"jugendamt",
    "52": r"sportamt",
    "53": r"gesundheitsamt",
    "54": r"amt für migration und integration",
    "61": r"stadtplanungsamt",
    "62": r"vermessungs- und katasteramt|katasteramt",
    "63": r"bauaufsichtsamt|bauaufsicht",
    "64": r"wohnungsamt|amt für wohnungswesen",
    "65": r"liegenschaftsamt",
    "66": r"amt für verkehrsmanagement|verkehrsmanagement",
    "67": r"stadtentwässerung",
    "68": r"gartenamt|garten-, friedhofs- und forstamt|friedhofsamt|forstamt",
    "69": r"amt für brücken-, tunnel- und stadtbahnbau|brücken-, tunnel- und stadtbahnbau",
    "80": r"wirtschaftsförderung",
}

ROLLEN_ANFRAGE = ("anfrage", "zanfrage")


# --- Laden ---------------------------------------------------------------------------------------
def paths(profile: str) -> dict[str, str]:
    """Pfade eines Profils aus `georep paths`, nie von Hand."""
    out = subprocess.run(
        ["uv", "run", "georep", "--profile", profile, "paths"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def art(paper_type: str | None, name: str | None) -> str:
    """Rolle einer Drucksache, wie Vorhaben 14 (`art()`), hier nur die drei, die 24 braucht."""
    t = (paper_type or "").strip()
    n = (name or "").lower()
    low = t.lower()
    if low.startswith(ROLLEN_ANFRAGE):
        return "anfrage"
    if t == "Vorlage aus der Politik":
        if "anfrage" in n and "antrag" not in n:
            return "anfrage"
        return "politik"
    if low.startswith(("antrag", "zantrag", "haushaltsantrag")):
        return "antrag"
    if "informationsvorlage" in low or "berichtsvorlage" in low:
        return "information"
    if "beschlussvorlage" in low or t == "Verwaltungsvorlage" or "beratungsvorlage" in low:
        return "vorlage"
    return "sonst"


def lade() -> pl.DataFrame:
    """Alle Dokumente der drei Perioden mit Rolle, Gremium, Urheber und Rohtext."""
    frames = []
    for profile, periode in PROFILE:
        p = paths(profile)
        root, processed = Path(p["root"]), Path(p["processed"])
        docs = pl.read_parquet(root / "interim" / "papers.parquet").select(
            "id", "reference", "date", "paper_type", "name", "file_name", "text"
        )
        gremien = pl.read_parquet(processed / "papers_gremien.parquet").select(
            "id", "gremium", "gremium_art"
        )
        urheber = pl.read_parquet(processed / "dokumente_urheber.parquet").select(
            "id", "urheber_art", "parteien"
        )
        roh = pl.read_parquet(ROHTEXT / f"{root.name}.parquet").select(
            pl.col("name").alias("file_name"), pl.col("text").alias("roh")
        )
        df = (
            docs.join(gremien, on="id", how="left")
            .join(urheber, on="id", how="left")
            .join(roh, on="file_name", how="left")
            .with_columns(pl.lit(periode).alias("periode"))
            .sort("id")
        )
        frames.append(df)
    df = pl.concat(frames)
    rollen = [
        art(t, n) for t, n in zip(df["paper_type"].to_list(), df["name"].to_list(), strict=True)
    ]
    return df.with_columns(pl.Series("rolle", rollen)).sort("periode", "id")


# --- Dezernatstabelle ----------------------------------------------------------------------------
def _d(s: str | None) -> date:
    return date.fromisoformat(s) if s else date(2099, 1, 1)


def pruefe_tabelle() -> None:
    """Kein Amt in zwei Dezernaten zugleich, kein Inhaber ohne Eintrag in INHABER."""
    for nr, wer, von, bis, aemter in DEZERNATE:
        assert wer in INHABER, wer
        assert _d(von) < _d(bis), (nr, wer)
        for nr2, wer2, von2, bis2, aemter2 in DEZERNATE:
            if (nr, wer, von) == (nr2, wer2, von2):
                continue
            if _d(von) < _d(bis2) and _d(von2) < _d(bis):
                doppelt = set(aemter) & set(aemter2)
                assert not doppelt, (nr, wer, von, nr2, wer2, von2, doppelt)


def amt_norm(code: str | None) -> str | None:
    """'01/13' -> '01', '41/205' -> '41', '40/603' bleibt, '02/BIC' -> '02'."""
    if not code:
        return None
    if code.startswith("40/60"):
        return code
    return code[:2]


def dezernat_am(amt: str | None, tag: date) -> tuple[str, str] | None:
    """(Dezernat, Inhaber) für ein Amt an einem Tag, oder None, wenn das Amt in keiner Zeile steht."""
    if amt is None:
        return None
    for nr, wer, von, bis, aemter in DEZERNATE:
        if amt in aemter and _d(von) <= tag < _d(bis):
            return nr, wer
    return None


def einheiten_am(tag: date) -> list[tuple[str, str]]:
    return sorted({(nr, wer) for nr, wer, von, bis, _ in DEZERNATE if _d(von) <= tag < _d(bis)})


def halbjahr(tag: date) -> str:
    return f"{tag.year}-{1 if tag.month <= 6 else 2}"


def halbjahr_tage(hj: str) -> tuple[date, date]:
    j, h = int(hj[:4]), int(hj[-1])
    return (date(j, 1, 1), date(j, 7, 1)) if h == 1 else (date(j, 7, 1), date(j + 1, 1, 1))


def einheiten_im_halbjahr(hj: str) -> list[tuple[str, str]]:
    a, b = halbjahr_tage(hj)
    return sorted({(nr, wer) for nr, wer, von, bis, _ in DEZERNATE if _d(von) < b and a < _d(bis)})


def fuehrt(einheit: tuple[str, str]) -> str | None:
    return INHABER[einheit[1]][0]


# --- Kopffelder der Vorlagen ---------------------------------------------------------------------
KOPF_AMT = re.compile(
    r"(?:Fachbereich|Amt\s*/\s*Institut)\s*:\s*\n?\s*(\d{2}(?:/[0-9A-Z]{1,4})?)\b"
)
KOPF_ENDE = re.compile(
    r"\n\s*(Beschlussdarstellung|Sachdarstellung|Beschlussentwurf|Beschlussvorschlag)\s*:"
)


def kopf_amt(roh: str | None) -> str | None:
    if not roh:
        return None
    m = KOPF_AMT.search(roh[:2000])
    return amt_norm(m.group(1)) if m else None


def rumpf(roh: str | None) -> str:
    """Text einer Vorlage ohne den Kopf (Fachbereich, Dezernent, Beratungsfolge), höchstens 4 000 Zeichen."""
    if not roh:
        return ""
    m = KOPF_ENDE.search(roh)
    t = roh[m.start() :] if m else "\n".join(roh.splitlines()[15:])
    return t[:4000]


# --- Wege der Zuordnung --------------------------------------------------------------------------
NUMMER_NEU = re.compile(r"\b([A-ZÄÖÜ]{2,6}\d{0,2})\s*/\s*0*(\d{1,4})\s*/\s*((?:19|20)\d{2})\b")
NUMMER_ALT = re.compile(r"\b(\d{2,3})\s*/\s*0*(\d{1,4})\s*/\s*((?:19|20)\d{2})\b")


def schluessel(ref: str) -> str:
    """Drucksachennummer ohne Leerzeichen und führende Nullen der laufenden Nummer."""
    m = NUMMER_NEU.fullmatch(ref.strip()) or NUMMER_ALT.fullmatch(ref.strip())
    if not m:
        return ref.replace(" ", "")
    return f"{m.group(1)}/{int(m.group(2))}/{m.group(3)}"


def weg_antwort(df: pl.DataFrame, anfragen: pl.DataFrame) -> dict[str, tuple[str, str]]:
    """Anfrage-ID -> (Amt, Nummer der Antwort) aus einer späteren Vorlage der Verwaltung mit Kopf,
    deren Titel oder Textanfang die Nummer der Anfrage nennt (eigene Drucksache als Antwort, 14 § 3.6)."""
    nach_nummer: dict[str, list[tuple[str, date]]] = defaultdict(list)
    for i, ref, d in anfragen.select("id", "reference", "date").iter_rows():
        nach_nummer[schluessel(ref)].append((i, d))
    kand = df.filter((pl.col("rolle") == "information") & pl.col("amt_kopf").is_not_null())
    out: dict[str, tuple[str, str]] = {}
    for ref, d, name, roh, amt in kand.select(
        "reference", "date", "name", "roh", "amt_kopf"
    ).iter_rows():
        hay = (name or "") + "\n" + (roh or "")[:2500]
        for rx in (NUMMER_NEU, NUMMER_ALT):
            for m in rx.finditer(hay):
                k = f"{m.group(1)}/{int(m.group(2))}/{m.group(3)}"
                if k == schluessel(ref):
                    continue
                for aid, ad in nach_nummer.get(k, []):
                    if ad <= d <= date(ad.year + 2, ad.month, min(ad.day, 28)) and aid not in out:
                        out[aid] = (amt, ref)
    return out


def ausschuss_aemter(df: pl.DataFrame) -> dict[tuple[str, str], Counter[str]]:
    """(Periode, Ausschuss) -> Ämter der Vorlagen mit Kopf, die dieser Ausschuss beraten hat
    (Gremium aus der Drucksachennummer oder der Folge, Punkte 23, 57, 58)."""
    out: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    v = df.filter(
        pl.col("rolle").is_in(["information", "vorlage"])
        & pl.col("amt_kopf").is_not_null()
        & (pl.col("gremium_art") == "ausschuss")
    )
    for per, g, amt in v.select("periode", "gremium", "amt_kopf").iter_rows():
        out[(per, g)][amt] += 1
    return out


def weg_ausschuss(
    row: dict[str, Any], tabelle: dict[tuple[str, str], Counter[str]], schwelle: float = 0.8
) -> tuple[tuple[str, str] | None, float]:
    """Dezernat des Fachausschusses, in dem die Anfrage gestellt ist: Anteil der Vorlagen dieses
    Ausschusses (Periode), deren Amt zum Datum der Anfrage in einem Dezernat liegt; zugeordnet ab
    `schwelle`. In 2014-2020 zählt auch der Amtskopf der alten Nummer (die Geschäftsführung)."""
    kopf = NUMMER_ALT.fullmatch((row["reference"] or "").strip())
    if kopf and kopf.group(1) in AMT_NAMEN and kopf.group(1) != "01":
        e0 = dezernat_am(kopf.group(1), row["date"])
        if e0 is not None:
            return e0, 1.0
    if row["gremium_art"] != "ausschuss":
        return None, 0.0
    c = tabelle.get((row["periode"], row["gremium"]))
    if not c:
        return None, 0.0
    dz: Counter[tuple[str, str]] = Counter()
    for amt, n in c.items():
        e = dezernat_am(amt, row["date"])
        if e is not None:
            dz[e] += n
    if not dz:
        return None, 0.0
    e, n = dz.most_common(1)[0]
    anteil = n / sum(dz.values())
    return (e if anteil >= schwelle else None), anteil


AMT_RX = {amt: re.compile(rf"(?:^|[^a-zäöüß])(?:{rx})") for amt, rx in AMT_MUSTER.items()}
AMT_NUMMER = re.compile(r"\bamt\s+(\d{2})\b")


def weg_amt_im_text(row: dict[str, Any]) -> tuple[tuple[str, str] | None, set[tuple[str, str]]]:
    """Dezernat aus Ämtern, die Titel oder Text der Anfrage beim Namen oder als „Amt 66" nennen;
    zugeordnet nur, wenn alle genannten Ämter in einem Dezernat liegen."""
    hay = ((row["name"] or "") + " " + (row["text"] or "")).lower()
    aemter = {amt for amt, rx in AMT_RX.items() if rx.search(hay)}
    aemter |= {m.group(1) for m in AMT_NUMMER.finditer(hay) if m.group(1) in AMT_NAMEN}
    dz = {e for a in aemter if (e := dezernat_am(a, row["date"])) is not None}
    return (next(iter(dz)) if len(dz) == 1 else None), dz


def textform(name: str | None, roh: str | None, klein: str | None) -> str:
    t = roh if roh else (klein or "")
    return ((name or "") + " \n " + (name or "") + " \n " + t[:4000]).lower()


def klassifikator(df: pl.DataFrame) -> tuple[TfidfVectorizer, LogisticRegression, dict[str, float]]:
    """Text -> Amt, trainiert an den Vorlagen der Verwaltung mit Kopf (ohne den Kopf); Kreuzprüfung
    über die Perioden: je eine Periode Test, die anderen Training, Treffer auf Ebene Dezernat."""
    v = df.filter(
        pl.col("rolle").is_in(["information", "vorlage"]) & pl.col("amt_kopf").is_not_null()
    )
    v = v.filter(pl.col("amt_kopf").is_in(list(AMT_NAMEN)))
    texte = [
        ((n or "") + " \n " + (n or "") + " \n " + rumpf(r)).lower()
        for n, r in zip(v["name"].to_list(), v["roh"].to_list(), strict=True)
    ]
    y = v["amt_kopf"].to_list()
    per = v["periode"].to_list()
    tage = v["date"].to_list()
    guete: dict[str, float] = {}
    for test in ("2014-2020", "2020-2025", "2025-"):
        tr = [i for i, p in enumerate(per) if p != test]
        te = [i for i, p in enumerate(per) if p == test]
        vec = TfidfVectorizer(
            sublinear_tf=True, min_df=3, max_df=0.5, ngram_range=(1, 2), max_features=80_000
        )
        xtr = vec.fit_transform([texte[i] for i in tr])
        clf = LogisticRegression(max_iter=1000, C=5.0)
        clf.fit(xtr, [y[i] for i in tr])
        pr = clf.predict(vec.transform([texte[i] for i in te]))
        ok = sum(
            1
            for i, p in zip(te, pr, strict=True)
            if dezernat_am(p, tage[i]) == dezernat_am(y[i], tage[i])
        )
        guete[test] = ok / len(te)
        guete[test + " n"] = len(te)
    vec = TfidfVectorizer(
        sublinear_tf=True, min_df=3, max_df=0.5, ngram_range=(1, 2), max_features=80_000
    )
    x = vec.fit_transform(texte)
    clf = LogisticRegression(max_iter=1000, C=5.0)
    clf.fit(x, y)
    guete["training n"] = len(y)
    return vec, clf, guete


def weg_klassifikator(
    texte: list[str], tage: list[date], vec: TfidfVectorizer, clf: LogisticRegression
) -> list[tuple[tuple[str, str] | None, float]]:
    """Wahrscheinlichkeit je Amt, summiert auf das Dezernat zum Datum; das wahrscheinlichste mit p."""
    proba = clf.predict_proba(vec.transform(texte))
    klassen = list(clf.classes_)
    out = []
    for row, tag in zip(proba, tage, strict=True):
        dz: dict[tuple[str, str], float] = defaultdict(float)
        for k, p in zip(klassen, row, strict=True):
            e = dezernat_am(k, tag)
            if e is not None:
                dz[e] += float(p)
        if not dz:
            out.append((None, 0.0))
            continue
        e, p = max(dz.items(), key=lambda kv: kv[1])
        out.append((e, p))
    return out


# --- Hilfen --------------------------------------------------------------------------------------
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / d, (c + r) / d


def pct(a: int, b: int) -> str:
    return f"{a} von {b} ({100 * a / b:.1f} %)" if b else f"{a} von 0"


def titel(s: str) -> None:
    print(f"\n=== {s} ===")


# --- Poisson mit festen Effekten (das vorab festgelegte Modell, § 8) ----------------------------
def codes(g: np.ndarray) -> np.ndarray:
    """Gruppenschlüssel als ganze Zahlen 0..k-1."""
    return np.unique(g, return_inverse=True)[1]


def ohne_leere_gruppen(y: np.ndarray, gruppen: list[np.ndarray]) -> np.ndarray:
    """Maske der Zellen, deren Gruppen (je Art) mindestens eine Anfrage haben; iteriert bis stabil
    (eine Gruppe nur aus Nullen hat ihren festen Effekt bei minus unendlich und trägt nichts bei)."""
    m = np.ones(len(y), dtype=bool)
    cs = [codes(g) for g in gruppen]
    while True:
        neu = m.copy()
        for c in cs:
            summe = np.bincount(c, weights=y * m, minlength=c.max() + 1)
            neu &= summe[c] > 0
        if (neu == m).all():
            return m
        m = neu


def bloecke(c1: np.ndarray, c2: np.ndarray, n1: int, n2: int) -> int:
    """Zahl der Zusammenhangskomponenten des zweiteiligen Graphen Gruppe 1 – Gruppe 2."""
    eltern = list(range(n1 + n2))

    def wurzel(i: int) -> int:
        while eltern[i] != i:
            eltern[i] = eltern[eltern[i]]
            i = eltern[i]
        return i

    for a, b in zip(c1.tolist(), (c2 + n1).tolist(), strict=True):
        ra, rb = wurzel(a), wurzel(b)
        if ra != rb:
            eltern[ra] = rb
    return len({wurzel(i) for i in range(n1 + n2)})


def ppml(
    y: np.ndarray, g1: np.ndarray, g2: np.ndarray, x: np.ndarray | None = None, tol: float = 1e-10
) -> tuple[np.ndarray, float | None, float | None, float]:
    """Poisson-Pseudo-Maximum-Likelihood mit zwei Arten fester Effekte und einem Regressor.

    Für festes β lösen abwechselnde Projektionen (iteratives proportionales Anpassen) die festen
    Effekte exakt; β folgt mit Newton-Schritten auf der Profil-Likelihood, die Information aus dem
    mit μ gewichteten, von beiden Effekten bereinigten x (Frisch-Waugh). Standardfehler quasi-Poisson:
    φ = Pearson-χ² / (n - p), mindestens 1. Gibt (μ, β, se, φ) zurück; ohne x nur μ und φ."""
    c1, c2 = codes(g1), codes(g2)
    n1, n2 = c1.max() + 1, c2.max() + 1
    sy1 = np.bincount(c1, y, n1)
    sy2 = np.bincount(c2, y, n2)
    a, c, b = np.zeros(n1), np.zeros(n2), 0.0
    info = float("nan")
    for _ in range(200):
        xb = b * x if x is not None else 0.0
        for _ in range(5000):
            a_neu = np.log(sy1) - np.log(np.bincount(c1, np.exp(c[c2] + xb), n1))
            c_neu = np.log(sy2) - np.log(np.bincount(c2, np.exp(a_neu[c1] + xb), n2))
            d = max(np.abs(a_neu - a).max(), np.abs(c_neu - c).max())
            a, c = a_neu, c_neu
            if d < tol:
                break
        mu = np.exp(a[c1] + c[c2] + xb)
        if x is None:
            break
        xt = x.astype(float).copy()
        w1, w2 = np.bincount(c1, mu, n1), np.bincount(c2, mu, n2)
        for _ in range(5000):
            m1 = np.bincount(c1, mu * xt, n1) / w1
            xt -= m1[c1]
            m2 = np.bincount(c2, mu * xt, n2) / w2
            xt -= m2[c2]
            if max(np.abs(m1).max(), np.abs(m2).max()) < 1e-12:
                break
        info = float(np.sum(mu * xt * xt))
        schritt = float(np.sum(x * (y - mu))) / info
        b += schritt
        if abs(schritt) < 1e-9:
            break
    # Freiheitsgrade: je zusammenhängendem Block der beiden Effektarten (hier je Halbjahr) ist ein
    # Effekt nicht identifiziert; der Rang der Dummy-Matrix ist n1 + n2 - Zahl der Blöcke.
    n, p = len(y), n1 + n2 - bloecke(c1, c2, n1, n2) + (1 if x is not None else 0)
    phi = max(1.0, float(np.sum((y - mu) ** 2 / np.maximum(mu, 1e-12))) / max(n - p, 1))
    if x is None:
        return mu, None, None, phi
    return mu, b, math.sqrt(phi / info), phi


def poisson_dummies(
    y: np.ndarray, g1: np.ndarray, g2: np.ndarray, x: np.ndarray
) -> tuple[float, float]:
    """Dasselbe Modell mit ausgeschriebenen Dummies und IRLS (nur zur Gegenprobe von `ppml`)."""
    spalten = [(g1 == w).astype(float) for w in np.unique(g1)]
    spalten += [(g2 == w).astype(float) for w in np.unique(g2)[1:]]
    spalten.append(x.astype(float))
    X = np.column_stack(spalten)
    mu = np.maximum(y, 0.5)
    eta = np.log(mu)
    for _ in range(100):
        z = eta + (y - mu) / mu
        sw = np.sqrt(mu)
        bb, *_ = np.linalg.lstsq(X * sw[:, None], z * sw, rcond=None)
        eta_neu = np.clip(X @ bb, -30, 30)
        if np.max(np.abs(eta_neu - eta)) < 1e-10:
            eta = eta_neu
            break
        eta = eta_neu
        mu = np.exp(eta)
    mu = np.exp(eta)
    p = np.linalg.matrix_rank(X)
    phi = max(1.0, float(np.sum((y - mu) ** 2 / mu)) / (len(y) - p))
    cov = np.linalg.pinv((X * mu[:, None]).T @ X)
    return float(bb[-1]), math.sqrt(phi * cov[-1, -1])


# --- Hauptteil -----------------------------------------------------------------------------------
def main() -> None:  # noqa: C901, PLR0912, PLR0915
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--stichprobe", action="store_true", help="Stichprobe und Kodieraufgaben schreiben"
    )
    ap.add_argument(
        "--sim", type=int, default=400, help="Wiederholungen je Effektgröße (Teststärke)"
    )
    args = ap.parse_args()
    t0 = time.time()
    pruefe_tabelle()

    titel("1 Daten")
    df = lade()
    df = df.with_columns(pl.Series("amt_kopf", [kopf_amt(r) for r in df["roh"].to_list()]))
    for per in ("2014-2020", "2020-2025", "2025-"):
        d = df.filter(pl.col("periode") == per)
        print(
            f"{per}: {d.height} Dokumente, {d.filter(pl.col('roh').is_not_null()).height} mit Rohtext, "
            f"{d.filter(pl.col('rolle') == 'anfrage').height} Anfragen, "
            f"{d.filter(pl.col('amt_kopf').is_not_null()).height} mit Amt im Kopf"
        )

    titel("2 Gegenprobe der Dezernatstabelle an den Kopffeldern")
    # Amt im Kopf -> liegt es zum Datum in einem Dezernat der Tabelle? Und nennt das Feld
    # „Dezernentin / Dezernent" dieselbe Person? (Name nur zum Vergleich, nicht gespeichert.)
    kopf_dez = re.compile(r"Dezernent(?:in)?(?:\s*/\s*Dezernent(?:in)?)?\s*:\s*\n?\s*([^\n]{2,90})")
    namen = [w for w in INHABER if w not in ("vakant", "Keller (OB)")]
    gleich = anders = ohne = 0
    beispiele: Counter[tuple[str, str, str]] = Counter()
    for roh, amt, tag in (
        df.filter(pl.col("amt_kopf").is_not_null()).select("roh", "amt_kopf", "date").iter_rows()
    ):
        e = dezernat_am(amt, tag)
        m = kopf_dez.search(roh[:2000])
        if e is None or m is None:
            ohne += 1
            continue
        feld = m.group(1).replace(" ", "")
        wer = next((n for n in namen if n.replace(" ", "") in feld), None)
        if wer == "Keller" and "Oberbürgermeister" in feld:
            wer = "Keller (OB)"
        if wer is None:
            ohne += 1
            continue
        if wer == e[1] or (e[1] == "vakant"):
            gleich += 1
        else:
            anders += 1
            beispiele[(amt, e[1], wer)] += 1
    print(
        f"Kopf mit Amt und Dezernent: Tabelle = Kopf {pct(gleich, gleich + anders)}; ohne Vergleich {ohne}"
    )
    print("häufigste Abweichungen (Amt, Tabelle, Kopf):", beispiele.most_common(12))
    # Plan 01.01.2026 gegen Vorstandsseite Januar 2026: wer steht 2026-01 bis 2026-09 im Kopf von Amt 66?
    wer66: Counter[str] = Counter()
    for (roh,) in (
        df.filter(
            (pl.col("amt_kopf") == "66")
            & pl.col("date").is_between(date(2026, 1, 1), date(2026, 9, 30))
        )
        .select("roh")
        .iter_rows()
    ):
        m = kopf_dez.search(roh[:2000])
        feld = m.group(1).replace(" ", "") if m else ""
        wer66[next((n for n in namen if n.replace(" ", "") in feld), "unbekannt")] += 1
    print("Amt 66 im Kopf, 2026-01 bis 2026-09:", dict(wer66))

    titel("3 Anfragen und Zeitfenster")
    anf = df.filter(pl.col("rolle") == "anfrage")
    zeilen = []
    for row in anf.iter_rows(named=True):
        per = row["periode"]
        umbenennen = FRAKTION_AB[per]
        frak = (
            sorted({umbenennen.get(p, p) for p in (row["parteien"] or [])})
            if row["urheber_art"] == "Fraktion"
            else []
        )
        mehrheit, ab = MEHRHEIT[per]
        hj = halbjahr(row["date"])
        im_fenster = hj >= ab
        stadt = row["gremium_art"] in ("rat", "ausschuss") or (
            per == "2014-2020" and row["gremium_art"] == "unbekannt"
        )
        zeilen.append(
            {**row, "fraktionen": frak, "halbjahr": hj, "fenster": im_fenster, "stadtebene": stadt}
        )
    anf = pl.DataFrame(zeilen, infer_schema_length=None)
    for per in ("2014-2020", "2020-2025", "2025-"):
        a = anf.filter(pl.col("periode") == per)
        h1 = a.filter(
            pl.col("stadtebene") & pl.col("fenster") & (pl.col("fraktionen").list.len() > 0)
        )
        print(
            f"{per}: Anfragen {a.height}; davon Rat/Ausschuss {a.filter(pl.col('stadtebene')).height}, "
            f"Bezirksvertretung {a.filter(pl.col('gremium_art') == 'bezirksvertretung').height}, "
            f"Beirat {a.filter(pl.col('gremium_art') == 'beirat').height}; "
            f"von Fraktionen, Stadtebene, im Fenster: {h1.height} "
            f"(gemeinsam: {h1.filter(pl.col('fraktionen').list.len() > 1).height})"
        )

    titel("4 Wege der Zuordnung")
    antwort = weg_antwort(df, anf)
    tab_aus = ausschuss_aemter(df)
    vec, clf, guete = klassifikator(df)
    print(
        "Klassifikator Text -> Amt, an Vorlagen mit Kopf; Treffer auf Ebene Dezernat, je Periode als Test: "
        + ", ".join(f"{k} {v:.3f}" if v < 1 else f"{k} {int(v)}" for k, v in guete.items())
    )
    texte = [
        textform(n, r, k)
        for n, r, k in zip(
            anf["name"].to_list(), anf["roh"].to_list(), anf["text"].to_list(), strict=True
        )
    ]
    klass = weg_klassifikator(texte, anf["date"].to_list(), vec, clf)
    erg = []
    for row, (k_e, k_p) in zip(anf.iter_rows(named=True), klass, strict=True):
        a_amt = antwort.get(row["id"])
        a_e = dezernat_am(a_amt[0], row["date"]) if a_amt else None
        g_e, g_anteil = weg_ausschuss(row, tab_aus)
        t_e, t_alle = weg_amt_im_text(row)
        if a_e is not None:
            weg, e = "antwort", a_e
        elif g_e is not None:
            weg, e = "ausschuss", g_e
        elif t_e is not None:
            weg, e = "amt_im_text", t_e
        elif k_e is not None and k_p >= 0.3:
            weg = (
                "klass_hoch" if k_p >= 0.7 else ("klass_mittel" if k_p >= 0.5 else "klass_niedrig")
            )
            e = k_e
        else:
            weg, e = "keins", None
        erg.append(
            {
                "id": row["id"],
                "weg": weg,
                "dezernat": e[0] if e else None,
                "inhaber": e[1] if e else None,
                "antwort": "|".join(a_e) if a_e else None,
                "ausschuss": "|".join(g_e) if g_e else None,
                "ausschuss_anteil": g_anteil,
                "amt_text": "|".join(t_e) if t_e else None,
                "amt_text_n": len(t_alle),
                "klass": "|".join(k_e) if k_e else None,
                "klass_p": k_p,
            }
        )
    zu = anf.join(pl.DataFrame(erg, infer_schema_length=None), on="id", how="left")
    h1pop = zu.filter(
        pl.col("stadtebene") & pl.col("fenster") & (pl.col("fraktionen").list.len() > 0)
    )
    bvpop = zu.filter(
        (pl.col("gremium_art") == "bezirksvertretung")
        & pl.col("fenster")
        & (pl.col("fraktionen").list.len() > 0)
    )
    for name, pop in (("Rat und Ausschüsse (H1)", h1pop), ("Bezirksvertretungen (R2)", bvpop)):
        print(f"\n{name}: {pop.height} Anfragen")
        for per in ("2014-2020", "2020-2025", "2025-", None):
            a = pop if per is None else pop.filter(pl.col("periode") == per)
            c = Counter(a["weg"].to_list())
            print(
                f"  {per or 'zusammen'} (n={a.height}): "
                + ", ".join(
                    f"{w} {c.get(w, 0)}"
                    for w in (
                        "antwort",
                        "ausschuss",
                        "amt_im_text",
                        "klass_hoch",
                        "klass_mittel",
                        "klass_niedrig",
                        "keins",
                    )
                )
                + f"; zugeordnet {pct(a.height - c.get('keins', 0), a.height)}"
            )
        # Abdeckung je Weg für sich (nicht nach Vorrang)
        print(
            "  je Weg für sich: "
            f"Antwort {pct(pop.filter(pl.col('antwort').is_not_null()).height, pop.height)}, "
            f"Fachausschuss {pct(pop.filter(pl.col('ausschuss').is_not_null()).height, pop.height)}, "
            f"Amt im Text {pct(pop.filter(pl.col('amt_text').is_not_null()).height, pop.height)} "
            f"(mehrere Dezernate: {pop.filter(pl.col('amt_text_n') > 1).height}), "
            f"Klassifikator p>=0,5 {pct(pop.filter(pl.col('klass_p') >= 0.5).height, pop.height)}, "
            f">=0,7 {pct(pop.filter(pl.col('klass_p') >= 0.7).height, pop.height)}, "
            f">=0,3 {pct(pop.filter(pl.col('klass_p') >= 0.3).height, pop.height)}"
        )
    print(
        "\n  Fachausschüsse: Anteil des häufigsten Dezernats an den Vorlagen (Periode, Ausschuss, n, Anteil):"
    )
    for (per, g), c in sorted(tab_aus.items()):
        n = sum(c.values())
        if n >= 20:
            e, anteil = weg_ausschuss(
                {
                    "periode": per,
                    "gremium": g,
                    "gremium_art": "ausschuss",
                    "date": date(2023, 1, 1)
                    if per == "2020-2025"
                    else (date(2017, 1, 1) if per == "2014-2020" else date(2026, 3, 1)),
                    "reference": "",
                },
                tab_aus,
            )
            print(f"    {per} {g}: n {n}, {anteil:.2f}{' -> ' + e[0] if e else ''}")
    amt_zaehl: Counter[str] = Counter()
    for row in h1pop.filter(pl.col("weg") == "amt_im_text").iter_rows(named=True):
        hay = ((row["name"] or "") + " " + (row["text"] or "")).lower()
        amt_zaehl.update(a for a, rx in AMT_RX.items() if rx.search(hay))
    print("  Amt im Text, genannte Ämter (H1, Weg amt_im_text):", dict(amt_zaehl.most_common()))
    titel(
        "4b Übereinstimmung der Wege untereinander (Rat und Ausschüsse, alle Anfragen mit Fraktion)"
    )
    alle = zu.filter(pl.col("stadtebene") & (pl.col("fraktionen").list.len() > 0))
    for a, b in (
        ("antwort", "klass"),
        ("ausschuss", "klass"),
        ("amt_text", "klass"),
        ("antwort", "ausschuss"),
        ("antwort", "amt_text"),
        ("ausschuss", "amt_text"),
    ):
        beide = alle.filter(pl.col(a).is_not_null() & pl.col(b).is_not_null())
        gl = beide.filter(
            pl.col(a).str.split("|").list.first() == pl.col(b).str.split("|").list.first()
        ).height
        lo, hi = wilson(gl, beide.height)
        print(f"  {a} = {b} (Dezernat): {pct(gl, beide.height)}, Wilson {lo:.3f}–{hi:.3f}")
    for schwelle in (0.5, 0.6, 0.7, 0.8, 0.9):
        ref = alle.filter(
            (pl.col("antwort").is_not_null() | pl.col("ausschuss").is_not_null())
            & (pl.col("klass_p") >= schwelle)
        )
        refd = ref.with_columns(
            pl.coalesce("antwort", "ausschuss").str.split("|").list.first().alias("r")
        )
        gl = refd.filter(pl.col("r") == pl.col("klass").str.split("|").list.first()).height
        print(
            f"  Klassifikator ab p {schwelle}: gegen Antwort/Fachausschuss {pct(gl, refd.height)}"
        )

    titel("5 Fallzahl je Fraktion × Dezernat × Halbjahr (H1-Stichprobe, ohne Trennung nach Status)")
    zellen, y, gf, gd, partner, status = aufbau_zellen(h1pop)
    print(
        f"Zellen: {len(y)}, Anfragen in Zellen (gemeinsame je Fraktion): {int(y.sum())}, Nullen {pct(int((y == 0).sum()), len(y))}"
    )
    for per in ("2014-2020", "2020-2025", "2025-"):
        m = np.array([z["periode"] == per for z in zellen])
        ident = sum(
            1 for z, mm in zip(zellen, m, strict=True) if mm and z["status"] in ("partner", "eigen")
        )
        print(
            f"  {per}: Zellen {int(m.sum())}, Anfragen {int(y[m].sum())}, Mittel je Zelle {y[m].mean():.2f}, "
            f"Halbjahre {len({z['halbjahr'] for z, mm in zip(zellen, m, strict=True) if mm})}, "
            f"Dezernatseinheiten {len({z['einheit'] for z, mm in zip(zellen, m, strict=True) if mm})}, "
            f"Zellen mit Status partner oder eigen {ident}"
        )
    je_frak: Counter[str] = Counter()
    je_dez: Counter[str] = Counter()
    for z, yy in zip(zellen, y, strict=True):
        je_frak[f"{z['periode']} {z['fraktion']}"] += int(yy)
        je_dez[f"{z['periode']} {z['einheit']}"] += int(yy)
    print("  je Fraktion:", dict(sorted(je_frak.items())))
    print("  je Dezernatseinheit:", dict(sorted(je_dez.items())))
    varianten = (
        ("alle Wege", h1pop),
        ("ohne Klassifikator unter 0,5", h1pop.filter(pl.col("weg") != "klass_niedrig")),
        (
            "Antwort, Fachausschuss, Klassifikator ab 0,7",
            h1pop.filter(pl.col("weg").is_in(["antwort", "ausschuss", "klass_hoch"])),
        ),
        (
            "nur Antwort und Fachausschuss",
            h1pop.filter(pl.col("weg").is_in(["antwort", "ausschuss"])),
        ),
    )
    for name, pop in varianten[1:]:
        _, y_s, *_ = aufbau_zellen(pop)
        print(
            f"  {name}: {int(y_s.sum())} Anfragen in Zellen, {pct(pop.height, h1pop.height)} der Grundgesamtheit"
        )

    titel("6 Teststärke (Simulation unter dem Nullmodell der Daten)")
    rng = np.random.default_rng(SEED)
    for name, pop in varianten:
        _, yv, gfv, gdv, xv, _ = aufbau_zellen(pop)
        m = ohne_leere_gruppen(yv, [gfv, gdv])
        yv, gfv, gdv, xv = yv[m], gfv[m], gdv[m], xv[m]
        mu0, _, _, phi0 = ppml(yv, gfv, gdv)
        # Überdispersion als Negativbinomial, theta aus den Momenten des Nullmodells
        r2 = float(np.sum((yv - mu0) ** 2 - mu0))
        theta = float(np.sum(mu0**2)) / r2 if r2 > 0 else 1e6
        print(
            f"{name}: {len(yv)} Zellen nach Entfernen leerer Gruppen, {int(yv.sum())} Anfragen, "
            f"{int(xv.sum())} Zellen partner, {int((xv == 0).sum())} andere oder eigen, "
            f"φ des Nullmodells {phi0:.2f}, theta {theta:.2f}"
        )
        if name == "alle Wege":
            ys = rng.poisson(mu0 * np.exp(np.log(1.5) * xv)).astype(float)
            ms = ohne_leere_gruppen(ys, [gfv, gdv])
            _, b1, s1, _ = ppml(ys[ms], gfv[ms], gdv[ms], xv[ms])
            b2, s2 = poisson_dummies(ys[ms], gfv[ms], gdv[ms], xv[ms])
            print(
                f"  Gegenprobe ppml gegen Dummies (ein simulierter Satz): beta {b1:.6f} / {b2:.6f}, se {s1:.6f} / {s2:.6f}"
            )
        ergebnis = []
        for irr in (1.0, 1.2, 1.25, 1.3, 1.4, 1.5, 2.0):
            treffer = 0
            for _ in range(args.sim):
                mu = mu0 * np.exp(np.log(irr) * xv)
                lam = rng.gamma(theta, mu / theta) if theta < 1e5 else mu
                ys = rng.poisson(lam).astype(float)
                ms = ohne_leere_gruppen(ys, [gfv, gdv])
                if ms.sum() < 10 or ys[ms][xv[ms] == 1].sum() == 0:
                    continue
                _, b, se, _ = ppml(ys[ms], gfv[ms], gdv[ms], xv[ms])
                if b is not None and se and b / se > 1.6449:
                    treffer += 1
            ergebnis.append((irr, treffer / args.sim))
        print(
            "  Teststärke (einseitig, α = 0,05): "
            + ", ".join(f"IRR {i}: {p:.2f}" for i, p in ergebnis)
        )
        mde = next((i for i, p in ergebnis if p >= 0.8), None)
        print(
            f"  kleinster IRR des Rasters mit Teststärke >= 0,8: {mde} (nach {time.time() - t0:.0f} s)"
        )
        if name != "alle Wege":
            continue
        # je Periode (Nebenrechnung R3), nur bei IRR 1,5
        perioden = np.array([g.split("|")[0] for g in gfv])
        for per in ("2014-2020", "2020-2025", "2025-"):
            mp = perioden == per
            treffer = 0
            for _ in range(args.sim):
                lam = mu0[mp] * np.exp(np.log(1.5) * xv[mp])
                ys = rng.poisson(lam).astype(float)
                ms = ohne_leere_gruppen(ys, [gfv[mp], gdv[mp]])
                if (
                    ms.sum() < 10
                    or ys[ms][xv[mp][ms] == 1].sum() == 0
                    or ys[ms][xv[mp][ms] == 0].sum() == 0
                ):
                    continue
                _, b, se, _ = ppml(ys[ms], gfv[mp][ms], gdv[mp][ms], xv[mp][ms])
                if b is not None and se and b / se > 1.6449:
                    treffer += 1
            print(
                f"  je Periode {per}: {int(mp.sum())} Zellen, {int(yv[mp].sum())} Anfragen, Teststärke bei IRR 1,5: {treffer / args.sim:.2f}"
            )

    titel("7 Stichprobe und Kodieraufgaben")
    stichprobe(h1pop, args.stichprobe)
    print(f"\nLaufzeit {time.time() - t0:.1f} s")


def aufbau_zellen(
    pop: pl.DataFrame,
) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Zellen Fraktion × Dezernatseinheit × Halbjahr für die Mehrheitsfraktionen, mit Nullen.

    Eine Halbjahr-Zelle gehört zur Periode der Mehrheit; Halbjahre, die zwei Datensätze teilen
    (2020-2, 2025-2), zählen je Datensatz für sich, weil 2020-2 zwei Mehrheiten hat."""
    zaehl: Counter[tuple[str, str, str, tuple[str, str]]] = Counter()
    for per, frak, hj, nr, wer in (
        pop.filter(pl.col("dezernat").is_not_null())
        .select("periode", "fraktionen", "halbjahr", "dezernat", "inhaber")
        .iter_rows()
    ):
        for f in frak:
            zaehl[(per, f, hj, (nr, wer))] += 1
    zellen = []
    for per in ("2014-2020", "2020-2025", "2025-"):
        mehrheit, ab = MEHRHEIT[per]
        hjs = sorted(
            {hj for p, hj in pop.select("periode", "halbjahr").iter_rows() if p == per and hj >= ab}
        )
        for hj in hjs:
            for einheit in einheiten_im_halbjahr(hj):
                for f in mehrheit:
                    fu = fuehrt(einheit)
                    st = "eigen" if fu == f else ("partner" if fu in mehrheit else "andere")
                    zellen.append(
                        {
                            "periode": per,
                            "fraktion": f,
                            "halbjahr": hj,
                            "einheit": f"{einheit[0]} {einheit[1]}",
                            "status": st,
                            "y": zaehl.get((per, f, hj, einheit), 0),
                        }
                    )
    y = np.array([z["y"] for z in zellen], dtype=float)
    gf = np.array([f"{z['periode']}|{z['fraktion']}|{z['halbjahr']}" for z in zellen])
    gd = np.array([f"{z['periode']}|{z['einheit']}|{z['halbjahr']}" for z in zellen])
    x = np.array([1.0 if z["status"] == "partner" else 0.0 for z in zellen])
    return zellen, y, gf, gd, x, [z["status"] for z in zellen]


# --- Stichprobe ----------------------------------------------------------------------------------
SCHICHTEN = {
    "antwort": 8,
    "ausschuss": 22,
    "amt_im_text": 16,
    "klass_hoch": 14,
    "klass_mittel": 14,
    "klass_niedrig": 14,
    "keins": 12,
}


def dezernatsliste(tag: date) -> list[dict[str, Any]]:
    out = []
    for nr, wer in einheiten_am(tag):
        aemter = next(
            a for n, w, v, b, a in DEZERNATE if (n, w) == (nr, wer) and _d(v) <= tag < _d(b)
        )
        out.append(
            {
                "code": nr,
                "bezeichnung": BEZEICHNUNG.get(nr, f"Dezernat {nr}")
                + (" (vakant, Vertretung)" if wer == "vakant" else ""),
                "aemter": [f"{a} {AMT_NAMEN.get(a, '')}".strip() for a in aemter],
            }
        )
    return out


def stichprobe(pop: pl.DataFrame, schreiben: bool) -> None:
    rnd = random.Random(SEED)
    gezogen: list[tuple[str, str]] = []
    for schicht, n in SCHICHTEN.items():
        ids = sorted(pop.filter(pl.col("weg") == schicht)["id"].to_list())
        k = min(n, len(ids))
        gezogen += [(i, schicht) for i in sorted(rnd.sample(ids, k))]
        print(f"  Schicht {schicht}: {k} von {len(ids)}")
    if not schreiben:
        if STICHPROBE.exists():
            alt = list(csv.reader(STICHPROBE.open()))[1:]
            print(
                "  gespeicherte Stichprobe",
                "gleich" if [tuple(r) for r in alt] == gezogen else "VERSCHIEDEN",
            )
        return
    STICHPROBE.parent.mkdir(parents=True, exist_ok=True)
    with STICHPROBE.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "schicht"])
        w.writerows(gezogen)
    KODIERUNG.mkdir(parents=True, exist_ok=True)
    zeilen = {r["id"]: r for r in pop.iter_rows(named=True)}
    # Reihenfolge der Aufgaben gemischt, damit die Schicht nicht aus der Position folgt.
    reihenfolge = [i for i, _ in gezogen]
    random.Random(SEED + 1).shuffle(reihenfolge)
    with AUFGABEN.open("w") as fh:
        for i in reihenfolge:
            r = zeilen[i]
            roh = r["roh"]
            fh.write(
                json.dumps(
                    {
                        "vorhaben": "24-kontrolle",
                        "id": i,
                        "codebuch": "2026-11-23.1",
                        "periode": r["periode"],
                        "drucksache": r["reference"],
                        "titel": r["name"],
                        "datum": r["date"].isoformat(),
                        "gremium": r["gremium"],
                        "textquelle": "rohtext" if roh else "klein",
                        "textanfang": (roh if roh else (r["text"] or ""))[:TEXTANFANG],
                        "dezernate_zum_datum": dezernatsliste(r["date"]),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    for k in ("A", "B"):
        p = KODIERUNG / f"antworten-{k}.jsonl"
        if not p.exists():
            p.write_text("")
    print(f"  geschrieben: {STICHPROBE} ({len(gezogen)}), {AUFGABEN}")


if __name__ == "__main__":
    sys.exit(main())
