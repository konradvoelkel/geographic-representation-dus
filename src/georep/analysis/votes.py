"""Abstimmungen je Tagesordnungspunkt: Ergebnis und Mehrheitsform, H28.2 (Vorhaben 28, Ebene A).

Wie entscheiden die Gremien? Die Sitzungsleitung trägt an jedem Tagesordnungspunkt in OParl
``result`` einen kurzen Eintrag ein („einstimmig beschlossen", „mehrheitlich abgelehnt", „vertagt"
…). Dieses Modul liest daraus nach der **Wortregel** aus § 8.1 des Messdokuments
(``docs/plans/28-abstimmungen.md``, vorab festgelegt im Commit ``97ebb52``):

* das **Ergebnis**: die erste Klasse, deren Wort im kleingeschriebenen Eintrag steht, sonst
  ``sonstiges`` (auch ohne Eintrag); eine Regel über Wörter, keine Tabelle der Werte, damit ein
  neuer Wert nicht still herausfällt;
* den Merker **geändert** („abweichend", „geändert");
* die **Mehrheitsform**, nur bei einem entschiedenen Beschluss (angenommen oder abgelehnt):
  ``einstimmig``, ``mehrheitlich`` oder ``ohne_angabe``.

Gemessen an 150 Punkten aus 50 Niederschriften: Präzision 0,982 (Wilson 0,928–0,995) bei einer
Abdeckung von 86,4 % der Beschlüsse der Hauptperiode (§ 5.1, ``LEVEL_A``). Die Positionen der
Fraktionen aus den Niederschriften (Ebene B) verfehlten das Kriterium (0,765, ``LEVEL_B``); sie
fehlen, und mit ihnen H28.1 und H28.3.

Die Wortregel ist eine **andere** als der Wortschatz von Vorhaben 26 (``[outcomes.results]``), der
die Beschlusslage je Dokument bestimmt (Messdokument § 10, Punkt 2): ``outcome_mismatches`` nennt
je Punkt, wo beide verschieden lesen, und gleicht nichts an.

**H28.2** (§ 8.6): Anträge, die nur Fraktionen der Opposition stellen (ohne die Fraktion der
WZB-Schwelle, die H28.3 prüft), nimmt der Rat in weniger als einem Viertel der Fälle an. Einheit ist
die Drucksache mit ihrem letzten entschiedenen Ratsbeschluss im Zeitraum, Test ein einseitiger
exakter Binomialtest, Holm über alle drei Hypothesen (``hypothesis_rows``).

Rein: keine Datei, kein Netz; Settings nur über ``VoteRules`` und die Argumente.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

import deal
import polars as pl
from polars._typing import PolarsDataType
from scipy import stats

from georep.analysis.hypotheses import CONFIRMED, CORE_SCHEMA, check_hypotheses, family
from georep.contracts import sorted_unique, values_known
from georep.errors import SchemaError
from georep.prep.bodies import KINDS, UNKNOWN, BodyRules, kind_of_code
from georep.settings import VOTE_DECIDED, VOTE_OTHER, VOTE_RESULTS, Votes

# Version 1: die drei Ausgaben aus § 6 und § 10 (nur Ebene A). Erhöhen, wenn sich eine Spalte ändert.
VOTES_SCHEMA_VERSION = 1

CLASSES: tuple[str, ...] = (*VOTE_RESULTS, VOTE_OTHER)
ACCEPTED, REJECTED = "angenommen", "abgelehnt"
UNANIMOUS, MAJORITY, UNSTATED = "einstimmig", "mehrheitlich", "ohne_angabe"
FORMS: tuple[str, ...] = (UNANIMOUS, MAJORITY, UNSTATED)
FROM_RESULT = "result"  # die Quelle der Form; ``niederschrift`` gäbe es erst mit Ebene B
COUNCIL, COMMITTEE = "rat", "ausschuss"
# Die Folge der Gremienarten in der Tabelle je Art: wie im Messdokument (§ 3.2)
KIND_ORDER: tuple[str, ...] = (COUNCIL, COMMITTEE, "bezirksvertretung", "beirat", UNKNOWN)
FRACTION = "Fraktion"  # die Urheberklasse aus ``analysis.parties.URHEBER_ARTEN``
# R3 (§ 8.6): Anträge, deren letztes Ergebnis keine Entscheidung ist, zählen als nicht angenommen
UNDECIDED_IN_R3: tuple[str, ...] = ("vertagt", "verwiesen", "erledigt", "zurueckgezogen")

VOTES_SCHEMA: dict[str, PolarsDataType] = {
    "top": pl.String,  # OParl AgendaItem, der Schlüssel
    "paper": pl.String,  # das Dokument (Korpus-ID)
    "sitzung": pl.Datetime("us"),  # Beginn der Sitzung, Ortszeit des Servers ohne Zone (wie 26)
    "datum": pl.Date,
    "gremium": pl.String,  # wie im Beratungsverlauf von 26: Kürzel, mehrere mit „+", sonst Schlüssel
    "gremium_art": pl.String,  # aus der ersten Organisation der Sitzung, eine aus ``KINDS``
    "nummer": pl.String,  # Nummer des Punkts auf der Tagesordnung
    "result": pl.String,  # der Eintrag der Sitzungsleitung, wörtlich; null = keiner
    "ergebnis": pl.String,  # eine aus ``CLASSES``
    "geaendert": pl.Boolean,
    "form": pl.String,  # eine aus ``FORMS``, genau bei angenommen oder abgelehnt
    "form_quelle": pl.String,  # ``result``, genau wo ``form`` steht
}
BODIES_SCHEMA: dict[str, PolarsDataType] = {
    "periode": pl.String,
    "gremium_art": pl.String,
    "punkte": pl.Int32,  # Tagesordnungspunkte mit Beratung
    "mit_eintrag": pl.Int32,  # davon mit Eintrag der Sitzungsleitung
    "beschluesse": pl.Int32,  # angenommen oder abgelehnt
    "angenommen": pl.Int32,
    "abgelehnt": pl.Int32,
    "einstimmig": pl.Int32,
    "mehrheitlich": pl.Int32,
    "ohne_angabe": pl.Int32,
    "geaendert": pl.Int32,  # angenommen mit Änderung
}
COUNTS: tuple[str, ...] = tuple(n for n in BODIES_SCHEMA if n not in ("periode", "gremium_art"))
HYPOTHESES_SCHEMA: dict[str, pl.DataType] = {
    **CORE_SCHEMA,
    "rechnung": pl.String(),  # haupttest, R1 (Ausschüsse), R2 (neue Mehrheit), R3, R4
    "partei": pl.String(),  # nur R4: die Oppositionsfraktion
    "entscheidung": pl.String(),  # bestätigt, widerlegt, nicht entscheidbar; nur beim Haupttest
    "grund": pl.String(),  # warum nicht entscheidbar (``REASONS``)
    "angenommen": pl.Int64(),
    "anteil": pl.Float64(),
    "schwelle": pl.Float64(),
    "ci_unten": pl.Float64(),  # einseitige 95-%-Grenzen nach Clopper-Pearson
    "ci_oben": pl.Float64(),
    "von": pl.Date(),  # der Zeitraum der Sitzungen
    "bis": pl.Date(),
}
HYPOTHESIS_KEY = ("hypothese", "rechnung", "partei")
MAIN, R1, R2, R3, R4 = "haupttest", "R1", "R2", "R3", "R4"
CALCULATIONS = (MAIN, R1, R2, R3, R4)
H1, H2, H3 = "H28.1", "H28.2", "H28.3"
HYPOTHESES = (H1, H2, H3)  # die Familie für Holm (m = 3), vorab festgelegt
REFUTED, UNDECIDABLE = "widerlegt", "nicht entscheidbar"
DECISIONS = (CONFIRMED, REFUTED, UNDECIDABLE)
# Warum eine Hypothese nicht entscheidbar ist (Spalte ``grund``)
LEVEL_B_REJECTED = "ebene_b_verworfen"  # H28.1 und H28.3 brauchen die Positionen der Fraktionen
LEVEL_A_MISSED = "ebene_a_verfehlt"
TOO_FEW = "zu_wenige"  # n unter ``votes.min_units``
NO_MAJORITY = "keine_mehrheit"  # das Profil kennt für den Zeitraum keine Mehrheit
NEITHER = "weder_noch"  # Holm verwirft nicht, und die untere Grenze liegt nicht über der Schwelle
REASONS = (LEVEL_B_REJECTED, LEVEL_A_MISSED, TOO_FEW, NO_MAJORITY, NEITHER)
CONFIDENCE = 0.95  # einseitig, für die Grenzen nach Clopper-Pearson (§ 8.6)


# --- Das Urteil der Messung je Ebene (§ 5.1) ------------------------------------------------------
@dataclass(frozen=True)
class LevelVerdict:
    """Präzision an 150 Punkten (gewichtet, Wilson bei Kishs n_eff) und Abdeckung der Beschlüsse."""

    precision: float
    interval: tuple[float, float]
    coverage: float
    met: bool  # Präzision ≥ 0,9 und Abdeckung ≥ 50 % (§ 8.2)


LEVEL_A = LevelVerdict(0.982, (0.928, 0.995), 0.864, True)
LEVEL_B = LevelVerdict(0.765, (0.671, 0.838), 0.701, False)


# --- Die Wortregel (§ 8.1) ------------------------------------------------------------------------
@dataclass(frozen=True)
class VoteRules:
    """Die Wortregel aus ``[votes]``, einmal gelesen; ``from_settings`` ist die einzige Brücke."""

    results: tuple[tuple[str, tuple[str, ...]], ...]
    changed: tuple[str, ...]
    unanimous: tuple[str, ...]
    majority: tuple[str, ...]

    @classmethod
    def from_settings(cls, votes: Votes) -> VoteRules:
        return cls(
            results=tuple((rule.result, tuple(rule.words)) for rule in votes.results),
            changed=tuple(votes.changed),
            unanimous=tuple(votes.unanimous),
            majority=tuple(votes.majority),
        )


@deal.post(lambda result: result in CLASSES, message="genau eine Klasse")
def result_class(result: str | None, rules: VoteRules) -> str:
    """Das Ergebnis eines Eintrags: die erste Klasse, deren Wort darin steht, sonst ``sonstiges``."""
    text = (result or "").lower()
    for klasse, words in rules.results:
        if any(word in text for word in words):
            return klasse
    return VOTE_OTHER


def is_changed(result: str | None, rules: VoteRules) -> bool:
    """Ob der Eintrag eine Änderung nennt („abweichend beschlossen")."""
    text = (result or "").lower()
    return any(word in text for word in rules.changed)


@deal.post(lambda result: result is None or result in FORMS, message="eine Form oder keine")
def form_of(result: str | None, rules: VoteRules) -> str | None:
    """Die Mehrheitsform eines entschiedenen Beschlusses; ohne Entscheidung keine."""
    if result_class(result, rules) not in VOTE_DECIDED:
        return None
    text = (result or "").lower()
    if any(word in text for word in rules.unanimous):
        return UNANIMOUS
    if any(word in text for word in rules.majority):
        return MAJORITY
    return UNSTATED


# --- Die Tabelle je Tagesordnungspunkt ------------------------------------------------------------
def _votes_fit(result: pl.DataFrame) -> bool:
    decided = result.get_column("ergebnis").is_in(list(VOTE_DECIDED))
    with_form = result.get_column("form").is_not_null()
    return (
        result.schema == pl.Schema(VOTES_SCHEMA)
        and sorted_unique(result, "top")
        and values_known(result, "ergebnis", CLASSES)
        and values_known(result, "form", FORMS)
        and values_known(result, "gremium_art", KINDS)
        and bool((decided == with_form).all())
        and bool((with_form == result.get_column("form_quelle").is_not_null()).all())
    )


PROGRESS_COLUMNS = ("id", "top", "gremium", "sitzung", "nummer", "result")


@deal.pre(
    lambda progress, bodies, rules: all(c in progress.columns for c in PROGRESS_COLUMNS),
    message="der Beratungsverlauf von 26 mit id, top, gremium, sitzung, nummer, result",
)
@deal.post(
    _votes_fit,
    message="eine Zeile je top, sortiert; Form genau bei angenommen oder abgelehnt, mit Quelle",
)
@deal.raises(SchemaError)
def votes_table(progress: pl.DataFrame, bodies: BodyRules, rules: VoteRules) -> pl.DataFrame:
    """Je Tagesordnungspunkt mit Beratung eine Zeile, aus dem Beratungsverlauf von Vorhaben 26.

    Eine Zeile des Verlaufs ohne ``top`` ist eine Beratung, deren Punkt nicht in der Sitzungsliste
    der Periode steht; sie ist keine Einheit (§ 8.1). Steht dieselbe Drucksache zweimal in einer
    Sitzung, sind es zwei Punkte und zwei Zeilen. ``SchemaError``, wenn ein Punkt mehr als einmal
    vorkommt: dann nennten zwei Beratungen denselben Punkt, und die Einheit wäre nicht eindeutig.
    Die Gremienart folgt aus dem Kürzel der ersten Organisation der Sitzung (wie im Messskript),
    das Gremium ist das von 26. Die Regel läuft je Wert einmal, nicht je Zeile.
    """
    items = progress.filter(pl.col("top").is_not_null())
    twice = items.filter(pl.col("top").is_duplicated()).get_column("top").unique().sort()
    if twice.len():
        raise SchemaError(
            f"Beratungsverlauf: {twice.len()} Tagesordnungspunkte stehen mehrfach, etwa "
            f"{twice[0]}; die Einheit von Vorhaben 28 ist der Punkt"
        )
    values = items.get_column("result").drop_nulls().unique().to_list()
    klasse = {value: result_class(value, rules) for value in values}
    form = {value: form_of(value, rules) for value in values}
    changed = {value: is_changed(value, rules) for value in values}
    kinds = {
        body: kind_of_code(body.split("+")[0], bodies)
        for body in items.get_column("gremium").drop_nulls().unique().to_list()
    }
    return (
        items.select(
            "top",
            pl.col("id").alias("paper"),
            "sitzung",
            pl.col("sitzung").dt.date().alias("datum"),
            "gremium",
            pl.col("gremium")
            .replace_strict(kinds, default=UNKNOWN, return_dtype=pl.String)
            .alias("gremium_art"),
            "nummer",
            "result",
            pl.col("result")
            .replace_strict(klasse, default=VOTE_OTHER, return_dtype=pl.String)
            .alias("ergebnis"),
            pl.col("result")
            .replace_strict(changed, default=False, return_dtype=pl.Boolean)
            .alias("geaendert"),
            pl.col("result")
            .replace_strict(form, default=None, return_dtype=pl.String)
            .alias("form"),
        )
        .with_columns(
            pl.when(pl.col("form").is_not_null())
            .then(pl.lit(FROM_RESULT))
            .otherwise(pl.lit(None, dtype=pl.String))
            .alias("form_quelle")
        )
        .select(list(VOTES_SCHEMA))
        .sort("top")
    )


# --- Je Gremienart (Abschnitt auf akteure.html, § 7 Punkt 1) --------------------------------------
def _bodies_fit(votes: pl.DataFrame, period: str, result: pl.DataFrame) -> bool:
    totals = result.select(pl.col(c).sum() for c in ("punkte", "beschluesse")).row(0)
    decided = votes.filter(pl.col("ergebnis").is_in(list(VOTE_DECIDED))).height
    parts = (
        result.get_column("angenommen") + result.get_column("abgelehnt")
        == result.get_column("beschluesse")
    ) & (
        result.get_column("einstimmig")
        + result.get_column("mehrheitlich")
        + result.get_column("ohne_angabe")
        == result.get_column("beschluesse")
    )
    return (
        result.schema == pl.Schema(BODIES_SCHEMA)
        and totals == (votes.height, decided)
        and bool(parts.all())
        and values_known(result, "gremium_art", KINDS)
    )


@deal.pre(lambda votes, period: votes.schema == pl.Schema(VOTES_SCHEMA))
@deal.ensure(
    _bodies_fit,
    message="je Gremienart eine Zeile; die Teile summieren zu den Beschlüssen, alle Punkte gezählt",
)
def body_summary(votes: pl.DataFrame, period: str) -> pl.DataFrame:
    """Je Gremienart, die vorkommt: Punkte, Beschlüsse, angenommen, abgelehnt, Formen, geändert.

    ``period`` ist der Schlüssel der Periode wie in ``antragserfolg`` von 26 („2020-2025"). Gezählt
    werden die Punkte zu den Dokumenten dieses Profils, auch Sitzungen nach dem Ende der Periode
    (ein Antrag von 2024 wird 2026 entschieden); Sitzungen, die noch ausstehen, tragen keinen
    Eintrag und zählen nur unter ``punkte``. Explorativ (§ 8.6), keine Zeile für alle Arten.
    """
    decided = pl.col("ergebnis").is_in(list(VOTE_DECIDED))
    counts = votes.group_by("gremium_art").agg(
        pl.len().alias("punkte"),
        pl.col("result").is_not_null().sum().alias("mit_eintrag"),
        decided.sum().alias("beschluesse"),
        (pl.col("ergebnis") == ACCEPTED).sum().alias("angenommen"),
        (pl.col("ergebnis") == REJECTED).sum().alias("abgelehnt"),
        (pl.col("form") == UNANIMOUS).sum().alias("einstimmig"),
        (pl.col("form") == MAJORITY).sum().alias("mehrheitlich"),
        (pl.col("form") == UNSTATED).sum().alias("ohne_angabe"),
        ((pl.col("ergebnis") == ACCEPTED) & pl.col("geaendert")).sum().alias("geaendert"),
    )
    order = {kind: rank for rank, kind in enumerate(KIND_ORDER)}
    return (
        counts.with_columns(
            pl.lit(period, dtype=pl.String).alias("periode"),
            *(pl.col(c).cast(pl.Int32) for c in COUNTS),
            pl.col("gremium_art")
            .replace_strict(order, default=len(order), return_dtype=pl.Int32)
            .alias("__rang"),
        )
        .sort("__rang")
        .select(list(BODIES_SCHEMA))
    )


# --- Die Wortregel neben dem Wortschatz von 26 (§ 10, Punkt 2) ------------------------------------
# Was 28 und 26 einander entsprechen lassen: angenommen ⇔ beschlossen oder geändert, abgelehnt ⇔
# abgelehnt, zurückgezogen ⇔ zurückgezogen; die übrigen Klassen beider Regeln vergleicht niemand.
CORRESPONDING: dict[str, tuple[str, ...]] = {
    ACCEPTED: ("beschlossen", "geaendert"),
    REJECTED: ("abgelehnt",),
    "zurueckgezogen": ("zurueckgezogen",),
}


def agrees_with_outcomes(word_class: str, outcome_class: str) -> bool:
    """Ob die Klasse der Wortregel und die von 26 an einem Eintrag dasselbe sagen."""
    return all(
        (word_class == mine) == (outcome_class in theirs) for mine, theirs in CORRESPONDING.items()
    )


def outcome_mismatches(votes: pl.DataFrame, results: Mapping[str, tuple[str, str]]) -> pl.DataFrame:
    """Die Punkte, an denen die Wortregel und ``[outcomes.results]`` (26) verschieden lesen.

    Je Punkt mit Eintrag ``top``, ``result``, die Klasse von 28 und die von 26; ein Eintrag, den 26
    nicht kennt, hätte 26 schon abgebrochen (``UnknownResultError``) und zählt hier nicht.
    """
    other = {value: klasse for value, (_, klasse) in results.items()}
    entered = votes.filter(pl.col("result").is_in(list(other)))
    keep = [
        not agrees_with_outcomes(word, other[value])
        for value, word in entered.select("result", "ergebnis").iter_rows()
    ]
    return (
        entered.filter(pl.Series(keep, dtype=pl.Boolean))
        .select(
            "top",
            "result",
            pl.col("ergebnis").alias("klasse_28"),
            pl.col("result").replace_strict(other, return_dtype=pl.String).alias("klasse_26"),
        )
        .sort("top")
    )


# --- H28.2: Anträge der Opposition (§ 8.6) --------------------------------------------------------
@dataclass(frozen=True)
class Opposition:
    """Wer zur Opposition zählt und welche Anträge H28.2 liest; aus Settings und Mehrheit."""

    majority: frozenset[str]  # Parteischlüssel der Mehrheit im Zeitraum
    excluded: frozenset[str]  # Anträge mit diesen Parteien prüft H28.3
    motion_type: str
    motion_not: str


def opposition_motions(
    corpus: pl.DataFrame, originators: pl.DataFrame, who: Opposition
) -> pl.DataFrame:
    """Die Anträge allein der Opposition: (``id``, ``parteien``), nach ``id``.

    Ein Antrag ist eine Drucksache, deren Dokumentart (klein) ``motion_type`` enthält und
    ``motion_not`` nicht; seine Urheber nennt Option 04 (``urheber_art`` Fraktion, mindestens eine
    Partei). Allein der Opposition heißt: keine Partei der Mehrheit und keine ausgelassene.
    """
    kind = pl.col("paper_type").str.to_lowercase()
    is_motion = kind.str.contains(who.motion_type, literal=True)
    if who.motion_not:
        is_motion = is_motion & ~kind.str.contains(who.motion_not, literal=True)
    motions = corpus.filter(is_motion.fill_null(False)).select("id")
    parties = pl.col("parteien").list
    named = sorted(who.majority | who.excluded)
    return (
        motions.join(originators.select("id", "urheber_art", "parteien"), on="id", how="inner")
        .filter(
            (pl.col("urheber_art") == FRACTION)
            & (parties.len() > 0)
            & ~parties.eval(pl.element().is_in(named)).list.any()
        )
        .select("id", "parteien")
        .sort("id")
    )


def _last_fits(
    votes: pl.DataFrame,
    motions: pl.DataFrame,
    kinds: Collection[str],
    results: Collection[str],
    start: dt.date,
    end: dt.date | None,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return sorted_unique(result, "id") and values_known(result, "ergebnis", results)


@deal.ensure(_last_fits, message="je Antrag eine Zeile, nach id, mit einem gezählten Ergebnis")
def last_decisions(
    votes: pl.DataFrame,
    motions: pl.DataFrame,
    kinds: Collection[str],
    results: Collection[str],
    start: dt.date,
    end: dt.date | None,
) -> pl.DataFrame:
    """Je Antrag aus ``motions`` der letzte Punkt mit einem Ergebnis aus ``results`` in Gremien der
    Arten ``kinds`` mit Sitzung im Zeitraum (beide Grenzen einschließlich, ``end`` None: offen).

    „Letzter" nach Sitzungsdatum, dann ID des Punkts, wie im Messskript. Ein Antrag ohne einen
    solchen Punkt fehlt. Spalten: ``id``, ``top``, ``datum``, ``ergebnis``, ``geaendert``,
    ``result``, ``parteien``.
    """
    window = pl.col("datum") >= start
    if end is not None:
        window = window & (pl.col("datum") <= end)
    found = (
        votes.filter(
            pl.col("gremium_art").is_in(list(kinds))
            & pl.col("ergebnis").is_in(list(results))
            & window
        )
        .sort("datum", "top")
        .group_by("paper", maintain_order=True)
        .last()
        .select(pl.col("paper").alias("id"), "top", "datum", "ergebnis", "geaendert", "result")
    )
    return found.join(motions, on="id", how="inner").sort("id")


@dataclass(frozen=True)
class Binomial:
    """Einseitiger exakter Binomialtest gegen ``p0`` (H1: p < p0) und die Grenzen nach Clopper-Pearson."""

    n: int
    k: int
    p: float
    lower: float  # einseitige untere 95-%-Grenze
    upper: float  # einseitige obere 95-%-Grenze

    @property
    def share(self) -> float:
        return self.k / self.n


@deal.pre(lambda k, n, p0: 0 <= k <= n and n >= 1 and 0.0 < p0 < 1.0)
@deal.ensure(
    lambda k, n, p0, result: (
        0.0 <= result.lower <= k / n <= result.upper <= 1.0 and 0.0 <= result.p <= 1.0
    ),
    message="untere Grenze ≤ Anteil ≤ obere Grenze, p in [0, 1]",
)
def binomial_less(k: int, n: int, p0: float) -> Binomial:
    """p = P(X ≤ k) unter Bin(n, p0); die einseitigen 95-%-Grenzen nach Clopper-Pearson."""
    alpha = 1.0 - CONFIDENCE
    p = float(stats.binom.cdf(k, n, p0))
    lower = 0.0 if k == 0 else float(stats.beta.ppf(alpha, k, n - k + 1))
    upper = 1.0 if k == n else float(stats.beta.ppf(1.0 - alpha, k + 1, n - k))
    return Binomial(n, k, min(1.0, p), min(lower, k / n), max(upper, k / n))


# --- Die Hypothesentabelle (§ 8.6, Kern aus analysis.hypotheses) ---------------------------------
@dataclass(frozen=True)
class Window:
    """Ein Zeitraum des Profils mit seiner Rechnung und der Mehrheit an seinem Beginn."""

    calculation: str  # haupttest oder R2
    start: dt.date
    end: dt.date | None
    majority: frozenset[str] | None  # None: das Profil kennt keine Mehrheit für den Zeitraum


@dataclass(frozen=True)
class HypothesisInputs:
    """Was ``hypothesis_rows`` liest: Punkte, Korpus (``id``, ``paper_type``), Urheber (Option 04)."""

    votes: pl.DataFrame
    corpus: pl.DataFrame
    originators: pl.DataFrame


def _row(**values: object) -> dict[str, object]:
    return {name: values.get(name) for name in HYPOTHESES_SCHEMA}


def _counted(
    hypothesis: str, calculation: str, window: Window, test: Binomial | None, **extra: object
) -> dict[str, object]:
    return _row(
        hypothese=hypothesis,
        rechnung=calculation,
        n=test.n if test else 0,
        p=test.p if test else None,
        angenommen=test.k if test else 0,
        anteil=test.share if test else None,
        ci_unten=test.lower if test else None,
        ci_oben=test.upper if test else None,
        von=window.start,
        bis=window.end,
        **extra,
    )


def _units(
    inputs: HypothesisInputs,
    motions: pl.DataFrame,
    window: Window,
    kinds: tuple[str, ...],
    results: tuple[str, ...],
) -> pl.DataFrame:
    """Die Anträge mit ihrem letzten Punkt im Zeitraum, in Gremien dieser Arten (``last_decisions``)."""
    return last_decisions(inputs.votes, motions, kinds, results, window.start, window.end)


def _test(frame: pl.DataFrame, threshold: float) -> Binomial | None:
    if frame.is_empty():
        return None
    return binomial_less(
        frame.filter(pl.col("ergebnis") == ACCEPTED).height, frame.height, threshold
    )


def _table_holds(result: pl.DataFrame, votes: Votes) -> bool:
    try:
        check_hypotheses(result, votes.alpha, key=HYPOTHESIS_KEY, strict=True, m=len(HYPOTHESES))
    except SchemaError:
        return False
    main = result.filter(pl.col("rechnung") == MAIN)
    side = result.filter(pl.col("rechnung") != MAIN)
    undecided = main.filter(pl.col("entscheidung") == UNDECIDABLE)
    return (
        result.schema == pl.Schema(HYPOTHESES_SCHEMA)
        and values_known(result, "rechnung", CALCULATIONS)
        and values_known(result, "entscheidung", DECISIONS)
        and values_known(result, "grund", REASONS)
        and main.get_column("entscheidung").null_count() == 0
        and undecided.get_column("grund").null_count() == 0
        and side.get_column("entscheidung").null_count() == side.height
        and side.get_column("p_holm").null_count() == side.height
    )


def _rows_hold(
    inputs: HypothesisInputs,
    windows: Sequence[Window],
    votes: Votes,
    labels: Mapping[str, str],
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return _table_holds(result, votes)


@deal.ensure(
    _rows_hold,
    message="der Kern aus 17 mit strict und m = 3; Entscheidung genau beim Haupttest",
)
def hypothesis_rows(
    inputs: HypothesisInputs,
    windows: Sequence[Window],
    votes: Votes,
    labels: Mapping[str, str],
) -> pl.DataFrame:
    """Die Zeilen von ``abstimmungen_hypothesen``: je Zeitraum H28.1 bis H28.3, beim Haupttest R1,
    R3 und R4 dazu. ``labels`` nennt die Parteien in der Folge von ``[originators]`` (für R4).

    H28.1 und H28.3 sind **nicht entscheidbar**: sie brauchen die Positionen der Fraktionen, und
    Ebene B verfehlte das Kriterium (``LEVEL_B``). Sie stehen ohne ``p`` und ``n`` da, zählen für
    Holm aber mit (m = 3, Kern aus ``analysis.hypotheses``). H28.2 ist im Haupttest in der Familie,
    wenn er entscheiden darf (Ebene A erfüllt das Kriterium, n ≥ ``min_units``, die Mehrheit ist
    bekannt): ``bestätigt``, wenn Holm bei ``p_holm < alpha`` verwirft, ``widerlegt``, wenn die
    untere einseitige Grenze nach Clopper-Pearson über der Schwelle liegt, sonst nicht entscheidbar.
    Die Nebenrechnungen R1 bis R4 berichten nur (§ 8.6): ohne ``p_holm``, ohne Entscheidung.
    """
    rows: list[dict[str, object]] = []
    for window in windows:
        common = {"rechnung": window.calculation, "festgelegt": votes.fixed}
        span = {"von": window.start, "bis": window.end}
        undecidable = {
            hypothesis: _row(hypothese=hypothesis, grund=LEVEL_B_REJECTED, **common, **span)
            for hypothesis in (H1, H3)
        }
        if window.majority is None:
            rows += [
                undecidable[H1],
                _row(hypothese=H2, grund=NO_MAJORITY, **common, **span),
                undecidable[H3],
            ]
            continue
        who = Opposition(
            window.majority, frozenset(votes.excluded_parties), votes.motion_type, votes.motion_not
        )
        motions = opposition_motions(inputs.corpus, inputs.originators, who)
        council = _units(inputs, motions, window, (COUNCIL,), VOTE_DECIDED)
        extra = {"festgelegt": votes.fixed, "schwelle": votes.threshold}
        tested = _counted(H2, window.calculation, window, _test(council, votes.threshold), **extra)
        rows += [undecidable[H1], tested, undecidable[H3]]
        if window.calculation != MAIN:
            continue
        for calculation, frame in (
            (R1, _units(inputs, motions, window, (COMMITTEE,), VOTE_DECIDED)),
            (R3, _units(inputs, motions, window, (COUNCIL,), (*VOTE_DECIDED, *UNDECIDED_IN_R3))),
        ):
            rows.append(_counted(H2, calculation, window, _test(frame, votes.threshold), **extra))
        present = set(council.get_column("parteien").explode().drop_nulls().to_list())
        for party in [key for key in labels if key in present]:
            own = council.filter(pl.col("parteien").list.contains(party))
            test = _test(own, votes.threshold)
            rows.append(_counted(H2, R4, window, test, partei=party, **extra))
    frame = pl.DataFrame(rows, schema=HYPOTHESES_SCHEMA)
    return _decide(frame, votes).with_columns(
        pl.when(pl.col("rechnung") == MAIN)
        .then(pl.col("entscheidung").fill_null(UNDECIDABLE))
        .otherwise(None)
        .alias("entscheidung")
    )


def _decide(frame: pl.DataFrame, votes: Votes) -> pl.DataFrame:
    """Holm über die Familie (H28.2 im Haupttest, m = 3) und die Entscheidung des Haupttests."""
    main = (pl.col("hypothese") == H2) & (pl.col("rechnung") == MAIN) & pl.col("grund").is_null()
    tested = frame.filter(main & pl.col("p").is_not_null() & (pl.col("n") >= votes.min_units))
    judged = (
        family(
            dict(tested.select("hypothese", "p").iter_rows()),
            alpha=votes.alpha,
            strict=True,
            m=len(HYPOTHESES),
        )
        if tested.height and LEVEL_A.met
        else {}
    )
    rows = frame.rows(named=True)
    for row in rows:
        if row["hypothese"] != H2 or row["rechnung"] != MAIN or row["grund"]:
            continue
        if not LEVEL_A.met:
            row.update(entscheidung=UNDECIDABLE, grund=LEVEL_A_MISSED)
        elif row["hypothese"] not in judged:
            row.update(entscheidung=UNDECIDABLE, grund=TOO_FEW)
        else:
            row["p_holm"], row["ergebnis"] = judged[row["hypothese"]]
            if row["ergebnis"] == CONFIRMED:
                row["entscheidung"] = CONFIRMED
            elif row["ci_unten"] > votes.threshold:
                row["entscheidung"] = REFUTED
            else:
                row.update(entscheidung=UNDECIDABLE, grund=NEITHER)
    return pl.DataFrame(rows, schema=HYPOTHESES_SCHEMA)
