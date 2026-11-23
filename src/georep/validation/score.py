"""Die Güte gegen die Labels (``georep validate score <vorhaben> [--pred <parquet>]``, F4).

Ohne ``--pred`` rechnet der Befehl aus ``labels.csv`` die Übereinstimmung der beiden Kodierer und
die Verteilung der Endlabels nach; bei binärer Skala dazu den Anteil des positiven Labels mit
Wilson-Intervall. Das ist die Präzision eines Verfahrens, wenn die Einheiten seine Treffer sind
(„Präzision an 100 Treffern je Art"). Mit ``--pred`` kommt die Ausgabe eines Verfahrens dazu:

- Einheiten ``document``, ``document_pair``, ``span``: ein Parquet mit ``id`` (Schlüssel der
  Einheit wie in ``labels.csv``) und ``label``; jede gelabelte Einheit braucht eine Vorhersage.
  Ergebnis: Präzision, Recall, F1 je Klasse, mikro und makro, Konfusionsmatrix.
- Einheit ``query_document``: ein Parquet mit ``query``, ``id`` (Dokument) und ``score``, die
  Rangfolge des Verfahrens je Anfrage. Ergebnis: nDCG@k je Anfrage und gemittelt; die Relevanz
  ist die Stufe der Option (die erste 0) oder, binär, 1 für das positive Label.

Alles landet in ``guete.json`` neben den Labels; ``merge`` hat dort Modell und Datum eingetragen.
Die Seite liest daraus den Satz „geprüft von zwei KI-Kodierern an n …, nicht von Menschen".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from georep.contracts import has_columns
from georep.errors import MissingInputError, SchemaError
from georep.io import digest, write_json
from georep.layout import Layout
from georep.settings import Settings
from georep.validation.codebook import Codebook, load_codebook
from georep.validation.measures import Classification, classify_scores, ndcg_at_k, wilson_interval
from georep.validation.merge import (
    LABEL_COLUMNS,
    Reliability,
    format_number,
    format_percent,
    reliability,
)
from georep.validation.paths import ValidationPaths, validation_paths
from georep.validation.sample import ID, read_sample


def read_labels(paths: ValidationPaths, codebook: Codebook) -> pl.DataFrame:
    """``labels.csv`` mit allen fünf Spalten als Text; jedes Label stammt aus dem Codebuch."""
    if not paths.labels.is_file():
        raise MissingInputError(
            f"{paths.labels} fehlt; `georep validate merge {paths.project}` legt die Labels ab"
        )
    frame = pl.read_csv(paths.labels, schema_overrides=dict.fromkeys(LABEL_COLUMNS, pl.String))
    if frame.columns != list(LABEL_COLUMNS):
        raise SchemaError(f"{paths.labels}: Spalten {list(LABEL_COLUMNS)}, nicht {frame.columns}")
    frame = frame.with_columns(pl.col("schlichtung").fill_null(""))
    known = set(codebook.labels)
    for column in ("kodierer_a", "kodierer_b", "label"):
        unknown = sorted(set(frame.get_column(column).to_list()) - known)
        if unknown:
            raise SchemaError(
                f"{paths.labels}: {column} trägt Labels außerhalb des Codebuchs: {unknown}"
            )
    return frame


def _classification_json(scores: Classification) -> dict[str, Any]:
    return {
        "n": scores.n,
        "genauigkeit": scores.accuracy,
        "genauigkeit_wilson95": list(scores.accuracy_interval),
        "mikro": {
            "praezision": scores.micro_precision,
            "recall": scores.micro_recall,
            "f1": scores.micro_f1,
        },
        "makro": {
            "praezision": scores.macro_precision,
            "recall": scores.macro_recall,
            "f1": scores.macro_f1,
        },
        "klassen": [
            {
                "label": c.label,
                "gold": c.support,
                "vorhergesagt": c.predicted,
                "richtig": c.true_positive,
                "praezision": c.precision,
                "praezision_wilson95": list(c.precision_interval) if c.precision_interval else None,
                "recall": c.recall,
                "recall_wilson95": list(c.recall_interval) if c.recall_interval else None,
                "f1": c.f1,
            }
            for c in scores.classes
        ],
        "konfusion": {
            "labels": list(scores.labels),
            "zeilen_gold": [list(r) for r in scores.confusion],
        },
    }


def classification(labels: pl.DataFrame, pred: pl.DataFrame, codebook: Codebook) -> Classification:
    """Präzision, Recall, F1 der Vorhersagen (``id``, ``label``) gegen die Endlabels."""
    if not has_columns(pred, "id", "label"):
        raise SchemaError(f"Vorhersagen brauchen die Spalten id und label, nicht {pred.columns}")
    pred = pred.select(pl.col("id").cast(pl.String), pl.col("label").cast(pl.String))
    if pred.get_column("id").n_unique() != pred.height:
        raise SchemaError("Vorhersagen: jede id höchstens einmal")
    joined = (
        labels.select("id", "label")
        .join(pred.rename({"label": "vorhersage"}), on="id", how="left")
        .sort("id")
    )
    missing = joined.filter(pl.col("vorhersage").is_null()).get_column("id")
    if missing.len():
        raise SchemaError(
            f"{missing.len()} gelabelte Einheiten ohne Vorhersage, etwa {missing[0]!r}"
        )
    unknown = sorted(set(joined.get_column("vorhersage").to_list()) - set(codebook.labels))
    if unknown:
        raise SchemaError(f"Vorhersagen außerhalb des Codebuchs: {unknown}")
    return classify_scores(
        joined.get_column("label").to_list(),
        joined.get_column("vorhersage").to_list(),
        codebook.labels,
    )


def gain(label: str, codebook: Codebook) -> float:
    """Die Relevanz eines Labels für nDCG: die Stufe der Option, binär 1 für das positive."""
    if codebook.scale == "binary":
        return 1.0 if label == codebook.score.positive else 0.0
    return float(codebook.labels.index(label))


def ranking_quality(
    labels: pl.DataFrame, sample: pl.DataFrame, pred: pl.DataFrame, codebook: Codebook
) -> dict[str, Any]:
    """nDCG@k je Anfrage der Stichprobe und gemittelt über die Anfragen mit Relevantem."""
    if codebook.scale == "nominal":
        raise SchemaError("nDCG braucht eine ordinale oder binäre Skala (Relevanzstufen)")
    if not has_columns(pred, "query", "id", "score"):
        raise SchemaError(
            f"Rangfolgen brauchen die Spalten query, id und score, nicht {pred.columns}"
        )
    judged = sample.select(ID, "anfrage", "dokument").join(labels.select(ID, "label"), on=ID)
    k = codebook.score.k
    per_query: dict[str, float | None] = {}
    for query in sorted(set(judged.get_column("anfrage").to_list())):
        rows = judged.filter(pl.col("anfrage") == query)
        gains = {
            doc: gain(label, codebook)
            for doc, label in zip(
                rows.get_column("dokument"), rows.get_column("label"), strict=True
            )
        }
        ranked = (
            pred.filter(pl.col("query").cast(pl.String) == query)
            .sort(["score", "id"], descending=[True, False])
            .get_column("id")
            .cast(pl.String)
            .to_list()
        )
        if len(set(ranked)) != len(ranked):
            raise SchemaError(f"Rangfolge zu {query!r}: ein Dokument mehrfach")
        per_query[query] = ndcg_at_k(ranked, gains, k)
    defined = [value for value in per_query.values() if value is not None]
    return {
        "k": k,
        "anfragen": len(per_query),
        "ohne_relevantes": len(per_query) - len(defined),
        "ndcg_mittel": sum(defined) / len(defined) if defined else None,
        "ndcg_je_anfrage": per_query,
    }


@dataclass(frozen=True)
class ScoreReport:
    path: Path
    reliability: Reliability
    min_alpha: float
    counts: dict[str, int]
    positive: tuple[int, int, tuple[float, float]] | None  # (positiv, n, Wilson)
    classification: Classification | None
    ranking: dict[str, Any] | None
    sentence: str

    def lines(self) -> list[str]:
        r = self.reliability
        alpha = r.alpha()
        verdict = (
            "nicht definiert"
            if alpha is None
            else ("erfüllt" if alpha >= self.min_alpha else "nicht erfüllt")
        )
        out = [
            f"Kodierer A–B: {r.n} Einheiten, einig {format_percent(r.share)}, κ {format_number(r.kappa)}, "
            f"α {format_number(alpha)} (Stufe 3 verlangt ≥ {format_number(self.min_alpha, 1)}: {verdict})",
            "Labels: " + ", ".join(f"{label} {n}" for label, n in self.counts.items()),
        ]
        if self.positive is not None:
            hits, n, (low, high) = self.positive
            out.append(
                f"positiv: {hits} von {n} ({format_percent(hits / n)}, Wilson 95 %: {format_percent(low)} bis {format_percent(high)})"
            )
        if self.classification is not None:
            c = self.classification
            out.append(
                f"Verfahren: Genauigkeit {format_percent(c.accuracy)} (Wilson 95 %: "
                f"{format_percent(c.accuracy_interval[0])} bis {format_percent(c.accuracy_interval[1])}), "
                f"Makro-F1 {format_number(c.macro_f1)}"
            )
            for score in c.classes:
                out.append(
                    f"  {score.label}: Präzision {format_number(score.precision)}, Recall {format_number(score.recall)}, "
                    f"F1 {format_number(score.f1)} (gold {score.support}, vorhergesagt {score.predicted})"
                )
        if self.ranking is not None:
            out.append(
                f"Verfahren: nDCG@{self.ranking['k']} {format_number(self.ranking['ndcg_mittel'])} über "
                f"{self.ranking['anfragen'] - self.ranking['ohne_relevantes']} Anfragen "
                f"({self.ranking['ohne_relevantes']} ohne relevantes Dokument)"
            )
        out.append(f"{self.sentence} -> {self.path}")
        return out


def score_project(
    settings: Settings, layout: Layout, project: str, *, pred: Path | None = None
) -> ScoreReport:
    """``georep validate score``: Übereinstimmung, Labels und, mit ``pred``, die Güte eines Verfahrens."""
    paths = validation_paths(settings, project)
    codebook = load_codebook(paths.codebook, project)
    labels = read_labels(paths, codebook).sort(ID)
    if not paths.quality.is_file():
        raise MissingInputError(f"{paths.quality} fehlt; `georep validate merge` legt sie an")
    quality: dict[str, Any] = json.loads(paths.quality.read_text(encoding="utf-8"))
    result = reliability(
        labels.get_column("kodierer_a").to_list(),
        labels.get_column("kodierer_b").to_list(),
        codebook,
    )
    final = labels.get_column("label").to_list()
    counts = {label: final.count(label) for label in codebook.labels}
    positive = None
    if codebook.scale == "binary":
        hits = counts[codebook.score.positive]
        positive = (hits, len(final), wilson_interval(hits, len(final)))
    scores, ranking = None, None
    if pred is not None:
        if not pred.is_file():
            raise MissingInputError(f"Vorhersagen {pred} fehlen")
        frame = pl.read_parquet(pred)
        if codebook.unit == "query_document":
            ranking = ranking_quality(labels, read_sample(paths, codebook), frame, codebook)
        else:
            scores = classification(labels, frame, codebook)
    min_alpha = settings.validation.min_alpha
    quality |= {
        "uebereinstimmung": result.as_json(),
        "alpha_mindestens": min_alpha,
        "alpha_genuegt": (result.alpha() or 0.0) >= min_alpha,
        "labels": counts,
        "positiv": None
        if positive is None
        else {
            "label": codebook.score.positive,
            "anzahl": positive[0],
            "n": positive[1],
            "anteil": positive[0] / positive[1],
            "wilson95": list(positive[2]),
        },
    }
    if pred is not None:
        quality["verfahren"] = {
            "vorhersage": pred.name,
            "vorhersage_sha256": digest(pred),
            **({"klassifikation": _classification_json(scores)} if scores is not None else {}),
            **({"rangfolge": ranking} if ranking is not None else {}),
        }
    write_json(paths.quality, quality)
    return ScoreReport(
        paths.quality,
        result,
        min_alpha,
        counts,
        positive,
        scores,
        ranking,
        str(quality.get("satz", "")),
    )
