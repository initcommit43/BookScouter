"""Tests für das Lesen eines Preises aus einem Anzeigetext.

Gebraucht für die Shops ohne maschinenlesbaren Preis (buch7) und für
Blackwell's, das je nach Standort deutsch oder englisch auszeichnet – beide
Schreibweisen müssen durch dieselbe Funktion gehen.
"""

from bookscouter.scrapers.base import preis_aus_text


def test_deutsche_schreibweise():
    assert preis_aus_text("17,47 €") == 17.47


def test_englische_schreibweise():
    assert preis_aus_text("£8.99") == 8.99


def test_waehrung_hinter_dem_betrag():
    assert preis_aus_text("25,00 EUR") == 25.00


def test_tausendertrennung_deutsch():
    assert preis_aus_text("1.234,50 €") == 1234.50


def test_tausendertrennung_englisch():
    assert preis_aus_text("$1,234.50") == 1234.50


def test_tausendertrennung_ohne_nachkomma():
    """"1.234" ist kein Betrag mit drei Nachkommastellen, sondern eintausend."""
    assert preis_aus_text("1.234 €") == 1234.0


def test_glatter_betrag_ohne_trenner():
    assert preis_aus_text("15 €") == 15.0


def test_unformatierter_attributwert():
    # So liefert buch7 den Preis: `data-matomo-price="25.00"`.
    assert preis_aus_text("25.00") == 25.00


def test_beschriftung_stoert_nicht():
    assert preis_aus_text("Price: £8.99") == 8.99


def test_geschuetztes_leerzeichen_stoert_nicht():
    assert preis_aus_text("17,47\xa0€") == 17.47


def test_leerer_text_ergibt_none():
    assert preis_aus_text("") is None


def test_fehlender_text_ergibt_none():
    assert preis_aus_text(None) is None


def test_text_ohne_ziffern_ergibt_none():
    assert preis_aus_text("Preis auf Anfrage") is None
