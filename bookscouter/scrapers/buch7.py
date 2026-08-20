"""Scraper für buch7.de: ISBN rein, Titel + Preis raus.

buch7 ist ein deutscher Versandbuchhändler, der den grössten Teil seines
Gewinns spendet. Fürs Sortiment heisst das nichts Besonderes – es ist der
volle Barsortiments-Katalog inklusive Manga, Light Novels und englischer
Importe.

Ein Request: `/suche?search=<ISBN>` leitet bei einem Treffer direkt auf die
Produktseite `/produkt/<slug>/<id>?ean=<ISBN>` um. Bleibt die Antwort auf
der Suchseite stehen, kennt der Shop die ISBN nicht.

Anders als bei den übrigen Shops gibt es hier weder JSON-LD noch Microdata –
Titel, Preis und Verfügbarkeit müssen aus dem gewöhnlichen Markup gelesen
werden.

Zur robots.txt: gesperrt sind Warenkorb-, Konto- und Bestellpfade sowie
`/products/*/blickinsbuch`; `/suche` und `/produkt/` stehen nicht darunter.
Dieser Shop ist also ohne Einschränkung abfragbar.
"""

from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from bookscouter.isbn import normalize_isbn, to_isbn13
from bookscouter.scrapers.base import (
    VERFUEGBARKEIT_UNBEKANNT,
    Scraper,
    ScrapeResult,
    preis_aus_text,
)

# buch7 nennt keine Lagerzustände, sondern Lieferzeiten ("gewöhnlich ca. 3-6
# Wochen"). Die werden hier auf dasselbe Vokabular abgebildet, das die
# übrigen Shops über schema.org liefern – sonst stünde in der einen Spalte
# einmal ein Zustand und einmal eine Zeitangabe.
#
# Geprüft an mehreren Titeln: "auf Lager (1-2 Werktage)", "Sofort lieferbar
# (Download)", "gewöhnlich ca. 1-2 Monate", "gewöhnlich ca. 3-6 Wochen",
# "Artikel neu aufgenommen, noch nicht am Lager". Eine Lieferzeit von Wochen
# ist weder "auf Lager" noch "nicht lieferbar", sondern besorgbar – dafür
# steht "Nachbestellt".
_LIEFERZEIT_VOKABULAR = (
    ("auf lager", "Auf Lager"),
    ("sofort lieferbar", "Auf Lager"),
    ("vorbestell", "Vorbestellbar"),
    ("noch nicht erschienen", "Vorbestellbar"),
    ("nicht lieferbar", "Nicht auf Lager"),
    ("vergriffen", "Nicht auf Lager"),
    ("gewöhnlich", "Nachbestellt"),
    ("noch nicht am lager", "Nachbestellt"),
)


class Buch7Scraper(Scraper):
    shop_name = "buch7"
    base_url = "https://www.buch7.de"

    def scrape(self, isbn: str) -> ScrapeResult:
        not_found = ScrapeResult(
            shop=self.shop_name, isbn=isbn, titel=None, preis=None, gefunden=False
        )

        isbn13 = to_isbn13(isbn)

        response = self._get(f"{self.base_url}/suche", params={"search": isbn13})
        if not response.ok:
            return not_found

        # Der Abgleich läuft über die erreichte Adresse, nicht über den
        # Seiteninhalt: ohne Treffer bleibt die Antwort auf der Suchseite,
        # und deren Trefferliste bringt durchaus Markup anderer Titel mit
        # (bei einer Fach-ISBN live als E-Book-Zeile beobachtet). Erst der
        # `ean`-Parameter der Produkt-URL sagt sicher, welches Buch die Seite
        # zeigt.
        if _ean_aus_url(response.url) != isbn13:
            return not_found

        soup = BeautifulSoup(response.text, "html.parser")

        ueberschrift = soup.select_one("h1")
        titel = ueberschrift.get_text(strip=True) if ueberschrift else None

        # Der Preis steht nur zweierlei auf der Seite: als Beschriftung des
        # Warenkorb-Buttons und in diesem Tracking-Attribut. Das Attribut
        # führt ihn unformatiert ("25.00") und ohne umgebendes Markup,
        # deshalb hier – der Button-Text wäre erst aus Bild-Alternativtext
        # und Zahl zu trennen.
        produktseite = soup.select_one("#produktseite[data-matomo-price]")
        preis = preis_aus_text(
            produktseite.get("data-matomo-price") if produktseite else None
        )
        if not titel or preis is None:
            return not_found

        return ScrapeResult(
            shop=self.shop_name,
            isbn=isbn,
            titel=titel,
            preis=preis,
            gefunden=True,
            verfuegbarkeit=_verfuegbarkeit(soup),
            url=response.url,
        )


def _ean_aus_url(url: str) -> str | None:
    """Liefert die ISBN aus dem `ean`-Parameter der Produkt-URL."""
    ean = parse_qs(urlparse(url).query).get("ean")
    return normalize_isbn(ean[0]) if ean else None


def _verfuegbarkeit(soup: BeautifulSoup) -> str:
    """Übersetzt buch7s Lieferzeitangabe in den Anzeigetext der übrigen Shops.

    Bewusst auf den sichtbaren Text und nicht auf den Klassennamen gestützt
    (`verfuegbarkeit-3-6-wochen`): den Namen bildet buch7 aus der jeweiligen
    Zeitspanne, es gäbe also beliebig viele davon.
    """
    element = soup.select_one("#hauptprodukt-verfuegbarkeit .verfuegbarkeit")
    if element is None:
        return VERFUEGBARKEIT_UNBEKANNT

    text = element.get_text(" ", strip=True).lower()
    for muster, anzeige in _LIEFERZEIT_VOKABULAR:
        if muster in text:
            return anzeige
    return VERFUEGBARKEIT_UNBEKANNT
