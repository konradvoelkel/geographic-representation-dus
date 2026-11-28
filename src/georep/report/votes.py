"""Der Abschnitt „Abstimmungen" auf ``akteure.html`` (Vorhaben 28, Stufe 3, nur Ebene A).

Ein Gast auf der Seite von Vorhaben 15 (``Contribution.sections``, Vorarbeit V1, Punkt 86), nach
``docs/plans/28-abstimmungen.md``, § 7 und § 10, Punkt 5. Für alle Fraktionen gleich gebaut, ohne
Personen und ohne Positionen je Fraktion:

1. *Einstimmig, mehrheitlich, geändert* je Gremienart der Periode, aus ``abstimmungen_gremien``,
   „explorativ" wie im Messdokument (§ 8.6);
2. *die vorab festgelegten Prüfungen* H28.1 bis H28.3 mit dem Kern aus ``analysis.hypotheses``:
   H28.2 gerechnet, H28.1 und H28.3 „nicht entscheidbar", festgelegt mit Commit ``votes.fixed``;
   darunter die Nebenrechnungen von H28.2, die nichts entscheiden.

**Die Prüfung** kommt aus ``validierung/28-abstimmungen/guete.json`` (Satz, Modelle; von der
Übereinstimmung der Kodierer nur die Fragen ``ergebnis`` und ``form`` und nur mit
``alpha_genuegt``) und, was die Datei nicht trägt, aus ``RULE_CHECK``: die Wortregel gegen die
Endlabels (A1, § 4.1). Der slow-Test ``tests/golden/test_votes_numbers.py`` rechnet sie aus
``labels.csv`` und der gebauten Tabelle der Hauptperiode nach. Ein Datensatz außerhalb der
Stichprobe heißt „explorativ" (``docs/plan-zeigen-2026-11.md``, § 8).

Was einem Profil fehlt, sagt der Abschnitt (Plan § 6): ohne den Schritt ``votes`` (Schalter aus
oder ohne Beratungsverlauf von 26) steht nur das da, ohne Zeitraum keine Prüfung. Kein Stadtwort,
keine Partei im Code: Namen, Mehrheiten und Zeiträume kommen aus den Settings.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import deal
import polars as pl

from georep.analysis.votes import (
    COUNTS,
    H1,
    H2,
    H3,
    KIND_ORDER,
    LEVEL_A,
    LEVEL_A_MISSED,
    LEVEL_B,
    LEVEL_B_REJECTED,
    MAIN,
    NEITHER,
    NO_MAJORITY,
    R1,
    R2,
    R3,
    R4,
    TOO_FEW,
    LevelVerdict,
)
from georep.errors import MissingInputError, SchemaError
from georep.layout import Layout
from georep.prep.bodies import KIND_LABELS
from georep.report.model import format_de, percent_de
from georep.report.need import p_text
from georep.settings import Settings

HOST = "akteure"  # die Seite von Vorhaben 15
SECTION = "abstimmungen"  # der Name, den 15 verlinkt (Punkt 88)
VALIDATION_PROJECT = "28-abstimmungen"
MEASUREMENT = "docs/plans/28-abstimmungen.md"
QUESTIONS = ("ergebnis", "form")  # die Fragen der Ebene A im Codebuch (§ 10, Punkt 6)
QUESTION_LABELS = {"ergebnis": "beim Ergebnis", "form": "bei der Form"}
WZB_SHARE = 0.188  # H28.3: 934 von 4 968 Anträgen der WZB-Studie (§ 8.6)
# Mehrzahl der Gremienarten für die Tabelle
KIND_PLURAL = {
    "rat": "Rat",
    "ausschuss": "Ausschüsse",
    "bezirksvertretung": "Bezirksvertretungen",
    "beirat": "Beiräte",
    "unbekannt": "Gremium unbekannt",
}
CALCULATION_LABELS = {
    MAIN: "Haupttest",
    R1: "R1, Ausschüsse statt Rat",
    R2: "R2, ab der Vereinbarung der neuen Mehrheit",
    R3: "R3, auch vertagte, verwiesene, erledigte und zurückgezogene Anträge im Nenner",
    R4: "R4, je Fraktion",
}
REASON_TEXT = {
    LEVEL_B_REJECTED: (
        "braucht die Positionen der Fraktionen aus den Niederschriften, und diese Ebene verfehlte "
        "das Kriterium"
    ),
    LEVEL_A_MISSED: "Ergebnis und Form aus dem Eintrag verfehlten das Kriterium",
    TOO_FEW: "zu wenige Anträge",
    NO_MAJORITY: "das Profil nennt für den Zeitraum keine Mehrheit",
    NEITHER: (
        "Holm verwirft nicht, und die untere Grenze des Anteils liegt nicht über der Schwelle"
    ),
}


# --- Die Prüfung (F4, Punkt 87) ------------------------------------------------------------------
@dataclass(frozen=True)
class RuleCheck:
    """Was ``guete.json`` nicht trägt: die Wortregel gegen die Endlabels (A1, Messdokument § 4.1).

    Treffer und Nenner roh, die Präzision gewichtet mit N_h/n_h, Wilson bei Kishs n_eff (wie das
    Messskript); dazu die Abdeckung der Hauptperiode (§ 3.2) und das Urteil über Ebene B.
    ``read_check`` vergleicht Codebuch und Zahl der Einheiten mit ``guete.json``: eine neue
    Kodierung macht die Konstante ungültig (wie Punkt 88, N1).
    """

    hits: int
    basis: int
    n_eff: float
    level_a: LevelVerdict
    level_b: LevelVerdict
    with_form: int  # Beschlüsse der Hauptperiode mit Form aus dem Eintrag (Messung, § 3.2)
    decided: int  # Beschlüsse der Hauptperiode
    criterion: float  # die verlangte Präzision (§ 8.2)
    codebook_version: str
    units: int


RULE_CHECK = RuleCheck(
    hits=90,
    basis=92,
    n_eff=90.1,
    level_a=LEVEL_A,
    level_b=LEVEL_B,
    with_form=10_856,
    decided=12_570,
    criterion=0.9,
    codebook_version="2026-11-24.1",
    units=150,
)


@dataclass(frozen=True)
class Agreement:
    """Übereinstimmung der Kodierer an einer Frage, nur wenn α genügt."""

    question: str
    label: str
    agreed: int
    paired: int
    alpha: float


@dataclass(frozen=True)
class VotesCheck:
    sentence: str  # ``satz`` aus ``guete.json``
    agreements: tuple[Agreement, ...]
    same_model: bool
    rule: RuleCheck
    measured: bool
    measured_datasets: tuple[str, ...]


def check_files(settings: Settings) -> tuple[Path, Path]:
    """``guete.json`` und ``stichprobe.json`` der Prüfung im Repo unter ``validation.root``."""
    folder = settings.validation.root / VALIDATION_PROJECT
    return folder / "guete.json", folder / "stichprobe.json"


@deal.raises(MissingInputError, SchemaError)
def read_check(settings: Settings, rule: RuleCheck = RULE_CHECK) -> VotesCheck:
    """Der Prüfsatz aus ``guete.json`` und ``stichprobe.json``; ``SchemaError`` bei fehlendem Feld
    oder wenn ``guete.json`` eine andere Kodierung beschreibt als ``RULE_CHECK``."""
    from georep.report.actors import _dataset_name, _profile_folders

    quality_path, sample_path = check_files(settings)
    for path in (quality_path, sample_path):
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; der Abschnitt {SECTION} nennt seine Prüfung")
    quality: dict[str, Any] = json.loads(quality_path.read_text(encoding="utf-8"))
    sample: dict[str, Any] = json.loads(sample_path.read_text(encoding="utf-8"))
    try:
        sentence = str(quality["satz"])
        models = dict(quality["modelle"])
        questions = dict(quality["fragen"])
        agreements = tuple(
            Agreement(
                name,
                QUESTION_LABELS[name],
                int(questions[name]["einig"]),
                int(questions[name]["beide"]),
                float(questions[name]["krippendorff_alpha"]),
            )
            for name in QUESTIONS
            if bool(questions[name]["alpha_genuegt"])
        )
        measured_on = (str(quality["codebuch_version"]), int(quality["einheiten"]))
        profiles = tuple(p.strip() for p in str(sample["profil"]).split(",") if p.strip())
    except (KeyError, TypeError, ValueError) as error:
        raise SchemaError(f"{quality_path} oder {sample_path}: Feld fehlt ({error})") from error
    if measured_on != (rule.codebook_version, rule.units):
        raise SchemaError(
            f"{quality_path}: Codebuch {measured_on[0]} an {measured_on[1]} Einheiten, RULE_CHECK "
            f"gilt für {rule.codebook_version} an {rule.units}; die Wortregel ist gegen die neue "
            "Kodierung nachzurechnen"
        )
    return VotesCheck(
        sentence=sentence,
        agreements=agreements,
        same_model=models.get("kodierer_a") == models.get("kodierer_b"),
        rule=rule,
        measured=settings.profile in _profile_folders(profiles),
        measured_datasets=tuple(_dataset_name(p) for p in profiles),
    )


# --- Je Gremienart --------------------------------------------------------------------------------
@dataclass(frozen=True)
class KindRow:
    kind: str
    label: str
    items: int
    decided: int
    accepted: int
    rejected: int
    unanimous: int
    majority: int
    unstated: int
    changed: int

    def share(self, count: int) -> float | None:
        return count / self.decided if self.decided else None


def kind_rows(bodies: pl.DataFrame) -> tuple[KindRow, ...]:
    """Die Zeilen von ``abstimmungen_gremien`` in der Folge von ``KIND_ORDER``; ohne Beschluss keine."""
    rows = {row["gremium_art"]: row for row in bodies.iter_rows(named=True)}
    return tuple(
        KindRow(
            kind=kind,
            label=KIND_PLURAL.get(kind, KIND_LABELS.get(kind, kind)),
            items=int(rows[kind]["punkte"]),
            decided=int(rows[kind]["beschluesse"]),
            accepted=int(rows[kind]["angenommen"]),
            rejected=int(rows[kind]["abgelehnt"]),
            unanimous=int(rows[kind]["einstimmig"]),
            majority=int(rows[kind]["mehrheitlich"]),
            unstated=int(rows[kind]["ohne_angabe"]),
            changed=int(rows[kind]["geaendert"]),
        )
        for kind in KIND_ORDER
        if kind in rows and rows[kind]["beschluesse"]
    )


def total_row(bodies: pl.DataFrame) -> KindRow | None:
    """Die Summe über alle Gremienarten; ``None`` ohne Beschluss."""
    if bodies.is_empty():
        return None
    total = bodies.select(pl.col(c).sum() for c in COUNTS).row(0, named=True)
    if not total["beschluesse"]:
        return None
    return KindRow(
        kind="alle",
        label="alle Gremien",
        items=int(total["punkte"]),
        decided=int(total["beschluesse"]),
        accepted=int(total["angenommen"]),
        rejected=int(total["abgelehnt"]),
        unanimous=int(total["einstimmig"]),
        majority=int(total["mehrheitlich"]),
        unstated=int(total["ohne_angabe"]),
        changed=int(total["geaendert"]),
    )


# --- Die Prüfungen --------------------------------------------------------------------------------
@dataclass(frozen=True)
class TestRow:
    """Eine Zeile der Hypothesentabelle, für die Vorlage aufbereitet."""

    hypothesis: str
    calculation: str  # Schlüssel: haupttest, R1 …
    calculation_label: str
    party: str  # nur R4: der Kurzname der Fraktion
    n: int | None
    accepted: int | None
    share: float | None
    p: str  # deutsch, „–" ohne Wert
    p_holm: str
    result: str | None  # bestätigt oder nicht bestätigt (Holm)
    decision: str | None  # bestätigt, widerlegt, nicht entscheidbar (nur Haupttest)
    reason: str  # der Satz zu ``grund``; leer ohne
    lower: float | None
    upper: float | None
    start: dt.date | None
    end: dt.date | None


def test_rows(tests: pl.DataFrame, labels: Mapping[str, str]) -> tuple[TestRow, ...]:
    """Die Zeilen in der Folge der Tabelle (je Zeitraum H28.1 bis H28.3, dann die Nebenrechnungen)."""
    return tuple(
        TestRow(
            hypothesis=row["hypothese"],
            calculation=row["rechnung"],
            calculation_label=CALCULATION_LABELS[row["rechnung"]],
            party=labels.get(row["partei"] or "", row["partei"] or ""),
            n=row["n"],
            accepted=row["angenommen"],
            share=row["anteil"],
            p=p_text(row["p"]),
            p_holm=p_text(row["p_holm"]),
            result=row["ergebnis"],
            decision=row["entscheidung"],
            reason=REASON_TEXT.get(row["grund"] or "", ""),
            lower=row["ci_unten"],
            upper=row["ci_oben"],
            start=row["von"],
            end=row["bis"],
        )
        for row in tests.iter_rows(named=True)
    )


@dataclass(frozen=True)
class Statement:
    """Die These einer Hypothese in Worten, mit Namen aus den Settings."""

    hypothesis: str
    text: str


def statements(settings: Settings, labels: Mapping[str, str]) -> tuple[Statement, ...]:
    """H28.1 bis H28.3 wie in § 8.6, die Parteien aus ``[majorities]`` und ``votes.excluded_parties``."""
    main = next((w for w in settings.votes.windows if w.calculation == MAIN), None)
    term = settings.majorities.on(main.start) if main is not None else None
    majority = (
        " und ".join(labels.get(p, p) for p in term.parties) if term is not None else "der Mehrheit"
    )
    excluded = " und ".join(labels.get(p, p) for p in settings.votes.excluded_parties)
    with_excluded = f"an denen {excluded} beteiligt ist" if excluded else ""
    return (
        Statement(
            H1,
            f"In strittigen Abstimmungen des Rates stimmen die Fraktionen der Ratsmehrheit "
            f"({majority}) gleich.",
        ),
        Statement(
            H2,
            "Anträge, die nur Fraktionen der Opposition stellen, nimmt der Rat in weniger als "
            f"{percent_de(settings.votes.threshold, 0)} der Fälle an"
            + (f" (ohne Anträge, {with_excluded}; die prüft H28.3)." if excluded else "."),
        ),
        Statement(
            H3,
            f"Anträge, {with_excluded or 'an denen die ausgegrenzte Fraktion beteiligt ist'}, "
            "finden im Rat seltener Zustimmung von mindestens einem Zehntel der übrigen Mitglieder "
            f"als in der WZB-Studie ({percent_de(WZB_SHARE, 1)}).",
        ),
    )


# --- Das Modell des Abschnitts --------------------------------------------------------------------
@dataclass(frozen=True)
class VotesModel:
    on: bool  # der Schritt ``votes`` ist in diesem Profil gebaut
    period: str  # Titel der Periode
    check: VotesCheck | None
    kinds: tuple[KindRow, ...]
    total: KindRow | None
    tests: tuple[TestRow, ...]  # Haupttest und R2: H28.1 bis H28.3
    side: tuple[TestRow, ...]  # R1, R3, R4
    statements: tuple[Statement, ...]
    windows: tuple[tuple[str, dt.date, dt.date | None], ...]  # alle festgelegten, auch fremde
    fixed: str
    fixed_on: dt.date | None
    alpha: float
    threshold: float
    min_units: int
    missing: tuple[str, ...]

    @property
    def explorative(self) -> bool:
        return self.check is not None and not self.check.measured

    @property
    def has_main(self) -> bool:
        return any(t.calculation == MAIN for t in self.tests)


def _missing(settings: Settings, on: bool, tests: Sequence[TestRow]) -> tuple[str, ...]:
    """Was in diesem Profil fehlt, in Sätzen (Plan § 6)."""
    if not on:
        reason = (
            "der Schritt ist für dieses Profil nicht eingeschaltet: der Wortschatz, mit dem die "
            "Sitzungsleitung hier Ergebnisse einträgt, ist nicht gemessen"
            if not settings.outcomes.enabled
            else "der Schalter votes.enabled ist aus"
        )
        return (f"Abstimmungen: {reason}.",)
    lines = [
        "Wer wie gestimmt hat (Positionen der Fraktionen aus den Niederschriften): die Prüfung "
        f"verfehlte das Kriterium (Präzision {format_de(RULE_CHECK.level_b.precision, 3)} bei "
        f"{format_de(RULE_CHECK.criterion, 1)} verlangt); damit fehlen H28.1 und H28.3."
    ]
    if not tests:
        lines.append(
            "Vorab festgelegte Prüfungen: keiner ihrer Zeiträume liegt in diesem Datensatz."
        )
    return tuple(lines)


def build_votes(
    settings: Settings,
    bodies: pl.DataFrame | None,
    tests: pl.DataFrame | None,
    check: VotesCheck,
) -> VotesModel:
    """Das Modell aus den Tabellen des Schritts; ``None`` für beide, wenn er nicht gebaut ist."""
    from georep.enrich.votes import party_labels
    from georep.report.model import period_info

    labels = party_labels(settings)
    on = bodies is not None and tests is not None
    rows = test_rows(tests, labels) if tests is not None else ()
    return VotesModel(
        on=on,
        period=period_info(settings).title,
        check=check,
        kinds=kind_rows(bodies) if bodies is not None else (),
        total=total_row(bodies) if bodies is not None else None,
        tests=tuple(r for r in rows if r.calculation in (MAIN, R2)),
        side=tuple(r for r in rows if r.calculation not in (MAIN, R2)),
        statements=statements(settings, labels),
        windows=tuple((w.calculation, w.start, w.end) for w in settings.votes.windows),
        fixed=settings.votes.fixed,
        fixed_on=settings.votes.fixed_on,
        alpha=settings.votes.alpha,
        threshold=settings.votes.threshold,
        min_units=settings.votes.min_units,
        missing=_missing(settings, on, rows),
    )


def _step_files(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Die beiden Tabellen, die der Abschnitt liest, wenn der Schritt in diesem Profil gebaut wird."""
    from georep.enrich.votes import vote_files, votes_enabled

    if not votes_enabled(settings):
        return ()
    files = vote_files(layout)
    return (files.bodies, files.hypotheses)


