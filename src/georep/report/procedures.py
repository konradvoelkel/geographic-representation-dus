"""Die Unterseite ``vorgaenge.html`` und der Vorgang im Dokumentdialog (Vorhaben 14, Stufe 3).

Stufe 3 von Vorhaben 14 (Messdokument ``docs/plans/14-vorgaenge.md``, § 7 und § 10) im Muster von
``akteure.html`` (Punkt 88). Vier Abschnitte:

1. *Antworten je Gremium*: Anfragen, „Antwort im Ratsinformationssystem gefunden", Median und Q3
   der Antwortzeit (nur gültig datiert, n daneben), eine Zeile je Gremium mit mindestens
   ``MIN_QUESTIONS`` Anfragen. Ein fehlender Anhang ist keine fehlende Antwort: für Gremien unter
   ``SESSION_PRACTICE`` steht der Hinweis auf die Niederschrift, bis Vorhaben 26 ihn ersetzt (der
   Gast ``SESSION_GUEST``, Punkt 86).
2. *Je Fraktion*, „explorativ" in jedem Datensatz (Frage 14): beobachtet gegen erwartet gegen die
   Praxis der Gremien (``analysis.practice``), daneben der Median der Antwortzeit ab
   ``MIN_DATED`` datierten Antworten; keine rohe Quote, keine Rangfolge nach einer rohen Zahl.
3. *Ohne gefundene Antwort*: nur in Gremien mit einer Praxis ab ``CANDIDATE_PRACTICE`` und älter
   als P90 der Antwortzeit beim Abruf, als „Kandidaten" benannt.
4. *Vorgänge*: Zahl und Größen nach der Rückfallregel, die Typen der starken Kanten, warum
   Textverweise nicht zählen.

Dazu der Haken im Dokumentdialog (``report.dialog``, Vorarbeit V2): je Dokument seine starken
Nachbarn mit Rolle, in ``data/vorgaenge.json`` (``dialog_rows``). Keine Textverweise, auch nicht als
„ungeprüft" (Messdokument § 5.1); ``bezug`` höchstens ``MAX_RELATED`` je Dokument (Frage 9.7).

Die Prüfung kommt aus drei ``guete.json`` (F4, Punkt 87): die Prüfstichprobe der Rückfallregel
(``14-vorgaenge-3-f4``) trägt die Kennzahl, gemessen an der Hauptperiode; die beiden ersten
Stichproben (``14-vorgaenge-f4``, ``14-vorgaenge-2-f4``) sagen, warum Nummern nur im Text nicht
zählen. Ein Datensatz außerhalb der Prüfstichprobe heißt in jeder Überschrift „explorativ".

Rein bis auf ``procedures_data``, ``dialog_rows`` und ``read_check``, die Dateien lesen; kein
Stadtwort, keine Partei im Code: Gremien und Fraktionen kommen aus den Settings.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import deal
import polars as pl

from georep.analysis.practice import EXPECTED, OBSERVED, RATIO, observed_expected
from georep.analysis.procedures import ATTACHMENT_SCHEMA, SOURCES
from georep.errors import MissingInputError, SchemaError
from georep.layout import Layout
from georep.prep.references import EDGE_TYPES, ReferenceRules, is_answer_attachment
from georep.report.dialog import DialogRows, DialogTarget
from georep.settings import Settings, load_settings, profile_folder

PAGE_NAME = "vorgaenge"
# Die drei Messungen unter ``validation.root`` (F4): die Kennzahl, dann die beiden Fassungen davor.
RULE_PROJECT = "14-vorgaenge-3-f4"  # Prüfstichprobe der Rückfallregel (Frage 9.18), Hauptperiode
FIRST_PROJECT = "14-vorgaenge-f4"  # Stichprobe 1: Regelfassung .1, mit Textverweisen
SECOND_PROJECT = "14-vorgaenge-2-f4"  # Bestätigung: Regelfassung .2, mit Textverweisen
CRITERION = (
    0.95  # vorab festgelegte Kantenpräzision (Messdokument § 3, § 5): keine Messung, eine Zusage
)
MIN_QUESTIONS = (
    30  # eine Zeile je Gremium und ein Verhältnis je Fraktion ab so vielen Anfragen (§ 7)
)
MIN_DATED = 30  # ein Median der Antwortzeit ab so vielen datierten Antworten (§ 7)
# Ein Verhältnis erst ab so vielen erwarteten Antworten: fragt eine Fraktion fast nur in Gremien,
# die in der Sitzung antworten, sind beobachtet und erwartet kleine Zahlen, und ihr Verhältnis
# schwankt mit einer einzigen Antwort (Hauptperiode: 129 Anfragen, rund zwei erwartet, 1,45).
MIN_EXPECTED = 10
SESSION_PRACTICE = 0.2  # darunter antwortet das Gremium in der Sitzung (§ 7, Abschnitt 1)
CANDIDATE_PRACTICE = (
    0.7  # Kandidaten nur aus Gremien mit mindestens dieser Praxis (§ 7, Abschnitt 3)
)
MAX_RELATED = 5  # Frage 9.7: höchstens so viele ``bezug`` je Dokument im Dialog
# Der Titel eines Ziels außerhalb von ``dokumente.json`` steht nur als title am Link; gekürzt hält
# er ``vorgaenge.json`` unter dem Budget von 100 KB (Messdokument § 7).
TITLE_CHARS = 100
SESSION_GUEST = (
    "in-der-sitzung"  # der Abschnitt von 26, der den Hinweis auf die Niederschrift ersetzt
)
NO_ANSWER = "keine"
MEASUREMENT = "docs/plans/14-vorgaenge.md"  # Messdokument, relativ zum Repository

# Die Fundstellen der Rückfallregel in Worten (``analysis.procedures.SOURCES``), stärkste zuerst.
SOURCE_LABELS: dict[str, str] = {
    "titel": "Titel",
    "nummer": "Nachtragsnummer",
    "anlage": "Anlagenname",
    "sammelbericht": "Sammelbericht",
    "text": "nur im Text",
}
# Die Kantentypen .2 in Worten (``prep.references.EDGE_TYPES``): was B, die nennende Drucksache, zu A ist.
TYPE_LABELS: dict[str, str] = {
    "antwort": "Antwort auf eine Anfrage",
    "kontrolle": "Sammelbericht nennt die Drucksache",
    "nachfrage": "Nachfrage",
    "umsetzung": "Umsetzung eines Antrags oder einer Eingabe",
    "aenderung": "Änderungs- oder Ergänzungsantrag",
    "fortsetzung": "Fortsetzung",
    "bau": "Ausführungs- zu Bedarfsbeschluss",
    "nachtrag": "Nachtrag",
    "bezug": "Bezug ohne Typ",
}
# Im Dialog je Typ zwei Wörter: bei B, das A nennt, und bei A, das B nennt. Folge der Einträge.
OUT, IN = "nennt", "genannt"
DIALOG_LABELS: dict[tuple[str, str], str] = {
    ("antwort", OUT): "Antwort auf",
    ("antwort", IN): "beantwortet in",
    ("nachfrage", OUT): "Nachfrage zu",
    ("nachfrage", IN): "nachgefragt in",
    ("umsetzung", OUT): "Umsetzung von",
    ("umsetzung", IN): "umgesetzt in",
    ("aenderung", OUT): "Änderung zu",
    ("aenderung", IN): "geändert durch",
    ("nachtrag", OUT): "Nachtrag zu",
    ("nachtrag", IN): "Nachtrag",
    ("fortsetzung", OUT): "Fortsetzung von",
    ("fortsetzung", IN): "fortgesetzt in",
    ("bau", OUT): "Ausführung zu",
    ("bau", IN): "ausgeführt in",
    ("kontrolle", OUT): "berichtet über",
    ("kontrolle", IN): "genannt im Sammelbericht",
    ("bezug", OUT): "nennt",
    ("bezug", IN): "genannt in",
}
DIALOG_TITLE = "Vorgang"


# --- Die Prüfung (F4, Punkt 87) --------------------------------------------------------------------
@dataclass(frozen=True)
class Measurement:
    """Die Kantenpräzision einer Stichprobe aus ``guete.json`` (Frage ``selbe_sache``)."""

    project: str
    sentence: str  # ``satz``: Modelle, Einheiten, „nicht von Menschen"
    hits: int
    judged: int
    interval: tuple[float, float]  # Wilson 95 %, ungewichtet
    weighted: float  # für die Grundgesamtheit, mit den Schichtgrößen gewichtet
    weighted_interval: tuple[float, float]  # Wilson bei Kishs effektivem n
    population: int
    strata: tuple[tuple[str, int], ...]  # (Schicht, gewertet), absteigend
    same_model: bool  # Kodierer A und B dasselbe Modell

    @property
    def share(self) -> float:
        return self.hits / self.judged if self.judged else 0.0


@dataclass(frozen=True)
class Check:
    """Der Prüfsatz der Seite: die Rückfallregel und die beiden Fassungen davor."""

    rule: Measurement
    first: Measurement
    second: Measurement
    criterion: float
    measured: bool  # dieser Datensatz gehört zur Prüfstichprobe; sonst ist die Seite explorativ
    measured_datasets: tuple[str, ...]  # Stadt und Periode der Prüfstichprobe


def check_files(settings: Settings) -> tuple[Path, ...]:
    """Die drei ``guete.json`` und ``stichprobe.json`` der Prüfstichprobe im Repo."""
    root = settings.validation.root
    return (
        root / RULE_PROJECT / "guete.json",
        root / RULE_PROJECT / "stichprobe.json",
        root / FIRST_PROJECT / "guete.json",
        root / SECOND_PROJECT / "guete.json",
    )


def _measurement(path: Path, project: str) -> Measurement:
    quality: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    try:
        hits = dict(quality["fragen"]["selbe_sache"]["treffer"])
        sample, population = dict(hits["stichprobe"]), dict(hits["grundgesamtheit"])
        strata = sorted(
            ((str(k), int(v["gewertet"])) for k, v in dict(hits["je_schicht"]).items()),
            key=lambda item: (-item[1], item[0]),
        )
        models = dict(quality["modelle"])
        low, high = (float(x) for x in sample["wilson95"])
        w_low, w_high = (float(x) for x in population["wilson95_kish"])
        return Measurement(
            project=project,
            sentence=str(quality["satz"]),
            hits=int(sample["treffer"]),
            judged=int(sample["gewertet"]),
            interval=(low, high),
            weighted=float(population["schaetzer"]),
            weighted_interval=(w_low, w_high),
            population=int(population["n"]),
            strata=tuple(strata),
            same_model=models.get("kodierer_a") == models.get("kodierer_b"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SchemaError(f"{path}: Feld fehlt ({error})") from error


def _dataset_name(profile: str) -> str:
    """„Stadt, Wahlperiode …" eines Paketprofils; ein unbekanntes bleibt sein Name."""
    from georep.report.model import period_info

    try:
        settings = load_settings(profile=profile, cwd=Path("/nonexistent"))
    except OSError, ValueError, SchemaError:
        return profile
    return f"{settings.city.name}, {period_info(settings).title}"


