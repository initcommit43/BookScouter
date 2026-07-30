from dataclasses import dataclass

from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT
from bookscouter.scrapers.waltscomicshop import WaltsComicShopScraper

SEARCH_HTML_WITH_HIT = """
<html><body>
  <nav><a class="mobile-menu__nav-link" href="/products/walts-comic-shop-gift-card">Gifts</a></nav>
  <a href="/products/watchmen-tp-new-edition?_pos=1&_sid=abc&_ss=r" class="product-item__title text--strong link">Watchmen TP New Edition</a>
</body></html>
"""

SEARCH_HTML_NO_HIT = """
<html><body><p>No results could be found</p></body></html>
"""

# Shopifys .js-Endpunkt: kein "product"-Wrapper, Preis in Cent, dafür mit
# "available" – anders als der .json-Endpunkt, der keine Lagerinfo nennt.
PRODUCT_JS_WITH_MATCH = """
{
  "title": "Watchmen TP New Edition",
  "variants": [
    {"price": 2249, "barcode": "9781779501127", "available": true}
  ]
}
"""

PRODUCT_JS_SOLD_OUT = """
{
  "title": "Watchmen TP New Edition",
  "variants": [
    {"price": 2249, "barcode": "9781779501127", "available": false}
  ]
}
"""

PRODUCT_JS_WITHOUT_AVAILABILITY = """
{
  "title": "Watchmen TP New Edition",
  "variants": [
    {"price": 2249, "barcode": "9781779501127"}
  ]
}
"""

PRODUCT_JS_NO_BARCODE_MATCH = """
{
  "title": "Some Other Book",
  "variants": [
    {"price": 999, "barcode": "0000000000000", "available": true}
  ]
}
"""


@dataclass
class FakeResponse:
    text: str
    ok: bool = True


def test_scrape_found(monkeypatch):
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(PRODUCT_JS_WITH_MATCH)]
    monkeypatch.setattr(
        WaltsComicShopScraper, "_get", lambda self, url, **kwargs: responses.pop(0)
    )

    result = WaltsComicShopScraper().scrape("9781779501127")

    assert result.gefunden is True
    assert result.titel == "Watchmen TP New Edition"
    assert result.preis == 22.49
    assert result.shop == "Walt's Comic Shop"
    assert result.isbn == "9781779501127"
    assert result.verfuegbarkeit == "Auf Lager"
    # Ohne die Tracking-Parameter aus der Trefferliste.
    assert result.url == "https://www.waltscomicshop.com/products/watchmen-tp-new-edition"


def test_scrape_uses_js_endpoint(monkeypatch):
    """Nur .js nennt `available`; .json hätte keine Lagerinformation."""
    requested_urls = []
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(PRODUCT_JS_WITH_MATCH)]

    def fake_get(self, url, **kwargs):
        requested_urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(WaltsComicShopScraper, "_get", fake_get)

    WaltsComicShopScraper().scrape("9781779501127")

    assert requested_urls[1] == (
        "https://www.waltscomicshop.com/products/watchmen-tp-new-edition.js"
    )


def test_scrape_sold_out(monkeypatch):
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(PRODUCT_JS_SOLD_OUT)]
    monkeypatch.setattr(
        WaltsComicShopScraper, "_get", lambda self, url, **kwargs: responses.pop(0)
    )

    result = WaltsComicShopScraper().scrape("9781779501127")

    # Vergriffen ist trotzdem ein Treffer – der Preis interessiert weiterhin.
    assert result.gefunden is True
    assert result.preis == 22.49
    assert result.verfuegbarkeit == "Nicht auf Lager"


def test_scrape_without_availability_falls_back(monkeypatch):
    responses = [
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(PRODUCT_JS_WITHOUT_AVAILABILITY),
    ]
    monkeypatch.setattr(
        WaltsComicShopScraper, "_get", lambda self, url, **kwargs: responses.pop(0)
    )

    result = WaltsComicShopScraper().scrape("9781779501127")

    assert result.gefunden is True
    assert result.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_no_search_hit(monkeypatch):
    monkeypatch.setattr(
        WaltsComicShopScraper, "_get", lambda self, url, **kwargs: FakeResponse(SEARCH_HTML_NO_HIT)
    )

    result = WaltsComicShopScraper().scrape("0000000000000")

    assert result.gefunden is False
    assert result.titel is None
    assert result.preis is None


def test_scrape_search_request_failed(monkeypatch):
    monkeypatch.setattr(
        WaltsComicShopScraper, "_get", lambda self, url, **kwargs: FakeResponse("", ok=False)
    )

    result = WaltsComicShopScraper().scrape("9781779501127")

    assert result.gefunden is False


def test_scrape_detail_request_failed(monkeypatch):
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse("", ok=False)]
    monkeypatch.setattr(
        WaltsComicShopScraper, "_get", lambda self, url, **kwargs: responses.pop(0)
    )

    result = WaltsComicShopScraper().scrape("9781779501127")

    assert result.gefunden is False


def test_scrape_barcode_does_not_match_requested_isbn(monkeypatch):
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(PRODUCT_JS_NO_BARCODE_MATCH)]
    monkeypatch.setattr(
        WaltsComicShopScraper, "_get", lambda self, url, **kwargs: responses.pop(0)
    )

    result = WaltsComicShopScraper().scrape("9781779501127")

    assert result.gefunden is False
