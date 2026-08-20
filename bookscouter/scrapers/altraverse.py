"""Scraper für altraverse.de: ISBN rein, Titel + Preis raus.

altraverse ist ein deutscher Manga-Verlag mit eigenem Shop – wie dani books
also eine Quelle für Titel, die im allgemeinen Buchhandel dünn vertreten sind.

Zwei Besonderheiten gegenüber den übrigen Shops:

1. **Die Suche findet eine ISBN nur mit Bindestrichen.** `978-3-96358-152-6`
   liefert einen Treffer, die reine Ziffernfolge `9783963581526` nicht – und
   willkürlich gesetzte Bindestriche ebenso wenig, es muss die amtliche
   Schreibweise sein. Dafür gibt es `hyphenate_isbn13()` in
   `bookscouter/isbn.py`. Sie deckt nur die deutschsprachige Gruppe 978-3 ab,
   was hier genügt: altraverse verlegt ausschliesslich deutsche Ausgaben.

2. **Die Produktdaten stehen als Microdata im Markup, nicht als JSON-LD.**
   Also `itemprop`-Attribute statt eines JSON-Blocks.

Der Shop läuft auf Shopware 5. Die robots.txt sperrt `/widgets/`, `/listing/`
und Konto-/Checkout-Pfade – der hier benutzte Pfad `/search` steht nicht
darunter, ist für `User-agent: *` also ausdrücklich erlaubt.
"""

from bs4 import BeautifulSoup

from bookscouter.isbn import hyphenate_isbn13, normalize_isbn, to_isbn13
from bookscouter.scrapers.base import (
    Scraper,
    ScrapeResult,
    microdata,
    verfuegbarkeit_aus_schema_org,
)


class AltraverseScraper(Scraper):
    shop_name = "altraverse"
    base_url = "https://altraverse.de"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        # Ohne die amtliche Bindestrich-Schreibweise findet die Suche nichts,
        # und ausserhalb der Gruppe 978-3 lässt sie sich nicht bilden. Dann
        # gar nicht erst anfragen: ein englischer Titel steht bei einem
        # deutschen Manga-Verlag ohnehin nicht im Katalog, und der gesparte
        # Request hält die Sammelabfrage kurz. (Gleiche Überlegung wie bei
        # Amazon, wo eine fehlende ISBN-10 den Request erspart.)
        mit_bindestrichen = hyphenate_isbn13(isbn)
        if mit_bindestrichen is None:
            return not_found

        search_response = self._get(
            f"{self.base_url}/search", params={"sSearch": mit_bindestrichen}
        )
        if not search_response.ok:
            return not_found

        search_soup = BeautifulSoup(search_response.text, "html.parser")
        # Bewusst genau dieser eine Selektor und keine Alternativenliste:
        # `select_one` liefert den ersten Treffer in Dokumentreihenfolge, und
        # ein loserer Selektor greift zuerst die Navigationslinks ab, die vor
        # der Trefferliste stehen.
        link = search_soup.select_one("a.product--title")
        if link is None or not link.get("href"):
            return not_found

        detail_url = link["href"]
        if detail_url.startswith("/"):
            detail_url = self.base_url + detail_url

        detail_response = self._get(detail_url)
        if not detail_response.ok:
            return not_found

        detail_soup = BeautifulSoup(detail_response.text, "html.parser")

        # Absicherung gegen falsch zugeordnete Treffer: die Suche ist unscharf
        # und liefert notfalls einen anderen Band derselben Reihe.
        seiten_isbn = microdata(detail_soup, "productISBN")
        if seiten_isbn is None or normalize_isbn(seiten_isbn) != to_isbn13(isbn):
            return not_found

        # Der Titel kommt aus der Überschrift, nicht aus `itemprop="name"`:
        # letzteres trägt auf dieser Seite den Hersteller ("altraverse").
        ueberschrift = detail_soup.select_one("h1")
        titel = ueberschrift.get_text(strip=True) if ueberschrift else None
        preis = microdata(detail_soup, "price")
        if not titel or preis is None:
            return not_found

        try:
            preis = float(preis)
        except ValueError:
            return not_found

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=titel,
            preis=preis,
            gefunden=True,
            verfuegbarkeit=verfuegbarkeit_aus_schema_org(
                microdata(detail_soup, "availability")
            ),
            url=detail_url,
        )