def _folder(profile: str) -> str | None:
    try:
        return profile_folder(profile)
    except OSError, ValueError, SchemaError:
        return None


@deal.raises(MissingInputError, SchemaError)
def read_check(settings: Settings) -> Check:
    """Der Prüfsatz aus den drei ``guete.json``; gemessen ist der Ordner der Prüfstichprobe."""
    rule_path, sample_path, first_path, second_path = check_files(settings)
    for path in (rule_path, sample_path, first_path, second_path):
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; die Seite {PAGE_NAME}.html nennt ihre Prüfung")
    sample: dict[str, Any] = json.loads(sample_path.read_text(encoding="utf-8"))
    try:
        profiles = tuple(p.strip() for p in str(sample["profil"]).split(",") if p.strip())
    except KeyError as error:
        raise SchemaError(f"{sample_path}: Feld fehlt ({error})") from error
    folders = {f for f in (_folder(p) for p in profiles) if f is not None}
    return Check(
        rule=_measurement(rule_path, RULE_PROJECT),
        first=_measurement(first_path, FIRST_PROJECT),
        second=_measurement(second_path, SECOND_PROJECT),
        criterion=CRITERION,
        measured=settings.profile in folders,
        measured_datasets=tuple(_dataset_name(p) for p in profiles),
    )


