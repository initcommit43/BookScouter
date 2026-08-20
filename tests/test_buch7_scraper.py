"""Tests für den buch7-Scraper.

Zwei Eigenheiten prägen diese Tests: der Abgleich läuft über den
`ean`-Parameter der erreichten URL (nicht über den Seiteninhalt), und die
Verfügbarkeit steht als deutsche Lieferzeit im Klartext.
"""

from dataclasses import dataclass

from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT
from bookscouter.scrapers.buch7 import Buch7Scraper

PRODUKT_URL = (
    "https://www.buch7.de/produkt/attack-on-titan-deluxe-1-hajime-isayama/"
    "1033619407?ean=9783551741035"
)
SUCHE_URL = "https://www.buch7.de/suche?search=9783551741035"

DETAIL_HTML = """
<html><body>
<h1>Attack on Titan Deluxe 1</h1>
<div id="produktseite" data-product-id="1033619407" data-matomo-price="25.00">
  <span class="produkt-verfuegbarkeit" id="hauptprodukt-verfuegbarkeit">
    <span>
      <span class="verfuegbarkeit verfuegbarkeit-1-2-werktage">
        <i class="fa-solid fa-truck"></i>
        auf Lager (1-2 Werktage)
      </span>
    </span>
  </span>
</div>
</body></html>
"""


def _mit_lieferzeit(text, klasse="verfuegbarkeit-3-6-wochen"):
    return DETAIL_HTML.replace("verfuegbarkeit-1-2-werktage", klasse).replace(
        "auf Lager (1-2 Werktage)", text
    )


DETAIL_HTML_OHNE_PREIS = DETAIL_HTML.replace(' data-matomo-price="25.00"', "")

DETAIL_HTML_OHNE_VERFUEGBARKEIT = DETAIL_HTML.replace(
    'class="verfuegbarkeit verfuegbarkeit-1-2-werktage"', 'class="etwas-anderes"'
)

# Ohne Treffer bleibt die Antwort auf der Suchseite stehen. Deren
# Trefferliste bringt durchaus Verfügbarkeits-Markup fremder Titel mit –
# live bei einer Fach-ISBN als E-Book-Zeile beobachtet.
SUCHSEITE_HTML = """
<html><body>
<h1>Suche</h1>
<span class="verfuegbarkeit verfuegbarkeit-sofort-download">Sofort lieferbar (Download)</span>
</body></html>
"""


@dataclass
class FakeResponse:
    text: str
    ok: bool = True
    url: str = PRODUKT_URL


def _antwortet(monkeypatch, antwort):
    monkeypatch.setattr(Buch7Scraper, "_get", lambda self, url, **kwargs: antwort)


def test_scrape_found(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    result = Buch7Scraper().scrape("9783551741035")

    assert result.gefunden is True
    assert result.titel == "Attack on Titan Deluxe 1"
    assert result.preis == 25.00
    assert result.shop == "buch7"
    assert result.isbn == "9783551741035"
    assert result.verfuegbarkeit == "Auf Lager"
    assert result.url == PRODUKT_URL


def test_ein_einziger_request(monkeypatch):
    aufrufe = []

    def fake_get(self, url, **kwargs):
        aufrufe.append(url)
        return FakeResponse(DETAIL_HTML)

    monkeypatch.setattr(Buch7Scraper, "_get", fake_get)

    Buch7Scraper().scrape("9783551741035")

    assert aufrufe == ["https://www.buch7.de/suche"]


def test_isbn10_findet_isbn13_seite(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML))

    assert Buch7Scraper().scrape("3551741034").gefunden is True


def test_lieferzeit_in_wochen_ist_nachbestellt(monkeypatch):
    """Wochen sind weder "auf Lager" noch "nicht lieferbar", sondern besorgbar."""
    _antwortet(monkeypatch, FakeResponse(_mit_lieferzeit("gewöhnlich ca. 3-6 Wochen")))

    assert Buch7Scraper().scrape("9783551741035").verfuegbarkeit == "Nachbestellt"


def test_noch_nicht_am_lager_ist_nachbestellt(monkeypatch):
    _antwortet(
        monkeypatch,
        FakeResponse(_mit_lieferzeit("Artikel neu aufgenommen, noch nicht am Lager")),
    )

    assert Buch7Scraper().scrape("9783551741035").verfuegbarkeit == "Nachbestellt"


def test_sofort_lieferbar_ist_auf_lager(monkeypatch):
    _antwortet(
        monkeypatch,
        FakeResponse(_mit_lieferzeit("Sofort lieferbar (Download)", "verfuegbarkeit-sofort-download")),
    )

    assert Buch7Scraper().scrape("9783551741035").verfuegbarkeit == "Auf Lager"


def test_vergriffen_ist_nicht_auf_lager(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(_mit_lieferzeit("Titel ist vergriffen")))

    assert Buch7Scraper().scrape("9783551741035").verfuegbarkeit == "Nicht auf Lager"


def test_unbekannte_lieferzeit_faellt_zurueck(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(_mit_lieferzeit("Lieferbarkeit ungeklärt")))

    result = Buch7Scraper().scrape("9783551741035")

    assert result.gefunden is True
    assert result.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_ohne_verfuegbarkeit(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_OHNE_VERFUEGBARKEIT))

    result = Buch7Scraper().scrape("9783551741035")

    assert result.gefunden is True
    assert result.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_ohne_preis(monkeypatch):
    _antwortet(monkeypatch, FakeResponse(DETAIL_HTML_OHNE_PREIS))

    assert Buch7Scraper().scrape("9783551741035").gefunden is False


def test_ohne_treffer_bleibt_auf_der_suchseite(monkeypatch):
    """Kein `ean` in der URL heisst: keine Produktseite, egal was die Seite sonst zeigt."""
    _antwortet(monkeypatch, FakeResponse(SUCHSEITE_HTML, url=SUCHE_URL))

    assert Buch7Scraper().scrape("9783551741035").gefunden is False


def test_produktseite_eines_anderen_buchs(monkeypatch):
    _antwortet(
        monkeypatch,
        FakeResponse(DETAIL_HTML, url="https://www.buch7.de/produkt/x/1?ean=9783551741042"),
    )

    assert Buch7Scraper().scrape("9783551741035").gefunden is False


def test_scrape_http_fehler(monkeypatch):
    _antwortet(monkeypatch, FakeResponse("", ok=False))

    assert Buch7Scraper().scrape("9783551741035").gefunden is False
