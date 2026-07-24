"""Gemeinsames Interface für alle Shop-Scraper: ISBN rein, Titel+Preis raus."""

import subprocess
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from bookscouter.config import REQUEST_DELAY_SECONDS, USER_AGENT


@dataclass
class ScrapeResult:
    shop: str
    isbn: str
    titel: str | None
    preis: float | None
    gefunden: bool


@dataclass
class HttpResponse:
    text: str
    ok: bool
    status_code: int


class Scraper:
    """Basisklasse, die jeder Shop-Scraper implementiert."""

    shop_name: str

    def __init__(self) -> None:
        self._last_request_time: float | None = None

    def _get(self, url: str, params: dict | None = None) -> HttpResponse:
        """GET-Request mit Mindestabstand zwischen Requests (Rate-Limiting).

        Nutzt den `curl`-Befehl statt der `requests`-Bibliothek: manche Shops
        (z. B. Thalia) blocken den TLS-Fingerabdruck von Python-HTTP-Clients
        per Cloudflare, unabhängig vom User-Agent-Header. curl mit demselben
        ehrlichen User-Agent kommt durch, ohne einen Browser vorzutäuschen.
        """
        if params:
            url = f"{url}?{urlencode(params)}"

        if self._last_request_time is not None:
            wait = REQUEST_DELAY_SECONDS - (time.monotonic() - self._last_request_time)
            if wait > 0:
                time.sleep(wait)

        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "10", "-A", USER_AGENT, "-w", "\n%{http_code}", url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._last_request_time = time.monotonic()

        body, _, status_text = result.stdout.rpartition("\n")
        status_code = int(status_text) if status_text.isdigit() else 0
        return HttpResponse(text=body, ok=200 <= status_code < 300, status_code=status_code)

    def scrape(self, isbn: str) -> ScrapeResult:
        raise NotImplementedError
