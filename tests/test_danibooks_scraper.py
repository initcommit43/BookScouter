from dataclasses import dataclass

from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT
from bookscouter.scrapers.danibooks import DaniBooksScraper

PRODUKT_URL = "https://www.danibooks.de/taylor-swift/194-taylor-swift-ein-swiftie-fanbuch.html"

SEARCH_HTML_WITH_HIT = f"""
<html><body>
<div class="products">
  <article class="product-miniature">
    <h2 class="product-title"><a href="{PRODUKT_URL}">Taylor Swift - Ein Swiftie-Fanbuch</a></h2>
  </article>
</div>
</body></html>
"""

SEARCH_HTML_NO_HIT = """
<html><body><div class="products"><p>Keine Ergebnisse</p></div></body></html>
"""

DETAIL_HTML_WITH_PRICE = """
<html><body>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": []}
</script>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Taylor Swift - Ein Swiftie-Fanbuch",
  "gtin13": "9783959560009",
  "offers": {
    "@type": "Offer",
    "priceCurrency": "EUR",
    "price": "19.99",
    "availability": "https://schema.org/PreOrder"
  }
}
</script>
</body></html>
"""

DETAIL_HTML_IN_STOCK = DETAIL_HTML_WITH_PRICE.replace(
    "https://schema.org/PreOrder", "https://schema.org/InStock"
)

DETAIL_HTML_WITHOUT_AVAILABILITY = """
<html><body>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Taylor Swift - Ein Swiftie-Fanbuch",
  "gtin13": "9783959560009",
  "offers": {"@type": "Offer", "price": "19.99"}
}
</script>
</body></html>
"""

DETAIL_HTML_WITHOUT_PRICE = """
<html><body>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Taylor Swift - Ein Swiftie-Fanbuch",
  "gtin13": "9783959560009",
  "offers": {"@type": "Offer", "availability": "https://schema.org/InStock"}
}
</script>
</body></html>
"""

DETAIL_HTML_OTHER_ISBN = """
<html><body>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Ganz anderes Buch",
  "gtin13": "9780000000000",
  "offers": {"@type": "Offer", "price": "9.99"}
}
</script>
</body></html>
"""


@dataclass
class FakeResponse:
    text: str
    ok: bool = True


def _antworten(monkeypatch, *seiten):
    antworten = list(seiten)
    monkeypatch.setattr(
        DaniBooksScraper, "_get", lambda self, url, **kwargs: antworten.pop(0)
    )


def test_scrape_found(monkeypatch):
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_IN_STOCK),
    )

    result = DaniBooksScraper().scrape("9783959560009")

    assert result.gefunden is True
    assert result.titel == "Taylor Swift - Ein Swiftie-Fanbuch"
    assert result.preis == 19.99
    assert result.shop == "dani books"
    assert result.isbn == "9783959560009"
    assert result.verfuegbarkeit == "Auf Lager"
    assert result.url == PRODUKT_URL


def test_scrape_vorbestellbar(monkeypatch):
    """PreOrder ist bei einem Verlagsshop der Normalfall für neue Bände."""
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_WITH_PRICE),
    )

    result = DaniBooksScraper().scrape("9783959560009")

    assert result.verfuegbarkeit == "Vorbestellbar"


def test_scrape_ohne_verfuegbarkeit(monkeypatch):
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_WITHOUT_AVAILABILITY),
    )

    result = DaniBooksScraper().scrape("9783959560009")

    assert result.gefunden is True
    assert result.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_ohne_preis(monkeypatch):
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_WITHOUT_PRICE),
    )

    assert DaniBooksScraper().scrape("9783959560009").gefunden is False


def test_scrape_ohne_treffer(monkeypatch):
    _antworten(monkeypatch, FakeResponse(SEARCH_HTML_NO_HIT))

    assert DaniBooksScraper().scrape("9783959560009").gefunden is False


def test_scrape_bei_fehlerstatus(monkeypatch):
    _antworten(monkeypatch, FakeResponse("", ok=False))

    assert DaniBooksScraper().scrape("9783959560009").gefunden is False


def test_scrape_falsche_isbn_auf_der_seite(monkeypatch):
    """Die Suche ist unscharf – ohne Abgleich käme ein fremder Preis durch."""
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_OTHER_ISBN),
    )

    assert DaniBooksScraper().scrape("9783959560009").gefunden is False


def test_scrape_sucht_mit_reiner_ziffernfolge(monkeypatch):
    """Anders als altraverse braucht dani books keine Bindestriche."""
    urls = []
    antworten = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_IN_STOCK)]

    def fake_get(self, url, **kwargs):
        urls.append((url, kwargs.get("params")))
        return antworten.pop(0)

    monkeypatch.setattr(DaniBooksScraper, "_get", fake_get)

    DaniBooksScraper().scrape("9783959560009")

    assert urls[0] == (
        "https://www.danibooks.de/suche",
        {"controller": "search", "s": "9783959560009"},
    )


def test_scrape_rechnet_isbn10_um(monkeypatch):
    """Eine ISBN-10-Eingabe muss dieselbe Seite finden wie die ISBN-13."""
    urls = []
    antworten = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_IN_STOCK)]

    def fake_get(self, url, **kwargs):
        urls.append(kwargs.get("params"))
        return antworten.pop(0)

    monkeypatch.setattr(DaniBooksScraper, "_get", fake_get)

    result = DaniBooksScraper().scrape("3959560001")

    assert urls[0]["s"] == "9783959560009"
    assert result.gefunden is True
