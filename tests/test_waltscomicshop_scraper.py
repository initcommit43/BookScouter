from dataclasses import dataclass

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

PRODUCT_JSON_WITH_MATCH = """
{
  "product": {
    "title": "Watchmen TP New Edition",
    "variants": [
      {"price": "22.49", "barcode": "9781779501127"}
    ]
  }
}
"""

PRODUCT_JSON_NO_BARCODE_MATCH = """
{
  "product": {
    "title": "Some Other Book",
    "variants": [
      {"price": "9.99", "barcode": "0000000000000"}
    ]
  }
}
"""


@dataclass
class FakeResponse:
    text: str
    ok: bool = True


def test_scrape_found(monkeypatch):
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(PRODUCT_JSON_WITH_MATCH)]
    monkeypatch.setattr(
        WaltsComicShopScraper, "_get", lambda self, url, **kwargs: responses.pop(0)
    )

    result = WaltsComicShopScraper().scrape("9781779501127")

    assert result.gefunden is True
    assert result.titel == "Watchmen TP New Edition"
    assert result.preis == 22.49
    assert result.shop == "Walt's Comic Shop"
    assert result.isbn == "9781779501127"


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
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(PRODUCT_JSON_NO_BARCODE_MATCH)]
    monkeypatch.setattr(
        WaltsComicShopScraper, "_get", lambda self, url, **kwargs: responses.pop(0)
    )

    result = WaltsComicShopScraper().scrape("9781779501127")

    assert result.gefunden is False
