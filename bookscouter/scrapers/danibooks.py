"""Scraper für danibooks.de: ISBN rein, Titel + Preis raus.

dani books ist ein kleiner Comic- und Manga-Verlag, der seine Titel selbst
verkauft – interessant, weil er damit Bücher führt, die die grossen Ketten
oft gar nicht erst listen.

Der Shop läuft auf PrestaShop. Eine ISBN-adressierbare Produkt-URL wie bei
Morawa gibt es nicht, also zwei Requests: Trefferliste unter `/suche`, dann
die Produktseite. Angenehm gegenüber altraverse: die Suche versteht die reine
Ziffernfolge, hier ist keine Bindestrich-Schreibweise nötig.

Auf der Produktseite liegt ein sauberer JSON-LD-Block mit `@type: "Product"`
– flach, ohne Thalias kaputte Escapes und ohne Morawas `mainEntity`-Ebene.

Zur robots.txt: sie enthält keinen `User-agent: *`-Abschnitt, sondern
ausschliesslich eine Sperrliste für KI-Crawler (GPTBot, ClaudeBot, CCBot und
ähnliche). Für dieses Tool gilt also keine Einschränkung – und dem Zweck der
Liste läuft es auch nicht zuwider: BookScouter sammelt keine Trainingsdaten
und crawlt keinen Katalog, sondern fragt eine einzelne, von der Nutzerin
eingetippte ISBN auf deren ausdrückliche Anfrage ab (siehe plan.md).
"""

import json

from bs4 import BeautifulSoup

from bookscouter.isbn import normalize_isbn, to_isbn13
from bookscouter.scrapers.base import Scraper, ScrapeResult, verfuegbarkeit_aus_schema_org


class DaniBooksScraper(Scraper):
    shop_name = "dani books"
    base_url = "https://www.danibooks.de"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        isbn13 = to_isbn13(isbn)

        search_response = self._get(
            f"{self.base_url}/suche", params={"controller": "search", "s": isbn13}
        )
        if not search_response.ok:
            return not_found

        search_soup = BeautifulSoup(search_response.text, "html.parser")
        link = search_soup.select_one("h2.product-title a")
        if link is None or not link.get("href"):
            return not_found

        # PrestaShop schreibt in der Trefferliste bereits absolute Links.
        detail_url = link["href"]
        detail_response = self._get(detail_url)
        if not detail_response.ok:
            return not_found

        produkt = self._extract_product_json_ld(detail_response.text)
        if produkt is None:
            return not_found

        # Absicherung gegen falsch zugeordnete Treffer: die Suche ist unscharf
        # und liefert bei einer unbekannten ISBN durchaus irgendein anderes
        # Buch zurück. `gtin13` steht als reine Ziffernfolge da, die
        # Bindestrich-Schreibweise nur in `sku`/`mpn`.
        if normalize_isbn(str(produkt.get("gtin13"))) != isbn13:
            return not_found

        angebot = produkt.get("offers", {})
        if not isinstance(angebot, dict):
            return not_found

        titel = produkt.get("name")
        preis = angebot.get("price")
        if titel is None or preis is None:
            return not_found

        try:
            preis = float(preis)
        except (TypeError, ValueError):
            return not_found

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=titel,
            preis=preis,
            gefunden=True,
            verfuegbarkeit=verfuegbarkeit_aus_schema_org(angebot.get("availability")),
            url=detail_url,
        )

    @staticmethod
    def _extract_product_json_ld(html: str) -> dict | None:
        """Liefert den JSON-LD-Block der Produktseite.

        Die Seite bringt mehrere Blöcke mit (Breadcrumb, Organisation, …),
        gesucht ist der mit `@type: "Product"`.
        """
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
            except (TypeError, ValueError):
                continue
            # Manche Blöcke sind eine Liste mehrerer Objekte.
            for eintrag in data if isinstance(data, list) else [data]:
                if isinstance(eintrag, dict) and str(eintrag.get("@type")).lower() == "product":
                    return eintrag
        return None