# --- Abschnitt 1: Antworten je Gremium -------------------------------------------------------------
@dataclass(frozen=True)
class Times:
    """Antwortzeiten in Tagen, nur gültig datiert: n, Median, Q1, Q3, P90 (None ohne Antwort)."""

    dated: int
    median: float | None
    q1: float | None
    q3: float | None
    p90: float | None


def answer_times_of(days: pl.Series) -> Times:
    """Median und Quartile über die Tage; ``nearest`` wie in der Messung (§ 3.7)."""
    valid = days.drop_nulls()
    if valid.is_empty():
        return Times(0, None, None, None, None)

    def quantile(q: float) -> float:
        value = valid.quantile(q, interpolation="nearest")
        assert value is not None
        return float(value)

    median = valid.median()
    assert isinstance(median, int | float)
    return Times(valid.len(), float(median), quantile(0.25), quantile(0.75), quantile(0.9))


def at_least(times: Times, minimum: int) -> Times:
    """Die Zahl der datierten Antworten bleibt, Median und Quartile erst ab ``minimum`` (Review K1).

    Dieselbe Regel je Gremium und je Fraktion: an drei Antworten ist ein Median kein Befund.
    """
    return times if times.dated >= minimum else Times(times.dated, None, None, None, None)


@dataclass(frozen=True)
class BodyRow:
    code: str
    name: str
    questions: int
    answered: int
    times: Times

    @property
    def share(self) -> float:
        return self.answered / self.questions if self.questions else 0.0

    @property
    def in_session(self) -> bool:
        """Unter ``SESSION_PRACTICE``: das Gremium antwortet in der Sitzung, nicht als Anlage."""
        return self.share < SESSION_PRACTICE


@dataclass(frozen=True)
class Answers:
    """Was die Anfragen dieses Datensatzes im Ratsinformationssystem als Antwort haben."""

    questions: int
    answered: int
    by_attachment: int  # mit Antwortanlage (auch mit eigener Drucksache)
    by_paper_only: int  # nur über eine Informationsvorlage, die die Anfrage im Titel nennt
    undated: int  # mit Antwort, aber ohne gültiges Datum (Umstellungstag)
    times: Times
    bodies: tuple[BodyRow, ...]  # Gremien ab ``MIN_QUESTIONS``, nach Anfragen absteigend
    small_bodies: int  # die übrigen Gremien
    small_questions: int
    names: int  # verschiedene Namen von Antwortanlagen an den Anfragen
    invalid_dates: tuple[dt.date, ...]
    young: int  # ohne Antwort und beim Abruf höchstens P90 alt

    @property
    def share(self) -> float:
        return self.answered / self.questions if self.questions else 0.0

    @property
    def session_bodies(self) -> tuple[BodyRow, ...]:
        return tuple(b for b in self.bodies if b.in_session)


