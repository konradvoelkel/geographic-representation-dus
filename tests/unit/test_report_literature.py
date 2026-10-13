"""Die Literaturübersicht: Daten im Paket, Stadt im Profil, ein Abschnitt auf der Seite (Punkt 47).

``docs/todo.md``, Punkt 5. Geprüft wird, dass die Einträge zitierfähig sind (Autor, Titel, Jahr,
Ort oder Institution, URL mit Abrufdatum oder DOI), dass die stadtneutrale Datei stadtneutral
bleibt, dass das Profil ergänzt statt zu ersetzen, und dass README und Seite dieselbe Liste tragen.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import replace
from pathlib import Path

import deal
import pytest
from pydantic import ValidationError

from georep.errors import SchemaError
from georep.report.literature import FILE, literature, package_literature
from georep.report.model import ReportModel
from georep.report.render import (
    ALLOWED_LINKS,
    Visuals,
    external_links,
    model_links,
    render_report,
    sections,
)
from georep.settings import LiteratureEntry, Settings
from tests.conftest import REPO, mg_settings
from tests.unit.test_report_city import CITY_WORDS

SOURCE_FILE = REPO / "src" / "georep" / "report" / FILE
THESIS_KEY = "bartzsch-2026"
GOOD: dict[str, object] = {
    "key": "beispiel",
    "authors": "A. Autorin",
    "title": "Ein Titel",
    "year": 2020,
    "venue": "Irgendeine Hochschule",
    "note": "Was der Eintrag beiträgt.",
}


def make(**overrides: object) -> LiteratureEntry:
    """Ein Eintrag mit den Pflichtfeldern; ``overrides`` setzt einzelne Felder, auch auf ``None``.

    ``model_validate`` statt des Konstruktors, weil ein ``**dict[str, object]`` unter
    ``mypy --strict`` je Feld einen Typfehler gäbe -- die Validierung ist hier der Prüfgegenstand.
    """
    return LiteratureEntry.model_validate(GOOD | overrides)


# --- Die Daten ---------------------------------------------------------------------------------


def test_the_package_file_holds_citable_entries() -> None:
    found = package_literature()
    assert len(found) >= 5, "lieber fünf belegte Einträge als zwölf vage"
    assert len({entry.key for entry in found}) == len(found)
    for entry in found:
        assert entry.url or entry.doi
        assert not entry.url or entry.accessed is not None
        assert entry.note.strip(), f"{entry.key}: ohne Satz zum Beitrag wäre es eine Linksammlung"
        assert entry.accessed is None or 1990 <= entry.accessed.year <= 2100


def test_no_city_word_in_the_package_file() -> None:
    """Dieselbe Regel wie für Code und Vorlage: die allgemeinen Einträge kennen keine Stadt."""
    text = SOURCE_FILE.read_text(encoding="utf-8")
    assert [word for word in CITY_WORDS if word in text] == []


def test_the_profile_adds_the_thesis_in_front_of_the_general_entries(
    default_settings: Settings,
) -> None:
    found = literature(default_settings)
    assert found[0].key == THESIS_KEY and found[0].pending
    assert "Heinrich-Heine-Universität" in found[0].venue
    # Die zweite Quelle der Arbeit ist die Lücke: ohne Jahr und ohne Link, darum nur mit ``pending``
    assert found[1].pending and found[1].year is None and found[1].links == ()
    assert found[2:] == package_literature()


def test_a_second_city_inherits_the_general_entries() -> None:
    """Option 01: ohne eigenen Eintrag erbt eine zweite Stadt die Paketliste, unverändert."""
    assert literature(mg_settings()) == package_literature()


def test_a_doubled_key_is_an_error(default_settings: Settings) -> None:
    clash = make(key=package_literature()[0].key, url="https://a.invalid/", accessed="2026-10-13")
    settings = default_settings.model_copy(
        update={"report": default_settings.report.model_copy(update={"literature": [clash]})}
    )
    with pytest.raises(SchemaError, match="doppelt"):
        literature(settings)


def test_a_broken_package_file_is_a_schema_error(tmp_path: Path) -> None:
    (tmp_path / FILE).write_text("literature = 3\n", encoding="utf-8")
    with pytest.raises(SchemaError, match="Liste von Tabellen"):
        package_literature(tmp_path)
    (tmp_path / FILE).write_text("[[literature]]\nkey = 1\n", encoding="utf-8")
    with pytest.raises(SchemaError, match=FILE):
        package_literature(tmp_path)
    with pytest.raises(SchemaError, match="nicht lesbar"):
        package_literature(tmp_path / "leer")


def test_the_same_key_twice_in_the_package_file_breaks_the_contract(tmp_path: Path) -> None:
    (tmp_path / FILE).write_text(
        '[[literature]]\nkey = "a"\nauthors = "A"\ntitle = "T"\nyear = 2020\n'
        'venue = "V"\ndoi = "10.1234/a"\nnote = "Trägt bei."\n\n'
        '[[literature]]\nkey = "a"\nauthors = "B"\ntitle = "U"\nyear = 2021\n'
        'venue = "W"\ndoi = "10.1234/b"\nnote = "Trägt auch bei."\n',
        encoding="utf-8",
    )
    with pytest.raises(deal.PostContractError):
        package_literature(tmp_path)


# --- Das Modell --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({}, "url oder doi"),
        ({"pending": True, "year": None, "url": "https://a.invalid/"}, "Abrufdatum"),
        ({"year": None, "doi": "10.1234/a"}, "gehört ein Jahr dazu"),
        ({"url": "https://a.invalid/"}, "Abrufdatum"),
        ({"url": "http://a.invalid/"}, "keine https-URL"),
        ({"doi": "nicht-doi"}, "beginnt mit 10."),
        ({"doi": "10.1234/a", "year": 1800}, "Jahreszahl"),
        ({"doi": "10.1234/a", "key": "Gross"}, "Kleinbuchstaben"),
        ({"doi": "10.1234/a", "authors": "  "}, "Pflicht"),
        ({"doi": "10.1234/a", "note": "   "}, "ein Satz zum Beitrag"),
        ({"url": "https://a.invalid/", "accessed": "1969-07-20"}, "Abrufdatum"),
        ({"url": "https://a.invalid/", "accessed": "2101-01-01"}, "Abrufdatum"),
    ],
)
def test_an_entry_that_cannot_be_checked_is_refused(
    update: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        make(**update)


def test_a_pending_entry_may_lack_year_and_link() -> None:
    """Was aus dem Verzeichnis einer nicht öffentlichen Arbeit nachzutragen ist, hat noch keinen Link."""
    found = make(pending=True, year=None)
    assert found.links == () and found.year is None and found.pending


def test_a_doi_becomes_a_link_and_both_links_count() -> None:
    both = make(doi="10.1234/abc", url="https://a.invalid/x", accessed="2026-10-13")
    assert both.doi_url == "https://doi.org/10.1234/abc"
    assert both.links == ("https://doi.org/10.1234/abc", "https://a.invalid/x")
    assert make(doi="10.1234/abc").links == ("https://doi.org/10.1234/abc",)


# --- Der Abschnitt der Seite -------------------------------------------------------------------


def test_the_section_stands_between_derived_data_and_downloads() -> None:
    numbers = {part.name: part.number for part in sections()}
    assert numbers["abgeleitete-daten"] < numbers["literatur"] < numbers["downloads"]


def test_the_page_carries_every_entry_with_a_cite_and_its_links(
    mini_page: str, default_settings: Settings
) -> None:
    found = literature(default_settings)
    assert "<h2>Literatur und verwandte Arbeiten</h2>" in mini_page
    block = mini_page[mini_page.index('<section id="literatur">') :]
    block = block[: block.index("</section>")]
    assert block.count("<cite>") == len(found)
    for entry in found:
        assert block.count(f'<li id="lit-{entry.key}"') == 1
        for link in entry.links:
            assert f'<a href="{link}">' in block
    assert block.count("<a href=") == sum(len(entry.links) for entry in found)


def test_no_link_on_the_page_claims_a_new_window(mini_page: str) -> None:
    """``rel="noopener"`` wirkt nur mit ``target="_blank"``, und die Seite öffnet nichts neu.

    Es stand im Literaturabschnitt an jedem Link und im Dialog der Dokumente an den PDF-Links; an
    beiden Stellen tat es nichts, und an den zwanzig Links der übrigen Abschnitte stand es nicht.
    Ein Attribut, das an zwei Stellen steht und an zwanzig nicht, liest sich wie eine Regel, die es
    nicht gibt (Review 2026-10-13). Jetzt steht es nirgends, und die eine Regel ist: diese Seite
    öffnet keinen Link in einem neuen Fenster.
    """
    assert "noopener" not in mini_page
    assert 'target="_blank"' not in mini_page


def test_a_pending_entry_without_a_title_is_allowed_and_says_so() -> None:
    """Ein formulierter Titel in ``<cite>`` behauptet eine Zitation, die niemand geprüft hat.

    Der Titel der Arbeit steht nirgends -- nicht in ihrem Repositorium, nicht in seiner
    Beschreibung, nicht in seinem README. Dann bleibt das Feld leer, und die Seite sagt es
    (Review 2026-10-13).
    """
    assert make(pending=True, title="", year=None).title == ""
    with pytest.raises(ValidationError, match="Titel"):
        make(title="")  # ohne pending bleibt der Titel Pflicht


def test_the_pending_entries_say_so_on_the_page(mini_page: str, default_settings: Settings) -> None:
    """Ein fehlender Titel und fehlende Angaben haben je einen Marker, mit Trennzeichen davor."""
    found = literature(default_settings)
    thesis = next(e for e in found if not e.title)
    assert thesis.pending
    assert f"<cite>{thesis.authors}</cite> \u2014 " in mini_page
    assert mini_page.count('<span class="pending">[Titel nachzutragen]</span>') == 1
    assert mini_page.count('<span class="pending">[Angaben nachzutragen]</span>') == 1
    assert "Sichtbarkeit der Kommunalwahlbezirke in den Ratsdokumenten" not in mini_page


def test_the_method_paragraph_points_at_the_section(mini_page: str) -> None:
    assert 'href="#literatur">Literatur und verwandte Arbeiten</a>' in mini_page


def test_an_url_with_an_ampersand_still_renders(
    mini_model: ReportModel, mini_visuals: Visuals
) -> None:
    """Eine Quelle mit Abfrageparametern bricht die Allowlist, wenn niemand entschlüsselt.

    Die Vorlage escapt ``&`` zu ``&amp;``; ``external_links`` fand bis zum 2026-10-13 die escapte
    Form, ``model_links`` liefert die rohe, und die Nachbedingung von ``render_report`` schlug fehl
    -- also an einer vollkommen gültigen DOI- oder Portal-URL (Review 2026-10-13).
    """
    url = "https://beispiel.invalid/suche?a=1&b=2"
    found = make(key="mit-und", url=url, accessed="2026-10-13", note="Mit Abfrageparametern.")
    model = replace(mini_model, literature=(found,))
    page = render_report(model, mini_visuals)
    assert "&amp;b=2" in page  # escaped im HTML
    assert url in external_links(page)  # entschlüsselt beim Vergleich
    assert set(external_links(page)) <= ALLOWED_LINKS | model_links(model)


# --- README und Quelle tragen dieselbe Liste ---------------------------------------------------

BULLET = re.compile(r"^- ", re.MULTILINE)


def readme_bullets() -> list[str]:
    """Die Einträge des README-Abschnitts „Literatur", je als ein Block (Fortsetzungszeilen dabei)."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    start = text.index("\n## Literatur\n")
    rest = text[start + 1 :]
    section = rest[: rest.index("\n## ", 1)]
    parts = BULLET.split(section)
    return [" ".join(part.split()) for part in parts[1:]]


