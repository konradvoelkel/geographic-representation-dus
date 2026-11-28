"""Die Beschlusslage auf ``vorgaenge.html``, im Dokumentdialog und als Download (Vorhaben 26, Stufe 3).

Stufe 3 von Vorhaben 26 nach ``docs/plans/26-beschluesse.md``, § 7 und § 10, mit Rückfall 1 (§ 5:
kein Prüfauftrag auf der Seite). Drei Gäste auf der Seite von Vorhaben 14 (``Contribution.sections``,
Vorarbeit V1, Punkt 86), in dieser Folge:

1. *Beschlusslage je Gremium* (``SECTION_OUTCOMES``): je Gremium der Drucksache die Anträge, Anteil
   angenommen (davon mit Änderungen), abgelehnt, zurückgezogen, ohne Abstimmung erledigt, offen,
   ohne Ergebnis; Median der Tage bis zur Entscheidung bei mehr als einer Beratung. Darüber, was
   „ohne Ergebnis" heißt, mit der Sitzung, in der die meisten liegen; Anträge in einer Praxiszelle
   (``eintrag_tragfaehig`` falsch) zählen in keinem Anteil, die Zellen stehen als Fußnote (§ 5).
2. *Erfolg je Fraktion* (``SECTION_SUCCESS``), explorativ: beobachtet gegen erwartet aus
   ``antragserfolg`` mit n und dem exakten Intervall nach Poisson, getrennt nach Rat mit Ausschüssen
   und nach Bezirksvertretungen, für alle Fraktionen gleich und nach Namen, nie nach dem Verhältnis
   (Frage 9.5). Keine rohe Quote und keine Spalte, aus der sie folgte.
3. *In der Sitzung beantwortet* (``SECTION_SESSION``, der Name, den 14 als ``SESSION_GUEST``
   erwartet): je Gremium der Anfragen der Anteil, dessen maßgeblicher Eintrag eine Antwort einträgt
   (``outcomes.answered``), neben den Antworten im System von 14. Wortlaut, keine geprüfte Klasse
   (Frage 9.9).

Dazu der Haken ``beschluesse`` im Dokumentdialog (``report.dialog``, Format 3): je Antrag ein Wort mit
Klasse, Gremium und Tag der Entscheidung; die Downloads ``beschlusslage``, ``beratungsverlauf`` (nur
Parquet) und ``antragserfolg`` stehen bei ihrem Beitrag (``enrich.outcomes``).

**Die Prüfung** kommt aus ``validierung/26-beschluesse/guete.json`` (Satz, Modelle, und von der
Übereinstimmung der Kodierer nur ``ergebnis`` mit ``alpha_genuegt``) und, was die Datei nicht trägt,
aus ``OUTCOMES_CHECK``: die Regel gegen die Endlabels (Messdokument § 4.1, Rückfall 1), nachgerechnet
im slow-Test ``tests/golden/test_outcomes.py``. Gemessen ist an den Profilen aus ``stichprobe.json``
(die Stichprobe zieht aus allen drei Düsseldorfer Perioden); jeder andere Datensatz heißt
„explorativ". Ob der Eintrag der Sitzungsleitung stimmt, prüft niemand: das zeigte nur die
Niederschrift, und das sagt jeder Satz.

Was einem Profil fehlt, sagt der erste Abschnitt (Plan § 6); der zweite und der dritte stehen nur
dort, wo der Schritt ``outcomes`` gebaut wird. Kein Stadtwort, keine Partei im Code: Gremien,
Fraktionen, Mehrheiten und der Wortschatz kommen aus den Settings.
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

from georep.errors import MissingInputError, SchemaError
from georep.layout import Layout
from georep.report.dialog import DialogRows
from georep.settings import Settings, profile_folder
from georep.validation.measures import wilson_interval

HOST = "vorgaenge"  # die Seite von Vorhaben 14 (``report.procedures.PAGE_NAME``)
SECTION_OUTCOMES = "beschlusslage"
SECTION_SUCCESS = "antragserfolg"
SECTION_SESSION = (
    "in-der-sitzung"  # ``report.procedures.SESSION_GUEST``: ersetzt den Hinweis von 14
)
DIALOG_NAME = "beschluesse"  # data/beschluesse.json
DIALOG_TITLE = "Beschlusslage"
VALIDATION_PROJECT = "26-beschluesse"
MEASUREMENT = "docs/plans/26-beschluesse.md"
QUESTION = "ergebnis"  # die Frage des Codebuchs, die nach Rückfall 1 gilt
MOTION, INQUIRY = "antrag", "anfrage"  # Rollen der Dokumente in Vorhaben 14
MIN_MOTIONS = 30  # eine Zeile je Gremium ab so vielen Anträgen (wie die Anfragen bei 14)
MIN_DURATION = 10  # ein Median der Tage ab so vielen Anträgen
MIN_SUCCESS = 30  # ein Verhältnis je Fraktion ab so vielen Anträgen mit Sachentscheidung
MIN_EXPECTED = 10  # und ab so vielen erwarteten Annahmen (wie 14, Punkt 91)
MIN_QUESTIONS = 30  # eine Zeile je Gremium ab so vielen Anfragen, dieselben Zeilen wie bei 14
MIN_SESSION = 10  # eine Sitzung ohne Einträge wird genannt, wenn so viele Anträge darin liegen
NO_ANSWER = "keine"  # ``antwortzeiten.quelle`` ohne Antwort im System (Vorhaben 14)

# Die Klassen in Worten, für Tabelle und Dialog (Messdokument § 3.1; Frage 9.4: beschlossen und
# geändert zeigt die Seite als „angenommen", geändert als Unterzahl).
CLASS_WORDS: dict[str, str] = {
    "beschlossen": "angenommen",
    "geaendert": "angenommen mit Änderungen",
    "abgelehnt": "abgelehnt",
    "zurueckgezogen": "zurückgezogen",
    "erledigt": "ohne Abstimmung erledigt",
    "vertagt": "zuletzt vertagt",
    "offen": "verwiesen, danach nichts im Datensatz",
    "ohne_ergebnis": "kein Ergebnis eingetragen",
}
PRACTICE_WORD = "zur Kenntnis genommen; in diesem Gremium und Jahr ein Eintrag ohne Aussage"
# Die Gruppen des Erfolgs je Fraktion (§ 7): Rat mit Ausschüssen, Bezirksvertretungen.
GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("rat-ausschuss", "Rat und Ausschüsse", ("rat", "ausschuss")),
    ("bezirksvertretung", "Bezirksvertretungen", ("bezirksvertretung",)),
)
KIND_PLURAL = {"beirat": "Beiräten", "unbekannt": "Gremien, die nicht erkannt sind"}


# --- Die Prüfung (F4, Punkt 87) --------------------------------------------------------------------
@dataclass(frozen=True)
class RuleCheck:
    """Was ``guete.json`` nicht trägt: die Regel gegen die Endlabels (Messdokument § 4.1).

    Nach Rückfall 1 gilt nur ``ergebnis``: Treffer an den gewerteten Anträgen, gewichtet mit den
    Schichtgrößen (Wilson bei Kishs effektivem n, wie das Messskript), und die Fälle, die mehr
    verlangten als das Nachschlagen eines Eintrags (eine Folge mit Entscheidung über mehrere
    Einträge). ``read_check`` vergleicht Codebuch und Einheiten mit ``guete.json``.
    """

    codebook_version: str
    units: int
    hits: int
    basis: int
    weighted: float
    weighted_interval: tuple[float, float]
    n_eff: float
    hard_hits: int
    hard_basis: int

    @property
    def interval(self) -> tuple[float, float]:
        return wilson_interval(self.hits, self.basis)

    @property
    def hard_interval(self) -> tuple[float, float]:
        return wilson_interval(self.hard_hits, self.hard_basis)


OUTCOMES_CHECK = RuleCheck(
    codebook_version="1",
    units=150,
    hits=150,
    basis=150,
    weighted=1.0,
    weighted_interval=(0.962, 1.0),
    n_eff=96.9,
    hard_hits=17,
    hard_basis=17,
)


@dataclass(frozen=True)
class OutcomesCheck:
    sentence: str  # ``satz`` aus ``guete.json``: Modelle, Einheiten, „nicht von Menschen"
    rule: RuleCheck
    agreed: int | None  # Übereinstimmung der Kodierer bei ``ergebnis``; None, wenn α nicht genügt
    paired: int | None
    alpha: float | None
    same_model: bool
    measured: bool
    measured_datasets: tuple[str, ...]

    @property
    def sufficient(self) -> bool:
        return self.alpha is not None


def check_files(settings: Settings) -> tuple[Path, Path]:
    """``guete.json`` und ``stichprobe.json`` der Kodierung im Repo unter ``validation.root``."""
    folder = settings.validation.root / VALIDATION_PROJECT
    return folder / "guete.json", folder / "stichprobe.json"


def sample_profiles(sample: Mapping[str, Any]) -> tuple[str, ...]:
    """Die Profile der Stichprobe: ``profile`` (die Liste), sonst ``profil`` mit Kommas.

    Die Stichprobe von 26 zieht aus allen drei Düsseldorfer Perioden (Messdokument § 4: 91, 42 und
    17 Anträge) und nennt sie in ``profile``; ``profil`` trägt dort nur die Hauptperiode.
    """
    listed = sample.get("profile")
    if isinstance(listed, list) and listed:
        return tuple(str(p).strip() for p in listed if str(p).strip())
    return tuple(p.strip() for p in str(sample["profil"]).split(",") if p.strip())


def _folders(profiles: Sequence[str]) -> set[str]:
    found: set[str] = set()
    for name in profiles:
        try:
            found.add(profile_folder(name))
        except OSError, ValueError, SchemaError:
            continue
    return found


@deal.raises(MissingInputError, SchemaError)
def read_check(settings: Settings, rule: RuleCheck = OUTCOMES_CHECK) -> OutcomesCheck:
    """Der Prüfsatz aus ``guete.json`` und ``stichprobe.json``; ``SchemaError`` bei fehlendem Feld
    oder wenn ``guete.json`` eine andere Kodierung beschreibt als ``rule``."""
    from georep.report.procedures import _dataset_name

    quality_path, sample_path = check_files(settings)
    for path in (quality_path, sample_path):
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; die Beschlusslage nennt ihre Prüfung")
    quality: dict[str, Any] = json.loads(quality_path.read_text(encoding="utf-8"))
    sample: dict[str, Any] = json.loads(sample_path.read_text(encoding="utf-8"))
    try:
        sentence = str(quality["satz"])
        models = dict(quality["modelle"])
        question = dict(quality["fragen"][QUESTION])
        sufficient = bool(question["alpha_genuegt"])
        measured_on = (str(quality["codebuch_version"]), int(quality["einheiten"]))
        profiles = sample_profiles(sample)
    except (KeyError, TypeError, ValueError) as error:
        raise SchemaError(f"{quality_path} oder {sample_path}: Feld fehlt ({error})") from error
    if measured_on != (rule.codebook_version, rule.units):
        raise SchemaError(
            f"{quality_path}: Codebuch {measured_on[0]} an {measured_on[1]} Einheiten, "
            f"OUTCOMES_CHECK gilt für {rule.codebook_version} an {rule.units}; die Regel ist gegen "
            "die neue Kodierung nachzurechnen"
        )
    return OutcomesCheck(
        sentence=sentence,
        rule=rule,
        agreed=int(question["einig"]) if sufficient else None,
        paired=int(question["beide"]) if sufficient else None,
        alpha=float(question["krippendorff_alpha"]) if sufficient else None,
        same_model=models.get("kodierer_a") == models.get("kodierer_b"),
        measured=settings.profile in _folders(profiles),
        measured_datasets=tuple(_dataset_name(p) for p in profiles),
    )


def check_sentence(check: OutcomesCheck, *, short: bool = False) -> str:
    """Der Prüfsatz: woher die Klasse kommt, wie sie geprüft ist, und dass es der Eintrag ist.

    Kennzahlen nur bei genügendem α (``alpha_genuegt`` der Frage ``ergebnis``); sonst sagt der Satz,
    dass die Kodierer zu wenig übereinstimmen. Außerhalb der Stichprobe „explorativ". ``short`` ist
    die Fassung für die Downloads und den Dialog (eine Zeile unter 1 KB, Plan § 5): ohne Gewichtung
    und ohne die Übereinstimmung der Kodierer.
    """
    from georep.report.model import format_de

    rule = check.rule
    start = (
        "Die Klasse folgt aus dem Eintrag der Sitzungsleitung am Tagesordnungspunkt, nach einer "
        "vorab festgelegten Regel (die letzte Entscheidung in der Sache)"
        + ("; sie ist " if short else ". Diese Zuordnung ist ")
    )
    if not check.sufficient:
        checked = (
            f"{check.sentence}; die beiden stimmen zu wenig überein, darum steht hier keine Zahl "
            "zur Güte."
        )
    else:
        low, high = rule.interval
        hard_low, hard_high = rule.hard_interval
        checked = (
            f"{check.sentence}: bei {format_de(rule.hits)} von {format_de(rule.basis)} Anträgen "
            f"dieselbe Klasse wie bei den Kodierern ({'' if short else '95-%-Intervall nach Wilson '}"
            f"{format_de(low, 3)}–{format_de(high, 3)}"
        )
        if not short:
            checked += (
                f"; gewichtet nach Schicht {format_de(rule.weighted, 3)}, "
                f"{format_de(rule.weighted_interval[0], 3)}–{format_de(rule.weighted_interval[1], 3)}"
            )
        checked += (
            f"); nur {format_de(rule.hard_basis)} davon verlangten mehr als das Nachschlagen eines "
            "Eintrags"
        )
        if not short:
            checked += (
                f" ({format_de(rule.hard_hits)} von {format_de(rule.hard_basis)}, "
                f"{format_de(hard_low, 3)}–{format_de(hard_high, 3)})"
            )
            if check.agreed is not None and check.paired is not None and check.alpha is not None:
                checked += (
                    f". Die Kodierer stimmten untereinander in {format_de(check.agreed)} von "
                    f"{format_de(check.paired)} überein (α = {format_de(check.alpha, 2)})"
                )
            if check.same_model:
                checked += "; zwei Kodierer desselben Modells sind ein schwacher Beleg"
        checked += "."
    end = " Ob der Eintrag selbst stimmt, zeigt nur die Niederschrift" + (
        "." if short else ", und die liest dieser Datensatz nicht."
    )
    if not check.measured:
        end += " In diesem Datensatz explorativ" + (
            "." if short else f": gemessen ist an {'; '.join(check.measured_datasets)}."
        )
    return start + checked + end


def table_check_files(settings: Settings) -> tuple[Path, ...]:
    """``TableCheck.files`` der Downloads: dieselben Dateien wie der Prüfsatz der Seite."""
    return check_files(settings)


def table_sentence(settings: Settings) -> str:
    """``TableCheck.sentence`` von ``beschlusslage``, in der kurzen Fassung."""
    return check_sentence(read_check(settings), short=True)


# --- Wo es steht ---------------------------------------------------------------------------------
def outcomes_built(settings: Settings) -> bool:
    """Ob der Schritt ``outcomes`` gebaut wird: 26 an, dazu 14 und die Antragsteller von 15."""
    from georep.enrich.outcomes import outcomes_built as built

    return built(settings)


def _missing(settings: Settings) -> tuple[str, ...]:
    """Was in diesem Profil fehlt, in Sätzen (Plan § 6); leer, wenn alles gebaut wird."""
    if not settings.outcomes.enabled:
        return (
            "Beschlusslage, Erfolg je Fraktion und Antworten in der Sitzung: der Wortschatz, mit "
            "dem die Sitzungsleitung hier Ergebnisse einträgt, ist nicht gemessen, darum ist der "
            "Schritt in diesem Profil aus (outcomes.enabled).",
        )
    if not outcomes_built(settings):
        return (
            "Beschlusslage, Erfolg je Fraktion und Antworten in der Sitzung: sie brauchen die "
            "Rollen der Dokumente (Vorhaben 14) und die Antragsteller (Vorhaben 15), die in diesem "
            "Profil nicht laufen.",
        )
    return ()


# --- Abschnitt 1: Beschlusslage je Gremium ---------------------------------------------------------
@dataclass(frozen=True)
class Counts:
    """Anträge je Klasse; ``practice`` (Praxiszellen) zählt in keinem Anteil (§ 5)."""

    motions: int
    practice: int
    accepted: int  # beschlossen und geändert
    changed: int  # davon geändert
    rejected: int
    withdrawn: int
    done: int  # erledigt, ohne die Praxiszellen
    pending: int  # vertagt oder verwiesen
    missing: int  # ohne Ergebnis

    @property
    def counted(self) -> int:
        return self.motions - self.practice

    def share(self, n: int) -> float:
        return n / self.counted if self.counted else 0.0


def _counts_add_up(frame: pl.DataFrame, result: Counts | None = None) -> bool:
    assert result is not None
    parts = (
        result.accepted
        + result.rejected
        + result.withdrawn
        + result.done
        + result.pending
        + result.missing
    )
    return result.motions == frame.height and parts == result.counted >= 0


@deal.post(lambda result: result.changed <= result.accepted, message="geändert ist eine Unterzahl")
@deal.ensure(_counts_add_up, message="jeder Antrag in genau einer Spalte oder einer Praxiszelle")
def counts_of(frame: pl.DataFrame) -> Counts:
    """Die Zählung über Anträge mit ``klasse`` und ``eintrag_tragfaehig``."""
    practice = frame.get_column("eintrag_tragfaehig").not_().fill_null(False)
    klasse = frame.get_column("klasse")

    def n(*names: str) -> int:
        return int((klasse.is_in(list(names)) & ~practice).sum())

    return Counts(
        motions=frame.height,
        practice=int(practice.sum()),
        accepted=n("beschlossen", "geaendert"),
        changed=n("geaendert"),
        rejected=n("abgelehnt"),
        withdrawn=n("zurueckgezogen"),
        done=n("erledigt"),
        pending=n("vertagt", "offen"),
        missing=n("ohne_ergebnis"),
    )


@dataclass(frozen=True)
class Duration:
    """Tage vom Antrag bis zur Sitzung der Entscheidung: Zahl und Median ab ``MIN_DURATION``."""

    n: int
    median: float | None


def duration_of(days: pl.Series) -> Duration:
    valid = days.drop_nulls()
    if valid.len() < MIN_DURATION:
        return Duration(valid.len(), None)
    median = valid.median()
    assert isinstance(median, int | float)
    return Duration(valid.len(), float(median))


@dataclass(frozen=True)
class OutcomeRow:
    code: str
    name: str
    counts: Counts
    duration: Duration  # nur Anträge mit mehr als einer Beratung


@dataclass(frozen=True)
class PracticeCell:
    body: str
    year: int
    done: int
    motions: int


@dataclass(frozen=True)
class Session:
    """Die Sitzung, in der die meisten Anträge ohne Ergebnis auf der Tagesordnung stehen."""

    body: str
    day: dt.date
    motions: int


@dataclass(frozen=True)
class OutcomesModel:
    on: bool
    period: str
    check: OutcomesCheck | None
    total: Counts | None
    rows: tuple[OutcomeRow, ...]
    small_bodies: int
    small_motions: int
    single: Duration  # Anträge mit einer Beratung
    several: Duration  # mit mehr als einer
    session: Session | None
    cells: tuple[PracticeCell, ...]
    missing: tuple[str, ...]
    min_motions: int = MIN_MOTIONS
    min_duration: int = MIN_DURATION

    @property
    def explorative(self) -> bool:
        return self.check is not None and not self.check.measured


def code_names(settings: Settings, codes: Sequence[str | None]) -> dict[str, str]:
    """Je Kürzel des Beratungsverlaufs (mehrere mit „+") der Name wie auf ``akteure.html``.

    Eine Organisation ohne Kürzel im Profil (ihr Schlüssel steht da) heißt „Gremium unbekannt".
    """
    from georep.prep.bodies import DISTRICT_BODY, UNKNOWN, BodyRules, kind_of_code
    from georep.report.actors import body_name

    rules = BodyRules.from_settings(settings.bodies)

    def one(code: str) -> str:
        kind = kind_of_code(code, rules)
        if kind == UNKNOWN and not rules.names.get(code):
            return "Gremium unbekannt"
        district = (
            int(code[len(rules.district_body) :])
            if kind == DISTRICT_BODY and code[len(rules.district_body) :].isdigit()
            else None
        )
        return body_name({"gremium": code, "gremium_art": kind, "stadtbezirk": district}, rules)

    return {
        code: " und ".join(dict.fromkeys(one(part) for part in code.split("+")))
        for code in sorted({c for c in codes if c})
    }


def largest_session(
    motions: pl.DataFrame, progress: pl.DataFrame, names: Mapping[str, str]
) -> Session | None:
    """Die Sitzung mit den meisten Anträgen ohne Ergebnis, ab ``MIN_SESSION`` (§ 3.3)."""
    without = motions.filter(pl.col("klasse") == "ohne_ergebnis").select("id")
    found = (
        progress.filter(pl.col("top").is_not_null() & pl.col("sitzung").is_not_null())
        .join(without, on="id", how="semi")
        .group_by(pl.col("gremium"), pl.col("sitzung").dt.date().alias("tag"))
        .agg(pl.col("id").n_unique().alias("n"))
        .sort(["n", "tag", "gremium"], descending=[True, False, False], nulls_last=True)
    )
    if found.is_empty() or int(found.get_column("n")[0]) < MIN_SESSION:
        return None
    row = found.row(0, named=True)
    code = str(row["gremium"] or "")
    return Session(names.get(code, "Gremium unbekannt"), row["tag"], int(row["n"]))


def build_outcomes(
    outcomes: pl.DataFrame | None,
    progress: pl.DataFrame | None,
    bodies: pl.DataFrame | None,
    settings: Settings,
    check: OutcomesCheck | None,
) -> OutcomesModel:
    """Das Modell des ersten Abschnitts; ohne Tabellen sagt es nur, was fehlt.

    ``outcomes`` ist die Beschlusslage, ``progress`` der Beratungsverlauf, ``bodies`` das Gremium
    der Drucksache (``papers_gremien``). Die Zeilen gelten dem Gremium der Drucksache, wie bei den
    Anfragen von 14: auch ein Antrag ohne Ergebnis hat eines.
    """
    from georep.analysis.outcomes import practice_cells
    from georep.report.model import period_info
    from georep.report.procedures import body_names

    period = period_info(settings).title
    missing = _missing(settings)
    if outcomes is None or progress is None or bodies is None:
        none = Duration(0, None)
        return OutcomesModel(False, period, check, None, (), 0, 0, none, none, None, (), missing)
    motions = (
        outcomes.filter(pl.col("dokument_rolle") == MOTION)
        .join(bodies.select("id", "gremium"), on="id", how="left")
        .sort("id")
    )
    names = body_names(settings, bodies)
    rows: list[OutcomeRow] = []
    small = small_motions = 0
    for (code,), group in motions.group_by("gremium"):
        if group.height < MIN_MOTIONS:
            small += 1
            small_motions += group.height
            continue
        key = str(code or "")
        rows.append(
            OutcomeRow(
                key,
                names.get(key, key or "Gremium nicht erkannt"),
                counts_of(group),
                duration_of(group.filter(pl.col("beratungen") > 1).get_column("tage")),
            )
        )
    verlauf = code_names(settings, progress.get_column("gremium").to_list())
    cells = practice_cells(
        outcomes, settings.outcomes.practice_share, settings.outcomes.practice_min
    )
    return OutcomesModel(
        on=True,
        period=period,
        check=check,
        total=counts_of(motions),
        rows=tuple(sorted(rows, key=lambda r: (-r.counts.motions, r.name))),
        small_bodies=small,
        small_motions=small_motions,
        single=duration_of(motions.filter(pl.col("beratungen") == 1).get_column("tage")),
        several=duration_of(motions.filter(pl.col("beratungen") > 1).get_column("tage")),
        session=largest_session(motions, progress, verlauf),
        cells=tuple(
            PracticeCell(
                verlauf.get(str(r["gremium"] or ""), "Gremium unbekannt"),
                int(r["jahr"]),
                int(r["erledigt"]),
                int(r["n"]),
            )
            for r in cells.iter_rows(named=True)
        ),
        missing=missing,
    )


# --- Abschnitt 2: Erfolg je Fraktion (explorativ) -------------------------------------------------
@dataclass(frozen=True)
class SuccessRow:
    key: str
    label: str
    majority: bool
    motions: int  # Anträge mit Sachentscheidung
    # beobachtet und erwartet stehen nicht auf der Seite: mit n folgte daraus die rohe Quote
    observed: int
    expected: float
    ratio: float | None  # None unter ``MIN_SUCCESS`` oder ``MIN_EXPECTED``
    interval: tuple[float, float] | None


@dataclass(frozen=True)
class SuccessGroup:
    key: str
    label: str
    rows: tuple[SuccessRow, ...]
    majority_ratio: float | None  # die Fraktionen der Mehrheit zusammen, beobachtet durch erwartet
    others_ratio: float | None


@dataclass(frozen=True)
class SuccessModel:
    on: bool
    period: str
    check: OutcomesCheck | None
    groups: tuple[SuccessGroup, ...]
    elsewhere: tuple[tuple[str, int], ...]  # (Gremienart in Worten, Anträge), nicht in den Tabellen
    majority: tuple[str, ...]  # Namen der Fraktionen der Ratsmehrheit dieser Periode
    majority_since: dt.date | None
    split: tuple[tuple[str, str, dt.date], ...]  # (Partei allein, Fraktion, Beginn der Fraktion)
    min_success: int = MIN_SUCCESS
    min_expected: int = MIN_EXPECTED

    @property
    def explorative(self) -> bool:
        return self.check is not None and not self.check.measured


def majority_fractions(settings: Settings) -> tuple[tuple[str, ...], dt.date | None]:
    """Die Fraktionen der Ratsmehrheit, die den größten Teil dieser Periode gilt, und ihr Beginn.

    ``antragserfolg`` trägt kein Datum; eine Mehrheit, die nur die ersten Wochen einer Periode
    gilt (die alte bis zum Monat nach der Wahl), bestimmt darum keine Zeile.
    """
    from georep.analysis.cosponsors import fractions_on

    start = settings.period.start
    end = settings.period.end or dt.date.max

    def overlap(term_start: dt.date, term_end: dt.date | None) -> int:
        low, high = max(start, term_start), min(end, term_end or dt.date.max)
        return (high - low).days if high > low else 0

    terms = [(overlap(t.valid_from, t.valid_to), t) for t in settings.majorities.terms]
    held = [(days, term) for days, term in terms if days > 0]
    if not held:
        return (), None
    _, term = max(held, key=lambda item: (item[0], item[1].valid_from))
    keys = fractions_on(term.parties, term.valid_from, settings.functions.fractions, {})
    return tuple(keys), term.valid_from


def _ratio(observed: int, expected: float) -> float | None:
    return observed / expected if expected > 0 else None


def success_rows(
    success: pl.DataFrame, kinds: Sequence[str], labels: Mapping[str, str], majority: Sequence[str]
) -> tuple[SuccessRow, ...]:
    """Je Fraktion über die Gremienarten ``kinds``: Σ n, Σ beobachtet, Σ erwartet, nach Namen.

    Die Summe ist die indirekte Standardisierung über die Vereinigung der Schichten (je Gremium):
    beobachtet und erwartet addieren sich, ihr Verhältnis ist das der Gruppe.
    """
    from georep.report.procedures import poisson_ratio_interval

    grouped = (
        success.filter(pl.col("gremium_art").is_in(list(kinds)))
        .group_by("fraktion")
        .agg(pl.col("n").sum(), pl.col("angenommen").sum(), pl.col("erwartet").sum())
    )
    rows = []
    for key, n, observed, expected in grouped.select(
        "fraktion", "n", "angenommen", "erwartet"
    ).iter_rows():
        shown = n >= MIN_SUCCESS and expected >= MIN_EXPECTED
        rows.append(
            SuccessRow(
                key=str(key),
                label=labels.get(str(key), str(key)),
                majority=str(key) in majority,
                motions=int(n),
                observed=int(observed),
                expected=float(expected),
                ratio=_ratio(int(observed), float(expected)) if shown else None,
                interval=poisson_ratio_interval(int(observed), float(expected)) if shown else None,
            )
        )
    return tuple(sorted(rows, key=lambda r: (r.label.casefold(), r.key)))


def build_success(
    success: pl.DataFrame | None, settings: Settings, check: OutcomesCheck | None
) -> SuccessModel:
    """Das Modell des zweiten Abschnitts; ohne Tabelle (Schritt aus) ``on`` falsch."""
    from georep.report.actors import labels_of
    from georep.report.model import period_info

    period = period_info(settings).title
    labels, _ = labels_of(settings)
    keys, since = majority_fractions(settings)
    if success is None:
        return SuccessModel(False, period, check, (), (), (), None, ())
    groups = []
    for key, label, kinds in GROUPS:
        rows = success_rows(success, kinds, labels, keys)
        inside = [r for r in rows if r.majority]
        outside = [r for r in rows if not r.majority]
        groups.append(
            SuccessGroup(
                key,
                label,
                rows,
                _ratio(sum(r.observed for r in inside), sum(r.expected for r in inside)),
                _ratio(sum(r.observed for r in outside), sum(r.expected for r in outside)),
            )
        )
    grouped = {kind for _, _, kinds in GROUPS for kind in kinds}
    other = (
        success.filter(~pl.col("gremium_art").is_in(sorted(grouped)))
        .group_by("gremium_art")
        .agg(pl.col("n").sum())
        .sort("gremium_art")
    )
    present = set(success.get_column("fraktion").to_list())
    split = tuple(
        (labels.get(party, party), labels.get(f.key, f.key), f.valid_from)
        for f in settings.functions.fractions
        if f.key in present
        for party in f.parties
        if party in present
    )
    return SuccessModel(
        on=True,
        period=period,
        check=check,
        groups=tuple(groups),
        elsewhere=tuple(
            (KIND_PLURAL.get(str(kind), str(kind)), int(n)) for kind, n in other.iter_rows()
        ),
        majority=tuple(labels.get(k, k) for k in keys),
        majority_since=since,
        split=split,
    )


# --- Abschnitt 3: In der Sitzung beantwortet -------------------------------------------------------
@dataclass(frozen=True)
class SessionRow:
    code: str
    name: str
    questions: int
    attached: int  # Antwort im System nach 14 (Anlage oder Drucksache)
    answered: int  # der maßgebliche Eintrag trägt eine Antwort
    written: int  # davon schriftlich
    neither: int  # weder Antwort im System noch ein solcher Eintrag

    def share(self, n: int) -> float:
        return n / self.questions if self.questions else 0.0


@dataclass(frozen=True)
class SessionModel:
    on: bool
    total: SessionRow | None
    rows: tuple[SessionRow, ...]
    small_bodies: int
    small_questions: int
    words: tuple[str, ...]  # ``outcomes.answered``, wörtlich
    written_words: tuple[str, ...]
    missing: tuple[str, ...]
    min_questions: int = MIN_QUESTIONS


def _session_row(code: str, name: str, group: pl.DataFrame) -> SessionRow:
    attached = group.get_column("quelle") != NO_ANSWER
    answered = group.get_column("beantwortet")
    return SessionRow(
        code=code,
        name=name,
        questions=group.height,
        attached=int(attached.sum()),
        answered=int(answered.sum()),
        written=int(group.get_column("schriftlich").sum()),
        neither=int((~attached & ~answered).sum()),
    )


def build_session(
    answers: pl.DataFrame | None,
    outcomes: pl.DataFrame | None,
    bodies: pl.DataFrame | None,
    settings: Settings,
) -> SessionModel:
    """Das Modell des dritten Abschnitts aus ``antwortzeiten`` (14) und der Beschlusslage.

    Dieselben Zeilen wie die Antworten je Gremium bei 14: das Gremium der Anfrage aus
    ``antwortzeiten``, ab ``MIN_QUESTIONS`` Anfragen. „Beantwortet" ist der Wortlaut des
    maßgeblichen Eintrags (``outcomes.answered``), keine geprüfte Klasse.
    """
    from georep.report.procedures import body_names

    words = tuple(settings.outcomes.answered)
    written = tuple(settings.outcomes.answered_written)
    missing: list[str] = []
    if answers is None or outcomes is None or bodies is None:
        return SessionModel(False, None, (), 0, 0, words, written, ())
    if not words:
        missing.append(
            "Antworten in der Sitzung: das Profil nennt keinen Eintrag, mit dem die "
            "Sitzungsleitung eine Antwort einträgt (outcomes.answered)."
        )
    if answers.is_empty():
        missing.append("Antworten in der Sitzung: dieser Datensatz hat keine Anfragen.")
    if missing:
        return SessionModel(False, None, (), 0, 0, words, written, tuple(missing))
    joined = (
        answers.select("id", "gremium", "quelle")
        .join(outcomes.select("id", "result"), on="id", how="left")
        .with_columns(
            pl.col("result").is_in(list(words)).fill_null(False).alias("beantwortet"),
            pl.col("result").is_in(list(written)).fill_null(False).alias("schriftlich"),
        )
        .sort("id")
    )
    names = body_names(settings, bodies)
    rows = []
    small = small_questions = 0
    for (code,), group in joined.group_by("gremium"):
        if group.height < MIN_QUESTIONS:
            small += 1
            small_questions += group.height
            continue
        key = str(code or "")
        rows.append(_session_row(key, names.get(key, key or "Gremium nicht erkannt"), group))
    return SessionModel(
        on=True,
        total=_session_row("", "alle Gremien", joined),
        rows=tuple(sorted(rows, key=lambda r: (-r.questions, r.name))),
        small_bodies=small,
        small_questions=small_questions,
        words=words,
        written_words=written,
        missing=(),
    )


# --- Eingaben und Daten der drei Gäste -----------------------------------------------------------
def _outcome_tables(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Beschlusslage und Beratungsverlauf, wenn der Schritt ``outcomes`` hier gebaut wird."""
    from georep.enrich.outcomes import outcome_files

    if not outcomes_built(settings):
        return ()
    files = outcome_files(layout)
    return (files.outcomes, files.progress)


def outcomes_section_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """``PageSection.inputs`` des ersten Gasts; die Prüfung nur, wo der Schritt gebaut wird."""
    tables = _outcome_tables(layout, settings)
    if not tables:
        return ()
    return (*tables, layout.papers_bodies, *check_files(settings))


def outcomes_section_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    """``PageSection.data``: der Schlüssel ``beschlusslage`` steht immer da (Punkt 86, N5)."""
    tables = _outcome_tables(layout, settings)
    check = read_check(settings) if tables else None
    if tables:
        outcomes, progress = (pl.read_parquet(path) for path in tables)
        bodies = pl.read_parquet(
            layout.papers_bodies, columns=["id", "gremium", "gremium_art", "stadtbezirk"]
        )
        model = build_outcomes(outcomes, progress, bodies, settings, check)
    else:
        model = build_outcomes(None, None, None, settings, None)
    return {
        "beschlusslage": model,
        "urls": repository_links(settings),
        "check_sentence": check_sentence(check) if check is not None else "",
    }


def success_section_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    from georep.enrich.outcomes import outcome_files

    if not outcomes_built(settings):
        return ()
    return (outcome_files(layout).success, *check_files(settings))


def success_section_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    """``PageSection.data``: ``antragserfolg`` immer, ohne Schritt mit ``on`` falsch."""
    from georep.enrich.outcomes import outcome_files

    if outcomes_built(settings):
        success = pl.read_parquet(outcome_files(layout).success)
        model = build_success(success, settings, read_check(settings))
    else:
        model = build_success(None, settings, None)
    return {"antragserfolg": model}


def session_section_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    from georep.enrich.outcomes import outcome_files
    from georep.enrich.procedures import procedure_files

    if not outcomes_built(settings):
        return ()
    return (
        outcome_files(layout).outcomes,
        procedure_files(layout).answers,
        layout.papers_bodies,
    )


def session_section_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    """``PageSection.data``: ``sitzung`` immer, ohne Schritt mit ``on`` falsch."""
    from georep.enrich.outcomes import outcome_files
    from georep.enrich.procedures import procedure_files

    if outcomes_built(settings):
        model = build_session(
            pl.read_parquet(procedure_files(layout).answers),
            pl.read_parquet(outcome_files(layout).outcomes, columns=["id", "result"]),
            pl.read_parquet(
                layout.papers_bodies, columns=["id", "gremium", "gremium_art", "stadtbezirk"]
            ),
            settings,
        )
    else:
        model = build_session(None, None, None, settings)
    return {"sitzung": model}


def repository_links(settings: Settings) -> dict[str, str]:
    """Messdokument und README der Prüfung im Repository."""
    from georep.report.render import REPOSITORY

    folder = settings.validation.root.name
    return {
        "measurement": f"{REPOSITORY}/blob/main/{MEASUREMENT}",
        "check": f"{REPOSITORY}/blob/main/{folder}/{VALIDATION_PROJECT}/README.md",
        "check_folder": f"{folder}/{VALIDATION_PROJECT}",
    }


def section_links(layout: Layout, settings: Settings) -> frozenset[str]:
    """Die Links nach außen des ersten Gasts: Messdokument und Prüfung."""
    links = repository_links(settings)
    return frozenset(v for k, v in links.items() if k != "check_folder")


# --- Der Haken im Dokumentdialog ------------------------------------------------------------------
def outcome_label(
    klasse: str, body: str | None, day: dt.date | None, *, practice: bool = False
) -> str:
    """„angenommen (Rat, 12.03.2024)": Klasse in Worten, Gremium und Tag, wo es sie gibt."""
    from georep.report.render import date_de

    word = PRACTICE_WORD if practice else CLASS_WORDS[klasse]
    where = [part for part in (body, date_de(day) if day else None) if part]
    return f"{word} ({', '.join(where)})" if where else word


def _rows_are_motions(layout: Layout, settings: Settings, result: DialogRows | None = None) -> bool:
    assert result is not None
    return all(len(entries) == 1 and entries[0][1] is None for entries in result.rows.values())


def dialog_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Was ``report`` für ``data/beschluesse.json`` liest: die Beschlusslage und die Prüfung."""
    from georep.enrich.outcomes import outcome_files

    return (outcome_files(layout).outcomes, *check_files(settings))


def dialog_note(check: OutcomesCheck) -> str:
    """Der Satz unter der Liste des Dialogs."""
    return f"{DIALOG_TITLE} der Anträge: {check_sentence(check, short=True)}"


@deal.ensure(_rows_are_motions, message="je Antrag genau ein Eintrag, ein Wort ohne Ziel")
def dialog_rows(layout: Layout, settings: Settings) -> DialogRows:
    """``DialogHook.rows``: je Antrag ein Wort mit Klasse, Gremium und Tag der Entscheidung.

    Nur Anträge (validiert sind nur sie, Frage 9.9); jedes andere Dokument bekommt keine Zeile. Ein
    Antrag ohne Ergebnis sagt das; einer in einer Praxiszelle sagt, dass sein Eintrag keine
    Aussage trägt (§ 5). Die Wörter stehen je einmal in ``labels``.
    """
    from georep.enrich.outcomes import outcome_files

    motions = (
        pl.read_parquet(
            outcome_files(layout).outcomes,
            columns=[
                "id",
                "dokument_rolle",
                "klasse",
                "entscheidung_gremium",
                "entscheidung_datum",
                "eintrag_tragfaehig",
            ],
        )
        .filter(pl.col("dokument_rolle") == MOTION)
        .sort("id")
    )
    names = code_names(settings, motions.get_column("entscheidung_gremium").to_list())
    labels: dict[str, int] = {}
    rows: dict[str, tuple[tuple[int, str | None], ...]] = {}
    for doc_id, klasse, body, day, carries in motions.select(
        "id", "klasse", "entscheidung_gremium", "entscheidung_datum", "eintrag_tragfaehig"
    ).iter_rows():
        label = outcome_label(
            str(klasse), names.get(str(body or "")), day, practice=carries is False
        )
        rows[str(doc_id)] = ((labels.setdefault(label, len(labels)), None),)
    return DialogRows(
        labels=tuple(labels),
        rows=rows,
        note=dialog_note(read_check(settings)) if rows else "",
    )
