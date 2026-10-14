"""Gremium je Ratsdokument: zuerst aus der Drucksachennummer, dann aus der Beratungsfolge (Option 5).

``BV6/108/2023`` ist eine Vorlage der Bezirksvertretung 6, ``RAT/270/2023`` eine des Rates,
``OVA/117/2023/1`` ein Nachtrag im Ordnungs- und Verkehrsausschuss: das Kürzel vor dem ersten
Schrägstrich nennt das Gremium, die Nummer dahinter bei Bezirksvertretungen den Stadtbezirk. Muster,
Kürzel und Namen stehen in den Settings (``[bodies]``, docs/plans/05-gremien.md, § 2); ein Kürzel ohne
Tabelle und eine Nummer ohne Muster sind „unbekannt", sichtbar mit Anteil auf der Seite, nie eine
stille Fehlklasse. ``parse_reference`` ist eine reine Funktion über einem vorkompilierten
``BodyRules``-Objekt (hypothesis aus der Grammatik, ``deal.cases``, crosshair in ``nox -s verify``);
``classify_papers`` ist die Batch-Grenze mit Verträgen und schreibt eine Zeile je Korpus-ID
(00-synergien.md, § 5.6). Der Vertrag des Parsers ist ``deal.safe`` und nicht ``deal.pure``: die
Batch-Funktion ruft ihn einmal je Dokument, und ``deal.has()`` patcht dabei je Aufruf prozessweit
``socket`` und ``sys.stdout`` (CLAUDE.md, „Nie"). Gemessen am 2026-10-12 auf der Referenz kostete
``deal.pure`` 0,076 s gegen 0,053 s, rund 30 %; die Reinheit prüfen stattdessen ``deal.cases`` und
crosshair.

**Die zweite Quelle** (Punkt 58, docs/befunde-2026-10-14.md, § 4): OParl nennt je Dokument die
beratenden Gremien als Organisations-URLs (``consultation_organizations``). ``[bodies.organizations]``
bildet sie auf dieselben Kürzel ab; die Tabelle ist gelernt und nicht geraten
(``georep learn-bodies``). Die Reihenfolge der Quellen ist fest: **die Nummer entscheidet**, die
Folge ergänzt nur, wo die Nummer kein bekanntes Gremium liefert -- und auch dann nur, wenn sie
**genau eines** nennt. Nennt sie mehrere, bleibt das Dokument „unbekannt": die Liste ist sortiert
und entdoppelt (``georep.oparl.OparlPaper.consultation_organizations``), die Beratungsreihenfolge
also nicht mehr darin, und gemessen am 2026-10-14 trifft die beste von fünf Auswahlregeln
(seltenste Organisation, Klassenvorrang, alphabetisch …) nur 59,9 % der Fälle, in denen die Nummer
die Antwort kennt -- gegen 99,1 % bei eindeutiger Folge. Jede Spalte der Ausgabe sagt, woher sie
kommt: ``quelle``, ``folge_gremium`` und ``folge_anzahl`` machen Zustimmung, Widerspruch und
Mehrdeutigkeit zählbar, statt sie zu verrechnen.
"""

from __future__ import annotations

import re
import types
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import deal
import polars as pl

from georep.contracts import has_columns, is_district_code, sorted_unique
from georep.settings import Bodies