def votes_section_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """``PageSection.inputs``: die Tabellen des Schritts (nur wenn er gebaut wird) und die Prüfung."""
    return (*_step_files(layout, settings), *check_files(settings))


def votes_section_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    """``PageSection.data``: der Schlüssel ``abstimmungen`` steht immer da (Punkt 86, N5)."""
    files = _step_files(layout, settings)
    bodies, tests = (pl.read_parquet(path) for path in files) if files else (None, None)
    model = build_votes(settings, bodies, tests, read_check(settings))
    return {
        "abstimmungen": model,
        "calculation_labels": CALCULATION_LABELS,
        "urls": repository_links(settings),
    }


def repository_links(settings: Settings) -> dict[str, str]:
    """Messdokument, README der Prüfung und der Commit der Festlegung im Repository."""
    from georep.report.render import REPOSITORY

    folder = settings.validation.root.name
    links = {
        "measurement": f"{REPOSITORY}/blob/main/{MEASUREMENT}",
        "check": f"{REPOSITORY}/blob/main/{folder}/{VALIDATION_PROJECT}/README.md",
        "check_folder": f"{folder}/{VALIDATION_PROJECT}",
    }
    if settings.votes.fixed:
        links["commit"] = f"{REPOSITORY}/commit/{settings.votes.fixed}"
    return links


def votes_section_links(layout: Layout, settings: Settings) -> frozenset[str]:
    """Die Links nach außen: Messdokument, Prüfung und Commit im Repository."""
    links = repository_links(settings)
    return frozenset(v for k, v in links.items() if k != "check_folder")
