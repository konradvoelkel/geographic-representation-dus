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
from georep.oparl import PaperPage
from georep.records import PaperRecord
from georep.settings import Period


@dataclass(frozen=True)
class FetchReport:
    pages: int
    seen: int
    kept: int
    stopped_early: bool

    def summary(self) -> str:
        tail = "; Rest älter als der Periodenbeginn" if self.stopped_early else ""
        return f"{self.pages} Seiten, {self.seen} Paper gesehen, {self.kept} im Zeitraum{tail}"


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
    pages = seen = 0
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
            if not paper.deleted and paper.in_period(period.start, period.end):
                records.append(PaperRecord.from_oparl(paper))
        dates = [p.date for p in page.data if p.date is not None]
        if stop_when_older and dates and max(dates) < period.start:
            stopped = True
            break
        url = page.links.next
        if url is not None and delay_s > 0:
            sleep(delay_s)
    return records, FetchReport(pages, seen, len(records), stopped)
