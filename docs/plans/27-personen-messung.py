"""Rechnet die Zahlen von `27-personen.md` nach (Vorhaben 27 „Personen und Mandatstyp").

    uv run python docs/plans/27-personen-messung.py [--stichprobe] [--sim N] [--labels]

Liest, was `georep run` je Profil schreibt (`interim/papers.parquet`, `processed/papers_gremien.parquet`,
`processed/dokumente_urheber.parquet`, `processed/inverted_index.parquet`,
`processed/combined_searchdict.parquet`, `external/Stimmbezirke_2025.geojson`), die Dateien des
Netzlaufs aus F6 unter `raw/` (`persons.jsonl`, `memberships.jsonl`, über `georep.council`), den Rohtext
als Messdatei (`$GEOREP_MESSDATEN/rohtext/<profil>.parquet`), den Zuschnitt 2020
(`snapshots/2014-2020/external/Kommunalwahlbezirke.geojson`) und die amtliche Wahlergebnispräsentation
der Stadt für die Ratswahlen 2020 und 2025 (`$GEOREP_FREMDDATEN/wahlen/votemanager-duesseldorf/`, README
mit SHA-256; das Skript prüft jede Datei gegen das Ladeprotokoll, bevor es liest).

**Namen bleiben lokal.** Das Skript druckt keine Namen; es schreibt Namen nur nach
`$GEOREP_MESSDATEN/27-personen/` (nie ins Repo). Ins Repo gehen OParl-Kennungen, Wahlbezirksnummern,
Codes und Zählungen.

Was es rechnet (Messdokument § 3):

1. die Kandidaturen je Wahlbezirk 2020 und 2025 (Partei, Stimmen, gewonnen, Vorsprung);
2. die Mandatsträger aus OParl (Rat und Bezirksvertretungen) mit ihren Zeiträumen und Fraktionen;
3. den Mandatstyp je Ratsmitglied (direkt, Liste) und den eigenen Wahlbezirk, mit Abdeckung je Periode;
4. die Zuordnung Dokument → Person (Titel, Absender im Briefkopf, Unterschrift) mit Abdeckung je
   Periode, Gremienart und Dokumentart;
5. die Überlappung der Wahlbezirke 2020 mit denen von 2025 (Näherung der Stufe 1, R7);
6. die Fallzahl der vorab festgelegten Prüfung (§ 8) und ihre Teststärke durch Simulation (`--sim`),
   **ohne** das Maß *Y* zu bilden: die Simulation zieht *Y* künstlich aus der Basisrate.

Mit `--stichprobe` schreibt es die Grundgesamtheit der Validierung nach
`<data_root>/duesseldorf/messung/27-personen-grundgesamtheit.parquet` (nur `id` und `schicht`); die
Stichprobe zieht danach `georep validate sample 27-personen`. Die Vorhersage des Verfahrens (Nachnamen)
liegt lokal unter `$GEOREP_MESSDATEN/27-personen/vorhersage.parquet`, nie im Auftrag.

Mit `--labels` misst es die Präzision des Verfahrens gegen `validierung/27-personen/labels.csv`.

Die Hypothese H1 wird **nicht** gerechnet (§ 8). Laufzeit ohne `--sim` rund eine Minute.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "4")

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from shapely.geometry import shape  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from georep.council import JsonlStore, council_files  # noqa: E402
from georep.layout import Layout  # noqa: E402
from georep.oparl import OparlMeeting, OparlMembership, OparlPerson  # noqa: E402
from georep.settings import load_settings  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
FREMDDATEN = Path(os.environ.get("GEOREP_FREMDDATEN", "/media/konrad/xtraspace/georep/fremddaten"))
WAHLEN = FREMDDATEN / "wahlen" / "votemanager-duesseldorf"
LOKAL = MESSDATEN / "27-personen"
VALIDIERUNG = REPO / "validierung" / "27-personen"
SEED = 20261124

# Die Wahlen, die eine Periode eröffnen: Profil, votemanager-ID der Ratswahl, Beginn und Ende der
# Ratsperiode (konstituierende Sitzung bis Ende der Wahlzeit, § 42 GO NRW: 1. November nach der Wahl).
# Dokumente vor dem Beginn stammen noch vom alten Rat und zählen nicht.
WAHLEN_JE_PERIODE = {
    "duesseldorf": (2020, 61, date(2020, 11, 1), date(2025, 10, 31)),
    "duesseldorf-2025": (2025, 89, date(2025, 11, 1), date(2030, 10, 31)),
}
# Rat und Bezirksvertretungen im Body 0015 (Profil [bodies.organizations]: gr/6 = RAT, gr/32 bis
# gr/41 = BV1 bis BV10).
RAT = "/gr/6"
BV = {f"/gr/{32 + i}": i + 1 for i in range(10)}
ROLLE_RAT = re.compile(r"(?<!beratendes )Ratsmitglied")
ROLLE_BV = re.compile(r"Bezirksvertretungsmitglied|BV-Mitglied|Bezirksbürgermeister")


# --- 0. Hilfen ------------------------------------------------------------------------------------


def norm(s: str) -> str:
    """Kleinschreibung, ß als ss, Akzente weg, nur Buchstaben (für Namensvergleiche)."""
    s = s.lower().replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s)


TITEL = re.compile(r"\b(?:Dr|Prof|Dipl|med|rer|nat|phil|jur|Ing)\.?(?:-[A-Za-z]+\.?)?\s*", re.I)


def ohne_titel(s: str) -> str:
    return TITEL.sub("", s).strip()


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def pct(k: int, n: int) -> str:
    if n == 0:
        return "–"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.3f} ({lo:.3f}–{hi:.3f})"


def pruefe_fremddaten() -> None:
    """Größe und SHA-256 jeder geladenen Datei gegen das Ladeprotokoll, bevor etwas gelesen wird."""
    zeilen = (WAHLEN / ".ladeprotokoll.tsv").read_text(encoding="utf-8").splitlines()
    for z in zeilen:
        _, rel, groesse, sha, _ = z.split("\t")
        f = WAHLEN / rel
        daten = f.read_bytes()
        if len(daten) != int(groesse) or hashlib.sha256(daten).hexdigest() != sha:
            sys.exit(f"Fremddatei verändert: {rel}")
    print(
        f"Fremddaten geprüft: {len(zeilen)} Dateien unter {WAHLEN.name}/, Größe und SHA-256 stimmen"
    )


def pfade(profil: str) -> dict[str, str]:
    out = subprocess.run(
        ["uv", "run", "georep", "--profile", profil, "paths"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO,
    ).stdout
    return dict(z.split("=", 1) for z in out.splitlines() if "=" in z)


def art(paper_type: str | None, name: str | None) -> str:
    """Rolle einer Drucksache, wörtlich aus `14-vorgaenge-messung.py` (nur Anfrage und Antrag)."""
    t = (paper_type or "").strip()
    n = (name or "").lower()
    low = t.lower()
    if low.startswith(("anfrage", "zanfrage")):
        return "anfrage"
    if low.startswith(("antrag", "zantrag", "haushaltsantrag")) or "fraktionsantrag" in low:
        return "antrag"
    if "mitgliederantrag" in low:
        return "antrag"
    if t == "Vorlage aus der Politik":
        if "anfrage" in n and "antrag" not in n:
            return "anfrage"
        if "antrag" in n:
            return "antrag"
        return "politik"
    return "sonst"


# --- 1. Kandidaturen ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Kandidatur:
    jahr: int
    wahlbezirk: int
    partei: str
    vorname: str  # erstes Wort des Vornamens, normiert
    nachname: str  # normiert
    stimmen: int
    anteil: float
    gewonnen: bool
    vorsprung: float  # Punkte vor dem Zweiten (Gewinner) oder Rückstand auf den Ersten (negativ)


def kandidaturen(jahr: int, wahl: int) -> list[Kandidatur]:
    """Je Wahlbezirk alle Bewerberinnen mit Stimmen; der Gewinner aus `gewaehlte_kandidaten`."""
    out: list[Kandidatur] = []
    ordner = WAHLEN / f"kw_{jahr}" / "api" / f"wahl_{wahl}"
    for f in sorted(ordner.glob("ergebnis_ebene_5_id_*_0.json")):
        e = json.loads(f.read_text(encoding="utf-8"))
        # 2025: "… - KWB 1 - Name", 2020: "… - 001 Name"
        m = re.match(r"(?:KWB\s*)?0*(\d+)\b", e["seitentitel"].split(" - ", 2)[-1])
        if m is None:
            sys.exit(f"{f.name}: kein Wahlbezirk im Titel")
        wb = int(m.group(1))
        gewaehlt = [i["label"] for i in e["Komponente"]["gewaehlte_kandidaten"]["items"]]
        if len(gewaehlt) != 1:
            sys.exit(f"{f.name}: {len(gewaehlt)} Gewählte statt einer")
        zeilen = []
        for z in e["Komponente"]["tabelle"]["zeilen"]:
            name, partei = z["label"]["labelKurz"].rsplit(",", 1)
            stimmen = int(z["zahl"].replace(".", ""))
            anteil = float(z["prozent"].replace("%", "").replace(",", ".").strip())
            zeilen.append((name.strip(), partei.strip(), stimmen, anteil))
        zeilen.sort(key=lambda r: -r[2])
        erster, zweiter = zeilen[0][3], zeilen[1][3]
        for name, partei, stimmen, anteil in zeilen:
            worte = ohne_titel(name).split()
            gew = gewaehlt[0].startswith(name + " (")
            out.append(
                Kandidatur(
                    jahr=jahr,
                    wahlbezirk=wb,
                    partei=partei,
                    vorname=norm(worte[0]),
                    nachname=norm(" ".join(worte[1:])),
                    stimmen=stimmen,
                    anteil=anteil,
                    gewonnen=gew,
                    vorsprung=(anteil - zweiter) if gew else (anteil - erster),
                )
            )
    gewinner = [k for k in out if k.gewonnen]
    if len(gewinner) != len({k.wahlbezirk for k in out}):
        sys.exit(f"{jahr}: Gewinner und Wahlbezirke passen nicht zusammen")
    return out


def sitze(jahr: int, wahl: int) -> dict[str, int]:
    e = json.loads(
        (WAHLEN / f"kw_{jahr}" / "api" / f"wahl_{wahl}" / "ergebnis_ebene_3_id_1_0.json").read_text(
            encoding="utf-8"
        )
    )
    return {x["label"]: x["sitze"] for x in e["Komponente"]["sitze"]["tortenDiagramm"]["entries"]}


# --- 2. Mandatsträger aus OParl -------------------------------------------------------------------


@dataclass
class Mandat:
    person: str
    vorname: str
    nachname: str
    nachname_roh: str
    rat: list[tuple[date, date]] = field(default_factory=list)
    bv: dict[int, list[tuple[date, date]]] = field(default_factory=dict)
    fraktion: list[tuple[date, date, str]] = field(default_factory=list)

    def im_rat(self, t: date) -> bool:
        return any(s <= t <= e for s, e in self.rat)

    def im_rat_zwischen(self, a: date, b: date) -> bool:
        return any(s <= b and e >= a for s, e in self.rat)

    def in_bv(self, nr: int, t: date) -> bool:
        return any(s <= t <= e for s, e in self.bv.get(nr, []))

    def fraktion_am(self, t: date) -> str | None:
        for s, e, org in self.fraktion:
            if s <= t <= e:
                return org
        return None


STAB = re.compile(r"Mitarbeiter|Geschäftsführ|Informationssystem|Personalrat|Verwaltung")


def fraktionen(settings: object) -> tuple[dict[str, str], list[tuple[re.Pattern[str], str]]]:
    """Fraktion je OParl-Organisation und je Parteiname, aus [originators] des Profils (Volt sitzt
    in der Fraktion SPD/Volt, die Klimaliste in der Fraktion mit der PARTEI)."""
    orgs: dict[str, str] = {}
    muster: list[tuple[re.Pattern[str], str]] = []
    o = settings.originators  # type: ignore[attr-defined]
    for p in list(o.parties) + list(o.groups):
        ziel = "SPD" if p.key == "VOLT" else p.key
        for org in p.organizations:
            orgs["/" + org.split("/organizations/", 1)[-1]] = ziel
        muster += [(re.compile(m), ziel) for m in p.patterns]
    muster.append((re.compile("klimaliste"), "PARTEI"))
    return orgs, muster


def mandatstraeger(layout: Layout, settings: object) -> dict[str, Mandat]:
    files = council_files(layout)
    personen = JsonlStore(files.persons, OparlPerson).load()
    mitglied = JsonlStore(files.memberships, OparlMembership).load()
    fr_org, _ = fraktionen(settings)
    out: dict[str, Mandat] = {}
    fr_roh: list[OparlMembership] = []
    for m in mitglied.values():
        if not m.person or not m.organization or m.person not in personen:
            continue
        rolle = m.role or ""
        org = "/" + m.organization.split("/organizations/", 1)[-1]
        zeit = (m.start_date or date(1900, 1, 1), m.end_date or date(2100, 1, 1))
        if org in fr_org and not STAB.search(rolle):
            fr_roh.append(m)
        ist_rat = (org == RAT and rolle == "Mitglied") or bool(ROLLE_RAT.search(rolle))
        ist_bv = (org in BV and rolle == "Mitglied") or bool(ROLLE_BV.search(rolle))
        if not (ist_rat or ist_bv):
            continue
        p = personen[m.person]
        md = out.get(m.person)
        if md is None:
            vor = ohne_titel(p.given_name or "").split()
            md = out[m.person] = Mandat(
                person=m.person,
                vorname=norm(vor[0]) if vor else "",
                nachname=norm(p.family_name or ""),
                nachname_roh=(p.family_name or "").strip(),
            )
        if ist_rat:
            md.rat.append(zeit)
        if ist_bv:
            nr = BV.get(org)
            if nr is not None:
                md.bv.setdefault(nr, []).append(zeit)
            else:  # Rolle in einer BV-Fraktion: die Nummer der BV steht nicht an der Organisation
                md.bv.setdefault(0, []).append(zeit)
    for m in fr_roh:
        if m.person in out and m.organization:
            org = "/" + m.organization.split("/organizations/", 1)[-1]
            s0 = m.start_date or date(1900, 1, 1)
            e0 = m.end_date or date(2100, 1, 1)
            out[m.person].fraktion.append((s0, e0, fr_org[org]))
    for md in out.values():  # die jüngste Mitgliedschaft zuerst: sie gilt bei Überlappung
        md.fraktion.sort(key=lambda x: x[0], reverse=True)
    return out


def ratsteilnehmer(layout: Layout, beginn: date, ende: date) -> set[str]:
    """Personen, die als Teilnehmer einer Ratssitzung der Periode genannt sind."""
    sitzungen = JsonlStore(council_files(layout).meetings, OparlMeeting).load()
    out: set[str] = set()
    for s in sitzungen.values():
        if (
            s.start
            and beginn <= s.start.date() <= ende
            and any(o.endswith(RAT) for o in s.organization)
        ):
            out |= set(s.participant)
    return out


def partei_zu_fraktion(t: Typ | None, muster: list[tuple[re.Pattern[str], str]]) -> str | None:
    """Rückfall, wenn OParl am Datum keine Fraktion nennt: die Partei der Kandidatur."""
    if t is None or t.partei is None:
        return None
    for m, ziel in muster:
        if m.search(t.partei.lower()):
            return ziel
    return "partei:" + t.partei


# --- 3. Mandatstyp je Ratsmitglied ----------------------------------------------------------------


@dataclass(frozen=True)
class Typ:
    person: str
    typ: str  # direkt | liste | unbekannt
    wahlbezirk: int | None  # der gewonnene oder der, in dem die Person kandidiert hat
    partei: str | None  # Partei der Kandidatur
    vorsprung: float | None
    quelle: str  # name | nachname | ohne_kandidatur | mehrdeutig
    nachruecker: bool


def ratsmitglieder(
    mand: dict[str, Mandat], teilnehmer: set[str], beginn: date, ende: date
) -> list[Mandat]:
    """Ratssitz in der Periode: eine Ratsmitgliedschaft überlappt sie, und die Person nahm an einer
    Ratssitzung der Periode teil oder ihre Mitgliedschaft beginnt in ihr. Ohne die Teilnahme zählten
    Mitglieder des alten Rats mit, deren Mitgliedschaft kein Ende trägt (`endDate` zu 7 % gefüllt)."""
    out = []
    for m in mand.values():
        starts = [s for s, e in m.rat if s <= ende and e >= beginn]
        if starts and (m.person in teilnehmer or max(starts) >= beginn - timedelta(days=60)):
            out.append(m)
    return sorted(out, key=lambda x: x.person)


def mandatstypen(
    rat: list[Mandat], kand: list[Kandidatur], beginn: date, ende: date
) -> dict[str, Typ]:
    """Ordnet jedem Ratsmitglied der Periode seine Kandidatur zu (Vor- und Nachname, sonst Nachname
    mit gleichem Anfangsbuchstaben des Vornamens). Ohne Kandidatur: Liste ohne eigenen Wahlbezirk,
    außer ein nicht zugeordneter Gewinner könnte dieselbe Person sein (dann unbekannt)."""
    voll: dict[tuple[str, str], list[Kandidatur]] = defaultdict(list)
    fam: dict[str, list[Kandidatur]] = defaultdict(list)
    for k in kand:
        voll[(k.vorname, k.nachname)].append(k)
        fam[k.nachname].append(k)
    treffer: dict[str, tuple[Kandidatur | None, str]] = {}
    for m in sorted(rat, key=lambda x: x.person):
        v = m.vorname.split("-")[0] if m.vorname else ""
        hits = voll.get((m.vorname, m.nachname), []) or voll.get((v, m.nachname), [])
        if len(hits) == 1:
            treffer[m.person] = (hits[0], "name")
            continue
        if len(hits) > 1:
            treffer[m.person] = (None, "mehrdeutig")
            continue
        f = [k for k in fam.get(m.nachname, []) if k.vorname[:1] == m.vorname[:1]]
        treffer[m.person] = (f[0], "nachname") if len(f) == 1 else (None, "ohne_kandidatur")
    zugeordnet = {(k.wahlbezirk, k.partei) for k, _ in treffer.values() if k is not None}
    offene_gewinner = [k for k in kand if k.gewonnen and (k.wahlbezirk, k.partei) not in zugeordnet]
    out: dict[str, Typ] = {}
    for m in rat:
        k, quelle = treffer[m.person]
        starts = [s for s, e in m.rat if s <= ende and e >= beginn]
        nach = (min(starts) - beginn).days > 60
        if k is not None:
            out[m.person] = Typ(
                m.person,
                "direkt" if k.gewonnen else "liste",
                k.wahlbezirk,
                k.partei,
                k.vorsprung,
                quelle,
                nach,
            )
            continue
        verdacht = any(
            g.nachname[:4] == m.nachname[:4] or g.vorname == m.vorname for g in offene_gewinner
        )
        typ = "unbekannt" if (verdacht or quelle == "mehrdeutig") else "liste"
        out[m.person] = Typ(m.person, typ, None, None, None, quelle, nach)
    return out


# --- 4. Zuordnung Dokument -> Person -------------------------------------------------------------

GRUSS = re.compile(
    r"Mit\s*freundlichen\s*Gr[üu](?:ß|ss)en|Freundliche\s*Gr[üu](?:ß|ss)e|Viele\s*Gr[üu](?:ß|ss)e"
    r"|\bgez\.|\bGez\."
)
GRUSS_ENDE = re.compile(
    r"f\.\s*d\.\s*R|F\.\s*d\.\s*R|für\s*die\s*Richtigkeit|Anlage|Seite\s*\d|Beratungsfolge|Quelle"
)
KOPF_ENDE = re.compile(
    r"\bAn\b|Bezirksbürgermeister|Oberbürgermeister|Vorsitzend|Ausschussvorsitz|\bHerrn\b"
    r"|Betrifft|Betreff|Sehr\s+geehrte"
)
ROLLE_TITEL = re.compile(
    r"\b(?:Ratsherrn?|Ratsfrau|Ratsmitglied(?:s|es)?|Herrn?|Frau|Bezirksvertreter(?:in|s|n)?"
    r"|Bezirksverordnete[nr]?|Stadtverordnete[nr]?)\b\s+((?:\S+\s*){1,4})"
)
WORT = re.compile(r"[A-Za-zÄÖÜäöüß]+")
UNTERSCHRIFT_ZEICHEN = 400
KOPF_ZEICHEN = 400
TOLERANZ_TAGE = 14


def worte(s: str) -> list[str]:
    return [norm(w) for w in WORT.findall(ohne_titel(s))]


def name_in(tok: list[str], vor: str, nach: str) -> bool:
    """Vorname, bis zu zwei weitere Worte, dann der Nachname (auch über mehrere Worte)."""
    for i, w in enumerate(tok):
        if w != vor:
            continue
        for j in range(i + 1, min(i + 4, len(tok))):
            for n in range(1, 4):
                if "".join(tok[j : j + n]) == nach:
                    return True
    return False


def nachname_in(tok: list[str], nach: str) -> bool:
    return any("".join(tok[j : j + n]) == nach for j in range(len(tok)) for n in range(1, 4))


@dataclass(frozen=True)
class Zuordnung:
    personen: tuple[str, ...]
    wege: tuple[str, ...]  # titel, kopf, unterschrift (je Person der erste Weg)
    ende: int  # letzte Textstelle eines Belegs (Titel: 0)
    mehrdeutig: bool


def aktiv(m: Mandat, t: date, bv: int | None) -> bool:
    """Mandatsträger am Datum (mit Toleranz): im Rat, oder in der genannten BV (0 = BV-Fraktion)."""
    tol = timedelta(days=TOLERANZ_TAGE)
    if any(s - tol <= t <= e + tol for s, e in m.rat):
        return True
    for nr, zeiten in m.bv.items():
        if (bv is None or nr in (bv, 0)) and any(s - tol <= t <= e + tol for s, e in zeiten):
            return True
    return False


def zuordnen(
    titel: str, text: str, t: date, stadtbezirk: int | None, kandidaten: list[Mandat]
) -> Zuordnung:
    """Die Regel: Name im Titel hinter einer Rollenbezeichnung, voller Name im Absender des
    Briefkopfs (vor der Anrede an Vorsitz oder Bezirksbürgermeister) oder in der Unterschrift (nach
    dem ersten Gruß, vor „f. d. R.")."""
    aktive = [m for m in kandidaten if aktiv(m, t, None) and m.vorname and m.nachname]
    gefunden: dict[str, tuple[str, int]] = {}
    # Titel: Nachname hinter einer Rollenbezeichnung, im Gremium des Dokuments
    im_gremium = [m for m in aktive if stadtbezirk is None or aktiv(m, t, stadtbezirk)]
    mehrdeutig = False
    for mt in ROLLE_TITEL.finditer(titel):
        tok = worte(mt.group(1))
        hits = [m for m in im_gremium if nachname_in(tok[:3], m.nachname)]
        if len(hits) > 1:
            hits = [m for m in hits if m.vorname.split("-")[0] in tok] or hits
        if len(hits) == 1:
            gefunden.setdefault(hits[0].person, ("titel", 0))
        elif len(hits) > 1:
            mehrdeutig = True
    # Briefkopf: Absender vor der Anrede
    k = KOPF_ENDE.search(text, 0, KOPF_ZEICHEN)
    kopf = text[: k.start() if k else KOPF_ZEICHEN]
    # Unterschrift: nach dem ersten Gruß hinter dem Kopf
    g = GRUSS.search(text, 80)
    sig, sig_start = "", 0
    if g:
        sig = text[g.end() : g.end() + UNTERSCHRIFT_ZEICHEN]
        e = GRUSS_ENDE.search(sig)
        sig = sig[: e.start()] if e else sig
        sig_start = g.end()
    for weg, region, start in (("kopf", kopf, 0), ("unterschrift", sig, sig_start)):
        if not region.strip():
            continue
        tok = worte(region)
        geklebt = region.count(" ") * 15 < len(region)  # pypdf ohne Leerzeichen
        flach = norm(ohne_titel(region))
        hits = []
        for m in aktive:
            v = m.vorname.split("-")[0]
            if name_in(tok, v, m.nachname) or (geklebt and (v + m.nachname) in flach):
                hits.append(m)
        namen = Counter((m.vorname.split("-")[0], m.nachname) for m in hits)
        for m in hits:
            if namen[(m.vorname.split("-")[0], m.nachname)] > 1:
                mehrdeutig = True
                continue
            pos = start + len(region)
            gefunden.setdefault(m.person, (weg, pos))
    personen = tuple(sorted(gefunden))
    return Zuordnung(
        personen=personen,
        wege=tuple(gefunden[p][0] for p in personen),
        ende=max((gefunden[p][1] for p in personen), default=0),
        mehrdeutig=mehrdeutig,
    )


def dokumente(profil: str, p: dict[str, str]) -> pl.DataFrame:
    root = Path(p["root"])
    papers = pl.read_parquet(root / "interim" / "papers.parquet").select(
        "id", "reference", "paper_type", "name", "date", "file_name"
    )
    gremien = pl.read_parquet(root / "processed" / "papers_gremien.parquet").select(
        "id", "gremium", "gremium_art", "stadtbezirk"
    )
    urheber = pl.read_parquet(root / "processed" / "dokumente_urheber.parquet").select(
        "id", "urheber_art"
    )
    roh = pl.read_parquet(MESSDATEN / "rohtext" / f"{p['profile']}.parquet").select(
        pl.col("name").alias("file_name"), pl.col("text").alias("rohtext")
    )
    d = (
        papers.join(gremien, on="id", how="left")
        .join(urheber, on="id", how="left")
        .join(roh, on="file_name", how="left")
        .sort("id")
    )
    return d.with_columns(
        pl.struct("paper_type", "name")
        .map_elements(lambda s: art(s["paper_type"], s["name"]), return_dtype=pl.String)
        .alias("rolle")
    )


def zuordnungen(d: pl.DataFrame, mand: dict[str, Mandat]) -> pl.DataFrame:
    kandidaten = sorted(mand.values(), key=lambda m: m.person)
    zeilen = []
    for r in d.filter(pl.col("urheber_art").is_in(["Fraktion", "Person"])).iter_rows(named=True):
        t = r["date"]
        if t is None:
            continue
        sb = r["stadtbezirk"] if r["gremium_art"] == "bezirksvertretung" else None
        z = zuordnen(r["name"] or "", r["rohtext"] or "", t, sb, kandidaten)
        zeilen.append(
            {
                "id": r["id"],
                "personen": list(z.personen),
                "wege": list(z.wege),
                "ende": z.ende,
                "mehrdeutig": z.mehrdeutig,
                "hat_text": bool(r["rohtext"]),
            }
        )
    return pl.DataFrame(
        zeilen,
        schema={
            "id": pl.String,
            "personen": pl.List(pl.String),
            "wege": pl.List(pl.String),
            "ende": pl.Int64,
            "mehrdeutig": pl.Boolean,
            "hat_text": pl.Boolean,
        },
    )


# --- 5. Wahlbezirke: Treffer je Dokument, Überlappung 2020 -> 2025 --------------------------------


def treffer_je_dokument(p: dict[str, str]) -> dict[str, set[int]]:
    """Die Wahlbezirke (Zuschnitt 2025), die ein Dokument über das Wörterbuch der Kette trifft."""
    root = Path(p["root"]) / "processed"
    idx = pl.read_parquet(root / "inverted_index.parquet")
    wb = pl.read_parquet(root / "combined_searchdict.parquet").explode("suchbegriffe")
    begriff_wb: dict[str, set[int]] = defaultdict(set)
    for b, w in wb.select("suchbegriffe", "wahlkreis_id").iter_rows():
        begriff_wb[b].add(int(w))
    out: dict[str, set[int]] = defaultdict(set)
    for b, ids in idx.select("suchbegriffe", "paper_ids").iter_rows():
        for i in ids:
            out[i] |= begriff_wb.get(b, set())
    return out


def ueberlappung_2020_2025(p: dict[str, str]) -> dict[int, tuple[int, float]]:
    """Je Wahlbezirk 2020 der Wahlbezirk 2025 mit der größten Fläche darin und deren Anteil."""
    alt = json.loads(
        (REPO / "snapshots" / "2014-2020" / "external" / "Kommunalwahlbezirke.geojson").read_text(
            encoding="utf-8"
        )
    )
    neu = json.loads(
        (Path(p["root"]) / "external" / "Stimmbezirke_2025.geojson").read_text(encoding="utf-8")
    )
    for g in (alt, neu):  # beide EPSG:4647, Meter
        if "4647" not in g["crs"]["properties"]["name"]:
            sys.exit("Zuschnitte nicht in EPSG:4647")
    teile: dict[int, list] = defaultdict(list)
    for f in neu["features"]:
        teile[int(f["properties"]["Kommunalwahlbezirk Nr."])].append(shape(f["geometry"]).buffer(0))
    neu_wb = {k: unary_union(v) for k, v in teile.items()}
    out: dict[int, tuple[int, float]] = {}
    for f in alt["features"]:
        a = shape(f["geometry"]).buffer(0)
        anteile = {k: a.intersection(g).area / a.area for k, g in neu_wb.items()}
        best = max(anteile, key=lambda k: anteile[k])
        out[int(f["properties"]["Kommunalwahlbezirk"])] = (best, anteile[best])
    return out


# --- 6. Fallzahl und Teststärke (ohne Y) ----------------------------------------------------------


def logit(x: np.ndarray) -> np.ndarray:
    return np.log(x / (1 - x))


def schaetze(
    y: np.ndarray, d: np.ndarray, z: np.ndarray, fe: np.ndarray, cl: np.ndarray
) -> tuple[float, float] | None:
    """Logistische Regression mit festen Effekten (Dummies), D und Kovariaten z; Standardfehler nach
    Person geclustert (CR1). Gruppen ohne Streuung in y fallen vorher heraus (wie fixest), denn ihr
    fester Effekt liefe gegen unendlich und trägt zu beta nichts bei. Gibt (beta, se) oder None."""
    gruppen = np.unique(fe)
    behalten = np.zeros(len(y), dtype=bool)
    for g in gruppen:
        m = fe == g
        if 0 < y[m].sum() < m.sum():
            behalten |= m
    y, d, z, fe, cl = y[behalten], d[behalten], z[behalten], fe[behalten], cl[behalten]
    if len(y) == 0 or d.min() == d.max():
        return None
    gruppen = np.unique(fe)
    X = np.column_stack([(fe == g).astype(float) for g in gruppen] + [d, z])
    n, k = X.shape
    b = np.zeros(k)
    for _ in range(50):
        eta = np.clip(X @ b, -30, 30)
        mu = 1 / (1 + np.exp(-eta))
        w = np.maximum(mu * (1 - mu), 1e-10)
        H = X.T @ (X * w[:, None])
        try:
            step = np.linalg.solve(H, X.T @ (y - mu))
        except np.linalg.LinAlgError:
            return None
        b += step
        if np.max(np.abs(step)) < 1e-8:
            break
    eta = np.clip(X @ b, -30, 30)
    mu = 1 / (1 + np.exp(-eta))
    w = mu * (1 - mu)
    try:
        Hi = np.linalg.inv(X.T @ (X * w[:, None]))
    except np.linalg.LinAlgError:
        return None
    u = X * (y - mu)[:, None]
    meat = np.zeros((k, k))
    cls = np.unique(cl)
    for c in cls:
        s = u[cl == c].sum(axis=0)
        meat += np.outer(s, s)
    G = len(cls)
    if G < 2:
        return None
    faktor = G / (G - 1) * (n - 1) / max(n - k, 1)
    V = Hi @ meat @ Hi * faktor
    j = len(gruppen)
    return float(b[j]), float(math.sqrt(max(V[j, j], 0.0)))


def teststaerke(
    paare: pl.DataFrame,
    reps: int,
    odds: float,
    a: float = 0.0,
    sd: float = 0.5,
    seed: int = SEED,
    spalte: str = "basisrate",
) -> tuple[float, float, float]:
    """Anteil der Läufe mit p < 0,05 einseitig, bei künstlichem Y aus der Basisrate (§ 8.4); dazu
    der Median der Treffer je Lauf und der Anteil der Läufe mit |beta| > 5 (Trennung)."""
    rng = np.random.default_rng(seed)
    d = paare["direkt"].to_numpy().astype(float)
    lb = logit(paare[spalte].to_numpy())
    kd = paare["k"].to_numpy()
    z = np.column_stack([lb, kd])
    fe = paare["fe"].to_numpy()
    cl = paare["person"].to_numpy()
    personen, inv = np.unique(cl, return_inverse=True)
    beta = math.log(odds)
    treffer = 0
    gueltig = 0
    ereignisse = []
    trennung = 0
    for _ in range(reps):
        u = rng.normal(0, sd, len(personen))[inv]
        pr = 1 / (1 + np.exp(-(lb + a + beta * d + u)))
        y = (rng.random(len(pr)) < pr).astype(float)
        ereignisse.append(y.sum())
        r = schaetze(y, d, z, fe, cl)
        if r is None:
            continue
        gueltig += 1
        b, se = r
        trennung += abs(b) > 5
        if se > 0 and b / se > 1.6448536269514722:
            treffer += 1
    if not gueltig:
        return (math.nan, math.nan, math.nan)
    return (treffer / gueltig, float(np.median(ereignisse)), trennung / gueltig)


# --- 7. Validierung: Grundgesamtheit und Auswertung -----------------------------------------------

SCHICHTEN = ("rat_ausschuss", "bezirksvertretung", "ohne_zuordnung")
AUSSCHNITT = 6000  # text.chars im Codebuch: so weit sehen die Kodierer


def grundgesamtheit(d: pl.DataFrame, z: pl.DataFrame, beginn: date) -> pl.DataFrame:
    """Politische Dokumente der Ratsperiode mit Rohtext; Schicht nach Zuordnung und Gremienart.
    Zugeordnete, deren Beleg hinter dem Ausschnitt liegt, fallen heraus (die Kodierer sähen ihn nicht)."""
    x = d.join(z, on="id", how="inner").filter(
        (pl.col("date") >= beginn)
        & pl.col("hat_text")
        & pl.col("rolle").is_in(["anfrage", "antrag"])
    )
    x = x.with_columns(
        pl.when(pl.col("personen").list.len() == 0)
        .then(pl.lit("ohne_zuordnung"))
        .when(pl.col("gremium_art") == "bezirksvertretung")
        .then(pl.lit("bezirksvertretung"))
        .otherwise(pl.lit("rat_ausschuss"))
        .alias("schicht")
    )
    x = x.filter((pl.col("schicht") == "ohne_zuordnung") | (pl.col("ende") <= AUSSCHNITT))
    return x.select("id", "schicht").sort("id")


def auswerten_labels(
    vorhersage: pl.DataFrame, gg: pl.DataFrame, mand: dict[str, Mandat], d: pl.DataFrame
) -> None:
    """Präzision der Zuordnung gegen die Endlabels (Frage `fragesteller`), je Paar und je Dokument,
    je Schicht und mit den Schichtgewichten der Grundgesamtheit (Kish, wie F4); dazu der Recall
    innerhalb der zugeordneten Dokumente. `labels.csv` trägt Nachnamen und bleibt lokal (siehe
    `validierung/27-personen/.gitignore`); ins Repo geht `labels-kennungen.csv` mit den
    OParl-Kennungen der gelabelten Personen, soweit eindeutig, und Zahlen."""
    datei = VALIDIERUNG / "labels.csv"
    if not datei.exists():
        print("\n(8) Validierung: labels.csv fehlt noch; die Kodierer startet der Supervisor.")
        return
    with datei.open(encoding="utf-8") as f:
        labels = {r["id"]: r["label"] for r in csv.DictReader(f) if r["frage"] == "fragesteller"}
    vh = {r["id"]: (r["personen"], r["nachnamen"]) for r in vorhersage.iter_rows(named=True)}
    schicht = dict(gg.select("id", "schicht").iter_rows())
    datum = dict(d.select("id", "date").iter_rows())
    N = Counter(schicht.values())
    paare: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    recall: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    doks: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    zeilen = []
    for i, lab in sorted(labels.items()):
        gold = {norm(x) for x in (json.loads(lab) if lab else [])}
        s = schicht[i]
        ids, namen = vh.get(i, ([], []))
        pred = {norm(x) for x in namen}
        paare[s][0] += len(pred & gold)
        paare[s][1] += len(pred)
        recall[s][0] += len(pred & gold)
        recall[s][1] += len(gold)
        doks[s][0] += pred <= gold
        doks[s][1] += 1
        kennungen, ohne = [], 0
        for g in sorted(gold):
            hits = [m.person for m in mand.values() if m.nachname == g and aktiv(m, datum[i], None)]
            if len(hits) == 1:
                kennungen.append(hits[0])
            else:
                ohne += 1
        zeilen.append(
            {
                "id": i,
                "schicht": s,
                "verfahren": ";".join(ids),
                "label_kennungen": ";".join(sorted(kennungen)),
                "label_ohne_kennung": ohne,
                "verfahren_bestaetigt": len(pred & gold),
                "verfahren_n": len(pred),
            }
        )
    with (VALIDIERUNG / "labels-kennungen.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(zeilen[0]))
        w.writeheader()
        w.writerows(zeilen)
    print("\n(8) Präzision der Zuordnung gegen die Endlabels")
    for s in SCHICHTEN[:2]:
        print(
            f"  {s}: Paare {pct(*paare[s])}; Dokumente ganz richtig {pct(*doks[s])}; "
            f"Recall der Paare {pct(*recall[s])}"
        )
    for name, tab in (
        ("Präzision der Paare", paare),
        ("Dokumente ganz richtig", doks),
        ("Recall", recall),
    ):
        W = {s: N[s] for s in SCHICHTEN[:2]}
        tot = sum(W.values())
        p_hat = sum(W[s] / tot * tab[s][0] / tab[s][1] for s in W if tab[s][1])
        n_eff = tot**2 / sum(W[s] ** 2 / tab[s][1] for s in W if tab[s][1])
        lo, hi = wilson(round(p_hat * n_eff), round(n_eff))
        print(f"  gewichtet, {name}: {p_hat:.3f} (Wilson bei n_eff {n_eff:.1f}: {lo:.3f}–{hi:.3f})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stichprobe", action="store_true")
    ap.add_argument("--labels", action="store_true")
    ap.add_argument("--sim", type=int, default=0, help="Läufe je Szenario (§ 8.4: 1000)")
    args = ap.parse_args()
    pruefe_fremddaten()
    LOKAL.mkdir(parents=True, exist_ok=True)
    alle_paare = []
    for profil, (jahr, wahl, beginn, ende) in WAHLEN_JE_PERIODE.items():
        p = pfade(profil)
        settings = load_settings(profile=profil)
        layout = Layout.from_settings(settings)
        _, partei_muster = fraktionen(settings)
        print(f"\n===== {profil}: Ratswahl {jahr}, Ratsperiode {beginn} bis {ende}")
        # (1) Kandidaturen
        kand = kandidaturen(jahr, wahl)
        s = sitze(jahr, wahl)
        gew = Counter(k.partei for k in kand if k.gewonnen)
        print(
            f"(1) {len({k.wahlbezirk for k in kand})} Wahlbezirke, {len(kand)} Kandidaturen, "
            f"{sum(s.values())} Sitze"
        )
        for partei in sorted(s, key=lambda x: -s[x]):
            print(f"    {partei}: {s[partei]} Sitze, davon {gew.get(partei, 0)} direkt")
        knapp = sum(1 for k in kand if k.gewonnen and k.vorsprung < 5)
        print(f"    Gewinner mit Vorsprung unter 5 Punkten: {knapp} von {sum(gew.values())}")
        pl.DataFrame([k.__dict__ for k in kand]).write_parquet(
            LOKAL / f"kandidaturen_{jahr}.parquet"
        )
        # (2) Mandatsträger
        mand = mandatstraeger(layout, settings)
        teilnehmer = ratsteilnehmer(layout, beginn, ende)
        ueberlappt = [m for m in mand.values() if m.im_rat_zwischen(beginn, ende)]
        rat = ratsmitglieder(mand, teilnehmer, beginn, ende)
        print(
            f"(2) OParl: {len(mand)} Mandatsträger (Rat oder BV); {len(ueberlappt)} mit einer "
            f"Ratsmitgliedschaft, die die Periode überlappt, davon {len(rat)} mit Ratssitz (Teilnahme "
            f"an einer der Ratssitzungen mit Teilnehmerliste oder Beginn in der Periode); "
            f"{len(teilnehmer)} Teilnehmer"
        )
        # (3) Mandatstyp
        typen = mandatstypen(rat, kand, beginn, ende)
        c = Counter(t.typ for t in typen.values())
        q = Counter(t.quelle for t in typen.values())
        mit_wb = sum(1 for t in typen.values() if t.typ in ("direkt", "liste") and t.wahlbezirk)
        nach = sum(1 for t in typen.values() if t.nachruecker)
        gewinner_oparl = sum(1 for t in typen.values() if t.typ == "direkt")
        nenner = sum(s.values()) + nach
        bekannt = c["direkt"] + c["liste"]
        nenner = max(nenner, len(typen))
        print(f"(3) Mandatstyp der {len(typen)} OParl-Ratsmitglieder: {dict(c)}; Quelle {dict(q)}")
        print(f"    mit eigenem Wahlbezirk: {mit_wb}; Nachrücker (Ratssitz ab Tag 61): {nach}")
        print(
            f"    Gewinner der Wahlbezirke mit OParl-Kennung: {gewinner_oparl} von {len(gew) and sum(gew.values())}"
        )
        print(
            f"    bekannt mit Kennung, je Sitz (Nenner Sitze + Nachrücker {nenner}): {pct(bekannt, nenner)}"
        )
        print(f"    bekannt mit Kennung und Wahlbezirk, je Sitz: {pct(mit_wb, nenner)}")
        print(f"    bekannt unter den OParl-Ratsmitgliedern: {pct(bekannt, len(typen))}")
        pl.DataFrame([t.__dict__ for t in typen.values()]).sort("person").write_parquet(
            LOKAL / f"mandatstyp_{profil}.parquet"
        )
        # (4) Zuordnung Dokument -> Person
        d = dokumente(profil, p)
        z = zuordnungen(d, mand)
        x = d.join(z, on="id", how="inner").filter(pl.col("date") >= beginn)
        x = x.with_columns(pl.col("personen").list.len().alias("n"))
        print(
            f"(4) Politische Dokumente der Ratsperiode: {x.height}, mit Rohtext {x['hat_text'].sum()}"
        )
        for spalte in ("gremium_art", "rolle"):
            for wert, g in sorted(x.group_by(spalte), key=lambda t: str(t[0])):
                print(
                    f"    {spalte} {wert[0]}: mit Person {pct(int((g['n'] > 0).sum()), g.height)}"
                )
        wege = Counter(w for ws in x["wege"].to_list() for w in ws)
        print(
            f"    Wege je Paar: {dict(wege)}; mehrdeutig verworfen bei {int(x['mehrdeutig'].sum())}"
        )
        print(
            f"    Personen je zugeordnetem Dokument: {Counter(x.filter(pl.col('n') > 0)['n'].to_list()).most_common(6)}"
        )
        if profil == "duesseldorf":
            jenseits = x.filter((pl.col("n") > 0) & (pl.col("ende") > AUSSCHNITT)).height
            print(f"    Beleg hinter {AUSSCHNITT} Zeichen: {jenseits}")
        # Anfragen in Rat und Ausschüssen: die Grundgesamtheit von H1
        a = x.filter(
            (pl.col("rolle") == "anfrage") & pl.col("gremium_art").is_in(["rat", "ausschuss"])
        )
        treffer = treffer_je_dokument(p)
        if profil == "duesseldorf":
            ue = ueberlappung_2020_2025(p)
            anteile = sorted(v for _, v in ue.values())
            print(
                f"(5) Wahlbezirke 2020 -> 2025: größte Überlappung Median {anteile[len(anteile) // 2]:.3f}, "
                f"Minimum {anteile[0]:.3f}, unter 0,8 bei {sum(v < 0.8 for v in anteile)} von {len(anteile)}; "
                f"gleiche Nummer bei {sum(1 for k, (b, _) in ue.items() if k == b)}"
            )
            zu_2025 = {k: b for k, (b, _) in ue.items()}
        else:
            zu_2025 = {k: k for k in range(1, 42)}
        paare = []
        for r in a.iter_rows(named=True):
            for pid in r["personen"]:
                m = mand[pid]
                if not m.im_rat(r["date"]) and not any(
                    s - timedelta(days=TOLERANZ_TAGE) <= r["date"] <= e for s, e in m.rat
                ):
                    continue
                t = typen.get(pid)
                paare.append(
                    {
                        "id": r["id"],
                        "person": pid,
                        "typ": t.typ if t else "kein_ratssitz_in_periode",
                        "wb": zu_2025.get(t.wahlbezirk) if t and t.wahlbezirk else None,
                        "fraktion": m.fraktion_am(r["date"])
                        or partei_zu_fraktion(t, partei_muster),
                        "vorsprung": t.vorsprung if t else None,
                    }
                )
        pa = pl.DataFrame(
            paare,
            schema={
                "id": pl.String,
                "person": pl.String,
                "typ": pl.String,
                "wb": pl.Int64,
                "fraktion": pl.String,
                "vorsprung": pl.Float64,
            },
        )
        mit_rat = pa["id"].n_unique() if pa.height else 0
        print(
            f"(6) Anfragen in Rat und Ausschüssen: {a.height}; mit Person {pct(int((a['n'] > 0).sum()), a.height)}; "
            f"mit Ratsmitglied {pct(mit_rat, a.height)}"
        )
        nutzbar = pa.filter(pl.col("typ").is_in(["direkt", "liste"]) & pl.col("wb").is_not_null())
        print(
            f"    Paare {pa.height}, nutzbar (Typ und Wahlbezirk bekannt) {nutzbar.height} "
            f"aus {nutzbar['id'].n_unique()} Anfragen von {nutzbar['person'].n_unique()} Personen; "
            f"Typ der Paare {dict(Counter(pa['typ'].to_list()))}"
        )
        for (fr,), g in sorted(nutzbar.group_by("fraktion"), key=lambda t: -t[1].height):
            cnt = Counter(g["typ"].to_list())
            pers = g.group_by("typ").agg(pl.col("person").n_unique())
            pp = dict(pers.iter_rows())
            print(
                f"    Fraktion {fr.rsplit('/', 1)[-1] if fr else None}: Paare direkt {cnt['direkt']}, Liste {cnt['liste']}; "
                f"Personen direkt {pp.get('direkt', 0)}, Liste {pp.get('liste', 0)}"
            )
        # Basisrate und k je Paar (Zuschnitt 2025), ohne die Anfragen der Person selbst
        pool = a.filter(pl.col("hat_text"))["id"].to_list()
        von = defaultdict(set)
        for r in pa.iter_rows(named=True):
            von[r["person"]].add(r["id"])
        n_pool = len(pool)
        hits_wb = Counter(w for i in pool for w in treffer.get(i, set()))
        # Nicht vorab festgelegt, nur Vorschlag für einen Umbau (§ 5): der Stadtbezirk des eigenen
        # Wahlbezirks statt des Wahlbezirks (gröber, also mehr Treffer)
        sb_tab = pl.read_parquet(Path(p["root"]) / "processed" / "wahlbezirke_stadtbezirke.parquet")
        sb_je_wb = {
            w: sb
            for w, sb, _ in sb_tab.sort("gewicht")
            .select("wahlkreis_id", "stadtbezirk", "gewicht")
            .iter_rows()
        }
        sb_hits = {i: {sb_je_wb[w] for w in treffer.get(i, set()) if w in sb_je_wb} for i in pool}
        hits_sb = Counter(b for i in pool for b in sb_hits[i])
        zeilen = []
        for r in nutzbar.iter_rows(named=True):
            eigene = von[r["person"]]
            n_ohne = n_pool - len(eigene)
            h_ohne = hits_wb[r["wb"]] - sum(1 for i in eigene if r["wb"] in treffer.get(i, set()))
            sb = sb_je_wb.get(r["wb"])
            h_sb = hits_sb[sb] - sum(1 for i in eigene if sb in sb_hits.get(i, set()))
            zeilen.append(
                {
                    "person": r["person"],
                    "direkt": r["typ"] == "direkt",
                    "basisrate": (1 + h_ohne) / (2 + n_ohne),
                    "basisrate_sb": (1 + h_sb) / (2 + n_ohne),
                    "k": math.log(1 + len(treffer.get(r["id"], set()))),
                    "fe": f"{profil}|{r['fraktion']}",
                    "knapp": (r["vorsprung"] or 99) < 5,
                }
            )
        if zeilen:
            alle_paare.append(pl.DataFrame(zeilen))
        mit_ort = sum(1 for i in pool if treffer.get(i))
        print(
            f"    Anfragen mit mindestens einem Ortsbezug (Zuschnitt 2025): {pct(mit_ort, n_pool)}"
        )
        if profil == "duesseldorf":
            gg = grundgesamtheit(d, z, beginn)
            print(f"(7) Grundgesamtheit der Validierung: {dict(Counter(gg['schicht'].to_list()))}")
            vorhersage = (
                z.join(gg, on="id", how="inner")
                .with_columns(
                    pl.col("personen")
                    .map_elements(
                        lambda ps, mand=mand: [mand[q].nachname_roh for q in ps],
                        return_dtype=pl.List(pl.String),
                    )
                    .alias("nachnamen")
                )
                .select("id", "schicht", "personen", "wege", "nachnamen")
            )
            vorhersage.write_parquet(LOKAL / "vorhersage.parquet")
            if args.stichprobe:
                ziel = Path(p["root"]) / "messung"
                ziel.mkdir(parents=True, exist_ok=True)
                gg.write_parquet(ziel / "27-personen-grundgesamtheit.parquet")
                print(f"    geschrieben: {ziel / '27-personen-grundgesamtheit.parquet'}")
            if args.labels:
                auswerten_labels(vorhersage, gg, mand, d)
    paare = pl.concat(alle_paare)
    print(
        f"\n===== Prüfung H1 (beide Perioden): {paare.height} Paare, {paare['person'].n_unique()} Personen, "
        f"direkt {int(paare['direkt'].sum())} Paare; Gruppen Fraktion x Periode {paare['fe'].n_unique()}"
    )
    gemischt = paare.group_by("fe").agg(
        pl.col("direkt").min().alias("a"), pl.col("direkt").max().alias("b")
    )
    gem = set(gemischt.filter(pl.col("a") != pl.col("b"))["fe"].to_list())
    ident = paare.filter(pl.col("fe").is_in(list(gem)))
    print(
        f"    Gruppen mit beiden Mandatstypen: {len(gem)}; Paare darin {ident.height} "
        f"(direkt {int(ident['direkt'].sum())}), Personen {ident['person'].n_unique()}"
    )
    print(
        f"    Basisrate Median {paare['basisrate'].median():.3f} (Stadtbezirk {paare['basisrate_sb'].median():.3f}); "
        f"k Median {paare['k'].median():.3f}; erwartete Treffer unter H0 {paare['basisrate'].sum():.1f}; "
        f"H2: Paare knapp gewählter Direktmandate {int((paare['direkt'] & paare['knapp']).sum())}"
    )
    if args.sim:
        print(f"(6b) Teststärke, {args.sim} Läufe je Szenario, Seed {SEED}:")
        for name, kw in (
            ("OR 1,5, a = 0, Streuung 0,5 (entscheidend)", {"odds": 1.5}),
            ("OR 1,0 (Fehler erster Art)", {"odds": 1.0}),
            ("OR 1,25", {"odds": 1.25}),
            ("OR 2,0", {"odds": 2.0}),
            ("OR 1,5, a = log 2", {"odds": 1.5, "a": math.log(2)}),
            ("OR 1,5, Streuung 1,0", {"odds": 1.5, "sd": 1.0}),
            ("Vorschlag Stadtbezirk, OR 1,0", {"odds": 1.0, "spalte": "basisrate_sb"}),
            ("Vorschlag Stadtbezirk, OR 1,5", {"odds": 1.5, "spalte": "basisrate_sb"}),
        ):
            ts, ev, tr = teststaerke(paare, args.sim, **kw)  # type: ignore[arg-type]
            print(f"    {name}: {ts:.3f} (Treffer je Lauf Median {ev:.0f}, Trennung {tr:.3f})")


if __name__ == "__main__":
    main()
