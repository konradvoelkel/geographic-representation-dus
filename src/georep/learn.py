"""``georep learn-bodies``: die Abbildung Organisation -> Gremium aus den Daten lernen (Punkt 58).

Die Beratungsfolge nennt Organisations-URLs, die Drucksachennummer nennt Kürzel. Wo eine Folge
**genau eine** Organisation nennt, sagt das Kürzel der Nummer, welche das ist -- und über alle
Dokumente einer Periode entsteht so die Tabelle ``[bodies.organizations]``, mit einer messbaren
Reinheit statt einer Vermutung. Gedruckt wird dreierlei:

1. der **Katalog**: je Organisation, die in einer Folge steht, ihre Dokumente, das gelernte Kürzel
   mit Reinheit und, wenn ``raw/organizations.json`` vorliegt, Kürzel, Klassifikation und Name vom
   Server (so entsteht die Tabelle für eine Stadt, deren Nummern kein Kürzel tragen);
2. der **TOML-Block** zum Einsetzen in das Profil;
3. die **Gegenprobe**: wie oft die Folge die Nummer bestätigt, wie oft sie ihr widerspricht, wie
   viele heute unbekannte Dokumente eine eindeutige Folge auflösen würde und wie viele
   mehrdeutig bleiben.

Geschrieben wird nichts. Die Tabelle gehört von Hand ins Profil, wie die Aliastabelle aus
Punkt 57: sie ist eine Behauptung über die Welt, und wer sie aufstellt, soll die Zahlen daneben
gesehen haben.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import polars as pl

from georep.analysis.parties import read_organizations
from georep.errors import MissingInputError
from georep.layout import Layout
from georep.oparl import OparlOrganization
from georep.prep.bodies import (
    BODY,
    CONSULTATION,
    ID,
    KIND,
    REFERENCE,
    UNKNOWN,
    BodyRules,
    classify_papers,
    merge_consultations,
    organization_key,
    resolve_organizations,
)
from georep.settings import Settings

EXAMPLES = 10  # so viele Zeilen zeigt die Liste der Unterschiede zur Tabelle im Profil


@dataclass(frozen=True)
class LearnedOrganization:
    """Eine Organisation der Beratungsfolge mit allem, was über sie bekannt ist."""

    key: str  # die beiden letzten Segmente der URL, der Schlüssel im Profil
    documents: int  # Dokumente, in deren Folge sie steht
    alone: int  # davon solche, deren Folge nur sie nennt und deren Nummer ein Kürzel trägt
    code: str  # das gelernte Kürzel; leer, wenn nichts zu lernen war
    pure: int  # Dokumente, die für dieses Kürzel stimmen
    short_name: str  # aus raw/organizations.json, wenn sie vorliegt
    classification: str
    name: str

    @property
    def purity(self) -> float:
        return self.pure / self.alone if self.alone else 0.0


@dataclass(frozen=True)
class LearnReport:
    """Was der Befehl gelernt hat; ``text()`` ist seine ganze Ausgabe."""

    profile: str
    documents: int
    with_consultation: int
    organizations: tuple[LearnedOrganization, ...]
    confirmed: int  # Nummer und eindeutige Folge nennen dasselbe Gremium
    conflicting: int
    resolvable: int  # heute unbekannt, und die Folge nennt genau ein Gremium
    ambiguous: int  # heute unbekannt, und die Folge nennt mehrere
    without: int  # heute unbekannt, und die Folge löst keines auf
    unknown: int  # heute unbekannt, insgesamt
    in_profile: dict[str, str]  # die Tabelle, die das Profil jetzt trägt

    @property
    def learned(self) -> tuple[LearnedOrganization, ...]:
        return tuple(entry for entry in self.organizations if entry.code)

    @property
    def purity(self) -> float:
        pure = sum(entry.pure for entry in self.learned)
        alone = sum(entry.alone for entry in self.learned)
        return pure / alone if alone else 0.0

    def table(self) -> str:
        head = (
            f"{'Organisation':<14}{'Dok.':>7}{'eindeutig':>11}{'Kürzel':>9}"
            f"{'Reinheit':>10}  Klassifikation und Name vom Server\n"
        )
        rows = []
        for entry in self.organizations:
            purity = f"{entry.purity:.1%}" if entry.alone else "—"
            server = " ".join(
                part for part in (entry.classification, entry.short_name, entry.name) if part
            )
            rows.append(
                f"{entry.key:<14}{entry.documents:>7}{entry.alone:>11}{entry.code or '—':>9}"
                f"{purity:>10}  {server}"
            )
        return head + "\n".join(rows) + "\n"

    def toml(self) -> str:
        """Der Block für das Profil; leer, wenn aus den Nummern nichts zu lernen war."""
        if not self.learned:
            return ""
        lines = [
            "[bodies.organizations]   # Organisation der Beratungsfolge -> Kürzel; "
            f"gelernt mit `georep --profile {self.profile} learn-bodies`",
        ]
        for entry in sorted(self.learned, key=lambda e: (-e.alone, e.key)):
            lines.append(
                f'"{entry.key}" = "{entry.code}"'.ljust(26)
                + f"# {entry.alone} Dokumente nennen nur sie, {entry.pure} davon "
                f"als {entry.code}" + (f" ({entry.name})" if entry.name else "")
            )
        return "\n".join(lines) + "\n"

    def differences(self) -> list[str]:
        """Wo die Tabelle des Profils vom Gelernten abweicht; leer heißt „deckt sich"."""
        learned = {entry.key: entry.code for entry in self.learned}
        profile = {organization_key(key): code for key, code in self.in_profile.items()}
        notes = [
            f"  {key}: Profil {profile[key]}, gelernt {learned[key]}"
            for key in sorted(set(profile) & set(learned))
            if profile[key] != learned[key]
        ]
        notes += [
            f"  {key}: nur im Profil ({profile[key]})"
            for key in sorted(set(profile) - set(learned))
        ]
        notes += [
            f"  {key}: nur gelernt ({learned[key]})" for key in sorted(set(learned) - set(profile))
        ]
        return notes

    def text(self) -> str:
        parts = [
            f"Profil {self.profile}: {self.documents} Dokumente, {self.with_consultation} mit "
            f"Beratungsfolge, {len(self.organizations)} verschiedene Organisationen darin\n",
            self.table(),
        ]
        if self.learned:
            parts.append(
                f"\nGelernt: {len(self.learned)} Organisationen aus "
                f"{sum(e.alone for e in self.learned)} Dokumenten mit genau einer, Reinheit "
                f"{self.purity:.1%}\n"
            )
            parts.append("\n" + self.toml())
        else:
            parts.append(
                "\nAus den Drucksachennummern ist nichts zu lernen (kein Dokument mit genau einer "
                "Organisation trägt ein Kürzel). Die Tabelle entsteht dann aus den Namen oben, von "
                "Hand und mit einer Zeile Begründung je Eintrag.\n"
            )
        parts.append(
            f"\nGegenprobe mit der Tabelle, die das Profil jetzt trägt ({len(self.in_profile)} "
            "Einträge):\n"
            f"  bestätigt {self.confirmed}, Widerspruch {self.conflicting}\n"
            f"  unbekannt {self.unknown}: davon eindeutig auflösbar {self.resolvable}, "
            f"mehrdeutig {self.ambiguous}, ohne auflösbare Folge {self.without}\n"
        )
        notes = self.differences()
        if notes:
            parts.append(
                "Unterschiede zur Tabelle im Profil:\n" + "\n".join(notes[:EXAMPLES]) + "\n"
            )
            if len(notes) > EXAMPLES:
                parts.append(f"  … und {len(notes) - EXAMPLES} weitere\n")
        return "".join(parts)


