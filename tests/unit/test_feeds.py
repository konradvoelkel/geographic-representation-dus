"""Atom-Feeds je Wahlbezirk (``report.feeds``): Form, Prüfung, Grenzfälle (Messdokument 17, § 3.6).

Ein Feed aus einem Mini-Korpus als Snapshot (klein und stabil, die Version des Generators fest),
ein Feed ohne Einträge, ein Titel mit ``&``, ``<``, Anführungszeichen und einem Steuerzeichen, und
die Gegenprobe des Messdokuments: ein kaputter Feed fällt durch.
"""

from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import pytest
from syrupy.assertion import SnapshotAssertion

from georep.report.feeds import (
    ATOM,
    EMPTY_UPDATED,
    FeedDocument,
    FeedEntry,
    FeedHead,
    atom_problems,
    clean_text,
    feed_id,
    feed_name,
    newest_entries,
    render_feed,
    timestamp,
)

BERLIN = ZoneInfo("Europe/Berlin")
HEAD = FeedHead(
    id=feed_id("stadt/2025", "wahlbezirk-01"),
    title="Ratsdokumente im Wahlbezirk 1 (Stadt, Wahlperiode seit 2025)",
    subtitle="Neue Dokumente, in denen ein Straßen- oder Ortsname des Wahlbezirks vorkommt.",
    generator_version="0.0.0",
)


def _entry(number: int, day: dt.date, title: str = "Antrag", modified: str = "") -> FeedEntry:
    published = dt.datetime.combine(day, dt.time(0, 0), tzinfo=BERLIN)
    return FeedEntry(
        id=f"https://ris.example/papers/{number}",
        title=f"A/{number:03d}/2025: {title}",
        published=published,
        updated=dt.datetime.fromisoformat(modified) if modified else published,
        link=f"https://ris.example/files/{number}.pdf",
    )


def test_a_small_feed_as_a_snapshot(snapshot: SnapshotAssertion) -> None:
    entries = [
        _entry(2, dt.date(2025, 11, 3), modified="2025-11-04T09:10:24+01:00"),
        _entry(1, dt.date(2025, 7, 1)),
    ]
    text = render_feed(HEAD, entries)
    assert atom_problems(text) == []
    assert text == snapshot


def test_the_feed_id_is_a_stable_urn_and_depends_on_city_folder_and_district() -> None:
    first = feed_id("stadt/2025", "wahlbezirk-01")
    assert first == feed_id("stadt/2025", "wahlbezirk-01")
    assert first.startswith("urn:uuid:") and len(first) == len("urn:uuid:") + 36
    assert first != feed_id("stadt/2025", "wahlbezirk-02")
    assert first != feed_id("stadt/2014-2020", "wahlbezirk-01")


def test_the_feed_updates_with_its_newest_entry_not_with_the_run() -> None:
    entries = [_entry(1, dt.date(2025, 10, 1)), _entry(2, dt.date(2025, 12, 24))]
    root = ET.fromstring(render_feed(HEAD, entries).encode("utf-8"))
    assert root.findtext(f"{{{ATOM}}}updated") == "2025-12-24T00:00:00+01:00"  # Winterzeit
    summer = _entry(3, dt.date(2025, 7, 1)).published
    assert timestamp(summer) == "2025-07-01T00:00:00+02:00"  # Sommerzeit


def test_a_feed_without_entries_is_valid_and_has_a_fixed_date() -> None:
    text = render_feed(HEAD, [])
    assert atom_problems(text) == []
    assert f"<updated>{EMPTY_UPDATED}</updated>" in text


def test_a_title_with_markup_quotes_and_a_control_character() -> None:
    title = "Bau & Verkehr: \"Weg\" <neu>\x0b mit 'Zusatz'"
    entry = _entry(7, dt.date(2025, 10, 1), title=title)
    entry = FeedEntry(
        entry.id, entry.title, entry.published, entry.updated, entry.link + '?a="1"&b'
    )
    text = render_feed(HEAD, [entry])
    assert atom_problems(text) == []
    root = ET.fromstring(text.encode("utf-8"))
    read = root.find(f"{{{ATOM}}}entry")
    assert read is not None
    assert read.findtext(f"{{{ATOM}}}title") == "A/007/2025: " + title.replace("\x0b", " ")
    link = read.find(f"{{{ATOM}}}link")
    assert link is not None and link.get("href") == entry.link


def test_clean_text_drops_only_what_xml_forbids() -> None:
    assert clean_text("a\x00b\x1fc\rd") == "a b c d"
    assert clean_text("Tab\tund\nZeile, ä ß €") == "Tab\tund\nZeile, ä ß €"
    assert clean_text("￾￿") == "  "


def test_a_moment_without_zone_is_no_atom_date() -> None:
    with pytest.raises(ValueError, match="Zeitzone"):
        timestamp(dt.datetime(2025, 1, 1))


