"""Alle verfügbaren Shop-Scraper an einer Stelle.

Damit CLI und UI dieselbe Liste verwenden und ein neuer Shop nur hier
eingetragen werden muss.
"""

from bookscouter.scrapers.amazon import AmazonScraper
from bookscouter.scrapers.base import Scraper, ScrapeResult
from bookscouter.scrapers.morawa import MorawaScraper
from bookscouter.scrapers.thalia import BuecherDeScraper, ThaliaDeScraper, ThaliaScraper
from bookscouter.scrapers.waltscomicshop import WaltsComicShopScraper

ALL_SCRAPERS = [
    ThaliaScraper,
    ThaliaDeScraper,
    BuecherDeScraper,
    MorawaScraper,
    WaltsComicShopScraper,
    AmazonScraper,
]

__all__ = [
    "ALL_SCRAPERS",
    "AmazonScraper",
    "BuecherDeScraper",
    "MorawaScraper",
    "Scraper",
    "ScrapeResult",
    "ThaliaDeScraper",
    "ThaliaScraper",
    "WaltsComicShopScraper",
]
