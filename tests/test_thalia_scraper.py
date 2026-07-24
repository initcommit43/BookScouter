from dataclasses import dataclass

from bookscouter.scrapers.thalia import ThaliaScraper

SEARCH_HTML_WITH_HIT = """
<html><body>
  <a href="/shop/home/artikeldetails/A1059470515">Self-Care Collection. Ayurveda</a>
</body></html>
"""

SEARCH_HTML_NO_HIT = """
<html><body><p>keine Treffer</p></body></html>
"""

DETAIL_HTML_WITH_PRICE = """
<html><body>
<script type="application/ld+json">
{
    "@context": "https://schema.org/",
    "@type": "Book",
    "isbn": "978-3-8310-4165-7",
    "name": "Self-Care Collection. Ayurveda",
    "offers": {
        "@type": "Offer",
        "priceCurrency": "EUR",
        "price": "13.90"
    }
}
</script>
</body></html>
"""

DETAIL_HTML_WITHOUT_PRICE = """
<html><body>
<script type="application/ld+json">
{"@type": "Book", "isbn": "978-3-8310-4165-7", "name": "Ohne Preis"}
</script>
</body></html>
"""


@dataclass
class FakeResponse:
    text: str
    ok: bool = True


def test_scrape_found(monkeypatch):
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_WITH_PRICE)]
    monkeypatch.setattr(ThaliaScraper, "_get", lambda self, url, **kwargs: responses.pop(0))

    result = ThaliaScraper().scrape("9783831041657")

    assert result.gefunden is True
    assert result.titel == "Self-Care Collection. Ayurveda"
    assert result.preis == 13.90
    assert result.shop == "Thalia.at"
    assert result.isbn == "9783831041657"


def test_scrape_no_search_hit(monkeypatch):
    monkeypatch.setattr(
        ThaliaScraper, "_get", lambda self, url, **kwargs: FakeResponse(SEARCH_HTML_NO_HIT)
    )

    result = ThaliaScraper().scrape("0000000000000")

    assert result.gefunden is False
    assert result.titel is None
    assert result.preis is None


def test_scrape_detail_page_missing_price(monkeypatch):
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_WITHOUT_PRICE)]
    monkeypatch.setattr(ThaliaScraper, "_get", lambda self, url, **kwargs: responses.pop(0))

    result = ThaliaScraper().scrape("9783831041657")

    assert result.gefunden is False


def test_scrape_search_request_failed(monkeypatch):
    monkeypatch.setattr(
        ThaliaScraper, "_get", lambda self, url, **kwargs: FakeResponse("", ok=False)
    )

    result = ThaliaScraper().scrape("9783831041657")

    assert result.gefunden is False
