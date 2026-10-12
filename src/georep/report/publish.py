"""``georep publish``: die Stadtseiten zusammentragen und den Städtevergleich bauen (Option 01).

Je Stadt aus ``publish.cities`` wird der veröffentlichte Ordner ``data/<profil>/site/`` gelesen
und nach ``data/site/`` kopiert: die erste Stadt an die Wurzel, jede weitere nach
``data/site/<slug>/``. Liegt eine Stadt flach (Profil leer, die Hauptstadt der Arbeit), ist ihre
Seite schon die Wurzel und wird nicht kopiert (Frage 1.7). Aus ``summary.json``, ``wahlbezirke.geojson`` und
``wahlbezirke_auswertung.parquet`` beider Städte entsteht ``vergleich.html``; fehlt der Lauf
einer Stadt, sagt die Zusammenfassung das und der Vergleich entfällt.

Der Befehl ist wiederholbar: Zeit und Commit sind Eingaben, kopiert wird atomar über ein
temporäres Verzeichnis, und nichts außerhalb von ``data/site/`` wird angefasst.
"""

from __future__ import annotations

import datetime as dt
import shutil
from dataclasses import dataclass, replace
from pathlib import Path

import deal

from georep import __version__
from georep.layout import Layout
from georep.report.comparison import (
    CitySite,
    ComparisonModel,
    build_comparison,
    read_city_site,
    table_rows,
)
from georep.report.model import format_de
from georep.report.render import CC0, REPOSITORY, environment, external_links
from georep.settings import Settings, load_settings

COMPARISON_NAME = "vergleich.html"
# Die Vergleichsseite verlinkt nach außen nur das Repository und die Lizenz; die Städte liegen
# relativ daneben, die Quellen und Lizenzen der Daten nennt jede Stadtseite in ihrem Fuß.
COMPARISON_LINKS = frozenset({REPOSITORY, CC0})


@dataclass(frozen=True)
class PublishSummary:
    cities: tuple[str, ...]  # Städte mit Lauf, in der Reihenfolge von publish.cities
    missing: tuple[str, ...]  # Städte ohne Lauf
    files: int
    bytes: int
    comparison: bool

    def line(self) -> str:
        parts = [f"{len(self.cities)} Städte" if len(self.cities) != 1 else "1 Stadt"]
        parts.append("1 Vergleich" if self.comparison else "kein Vergleich")
        parts.append(f"{self.files} Dateien, {format_de(self.bytes / 1e6, 1)} MB")
        line = ", ".join(parts)
        if self.missing:
            line += "; kein Lauf: " + ", ".join(self.missing)
        return line


def city_layout(settings: Settings, root: Layout, slug: str) -> Layout:
    """Das Layout einer Stadt unter derselben Datenwurzel; ihr Profil bestimmt den Unterordner.

    Die Dateinamen und der Unterordner kommen aus dem Profil der anderen Stadt, die Wurzeln aus
    dem Lauf, der veröffentlicht: so liest ``publish`` genau das, was ``georep run`` dort schrieb.
    """
    if slug == settings.city.slug:
        return root
    other = load_settings(profile=slug, cwd=Path("/nonexistent"))
    return replace(
        Layout.from_settings(other),
        data_root=root.data_root,
        cache_root=root.cache_root,
        reference_root=root.reference_root,
    )


def _copy_tree(source: Path, target: Path) -> None:
    """Atomar genug: erst neben das Ziel schreiben, dann tauschen."""
    staging = target.with_name(target.name + ".neu")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(source, staging)
    if target.exists():
        shutil.rmtree(target)
    staging.rename(target)


def _tree_size(folder: Path) -> tuple[int, int]:
    files = [p for p in folder.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


@deal.post(
    lambda result: set(external_links(result)) <= COMPARISON_LINKS,
    message="der Vergleich verlinkt nur Repository und Lizenz nach außen",
)
def render_comparison(model: ComparisonModel) -> str:
    template = environment().get_template("vergleich.html.j2")
    return template.render(
        model=model, rows=table_rows(model), links={"repository": REPOSITORY, "cc0": CC0}
    )


def publish_sites(
    settings: Settings,
    layout: Layout,
    *,
    now: dt.datetime,
    commit: str | None = None,
    out: Path | None = None,
) -> PublishSummary:
    """Kopiert die Stadtseiten in den Veröffentlichungsordner und baut den Vergleich."""
    slugs = list(settings.publish.cities) or [settings.city.slug]
    root = out if out is not None else layout.data_root / "site"
    root.mkdir(parents=True, exist_ok=True)
    found: list[CitySite] = []
    missing: list[str] = []
    for index, slug in enumerate(slugs):
        source = city_layout(settings, layout, slug).site
        if not (source / "index.html").is_file():
            missing.append(slug)
            continue
        target = root if index == 0 else root / slug
        href = "" if index == 0 else f"{slug}/"
        if source.resolve() != target.resolve():
            _copy_tree(source, target)
        found.append(read_city_site(target, href, settings.geo.working_crs))
    comparison = len(found) >= 2
    if comparison:
        model = build_comparison(tuple(found), now=now, version=__version__, commit=commit)
        (root / COMPARISON_NAME).write_text(render_comparison(model), encoding="utf-8")
    elif (root / COMPARISON_NAME).exists():
        # Eine Stadt weniger als beim letzten Mal: der alte Vergleich wäre eine Lüge
        (root / COMPARISON_NAME).unlink()
    files, size = _tree_size(root)
    return PublishSummary(
        cities=tuple(city.slug for city in found),
        missing=tuple(missing),
        files=files,
        bytes=size,
        comparison=comparison,
    )
