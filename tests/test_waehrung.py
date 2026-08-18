"""Tests für die Währungsumrechnung.

Kein Netz: der EZB-Abruf wird durchweg ersetzt. Das Modul hält seinen Stand
in Modulvariablen, deshalb setzt `frischer_start` sie vor jedem Test zurück –
sonst würde der erste Test die Kurse für alle folgenden festnageln.
"""

from dataclasses import dataclass

import pytest

from bookscouter import waehrung

EZB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
                 xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <Cube>
    <Cube time='2026-08-18'>
      <Cube currency='USD' rate='1.1576'/>
      <Cube currency='CHF' rate='0.9406'/>
    </Cube>
  </Cube>
</gesmes:Envelope>
"""


@dataclass
class FakeResponse:
    text: str
    ok: bool = True


@pytest.fixture(autouse=True)
def frischer_start(monkeypatch, tmp_path):
    monkeypatch.setattr(waehrung, "_kurse", None)
    monkeypatch.setattr(waehrung, "_abgerufen", False)
    monkeypatch.setattr(waehrung, "KURS_CACHE_PATH", str(tmp_path / "wechselkurse.json"))


def _ezb_antwortet(monkeypatch, antwort):
    monkeypatch.setattr(waehrung, "hole", lambda url, params=None: antwort)


def test_euro_bleibt_unveraendert(monkeypatch):
    """Für Euro-Shops darf gar kein Kurs nötig sein."""

    def kein_abruf(url, params=None):
        pytest.fail("Für EUR darf die EZB nicht angefragt werden")

    monkeypatch.setattr(waehrung, "hole", kein_abruf)

    assert waehrung.in_euro(19.99, "EUR") == 19.99


def test_chf_wird_umgerechnet(monkeypatch):
    _ezb_antwortet(monkeypatch, FakeResponse(EZB_XML))

    # Die EZB notiert, wie viel Fremdwährung ein Euro kostet: 38.90 / 0.9406.
    assert waehrung.in_euro(38.90, "CHF") == pytest.approx(41.36, abs=0.01)


def test_kleinschreibung_wird_akzeptiert(monkeypatch):
    _ezb_antwortet(monkeypatch, FakeResponse(EZB_XML))

    assert waehrung.in_euro(38.90, "chf") == pytest.approx(41.36, abs=0.01)


def test_unbekannte_waehrung_ergibt_none(monkeypatch):
    _ezb_antwortet(monkeypatch, FakeResponse(EZB_XML))

    assert waehrung.in_euro(10.0, "XYZ") is None


def test_fehlende_waehrung_ergibt_none(monkeypatch):
    _ezb_antwortet(monkeypatch, FakeResponse(EZB_XML))

    assert waehrung.in_euro(10.0, None) is None


def test_ohne_netz_und_ohne_cache_ergibt_none(monkeypatch):
    _ezb_antwortet(monkeypatch, FakeResponse("", ok=False))

    assert waehrung.in_euro(38.90, "CHF") is None


def test_kaputtes_xml_ergibt_none(monkeypatch):
    _ezb_antwortet(monkeypatch, FakeResponse("<kein> gueltiges xml"))

    assert waehrung.in_euro(38.90, "CHF") is None


def test_kurse_werden_nur_einmal_geholt(monkeypatch):
    """Eine Sammelabfrage darf die EZB nicht pro Buch anfragen."""
    abrufe = []

    def zaehlender_abruf(url, params=None):
        abrufe.append(url)
        return FakeResponse(EZB_XML)

    monkeypatch.setattr(waehrung, "hole", zaehlender_abruf)

    waehrung.in_euro(10.0, "CHF")
    waehrung.in_euro(20.0, "CHF")
    waehrung.in_euro(30.0, "CHF")

    assert len(abrufe) == 1


def test_ohne_netz_wird_nur_einmal_versucht(monkeypatch):
    """Ohne Netz darf nicht jede ISBN erneut in den Timeout laufen."""
    abrufe = []

    def fehlschlag(url, params=None):
        abrufe.append(url)
        return FakeResponse("", ok=False)

    monkeypatch.setattr(waehrung, "hole", fehlschlag)

    waehrung.in_euro(10.0, "CHF")
    waehrung.in_euro(20.0, "CHF")

    assert len(abrufe) == 1


def test_zweiter_lauf_nutzt_die_datei(monkeypatch):
    """Beim nächsten Start am selben Tag genügt der Zwischenspeicher."""
    _ezb_antwortet(monkeypatch, FakeResponse(EZB_XML))
    waehrung.in_euro(10.0, "CHF")

    # Neuer "Programmlauf": Modulzustand weg, Datei bleibt.
    monkeypatch.setattr(waehrung, "_kurse", None)
    monkeypatch.setattr(waehrung, "_abgerufen", False)

    def kein_abruf(url, params=None):
        pytest.fail("Am selben Tag darf nicht erneut abgerufen werden")

    monkeypatch.setattr(waehrung, "hole", kein_abruf)

    assert waehrung.in_euro(38.90, "CHF") == pytest.approx(41.36, abs=0.01)


def test_veralteter_cache_wird_genutzt_wenn_netz_fehlt(monkeypatch):
    """Ein paar Tage alter Kurs schlägt gar kein Ergebnis."""
    _ezb_antwortet(monkeypatch, FakeResponse(EZB_XML))
    waehrung.in_euro(10.0, "CHF")

    import json
    from pathlib import Path

    pfad = Path(waehrung.KURS_CACHE_PATH)
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["geholt_am"] = "2020-01-01"
    pfad.write_text(json.dumps(daten), encoding="utf-8")

    monkeypatch.setattr(waehrung, "_kurse", None)
    monkeypatch.setattr(waehrung, "_abgerufen", False)
    _ezb_antwortet(monkeypatch, FakeResponse("", ok=False))

    assert waehrung.in_euro(38.90, "CHF") == pytest.approx(41.36, abs=0.01)
