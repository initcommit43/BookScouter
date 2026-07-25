"""Scraper für morawa.at: ISBN rein, Titel + Preis raus.

Angenehmster der bisherigen Shops: Morawa hat unter
`/detail/ISBN-<isbn>` eine direkt per ISBN adressierbare Produktseite (der
Autor/Titel-Teil der URL aus der Sitemap ist optional). Deshalb genügt ein
einziger Request statt Suche + Detailseite, und – anders als bei Thalia und
Walt's Comic Shop – ist dieser Pfad in der robots.txt ausdrücklich erlaubt:
gesperrt sind dort nur die Suche (`/suchergebnis?bpmquery*`) sowie `.json`-
und `.xml`-Pfade, die hier alle nicht gebraucht werden.

Nicht geführte ISBNs liefern sauber HTTP 404. Nur ISBN-13 funktioniert,
ISBN-10 wird nicht weitergeleitet.

Die Produktdaten stecken in einem JSON-LD-Block, dort aber – anders als bei
Thalia – verschachtelt unter `mainEntity` mit kleingeschriebenem
`@type: ["book", "product"]`.
"""

import json

from bs4 import BeautifulSoup

from bookscouter.scrapers.base import Scraper, ScrapeResult


class MorawaScraper(Scraper):
    shop_name = "Morawa.at"
    base_url = "https://www.morawa.at"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        response = self._get(f"{self.base_url}/detail/ISBN-{isbn}")
        if not response.ok:
            return not_found

        book_data = self._extract_book_json_ld(response.text)
        if book_data is None:
            return not_found

        # Absicherung gegen "Soft 404" bzw. falsch zugeordnete Seiten: die
        # Seite muss wirklich die angefragte ISBN führen (im JSON-LD steht
        # sie als Zahl, daher str()).
        if str(book_data.get("isbn")) != isbn:
            return not_found

        titel = book_data.get("name")
        preis = book_data.get("offers", {}).get("price")
        if titel is None or preis is None:
            return not_found

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=titel,
            preis=float(preis),
            gefunden=True,
        )

    @staticmethod
    def _extract_book_json_ld(html: str) -> dict | None:
        """Liefert die `mainEntity` des JSON-LD-Blocks, der ein Buch beschreibt."""
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
            except (TypeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue

            main_entity = data.get("mainEntity")
            if not isinstance(main_entity, dict):
                continue

            # @type ist hier eine Liste ("book"/"product"), kann laut
            # schema.org aber auch ein einzelner String sein.
            entity_type = main_entity.get("@type", [])
            if isinstance(entity_type, str):
                entity_type = [entity_type]
            if any(t.lower() == "book" for t in entity_type):
                return main_entity
        return None
