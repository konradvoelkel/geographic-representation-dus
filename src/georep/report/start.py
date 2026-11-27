"""Die Startseite ``index.html`` (``docs/plan-startseite-2026-11.md``).

Seit Stufe U (§ 3, § 9) steht die ganze Auswertung als ``details.html`` daneben, und die Startseite
ist die Seite, die eine Adresse ohne Dateinamen öffnet. Seit Stufe B trägt sie den Kopf mit
Datenstand, die Kurzfassung (§ 8), die Karte mit Zeitregler und Gremium (§ 4 bis § 7,
``report.startkarte``), den Linkblock und den Fuß des Rahmens.

**Alte Anker.** Bis ``v0.38.0`` stand die Auswertung unter ``index.html``, und Links mit Anker
(``#suche=<begriff>``, ``#bezirk-17``, ``#gremien``) zeigen von außen und aus den Dokumenten auf
die Wurzel. GitHub Pages kann nicht umleiten; darum ersetzt ein Skript ganz oben auf der Startseite
jede Adresse, deren Anker kein Schlüssel der Startseite ist, durch ``details.html`` mit demselben
Anker. Die eigenen ids der Startseite beginnen mit ``START_PREFIX``, ihre Schlüssel in der Adresse
heißen wie ``START_KEYS``; ein Test hält fest, dass keiner davon eine id auf ``details.html`` ist.
Dazu kommen nur die ids des Rahmens (``FRAME_IDS``: Dialog und Tooltip), die auch die Details tragen.

**Kurzfassung** (§ 8, Frage S.3: K1 bis K4, ohne K5). Jeder Satz ist aus dem ``ReportModel``
gerechnet und verlinkt den Abschnitt von ``details.html``, aus dem seine Zahl stammt. Nur Aussagen
aus dem Verfahren der Arbeit, aus Regeln (Gremium) und aus dem Test über alle Wahlbezirke; die
Spalte „ohne Ausreißer" ist explorativ und steht nicht hier, nichts ist KI-kodiert, keine Partei.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources

import deal

from georep.prep.bodies import UNKNOWN
from georep.report.charts import rate_label
from georep.report.model import ReportModel, format_de, percent_de
from georep.report.render import (
    ALLOWED_LINKS,
    CC0,
    GPL,
    ODBL,
    OSM_COPYRIGHT,
    REPOSITORY,
    WIKIDATA,
    WIKIPEDIA,
    environment,
    external_links,
    model_links,
)
from georep.report.startkarte import (
    StartMap,
    choropleth,
    choropleth_legend,
    point_radius,
)

DETAILS_NAME = "details.html"  # Layout.site_details; die Startseite verlinkt relativ daneben
START_PREFIX = "start-"  # jede id der Startseite beginnt so (plan-startseite, § 3)
# Die Schlüssel der Startseite in der Adresse (#zeitraum=…&gremium=…, § 5). Kleinbuchstaben, damit
# sie ohne Maskierung im regulären Ausdruck des Skripts stehen.
START_KEYS = ("zeitraum", "gremium")
# Die ids des Rahmens, die auch details.html trägt: Dokumentdialog und Tooltip (frame/dialog.html.j2)
FRAME_IDS = ("docs", "docs-title", "tooltip")
_WORD = re.compile(r"^[a-z]+$")


@dataclass(frozen=True)
class StartLink:
    """Ein Eintrag im Linkblock der Startseite: relativer Link, Titel, ein Satz dazu."""

    href: str
    title: str
    lead: str


@deal.pre(lambda: all(_WORD.fullmatch(key) for key in START_KEYS))
@deal.post(lambda result: len(result.encode("utf-8")) < 500)
def redirect_script() -> str:
    """Das Skript ganz oben auf der Startseite: alte Anker nach ``details.html`` (unter 0,5 KB).

    Es bleibt, wer keinen Anker hat oder einen der Startseite: eine id mit ``START_PREFIX`` oder
    einen Schlüssel aus ``START_KEYS``, allein oder mit ``=`` oder ``&`` dahinter. Alles andere
    ersetzt ``location.replace`` durch ``details.html`` mit demselben Anker, ohne Eintrag in der
    Chronik, damit „Zurück" nicht wieder auf die Weiterleitung führt.
    """
    keys = "|".join(START_KEYS)
    return (
        "(function(){var h=location.hash.slice(1);"
        f"if(h&&!/^(?:{START_PREFIX}|(?:{keys})(?:[=&]|$))/.test(h))"
        f'location.replace("{DETAILS_NAME}"+location.hash);}})();'
    )


def start_links(model: ReportModel) -> tuple[StartLink, ...]:
    """Der Linkblock: Details, Downloads, die Unterseiten der Beiträge, die anderen Perioden.

    Die Nachbarstädte und der Städtevergleich stehen nicht hier: erst ``georep publish`` weiß,
    welche Seiten wirklich daneben liegen, und setzt ihre Zeile an der Marke im Kopf.
    """
    links = [
        StartLink(
            DETAILS_NAME,
            "Details",
            "die ganze Auswertung: Kernzahlen, Karte, Tabellen je Wahlbezirk, Methode, Quellen",
        ),
        StartLink(
            f"{DETAILS_NAME}#downloads",
            "Downloads",
            "alle Tabellen als Parquet und CSV, mit Prüfsummen und Spaltenschema",
        ),
    ]
    links.extend(StartLink(page.href, page.title, page.lead) for page in model.pages)
    city = model.city.genitive if model.city is not None else ""
    if model.parent_url:
        links.append(
            StartLink(model.parent_url, "Hauptperiode", f"die Auswertung der Hauptperiode {city}")
        )
    if model.comparison is not None:
        comparison = model.comparison
        links.append(
            StartLink(
                comparison.subpage,
                comparison.previous,
                "dieselbe Auswertung für die ältere Wahlperiode",
            )
        )
    if model.monitoring_url:
        links.append(
            StartLink(
                model.monitoring_url,
                "Laufende Wahlperiode",
                f"die Dokumente seit der Kommunalwahl {model.stand.election:%Y}",
            )
        )
    return tuple(links)


# --- Kurzfassung (§ 8) --------------------------------------------------------------------------

TEXT_SHARE = 0.9  # darunter sagt K1, wie viele Dokumente einen Text haben (Mönchengladbach 22 %)
SIGNIFICANCE = 0.05  # das vorab festgelegte Niveau von Tabelle 5
# Woher die Dokumente kommen, als Satzglied nach „stammen" (K4); die Folge ist die der Anteile
KIND_PHRASES = {
    "bezirksvertretung": "aus Bezirksvertretungen",
    "rat": "aus dem Rat",
    "ausschuss": "aus Ausschüssen",
    "beirat": "aus Beiräten",
}
UNKNOWN_KIND = UNKNOWN  # prep.bodies: die Klasse ohne erkanntes Gremium


@dataclass(frozen=True)
class Sentence:
    """Ein Satz der Kurzfassung mit dem Abschnitt von ``details.html``, aus dem seine Zahl stammt."""

    key: str  # K1 bis K4, wie im Plan
    text: str
    target: str  # eine id auf details.html
    link: str


def _and(parts: Sequence[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " und " + parts[-1]


def scope_sentence(model: ReportModel) -> Sentence:
    """K1: Umfang; liegt der Anteil mit Text unter 90 %, sagt der Satz das zuerst."""
    f = model.figures
    period = model.period.title
    places = f"mindestens eine Straße oder einen Ort aus dem Wörterbuch eines der {f.districts} Wahlbezirke"
    if f.documents and f.documents_with_text / f.documents >= TEXT_SHARE:
        text = (
            f"{format_de(f.documents_hit)} der {format_de(f.documents)} Ratsdokumente der {period} "
            f"({percent_de(f.documents_hit / f.documents, 0)}) nennen {places}."
        )
    else:
        share = f.documents_hit / f.documents_with_text if f.documents_with_text else 0.0
        text = (
            f"Nur {format_de(f.documents_with_text)} der {format_de(f.documents)} Ratsdokumente der "
            f"{period} haben einen Text, den die Suche lesen kann; {format_de(f.documents_hit)} "
            f"davon ({percent_de(share, 0)}) nennen {places}."
        )
    return Sentence("K1", text, "kernzahlen", "Kernzahlen")


def spread_sentence(model: ReportModel) -> Sentence | None:
    """K2: der sichtbarste und der am wenigsten sichtbare Wahlbezirk, mit dem Vorbehalt (r)."""
    rows = [d for d in model.districts if d.eligible > 0]
    if len(rows) < 2:
        return None
    high = max(rows, key=lambda d: (d.rate, -d.id))
    low = min(rows, key=lambda d: (d.rate, d.id))
    if low.rate <= 0 or high.rate <= low.rate:
        return None
    text = (
        f"Gemessen an den Wahlberechtigten nennen die Dokumente Wahlbezirk {high.id} {high.name} "
        f"am häufigsten ({rate_label(high.rate)} Dokumente je Wahlberechtigtem) und Wahlbezirk "
        f"{low.id} {low.name} am seltensten ({rate_label(low.rate)}), ein Unterschied um das "
        f"{format_de(high.rate / low.rate, 1)}-Fache."
    )
    if model.bias is not None:
        text += (
            " Ein Teil davon liegt am Wörterbuch: Wahlbezirke mit mehr Straßen und Orten haben "
            f"mehr Treffer (r = {format_de(model.bias.hits_terms, 2)})."
        )
    return Sentence("K2", text, "wahlbezirke", "Je Wahlbezirk")


def question_sentence(model: ReportModel, has_months: bool) -> Sentence:
    """K3: die Leitfrage, nur aus der Spalte über alle Wahlbezirke (die zweite ist explorativ)."""
    if model.regression is None:
        return Sentence(
            "K3",
            "Zur laufenden Wahlperiode gibt es noch keine Wahlbeteiligung, also keine Regression; "
            "gezählt werden die Dokumente je Monat.",
            "monate" if has_months else "kernzahlen",
            "Je Monat" if has_months else "Kernzahlen",
        )
    fit_all = model.regression.all
    if fit_all.p >= SIGNIFICANCE:
        text = (
            "Einen Zusammenhang zwischen dieser Trefferquote und der Wahlbeteiligung belegt die "
            f"Regression über alle {fit_all.n} Wahlbezirke nicht (p = {format_de(fit_all.p, 2)})."
        )
    else:
        text = (
            f"Über alle {fit_all.n} Wahlbezirke hängen Trefferquote und Wahlbeteiligung auf dem "
            f"5-%-Niveau zusammen (p = {format_de(fit_all.p, 3)}, r = {format_de(fit_all.r, 2)})."
        )
    return Sentence("K3", text, "zusammenhang", "Trefferquote und Wahlbeteiligung")


def bodies_sentence(model: ReportModel) -> Sentence | None:
    """K4: aus welchen Gremien die Dokumente mit Treffer stammen, mit „unbekannt", wo es das gibt."""
    totals: dict[str, int] = {}
    for row in model.bodies:
        totals[row.kind] = totals.get(row.kind, 0) + row.with_hits
    total = sum(totals.values())
    if not total:
        return None
    known = sorted(
        (kind for kind in KIND_PHRASES if totals.get(kind)),
        key=lambda kind: (-totals[kind], list(KIND_PHRASES).index(kind)),
    )
    parts = [f"{percent_de(totals[kind] / total, 0)} {KIND_PHRASES[kind]}" for kind in known]
    unknown = totals.get(UNKNOWN_KIND, 0)
    if not parts:
        text = "Für die Dokumente mit Treffer nennt keine Quelle das Gremium"
    else:
        text = f"Von den Dokumenten mit Treffer stammen {_and(parts)}"
        if unknown:
            text += f"; bei {percent_de(unknown / total, 0)} ist das Gremium unbekannt"
    return Sentence("K4", text + ".", "gremien", "Gremien")


