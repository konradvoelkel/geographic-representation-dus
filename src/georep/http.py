"""HTTP-Sitzungen mit Timeout, Retry mit Backoff und User-Agent.

``requests`` kennt keinen Timeout pro Session; ohne einen hängt ein Aufruf beliebig lange
(bandit B113, viermal im Altcode, Stand 2026-10-10). ``make_session`` liefert eine Session,
die jedem Aufruf einen Timeout mitgibt, 429 und 5xx mit exponentiellem Backoff wiederholt und
das auf http wie https tut; der Altcode hatte den Adapter nur auf http gemountet, die PDFs
kommen aber per Redirect von https.
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT_S = 180.0  # der OParl-Server brauchte am 2026-10-09 85 s pro Seite
DEFAULT_RETRIES = 5
DEFAULT_BACKOFF_S = 1.0
DEFAULT_USER_AGENT = "georep/0.1 (+https://github.com/konradvoelkel/geographic-representation-dus)"
RETRY_STATUSES = (429, 500, 502, 503, 504)


class TimeoutSession(requests.Session):
    """Session, die jedem Aufruf einen Timeout mitgibt, wenn der Aufrufer keinen setzt."""

    def __init__(self, timeout_s: float) -> None:
        super().__init__()
        self.timeout_s = timeout_s

    def request(self, *args: Any, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout_s)
        return super().request(*args, **kwargs)


def make_session(
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    retries: int = DEFAULT_RETRIES,
    backoff_s: float = DEFAULT_BACKOFF_S,
    user_agent: str = DEFAULT_USER_AGENT,
) -> TimeoutSession:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_s,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    session = TimeoutSession(timeout_s)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = user_agent
    return session
