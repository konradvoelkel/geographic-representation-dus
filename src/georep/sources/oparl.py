"""Paper-Metadaten seitenweise über die OParl-Schnittstelle, typisiert und wiederaufnehmbar.

Der Server listet neueste zuerst. Mit ``stop_when_older`` endet der Abruf, sobald eine Seite nur
noch Paper vor dem Periodenbeginn enthält; die Arbeit hat alle 365 Seiten gelesen, davon 270 für
Paper vor 2020. ``modified_since`` (OParl 1.1, ISO-8601) holt nur Geändertes; ob der Server es
beachtet, zeigt ``georep status`` nach einem Lauf, nicht diese Funktion.
"""

from __future__ import annotations

import datetime as dt
import time
from collections.abc import Callable
from dataclasses import dataclass

import deal

from georep.errors import FetchError, NetworkError
from georep.http import Transport, network_errors
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

    def summary(self) -> str:
        tail = "; Rest älter als der Periodenbeginn" if self.stopped_early else ""
        return (
            f"{self.pages} Seiten, {self.seen} Paper gesehen, {self.kept} im Zeitraum, "
            f"davon {self.originators} mit Urheberfeld{tail}"
        )


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
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[PaperRecord], FetchReport]:
    records: list[PaperRecord] = []
    pages = seen = with_originator = 0
    stopped = False
    url: str | None = endpoint
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
            if not paper.deleted and paper.in_period(period.start, period.end):
                records.append(PaperRecord.from_oparl(paper))
        dates = [p.date for p in page.data if p.date is not None]
        if stop_when_older and dates and max(dates) < period.start:
            stopped = True
            break
        url = page.links.next
        if url is not None and delay_s > 0:
            sleep(delay_s)
    return records, FetchReport(pages, seen, len(records), stopped, with_originator)


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
