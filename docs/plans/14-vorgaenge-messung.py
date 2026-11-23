"""Rechnet die Zahlen von `14-vorgaenge.md` nach (Vorhaben 14 „Vorgänge", Stufe 1).

    uv run python docs/plans/14-vorgaenge-messung.py [--stichprobe] [--neu-aus-cache]

Liest nur, was `georep run` je Profil schreibt (`interim/papers.parquet`,
`processed/papers_gremien.parquet`, `processed/dokumente_urheber.parquet`; Pfade aus
`georep --profile <p> paths`), dazu die OParl-Paper-Objekte, die Konrads Netzläufe vom 2026-10-13
und 2026-10-14 im HTTP-Cache hinterlassen haben (`<cache_root>/http.sqlite`, nur lesend geöffnet).
Aus dem Cache kommen drei Angaben, die weder der Korpus noch ein Paket trägt: die **Anlagen** je
Drucksache (`auxiliaryFile`: Name und Datum, darin die „Antwort der Verwaltung"), die **Sitzungen**
der Beratungsfolge (`consultation[].meeting`, `role`) und `subordinatedPaper`. Weil ein Cache
aufgeräumt werden kann, zieht das Skript beim ersten Lauf einen Auszug nach
`$GEOREP_MESSDATEN/14-vorgaenge/oparl_papiere.parquet` (Standard
`/media/konrad/xtraspace/georep/messdaten`) und liest danach nur noch diesen; `--neu-aus-cache`
zieht ihn neu.

Mit `--stichprobe` schreibt es die geschichtete Stichprobe von 150 Kanten nach
`validierung/14-vorgaenge/stichprobe.csv` (nur IDs) und die Kodieraufgaben mit Ausschnitten nach
`$GEOREP_MESSDATEN/kodierung/14-vorgaenge/aufgaben.jsonl` (nie ins Repo); ohne den Schalter prüft
es nur, ob die gespeicherte Stichprobe noch dieselbe ist. Das Codebuch
(`validierung/14-vorgaenge/codebuch.toml`) ist von Hand geschrieben und wird nur gelesen.

Laufzeit rund 1 bis 2 Minuten (Regex über 48 000 Texte, einfädig); Polars auf vier Threads.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sqlite3
import subprocess
import sys
import time
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("POLARS_MAX_THREADS", "4")
import polars as pl  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
AUSZUG = MESSDATEN / "14-vorgaenge" / "oparl_papiere.parquet"
AUFGABEN = MESSDATEN / "kodierung" / "14-vorgaenge" / "aufgaben.jsonl"
STICHPROBE = REPO / "validierung" / "14-vorgaenge" / "stichprobe.csv"
CODEBUCH = REPO / "validierung" / "14-vorgaenge" / "codebuch.toml"
SEED = 14
TEXTANFANG = 1500  # Zeichen je Dokument in einer Kodieraufgabe (Briefing)
FENSTER = 300  # Zeichen links und rechts der Fundstelle

# Profil -> (Stadt, Datensatz). Reihenfolge = Zeit; die drei Düsseldorfer Perioden sind disjunkt
# (2014-05-25 bis 2020-09-12, 2020-09-13 bis 2025-09-14, ab 2025-09-15).
PROFILE = (
    ("duesseldorf-2014", "dus", "2014-2020"),
    ("duesseldorf", "dus", "2020-2025"),
    ("duesseldorf-2025", "dus", "2025-"),
    ("moenchengladbach", "mg", "mg-2020-2025"),
)

# --- Muster der Drucksachennummer je Stadt (Stufe 2: ins Profil) -------------------------------
# Düsseldorf heute: KÜRZEL[NR]/laufende Nummer/Jahr[/Nachtrag], etwa BV6/108/2023, OVA/117/2023/1.
REF_NEU = re.compile(r"^([A-ZÄÖÜ]+)(\d{1,2})?/(\d+)/(\d{4})(?:\s*[/-]+\s*(\d+))?$")
# Düsseldorf bis 2019 (Punkt 57): <Amt>/ <laufende Nummer>/<Jahr>[ - Nachtrag], etwa 61/ 12/2014.
REF_ALT = re.compile(r"^(\d{2,3})/\s*(\d+)/(\d{4})(?:\s*[-/]\s*(\d+))?$")
# Mönchengladbach: laufende Nummer/Wahlperiode römisch, Nachtrag als -k vor oder hinter der Periode.
REF_MG = re.compile(r"^(\d{3,4})(?:-(\d+))?/([IVX]+)(?:[-/](\d+))?$")

# Im kleingeschriebenen Text. Die Buchstabenfolge vor der Nummer wird ganz genommen und danach auf
# das längste bekannte Kürzel am Ende gekürzt: pypdf klebt Wörter zusammen („vorlagebv6/…").
TXT_NEU = re.compile(
    r"(?<![a-zäöüß])([a-zäöüß]+)\s?(\d{0,2})\s?/\s?(\d{1,4})\s?/\s?(\d{4})(?!\d)"
    r"(?:\s?/\s?(\d{1,2})(?![\d.,]))?"
)
TXT_ALT = re.compile(
    r"(?<![\d.,/])(\d{2,3})/(\s{0,2})(\d{1,4})/(\d{4})(?!\d)(?:\s?-\s?(\d{1,2})(?![\d.,]))?"
)
TXT_MG = re.compile(
    r"(?<![\d/.,])(\d{3,4})(?:\s?-\s?(\d{1,2}))?\s?/\s?([ivx]{1,4})(?![a-zäöüß])"
    r"(?:\s?-\s?(\d{1,2})(?![\d.,]))?"
)
BPLAN = re.compile(r"bebauungsplan|b-plan|bplan|plan nr|planes nr|bauleitplan")

# Anlage, die eine Antwort ist (Name der auxiliaryFile, kleingeschrieben).
# „Stellungnahme" allein ist zu breit (IHK, ver.di, Abwägung nach BauGB): nur die der Verwaltung.
ANTWORT_ANLAGE = re.compile(
    r"(^|[^a-zäöü])(be)?antwort|verwaltungsantwort|anrwort|stellungnahme (der |des )?(verwaltung|dezernat|amt)"
)
ZWISCHEN = re.compile(r"zwischen")
# Am 2019-07-03 bekamen alle Anlagen älterer Drucksachen dieses Datum (Umstellung des
# Ratsinformationssystems, 28 451 Anlagen); es ist kein Antwortdatum.
MIGRATION = __import__("datetime").date(2019, 7, 3)


# --- Klassen der Dokumentart (Stufe 2: Tabelle im Profil) --------------------------------------
def art(paper_type: str | None, name: str | None) -> str:
    """Rolle einer Drucksache im Vorgang, aus der Dokumentart (und alt: dem Titel)."""
    t = (paper_type or "").strip()
    n = (name or "").lower()
    low = t.lower()
    if low.startswith(("anfrage", "zanfrage")):
        return "anfrage"
    if low.startswith(("antrag", "zantrag", "haushaltsantrag")) or "fraktionsantrag" in low:
        return "antrag"
    if "mitgliederantrag" in low:
        return "antrag"
    if t == "Vorlage aus der Politik":  # Düsseldorf bis 2019: Antrag und Anfrage in einer Art
        if "anfrage" in n and "antrag" not in n:
            return "anfrage"
        if "antrag" in n:
            return "antrag"
        return "politik"
    if t == "Bedarfsbeschluss":
        return "bedarf"
    if t == "A+F Beschluss":  # Ausführungs- und Finanzierungsbeschluss, keine Antwort
        return "af"
    if "informationsvorlage" in low or "berichtsvorlage" in low:
        return "information"
    if "änderungsvorlage" in low:
        return "vorlage"
    if "beschlussvorlage" in low or "beratungsvorlage" in low or t == "Verwaltungsvorlage":
        return "vorlage"
    if low.startswith("eingabe") or "eingabe nach" in low:
        return "eingabe"
    return "sonst"


# Kantentyp aus (Art der zitierenden, Art der zitierten) Drucksache; die zitierende ist die spätere.
def kantentyp(von: str, nach: str) -> str:
    if nach == "anfrage" and von == "information":
        return "antwort"
    if nach == "anfrage" and von == "anfrage":
        return "nachfrage"
    if nach == "antrag" and von in ("information", "vorlage"):
        return "umsetzung"
    if nach in ("vorlage", "bedarf", "af") and von == "antrag":
        return "aenderung"
    if nach == "bedarf" and von == "af":
        return "bau"
    return "bezug"


# --- Normalform ----------------------------------------------------------------------------------
def key_ref(stadt: str, ref: str | None) -> tuple[str | None, str]:
    """(Schlüssel, Form) einer Drucksachennummer; Schlüssel ohne Nullen und Leerzeichen."""
    if not ref:
        return None, "leer"
    r = ref.strip()
    if stadt == "dus":
        m = REF_NEU.match(r)
        if m:
            code, n, num, year, suf = m.groups()
            return _k(f"{code}{int(n) if n else ''}", num, year, suf), "neu"
        m = REF_ALT.match(r)
        if m:
            head, num, year, suf = m.groups()
            return _k(head, num, year, suf), "alt"
        return None, "fremd"
    m = REF_MG.match(r)
    if m:
        num, suf1, per, suf2 = m.groups()
        suf = suf1 or suf2
        return f"{int(num):04d}/{per}" + (f"/{int(suf)}" if suf else ""), "mg"
    return None, "fremd"


def _k(head: str, num: str, year: str, suf: str | None) -> str:
    return f"{head}/{int(num)}/{year}" + (f"/{int(suf)}" if suf else "")


def basis(key: str) -> str:
    parts = key.split("/")
    return "/".join(parts[:2]) if parts[1].isalpha() or parts[1] in ROMAN else "/".join(parts[:3])


ROMAN = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII"}


def ist_nachtrag(key: str) -> bool:
    return basis(key) != key


@dataclass(frozen=True)
class Treffer:
    key: str
    start: int
    end: int
    form: str  # neu | alt | mg
    geklebt: bool  # Kürzel nur als Ende einer längeren Buchstabenfolge
    datumsfoermig: bool  # alte Form ohne Leerzeichen, wie ein Datum lesbar
    bplan: bool  # Mönchengladbach: Bebauungsplan-Wort kurz davor


def treffer(stadt: str, s: str, codes: frozenset[str]) -> Iterator[Treffer]:
    if stadt == "dus":
        alt = list(TXT_ALT.finditer(s))
        alt_starts = {m.start() for m in alt}
        for m in TXT_NEU.finditer(s):
            run, n, num, year, suf = m.groups()
            run_u = run.upper()
            code = next((run_u[i:] for i in range(len(run_u)) if run_u[i:] in codes), None)
            if code is None:
                # „vorlage 61/ 12/2014", „drucksache 01/ 5/2016": ein Wort vor der alten Form,
                # kein Kürzel; die alte Form unten nimmt den Treffer
                if (n and m.start(2) in alt_starts) or len(run_u) > 6:
                    continue
                code = run_u
            geklebt = code != run_u
            yield Treffer(
                _k(f"{code}{int(n) if n else ''}", num, year, suf),
                m.start() + (len(run_u) - len(code)),
                m.end(),
                "neu",
                geklebt,
                False,
                False,
            )
        for m in alt:
            head, space, num, year, suf = m.groups()
            datum = not space and int(head) <= 31 and len(num) == 2 and 1 <= int(num) <= 12
            yield Treffer(_k(head, num, year, suf), m.start(), m.end(), "alt", False, datum, False)
    else:
        for m in TXT_MG.finditer(s):
            num, suf1, per, suf2 = m.groups()
            suf = suf1 or suf2
            key = f"{int(num):04d}/{per.upper()}" + (f"/{int(suf)}" if suf else "")
            bp = bool(BPLAN.search(s[max(0, m.start() - 50) : m.start()]))
            yield Treffer(key, m.start(), m.end(), "mg", False, False, bp)


# --- Laden ---------------------------------------------------------------------------------------
def paths(profile: str) -> dict[str, str]:
    exe = Path(sys.executable).parent / "georep"
    out = subprocess.run(
        [str(exe), "--profile", profile, "paths"], check=True, capture_output=True, text=True
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def lade_profil(profile: str, stadt: str, datensatz: str) -> tuple[pl.DataFrame, dict[str, str]]:
    p = paths(profile)
    root = Path(p["root"])
    corpus = pl.read_parquet(
        root / "interim" / "papers.parquet",
        columns=["id", "name", "reference", "date", "paper_type", "text"],
    )
    gremien = pl.read_parquet(
        root / "processed" / "papers_gremien.parquet", columns=["id", "gremium", "gremium_art"]
    )
    urheber = pl.read_parquet(
        root / "processed" / "dokumente_urheber.parquet", columns=["id", "urheber_art", "parteien"]
    )
    df = (
        corpus.join(gremien, on="id", how="left")
        .join(urheber, on="id", how="left")
        .with_columns(pl.lit(stadt).alias("stadt"), pl.lit(datensatz).alias("datensatz"))
        .sort("id")
    )
    return df, p


def auszug_aus_cache(sqlite_path: Path, ziel: Path) -> None:
    """OParl-Paper aus dem requests-cache (nur lesend) als Parquet; je ID das jüngste Objekt."""
    from requests_cache.serializers import SERIALIZERS

    ser = SERIALIZERS["pickle"]
    con = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    papers: dict[str, dict[str, Any]] = {}
    for (val,) in con.execute("select value from responses"):
        r = ser.loads(val)
        if "/papers" not in r.url or "ris-oparl" not in r.url:
            continue
        fetched = r.created_at.date()
        for p in json.loads(r.content).get("data", []):
            modified = p.get("modified") or ""
            prev = papers.get(p["id"])
            if prev is not None and prev["modified"] >= modified:
                continue
            aux = p.get("auxiliaryFile") or []
            cons = p.get("consultation") or []
            papers[p["id"]] = {
                "id": p["id"],
                "modified": modified,
                "abgerufen": fetched,
                "anlage_name": [f.get("name") or "" for f in aux],
                "anlage_datum": [f.get("date") or (f.get("created") or "")[:10] for f in aux],
                "sitzungen": [c.get("meeting") or "" for c in cons if c.get("meeting")],
                "rollen": [c.get("role") or "" for c in cons],
                "untergeordnet": [
                    x if isinstance(x, str) else x.get("id", "")
                    for x in p.get("subordinatedPaper") or []
                ],
            }
    con.close()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(list(papers.values()), infer_schema_length=None).sort("id")
    df.write_parquet(ziel)


# --- Hilfen --------------------------------------------------------------------------------------
def pct(a: int, b: int) -> str:
    return f"{a} von {b} ({100 * a / b:.1f} %)" if b else f"{a} von 0"


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


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def komponenten(ids: Iterable[str], kanten: Iterable[tuple[str, str]]) -> dict[str, str]:
    uf = UnionFind()
    for i in ids:
        uf.find(i)
    for a, b in kanten:
        uf.union(a, b)
    return {i: uf.find(i) for i in uf.parent}


def wurzel(x: str, parent: dict[str, str]) -> str:
    """Wurzel eines Vorgangs als Baum; ein Kreis (Verweis in beide Richtungen) bricht ab."""
    seen: set[str] = set()
    while x in parent and x not in seen:
        seen.add(x)
        x = parent[x]
    return x


def groessen(comp: dict[str, str]) -> Counter[int]:
    size = Counter(comp.values())
    return Counter(size.values())


def verteilung(sizes: Counter[int]) -> str:
    bins = ((1, 1), (2, 2), (3, 3), (4, 5), (6, 10), (11, 50), (51, 10**9))
    parts = []
    for lo, hi in bins:
        k = sum(c for s, c in sizes.items() if lo <= s <= hi)
        d = sum(s * c for s, c in sizes.items() if lo <= s <= hi)
        label = f"{lo}" if lo == hi else (f"{lo}–{hi}" if hi < 10**9 else f"> {lo - 1}")
        parts.append(f"{label}: {k} Komp./{d} Dok.")
    return "; ".join(parts)


def tage_stats(s: pl.Series) -> str:
    if s.len() == 0:
        return "n = 0"
    q = s.cast(pl.Float64)
    return (
        f"n = {s.len()}, Median {q.median():.0f}, Q1 {q.quantile(0.25, 'nearest'):.0f}, "
        f"Q3 {q.quantile(0.75, 'nearest'):.0f}, P90 {q.quantile(0.9, 'nearest'):.0f}"
    )


# --- Hauptteil -----------------------------------------------------------------------------------
def main() -> None:  # noqa: C901, PLR0912, PLR0915 -- ein Messskript liest sich am besten von oben nach unten
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--stichprobe", action="store_true", help="Stichprobe und Kodieraufgaben schreiben"
    )
    ap.add_argument(
        "--neu-aus-cache", action="store_true", help="Auszug aus dem HTTP-Cache neu ziehen"
    )
    args = ap.parse_args()
    t0 = time.perf_counter()
    pl.Config.set_tbl_rows(40)
    pl.Config.set_tbl_width_chars(220)
    pl.Config.set_tbl_cols(-1)
    pl.Config.set_fmt_str_lengths(60)

    frames = []
    cache_root = None
    for profile, stadt, datensatz in PROFILE:
        df, p = lade_profil(profile, stadt, datensatz)
        frames.append(df)
        cache_root = Path(p["cache"]).parent
    docs = pl.concat(frames, how="vertical_relaxed")
    assert cache_root is not None
    titel("1 Datenlage")
    print(
        docs.group_by("datensatz", maintain_order=True).agg(
            pl.len().alias("dokumente"),
            (pl.col("text").str.len_chars() > 0).sum().alias("mit_text"),
            pl.col("date").min().alias("von"),
            pl.col("date").max().alias("bis"),
        )
    )
    dup = docs.group_by("id").len().filter(pl.col("len") > 1).height
    print("IDs in mehr als einem Datensatz:", dup)

    if args.neu_aus_cache or not AUSZUG.exists():
        sqlite_path = cache_root / "http.sqlite"
        print(f"Auszug aus {sqlite_path} -> {AUSZUG}")
        auszug_aus_cache(sqlite_path, AUSZUG)
    oparl = pl.read_parquet(AUSZUG)
    docs = docs.join(oparl.drop("modified"), on="id", how="left")
    print(
        "Paper im Cache-Auszug:",
        oparl.height,
        "; davon im Korpus:",
        docs.filter(pl.col("abgerufen").is_not_null()).height,
        "von",
        docs.height,
    )
    print(
        docs.group_by("datensatz", maintain_order=True).agg(
            pl.col("abgerufen").is_not_null().sum().alias("im_cache"),
            pl.col("abgerufen").max().alias("abgerufen"),
            (pl.col("anlage_name").list.len() > 0).sum().alias("mit_anlage"),
            (pl.col("sitzungen").list.len() > 0).sum().alias("mit_sitzung"),
        )
    )

    # Art und Schlüssel je Dokument
    rows = docs.select("id", "stadt", "reference", "paper_type", "name").rows()
    arten, keys, forms = [], [], []
    for _id, stadt, ref, pt, name in rows:
        arten.append(art(pt, name))
        k, f = key_ref(stadt, ref)
        keys.append(k)
        forms.append(f)
    docs = docs.with_columns(
        pl.Series("art", arten), pl.Series("key", keys, dtype=pl.String), pl.Series("form", forms)
    )

    titel("2 Muster der Drucksachennummer je Datensatz (Abdeckung der eigenen Nummern)")
    print(docs.group_by("datensatz", "form", maintain_order=True).len().sort("datensatz", "form"))
    print(
        docs.group_by("datensatz", "art").len().sort("datensatz", "len", descending=[False, True])
    )

    # Bekannte Nummern je Stadt (über alle Perioden)
    known: dict[str, dict[str, list[str]]] = {"dus": defaultdict(list), "mg": defaultdict(list)}
    for _id, stadt, k in docs.select("id", "stadt", "key").rows():
        if k:
            known[stadt][k].append(_id)
    for stadt, d in known.items():
        print(f"{stadt}: {len(d)} Schlüssel, mehrdeutig {sum(1 for v in d.values() if len(v) > 1)}")
    codes = frozenset(m.group(1) for k in known["dus"] if (m := re.match(r"^([A-ZÄÖÜ]+)", k)))
    print("Kürzel Düsseldorf:", len(codes))
    meta = {r[0]: r for r in docs.select("id", "datensatz", "date", "art", "key", "stadt").rows()}

    titel("3 Verweise in Titel, Text und Anlagennamen")
    edges_raw: list[tuple[str, str, str, int, int, str]] = []  # von, nach, feld, start, end, match
    stat: Counter[tuple[str, str, str]] = Counter()
    unknown_years: Counter[tuple[str, str]] = Counter()
    unknown_codes: Counter[str] = Counter()
    flags: Counter[tuple[str, str]] = Counter()
    docs_with: dict[tuple[str, str], set[str]] = defaultdict(set)
    for _id, stadt, ds, own, name, text, anl in docs.select(
        "id", "stadt", "datensatz", "key", "name", "text", "anlage_name"
    ).rows():
        fields = (
            ("titel", (name or "").lower()),
            ("text", text or ""),
            ("anlage", " | ".join(anl or []).lower()),
        )
        for feld, s in fields:
            if not s:
                continue
            seen: set[str] = set()
            for t in treffer(stadt, s, codes):
                stat[(ds, feld, "roh")] += 1
                if t.key in seen:
                    continue
                seen.add(t.key)
                stat[(ds, feld, "eindeutig_je_dok")] += 1
                target = known[stadt].get(t.key)
                how = "bekannt"
                if target is None and ist_nachtrag(t.key):
                    target = known[stadt].get(basis(t.key))
                    how = "basis"
                if target is None:
                    stat[(ds, feld, "unbekannt")] += 1
                    year = t.key.split("/")[2] if stadt == "dus" else t.key.split("/")[1]
                    unknown_years[(ds, year)] += 1
                    if t.form == "neu":
                        unknown_codes[t.key.split("/")[0].rstrip("0123456789")] += 1
                    continue
                if _id in target or t.key == own:
                    stat[(ds, feld, "selbst")] += 1
                    continue
                if len(target) > 1:
                    stat[(ds, feld, "mehrdeutig")] += 1
                    continue
                stat[(ds, feld, how)] += 1
                if t.geklebt:
                    flags[(feld, "geklebt")] += 1
                if t.datumsfoermig:
                    flags[(feld, "datumsfoermig")] += 1
                if t.bplan:
                    flags[(feld, "bplan")] += 1
                flags[(feld, t.form)] += 1
                docs_with[(ds, feld)].add(_id)
                edges_raw.append((_id, target[0], feld, t.start, t.end, s[t.start : t.end]))
    tab = []
    for ds in [d for _, _, d in PROFILE]:
        for feld in ("titel", "text", "anlage"):
            row: dict[str, Any] = {"datensatz": ds, "feld": feld}
            for name, k in (
                ("roh", "roh"),
                ("je_dok", "eindeutig_je_dok"),
                ("selbst", "selbst"),
                ("bekannt", "bekannt"),
                ("ueber_basis", "basis"),
                ("mehrdeutig", "mehrdeutig"),
                ("unbekannt", "unbekannt"),
            ):
                row[name] = stat[(ds, feld, k)]
            row["dok_mit_verweis"] = len(docs_with[(ds, feld)])
            tab.append(row)
    print(pl.DataFrame(tab))
    print("Merkmale bekannter Treffer:", dict(sorted(flags.items())))
    print("Unbekannte Kürzel (neue Form, Top 15):", unknown_codes.most_common(15))
    uy = pl.DataFrame(
        [{"datensatz": d, "jahr": y, "n": n} for (d, y), n in unknown_years.items()]
    ).sort("datensatz", "jahr")
    gruppe_jahr = (
        pl.when(pl.col("jahr").str.contains(r"^[IVX]+$"))
        .then(
            pl.when(pl.col("jahr") == "X")
            .then(pl.lit("Periode X (im Datensatz)"))
            .otherwise(pl.lit("andere Periode"))
        )
        .when(pl.col("jahr").cast(pl.Int32, strict=False) < 2014)
        .then(pl.lit("vor 2014 (vor den Daten)"))
        .when(pl.col("jahr").cast(pl.Int32, strict=False) <= 2026)
        .then(pl.lit("2014 bis 2026 (im Zeitraum)"))
        .otherwise(pl.lit("unplausibel"))
    )
    print("Unbekannte Treffer nach Jahr (Periode) der Nummer:")
    print(
        uy.group_by("datensatz", gruppe_jahr.alias("gruppe"))
        .agg(pl.col("n").sum())
        .pivot(on="gruppe", index="datensatz", values="n")
        .fill_null(0)
        .sort("datensatz")
    )

    # Kanten: je (von, nach) eine, mit den Feldern, in denen der Verweis steht
    e = pl.DataFrame(
        edges_raw, schema=["von", "nach", "feld", "start", "end", "match"], orient="row"
    )
    rang = pl.col("feld").replace_strict({"titel": 0, "text": 1, "anlage": 2}, return_dtype=pl.Int8)
    fund = e.sort("von", "nach", rang, "start").unique(["von", "nach"], keep="first")
    e = e.group_by("von", "nach").agg(pl.col("feld").unique().sort().str.join("+").alias("felder"))
    # Nachträge über die Nummer (X/1 -> X), auch ohne Nennung
    nach_rows = []
    for d in known.values():
        for k, ids in d.items():
            if ist_nachtrag(k) and basis(k) in d and len(ids) == 1 and len(d[basis(k)]) == 1:
                nach_rows.append((ids[0], d[basis(k)][0]))
    n_e = pl.DataFrame(nach_rows, schema=["von", "nach"], orient="row").with_columns(
        pl.lit("nummer").alias("felder")
    )
    e = (
        pl.concat([e, n_e])
        .group_by("von", "nach")
        .agg(pl.col("felder").str.join("+").str.split("+").list.unique().list.sort().list.join("+"))
    )
    # Ausrichten: von ist die zitierende Drucksache; Typ aus den Arten
    m = docs.select("id", "datensatz", "stadt", "date", "art", "key", "gremium", "gremium_art")
    e = (
        e.join(
            m.rename({c: f"von_{c}" for c in m.columns if c != "id"}).rename({"id": "von"}),
            on="von",
        )
        .join(
            m.rename({c: f"nach_{c}" for c in m.columns if c != "id"}).rename({"id": "nach"}),
            on="nach",
        )
        .with_columns(tage=(pl.col("von_date") - pl.col("nach_date")).dt.total_days())
        .with_columns(
            typ=pl.when(pl.col("felder").str.contains("nummer"))
            .then(pl.lit("nachtrag"))
            .otherwise(
                pl.struct("von_art", "nach_art").map_elements(
                    lambda r: kantentyp(r["von_art"], r["nach_art"]), return_dtype=pl.String
                )
            ),
            stadt=pl.col("von_stadt"),
        )
        .sort("von", "nach")
    )
    print("Nachtragskanten über die Nummer:", n_e.height)
    sub = docs.select("id", "untergeordnet").explode("untergeordnet").drop_nulls()
    sub = sub.filter(pl.col("untergeordnet") != "")
    print(
        "OParl subordinatedPaper-Paare:",
        sub.height,
        "; davon auch Nachtrag über die Nummer:",
        sub.join(
            n_e.select(pl.col("nach").alias("id"), pl.col("von").alias("untergeordnet")),
            on=["id", "untergeordnet"],
        ).height,
    )

    titel("4 Kanten: Felder, Richtung, Perioden")
    print("Kanten gesamt:", e.height, dict(e.group_by("stadt").len().rows()))
    print(e.group_by("felder").len().sort("len", descending=True))
    rueck = e.filter(pl.col("tage") < 0).height
    gleich = e.filter(pl.col("tage") == 0).height
    print(f"Richtung: zitierende älter als zitierte {pct(rueck, e.height)}; gleicher Tag {gleich}")
    print("Rückwärts je Feld:", dict(e.filter(pl.col("tage") < 0).group_by("felder").len().rows()))
    print(e.group_by("von_datensatz", "nach_datensatz").len().sort("len", descending=True))

    titel("5 Typisierte Paare (Art der zitierenden -> Art der zitierten)")
    agg = (
        e.group_by("stadt", "typ")
        .agg(
            pl.len().alias("n"),
            (pl.col("tage") < 0).sum().alias("rueckwaerts"),
            pl.col("tage").median().alias("median_tage"),
            (pl.col("von_gremium") == pl.col("nach_gremium"))
            .mean()
            .round(3)
            .alias("gleiches_gremium"),
        )
        .sort("stadt", "n", descending=[False, True])
    )
    print(agg)
    print(e.group_by("von_art", "nach_art").len().sort("len", descending=True).head(20))
    for ziel, typen, label in (
        ("antrag", ("umsetzung",), "Anträge mit Vorlage oder Mitteilung, die sie nennt"),
        ("vorlage", ("aenderung",), "Vorlagen mit Antrag, der sie nennt (Änderung, Ergänzung)"),
        ("anfrage", ("antwort",), "Anfragen mit Informationsvorlage, die sie nennt"),
        ("anfrage", ("nachfrage",), "Anfragen mit späterer Anfrage, die sie nennt"),
        ("bedarf", ("bau",), "Bedarfsbeschlüsse mit A+F-Beschluss, der sie nennt"),
    ):
        hit = set(e.filter(pl.col("typ").is_in(typen) & (pl.col("tage") >= 0))["nach"].to_list())
        for ds in [d for _, _, d in PROFILE]:
            ids_ = docs.filter((pl.col("datensatz") == ds) & (pl.col("art") == ziel))[
                "id"
            ].to_list()
            if ids_:
                print(f"  {label}, {ds}: {pct(sum(1 for i in ids_ if i in hit), len(ids_))}")

    titel("6 Verweisgraph: Komponenten (Vorgänge)")
    typed = ("antwort", "nachfrage", "umsetzung", "aenderung", "nachtrag", "bau")
    for stadt in ("dus", "mg"):
        ids = docs.filter(pl.col("stadt") == stadt)["id"].to_list()
        es = e.filter(pl.col("stadt") == stadt).select("von", "nach").rows()
        comp = komponenten(ids, es)
        sizes = groessen(comp)
        in_vorgang = sum(s * c for s, c in sizes.items() if s > 1)
        print(
            f"{stadt}, alle Kanten: {len(ids)} Dokumente, {len(es)} Kanten, in einer Komponente ≥ 2: "
            f"{pct(in_vorgang, len(ids))}, Komponenten ≥ 2: {sum(c for s, c in sizes.items() if s > 1)}"
        )
        print("  Größen:", verteilung(sizes))
        print("  größte drei:", [n for _, n in Counter(comp.values()).most_common(3)])
        indeg = Counter(b for _, b in es)
        top = indeg.most_common(8)
        print("  meistzitiert:", [(meta[k][4], meta[k][3], v) for k, v in top])
        hubs = [k for k, v in indeg.items() if v > 10]
        es2 = [(a, b) for a, b in es if indeg[b] <= 10]
        comp2 = komponenten(ids, es2)
        print(
            f"  ohne Kanten in {len(hubs)} Knoten mit > 10 Zitaten ({len(es) - len(es2)} Kanten):",
            verteilung(groessen(comp2)),
            "; größte:",
            Counter(comp2.values()).most_common(1)[0][1],
        )
        et = e.filter((pl.col("stadt") == stadt) & pl.col("typ").is_in(typed))
        comp3 = komponenten(ids, et.select("von", "nach").rows())
        sizes3 = groessen(comp3)
        in3 = sum(s * c for s, c in sizes3.items() if s > 1)
        print(
            f"  nur typisierte Kanten ({et.height}): in einem Vorgang {pct(in3, len(ids))}, "
            f"Vorgänge {sum(c for s, c in sizes3.items() if s > 1)};",
            verteilung(sizes3),
            "; größte:",
            [n for _, n in Counter(comp3.values()).most_common(3)],
        )
        tin = et.group_by("nach").len()
        et4 = et.join(tin.filter(pl.col("len") <= 5).select("nach"), on="nach", how="semi")
        comp4 = komponenten(ids, et4.select("von", "nach").rows())
        print(
            f"  typisiert ohne Kanten in Knoten mit > 5 typisierten Zitaten ({et.height - et4.height} Kanten):",
            verteilung(groessen(comp4)),
            "; größte:",
            [n for _, n in Counter(comp4.values()).most_common(3)],
        )
        # Vorgang als Baum: jede Antwort hängt an genau einem Vorgänger (dem ältesten, den sie
        # typisiert nennt); Wurzel ist das Dokument ohne Vorgänger. So verschmelzen zwei Vorgänge
        # nicht, nur weil ein drittes Dokument beide nennt.
        parent: dict[str, str] = {}
        for von, nach in (
            et.filter(pl.col("tage") >= 0)
            .sort("von", "nach_date", "nach")
            .unique("von", keep="first")
            .select("von", "nach")
            .rows()
        ):
            parent[von] = nach

        baum = Counter(wurzel(i, parent) for i in ids)
        bsizes = Counter(baum.values())
        print(
            f"  als Baum (ein Vorgänger je Dokument): Vorgänge ≥ 2: {sum(c for s_, c in bsizes.items() if s_ > 1)}, "
            f"darin {pct(sum(s_ * c for s_, c in bsizes.items() if s_ > 1), len(ids))};",
            verteilung(bsizes),
            "; größte:",
            [n for _, n in baum.most_common(3)],
        )
        if stadt == "dus":
            size_of = Counter(comp3.values())
            ex = sorted(r for r, n in size_of.items() if n == 5 and meta[r][1] == "2020-2025")
            if ex:
                root = ex[len(ex) // 2]
                members = {i for i, r in comp3.items() if r == root}
                print(
                    "  Beispielvorgang (typisiert, 5 Dokumente):",
                    sorted((str(meta[i][2]), meta[i][4], meta[i][3]) for i in members),
                )
                print(
                    "   Kanten:",
                    et.filter(pl.col("von").is_in(list(members)))
                    .select("von_key", "nach_key", "typ")
                    .rows(),
                )

    # --- Anfragen und Antworten (Düsseldorf) -----------------------------------------------------
    titel("7 Anfragen: Antwort gefunden?")
    dus = docs.filter(pl.col("stadt") == "dus")
    anf = dus.filter(pl.col("art") == "anfrage")
    print("Anfragen (Art 'anfrage'):", anf.height, dict(anf.group_by("datensatz").len().rows()))
    aux_all = (
        dus.select("id", "art", "date", "anlage_name", "anlage_datum")
        .explode("anlage_name", "anlage_datum")
        .drop_nulls("anlage_name")
        .with_columns(low=pl.col("anlage_name").str.to_lowercase())
        .with_columns(
            ist_antwort=pl.col("low").str.contains(ANTWORT_ANLAGE.pattern),
            zwischen=pl.col("low").str.contains(ZWISCHEN.pattern),
            adatum=pl.col("anlage_datum").str.to_date(strict=False),
        )
    )
    mig = aux_all.filter(pl.col("adatum") == MIGRATION)
    print(
        f"Anlagen mit dem Datum {MIGRATION} (Umstellung des Ratsinformationssystems): "
        f"{pct(mig.height, aux_all.height)}; Paperdatum {mig['date'].min()} bis {mig['date'].max()}"
    )
    print(
        "Politik-Vorlagen ohne Art (alt) mit Antwortanlage:",
        pct(
            aux_all.filter((pl.col("art") == "politik") & pl.col("ist_antwort"))["id"].n_unique(),
            dus.filter(pl.col("art") == "politik").height,
        ),
    )
    aux = aux_all.filter(pl.col("art") == "anfrage")
    norm = pl.col("anlage_name").str.replace_all(r"\d", "9")
    print(
        "Anlagennamen als Antwort (Top 12):",
        aux.filter("ist_antwort").group_by(norm).len().sort("len", descending=True).head(12).rows(),
    )
    print(
        "Anlagennamen nicht als Antwort (Top 12):",
        aux.filter(~pl.col("ist_antwort"))
        .group_by(norm)
        .len()
        .sort("len", descending=True)
        .head(12)
        .rows(),
    )
    print(
        "Zwischennachrichten (nicht gezählt):",
        aux.filter(pl.col("ist_antwort") & pl.col("zwischen")).height,
    )
    a1 = (
        aux.filter(pl.col("ist_antwort") & ~pl.col("zwischen"))
        .group_by("id")
        .agg(
            pl.len().alias("antwort_anlagen"),
            pl.col("adatum").filter(pl.col("adatum") != MIGRATION).min().alias("antwort_anlage"),
        )
    )
    a2 = (
        e.filter((pl.col("typ") == "antwort") & (pl.col("tage") >= 0))
        .group_by("nach")
        .agg(
            pl.col("von_date").min().alias("antwort_vorlage"),
            pl.col("von_key").min().alias("antwort_key"),
        )
        .rename({"nach": "id"})
    )
    a = (
        anf.select(
            "id",
            "datensatz",
            "key",
            "reference",
            "date",
            "gremium",
            "gremium_art",
            "urheber_art",
            "parteien",
            "sitzungen",
            "rollen",
            "abgerufen",
        )
        .join(a1, on="id", how="left")
        .join(a2, on="id", how="left")
        .with_columns(
            hat_anlage=pl.col("antwort_anlagen").fill_null(0) > 0,
            hat_vorlage=pl.col("antwort_vorlage").is_not_null(),
            sitzung=pl.col("sitzungen").list.len() > 0,
            alter=(pl.col("abgerufen") - pl.col("date")).dt.total_days(),
            jahr=pl.col("date").dt.year(),
        )
        .with_columns(
            beantwortet=pl.col("hat_anlage") | pl.col("hat_vorlage"),
            antwort=pl.min_horizontal("antwort_anlage", "antwort_vorlage"),
            quelle=pl.when(pl.col("hat_anlage") & pl.col("hat_vorlage"))
            .then(pl.lit("beide"))
            .when(pl.col("hat_anlage"))
            .then(pl.lit("anlage"))
            .when(pl.col("hat_vorlage"))
            .then(pl.lit("vorlage"))
            .otherwise(pl.lit("keine")),
        )
        .with_columns(tage=(pl.col("antwort") - pl.col("date")).dt.total_days())
        .sort("id")
    )
    print(
        a.group_by("datensatz", "quelle")
        .len()
        .pivot(on="quelle", index="datensatz", values="len")
        .fill_null(0)
        .sort("datensatz")
    )
    found = a.filter("beantwortet").height
    print("Anfragen mit gefundener Antwort, alle drei Perioden:", pct(found, a.height))
    for ds in ("2014-2020", "2020-2025", "2025-"):
        x = a.filter(pl.col("datensatz") == ds)
        print(f"  {ds}: {pct(x.filter('beantwortet').height, x.height)}")
    print("Antwort vor der Anfrage datiert:", a.filter(pl.col("tage") < 0).height)

    titel(
        "8 Antwortzeiten (Tage bis zur frühesten datierten Antwort; Anlagen vom Umstellungstag ohne Datum)"
    )
    t = a.filter(pl.col("tage") >= 0)
    print(
        "mit gültigem Datum:",
        pct(t.height, found),
        "; davon je Datensatz:",
        dict(t.group_by("datensatz").len().rows()),
    )
    print("alle:", tage_stats(t["tage"]))
    for q, col in (("Anlage", "antwort_anlage"), ("eigene Drucksache", "antwort_vorlage")):
        s_ = a.filter(pl.col(col).is_not_null()).select(
            (pl.col(col) - pl.col("date")).dt.total_days().alias("d")
        )
        print(f"  nur {q}:", tage_stats(s_.filter(pl.col("d") >= 0)["d"]))
    p90 = int(t["tage"].quantile(0.9, "nearest") or 0)
    p95 = int(t["tage"].quantile(0.95, "nearest") or 0)
    print(f"P90 = {p90} Tage, P95 = {p95} Tage (Grenze für „zu jung, um offen zu heißen“)")
    # gruppiert: Hauptperiode und laufende (nur dort gibt es gültige Daten in Menge)
    neu = a.filter(pl.col("datensatz") != "2014-2020")

    def gruppe(col: str | pl.Expr, df: pl.DataFrame, top: int | None = None) -> pl.DataFrame:
        g = (
            df.group_by(col)
            .agg(
                pl.len().alias("anfragen"),
                pl.col("beantwortet").sum().alias("mit_antwort"),
                pl.col("tage").filter(pl.col("tage") >= 0).len().alias("n_tage"),
                pl.col("tage").filter(pl.col("tage") >= 0).median().alias("median_tage"),
                pl.col("tage")
                .filter(pl.col("tage") >= 0)
                .quantile(0.75, "nearest")
                .alias("q3_tage"),
            )
            .with_columns((pl.col("mit_antwort") / pl.col("anfragen")).round(3).alias("anteil"))
            .sort("anfragen", descending=True)
        )
        return g.head(top) if top else g

    print("Hauptperiode und laufende Periode, je Gremienart:")
    print(gruppe("gremium_art", neu))
    print("je Gremium (Top 16):")
    print(gruppe("gremium", neu, 16))
    neu_p = neu.with_columns(
        partei=pl.when(pl.col("parteien").list.len() > 0)
        .then(pl.col("parteien"))
        .otherwise(pl.concat_list(pl.col("urheber_art").fill_null("unbekannt")))
    ).explode("partei")
    print("je Urheber (Partei, sonst Urheberklasse; gemeinsame Anfragen zählen je Partei):")
    print(gruppe("partei", neu_p))
    print("je Jahr (alle drei Perioden; Antwortzeiten erst ab Juli 2019 datiert):")
    print(gruppe("jahr", a).sort("jahr"))

    titel("9 Ohne Antwort im Datensatz: was das heißt")
    k = a.filter(~pl.col("beantwortet"))
    print("ohne Antwort:", pct(k.height, a.height))
    print(
        "  in einer Sitzung beraten (consultation.meeting):",
        pct(k.filter("sitzung").height, k.height),
        "; Gegenprobe beantwortete:",
        pct(a.filter(pl.col("beantwortet") & pl.col("sitzung")).height, found),
    )
    print(
        "  Rollen der Beratung (alle Anfragen):",
        a.explode("rollen").group_by("rollen").len().sort("len", descending=True).rows(),
    )
    print(
        f"  zu jung (Alter am Abruf ≤ P90 = {p90} Tage):", k.filter(pl.col("alter") <= p90).height
    )
    hp = a.filter(pl.col("datensatz") == "2020-2025")
    rate = gruppe("gremium", hp).filter(pl.col("anfragen") >= 30)
    print(
        f"Praxis je Gremium, Hauptperiode (Gremien mit ≥ 30 Anfragen: {rate.height}): Anteil mit Antwort "
        f"von {rate['anteil'].min()} bis {rate['anteil'].max()}; unter 0,2: {rate.filter(pl.col('anteil') < 0.2).height}, "
        f"über 0,7: {rate.filter(pl.col('anteil') > 0.7).height}"
    )
    print(rate.sort("anteil").select("gremium", "anfragen", "anteil").rows())
    # Urheber gegen die Praxis ihrer Gremien: beobachtet / erwartet (indirekte Standardisierung)
    r_g = gruppe("gremium", hp).select("gremium", pl.col("anteil").alias("rate_g"))
    hp_p = (
        hp.with_columns(
            partei=pl.when(pl.col("parteien").list.len() > 0)
            .then(pl.col("parteien"))
            .otherwise(pl.concat_list(pl.col("urheber_art").fill_null("unbekannt")))
        )
        .explode("partei")
        .join(r_g, on="gremium", how="left")
    )
    std = (
        hp_p.group_by("partei")
        .agg(
            pl.len().alias("anfragen"),
            pl.col("beantwortet").sum().alias("beob"),
            pl.col("rate_g").sum().alias("erw"),
        )
        .with_columns(
            (pl.col("beob") / pl.col("anfragen")).round(3).alias("roh"),
            (pl.col("beob") / pl.col("erw")).round(2).alias("beob_durch_erw"),
        )
        .sort("anfragen", descending=True)
    )
    print(
        "Hauptperiode je Urheber, Antwortanteil roh und gegen die Gremienpraxis (beobachtet/erwartet):"
    )
    print(std)
    print(
        "Gremien der AfD-Anfragen (Hauptperiode):",
        hp_p.filter(pl.col("partei") == "AfD")
        .group_by("gremium")
        .len()
        .sort("len", descending=True)
        .head(5)
        .rows(),
    )
    alt_ = k.filter(pl.col("alter") > p95)
    print(
        f"ohne Antwort und älter als P95 = {p95} Tage:",
        alt_.height,
        dict(alt_.group_by("datensatz").len().rows()),
    )
    gute = set(rate.filter(pl.col("anteil") >= 0.7)["gremium"].to_list())
    print("Gremien, in denen die Antwort fast immer als Anlage kommt (Anteil ≥ 0,7):", sorted(gute))
    cols = [
        "datensatz",
        "reference",
        "date",
        "gremium",
        "urheber_art",
        pl.col("parteien").list.join(",").alias("parteien"),
        "alter",
    ]
    for ds in ("2020-2025", "2025-"):
        x = k.filter(
            (pl.col("datensatz") == ds)
            & (pl.col("alter") > p90)
            & pl.col("gremium").is_in(list(gute))
        )
        print(
            f"älteste ohne gefundene Antwort, {ds}, in diesen Gremien, älter als P90 ({x.height}):"
        )
        print(x.sort("date").select(cols).head(12))
    print(
        "Anteil mit Antwort je Gremium dieser Liste in der laufenden Periode (Praxiswechsel?):",
        gruppe(
            "gremium",
            a.filter((pl.col("datensatz") == "2025-") & pl.col("gremium").is_in(list(gute))),
        )
        .select("gremium", "anfragen", "anteil")
        .sort("gremium")
        .rows(),
    )

    # --- Stichprobe ------------------------------------------------------------------------------
    titel("10 Stichprobe für die Validierung (150 Kanten, Seed 14)")
    e = e.with_columns(
        kante=pl.concat_str("von", "nach", separator="|").map_elements(
            lambda s: hashlib.sha1(s.encode()).hexdigest()[:12], return_dtype=pl.String
        ),
        quer=pl.col("von_datensatz") != pl.col("nach_datensatz"),
    )
    # Schichten in Vorrangfolge; eine Kante gehört zur ersten, die passt
    schichten = (
        ("mg", 15, pl.col("stadt") == "mg"),
        ("periodenuebergreifend", 10, pl.col("quer")),
        ("antwort", 25, pl.col("typ") == "antwort"),
        ("nachfrage", 15, pl.col("typ") == "nachfrage"),
        ("umsetzung", 25, pl.col("typ") == "umsetzung"),
        ("aenderung", 20, pl.col("typ") == "aenderung"),
        ("nachtrag", 10, pl.col("typ") == "nachtrag"),
        ("bau", 5, pl.col("typ") == "bau"),
        ("bezug_titel", 12, (pl.col("typ") == "bezug") & pl.col("felder").str.contains("titel")),
        ("bezug_text", 13, pl.col("typ") == "bezug"),
    )
    rest = e
    sample_rows = []
    groessen_tab = []
    for name, n, cond in schichten:
        pool = rest.filter(cond).sort("kante")
        rest = rest.join(pool.select("kante"), on="kante", how="anti")
        rng = random.Random(f"{SEED}-{name}")
        idx = sorted(rng.sample(range(pool.height), min(n, pool.height)))
        pick = pool[idx].with_columns(pl.lit(name).alias("schicht"))
        sample_rows.append(pick)
        groessen_tab.append((name, pool.height, pick.height))
    sample = pl.concat(sample_rows).sort("schicht", "kante")
    print(
        "Schicht, Kanten in der Schicht, gezogen:",
        groessen_tab,
        "; Rest ohne Schicht:",
        rest.height,
    )
    rows_csv = sample.select("kante", "schicht", "typ", "von", "nach").rows()
    if args.stichprobe:
        STICHPROBE.parent.mkdir(parents=True, exist_ok=True)
        with STICHPROBE.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["kante", "schicht", "typ", "von", "nach"])
            w.writerows(rows_csv)
        schreibe_aufgaben(sample, docs, fund)
        print(f"geschrieben: {STICHPROBE.relative_to(REPO)} ({len(rows_csv)} Kanten), {AUFGABEN}")
    elif STICHPROBE.exists():
        with STICHPROBE.open(encoding="utf-8") as fh:
            saved = [tuple(r) for r in list(csv.reader(fh))[1:]]
        print(
            "gespeicherte Stichprobe:",
            "unverändert"
            if saved == [tuple(r) for r in rows_csv]
            else f"ABWEICHUNG ({len(set(saved) ^ {tuple(r) for r in rows_csv})} Zeilen)",
        )
    lo, hi = wilson(147, 150)
    print(
        f"Wilson-95-%-Intervall bei 147/150: {lo:.3f}–{hi:.3f}; bei 150/150: {wilson(150, 150)[0]:.3f}–1"
    )
    print(f"\nLaufzeit {time.perf_counter() - t0:.1f} s")


def schreibe_aufgaben(sample: pl.DataFrame, docs: pl.DataFrame, fund: pl.DataFrame) -> None:
    """Eine JSON-Zeile je Kante: beide Dokumente (A = zitiert, B = zitierend) und die Fundstelle.

    Der Kantentyp des Verfahrens steht nicht darin: die Kodierer sollen die Beziehung selbst
    benennen (F4: ohne die Ausgabe des zu prüfenden Verfahrens).
    """
    buch = tomllib.loads(CODEBUCH.read_text(encoding="utf-8"))
    d = {
        r["id"]: r
        for r in docs.select(
            "id", "key", "reference", "name", "paper_type", "date", "gremium", "text", "anlage_name"
        ).iter_rows(named=True)
    }
    f = {(r["von"], r["nach"]): r for r in fund.iter_rows(named=True)}

    def dok(i: str) -> dict[str, Any]:
        r = d[i]
        return {
            "id": i,
            "drucksache": r["reference"],
            "titel": r["name"],
            "dokumentart": r["paper_type"],
            "datum": r["date"].isoformat() if r["date"] else None,
            "gremium": r["gremium"],
            "anlagen": r["anlage_name"] or [],
            "textanfang": (r["text"] or "")[:TEXTANFANG],
        }

    AUFGABEN.parent.mkdir(parents=True, exist_ok=True)
    with AUFGABEN.open("w", encoding="utf-8") as fh:
        for r in sample.iter_rows(named=True):
            hit = f.get((r["von"], r["nach"]))
            fundstelle: dict[str, Any] = {"dokument": "B", "feld": "nummer", "ausschnitt": None}
            if hit is not None:
                src = d[r["von"]]
                s = {
                    "titel": (src["name"] or "").lower(),
                    "text": src["text"] or "",
                    "anlage": " | ".join(src["anlage_name"] or []).lower(),
                }[hit["feld"]]
                a, b = max(0, hit["start"] - FENSTER), min(len(s), hit["end"] + FENSTER)
                fundstelle = {
                    "dokument": "B",
                    "feld": hit["feld"],
                    "treffer": hit["match"],
                    "ausschnitt": s[a:b],
                    "start_im_ausschnitt": hit["start"] - a,
                    "ende_im_ausschnitt": hit["end"] - a,
                }
            rec = {
                "vorhaben": "14-vorgaenge",
                "kante": r["kante"],
                "codebuch": buch["meta"]["version"],
                "a": dok(r["nach"]),
                "b": dok(r["von"]),
                "fundstelle": fundstelle,
                "fragen": buch["fragen"],
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
