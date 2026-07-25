"""Tests für die reine Anzeige-Logik der UI.

Bewusst ohne echtes Fenster: getestet werden nur die Funktionen, die Werte
für die Darstellung aufbereiten. Der Aufbau der Widgets selbst braucht einen
Bildschirm und wird von Hand geprüft.
"""

from bookscouter.ui import BookScouterApp, FARBE_GEDAEMPFT, FARBE_GUENSTIGER, FARBE_TEURER
from bookscouter.ui import format_datum, format_preis


def test_format_preis_uses_german_decimal_comma():
    assert format_preis(26.5) == "26,50 €"
    assert format_preis(7.0) == "7,00 €"


def test_format_datum_from_iso_timestamp():
    assert format_datum("2026-07-25T19:32:07.862179+00:00") == "25.07.2026"


def test_format_datum_passes_through_unparsable_value():
    assert format_datum("keine-datumsangabe") == "keine-datumsangabe"


def test_differenz_teurer():
    text, farbe = BookScouterApp._differenz(26.50, 24.99)
    assert text == "▲ +1,51 €"
    assert farbe == FARBE_TEURER


def test_differenz_guenstiger():
    text, farbe = BookScouterApp._differenz(25.00, 27.50)
    assert text == "▼ -2,50 €"
    assert farbe == FARBE_GUENSTIGER


def test_differenz_unveraendert():
    text, farbe = BookScouterApp._differenz(25.00, 25.00)
    assert text == "– unverändert"
    assert farbe == FARBE_GEDAEMPFT


def test_vorherige_preise_keeps_latest_entry_per_shop():
    """Die Historie ist aufsteigend sortiert – der letzte Eintrag je Shop gewinnt."""
    historie = [
        {"shop": "Thalia.at", "preis": 27.50, "datum": "2026-05-12T10:00:00+00:00"},
        {"shop": "Thalia.at", "preis": 24.99, "datum": "2026-06-24T10:00:00+00:00"},
        {"shop": "Morawa.at", "preis": 26.95, "datum": "2026-06-24T10:00:00+00:00"},
    ]

    app = BookScouterApp.__new__(BookScouterApp)  # ohne Tk-Fenster
    app._merke_vorherige_preise(historie)

    assert app._vorherige_preise["Thalia.at"]["preis"] == 24.99
    assert app._vorherige_preise["Morawa.at"]["preis"] == 26.95
