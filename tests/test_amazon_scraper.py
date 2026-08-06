"""Tests für AmazonScraper.

Die HTML-Fixtures sind von Hand gebaut, nicht aus einer echten Antwort
mitgeschnitten – anders als bei den übrigen Scrapern. Die Selektoren und die
Kernlogik selbst sind aber inzwischen live gegen amazon.de verifiziert
(siehe Docstring in `bookscouter/scrapers/amazon.py`), inklusive des dabei
gefundenen und in `scrapers/base.py` behobenen gzip-Bugs.
"""

from dataclasses import dataclass

from bookscouter.scrapers.amazon import AmazonScraper
from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT

HTML_FOUND = """
<html><body>
<span id="productTitle"> Die Straße </span>
<div id="corePrice_feature_div">
  <span class="a-price"><span class="a-offscreen">12,99&nbsp;€</span></span>
</div>
<div id="availability">
  <span class="a-size-medium a-color-success">Auf Lager.</span>
</div>
</body></html>
"""

HTML_LIMITED_STOCK = """
<html><body>
<span id="productTitle">Die Straße</span>
<div id="corePrice_feature_div">
  <span class="a-price"><span class="a-offscreen">12,99&nbsp;€</span></span>
</div>
<div id="availability">
  <span class="a-color-price">Nur noch 3 auf Lager (mehr ist unterwegs).</span>
</div>
</body></html>
"""

HTML_OUT_OF_STOCK = """
<html><body>
<span id="productTitle">Die Straße</span>
<div id="tp_price_block_total_price_ww">
  <span class="a-offscreen">12,99&nbsp;€</span>
</div>
<div id="availability">
  <span class="a-color-price">Derzeit nicht verfügbar.</span>
</div>
</body></html>
"""

HTML_WITHOUT_AVAILABILITY = """
<html><body>
<span id="productTitle">Die Straße</span>
<div id="corePrice_feature_div">
  <span class="a-price"><span class="a-offscreen">12,99&nbsp;€</span></span>
</div>
</body></html>
"""

HTML_WITHOUT_PRICE = """
<html><body>
<span id="productTitle">Die Straße</span>
</body></html>
"""

# Steht für sowohl "Titel nicht geführt" als auch eine CAPTCHA/Robot-Check-
# Seite ohne #productTitle – beides ist mit diesem Selektor nicht
# unterscheidbar, siehe Docstring in amazon.py.
HTML_WITHOUT_TITLE = """
<html><body><div>Bestätigen Sie, dass Sie kein Roboter sind.</div></body></html>
"""

HTML_THOUSANDS_SEPARATOR_PRICE = """
<html><body>
<span id="productTitle">Gesammelte Werke</span>
<span class="a-price"><span class="a-offscreen">1.234,56 €</span></span>
</body></html>
"""


@dataclass
class FakeResponse:
    text: str
    ok: bool = True


def test_scrape_found(monkeypatch):
    monkeypatch.setattr(AmazonScraper, "_get", lambda self, url, **kwargs: FakeResponse(HTML_FOUND))

    result = AmazonScraper().scrape("9783546100335")

    assert result.gefunden is True
    assert result.titel == "Die Straße"
    assert result.preis == 12.99
    assert result.shop == "Amazon.de"
    assert result.isbn == "9783546100335"
    assert result.verfuegbarkeit == "Auf Lager"
    assert result.url == "https://www.amazon.de/dp/3546100336"


def test_scrape_uses_isbn10_url_for_isbn13_input(monkeypatch):
    requested_urls = []

    def fake_get(self, url, **kwargs):
        requested_urls.append(url)
        return FakeResponse(HTML_FOUND)

    monkeypatch.setattr(AmazonScraper, "_get", fake_get)

    AmazonScraper().scrape("9783546100335")

    assert requested_urls == ["https://www.amazon.de/dp/3546100336"]


def test_scrape_isbn10_input_used_directly(monkeypatch):
    requested_urls = []

    def fake_get(self, url, **kwargs):
        requested_urls.append(url)
        return FakeResponse(HTML_FOUND)

    monkeypatch.setattr(AmazonScraper, "_get", fake_get)

    AmazonScraper().scrape("3546100336")

    assert requested_urls == ["https://www.amazon.de/dp/3546100336"]


def test_scrape_limited_stock(monkeypatch):
    monkeypatch.setattr(
        AmazonScraper, "_get", lambda self, url, **kwargs: FakeResponse(HTML_LIMITED_STOCK)
    )

    result = AmazonScraper().scrape("9783546100335")

    assert result.gefunden is True
    assert result.verfuegbarkeit == "Nur begrenzt"


def test_scrape_out_of_stock(monkeypatch):
    monkeypatch.setattr(
        AmazonScraper, "_get", lambda self, url, **kwargs: FakeResponse(HTML_OUT_OF_STOCK)
    )

    result = AmazonScraper().scrape("9783546100335")

    assert result.gefunden is True
    assert result.preis == 12.99
    assert result.verfuegbarkeit == "Nicht auf Lager"


def test_scrape_without_availability_falls_back(monkeypatch):
    monkeypatch.setattr(
        AmazonScraper, "_get", lambda self, url, **kwargs: FakeResponse(HTML_WITHOUT_AVAILABILITY)
    )

    result = AmazonScraper().scrape("9783546100335")

    assert result.gefunden is True
    assert result.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_missing_price_returns_not_found(monkeypatch):
    monkeypatch.setattr(
        AmazonScraper, "_get", lambda self, url, **kwargs: FakeResponse(HTML_WITHOUT_PRICE)
    )

    result = AmazonScraper().scrape("9783546100335")

    assert result.gefunden is False
    assert result.titel is None
    assert result.preis is None


def test_scrape_missing_title_returns_not_found(monkeypatch):
    monkeypatch.setattr(
        AmazonScraper, "_get", lambda self, url, **kwargs: FakeResponse(HTML_WITHOUT_TITLE)
    )

    result = AmazonScraper().scrape("9783546100335")

    assert result.gefunden is False


def test_scrape_request_not_ok_returns_not_found(monkeypatch):
    monkeypatch.setattr(AmazonScraper, "_get", lambda self, url, **kwargs: FakeResponse("", ok=False))

    result = AmazonScraper().scrape("9783546100335")

    assert result.gefunden is False


def test_scrape_979_prefix_isbn_returns_not_found_without_request(monkeypatch):
    """979-ISBN-13 hat keine ISBN-10-Entsprechung, also auch keine amazon.de-ASIN-URL."""
    requested_urls = []
    monkeypatch.setattr(
        AmazonScraper,
        "_get",
        lambda self, url, **kwargs: requested_urls.append(url) or FakeResponse(HTML_FOUND),
    )

    result = AmazonScraper().scrape("9791234567896")

    assert result.gefunden is False
    assert requested_urls == []


def test_scrape_price_with_thousands_separator(monkeypatch):
    monkeypatch.setattr(
        AmazonScraper,
        "_get",
        lambda self, url, **kwargs: FakeResponse(HTML_THOUSANDS_SEPARATOR_PRICE),
    )

    result = AmazonScraper().scrape("9783546100335")

    assert result.gefunden is True
    assert result.preis == 1234.56