KINDS = ("bezirksvertretung", "rat", "ausschuss", "beirat", "unbekannt")
DISTRICT_BODY, COUNCIL, COMMITTEE, ADVISORY, UNKNOWN = KINDS
KIND_LABELS = {
    DISTRICT_BODY: "Bezirksvertretung",
    COUNCIL: "Rat",
    COMMITTEE: "Ausschuss",
    ADVISORY: "Beirat",
    UNKNOWN: "unbekannt",
}
# Punkt 58: woher die Klasse eines Dokuments kommt. Die Reihenfolge ist die der Entscheidung.
SOURCES = ("nummer", "alias", "beratungsfolge", "unbekannt")
FROM_NUMBER, FROM_ALIAS, FROM_CONSULTATION, FROM_NOWHERE = SOURCES
SOURCE_LABELS = {
    FROM_NUMBER: "Drucksachennummer",
    FROM_ALIAS: "ältere Nummernform",
    FROM_CONSULTATION: "Beratungsfolge",
    FROM_NOWHERE: "keine Quelle",
}
# Version 2 (Punkt 58): quelle, folge_gremium und folge_anzahl kommen dazu.
BODIES_SCHEMA_VERSION = 2  # erhöhen, wenn sich Spalten oder Typen von papers_gremien.parquet ändern
# Spaltennamen der Ausgabe; wer sie liest, nennt sie so (georep.analysis.bodies, der Report)
ID = "id"
REFERENCE = "reference"
BODY = "gremium"
KIND = "gremium_art"
CITY_DISTRICT = "stadtbezirk"
SOURCE = "quelle"
CONSULTATION = "consultation_organizations"  # Spalte des Korpus und des Pakets
CONSULTATION_BODY = "folge_gremium"
CONSULTATION_COUNT = "folge_anzahl"
BODIES_COLUMNS = [
    ID,
    REFERENCE,
    BODY,
    KIND,
    CITY_DISTRICT,
    SOURCE,
    CONSULTATION_BODY,
    CONSULTATION_COUNT,
]
BODIES_SCHEMA = {
    ID: pl.String,
    REFERENCE: pl.String,
    BODY: pl.String,  # Kürzel samt Nummer (BV6, RAT, OVA); null, wenn das Muster nicht trifft
    KIND: pl.String,  # eines aus KINDS
    CITY_DISTRICT: pl.Int64,  # nur bei Bezirksvertretungen
    SOURCE: pl.String,  # eines aus SOURCES
    # Punkt 58: was die Beratungsfolge allein sagen würde; null, wenn sie nichts oder mehr als ein
    # Gremium nennt. Daneben die Zahl der Gremien, die sie auflöst: 0 = keine Folge oder keine
    # bekannte Organisation darin, 1 = entschieden, mehr = mehrdeutig.
    CONSULTATION_BODY: pl.String,
    CONSULTATION_COUNT: pl.Int64,
}


@dataclass(frozen=True)
class BodyRef:
    kind: str  # eines aus KINDS
    code: str | None  # Kürzel samt Nummer, etwa "BV6"; None, wenn das Muster nicht trifft
    district: int | None  # Stadtbezirk, genau bei Bezirksvertretungen
    # Punkt 58: woher die Klasse kommt, eines aus SOURCES. ``compare=False``, weil die Herkunft
    # keine Identität ist: dasselbe Gremium bleibt dasselbe, ob die Nummer oder die Beratungsfolge
    # es nennt. So vergleichen die Beispieltests weiter drei Felder.
    source: str = field(default=FROM_NUMBER, compare=False)


@dataclass(frozen=True)
class BodyRules:
    """Die Regeln aus ``[bodies]``, einmal kompiliert; ``from_settings`` ist die einzige Brücke."""

    pattern: re.Pattern[str] | None  # None: die Nummern tragen kein Kürzel (Option 01)
    district_body: str
    district_body_name: str  # mit {n} für den Stadtbezirk
    council: frozenset[str]
    committees: frozenset[str]
    advisory: frozenset[str]
    names: Mapping[str, str]  # Kürzel -> Name; leer = nicht gesichert
    # Punkt 57: Kopf einer älteren Nummernform -> Kürzel, nur befragt, wenn das Muster nicht
    # trifft. Leer ist der Normalfall; die Settings prüfen, dass jedes Ziel ein bekanntes Kürzel ist.
    aliases: Mapping[str, str] = types.MappingProxyType({})
    # Punkt 58: Organisation der Beratungsfolge -> Kürzel, und die Namen der Bezirksvertretungen,
    # wo sie keine Nummer tragen. Beide leer ist der Normalfall.
    organizations: Mapping[str, str] = types.MappingProxyType({})
    district_body_names: Mapping[str, str] = types.MappingProxyType({})

    @classmethod
    def from_settings(cls, bodies: Bodies) -> BodyRules:
        return cls(
            pattern=re.compile(bodies.reference_pattern) if bodies.reference_pattern else None,
            district_body=bodies.district_body,
            district_body_name=bodies.district_body_name,
            council=frozenset(bodies.council),
            committees=frozenset(bodies.committees),
            advisory=frozenset(bodies.advisory),
            names={**bodies.council, **bodies.committees, **bodies.advisory},
            aliases=dict(bodies.aliases),
            organizations=dict(bodies.organizations),
            district_body_names=dict(bodies.district_body_names),
        )

    def kind_of(self, code: str) -> str:
        """Die Klasse eines Kürzels ohne Nummer; Bezirksvertretungen entscheidet ``parse_reference``."""
        if code in self.council:
            return COUNCIL
        if code in self.committees:
            return COMMITTEE
        if code in self.advisory:
            return ADVISORY
        return UNKNOWN

    def name_of(self, ref: BodyRef) -> str:
        """Der Name zum Gremium; leer, wenn keiner gesichert ist (die Seite zeigt dann das Kürzel).

        Punkt 58: eine Stadt, deren Bezirksvertretungen keine Nummer im Namen tragen
        (Mönchengladbach: „Bezirksvertretung Nord"), nennt sie in ``district_body_names``; ohne
        Eintrag bleibt das Muster ``district_body_name`` mit der Nummer.
        """
        if ref.kind == DISTRICT_BODY:
            named = self.district_body_names.get(ref.code or "")
            return named if named else self.district_body_name.format(n=ref.district)
        return self.names.get(ref.code or "", "")