def test_a_broken_feed_fails_the_check() -> None:
    """Die Gegenprobe aus dem Messdokument: kaputtes Datum, falscher Elementname."""
    text = render_feed(HEAD, [_entry(1, dt.date(2025, 10, 1))])
    broken = (
        text.replace("<updated>", "<updated>gestern", 1)
        .replace("  <title>", "  <titel>", 1)
        .replace("</title>\n  <subtitle>", "</titel>\n  <subtitle>", 1)
    )
    problems = atom_problems(broken)
    assert any("titel" in p for p in problems)
    assert any("0× title" in p for p in problems)
    assert any("RFC 3339" in p for p in problems)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda t: t.replace("<id>urn:uuid:", "<id>relativ-", 1), "nicht absolut"),
        (
            lambda t: t.replace(
                "<author><name>georep, aus dem Ratsinformationssystem (OParl)</name></author>\n", ""
            ),
            "author",
        ),
        (
            lambda t: t.replace('    <link rel="alternate"', '    <link rel="related"'),
            "alternate-Link",
        ),
        (
            lambda t: t.replace("  </entry>", "    <summary>Text</summary>\n  </entry>", 1),
            "Elemente außer",
        ),
        (lambda t: t.replace("<published>2025-10-01", "<published>2025-12-01", 1), "vor published"),
        (
            lambda t: t.replace("</feed>", "  <subtitle>zwei</subtitle>\n</feed>"),
            "hinter einem Eintrag",
        ),
        (lambda t: t.replace("<feed ", "<fead ").replace("</feed>", "</fead>"), "Wurzel"),
        (lambda t: t + "<", "wohlgeformt"),
    ],
)
def test_each_rule_names_what_is_wrong(change: object, message: str) -> None:
    text = render_feed(HEAD, [_entry(1, dt.date(2025, 10, 1))])
    broken = change(text)  # type: ignore[operator]
    assert any(message in p for p in atom_problems(broken)), atom_problems(broken)


def test_two_entries_with_the_same_id_are_one_too_many() -> None:
    entry = _entry(1, dt.date(2025, 10, 1))
    assert "zwei Einträge mit derselben id" in atom_problems(render_feed(HEAD, [entry, entry]))


def _document(number: int, day: dt.date, **changes: object) -> FeedDocument:
    values: dict[str, object] = {
        "id": f"http://ris.example/papers/{number}",
        "reference": f"A/{number:03d}/2025",
        "name": "Antrag",
        "day": day,
        "modified": None,
        "link": f"http://ris.example/files/{number}.pdf",
    }
    values.update(changes)
    return FeedDocument(**values)  # type: ignore[arg-type]


def test_the_newest_come_first_and_ties_go_by_update_then_id() -> None:
    late = dt.datetime(2025, 10, 2, 8, 0, tzinfo=BERLIN)
    documents = [
        _document(1, dt.date(2025, 10, 1)),
        _document(2, dt.date(2025, 10, 1), modified=late),
        _document(3, dt.date(2025, 9, 1)),
        _document(4, dt.date(2025, 10, 1)),
    ]
    entries = newest_entries(documents, 3, BERLIN)
    assert [e.id.rsplit("/", 1)[1] for e in entries] == ["2", "4", "1"]
    assert timestamp(entries[0].updated) == "2025-10-02T08:00:00+02:00"
    assert newest_entries(documents[::-1], 3, BERLIN) == entries


def test_an_entry_links_the_pdf_by_https_and_never_updates_before_it_was_published() -> None:
    early = dt.datetime(2025, 9, 1, 12, 0, tzinfo=BERLIN)
    (entry,) = newest_entries([_document(5, dt.date(2025, 10, 1), modified=early)], 50, BERLIN)
    assert entry.link == "https://ris.example/files/5.pdf"
    assert entry.updated == entry.published
    assert timestamp(entry.published) == "2025-10-01T00:00:00+02:00"
    assert entry.title == "A/005/2025: Antrag"


def test_without_pdf_the_entry_links_the_oparl_object_or_the_page() -> None:
    (oparl,) = newest_entries([_document(6, dt.date(2025, 10, 1), link="")], 1, BERLIN)
    assert (oparl.link, oparl.link_type) == ("http://ris.example/papers/6", "application/json")
    bare = _document(7, dt.date(2025, 10, 1), link="", id="p7", reference="")
    (page,) = newest_entries([bare], 1, BERLIN)
    assert (page.link, page.link_type) == ("../index.html", "text/html")
    assert page.id.startswith("urn:uuid:") and page.title == "Antrag"
    assert atom_problems(render_feed(HEAD, [oparl, page])) == []


def test_the_file_name_pads_the_district() -> None:
    assert feed_name(1) == "wahlbezirk-01.xml" and feed_name(41) == "wahlbezirk-41.xml"


def test_updated_and_order_go_by_instant_not_by_string() -> None:
    """Review N3: zwei Zeitpunkte mit verschiedenem Versatz ordnen sich als Text falsch.

    A ist 2025-10-01 23:00 UTC (als 01:00+02:00), B 23:30 UTC (als 23:30+00:00): als Text käme A
    nach B, in der Zeit ist B das jüngere. Beide stehen danach in der Zeitzone des Profils.
    """
    a = dt.datetime(2025, 10, 2, 1, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
    b = dt.datetime(2025, 10, 1, 23, 30, tzinfo=dt.UTC)
    documents = [
        _document(1, dt.date(2025, 10, 1), modified=a),
        _document(2, dt.date(2025, 10, 1), modified=b),
    ]
    entries = newest_entries(documents, 50, BERLIN)
    assert [e.id.rsplit("/", 1)[1] for e in entries] == ["2", "1"]
    text = render_feed(HEAD, entries)
    assert "<updated>2025-10-02T01:30:00+02:00</updated>\n  <author>" in text  # feed/updated: B
    assert "<updated>2025-10-02T01:00:00+02:00</updated>" in text  # A in Ortszeit
