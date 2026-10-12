"""Urheber je Ratsdokument und daraus die Kennzahlen je Partei und Wahlbezirk.

Der OParl-Server der ITK Rheinland liefert für Düsseldorf keine Urheberfelder (0 von 19 108
Rohobjekten, Befund vom 2026-10-09 in ``tests/fixtures/oparl/papers_page.json``). Der Urheber steht
stattdessen in drei vorhandenen Feldern, und genau in dieser Reihenfolge wird gefragt:

1. ``oparl``: ``originatorOrganization`` über die Organisations-URLs der Settings und, wenn
   ``raw/organizations.json`` vorliegt, über die Namen der Organisationen. Greift ohne
   Codeänderung, sobald der Server die Felder füllt.
2. ``paper_type``: „Anfrage SPD", „Antrag CDU/Grüne" nennen die Fraktion im Typ; die Vorlagen der
   Verwaltung und die Eingaben nach § 24 GO NRW stehen als ganze Werte in den Settings.
3. ``name``: „Antrag der SPD-Fraktion"; befragt wird der Titel nur, wenn ein Fraktionsmarker
   darin steht, sonst zählte „die cdu-fraktion beantragt" in einer Verwaltungsvorlage mit.
4. ``text``: ein Fenster um „antrag|anfrage … fraktion" in den ersten Zeichen nach „betrifft".

Die erste Quelle mit Parteitreffer gewinnt, die anderen werden nicht mehr befragt. ``urheber_art``
ist eine Partition (genau eine Klasse je Dokument), ``parteien`` eine sortierte Menge von
Settings-Schlüsseln, bei Nicht-Fraktionen leer. Alle Muster stehen in ``defaults.toml`` unter
``[originators]``, nichts davon im Code (Vorbereitung für Option 10).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

import deal
import polars as pl
from polars._typing import PolarsDataType
from scipy.stats import pearsonr, spearmanr

from georep.analysis.hits import DISTRICT, RATE
from georep.contracts import has_columns, one_row_per_document, sorted_unique
from georep.errors import SchemaError
from georep.oparl import OparlOrganization
from georep.search.index import HITS, PAPER_IDS
from georep.settings import Originators, Party

# Die Partition: genau eine Klasse je Dokument, ihre Summe ist die Zahl der Dokumente.
URHEBER_ARTEN = ("Verwaltung", "Fraktion", "Person", "Eingabe", "unbekannt")
# Spaltennamen der Partition in den Bezirkstabellen, in derselben Reihenfolge wie URHEBER_ARTEN.
KLASSEN_SPALTEN = ("verwaltung", "fraktion", "person", "eingabe", "unbekannt")
QUELLEN = ("oparl", "paper_type", "name", "text", "")
ART = "urheber_art"
PARTEIEN = "parteien"
QUELLE = "quelle"
TREFFER = "treffer"
PARTEI = "partei"
EXCERPT_PAD = 30  # Zeichen links und rechts um den Treffer in der Spalte ``treffer``

ATTRIBUTION_SCHEMA: dict[str, PolarsDataType] = {
    "id": pl.String,
    ART: pl.String,
    PARTEIEN: pl.List(pl.String),
    QUELLE: pl.String,
    TREFFER: pl.String,
}


@dataclass(frozen=True)
class Classification:
    """Die Zuordnung eines Dokuments: Klasse, Parteien, Quelle und die getroffene Zeichenkette."""

    art: str
    parteien: tuple[str, ...]
    quelle: str
    treffer: str


@dataclass(frozen=True)
class Patterns:
    """Die Muster aus ``[originators]``, einmal übersetzt.

    ``classify_document`` läuft je Dokument, also 19 108 Mal; ``re.compile`` je Aufruf wäre der
    teuerste Teil des Schritts. ``from_settings`` baut die Struktur einmal, ``with_organizations``
    hängt die Abbildung aus ``raw/organizations.json`` an.
    """

    admin_types: frozenset[str]
    citizen_types: frozenset[str]
    motion_prefixes: tuple[str, ...]  # längste zuerst, damit „Haushaltsantrag" vor „Antrag" greift
    fraction: re.Pattern[str] | None
    joint: re.Pattern[str] | None
    person: re.Pattern[str] | None
    text: re.Pattern[str] | None
    name_party: re.Pattern[str] | None  # schwaches Tor, erst nach den Personenmarkern
    parties: tuple[
        tuple[str, re.Pattern[str]], ...
    ]  # Schlüssel -> Muster, Reihenfolge der Settings
    org_suffixes: tuple[tuple[str, str], ...]  # URL-Endung -> Schlüssel, aus den Settings
    org_exact: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # URL -> Schlüssel
    head_chars: int = 600
    window_chars: int = 80

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.parties)

    @classmethod
    def from_settings(cls, originators: Originators) -> Patterns:
        return cls(
            admin_types=frozenset(originators.admin_types),
            citizen_types=frozenset(originators.citizen_types),
            motion_prefixes=tuple(
                sorted((p.lower() for p in originators.motion_prefixes), key=len, reverse=True)
            ),
            fraction=_any_of(originators.fraction_markers),
            joint=_any_of(originators.joint_markers),
            person=_any_of(originators.person_markers),
            text=_any_of(originators.text_markers),
            name_party=_any_of(originators.name_party_markers),
            parties=tuple(
                (p.key, _alternation(p.patterns))
                for p in (*originators.parties, *originators.groups)
            ),
            org_suffixes=tuple(
                (url, p.key)
                for p in (*originators.parties, *originators.groups)
                for url in p.organizations
            ),
            head_chars=originators.text_head_chars,
            window_chars=originators.text_window_chars,
        )

    def with_organizations(self, organizations: Iterable[OparlOrganization]) -> Patterns:
        """Dieselben Muster, dazu die URL-zu-Partei-Abbildung aus der Organisationsseite.

        Der Name und das Kürzel jeder Organisation werden mit den Parteimustern verglichen; so
        findet „Ratsfraktion SPD/Volt" die Schlüssel SPD und VOLT, ohne dass die URL in den
        Settings stehen muss. Gelöschte Organisationen bleiben draußen.
        """
        exact: dict[str, tuple[str, ...]] = {}
        for organization in organizations:
            if organization.deleted:
                continue
            haystack = " ".join(
                part for part in (organization.name, organization.short_name) if part
            ).lower()
            found = tuple(key for key, pattern in self.parties if pattern.search(haystack))
            if found:
                exact[organization.id] = found
        return replace(self, org_exact=exact)

    def in_settings_order(self, keys: Iterable[str]) -> tuple[str, ...]:
        """Die bekannten Schlüssel in der Reihenfolge der Settings, eindeutig; Unbekanntes fällt weg.

        ``from_settings`` baut Parteien und Organisationsabbildung aus derselben Liste, ein
        unbekannter Schlüssel kann also nur aus einem von Hand gebauten ``Patterns`` kommen. Er
        wird weggelassen statt die Sortierung zum Absturz zu bringen (crosshair, 2026-10-12): der
        Vertrag von ``classify_document`` verlangt ``parteien`` als Teilmenge der Settings.
        """
        order = {key: index for index, key in enumerate(self.keys)}
        return tuple(sorted({k for k in keys if k in order}, key=lambda k: order[k]))

    def parties_for_urls(self, urls: Sequence[str]) -> tuple[tuple[str, ...], str]:
        """(Parteischlüssel, getroffene URLs) für OParl-Urheber-URLs; leer, wenn keine zuordbar ist."""
        found: set[str] = set()
        matched: list[str] = []
        for url in urls:
            keys = self.org_exact.get(url, ())
            if not keys:
                keys = tuple(key for suffix, key in self.org_suffixes if url.endswith(suffix))
            known = self.in_settings_order(keys)
            if known:
                found.update(known)
                matched.append(url)
        return self.in_settings_order(found), " ".join(matched)


def read_organizations(path: Path) -> tuple[OparlOrganization, ...]:
    """Die Organisationen aus ``raw/organizations.json``; leer, wenn der Netzschritt nie lief.

    Der Schritt ``parties`` läuft auch ohne die Datei (dann greifen nur die URL-Endungen aus den
    Settings), damit die Kette aus der Referenz ohne Netz durchläuft.
    """
    if not path.is_file():
        return ()
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise SchemaError(f"{path.name}: kein gültiges JSON ({error})") from error
    if not isinstance(items, list):
        raise SchemaError(f"{path.name}: erwartet eine Liste von Organisationen")
    try:
        # pydantics ValidationError ist ein ValueError; der Rest der Kette kennt nur SchemaError,
        # und eine kaputte Datei soll eine Zeile auf stderr geben, keinen Traceback.
        return tuple(OparlOrganization.model_validate(item) for item in items)
    except ValueError as error:
        raise SchemaError(f"{path.name}: keine gültige Organisation ({error})") from error


def _any_of(patterns: Sequence[str]) -> re.Pattern[str] | None:
    """Ein Muster aus allen Markern; ``None``, wenn keine konfiguriert sind (Marker aus Settings)."""
    return re.compile("|".join(f"(?:{p})" for p in patterns)) if patterns else None


def _alternation(patterns: Sequence[str]) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns))


def _excerpt(haystack: str, start: int, end: int, pad: int = EXCERPT_PAD) -> str:
    """Der Treffer mit ``pad`` Zeichen Umgebung, damit jede Zuordnung von Hand prüfbar ist."""
    return haystack[max(0, start - pad) : end + pad].strip()


def _parties_in(haystack: str, patterns: Patterns) -> tuple[tuple[str, ...], str]:
    """(Schlüssel in der Reihenfolge der Settings, Auszug um den ersten Treffer)."""
    found: list[str] = []
    first: tuple[int, int] | None = None
    for key, pattern in patterns.parties:
        match = pattern.search(haystack)
        if match is None:
            continue
        found.append(key)
        if first is None or match.start() < first[0]:
            first = (match.start(), match.end())
    if first is None:
        return (), ""
    # Dedupliziert und in Settings-Reihenfolge: stünde ein Schlüssel zweimal in der Parteiliste,
    # käme er sonst zweimal in ``parteien`` (crosshair, 2026-10-12). Der Settings-Validator
    # verbietet doppelte Schlüssel, der Vertrag hängt aber nicht daran.
    return patterns.in_settings_order(found), _excerpt(haystack, *first)


def _attribution_is_consistent(
    paper_type: str | None,
    name: str | None,
    text_head: str,
    patterns: Patterns,
    originator_organizations: Sequence[str] = (),
    result: Classification | None = None,
) -> bool:
    assert result is not None
    parteien = result.parteien
    # Die Teilmenge wird vor der Sortierung geprüft: ein unbekannter Schlüssel ist eine verletzte
    # Bedingung, kein ValueError in der Sortierfunktion (crosshair, 2026-10-12).
    return (
        result.art in URHEBER_ARTEN
        and result.quelle in QUELLEN
        and set(parteien) <= set(patterns.keys)
        and parteien == patterns.in_settings_order(parteien)
        and (result.art == "Fraktion" or not parteien)
        and (result.quelle != "" or result.art == "unbekannt")
    )


# deal.safe statt deal.pure: deals has()-Patcher fasst socket und stdout prozessweit an und ist
# nicht reentrant, und diese Funktion läuft je Dokument (CLAUDE.md, „Nie"). Die Vor- und
# Nachbedingungen bleiben und machen sie zum Kandidaten für crosshair (nox -s verify).
@deal.safe
@deal.pre(
    lambda paper_type, name, text_head, patterns, originator_organizations=(): (
        patterns.head_chars > 0 and patterns.window_chars > 0
    )
)
@deal.ensure(_attribution_is_consistent, message="eine Klasse, sortierte Parteien aus den Settings")
def classify_document(
    paper_type: str | None,
    name: str | None,
    text_head: str,
    patterns: Patterns,
    originator_organizations: Sequence[str] = (),
) -> Classification:
    """Die Zuordnung eines Dokuments; rein, nur aus den vier Feldern und den Mustern.

    ``text_head`` ist schon auf ``patterns.head_chars`` gekürzt und kleingeschrieben (so liegt der
    Text im Korpus); ``paper_type`` wird als ganzer Wert verglichen und sonst kleingeschrieben.
    """
    keys, url = patterns.parties_for_urls(originator_organizations)
    if keys:
        return Classification("Fraktion", keys, "oparl", url)

    typ = paper_type or ""
    if typ in patterns.admin_types:
        return Classification("Verwaltung", (), "paper_type", typ)
    if typ in patterns.citizen_types:
        return Classification("Eingabe", (), "paper_type", typ)
    rest = _without_prefix(typ.lower(), patterns.motion_prefixes)
    if rest:
        keys, hit = _parties_in(rest, patterns)
        if keys:
            return Classification("Fraktion", keys, "paper_type", hit)

    title = (name or "").lower()
    if patterns.fraction is not None and patterns.fraction.search(title):
        keys, hit = _parties_in(title, patterns)
        if keys:
            return Classification("Fraktion", keys, "name", hit)
        joint = patterns.joint.search(title) if patterns.joint is not None else None
        if joint is not None:
            return Classification("Fraktion", (), "name", _excerpt(title, *joint.span()))

    head = text_head[: patterns.head_chars]
    found = patterns.text.search(head) if patterns.text is not None else None
    if found is not None:
        pad = patterns.window_chars
        window = head[max(0, found.start() - pad) : found.end() + pad]
        keys, hit = _parties_in(window, patterns)
        if keys:
            return Classification("Fraktion", keys, "text", hit)
        # Der Kopf sagt „eine Fraktion", nennt sie aber nicht. Die Klasse steht damit fest, der
        # Urheber nicht: das schwache Titel-Tor darf ihn noch nennen (BV3/134/2025: der Kopf
        # trifft „beantragenden fraktionen", der Titel nennt alle drei Parteien in der Klammer).
        # Die Personenmarker bleiben außen vor, sie widersprächen der schon gesetzten Klasse.
        keys, hit = _parties_in_bracket(title, patterns)
        if keys:
            return Classification("Fraktion", keys, "name", hit)
        return Classification("Fraktion", (), "text", _excerpt(head, *found.span()))

    person = patterns.person.search(title) if patterns.person is not None else None
    if person is not None:
        return Classification("Person", (), "name", _excerpt(title, *person.span()))

    # Zuletzt das schwache Tor: eine Antragsklammer im Titel, die eine Partei ohne das Wort
    # „Fraktion" nennt („(Antrag BÜNDNIS 90/DIE GRÜNEN)"). Es steht hinter den Personenmarkern,
    # damit „(Antrag Herr Lemmer-Freie Wähler)" Person bleibt wie „Herrn Salinger; AfD".
    keys, hit = _parties_in_bracket(title, patterns)
    if keys:
        return Classification("Fraktion", keys, "name", hit)
    return Classification("unbekannt", (), "", "")


def _parties_in_bracket(title: str, patterns: Patterns) -> tuple[tuple[str, ...], str]:
    """Die Parteien einer Antragsklammer im Titel („(Antrag BÜNDNIS 90/DIE GRÜNEN, CDU, SPD)")."""
    bracket = patterns.name_party.search(title) if patterns.name_party is not None else None
    return _parties_in(bracket.group(0), patterns) if bracket is not None else ((), "")


def _without_prefix(value: str, prefixes: Sequence[str]) -> str:
    """``"haushaltsantrag cdu/grüne"`` ohne das längste passende Präfix: ``"cdu/grüne"``."""
    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix) :].strip()
    return value


