"""Rechnet die Zahlen von `16-ortsbezug.md` nach (Vorhaben 16, Stufe 1: Ortsbezug verfeinern).

    uv run python docs/plans/16-ortsbezug-messung.py               # alle Zahlen, rund vier Minuten
    uv run python docs/plans/16-ortsbezug-messung.py --aufgaben    # dazu Stichprobe und Kodieraufgaben

Liest nur: den Korpus der Hauptperiode nach `georep run` (`interim/papers.parquet`, Index,
Wörterbuch, Straßen und Orte je Wahlbezirk, Auswertung, Stimmbezirke), den Rohtext der Messdatei
(`messdaten/rohtext/duesseldorf.parquet`, pypdf 7.1.0 mit Groß- und Kleinschreibung, Zeilen und
Seitenwechseln), das Regelwerk von Vorhaben 11 (`docs/plans/11-struktur-messung.py`, Fassung
`struktur-entwurf-1`, unverändert importiert) und Fremddaten unter
`/media/konrad/xtraspace/georep/fremddaten/opendata/` (Größe und SHA-256 werden vor dem Lesen gegen
die README dort geprüft). Schreibt nur mit `--aufgaben`: `validierung/16-ortsbezug/stichprobe.csv`
(nur IDs) ins Repo und die Kodieraufgaben mit Textausschnitten nach
`messdaten/kodierung/16-ortsbezug/` (nie ins Repo, plan-vorverarbeitung-2026-11.md § 4).

Wie die Stelle eines Treffers entsteht: der Index der Arbeit sucht im Textstore, der aus dem Rohtext
durch Entfernen der Zeilenumbrüche (auch der Seitenwechsel), Kleinschreiben und Abschneiden vor dem
ersten „betrifft" entsteht (`prep/extract.py`). Das Skript baut denselben Text aus der Messdatei,
merkt sich je Zeichen die Stelle im Rohtext, prüft, dass er dem Textstore gleich ist, und sucht dort
mit demselben Matcher (flashtext) die Begriffe samt Stelle. So liegt jeder Treffer des Index auf
Zeichen genau im Rohtext, und die Abschnitte von Vorhaben 11 sagen, in welchem Teil er steht.

Personennamen werden nie ausgegeben; Adressen nur als Zahlen (Anteile), nie als Beispiel, weil in
Eingaben Anschriften von Privatpersonen stehen.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import polars as pl
from flashtext import KeywordProcessor
from scipy.stats import pearsonr, spearmanr
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from georep.analysis.hits import citywide_terms
from georep.analysis.regression import regression_pair
from georep.prep.extract import after_marker
from georep.settings import load_settings

ROOT = Path(__file__).resolve().parents[2]
MESSDATEN = Path("/media/konrad/xtraspace/georep/messdaten")
ROHTEXT = MESSDATEN / "rohtext" / "duesseldorf.parquet"
AUFGABEN_DIR = MESSDATEN / "kodierung" / "16-ortsbezug"
VALIDIERUNG = ROOT / "validierung" / "16-ortsbezug"
FREMDDATEN = Path("/media/konrad/xtraspace/georep/fremddaten/opendata")
STRUKTUR = ROOT / "docs" / "plans" / "11-struktur-messung.py"
EXTRACTOR = "ortsbezug-entwurf-1"
SEED = 20261123  # Tag der Messung; Stichprobe und Reihenfolge der Aufgaben hängen nur an ihm
STICHPROBE = 200
MINDESTENS_JE_SCHICHT = 30
MAX_ZEILEN_AUFGABE = 600  # wie Vorhaben 11; Zeilen mit Treffern dahinter kommen als Auszug dazu
AUSZUG_RAND = 6  # Zeilen vor und nach einem Treffer jenseits von Zeile 600

# --- Stelle eines Treffers ----------------------------------------------------------------------
# Feine Stelle: die Abschnittsart von Vorhaben 11 (Ebene 1), in der das erste Zeichen des Treffers
# liegt. Grobe Stelle: fünf Klassen, nach denen die Regel fragt. „Kern" ist der Teil, über den
# abgestimmt oder nach dem gefragt wird (Beschlussvorschlag, Fragen einer Anfrage); „Begleittext"
# ist, was ihn begründet oder berichtet; „Rest" ist alles andere bis hin zum Text außerhalb jedes
# Abschnitts (Anlagenliste, Kopf, Tabellen hinter der Unterschrift, angehängte Seiten).
GROB = {
    "betreff": "betreff",
    "beschlussvorschlag": "kern",
    "fragen": "kern",
    "sachdarstellung": "begleittext",
    "begruendung": "begleittext",
    "stellungnahme": "begleittext",
    "beschlusslage": "begleittext",
    "alternative": "begleittext",
    "rumpf": "begleittext",
}
RANG = {"titel": 0, "betreff": 1, "kern": 2, "begleittext": 3, "rest": 4}
STELLEN = ["titel", "betreff", "kern", "begleittext", "rest"]

# --- Die Regel (vorab festgelegt am 2026-11-23, vor jeder Kodierung) ------------------------------
# Ein Paar (Dokument, Wahlbezirk) „handelt von" einem Ort des Bezirks, wenn mindestens ein Begriff
# seines Wörterbuchs im Titel, im Betreff oder im Kern des Dokuments steht; sonst „erwähnt" es ihn.
REGEL_HANDELT_VON = frozenset({"titel", "betreff", "kern"})
# Nebenregeln, an derselben Kodierung gemessen und als explorativ berichtet: A nimmt die
# Häufigkeit dazu (drei Erwähnungen im Begleittext), B nur Titel und Betreff, C dazu Listen und
# Adressen im Begleittext (der Begriff beginnt eine kurze Zeile, wie in Maßnahmen-, Förder- und
# Fällisten, oder trägt eine Hausnummer).
NEBEN_A_MIN_BEGLEIT = 3
NEBEN_B = frozenset({"titel", "betreff"})
LISTE_MAX_ZEILE = 60  # Zeichen der Zeile ohne Leerraum am Rand
LISTE_MAX_VORLAUF = 12  # Zeichen vor dem Begriff in dieser Zeile („14 ", „1. ", „6 Anlage ")
# Gewicht nach Stelle (Sensitivität, kein Ergebnis der Validierung): bestes Gewicht über alle
# Treffer des Paares, jeder Faktor in [0, 1] wie in analysis/weights.py.
GEWICHT_STELLE = {"titel": 1.0, "betreff": 1.0, "kern": 1.0, "begleittext": 0.5, "rest": 0.25}


def load_struktur() -> ModuleType:
    """Das Messskript von Vorhaben 11 als Modul, ohne seinen `main` zu starten."""
    spec = importlib.util.spec_from_file_location("struktur11", STRUKTUR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["struktur11"] = module  # dataclasses mit `from __future__ import annotations`
    spec.loader.exec_module(module)
    return module


def wilson(part: int, whole: int, z: float = 1.959964) -> tuple[float, float]:
    if not whole:
        return (math.nan, math.nan)
    p = part / whole
    d = 1 + z * z / whole
    c = p + z * z / (2 * whole)
    h = z * ((p * (1 - p) / whole + z * z / (4 * whole * whole)) ** 0.5)
    return ((c - h) / d, (c + h) / d)


def pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.1f} %" if whole else "–"


def wil(part: int, whole: int) -> str:
    lo, hi = wilson(part, whole)
    return f"{pct(part, whole)} ({100 * lo:.1f}–{100 * hi:.1f})" if whole else "–"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_file(path: Path, expected_sha: str) -> Path:
    """Fremddaten nur lesen, wenn die Prüfsumme der README stimmt."""
    found = sha256(path)
    if found != expected_sha:
        raise SystemExit(f"{path}: SHA-256 {found} statt {expected_sha} (README)")
    return path


# --------------------------------------------------------------------------------------------
# Daten
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Daten:
    corpus: pl.DataFrame  # id, reference, name, paper_type, date, store, raw
    dictionary: dict[int, list[str]]  # Wahlbezirk -> Begriffe
    term_districts: dict[str, list[int]]  # Begriff -> Wahlbezirke
    term_type: dict[str, str]  # Begriff -> strasse | ort | beides
    index: pl.DataFrame
    results: pl.DataFrame  # wahlbezirke_auswertung
    citywide: tuple[str, ...]
    citywide_basis: str
    exclude: tuple[int, ...]
    marker: str
    processed: Path
    interim: Path


def street_variants(name: str) -> set[str]:
    """Wie `search.dictionary.normalise_terms`: klein, getrimmt, dazu die `str.`-Variante."""
    term = name.strip().lower()
    out = {term} if term else set()
    if "straße" in term:
        out.add(term.replace("straße", "str."))
    return out


def load_data() -> Daten:
    settings = load_settings(cwd=ROOT, profile="duesseldorf")
    base = Path(settings.data_root) / "duesseldorf"
    processed, interim = base / "processed", base / "interim"
    papers = pl.read_parquet(interim / "papers.parquet").select(
        "id", "reference", "name", "paper_type", "date", "file_name", pl.col("text").alias("store")
    )
    raw = pl.read_parquet(ROHTEXT).select("name", pl.col("text").alias("raw"))
    corpus = (
        papers.join(raw, left_on="file_name", right_on="name", how="left")
        .with_columns(
            pl.col("raw").fill_null(""),
            pl.col("store").fill_null(""),
            pl.col("paper_type").fill_null(""),
            pl.col("name").fill_null(""),
        )
        .sort("id")
    )
    dict_frame = pl.read_parquet(processed / "combined_searchdict.parquet")
    dictionary = {
        int(d): list(terms)
        for d, terms in dict_frame.select("wahlkreis_id", "suchbegriffe").iter_rows()
    }
    term_districts: dict[str, list[int]] = defaultdict(list)
    for district, terms in sorted(dictionary.items()):
        for term in terms:
            term_districts[term].append(district)
    streets: set[str] = set()
    for _d, names in pl.read_parquet(processed / "wahlbezirke_strassen.parquet").iter_rows():
        for name in names:
            streets |= street_variants(name)
    places: set[str] = set()
    for _d, names in pl.read_parquet(processed / "wikidata_agg.parquet").iter_rows():
        for name in names:
            places |= street_variants(name)
    term_type = {
        t: ("beides" if t in streets and t in places else "strasse" if t in streets else "ort")
        for t in term_districts
    }
    index = pl.read_parquet(processed / "inverted_index.parquet")
    found = citywide_terms(
        index,
        quantile=settings.search.citywide_quantile,
        median_factor=settings.search.citywide_median_factor,
    )
    return Daten(
        corpus=corpus,
        dictionary=dictionary,
        term_districts=dict(term_districts),
        term_type=term_type,
        index=index,
        results=pl.read_parquet(processed / "wahlbezirke_auswertung.parquet"),
        citywide=found.terms,
        citywide_basis=found.basis,
        exclude=tuple(settings.analysis.exclude_districts),
        marker=settings.search.text_split_marker,
        processed=processed,
        interim=interim,
    )


# --------------------------------------------------------------------------------------------
# Treffer mit Stelle
# --------------------------------------------------------------------------------------------


def store_view(raw: str, marker: str) -> tuple[str, list[int]]:
    """Der Text des Textstores aus dem Rohtext und je Zeichen seine Stelle im Rohtext.

    `prep/extract.py`: Seiten mit Zeilenumbruch verbunden (die Messdatei hat dort `\\f`), alle
    Zeilenumbrüche entfernt, kleingeschrieben, alles bis zum ersten Marker verworfen.
    """
    chars: list[str] = []
    where: list[int] = []
    for i, char in enumerate(raw):
        if char in "\n\f":
            continue
        low = char.lower()
        chars.append(low)
        where.extend([i] * len(low))
    text = "".join(chars)
    cut = after_marker(text, marker)
    offset = len(text) - len(cut)
    return cut, where[offset:]


@dataclass
class Treffer:
    """Ein Vorkommen eines Begriffs: Dokument, Begriff, Rohtextstelle, feine und grobe Stelle."""

    doc: str
    term: str
    start: int
    end: int
    fein: str
    grob: str
    liste: bool  # Listen- oder Tabellenzeile oder Hausnummer dahinter (Nebenregel C)


def locate(
    text: str, sections: Sequence[Any], level2: frozenset[str]
) -> tuple[list[int], list[Any]]:
    spans = sorted((s for s in sections if s.norm not in level2), key=lambda s: s.start)
    return [s.start for s in spans], spans


def section_of(pos: int, starts: list[int], spans: list[Any]) -> str:
    k = bisect.bisect_right(starts, pos) - 1
    if k >= 0 and spans[k].start <= pos < spans[k].end:
        return str(spans[k].norm)
    return "ausserhalb"


@dataclass(frozen=True)
class Rahmen:
    """Was je Dokument neben den Abschnitten zählt: Ende des Kopfes, Ende des Betreffs, Schluss."""

    head_end: int  # Ende der letzten Kopfspanne (Amt, Dezernat, Zeile der Beratungsfolge)
    betreff_end: int  # Ende des ersten Betreffs, 0 ohne Betreff
    closing: int  # Anfang der ersten Grußformel oder „gez." nach dem Betreff, sonst Textende


def rahmen(raw: str, result: Any, closings: Sequence[re.Pattern[str]]) -> Rahmen:
    head = [s.end for s in result.head if s.kind in ("amt", "dezernat", "beratung")]
    betreff = [s for s in result.sections if s.norm == "betreff"]
    betreff_end = betreff[0].end if betreff else 0
    closing = len(raw)
    for s, e in result.lines:
        if s >= betreff_end and any(p.match(raw[s:e]) for p in closings):
            closing = s
            break
    return Rahmen(max(head, default=0), betreff_end, closing)


def fine_position(pos: int, starts: list[int], spans: list[Any], frame: Rahmen) -> str:
    """Feine Stelle eines Treffers.

    Zwei Fälle, die das Regelwerk von 11 nicht trennt, weil es Abschnitte nur an Überschriften
    öffnet: In 55 % der BV-Informationsvorlagen folgt der Text der Beratungsfolge ohne die
    Überschrift „Sachdarstellung:" und gehört für 11 noch zum Kopfabschnitt; in Anfragen steht
    zwischen Betreff und Fragen eine Einleitung ohne Überschrift. Beides ist Rumpf (Begleittext).
    Hinter der Grußformel stehen Unterschrift, Verteiler und angehängte Seiten: Rest.
    """
    sec = section_of(pos, starts, spans)
    if sec.startswith("kopf_"):
        return "rumpf" if pos >= frame.head_end else "kopf"
    if sec == "ausserhalb":
        if pos >= frame.closing:
            return "nach_schluss"
        return "rumpf" if pos >= frame.betreff_end else "kopf"
    return sec


def coarse(fein: str) -> str:
    return GROB.get(fein, "rest")


def find_hits(data: Daten, struktur: ModuleType) -> tuple[list[Treffer], dict[str, Any]]:
    """Alle Vorkommen aller Begriffe in allen Dokumenten, mit Stelle; dazu Prüfzahlen."""
    rules = struktur.Rules.load("duesseldorf")
    closings = [
        p for p in rules.end_markers if "geehrte" not in p.pattern
    ]  # Anrede ist kein Schluss
    processor = KeywordProcessor(case_sensitive=False)
    processor.add_keywords_from_list(sorted(data.term_districts))
    index_pairs = {
        (doc, term)
        for term, ids in data.index.select("suchbegriffe", "paper_ids").iter_rows()
        for doc in ids
    }
    hits: list[Treffer] = []
    differ_refs: list[str] = []
    same_store = differ = no_raw = 0
    found_pairs: set[tuple[str, str]] = set()
    titles: dict[str, str] = {}
    results: dict[str, Any] = {}
    t0 = time.perf_counter()
    for doc, title, paper_type, store, raw in data.corpus.select(
        "id", "name", "paper_type", "store", "raw"
    ).iter_rows():
        titles[doc] = title.lower()
        if not raw:
            no_raw += 1
            continue
        view, where = store_view(raw, data.marker)
        if view == store:
            same_store += 1
        else:
            differ += 1
            differ_refs.append(doc)
            continue  # nur Dokumente, deren Textstore die Messdatei genau wiedergibt
        result = struktur.analyse(doc, raw, rules, paper_type)
        results[doc] = result
        starts, spans = locate(raw, result.sections, rules.level2)
        frame = rahmen(raw, result, closings)
        line_starts = [s for s, _e in result.lines]
        for term, a, b in processor.extract_keywords(view, span_info=True):
            start, end = where[a], where[b - 1] + 1
            fein = fine_position(start, starts, spans, frame)
            ls, le = result.lines[bisect.bisect_right(line_starts, start) - 1]
            line = raw[ls:le]
            lead = len(line) - len(line.lstrip())
            in_list = (
                len(line.strip()) <= LISTE_MAX_ZEILE and start - ls - lead <= LISTE_MAX_VORLAUF
            )
            hits.append(
                Treffer(
                    doc,
                    term,
                    start,
                    end,
                    fein,
                    coarse(fein),
                    in_list or bool(HAUSNR.match(raw, end)),
                )
            )
            found_pairs.add((doc, term))
    check = {
        "dokumente": data.corpus.height,
        "ohne_rohtext": no_raw,
        "store_gleich": same_store,
        "store_anders": differ,
        "index_paare": len(index_pairs),
        "gefundene_paare": len(found_pairs),
        "paare_gleich": len(index_pairs & found_pairs),
        "nur_index": len(index_pairs - found_pairs),
        "nur_gefunden": len(found_pairs - index_pairs),
        "sekunden": time.perf_counter() - t0,
        "anders": differ_refs,
        "titles": titles,
        "results": results,
    }
    return hits, check


# --------------------------------------------------------------------------------------------
# Paare: Dokument × Begriff, Dokument × Wahlbezirk
# --------------------------------------------------------------------------------------------


def title_terms(data: Daten, titles: dict[str, str]) -> set[tuple[str, str]]:
    """(Dokument, Begriff), wo der Begriff im OParl-Titel steht (derselbe Matcher, dieselben Grenzen)."""
    processor = KeywordProcessor(case_sensitive=False)
    processor.add_keywords_from_list(sorted(data.term_districts))
    return {
        (doc, term) for doc, title in titles.items() for term in processor.extract_keywords(title)
    }


def doc_terms(hits: Sequence[Treffer], in_title: set[tuple[str, str]]) -> pl.DataFrame:
    """Je (Dokument, Begriff) des Index mit Rohtext: Erwähnungen, beste Stelle, Erwähnungen je Stelle."""
    frame = pl.DataFrame(
        {
            "id": [h.doc for h in hits],
            "begriff": [h.term for h in hits],
            "grob": [h.grob for h in hits],
            "fein": [h.fein for h in hits],
            "liste": [h.liste for h in hits],
        },
        schema={
            "id": pl.String,
            "begriff": pl.String,
            "grob": pl.String,
            "fein": pl.String,
            "liste": pl.Boolean,
        },
    )
    rank = pl.col("grob").replace_strict(RANG, return_dtype=pl.Int64)
    out = (
        frame.group_by("id", "begriff")
        .agg(
            pl.len().alias("erwaehnungen"),
            rank.min().alias("rang"),
            (pl.col("grob") == "begleittext").sum().alias("n_begleit"),
            ((pl.col("grob") == "begleittext") & pl.col("liste")).sum().alias("n_liste"),
        )
        .with_columns(
            pl.struct("id", "begriff")
            .map_elements(lambda r: (r["id"], r["begriff"]) in in_title, return_dtype=pl.Boolean)
            .alias("im_titel")
        )
        .with_columns(pl.when(pl.col("im_titel")).then(0).otherwise(pl.col("rang")).alias("rang"))
        .sort("id", "begriff")
    )
    return out


def doc_districts(dt: pl.DataFrame, data: Daten) -> pl.DataFrame:
    """Je (Dokument, Wahlbezirk) mit mindestens einem Treffer: alle Paare des Index.

    Paare aus Dokumenten ohne Rohtext (oder mit abweichendem Textstore) bleiben mit `rang` null
    stehen: sie zählen in jeder Variante wie bisher, weil über ihre Stelle nichts bekannt ist.
    """
    term_district = pl.DataFrame(
        [(t, d) for t, ds in data.term_districts.items() for d in ds],
        schema={"begriff": pl.String, "wahlkreis_id": pl.Int64},
        orient="row",
    )
    index_pairs = (
        data.index.select(pl.col("suchbegriffe").alias("begriff"), pl.col("paper_ids").alias("id"))
        .explode("id")
        .drop_nulls()
    )
    citywide = set(data.citywide)
    joined = (
        index_pairs.join(dt, on=["id", "begriff"], how="left")
        .join(term_district, on="begriff", how="inner")
        .with_columns(pl.col("begriff").is_in(list(citywide)).alias("stadtweit"))
    )
    return (
        joined.group_by("id", "wahlkreis_id")
        .agg(
            pl.col("rang").min().alias("rang"),
            pl.col("erwaehnungen").sum().alias("erwaehnungen"),
            pl.col("n_begleit").sum().alias("n_begleit"),
            pl.col("n_liste").sum().alias("n_liste"),
            pl.len().alias("n_begriffe"),
            pl.col("stadtweit").all().alias("nur_stadtweit"),
            pl.col("begriff").sort().alias("begriffe"),
            pl.col("rang").is_null().all().alias("ohne_stelle"),
        )
        .with_columns(
            pl.when(pl.col("ohne_stelle"))
            .then(pl.lit(None, dtype=pl.String))
            .otherwise(pl.col("rang").replace_strict({v: k for k, v in RANG.items()}, default=None))
            .alias("stelle")
        )
        .sort("id", "wahlkreis_id")
    )


def rule_columns(pairs: pl.DataFrame) -> pl.DataFrame:
    """Die Regel und die Nebenregeln je Paar; Paare ohne Stelle bleiben null."""
    s = pl.col("stelle")
    return pairs.with_columns(
        pl.when(s.is_null()).then(None).otherwise(s.is_in(list(REGEL_HANDELT_VON))).alias("regel"),
        pl.when(s.is_null())
        .then(None)
        .otherwise(s.is_in(list(REGEL_HANDELT_VON)) | (pl.col("n_begleit") >= NEBEN_A_MIN_BEGLEIT))
        .alias("neben_a"),
        pl.when(s.is_null()).then(None).otherwise(s.is_in(list(NEBEN_B))).alias("neben_b"),
        pl.when(s.is_null())
        .then(None)
        .otherwise(s.is_in(list(REGEL_HANDELT_VON)) | (pl.col("n_liste") >= 1))
        .alias("neben_c"),
        pl.when(s.is_null())
        .then(1.0)
        .otherwise(s.replace_strict(GEWICHT_STELLE, return_dtype=pl.Float64))
        .alias("gewicht_stelle"),
    )


# --------------------------------------------------------------------------------------------
# § 3.1 Wo steht ein Treffer?
# --------------------------------------------------------------------------------------------


def table(rows: Sequence[Sequence[Any]], head: Sequence[str]) -> None:
    print("  | " + " | ".join(head) + " |")
    for row in rows:
        print("  | " + " | ".join(str(x) for x in row) + " |")


def position_report(
    hits: Sequence[Treffer], dt: pl.DataFrame, pairs: pl.DataFrame, data: Daten
) -> None:
    n_hits = len(hits)
    fine = Counter(h.fein for h in hits)
    print(f"  Erwähnungen (Vorkommen eines Begriffs im Text): {n_hits}")
    table(
        [(k, v, pct(v, n_hits), coarse(k)) for k, v in fine.most_common()],
        ["feine Stelle", "Erwähnungen", "Anteil", "grob"],
    )
    grob = Counter(h.grob for h in hits)
    n_title = int(dt["im_titel"].sum())
    print(
        f"  (Dokument, Begriff) mit Stelle: {dt.height}; davon Begriff auch im Titel: {n_title} ({pct(n_title, dt.height)})"
    )
    best_dt = Counter(STELLEN[r] for r in dt["rang"].to_list())
    located = pairs.filter(pl.col("stelle").is_not_null())
    best_p = Counter(located["stelle"].to_list())
    rows = []
    for s in STELLEN:
        rows.append(
            (
                s,
                grob.get(s, 0),
                pct(grob.get(s, 0), n_hits),
                best_dt.get(s, 0),
                pct(best_dt.get(s, 0), dt.height),
                best_p.get(s, 0),
                pct(best_p.get(s, 0), located.height),
            )
        )
    print(
        "  Grobe Stelle: Erwähnungen | (Dokument, Begriff) nach bester Stelle | (Dokument, Wahlbezirk) nach bester Stelle"
    )
    table(rows, ["Stelle", "Erwähnungen", "%", "Dok×Begriff", "%", "Dok×Bezirk", "%"])
    n_pairs = pairs.height
    no_pos = pairs.filter(pl.col("stelle").is_null()).height
    print(
        f"  Paare (Dokument, Wahlbezirk) im Index: {n_pairs} (= Summe der Treffer aller Bezirke {int(data.results['anzahl_treffer'].sum())}); ohne Stelle (kein Rohtext): {no_pos}"
    )
    em = located["erwaehnungen"]
    print(
        f"  Erwähnungen je Paar: Median {em.median():.0f}, Mittel {em.mean():.2f}, ein einziges Vorkommen {pct(int((em == 1).sum()), located.height)}, "
        f"≥ 3 Vorkommen {pct(int((em >= 3).sum()), located.height)}, ≥ 10 {pct(int((em >= 10).sum()), located.height)}"
    )


def type_report(dt: pl.DataFrame, data: Daten) -> None:
    """Beste Stelle je (Dokument, Begriff) nach Begriffsart und für die stadtweiten Begriffe."""
    citywide = set(data.citywide)
    frame = dt.with_columns(
        pl.col("begriff").replace_strict(data.term_type, default="?").alias("art"),
        pl.col("begriff").is_in(list(citywide)).alias("stadtweit"),
        pl.col("rang")
        .replace_strict(dict(enumerate(STELLEN)), return_dtype=pl.String)
        .alias("stelle"),
    )
    rows = []
    for label, sub in [
        ("Straße", frame.filter(pl.col("art") == "strasse")),
        ("Ort (Wikidata)", frame.filter(pl.col("art") == "ort")),
        ("beides", frame.filter(pl.col("art") == "beides")),
        (f"{len(citywide)} stadtweite", frame.filter(pl.col("stadtweit"))),
        ("übrige", frame.filter(~pl.col("stadtweit"))),
        ("alle", frame),
    ]:
        c = Counter(sub["stelle"].to_list())
        rows.append(
            (
                label,
                sub.height,
                *[pct(c.get(s, 0), sub.height) for s in STELLEN],
                pct(sum(c.get(s, 0) for s in REGEL_HANDELT_VON), sub.height),
            )
        )
    table(rows, ["Begriffsart", "Dok×Begriff", *STELLEN, "Titel/Betreff/Kern"])
    n_terms = Counter(data.term_type[t] for t in data.term_districts)
    print(f"  Begriffe im Wörterbuch nach Art: {dict(n_terms)}")
    print(
        "  Die stadtweiten Begriffe einzeln (Dokumente mit Stelle; Anteil mit Begriff in Titel/Betreff/Kern):"
    )
    per = (
        frame.filter(pl.col("stadtweit"))
        .group_by("begriff")
        .agg(
            pl.len().alias("dok"),
            pl.col("stelle").is_in(list(REGEL_HANDELT_VON)).mean().alias("anteil"),
        )
        .sort(["dok", "begriff"], descending=[True, False])
    )
    print("  " + "; ".join(f"{t} {n} ({100 * a:.0f} %)" for t, n, a in per.iter_rows()))
    lo = per.filter(pl.col("anteil") < 0.1)
    print(
        f"  stadtweite Begriffe mit unter 10 % in Titel/Betreff/Kern: {lo.height}: {', '.join(lo['begriff'].to_list())}"
    )


def district_report(pairs: pl.DataFrame, data: Daten) -> pl.DataFrame:
    sizes = {d: len(t) for d, t in data.dictionary.items()}
    per = (
        pairs.group_by("wahlkreis_id")
        .agg(
            pl.len().alias("treffer"),
            pl.col("stelle").is_not_null().sum().alias("mit_stelle"),
            *[(pl.col("stelle") == s).sum().alias(s) for s in STELLEN],
            pl.col("regel").sum().alias("handelt_von"),
            (pl.col("nur_stadtweit") & pl.col("stelle").is_not_null()).sum().alias("nur_stadtweit"),
        )
        .with_columns(
            pl.col("wahlkreis_id").replace_strict(sizes, return_dtype=pl.Int64).alias("begriffe")
        )
        .sort("wahlkreis_id")
    )
    rows = []
    for r in per.iter_rows(named=True):
        m = r["mit_stelle"]
        rows.append(
            (
                r["wahlkreis_id"],
                r["begriffe"],
                r["treffer"],
                pct(r["titel"] + r["betreff"], m),
                pct(r["kern"], m),
                pct(r["begleittext"], m),
                pct(r["rest"], m),
                pct(r["handelt_von"], m),
                pct(r["nur_stadtweit"], m),
            )
        )
    table(
        rows,
        [
            "Bezirk",
            "Begriffe",
            "Treffer",
            "Titel+Betreff",
            "Kern",
            "Begleittext",
            "Rest",
            "handelt von (Regel)",
            "nur stadtweite Begriffe",
        ],
    )
    share = per.with_columns((pl.col("handelt_von") / pl.col("mit_stelle")).alias("anteil"))
    r, p = pearsonr(share["begriffe"].to_numpy(), share["anteil"].to_numpy())
    rs = spearmanr(share["begriffe"].to_numpy(), share["anteil"].to_numpy())
    a = share["anteil"]
    print(
        f"  Anteil „handelt von“ je Bezirk: Median {100 * a.median():.1f} %, Spannweite {100 * a.min():.1f} bis {100 * a.max():.1f} %; "
        f"gegen die Zahl der Begriffe Pearson r = {r:.3f} (p = {p:.4f}), Spearman ρ = {rs.statistic:.3f}"
    )
    return per


# --------------------------------------------------------------------------------------------
# § 3.2 Regel und § 3.3 Wirkung als Sensitivität
# --------------------------------------------------------------------------------------------


def rule_report(pairs: pl.DataFrame, data: Daten, struktur: ModuleType) -> None:
    located = pairs.filter(pl.col("stelle").is_not_null())
    rules = struktur.Rules.load("duesseldorf")
    art = {d: rules.art(t) for d, t in data.corpus.select("id", "paper_type").iter_rows()}
    by_art = (
        located.with_columns(pl.col("id").replace_strict(art, return_dtype=pl.String).alias("art"))
        .group_by("art")
        .agg(
            pl.len().alias("paare"),
            pl.col("regel").mean().alias("anteil"),
            *[(pl.col("stelle") == s).mean().alias(s) for s in STELLEN],
        )
        .sort("paare", descending=True)
    )
    table(
        [
            (r["art"], r["paare"], pct(r["anteil"], 1), *[pct(r[s], 1) for s in STELLEN])
            for r in by_art.iter_rows(named=True)
        ],
        ["Dokumentart (wie 11)", "Paare", "handelt von", *STELLEN],
    )
    n = located.height
    for col, label in [
        ("regel", "Regel (Titel, Betreff oder Kern)"),
        (
            "neben_a",
            f"Nebenregel A (Regel oder ≥ {NEBEN_A_MIN_BEGLEIT} Erwähnungen im Begleittext)",
        ),
        ("neben_b", "Nebenregel B (nur Titel oder Betreff)"),
        ("neben_c", "Nebenregel C (Regel oder Listenzeile oder Adresse im Begleittext)"),
    ]:
        k = int(located[col].sum())
        print(f"  {label}: „handelt von“ {k} von {n} Paaren ({pct(k, n)})")
    docs = located.group_by("id").agg(
        pl.col("regel").any().alias("irgendein"), pl.len().alias("bezirke")
    )
    k = int(docs["irgendein"].sum())
    print(
        f"  Dokumente mit Treffer und Stelle: {docs.height}; davon handelt mindestens ein Paar von einem Bezirk: {k} ({pct(k, docs.height)})"
    )
    multi = docs.filter(pl.col("bezirke") >= 5)
    print(
        f"  Dokumente mit Treffern in ≥ 5 Bezirken: {multi.height}, sie tragen {int(multi['bezirke'].sum())} der {n} Paare ({pct(int(multi['bezirke'].sum()), n)})"
    )


VARIANTEN = [
    ("basis", "alle Treffer (Tabelle 5)"),
    ("regel", "nur „handelt von“ (Regel)"),
    ("neben_b", "nur Titel oder Betreff (Nebenregel B)"),
    ("gewicht_stelle", "nach Stelle gewichtet (1 / 1 / 1 / 0,5 / 0,25)"),
    ("adresse", "Hausnummer vor Straßenname (§ 3.4)"),
]


def sensitivity(pairs: pl.DataFrame, data: Daten, drop: set[tuple[str, int]]) -> pl.DataFrame:
    """Treffer je Wahlbezirk je Variante, Tabelle 5, Verzerrung durch die Wörterbuchgröße."""
    from georep.prep.voters import ELIGIBLE_TOTAL, TURNOUT

    sizes = pl.DataFrame(
        [(d, len(t)) for d, t in sorted(data.dictionary.items())],
        schema={"wahlkreis_id": pl.Int64, "begriffe": pl.Int64},
        orient="row",
    )
    counts = (
        pairs.with_columns(
            pl.lit(1.0).alias("basis"),
            pl.col("regel").fill_null(True).cast(pl.Float64),
            pl.col("neben_b").fill_null(True).cast(pl.Float64),
            pl.struct("id", "wahlkreis_id")
            .map_elements(
                lambda r: 0.0 if (r["id"], r["wahlkreis_id"]) in drop else 1.0,
                return_dtype=pl.Float64,
            )
            .alias("adresse"),
        )
        .group_by("wahlkreis_id")
        .agg(*[pl.col(v).sum() for v, _l in VARIANTEN])
        .sort("wahlkreis_id")
    )
    base = data.results.select(
        "wahlkreis_id", "anzahl_treffer", ELIGIBLE_TOTAL, TURNOUT, "trefferquote"
    )
    frame = (
        base.join(counts, on="wahlkreis_id", how="inner")
        .join(sizes, on="wahlkreis_id", how="inner")
        .sort("wahlkreis_id")
    )
    assert (
        frame.height == 41 and (frame["basis"] == frame["anzahl_treffer"].cast(pl.Float64)).all()
    ), "Basis = anzahl_treffer"
    q_base = frame["basis"] / frame[ELIGIBLE_TOTAL]
    rows = []
    for v, label in VARIANTEN:
        f = frame.with_columns((pl.col(v) / pl.col(ELIGIBLE_TOTAL)).alias("x"))
        pair = regression_pair(f, data.exclude, x="x")
        r_terms = pearsonr(f[v].to_numpy(), f["begriffe"].to_numpy()).statistic
        r_elig = pearsonr(f[v].to_numpy(), f[ELIGIBLE_TOTAL].to_numpy()).statistic
        per_term = (f[v] / f["begriffe"]).to_numpy()
        r_per = pearsonr(per_term, f["begriffe"].to_numpy()).statistic
        rho = spearmanr(f["x"].to_numpy(), q_base.to_numpy()).statistic
        w = pair.without
        rows.append(
            (
                label,
                f"{f[v].sum():.1f}",
                f"{r_terms:.3f}",
                f"{r_elig:.3f}",
                f"{r_per:.3f}",
                f"{rho:.3f}",
                f"{pair.all.slope:.2f} / {pair.all.r:.4f} / {pair.all.p:.4f}",
                f"{w.slope:.2f} / {w.r:.4f} / {w.p:.4f}" if w else "–",
            )
        )
    table(
        rows,
        [
            "Variante",
            "Summe",
            "r(Treffer, Begriffe)",
            "r(Treffer, Wahlberechtigte)",
            "r(je Begriff, Begriffe)",
            "ρ zur Quote",
            "Tabelle 5 alle: Steigung / r / p",
            "ohne 1 und 10: Steigung / r / p",
        ],
    )
    share = frame.with_columns((pl.col("regel") / pl.col("basis")).alias("anteil")).sort("anteil")
    print(
        "  Anteil „handelt von“ an allen Treffern je Bezirk, niedrigste fünf: "
        + ", ".join(
            f"{d} ({100 * a:.1f} %, {b} Begriffe)"
            for d, a, b in share.select("wahlkreis_id", "anteil", "begriffe").head(5).iter_rows()
        )
    )
    print(
        "  höchste fünf: "
        + ", ".join(
            f"{d} ({100 * a:.1f} %, {b} Begriffe)"
            for d, a, b in share.select("wahlkreis_id", "anteil", "begriffe")
            .tail(5)
            .reverse()
            .iter_rows()
        )
    )
    ranks = frame.with_columns(
        (pl.col("basis") / pl.col(ELIGIBLE_TOTAL))
        .rank("ordinal", descending=True)
        .cast(pl.Int64)
        .alias("platz_basis"),
        (pl.col("regel") / pl.col(ELIGIBLE_TOTAL))
        .rank("ordinal", descending=True)
        .cast(pl.Int64)
        .alias("platz_regel"),
    )
    moved = ranks.filter((pl.col("platz_basis") - pl.col("platz_regel")).abs() >= 5)
    print(
        f"  Bezirke, die mit der Regel um ≥ 5 Plätze der Quote wandern: {moved.height}: "
        + ", ".join(
            f"{d} ({a}→{b})"
            for d, a, b in moved.select("wahlkreis_id", "platz_basis", "platz_regel").iter_rows()
        )
    )
    for d in data.exclude:
        r = ranks.filter(pl.col("wahlkreis_id") == d).row(0, named=True)
        print(
            f"  Bezirk {d}: Platz der Quote {r['platz_basis']} → {r['platz_regel']}, Anteil handelt von {100 * r['regel'] / r['basis']:.1f} %"
        )
    return frame


# --------------------------------------------------------------------------------------------
# § 4 Stichprobe, Kodieraufgaben, Auswertung der Kodierung
# --------------------------------------------------------------------------------------------

# Drei Schichten: die beiden, die die Regel „handelt von" nennt, und der Rest (Begleittext und die
# 0,3 % in Anlagenliste, Kopf und hinter dem Schluss), in dem ihre Fehler nach unten liegen.
SCHICHT = {
    "titel": "titel_betreff",
    "betreff": "titel_betreff",
    "kern": "kern",
    "begleittext": "begleit_rest",
    "rest": "begleit_rest",
}


def pair_key(doc: str, district: int) -> str:
    return hashlib.sha1(f"{doc}|{district}".encode()).hexdigest()[:12]


def draw_sample(pairs: pl.DataFrame, struktur: ModuleType) -> list[dict[str, Any]]:
    """200 Paare mit Stelle, geschichtet nach der besten Stelle (drei Schichten), ein Paar je Dokument.

    Proportional mit mindestens 30 je Schicht (Rest nach größtem Bruchteil, `allocate` aus 11);
    je Schicht in fester Folge gemischt (Seed), ein Paar, dessen Dokument schon gezogen ist, wird
    übersprungen. Gewicht = Paare der Schicht durch Stichprobe der Schicht.
    """
    located = pairs.filter(pl.col("stelle").is_not_null()).with_columns(
        pl.col("stelle").replace_strict(SCHICHT, return_dtype=pl.String).alias("schicht")
    )
    strata: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for doc, wk, schicht in located.select("id", "wahlkreis_id", "schicht").iter_rows():
        strata[schicht].append((doc, int(wk)))
    sizes = {k: len(v) for k, v in strata.items()}
    alloc = struktur.allocate(sizes, STICHPROBE, MINDESTENS_JE_SCHICHT)
    rng = random.Random(SEED)
    used: set[str] = set()
    chosen: list[dict[str, Any]] = []
    for schicht in sorted(strata):
        pool = sorted(strata[schicht])
        rng.shuffle(pool)
        taken = 0
        for doc, wk in pool:
            if taken == alloc[schicht]:
                break
            if doc in used:
                continue
            used.add(doc)
            taken += 1
            chosen.append(
                {
                    "paar": pair_key(doc, wk),
                    "id": doc,
                    "wahlkreis_id": wk,
                    "schicht": schicht,
                    "gewicht": sizes[schicht] / alloc[schicht],
                }
            )
    print("  Schicht | Paare mit Stelle | Stichprobe | Gewicht")
    for schicht in sorted(strata, key=lambda s: -sizes[s]):
        print(
            f"  {schicht} | {sizes[schicht]} | {alloc[schicht]} | {sizes[schicht] / alloc[schicht]:.2f}"
        )
    return chosen


def line_of(lines: Sequence[tuple[int, int]], pos: int) -> int:
    starts = [s for s, _e in lines]
    return bisect.bisect_right(starts, pos)  # 1-basiert


def write_tasks(
    chosen: Sequence[dict[str, Any]],
    pairs: pl.DataFrame,
    hits: Sequence[Treffer],
    data: Daten,
    results: dict[str, Any],
    names: dict[int, str],
) -> None:
    VALIDIERUNG.mkdir(parents=True, exist_ok=True)
    AUFGABEN_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED + 1)
    order = list(chosen)
    rng.shuffle(order)  # Kodierer sehen die Schichten gemischt
    for number, row in enumerate(order, start=1):
        row["aufgabe"] = f"16-ortsbezug-{number:03d}"
    with (VALIDIERUNG / "stichprobe.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["aufgabe", "paar", "id", "wahlkreis_id", "schicht", "gewicht"])
        for row in sorted(order, key=lambda r: r["aufgabe"]):
            writer.writerow(
                [
                    row["aufgabe"],
                    row["paar"],
                    row["id"],
                    row["wahlkreis_id"],
                    row["schicht"],
                    f"{row['gewicht']:.4f}",
                ]
            )
    by_doc: dict[str, list[Treffer]] = defaultdict(list)
    wanted = {r["id"] for r in order}
    for h in hits:
        if h.doc in wanted:
            by_doc[h.doc].append(h)
    meta = {
        r["id"]: r
        for r in data.corpus.filter(pl.col("id").is_in(list(wanted))).iter_rows(named=True)
    }
    info = {
        (r["id"], r["wahlkreis_id"]): r
        for r in pairs.filter(pl.col("id").is_in(list(wanted))).iter_rows(named=True)
    }
    n_cut = 0
    with (
        (AUFGABEN_DIR / "aufgaben.jsonl").open("w", encoding="utf-8") as tasks,
        (AUFGABEN_DIR / "regel.jsonl").open("w", encoding="utf-8") as rule_out,
    ):
        for row in order:
            doc, wk = row["id"], row["wahlkreis_id"]
            raw = meta[doc]["raw"]
            lines = results[doc].lines
            terms = set(data.dictionary[wk])
            occ: dict[str, list[int]] = defaultdict(list)
            for h in by_doc[doc]:
                if h.term in terms:
                    occ[h.term].append(line_of(lines, h.start))
            title = meta[doc]["name"].lower()
            in_title = [
                t for t in occ if re.search(rf"(?<![\wäöüß]){re.escape(t)}(?![\wäöüß])", title)
            ]
            far = sorted({ln for ls in occ.values() for ln in ls if ln > MAX_ZEILEN_AUFGABE})
            extra: set[int] = set()
            for ln in far:
                extra |= set(
                    range(
                        max(MAX_ZEILEN_AUFGABE + 1, ln - AUSZUG_RAND),
                        min(len(lines), ln + AUSZUG_RAND) + 1,
                    )
                )
            n_cut += len(lines) > MAX_ZEILEN_AUFGABE
            pages = [i + 1 for i, (s, _e) in enumerate(lines) if s > 0 and raw[s - 1] == "\f"]
            tasks.write(
                json.dumps(
                    {
                        "vorhaben": "16-ortsbezug",
                        "aufgabe": row["aufgabe"],
                        "id": doc,
                        "drucksache": meta[doc]["reference"],
                        "dokumentart": meta[doc]["paper_type"],
                        "datum": str(meta[doc]["date"]),
                        "titel": meta[doc]["name"],
                        "wahlbezirk": wk,
                        "wahlbezirk_name": names.get(wk, ""),
                        "begriffe": [
                            {
                                "begriff": t,
                                "art": {
                                    "strasse": "Straße",
                                    "ort": "Ort",
                                    "beides": "Straße oder Ort",
                                }[data.term_type[t]],
                                "zeilen": sorted(set(ls)),
                                "im_titel": t in in_title,
                            }
                            for t, ls in sorted(occ.items())
                        ],
                        "zeilen": [raw[s:e] for s, e in lines[:MAX_ZEILEN_AUFGABE]],
                        "auszug": [
                            {"zeile": i, "text": raw[lines[i - 1][0] : lines[i - 1][1]]}
                            for i in sorted(extra)
                        ],
                        "seitenanfang_zeilen": [p for p in pages if p <= MAX_ZEILEN_AUFGABE],
                        "gekuerzt": len(lines) > MAX_ZEILEN_AUFGABE,
                        "codebuch": "validierung/16-ortsbezug/codebuch.toml",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            p = info[(doc, wk)]
            rule_out.write(
                json.dumps(
                    {
                        "aufgabe": row["aufgabe"],
                        "paar": row["paar"],
                        "schicht": row["schicht"],
                        "stelle": p["stelle"],
                        "regel": p["regel"],
                        "neben_a": p["neben_a"],
                        "neben_b": p["neben_b"],
                        "neben_c": p["neben_c"],
                        "erwaehnungen": p["erwaehnungen"],
                        "n_begleit": p["n_begleit"],
                        "n_liste": p["n_liste"],
                        "extractor": EXTRACTOR,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    size = (AUFGABEN_DIR / "aufgaben.jsonl").stat().st_size
    print(f"  geschrieben: {VALIDIERUNG / 'stichprobe.csv'} ({len(order)} Paare, nur IDs)")
    print(
        f"  geschrieben: {AUFGABEN_DIR / 'aufgaben.jsonl'} ({size / 1e3:.0f} KB) und regel.jsonl (lokal, nicht im Repo); gekürzt über {MAX_ZEILEN_AUFGABE} Zeilen: {n_cut}"
    )


def krippendorff_nominal(a: Sequence[str], b: Sequence[str]) -> float:
    """α für zwei Kodierer, nominal, ohne fehlende Werte."""
    coincidence: Counter[tuple[str, str]] = Counter()
    for x, y in zip(a, b, strict=True):
        coincidence[(x, y)] += 1
        coincidence[(y, x)] += 1
    n = sum(coincidence.values())
    marg: Counter[str] = Counter()
    for (x, _y), c in coincidence.items():
        marg[x] += c
    d_o = sum(c for (x, y), c in coincidence.items() if x != y) / n
    d_e = sum(marg[x] * marg[y] for x in marg for y in marg if x != y) / (n * (n - 1))
    return 1.0 - d_o / d_e if d_e else 1.0


def f1_weighted(rows: Sequence[tuple[bool, bool, float]]) -> tuple[float, float, float]:
    tp = sum(w for t, p, w in rows if t and p)
    fp = sum(w for t, p, w in rows if not t and p)
    fn = sum(w for t, p, w in rows if t and not p)
    prec = tp / (tp + fp) if tp + fp else math.nan
    rec = tp / (tp + fn) if tp + fn else math.nan
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else math.nan
    return prec, rec, f1


def cohen_kappa(rows: Sequence[tuple[bool, bool, float]]) -> float:
    """κ zwischen Regel und Label (zwei Klassen), mit Gewichten."""
    total = sum(w for _t, _p, w in rows)
    agree = sum(w for t, p, w in rows if t == p) / total
    pt = sum(w for t, _p, w in rows if t) / total
    pp = sum(w for _t, p, w in rows if p) / total
    chance = pt * pp + (1 - pt) * (1 - pp)
    return (agree - chance) / (1 - chance) if chance < 1 else math.nan


def stratified_bootstrap(
    rows_by_stratum: dict[str, list[tuple[bool, bool, float]]], stat: Any, reps: int = 2000
) -> tuple[float, float]:
    rng = random.Random(SEED)
    boot = []
    for _ in range(reps):
        draw = [rng.choice(v) for v in rows_by_stratum.values() for _k in v]
        value = stat(draw)
        if not math.isnan(value):
            boot.append(value)
    boot.sort()
    return boot[int(0.025 * len(boot))], boot[int(0.975 * len(boot)) - 1]


def score_labels() -> None:
    """Liest `labels.csv`, wenn die Kodierung da ist, und rechnet das Kriterium (F1 ≥ 0,8).

    Vorab festgelegt (2026-11-23, vor der Kodierung): Hauptmaß ist F1 der Klasse „handelt von"
    für die Regel, mit den Schichtgewichten aus `stichprobe.csv` hochgerechnet, mit
    geschichtetem Bootstrap (2000 Ziehungen, Seed) als Intervall. Daneben, ohne Einfluss auf das
    Urteil: ungewichtet, F1 der Klasse „erwähnt oder kein Bezug", Cohens κ zwischen Regel und
    Label, die Nebenregeln A bis C und die triviale Regel „alles handelt von" als Vergleich — bei
    hoher Prävalenz erreicht sie ein hohes F1 ohne jede Trennung (§ 9 des Messdokuments).
    """
    labels_path = VALIDIERUNG / "labels.csv"
    sample_path = VALIDIERUNG / "stichprobe.csv"
    if not labels_path.exists():
        print("  noch nicht kodiert: validierung/16-ortsbezug/labels.csv fehlt")
        return
    with sample_path.open(encoding="utf-8") as handle:
        sample = {r["aufgabe"]: r for r in csv.DictReader(handle)}
    with labels_path.open(encoding="utf-8") as handle:
        labels = [r for r in csv.DictReader(handle) if r["frage"] == "bezug" and r["label"]]
    rule_rows = {}
    with (AUFGABEN_DIR / "regel.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            r = json.loads(line)
            rule_rows[r["aufgabe"]] = r
    print(f"  Labels: {len(labels)}; Verteilung: {dict(Counter(r['label'] for r in labels))}")
    both = [r for r in labels if r["kodierer_a"] and r["kodierer_b"]]
    alpha = krippendorff_nominal([r["kodierer_a"] for r in both], [r["kodierer_b"] for r in both])
    agree = sum(r["kodierer_a"] == r["kodierer_b"] for r in both)
    print(
        f"  Übereinstimmung der Kodierer: {agree} von {len(both)}, Krippendorffs α (nominal, drei Klassen) = {alpha:.3f}"
    )
    for stratum in sorted({s["schicht"] for s in sample.values()}):
        sub = [r for r in labels if sample[r["aufgabe"]]["schicht"] == stratum]
        k = sum(r["label"] == "handelt_von" for r in sub)
        print(f"  Schicht {stratum}: handelt von {wil(k, len(sub))}")
    for col in ("regel", "neben_a", "neben_b", "neben_c", "alle"):
        rows = [
            (
                r["label"] == "handelt_von",
                True if col == "alle" else bool(rule_rows[r["aufgabe"]][col]),
                float(sample[r["aufgabe"]]["gewicht"]),
            )
            for r in labels
        ]
        by_stratum: dict[str, list[tuple[bool, bool, float]]] = defaultdict(list)
        for lab, row in zip(labels, rows, strict=True):
            by_stratum[sample[lab["aufgabe"]]["schicht"]].append(row)
        p_u, r_u, f_u = f1_weighted([(t, p, 1.0) for t, p, _w in rows])
        p_w, r_w, f_w = f1_weighted(rows)
        lo, hi = stratified_bootstrap(by_stratum, lambda d: f1_weighted(d)[2])
        neg = f1_weighted([(not t, not p, w) for t, p, w in rows])[2]
        kappa = cohen_kappa(rows) if col != "alle" else 0.0
        k_lo, k_hi = stratified_bootstrap(by_stratum, cohen_kappa) if col != "alle" else (0.0, 0.0)
        # Kriterium aus dem Briefing; daneben, ob die Regel die triviale „alles handelt von"
        # schlägt (κ-Intervall über 0), Annahme 9.2 des Messdokuments.
        verdict = (
            f"; Kriterium F1 ≥ 0,8: {'erfüllt' if f_w >= 0.8 else 'nicht erfüllt'}; "
            f"schlägt die triviale Regel (κ-Intervall über 0): {'ja' if k_lo > 0 else 'nein'}"
            if col == "regel"
            else ""
        )
        print(
            f"  {col}: ungewichtet P {p_u:.3f} R {r_u:.3f} F1 {f_u:.3f}; hochgerechnet P {p_w:.3f} R {r_w:.3f} "
            f"F1 {f_w:.3f} (95 % {lo:.3f}–{hi:.3f}); F1 der Gegenklasse {neg:.3f}; "
            f"κ {kappa:.3f} (95 % {k_lo:.3f}–{k_hi:.3f}){verdict}"
        )
    wrong = [(r["label"] == "kein_bezug", float(sample[r["aufgabe"]]["gewicht"])) for r in labels]
    k = sum(1 for t, _w in wrong if t)
    share = sum(w for t, w in wrong if t) / sum(w for _t, w in wrong)
    print(
        f"  kein Bezug (der Begriff meint keinen Ort im Bezirk): {k} von {len(wrong)}, hochgerechnet {100 * share:.1f} % der Paare"
    )


# --------------------------------------------------------------------------------------------
# Fremddaten: Prüfsumme, Stimmbezirke
# --------------------------------------------------------------------------------------------


def expected_sha(path: Path) -> str:
    """SHA-256 aus der README neben der Datei, sonst aus der README unter `opendata/`."""
    for readme in (path.parent / "README.md", FREMDDATEN / "README.md"):
        if not readme.exists():
            continue
        for line in readme.read_text(encoding="utf-8").splitlines():
            if f"{path.name}`" in line:
                found = re.search(r"`([0-9a-f]{64})`", line)
                if found:
                    return found.group(1)
    raise SystemExit(f"{path}: keine Prüfsumme in einer README")


def checked(path: Path) -> Path:
    return check_file(path, expected_sha(path))


@dataclass(frozen=True)
class Bezirke:
    """Stimmbezirke der Seite (EPSG:4647) mit ihrem Wahlbezirk, für Punkt- und Flächenabfragen."""

    shapes: list[Any]
    district: list[int]
    tree: STRtree
    names: dict[int, str]

    @classmethod
    def load(cls, interim: Path) -> Bezirke:
        data = json.loads((interim / "stimmbezirke.geojson").read_text(encoding="utf-8"))
        shapes, district, names = [], [], {}
        for f in data["features"]:
            shapes.append(shape(f["geometry"]))
            district.append(int(f["properties"]["wahlbezirk"]))
            names[int(f["properties"]["wahlbezirk"])] = f["properties"]["wahlbezirk_name"]
        return cls(shapes, district, STRtree(shapes), names)

    def at(self, x: float, y: float) -> int | None:
        point = Point(x, y)
        for k in self.tree.query(point):
            if self.shapes[int(k)].covers(point):
                return self.district[int(k)]
        return None

    def overlapping(self, geom: Any, min_share: float = 0.05) -> list[int]:
        area: Counter[int] = Counter()
        for k in self.tree.query(geom):
            inter = self.shapes[int(k)].intersection(geom).area
            if inter > 0:
                area[self.district[int(k)]] += inter
        total = geom.area or 1.0
        return sorted(d for d, a in area.items() if a / total >= min_share)


# --------------------------------------------------------------------------------------------
# § 3.4 Hausnummern
# --------------------------------------------------------------------------------------------

GEBREF = FREMDDATEN / "nrw-gebaeudereferenzen" / "gebref_EPSG25832_ASCII.zip"
UTM_ZONE_OFFSET = 32_000_000  # EPSG:25832 → EPSG:4647: Zonenzahl 32 vor dem Rechtswert

# Hausnummer direkt hinter einem Straßennamen: bis drei Ziffern, ein Buchstabe als Zusatz, ein
# Bereich („50–54", „12/14"), „Nr." davor erlaubt. Keine Hausnummer: Dezimalzahlen, Jahreszahlen
# (vier Ziffern) und Zahlen mit Einheit (Meter, Prozent, Euro, Uhr …).
HAUSNR = re.compile(
    r"\s{0,3}(?:Nr\.\s?)?(?P<nr>\d{1,3})(?:\s?(?P<zusatz>[a-zA-Z])(?![A-Za-zÄÖÜäöüß]))?"
    r"(?:\s?[-–/+]\s?\d{1,3}\s?[a-zA-Z]?(?![A-Za-zÄÖÜäöüß]))?(?!\d)(?!\s?[.,]\d)"
    r"(?!\s?(?:%|m\b|km\b|qm\b|m²|mm\b|cm\b|ha\b|€|Euro\b|EUR\b|Jahr|Std|Uhr|Min|Monat|Tag|Woche|Pl[äa]tz|Stellpl|Standort|Wohnung|WE\b|Stück|Stk))"
)


def norm_street(name: str) -> str:
    s = name.strip().lower().replace("strasse", "straße")
    s = re.sub(r"str\.(?=$|[\s-])", "straße", s)
    s = re.sub(r"\s*-\s*", "-", s)
    return re.sub(r"\s+", " ", s)


def load_gebref() -> dict[str, dict[tuple[int, str], tuple[float, float]]]:
    """Hauskoordinaten der Stadt (Regierungsbezirk 1, Kreis 11, Gemeinde 000) aus GebRef NRW."""
    import io

    out: dict[str, dict[tuple[int, str], tuple[float, float]]] = defaultdict(dict)
    with zipfile.ZipFile(checked(GEBREF)) as archive, archive.open("gebref.txt") as raw:
        for line in io.TextIOWrapper(raw, encoding="utf-8"):
            p = line.split(";")
            if p[3] != "05" or p[5] != "1" or p[7] != "11" or p[9] != "000" or not p[15].isdigit():
                continue
            out[norm_street(p[14])][(int(p[15]), p[16].strip().lower())] = (
                float(p[18]) + UTM_ZONE_OFFSET,
                float(p[19]),
            )
    return dict(out)


def lookup(
    street: dict[tuple[int, str], tuple[float, float]], nr: int, zusatz: str
) -> tuple[str, tuple[float, float] | None]:
    """genau (Nummer und Zusatz), ohne_zusatz (Zusatz weggelassen), mit_zusatz (Nummer nur mit Zusatz), nein."""
    if (nr, zusatz) in street:
        return "genau", street[(nr, zusatz)]
    if zusatz and (nr, "") in street:
        return "ohne_zusatz", street[(nr, "")]
    others = [v for (n, _z), v in street.items() if n == nr]
    if others:
        return "mit_zusatz", others[0]
    return "nein", None


def house_numbers(
    hits: Sequence[Treffer], data: Daten, bezirke: Bezirke, pairs: pl.DataFrame
) -> dict[str, Any]:
    raw_of = dict(data.corpus.select("id", "raw").iter_rows())
    gebref = load_gebref()
    n_addr = sum(len(v) for v in gebref.values())
    print(f"  GebRef NRW, Stadtgebiet: {n_addr} Hausnummern an {len(gebref)} Straßennamen")
    names = {
        norm_street(t)
        for t, k in data.term_type.items()
        if k in ("strasse", "beides") and not t.endswith("str.")
    }
    multi_names = sum(
        1
        for t, k in data.term_type.items()
        if k in ("strasse", "beides") and not t.endswith("str.") and len(data.term_districts[t]) > 1
    )
    print(
        f"  Straßenbegriffe des Wörterbuchs (ohne „str.“-Varianten): {len(names)}; in GebRef: {len(names & set(gebref))} "
        f"({pct(len(names & set(gebref)), len(names))}); in mehr als einem Wahlbezirk: {multi_names}"
    )
    # Was ein Paket für Stufe 2 wöge: Straße, Nummer, Zusatz, Wahlbezirk (ohne Koordinaten).
    import io

    rows = [
        (st, nr, z, bezirke.at(x, y))
        for st, nums in gebref.items()
        for (nr, z), (x, y) in nums.items()
    ]
    table_frame = pl.DataFrame(
        rows,
        schema={
            "strasse": pl.String,
            "nr": pl.UInt16,
            "zusatz": pl.String,
            "wahlkreis_id": pl.Int64,
        },
        orient="row",
    ).sort("strasse", "nr", "zusatz")
    buffer = io.BytesIO()
    table_frame.write_parquet(buffer, compression="zstd")
    print(
        f"  Adresse → Wahlbezirk als Parquet (zstd): {buffer.tell()} Bytes für {table_frame.height} Adressen; "
        f"ohne Bezirk: {table_frame['wahlkreis_id'].null_count()}"
    )
    street_hits = [h for h in hits if data.term_type[h.term] in ("strasse", "beides")]
    found: list[tuple[Treffer, int, str]] = []
    for h in street_hits:
        m = HAUSNR.match(raw_of[h.doc], h.end)
        if m:
            found.append((h, int(m.group("nr")), (m.group("zusatz") or "").lower()))
    n_s, n_f = len(street_hits), len(found)
    print(
        f"  Erwähnungen von Straßenbegriffen: {n_s}; mit Hausnummer dahinter: {n_f} ({pct(n_f, n_s)})"
    )
    dt_street = {(h.doc, h.term) for h in street_hits}
    dt_nr = {(h.doc, h.term) for h, _n, _z in found}
    print(
        f"  (Dokument, Straße): {len(dt_street)}; mit mindestens einer Hausnummer: {len(dt_nr)} ({pct(len(dt_nr), len(dt_street))})"
    )
    docs_nr = {h.doc for h, _n, _z in found}
    located_pairs = pairs.filter(pl.col("stelle").is_not_null())
    pairs_nr = {(d, wk) for (d, t) in dt_nr for wk in data.term_districts[t]}
    k = sum(
        1 for d, wk in located_pairs.select("id", "wahlkreis_id").iter_rows() if (d, wk) in pairs_nr
    )
    print(
        f"  Dokumente mit „Straße + Hausnummer“: {len(docs_nr)}; Paare (Dokument, Wahlbezirk) mit einer solchen Adresse: {k} von {located_pairs.height} ({pct(k, located_pairs.height)})"
    )
    stelle = Counter(h.grob for h, _n, _z in found)
    print(
        "  Stelle der Adressen: "
        + ", ".join(
            f"{s} {stelle.get(s, 0)} ({pct(stelle.get(s, 0), n_f)})"
            for s in STELLEN
            if s != "titel"
        )
    )
    status: Counter[str] = Counter()
    located_wks: dict[tuple[str, str], set[int]] = defaultdict(
        set
    )  # (Dokument, Begriff) -> Bezirke der Adressen
    located_n: Counter[tuple[str, str]] = Counter()  # verortete Adressen je (Dokument, Begriff)
    street_known = 0
    consistent = inconsistent = outside = 0
    multi = multi_resolved = 0
    resolved_pairs: dict[tuple[str, str], set[int]] = defaultdict(set)
    for h, nr, zusatz in found:
        key = norm_street(h.term)
        street = gebref.get(key)
        if street is None:
            status["strasse_unbekannt"] += 1
            continue
        street_known += 1
        how, xy = lookup(street, nr, zusatz)
        status[how] += 1
        if xy is None:
            continue
        wk = bezirke.at(*xy)
        districts = data.term_districts[h.term]
        if how in ("genau", "ohne_zusatz") and wk is not None:
            located_n[(h.doc, h.term)] += 1
            located_wks[(h.doc, h.term)].add(wk)
        if wk is None:
            outside += 1
        elif wk in districts:
            consistent += 1
            resolved_pairs[(h.doc, h.term)].add(wk)
        else:
            inconsistent += 1
        if len(districts) > 1:
            multi += 1
            if wk in districts:
                multi_resolved += 1
    ok = status["genau"] + status["ohne_zusatz"]
    print(
        f"  Straßenname in GebRef gefunden: {street_known} von {n_f} Adressen ({pct(street_known, n_f)})"
    )
    print(
        f"  verortbar (Nummer mit Zusatz genau, oder Hauptnummer bei unbekanntem Zusatz): {wil(ok, n_f)}; "
        f"genau {status['genau']}, ohne Zusatz {status['ohne_zusatz']}, nur mit anderem Zusatz {status['mit_zusatz']}, "
        f"Nummer fehlt {status['nein']}, Straße unbekannt {status['strasse_unbekannt']}"
    )
    lenient = ok + status["mit_zusatz"]
    print(f"  verortbar, großzügig (dazu Nummer nur mit anderem Zusatz): {wil(lenient, n_f)}")
    print(
        f"  verortete Adressen im Wahlbezirk des Begriffs: {consistent}, in einem anderen: {inconsistent}, außerhalb der Stimmbezirke: {outside}"
    )
    print(
        f"  Adressen an Straßen in mehreren Wahlbezirken: {multi}; davon einem der Bezirke zugeordnet: {multi_resolved}"
    )
    # Was eine Hausnummer an Paaren ändert: ein (Dokument, Straße), dessen Adressen alle verortet sind,
    # zählt nur noch für deren Bezirke statt für alle Bezirke der Straße.
    dropped = 0
    for (_doc, term), wks in resolved_pairs.items():
        dropped += len(set(data.term_districts[term]) - wks)
    print(
        f"  (Dokument, Straße) mit verorteter Adresse: {len(resolved_pairs)}; Bezirkszuordnungen, die die Adresse wegnähme (obere Schranke, ohne Blick auf andere Begriffe): {dropped}"
    )
    # Genau gerechnet: ein Paar (Dokument, Bezirk) fällt weg, wenn jeder Begriff des Bezirks im
    # Dokument eine Straße ist, die dort nur mit verorteten Hausnummern vorkommt, und keine dieser
    # Adressen im Bezirk liegt. Das ist die Wirkung „Hausnummer vor Straßenname".
    occ = Counter((h.doc, h.term) for h in hits)
    resolved = {k: wks for k, wks in located_wks.items() if located_n[k] == occ[k]}
    drop: set[tuple[str, int]] = set()
    for doc, wk, terms in pairs.select("id", "wahlkreis_id", "begriffe").iter_rows():
        if all((doc, t) in resolved and wk not in resolved[(doc, t)] for t in terms):
            drop.add((doc, int(wk)))
    full = sum(1 for k in occ if k in resolved)
    print(
        f"  (Dokument, Straße), deren Erwähnungen alle verortete Adressen sind: {full}; "
        f"Paare (Dokument, Wahlbezirk), die damit wegfielen: {len(drop)} von {pairs.height} ({pct(len(drop), pairs.height)})"
    )
    return {
        "erwaehnungen": n_s,
        "mit_nr": n_f,
        "verortbar": ok,
        "grosszuegig": lenient,
        "drop": drop,
    }


# --------------------------------------------------------------------------------------------
# § 3.5 Flächen und benannte Objekte des Portals
# --------------------------------------------------------------------------------------------


def projected(geom: Any, transformer: Any) -> Any:
    """WGS84 nach EPSG:4647, repariert (`buffer(0)`), für Flächenanteile in Quadratmetern."""
    import shapely

    return shapely.transform(
        geom, lambda xy: np.column_stack(transformer.transform(xy[:, 0], xy[:, 1]))
    ).buffer(0)


@dataclass
class Objekt:
    quelle: str
    name: str
    terms: set[str]
    districts: list[int]


def clean_name(name: str) -> str:
    name = re.sub(r'["„“”]', "", name)
    name = re.sub(r"\s+e\.\s?V\.?$", "", name.strip())
    return re.sub(r"\s+", " ", name).strip().lower()


SCHULNAME = re.compile(
    r"((?:[A-ZÄÖÜ][\wäöüß.]*[- ])+(?:Schule|Gymnasium|Realschule|Gesamtschule|Berufskolleg|Hauptschule|Grundschule|Förderschule|Sekundarschule))"
)


def school_terms(*fields: str) -> set[str]:
    text = " ".join(fields)
    text = re.sub(r"\b(Städt\.|Städtische[rs]?|Gem\.|Kath\.|Ev\.|Evang\.)\s*", "", text)
    out = set()
    for m in SCHULNAME.finditer(text):
        name = m.group(1).strip()
        if len(name.split("-")[0].split()[0]) < 3:
            continue
        out.add(name.lower())
        out.add(name.lower().replace(" ", "-"))
    return out


def load_objects(bezirke: Bezirke) -> tuple[list[Objekt], list[tuple[str, str, Any]]]:
    from pyproj import Transformer

    to4647 = Transformer.from_crs("EPSG:4326", "EPSG:4647", always_xy=True)

    def pt(lon: float, lat: float) -> list[int]:
        x, y = to4647.transform(lon, lat)
        wk = bezirke.at(x, y)
        return [wk] if wk is not None else []

    def area(geom: dict[str, Any]) -> list[int]:
        return bezirke.overlapping(projected(shape(geom), to4647))

    objs: list[Objekt] = []
    gj = lambda p: json.loads(checked(FREMDDATEN / p).read_text(encoding="utf-8-sig"))  # noqa: E731
    for f in gj("duesseldorf-stadtteile/Stadtteile_2025_WGS84_EPSG4326_1.geojson")["features"]:
        objs.append(
            Objekt(
                "Stadtteile",
                f["properties"]["Name"],
                {clean_name(f["properties"]["Name"])},
                area(f["geometry"]),
            )
        )
    for f in gj("duesseldorf-sportstaetten/Sportstaetten_Duesseldorf.geojson")["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        objs.append(
            Objekt(
                "Sportstätten",
                f["properties"]["name"],
                {clean_name(f["properties"]["name"])},
                pt(lon, lat),
            )
        )
    for f in gj("duesseldorf-kirchen/Kirchen_in_Duesseldorf.geojson")["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        objs.append(
            Objekt(
                "Kirchen",
                f["properties"]["name"],
                {clean_name(f["properties"]["name"])},
                pt(lon, lat),
            )
        )
    for f in gj("duesseldorf-museen/Duesseldorfer_Museen_erweiterte_Info_WGS84_4326.geojson")[
        "features"
    ]:
        lon, lat = f["geometry"]["coordinates"][:2]
        objs.append(
            Objekt(
                "Museen",
                f["properties"]["NAME"],
                {clean_name(f["properties"]["NAME"])},
                pt(lon, lat),
            )
        )
    for name in (
        "Standorte_der_S-Bahnhoefe_in_Duesseldorf.geojson",
        "Standorte_der_Fernbahnhoefe_in_Duesseldorf_0.geojson",
    ):
        for f in gj(f"duesseldorf-bahnhoefe/{name}")["features"]:
            props = f["properties"]
            x, y = float(props["UTM EAST"]), float(props["UTM NORTH"])  # schon mit Zonenzahl
            wk = bezirke.at(x, y)
            n = clean_name(props["NAME"])
            objs.append(
                Objekt(
                    "Bahnhöfe",
                    props["NAME"],
                    {f"s-bahnhof {n}", f"bahnhof {n}", f"s-bahn-haltepunkt {n}"}
                    if n != "hauptbahnhof"
                    else {"hauptbahnhof"},
                    [wk] if wk else [],
                )
            )
    for f in gj("duesseldorf-wohnbauflaechen/potenzial_wohnen_2026.geojson")["features"]:
        props = f["properties"]
        objs.append(
            Objekt(
                "Wohnbauflächen", props["name"], {clean_name(props["name"])}, area(f["geometry"])
            )
        )
    with checked(FREMDDATEN / "duesseldorf-kleingaerten/Kleingaerten_Duesseldorf.csv").open(
        encoding="utf-8-sig"
    ) as handle:
        for r in csv.DictReader(handle, delimiter=";"):
            quoted = re.findall(r'"([^"]+)"', r["Anlage / Verein"])
            if quoted:
                # ohne Koordinate: nur Begriffe und Dokumente, kein Bezirk
                objs.append(
                    Objekt(
                        "Kleingärten",
                        r["Anlage / Verein"],
                        {
                            f"kleingartenanlage {quoted[0].lower()}",
                            f"kgv {quoted[0].lower()}",
                            f"kleingartenverein {quoted[0].lower()}",
                        },
                        [],
                    )
                )
    with checked(FREMDDATEN / "duesseldorf-kitas/Tageseinrichtungen_fuer_Kinder.csv").open(
        encoding="utf-8-sig"
    ) as handle:
        for r in csv.DictReader(handle, delimiter=";"):
            try:  # eine Zeile trägt „512.209.216.102.838" als Breite: ohne Bezirk
                where = pt(float(r["LONGITUDE"]), float(r["LATITUDE"]))
            except ValueError:
                where = []
            objs.append(
                Objekt("Kitas", r["EINRICHTUNGSNAME"], {clean_name(r["EINRICHTUNGSNAME"])}, where)
            )
    with checked(FREMDDATEN / "nrw-schuldaten/schuldaten.csv").open(encoding="utf-8") as handle:
        next(handle)  # „sep=;"
        for r in csv.DictReader(handle, delimiter=";"):
            if r["Gemeindeschluessel"] != "05111000":
                continue
            x, y = float(r["UTMRechtswert"]) + UTM_ZONE_OFFSET, float(r["UTMHochwert"])
            wk = bezirke.at(x, y)
            objs.append(
                Objekt(
                    "Schulen",
                    r["Kurzbezeichnung"],
                    school_terms(
                        r["Schulbezeichnung_1"], r["Schulbezeichnung_2"], r["Schulbezeichnung_3"]
                    ),
                    [wk] if wk else [],
                )
            )
    plans = json.loads(
        checked(FREMDDATEN / "nrw-bauleitplanung/bplan_duesseldorf_gkz05111000.geojson").read_text(
            encoding="utf-8"
        )
    )
    bplan: list[tuple[str, str, Any]] = []
    for f in plans["features"]:
        title = f["properties"]["officialTitle"]
        bplan.append((title, f["properties"]["planTypeName.title"], f["geometry"]))
    return objs, bplan


def objects_report(objs: list[Objekt], data: Daten, pairs: pl.DataFrame) -> None:
    known = set(data.term_districts)
    base_pairs = set(pairs.select("id", "wahlkreis_id").iter_rows())
    term_objs: dict[str, list[Objekt]] = defaultdict(list)
    for o in objs:
        for t in o.terms:
            if len(t) >= 5:
                term_objs[t].append(o)
    new_terms = sorted(t for t in term_objs if t not in known)
    processor = KeywordProcessor(case_sensitive=False)
    processor.add_keywords_from_list(new_terms)
    docs_of: dict[str, set[str]] = defaultdict(set)
    for doc, store in data.corpus.select("id", "store").iter_rows():
        if store:
            for t in processor.extract_keywords(store):
                docs_of[t].add(doc)
    rows = []
    for quelle in sorted({o.quelle for o in objs}):
        mine = [o for o in objs if o.quelle == quelle]
        terms = {t for o in mine for t in o.terms if len(t) >= 5}
        already = {t for t in terms if t in known}
        fresh = terms - already
        hit_terms = {t for t in fresh if docs_of.get(t)}
        docs = {d for t in fresh for d in docs_of.get(t, ())}
        pairs_q = {
            (d, wk)
            for t in fresh
            for o in term_objs[t]
            if o.quelle == quelle
            for wk in o.districts
            for d in docs_of.get(t, ())
        }
        new = pairs_q - base_pairs
        ambiguous = sum(
            1 for t in fresh if len({wk for o in term_objs[t] for wk in o.districts}) > 1
        )
        with_place = sum(1 for o in mine if o.districts)
        rows.append(
            (
                quelle,
                len(mine),
                with_place,
                len(terms),
                len(already),
                len(fresh),
                len(hit_terms),
                len(docs),
                len(pairs_q),
                len(new),
                ambiguous,
            )
        )
    table(
        rows,
        [
            "Quelle",
            "Objekte",
            "davon verortet",
            "Begriffe",
            "schon im Wörterbuch",
            "neu",
            "neu mit Treffer",
            "Dokumente",
            "Paare",
            "davon neue Paare",
            "Begriffe in mehreren Bezirken",
        ],
    )
    all_new_pairs = {
        (d, wk)
        for t in new_terms
        for o in term_objs[t]
        for wk in o.districts
        for d in docs_of.get(t, ())
    } - base_pairs
    no_area = {
        (d, wk)
        for t in new_terms
        for o in term_objs[t]
        if o.quelle != "Stadtteile"
        for wk in o.districts
        for d in docs_of.get(t, ())
    } - base_pairs
    print(
        f"  zusammen neue Paare: {len(all_new_pairs)} ({pct(len(all_new_pairs), pairs.height)} der {pairs.height} Paare); ohne Stadtteile: {len(no_area)} ({pct(len(no_area), pairs.height)})"
    )
    top = sorted(((len(docs_of.get(t, ())), t) for t in new_terms), reverse=True)[:15]
    print("  neue Begriffe mit den meisten Dokumenten: " + "; ".join(f"{t} {n}" for n, t in top))
    st = [o for o in objs if o.quelle == "Stadtteile"]
    print(
        f"  Stadtteile: im Mittel {sum(len(o.districts) for o in st) / len(st):.1f} Wahlbezirke je Stadtteil (Überlappung ≥ 5 % der Stadtteilfläche)"
    )


BPLAN_NR = re.compile(r"(?<![\d/])(\d{2}/\d{3}|\d{4}/\d{3})(?![\d/])")
BPLAN_KONTEXT = re.compile(
    r"(?i)bebauungsplan|b-plan|bplan|bauleitplan|vorhabenbezogen|planverfahren|plan\s*nr|aufstellungsbeschluss|änderungsverfahren"
)


def bplan_report(
    bplan: list[tuple[str, str, Any]], data: Daten, bezirke: Bezirke, pairs: pl.DataFrame
) -> None:
    from pyproj import Transformer

    to4647 = Transformer.from_crs("EPSG:4326", "EPSG:4647", always_xy=True)
    numbers: dict[str, list[int]] = {}
    kinds = Counter(k for _t, k, _g in bplan)
    for title, _kind, geom in bplan:
        wks = bezirke.overlapping(projected(shape(geom), to4647))
        for nr in re.findall(r"\d{2}/\d{3}|\d{4}/\d{3}", title):
            numbers[nr] = wks
    print(
        f"  Bauleitpläne NRW, Stadt: {len(bplan)} Pläne ({dict(kinds)}), {len(numbers)} Plannummern (neu und alt) im Titel"
    )
    mentions: dict[str, set[str]] = defaultdict(set)
    for doc, raw in data.corpus.select("id", "raw").iter_rows():
        for m in BPLAN_NR.finditer(raw):
            if BPLAN_KONTEXT.search(raw[max(0, m.start() - 120) : m.start()]):
                mentions[m.group(1)].add(doc)
    docs_any = {d for ds in mentions.values() for d in ds}
    known = {nr: ds for nr, ds in mentions.items() if nr in numbers}
    docs_known = {d for ds in known.values() for d in ds}
    base_pairs = set(pairs.select("id", "wahlkreis_id").iter_rows())
    plan_pairs = {(d, wk) for nr, ds in known.items() for d in ds for wk in numbers[nr]}
    new = plan_pairs - base_pairs
    print(
        f"  Plannummern im Text (mit „Bebauungsplan“ o. ä. in den 120 Zeichen davor): {len(mentions)} verschiedene in {len(docs_any)} Dokumenten; "
        f"davon im Landesdatensatz: {len(known)} Nummern in {len(docs_known)} Dokumenten ({pct(len(known), len(mentions))} der Nummern)"
    )
    print(f"  Paare über die Geltungsbereiche: {len(plan_pairs)}, davon neu: {len(new)}")


# --------------------------------------------------------------------------------------------
# Ablauf
# --------------------------------------------------------------------------------------------


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aufgaben", action="store_true", help="Stichprobe und Kodieraufgaben schreiben"
    )
    args = parser.parse_args(argv)
    t_start = time.perf_counter()
    load = os.getloadavg()
    print(
        f"Lauf am {date.today().isoformat()}, Last (uptime): {load[0]:.1f} / {load[1]:.1f} / {load[2]:.1f}"
    )

    print("\n§ 2 Datenlage")
    data = load_data()
    struktur = load_struktur()
    print(
        f"  Korpus: {data.corpus.height} Dokumente; Wörterbuch: {len(data.term_districts)} Begriffe in {len(data.dictionary)} Wahlbezirken; stadtweit: {len(data.citywide)} ({data.citywide_basis})"
    )
    hits, check = find_hits(data, struktur)
    print(
        f"  Rohtext zu {check['dokumente'] - check['ohne_rohtext']} Dokumenten; Textstore aus dem Rohtext nachgebaut und gleich: {check['store_gleich']}, "
        f"anders: {check['store_anders']} ({check['sekunden']:.0f} s mit dem Regelwerk von 11)"
    )
    print(
        f"  (Dokument, Begriff) im Index: {check['index_paare']}; mit Stelle wiedergefunden: {check['paare_gleich']}; "
        f"nur im Index (Dokumente ohne Rohtext): {check['nur_index']}; nur gefunden: {check['nur_gefunden']}"
    )
    assert check["nur_gefunden"] == 0, (
        "derselbe Matcher auf demselben Text findet nichts, was der Index nicht hat"
    )
    ref = dict(data.corpus.select("id", "reference").iter_rows())
    no_raw = data.corpus.filter(pl.col("raw") == "")
    with_store = no_raw.filter(pl.col("store") != "")
    unlocated = set(no_raw["id"]) | set(check["anders"])
    lost = Counter(
        ref[d]
        for _t, ids in data.index.select("suchbegriffe", "paper_ids").iter_rows()
        for d in ids
        if d in unlocated
    )
    stores = ", ".join(
        f"{r} mit {n} Zeichen"
        for r, n in with_store.select("reference", pl.col("store").str.len_chars()).iter_rows()
    )
    print(
        f"  ohne Rohtext: {no_raw.height} Dokumente, davon mit Textstore: {with_store.height} ({stores}); "
        f"Textstore anders: {', '.join(ref[d] for d in check['anders'])}; "
        f"Paare des Index ohne Stelle je Dokument: {dict(lost)}"
    )
    in_title = title_terms(data, check["titles"])
    dt = doc_terms(hits, in_title)
    pairs = rule_columns(doc_districts(dt, data))
    assert pairs.height == int(data.results["anzahl_treffer"].sum()), "Paare = Summe der Treffer"

    print("\n§ 3.1 Wo steht ein Treffer?")
    position_report(hits, dt, pairs, data)
    print("\n  nach Begriffsart (beste Stelle je Dokument und Begriff):")
    type_report(dt, data)
    print("\n  je Wahlbezirk (Paare mit Stelle; Anteile an ihnen):")
    district_report(pairs, data)

    print("\n§ 3.2 Die Regel „handelt von“")
    rule_report(pairs, data, struktur)

    bezirke = Bezirke.load(data.interim)
    print("\n§ 3.4 Hausnummern (vor § 3.3 gerechnet, weil § 3.3 ihre Zuordnung als Variante nutzt)")
    addresses = house_numbers(hits, data, bezirke, pairs)

    print("\n§ 3.3 Wirkung als Sensitivität (Treffer je Wahlbezirk, Tabelle 5, Wörterbuchgröße)")
    sensitivity(pairs, data, addresses["drop"])

    print(
        "\n§ 3.5 Flächen und benannte Objekte des Portals (Schalter aus; nichts davon zählt heute)"
    )
    objs, bplan = load_objects(bezirke)
    objects_report(objs, data, pairs)
    bplan_report(bplan, data, bezirke, pairs)

    print(f"\n§ 4 Stichprobe (Paare mit Stelle, geschichtet nach bester Stelle, Seed {SEED})")
    chosen = draw_sample(pairs, struktur)
    print(f"  gezogen: {len(chosen)} Paare aus {len({c['id'] for c in chosen})} Dokumenten")
    if args.aufgaben:
        write_tasks(chosen, pairs, hits, data, check["results"], bezirke.names)
    print("\n§ 4.1 Kodierung")
    score_labels()
    load = os.getloadavg()
    print(f"\nLaufzeit gesamt: {time.perf_counter() - t_start:.0f} s, Last am Ende: {load[0]:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
