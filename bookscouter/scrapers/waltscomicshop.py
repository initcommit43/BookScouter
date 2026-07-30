"""Scraper für waltscomicshop.com: ISBN rein, Titel + Preis raus.

Anders als Thalia läuft dieser Shop auf Shopify: Produktseiten bieten einen
öffentlichen `<handle>.js`-Endpunkt mit sauberen Preis-/SKU-Daten (die ISBN
steckt im `barcode`-Feld der Variante), daher genügt HTML-Parsing nur für die
Trefferliste, nicht für die Detailseite.

Verwendet wird `.js` und nicht der ebenfalls verfügbare `.json`-Endpunkt:
nur `.js` nennt pro Variante ein `available`-Flag, und ohne das gäbe es für
diesen Shop keine Lagerinformation. Preis ist dort in Cent angegeben.

robots.txt sperrt `/search` zwar für Bots allgemein, dieses Tool fragt aber
ausschließlich einzelne ISBNs auf gezielte Anfrage der Nutzerin/des Nutzers ab
(kein Crawling, siehe plan.md) – daher wird das bewusst in Kauf genommen
(gleiche Begründung wie bei Thalia, siehe thalia.py).
"""

import json
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from bookscouter.scrapers.base import (
    VERFUEGBARKEIT_UNBEKANNT,
    Scraper,
    ScrapeResult,
    verfuegbarkeit_aus_schema_org,
)


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

        # Der Link der Trefferliste hängt Tracking-Parameter an (?_pos=…),
        # der reine Pfad ist die eigentliche Produktseite.
        handle_path = urlparse(link["href"]).path
        detail_response = self._get(f"{self.base_url}{handle_path}.js")
        if not detail_response.ok:
            return not_found

        try:
            product = json.loads(detail_response.text)
        except ValueError:
            return not_found
        if not isinstance(product, dict):
            return not_found

        variants = product.get("variants", [])
        variant = next((v for v in variants if v.get("barcode") == isbn), None)
        if variant is None or variant.get("price") is None:
            return not_found

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=product.get("title"),
            # Shopify gibt den Preis im .js-Endpunkt in Cent an (2249 = 22,49 €).
            preis=float(variant["price"]) / 100,
            gefunden=True,
            verfuegbarkeit=_verfuegbarkeit(variant.get("available")),
            url=f"{self.base_url}{handle_path}",
        )


def _verfuegbarkeit(available: object) -> str:
    """Übersetzt Shopifys `available`-Flag in denselben Anzeigetext wie schema.org.

    Shopify kennt hier nur "bestellbar oder nicht". Der Umweg über die
    schema.org-Namen spart eigene Texte: so heisst es in allen Shops gleich.
    Fehlt das Feld oder ist es kein Bool, bleibt es bei
    `VERFUEGBARKEIT_UNBEKANNT`.
    """
    if not isinstance(available, bool):
        return VERFUEGBARKEIT_UNBEKANNT
    return verfuegbarkeit_aus_schema_org("InStock" if available else "OutOfStock")