def _one_row_per_corpus_id(
    corpus: pl.DataFrame,
    originators: Originators,
    organizations: Sequence[OparlOrganization] = (),
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return one_row_per_document(result, corpus.get_column("id").to_list())


def _classes_and_parties_are_from_the_settings(
    corpus: pl.DataFrame,
    originators: Originators,
    organizations: Sequence[OparlOrganization] = (),
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    keys = set(originators.all_keys)
    arten = set(result.get_column(ART).unique().to_list())
    quellen = set(result.get_column(QUELLE).unique().to_list())
    parteien = result.get_column(PARTEIEN).to_list()
    return (
        arten <= set(URHEBER_ARTEN)
        and quellen <= set(QUELLEN)
        and all(set(items) <= keys for items in parteien)
        and all(len(items) == len(set(items)) for items in parteien)
    )


def _only_fractions_name_parties(
    corpus: pl.DataFrame,
    originators: Originators,
    organizations: Sequence[OparlOrganization] = (),
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    other = result.filter(pl.col(ART) != "Fraktion")
    return bool((other.get_column(PARTEIEN).list.len() == 0).all())


@deal.pre(
    lambda corpus, originators, organizations=(): has_columns(
        corpus, "id", "paper_type", "name", "text"
    )
)
@deal.ensure(_one_row_per_corpus_id, message="eine Zeile je Korpus-ID, nach id sortiert")
@deal.ensure(
    _classes_and_parties_are_from_the_settings, message="Klassen und Parteien aus den Settings"
)
@deal.ensure(_only_fractions_name_parties, message="nur Fraktionen nennen Parteien")
def classify_originators(
    corpus: pl.DataFrame,
    originators: Originators,
    organizations: Sequence[OparlOrganization] = (),
) -> pl.DataFrame:
    """Je Korpus-ID die Klasse, die Parteien, die Quelle und die getroffene Zeichenkette.

    ``organizations`` sind die Objekte aus ``raw/organizations.json``, falls der Netzschritt
    ``organizations`` lief; ohne sie greifen nur die URL-Endungen aus den Settings, und der Schritt
    läuft auch aus der Referenz.
    """
    patterns = Patterns.from_settings(originators).with_organizations(organizations)
    needed = corpus.select(
        "id",
        "paper_type",
        "name",
        pl.col("text").str.slice(0, patterns.head_chars).alias("head"),
        *(
            [pl.col("originator_organization")]
            if "originator_organization" in corpus.columns
            else [pl.lit([], dtype=pl.List(pl.String)).alias("originator_organization")]
        ),
    ).sort("id")
    rows = [
        (
            row["id"],
            *_as_tuple(
                classify_document(
                    row["paper_type"],
                    row["name"],
                    row["head"] or "",
                    patterns,
                    row["originator_organization"] or (),
                )
            ),
        )
        for row in needed.iter_rows(named=True)
    ]
    return pl.DataFrame(rows, schema=ATTRIBUTION_SCHEMA, orient="row")


def _as_tuple(found: Classification) -> tuple[str, list[str], str, str]:
    return found.art, list(found.parteien), found.quelle, found.treffer


def originator_figures(attribution: pl.DataFrame) -> dict[str, int]:
    """Zähler je Klasse über alle Dokumente, jede Klasse mit Eintrag (auch die leeren)."""
    found = attribution.group_by(ART).len()
    by_class = dict(
        zip(found.get_column(ART).to_list(), found.get_column("len").to_list(), strict=True)
    )
    return {art: int(by_class.get(art, 0)) for art in URHEBER_ARTEN}


def documents_per_party(attribution: pl.DataFrame, parties: Iterable[Party]) -> dict[str, int]:
    """Dokumente je Partei (Mehrfachnennung: ein Papier mit zwei Parteien zählt für beide)."""
    exploded = attribution.select(pl.col(PARTEIEN).explode().alias(PARTEI)).drop_nulls()
    found = exploded.group_by(PARTEI).len()
    counts = dict(
        zip(found.get_column(PARTEI).to_list(), found.get_column("len").to_list(), strict=True)
    )
    return {p.key: int(counts.get(p.key, 0)) for p in parties}


# --- Kennzahlen je Wahlbezirk und Partei ----------------------------------------------------------


def _partition_adds_up(
    results: pl.DataFrame,
    documents: pl.DataFrame,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    total = sum(
        (pl.col(column) for column in KLASSEN_SPALTEN[1:]), start=pl.col(KLASSEN_SPALTEN[0])
    )
    return bool(result.select(total == pl.col(HITS)).to_series().all())


@deal.pre(
    lambda results, documents: (
        has_columns(results, DISTRICT, PAPER_IDS, HITS) and has_columns(documents, "id", ART)
    )
)
@deal.post(lambda result: result.columns == [DISTRICT, HITS, *KLASSEN_SPALTEN])
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.ensure(
    _partition_adds_up,
    message="die fünf Urheberklassen summieren je Wahlbezirk zu anzahl_treffer",
)
@deal.ensure(
    lambda results, documents, result: result.height == results.height,
    message="nur Wahlbezirke der Auswertung, jeder einmal",
)
@deal.raises(SchemaError)
def originators_by_district(results: pl.DataFrame, documents: pl.DataFrame) -> pl.DataFrame:
    """Je Wahlbezirk die Verteilung der Treffer auf die fünf Urheberklassen.

    Der Vertrag ist die Partition: die Summe der Klassen ist die ``anzahl_treffer`` der Auswertung.
    Fehlt eine ``paper_id`` der Auswertung in ``documents``, ist das ein Schemafehler und keine
    stillschweigende Null.
    """
    pairs = results.select(DISTRICT, PAPER_IDS).explode(PAPER_IDS).rename({PAPER_IDS: "id"})
    missing = pairs.join(documents.select("id"), on="id", how="anti")
    if missing.height:
        raise SchemaError(
            f"{missing.height} Dokument-IDs der Auswertung fehlen in der Urheber-Tabelle, "
            f"zum Beispiel {missing.get_column('id').head(3).to_list()}; "
            "lief der Schritt parties auf demselben Korpus?"
        )
    counted = (
        pairs.join(documents.select("id", ART), on="id", how="inner")
        .group_by(DISTRICT, ART)
        .len()
        .pivot(ART, index=DISTRICT, values="len")
    )
    return (
        results.select(DISTRICT, HITS)
        .join(counted, on=DISTRICT, how="left")
        .with_columns(
            *(
                pl.col(art).fill_null(0).cast(pl.Int64).alias(column)
                if art in counted.columns
                else pl.lit(0, dtype=pl.Int64).alias(column)
                for art, column in zip(URHEBER_ARTEN, KLASSEN_SPALTEN, strict=True)
            )
        )
        .select(DISTRICT, HITS, *KLASSEN_SPALTEN)
        .sort(DISTRICT)
    )


PARTY_COLUMNS = (
    DISTRICT,
    PARTEI,
    HITS,
    "treffer_allein",
    "dokumente_partei",
    "anteil_dokumente",
    RATE,
    "stimmen",
    "stimmenanteil",
    "angetreten",
)


def _party_grid_is_complete(
    results: pl.DataFrame,
    documents: pl.DataFrame,
    voters: pl.DataFrame,
    parties: Sequence[Party],
    eligible_column: str = "Wahlberechtigte_insgesamt",
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return result.height == results.height * len(parties)


def _party_bounds_hold(
    results: pl.DataFrame,
    documents: pl.DataFrame,
    voters: pl.DataFrame,
    parties: Sequence[Party],
    eligible_column: str = "Wahlberechtigte_insgesamt",
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    # Zweite Schranke aus § 5 C des Plans: die Treffer einer Partei im Bezirk können nie mehr sein
    # als die Treffer des Bezirks (ein Dokument zählt je Bezirk einmal, auch mit mehreren Parteien).
    per_district = dict(results.select(DISTRICT, HITS).iter_rows())
    within_district = all(
        row[HITS] <= per_district.get(row[DISTRICT], 0) for row in result.iter_rows(named=True)
    )
    checks = result.select(
        ((pl.col("treffer_allein") >= 0) & (pl.col("treffer_allein") <= pl.col(HITS))).all(),
        (pl.col(HITS) <= pl.col("dokumente_partei")).all(),
        ((pl.col("anteil_dokumente") >= 0.0) & (pl.col("anteil_dokumente") <= 1.0)).all(),
        ((pl.col("stimmenanteil") >= 0.0) & (pl.col("stimmenanteil") <= 1.0)).all(),
        (pl.col("angetreten") == (pl.col("stimmen") > 0)).all(),
        (pl.col(RATE) >= 0.0).all(),
    )
    return within_district and all(checks.row(0))


def _documents_per_party_is_constant(
    results: pl.DataFrame,
    documents: pl.DataFrame,
    voters: pl.DataFrame,
    parties: Sequence[Party],
    eligible_column: str = "Wahlberechtigte_insgesamt",
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    found = result.group_by(PARTEI).agg(pl.col("dokumente_partei").n_unique())
    return bool((found.get_column("dokumente_partei") == 1).all())


@deal.pre(
    lambda results, documents, voters, parties, eligible_column="Wahlberechtigte_insgesamt": (
        has_columns(results, DISTRICT, PAPER_IDS, HITS)
        and has_columns(documents, "id", ART, PARTEIEN)
        and has_columns(voters, DISTRICT, eligible_column)
        and len(parties) > 0
    )
)
@deal.post(lambda result: list(result.columns) == list(PARTY_COLUMNS))
@deal.ensure(_party_grid_is_complete, message="genau |Bezirke| x |Parteien| Zeilen")
@deal.ensure(_party_bounds_hold, message="die Schranken je Partei und Bezirk")
@deal.ensure(_documents_per_party_is_constant, message="dokumente_partei ist je Partei konstant")
def party_hits(
    results: pl.DataFrame,
    documents: pl.DataFrame,
    voters: pl.DataFrame,
    parties: Sequence[Party],
    eligible_column: str = "Wahlberechtigte_insgesamt",
) -> pl.DataFrame:
    """Je Wahlbezirk und Partei: Treffer, Alleinurheber, Anteil, Quote, Stimmen, Stimmenanteil.

    Ein Dokument mit zwei Parteien zählt für jede voll (Entscheidung § 2 des Plans, Frage 4.2);
    ``treffer_allein`` ist die Gegenprobe über die Dokumente mit genau einem Urheber.
    ``angetreten`` ist falsch, wo die Partei keinen Wahlvorschlag hatte (Wahlbezirk 11 für Die
    Linke): ein Stimmenanteil von 0 heißt dort „nicht angetreten", nicht „keine Zustimmung".
    """
    keys = [p.key for p in parties]
    pairs = results.select(DISTRICT, PAPER_IDS).explode(PAPER_IDS).rename({PAPER_IDS: "id"})
    attributed = documents.select("id", PARTEIEN, alleine=pl.col(PARTEIEN).list.len() == 1)
    per_pair = (
        pairs.join(attributed, on="id", how="inner")
        .explode(PARTEIEN)
        .rename({PARTEIEN: PARTEI})
        .filter(pl.col(PARTEI).is_in(keys))
        .group_by(DISTRICT, PARTEI)
        .agg(pl.len().cast(pl.Int64).alias(HITS), pl.col("alleine").sum().alias("treffer_allein"))
    )
    totals = (
        documents.select(pl.col(PARTEIEN).explode().alias(PARTEI))
        .drop_nulls()
        .filter(pl.col(PARTEI).is_in(keys))
        .group_by(PARTEI)
        .agg(pl.len().cast(pl.Int64).alias("dokumente_partei"))
    )
    grid = results.select(DISTRICT).join(pl.DataFrame({PARTEI: keys}), how="cross")
    long_votes = _votes_long(voters, keys)
    return (
        grid.join(per_pair, on=[DISTRICT, PARTEI], how="left")
        .with_columns(
            pl.col(HITS).fill_null(0).cast(pl.Int64),
            pl.col("treffer_allein").fill_null(0).cast(pl.Int64),
        )
        .join(totals, on=PARTEI, how="left")
        .with_columns(pl.col("dokumente_partei").fill_null(0).cast(pl.Int64))
        .join(voters.select(DISTRICT, eligible_column), on=DISTRICT, how="inner")
        .join(long_votes, on=[DISTRICT, PARTEI], how="left")
        .with_columns(
            pl.when(pl.col("dokumente_partei") > 0)
            .then(pl.col(HITS) / pl.col("dokumente_partei"))
            .otherwise(0.0)
            .alias("anteil_dokumente"),
            (pl.col(HITS) / pl.col(eligible_column)).alias(RATE),
            pl.col("stimmen").fill_null(0).cast(pl.Int64),
            pl.col("stimmenanteil").fill_null(0.0),
        )
        .with_columns(angetreten=pl.col("stimmen") > 0)
        .select(*PARTY_COLUMNS)
        .sort([PARTEI, DISTRICT])
    )


def _votes_long(voters: pl.DataFrame, keys: Sequence[str]) -> pl.DataFrame:
    """Die Stimmen und Anteile der Wählertabelle in Langform: eine Zeile je Bezirk und Partei."""
    rows = [
        voters.select(
            DISTRICT,
            pl.lit(key, dtype=pl.String).alias(PARTEI),
            pl.col(f"{key}_Stimmen").cast(pl.Int64).alias("stimmen")
            if f"{key}_Stimmen" in voters.columns
            else pl.lit(0, dtype=pl.Int64).alias("stimmen"),
            pl.col(f"{key}_anteil").cast(pl.Float64).alias("stimmenanteil")
            if f"{key}_anteil" in voters.columns
            else pl.lit(0.0, dtype=pl.Float64).alias("stimmenanteil"),
        )
        for key in keys
    ]
    return pl.concat(rows) if rows else pl.DataFrame(schema={DISTRICT: pl.Int64, PARTEI: pl.String})


@dataclass(frozen=True)
class PartyCorrelation:
    """Je Partei der Zusammenhang zwischen Dokumentanteil und Stimmenanteil über die Bezirke."""

    key: str
    n: int  # Bezirke, in denen die Partei angetreten ist
    documents: int
    hits: int
    districts_hit: int
    r: float | None  # Pearson; None unter min_n oder ohne Streuung
    p: float | None
    rho: float | None  # Spearman, mitgeführt, nicht auf der Seite


@deal.pre(lambda party_results, min_n=3: min_n >= 3)
@deal.post(
    lambda result: all(
        c.r is None or (-1.0 <= c.r <= 1.0 and c.p is not None and 0.0 <= c.p <= 1.0)
        for c in result
    ),
    message="r in [-1, 1], p in [0, 1] oder beides None",
)
def party_correlations(party_results: pl.DataFrame, min_n: int = 3) -> tuple[PartyCorrelation, ...]:
    """Pearson r und p zwischen ``anteil_dokumente`` und ``stimmenanteil`` je Partei.

    Gerechnet nur über die Bezirke mit ``angetreten``; unter ``min_n`` Bezirken oder ohne Streuung
    in einer der beiden Reihen bleibt es bei ``None``. Spearman rho läuft mit, weil er bei 70
    Treffern über 41 Bezirke robuster ist; die Seite zeigt r und p.
    """
    found: list[PartyCorrelation] = []
    for key in party_results.get_column(PARTEI).unique(maintain_order=True).to_list():
        mine = party_results.filter(pl.col(PARTEI) == key)
        ran = mine.filter(pl.col("angetreten"))
        r = p = rho = None
        if ran.height >= min_n:
            x = ran.get_column("anteil_dokumente").to_numpy()
            y = ran.get_column("stimmenanteil").to_numpy()
            if len(set(x.tolist())) > 1 and len(set(y.tolist())) > 1:
                pearson = pearsonr(x, y)
                spearman = spearmanr(x, y)
                r, p = float(pearson.statistic), float(pearson.pvalue)
                rho = float(spearman.statistic)
        found.append(
            PartyCorrelation(
                key=str(key),
                n=ran.height,
                documents=int(mine.get_column("dokumente_partei").to_list()[0]),
                hits=int(mine.get_column(HITS).sum()),
                districts_hit=int(mine.filter(pl.col(HITS) > 0).height),
                r=r,
                p=p,
                rho=rho,
            )
        )
    return tuple(found)
