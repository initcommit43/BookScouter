from dataclasses import dataclass

import pytest

from bookscouter.scrapers.altraverse import AltraverseScraper
from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT

PRODUKT_URL = "https://altraverse.de/manga/after-the-rain/111/after-the-rain-band-04"

SEARCH_HTML_WITH_HIT = f"""
<html><body>
<nav><a href="https://altraverse.de/manga/" title="Manga">Manga</a></nav>
<div class="listing">
  <a href="{PRODUKT_URL}" title="After the Rain, Band 04" class="product--image"></a>
  <a href="{PRODUKT_URL}" class="product--title" title="After the Rain, Band 04">
    After the Rain, Band 04
  </a>
</div>
</body></html>
"""

SEARCH_HTML_NO_HIT = """
<html><body>
<nav><a href="https://altraverse.de/manga/" title="Manga">Manga</a></nav>
<div class="listing"></div>
</body></html>
"""

DETAIL_HTML_IN_STOCK = """
<html><body>
<h1 class="product--title">After the Rain, Band 04</h1>
<div itemscope itemtype="https://schema.org/Product">
  <meta itemprop="name" content="altraverse" />
  <meta itemprop="productISBN" content="978-3-96358-152-6" />
  <div itemprop="offers" itemscope>
    <meta itemprop="priceCurrency" content="EUR" />
    <meta itemprop="price" content="10.00" />
    <link itemprop="availability" href="http://schema.org/InStock" />
  </div>
</div>
</body></html>
"""

DETAIL_HTML_OUT_OF_STOCK = DETAIL_HTML_IN_STOCK.replace(
    "http://schema.org/InStock", "http://schema.org/OutOfStock"
)

DETAIL_HTML_WITHOUT_AVAILABILITY = """
<html><body>
<h1 class="product--title">After the Rain, Band 04</h1>
<meta itemprop="productISBN" content="978-3-96358-152-6" />
<meta itemprop="price" content="10.00" />
</body></html>
"""

DETAIL_HTML_WITHOUT_PRICE = """
<html><body>
<h1 class="product--title">After the Rain, Band 04</h1>
<meta itemprop="productISBN" content="978-3-96358-152-6" />
<link itemprop="availability" href="http://schema.org/InStock" />
</body></html>
"""

DETAIL_HTML_OTHER_ISBN = """
<html><body>
<h1 class="product--title">After the Rain, Band 05</h1>
<meta itemprop="productISBN" content="978-3-96358-153-3" />
<meta itemprop="price" content="10.00" />
</body></html>
"""


@dataclass
class FakeResponse:
    text: str
    ok: bool = True


def _antworten(monkeypatch, *seiten):
    antworten = list(seiten)
    monkeypatch.setattr(
        AltraverseScraper, "_get", lambda self, url, **kwargs: antworten.pop(0)
    )


def test_scrape_found(monkeypatch):
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_IN_STOCK),
    )

    result = AltraverseScraper().scrape("9783963581526")

    assert result.gefunden is True
    assert result.titel == "After the Rain, Band 04"
    assert result.preis == 10.00
    assert result.shop == "altraverse"
    assert result.isbn == "9783963581526"
    assert result.verfuegbarkeit == "Auf Lager"
    assert result.url == PRODUKT_URL


def test_scrape_nicht_auf_lager(monkeypatch):
    """Die Verfügbarkeit steht im href des <link>, nicht in content."""
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_OUT_OF_STOCK),
    )

    result = AltraverseScraper().scrape("9783963581526")

    assert result.verfuegbarkeit == "Nicht auf Lager"


def test_scrape_ohne_verfuegbarkeit(monkeypatch):
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_WITHOUT_AVAILABILITY),
    )

    result = AltraverseScraper().scrape("9783963581526")

    assert result.gefunden is True
    assert result.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_ohne_preis(monkeypatch):
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_WITHOUT_PRICE),
    )

    assert AltraverseScraper().scrape("9783963581526").gefunden is False


def test_scrape_ohne_treffer(monkeypatch):
    _antworten(monkeypatch, FakeResponse(SEARCH_HTML_NO_HIT))

    assert AltraverseScraper().scrape("9783963581526").gefunden is False


def test_scrape_bei_fehlerstatus(monkeypatch):
    _antworten(monkeypatch, FakeResponse("", ok=False))

    assert AltraverseScraper().scrape("9783963581526").gefunden is False


def test_scrape_falsche_isbn_auf_der_seite(monkeypatch):
    """Die Suche liefert notfalls einen anderen Band derselben Reihe."""
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_OTHER_ISBN),
    )

    assert AltraverseScraper().scrape("9783963581526").gefunden is False


def test_scrape_sucht_mit_bindestrichen(monkeypatch):
    """Ohne die amtliche Schreibweise findet altraverses Suche nichts."""
    params = []
    antworten = [FakeResponse(SEARCH_HTML_WITH_HIT), FakeResponse(DETAIL_HTML_IN_STOCK)]

    def fake_get(self, url, **kwargs):
        params.append((url, kwargs.get("params")))
        return antworten.pop(0)

    monkeypatch.setattr(AltraverseScraper, "_get", fake_get)

    AltraverseScraper().scrape("9783963581526")

    assert params[0] == (
        "https://altraverse.de/search",
        {"sSearch": "978-3-96358-152-6"},
    )


def test_scrape_nimmt_ueberschrift_nicht_itemprop_name(monkeypatch):
    """`itemprop="name"` trägt den Hersteller, nicht den Buchtitel."""
    _antworten(
        monkeypatch,
        FakeResponse(SEARCH_HTML_WITH_HIT),
        FakeResponse(DETAIL_HTML_IN_STOCK),
    )

    result = AltraverseScraper().scrape("9783963581526")

    assert result.titel != "altraverse"


def test_fremde_isbn_gruppe_ohne_request(monkeypatch):
    """Eine englische ISBN kann altraverse nicht führen – kein Request nötig."""

    def fake_get(self, url, **kwargs):
        pytest.fail(f"Es darf kein Request rausgehen, war aber: {url}")

    monkeypatch.setattr(AltraverseScraper, "_get", fake_get)

    assert AltraverseScraper().scrape("9780306406157").gefunden is False
