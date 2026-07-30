"""Gemeinsames Interface für alle Shop-Scraper: ISBN rein, Titel+Preis raus."""

import subprocess
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from bookscouter.config import REQUEST_DELAY_SECONDS, USER_AGENT

# Ohne dieses Flag blitzt unter Windows bei jedem curl-Aufruf kurz ein
# Konsolenfenster auf – in der gepackten .exe, die selbst keine Konsole hat,
# wären das pro Suche bis zu zehn Blitzer. Nur unter Windows vorhanden.
_OHNE_KONSOLENFENSTER = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Rückfallwert, wenn ein Shop keine oder eine unbekannte Verfügbarkeit meldet.
# Bewusst nicht "Nicht auf Lager": ein fehlendes Feld heisst nicht, dass der
# Titel vergriffen ist, und eine falsche Aussage wäre schlechter als keine.
VERFUEGBARKEIT_UNBEKANNT = "Unbekannt"

# schema.org/ItemAvailability – Thalia-Plattform und Morawa liefern diese
# Werte als URL im JSON-LD ("https://schema.org/InStock").
_SCHEMA_ORG_VERFUEGBARKEIT = {
    "instock": "Auf Lager",
    "instoreonly": "Nur im Laden",
    "onlineonly": "Nur online",
    "limitedavailability": "Nur begrenzt",
    "preorder": "Vorbestellbar",
    "presale": "Vorbestellbar",
    "backorder": "Nachbestellt",
    "outofstock": "Nicht auf Lager",
    "soldout": "Ausverkauft",
    "discontinued": "Nicht mehr lieferbar",
}


def verfuegbarkeit_aus_schema_org(wert: object) -> str:
    """Übersetzt einen schema.org-Verfügbarkeitswert in einen Anzeigetext.

    Nimmt sowohl die URL-Schreibweise ("https://schema.org/InStock") als auch
    den blossen Namen ("InStock"). Alles, was fehlt, kein String ist oder
    nicht im Katalog steht, wird zu `VERFUEGBARKEIT_UNBEKANNT` – die Funktion
    wirft nie, damit ein unerwarteter Wert nie eine sonst gelungene Abfrage
    kostet.
    """
    if not isinstance(wert, str):
        return VERFUEGBARKEIT_UNBEKANNT
    name = wert.strip().rstrip("/").rsplit("/", 1)[-1].lower()
    return _SCHEMA_ORG_VERFUEGBARKEIT.get(name, VERFUEGBARKEIT_UNBEKANNT)


@dataclass
class ScrapeResult:
    shop: str
    isbn: str
    titel: str | None
    preis: float | None
    gefunden: bool
    # Anzeigetext der Lagerverfügbarkeit; bei nicht gefundenen Titeln
    # uninteressant, deshalb mit Rückfallwert vorbelegt.
    verfuegbarkeit: str = VERFUEGBARKEIT_UNBEKANNT
    # Produktseite beim Shop, in der Oberfläche als Link hinterlegt.
    url: str | None = None


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
            creationflags=_OHNE_KONSOLENFENSTER,
        )
        self._last_request_time = time.monotonic()

        body, _, status_text = result.stdout.rpartition("\n")
        status_code = int(status_text) if status_text.isdigit() else 0
        return HttpResponse(text=body, ok=200 <= status_code < 300, status_code=status_code)

    def scrape(self, isbn: str) -> ScrapeResult:
        raise NotImplementedError
