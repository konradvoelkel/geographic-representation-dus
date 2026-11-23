"""Rechnet die Zahlen von `17-zeit.md` nach (Vorhaben 17 „Zeit und Neuigkeiten").

    uv run python docs/plans/17-zeit-messung.py [--stichprobe] [--labels] [--feeds DIR]

Liest nur, was `georep run` je Profil schreibt (`interim/papers.parquet`,
`processed/papers_gremien.parquet`, `processed/dokumente_urheber.parquet`, für die Feeds dazu
`raw/papers.jsonl`, `processed/combined_searchdict.parquet` und `processed/inverted_index.parquet`;
Pfade aus `georep --profile <p> paths`), das Lexikon `docs/plans/17-zeit-lexikon.toml` und für die
Kodieraufgaben den Rohtext aus Phase 0 (`$GEOREP_MESSDATEN/rohtext/`, Groß- und Kleinschreibung).

Rechnet, in der Reihenfolge des Messdokuments: die Datenlage (§ 2), die drei vorab festgelegten Tests
H17.1 bis H17.3 mit ihren Sensitivitäten und Holm (§ 8, Ergebnisse in § 3), die Ereignisspuren je
Gremium (explorativ), die zeitliche Gegenprobe des Lexikons, und den Prototyp der Atom-Feeds je
Wahlbezirk der laufenden Periode: Feeds schreiben (nach `--feeds`, Vorgabe ein Temporärordner), gegen
RFC 4287 prüfen (die normativen Regeln hier; das RELAX-NG-Schema aus Anhang B, von Hand ins
XML-Format übertragen, mit lxml, wenn ein Python mit lxml da ist — das Paket hat es nicht), Umfang.

Mit `--stichprobe` schreibt es die Stichprobe von 100 Treffern (zehn je Kategorie, Seed 17) nach
`validierung/17-zeit/stichprobe.csv` und die Kodieraufgaben nach
`$GEOREP_MESSDATEN/kodierung/17-zeit/aufgaben.jsonl` (nie ins Repo); ohne den Schalter prüft es nur,
ob die gespeicherte Stichprobe noch dieselbe ist. Das Codebuch (`validierung/17-zeit/codebuch.toml`)
ist von Hand geschrieben.

Liegen die Antworten der Kodierer (`antworten-A.jsonl`, `antworten-B.jsonl`, `schlichtung.jsonl` unter
`$GEOREP_MESSDATEN/kodierung/17-zeit/`), bildet es die Endlabels, rechnet Krippendorffs α, die
Präzision je Kategorie und gesamt (ungewichtet und mit der Population gewichtet, Wilson) und die Ebene
je Kategorie (§ 4.1); mit `--labels` schreibt es `validierung/17-zeit/labels.csv` (nur Labels als
JSON, keine Ausschnitte, keine Begründungen), ohne den Schalter prüft es, ob die Datei noch stimmt. Alle Tabellen, die in Stufe 2 ins Stadtprofil gehören (Wahltage, Muster
der Haushaltsanträge), stehen unten im Block „Profil". Laufzeit rund eine Minute.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator, Sequence
from itertools import combinations
from pathlib import Path
from statistics import median
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

os.environ.setdefault("POLARS_MAX_THREADS", "4")
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from scipy import stats  # noqa: E402

from georep import __version__  # noqa: E402
from georep.analysis.hits import hits_by_district  # noqa: E402
from georep.settings import load_settings  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
ROHTEXT = MESSDATEN / "rohtext"
AUFGABEN = MESSDATEN / "kodierung" / "17-zeit" / "aufgaben.jsonl"
LEXIKON = REPO / "docs" / "plans" / "17-zeit-lexikon.toml"
STICHPROBE = REPO / "validierung" / "17-zeit" / "stichprobe.csv"
CODEBUCH = REPO / "validierung" / "17-zeit" / "codebuch.toml"
KODIERUNG = MESSDATEN / "kodierung" / "17-zeit"
LABELS = REPO / "validierung" / "17-zeit" / "labels.csv"
FRAGEN = ("thema", "ebene")
EBENEN = ("bund", "land_eu", "lokal", "unklar")
SEED = 17
JE_KATEGORIE = 10  # Treffer je Kategorie in der Stichprobe (zehn Kategorien, 100 Treffer)
FENSTER = 350  # Zeichen links und rechts der Fundstelle in einer Kodieraufgabe
FEED_EINTRAEGE = 50  # neueste Dokumente je Feed

# Profil -> Datensatz; die drei Düsseldorfer Perioden sind disjunkt und lückenlos.
PROFILE = (
    ("duesseldorf-2014", "2014-2020"),
    ("duesseldorf", "2020-2025"),
    ("duesseldorf-2025", "2025-"),
)
DATENSAETZE = tuple(d for _, d in PROFILE)
FEED_PROFIL = "duesseldorf-2025"

# ================================================================================================
# Profil (Stufe 2: `[cycles]` im Stadtprofil, mit Quelle)
# ================================================================================================
# Kommunalwahlen NRW (Landeswahlleiterin NRW); die Profile tragen sie als Periodengrenzen.
WAHLEN = (dt.date(2014, 5, 25), dt.date(2020, 9, 13), dt.date(2025, 9, 14))
# Vollständige Wahljahre (1.9. bis 31.8.) je Datensatz; Wahljahr = Jahr seines Septembers.
WAHLJAHRE: dict[str, tuple[int, ...]] = {
    "2014-2020": (2014, 2015, 2016, 2017, 2018, 2019),
    "2020-2025": (2020, 2021, 2022, 2023, 2024),
    "2025-": (2025,),
}
HAUSHALTSANTRAG = r"haushalts(begleit)?-?antrag"  # auf Dokumentart und Titel, kleingeschrieben
HAUSHALT_MINDESTENS = 5  # so viele Haushaltsanträge braucht ein Wahljahr für einen Haushaltsmonat
FRAKTION = ("Fraktion",)
POLITISCH = ("Fraktion", "Person", "unbekannt")
# Reihenfolge der Kalendermonate im Wahljahr: September zuerst.
MONATE_WJ = (9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8)
MONATSNAME = {
    1: "Jan",
    2: "Feb",
    3: "Mär",
    4: "Apr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Okt",
    11: "Nov",
    12: "Dez",
}
# Zeitliche Gegenprobe: vor diesem Tag kann ein Treffer die Kategorie nicht meinen.
ANACHRONISMUS = {
    "corona": (dt.date(2020, 1, 1), ("\\bcorona", "\\bcovid", "sars-cov", "\\blockdown")),
    "energiekrise": (dt.date(2021, 9, 1), None),
    "bundesverkehr": (
        dt.date(2022, 3, 1),
        ("deutschland-?ticket", "\\bd-ticket", "\\b(9|49|58|neun)[-\\s]?(euro|€)[-\\s]?ticket"),
    ),
}
# Ereignisspuren (explorativ): Fenster des Ereignisses gegen dieselben Kalendermonate davor.
EREIGNISSE = (
    ("hochwasser", "Hochwasser Juli 2021", dt.date(2021, 7, 1), 6),
    ("corona", "Pandemie ab März 2020", dt.date(2020, 3, 1), 12),
    ("ukraine_krieg", "Vollinvasion Februar 2022", dt.date(2022, 3, 1), 12),
    ("energiekrise", "Energiekrise 2022", dt.date(2022, 7, 1), 12),
)


# ================================================================================================
# Laden
# ================================================================================================
def paths(profile: str) -> dict[str, str]:
    exe = Path(sys.executable).parent / "georep"
    out = subprocess.run(
        [str(exe), "--profile", profile, "paths"], check=True, capture_output=True, text=True
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def wahljahr(col: str = "date") -> pl.Expr:
    return (pl.col(col).dt.year() - (pl.col(col).dt.month() < 9).cast(pl.Int32)).cast(pl.Int32)


def lade(profile: str, datensatz: str) -> tuple[pl.DataFrame, dict[str, str]]:
    p = paths(profile)
    root = Path(p["root"])
    corpus = pl.read_parquet(
        root / "interim" / "papers.parquet",
        columns=[
            "id",
            "name",
            "reference",
            "date",
            "paper_type",
            "file_name",
            "download_url",
            "text",
        ],
    )
    gremien = pl.read_parquet(
        root / "processed" / "papers_gremien.parquet", columns=["id", "gremium", "gremium_art"]
    )
    urheber = pl.read_parquet(
        root / "processed" / "dokumente_urheber.parquet", columns=["id", "urheber_art"]
    )
    erlaubt = list(WAHLJAHRE[datensatz])
    df = (
        corpus.join(gremien, on="id", how="left")
        .join(urheber, on="id", how="left")
        .with_columns(
            pl.lit(datensatz).alias("datensatz"),
            pl.lit(root.name).alias("ordner"),
            pl.col("text").fill_null(""),
            pl.col("name").fill_null(""),
            pl.col("paper_type").fill_null(""),
        )
        .with_columns(
            (pl.col("text") != "").alias("mit_text"),
            pl.col("date").dt.month().alias("kal"),
            pl.col("date").dt.truncate("1mo").alias("monat"),
            pl.when(wahljahr().is_in(erlaubt)).then(wahljahr()).otherwise(None).alias("wj"),
            (pl.col("name").str.to_lowercase() + " " + pl.col("text")).alias("suchtext"),
            (pl.col("name").str.to_lowercase() + " " + pl.col("text").str.slice(0, 2000)).alias(
                "suchtext_kopf"
            ),
            (
                pl.col("paper_type").str.to_lowercase().str.contains(HAUSHALTSANTRAG)
                | pl.col("name").str.to_lowercase().str.contains(HAUSHALTSANTRAG)
            ).alias("haushaltsantrag"),
            pl.col("urheber_art").is_in(FRAKTION).alias("fraktion"),
            pl.col("urheber_art").is_in(POLITISCH).alias("politisch"),
        )
        .sort("id")
    )
    return df, p


def lexikon() -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    lx = tomllib.loads(LEXIKON.read_text(encoding="utf-8"))
    return lx["meta"], lx["kategorie"], lx.get("lokal", [])


def muster(kategorie: dict[str, object]) -> str:
    return "|".join(f"(?:{m})" for m in kategorie["muster"])  # type: ignore[attr-defined]


def markiere(df: pl.DataFrame, kategorien: Sequence[dict[str, object]]) -> pl.DataFrame:
    """Je Kategorie zwei Spalten: Treffer in Titel und Text, Treffer in Titel und Textkopf."""
    return df.with_columns(
        *[pl.col("suchtext").str.contains(muster(k)).alias(f"k_{k['id']}") for k in kategorien],
        *[
            pl.col("suchtext_kopf").str.contains(muster(k)).alias(f"kk_{k['id']}")
            for k in kategorien
        ],
    )


# ================================================================================================
# Hilfen
# ================================================================================================
def pct(a: float, b: float) -> str:
    return f"{a} von {b} ({100 * a / b:.1f} %)" if b else f"{a} von 0"


def holm(pwerte: dict[str, float], alpha: float = 0.05) -> dict[str, tuple[float, bool]]:
    """Holm-Bonferroni: je Hypothese der angepasste p-Wert und ob sie verworfen wird."""
    order = sorted(pwerte, key=lambda k: pwerte[k])
    m = len(order)
    out: dict[str, tuple[float, bool]] = {}
    laufend = 0.0
    weiter = True
    for i, k in enumerate(order):
        laufend = max(laufend, min(1.0, (m - i) * pwerte[k]))
        weiter = weiter and pwerte[k] <= alpha / (m - i)
        out[k] = (laufend, weiter)
    return out


def ols(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """Koeffizienten, ihre Standardfehler, Freiheitsgrade."""
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    df = len(y) - x.shape[1]
    s2 = float(resid @ resid) / df
    cov = s2 * np.linalg.inv(x.T @ x)
    return beta, np.sqrt(np.diag(cov)), df


def jt_statistik(gruppen: Sequence[Sequence[float]]) -> float:
    s = 0.0
    for i in range(len(gruppen)):
        for j in range(i + 1, len(gruppen)):
            for a in gruppen[i]:
                for b in gruppen[j]:
                    s += 1.0 if a < b else (0.5 if a == b else 0.0)
    return s


def jt_exakt(werte: Sequence[float], groessen: Sequence[int]) -> tuple[float, float, int]:
    """Jonckheere-Terpstra, einseitig steigend, exakt über alle Gruppenzuordnungen."""
    n = len(werte)
    beobachtet: list[list[float]] = []
    start = 0
    for g in groessen:
        beobachtet.append(list(werte[start : start + g]))
        start += g
    jt = jt_statistik(beobachtet)
    zaehler = 0
    gesamt = 0

    def zuordnungen(frei: list[int], rest: Sequence[int]) -> Iterator[list[list[int]]]:
        if not rest:
            yield []
            return
        for wahl in combinations(frei, rest[0]):
            uebrig = [f for f in frei if f not in wahl]
            for weitere in zuordnungen(uebrig, rest[1:]):
                yield [list(wahl), *weitere]

    for z in zuordnungen(list(range(n)), list(groessen)):
        gesamt += 1
        if jt_statistik([[werte[i] for i in g] for g in z]) >= jt - 1e-12:
            zaehler += 1
    return jt, zaehler / gesamt, gesamt


def multimengen_zuordnungen(labels: Sequence[int]) -> Iterator[list[int]]:
    """Alle verschiedenen Anordnungen einer Multimenge (für den Randomisierungstest von H17.2)."""
    zaehlung = Counter(labels)
    schluessel = sorted(zaehlung)
    n = len(labels)

    def rek(frei: list[int], ks: list[int]) -> Iterator[dict[int, int]]:
        if not ks:
            yield {}
            return
        k = ks[0]
        for wahl in combinations(frei, zaehlung[k]):
            uebrig = [f for f in frei if f not in wahl]
            for sub in rek(uebrig, ks[1:]):
                d = dict(sub)
                d.update(dict.fromkeys(wahl, k))
                yield d

    for d in rek(list(range(n)), schluessel):
        yield [d[i] for i in range(n)]


def doppelt_zentriert(a: np.ndarray) -> np.ndarray:
    return a - a.mean(axis=1, keepdims=True) - a.mean(axis=0, keepdims=True) + a.mean()


def wj_name(w: int) -> str:
    return f"{w}/{(w + 1) % 100:02d}"


# ================================================================================================
# § 2 Datenlage
# ================================================================================================
def datenlage(alle: pl.DataFrame, pfade: dict[str, dict[str, str]]) -> None:
    print("\n== § 2 Datenlage")
    for d in DATENSAETZE:
        t = alle.filter(pl.col("datensatz") == d)
        im_wj = t.filter(pl.col("wj").is_not_null())
        print(
            f"{d}: {t.height} Dokumente, {t.filter('mit_text').height} mit Text, "
            f"{t.get_column('date').min()} bis {t.get_column('date').max()}; in Wahljahren "
            f"{im_wj.height}; Fraktion {t.filter('fraktion').height}, politisch "
            f"{t.filter('politisch').height}, Haushaltsanträge {t.filter('haushaltsantrag').height}; "
            f"Text {t.get_column('text').str.len_chars().sum() / 1e6:.1f} Mio. Zeichen, "
            f"Mittel {t.filter('mit_text').get_column('text').str.len_chars().mean():.0f}; "
            f"Ordner {pfade[d]['root']}"
        )


# ================================================================================================
# H17.1 Wahlzyklus
# ================================================================================================
def jahressummen(alle: pl.DataFrame, spalte: str, ohne_monate: Sequence[int] = ()) -> pl.DataFrame:
    return (
        alle.filter(pl.col("wj").is_not_null() & ~pl.col("kal").is_in(list(ohne_monate)))
        .group_by("datensatz", "wj")
        .agg(
            pl.col(spalte).sum().alias("y"),
            pl.len().alias("alle"),
            pl.col("fraktion").sum().alias("fraktion"),
        )
        .sort("wj")
    )


def h171_modell(
    summen: pl.DataFrame, mit_anlauf: bool = False, spalte: str = "y", log: bool = True
) -> dict[str, float]:
    """OLS ln y = μ_Periode + δ·Vorwahljahr über die Vergleichs- und Vorwahljahre."""
    zeilen = []
    for d in ("2014-2020", "2020-2025"):
        jahre = WAHLJAHRE[d]
        nutzbar = jahre if mit_anlauf else jahre[1:]
        for w in nutzbar:
            wert = summen.filter((pl.col("datensatz") == d) & (pl.col("wj") == w)).get_column(
                spalte
            )
            zeilen.append((d, w, float(wert.item()), w == jahre[-1]))
    y = np.array([math.log(z[2]) if log else z[2] for z in zeilen])
    x = np.array(
        [
            [1.0 if z[0] == "2014-2020" else 0.0, 1.0 if z[0] == "2020-2025" else 0.0, float(z[3])]
            for z in zeilen
        ]
    )
    beta, se, df = ols(y, x)
    t = beta[2] / se[2]
    p = float(stats.t.sf(t, df))
    q = float(stats.t.ppf(0.95, df))
    # Randomisierung: welches Nicht-Anlaufjahr je Periode „Vorwahljahr" ist (bei mit_anlauf alle).
    kandidaten = {
        d: [i for i, z in enumerate(zeilen) if z[0] == d] for d in ("2014-2020", "2020-2025")
    }
    gesamt = 0
    groesser = 0
    for a in kandidaten["2014-2020"]:
        for b in kandidaten["2020-2025"]:
            xx = x.copy()
            xx[:, 2] = 0.0
            xx[a, 2] = 1.0
            xx[b, 2] = 1.0
            bb, *_ = np.linalg.lstsq(xx, y, rcond=None)
            gesamt += 1
            groesser += int(bb[2] >= beta[2] - 1e-12)
    return {
        "delta": float(beta[2]),
        "se": float(se[2]),
        "t": float(t),
        "df": df,
        "p": p,
        "lo": float(beta[2] - q * se[2]),
        "hi": float(beta[2] + q * se[2]),
        "p_rand": groesser / gesamt,
        "n_rand": gesamt,
        "n": len(zeilen),
    }


def zeige_h171(name: str, r: dict[str, float], log: bool = True) -> None:
    if log:
        print(
            f"{name}: δ = {r['delta']:.4f} (SE {r['se']:.4f}, t = {r['t']:.3f}, df = {r['df']}), "
            f"Effekt {100 * (math.exp(r['delta']) - 1):+.1f} % (90 %: "
            f"{100 * (math.exp(r['lo']) - 1):+.1f} bis {100 * (math.exp(r['hi']) - 1):+.1f}), "
            f"p einseitig = {r['p']:.4f}; Randomisierung p = {r['p_rand']:.3f} "
            f"({int(r['n_rand'])} Zuordnungen), n = {r['n']}"
        )
    else:
        print(
            f"{name}: δ = {100 * r['delta']:+.2f} Prozentpunkte (SE {100 * r['se']:.2f}, t = "
            f"{r['t']:.3f}, df = {r['df']}), p einseitig = {r['p']:.4f}; Randomisierung p = "
            f"{r['p_rand']:.3f}"
        )


def anfrage_antrag(df: pl.DataFrame) -> pl.DataFrame:
    art = pl.col("paper_type").str.to_lowercase()
    titel = pl.col("name").str.to_lowercase()
    return df.with_columns(
        pl.when(art.str.starts_with("anfrage") | art.str.starts_with("zanfrage"))
        .then(pl.lit("anfrage"))
        .when(
            art.str.starts_with("antrag")
            | art.str.starts_with("zantrag")
            | art.str.starts_with("haushaltsantrag")
        )
        .then(pl.lit("antrag"))
        .when(titel.str.contains(r"\b(z?anfrage|nachfrage)") & ~titel.str.contains("antrag"))
        .then(pl.lit("anfrage"))
        .when(titel.str.contains("antrag"))
        .then(pl.lit("antrag"))
        .otherwise(pl.lit("sonst"))
        .alias("instrument")
    )


def h171(alle: pl.DataFrame) -> float:
    print("\n== H17.1 Wahlzyklus (§ 8.1)")
    summen = jahressummen(alle, "fraktion")
    print("Fraktionsdokumente je Wahljahr (alle Dokumente, Anteil):")
    for row in summen.iter_rows(named=True):
        print(
            f"  {row['datensatz']:9} {wj_name(row['wj'])}: {row['y']:5d} von {row['alle']:5d} "
            f"({100 * row['y'] / row['alle']:.1f} %)"
        )
    haupt = h171_modell(summen)
    zeige_h171("HAUPTTEST H17.1 (Fraktionsdokumente, ohne Anlaufjahre)", haupt)

    print("Sensitivitäten (berichtet, nicht entscheidend):")
    zeige_h171("  S1.1 politische Dokumente", h171_modell(jahressummen(alle, "politisch")))
    zeige_h171(
        "  S1.2 ohne März bis Juni", h171_modell(jahressummen(alle, "fraktion", (3, 4, 5, 6)))
    )
    zeige_h171("  S1.3 Anlaufjahre als Vergleich", h171_modell(summen, mit_anlauf=True))
    anteil = summen.with_columns((pl.col("y") / pl.col("alle")).alias("anteil"))
    zeige_h171(
        "  S1.4 Anteil an allen Dokumenten",
        h171_modell(anteil, spalte="anteil", log=False),
        log=False,
    )
    inst = anfrage_antrag(alle.filter("fraktion"))
    for art in ("anfrage", "antrag"):
        s = jahressummen(inst.with_columns((pl.col("instrument") == art).alias("_i")), "_i")
        zeige_h171(f"  S1.5 nur {art}", h171_modell(s))
    print(
        "  S1.5 sonst (weder Anfrage noch Antrag): "
        + ", ".join(
            f"{d} {inst.filter((pl.col('datensatz') == d) & (pl.col('instrument') == 'sonst')).height}"
            for d in DATENSAETZE
        )
    )
    print("  S1.5 Fraktionsdokumente je Wahljahr nach Instrument (anfrage / antrag / sonst):")
    tab = (
        inst.filter(pl.col("wj").is_not_null())
        .group_by("datensatz", "wj", "instrument")
        .len()
        .sort("wj", "instrument")
    )
    for (d, w), g in tab.group_by(["datensatz", "wj"], maintain_order=True):
        werte = {r["instrument"]: r["len"] for r in g.iter_rows(named=True)}
        print(
            f"    {d:9} {wj_name(int(w))}: {werte.get('anfrage', 0):4d} / "  # type: ignore[call-overload]
            f"{werte.get('antrag', 0):4d} / {werte.get('sonst', 0):4d}"
        )
    print("  S1.6 je Wahl, Vorwahljahr / Mittel der mittleren Jahre:")
    for d in ("2014-2020", "2020-2025"):
        jahre = WAHLJAHRE[d]
        t = summen.filter(pl.col("datensatz") == d)
        letzt = t.filter(pl.col("wj") == jahre[-1]).get_column("y").item()
        mitte = [t.filter(pl.col("wj") == w).get_column("y").item() for w in jahre[1:-1]]
        rang = 1 + sum(v > letzt for v in mitte)
        print(
            f"    Wahl {jahre[-1] + 1}: {letzt} gegen Mittel {sum(mitte) / len(mitte):.1f} "
            f"(Verhältnis {letzt / (sum(mitte) / len(mitte)):.3f}), Rang {rang} von {len(mitte) + 1}"
        )
    # Begleitend: Anlaufjahr (explorativ)
    print(
        "Anlaufjahr (explorativ), erstes Wahljahr / Mittel der mittleren Jahre derselben Periode:"
    )
    for d in ("2014-2020", "2020-2025"):
        jahre = WAHLJAHRE[d]
        t = summen.filter(pl.col("datensatz") == d)
        erst = t.filter(pl.col("wj") == jahre[0]).get_column("y").item()
        mitte = [t.filter(pl.col("wj") == w).get_column("y").item() for w in jahre[1:-1]]
        print(
            f"  {d} {wj_name(jahre[0])}: {erst} gegen {sum(mitte) / len(mitte):.1f} "
            f"({erst / (sum(mitte) / len(mitte)):.3f})"
        )
    erst25 = summen.filter(pl.col("datensatz") == "2025-").get_column("y").item()
    mitte20 = [
        summen.filter((pl.col("datensatz") == "2020-2025") & (pl.col("wj") == w))
        .get_column("y")
        .item()
        for w in WAHLJAHRE["2020-2025"][1:-1]
    ]
    print(
        f"  2025- 2025/26: {erst25} gegen die mittleren Jahre der Hauptperiode "
        f"{sum(mitte20) / len(mitte20):.1f} ({erst25 / (sum(mitte20) / len(mitte20)):.3f}; zwei Räte)"
    )
    return haupt["p"]


# ================================================================================================
# H17.2 Haushaltsrhythmus
# ================================================================================================
def haushaltsmonate(alle: pl.DataFrame) -> dict[int, int | None]:
    """Je Wahljahr der Kalendermonat mit den meisten Haushaltsanträgen (Exposition)."""
    ha = (
        alle.filter(pl.col("wj").is_not_null() & pl.col("haushaltsantrag"))
        .group_by("wj", "kal")
        .len()
    )
    out: dict[int, int | None] = {}
    for w in sorted({w for d in DATENSAETZE for w in WAHLJAHRE[d]}):
        t = ha.filter(pl.col("wj") == w)
        if t.get_column("len").sum() < HAUSHALT_MINDESTENS:
            out[w] = None
            continue
        # Gleichstand: der frühere Monat im Wahljahr
        best = max(t.iter_rows(named=True), key=lambda r: (r["len"], -MONATE_WJ.index(r["kal"])))
        out[w] = int(best["kal"])
    return out


def monatstabelle(alle: pl.DataFrame, spalte: str, jahre: Sequence[int]) -> np.ndarray:
    z = (
        alle.filter(pl.col("wj").is_not_null())
        .group_by("wj", "kal")
        .agg(pl.col(spalte).sum().alias("y"))
    )
    tab = np.zeros((len(jahre), 12))
    for row in z.iter_rows(named=True):
        if row["wj"] in jahre:
            tab[list(jahre).index(row["wj"]), MONATE_WJ.index(row["kal"])] = row["y"]
    return tab


def delta_zwei_wege(yt: np.ndarray, zuordnung: Sequence[int]) -> float:
    t = np.zeros_like(yt)
    for i, kal in enumerate(zuordnung):
        t[i, MONATE_WJ.index(kal)] = 1.0
    tt = doppelt_zentriert(t)
    return float((tt * yt).sum() / (tt * tt).sum())


def h172_test(tab: np.ndarray, zuordnung: Sequence[int]) -> tuple[float, float, float, int]:
    yt = doppelt_zentriert(np.log1p(tab))
    d0 = delta_zwei_wege(yt, zuordnung)
    groesser = 0
    betrag = 0
    gesamt = 0
    for z in multimengen_zuordnungen(zuordnung):
        d = delta_zwei_wege(yt, z)
        gesamt += 1
        groesser += int(d >= d0 - 1e-12)
        betrag += int(abs(d) >= abs(d0) - 1e-12)
    return d0, groesser / gesamt, betrag / gesamt, gesamt


def h172(alle: pl.DataFrame) -> float:
    print("\n== H17.2 Haushaltsrhythmus (§ 8.2)")
    hm = haushaltsmonate(alle)
    jahre = sorted(hm)
    ha = (
        alle.filter(pl.col("wj").is_not_null() & pl.col("haushaltsantrag"))
        .group_by("wj")
        .len()
        .sort("wj")
    )
    print("Exposition: Haushaltsmonat je Wahljahr (Haushaltsanträge im Wahljahr, im Monat):")
    for w in jahre:
        n = ha.filter(pl.col("wj") == w).get_column("len").sum()
        im = (
            alle.filter(
                (pl.col("wj") == w) & pl.col("haushaltsantrag") & (pl.col("kal") == hm[w])
            ).height
            if hm[w]
            else 0
        )
        print(f"  {wj_name(w)}: {MONATSNAME.get(hm[w] or 0, '-')} ({n}, davon {im} im Monat)")
    if any(v is None for v in hm.values()):
        print("  Wahljahre ohne Haushaltsmonat fallen aus dem Test.")
    jahre = [w for w in jahre if hm[w] is not None]
    zuordnung = [int(hm[w]) for w in jahre]  # type: ignore[arg-type]

    def zeige(name: str, spalte: str, df: pl.DataFrame, zweiseitig: bool = False) -> float:
        tab = monatstabelle(df, spalte, jahre)
        d0, p1, p2, n = h172_test(tab, zuordnung)
        print(
            f"{name}: δ = {d0:.4f}, Effekt {100 * (math.exp(d0) - 1):+.1f} %, "
            f"p einseitig = {p1:.5f}, p zweiseitig = {p2:.5f} ({n} Zuordnungen)"
        )
        return p2 if zweiseitig else p1

    tab = monatstabelle(alle, "fraktion", jahre)
    print("Fraktionsdokumente je Wahljahr und Kalendermonat (Sep bis Aug; * = Haushaltsmonat):")
    for i, w in enumerate(jahre):
        zellen = [f"{int(v)}{'*' if MONATE_WJ[j] == hm[w] else ''}" for j, v in enumerate(tab[i])]
        print(f"  {wj_name(w)}: " + " ".join(f"{c:>5}" for c in zellen))
    p = zeige("HAUPTTEST H17.2 (Fraktionsdokumente)", "fraktion", alle)
    ohne = alle.with_columns(
        (pl.col("fraktion") & ~pl.col("haushaltsantrag")).alias("_ohne"), pl.lit(1).alias("_eins")
    )
    zeige("  S2.1 Fraktionsdokumente ohne Haushaltsanträge (zweiseitig)", "_ohne", ohne, True)
    zeige("  S2.2 alle Dokumente", "_eins", ohne)
    tab_o = monatstabelle(ohne, "_ohne", jahre)
    # Beschreibend: Haushaltsmonat gegen denselben Kalendermonat in den anderen Wahljahren
    print(
        "Beschreibend, je Wahljahr: Haushaltsmonat gegen Mittel desselben Kalendermonats ohne Haushalt"
    )
    for i, w in enumerate(jahre):
        j = MONATE_WJ.index(zuordnung[i])
        andere = [k for k in range(len(jahre)) if zuordnung[k] != zuordnung[i]]
        m = np.mean(tab[andere, j])
        mo = np.mean(tab_o[andere, j])
        print(
            f"  {wj_name(w)} {MONATSNAME[zuordnung[i]]}: {int(tab[i, j])} gegen {m:.1f} "
            f"(×{tab[i, j] / m:.2f}); ohne Haushaltsanträge {int(tab_o[i, j])} gegen {mo:.1f} "
            f"(×{tab_o[i, j] / mo:.2f}); Rang im Wahljahr {1 + int((tab[i] > tab[i, j]).sum())}"
        )
    # S2.3: nur Hauptperiode
    haupt = [w for w in WAHLJAHRE["2020-2025"] if w in jahre]
    idx = [jahre.index(w) for w in haupt]
    feb, dez = MONATE_WJ.index(2), MONATE_WJ.index(12)
    print(
        "  S2.3 Hauptperiode: Februar 2021 "
        f"{int(tab[idx[0], feb])} gegen Februar 2022 bis 2025 {np.mean(tab[idx[1:], feb]):.1f}; "
        f"Dezember 2021 bis 2024 {np.mean(tab[idx[1:], dez]):.1f} gegen Dezember 2020 "
        f"{int(tab[idx[0], dez])}"
    )
    return p


# ================================================================================================
# H17.3 Bundespolitisches Vokabular
# ================================================================================================
def h173(alle: pl.DataFrame, kategorien: Sequence[dict[str, object]]) -> float:
    print("\n== H17.3 Bundespolitisches Vokabular (§ 8.3)")
    struktur = [str(k["id"]) for k in kategorien if k["art"] == "struktur"]
    ereignis = [str(k["id"]) for k in kategorien if k["art"] == "ereignis"]
    t = alle.filter("mit_text").with_columns(
        pl.any_horizontal([pl.col(f"k_{k}") for k in struktur]).alias("struktur"),
        pl.any_horizontal([pl.col(f"kk_{k}") for k in struktur]).alias("struktur_kopf"),
        pl.any_horizontal([pl.col(f"k_{k}") for k in struktur + ereignis]).alias("alle_kat"),
        pl.any_horizontal([pl.col(f"k_{k}") for k in struktur if k != "migration_asyl"]).alias(
            "ohne_migration"
        ),
    )

    def je_jahr(spalte: str, df: pl.DataFrame = t) -> list[tuple[str, int, float, int, int]]:
        z = (
            df.filter(pl.col("wj").is_not_null())
            .group_by("datensatz", "wj")
            .agg(pl.col(spalte).sum().alias("a"), pl.len().alias("n"))
            .sort("wj")
        )
        return [
            (r["datensatz"], r["wj"], r["a"] / r["n"], r["a"], r["n"])
            for r in z.iter_rows(named=True)
        ]

    def test(name: str, spalte: str, df: pl.DataFrame = t, zeigen: bool = True) -> float:
        reihe = je_jahr(spalte, df)
        werte = [r[2] for r in reihe]
        groessen = [sum(1 for r in reihe if r[0] == d) for d in DATENSAETZE]
        jt, p, n = jt_exakt(werte, groessen)
        perioden = []
        for d in DATENSAETZE:
            a = sum(r[3] for r in reihe if r[0] == d)
            b = sum(r[4] for r in reihe if r[0] == d)
            perioden.append(100 * a / b)
        print(
            f"{name}: Anteil je Periode {perioden[0]:.2f} / {perioden[1]:.2f} / {perioden[2]:.2f} %, "
            f"Differenz laufende − erste {perioden[2] - perioden[0]:+.2f} Pp.; JT = {jt:.1f}, "
            f"p einseitig = {p:.5f} ({n} Zuordnungen)"
        )
        if zeigen:
            print("  je Wahljahr: " + ", ".join(f"{wj_name(r[1])} {100 * r[2]:.2f}" for r in reihe))
        return p

    p = test("HAUPTTEST H17.3 (Strukturkategorien, Titel und Text)", "struktur")
    print("Sensitivitäten (berichtet, nicht entscheidend):")
    test("  S3.1 nur Titel und erste 2 000 Zeichen", "struktur_kopf")
    test("  S3.2 alle zehn Kategorien", "alle_kat")
    test("  S3.5 nachträglich, explorativ: Strukturkategorien ohne Migration", "ohne_migration")
    print("  S3.3 je Kategorie (explorativ, keine Korrektur):")
    for k in struktur + ereignis:
        test(f"    {k}", f"k_{k}", zeigen=False)
    pol = t.filter("politisch")
    verw = t.filter(pl.col("urheber_art") == "Verwaltung")
    test("  S3.4 politische Dokumente", "struktur", pol, zeigen=False)
    test("  S3.4 Verwaltung", "struktur", verw, zeigen=False)
    print(
        "Muster mit den meisten Dokumenten je Kategorie (alle drei Perioden, Dokumente mit Text):"
    )
    for k in kategorien:
        zaehl = []
        for m in k["muster"]:  # type: ignore[attr-defined]
            n = t.filter(pl.col("suchtext").str.contains(m)).height
            zaehl.append((n, m))
        zaehl.sort(key=lambda x: (-x[0], x[1]))
        print(f"  {k['id']:15} " + "; ".join(f"{m} {n}" for n, m in zaehl[:5] if n))
    # Dokumente mit Text je Periode, Treffer je Kategorie (Zählung, alle Dokumente der Periode)
    print("Dokumente mit Treffer je Kategorie und Periode (alle Dokumente mit Text der Periode):")
    for k in struktur + ereignis:
        teile = []
        for d in DATENSAETZE:
            td = t.filter(pl.col("datensatz") == d)
            teile.append(
                f"{td.filter(pl.col(f'k_{k}')).height} ({100 * td.filter(pl.col(f'k_{k}')).height / td.height:.2f} %)"
            )
        print(f"  {k:15} " + " / ".join(teile))
    return p


def gegenprobe(alle: pl.DataFrame, kategorien: Sequence[dict[str, object]]) -> None:
    """Zeitliche Gegenprobe: Treffer vor dem Ereignis können die Kategorie nicht meinen."""
    print("\n== Zeitliche Gegenprobe des Lexikons (deterministisch)")
    t = alle.filter("mit_text")
    for k, (stichtag, teil) in ANACHRONISMUS.items():
        rx = (
            "|".join(f"(?:{m})" for m in teil)
            if teil
            else muster(next(x for x in kategorien if x["id"] == k))
        )
        hits = t.with_columns(pl.col("suchtext").str.contains(rx).alias("_h")).filter("_h")
        vor = hits.filter(pl.col("date") < stichtag)
        print(
            f"{k} ({'Teilmuster' if teil else 'alle Muster'}): {vor.height} von {hits.height} "
            f"Dokumenten mit Treffer liegen vor dem {stichtag}"
        )
        for row in vor.sort("date").head(6).iter_rows(named=True):
            m = re.search(rx, row["suchtext"])
            ctx = row["suchtext"][max(0, m.start() - 50) : m.end() + 50] if m else ""
            print(f"    {row['date']} {row['reference']}: …{ctx}…")
    # Pandemie vor 2020: welches Teilwort trifft
    pan = t.filter(pl.col("date") < dt.date(2020, 1, 1)).with_columns(
        pl.col("suchtext").str.contains("pandemie").alias("_p")
    )
    print(f'corona, Muster „pandemie" vor 2020: {pan.filter("_p").height} Dokumente')
    es = t.with_columns(pl.col("suchtext").str.contains("energiesicherungs").alias("_e")).filter(
        "_e"
    )
    print(
        "energiekrise, Muster energiesicherungs: "
        + ", ".join(f"{d} {es.filter(pl.col('datensatz') == d).height}" for d in DATENSAETZE)
        + " Dokumente"
    )
    # Kandidaten für Version 2 (nach der Kodierung, § 4.1; nicht festgelegt): was eine Änderung je
    # Kategorie an Dokumenten kostet
    kandidaten = {
        "gendern": ("\\bgendern", "\\bgenderns?\\b"),
        "energiekrise": ("energiesicherungs", None),
        "ukraine_krieg": ("angriffskrieg", "angriffskrieg\\s+(gegen\\s+die\\s+ukraine|russlands)"),
    }
    for kid, (alt, ersatz) in kandidaten.items():
        k = next(x for x in kategorien if x["id"] == kid)
        neu = [ersatz if m == alt else m for m in k["muster"] if not (m == alt and ersatz is None)]  # type: ignore[attr-defined]
        rx2 = "|".join(f"(?:{m})" for m in neu)
        v1 = t.filter(pl.col(f"k_{kid}"))
        v2 = v1.filter(pl.col("suchtext").str.contains(rx2))
        print(
            f"Kandidat Version 2, {kid}: {alt!r} -> {ersatz!r}: {v1.height} -> {v2.height} Dokumente "
            "("
            + ", ".join(
                f"{d} {v1.filter(pl.col('datensatz') == d).height}->{v2.filter(pl.col('datensatz') == d).height}"
                for d in DATENSAETZE
            )
            + ")"
        )
    uk = t.filter(pl.col("k_ukraine_krieg") & (pl.col("date") < dt.date(2022, 2, 24))).sort("date")
    rx_uk = muster(next(x for x in kategorien if x["id"] == "ukraine_krieg"))
    print(f"ukraine_krieg vor dem 24.02.2022: {uk.height} Dokumente")
    for row in uk.iter_rows(named=True):
        m = re.search(rx_uk, row["suchtext"])
        ctx = row["suchtext"][max(0, m.start() - 60) : m.end() + 60] if m else ""
        print(f"    {row['date']} {row['reference']}: …{ctx}…")


# ================================================================================================
# Ereignisspuren (explorativ)
# ================================================================================================
def ereignisse(alle: pl.DataFrame, lokal: Sequence[dict[str, object]]) -> None:
    print("\n== Ereignisspuren je Gremium (explorativ)")
    t = alle.filter("mit_text")
    if lokal:
        t = t.with_columns(
            *[pl.col("suchtext").str.contains(muster(k)).alias(f"k_{k['id']}") for k in lokal]
        )
    for kat, name, beginn, laenge in EREIGNISSE:
        spalte = f"k_{kat}"
        start = dt.date(beginn.year, beginn.month, 1)
        stop = dt.date(
            start.year + (start.month - 1 + laenge) // 12, (start.month - 1 + laenge) % 12 + 1, 1
        )
        vstart = dt.date(start.year - 1, start.month, 1)
        vstop = dt.date(stop.year - 1, stop.month, 1)
        im = t.filter((pl.col("date") >= start) & (pl.col("date") < stop))
        vor = t.filter((pl.col("date") >= vstart) & (pl.col("date") < vstop))
        a, b = im.filter(spalte).height, im.height
        c, d = vor.filter(spalte).height, vor.height
        print(
            f"{name} [{kat}], {start} bis {stop} gegen {vstart} bis {vstop}: stadtweit "
            f"{a}/{b} ({100 * a / b:.1f} %) gegen {c}/{d} ({100 * c / d:.1f} %)"
        )
        monate = (
            t.filter(
                (pl.col("date") >= vstart)
                & (pl.col("date") < dt.date(stop.year + 1, stop.month, 1))
            )
            .group_by("monat")
            .agg(pl.col(spalte).sum().alias("a"), pl.len().alias("n"))
            .sort("monat")
        )
        spitze = (
            monate.with_columns((pl.col("a") / pl.col("n")).alias("q"))
            .sort("q", descending=True)
            .head(1)
        )
        sp = spitze.row(0, named=True)
        print(
            f"  Spitzenmonat {sp['monat']:%Y-%m}: {sp['a']}/{sp['n']} ({100 * sp['q']:.1f} %); "
            "Monatsanteile: "
            + " ".join(
                f"{r['monat']:%y-%m} {100 * r['a'] / r['n']:.0f}"
                for r in monate.iter_rows(named=True)
            )
        )
        gi = im.group_by("gremium").agg(pl.col(spalte).sum().alias("a"), pl.len().alias("n"))
        gv = vor.group_by("gremium").agg(pl.col(spalte).sum().alias("c"), pl.len().alias("d"))
        g = gi.join(gv, on="gremium", how="left").sort(
            ["a", "gremium"], descending=[True, False], nulls_last=True
        )
        zeilen = []
        for row in g.filter(pl.col("n") >= 20).head(8).iter_rows(named=True):
            vq = f"{100 * row['c'] / row['d']:.0f}" if row["d"] else "-"
            zeilen.append(
                f"{row['gremium']} {row['a']}/{row['n']} ({100 * row['a'] / row['n']:.0f} % gegen {vq} %)"
            )
        print("  je Gremium (mindestens 20 Dokumente im Fenster): " + "; ".join(zeilen))


# ================================================================================================
# Stichprobe und Kodieraufgaben
# ================================================================================================
def rohtexte() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for f in sorted(ROHTEXT.glob("*.parquet")):
        r = pl.read_parquet(f, columns=["name", "text"])
        out[f.stem] = dict(
            zip(
                r.get_column("name").to_list(),
                r.get_column("text").fill_null("").to_list(),
                strict=True,
            )
        )
    return out


def ziehe(alle: pl.DataFrame, kategorien: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    """Zehn Dokumente je Kategorie (Seed 17 je Kategorie), je Dokument eine zufällige Fundstelle."""
    zeilen: list[dict[str, object]] = []
    t = alle.filter("mit_text")
    for k in kategorien:
        kid = str(k["id"])
        rx = re.compile(muster(k))
        pop = t.filter(pl.col(f"k_{kid}")).sort("id")
        rng = random.Random(f"{SEED}-{kid}")
        ids = pop.get_column("id").to_list()
        wahl = sorted(rng.sample(ids, min(JE_KATEGORIE, len(ids))))
        for pid in wahl:
            row = pop.filter(pl.col("id") == pid).row(0, named=True)
            treffer = list(rx.finditer(row["suchtext"]))
            assert treffer, f"Python re findet {kid} nicht in {pid}: Muster nicht gleichwertig"
            m = treffer[rng.randrange(len(treffer))]
            titel_laenge = len(row["name"])
            zeilen.append(
                {
                    "id": pid,
                    "kategorie": kid,
                    "periode": row["datensatz"],
                    "stelle": "titel" if m.start() < titel_laenge else "text",
                    "start": m.start(),
                    "treffer": m.group(0),
                    "row": row,
                    "rx": rx,
                }
            )
    ordnung = random.Random(SEED)
    ordnung.shuffle(zeilen)
    for i, z in enumerate(zeilen, 1):
        z["aufgabe"] = f"17-{i:03d}"
    return zeilen


def ausschnitt(z: dict[str, object], roh: dict[str, dict[str, str]]) -> tuple[str, str]:
    """Der Ausschnitt um die Fundstelle, mit ⟦…⟧ markiert; Rohtext, wenn er sie trägt."""
    row = z["row"]  # type: ignore[assignment]
    rx: re.Pattern[str] = z["rx"]  # type: ignore[assignment]
    titel = row["name"]  # type: ignore[index]
    if z["stelle"] == "titel":
        m = rx.search(titel.lower())
        if m:
            return titel[: m.start()] + "⟦" + titel[m.start() : m.end()] + "⟧" + titel[
                m.end() :
            ], "titel"
    text_roh = roh.get(row["ordner"], {}).get(row["file_name"] or "", "")  # type: ignore[index]
    klein = row["suchtext"]  # type: ignore[index]
    rel = (int(z["start"]) - len(titel) - 1) / max(1, len(klein) - len(titel) - 1)  # type: ignore[arg-type]
    if text_roh:
        # dasselbe Fundwort, Leerraum beliebig; erst wenn es fehlt, irgendein Muster der Kategorie
        wort = re.compile(r"\s+".join(re.escape(t) for t in str(z["treffer"]).split()))
        kand = list(wort.finditer(text_roh.lower())) or list(rx.finditer(text_roh.lower()))
        if kand:
            m = min(kand, key=lambda k: abs(k.start() / max(1, len(text_roh)) - rel))
            a, b = max(0, m.start() - FENSTER), min(len(text_roh), m.end() + FENSTER)
            return (
                ("…" if a else "")
                + text_roh[a : m.start()]
                + "⟦"
                + text_roh[m.start() : m.end()]
                + "⟧"
                + text_roh[m.end() : b]
                + ("…" if b < len(text_roh) else ""),
                "rohtext",
            )
    s = int(z["start"])  # type: ignore[arg-type]
    e = s + len(str(z["treffer"]))
    a, b = max(0, s - FENSTER), min(len(klein), e + FENSTER)
    return "…" + klein[a:s] + "⟦" + klein[s:e] + "⟧" + klein[e:b] + "…", "klein"


def stichprobe(
    alle: pl.DataFrame, kategorien: Sequence[dict[str, object]], schreiben: bool
) -> None:
    print("\n== Stichprobe für die Präzision (§ 4)")
    zeilen = ziehe(alle, kategorien)
    spalten = ["aufgabe", "id", "kategorie", "periode", "stelle", "treffer"]
    neu = [[str(z[c]) for c in spalten] for z in zeilen]
    print(
        f"{len(zeilen)} Treffer; je Periode: "
        + ", ".join(
            f"{k} {v}" for k, v in sorted(Counter(str(z["periode"]) for z in zeilen).items())
        )
    )
    print(
        "je Stelle: "
        + ", ".join(
            f"{k} {v}" for k, v in sorted(Counter(str(z["stelle"]) for z in zeilen).items())
        )
    )
    print(
        "Population je Kategorie (Dokumente mit Text und Treffer, alle drei Perioden): "
        + ", ".join(
            f"{k['id']} {alle.filter('mit_text').filter(pl.col(f'k_{k["id"]}')).height}"
            for k in kategorien
        )
    )
    if not schreiben:
        if STICHPROBE.exists():
            with STICHPROBE.open(encoding="utf-8") as fh:
                alt = [r for r in csv.reader(fh)][1:]
            print(f"gespeicherte Stichprobe ist {'dieselbe' if alt == neu else 'NICHT dieselbe'}")
        return
    STICHPROBE.parent.mkdir(parents=True, exist_ok=True)
    with STICHPROBE.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(spalten)
        w.writerows(neu)
    codebuch = tomllib.loads(CODEBUCH.read_text(encoding="utf-8"))
    roh = rohtexte()
    AUFGABEN.parent.mkdir(parents=True, exist_ok=True)
    quellen = Counter()
    with AUFGABEN.open("w", encoding="utf-8") as fh:
        for z in sorted(zeilen, key=lambda z: str(z["aufgabe"])):
            row = z["row"]  # type: ignore[assignment]
            text, quelle = ausschnitt(z, roh)
            quellen[quelle] += 1
            aufgabe = {
                "vorhaben": "17-zeit",
                "aufgabe": z["aufgabe"],
                "codebuch": codebuch["meta"]["version"],
                "id": z["id"],
                "drucksache": row["reference"],  # type: ignore[index]
                "titel": row["name"],  # type: ignore[index]
                "dokumentart": row["paper_type"],  # type: ignore[index]
                "datum": row["date"].isoformat(),  # type: ignore[index]
                "gremium": row["gremium"],  # type: ignore[index]
                "fundwort": z["treffer"],
                "textquelle": quelle,
                "ausschnitt": text,
            }
            fh.write(json.dumps(aufgabe, ensure_ascii=False) + "\n")
    print(
        f"geschrieben: {STICHPROBE} und {AUFGABEN} ({AUFGABEN.stat().st_size} Byte); Textquelle: {dict(quellen)}"
    )


# ================================================================================================
# Kodierung: Endlabels, Übereinstimmung, Präzision, Ebene (§ 4.1)
# ================================================================================================
def lies_jsonl(pfad: Path) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    with pfad.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                o = json.loads(line)
                out[str(o["aufgabe"])] = o
    return out


def wilson(k: float, n: float, z: float = 1.959964) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    nenner = 1 + z * z / n
    mitte = (p + z * z / (2 * n)) / nenner
    halb = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / nenner
    return (max(0.0, mitte - halb), min(1.0, mitte + halb))


def masi(a: frozenset[str], b: frozenset[str]) -> float:
    """MASI-Distanz (Passonneau 2006): 1 − Jaccard · Monotonie."""
    if not a and not b:
        return 0.0
    j = len(a & b) / len(a | b)
    m = 1.0 if a == b else (2 / 3 if a <= b or b <= a else (1 / 3 if a & b else 0.0))
    return 1 - j * m


def jaccard_d(a: frozenset[str], b: frozenset[str]) -> float:
    return 1 - len(a & b) / len(a | b) if a | b else 0.0


def nominal(a: object, b: object) -> float:
    return 0.0 if a == b else 1.0


def krippendorff(paare: Sequence[tuple[object, object]], d: object) -> float:
    """α für zwei Kodierer ohne fehlende Werte: 1 − D_o/D_e über alle paarbaren Werte."""
    dist = d  # type: ignore[assignment]
    werte = [v for paar in paare for v in paar]
    n = len(werte)
    do = sum(dist(a, b) for a, b in paare) / len(paare)  # type: ignore[operator]
    de = sum(dist(werte[i], werte[j]) for i in range(n) for j in range(n) if i != j) / (n * (n - 1))  # type: ignore[operator]
    return 1 - do / de if de else 1.0


def endlabels(
    a: dict[str, dict[str, object]],
    b: dict[str, dict[str, object]],
    s: dict[str, dict[str, object]],
    ordnung: Sequence[str],
) -> list[dict[str, object]]:
    """Je Aufgabe und Frage: A, B, Schlichtung (nur bei Uneinigkeit), Endlabel."""

    def norm(frage: str, wert: object) -> object:
        if frage == "thema":
            return sorted(wert, key=lambda k: ordnung.index(k) if k in ordnung else len(ordnung))  # type: ignore[arg-type]
        return wert

    zeilen: list[dict[str, object]] = []
    for aufgabe in sorted(a):
        entscheid = s.get(aufgabe, {}).get("entscheid", {})
        for frage in FRAGEN:
            va = norm(frage, a[aufgabe][frage])
            vb = norm(frage, b[aufgabe][frage])
            vs = norm(frage, entscheid[frage]) if frage in entscheid else None  # type: ignore[operator]
            if va != vb and vs is None:
                raise SystemExit(f"{aufgabe}/{frage}: uneinig und nicht geschlichtet")
            if va == vb and vs is not None:
                raise SystemExit(f"{aufgabe}/{frage}: geschlichtet, obwohl einig")
            zeilen.append(
                {
                    "aufgabe": aufgabe,
                    "frage": frage,
                    "kodierer_a": va,
                    "kodierer_b": vb,
                    "schlichtung": vs,
                    "label": vs if vs is not None else va,
                }
            )
    return zeilen


def kodierung(alle: pl.DataFrame, kategorien: Sequence[dict[str, object]], schreiben: bool) -> None:
    print("\n== § 4.1 Kodierung: Endlabels, Übereinstimmung, Präzision, Ebene")
    pfade = [KODIERUNG / f for f in ("antworten-A.jsonl", "antworten-B.jsonl", "schlichtung.jsonl")]
    if not all(f.exists() for f in pfade):
        print("keine Antworten der Kodierer gefunden; übersprungen")
        return
    a, b, s = (lies_jsonl(f) for f in pfade)
    with STICHPROBE.open(encoding="utf-8") as fh:
        stich = {r["aufgabe"]: r for r in csv.DictReader(fh)}
    if not (set(a) == set(b) == set(stich)):
        raise SystemExit("Antworten und Stichprobe decken nicht dieselben Aufgaben ab")
    ordnung = [str(k["id"]) for k in kategorien] + ["anderes", "unklar"]
    zeilen = endlabels(a, b, s, ordnung)
    spalten = ["aufgabe", "frage", "kodierer_a", "kodierer_b", "schlichtung", "label"]
    neu = [
        [str(z["aufgabe"]), str(z["frage"])]
        + ["" if z[c] is None else json.dumps(z[c], ensure_ascii=False) for c in spalten[2:]]
        for z in zeilen
    ]
    if schreiben:
        with LABELS.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(spalten)
            w.writerows(neu)
        print(f"geschrieben: {LABELS} ({len(neu)} Zeilen)")
    elif LABELS.exists():
        with LABELS.open(encoding="utf-8") as fh:
            alt = list(csv.reader(fh))[1:]
        print(f"gespeicherte Labels sind {'dieselben' if alt == neu else 'NICHT dieselben'}")
    label = {(str(z["aufgabe"]), str(z["frage"])): z for z in zeilen}
    aufgaben = sorted(stich)

    # Übereinstimmung zwischen den Kodierern
    th = [(frozenset(a[k]["thema"]), frozenset(b[k]["thema"])) for k in aufgaben]  # type: ignore[arg-type]
    eb = [(a[k]["ebene"], b[k]["ebene"]) for k in aufgaben]
    binaer = [
        (stich[k]["kategorie"] in a[k]["thema"], stich[k]["kategorie"] in b[k]["thema"])  # type: ignore[operator]
        for k in aufgaben
    ]
    gleich_th = sum(x == y for x, y in th)
    gleich_eb = sum(x == y for x, y in eb)
    print(
        f"Übereinstimmung thema {gleich_th}/{len(th)} (Jaccard im Mittel "
        f"{sum(1 - jaccard_d(x, y) for x, y in th) / len(th):.3f}), α MASI "
        f"{krippendorff(th, masi):.3f}, α Jaccard {krippendorff(th, jaccard_d):.3f}, α nominal "
        f"(die Menge als ein Wert) {krippendorff(th, nominal):.3f}, α binär "
        f"(Lexikonkategorie im Thema) {krippendorff(binaer, nominal):.3f} "
        f"({sum(x == y for x, y in binaer)}/{len(binaer)} gleich)"
    )
    print(f"Übereinstimmung ebene {gleich_eb}/{len(eb)}, α nominal {krippendorff(eb, nominal):.3f}")
    print(
        f"geschlichtet: {len(s)} Aufgaben; thema "
        f"{sum(1 for k in s if 'thema' in s[k]['entscheid'])}, ebene "  # type: ignore[operator]
        f"{sum(1 for k in s if 'ebene' in s[k]['entscheid'])}; Regeln: "  # type: ignore[operator]
        + ", ".join(sorted({str(s[k]["regel"]).split(" ")[0] for k in s}))
    )
    print(
        "unsicher: A "
        f"{sum(bool(a[k]['unsicher']) for k in aufgaben)}, B {sum(bool(b[k]['unsicher']) for k in aufgaben)}, "
        f"beide {sum(bool(a[k]['unsicher']) and bool(b[k]['unsicher']) for k in aufgaben)}"
    )

    # Präzision je Kategorie und gesamt
    t = alle.filter("mit_text")
    pop = {str(k["id"]): t.filter(pl.col(f"k_{k['id']}")).height for k in kategorien}
    print("Präzision je Kategorie (Endlabel thema enthält die Kategorie; unklar nicht gewertet):")
    richtig_ges = 0
    gewertet_ges = 0
    gewichtet = 0.0
    summe_w2_n = 0.0
    gesamt_pop = sum(pop.values())
    for k in kategorien:
        kid = str(k["id"])
        ids = [x for x in aufgaben if stich[x]["kategorie"] == kid]
        themen = [label[(x, "thema")]["label"] for x in ids]
        unklar = sum(1 for v in themen if v == ["unklar"])
        gewertet = len(ids) - unklar
        richtig = sum(1 for v in themen if kid in v)  # type: ignore[operator]
        lo, hi = wilson(richtig, gewertet)
        falsch = [x for x, v in zip(ids, themen, strict=True) if kid not in v]  # type: ignore[operator]
        print(
            f"  {kid:15} {richtig}/{gewertet} = {richtig / gewertet:.2f} (Wilson {lo:.2f} bis "
            f"{hi:.2f}), unklar {unklar}, Population {pop[kid]}; falsch: "
            + ", ".join(f"{x} ({stich[x]['treffer']})" for x in falsch)
        )
        richtig_ges += richtig
        gewertet_ges += gewertet
        w = pop[kid] / gesamt_pop
        gewichtet += w * richtig / gewertet
        summe_w2_n += w * w / gewertet
    lo, hi = wilson(richtig_ges, gewertet_ges)
    print(
        f"GESAMT ungewichtet {richtig_ges}/{gewertet_ges} = {richtig_ges / gewertet_ges:.3f} "
        f"(Wilson {lo:.3f} bis {hi:.3f}); Kriterium >= 0,9: "
        f"{'erfüllt' if richtig_ges / gewertet_ges >= 0.9 else 'NICHT erfüllt'}"
    )
    n_eff = 1 / summe_w2_n
    lo, hi = wilson(gewichtet * n_eff, n_eff)
    print(
        f"GESAMT mit der Population gewichtet {gewichtet:.3f} (Wilson mit effektivem n = "
        f"{n_eff:.1f}: {lo:.3f} bis {hi:.3f})"
    )
    struktur = [str(k["id"]) for k in kategorien if k["art"] == "struktur"]
    r_s = sum(
        1
        for x in aufgaben
        if stich[x]["kategorie"] in struktur
        and stich[x]["kategorie"] in label[(x, "thema")]["label"]  # type: ignore[operator]
    )
    n_s = sum(1 for x in aufgaben if stich[x]["kategorie"] in struktur)
    lo, hi = wilson(r_s, n_s)
    print(
        f"Strukturkategorien (H17.3) {r_s}/{n_s} = {r_s / n_s:.3f} (Wilson {lo:.3f} bis {hi:.3f})"
    )

    # Ebene je Kategorie
    print(
        "Ebene je Kategorie (Endlabel; bund / land_eu / lokal / unklar), alle zehn und nur richtige:"
    )
    anteil_bund: dict[str, float] = {}
    for k in kategorien:
        kid = str(k["id"])
        ids = [x for x in aufgaben if stich[x]["kategorie"] == kid]
        alle_e = Counter(str(label[(x, "ebene")]["label"]) for x in ids)
        nur_r = Counter(
            str(label[(x, "ebene")]["label"])
            for x in ids
            if kid in label[(x, "thema")]["label"]  # type: ignore[operator]
        )
        anteil_bund[kid] = nur_r["bund"] / max(1, sum(nur_r.values()))
        print(
            f"  {kid:15} alle: "
            + " / ".join(str(alle_e[e]) for e in EBENEN)
            + "; richtige: "
            + " / ".join(str(nur_r[e]) for e in EBENEN)
        )
    for name, gruppe in (
        ("Strukturkategorien", struktur),
        ("Strukturkategorien ohne Migration", [k for k in struktur if k != "migration_asyl"]),
        ("alle zehn", [str(k["id"]) for k in kategorien]),
    ):
        w = sum(pop[k] for k in gruppe)
        wert = sum(pop[k] * anteil_bund[k] for k in gruppe) / w
        print(
            f"Anteil bund unter den richtigen Treffern, mit der Population gewichtet, {name}: {wert:.3f}"
        )
    print(
        "Ebene je Periode (Endlabel, alle 100): "
        + "; ".join(
            f"{d} "
            + " / ".join(
                str(
                    sum(
                        1
                        for x in aufgaben
                        if stich[x]["periode"] == d and label[(x, "ebene")]["label"] == e
                    )
                )
                for e in EBENEN
            )
            for d in DATENSAETZE
        )
    )


# ================================================================================================
# Atom-Feeds je Wahlbezirk (Prototyp)
# ================================================================================================
ATOM = "http://www.w3.org/2005/Atom"
BERLIN = ZoneInfo("Europe/Berlin")
DATUMZEIT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
ABSOLUT = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

# RFC 4287, Anhang B (RELAX NG Compact), von Hand ins XML-Format übertragen; die beiden
# Schematron-Regeln des Anhangs prüft `atom_regeln` (lxml wertet eingebettetes Schematron nicht aus).
# Code-Bestandteile von RFCs dürfen nach den Legal Provisions des IETF Trust (Abschnitt 4) benutzt
# und abgeleitet werden.
ATOM_RNG = """<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0" ns="http://www.w3.org/2005/Atom"
         datatypeLibrary="http://www.w3.org/2001/XMLSchema-datatypes">
  <start><choice><ref name="atomFeed"/><ref name="atomEntry"/></choice></start>
  <define name="atomCommonAttributes">
    <optional><attribute name="xml:base"><ref name="atomUri"/></attribute></optional>
    <optional><attribute name="xml:lang"><ref name="atomLanguageTag"/></attribute></optional>
    <zeroOrMore><ref name="undefinedAttribute"/></zeroOrMore>
  </define>
  <define name="atomPlainTextConstruct">
    <ref name="atomCommonAttributes"/>
    <optional><attribute name="type"><choice><value>text</value><value>html</value></choice></attribute></optional>
    <text/>
  </define>
  <define name="atomXHTMLTextConstruct">
    <ref name="atomCommonAttributes"/>
    <attribute name="type"><value>xhtml</value></attribute>
    <ref name="xhtmlDiv"/>
  </define>
  <define name="atomTextConstruct">
    <choice><ref name="atomPlainTextConstruct"/><ref name="atomXHTMLTextConstruct"/></choice>
  </define>
  <define name="atomPersonConstruct">
    <ref name="atomCommonAttributes"/>
    <interleave>
      <element name="name"><text/></element>
      <optional><element name="uri"><ref name="atomUri"/></element></optional>
      <optional><element name="email"><ref name="atomEmailAddress"/></element></optional>
      <zeroOrMore><ref name="extensionElement"/></zeroOrMore>
    </interleave>
  </define>
  <define name="atomDateConstruct">
    <ref name="atomCommonAttributes"/>
    <data type="dateTime"/>
  </define>
  <define name="atomFeed">
    <element name="feed">
      <ref name="atomCommonAttributes"/>
      <interleave>
        <zeroOrMore><ref name="atomAuthor"/></zeroOrMore>
        <zeroOrMore><ref name="atomCategory"/></zeroOrMore>
        <zeroOrMore><ref name="atomContributor"/></zeroOrMore>
        <optional><ref name="atomGenerator"/></optional>
        <optional><ref name="atomIcon"/></optional>
        <ref name="atomId"/>
        <zeroOrMore><ref name="atomLink"/></zeroOrMore>
        <optional><ref name="atomLogo"/></optional>
        <optional><ref name="atomRights"/></optional>
        <optional><ref name="atomSubtitle"/></optional>
        <ref name="atomTitle"/>
        <ref name="atomUpdated"/>
        <zeroOrMore><ref name="extensionElement"/></zeroOrMore>
      </interleave>
      <zeroOrMore><ref name="atomEntry"/></zeroOrMore>
    </element>
  </define>
  <define name="atomEntry">
    <element name="entry">
      <ref name="atomCommonAttributes"/>
      <interleave>
        <zeroOrMore><ref name="atomAuthor"/></zeroOrMore>
        <zeroOrMore><ref name="atomCategory"/></zeroOrMore>
        <optional><ref name="atomContent"/></optional>
        <zeroOrMore><ref name="atomContributor"/></zeroOrMore>
        <ref name="atomId"/>
        <zeroOrMore><ref name="atomLink"/></zeroOrMore>
        <optional><ref name="atomPublished"/></optional>
        <optional><ref name="atomRights"/></optional>
        <optional><ref name="atomSource"/></optional>
        <optional><ref name="atomSummary"/></optional>
        <ref name="atomTitle"/>
        <ref name="atomUpdated"/>
        <zeroOrMore><ref name="extensionElement"/></zeroOrMore>
      </interleave>
    </element>
  </define>
  <define name="atomInlineTextContent">
    <element name="content">
      <ref name="atomCommonAttributes"/>
      <optional><attribute name="type"><choice><value>text</value><value>html</value></choice></attribute></optional>
      <zeroOrMore><text/></zeroOrMore>
    </element>
  </define>
  <define name="atomInlineXHTMLContent">
    <element name="content">
      <ref name="atomCommonAttributes"/>
      <attribute name="type"><value>xhtml</value></attribute>
      <ref name="xhtmlDiv"/>
    </element>
  </define>
  <define name="atomInlineOtherContent">
    <element name="content">
      <ref name="atomCommonAttributes"/>
      <optional><attribute name="type"><ref name="atomMediaType"/></attribute></optional>
      <zeroOrMore><choice><text/><ref name="anyElement"/></choice></zeroOrMore>
    </element>
  </define>
  <define name="atomOutOfLineContent">
    <element name="content">
      <ref name="atomCommonAttributes"/>
      <optional><attribute name="type"><ref name="atomMediaType"/></attribute></optional>
      <attribute name="src"><ref name="atomUri"/></attribute>
      <empty/>
    </element>
  </define>
  <define name="atomContent">
    <choice>
      <ref name="atomInlineTextContent"/>
      <ref name="atomInlineXHTMLContent"/>
      <ref name="atomInlineOtherContent"/>
      <ref name="atomOutOfLineContent"/>
    </choice>
  </define>
  <define name="atomAuthor"><element name="author"><ref name="atomPersonConstruct"/></element></define>
  <define name="atomCategory">
    <element name="category">
      <ref name="atomCommonAttributes"/>
      <attribute name="term"/>
      <optional><attribute name="scheme"><ref name="atomUri"/></attribute></optional>
      <optional><attribute name="label"/></optional>
      <ref name="undefinedContent"/>
    </element>
  </define>
  <define name="atomContributor"><element name="contributor"><ref name="atomPersonConstruct"/></element></define>
  <define name="atomGenerator">
    <element name="generator">
      <ref name="atomCommonAttributes"/>
      <optional><attribute name="uri"><ref name="atomUri"/></attribute></optional>
      <optional><attribute name="version"/></optional>
      <text/>
    </element>
  </define>
  <define name="atomIcon"><element name="icon"><ref name="atomCommonAttributes"/><ref name="atomUri"/></element></define>
  <define name="atomId"><element name="id"><ref name="atomCommonAttributes"/><ref name="atomUri"/></element></define>
  <define name="atomLogo"><element name="logo"><ref name="atomCommonAttributes"/><ref name="atomUri"/></element></define>
  <define name="atomLink">
    <element name="link">
      <ref name="atomCommonAttributes"/>
      <attribute name="href"><ref name="atomUri"/></attribute>
      <optional><attribute name="rel"><choice><ref name="atomNCName"/><ref name="atomUri"/></choice></attribute></optional>
      <optional><attribute name="type"><ref name="atomMediaType"/></attribute></optional>
      <optional><attribute name="hreflang"><ref name="atomLanguageTag"/></attribute></optional>
      <optional><attribute name="title"/></optional>
      <optional><attribute name="length"/></optional>
      <ref name="undefinedContent"/>
    </element>
  </define>
  <define name="atomPublished"><element name="published"><ref name="atomDateConstruct"/></element></define>
  <define name="atomRights"><element name="rights"><ref name="atomTextConstruct"/></element></define>
  <define name="atomSource">
    <element name="source">
      <ref name="atomCommonAttributes"/>
      <interleave>
        <zeroOrMore><ref name="atomAuthor"/></zeroOrMore>
        <zeroOrMore><ref name="atomCategory"/></zeroOrMore>
        <zeroOrMore><ref name="atomContributor"/></zeroOrMore>
        <optional><ref name="atomGenerator"/></optional>
        <optional><ref name="atomIcon"/></optional>
        <optional><ref name="atomId"/></optional>
        <zeroOrMore><ref name="atomLink"/></zeroOrMore>
        <optional><ref name="atomLogo"/></optional>
        <optional><ref name="atomRights"/></optional>
        <optional><ref name="atomSubtitle"/></optional>
        <optional><ref name="atomTitle"/></optional>
        <optional><ref name="atomUpdated"/></optional>
        <zeroOrMore><ref name="extensionElement"/></zeroOrMore>
      </interleave>
    </element>
  </define>
  <define name="atomSubtitle"><element name="subtitle"><ref name="atomTextConstruct"/></element></define>
  <define name="atomSummary"><element name="summary"><ref name="atomTextConstruct"/></element></define>
  <define name="atomTitle"><element name="title"><ref name="atomTextConstruct"/></element></define>
  <define name="atomUpdated"><element name="updated"><ref name="atomDateConstruct"/></element></define>
  <define name="atomNCName">
    <data type="string"><param name="minLength">1</param><param name="pattern">[^:]*</param></data>
  </define>
  <define name="atomMediaType"><data type="string"><param name="pattern">.+/.+</param></data></define>
  <define name="atomLanguageTag">
    <data type="string"><param name="pattern">[A-Za-z]{1,8}(-[A-Za-z0-9]{1,8})*</param></data>
  </define>
  <define name="atomUri"><text/></define>
  <define name="atomEmailAddress"><data type="string"><param name="pattern">.+@.+</param></data></define>
  <define name="simpleExtensionElement">
    <element><anyName><except><nsName/></except></anyName><text/></element>
  </define>
  <define name="structuredExtensionElement">
    <element>
      <anyName><except><nsName/></except></anyName>
      <choice>
        <group>
          <oneOrMore><attribute><anyName/></attribute></oneOrMore>
          <zeroOrMore><choice><text/><ref name="anyElement"/></choice></zeroOrMore>
        </group>
        <group>
          <zeroOrMore><attribute><anyName/></attribute></zeroOrMore>
          <optional><text/></optional>
          <oneOrMore><ref name="anyElement"/></oneOrMore>
          <zeroOrMore><choice><text/><ref name="anyElement"/></choice></zeroOrMore>
        </group>
      </choice>
    </element>
  </define>
  <define name="extensionElement">
    <choice><ref name="simpleExtensionElement"/><ref name="structuredExtensionElement"/></choice>
  </define>
  <define name="undefinedAttribute">
    <attribute>
      <anyName>
        <except>
          <name ns="http://www.w3.org/XML/1998/namespace">base</name>
          <name ns="http://www.w3.org/XML/1998/namespace">lang</name>
          <nsName ns=""/>
        </except>
      </anyName>
    </attribute>
  </define>
  <define name="undefinedContent">
    <zeroOrMore><choice><text/><ref name="anyForeignElement"/></choice></zeroOrMore>
  </define>
  <define name="anyElement">
    <element>
      <anyName/>
      <zeroOrMore><choice><attribute><anyName/></attribute><text/><ref name="anyElement"/></choice></zeroOrMore>
    </element>
  </define>
  <define name="anyForeignElement">
    <element>
      <anyName><except><nsName/></except></anyName>
      <zeroOrMore><choice><attribute><anyName/></attribute><text/><ref name="anyElement"/></choice></zeroOrMore>
    </element>
  </define>
  <define name="anyXHTML">
    <element>
      <nsName ns="http://www.w3.org/1999/xhtml"/>
      <zeroOrMore><choice><attribute><anyName/></attribute><text/><ref name="anyXHTML"/></choice></zeroOrMore>
    </element>
  </define>
  <define name="xhtmlDiv">
    <element>
      <name ns="http://www.w3.org/1999/xhtml">div</name>
      <zeroOrMore><choice><attribute><anyName/></attribute><text/><ref name="anyXHTML"/></choice></zeroOrMore>
    </element>
  </define>
