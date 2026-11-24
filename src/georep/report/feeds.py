"""Atom-Feeds je Wahlbezirk (Vorhaben 17): der Text eines Feeds und seine Prüfung, rein und ohne Dateien.

Ein Feed nennt die neuesten Dokumente, in denen ein Name aus dem Wörterbuch eines Wahlbezirks
vorkommt (dieselbe Zuordnung wie die Zahl auf der Seite), und je Dokument nur, was
``site/data/dokumente.json`` schon veröffentlicht: Kennung, Drucksache und Titel, Datum, Link aufs
PDF. Keine Texte, keine Kategorien, keine Personen (Messdokument 17, § 3.6; Fragen 27 und 28 mit
ihrer Annahme: keine Straßennamen als ``category``, kein ``rel="self"``).

Was die Form festlegt, und warum:

* ``feed/id`` ist ``urn:uuid:`` aus Stadt, Ordner und Wahlbezirk: absolut und dauerhaft, ohne dass
  die Seite ihre eigene Adresse kennen muss (Pages oder eigener Server);
* ``feed/updated`` ist das jüngste ``updated`` der Einträge, nie die Laufzeit: gleiche Daten geben
  gleiche Bytes, ein Lauf ohne neues Dokument ändert keinen Feed;
* ``entry/id`` ist die OParl-URL des Dokuments; dasselbe Dokument trägt in mehreren Bezirksfeeds
  dieselbe id, wie RFC 4287 es für denselben Eintrag vorsieht;
* ``entry/updated`` ist OParls ``modified``, nie vor ``published`` (dem Vorlagendatum um 00:00
  Ortszeit): ein vom Ratsinformationssystem berührtes Dokument erscheint im Reader neu;
* ein Titel verliert nur, was XML 1.0 verbietet (Steuerzeichen außer Tabulator und Zeilenumbruch,
  ``\\r``, Ersatzzeichen U+FFFE und U+FFFF, einzelne Surrogate); alles andere kommt beim Lesen
  unverändert zurück.

``atom_problems`` prüft einen Feed ohne Netz und ohne lxml: die normativen Regeln aus RFC 4287, die
ein Schema nicht ausdrückt (Autor, genau ein ``id``, ``title``, ``updated``, Datum nach RFC 3339,
absolute ids, alternate-Link ohne ``content``), dazu die Form, die das RELAX-NG-Schema aus Anhang B
für die Elemente verlangt, die ein Feed hier tragen kann, und die Regeln dieses Projekts (nur
``id``, ``title``, ``updated``, ``published``, ``link`` je Eintrag, ids eindeutig, ``feed/updated``
das jüngste). Gegen das Schema selbst sind die Feeds des Messdokuments mit lxml geprüft (41 von 41).
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import polars as pl

__all__ = [
    "ATOM",
    "EMPTY_UPDATED",
    "FEEDS_SCHEMA",
    "FEEDS_SCHEMA_VERSION",
    "SUBTITLE",
    "FeedDocument",
    "FeedEntry",
    "FeedHead",
    "atom_problems",
    "clean_text",
    "feed_id",
    "feed_name",
    "newest_entries",
    "render_feed",
    "timestamp",
]

ATOM = "http://www.w3.org/2005/Atom"
SUBTITLE = (
    "Neue Dokumente, in denen ein Straßen- oder Ortsname des Wahlbezirks vorkommt: Drucksache, "
    "Titel, Datum und Link ins Ratsinformationssystem, keine Texte."
)
# Die Liste der Feeds je Wahlbezirk (``processed/wahlbezirke_feeds.parquet``), für die Unterseite
FEEDS_SCHEMA_VERSION = 1
FEEDS_SCHEMA: dict[str, pl.DataType] = {
    "wahlkreis_id": pl.Int64(),
    "datei": pl.String(),  # relativ zur Seite: ``feeds/wahlbezirk-01.xml``
    "eintraege": pl.Int64(),  # im Feed, höchstens ``feeds.entries``
    "dokumente": pl.Int64(),  # mit Treffer im Wahlbezirk und Datum, in der ganzen Periode
    "neu_30_tage": pl.Int64(),  # davon in den 30 Tagen bis zum letzten Datum des Korpus
    "aktualisiert": pl.String(),  # feed/updated; leer ohne Eintrag
    "bytes": pl.Int64(),
}
EMPTY_UPDATED = (
    "1970-01-01T00:00:00+00:00"  # ein Feed ohne Einträge: ein festes Datum, keine Laufzeit
)
AUTHOR = "georep, aus dem Ratsinformationssystem (OParl)"
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
_ABSOLUTE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
# XML 1.0, § 2.2: erlaubt sind Tabulator, Zeilenumbruch, Wagenrücklauf und ab U+0020, ohne
# Surrogate und ohne U+FFFE, U+FFFF. Der Wagenrücklauf wird beim Lesen zum Zeilenumbruch und kommt
# darum nicht unverändert zurück; er fällt mit weg.
_FORBIDDEN = re.compile("[\x00-\x08\x0b\x0c\x0d\x0e-\x1f\ud800-\udfff￾￿]")
_FEED_CHILDREN = {
    "author",
    "category",
    "contributor",
    "generator",
    "icon",
    "id",
    "link",
    "logo",
    "rights",
    "subtitle",
    "title",
    "updated",
}
_ENTRY_CHILDREN = {"id", "title", "updated", "published", "link"}  # Projektregel: keine Texte
_LINK_ATTRIBUTES = {"href", "rel", "type", "hreflang", "title", "length"}


@dataclass(frozen=True)
class FeedHead:
    id: str  # absolut, etwa ``urn:uuid:…``
    title: str
    subtitle: str
    generator_version: str
    alternate: str = "../index.html"  # die Seite der Periode, relativ


@dataclass(frozen=True)
class FeedEntry:
    id: str  # absolut: die OParl-URL des Dokuments
    title: str
    published: str  # RFC 3339
    updated: str  # RFC 3339, nie vor published
    link: str
    link_type: str = "application/pdf"


@dataclass(frozen=True)
class FeedDocument:
    """Was ein Feed von einem Dokument braucht; alles davon steht schon in ``dokumente.json``."""

    id: str  # die Korpus-ID, bei OParl die URL des Dokuments
    reference: str  # Drucksache, leer ohne
    name: str  # Titel
    day: dt.date  # Vorlagendatum
    modified: dt.datetime | None  # OParl ``modified``, mit Zeitzone; ohne: das Vorlagendatum
    link: str  # das PDF; leer ohne


def feed_name(district: int) -> str:
    """Der Dateiname eines Feeds unter ``site/feeds/``: ``wahlbezirk-01.xml``."""
    return f"wahlbezirk-{district:02d}.xml"


def _entry(document: FeedDocument, zone: ZoneInfo) -> FeedEntry:
    published = dt.datetime.combine(document.day, dt.time(0, 0), tzinfo=zone)
    updated = max(document.modified or published, published)
    link, kind = document.link, "application/pdf"
    if link.startswith("http://"):
        link = "https://" + link[len("http://") :]
    if not link:
        # ohne PDF die OParl-URL des Dokuments, sonst die Seite: ein Eintrag ohne content braucht
        # einen alternate-Link (RFC 4287, § 4.1.2)
        if document.id.startswith(("http://", "https://")):
            link, kind = document.id, "application/json"
        else:
            link, kind = "../index.html", "text/html"
    ident = document.id if _ABSOLUTE.match(document.id) else feed_id("dokument", document.id)
    title = f"{document.reference}: {document.name}" if document.reference else document.name
    return FeedEntry(ident, title, timestamp(published), timestamp(updated), link, kind)


def newest_entries(
    documents: Iterable[FeedDocument], limit: int, zone: ZoneInfo
) -> list[FeedEntry]:
    """Die ``limit`` neuesten Einträge, neueste zuerst: nach Datum, dann ``updated``, dann id.

    Die Folge hängt nur an den Dokumenten, nicht an ihrer Reihenfolge: derselbe Korpus gibt
    dieselben Bytes (der Monitor schriebe sonst täglich neu).
    """
    keyed = sorted(
        ((d.day, entry.updated, entry.id, entry) for d in documents for entry in [_entry(d, zone)]),
        key=lambda item: (item[0], item[1], item[2]),
        reverse=True,
    )
    return [entry for *_, entry in keyed[:limit]]


def feed_id(slug: str, district: str) -> str:
    """Die dauerhafte Kennung eines Feeds: UUID v5 aus ``georep:<stadt>/<ordner>/feeds/<bezirk>``."""
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'georep:{slug}/feeds/{district}')}"


def clean_text(text: str) -> str:
    """Ein Text ohne die Zeichen, die XML 1.0 verbietet (und ohne ``\\r``); je eines wird ein Leerzeichen."""
    return _FORBIDDEN.sub(" ", text)


def timestamp(moment: dt.datetime) -> str:
    """RFC 3339 mit Sekunden und Zeitzone, wie Atom es verlangt (§ 3.3)."""
    if moment.tzinfo is None:
        raise ValueError(f"ein Zeitpunkt ohne Zeitzone ist kein Datum nach RFC 3339: {moment}")
    return moment.isoformat(timespec="seconds")


def _attribute(value: str) -> str:
    return escape(clean_text(value), {'"': "&quot;"})


def render_feed(head: FeedHead, entries: Sequence[FeedEntry]) -> str:
    """Der Feed als Text, in der Folge der Einträge; ``updated`` ist das jüngste der Einträge."""
    updated = max((e.updated for e in entries), default=EMPTY_UPDATED)
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<feed xmlns="{ATOM}" xml:lang="de">',
        f"  <id>{escape(clean_text(head.id))}</id>",
        f"  <title>{escape(clean_text(head.title))}</title>",
        f"  <subtitle>{escape(clean_text(head.subtitle))}</subtitle>",
        f"  <updated>{updated}</updated>",
        f"  <author><name>{escape(AUTHOR)}</name></author>",
        f'  <generator version="{_attribute(head.generator_version)}">georep</generator>',
        f'  <link rel="alternate" type="text/html" href="{_attribute(head.alternate)}"/>',
    ]
    for e in entries:
        lines += [
            "  <entry>",
            f"    <id>{escape(clean_text(e.id))}</id>",
            f"    <title>{escape(clean_text(e.title))}</title>",
            f"    <published>{e.published}</published>",
            f"    <updated>{e.updated}</updated>",
            f'    <link rel="alternate" type="{_attribute(e.link_type)}" href="{_attribute(e.link)}"/>',
            "  </entry>",
        ]
    lines.append("</feed>")
    return "\n".join(lines) + "\n"


def _local(tag: str) -> str | None:
    """Der Name eines Elements im Atom-Namensraum, sonst ``None``."""
    prefix = f"{{{ATOM}}}"
    return tag[len(prefix) :] if tag.startswith(prefix) else None


def atom_problems(xml: str) -> list[str]:
    """Was einen Feed ungültig macht (RFC 4287, Form nach Anhang B, Projektregeln); leer heißt gültig."""
    problems: list[str] = []
    a = f"{{{ATOM}}}"
    try:
        root = ET.fromstring(xml.encode("utf-8"))
    except ET.ParseError as error:
        return [f"nicht wohlgeformt: {error}"]
    if root.tag != f"{a}feed":
        return [f"Wurzel ist {root.tag}, nicht atom:feed"]

    def exactly_one(element: ET.Element, name: str, where: str) -> None:
        count = len(element.findall(f"{a}{name}"))
        if count != 1:
            problems.append(f"{where}: {count}× {name} (genau eines verlangt)")

    def at_most_one(element: ET.Element, name: str, where: str) -> None:
        if len(element.findall(f"{a}{name}")) > 1:
            problems.append(f"{where}: mehr als ein {name}")

    def moment(element: ET.Element | None, where: str) -> dt.datetime | None:
        text = None if element is None else element.text
        if text is None or not _DATETIME.match(text):
            problems.append(f"{where}: Datum nicht nach RFC 3339 (§ 3.3): {text!r}")
            return None
        try:
            return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            problems.append(f"{where}: kein gültiges Datum: {text!r}")
            return None

    def links(element: ET.Element, where: str) -> None:
        seen: Counter[tuple[str | None, str | None]] = Counter()
        for link in element.findall(f"{a}link"):
            unknown = set(link.attrib) - _LINK_ATTRIBUTES
            if "href" not in link.attrib or unknown or len(link) or (link.text or "").strip():
                problems.append(
                    f"{where}: link mit href, ohne Inhalt, Attribute {sorted(_LINK_ATTRIBUTES)}"
                )
            if link.get("rel", "alternate") == "alternate":
                seen[(link.get("type"), link.get("hreflang"))] += 1
        if any(n > 1 for n in seen.values()):
            problems.append(
                f"{where}: zwei alternate-Links mit gleichem type und hreflang (§ 4.1.1)"
            )

    def text_only(element: ET.Element, where: str) -> None:
        if len(element):
            problems.append(f"{where}: {_local(element.tag)} trägt Elemente statt Text")

    # Kopf: erst die Metadaten, dann die Einträge (Anhang B: interleave, danach entry*)
    seen_entry = False
    for child in root:
        name = _local(child.tag)
        if name == "entry":
            seen_entry = True
        elif name is None or name not in _FEED_CHILDREN:
            problems.append(f"feed: unbekanntes Element {child.tag}")
        elif seen_entry:
            problems.append(f"feed: {name} steht hinter einem Eintrag")
    for name in ("id", "title", "updated"):
        exactly_one(root, name, "feed")
    for name in ("generator", "icon", "logo", "rights", "subtitle"):
        at_most_one(root, name, "feed")
    moment(root.find(f"{a}updated"), "feed/updated")
    for name in ("id", "title", "subtitle", "updated", "generator"):
        for element in root.findall(f"{a}{name}"):
            text_only(element, "feed")
    feed_ident = root.findtext(f"{a}id") or ""
    if not _ABSOLUTE.match(feed_ident):
        problems.append(f"feed/id nicht absolut (§ 4.2.6): {feed_ident!r}")
    for author in root.findall(f"{a}author"):
        exactly_one(author, "name", "feed/author")
    links(root, "feed")
    has_author = root.find(f"{a}author") is not None
    identifiers: list[str] = []
    newest = ""
    for index, entry in enumerate(root.findall(f"{a}entry"), 1):
        where = f"entry {index}"
        for name in ("id", "title", "updated"):
            exactly_one(entry, name, where)
        at_most_one(entry, "published", where)
        updated = moment(entry.find(f"{a}updated"), f"{where}/updated")
        published = entry.find(f"{a}published")
        if published is not None:
            first = moment(published, f"{where}/published")
            if first is not None and updated is not None and updated < first:
                problems.append(f"{where}: updated liegt vor published (Projektregel)")
        if not has_author and entry.find(f"{a}author") is None:
            problems.append(f"{where}: weder Feed noch Eintrag haben einen author (§ 4.1.1)")
        if not any(k.get("rel", "alternate") == "alternate" for k in entry.findall(f"{a}link")):
            problems.append(f"{where}: ohne content und ohne alternate-Link (§ 4.1.2)")
        links(entry, where)
        foreign = {child.tag for child in entry} - {f"{a}{n}" for n in _ENTRY_CHILDREN}
        if foreign:
            problems.append(f"{where}: Elemente außer {sorted(_ENTRY_CHILDREN)}: {sorted(foreign)}")
        for name in ("id", "title", "updated", "published"):
            for element in entry.findall(f"{a}{name}"):
                text_only(element, where)
        ident = entry.findtext(f"{a}id") or ""
        if not _ABSOLUTE.match(ident):
            problems.append(f"{where}: id nicht absolut: {ident!r}")
        identifiers.append(ident)
        newest = max(newest, entry.findtext(f"{a}updated") or "")
    if len(identifiers) != len(set(identifiers)):
        problems.append("zwei Einträge mit derselben id")
    if identifiers and (root.findtext(f"{a}updated") or "") != newest:
        problems.append("feed/updated ist nicht das jüngste updated der Einträge (Projektregel)")
    return problems
