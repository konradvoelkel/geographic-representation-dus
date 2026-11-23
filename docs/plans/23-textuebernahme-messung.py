"""Rechnet die Zahlen von `23-textuebernahme.md` nach (Vorhaben 23, Stufe 1: Textübernahme).

    uv run python -I docs/plans/23-textuebernahme-messung.py [--schreiben] [--neu] [--ohne-gegenprobe]
        [--cherif PFAD] [--messdaten PFAD]

Liest je Düsseldorfer Profil und für Mönchengladbach, was `georep run` geschrieben hat
(`interim/papers.parquet` mit dem kleingeschriebenen Text der Hauptdatei,
`processed/papers_gremien.parquet`, `processed/dokumente_urheber.parquet`; Pfade aus
`georep --profile <p> paths`), dazu das Ratsvorlagen-Korpus von Cherif (Zenodo, CC BY 4.0) aus
`--cherif` (die vier `ratsvorlagen_<stadt>.jsonl.zst`, nur gelesen, nie ausgeführt; das Skript liegt
woanders und läuft mit `python -I`). Die Antragsteller der Düsseldorfer Dokumente kommen aus dem
Regelwerk von Vorhaben 15 (`15-funktion-messung.py`, `antragsteller()`), die Parteimuster aus
`[originators]` des Profils.

Verfahren (23-textuebernahme.md, § 3): Wort-Tokens (`\\w+`, kleingeschrieben, höchstens CAP je
Dokument), Shingles aus K Wörtern wie der Prototyp von Vorhaben 13, Shingles in mehr als DF_MAX
Dokumenten zählen als Baustein nicht mit; MinHash mit LSH über **Fenster** (zwei Blöcke zu BLOCK
Shingles, je um einen Block versetzt) in 64 Bändern zu 2 Zeilen; ein Vorfilter über die exakt
gezählten gemeinsamen seltenen Shingles; lokale Ausrichtung (Smith-Waterman auf Wörtern) auf jedem
Dokumentpaar mit mindestens einem Düsseldorfer Dokument; eine Zufallsgrenze aus einer
Nullverteilung; eine Regel für die Art der Übernahme in zwei Durchgängen (`classify`, `refine`) und
Familien über die politischen Übernahmen. Die Gegenprobe misst den Recall der Kandidatensuche gegen
eine erschöpfende Suche über einen invertierten Index der seltenen Shingles.

Laufzeit: rund 19 Minuten ohne Zwischenablage (`--neu`, gemessen 2026-11-23 unter Fremdlast,
Lastmittel 10 bis 18, `nice -n 10`, höchster Speicher 5,6 GB), davon rund 8 Minuten Ausrichtung und
6 Minuten LSH mit Vorfilter; mit Zwischenablage rund 6 Minuten.

Zwischenergebnisse liegen unter `<messdaten>/23-textuebernahme/cache/` (Tokens, Kandidaten,
Ausrichtungen); `--neu` rechnet alles neu. `--schreiben` legt die Stichprobe
(`validierung/23-textuebernahme/stichprobe.csv`) und die Kodieraufgaben
(`<messdaten>/kodierung/23-textuebernahme/aufgaben.jsonl`) an; ohne den Schalter prüft das Skript nur,
ob die Datei im Repo gleich der berechneten ist. Alles ist deterministisch (feste Seeds, Hash ohne
Zufall des Interpreters, sortierte Paare).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import io
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from array import array
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("POLARS_MAX_THREADS", "4")
import numpy as np  # noqa: E402
import numpy.typing as npt  # noqa: E402
import polars as pl  # noqa: E402
from scipy.sparse import coo_matrix  # noqa: E402
from scipy.sparse.csgraph import connected_components  # noqa: E402

U64 = npt.NDArray[np.uint64]
U32 = npt.NDArray[np.uint32]
I32 = npt.NDArray[np.int32]
I64 = npt.NDArray[np.int64]

# --- Parameter, begründet in 23-textuebernahme.md, § 3 ----------------------------------------
CAP = 3000  # Wörter je Dokument; ein Antrag ist kürzer, abgeschnitten werden lange Vorlagen
K = 5  # Wörter je Shingle, wie Vorhaben 13
BLOCK = 25  # Shingles je Block; ein Fenster sind zwei Blöcke (50 Shingles, 54 Wörter)
MIN_SH = 20  # kürzere Texte (unter 24 Wörtern) bekommen kein Fenster
N_PERM, BANDS, ROWS = 128, 64, 2  # Schwelle (1/64)^(1/2) ≈ 0,125 (32 × 4 fand zu wenig, § 3.4)
MIN_SHARED = 5  # ein Dokumentpaar braucht so viele gemeinsame seltene Shingles für die Ausrichtung
MAXDOC = 30  # ein Eimer mit mehr Dokumenten ist ein Baustein und gibt keine Paare
DF_MAX = 30  # ein Shingle in mehr Dokumenten (alle Korpora) ist Baustein und zählt im MinHash nicht
MIN_RARE = 15  # ein Fenster mit weniger seltenen Shingles geht nicht in die Kandidatensuche
SEED = 23
PRIME = np.uint64(4_294_967_291)
MARGIN = 40  # Wörter Rand um die Fenster eines Paars, in dem die Ausrichtung sucht
MAXREG = 1500  # höchstens so viele Wörter je Seite gehen in die Ausrichtung
MATCH, MISMATCH, GAP = 1, -1, -1  # Smith-Waterman auf Wörtern, lineare Lücke
NULL_PAIRS = 2000  # Zufallspaare für die Verteilung der Ausrichtung ohne Übernahme
NULL_LEN = 300  # Wörter je Seite in der Nullverteilung
MIN_ALIGNED = 30  # Mindestlänge einer Übernahme in Wörtern (kürzere Seite der Ausrichtung)
FREQ_DOCS = 30  # ein Abschnitt, dessen Shingles im Median in mehr Dokumenten stehen, ist Baustein
LEGAL_PER_100 = 3.0  # Rechtsmarken je 100 Wörter, ab denen eine Stelle Rechtszitat heißt
SAMPLE_SIZE = 100
EXCERPT_CONTEXT = 40  # Wörter Kontext links und rechts der ausgerichteten Stelle
EXCERPT_MAX = 2500  # Zeichen der Stelle samt Kontext je Dokument
HEAD = 600  # Zeichen des Dokumentanfangs (Briefkopf mit Antragsteller)

MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
CHERIF = Path("/media/konrad/xtraspace/georep/fremddaten/cherif")
REPO = Path(__file__).resolve().parents[2]
SAMPLE_CSV = REPO / "validierung" / "23-textuebernahme" / "stichprobe.csv"
CODEBOOK = REPO / "validierung" / "23-textuebernahme" / "codebuch.toml"
TOKEN = re.compile(r"\w+")

# Korpora: (Code, Profil oder Stadt, Stadt, Periode). Die Düsseldorfer Perioden sind disjunkt.
DUS_PROFILES = (
    ("dus-2014", "duesseldorf-2014", "duesseldorf", "2014-2020"),
    ("dus-2020", "duesseldorf", "duesseldorf", "2020-2025"),
    ("dus-2025", "duesseldorf-2025", "duesseldorf", "2025-"),
    ("mg", "moenchengladbach", "moenchengladbach", "2020-2025"),
)
CHERIF_CITIES = (
    ("leipzig", "leipzig"),
    ("osnabrueck", "osnabrueck"),
    ("dresden", "dresden"),
    ("freiburg", "freiburg-im-breisgau"),
)
KORPORA = tuple(k for k, *_ in DUS_PROFILES) + tuple(c for c, _ in CHERIF_CITIES)
DUS_CODES = frozenset({0, 1, 2})

# ================================================================================================
# Profil der Fremddaten (Stufe 2: in ein Profil je Stadt, nicht in den Code)
# ================================================================================================
# Dokumentarten der Cherif-Städte -> Urheberklasse. Was nicht hier steht, ist Verwaltung.
CHERIF_POLITIK = frozenset(
    {
        "Antrag",
        "Änderungsantrag",
        "Neufassung Antrag",
        "Anfrage",
        "Dringliche Anfrage",
        "OBM-Anfrage",
        "Haushaltsantrag Stadtrat",
        "Haushaltsantrag Ortschaftsrat",
        "Haushaltsantrag Stadtbezirksbeirat",
        "Neufassung zum Haushaltsantrag",
        "Änderungsantrag zum Haushaltsantrag",
        "Änderung zum HH-Planentwurf",
        "Aktuelle Stunde",
    }
)
CHERIF_EINGABE = frozenset(
    {
        "Einwohneranfrage",
        "Petition",
        "Bürgereinwand zum Haushalt",
        "Bürgervorschlag zum Haushalt",
        "Stadtbezirksbudget Projekt",
        "Stadtbezirksbudget Vorschlag",
    }
)
# Parteien im Kopf eines Cherif-Dokuments; die Schlüssel sind die des Düsseldorfer Profils, wo es
# die Partei dort gibt, sonst ein eigener.
CHERIF_PARTEIEN: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (k, re.compile(p))
    for k, p in (
        ("CDU", r"\bcdu\b"),
        ("GRUENE", r"grüne|gruene|bündnis ?90"),
        ("SPD", r"\bspd\b"),
        ("FDP", r"\bfdp\b"),
        ("Die_Linke", r"\blinke\b"),
        ("AfD", r"\bafd\b"),
        ("VOLT", r"\bvolt\b"),
        ("PARTEI", r"die partei\b"),
        ("T_FW", r"freie wähler|tierschutz"),
        ("BSW", r"\bbsw\b|sahra wagenknecht"),
        ("Freibeuter", r"freibeuter"),
        ("Piraten", r"piraten"),
        ("UWG", r"\buwg\b"),
        ("BOB", r"\bbob\b|bund osnabrücker bürger"),
    )
)
LEIPZIG_KOPF = re.compile(r"eingereicht von\s*(.{0,200}?)\s*betreff", re.S)
OSNABRUECK_KOPF = re.compile(r"seite:\s*1/\d+\s*(.{0,200}?)\s*(antrag|anfrage)\s+vorlage-nr", re.S)

# Floskeln eines Formulars: Briefkopf, Anrede, Bitte um Tagesordnung, Gruß, Unterschrift,
# Beratungsfolge. Was eine Stelle nach Abzug der Floskeln übrig lässt, ist ihr Kern.
FLOSKEL = re.compile(
    r"sehr geehrte[rn]? (herr|frau|damen und herren|oberbürgermeister|bezirksbürgermeister)\w*[^,.]{0,60}[,.]?"
    r"|(wir bitten|ich bitte|bitten wir) sie,? .{0,80}?(tagesordnung|beratung|abstimmung|beantwortung)"
    r".{0,120}?(zu setzen|zu nehmen|vorzulegen|zu bringen|aufzunehmen|zu beantworten|folgende fragen)"
    r"|mit freundlichen grüßen|freundliche grüße|f\.\s?d\.\s?r\.|gez\.\s*[^\s,]+(\s[^\s,]+){0,3}"
    r"|fraktions(vorsitzende|sprecher|geschäftsführer)\w*|ratsherr\w*|ratsfrau\w*"
    r"|rsd vorlage|seite \d+ von \d+|seite:? \d+/\d+|x?\s*öffentlich\s+nicht öffentlich"
    r"|beratungsfolge:?.{0,60}?(sitzungsdatum|zuständigkeit|ergebnis)|gremium\s+sitzungsdatum\s+\w+"
    r"|an (den|die|das) (herrn |frau )?(bezirksbürgermeister|bezirksvorsteher|vorsitzend|oberbürgermeister|ausschuss)\w*"
    r"|düsseldorf, (den )?\d{1,2}\.\d{1,2}\.\d{2,4}|vorlage \S+/\s*\d+/\d{4}"
    r"|die sitzung wurde zum zeitpunkt der drucklegung.{0,60}|das beratungsergebnis wurde zum zeitpunkt.{0,60}"
    r"|anlagen:.{0,40}?(beigefügt|vorhanden)|a n t r a g|a n f r a g e"
)

# Rechtsmarken für die Art „Rechtszitat"; gezählt im ausgerichteten Text.
LEGAL = re.compile(
    r"§|\babs\.|\bgesetz\w*|\w+gesetz\w*|verordnung\w*|\bsatz \d|richtlinie\w*|\berlass\w*"
    r"|\bgo nrw\b|gemeindeordnung|\bbaugb\b|\bstvo\b|\bkag\b|\bsächsgemo\b|\bnkomvg\b|\bgemo\b"
    r"|\bart\. \d|grundgesetz|\bbgb\b|\bsgb\b|\bvwvfg\b"
)


# ================================================================================================
# Laden
# ================================================================================================
def georep_paths(profile: str) -> dict[str, str]:
    exe = shutil.which("georep") or str(Path(sys.executable).with_name("georep"))
    out = subprocess.run(
        [exe, "--profile", profile, "paths"], check=True, capture_output=True, text=True
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def regelwerk_15() -> Any:
    """Das Messskript von Vorhaben 15 als Modul: `antragsteller()` und `titelparteien()`."""
    path = REPO / "docs" / "plans" / "15-funktion-messung.py"
    spec = importlib.util.spec_from_file_location("funktion15", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"{path} fehlt")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DOC_SCHEMA = {
    "korpus": pl.String,
    "stadt": pl.String,
    "periode": pl.String,
    "id": pl.String,
    "reference": pl.String,
    "name": pl.String,
    "date": pl.String,
    "paper_type": pl.String,
    "gremium": pl.String,
    "urheber": pl.String,  # Politik, Verwaltung, Eingabe, unbekannt
    "parteien": pl.List(pl.String),
    "file_name": pl.String,
    "text": pl.String,
}


def load_dus(f15: Any) -> pl.DataFrame:
    frames = []
    for code, profile, stadt, periode in DUS_PROFILES:
        root = Path(georep_paths(profile)["root"])
        corpus = pl.read_parquet(
            root / "interim" / "papers.parquet",
            columns=["id", "name", "reference", "date", "paper_type", "file_name", "text"],
        )
        gremien = pl.read_parquet(
            root / "processed" / "papers_gremien.parquet", columns=["id", "gremium"]
        )
        urheber = pl.read_parquet(
            root / "processed" / "dokumente_urheber.parquet",
            columns=["id", "urheber_art", "parteien", "quelle"],
        )
        _marker, muster, _kurz = f15.titelparteien(profile)
        df = corpus.join(gremien, on="id", how="left").join(urheber, on="id", how="left").sort("id")
        parteien: list[list[str]] = []
        for row in df.iter_rows(named=True):
            p = f15.antragsteller(
                row["paper_type"],
                row["name"],
                row["parteien"],
                row["urheber_art"],
                row["quelle"],
                muster,
                row["text"],
            )
            if row["urheber_art"] == "Person":
                p = list(row["parteien"] or [])
            if not p and row["urheber_art"] in ("Fraktion", "Person"):
                head = (row["text"] or "")[:HEAD]
                p = [k for k, m in muster if m.search(head)][:3]
            parteien.append(sorted(set(p)))
        klasse = {
            "Verwaltung": "Verwaltung",
            "Fraktion": "Politik",
            "Person": "Politik",
            "Eingabe": "Eingabe",
        }
        frames.append(
            df.with_columns(
                pl.lit(code).alias("korpus"),
                pl.lit(stadt).alias("stadt"),
                pl.lit(periode).alias("periode"),
                pl.col("date").cast(pl.String),
                pl.col("urheber_art")
                .replace_strict(klasse, default="unbekannt", return_dtype=pl.String)
                .alias("urheber"),
                pl.Series("parteien", parteien, dtype=pl.List(pl.String)),
                pl.col("text").fill_null(""),
            ).select(list(DOC_SCHEMA))
        )
    return pl.concat(frames)


def cherif_parteien(city: str, paper_type: str, text: str) -> list[str]:
    head = text[:1500].lower()
    seg = ""
    if city == "leipzig":
        m = LEIPZIG_KOPF.search(head)
        seg = m.group(1) if m else ""
    elif city == "osnabrueck":
        m = OSNABRUECK_KOPF.search(head)
        seg = m.group(1) if m else ""
    elif city == "dresden" and paper_type.lower().startswith("antrag "):
        seg = paper_type.lower()[len("antrag ") :]
        if seg.startswith("ortschaft") or seg.startswith("sbr") or seg.startswith("mitglieder"):
            seg = ""
    return sorted({k for k, m in CHERIF_PARTEIEN if seg and m.search(seg)})


def cherif_urheber(city: str, paper_type: str, rolle: str | None) -> str:
    if rolle == "anlage":
        return "Verwaltung"
    if paper_type in CHERIF_POLITIK or (city == "dresden" and paper_type.startswith("Antrag ")):
        return "Politik"
    if paper_type in CHERIF_EINGABE:
        return "Eingabe"
    return "Verwaltung"


def load_cherif(folder: Path) -> pl.DataFrame:
    from compression import zstd

    rows: list[dict[str, Any]] = []
    for code, slug in CHERIF_CITIES:
        name = "freiburg" if code == "freiburg" else code
        with zstd.open(folder / f"ratsvorlagen_{name}.jsonl.zst", "rt", encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                text = r.get("text") or ""
                ptype = r.get("paper_type") or ""
                urheber = cherif_urheber(code, ptype, r.get("rolle"))
                rows.append(
                    {
                        "korpus": code,
                        "stadt": slug,
                        "periode": "",
                        "id": r["oparl_id"]
                        + (f"#{r['datei_name']}" if r.get("rolle") == "anlage" else ""),
                        "reference": r.get("reference"),
                        "name": r.get("name"),
                        "date": r.get("date"),
                        "paper_type": ptype,
                        "gremium": None,
                        "urheber": urheber,
                        "parteien": cherif_parteien(code, ptype, text)
                        if urheber == "Politik"
                        else [],
                        "file_name": None,
                        # nur so viel Text, wie die Tokens brauchen (CAP Wörter); der Rest bleibt
                        "text": text[: CAP * 14],
                    }
                )
    return pl.DataFrame(rows, schema=DOC_SCHEMA).sort("korpus", "id")


# ================================================================================================
# Tokens und Shingles
# ================================================================================================
def _mix(x: U64) -> U64:
    """splitmix64, wie Vorhaben 13."""
    z = x + np.uint64(0x9E3779B97F4A7C15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return z ^ (z >> np.uint64(31))


@dataclass
class Tokens:
    """Alle Dokumente hintereinander: Wort-IDs, Zeichenpositionen, Shingles, Versätze je Dokument."""

    ids: I32  # Wort-ID je Token
    start: I32  # Zeichenposition des Tokens im Text
    end: I32
    off: I64  # Versatz des ersten Tokens je Dokument, Länge n_docs + 1
    sh: U32  # Shingle-Hash je Position (Länge je Dokument max(n - K + 1, 0))
    sh_off: I64
    vocab_size: int

    def doc(self, d: int) -> I32:
        return self.ids[self.off[d] : self.off[d + 1]]

    def ntok(self) -> I64:
        return np.diff(self.off)

    def nsh(self) -> I64:
        return np.diff(self.sh_off)

    def shingles(self, d: int) -> U32:
        return self.sh[self.sh_off[d] : self.sh_off[d + 1]]


def tokenize(texts: Sequence[str]) -> Tokens:
    vocab: dict[str, int] = {}
    ids = array("i")
    start = array("i")
    end = array("i")
    off = [0]
    for text in texts:
        for m in itertools.islice(TOKEN.finditer(text), CAP):
            tok = m.group().lower()
            v = vocab.get(tok)
            if v is None:
                v = len(vocab)
                vocab[tok] = v
            ids.append(v)
            start.append(m.start())
            end.append(m.end())
        off.append(len(ids))
    # Token-Hash aus BLAKE2b (unabhängig von der Reihenfolge des Vokabulars), dann splitmix64
    th = np.empty(len(vocab), dtype=np.uint64)
    for tok, v in vocab.items():
        th[v] = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "little")
    ids_a = np.frombuffer(ids, dtype=np.int32).copy()
    off_a = np.asarray(off, dtype=np.int64)
    hashes = th[ids_a]
    sh_parts: list[U32] = []
    sh_off = [0]
    with np.errstate(over="ignore"):
        for d in range(len(texts)):
            h = hashes[off_a[d] : off_a[d + 1]]
            n = len(h) - K + 1
            if n <= 0:
                sh_off.append(sh_off[-1])
                continue
            acc = np.zeros(n, dtype=np.uint64)
            for j in range(K):
                acc = _mix(acc ^ h[j : j + n])
            sh_parts.append((acc >> np.uint64(32)).astype(np.uint32))
            sh_off.append(sh_off[-1] + n)
    return Tokens(
        ids=ids_a,
        start=np.frombuffer(start, dtype=np.int32).copy(),
        end=np.frombuffer(end, dtype=np.int32).copy(),
        off=off_a,
        sh=np.concatenate(sh_parts) if sh_parts else np.empty(0, dtype=np.uint32),
        sh_off=np.asarray(sh_off, dtype=np.int64),
        vocab_size=len(vocab),
    )


# ================================================================================================
# Fenster, MinHash, LSH
# ================================================================================================
@dataclass
class Windows:
    doc: I64  # Dokument je Fenster
    tok_start: I64  # erstes Token des Fensters im Dokument
    tok_end: I64  # hinter dem letzten Token
    block_a: I64  # die beiden Blöcke (gleich bei Dokumenten mit nur einem Block)
    block_b: I64
    block_starts: I64  # Versatz jedes Blocks in `flat`
    flat: U64  # Shingles der Dokumente mit Fenstern, hintereinander
    rare_flat: npt.NDArray[np.bool_]  # Shingle in höchstens DF_MAX Dokumenten
    nrare: I64  # seltene Shingles je Fenster


def shingle_df(tok: Tokens) -> I64:
    """Dokumenthäufigkeit je Shingle-Position: in wie vielen Dokumenten (aller Korpora) es steht."""
    nsh = tok.nsh()
    doc = np.repeat(np.arange(len(nsh), dtype=np.uint64), nsh)
    pairs = np.unique((tok.sh.astype(np.uint64) << np.uint64(32)) | doc)
    hashes, counts = np.unique(pairs >> np.uint64(32), return_counts=True)
    return counts[np.searchsorted(hashes, tok.sh.astype(np.uint64))].astype(np.int64)


def windows(tok: Tokens, df: I64) -> Windows:
    nsh = tok.nsh()
    rare = df <= DF_MAX
    parts_flat: list[U32] = []
    parts_rare: list[npt.NDArray[np.bool_]] = []
    block_starts: list[npt.NDArray[np.int64]] = []
    w_doc: list[npt.NDArray[np.int64]] = []
    w_ts: list[npt.NDArray[np.int64]] = []
    w_te: list[npt.NDArray[np.int64]] = []
    w_a: list[npt.NDArray[np.int64]] = []
    w_b: list[npt.NDArray[np.int64]] = []
    pos = 0
    nblocks = 0
    for d in np.flatnonzero(nsh >= MIN_SH):
        n = int(nsh[d])
        parts_flat.append(tok.shingles(int(d)))
        parts_rare.append(rare[tok.sh_off[d] : tok.sh_off[d + 1]])
        nb = math.ceil(n / BLOCK)
        block_starts.append(pos + np.arange(nb, dtype=np.int64) * BLOCK)
        if nb == 1:
            first = np.array([0], dtype=np.int64)
            second = first
        else:
            first = np.arange(nb - 1, dtype=np.int64)
            second = first + 1
        w_doc.append(np.full(len(first), d, dtype=np.int64))
        w_ts.append(first * BLOCK)
        w_te.append(np.minimum(first * BLOCK + 2 * BLOCK, n) + K - 1)
        w_a.append(nblocks + first)
        w_b.append(nblocks + second)
        pos += n
        nblocks += nb
    starts = np.concatenate(block_starts)
    rare_flat = np.concatenate(parts_rare)
    per_block = np.add.reduceat(rare_flat.astype(np.int64), starts)
    block_a = np.concatenate(w_a)
    block_b = np.concatenate(w_b)
    nrare = per_block[block_a] + np.where(block_b != block_a, per_block[block_b], 0)
    return Windows(
        doc=np.concatenate(w_doc),
        tok_start=np.concatenate(w_ts),
        tok_end=np.concatenate(w_te),
        block_a=block_a,
        block_b=block_b,
        block_starts=starts,
        flat=np.concatenate(parts_flat).astype(np.uint64),
        rare_flat=rare_flat,
        nrare=nrare,
    )


@dataclass
class Candidates:
    wa: I64  # Fensterpaare (Fenster des kleineren Dokuments zuerst)
    wb: I64
    frequent: npt.NDArray[np.bool_]  # Fenster in mindestens einem Eimer mit > MAXDOC Dokumenten
    active: int  # Fenster mit mindestens MIN_RARE seltenen Shingles
    buckets_kept: int
    buckets_frequent: int


def lsh(win: Windows, korpus_code: I64, cherif_doc: npt.NDArray[np.bool_]) -> Candidates:
    """Fensterpaare mit gleichem Schlüssel in mindestens einem Band; nur Paare mit Düsseldorf."""
    rng = np.random.default_rng(SEED)
    a = rng.integers(1, int(PRIME), size=N_PERM, dtype=np.uint64)
    b = rng.integers(0, int(PRIME), size=N_PERM, dtype=np.uint64)
    nw = len(win.doc)
    is_dus = np.isin(korpus_code[win.doc], list(DUS_CODES))
    frequent = np.zeros(nw, dtype=bool)
    active = np.flatnonzero(win.nrare >= MIN_RARE)
    na = len(active)
    common = ~win.rare_flat
    found: list[I64] = []
    kept_total = 0
    freq_total = 0
    for band in range(BANDS):
        cols = []
        for r in range(ROWS):
            i = band * ROWS + r
            values = (a[i] * win.flat + b[i]) % PRIME
            values[common] = PRIME  # häufige Shingles zählen nicht
            bm = np.minimum.reduceat(values, win.block_starts)
            cols.append(np.minimum(bm[win.block_a[active]], bm[win.block_b[active]]))
        with np.errstate(over="ignore"):
            key = np.full(na, np.uint64(band), dtype=np.uint64)
            for c in cols:
                key = _mix(key ^ c)
        order = active[np.argsort(key, kind="stable")]
        ks = np.sort(key, kind="stable")
        bounds = np.flatnonzero(np.diff(ks)) + 1
        run_start = np.concatenate([[0], bounds])
        run_len = np.diff(np.concatenate([run_start, [na]]))
        multi = np.flatnonzero(run_len >= 2)
        if multi.size == 0:
            continue
        # Elemente der Eimer mit mindestens zwei Fenstern
        el_run = np.repeat(multi, run_len[multi])
        el_pos = _ranges(run_start[multi], run_len[multi])
        el_win = order[el_pos]
        el_doc = win.doc[el_win]
        # verschiedene Dokumente je Eimer
        pair_key = el_run.astype(np.int64) * (int(win.doc.max()) + 1) + el_doc
        uniq = np.unique(pair_key)
        run_of_uniq = uniq // (int(win.doc.max()) + 1)
        runs, ndocs = np.unique(run_of_uniq, return_counts=True)
        ndoc_of_run = np.zeros(len(run_len), dtype=np.int64)
        ndoc_of_run[runs] = ndocs
        has_dus = np.zeros(len(run_len), dtype=bool)
        np.logical_or.at(has_dus, el_run, is_dus[el_win])
        freq_runs = ndoc_of_run > MAXDOC
        frequent[el_win[freq_runs[el_run]]] = True
        freq_total += int(freq_runs.sum())
        keep_run = (ndoc_of_run >= 2) & (ndoc_of_run <= MAXDOC) & has_dus
        kept_total += int(keep_run.sum())
        sel = keep_run[el_run]
        el_run_k = el_run[sel]
        el_win_k = el_win[sel]
        # Paare je Eimer; die meisten Eimer haben zwei Fenster
        bounds_k = np.flatnonzero(np.diff(el_run_k)) + 1
        groups = np.split(el_win_k, bounds_k)
        out: list[tuple[int, int]] = []
        for g in groups:
            if len(g) == 2:
                x, y = int(g[0]), int(g[1])
                dx, dy = int(win.doc[x]), int(win.doc[y])
                if dx != dy and (is_dus[x] or is_dus[y]):
                    out.append((x, y) if dx < dy else (y, x))
                continue
            for x, y in itertools.combinations(g.tolist(), 2):
                dx, dy = int(win.doc[x]), int(win.doc[y])
                if dx == dy or not (is_dus[x] or is_dus[y]):
                    continue
                if cherif_doc[dx] and cherif_doc[dy]:
                    continue
                out.append((x, y) if dx < dy else (y, x))
        if out:
            arr = np.asarray(out, dtype=np.int64)
            found.append(arr[:, 0] * nw + arr[:, 1])
    allk = np.unique(np.concatenate(found)) if found else np.empty(0, dtype=np.int64)
    return Candidates(
        wa=allk // nw,
        wb=allk % nw,
        frequent=frequent,
        active=na,
        buckets_kept=kept_total,
        buckets_frequent=freq_total,
    )


def _ranges(starts: I64, lengths: I64) -> I64:
    """Verkettung von arange(s, s + n) für alle (s, n), ohne Python-Schleife."""
    total = int(lengths.sum())
    rep = np.repeat(starts - np.concatenate([[0], np.cumsum(lengths)[:-1]]), lengths)
    return np.arange(total, dtype=np.int64) + rep


# ================================================================================================
# Lokale Ausrichtung (Smith-Waterman auf Wörtern)
# ================================================================================================
def smith_waterman(x: I32, y: I32) -> tuple[int, int, int, int, int, int, int]:
    """Beste lokale Ausrichtung von x und y: (Wert, x_von, x_bis, y_von, y_bis, Treffer, Spalten).

    Lineare Lücke: die Zeile wird ohne waagrechte Lücke gerechnet, die waagrechten Lücken danach
    mit einem laufenden Maximum (H[i,j] = max_k t[k] + GAP·(j − k)), das ist exakt für lineare
    Kosten. Die Rückverfolgung zählt Treffer und Spalten der Ausrichtung.
    """
    n, m = len(x), len(y)
    if n == 0 or m == 0:
        return 0, 0, 0, 0, 0, 0, 0
    h = np.zeros((n + 1, m + 1), dtype=np.int32)
    idx = np.arange(1, m + 1, dtype=np.int32)
    for i in range(1, n + 1):
        s = np.where(y == x[i - 1], MATCH, MISMATCH).astype(np.int32)
        t = np.maximum(np.maximum(h[i - 1, :-1] + s, h[i - 1, 1:] + GAP), 0)
        h[i, 1:] = np.maximum.accumulate(t - GAP * idx) + GAP * idx
    i, j = divmod(int(np.argmax(h)), m + 1)
    best = int(h[i, j])
    ie, je = i, j
    matches = cols = 0
    while i > 0 and j > 0 and h[i, j] > 0:
        v = h[i, j]
        same = x[i - 1] == y[j - 1]
        if v == h[i - 1, j - 1] + (MATCH if same else MISMATCH):
            matches += int(same)
            i -= 1
            j -= 1
        elif v == h[i - 1, j] + GAP:
            i -= 1
        elif v == h[i, j - 1] + GAP:
            j -= 1
        else:  # pragma: no cover - die Rekursion lässt keinen anderen Vorgänger zu
            break
        cols += 1
    return best, i, ie, j, je, matches, cols


ALIGN_SCHEMA = {
    "a": pl.Int64,
    "b": pl.Int64,
    "fenster": pl.Int64,
    "wert": pl.Int64,
    "a_von": pl.Int64,
    "a_bis": pl.Int64,
    "b_von": pl.Int64,
    "b_bis": pl.Int64,
    "treffer": pl.Int64,
    "spalten": pl.Int64,
}


def shared_rare(tok: Tokens, df: I64, pairs: Sequence[tuple[int, int]]) -> I64:
    """Zahl der verschiedenen seltenen Shingles, die beide Dokumente eines Paars tragen."""
    rare = df <= DF_MAX
    memo: dict[int, U32] = {}

    def own(d: int) -> U32:
        s = memo.get(d)
        if s is None:
            s = np.unique(tok.shingles(d)[rare[tok.sh_off[d] : tok.sh_off[d + 1]]])
            memo[d] = s
        return s

    return np.asarray(
        [np.intersect1d(own(a), own(b), assume_unique=True).size for a, b in pairs],
        dtype=np.int64,
    )


def filter_candidates(
    tok: Tokens, df: I64, win: Windows, cand: Candidates
) -> tuple[Candidates, int]:
    """Nur Fensterpaare aus Dokumentpaaren mit mindestens MIN_SHARED gemeinsamen seltenen Shingles."""
    da = win.doc[cand.wa]
    db = win.doc[cand.wb]
    key = da * (int(win.doc.max()) + 1) + db
    uniq, inverse = np.unique(key, return_inverse=True)
    pairs = [(int(k // (int(win.doc.max()) + 1)), int(k % (int(win.doc.max()) + 1))) for k in uniq]
    counts = shared_rare(tok, df, pairs)
    keep = counts[inverse] >= MIN_SHARED
    kept = Candidates(
        wa=cand.wa[keep],
        wb=cand.wb[keep],
        frequent=cand.frequent,
        active=cand.active,
        buckets_kept=cand.buckets_kept,
        buckets_frequent=cand.buckets_frequent,
    )
    return kept, len(uniq)


def align_pairs(tok: Tokens, win: Windows, cand: Candidates) -> pl.DataFrame:
    """Je Dokumentpaar eine Ausrichtung über den Bereich seiner Kandidatenfenster."""
    da = win.doc[cand.wa]
    db = win.doc[cand.wb]
    order = np.lexsort((win.tok_start[cand.wa], db, da))
    da, db = da[order], db[order]
    wa, wb = cand.wa[order], cand.wb[order]
    bounds = np.flatnonzero((np.diff(da) != 0) | (np.diff(db) != 0)) + 1
    starts = np.concatenate([[0], bounds])
    ends = np.concatenate([bounds, [len(da)]])
    ntok = tok.ntok()
    rows: list[tuple[int, ...]] = []
    for s, e in zip(starts.tolist(), ends.tolist(), strict=True):
        a, b = int(da[s]), int(db[s])
        as_, ae = win.tok_start[wa[s:e]], win.tok_end[wa[s:e]]
        bs, be = win.tok_start[wb[s:e]], win.tok_end[wb[s:e]]
        if max(ae.max() - as_.min(), be.max() - bs.min()) > MAXREG:
            # mehrere Stellen: die Diagonale mit den meisten Fensterpaaren
            diag = bs - as_
            near = (np.abs(diag[:, None] - diag[None, :]) <= 4 * BLOCK).sum(axis=1)
            keep = np.abs(diag - diag[int(np.argmax(near))]) <= 4 * BLOCK
            as_, ae, bs, be = as_[keep], ae[keep], bs[keep], be[keep]
        a0 = max(0, int(as_.min()) - MARGIN)
        a1 = min(int(ntok[a]), int(ae.max()) + MARGIN, a0 + MAXREG)
        b0 = max(0, int(bs.min()) - MARGIN)
        b1 = min(int(ntok[b]), int(be.max()) + MARGIN, b0 + MAXREG)
        x = tok.doc(a)[a0:a1]
        y = tok.doc(b)[b0:b1]
        best, xi, xe, yj, ye, hits, cols = smith_waterman(x, y)
        rows.append((a, b, e - s, best, a0 + xi, a0 + xe, b0 + yj, b0 + ye, hits, cols))
    return pl.DataFrame(rows, schema=ALIGN_SCHEMA, orient="row")


def null_alignments(tok: Tokens, docs: pl.DataFrame, exclude: set[tuple[int, int]]) -> pl.DataFrame:
    """Ausrichtungen zufälliger Paare ohne Kandidatenbezug: wie hoch kommt der Wert ohne Übernahme?

    Gezogen werden Paare aus einem Düsseldorfer Dokument und einem beliebigen anderen, beide mit
    mindestens NULL_LEN Wörtern, kein Kandidatenpaar; je Seite ein zufälliger Ausschnitt von NULL_LEN
    Wörtern. Der Wert misst gemeinsame Floskeln und Zufall, nicht Übernahme.
    """
    rng = np.random.default_rng(SEED + 1)
    ntok = tok.ntok()
    long_docs = np.flatnonzero(ntok >= NULL_LEN)
    dus = np.asarray(
        [d for d in long_docs.tolist() if docs["korpus"][d] in ("dus-2014", "dus-2020", "dus-2025")]
    )
    rows: list[tuple[int, ...]] = []
    while len(rows) < NULL_PAIRS:
        a = int(rng.choice(dus))
        b = int(rng.choice(long_docs))
        if a == b or (min(a, b), max(a, b)) in exclude:
            continue
        sa = int(rng.integers(0, ntok[a] - NULL_LEN + 1))
        sb = int(rng.integers(0, ntok[b] - NULL_LEN + 1))
        best, xi, xe, yj, ye, hits, cols = smith_waterman(
            tok.doc(a)[sa : sa + NULL_LEN], tok.doc(b)[sb : sb + NULL_LEN]
        )
        rows.append((a, b, 0, best, sa + xi, sa + xe, sb + yj, sb + ye, hits, cols))
    return pl.DataFrame(rows, schema=ALIGN_SCHEMA, orient="row")


# ================================================================================================
# Merkmale und Art einer Übernahme
# ================================================================================================
TITLE_STOP = frozenset(
    "der die das und zur zum zu von vom des den dem in im an am auf für mit über bei aus nach "
    "antrag anfrage änderungsantrag ratsfraktion fraktion fraktionen ratsfraktionen hier "
    "vorlage stadtbezirk bezirksvertretung herr herrn frau cdu spd fdp grüne grünen bündnis "
    "90 linke afd volt partei klima tierschutz freie wähler sowie bzw ein eine einer".split()
)
REF_TAIL = re.compile(r"([/-](ÄA|AW|VSP|NF|DS|ÄA-\d+|AW-\d+|VSP-\d+|NF-\d+|\d{1,2}))+$")


def title_words(title: str | None) -> set[str]:
    return {w for w in TOKEN.findall((title or "").lower()) if w not in TITLE_STOP and len(w) > 2}


def base_reference(ref: str | None) -> str:
    """Drucksachennummer ohne Nachtrag (`X/1`, `-01`, `-ÄA-002`, `-NF-01`)."""
    ref = re.sub(r"\s+", "", ref or "")
    if ref.count("/") >= 3:  # Düsseldorf: KÜRZEL/NR/JAHR/NACHTRAG
        ref = ref.rsplit("/", 1)[0]
    return REF_TAIL.sub("", ref)


def flatten(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def mentions(flat_text: str, ref: str | None) -> bool:
    """Nennt der (geplättete) Text die Drucksachennummer (Leerzeichen, Groß-/Kleinschreibung egal)?"""
    if not ref or len(ref) < 6:
        return False
    return flatten(ref) in flat_text


ART_POLITISCH = ("musterantrag", "fraktionsuebergreifend")
ARTEN = (
    "musterantrag",
    "fraktionsuebergreifend",
    "eigene_wiederholung",
    "verfahrenszitat",
    "baustein",
    "rechtszitat",
    "andere_quelle",
    "zufall",
)


def features(al: pl.DataFrame, docs: pl.DataFrame, tok: Tokens, df: I64) -> pl.DataFrame:
    """Je Ausrichtung: Längen, Anteile, Häufigkeit der Stelle, Rechtsmarken, Verweis, Titelnähe."""
    texts = docs.get_column("text").to_list()
    names = docs.get_column("name").to_list()
    refs = docs.get_column("reference").to_list()
    cities = docs.get_column("stadt").to_list()
    ntok = tok.ntok()

    def span(d: int, s: int, e: int) -> str:
        if e <= s:
            return ""
        o = int(tok.off[d])
        return texts[d][int(tok.start[o + s]) : int(tok.end[o + e - 1])]

    flat_memo: dict[int, str] = {}

    def flat(d: int) -> str:
        v = flat_memo.get(d)
        if v is None:
            v = flatten(texts[d] + " " + (names[d] or ""))
            flat_memo[d] = v
        return v

    rows = []
    for r in al.iter_rows(named=True):
        a, b = r["a"], r["b"]
        av, ab_ = r["a_von"], r["a_bis"]
        la, lb = ab_ - av, r["b_bis"] - r["b_von"]
        o = int(tok.sh_off[a])
        seg = df[o + av : o + max(av, ab_ - K + 1)]
        passage = span(a, av, ab_).lower()
        context = (
            span(a, max(0, av - 20), av).lower()
            + " "
            + span(b, max(0, r["b_von"] - 20), r["b_von"]).lower()
        )
        n_legal = len(LEGAL.findall(passage))
        # Kern: Tokens der Stelle, die in keiner Floskel liegen
        o_a = int(tok.off[a])
        base = int(tok.start[o_a + av]) if ab_ > av else 0
        covered = np.zeros(len(passage), dtype=bool)
        for fm in FLOSKEL.finditer(passage):
            covered[fm.start() : fm.end()] = True
        tok_pos = tok.start[o_a + av : o_a + ab_] - base
        kern = int((~covered[np.clip(tok_pos, 0, max(len(passage) - 1, 0))]).sum()) if la else 0
        link = cities[a] == cities[b] and (
            base_reference(refs[a]) == base_reference(refs[b])
            or mentions(flat(b), refs[a])
            or mentions(flat(a), refs[b])
        )
        ta, tb = title_words(names[a]), title_words(names[b])
        rows.append(
            (
                la,
                lb,
                la / max(int(ntok[a]), 1),
                lb / max(int(ntok[b]), 1),
                float(np.median(seg)) if len(seg) else 0.0,
                n_legal,
                100 * n_legal / max(la, 1),
                len(LEGAL.findall(context)),
                link,
                len(ta & tb) / len(ta | tb) if ta | tb else 0.0,
                kern,
            )
        )
    feat = pl.DataFrame(
        rows,
        schema={
            "la": pl.Int64,
            "lb": pl.Int64,
            "anteil_a": pl.Float64,
            "anteil_b": pl.Float64,
            "df_median": pl.Float64,
            "recht": pl.Int64,
            "recht_100": pl.Float64,
            "recht_kontext": pl.Int64,
            "verweis": pl.Boolean,
            "titel_nah": pl.Float64,
            "kern": pl.Int64,
        },
        orient="row",
    )
    meta = (
        docs.drop("text", "file_name").with_row_index("i").with_columns(pl.col("i").cast(pl.Int64))
    )
    side_a = meta.rename({c: f"{c}_a" for c in meta.columns if c != "i"})
    side_b = meta.rename({c: f"{c}_b" for c in meta.columns if c != "i"})
    return (
        pl.concat([al, feat], how="horizontal")
        .with_columns((pl.col("treffer") / pl.col("spalten")).alias("identitaet"))
        .join(side_a, left_on="a", right_on="i", how="left")
        .join(side_b, left_on="b", right_on="i", how="left")
        .sort("a", "b")
    )


def classify(feat: pl.DataFrame) -> pl.DataFrame:
    """Art der Übernahme nach der Regel aus 23-textuebernahme.md, § 3.4, und die Grenze des Paars.

    Die Reihenfolge zählt und folgt dem Vorrang des Codebuchs: ein Verweis (gleicher Vorgang) schlägt
    alles, dann Rechtszitat (dichte Rechtsmarken), dann Baustein (häufige Stelle oder nur Floskeln),
    dann die Urheber. `politisch_ohne_partei` ist kein
    Code des Codebuchs: zwei politische Dokumente, bei einem fehlt die Partei.
    """
    pol_a = pl.col("urheber_a").is_in(["Politik"])
    pol_b = pl.col("urheber_b").is_in(["Politik"])
    open_a = pl.col("urheber_a").is_in(["Politik", "unbekannt"])
    open_b = pl.col("urheber_b").is_in(["Politik", "unbekannt"])
    adm = (pl.col("urheber_a") == "Verwaltung") & (pl.col("urheber_b") == "Verwaltung")
    known = (pl.col("parteien_a").list.len() > 0) & (pl.col("parteien_b").list.len() > 0)
    same = pl.col("parteien_a").list.set_intersection("parteien_b").list.len() > 0
    city = pl.col("stadt_a") != pl.col("stadt_b")
    period = pl.col("periode_a") != pl.col("periode_b")
    body = pl.col("gremium_a").fill_null("?") != pl.col("gremium_b").fill_null("?")
    art = (
        pl.when(pl.col("verweis"))
        .then(pl.lit("verfahrenszitat"))
        .when(pl.col("recht_100") >= LEGAL_PER_100)
        .then(pl.lit("rechtszitat"))
        .when((pl.col("df_median") >= FREQ_DOCS) | (pl.col("kern") < MIN_ALIGNED))
        .then(pl.lit("baustein"))
        .when(pol_a & pol_b & known & same)
        .then(
            pl.when(city | period | body)
            .then(pl.lit("musterantrag"))
            .otherwise(pl.lit("eigene_wiederholung"))
        )
        .when(pol_a & pol_b & known & ~same)
        .then(pl.lit("fraktionsuebergreifend"))
        .when(city)
        .then(
            pl.when(pl.col("recht") + pl.col("recht_kontext") >= 1)
            .then(pl.lit("rechtszitat"))
            .otherwise(pl.lit("andere_quelle"))
        )
        .when(adm)
        .then(
            pl.when(pl.col("titel_nah") >= 0.3)
            .then(pl.lit("eigene_wiederholung"))
            .otherwise(pl.lit("baustein"))
        )
        .when(open_a & open_b)
        .then(pl.lit("politisch_ohne_partei"))
        .otherwise(pl.lit("andere_quelle"))
    )
    grenze = (
        pl.when(city)
        .then(pl.lit("Stadt"))
        .when(period)
        .then(pl.lit("Periode"))
        .when(body)
        .then(pl.lit("Gremium"))
        .otherwise(pl.lit("keine"))
    )
    return feat.with_columns(art.alias("art"), grenze.alias("grenze"))


# Drucksachennummern im Titel und Textanfang (Düsseldorfer Formen); zwei Anträge, die beide auf
# dieselbe dritte Drucksache zielen („Änderungsantrag … zur Vorlage OVA/103/2020"), zitieren deren
# Text im selben Verfahren.
REF_IN_TEXT = re.compile(r"\b(?:[a-zäöü]{2,6}\d{0,2}/\s?\d{2,3}/\d{4}|\d{2,3}/\s*\d{1,3}/\d{4})\b")
AMENDMENT = re.compile(r"änderungs|ergänzungs|zusatzantrag|begleitantrag|\bäa\b")
AMENDMENT_DAYS = 90  # ein Änderungsantrag einer anderen Fraktion in diesem Abstand zitiert meist
HEAD_TOKENS = 40  # beginnt die Stelle in beiden Dokumenten so früh, liegt sie im Briefkopf
FAMILY_SHARE = 0.5  # ein Dokument trägt die Stelle, wenn es die Hälfte ihrer Shingles hat
FAMILY_MAX = 2  # mehr Träger mit verschiedenen Titeln: Formular, kein Antragstext
TITLE_SAME = 0.2  # mittlere Titelnähe der Träger, ab der sie dieselbe Sache behandeln


class ShingleIndex:
    """Sortierter Index Shingle -> Dokument über alle Korpora, für die Träger einer Stelle."""

    def __init__(self, tok: Tokens) -> None:
        nsh = tok.nsh()
        self.tok = tok
        self.order = np.argsort(tok.sh, kind="stable")
        self.keys = tok.sh[self.order]
        self.doc_of = np.repeat(np.arange(len(nsh), dtype=np.int64), nsh)

    def carriers(self, d: int, s: int, e: int) -> I64:
        """Dokumente, die mindestens FAMILY_SHARE der verschiedenen Shingles der Stelle tragen."""
        o = int(self.tok.sh_off[d])
        own = np.unique(self.tok.sh[o + s : o + max(s, e - K + 1)])
        if own.size == 0:
            return np.empty(0, dtype=np.int64)
        lo = np.searchsorted(self.keys, own, side="left")
        hi = np.searchsorted(self.keys, own, side="right")
        docs = np.concatenate([self.doc_of[self.order[x:y]] for x, y in zip(lo, hi, strict=True)])
        tags = np.repeat(np.arange(own.size), hi - lo)
        pairs = np.unique(docs * own.size + tags)
        cand, counts = np.unique(pairs // own.size, return_counts=True)
        return cand[counts >= FAMILY_SHARE * own.size]


def refine(
    feat: pl.DataFrame, tok: Tokens, docs: pl.DataFrame, index: ShingleIndex
) -> pl.DataFrame:
    """Zweiter Durchgang für die politischen Arten, nach Sichtung von 25 Beispielen (§ 3.5):

    1. Zielen beide Dokumente auf dieselbe dritte Drucksache (Titel oder Textanfang), ist es ein
       Zitat im selben Verfahren.
    2. Über Fraktionsgrenzen: ist eines der beiden ein Änderungs-, Ergänzungs- oder Begleitantrag
       und liegen beide höchstens AMENDMENT_DAYS auseinander, ist es ein Zitat im selben Verfahren.
    3. Tragen mehr als FAMILY_MAX Dokumente die Stelle und behandeln sie verschiedene Sachen
       (mittlere Titelnähe zum ersten Dokument unter TITLE_SAME), ist die Stelle ein Formular;
       ebenso, wenn sie in beiden Dokumenten in den ersten HEAD_TOKENS Wörtern beginnt und die
       Titel verschieden sind (Briefkopf).
    """
    types = docs.get_column("paper_type").to_list()
    dates = docs.get_column("date").to_list()

    def amendment(d: int) -> bool:
        return bool(AMENDMENT.search(((names[d] or "") + " " + (types[d] or "")).lower()))

    def days(a: int, b: int) -> int:
        try:
            da = dt.date.fromisoformat((dates[a] or "")[:10])
            db = dt.date.fromisoformat((dates[b] or "")[:10])
        except ValueError:
            return 10**6
        return abs((da - db).days)

    names = docs.get_column("name").to_list()
    refs = docs.get_column("reference").to_list()
    texts = docs.get_column("text").to_list()
    political = (*ART_POLITISCH, "politisch_ohne_partei")
    rows = feat.with_row_index("_r").filter(pl.col("art").is_in(political))
    updates: dict[int, tuple[str, int, float]] = {}
    for r in rows.iter_rows(named=True):
        a, b = r["a"], r["b"]
        own = {flatten(refs[a] or ""), flatten(refs[b] or "")}

        def cited(d: int, own: set[str] = own) -> set[str]:
            head = ((names[d] or "") + " " + texts[d][:1000]).lower()
            return {flatten(m) for m in REF_IN_TEXT.findall(head)} - own

        carriers = index.carriers(a, r["a_von"], r["a_bis"])
        ta = title_words(names[a])
        others = [c for c in carriers.tolist() if c != a]
        same_matter = (
            float(
                np.mean(
                    [
                        len(ta & title_words(names[c])) / len(ta | title_words(names[c]))
                        if ta | title_words(names[c])
                        else 0.0
                        for c in others
                    ]
                )
            )
            if others
            else 1.0
        )
        art = r["art"]
        if cited(a) & cited(b):
            art = "verfahrenszitat"
        elif (
            art != "musterantrag"
            and (amendment(a) or amendment(b))
            and r["stadt_a"] == r["stadt_b"]
            and days(a, b) <= AMENDMENT_DAYS
        ):
            art = "verfahrenszitat"
        elif len(carriers) > FAMILY_MAX and same_matter < TITLE_SAME:
            art = "baustein"
        elif r["a_von"] < HEAD_TOKENS and r["b_von"] < HEAD_TOKENS and r["titel_nah"] < 0.5:
            art = "baustein"
        updates[r["_r"]] = (art, len(carriers), same_matter)
    idx = list(updates)
    patch = pl.DataFrame(
        {
            "_r": idx,
            "art_neu": [updates[i][0] for i in idx],
            "traeger": [updates[i][1] for i in idx],
            "traeger_titelnah": [updates[i][2] for i in idx],
        },
        schema={
            "_r": pl.UInt32,
            "art_neu": pl.String,
            "traeger": pl.Int64,
            "traeger_titelnah": pl.Float64,
        },
    )
    return (
        feat.with_row_index("_r")
        .join(patch, on="_r", how="left")
        .with_columns(pl.coalesce("art_neu", "art").alias("art"))
        .drop("_r", "art_neu")
    )


def kinds(
    al: pl.DataFrame, docs: pl.DataFrame, tok: Tokens, df: I64, index: ShingleIndex
) -> pl.DataFrame:
    """Merkmale, Art nach der Regel und zweiter Durchgang: die eine Stelle, an der die Art entsteht."""
    return refine(classify(features(al, docs, tok, df)), tok, docs, index)


def confirmed(feat: pl.DataFrame, threshold: int) -> pl.Expr:
    """Eine Übernahme im weiten Sinn: Wert ab der Zufallsgrenze und beide Seiten MIN_ALIGNED Wörter."""
    return (pl.col("wert") >= threshold) & (pl.min_horizontal("la", "lb") >= MIN_ALIGNED)


# ================================================================================================
# Familien
# ================================================================================================
def families(reuse: pl.DataFrame, docs: pl.DataFrame) -> pl.DataFrame:
    """Zusammenhangskomponenten über die politischen Übernahmen; je Familie Größe und Grenzen."""
    pol = reuse.filter(pl.col("art").is_in(ART_POLITISCH))
    if pol.height == 0:
        return pl.DataFrame()
    nodes = np.unique(np.concatenate([pol["a"].to_numpy(), pol["b"].to_numpy()]))
    index = {int(n): i for i, n in enumerate(nodes)}
    ea = np.asarray([index[int(x)] for x in pol["a"]], dtype=np.int64)
    eb = np.asarray([index[int(x)] for x in pol["b"]], dtype=np.int64)
    graph = coo_matrix((np.ones(len(ea)), (ea, eb)), shape=(len(nodes), len(nodes)))
    _, labels = connected_components(graph, directed=False)
    member = pl.DataFrame({"doc": nodes.astype(np.int64), "familie": labels.astype(np.int64)})
    meta = (
        docs.select("stadt", "periode", "parteien", "gremium", "id")
        .with_row_index("doc")
        .with_columns(pl.col("doc").cast(pl.Int64))
    )
    edge_fam = pol.with_columns(
        pl.Series("familie", labels[ea].astype(np.int64)),
    )
    cross_party = edge_fam.group_by("familie").agg(
        (pl.col("art") == "fraktionsuebergreifend").sum().alias("kanten_partei"),
        pl.len().alias("kanten"),
    )
    return (
        member.join(meta, on="doc", how="left")
        .group_by("familie")
        .agg(
            pl.len().alias("dokumente"),
            pl.col("stadt").n_unique().alias("staedte"),
            pl.col("periode").n_unique().alias("perioden"),
            pl.col("gremium").n_unique().alias("gremien"),
            pl.col("parteien")
            .list.explode(keep_nulls=False, empty_as_null=False)
            .unique()
            .sort()
            .alias("parteien"),
            pl.col("id").sort().first().alias("erste_id"),
        )
        .join(cross_party, on="familie", how="left")
        .sort("dokumente", "erste_id", descending=[True, False])
    )


# ================================================================================================
# Gegenprobe: erschöpfende Suche über seltene Shingles für eine Zufallsauswahl
# ================================================================================================
def exhaustive_partners(
    tok: Tokens, df: I64, sample: npt.NDArray[np.int64], scope_ok: Any, min_shared: int
) -> list[tuple[int, int, int]]:
    """Für jedes Dokument der Auswahl alle Partner mit mindestens min_shared gemeinsamen seltenen
    Shingles, über einen invertierten Index (keine LSH); Paare (kleiner, größer, gemeinsame)."""
    nsh = tok.nsh()
    doc_of = np.repeat(np.arange(len(nsh), dtype=np.int64), nsh)
    rare = df <= DF_MAX
    order = np.argsort(tok.sh, kind="stable")
    keys = tok.sh[order]
    out: list[tuple[int, int, int]] = []
    for d in sample.tolist():
        own = tok.shingles(d)[rare[tok.sh_off[d] : tok.sh_off[d + 1]]]
        own = np.unique(own)
        if own.size == 0:
            continue
        lo = np.searchsorted(keys, own, side="left")
        hi = np.searchsorted(keys, own, side="right")
        partners = np.concatenate([doc_of[order[x:y]] for x, y in zip(lo, hi, strict=True)])
        # je Partner: Zahl der verschiedenen gemeinsamen Shingles (ein Shingle kann im Partner
        # mehrfach stehen, darum über (Shingle, Partner) eindeutig)
        sh_rep = np.repeat(own, (hi - lo))
        pair = np.unique(partners.astype(np.uint64) << np.uint64(32) | sh_rep.astype(np.uint64))
        cand, counts = np.unique((pair >> np.uint64(32)).astype(np.int64), return_counts=True)
        for c, n in zip(cand.tolist(), counts.tolist(), strict=True):
            if c != d and n >= min_shared and scope_ok(d, c):
                out.append((min(d, c), max(d, c), n))
    return sorted(set(out))


def align_by_shared(tok: Tokens, df: I64, pairs: Sequence[tuple[int, int, int]]) -> pl.DataFrame:
    """Ausrichtung je Paar über den Bereich der gemeinsamen seltenen Shingles (für die Gegenprobe)."""
    rare = df <= DF_MAX
    ntok = tok.ntok()
    rows: list[tuple[int, ...]] = []
    for a, b, _n in pairs:
        sa, sb = tok.shingles(a), tok.shingles(b)
        ra = rare[tok.sh_off[a] : tok.sh_off[a + 1]]
        rb = rare[tok.sh_off[b] : tok.sh_off[b + 1]]
        pa = np.flatnonzero(np.isin(sa, sb[rb]) & ra)
        pb = np.flatnonzero(np.isin(sb, sa[ra]) & rb)
        if pa.size == 0 or pb.size == 0:
            continue
        a0 = max(0, int(pa.min()) - MARGIN)
        a1 = min(int(ntok[a]), int(pa.max()) + K + MARGIN, a0 + MAXREG)
        b0 = max(0, int(pb.min()) - MARGIN)
        b1 = min(int(ntok[b]), int(pb.max()) + K + MARGIN, b0 + MAXREG)
        best, xi, xe, yj, ye, hits, cols = smith_waterman(tok.doc(a)[a0:a1], tok.doc(b)[b0:b1])
        rows.append((a, b, 0, best, a0 + xi, a0 + xe, b0 + yj, b0 + ye, hits, cols))
    return pl.DataFrame(rows, schema=ALIGN_SCHEMA, orient="row")


# ================================================================================================
# Stichprobe und Kodieraufgaben
# ================================================================================================
# Schichten: (Art des Verfahrens, gezogene Paare). Dicht bei den politischen Arten, an denen das
# Kriterium hängt; die übrigen Arten prüfen, ob das Verfahren sie richtig ausschließt, und die
# Schicht `unter_schwelle` prüft die Zufallsgrenze.
STRATA: tuple[tuple[str, int], ...] = (
    ("musterantrag", 30),
    ("fraktionsuebergreifend", 30),
    ("eigene_wiederholung", 6),
    ("verfahrenszitat", 6),
    ("baustein", 6),
    ("rechtszitat", 6),
    ("andere_quelle", 4),
    ("politisch_ohne_partei", 4),
    ("unter_schwelle", 8),
)


def sample_pairs(feat: pl.DataFrame, threshold: int) -> pl.DataFrame:
    """Geschichtete Stichprobe von SAMPLE_SIZE Paaren mit festem Seed; Reihenfolge gemischt.

    In den politischen Schichten kommen zuerst alle Paare über Stadtgrenzen (es sind wenige), der
    Rest wird nach Grenze proportional gezogen, damit Periode und Gremium beide vertreten sind.
    """
    rng = np.random.default_rng(SEED)
    ok = feat.filter(confirmed(feat, threshold))
    below = feat.filter(~confirmed(feat, threshold) & (pl.col("wert") >= 10))
    chosen: list[pl.DataFrame] = []
    for art, take in STRATA:
        pool = (
            below.with_columns(pl.lit("unter_schwelle").alias("art"))
            if art == "unter_schwelle"
            else ok.filter(pl.col("art") == art)
        ).sort("a", "b")
        population = pool.height
        if population == 0:
            continue
        picked: list[pl.DataFrame] = []
        if art in ART_POLITISCH:
            city = pool.filter(pl.col("grenze") == "Stadt")
            picked.append(city.head(take))
            rest = pool.filter(pl.col("grenze") != "Stadt")
            left = max(0, take - min(take, city.height))
            groups = rest.partition_by("grenze", maintain_order=True, as_dict=True)
            sizes = {k[0]: g.height for k, g in groups.items()}
            total = sum(sizes.values())
            quota = {k: round(left * n / total) for k, n in sizes.items()} if total else {}
            while total and sum(quota.values()) != left:
                key = max(sizes, key=lambda k: sizes[k] - quota[k] * total / left)
                quota[key] += 1 if sum(quota.values()) < left else -1
            for (k,), g in sorted(groups.items()):
                n = min(quota.get(k, 0), g.height)
                if n:
                    rows = np.sort(rng.choice(g.height, size=n, replace=False))
                    picked.append(g[rows.tolist()])
        else:
            n = min(take, population)
            rows = np.sort(rng.choice(population, size=n, replace=False))
            picked.append(pool[rows.tolist()])
        part = pl.concat(picked).with_columns(
            pl.format("{}|{}", pl.col("art"), pl.col("grenze")).alias("schicht")
        )
        sizes_all = (
            pool.group_by("grenze").agg(pl.len().alias("grundgesamtheit"))
            if art in ART_POLITISCH
            else pl.DataFrame({"grenze": part["grenze"].unique(), "grundgesamtheit": population})
        )
        if art not in ART_POLITISCH:
            part = part.with_columns(
                pl.lit(art).alias("schicht"), pl.lit(population).alias("grundgesamtheit")
            )
        else:
            part = part.join(sizes_all, on="grenze", how="left")
        chosen.append(part)
    sample = pl.concat(chosen, how="diagonal_relaxed")
    order = rng.permutation(sample.height)
    sample = sample[order.tolist()].with_columns(
        pl.format("p{}", pl.int_range(1, sample.height + 1).cast(pl.String).str.zfill(3)).alias(
            "paar"
        )
    )
    return sample


def sample_csv(sample: pl.DataFrame) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    cols = ["paar", "id_a", "id_b", "schicht", "grundgesamtheit", "wert", "la", "lb"]
    writer.writerow(cols)
    for row in sample.select(
        "paar",
        pl.col("id_a"),
        pl.col("id_b"),
        "schicht",
        "grundgesamtheit",
        "wert",
        "la",
        "lb",
    ).iter_rows():
        writer.writerow(row)
    return buffer.getvalue()


def excerpt(text: str, start: int, end: int, ctx_start: int, ctx_end: int) -> str:
    """Kontext, die ausgerichtete Stelle in ⟦…⟧, Kontext; Leerraum zusammengezogen."""
    pre = text[ctx_start:start]
    mid = text[start:end]
    post = text[end:ctx_end]
    out = f"{pre}⟦{mid}⟧{post}"
    out = re.sub(r"[ \t\f\r]+", " ", out)
    out = re.sub(r"\n\s*\n+", "\n", out).strip()
    if len(out) > EXCERPT_MAX:
        keep = EXCERPT_MAX // 2
        out = out[:keep] + " […] " + out[-keep:]
    return out


def tasks(
    sample: pl.DataFrame, docs: pl.DataFrame, tok: Tokens, messdaten: Path
) -> list[dict[str, Any]]:
    """Kodieraufgaben ohne die Klassifikation des Verfahrens: Metadaten, Kopf, Stelle mit Kontext."""
    raw: dict[str, str] = {}
    for _code, profile, _stadt, _periode in DUS_PROFILES:
        folder = georep_paths(profile)["profile"]
        path = messdaten / "rohtext" / f"{folder}.parquet"
        if path.exists():
            frame = pl.read_parquet(path, columns=["name", "text"])
            raw.update(zip(frame["name"].to_list(), frame["text"].to_list(), strict=True))
    texts = docs.get_column("text").to_list()
    files = docs.get_column("file_name").to_list()
    codebook = tomllib.loads(CODEBOOK.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for row in sample.iter_rows(named=True):
        entry: dict[str, Any] = {
            "vorhaben": "23-textuebernahme",
            "paar": row["paar"],
            "codebuch": "validierung/23-textuebernahme/codebuch.toml",
            "fragen": {f["name"]: f["optionen"] for f in codebook["fragen"]},
        }
        for side in ("a", "b"):
            d = int(row[side])
            o = int(tok.off[d])
            n = int(tok.ntok()[d])
            s, e = int(row[f"{side}_von"]), int(row[f"{side}_bis"])
            text = texts[d]
            cs = int(tok.start[o + max(0, s - EXCERPT_CONTEXT)]) if n else 0
            ce = int(tok.end[o + min(n, e + EXCERPT_CONTEXT) - 1]) if n else 0
            head_src = raw.get(files[d] or "", "") or text
            entry[side] = {
                "id": row[f"id_{side}"],
                "stadt": row[f"stadt_{side}"],
                "periode": row[f"periode_{side}"] or None,
                "drucksache": row[f"reference_{side}"],
                "titel": row[f"name_{side}"],
                "datum": row[f"date_{side}"],
                "art": row[f"paper_type_{side}"],
                "gremium": row[f"gremium_{side}"],
                "kopf": re.sub(r"\s+", " ", head_src[:HEAD]).strip(),
                "kopf_quelle": "rohtext" if files[d] in raw else "korpustext",
                "stelle": excerpt(
                    text,
                    int(tok.start[o + s]) if e > s else 0,
                    int(tok.end[o + e - 1]) if e > s else 0,
                    cs,
                    ce,
                ),
                "woerter_stelle": e - s,
                "woerter_dokument": n,
            }
        out.append(entry)
    return out


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    share = hits / n
    centre = (share + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(share * (1 - share) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


# ================================================================================================
# Ausgabe
# ================================================================================================
def pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f} %".replace(".", ",")


def num(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def show(frame: pl.DataFrame, rows: int = 60) -> None:
    with pl.Config(
        tbl_rows=rows,
        tbl_cols=30,
        tbl_width_chars=220,
        fmt_str_lengths=90,
        tbl_hide_dataframe_shape=True,
        tbl_hide_column_data_types=True,
    ):
        print(frame)


def stamp() -> dict[str, Any]:
    return {
        "CAP": CAP,
        "K": K,
        "BLOCK": BLOCK,
        "MIN_SH": MIN_SH,
        "N_PERM": N_PERM,
        "BANDS": BANDS,
        "ROWS": ROWS,
        "MAXDOC": MAXDOC,
        "DF_MAX": DF_MAX,
        "MIN_RARE": MIN_RARE,
        "SEED": SEED,
        "MARGIN": MARGIN,
        "MAXREG": MAXREG,
        "SCORES": [MATCH, MISMATCH, GAP],
        "NULL": [NULL_PAIRS, NULL_LEN],
        "MIN_SHARED": MIN_SHARED,
        "version": 2,
    }


@dataclass
class Prepared:
    docs: pl.DataFrame
    tok: Tokens
    df: I64
    win: Windows
    cand: Candidates
    align: pl.DataFrame
    null: pl.DataFrame
    seconds: dict[str, float]
    raw_window_pairs: int  # Fensterpaare aus LSH vor dem Vorfilter
    raw_doc_pairs: int  # Dokumentpaare aus LSH vor dem Vorfilter


def prepare(cache: Path, cherif: Path, fresh: bool) -> Prepared:
    """Korpora laden, Tokens, Dokumenthäufigkeit, Fenster, LSH, Ausrichtung; mit Zwischenablage."""
    cache.mkdir(parents=True, exist_ok=True)
    stamp_file = cache / "stamp.json"
    same = stamp_file.exists() and json.loads(stamp_file.read_text()) == stamp()
    seconds: dict[str, float] = {}
    t = time.perf_counter()
    if same and not fresh and (cache / "docs.parquet").exists():
        docs = pl.read_parquet(cache / "docs.parquet")
    else:
        same = False
        f15 = regelwerk_15()
        docs = pl.concat([load_dus(f15), load_cherif(cherif)])
        docs.write_parquet(cache / "docs.parquet")
    seconds["Laden"] = time.perf_counter() - t
    t = time.perf_counter()
    if same and (cache / "tokens.npz").exists():
        z = np.load(cache / "tokens.npz")
        tok = Tokens(
            ids=z["ids"],
            start=z["start"],
            end=z["end"],
            off=z["off"],
            sh=z["sh"],
            sh_off=z["sh_off"],
            vocab_size=int(z["vocab"][0]),
        )
        df = z["df"]
    else:
        tok = tokenize(docs.get_column("text").to_list())
        df = shingle_df(tok)
        np.savez(
            cache / "tokens.npz",
            ids=tok.ids,
            start=tok.start,
            end=tok.end,
            off=tok.off,
            sh=tok.sh,
            sh_off=tok.sh_off,
            vocab=np.array([tok.vocab_size]),
            df=df,
        )
    seconds["Tokens, Shingles, Häufigkeit"] = time.perf_counter() - t
    t = time.perf_counter()
    win = windows(tok, df)
    code = {k: i for i, k in enumerate(KORPORA)}
    kc = docs.get_column("korpus").replace_strict(code, return_dtype=pl.Int64).to_numpy()
    if same and (cache / "kandidaten.npz").exists():
        z = np.load(cache / "kandidaten.npz")
        cand = Candidates(
            wa=z["wa"],
            wb=z["wb"],
            frequent=z["frequent"],
            active=int(z["meta"][0]),
            buckets_kept=int(z["meta"][1]),
            buckets_frequent=int(z["meta"][2]),
        )
        n_doc_pairs = int(z["meta"][4])
        raw_window_pairs = int(z["meta"][3])
    else:
        raw = lsh(win, kc, kc >= len(DUS_PROFILES))
        cand, n_doc_pairs = filter_candidates(tok, df, win, raw)
        np.savez(
            cache / "kandidaten.npz",
            wa=cand.wa,
            wb=cand.wb,
            frequent=cand.frequent,
            meta=np.array(
                [cand.active, cand.buckets_kept, cand.buckets_frequent, len(raw.wa), n_doc_pairs]
            ),
        )
    if not (same and (cache / "kandidaten.npz").exists()):
        raw_window_pairs = len(raw.wa)
    seconds["Fenster, LSH, Vorfilter"] = time.perf_counter() - t
    t = time.perf_counter()
    if same and (cache / "ausrichtung.parquet").exists():
        align = pl.read_parquet(cache / "ausrichtung.parquet")
        null = pl.read_parquet(cache / "null.parquet")
    else:
        align = align_pairs(tok, win, cand)
        exclude = set(zip(align["a"].to_list(), align["b"].to_list(), strict=True))
        null = null_alignments(tok, docs.select("korpus"), exclude)
        align.write_parquet(cache / "ausrichtung.parquet")
        null.write_parquet(cache / "null.parquet")
    seconds["Ausrichtung"] = time.perf_counter() - t
    stamp_file.write_text(json.dumps(stamp()))
    return Prepared(docs, tok, df, win, cand, align, null, seconds, raw_window_pairs, n_doc_pairs)


def section_data(p: Prepared, cherif: Path) -> None:
    print("\n=== § 2 Datenlage")
    ntok = p.tok.ntok()
    frame = p.docs.select("korpus", "urheber", "parteien").with_columns(
        pl.Series("woerter", ntok),
        pl.Series("text", ntok > 0),
        (pl.col("parteien").list.len() > 0).alias("partei"),
    )
    show(
        frame.group_by("korpus", maintain_order=True).agg(
            pl.len().alias("dokumente"),
            pl.col("text").sum().alias("mit_text"),
            pl.col("woerter").sum().alias("woerter_bis_cap"),
            (pl.col("urheber") == "Politik").sum().alias("politik"),
            ((pl.col("urheber") == "Politik") & pl.col("partei")).sum().alias("politik_mit_partei"),
            (pl.col("urheber") == "Verwaltung").sum().alias("verwaltung"),
            (pl.col("urheber") == "unbekannt").sum().alias("unbekannt"),
            (pl.col("urheber") == "Eingabe").sum().alias("eingabe"),
        )
    )
    files = sorted(cherif.glob("*"))
    total = sum(f.stat().st_size for f in files)
    print(
        f"  Cherif-Korpus: {len(files)} Dateien, {total} Bytes ({total / 1e6:.1f} MB) in {cherif}"
    )
    print(
        f"  Tokens zusammen {len(p.tok.ids)}, Vokabular {p.tok.vocab_size}, Shingles {len(p.tok.sh)}"
    )


def section_candidates(p: Prepared) -> pl.DataFrame:
    print("\n=== § 3.1 Kandidaten (Fenster, MinHash, LSH)")
    rare = p.df <= DF_MAX
    print(
        f"  Shingles {len(p.df)}, davon selten (df <= {DF_MAX}) {int(rare.sum())} = {pct(rare.mean())};"
        f" Fenster {len(p.win.doc)}, aktiv (>= {MIN_RARE} seltene) {p.cand.active}"
        f" = {pct(p.cand.active / len(p.win.doc))}"
    )
    print(
        f"  Eimer mit 2 bis {MAXDOC} Dokumenten und Düsseldorf über alle Bänder: {p.cand.buckets_kept};"
        f" Eimer mit mehr als {MAXDOC} Dokumenten: {p.cand.buckets_frequent}"
    )
    print(
        f"  aus LSH: Fensterpaare {p.raw_window_pairs}, Dokumentpaare {p.raw_doc_pairs};"
        f" mit >= {MIN_SHARED} gemeinsamen seltenen Shingles: Fensterpaare {len(p.cand.wa)},"
        f" Dokumentpaare {p.align.height}"
    )
    pairs = p.align.select("a", "b").with_columns(
        pl.Series("ka", p.docs["korpus"].gather(p.align["a"].to_numpy())),
        pl.Series("kb", p.docs["korpus"].gather(p.align["b"].to_numpy())),
    )
    show(pairs.group_by("ka", "kb").len().sort("ka", "kb"))
    return pairs


def section_alignment(p: Prepared) -> int:
    print("\n=== § 3.2 Ausrichtung und Zufallsgrenze")
    q = np.quantile(p.null["wert"].to_numpy(), [0.5, 0.9, 0.99, 0.995, 0.999])
    print(
        f"  Nullverteilung ({NULL_PAIRS} Zufallspaare, je {NULL_LEN} Wörter): Median {q[0]:.0f},"
        f" 90 % {q[1]:.0f}, 99 % {q[2]:.1f}, 99,5 % {q[3]:.1f}, 99,9 % {q[4]:.1f},"
        f" Maximum {p.null['wert'].max()}"
    )
    show(p.null.group_by("wert").len().sort("wert").filter(pl.col("wert") >= 8))
    texts = p.docs.get_column("text").to_list()
    for r in p.null.sort("wert", descending=True).head(5).iter_rows(named=True):
        o = int(p.tok.off[r["a"]])
        t = texts[r["a"]][int(p.tok.start[o + r["a_von"]]) : int(p.tok.end[o + r["a_bis"] - 1])]
        print(f"   {r['wert']:3d} {r['a_bis'] - r['a_von']:3d} W.: {t[:150]!r}")
    threshold = 20
    print(
        f"  Zufallsgrenze S* = {threshold}: kein Zufallspaar darüber außer Bausteinen (oben); dazu"
        f" mindestens {MIN_ALIGNED} Wörter auf beiden Seiten"
    )
    al = p.align.with_columns(
        (pl.col("a_bis") - pl.col("a_von")).alias("la"),
        (pl.col("b_bis") - pl.col("b_von")).alias("lb"),
    )
    ok = al.filter(confirmed(al, threshold))
    print(
        f"  Kandidatenpaare {al.height}; davon über der Grenze {ok.height} = {pct(ok.height / al.height)}"
    )
    vals = ok.with_columns((pl.col("treffer") / pl.col("spalten")).alias("ident"))
    show(
        vals.select(
            pl.col("wert").quantile(q).alias(f"wert_q{int(q * 100)}") for q in (0.1, 0.5, 0.9)
        )
        .hstack(
            vals.select(
                pl.min_horizontal("la", "lb").quantile(q).alias(f"woerter_q{int(q * 100)}")
                for q in (0.1, 0.5, 0.9)
            )
        )
        .hstack(
            vals.select(
                pl.col("ident").quantile(q).alias(f"ident_q{int(q * 100)}") for q in (0.1, 0.5)
            )
        )
    )
    return threshold


def length_bin() -> pl.Expr:
    w = pl.min_horizontal("la", "lb")
    return (
        pl.when(w < 50)
        .then(pl.lit("a 30-49"))
        .when(w < 100)
        .then(pl.lit("b 50-99"))
        .when(w < 200)
        .then(pl.lit("c 100-199"))
        .otherwise(pl.lit("d 200+"))
        .alias("laenge")
    )


def section_gegenprobe(p: Prepared, threshold: int, index: ShingleIndex) -> None:
    """Recall der Kandidatensuche gegen eine erschöpfende Suche über seltene Shingles."""
    print("\n=== § 3.3 Gegenprobe: erschöpfende Suche über seltene Shingles")
    lsh_pairs = set(zip(p.align["a"].to_list(), p.align["b"].to_list(), strict=True))
    korpus = p.docs.get_column("korpus").to_numpy()
    stadt = p.docs.get_column("stadt").to_numpy()
    urheber = p.docs.get_column("urheber").to_numpy()
    nsh = p.tok.nsh()
    dus = np.flatnonzero(np.isin(korpus, ["dus-2014", "dus-2020", "dus-2025"]) & (nsh >= MIN_SH))
    rng = np.random.default_rng(SEED + 2)
    sample = np.sort(rng.choice(dus, size=400, replace=False))
    cherif_codes = {c for c, _ in CHERIF_CITIES}

    def any_scope(d: int, c: int) -> bool:
        return not (korpus[d] in cherif_codes and korpus[c] in cherif_codes)

    for label, docs_, scope in (
        ("400 zufällige Düsseldorfer Dokumente, Partner überall", sample, any_scope),
        (
            "alle politischen Düsseldorfer Dokumente, Partner in anderen Städten",
            np.flatnonzero(
                np.isin(korpus, ["dus-2014", "dus-2020", "dus-2025"]) & (urheber == "Politik")
            ),
            lambda d, c: stadt[c] != stadt[d],
        ),
    ):
        t = time.perf_counter()
        pairs = exhaustive_partners(p.tok, p.df, docs_, scope, min_shared=5)
        al = align_by_shared(p.tok, p.df, pairs)
        feat = kinds(al, p.docs, p.tok, p.df, index)
        ok = feat.filter(confirmed(feat, threshold))
        found = ok.with_columns(
            pl.Series(
                "lsh",
                [(a, b) in lsh_pairs for a, b in zip(ok["a"], ok["b"], strict=True)],
                dtype=pl.Boolean,
            ),
            length_bin(),
            (pl.col("art") == "baustein").alias("ist_baustein"),
        )
        print(
            f"  {label}: {len(docs_)} Dokumente, {len(pairs)} Paare mit >= 5 gemeinsamen seltenen"
            f" Shingles, {ok.height} über der Grenze ({time.perf_counter() - t:.0f} s)"
        )
        if ok.height == 0:
            continue
        print("  Recall der Kandidatensuche je Art (Art nach derselben Regel):")
        show(
            found.group_by("art")
            .agg(
                pl.len().alias("paare"),
                pl.col("lsh").sum().alias("lsh"),
                pl.col("lsh").mean().round(3).alias("recall"),
            )
            .sort("art")
        )
        print("  ohne Bausteine, je Länge der kürzeren Seite:")
        show(
            found.filter(~pl.col("ist_baustein"))
            .group_by("laenge")
            .agg(
                pl.len().alias("paare"),
                pl.col("lsh").sum().alias("lsh"),
                pl.col("lsh").mean().round(3).alias("recall"),
            )
            .sort("laenge")
        )
        nb = found.filter(~pl.col("ist_baustein"))
        pol = found.filter(pl.col("art").is_in(ART_POLITISCH))
        print(
            f"  Recall ohne Bausteine {int(nb['lsh'].sum())}/{nb.height}"
            f" = {pct(nb['lsh'].mean()) if nb.height else '-'};"
            f" politische Arten {int(pol['lsh'].sum())}/{pol.height}"
        )


def section_kinds(p: Prepared, threshold: int, index: ShingleIndex) -> pl.DataFrame:
    print("\n=== § 3.4 Was übernommen wird: Art nach der Regel und Grenze")
    feat = kinds(p.align, p.docs, p.tok, p.df, index)
    ok = feat.filter(confirmed(feat, threshold))
    order = [*ARTEN[:-1], "politisch_ohne_partei"]
    table = (
        ok.pivot(on="grenze", index="art", values="a", aggregate_function="len")
        .fill_null(0)
        .with_columns(pl.col("art").replace_strict({a: i for i, a in enumerate(order)}).alias("_o"))
        .sort("_o")
        .drop("_o")
    )
    cols = [c for c in ("keine", "Gremium", "Periode", "Stadt") if c in table.columns]
    show(table.select("art", *cols).with_columns(pl.sum_horizontal(cols).alias("zusammen")))
    print("  über Stadtgrenzen, je Städtepaar:")
    city = ok.filter(pl.col("grenze") == "Stadt").with_columns(
        pl.format("{}–{}", pl.col("korpus_a"), pl.col("korpus_b")).alias("paar")
    )
    if city.height:
        show(
            city.pivot(on="art", index="paar", values="a", aggregate_function="len")
            .fill_null(0)
            .sort("paar")
        )
    print("  Länge (Wörter der kürzeren Seite) und Anteil am späteren Dokument, Median je Art:")
    later_share = (
        pl.when(pl.col("date_a").fill_null("") <= pl.col("date_b").fill_null(""))
        .then(pl.col("anteil_b"))
        .otherwise(pl.col("anteil_a"))
    )
    show(
        ok.group_by("art")
        .agg(
            pl.len().alias("paare"),
            pl.min_horizontal("la", "lb").median().alias("woerter_median"),
            pl.min_horizontal("la", "lb").quantile(0.9).alias("woerter_q90"),
            later_share.median().alias("anteil_spaeteres_median"),
            (later_share >= 0.5).mean().alias("anteil_ueber_haelfte"),
            pl.col("identitaet").median().alias("identitaet_median"),
        )
        .sort("art")
    )
    pol = ok.filter(pl.col("art").is_in(ART_POLITISCH))
    print(
        "  Parteien der politischen Übernahmen (Musterantrag: gemeinsame Partei; über Fraktionsgrenzen: Paar):"
    )
    show(
        pol.filter(pl.col("art") == "musterantrag")
        .with_columns(
            pl.col("parteien_a")
            .list.set_intersection("parteien_b")
            .list.sort()
            .list.join("+")
            .alias("partei")
        )
        .group_by("partei")
        .len()
        .sort("len", descending=True)
        .head(12)
    )
    show(
        pol.filter(pl.col("art") == "fraktionsuebergreifend")
        .with_columns(
            pl.concat_str(
                pl.col("parteien_a").list.sort().list.join("+"),
                pl.lit(" / "),
                pl.col("parteien_b").list.sort().list.join("+"),
            ).alias("parteien")
        )
        .group_by("parteien")
        .len()
        .sort("len", descending=True)
        .head(12)
    )
    print("  Beispiele (je Art bis zu drei, Seed fest):")
    texts = p.docs.get_column("text").to_list()
    for art in ("musterantrag", "fraktionsuebergreifend", "rechtszitat", "baustein"):
        part = ok.filter(pl.col("art") == art).sort("a", "b")
        if part.height == 0:
            continue
        rows = np.random.default_rng(SEED).choice(
            part.height, size=min(3, part.height), replace=False
        )
        for r in part[np.sort(rows).tolist()].iter_rows(named=True):
            o = int(p.tok.off[r["a"]])
            t = texts[r["a"]][int(p.tok.start[o + r["a_von"]]) : int(p.tok.end[o + r["a_bis"] - 1])]
            print(
                f"   [{art}, {r['grenze']}] {r['reference_a']} ({r['korpus_a']}, {r['parteien_a']}) ~"
                f" {r['reference_b']} ({r['korpus_b']}, {r['parteien_b']}), {r['la']} W.,"
                f" Wert {r['wert']}: {re.sub(r'\\s+', ' ', t)[:160]!r}"
            )
    return feat


def section_families(p: Prepared, feat: pl.DataFrame, threshold: int) -> pl.DataFrame:
    print("\n=== § 3.5 Familien über politische Übernahmen")
    ok = feat.filter(confirmed(feat, threshold))
    fam = families(ok, p.docs)
    if fam.height == 0:
        print("  keine")
        return fam
    print(
        f"  Familien {fam.height} mit {int(fam['dokumente'].sum())} Dokumenten;"
        f" Größe 2: {fam.filter(pl.col('dokumente') == 2).height},"
        f" größte {int(fam['dokumente'].max())};"
        f" über Stadtgrenzen {fam.filter(pl.col('staedte') >= 2).height},"
        f" über Parteigrenzen {fam.filter(pl.col('kanten_partei') > 0).height},"
        f" über Periodengrenzen {fam.filter(pl.col('perioden') >= 2).height},"
        f" über Gremiengrenzen {fam.filter(pl.col('gremien') >= 2).height}"
    )
    show(
        fam.select(
            "dokumente", "staedte", "perioden", "gremien", "parteien", "kanten", "kanten_partei"
        ).head(10)
    )
    return fam


def section_sample(
    p: Prepared, feat: pl.DataFrame, threshold: int, write: bool, messdaten: Path
) -> None:
    print("\n=== § 4 Stichprobe und Kodieraufgaben")
    sample = sample_pairs(feat, threshold)
    show(
        sample.group_by("schicht")
        .agg(pl.len().alias("gezogen"), pl.col("grundgesamtheit").first())
        .sort("schicht")
    )
    pol = sample.filter(pl.col("art").is_in(ART_POLITISCH)).height
    for right in (pol - 3, pol - 6):
        lo, hi = wilson(right, pol)
        print(
            f"  Rechenbeispiel: {right} von {pol} politischen Paaren richtig ({pct(right / pol)})"
            f" gäbe ein Wilson-Intervall [{num(lo)}, {num(hi)}]"
        )
    text = sample_csv(sample)
    if write:
        SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
        SAMPLE_CSV.write_text(text, encoding="utf-8")
        target = messdaten / "kodierung" / "23-textuebernahme" / "aufgaben.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = tasks(sample, p.docs, p.tok, messdaten)
        target.write_text(
            "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
            encoding="utf-8",
        )
        print(f"  geschrieben: {SAMPLE_CSV} ({sample.height} Paare), {target}")
    elif SAMPLE_CSV.exists():
        same = SAMPLE_CSV.read_text(encoding="utf-8") == text
        print(f"  Stichprobe im Repo {'gleich der berechneten' if same else 'WEICHT AB'}")
        if not same:
            raise SystemExit(1)
    else:
        print("  keine Stichprobe im Repo; mit --schreiben anlegen")


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--schreiben", action="store_true")
    parser.add_argument("--neu", action="store_true")
    parser.add_argument("--ohne-gegenprobe", action="store_true")
    parser.add_argument("--cherif", type=Path, default=CHERIF)
    parser.add_argument("--messdaten", type=Path, default=MESSDATEN)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    cache = args.messdaten / "23-textuebernahme" / "cache"
    prepared = prepare(cache, args.cherif, args.neu)
    section_data(prepared, args.cherif)
    section_candidates(prepared)
    threshold = section_alignment(prepared)
    index = ShingleIndex(prepared.tok)
    if not args.ohne_gegenprobe:
        section_gegenprobe(prepared, threshold, index)
    feat = section_kinds(prepared, threshold, index)
    section_families(prepared, feat, threshold)
    section_sample(prepared, feat, threshold, args.schreiben, args.messdaten)
    print("\nLaufzeiten:", {k: round(v, 1) for k, v in prepared.seconds.items()})
    print(f"Laufzeit insgesamt {num(time.perf_counter() - started, 1)} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
