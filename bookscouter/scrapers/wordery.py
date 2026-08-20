"""Scraper für wordery.com: ISBN rein, Titel + Preis raus.

Wordery ist ein britischer Online-Buchhändler mit versandkostenfreier
Lieferung und breitem Manga-/Light-Novel-Sortiment auf Englisch. Wie
Blackwell's ein Shop ohne Buchpreisbindung – die beiden weichen im Preis
regelmässig voneinander ab, während die deutschen Shops für eine deutsche
Ausgabe alle denselben Betrag nennen.

Ein Request: `/book/<ISBN13>` leitet auf die vollständige Produkt-URL
(`/book/<titel>/<autor>/<ISBN13>`) um. Diesen Kurzweg zu nehmen statt der
Suche ist keine Bequemlichkeit, sondern Absicht – siehe robots.txt unten.

Die Produktseite bringt vollständige schema.org-Microdata mit: `isbn`,
`name`, `price`, `priceCurrency` und `availability`. Die ISBN steht dabei
als Elementtext statt in einem Attribut, was `microdata()` mit abdeckt.

Preise stehen in Pfund; die Umrechnung übernimmt `in_euro()` über die
EZB-Referenzkurse, wie bei Orell Füssli. Angezeigt wird zusätzlich der
Originalbetrag, denn der ist der tatsächliche Ladenpreis.

Zur robots.txt: `/search*` und `*/search?term=` sind für alle Bots gesperrt,
`/book/*` dagegen nicht. Die Suche wird deshalb gar nicht erst angefasst –
anders als bei Lehmanns braucht es hier keine Abwägung, weil der erlaubte
Pfad zum selben Ziel führt. Der `Content-Signal`-Vermerk der Datei
(`search=yes, ai-train=no, use=reference`) erlaubt das Nachschlagen
ausdrücklich und untersagt allein das Sammeln von Trainingsdaten.
"""

from bs4 import BeautifulSoup

from bookscouter.isbn import normalize_isbn, to_isbn13
from bookscouter.scrapers.base import (
    Scraper,
    ScrapeResult,
    microdata,
    verfuegbarkeit_aus_schema_org,
)
from bookscouter.waehrung import in_euro


class WorderyScraper(Scraper):
    shop_name = "Wordery"
    base_url = "https://wordery.com"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        isbn13 = to_isbn13(isbn)

        response = self._get(f"{self.base_url}/book/{isbn13}")
        if not response.ok:
            return not_found

        soup = BeautifulSoup(response.text, "html.parser")

        # Absicherung gegen falsch zugeordnete Treffer: bei einer unbekannten
        # ISBN landet der Kurzweg auf einer Fehler- oder Suchseite, auf der
        # das Feld fehlt.
        seiten_isbn = microdata(soup, "isbn")
        if seiten_isbn is None or normalize_isbn(seiten_isbn) != isbn13:
            return not_found

        titel = microdata(soup, "name")
        preis_original = microdata(soup, "price")
        if not titel or preis_original is None:
            return not_found

        try:
            preis_original = float(preis_original)
        except ValueError:
            return not_found

        waehrung = (microdata(soup, "priceCurrency") or "GBP").strip().upper()
        preis = in_euro(preis_original, waehrung)
        if preis is None:
            # Kein Wechselkurs zu bekommen: lieber nichts melden, als einen
            # Pfund-Betrag als Euro-Preis auszugeben.
            return not_found

        fremdwaehrung = waehrung != "EUR"

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=titel,
            preis=preis,
            gefunden=True,
            verfuegbarkeit=verfuegbarkeit_aus_schema_org(
                microdata(soup, "availability")
            ),
            # Die vom Kurzweg erreichte, ausgeschriebene Produkt-URL – die
            # ist als Link haltbarer und für die Nutzerin sprechender.
            url=response.url,
            originalpreis=preis_original if fremdwaehrung else None,
            originalwaehrung=waehrung if fremdwaehrung else None,
        )
