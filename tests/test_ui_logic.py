"""Tests für die reine Anzeige-Logik der UI.

Bewusst ohne echtes Fenster: getestet werden nur die Funktionen, die Werte
für die Darstellung aufbereiten. Der Aufbau der Widgets selbst braucht einen
Bildschirm und wird von Hand geprüft.
"""

from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT, ScrapeResult
from bookscouter.ui import BookScouterApp, FARBE_GEDAEMPFT, FARBE_GUENSTIGER, FARBE_TEURER
from bookscouter.ui import Fehlerzeile, format_preis


def test_format_preis_uses_german_decimal_comma():
    assert format_preis(26.5) == "26,50 €"
    assert format_preis(7.0) == "7,00 €"


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


def test_verfuegbarkeits_farbe_lieferbar():
    assert BookScouterApp._verfuegbarkeits_farbe("Auf Lager") == FARBE_GUENSTIGER
    assert BookScouterApp._verfuegbarkeits_farbe("Nur im Laden") == FARBE_GUENSTIGER


def test_verfuegbarkeits_farbe_vergriffen():
    assert BookScouterApp._verfuegbarkeits_farbe("Nicht auf Lager") == FARBE_TEURER
    assert BookScouterApp._verfuegbarkeits_farbe("Ausverkauft") == FARBE_TEURER


def test_verfuegbarkeits_farbe_unbekannt_bleibt_neutral():
    """"Unbekannt" ist keine Aussage – also weder grün noch rot."""
    assert BookScouterApp._verfuegbarkeits_farbe(VERFUEGBARKEIT_UNBEKANNT) == FARBE_GEDAEMPFT
    assert BookScouterApp._verfuegbarkeits_farbe("Vorbestellbar") == FARBE_GEDAEMPFT


def _ergebnis(shop, preis, verfuegbarkeit="Auf Lager", gefunden=True):
    return ScrapeResult(
        shop=shop, isbn="9783546100335", titel="Die Straße", preis=preis,
        gefunden=gefunden, verfuegbarkeit=verfuegbarkeit,
    )


def _sortiere(zeilen):
    return [zeile.shop for zeile in sorted(zeilen, key=BookScouterApp._sortierschluessel)]


def test_sortierung_guenstigstes_angebot_zuerst():
    zeilen = [_ergebnis("Teuer", 26.95), _ergebnis("Billig", 22.99), _ergebnis("Mittel", 25.00)]

    assert _sortiere(zeilen) == ["Billig", "Mittel", "Teuer"]


def test_sortierung_vergriffenes_landet_hinter_lieferbarem():
    """Auch ein billigeres Angebot rutscht nach unten, wenn es vergriffen ist."""
    zeilen = [
        _ergebnis("Vergriffen", 9.99, "Nicht auf Lager"),
        _ergebnis("Lieferbar", 26.95, "Auf Lager"),
    ]

    assert _sortiere(zeilen) == ["Lieferbar", "Vergriffen"]


def test_sortierung_unklare_verfuegbarkeit_in_der_mitte():
    zeilen = [
        _ergebnis("Vergriffen", 10.00, "Nicht auf Lager"),
        _ergebnis("Unbekannt", 30.00, VERFUEGBARKEIT_UNBEKANNT),
        _ergebnis("Lieferbar", 40.00, "Auf Lager"),
    ]

    assert _sortiere(zeilen) == ["Lieferbar", "Unbekannt", "Vergriffen"]


def test_sortierung_nicht_gefuehrt_und_fehler_ganz_unten():
    zeilen = [
        Fehlerzeile(shop="Kaputt", text="Zeitüberschreitung"),
        _ergebnis("Nicht geführt", None, gefunden=False),
        _ergebnis("Vergriffen", 10.00, "Nicht auf Lager"),
        _ergebnis("Lieferbar", 40.00, "Auf Lager"),
    ]

    assert _sortiere(zeilen)[:2] == ["Lieferbar", "Vergriffen"]
    assert set(_sortiere(zeilen)[2:]) == {"Kaputt", "Nicht geführt"}


def test_sortierung_bei_gleichem_preis_bleibt_abfragereihenfolge():
    """Thalia.de und Buecher.de haben oft denselben Preis – dann nicht springen."""
    zeilen = [_ergebnis("Thalia.de", 25.00), _ergebnis("Buecher.de", 25.00)]

    assert _sortiere(zeilen) == ["Thalia.de", "Buecher.de"]


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
