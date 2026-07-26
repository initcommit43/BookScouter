from dataclasses import dataclass

from bookscouter.scrapers.morawa import MorawaScraper

DETAIL_HTML_WITH_PRICE = """
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "WebPage",
  "mainEntity": {
    "@type": ["book", "product"],
    "isbn": 9783546100335,
    "name": "Die Stra\\u00dfe",
    "offers": {
      "@type": "Offer",
      "priceCurrency": "EUR",
      "price": 26.95
    }
  }
}
</script>
</body></html>
"""

DETAIL_HTML_OTHER_ISBN = """
<html><body>
<script type="application/ld+json">
{
  "@type": "WebPage",
  "mainEntity": {
    "@type": ["book", "product"],
    "isbn": 9780000000000,
    "name": "Ganz anderes Buch",
    "offers": {"price": 9.99}
  }
}
</script>
</body></html>
"""

DETAIL_HTML_WITHOUT_PRICE = """
<html><body>
<script type="application/ld+json">
{
  "@type": "WebPage",
  "mainEntity": {
    "@type": ["book", "product"],
    "isbn": 9783546100335,
    "name": "Ohne Preis"
  }
}
</script>
</body></html>
"""

DETAIL_HTML_NO_BOOK_ENTITY = """
<html><body>
<script type="application/ld+json">
{"@type": "WebPage", "mainEntity": {"@type": ["organization"], "name": "Morawa"}}
</script>
</body></html>
"""


@dataclass
class FakeResponse:
    text: str
    ok: bool = True


def test_scrape_found(monkeypatch):
    monkeypatch.setattr(
        MorawaScraper, "_get", lambda self, url, **kwargs: FakeResponse(DETAIL_HTML_WITH_PRICE)
    )

    result = MorawaScraper().scrape("9783546100335")

    assert result.gefunden is True
    assert result.titel == "Die Straße"
    assert result.preis == 26.95
    assert result.shop == "Morawa.at"
    assert result.isbn == "9783546100335"


def test_scrape_uses_direct_isbn_url_without_search(monkeypatch):
    requested_urls = []

    def fake_get(self, url, **kwargs):
        requested_urls.append(url)
        return FakeResponse(DETAIL_HTML_WITH_PRICE)

    monkeypatch.setattr(MorawaScraper, "_get", fake_get)

    MorawaScraper().scrape("9783546100335")

    assert requested_urls == ["https://www.morawa.at/detail/ISBN-9783546100335"]


def test_scrape_converts_isbn10_to_isbn13_for_url(monkeypatch):
    """Morawa kennt nur ISBN-13, eine ISBN-10 in der URL liefert 404."""
    requested_urls = []

    def fake_get(self, url, **kwargs):
        requested_urls.append(url)
        return FakeResponse(DETAIL_HTML_WITH_PRICE)

    monkeypatch.setattr(MorawaScraper, "_get", fake_get)

    # 3546100336 ist die ISBN-10 zu 9783546100335.
    result = MorawaScraper().scrape("3546100336")

    assert requested_urls == ["https://www.morawa.at/detail/ISBN-9783546100335"]
    assert result.gefunden is True
    assert result.preis == 26.95


def test_scrape_not_carried_returns_404(monkeypatch):
    monkeypatch.setattr(
        MorawaScraper, "_get", lambda self, url, **kwargs: FakeResponse("", ok=False)
    )

    result = MorawaScraper().scrape("9783831041657")

    assert result.gefunden is False
    assert result.titel is None
    assert result.preis is None


def test_scrape_rejects_page_for_different_isbn(monkeypatch):
    monkeypatch.setattr(
        MorawaScraper, "_get", lambda self, url, **kwargs: FakeResponse(DETAIL_HTML_OTHER_ISBN)
    )

    result = MorawaScraper().scrape("9783546100335")

    assert result.gefunden is False


def test_scrape_missing_price(monkeypatch):
    monkeypatch.setattr(
        MorawaScraper, "_get", lambda self, url, **kwargs: FakeResponse(DETAIL_HTML_WITHOUT_PRICE)
    )

    result = MorawaScraper().scrape("9783546100335")

    assert result.gefunden is False


def test_scrape_no_book_entity(monkeypatch):
    monkeypatch.setattr(
        MorawaScraper, "_get", lambda self, url, **kwargs: FakeResponse(DETAIL_HTML_NO_BOOK_ENTITY)
    )

    result = MorawaScraper().scrape("9783546100335")

    assert result.gefunden is False