</grammar>
"""

# Läuft unter einem Python mit lxml (`python3 -I`), liest Schema und Dateien aus argv.
RNG_PRUEFER = """
import json, sys
from lxml import etree
schema = etree.RelaxNG(etree.parse(sys.argv[1]))
out = {}
for f in sys.argv[2:]:
    ok = schema.validate(etree.parse(f))
    out[f] = [ok, [str(e) for e in schema.error_log][:3]]
print(json.dumps(out))
"""


def zeit_atom(d: dt.datetime) -> str:
    return d.isoformat(timespec="seconds")


def feed_xml(
    nr: int, eintraege: list[dict[str, object]], stadt: str, periode: str, slug: str
) -> str:
    """Ein Feed: nur Kennungen, Titel, Datum und Link ins Ratsinformationssystem."""
    fid = uuid.uuid5(uuid.NAMESPACE_URL, f"georep:{slug}/feeds/wahlbezirk-{nr:02d}")
    aktualisiert = max((str(e["updated"]) for e in eintraege), default="1970-01-01T00:00:00+00:00")
    teile = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<feed xmlns="{ATOM}" xml:lang="de">',
        f"  <id>urn:uuid:{fid}</id>",
        f"  <title>Ratsdokumente im Wahlbezirk {nr} ({escape(stadt)}, {escape(periode)})</title>",
        "  <subtitle>Neue Dokumente, in denen ein Straßen- oder Ortsname des Wahlbezirks vorkommt: "
        "Drucksache, Titel, Datum und Link ins Ratsinformationssystem, keine Texte.</subtitle>",
        f"  <updated>{aktualisiert}</updated>",
        "  <author><name>georep, aus dem Ratsinformationssystem (OParl)</name></author>",
        f'  <generator version="{escape(__version__)}">georep</generator>',
        '  <link rel="alternate" type="text/html" href="../index.html"/>',
    ]
    for e in eintraege:
        teile += [
            "  <entry>",
            f"    <id>{escape(str(e['id']))}</id>",
            f"    <title>{escape(str(e['title']))}</title>",
            f"    <published>{e['published']}</published>",
            f"    <updated>{e['updated']}</updated>",
            f'    <link rel="alternate" type="application/pdf" href="{escape(str(e["link"]), {chr(34): "&quot;"})}"/>',
            "  </entry>",
        ]
    teile.append("</feed>")
    return "\n".join(teile) + "\n"


def atom_regeln(pfad: Path) -> list[str]:
    """Die normativen Regeln aus RFC 4287, die das RELAX-NG-Schema nicht ausdrückt, und die eigenen."""
    fehler: list[str] = []
    a = f"{{{ATOM}}}"
    try:
        wurzel = ET.parse(pfad).getroot()
    except ET.ParseError as err:
        return [f"nicht wohlgeformt: {err}"]
    if wurzel.tag != f"{a}feed":
        return [f"Wurzel ist {wurzel.tag}"]

    def genau_eins(el: ET.Element, name: str, wo: str) -> None:
        n = len(el.findall(f"{a}{name}"))
        if n != 1:
            fehler.append(f"{wo}: {n}× {name} (genau eines verlangt)")

    def hoechstens_eins(el: ET.Element, name: str, wo: str) -> None:
        if len(el.findall(f"{a}{name}")) > 1:
            fehler.append(f"{wo}: mehr als ein {name}")

    def datum(el: ET.Element | None, wo: str) -> None:
        if el is None or el.text is None or not DATUMZEIT.match(el.text):
            fehler.append(f"{wo}: Datum nicht nach RFC 3339 (§ 3.3): {getattr(el, 'text', None)!r}")
        else:
            dt.datetime.fromisoformat(el.text.replace("Z", "+00:00"))

    def alternate_einmal(el: ET.Element, wo: str) -> None:
        schl = Counter(
            (k.get("type"), k.get("hreflang"))
            for k in el.findall(f"{a}link")
            if k.get("rel", "alternate") == "alternate"
        )
        if any(v > 1 for v in schl.values()):
            fehler.append(f"{wo}: zwei alternate-Links mit gleichem type und hreflang (§ 4.1.1)")

    for name in ("id", "title", "updated"):
        genau_eins(wurzel, name, "feed")
    for name in ("generator", "icon", "logo", "rights", "subtitle"):
        hoechstens_eins(wurzel, name, "feed")
    datum(wurzel.find(f"{a}updated"), "feed/updated")
    fid = wurzel.findtext(f"{a}id") or ""
    if not ABSOLUT.match(fid):
        fehler.append(f"feed/id nicht absolut (§ 4.2.6): {fid!r}")
    alternate_einmal(wurzel, "feed")
    eintraege = wurzel.findall(f"{a}entry")
    hat_autor = wurzel.find(f"{a}author") is not None
    ids: list[str] = []
    juengstes = ""
    erlaubt = {f"{a}{n}" for n in ("id", "title", "updated", "published", "link")}
    for i, e in enumerate(eintraege):
        wo = f"entry {i + 1}"
        for name in ("id", "title", "updated"):
            genau_eins(e, name, wo)
        for name in ("published", "content", "summary", "rights", "source"):
            hoechstens_eins(e, name, wo)
        datum(e.find(f"{a}updated"), f"{wo}/updated")
        if e.find(f"{a}published") is not None:
            datum(e.find(f"{a}published"), f"{wo}/published")
        if not hat_autor and e.find(f"{a}author") is None:
            fehler.append(f"{wo}: weder Feed noch Eintrag haben einen author (§ 4.1.1)")
        if e.find(f"{a}content") is None and not any(
            k.get("rel", "alternate") == "alternate" for k in e.findall(f"{a}link")
        ):
            fehler.append(f"{wo}: ohne content und ohne alternate-Link (§ 4.1.2)")
        alternate_einmal(e, wo)
        eid = e.findtext(f"{a}id") or ""
        if not ABSOLUT.match(eid):
            fehler.append(f"{wo}: id nicht absolut: {eid!r}")
        ids.append(eid)
        juengstes = max(juengstes, e.findtext(f"{a}updated") or "")
        # Projektregel: keine Texte, nur Kennung, Titel, Datum, Link
        fremd = {c.tag for c in e} - erlaubt
        if fremd:
            fehler.append(
                f"{wo}: Elemente außer id, title, updated, published, link: {sorted(fremd)}"
            )
    if len(ids) != len(set(ids)):
        fehler.append("zwei Einträge mit derselben id")
    if eintraege and (wurzel.findtext(f"{a}updated") or "") != juengstes:
        fehler.append("feed/updated ist nicht das jüngste updated der Einträge (Projektregel)")
    return fehler


def rng_pruefen(schema: Path, dateien: Sequence[Path]) -> dict[str, list[object]] | None:
    """RELAX NG mit lxml; das Paket hat lxml nicht, also ein Python mit lxml, wenn es eines gibt."""
    for py in (shutil.which("python3"), "/usr/bin/python3"):
        if not py:
            continue
        try:
            out = subprocess.run(
                [py, "-I", "-c", RNG_PRUEFER, str(schema), *map(str, dateien)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError, OSError:
            continue
        return json.loads(out.stdout)  # type: ignore[no-any-return]
    return None


def feeds(ziel: Path) -> None:
    print("\n== Atom-Feeds je Wahlbezirk (Prototyp, laufende Periode)")
    s = load_settings(profile=FEED_PROFIL)
    p = paths(FEED_PROFIL)
    root = Path(p["root"])
    korpus = pl.read_parquet(
        root / "interim" / "papers.parquet",
        columns=["id", "name", "reference", "date", "paper_type", "download_url"],
    )
    modified: dict[str, str] = {}
    with (root / "raw" / "papers.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if o.get("modified"):
                modified[o["id"]] = o["modified"]
    woerterbuch = pl.read_parquet(root / "processed" / "combined_searchdict.parquet")
    index = pl.read_parquet(root / "processed" / "inverted_index.parquet")
    bezirke = (
        hits_by_district(woerterbuch, index)
        .select("wahlkreis_id", "paper_ids")
        .sort("wahlkreis_id")
    )
    meta = {r["id"]: r for r in korpus.iter_rows(named=True)}
    stand = korpus.get_column("date").max()
    print(
        f"{korpus.height} Dokumente, {len(modified)} mit OParl-modified, letztes Datum {stand}; "
        f"{bezirke.height} Wahlbezirke"
    )
    if ziel.exists():
        shutil.rmtree(ziel)
    (ziel / "feeds").mkdir(parents=True)
    rng_datei = ziel / "atom.rng"
    rng_datei.write_text(ATOM_RNG, encoding="utf-8")

    def eintrag(pid: str) -> dict[str, object]:
        r = meta[pid]
        tag = dt.datetime.combine(r["date"], dt.time(0, 0), tzinfo=BERLIN)
        mod = modified.get(pid)
        upd = dt.datetime.fromisoformat(mod) if mod else tag
        url = r["download_url"] or ""
        if url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        return {
            "id": pid,
            "title": f"{r['reference']}: {r['name']}" if r["reference"] else r["name"],
            "published": zeit_atom(tag),
            "updated": zeit_atom(max(upd, tag)),
            "link": url,
            "date": r["date"],
        }

    def je_bezirk() -> Iterator[tuple[int, list[dict[str, object]]]]:
        for row in bezirke.iter_rows(named=True):
            yield (
                int(row["wahlkreis_id"]),
                sorted(
                    (eintrag(pid) for pid in row["paper_ids"] if pid in meta),
                    key=lambda e: (e["date"], e["updated"], e["id"]),
                    reverse=True,
                ),
            )

    def baue(ordner: Path) -> list[Path]:
        ordner.mkdir(parents=True, exist_ok=True)
        out = []
        for nr, alle_e in je_bezirk():
            xml = feed_xml(
                nr,
                alle_e[:FEED_EINTRAEGE],
                s.city.name,
                s.period.label,
                f"{s.city.slug}/{root.name}",
            )
            f = ordner / f"wahlbezirk-{nr:02d}.xml"
            f.write_text(xml, encoding="utf-8")
            out.append(f)
        return out

    dateien = baue(ziel / "feeds")
    groessen = [f.stat().st_size for f in dateien]
    spannen: list[int] = []
    je_woche: list[float] = []
    letzte_30: list[int] = []
    ohne_link = 0
    tage = (stand - s.period.start).days + 1
    for _, alle_e in je_bezirk():
        ohne_link += sum(1 for e in alle_e if not e["link"])
        auswahl = alle_e[:FEED_EINTRAEGE]
        if auswahl:
            spannen.append((auswahl[0]["date"] - auswahl[-1]["date"]).days)  # type: ignore[operator]
        je_woche.append(7 * len(alle_e) / tage)
        letzte_30.append(sum(1 for e in alle_e if (stand - e["date"]).days < 30))  # type: ignore[operator]
    print(
        f"{len(dateien)} Feeds, je höchstens {FEED_EINTRAEGE} Einträge; Größe {min(groessen)} bis "
        f"{max(groessen)} Byte, Median {median(groessen):.0f}, zusammen {sum(groessen) / 1024:.1f} KB"
    )
    print(
        f"Zeitspanne der {FEED_EINTRAEGE} neuesten Einträge: {min(spannen)} bis {max(spannen)} Tage, "
        f"Median {median(spannen):.0f}; neue Dokumente je Wahlbezirk und Woche: {min(je_woche):.1f} bis "
        f"{max(je_woche):.1f}, Median {median(je_woche):.1f}; in den letzten 30 Tagen vor {stand}: "
        f"{min(letzte_30)} bis {max(letzte_30)}, Median {median(letzte_30):.0f}; Einträge ohne Link {ohne_link}"
    )
    regelfehler = {f.name: atom_regeln(f) for f in dateien}
    schlecht = {k: v for k, v in regelfehler.items() if v}
    print(
        f"RFC-4287-Regeln (normativ, dazu Projektregeln): {len(dateien) - len(schlecht)} von {len(dateien)} ohne Fehler"
    )
    for k, v in list(schlecht.items())[:5]:
        print(f"  {k}: {v[:3]}")
    rng = rng_pruefen(rng_datei, dateien)
    if rng is None:
        print("RELAX NG: nicht geprüft (kein Python mit lxml gefunden)")
    else:
        gut = sum(1 for v in rng.values() if v[0])
        print(f"RELAX NG (RFC 4287 Anhang B, lxml): {gut} von {len(rng)} gültig")
        for k, v in list((k, v) for k, v in rng.items() if not v[0])[:3]:
            print(f"  {Path(k).name}: {v[1]}")
    # Gegenprobe der Prüfer: ein absichtlich kaputter Feed muss durchfallen
    kaputt = ziel / "kaputt.xml"
    kaputt.write_text(
        dateien[0]
        .read_text(encoding="utf-8")
        .replace("<updated>", "<updated>gestern", 1)
        .replace("  <title>", "  <titel>", 1)
        .replace("</title>\n  <subtitle>", "</titel>\n  <subtitle>", 1),
        encoding="utf-8",
    )
    kr = atom_regeln(kaputt)
    kn = rng_pruefen(rng_datei, [kaputt])
    print(
        f"Gegenprobe kaputter Feed: Regeln melden {len(kr)} Fehler; RELAX NG "
        f"{'gültig (FALSCH)' if kn and list(kn.values())[0][0] else 'ungültig (richtig)' if kn else 'nicht geprüft'}"
    )
    kaputt.unlink()
    # Determinismus: ein zweiter Bau ergibt dieselben Bytes (der Monitor schriebe sonst täglich neu)
    zweit = baue(ziel / "zweit")
    gleich = all(a.read_bytes() == b.read_bytes() for a, b in zip(dateien, zweit, strict=True))
    shutil.rmtree(ziel / "zweit")
    print(f"Determinismus: zweiter Bau {'bytegleich' if gleich else 'VERSCHIEDEN'}")
    print(f"Feeds liegen in {ziel / 'feeds'}")
    beispiel = dateien[0].read_text(encoding="utf-8").splitlines()
    print("Beispiel (Kopf und erster Eintrag):\n  " + "\n  ".join(beispiel[:17]))


# ================================================================================================
# Hauptteil
# ================================================================================================
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--stichprobe", action="store_true", help="Stichprobe und Kodieraufgaben schreiben"
    )
    ap.add_argument("--feeds", type=Path, default=None, help="Ordner für den Feed-Prototyp")
    ap.add_argument("--labels", action="store_true", help="Endlabels nach validierung/ schreiben")
    args = ap.parse_args()
    t0 = time.perf_counter()
    meta, kategorien, lokal = lexikon()
    print(
        f"Lexikon {meta['name']}, Version {meta['version']}: {len(kategorien)} Kategorien, "
        f"{sum(len(k['muster']) for k in kategorien)} Muster"
    )  # type: ignore[arg-type]
    teile = []
    pfade: dict[str, dict[str, str]] = {}
    for profile, d in PROFILE:
        df, p = lade(profile, d)
        teile.append(df)
        pfade[d] = p
    alle = markiere(pl.concat(teile, how="vertical_relaxed"), kategorien)
    print(f"geladen und markiert in {time.perf_counter() - t0:.1f} s")
    datenlage(alle, pfade)
    p1 = h171(alle)
    p2 = h172(alle)
    p3 = h173(alle, kategorien)
    print("\n== Holm über die Familie (α = 0,05)")
    for k, (padj, verworfen) in holm({"H17.1": p1, "H17.2": p2, "H17.3": p3}).items():
        roh = {"H17.1": p1, "H17.2": p2, "H17.3": p3}[k]
        print(
            f"{k}: p = {roh:.5f}, Holm-angepasst {padj:.5f}, {'bestätigt' if verworfen else 'nicht bestätigt'}"
        )
    gegenprobe(alle, kategorien)
    ereignisse(alle, lokal)
    stichprobe(alle, kategorien, args.stichprobe)
    kodierung(alle, kategorien, args.labels)
    ziel = args.feeds or Path(tempfile.mkdtemp(prefix="georep-17-feeds-"))
    feeds(ziel)
    print(f"\nLaufzeit {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
