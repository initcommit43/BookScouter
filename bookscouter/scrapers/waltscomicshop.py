"""Scraper für waltscomicshop.com: ISBN rein, Titel + Preis raus.

Anders als Thalia läuft dieser Shop auf Shopify: Produktseiten bieten einen
öffentlichen `<handle>.json`-Endpunkt mit sauberen Preis-/SKU-Daten (die ISBN
steckt im `barcode`-Feld der Variante), daher genügt HTML-Parsing nur für die
Trefferliste, nicht für die Detailseite.

robots.txt sperrt `/search` zwar für Bots allgemein, dieses Tool fragt aber
ausschließlich einzelne ISBNs auf gezielte Anfrage der Nutzerin/des Nutzers ab
(kein Crawling, siehe plan.md) – daher wird das bewusst in Kauf genommen
(gleiche Begründung wie bei Thalia, siehe thalia.py).
"""

import json
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from bookscouter.scrapers.base import Scraper, ScrapeResult


class WaltsComicShopScraper(Scraper):
    shop_name = "Walt's Comic Shop"
    base_url = "https://www.waltscomicshop.com"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        search_response = self._get(f"{self.base_url}/search", params={"q": isbn})
        if not search_response.ok:
            return not_found

        search_soup = BeautifulSoup(search_response.text, "html.parser")
        link = search_soup.select_one("a.product-item__title")
        if link is None:
            return not_found

        handle_path = urlparse(link["href"]).path
        detail_response = self._get(f"{self.base_url}{handle_path}.json")
        if not detail_response.ok:
            return not_found

        try:
            product = json.loads(detail_response.text)["product"]
        except (KeyError, ValueError):
            return not_found

        variants = product.get("variants", [])
        variant = next((v for v in variants if v.get("barcode") == isbn), None)
        if variant is None or variant.get("price") is None:
            return not_found

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=product.get("title"),
            preis=float(variant["price"]),
            gefunden=True,
        )
