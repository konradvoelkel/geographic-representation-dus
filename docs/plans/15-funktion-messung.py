"""Rechnet die Zahlen von `15-funktion.md` nach (Vorhaben 15 „Dokumentfunktion und gemeinsame Anträge").

    uv run python docs/plans/15-funktion-messung.py [--stichprobe]

Liest nur, was `georep run` je Profil schreibt (`interim/papers.parquet`,
`processed/papers_gremien.parquet`, `processed/dokumente_urheber.parquet`; Pfade aus
`georep --profile <p> paths`), die Parteimuster aus den Settings des Profils (`[originators]`) und
zwei gemeinsame Messdateien, beide nur lesend: die Beratungsrollen der OParl-Objekte aus dem Auszug
von Vorhaben 14 (`$GEOREP_MESSDATEN/14-vorgaenge/oparl_papiere.parquet`) als deterministische
Gegenprobe, und für die Kodieraufgaben den Rohtext aus Phase 0 (`$GEOREP_MESSDATEN/rohtext/`, Groß-
und Kleinschreibung, Zeilenumbrüche). Fehlt eine der beiden, entfällt nur die Gegenprobe
beziehungsweise die Aufgabe nimmt den kleingeschriebenen Text.

Mit `--stichprobe` schreibt es die geschichtete Stichprobe von 150 Dokumenten nach
`validierung/15-funktion/stichprobe.csv` (nur IDs und Schicht) und die Kodieraufgaben nach
`$GEOREP_MESSDATEN/kodierung/15-funktion/aufgaben.jsonl` (nie ins Repo); ohne den Schalter prüft es
nur, ob die gespeicherte Stichprobe noch dieselbe ist. Das Codebuch
(`validierung/15-funktion/codebuch.toml`) ist von Hand geschrieben und wird nur gelesen.

Mit `--labels` bildet es aus den Antworten der beiden Kodierer und der Schlichtung (lokal unter
`$GEOREP_MESSDATEN/kodierung/15-funktion/`) die Endlabels `validierung/15-funktion/labels.csv`; liegt
diese Datei, wertet es das Regelwerk dagegen aus (§ 4.1 des Messdokuments: κ, Konfusionsmatrix,
Urheber, Restklasse). Die Auswertung braucht nur `labels.csv`, nicht die lokalen Antworten.

Alle Tabellen des Regelwerks stehen unten in einem Block „Profil"; Stufe 2 legt sie ins Stadtprofil
(`[functions]`), der Code kennt dann kein Stadtwort. Laufzeit rund eine halbe Minute.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import subprocess
import sys
import time
import tomllib
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

os.environ.setdefault("POLARS_MAX_THREADS", "4")
import polars as pl  # noqa: E402

from georep.settings import load_settings  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
ROLLEN = MESSDATEN / "14-vorgaenge" / "oparl_papiere.parquet"
ROHTEXT = MESSDATEN / "rohtext"
AUFGABEN = MESSDATEN / "kodierung" / "15-funktion" / "aufgaben.jsonl"
STICHPROBE = REPO / "validierung" / "15-funktion" / "stichprobe.csv"
CODEBUCH = REPO / "validierung" / "15-funktion" / "codebuch.toml"
SEED = 15
KODIERUNG = MESSDATEN / "kodierung" / "15-funktion"
ANTWORTEN = {"a": KODIERUNG / "antworten-A.jsonl", "b": KODIERUNG / "antworten-B.jsonl"}
SCHLICHTUNG = KODIERUNG / "schlichtung.jsonl"
LABELS = REPO / "validierung" / "15-funktion" / "labels.csv"
FRAGEN = ("funktion", "urheber", "adressat")
BOOTSTRAP = 2000  # Ziehungen für das Intervall von kappa
TEXTANFANG = 1500  # Zeichen je Dokument in einer Kodieraufgabe (Briefing)
KOPF = 700  # Zeichen des Textkopfs, in denen die Regeln der Sammelarten suchen

# Profil -> (Stadt, Datensatz). Die drei Düsseldorfer Perioden sind disjunkt; Mönchengladbach nur
# als Prüfstein für die Stadtneutralität des Regelwerks (Abdeckung), nicht in der Stichprobe.
PROFILE = (
    ("duesseldorf-2014", "dus", "2014-2020"),
    ("duesseldorf", "dus", "2020-2025"),
    ("duesseldorf-2025", "dus", "2025-"),
    ("moenchengladbach", "mg", "mg-2020-2025"),
)
DUS = ("2014-2020", "2020-2025", "2025-")

FUNKTIONEN = ("kontrolle", "information", "initiative", "symbol", "vollzug", "rest")
POLITISCH = ("Fraktion", "Person", "unbekannt")  # Urheberklassen, die Symbolpolitik tragen können

# ================================================================================================
# Profil (Stufe 2: `[functions]` im Stadtprofil). Düsseldorf in allen drei Perioden, dazu
# Mönchengladbach; die Dokumentart wird als ganzer Wert verglichen, dann über Präfixe.
# ================================================================================================
ART: dict[str, tuple[str, str]] = {
    # Düsseldorf, Verwaltung
    "Beschlussvorlage": ("vollzug", "beschlussvorlage"),
    "Bezirksvertretung Beschlussvorlage": ("vollzug", "beschlussvorlage"),
    "Beschlussvorlage RPA": ("vollzug", "rechnungspruefung"),
    "Bedarfsbeschluss": ("vollzug", "bau"),
    "A+F Beschluss": ("vollzug", "bau"),  # Ausführungs- und Finanzierungsbeschluss (Vorhaben 14)
    "Informationsvorlage": ("information", "informationsvorlage"),
    "Bezirksvertretung Informationsvorlage": ("information", "informationsvorlage"),
    "Berichtsvorlage": ("information", "berichtsvorlage"),
    "Eingabe nach 24GO": ("initiative", "eingabe"),
    "Eingabe nach 24 GO": ("initiative", "eingabe"),
    "Bezirksvertretung Eingabe nach 24Go": ("initiative", "eingabe"),
    # Mönchengladbach (Punkt 59: alle 16 Arten sind eindeutig)
    "1.1 - Beratungsvorlage": ("vollzug", "beschlussvorlage"),
    "1.2 - Beratungsvorlage BV": ("vollzug", "beschlussvorlage"),
    "6.3 - Beratungsvorlage Sondergremien": ("vollzug", "beschlussvorlage"),
    "6.5 - Beratungsvorlage Nat. Beirat": ("vollzug", "beschlussvorlage"),
    "8.1 - GMMG Beratungsvorlage": ("vollzug", "beschlussvorlage"),
    "8.2 - GMMG Beratungsvorlage BetrA": ("vollzug", "beschlussvorlage"),
    "7.1 - EWMG Beratungsvorlage": ("vollzug", "beschlussvorlage"),
    "4 - Änderungsvorlage": ("vollzug", "beschlussvorlage"),
    "2.1 - Berichtsvorlage": ("information", "berichtsvorlage"),
    "2.2 - Berichtsvorlage BV": ("information", "berichtsvorlage"),
    "6.2 - Berichtsvorlage Sondergremien": ("information", "berichtsvorlage"),
    "8.3 - GMMG Berichtsvorlage": ("information", "berichtsvorlage"),
    "8.4 - GMMG Berichtsvorlage BetrA": ("information", "berichtsvorlage"),
    "7.2 - EWMG Berichtsvorlage": ("information", "berichtsvorlage"),
    "3 - Fraktionsantrag": ("initiative", "antrag"),
    "6.1 - Mitgliederantrag": ("initiative", "antrag"),
}
# Präfix der Dokumentart (kleingeschrieben, längste zuerst) -> Funktion; „Antrag CDU/Grüne",
# „Haushaltsantrag Die Linke", „zAnfrage REP".
PRAEFIX: tuple[tuple[str, str, str], ...] = (
    ("haushaltsantrag", "initiative", "haushaltsantrag"),
    ("zanfrage", "kontrolle", "anfrage"),
    ("zantrag", "initiative", "antrag"),
    ("anfrage", "kontrolle", "anfrage"),
    ("antrag", "initiative", "antrag"),
)
# Sammelarten der Periode 2014-2020: die Art nennt die Funktion nicht, Titel und Textkopf tun es.
SAMMEL_POLITIK = frozenset({"Vorlage aus der Politik"})
SAMMEL_VERWALTUNG = frozenset({"Verwaltungsvorlage"})

# Titelmuster (kleingeschrieben). Symbolpolitik: eine Erklärung des Gremiums, die keine Sache der
# Stadt entscheidet (Resolution, Appell, Solidarität, Verurteilung, Bündnisbeitritt).
SYMBOL_TITEL = re.compile(
    r"resolution|(?<![a-zäöüß])appell|solidarität mit|verurteil|bekennt sich|gegen hass"
    r"|sichere[rn]? häfen?|seebrücke|mayors for peace|städtebündnis|städte-?koalition"
)
ANFRAGE_TITEL = re.compile(r"(?<![a-zäöüß])(z?anfrage|nachfrage|rückfrage)")
ANTRAG_TITEL = re.compile(
    r"(?<![a-zäöüß])(änderungs-?|ergänzungs-?|haushalts-?|haushaltsbegleit|prüf|dringlichkeits-?|zusatz-?)?antrag"
)
NACHFRAGE_TITEL = re.compile(r"nachfrage|rückfrage|zusatzfrage|folgeanfrage")
AENDERUNG = re.compile(
    r"änderungs-?\s?antrag|ergänzungs-?\s?antrag|zusatzantrag|änderungs- und ergänzungsantrag"
)
HAUSHALTSANTRAG = re.compile(r"haushalts(begleit)?-?antrag")
PRUEF = re.compile(
    r"prüfauftrag|prüf-?antrag|pürfantrag|(?<![a-zäöüß])prüfung (der|des|von|einer|eines|ob)|zu prüfen"
)
# Berichtsantrag: ein Antrag, der nur Auskunft verlangt (Sachstand, Bericht). Variante B zählt ihn
# als Kontrolle, Variante A als Initiative; die Kodierung entscheidet (§ 4).
BERICHT_TITEL = re.compile(
    r"sachstand|(?<![a-zäöüß])bericht(?!s?vorlage)(?!igung)|berichterstattung"
)
# Vollzug: was die Beschlussvorlage entscheidet, nur als Unterart (Instrument)
VOLLZUG_TITEL: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "haushalt",
        re.compile(
            r"haushaltssatzung|haushaltsplan|nachtragshaushalt|jahresabschluss|gesamtabschluss|wirtschaftsplan|stellenplan"
        ),
    ),
    ("satzung", re.compile(r"satzung|ordnung der|gebührenordnung|verordnung")),
    (
        "bauleitplanung",
        re.compile(r"bebauungsplan|flächennutzungsplan|(?<![a-zäöüß])plan nr|vorhabenbezogene"),
    ),
    (
        "besetzung",
        re.compile(
            r"(?<![a-zäöüß])(neu|nach|um)?wahl (von|der|des|eines|einer|zum|zur)|bestellung (von|eines|einer|der|des)|benennung|entsendung|abberufung|besetzung"
        ),
    ),
    (
        "dringlichkeit",
        re.compile(
            r"dringlichkeitsentscheidung|dringliche[rn]? entscheidung|dringlichkeitsbeschluss|60er-beschluss"
        ),
    ),
)
# Textkopf der Sammelart „Vorlage aus der Politik": das erste Instrumentwort hinter dem Briefkopf
# („… an den bezirksvorsteher … 11.09.2014  antrag quartier rund um …").
TEXT_INSTRUMENT = re.compile(
    r"(?<![a-zäöüß])((?:[a-zäöüß]*-?)?(?:antrag|anfrage)|resolution|informationsvorlage|mitteilung"
    r"|beschlussdarstellung|dringlichkeitsbeschluss)(?![a-zäöüß])"
)
NICHT_INSTRUMENT = frozenset(
    {
        "bauantrag",
        "bauvoranfrage",
        "voranfrage",
        "zuwendungsantrag",
        "förderantrag",
        "förderungsantrag",
        "bürgerantrag",
    }
)
# Textkopf der Sammelart „Verwaltungsvorlage": Kenntnisnahme gegen Entscheidung, das erste gewinnt.
TEXT_KENNTNIS = re.compile(
    r"informationsvorlage|zur kenntnis|kenntnis ?nahme|nimmt [^.]{0,200}?kenntnis|teilt (die verwaltung )?(wie folgt )?mit|hierzu teilt|berichtsvorlage|sachstandsbericht"
)
TEXT_BESCHLUSS = re.compile(
    r"beschließt|beschliesst|beschlossen|empfiehlt|genehmigt|stimmt [^.]{0,80}?zu|(?<![a-zäöüß])wählt|bestellt|benennt|entsendet|ermächtigt|beauftragt|bewilligt"
    r"|beschlussvorschlag|beschlussempfehlung|stellt [^.]{0,80}?fest|erteilt|setzt [^.]{0,60}?fest"
)
TEXT_BESCHLUSS_KOPF = re.compile(r"beschlussdarstellung")
TITEL_INFORMATION = re.compile(
    r"informationsvorlage|mitteilung|(?<![a-zäöüß])mdv(?![a-zäöüß])|sachstand|bericht(?!igung)|sitzungstermine"
    r"|stellungnahmen|beschlusskontrolle|(?<![a-zäöüß])ergebnisse|(?<![a-zäöüß])information"
)
TITEL_BESCHLUSS = re.compile(
    r"beschluss(?!kontrolle)|satzung|bebauungsplan|flächennutzungsplan|(?<![a-zäöüß])plan nr|genehmigung|vergabe|bestellung|wahl (der|des|von)"
)
BRIEFKOPF_POLITIK = re.compile(r"rsd\s*vorlage\s*x?\s*öffentlich\s*nicht\s*öffentlich")
BRIEFKOPF_ENDE = re.compile(
    r"(der|des) (bezirksvertretung|rates|ausschuss|integrationsrat|jugendrat)|(?<![a-zäöüß])an (den|die|das|herrn|frau)(?![a-zäöüß])|\d{1,2}\.\s?\d{1,2}\.\s?\d{4}"
)
WEIT = 3000  # zweiter Blick in den Text einer Verwaltungsvorlage, wenn Kopf und Titel nichts sagen
# Variante B: Symbolpolitik auch aus dem Beschlusstext eines Antrags (Adressat außerhalb der Stadt
# oder ein Bekenntnis des Gremiums) und Berichtsantrag als Kontrolle.
SYMBOL_TEXT = re.compile(
    r"(rat|bezirksvertretung|ausschuss|integrationsrat)[^.]{0,80}?(verurteilt|appelliert|bekräftigt|bekennt sich|solidarisiert sich"
    r"|erklärt (seine|ihre) (volle )?solidarität|fordert [^.]{0,40}?(bundes|landes)regierung"
    r"|fordert [^.]{0,30}?(den bund|den bundestag|den landtag|das land))"
)
BERICHT_TEXT = re.compile(
    r"(gebeten|beauftragt|aufgefordert)[^.]{0,120}?(zu berichten|bericht zu erstatten|sachstandsbericht|einen bericht)"
)

# Mehrheit im Rat je Periode, mit Quelle im Korpus (§ 3.8). Annahme: dieselbe Mehrheit in den
# Ausschüssen; die Bezirksvertretungen haben eigene Mehrheiten und werden ohne Lager gezählt.
MEHRHEIT: dict[str, frozenset[str]] = {
    "2014-2020": frozenset({"SPD", "GRUENE", "FDP"}),
    "2020-2025": frozenset({"CDU", "GRUENE"}),
    "2025-": frozenset({"CDU", "GRUENE"}),
}
# Je Periode die Formel der eigenen Mehrheit; ein Rückblick („gemäß ampel-kooperationsvertrag
# 2014-2020" in einem Antrag von 2021) belegt die Vorperiode und zählt dort nicht.
_SCHWARZ_GRUEN = (
    r".{0,60}(ratsmehrheit aus cdu und grün\w*|schwarz[/-]grünen? ratsmehrheit"
    r"|kooperation (von|aus) cdu und (den )?grün\w*|ratsmehrheit von cdu und bündnis).{0,80}"
)
MEHRHEIT_QUELLE: dict[str, str] = {
    "2014-2020": r".{0,60}(ampelmehrheit|ampelkooperation|ampel-kooperation\w*|ampelparteien).{0,80}",
    "2020-2025": _SCHWARZ_GRUEN,
    "2025-": _SCHWARZ_GRUEN,
}
STADTEBENE = ("rat", "ausschuss")  # gremium_art, für die das Lager der Ratsmehrheit gilt
# Fraktionen, die mehrere Parteischlüssel tragen (Kommentare an `organizations` im Profil): die
# Ratsfraktion SPD/Volt ab 2020-11-01, die Ratsgruppe Freie Wähler Tierschutz PARTEI ab 2025-11.
# Stufe 2: aus `raw/organizations.json` (F6), wie `Patterns.with_organizations` es schon kann.
FRAKTION_EINHEIT: dict[str, dict[str, str]] = {
    "2020-2025": {"VOLT": "SPD+VOLT", "SPD": "SPD+VOLT"},
    "2025-": {
        "VOLT": "SPD+VOLT",
        "SPD": "SPD+VOLT",
        "PARTEI": "T_FW+PARTEI",
        "T_FW": "T_FW+PARTEI",
    },
}
# Autorenteil eines Titels: vom ersten Instrumentwort bis zum ersten Trenner; was davor oder danach
# steht, ist Gegenstand oder Bezug („Änderungsantrag der SPD zum Antrag der CDU …").
AUTOR = re.compile(
    r"(?<![a-zäöüß])(?:[a-zäöüß]*antrag|[a-zäöüß]*anfrage|resolution|äa)(?![a-zäöüß])"
)
TRENNER = re.compile(r":|;| zu[mr]? | zu der | hier| vom | betr| bzgl| wegen | - | – ")
TYP_PRAEFIX = re.compile(r"^(haushaltsantrag|zanfrage|zantrag|anfrage|antrag)\s*")


# ================================================================================================
# Regelwerk
# ================================================================================================
def _vollzug_instrument(titel: str, standard: str) -> str:
    for name, muster in VOLLZUG_TITEL:
        if muster.search(titel):
            return name
    return standard


def _initiative_instrument(titel: str, standard: str) -> str:
    if HAUSHALTSANTRAG.search(titel) or standard == "haushaltsantrag":
        return "haushaltsantrag"
    if AENDERUNG.search(titel):
        return "aenderungsantrag"
    if PRUEF.search(titel):
        return "pruefauftrag"
    if BERICHT_TITEL.search(titel):
        return "berichtsantrag"
    return standard


def _aus_textwort(wort: str) -> tuple[str, str] | None:
    """Funktion und Instrument aus dem ersten Instrumentwort im Textkopf einer Sammelart."""
    w = wort.strip("-")
    if w in NICHT_INSTRUMENT:
        return None
    if w.endswith("anfrage"):
        return "kontrolle", "anfrage"
    if w.endswith("antrag"):
        return "initiative", _initiative_instrument(w, "antrag")
    if w == "resolution":
        return "symbol", "resolution"
    if w in ("informationsvorlage", "mitteilung"):
        return "information", "informationsvorlage"
    if w in ("beschlussdarstellung", "dringlichkeitsbeschluss"):
        return "vollzug", "beschlussvorlage"
    return None


def _kenntnis_oder_beschluss(text: str) -> str | None:
    """Das erste Merkmal im Text gewinnt: Kenntnisnahme (Information) oder Entscheidung (Vollzug)."""
    k = TEXT_KENNTNIS.search(text)
    b = TEXT_BESCHLUSS.search(text)
    if k is not None and (b is None or k.start() < b.start()):
        return "information"
    if b is not None or TEXT_BESCHLUSS_KOPF.search(text):
        return "vollzug"
    return None


def _verwaltung_aus_text(text: str, titel: str) -> tuple[str, str, str]:
    """Verwaltungsvorlage (Sammelart 2014-2020): Briefkopf, Textkopf, Titel, dann der weitere Text."""
    kopf = text[:KOPF]
    if BRIEFKOPF_POLITIK.search(kopf):  # der Briefkopf der Politik, auch ohne das Wort „fraktion"
        return _politik(titel, kopf)
    f = _kenntnis_oder_beschluss(kopf)
    if f is None:
        if TITEL_INFORMATION.search(titel):
            return "information", "informationsvorlage", "titel"
        if TITEL_BESCHLUSS.search(titel):
            return "vollzug", _vollzug_instrument(titel, "beschlussvorlage"), "titel"
        f = _kenntnis_oder_beschluss(text[:WEIT])
        if f is None:
            return "rest", "sammelart_ohne_merkmal", ""
        return (
            f,
            "informationsvorlage"
            if f == "information"
            else _vollzug_instrument(titel, "beschlussvorlage"),
            "text",
        )
    if f == "information":
        return "information", "informationsvorlage", "text"
    return "vollzug", _vollzug_instrument(titel, "beschlussvorlage"), "text"


def _politik(titel: str, kopf: str) -> tuple[str, str, str]:
    an = ANTRAG_TITEL.search(titel)
    af = ANFRAGE_TITEL.search(titel)
    if af is not None and an is None:  # eine Anfrage zu einer Resolution ist Kontrolle
        return "kontrolle", "nachfrage" if NACHFRAGE_TITEL.search(titel) else "anfrage", "titel"
    if SYMBOL_TITEL.search(titel):
        return "symbol", "resolution", "titel"
    if an is not None:
        return "initiative", _initiative_instrument(titel, "antrag"), "titel"
    for m in TEXT_INSTRUMENT.finditer(kopf[:KOPF]):
        found = _aus_textwort(m.group(1))
        if found is not None:
            return (*found, "text")
    return "rest", "sammelart_ohne_merkmal", ""


def funktion(
    paper_type: str | None,
    name: str | None,
    text: str | None,
    urheber_art: str | None,
    variante: str = "A",
) -> tuple[str, str, str]:
    """(Funktion, Instrument, Quelle) eines Dokuments. Quelle: art, titel, text oder leer (Rest).

    Reihenfolge: Dokumentart (ganzer Wert, dann Präfix), bei den Sammelarten Titel und Textkopf,
    danach die Titelmuster, die eine Initiative zur Symbolpolitik machen (nur aus der Politik: eine
    Informationsvorlage „Resolution zur Stärkung der Kommunalfinanzen" berichtet über eine
    Resolution und bleibt Information). Variante B liest zusätzlich den Beschlusstext eines
    Antrags (Symbolpolitik) und zählt den Berichtsantrag als Kontrolle.
    """
    typ = (paper_type or "").strip()
    low = typ.lower()
    titel = (name or "").lower()
    kopf = (text or "")[:KOPF]
    art = urheber_art or "unbekannt"
    f: str
    i: str
    q: str
    if typ in ART:
        f, i = ART[typ]
        q = "art"
        if f == "vollzug":
            i = _vollzug_instrument(titel, i)
        elif f == "initiative" and i != "eingabe":
            i = _initiative_instrument(titel, i)
    elif typ in SAMMEL_POLITIK or (typ in SAMMEL_VERWALTUNG and art in POLITISCH):
        f, i, q = _politik(titel, kopf)
    elif typ in SAMMEL_VERWALTUNG:
        f, i, q = _verwaltung_aus_text(text or "", titel)
    else:
        for praefix, pf, pi in PRAEFIX:
            if low.startswith(praefix):
                f, i, q = pf, pi, "art"
                if f == "initiative":
                    i = _initiative_instrument(titel, i)
                elif NACHFRAGE_TITEL.search(titel):
                    i = "nachfrage"
                break
        else:
            f, i, q = "rest", "art_unbekannt", ""
    if f == "initiative" and art in POLITISCH and i != "eingabe" and SYMBOL_TITEL.search(titel):
        f, i, q = "symbol", "resolution", "titel"
    if variante == "B" and f == "initiative" and art in POLITISCH and i != "eingabe":
        beschluss = (text or "")[:1200]
        if SYMBOL_TEXT.search(beschluss):
            f, i, q = "symbol", "erklaerung_text", "text"
        elif i == "berichtsantrag" or BERICHT_TEXT.search(beschluss):
            f, i, q = "kontrolle", "berichtsantrag", q if i == "berichtsantrag" else "text"
    return f, i, q


def autorenteil(titel: str) -> str | None:
    m = AUTOR.search(titel)
    if m is None:
        return None
    rest = titel[m.start() :]
    cut = TRENNER.search(rest, m.end() - m.start())
    return rest[: cut.start()] if cut else rest


def briefkopf_autoren(text: str | None) -> str | None:
    """Der Verfasserblock des Briefkopfs der Periode 2014-2020: zwischen „nicht öffentlich" und dem
    Gremium oder der Anrede („… nicht öffentlich  spd - fraktion  cdu - fraktion  der
    bezirksvertretung 8  an den bezirksbürgermeister …"); der Betreff dahinter zählt nicht."""
    kopf = (text or "")[:KOPF]
    m = BRIEFKOPF_POLITIK.search(kopf)
    if m is None:
        return None
    seg = kopf[m.end() : m.end() + 240]
    cut = BRIEFKOPF_ENDE.search(seg)
    return seg[: cut.start()] if cut else seg


def antragsteller(
    paper_type: str | None,
    name: str | None,
    parteien: list[str] | None,
    urheber_art: str | None,
    urheber_quelle: str | None,
    muster: tuple[tuple[str, re.Pattern[str]], ...],
    text: str | None = None,
) -> list[str]:
    """Parteien, die ein Fraktionsdokument stellen: Dokumentart und Autorenteil des Titels.

    `parteien` aus `dokumente_urheber` nimmt die erste Quelle mit Treffer (Punkt 59 ff.): bei
    „Antrag CDU/Grüne" die Art, auch wenn der Titel vier Fraktionen nennt, und bei einem Titel den
    ganzen Titel, auch den Gegenstand („Antrag Die Linke: AfD keine Plattform geben"), und beim
    Briefkopf der Periode 2014-2020 ein Fenster, das den Betreff mitnimmt. Hier zählt die
    Vereinigung aus Art, Autorenteil des Titels und Verfasserblock des Briefkopfs; nennen alle drei
    keine Partei, bleibt `parteien`.
    """
    if urheber_art != "Fraktion":
        return []
    vorher = list(parteien or [])
    order = {k: i for i, (k, _m) in enumerate(muster)}
    rest_typ = TYP_PRAEFIX.sub("", (paper_type or "").lower())
    aus_art = [k for k, m in muster if rest_typ and m.search(rest_typ)]
    seg = autorenteil((name or "").lower())
    aus_titel = [k for k, m in muster if seg and m.search(seg)]
    kopf = briefkopf_autoren(text)
    aus_kopf = [k for k, m in muster if kopf and m.search(kopf)]
    alle = set(aus_art) | set(aus_titel) | set(aus_kopf)
    if not alle:
        return vorher
    return sorted(alle, key=lambda k: order.get(k, 99))


# ================================================================================================
# Laden
# ================================================================================================
def paths(profile: str) -> dict[str, str]:
    exe = Path(sys.executable).parent / "georep"
    out = subprocess.run(
        [str(exe), "--profile", profile, "paths"], check=True, capture_output=True, text=True
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def lade(profile: str, stadt: str, datensatz: str) -> tuple[pl.DataFrame, dict[str, str]]:
    p = paths(profile)
    root = Path(p["root"])
    corpus = pl.read_parquet(
        root / "interim" / "papers.parquet",
        columns=["id", "name", "reference", "date", "paper_type", "file_name", "text"],
    )
    gremien = pl.read_parquet(
        root / "processed" / "papers_gremien.parquet", columns=["id", "gremium", "gremium_art"]
    )
    urheber = pl.read_parquet(
        root / "processed" / "dokumente_urheber.parquet",
        columns=["id", "urheber_art", "parteien", "quelle"],
    )
    df = (
        corpus.join(gremien, on="id", how="left")
        .join(urheber.rename({"quelle": "urheber_quelle"}), on="id", how="left")
        .with_columns(
            pl.lit(stadt).alias("stadt"),
            pl.lit(datensatz).alias("datensatz"),
            pl.lit(root.name).alias("ordner"),
        )
        .sort("id")
    )
    return df, p


def titelparteien(
    profile: str,
) -> tuple[re.Pattern[str] | None, tuple[tuple[str, re.Pattern[str]], ...], dict[str, str]]:
    """Fraktionsmarker, Parteimuster und Kurznamen aus `[originators]` des Profils."""
    s = load_settings(profile=profile)
    o = s.originators
    marker = (
        re.compile("|".join(f"(?:{m})" for m in o.fraction_markers)) if o.fraction_markers else None
    )
    gruppen = (*o.parties, *o.groups)
    muster = tuple((g.key, re.compile("|".join(f"(?:{m})" for m in g.patterns))) for g in gruppen)
    kurz = {g.key: g.short for g in gruppen}
    return marker, muster, kurz


# ================================================================================================
# Hilfen
# ================================================================================================
def pct(a: int, b: int) -> str:
    return f"{a} von {b} ({100 * a / b:.1f} %)" if b else f"{a} von 0"


def p1(a: float, b: float) -> str:
    return f"{100 * a / b:.1f} %" if b else "–"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (c - r) / d, (c + r) / d


def titel(s: str) -> None:
    print(f"\n=== {s} ===")


def tabelle(df: pl.DataFrame, rows: int = 60) -> None:
    with pl.Config(
        tbl_rows=rows,
        tbl_cols=-1,
        fmt_str_lengths=100,
        tbl_width_chars=260,
        tbl_hide_dataframe_shape=True,
    ):
        print(df)


# ================================================================================================
# Messung
# ================================================================================================
def main() -> None:  # noqa: C901, PLR0912, PLR0915 -- ein Messskript liest sich am besten von oben nach unten
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--stichprobe", action="store_true", help="Stichprobe und Kodieraufgaben neu schreiben"
    )
    ap.add_argument(
        "--labels", action="store_true", help="labels.csv aus Antworten und Schlichtung bilden"
    )
    args = ap.parse_args()
    t0 = time.perf_counter()

    frames = []
    pmuster: dict[str, Any] = {}
    for profile, stadt, datensatz in PROFILE:
        df, _ = lade(profile, stadt, datensatz)
        frames.append(df)
        pmuster[datensatz] = titelparteien(profile)
    docs = pl.concat(frames, how="vertical_relaxed")

    rows = []
    t_regel = time.perf_counter()
    for r in docs.select("id", "paper_type", "name", "text", "urheber_art").iter_rows():
        fa, ia, qa = funktion(r[1], r[2], r[3], r[4], "A")
        fb, ib, qb = funktion(r[1], r[2], r[3], r[4], "B")
        rows.append((r[0], fa, ia, qa, fb, ib, qb))
    t_regel = time.perf_counter() - t_regel
    regel = pl.DataFrame(
        rows,
        schema=[
            "id",
            "funktion",
            "instrument",
            "quelle_f",
            "funktion_b",
            "instrument_b",
            "quelle_b",
        ],
        orient="row",
    )
    docs = docs.join(regel, on="id", how="left").sort("datensatz", "id")

    # --- 2 Datenlage ----------------------------------------------------------------------------
    titel("2 Datenlage")
    tabelle(
        docs.group_by("datensatz")
        .agg(
            pl.len().alias("dokumente"),
            (pl.col("text").str.len_chars() > 0).sum().alias("mit_text"),
            pl.col("paper_type").n_unique().alias("arten"),
            pl.col("date").min().alias("von"),
            pl.col("date").max().alias("bis"),
        )
        .sort("datensatz")
    )

    # --- 3.1 Abdeckung je Periode -----------------------------------------------------------------
    titel(
        "3.1 Abdeckung je Periode, Variante A (Art, Titel, Urheberklasse; Textkopf nur bei Sammelarten)"
    )
    for var, col in (("A", "funktion"), ("B", "funktion_b")):
        t = (
            docs.group_by("datensatz", col)
            .len()
            .sort(col)
            .pivot(on=col, index="datensatz", values="len")
            .fill_null(0)
            .with_columns(pl.sum_horizontal(*FUNKTIONEN).alias("n"))
            .select("datensatz", *FUNKTIONEN, "n")
            .sort("datensatz")
        )
        print(f"Variante {var}:")
        tabelle(t)
        for r in t.iter_rows(named=True):
            print(f"  {r['datensatz']}: Rest {pct(r['rest'], r['n'])}")
        dus = t.filter(pl.col("datensatz").is_in(DUS))
        print(f"  Düsseldorf zusammen: Rest {pct(int(dus['rest'].sum()), int(dus['n'].sum()))}")
    print("\nQuelle der Funktion (Variante A):")
    tabelle(
        docs.group_by("datensatz", "quelle_f")
        .len()
        .sort("quelle_f")
        .pivot(on="quelle_f", index="datensatz", values="len")
        .fill_null(0)
        .sort("datensatz")
    )
    print("\nAbweichung A gegen B:")
    ab = docs.filter(pl.col("funktion") != pl.col("funktion_b"))
    tabelle(
        ab.group_by("datensatz", "funktion", "funktion_b", "instrument_b")
        .len()
        .sort("datensatz", "len", descending=[False, True])
    )

    # --- 3.2 Je Dokumentart ---------------------------------------------------------------------
    titel("3.2 Funktion je Dokumentart (Düsseldorf, alle drei Perioden; Arten ab 30 Dokumenten)")
    d3 = docs.filter(pl.col("stadt") == "dus")
    t = (
        d3.group_by("paper_type", "funktion")
        .len()
        .sort("funktion")
        .pivot(on="funktion", index="paper_type", values="len")
        .fill_null(0)
    )
    for f in FUNKTIONEN:
        if f not in t.columns:
            t = t.with_columns(pl.lit(0, dtype=pl.UInt32).alias(f))
    t = (
        t.with_columns(pl.sum_horizontal(*FUNKTIONEN).alias("n"))
        .select("paper_type", *FUNKTIONEN, "n")
        .sort("n", descending=True)
    )
    tabelle(t.filter(pl.col("n") >= 30))
    eindeutig = t.with_columns(pl.max_horizontal(*FUNKTIONEN).alias("max")).filter(
        pl.col("max") == pl.col("n")
    )
    print(
        f"Arten: {t.height}, davon eine Funktion: {eindeutig.height} mit {int(eindeutig['n'].sum())} Dokumenten von {int(t['n'].sum())}"
    )
    print("\nInstrumente (Variante A, Düsseldorf) je Periode:")
    tabelle(
        d3.group_by("funktion", "instrument", "datensatz")
        .len()
        .sort("datensatz")
        .pivot(on="datensatz", index=["funktion", "instrument"], values="len")
        .fill_null(0)
        .sort("funktion", "instrument")
    )
    print("\nMönchengladbach je Art:")
    tabelle(
        docs.filter(pl.col("stadt") == "mg")
        .group_by("paper_type", "funktion")
        .len()
        .sort("len", descending=True)
    )

    # --- 3.3 Restklasse ---------------------------------------------------------------------------
    titel("3.3 Restklasse mit Beispielen")
    rest = docs.filter(pl.col("funktion") == "rest")
    tabelle(
        rest.group_by("datensatz", "paper_type", "instrument", "urheber_art")
        .len()
        .sort("len", descending=True)
    )
    rnd = random.Random(SEED)
    rid = sorted(rest["id"].to_list())
    for i in sorted(rnd.sample(rid, min(10, len(rid)))):
        r = rest.filter(pl.col("id") == i).row(0, named=True)
        print(
            f"  {r['reference']} [{r['paper_type']}, {r['urheber_art']}] {r['name'][:90]!r} | {(r['text'] or '')[:160]!r}"
        )
    print("Symbolpolitik, alle Titel (Variante A):")
    for r in docs.filter(pl.col("funktion") == "symbol").sort("date").iter_rows(named=True):
        print(
            f"  {r['datensatz']} {r['reference']} {r['date']} [{r['paper_type']}] {r['name'][:110]}"
        )
    print("Symbolpolitik nur aus dem Beschlusstext (Variante B), Beispiele:")
    sb = docs.filter((pl.col("funktion_b") == "symbol") & (pl.col("funktion") != "symbol"))
    for r in sb.sort("date").head(15).iter_rows(named=True):
        print(f"  {r['datensatz']} {r['reference']} [{r['paper_type']}] {r['name'][:110]}")

    # --- 3.4 Gegenproben aus den Daten ----------------------------------------------------------
    titel("3.4 Gegenproben aus den Daten selbst")
    if ROLLEN.exists():
        rollen = pl.read_parquet(ROLLEN, columns=["id", "rollen"])

        def rolle(lst: list[str] | None) -> str:
            s = {x for x in (lst or []) if x and x != "-"}
            if not s:
                return "keine"
            if s == {"Kenntnisnahme"}:
                return "kenntnisnahme"
            if "Kenntnisnahme" in s:
                return "gemischt"
            return "entscheidung"

        rr = pl.DataFrame(
            [(i, rolle(lst)) for i, lst in rollen.iter_rows()], schema=["id", "rolle"], orient="row"
        )
        dr = d3.join(rr, on="id", how="left").with_columns(pl.col("rolle").fill_null("kein_objekt"))
        print("Beratungsrolle der OParl-Objekte (consultation.role) je Funktion, Düsseldorf:")
        tabelle(
            dr.group_by("datensatz", "funktion", "rolle")
            .len()
            .sort("rolle")
            .pivot(on="rolle", index=["datensatz", "funktion"], values="len")
            .fill_null(0)
            .sort("datensatz", "funktion")
        )
        mit = dr.filter(pl.col("rolle").is_in(["kenntnisnahme", "entscheidung"]))
        ok = mit.filter(
            ((pl.col("funktion") == "information") & (pl.col("rolle") == "kenntnisnahme"))
            | (
                (pl.col("funktion").is_in(["vollzug", "initiative", "symbol"]))
                & (pl.col("rolle") == "entscheidung")
            )
            | ((pl.col("funktion") == "kontrolle") & (pl.col("rolle") == "kenntnisnahme"))
        )
        rel = mit.filter(pl.col("funktion") != "rest")
        print(
            f"Passend (Information/Kontrolle ~ Kenntnisnahme, Vollzug/Initiative/Symbol ~ Entscheidung) unter Dokumenten mit eindeutiger Rolle: {pct(ok.height, rel.height)}"
        )
        for ds in DUS:
            m = rel.filter(pl.col("datensatz") == ds)
            o = ok.filter(pl.col("datensatz") == ds)
            print(f"  {ds}: {pct(o.height, m.height)}")
    else:
        print(f"{ROLLEN} fehlt; Gegenprobe über die Beratungsrolle entfällt")

    print(
        "\nTextregel der Sammelart Verwaltungsvorlage, angewandt auf die Vorlagen der Hauptperiode und der laufenden, deren Art die Funktion nennt:"
    )
    probe = d3.filter(
        pl.col("datensatz").is_in(["2020-2025", "2025-"])
        & pl.col("paper_type").is_in(
            [
                "Beschlussvorlage",
                "Bezirksvertretung Beschlussvorlage",
                "Informationsvorlage",
                "Bezirksvertretung Informationsvorlage",
                "Berichtsvorlage",
            ]
        )
    )
    tr = [
        (_verwaltung_aus_text(r[2] or "", (r[1] or "").lower())[0], r[3])
        for r in probe.select("id", "name", "text", "funktion").iter_rows()
    ]
    tt = Counter(tr)
    for (pred, wahr), n in sorted(tt.items()):
        print(f"  Art sagt {wahr:12s} Textregel sagt {pred:12s}: {n}")
    richtig = sum(n for (p_, w), n in tt.items() if p_ == w)
    ohne_rest = sum(n for (p_, _w), n in tt.items() if p_ != "rest")
    print(
        f"  Treffer {pct(richtig, sum(tt.values()))}; ohne Rest der Textregel {pct(richtig, ohne_rest)}"
    )

    print(
        "\nTextregel der Sammelart Vorlage aus der Politik gegen das Titelwort (2014-2020, wo beides da ist):"
    )
    vp = d3.filter(pl.col("paper_type").is_in(list(SAMMEL_POLITIK)))
    paare = Counter()
    for r in vp.select("name", "text").iter_rows():
        t_ = (r[0] or "").lower()
        an, af = ANTRAG_TITEL.search(t_), ANFRAGE_TITEL.search(t_)
        tit = "kontrolle" if af and not an else "initiative" if an else None
        txt = None
        for m in TEXT_INSTRUMENT.finditer((r[1] or "")[:KOPF]):
            found = _aus_textwort(m.group(1))
            if found is not None:
                txt = found[0]
                break
        if tit and txt:
            paare[(tit, txt)] += 1
    for (a_, b_), n in sorted(paare.items()):
        print(f"  Titel {a_:10s} Text {b_:11s}: {n}")
    print(
        f"  Übereinstimmung {pct(sum(n for (a_, b_), n in paare.items() if a_ == b_), sum(paare.values()))}"
    )

    # --- 3.5 Funktion x Urheberklasse -----------------------------------------------------------
    titel("3.5 Funktion je Urheberklasse und Periode (Variante A)")
    tabelle(
        docs.group_by("datensatz", "urheber_art", "funktion")
        .len()
        .sort("funktion")
        .pivot(on="funktion", index=["datensatz", "urheber_art"], values="len")
        .fill_null(0)
        .sort("datensatz", "urheber_art")
    )

    # --- Antragsteller und Fraktionen ------------------------------------------------------------
    rows_a = []
    for r in d3.select(
        "id", "datensatz", "paper_type", "name", "parteien", "urheber_art", "urheber_quelle", "text"
    ).iter_rows(named=True):
        _, muster, _ = pmuster[r["datensatz"]]
        ast = antragsteller(
            r["paper_type"],
            r["name"],
            r["parteien"],
            r["urheber_art"],
            r["urheber_quelle"],
            muster,
            r["text"],
        )
        unit = FRAKTION_EINHEIT.get(r["datensatz"], {})
        rows_a.append((r["id"], ast, sorted({unit.get(k, k) for k in ast})))
    d3 = d3.join(
        pl.DataFrame(
            rows_a,
            schema={
                "id": pl.String,
                "antragsteller": pl.List(pl.String),
                "fraktionen": pl.List(pl.String),
            },
            orient="row",
        ),
        on="id",
        how="left",
    )

    # --- 3.6 Funktion x Fraktion --------------------------------------------------------------------
    titel("3.6 Funktion je Fraktion (Düsseldorf; gemeinsame Dokumente zählen je Fraktion)")
    print(f"Fraktionseinheiten: {FRAKTION_EINHEIT}")
    pol = d3.filter(
        (pl.col("urheber_art") == "Fraktion")
        & pl.col("funktion").is_in(["kontrolle", "initiative", "symbol"])
    ).with_columns(pl.col("fraktionen").list.len().alias("k"))
    ex = pol.explode("fraktionen").filter(pl.col("fraktionen").is_not_null())
    roh = (
        ex.group_by("datensatz", "fraktionen")
        .agg(
            pl.len().alias("n"),
            (pl.col("funktion") == "kontrolle").sum().alias("kontrolle"),
            (pl.col("funktion") == "initiative").sum().alias("initiative"),
            (pl.col("funktion") == "symbol").sum().alias("symbol"),
            (pl.col("k") >= 2).sum().alias("gemeinsam"),
        )
        .with_columns((pl.col("kontrolle") / pl.col("n")).alias("anteil_kontrolle"))
    )
    # Indirekte Standardisierung über das Gremium: erwartet = Summe der Kontrollanteile des Gremiums
    # (über alle Fraktionsdokumente dieser drei Funktionen in der Periode) über die Dokumente der Fraktion.
    g_ant = pol.group_by("datensatz", "gremium").agg(
        (pl.col("funktion") == "kontrolle").mean().alias("g_anteil"), pl.len().alias("g_n")
    )
    erw = (
        ex.join(g_ant, on=["datensatz", "gremium"], how="left")
        .group_by("datensatz", "fraktionen")
        .agg(pl.col("g_anteil").sum().alias("erwartet"))
    )
    std = (
        roh.join(erw, on=["datensatz", "fraktionen"], how="left")
        .with_columns((pl.col("kontrolle") / pl.col("erwartet")).alias("beob_erw"))
        .sort("datensatz", "n", descending=[False, True])
    )
    tabelle(
        std.select(
            "datensatz",
            "fraktionen",
            "n",
            "gemeinsam",
            "kontrolle",
            "initiative",
            "symbol",
            pl.col("anteil_kontrolle").round(3),
            pl.col("erwartet").round(1),
            pl.col("beob_erw").round(2),
        )
    )
    print("Kontrollanteil der Gremien (Fraktionsdokumente; Gremien mit mindestens 100):")
    tabelle(
        g_ant.filter(pl.col("g_n") >= 100)
        .sort("datensatz", "g_anteil")
        .with_columns(pl.col("g_anteil").round(3))
    )
    print("Spannweite des Gremienanteils je Periode:")
    tabelle(
        g_ant.filter(pl.col("g_n") >= 100)
        .group_by("datensatz")
        .agg(
            pl.col("g_anteil").min().round(3).alias("min"),
            pl.col("g_anteil").max().round(3).alias("max"),
            pl.len().alias("gremien"),
        )
        .sort("datensatz")
    )
    print("Kontrollanteil je Gremienart (Fraktionsdokumente):")
    tabelle(
        pol.group_by("datensatz", "gremium_art")
        .agg(
            pl.len().alias("n"),
            (pl.col("funktion") == "kontrolle").mean().round(3).alias("kontrolle"),
        )
        .sort("datensatz", "gremium_art")
    )

    # --- 3.7 Gemeinsame Dokumente ------------------------------------------------------------------
    titel("3.7 Gemeinsame Dokumente: Erkennung")
    fr = d3.filter(pl.col("urheber_art") == "Fraktion")
    anders = fr.filter(pl.col("antragsteller").list.sort() != pl.col("parteien").list.sort())
    print(
        f"Fraktionsdokumente: {fr.height}; Antragsteller aus Art und Autorenteil des Titels weichen von `parteien` ab: {anders.height}"
    )
    tabelle(
        anders.with_columns(
            pl.when(pl.col("antragsteller").list.len() > pl.col("parteien").list.len())
            .then(pl.lit("mehr"))
            .when(pl.col("antragsteller").list.len() < pl.col("parteien").list.len())
            .then(pl.lit("weniger"))
            .otherwise(pl.lit("andere"))
            .alias("richtung")
        )
        .group_by("datensatz", "richtung", "urheber_quelle")
        .len()
        .sort("datensatz", "len", descending=[False, True])
    )
    rnd2 = random.Random(SEED)
    for i in sorted(rnd2.sample(sorted(anders["id"].to_list()), min(14, anders.height))):
        r = anders.filter(pl.col("id") == i).row(0, named=True)
        print(
            f"  {r['reference']} [{r['paper_type']}] {r['parteien']} -> {r['antragsteller']} | {r['name'][:120]}"
        )
    tabelle(
        fr.with_columns(
            pl.when(pl.col("fraktionen").list.len() >= 2)
            .then(pl.lit("gemeinsam"))
            .when(pl.col("fraktionen").list.len() == 0)
            .then(pl.lit("ohne_partei"))
            .otherwise(pl.lit("allein"))
            .alias("form")
        )
        .group_by("datensatz", "form")
        .len()
        .sort("form")
        .pivot(on="form", index="datensatz", values="len")
        .fill_null(0)
        .sort("datensatz")
    )
    gem = fr.filter(pl.col("fraktionen").list.len() >= 2)
    print("Gemeinsame Dokumente je Funktion:")
    tabelle(
        gem.group_by("datensatz", "funktion")
        .len()
        .sort("funktion")
        .pivot(on="funktion", index="datensatz", values="len")
        .fill_null(0)
        .sort("datensatz")
    )
    print("Anteil gemeinsamer Dokumente je Gremienart:")
    tabelle(
        fr.group_by("datensatz", "gremium_art")
        .agg(
            pl.len().alias("fraktion"),
            (pl.col("fraktionen").list.len() >= 2).sum().alias("gemeinsam"),
        )
        .with_columns((pl.col("gemeinsam") / pl.col("fraktion")).round(3).alias("anteil"))
        .sort("datensatz", "gremium_art")
    )
    print("Gemeinsame Dokumentarten (die Art nennt zwei Fraktionen):")
    tabelle(
        fr.filter(
            pl.col("paper_type").str.contains("/")
            & ~pl.col("paper_type").str.contains(
                "Bündnis 90/|B90/|Tierschutz/|FREIE|Freie|SPD/Volt$"
            )
        )
        .group_by("datensatz", "paper_type")
        .len()
        .sort("datensatz", "len", descending=[False, True])
    )
    print("Zahl der Fraktionen je gemeinsamem Dokument:")
    tabelle(
        gem.group_by("datensatz", pl.col("fraktionen").list.len().alias("k"))
        .len()
        .sort("k")
        .pivot(on="k", index="datensatz", values="len")
        .fill_null(0)
        .sort("datensatz")
    )

    # --- 3.8 Mehrheiten und Netz ---------------------------------------------------------------------
    titel("3.8 Mehrheiten: Belege im Korpus")
    for ds in DUS:
        s_ = (
            d3.filter(pl.col("datensatz") == ds)
            .with_columns(pl.col("text").str.extract(MEHRHEIT_QUELLE[ds], 0).alias("beleg"))
            .filter(pl.col("beleg").is_not_null())
            .sort("date")
        )
        print(f"{ds}: Annahme {sorted(MEHRHEIT[ds])}; {s_.height} Dokumente mit Beleg")
        for r in s_.head(3).iter_rows(named=True):
            print(f"  {r['reference']} {r['date']}: …{r['beleg'].strip()}…")
        for r in s_.tail(2).iter_rows(named=True):
            print(f"  {r['reference']} {r['date']}: …{r['beleg'].strip()}…")
        kt = d3.filter((pl.col("datensatz") == ds) & pl.col("paper_type").str.contains("CDU/Grüne"))
        print(f"  Dokumentart „… CDU/Grüne“: {kt.height}")

    titel(
        "3.8 Netz der Mitantragsteller je Periode (Kanten zwischen Fraktionen, Gewicht = gemeinsame Dokumente)"
    )
    for ds in DUS:
        m = MEHRHEIT[ds]
        g = gem.filter(pl.col("datensatz") == ds)
        n_doc = Counter(
            k for lst in fr.filter(pl.col("datensatz") == ds)["fraktionen"].to_list() for k in lst
        )
        kanten: Counter[tuple[str, str]] = Counter()
        kanten_stadt: Counter[tuple[str, str]] = Counter()
        for lst, ga in g.select("fraktionen", "gremium_art").iter_rows():
            for a, b_ in combinations(sorted(lst), 2):
                kanten[(a, b_)] += 1
                if ga in STADTEBENE:
                    kanten_stadt[(a, b_)] += 1
        print(
            f"\n{ds}: {len(kanten)} Kanten, {sum(kanten.values())} Paarungen aus {g.height} Dokumenten; Mehrheit {sorted(m)}"
        )
        for (a, b_), w in kanten.most_common(16):
            lager = (
                "Mehrheit"
                if a in m and b_ in m
                else "über die Grenze"
                if (a in m) != (b_ in m)
                else "Opposition"
            )
            print(
                f"  {a:10s} – {b_:10s} {w:5d}  (Rat/Ausschüsse {kanten_stadt[(a, b_)]:4d})  {lager:15s} Anteil an {a}: {p1(w, n_doc[a])}, an {b_}: {p1(w, n_doc[b_])}"
            )
        print("  Rat und Ausschüsse allein, stärkste Kanten:")
        for (a, b_), w in kanten_stadt.most_common(8):
            lager = (
                "Mehrheit"
                if a in m and b_ in m
                else "über die Grenze"
                if (a in m) != (b_ in m)
                else "Opposition"
            )
            print(f"    {a:10s} – {b_:10s} {w:5d}  {lager}")
        afd = g.filter(pl.col("fraktionen").list.contains("AfD"))
        print(
            f"  gemeinsame Dokumente mit AfD: {afd.height} (AfD-Dokumente insgesamt {n_doc['AfD']})"
        )
        for r in afd.head(5).iter_rows(named=True):
            print(f"    {r['reference']} [{r['paper_type']}] {r['fraktionen']} {r['name'][:100]}")

    # --- 3.9 Konkordanz ----------------------------------------------------------------------------
    titel(
        "3.9 Konkordanz gegen Konkurrenz: Mitanträge über die Grenze zwischen Mehrheit und Opposition"
    )

    def lager_von(lst: list[str], m: frozenset[str]) -> str:
        if len(lst) == 0:
            return "ohne_partei"
        ins = [k in m for k in lst]
        if len(lst) == 1:
            return "allein_mehrheit" if ins[0] else "allein_opposition"
        if all(ins):
            return "gemeinsam_mehrheit"
        if not any(ins):
            return "gemeinsam_opposition"
        return "ueber_grenze"

    lg = [
        (i, lager_von(lst, MEHRHEIT[ds]))
        for i, lst, ds in fr.select("id", "fraktionen", "datensatz").iter_rows()
    ]
    fr = fr.join(pl.DataFrame(lg, schema=["id", "lager"], orient="row"), on="id", how="left")
    for ebene, filt in (
        ("Rat und Ausschüsse", pl.col("gremium_art").is_in(list(STADTEBENE))),
        (
            "Bezirksvertretungen (Lager der Ratsmehrheit als Näherung)",
            pl.col("gremium_art") == "bezirksvertretung",
        ),
    ):
        print(f"\n{ebene}: Lager × Funktion")
        sub = fr.filter(filt & pl.col("funktion").is_in(["initiative", "symbol", "kontrolle"]))
        tabelle(
            sub.group_by("datensatz", "lager", "funktion")
            .len()
            .sort("funktion")
            .pivot(on="funktion", index=["datensatz", "lager"], values="len")
            .fill_null(0)
            .sort("datensatz", "lager")
        )
        for ds in DUS:
            f_ = sub.filter(pl.col("datensatz") == ds)
            c = Counter(f_["lager"].to_list())
            ini = f_.filter(pl.col("funktion") != "kontrolle")
            ci = Counter(ini["lager"].to_list())
            gem_n = c["gemeinsam_mehrheit"] + c["gemeinsam_opposition"] + c["ueber_grenze"]
            gem_i = ci["gemeinsam_mehrheit"] + ci["gemeinsam_opposition"] + ci["ueber_grenze"]
            opp = c["allein_opposition"] + c["gemeinsam_opposition"] + c["ueber_grenze"]
            opp_i = ci["allein_opposition"] + ci["gemeinsam_opposition"] + ci["ueber_grenze"]
            mit_i = ini.height - ci["ohne_partei"]
            lo, hi = wilson(ci["ueber_grenze"], opp_i)
            print(
                f"  {ds}: Fraktionsdokumente {f_.height}\n"
                f"    K1 über die Grenze / gemeinsame: alle {pct(c['ueber_grenze'], gem_n)}; Initiative {pct(ci['ueber_grenze'], gem_i)}\n"
                f"    K2 über die Grenze / alle mit Fraktion: Initiative {pct(ci['ueber_grenze'], mit_i)}\n"
                f"    K3 Opposition mit Mehrheitsfraktion / alle mit Opposition: alle {pct(c['ueber_grenze'], opp)}; Initiative {pct(ci['ueber_grenze'], opp_i)} (Wilson-95-% {lo:.3f}–{hi:.3f})"
            )
            ini_b = f_.filter(pl.col("funktion_b").is_in(["initiative", "symbol"]))
            cb = Counter(ini_b["lager"].to_list())
            opp_b = cb["allein_opposition"] + cb["gemeinsam_opposition"] + cb["ueber_grenze"]
            lo_b, hi_b = wilson(cb["ueber_grenze"], opp_b)
            print(
                f"    K3 Initiative nach Variante B: {pct(cb['ueber_grenze'], opp_b)} (Wilson-95-% {lo_b:.3f}–{hi_b:.3f})"
            )
        if ebene.startswith("Rat"):
            print(
                "  Mehrheit: Anteil gemeinsam je Funktion (Initiative gemeinsam, Kontrolle allein?)"
            )
            for ds in DUS:
                mm = sub.filter(
                    (pl.col("datensatz") == ds)
                    & pl.col("lager").is_in(["allein_mehrheit", "gemeinsam_mehrheit"])
                )
                for fk in ("initiative", "kontrolle"):
                    x = mm.filter(pl.col("funktion") == fk)
                    print(
                        f"    {ds} {fk:10s}: gemeinsam {pct(x.filter(pl.col('lager') == 'gemeinsam_mehrheit').height, x.height)}"
                    )
            print("  Kontrollanteil je Lager (alle Dokumente des Lagers, allein und gemeinsam):")
            for ds in DUS:
                for name_, lst in (
                    ("Mehrheit", ["allein_mehrheit", "gemeinsam_mehrheit"]),
                    ("Opposition", ["allein_opposition", "gemeinsam_opposition"]),
                ):
                    x = sub.filter((pl.col("datensatz") == ds) & pl.col("lager").is_in(lst))
                    print(
                        f"    {ds} {name_:10s}: Kontrolle {pct(x.filter(pl.col('funktion') == 'kontrolle').height, x.height)}"
                    )
    print("\nAllparteiendokumente (mindestens vier Fraktionen, beide Lager), Rat und Ausschüsse:")
    for ds in DUS:
        x = fr.filter(
            (pl.col("datensatz") == ds)
            & pl.col("gremium_art").is_in(list(STADTEBENE))
            & (pl.col("lager") == "ueber_grenze")
            & (pl.col("fraktionen").list.len() >= 4)
        )
        print(f"  {ds}: {x.height}")
        for r in x.sort("date").head(4).iter_rows(named=True):
            print(f"    {r['reference']} {r['fraktionen']} {r['name'][:100]}")
    bsw = d3.filter(pl.col("paper_type").str.contains("Wagenknecht|BSW"))
    print(
        f"\nDokumentarten mit BSW (laufende Periode): {bsw.height}; Urheberklasse {dict(Counter(bsw['urheber_art'].to_list()))}, Parteien {dict(Counter(tuple(x) for x in bsw['parteien'].to_list()))}"
    )
    mg = docs.filter((pl.col("stadt") == "mg") & (pl.col("urheber_art") == "Fraktion"))
    print(
        f"Mönchengladbach: Fraktionsanträge {mg.height}, mit mindestens zwei Parteien in `parteien` {mg.filter(pl.col('parteien').list.len() >= 2).height}"
    )
    print("\nOhne Partei, aber Fraktion (interfraktionell ohne Namen), je Periode:")
    tabelle(
        fr.filter(pl.col("fraktionen").list.len() == 0)
        .group_by("datensatz", "gremium_art")
        .len()
        .sort("datensatz", "gremium_art")
    )
    d3 = d3.join(fr.select("id", "lager"), on="id", how="left")

    # --- 4 Validierung --------------------------------------------------------------------------------
    titel("4 Validierung: Stichprobe")
    schicht_ziel = (
        ("abweichung_ab", 10),
        ("rest", 15),
        ("symbol", 15),
        ("gemeinsam", 20),
        ("sammelart", 15),
        ("kontrolle", 20),
        ("information", 15),
        ("initiative", 20),
        ("vollzug", 20),
    )

    def schicht(r: dict[str, Any]) -> str:
        if r["funktion"] != r["funktion_b"]:
            return "abweichung_ab"
        if r["funktion"] == "rest":
            return "rest"
        if r["funktion"] == "symbol":
            return "symbol"
        if r["urheber_art"] == "Fraktion" and len(r["fraktionen"] or []) >= 2:
            return "gemeinsam"
        if r["paper_type"] in SAMMEL_POLITIK | SAMMEL_VERWALTUNG:
            return "sammelart"
        return str(r["funktion"])

    sch = [
        (r["id"], schicht(r))
        for r in d3.select(
            "id", "funktion", "funktion_b", "urheber_art", "fraktionen", "paper_type"
        ).iter_rows(named=True)
    ]
    d3 = d3.join(pl.DataFrame(sch, schema=["id", "schicht"], orient="row"), on="id", how="left")
    groessen = Counter(s for _i, s in sch)
    rnd = random.Random(SEED)
    sample: list[tuple[str, str]] = []
    for s, k in schicht_ziel:
        ids = sorted(i for i, x in sch if x == s)
        sample += [(i, s) for i in sorted(rnd.sample(ids, min(k, len(ids))))]
    print(f"{len(sample)} Dokumente, Seed {SEED}")
    for s, _k in schicht_ziel:
        print(
            f"  {s:14s} Population {groessen[s]:6d}  gezogen {sum(1 for _i, x in sample if x == s)}"
        )
    st = pl.DataFrame(sample, schema=["id", "schicht"], orient="row")
    sd = st.join(d3.select("id", "datensatz", "funktion", "funktion_b"), on="id", how="left")
    tabelle(sd.group_by("datensatz").len().sort("datensatz"))
    print("Klassen der Regel A in der Stichprobe:")
    tabelle(sd.group_by("funktion").len().sort("funktion"))
    verteilung = Counter(sd["funktion"].to_list())
    pe = sum((v / len(sample)) ** 2 for v in verteilung.values())
    print(
        f"Erwartete Zufallsübereinstimmung bei gleichen Randverteilungen p_e = {pe:.3f}; κ = 0,7 verlangt p_o ≥ {0.7 + 0.3 * pe:.3f}, also höchstens {int(len(sample) * (1 - (0.7 + 0.3 * pe)))} Abweichungen an {len(sample)}"
    )
    lo, hi = wilson(int(len(sample) * (0.7 + 0.3 * pe)) + 1, len(sample))
    print(f"Wilson-95-% bei dieser Grenze für die Trefferquote: {lo:.3f}–{hi:.3f}")

    if args.stichprobe:
        STICHPROBE.parent.mkdir(parents=True, exist_ok=True)
        with STICHPROBE.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "schicht"])
            w.writerows(sorted(sample))
        schreibe_aufgaben(st, d3)
        print(f"geschrieben: {STICHPROBE.relative_to(REPO)} und {AUFGABEN}")
    elif STICHPROBE.exists():
        with STICHPROBE.open(encoding="utf-8") as fh:
            gespeichert = sorted((r["id"], r["schicht"]) for r in csv.DictReader(fh))
        print(
            f"gespeicherte Stichprobe {'gleich' if gespeichert == sorted(sample) else 'VERSCHIEDEN'} ({len(gespeichert)} Zeilen)"
        )

    if args.labels:
        schreibe_labels()
        print(f"geschrieben: {LABELS.relative_to(REPO)}")
    if LABELS.exists():
        auswertung(d3, groessen)

    print(
        f"\nRegelwerk (Varianten A und B) über {docs.height} Dokumente: {t_regel:.1f} s, einfädig"
    )
    print(f"Laufzeit {time.perf_counter() - t0:.1f} s")