def _catalogue(layout: Layout) -> dict[str, OparlOrganization]:
    """``raw/organizations.json`` je Schlüssel; leer, wenn der Netzschritt nie lief."""
    return {organization_key(o.id): o for o in read_organizations(layout.organizations)}


def learn_bodies(layout: Layout, settings: Settings, *, min_documents: int = 1) -> LearnReport:
    """Die Tabelle aus Korpus, Paket und Nummern lernen und die Gegenprobe rechnen."""
    if not layout.corpus.is_file():
        raise MissingInputError(
            f"{layout.corpus} fehlt; `georep run corpus` baut den Korpus dieses Profils."
        )
    corpus = pl.read_parquet(layout.corpus, columns=[ID, REFERENCE, CONSULTATION])
    extra = (
        pl.read_parquet(layout.consultations, columns=[ID, CONSULTATION])
        if settings.bodies.consultations is not None and layout.consultations.is_file()
        else None
    )
    folge = merge_consultations(corpus, extra)
    lists = dict(
        zip(
            folge.get_column(ID).to_list(),
            folge.get_column(CONSULTATION).to_list(),
            strict=True,
        )
    )
    # Die Nummern allein, ohne die Tabelle des Profils: sonst lernte der Befehl von sich selbst.
    rules = BodyRules.from_settings(settings.bodies.model_copy(update={"organizations": {}}))
    by_number = classify_papers(corpus.select(ID, REFERENCE), rules)

    votes: dict[str, Counter[str]] = {}
    documents: Counter[str] = Counter()
    for row in by_number.iter_rows(named=True):
        organizations = lists.get(str(row[ID])) or []
        keys = {organization_key(str(url)) for url in organizations}
        for key in keys:
            documents[key] += 1
        if len(keys) == 1 and row[BODY]:
            votes.setdefault(next(iter(keys)), Counter())[str(row[BODY])] += 1

    catalogue = _catalogue(layout)
    organizations = []
    for key in sorted(documents, key=lambda k: (-documents[k], k)):
        counted = votes.get(key, Counter())
        best = counted.most_common(1)
        entry = catalogue.get(key)
        organizations.append(
            LearnedOrganization(
                key=key,
                documents=documents[key],
                alone=sum(counted.values()),
                code=best[0][0] if best and sum(counted.values()) >= min_documents else "",
                pure=best[0][1] if best else 0,
                short_name=(entry.short_name or "") if entry else "",
                classification=(entry.classification or "") if entry else "",
                name=(entry.name or "") if entry else "",
            )
        )
    return LearnReport(
        profile=settings.default_profile,
        documents=corpus.height,
        with_consultation=int((folge.get_column(CONSULTATION).list.len() > 0).sum()),
        organizations=tuple(organizations),
        in_profile=dict(settings.bodies.organizations),
        **_cross_check(by_number, lists, settings),
    )


def _cross_check(
    by_number: pl.DataFrame, lists: dict[str, list[str]], settings: Settings
) -> dict[str, int]:
    """Die Gegenprobe mit der Tabelle, die das Profil **jetzt** trägt (nicht mit der gelernten).

    So sagt der Befehl, was die Tabelle im Profil heute leistet, und nicht, was sie leisten
    könnte: die gelernte Tabelle ist per Konstruktion mit sich selbst einig.
    """
    mapping = dict(settings.bodies.organizations)
    confirmed = conflicting = resolvable = ambiguous = without = unknown = 0
    for row in by_number.iter_rows(named=True):
        codes = resolve_organizations(lists.get(str(row[ID])) or [], mapping)
        if row[KIND] == UNKNOWN:
            unknown += 1
            if len(codes) == 1:
                resolvable += 1
            elif codes:
                ambiguous += 1
            else:
                without += 1
        elif len(codes) == 1:
            confirmed += codes[0] == row[BODY]
            conflicting += codes[0] != row[BODY]
    return {
        "confirmed": confirmed,
        "conflicting": conflicting,
        "resolvable": resolvable,
        "ambiguous": ambiguous,
        "without": without,
        "unknown": unknown,
    }
