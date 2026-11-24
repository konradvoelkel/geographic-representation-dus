"""Rechnet die Zahlen von `20-kurzfassungen.md` nach (Vorhaben 20, Stufe 1: Kurzfassungen).

    uv run python docs/plans/20-kurzfassungen-messung.py                 # alle Zahlen, ohne GPU
    uv run python docs/plans/20-kurzfassungen-messung.py selbsttest      # die Treueprüfung an Beispielen
    uv run python docs/plans/20-kurzfassungen-messung.py stichprobe      # die 200 und die 50 ziehen
    flock /media/konrad/xtraspace/georep/gpu-queue/gpu.lock \\
      uv run python docs/plans/20-kurzfassungen-messung.py erzeugen --modell qwen3.6:27b --minuten 28
    uv run python docs/plans/20-kurzfassungen-messung.py massstab        # Auftrag des Maßstab-Agenten
    uv run python docs/plans/20-kurzfassungen-messung.py kodierung       # Aufträge A und B (nach dem Maßstab)
    uv run python docs/plans/20-kurzfassungen-messung.py auswertung      # nach `georep validate merge`
    flock … uv run python docs/plans/20-kurzfassungen-messung.py vorgaenge --modell gemma4  # Versuch § 3.6
    uv run python docs/plans/20-kurzfassungen-messung.py nachmessung stichprobe  # Stufe 2, § 5.4

Liest: den Rohtext der Messdatei (`messdaten/rohtext/<profil>.parquet`, pypdf 7.1.0, Groß- und
Kleinschreibung, Zeilen, Seiten mit `\\f`), den Korpus der Hauptperiode aus `data_root` (nach
`georep run`), das Regelwerk von Vorhaben 11 (`11-struktur-messung.py`, als Modul geladen) und die
Ortsnamen des Wörterbuchs (`processed/combined_searchdict.parquet`).

Schreibt ins Repo nur IDs, Codes und Zahlen (`validierung/20-kurzfassungen/`). **Kurzfassungen
kommen nie ins Repo und nie auf die Seite** (Konrad, 2026-11-23, Meta-Plan § 10, Frage 6): sie liegen
im Modellcache von F5 (`cache_root/ml/`) und als Auszug unter
`/media/konrad/xtraspace/georep/messdaten/20-kurzfassungen/`; die Aufträge an Maßstab und Kodierer
liegen unter `messdaten/kodierung/20-kurzfassungen/`.

Was vor der ersten Kurzfassung festgelegt war (Messdokument § 3.1, Commit „vorab"): Prompt Fassung 1
(`SYSTEM`, `REGELN`, `eingabe`), die Optionen aus `[ml.generation]`, die beiden Modelle, die
Treueprüfung (`angaben`, `pruefe`), das Kriterium und die Regel der Hochrechnung (`BUDGET_*`).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import ModuleType
from typing import Any

import polars as pl

from georep.layout import Layout
from georep.ml.base import GenerationOptions, GenerationUse, Reply, full_name
from georep.ml.batch import generate_texts, progress_log
from georep.ml.cache import ModelCache, input_sha256
from georep.ml.ollama import (
    OllamaGenerator,
    client_from_settings,
    generation_options,
    generator_from_settings,
)
from georep.settings import Settings, load_settings
from georep.validation.codebook import load_codebook
from georep.validation.measures import krippendorff_alpha
from georep.validation.paths import ValidationPaths
from georep.validation.sample import allocate, rank, write_sample
from georep.validation.tasks import questions, write_assignment

ROOT = Path(__file__).resolve().parents[2]
MESSDATEN = Path("/media/konrad/xtraspace/georep/messdaten")
ROHTEXT = MESSDATEN / "rohtext"
LOKAL = MESSDATEN / "20-kurzfassungen"  # Kurzfassungen, Läufe, Zuordnung: nie ins Repo
KODIERUNG = MESSDATEN / "kodierung" / "20-kurzfassungen"
VALIDIERUNG = ROOT / "validierung" / "20-kurzfassungen"
VALIDIERUNG_NACH = ROOT / "validierung" / "20-kurzfassungen-nachmessung"
KODIERUNG_NACH = MESSDATEN / "kodierung" / "20-kurzfassungen-nachmessung"
STRUKTUR = ROOT / "docs" / "plans" / "11-struktur-messung.py"
PROJEKT = "20-kurzfassungen"

# --------------------------------------------------------------------------------------------
# Vorab festgelegt (2026-11-23, vor der ersten Kurzfassung; Messdokument § 3.1)
# --------------------------------------------------------------------------------------------

PROMPT_VERSION = "20-kurzfassung-1"  # Fassung 1; Teil des Cache-Schlüssels von F5
MODELLE = ("qwen3.6:27b", "gemma4:latest")
SEED = 2026112320  # Tag der Festlegung und Nummer des Vorhabens
# Umbaurunde (Messdokument § 5.2, Frage 35: umbauen): frische 200 ohne die der ersten Runde
SEED_RUNDE2 = 2026112330
# Nachmessung in Stufe 2 (Messdokument § 5.4, Frage 20.13 und 38): frische 50 ohne die 400 beider
# Runden, Eingabe und Prompt Fassung 2 aus dem Paket (georep.enrich.summaries), nur `unbelegt`
SEED_NACHMESSUNG = 2026112420
NACHMESSUNG = "20-kurzfassungen-nachmessung"
NACHMESSUNG_N = 50
STICHPROBE = 200
KODIERT = 50
BUDGET_ZEICHEN = 8000  # Abschnittstext je Eingabe; darüber wird gekürzt (Feld gekuerzt)
LAENGE = (("kurz", 1500), ("mittel", 5000), ("lang", math.inf))  # Rohtext in Zeichen, obere Grenze
# Reihenfolge, in der die Abschnitte aus Vorhaben 11 in die Eingabe kommen und das Budget füllen;
# Kopf, Anlagen und Nachrichtlich bleiben draußen.
ABSCHNITTE = (
    ("betreff", "Betreff"),
    ("beschlussvorschlag", "Beschlussvorschlag"),
    ("fragen", "Fragen"),
    ("sachdarstellung", "Sachdarstellung"),
    ("begruendung", "Begründung"),
    ("stellungnahme", "Stellungnahme der Verwaltung"),
    ("beschlusslage", "Zitierter Beschluss"),
    ("finanzen", "Finanzen"),
    ("klima", "Klima"),
    ("alternative", "Alternative"),
)
KERN = frozenset(
    {"beschlussvorschlag", "fragen", "sachdarstellung", "begruendung", "stellungnahme"}
)

SYSTEM = (
    "Du schreibst Kurzfassungen von Dokumenten aus dem Ratsinformationssystem einer deutschen "
    "Stadt für Ratsmitglieder. Du schreibst sachlich und neutral auf Deutsch und gibst nur wieder, "
    "was im Dokument steht."
)
REGELN = """Fasse das Dokument unten in zwei bis drei Sätzen zusammen, zusammen höchstens 80 Wörter.

