"""Gemeinsames Interface für alle Shop-Scraper: ISBN rein, Titel+Preis raus."""

import re
import time
from dataclasses import dataclass

from bs4 import BeautifulSoup

from bookscouter.config import REQUEST_DELAY_SECONDS
from bookscouter.http import HttpResponse, hole

# Rückfallwert, wenn ein Shop keine oder eine unbekannte Verfügbarkeit meldet.
# Bewusst nicht "Nicht auf Lager": ein fehlendes Feld heisst nicht, dass der
# Titel vergriffen ist, und eine falsche Aussage wäre schlechter als keine.
VERFUEGBARKEIT_UNBEKANNT = "Unbekannt"

# schema.org/ItemAvailability – Thalia-Plattform und Morawa liefern diese
# Werte als URL im JSON-LD ("https://schema.org/InStock").
_SCHEMA_ORG_VERFUEGBARKEIT = {
    "instock": "Auf Lager",
    "instoreonly": "Nur im Laden",
    "onlineonly": "Nur online",
    "limitedavailability": "Nur begrenzt",
    "preorder": "Vorbestellbar",
    "presale": "Vorbestellbar",
    "backorder": "Nachbestellt",
    "outofstock": "Nicht auf Lager",
    "soldout": "Ausverkauft",
    "discontinued": "Nicht mehr lieferbar",
}


def verfuegbarkeit_aus_schema_org(wert: object) -> str:
    """Übersetzt einen schema.org-Verfügbarkeitswert in einen Anzeigetext.

    Nimmt sowohl die URL-Schreibweise ("https://schema.org/InStock") als auch
    den blossen Namen ("InStock"). Alles, was fehlt, kein String ist oder
    nicht im Katalog steht, wird zu `VERFUEGBARKEIT_UNBEKANNT` – die Funktion
    wirft nie, damit ein unerwarteter Wert nie eine sonst gelungene Abfrage
    kostet.
    """
    if not isinstance(wert, str):
        return VERFUEGBARKEIT_UNBEKANNT
    name = wert.strip().rstrip("/").rsplit("/", 1)[-1].lower()
    return _SCHEMA_ORG_VERFUEGBARKEIT.get(name, VERFUEGBARKEIT_UNBEKANNT)


def microdata(soup: BeautifulSoup, name: str, wurzel=None) -> str | None:
    """Liest ein `itemprop`-Feld aus dem Markup.

    Shops verteilen den Wert je nach Feld auf zwei verschiedene Attribute:
    Preis und ISBN stehen meist in `content`, die Verfügbarkeit dagegen als
    `<link itemprop="availability" href="http://schema.org/InStock" />` im
    `href`. Deshalb beide Attribute prüfen – sonst käme die Lagerinformation
    still als "Unbekannt" durch, obwohl die Seite sie nennt.

    `wurzel` grenzt die Suche auf einen Teilbaum ein. Nötig auf Seiten, die
    dasselbe `itemprop` mehrfach führen – etwa in Empfehlungskarussells, wo
    sonst der Wert eines fremden Buchs zurückkäme.

    Steht der Wert als Elementtext statt als Attribut (Wordery schreibt die
    ISBN so), kommt er ebenfalls zurück; die Attribute haben Vorrang, weil
    sie die unformatierte Fassung tragen.
    """
    element = (wurzel or soup).select_one(f'[itemprop="{name}"]')
    if element is None:
        return None
    wert = element.get("content") or element.get("href")
    if wert:
        return wert
    text = element.get_text(strip=True)
    return text or None


# Alles, was in einem angezeigten Preis kein Zifferntrenner ist: Währungs-
# symbole und -kürzel, geschützte Leerzeichen, Beschriftungen wie "Price:".
_KEIN_PREISZEICHEN = re.compile(r"[^0-9.,]")