def _consistent(result: BodyRef) -> bool:
    return (
        result.kind in KINDS
        and (result.district is not None) == (result.kind == DISTRICT_BODY)
        and (result.district is None or result.district >= 1)
        and (result.code is not None or result.kind == UNKNOWN)
        and result.source in SOURCES
        # Punkt 58: „keine Quelle" und „unbekannt" sind dieselbe Aussage, von zwei Seiten.
        and (result.source == FROM_NOWHERE) == (result.kind == UNKNOWN)
    )


def organization_key(url: str) -> str:
    """Die beiden letzten Segmente einer Organisations-URL: ``…/organizations/gr/6`` wird ``gr/6``.

    So steht in ``[bodies.organizations]`` ein lesbarer Schlüssel statt einer 70 Zeichen langen
    URL, und ein Wechsel von ``http`` auf ``https`` oder ein anderer Host derselben Körperschaft
    macht die Tabelle nicht ungültig. Eine URL mit weniger als zwei Segmenten bleibt, wie sie ist.
    """
    return "/".join(url.rsplit("/", 2)[-2:])


def _codes_are_sorted_and_unique(result: tuple[str, ...]) -> bool:
    return list(result) == sorted(set(result)) and all(result)


@deal.safe
@deal.post(_codes_are_sorted_and_unique, message="jedes Kürzel einmal, sortiert, nie leer")
def resolve_organizations(
    organizations: Sequence[str], mapping: Mapping[str, str]
) -> tuple[str, ...]:
    """Die Kürzel, auf die eine Beratungsfolge zeigt: sortiert, jedes einmal.

    Zwei Wege je Organisation, erst die volle URL, dann ihre beiden letzten Segmente; eine
    Organisation, die die Tabelle nicht kennt, fällt weg. Genau ein Kürzel heißt „entschieden",
    mehrere heißen „mehrdeutig", und die aufrufende Stelle entscheidet, was das bedeutet.
    """
    found = {
        code
        for url in organizations
        if (code := mapping.get(url) or mapping.get(organization_key(url)))
    }
    return tuple(sorted(found))


def _from_code(code: str, rules: BodyRules, source: str = FROM_ALIAS) -> BodyRef:
    """Die Klasse eines fertigen Kürzels, wie ``bodies.aliases`` es liefert (Punkt 57).

    Dieselben zwei Regeln wie am Ende von ``parse_reference``, nur ohne die Gruppen eines Musters:
    das Kürzel der Bezirksvertretungen mit einer Nummer ab 1 ist eine Bezirksvertretung, alles
    andere entscheidet die Tabelle. Die erste Regel ist ``contracts.is_district_code``, dasselbe
    Prädikat, das der Validator von ``settings.Bodies`` auf die Ziele in ``bodies.aliases``
    anwendet -- vorher stand sie zweimal da und wich bei leerem ``district_body`` auseinander.
    """
    if is_district_code(code, rules.district_body):
        return BodyRef(DISTRICT_BODY, code, int(code[len(rules.district_body) :]), source)
    if rules.district_body and code.startswith(rules.district_body):
        # Das Kürzel der Bezirksvertretungen ohne brauchbare Nummer (``BV``, ``BV0``, ``BVx``):
        # unbekannt, aber mit Kürzel -- wie am Muster, damit die Seite es nennen kann.
        return BodyRef(UNKNOWN, code, None, FROM_NOWHERE)
    kind = rules.kind_of(code)
    return BodyRef(kind, code, None, FROM_NOWHERE if kind == UNKNOWN else source)


