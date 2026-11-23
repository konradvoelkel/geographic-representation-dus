"""Rechnet die Zahlen von `12-kennungen.md` nach (Vorhaben 12, Stufe 1: Kennungen und Beträge).

    uv run python docs/plans/12-kennungen-messung.py [--profil duesseldorf] [--alle] [--stichprobe]

Ohne Schalter misst es die Hauptperiode (rund eine Minute auf vier Kernen); `--alle` misst dazu
2014-2020, 2025 und Mönchengladbach (Übertragbarkeit, § 3.8 des Dokuments); `--stichprobe` zieht
die Validierungsstichprobe (Seed fest) und schreibt `validierung/12-kennungen/stichprobe.csv`
(nur IDs und Spannengrenzen) sowie die Kodieraufgaben mit Textausschnitten nach
`messdaten/kodierung/12-kennungen/aufgaben.jsonl` auf xtraspace (nie ins Repo, Plan § 4).

Liest nur: den Rohtext unter `messdaten/rohtext/<profil>.parquet` (pypdf 7.1.0, Groß- und
Kleinschreibung, Zeilenumbrüche, Seitenwechsel als `\\f`; vom Supervisor am 2026-11-23
extrahiert) und die Metadaten `raw/papers.jsonl` je Profil (Dokument-ID, Dokumentart). Schreibt
nichts unter `src/` und nichts nach `data_root`.

Die Extraktoren hier sind die Messfassung, nicht der Bau: reguläre Ausdrücke, je Art eine
Funktion, Ausgabe als Spannen nach F3 (`id, start, end, kind, value, norm, section, extractor`)
und dazu `attr` (Rolle eines Betrags, Frist eines Termins). Was stadtspezifisch ist (Kopffelder,
Nummernformate der Bebauungspläne und des Haushalts), steht in `PROFILMUSTER` je Stadt und zieht
in Stufe 2 ins Profil; alles andere ist stadtneutral und zieht nach `defaults.toml`.
Offsets sind Python-Zeichenindizes (Codepunkte) in den Rohtext, gebunden an `pdf_sha256` und den
Extraktor der Messdatei.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

import polars as pl

from georep.layout import Layout
from georep.settings import load_settings

REPO = Path(__file__).resolve().parents[2]
MESSDATEN = Path("/media/konrad/xtraspace/georep/messdaten")
ROHTEXT = MESSDATEN / "rohtext"
KODIERUNG = MESSDATEN / "kodierung" / "12-kennungen"
VALIDIERUNG = REPO / "validierung" / "12-kennungen"
EXTRACTOR = "kennungen-messung-v1"
SEED = 20261123
ARBEITER = 4  # Plan § 5 und Auftrag: höchstens vier Kerne

# Rohtext-Datei -> (georep-Profil, Stadt der Muster)
PROFILE: dict[str, tuple[str, str]] = {
    "duesseldorf": ("duesseldorf", "duesseldorf"),
    "2014-2020": ("duesseldorf-2014", "duesseldorf"),
    "2025": ("duesseldorf-2025", "duesseldorf"),
    "moenchengladbach": ("moenchengladbach", "moenchengladbach"),
}

# Die sechs Arten des Briefings und ihre kinds
ARTEN: dict[str, tuple[str, ...]] = {
    "1 Bauleitplanung": ("bplan", "fnp"),
    "2 Haushalt": ("produkt", "sachkonto", "psp", "investition"),
    "3 Betrag": ("betrag",),
    "4 Termin": ("termin",),
    "5 Rechtsgrundlage": ("recht",),
    "6 Verwaltungseinheit": ("amt", "dezernat"),
}
ART_VON = {kind: art for art, kinds in ARTEN.items() for kind in kinds}

# --------------------------------------------------------------------------------------------
# Muster. Leerraum: WS ohne Zeilenwechsel, WSN mit höchstens einem.
# --------------------------------------------------------------------------------------------

WS = r"[ \t\u00a0\u202f]*"
WSN = r"[ \t\u00a0\u202f]*(?:\n[ \t\u00a0\u202f]*)?"

# Stadtspezifisch: zieht in Stufe 2 nach src/georep/profiles/<slug>.toml, [identifiers]
PROFILMUSTER: dict[str, dict[str, str]] = {
    "duesseldorf": {
        # alte Nummern Kartenblatt/lfd. Nr. (5674/26, 5374-027, 5872 011), neue Bezirk/lfd. Nr.
        # (03/017, 06-018)
        "bplan_nummer": r"\d{4}[ \t]?[/-][ \t]?\d{2,3}|\d{4} \d{3}|\d{2}[/-]\d{3}",
        # 7-stellig (2528101), mit Leerzeichen (25 28101, 55 551 02), 10-stellig (1111115019)
        "produkt": r"(?:Produkt(?:sachkonto|nummer|nr\.?)?|Profitcenter(?:/Konto/Maßnahme)?)"
        + WS
        + r":?"
        + WSN
        + r"(?P<n>\d{2,3}(?:[ \n]?\d){4,8})(?![\d.])",
        "haushaltsstelle": r"Haushaltsstelle"
        + WS
        + r":?"
        + WSN
        + r"(?P<n>\d{2}\.\d{3}\.\d{2}\.\d{3})",
        "sachkonto_schluessel": r"(?:Sach|Produktsach)?[Kk]onto(?:s)?|Kontierung|Kostenart",
        "sachkonto": r"(?<![\d.])\d{8}(?![\d]|\.\w)",
        "psp": r"PSP[- ]?Element\w*" + WS + r":?" + WSN + r"(?P<n>[1-9](?:\.[0-9A-Z]{1,8}){1,5})",
        # Investitionsmaßnahmen: PSP-Elemente, die mit 7. beginnen (7.90000278, 7.9000672.A0)
        "investition": r"(?<![\d.])(?P<n>7\.\d{7,8}(?:\.[A-Z0-9]{1,3}){0,2})(?![\d])|"
        r"Maßnahme(?:nnummer|nnr\.?)?[ \t]*:?[ \t]*(?P<m>7\d{8})(?!\d)",
        # Kopffeld der Vorlagen: federführendes Amt
        "amt_kopf": r"^[ \t]*(?:Fachbereich|Amt[ \t]*/[ \t]*Institut)[ \t]*:[ \t]*\n?[ \t]*"
        r"(?P<v>[^\n]*?\S)[ \t]*$",
        "amt_kopf_code": r"^(?P<code>\d{2}(?:/\d{1,2})?)[ \t]*[-–][ \t]*(?P<name>.+)$",
        # Kopffeld mit Namen der Beigeordneten: nur gezählt, nie extrahiert (Abschnitt 9, F6)
        "dezernent_kopf": r"^[ \t]*Dezernentin[ \t]*/[ \t]*Dezernent[ \t]*:",
    },
    "moenchengladbach": {
        # Nummer/Stadtbezirk (809/N, 793/O) oder Nummer/römische Ziffer (517/III)
        "bplan_nummer": r"\d{1,4}/(?:[NOSW]|[IVX]{1,4})(?![\w])",
        "produkt": r"Produkt" + WS + r":?" + WSN + r"(?P<n>\d{2}[ ]?\d{3}[ ]?\d{2})(?![\d])",
        "haushaltsstelle": r"(?!x)x",
        "sachkonto_schluessel": r"(?:Sach)?[Kk]onto|Kostenart",
        "sachkonto": r"(?<![\d.])\d{4}[ .]?\d{4}(?![\d])",
        "psp": r"PSP[- ]?Element\w*"
        + WS
        + r":?"
        + WSN
        + r"(?P<n>[0-9A-Z](?:[.\-][0-9A-Z]{1,8}){1,5})",
        "investition": r"\bLDI(?:-Nr\.)?" + WS + r"(?:LDI)?[- ]?" + WS + r"(?P<n>\d{3,4})(?![\d])",
        "amt_kopf": r"^[ \t]*Fachbereich[ \t]+(?P<v>[^\n]*?\S)[ \t]*$",
        "amt_kopf_code": r"^(?:FB[ \t]*)?(?P<code>\d{1,2}(?:\.\d{1,2})?)[ \t]+(?P<name>.+)$",
        "dezernent_kopf": r"(?!x)x",
    },
}

# Stadtneutral: zieht nach defaults.toml, [identifiers]
BPLAN_SCHLUESSEL = (
    r"(?:[Vv]orhabenbezogene[nrs]?[ \t]+)?"
    r"(?:Bebauungspl(?:an|äne)\w*|B-?Pl(?:an|äne)\w*|(?:Fluchtlinien|Durchführungs)pl(?:an|äne)\w*)"
    r"(?:[ \t]*[-–]?[ \t]*(?:Vor)?[Ee]ntwurf(?:s|es)?|[ \t]*[-–]?[ \t]*Vorentwurf(?:s|es)?)?"
)
FNP_SCHLUESSEL = (
    r"(?:Flächennutzungsplan(?:es|s)?[ \t]*[-–]?[ \t]*[Ää]nderung(?:en|s)?"
    r"|Flächennutzungsplanänderung(?:en)?|FNP[ \t]*[-–]?[ \t]*[Ää]nderung(?:en)?|FNP)"
)
FNP_ORDINAL = r"(?P<n>\d{1,3})\.[ \t]*[Ää]nderung[ \t]+des[ \t]+Flächennutzungsplan(?:es|s)?"
NR = r"(?:Nr\.?|Nrn\.|Nummer|No\.)[ \t]*:?"

NUM = (
    r"(?<![\d.,\w])(?P<sign>[-−])?"
    r"(?P<num>(?:\d{1,3}(?:[.\u00a0\u202f]\d{3})+|\d{2,3}(?: \d{3})+|\d+)(?:,(?:\d{1,2}|-{1,2}|–))?)(?![\d])"
)
MULT = r"(?P<mult>Mio\.?|Millionen|Million|Mrd\.?|Milliarden|Milliarde|Tsd\.?|Tausend)"
UNIT = r"(?P<unit>€|(?i:euro?)\b|TEUR\b|T€|T[ \t]?EUR\b)"
BETRAG_NACH = NUM + WSN + r"(?:" + MULT + WSN + r")?" + UNIT
BETRAG_VOR = r"(?P<unit>€|EUR\b)[ \t\u00a0]?" + NUM + r"(?:" + WS + MULT + r")?"
SPANNE_VOR = (
    r"(?<![\d.,\w])(?P<num>(?:\d{1,3}(?:[.\u00a0\u202f]\d{3})+|\d+)(?:,\d{1,2})?)"
    + WS
    + r"(?:bis(?:[ \t]+zu)?|und|-|–)"
    + WS
    + r"$"
)
JE_EINHEIT = (
    WS + r"(?:/|pro|je)" + WS + r"(?:m²|m2|qm|Quadratmeter|Monat|Jahr|Stunde|Std\.|Tag|Woche|"
    r"Person|Kopf|Einwohner\w*|Kind|Platz|Teilnehm\w*|Nacht|Stück|Fahrt|Ticket|Kilometer|km|"
    r"Meter|Haushalt|Schüler\w*|Fall|Mitglied|Wohnung|Einheit|Monatskarte|Abo|Termin)"
)
TABELLE_EINHEIT = (
    r"(?:\(|\bin[ \t]+|Beträge[ \t]+in[ \t]+)(?:T€|TEUR|EUR|Euro|€|Tsd\.?[ \t]*€)\)?|"
    r"^[ \t]*(?:EUR|Euro|€|T€|TEUR)[ \t]*$"
)
TABELLE_ZAHL = r"(?<![\d.,\w])[-−]?\d{1,3}(?:\.\d{3})+(?:,\d{2})?(?![\d,.]?\d)"

# Rollen eines Betrags; Vorrang: Verfügungsmittel im Satz, dann Einsparung nah, sonst der nächste
ROLLEN: tuple[tuple[str, str], ...] = (
    (
        "verfuegungsmittel",
        r"Verfügungsmittel\w*|bezirkliche[nr]?[ \t\n]+(?:Haushalts)?[Mm]ittel\w*|"
        r"bezirksbezogene[nr]?[ \t\n]+(?:Haushalts)?[Mm]ittel\w*|Bezirksbudget\w*|Bezirkshaushalt\w*",
    ),
    (
        "einsparung",
        r"[Ee]insparung\w*|eingespart|einzusparen|Kürzung\w*|gekürzt|zu[ \t]+kürzen|Minderaufwand\w*|"
        r"Minderausgabe\w*|Konsolidierung\w*|Haushaltsverbesserung\w*",
    ),
    (
        "foerderung",
        r"Förder(?:mittel|summe|quote|betrag|bescheid|zusage|programm|satz|richtlinie)\w*|"
        r"Landes(?:mittel|förderung|zuschuss|zuschüsse|zuwendung)\w*|"
        r"Bundes(?:mittel|förderung|zuschuss|zuschüsse)\w*|EU-(?:Mittel|Förderung)\w*|"
        r"Zuweisung\w*|Städtebauförderung\w*|Drittmittel\w*",
    ),
    (
        "zuschuss",
        r"Zuschuss\w*|Zuschüsse\w*|Zuwendung\w*|Festbetrag\w*|Fehlbedarf\w*|bezuschusst|"
        r"gewährt|gewähren|bewilligt|bewilligen|Bewilligung\w*|Förderung|fördern|gefördert|Spende\w*",
    ),
    (
        "ertrag",
        r"Ertr(?:a|ä)g\w*|Einnahme\w*|Einzahlung\w*|Erlös\w*|Gebühr\w*|Entgelt\w*|Mieteinnahme\w*|"
        r"Pacht\w*|Steuer(?:einnahme|aufkommen|ertrag)\w*|Bußgeld\w*|Verwarn\w*|Gewinn\w*|Ausschüttung\w*",
    ),
    (
        "ansatz",
        r"Haushaltsansatz\w*|Ansatz\w*|Ansätze\w*|Budget\w*|Etat\w*|veranschlagt\w*|bereitgestellt|"
        r"bereitzustellen|bereitstellen|bereit[ \t]+gestellt|Bereitstellung\w*|zur[ \t\n]+Verfügung|"
        r"Haushaltsmittel\w*|Restmittel\w*|Ermächtigung\w*|Planansatz\w*|Mittelbereitstellung\w*|"
        r"Ansatzmittel\w*|Mittel\b|Mitteln\b|Sperrvermerk\w*|Teilbetrag\w*",
    ),
    (
        "kosten",
        r"[Kk]osten\w*|kostet|Aufwand|Aufwendung\w*|Auszahlung\w*|Ausgabe\w*|Investition\w*|"
        r"Auftragswert\w*|Auftragssumme\w*|Honorar\w*|Finanzbedarf\w*|Mehrbedarf\w*|belaufen|beläuft|"
        r"Kaufpreis\w*|Gesamtsumme\w*|Beschlusssumme\w*|Baukosten\w*|Bausumme\w*|Vergabe\w*|"
        r"benötigt|\w*bedarf\w*|Finanzierung\w*|finanziert|Summe\b|Gesamt\b|insgesamt|Preis\w*|"
        r"Pauschale\w*",
    ),
)
ROLLEN_RX = [(name, re.compile(rx, re.I)) for name, rx in ROLLEN]
BETREFF_ZEICHEN = 900  # Kopf und Betreff: Quelle der Rolle, wenn der Satz keine nennt
SATZGRENZE = re.compile(r"\n[ \t]*\n|[.!?][ \t]+(?=[A-ZÄÖÜ])|:[ \t]*\n")

MONATE = {
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
    "mär": 3,
    "maerz": 3,
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
MONAT = (
    r"(?P<monat>Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|"
    r"Dezember|Jan\.|Feb\.|Mär\.|Apr\.|Jun\.|Jul\.|Aug\.|Sept?\.|Okt\.|Nov\.|Dez\.)"
)
DATUM_ZAHL = (
    r"(?<![\d.\w])(?P<tag>\d{1,2})\.[ \t]?(?P<mon>\d{1,2})\.[ \t]?(?P<jahr>(?:19|20)\d{2}|\d{2})"
    r"(?![\d]|\.\d)"
)
DATUM_TEXT = r"(?<![\d\w])(?P<tag>\d{1,2})\.?" + WS + MONAT + WS + r"(?P<jahr>(?:19|20)\d{2})(?!\d)"
MONAT_JAHR = r"(?<![\d.][ \t])(?<![\d.])" + MONAT + WS + r"(?P<jahr>(?:19|20)\d{2})(?!\d)"
QUARTAL = (
    r"(?P<q>[1-4]|I{1,3}|IV)\.?"
    + WS
    + r"(?P<art>Quartal|Halbjahr)(?:es|s)?"
    + WS
    + r"(?P<jahr>(?:19|20)\d{2})(?!\d)"
)
JAHR_QUALIFIZIERT = (
    r"(?P<q>Anfang|Mitte|Ende|Frühjahr|Frühling|Sommer|Herbst|Winter|Jahresende|Jahresmitte)"
    + WS
    + r"(?:des[ \t]+Jahres[ \t]+)?(?P<jahr>(?:19|20)\d{2})(?!\d)"
)
RELATIV: tuple[tuple[str, str], ...] = (
    (
        "relativ:naechste_sitzung",
        r"(?:in|zu|zur|bis[ \t]+zur|bis[ \t]+zu)[ \t]+(?:der|einer|den)?[ \t]*(?:der[ \t]+)?"
        r"(?:nächsten|kommenden|folgenden|übernächsten)[ \t\n]+Sitzung(?:en)?",
    ),
    ("relativ:nach_sommerpause", r"(?:nach|vor)[ \t]+der[ \t]+Sommerpause"),
    (
        "relativ:frist",
        r"innerhalb[ \t]+(?:von[ \t]+)?(?:\d+|eines|einem|zwei|drei|vier|sechs|zwölf)[ \t]+"
        r"(?:Tag|Woche|Monat|Jahr)(?:es|en|e|s)?\b",
    ),
    ("relativ:jahresende", r"bis[ \t]+(?:zum[ \t]+)?(?:Jahresende|Ende[ \t]+des[ \t]+Jahres)"),
)
FRIST_VOR = re.compile(
    r"(?:\bbis(?:[ \t]+(?:zum|spätestens|einschließlich|Ende|Anfang|Mitte))?|\bspätestens"
    r"(?:[ \t]+(?:am|zum|bis))?|\bFrist\w*(?:[ \t]+(?:bis|zum|endet[ \t]+am))?[ \t]*:?|"
    r"\bTermin[ \t]*:|\bfristgerecht(?:[ \t]+(?:bis|zum))?|"
    r"\b(?:vorzulegen|einzureichen|abzugeben|zu[ \t]+berichten)[ \t]+(?:bis(?:[ \t]+zum)?)?)"
    r"[ \t]*\n?[ \t]*(?:zum[ \t]+)?$"
)
# „vom 10.07. bis“, „1.1.2020 bis“, „November 2021 bis“: das Datum endet einen Zeitraum
ZEITRAUM_VOR = re.compile(
    r"(?:\b(?:vom|von|ab|seit|zwischen)\b[^\n]{0,30}|\d\.?|"
    r"(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"[ \t]*\d{0,4})[ \t]*$"
)
BERICHT_NACH = re.compile(
    r"berichten|vorzulegen|vorlegen|darzustellen|darstellen|informieren|Bericht|Auskunft|"
    r"vorzustellen|vorstellen|erläutern|beantworten|Sachstand"
)
SITZUNG_VOR = re.compile(
    r"(?:Sitzung\w*|Sitzungsdatum|tagt\w*)[^\n]{0,60}?(?:am|vom)?[ \t]*\n?[ \t]*$"
)

PARA = (
    r"(?:§§?|Art(?:ikel|\.)?(?=[ \t]*\d))[ \t\u00a0]*\d+"
    r"(?:[ \t]?ff\b\.?|[ \t]?f\.|[a-z](?![\w])|[ \t][a-z](?![.\w]))?(?![\w])"
    r"(?:[ \t\u00a0\n]*(?:(?:Abs(?:atz|ätze|\.)?|Satz|S\.|Nr\.?|Nummer|Ziff(?:er|\.)?|lit\.|"
    r"Buchst(?:abe|\.)?|Halbsatz|Alt(?:ernative|\.)?|Unterabs(?:atz|\.)?)[ \t\u00a0]*\n?[ \t\u00a0]*"
    r"(?:\d+[a-z]?|[a-z]\)?|[IVX]+)\b|[a-z]\)|\(\d{1,2}[a-z]?\)|[IVX]{1,4}\b(?![.\w])))*"
)
SPEZ = (
    r"(?:Abs(?:atz|ätze|\.)?|Satz|S\.|Nr\.?|Nummer|Ziff(?:er|\.)?|lit\.|Buchst(?:abe|\.)?)"
    r"[ \t\u00a0]*\n?[ \t\u00a0]*(?:\d+[a-z]?|[a-z]\)?)"
)
VERBINDER = (
    r"[ \t\u00a0\n]*(?:,|und|sowie|bzw\.|oder|bis|i\.[ \t]?V\.[ \t]?(?:m\.|mit)|in[ \t\n]+Verbindung[ \t\n]+mit|"
    r"-|–)[ \t\u00a0\n]*"
)
GESETZ_KURZ = (
    r"(?=[A-ZÄÖÜ])(?:[A-Za-zÄÖÜäöü]*[A-ZÄÖÜ][A-Za-zÄÖÜäöü]*[A-ZÄÖÜ][A-Za-zÄÖÜäöü/\-]*|GO|GG)"
    r"(?:[ \t]+(?:NRW|NW|[IVX]{1,4}))?(?![\w])"
)
GESETZ_LANG = (
    r"(?:[A-ZÄÖÜ](?:[\wäöüß\-]|-[ \t]*\n[ \t]*)*?(?:gesetzbuch|gesetz|verordnung|ordnung|satzung|richtlinien|"
    r"richtlinie|vertrag|regelung|statut)(?:es|s|en|n)?(?![\w])"
    r"(?:[ \t]+(?:für[ \t]+das[ \t]+Land[ \t]+)?(?:NRW|NW|Nordrhein-Westfalen))?)"
    r"|Sozialgesetzbuch(?:es)?[ \t]*(?:[-–][ \t]*)?(?:[IVX]{1,4}|\(?[A-ZÄÖÜ]\w+[ \t]+Buch\)?)"
    r"|(?:Satzung|Verordnung|Richtlinie|Gesetz(?:es)?|Vertrag(?:es)?)(?![\w])"
)
# „§§ 26, 27, 28 und 72 KWahlO“: nach §§ dürfen nackte Nummern folgen, nach § nicht („§ 5, 12 Mitglieder“)
RECHT = (
    r"(?:(?=§§)"
    + PARA
    + r"(?:"
    + VERBINDER
    + r"(?:"
    + PARA
    + r"|"
    + SPEZ
    + r"|\d+[a-z]?\b(?:[ \t]?ff\b\.?)?))*"
    + r"|"
    + PARA
    + r"(?:"
    + VERBINDER
    + r"(?:"
    + PARA
    + r"|"
    + SPEZ
    + r"))*)"
    + r"(?P<gesetz>"
    + WSN
    + r"(?:(?:der|des|im|in[ \t]+der|nach[ \t]+dem|gemäß|gem\.)[ \t\n]+)?"
    + r"(?:"
    + GESETZ_LANG
    + r"|"
    + GESETZ_KURZ
    + r"))?"
)
# Landesrecht und Langformen -> Kurzform; NRW-Bezug steht in defaults.toml, je Land überschreibbar
GESETZ_KANON: tuple[tuple[str, str], ...] = (
    (r"^Baugesetzbuch(?:es|s)?$|^BauGB$", "BauGB"),
    (r"^Baunutzungsverordnung$|^BauNVO$", "BauNVO"),
    (r"^(?:Landes)?[Bb]auordnung|^BauO", "BauO NRW"),
    (r"^Gemeindeordnung|^GO(?: NRW| NW)?$", "GO NRW"),
    (r"^Straßenverkehrs-?[Oo]rdnung$|^StVO$", "StVO"),
    (r"^Kommunalabgabengesetz|^KAG", "KAG NRW"),
    (r"^Kommunalhaushaltsverordnung|^KomHVO", "KomHVO NRW"),
    (r"^Schulgesetz|^SchulG", "SchulG NRW"),
    (r"^Kinderbildungsgesetz|^KiBiz", "KiBiz"),
    (r"^Gewerbeordnung$|^GewO$", "GewO"),
    (r"^Wasserhaushaltsgesetz|^WHG$", "WHG"),
    (r"^Bundes-Immissionsschutzgesetz|^BImSchG$", "BImSchG"),
    (r"^Denkmalschutzgesetz|^DSchG", "DSchG NRW"),
    (r"^Grundgesetz(?:es)?$|^GG$", "GG"),
    (r"^Bürgerliche|^BGB$", "BGB"),
    (r"^Eigenbetriebsverordnung|^EigVO", "EigVO NRW"),
    (r"^Gemeindehaushaltsverordnung|^GemHVO", "GemHVO NRW"),
    (r"^Landesgleichstellungsgesetz|^LGG", "LGG NRW"),
    (r"^Ladenöffnungsgesetz|^LÖG", "LÖG NRW"),
    (r"^Bundesnaturschutzgesetz|^BNatSchG$", "BNatSchG"),
    (r"^Landesnaturschutzgesetz|^LNatSchG", "LNatSchG NRW"),
    (r"^Straßen-? und Wegegesetz|^StrWG", "StrWG NRW"),
    (r"^Personenbeförderungsgesetz|^PBefG$", "PBefG"),
    (r"^Verwaltungsverfahrensgesetz|^VwVfG", "VwVfG"),
    (r"^Kommunalwahlgesetz|^KWahlG", "KWahlG NRW"),
    (r"^Kommunalwahlordnung|^KWahlO", "KWahlO NRW"),
    (r"^Geschäftsordnung|^GeschO$", "Geschäftsordnung"),
)
GESETZ_KANON_RX = [(re.compile(rx), kanon) for rx, kanon in GESETZ_KANON]
GESETZ_VOR = re.compile(
    r"(?<![\w])(?P<g>" + GESETZ_KURZ + r")[ \t]*\n?[ \t]*$"
)  # „In der StVO § 5“
GESETZ_NAH = re.compile(r"(?<![\w])(?P<g>" + GESETZ_LANG + r"|" + GESETZ_KURZ + r")")
SGB = re.compile(r"^(?:SGB|Sozialgesetzbuch(?:es)?)[ \t]*[-–]?[ \t]*(?P<buch>[IVX]{1,4})?")

AMT_NUMMER = r"\bAmt(?:es)?[ \t]+(?P<n>\d{2})(?:/(?P<u>\d{1,2}))?(?![\d/])"
DEZERNAT_NUMMER = r"\bDezernat(?:es|s)?[ \t]+(?P<n>\d{1,2})(?![\d/.])"
# Kopffelder, die ein Gremium statt einer Verwaltungseinheit nennen, kommen nicht ins Verzeichnis
GREMIUM = re.compile(r"(?i)ausschuss|beirat|rat\b|kommission|vertretung|konferenz|versammlung")
FB_NUMMER = r"\b(?:FB|Fachbereich(?:es|s)?)[ \t]+(?P<n>\d{1,2}(?:\.\d{1,2})?)(?![\d])"

ABSCHNITTE: tuple[tuple[str, str], ...] = (
    (
        "beschluss",
        r"Beschluss(?:vorschlag|entwurf|darstellung|empfehlung|text|fassung)\w*[ \t]*:?|Antrag[ \t]*:",
    ),
    ("begruendung", r"Sachdarstellung|Sachverhalt|Begründung|Erläuterung(?:en)?|Stellungnahme"),
    (
        "finanzen",
        r"Finanzielle[ \t]+Auswirkung(?:en)?|Finanzwirksamkeit|Kosten[ \t]+und[ \t]+Finanzierung|"
        r"Finanzierung|Haushaltsrechtliche\w*|Auswirkungen[ \t]+auf[ \t]+den[ \t]+Haushalt|Kosten",
    ),
    ("anlagen", r"Anlage(?:n)?"),
)
ABSCHNITT_RX = re.compile(
    r"^[ \t]*(?:" + "|".join(f"(?P<{name}>{rx})" for name, rx in ABSCHNITTE) + r")[ \t]*:?[ \t]*$",
    re.M,
)


@dataclass(frozen=True)
class Span:
    """Eine Spanne nach F3, dazu ``attr`` (Rolle, Frist) und ``cue`` (auslösendes Wort)."""

    doc: str  # Dateiname des PDF; die Dokument-ID kommt über papers.jsonl
    start: int
    end: int
    kind: str
    value: str
    norm: str
    section: str
    attr: str = ""
    cue: str = ""
    extractor: str = EXTRACTOR


@dataclass
class Kontext:
    """Was ein Arbeiter je Profil braucht: kompilierte Muster und das Amtsverzeichnis."""

    stadt: str
    rx: dict[str, re.Pattern[str]] = field(default_factory=dict)
    aemter: dict[str, str] = field(default_factory=dict)  # Name -> Code aus den Kopffeldern
    aemter_rx: re.Pattern[str] | None = None


def kontext_bauen(stadt: str, aemter: dict[str, str]) -> Kontext:
    m = PROFILMUSTER[stadt]
    k = Kontext(stadt=stadt, aemter=aemter)
    k.rx = {
        "bplan": re.compile(
            BPLAN_SCHLUESSEL
            + r"(?P<fill>[^\d\n.;]{0,40}?(?:\n[^\d\n.;]{0,25}?)?)"
            + r"(?:"
            + NR
            + WSN
            + r")?(?<![\w/.-])(?P<n>"
            + m["bplan_nummer"]
            + r")(?![\d/])"
        ),
        "bplan_weiter": re.compile(
            WSN
            + r"(?:,|und|sowie|bzw\.|oder)"
            + WSN
            + r"(?:"
            + NR
            + WSN
            + r")?(?<![\w/.-])(?P<n>"
            + m["bplan_nummer"]
            + r")(?![\d/])"
        ),
        "fnp": re.compile(
            FNP_SCHLUESSEL
            + WSN
            + r"(?:\((?:Vor)?[Ee]ntwurf\)"
            + WSN
            + r")?(?:"
            + NR
            + WSN
            + r")?(?P<n>\d{1,3}[a-z]?)(?![\d/.,])"
        ),
        "fnp_ordinal": re.compile(FNP_ORDINAL),
        "produkt": re.compile(m["produkt"]),
        "haushaltsstelle": re.compile(m["haushaltsstelle"]),
        "sachkonto_schluessel": re.compile(m["sachkonto_schluessel"]),
        "sachkonto": re.compile(m["sachkonto"]),
        "psp": re.compile(m["psp"]),
        "investition": re.compile(m["investition"]),
        "betrag_nach": re.compile(BETRAG_NACH),
        "betrag_vor": re.compile(BETRAG_VOR),
        "spanne_vor": re.compile(SPANNE_VOR),
        "je_einheit": re.compile(JE_EINHEIT),
        "datum_zahl": re.compile(DATUM_ZAHL),
        "datum_text": re.compile(DATUM_TEXT),
        "monat_jahr": re.compile(MONAT_JAHR),
        "quartal": re.compile(QUARTAL),
        "jahr_q": re.compile(JAHR_QUALIFIZIERT),
        "recht": re.compile(RECHT),
        "amt_kopf": re.compile(m["amt_kopf"], re.M),
        "amt_kopf_code": re.compile(m["amt_kopf_code"]),
        "amt_nummer": re.compile(AMT_NUMMER),
        "fb_nummer": re.compile(FB_NUMMER),
        "dezernat_nummer": re.compile(DEZERNAT_NUMMER),
        "dezernent_kopf": re.compile(m["dezernent_kopf"], re.M),
    }
    for name, rx in RELATIV:
        k.rx[name] = re.compile(rx)
    if aemter:
        namen = sorted(aemter, key=len, reverse=True)
        k.aemter_rx = re.compile(
            r"(?<![\w-])(?P<name>"
            + "|".join(re.escape(n).replace(r"\ ", r"[ \t\n]+") for n in namen)
            + r")(?![\w-])(?P<klammer>"
            + WS
            + r"\((?:Amt[ \t]*)?\d{2}(?:/\d{1,2})?\))?"
        )
    return k


# --------------------------------------------------------------------------------------------
# Normalisierung
# --------------------------------------------------------------------------------------------


def betrag_norm(num: str, sign: str | None, mult: str | None, unit: str) -> Decimal | None:
    """Betrag in Euro: Tausenderpunkte und -leerzeichen weg, Komma zu Punkt, ,- zu ,00."""
    roh = re.sub(r"[.\u00a0\u202f ]", "", num)
    roh = re.sub(r",(?:-{1,2}|–)$", "", roh).replace(",", ".")
    try:
        wert = Decimal(roh)
    except InvalidOperation:
        return None
    faktor = Decimal(1)
    m = (mult or "").lower()
    if m.startswith(("mio", "million")):
        faktor = Decimal(1_000_000)
    elif m.startswith(("mrd", "milliard")):
        faktor = Decimal(1_000_000_000)
    elif m.startswith(("tsd", "tausend")):
        faktor = Decimal(1000)
    if unit.replace(" ", "").upper() in {"T€", "TEUR"}:
        faktor *= 1000
    wert *= faktor
    if sign:
        wert = -wert
    return wert.quantize(Decimal("0.01"))


def bplan_norm(n: str, stadt: str) -> str:
    """Düsseldorfer alte Nummern dreistellig hinten (5674/26 -> 5674/026), Trenner einheitlich."""
    n = re.sub(r"[ \t]", "", n) if "/" in n or "-" in n else n
    if stadt == "duesseldorf":
        m = re.fullmatch(r"(\d{4})[ /-]?(\d{2,3})", n.replace(" ", "/", 1))
        if m:
            return f"{m.group(1)}/{int(m.group(2)):03d}"
        m = re.fullmatch(r"(\d{2})[/-](\d{3})", n)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    return re.sub(r"\s+", "", n).upper()


def gesetz_kanon(roh: str) -> str:
    g = re.sub(r"-[ \t]*\n[ \t]*(?=[a-zäöüß])", "", roh)
    g = re.sub(r"\s+", " ", g).strip()
    g = re.sub(r"^(?:der|des|im|in der|nach dem|gemäß|gem\.)\s+", "", g)
    m = SGB.match(g)
    if m:
        return f"SGB {m.group('buch')}" if m.group("buch") else "SGB"
    for rx, kanon in GESETZ_KANON_RX:
        if rx.search(g):
            return kanon
    return re.sub(r"(?<=[a-zäöüß])(?:es|s)$", "", g) if g.endswith(("ordnunges",)) else g


def para_kanon(roh: str) -> str:
    t = re.sub(r"[\s\u00a0]+", " ", roh).strip()
    t = re.sub(r"\bAbsatz\b|\bAbsätze\b", "Abs.", t)
    t = re.sub(r"\bSatz\b", "S.", t)
    t = re.sub(r"\bNummer\b|\bNr\b(?!\.)", "Nr.", t)
    t = re.sub(r"\bZiffer\b", "Ziff.", t)
    t = re.sub(r"\bArtikel\b", "Art.", t)
    t = re.sub(r"(§§?|Art\.|Abs\.|S\.|Nr\.|Ziff\.)\s*", r"\1 ", t)
    t = re.sub(r"i\.\s?V\.\s?m\.", "i. V. m.", t)
    return re.sub(r"\s+", " ", t).strip(" ,")


def datum_iso(tag: int, monat: int, jahr: int) -> str | None:
    if not (1 <= monat <= 12 and 1 <= tag <= 31 and 1950 <= jahr <= 2040):
        return None
    tage = [31, 29 if jahr % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][monat - 1]
    if tag > tage:
        return None
    return f"{jahr:04d}-{monat:02d}-{tag:02d}"


def jahr4(j: str) -> int:
    return int(j) if len(j) == 4 else 2000 + int(j)


# --------------------------------------------------------------------------------------------
# Abschnitte (grob; Stufe 2 nimmt sie aus Vorhaben 11)
# --------------------------------------------------------------------------------------------


def abschnitte(text: str) -> tuple[list[int], list[str]]:
    starts, names = [0], ["kopf"]
    for m in ABSCHNITT_RX.finditer(text):
        name = next(n for n, _ in ABSCHNITTE if m.group(n))
        starts.append(m.start())
        names.append(name)
    return starts, names


def abschnitt_an(pos: int, starts: list[int], names: list[str]) -> str:
    return names[bisect.bisect_right(starts, pos) - 1]


# --------------------------------------------------------------------------------------------
# Extraktoren je Art
# --------------------------------------------------------------------------------------------


def bauleitplanung(text: str, k: Kontext) -> Iterator[tuple[int, int, str, str, str, str]]:
    """(start, end, kind, norm, attr, cue): Spanne ist die Nummer, nicht das Schlüsselwort."""
    for m in k.rx["bplan"].finditer(text):
        yield m.start("n"), m.end("n"), "bplan", bplan_norm(m.group("n"), k.stadt), "", m.group(0)
        pos = m.end("n")
        while True:
            w = k.rx["bplan_weiter"].match(text, pos)
            if not w:
                break
            yield w.start("n"), w.end("n"), "bplan", bplan_norm(w.group("n"), k.stadt), "", "Liste"
            pos = w.end("n")
    for m in k.rx["fnp"].finditer(text):
        yield m.start("n"), m.end("n"), "fnp", f"FNP-Änderung {m.group('n')}", "", m.group(0)
    for m in k.rx["fnp_ordinal"].finditer(text):
        yield m.start("n"), m.end("n"), "fnp", f"FNP-Änderung {m.group('n')}", "", m.group(0)


def haushalt(text: str, k: Kontext) -> Iterator[tuple[int, int, str, str, str, str]]:
    for m in k.rx["produkt"].finditer(text):
        ziffern = re.sub(r"\D", "", m.group("n"))
        if 7 <= len(ziffern) <= 10 and len(ziffern) != 8:  # acht Ziffern sind ein Sachkonto
            yield m.start("n"), m.end("n"), "produkt", ziffern, "", m.group(0)
    for m in k.rx["haushaltsstelle"].finditer(text):
        yield m.start("n"), m.end("n"), "produkt", re.sub(r"\D", "", m.group("n")), "", "HHSt"
    for m in k.rx["sachkonto_schluessel"].finditer(text):
        fenster = text[m.end() : m.end() + 45]
        halt = re.search(r"[A-Za-zÄÖÜäöüß]{2,}", fenster)
        if halt:
            fenster = fenster[: halt.start()]
        for a in k.rx["sachkonto"].finditer(fenster):
            yield (
                m.end() + a.start(),
                m.end() + a.end(),
                "sachkonto",
                re.sub(r"\D", "", a.group(0)),
                "",
                m.group(0),
            )
    for m in k.rx["psp"].finditer(text):
        n = m.group("n").rstrip(".")
        kind = "investition" if k.stadt == "duesseldorf" and n.startswith("7.") else "psp"
        yield m.start("n"), m.start("n") + len(n), kind, n, "", "PSP-Element"
    for m in k.rx["investition"].finditer(text):
        g = "n" if m.group("n") else "m"
        n = m.group(g)
        if g == "m":
            norm = f"7.{n[1:]}"  # Maßnahme 790000724 = 7.90000724
        else:
            norm = f"LDI-{int(n):04d}" if n.isdigit() else n
        yield m.start(g), m.end(g), "investition", norm, "", m.group(0)[:12]


def rolle(text: str, s: int, e: int) -> tuple[str, str]:
    """Rolle aus dem Kontext: Fenster im Satz, Zeilenhinweis zuerst, dann Vorrang, dann Nähe."""
    lo = max(0, s - 180)
    davor = text[lo:s]
    grenzen = list(SATZGRENZE.finditer(davor))
    if grenzen:
        lo += grenzen[-1].end()
    hi = min(len(text), e + 70)
    danach = text[e:hi]
    g = SATZGRENZE.search(danach)
    if g:
        hi = e + g.start()
    fenster_vor, fenster_nach = text[lo:s], text[e:hi]
    zeile_vor = fenster_vor[fenster_vor.rfind("\n") + 1 :]
    treffer: list[tuple[float, int, str, str]] = []
    for rang, (name, rx) in enumerate(ROLLEN_RX):
        for m in rx.finditer(fenster_vor):
            abstand = len(fenster_vor) - m.end()
            if m.start() >= len(fenster_vor) - len(zeile_vor):
                abstand -= 1000  # gleiche Zeile davor: Tabellenzeile „Baukosten 82.000 EUR“
            treffer.append((abstand, rang, name, m.group(0)))
        for m in rx.finditer(fenster_nach):
            treffer.append((m.start() * 1.5 + 5, rang, name, m.group(0)))
    if not treffer:
        kopf = text[:BETREFF_ZEICHEN]
        for name, rx in ROLLEN_RX[
            :5
        ]:  # Verfügungsmittel bis Ertrag; Kosten und Ansatz zu unspezifisch
            m = rx.search(kopf)
            if m:
                return name + ";dok", m.group(0)
        return "sonstig", ""
    namen = {t[2] for t in treffer}
    if "verfuegungsmittel" in namen:
        t = min(x for x in treffer if x[2] == "verfuegungsmittel")
        return t[2], t[3]
    nah_einsparung = [x for x in treffer if x[2] == "einsparung" and x[0] < 60]
    if nah_einsparung:
        t = min(nah_einsparung)
        return t[2], t[3]
    t = min(treffer)
    return t[2], t[3]


def betraege(text: str, k: Kontext) -> Iterator[tuple[int, int, str, str, str, str]]:
    belegt: list[tuple[int, int]] = []
    einheiten: set[int] = set()
    funde: list[tuple[int, int, Decimal, str]] = []
    for m in k.rx["betrag_nach"].finditer(text):
        wert = betrag_norm(m.group("num"), m.group("sign"), m.group("mult"), m.group("unit"))
        if wert is None:
            continue
        s = m.start("sign") if m.group("sign") else m.start("num")
        funde.append((s, m.end(), wert, "nach"))
        belegt.append((s, m.end()))
        einheiten.update(range(m.start("unit"), m.end("unit")))
        # Spanne „5.000 bis 10.000 Euro“: die erste Zahl erbt Einheit und Faktor
        v = k.rx["spanne_vor"].search(text, max(0, s - 40), s)
        if v and not re.fullmatch(r"(?:19|20)\d{2}", v.group("num")):
            w = betrag_norm(v.group("num"), None, m.group("mult"), m.group("unit"))
            if w is not None:
                funde.append((v.start("num"), v.end("num"), w, "spanne"))
                belegt.append((v.start("num"), v.end("num")))
    for m in k.rx["betrag_vor"].finditer(text):
        if m.start("unit") in einheiten:
            continue
        if re.fullmatch(r"(?:19|20)\d{2}", m.group("num")):
            continue
        if any(a < m.end() and m.start() < b for a, b in belegt):
            continue
        wert = betrag_norm(m.group("num"), m.group("sign"), m.group("mult"), m.group("unit"))
        if wert is None:
            continue
        funde.append((m.start(), m.end(), wert, "vor"))
        belegt.append((m.start(), m.end()))
    for s, e, wert, form in funde:
        r, cue = rolle(text, s, e)
        je = bool(k.rx["je_einheit"].match(text, e))
        attr = r + (";je" if je else "") + (";spanne" if form == "spanne" else "")
        yield s, e, "betrag", f"{wert}", attr, cue


def tabellen_kandidaten(text: str, belegt: list[tuple[int, int]]) -> tuple[int, int]:
    """Zahlen mit Tausenderpunkt ohne eigene Einheit in Dokumenten mit Einheitenkopf."""
    if not re.search(TABELLE_EINHEIT, text, re.M):
        return 0, 0
    starts = sorted(a for a, _ in belegt)
    frei = 0
    alle = 0
    for m in re.finditer(TABELLE_ZAHL, text):
        alle += 1
        i = bisect.bisect_right(starts, m.start()) - 1
        if i >= 0 and any(a <= m.start() < b for a, b in belegt[max(0, i - 3) : i + 4]):
            continue
        frei += 1
    return frei, alle


def termine(text: str, k: Kontext) -> Iterator[tuple[int, int, str, str, str, str]]:
    belegt: list[tuple[int, int]] = []

    def frei(s: int, e: int) -> bool:
        return not any(a < e and s < b for a, b in belegt)

    def art(s: int) -> tuple[str, str]:
        davor = text[max(0, s - 45) : s]
        f = FRIST_VOR.search(davor)
        if f:
            vorher = text[max(0, s - 45 - 30) : s - len(davor) + f.start()]
            if f.group(0).lstrip().startswith("bis") and ZEITRAUM_VOR.search(vorher):
                return "zeitraum", f.group(0).strip()  # „vom 10.07. bis zum 17.07.2022“
            return "frist", f.group(0).strip()
        if SITZUNG_VOR.search(text[max(0, s - 80) : s]):
            return "sitzung", ""
        return "sonst", ""

    for m in k.rx["datum_text"].finditer(text):
        monat = MONATE.get(m.group("monat").lower().rstrip("."))
        iso = datum_iso(int(m.group("tag")), monat or 0, int(m.group("jahr")))
        if iso:
            belegt.append((m.start(), m.end()))
            a, cue = art(m.start())
            yield m.start(), m.end(), "termin", iso, a + ";tag", cue
    for m in k.rx["datum_zahl"].finditer(text):
        tag, mon, j = m.group("tag"), m.group("mon"), m.group("jahr")
        if len(j) == 2 and (len(tag) != 2 or len(mon) != 2):
            continue  # „3.2.10“ ist eher eine Gliederungsnummer
        iso = datum_iso(int(tag), int(mon), jahr4(j))
        if iso and frei(m.start(), m.end()):
            belegt.append((m.start(), m.end()))
            a, cue = art(m.start())
            yield m.start(), m.end(), "termin", iso, a + ";tag", cue
    for m in k.rx["quartal"].finditer(text):
        q = m.group("q")
        q = {"I": "1", "II": "2", "III": "3", "IV": "4"}.get(q, q)
        if m.group("art").startswith("Halb") and q not in {"1", "2"}:
            continue
        norm = f"{m.group('jahr')}-{'Q' if m.group('art').startswith('Q') else 'H'}{q}"
        if frei(m.start(), m.end()):
            belegt.append((m.start(), m.end()))
            a, cue = art(m.start())
            yield m.start(), m.end(), "termin", norm, a + ";quartal", cue
    for m in k.rx["monat_jahr"].finditer(text):
        monat = MONATE.get(m.group("monat").lower().rstrip("."))
        if monat and frei(m.start(), m.end()):
            belegt.append((m.start(), m.end()))
            a, cue = art(m.start())
            yield m.start(), m.end(), "termin", f"{m.group('jahr')}-{monat:02d}", a + ";monat", cue
    for m in k.rx["jahr_q"].finditer(text):
        if frei(m.start(), m.end()):
            belegt.append((m.start(), m.end()))
            a, cue = art(m.start())
            q = m.group("q").lower()
            yield m.start(), m.end(), "termin", f"{m.group('jahr')}~{q}", a + ";jahr", cue
    for name, _ in RELATIV:
        for m in k.rx[name].finditer(text):
            if frei(m.start(), m.end()):
                belegt.append((m.start(), m.end()))
                a, cue = art(m.start())
                if name == "relativ:naechste_sitzung" and a == "sonst":
                    # „in der nächsten Sitzung zu berichten“ ist eine Frist, „… zu beschließen“ ein Termin
                    a = "frist" if BERICHT_NACH.search(text, m.end(), m.end() + 120) else "sitzung"
                elif name in {"relativ:frist", "relativ:jahresende"} and a == "sonst":
                    a = "frist"
                yield m.start(), m.end(), "termin", name, a + ";relativ", cue


def rechtsgrundlagen(text: str, k: Kontext) -> Iterator[tuple[int, int, str, str, str, str]]:
    for m in k.rx["recht"].finditer(text):
        gesetz = m.group("gesetz")
        kette_ende = m.start("gesetz") if gesetz else m.end()
        kette = para_kanon(text[m.start() : kette_ende])
        if gesetz:
            kanon = gesetz_kanon(gesetz)
            yield m.start(), m.end(), "recht", f"{kanon} {kette}", "gesetz", ""
        else:
            ende = m.start() + len(text[m.start() : m.end()].rstrip(" \t\n,"))
            nah = GESETZ_NAH.search(text, ende, min(len(text), ende + 60))
            if nah and not re.search(r"[.;:]\s|\n\s*\n|§", text[ende : nah.start()]):
                kanon = gesetz_kanon(nah.group("g"))
                yield m.start(), ende, "recht", f"{kanon} {kette}", "gesetz_nah", nah.group("g")
            else:
                vor = GESETZ_VOR.search(text, max(0, m.start() - 40), m.start())
                if vor:
                    kanon = gesetz_kanon(vor.group("g"))
                    yield m.start(), ende, "recht", f"{kanon} {kette}", "gesetz_vor", vor.group("g")
                else:
                    yield m.start(), ende, "recht", f"? {kette}", "ohne_gesetz", ""


def kopf_amt(v: str, k: Kontext) -> tuple[str, str] | None:
    """(Code, Name) aus einem Kopffeld; Bezirksverwaltungsstellen ohne Nummer behalten den Namen."""
    m = k.rx["amt_kopf_code"].match(v.strip())
    if m:
        return m.group("code"), re.sub(r"\s+", " ", m.group("name")).strip()
    v = re.sub(r"\s+", " ", v).strip()
    if len(v) >= 4 and not v.endswith(":"):
        return v, v
    return None


def verwaltung(text: str, k: Kontext) -> Iterator[tuple[int, int, str, str, str, str]]:
    belegt: list[tuple[int, int]] = []
    for m in k.rx["amt_kopf"].finditer(text[:6000]):
        r = kopf_amt(m.group("v"), k)
        if r:
            belegt.append((m.start("v"), m.end("v")))
            yield m.start("v"), m.end("v"), "amt", r[0], "kopf", ""
    if k.aemter_rx is not None:
        for m in k.aemter_rx.finditer(text):
            if any(a < m.end() and m.start() < b for a, b in belegt):
                continue
            if re.search(
                r"(?:Ausschuss(?:es)?|Beirat(?:s|es)?)[ \t\n]+für[ \t\n]+(?:die[ \t]+|den[ \t]+)?$",
                text[max(0, m.start() - 30) : m.start()],
            ):
                continue  # „Ausschuss für Umwelt“ nennt ein Gremium, kein Amt
            name = re.sub(r"\s+", " ", m.group("name"))
            belegt.append((m.start(), m.end()))
            yield m.start(), m.end(), "amt", k.aemter[name], "name", ""
    for m in k.rx["amt_nummer"].finditer(text):
        if any(a < m.end() and m.start() < b for a, b in belegt):
            continue
        norm = m.group("n") + (f"/{m.group('u')}" if m.group("u") else "")
        yield m.start(), m.end(), "amt", norm, "nummer", ""
    if k.stadt != "duesseldorf":
        for m in k.rx["fb_nummer"].finditer(text):
            if any(a < m.end() and m.start() < b for a, b in belegt):
                continue
            yield m.start(), m.end(), "amt", m.group("n"), "nummer", ""
    for m in k.rx["dezernat_nummer"].finditer(text):
        yield m.start(), m.end(), "dezernat", f"{int(m.group('n')):02d}", "nummer", ""


EXTRAKTOREN: tuple[Callable[[str, Kontext], Iterator[tuple[int, int, str, str, str, str]]], ...] = (
    bauleitplanung,
    haushalt,
    betraege,
    termine,
    rechtsgrundlagen,
    verwaltung,
)


@dataclass
class DokErgebnis:
    name: str
    spans: list[Span]
    tabelle_frei: int
    tabelle_alle: int
    dezernent_kopf: bool


def dokument(name: str, text: str, k: Kontext) -> DokErgebnis:
    starts, names = abschnitte(text)
    spans: list[Span] = []
    for fn in EXTRAKTOREN:
        for s, e, kind, norm, attr, cue in fn(text, k):
            assert 0 <= s < e <= len(text), (name, s, e, kind)
            spans.append(
                Span(
                    doc=name,
                    start=s,
                    end=e,
                    kind=kind,
                    value=text[s:e],
                    norm=norm,
                    section=abschnitt_an(s, starts, names),
                    attr=attr,
                    cue=re.sub(r"\s+", " ", cue)[:40],
                )
            )
    spans.sort(key=lambda x: (x.start, x.end, x.kind))
    betrag = [(x.start, x.end) for x in spans if x.kind == "betrag"]
    frei, alle = tabellen_kandidaten(text, betrag)
    dez = bool(k.rx["dezernent_kopf"].search(text[:6000]))
    return DokErgebnis(name, spans, frei, alle, dez)


_K: Kontext | None = None


def _init(stadt: str, aemter: dict[str, str]) -> None:
    global _K
    _K = kontext_bauen(stadt, aemter)


def _stapel(paare: Sequence[tuple[str, str]]) -> list[DokErgebnis]:
    assert _K is not None
    return [dokument(n, t, _K) for n, t in paare]


# --------------------------------------------------------------------------------------------
# Laden
# --------------------------------------------------------------------------------------------


def rohtext(profil: str) -> pl.DataFrame:
    return (
        pl.read_parquet(ROHTEXT / f"{profil}.parquet")
        .filter(pl.col("text").is_not_null())
        .sort("name")
    )


def metadaten(profil: str) -> pl.DataFrame:
    """Eine Zeile je Datei: Dokument-ID (kleinste, falls mehrere Paper dieselbe Datei tragen)."""
    settings = load_settings(profile=PROFILE[profil][0])
    layout = Layout.from_settings(settings)
    zeilen = [json.loads(z) for z in layout.papers.read_text(encoding="utf-8").splitlines() if z]
    df = pl.DataFrame(
        {
            "file_name": [z.get("file_name") for z in zeilen],
            "id": [z.get("id") for z in zeilen],
            "paper_type": [z.get("paper_type") or "" for z in zeilen],
            "title": [z.get("name") or "" for z in zeilen],
            "date": [z.get("date") or "" for z in zeilen],
        }
    ).filter(pl.col("file_name").is_not_null())
    return df.sort("id").group_by("file_name", maintain_order=True).first().sort("file_name")


def amtsverzeichnis(df: pl.DataFrame, stadt: str) -> tuple[dict[str, str], dict[str, Counter[str]]]:
    """Name -> häufigster Code aus den Kopffeldern des Korpus selbst (kein Stadtwort im Code)."""
    k = kontext_bauen(stadt, {})
    je_name: dict[str, Counter[str]] = defaultdict(Counter)
    for text in df["text"]:
        for m in k.rx["amt_kopf"].finditer(text[:6000]):
            r = kopf_amt(m.group("v"), k)
            if r and r[0] != r[1]:
                je_name[r[1]][r[0]] += 1
    verzeichnis = {
        name: c.most_common(1)[0][0]
        for name, c in je_name.items()
        if sum(c.values()) >= 3
        and (len(name) >= 8 or "amt" in name.lower())  # „Umwelt“, „BV Ost“: zu allgemein
        and not GREMIUM.search(name)
    }
    return verzeichnis, je_name


def extrahieren(
    profil: str,
) -> tuple[pl.DataFrame, list[DokErgebnis], dict[str, str], dict[str, Counter[str]]]:
    df = rohtext(profil)
    stadt = PROFILE[profil][1]
    aemter, je_name = amtsverzeichnis(df, stadt)
    paare = list(zip(df["name"].to_list(), df["text"].to_list(), strict=True))
    stapel = [paare[i : i + 400] for i in range(0, len(paare), 400)]
    ergebnisse: list[DokErgebnis] = []
    with ProcessPoolExecutor(ARBEITER, initializer=_init, initargs=(stadt, aemter)) as ex:
        for teil in ex.map(_stapel, stapel):
            ergebnisse.extend(teil)
    return df, ergebnisse, aemter, je_name


def spans_frame(ergebnisse: Iterable[DokErgebnis]) -> pl.DataFrame:
    zeilen = [s for e in ergebnisse for s in e.spans]
    return pl.DataFrame(
        {
            "name": [s.doc for s in zeilen],
            "start": [s.start for s in zeilen],
            "end": [s.end for s in zeilen],
            "kind": [s.kind for s in zeilen],
            "value": [s.value for s in zeilen],
            "norm": [s.norm for s in zeilen],
            "section": [s.section for s in zeilen],
            "attr": [s.attr for s in zeilen],
            "cue": [s.cue for s in zeilen],
            "extractor": [s.extractor for s in zeilen],
        },
        schema_overrides={"start": pl.Int64, "end": pl.Int64},
    ).with_columns(pl.col("kind").replace_strict(ART_VON).alias("art"))


# --------------------------------------------------------------------------------------------
# Bericht
# --------------------------------------------------------------------------------------------


def pct(a: float, b: float) -> str:
    return f"{100 * a / b:.1f} %" if b else "–"


def bericht(
    profil: str,
    df: pl.DataFrame,
    sp: pl.DataFrame,
    erg: list[DokErgebnis],
    aemter: dict[str, str],
    je_name: dict[str, Counter[str]],
    meta: pl.DataFrame,
    ausfuehrlich: bool,
) -> None:
    n_dok = df.height
    print(f"\n=== {profil}: {n_dok} Dokumente mit Text, {df['chars'].sum():,} Zeichen ===")
    print(f"{'kind':<12}{'Treffer':>9}{'Dok.':>8}{'Anteil':>9}{'versch.':>9}  häufigste norm")
    for art, kinds in ARTEN.items():
        print(f"-- {art}")
        for kind in kinds:
            t = sp.filter(pl.col("kind") == kind)
            docs = t["name"].n_unique()
            top = t["norm"].value_counts(sort=True).head(3)
            tops = ", ".join(f"{a} ({b})" for a, b in top.iter_rows())
            print(
                f"{kind:<12}{t.height:>9}{docs:>8}{pct(docs, n_dok):>9}{t['norm'].n_unique():>9}  {tops}"
            )
    if not ausfuehrlich:
        return
    j = sp.join(
        meta.select("file_name", "paper_type"), left_on="name", right_on="file_name", how="left"
    )
    typen = meta.join(df.select("name"), left_on="file_name", right_on="name")["paper_type"]
    gross = typen.value_counts(sort=True).head(8)["paper_type"].to_list()
    print("\nAnteil der Dokumente mit mindestens einem Treffer je Art, nach Dokumentart:")
    print(f"{'Dokumentart':<40}" + "".join(f"{a.split()[0]:>7}" for a in ARTEN) + "      n")
    for typ in gross:
        n = int((typen == typ).sum())
        zeile = f"{typ[:39]:<40}"
        for art in ARTEN:
            d = j.filter((pl.col("paper_type") == typ) & (pl.col("art") == art))["name"].n_unique()
            zeile += f"{100 * d / n:>6.0f}%"
        print(zeile + f"{n:>7}")

    # Art 1
    b = sp.filter(pl.col("kind") == "bplan").with_columns(
        pl.col("value").str.replace_all(r"\s", "").alias("roh")
    )
    var = b.group_by("norm").agg(pl.col("roh").n_unique().alias("formen"))
    print(
        f"\nArt 1: {b['norm'].n_unique()} Bebauungspläne, davon {var.filter(pl.col('formen') > 1).height} "
        f"in mehr als einer Schreibweise; Listenfortsetzungen {b.filter(pl.col('cue') == 'Liste').height}"
    )
    print(
        "  Schreibweisen je norm (Beispiele):",
        b.filter(
            pl.col("norm").is_in(var.filter(pl.col("formen") > 1)["norm"].sort().head(4).implode())
        )
        .group_by("norm")
        .agg(pl.col("roh").unique().sort())
        .sort("norm")
        .rows()[:4],
    )
    # Recall-Näherung: Plannummern-Form in Dokumenten mit Bebauungsplan-Wort, die keine Spanne trifft
    stadt = PROFILE[profil][1]
    form = re.compile(r"(?<![\w/.-])(?:" + PROFILMUSTER[stadt]["bplan_nummer"] + r")(?![\d/])")
    bpl_wort = re.compile(r"Bebauungspl|B-Pl")
    belegt = defaultdict(list)
    for r in b.select("name", "start", "end").iter_rows():
        belegt[r[0]].append((r[1], r[2]))
    frei, kandidaten = 0, 0
    beispiele: list[str] = []
    for name, text in zip(df["name"], df["text"], strict=True):
        if not bpl_wort.search(text):
            continue
        for m in form.finditer(text):
            kandidaten += 1
            if not any(a <= m.start() < e for a, e in belegt[name]):
                frei += 1
                if len(beispiele) < 6:
                    beispiele.append(text[max(0, m.start() - 50) : m.end() + 10].replace("\n", "⏎"))
    print(
        f"  Nummernform in Dokumenten mit Planwort: {kandidaten}, davon ohne Spanne {frei} "
        f"({pct(frei, kandidaten)})"
    )
    for x in beispiele:
        print("   ", x)

    # Art 2
    h = sp.filter(pl.col("art") == "2 Haushalt")
    pr = h.filter(pl.col("kind") == "produkt")
    print(
        f"\nArt 2: Produkte {pr.height} ({pr['norm'].n_unique()} versch.), davon 7-stellig "
        f"{pr.filter(pl.col('norm').str.len_chars() == 7).height}; Produktbereiche (2 Ziffern): "
        f"{pr.filter(pl.col('norm').str.len_chars() == 7)['norm'].str.slice(0, 2).n_unique()}"
    )

    # Art 3
    bt = sp.filter(pl.col("kind") == "betrag").with_columns(
        pl.col("attr").str.split(";").list.first().alias("rolle"),
        pl.col("attr").str.contains(";je").alias("je"),
        pl.col("attr").str.contains(";spanne").alias("spanne"),
        pl.col("norm").cast(pl.Float64).alias("eur"),
    )
    print(f"\nArt 3: {bt.height} Beträge in {bt['name'].n_unique()} Dokumenten")
    for r in bt["rolle"].value_counts(sort=True).iter_rows():
        print(f"  Rolle {r[0]:<18}{r[1]:>7}  {pct(r[1], bt.height)}")
    mio = bt.filter(pl.col("value").str.contains(r"Mio|Million|Mrd|Milliard")).height
    tsd = bt.filter(pl.col("value").str.contains(r"T€|TEUR|Tsd|Tausend")).height
    vor = bt.filter(pl.col("value").str.contains(r"^(?:€|EUR)")).height
    print(
        f"  je Einheit {bt['je'].sum()}, Spannen (erste Zahl) {bt['spanne'].sum()}, Mio./Mrd. {mio}, "
        f"Tsd./T€ {tsd}, Einheit vorn {vor}, Nullbeträge {bt.filter(pl.col('eur') == 0).height}"
    )
    print(
        "  Größenordnung (Median, 90 %, Max):",
        bt["eur"].median(),
        bt["eur"].quantile(0.9),
        bt["eur"].max(),
    )
    for r in bt["section"].value_counts(sort=True).iter_rows():
        print(f"  Abschnitt {r[0]:<14}{r[1]:>7}")
    frei = sum(e.tabelle_frei for e in erg)
    alle = sum(e.tabelle_alle for e in erg)
    mit = sum(1 for e in erg if e.tabelle_alle)
    print(
        f"  Tabellenzahlen ohne eigene Einheit in {mit} Dokumenten mit Einheitenkopf: {frei} "
        f"(von {alle} Zahlen mit Tausenderpunkt dort)"
    )

    # Art 4
    tm = sp.filter(pl.col("kind") == "termin").with_columns(
        pl.col("attr").str.split(";").list.get(0).alias("rolle"),
        pl.col("attr").str.split(";").list.get(1).alias("form"),
    )
    print(f"\nArt 4: {tm.height} Termine")
    for r in tm.group_by("form", "rolle").len().sort("form", "rolle").iter_rows():
        print(f"  {r[0]:<9}{r[1]:<9}{r[2]:>8}")
    print(
        "  Frist-Auslöser:",
        tm.filter(pl.col("rolle") == "frist")["cue"].value_counts(sort=True).head(8).rows(),
    )

    # Art 5
    rc = sp.filter(pl.col("kind") == "recht").with_columns(
        pl.col("norm").str.extract(r"^(.*?) (?:§|Art\.)", 1).alias("gesetz")
    )
    ohne = rc.filter(pl.col("attr") == "ohne_gesetz").height
    print(f"\nArt 5: {rc.height} Zitate, ohne erkanntes Gesetz {ohne} ({pct(ohne, rc.height)})")
    print(
        "  Gesetze:",
        rc.filter(pl.col("attr") == "gesetz")["gesetz"].value_counts(sort=True).head(20).rows(),
    )

    # Art 6
    am = sp.filter(pl.col("kind") == "amt")
    kopf = am.filter(pl.col("attr") == "kopf")
    print(
        f"\nArt 6: Ämter {am.height} (Kopf {kopf.height}, Name {am.filter(pl.col('attr') == 'name').height}, "
        f"Nummer {am.filter(pl.col('attr') == 'nummer').height}); Dezernate "
        f"{sp.filter(pl.col('kind') == 'dezernat').height}"
    )
    print(
        f"  Amtsverzeichnis aus Kopffeldern: {len(aemter)} Namen; mehrdeutig (mehr als ein Code): "
        f"{sum(1 for n in aemter if len(je_name[n]) > 1)}"
    )
    kd = kopf["name"].n_unique()
    print(
        f"  Dokumente mit Amt im Kopf: {kd} ({pct(kd, n_dok)}); mit Dezernentenfeld: "
        f"{sum(e.dezernent_kopf for e in erg)}"
    )
    jk = kopf.join(meta.select("file_name", "paper_type"), left_on="name", right_on="file_name")
    for typ in gross:
        n = int((typen == typ).sum())
        d = jk.filter(pl.col("paper_type") == typ)["name"].n_unique()
        print(f"    {typ[:40]:<42}{pct(d, n):>8}")


def groesse_ausgabe(sp: pl.DataFrame) -> None:
    """Größe der Ausgabe von Stufe 2 (ohne die Messspalten cue und art), im Speicher geschrieben."""
    aus = sp.drop("cue", "art")
    for name, teil in (("alle", aus), ("ohne Termine", aus.filter(pl.col("kind") != "termin"))):
        pq, cs = io.BytesIO(), io.BytesIO()
        teil.write_parquet(pq, compression="zstd")
        teil.write_csv(cs)
        print(
            f"  Ausgabe {name}: {teil.height} Zeilen, Parquet {pq.tell()} Bytes, CSV {cs.tell()} Bytes"
        )


# --------------------------------------------------------------------------------------------
# Stichprobe und Kodieraufgaben
# --------------------------------------------------------------------------------------------

PRAEZISION_JE_ART = 100
RECALL_DOKUMENTE = 50
RECALL_MAX_ZEICHEN = 12_000
AUSSCHNITT = 400  # Zeichen links und rechts der Markierung


def schichten_quoten(groessen: dict[str, int], n: int, mindest: int) -> dict[str, int]:
    """Proportional mit Mindestzahl je Schicht; Rest nach größten Bruchteilen."""
    schichten = sorted(k for k, v in groessen.items() if v > 0)
    quote = {s: min(MINDEST_SCHICHT.get(s, mindest), groessen[s]) for s in schichten}
    rest = n - sum(quote.values())
    gesamt = sum(groessen[s] - quote[s] for s in schichten)
    if rest > 0 and gesamt > 0:
        roh = {s: rest * (groessen[s] - quote[s]) / gesamt for s in schichten}
        for s in schichten:
            quote[s] += int(roh[s])
        uebrig = n - sum(quote.values())
        for s in sorted(schichten, key=lambda s: -(roh[s] - int(roh[s])))[:uebrig]:
            quote[s] += 1
    return {s: min(q, groessen[s]) for s, q in quote.items()}


def schicht_von(art: str, kind: str, attr: str, section: str) -> str:
    if art == "3 Betrag":
        return "betrag:" + attr.split(";")[0]
    if art == "4 Termin":
        rolle_, form = attr.split(";")[:2]
        return f"termin:{'frist' if rolle_ == 'frist' else form}"
    if art == "5 Rechtsgrundlage":
        return f"recht:{attr}"
    if art == "6 Verwaltungseinheit":
        return f"{kind}:{attr}"
    return kind


# Die Frist ist das Merkmal, das 29 (Wiedervorlage) braucht; 30 Fälle geben ihr ein eigenes Maß
MINDEST_SCHICHT = {"termin:frist": 30}
MINDEST = {
    "1 Bauleitplanung": 25,
    "2 Haushalt": 15,
    "3 Betrag": 10,
    "4 Termin": 12,
    "5 Rechtsgrundlage": 20,
    "6 Verwaltungseinheit": 15,
}


def stichprobe(df: pl.DataFrame, sp: pl.DataFrame, meta: pl.DataFrame) -> None:
    rng = random.Random(SEED)
    texte = dict(zip(df["name"].to_list(), df["text"].to_list(), strict=True))
    sha = dict(zip(df["name"].to_list(), df["pdf_sha256"].to_list(), strict=True))
    ids = dict(zip(meta["file_name"].to_list(), meta["id"].to_list(), strict=True))
    zeilen: list[dict[str, object]] = []
    aufgaben: list[dict[str, object]] = []
    sp = sp.with_columns(
        pl.struct("art", "kind", "attr", "section")
        .map_elements(
            lambda r: schicht_von(r["art"], r["kind"], r["attr"], r["section"]),
            return_dtype=pl.String,
        )
        .alias("schicht")
    ).sort("name", "start", "end", "kind")
    print("\nStichprobe (Präzision): Schichten und Quoten je Art")
    for art in ARTEN:
        t = sp.filter(pl.col("art") == art)
        groessen = dict(t["schicht"].value_counts().iter_rows())
        quoten = schichten_quoten(groessen, PRAEZISION_JE_ART, MINDEST[art])
        print(f"  {art}: " + ", ".join(f"{s} {q}/{groessen[s]}" for s, q in sorted(quoten.items())))
        for schicht, q in sorted(quoten.items()):
            kandidaten = t.filter(pl.col("schicht") == schicht).rows(named=True)
            for r in rng.sample(kandidaten, q):
                text = texte[r["name"]]
                lo, hi = max(0, r["start"] - AUSSCHNITT), min(len(text), r["end"] + AUSSCHNITT)
                zeilen.append(
                    {
                        "typ": "praezision",
                        "art": art,
                        "schicht": schicht,
                        "schicht_n": groessen[schicht],
                        "dok_id": ids.get(r["name"], ""),
                        "datei": r["name"],
                        "start": r["start"],
                        "end": r["end"],
                    }
                )
                aufgaben.append(
                    {
                        "typ": "praezision",
                        "dok_id": ids.get(r["name"], ""),
                        "datei": r["name"],
                        "pdf_sha256": sha[r["name"]],
                        "rohtext": "messdaten/rohtext/duesseldorf.parquet (pypdf-7.1.0 roh)",
                        "ausschnitt_start": lo,
                        "ausschnitt": text[lo : r["start"]]
                        + "⟦"
                        + text[r["start"] : r["end"]]
                        + "⟧"
                        + text[r["end"] : hi],
                        "markierung": {
                            "start": r["start"],
                            "end": r["end"],
                            "text": text[r["start"] : r["end"]],
                        },
                        "fragen": ["art", "grenzen", "norm", "rolle", "frist"],
                    }
                )
    # Recall: 50 Dokumente, geschichtet nach Metadaten und Titelwörtern, nicht nach Extraktor
    m = meta.join(df.select("name", "chars"), left_on="file_name", right_on="name")
    m = m.filter((pl.col("chars") >= 300) & (pl.col("chars") <= RECALL_MAX_ZEICHEN)).sort(
        "file_name"
    )
    titel = pl.col("title").str.to_lowercase()
    typ = pl.col("paper_type").str.to_lowercase()
    schichten = {
        "planung": titel.str.contains(r"bebauungsplan|flächennutzungsplan|b-plan|bauleitplan"),
        "haushalt": typ.str.contains("haushalt")
        | titel.str.contains(r"haushalt|verfügungsmittel|zuschuss|förder|finanz|investition"),
        "bezirk": typ.str.contains("bezirksvertretung"),
        "fraktion": typ.str.contains(r"^(?:antrag|anfrage)"),
    }
    gezogen: set[str] = set()
    print("\nStichprobe (Recall): je Schicht 10 Dokumente")
    for name, bedingung in [*schichten.items(), ("zufall", pl.lit(True))]:
        pool = [f for f in m.filter(bedingung)["file_name"].to_list() if f not in gezogen]
        wahl = rng.sample(pool, 10)
        gezogen.update(wahl)
        print(f"  {name}: Pool {len(pool)}")
        for f in wahl:
            text = texte[f]
            zeilen.append(
                {
                    "typ": "recall",
                    "art": "alle",
                    "schicht": name,
                    "schicht_n": len(pool),
                    "dok_id": ids.get(f, ""),
                    "datei": f,
                    "start": 0,
                    "end": len(text),
                }
            )
            aufgaben.append(
                {
                    "typ": "recall",
                    "dok_id": ids.get(f, ""),
                    "datei": f,
                    "pdf_sha256": sha[f],
                    "rohtext": "messdaten/rohtext/duesseldorf.parquet (pypdf-7.1.0 roh)",
                    "text": text,
                    "fragen": ["alle_spannen"],
                }
            )
    reihenfolge = list(range(len(zeilen)))
    rng.shuffle(reihenfolge)
    VALIDIERUNG.mkdir(parents=True, exist_ok=True)
    KODIERUNG.mkdir(parents=True, exist_ok=True)
    felder = ["aufgabe", "typ", "art", "schicht", "schicht_n", "dok_id", "datei", "start", "end"]
    with (VALIDIERUNG / "stichprobe.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=felder, lineterminator="\n")
        w.writeheader()
        for nr, i in enumerate(reihenfolge, 1):
            w.writerow({"aufgabe": f"12-{nr:04d}", **zeilen[i]})
    with (KODIERUNG / "aufgaben.jsonl").open("w", encoding="utf-8") as f:
        for nr, i in enumerate(reihenfolge, 1):
            f.write(
                json.dumps({"aufgabe": f"12-{nr:04d}", **aufgaben[i]}, ensure_ascii=False) + "\n"
            )
    (KODIERUNG / "antworten-leer.jsonl").write_text("", encoding="utf-8")
    print(
        f"  geschrieben: {VALIDIERUNG / 'stichprobe.csv'} ({len(zeilen)} Zeilen), "
        f"{KODIERUNG / 'aufgaben.jsonl'}"
    )
    recall_zeichen = sum(len(str(a["text"])) for a in aufgaben if a["typ"] == "recall")
    sha = hashlib.sha256((VALIDIERUNG / "stichprobe.csv").read_bytes()).hexdigest()
    groesse = (KODIERUNG / "aufgaben.jsonl").stat().st_size
    print(f"  Recall-Dokumente zusammen {recall_zeichen} Zeichen; aufgaben.jsonl {groesse} Bytes")
    print(f"  SHA-256 stichprobe.csv {sha}")


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--profil", default="duesseldorf", choices=sorted(PROFILE))
    ap.add_argument("--alle", action="store_true", help="dazu die drei übrigen Datensätze")
    ap.add_argument(
        "--stichprobe", action="store_true", help="Stichprobe und Kodieraufgaben schreiben"
    )
    ap.add_argument("--einzelprozess", action="store_true", help="Laufzeit in einem Prozess messen")
    ap.add_argument("--beispiele", default="", help="kind: zufällige Beispiele mit Kontext zeigen")
    args = ap.parse_args(argv)
    profile = [args.profil] + ([p for p in PROFILE if p != args.profil] if args.alle else [])
    for i, profil in enumerate(profile):
        t0 = time.perf_counter()
        df, erg, aemter, je_name = extrahieren(profil)
        sp = spans_frame(erg)
        meta = metadaten(profil)
        dauer = time.perf_counter() - t0
        bericht(profil, df, sp, erg, aemter, je_name, meta, ausfuehrlich=i == 0)
        if i == 0:
            groesse_ausgabe(sp)
        if args.einzelprozess and i == 0:
            k = kontext_bauen(PROFILE[profil][1], aemter)
            t1 = time.perf_counter()
            for name, text in zip(df["name"].to_list(), df["text"].to_list(), strict=True):
                dokument(name, text, k)
            print(f"  Extraktion in einem Prozess: {time.perf_counter() - t1:.1f} s")
        print(f"  Laufzeit Extraktion {profil}: {dauer:.1f} s")
        if args.beispiele and i == 0:
            texte = dict(zip(df["name"].to_list(), df["text"].to_list(), strict=True))
            kind, _, attr = args.beispiele.partition(":")
            auswahl = sp.filter((pl.col("kind") == kind) & pl.col("attr").str.starts_with(attr))
            rows = auswahl.rows(named=True)
            for r in random.Random(1).sample(rows, min(40, len(rows))):
                t = texte[r["name"]]
                ctx = (
                    t[max(0, r["start"] - 70) : r["start"]]
                    + "⟦"
                    + t[r["start"] : r["end"]]
                    + "⟧"
                    + t[r["end"] : r["end"] + 40]
                ).replace("\n", "⏎")
                print(f"  {r['norm']:<28} {r['attr']:<22} {ctx}")
        if args.stichprobe and i == 0:
            stichprobe(df, sp, meta)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
