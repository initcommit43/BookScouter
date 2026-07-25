"""Scraper für die Thalia-Plattform: ISBN rein, Titel + Preis raus.

Deckt thalia.at, thalia.de und buecher.de ab. Alle drei laufen auf derselben
Plattform (identische Struktur bis hin zu denselben Artikel-IDs, Bilder von
images.thalia.media – teils aber unterschiedliche Preise), daher ein
parametrisierter Scraper statt drei Kopien.

Thalia bietet keine ISBN-basierte Produkt-URL an. Der einzige Weg, eine ISBN
einer Produktseite zuzuordnen, ist die Trefferliste unter /suche?sq=<isbn>.
robots.txt sperrt /suche zwar für Bots allgemein, dieses Tool fragt aber
ausschließlich einzelne ISBNs auf gezielte Anfrage der Nutzerin/des Nutzers ab
(kein Crawling, siehe plan.md) – daher wird das bewusst in Kauf genommen.
"""

import html
import json

from bs4 import BeautifulSoup

from bookscouter.scrapers.base import Scraper, ScrapeResult


class ThaliaScraper(Scraper):
    def __init__(self, base_url: str = "https://www.thalia.at", shop_name: str = "Thalia.at") -> None:
        super().__init__()
        self.shop_name = shop_name
        self.base_url = base_url

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        search_response = self._get(f"{self.base_url}/suche", params={"sq": isbn})
        if not search_response.ok:
            return not_found

        search_soup = BeautifulSoup(search_response.text, "html.parser")
        link = search_soup.select_one('a[href*="artikeldetails"]')
        if link is None:
            return not_found

        detail_url = link["href"]
        if detail_url.startswith("/"):
            detail_url = self.base_url + detail_url

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
            # Die Titel im JSON-LD enthalten HTML-Entities ("Die Stra&szlig;e"),
            # daher vor dem Speichern/Anzeigen dekodieren.
            titel=html.unescape(titel),
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


class ThaliaDeScraper(ThaliaScraper):
    def __init__(self) -> None:
        super().__init__(base_url="https://www.thalia.de", shop_name="Thalia.de")


class BuecherDeScraper(ThaliaScraper):
    """buecher.de – andere Marke, gleiche Plattform (siehe Modul-Docstring)."""

    def __init__(self) -> None:
        super().__init__(base_url="https://www.buecher.de", shop_name="Buecher.de")