@deal.safe
@deal.post(_consistent, message="Klasse aus KINDS, Stadtbezirk genau bei Bezirksvertretungen, ab 1")
def parse_reference(reference: str | None, rules: BodyRules) -> BodyRef:
    """Das Gremium einer Drucksachennummer; alles Unerwartete ist ``unbekannt``."""
    # Option 01: ohne Muster trägt die Nummer kein Kürzel, und alles ist „unbekannt"
    if reference is None or rules.pattern is None:
        return BodyRef(UNKNOWN, None, None, FROM_NOWHERE)
    match = rules.pattern.match(reference)
    if match is None:
        # Punkt 57: eine ältere Nummernform derselben Stadt, deren Kopf kein Kürzel ist
        # (``171/ 23/2016``). Das Profil übersetzt genau die Köpfe, die eines bedeuten; alles
        # übrige bleibt „unbekannt", und ein Profil ohne Tabelle merkt von alledem nichts.
        alias = rules.aliases.get(reference.split("/", 1)[0].strip())
        if alias is not None:
            return _from_code(alias, rules, FROM_ALIAS)
        return BodyRef(UNKNOWN, None, None, FROM_NOWHERE)
    # ``groupdict`` statt ``group``: ein Muster ohne die Gruppe ``code`` ist dann „unbekannt" statt
    # eines KeyError. Die Settings erzwingen beide Gruppen, ein von Hand gebautes BodyRules nicht
    # (crosshair fand den Fall am 2026-10-12).
    groups = match.groupdict()
    code, number = groups.get("code"), groups.get("number")
    if code is None:
        return BodyRef(UNKNOWN, None, None, FROM_NOWHERE)
    if number is not None and not number.isdecimal():
        return BodyRef(UNKNOWN, f"{code}{number}", None, FROM_NOWHERE)
    if code == rules.district_body:
        if number is None or int(number) < 1:
            return BodyRef(UNKNOWN, f"{code}{number or ''}", None, FROM_NOWHERE)
        return BodyRef(DISTRICT_BODY, f"{code}{number}", int(number), FROM_NUMBER)
    if number is not None:
        return BodyRef(UNKNOWN, f"{code}{number}", None, FROM_NOWHERE)
    kind = rules.kind_of(code)
    return BodyRef(kind, code, None, FROM_NOWHERE if kind == UNKNOWN else FROM_NUMBER)


def _district_only_for_district_bodies(frame: pl.DataFrame) -> bool:
    is_body = frame.get_column(KIND) == DISTRICT_BODY
    return bool((frame.get_column(CITY_DISTRICT).is_null() != is_body).all())


def _same_ids(
    corpus: pl.DataFrame,
    rules: BodyRules,
    consultations: pl.DataFrame | None = None,
    result: pl.DataFrame | None = None,
) -> bool:
    """Benannter Validator mit Vorgaben, weil ``consultations`` optional ist (CLAUDE.md, deal)."""
    assert result is not None
    return result.height == corpus.height and set(result.get_column(ID)) == set(
        corpus.get_column(ID)
    )


def _source_matches_the_class(frame: pl.DataFrame) -> bool:
    """Punkt 58: „unbekannt" und „keine Quelle" stehen immer zusammen, und sonst nie."""
    nowhere = frame.get_column(SOURCE) == FROM_NOWHERE
    return bool(
        set(frame.get_column(SOURCE)) <= set(SOURCES)
        and ((frame.get_column(KIND) == UNKNOWN) == nowhere).all()
    )


def _consultation_counts_fit(frame: pl.DataFrame) -> bool:
    """``folge_gremium`` steht genau dann, wenn die Folge genau ein Gremium auflöst."""
    return bool(
        (frame.get_column(CONSULTATION_COUNT) >= 0).all()
        and (
            frame.get_column(CONSULTATION_BODY).is_not_null()
            == (frame.get_column(CONSULTATION_COUNT) == 1)
        ).all()
    )


