"""Rechnet die Zahlen von `13-dubletten.md` nach (Vorhaben 13, Stufe 1: Dubletten und Familien).

    uv run python docs/plans/13-dubletten-messung.py [--kurven] [--familien] [--empfindlichkeit]
        [--perioden] [--stichprobe] [--kodierung] [--schreiben] [--labels-schreiben]
        [--messdaten PFAD]

Ohne Schalter läuft alles außer dem Schreiben: 1:26 min, höchster Speicher 1,3 GB (gemessen am
2026-11-23 mit `nice -n 10`, `POLARS_MAX_THREADS=4`, `OMP_NUM_THREADS=2` bei Lastmittel 10).
`--kodierung` wertet `validierung/13-dubletten/labels.csv` aus (§ 4.1); `--labels-schreiben`
baut diese Datei aus den Antworten der Kodierer und der Schlichtung unter
`<messdaten>/kodierung/13-dubletten/`.
Liest je Profil, was `georep run` geschrieben hat: den Korpus (`interim/papers.parquet`, Spalte `text`, kleingeschrieben, ohne
Zeilenumbrüche), die Gremien je Dokument und die Auswertung je Wahlbezirk (`paper_ids`, die
Wahlberechtigten, Tabelle 5). Die Wurzeln kommen aus `georep --profile <p> paths`, die
Dateinamen aus dem Layout, das dieselbe Quelle ist; kein Pfad steht hier von Hand außer dem der
gemeinsamen Messdaten (`--messdaten`, Plan § 6).

`--perioden` braucht die gelaufenen Profile `duesseldorf-2014` und `duesseldorf-2025`; fehlt eines,
sagt das Skript es und lässt den Teil aus. `--schreiben` legt die Stichprobe
(`validierung/13-dubletten/stichprobe.csv`) und die Kodieraufgaben
(`<messdaten>/kodierung/13-dubletten/aufgaben.jsonl`) an; ohne den Schalter prüft `--stichprobe`
nur, ob die Datei im Repo gleich der berechneten ist. Alles ist deterministisch (fester Seed,
Hash ohne Zufall des Interpreters, Paare sortiert).

Das MinHash hier ist der Prototyp der eigenen Umsetzung für Stufe 2 (13-dubletten.md, § 3.3 und
§ 6): Wort-Shingles, 32-Bit-Hash je Shingle, universelles Hashing modulo einer Primzahl, LSH in
Bändern, die Ähnlichkeit danach exakt über die Shingle-Mengen.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import sys
import time
import tomllib
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import polars as pl
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from georep.analysis.hits import DISTRICT, RATE
from georep.analysis.regression import RegressionPair, regression_pair, spearman
from georep.layout import Layout
from georep.prep.voters import ELIGIBLE_TOTAL
from georep.search.index import HITS, PAPER_IDS
from georep.settings import Settings, load_settings
from georep.validation.measures import krippendorff_alpha, wilson_interval

U64 = npt.NDArray[np.uint64]
U32 = npt.NDArray[np.uint32]
I64 = npt.NDArray[np.int64]
F64 = npt.NDArray[np.float64]

# --- Parameter, begründet in 13-dubletten.md, § 3.3 -------------------------------------------
K = 5  # Wörter je Shingle
N_PERM = 128  # Permutationen (Hashfunktionen) je Signatur
BANDS, ROWS = 32, 4  # LSH: 32 Bänder zu 4 Zeilen, Schwelle (1/32)^(1/4) ≈ 0,42
WIDE = (64, 2)  # die Gegenprobe: 64 Bänder zu 2 Zeilen findet fast jedes Paar ab J = 0,3
SEED = 13  # Seed der Hashfunktionen und der Stichprobe (Nummer des Vorhabens)
PRIME = np.uint64(4_294_967_291)  # größte Primzahl unter 2^32: a·x + b passt in uint64
TAU = 0.9  # Schwelle der Familien, vorab gewählt (§ 3.4), bevor Familienanteil und
# Empfindlichkeit gerechnet waren; die anderen Schwellen stehen daneben
TAUS = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95)
K_VARIANTS = (3, 5, 8)
# Schichten der Stichprobe: (untere Grenze, obere Grenze, vorgesehene Paare; Summe 200). Dicht, wo
# die Schwelle liegen kann (0,80 bis 0,95); die Schicht ab 0,95 hat weniger als 40 Paare, wird
# ganz genommen, und ihr Rest geht reihum an die Schichten in TOP_UP.
STRATA: tuple[tuple[float, float, int], ...] = (
    (0.95, 1.01, 40),
    (0.90, 0.95, 36),
    (0.85, 0.90, 32),
    (0.80, 0.85, 32),
    (0.70, 0.80, 28),
    (0.50, 0.70, 20),
    (0.30, 0.50, 12),
)
SAMPLE_SIZE = 200
TOP_UP = (2, 3, 1, 4)  # Schichten, die auffüllen, wenn eine andere zu klein ist
EXCERPT = 1500  # Zeichen je Dokument in der Kodieraufgabe (Briefing)
MESSDATEN = Path("/media/konrad/xtraspace/georep/messdaten")  # Plan § 6, gemeinsam und lokal
REPO = Path(__file__).resolve().parents[2]
SAMPLE_CSV = REPO / "validierung" / "13-dubletten" / "stichprobe.csv"
CODEBOOK = REPO / "validierung" / "13-dubletten" / "codebuch.toml"
LABELS_CSV = REPO / "validierung" / "13-dubletten" / "labels.csv"
CODES = ("gleich", "fast_gleich", "aehnlich_andere_sache", "verschieden")
SAME = ("gleich", "fast_gleich")  # „richtig" nach dem Codebuch; streng nur „gleich"
BOUNDS = (0.70, 0.80, 0.85, 0.90, 0.95)  # die Grenzen der Schwellenregel (Codebuch, § 5)
MIN_PRECISION = 0.95
MAIN, EARLIER, LATER = "duesseldorf", "duesseldorf-2014", "duesseldorf-2025"
TOKEN = re.compile(r"\w+")
PERIODIC = re.compile(
    r"halbjahr|quartal|kalenderwoche|jahresbericht|controlling|beschlusskontrolle"
)


# --- Pfade ------------------------------------------------------------------------------------


def georep_paths(profile: str) -> dict[str, str]:
    """`georep --profile <p> paths` als Wörterbuch; die eine Quelle für Pfade außerhalb des Pakets."""
    exe = shutil.which("georep") or str(Path(sys.executable).with_name("georep"))
    out = subprocess.run(
        [exe, "--profile", profile, "paths"], check=True, capture_output=True, text=True
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


@dataclass(frozen=True)
class Profile:
    name: str
    settings: Settings
    layout: Layout
    folder: str  # Ordnername des Profils, zugleich Name der Rohtext-Messdatei


def open_profile(name: str) -> Profile | None:
    paths = georep_paths(name)
    settings = load_settings(profile=name)
    layout = Layout.from_settings(settings)
    if str(layout.root.resolve()) != paths["root"]:
        raise SystemExit(f"Layout und `georep paths` widersprechen sich für {name}")
    if not layout.corpus.exists():
        return None
    return Profile(name, settings, layout, paths["profile"])


# --- MinHash und LSH --------------------------------------------------------------------------


def _mix(x: U64) -> U64:
    """splitmix64: ein fester Mischer, damit der Shingle-Hash nicht vom Interpreter abhängt."""
    z = x + np.uint64(0x9E3779B97F4A7C15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return z ^ (z >> np.uint64(31))


class Shingler:
    """Wort-Shingles als sortierte, eindeutige 32-Bit-Hashes; Tokenhashes werden gemerkt."""

    def __init__(self, k: int) -> None:
        self.k = k
        self._tokens: dict[str, int] = {}

    def _token(self, token: str) -> int:
        value = self._tokens.get(token)
        if value is None:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "little")
            self._tokens[token] = value
        return value

    def __call__(self, text: str) -> U64:
        tokens = TOKEN.findall(text)
        if len(tokens) < self.k:
            return np.empty(0, dtype=np.uint64)
        ids = np.fromiter((self._token(t) for t in tokens), dtype=np.uint64, count=len(tokens))
        n = len(ids) - self.k + 1
        h = np.zeros(n, dtype=np.uint64)
        with np.errstate(over="ignore"):
            for j in range(self.k):
                h = _mix(h ^ ids[j : j + n])
        return np.unique(h >> np.uint64(32))


def signatures(sets: Sequence[U64], n_perm: int = N_PERM, seed: int = SEED) -> U32:
    """MinHash je Menge: min über (a·x + b) mod p für n_perm Paare (a, b); leere Mengen verboten."""
    rng = np.random.default_rng(seed)
    a = rng.integers(1, int(PRIME), size=n_perm, dtype=np.uint64)
    b = rng.integers(0, int(PRIME), size=n_perm, dtype=np.uint64)
    lengths = np.fromiter((len(s) for s in sets), dtype=np.int64, count=len(sets))
    if (lengths == 0).any():
        raise ValueError("eine leere Shingle-Menge hat keine Signatur")
    flat = np.concatenate(list(sets))
    offsets = np.concatenate([[0], np.cumsum(lengths)[:-1]])
    out = np.empty((len(sets), n_perm), dtype=np.uint32)
    for i in range(n_perm):
        out[:, i] = np.minimum.reduceat((a[i] * flat + b[i]) % PRIME, offsets).astype(np.uint32)
    return out


def lsh_candidates(sig: U32, bands: int, rows: int) -> I64:
    """Paare (i, j), i < j, die in mindestens einem Band denselben Schlüssel tragen; sortiert."""
    found: set[tuple[int, int]] = set()
    for band in range(bands):
        block = np.ascontiguousarray(sig[:, band * rows : (band + 1) * rows])
        keys = block.view(np.dtype((np.void, block.dtype.itemsize * rows))).ravel()
        _, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
        shared = np.flatnonzero(counts[inverse] > 1)
        if shared.size == 0:
            continue
        order = shared[np.argsort(inverse[shared], kind="stable")]
        for group in np.split(order, np.flatnonzero(np.diff(inverse[order])) + 1):
            members = sorted(int(m) for m in group)
            for x, left in enumerate(members):
                for right in members[x + 1 :]:
                    found.add((left, right))
    if not found:
        return np.empty((0, 2), dtype=np.int64)
    return np.array(sorted(found), dtype=np.int64)


def jaccard(sets: Sequence[U64], pairs: I64) -> F64:
    """Exakte Jaccard-Ähnlichkeit der Shingle-Mengen je Paar."""
    out = np.empty(len(pairs), dtype=np.float64)
    for n, (i, j) in enumerate(pairs):
        common = np.intersect1d(sets[i], sets[j], assume_unique=True).size
        out[n] = common / (sets[i].size + sets[j].size - common)
    return out


def s_curve(s: float, bands: int, rows: int) -> float:
    """Wahrscheinlichkeit, dass ein Paar mit Jaccard s Kandidat wird: 1 − (1 − s^r)^b."""
    return 1.0 - (1.0 - s**rows) ** bands


def components(n: int, pairs: I64, keep: npt.NDArray[np.bool_]) -> I64:
    """Familien als Zusammenhangskomponenten der Kanten ``pairs[keep]``; Etikett je Dokument."""
    edges = pairs[keep]
    graph = coo_matrix(
        (np.ones(len(edges)), (edges[:, 0], edges[:, 1]) if len(edges) else ([], [])),
        shape=(n, n),
    )
    _, labels = connected_components(graph, directed=False)
    return np.asarray(labels, dtype=np.int64)


# --- Ein Korpus, gemessen ---------------------------------------------------------------------


@dataclass
class Measured:
    """Dokumente mit Shingles (Zeilen von ``meta``), ihre Mengen, Kandidaten und Ähnlichkeiten."""

    meta: pl.DataFrame  # id, name, reference, date, paper_type, gremium, gremium_art, periode
    sets: list[U64]
    pairs: I64  # Kandidaten aus BANDS × ROWS, Zeilen von meta
    sim: F64
    wide_pairs: I64  # Kandidaten der Gegenprobe
    wide_sim: F64
    n_corpus: int
    n_text: int
    seconds: dict[str, float]


def load_meta(profile: Profile, period: str) -> pl.DataFrame:
    corpus = pl.read_parquet(
        profile.layout.corpus, columns=["id", "name", "reference", "date", "paper_type", "text"]
    )
    bodies = pl.read_parquet(profile.layout.papers_bodies, columns=["id", "gremium", "gremium_art"])
    # Nach dem Join sortieren: die Zeilenfolge eines Joins ist nicht festgelegt (CLAUDE.md).
    return (
        corpus.join(bodies, on="id", how="left")
        .with_columns(pl.lit(period).alias("periode"))
        .sort("id")
    )


def measure(meta: pl.DataFrame, k: int = K, wide: bool = True) -> Measured:
    seconds: dict[str, float] = {}
    start = time.perf_counter()
    shingle = Shingler(k)
    texts = meta.get_column("text").to_list()
    all_sets = [shingle(t) for t in texts]
    rows = [i for i, s in enumerate(all_sets) if s.size]
    seconds["Shingles"] = time.perf_counter() - start
    start = time.perf_counter()
    sets = [all_sets[i] for i in rows]
    sig = signatures(sets)
    seconds["Signaturen"] = time.perf_counter() - start
    start = time.perf_counter()
    pairs = lsh_candidates(sig, BANDS, ROWS)
    seconds["LSH"] = time.perf_counter() - start
    start = time.perf_counter()
    sim = jaccard(sets, pairs)
    seconds["Jaccard"] = time.perf_counter() - start
    if wide:
        wide_pairs = lsh_candidates(sig, *WIDE)
        wide_sim = jaccard(sets, wide_pairs)
    else:
        wide_pairs, wide_sim = np.empty((0, 2), dtype=np.int64), np.empty(0)
    kept = meta[rows].drop("text") if rows else meta.clear().drop("text")
    return Measured(
        meta=kept,
        sets=sets,
        pairs=pairs,
        sim=sim,
        wide_pairs=wide_pairs,
        wide_sim=wide_sim,
        n_corpus=meta.height,
        n_text=meta.filter(pl.col("text") != "").height,
        seconds=seconds,
    )


def family_frame(m: Measured, tau: float) -> pl.DataFrame:
    """id, familie (Etikett), groesse; Dokumente ohne Partner sind Familien der Größe 1."""
    labels = components(m.meta.height, m.pairs, m.sim >= tau)
    frame = pl.DataFrame({"id": m.meta.get_column("id"), "familie": labels})
    sizes = frame.group_by("familie").agg(pl.len().alias("groesse"))
    return frame.join(sizes, on="familie", how="left").sort("id")


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f} %".replace(".", ",")


def num(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


# --- § 3.2 Exakte Dubletten -------------------------------------------------------------------


def exact_duplicates(meta: pl.DataFrame) -> None:
    """Gleicher Text unter den Dokumenten mit mindestens K Wörtern; der Rest ist leer oder kurz."""
    words = pl.col("text").str.count_matches(r"\w+")
    usable = meta.filter(words >= K)
    groups = (
        usable.group_by("text")
        .agg(pl.len().alias("n"), pl.col("reference").sort())
        .filter(pl.col("n") > 1)
        .sort("reference")
    )
    n_docs = int(groups.get_column("n").sum()) if groups.height else 0
    print(
        f"\n=== § 3.2 Exakte Dubletten: {groups.height} Gruppen, {n_docs} Dokumente "
        f"(von {usable.height} mit mindestens {K} Wörtern)"
    )
    for row in groups.iter_rows(named=True):
        print(f"  {row['n']}: {', '.join(row['reference'])}")
    empty = meta.filter(pl.col("text") == "").height
    short = meta.filter((pl.col("text") != "") & (words < K)).height
    print(
        f"  ohne Text {empty}, Text mit weniger als {K} Wörtern (oft nur Leerzeichen eines Scans) "
        f"{short}: beide bleiben Einzeldokumente"
    )


# --- § 3.3 Kurven -----------------------------------------------------------------------------


def curves(meta: pl.DataFrame, m: Measured) -> None:
    print("\n=== § 3.3 Kurven")
    shingle_counts = np.array([s.size for s in m.sets])
    print(
        f"Korpus {m.n_corpus}, mit Text {m.n_text}, mit mindestens einem {K}-Shingle "
        f"{m.meta.height}; Shingles je Dokument Median {int(np.median(shingle_counts))}, "
        f"Summe {int(shingle_counts.sum())}"
    )
    print(
        "Laufzeit: "
        + ", ".join(f"{name} {num(sec, 1)} s" for name, sec in m.seconds.items())
        + f"; Kandidaten {BANDS}×{ROWS}: {len(m.pairs)}, Gegenprobe {WIDE[0]}×{WIDE[1]}: "
        f"{len(m.wide_pairs)}"
    )

    print("\nS-Kurve P(Kandidat | J = s) = 1 − (1 − s^r)^b, 128 Permutationen:")
    grid = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
    print("  b×r    Schwelle " + " ".join(f"s={s:.1f}" for s in grid))
    for bands, rows in ((16, 8), (32, 4), (64, 2)):
        threshold = (1 / bands) ** (1 / rows)
        print(
            f"  {bands:2d}×{rows}   {num(threshold, 2):>8} "
            + " ".join(f"{s_curve(s, bands, rows):5.3f}" for s in grid)
        )
    print("Standardfehler der MinHash-Schätzung sqrt(J(1−J)/n):")
    for n_perm in (64, 128, 256):
        print(
            f"  n={n_perm:3d}: "
            + ", ".join(
                f"J={j:.1f} ± {math.sqrt(j * (1 - j) / n_perm):.3f}" for j in (0.5, 0.8, 0.9)
            )
        )

    # Trefferquote des Produktionsaufbaus gegen die Gegenprobe, je Band der exakten Ähnlichkeit
    production = {tuple(p) for p in m.pairs[m.sim >= 0.3].tolist()}
    print("\nGefunden von 32×4 unter den Paaren der Gegenprobe 64×2, je Band der exakten Jaccard:")
    for lo, hi in ((0.3, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)):
        band = (m.wide_sim >= lo) & (m.wide_sim < hi)
        wide = [tuple(p) for p in m.wide_pairs[band].tolist()]
        hit = sum(1 for p in wide if p in production)
        print(
            f"  [{lo:.1f}, {min(hi, 1.0):.1f}{']' if hi > 1 else ')'}: "
            f"{hit}/{len(wide)} = {num(hit / max(len(wide), 1))}"
        )
    extra = len(production - {tuple(p) for p in m.wide_pairs.tolist()})
    print(f"  Paare ab 0,3 nur in 32×4, nicht in 64×2: {extra}")

    proxies(m)

    print(f"\nSchwelle τ gegen Kanten und Familien (k = {K}, exakte Jaccard, 32×4):")
    print("  τ     Kanten  Familien  Dokumente in Familien  größte  Größen 2/3/4/5+")
    for tau in TAUS:
        fam = family_frame(m, tau)
        sizes = fam.unique("familie").filter(pl.col("groesse") > 1).get_column("groesse")
        in_families = int(sizes.sum()) if sizes.len() else 0
        by_size = Counter(min(int(s), 5) for s in sizes.to_list())
        print(
            f"  {num(tau, 2)}  {int((m.sim >= tau).sum()):6d}  {sizes.len():8d}  "
            f"{in_families:5d} = {pct(in_families / m.n_corpus):>7} des Korpus  "
            f"{max(sizes.to_list(), default=0):5d}  "
            f"{by_size[2]}/{by_size[3]}/{by_size[4]}/{by_size[5]}"
        )

    print("\nShingle-Länge k gegen Kanten (je eigenes MinHash, 32×4) und Überlappung mit k = 5:")
    reference: dict[float, set[tuple[str, str]]] = {}
    ids5 = m.meta.get_column("id").to_list()
    for tau in (0.7, 0.8, 0.9):
        reference[tau] = {(ids5[i], ids5[j]) for i, j in m.pairs[m.sim >= tau].tolist()}
    for k in K_VARIANTS:
        other = m if k == K else measure(meta, k=k, wide=False)
        ids = other.meta.get_column("id").to_list()
        cells = []
        for tau in (0.7, 0.8, 0.9):
            edges = {(ids[i], ids[j]) for i, j in other.pairs[other.sim >= tau].tolist()}
            union = edges | reference[tau]
            overlap = len(edges & reference[tau]) / max(len(union), 1)
            cells.append(f"τ={tau:.1f}: {len(edges):4d} Kanten, Jaccard zu k=5 {num(overlap, 2)}")
        fam = family_frame(other, TAU)
        in_families = int(fam.filter(pl.col("groesse") > 1).height)
        print(
            f"  k={k}: " + "; ".join(cells) + f"; Dokumente in Familien bei τ={TAU}: {in_families}"
        )


def proxies(m: Measured) -> None:
    """Labels aus den Metadaten je Ähnlichkeitsstufe: Hinweise, keine Validierung (§ 3.3, § 5).

    Gleicher Titel spricht für „gleiche Sache", ist aber weder nötig (eine Fortschreibung ändert
    den Titel) noch hinreichend (ein wiederkehrender Bericht behält ihn); dieselbe Grundnummer
    (``X`` und ``X/1``) ist ein fast sicheres Zeichen für dieselbe Sache.
    """
    meta = m.meta
    names = [norm_title(t) for t in meta.get_column("name").to_list()]
    refs = [base_reference(r) for r in meta.get_column("reference").to_list()]
    dates = meta.get_column("date").to_list()
    periodic = [bool(PERIODIC.search(t)) for t in names]
    print("\nHinweise aus den Metadaten je Stufe (Gegenprobe 64×2 und 32×4 zusammen):")
    print("  Stufe       Paare  Titel gleich  Grundnummer gleich  ≤ 31 Tage  Bericht im Titel")
    found: dict[tuple[int, int], float] = {}
    for pairs, sims in ((m.wide_pairs, m.wide_sim), (m.pairs, m.sim)):
        for (i, j), s in zip(pairs.tolist(), sims.tolist(), strict=True):
            found[(i, j)] = s
    for lo, hi, _ in STRATA:
        chosen = [(i, j) for (i, j), s in found.items() if lo <= s < hi]
        if not chosen:
            continue
        title = sum(names[i] == names[j] for i, j in chosen) / len(chosen)
        same = sum(refs[i] == refs[j] for i, j in chosen) / len(chosen)
        close = sum(
            dates[i] is not None and dates[j] is not None and abs((dates[i] - dates[j]).days) <= 31
            for i, j in chosen
        ) / len(chosen)
        report = sum(periodic[i] and periodic[j] for i, j in chosen) / len(chosen)
        print(
            f"  {lo:.2f}–{min(hi, 1.0):.2f}  {len(chosen):6d}  {pct(title):>12}  {pct(same):>18}"
            f"  {pct(close):>9}  {pct(report):>16}"
        )


# --- § 3.4 Familien ---------------------------------------------------------------------------


def base_reference(reference: str | None) -> str:
    """Die Drucksachennummer ohne Ergänzungszähler: ``RAT/014/2022/1`` und ``50/ 30/2017 - 1``."""
    if not reference:
        return ""
    match = re.match(r"^(.*?/\s*\d{4})(?:\s*-\s*\d+|/\d+)?$", reference.strip())
    return match.group(1) if match else reference


def norm_title(title: str | None) -> str:
    """Titel ohne den Verweis auf eine Vorlage und ohne Satzzeichen, kleingeschrieben."""
    text = (title or "").lower()
    text = re.sub(r"\s*-?\s*vorlage\s+[a-z0-9]+/\d+/\d{4}(/\d+)?", " ", text)
    return " ".join(TOKEN.findall(text))


def family_kind(members: pl.DataFrame) -> str:
    """Eine beschreibende Typisierung, keine Validierung (13-dubletten.md, § 3.4)."""
    refs = members.get_column("reference").to_list()
    if len({base_reference(r) for r in refs}) < len(refs):
        return "Fortschreibung (/1, /2 derselben Nummer)"
    bodies = {b for b in members.get_column("gremium").to_list() if b}
    types = " ".join(t or "" for t in members.get_column("paper_type").to_list()).lower()
    titles = " ".join(norm_title(t) for t in members.get_column("name").to_list())
    dates = members.get_column("date").drop_nulls()
    span = (dates.max() - dates.min()).days if dates.len() > 1 else 0  # type: ignore[operator, union-attr]
    if len(bodies) > 1:
        if "antrag" in types or "anfrage" in types:
            return "gleicher Antrag oder gleiche Anfrage in mehreren Gremien"
        return "Verteilervorlage (dieselbe Vorlage an mehrere Gremien)"
    if PERIODIC.search(titles) or span > 300:
        return "wiederkehrender Bericht oder Formular (ein Gremium, Abstand > 300 Tage)"
    return "Wiedervorlage im selben Gremium (Abstand ≤ 300 Tage)"


def describe_families(m: Measured, tau: float, examples: int) -> pl.DataFrame:
    fam = family_frame(m, tau)
    members = (
        m.meta.join(fam, on="id", how="left").filter(pl.col("groesse") > 1).sort("familie", "id")
    )
    rows = []
    for (label,), group in members.group_by(["familie"], maintain_order=True):
        rows.append({"familie": int(label), "art": family_kind(group), "n": group.height})
    kinds = pl.DataFrame(rows, schema={"familie": pl.Int64, "art": pl.String, "n": pl.Int64})
    total = int(kinds.get_column("n").sum()) if kinds.height else 0
    print(f"\n--- Familien bei τ = {num(tau, 2)}: {kinds.height} Familien, {total} Dokumente")
    summary = (
        kinds.group_by("art")
        .agg(pl.len().alias("familien"), pl.col("n").sum())
        .sort(["familien", "art"], descending=[True, False])
    )
    for row in summary.iter_rows(named=True):
        print(f"  {row['familien']:4d} Familien, {row['n']:4d} Dokumente: {row['art']}")
    kinds_of = members.join(kinds.select("familie", "art"), on="familie", how="left").sort("id")
    print("  Dokumentarten in Familien (häufigste zehn, Anteil an allen Dokumenten der Art):")
    all_types = m.meta.group_by("paper_type").agg(pl.len().alias("alle"))
    per_type = (
        kinds_of.group_by("paper_type")
        .agg(pl.len().alias("in_familien"))
        .join(all_types, on="paper_type", how="left")
        .sort(["in_familien", "paper_type"], descending=[True, False])
    )
    for row in per_type.head(10).iter_rows(named=True):
        print(
            f"    {row['in_familien']:4d} von {row['alle']:5d} ({pct(row['in_familien'] / row['alle'])}) "
            f"{row['paper_type']}"
        )
    per_kind = kinds_of.group_by("gremium_art").agg(pl.len().alias("n")).sort("n", descending=True)
    print(
        "  Gremienart der Dokumente in Familien: "
        + ", ".join(f"{r['gremium_art']} {r['n']}" for r in per_kind.iter_rows(named=True))
    )
    # Verkettung: wie viele Familien sind Cliquen, d. h. jedes Paar liegt über τ?
    lookup = {(int(i), int(j)): float(s) for (i, j), s in zip(m.pairs.tolist(), m.sim, strict=True)}
    position = {doc: n for n, doc in enumerate(m.meta.get_column("id").to_list())}
    cliques, worst = 0, 1.0
    for _, group in members.group_by(["familie"], maintain_order=True):
        idx = sorted(position[d] for d in group.get_column("id").to_list())
        sims = []
        for x, left in enumerate(idx):
            for right in idx[x + 1 :]:
                if (left, right) in lookup:
                    sims.append(lookup[(left, right)])
                else:
                    a, b = m.sets[left], m.sets[right]
                    common = np.intersect1d(a, b, assume_unique=True).size
                    sims.append(common / (a.size + b.size - common))
        cliques += int(min(sims) >= tau)
        worst = min(worst, min(sims))
    print(
        f"  Verkettung: {cliques} von {kinds.height} Familien sind Cliquen (jedes Paar ≥ τ); "
        f"kleinste Ähnlichkeit innerhalb einer Familie {num(worst)}"
    )
    if examples:
        print("  Beispiele (größte Familien zuerst, je Art höchstens zwei):")
        shown: Counter[str] = Counter()
        order = kinds.sort(["n", "familie"], descending=[True, False])
        for row in order.iter_rows(named=True):
            if shown[row["art"]] >= 2:
                continue
            shown[row["art"]] += 1
            group = members.filter(pl.col("familie") == row["familie"])
            refs = ", ".join(group.get_column("reference").to_list()[:10])
            more = " …" if group.height > 10 else ""
            print(f"    [{row['art']}] {row['n']}: {refs}{more}")
            print(f"        „{(group.get_column('name')[0] or '')[:100]}“")
    return fam


def numbered_revisions(m: Measured) -> None:
    """Fortschreibungen nach der Nummer allein (``X/1`` neben ``X``): wie ähnlich sind sie?

    Das braucht kein MinHash, nur die Drucksachennummer; Vorhaben 14 (Vorgänge) liest sie ohnehin.
    """
    refs = [r or "" for r in m.meta.get_column("reference").to_list()]
    position = {r: i for i, r in enumerate(refs) if r}
    revisions = [
        (i, position[base_reference(r)])
        for i, r in enumerate(refs)
        if r and base_reference(r) != r and base_reference(r) in position
    ]
    suffixed = sum(1 for r in refs if r and base_reference(r) != r)
    sims = []
    for i, j in revisions:
        a, b = m.sets[i], m.sets[j]
        common = np.intersect1d(a, b, assume_unique=True).size
        sims.append(common / (a.size + b.size - common))
    values = np.array(sims) if sims else np.zeros(0)
    print(
        f"\n--- Fortschreibungen nach der Nummer: {suffixed} Dokumente mit Ergänzungszähler, "
        f"{len(revisions)} davon mit der Grundnummer im Korpus; Jaccard zur Grundnummer "
        f"Median {num(float(np.median(values)) if values.size else 0.0)}, "
        f"≥ 0,9: {int((values >= 0.9).sum())}, ≥ 0,7: {int((values >= 0.7).sum())}, "
        f"< 0,5: {int((values < 0.5).sum())}"
    )


# --- § 3.5 Empfindlichkeit --------------------------------------------------------------------


def family_hits(results: pl.DataFrame, fam: pl.DataFrame) -> pl.DataFrame:
    """Je Wahlbezirk: Dokumente mit Treffer und Familien mit Treffer (jede Familie einmal).

    Das ist die Gewichtsvariante ``familie`` in der Form von ``analysis/weights.py``: ein Paar
    (Wahlbezirk, Dokument) bekommt 1/k, wenn k Dokumente seiner Familie den Bezirk treffen; die
    Summe je Bezirk ist die Zahl der Familien. Die Gegenprobe steht in ``family_weights``.
    """
    exploded = results.select(DISTRICT, PAPER_IDS).explode(PAPER_IDS).rename({PAPER_IDS: "id"})
    labelled = (
        exploded.join(fam.select("id", "familie"), on="id", how="left")
        .with_columns(pl.coalesce(pl.col("familie").cast(pl.String), pl.col("id")).alias("f"))
        .sort(DISTRICT, "id")
    )
    weights = family_weights(labelled)
    per_district = labelled.group_by(DISTRICT).agg(
        pl.len().alias("dokumente"), pl.col("f").n_unique().alias("familien")
    )
    summed = weights.group_by(DISTRICT).agg(pl.col("gewicht").sum().alias("summe"))
    checked = per_district.join(summed, on=DISTRICT, how="left").sort(DISTRICT)
    if not (checked.get_column("summe") - checked.get_column("familien")).abs().max() < 1e-9:  # type: ignore[operator]
        raise SystemExit("Gewichtsvariante und Zählung der Familien widersprechen sich")
    return checked.drop("summe")


def family_weights(labelled: pl.DataFrame) -> pl.DataFrame:
    """Gewicht je (Wahlbezirk, Dokument): 1 / Zahl der Dokumente seiner Familie mit Treffer dort."""
    return (
        labelled.with_columns((1.0 / pl.len().over(DISTRICT, "f")).alias("gewicht"))
        .select(DISTRICT, "id", "gewicht")
        .sort(DISTRICT, "id")
    )


def show_regression(label: str, pair: RegressionPair) -> None:
    without = pair.without
    print(
        f"  {label}: alle n={pair.all.n} Steigung {num(pair.all.slope, 4)}, r {num(pair.all.r, 4)}, "
        f"p {num(pair.all.p, 5)}"
        + (
            f"; ohne {list(pair.excluded)} Steigung {num(without.slope, 4)}, r {num(without.r, 4)}, "
            f"p {num(without.p, 5)}"
            if without
            else ""
        )
    )


def sensitivity(profile: Profile, m: Measured, taus: Iterable[float]) -> None:
    results = pl.read_parquet(profile.layout.results)
    exclude = profile.settings.analysis.exclude_districts
    print(
        f"\n=== § 3.5 Empfindlichkeit ({profile.name}): Treffer {int(results.get_column(HITS).sum())}"
        f" in {results.height} Wahlbezirken"
    )
    base = regression_pair(results, exclude)
    show_regression("Tabelle 5 heute", base)
    for tau in taus:
        fam = family_frame(m, tau)
        counted = family_hits(results, fam)
        frame = (
            results.select(DISTRICT, HITS, ELIGIBLE_TOTAL, RATE, "wahlbeteiligung")
            .join(counted, on=DISTRICT, how="left")
            .with_columns(
                (1 - pl.col("familien") / pl.col("dokumente")).alias("verlust"),
                (pl.col("familien") / pl.col(ELIGIBLE_TOTAL)).alias("quote_familie"),
            )
            .sort(DISTRICT)
        )
        if not (frame.get_column("dokumente") == frame.get_column(HITS)).all():
            raise SystemExit("paper_ids und anzahl_treffer widersprechen sich")
        lost = frame.get_column("verlust")
        documents = int(frame.get_column("dokumente").sum())
        families = int(frame.get_column("familien").sum())
        lost_median = float(lost.median() or 0.0)  # type: ignore[arg-type]
        lost_max = float(lost.max() or 0.0)  # type: ignore[arg-type]
        top = frame.sort(["verlust", DISTRICT], descending=[True, False]).head(5)
        print(
            f"\n  τ = {num(tau, 2)}: Treffer {documents} → {families} "
            f"({pct(1 - families / documents)} weniger); "
            f"Verlust je Bezirk Median {pct(lost_median)}, "
            f"größter {pct(lost_max)}; Bezirke mit ≥ 5 %: {int((lost >= 0.05).sum())}"
        )
        print(
            "    am stärksten: "
            + ", ".join(
                f"WB {r[DISTRICT]} {pct(r['verlust'], 2)} ({r['dokumente']}→{r['familien']})"
                for r in top.iter_rows(named=True)
            )
        )
        pair = regression_pair(frame, exclude, x="quote_familie")
        show_regression("Tabelle 5, jede Familie einmal", pair)
        rho = spearman(frame, "quote_familie", RATE)
        print(f"    Rangkorrelation zur heutigen Quote ρ = {num(rho or float('nan'), 4)}")


# --- § 3.6 Perioden ---------------------------------------------------------------------------


def periods(main: Profile) -> None:
    print("\n=== § 3.6 Perioden")
    earlier, later = open_profile(EARLIER), open_profile(LATER)
    frames = [load_meta(main, "2020-2025")]
    for label, profile in (("2014-2020", earlier), ("2025-", later)):
        if profile is None:
            print(f"  {label}: Profil nicht gelaufen (georep --profile … run), ausgelassen")
            continue
        meta = load_meta(profile, label)
        frames.append(meta)
        m = measure(meta, wide=False)
        print(f"\n  Periode {label}: Korpus {m.n_corpus}, mit Shingles {m.meta.height}")
        words = pl.col("text").str.count_matches(r"\w+")
        exact = meta.filter(words >= K).group_by("text").agg(pl.len().alias("n"))
        exact = exact.filter(pl.col("n") > 1)
        short = meta.filter((pl.col("text") != "") & (words < K)).height
        print(
            f"    exakte Dubletten (mindestens {K} Wörter): {exact.height} Gruppen, "
            f"{int(exact.get_column('n').sum()) if exact.height else 0} Dokumente; "
            f"Text mit weniger als {K} Wörtern: {short}"
        )
        for tau in (0.7, 0.8, 0.9):
            fam = family_frame(m, tau)
            sizes = fam.unique("familie").filter(pl.col("groesse") > 1).get_column("groesse")
            n_in = int(sizes.sum()) if sizes.len() else 0
            print(
                f"    τ = {num(tau, 1)}: {sizes.len()} Familien, {n_in} Dokumente "
                f"= {pct(n_in / m.n_corpus)}"
            )
        if label == "2014-2020":
            describe_families(m, TAU, examples=1)
            sensitivity(profile, m, (TAU,))
    # Über die Grenze: alle Perioden zusammen, Kanten zwischen verschiedenen Perioden
    together = pl.concat(frames, how="vertical_relaxed")
    # Dasselbe Paper kann in zwei Perioden stehen (Datum an der Grenze): einmal behalten
    duplicated_ids = together.group_by("id").agg(pl.len().alias("n")).filter(pl.col("n") > 1)
    together = together.unique("id", keep="first", maintain_order=True).sort("id")
    print(f"\n  Über die Grenze: {together.height} Dokumente, {duplicated_ids.height} IDs doppelt")
    m = measure(together, wide=False)
    period = m.meta.get_column("periode").to_list()
    cross = np.array([period[i] != period[j] for i, j in m.pairs.tolist()], dtype=bool)
    for tau in (0.7, 0.8, 0.9):
        keep = cross & (m.sim >= tau)
        kinds = Counter(tuple(sorted((period[i], period[j]))) for i, j in m.pairs[keep].tolist())
        docs = {int(x) for x in m.pairs[keep].ravel().tolist()}
        print(
            f"    τ = {num(tau, 1)}: {int(keep.sum())} Paare über eine Periodengrenze, "
            f"{len(docs)} Dokumente; "
            + ", ".join(f"{a} × {b}: {n}" for (a, b), n in sorted(kinds.items()))
        )
    keep = cross & (m.sim >= TAU)
    meta = m.meta
    ref = meta.get_column("reference").to_list()
    names = meta.get_column("name").to_list()
    types = meta.get_column("paper_type").to_list()
    titles_equal = sum(
        1 for i, j in m.pairs[keep].tolist() if norm_title(names[i]) == norm_title(names[j])
    )
    print(f"    davon mit gleichem Titel (τ = {TAU}): {titles_equal}")
    type_pairs = Counter(
        " / ".join(sorted({types[i] or "", types[j] or ""})) for i, j in m.pairs[keep].tolist()
    )
    print(
        "    Dokumentarten der Paare: "
        + "; ".join(f"{t} {n}" for t, n in type_pairs.most_common(6))
    )
    print("    Beispiele:")
    order = np.argsort(-m.sim[keep], kind="stable")
    for n in order[:8]:
        i, j = m.pairs[keep][n]
        print(
            f"      J={num(float(m.sim[keep][n]))} {ref[i]} ({period[i]}) ~ {ref[j]} ({period[j]}): "
            f"„{(names[i] or '')[:70]}“"
        )


# --- § 4 Stichprobe und Kodieraufgaben --------------------------------------------------------


def sample_pairs(m: Measured) -> pl.DataFrame:
    """Geschichtete Stichprobe über die Ähnlichkeitsstufen, aus Produktion und Gegenprobe."""
    ids = m.meta.get_column("id").to_list()
    found: dict[tuple[int, int], float] = {}
    for pairs, sims in ((m.wide_pairs, m.wide_sim), (m.pairs, m.sim)):
        for (i, j), s in zip(pairs.tolist(), sims.tolist(), strict=True):
            found[(i, j)] = s
    universe = pl.DataFrame(
        {
            "id_a": [ids[i] for i, _ in found],
            "id_b": [ids[j] for _, j in found],
            "jaccard": list(found.values()),
        }
    ).sort("id_a", "id_b")
    rng = np.random.default_rng(SEED)
    strata = [
        universe.filter((pl.col("jaccard") >= lo) & (pl.col("jaccard") < hi))
        for lo, hi, _ in STRATA
    ]
    targets = [
        min(size, stratum.height) for (_, _, size), stratum in zip(STRATA, strata, strict=True)
    ]
    # Eine Schicht mit weniger Paaren als vorgesehen wird ganz genommen; der Rest geht reihum an
    # die Schichten nahe der Schwelle (0,85–0,90, 0,80–0,85, 0,90–0,95, 0,70–0,80).
    missing = SAMPLE_SIZE - sum(targets)
    while missing > 0:
        progressed = False
        for s in TOP_UP:
            if missing and targets[s] < strata[s].height:
                targets[s] += 1
                missing -= 1
                progressed = True
        if not progressed:
            break
    chosen = []
    print("\n=== § 4 Stichprobe: Schichten (Grundgesamtheit, gezogen)")
    for (lo, hi, _), stratum, take in zip(STRATA, strata, targets, strict=True):
        rows = np.sort(rng.choice(stratum.height, size=take, replace=False))
        label = f"{lo:.2f}-{min(hi, 1.0):.2f}"
        chosen.append(
            stratum[rows.tolist()].with_columns(
                pl.lit(label).alias("stufe"), pl.lit(stratum.height).alias("grundgesamtheit")
            )
        )
        print(f"  [{label}] {stratum.height:6d} Paare, gezogen {take}")
    sample = pl.concat(chosen)
    # Reihenfolge mischen, damit die Kodierer die Stufe nicht aus der Position lesen
    order = rng.permutation(sample.height)
    sample = sample[order.tolist()].with_columns(
        pl.format("p{}", pl.int_range(1, sample.height + 1).cast(pl.String).str.zfill(3)).alias(
            "paar"
        )
    )
    selected: pl.DataFrame = sample.select(
        "paar", "id_a", "id_b", "stufe", "grundgesamtheit", pl.col("jaccard").round(4)
    )
    return selected


def sample_csv(sample: pl.DataFrame) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(sample.columns)
    for row in sample.iter_rows():
        writer.writerow([f"{v:.4f}" if isinstance(v, float) else v for v in row])
    return buffer.getvalue()


def excerpt(text: str) -> str:
    """Anfang des Rohtexts, Leerzeilen zusammengezogen, höchstens EXCERPT Zeichen."""
    text = re.sub(r"[ \t\f\r]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:EXCERPT]


def tasks(sample: pl.DataFrame, profile: Profile, messdaten: Path) -> list[dict[str, object]]:
    corpus = load_meta(profile, "2020-2025")
    raw_path = messdaten / "rohtext" / f"{profile.folder}.parquet"
    files = pl.read_parquet(profile.layout.corpus, columns=["id", "file_name"])
    raw = (
        pl.read_parquet(raw_path, columns=["name", "text", "pages"]).rename(
            {"name": "file_name", "text": "rohtext"}
        )
        if raw_path.exists()
        else pl.DataFrame(schema={"file_name": pl.String, "rohtext": pl.String, "pages": pl.Int64})
    )
    docs = corpus.join(files, on="id", how="left").join(raw, on="file_name", how="left").sort("id")
    lookup = {row["id"]: row for row in docs.iter_rows(named=True)}
    codebook = tomllib.loads(CODEBOOK.read_text(encoding="utf-8"))
    options = [option["code"] for option in codebook["optionen"]]
    out: list[dict[str, object]] = []
    for row in sample.iter_rows(named=True):
        entry: dict[str, object] = {
            "vorhaben": "13-dubletten",
            "paar": row["paar"],
            "codebuch": "validierung/13-dubletten/codebuch.toml",
            "optionen": options,
        }
        for side in ("a", "b"):
            doc = lookup[row[f"id_{side}"]]
            text = doc["rohtext"] if doc["rohtext"] else doc["text"]
            entry[side] = {
                "id": doc["id"],
                "drucksache": doc["reference"],
                "titel": doc["name"],
                "datum": str(doc["date"]) if doc["date"] else None,
                "art": doc["paper_type"],
                "gremium": doc["gremium"],
                "seiten": doc["pages"],
                "zeichen": len(text),
                "quelle": "rohtext" if doc["rohtext"] else "kleingeschrieben",
                "ausschnitt": excerpt(text),
            }
        out.append(entry)
    return out


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson-Intervall eines Anteils hits/n (95 % mit z = 1,96)."""
    share = hits / n
    centre = (share + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(share * (1 - share) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def stichprobe(profile: Profile, m: Measured, write: bool, messdaten: Path) -> None:
    sample = sample_pairs(m)
    above = sample.filter(pl.col("jaccard") >= TAU).height
    low, high = wilson(above - 2, above)
    print(
        f"  Rechenbeispiel: {above} gezogene Paare ab τ = {TAU}; wären {above - 2} davon richtig "
        f"({pct((above - 2) / above)}), läge das Wilson-Intervall bei [{num(low)}, {num(high)}]"
    )
    text = sample_csv(sample)
    if write:
        SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
        SAMPLE_CSV.write_text(text, encoding="utf-8")
        target = messdaten / "kodierung" / "13-dubletten" / "aufgaben.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = tasks(sample, profile, messdaten)
        target.write_text(
            "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
            encoding="utf-8",
        )
        longest = max(
            len(str(side["ausschnitt"]))
            for line in lines
            for side in (line["a"], line["b"])
            if isinstance(side, dict)
        )
        print(
            f"  geschrieben: {SAMPLE_CSV} ({sample.height} Paare), {target} (längster Ausschnitt {longest} Zeichen)"
        )
    elif SAMPLE_CSV.exists():
        same = SAMPLE_CSV.read_text(encoding="utf-8") == text
        print(f"  Stichprobe im Repo {'gleich der berechneten' if same else 'WEICHT AB'}")
        if not same:
            raise SystemExit(1)
    else:
        print("  keine Stichprobe im Repo; mit --schreiben anlegen")


# --- § 4.1 Kodierung -------------------------------------------------------------------------


def write_labels(messdaten: Path) -> None:
    """``labels.csv`` aus den Antworten der Kodierer und der Schlichtung, Werte als JSON.

    Keine Ausschnitte, keine Begründungen; die Schlichtung steht nur, wo A und B abweichen, und
    ``uneinig.jsonl`` muss genau diese Paare nennen.
    """
    folder = messdaten / "kodierung" / "13-dubletten"

    def codes(name: str) -> dict[str, str]:
        with (folder / name).open(encoding="utf-8") as handle:
            return {(r := json.loads(line))["paar"]: str(r["code"]) for line in handle}

    a, b = codes("antworten-A.jsonl"), codes("antworten-B.jsonl")
    with (folder / "schlichtung.jsonl").open(encoding="utf-8") as handle:
        settled = {(r := json.loads(line))["paar"]: str(r["entscheid"]["code"]) for line in handle}
    with (folder / "uneinig.jsonl").open(encoding="utf-8") as handle:
        open_pairs = {json.loads(line)["aufgabe"]["paar"] for line in handle}
    disagree = {p for p in a if a[p] != b[p]}
    if set(a) != set(b) or disagree != open_pairs or set(settled) != disagree:
        raise SystemExit("Antworten, uneinig.jsonl und Schlichtung passen nicht zusammen")
    if not set(a.values()) | set(b.values()) | set(settled.values()) <= set(CODES):
        raise SystemExit("ein Code steht nicht im Codebuch")
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["aufgabe", "frage", "kodierer_a", "kodierer_b", "schlichtung", "label"])
    for pair in sorted(a):
        final = settled.get(pair, a[pair])
        writer.writerow(
            [
                pair,
                "code",
                json.dumps(a[pair]),
                json.dumps(b[pair]),
                json.dumps(settled[pair]) if pair in settled else "",
                json.dumps(final),
            ]
        )
    LABELS_CSV.write_text(buffer.getvalue(), encoding="utf-8")
    print(f"  geschrieben: {LABELS_CSV} ({len(a)} Paare, {len(settled)} geschlichtet)")


def read_labels() -> dict[str, dict[str, str | None]]:
    with LABELS_CSV.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {
        r["aufgabe"]: {
            k: (json.loads(r[k]) if r[k] else None)
            for k in ("kodierer_a", "kodierer_b", "schlichtung", "label")
        }
        for r in rows
        if r["frage"] == "code"
    }


@dataclass(frozen=True)
class Stratum:
    label: str  # wie in stichprobe.csv, etwa „0.90-0.95"
    low: float
    population: int
    n: int
    same: int
    strict: int


def strata_from(labels: dict[str, dict[str, str | None]]) -> list[Stratum]:
    with SAMPLE_CSV.open(encoding="utf-8") as handle:
        sample = list(csv.DictReader(handle))
    grouped: dict[str, list[str]] = {}
    population: dict[str, int] = {}
    for row in sample:
        grouped.setdefault(row["stufe"], []).append(str(labels[row["paar"]]["label"]))
        population[row["stufe"]] = int(row["grundgesamtheit"])
    return [
        Stratum(
            label=name,
            low=float(name.split("-")[0]),
            population=population[name],
            n=len(codes),
            same=sum(c in SAME for c in codes),
            strict=sum(c == "gleich" for c in codes),
        )
        for name, codes in sorted(grouped.items(), key=lambda kv: -float(kv[0].split("-")[0]))
    ]


def weighted_precision(
    strata: Sequence[Stratum], tau: float, strict: bool = False
) -> tuple[float, float, float]:
    """Präzision über alle Paare mit J ≥ τ: Mittel der Stufen, gewichtet mit ihrer Grundgesamtheit.

    Das Intervall überträgt die Wilson-Grenzen jeder Stufe mit denselben Gewichten; eine ganz
    gezogene Stufe (n = Grundgesamtheit) trägt keine Unsicherheit. Das ist konservativ (die
    Grenzen addieren sich, statt sich wie Varianzen zu mitteln).
    """
    chosen = [s for s in strata if s.low >= tau - 1e-9]
    total = sum(s.population for s in chosen)
    point = low = high = 0.0
    for s in chosen:
        hits = s.strict if strict else s.same
        share = hits / s.n
        lo, hi = (share, share) if s.n == s.population else wilson_interval(hits, s.n)
        weight = s.population / total
        point += weight * share
        low += weight * lo
        high += weight * hi
    return point, low, high


def kodierung(profile: Profile, m: Measured) -> None:
    print("\n=== § 4.1 Kodierung")
    if not LABELS_CSV.exists():
        print("  noch nicht kodiert: validierung/13-dubletten/labels.csv fehlt")
        return
    labels = read_labels()
    pairs = sorted(labels)
    a = [str(labels[p]["kodierer_a"]) for p in pairs]
    b = [str(labels[p]["kodierer_b"]) for p in pairs]
    final = Counter(str(labels[p]["label"]) for p in pairs)
    alpha4 = krippendorff_alpha([[x, y] for x, y in zip(a, b, strict=True)], "nominal", CODES)
    alpha2 = krippendorff_alpha(
        [[str(x in SAME), str(y in SAME)] for x, y in zip(a, b, strict=True)],
        "nominal",
        ("True", "False"),
    )
    agree4 = sum(x == y for x, y in zip(a, b, strict=True))
    agree2 = sum((x in SAME) == (y in SAME) for x, y in zip(a, b, strict=True))
    print(
        f"  {len(pairs)} Paare; Übereinstimmung Code {agree4}/{len(pairs)}, α {num(alpha4 or 0)}; "
        f"Familie ja/nein {agree2}/{len(pairs)}, α {num(alpha2 or 0)}; geschlichtet "
        f"{sum(1 for p in pairs if labels[p]['schlichtung'])}"
    )
    print(f"  A: {dict(Counter(a))}; B: {dict(Counter(b))}; Label: {dict(final)}")
    strata = strata_from(labels)
    print("  Präzision je Stufe (gleich oder fast gleich; streng: nur gleich), Wilson 95 %:")
    for s in strata:
        lo, hi = wilson_interval(s.same, s.n)
        census = " (ganz gezogen)" if s.n == s.population else ""
        print(
            f"    [{s.label}] N={s.population:5d} n={s.n:3d}{census}: {s.same}/{s.n} = "
            f"{num(s.same / s.n)} [{num(lo)}, {num(hi)}]; streng {s.strict}/{s.n} = "
            f"{num(s.strict / s.n)}; geschätzt gleiche Sache in der Stufe {num(s.population * s.same / s.n, 0)}"
        )
    print("  Präzision ab τ (gewichtet mit der Grundgesamtheit je Stufe):")
    chosen: float | None = None
    for tau in BOUNDS:
        point, low, high = weighted_precision(strata, tau)
        strict, _, _ = weighted_precision(strata, tau, strict=True)
        reached = point >= MIN_PRECISION
        print(
            f"    τ = {num(tau, 2)}: {num(point, 4)} [{num(low)}, {num(high)}], streng {num(strict, 4)}"
            f" — {'erreicht' if reached else 'nicht erreicht'} (≥ {num(MIN_PRECISION, 2)})"
        )
        if reached and chosen is None:
            chosen = tau
    print(
        "  τ* nach der vorab festgelegten Regel: "
        + (
            num(chosen, 2)
            if chosen is not None
            else "keine Grenze erreicht 0,95 → Kriterium verfehlt"
        )
    )
    # Die falschen Paare ab 0,9, mit Nummer: was die Präzision dort drückt
    with SAMPLE_CSV.open(encoding="utf-8") as handle:
        sample = {r["paar"]: r for r in csv.DictReader(handle)}
    refs = dict(m.meta.select("id", "reference").iter_rows())
    names = dict(m.meta.select("id", "name").iter_rows())
    print("  falsch ab 0,9:")
    for pair in pairs:
        row = sample[pair]
        if float(row["jaccard"]) >= TAU and labels[pair]["label"] not in SAME:
            print(
                f"    {pair} J={row['jaccard']} {refs.get(row['id_a'])} ~ {refs.get(row['id_b'])}: "
                f"{labels[pair]['label']}, „{(names.get(row['id_a']) or '')[:60]}“"
            )
    # Was die Metadaten über die Labels sagen (ab 0,7, ungewichtet): Hinweise für eine Fassung 2
    print("  Labels ab 0,7 nach Merkmalen der Metadaten (ungewichtet, gleiche Sache / Paare):")
    dates = dict(m.meta.select("id", "date").iter_rows())
    groups: dict[str, list[bool]] = {}
    for pair in pairs:
        row = sample[pair]
        if float(row["jaccard"]) < 0.7:
            continue
        ra, rb = refs.get(row["id_a"]), refs.get(row["id_b"])
        ta, tb = norm_title(names.get(row["id_a"])), norm_title(names.get(row["id_b"]))
        da, db = dates.get(row["id_a"]), dates.get(row["id_b"])
        same = labels[pair]["label"] in SAME
        keys = [
            "gleiche Grundnummer"
            if base_reference(ra) == base_reference(rb)
            else "andere Grundnummer",
            "Titel gleich" if ta == tb else "Titel verschieden",
            "Berichtswort in beiden Titeln"
            if PERIODIC.search(ta) and PERIODIC.search(tb)
            else "kein gemeinsames Berichtswort",
            "Abstand ≤ 31 Tage"
            if da is not None and db is not None and abs((da - db).days) <= 31
            else "Abstand > 31 Tage",
        ]
        for key in keys:
            groups.setdefault(key, []).append(same)
    for key in sorted(groups):
        values = groups[key]
        print(f"    {key}: {sum(values)}/{len(values)} = {num(sum(values) / len(values))}")
    # Wirkung auf die Zählung: bei der besten Grenze und als Obergrenze über alle Kanten ab 0,5
    sensitivity(profile, m, (TAU, 0.5))
    for lowest in (0.5, 0.3):
        expected_effect(profile, m, strata, lowest)


DRAWS = 200  # Ziehungen der ausgedünnten Kanten in expected_effect


def expected_effect(
    profile: Profile, m: Measured, strata: Sequence[Stratum], lowest: float
) -> None:
    """Wirkung, wenn nur die Kanten zählen, die dieselbe Sache sind: geschätzt durch Ausdünnen.

    Jede Kante ab ``lowest`` (Produktion und Gegenprobe zusammen) bleibt mit der Präzision ihrer
    Stufe stehen, unabhängig von den anderen; je Ziehung die Familien und die Treffer je
    Wahlbezirk. Das unterstellt, dass richtige und falsche Kanten sich nicht nach Wahlbezirk
    unterscheiden; es ist eine Größenordnung, keine Messung je Bezirk.
    """
    found: dict[tuple[int, int], float] = {}
    for pairs, sims in ((m.wide_pairs, m.wide_sim), (m.pairs, m.sim)):
        for (i, j), sim in zip(pairs.tolist(), sims.tolist(), strict=True):
            if sim >= lowest:
                found[(i, j)] = sim
    edges = np.array(sorted(found), dtype=np.int64)
    sims = np.array([found[(int(i), int(j))] for i, j in edges])
    share = np.zeros(len(sims))
    assigned = np.zeros(len(sims), dtype=bool)
    for stratum in sorted(strata, key=lambda s: -s.low):  # die höchste passende Stufe gilt
        hit = (sims >= stratum.low - 1e-12) & ~assigned
        share[hit] = stratum.same / stratum.n
        assigned |= hit
    results = pl.read_parquet(profile.layout.results)
    ids = m.meta.get_column("id")
    rng = np.random.default_rng(SEED)
    totals: list[float] = []
    worst: list[float] = []
    over: list[int] = []
    in_families: list[float] = []
    for _ in range(DRAWS):
        keep = rng.random(len(edges)) < share
        labels = components(m.meta.height, edges, keep)
        sizes = np.bincount(labels)
        in_families.append(float(sizes[sizes > 1].sum()) / m.n_corpus)
        frame = pl.DataFrame({"id": ids, "familie": labels})
        counted = family_hits(results, frame)
        lost = 1 - counted.get_column("familien") / counted.get_column("dokumente")
        families = int(counted.get_column("familien").sum())
        documents = int(counted.get_column("dokumente").sum())
        totals.append(1 - families / documents)
        worst.append(float(lost.max() or 0.0))  # type: ignore[arg-type]
        over.append(int((lost >= 0.05).sum()))

    def spread(values: Sequence[float]) -> str:
        ordered = sorted(values)
        return (
            f"{pct(float(np.mean(ordered)), 2)} "
            f"[{pct(ordered[int(0.025 * len(ordered))], 2)}, {pct(ordered[int(0.975 * len(ordered)) - 1], 2)}]"
        )

    print(
        f"\n  Ausgedünnt ab J = {num(lowest, 1)} ({len(edges)} Kanten, im Mittel "
        f"{num(float(share.sum()), 0)} stehen; {DRAWS} Ziehungen, Seed {SEED}): Dokumente in "
        f"Familien {spread(in_families)}; Treffer weniger {spread(totals)}; größter Verlust eines Wahlbezirks {spread(worst)}; Bezirke mit ≥ 5 %: "
        f"im Mittel {num(float(np.mean(over)), 2)}, höchstens {max(over)}"
    )


# --- Hauptprogramm ----------------------------------------------------------------------------


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for flag in ("kurven", "familien", "empfindlichkeit", "perioden", "stichprobe", "kodierung"):
        parser.add_argument(f"--{flag}", action="store_true")
    parser.add_argument("--schreiben", action="store_true")
    parser.add_argument(
        "--labels-schreiben",
        action="store_true",
        help="labels.csv aus den Antworten unter <messdaten>/kodierung/13-dubletten/ anlegen",
    )
    parser.add_argument("--messdaten", type=Path, default=MESSDATEN)
    args = parser.parse_args(argv)
    chosen = {
        f
        for f in ("kurven", "familien", "empfindlichkeit", "perioden", "stichprobe", "kodierung")
        if getattr(args, f)
    }
    everything = not chosen
    started = time.perf_counter()
    if args.labels_schreiben:
        write_labels(args.messdaten)
    main_profile = open_profile(MAIN)
    if main_profile is None:
        raise SystemExit("Hauptperiode nicht gelaufen: uv run georep run")
    meta = load_meta(main_profile, "2020-2025")
    print(f"Hauptperiode: {meta.height} Dokumente aus {main_profile.layout.corpus}")
    m = measure(meta)
    if everything or "kurven" in chosen:
        exact_duplicates(meta)
        curves(meta, m)
    if everything or "familien" in chosen:
        print("\n=== § 3.4 Familien")
        for tau in (TAU, 0.8, 0.7):
            describe_families(m, tau, examples=2 if tau in (TAU, 0.7) else 0)
        numbered_revisions(m)
    if everything or "empfindlichkeit" in chosen:
        sensitivity(main_profile, m, (0.7, 0.8, TAU))
    if everything or "perioden" in chosen:
        periods(main_profile)
    if everything or "stichprobe" in chosen or args.schreiben:
        stichprobe(main_profile, m, args.schreiben, args.messdaten)
    if everything or "kodierung" in chosen:
        kodierung(main_profile, m)
    print(f"\nLaufzeit insgesamt {num(time.perf_counter() - started, 1)} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
