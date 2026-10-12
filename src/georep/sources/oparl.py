"""Paper-Metadaten seitenweise über die OParl-Schnittstelle, typisiert und wiederaufnehmbar.

Der Server listet neueste zuerst. Mit ``stop_when_older`` endet der Abruf, sobald eine Seite nur
noch Paper vor dem Periodenbeginn enthält; die Arbeit hat alle 365 Seiten gelesen, davon 270 für
Paper vor 2020. ``modified_since`` (OParl 1.1, ISO-8601) holt nur Geändertes; ob der Server es
beachtet, zeigt ``georep status`` nach einem Lauf, nicht diese Funktion.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import deal

from georep.errors import FetchError, NetworkError
from georep.http import Transport, network_errors
from georep.io import write_json
from georep.oparl import OparlOrganization, OrganizationPage, PaperPage
from georep.records import PaperRecord
from georep.settings import Period


@dataclass(frozen=True)
class FetchReport:
    pages: int
    seen: int
    kept: int
    stopped_early: bool
    # Option 04: alle gesehenen Paper mit mindestens einem Urheberfeld, auch die außerhalb der
    # Periode. Die Zahl ist die Probe, ob der Server inzwischen originatorOrganization liefert;
    # am 2026-10-09 war sie null (docs/plans/04-parteien.md, § 3.1).
    originators: int = 0
    # Option 02: wo der Abruf begann und wo er weiterginge; der Abruf einer alten Periode dauert
    # Stunden, und der Log soll beides nennen, nicht nur die Zahl der Seiten.
    first_url: str = ""
    next_url: str | None = None

    def summary(self) -> str:
        tail = "; Rest älter als der Periodenbeginn" if self.stopped_early else ""
        where = f"; ab {self.first_url}" if self.first_url else ""
        return (
            f"{self.pages} Seiten, {self.seen} Paper gesehen, {self.kept} im Zeitraum, "
            f"davon {self.originators} mit Urheberfeld{tail}{where}"
        )


def start_url(endpoint: str, first_page: int) -> str:
    """Die erste URL des Abrufs; OParl zählt Seiten ab 1, Seite 1 ist der Endpunkt selbst.

    Die Liste ist neueste zuerst: ein Profil für eine alte Periode überspringt so die Seiten der
    jüngeren Perioden, ohne sie zu laden (2014 bis 2020 beginnt bei Seite 90, Stand 2026-10).
    """
    return endpoint if first_page <= 1 else f"{endpoint}?page={first_page}"


# Nach jeder vollständig gelesenen Seite: die Paper dieser Seite und die URL der nächsten. Der
# Aufrufer speichert beides, dann kostet ein Abbruch nach drei Stunden keine drei Stunden.
PageDone = Callable[[list[PaperRecord], str | None], None]


@deal.raises(FetchError, NetworkError)
@deal.post(lambda result: result[1].kept == len(result[0]) and result[1].kept <= result[1].seen)
def fetch_papers(
    http: Transport,
    endpoint: str,
    period: Period,
    *,
    delay_s: float = 0.0,
    modified_since: dt.datetime | None = None,
    stop_when_older: bool = True,
    max_pages: int | None = None,
    first_page: int = 1,
    resume_from: str | None = None,
    on_page: PageDone | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[PaperRecord], FetchReport]:
    records: list[PaperRecord] = []
    pages = seen = with_originator = 0
    stopped = False
    first = resume_from or start_url(endpoint, first_page)
    url: str | None = first
    params = {"modified_since": modified_since.isoformat()} if modified_since else None
    while url is not None and (max_pages is None or pages < max_pages):
        with network_errors(url):
            response = http.get(url, params=params)
            response.raise_for_status()
        params = None  # der Filter steht nur auf der ersten Anfrage; next-Links tragen ihn weiter
        try:
            # pydantics ValidationError ist ein ValueError, wie der JSON-Fehler
            page = PaperPage.model_validate(response.json())
        except ValueError as error:
            raise FetchError(f"OParl {url}: keine gültige Paper-Seite ({error})") from error
        pages += 1
        seen += len(page.data)
        for paper in page.data:
            if paper.has_originator:
                with_originator += 1
        kept = [
            PaperRecord.from_oparl(paper)
            for paper in page.data
            if not paper.deleted and paper.in_period(period.start, period.end)
        ]
        records.extend(kept)
        dates = [p.date for p in page.data if p.date is not None]
        if stop_when_older and dates and max(dates) < period.start:
            stopped = True
            if on_page is not None:
                on_page(kept, None)
            break
        url = page.links.next
        if on_page is not None:
            on_page(kept, url)
        if url is not None and delay_s > 0:
            sleep(delay_s)
    return records, FetchReport(pages, seen, len(records), stopped, with_originator, first, url)


def _ids_are_unique(result: tuple[list[OparlOrganization], int]) -> bool:
    ids = [o.id for o in result[0]]
    return len(ids) == len(set(ids))


@deal.raises(FetchError, NetworkError)
@deal.post(_ids_are_unique, message="jede Organisation einmal")
def fetch_organizations(
    http: Transport,
    endpoint: str,
    *,
    delay_s: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[OparlOrganization], int]:
    """Alle Organisationen (Fraktionen, Ausschüsse, Bezirksvertretungen) und die Zahl der Seiten.

    Düsseldorf hat eine Seite mit 58 Objekten, die am 2026-10-11 in 0,47 s kam; die Funktion folgt
    trotzdem ``links.next``, weil größere Körperschaften mehrere Seiten haben. Gelöschte
    Organisationen bleiben draußen, Dubletten über Seitengrenzen werden verworfen (Nachbedingung).
    """
    found: list[OparlOrganization] = []
    known: set[str] = set()
    pages = 0
    url: str | None = endpoint
    while url is not None:
        with network_errors(url):
            response = http.get(url)
            response.raise_for_status()
        try:
            page = OrganizationPage.model_validate(response.json())
        except ValueError as error:
            raise FetchError(f"OParl {url}: keine gültige Organisationsseite ({error})") from error
        pages += 1
        for organization in page.data:
            if organization.deleted or organization.id in known:
                continue
            known.add(organization.id)
            found.append(organization)
        url = page.links.next
        if url is not None and delay_s > 0:
            sleep(delay_s)
    return found, pages


# --- Option 02: der Fortschritt eines mehrstündigen Abrufs -------------------------------------


def write_progress(path: Path, next_url: str | None, pages: int) -> None:
    """Wo der Abruf weiterginge, nach jeder gespeicherten Seite; ohne ``next_url`` ist er fertig."""
    write_json(
        path,
        {
            "next_url": next_url,
            "pages": pages,
            "written": dt.datetime.now(dt.UTC).isoformat(),
        },
    )


def read_progress(path: Path) -> str | None:
    """Die URL, bei der ein abgebrochener Abruf weitermachen soll; None, wenn keine ansteht.

    Eine unlesbare oder leere Datei ist kein Fehler: dann beginnt der Abruf bei ``first_page``,
    und der Store verwirft die Dubletten.
    """
    if not path.is_file():
        return None
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    url = saved.get("next_url") if isinstance(saved, dict) else None
    return url if isinstance(url, str) and url else None
