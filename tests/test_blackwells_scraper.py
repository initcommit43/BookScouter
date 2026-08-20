"""Tests für den Blackwell's-Scraper.

Die zwei Fallstricke des Shops stehen im Mittelpunkt: der Nettopreis im
Button-Attribut, der nicht genommen werden darf, und die Empfehlungs-
karussells, die dieselbe Preisklasse tragen wie der Hauptartikel.
"""

from dataclasses import dataclass

import pytest

from bookscouter.scrapers import blackwells
from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT
from bookscouter.scrapers.blackwells import BlackwellsScraper

PRODUKT_URL = "https://blackwells.co.uk/bookshop/product/9781974709939"

# Der Karussell-Block steht bewusst *vor* dem Hauptartikel: ein Selektor
# ohne Eingrenzung greift den ersten Treffer in Dokumentreihenfolge ab und
# meldete damit 51,08 € statt 17,47 € – live so beobachtet.
DETAIL_HTML = """
<html><body>
<section class="recommendations">
  <article>
    <div class="product-price">
      <ul class="list--inline">
        <li class="product-price--current">51,08&euro;</li>
      </ul>
      <span class="is-hidden">Out Of Stock</span>
    </div>
  </article>
</section>

<div class="content product__info">
  <h1 class="product__name" itemprop="name">
    Chainsaw Man, Vol. 1 <small>Dog And Chainsaw</small>
    - Chainsaw Man
  </h1>
  <div class="product__price">
    <div class="product-price">
      <ul class="list--inline">
        <li class="product-price--current">17,47&euro;</li>
      </ul>
      <span class="is-hidden">In Stock</span>
    </div>
  </div>
  <form method="post" action="/bookshop/basket" class="addToBasket">
    <button class="btn js-add-to-basket"
      data-product-name="Chainsaw Man, Vol. 1"
      data-product-isbn="9781974709939"
      data-product-price="15.88"
      data-currency="EUR">Add to basket</button>
  </form>
</div>
</body></html>
"""

DETAIL_HTML_IN_GBP = (
    DETAIL_HTML.replace('data-currency="EUR"', 'data-currency="GBP"')
    .replace("17,47&euro;", "&pound;8.99")
)

DETAIL_HTML_OHNE_PREIS = DETAIL_HTML.replace(
    '<li class="product-price--current">17,47&euro;</li>', ""
)

DETAIL_HTML_OHNE_VERFUEGBARKEIT = DETAIL_HTML.replace(
    '<span class="is-hidden">In Stock</span>', ""
)

DETAIL_HTML_ANDERE_ISBN = DETAIL_HTML.replace(
    'data-product-isbn="9781974709939"', 'data-product-isbn="9781974709946"'
)

# Eine unbekannte ISBN landet auf der Suchseite, die mit HTTP 200 antwortet
# und keinen Produktblock hat.
SUCHSEITE_HTML = "<html><body><h1>Search results</h1><p>No results</p></body></html>"


@dataclass
class FakeResponse:
    text: str
    ok: bool = True
    url: str = PRODUKT_URL


def _antwortet(monkeypatch, antwort):
    monkeypatch.setattr(BlackwellsScraper, "_get", lambda self, url, **kwargs: antwort)


def test_scrape_found(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    result = BlackwellsScraper().scrape("9781974709939")

    assert result.gefunden is True
    assert result.titel == "Chainsaw Man, Vol. 1"
    assert result.preis == 17.47
    assert result.shop == "Blackwell's"
    assert result.isbn == "9781974709939"
    assert result.verfuegbarkeit == "Auf Lager"
    assert result.url == PRODUKT_URL


def test_titel_ohne_untertitel_und_reihe(monkeypatch):
    """Die `h1` führt Titel, Untertitel und Reihe ohne Trennzeichen hintereinander."""
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    assert BlackwellsScraper().scrape("9781974709939").titel == "Chainsaw Man, Vol. 1"


def test_nimmt_den_brutto_und_nicht_den_nettopreis(monkeypatch):
    """`data-product-price` führt den Nettopreis – die übrigen Shops melden brutto."""
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    assert BlackwellsScraper().scrape("9781974709939").preis != 15.88


def test_nimmt_nicht_den_preis_aus_dem_karussell(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    result = BlackwellsScraper().scrape("9781974709939")

    assert result.preis == 17.47
    assert result.verfuegbarkeit == "Auf Lager"


def test_ohne_suche_direkt_zur_produktseite(monkeypatch):
    aufrufe = []

    def fake_get(self, url, **kwargs):
        aufrufe.append(url)
        return FakeResponse(DETAIL_HTML)

    monkeypatch.setattr(BlackwellsScraper, "_get", fake_get)

    BlackwellsScraper().scrape("9781974709939")

    assert aufrufe == [PRODUKT_URL]


def test_isbn10_wird_zur_isbn13_url(monkeypatch):
    aufrufe = []

    def fake_get(self, url, **kwargs):
        aufrufe.append(url)
        return FakeResponse(DETAIL_HTML)

    monkeypatch.setattr(BlackwellsScraper, "_get", fake_get)

    assert BlackwellsScraper().scrape("1974709930").gefunden is True
    assert aufrufe == [PRODUKT_URL]


def test_euro_shop_ohne_originalpreis(monkeypatch):
    """Aus dem Euroraum zeichnet der Shop selbst in Euro aus – kein Kurs im Spiel."""
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    result = BlackwellsScraper().scrape("9781974709939")

    assert result.originalpreis is None
    assert result.originalwaehrung is None


def test_pfund_wird_umgerechnet(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_IN_GBP))
    monkeypatch.setattr(blackwells, "in_euro", lambda betrag, waehrung: betrag / 0.8571)

    result = BlackwellsScraper().scrape("9781974709939")

    assert result.gefunden is True
    assert result.preis == pytest.approx(10.49, abs=0.01)
    assert result.originalpreis == 8.99
    assert result.originalwaehrung == "GBP"


def test_ohne_kurs_nicht_gefunden(monkeypatch):
    """Lieber kein Ergebnis als ein Pfund-Betrag in der Euro-Spalte."""
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_IN_GBP))
    monkeypatch.setattr(blackwells, "in_euro", lambda betrag, waehrung: None)

    assert BlackwellsScraper().scrape("9781974709939").gefunden is False


def test_scrape_ohne_verfuegbarkeit(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_OHNE_VERFUEGBARKEIT))

    result = BlackwellsScraper().scrape("9781974709939")

    assert result.gefunden is True
    assert result.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_ohne_preis(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_OHNE_PREIS))

    assert BlackwellsScraper().scrape("9781974709939").gefunden is False


def test_scrape_andere_isbn(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_ANDERE_ISBN))

    assert BlackwellsScraper().scrape("9781974709939").gefunden is False


def test_unbekannte_isbn_landet_auf_der_suchseite(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(SUCHSEITE_HTML))

    assert BlackwellsScraper().scrape("9781974709939").gefunden is False


def test_scrape_http_fehler(monkeypatch):
    _antwortet(monkeypatch, FakeResponse("", ok=False))

    assert BlackwellsScraper().scrape("9781974709939").gefunden is False
