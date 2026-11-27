"""Grundgesamtheit der Prüfung der Klasse OVA (Frage 22.3; `22-bedarf.md`, § 4.1).

    uv run python docs/plans/22-bedarf-ova.py               # nach `georep run`, Profil duesseldorf
    uv run georep validate sample 22-bedarf-ova
    uv run python docs/plans/22-bedarf-ova.py --auswertung  # nach merge und score

Die Einheiten sind die Dokumente, die H1 ungeprüft trägt: Dokumente mit Treffer in mindestens
einem Wahlbezirk (`paper_ids` in `wahlbezirke_auswertung.parquet`, wie `attention_by_district`
sie zählt), deren passender Ausschuss nach dem Ausschussklassifikator (`papers_ausschuss.parquet`,
Punkt 45) in `context.need.classes.traffic` steht (Düsseldorf: `OVA`) und die keine
Ausschussberatung haben. „Ohne Ausschussberatung" heißt wie in `analysis.committees._labelled`:
das Gremium der Drucksachennummer ist kein Ausschuss aus `[bodies.committees]`
(`papers_gremien.parquet`). Je Einheit stehen `id`, das Gremium mit seinem Namen von der Seite
(`gremium`, die Schicht und Kontext im Auftrag) und die Dokumentart (`dokumentart`, Kontext). Die
Klasse steht nicht in der Datei: sie ist die Ausgabe des geprüften Verfahrens.

Daneben schreibt das Skript die Vorhersage des Verfahrens für `georep validate score --pred`: je
Einheit `ordnung_verkehr = ja`, denn jede Einheit ist ein Treffer der Klasse. Beide Dateien liegen
unter `interim/` des Profilordners, nicht im Repo. Kein Netz, kein Modell.

Mit `--auswertung` liest es nur: die Labels (`validierung/22-bedarf-ova/labels.csv`), die
Stichprobe und `guete.json`, und druckt die Treffer je Art des Gremiums, die Zahl `unklar` und die
Folge für die Seite nach § 4.1 (Präzision mit Prüfsatz, „unscharf" oder keine Präzision).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl

from georep.analysis.topics import TopicRules
from georep.io import write_parquet
from georep.layout import Layout
from georep.prep.bodies import BODY, COMMITTEE, KIND
from georep.report.procedures import body_names
from georep.settings import load_settings

REPO = Path(__file__).resolve().parents[2]
PROJECT = "22-bedarf-ova"
FOLDER = REPO / "validierung" / PROJECT
TARGET = "interim/ova_ohne_ausschuss.parquet"  # sample.population im Codebuch
PREDICTION = "interim/ova_vorhersage.parquet"  # für georep validate score --pred
QUESTION = "ordnung_verkehr"
SCHEMA_VERSION = 1
THRESHOLD = 0.8  # § 4.1: untere Grenze des Intervalls und Schwelle von α


def main() -> None:
    settings = load_settings()
    layout = Layout.from_settings(settings)
    traffic = settings.context.need.classes.traffic
    if not traffic:
        raise SystemExit(f"Profil {layout.profile}: context.need.classes.traffic ist leer")
    committees = sorted(TopicRules.from_settings(settings).committees)
    classes = pl.read_parquet(layout.papers_committee, columns=["id", "ausschuss"])
    bodies = pl.read_parquet(layout.papers_bodies)
    results = pl.read_parquet(layout.results, columns=["paper_ids"])
    hits = sorted(set(results.explode("paper_ids").get_column("paper_ids").drop_nulls()))
    corpus = pl.read_parquet(layout.corpus, columns=["id", "paper_type"])
    names = body_names(settings, bodies)

    consulted = (pl.col(KIND) == COMMITTEE) & pl.col(BODY).is_in(committees)
    frame = (
        classes.filter(pl.col("ausschuss").is_in(traffic))
        .join(bodies.select("id", BODY, KIND), on="id", how="left")
        .with_columns(consulted.fill_null(False).alias("_beraten"))
        .sort("id")
    )
    total = frame.height
    without = frame.filter(~pl.col("_beraten"))
    hit = frame.filter(pl.col("id").is_in(hits))
    population = (
        without.filter(pl.col("id").is_in(hits))
        .join(corpus, on="id", how="left")
        .select(
            "id",
            pl.col(BODY).replace_strict(names, default=pl.col(BODY)).fill_null("").alias("gremium"),
            pl.col("paper_type").fill_null("").alias("dokumentart"),
        )
        .sort("id")
    )
    if population.get_column("id").n_unique() != population.height:
        raise SystemExit("ein Dokument zweimal in der Grundgesamtheit")
    if population.filter(pl.col("gremium") == "").height:
        raise SystemExit("ein Dokument ohne Gremium in der Grundgesamtheit")
    write_parquet(population, layout.root / TARGET, schema_version=SCHEMA_VERSION)
    prediction = population.select(
        "id", pl.lit(QUESTION).alias("frage"), pl.lit("ja").alias("label")
    )
    write_parquet(prediction, layout.root / PREDICTION, schema_version=SCHEMA_VERSION)

    print(f"Klasse {', '.join(traffic)}: {total} Dokumente mit Text")
    print(f"  davon ohne Ausschussberatung: {without.height}")
    print(f"  davon mit Treffer: {hit.height}")
    print(f"  mit Treffer und ohne Ausschussberatung (Grundgesamtheit): {population.height}")
    print(f"  Anteil am Zähler der Klasse: {population.height / hit.height:.4f}")
    for (name,), group in sorted(population.group_by("gremium"), key=lambda g: -g[1].height):
        print(f"    {name}: {group.height}")
    longest = population.select(pl.col("dokumentart").str.len_chars().max()).item()
    print(
        f"{population.height} Dokumente -> {layout.root / TARGET} (längste Dokumentart {longest})"
    )
    print(f"Vorhersage -> {layout.root / PREDICTION}")


def evaluate() -> None:
    """Treffer je Art des Gremiums und die Folge für die Seite aus Labels und ``guete.json``."""
    sample = pl.read_csv(FOLDER / "stichprobe.csv", infer_schema=False)
    labels = pl.read_csv(FOLDER / "labels.csv", infer_schema=False).filter(
        pl.col("frage") == QUESTION
    )
    quality = json.loads((FOLDER / "guete.json").read_text(encoding="utf-8"))
    frame = sample.select("id", "schicht").join(labels.select("id", "label"), on="id", how="left")
    if frame.get_column("label").null_count():
        raise SystemExit("eine Einheit der Stichprobe ohne Label")
    kind = (
        pl.when(pl.col("schicht").str.starts_with("Bezirksvertretung"))
        .then(pl.lit("Bezirksvertretungen"))
        .otherwise(pl.lit("Rat und Beiräte"))
    )
    for (name,), group in sorted(frame.with_columns(kind.alias("art")).group_by("art")):
        counted = group.filter(pl.col("label").is_in(["ja", "nein"]))
        yes = counted.filter(pl.col("label") == "ja").height
        unclear = group.filter(pl.col("label") == "unklar").height
        print(f"  {name}: ja {yes} von {counted.height}, unklar {unclear}")
    entry = quality["fragen"][QUESTION]
    found = entry["treffer"]["grundgesamtheit"]
    low, high = found["wilson95_kish"]
    print(f"α {entry['krippendorff_alpha']}, genügt {entry['alpha_genuegt']}")
    print(
        f"Präzision {found['schaetzer']:.4f} ({low:.4f} bis {high:.4f}), n_eff {found['n_eff']:.1f}"
    )
    if not entry["alpha_genuegt"]:
        print("Folge: die Seite nennt keine Präzision; die Prüfung ergab kein verlässliches Maß")
    elif low >= THRESHOLD:
        print("Folge: Präzision mit Prüfsatz, H1 wie im Bauplan")
    else:
        print(
            f"Folge: H1 als vorab festgelegtes Ergebnis, daneben „trifft nur zu {found['schaetzer']:.0%}“, unscharf"
        )


if __name__ == "__main__":
    if sys.argv[1:] == ["--auswertung"]:
        evaluate()
    elif sys.argv[1:]:
        raise SystemExit(__doc__)
    else:
        main()
