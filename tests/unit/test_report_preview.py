"""Die Vorschau langer Tabellen (Punkt 48): Zeilen, Bedienelement, kein Skript, Druck.

Eine lange Tabelle zeigt Kopf und die ersten ``report.table_preview_rows`` Zeilen; darunter steht
eine Schaltfläche „alle n Zeilen zeigen". Welche Zeilen sichtbar sind, entscheidet eine CSS-Regel
und kein Attribut je Zeile — darum prüft dieser Test die Regeln und das Markup, nicht verborgene
Attribute (die Gründe in ``docs/seitengroesse-2026-10.md``, § 3.2). Die Mini-Fixture hat drei
Wahlbezirke, also klappt mit der Vorgabe 3 nichts ein; die Tests setzen ``preview_rows`` selbst.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pydantic
import pytest

from georep.report.model import ReportModel
from georep.report.render import Visuals, render_report
from georep.settings import Report

BUTTON = re.compile(
    r'<p class="more"><button type="button" aria-expanded="false" '
    r'aria-controls="([\w-]+)" data-less="([^"]+)">([^<]+)</button></p>'
)


@pytest.fixture(scope="module")
def narrow(mini_model: ReportModel, mini_visuals: Visuals) -> str:
    """Die Mini-Seite mit einer einzigen Vorschauzeile: drei Wahlbezirke klappen dann ein."""
    return render_report(replace(mini_model, preview_rows=1), mini_visuals)


def test_the_setting_decides_how_many_rows_stay_visible(
    mini_model: ReportModel, mini_visuals: Visuals, narrow: str
) -> None:
    assert "table.preview tbody tr:nth-child(n+2) { display: none; }" in narrow
    wide = render_report(replace(mini_model, preview_rows=5), mini_visuals)
    assert "table.preview tbody tr:nth-child(n+6) { display: none; }" in wide


def test_a_table_longer_than_the_preview_gets_a_button_and_a_short_one_does_not(
    mini_model: ReportModel, mini_visuals: Visuals, narrow: str
) -> None:
    """Drei Wahlbezirke, eine Vorschauzeile: Schaltfläche. Fünf Vorschauzeilen: keine."""
    assert "districts" in {match.group(1) for match in BUTTON.finditer(narrow)}
    assert "alle 3 Zeilen zeigen</button>" in narrow
    wide = render_report(replace(mini_model, preview_rows=5), mini_visuals)
    assert "districts" not in {match.group(1) for match in BUTTON.finditer(wide)}


def test_nothing_is_collapsed_without_a_preview(
    mini_model: ReportModel, mini_visuals: Visuals
) -> None:
    """``table_preview_rows = 0`` heißt: keine Regel, keine Schaltfläche, kein noscript-Block."""
    page = render_report(replace(mini_model, preview_rows=0), mini_visuals)
    assert "tr:nth-child(n+1) { display: none; }" not in page and not BUTTON.search(page)
    # Der Abschnitt „Suche" hat seinen eigenen <noscript>; der Block mit dem Stil gehört hierher.
    assert "<noscript><style>" not in page
    assert 'class="preview"' in page  # die Klasse bleibt, sie wirkt nur nicht


def test_every_button_controls_a_preview_table_and_every_long_table_has_one(narrow: str) -> None:
    """``aria-controls`` zeigt auf eine Tabelle mit ``class="preview"``, und zwar auf ihre ID."""
    tables = dict(re.findall(r'<table id="([\w-]+)"((?: [a-z-]+="[^"]*")*)>', narrow))
    previews = {name for name, attrs in tables.items() if 'class="preview"' in attrs}
    assert previews, narrow[:200]
    for name, less, label in BUTTON.findall(narrow):
        assert name in previews, name
        assert less == "wieder einklappen"
        assert label.startswith("alle ") and label.endswith(" Zeilen zeigen")
    # Jede Vorschautabelle mit mehr Zeilen als der Vorschau hat eine Schaltfläche; auf der
    # Mini-Fixture sind das die drei Wahlbezirke und die Begriffe, die kürzeren nicht.
    controlled = {name for name, _, _ in BUTTON.findall(narrow)}
    for name in controlled:
        rows = re.search(rf'<table id="{name}".*?</table>', narrow, re.S)
        assert rows is not None and rows.group(0).count("<tr") > 1


def test_a_collapsed_row_opens_when_it_is_selected_targeted_or_the_table_is_open(
    narrow: str,
) -> None:
    """Drei Nähte: ``georep.select`` setzt ``selected``, die Adresse setzt ``:target``, die
    Schaltfläche ``open``.

    ``:target`` ist der Sprung aus einer geteilten Adresse: ``index.html#bezirk-17`` zielt auf eine
    Zeile, die die Vorschau verbirgt, und ohne diese Regel scrollte der Browser ins Leere -- für 38
    der 41 Wahlbezirke (Review 2026-10-13). Niemand liest dafür ``location.hash``; das kann CSS.
    """
    assert (
        "table.preview.open tbody tr, table.preview tbody tr.selected,"
        " table.preview tbody tr:target { display: table-row; }" in narrow
    )
    assert 'table.classList.toggle("open", open)' in narrow
    assert 'button.setAttribute("aria-expanded", open ? "true" : "false")' in narrow


def test_the_button_stands_before_its_table(narrow: str) -> None:
    """Das Aufklappmuster der WAI-ARIA Authoring Practices: der Aufklapper vor dem Inhalt.

    Stand die Schaltfläche hinter der Tabelle, rutschte sie beim Aufklappen mit dem Fokus aus dem
    Bild -- bei 41 Zeilen von y = 436 auf y = 3924 (Review 2026-10-13).
    """
    for name, _, _ in BUTTON.findall(narrow):
        button = narrow.index(f'aria-controls="{name}"')
        table = narrow.index(f'<table id="{name}"')
        assert button < table, name


def test_the_button_shows_whether_it_is_open(narrow: str) -> None:
    """Ein Dreieck macht aus dem Text ein Bedienelement; es kommt aus dem Zustand, nicht aus JS."""
    assert 'p.more button::before { content: "▸ "; }' in narrow
    assert 'p.more button[aria-expanded="true"]::before { content: "▾ "; }' in narrow


def test_without_javascript_every_row_and_no_button_is_there(narrow: str) -> None:
    block = re.search(r"<noscript><style>(.*?)</style></noscript>", narrow, re.S)
    assert block is not None
    assert "table.preview tbody tr { display: table-row !important; }" in block.group(1)
    assert "p.more { display: none !important; }" in block.group(1)


def test_printing_shows_every_row(narrow: str) -> None:
    block = re.search(r"@media print \{(.*?)\n\}", narrow, re.S)
    assert block is not None
    assert "table.preview tbody tr { display: table-row !important; }" in block.group(1)
    assert "p.more, #tooltip { display: none !important; }" in block.group(1)


def test_the_number_of_preview_rows_stays_in_its_bounds() -> None:
    assert Report().table_preview_rows == 3
    for wrong in (-1, 51):
        with pytest.raises(pydantic.ValidationError):
            Report(table_preview_rows=wrong)
