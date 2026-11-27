"""Die Startseite und der Umzug der Auswertung nach ``details.html`` (plan-startseite-2026-11.md).

Stufe U (§ 3, § 9): der Schritt ``report`` schreibt den bisherigen Inhalt als ``details.html``, und
``index.html`` ist eine vorläufige Startseite mit Kopf, Linkblock, einem ``<noscript>``-Satz und dem
Skript, das alte Anker nach ``details.html`` weiterleitet. Die eigenen Schlüssel der Startseite
(ids mit ``start-``, in der Adresse ``zeitraum`` und ``gremium``) sind reserviert: keine id auf
``details.html`` darf einer sein, sonst bliebe ein alter Link auf der Startseite hängen.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast

import pytest

from georep.layout import Layout
from georep.report.charts import rate_label
from georep.report.model import ReportModel, format_de, percent_de
from georep.report.pages import page_links
from georep.report.render import sections
from georep.report.start import (
    FRAME_IDS,
    KIND_PHRASES,
    START_KEYS,
    START_PREFIX,
    _asset,
    question_sentence,
    redirect_script,
    scope_sentence,
    summary_sentences,
)
from georep.report.startkarte import KARTE_NAME
from georep.settings import Settings
from tests.unit.test_report_render import _contrast

_ID = re.compile(r'(?<![\w-])id="([^"]*)"')
_SECTION = re.compile(r'<section id="([^"]*)"')
_HREF = re.compile(r'href="([^"]*)"')


def _ids(page: str) -> list[str]:
    return _ID.findall(page)


def _details(layout: Layout) -> str:
    return layout.site_details.read_text(encoding="utf-8")


def _start(layout: Layout) -> str:
    return layout.site_index.read_text(encoding="utf-8")


def test_the_report_step_writes_details_and_a_start_page(mini_run: Layout) -> None:
    assert mini_run.site_details == mini_run.site / "details.html"
    assert mini_run.site_details.is_file() and mini_run.site_index.is_file()
    # Der Stamp bleibt an der Startseite (Layout.site_index, plan-startseite, § 3)
    assert mini_run.site_index.with_name("index.html.stamp.json").is_file()
    assert not mini_run.site_details.with_name("details.html.stamp.json").exists()


def test_details_carries_every_section_of_the_profile(
    mini_run: Layout, mini_model: ReportModel
) -> None:
    """Jeder Abschnitt der Auswertung steht auf ``details.html``, keiner auf der Startseite.

    Auf der Mini-Fixture fehlt nur „Zwei Wahlperioden": das Standardprofil rechnet keinen
    Vergleich. Mit allen Abschnitten prüft es ``tests/golden/test_published_page.py`` an der
    veröffentlichten Seite.
    """
    assert mini_model.comparison is None and mini_model.monitoring_url
    expected = [s.name for s in sections() if s.name != "perioden"]
    assert _SECTION.findall(_details(mini_run)) == expected
    assert not set(_SECTION.findall(_start(mini_run))) & {s.name for s in sections()}


def test_details_keeps_title_and_links_back_to_the_start_page(mini_run: Layout) -> None:
    page = _details(mini_run)
    assert "<title>Geografische Repräsentation in " in page
    assert '<p class="meta" data-start="1"><a href="index.html">Zur Startseite</a></p>' in page


def test_no_id_on_details_takes_a_key_of_the_start_page(mini_run: Layout) -> None:
    """Die Weiterleitung lässt jeden Anker der Startseite stehen; auf ``details.html`` gibt es keinen."""
    ids = _ids(_details(mini_run))
    assert ids
    assert not [i for i in ids if i.startswith(START_PREFIX) or i in START_KEYS]
    # Der Schlüssel der Suche auf details.html (15-suche.js) ist keiner der Startseite
    assert "suche" not in START_KEYS
    # Die eigenen ids der Startseite beginnen mit start-; dazu nur Dialog und Tooltip des Rahmens
    own = _ids(_start(mini_run))
    assert own and all(i.startswith(START_PREFIX) or i in FRAME_IDS for i in own), own
    assert set(FRAME_IDS) <= set(ids)


def _forwards(page: str) -> re.Pattern[str]:
    """Der reguläre Ausdruck der Weiterleitung, aus der Seite gelesen; in Python dieselbe Syntax."""
    match = re.search(r"!/(.+?)/\.test\(h\)", page)
    assert match is not None
    return re.compile(match.group(1))


@pytest.mark.parametrize(
    ("anchor", "stays"),
    [
        ("suche=Benrath", False),
        ("suche=grafenberger%20allee", False),
        ("bezirk-17", False),
        ("kernzahlen", False),
        ("downloads", False),
        ("zeitraumx", False),
        ("start-karte", True),
        ("zeitraum=2024-10..2025-09&gremium=OVA", True),
        ("gremium=OVA", True),
        ("zeitraum", True),
    ],
)
def test_the_start_page_forwards_old_anchors_to_details(
    mini_run: Layout, anchor: str, stays: bool
) -> None:
    page = _start(mini_run)
    head = page[: page.index("</head>")]
    assert redirect_script() in head  # ganz oben, vor dem Stil
    assert head.index(redirect_script()) < head.index("<style>")
    assert 'location.replace("details.html"+location.hash)' in redirect_script()
    assert (_forwards(page).match(anchor) is not None) is stays


def test_the_start_page_links_details_downloads_and_every_subpage(
    mini_run: Layout, default_settings: Settings
) -> None:
    page = _start(mini_run)
    hrefs = _HREF.findall(page)
    assert "details.html" in hrefs and "details.html#downloads" in hrefs
    for link in page_links(default_settings):
        assert link.href in hrefs
    ids = set(_ids(_details(mini_run)))
    targets = [h.split("#", 1)[1] for h in hrefs if h.startswith("details.html#")]
    assert targets and all(t in ids for t in targets), targets


def test_the_start_page_says_what_works_without_script(mini_run: Layout) -> None:
    """§ 4.7: ohne Skript die Choroplethe, Kurzfassung und Links; ein Satz sagt, was fehlt."""
    page = _start(mini_run)
    # der zweite <noscript> im Kopf hebt nur die Vorschau der Liste auf (Punkt 48)
    noscript = [n for n in re.findall(r"<noscript>(.*?)</noscript>", page, re.S) if "<p" in n]
    assert len(noscript) == 1 and 'href="details.html"' in noscript[0]
    assert "Dokumente je Wahlbezirk in den letzten zwölf Monaten" in noscript[0]
    # ohne Skript stehen Kurzfassung, Choroplethe und Links; die Bedienung ist verborgen
    assert '<div id="start-controls" hidden>' in page
    assert re.search(r'<path class="start-area q\d"', page)
    # Die Zeile „Weitere Städte" setzt publish auch hier (plan-startseite, § 3)
    assert page.count("<!--georep:weitere-staedte-->") == 1


# --- Stufe B: Kurzfassung, Karte, karte.json --------------------------------------------------


def _karte(layout: Layout) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((layout.site_data / KARTE_NAME).read_text(encoding="utf-8"))
    return data


def test_every_number_of_the_summary_comes_from_the_model(
    mini_run: Layout, mini_model: ReportModel
) -> None:
    """§ 8: K1 bis K4 aus dem Modell, an der Mini-Fixture nachgerechnet; ohne K5 (Frage S.3)."""
    page = _start(mini_run)
    kurz = page[
        page.index('<section id="start-kurz"') : page.index(
            "</section>", page.index('<section id="start-kurz"')
        )
    ]
    f = mini_model.figures
    assert f"{format_de(f.documents_hit)} der {format_de(f.documents)} Ratsdokumente" in kurz
    assert percent_de(f.documents_hit / f.documents, 0) in kurz
    rows = [d for d in mini_model.districts if d.eligible]
    high = max(rows, key=lambda d: (d.rate, -d.id))
    low = min(rows, key=lambda d: (d.rate, d.id))
    assert f"Wahlbezirk {high.id} {high.name}" in kurz and rate_label(high.rate) in kurz
    assert f"Wahlbezirk {low.id} {low.name}" in kurz and rate_label(low.rate) in kurz
    assert f"{format_de(high.rate / low.rate, 1)}-Fache" in kurz
    if mini_model.bias is not None:
        assert f"r = {format_de(mini_model.bias.hits_terms, 2)}" in kurz
    assert mini_model.regression is not None
    fit = mini_model.regression.all
    assert f"alle {fit.n} Wahlbezirke" in kurz
    assert (f"p = {format_de(fit.p, 2)}" if fit.p >= 0.05 else f"p = {format_de(fit.p, 3)}") in kurz
    totals: dict[str, int] = {}
    for row in mini_model.bodies:
        totals[row.kind] = totals.get(row.kind, 0) + row.with_hits
    total = sum(totals.values())
    for kind, count in totals.items():
        if count and kind != "unbekannt":
            assert f"{percent_de(count / total, 0)} {KIND_PHRASES[kind]}" in kurz, kind
    # nichts Exploratives, keine Sensitivität (K5)
    assert "explorativ" not in kurz and "Ausreißer" not in kurz and "Gewichtung" not in kurz
    assert "weightings" not in page  # die englische Kurzfassung ohne K5


def test_every_link_of_the_summary_hits_an_id_of_details(
    mini_run: Layout, mini_model: ReportModel
) -> None:
    ids = set(_ids(_details(mini_run)))
    sentences = summary_sentences(mini_model)
    assert [s.key for s in sentences] == ["K1", "K2", "K3", "K4"]
    assert all(s.target in ids for s in sentences), [s.target for s in sentences]
    page = _start(mini_run)
    for s in sentences:
        assert f'<a href="details.html#{s.target}">{s.link}</a>' in page


def test_the_question_sentence_without_a_regression() -> None:
    """Laufende Periode: keine Wahlbeteiligung, also keine Regression; der Satz sagt es."""
    model = cast(ReportModel, SimpleNamespace(regression=None))
    sentence = question_sentence(model, has_months=True)
    assert "keine Wahlbeteiligung" in sentence.text and sentence.target == "monate"
    assert question_sentence(model, has_months=False).target == "kernzahlen"


def test_a_low_text_share_is_named_first(mini_model: ReportModel) -> None:
    """Mönchengladbach: 650 von 2 895 Dokumenten haben Text; K1 sagt das, bevor es den Anteil nennt."""
    figures = replace(
        mini_model.figures, documents=1_000, documents_with_text=500, documents_hit=400
    )
    sentence = scope_sentence(replace(mini_model, figures=figures))
    assert sentence.text.startswith("Nur 500 der 1 000 Ratsdokumente")
    assert "400 davon (80 %)" in sentence.text


def test_no_party_or_parliamentary_group_word_on_the_start_page(
    mini_run: Layout, default_settings: Settings
) -> None:
    """§ 1 und § 8: kein Filter nach Partei, keine Rangfolge von Fraktionen; wie test_report_city."""
    page = _start(mini_run)
    visible = re.sub(r"<script>.*?</script>", "", page, flags=re.S)
    names: set[str] = set()
    for party in (*default_settings.originators.parties, *default_settings.originators.groups):
        names |= {party.key, party.label}

    def found(text: str, words: set[str]) -> list[str]:
        return sorted(w for w in words if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text))

    # Keine Partei auf der ganzen Seite; in Kurzfassung und Karte auch nicht das Wort selbst (der
    # Linkblock nennt die Unterseite der Akteure mit ihrem Satz, und der spricht von Fraktionen)
    assert found(visible, names) == []
    for section in ("start-kurz", "start-karte"):
        start = visible.index(f'<section id="{section}"')
        part = visible[start : visible.index("</section>", start)]
        assert found(part, names | {"Partei", "Parteien", "Fraktion", "Fraktionen"}) == [], section
    assert "Ressort" not in page  # § 6: das Wort verspräche die Verwaltungssicht


def test_karte_json_follows_dokumente_json(mini_run: Layout, default_settings: Settings) -> None:
    """§ 4.5, Format 1: je Dokument von dokumente.json eine Zeile, Orte in der viewBox, Gremien gültig."""
    data = _karte(mini_run)
    listed = json.loads((mini_run.site_data / "dokumente.json").read_text(encoding="utf-8"))
    assert data["format"] == 1 and len(data["docs"]) == len(listed["documents"])
    page = _start(mini_run)
    box = re.search(r'viewBox="0 0 (\d+) (\d+)"', page)
    assert box is not None
    width, height = int(box.group(1)), int(box.group(2))
    assert all(0 <= p[0] <= width and 0 <= p[1] <= height for p in data["places"])
    assert all(p[3] in range(len(data["arts"])) for p in data["places"])
    limit = default_settings.report.start.max_places
    for doc in data["docs"]:
        assert -1 <= doc[0] < len(data["months"]) and 0 <= doc[1] < len(data["gremien"])
        rest = doc[2:]
        assert rest, doc
        assert all(v >= 0 for v in rest) or all(v < 0 for v in rest), doc
        if rest[0] >= 0:
            assert len(rest) <= limit and all(v < len(data["places"]) for v in rest)
    first, last = data["window"]
    assert 0 <= first <= last < len(data["months"]) and last - first + 1 <= 12
    # kein Punkt feiner als Straße je Wahlbezirk: jedes Paar (Name, Wahlbezirk) einmal
    pairs = [(p[4], p[2]) for p in data["places"]]
    assert len(pairs) == len(set(pairs))


def test_karte_json_has_its_download_row_and_stays_small(
    mini_run: Layout, default_settings: Settings
) -> None:
    details = _details(mini_run)
    assert f'href="data/{KARTE_NAME}"' in details
    assert (
        mini_run.site_data / KARTE_NAME
    ).stat().st_size < default_settings.report.map_budget_bytes


def test_without_script_the_map_is_the_choropleth_of_the_last_months(mini_run: Layout) -> None:
    """§ 4.7: die Klassen der Flächen sind die aus karte.json im voreingestellten Zeitraum."""
    data = _karte(mini_run)
    first, last = data["window"]
    counts: dict[int, int] = {}
    for doc in data["docs"]:
        if not first <= doc[0] <= last:
            continue
        districts = {-v for v in doc[2:]} if doc[2] < 0 else {data["places"][p][2] for p in doc[2:]}
        for d in districts:
            counts[d] = counts.get(d, 0) + 1
    page = _start(mini_run)
    shown = dict(
        re.findall(r'data-wb="(\d+)"[^>]*><title>Wahlbezirk \d+ [^:]*: ([\d ]+) Dokumente', page)
    )
    assert shown and {int(k): int(v.replace(" ", "")) for k, v in shown.items()} == {
        k: counts.get(k, 0) for k in map(int, shown)
    }
    areas = re.findall(r'<path class="start-area (q\d)"', page)
    assert len(areas) == len(shown)


def test_the_map_contrast_holds_against_the_areas() -> None:
    """§ 4.3, WCAG 1.4.11: Kreise in --accent gegen --surface und die neutralen Flächen, beide Modi."""
    from georep.report.render import environment

    frame = environment().loader.get_source(environment(), "frame/style.css.j2")[0]  # type: ignore[union-attr]
    css = frame + _asset("karte.css")
    assert ".start-plain .start-area { fill: var(--grid); }" in css
    blocks = frame.split("@media (prefers-color-scheme: dark)")
    for mode, block in (("hell", blocks[0]), ("dunkel", blocks[1])):
        colours = {}
        for name in ("accent", "surface", "grid"):
            found = re.search(rf"--{name}: (#[0-9a-f]{{6}})", block)
            assert found is not None, (mode, name)
            colours[name] = found.group(1)
        for ground in ("surface", "grid"):
            assert _contrast(colours["accent"], colours[ground]) >= 3.0, (mode, ground)


def test_the_start_page_stays_under_its_budget(
    mini_run: Layout, default_settings: Settings
) -> None:
    size = mini_run.site_index.stat().st_size
    assert size < default_settings.report.start_budget_bytes
    page = _start(mini_run)
    assert "tile.openstreetmap" not in page and "<script src" not in page and "<link " not in page