def preis_aus_text(text: str | None) -> float | None:
    """Liest einen Preis aus einem Anzeigetext ("17,47 €", "£8.99").

    Gebraucht für Shops, die den Preis nirgends maschinenlesbar hinterlegen
    (buch7) oder deren maschinenlesbarer Wert etwas anderes meint als der
    angezeigte (Blackwell's führt im Warenkorb-Attribut den Netto-, in der
    Anzeige den Bruttopreis).

    Das Dezimaltrennzeichen ist nicht festgelegt: Blackwell's zeichnet je
    nach Region deutsch ("17,47 €") oder englisch ("£8.99") aus. Deshalb
    gilt das *letzte* Komma oder der letzte Punkt als Dezimaltrenner und
    alles davor als Tausendertrennung – das trifft beide Schreibweisen und
    auch "1.234,50".

    Wirft nie; was sich nicht als Preis lesen lässt, ergibt `None`.
    """
    if not text:
        return None

    ziffern = _KEIN_PREISZEICHEN.sub("", text)
    trenner = max(ziffern.rfind(","), ziffern.rfind("."))
    if trenner == -1:
        ganzzahl, nachkomma = ziffern, ""
    else:
        ganzzahl, nachkomma = ziffern[:trenner], ziffern[trenner + 1 :]

    # Ein "Trenner", hinter dem keine ein bis zwei Ziffern stehen, war keiner
    # – etwa die Tausendertrennung in "1.234" ohne Nachkommastellen.
    if not nachkomma.isdigit() or len(nachkomma) > 2:
        ganzzahl, nachkomma = ziffern, ""

    ganzzahl = ganzzahl.replace(",", "").replace(".", "")
    if not ganzzahl.isdigit():
        return None
    return float(f"{ganzzahl}.{nachkomma or '0'}")


@dataclass
class ScrapeResult:
    shop: str
    isbn: str
    titel: str | None
    preis: float | None
    gefunden: bool
    # Anzeigetext der Lagerverfügbarkeit; bei nicht gefundenen Titeln
    # uninteressant, deshalb mit Rückfallwert vorbelegt.
    verfuegbarkeit: str = VERFUEGBARKEIT_UNBEKANNT
    # Produktseite beim Shop, in der Oberfläche als Link hinterlegt.
    url: str | None = None
    # Nur gesetzt, wenn der Shop in einer anderen Währung als Euro auszeichnet
    # (bisher allein Orell Füssli in CHF). `preis` ist dann der umgerechnete
    # Euro-Betrag, damit Vergleich, Chart und Historie eine einzige Einheit
    # behalten; hier steht zusätzlich der Originalbetrag, damit die Anzeige
    # offenlegen kann, dass ein Wechselkurs im Spiel war, statt eine
    # umgerechnete Zahl als Ladenpreis auszugeben.
    originalpreis: float | None = None
    originalwaehrung: str | None = None


class Scraper:
    """Basisklasse, die jeder Shop-Scraper implementiert."""

    shop_name: str

    def __init__(self) -> None:
        self._last_request_time: float | None = None

    def _get(self, url: str, params: dict | None = None) -> HttpResponse:
        """GET-Request mit Mindestabstand zwischen Requests (Rate-Limiting).

        Der Abstand wird je Scraper-Instanz gezählt, deshalb legen CLI und
        Oberfläche die Scraper einmal an und verwenden sie für alle Bücher
        einer Sammelabfrage weiter.
        """
        if self._last_request_time is not None:
            wait = REQUEST_DELAY_SECONDS - (time.monotonic() - self._last_request_time)
            if wait > 0:
                time.sleep(wait)

        try:
            return hole(url, params)
        finally:
            # Auch ein Fehlschlag ging über die Leitung und zählt für den
            # Mindestabstand – sonst würde ausgerechnet eine Fehlerserie
            # ungebremst weiterlaufen.
            self._last_request_time = time.monotonic()

    def scrape(self, isbn: str) -> ScrapeResult:
        raise NotImplementedError
