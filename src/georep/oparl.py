"""OParl 1.1 als Vertrag: die Objekte, die wir vom Ratsinformationssystem lesen.

Spezifikation: https://oparl.org/spezifikation/online-ansicht/ (Paper, File, Organization,
Paginierung). Validiert an der Systemgrenze, damit der Rest des Codes mit Typen statt mit
``.get()``-Ketten arbeitet. Felder, die wir nicht brauchen, werden ignoriert; ``tests/fixtures/oparl``
hält echte Antworten fest (Paper-Seite vom 2026-10-09, Organisationen vom 2026-10-11), und ein Test
schlägt an, sobald der Server Schlüssel liefert, die das Modell nicht kennt.

Die Urheberfelder ``originatorPerson``, ``originatorOrganization`` und ``underDirectionOf`` sind
Tupel von URLs (OParl 1.1, Paper); der Server der ITK Rheinland liefert sie für Düsseldorf nicht
(Stand 2026-10-09), das Modell trägt sie trotzdem, damit die Quelle ``oparl`` in
``georep.analysis.parties`` ohne Codeänderung greift, sobald sie gefüllt sind (Option 04).

Fundament F6 (2026-11-23) ergänzt Meeting, AgendaItem, Consultation, Person und Membership mit
einem gemeinsamen Umschlag für jede Liste (``ListPage``); ``tests/fixtures/http`` hält die Antworten
der Netzstichprobe fest. Personen liest das Modell ohne Kontaktdaten (``PERSON_PRIVATE_KEYS``).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Oparl(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class OparlFile(_Oparl):
    """oparl:File. ``download_url`` ist der direkte Download, ``access_url`` die Ansicht."""

    id: str
    type: str | None = None
    name: str | None = None
    file_name: str | None = Field(default=None, alias="fileName")
    mime_type: str | None = Field(default=None, alias="mimeType")
    date: dt.date | None = None
    size: int | None = None
    sha1_checksum: str | None = Field(default=None, alias="sha1Checksum")
    sha512_checksum: str | None = Field(default=None, alias="sha512Checksum")
    access_url: str | None = Field(default=None, alias="accessUrl")
    download_url: str | None = Field(default=None, alias="downloadUrl")
    # F6: das Einzelobjekt nennt die Sitzungen, zu denen die Datei gehört (eingebettet fehlt es)
    meeting: tuple[str, ...] = ()
    created: dt.datetime | None = None
    modified: dt.datetime | None = None
    deleted: bool = False


class OparlPaper(_Oparl):
    """oparl:Paper: Vorlage, Antrag, Anfrage. ``date`` ist das Datum der Vorlage."""

    id: str
    type: str | None = None
    body: str | None = None
    name: str | None = None
    reference: str | None = None
    date: dt.date | None = None
    paper_type: str | None = Field(default=None, alias="paperType")
    main_file: OparlFile | None = Field(default=None, alias="mainFile")
    auxiliary_file: list[OparlFile] = Field(default_factory=list, alias="auxiliaryFile")
    consultation: list[dict[str, Any]] = Field(default_factory=list)
    originator_person: tuple[str, ...] = Field(default=(), alias="originatorPerson")
    originator_organization: tuple[str, ...] = Field(default=(), alias="originatorOrganization")
    under_direction_of: tuple[str, ...] = Field(default=(), alias="underDirectionOf")
    web: str | None = None
    created: dt.datetime | None = None
    modified: dt.datetime | None = None
    deleted: bool = False

    @property
    def has_originator(self) -> bool:
        """Mindestens eines der drei Urheberfelder ist gefüllt (Zähler im Abrufbericht)."""
        return bool(
            self.originator_person or self.originator_organization or self.under_direction_of
        )

    @property
    def consultation_organizations(self) -> tuple[str, ...]:
        """Die beratenden Gremien aus ``consultation[].organization``, sortiert und eindeutig.

        Der Server schreibt eine Liste von URLs je Beratung, die Spezifikation erlaubt auch eine
        einzelne; beides wird gelesen. Das ist das Gremium, nicht der Urheber (Option 5).
        """
        found: set[str] = set()
        for entry in self.consultation:
            value = entry.get("organization")
            if isinstance(value, str):
                found.add(value)
            elif isinstance(value, list):
                found.update(v for v in value if isinstance(v, str))
        return tuple(sorted(found))

    @property
    def consultations(self) -> tuple[OparlConsultation, ...]:
        """Die eingebetteten Beratungen, typisiert, in der Reihenfolge des Servers (F6).

        Jede nennt Sitzung und Tagesordnungspunkt (98,9 % in der Hauptperiode): der Weg vom
        Paper zum Ergebnis braucht damit keine Paper-Abfrage mehr, nur die Tagesordnung.
        """
        return tuple(OparlConsultation.model_validate(entry) for entry in self.consultation)

    @property
    def primary_file(self) -> OparlFile | None:
        """``mainFile``, sonst die erste ``auxiliaryFile``; so hat es die Arbeit gehalten."""
        if self.main_file is not None:
            return self.main_file
        return self.auxiliary_file[0] if self.auxiliary_file else None

    @property
    def download_url(self) -> str | None:
        primary = self.primary_file
        return primary.download_url if primary is not None else None

    def in_period(self, start: dt.date, end: dt.date | None) -> bool:
        """Beide Grenzen einschließlich; ohne Ende (laufende Periode) ab ``start``; ohne Datum nie."""
        if self.date is None:
            return False
        return start <= self.date and (end is None or self.date <= end)


class OparlOrganization(_Oparl):
    """oparl:Organization: Fraktion, Ausschuss, Bezirksvertretung, Gremium.

    Der Server der ITK Rheinland setzt ``classification`` („Fraktion", „Ausschuss", „Bezirk",
    „Gremium" oder nichts), nie ``organizationType``; ``membership`` sind URLs.
    """

    id: str
    type: str | None = None
    body: str | None = None
    name: str | None = None
    short_name: str | None = Field(default=None, alias="shortName")
    classification: str | None = None
    organization_type: str | None = Field(default=None, alias="organizationType")
    start_date: dt.date | None = Field(default=None, alias="startDate")
    end_date: dt.date | None = Field(default=None, alias="endDate")
    membership: tuple[str, ...] = ()
    sub_organization_of: str | None = Field(default=None, alias="subOrganizationOf")
    meeting: str | None = None
    location: dict[str, Any] | None = None
    web: str | None = None
    created: dt.datetime | None = None
    modified: dt.datetime | None = None
    deleted: bool = False

    def active_on(self, day: dt.date) -> bool:
        """Besteht die Organisation an diesem Tag? Ohne Daten gilt sie als immer bestehend."""
        after_start = self.start_date is None or self.start_date <= day
        before_end = self.end_date is None or day <= self.end_date
        return after_start and before_end


class Pagination(_Oparl):
    total_elements: int | None = Field(default=None, alias="totalElements")
    elements_per_page: int | None = Field(default=None, alias="elementsPerPage")
    current_page: int | None = Field(default=None, alias="currentPage")
    total_pages: int | None = Field(default=None, alias="totalPages")


class Links(_Oparl):
    first: str | None = None
    self_: str | None = Field(default=None, alias="self")
    # F6: ab Seite 2 nennt der Server auch die vorige (Sitzungsliste, Seite 4, 2026-11-23)
    prev: str | None = None
    next: str | None = None
    last: str | None = None


class PaperPage(_Oparl):
    """Eine Seite der Paper-Liste; ``links.next`` fehlt auf der letzten."""

    data: list[OparlPaper]
    pagination: Pagination | None = None
    links: Links = Links()


class OrganizationPage(_Oparl):
    """Eine Seite der Organisationsliste; Düsseldorf hat eine (58 Objekte, 2026-10-11)."""

    data: list[OparlOrganization]
    pagination: Pagination | None = None
    links: Links = Links()


def known_aliases(model: type[BaseModel]) -> set[str]:
    """Die JSON-Schlüssel, die ein Modell versteht (Alias oder Feldname)."""
    return {field.alias or name for name, field in model.model_fields.items()}


# --- Fundament F6: Sitzungen, Tagesordnung, Beratungen, Personen --------------------------------
#
# Gemessen am 2026-11-23 an einer Netzstichprobe (zwei Seiten der Sitzungsliste mit 400 Sitzungen
# und 9 495 Tagesordnungspunkten, je eine Seite Personen, Mitgliedschaften und
# Tagesordnungspunkte; tests/fixtures/http/README.md) und an den 469 Paper-Seiten des Vollabrufs
# vom 2026-10-13/14 im HTTP-Cache. Die Befunde stehen je Klasse; die Zahlen in
# docs/runbook-sitzungen.md, § 2.


class OparlObject(_Oparl):
    """Was jedes Objekt einer OParl-Liste trägt: Kennung, Zeitstempel, Löschmarke.

    ``georep.sources.oparl.fetch_objects`` liest damit jede Liste gleich: entdoppeln über
    ``id``, Gelöschte melden, ``modified_since`` aus dem jüngsten ``modified`` setzen.
    """

    id: str
    type: str | None = None
    web: str | None = None
    created: dt.datetime | None = None
    modified: dt.datetime | None = None
    deleted: bool = False


class OparlConsultation(OparlObject):
    """oparl:Consultation: ein Paper in einer Sitzung, unter einem Tagesordnungspunkt.

    Der Server bettet die Beratungen in jedes Paper ein (``OparlPaper.consultations``) und listet
    sie unter ``…/consultations``. In den 25 675 Beratungen der Paper der Hauptperiode sind
    ``meeting`` und ``agendaItem`` zu 98,9 % gefüllt, ``organization`` zu 98,3 %,
    ``authoritative`` zu 91,4 % (sonst fehlt es, ``false`` kommt nicht vor), ``role`` immer.
    ``agendaItem`` nennt den **letzten** Punkt: wird eine Vorlage vertagt, zeigen beide Punkte auf
    dieselbe Beratung, die Beratung aber nur auf den späteren.
    """

    paper: str | None = None
    agenda_item: str | None = Field(default=None, alias="agendaItem")
    meeting: str | None = None
    organization: tuple[str, ...] = ()
    authoritative: bool | None = None
    role: str | None = None

    @field_validator("organization", mode="before")
    @classmethod
    def _one_or_many(cls, value: object) -> object:
        """Die Spezifikation verlangt eine Liste; eine einzelne URL wird ebenso gelesen."""
        return (value,) if isinstance(value, str) else value


class OparlAgendaItem(OparlObject):
    """oparl:AgendaItem: ein Tagesordnungspunkt, ``result`` ist das Ergebnis in Worten.

    Der Server füllt ``result`` (80,2 % der Punkte auf Seite 4 der Sitzungsliste, 96,5 % der
    Punkte mit Beratung), aus einem festen Wortschatz („einstimmig beschlossen", „mehrheitlich
    abgelehnt", „vertagt", „zur Kenntnis genommen" …). ``resolutionText`` und ``resolutionFile``
    setzt er nie (0 von 9 495), ``start`` und ``end`` auch nicht; ``public`` ist immer wahr, die
    Liste enthält nur öffentliche Punkte. ``consultation`` ist eine URL: über sie, nicht über
    ``OparlConsultation.agenda_item``, findet man alle Punkte einer Beratung.
    """

    meeting: str | None = None
    number: str | None = None
    order: int | None = None
    name: str | None = None
    public: bool | None = None
    consultation: str | None = None
    result: str | None = None
    resolution_text: str | None = Field(default=None, alias="resolutionText")
    resolution_file: OparlFile | None = Field(default=None, alias="resolutionFile")
    auxiliary_file: list[OparlFile] = Field(default_factory=list, alias="auxiliaryFile")
    start: dt.datetime | None = None
    end: dt.datetime | None = None


class OparlMeeting(OparlObject):
    """oparl:Meeting mit eingebetteter Tagesordnung (``agendaItem``).

    Befunde: ``cancelled`` und ``meetingState`` setzt der Server nie. ``invitation``,
    ``resultsProtocol`` und ``verbatimProtocol`` sind, wo gesetzt, **dieselbe** Datei, und die
    ist ein Nachtrag zur Tagesordnung („NachtragsTO", „1. Nachlieferung"), keine Niederschrift;
    die Niederschrift steht unter ``auxiliaryFile`` („Niederschrift Ö"). ``modified`` der
    Sitzung folgt ihrer Tagesordnung nicht: bei 69 von 314 Sitzungen mit Tagesordnung ist ein
    Punkt jünger als die Sitzung, um bis zu 245 Tage — ``modified_since`` auf der Sitzungsliste
    verpasste also nachgetragene Ergebnisse.
    """

    name: str | None = None
    meeting_state: str | None = Field(default=None, alias="meetingState")
    cancelled: bool | None = None
    start: dt.datetime | None = None
    end: dt.datetime | None = None
    location: dict[str, Any] | None = None
    organization: tuple[str, ...] = ()
    participant: tuple[str, ...] = ()
    invitation: OparlFile | None = None
    results_protocol: OparlFile | None = Field(default=None, alias="resultsProtocol")
    verbatim_protocol: OparlFile | None = Field(default=None, alias="verbatimProtocol")
    auxiliary_file: list[OparlFile] = Field(default_factory=list, alias="auxiliaryFile")
    agenda_item: list[OparlAgendaItem] = Field(default_factory=list, alias="agendaItem")

    def starts_on_or_after(self, day: dt.date) -> bool:
        """Beginnt die Sitzung an diesem Tag oder später? Ohne Beginn gilt sie als ja.

        Der Tag ist der der Ortszeit, die der Server mitschickt (``+01:00``, ``+02:00``).
        """
        return self.start is None or self.start.date() >= day


class OparlMembership(OparlObject):
    """oparl:Membership: eine Person in einer Organisation, mit Rolle und Zeitraum.

    Gefüllt (630 eingebettete Mitgliedschaften der ersten Personenseite): ``role`` und
    ``startDate`` immer, ``votingRight`` zu 63,8 % (sonst fehlt es), ``endDate`` zu 7,3 %,
    ``onBehalfOf`` nie. Die Rolle ist freier Text („ordentliches Mitglied",
    „stellvertretendes Bürgermitglied", „Fraktion Mitarbeiter/in" …).
    """

    person: str | None = None
    organization: str | None = None
    role: str | None = None
    voting_right: bool | None = Field(default=None, alias="votingRight")
    start_date: dt.date | None = Field(default=None, alias="startDate")
    end_date: dt.date | None = Field(default=None, alias="endDate")
    on_behalf_of: str | None = Field(default=None, alias="onBehalfOf")

    def active_on(self, day: dt.date) -> bool:
        """Besteht die Mitgliedschaft an diesem Tag? Beide Grenzen einschließlich."""
        after_start = self.start_date is None or self.start_date <= day
        before_end = self.end_date is None or day <= self.end_date
        return after_start and before_end


# Was der Server zu einer Person außerdem schickt und das Modell absichtlich **nicht** liest:
# Telefon, E-Mail, Anschrift, Lebenslauf. Personen kommen in diesem Projekt nur in ihrer
# öffentlichen Rolle vor (docs/plan-vorverarbeitung-2026-11.md, § 1); was das Modell nicht kennt,
# steht in keiner Datei eines Laufs. Ein Test hält beides fest.
PERSON_PRIVATE_KEYS = frozenset(
    {"phone", "email", "location", "locationObject", "life", "lifeSource"}
)


class OparlPerson(OparlObject):
    """oparl:Person mit eingebetteten Mitgliedschaften, ohne Kontaktdaten.

    Die Liste nennt alle Personen des Bodys, auch Fraktionsmitarbeiter, sachkundige Einwohner und
    Verwaltung (die Rolle steht an der Mitgliedschaft). Die eingebetteten Mitgliedschaften sind
    dieselben Objekte wie die der Liste ``…/memberships`` (80 von 80 gleich); ``modified`` der
    Person folgt ihnen aber nicht (91 von 198 Personen haben eine jüngere Mitgliedschaft).
    """

    body: str | None = None
    name: str | None = None
    family_name: str | None = Field(default=None, alias="familyName")
    given_name: str | None = Field(default=None, alias="givenName")
    form_of_address: str | None = Field(default=None, alias="formOfAddress")
    affix: str | None = None
    title: tuple[str, ...] = ()
    gender: str | None = None
    status: tuple[str, ...] = ()
    membership: list[OparlMembership] = Field(default_factory=list)


class ListPage(_Oparl):
    """Eine Seite irgendeiner OParl-Liste; die Objekte prüft das Modell ihrer Art.

    Ein Umschlag statt einer Klasse je Liste: ``fetch_objects`` liest damit jede Liste, und die
    Objekte gehen einzeln durch ``model_validate`` ihrer Klasse.
    """

    data: list[dict[str, Any]]
    pagination: Pagination | None = None
    links: Links = Links()
