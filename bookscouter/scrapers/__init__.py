"""Alle verfügbaren Shop-Scraper an einer Stelle.

Damit CLI und UI dieselbe Liste verwenden und ein neuer Shop nur hier
eingetragen werden muss.
"""

from bookscouter.scrapers.altraverse import AltraverseScraper
from bookscouter.scrapers.amazon import AmazonScraper
from bookscouter.scrapers.base import Scraper, ScrapeResult
from bookscouter.scrapers.danibooks import DaniBooksScraper
from bookscouter.scrapers.morawa import MorawaScraper
from bookscouter.scrapers.thalia import (
    BuecherDeScraper,
    OrellFuessliScraper,
    OsianderScraper,
    ThaliaDeScraper,
    ThaliaScraper,
)
from bookscouter.scrapers.waltscomicshop import WaltsComicShopScraper

# Die Reihenfolge ist nicht kosmetisch: sie bestimmt die Reihenfolge der
# Shop-Checkboxen in der Oberfläche und die Farbzuordnung im Preisverlauf.
# Neue Shops deshalb hinten anhängen – wer vorne einfügt, verschiebt die
# Farben aller bestehenden Linien.
ALL_SCRAPERS = [
    ThaliaScraper,
    ThaliaDeScraper,
    BuecherDeScraper,
    MorawaScraper,
    WaltsComicShopScraper,
    AmazonScraper,
    OsianderScraper,
    OrellFuessliScraper,
    DaniBooksScraper,
    AltraverseScraper,
]

__all__ = [
    "ALL_SCRAPERS",
    "AltraverseScraper",
    "AmazonScraper",
    "BuecherDeScraper",
    "DaniBooksScraper",
    "MorawaScraper",
    "OrellFuessliScraper",
    "OsianderScraper",
    "Scraper",
    "ScrapeResult",
    "ThaliaDeScraper",
    "ThaliaScraper",
    "WaltsComicShopScraper",
]
