"""Die Startseite ``index.html`` (``docs/plan-startseite-2026-11.md``).

Seit Stufe U (§ 3, § 9) steht die ganze Auswertung als ``details.html`` daneben, und die Startseite
ist die Seite, die eine Adresse ohne Dateinamen öffnet. In U trägt sie nur den Kopf, den Linkblock,
einen ``<noscript>``-Satz und das Skript, das alte Anker weiterleitet; Karte, Zeitregler und
Kurzfassung kommen in Stufe B.

**Alte Anker.** Bis ``v0.38.0`` stand die Auswertung unter ``index.html``, und Links mit Anker
(``#suche=<begriff>``, ``#bezirk-17``, ``#gremien``) zeigen von außen und aus den Dokumenten auf
die Wurzel. GitHub Pages kann nicht umleiten; darum ersetzt ein Skript ganz oben auf der Startseite
jede Adresse, deren Anker kein Schlüssel der Startseite ist, durch ``details.html`` mit demselben
Anker. Die eigenen ids der Startseite beginnen mit ``START_PREFIX``, ihre Schlüssel in der Adresse
heißen wie ``START_KEYS``; ein Test hält fest, dass keiner davon eine id auf ``details.html`` ist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import deal

from georep.report.model import ReportModel
from georep.report.render import (
    ALLOWED_LINKS,
    CC0,
    GPL,
    REPOSITORY,
    environment,
    external_links,
    model_links,
)

DETAILS_NAME = "details.html"  # Layout.site_details; die Startseite verlinkt relativ daneben
START_PREFIX = "start-"  # jede id der Startseite beginnt so (plan-startseite, § 3)
# Die Schlüssel der Startseite in der Adresse (#zeitraum=…&gremium=…, § 5). Kleinbuchstaben, damit
# sie ohne Maskierung im regulären Ausdruck des Skripts stehen.
START_KEYS = ("zeitraum", "gremium")
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


@deal.post(lambda result: result.startswith("<!doctype html>") and 'lang="de"' in result)
@deal.ensure(
    lambda model, result: set(external_links(result)) <= ALLOWED_LINKS | model_links(model),
    message="nur die erlaubten Links nach außen, keine externen Ressourcen",
)
def render_start(model: ReportModel) -> str:
    """Die Startseite als HTML; sie liest dasselbe Modell wie ``details.html``."""
    return (
        environment()
        .get_template("start.html.j2")
        .render(
            model=model,
            redirect=redirect_script(),
            start_links=start_links(model),
            details=DETAILS_NAME,
            links={"repository": REPOSITORY, "cc0": CC0, "gpl": GPL},
        )
    )
