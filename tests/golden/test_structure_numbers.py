"""Vorhaben 11 über die Hauptperiode, gegen die Messung und gegen die Kodierung.

Zwei Arten von Zahlen. **Die Validierung als Regressionstest**: an den Labels zweier KI-Kodierer
(``validierung/11-struktur-f4/labels.csv``, 200 Dokumente) muss ``struktur-1`` dieselben Zahlen
treffen wie der Entwurf (Messdokument ``docs/plans/11-struktur.md``, § 4.1): Beschlussvorschlag
188 von 200 zeilengenau, 190 mit einer Zeile Toleranz, Amt 125/125, Amtsbezeichnung 69/69, Zeilen
der Beratungsfolge 160/168, Briefdatum 73/73, Datum der Sitzung 48/48. Ein Umbau, der eine dieser
Zahlen senkt, ist kein Refactoring. **Die Messung**: das Regelwerk ohne Rumpf ist auf jedem
Dokument der Hauptperiode genau ``analyse`` aus dem Messskript (``struktur-entwurf-1``), und die
Zahlen aus § 3.4 und § 4.1 stehen.

Der Korpus entsteht wie in ``georep run``: ``bootstrap`` aus den Datenpaketen im Repo (darunter das
Rohtextpaket der Hauptperiode, Fundament F1), dann die Schritte ``corpus`` und ``sections``.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import polars as pl
import pytest

from georep.bootstrap import bootstrap_from_settings
from georep.enrich.sections import raw_text_frame, sections_files
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.bodies import CONSULTATION, merge_consultations
from georep.prep.raw_texts import split_lines
from georep.prep.structure import (
    StructureRules,
    analyse_draft,
    consultation_agreement,
    decision_share,
)
from georep.settings import Settings, load_settings

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[2]
VALIDATION = REPO / "validierung" / "11-struktur-f4"
NOWHERE = Path("/nonexistent")
# Gemessen am 2026-11-24 aus den Paketen der Hauptperiode (Rohtext pypdf 7.1.0, F1)
DOCUMENTS_WITH_RAW_TEXT = 19_091  # das AES-verschlüsselte 00403713.pdf hat keinen (Punkt 73)
EXPECTED_SHARE = (10_506, 10_784)  # § 3.4, wie gemessen
# § 4.1 maß 10 404 von 10 867 (95,7 %) mit den Namen des Profils allein; dazu kommen die Kürzel
# selbst, die Genitivformen und die sechs Namen aus Frage 15
OPARL = (12_763, 13_232)
SESSION_BODIES = (48, 48)  # im Entwurf wörtlich 27 von 48
SOURCES = {"ueberschrift": 9_236, "einleitung": 927, "beschlusssatz": 343}  # § 3.4, „Woher"


@dataclass(frozen=True)
class Period:
    settings: Settings
    layout: Layout
    documents: pl.DataFrame  # id, paper_type, text, extractor
    spans: pl.DataFrame
    head: pl.DataFrame


@pytest.fixture(scope="module")
def period(tmp_path_factory: pytest.TempPathFactory) -> Period:
    root = tmp_path_factory.mktemp("structure")
    settings = load_settings(profile="duesseldorf", cwd=NOWHERE).model_copy(
        update={"data_root": root / "data", "cache_root": root / "cache"}
    )
    layout = Layout.from_settings(settings)
    bootstrap_from_settings(layout, settings)
    outcomes = run_pipeline(build_steps(settings, layout), settings, ["corpus", "sections"])
    assert all(o.status == "ausgeführt" for o in outcomes), [o.line() for o in outcomes]
    corpus = pl.read_parquet(layout.corpus, columns=["id", "paper_type", "file_name"])
    documents = corpus.join(
        raw_text_frame(layout.raw_texts), left_on="file_name", right_on="name", how="left"
    ).select("id", pl.col("paper_type").fill_null(""), "text", "extractor")
    files = sections_files(layout)
    return Period(
        settings,
        layout,
        documents,
        pl.read_parquet(files.sections),
        pl.read_parquet(files.head),
    )


# --- Kodierung (§ 4.1) ------------------------------------------------------------------------------


def _labels() -> dict[str, dict[str, Any]]:
    """Endlabel je Aufgabe und Frage; Ja/Nein als bool, sonst JSON."""
    out: dict[str, dict[str, Any]] = {}
    with (VALIDATION / "labels.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = row["label"]
            # Ja/Nein als bool, Auswahl (Amtsbezeichnung, „keins") wie geschrieben, sonst JSON
            value: Any = {"ja": True, "nein": False}.get(raw, raw)
            if raw == "":
                value = None
            elif isinstance(value, str) and raw[0] in '[{"n0123456789':
                value = json.loads(raw)
            out.setdefault(row["id"], {})[row["frage"]] = value
    return out


def _tasks() -> dict[str, str]:
    """Aufgabe -> Korpus-ID (``stichprobe.csv`` der Validierung)."""
    with (VALIDATION / "stichprobe.csv").open(encoding="utf-8") as handle:
        return {row["id"]: row["dokument"] for row in csv.DictReader(handle)}


def _key(value: str) -> str:
    """Vergleich nach Leerraum- und Trennstrich-Normalisierung (Codebuch, ``[mass]``)."""
    return re.sub(r"[\s-]+", "", value)


def _dmy(day: Any) -> str:
    return day.strftime("%d.%m.%Y") if day is not None else ""


def _next_text_line(lines: list[str], number: int) -> int:
    """Zeilennummer, auf die nächste Zeile mit Text gerückt (Codebuch: leere Zeilen zählen nicht)."""
    i = number - 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i + 1


def _line_of(lines: list[tuple[int, int]], position: int) -> int:
    return next(i + 1 for i, (s, e) in enumerate(lines) if s <= position <= e)


@dataclass(frozen=True)
class Score:
    strict: int
    mild: int
    amt: tuple[int, int]
    dezernat: tuple[int, int]
    beratung: tuple[int, int]  # wörtlich, wie § 4.1
    beratung_placeholder: tuple[int, int]  # „-" als „keine"
    briefdatum: tuple[int, int]
    sitzung_datum: tuple[int, int]
    sitzung_gremium: tuple[int, int]  # Gremium im Nominativ aus [bodies] und Datum


@pytest.fixture(scope="module")
def score(period: Period) -> Score:
    labels = _labels()
    tasks = _tasks()
    texts = dict(period.documents.select("id", "text").iter_rows())
    heads = {row["id"]: row for row in period.head.iter_rows(named=True)}
    spans = period.spans.filter(
        (pl.col("kind") == "abschnitt") & (pl.col("norm") == "beschlussvorschlag")
    )
    first = {
        doc: (start, end)
        for doc, start, end in spans.group_by("id", maintain_order=True)
        .first()
        .select("id", "start", "end")
        .iter_rows()
    }
    strict = mild = 0
    counts: Counter[str] = Counter()
    for task, label in sorted(labels.items()):
        doc = tasks[task]
        text = texts[doc]
        bounds = split_lines(text)
        lines = [text[s:e] for s, e in bounds]
        found = first.get(doc)
        if (found is not None) == label["bv_vorhanden"]:
            if found is None:
                strict += 1
                mild += 1
            else:
                rule = [_next_text_line(lines, _line_of(bounds, p)) for p in found]
                gold = [
                    _next_text_line(lines, label[q]) for q in ("bv_erste_zeile", "bv_letzte_zeile")
                ]
                strict += rule == gold
                mild += all(abs(a - b) <= 1 for a, b in zip(rule, gold, strict=True))
        head = heads[doc]
        if head["amt_name"] is not None:
            counts["amt"] += 1
            written = f"{head['amt_nr'] or ''}{head['amt_name']}"
            counts["amt_ok"] += _key(written) == _key(label["amt"] or "")
        if head["dezernat_titel"] is not None:
            counts["dezernat"] += 1
            counts["dezernat_ok"] += head["dezernat_titel"] == label["dezernat_titel"]
        gold_rows = Counter(
            (_key(r["gremium"]), r["datum"], r["qualitaet"]) for r in label["beratungsfolge"]
        )
        placeholder = Counter(
            (g, d, "" if q in ("keine", "-", "-/-") else q)
            for (g, d, q), n in gold_rows.items()
            for _ in range(n)
        )
        for row in head["beratungsfolge"] or []:
            counts["beratung"] += 1
            key = (_key(row["gremium"]), _dmy(row["datum"]), row["qualitaet"] or "")
            if gold_rows[key] > 0:
                gold_rows[key] -= 1
                counts["beratung_ok"] += 1
            if placeholder[key] > 0:
                placeholder[key] -= 1
                counts["beratung_placeholder_ok"] += 1
        if head["briefdatum"] is not None:
            counts["briefdatum"] += 1
            counts["briefdatum_ok"] += _dmy(head["briefdatum"]) == (label["briefdatum"] or "")
        if head["sitzung_datum"] is not None:
            session = label["sitzung"] or {}
            counts["sitzung"] += 1
            same_day = _dmy(head["sitzung_datum"]) == session.get("datum")
            counts["sitzung_ok"] += same_day
            counts["sitzung_gremium_ok"] += same_day and head["sitzung_gremium"] == session.get(
                "gremium"
            )
    return Score(
        strict,
        mild,
        (counts["amt_ok"], counts["amt"]),
        (counts["dezernat_ok"], counts["dezernat"]),
        (counts["beratung_ok"], counts["beratung"]),
        (counts["beratung_placeholder_ok"], counts["beratung"]),
        (counts["briefdatum_ok"], counts["briefdatum"]),
        (counts["sitzung_ok"], counts["sitzung"]),
        (counts["sitzung_gremium_ok"], counts["sitzung"]),
    )


def test_the_decision_proposal_is_right_as_validated(score: Score) -> None:
    """Kriterium ≥ 0,90 der Stichprobe: 188 von 200 zeilengenau, 190 mit einer Zeile Toleranz."""
    assert (score.strict, score.mild) == (188, 190)


def test_the_head_fields_are_right_as_validated(score: Score) -> None:
    """Kriterium Präzision ≥ 0,95 je Kopffeld; die acht Zeilen der Beratungsfolge, die wörtlich
    abweichen, sind Eingaben mit dem Platzhalter „-", den die Kodierer „keine" nannten."""
    assert score.amt == (125, 125)
    assert score.dezernat == (69, 69)
    assert score.beratung == (160, 168)
    assert score.beratung_placeholder == (168, 168)
    assert score.briefdatum == (73, 73)
    assert score.sitzung_datum == (48, 48)


def test_the_session_is_named_like_the_coders_name_it(score: Score) -> None:
    """Stufe 2 normalisiert das Gremium der Sitzung über ``[bodies]`` (Nominativ, Kürzel
    ausgeschrieben); wörtlich trafen im Entwurf 27 von 48 (§ 4.1)."""
    assert score.sitzung_gremium == SESSION_BODIES


# --- Messung (§ 3.4, § 4.1) ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def measurement() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "struktur_messung", REPO / "docs" / "plans" / "11-struktur-messung.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("struktur_messung", module)
    spec.loader.exec_module(module)
    return module


def test_struktur_1_is_the_draft_on_every_document(period: Period, measurement: ModuleType) -> None:
    """Abschnitte, Kopffelder und Quellen ohne Rumpf: in keinem Dokument anders als im Messskript."""
    old_rules = measurement.Rules.load("duesseldorf")
    rules = StructureRules.from_settings(period.settings)
    different = []
    checked = 0
    for doc, paper_type, text in period.documents.select("id", "paper_type", "text").iter_rows():
        if text is None:
            continue
        checked += 1
        old = measurement.analyse(doc, text, old_rules, paper_type)
        new = analyse_draft(text, rules, paper_type)
        plain = [
            [(s.start, s.end, s.kind, s.value, s.norm, s.section) for s in spans]
            for spans in (old.sections, old.head)
        ]
        if [[tuple(s) for s in new.sections], [tuple(s) for s in new.head]] != plain or (
            new.sources != old.sources
        ):
            different.append(doc)
    assert checked == DOCUMENTS_WITH_RAW_TEXT
    assert different == []


def test_the_decision_proposal_is_found_where_the_type_expects_one(period: Period) -> None:
    """§ 3.4: 10 506 von 10 784 Dokumenten mit Text in den Arten mit erwartetem Vorschlag."""
    rules = StructureRules.from_settings(period.settings)
    assert decision_share(period.head, period.documents, rules) == EXPECTED_SHARE


def test_the_head_bodies_stand_in_the_consultations_of_the_server(period: Period) -> None:
    """§ 4.1: 95,7 % der Kopfzeilen mit Gremium aus dem Profil stehen in der OParl-Folge desselben
    Dokuments; eine untere Schranke der Präzision (OParl hält die tatsächliche Beratung)."""
    corpus = pl.read_parquet(period.layout.corpus, columns=["id", CONSULTATION])
    extra = pl.read_parquet(period.layout.consultations, columns=["id", CONSULTATION])
    found, known = consultation_agreement(
        period.head, merge_consultations(corpus, extra), period.settings.bodies.organizations
    )
    assert (found, known) == OPARL
    assert found / known >= 0.95


def test_the_decision_proposals_come_from_where_the_measurement_found_them(period: Period) -> None:
    """§ 3.4: Überschrift 87,9 %, Einleitungssatz 8,8 %, Beschlusssatz 3,3 %."""
    rules = StructureRules.from_settings(period.settings)
    expected = [
        doc
        for doc, paper_type, text in period.documents.select("id", "paper_type", "text").iter_rows()
        if text and text.strip() and rules.art(paper_type) in rules.decision_expected
    ]
    sources = (
        period.head.filter(pl.col("id").is_in(expected) & pl.col("beschlussvorschlag"))
        .get_column("beschlussvorschlag_quelle")
        .value_counts()
    )
    assert dict(sources.iter_rows()) == SOURCES
