"""Tests für den Wordery-Scraper.

Besonderheit gegenüber den anderen Microdata-Shops: die ISBN steht als
Elementtext statt in einem Attribut, und die Preise sind in Pfund.
"""

from dataclasses import dataclass

import pytest

from bookscouter.scrapers import wordery
from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT
from bookscouter.scrapers.wordery import WorderyScraper

PRODUKT_URL = "https://www.wordery.com/book/chainsaw-man-vol-1/tatsuki-fujimoto/9781974709939"

DETAIL_HTML = """
<html><body>
<div itemprop="mainEntity" itemscope itemtype="https://schema.org/Book">
  <h1 class="info-title" itemprop="name">Chainsaw Man, Vol. 1</h1>
  <div class="info-price" itemprop="offers" itemscope itemtype="http://schema.org/Offer">
    <link itemprop="availability" href="https://schema.org/InStock"/>
    <meta itemprop="priceCurrency" content="GBP"/>
    <meta itemprop="price" content="8.99"/>
    <span class="price-sale">&pound;8.99</span>
  </div>
  <ul>
    <li>ISBN: <span itemprop="isbn">9781974709939</span></li>
    <li>Number of pages: <span itemprop="numberOfPages">192</span></li>
  </ul>
</div>
</body></html>
"""

DETAIL_HTML_IN_EURO = DETAIL_HTML.replace(
    '<meta itemprop="priceCurrency" content="GBP"/>',
    '<meta itemprop="priceCurrency" content="EUR"/>',
)

DETAIL_HTML_OHNE_VERFUEGBARKEIT = DETAIL_HTML.replace(
    '<link itemprop="availability" href="https://schema.org/InStock"/>', ""
)

DETAIL_HTML_OHNE_PREIS = DETAIL_HTML.replace('<meta itemprop="price" content="8.99"/>', "")

DETAIL_HTML_ANDERE_ISBN = DETAIL_HTML.replace("9781974709939</span>", "9781974709946</span>")

FEHLERSEITE_HTML = "<html><body><h1>Page not found</h1></body></html>"


@dataclass
class FakeResponse:
    text: str
    ok: bool = True
    url: str = PRODUKT_URL


def _antwortet(monkeypatch, antwort):
    monkeypatch.setattr(WorderyScraper, "_get", lambda self, url, **kwargs: antwort)


def _kurs(monkeypatch, faktor=0.8571):
    monkeypatch.setattr(wordery, "in_euro", lambda betrag, waehrung: betrag / faktor)


def test_scrape_found(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))
    _kurs(monkeypatch)

    result = WorderyScraper().scrape("9781974709939")

    assert result.gefunden is True
    assert result.titel == "Chainsaw Man, Vol. 1"
    assert result.preis == pytest.approx(10.49, abs=0.01)
    assert result.shop == "Wordery"
    assert result.isbn == "9781974709939"
    assert result.verfuegbarkeit == "Auf Lager"
    assert result.url == PRODUKT_URL


def test_pfundbetrag_bleibt_erhalten(monkeypatch):
    """Der Ladenpreis ist der Pfund-Betrag – die Anzeige muss ihn nennen können."""
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))
    _kurs(monkeypatch)

    result = WorderyScraper().scrape("9781974709939")

    assert result.originalpreis == 8.99
    assert result.originalwaehrung == "GBP"


def test_euro_ohne_originalpreis(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_IN_EURO))
    monkeypatch.setattr(wordery, "in_euro", lambda betrag, waehrung: betrag)

    result = WorderyScraper().scrape("9781974709939")

    assert result.preis == 8.99
    assert result.originalpreis is None
    assert result.originalwaehrung is None


def test_ohne_kurs_nicht_gefunden(monkeypatch):
    """Lieber kein Ergebnis als ein Pfund-Betrag in der Euro-Spalte."""
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))
    monkeypatch.setattr(wordery, "in_euro", lambda betrag, waehrung: None)

    assert WorderyScraper().scrape("9781974709939").gefunden is False


def test_nutzt_den_erlaubten_kurzweg_statt_der_suche(monkeypatch):
    """`/search*` ist in der robots.txt gesperrt, `/book/*` nicht."""
    aufrufe = []

    def fake_get(self, url, **kwargs):
        aufrufe.append(url)
        return FakeResponse(DETAIL_HTML)

    monkeypatch.setattr(WorderyScraper, "_get", fake_get)
    _kurs(monkeypatch)

    WorderyScraper().scrape("9781974709939")

    assert aufrufe == ["https://wordery.com/book/9781974709939"]


def test_isbn10_wird_zur_isbn13_url(monkeypatch):
    aufrufe = []

    def fake_get(self, url, **kwargs):
        aufrufe.append(url)
        return FakeResponse(DETAIL_HTML)

    monkeypatch.setattr(WorderyScraper, "_get", fake_get)
    _kurs(monkeypatch)

    assert WorderyScraper().scrape("1974709930").gefunden is True
    assert aufrufe == ["https://wordery.com/book/9781974709939"]


def test_scrape_ohne_verfuegbarkeit(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_OHNE_VERFUEGBARKEIT))
    _kurs(monkeypatch)

    result = WorderyScraper().scrape("9781974709939")

    assert result.gefunden is True
    assert result.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_ohne_preis(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_OHNE_PREIS))
    _kurs(monkeypatch)

    assert WorderyScraper().scrape("9781974709939").gefunden is False


def test_scrape_andere_isbn(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_ANDERE_ISBN))
    _kurs(monkeypatch)

    assert WorderyScraper().scrape("9781974709939").gefunden is False


def test_scrape_unbekannte_isbn(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(FEHLERSEITE_HTML))
    _kurs(monkeypatch)

    assert WorderyScraper().scrape("9781974709939").gefunden is False


def test_scrape_http_fehler(monkeypatch):
    _antwortet(monkeypatch, FakeResponse("", ok=False))

    assert WorderyScraper().scrape("9781974709939").gefunden is False