def body_rows(
    answers: pl.DataFrame, names: Mapping[str, str]
) -> tuple[tuple[BodyRow, ...], int, int]:
    """Je Gremium ab ``MIN_QUESTIONS`` eine Zeile; dazu Zahl und Anfragen der übrigen."""
    rows = []
    small = small_questions = 0
    for code, group in answers.group_by("gremium", maintain_order=True):
        key = str(code[0] or "")
        n = group.height
        if n < MIN_QUESTIONS:
            small += 1
            small_questions += n
            continue
        answered = int((group.get_column("quelle") != NO_ANSWER).sum())
        rows.append(
            BodyRow(
                key,
                names.get(key, key or "Gremium nicht erkannt"),
                n,
                answered,
                at_least(answer_times_of(group.get_column("tage")), MIN_DATED),
            )
        )
    return tuple(sorted(rows, key=lambda r: (-r.questions, r.name))), small, small_questions


def answer_names(answers: pl.DataFrame, attachments: pl.DataFrame, rules: ReferenceRules) -> int:
    """Wie viele verschiedene Anlagennamen an den Anfragen die Namensregel als Antwort liest."""
    questions = set(answers.get_column("id").to_list())
    found = {
        str(item["name"])
        for doc_id, files in attachments.select("id", "anlagen").iter_rows()
        if doc_id in questions
        for item in files or []
        if is_answer_attachment(item["name"], rules)
    }
    return len(found)


# --- Abschnitt 2: je Fraktion (explorativ) -------------------------------------------------------
@dataclass(frozen=True)
class FractionRow:
    key: str
    label: str
    questions: int
    answered: int  # beobachtet
    expected: float
    # beobachtet durch erwartet; None unter ``MIN_QUESTIONS`` oder ``MIN_EXPECTED``
    ratio: float | None
    times: Times  # Median erst ab ``MIN_DATED``


def fraction_rows(questions: pl.DataFrame, labels: Mapping[str, str]) -> tuple[FractionRow, ...]:
    """Je Fraktion ihre Anfragen gegen die Praxis der Gremien (explorativ, Frage 14).

    ``questions`` trägt je Anfrage ``fraktionen`` (Liste, aus Vorhaben 15), ``quelle``, ``tage``
    und ``gremium``. Erwartet ist die Summe der Antwortanteile der Gremien über die Anfragen der
    Fraktion (``observed_expected``, Schicht das Gremium); eine gemeinsame Anfrage zählt für jede.
    Sortiert nach Anfragen absteigend, dann nach Bezeichnung: dieselbe Regel für jede Fraktion.
    """
    if questions.is_empty():
        return ()
    frame = questions.with_columns(
        (pl.col("quelle") != NO_ANSWER).alias("beantwortet"), pl.col("gremium").fill_null("")
    )
    ratios = observed_expected(
        frame.select("fraktionen", "beantwortet", "gremium"),
        unit="fraktionen",
        outcome="beantwortet",
        strata=("gremium",),
    )
    exploded = frame.select("fraktionen", "tage").explode("fraktionen").drop_nulls("fraktionen")
    rows = []
    for key, n, observed, expected, ratio in ratios.select(
        "fraktionen", "n", OBSERVED, EXPECTED, RATIO
    ).iter_rows():
        days = exploded.filter(pl.col("fraktionen") == key).get_column("tage")
        times = answer_times_of(days)
        times = at_least(times, MIN_DATED)
        rows.append(
            FractionRow(
                key=str(key),
                label=labels.get(str(key), str(key)),
                questions=int(n),
                answered=int(observed),
                expected=float(expected),
                ratio=(
                    float(ratio)
                    if ratio is not None and int(n) >= MIN_QUESTIONS and expected >= MIN_EXPECTED
                    else None
                ),
                times=times,
            )
        )
    return tuple(sorted(rows, key=lambda r: (-r.questions, r.label)))


@dataclass(frozen=True)
class SplitFraction:
    """Eine Partei allein neben der Fraktion, zu der sie erst ab einem Tag gehört (wie akteure.html)."""

    alone: str
    joint: str
    since: dt.date


def split_fractions(
    questions: pl.DataFrame, rows: Sequence[FractionRow], settings: Settings
) -> tuple[SplitFraction, ...]:
    """Je Fraktion aus mehreren Parteien, deren Partei allein eine Zeile hat, die ganz davor liegt.

    Nur dann ist der Satz wahr, dass die Anfragen der Partei allein von der Fraktion des Rates
    davor stammen; ``questions`` trägt ``fraktionen`` und ``date``.
    """
    by_key = {r.key: r for r in rows}
    found = []
    for fraction in settings.functions.fractions:
        if fraction.key not in by_key:
            continue
        for party in fraction.parties:
            if party not in by_key:
                continue
            latest = (
                questions.filter(pl.col("fraktionen").list.contains(party))
                .get_column("date")
                .drop_nulls()
                .max()
            )
            if isinstance(latest, dt.date) and latest < fraction.valid_from:
                found.append(
                    SplitFraction(
                        by_key[party].label, by_key[fraction.key].label, fraction.valid_from
                    )
                )
    return tuple(found)


