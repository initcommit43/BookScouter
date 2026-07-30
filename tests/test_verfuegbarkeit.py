"""Tests für die Übersetzung der schema.org-Verfügbarkeiten."""

from bookscouter.scrapers.base import (
    VERFUEGBARKEIT_UNBEKANNT,
    ScrapeResult,
    verfuegbarkeit_aus_schema_org,
)


def test_url_schreibweise():
    assert verfuegbarkeit_aus_schema_org("https://schema.org/InStock") == "Auf Lager"


def test_http_und_nachgestellter_schraegstrich():
    assert verfuegbarkeit_aus_schema_org("http://schema.org/OutOfStock/") == "Nicht auf Lager"


def test_blosser_name_ohne_url():
    assert verfuegbarkeit_aus_schema_org("PreOrder") == "Vorbestellbar"


def test_unbekannter_wert_faellt_zurueck():
    assert verfuegbarkeit_aus_schema_org("https://schema.org/Erfunden") == VERFUEGBARKEIT_UNBEKANNT


def test_fehlender_wert_faellt_zurueck():
    assert verfuegbarkeit_aus_schema_org(None) == VERFUEGBARKEIT_UNBEKANNT


def test_nicht_string_faellt_zurueck_statt_zu_werfen():
    # Ein unerwarteter Typ im JSON-LD darf keine sonst gelungene Abfrage kosten.
    assert verfuegbarkeit_aus_schema_org({"@id": "InStock"}) == VERFUEGBARKEIT_UNBEKANNT


def test_scrape_result_hat_rueckfallwerte():
    ergebnis = ScrapeResult(shop="Shop", isbn="9783546100335", titel=None, preis=None, gefunden=False)
    assert ergebnis.verfuegbarkeit == VERFUEGBARKEIT_UNBEKANNT
    assert ergebnis.url is None
