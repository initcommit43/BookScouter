from dataclasses import dataclass

from bookscouter.scrapers.thalia import BuecherDeScraper, ThaliaDeScraper, ThaliaScraper

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

DETAIL_HTML_WITH_ENTITIES = """
<html><body>
<script type="application/ld+json">
{
    "@type": "Book",
    "isbn": "978-3-546-10033-5",
    "name": "Die Stra&szlig;e",
    "offers": {"price": "26.50"}
}
</script>
</body></html>
"""

# Thalia liefert im Fliesstext \\&quot; – eine in JSON ungültige Escape-Sequenz,
# an der json.loads den ganzen Block abwies (beobachtet bei 9783842006874).
DETAIL_HTML_WITH_INVALID_ESCAPE = """
<html><body>
<script type="application/ld+json">
{
    "@type": "Book",
    "isbn": "978-3-8420-0687-4",
    "name": "Gute Nacht, Punpun 01",
    "description": "Sein imaginierter Freund \\&quot;Gott\\&quot; hilft wenig.",
    "offers": {"price": "8.30"}
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


def test_scrape_decodes_html_entities_in_title(monkeypatch):
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_WITH_ENTITIES)]
    monkeypatch.setattr(ThaliaScraper, "_get", lambda self, url, **kwargs: responses.pop(0))

    result = ThaliaScraper().scrape("9783546100335")

    assert result.titel == "Die Straße"


def test_scrape_survives_invalid_json_escape(monkeypatch):
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_WITH_INVALID_ESCAPE)]
    monkeypatch.setattr(ThaliaScraper, "_get", lambda self, url, **kwargs: responses.pop(0))

    result = ThaliaScraper().scrape("9783842006874")

    assert result.gefunden is True
    assert result.titel == "Gute Nacht, Punpun 01"
    assert result.preis == 8.30


def test_scrape_rejects_page_with_other_isbn(monkeypatch):
    """Unscharfer Suchtreffer darf nicht als Preis des gesuchten Buchs durchgehen."""
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_WITH_PRICE)]
    monkeypatch.setattr(ThaliaScraper, "_get", lambda self, url, **kwargs: responses.pop(0))

    result = ThaliaScraper().scrape("9783842006874")

    assert result.gefunden is False
    assert result.preis is None


def test_scrape_accepts_isbn10_for_isbn13_page(monkeypatch):
    """Thalias Suche nimmt ISBN-10 an, die Seite führt aber die ISBN-13."""
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_WITH_PRICE)]
    monkeypatch.setattr(ThaliaScraper, "_get", lambda self, url, **kwargs: responses.pop(0))

    result = ThaliaScraper().scrape("3831041652")

    assert result.gefunden is True
    assert result.preis == 13.90


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


def test_de_scraper_uses_de_domain(monkeypatch):
    requested_urls = []
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_WITH_PRICE)]

    def fake_get(self, url, **kwargs):
        requested_urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(ThaliaDeScraper, "_get", fake_get)

    result = ThaliaDeScraper().scrape("9783831041657")

    assert result.shop == "Thalia.de"
    assert result.gefunden is True
    assert requested_urls[0].startswith("https://www.thalia.de/suche")
    assert requested_urls[1].startswith("https://www.thalia.de/shop/home/artikeldetails")


def test_buecherde_scraper_uses_buecherde_domain(monkeypatch):
    requested_urls = []
    responses = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_WITH_PRICE)]

    def fake_get(self, url, **kwargs):
        requested_urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(BuecherDeScraper, "_get", fake_get)

    result = BuecherDeScraper().scrape("9783831041657")

    assert result.shop == "Buecher.de"
    assert result.gefunden is True
    assert requested_urls[0].startswith("https://www.buecher.de/suche")
    assert requested_urls[1].startswith("https://www.buecher.de/shop/home/artikeldetails")
