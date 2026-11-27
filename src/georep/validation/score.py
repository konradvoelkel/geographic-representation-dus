"""Die Güte gegen die Labels (``georep validate score <vorhaben> [--pred <parquet>]``, F4).

Ohne ``--pred`` rechnet der Befehl aus ``labels.csv`` je Frage die Übereinstimmung der beiden
Kodierer nach und die Verteilung der Endlabels. Hat eine Frage ``positive`` im Codebuch, kommt
der Anteil der Treffer dazu (unter den gewerteten Labels, ohne ``ignore``): das ist die Präzision
eines Verfahrens, wenn die Einheiten seine Treffer sind (Kantenpräzision bei Vorhaben 14).

**Gewichte** (Review 2026-11-23, Befund 1). Eine geschichtete Stichprobe ist nur dann wie eine
einfache auszuzählen, wenn sie selbstgewichtend ist (n_h/N_h überall gleich). ``score`` gibt
darum je Zahl drei Lesarten: je Schicht (x_h/m_h mit Wilson), den Anteil in der Stichprobe (x/m,
was ein Kriterium „an 150" meint; beschreibt die Stichprobe, nicht die Grundgesamtheit) und den
geschichteten Schätzer für die Grundgesamtheit Σ W_h·x_h/m_h mit W_h = N_h/N und einem
Wilson-Intervall bei Kishs effektivem n (``measures.stratified_share``). Die Schichtgrößen N_h
stehen in ``stichprobe.csv`` (``schicht_n``).

Mit ``--pred`` kommt die Ausgabe eines Verfahrens dazu:

- Einheiten außer ``query_document``: ein Parquet mit ``id``, ``frage`` (bei einem Codebuch mit
  einer Frage darf sie fehlen) und ``label``; jede gelabelte Einheit der Frage braucht eine
  Vorhersage. Ergebnis je Frage: Präzision, Recall, F1 je Klasse, mikro und makro, Konfusionsmatrix
  (die Stichprobe), dazu die Genauigkeit für die Grundgesamtheit (gewichtet).
- Einheit ``query_document``: ein Parquet mit ``query``, ``id`` (Dokument) und ``score``. Ergebnis:
  nDCG@k je Anfrage über die geurteilten Dokumente (Gleichstände gemittelt) und judged@k, der
  Anteil geurteilter Dokumente unter den ersten k des Verfahrens.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from georep.contracts import has_columns
from georep.errors import MissingInputError, SchemaError
from georep.io import digest, write_json
from georep.layout import Layout
from georep.settings import Settings
from georep.validation.codebook import OPTION_SCALES, Codebook, Question, load_codebook
from georep.validation.measures import (
    Classification,
    StratifiedShare,
    classify_scores,
    ndcg_at_k,
    stratified_share,
    weighted_accuracy,
    wilson_interval,
)
from georep.validation.merge import (
    LABEL_COLUMNS,
    Reliability,
    alpha_suffices,
    format_number,
    format_percent,
    quality_entry,
    reliability,
)
from georep.validation.paths import ValidationPaths, validation_paths
from georep.validation.sample import ID, STRATUM, STRATUM_SIZE, read_sample, sample_meta


def read_labels(paths: ValidationPaths, codebook: Codebook) -> pl.DataFrame:
    """``labels.csv`` als Text; jede Frage aus dem Codebuch, jedes Label aus ihren Optionen."""
    if not paths.labels.is_file():
        raise MissingInputError(
            f"{paths.labels} fehlt; `georep validate merge {paths.project}` legt die Labels ab"
        )
    frame = pl.read_csv(paths.labels, infer_schema=False)
    if frame.columns != list(LABEL_COLUMNS):
        raise SchemaError(f"{paths.labels}: Spalten {list(LABEL_COLUMNS)}, nicht {frame.columns}")
    frame = frame.with_columns(pl.all().fill_null(""))
    unknown = sorted(set(frame.get_column("frage")) - set(codebook.question_ids))
    if unknown:
        raise SchemaError(f"{paths.labels}: Fragen außerhalb des Codebuchs: {unknown}")
    for question in codebook.questions:
        if question.scale not in OPTION_SCALES:
            continue
        rows = frame.filter(pl.col("frage") == question.id)
        found = {
            v
            for c in ("kodierer_a", "kodierer_b", "schlichtung", "label")
            for v in rows.get_column(c)
        }
        outside = sorted(found - {"", *question.labels})
        if outside:
            raise SchemaError(
                f"{paths.labels}: {question.id} trägt Labels außerhalb des Codebuchs: {outside}"
            )
    return frame


def _none(value: str) -> str | None:
    return value or None


@dataclass(frozen=True)
class Share:
    """Der Anteil der Treffer einer Frage: je Schicht, in der Stichprobe, für die Grundgesamtheit."""

    positive: tuple[str, ...]
    hits: int
    counted: int
    ignored: int
    interval: tuple[float, float]
    strata: dict[str, tuple[int, int, int]]  # Schicht -> (Treffer, gewertet, N_h)
    population: StratifiedShare
    self_weighting: bool

    def as_json(self) -> dict[str, Any]:
        return {
            "positiv": list(self.positive),
            "stichprobe": {
                "treffer": self.hits,
                "gewertet": self.counted,
                "ignoriert": self.ignored,
                "anteil": self.hits / self.counted,
                "wilson95": list(self.interval),
            },
            "grundgesamtheit": {
                "schaetzer": self.population.estimate,
                "wilson95_kish": list(self.population.interval),
                "n_eff": self.population.effective_n,
                "n": self.population.population,
                "selbstgewichtend": self.self_weighting,
            },
            "je_schicht": {
                name: {
                    "treffer": x,
                    "gewertet": m,
                    "schicht_n": size,
                    "anteil": x / m,
                    "wilson95": list(wilson_interval(x, m)),
                }
                for name, (x, m, size) in self.strata.items()
            },
        }


def share(
    question: Question,
    labels: Mapping[str, str],
    strata: Mapping[str, str],
    sizes: Mapping[str, int],
) -> Share | None:
    """Der Anteil der Labels in ``positive`` unter den gewerteten (ohne ``ignore``)."""
    if not question.positive:
        return None
    hits: dict[str, tuple[int, int]] = {}
    ignored = 0
    for unit, label in labels.items():
        if label in question.ignore:
            ignored += 1
            continue
        x, m = hits.get(strata[unit], (0, 0))
        hits[strata[unit]] = (x + (label in question.positive), m + 1)
    if not hits:
        return None
    x = sum(h for h, _ in hits.values())
    m = sum(n for _, n in hits.values())
    drawn = {name: sum(1 for s in strata.values() if s == name) for name in hits}
    return Share(
        positive=tuple(question.positive),
        hits=x,
        counted=m,
        ignored=ignored,
        interval=wilson_interval(x, m),
        strata={name: (hx, hm, sizes[name]) for name, (hx, hm) in sorted(hits.items())},
        population=stratified_share(hits, {name: sizes[name] for name in hits}),
        self_weighting=len({drawn[name] / sizes[name] for name in hits}) == 1,
    )


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


def predictions(pred: pl.DataFrame, codebook: Codebook) -> pl.DataFrame:
    """Die Vorhersagen als ``id``, ``frage``, ``label`` (Text), jedes Paar höchstens einmal."""
    if "frage" not in pred.columns and len(codebook.questions) == 1:
        pred = pred.with_columns(pl.lit(codebook.questions[0].id).alias("frage"))
    if not has_columns(pred, "id", "frage", "label"):
        raise SchemaError(
            f"Vorhersagen brauchen die Spalten id, frage und label, nicht {pred.columns}"
        )
    pred = pred.select(*(pl.col(c).cast(pl.String) for c in ("id", "frage", "label")))
    if pred.select("id", "frage").is_duplicated().any():
        raise SchemaError("Vorhersagen: jedes Paar aus id und frage höchstens einmal")
    return pred


def classification(
    question: Question,
    labels: pl.DataFrame,
    pred: pl.DataFrame,
    strata: Mapping[str, str],
    sizes: Mapping[str, int],
) -> dict[str, Any] | None:
    """Präzision, Recall, F1 einer Frage gegen die Endlabels, dazu die gewichtete Genauigkeit."""
    gold = labels.filter((pl.col("frage") == question.id) & (pl.col("label") != "")).select(
        ID, "label"
    )
    mine = pred.filter(pl.col("frage") == question.id).select(
        ID, pl.col("label").alias("vorhersage")
    )
    if mine.is_empty():
        return None
    if question.scale not in OPTION_SCALES:
        raise SchemaError(f"Vorhersagen zu {question.id}: nur Fragen mit Optionen haben Klassen")
    joined = gold.join(mine, on=ID, how="left").sort(ID)
    missing = joined.filter(pl.col("vorhersage").is_null()).get_column(ID)
    if missing.len():
        raise SchemaError(
            f"{question.id}: {missing.len()} gelabelte Einheiten ohne Vorhersage, etwa {missing[0]!r}"
        )
    outside = sorted(set(joined.get_column("vorhersage").to_list()) - set(question.labels))
    if outside:
        raise SchemaError(f"{question.id}: Vorhersagen außerhalb des Codebuchs: {outside}")
    units = joined.get_column(ID).to_list()
    gold_labels = joined.get_column("label").to_list()
    guessed = joined.get_column("vorhersage").to_list()
    scores = classify_scores(gold_labels, guessed, question.labels)
    layers = [strata[u] for u in units]
    weighted = weighted_accuracy(gold_labels, guessed, layers, {h: sizes[h] for h in set(layers)})
    return _classification_json(scores) | {
        "genauigkeit_grundgesamtheit": {
            "schaetzer": weighted.estimate,
            "wilson95_kish": list(weighted.interval),
            "n_eff": weighted.effective_n,
        }
    }


def gain(label: str, question: Question) -> float:
    """Die Relevanz eines Labels für nDCG: die Stufe der Option, binär 1 für das positive."""
    if question.scale == "binary":
        return 1.0 if label in question.positive else 0.0
    return float(question.labels.index(label))


def relevance_question(codebook: Codebook) -> Question:
    chosen = codebook.score.relevance or next(
        (q.id for q in codebook.questions if q.scale in ("ordinal", "binary")), ""
    )
    if not chosen or codebook.question(chosen).scale not in ("ordinal", "binary"):
        raise SchemaError("nDCG braucht eine ordinale oder binäre Frage (score.relevance)")
    return codebook.question(chosen)


def ranking_quality(
    labels: pl.DataFrame, sample: pl.DataFrame, pred: pl.DataFrame, codebook: Codebook
) -> dict[str, Any]:
    """nDCG@k je Anfrage über die geurteilten Dokumente, gemittelt, dazu judged@k (Befund 4)."""
    question = relevance_question(codebook)
    if not has_columns(pred, "query", "id", "score"):
        raise SchemaError(
            f"Rangfolgen brauchen die Spalten query, id und score, nicht {pred.columns}"
        )
    pred = pred.select(
        pl.col("query").cast(pl.String),
        pl.col("id").cast(pl.String),
        pl.col("score").cast(pl.Float64),
    )
    broken = pred.filter(pl.col("score").is_null() | ~pl.col("score").is_finite())
    if broken.height:
        raise SchemaError(f"Rangfolgen: {broken.height} Punktzahlen leer oder nicht endlich")
    if pred.select("query", "id").is_duplicated().any():
        raise SchemaError("Rangfolgen: ein Dokument mehrfach in einer Anfrage")
    judged = (
        sample.select(ID, "anfrage", "dokument")
        .join(labels.filter(pl.col("frage") == question.id).select(ID, "label"), on=ID)
        .filter(pl.col("label") != "")
    )
    k = codebook.score.k
    per_query: dict[str, float | None] = {}
    judged_at_k: dict[str, float | None] = {}
    for query in sorted(set(judged.get_column("anfrage").to_list())):
        rows = judged.filter(pl.col("anfrage") == query)
        gains = {
            doc: gain(label, question)
            for doc, label in zip(
                rows.get_column("dokument"), rows.get_column("label"), strict=True
            )
        }
        ranked = pred.filter(pl.col("query") == query).sort(
            ["score", "id"], descending=[True, False], nulls_last=True
        )
        scores = dict(zip(ranked.get_column("id"), ranked.get_column("score"), strict=True))
        top = ranked.get_column("id").head(k).to_list()
        judged_at_k[query] = sum(1 for doc in top if doc in gains) / len(top) if top else None
        per_query[query] = ndcg_at_k(scores, gains, k)
    defined = [value for value in per_query.values() if value is not None]
    return {
        "frage": question.id,
        "k": k,
        "anfragen": len(per_query),
        "ohne_relevantes": len(per_query) - len(defined),
        "ndcg_mittel": sum(defined) / len(defined) if defined else None,
        "ndcg_je_anfrage": per_query,
        "judged_at_k": judged_at_k,
    }


@dataclass(frozen=True)
class ScoreReport:
    path: Path
    results: tuple[Reliability, ...]
    min_alpha: float
    counts: dict[str, dict[str, int]]
    shares: dict[str, Share]
    methods: dict[str, dict[str, Any]]
    ranking: dict[str, Any] | None
    sentence: str

    def lines(self) -> list[str]:
        out = []
        for r in self.results:
            verdict = "genügt" if alpha_suffices(r, self.min_alpha) else "genügt nicht"
            out.append(
                f"{r.question}: einig {r.agreed} von {r.both} ({format_percent(r.share)}), "
                f"κ {format_number(r.kappa)}, α {format_number(r.alpha())} (Stufe 3 verlangt ≥ "
                f"{format_number(self.min_alpha, 2)}: {verdict}); Labels "
                + ", ".join(f"{label} {n}" for label, n in self.counts[r.question].items())
            )
            found = self.shares.get(r.question)
            if found is not None:
                low, high = found.interval
                pop = found.population
                out.append(
                    f"  Treffer ({', '.join(found.positive)}): in der Stichprobe {found.hits} von "
                    f"{found.counted} = {format_number(found.hits / found.counted)} (Wilson 95 %: "
                    f"{format_number(low)} bis {format_number(high)}); für die Grundgesamtheit "
                    f"{format_number(pop.estimate)} (Wilson mit Kish-n_eff {format_number(pop.effective_n, 1)}: "
                    f"{format_number(pop.interval[0])} bis {format_number(pop.interval[1])})"
                    + ("" if found.self_weighting else ", gewichtet mit N_h/n_h")
                )
            method = self.methods.get(r.question)
            if method is not None:
                weighted = method["genauigkeit_grundgesamtheit"]
                out.append(
                    f"  Verfahren: Genauigkeit {format_percent(method['genauigkeit'])} in der "
                    f"Stichprobe, {format_percent(weighted['schaetzer'])} für die Grundgesamtheit; "
                    f"Makro-F1 {format_number(method['makro']['f1'])}"
                )
        if self.ranking is not None:
            out.append(
                f"Verfahren: nDCG@{self.ranking['k']} {format_number(self.ranking['ndcg_mittel'])} "
                f"über {self.ranking['anfragen'] - self.ranking['ohne_relevantes']} Anfragen "
                f"({self.ranking['ohne_relevantes']} ohne relevantes Dokument)"
            )
        out.append(f"{self.sentence} -> {self.path}")
        return out


def score_project(
    settings: Settings, layout: Layout, project: str, *, pred: Path | None = None
) -> ScoreReport:
    """``georep validate score``: Übereinstimmung, Treffer und, mit ``pred``, die Güte eines Verfahrens."""
    paths = validation_paths(settings, project)
    codebook = load_codebook(paths.codebook, project)
    labels = read_labels(paths, codebook)
    sample = read_sample(paths, codebook)
    if not paths.quality.is_file():
        raise MissingInputError(f"{paths.quality} fehlt; `georep validate merge` legt sie an")
    quality: dict[str, Any] = json.loads(paths.quality.read_text(encoding="utf-8"))
    strata = dict(zip(sample.get_column(ID), sample.get_column(STRATUM), strict=True))
    sizes = dict(zip(sample.get_column(STRATUM), sample.get_column(STRATUM_SIZE), strict=True))
    results, counts, shares = [], {}, {}
    for question in codebook.questions:
        rows = labels.filter(pl.col("frage") == question.id)
        results.append(
            reliability(
                question,
                [_none(v) for v in rows.get_column("kodierer_a")],
                [_none(v) for v in rows.get_column("kodierer_b")],
            )
        )
        final = {
            u: v for u, v in zip(rows.get_column(ID), rows.get_column("label"), strict=True) if v
        }
        counts[question.id] = {
            label: sum(1 for v in final.values() if v == label)
            for label in (question.labels or sorted(set(final.values())))
        }
        found = share(question, final, strata, sizes)
        if found is not None:
            shares[question.id] = found
    methods: dict[str, dict[str, Any]] = {}
    ranking = None
    if pred is not None:
        if not pred.is_file():
            raise MissingInputError(f"Vorhersagen {pred} fehlen")
        frame = pl.read_parquet(pred)
        if codebook.unit == "query_document":
            ranking = ranking_quality(labels, sample, frame, codebook)
        else:
            guessed = predictions(frame, codebook)
            for question in codebook.questions:
                result = classification(question, labels, guessed, strata, sizes)
                if result is not None:
                    methods[question.id] = result
    min_alpha = settings.validation.min_alpha
    meta = sample_meta(paths)
    for r in results:
        entry = quality.setdefault("fragen", {}).setdefault(r.question, {})
        entry.pop("alpha_vermerk", None)  # ein alter Vermerk gilt nur, wenn die Regel noch trägt
        entry |= quality_entry(r, min_alpha)
        entry["labels"] = counts[r.question]
        entry["treffer"] = shares[r.question].as_json() if r.question in shares else None
        if r.question in methods:
            entry["verfahren"] = methods[r.question]
    quality["alpha_mindestens"] = min_alpha
    quality["selbstgewichtend"] = meta.get("selbstgewichtend")
    if pred is not None:
        quality["vorhersage"] = {"datei": pred.name, "sha256": digest(pred)}
    if ranking is not None:
        quality["rangfolge"] = ranking
    write_json(paths.quality, quality)
    return ScoreReport(
        paths.quality,
        tuple(results),
        min_alpha,
        counts,
        shares,
        methods,
        ranking,
        str(quality.get("satz", "")),
    )
