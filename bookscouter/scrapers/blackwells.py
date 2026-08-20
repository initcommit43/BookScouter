"""Scraper für blackwells.co.uk: ISBN rein, Titel + Preis raus.

Blackwell's ist ein britischer Buchhändler mit grossem Manga- und
Light-Novel-Sortiment auf Englisch und weltweitem Versand. Für dieses Tool
vor allem deshalb interessant, weil englische Ausgaben nicht der deutschen
Buchpreisbindung unterliegen: hier entstehen tatsächlich Preisunterschiede,
während die deutschen Shops für eine deutsche Ausgabe alle denselben Betrag
nennen.

Kein Suchrequest nötig – `/bookshop/product/<ISBN13>` ist direkt
adressierbar, eine Abfrage kostet also einen einzigen Request. Kennt der
Shop die ISBN nicht, leitet er auf die Suchseite um und antwortet trotzdem
mit HTTP 200; erkannt wird das daran, dass der Produktblock fehlt.

Drei Eigenheiten, alle live bestätigt:

1. **Der Preis steht zweimal auf der Seite, mit verschiedener Bedeutung.**
   Der Warenkorb-Button trägt `data-product-price="15.88"`, angezeigt wird
   `17,47 €` – der Unterschied ist die Mehrwertsteuer. Genommen wird der
   angezeigte Bruttopreis, denn die übrigen Shops melden ebenfalls brutto.

2. **Preis und Währung hängen vom Standort ab.** Aus dem Euroraum zeichnet
   Blackwell's in Euro aus, sonst in Pfund. Deshalb wird die Währung aus
   `data-currency` gelesen und durch `in_euro()` geschickt, statt eine
   anzunehmen – und deshalb muss der Preis aus dem Anzeigetext beide
   Dezimaltrennzeichen vertragen ("17,47 €" wie "£8.99"), was
   `preis_aus_text()` erledigt.

3. **Die Preisklasse kommt auf der Seite mehrfach vor.** Auch die
   Empfehlungskarussells benutzen `.product-price`; ohne Eingrenzung auf den
   Hauptartikel greift man den Preis eines fremden Buchs ab (im Test mit
   51,08 € statt 17,47 € beobachtet).

Zur robots.txt: gesperrt sind einzelne `.jsp`-Seiten und Unterverzeichnisse
wie `/bookshop/search_results.jsp` oder `/bookshop/orders/`. Der hier
benutzte Pfad `/bookshop/product/` steht nicht darunter und ist für
`User-agent: *` ausdrücklich erlaubt.
"""

from bs4 import BeautifulSoup

from bookscouter.isbn import normalize_isbn, to_isbn13
from bookscouter.scrapers.base import (
    Scraper,
    ScrapeResult,
    preis_aus_text,
    verfuegbarkeit_aus_schema_org,
)
from bookscouter.waehrung import in_euro


class BlackwellsScraper(Scraper):
    shop_name = "Blackwell's"
    base_url = "https://blackwells.co.uk"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        isbn13 = to_isbn13(isbn)
        produkt_url = f"{self.base_url}/bookshop/product/{isbn13}"

        response = self._get(produkt_url)
        if not response.ok:
            return not_found

        soup = BeautifulSoup(response.text, "html.parser")

        # Alles Weitere wird aus diesem Block gelesen und nicht aus dem
        # ganzen Dokument – siehe Punkt 3 im Modul-Docstring.
        hauptartikel = soup.select_one("div.content.product__info")
        if hauptartikel is None:
            return not_found

        # Der Warenkorb-Button des Hauptartikels trägt ISBN und Währung als
        # Attribute. Seinem Preis-Attribut wird bewusst nicht getraut (es
        # führt den Nettopreis), wohl aber der ISBN – sie ist die Absicherung
        # dagegen, dass eine unbekannte ISBN auf der Suchseite landet.
        button = hauptartikel.select_one("button[data-product-isbn]")
        if button is None:
            return not_found
        if normalize_isbn(button.get("data-product-isbn", "")) != isbn13:
            return not_found

        titel = _titel(hauptartikel)

        preis_element = hauptartikel.select_one(".product-price--current")
        preis_original = preis_aus_text(
            preis_element.get_text(strip=True) if preis_element else None
        )
        if not titel or preis_original is None:
            return not_found

        waehrung = (button.get("data-currency") or "EUR").strip().upper()
        preis = in_euro(preis_original, waehrung)
        if preis is None:
            # Kein Wechselkurs zu bekommen: lieber nichts melden, als einen
            # Pfund-Betrag als Euro-Preis auszugeben. Gleiche Abwägung wie
            # bei Orell Füssli, siehe `bookscouter/waehrung.py`.
            return not_found

        # Die Verfügbarkeit steht als englischer Klartext in einem für
        # Screenreader gedachten Element ("In Stock"). Die Schreibweise
        # entspricht bis auf das Leerzeichen den schema.org-Namen, deshalb
        # genügt es, die Zwischenräume zu entfernen, statt ein zweites
        # Vokabular zu pflegen.
        lagertext = hauptartikel.select_one(".product-price .is-hidden")
        fremdwaehrung = waehrung != "EUR"

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=titel,
            preis=preis,
            gefunden=True,
            verfuegbarkeit=verfuegbarkeit_aus_schema_org(
                lagertext.get_text(strip=True).replace(" ", "") if lagertext else None
            ),
            url=produkt_url,
            originalpreis=preis_original if fremdwaehrung else None,
            originalwaehrung=waehrung if fremdwaehrung else None,
        )


def _titel(hauptartikel) -> str | None:
    """Liest den Buchtitel aus der Überschrift des Hauptartikels.

    Blackwell's packt drei Angaben ohne Trennzeichen in dieselbe `h1`: den
    Titel als freien Text, den Untertitel in einem `<small>` und dahinter
    noch einmal die Reihe. Der ganze Text ergäbe "Chainsaw Man, Vol. 1 Dog
    And Chainsaw - Chainsaw Man" – deshalb nur der erste freie Textknoten,
    was denselben Titel liefert, den die übrigen Shops nennen.
    """
    ueberschrift = hauptartikel.select_one('h1[itemprop="name"]')
    if ueberschrift is None:
        return None
    for knoten in ueberschrift.children:
        if isinstance(knoten, str) and knoten.strip():
            return knoten.strip()
    # Kein freier Text: dann lieber die ganze Überschrift als gar nichts.
    return ueberschrift.get_text(" ", strip=True) or None