# ================================================================================================
# Labels und Auswertung (§ 4.1)
# ================================================================================================
def _norm(frage: str, wert: Any) -> Any:
    """Urheber als sortierte Liste ohne Doppel, sonst der Wert selbst."""
    return sorted(set(wert)) if frage == "urheber" else wert


def schreibe_labels() -> None:
    """Endlabel je Aufgabe und Frage: gleich kodiert, sonst der Entscheid der Schlichtung."""
    ant = {
        k: {
            json.loads(z)["id"]: json.loads(z)
            for z in f.read_text(encoding="utf-8").splitlines()
            if z
        }
        for k, f in ANTWORTEN.items()
    }
    schl = {}
    if SCHLICHTUNG.exists():
        for z in SCHLICHTUNG.read_text(encoding="utf-8").splitlines():
            if z:
                r = json.loads(z)
                schl[r["id"]] = r["entscheid"]
    if set(ant["a"]) != set(ant["b"]):
        raise SystemExit("Kodierer A und B haben verschiedene Aufgaben")
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    with LABELS.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["aufgabe", "frage", "kodierer_a", "kodierer_b", "schlichtung", "label"])
        for i in sorted(ant["a"]):
            for frage in FRAGEN:
                a = _norm(frage, ant["a"][i][frage])
                b = _norm(frage, ant["b"][i][frage])
                entscheid = schl.get(i, {})
                if a == b:
                    sch, label = "", json.dumps(a, ensure_ascii=False)
                elif frage in entscheid:
                    sch = json.dumps(_norm(frage, entscheid[frage]), ensure_ascii=False)
                    label = sch
                else:
                    raise SystemExit(f"uneinig ohne Schlichtung: {i} {frage}")
                w.writerow(
                    [
                        i,
                        frage,
                        json.dumps(a, ensure_ascii=False),
                        json.dumps(b, ensure_ascii=False),
                        sch,
                        label,
                    ]
                )


