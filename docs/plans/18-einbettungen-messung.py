"""Rechnet die Zahlen von `18-einbettungen.md` nach (Vorhaben 18, Stufe 1).

    uv run python docs/plans/18-einbettungen-messung.py --einbetten [--limit N]  # GPU, unter flock
    uv run python docs/plans/18-einbettungen-messung.py                          # Zahlen aus dem Cache
    uv run python docs/plans/18-einbettungen-messung.py --pools                  # Pools für F4 schreiben
    uv run python docs/plans/18-einbettungen-messung.py --auswertung             # nach den Labels

Liest den Korpus der Hauptperiode (`interim/papers.parquet` nach `georep bootstrap && georep
run`), die Rohtext-Messdatei (`$GEOREP_MESSDATEN/rohtext/duesseldorf.parquet`) und die Suchfragen
aus `18-einbettungen-anfragen.toml`. Die Einbettungen kommen über die Naht von F5 (`georep.ml`)
aus dem Modellcache unter `cache_root/ml/`; `--einbetten` rechnet, was dort fehlt (ollama muss
laufen, jeder Lauf unter `flock /media/konrad/xtraspace/georep/gpu-queue/gpu.lock`, mit `--limit`
in Blöcken von höchstens rund 30 Minuten). Ohne `--einbetten` fragt das Skript den Server nur nach
dem Digest des Modells und rechnet nichts auf der GPU.

Alles, was vorab festgelegt ist (Messdokument § 3.1, Festlegungscommit `a38e149`), steht in den
Konstanten unten; das Skript setzt § 3.1 um und ändert nichts daran. Was nicht im Kriterium steht,
heißt im Ausdruck „explorativ". `--auswertung` rechnet nach der Kodierung Kriterium, Intervalle und
Urteil samt Rückfallregel; mit erfundenen Labels in beide Richtungen geprüft (Messdokument § 4.3).

Ausgaben: lokal unter `$GEOREP_MESSDATEN/18-einbettungen/` (Rangfolgen, Nachbarn, Laufzeiten,
Größenproben; nie ins Repo, sie tragen keine Texte, aber sie sind die Ausgabe des Verfahrens und
gehören nicht in die Nähe der Kodierer); mit `--pools` die Grundgesamtheiten der beiden Codebücher
unter `data/<profil>/messung18/` (Schlüssel und Bedarf, kein Ratstext). Stichprobe und Aufträge
schreibt danach `georep validate sample|tasks` (Messdokument § 4).

Unter Fremdlast mit `nice -n 10`, `POLARS_MAX_THREADS=4`, `OMP_NUM_THREADS=2` starten.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import tomllib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("POLARS_MAX_THREADS", "4")
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from scipy import sparse  # noqa: E402

from georep.layout import Layout  # noqa: E402
from georep.ml.base import EmbeddingUse  # noqa: E402
from georep.ml.batch import embed_texts, progress_log  # noqa: E402
from georep.ml.cache import CacheKey, ModelCache, decode_vectors, input_sha256  # noqa: E402
from georep.ml.ollama import client_from_settings, embedder_from_settings  # noqa: E402
from georep.settings import load_settings  # noqa: E402
from georep.validation.measures import ndcg_at_k, wilson_interval  # noqa: E402
from georep.validation.sample import allocate, rank  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
AUS = MESSDATEN / "18-einbettungen"
ANFRAGEN = REPO / "docs" / "plans" / "18-einbettungen-anfragen.toml"
# Ordner der Labels; die Umgebungsvariablen sind nur für die Probe mit erfundenen Labels
V_SUCHE = Path(os.environ.get("V18_SUCHE", REPO / "validierung" / "18-einbettungen"))
V_NACHBARN = Path(os.environ.get("V18_NACHBARN", REPO / "validierung" / "18-einbettungen-nachbarn"))
PROFIL = "duesseldorf"

# --- vorab festgelegt (Messdokument § 3.1, Commit a38e149) ---------------------------------------
SEED = 20261123
TITEL_MAX = 200  # Zeichen des Titels in T(d) und in jedem Stück
STUECK_MAX = 1600  # Titel + Leerzeile + Rumpf eines Stücks, in Zeichen
UEBERLAPPUNG = 200  # Zeichen der letzten Zeilen des vorigen Stücks
DOK_PREFIX = "search_document: "
FRAGE_PREFIX = "search_query: "
PROMPT_STUECKE = "18-stuecke-1"
PROMPT_ANFRAGE = "18-anfrage-1"
K1, B = 1.2, 0.75  # BM25
RRF_K = 60
TIEFE = 100  # Listen, die in die Mischung gehen
POOL = 10  # je Verfahren und Frage geurteilt
ANKER = 50
NACHBARN = 5
ANKER_MIN = 300  # Zeichen Rohtext
DOKVEKTOR_STUECKE = 3
ARTEN_SCHICHTEN = 8  # die häufigsten Dokumentarten als eigene Schicht, der Rest „sonst"
BOOT = 2000
PERM = 10000
SCHWELLE_SUCHE = 0.05
SCHWELLE_NACHBARN = 0.70
TFIDF_TOLERANZ = 0.05
RELEVANZ = ("0", "1", "2")
NACHBAR_LABELS = ("verschieden", "gleiches_thema", "gleiche_sache")
VERFAHREN = ("bm25", "einbettung", "mischung")
# --- explorativ ----------------------------------------------------------------------------------
MATRJOSCHKA = 256
CLUSTER_K = 20
CLUSTER_SEEDS = (0, 1, 2, 3, 4)


def uptime() -> str:
    return Path("/proc/loadavg").read_text().split(" ", 3)[:3].__str__()


def log(*parts: object) -> None:
    print(*parts, flush=True)


# --- Einheiten -----------------------------------------------------------------------------------


def settings_and_layout() -> tuple[Any, Layout]:
    settings = load_settings(cwd=REPO, profile=PROFIL)
    return settings, Layout.from_settings(settings)


def titel_von(name: str | None) -> str:
    return " ".join((name or "").split())[:TITEL_MAX]


def lade_einheiten(layout: Layout, rohtext: Path) -> pl.DataFrame:
    """Je PDF-Datei eine Einheit unter der kleinsten Korpus-ID, nur mit nicht leerem Rohtext."""
    korpus = pl.read_parquet(
        layout.corpus, columns=["id", "name", "reference", "paper_type", "date", "file_name"]
    ).filter(pl.col("file_name").is_not_null() & (pl.col("file_name") != ""))
    roh = (
        pl.read_parquet(rohtext, columns=["name", "text"])
        .rename({"name": "file_name", "text": "roh"})
        .filter(pl.col("roh").str.strip_chars() != "")
    )
    verbunden = korpus.join(roh, on="file_name", how="inner").sort("id")
    ids = verbunden.group_by("file_name").agg(pl.col("id").sort().alias("ids"))
    einheiten = (
        verbunden.unique(subset="file_name", keep="first", maintain_order=True)
        .join(ids, on="file_name", how="left")
        .sort("id")
    )
    return einheiten.with_columns(
        pl.col("name").map_elements(titel_von, return_dtype=pl.String).alias("titel")
    )


def text_von(titel: str, roh: str) -> str:
    return titel + "\n\n" + roh.replace("\f", "\n")


def zeilen_von(roh: str, budget: int) -> list[str]:
    zeilen: list[str] = []
    for zeile in roh.replace("\f", "\n").split("\n"):
        zeile = zeile.rstrip()
        if not zeile.strip():
            continue
        while len(zeile) > budget:
            schnitt = zeile.rfind(" ", 0, budget + 1)
            if schnitt <= 0:
                schnitt = budget
            kopf = zeile[:schnitt].rstrip()
            if kopf.strip():
                zeilen.append(kopf)
            zeile = zeile[schnitt:].lstrip()
        if zeile.strip():
            zeilen.append(zeile)
    return zeilen


def _laenge(zeilen: Sequence[str], start: int, ende: int) -> int:
    return sum(len(z) for z in zeilen[start:ende]) + max(0, ende - start - 1)


def zerteile(titel: str, roh: str) -> list[str]:
    """Fassung 18-stuecke-1: Rümpfe der Stücke (ohne Präfix und Titel), § 3.1."""
    budget = STUECK_MAX - len(titel) - 2
    zeilen = zeilen_von(roh, budget)
    ruempfe: list[str] = []
    start = 0
    while start < len(zeilen):
        ende = start + 1
        while ende < len(zeilen) and _laenge(zeilen, start, ende + 1) <= budget:
            ende += 1
        ruempfe.append("\n".join(zeilen[start:ende]))
        if ende >= len(zeilen):
            break
        neu = ende
        while neu - 1 > start and _laenge(zeilen, neu - 1, ende) <= UEBERLAPPUNG:
            neu -= 1
        while _laenge(zeilen, neu, ende + 1) > budget:
            neu += 1
        start = neu
    return ruempfe


def stueck_text(titel: str, rumpf: str) -> str:
    return DOK_PREFIX + titel + "\n\n" + rumpf


@dataclass(frozen=True)
class Stuecke:
    texte: list[str]
    einheit: np.ndarray  # Index der Einheit je Stück, aufsteigend
    erstes: np.ndarray  # Index des ersten Stücks je Einheit
    anzahl: np.ndarray  # Stücke je Einheit


def alle_stuecke(einheiten: pl.DataFrame) -> Stuecke:
    texte: list[str] = []
    einheit: list[int] = []
    anzahl: list[int] = []
    for i, (titel, roh) in enumerate(zip(einheiten["titel"], einheiten["roh"], strict=True)):
        ruempfe = zerteile(titel, roh)
        texte.extend(stueck_text(titel, r) for r in ruempfe)
        einheit.extend([i] * len(ruempfe))
        anzahl.append(len(ruempfe))
    zahl = np.asarray(anzahl, dtype=np.int64)
    erstes = np.concatenate([[0], np.cumsum(zahl)[:-1]])
    return Stuecke(texte, np.asarray(einheit, dtype=np.int64), erstes, zahl)


# --- Snowball-Stemmer für Deutsch (klassische Fassung, snowballstem.org) -----------------------

_V = frozenset("aeiouyäöü")
_S_ENDE = frozenset("bdfghklmnrt")
_ST_ENDE = frozenset("bdfghklmnt")
_SCHRITT1 = ("ern", "em", "er", "en", "es", "e", "s")
_SCHRITT2 = ("est", "en", "er", "st")
_SCHRITT3 = ("isch", "lich", "heit", "keit", "end", "ung", "ig", "ik")


def _region(w: str, start: int) -> int:
    i = start
    while i < len(w) and w[i] not in _V:
        i += 1
    while i < len(w) and w[i] in _V:
        i += 1
    return min(i + 1, len(w))


def _laengstes(w: str, endungen: Sequence[str]) -> str:
    for endung in sorted(endungen, key=len, reverse=True):
        if w.endswith(endung):
            return endung
    return ""


def stem_de(wort: str) -> str:
    """Der Snowball-Stemmer für Deutsch: Prelude, R1/R2, Schritte 1 bis 3, Postlude."""
    w = list(wort.replace("ß", "ss"))
    for i in range(1, len(w) - 1):
        if w[i] in "uy" and w[i - 1] in _V and w[i + 1] in _V:
            w[i] = w[i].upper()
    s = "".join(w)
    if len(s) < 3:
        r1 = r2 = len(s)
    else:
        roh_r1 = _region(s, 0)
        r2 = _region(s, roh_r1)
        r1 = max(roh_r1, 3)
    # Schritt 1
    e = _laengstes(s, _SCHRITT1)
    if e and len(s) - len(e) >= r1:
        if e in ("em", "ern", "er"):
            s = s[: -len(e)]
        elif e in ("e", "en", "es"):
            s = s[: -len(e)]
            if s.endswith("niss"):
                s = s[:-1]
        elif e == "s" and len(s) >= 2 and s[-2] in _S_ENDE:
            s = s[:-1]
    # Schritt 2
    e = _laengstes(s, _SCHRITT2)
    if e and len(s) - len(e) >= r1:
        if e in ("en", "er", "est"):
            s = s[: -len(e)]
        elif e == "st" and len(s) >= 3 and s[-3] in _ST_ENDE and len(s) - 3 >= 3:
            s = s[:-2]
    # Schritt 3
    e = _laengstes(s, _SCHRITT3)
    if e and len(s) - len(e) >= r2:
        if e in ("end", "ung"):
            s = s[: -len(e)]
            if s.endswith("ig") and len(s) - 2 >= r2 and not s[:-2].endswith("e"):
                s = s[:-2]
        elif e in ("ig", "ik", "isch"):
            if not s[: -len(e)].endswith("e"):
                s = s[: -len(e)]
        elif e in ("lich", "heit"):
            s = s[: -len(e)]
            for vor in ("er", "en"):
                if s.endswith(vor) and len(s) - 2 >= r1:
                    s = s[:-2]
                    break
        elif e == "keit":
            s = s[:-4]
            f = _laengstes(s, ("lich", "ig"))
            if f and len(s) - len(f) >= r2:
                s = s[: -len(f)]
    return (
        s.replace("U", "u").replace("Y", "y").replace("ä", "a").replace("ö", "o").replace("ü", "u")
    )


STEMMER_PROBE = {
    # Paare aus der Beispielliste von snowballstem.org (German, Vokabular und Ausgabe)
    "aufeinanderfolgenden": "aufeinanderfolg",
    "kategorien": "kategori",
    "häuser": "haus",
    "ergebnisse": "ergebnis",
    "radwege": "radweg",
    "radweg": "radweg",
    "schulen": "schul",
    "kindertageseinrichtungen": "kindertageseinricht",
    "straße": "strass",
    "möglichkeiten": "moglich",
}

_WORT = re.compile(r"\w+")


class Zerleger:
    """Token `\\w+` in Kleinschreibung, mit oder ohne Stemmer; jedes Wort wird einmal gestemmt."""

    def __init__(self, stemmen: bool) -> None:
        self.stemmen = stemmen
        self.cache: dict[str, str] = {}

    def __call__(self, text: str) -> list[str]:
        woerter = _WORT.findall(text.lower())
        if not self.stemmen:
            return woerter
        cache = self.cache
        out = []
        for w in woerter:
            s = cache.get(w)
            if s is None:
                s = cache[w] = stem_de(w)
            out.append(s)
        return out


class Bm25:
    """Okapi BM25 über eine Wortmatrix (Einheiten × Token), Fassung 18-bm25-1 (§ 3.1)."""

    def __init__(self, texte: Sequence[str], zerleger: Zerleger) -> None:
        from sklearn.feature_extraction.text import CountVectorizer

        self.zerleger = zerleger
        vec = CountVectorizer(analyzer=zerleger, dtype=np.float64)
        matrix = vec.fit_transform(texte)
        self.vokabular: dict[str, int] = {str(k): int(v) for k, v in vec.vocabulary_.items()}
        self.matrix = sparse.csc_matrix(matrix)
        laenge = np.asarray(matrix.sum(axis=1)).ravel()
        self.n = matrix.shape[0]
        df = np.diff(self.matrix.indptr)
        self.idf = np.log(1.0 + (self.n - df + 0.5) / (df + 0.5))
        self.norm = K1 * (1.0 - B + B * laenge / laenge.mean())

    def punkte(self, frage: str) -> np.ndarray:
        werte = np.zeros(self.n, dtype=np.float64)
        for token in dict.fromkeys(self.zerleger(frage)):
            spalte = self.vokabular.get(token)
            if spalte is None:
                continue
            lo, hi = self.matrix.indptr[spalte], self.matrix.indptr[spalte + 1]
            zeilen = self.matrix.indices[lo:hi]
            tf = self.matrix.data[lo:hi]
            werte[zeilen] += self.idf[spalte] * tf * (K1 + 1.0) / (tf + self.norm[zeilen])
        return werte


def rangfolge(werte: np.ndarray, tiefe: int, nur_positiv: bool = False) -> list[int]:
    """Indizes der besten ``tiefe`` Einheiten; Gleichstände nach Index (= nach ID) aufsteigend."""
    index = np.arange(len(werte))
    if nur_positiv:
        index = index[werte > 0]
    if len(index) == 0:
        return []
    teil = index[np.argsort(-werte[index], kind="stable")]
    # stabil sortiert über aufsteigende Indizes: Gleichstände bleiben nach ID geordnet
    return teil[:tiefe].tolist()


def rrf(listen: Sequence[Sequence[int]], tiefe: int) -> list[tuple[int, float]]:
    werte: dict[int, float] = {}
    for liste in listen:
        for platz, i in enumerate(liste[:TIEFE], start=1):
            werte[i] = werte.get(i, 0.0) + 1.0 / (RRF_K + platz)
    geordnet = sorted(werte.items(), key=lambda p: (-p[1], p[0]))
    return geordnet[:tiefe]


def konvex(
    listen: Sequence[tuple[Sequence[int], np.ndarray]], tiefe: int
) -> list[tuple[int, float]]:
    """Explorativ: 0,5 / 0,5 der auf [0, 1] skalierten Punktzahlen der ersten 100."""
    werte: dict[int, float] = {}
    for liste, punkte in listen:
        oben = list(liste[:TIEFE])
        if not oben:
            continue
        p = punkte[oben]
        lo, hi = float(p.min()), float(p.max())
        for i, x in zip(oben, p, strict=True):
            skaliert = (float(x) - lo) / (hi - lo) if hi > lo else 1.0
            werte[i] = werte.get(i, 0.0) + 0.5 * skaliert
    return sorted(werte.items(), key=lambda q: (-q[1], q[0]))[:tiefe]


# --- Einbettungen über F5 ------------------------------------------------------------------------


@dataclass
class Modell:
    settings: Any
    layout: Layout

    def __post_init__(self) -> None:
        client = client_from_settings(self.settings.ml)
        self.embedder = embedder_from_settings(self.settings.ml, client)
        self.stuecke = EmbeddingUse(self.embedder, PROMPT_STUECKE)
        self.anfragen = EmbeddingUse(self.embedder, PROMPT_ANFRAGE)

    def cache(self) -> ModelCache:
        return ModelCache(self.layout.ml_cache, self.stuecke.name)

    def rechnen(self, use: EmbeddingUse, texte: Sequence[str], limit: int) -> dict[str, Any]:
        self.embedder.calls.clear()
        vorher = uptime()
        t0 = time.perf_counter()
        with self.cache() as cache:
            got = embed_texts(
                use,
                cache,
                texte,
                batch_size=self.settings.ml.batch_size,
                limit=limit,
                progress=progress_log(60.0),
            )
        wand = time.perf_counter() - t0
        calls = list(self.embedder.calls)
        return {
            "zeit": time.strftime("%Y-%m-%d %H:%M:%S"),
            "prompt": use.prompt,
            "bericht": got.report.line(),
            "neu": got.report.computed,
            "offen": got.report.left + got.report.failed,
            "aufrufe": len(calls),
            "token": sum(c.prompt_tokens for c in calls),
            "server_s": sum(c.seconds for c in calls),
            "laden_s": sum(c.load_seconds for c in calls),
            "wand_s": wand,
            "uptime_vorher": vorher,
            "uptime_nachher": uptime(),
        }

    def aus_cache(self, use: EmbeddingUse, texte: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
        """Vektoren aus dem Cache, ohne zu rechnen; ``present`` markiert, was fehlt."""
        key = CacheKey(use.name, self.embedder.digest, use.prompt_key())
        shas = [input_sha256(t) for t in texte]
        with self.cache() as cache:
            found = cache.get_many(key, sorted(set(shas)))
        null = bytes(4 * self.embedder.dimension)
        vektoren = decode_vectors([found.get(s, null) for s in shas], self.embedder.dimension)
        da = np.asarray([s in found for s in shas], dtype=np.bool_)
        return normiert(vektoren), da


def normiert(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float32)
    n = np.linalg.norm(m, axis=-1, keepdims=True)
    return np.divide(m, n, out=np.zeros_like(m), where=n > 0)


def max_je_einheit(sims: np.ndarray, st: Stuecke, n: int) -> np.ndarray:
    werte = np.full(n, -np.inf, dtype=np.float64)
    np.maximum.at(werte, st.einheit, sims)
    return werte


def dokvektoren(vek: np.ndarray, st: Stuecke) -> np.ndarray:
    """Fassung 18-dokvektor-1: Mittel der ersten drei Stückvektoren, normiert."""
    n = len(st.anzahl)
    summe = np.zeros((n, vek.shape[1]), dtype=np.float64)
    platz = np.arange(len(st.einheit)) - st.erstes[st.einheit]
    nimm = platz < DOKVEKTOR_STUECKE
    np.add.at(summe, st.einheit[nimm], vek[nimm])
    return normiert(summe.astype(np.float32))


# --- Anfragen, Rangfolgen, Pools -------------------------------------------------------------------


def lade_anfragen() -> list[dict[str, str]]:
    return tomllib.loads(ANFRAGEN.read_text(encoding="utf-8"))["anfrage"]


@dataclass
class Rangfolgen:
    """Je Verfahren und Frage die Indizes der Einheiten mit Punktzahl (die ersten TIEFE)."""

    listen: dict[str, dict[str, list[tuple[int, float]]]]

    def frame(self, ids: Sequence[str], anfragen: Sequence[dict[str, str]]) -> pl.DataFrame:
        zeilen = []
        text = {a["id"]: a["anfrage"] for a in anfragen}
        for verfahren, je_frage in self.listen.items():
            for aid, liste in je_frage.items():
                for platz, (i, wert) in enumerate(liste, start=1):
                    zeilen.append(
                        {
                            "verfahren": verfahren,
                            "anfrage_id": aid,
                            "query": text[aid],
                            "id": ids[i],
                            "rang": platz,
                            "score": float(wert),
                        }
                    )
        return pl.DataFrame(zeilen)


def rechne_rangfolgen(
    einheiten: pl.DataFrame,
    st: Stuecke,
    vek: np.ndarray,
    fragen_vek: np.ndarray,
    anfragen: Sequence[dict[str, str]],
    texte: Sequence[str],
) -> Rangfolgen:
    n = einheiten.height
    t0 = time.perf_counter()
    bm25 = Bm25(texte, Zerleger(stemmen=True))
    log(f"BM25 mit Stemmer: {len(bm25.vokabular)} Token, {time.perf_counter() - t0:.1f} s")
    t0 = time.perf_counter()
    roh = Bm25(texte, Zerleger(stemmen=False))
    log(
        f"BM25 ohne Stemmer (explorativ): {len(roh.vokabular)} Token, {time.perf_counter() - t0:.1f} s"
    )
    erste = st.erstes
    kurz = normiert(vek[:, :MATRJOSCHKA])
    listen: dict[str, dict[str, list[tuple[int, float]]]] = {
        k: {}
        for k in (
            *VERFAHREN,
            "bm25_ohne_stemmer",
            "einbettung_erstes_stueck",
            "einbettung_256",
            "mischung_konvex",
        )
    }
    for j, a in enumerate(anfragen):
        aid = a["id"]
        p_bm = bm25.punkte(a["anfrage"])
        r_bm = rangfolge(p_bm, TIEFE, nur_positiv=True)
        listen["bm25"][aid] = [(i, float(p_bm[i])) for i in r_bm]
        sims = vek @ fragen_vek[j]
        p_em = max_je_einheit(sims, st, n)
        r_em = rangfolge(p_em, TIEFE)
        listen["einbettung"][aid] = [(i, float(p_em[i])) for i in r_em]
        listen["mischung"][aid] = rrf([r_bm, r_em], TIEFE)
        # explorativ
        p_roh = roh.punkte(a["anfrage"])
        listen["bm25_ohne_stemmer"][aid] = [
            (i, float(p_roh[i])) for i in rangfolge(p_roh, TIEFE, nur_positiv=True)
        ]
        p_erst = sims[erste]
        listen["einbettung_erstes_stueck"][aid] = [
            (i, float(p_erst[i])) for i in rangfolge(p_erst, TIEFE)
        ]
        q256 = normiert(fragen_vek[j][:MATRJOSCHKA][None, :])[0]
        p_256 = max_je_einheit(kurz @ q256, st, n)
        listen["einbettung_256"][aid] = [(i, float(p_256[i])) for i in rangfolge(p_256, TIEFE)]
        listen["mischung_konvex"][aid] = konvex([(r_bm, p_bm), (r_em, p_em)], TIEFE)
    return Rangfolgen(listen)


def pool_suche(
    rf: Rangfolgen, ids: Sequence[str], anfragen: Sequence[dict[str, str]]
) -> pl.DataFrame:
    zeilen = []
    for a in anfragen:
        gesehen: set[int] = set()
        for verfahren in VERFAHREN:
            for i, _ in rf.listen[verfahren][a["id"]][:POOL]:
                gesehen.add(i)
        for i in sorted(gesehen):
            zeilen.append({"query": a["anfrage"], "id": ids[i], "bedarf": a["bedarf"]})
    return pl.DataFrame(zeilen).sort("query", "id")


# --- Anker und Nachbarn ---------------------------------------------------------------------------


def ziehe_anker(einheiten: pl.DataFrame) -> pl.DataFrame:
    kandidaten = einheiten.filter(pl.col("roh").str.len_chars() >= ANKER_MIN)
    oben = (
        kandidaten.group_by("paper_type")
        .len()
        .sort(["len", "paper_type"], descending=[True, False])
        .head(ARTEN_SCHICHTEN)["paper_type"]
        .to_list()
    )
    kandidaten = kandidaten.with_columns(
        pl.when(pl.col("paper_type").is_in(oben))
        .then(pl.col("paper_type"))
        .otherwise(pl.lit("sonst"))
        .alias("schicht")
    )
    groessen = {str(k): int(v) for k, v in kandidaten.group_by("schicht").len().iter_rows()}
    quote = allocate(groessen, ANKER, "proportional")
    kandidaten = kandidaten.with_columns(
        pl.col("id").map_elements(lambda i: rank(SEED, i), return_dtype=pl.String).alias("rang")
    )
    teile = [
        kandidaten.filter(pl.col("schicht") == s).sort("rang").head(quote[s]) for s in sorted(quote)
    ]
    return pl.concat(teile).sort("rang").select("id", "schicht", "paper_type")


def tfidf_matrix(texte: Sequence[str]) -> sparse.csr_matrix:
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(
        lowercase=True,
        token_pattern=r"(?u)\b\w\w+\b",
        min_df=2,
        max_df=0.5,
        sublinear_tf=True,
        norm="l2",
        dtype=np.float32,
    )
    return sparse.csr_matrix(vec.fit_transform(texte))


def naechste(werte: np.ndarray, selbst: int, k: int) -> list[int]:
    werte = werte.astype(np.float64).copy()
    werte[selbst] = -np.inf
    return rangfolge(werte, k)


def _basis(referenz: str | None) -> str:
    """Drucksachennummer ohne Fassung: BV6/108/2023/1 -> BV6/108/2023."""
    teile = (referenz or "").split("/")
    return "/".join(teile[:3]) if len(teile) >= 3 else (referenz or "")


def verweis_anteil(einheiten: pl.DataFrame, paare: pl.DataFrame) -> None:
    """Explorativ, ohne Kodierung (Labels aus den Daten, Plan § 2.6): Anteil der Paare, die
    dieselbe Drucksachennummer tragen oder deren einer Text die Nummer des anderen nennt -- ein
    grobes Zeichen für denselben Vorgang (Vorhaben 14 nutzt dieselben Verweise)."""
    ref = dict(zip(einheiten["id"], einheiten["reference"], strict=True))
    text = dict(
        zip(
            einheiten["id"],
            [
                t + "\n" + r
                for t, r in zip(einheiten["name"].fill_null(""), einheiten["roh"], strict=True)
            ],
            strict=True,
        )
    )
    for verfahren in ("einbettung", "tfidf"):
        q = paare.filter(pl.col("verfahren") == verfahren)
        treffer = 0
        for a, b in q.select("anker", "nachbar").iter_rows():
            ra, rb = _basis(ref[a]), _basis(ref[b])
            treffer += bool((ra and ra == rb) or (ra and ra in text[b]) or (rb and rb in text[a]))
        log(f"Verweis zwischen Anker und Nachbar ({verfahren}, explorativ): {treffer}/{q.height}")


# --- Auswertung -------------------------------------------------------------------------------------


def bootstrap_diff(a: np.ndarray, b: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    d = a - b
    zieh = rng.integers(0, len(d), size=(BOOT, len(d)))
    m = d[zieh].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def permutation_p(a: np.ndarray, b: np.ndarray, rng: np.random.Generator) -> float:
    d = a - b
    beob = abs(d.mean())
    zeichen = rng.choice([-1.0, 1.0], size=(PERM, len(d)))
    null = np.abs((zeichen * d).mean(axis=1))
    return float((1 + (null >= beob - 1e-12).sum()) / (PERM + 1))


def labels_lesen(ordner: Path) -> pl.DataFrame | None:
    pfad = ordner / "labels.csv"
    if not pfad.is_file():
        return None
    return pl.read_csv(pfad, infer_schema_length=0)


# --- Ausgaben ----------------------------------------------------------------------------------------


def sha256_datei(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def schreibe(frame: pl.DataFrame, pfad: Path) -> str:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(pfad, compression="zstd", statistics=False)
    return sha256_datei(pfad)[:12]


def main(argv: Sequence[str]) -> int:  # noqa: C901, PLR0912, PLR0915 -- von oben nach unten lesbar
    ap = argparse.ArgumentParser()
    ap.add_argument("--einbetten", action="store_true", help="fehlende Stücke rechnen (GPU)")
    ap.add_argument("--limit", type=int, default=0, help="höchstens so viele neue Stücke")
    ap.add_argument(
        "--minuten", type=float, default=28.0, help="danach keinen neuen Block beginnen"
    )
    ap.add_argument("--pools", action="store_true", help="Grundgesamtheiten für F4 schreiben")
    ap.add_argument("--auswertung", action="store_true", help="Kriterium aus den Labels")
    ap.add_argument("--cluster", action="store_true", help="Cluster gegen NMF (explorativ)")
    ap.add_argument("--groessen", action="store_true", help="Größen der Ausgaben messen")
    ap.add_argument(
        "--hochrechnung", action="store_true", help="Stücke und Laufzeit je Periode (ohne GPU)"
    )
    ap.add_argument(
        "--rohtext",
        type=Path,
        default=MESSDATEN / "rohtext" / f"{PROFIL}.parquet",
    )
    args = ap.parse_args(argv)

    for wort, stamm in STEMMER_PROBE.items():
        if stem_de(wort) != stamm:
            log(f"Stemmer-Probe: {wort} -> {stem_de(wort)}, erwartet {stamm}")
            return 2

    settings, layout = settings_and_layout()
    t0 = time.perf_counter()
    einheiten = lade_einheiten(layout, args.rohtext)
    st = alle_stuecke(einheiten)
    texte = [text_von(t, r) for t, r in zip(einheiten["titel"], einheiten["roh"], strict=True)]
    ids = einheiten["id"].to_list()
    zeichen = einheiten["roh"].str.len_chars()
    log(
        f"{einheiten.height} Einheiten ({int(einheiten['ids'].list.len().sum())} Korpus-IDs), "
        f"{len(st.texte)} Stücke, {int(zeichen.sum())} Zeichen Rohtext; "
        f"Stücke je Einheit Mittel {st.anzahl.mean():.2f}, Median {np.median(st.anzahl):.0f}, "
        f"max {st.anzahl.max()}; Zeichen je Stück Mittel "
        f"{np.mean([len(t) for t in st.texte]):.0f} ({time.perf_counter() - t0:.1f} s)"
    )
    anfragen = lade_anfragen()
    modell = Modell(settings, layout)
    AUS.mkdir(parents=True, exist_ok=True)

    if args.hochrechnung:
        return hochrechnung(st, einheiten)

    if args.einbetten:
        return einbetten(modell, st, anfragen, args.minuten, args.limit)

    vek, da = modell.aus_cache(modell.stuecke, st.texte)
    fragen_vek, fda = modell.aus_cache(
        modell.anfragen, [FRAGE_PREFIX + a["anfrage"] for a in anfragen]
    )
    log(
        f"aus dem Cache: {int(da.sum())} von {len(da)} Stücken, {int(fda.sum())} von {len(fda)} Fragen"
    )
    if not da.all() or not fda.all():
        log("Es fehlen Einbettungen; zuerst --einbetten (unter flock).")
        return 1

    rf = rechne_rangfolgen(einheiten, st, vek, fragen_vek, anfragen, texte)
    rang = rf.frame(ids, anfragen)
    log(f"Rangfolgen: {rang.height} Zeilen, sha256 {schreibe(rang, AUS / 'rangfolgen.parquet')}")

    # Überblick ohne Labels: Überschneidung der Listen und leere BM25-Listen
    form = {a["id"]: a["form"] for a in anfragen}
    ueber = []
    for a in anfragen:
        top = {v: {i for i, _ in rf.listen[v][a["id"]][:POOL]} for v in VERFAHREN}
        ueber.append(
            {
                "anfrage_id": a["id"],
                "form": form[a["id"]],
                "bm25_n": len(rf.listen["bm25"][a["id"]]),
                "jaccard_bm25_einb": len(top["bm25"] & top["einbettung"])
                / max(1, len(top["bm25"] | top["einbettung"])),
                "pool": len(top["bm25"] | top["einbettung"] | top["mischung"]),
            }
        )
    ueber_f = pl.DataFrame(ueber)
    log(
        ueber_f.group_by("form")
        .agg(
            pl.len().alias("fragen"),
            pl.col("jaccard_bm25_einb").mean().round(3),
            (pl.col("bm25_n") < POOL).sum().alias("bm25_unter_10"),
            pl.col("pool").mean().round(1),
        )
        .sort("form")
    )
    log(f"Pool gesamt: {int(ueber_f['pool'].sum())} Paare (Frage, Einheit)")

    anker = ziehe_anker(einheiten)
    dok = dokvektoren(vek, st)
    tf = tfidf_matrix(texte)
    index = {i: k for k, i in enumerate(ids)}
    paare = []
    for aid in anker["id"]:
        k = index[aid]
        for verfahren, werte in (
            ("einbettung", dok @ dok[k]),
            ("tfidf", (tf @ tf[k].T).toarray().ravel()),
        ):
            for platz, j in enumerate(naechste(werte, k, NACHBARN), start=1):
                paare.append(
                    {
                        "anker": aid,
                        "nachbar": ids[j],
                        "verfahren": verfahren,
                        "rang": platz,
                        "score": float(werte[j]),
                    }
                )
    paare_f = pl.DataFrame(paare)
    log(f"Nachbarn: {paare_f.height} Zeilen, sha256 {schreibe(paare_f, AUS / 'nachbarn.parquet')}")
    einb = paare_f.filter(pl.col("verfahren") == "einbettung").select("anker", "nachbar")
    tfid = paare_f.filter(pl.col("verfahren") == "tfidf").select("anker", "nachbar")
    gemeinsam = einb.join(tfid, on=["anker", "nachbar"], how="inner").height
    log(
        f"Anker {anker.height} (Schichten {dict(Counter(anker['schicht']))}); Paare Einbettung "
        f"{einb.height}, TF-IDF {tfid.height}, gemeinsam {gemeinsam}, vereinigt "
        f"{einb.height + tfid.height - gemeinsam}"
    )

    verweis_anteil(einheiten, paare_f)

    if args.pools:
        ziel = layout.root / "messung18"
        p_suche = pool_suche(rf, ids, anfragen)
        log(
            f"Pool Suche: {p_suche.height} Einheiten, sha256 {schreibe(p_suche, ziel / 'pool_suche.parquet')}"
        )
        p_nach = (
            pl.concat([einb, tfid])
            .unique()
            .rename({"anker": "id_a", "nachbar": "id_b"})
            .sort("id_a", "id_b")
        )
        log(
            f"Pool Nachbarn: {p_nach.height} Paare, sha256 {schreibe(p_nach, ziel / 'pool_nachbarn.parquet')}"
        )
        anker_pfad = AUS / "anker.parquet"
        log(f"Anker: sha256 {schreibe(anker, anker_pfad)}")

    if args.groessen:
        groessen(vek, dok, st, einheiten, layout)

    if args.cluster:
        cluster(dok, einheiten, layout, settings)

    if args.auswertung:
        auswertung(rf, ids, anfragen, paare_f, einheiten)
    return 0


# --- Einbetten in Blöcken (GPU, unter flock) ----------------------------------------------------------

BLOCK = 2048  # Stücke je Aufruf von embed_texts; danach Zeitprüfung
PROBE = 64
GPU_GRENZE_S = 0.05  # Rechenzeit des Servers je Stück; darüber rechnet ollama auf der CPU


def _notiere(bericht: dict[str, Any]) -> None:
    log(json.dumps(bericht, ensure_ascii=False))
    with (AUS / "laufzeit.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(bericht, ensure_ascii=False) + "\n")


def einbetten(
    modell: Modell, st: Stuecke, anfragen: Sequence[dict[str, str]], minuten: float, limit: int
) -> int:
    """Fragen, dann eine Probe von 64 Stücken (bricht ab, wenn ollama auf der CPU rechnet: am
    2026-11-23 um 22:42 scheiterte die CUDA-Initialisierung still, und `ollama ps` sagte
    trotzdem „100% GPU"), dann Blöcke bis ``minuten`` oder ``limit``."""
    start = time.perf_counter()
    _notiere(modell.rechnen(modell.anfragen, [FRAGE_PREFIX + a["anfrage"] for a in anfragen], 0))
    probe = modell.rechnen(modell.stuecke, st.texte, PROBE)
    probe["block"] = "probe"
    _notiere(probe)
    if probe["neu"] and probe["server_s"] / probe["neu"] > GPU_GRENZE_S:
        log(
            f"Abbruch: {probe['server_s'] / probe['neu']:.3f} s je Stück, über {GPU_GRENZE_S}; "
            "ollama rechnet wohl auf der CPU (Log: ggml_cuda_init)."
        )
        return 3
    gerechnet = probe["neu"]
    while time.perf_counter() - start < minuten * 60:
        rest = BLOCK if not limit else min(BLOCK, limit - gerechnet)
        if rest <= 0:
            break
        bericht = modell.rechnen(modell.stuecke, st.texte, rest)
        _notiere(bericht)
        gerechnet += bericht["neu"]
        if bericht["neu"] == 0:
            break
    log(f"{gerechnet} Stücke in {time.perf_counter() - start:.0f} s")
    return 0


# --- Hochrechnung je Periode (§ 3.3) ---------------------------------------------------------------

PERIODEN = {
    "duesseldorf": "Hauptperiode 2020-2025",
    "2014-2020": "Wahlperiode 2014-2020",
    "2025": "laufende Periode ab 2025",
    "moenchengladbach": "Mönchengladbach",
}


def hochrechnung(st: Stuecke, einheiten: pl.DataFrame) -> int:
    """Stücke je Periode mit einem Platzhaltertitel von der mittleren Titellänge der Hauptperiode,
    Token und Sekunden aus den gemessenen Blöcken (laufzeit.jsonl) der Hauptperiode."""
    titel = "x" * round(float(einheiten["titel"].str.len_chars().mean()))
    laeufe = [
        json.loads(z)
        for z in (AUS / "laufzeit.jsonl").read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    bloecke = [b for b in laeufe if b["prompt"] == PROMPT_STUECKE and b["neu"] > 0]
    neu = sum(b["neu"] for b in bloecke)
    token_je = sum(b["token"] for b in bloecke) / neu
    server_je = sum(b["server_s"] for b in bloecke) / neu
    wand_je = sum(b["wand_s"] for b in bloecke) / neu
    log(
        f"gemessen: {neu} Stücke in {len(bloecke)} Blöcken, {token_je:.0f} Token je Stück, "
        f"Server {1000 * server_je:.2f} ms, Wanduhr {1000 * wand_je:.2f} ms je Stück; "
        f"Last {bloecke[0]['uptime_vorher']} bis {bloecke[-1]['uptime_nachher']}"
    )
    for datei, name in PERIODEN.items():
        roh = pl.read_parquet(MESSDATEN / "rohtext" / f"{datei}.parquet", columns=["text"])
        roh = roh.filter(pl.col("text").str.strip_chars() != "")
        n = sum(len(zerteile(titel, t)) for t in roh["text"])
        log(
            f"{name}: {roh.height} Dateien, {int(roh['text'].str.len_chars().sum())} Zeichen, "
            f"{n} Stücke, {n * token_je / 1e6:.1f} Mio. Token, GPU {n * server_je / 60:.1f} min, "
            f"Wanduhr {n * wand_je / 60:.1f} min, float16 768: {n * 1536 / 2**20:.0f} MiB roh"
        )
    log(f"Hauptperiode mit echten Titeln: {len(st.texte)} Stücke")
    return 0


# --- Größen (§ 3.4) ---------------------------------------------------------------------------------


def groessen(
    vek: np.ndarray, dok: np.ndarray, st: Stuecke, einheiten: pl.DataFrame, layout: Layout
) -> None:
    ziel = AUS / "groessen"
    ziel.mkdir(parents=True, exist_ok=True)
    ids = einheiten["id"].to_list()

    # float16 ohne Polars-Typ: als Bytes je Zeile, wie ein Paket es tragen würde
    def bytes_frame(m: np.ndarray, schluessel: Sequence[str], dtype: Any) -> pl.DataFrame:
        return pl.DataFrame({"id": list(schluessel), "v": [r.astype(dtype).tobytes() for r in m]})

    proben = {
        "dokvektoren_f16_768": bytes_frame(dok, ids, np.float16),
        "dokvektoren_f16_256": bytes_frame(normiert(dok[:, :MATRJOSCHKA]), ids, np.float16),
        "dokvektoren_i8_768": bytes_frame(np.round(dok * 127).clip(-127, 127), ids, np.int8),
        "stuecke_f16_768": pl.DataFrame(
            {
                "id": [ids[i] for i in st.einheit],
                "stueck": (np.arange(len(st.einheit)) - st.erstes[st.einheit]).tolist(),
                "v": [r.astype(np.float16).tobytes() for r in vek],
            }
        ),
    }
    for name, frame in proben.items():
        pfad = ziel / f"{name}.parquet"
        frame.write_parquet(pfad, compression="zstd", compression_level=19, statistics=False)
        log(f"Größe {name}: {frame.height} Zeilen, {pfad.stat().st_size / 2**20:.1f} MiB")
    # Nachbarn je Einheit (10 IDs) als Paket und als JSON für den Dialog
    t0 = time.perf_counter()
    nachbarn = np.zeros((len(ids), 10), dtype=np.int64)
    werte = np.zeros((len(ids), 10), dtype=np.float32)
    for start in range(0, len(ids), 2048):
        block = dok[start : start + 2048] @ dok.T
        for r in range(block.shape[0]):
            block[r, start + r] = -np.inf
        teil = np.argpartition(-block, 10, axis=1)[:, :10]
        for r in range(block.shape[0]):
            ordnung = teil[r][np.lexsort((teil[r], -block[r, teil[r]]))]
            nachbarn[start + r] = ordnung
            werte[start + r] = block[r, ordnung]
    log(f"zehn Nachbarn je Einheit für {len(ids)} Einheiten: {time.perf_counter() - t0:.1f} s")
    tab = pl.DataFrame(
        {
            "id": ids,
            "rang": [list(range(1, 11))] * len(ids),
            "nachbar": [[ids[j] for j in row] for row in nachbarn],
            "aehnlichkeit": werte.round(4).tolist(),
        }
    ).explode("rang", "nachbar", "aehnlichkeit")
    pfad = ziel / "aehnliche_dokumente.parquet"
    tab.write_parquet(pfad, compression="zstd", compression_level=19, statistics=False)
    log(
        f"Größe aehnliche_dokumente (10 je Einheit, lang): {tab.height} Zeilen, {pfad.stat().st_size / 2**20:.2f} MiB"
    )
    np.save(AUS / "nachbarn10.npy", nachbarn)
    # Dialog: die Dokumente aus dokumente.json; fünf Nachbarn als Index in eine Tabelle aller Einheiten
    dokjson = layout.root / "site" / "data" / "dokumente.json"
    if dokjson.is_file():
        d = json.loads(dokjson.read_text(encoding="utf-8"))
        datei_index = {f: k for k, f in enumerate(einheiten["file_name"].to_list())}
        im_dialog = [datei_index.get(row[0]) for row in d["documents"]]
        im_dialog_set = {k for k in im_dialog if k is not None}
        fuenf = {k: nachbarn[k, :5].tolist() for k in im_dialog_set}
        fremde = {j for v in fuenf.values() for j in v} - im_dialog_set
        kompakt = json.dumps(
            [fuenf.get(k, []) if k is not None else [] for k in im_dialog], separators=(",", ":")
        )
        meta = json.dumps(
            [
                [
                    einheiten["file_name"][j],
                    str(einheiten["date"][j]),
                    einheiten["reference"][j] or "",
                    einheiten["titel"][j],
                ]
                for j in sorted(fremde)
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        import gzip

        log(
            f"Dialog: {len(im_dialog)} Dokumente in dokumente.json, davon {len(im_dialog_set)} Einheiten; "
            f"fünf Nachbarn als Indizes {len(kompakt.encode()) / 1024:.0f} KB (gzip "
            f"{len(gzip.compress(kompakt.encode())) / 1024:.0f} KB), Nachbarn außerhalb der Datei {len(fremde)}, "
            f"ihre Metadaten {len(meta.encode()) / 1024:.0f} KB (gzip {len(gzip.compress(meta.encode())) / 1024:.0f} KB); "
            f"je Dokument {len(kompakt.encode()) / max(1, len(im_dialog)):.0f} Bytes"
        )


# --- Cluster (explorativ, § 3.5) ---------------------------------------------------------------------


def _modul(pfad: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, pfad)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cluster(dok: np.ndarray, einheiten: pl.DataFrame, layout: Layout, settings: Any) -> None:
    from sklearn.cluster import KMeans
    from sklearn.decomposition import NMF
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

    from georep.analysis import topics as tp

    korpus = pl.read_parquet(layout.corpus, columns=["id", "text"])
    frame = (
        einheiten.select("id")
        .join(korpus, on="id", how="left")
        .with_columns(pl.col("text").fill_null(""))
    )
    mit_text = (frame["text"] != "").to_numpy()
    texte = [t for t, m in zip(frame["text"].to_list(), mit_text, strict=True) if m]
    X = dok[mit_text]
    ids = [i for i, m in zip(frame["id"].to_list(), mit_text, strict=True) if m]
    gremien = pl.read_parquet(
        layout.root / "processed" / "papers_gremien.parquet",
        columns=["id", "gremium", "gremium_art"],
    )
    g = pl.DataFrame({"id": ids}).join(gremien, on="id", how="left")
    ausschuss = (g["gremium_art"] == "ausschuss").fill_null(False).to_numpy()
    label_gremium = g["gremium"].fill_null("").to_numpy()
    rules = tp.TopicRules.from_settings(settings)
    matrix, vokabular = tp.vectorize(texte, settings.topics, rules)
    voc = np.asarray(vokabular)
    themen = _modul(REPO / "docs" / "themenmodell-2026-10-messung.py", "themenmessung")
    ergebnisse = []

    def bewerte(
        name: str, labels_je_seed: list[np.ndarray], woerter: list[list[str]], t: float
    ) -> None:
        aris = [
            adjusted_rand_score(a, b)
            for k, a in enumerate(labels_je_seed)
            for b in labels_je_seed[k + 1 :]
        ]
        nmi = normalized_mutual_info_score(label_gremium[ausschuss], labels_je_seed[0][ausschuss])
        npmi, umass = themen.coherence(texte, woerter)
        groessen = np.bincount(labels_je_seed[0])
        ergebnisse.append(
            {
                "verfahren": name,
                "ari_seeds": round(float(np.mean(aris)), 3) if aris else None,
                "nmi_ausschuss": round(float(nmi), 3),
                "npmi": round(npmi, 4),
                "umass": round(umass, 3),
                "groesste": int(groessen.max()),
                "kleinste": int(groessen.min()),
                "sekunden": round(t, 1),
            }
        )
        log(ergebnisse[-1])

    def topwoerter(labels: np.ndarray) -> list[list[str]]:
        out = []
        for c in range(CLUSTER_K):
            zeilen = matrix[labels == c]
            if zeilen.shape[0] == 0:
                out.append([])
                continue
            mittel = np.asarray(zeilen.mean(axis=0)).ravel()
            out.append(voc[np.argsort(-mittel)[:10]].tolist())
        return out

    t0 = time.perf_counter()
    km = [
        KMeans(n_clusters=CLUSTER_K, n_init=10, random_state=s).fit_predict(X)
        for s in CLUSTER_SEEDS
    ]
    bewerte(
        "kmeans_einbettung", km, topwoerter(km[0]), (time.perf_counter() - t0) / len(CLUSTER_SEEDS)
    )
    t0 = time.perf_counter()
    nmf_labels = []
    nmf_woerter: list[list[str]] = []
    for s in CLUSTER_SEEDS:
        m = NMF(
            n_components=CLUSTER_K,
            init="nndsvda",
            solver="cd",
            max_iter=settings.topics.max_iter,
            tol=settings.topics.tol,
            random_state=s,
        )
        w = m.fit_transform(matrix)
        nmf_labels.append(np.asarray(w.argmax(axis=1)))
        if not nmf_woerter:
            nmf_woerter = [voc[np.argsort(-row)[:10]].tolist() for row in m.components_]
    bewerte("nmf_frei", nmf_labels, nmf_woerter, (time.perf_counter() - t0) / len(CLUSTER_SEEDS))
    km_tfidf = [
        KMeans(n_clusters=CLUSTER_K, n_init=10, random_state=s).fit_predict(matrix)
        for s in CLUSTER_SEEDS[:2]
    ]
    bewerte("kmeans_tfidf", km_tfidf, topwoerter(km_tfidf[0]), 0.0)
    # das Modell der Seite (gesät): dominantes Thema
    td = pl.read_parquet(layout.root / "processed" / "themen_dokumente.parquet")
    dom = pl.DataFrame({"id": ids}).join(
        td.sort("anteil", descending=True).unique("id", keep="first"), on="id", how="left"
    )
    th = pl.read_parquet(layout.root / "processed" / "themen.parquet").sort("thema")
    dom_lab = dom["thema"].fill_null(-1).to_numpy()
    ok = dom_lab >= 0
    nmi = normalized_mutual_info_score(label_gremium[ausschuss & ok], dom_lab[ausschuss & ok])
    npmi, umass = themen.coherence(texte, th["woerter"].to_list())
    log(
        {
            "verfahren": "nmf_gesaet_seite",
            "nmi_ausschuss": round(float(nmi), 3),
            "npmi": round(npmi, 4),
            "umass": round(umass, 3),
        }
    )
    pl.DataFrame(ergebnisse).write_csv(AUS / "cluster.csv")
    for c, woerter in enumerate(topwoerter(km[0])):
        log(f"  Cluster {c:2d} [{int((km[0] == c).sum()):5d}] {', '.join(woerter)}")


# --- Auswertung nach den Labels (§ 4, § 5) ---------------------------------------------------------


def auswertung(
    rf: Rangfolgen,
    ids: Sequence[str],
    anfragen: Sequence[dict[str, str]],
    paare: pl.DataFrame,
    einheiten: pl.DataFrame,
) -> None:
    rng = np.random.default_rng(SEED)
    suche: bool | None = None
    besser = ""
    lab = labels_lesen(V_SUCHE)
    if lab is None:
        log("validierung/18-einbettungen/labels.csv fehlt: Suche noch nicht kodiert")
    else:
        rel = lab.filter(pl.col("frage") == "relevanz")
        stich = pl.read_csv(V_SUCHE / "stichprobe.csv", infer_schema_length=0)
        urteile = stich.join(rel.select("id", "label"), on="id", how="inner").filter(
            pl.col("label") != ""
        )
        gains: dict[str, dict[str, float]] = {}
        for q, d, lab_ in urteile.select("anfrage", "dokument", "label").iter_rows():
            gains.setdefault(q, {})[d] = float(RELEVANZ.index(lab_.strip('"')))
        nach_text = {a["anfrage"]: a for a in anfragen}
        tabelle = []
        for a in anfragen:
            g = gains.get(a["anfrage"], {})
            zeile: dict[str, Any] = {
                "anfrage_id": a["id"],
                "form": a["form"],
                "art": a["art"],
                "relevante": sum(1 for v in g.values() if v >= 1),
            }
            for verfahren, je in rf.listen.items():
                liste = je[a["id"]]
                punkte = {ids[i]: float(len(liste) - k) for k, (i, _) in enumerate(liste)}
                zeile[verfahren] = ndcg_at_k(punkte, g, POOL) if g else None
                oben = [ids[i] for i, _ in liste[:POOL]]
                zeile[f"{verfahren}_judged"] = (
                    sum(1 for d in oben if d in g) / len(oben) if oben else None
                )
            tabelle.append(zeile)
        t = pl.DataFrame(tabelle)
        gueltig = t.filter(pl.col("relevante") > 0)
        log(f"Fragen mit mindestens einem relevanten Dokument: {gueltig.height} von {t.height}")
        mittel = {v: float(gueltig[v].mean()) for v in rf.listen}
        for v in rf.listen:
            log(
                f"nDCG@10 {v:26s} {mittel[v]:.3f}  judged@10 {float(gueltig[v + '_judged'].mean()):.3f}"
            )
        bm = gueltig["bm25"].to_numpy()
        ergebnis = {}
        for v in ("einbettung", "mischung"):
            x = gueltig[v].to_numpy()
            lo, hi = bootstrap_diff(x, bm, rng)
            p = permutation_p(x, bm, rng)
            ergebnis[v] = mittel[v] - mittel["bm25"]
            log(
                f"Differenz {v} − bm25: {ergebnis[v]:+.3f} (95 % {lo:+.3f} bis {hi:+.3f}), p = {p:.4f}"
            )
        besteht = max(ergebnis.values()) >= SCHWELLE_SUCHE
        suche = besteht
        besser = max(ergebnis, key=lambda v: ergebnis[v])
        log(
            f"KRITERIUM SUCHE (max Differenz ≥ {SCHWELLE_SUCHE}): {'erfüllt' if besteht else 'verfehlt'}"
        )
        for spalte in ("form", "art"):
            log(
                gueltig.group_by(spalte)
                .agg(pl.len(), *[pl.col(v).mean().round(3) for v in rf.listen])
                .sort(spalte)
            )
        t.write_csv(AUS / "ndcg_je_anfrage.csv")
        intervalle_je_form(gueltig)
        del nach_text
    lab_n = labels_lesen(V_NACHBARN)
    if lab_n is None:
        log("validierung/18-einbettungen-nachbarn/labels.csv fehlt: Nachbarn noch nicht kodiert")
        urteil(suche, besser, None, None)
        return
    praez: dict[str, float] = {}
    stich = pl.read_csv(V_NACHBARN / "stichprobe.csv", infer_schema_length=0)
    urteile = stich.join(lab_n.filter(pl.col("frage") == "aehnlich").select("id", "label"), on="id")
    paarlabel = {
        (a, b): x.strip('"') for a, b, x in urteile.select("id_a", "id_b", "label").iter_rows()
    }
    for verfahren in ("einbettung", "tfidf"):
        p = paare.filter(pl.col("verfahren") == verfahren)
        werte = [paarlabel.get((a, b)) for a, b in p.select("anker", "nachbar").iter_rows()]
        bekannt = [w for w in werte if w is not None]
        treffer = sum(1 for w in bekannt if w in NACHBAR_LABELS[1:])
        streng = sum(1 for w in bekannt if w == NACHBAR_LABELS[2])
        iv_lo, iv_hi = wilson_interval(treffer, len(bekannt))
        anker_ids = sorted(
            p["anker"].unique().to_list()
        )  # feste Folge: der Bootstrap zieht nach Platz
        je_anker = {
            a: [
                paarlabel.get((a, b)) in NACHBAR_LABELS[1:]
                for b in p.filter(pl.col("anker") == a)["nachbar"]
            ]
            for a in anker_ids
        }
        matrix = np.asarray([np.mean(v) for v in je_anker.values()])
        boot = matrix[rng.integers(0, len(matrix), size=(BOOT, len(matrix)))].mean(axis=1)
        log(
            f"Präzision@5 {verfahren}: {treffer}/{len(bekannt)} = {treffer / max(1, len(bekannt)):.3f} "
            f"(Wilson {iv_lo:.3f} bis {iv_hi:.3f}; Anker-Bootstrap {np.percentile(boot, 2.5):.3f} bis "
            f"{np.percentile(boot, 97.5):.3f}); streng (gleiche Sache) {streng / max(1, len(bekannt)):.3f}"
        )
        praez[verfahren] = treffer / max(1, len(bekannt))
    urteil(suche, besser, praez["einbettung"], praez["tfidf"])


def _mittel_ci(x: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    zieh = rng.integers(0, len(x), size=(BOOT, len(x)))
    m = x[zieh].mean(axis=1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def intervalle_je_form(gueltig: pl.DataFrame) -> None:
    """Nachgetragen nach der Kodierung (Supervisor, 2026-11-24), ohne Einfluss auf das Kriterium:
    nDCG@10 je Verfahren mit Bootstrap-Intervall über die Fragen, insgesamt und je ``form``, dazu
    die Differenzen zu BM25 je ``form`` mit Intervall und Permutationstest. Ein eigener Zufallsstrom
    je Block (Seed wie § 3.1), damit die vorab festgelegten Intervalle oben unverändert bleiben."""
    gruppen = [("alle", gueltig)] + [
        (f, gueltig.filter(pl.col("form") == f)) for f in ("wort", "umschrieben", "frage")
    ]
    for name, g in gruppen:
        rng = np.random.default_rng(SEED)
        teile = []
        for v in VERFAHREN:
            m, lo, hi = _mittel_ci(g[v].to_numpy(), rng)
            teile.append(f"{v} {m:.3f} ({lo:.3f} bis {hi:.3f})")
        log(f"nDCG@10 je Verfahren, {name} (n = {g.height}): " + "; ".join(teile))
        bm = g["bm25"].to_numpy()
        for v in ("einbettung", "mischung"):
            x = g[v].to_numpy()
            lo, hi = bootstrap_diff(x, bm, rng)
            p = permutation_p(x, bm, rng)
            besser = int((x > bm + 1e-12).sum())
            schlechter = int((x < bm - 1e-12).sum())
            log(
                f"  {v} − bm25, {name}: {float((x - bm).mean()):+.3f} ({lo:+.3f} bis {hi:+.3f}), "
                f"p = {p:.4f}; besser bei {besser}, schlechter bei {schlechter} von {g.height} Fragen"
            )


def urteil(suche: bool | None, besser: str, p_einb: float | None, p_tfidf: float | None) -> None:
    """Die Entscheidungsregel aus § 3.1, wörtlich in Code; ``None`` heißt: noch nicht kodiert."""
    nachbarn = None if p_einb is None else p_einb >= SCHWELLE_NACHBARN
    log(f"KRITERIUM NACHBARN (Präzision@5 ≥ {SCHWELLE_NACHBARN}): {nachbarn}")
    billiger = (
        p_einb is not None
        and p_tfidf is not None
        and p_tfidf >= SCHWELLE_NACHBARN
        and p_tfidf >= p_einb - TFIDF_TOLERANZ
    )
    if suche is None or nachbarn is None:
        log("URTEIL: offen, es fehlen Labels")
    elif suche and nachbarn:
        log(f"URTEIL: bauen (embeddings, neighbors, georep suche mit {besser})")
    elif suche:
        log(
            f"URTEIL: bauen nur embeddings und georep suche mit {besser}; keine ähnlichen Dokumente"
        )
    elif nachbarn:
        log("URTEIL: bauen nur embeddings und neighbors; georep suche nicht mit Einbettung")
    else:
        log("URTEIL: verwerfen")
    if billiger:
        log(
            "RÜCKFALL: TF-IDF-Nachbarn statt Einbettung für den Dialog (≥ 0,70, höchstens 0,05 darunter)"
        )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
