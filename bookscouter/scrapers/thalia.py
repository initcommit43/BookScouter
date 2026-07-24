"""Scraper für thalia.at: ISBN rein, Titel + Preis raus.

Thalia bietet keine ISBN-basierte Produkt-URL an. Der einzige Weg, eine ISBN
einer Produktseite zuzuordnen, ist die Trefferliste unter /suche?sq=<isbn>.
robots.txt sperrt /suche zwar für Bots allgemein, dieses Tool fragt aber
ausschließlich einzelne ISBNs auf gezielte Anfrage der Nutzerin/des Nutzers ab
(kein Crawling, siehe plan.md) – daher wird das bewusst in Kauf genommen.
"""

import json

from bs4 import BeautifulSoup

from bookscouter.scrapers.base import Scraper, ScrapeResult

BASE_URL = "https://www.thalia.at"
SEARCH_URL = f"{BASE_URL}/suche"


class ThaliaScraper(Scraper):
    shop_name = "Thalia.at"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        search_response = self._get(SEARCH_URL, params={"sq": isbn})
        if not search_response.ok:
            return not_found

        search_soup = BeautifulSoup(search_response.text, "html.parser")
        link = search_soup.select_one('a[href*="artikeldetails"]')
        if link is None:
            return not_found

        detail_url = link["href"]
        if detail_url.startswith("/"):
            detail_url = BASE_URL + detail_url

        detail_response = self._get(detail_url)
        if not detail_response.ok:
            return not_found

        book_data = self._extract_book_json_ld(detail_response.text)
        if book_data is None:
            return not_found

        titel = book_data.get("name")
        preis_raw = book_data.get("offers", {}).get("price")
        if titel is None or preis_raw is None:
            return not_found

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=titel,
            preis=float(preis_raw),
            gefunden=True,
        )

    @staticmethod
    def _extract_book_json_ld(html: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
            except (TypeError, ValueError):
                continue
            if isinstance(data, dict) and data.get("@type") == "Book":
                return data
        return None