# --- Abschnitt 3: Kandidaten ---------------------------------------------------------------------
@dataclass(frozen=True)
class Candidate:
    reference: str
    url: str
    date: dt.date | None
    body: str
    authors: str
    age: int  # Tage beim Abruf


def _https(url: str | None) -> str:
    if not url:
        return ""
    return "https://" + url[len("http://") :] if url.startswith("http://") else url


# --- Abschnitt 4: Vorgänge -----------------------------------------------------------------------
@dataclass(frozen=True)
class Procedures:
    documents: int  # Korpus
    procedures: int  # Vorgänge mit mindestens zwei Dokumenten, die ein eigenes Dokument tragen
    members: int  # eigene Dokumente darin
    sizes: tuple[tuple[int, int], ...]  # (Größe, Vorgänge), aufsteigend
    across: int  # Vorgänge, deren Wurzel in einer Nachbarperiode liegt
    edges: int
    strong: int
    weak: int  # nur im Text: in den Daten, nicht im Vorgang
    strong_across: int  # starke Kanten in eine Nachbarperiode
    by_type: tuple[tuple[str, str, int], ...]  # (Typ, Wort, starke Kanten), nach Zahl absteigend
    by_source: tuple[
        tuple[str, str, int], ...
    ]  # (Fundstelle, Wort, starke Kanten), Folge der Regel

    @property
    def largest(self) -> int:
        return max((size for size, _ in self.sizes), default=0)

    @property
    def pairs(self) -> int:
        return dict(self.sizes).get(2, 0)

    @property
    def top(self) -> int:
        """Die häufigste Größe: die Länge des längsten Balkens."""
        return max((n for _, n in self.sizes), default=0)


def procedure_summary(
    forest: pl.DataFrame, edges: pl.DataFrame, own_ids: Sequence[str]
) -> Procedures:
    """Die Vorgänge aus ``dokumente_vorgang`` und die Kanten aus ``vorgang_kanten`` dieses Datensatzes."""
    grouped = forest.filter(pl.col("groesse") > 1)
    per = grouped.select("vorgang", "groesse").unique()
    sizes = Counter(int(size) for size in per.get_column("groesse").to_list())
    own = set(own_ids)
    strong = edges.filter("stark")
    types = Counter(str(t) for t in strong.get_column("typ").to_list())
    sources = Counter(str(s) for s in strong.get_column("quelle").to_list())
    return Procedures(
        documents=forest.height,
        procedures=per.height,
        members=grouped.height,
        sizes=tuple(sorted(sizes.items())),
        across=int(sum(1 for v in per.get_column("vorgang").to_list() if v not in own)),
        edges=edges.height,
        strong=strong.height,
        weak=edges.height - strong.height,
        strong_across=int((strong.get_column("nach_periode") != "").sum()),
        by_type=tuple(
            (t, TYPE_LABELS[t], types[t])
            for t in sorted(
                (t for t in EDGE_TYPES if types[t]), key=lambda t: (-types[t], EDGE_TYPES.index(t))
            )
        ),
        by_source=tuple((s, SOURCE_LABELS[s], sources[s]) for s in SOURCES if sources[s]),
    )


# --- Die ganze Seite -------------------------------------------------------------------------------
@dataclass(frozen=True)
class ProceduresModel:
    """Was ``templates/pages/vorgaenge.html.j2`` als ``data.vorgaenge`` sieht."""

    check: Check
    first: dt.date | None
    last: dt.date | None
    answers: Answers | None  # None ohne Anfragen im Datensatz
    fractions: tuple[FractionRow, ...]
    split: tuple[SplitFraction, ...]  # eine Partei neben ihrer späteren Fraktion (wie Punkt 88)
    with_fractions: bool  # Vorhaben 15 läuft in diesem Profil
    candidates: tuple[Candidate, ...]
    candidate_bodies: tuple[str, ...]  # die Gremien ab ``CANDIDATE_PRACTICE``, beim Namen
    procedures: Procedures
    missing: tuple[str, ...]  # was diesem Profil fehlt, je ein Satz (Plan § 6)
    running: bool  # laufende Periode: viele Anfragen sind beim Abruf noch jung
    min_questions: int = MIN_QUESTIONS
    min_dated: int = MIN_DATED
    min_expected: int = MIN_EXPECTED
    session_practice: float = SESSION_PRACTICE
    candidate_practice: float = CANDIDATE_PRACTICE

    @property
    def explorative(self) -> bool:
        return not self.check.measured