@deal.pre(
    lambda corpus, rules, consultations=None: (
        has_columns(corpus, ID, REFERENCE)
        and (consultations is None or has_columns(consultations, ID, CONSULTATION))
    ),
    message="Korpus mit id und reference, Beratungsfolge mit id und consultation_organizations",
)
@deal.post(lambda result: result.columns == BODIES_COLUMNS)
@deal.post(lambda result: sorted_unique(result, ID), message="eine Zeile je Korpus-ID, sortiert")
@deal.post(lambda result: set(result.get_column(KIND)) <= set(KINDS))
@deal.post(
    _district_only_for_district_bodies,
    message="stadtbezirk genau bei Bezirksvertretungen gesetzt",
)
@deal.post(_source_matches_the_class, message="quelle und gremium_art sagen dasselbe")
@deal.post(_consultation_counts_fit, message="folge_gremium genau bei folge_anzahl = 1")
@deal.ensure(_same_ids, message="genau die IDs des Korpus")
def classify_papers(
    corpus: pl.DataFrame, rules: BodyRules, consultations: pl.DataFrame | None = None
) -> pl.DataFrame:
    """Eine Zeile je Dokument: Kürzel, Klasse, Stadtbezirk und die Quelle, aus der sie kommen.

    Die Drucksachennummer entscheidet. ``consultations`` (Spalten ``id`` und
    ``consultation_organizations``) ist die zweite Quelle und ergänzt nur, wo die Nummer kein
    bekanntes Gremium liefert **und** die Folge genau eines nennt (Punkt 58, siehe Modulkopf).
    Ohne das Argument rechnet die Funktion wie vor Punkt 58: allein aus der Nummer.
    """
    refs = [parse_reference(r, rules) for r in corpus.get_column(REFERENCE).to_list()]
    resolved = _resolved_consultations(corpus, rules, consultations)
    folge = [resolved.get(str(i), ()) for i in corpus.get_column(ID).to_list()]
    counts = [len(codes) for codes in folge]
    from_folge = [codes[0] if len(codes) == 1 else None for codes in folge]
    decided = [_decide(ref, code, rules) for ref, code in zip(refs, from_folge, strict=True)]
    return pl.DataFrame(
        {
            ID: corpus.get_column(ID),
            REFERENCE: corpus.get_column(REFERENCE),
            BODY: [r.code for r in decided],
            KIND: [r.kind for r in decided],
            CITY_DISTRICT: [r.district for r in decided],
            SOURCE: [r.source for r in decided],
            CONSULTATION_BODY: from_folge,
            CONSULTATION_COUNT: counts,
        },
        schema=BODIES_SCHEMA,
    ).sort(ID)


def _decide(ref: BodyRef, from_consultation: str | None, rules: BodyRules) -> BodyRef:
    """Die Nummer zuerst; die Folge nur, wo die Nummer kein bekanntes Gremium liefert."""
    if ref.kind != UNKNOWN or from_consultation is None:
        return ref
    candidate = _from_code(from_consultation, rules, FROM_CONSULTATION)
    return ref if candidate.kind == UNKNOWN else candidate


def _resolved_consultations(
    corpus: pl.DataFrame, rules: BodyRules, consultations: pl.DataFrame | None
) -> dict[str, tuple[str, ...]]:
    """Dokument-ID -> die Kürzel, die seine Beratungsfolge auflöst (leer, wo es keine gibt)."""
    if consultations is None or not rules.organizations:
        return {}
    wanted = set(corpus.get_column(ID).to_list())
    return {
        str(row[ID]): resolve_organizations(row[CONSULTATION] or (), rules.organizations)
        for row in consultations.select(ID, CONSULTATION).iter_rows(named=True)
        if str(row[ID]) in wanted
    }


