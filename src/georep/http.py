"""HTTP-Sitzungen mit Timeout, Retry mit Backoff und User-Agent.

``requests`` kennt keinen Timeout pro Session; ohne einen hängt ein Aufruf beliebig lange
(bandit B113, viermal im Altcode, Stand 2026-10-10). ``make_session`` liefert eine Session,
die jedem Aufruf einen Timeout mitgibt, 429 und 5xx mit exponentiellem Backoff wiederholt und
das auf http wie https tut; der Altcode hatte den Adapter nur auf http gemountet, die PDFs
kommen aber per Redirect von https.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from requests_cache import DO_NOT_CACHE, CachedSession
from requests_cache.models.response import CachedResponse, OriginalResponse
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT_S = 180.0  # der OParl-Server brauchte am 2026-10-09 85 s pro Seite
DEFAULT_RETRIES = 5
DEFAULT_BACKOFF_S = 1.0
DEFAULT_USER_AGENT = "georep/0.1 (+https://github.com/konradvoelkel/geographic-representation-dus)"
RETRY_STATUSES = (429, 500, 502, 503, 504)


class Transport(Protocol):
    """Das, was Fetcher vom Netz brauchen. ``requests.Session`` erfüllt es, Fakes in Tests auch.

    Netz ist eine Eingabe, keine Umwelt: Funktionen nehmen einen ``Transport`` entgegen und
    bekommen ohne Angabe eine echte Session aus ``make_session``.
    """

    def get(self, url: str, *, params: Any = None, headers: Any = None) -> requests.Response: ...


class TimeoutSession(requests.Session):
    """Session, die jedem Aufruf einen Timeout mitgibt, wenn der Aufrufer keinen setzt."""

    def __init__(self, timeout_s: float) -> None:
        super().__init__()
        self.timeout_s = timeout_s

    def request(self, *args: Any, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout_s)
        return super().request(*args, **kwargs)


class CachedTimeoutSession(CachedSession):
    """Wie ``TimeoutSession``, aber mit requests-cache (SQLite) für Antworten nach URL-Regeln."""

    def __init__(self, timeout_s: float, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.timeout_s = timeout_s

    def request(self, *args: Any, **kwargs: Any) -> OriginalResponse | CachedResponse:
        kwargs.setdefault("timeout", self.timeout_s)
        return super().request(*args, **kwargs)


def cache_pattern(endpoint: str) -> str:
    """requests-cache vergleicht Muster ohne Schema: ``host/pfad*``."""
    parts = urlsplit(endpoint)
    return f"{parts.netloc}{parts.path}*"


def make_session(
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    retries: int = DEFAULT_RETRIES,
    backoff_s: float = DEFAULT_BACKOFF_S,
    user_agent: str = DEFAULT_USER_AGENT,
    cache_path: Path | None = None,
    cache_rules: Mapping[str, int] | None = None,
) -> requests.Session:
    """Session mit Timeout, Retry und User-Agent; mit ``cache_path`` zusätzlich ein Antwort-Cache.

    ``cache_rules`` bildet URL-Muster auf Sekunden ab (0 = nie cachen); alles ohne Regel wird
    nicht gecacht, PDFs also nie (die gehören in den PDF-Store, nicht in SQLite).
    """
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
    session: requests.Session
    if cache_path is None:
        session = TimeoutSession(timeout_s)
    else:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        session = CachedTimeoutSession(
            timeout_s,
            cache_name=str(cache_path),
            backend="sqlite",
            expire_after=DO_NOT_CACHE,
            urls_expire_after={
                k: (v if v > 0 else DO_NOT_CACHE) for k, v in (cache_rules or {}).items()
            },
            allowable_codes=(200,),
        )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = user_agent
    return session