Regeln:
1. Der erste Satz sagt, wer was will oder mitteilt (wer beantragt, beschließen lassen will, fragt oder berichtet) und worum es geht.
2. Danach das Wesentliche: der Kern des Beschlussvorschlags, der Fragen oder der Mitteilung, dazu Ort, Betrag und Frist, wenn das Dokument sie nennt.
3. Zahlen, Beträge, Daten, Drucksachennummern und Namen nur, wenn sie im Dokument stehen, und genau so geschrieben wie dort.
4. Füge nichts hinzu, was nicht im Dokument steht: kein Wissen von außen, keine Bewertung, keine Vermutung.
5. Keine Personennamen; nenne Personen nach ihrer Rolle (etwa „die Verwaltung", „die Fraktion", „die Bezirksvertretung").
6. Antworte nur mit der Kurzfassung als Fließtext, ohne Überschrift, ohne Aufzählung, ohne Einleitung.

Dokument:

"""

# Treueprüfung: eine Kurzfassung „ohne unbelegte Angabe" hat keine Zahl, kein Datum, keine
# Drucksachennummer und keinen Eigennamen, der nicht in ihrer Eingabe steht (Definition in § 3.1).
SELTEN_ANTEIL = 0.01  # Klasse e: großgeschriebenes Wort in weniger als 1 % der Korpusdokumente
KRITERIUM_TREUE = 0.98
KRITERIUM_MEDIAN = 4
# Hochrechnung: eine Periode läuft, wenn sie mit dem gewählten Modell höchstens BUDGET_PERIODE
# GPU-Stunden braucht, in der Folge der Perioden unten, solange die Summe BUDGET_GESAMT nicht
# übersteigt; sonst nur die Auswahl (Arten mit Beschlussvorschlag oder Fragen), wenn sie passt.
BUDGET_PERIODE = 12.0
BUDGET_GESAMT = 36.0
PERIODEN = (  # Profil der Messdatei, Profilblock des Regelwerks von 11, Name
    ("2025", "duesseldorf", "laufende Periode 2025–"),
    ("duesseldorf", "duesseldorf", "Hauptperiode 2020–2025"),
    ("moenchengladbach", "moenchengladbach", "Mönchengladbach 2020–2025"),
    ("2014-2020", "duesseldorf-2014", "Periode 2014–2020"),
)
AUSWAHL_ARTEN = frozenset(
    {
        "Beschlussvorlage",
        "Bezirksvertretung Beschlussvorlage",
        "A+F Beschluss",
        "Bedarfsbeschluss",
        "Beschlussvorlage RPA",
        "Antrag",
        "Haushaltsantrag",
        "Anfrage",
    }
)

# --------------------------------------------------------------------------------------------
# Daten
# --------------------------------------------------------------------------------------------


def load_struktur() -> ModuleType:
    """Das Messskript von Vorhaben 11 als Modul, ohne seinen `main` zu starten (wie Vorhaben 16)."""
    spec = importlib.util.spec_from_file_location("struktur11", STRUKTUR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["struktur11"] = module  # dataclasses mit `from __future__ import annotations`
    spec.loader.exec_module(module)
    return module


def settings_dus() -> Settings:
    return load_settings(cwd=ROOT, profile="duesseldorf")


def korpus(settings: Settings) -> pl.DataFrame:
    """Hauptperiode: id, titel, reference, date, paper_type, file_name, text (Rohtext), chars."""
    base = Path(settings.data_root) / "duesseldorf" / "interim" / "papers.parquet"
    papers = pl.read_parquet(
        base, columns=["id", "name", "reference", "date", "paper_type", "file_name"]
    ).rename({"name": "titel"})
    raw = pl.read_parquet(ROHTEXT / "duesseldorf.parquet", columns=["name", "text", "chars"])
    return (
        papers.join(raw, left_on="file_name", right_on="name", how="inner")
        .with_columns(
            pl.col("text").fill_null(""),
            pl.col("paper_type").fill_null(""),
            pl.col("titel").fill_null(""),
            pl.col("reference").fill_null(""),
        )
        .filter(pl.col("text").str.strip_chars() != "")
        .sort("id")
    )


def laenge(chars: int) -> str:
    return next(name for name, upper in LAENGE if chars < upper)


# --------------------------------------------------------------------------------------------
# Eingabe, Fassung 1: Kopfzeilen und die Abschnitte aus Vorhaben 11
# --------------------------------------------------------------------------------------------


def saeubern(text: str) -> str:
    """Seitenwechsel zu Zeilen, Silbentrennung am Zeilenende weg, Leerraum je Zeile zusammen."""
    text = text.replace("\f", "\n").replace("­", "")
    text = re.sub(r"(?<=[a-zäöüß])-\n(?=[a-zäöüß])", "", text)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def kuerzen(body: str, rest: int) -> str:
    """Auf höchstens ``rest`` Zeichen, am letzten Zeilenende oder Wortende davor, mit „[…]"."""
    cut = body.rfind("\n", 0, rest)
    if cut < rest // 2:
        cut = body.rfind(" ", 0, rest)
    if cut < rest // 2:
        cut = rest
    return body[:cut].rstrip() + " […]"


@dataclass(frozen=True)
class Eingabe:
    id: str
    text: str  # was das Modell als Dokument sieht: Kopfzeilen und Abschnitte
    quelle: str  # abschnitte | rohtext
    abschnitte: tuple[str, ...]
    gekuerzt: bool
    zeichen: int  # Abschnittstext ohne Kopfzeilen


def datum_de(value: date | None) -> str:
    return f"{value.day:02d}.{value.month:02d}.{value.year}" if value else "unbekannt"


def eingabe(
    struktur: ModuleType,
    rules: Any,
    doc_id: str,
    text: str,
    paper_type: str,
    titel: str,
    reference: str,
    datum: date | None,
) -> Eingabe:
    result = struktur.analyse(doc_id, text, rules, paper_type)
    order = {kind: i for i, (kind, _name) in enumerate(ABSCHNITTE)}
    names = dict(ABSCHNITTE)
    spans = sorted(
        (s for s in result.sections if s.norm in order), key=lambda s: (order[s.norm], s.start)
    )
    used: list[tuple[int, int]] = []
    parts: list[tuple[str, str]] = []
    rest, gekuerzt = BUDGET_ZEICHEN, False
    for span in spans:
        if rest <= 0:
            gekuerzt = True
            break
        if any(span.start < b and a < span.end for a, b in used):
            continue  # Ebene 2 im Text eines schon genommenen Abschnitts
        body = saeubern(text[span.start : span.end])
        if not body:
            continue
        if len(body) > rest:
            body, gekuerzt = kuerzen(body, rest), True
        used.append((span.start, span.end))
        parts.append((span.norm, body))
        rest -= len(body)
    quelle = "abschnitte"
    if not any(kind in KERN for kind, _ in parts):
        quelle = "rohtext"
        head = [s.end for s in result.sections if s.norm == "betreff" or s.norm.startswith("kopf")]
        body = saeubern(text[max(head, default=0) :])
        if len(body) < 50:
            body = saeubern(text)
        rest = BUDGET_ZEICHEN - sum(len(b) for k, b in parts if k == "betreff")
        parts = [(k, b) for k, b in parts if k == "betreff"]
        if len(body) > rest:
            body, gekuerzt = kuerzen(body, rest), True
        parts.append(("text", body))
    blocks: list[str] = []
    for kind, body in parts:
        title = names.get(kind, "Text")
        if blocks and blocks[-1].startswith(f"## {title}\n"):
            blocks[-1] += "\n\n" + body
        else:
            blocks.append(f"## {title}\n{body}")
    kopf = (
        f"Dokumentart: {paper_type or 'unbekannt'}\n"
        f"Drucksache: {reference or 'unbekannt'}\n"
        f"Datum: {datum_de(datum)}\n"
        f"Titel: {titel or 'unbekannt'}"
    )
    return Eingabe(
        doc_id,
        kopf + "\n\n" + "\n\n".join(blocks),
        quelle,
        tuple(dict.fromkeys(k for k, _ in parts)),
        gekuerzt,
        sum(len(b) for _, b in parts),
    )


def prompt(e: Eingabe) -> str:
    return REGELN + e.text


def eingaben(frame: pl.DataFrame, struktur: ModuleType, rules_name: str) -> dict[str, Eingabe]:
    rules = struktur.Rules.load(rules_name)
    out: dict[str, Eingabe] = {}
    for row in frame.iter_rows(named=True):
        out[row["id"]] = eingabe(
            struktur,
            rules,
            row["id"],
            row["text"],
            row["paper_type"],
            row.get("titel") or "",
            row.get("reference") or "",
            row.get("date"),
        )
    return out


# --------------------------------------------------------------------------------------------
# Treueprüfung (vorab festgelegt, § 3.1)
# --------------------------------------------------------------------------------------------

MONATE = {
    "januar": 1,
    "jänner": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "febr": 2,
    "märz": 3,
    "maerz": 3,
    "mär": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}
_MONAT = r"(Januar|Jänner|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Jan\.|Febr?\.|Mär\.|Apr\.|Jun\.|Jul\.|Aug\.|Sept?\.|Okt\.|Nov\.|Dez\.)"
DATUM_ZAHL = re.compile(r"(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(\d{4}|\d{2}))?(?![\d])")
DATUM_WORT = re.compile(r"(?<!\d)(\d{1,2})\.\s?" + _MONAT + r"(?:\s?(\d{4}))?", re.I)
MONAT_JAHR = re.compile(r"(?<![\d.]\s)(?<![\d.])\b" + _MONAT + r"\s(\d{4})\b", re.I)
DATUM_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
UHRZEIT = re.compile(r"(?<![\d.,])(\d{1,2})(?:[:.](\d{2}))?\s?Uhr\b")
# Drucksachennummer: Kürzel, optional Nummer, laufende Nummer, Jahr, optional Nachtrag
# (BV6/108/2023, RAT/270/2023, OVA/117/2023/1); die alte Form <Amt>/ <Nummer>/<Jahr> (61/ 12/2014).
DRUCKSACHE = re.compile(
    r"(?<![\w/])([A-ZÄÖÜ]{1,8})\s?(\d{1,2})?\s?/\s?(\d{1,4})\s?/\s?(\d{4})"
    r"(?:\s?[/-]\s?(\d{1,2}))?(?![\d/])"
)
DRUCKSACHE_ALT = re.compile(
    r"(?<![\w/.,])(\d{2,3})/\s{0,2}(\d{1,4})/(\d{4})(?:\s?-\s?(\d{1,2}))?(?!\d)"
)
# Im Text der Eingabe, großzügig: pypdf klebt Wörter zusammen („VorlageBV6/002/2023"); jede
# Endung der Buchstabenfolge gilt als Kürzel.
DRUCKSACHE_TEXT = re.compile(
    r"([A-Za-zÄÖÜäöü]*)\s?(\d{1,2})?\s?/\s?(\d{1,4})\s?/\s?(\d{4})(?:\s?[/-]\s?(\d{1,2}))?(?![\d/])"
)
FAKTOR = {
    "tsd": 1000,
    "tausend": 1000,
    "t€": 1000,
    "teur": 1000,
    "mio": 10**6,
    "million": 10**6,
    "millionen": 10**6,
    "mrd": 10**9,
    "milliarde": 10**9,
    "milliarden": 10**9,
}
ZAHL = re.compile(
    r"(?<![\d.,/])(\d{1,3}(?:[.   ]\d{3})+|\d+)(?:,(\d+))?(?![\d])"
    r"(?:\s?(Tsd\.?|Tausend|T€|TEUR|Mio\.?|Millionen|Million|Mrd\.?|Milliarden|Milliarde)(?![a-zäöüß]))?"
)
ZAHLWORT = {
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fünf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwölf": 12,
    "zwanzig": 20,
    "dreißig": 30,
    "hundert": 100,
}
ZAHLWORT_RE = re.compile(r"\b(" + "|".join(ZAHLWORT) + r")\b", re.I)
KUERZEL = re.compile(
    r"(?<![\w-])([A-ZÄÖÜ]{1,6}\s?\d{1,2}|[A-ZÄÖÜ][A-Za-zÄÖÜäöü]*[A-ZÄÖÜ][A-Za-zÄÖÜäöü]*\d{0,2})(?![\w])"
)
ROEMISCH = re.compile(r"^[IVXLC]+$")
WAEHRUNG = frozenset({"EUR", "EURO", "TEUR"})
PERSON = re.compile(r"\b(?:Herrn?|Frau|Dr\.|Prof\.)\s+([A-ZÄÖÜ][\wäöüß-]+)")
WORT = re.compile(r"(?<![\w-])([A-ZÄÖÜ][a-zäöüß][\wäöüß]*(?:-[\wäöüß]+)*)")
ENDUNGEN = ("ern", "en", "er", "es", "e", "n", "s")


@dataclass(frozen=True)
class Angabe:
    klasse: str  # zahl | datum | drucksache | name
    art: str  # Unterart: zahl, zahlwort, uhrzeit, datum, monat, tag, drucksache, kuerzel, ort, person, selten
    text: str
    belegt: bool


def _jahr(y: str | None) -> int | None:
    if not y:
        return None
    n = int(y)
    return n + 2000 if n < 100 else n


def _wert(ganz: str, bruch: str | None, einheit: str | None) -> tuple[Decimal, Decimal | None]:
    """Wert einer Zahl und, mit Einheit (Tsd., Mio., Mrd.), der skalierte Wert."""
    digits = re.sub(r"[.   ]", "", ganz)
    try:
        value = Decimal(f"{digits}.{bruch}" if bruch else digits)
    except InvalidOperation:
        value = Decimal(0)
    if not einheit:
        return value, None
    key = einheit.lower().rstrip(".")
    return value, value * FAKTOR.get(key, 1)


def _norm_dec(value: Decimal) -> str:
    return (
        format(value.normalize(), "f") if value == value.to_integral() else str(value.normalize())
    )


def ds_key(code: str, nr: str | None, num: str, year: str, suf: str | None) -> str:
    return f"{code.upper()}{int(nr) if nr else ''}/{int(num)}/{year}" + (
        f"/{int(suf)}" if suf else ""
    )


@dataclass
class Belege:
    """Was in einer Eingabe steht, normalisiert: die Menge, gegen die eine Kurzfassung geprüft wird."""

    lower: str
    compact: str  # ohne Leerraum: pypdf klebt und trennt Wörter
    daten: set[tuple[int, int, int]] = field(default_factory=set)
    monate: set[tuple[int, int]] = field(default_factory=set)
    tage: set[tuple[int, int]] = field(default_factory=set)
    zeiten: set[tuple[int, int]] = field(default_factory=set)
    zahlen: set[str] = field(default_factory=set)
    drucksachen: set[str] = field(default_factory=set)


def _norm_text(text: str) -> str:
    text = text.replace("­", "").replace("‐", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"(?<=[a-zäöüß])-\s*\n\s*(?=[a-zäöüß])", "", text)
    return re.sub(r"\s+", " ", text.lower())


def belege(text: str) -> Belege:
    b = Belege(_norm_text(text), re.sub(r"\s+", "", _norm_text(text)))
    for d, m, y in DATUM_ZAHL.findall(text):
        dd, mm, yy = int(d), int(m), _jahr(y)
        if 1 <= dd <= 31 and 1 <= mm <= 12:
            b.tage.add((dd, mm))
            if yy:
                b.daten.add((dd, mm, yy))
                b.monate.add((mm, yy))
    for d, mon, y in DATUM_WORT.findall(text):
        mm = MONATE[mon.lower().rstrip(".")]
        b.tage.add((int(d), mm))
        if y:
            b.daten.add((int(d), mm, int(y)))
            b.monate.add((mm, int(y)))
    for mon, y in MONAT_JAHR.findall(text):
        b.monate.add((MONATE[mon.lower().rstrip(".")], int(y)))
    for y, m, d in DATUM_ISO.findall(text):
        b.daten.add((int(d), int(m), int(y)))
        b.tage.add((int(d), int(m)))
        b.monate.add((int(m), int(y)))
    for h, mi in UHRZEIT.findall(text):
        b.zeiten.add((int(h), int(mi or 0)))
    for match in ZAHL.finditer(text):
        value, scaled = _wert(match.group(1), match.group(2), match.group(3))
        b.zahlen.add(_norm_dec(value))
        if scaled is not None:
            b.zahlen.add(_norm_dec(scaled))
    for run in re.findall(r"\d+", text):  # auch Teile von Daten, Nummern, Beträgen
        b.zahlen.add(str(int(run)))
    for word in ZAHLWORT_RE.findall(text):
        b.zahlen.add(str(ZAHLWORT[word.lower()]))
    for letters, nr, num, year, suf in DRUCKSACHE_TEXT.findall(text):
        for i in range(max(0, len(letters) - 8), len(letters) + 1):
            b.drucksachen.add(ds_key(letters[i:], nr, num, year, suf))
    for head, num, year, suf in DRUCKSACHE_ALT.findall(text):
        b.drucksachen.add(ds_key(head, None, num, year, suf))
    return b


def _in_text(term: str, b: Belege) -> bool:
    """Ein Name steht in der Eingabe: als Teilfolge, ohne Leerraum, „str." gleich „straße"."""
    t = _norm_text(term).strip()
    variants = {t, t.replace("str.", "straße"), t.replace("straße", "str."), t.replace("ß", "ss")}
    return any(v and (v in b.lower or v.replace(" ", "") in b.compact) for v in variants)


def _stamm_in_text(word: str, b: Belege) -> bool:
    """Ein Wort steht in der Eingabe, auch gebeugt oder als Teil eines längeren Wortes."""
    w = word.lower()
    if _in_text(w, b):
        return True
    for ending in ENDUNGEN:
        if w.endswith(ending) and len(w) - len(ending) >= 4 and _in_text(w[: -len(ending)], b):
            return True
    return False


@dataclass(frozen=True)
class Lexikon:
    """Was die Prüfung außer der Eingabe braucht: Ortsnamen, Gremienkürzel, Wortverbreitung."""

    orte: tuple[str, ...]  # Ortsnamen des Wörterbuchs, klein, nach Länge absteigend
    gremien: dict[str, str]  # Kürzel -> Name, klein
    bezirk_name: str  # „bezirksvertretung {n}"
    bezirk_kuerzel: str  # „BV"
    haeufig: frozenset[str]  # Wörter (klein) in mindestens SELTEN_ANTEIL der Korpusdokumente


def _ist_belegtes_kuerzel(token: str, b: Belege, lex: Lexikon) -> bool:
    token = token.replace(" ", "")
    low = token.lower()
    stem = low[:-1] if len(low) > 3 and token.endswith("s") and token[-2].isupper() else low
    for form in {low, stem}:
        if len(form) >= 3 and form in b.compact:
            return True
        if re.search(rf"(?<![a-zäöüß]){re.escape(form)}(?![a-zäöüß])", b.lower):
            return True
    upper = token.upper()
    if upper == lex.bezirk_kuerzel and _in_text(lex.bezirk_name.split("{")[0].strip(), b):
        return True
    match = re.fullmatch(rf"{re.escape(lex.bezirk_kuerzel)}\s?(\d{{1,2}})", upper)
    if match and _in_text(lex.bezirk_name.format(n=int(match.group(1))), b):
        return True
    name = lex.gremien.get(upper)
    return bool(name) and _in_text(name, b)


def angaben(summary: str, b: Belege, lex: Lexikon) -> list[Angabe]:
    """Alle prüfbaren Angaben einer Kurzfassung mit dem Urteil „steht in der Eingabe"."""
    out: list[Angabe] = []
    masked = summary

    def mask(span: tuple[int, int]) -> None:
        nonlocal masked
        a, z = span
        masked = masked[:a] + " " * (z - a) + masked[z:]

    for m in DRUCKSACHE.finditer(summary):
        key = ds_key(*m.groups())
        out.append(Angabe("drucksache", "drucksache", m.group(0), key in b.drucksachen))
        mask(m.span())
    for m in DRUCKSACHE_ALT.finditer(masked):
        key = ds_key(m.group(1), None, m.group(2), m.group(3), m.group(4))
        out.append(Angabe("drucksache", "drucksache", m.group(0), key in b.drucksachen))
        mask(m.span())
    for m in DATUM_ISO.finditer(masked):
        y, mo, d = (int(x) for x in m.groups())
        out.append(Angabe("datum", "datum", m.group(0), (d, mo, y) in b.daten))
        mask(m.span())
    for m in DATUM_WORT.finditer(masked):
        d, mon, y = m.groups()
        mm = MONATE[mon.lower().rstrip(".")]
        ok = (int(d), mm, int(y)) in b.daten if y else (int(d), mm) in b.tage
        out.append(Angabe("datum", "datum" if y else "tag", m.group(0), ok))
        mask(m.span())
    for m in DATUM_ZAHL.finditer(masked):
        d, mo, y = m.groups()
        dd, mm, yy = int(d), int(mo), _jahr(y)
        if not (1 <= dd <= 31 and 1 <= mm <= 12):
            continue
        ok = (dd, mm, yy) in b.daten if yy else (dd, mm) in b.tage
        out.append(Angabe("datum", "datum" if yy else "tag", m.group(0), ok))
        mask(m.span())
    for m in MONAT_JAHR.finditer(masked):
        mm, yy = MONATE[m.group(1).lower().rstrip(".")], int(m.group(2))
        out.append(Angabe("datum", "monat", m.group(0), (mm, yy) in b.monate))
        mask(m.span())
    for m in UHRZEIT.finditer(masked):
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        out.append(Angabe("zahl", "uhrzeit", m.group(0), (h, mi) in b.zeiten))
        mask(m.span())
    for m in ZAHL.finditer(masked):
        value, scaled = _wert(m.group(1), m.group(2), m.group(3))
        ok = _norm_dec(value) in b.zahlen or (scaled is not None and _norm_dec(scaled) in b.zahlen)
        out.append(Angabe("zahl", "zahl", m.group(0).strip(), ok))
        mask(m.span())
    for m in ZAHLWORT_RE.finditer(masked):
        word = m.group(1)
        ok = str(ZAHLWORT[word.lower()]) in b.zahlen
        out.append(Angabe("zahl", "zahlwort", word, ok))
    # Eigennamen: a Kürzel, b Ortsnamen des Wörterbuchs, d Personen nach Anrede, e seltene Wörter
    seen: set[tuple[int, int]] = set()
    for m in PERSON.finditer(masked):
        out.append(Angabe("name", "person", m.group(1), _stamm_in_text(m.group(1), b)))
        seen.add(m.span(1))
    low = masked.lower()
    for term in lex.orte:
        start = 0
        while (pos := low.find(term, start)) >= 0:
            end = pos + len(term)
            start = end
            before = low[pos - 1] if pos else " "
            after = low[end] if end < len(low) else " "
            if before.isalnum() or (after.isalpha() and not term.endswith(".")):
                continue
            if any(pos < z and a < end for a, z in seen):
                continue
            out.append(Angabe("name", "ort", masked[pos:end], _in_text(term, b)))
            seen.add((pos, end))
    for m in KUERZEL.finditer(masked):
        token = m.group(1)
        if ROEMISCH.match(token) or token.upper() in WAEHRUNG:
            continue
        if any(m.start() < z and a < m.end() for a, z in seen):
            continue
        if sum(c.isupper() for c in token) < 2 and not re.search(r"\d", token):
            continue
        out.append(Angabe("name", "kuerzel", token, _ist_belegtes_kuerzel(token, b, lex)))
        seen.add(m.span())
    for m in WORT.finditer(masked):
        word = m.group(1)
        if any(m.start() < z and a < m.end() for a, z in seen):
            continue
        if word.lower() in lex.haeufig or all(p in lex.haeufig for p in word.lower().split("-")):
            continue
        out.append(Angabe("name", "selten", word, _stamm_in_text(word, b)))
        seen.add(m.span())
    return out


@dataclass(frozen=True)
class Pruefung:
    id: str
    modell: str
    angaben: tuple[Angabe, ...]
    abgeschnitten: bool
    leer: bool

    @property
    def unbelegt(self) -> list[Angabe]:
        return [a for a in self.angaben if not a.belegt]

    @property
    def ok(self) -> bool:
        """Ohne unbelegte Angabe; eine leere oder abgeschnittene Kurzfassung besteht nie."""
        return not self.unbelegt and not self.abgeschnitten and not self.leer


def pruefe(
    doc_id: str, modell: str, summary: str | None, cut: bool, b: Belege, lex: Lexikon
) -> Pruefung:
    if not summary or not summary.strip():
        return Pruefung(doc_id, modell, (), cut, True)
    return Pruefung(doc_id, modell, tuple(angaben(summary, b, lex)), cut, False)


def lexikon(settings: Settings, corpus_lower: pl.Series) -> Lexikon:
    processed = Path(settings.data_root) / "duesseldorf" / "processed"
    terms = pl.read_parquet(processed / "combined_searchdict.parquet")["suchbegriffe"].explode()
    orte = sorted({t for t in terms.drop_nulls().to_list() if len(t) >= 4}, key=len, reverse=True)
    bodies = settings.bodies
    gremien = {k: v.lower() for k, v in {**bodies.council, **bodies.committees}.items() if v}
    n = corpus_lower.len()
    tokens = (
        corpus_lower.str.extract_all(r"[a-zäöüß][a-zäöüß0-9]*(?:-[a-zäöüß0-9]+)*")
        .list.unique()
        .explode()
        .drop_nulls()
        .value_counts()
    )
    tokens = tokens.rename({tokens.columns[0]: "wort", tokens.columns[1]: "df"})
    haeufig = frozenset(tokens.filter(pl.col("df") >= SELTEN_ANTEIL * n)["wort"].to_list())
    return Lexikon(
        tuple(orte),
        gremien,
        bodies.district_body_name.lower(),
        bodies.district_body,
        haeufig,
    )


# --------------------------------------------------------------------------------------------
# Stichprobe
# --------------------------------------------------------------------------------------------


def schichten(frame: pl.DataFrame, struktur: ModuleType) -> pl.DataFrame:
    rules = struktur.Rules.load("duesseldorf")
    return frame.with_columns(
        pl.col("paper_type").map_elements(rules.art, return_dtype=pl.String).alias("art"),
        pl.col("chars").map_elements(laenge, return_dtype=pl.String).alias("laenge"),
    ).with_columns((pl.col("art") + "|" + pl.col("laenge")).alias("schicht"))


def ziehen(frame: pl.DataFrame, stratum: str, n: int, seed: int) -> pl.DataFrame:
    """Proportional nach ``stratum`` mit größtem Rest (F4 ``allocate``), je Schicht nach Rang (F4 ``rank``)."""
    sizes = dict(frame.group_by(stratum).len().iter_rows())
    alloc = allocate(sizes, n, "proportional")
    ranked = frame.with_columns(
        pl.col("id").map_elements(lambda i: rank(seed, i), return_dtype=pl.String).alias("rang")
    )
    picked = [
        ranked.filter(pl.col(stratum) == name).sort("rang").head(k) for name, k in alloc.items()
    ]
    return (
        pl.concat(picked)
        .join(frame.group_by(stratum).len().rename({"len": "schicht_n"}), on=stratum, how="left")
        .sort("rang")
    )


def endung(runde: int) -> str:
    """Dateinamen der Umbaurunde tragen „-2"; die erste Runde bleibt, wie sie geschrieben ist."""
    return "" if runde == 1 else f"-{runde}"


def stichprobe200(runde: int = 1) -> pl.DataFrame:
    path = VALIDIERUNG / f"stichprobe200{endung(runde)}.csv"
    return pl.read_csv(path, infer_schema=False).with_columns(pl.col("schicht_n").cast(pl.Int64))


def cmd_stichprobe2() -> int:
    """Die frischen 200 der Umbaurunde: dieselbe Schichtung, ohne die 200 der ersten Runde."""
    settings = settings_dus()
    struktur = load_struktur()
    full = schichten(korpus(settings), struktur)
    first = stichprobe200(1)["id"].to_list()
    rest = full.filter(~pl.col("id").is_in(first))
    sizes = full.group_by("schicht").len().rename({"len": "schicht_n"})
    sample = (
        ziehen(rest, "schicht", STICHPROBE, SEED_RUNDE2)
        .drop("schicht_n")
        .join(sizes, on="schicht", how="left")
        .sort("rang")
    )
    assert not set(sample["id"].to_list()) & set(first)
    sample.select("id", "art", "laenge", "schicht", "schicht_n").write_csv(
        VALIDIERUNG / "stichprobe200-2.csv"
    )
    print(
        f"Runde 2: {sample.height} Dokumente aus {rest.height}, {sample['schicht'].n_unique()} Schichten"
    )
    return 0


def cmd_stichprobe() -> int:
    settings = settings_dus()
    struktur = load_struktur()
    frame = schichten(korpus(settings), struktur)
    sample = ziehen(frame, "schicht", STICHPROBE, SEED)
    VALIDIERUNG.mkdir(parents=True, exist_ok=True)
    sample.select("id", "art", "laenge", "schicht", "schicht_n").write_csv(
        VALIDIERUNG / "stichprobe200.csv"
    )
    print(
        f"200: {sample.height} Dokumente aus {frame.height}, {sample['schicht'].n_unique()} Schichten"
    )
    # Die 50 für die Bewertung: aus den 200, proportional nach Dokumentart (F4-Format)
    sub = ziehen(sample.drop("schicht_n", "rang"), "art", KODIERT, SEED + 1)
    LOKAL.mkdir(parents=True, exist_ok=True)
    population = LOKAL / "grundgesamtheit50.parquet"
    sample.select("id", "art").write_parquet(population)
    paths = ValidationPaths(PROJEKT, VALIDIERUNG, KODIERUNG)
    sizes = dict(sample.group_by("art").len().iter_rows())
    drawn = dict(sub.group_by("art").len().iter_rows())
    write_sample(
        paths,
        sub.select("id", pl.col("art").alias("schicht"), "schicht_n").sort("id"),
        {
            "vorhaben": PROJEKT,
            "codebuch_version": load_codebook(paths.codebook, PROJEKT).version,
            "profil": "duesseldorf",
            "einheit": "document",
            "grundgesamtheit": "validierung/20-kurzfassungen/stichprobe200.csv (Spalten id, art)",
            "grundgesamtheit_sha256": hashlib.sha256(
                (VALIDIERUNG / "stichprobe200.csv").read_bytes()
            ).hexdigest(),
            "einheiten": sample.height,
            "ohne_text": 0,
            "groesse": KODIERT,
            "seed": SEED + 1,
            "schicht": "art",
            "aufteilung": "proportional",
            "selbstgewichtend": False,
            "schichten": {
                k: {"grundgesamtheit": sizes[k], "stichprobe": drawn.get(k, 0)}
                for k in sorted(sizes)
            },
            "gezogen": date.today().isoformat(),
        },
    )
    print(f"50: {sub.height} Dokumente, {sub['art'].n_unique()} Arten")
    return 0


# --------------------------------------------------------------------------------------------
# Erzeugen (GPU, unter der Sperre der Warteschlange)
# --------------------------------------------------------------------------------------------


class Gemessen:
    """Ein ``Generator``, der je Aufruf Token, Sekunden und Wanduhr mitschreibt."""

    def __init__(self, inner: OllamaGenerator) -> None:
        self.inner = inner
        self.log: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def digest(self) -> str:
        return self.inner.digest

    def generate(
        self, prompt: str, *, system: str = "", options: GenerationOptions | None = None
    ) -> Reply:
        started = time.perf_counter()
        reply = self.inner.generate(prompt, system=system, options=options)
        wall = time.perf_counter() - started
        call = self.inner.calls[-1]
        self.log.append(
            {
                "sha": input_sha256(f"{system}\x00{prompt}"),
                "wand": round(wall, 4),
                **{
                    k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(call).items()
                },
            }
        )
        return reply


def last() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]


