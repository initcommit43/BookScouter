"""Tests für den Lehmanns-Scraper.

Das Markup ist aus der echten Produktseite gekürzt. Wichtig daran: die ISBN
steht mit Bindestrichen, und `itemprop="name"` kommt zweimal vor – einmal
als Buchtitel in der Überschrift, einmal als Verlagsname weiter unten.
"""

from dataclasses import dataclass

from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT
from bookscouter.scrapers.lehmanns import LehmannsScraper

PRODUKT_URL = (
    "https://www.lehmanns.de/shop/literatur/43093019-9783551741035-attack-on-titan-deluxe-1"
)

DETAIL_HTML = """
<html><body>
<h1 itemprop="name">Attack on Titan Deluxe 1</h1>
<span itemprop="publisher" itemscope itemtype="https://schema.org/Organization">
  <span itemprop="name">Carlsen</span>
</span>
<span class="isbn"><span itemprop="isbn">978-3-551-74103-5</span> (ISBN)</span>
<div class="price" itemprop="offers" itemscope itemtype="https://schema.org/Offer">
  <link itemprop="availability" href="https://schema.org/InStock"/>
  <meta itemprop="priceCurrency" content="EUR" />
  <meta itemprop="price" content="25.00"/>
  <strong>25,<sup>00</sup></strong> <span class="currency">&euro;</span>
</div>
</body></html>
"""

DETAIL_HTML_VORBESTELLBAR = DETAIL_HTML.replace(
    "https://schema.org/InStock", "https://schema.org/PreOrder"
)

DETAIL_HTML_OHNE_VERFUEGBARKEIT = DETAIL_HTML.replace(
    '<link itemprop="availability" href="https://schema.org/InStock"/>', ""
)

DETAIL_HTML_OHNE_PREIS = DETAIL_HTML.replace(
    '<meta itemprop="price" content="25.00"/>', ""
)

DETAIL_HTML_ANDERE_ISBN = DETAIL_HTML.replace("978-3-551-74103-5", "978-3-551-74104-2")

# Ohne Treffer bleibt die Suche auf der Trefferliste stehen – dort gibt es
# kein `itemprop="isbn"`, das der gesuchten ISBN entspräche.
TREFFERLISTE_HTML = "<html><body><h1>Suchergebnis</h1><p>Keine Treffer</p></body></html>"


@dataclass
class FakeResponse:
    text: str
    ok: bool = True
    url: str = PRODUKT_URL


def _antwortet(monkeypatch, antwort):
    monkeypatch.setattr(LehmannsScraper, "_get", lambda self, url, **kwargs: antwort)


def test_scrape_found(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    result = LehmannsScraper().scrape("9783551741035")

    assert result.gefunden is True
    assert result.titel == "Attack on Titan Deluxe 1"
    assert result.preis == 25.00
    assert result.shop == "Lehmanns"
    assert result.isbn == "9783551741035"
    assert result.verfuegbarkeit == "Auf Lager"
    assert result.url == PRODUKT_URL


def test_titel_ist_nicht_der_verlagsname(monkeypatch):
    """Auf der Seite trägt ein zweites `itemprop="name"` den Verlag."""
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    assert LehmannsScraper().scrape("9783551741035").titel != "Carlsen"


def test_ein_einziger_request(monkeypatch):
    """Die Suche leitet direkt auf die Produktseite um – ein zweiter Abruf wäre unnötig."""
    aufrufe = []

    def fake_get(self, url, **kwargs):
        aufrufe.append(url)
        return FakeResponse(DETAIL_HTML)

    monkeypatch.setattr(LehmannsScraper, "_get", fake_get)

    LehmannsScraper().scrape("9783551741035")

    assert aufrufe == ["https://www.lehmanns.de/search/quick"]


def test_isbn10_findet_isbn13_seite(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    assert LehmannsScraper().scrape("3551741034").gefunden is True


def test_scrape_vorbestellbar(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_VORBESTELLBAR))

    assert LehmannsScraper().scrape("9783551741035").verfuegbarkeit == "Vorbestellbar"


def test_scrape_ohne_verfuegbarkeit(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_OHNE_VERFUEGBARKEIT))

    result = LehmannsScraper().scrape("9783551741035")

    assert result.gefunden is True
    assert result.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_ohne_preis(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_OHNE_PREIS))

    assert LehmannsScraper().scrape("9783551741035").gefunden is False


def test_scrape_andere_isbn(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_ANDERE_ISBN))

    assert LehmannsScraper().scrape("9783551741035").gefunden is False


def test_scrape_ohne_treffer(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(TREFFERLISTE_HTML))

    assert LehmannsScraper().scrape("9783551741035").gefunden is False


def test_scrape_http_fehler(monkeypatch):
    _antwortet(monkeypatch, FakeResponse("", ok=False))

    assert LehmannsScraper().scrape("9783551741035").gefunden is False
