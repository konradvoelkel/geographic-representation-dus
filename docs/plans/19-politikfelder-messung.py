"""Rechnet die Zahlen von `19-politikfelder.md` nach (Vorhaben 19 „Politikfelder nach dem CAP").

    uv run python docs/plans/19-politikfelder-messung.py [teil ...]

Ohne Teil rechnet es aus dem, was liegt, alle Zahlen des Messdokuments nach (Datenlage, Wege,
Übereinstimmung, Laufzeiten, nach der Kodierung das Urteil) und ruft kein Modell. Die Teile:

- `grundgesamtheit`: schreibt die Grundgesamtheit der Testmenge (Hauptperiode, Dokumente mit Text im
  Korpus und im Rohtext, Schicht = Gremiumsart|Gruppe der Dokumentart) nach
  `<profil>/messung/19-politikfelder-grundgesamtheit.parquet`. Danach zieht F4 die 300:
  `georep validate sample 19-politikfelder`, `georep validate tasks 19-politikfelder --coder A
  --texts <rohtext>` (und B).
- `entwicklung`: zieht die 200 der Entwicklungsmenge (ohne die 300) nach
  `validierung/19-politikfelder/entwicklung.csv` (nur IDs).
- `ausschuss`: Weg 2A und 2B für alle Dokumente der Hauptperiode.
- `cap`: liest die deutschen CAP-Daten (Fremddaten, nur lesend, nur CSV) und schreibt
  Training, zurückgehaltene 10 % und die 200 Anfragentitel der zweiten Prüfung.
- `tfidf`: das Nebenverfahren (TF-IDF und logistische Regression auf den CAP-Daten).
- `silber`: zieht 4 000 Ratsdokumente außerhalb von Test- und Entwicklungsmenge (Silberlabels).
- `eingabe`: schreibt die Eingabe von Weg 3 (Titel und Textanfang) für das Trainingsskript.
- `llm --menge test|entwicklung|silber|cap [--modell M] [--limit N]`: Weg 1 über die Naht von F5; nur unter
  der GPU-Sperre aufrufen (`flock …/gpu-queue/gpu.lock`). Antworten liegen im Modellcache und sind
  fortsetzbar; die Ausgabe ist eine Parquet-Datei je Menge und Modell unter `$GEOREP_MESSDATEN`.
- `prompt`: druckt Prompt-Version, Länge und SHA-256 des Systemprompts (für das Einfrieren).
- `vorhersage --weg W`: schreibt die Testvorhersage eines Wegs für `georep validate score --pred`.

Alles, was ein Verfahren ausgibt, liegt unter `$GEOREP_MESSDATEN/19-politikfelder/` (nie im Repo);
ins Repo kommen nur IDs (Stichprobe, Entwicklungsmenge) und später die Labels (F4). Die Werte, die
vor der Messung festgelegt wurden (Messdokument § 8), stehen oben als Konstanten.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

os.environ.setdefault("POLARS_MAX_THREADS", "4")
import polars as pl  # noqa: E402

from georep.layout import Layout  # noqa: E402
from georep.settings import load_settings  # noqa: E402
from georep.validation.codebook import Codebook, load_codebook  # noqa: E402
from georep.validation.measures import classify_scores, cohen_kappa  # noqa: E402
from georep.validation.sample import allocate  # noqa: E402
from georep.validation.tasks import load_documents, show_document  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PROFIL = "duesseldorf"
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
FREMDDATEN = Path(os.environ.get("GEOREP_FREMDDATEN", "/media/konrad/xtraspace/georep/fremddaten"))
ROHTEXT = MESSDATEN / "rohtext" / "duesseldorf.parquet"
AUSGABE = MESSDATEN / "19-politikfelder"
CAP_DE = FREMDDATEN / "cap" / "cap-deutschland"
VORHABEN = "19-politikfelder"
VALID = REPO / "validierung" / VORHABEN
CODEBUCH = VALID / "codebuch.toml"
STICHPROBE = VALID / "stichprobe.csv"
ENTWICKLUNG = VALID / "entwicklung.csv"
LABELS = VALID / "labels.csv"
GRUNDGESAMTHEIT = "messung/19-politikfelder-grundgesamtheit.parquet"  # relativ zum Profilordner
LAUFZEITEN = AUSGABE / "laufzeiten.jsonl"
SILBER = AUSGABE / "silber.csv"  # IDs der Silbermenge (aus dem Seed nachrechenbar)

# ================================================================================================
# Vorab festgelegt (Messdokument § 8, 2026-11-23). Nicht nach einem Ergebnis ändern.
# ================================================================================================
SEED_TEST = 20261123  # Testmenge (codebuch.toml, [sample]) und Bootstrap
SEED_ENTWICKLUNG = 20261124
SEED_CAP = 20261125  # 200 Anfragentitel der zweiten Prüfung und die zurückgehaltenen 10 %
SEED_SILBER = 20261126  # 4 000 Ratsdokumente für Silberlabels (GPU-Warteschlange), ohne Test
N_SILBER = 4000
WEG3_ZEICHEN = 1500  # Titel und so viele Zeichen Rohtext sind die Eingabe von Weg 3
N_ENTWICKLUNG = 200
N_CAP_TITEL = 200
ANTEIL_ZURUECK = 0.10  # zurückgehaltener Anteil der deutschen CAP-Daten (Weg 3, zweite Prüfung)
BOOTSTRAP = 2000
KRITERIUM_F1 = 0.70
ABDECKUNG_RUECKFALL = 0.70
ALPHA_URTEIL, ALPHA_STUFE3 = 0.67, 0.80
SILBER_MINDESTENS = 2000  # Ratsdokumente mit Silberlabels, ab denen 3b statt 3a ins Urteil geht

CODES = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "13", "14", "15", "16", "17")
CODES += ("18", "19", "20", "21", "23", "99")
UNGUELTIG = "ungueltig"  # eine Antwort ohne gültige Nummer; zählt als falsche Klasse

# Weg 2: Ausschuss -> Hauptthema (Messdokument § 8.4); "" ist die Restklasse der Kette (2A).
AUSSCHUSS_CAP: dict[str, str] = {
    "ABA": "20",
    "ADIG": "20",
    "AGS": "13",
    "APS": "14",
    "AUS": "7",
    "AWIR": "15",
    "AWIZ": "15",
    "AWM": "14",
    "AÖE": "7",
    "BAU": "20",
    "GLA": "2",
    "HFA": "1",
    "JHA": "13",
    "KUA": "23",
    "OVA": "10",
    "RPAU": "20",
    "SCHUA": "6",
    "SEBD": "7",
    "SPOA": "13",
    "WALTW": "20",
    "WABTW": "20",
    "WPA": "20",
    "AWTL": "20",
    "POA": "20",
    "ACI": "9",
    "": "99",
}

# Gruppe der Dokumentart für die Schichtung (Gremiumsart × Gruppe).
GRUPPEN = (
    ("beschluss", ("Beschlussvorlage", "Bezirksvertretung Beschlussvorlage", "Bedarfsbeschluss")),
    ("beschluss", ("A+F Beschluss", "Beschlussvorlage RPA")),
    ("information", ("Informationsvorlage", "Bezirksvertretung Informationsvorlage")),
    ("information", ("Berichtsvorlage",)),
)
PRAEFIXE = (("antrag", ("Antrag", "Haushaltsantrag")), ("anfrage", ("Anfrage", "zAnfrage")))
PRAEFIXE += (("eingabe", ("Eingabe",)),)

# Weg 1: Prompt. Die Version zählt hoch, wenn sich Systemprompt, Nutzerprompt oder Parser ändern;
# eingefroren wird sie mit dem SHA-256 des Systemprompts in einem Commit vor dem Testlauf.
PROMPT_VERSION = "19-cap-1"
NUM_PREDICT = 64
MODELL = "qwen3.6:27b"
ANTWORT = re.compile(r"THEMA\s*:\s*\**\s*(\d{1,2})\b")


# ------------------------------------------------------------------------------------------------
# Hilfen
# ------------------------------------------------------------------------------------------------
def umgebung() -> tuple[Any, Layout]:
    settings = load_settings(cwd=REPO, profile=PROFIL)
    return settings, Layout.from_settings(settings)


def codebuch() -> Codebook:
    return load_codebook(CODEBUCH, VORHABEN)


def uptime() -> str:
    return subprocess.run(["uptime"], capture_output=True, text=True, check=False).stdout.strip()


def rang(seed: int, key: str) -> str:
    return hashlib.sha256(f"{seed}|{key}".encode()).hexdigest()


def gruppe(art: str | None) -> str:
    art = art or ""
    for name, arten in GRUPPEN:
        if art in arten:
            return name
    for name, praefixe in PRAEFIXE:
        if art.startswith(praefixe):
            return name
    return "sonstige"


def ziehe(frame: pl.DataFrame, n: int, seed: int) -> pl.DataFrame:
    """Proportional geschichtet, bottom-k nach sha256(seed|id) wie F4 (`georep.validation.sample`)."""
    groessen = dict(frame.group_by("schicht").len().iter_rows())
    quoten = allocate(groessen, n, "proportional")
    gerankt = frame.with_columns(
        pl.col("id").map_elements(lambda i: rang(seed, i), return_dtype=pl.String).alias("rang")
    ).sort("schicht", "rang")
    teile = [
        gerankt.filter(pl.col("schicht") == s).head(k).with_columns(pl.lit(groessen[s]).alias("n"))
        for s, k in sorted(quoten.items())
    ]
    return pl.concat(teile).drop("rang").sort("id")


def lies_ids(pfad: Path) -> list[str]:
    return pl.read_csv(pfad, infer_schema_length=0).get_column("id").to_list()


def protokoll(eintrag: dict[str, Any]) -> None:
    AUSGABE.mkdir(parents=True, exist_ok=True)
    with LAUFZEITEN.open("a", encoding="utf-8") as f:
        f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")


def titel(text: str) -> None:
    print(f"\n=== {text}")


# ------------------------------------------------------------------------------------------------
# Grundgesamtheit und Mengen
# ------------------------------------------------------------------------------------------------
def korpus(layout: Layout) -> pl.DataFrame:
    papers = pl.read_parquet(
        layout.corpus, columns=["id", "name", "paper_type", "file_name", "text", "date"]
    )
    gremien = pl.read_parquet(layout.papers_bodies, columns=["id", "gremium", "gremium_art"])
    roh = pl.read_parquet(ROHTEXT, columns=["name", "text"]).rename(
        {"name": "file_name", "text": "rohtext"}
    )
    return (
        papers.join(gremien, on="id", how="left")
        .join(roh, on="file_name", how="left")
        .with_columns(
            pl.col("paper_type").map_elements(gruppe, return_dtype=pl.String).alias("gruppe"),
            (pl.col("text").fill_null("").str.strip_chars() != "").alias("mit_text"),
            (pl.col("rohtext").fill_null("").str.strip_chars() != "").alias("mit_rohtext"),
        )
        .sort("id")
    )


def grundgesamtheit(layout: Layout) -> pl.DataFrame:
    k = korpus(layout)
    return (
        k.filter(pl.col("mit_text") & pl.col("mit_rohtext"))
        .select(
            "id",
            (pl.col("gremium_art") + "|" + pl.col("gruppe")).alias("schicht"),
            pl.col("paper_type").alias("dokumentart"),
        )
        .sort("id")
    )


def schreibe_grundgesamtheit(layout: Layout) -> None:
    gg = grundgesamtheit(layout)
    ziel = layout.root / GRUNDGESAMTHEIT
    ziel.parent.mkdir(parents=True, exist_ok=True)
    gg.write_parquet(ziel)
    print(f"{gg.height} Dokumente nach {ziel}")
    print(gg.group_by("schicht").len().sort("schicht"))


def schreibe_entwicklung(layout: Layout) -> None:
    test = set(lies_ids(STICHPROBE))
    gg = grundgesamtheit(layout).filter(~pl.col("id").is_in(sorted(test)))
    entw = ziehe(gg, N_ENTWICKLUNG, SEED_ENTWICKLUNG).select("id", "schicht", "n")
    entw.rename({"n": "schicht_n"}).write_csv(ENTWICKLUNG)
    print(f"{entw.height} Dokumente nach {ENTWICKLUNG} (ohne {len(test)} der Testmenge)")


def schreibe_silber(layout: Layout) -> None:
    """4 000 Ratsdokumente außerhalb von Test- und Entwicklungsmenge für Silberlabels (Weg 3b)."""
    raus = set(lies_ids(STICHPROBE)) | set(lies_ids(ENTWICKLUNG))
    gg = grundgesamtheit(layout).filter(~pl.col("id").is_in(sorted(raus)))
    silber = ziehe(gg, N_SILBER, SEED_SILBER).select(
        "id", "schicht", pl.col("n").alias("schicht_n")
    )
    AUSGABE.mkdir(parents=True, exist_ok=True)
    silber.write_csv(SILBER)
    print(f"{silber.height} Dokumente nach {SILBER}")


def schreibe_eingabe(layout: Layout) -> None:
    """Die Eingabe von Weg 3 je Ratsdokument (Titel und Textanfang) für das Trainingsskript.

    Das Trainingsskript läuft in einem eigenen Venv ohne georep; es liest nur diese Datei.
    """
    mengen = {"test": lies_ids(STICHPROBE), "entwicklung": lies_ids(ENTWICKLUNG)}
    if SILBER.is_file():
        mengen["silber"] = lies_ids(SILBER)
    alle = sorted({i for ids in mengen.values() for i in ids})
    docs = load_documents(layout, codebuch(), set(alle), texts=ROHTEXT)
    rows = [
        {
            "id": i,
            "menge": menge,
            "text": " ".join(f"{docs[i].title}\n{docs[i].text[:WEG3_ZEICHEN]}".split()),
        }
        for menge, ids in mengen.items()
        for i in ids
    ]
    pl.DataFrame(rows).sort("menge", "id").write_parquet(AUSGABE / "ratsdokumente.parquet")
    print(f"{len(rows)} Eingaben nach {AUSGABE / 'ratsdokumente.parquet'}")


# ------------------------------------------------------------------------------------------------
# Weg 2: Ausschuss -> CAP
# ------------------------------------------------------------------------------------------------
def weg2(settings: Any, layout: Layout) -> pl.DataFrame:
    """2A aus der Kette, 2B dasselbe Modell ohne Schwelle; eine Zeile je Dokument mit Text."""
    from georep.analysis.committees import assign_committees
    from georep.analysis.topics import TopicRules

    a = pl.read_parquet(layout.papers_committee, columns=["id", "ausschuss"])
    ohne_schwelle = settings.classify.model_copy(update={"min_probability": 0.0})
    b = assign_committees(
        pl.read_parquet(layout.corpus, columns=["id", "text"]),
        pl.read_parquet(layout.papers_bodies),
        settings.topics,
        ohne_schwelle,
        TopicRules.from_settings(settings),
    ).papers.select("id", pl.col("ausschuss").alias("ausschuss_b"))
    frame = a.join(b, on="id", how="left").sort("id")
    fehlend = sorted(
        set(frame.get_column("ausschuss").to_list() + frame.get_column("ausschuss_b").to_list())
        - set(AUSSCHUSS_CAP)
    )
    if fehlend:
        raise SystemExit(f"Ausschuss ohne Hauptthema in AUSSCHUSS_CAP: {fehlend}")
    return frame.with_columns(
        pl.col("ausschuss").replace_strict(AUSSCHUSS_CAP).alias("weg2a"),
        pl.col("ausschuss_b").replace_strict(AUSSCHUSS_CAP).alias("weg2b"),
    )


# ------------------------------------------------------------------------------------------------
# Weg 1: LLM mit Codebuch
# ------------------------------------------------------------------------------------------------
def systemprompt(cb: Codebook) -> str:
    frage = next(q for q in cb.questions if q.id == "politikfeld")
    zeilen = [
        "Du kodierst Ratsdokumente einer deutschen Großstadt nach dem Codebuch des Comparative "
        "Agendas Project (CAP). Du bekommst Dokumentart, Titel und den Anfang des Textes.",
        "",
        "## Anweisungen",
        "",
        cb.instructions.strip(),
        "",
        f"## Frage: {frage.question}",
        "",
        frage.instructions.strip(),
        "",
    ]
    for o in frage.options:
        zeilen.append(f"- {o.value} ({o.name}): {' '.join(o.definition.split())}")
        if o.example:
            zeilen.append(f"  Beispiel: {o.example}")
    zeilen += [
        "",
        "## Antwort",
        "",
        "Antworte mit genau einer Zeile und sonst nichts: `THEMA: <Nummer>`, die Nummer einer der "
        "Optionen oben (1 bis 23 oder 99), etwa `THEMA: 10`.",
    ]
    return "\n".join(zeilen) + "\n"


def nutzerprompt(art: str, auftrag: dict[str, Any]) -> str:
    return (
        f"Dokumentart: {art}\nTitel: {auftrag.get('titel', '')}\n\n"
        f"Ausschnitt (erste {auftrag['ausschnitt_ende']} von {auftrag['zeichen']} Zeichen):\n"
        f"{auftrag['ausschnitt']}"
    )


def parse(antwort: str | None) -> str:
    if antwort is None:
        return UNGUELTIG
    m = ANTWORT.search(antwort)
    return m.group(1) if m and m.group(1) in CODES else UNGUELTIG


def prompts_ratsdokumente(layout: Layout, ids: Sequence[str]) -> list[tuple[str, str]]:
    """(id, Nutzerprompt) mit genau dem Material der Kodierer (`show_document` aus F4)."""
    cb = codebuch()
    docs = load_documents(layout, cb, set(ids), texts=ROHTEXT)
    arten = dict(
        pl.read_parquet(layout.corpus, columns=["id", "paper_type"])
        .filter(pl.col("id").is_in(list(ids)))
        .iter_rows()
    )
    return [(i, nutzerprompt(arten.get(i) or "", show_document(docs[i], cb, [])[0])) for i in ids]


def prompts_cap() -> list[tuple[str, str]]:
    titel_ = pl.read_parquet(AUSGABE / "cap_pruefung.parquet")
    return [
        (
            r["id"],
            f"Dokumentart: Anfrage im Bundestag\nTitel: {r['text']}\n\nAusschnitt: (nur Titel)",
        )
        for r in titel_.iter_rows(named=True)
    ]


def weg1(settings: Any, layout: Layout, menge: str, modell: str, limit: int) -> None:
    from georep.ml.base import GenerationUse
    from georep.ml.batch import generate_texts, progress_log
    from georep.ml.cache import ModelCache
    from georep.ml.ollama import client_from_settings, generation_options, generator_from_settings

    if menge == "test":
        paare = prompts_ratsdokumente(layout, lies_ids(STICHPROBE))
    elif menge == "entwicklung":
        paare = prompts_ratsdokumente(layout, lies_ids(ENTWICKLUNG))
    elif menge == "silber":
        paare = prompts_ratsdokumente(layout, lies_ids(SILBER))
    else:
        paare = prompts_cap()
    system = systemprompt(codebuch())
    options = dataclasses.replace(generation_options(settings.ml), num_predict=NUM_PREDICT)
    client = client_from_settings(settings.ml)
    use = GenerationUse(
        generator_from_settings(settings.ml, client, model=modell), PROMPT_VERSION, options
    )
    vorher = uptime()
    start = time.time()
    with ModelCache(layout.ml_cache, use.name) as cache:
        found = generate_texts(
            use, cache, [p for _, p in paare], system=system, limit=limit, progress=progress_log()
        )
    wand = time.time() - start
    nachher = uptime()
    print(found.report.line())
    rows = [
        {"id": i, "antwort": t, "label": parse(t), "abgeschnitten": c}
        for (i, _), t, c in zip(paare, found.texts, found.truncated, strict=True)
    ]
    ziel = AUSGABE / f"weg1_{menge}_{modell.replace(':', '-')}.parquet"
    AUSGABE.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows, schema_overrides={"antwort": pl.String}).write_parquet(ziel)
    protokoll(
        {
            "zeit": time.strftime("%Y-%m-%d %H:%M:%S"),
            "teil": "llm",
            "menge": menge,
            "modell": modell,
            "digest": use.model.digest,
            "prompt": PROMPT_VERSION,
            "eingaben": found.report.total,
            "neu": found.report.computed,
            "aus_cache": found.report.cached,
            "offen": found.report.left,
            "sekunden_batch": round(found.report.seconds, 1),
            "sekunden_wand": round(wand, 1),
            "uptime_vorher": vorher,
            "uptime_nachher": nachher,
        }
    )
    print(f"{len(rows)} Antworten nach {ziel}; {Counter(r['label'] for r in rows).most_common()}")


# ------------------------------------------------------------------------------------------------
# Deutsche CAP-Daten (Fremddaten) und Nebenverfahren
# ------------------------------------------------------------------------------------------------
def cap_daten() -> pl.DataFrame:
    anfragen = pl.read_csv(
        CAP_DE / "anfrage_1976-2005_website-release_2.5.csv", infer_schema_length=0
    ).select(
        ("anfrage:" + pl.col("doc_id") + ":" + pl.col("date")).alias("id"),
        pl.col("title").alias("text"),  # ASCII-Umschrift („Laender") wie geliefert
        pl.col("cap_topic").alias("label"),
        pl.lit("anfrage").alias("quelle"),
    )
    programme = (
        pl.read_csv(
            CAP_DE / "manifesto_1949-2013_website-release_2.5_2_3.csv", infer_schema_length=0
        )
        .filter((pl.col("junk") == "0") & pl.col("cap_topic").is_in(list(CODES)))
        .select(
            ("programm:" + pl.col("manifesto_id") + ":" + pl.col("sentence_id")).alias("id"),
            pl.col("sentence_text").alias("text"),
            pl.col("cap_topic").alias("label"),
            pl.lit("programm").alias("quelle"),
        )
    )
    frame = (
        pl.concat([anfragen, programme])
        .filter(pl.col("label").is_in(list(CODES)) & (pl.col("text").str.len_chars() > 0))
        .unique("id", keep="first")
        .sort("id")
    )
    # je Quelle und Label die 10 % mit dem kleinsten Rang zurückhalten (bottom-k, reproduzierbar)
    frame = frame.with_columns(
        pl.col("id").map_elements(lambda i: rang(SEED_CAP, i), return_dtype=pl.String).alias("r")
    ).with_columns(
        (
            pl.col("r").rank("ordinal").over("quelle", "label")
            <= (pl.len().over("quelle", "label") * ANTEIL_ZURUECK).ceil()
        ).alias("zurueck")
    )
    return frame.drop("r")


def schreibe_cap() -> None:
    frame = cap_daten()
    AUSGABE.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(AUSGABE / "cap_de.parquet")
    # 200 Anfragentitel aus den zurückgehaltenen, proportional nach Hauptthema
    zurueck = frame.filter(pl.col("zurueck") & (pl.col("quelle") == "anfrage")).rename(
        {"label": "schicht"}
    )
    pruefung = ziehe(zurueck, N_CAP_TITEL, SEED_CAP).rename({"schicht": "label"})
    pruefung.select("id", "text", "label").write_parquet(AUSGABE / "cap_pruefung.parquet")
    print(
        frame.group_by("quelle", "zurueck").len().sort("quelle", "zurueck"),
        f"\n{pruefung.height} Anfragentitel für die zweite Prüfung",
    )


def tfidf(layout: Layout) -> None:
    """Nebenverfahren: TF-IDF und logistische Regression auf den CAP-Daten (ohne Ratsdokumente)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    cap = pl.read_parquet(AUSGABE / "cap_de.parquet")
    train, zurueck = cap.filter(~pl.col("zurueck")), cap.filter(pl.col("zurueck"))
    vec = TfidfVectorizer(sublinear_tf=True, min_df=2, ngram_range=(1, 2), lowercase=True)
    x = vec.fit_transform(train.get_column("text").to_list())
    model = LogisticRegression(max_iter=2000, C=4.0, random_state=0)
    model.fit(x, train.get_column("label").to_list())
    vorhersage = model.predict(vec.transform(zurueck.get_column("text").to_list()))
    zurueck = zurueck.with_columns(pl.Series("vorhersage", vorhersage, dtype=pl.String))
    ids = lies_ids(STICHPROBE) + lies_ids(ENTWICKLUNG)
    docs = load_documents(layout, codebuch(), set(ids), texts=ROHTEXT)
    texte = [f"{docs[i].title}\n{docs[i].text[:1500]}" for i in ids]
    rats = pl.DataFrame({"id": ids, "label": [str(v) for v in model.predict(vec.transform(texte))]})
    zurueck.select("id", "quelle", "label", "vorhersage").write_parquet(
        AUSGABE / "tfidf_cap_zurueck.parquet"
    )
    rats.write_parquet(AUSGABE / "tfidf_ratsdokumente.parquet")
    print(f"TF-IDF: {train.height} Training, {zurueck.height} zurück, {rats.height} Ratsdokumente")


