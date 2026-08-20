"""Scraper für lehmanns.de: ISBN rein, Titel + Preis raus.

Lehmanns Media ist ein deutscher Fachbuchhändler mit breitem Sortiment, der
neben Fachliteratur auch Manga und Light Novels führt – und, anders als die
Verlagsshops, auch nicht preisgebundene Importtitel.

Der einfachste Shop des ganzen Projekts, aus zwei Gründen:

1. **Ein einziger Request.** `/search/quick?q=<ISBN>` beantwortet eine ISBN
   nicht mit einer Trefferliste, sondern leitet direkt auf die Produktseite
   um. Deren Adresse steht in `HttpResponse.url` (siehe `bookscouter/http.py`).
   Sie selbst zusammenzubauen ginge nicht: sie enthält eine interne Artikel-
   nummer (`/shop/literatur/43093019-9783551741035-attack-on-titan-deluxe-1`),
   die aus der ISBN nicht ableitbar ist.

2. **Vollständige schema.org-Microdata.** Preis, Währung, Verfügbarkeit und
   ISBN stehen alle als `itemprop` im Markup, ohne die kaputten Escapes von
   Thalia oder die Verschachtelung von Morawa.

Zur robots.txt: sie sperrt `/search/` für alle Bots, Produktseiten unter
`/shop/` dagegen nicht. Da die Produkt-URL wegen der internen Artikelnummer
nur über die Suche zu finden ist, führt kein erlaubter Weg zum Ziel. Genutzt
wird sie trotzdem – nach derselben Abwägung wie bei Thalia: BookScouter
crawlt keinen Katalog, sondern fragt genau eine von der Nutzerin eingetippte
ISBN auf deren ausdrückliche Anfrage ab (siehe plan.md).
"""

from bs4 import BeautifulSoup

from bookscouter.isbn import normalize_isbn, to_isbn13
from bookscouter.scrapers.base import (
    Scraper,
    ScrapeResult,
    microdata,
    verfuegbarkeit_aus_schema_org,
)


class LehmannsScraper(Scraper):
    shop_name = "Lehmanns"
    base_url = "https://www.lehmanns.de"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        isbn13 = to_isbn13(isbn)

        response = self._get(f"{self.base_url}/search/quick", params={"q": isbn13})
        if not response.ok:
            return not_found

        soup = BeautifulSoup(response.text, "html.parser")

        # Absicherung gegen falsch zugeordnete Treffer: bei einer unbekannten
        # ISBN bleibt die Suche auf einer Trefferliste stehen, statt
        # umzuleiten – dann fehlt das Feld und es wird nichts gemeldet.
        # Notiert ist die ISBN in der amtlichen Schreibweise mit
        # Bindestrichen ("978-3-551-74103-5"), daher `normalize_isbn`.
        seiten_isbn = microdata(soup, "isbn")
        if seiten_isbn is None or normalize_isbn(seiten_isbn) != isbn13:
            return not_found

        # Der Titel kommt aus der Überschrift, nicht über `microdata`: dort
        # steht er zwar als `itemprop="name"`, aber als Elementtext – und ein
        # zweites `itemprop="name"` weiter unten trägt den Verlagsnamen.
        # `select_one` liefert den ersten Treffer in Dokumentreihenfolge, das
        # wäre hier zwar der richtige, doch der Selektor sagt dann nicht mehr,
        # welches der beiden Felder gemeint ist.
        ueberschrift = soup.select_one('h1[itemprop="name"]')
        titel = ueberschrift.get_text(strip=True) if ueberschrift else None
        preis = microdata(soup, "price")
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
                microdata(soup, "availability")
            ),
            url=response.url,
        )
