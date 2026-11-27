"""Die Unterseite ``zeit.html``: Rhythmus der Ratsarbeit, vorab festgelegte Tests, Bundespolitik (Vorhaben 17).

Stufe 3 von Vorhaben 17 (Messdokument ``docs/plans/17-zeit.md``, § 7 und § 10, Punkte 8 und 9;
``docs/plan-zeigen-2026-11.md``, § 7), im Muster von ``akteure.html`` (Punkt 88). Fünf Abschnitte,
**für alle Fraktionen und Gremien gleich gebaut**:

1. *Rhythmus der Ratsarbeit*: je Urheberklasse eine Reihe Monatsbalken über den Datensatz, die
   Haushaltsmonate markiert; die vollständigen Wahljahre mit ihrer Rolle in H17.1 und ihrem
   Haushaltsmonat; der Median je Kalendermonat. Zählungen, beschreibend.
2. *Vorab festgelegte Hypothesen*: die drei Haupttests aus ``zeit_hypothesen`` mit dem Wort des
   Ergebnisses, Holm und dem Commit der Festlegung, darunter die Sensitivitäten, die nichts
   bestätigen. Nur im Profil, das die Tests rechnet (``cycles.periods``); sonst sagt die Seite, wo
   sie stehen oder dass es keine gibt.
3. *Bundespolitisches Vokabular*: der Anteil der Dokumente je Wahljahr und Kategorie, je Kategorie
   die Prüfung aus den Labels von F4 (richtig k von n, nennt die Bundesebene m von k).
4. *Ereignisspuren* (explorativ): die Ereigniskategorien des Lexikons je Monat und die Gremien mit
   den meisten Treffern.
5. *Neuigkeiten je Wahlbezirk* (nur mit ``feeds.enabled``): die Feeds mit dem Datenstand und dem
   Satz, dass sie ohne Timer den Stand des Schnappschusses zeigen (Plan § 7).

Die Prüfung steht oben: der Satz aus ``guete.json`` (Punkt 87), die Präzision aus den Labels gegen
``analysis.lexicon.VALIDATED`` und die Festlegung der Hypothesen (``PREREGISTRATION``). Ein
Datensatz, an dem das Lexikon nicht gemessen ist, heißt beim Vokabular „explorativ"; was nicht vorab
festgelegt war, heißt es immer. Was einem Profil fehlt, sagt die Seite (Plan § 6), etwa ein
Datensatz ohne Haushaltsmonat (``docs/todo.md``, Punkt 13 (d)).

Rein bis auf ``read_inputs``, ``read_check`` und die Suche nach anderen Profilen; kein Stadtwort,
keine Partei: Namen kommen aus den Settings und den Daten.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import deal
import polars as pl

from georep.analysis.cycles import (
    PREREGISTERED,
    CycleRules,
    election_year,
    pre_election_years,
    wahljahr_of,
)
from georep.analysis.hypotheses import ALPHA, CONFIRMED
from georep.analysis.lexicon import (
    EVENT,
    MIN_PRECISION,
    STRUCTURE,
    VALIDATED,
    Lexicon,
    load_lexicon,
)
from georep.errors import MissingInputError, SchemaError
from georep.layout import Layout
from georep.prep.bodies import BodyRules
from georep.report.actors import _dataset_name, _profile_folders, body_name
from georep.report.charts import MONTHS_DE
from georep.settings import Settings, available_profiles, load_settings, profile_folder
from georep.validation.measures import wilson_interval

PAGE_NAME = "zeit"
VALIDATION_PROJECT = "17-zeit-f4"  # der Ordner unter ``validation.root`` mit ``guete.json``
MEASUREMENT = "docs/plans/17-zeit.md"  # Messdokument, relativ zum Repository
MIN_BODY_DOCUMENTS = 20  # Ereignisspuren: ein Gremium erst ab so vielen Dokumenten mit Text (§ 3.5)
# Ereignisspuren: ein Monat trägt einen Anteil erst ab so vielen Dokumenten mit Text. Darunter
# schwankt er zu stark (Mönchengladbach: 2 von 3 im November 2021 wären die Spitze), dieselbe Grenze
# wie für ein Gremium.
MIN_MONTH_DOCUMENTS = 20
TOP_BODIES = 5  # so viele Gremien je Ereignis
MIN_MEDIAN_YEARS = 2  # ein Median je Kalendermonat erst über so viele vollständige Wahljahre
UNCLEAR = "unklar"  # ein Thema, das gezählt, aber nicht gewertet wird (Messdokument § 4)
FEDERAL = "bund"  # die Ebene „nennt die Bundesebene" (Frage ``ebene`` des Codebuchs)
MONTH_SHORT = ("Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez")

# Die Urheberklassen (Option 04) als drei Reihen; zusammen genau ``URHEBER_ARTEN`` (ein Test). Die
# Fraktionen sind die zweite Reihe (``FRACTION_GROUP``): H17.1 und H17.2 zählen ihre Dokumente.
FRACTION_GROUP = 1
GROUP_SHORT = {"verwaltung": "Verwaltung", "fraktionen": "Fraktionen", "uebrige": "übrige"}
GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("verwaltung", "Verwaltung", ("Verwaltung",)),
    ("fraktionen", "Fraktionen", ("Fraktion",)),
    (
        "uebrige",
        "Übrige: einzelne Mandatsträger, Eingaben, Urheber nicht erkannt",
        ("Person", "Eingabe", "unbekannt"),
    ),
)
# Die drei vorab festgelegten Hypothesen in Worten (Messdokument § 8.1 bis § 8.3); die Kennungen
# sind die der Tabelle ``zeit_hypothesen``, ein Test hält beide gleich.
HYPOTHESES: dict[str, tuple[str, str]] = {
    "H17.1": (
        "Wahlzyklus",
        "Im letzten Wahljahr vor einer Kommunalwahl reichen die Fraktionen mehr Dokumente ein als "
        "in den mittleren Wahljahren derselben Periode.",
    ),
    "H17.2": (
        "Haushaltsrhythmus",
        "Der Monat der Haushaltsberatung ist für die Fraktionen ein Spitzenmonat: in ihm liegen mehr "
        "Fraktionsdokumente, als derselbe Kalendermonat in Wahljahren erwarten lässt, in denen der "
        "Haushalt in einem anderen Monat beraten wurde.",
    ),
    "H17.3": (
        "Bundespolitisches Vokabular",
        "Der Anteil der Dokumente mit einem Begriff aus den Strukturkategorien des Lexikons steigt "
        "von Periode zu Periode.",
    ),
}
BUDGET_SENSITIVITY = "H17.2/S2.1"  # ohne die Haushaltsanträge selbst, zweiseitig (§ 8.2)
VOCABULARY_TEST = "H17.3"  # gewertet erst mit validiertem Lexikon (§ 8.3)


# --- Die Festlegung (Messdokument § 8) -----------------------------------------------------------
@dataclass(frozen=True)
class Preregistration:
    """Wann und wo die Hypothesen festgelegt sind: der Commit allein mit § 8 und dem Lexikon."""

    commit: str
    when: dt.datetime  # Autorendatum des Commits, Ortszeit
    section: str


PREREGISTRATION = Preregistration(
    PREREGISTERED, dt.datetime(2026, 11, 23, 19, 45), "§ 8 des Messdokuments"
)


# --- Die Prüfung des Lexikons (F4, Punkt 87) -----------------------------------------------------
@dataclass(frozen=True)
class Agreement:
    """Die Übereinstimmung der Kodierer bei einer Frage, aus ``guete.json``."""

    agreed: int
    units: int
    alpha: float


@dataclass(frozen=True)
class CategoryCheck:
    """Eine Kategorie in der Stichprobe: richtig von gewertet, und wie oft die richtigen den Bund nennen."""

    right: int
    coded: int  # gewertet: ohne „unklar"
    federal: int  # unter den richtigen die mit Ebene „bund"


@dataclass(frozen=True)
class LexiconCheck:
    """Der Prüfsatz des Vokabulars: ``guete.json``, die Labels und ``VALIDATED`` für das Lexikon."""

    sentence: str  # ``satz`` aus ``guete.json``: Modelle, Einheiten, „nicht von Menschen"
    lexicon: str  # Name und Version, wie an jeder Ausgabe
    validated: bool  # die Labels gelten für diese Version (``VALIDATED`` nennt sie)
    right: int
    coded: int
    interval: tuple[float, float]  # Wilson 95 %
    topic: Agreement
    level: Agreement
    categories: Mapping[str, CategoryCheck]  # leer, wenn die Labels nicht für diese Version gelten
    same_model: bool
    measured: bool  # dieser Datensatz gehört zur Stichprobe; sonst ist das Vokabular explorativ
    measured_datasets: tuple[str, ...]  # Stadt und Periode je Profil der Stichprobe (Punkt 88, N5)

    @property
    def precision(self) -> float:
        return self.right / self.coded if self.coded else 0.0


def check_files(settings: Settings) -> tuple[Path, Path, Path, Path]:
    """``guete.json``, ``stichprobe.json``, ``stichprobe.csv`` und ``labels.csv`` der Prüfung."""
    folder = settings.validation.root / VALIDATION_PROJECT
    return (
        folder / "guete.json",
        folder / "stichprobe.json",
        folder / "stichprobe.csv",
        folder / "labels.csv",
    )


def _agreement(question: Mapping[str, Any]) -> Agreement:
    return Agreement(
        int(question["einig"]), int(question["n"]), float(question["krippendorff_alpha"])
    )


def category_checks(
    sample: Mapping[str, str], topics: Mapping[str, list[str]], levels: Mapping[str, str]
) -> dict[str, CategoryCheck]:
    """Je Kategorie der Stichprobe richtig, gewertet und Bundesebene, aus den Endlabels.

    Ein Treffer ist richtig, wenn sein Endlabel ``thema`` die Kategorie des Lexikons enthält;
    „unklar" wird gezählt, nicht gewertet (Messdokument § 4, Frage 9.13). ``federal`` zählt unter
    den richtigen die mit Endlabel ``ebene`` gleich ``bund`` (§ 4.1, „nur richtige").
    """
    found: dict[str, list[int]] = {}
    for unit, category in sample.items():
        topic = topics.get(unit, [])
        counts = found.setdefault(category, [0, 0, 0])
        if topic == [UNCLEAR]:
            continue
        counts[1] += 1
        if category in topic:
            counts[0] += 1
            counts[2] += levels.get(unit) == FEDERAL
    return {c: CategoryCheck(right, coded, federal) for c, (right, coded, federal) in found.items()}


@deal.raises(MissingInputError, SchemaError)
def read_check(settings: Settings, lexicon: Lexicon) -> LexiconCheck:
    """Der Prüfsatz aus ``guete.json`` und den Labels; ``SchemaError`` bei fehlendem Feld.

    Die Labels gelten für die Version des Lexikons, für die ``VALIDATED`` eine Zahl nennt; weichen
    die Treffer der Labels davon ab, ist das ein ``SchemaError`` (eine neue Kodierung macht die
    Konstante ungültig, wie ``RULE_CHECK`` bei ``akteure.html``). Nennt ``VALIDATED`` diese Version
    nicht, ist sie nicht geprüft: die Seite sagt das und zeigt keine Zahl je Kategorie.
    """
    quality_path, sample_json, sample_csv, labels_csv = check_files(settings)
    for path in (quality_path, sample_json, sample_csv, labels_csv):
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; die Seite {PAGE_NAME}.html nennt ihre Prüfung")
    quality: dict[str, Any] = json.loads(quality_path.read_text(encoding="utf-8"))
    drawn: dict[str, Any] = json.loads(sample_json.read_text(encoding="utf-8"))
    try:
        with sample_csv.open(encoding="utf-8", newline="") as handle:
            sample = {row["id"]: row["schicht"] for row in csv.DictReader(handle)}
        topics: dict[str, list[str]] = {}
        levels: dict[str, str] = {}
        with labels_csv.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["frage"] == "thema":
                    topics[row["id"]] = [str(t) for t in json.loads(row["label"])]
                elif row["frage"] == "ebene":
                    levels[row["id"]] = row["label"]
        sentence = str(quality["satz"])
        models = dict(quality["modelle"])
        topic = _agreement(quality["fragen"]["thema"])
        level = _agreement(quality["fragen"]["ebene"])
        profiles = tuple(p.strip() for p in str(drawn["profil"]).split(",") if p.strip())
    except (KeyError, TypeError, ValueError) as error:
        raise SchemaError(f"{quality_path.parent}: Feld fehlt ({error})") from error
    checks = category_checks(sample, topics, levels)
    right = sum(c.right for c in checks.values())
    coded = sum(c.coded for c in checks.values())
    known = VALIDATED.get((lexicon.key, lexicon.version))
    if known is not None and known != (right, coded):
        raise SchemaError(
            f"{labels_csv}: {right} von {coded} richtig, VALIDATED nennt für {lexicon.label} "
            f"{known[0]} von {known[1]}; das Lexikon ist gegen die neue Kodierung nachzurechnen"
        )
    return LexiconCheck(
        sentence=sentence,
        lexicon=lexicon.label,
        validated=known is not None,
        right=right,
        coded=coded,
        interval=wilson_interval(right, coded) if coded else (0.0, 0.0),
        topic=topic,
        level=level,
        categories=checks if known is not None else {},
        same_model=models.get("kodierer_a") == models.get("kodierer_b"),
        measured=settings.profile in _profile_folders(profiles),
        measured_datasets=tuple(_dataset_name(p) for p in profiles),
    )


# --- Abschnitt 1: Rhythmus der Ratsarbeit --------------------------------------------------------
@dataclass(frozen=True)
class MonthRow:
    """Ein Monat des Datensatzes: Dokumente je Reihe, Haushaltsanträge, ob er Haushaltsmonat ist."""

    month: dt.date
    year: int | None  # Wahljahr; leer außerhalb der vollständigen
    counts: tuple[int, ...]  # in der Folge von ``GROUPS``
    total: int
    budget_motions: int
    budget: bool  # der Haushaltsmonat seines Wahljahrs
    label: str  # das Wahljahr in Worten, „2020/21"; leer ohne


@dataclass(frozen=True)
class Bar:
    index: int  # Monat ab dem ersten des Datensatzes
    value: int
    height: float  # Anteil 0 bis 1 am höchsten Monat der Reihe


@dataclass(frozen=True)
class Panel:
    """Eine Reihe Monatsbalken; jede Reihe hat ihren eigenen Maßstab, ihr höchster Monat steht dabei."""

    key: str
    label: str
    peak: int
    peak_month: dt.date | None
    total: int
    bars: tuple[Bar, ...]  # nur Monate mit mindestens einem Dokument

    @property
    def path(self) -> str:
        """Alle Balken als ein SVG-Pfad in der Leinwand ``0 0 Monate 100``, je Monat 0,8 breit.

        Ein Pfad statt eines Rechtecks je Monat: in der Hauptperiode sind es 183 Balken, und als
        Rechtecke mit Titel trugen sie 14 KB mehr. Die Zahlen stehen in der Tabelle darunter.
        """
        return "".join(f"M{b.index}.1 100V{100 - 100 * b.height:.1f}h.8V100z" for b in self.bars)


@dataclass(frozen=True)
class YearSpan:
    """Wo ein vollständiges Wahljahr unter den Balken steht: Anfang und Breite als Anteil 0 bis 1."""

    label: str
    start: float
    width: float
    index: int  # der erste Monat des Wahljahrs unter den Balken


@dataclass(frozen=True)
class YearRow:
    """Ein vollständiges Wahljahr mit seiner Rolle in H17.1 und seinem Haushaltsmonat."""

    year: int
    label: str
    role: str  # „Anlaufjahr", „mittleres Jahr", „Vorwahljahr"
    election: dt.date | None  # beim Vorwahljahr: der Wahltag danach
    documents: int
    fraction: int
    budget_month: int | None
    budget_in_month: int | None
    budget_motions: int

    @property
    def share(self) -> float:
        return self.fraction / self.documents if self.documents else 0.0


@dataclass(frozen=True)
class PreElectionNote:
    """S1.6, beschreibend: das Vorwahljahr gegen das Mittel der mittleren Jahre derselben Periode."""

    label: str
    election: dt.date
    fraction: int
    middle_mean: float
    middle_years: int
    rank: int  # unter den Jahren ohne Anlaufjahr, nach Fraktionsdokumenten absteigend
    of: int

    @property
    def ratio(self) -> float:
        return self.fraction / self.middle_mean if self.middle_mean else 0.0


@dataclass(frozen=True)
class CalendarMonth:
    month: int
    name: str
    documents: float  # Median über die vollständigen Wahljahre
    fraction: float


@dataclass(frozen=True)
class Rhythm:
    months: tuple[MonthRow, ...]
    panels: tuple[Panel, ...]
    spans: tuple[YearSpan, ...]
    budget_indexes: tuple[int, ...]  # die Haushaltsmonate unter den Balken
    years: tuple[YearRow, ...]
    notes: tuple[PreElectionNote, ...]
    calendar: tuple[CalendarMonth, ...]  # leer unter ``MIN_MEDIAN_YEARS`` vollständigen Wahljahren
    weakest: CalendarMonth | None
    undated: int
    budget_minimum: int
    budget_total: int  # Haushaltsanträge in vollständigen Wahljahren

    @property
    def has_budget(self) -> bool:
        return any(y.budget_month is not None for y in self.years)


def year_label(year: int, start_month: int) -> str:
    """„2020/21" bei einem Wahljahr ab September, das Kalenderjahr bei einem ab Januar."""
    return f"{year}/{(year + 1) % 100:02d}" if start_month > 1 else str(year)


def _group_of(art: str | None) -> int:
    for i, (_, _, arts) in enumerate(GROUPS):
        if (art or "unbekannt") in arts:
            return i
    return len(GROUPS) - 1


def _rows_partition(
    months: pl.DataFrame, budget: pl.DataFrame, rules: CycleRules, result: Rhythm | None = None
) -> bool:
    """Die Reihen summieren je Monat zum Monat, alle Monate zu den datierten Dokumenten."""
    assert result is not None
    dated = int(months.filter(pl.col("monat").is_not_null()).get_column("dokumente").sum() or 0)
    return all(sum(m.counts) == m.total for m in result.months) and (
        sum(m.total for m in result.months) == dated
    )


@deal.ensure(_rows_partition, message="die Reihen summieren je Monat zum Monat, alle zum Korpus")
def rhythm(months: pl.DataFrame, budget: pl.DataFrame, rules: CycleRules) -> Rhythm:
    """Der Abschnitt aus ``zeit_monate`` und ``haushaltsmonate``; reine Zählungen."""
    frame = months.with_columns(pl.col("urheber_art").fill_null("unbekannt"))
    dated = frame.filter(pl.col("monat").is_not_null())
    undated = int(frame.filter(pl.col("monat").is_null()).get_column("dokumente").sum() or 0)
    budget_of = {
        int(r["wahljahr"]): r for r in budget.iter_rows(named=True) if r["wahljahr"] is not None
    }
    per_month: dict[dt.date, list[int]] = {}
    motions: dict[dt.date, int] = {}
    year_of: dict[dt.date, int | None] = {}
    for month, year, art, n, budget_n in dated.select(
        "monat", "wahljahr", "urheber_art", "dokumente", "haushaltsantraege"
    ).iter_rows():
        counts = per_month.setdefault(month, [0] * len(GROUPS))
        counts[_group_of(art)] += int(n)
        motions[month] = motions.get(month, 0) + int(budget_n)
        year_of[month] = None if year is None else int(year)
    rows = []
    for month in sorted(per_month):
        year = year_of[month]
        chosen = budget_of.get(year) if year is not None else None
        rows.append(
            MonthRow(
                month=month,
                year=year,
                counts=tuple(per_month[month]),
                total=sum(per_month[month]),
                budget_motions=motions[month],
                budget=chosen is not None
                and chosen["monat_kalender"] is not None
                and int(chosen["monat_kalender"]) == month.month,
                label="" if year is None else year_label(year, rules.start_month),
            )
        )
    panels = []
    for i, (key, label, _) in enumerate(GROUPS):
        values = [m.counts[i] for m in rows]
        peak = max(values, default=0)
        peak_month = rows[values.index(peak)].month if peak else None
        panels.append(
            Panel(
                key,
                label,
                peak,
                peak_month,
                sum(values),
                tuple(Bar(j, v, v / peak) for j, v in enumerate(values) if v and peak),
            )
        )
    count = len(rows)
    spans = []
    for year in sorted({m.year for m in rows if m.year is not None}):
        indexes = [j for j, m in enumerate(rows) if m.year == year]
        spans.append(
            YearSpan(
                year_label(year, rules.start_month),
                indexes[0] / count,
                len(indexes) / count,
                indexes[0],
            )
        )
    years = _year_rows(rows, budget_of, rules)
    calendar = _calendar(rows, rules) if len(years) >= MIN_MEDIAN_YEARS else ()
    return Rhythm(
        months=tuple(rows),
        panels=tuple(panels),
        spans=tuple(spans),
        budget_indexes=tuple(j for j, m in enumerate(rows) if m.budget),
        years=years,
        notes=_pre_election_notes(years),
        calendar=calendar,
        weakest=min(calendar, key=lambda c: (c.documents, c.month)) if calendar else None,
        undated=undated,
        budget_minimum=rules.budget_minimum,
        budget_total=sum(y.budget_motions for y in years),
    )


def _year_rows(
    rows: Sequence[MonthRow], budget_of: Mapping[int, Mapping[str, Any]], rules: CycleRules
) -> tuple[YearRow, ...]:
    complete = sorted({m.year for m in rows if m.year is not None})
    treated = pre_election_years(complete, rules)
    found = []
    for year in complete:
        within = [m for m in rows if m.year == year]
        chosen = budget_of.get(year, {})
        election = next(
            (d for d in rules.elections if election_year(d, rules.start_month) - 1 == year), None
        )
        if year == complete[0]:
            role = "Anlaufjahr"
        elif year in treated:
            role = "Vorwahljahr"
        else:
            role = "mittleres Jahr"
        month = chosen.get("monat_kalender")
        found.append(
            YearRow(
                year=year,
                label=year_label(year, rules.start_month),
                role=role,
                election=election if year in treated and year != complete[0] else None,
                documents=sum(m.total for m in within),
                fraction=sum(m.counts[FRACTION_GROUP] for m in within),
                budget_month=None if month is None else int(month),
                budget_in_month=None if chosen.get("im_monat") is None else int(chosen["im_monat"]),
                budget_motions=int(chosen.get("haushaltsantraege") or 0),
            )
        )
    return tuple(found)


def _pre_election_notes(years: Sequence[YearRow]) -> tuple[PreElectionNote, ...]:
    """S1.6 je Vorwahljahr dieses Datensatzes, wenn es mittlere Jahre gibt (beschreibend)."""
    later = [y for y in years if y.role != "Anlaufjahr"]
    middle = [y for y in later if y.role == "mittleres Jahr"]
    notes = []
    for year in later:
        if year.role != "Vorwahljahr" or year.election is None or not middle:
            continue
        ordered = sorted(later, key=lambda y: (-y.fraction, y.year))
        notes.append(
            PreElectionNote(
                label=year.label,
                election=year.election,
                fraction=year.fraction,
                middle_mean=sum(y.fraction for y in middle) / len(middle),
                middle_years=len(middle),
                rank=ordered.index(year) + 1,
                of=len(later),
            )
        )
    return tuple(notes)


def _calendar(rows: Sequence[MonthRow], rules: CycleRules) -> tuple[CalendarMonth, ...]:
    """Der Median je Kalendermonat über die vollständigen Wahljahre, in der Folge des Wahljahrs."""
    order = [(rules.start_month - 1 + i) % 12 + 1 for i in range(12)]
    found = []
    for month in order:
        within = [m for m in rows if m.year is not None and m.month.month == month]
        if not within:
            continue
        found.append(
            CalendarMonth(
                month,
                MONTH_SHORT[month - 1],
                float(statistics.median(m.total for m in within)),
                float(statistics.median(m.counts[FRACTION_GROUP] for m in within)),
            )
        )
    return tuple(found)


# --- Abschnitt 2: die vorab festgelegten Hypothesen ----------------------------------------------
@dataclass(frozen=True)
class Hypothesis:
    """Eine Hypothese der Familie, wie die Seite sie zeigt."""

    key: str
    title: str
    statement: str
    measure: str
    test: str
    effect: str  # in Worten mit Zahl, etwa „-4,9 % (90 %: -12,9 bis +3,8 %)"
    p: float
    p_holm: float
    result: str
    n: int
    fixed: str  # Commit der Festlegung
    notes: tuple[str, ...]  # je ein Satz: Randomisierung, S2.1, Gültigkeit

    @property
    def p_label(self) -> str:
        return p_text(self.p)

    @property
    def p_holm_label(self) -> str:
        return p_text(self.p_holm)


@dataclass(frozen=True)
class Sensitivity:
    """Eine Zeile außerhalb der Familie: Sensitivität oder explorativ; bestätigt nichts."""

    key: str
    parent: str
    role: str
    measure: str
    effect: str
    p: float | None
    two_sided: bool

    @property
    def p_label(self) -> str:
        return "–" if self.p is None else p_text(self.p)


@dataclass(frozen=True)
class Tests:
    main: tuple[Hypothesis, ...]
    others: tuple[Sensitivity, ...]
    periods: tuple[str, ...]  # die Perioden in zeitlicher Folge, in Worten
    data_until: dt.date | None
    lexicon: str
    alpha: float = ALPHA

    @property
    def periods_text(self) -> str:
        return listed(self.periods)


def p_text(p: float) -> str:
    """Ein p-Wert in deutscher Schreibweise: drei Stellen, darunter zwei gültige Ziffern."""
    from georep.report.model import format_de

    if p >= 0.001 or p <= 0:
        return format_de(p, 3)
    decimals = -math.floor(math.log10(p)) + 1
    return format_de(p, decimals)


def _signed(value: float, text: str) -> str:
    return f"+{text}" if value > 0 else text


def listed(names: Sequence[str]) -> str:
    """„die A, die B und die C": Perioden im Satz, je mit Artikel."""
    named = [f"die {n}" for n in names]
    return named[0] if len(named) == 1 else f"{', '.join(named[:-1])} und {named[-1]}"


def effect_text(row: Mapping[str, Any], periods: Sequence[str] = ()) -> str:
    """Der Effekt einer Zeile in Worten: relativ in Prozent, ein Anteil in Prozentpunkten."""
    from georep.report.model import format_de

    effect = row.get("effekt")
    if effect is None:
        return "–"
    unit = row.get("einheit")
    shares = row.get("anteile")
    if unit == "relativ":
        text = _signed(effect, f"{format_de(100 * effect, 1)} %")
        lo, hi = row.get("effekt_unten"), row.get("effekt_oben")
        if lo is not None and hi is not None:
            low = _signed(lo, format_de(100 * lo, 1))
            high = _signed(hi, f"{format_de(100 * hi, 1)} %")
            text += f" (90 %: {low} bis {high})"
        return text
    points = _signed(effect, f"{format_de(100 * effect, 2)} Prozentpunkte")
    if shares:
        listed = " / ".join(format_de(100 * s, 2) for s in shares)
        named = f" ({', '.join(periods)})" if len(periods) == len(shares) else ""
        return f"{listed} % je Periode{named}; Differenz der letzten zur ersten {points}"
    return points


@deal.raises(SchemaError)
def tests_model(
    table: pl.DataFrame, periods: Sequence[str], lexicon: Lexicon, check: LexiconCheck
) -> Tests:
    """Die Familie und die übrigen Zeilen aus ``zeit_hypothesen``, in der Folge der Tabelle.

    ``SchemaError``, wenn die Tabelle eine Hypothese trägt, die ``HYPOTHESES`` nicht kennt, oder
    eine Festlegung, die nicht ``PREREGISTRATION`` ist: dann stünden Worte und Datum der Seite neben
    fremden Zahlen.
    """
    rows = table.rows(named=True)
    by_key = {str(r["hypothese"]): r for r in rows if r["hypothese"] is not None}
    main: list[Hypothesis] = []
    others: list[Sensitivity] = []
    for row in rows:
        key = str(row["hypothese"])
        fixed = row["festgelegt"]
        if fixed is not None and fixed != PREREGISTRATION.commit:
            raise SchemaError(
                f"zeit_hypothesen: {key} ist in {fixed} festgelegt, die Seite kennt nur "
                f"{PREREGISTRATION.commit}"
            )
        if row["p_holm"] is None:
            others.append(
                Sensitivity(
                    key=key,
                    parent=key.split("/", 1)[0],
                    role=str(row.get("rolle") or "Sensitivität"),
                    measure=str(row.get("mass") or ""),
                    effect=effect_text(row),
                    p=row["p"],
                    two_sided="zweiseitig" in str(row.get("test") or ""),
                )
            )
            continue
        if key not in HYPOTHESES:
            raise SchemaError(
                f"zeit_hypothesen: {key} steht in der Familie, die Seite kennt es nicht"
            )
        title, statement = HYPOTHESES[key]
        main.append(
            Hypothesis(
                key=key,
                title=title,
                statement=statement,
                measure=str(row.get("mass") or ""),
                test=str(row.get("test") or ""),
                effect=effect_text(row, periods),
                p=float(row["p"]),
                p_holm=float(row["p_holm"]),
                result=str(row["ergebnis"]),
                n=int(row["n"]),
                fixed=str(fixed),
                notes=_notes(row, by_key, lexicon, check),
            )
        )
    days = [r["daten_bis"] for r in rows if r.get("daten_bis") is not None]
    return Tests(
        main=tuple(main),
        others=tuple(others),
        periods=tuple(periods),
        data_until=max(days) if days else None,
        lexicon=str(next((r["lexikon"] for r in rows if r.get("lexikon")), lexicon.label)),
    )


def _notes(
    row: Mapping[str, Any],
    by_key: Mapping[str, Mapping[str, Any]],
    lexicon: Lexicon,
    check: LexiconCheck,
) -> tuple[str, ...]:
    from georep.report.model import format_de

    key = str(row["hypothese"])
    notes = []
    count = row.get("zuordnungen")
    if row.get("p_randomisierung") is not None and count:
        notes.append(
            f"Die Randomisierung über {format_de(count)} Zuordnungen gibt p = "
            f"{p_text(float(row['p_randomisierung']))}; sie wird berichtet und entscheidet nicht."
        )
    elif count and float(row["p"]) * count < 1.5:
        notes.append(
            f"Die beobachtete Zuordnung ist die extremste von {format_de(count)}; kleiner kann p "
            "in diesem Test nicht werden."
        )
    sensitivity = by_key.get(BUDGET_SENSITIVITY) if key == "H17.2" else None
    if sensitivity is not None and sensitivity.get("effekt") is not None:
        effect = float(sensitivity["effekt"])
        direction = "unter" if effect < 0 else "über"
        text = (
            f"Ohne die Haushaltsanträge selbst liegt der Haushaltsmonat "
            f"{format_de(abs(100 * effect), 1)} % {direction} seinem Kalendermonat "
            f"(Sensitivität S2.1, zweiseitig p = {p_text(float(sensitivity['p']))})."
        )
        if row["ergebnis"] == CONFIRMED and float(sensitivity["p"]) > ALPHA:
            text += (
                " Die Spitze tragen die Haushaltsanträge selbst; andere Initiativen zieht der "
                "Haushalt nicht nachweisbar mit."
            )
        notes.append(text)
    if key == VOCABULARY_TEST:
        if check.validated and check.precision >= MIN_PRECISION:
            notes.append(
                f"Gewertet, weil das Lexikon ({lexicon.label}) die vorab verlangte Präzision von "
                f"mindestens {format_de(MIN_PRECISION, 1)} erreicht: {check.right} von "
                f"{check.coded} Treffern richtig."
            )
        else:
            notes.append(
                f"Vorläufig: das Lexikon ({lexicon.label}) hat die vorab verlangte Präzision von "
                f"mindestens {format_de(MIN_PRECISION, 1)} nicht an Labels nachgewiesen."
            )
    return tuple(notes)


@dataclass(frozen=True)
class Elsewhere:
    """Wo die Tests stehen, wenn dieses Profil sie nicht rechnet."""

    computed_here: bool  # das Profil, das sie rechnet, schreibt in diesen Ordner (anderer Lauf)
    period: str  # Periode der Seite, auf der sie stehen, in Worten; leer, wenn keine
    periods: tuple[str, ...]  # die Perioden, über die sie rechnen, in Worten

    @property
    def periods_text(self) -> str:
        return listed(self.periods)


@cache
def _computing_profiles() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Je Paketprofil mit ``cycles.periods``: sein Ordner, seine Periode, die Ordner der Perioden."""
    from georep.report.model import period_info

    found = []
    for name in available_profiles():
        try:
            settings = load_settings(profile=name, cwd=Path("/nonexistent"))
        except OSError, ValueError, SchemaError:
            continue
        if settings.cycles.periods:
            found.append(
                (settings.profile, period_info(settings).title, tuple(settings.cycles.periods))
            )
    return tuple(found)


@cache
def period_title(folder: str) -> str:
    """Die Periode eines Ordners unter ``data_root`` in Worten, aus dem ersten Paketprofil dort."""
    from georep.report.model import period_info

    for name in available_profiles():
        try:
            if profile_folder(name) != folder:
                continue
            return period_info(load_settings(profile=name, cwd=Path("/nonexistent"))).title
        except OSError, ValueError, SchemaError:
            continue
    return folder


def tests_elsewhere(settings: Settings) -> Elsewhere | None:
    """Das Paketprofil, das die Tests über die Periode dieses Datensatzes rechnet; sonst ``None``."""
    for folder, title, periods in _computing_profiles():
        if settings.profile in periods:
            return Elsewhere(
                computed_here=folder == settings.profile,
                period=title,
                periods=tuple(period_title(p) for p in periods),
            )
    return None


# --- Abschnitt 3: Bundespolitisches Vokabular ----------------------------------------------------
@dataclass(frozen=True)
class ShareCell:
    share: float
    hits: int
    width: float  # der kleine Balken: Anteil am höchsten Wert der Zeile, 0 bis 1


@dataclass(frozen=True)
class VocabularyRow:
    key: str  # Kategorie, ``struktur`` oder ``alle`` für die Summenzeilen
    label: str
    kind: str  # „Struktur", „Ereignis", leer bei einer Summenzeile
    cells: tuple[ShareCell, ...]  # je Wahljahr, in der Folge von ``Vocabulary.years``
    pooled: ShareCell
    check: CategoryCheck | None
    total: bool  # eine Summenzeile


@dataclass(frozen=True)
class Vocabulary:
    years: tuple[str, ...]
    documents: int  # Dokumente mit Text in den vollständigen Wahljahren
    per_year: tuple[int, ...]
    rows: tuple[VocabularyRow, ...]


def _flag(categories: Sequence[str]) -> pl.Expr:
    return pl.col("kategorien").list.set_intersection(pl.lit(sorted(categories))).list.len() > 0


def _cells(frame: pl.DataFrame, years: Sequence[int], flag: pl.Expr) -> tuple[list[int], int]:
    counts = frame.group_by("wahljahr").agg(flag.sum().alias("a"))
    found = {int(w): int(a) for w, a in counts.iter_rows() if w is not None}
    hits = [found.get(w, 0) for w in years]
    return hits, sum(hits)


def _sum_check(checks: Mapping[str, CategoryCheck], ids: Sequence[str]) -> CategoryCheck | None:
    chosen = [checks[c] for c in ids if c in checks]
    if not chosen:
        return None
    return CategoryCheck(
        sum(c.right for c in chosen), sum(c.coded for c in chosen), sum(c.federal for c in chosen)
    )


def vocabulary(
    documents: pl.DataFrame,
    years: Sequence[int],
    rules: CycleRules,
    lexicon: Lexicon,
    check: LexiconCheck,
) -> Vocabulary:
    """Anteil der Dokumente mit Text und Treffer je vollständigem Wahljahr und Kategorie.

    Wie H17.3 (§ 8.3): Nenner sind die Dokumente mit Text im Wahljahr, gezählt nach Vorlagendatum;
    „Periode" ist der Anteil über alle vollständigen Wahljahre zusammen, wie ``anteile`` in
    ``zeit_hypothesen``. Ohne vollständiges Wahljahr zählt der ganze Datensatz als eine Spalte.
    """
    with_text = documents.filter(pl.col("mit_text"))
    if years:
        frame = with_text.with_columns(wahljahr_of("date", rules, years).alias("wahljahr")).filter(
            pl.col("wahljahr").is_not_null()
        )
        labels = tuple(year_label(w, rules.start_month) for w in years)
        keys = list(years)
    else:
        frame = with_text.with_columns(pl.lit(0, dtype=pl.Int32).alias("wahljahr"))
        labels = ("ganzer Datensatz",)
        keys = [0]
    per_year_frame = frame.group_by("wahljahr").len()
    sizes = {int(w): int(n) for w, n in per_year_frame.iter_rows()}
    per_year = [sizes.get(w, 0) for w in keys]
    structure = lexicon.of_kind(STRUCTURE)
    kinds = {STRUCTURE: "Struktur", EVENT: "Ereignis"}
    plan: list[tuple[str, str, str, Sequence[str], bool]] = [
        ("struktur", "Strukturkategorien zusammen (das Maß von H17.3)", "", structure, True),
        *((c.id, c.name, kinds.get(c.kind, c.kind), (c.id,), False) for c in lexicon.categories),
        ("alle", "alle Kategorien, auch die Ereignisse", "", lexicon.ids, True),
    ]
    rows = []
    for key, label, kind, ids, total in plan:
        hits, all_hits = _cells(frame, keys, _flag(ids))
        shares = [a / n if n else 0.0 for a, n in zip(hits, per_year, strict=True)]
        top = max(shares, default=0.0)
        pooled = all_hits / sum(per_year) if sum(per_year) else 0.0
        rows.append(
            VocabularyRow(
                key=key,
                label=label,
                kind=kind,
                cells=tuple(
                    ShareCell(s, a, s / top if top else 0.0)
                    for s, a in zip(shares, hits, strict=True)
                ),
                pooled=ShareCell(pooled, all_hits, 0.0),
                check=_sum_check(check.categories, ids) if total else check.categories.get(key),
                total=total,
            )
        )
    return Vocabulary(labels, sum(per_year), tuple(per_year), tuple(rows))


# --- Abschnitt 4: Ereignisspuren (explorativ) ----------------------------------------------------
@dataclass(frozen=True)
class EventBody:
    name: str
    hits: int
    documents: int

    @property
    def share(self) -> float:
        return self.hits / self.documents if self.documents else 0.0


@dataclass(frozen=True)
class Event:
    key: str
    label: str
    definition: str
    hits: int
    path: str  # Treppe der Monatsanteile als SVG-Pfad in einer Leinwand ``0 0 Monate 100``
    months: int
    peak_month: dt.date | None
    peak_share: float
    peak_hits: int
    peak_documents: int
    bodies: tuple[EventBody, ...]
    thin: int  # Monate unter ``MIN_MONTH_DOCUMENTS`` Dokumenten mit Text: ohne Anteil


def _step_path(shares: Sequence[float], top: float) -> str:
    """Eine Fläche aus Stufen: je Monat eine Breite von 1, die Höhe als Anteil am Höchstwert."""
    if not shares or top <= 0:
        return ""
    parts = ["M0 100"]
    for i, share in enumerate(shares):
        y = 100 - 100 * share / top
        parts.append(f"V{y:.1f}H{i + 1}")
    parts.append("V100Z")
    return "".join(parts)


def events(
    documents: pl.DataFrame, lexicon: Lexicon, rules: BodyRules, months: Sequence[dt.date]
) -> tuple[Event, ...]:
    """Je Ereigniskategorie des Lexikons der Monatsanteil und die Gremien mit den meisten Treffern.

    Explorativ (Messdokument § 8.4): keine Tests, das Fenster ist der ganze Datensatz. Nenner sind
    die Dokumente mit Text je Monat beziehungsweise je Gremium; ein Gremium zählt erst ab
    ``MIN_BODY_DOCUMENTS`` Dokumenten mit Text, ein Monat erst ab ``MIN_MONTH_DOCUMENTS``. ``months`` sind die Monate der Balken oben (je der
    erste Tag), damit beide Reihen dieselbe Zeitachse haben.
    """
    with_text = documents.filter(pl.col("mit_text") & pl.col("date").is_not_null())
    if with_text.is_empty() or not months:
        return ()
    frame = with_text.with_columns(pl.col("date").dt.truncate("1mo").alias("monat"))
    names = {
        str(code): body_name({"gremium": code, "gremium_art": kind, "stadtbezirk": district}, rules)
        for code, kind, district in frame.select("gremium", "gremium_art", "stadtbezirk")
        .unique()
        .iter_rows()
    }
    found = []
    for category in lexicon.categories:
        if category.kind != EVENT:
            continue
        flagged = frame.with_columns(_flag([category.id]).alias("treffer"))
        per_month = flagged.group_by("monat").agg(
            pl.col("treffer").sum().alias("a"), pl.len().alias("n")
        )
        counts = {m: (int(a), int(n)) for m, a, n in per_month.iter_rows()}
        usable = {m for m, (_, n) in counts.items() if n >= MIN_MONTH_DOCUMENTS}
        shares = [counts[m][0] / counts[m][1] if m in usable else 0.0 for m in months]
        top = max(shares, default=0.0)
        peak = shares.index(top) if top else None
        per_body = (
            flagged.group_by("gremium")
            .agg(pl.col("treffer").sum().alias("a"), pl.len().alias("n"))
            .filter((pl.col("n") >= MIN_BODY_DOCUMENTS) & (pl.col("a") > 0))
        )
        bodies = sorted(
            (
                EventBody(
                    names.get(str(code), str(code or "")) or "Gremium nicht erkannt", int(a), int(n)
                )
                for code, a, n in per_body.iter_rows()
            ),
            key=lambda b: (-b.hits, -b.share, b.name),
        )[:TOP_BODIES]
        hits = int(flagged.get_column("treffer").sum())
        found.append(
            Event(
                key=category.id,
                label=category.name,
                definition=category.definition.strip(),
                hits=hits,
                path=_step_path(shares, top),
                months=len(months),
                peak_month=months[peak] if peak is not None else None,
                peak_share=top,
                peak_hits=counts[months[peak]][0] if peak is not None else 0,
                peak_documents=counts[months[peak]][1] if peak is not None else 0,
                bodies=tuple(bodies),
                thin=sum(1 for m in months if m not in usable),
            )
        )
    return tuple(found)


# --- Abschnitt 5: Neuigkeiten je Wahlbezirk ------------------------------------------------------
@dataclass(frozen=True)
class FeedRow:
    district: int
    href: str  # relativ zur Seite, ``feeds/wahlbezirk-01.xml``
    entries: int
    documents: int
    new: int  # in den 30 Tagen bis zum Stand
    updated: dt.date | None  # ``feed/updated`` als Datum seiner eigenen Zone


@dataclass(frozen=True)
class Feeds:
    rows: tuple[FeedRow, ...]
    stand: dt.date | None  # das neueste Vorlagendatum: der Stand, den die Feeds zeigen
    timer: bool  # ein Timer schreibt die Periode fort; dann entfällt der Satz zum Schnappschuss
    limit: int  # höchstens so viele Einträge je Feed
    size: int  # Bytes aller Feeds


def feeds(manifest: pl.DataFrame, stand: dt.date | None, *, timer: bool, limit: int) -> Feeds:
    """Die Liste der Feeds aus ``wahlbezirke_feeds``, nach Wahlbezirk."""
    rows = []
    for row in manifest.sort("wahlkreis_id").iter_rows(named=True):
        updated = row["aktualisiert"]
        day = dt.datetime.fromisoformat(updated).date() if updated else None
        rows.append(
            FeedRow(
                district=int(row["wahlkreis_id"]),
                href=str(row["datei"]),
                entries=int(row["eintraege"]),
                documents=int(row["dokumente"]),
                new=int(row["neu_30_tage"]),
                updated=day,
            )
        )
    return Feeds(tuple(rows), stand, timer, limit, int(manifest.get_column("bytes").sum() or 0))


# --- Die ganze Seite ------------------------------------------------------------------------------
@dataclass(frozen=True)
class TimeInputs:
    """Was die Seite liest, als Tabellen; ``read_inputs`` liest sie aus dem Layout."""

    months: pl.DataFrame  # zeit_monate
    budget: pl.DataFrame  # haushaltsmonate
    documents: (
        pl.DataFrame
    )  # id, date, mit_text, urheber_art, gremium, gremium_art, stadtbezirk, kategorien
    hypotheses: pl.DataFrame | None  # zeit_hypothesen, nur im Profil mit ``cycles.periods``
    feeds: pl.DataFrame | None  # wahlbezirke_feeds, nur mit ``feeds.enabled``


DOCUMENT_COLUMNS = (
    "id",
    "date",
    "mit_text",
    "urheber_art",
    "gremium",
    "gremium_art",
    "stadtbezirk",
    "kategorien",
)


@dataclass(frozen=True)
class TimeModel:
    """Was ``templates/pages/zeit.html.j2`` als ``data.zeit`` sieht."""

    documents: int
    first: dt.date | None
    last: dt.date | None
    check: LexiconCheck
    preregistration: Preregistration
    rhythm: Rhythm
    tests: Tests | None
    elsewhere: Elsewhere | None
    vocabulary: Vocabulary
    events: tuple[Event, ...]
    feeds: Feeds | None
    missing: tuple[str, ...]  # was diesem Profil fehlt, je ein Satz (Plan § 6)
    running: bool  # laufende Periode (``period.end`` leer)
    start_month: str  # der Monat, mit dem ein Wahljahr beginnt, in Worten

    @property
    def explorative(self) -> bool:
        return not self.check.measured


def _missing(
    rhythm_model: Rhythm, tests: Tests | None, elsewhere: Elsewhere | None, running: bool
) -> list[str]:
    from georep.report.model import format_de

    found = []
    if not rhythm_model.years:
        found.append(
            "Vollständige Wahljahre: der Datensatz deckt keines ganz ab; Wahljahre, Haushaltsmonate "
            "und die Anteile je Wahljahr fehlen."
        )
    elif not rhythm_model.has_budget:
        found.append(
            f"Haushaltsmonat: in keinem vollständigen Wahljahr stehen mindestens "
            f"{rhythm_model.budget_minimum} Haushaltsanträge (Dokumentart oder Titel), zusammen "
            f"{format_de(rhythm_model.budget_total)}; dieser Datensatz hat darum keinen "
            "Haushaltsmonat, und die Haushaltsmonate fehlen in den Balken und in der Tabelle."
        )
    if rhythm_model.years and not rhythm_model.calendar:
        found.append(
            f"Median je Kalendermonat: er braucht mindestens {MIN_MEDIAN_YEARS} vollständige "
            f"Wahljahre, dieser Datensatz hat {len(rhythm_model.years)}."
        )
    if running and not any(y.role == "Vorwahljahr" for y in rhythm_model.years):
        found.append("Vorwahljahr: die Periode läuft, ein Vorwahljahr hat sie noch nicht.")
    if tests is None and elsewhere is None:
        found.append(
            "Vorab festgelegte Tests: für diesen Datensatz ist keiner festgelegt; was hier steht, "
            "ist beschreibend oder explorativ."
        )
    return found


def build_time(
    inputs: TimeInputs, settings: Settings, lexicon: Lexicon, check: LexiconCheck
) -> TimeModel:
    """Das Modell der Seite aus den Tabellen; ``SchemaError``, wenn eine Spalte fehlt."""
    from georep.enrich.cycles import cycle_rules

    missing_columns = sorted(set(DOCUMENT_COLUMNS) - set(inputs.documents.columns))
    if missing_columns:
        raise SchemaError(f"{PAGE_NAME}.html: Spalten fehlen: {missing_columns}")
    rules = cycle_rules(settings)
    documents = inputs.documents.sort("id")
    rhythm_model = rhythm(inputs.months, inputs.budget, rules)
    years = [y.year for y in rhythm_model.years]
    tests = (
        tests_model(
            inputs.hypotheses,
            tuple(period_title(p) for p in settings.cycles.periods),
            lexicon,
            check,
        )
        if inputs.hypotheses is not None
        else None
    )
    elsewhere = tests_elsewhere(settings) if tests is None else None
    dates = documents.get_column("date").drop_nulls()
    first, last = dates.min(), dates.max()
    running = settings.period.end is None
    feeds_model = (
        feeds(
            inputs.feeds,
            last if isinstance(last, dt.date) else None,
            timer=settings.feeds.timer,
            limit=settings.feeds.entries,
        )
        if inputs.feeds is not None
        else None
    )
    return TimeModel(
        documents=documents.height,
        first=first if isinstance(first, dt.date) else None,
        last=last if isinstance(last, dt.date) else None,
        check=check,
        preregistration=PREREGISTRATION,
        rhythm=rhythm_model,
        tests=tests,
        elsewhere=elsewhere,
        vocabulary=vocabulary(documents, years, rules, lexicon, check),
        events=events(
            documents,
            lexicon,
            BodyRules.from_settings(settings.bodies),
            [m.month for m in rhythm_model.months],
        ),
        feeds=feeds_model,
        missing=tuple(_missing(rhythm_model, tests, elsewhere, running)),
        running=running,
        start_month=MONTHS_DE[rules.start_month - 1],
    )


# --- Dateien ---------------------------------------------------------------------------------------
def time_enabled(settings: Settings) -> bool:
    """Der Schalter der Seite und der Tabellen: der Schritt ``cycles`` läuft (Schalter und Urheber)."""
    return settings.cycles.enabled and bool(settings.originators.parties)


def time_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Was der Schritt ``page_zeit`` liest: die Tabellen von 17, Korpus, Urheber, Gremien, Prüfung."""
    from georep.enrich.cycles import time_files

    files = time_files(layout)
    return (
        files.months,
        files.budget,
        files.vocabulary,
        *((files.hypotheses,) if settings.cycles.periods else ()),
        *((files.feeds,) if settings.feeds.enabled else ()),
        layout.corpus,
        layout.document_originators,
        layout.papers_bodies,
        *check_files(settings),
    )


def read_inputs(layout: Layout, settings: Settings) -> TimeInputs:
    """Die Tabellen der Seite aus dem Layout; die Dokumente nach ``id`` sortiert."""
    from georep.enrich.cycles import time_files

    files = time_files(layout)
    documents = (
        pl.read_parquet(layout.corpus, columns=["id", "date", "text"])
        .select("id", "date", (pl.col("text").fill_null("") != "").alias("mit_text"))
        .join(
            pl.read_parquet(layout.document_originators, columns=["id", "urheber_art"]),
            on="id",
            how="left",
        )
        .join(
            pl.read_parquet(
                layout.papers_bodies, columns=["id", "gremium", "gremium_art", "stadtbezirk"]
            ),
            on="id",
            how="left",
        )
        .join(pl.read_parquet(files.vocabulary, columns=["id", "kategorien"]), on="id", how="left")
        .with_columns(
            pl.col("urheber_art").fill_null("unbekannt"),
            pl.col("kategorien").fill_null(pl.lit([], dtype=pl.List(pl.String()))),
        )
        .sort("id")  # ein Join legt die Zeilenfolge nicht fest (CLAUDE.md)
    )
    return TimeInputs(
        months=pl.read_parquet(files.months),
        budget=pl.read_parquet(files.budget),
        documents=documents,
        hypotheses=pl.read_parquet(files.hypotheses) if settings.cycles.periods else None,
        feeds=pl.read_parquet(files.feeds) if settings.feeds.enabled else None,
    )


def repository_links(settings: Settings) -> dict[str, str]:
    """Messdokument, README der Prüfung und Commit der Festlegung; Vorlage und Allowlist lesen dieselben."""
    from georep.report.render import REPOSITORY

    folder = settings.validation.root.name
    return {
        "measurement": f"{REPOSITORY}/blob/main/{MEASUREMENT}",
        "check": f"{REPOSITORY}/blob/main/{folder}/{VALIDATION_PROJECT}/README.md",
        "check_folder": f"{folder}/{VALIDATION_PROJECT}",
        "commit": f"{REPOSITORY}/commit/{PREREGISTRATION.commit}",
    }


def page_data(model: TimeModel, settings: Settings) -> Mapping[str, object]:
    """Was die Vorlage als ``data`` sieht: das Modell als ``zeit`` und die Links ins Repository."""
    return {
        "zeit": model,
        "groups": tuple((key, label, GROUP_SHORT[key]) for key, label, _ in GROUPS),
        "months_de": MONTHS_DE,
        "urls": repository_links(settings),
        "alpha": ALPHA,
        "min_body_documents": MIN_BODY_DOCUMENTS,
        "min_month_documents": MIN_MONTH_DOCUMENTS,
    }


def time_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    """``Page.data``: die Dateien lesen, das Modell bauen (``page_data``)."""
    lexicon = load_lexicon(settings.cycles.lexicon)
    model = build_time(
        read_inputs(layout, settings), settings, lexicon, read_check(settings, lexicon)
    )
    return page_data(model, settings)


def time_links(layout: Layout, settings: Settings) -> frozenset[str]:
    """Die Links nach außen: Messdokument, Prüfung und Commit der Festlegung im Repository."""
    links = repository_links(settings)
    return frozenset({links["measurement"], links["check"], links["commit"]})
