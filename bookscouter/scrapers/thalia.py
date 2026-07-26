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
import re

from bs4 import BeautifulSoup

from bookscouter.isbn import normalize_isbn, to_isbn13
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

        # Absicherung gegen falsch zugeordnete Treffer: übernommen wird der
        # erste artikeldetails-Link der Trefferliste, und Thalias Suche ist
        # unscharf – ohne diese Prüfung könnte still der Preis eines anderen
        # Buchs zurückkommen. Thalia schreibt die ISBN mit Bindestrichen und
        # immer als ISBN-13, auch wenn mit einer ISBN-10 gesucht wurde, daher
        # beide Seiten auf dieselbe Form bringen.
        if normalize_isbn(str(book_data.get("isbn", ""))) != to_isbn13(isbn):
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
                data = json.loads(_repariere_json_escapes(script.string))
            except (TypeError, ValueError):
                continue
            if isinstance(data, dict) and data.get("@type") == "Book":
                return data
        return None


# In JSON sind nur diese Zeichen hinter einem Backslash erlaubt.
_ERLAUBTE_ESCAPES = '"\\/bfnrtu'


def _repariere_json_escapes(text: str) -> str:
    """Entfernt ungültige Escape-Sequenzen aus Thalias JSON-LD.

    Thalia escaped Anführungszeichen im Fliesstext erst zu \\" und lässt
    danach noch das HTML-Escaping drüberlaufen. Übrig bleibt \\&quot; – und
    \\& ist in JSON keine gültige Escape-Sequenz, weshalb json.loads den
    kompletten Block abweist. Beobachtet z.B. bei 9783842006874 ("Gute
    Nacht, Punpun 01"), wo die description \\&quot;Gott\\&quot; enthält.

    Da der Fehler in einem Feld steckt, das dieser Scraper gar nicht liest,
    darf er nicht die ganze Abfrage kosten: ein überflüssiger Backslash wird
    verworfen, aus \\&quot; wird &quot; und daraus beim späteren
    html.unescape() wieder ein normales Anführungszeichen.
    """
    return re.sub(
        r"\\(.)",
        lambda treffer: treffer.group(0)
        if treffer.group(1) in _ERLAUBTE_ESCAPES
        else treffer.group(1),
        text,
        flags=re.DOTALL,
    )


class ThaliaDeScraper(ThaliaScraper):
    def __init__(self) -> None:
        super().__init__(base_url="https://www.thalia.de", shop_name="Thalia.de")


class BuecherDeScraper(ThaliaScraper):
    """buecher.de – andere Marke, gleiche Plattform (siehe Modul-Docstring)."""

    def __init__(self) -> None:
        super().__init__(base_url="https://www.buecher.de", shop_name="Buecher.de")