def body_names(settings: Settings, bodies: pl.DataFrame) -> dict[str, str]:
    """Je Kürzel der Name wie auf ``akteure.html`` (``actors.body_name``), sonst das Kürzel."""
    from georep.prep.bodies import BodyRules
    from georep.report.actors import body_name

    rules = BodyRules.from_settings(settings.bodies)
    names: dict[str, str] = {}
    for row in (
        bodies.select("gremium", "gremium_art", "stadtbezirk").unique().iter_rows(named=True)
    ):
        code = str(row["gremium"] or "")
        if code and code not in names:
            names[code] = body_name(row, rules)
    return names


def _authors(fractions: Sequence[str] | None, kind: str | None, labels: Mapping[str, str]) -> str:
    from georep.report.actors import ORIGINATOR_LABELS

    if fractions:
        return ", ".join(labels.get(f, f) for f in fractions)
    if kind == "Fraktion":
        return "Fraktion nicht erkannt"
    return ORIGINATOR_LABELS.get(str(kind or "unbekannt"), str(kind or "unbekannt"))


def build_procedures(
    corpus: pl.DataFrame,
    forest: pl.DataFrame,
    edges: pl.DataFrame,
    answers: pl.DataFrame,
    questions: pl.DataFrame,
    attachments: pl.DataFrame,
    bodies: pl.DataFrame,
    settings: Settings,
    check: Check,
    *,
    with_fractions: bool,
) -> ProceduresModel:
    """Das Modell der Seite. ``questions`` trägt je Anfrage ``id``, ``fraktionen``, ``urheber_art``."""
    from georep.report.actors import labels_of

    labels, _ = labels_of(settings)
    names = body_names(settings, bodies)
    dates = corpus.get_column("date").drop_nulls()
    first, last = dates.min(), dates.max()
    missing: list[str] = []
    answers_model: Answers | None = None
    fractions: tuple[FractionRow, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    candidate_bodies: tuple[str, ...] = ()
    split: tuple[SplitFraction, ...] = ()
    if answers.is_empty():
        missing.append(
            "Anfragen: das Profil kennt keine Dokumentart mit der Rolle Anfrage, darum fehlen "
            "Antworten, Antwortzeiten und Kandidaten."
        )
    else:
        joined = (
            answers.join(questions, on="id", how="left")
            .join(corpus.select("id", "reference", "date", "download_url"), on="id", how="left")
            .with_columns(pl.col("fraktionen").fill_null([]))
            .sort("id")  # ein Join legt die Zeilenfolge nicht fest (CLAUDE.md)
        )
        times = answer_times_of(joined.get_column("tage"))
        rows, small, small_questions = body_rows(joined, names)
        source = joined.get_column("quelle")
        answered = int((source != NO_ANSWER).sum())
        unanswered = joined.filter(pl.col("quelle") == NO_ANSWER)
        p90 = times.p90
        answers_model = Answers(
            questions=joined.height,
            answered=answered,
            by_attachment=int(source.is_in(["anlage", "beide"]).sum()),
            by_paper_only=int((source == "drucksache").sum()),
            undated=answered - times.dated,
            times=times,
            bodies=rows,
            small_bodies=small,
            small_questions=small_questions,
            names=answer_names(
                joined, attachments, ReferenceRules.from_settings(settings.procedures)
            ),
            invalid_dates=tuple(settings.procedures.attachment_dates_invalid),
            young=int((unanswered.get_column("alter_am_abruf") <= p90).sum())
            if p90 is not None
            else 0,
        )
        if with_fractions:
            fractions = fraction_rows(joined, labels)
            split = split_fractions(joined, fractions, settings)
        else:
            missing.append(
                "Fraktionen: Vorhaben 15 (Antragsteller) läuft in diesem Profil nicht, darum fehlt "
                "der Abschnitt je Fraktion."
            )
        # Die Praxis eines Gremiums zählt erst ab ``MIN_QUESTIONS`` Anfragen, wie die Zeilen von
        # Abschnitt 1; drei von vier Antworten sind keine Praxis (Messdokument § 3.8: die Gremien
        # mit mindestens 30 Anfragen).
        large = {row.code for row in rows}
        practiced = joined.filter(
            (pl.col("praxis_gremium") >= CANDIDATE_PRACTICE)
            & pl.col("gremium").fill_null("").is_in(sorted(large))
        )
        candidate_bodies = tuple(
            sorted(
                {
                    names.get(str(c), str(c))
                    for c in practiced.get_column("gremium").unique().drop_nulls().to_list()
                }
            )
        )
        if p90 is not None:
            chosen = practiced.filter(
                (pl.col("quelle") == NO_ANSWER) & (pl.col("alter_am_abruf") > p90)
            )
            candidates = tuple(
                Candidate(
                    reference=str(row["reference"] or ""),
                    url=_https(row["download_url"]),
                    date=row["date"],
                    body=names.get(str(row["gremium"] or ""), str(row["gremium"] or "")),
                    authors=_authors(row["fraktionen"], row["urheber_art"], labels),
                    age=int(row["alter_am_abruf"]),
                )
                for row in chosen.sort("date", "reference").iter_rows(named=True)
            )
    own_ids = corpus.get_column("id").to_list()
    return ProceduresModel(
        check=check,
        first=first if isinstance(first, dt.date) else None,
        last=last if isinstance(last, dt.date) else None,
        answers=answers_model,
        fractions=fractions,
        split=split,
        with_fractions=with_fractions,
        candidates=candidates,
        candidate_bodies=candidate_bodies,
        procedures=procedure_summary(forest, edges, own_ids),
        missing=tuple(missing),
        running=settings.period.end is None,
    )


# --- Dateien -----------------------------------------------------------------------------------
def _files(layout: Layout) -> tuple[Path, Path, Path]:
    from georep.enrich.procedures import procedure_files

    files = procedure_files(layout)
    return files.edges, files.documents, files.answers


def _attachments(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    from georep.enrich.procedures import procedure_files

    return (procedure_files(layout).attachments,) if settings.procedures.attachments else ()


def _cosponsors(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    from georep.enrich.functions import functions_enabled, functions_files

    return (functions_files(layout).cosponsors,) if functions_enabled(settings) else ()


def procedures_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Was ``page_vorgaenge`` liest: die drei Tabellen von 14, Korpus, Gremien, Urheber, Anlagen,
    die Antragsteller aus 15, wo es läuft, und die Prüfung."""
    return (
        *_files(layout),
        layout.corpus,
        layout.papers_bodies,
        layout.document_originators,
        *_attachments(layout, settings),
        *_cosponsors(layout, settings),
        *check_files(settings),
    )


def _questions(layout: Layout, settings: Settings) -> pl.DataFrame:
    """Je Korpus-ID Urheberklasse und Fraktionen (leer ohne Vorhaben 15)."""
    originators = pl.read_parquet(layout.document_originators, columns=["id", "urheber_art"])
    cosponsors = _cosponsors(layout, settings)
    if not cosponsors:
        return originators.with_columns(pl.lit([], dtype=pl.List(pl.String)).alias("fraktionen"))
    fractions = pl.read_parquet(cosponsors[0], columns=["id", "fraktionen"])
    return originators.join(fractions, on="id", how="left").sort("id")


def read_attachments(layout: Layout, settings: Settings) -> pl.DataFrame:
    paths = _attachments(layout, settings)
    if not paths:
        return pl.DataFrame(schema=ATTACHMENT_SCHEMA)
    return pl.read_parquet(paths[0])


def procedures_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    """``Page.data``: die Dateien lesen, das Modell bauen."""
    edges, forest, answers = _files(layout)
    model = build_procedures(
        pl.read_parquet(layout.corpus, columns=["id", "reference", "date", "download_url"]),
        pl.read_parquet(forest),
        pl.read_parquet(edges),
        pl.read_parquet(answers),
        _questions(layout, settings),
        read_attachments(layout, settings),
        pl.read_parquet(
            layout.papers_bodies, columns=["id", "gremium", "gremium_art", "stadtbezirk"]
        ),
        settings,
        read_check(settings),
        with_fractions=bool(_cosponsors(layout, settings)),
    )
    return page_data(model, settings)


def repository_links(settings: Settings) -> dict[str, str]:
    """Messdokument und die READMEs der drei Prüfungen; Vorlage und Allowlist lesen dieselben."""
    from georep.report.render import REPOSITORY

    folder = settings.validation.root.name
    readme = f"{REPOSITORY}/blob/main/{folder}"
    return {
        "measurement": f"{REPOSITORY}/blob/main/{MEASUREMENT}",
        "rule": f"{readme}/{RULE_PROJECT}/README.md",
        "first": f"{readme}/{FIRST_PROJECT}/README.md",
        "second": f"{readme}/{SECOND_PROJECT}/README.md",
        "rule_folder": f"{folder}/{RULE_PROJECT}",
    }


def page_data(model: ProceduresModel, settings: Settings) -> Mapping[str, object]:
    """Was die Vorlage als ``data`` sieht: das Modell als ``vorgaenge``, Links und Wörter."""
    return {
        "vorgaenge": model,
        "urls": repository_links(settings),
        "session_guest": SESSION_GUEST,
        "sources": SOURCE_LABELS,
    }


def procedures_links(layout: Layout, settings: Settings) -> frozenset[str]:
    """Die Links nach außen: die PDF-Dateien des Korpus (Kandidaten), Messdokument, Prüfungen."""
    links = set(v for k, v in repository_links(settings).items() if k != "rule_folder")
    if not layout.corpus.is_file():
        return frozenset(links)
    urls = pl.read_parquet(layout.corpus, columns=["download_url"]).get_column("download_url")
    return frozenset(links | {_https(u) for u in urls.to_list() if u})


# --- Der Vorgang im Dokumentdialog (Vorarbeit V2) ------------------------------------------------
def dialog_entries(
    edges: pl.DataFrame, dates: Mapping[str, dt.date | None]
) -> tuple[tuple[str, ...], dict[str, tuple[tuple[int, str | None], ...]]]:
    """Je Dokument seine starken Nachbarn mit Rolle, in beiden Richtungen; ``bezug`` höchstens
    ``MAX_RELATED``, danach ein Eintrag „und N weitere Nennungen" ohne Ziel (Frage 9.7).

    Folge je Dokument: nach der Folge von ``DIALOG_LABELS``, dann neueste zuerst, dann ID.
    """
    order = list(DIALOG_LABELS)
    found: dict[str, list[tuple[int, str]]] = {}
    for von, nach, typ in edges.filter("stark").select("von", "nach", "typ").iter_rows():
        found.setdefault(von, []).append((order.index((typ, OUT)), nach))
        found.setdefault(nach, []).append((order.index((typ, IN)), von))
    labels = [DIALOG_LABELS[key] for key in order]
    related = {order.index(("bezug", OUT)), order.index(("bezug", IN))}
    rows: dict[str, tuple[tuple[int, str | None], ...]] = {}
    for doc_id, entries in found.items():
        entries.sort(key=lambda e: (e[0], -(dates.get(e[1]) or dt.date.min).toordinal(), e[1]))
        kept: list[tuple[int, str | None]] = []
        dropped = 0
        for label, target in entries:
            if label in related and sum(1 for k, _ in kept if k in related) >= MAX_RELATED:
                dropped += 1
                continue
            kept.append((label, target))
        if dropped:
            word = f"und {dropped} weitere Nennung" + ("en" if dropped > 1 else "")
            if word not in labels:
                labels.append(word)
            kept.append((labels.index(word), None))
        rows[doc_id] = tuple(kept)
    return tuple(labels), rows


def dialog_note(check: Check) -> str:
    """Der Satz unter der Liste: was eine Verbindung ist und wie sie geprüft ist (``guete.json``)."""
    from georep.report.model import format_de

    rule = check.rule
    note = (
        f"{DIALOG_TITLE}: Verbindungen über die Nummer im Titel, in einer Anlage, als Nachtrag "
        f"oder aus einem Sammelbericht, nicht nur im Text; {format_de(rule.hits)} von "
        f"{format_de(rule.judged)} als dieselbe Sache bestätigt, {rule.sentence}."
    )
    if not check.measured:
        note += " In diesem Datensatz explorativ."
    return note


def short_title(title: str | None) -> str:
    """Leerraum zusammengefasst, höchstens ``TITLE_CHARS`` Zeichen, gekürzt mit „…"."""
    text = " ".join((title or "").split())
    return text if len(text) <= TITLE_CHARS else text[: TITLE_CHARS - 1].rstrip() + "…"


def _neighbour_targets(settings: Settings, wanted: set[str]) -> dict[str, DialogTarget]:
    """Die Ziele in einer Nachbarperiode aus deren Paket: Link, Datum, Drucksache, Titel."""
    from georep.enrich.procedures import neighbours, read_papers

    found: dict[str, DialogTarget] = {}
    for period in neighbours(settings):
        for record in read_papers(period.papers):
            if record.id in wanted and record.id not in found:
                found[record.id] = DialogTarget(
                    _https(record.download_url),
                    record.date,
                    record.reference or "",
                    short_title(record.name),
                )
    return found


def dialog_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Was ``report`` für ``data/vorgaenge.json`` liest: Kanten, Korpus, Pakete der Nachbarn, Prüfung."""
    from georep.enrich.procedures import procedure_files, related_inputs

    return (
        procedure_files(layout).edges,
        layout.corpus,
        *related_inputs(settings, texts=False),
        *check_files(settings),
    )


def dialog_rows(layout: Layout, settings: Settings) -> DialogRows:
    """``DialogHook.rows``: je Dokument die starken Nachbarn, die Ziele mit Link und Titel."""
    from georep.enrich.procedures import procedure_files

    edges = pl.read_parquet(procedure_files(layout).edges, columns=["von", "nach", "typ", "stark"])
    corpus = pl.read_parquet(
        layout.corpus, columns=["id", "reference", "name", "date", "download_url"]
    )
    targets = {
        str(row["id"]): DialogTarget(
            _https(row["download_url"]),
            row["date"],
            str(row["reference"] or ""),
            short_title(row["name"]),
        )
        for row in corpus.iter_rows(named=True)
    }
    wanted = {str(n) for n in edges.filter("stark").get_column("nach").to_list()} - set(targets)
    targets |= _neighbour_targets(settings, wanted)
    labels, found = dialog_entries(edges, {k: t.date for k, t in targets.items()})
    # Ein Ziel, das weder der Korpus noch ein Nachbarpaket kennt, fällt weg, statt ohne Nummer da
    # zu stehen; ``references`` legt nur Kanten zu bekannten Nummern an, es ist also ein Schutz.
    rows = {
        doc_id: tuple(e for e in entries if e[1] is None or e[1] in targets)
        for doc_id, entries in found.items()
    }
    used = {target for entries in rows.values() for _, target in entries if target is not None}
    return DialogRows(
        labels=labels,
        rows=rows,
        targets={k: targets[k] for k in sorted(used & set(targets))},
        note=dialog_note(read_check(settings)),
    )