def gpu_speicher() -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        return ""
    return out


def ausgewaehlte_eingaben(ids: Sequence[str]) -> dict[str, Eingabe]:
    settings = settings_dus()
    struktur = load_struktur()
    frame = korpus(settings).filter(pl.col("id").is_in(list(ids)))
    return eingaben(frame, struktur, "duesseldorf")


def exportieren(
    modell: str,
    digest: str,
    ids: Sequence[str],
    texts: Sequence[str | None],
    cut: Sequence[bool],
    runde: int = 1,
) -> None:
    """Die Kurzfassungen aus dem Cache als lokaler Auszug (nie ins Repo)."""
    LOKAL.mkdir(parents=True, exist_ok=True)
    name = full_name(modell).replace(":", "_").replace("/", "_")
    path = LOKAL / f"kurzfassungen-{name}{endung(runde)}.jsonl"
    rows = [
        {
            "id": i,
            "modell": full_name(modell),
            "digest": digest,
            "prompt": PROMPT_VERSION,
            "text": t,
            "abgeschnitten": c,
        }
        for i, t, c in zip(ids, texts, cut, strict=True)
        if t is not None
    ]
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def cmd_erzeugen(
    modell: str, minuten: float, block: int, ids: Sequence[str] | None = None, runde: int = 1
) -> int:
    settings = settings_dus()
    layout = Layout.from_settings(settings)
    sample = stichprobe200(runde)
    order = (
        ids if ids is not None else sample["id"].to_list()
    )  # nach Rang: ein Teillauf ist zufällig
    inputs = ausgewaehlte_eingaben(order)
    prompts = [prompt(inputs[i]) for i in order]
    sha_to_id = {input_sha256(f"{SYSTEM}\x00{p}"): i for i, p in zip(order, prompts, strict=True)}
    client = client_from_settings(settings.ml)
    timed = Gemessen(generator_from_settings(settings.ml, client, model=modell))
    use = GenerationUse(timed, PROMPT_VERSION, generation_options(settings.ml))
    LOKAL.mkdir(parents=True, exist_ok=True)
    (LOKAL / "laeufe").mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    log_path = LOKAL / "laeufe" / f"{full_name(modell).replace(':', '_')}-{stamp}.jsonl"
    head = {
        "art": "beginn",
        "zeit": datetime.now().isoformat(timespec="seconds"),
        "last": last(),
        "gpu": gpu_speicher(),
        "modell": use.name,
        "digest": timed.digest,
        "prompt": PROMPT_VERSION,
        "optionen": asdict(use.options),
    }
    started = time.monotonic()
    with (
        ModelCache(layout.ml_cache, use.name) as cache,
        log_path.open("w", encoding="utf-8") as log,
    ):
        log.write(json.dumps(head) + "\n")
        while True:
            out = generate_texts(
                use, cache, prompts, system=SYSTEM, limit=block, progress=progress_log()
            )
            for entry in timed.log:
                entry["id"] = sha_to_id.get(entry["sha"], "")
                entry["art"] = "aufruf"
                log.write(json.dumps(entry) + "\n")
            timed.log.clear()
            log.flush()
            print(out.report.line(), flush=True)
            if out.report.left == 0 or out.report.computed == 0:
                break
            if time.monotonic() - started > minuten * 60:
                print("Zeit des Blocks um; der nächste Lauf rechnet weiter")
                break
        log.write(
            json.dumps(
                {
                    "art": "ende",
                    "zeit": datetime.now().isoformat(timespec="seconds"),
                    "last": last(),
                    "gpu": gpu_speicher(),
                    "offen": out.report.left,
                    "gescheitert": out.report.failed,
                }
            )
            + "\n"
        )
    exportieren(modell, timed.digest, order, out.texts, out.truncated, runde)
    return 0


