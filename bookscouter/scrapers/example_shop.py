"""Scraper for the first configured shop. Implemented in Phase 1."""

from bookscouter.scrapers.base import Scraper, ScrapeResult


class ExampleShopScraper(Scraper):
    shop_name = "Example Shop"

    def scrape(self, isbn: str) -> ScrapeResult:
        raise NotImplementedError