def merge_consultations(own: pl.DataFrame, extra: pl.DataFrame | None) -> pl.DataFrame:
    """Die Beratungsfolge des Korpus, aufgefüllt aus einem Paket (Punkt 58).

    ``own`` sind ``id`` und ``consultation_organizations`` aus dem Korpus dieses Profils, ``extra``
    dieselben zwei Spalten aus ``[bodies].consultations``. Was das Dokument selbst mitbringt,
    gewinnt: das Paket ist für die Periode gedacht, deren Abruf die Folge nicht trug (die
    Hauptperiode Düsseldorfs kommt aus dem Altformat der Arbeit). Dokumente, die nur im Paket
    stehen, fallen weg -- der Korpus sagt, welche Dokumente es gibt.
    """
    empty = pl.col(CONSULTATION).list.len() == 0
    if extra is None:
        return own.select(ID, CONSULTATION)
    filled = extra.select(ID, pl.col(CONSULTATION).alias("_extra"))
    return (
        own.select(ID, CONSULTATION)
        .join(filled, on=ID, how="left")
        .with_columns(
            pl.when(empty & pl.col("_extra").is_not_null())
            .then(pl.col("_extra"))
            .otherwise(pl.col(CONSULTATION))
            .alias(CONSULTATION)
        )
        .select(ID, CONSULTATION)
    )


@deal.pre(lambda frame: has_columns(frame, KIND))
@deal.post(lambda result: tuple(result) == KINDS, message="jede Klasse kommt vor, auch mit 0")
def counts_by_kind(frame: pl.DataFrame) -> dict[str, int]:
    counted = dict(frame.group_by(KIND).len().iter_rows())
    return {kind: int(counted.get(kind, 0)) for kind in KINDS}


@dataclass(frozen=True)
class SourceCounts:
    """Punkt 58: wie viele Dokumente aus welcher Quelle kommen, und wie die beiden sich vertragen."""

    per_source: tuple[tuple[str, int], ...]  # in der Reihenfolge von SOURCES
    confirmed: int  # Nummer und Folge nennen dasselbe Gremium
    conflicting: int  # beide nennen eines, und es ist nicht dasselbe; die Nummer bleibt
    ambiguous: int  # ohne Gremium aus der Nummer, und die Folge nennt mehr als eines

    @property
    def documents(self) -> int:
        return sum(count for _, count in self.per_source)

    @property
    def from_consultation(self) -> int:
        return dict(self.per_source)[FROM_CONSULTATION]

    def line(self) -> str:
        """Der Zusatz in der Zeile des Schritts; leer, wo die Folge gar nicht mitgerechnet hat."""
        if not (self.from_consultation or self.confirmed or self.conflicting or self.ambiguous):
            return ""
        return (
            f"Beratungsfolge: {self.from_consultation} ergänzt, {self.confirmed} bestätigt, "
            f"{self.conflicting} Widerspruch, {self.ambiguous} mehrdeutig"
        )


@deal.pre(
    lambda frame: has_columns(frame, BODY, KIND, SOURCE, CONSULTATION_BODY, CONSULTATION_COUNT)
)
@deal.post(
    lambda result: result.documents >= 0 and {s for s, _ in result.per_source} == set(SOURCES),
    message="jede Quelle kommt vor, auch mit 0",
)
def source_counts(frame: pl.DataFrame) -> SourceCounts:
    """Die Zahlen zu den Quellen aus ``papers_gremien.parquet``; eine Abfrage, keine Rechnung."""
    counted = dict(frame.group_by(SOURCE).len().iter_rows())
    both = frame.filter((pl.col(KIND) != UNKNOWN) & pl.col(CONSULTATION_BODY).is_not_null()).filter(
        pl.col(SOURCE) != FROM_CONSULTATION
    )
    same = int((both.get_column(CONSULTATION_BODY) == both.get_column(BODY)).sum())
    return SourceCounts(
        per_source=tuple((source, int(counted.get(source, 0))) for source in SOURCES),
        confirmed=same,
        conflicting=both.height - same,
        ambiguous=int(
            frame.filter((pl.col(KIND) == UNKNOWN) & (pl.col(CONSULTATION_COUNT) > 1)).height
        ),
    )


def summary(frame: pl.DataFrame) -> str:
    """Die Rückgabezeile des Schritts ``bodies``."""
    counts = counts_by_kind(frame)
    parts = ", ".join(f"{counts[kind]} {KIND_LABELS[kind]}" for kind in KINDS)
    line = f"{frame.height} Dokumente: {parts}"
    sources = source_counts(frame).line() if has_columns(frame, SOURCE) else ""
    return f"{line}; {sources}" if sources else line
