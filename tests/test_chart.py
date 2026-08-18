"""Tests für die Rechenlogik des Preisverlauf-Diagramms.

Wie bei der übrigen UI ohne echtes Fenster: geprüft werden nur die Funktionen,
die aus der Historie Datenpunkte und Achsenbereiche machen. Das Zeichnen
selbst braucht einen Bildschirm und wird von Hand geprüft.
"""

from datetime import date

from bookscouter.chart import SERIENFARBEN, aggregiere_nach_tag, berechne_y_achse, serienstil


def test_aggregiert_je_shop_und_tag():
    punkte = [
        {"shop": "Thalia.at", "preis": 26.50, "datum": "2026-07-24T10:00:00+00:00"},
        {"shop": "Thalia.at", "preis": 25.00, "datum": "2026-07-25T10:00:00+00:00"},
        {"shop": "Morawa.at", "preis": 26.95, "datum": "2026-07-25T10:00:00+00:00"},
    ]

    serien = aggregiere_nach_tag(punkte)

    assert serien["Thalia.at"] == [(date(2026, 7, 24), 26.50), (date(2026, 7, 25), 25.00)]
    assert serien["Morawa.at"] == [(date(2026, 7, 25), 26.95)]


def test_mehrere_abfragen_am_selben_tag_werden_zur_letzten():
    """Eine Suche schreibt pro Shop eine Zeile – mehrmals am Tag gesucht zählt der letzte Preis."""
    punkte = [
        {"shop": "Thalia.at", "preis": 26.50, "datum": "2026-07-25T09:00:00+00:00"},
        {"shop": "Thalia.at", "preis": 24.99, "datum": "2026-07-25T21:13:00+00:00"},
    ]

    assert aggregiere_nach_tag(punkte)["Thalia.at"] == [(date(2026, 7, 25), 24.99)]


def test_reihenfolge_der_eingabe_egal():
    punkte = [
        {"shop": "Thalia.at", "preis": 24.99, "datum": "2026-07-25T21:13:00+00:00"},
        {"shop": "Thalia.at", "preis": 26.50, "datum": "2026-07-25T09:00:00+00:00"},
    ]

    assert aggregiere_nach_tag(punkte)["Thalia.at"] == [(date(2026, 7, 25), 24.99)]


def test_unlesbares_datum_wird_uebersprungen():
    punkte = [
        {"shop": "Thalia.at", "preis": 26.50, "datum": "kein-datum"},
        {"shop": "Thalia.at", "preis": 25.00, "datum": "2026-07-25T10:00:00+00:00"},
    ]

    assert aggregiere_nach_tag(punkte)["Thalia.at"] == [(date(2026, 7, 25), 25.00)]


def test_leere_historie():
    assert aggregiere_nach_tag([]) == {}


def test_y_achse_umschliesst_die_werte_mit_luft():
    unten, oben, _schritt = berechne_y_achse([25.00, 26.95])

    assert unten < 25.00
    assert oben > 26.95


def test_y_achse_liegt_auf_glatten_werten():
    """Sonst steht an der Achse "24,71 €" statt "25,00 €"."""
    unten, oben, schritt = berechne_y_achse([25.00, 26.95])

    assert unten % schritt == 0
    assert oben % schritt == 0


def test_y_achse_bei_durchgehend_gleichem_preis():
    """Sonst läge die waagerechte Linie exakt auf dem Rahmen."""
    unten, oben, _schritt = berechne_y_achse([25.00, 25.00])

    assert unten < 25.00 < oben


def test_y_achse_bei_kleinen_preisunterschieden():
    """Manga-Preise liegen dicht beieinander – die Achse darf nicht kollabieren."""
    unten, oben, schritt = berechne_y_achse([8.00, 8.30])

    assert unten < 8.00
    assert oben > 8.30
    assert schritt <= 0.5


def test_jeder_shop_bekommt_einen_eigenen_stil():
    """Zwei Shops duerfen nie gleich aussehen.

    Es gibt mehr Shops als Farbslots, deshalb reicht die Farbe allein nicht:
    ab Slot 9 unterscheidet zusaetzlich die Strichart. Geprueft wird die
    Kombination aus beidem.
    """
    from bookscouter.scrapers import ALL_SCRAPERS

    stile = [serienstil(nummer) for nummer in range(len(ALL_SCRAPERS))]

    assert len(set(stile)) == len(ALL_SCRAPERS)


def test_erste_slots_sind_durchgezogen():
    """Solange die Farbslots reichen, bleibt jede Linie durchgezogen."""
    for nummer in range(len(SERIENFARBEN)):
        farbpaar, strich = serienstil(nummer)

        assert farbpaar == SERIENFARBEN[nummer]
        assert strich == ()


def test_ueberzaehlige_slots_werden_gestrichelt():
    """Slot 9 wiederholt die Farbe von Slot 1 – dann aber gestrichelt."""
    farbpaar, strich = serienstil(len(SERIENFARBEN))

    assert farbpaar == SERIENFARBEN[0]
    assert strich != ()
