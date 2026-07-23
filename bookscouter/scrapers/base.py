"""Gemeinsames Interface für alle Shop-Scraper: ISBN rein, Titel+Preis raus."""

from dataclasses import dataclass


@dataclass
class ScrapeResult:
    shop: str
    isbn: str
    titel: str | None
    preis: float | None
    gefunden: bool


class Scraper:
    """Basisklasse, die jeder Shop-Scraper implementiert."""

    shop_name: str

    def scrape(self, isbn: str) -> ScrapeResult:
        raise NotImplementedError