# ------------------------------------------------------------------------------------------------
# Maße
# ------------------------------------------------------------------------------------------------
def makro_f1(gold: Sequence[str], vorhersage: Sequence[str]) -> float:
    labels = sorted(set(gold) | set(vorhersage))
    return classify_scores(gold, vorhersage, labels).macro_f1


def bootstrap(
    gold: Sequence[str], vorhersagen: dict[str, Sequence[str]], seed: int = SEED_TEST
) -> dict[str, list[float]]:
    """Makro-F1 je Verfahren über dieselben Ziehungen (gepaart), ohne numpy-Zufall: sha256-Folge."""
    n = len(gold)
    werte: dict[str, list[float]] = {k: [] for k in vorhersagen}
    for b in range(BOOTSTRAP):
        idx = [
            int(hashlib.sha256(f"{seed}|{b}|{j}".encode()).hexdigest()[:12], 16) % n
            for j in range(n)
        ]
        g = [gold[i] for i in idx]
        for k, v in vorhersagen.items():
            werte[k].append(makro_f1(g, [v[i] for i in idx]))
    return werte


def perzentil(werte: Sequence[float], q: float) -> float:
    s = sorted(werte)
    pos = q * (len(s) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def guete(gold: Sequence[str], vorhersage: Sequence[str]) -> str:
    if not gold:
        return "n 0"
    labels = sorted(set(gold) | set(vorhersage))
    c = classify_scores(gold, vorhersage, labels)
    kappa = cohen_kappa(list(gold), list(vorhersage))
    return (
        f"n {len(gold)}, Makro-F1 {c.macro_f1:.3f}, Genauigkeit {c.accuracy:.3f}, "
        f"κ {kappa if kappa is None else round(kappa, 3)}"
    )


# ------------------------------------------------------------------------------------------------
# Nachrechnen
# ------------------------------------------------------------------------------------------------
def lies(name: str) -> pl.DataFrame | None:
    pfad = AUSGABE / name
    return pl.read_parquet(pfad) if pfad.is_file() else None


def datenlage(layout: Layout) -> None:
    titel("Datenlage (Hauptperiode)")
    k = korpus(layout)
    print(
        f"{k.height} Dokumente, {k.filter('mit_text').height} mit Text im Korpus, "
        f"{k.filter('mit_rohtext').height} mit Rohtext, "
        f"{k.filter(pl.col('mit_text') & pl.col('mit_rohtext')).height} mit beidem"
    )
    gg = grundgesamtheit(layout)
    print(gg.group_by("schicht").len().sort("len", descending=True))


def nachrechnen(settings: Any, layout: Layout) -> None:
    datenlage(layout)
    test = lies_ids(STICHPROBE) if STICHPROBE.is_file() else []
    w2 = weg2(settings, layout)
    titel("Weg 2: Verteilung der Hauptthemen über alle Dokumente mit Text")
    for spalte in ("weg2a", "weg2b"):
        zahlen = w2.group_by(spalte).len().sort("len", descending=True).iter_rows()
        print(f"{spalte} ({w2.height} Dokumente): {list(zahlen)}")
    print(f"Ausschüsse der Kette: {w2.filter(pl.col('ausschuss') != '').height} zugeordnet")
    if not test:
        return
    wege: dict[str, dict[str, str]] = {
        "weg2a": dict(w2.select("id", "weg2a").iter_rows()),
        "weg2b": dict(w2.select("id", "weg2b").iter_rows()),
    }
    for name in sorted(p.name for p in AUSGABE.glob("weg1_test_*.parquet")):
        wege[name.removeprefix("weg1_test_").removesuffix(".parquet")] = dict(
            pl.read_parquet(AUSGABE / name).select("id", "label").iter_rows()
        )
    for name in ("weg3a_test.parquet", "weg3b_test.parquet", "tfidf_ratsdokumente.parquet"):
        f = lies(name)
        if f is not None:
            wege[name.removesuffix(".parquet")] = dict(f.select("id", "label").iter_rows())
    titel("Testmenge: Übereinstimmung der Verfahren untereinander (kein Gold, Entwurf)")
    namen = sorted(wege)
    for i, a in enumerate(namen):
        for b in namen[i + 1 :]:
            gemeinsam = [d for d in test if d in wege[a] and d in wege[b]]
            gleich = sum(wege[a][d] == wege[b][d] for d in gemeinsam)
            print(f"{a} ~ {b}: {gleich}/{len(gemeinsam)}")
    for name in namen:
        verteilung = Counter(wege[name].get(d, "fehlt") for d in test)
        print(f"{name}: {sorted(verteilung.items(), key=lambda kv: -kv[1])}")
    entwurf_einigkeit(wege, test)
    zweite_pruefung()
    laufzeiten()
    hochrechnung()
    if LABELS.is_file():
        urteil(wege, test)


def zweite_pruefung() -> None:
    titel("Zweite Prüfung an menschlich kodierten deutschen CAP-Daten")
    pruefung = lies("cap_pruefung.parquet")
    if pruefung is not None:
        gold = dict(pruefung.select("id", "label").iter_rows())
        for pfad in sorted(AUSGABE.glob("weg1_cap_*.parquet")):
            v = dict(pl.read_parquet(pfad).select("id", "label").iter_rows())
            ids = sorted(gold)
            g, p = [gold[i] for i in ids], [v.get(i, UNGUELTIG) for i in ids]
            werte = bootstrap(g, {"x": p}, SEED_CAP)["x"]
            print(
                f"{pfad.stem} gegen 200 Anfragentitel: {guete(g, p)}, "
                f"Intervall {perzentil(werte, 0.025):.3f}–{perzentil(werte, 0.975):.3f}"
            )
    for name in (
        "tfidf_cap_zurueck.parquet",
        "weg3a_cap_zurueck.parquet",
        "weg3b_cap_zurueck.parquet",
    ):
        f = lies(name)
        if f is None:
            continue
        if pruefung is not None:
            titel_ids = set(pruefung.get_column("id").to_list())
            t = f.filter(pl.col("id").is_in(sorted(titel_ids))).sort("id")
            g, p = t.get_column("label").to_list(), t.get_column("vorhersage").to_list()
            werte = bootstrap(g, {"x": p}, SEED_CAP)["x"]
            print(
                f"{name} auf denselben 200 Anfragentiteln: {guete(g, p)}, "
                f"Intervall {perzentil(werte, 0.025):.3f}–{perzentil(werte, 0.975):.3f}"
            )
        for quelle in ("anfrage", "programm"):
            teil = f.filter(pl.col("quelle") == quelle)
            print(
                f"{name} {quelle}: "
                f"{guete(teil.get_column('label').to_list(), teil.get_column('vorhersage').to_list())}"
            )


PROFILE = ("duesseldorf-2014", "duesseldorf", "duesseldorf-2025", "moenchengladbach")


def dokumente_mit_text() -> dict[str, int]:
    """Dokumente mit Text je Profil (aus dem Korpus, den `georep --profile <p> run` schreibt)."""
    zahlen = {}
    for profil in PROFILE:
        layout = Layout.from_settings(load_settings(cwd=REPO, profile=profil))
        if layout.corpus.is_file():
            zahlen[profil] = int(
                pl.read_parquet(layout.corpus, columns=["text"])
                .select((pl.col("text").fill_null("").str.strip_chars() != "").sum())
                .item()
            )
    return zahlen


def hochrechnung() -> None:
    """Sekunden je Ratsdokument aus den Läufen mit neuen Eingaben, mal Dokumente je Profil."""
    titel("Hochrechnung auf alle Perioden (GPU-Stunden, ohne Laden)")
    if not LAUFZEITEN.is_file():
        return
    je_modell: dict[str, list[tuple[int, float]]] = {}
    for zeile in LAUFZEITEN.read_text(encoding="utf-8").splitlines():
        e = json.loads(zeile)
        if e.get("teil") == "llm" and e.get("menge") != "cap" and e.get("neu"):
            je_modell.setdefault(e["modell"], []).append((e["neu"], e["sekunden_batch"]))
    zahlen = dokumente_mit_text()
    print(f"Dokumente mit Text: {zahlen}, zusammen {sum(zahlen.values())}")
    for modell, laeufe in je_modell.items():
        n, sek = sum(a for a, _ in laeufe), sum(b for _, b in laeufe)
        je = sek / n
        teile = ", ".join(f"{p} {je * k / 3600:.1f} h" for p, k in zahlen.items())
        print(
            f"{modell}: {je:.2f} s je Dokument aus {n} Dokumenten; {teile}; "
            f"alle {je * sum(zahlen.values()) / 3600:.1f} h"
        )


def laufzeiten() -> None:
    titel("Laufzeiten der Modelläufe (laufzeiten.jsonl) und Training (weg3*_lauf.json)")
    for pfad in sorted(AUSGABE.glob("weg3*_lauf.json")):
        lauf = json.loads(pfad.read_text())
        print(
            f"{pfad.name}: {lauf['training_beispiele']} Beispiele ({lauf['silber_dokumente']} "
            f"Silberdokumente), {lauf['schritte']} Schritte in {lauf['sekunden_training']} s, "
            f"{lauf['bloecke']} Block/Blöcke; Makro-F1 zurück je Epoche "
            f"{[round(e['makro_f1_zurueck'], 3) for e in lauf['epochen']]}; {lauf['zeit']}, "
            f"{lauf['uptime'][-40:]}"
        )
    if not LAUFZEITEN.is_file():
        return
    for zeile in LAUFZEITEN.read_text(encoding="utf-8").splitlines():
        e = json.loads(zeile)
        je = e["sekunden_batch"] / e["neu"] if e.get("neu") else None
        print(
            f"{e['zeit']} {e.get('teil')} {e.get('menge')} {e.get('modell')}: {e.get('neu')} neu in "
            f"{e.get('sekunden_batch')} s ({je and round(je, 2)} s je Dokument); "
            f"{e.get('uptime_vorher', '')[-40:]} -> {e.get('uptime_nachher', '')[-40:]}"
        )


def gewichte(ids: Sequence[str]) -> dict[str, float]:
    """Schichtgewicht N_h / n_h je Dokument der Testmenge (stichprobe.csv)."""
    st = pl.read_csv(STICHPROBE, infer_schema_length=0)
    n_h = Counter(st.get_column("schicht").to_list())
    w = {r["id"]: int(r["schicht_n"]) / n_h[r["schicht"]] for r in st.iter_rows(named=True)}
    return {d: w[d] for d in ids}


def einigkeit(wege: dict[str, dict[str, str]], ids: Sequence[str]) -> tuple[str, str] | None:
    """Die Wege der Einigkeitsregel (§ 8.6): Weg 1 (qwen) und Weg 3 (3b, sonst 3a)."""
    w1 = "qwen3.6-27b"
    w3 = next((k for k in ("weg3b_test", "weg3a_test") if k in wege), None)
    return (w1, w3) if w1 in wege and w3 else None


def entwurf_einigkeit(wege: dict[str, dict[str, str]], test: list[str]) -> None:
    """Vor der Kodierung schon rechenbar: die Abdeckung der Einigkeitsregel (ohne Gold)."""
    paar = einigkeit(wege, test)
    if paar is None:
        return
    a, b = paar
    w = gewichte(test)
    einig = [d for d in test if wege[a].get(d) == wege[b].get(d)]
    abdeckung = sum(w[d] for d in einig) / sum(w.values())
    print(
        f"Einigkeitsregel {a} ∩ {b}: {len(einig)}/{len(test)} Dokumente, "
        f"gewichtet {abdeckung:.3f} (Schwelle {ABDECKUNG_RUECKFALL})"
    )


def alpha(labels: pl.DataFrame) -> float | None:
    from georep.validation.measures import krippendorff_alpha

    units = [
        [r["kodierer_a"] or None, r["kodierer_b"] or None] for r in labels.iter_rows(named=True)
    ]
    return krippendorff_alpha(units, "nominal", list(CODES))


def nebenmasse(
    gold: list[str], v: list[str], ids: list[str], unsicher: dict[str, str], kopf: set[str]
) -> None:
    """Die Nebenmaße aus § 8.5 (ohne Einfluss auf das Urteil) für eine Vorhersage."""
    labels = sorted(set(gold) | set(v))
    c = classify_scores(gold, v, labels)
    gross = [k.label for k in c.classes if k.support >= 5]
    f1_gross = [k.f1 or 0.0 for k in c.classes if k.label in gross]
    gewichtet = sum((k.f1 or 0.0) * k.support for k in c.classes) / len(gold)
    print(
        f"  Makro-F1 über {len(gross)} Klassen mit ≥ 5 Gold: "
        f"{sum(f1_gross) / max(1, len(f1_gross)):.3f}; gewichtetes Makro-F1 {gewichtet:.3f}"
    )
    print(
        "  je Klasse (Gold/vorhergesagt/F1): "
        + ", ".join(
            f"{k.label} {k.support}/{k.predicted}/{(k.f1 or 0):.2f}"
            for k in sorted(c.classes, key=lambda k: -k.support)
        )
    )
    sicher = [i for i, d in enumerate(ids) if unsicher.get(d) != "ja"]
    mit_kopf = [i for i, d in enumerate(ids) if d in kopf]
    ohne_kopf = [i for i, d in enumerate(ids) if d not in kopf]
    for name, teil in (("ohne unsichere", sicher), ("Ausschuss im Kopf", mit_kopf)):
        print(f"  {name}: {guete([gold[i] for i in teil], [v[i] for i in teil])}")
    print(
        f"  ohne Ausschuss im Kopf: {guete([gold[i] for i in ohne_kopf], [v[i] for i in ohne_kopf])}"
    )
    paare = Counter((g, p) for g, p in zip(gold, v, strict=True) if g != p)
    print(f"  häufigste Verwechslungen (Gold, Vorhersage): {paare.most_common(8)}")


def kopf_mit_ausschuss(layout: Layout, ids: Sequence[str]) -> set[str]:
    """Dokumente, deren Ausschnitt mit dem Kürzel eines Ausschusses beginnt (Frage 9.2)."""
    docs = load_documents(layout, codebuch(), set(ids), texts=ROHTEXT)
    kuerzel = "|".join(re.escape(k) for k in AUSSCHUSS_CAP if k)
    muster = re.compile(rf"\s*({kuerzel})/\d")
    return {d for d in ids if muster.match(docs[d].text[:200])}


def urteil(wege: dict[str, dict[str, str]], test: list[str]) -> None:
    """Nach der Kodierung: Kriterium und Entscheidung nach § 8.5 und § 8.6 des Messdokuments."""
    titel("Urteil gegen die Labels (F4)")
    labels = pl.read_csv(LABELS, infer_schema_length=0).filter(pl.col("frage") == "politikfeld")
    a = alpha(labels)
    stufe = (
        "kein Urteil: Codebuch zu unscharf (Fassung 2)"
        if a is None or a < ALPHA_URTEIL
        else "Urteil vorläufig, Stufe 3 gesperrt"
        if a < ALPHA_STUFE3
        else "Urteil gilt"
    )
    print(f"Krippendorffs α (nominal) zwischen den Kodierern: {a}; {stufe}")
    gold_map = dict(labels.select("id", "label").iter_rows())
    ids = [d for d in test if gold_map.get(d)]
    gold = [gold_map[d] for d in ids]
    vorhersagen = {k: [v.get(d, UNGUELTIG) for d in ids] for k, v in wege.items()}
    werte = bootstrap(gold, vorhersagen)
    for k, v in vorhersagen.items():
        print(
            f"{k}: {guete(gold, v)}, Intervall "
            f"{perzentil(werte[k], 0.025):.3f}–{perzentil(werte[k], 0.975):.3f}"
        )
    # unsicher: ohne Schlichtung (adjudicate = false); unsicher, wenn einer der beiden es sagt
    unsicher = {
        r["id"]: "ja" if "ja" in (r["kodierer_a"], r["kodierer_b"]) else "nein"
        for r in pl.read_csv(LABELS, infer_schema_length=0)
        .filter(pl.col("frage") == "unsicher")
        .iter_rows(named=True)
    }
    kopf = kopf_mit_ausschuss(umgebung()[1], ids)
    print(
        f"Gold ({len(gold)}): {Counter(gold).most_common()}; unsicher bei einem der beiden: "
        f"{sum(v == 'ja' for v in unsicher.values())}; Ausschusskürzel im Kopf: {len(kopf)}"
    )
    st = pl.read_csv(STICHPROBE, infer_schema_length=0)
    schicht = dict(st.select("id", "schicht").iter_rows())
    for k, v in vorhersagen.items():
        print(f"Nebenmaße {k}:")
        nebenmasse(gold, v, ids, unsicher, kopf)
        je = Counter(schicht[d] for d in ids)
        print(
            "  Genauigkeit je Schicht: "
            + ", ".join(
                f"{s_} {sum(gold[i] == v[i] for i, d in enumerate(ids) if schicht[d] == s_)}/{n}"
                for s_, n in sorted(je.items())
            )
        )
    ref = max(("weg2a", "weg2b"), key=lambda k: makro_f1(gold, vorhersagen[k]))
    kandidaten = [k for k in ("qwen3.6-27b", "weg3b_test", "weg3a_test") if k in vorhersagen]
    if "weg3b_test" in kandidaten and "weg3a_test" in kandidaten:
        lauf = AUSGABE / "weg3b_lauf.json"
        silber = json.loads(lauf.read_text())["silber_dokumente"] if lauf.is_file() else 0
        kandidaten.remove("weg3a_test" if silber >= SILBER_MINDESTENS else "weg3b_test")
    erfuellt = []
    for k in kandidaten:
        diff = [x - y for x, y in zip(werte[k], werte[ref], strict=True)]
        punkt = makro_f1(gold, vorhersagen[k])
        ok = punkt >= KRITERIUM_F1 and perzentil(diff, 0.025) > 0
        erfuellt += [k] if ok else []
        print(
            f"{k} gegen {ref}: Differenz {punkt - makro_f1(gold, vorhersagen[ref]):+.3f} "
            f"(2,5 % {perzentil(diff, 0.025):+.3f}); Kriterium {'erfüllt' if ok else 'nicht'}"
        )
    if erfuellt:
        erfuellt.sort(key=lambda k: -makro_f1(gold, vorhersagen[k]))
        if len(erfuellt) > 1:
            diff = [x - y for x, y in zip(werte[erfuellt[0]], werte[erfuellt[1]], strict=True)]
            print(f"Vorsprung {erfuellt[0]} vor {erfuellt[1]}: 2,5 % {perzentil(diff, 0.025):+.3f}")
            if perzentil(diff, 0.025) <= 0:
                billig = [k for k in erfuellt[:2] if k.startswith("weg3")]
                erfuellt = billig + [k for k in erfuellt if k not in billig]
        print(f"Entscheidung: bauen mit {erfuellt[0]}")
        rueckfall(wege, ids, gold, vorhersagen, ref, nur_zur_information=True)
        return
    rueckfall(wege, ids, gold, vorhersagen, ref, nur_zur_information=False)


def rueckfall(
    wege: dict[str, dict[str, str]],
    ids: list[str],
    gold: list[str],
    vorhersagen: dict[str, list[str]],
    ref: str,
    *,
    nur_zur_information: bool,
) -> None:
    """Die Einigkeitsregel (§ 8.6); greift nur, wenn kein Weg das Kriterium erfüllt."""
    paar = einigkeit(wege, ids)
    if paar is None:
        if not nur_zur_information:
            print("Entscheidung: verwerfen (kein Weg erfüllt das Kriterium, keine Einigkeitsregel)")
        return
    x, y = paar
    einig = [i for i, d in enumerate(ids) if wege[x].get(d) == wege[y].get(d)]
    w = gewichte(ids)
    abdeckung = sum(w[ids[i]] for i in einig) / sum(w.values())
    g = [gold[i] for i in einig]
    v = [vorhersagen[x][i] for i in einig]
    r = [vorhersagen[ref][i] for i in einig]
    bw = bootstrap(g, {"regel": v, "ref": r})
    diff = [p - q for p, q in zip(bw["regel"], bw["ref"], strict=True)]
    ok = makro_f1(g, v) >= KRITERIUM_F1 and perzentil(diff, 0.025) > 0
    ok = ok and abdeckung >= ABDECKUNG_RUECKFALL
    vorspann = "nur zur Information, greift nicht: " if nur_zur_information else ""
    print(
        f"{vorspann}Rückfall (Einigkeit {x} ∩ {y}): {len(einig)} Dokumente, Abdeckung gewichtet "
        f"{abdeckung:.3f}, {guete(g, v)}, Intervall "
        f"{perzentil(bw['regel'], 0.025):.3f}–{perzentil(bw['regel'], 0.975):.3f}, "
        f"gegen {ref} 2,5 % {perzentil(diff, 0.025):+.3f}; Regel {'erfüllt' if ok else 'nicht'}"
    )
    if not nur_zur_information:
        print(f"Entscheidung: {'bauen mit der Einigkeitsregel' if ok else 'verwerfen'}")


def schreibe_vorhersage(weg: str) -> None:
    """Die Vorhersage eines Wegs auf der Testmenge im Format von `georep validate score --pred`."""
    quelle = {"qwen3.6-27b": "weg1_test_qwen3.6-27b.parquet"}.get(weg, f"{weg}.parquet")
    ziel = AUSGABE / f"pred_{weg}.parquet"
    pl.read_parquet(AUSGABE / quelle).select(
        "id", pl.lit("politikfeld").alias("frage"), "label"
    ).sort("id").write_parquet(ziel)
    print(f"{ziel}: `georep validate score {VORHABEN} --pred {ziel}`")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "teil",
        nargs="*",
        choices=["grundgesamtheit", "entwicklung", "silber", "eingabe", "ausschuss", "cap", "tfidf"]
        + ["llm", "prompt", "vorhersage"],
    )
    ap.add_argument(
        "--menge", choices=["test", "entwicklung", "silber", "cap"], default="entwicklung"
    )
    ap.add_argument("--modell", default=MODELL)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--weg", default="qwen3.6-27b", help="für `vorhersage`: weg3a_test, weg3b_test")
    args = ap.parse_args()
    settings, layout = umgebung()
    if not args.teil:
        nachrechnen(settings, layout)
        return
    for teil in args.teil:
        if teil == "grundgesamtheit":
            schreibe_grundgesamtheit(layout)
        elif teil == "entwicklung":
            schreibe_entwicklung(layout)
        elif teil == "silber":
            schreibe_silber(layout)
        elif teil == "eingabe":
            schreibe_eingabe(layout)
        elif teil == "ausschuss":
            w2 = weg2(settings, layout)
            AUSGABE.mkdir(parents=True, exist_ok=True)
            w2.write_parquet(AUSGABE / "weg2.parquet")
            print(f"{w2.height} Dokumente nach {AUSGABE / 'weg2.parquet'}")
        elif teil == "cap":
            schreibe_cap()
        elif teil == "tfidf":
            tfidf(layout)
        elif teil == "llm":
            weg1(settings, layout, args.menge, args.modell, args.limit)
        elif teil == "vorhersage":
            schreibe_vorhersage(args.weg)
        elif teil == "prompt":
            s = systemprompt(codebuch())
            print(
                f"{PROMPT_VERSION}: {len(s)} Zeichen, "
                f"SHA-256 {hashlib.sha256(s.encode()).hexdigest()}"
            )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
