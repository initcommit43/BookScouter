"""Scraper für amazon.de: ISBN rein, Titel + Preis raus.

**Live gegen die echte Seite geprüft** (9783546100335 → "Die Straße",
9783831041657 → "Self-Care Collection. Ayurveda", beide korrekt mit Titel,
Preis und "Auf Lager"; eine erfundene ISBN liefert sauber HTTP 404 → nicht
gefunden). Adressierung: Amazon nutzt für Bücher traditionell die ISBN-10
als ASIN (`/dp/<ISBN-10>`), ein einziger Request wie bei Morawa. Für
ISBN-13 mit 979-Präfix gibt es keine ISBN-10-Entsprechung – solche ISBNs
werden ohne Request als "nicht gefunden" behandelt, weil keine ASIN aus
ihnen ableitbar ist. Kein JSON-LD wie bei Thalia/Morawa: Amazons
Produktseiten liefern Titel, Preis und Verfügbarkeit nur in normalem
HTML-Markup.

**Bug gefunden und in `scrapers/base.py` behoben:** amazon.de lieferte bei
einem von sechs Live-Requests die Antwort unangefragt gzip-komprimiert. Die
gemeinsame `_get()` deserialisiert mit `text=True`/`encoding="utf-8"` und
hatte kein `--compressed` gesetzt, wodurch die rohen gzip-Bytes lautlos zu
Ersatzzeichen wurden – eine echte "auf Lager"-Antwort sah dadurch wie "nicht
gefunden" aus. `--compressed` behebt das für alle Shops, nicht nur Amazon,
und ändert nichts für Shops, die ohnehin unkomprimiert antworten.

**Weiterhin unverändert, weil kein Code-Problem, sondern eine bewusste
Abwägung des Users:** Amazons Nutzungsbedingungen verbieten automatisiertes
Abfragen explizit (nicht nur eine robots.txt-Empfehlung wie bei
Thalia/Walt's) – ein grundsätzlich anderes rechtliches Risiko als bei den
übrigen Shops. Vor dauerhaftem Einsatz abwägen.
"""

import re

from bs4 import BeautifulSoup

from bookscouter.isbn import to_isbn10
from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT, Scraper, ScrapeResult

# Amazon nennt Verfügbarkeit als Fliesstext statt als schema.org-Wert, daher
# eine eigene Übersetzungstabelle statt `verfuegbarkeit_aus_schema_org()`.
# Teilstring-Suche, längste/spezifischste Treffer zuerst geprüft.
_VERFUEGBARKEIT_TEXTE = [
    ("derzeit nicht verfügbar", "Nicht auf Lager"),
    ("zurzeit nicht auf lager", "Nicht auf Lager"),
    ("nicht auf lager", "Nicht auf Lager"),
    ("nur noch", "Nur begrenzt"),
    ("lieferbar ab", "Vorbestellbar"),
    ("vorbestellen", "Vorbestellbar"),
    ("auf lager", "Auf Lager"),
]

_PREIS_SELEKTOREN = (
    "#corePrice_feature_div span.a-offscreen",
    "#tp_price_block_total_price_ww span.a-offscreen",
    "#price_inside_buybox",
    "span.a-price span.a-offscreen",
)


class AmazonScraper(Scraper):
    shop_name = "Amazon.de"
    base_url = "https://www.amazon.de"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        isbn10 = to_isbn10(isbn)
        if isbn10 is None:
            return not_found

        produkt_url = f"{self.base_url}/dp/{isbn10}"
        response = self._get(produkt_url)
        if not response.ok:
            return not_found

        soup = BeautifulSoup(response.text, "html.parser")

        titel_element = soup.select_one("#productTitle")
        if titel_element is None:
            return not_found
        titel = titel_element.get_text(strip=True)

        preis = self._extrahiere_preis(soup)
        if preis is None:
            return not_found

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=titel,
            preis=preis,
            gefunden=True,
            verfuegbarkeit=self._extrahiere_verfuegbarkeit(soup),
            url=produkt_url,
        )

    @staticmethod
    def _extrahiere_preis(soup: BeautifulSoup) -> float | None:
        for selektor in _PREIS_SELEKTOREN:
            element = soup.select_one(selektor)
            if element is None:
                continue
            preis = _parse_euro_betrag(element.get_text(strip=True))
            if preis is not None:
                return preis
        return None

    @staticmethod
    def _extrahiere_verfuegbarkeit(soup: BeautifulSoup) -> str:
        element = soup.select_one("#availability span")
        if element is None:
            return VERFUEGBARKEIT_UNBEKANNT
        text = element.get_text(strip=True).lower()
        for teiltext, anzeige in _VERFUEGBARKEIT_TEXTE:
            if teiltext in text:
                return anzeige
        return VERFUEGBARKEIT_UNBEKANNT


def _parse_euro_betrag(text: str) -> float | None:
    """Wandelt "12,99 €" o.ä. in 12.99 um. Liefert None statt zu werfen."""
    treffer = re.search(r"(\d+(?:\.\d{3})*),(\d{2})", text)
    if treffer is None:
        return None
    vorkomma = treffer.group(1).replace(".", "")
    return float(f"{vorkomma}.{treffer.group(2)}")