# --------------------------------------------------------------------------------------------
# Maßstab und Kodierung (F4)
# --------------------------------------------------------------------------------------------

MASSSTAB = KODIERUNG / "massstab"
QUELLEN = ("qwen", "gemma", "massstab")  # was hinter K1 bis K3 steht; die Zuordnung liegt in LOKAL


def stichprobe50() -> list[str]:
    return sorted(pl.read_csv(VALIDIERUNG / "stichprobe.csv", infer_schema=False)["id"].to_list())


def cmd_massstab(force: bool) -> int:
    ids = stichprobe50()
    inputs = ausgewaehlte_eingaben(ids)
    MASSSTAB.mkdir(parents=True, exist_ok=True)
    answers = MASSSTAB / "antworten.jsonl"
    if answers.exists() and not force:
        filled = [json.loads(line) for line in answers.read_text(encoding="utf-8").splitlines()]
        if any(row.get("kurzfassung") for row in filled):
            print(f"{answers} trägt schon Kurzfassungen; --force schreibt neu")
            return 1
    order = sorted(ids, key=lambda i: rank(SEED + 3, i))
    tasks = [{"id": i, "dokument": inputs[i].text} for i in order]
    (MASSSTAB / "auftrag.jsonl").write_text(
        "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in tasks), encoding="utf-8"
    )
    answers.write_text(
        "".join(json.dumps({"id": i, "kurzfassung": None}) + "\n" for i in order), encoding="utf-8"
    )
    (MASSSTAB / "anleitung.md").write_text(MASSSTAB_ANLEITUNG, encoding="utf-8")
    print(f"Maßstab: {len(tasks)} Dokumente -> {MASSSTAB}")
    return 0


MASSSTAB_ANLEITUNG = f"""# Maßstab-Kurzfassungen, Vorhaben 20

Du schreibst je Dokument eine Kurzfassung, die als Maßstab dient. Du bekommst genau den Text, den
auch die anderen Verfasser bekommen haben, und genau dieselbe Anweisung.

`auftrag.jsonl` hat je Zeile ein Dokument (`id`, `dokument`). Schreibe in `antworten.jsonl`, in die
Zeile mit derselben `id`, deine Kurzfassung als Text in `kurzfassung`. Ändere keine `id`, lass keine
Zeile weg, füge keine hinzu. Jede Kurzfassung ist dein eigener Text zu genau diesem Dokument: kein
Skript, keine Vorlage über mehrere Dokumente, keine Suche. Lies keine anderen Dateien, nicht das
Repository, nichts im Netz. Arbeite in Blöcken von zehn Zeilen und schreibe nach jedem Block.

## Rolle

{SYSTEM}

## Anweisung (wörtlich wie für die anderen Verfasser; das Dokument steht in `dokument`)

{REGELN.rstrip()}
"""


def lies_massstab() -> dict[str, str]:
    path = MASSSTAB / "antworten.jsonl"
    if not path.is_file():
        return {}
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return {
        r["id"]: r["kurzfassung"]
        for r in rows
        if isinstance(r.get("kurzfassung"), str) and r["kurzfassung"].strip()
    }