def test_the_readme_list_is_the_same_list_in_the_same_order(default_settings: Settings) -> None:
    """Von Hand gepflegt, aber nicht frei: dieser Test hält README und Quelle zusammen.

    Erzeugt wird der Abschnitt nicht — das README ist die Datei, die ein frischer Klon zuerst
    liest, und ein Generator bräuchte einen Build-Schritt, den das Repo nicht hat. Was gelten
    muss, steht hier: dieselben Einträge, dieselbe Reihenfolge, derselbe Satz zum Beitrag.
    """
    bullets = readme_bullets()
    found = literature(default_settings)
    assert len(bullets) == len(found)
    for entry, bullet in zip(found, bullets, strict=True):
        assert entry.authors in bullet, entry.key
        assert entry.title in bullet, entry.key
        assert entry.venue in bullet, entry.key
        if entry.year is not None:
            assert str(entry.year) in bullet, entry.key
        assert entry.note.strip(), entry.key  # sonst wäre der Vergleich unten tautologisch
        assert " ".join(entry.note.split()) in bullet, entry.key
        for link in entry.links:
            assert link in bullet, entry.key
        if entry.accessed is not None:
            assert entry.accessed.strftime("%d.%m.%Y") in bullet, entry.key


def test_the_source_file_documents_its_own_rules() -> None:
    """Jede Zahl trägt ihre Begründung (CLAUDE.md): die Datei sagt, was ein Eintrag braucht."""
    head = SOURCE_FILE.read_text(encoding="utf-8").split("[[literature]]", 1)[0]
    assert "docs/todo.md" in head and "docs/decisions.md" in head
    assert all(field in head for field in ("key", "url", "note", "pending"))
    payload = tomllib.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    assert [row["key"] for row in payload["literature"]] == [e.key for e in package_literature()]
