"""Rechnet die Zahlen von `26-beschluesse.md` nach (Vorhaben 26 „Beschlusslage und Antragserfolg").

    uv run python docs/plans/26-beschluesse-messung.py [--stichprobe] [--auswertung]

Liest je Profil, was `georep run` schreibt (`interim/papers.parquet`,
`processed/papers_gremien.parquet`, `processed/dokumente_urheber.parquet`), und die fünf Dateien
des Netzlaufs aus Fundament F6 unter `raw/` (`georep.council.council_files`; Sitzungen mit
Tagesordnung, Beratungen, Personen, Mitgliedschaften), gelesen mit den Modellen aus
`georep.oparl`. Die Beratungen sind je Body dieselbe Liste: die beiden älteren Düsseldorfer
Profile lesen eine Kopie der Datei der Hauptperiode. Fehlen die Dateien eines Profils
(Mönchengladbach am 2026-11-24), steht es mit „nicht abgerufen" da.

Dazu, nur lesend: die Regeln für Rolle und Antragsteller aus den Messskripten der Vorhaben 14 und 15
(`14-vorgaenge-messung.py`: `art2`; `15-funktion-messung.py`: `antragsteller`, Mehrheiten), die
starken Kanten der Stufe 2 von Vorhaben 14 (`processed/vorgang_kanten.parquet` aus dem Worktree
`14-vorgaenge`, beim ersten Lauf nach `$GEOREP_MESSDATEN/26-beschluesse/` kopiert und danach nur von
dort gelesen) und für die Kodieraufgaben den Rohtext aus Phase 0 (`$GEOREP_MESSDATEN/rohtext/`).

Mit `--stichprobe` schreibt es die Stichprobe von 150 Anträgen nach
`validierung/26-beschluesse/stichprobe.csv` und `.json` (nur Schlüssel und Schicht) und die
Kodieraufträge im Format von F4 nach `$GEOREP_MESSDATEN/kodierung/26-beschluesse/{A,B}/` (nie ins
Repo); ohne den Schalter prüft es nur, ob die gespeicherte Stichprobe noch dieselbe ist. Das Codebuch
(`validierung/26-beschluesse/codebuch.toml`) ist von Hand geschrieben und wird nur gelesen.
Zusammenführen und Schlichten gehen über `georep validate merge 26-beschluesse`.

Mit `--auswertung` wertet es die Regel gegen `validierung/26-beschluesse/labels.csv` aus (nach der
Schlichtung), in den Stufen der Vorab-Festlegung (§ 3.1 des Messdokuments): volle Klasse, Rückfall 1
ohne Prüfauftrag, Rückfall 2 grobe Klassen.

Laufzeit rund 15 Sekunden (drei Netzläufe laden rund 8 s).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("POLARS_MAX_THREADS", "4")
import polars as pl  # noqa: E402

from georep.council import JsonlStore, council_files  # noqa: E402
from georep.layout import Layout  # noqa: E402
from georep.oparl import OparlAgendaItem, OparlConsultation, OparlMeeting  # noqa: E402
from georep.settings import Settings, load_settings  # noqa: E402
from georep.validation.codebook import load_codebook  # noqa: E402
from georep.validation.paths import ValidationPaths  # noqa: E402
from georep.validation.sample import rank  # noqa: E402
from georep.validation.tasks import questions, write_assignment  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PLANS = Path(__file__).resolve().parent
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
EIGENE = MESSDATEN / "26-beschluesse"
ROHTEXT = MESSDATEN / "rohtext"
KODIERUNG = MESSDATEN / "kodierung" / "26-beschluesse"
PROJEKT = "26-beschluesse"
VALIDIERUNG = REPO / "validierung" / PROJEKT
STICHPROBE = VALIDIERUNG / "stichprobe.csv"
STICHPROBE_META = VALIDIERUNG / "stichprobe.json"
LABELS = VALIDIERUNG / "labels.csv"
VORGAENGE_QUELLE = Path(
    os.environ.get("GEOREP_VORGAENGE", "/media/konrad/xtraspace/georep/worktrees/14-vorgaenge/data")
)
SEED = 26
TEXTANFANG = 2500  # Zeichen Rohtext je Antrag im Kodierauftrag
ABRUF = dt.date(2026, 11, 23)  # Netzlauf aus F6 (2026-11-23, 23:29 bis 2026-11-24, 00:32)

# Profil -> (Stadt, Datensatz). Die drei Düsseldorfer Perioden sind disjunkt.
PROFILE = (
    ("duesseldorf-2014", "dus", "2014-2020"),
    ("duesseldorf", "dus", "2020-2025"),
    ("duesseldorf-2025", "dus", "2025-"),
    ("moenchengladbach", "mg", "mg-2020-2025"),
)
HAUPT = "2020-2025"

# ================================================================================================
# Vorab festgelegt (Messdokument § 3.1, Commit d68962e, 2026-11-24 00:41): Wert von `result` ->
# (Stufe, Klasse). Stufe "sache" ist eine Entscheidung in der Sache, "stand" alles andere.
# Ein Wert, der hier fehlt, bricht die Messung ab: der Server hätte seinen Wortschatz geändert.
# ================================================================================================
RESULT: dict[str, tuple[str, str]] = {
    "einstimmig beschlossen": ("sache", "beschlossen"),
    "mehrheitlich beschlossen": ("sache", "beschlossen"),
    "beschlossen": ("sache", "beschlossen"),
    "Empfehlung einstimmig beschlossen": ("sache", "beschlossen"),
    "Empfehlung mehrheitlich beschlossen": ("sache", "beschlossen"),
    "abweichend beschlossen": ("sache", "geaendert"),
    "Empfehlung abweichend beschlossen": ("sache", "geaendert"),
    "einstimmig abgelehnt": ("sache", "abgelehnt"),
    "mehrheitlich abgelehnt": ("sache", "abgelehnt"),
    "abgelehnt aufgrund Stimmengleichheit": ("sache", "abgelehnt"),
    "zurückgewiesen": ("sache", "abgelehnt"),
    "Empfehlung einstimmig abgelehnt": ("sache", "abgelehnt"),
    "Empfehlung mehrheitlich abgelehnt": ("sache", "abgelehnt"),
    "zurückgezogen": ("sache", "zurueckgezogen"),
    "zur Kenntnis genommen": ("stand", "erledigt"),
    "passieren lassen": ("stand", "erledigt"),
    "beantwortet": ("stand", "erledigt"),
    "schriftlich beantwortet": ("stand", "erledigt"),
    "vertagt": ("stand", "vertagt"),
    "zurückgestellt": ("stand", "vertagt"),
    "verwiesen": ("stand", "offen"),
}
KLASSEN = (
    "beschlossen",
    "geaendert",
    "abgelehnt",
    "zurueckgezogen",
    "erledigt",
    "vertagt",
    "offen",
    "ohne_ergebnis",
)
ANGENOMMEN = ("beschlossen", "geaendert")
ABSCHLIESSEND = ("beschlossen", "geaendert", "abgelehnt", "zurueckgezogen", "erledigt")
GROB = {
    "beschlossen": "angenommen",
    "geaendert": "angenommen",
    "abgelehnt": "abgelehnt",
    "zurueckgezogen": "ohne_sachbeschluss",
    "erledigt": "ohne_sachbeschluss",
    "vertagt": "offen",
    "offen": "offen",
    "ohne_ergebnis": "ohne_ergebnis",
}
# Feste Aufteilung der Stichprobe (§ 3.1); "pruefauftrag" = angenommen mit Prüfauftrag.
AUFTEILUNG = {
    "beschlossen": 25,
    "geaendert": 20,
    "pruefauftrag": 20,
    "abgelehnt": 20,
    "zurueckgezogen": 15,
    "erledigt": 15,
    "vertagt": 15,
    "offen": 10,
    "ohne_ergebnis": 10,
}

# ================================================================================================
# Regel für den Prüfauftrag (nach der Vorab-Festlegung, vor dem Ziehen der Stichprobe committet,
# e2b3545). Gelesen wird der Beschlusstext eines Antrags im kleingeschriebenen Korpus: vom letzten
# Marker („antrag:", „folgendes zu beschließen:", „beschlussvorschlag" …) vor der Begründung bis zu
# ihr. Ein Satz ist eine Prüfung, wenn er ein Prüfwort trägt; er trägt zusätzlich eine Maßnahme, wenn
# vor dem Prüfwort eine steht („einzurichten und zu berichten") oder danach eine folgt, die nicht in
# einer Frage („prüfen, ob …") oder unter Vorbehalt steht. Ein Satz ohne Prüfwort ist eine Maßnahme,
# wenn er eine Handlung festlegt. Prüfauftrag heißt: mindestens ein Prüfsatz und kein Maßnahmesatz.
# ================================================================================================
MARKER = re.compile(
    r"(?:(?:änderungs|ergänzungs|haushalts|zusatz)?-?antrag\s*:"
    r"|beschlussvorschlag\s*:?|beschlussentwurf\s*:?|beschlusstext\s*:?"
    r"|(?:folgendes|nachstehendes|wie folgt|folgenden beschluss)\s+zu\s+(?:beschließen|fassen)\s*:?"
    r"|möge\s+(?:folgendes\s+|wie folgt\s+)?beschließen\s*:?"
    r"|(?:beschließen|abstimmen) zu lassen\s*:?|zur abstimmung zu (?:bringen|stellen)\s*:?)"
)
BEGRUENDUNG = re.compile(r"begründung|sachdarstellung|erläuterung\s*:|mit freundlichen grüßen")
BESCHLUSS_FENSTER = 2000  # Zeichen vom Anfang, in denen der Marker steht
BESCHLUSS_MAX = 1500  # höchstens so viel Beschlusstext
PRUEFWORT = re.compile(
    r"prüf|untersuch|evaluier|machbarkeit|bericht|sachstand|darzustellen|darstellung|aufzuzeigen"
    r"|zu informieren|informier|konzept|vorzulegen|vorlegen|zu erarbeiten|erarbeit|zu klären"
    r"|zu ermitteln|stellung zu nehmen|stellungnahme|auskunft|zu erläutern|eruier|auszuloten|sondier"
    r"|bewert|analys|gutacht|studie|erhebung|zählung|vorzustellen|vorstellung|zu präsentieren"
    r"|präsentation|zu unterrichten|unterricht"
)
# Wörter, die ein Prüfwort enthalten, aber keine Prüfung verlangen.
KEIN_PRUEFWORT = re.compile(
    r"beschluss\s?darstellung|darstellung des beschlusses|prüfstand|prüfungsamt"
)
TRENNBAR = (
    r"an|auf|aus|ab|ein|um|her|hin|vor|zu|bei|mit|nach|dar|fest|frei|bereit|durch|weg|zurück"
    r"|wieder|hinzu|herbei|instand|sicher|statt|teil|still|weiter|fort|offen|bekannt"
)
# Kein Verb hinter „zu": Artikel, Pronomen, feste Wendungen („zu diesen Themen", „zu Lasten").
KEIN_VERB = (
    r"den|dem|der|denen|diesen|einen|ihnen|ihren|seinen|allen|unseren|welchen|jenen|eigenen|anderen"
    r"|beiden|neuen|folgenden|lasten|gunsten|zeiten|seiten|zwecken|ehren|beginn|kosten|fragen|themen"
)
MASSNAHME = re.compile(
    rf"\b[a-zäöüß]*(?:{TRENNBAR})zu[a-zäöüß]{{3,}}n\b"
    rf"|\bzu (?!(?:{KEIN_VERB})\b)[a-zäöüß]{{3,}}n\b"
    r"|\b(?:die stadt|der rat|die bezirksvertretung|die bv ?\d*|der ausschuss|die verwaltung"
    r"|der oberbürgermeister|der jugendrat|der beirat)\b[^.,]{0,40}?\b(?:führt|beteiligt|richtet"
    r"|schafft|setzt|nimmt|gibt|errichtet|übernimmt|benennt|fördert|startet|veranstaltet|baut"
    r"|pflanzt|sorgt|tritt|schließt|ändert|verzichtet|beschafft|erhöht|senkt|stattet)\b"
    r"|\bbeschließt\b(?!\W+(?:dass|,)?\s*(?:die |der )?(?:verwaltung|oberbürgermeister))"
    r"|\bbewilligt\b|\bgewährt\b|\bvergibt\b|\bstellt\b[^.]{0,80}\b(?:bereit|ein)\b"
    r"|\b(?:haushalts|finanz|sach|personal|eigen)?mittel\b[^.]{0,120}\b(?:bereit\w*|ein\b|eingestellt|zur verfügung)"
    r"|\b(?:euro|haushalt\w*)\b[^.]{0,80}\b(?:eingestellt|bereitgestellt|zur verfügung gestellt|einzustellen)"
    r"|\bwird wie folgt (?:geändert|ergänzt|gefasst)|\bwird (?:ersetzt|gestrichen|ergänzt)\b"
    r"|\blehnt\b[^.]{0,60}\bab\b|\bunterstützt\b|\bbegrüßt\b|\bsetzt sich\b|\bverurteilt\b"
    r"|\bbekennt sich\b|\bspricht sich\b|\bstimmt\b[^.]{0,60}\bzu\b|\bsoll(?:en)?\b[^.]{0,100}\bwerden\b"
    r"|\b(?:wird|werden)\b[^.]{0,120}?\b(?:festgesetzt|eingerichtet|eingeführt|umgesetzt|aufgestellt"
    r"|angebracht|errichtet|ausgewiesen|bereitgestellt|eingestellt|gestrichen|ausgesetzt|durchgeführt"
    r"|angelegt|erhöht|gesenkt|gekürzt|verlängert|vergeben|zurückgenommen|fortgeschrieben|benannt"
    r"|umbenannt|saniert|gepflanzt|installiert|geschaffen|freigegeben|aufgehoben|verkauft|erworben)\b"
)
# Eine Maßnahme unter dem Vorbehalt der Prüfung („wenn die Prüfung positiv ausfällt, …") gehört
# zur Prüfung (Codebuch, Frage `auftrag`).
VORBEHALT = re.compile(
    r"\b(?:wenn|sofern|falls|soweit|sollte)\b[^.]{0,60}\b(?:prüf|möglich|machbar)"
)
# Verben, die zu einer Prüfung oder einem Bericht gehören oder neutral sind: keine Maßnahme.
NEUTRAL = frozenset(
    "vorzulegen vorzustellen darzustellen darzulegen aufzuzeigen mitzuteilen aufzulisten "
    "auszuarbeiten einzuholen anzufertigen durchzuführen vorzunehmen nachzugehen auszuwerten "
    "berichten informieren erläutern ermitteln klären erarbeiten untersuchen evaluieren prüfen "
    "überprüfen bewerten analysieren erheben entwickeln erstellen beauftragen vergeben erwarten "
    "beantworten werden lassen nehmen setzen bringen stellen beraten erfahren wissen einzuladen".split()
)
FRAGE = re.compile(
    r"^\W{0,4}(?:[a-zäöüß]+\W+){0,3}?(?:ob|wie|inwieweit|inwiefern|welche\w*|wann|wo\w*|dass|weshalb"
    r"|warum|unter welchen|in welche\w*|mit welche\w*)\b"
)
SATZ = re.compile(r"(?<=[.;!?])\s+|\s(?=\d{1,2}[.)]\s)|\s•\s|\s[-–]\s(?=[a-zäöü])")
TITEL_PRUEF = re.compile(
    r"prüfauftrag|prüfantrag|\bprüfen\b|\bprüfung\b|sachstand|bericht(?!s?vorlage)"
)
RAHMEN = re.compile(r"tagesordnung|bitte[nt]? (?:ich|wir) sie|zur abstimmung")


def beschlusstext(text: str | None) -> tuple[str, bool]:
    """(Beschlusstext, Marker gefunden) im kleingeschriebenen Text eines Antrags."""
    t = text or ""
    b = BEGRUENDUNG.search(t, 40)
    ende = b.start() if b else min(len(t), BESCHLUSS_FENSTER)
    start, gefunden = 0, False
    for m in MARKER.finditer(t, 0, min(ende, BESCHLUSS_FENSTER)):
        start, gefunden = m.end(), True
    return t[start:ende][:BESCHLUSS_MAX], gefunden


def saetze(s: str) -> list[str]:
    return [x for x in SATZ.split(s) if x and x.strip()]


def massnahme(s: str) -> bool:
    """Legt dieser Teil eines Satzes eine Handlung fest (ein Verb außerhalb von ``NEUTRAL``)?"""
    for m in MASSNAHME.finditer(s):
        wort = m.group(0).split()[-1] if m.group(0).startswith("zu ") else m.group(0)
        if wort.split()[0] in NEUTRAL or wort in NEUTRAL:
            continue
        return True
    return False


def pruefauftrag(titel: str | None, text: str | None) -> tuple[bool, str]:
    """(Prüfauftrag, Quelle): Quelle `text` (Marker gefunden), `anfang` (ohne Marker), `titel`.

    Ein Satz mit Prüfwort ist eine Prüfung; er trägt zusätzlich eine Maßnahme, wenn vor dem
    Prüfwort eine steht oder danach eine folgt, die nicht in einer Frage („prüfen, ob …") liegt.
    Ein Satz ohne Prüfwort und ohne Fragezeichen ist eine Maßnahme, wenn er eine Handlung festlegt.
    Prüfauftrag heißt: mindestens eine Prüfung, keine Maßnahme.
    """
    seg, gefunden = beschlusstext(text)
    if not gefunden and not (text or "").strip():
        return bool(TITEL_PRUEF.search((titel or "").lower())), "titel"
    pruef = mass = 0
    for s in saetze(seg):
        if RAHMEN.search(s):
            continue
        s2 = KEIN_PRUEFWORT.sub(" ", s)
        m = PRUEFWORT.search(s2)
        if m:
            pruef += 1
            tail = s2[m.end() :]
            if VORBEHALT.search(s2):
                continue
            if massnahme(s2[: m.start()]) or (not FRAGE.search(tail[:60]) and massnahme(tail)):
                mass += 1
        elif "?" not in s2 and massnahme(s2):
            mass += 1
    return pruef > 0 and mass == 0, "text" if gefunden else "anfang"


# ================================================================================================
# Laden
# ================================================================================================
def lade_modul(name: str, datei: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, PLANS / datei)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


M14 = lade_modul("m14_vorgaenge", "14-vorgaenge-messung.py")
M15 = lade_modul("m15_funktion", "15-funktion-messung.py")


@dataclass(frozen=True)
class Schritt:
    """Ein Tagesordnungspunkt, der eine Beratung des Antrags behandelt."""

    beratung: str
    rolle: str
    gremium: str
    sitzung: dt.datetime | None
    nummer: str
    ordnung: int
    top: str
    bezeichnung: str
    result: str | None

    def schluessel(self) -> tuple[str, int, str]:
        return (self.sitzung.isoformat() if self.sitzung else "", self.ordnung, self.top)


@dataclass
class Profil:
    slug: str
    stadt: str
    datensatz: str
    settings: Settings
    layout: Layout
    docs: pl.DataFrame
    abgerufen: bool
    meetings: dict[str, OparlMeeting]
    items: dict[str, OparlAgendaItem]
    cons: dict[str, OparlConsultation]
    folge: dict[str, list[Schritt]]  # Paper-ID -> Schritte, nach Sitzung sortiert
    beratungen: dict[str, list[OparlConsultation]]  # Paper-ID -> Beratungen
    gremien: dict[str, str]  # Organisations-URL -> Kürzel


def kuerzel(settings: Settings) -> dict[str, str]:
    return dict(settings.bodies.organizations)


def org_name(url: str, table: dict[str, str]) -> str:
    tail = "/".join(url.rstrip("/").split("/")[-2:])
    return table.get(tail, tail)


def lade(slug: str, stadt: str, datensatz: str) -> Profil:
    settings = load_settings(profile=slug)
    layout = Layout.from_settings(settings)
    root = layout.root
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
    docs = (
        corpus.join(gremien, on="id", how="left")
        .join(urheber.rename({"quelle": "urheber_quelle"}), on="id", how="left")
        .with_columns(pl.lit(stadt).alias("stadt"), pl.lit(datensatz).alias("datensatz"))
        .sort("id")
    )
    files = council_files(layout)
    abgerufen = files.meetings.is_file() and files.consultations.is_file()
    meetings = JsonlStore(files.meetings, OparlMeeting).load() if abgerufen else {}
    items = JsonlStore(files.agenda_items, OparlAgendaItem).load() if abgerufen else {}
    cons = JsonlStore(files.consultations, OparlConsultation).load() if abgerufen else {}
    table = kuerzel(settings)
    ids = set(docs.get_column("id").to_list())
    beratungen: dict[str, list[OparlConsultation]] = defaultdict(list)
    for c in cons.values():
        if c.paper in ids:
            beratungen[c.paper].append(c)
    by_cons: dict[str, list[OparlAgendaItem]] = defaultdict(list)
    for i in items.values():
        if i.consultation:
            by_cons[i.consultation].append(i)
    folge: dict[str, list[Schritt]] = {}
    for paper, cs in beratungen.items():
        steps: list[Schritt] = []
        for c in cs:
            linked = {i.id: i for i in by_cons.get(c.id, [])}
            if c.agenda_item and c.agenda_item in items and c.agenda_item not in linked:
                linked[c.agenda_item] = items[c.agenda_item]
            for i in linked.values():
                m = meetings.get(i.meeting or "")
                orgs = m.organization if m and m.organization else c.organization
                steps.append(
                    Schritt(
                        beratung=c.id,
                        rolle=c.role or "",
                        gremium="+".join(org_name(o, table) for o in orgs) or "?",
                        sitzung=m.start if m else None,
                        nummer=i.number or "",
                        ordnung=i.order or 0,
                        top=i.id,
                        bezeichnung=i.name or "",
                        result=i.result,
                    )
                )
        folge[paper] = sorted(steps, key=Schritt.schluessel)
    return Profil(
        slug,
        stadt,
        datensatz,
        settings,
        layout,
        docs,
        abgerufen,
        meetings,
        items,
        cons,
        folge,
        beratungen,
        table,
    )


# ================================================================================================
# Die Regel
# ================================================================================================
def klasse(steps: Sequence[Schritt]) -> tuple[str, Schritt | None]:
    """(Klasse, maßgeblicher Schritt) nach der letzten Entscheidung in der Sache (§ 3.1)."""
    mit = [s for s in steps if s.result]
    for s in mit:
        if s.result not in RESULT:
            raise SystemExit(f"unbekannter Wert von result: {s.result!r} ({s.top})")
    sache = [s for s in mit if RESULT[s.result or ""][0] == "sache"]
    if sache:
        last = max(sache, key=Schritt.schluessel)
        return RESULT[last.result or ""][1], last
    if mit:
        last = max(mit, key=Schritt.schluessel)
        return RESULT[last.result or ""][1], last
    return "ohne_ergebnis", None


def warum_ohne(p: Profil, paper: str) -> str:
    """Warum ein Antrag ohne Ergebnis bleibt; die erste zutreffende Ursache."""
    cs = p.beratungen.get(paper, [])
    if not cs:
        return "keine Beratung"
    steps = p.folge.get(paper, [])
    if steps:
        if all(s.sitzung and s.sitzung.date() > ABRUF for s in steps):
            return "Sitzung nach dem Abruf"
        return "Tagesordnungspunkt ohne Ergebnis"
    if all(not c.meeting for c in cs):
        return "Beratung ohne Sitzung"
    if any(c.meeting and c.meeting not in p.meetings for c in cs):
        return "Sitzung nicht in der Liste"
    return "Sitzung ohne passenden Tagesordnungspunkt"


def haushaltsantrag(paper_type: str | None, name: str | None) -> bool:
    return "haushalt" in ((paper_type or "") + " " + (name or "")).lower()


# ================================================================================================
# Hilfen
# ================================================================================================
def pct(a: int, b: int) -> str:
    return f"{a} von {b} ({100 * a / b:.1f} %)" if b else f"{a} von 0"


def p1(a: float, b: float) -> str:
    return f"{100 * a / b:.1f} %" if b else "–"


def wilson(k: float, n: float, z: float = 1.959964) -> tuple[float, float]:
    if n <= 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def titel(s: str) -> None:
    print(f"\n{'=' * 100}\n{s}\n{'=' * 100}")


def tage_stats(values: Sequence[int]) -> str:
    if not values:
        return "n = 0"
    v = sorted(values)
    q = statistics.quantiles(v, n=10, method="inclusive") if len(v) > 1 else [v[0]] * 9
    q4 = statistics.quantiles(v, n=4, method="inclusive") if len(v) > 1 else [v[0]] * 3
    return (
        f"n = {len(v)}, Median {statistics.median(v):g}, Q1 {q4[0]:g}, Q3 {q4[2]:g}, P90 {q[8]:g}"
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ================================================================================================
# Zusammenstellen: eine Zeile je Drucksache mit Rolle, Klasse, Prüfauftrag, Antragsteller
# ================================================================================================
def zeilen(p: Profil) -> pl.DataFrame:
    marker, muster, _kurz = M15.titelparteien(p.slug)
    del marker
    rows: list[dict[str, Any]] = []
    for r in p.docs.iter_rows(named=True):
        rolle = M14.art2(r["paper_type"], r["name"])
        steps = p.folge.get(r["id"], [])
        k, s = klasse(steps) if p.abgerufen else ("ohne_ergebnis", None)
        pa, pq = pruefauftrag(r["name"], r["text"]) if rolle == "antrag" else (False, "")
        parteien = (
            M15.antragsteller(
                r["paper_type"],
                r["name"],
                r["parteien"],
                r["urheber_art"],
                r["urheber_quelle"],
                muster,
                r["text"],
            )
            if rolle == "antrag"
            else []
        )
        einheit = M15.FRAKTION_EINHEIT.get(p.datensatz, {})
        fraktionen = sorted({einheit.get(x, x) for x in parteien})
        rows.append(
            {
                "id": r["id"],
                "profil": p.slug,
                "stadt": p.stadt,
                "datensatz": p.datensatz,
                "reference": r["reference"],
                "date": r["date"],
                "paper_type": r["paper_type"],
                "name": r["name"],
                "file_name": r["file_name"],
                "rolle": rolle,
                "gremium": r["gremium"],
                "gremium_art": r["gremium_art"],
                "urheber_art": r["urheber_art"],
                "fraktionen": fraktionen,
                "haushalt": haushaltsantrag(r["paper_type"], r["name"]),
                "beratungen": len(p.beratungen.get(r["id"], [])),
                "schritte": len(steps),
                "mit_result": sum(1 for x in steps if x.result),
                "klasse": k,
                "result": s.result if s else None,
                "entscheidung_gremium": s.gremium if s else None,
                "entscheidung_datum": s.sitzung.date() if s and s.sitzung else None,
                "entscheidung_rolle": s.rolle if s else None,
                "pruefauftrag": pa,
                "pruef_quelle": pq,
                "warum_ohne": warum_ohne(p, r["id"])
                if k == "ohne_ergebnis" and p.abgerufen
                else "",
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).sort("id")


def schicht(k: str, pa: bool) -> str:
    return "pruefauftrag" if k in ANGENOMMEN and pa else k


# ================================================================================================
# Messung
# ================================================================================================
def server_fuellt(profile: Sequence[Profil]) -> None:
    titel("§ 3.2 Was der Server füllt (Sitzungen, Tagesordnungspunkte, Beratungen)")
    for p in profile:
        if not p.abgerufen:
            print(f"\n{p.datensatz} ({p.slug}): nicht abgerufen")
            continue
        items = list(p.items.values())
        meets = list(p.meetings.values())
        past = [m for m in meets if m.start and m.start.date() <= ABRUF]
        print(
            f"\n{p.datensatz} ({p.slug}): {len(meets)} Sitzungen ({len(past)} bis zum Abruf), "
            f"{len(items)} Tagesordnungspunkte"
        )
        past_ids = {m.id for m in past}
        it_past = [i for i in items if i.meeting in past_ids]
        print(
            f"  Punkte mit result: {pct(sum(1 for i in items if i.result), len(items))}; "
            f"in vergangenen Sitzungen {pct(sum(1 for i in it_past if i.result), len(it_past))}"
        )
        mitb = [i for i in it_past if i.consultation]
        print(
            f"  Punkte mit consultation: {pct(sum(1 for i in items if i.consultation), len(items))}; "
            f"davon (vergangen) mit result {pct(sum(1 for i in mitb if i.result), len(mitb))}"
        )
        print(
            f"  resolutionText {sum(1 for i in items if i.resolution_text)}, resolutionFile "
            f"{sum(1 for i in items if i.resolution_file)}, Ergebniswerte "
            f"{len({i.result for i in items if i.result})}"
        )
        print(
            f"  Sitzungen mit Niederschrift (Anlage 'Niederschrift…'): "
            f"{pct(sum(1 for m in past if any((f.name or '').startswith('Niederschrift') for f in m.auxiliary_file)), len(past))}"
        )
    p0 = next(p for p in profile if p.abgerufen)
    cons = list(p0.cons.values())
    print(f"\nBeratungen (Liste des Bodys, {p0.slug}): {len(cons)}")
    print(
        f"  mit meeting {pct(sum(1 for c in cons if c.meeting), len(cons))}, mit agendaItem "
        f"{pct(sum(1 for c in cons if c.agenda_item), len(cons))}"
    )
    print(f"  role: {Counter(c.role for c in cons).most_common()}")
    print(f"  authoritative: {Counter(c.authoritative for c in cons).most_common()}")
    # Verbindung: agendaItem.consultation gegen consultation.agendaItem
    for p in profile:
        if not p.abgerufen:
            continue
        nennt = Counter()
        for c in p.cons.values():
            if not c.agenda_item:
                continue
            if c.agenda_item not in p.items:
                nennt["Punkt nicht in der Liste dieses Profils"] += 1
                continue
            i = p.items[c.agenda_item]
            if i.consultation == c.id:
                nennt["gegenseitig"] += 1
            elif i.consultation is None:
                nennt["Punkt nennt keine Beratung"] += 1
            else:
                nennt["Punkt nennt eine andere Beratung"] += 1
        zwei = Counter(len(v) for v in _items_je_beratung(p).values())
        print(
            f"  {p.datensatz}: consultation.agendaItem -> {dict(nennt)}; Punkte je Beratung "
            f"(über agendaItem.consultation): {dict(sorted(zwei.items()))}"
        )


def _items_je_beratung(p: Profil) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for i in p.items.values():
        if i.consultation:
            out[i.consultation].append(i.id)
    return out


def je_gremium_result(p: Profil) -> None:
    """Anteil der Punkte mit result in vergangenen Sitzungen, je Gremium (mit Beratung)."""
    past = {m.id: m for m in p.meetings.values() if m.start and m.start.date() <= ABRUF}
    n: Counter[str] = Counter()
    k: Counter[str] = Counter()
    for i in p.items.values():
        m = past.get(i.meeting or "")
        if m is None or not i.consultation:
            continue
        g = "+".join(org_name(o, p.gremien) for o in m.organization) or "?"
        n[g] += 1
        k[g] += bool(i.result)
    print(
        f"\n  {p.datensatz}: Punkte mit Beratung in vergangenen Sitzungen, Anteil mit result, "
        f"Gremien mit mindestens 200 Punkten:"
    )
    for g, total in n.most_common():
        if total >= 200:
            print(f"    {g:10s} {total:6d}  {p1(k[g], total)}")


def weg_zum_ergebnis(df: pl.DataFrame) -> None:
    titel("§ 3.3 Vom Antrag zum Ergebnis: Abdeckung je Stufe des Weges")
    for ds in df.get_column("datensatz").unique(maintain_order=True).to_list():
        for rolle in ("antrag", "vorlage", "anfrage", "information"):
            d = df.filter((pl.col("datensatz") == ds) & (pl.col("rolle") == rolle))
            n = d.height
            if not n:
                continue
            mb = d.filter(pl.col("beratungen") > 0).height
            mt = d.filter(pl.col("schritte") > 0).height
            mr = d.filter(pl.col("mit_result") > 0).height
            print(
                f"  {ds:12s} {rolle:11s} n {n:6d}  Beratung {p1(mb, n):>7s}  Tagesordnungspunkt "
                f"{p1(mt, n):>7s}  mit Ergebnis {p1(mr, n):>7s}"
            )
    print("\n  Beratungen und Tagesordnungspunkte je Antrag (Hauptperiode):")
    a = df.filter((pl.col("datensatz") == HAUPT) & (pl.col("rolle") == "antrag"))
    print(
        f"    Beratungen: {dict(sorted(Counter(min(x, 4) for x in a.get_column('beratungen')).items()))}"
        f"  Punkte: {dict(sorted(Counter(min(x, 4) for x in a.get_column('schritte')).items()))}"
    )
    print("\n  Anträge ohne Ergebnis und warum:")
    for ds in df.get_column("datensatz").unique(maintain_order=True).to_list():
        o = df.filter(
            (pl.col("datensatz") == ds)
            & (pl.col("rolle") == "antrag")
            & (pl.col("klasse") == "ohne_ergebnis")
        )
        if not o.height:
            continue
        w = Counter(o.get_column("warum_ohne").to_list())
        h = o.filter(pl.col("haushalt")).height
        print(f"    {ds:12s} {o.height:5d}: {dict(w.most_common())}; davon Haushaltsanträge {h}")
        ohne_top = o.filter(pl.col("warum_ohne") == "Tagesordnungspunkt ohne Ergebnis")
        print(
            f"      Tagesordnungspunkt ohne Ergebnis, je Gremium der Drucksache: "
            f"{Counter(ohne_top.get_column('gremium').to_list()).most_common(8)}"
        )


def klassen_je_periode(df: pl.DataFrame) -> None:
    titel("§ 3.4 Klassen der Beschlusslage je Periode (Anträge)")
    for ds in df.get_column("datensatz").unique(maintain_order=True).to_list():
        a = df.filter((pl.col("datensatz") == ds) & (pl.col("rolle") == "antrag"))
        n = a.height
        if not n:
            continue
        c = Counter(a.get_column("klasse").to_list())
        line = "  ".join(f"{k} {c[k]} ({p1(c[k], n)})" for k in KLASSEN)
        print(f"\n  {ds} (n = {n}): {line}")
        mit = n - c["ohne_ergebnis"]
        absch = sum(c[k] for k in ABSCHLIESSEND)
        print(
            f"    mit Ergebnis (Klasse außer ohne_ergebnis): {pct(mit, n)}; abschließend: {pct(absch, n)}"
        )
        ang = a.filter(pl.col("klasse").is_in(ANGENOMMEN))
        pa = ang.filter(pl.col("pruefauftrag")).height
        print(
            f"    angenommen {ang.height}, davon Prüfauftrag {pct(pa, ang.height)}; Prüfauftrag-Quelle "
            f"{dict(Counter(a.get_column('pruef_quelle').to_list()))}"
        )
        ohne_h = a.filter(~pl.col("haushalt"))
        c2 = Counter(ohne_h.get_column("klasse").to_list())
        print(
            f"    ohne Haushaltsanträge (n = {ohne_h.height}): mit Ergebnis "
            f"{pct(ohne_h.height - c2['ohne_ergebnis'], ohne_h.height)}"
        )
        res = Counter(a.filter(pl.col("result").is_not_null()).get_column("result").to_list())
        print(f"    maßgeblicher Wert: {res.most_common()}")
    print("\n  Haushaltsanträge (Dokumentart oder Titel mit „Haushalt“), Klassen je Periode:")
    for ds in ("2014-2020", "2020-2025", "2025-"):
        h = df.filter(
            (pl.col("datensatz") == ds) & (pl.col("rolle") == "antrag") & pl.col("haushalt")
        )
        c = Counter(h.get_column("klasse").to_list())
        print(f"    {ds:10s} n {h.height:5d}: " + ", ".join(f"{k} {c[k]}" for k in KLASSEN if c[k]))
        rat = h.filter(pl.col("gremium") == "RAT")
        cr = Counter(rat.get_column("klasse").to_list())
        print(
            f"      davon im Rat n {rat.height}: "
            + ", ".join(f"{k} {cr[k]}" for k in KLASSEN if cr[k])
        )
    print(
        "\n  Wo „erledigt“ bei Anträgen gehäuft vorkommt (Gremium und Jahr der Entscheidung, mindestens 10):"
    )
    e = (
        df.filter((pl.col("rolle") == "antrag") & pl.col("entscheidung_datum").is_not_null())
        .with_columns(pl.col("entscheidung_datum").dt.year().alias("jahr"))
        .group_by("entscheidung_gremium", "jahr")
        .agg(pl.len().alias("n"), (pl.col("klasse") == "erledigt").sum().alias("erledigt"))
        .filter(pl.col("erledigt") >= 10)
        .sort("erledigt", descending=True)
    )
    for r in e.iter_rows(named=True):
        print(
            f"    {r['entscheidung_gremium']:8s} {r['jahr']}  {r['erledigt']:4d} von {r['n']:4d} ({p1(r['erledigt'], r['n'])})"
        )
    titel("§ 3.4b Beschlussvorlagen der Verwaltung und Anfragen, dieselbe Abbildung (beschreibend)")
    for rolle in ("vorlage", "anfrage"):
        for ds in df.get_column("datensatz").unique(maintain_order=True).to_list():
            a = df.filter((pl.col("datensatz") == ds) & (pl.col("rolle") == rolle))
            if not a.height:
                continue
            c = Counter(a.get_column("klasse").to_list())
            print(
                f"  {rolle:8s} {ds:12s} n {a.height:6d}: "
                + ", ".join(f"{k} {p1(c[k], a.height)}" for k in KLASSEN if c[k])
            )


def abdeckung_je(df: pl.DataFrame) -> None:
    titel("§ 3.5 Abdeckung je Gremium und je Fraktion (Anträge, alle drei Düsseldorfer Perioden)")
    a = df.filter((pl.col("rolle") == "antrag") & (pl.col("stadt") == "dus"))
    g = (
        a.group_by("gremium_art", "datensatz")
        .agg(
            pl.len().alias("n"),
            (pl.col("klasse") != "ohne_ergebnis").sum().alias("mit"),
            pl.col("klasse").is_in(list(ABSCHLIESSEND)).sum().alias("absch"),
        )
        .sort("datensatz", "n", descending=[False, True])
    )
    for r in g.iter_rows(named=True):
        print(
            f"  {r['datensatz']:10s} {str(r['gremium_art']):18s} n {r['n']:5d}  mit Ergebnis "
            f"{p1(r['mit'], r['n']):>7s}  abschließend {p1(r['absch'], r['n']):>7s}"
        )
    print(
        "\n  Gremien mit dem niedrigsten Anteil mit Ergebnis (mindestens 50 Anträge, Hauptperiode):"
    )
    h = (
        a.filter(pl.col("datensatz") == HAUPT)
        .group_by("gremium")
        .agg(pl.len().alias("n"), (pl.col("klasse") != "ohne_ergebnis").mean().alias("anteil"))
        .filter(pl.col("n") >= 50)
        .sort("anteil")
    )
    print(
        "   "
        + "; ".join(
            f"{r['gremium']} {r['n']} / {100 * r['anteil']:.1f} %"
            for r in h.head(8).iter_rows(named=True)
        )
    )
    print(
        "   höchste: "
        + "; ".join(
            f"{r['gremium']} {r['n']} / {100 * r['anteil']:.1f} %"
            for r in h.tail(5).iter_rows(named=True)
        )
    )
    print(
        "\n  Je Fraktion (gemeinsame Anträge je Fraktion; Hauptperiode): n, mit Ergebnis, abschließend"
    )
    e = a.filter(pl.col("datensatz") == HAUPT).explode("fraktionen")
    e = e.with_columns(pl.col("fraktionen").fill_null(pl.col("urheber_art")).alias("wer"))
    for r in (
        e.group_by("wer")
        .agg(
            pl.len().alias("n"),
            (pl.col("klasse") != "ohne_ergebnis").mean().alias("mit"),
            pl.col("klasse").is_in(list(ABSCHLIESSEND)).mean().alias("absch"),
        )
        .sort("n", descending=True)
        .iter_rows(named=True)
    ):
        if r["n"] >= 30:
            print(
                f"    {str(r['wer']):14s} {r['n']:5d}  {100 * r['mit']:5.1f} %  {100 * r['absch']:5.1f} %"
            )


def dauer(df: pl.DataFrame) -> None:
    titel(
        "§ 3.6 Dauer bis zur maßgeblichen Entscheidung (Tage vom Datum des Antrags bis zur Sitzung)"
    )
    a = df.filter(
        (pl.col("rolle") == "antrag")
        & (pl.col("stadt") == "dus")
        & pl.col("entscheidung_datum").is_not_null()
    ).with_columns((pl.col("entscheidung_datum") - pl.col("date")).dt.total_days().alias("tage"))
    neg = a.filter(pl.col("tage") < 0).height
    print(f"  Entscheidung vor dem Datum des Antrags: {neg} (gezählt, nicht verwendet)")
    a = a.filter(pl.col("tage") >= 0)
    print(f"  alle mit Entscheidung: {tage_stats(a.get_column('tage').to_list())}")
    for k in KLASSEN[:-1]:
        v = a.filter(pl.col("klasse") == k).get_column("tage").to_list()
        if v:
            print(f"    {k:15s} {tage_stats(v)}")
    for ga in ("bezirksvertretung", "ausschuss", "rat", "beirat"):
        v = (
            a.filter((pl.col("gremium_art") == ga) & pl.col("klasse").is_in(list(ABSCHLIESSEND)))
            .get_column("tage")
            .to_list()
        )
        if v:
            print(f"    abschließend, {ga:17s} {tage_stats(v)}")
    for ds in ("2014-2020", "2020-2025", "2025-"):
        v = (
            a.filter((pl.col("datensatz") == ds) & pl.col("klasse").is_in(list(ABSCHLIESSEND)))
            .get_column("tage")
            .to_list()
        )
        print(f"    abschließend, {ds:10s} {tage_stats(v)}")
    lang = (
        a.filter(pl.col("klasse").is_in(list(ABSCHLIESSEND))).sort("tage", descending=True).head(5)
    )
    print(
        "  längste: "
        + "; ".join(
            f"{r['reference']} {r['tage']} Tage ({r['klasse']}, {r['entscheidung_gremium']})"
            for r in lang.iter_rows(named=True)
        )
    )
    mehr = a.filter(pl.col("beratungen") > 1)
    print(
        f"  mit mehr als einer Beratung: {mehr.height}; {tage_stats(mehr.get_column('tage').to_list())}"
    )


def lade_kanten() -> pl.DataFrame | None:
    """Die starken Kanten aus Stufe 2 von Vorhaben 14, einmal nach messdaten kopiert."""
    EIGENE.mkdir(parents=True, exist_ok=True)
    frames = []
    for ordner in ("2014-2020", "duesseldorf", "2025", "moenchengladbach"):
        ziel = EIGENE / f"vorgang_kanten-{ordner}.parquet"
        quelle = VORGAENGE_QUELLE / ordner / "processed" / "vorgang_kanten.parquet"
        if not ziel.is_file() and quelle.is_file():
            shutil.copyfile(quelle, ziel)
        if ziel.is_file():
            frames.append(pl.read_parquet(ziel).with_columns(pl.lit(ordner).alias("ordner")))
    if not frames:
        return None
    return pl.concat(frames)


def pruefauftraege(df: pl.DataFrame, kanten: pl.DataFrame | None) -> None:
    titel("§ 3.7 Prüfaufträge und Folgevorlagen (starke Kanten aus Vorhaben 14)")
    if kanten is None:
        print("  Kanten von 14 fehlen; Abschnitt entfällt")
        return
    stark = kanten.filter(pl.col("stark"))
    print(
        f"  starke Kanten aus 14: {stark.height} (Dateien: {sorted(kanten.get_column('ordner').unique().to_list())}); "
        f"Typen {dict(Counter(stark.get_column('typ').to_list()).most_common())}"
    )
    rollen = dict(df.select("id", "rolle").iter_rows())
    datum = dict(df.select("id", "date").iter_rows())
    folge: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in stark.iter_rows(named=True):
        if rollen.get(r["von"]) in ("vorlage", "information", "bedarf", "af"):
            folge[r["nach"]].append((r["von"], r["typ"]))
    a = df.filter((pl.col("rolle") == "antrag") & (pl.col("stadt") == "dus"))
    print(
        "\n  Anteil der Anträge mit einer Folgevorlage der Verwaltung (starke Kante, die den Antrag nennt), je Klasse:"
    )
    for k in KLASSEN:
        ids = a.filter(pl.col("klasse") == k).get_column("id").to_list()
        mit = sum(1 for i in ids if folge.get(i))
        print(f"    {k:15s} {pct(mit, len(ids))}")
    ang = a.filter(pl.col("klasse").is_in(ANGENOMMEN))
    for pa in (True, False):
        d = ang.filter(pl.col("pruefauftrag") == pa)
        mit = sum(1 for i in d.get_column("id").to_list() if folge.get(i))
        print(
            f"  angenommen, {'Prüfauftrag' if pa else 'Sachbeschluss'}: mit Folgevorlage {pct(mit, d.height)}"
        )
    tage: list[int] = []
    for r in ang.filter(pl.col("pruefauftrag")).iter_rows(named=True):
        for von, _t in folge.get(r["id"], []):
            if r["entscheidung_datum"] and datum.get(von):
                d = (datum[von] - r["entscheidung_datum"]).days
                if d >= 0:
                    tage.append(d)
                    break
    print(
        f"  Tage vom Beschluss eines Prüfauftrags bis zur ersten Folgevorlage: {tage_stats(tage)}"
    )
    alle: dict[str, int] = Counter()
    for r in kanten.iter_rows(named=True):
        if rollen.get(r["von"]) in ("vorlage", "information", "bedarf", "af"):
            alle[r["nach"]] += 1
    for pa in (True, False):
        d = ang.filter(pl.col("pruefauftrag") == pa)
        mit = sum(1 for i in d.get_column("id").to_list() if alle.get(i))
        print(
            f"  angenommen, {'Prüfauftrag' if pa else 'Sachbeschluss'}: mit Folgevorlage über irgendeine Kante (auch schwach, Text): {pct(mit, d.height)}"
        )
    p90 = sorted(tage)[int(0.9 * (len(tage) - 1))] if tage else 365
    for ds in ("2014-2020", "2020-2025", "2025-"):
        d = ang.filter((pl.col("datensatz") == ds) & pl.col("pruefauftrag"))
        offen = [
            r
            for r in d.iter_rows(named=True)
            if not folge.get(r["id"])
            and r["entscheidung_datum"]
            and (ABRUF - r["entscheidung_datum"]).days > p90
        ]
        print(
            f"  {ds}: beschlossene Prüfaufträge {d.height}, ohne Folgevorlage und älter als P90 ({p90} Tage): "
            f"{len(offen)}"
        )
        for r in sorted(offen, key=lambda r: r["entscheidung_datum"])[:6]:
            print(
                f"      {r['reference']} {r['entscheidung_datum']} {r['entscheidung_gremium']} {(r['name'] or '')[:70]}"
            )
    print(
        "\n  Je Gremienart: Prüfaufträge unter den angenommenen Anträgen, mit Folgevorlage (alle drei Perioden)"
    )
    for ga in ("bezirksvertretung", "ausschuss", "rat", "beirat"):
        d = ang.filter(pl.col("gremium_art") == ga)
        pa = d.filter(pl.col("pruefauftrag"))
        mit = sum(1 for i in pa.get_column("id").to_list() if folge.get(i))
        print(
            f"    {ga:17s} angenommen {d.height:5d}, Prüfauftrag {p1(pa.height, d.height):>7s}, davon mit Folgevorlage {p1(mit, pa.height)}"
        )


def gegenproben(df: pl.DataFrame, profile: Sequence[Profil], kanten: pl.DataFrame | None) -> None:
    titel("§ 3.8 Gegenproben aus den Daten selbst")
    if kanten is None:
        print("  Kanten von 14 fehlen; Abschnitt entfällt")
        return
    # 1. Änderungsantrag (starke Kante `aenderung`, Antrag -> Vorlage) in derselben Sitzung wie die Vorlage
    stark = kanten.filter(pl.col("stark") & (pl.col("typ") == "aenderung"))
    folgen: dict[str, list[Schritt]] = {}
    for p in profile:
        folgen.update(p.folge)
    klasse_von = dict(df.select("id", "klasse").iter_rows())
    rolle = dict(df.select("id", "rolle").iter_rows())
    tab: Counter[tuple[str, str]] = Counter()
    beispiele: dict[tuple[str, str], list[str]] = defaultdict(list)
    ref = dict(df.select("id", "reference").iter_rows())
    titel_von = dict(df.select("id", "name").iter_rows())
    datensatz_von = dict(df.select("id", "datensatz").iter_rows())
    je: Counter[tuple[str, str, str, str]] = Counter()
    for r in stark.iter_rows(named=True):
        antrag, vorlage = r["von"], r["nach"]
        if rolle.get(antrag) != "antrag" or rolle.get(vorlage) not in ("vorlage", "bedarf", "af"):
            continue
        sa = [s for s in folgen.get(antrag, []) if s.result and RESULT[s.result][0] == "sache"]
        sv = {(s.sitzung, s.gremium): s for s in folgen.get(vorlage, []) if s.result}
        for s in sa:
            v = sv.get((s.sitzung, s.gremium))
            if v is None:
                continue
            ka = RESULT[s.result or ""][1]
            kv = RESULT[v.result or ""][1]
            ka = "angenommen" if ka in ANGENOMMEN else ka
            kv = {
                "geaendert": "geändert beschlossen",
                "beschlossen": "unverändert beschlossen",
            }.get(kv, kv)
            tab[(ka, kv)] += 1
            art = (
                "ergänzung"
                if re.search(r"ergänzung|begleit|zusatz", (titel_von.get(antrag) or "").lower())
                else "änderung"
            )
            je[(datensatz_von.get(antrag, "?"), art, ka, kv)] += 1
            if len(beispiele[(ka, kv)]) < 3:
                beispiele[(ka, kv)].append(f"{ref.get(antrag)} -> {ref.get(vorlage)}")
            break
    print(
        "  1. Änderungsantrag und geänderte Vorlage in derselben Sitzung desselben Gremiums "
        "(Ergebnis des Antrags x Ergebnis der Vorlage):"
    )
    for (ka, kv), n in sorted(tab.items(), key=lambda x: -x[1]):
        print(f"     {ka:15s} {kv:24s} {n:5d}   {beispiele[(ka, kv)]}")
    ang = sum(n for (ka, _), n in tab.items() if ka == "angenommen")
    ang_abw = tab[("angenommen", "geändert beschlossen")]
    abg = sum(n for (ka, _), n in tab.items() if ka == "abgelehnt")
    abg_unv = tab[("abgelehnt", "unverändert beschlossen")]
    print(
        f"     angenommen -> Vorlage geändert: {pct(ang_abw, ang)}; abgelehnt -> Vorlage unverändert: {pct(abg_unv, abg)}"
    )
    print(
        "     angenommene Anträge je Periode und Art (Titel: Ergänzungs-, Begleit-, Zusatzantrag gegen übrige):"
    )
    for ds in ("2014-2020", "2020-2025", "2025-"):
        for art in ("änderung", "ergänzung"):
            geaendert = je[(ds, art, "angenommen", "geändert beschlossen")]
            unv = je[(ds, art, "angenommen", "unverändert beschlossen")]
            if geaendert + unv:
                print(
                    f"       {ds:10s} {art:10s} Vorlage geändert {pct(geaendert, geaendert + unv)}"
                )
    del klasse_von


def nachtraege(df: pl.DataFrame, profile: Sequence[Profil], kanten: pl.DataFrame | None) -> None:
    """Zahlen, die das Messdokument zu den Lücken nennt (§ 3.3, § 3.5, § 3.7, § 5, Paket in § 2)."""
    titel("§ 3.3/3.5/3.7/5 Lücken: Sitzungen ohne Eintrag, Praxiszellen, Paketgröße")
    folge: dict[str, list[Schritt]] = {}
    for p in profile:
        folge.update(p.folge)
    a = df.filter((pl.col("rolle") == "antrag") & (pl.col("stadt") == "dus"))
    for ds in ("2014-2020", "2020-2025", "2025-"):
        o = a.filter((pl.col("datensatz") == ds) & (pl.col("klasse") == "ohne_ergebnis"))
        c: Counter[tuple[str, str]] = Counter()
        for i in o.get_column("id").to_list():
            for x in {
                (s.gremium, s.sitzung.date().isoformat() if s.sitzung else "")
                for s in folge.get(i, [])
            }:
                c[x] += 1
        print(f"  {ds}: Sitzungen mit den meisten Anträgen ohne Ergebnis: {c.most_common(5)}")
        if not c:
            continue
        (g, d), _n = c.most_common(1)[0]
        in_s = {
            i
            for i in o.get_column("id").to_list()
            if any(
                s.gremium == g and s.sitzung and s.sitzung.date().isoformat() == d
                for s in folge.get(i, [])
            )
        }
        rat = a.filter((pl.col("datensatz") == ds) & (pl.col("gremium_art") == "rat"))
        rest = rat.filter(~pl.col("id").is_in(list(in_s)))
        mit = rest.filter(pl.col("klasse") != "ohne_ergebnis").height
        print(f"    Rat ohne die Anträge dieser Sitzung: mit Ergebnis {pct(mit, rest.height)}")
        e = a.filter(pl.col("datensatz") == ds).explode("fraktionen")
        for f in sorted({x for x in e.get_column("fraktionen").to_list() if x}):
            ef = e.filter(pl.col("fraktionen") == f)
            oe = ef.filter(pl.col("klasse") == "ohne_ergebnis").get_column("id").to_list()
            hier = sum(1 for i in oe if i in in_s)
            if hier >= 10:
                print(
                    f"    {f}: {ef.height} Anträge, ohne Ergebnis {len(oe)}, davon in dieser Sitzung {hier}"
                )
    # Praxiszellen mit Schwelle 0,4 (Vorschlag für Stufe 2, § 5)
    z = (
        a.filter(pl.col("entscheidung_datum").is_not_null())
        .with_columns(pl.col("entscheidung_datum").dt.year().alias("jahr"))
        .group_by("entscheidung_gremium", "jahr")
        .agg(pl.len().alias("n"), (pl.col("klasse") == "erledigt").sum().alias("erl"))
        .filter((pl.col("erl") >= 10) & (pl.col("erl") / pl.col("n") >= 0.4))
    )
    zellen = {(r["entscheidung_gremium"], r["jahr"]) for r in z.iter_rows(named=True)}
    betroffen = a.filter(pl.col("klasse") == "erledigt").with_columns(
        pl.col("entscheidung_datum").dt.year().alias("jahr")
    )
    ids = [
        r["id"]
        for r in betroffen.iter_rows(named=True)
        if (r["entscheidung_gremium"], r["jahr"]) in zellen
    ]
    print(
        f"  Praxiszellen (Anteil erledigt >= 0,4, mindestens 10 erledigt): {sorted(zellen)}; Anträge erledigt darin: {len(ids)}"
    )
    alt = a.filter(pl.col("datensatz") == "2014-2020")
    mit = alt.filter((pl.col("klasse") != "ohne_ergebnis") & ~pl.col("id").is_in(ids)).height
    print(f"    2014-2020 mit Ergebnis, Praxiszellen als ohne Ergebnis: {pct(mit, alt.height)}")
    if kanten is not None:
        rollen = dict(df.select("id", "rolle").iter_rows())
        typ: dict[str, set[str]] = defaultdict(set)
        for r in kanten.filter(pl.col("stark")).iter_rows(named=True):
            if rollen.get(r["von"]) in ("vorlage", "information", "bedarf", "af"):
                typ[r["nach"]].add(r["typ"])
        e2 = a.filter((pl.col("klasse") == "erledigt") & pl.col("id").is_in(list(typ)))
        print(
            f"  erledigt mit Folgevorlage: {e2.height}; result {Counter(e2.get_column('result').to_list()).most_common()}; "
            f"Haushaltsanträge {e2.filter(pl.col('haushalt')).height}; Kantentypen "
            f"{Counter(t for i in e2.get_column('id').to_list() for t in typ[i]).most_common()}"
        )
    # Paket: Paper x Tagesordnungspunkt, drei Düsseldorfer Perioden
    rows = []
    for p in profile:
        if p.stadt != "dus":
            continue
        for pid, steps in p.folge.items():
            for st in steps:
                rows.append(
                    {
                        "id": pid,
                        "beratung": st.beratung,
                        "top": st.top,
                        "gremium": st.gremium,
                        "rolle": st.rolle,
                        "sitzung": st.sitzung.date() if st.sitzung else None,
                        "nummer": st.nummer,
                        "result": st.result,
                    }
                )
    paket = pl.DataFrame(rows).unique().sort("id", "sitzung", "top")
    EIGENE.mkdir(parents=True, exist_ok=True)
    ziel = EIGENE / "beratungsfolge-probe.parquet"
    paket.write_parquet(ziel, compression="zstd")
    print(
        f"  Paket Paper x Tagesordnungspunkt: {paket.height} Zeilen, {ziel.stat().st_size} Bytes (zstd)"
    )


def anfragen(df: pl.DataFrame) -> None:
    titel("§ 3.9 Anfragen: was der Tagesordnungspunkt sagt (für Vorhaben 14)")
    a = df.filter(
        (pl.col("rolle") == "anfrage")
        & (pl.col("stadt") == "dus")
        & (pl.col("datensatz") != "2014-2020")
    )
    print(
        f"  Hauptperiode und laufende Periode, {a.height} Anfragen; maßgeblicher Wert je Gremienart:"
    )
    for ga in ("rat", "ausschuss", "bezirksvertretung", "beirat"):
        d = a.filter(pl.col("gremium_art") == ga)
        if not d.height:
            continue
        c = Counter((x or "kein Ergebnis") for x in d.get_column("result").to_list())
        print(
            f"    {ga:17s} n {d.height:5d}: "
            + ", ".join(f"{k} {p1(v, d.height)}" for k, v in c.most_common(6))
        )
    rat = a.filter(pl.col("gremium") == "RAT")
    c = Counter((x or "kein Ergebnis") for x in rat.get_column("result").to_list())
    print(f"    RAT allein n {rat.height}: {c.most_common()}")


def erfolg(df: pl.DataFrame) -> None:
    titel("§ 3.10 Erfolg je Fraktion, standardisiert nach Gremium und Periode (explorativ)")
    a = df.filter(
        (pl.col("rolle") == "antrag")
        & (pl.col("stadt") == "dus")
        & pl.col("klasse").is_in([*ANGENOMMEN, "abgelehnt"])
    ).with_columns(pl.col("klasse").is_in(ANGENOMMEN).alias("ok"))
    raten = a.group_by("datensatz", "gremium").agg(
        pl.col("ok").mean().alias("rate"), pl.len().alias("n_g")
    )
    a = a.join(raten, on=["datensatz", "gremium"], how="left").sort("id")
    print(
        f"  Anträge mit Sachentscheidung (angenommen oder abgelehnt): {a.height}; angenommen {p1(a.get_column('ok').sum(), a.height)}"
    )
    for ds in ("2014-2020", "2020-2025", "2025-"):
        d = a.filter(pl.col("datensatz") == ds)
        if not d.height:
            continue
        mehrheit = M15.MEHRHEIT.get(ds, frozenset())
        einheit = M15.FRAKTION_EINHEIT.get(ds, {})
        mehr = {einheit.get(x, x) for x in mehrheit}
        print(
            f"\n  {ds}: n {d.height}, angenommen {p1(d.get_column('ok').sum(), d.height)}; Mehrheit im Rat (15): {sorted(mehr)}"
        )
        e = d.explode("fraktionen").with_columns(
            pl.col("fraktionen").fill_null(pl.col("urheber_art")).alias("wer")
        )
        t = (
            e.group_by("wer")
            .agg(
                pl.len().alias("n"),
                pl.col("ok").sum().alias("beob"),
                pl.col("rate").sum().alias("erw"),
            )
            .sort("n", descending=True)
        )
        print(f"    {'Urheber':14s} {'n':>5s} {'roh':>7s} {'beob/erw':>9s}")
        for r in t.iter_rows(named=True):
            if r["n"] >= 30:
                lager = "M" if r["wer"] in mehr else ""
                print(
                    f"    {str(r['wer']):14s} {r['n']:5d} {100 * r['beob'] / r['n']:6.1f} % {r['beob'] / r['erw']:9.2f} {lager}"
                )
        for ga in ("rat", "ausschuss", "bezirksvertretung"):
            x = e.filter(pl.col("gremium_art") == ga)
            if not x.height:
                continue
            m = x.filter(pl.col("wer").is_in(list(mehr)))
            o = x.filter(~pl.col("wer").is_in(list(mehr)) & (pl.col("urheber_art") == "Fraktion"))
            print(
                f"    {ga:17s} Mehrheitsfraktionen {p1(m.get_column('ok').sum(), m.height)} (n {m.height}), "
                f"übrige Fraktionen {p1(o.get_column('ok').sum(), o.height)} (n {o.height})"
            )


# ================================================================================================
# Stichprobe und Kodieraufträge (F4-Format)
# ================================================================================================
def ziehe(df: pl.DataFrame) -> pl.DataFrame:
    """150 Anträge, je Schicht die kleinsten Ränge (SHA-256 aus Seed und ID, wie F4)."""
    a = df.filter((pl.col("rolle") == "antrag") & (pl.col("stadt") == "dus")).with_columns(
        pl.struct("klasse", "pruefauftrag")
        .map_elements(lambda s: schicht(s["klasse"], s["pruefauftrag"]), return_dtype=pl.String)
        .alias("schicht")
    )
    groessen = dict(a.group_by("schicht").len().iter_rows())
    quote = dict(AUFTEILUNG)
    rest = 0
    for s, q in AUFTEILUNG.items():
        if groessen.get(s, 0) < q:
            rest += q - groessen.get(s, 0)
            quote[s] = groessen.get(s, 0)
    quote["beschlossen"] += rest
    rows = []
    for s, q in quote.items():
        ids = a.filter(pl.col("schicht") == s).get_column("id").to_list()
        for i in sorted(ids, key=lambda x: rank(SEED, x))[:q]:
            rows.append({"id": i, "schicht": s, "schicht_n": groessen.get(s, 0)})
    return pl.DataFrame(rows).sort("id")


def beratungsfolge(p: Profil, paper: str) -> list[dict[str, Any]]:
    """Die Beratungsfolge, wie die Kodierer sie sehen: je Tagesordnungspunkt eine Zeile."""
    out: list[dict[str, Any]] = []
    seen = set()
    for s in p.folge.get(paper, []):
        seen.add(s.beratung)
        out.append(
            {
                "gremium": s.gremium,
                "rolle": s.rolle or None,
                "sitzung": s.sitzung.date().isoformat() if s.sitzung else None,
                "top": s.nummer or None,
                "bezeichnung": s.bezeichnung,
                "ergebnis": s.result,
            }
        )
    for c in sorted(p.beratungen.get(paper, []), key=lambda c: c.id):
        if c.id in seen:
            continue
        g = "+".join(org_name(o, p.gremien) for o in c.organization) or "?"
        m = p.meetings.get(c.meeting or "")
        out.append(
            {
                "gremium": g,
                "rolle": c.role or None,
                "sitzung": m.start.date().isoformat() if m and m.start else None,
                "top": None,
                "bezeichnung": None,
                "ergebnis": None,
                "hinweis": "Beratung ohne Tagesordnungspunkt im Datensatz",
            }
        )
    return out


def rohtexte(profile: Sequence[Profil], namen: dict[str, set[str]]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for p in profile:
        f = ROHTEXT / f"{p.layout.root.name}.parquet"
        want = namen.get(p.slug, set())
        if not want or not f.is_file():
            continue
        r = pl.read_parquet(f, columns=["name", "text"]).filter(pl.col("name").is_in(list(want)))
        for name, text in r.iter_rows():
            out[(p.slug, name)] = text or ""
    return out


def schreibe_stichprobe(df: pl.DataFrame, profile: Sequence[Profil], force: bool) -> None:
    sample = ziehe(df)
    VALIDIERUNG.mkdir(parents=True, exist_ok=True)
    EIGENE.mkdir(parents=True, exist_ok=True)
    pop = EIGENE / "grundgesamtheit.parquet"
    df.filter((pl.col("rolle") == "antrag") & (pl.col("stadt") == "dus")).select(
        "id",
        "profil",
        "datensatz",
        "klasse",
        "pruefauftrag",
        "result",
        "entscheidung_gremium",
        "entscheidung_datum",
    ).write_parquet(pop)
    sample.write_csv(STICHPROBE)
    groessen = dict(sample.select("schicht", "schicht_n").unique().iter_rows())
    gezogen = Counter(sample.get_column("schicht").to_list())
    meta = {
        "vorhaben": PROJEKT,
        "codebuch_version": load_codebook(VALIDIERUNG / "codebuch.toml", PROJEKT).version,
        "profil": "duesseldorf",
        "profile": [p.slug for p in profile if p.stadt == "dus"],
        "einheit": "document",
        "grundgesamtheit": f"{pop} (Anträge der drei Düsseldorfer Perioden, Klasse der Regel)",
        "grundgesamtheit_sha256": sha256(pop),
        "einheiten": int(sum(groessen.values())),
        "ohne_text": 0,
        "groesse": sample.height,
        "seed": SEED,
        "schicht": "schicht",
        "aufteilung": "fest (Messdokument § 3.1)",
        "selbstgewichtend": False,
        "schichten": {
            s: {"grundgesamtheit": int(groessen[s]), "stichprobe": int(gezogen[s])}
            for s in sorted(groessen)
        },
        "gezogen": dt.date.today().isoformat(),
    }
    STICHPROBE_META.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Aufträge
    paths = ValidationPaths(PROJEKT, VALIDIERUNG, KODIERUNG)
    codebook = load_codebook(paths.codebook, PROJEKT)
    shown = questions(codebook)
    by_id = {r["id"]: r for r in df.iter_rows(named=True)}
    prof = {p.slug: p for p in profile}
    namen: dict[str, set[str]] = defaultdict(set)
    for i in sample.get_column("id").to_list():
        namen[by_id[i]["profil"]].add(by_id[i]["file_name"])
    texte = rohtexte(profile, namen)
    korpus = {}
    for p in profile:
        for i, t in p.docs.select("id", "text").iter_rows():
            if i in by_id and by_id[i]["rolle"] == "antrag":
                korpus[i] = t or ""
    tasks = []
    klein = 0
    for i in sample.get_column("id").to_list():
        r = by_id[i]
        text = texts_or(texte.get((r["profil"], r["file_name"])), korpus.get(i, ""))
        if (r["profil"], r["file_name"]) not in texte:
            klein += 1
        tasks.append(
            {
                "id": i,
                "vorhaben": PROJEKT,
                "codebuch_version": codebook.version,
                "dokumente": [
                    {
                        "id": i,
                        "titel": r["name"],
                        "drucksache": r["reference"],
                        "datum": r["date"].isoformat() if r["date"] else None,
                        "dokumentart": r["paper_type"],
                        "textquelle": "roh" if (r["profil"], r["file_name"]) in texte else "klein",
                        "ausschnitt": text[:TEXTANFANG],
                    }
                ],
                "beratungsfolge": beratungsfolge(prof[r["profil"]], i),
                "fragen": shown,
                "antwort": None,
            }
        )
    for coder in ("A", "B"):
        ordered = sorted(tasks, key=lambda t: rank(SEED, f"{coder}|{t['id']}"))
        write_assignment(paths, coder, ordered, codebook, force=force)
    print(
        f"\nStichprobe: {sample.height} Anträge -> {STICHPROBE}; Schichten {dict(sorted(gezogen.items()))}"
    )
    print(
        f"Aufträge: {len(tasks)} je Kodierer -> {KODIERUNG}/A, /B ({klein} aus dem kleingeschriebenen Korpus)"
    )


def texts_or(roh: str | None, klein: str) -> str:
    return roh if roh else klein


def pruefe_stichprobe(df: pl.DataFrame) -> None:
    if not STICHPROBE.is_file():
        print("\n(keine gespeicherte Stichprobe; --stichprobe zieht sie)")
        return
    neu = ziehe(df)
    alt = pl.read_csv(STICHPROBE, schema_overrides={"schicht_n": pl.Int64})
    gleich = alt.sort("id").equals(neu.sort("id"))
    print(
        f"\nGespeicherte Stichprobe {'unverändert' if gleich else 'WEICHT AB'} ({alt.height} Anträge)"
    )


# ================================================================================================
# Auswertung gegen die Labels (nach der Schlichtung)
# ================================================================================================
def lies_labels() -> dict[str, dict[str, str | None]]:
    out: dict[str, dict[str, str | None]] = defaultdict(dict)
    with LABELS.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["id"]][row["frage"]] = row["label"] or None
    return out


def geschichtet(rows: Iterable[tuple[str, int, bool]]) -> tuple[float, float, float, float]:
    """Σ W_h·x_h/m_h mit Wilson bei Kishs n_eff (wie F4, docs/validierung.md § 5)."""
    by: dict[str, list[bool]] = defaultdict(list)
    size: dict[str, int] = {}
    for s, n, ok in rows:
        by[s].append(ok)
        size[s] = n
    total = sum(size.values())
    est = sum(size[h] / total * sum(v) / len(v) for h, v in by.items())
    w = [size[h] / len(v) for h, v in by.items() for _ in v]
    n_eff = sum(w) ** 2 / sum(x * x for x in w)
    lo, hi = wilson(est * n_eff, n_eff)
    return est, lo, hi, n_eff


def auswertung(df: pl.DataFrame) -> None:
    titel("§ 4.1 Auswertung gegen die Labels (Stufen der Vorab-Festlegung)")
    if not LABELS.is_file():
        print(
            "  labels.csv fehlt; erst kodieren, schlichten, `georep validate merge 26-beschluesse`"
        )
        return
    labels = lies_labels()
    sample = pl.read_csv(STICHPROBE, schema_overrides={"schicht_n": pl.Int64})
    regel = {r["id"]: r for r in df.iter_rows(named=True)}
    stufen = {
        "voll": lambda k, a, lk, la: k == lk and (k not in ANGENOMMEN or a == la),
        "rueckfall_1": lambda k, a, lk, la: k == lk,
        "rueckfall_2": lambda k, a, lk, la: GROB.get(k) == GROB.get(lk or ""),
    }
    unklar = 0
    werte: dict[str, list[tuple[str, int, bool]]] = defaultdict(list)
    je_klasse: dict[str, Counter[str]] = defaultdict(Counter)
    fehler: list[str] = []
    for r in sample.iter_rows(named=True):
        lab = labels.get(r["id"], {})
        lk, la = lab.get("ergebnis"), lab.get("auftrag")
        k = regel[r["id"]]["klasse"]
        a = "pruefauftrag" if regel[r["id"]]["pruefauftrag"] else "sachbeschluss"
        if lk in (None, "unklar") or (
            lk in ANGENOMMEN and k in ANGENOMMEN and la in (None, "unklar")
        ):
            unklar += 1
            continue
        for name, f in stufen.items():
            werte[name].append((r["schicht"], r["schicht_n"], bool(f(k, a, lk, la))))
        ok = stufen["voll"](k, a, lk, la)
        je_klasse[r["schicht"]]["n"] += 1
        je_klasse[r["schicht"]]["ok"] += ok
        if not ok:
            fehler.append(f"{regel[r['id']]['reference']}: Regel {k}/{a}, Label {lk}/{la}")
    print(f"  gewertet {len(werte['voll'])}, unklar {unklar} (Grenze 15)")
    urteil = None
    for name in ("voll", "rueckfall_1", "rueckfall_2"):
        v = werte[name]
        k = sum(ok for _, _, ok in v)
        lo, hi = wilson(k, len(v))
        est, glo, ghi, neff = geschichtet(v)
        erfuellt = k / len(v) >= 0.95 and est >= 0.95
        print(
            f"  {name:12s} ungewichtet {k}/{len(v)} = {k / len(v):.3f} (Wilson {lo:.3f}–{hi:.3f}); "
            f"gewichtet {est:.3f} ({glo:.3f}–{ghi:.3f}, n_eff {neff:.1f}) -> {'erfüllt' if erfuellt else 'verfehlt'}"
        )
        if erfuellt and urteil is None:
            urteil = name
    print(f"  Urteil nach der Vorab-Festlegung: {urteil or 'umbauen oder verwerfen'}")
    print(
        "  je Schicht (volle Klasse): "
        + "; ".join(f"{s} {c['ok']}/{c['n']}" for s, c in sorted(je_klasse.items()))
    )
    for s, c in sorted(je_klasse.items()):
        if c["n"] >= 10 and c["ok"] / c["n"] < 0.8:
            print(f"  Schicht {s}: {c['ok']}/{c['n']} unter 0,80 -> nur in ihrer groben Klasse")
    print("  Fehler: " + "; ".join(fehler))


# ================================================================================================
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stichprobe", action="store_true")
    ap.add_argument("--force", action="store_true", help="begonnene Antworten überschreiben")
    ap.add_argument("--auswertung", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    profile = [lade(*x) for x in PROFILE]
    print(f"geladen in {time.time() - t0:.1f} s")
    for p in profile:
        print(
            f"  {p.datensatz:12s} {p.slug:18s} {p.docs.height:6d} Dokumente, "
            + (
                f"{len(p.meetings)} Sitzungen, {len(p.items)} Punkte, {len(p.cons)} Beratungen, "
                f"{len(p.beratungen)} Dokumente mit Beratung"
                if p.abgerufen
                else "Netzlauf fehlt"
            )
        )
    df = pl.concat([zeilen(p) for p in profile], how="diagonal_relaxed").sort("id")
    print(f"klassifiziert in {time.time() - t0:.1f} s")
    server_fuellt(profile)
    for p in profile:
        if p.abgerufen:
            je_gremium_result(p)
    weg_zum_ergebnis(df)
    klassen_je_periode(df)
    abdeckung_je(df)
    dauer(df)
    kanten = lade_kanten()
    pruefauftraege(df, kanten)
    gegenproben(df, profile, kanten)
    nachtraege(df, profile, kanten)
    anfragen(df)
    erfolg(df)
    if args.stichprobe:
        schreibe_stichprobe(df, profile, args.force)
    else:
        pruefe_stichprobe(df)
    if args.auswertung:
        auswertung(df)
    print(f"\nLaufzeit {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
