"""Gemeinsames Interface für alle Shop-Scraper: ISBN rein, Titel+Preis raus."""

import time
from dataclasses import dataclass

from bookscouter.config import REQUEST_DELAY_SECONDS
from bookscouter.http import HttpResponse, hole

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


class Scraper:
    """Basisklasse, die jeder Shop-Scraper implementiert."""

    shop_name: str

    def __init__(self) -> None:
        self._last_request_time: float | None = None

    def _get(self, url: str, params: dict | None = None) -> HttpResponse:
        """GET-Request mit Mindestabstand zwischen Requests (Rate-Limiting).

        Der Abstand wird je Scraper-Instanz gezählt, deshalb legen CLI und
        Oberfläche die Scraper einmal an und verwenden sie für alle Bücher
        einer Sammelabfrage weiter.
        """
        if self._last_request_time is not None:
            wait = REQUEST_DELAY_SECONDS - (time.monotonic() - self._last_request_time)
            if wait > 0:
                time.sleep(wait)

        try:
            return hole(url, params)
        finally:
            # Auch ein Fehlschlag ging über die Leitung und zählt für den
            # Mindestabstand – sonst würde ausgerechnet eine Fehlerserie
            # ungebremst weiterlaufen.
            self._last_request_time = time.monotonic()

    def scrape(self, isbn: str) -> ScrapeResult:
        raise NotImplementedError