def lies_kurzfassungen(modell: str, runde: int = 1) -> dict[str, tuple[str, bool]]:
    name = full_name(modell).replace(":", "_").replace("/", "_")
    path = LOKAL / f"kurzfassungen-{name}{endung(runde)}.jsonl"
    if not path.is_file():
        return {}
    out: dict[str, tuple[str, bool]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("prompt") == PROMPT_VERSION:
            out[row["id"]] = (row["text"], bool(row["abgeschnitten"]))
    return out


def zuordnung(doc_id: str) -> dict[str, str]:
    """K1 bis K3 -> Quelle, je Dokument fest (für beide Kodierer gleich), zufällig über den Seed."""
    perms = [(a, b, c) for a in QUELLEN for b in QUELLEN for c in QUELLEN if len({a, b, c}) == 3]
    chosen = perms[int(rank(SEED + 2, doc_id), 16) % len(perms)]
    return {f"K{i + 1}": q for i, q in enumerate(chosen)}


def cmd_kodierung(force: bool) -> int:
    ids = stichprobe50()
    reference = lies_massstab()
    missing = [i for i in ids if i not in reference]
    if missing:
        print(f"Maßstab fehlt für {len(missing)} von {len(ids)} Dokumenten; erst der Maßstab-Agent")
        return 1
    texts = {"qwen": lies_kurzfassungen(MODELLE[0]), "gemma": lies_kurzfassungen(MODELLE[1])}
    for name, found in texts.items():
        gaps = [i for i in ids if i not in found]
        if gaps:
            print(f"{name}: {len(gaps)} Kurzfassungen fehlen")
            return 1
    inputs = ausgewaehlte_eingaben(ids)
    settings = settings_dus()
    titles = dict(
        korpus(settings).filter(pl.col("id").is_in(ids)).select("id", "titel").iter_rows()
    )
    paths = ValidationPaths(PROJEKT, VALIDIERUNG, KODIERUNG)
    codebook = load_codebook(paths.codebook, PROJEKT)
    shown = questions(codebook)
    mapping: dict[str, dict[str, str]] = {}
    tasks: list[dict[str, Any]] = []
    for doc in ids:
        mapping[doc] = zuordnung(doc)
        summaries = []
        for k, source in mapping[doc].items():
            text = reference[doc] if source == "massstab" else texts[source][doc][0]
            summaries.append({"kennung": k, "text": text})
        tasks.append(
            {
                "id": doc,
                "vorhaben": PROJEKT,
                "codebuch_version": codebook.version,
                "dokumente": [
                    {"id": doc, "titel": titles.get(doc, ""), "ausschnitt": inputs[doc].text}
                ],
                "kurzfassungen": summaries,
                "fragen": shown,
                "antwort": None,
            }
        )
    for coder in ("A", "B"):
        ordered = sorted(tasks, key=lambda t: rank(codebook.sample.seed, f"{coder}|{t['id']}"))
        write_assignment(paths, coder, ordered, codebook, force=force)
    (LOKAL / "zuordnung.json").write_text(
        json.dumps(mapping, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(
        f"Kodierung: {len(tasks)} Einheiten je Kodierer -> {KODIERUNG}/A, /B; Zuordnung in {LOKAL}"
    )
    return 0


# --------------------------------------------------------------------------------------------
# Auswertung: Treue, Länge, Durchsatz, Hochrechnung
# --------------------------------------------------------------------------------------------


def wilson(part: int, whole: int, z: float = 1.959964) -> tuple[float, float]:
    if not whole:
        return (math.nan, math.nan)
    p = part / whole
    d = 1 + z * z / whole
    c = p + z * z / (2 * whole)
    h = z * ((p * (1 - p) / whole + z * z / (4 * whole * whole)) ** 0.5)
    return ((c - h) / d, (c + h) / d)


def geschichtet(rows: Iterable[tuple[str, int, bool]]) -> tuple[float, float, float, float]:
    """Σ W_h·x_h/m_h mit Wilson bei Kishs n_eff (wie F4, docs/validierung.md § 5)."""
    by: dict[str, list[bool]] = defaultdict(list)
    size: dict[str, int] = {}
    for stratum, n, ok in rows:
        by[stratum].append(ok)
        size[stratum] = n
    total = sum(size.values())
    est = sum(size[h] / total * sum(v) / len(v) for h, v in by.items())
    weights = [size[h] / len(v) for h, v in by.items() for _ in v]
    n_eff = sum(weights) ** 2 / sum(w * w for w in weights)
    lo, hi = wilson(round(est * n_eff), round(n_eff))
    return est, lo, hi, n_eff


SATZ = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ„\"])")
GERUNDET = re.compile(r"(rund|etwa|ca\.|circa|knapp|über|mehr als|fast|gut|annähernd)\s*$", re.I)


def gerundet(summary: str, a: Angabe, b: Belege) -> bool:
    """Eine unbelegte Zahl mit Rundungswort davor, die höchstens 5 % neben einer Zahl der Eingabe liegt."""
    pos = summary.find(a.text)
    if a.klasse != "zahl" or pos < 0 or not GERUNDET.search(summary[max(0, pos - 14) : pos]):
        return False
    m = ZAHL.match(a.text)
    if not m:
        return False
    value, scaled = _wert(m.group(1), m.group(2), m.group(3))
    target = scaled if scaled is not None else value
    for raw in b.zahlen:
        other = Decimal(raw)
        if other >= 100 and abs(other - target) <= Decimal("0.05") * other:
            return True
    return False


def treue(
    sample: pl.DataFrame, inputs: dict[str, Eingabe], lex: Lexikon, runde: int = 1
) -> tuple[list[Pruefung], dict[str, str]]:
    found: list[Pruefung] = []
    texts: dict[str, str] = {}
    for modell in MODELLE:
        summaries = lies_kurzfassungen(modell, runde)
        for doc in sample["id"].to_list():
            text, cut = summaries.get(doc, (None, False))
            b = belege(inputs[doc].text)
            found.append(pruefe(doc, full_name(modell), text, cut, b, lex))
            if text:
                texts[f"{full_name(modell)}|{doc}"] = text
    return found, texts


def zeige_treue(
    sample: pl.DataFrame,
    checks: list[Pruefung],
    texts: dict[str, str],
    inputs: dict[str, Eingabe],
    runde: int = 1,
) -> None:
    print("\n## Treueprüfung (deterministisch, Kriterium ≥ 98 % ohne unbelegte Angabe)")
    strata = dict(sample.select("id", "schicht").iter_rows())
    sizes = dict(sample.select("schicht", "schicht_n").unique().iter_rows())
    art = dict(sample.select("id", "art").iter_rows())
    rows_out: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for modell in MODELLE:
        name = full_name(modell)
        mine = [c for c in checks if c.modell == name]
        present = [c for c in mine if not c.leer]
        if not present:
            print(f"{name}: keine Kurzfassungen")
            continue
        ok = sum(c.ok for c in mine)
        lo, hi = wilson(ok, len(mine))
        est, wlo, whi, n_eff = geschichtet((strata[c.id], sizes[strata[c.id]], c.ok) for c in mine)
        print(
            f"{name}: {len(present)} von {len(mine)} Kurzfassungen, ohne unbelegte Angabe {ok} "
            f"= {100 * ok / len(mine):.1f} % (Wilson {100 * lo:.1f}–{100 * hi:.1f}); geschichtet "
            f"{100 * est:.1f} % ({100 * wlo:.1f}–{100 * whi:.1f}, n_eff {n_eff:.0f}); "
            f"abgeschnitten {sum(c.abgeschnitten for c in mine)}, leer {sum(c.leer for c in mine)}"
        )
        per_class = Counter(a.klasse for c in present for a in c.angaben)
        bad_class = Counter(a.klasse for c in present for a in c.unbelegt)
        bad_art = Counter(a.art for c in present for a in c.unbelegt)
        docs_bad_class = Counter(k for c in present for k in {a.klasse for a in c.unbelegt})
        print(
            "  Angaben je Klasse (unbelegt; Kurzfassungen mit unbelegter): "
            + ", ".join(
                f"{k} {per_class[k]} ({bad_class[k]}; {docs_bad_class[k]})"
                for k in ("zahl", "datum", "drucksache", "name")
            )
            + f"; je Unterart unbelegt: {dict(sorted(bad_art.items()))}"
        )
        mean_n = statistics.mean(len(c.angaben) for c in present)
        persons = sum(any(a.art == "person" for a in c.angaben) for c in present)
        print(f"  Kurzfassungen mit Person nach Anrede (gegen Regel 5): {persons}")
        print(
            f"  Angaben je Kurzfassung im Mittel {mean_n:.1f}; ohne jede Angabe {sum(not c.angaben for c in present)}"
        )
        rounded = sum(
            gerundet(texts[f"{name}|{c.id}"], a, belege(inputs[c.id].text))
            for c in present
            for a in c.unbelegt
        )
        strict_bad = [c for c in mine if not c.ok]
        only_rounded = sum(
            1
            for c in strict_bad
            if not c.leer
            and not c.abgeschnitten
            and all(
                gerundet(texts[f"{name}|{c.id}"], a, belege(inputs[c.id].text)) for a in c.unbelegt
            )
        )
        print(
            f"  davon unbelegte Zahlen mit Rundungswort und ≤ 5 % Abstand: {rounded}; Kurzfassungen, die nur daran scheitern: {only_rounded}"
        )
        by_art = Counter(art[c.id] for c in mine if not c.ok)
        print(f"  nicht bestanden je Art: {dict(by_art.most_common())}")
        by_len = Counter(strata[c.id].split("|")[1] for c in mine if not c.ok)
        n_len = Counter(strata[c.id].split("|")[1] for c in mine)
        print(
            "  nicht bestanden je Länge: "
            + ", ".join(f"{k} {by_len[k]}/{n_len[k]}" for k in ("kurz", "mittel", "lang"))
        )
        cut_in = Counter((inputs[c.id].gekuerzt, c.ok) for c in mine)
        print(f"  Eingabe gekürzt: bestanden {cut_in[(True, True)]}, nicht {cut_in[(True, False)]}")
        words = [len(texts[f"{name}|{c.id}"].split()) for c in present]
        sents = [len(SATZ.split(texts[f"{name}|{c.id}"].strip())) for c in present]
        within = sum(w <= 80 and s <= 3 for w, s in zip(words, sents, strict=True))
        print(
            f"  Länge: Wörter Median {statistics.median(words):.0f} (max {max(words)}), Sätze "
            f"Median {statistics.median(sents):.0f} (max {max(sents)}); ≤ 3 Sätze und ≤ 80 Wörter: "
            f"{within} von {len(present)}"
        )
        for c in mine:
            counts = Counter(a.klasse for a in c.angaben)
            bad = Counter(a.klasse for a in c.unbelegt)
            rows_out.append(
                {
                    "id": c.id,
                    "modell": name,
                    "angaben": len(c.angaben),
                    **{f"{k}": counts[k] for k in ("zahl", "datum", "drucksache", "name")},
                    **{f"unbelegt_{k}": bad[k] for k in ("zahl", "datum", "drucksache", "name")},
                    "abgeschnitten": int(c.abgeschnitten),
                    "leer": int(c.leer),
                    "ok": int(c.ok),
                }
            )
            for a in c.unbelegt:
                details.append({"id": c.id, "modell": name, **asdict(a)})
    if rows_out:
        pl.DataFrame(rows_out).sort("modell", "id").write_csv(
            VALIDIERUNG / f"treue{endung(runde)}.csv"
        )
        LOKAL.mkdir(parents=True, exist_ok=True)
        (LOKAL / f"treue_unbelegt{endung(runde)}.jsonl").write_text(
            "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in details), encoding="utf-8"
        )
    # beide Modelle an denselben Dokumenten
    by_doc: dict[str, dict[str, bool]] = defaultdict(dict)
    for c in checks:
        by_doc[c.id][c.modell] = c.ok
    a, b = (full_name(m) for m in MODELLE)
    pairs = Counter((v.get(a), v.get(b)) for v in by_doc.values() if a in v and b in v)
    print(
        f"  beide bestanden {pairs[(True, True)]}, nur {a} {pairs[(True, False)]}, nur {b} {pairs[(False, True)]}, keines {pairs[(False, False)]}"
    )


# Nachträglich, nach der Durchsicht (§ 3.2), nicht Teil der Festlegung: Klasse e in Fassung 2. Ein
# seltenes Wort bleibt nur beanstandet, wenn es keine Endung eines Abstraktums trägt und sich nicht
# in Wörter des Korpus zerlegen lässt; bei Bindestrichen zählt jeder Teil für sich. An dieser
# Stichprobe ist das explorativ (die Regel ist an ihren Fehlalarmen entstanden); bestätigen kann
# sie nur eine frische Stichprobe (§ 5.2).
ABSTRAKTUM = re.compile(r"(ung|heit|keit|schaft|ität|ion|nis|tum|ismus)(en|e|s|es|n|ses|sen)?$")


def bekannte_woerter(corpus_lower: pl.Series, mindestens: int = 3) -> frozenset[str]:
    words = (
        corpus_lower.str.extract_all(r"[a-zäöüß]{3,}").list.unique().explode().drop_nulls()
    ).value_counts()
    return frozenset(words.filter(pl.col(words.columns[1]) >= mindestens)[words.columns[0]])


def zerlegbar(word: str, known: frozenset[str], depth: int = 0) -> bool:
    w = word.lower()
    if w in known and depth:
        return True
    if depth > 3:
        return False
    for i in range(3, len(w) - 2):
        head, tail = w[:i], w[i:]
        for link in ("", "s", "es", "n", "en"):
            stem = head[: len(head) - len(link)] if link and head.endswith(link) else head
            if (link and not head.endswith(link)) or len(stem) < 3 or stem not in known:
                continue
            if tail in known or zerlegbar(tail, known, depth + 1):
                return True
    return False


def kategorie(a: Angabe, b: Belege, known: frozenset[str]) -> str:
    """Warum Fassung 2 eine Beanstandung der Klasse e fallen lässt, oder ``bleibt``."""
    if a.art != "selten":
        return "bleibt"
    parts = [p for p in a.text.split("-") if len(p) >= 4] if "-" in a.text else [a.text]
    reasons = []
    for part in parts:
        if len(parts) > 1 and _stamm_in_text(part, b):
            reasons.append("bindestrich_teil_belegt")
        elif ABSTRAKTUM.search(part.lower()):
            reasons.append("abstraktum")
        elif part.lower() in known:
            reasons.append("korpuswort")
        elif zerlegbar(part, known):
            reasons.append("zusammensetzung")
        else:
            return "bleibt"
    return reasons[0]


def bleibt_fassung2(a: Angabe, b: Belege, known: frozenset[str]) -> bool:
    """Bleibt eine unbelegte Angabe nach Fassung 2 der Klasse e beanstandet?"""
    return kategorie(a, b, known) == "bleibt"


def zeige_fassung2(
    checks: list[Pruefung], inputs: dict[str, Eingabe], known: frozenset[str]
) -> None:
    print("\n## Nachträglich, explorativ: Klasse e in Fassung 2 (nicht das Kriterium)")
    for modell in MODELLE:
        name = full_name(modell)
        mine = [c for c in checks if c.modell == name and not c.leer]
        if not mine:
            continue
        left = Counter()
        why: Counter[str] = Counter()
        ok = 0
        no_e = 0
        for c in mine:
            b = belege(inputs[c.id].text)
            why.update(kategorie(a, b, known) for a in c.unbelegt if a.art == "selten")
            rest = [a for a in c.unbelegt if bleibt_fassung2(a, b, known)]
            left.update(a.art for a in rest)
            ok += not rest and not c.abgeschnitten
            no_e += not [a for a in c.unbelegt if a.art != "selten"] and not c.abgeschnitten
        print(
            f"{name}: ohne Klasse e {no_e} von {len(mine)} ohne unbelegte Angabe; mit Klasse e in "
            f"Fassung 2 {ok} von {len(mine)}; verbleibend je Unterart {dict(left)}"
        )
        print(f"  Beanstandungen der Klasse e nach Grund: {dict(why.most_common())}")


def zeige_bestaetigung(
    sample: pl.DataFrame, checks: list[Pruefung], inputs: dict[str, Eingabe], known: frozenset[str]
) -> dict[str, float]:
    """Umbaurunde (§ 5.2): das Kriterium mit Klasse e in Fassung 2, sonst wie festgelegt."""
    print("\n## Bestätigung: Kriterium mit Klasse e in Fassung 2 (§ 5.2, vorab festgelegt)")
    strata = dict(sample.select("id", "schicht").iter_rows())
    sizes = dict(sample.select("schicht", "schicht_n").unique().iter_rows())
    flags: dict[tuple[str, str], int] = {}
    shares: dict[str, float] = {}
    for modell in MODELLE:
        name = full_name(modell)
        mine = [c for c in checks if c.modell == name]
        if not mine or all(c.leer for c in mine):
            continue
        left: Counter[str] = Counter()
        why: Counter[str] = Counter()
        oks: list[tuple[str, int, bool]] = []
        for c in mine:
            b = belege(inputs[c.id].text)
            rest = [a for a in c.unbelegt if bleibt_fassung2(a, b, known)]
            why.update(kategorie(a, b, known) for a in c.unbelegt if a.art == "selten")
            left.update(f"{a.klasse}/{a.art}" for a in rest)
            ok = not rest and not c.abgeschnitten and not c.leer
            flags[(name, c.id)] = len(rest)
            oks.append((strata[c.id], sizes[strata[c.id]], ok))
        n_ok = sum(ok for _, _, ok in oks)
        lo, hi = wilson(n_ok, len(oks))
        est, wlo, whi, n_eff = geschichtet(oks)
        shares[name] = est
        verdict = "besteht" if est >= KRITERIUM_TREUE else "besteht nicht"
        print(
            f"{name}: ohne unbelegte Angabe {n_ok} / {len(oks)} = {100 * n_ok / len(oks):.1f} % "
            f"(Wilson {100 * lo:.1f}–{100 * hi:.1f}); geschichtet {100 * est:.1f} % "
            f"({100 * wlo:.1f}–{100 * whi:.1f}, n_eff {n_eff:.0f}) -> Teil 1 {verdict}"
        )
        print(f"  verbleibende unbelegte Angaben je Klasse/Art: {dict(left.most_common())}")
        print(f"  Klasse e nach Grund: {dict(why.most_common())}")
    path = VALIDIERUNG / "treue-2.csv"
    if path.is_file() and flags:
        frame = pl.read_csv(path).with_columns(
            pl.struct("modell", "id")
            .map_elements(lambda r: flags.get((r["modell"], r["id"]), 0), return_dtype=pl.Int64)
            .alias("unbelegt_fassung2")
        )
        frame = frame.with_columns(
            (
                (pl.col("unbelegt_fassung2") == 0)
                & (pl.col("abgeschnitten") == 0)
                & (pl.col("leer") == 0)
            )
            .cast(pl.Int64)
            .alias("ok_fassung2")
        )
        frame.write_csv(path)
    if len(shares) == 2:
        q, g = (shares[full_name(m)] for m in MODELLE)
        print(
            f"Modellwahl, falls Teil 2 für beide besteht: qwen − gemma = {100 * (q - g):+.1f} "
            f"Prozentpunkte (qwen nur ab +2,0, sonst gemma)"
        )
    return shares


def lies_laeufe() -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted((LOKAL / "laeufe").glob("*.jsonl")):
        head: dict[str, Any] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry["art"] == "beginn":
                head = entry
            elif entry["art"] == "aufruf" and entry.get("id"):
                rows.append(
                    {
                        "id": entry["id"],
                        "modell": head["modell"],
                        "lauf": path.name,
                        "prompt": head.get("prompt", ""),
                        "prompt_tokens": entry["prompt_tokens"],
                        "output_tokens": entry["output_tokens"],
                        "sekunden": entry["seconds"],
                        "laden": entry["load_seconds"],
                        "eingabe_s": entry["prompt_seconds"],
                        "ausgabe_s": entry["output_seconds"],
                        "wand": entry["wand"],
                        "abgeschnitten": entry["truncated"],
                    }
                )
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def lauf_lasten() -> list[str]:
    out = []
    for path in sorted((LOKAL / "laeufe").glob("*.jsonl")):
        lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        start = next((x for x in lines if x["art"] == "beginn"), None)
        end = next((x for x in lines if x["art"] == "ende"), None)
        calls = sum(1 for x in lines if x["art"] == "aufruf")
        if start and calls:
            out.append(
                f"{start['zeit']} {start['modell']}: {calls} Aufrufe, Last {start['last']} -> "
                f"{end['last'] if end else '?'}, GPU {end['gpu'] if end else start['gpu']}"
            )
    return out


def durchsatz(sample: pl.DataFrame, inputs: dict[str, Eingabe], runde: int = 1) -> pl.DataFrame:
    """Je Modell und Dokument der letzte Aufruf (Fassung 1); ins Repo nur Zahlen."""
    runs = lies_laeufe()
    path = VALIDIERUNG / f"durchsatz{endung(runde)}.csv"
    if runs.height:
        runs = (
            runs.filter(
                pl.col("prompt") == PROMPT_VERSION, pl.col("id").is_in(sample["id"].to_list())
            )
            .sort("lauf")
            .unique(subset=["modell", "id"], keep="last")
            .with_columns(
                pl.col("id")
                .map_elements(lambda i: inputs[i].zeichen, return_dtype=pl.Int64)
                .alias("eingabe_zeichen"),
                (pl.col("wand") - pl.col("laden")).round(4).alias("je_dokument"),
            )
            .select(
                "id",
                "modell",
                "eingabe_zeichen",
                "prompt_tokens",
                "output_tokens",
                "eingabe_s",
                "ausgabe_s",
                "sekunden",
                "laden",
                "je_dokument",
            )
            .sort("modell", "id")
        )
        runs.write_csv(path)
        return runs
    return pl.read_csv(path) if path.is_file() else pl.DataFrame()


def fit(x: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    mx, my = statistics.mean(x), statistics.mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    slope = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / sxx if sxx else 0.0
    return my - slope * mx, slope


def zeige_durchsatz(runs: pl.DataFrame) -> dict[str, tuple[float, float]]:
    print("\n## Durchsatz auf der RTX 4090 (je Dokument ohne Laden des Modells)")
    for line in lauf_lasten():
        print(f"  {line}")
    models: dict[str, tuple[float, float]] = {}
    for modell in MODELLE:
        name = full_name(modell)
        r = runs.filter(pl.col("modell") == name) if runs.height else runs
        if not r.height:
            continue
        per = r["je_dokument"].to_list()
        out_rate = r["output_tokens"].sum() / max(r["ausgabe_s"].sum(), 1e-9)
        in_rate = r["prompt_tokens"].sum() / max(r["eingabe_s"].sum(), 1e-9)
        a, b = fit(r["eingabe_zeichen"].cast(pl.Float64).to_list(), per)
        models[name] = (a, b)
        # Nachträglich: ollama meldet auch bei geladenem Modell je Aufruf eine „load_duration"
        # (Median 0,28 s bei qwen, 0,39 s bei gemma); sie ist Wanduhr, die jeder Stapellauf zahlt.
        # Die Gerade „Wanduhr warm" nimmt jeden Aufruf außer dem, der das Modell wirklich lud.
        warm = r.filter(pl.col("laden") < 5.0)
        wall = (warm["je_dokument"] + warm["laden"]).to_list()
        a2, b2 = fit(warm["eingabe_zeichen"].cast(pl.Float64).to_list(), wall)
        models[f"{name} (Wanduhr warm)"] = (a2, b2)
        warm_line = (
            f"  Wanduhr warm: Mittel {statistics.mean(wall):.2f} s, Median "
            f"{statistics.median(wall):.2f} s; je Aufruf gemeldetes Laden Median "
            f"{statistics.median(warm['laden'].to_list()):.2f} s; Gerade {a2:.2f} s + "
            f"{1000 * b2:.3f} s je 1000 Zeichen"
        )
        print(
            f"{name}: n {r.height}, je Dokument Mittel {statistics.mean(per):.2f} s, Median "
            f"{statistics.median(per):.2f} s, P90 {statistics.quantiles(per, n=10)[-1]:.2f} s; "
            f"Eingabe {r['prompt_tokens'].mean():.0f} Token im Mittel ({in_rate:.0f} Token/s), "
            f"Ausgabe {r['output_tokens'].mean():.0f} Token ({out_rate:.1f} Token/s); "
            f"Zeichen je Eingabetoken {r['eingabe_zeichen'].sum() / r['prompt_tokens'].sum():.2f}; "
            f"Gerade: {a:.2f} s + {1000 * b:.3f} s je 1000 Zeichen"
        )
        print(warm_line)
    return models


def periode_eingaben(struktur: ModuleType) -> dict[str, pl.DataFrame]:
    """Eingabelänge je Dokument mit Text für jede Periode (dasselbe Regelwerk wie die Stichprobe)."""
    out: dict[str, pl.DataFrame] = {}
    for profile, rules_name, _name in PERIODEN:
        if profile == "duesseldorf":
            frame = korpus(settings_dus())
        else:
            frame = struktur.load_profile(profile).with_columns(pl.lit("").alias("titel"))
            frame = frame.filter(pl.col("text").str.strip_chars() != "")
        rules = struktur.Rules.load(rules_name)
        sizes = []
        for row in frame.iter_rows(named=True):
            e = eingabe(struktur, rules, row["id"], row["text"], row["paper_type"], "", "", None)
            sizes.append(e.zeichen)
        out[profile] = frame.select("id", "paper_type").with_columns(
            pl.Series("zeichen", sizes),
            pl.col("paper_type")
            .map_elements(struktur.Rules.load(rules_name).art, return_dtype=pl.String)
            .alias("art"),
        )
    return out


def zeige_hochrechnung(
    models: dict[str, tuple[float, float]], periods: dict[str, pl.DataFrame]
) -> None:
    print("\n## Hochrechnung je Periode (GPU-Stunden, Gerade aus der Stichprobe)")
    for name, (a, b) in models.items():
        used = 0.0
        print(f"{name}:")
        for profile, _rules, label in PERIODEN:
            frame = periods[profile]
            hours = sum(a + b * z for z in frame["zeichen"].to_list()) / 3600
            pick = frame.filter(pl.col("art").is_in(list(AUSWAHL_ARTEN)))
            hours_pick = sum(a + b * z for z in pick["zeichen"].to_list()) / 3600
            if hours <= BUDGET_PERIODE and used + hours <= BUDGET_GESAMT:
                verdict, used = "läuft ganz", used + hours
            elif hours_pick <= BUDGET_PERIODE and used + hours_pick <= BUDGET_GESAMT:
                verdict, used = "läuft als Auswahl", used + hours_pick
            else:
                verdict = "läuft nicht"
            print(
                f"  {label}: {frame.height} Dokumente mit Text, {hours:.1f} h; Auswahl "
                f"{pick.height} Dokumente, {hours_pick:.1f} h -> {verdict} (Summe {used:.1f} h)"
            )


def zeige_stichprobe(sample: pl.DataFrame, inputs: dict[str, Eingabe]) -> None:
    print("\n## Stichprobe und Eingaben")
    print(f"200 Dokumente, {sample['schicht'].n_unique()} Schichten (Art × Länge)")
    print("je Länge:", dict(Counter(sample["laenge"].to_list())))
    print("je Art:", dict(Counter(sample["art"].to_list()).most_common()))
    src = Counter(inputs[i].quelle for i in sample["id"].to_list())
    cut = sum(inputs[i].gekuerzt for i in sample["id"].to_list())
    chars = [inputs[i].zeichen for i in sample["id"].to_list()]
    print(
        f"Eingabe aus Abschnitten {src['abschnitte']}, Rohtext-Rückfall {src['rohtext']}, gekürzt "
        f"{cut}; Abschnittstext Median {statistics.median(chars):.0f} Zeichen, Mittel "
        f"{statistics.mean(chars):.0f}, max {max(chars)}"
    )
    kinds = Counter(k for i in sample["id"].to_list() for k in inputs[i].abschnitte)
    print("Abschnitte in den Eingaben:", dict(kinds.most_common()))


# --------------------------------------------------------------------------------------------
# Nach der Kodierung: Bewertung je Modell (F4 merge hat labels.csv geschrieben)
# --------------------------------------------------------------------------------------------

DIMENSIONEN = ("treue", "vollstaendigkeit", "verstaendlichkeit")


def zeige_bewertung(lex: Lexikon, known: frozenset[str]) -> None:
    labels_path = VALIDIERUNG / "labels.csv"
    mapping_path = LOKAL / "zuordnung.json"
    print("\n## Bewertung der 50 (zwei Kodier-Agenten, geschlichtet; Kriterium Median ≥ 4)")
    if not labels_path.is_file() or not mapping_path.is_file():
        print("noch nicht kodiert")
        return
    mapping: dict[str, dict[str, str]] = json.loads(mapping_path.read_text(encoding="utf-8"))
    labels = pl.read_csv(labels_path, infer_schema=False)
    values: dict[tuple[str, str], list[int]] = defaultdict(list)
    unbelegt: dict[str, Counter[str]] = defaultdict(Counter)
    coder_unbelegt: dict[tuple[str, str], bool] = {}
    for row in labels.iter_rows(named=True):
        k, _, dim = row["frage"].partition("_")
        source = mapping[row["id"]][k.upper()]
        if row["label"] is None:
            continue
        if dim == "unbelegt":
            unbelegt[source][row["label"]] += 1
            coder_unbelegt[(source, row["id"])] = row["label"] == "ja"
        else:
            values[(source, dim)].append(int(row["label"]))
    # α der Kodierer je Dimension: über alle 150 Kurzfassungen (die Fragen k1 bis k3 mischen die
    # Quellen, weil die Zuordnung je Dokument wechselt) und je Quelle; ordinal, „unbelegt" nominal
    pairs: dict[tuple[str, str], list[list[str | None]]] = defaultdict(list)
    for row in labels.iter_rows(named=True):
        k, _, dim = row["frage"].partition("_")
        source = mapping[row["id"]][k.upper()]
        pair: list[str | None] = [row["kodierer_a"], row["kodierer_b"]]
        pairs[(source, dim)].append(pair)
        pairs[("alle", dim)].append(pair)
    alpha: dict[tuple[str, str], float | None] = {}
    for (source, dim), units in pairs.items():
        level = "nominal" if dim == "unbelegt" else "ordinal"
        cats = ["ja", "nein"] if dim == "unbelegt" else ["1", "2", "3", "4", "5"]
        alpha[(source, dim)] = krippendorff_alpha(units, level, cats)

    def fmt(value: float | None) -> str:
        return "–" if value is None else f"{value:.3f}"

    for dim in (*DIMENSIONEN, "unbelegt"):
        print(
            f"α {dim}: alle 150 {fmt(alpha.get(('alle', dim)))}; "
            + ", ".join(f"{q} {fmt(alpha.get((q, dim)))}" for q in QUELLEN)
            + (
                " -> zählt"
                if (alpha.get(("alle", dim)) or 0) >= 0.8
                else " -> zählt nicht (α < 0,8)"
            )
        )
    for source in QUELLEN:
        cells = []
        for dim in DIMENSIONEN:
            v = values[(source, dim)]
            if v:
                dist = Counter(v)
                cells.append(
                    f"{dim} Median {statistics.median(v):g} (Mittel {statistics.mean(v):.2f}; "
                    + " ".join(f"{s}:{dist[s]}" for s in range(1, 6))
                    + ")"
                )
        u = unbelegt[source]
        n = u["ja"] + u["nein"]
        lo, hi = wilson(u["nein"], n)
        print(
            f"{source}: "
            + "; ".join(cells)
            + f"; ohne unbelegte Angabe laut Kodierern {u['nein']}/{n}"
            f" ({100 * lo:.1f}–{100 * hi:.1f} %)"
        )
    # die deterministische Prüfung gegen das Urteil der Kodierer (je Kurzfassung)
    inputs = ausgewaehlte_eingaben(list(mapping))
    reference = lies_massstab()
    texts = {"qwen": lies_kurzfassungen(MODELLE[0]), "gemma": lies_kurzfassungen(MODELLE[1])}
    table: Counter[tuple[bool, bool]] = Counter()
    table2: Counter[tuple[bool, bool]] = Counter()
    for (source, doc), coder_bad in coder_unbelegt.items():
        text = (
            reference.get(doc) if source == "massstab" else texts[source].get(doc, ("", False))[0]
        )
        b = belege(inputs[doc].text)
        check = pruefe(doc, source, text, False, b, lex)
        table[(not check.ok, coder_bad)] += 1
        flagged2 = check.leer or any(bleibt_fassung2(a, b, known) for a in check.unbelegt)
        table2[(flagged2, coder_bad)] += 1
    for name, t in (("Fassung 1 (festgelegt)", table), ("Klasse e in Fassung 2", table2)):
        print(
            f"Prüfung {name} gegen Kodierer (alle drei Quellen): beide unbelegt "
            f"{t[(True, True)]}, nur Prüfung {t[(True, False)]}, nur Kodierer "
            f"{t[(False, True)]}, beide belegt {t[(False, False)]}"
        )
    massstab_flagged = sum(
        1
        for doc, text in reference.items()
        if doc in mapping
        and not pruefe(doc, "massstab", text, False, belege(inputs[doc].text), lex).ok
    )
    print(f"Maßstab: die Prüfung beanstandet {massstab_flagged} von {len(reference)}")


# --------------------------------------------------------------------------------------------
# Versuch: Kurzfassung je Vorgang und „was ist neu" (§ 3.6, nicht validiert)
# --------------------------------------------------------------------------------------------

VORGANG_VERSION = "20-vorgang-1"
NEU_VERSION = "20-neu-1"
VORGANG_ZEICHEN = 2500  # je Dokument eines Vorgangs
NEU_ZEICHEN = 3500  # je Fassung
VORGAENGE = 8
NEU_PAARE = 6
REGELN_VORGANG = """Die Dokumente unten gehören zu einem Vorgang im Ratsinformationssystem, nach Datum geordnet. Fasse den Vorgang in zwei bis drei Sätzen zusammen, zusammen höchstens 80 Wörter: worum es geht, wer was beantragt, gefragt oder vorgeschlagen hat, und was daraus wurde (Antwort, Beschlussvorschlag, Mitteilung), soweit die Dokumente es sagen.

Regeln 3 bis 6 wie für ein Dokument: Zahlen, Beträge, Daten, Drucksachennummern und Namen nur, wenn sie in den Dokumenten stehen, genau so geschrieben; nichts hinzufügen; keine Personennamen; nur die Kurzfassung als Fließtext.

"""
REGELN_NEU = """Dokument B ist eine neue Fassung von Dokument A (ein Nachtrag oder eine Änderung). Sage in ein bis drei Sätzen, zusammen höchstens 60 Wörter, was in B neu oder anders ist als in A. Ist nichts Wesentliches neu, sage das.

Regeln: Zahlen, Beträge, Daten, Drucksachennummern und Namen nur, wenn sie in A oder B stehen, genau so geschrieben; nichts hinzufügen; keine Personennamen; nur die Antwort als Fließtext.

"""


def _ref_key(reference: str) -> str | None:
    m = re.fullmatch(
        r"([A-ZÄÖÜ]+?)(\d{1,2})?/(\d+)/(\d{4})(?:\s*[/-]+\s*(\d+))?", reference.strip()
    )
    return ds_key(*m.groups()) if m else None


def vorgaenge_waehlen(frame: pl.DataFrame) -> tuple[list[list[str]], list[tuple[str, str]]]:
    """Kanten der Rückfallregel von 14, soweit ohne Anlagen prüfbar: Titel nennt eine Drucksache, Nachtrag."""
    key_to_id: dict[str, str] = {}
    for doc, reference in frame.select("id", "reference").iter_rows():
        key = _ref_key(reference or "")
        if key:
            key_to_id.setdefault(key, doc)
    edges: set[tuple[str, str]] = set()
    nachtrag: list[tuple[str, str]] = []
    for doc, reference, title in frame.select("id", "reference", "titel").iter_rows():
        key = _ref_key(reference or "")
        if key and key.count("/") == 3:
            base = key_to_id.get(key.rsplit("/", 1)[0])
            if base and base != doc:
                edges.add((base, doc))
                nachtrag.append((base, doc))
        for letters, nr, num, year, suf in DRUCKSACHE_TEXT.findall(title or ""):
            for i in range(len(letters)):
                other = key_to_id.get(ds_key(letters[i:], nr, num, year, suf))
                if other and other != doc:
                    edges.add((other, doc))
                    break
    parent: dict[str, str] = {}

    def root(x: str) -> str:
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    comps: dict[str, list[str]] = defaultdict(list)
    for doc in {d for e in edges for d in e}:
        comps[root(doc)].append(doc)
    eligible = [sorted(c) for c in comps.values() if 2 <= len(c) <= 4]
    eligible.sort(key=lambda c: rank(SEED + 4, c[0]))
    # die Hälfte aus Vorgängen mit drei oder vier Dokumenten, sonst wären es nur Paare (14, § 5.1)
    longer = [c for c in eligible if len(c) >= 3][: VORGAENGE // 2]
    pairs = [c for c in eligible if len(c) == 2][: VORGAENGE - len(longer)]
    nachtrag.sort(key=lambda p: rank(SEED + 5, f"{p[0]}|{p[1]}"))
    return longer + pairs, nachtrag[:NEU_PAARE]


def cmd_vorgaenge(modell: str) -> int:
    settings = settings_dus()
    layout = Layout.from_settings(settings)
    struktur = load_struktur()
    frame = korpus(settings)
    groups, pairs = vorgaenge_waehlen(frame)
    ids = sorted({d for g in groups for d in g} | {d for p in pairs for d in p})
    inputs = eingaben(frame.filter(pl.col("id").is_in(ids)), struktur, "duesseldorf")
    dates = dict(frame.select("id", "date").iter_rows())
    jobs: list[tuple[str, str, str, str]] = []  # (version, schlüssel, prompt, eingabe)
    for g in groups:
        ordered = sorted(g, key=lambda d: (dates[d], d))
        body = "\n\n".join(
            f"### Dokument {n + 1}\n{inputs[d].text[:VORGANG_ZEICHEN]}"
            for n, d in enumerate(ordered)
        )
        jobs.append((VORGANG_VERSION, "|".join(ordered), REGELN_VORGANG + body, body))
    for a, b in pairs:
        body = f"### Dokument A\n{inputs[a].text[:NEU_ZEICHEN]}\n\n### Dokument B\n{inputs[b].text[:NEU_ZEICHEN]}"
        jobs.append((NEU_VERSION, f"{a}|{b}", REGELN_NEU + body, body))
    client = client_from_settings(settings.ml)
    timed = Gemessen(generator_from_settings(settings.ml, client, model=modell))
    rows: list[dict[str, Any]] = []
    for version in (VORGANG_VERSION, NEU_VERSION):
        use = GenerationUse(timed, version, generation_options(settings.ml))
        mine = [j for j in jobs if j[0] == version]
        with ModelCache(layout.ml_cache, use.name) as cache:
            out = generate_texts(use, cache, [j[2] for j in mine], system=SYSTEM)
        for job, text, cut in zip(mine, out.texts, out.truncated, strict=True):
            rows.append(
                {
                    "version": version,
                    "schluessel": job[1],
                    "text": text,
                    "abgeschnitten": cut,
                    "eingabe": job[3],
                }
            )
    timing = {e["sha"]: e for e in timed.log}
    for row in rows:
        sha = input_sha256(
            f"{SYSTEM}\x00{(REGELN_VORGANG if row['version'] == VORGANG_VERSION else REGELN_NEU) + row['eingabe']}"
        )
        row["wand"] = timing.get(sha, {}).get("wand")
        row["modell"] = timed.name
    LOKAL.mkdir(parents=True, exist_ok=True)
    path = LOKAL / f"vorgaenge-{timed.name.replace(':', '_')}.jsonl"
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    plan = [{"art": "vorgang", "nr": n + 1, "id": d} for n, g in enumerate(groups) for d in g]
    plan += [{"art": "neu", "nr": n + 1, "id": d} for n, p in enumerate(pairs) for d in p]
    pl.DataFrame(plan).write_csv(VALIDIERUNG / "vorgaenge.csv")
    print(f"{timed.name}: {len(rows)} Antworten -> {path}")
    return 0


def zeige_vorgaenge(lex: Lexikon) -> None:
    print("\n## Versuch: Vorgang und „was ist neu“ (nicht validiert)")
    for modell in MODELLE:
        path = LOKAL / f"vorgaenge-{full_name(modell).replace(':', '_')}.jsonl"
        if not path.is_file():
            continue
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        for version in (VORGANG_VERSION, NEU_VERSION):
            mine = [r for r in rows if r["version"] == version]
            checks = [
                pruefe(
                    r["schluessel"],
                    modell,
                    r["text"],
                    r["abgeschnitten"],
                    belege(r["eingabe"]),
                    lex,
                )
                for r in mine
            ]
            words = [len((r["text"] or "").split()) for r in mine]
            walls = [r["wand"] for r in mine if r.get("wand")]
            print(
                f"{full_name(modell)} {version}: {len(mine)} Antworten, ohne unbelegte Angabe "
                f"{sum(c.ok for c in checks)}, unbelegt {[a.art for c in checks for a in c.unbelegt]}; "
                f"Wörter Median {statistics.median(words) if words else 0:.0f}; "
                f"Sekunden je Antwort Median {statistics.median(walls) if walls else float('nan'):.1f}"
            )


# --------------------------------------------------------------------------------------------
# Selbsttest der Prüfung an erfundenen Beispielen (keine Kurzfassung eines Modells)
# --------------------------------------------------------------------------------------------


def cmd_selbsttest() -> int:
    lex = Lexikon(
        ("kölner straße", "benrath", "königsallee"),
        {"OVA": "ordnungs- und verkehrsausschuss"},
        "bezirksvertretung {n}",
        "BV",
        frozenset(
            {
                "die",
                "der",
                "bis",
                "vgl",
                "herr",
                "verweis",
                "sitzung",
                "varianten",
                "förderung",
                "verwaltung",
                "antrag",
                "fraktion",
                "spd",
                "bezirksvertretung",
                "euro",
                "radweg",
            }
        ),
    )
    text = (
        "Dokumentart: Antrag SPD\nDrucksache: BV6/108/2023\nDatum: 15.06.2023\nTitel: Radweg Kölner Str.\n\n"
        "## Beschlussvorschlag\nDie Bezirksvertretung 6 beschließt, für 1.500.000,00 € bis zum 31. Dezember 2024 "
        "einen Radweg in Benrath zu bauen. Vgl. Vorlage OVA/117/2023/1 und 61/ 12/2014. Sitzung um 17.30 Uhr; "
        "Herr Müller berichtet. 3 Varianten, 12,5 % Förderung."
    )
    b = belege(text)
    cases = [
        (
            "Die SPD beantragt in der BV 6 einen Radweg an der Kölner Straße für 1,5 Mio. Euro.",
            True,
        ),
        ("Bis zum 31.12.2024 soll der Radweg in Benrath gebaut werden (BV6/108/2023).", True),
        ("Der OVA hat am 15. Juni 2023 über drei Varianten mit 12,5 % Förderung beraten.", True),
        ("Verweis auf OVA/117/2023/1 und 61/12/2014; Sitzung um 17:30 Uhr.", True),
        ("Die Bezirksvertretung 6 beantragt 2 Mio. Euro.", False),  # Betrag nicht im Text
        ("Der Radweg soll bis zum 30.06.2025 fertig sein.", False),  # Datum nicht im Text
        ("Vgl. BV6/109/2023.", False),  # andere Drucksache
        ("Der Radweg führt über die Königsallee.", False),  # Ortsname nicht im Text
        ("Herr Schmitz berichtet.", False),  # Person nicht im Text
        ("Die Rheinbahn soll den Radweg planen.", False),  # seltenes Wort nicht im Text
        ("Die CDU beantragt den Radweg.", False),  # Kürzel nicht im Text
        ("Herr Müller berichtet über den Radweg in Benrath.", True),
        ("Herr Müller berichtet über den Radweg im Süden von Benrath.", False),  # Süden fehlt
        ("Die BV 6 beschließt den Radweg.", True),
    ]
    failed = 0
    for summary, expected in cases:
        found = angaben(summary, b, lex)
        ok = all(a.belegt for a in found)
        mark = "ok" if ok == expected else "FALSCH"
        failed += ok != expected
        print(f"{mark}: erwartet {'belegt' if expected else 'unbelegt'}: {summary}")
        for a in found:
            print(f"    {a.klasse}/{a.art} {a.text!r} {'belegt' if a.belegt else 'UNBELEGT'}")
    print(f"{len(cases) - failed} von {len(cases)} Fällen wie erwartet")
    return 1 if failed else 0


# --------------------------------------------------------------------------------------------
# Nachmessung in Stufe 2 (§ 5.4): frische 50, Eingabe und Prompt Fassung 2, nur `unbelegt`
# --------------------------------------------------------------------------------------------


def nachmessung_grundgesamtheit() -> tuple[pl.DataFrame, pl.DataFrame]:
    """(alle Dokumente mit Rohtext und Schicht, dieselben ohne die 400 beider Runden)."""
    settings = settings_dus()
    full = schichten(korpus(settings), load_struktur())
    frueher = set(stichprobe200(1)["id"].to_list()) | set(stichprobe200(2)["id"].to_list())
    return full, full.filter(~pl.col("id").is_in(sorted(frueher)))


def cmd_nachmessung_stichprobe(force: bool) -> int:
    """Die 50 der Nachmessung (§ 5.4): dieselbe Schichtung wie die 200, Seed SEED_NACHMESSUNG.

    Die Schichtgröße ``schicht_n`` ist die der ganzen Grundgesamtheit (wie in Runde 2): die 50
    stehen für alle Dokumente, über die der Stapellauf geht.
    """
    paths = ValidationPaths(NACHMESSUNG, VALIDIERUNG_NACH, KODIERUNG_NACH)
    if paths.sample.exists() and not force:
        print(f"{paths.sample} gibt es schon; eine Stichprobe zieht man einmal (--force)")
        return 1
    full, rest = nachmessung_grundgesamtheit()
    sizes = full.group_by("schicht").len().rename({"len": "schicht_n"})
    sample = (
        ziehen(rest, "schicht", NACHMESSUNG_N, SEED_NACHMESSUNG)
        .drop("schicht_n")
        .join(sizes, on="schicht", how="left")
        .sort("rang")
    )
    frueher = set(full["id"].to_list()) - set(rest["id"].to_list())
    assert not set(sample["id"].to_list()) & frueher
    drawn = dict(sample.group_by("schicht").len().iter_rows())
    population = dict(sizes.iter_rows())
    ids = "\n".join(sorted(rest["id"].to_list())).encode()
    write_sample(
        paths,
        sample.select("id", "schicht", "schicht_n").sort("id"),
        {
            "vorhaben": NACHMESSUNG,
            "codebuch_version": load_codebook(paths.codebook, NACHMESSUNG).version,
            "profil": "duesseldorf",
            "einheit": "document",
            "grundgesamtheit": (
                "Hauptperiode mit nicht leerem Rohtext (interim/papers.parquet über file_name an "
                "messdaten/rohtext/duesseldorf.parquet) ohne stichprobe200.csv und "
                "stichprobe200-2.csv; Prüfsumme über die sortierten IDs, je Zeile eine"
            ),
            "grundgesamtheit_sha256": hashlib.sha256(ids).hexdigest(),
            "einheiten": rest.height,
            "ohne_text": 0,
            "groesse": NACHMESSUNG_N,
            "seed": SEED_NACHMESSUNG,
            "schicht": "schicht",
            "aufteilung": "proportional",
            "selbstgewichtend": False,
            "schichten": {
                k: {"grundgesamtheit": population[k], "stichprobe": drawn.get(k, 0)}
                for k in sorted(population)
            },
            "gezogen": date.today().isoformat(),
        },
    )
    print(
        f"Nachmessung: {sample.height} Dokumente aus {rest.height} (ohne {len(frueher)} der beiden "
        f"Runden), {sample['schicht'].n_unique()} Schichten -> {paths.sample}"
    )
    return 0


# --------------------------------------------------------------------------------------------
# Alle Zahlen
# --------------------------------------------------------------------------------------------


def cmd_alles(mit_perioden: bool, runde: int = 1) -> int:
    settings = settings_dus()
    struktur = load_struktur()
    frame = korpus(settings)
    sample = stichprobe200(runde)
    inputs = eingaben(
        frame.filter(pl.col("id").is_in(sample["id"].to_list())), struktur, "duesseldorf"
    )
    corpus_lower = pl.read_parquet(
        Path(settings.data_root) / "duesseldorf" / "interim" / "papers.parquet", columns=["text"]
    ).filter(pl.col("text").fill_null("") != "")["text"]
    lex = lexikon(settings, corpus_lower)
    print(
        f"Lexikon: {len(lex.orte)} Ortsnamen, {len(lex.gremien)} Gremien, {len(lex.haeufig)} häufige Wörter (≥ {100 * SELTEN_ANTEIL:g} % von {corpus_lower.len()} Dokumenten)"
    )
    zeige_stichprobe(sample, inputs)
    known = bekannte_woerter(corpus_lower)
    checks, texts = treue(sample, inputs, lex, runde)
    zeige_treue(sample, checks, texts, inputs, runde)
    if runde == 1:
        zeige_fassung2(checks, inputs, known)
    else:
        zeige_bestaetigung(sample, checks, inputs, known)
    runs = durchsatz(sample, inputs, runde)
    models = zeige_durchsatz(runs)
    if mit_perioden and models:
        zeige_hochrechnung(models, periode_eingaben(struktur))
    if runde == 1:
        zeige_bewertung(lex, known)
        zeige_vorgaenge(lex)
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="befehl")
    sub.add_parser("selbsttest")
    st = sub.add_parser("stichprobe")
    st.add_argument("--runde", type=int, default=1, choices=(1, 2))
    run = sub.add_parser("erzeugen")
    run.add_argument("--runde", type=int, default=1, choices=(1, 2))
    run.add_argument("--modell", required=True)
    run.add_argument("--minuten", type=float, default=28.0)
    run.add_argument("--block", type=int, default=20)
    for name in ("massstab", "kodierung"):
        p = sub.add_parser(name)
        p.add_argument("--force", action="store_true")
    v = sub.add_parser("vorgaenge")
    v.add_argument("--modell", required=True)
    nach = sub.add_parser("nachmessung")
    nach_sub = nach.add_subparsers(dest="schritt", required=True)
    nach_st = nach_sub.add_parser("stichprobe")
    nach_st.add_argument("--force", action="store_true")
    alles = sub.add_parser("alles")
    alles.add_argument("--ohne-perioden", action="store_true")
    alles.add_argument("--runde", type=int, default=1, choices=(1, 2))
    args = parser.parse_args(argv)
    if args.befehl == "selbsttest":
        return cmd_selbsttest()
    if args.befehl == "stichprobe":
        return cmd_stichprobe() if args.runde == 1 else cmd_stichprobe2()
    if args.befehl == "erzeugen":
        return cmd_erzeugen(args.modell, args.minuten, args.block, runde=args.runde)
    if args.befehl == "massstab":
        return cmd_massstab(args.force)
    if args.befehl == "kodierung":
        return cmd_kodierung(args.force)
    if args.befehl == "vorgaenge":
        return cmd_vorgaenge(args.modell)
    if args.befehl == "nachmessung" and args.schritt == "stichprobe":
        return cmd_nachmessung_stichprobe(args.force)
    return cmd_alles(not getattr(args, "ohne_perioden", False), getattr(args, "runde", 1))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
