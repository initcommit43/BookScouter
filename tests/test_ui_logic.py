"""Tests für die reine Anzeige-Logik der UI.

Bewusst ohne echtes Fenster: getestet werden nur die Funktionen, die Werte
für die Darstellung aufbereiten. Der Aufbau der Widgets selbst braucht einen
Bildschirm und wird von Hand geprüft.
"""

from bookscouter.scrapers import ALL_SCRAPERS
from bookscouter.scrapers.base import VERFUEGBARKEIT_UNBEKANNT, ScrapeResult
from bookscouter.ui import BookScouterApp, FARBE_GEDAEMPFT, FARBE_GUENSTIGER, FARBE_TEURER
from bookscouter.ui import (
    Buch, Fehlerzeile, bestes_angebot, format_preis, fortschritt_text,
    gewaehlte_scraper, shop_namen,
)


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


def test_shop_namen_matches_scraper_list():
    namen = shop_namen()

    assert len(namen) == len(ALL_SCRAPERS)
    assert namen[0] == "Thalia.at"
    assert "Morawa.at" in namen


def test_gewaehlte_scraper_alle_angehakt():
    auswahl = {name: True for name in shop_namen()}

    assert gewaehlte_scraper(auswahl) == ALL_SCRAPERS


def test_gewaehlte_scraper_filtert_abgewaehlte_heraus():
    auswahl = {name: name == "Morawa.at" for name in shop_namen()}

    gewaehlt = gewaehlte_scraper(auswahl)

    assert [cls().shop_name for cls in gewaehlt] == ["Morawa.at"]


def test_gewaehlte_scraper_behaelt_reihenfolge_von_all_scrapers():
    """Die Reihenfolge bestimmt die Diagrammfarben – sie darf nicht an der
    Reihenfolge im Auswahl-Dict hängen."""
    auswahl = {"Morawa.at": True, "Thalia.at": True}

    gewaehlt = [cls().shop_name for cls in gewaehlte_scraper(auswahl)]

    assert gewaehlt.index("Thalia.at") < gewaehlt.index("Morawa.at")


def test_gewaehlte_scraper_ohne_auswahl_ist_leer():
    auswahl = {name: False for name in shop_namen()}

    assert gewaehlte_scraper(auswahl) == []


def test_gewaehlte_scraper_unbekannter_shop_gilt_als_angehakt():
    """Ein Shop, der in der Auswahl fehlt, darf nicht stillschweigend
    wegfallen – lieber einer zu viel als einer zu wenig."""
    assert gewaehlte_scraper({}) == ALL_SCRAPERS


def test_vorherige_preise_keeps_latest_entry_per_shop():
    """Die Historie ist aufsteigend sortiert – der letzte Eintrag je Shop gewinnt."""
    historie = [
        {"shop": "Thalia.at", "preis": 27.50, "datum": "2026-05-12T10:00:00+00:00"},
        {"shop": "Thalia.at", "preis": 24.99, "datum": "2026-06-24T10:00:00+00:00"},
        {"shop": "Morawa.at", "preis": 26.95, "datum": "2026-06-24T10:00:00+00:00"},
    ]

    letzte = BookScouterApp._letzte_preise(historie)

    assert letzte["Thalia.at"]["preis"] == 24.99
    assert letzte["Morawa.at"]["preis"] == 26.95


# ------------------------------------------------------- Sammelabfrage: Bücher


def test_bestes_angebot_ist_das_guenstigste_lieferbare():
    zeilen = [_ergebnis("Teuer", 26.95), _ergebnis("Billig", 22.99)]

    assert bestes_angebot(zeilen).shop == "Billig"


def test_bestes_angebot_uebergeht_billigeres_vergriffenes():
    """Dieselbe Regel wie in der Tabelle: kaufen kann man nur, was da ist."""
    zeilen = [
        _ergebnis("Vergriffen", 9.99, "Nicht auf Lager"),
        _ergebnis("Lieferbar", 26.95, "Auf Lager"),
    ]

    assert bestes_angebot(zeilen).shop == "Lieferbar"


def test_bestes_angebot_nimmt_vergriffenes_wenn_es_nichts_anderes_gibt():
    zeilen = [_ergebnis("Vergriffen", 9.99, "Nicht auf Lager")]

    assert bestes_angebot(zeilen).shop == "Vergriffen"


def test_bestes_angebot_ohne_treffer_ist_none():
    zeilen = [
        Fehlerzeile(shop="Kaputt", text="Zeitüberschreitung"),
        _ergebnis("Nicht geführt", None, gefunden=False),
    ]

    assert bestes_angebot(zeilen) is None


def test_bestes_angebot_bei_leerer_liste_ist_none():
    """Solange noch kein Shop geantwortet hat, gibt es nichts anzuzeigen."""
    assert bestes_angebot([]) is None


def test_buch_gefunden_wenn_mindestens_ein_shop_liefert():
    buch = Buch(isbn="9783546100335")
    buch.zeilen = [_ergebnis("Leer", None, gefunden=False), _ergebnis("Treffer", 12.00)]

    assert buch.gefunden


def test_buch_ohne_treffer_gilt_als_nicht_gefunden():
    buch = Buch(isbn="9783546100335")
    buch.zeilen = [
        _ergebnis("Leer", None, gefunden=False),
        Fehlerzeile(shop="Kaputt", text="Zeitüberschreitung"),
    ]

    assert not buch.gefunden


def test_fortschritt_text_bei_einer_isbn_ohne_buchzaehlung():
    """"Buch 1 von 1" wäre nur Lärm."""
    assert fortschritt_text("Thalia.at", 1, 1, 2, 6) == "Frage Thalia.at ab … (2 von 6)"


def test_fortschritt_text_bei_mehreren_isbns_zaehlt_buecher_mit():
    text = fortschritt_text("Morawa.at", 3, 8, 4, 6)

    assert text == "Buch 3 von 8 · Frage Morawa.at ab … (4 von 6)"