def summary_sentences(model: ReportModel) -> tuple[Sentence, ...]:
    """K1 bis K4 (§ 8, Frage S.3: ohne K5), jeder Satz aus dem Modell und mit einem Link."""
    has_months = any(row.month is not None for row in model.timeline)
    found = [
        scope_sentence(model),
        spread_sentence(model),
        question_sentence(model, has_months),
        bodies_sentence(model),
    ]
    return tuple(s for s in found if s is not None)


def _asset(name: str) -> str:
    """Stil und Skript der Startseite (``templates/start/``), wie die Abschnitte der Details."""
    return (resources.files("georep.report") / "templates" / "start" / name).read_text(
        encoding="utf-8"
    )


def _only_allowed_links(model: ReportModel, start_map: StartMap, result: str = "") -> bool:
    return set(external_links(result)) <= ALLOWED_LINKS | model_links(model)


@deal.post(lambda result: result.startswith("<!doctype html>") and 'lang="de"' in result)
@deal.ensure(
    _only_allowed_links, message="nur die erlaubten Links nach außen, keine externen Ressourcen"
)
def render_start(model: ReportModel, start_map: StartMap) -> str:
    """Die Startseite als HTML; sie liest dasselbe Modell wie ``details.html`` und die Karte."""
    classes, counts = choropleth(start_map)
    return (
        environment()
        .get_template("start.html.j2")
        .render(
            model=model,
            redirect=redirect_script(),
            start_links=start_links(model),
            details=DETAILS_NAME,
            summary=summary_sentences(model),
            start_map=start_map,
            classes=classes,
            counts=counts,
            legend=choropleth_legend(classes),
            top=start_map.top(),
            size=point_radius,
            start_css=_asset("karte.css"),
            start_js=_asset("karte.js"),
            links={
                "repository": REPOSITORY,
                "cc0": CC0,
                "gpl": GPL,
                "osm": OSM_COPYRIGHT,
                "odbl": ODBL,
                "wikidata": WIKIDATA,
                "wikipedia": WIKIPEDIA,
            },
        )
    )