def lies_labels() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = defaultdict(dict)
    with LABELS.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["aufgabe"]][r["frage"]] = {
                "a": json.loads(r["kodierer_a"]),
                "b": json.loads(r["kodierer_b"]),
                "schlichtung": r["schlichtung"],
                "label": json.loads(r["label"]),
            }
    return dict(out)


def cohen_kappa(paare: list[tuple[str, str]], gewichte: list[float] | None = None) -> float:
    """Cohens kappa für zwei nominale Bewerter; mit Gewichten je Paar (Schichtgewichte)."""
    w = gewichte or [1.0] * len(paare)
    n = sum(w)
    if n == 0:
        return float("nan")
    po = sum(wi for (x, y), wi in zip(paare, w, strict=True) if x == y) / n
    rx: Counter[str] = Counter()
    ry: Counter[str] = Counter()
    for (x, y), wi in zip(paare, w, strict=True):
        rx[x] += wi
        ry[y] += wi
    pe = sum(rx[k] * ry[k] for k in set(rx) | set(ry)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def kappa_intervall(paare: list[tuple[str, str]], seed: int = SEED) -> tuple[float, float]:
    """Perzentil-Bootstrap (95 %) über die Dokumente."""
    rnd = random.Random(seed)
    werte = sorted(
        cohen_kappa([paare[rnd.randrange(len(paare))] for _ in paare]) for _ in range(BOOTSTRAP)
    )
    return werte[int(0.025 * BOOTSTRAP)], werte[int(0.975 * BOOTSTRAP) - 1]


def alpha_nominal(a: list[str], b: list[str]) -> float:
    """Krippendorffs alpha, nominal, zwei Kodierer, keine fehlenden Werte."""
    werte = a + b
    n = len(werte)
    c = Counter(werte)
    do = sum(1 for x, y in zip(a, b, strict=True) if x != y) * 2 / n
    de = sum(c[k] * (n - c[k]) for k in c) / (n * (n - 1))
    return 1 - do / de if de else 1.0


def regel_urheber(art: str | None, fraktionen: list[str] | None) -> list[str]:
    """Die Urheber des Regelwerks in den Optionen des Codebuchs."""
    if art == "Fraktion":
        return sorted(fraktionen) if fraktionen else ["interfraktionell_ohne_namen"]
    return [
        {"Verwaltung": "verwaltung", "Person": "einzelmitglied", "Eingabe": "buerger"}.get(
            art or "", "unklar"
        )
    ]


def auswertung(d3: pl.DataFrame, groessen: Counter[str]) -> None:  # noqa: C901, PLR0912, PLR0915
    titel("4.1 Auswertung der Kodierung (labels.csv)")
    lab = lies_labels()
    with STICHPROBE.open(encoding="utf-8") as fh:
        schicht = {r["id"]: r["schicht"] for r in csv.DictReader(fh)}
    if set(lab) != set(schicht):
        print("labels.csv und stichprobe.csv haben verschiedene Dokumente")
        return
    # Übereinstimmung der Kodierer
    for frage in FRAGEN:
        a = [json.dumps(lab[i][frage]["a"], ensure_ascii=False) for i in sorted(lab)]
        b = [json.dumps(lab[i][frage]["b"], ensure_ascii=False) for i in sorted(lab)]
        gleich = sum(1 for x, y in zip(a, b, strict=True) if x == y)
        geschl = sum(1 for i in lab if lab[i][frage]["schlichtung"])
        print(
            f"{frage:9s}: gleich {gleich}/{len(a)}, alpha (nominal) {alpha_nominal(a, b):.3f}, geschlichtet {geschl}"
        )

    unit = FRAKTION_EINHEIT
    rows = {
        r["id"]: r
        for r in d3.filter(pl.col("id").is_in(list(lab)))
        .select(
            "id",
            "reference",
            "datensatz",
            "paper_type",
            "urheber_art",
            "urheber_quelle",
            "parteien",
            "antragsteller",
            "fraktionen",
            "funktion",
            "funktion_b",
            "instrument_b",
        )
        .iter_rows(named=True)
    }
    gew = {
        s: groessen[s] / sum(1 for x in schicht.values() if x == s) for s in set(schicht.values())
    }

    # --- funktion ------------------------------------------------------------------------------
    print("\nLabel funktion je Schicht:")
    tab: dict[str, Counter[str]] = defaultdict(Counter)
    for i, s in schicht.items():
        tab[s][lab[i]["funktion"]["label"]] += 1
    for s in sorted(tab):
        print(f"  {s:14s} {dict(sorted(tab[s].items()))}")
    rest_ids = [i for i in lab if rows[i]["funktion"] == "rest"]
    print(
        f"Restklasse des Regelwerks: {len(rest_ids)} Dokumente, Labels {dict(Counter(lab[i]['funktion']['label'] for i in rest_ids))}"
    )
    for i in sorted(rest_ids, key=lambda x: rows[x]["reference"] or ""):
        print(
            f"    {rows[i]['reference']} [{rows[i]['paper_type']}] -> {lab[i]['funktion']['label']}"
        )
    if all(
        f.exists() for f in ANTWORTEN.values()
    ):  # nur lokal: das Feld unsicher steht nicht in labels.csv
        for k, f in ANTWORTEN.items():
            ant = [json.loads(z) for z in f.read_text(encoding="utf-8").splitlines() if z]
            print(
                f"  Kodierer {k.upper()}: unsicher {sum(r['unsicher'] for r in ant)}/{len(ant)}, "
                f"davon in der Restklasse {sum(r['unsicher'] for r in ant if r['id'] in rest_ids)}/{len(rest_ids)}"
            )
    unklar = [i for i in lab if lab[i]["funktion"]["label"] == "unklar"]
    print(
        f"Label unklar: {len(unklar)} ({', '.join(sorted(rows[i]['reference'] for i in unklar))}), Regel {[rows[i]['funktion'] for i in unklar]}"
    )

    basis = sorted(
        i for i in lab if rows[i]["funktion"] != "rest" and lab[i]["funktion"]["label"] != "unklar"
    )
    print(
        f"\nBasis des Kriteriums (Frage 17): Regelwerk gibt eine Funktion, Label nicht unklar: {len(basis)} Dokumente"
    )
    for var, col in (("A", "funktion"), ("B", "funktion_b")):
        paare = [(rows[i][col], lab[i]["funktion"]["label"]) for i in basis]
        k = cohen_kappa(paare)
        lo, hi = kappa_intervall(paare)
        tr = sum(1 for x, y in paare if x == y)
        wl, wh = wilson(tr, len(paare))
        g = [gew[schicht[i]] for i in basis]
        kw = cohen_kappa(paare, g)
        tw = sum(gi for (x, y), gi in zip(paare, g, strict=True) if x == y) / sum(g)
        print(
            f"Variante {var}: kappa {k:.3f} (Bootstrap-95-% {lo:.3f}–{hi:.3f}), Treffer {tr}/{len(paare)} = {tr / len(paare):.3f} (Wilson {wl:.3f}–{wh:.3f}); gewichtet: kappa {kw:.3f}, Treffer {tw:.3f}"
        )
        mat: Counter[tuple[str, str]] = Counter(paare)
        klassen = [f for f in FUNKTIONEN if f != "rest"]
        print(
            "  Konfusion (Zeile Regel, Spalte Label): " + " ".join(f"{f[:5]:>6s}" for f in klassen)
        )
        for f in klassen:
            print(f"  {f:38s} " + " ".join(f"{mat[(f, g_)]:6d}" for g_ in klassen))
        for f in klassen:
            tp = mat[(f, f)]
            pr = sum(mat[(f, g_)] for g_ in klassen)
            rc = sum(mat[(g_, f)] for g_ in klassen)
            print(f"    {f:12s} Präzision {tp}/{pr}  Recall {tp}/{rc}")
        je: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for i in basis:
            je[schicht[i]][0] += rows[i][col] == lab[i]["funktion"]["label"]
            je[schicht[i]][1] += 1
        print(
            "  je Schicht: " + ", ".join(f"{s_} {a_}/{n_}" for s_, (a_, n_) in sorted(je.items()))
        )
        falsch = [i for i in basis if rows[i][col] != lab[i]["funktion"]["label"]]
        for i in sorted(falsch, key=lambda x: (schicht[x], rows[x]["reference"] or "")):
            print(
                f"    falsch [{schicht[i]}] {rows[i]['reference']} [{rows[i]['paper_type']}] Regel {rows[i][col]} ({rows[i]['instrument_b'] if col == 'funktion_b' else ''}), Label {lab[i]['funktion']['label']}"
            )
    mit_rest = sorted(i for i in lab if lab[i]["funktion"]["label"] != "unklar")
    for var, col in (("A", "funktion"), ("B", "funktion_b")):
        paare = [(rows[i][col], lab[i]["funktion"]["label"]) for i in mit_rest]
        lo, hi = kappa_intervall(paare)
        print(
            f"Zum Vergleich mit der Restklasse (vor Frage 17 vorgesehen), Variante {var}: kappa {cohen_kappa(paare):.3f} "
            f"({lo:.3f}–{hi:.3f}), Treffer {sum(x == y for x, y in paare)}/{len(paare)}"
        )
    ab = [i for i in basis if schicht[i] == "abweichung_ab"]
    print(
        f"Schicht abweichung_ab (Entwurfsvergleich A gegen B): A {sum(rows[i]['funktion'] == lab[i]['funktion']['label'] for i in ab)}/{len(ab)}, B {sum(rows[i]['funktion_b'] == lab[i]['funktion']['label'] for i in ab)}/{len(ab)}"
    )
    for i in sorted(ab, key=lambda x: rows[x]["reference"] or ""):
        print(
            f"    {rows[i]['reference']} B={rows[i]['funktion_b']}/{rows[i]['instrument_b']} Label {lab[i]['funktion']['label']} adressat {lab[i]['adressat']['label']}"
        )

    # --- urheber -------------------------------------------------------------------------------
    print(
        "\nUrheber (Regelwerk: Fraktionen aus Art, Autorenteil und Briefkopf; dagegen `parteien`):"
    )
    fr_ids = {
        d: {x["id"] for x in tomllib.loads(CODEBUCH.read_text(encoding="utf-8"))["fraktionen"][d]}
        for d in DUS
    }

    def klasse(lst: list[str], ds: str) -> str:
        if any(x in fr_ids[ds] for x in lst) or "interfraktionell_ohne_namen" in lst:
            return "Fraktion"
        for k_, v_ in (
            ("verwaltung", "Verwaltung"),
            ("einzelmitglied", "Person"),
            ("buerger", "Eingabe"),
            ("beirat_oder_sondergremium", "Beirat"),
            ("andere", "andere"),
        ):
            if k_ in lst:
                return v_
        return "unklar"

    ex_r = ex_p = 0
    kl = Counter()
    for i in lab:
        r = rows[i]
        ru = regel_urheber(r["urheber_art"], r["fraktionen"])
        pu = regel_urheber(
            r["urheber_art"],
            sorted({unit.get(r["datensatz"], {}).get(k, k) for k in (r["parteien"] or [])}),
        )
        lb = lab[i]["urheber"]["label"]
        ex_r += ru == lb
        ex_p += pu == lb
        kl[(r["urheber_art"] or "unbekannt", klasse(lb, r["datensatz"]))] += 1
    print(f"exakt gleiche Urheber: Regelwerk {ex_r}/{len(lab)}, `parteien` {ex_p}/{len(lab)}")
    print(
        "Urheberklasse (Regel, Label): "
        + ", ".join(f"{a}->{b}: {n}" for (a, b), n in sorted(kl.items()))
    )
    for name, feld in (("Regelwerk", "fraktionen"), ("parteien", "parteien")):
        tp = fp = fn = 0
        je_f: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        gem = [0, 0, 0, 0]  # tp, fp, fn, exakt unter Label-gemeinsam
        gem_n = 0
        for i in lab:
            r = rows[i]
            ds = r["datensatz"]
            if r["urheber_art"] == "Fraktion":
                werte = r[feld] or []
                if feld == "parteien":
                    werte = sorted({unit.get(ds, {}).get(k, k) for k in werte})
                rs = set(werte)
            else:
                rs = set()
            ls = {x for x in lab[i]["urheber"]["label"] if x in fr_ids[ds]}
            tp += len(rs & ls)
            fp += len(rs - ls)
            fn += len(ls - rs)
            for f_ in rs & ls:
                je_f[f_][0] += 1
            for f_ in rs - ls:
                je_f[f_][1] += 1
            for f_ in ls - rs:
                je_f[f_][2] += 1
            if len(ls) >= 2 or len(rs) >= 2:
                gem[0] += len(ls) >= 2 and len(rs) >= 2
                gem[1] += len(rs) >= 2 and len(ls) < 2
                gem[2] += len(ls) >= 2 and len(rs) < 2
            if len(ls) >= 2:
                gem_n += 1
                gem[3] += rs == ls
        print(
            f"  {name}: Fraktionen Präzision {tp}/{tp + fp} = {tp / max(1, tp + fp):.3f}, Recall {tp}/{tp + fn} = {tp / max(1, tp + fn):.3f}"
        )
        print(
            "    je Fraktion (tp/fp/fn): "
            + ", ".join(f"{k_} {v_[0]}/{v_[1]}/{v_[2]}" for k_, v_ in sorted(je_f.items()))
        )
        print(
            f"    gemeinsam (mindestens zwei Fraktionen): beide {gem[0]}, nur Regel {gem[1]}, nur Label {gem[2]}; exakt gleiche Menge unter den {gem_n} gemeinsamen des Labels: {gem[3]}"
        )
    for i in sorted(lab, key=lambda x: rows[x]["reference"] or ""):
        r = rows[i]
        if r["urheber_art"] != "Fraktion":
            continue
        ps = {unit.get(r["datensatz"], {}).get(k, k) for k in (r["parteien"] or [])}
        ls = {x for x in lab[i]["urheber"]["label"] if x in fr_ids[r["datensatz"]]}
        if ps - ls:
            print(
                f"  `parteien` nennt, was das Label nicht nennt: {r['reference']} {sorted(ps - ls)} [{r['urheber_quelle']}]"
            )
    abw = [
        i
        for i in lab
        if regel_urheber(rows[i]["urheber_art"], rows[i]["fraktionen"])
        != lab[i]["urheber"]["label"]
    ]
    print(f"  Abweichungen Regelwerk gegen Label ({len(abw)}):")
    for i in sorted(abw, key=lambda x: (rows[x]["datensatz"], rows[x]["reference"] or "")):
        r = rows[i]
        print(
            f"    {r['reference']} [{r['paper_type']}, {r['urheber_art']}/{r['urheber_quelle']}] Regel {regel_urheber(r['urheber_art'], r['fraktionen'])} parteien {r['parteien']} Label {lab[i]['urheber']['label']}"
        )

    # --- adressat ------------------------------------------------------------------------------
    print("\nAdressat (das Regelwerk vergibt keinen): Label funktion x Label adressat")
    ad: Counter[tuple[str, str]] = Counter(
        (lab[i]["funktion"]["label"], lab[i]["adressat"]["label"]) for i in lab
    )
    for f in (*FUNKTIONEN, "unklar"):
        z = {a_: n for (f_, a_), n in ad.items() if f_ == f}
        if z:
            print(f"  {f:12s} {dict(sorted(z.items()))}")
    sym_b = [i for i in lab if rows[i]["funktion_b"] == "symbol"]
    print(
        f"  Regel B symbol: {len(sym_b)}, Label adressat {dict(Counter(lab[i]['adressat']['label'] for i in sym_b))}, Label funktion {dict(Counter(lab[i]['funktion']['label'] for i in sym_b))}"
    )


def schreibe_aufgaben(sample: pl.DataFrame, docs: pl.DataFrame) -> None:
    """Eine JSON-Zeile je Dokument: Titel, Art, Datum, Gremium, Textanfang (Rohtext, sonst klein).

    Weder die Funktion noch die Parteien, die die Regeln vergeben, stehen darin (F4: ohne die
    Ausgabe des zu prüfenden Verfahrens); auch die Schicht nicht, denn sie verrät die Funktion.
    """
    buch = tomllib.loads(CODEBUCH.read_text(encoding="utf-8"))
    d = {
        r["id"]: r
        for r in docs.select(
            "id",
            "reference",
            "name",
            "paper_type",
            "date",
            "gremium",
            "ordner",
            "file_name",
            "text",
            "datensatz",
        ).iter_rows(named=True)
    }
    roh: dict[str, dict[str, str]] = {}
    for ordner in {d[i]["ordner"] for i in sample["id"]}:
        f = ROHTEXT / f"{ordner}.parquet"
        if f.exists():
            namen = [d[i]["file_name"] for i in sample["id"] if d[i]["ordner"] == ordner]
            rt = pl.read_parquet(f, columns=["name", "text"]).filter(pl.col("name").is_in(namen))
            roh[ordner] = {r[0]: r[1] for r in rt.iter_rows()}
    AUFGABEN.parent.mkdir(parents=True, exist_ok=True)
    with AUFGABEN.open("w", encoding="utf-8") as fh:
        for i in sorted(sample["id"]):
            r = d[i]
            rt = roh.get(r["ordner"], {}).get(r["file_name"] or "")
            text, quelle = (rt, "rohtext") if rt else (r["text"] or "", "klein")
            rec = {
                "vorhaben": "15-funktion",
                "id": i,
                "codebuch": buch["meta"]["version"],
                "periode": r["datensatz"],
                "drucksache": r["reference"],
                "titel": r["name"],
                "dokumentart": r["paper_type"],
                "datum": r["date"].isoformat() if r["date"] else None,
                "gremium": r["gremium"],
                "textquelle": quelle,
                "textanfang": text[:TEXTANFANG],
                "grundsatz": buch["meta"]["grundsatz"],
                "fraktionen_der_periode": buch["fraktionen"][r["datensatz"]],
                "fragen": buch["fragen"],
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
